"""Discovery sample: what does a declared-mutable, unchanged shared object cost on Sui?

For each sampled successful programmable transaction, take shared inputs declared
mutable whose BCS contents did not change. Such an object is still written back
(version bump), so the sender pays storage on it and gets the live rate of the old
rebate back at the live storage_rebate_rate (9999 of 10000).

Only aggregates are stored; no addresses, no digests.
Pure stdlib; run with python -I.
usage: python -I sui_unchanged_fee.py <out.json> [n_checkpoints] [spacing] [per_cp]
"""
import json
import statistics
import sys
import time
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
out = sys.argv[1]
RATE = 1 - 9999 / 10000  # storage_rebate_rate on mainnet, from protocol config
n_cp = int(sys.argv[2]) if len(sys.argv) > 2 else 40
spacing = int(sys.argv[3]) if len(sys.argv) > 3 else 5000
per_cp = int(sys.argv[4]) if len(sys.argv) > 4 else 50
URL = "https://graphql.mainnet.sui.io/graphql"

TX = """
  gasInput { gasPrice }
  kind { __typename ... on ProgrammableTransaction {
      inputs(first: 50) { nodes { __typename ... on SharedInput { address mutable } } }
  } }
  effects {
    status
    gasEffects { gasSummary { computationCost storageCost storageRebate nonRefundableStorageFee } }
    objectChanges(first: 50) { nodes { address
      inputState { storageRebate asMoveObject { contents { bcs } } }
      outputState { storageRebate asMoveObject { contents { bcs } } } } }
  }
"""


def gql(query, tries=6):
    body = json.dumps({"query": query}).encode()
    wait = 2
    for t in range(tries):
        req = urllib.request.Request(
            URL, data=body, headers={"Content-Type": "application/json", "User-Agent": "research-probe/0.1"}
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                d = json.loads(r.read().decode())
            if "errors" in d and not d.get("data"):
                raise RuntimeError(str(d["errors"])[:300])
            return d
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, RuntimeError) as e:
            if t < tries - 1:
                time.sleep(wait)
                wait = min(wait * 2, 60)
                continue
            raise


latest = gql("{ checkpoint { sequenceNumber } epoch { epochId referenceGasPrice } protocolConfigs { protocolVersion } }")
info = latest["data"]
cp0 = info["checkpoint"]["sequenceNumber"] - 20

n_ptb = n_ok_with_mut = n_with_unchanged = 0
n_mut = n_mut_unchanged = 0
per_object_rebate = []
per_object_fee = []
ratio_fee_to_comp = []
ratio_nonref_to_comp = []
comp_values = []
gas_prices = []
ts = []
errors = 0
for i in range(n_cp):
    cp = cp0 - i * spacing
    q = "{ checkpoint(sequenceNumber: %d) { timestamp transactions(first: %d) { nodes { %s } } } }" % (cp, per_cp, TX)
    try:
        d = gql(q)
    except Exception as e:  # noqa: BLE001
        errors += 1
        print("cp error", cp, str(e)[:200], flush=True)
        continue
    c = (d.get("data") or {}).get("checkpoint")
    if not c:
        continue
    ts.append(c.get("timestamp"))
    for n in c["transactions"]["nodes"]:
        k = n.get("kind") or {}
        if k.get("__typename") != "ProgrammableTransaction":
            continue
        n_ptb += 1
        eff = n.get("effects") or {}
        if eff.get("status") != "SUCCESS":
            continue
        muts = [
            x["address"]
            for x in (k.get("inputs") or {}).get("nodes", [])
            if x["__typename"] == "SharedInput" and x.get("mutable")
        ]
        if not muts:
            continue
        n_ok_with_mut += 1
        ch = {}
        for o in (eff.get("objectChanges") or {}).get("nodes") or []:
            a = o.get("inputState") or {}
            b = o.get("outputState") or {}
            abcs = ((a.get("asMoveObject") or {}).get("contents") or {}).get("bcs")
            bbcs = ((b.get("asMoveObject") or {}).get("contents") or {}).get("bcs")
            ch[o["address"]] = (abcs, bbcs, a.get("storageRebate"), b.get("storageRebate"))
        fee = 0.0
        any_unchanged = False
        for m in muts:
            n_mut += 1
            v = ch.get(m)
            if not v or v[0] is None or v[1] is None:
                continue
            if v[0] == v[1]:
                n_mut_unchanged += 1
                any_unchanged = True
                reb = int(v[2] or 0)
                per_object_rebate.append(reb)
                per_object_fee.append(RATE * reb)
                fee += RATE * reb
        gs = (eff.get("gasEffects") or {}).get("gasSummary") or {}
        comp = int(gs.get("computationCost") or 0)
        nonref = int(gs.get("nonRefundableStorageFee") or 0)
        gi = n.get("gasInput") or {}
        if gi.get("gasPrice") is not None:
            gas_prices.append(int(gi["gasPrice"]))
        if any_unchanged:
            n_with_unchanged += 1
            if comp > 0:
                ratio_fee_to_comp.append(fee / comp)
                comp_values.append(comp)
        if comp > 0:
            ratio_nonref_to_comp.append(nonref / comp)
    time.sleep(0.5)


def q(v, p):
    if not v:
        return None
    s = sorted(v)
    return s[min(len(s) - 1, int(p * len(s)))]


summary = {
    "url": URL,
    "epoch": info["epoch"],
    "protocol_version": info["protocolConfigs"]["protocolVersion"],
    "checkpoint_latest_minus_20": cp0,
    "n_checkpoints_requested": n_cp,
    "spacing": spacing,
    "timestamps_first_last": [ts[0], ts[-1]] if ts else None,
    "errors": errors,
    "n_programmable": n_ptb,
    "n_success_with_mutable_shared": n_ok_with_mut,
    "n_with_unchanged_mutable_shared": n_with_unchanged,
    "mutable_shared_declared": n_mut,
    "mutable_shared_unchanged": n_mut_unchanged,
    "object_storage_rebate_mist_p10_50_90": [q(per_object_rebate, 0.1), q(per_object_rebate, 0.5), q(per_object_rebate, 0.9)],
    "unchanged_object_fee_mist_p10_50_90": [q(per_object_fee, 0.1), q(per_object_fee, 0.5), q(per_object_fee, 0.9)],
    "fee_over_computation_p10_50_90": [q(ratio_fee_to_comp, 0.1), q(ratio_fee_to_comp, 0.5), q(ratio_fee_to_comp, 0.9)],
    "computation_cost_mist_p10_50_90": [q(comp_values, 0.1), q(comp_values, 0.5), q(comp_values, 0.9)],
    "nonrefundable_over_computation_p50": q(ratio_nonref_to_comp, 0.5),
    "gas_price_p10_50_90": [q(gas_prices, 0.1), q(gas_prices, 0.5), q(gas_prices, 0.9)],
    "fetched_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
}
json.dump(summary, open(out, "w", encoding="utf-8"), indent=1)
print(json.dumps(summary, indent=1))
