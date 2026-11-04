"""Discovery sample: share of Monad transactions carrying an access list; receipts check.

Only aggregates are stored. Pure stdlib; run with python -I.
usage: python -I monad_al_share.py <rpc> <out.json> [n_blocks] [step]
"""
import json
import statistics
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
rpc, out = sys.argv[1], sys.argv[2]
nb = int(sys.argv[3]) if len(sys.argv) > 3 else 200
step = int(sys.argv[4]) if len(sys.argv) > 4 else 1500


def call(method, params):
    req = urllib.request.Request(
        rpc,
        data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode(),
        headers={"content-type": "application/json", "user-agent": "research-probe/0.1"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


head = int(call("eth_blockNumber", [])["result"], 16)
n_tx = n_al = errors = 0
n_addr = []
n_keys = []
types = {}
sum_limit = 0
sum_limit_al = 0
blocks_used = 0
first_ts = last_ts = None
for i in range(nb):
    n = head - step * i - 10
    try:
        b = call("eth_getBlockByNumber", [hex(n), True])["result"]
    except Exception:  # noqa: BLE001
        errors += 1
        time.sleep(1)
        continue
    if not b:
        errors += 1
        continue
    blocks_used += 1
    t = int(b["timestamp"], 16)
    first_ts = first_ts or t
    last_ts = t
    for tx in b["transactions"]:
        n_tx += 1
        ty = tx.get("type", "0x0")
        types[ty] = types.get(ty, 0) + 1
        lim = int(tx["gas"], 16)
        sum_limit += lim
        al = tx.get("accessList") or []
        if al:
            n_al += 1
            sum_limit_al += lim
            n_addr.append(len(al))
            n_keys.append(sum(len(a.get("storageKeys") or []) for a in al))
    time.sleep(0.05)

summary = {
    "rpc": rpc,
    "head": head,
    "blocks_used": blocks_used,
    "step": step,
    "first_ts": first_ts,
    "last_ts": last_ts,
    "errors": errors,
    "n_tx": n_tx,
    "n_with_access_list": n_al,
    "share_with_access_list": n_al / n_tx if n_tx else None,
    "share_of_gas_limit_with_access_list": sum_limit_al / sum_limit if sum_limit else None,
    "types": types,
    "addresses_per_list_median": statistics.median(n_addr) if n_addr else None,
    "keys_per_list_median": statistics.median(n_keys) if n_keys else None,
    "fetched_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
}
json.dump(summary, open(out, "w", encoding="utf-8"), indent=1)
print(json.dumps(summary, indent=1))
