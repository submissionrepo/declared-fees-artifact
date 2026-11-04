"""Sample Avalanche C-Chain mainnet receipts: how often gas charged equals ceil(limit/2)?

Pure stdlib; run with python -I.
usage: python -I avax_sample.py <rpc-url> <out.json> [n_blocks] [step] [txs_per_block]
"""
import json
import statistics
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
rpc, out = sys.argv[1], sys.argv[2]
nb = int(sys.argv[3]) if len(sys.argv) > 3 else 40
step = int(sys.argv[4]) if len(sys.argv) > 4 else 2000
nt = int(sys.argv[5]) if len(sys.argv) > 5 else 8


def call(method, params):
    req = urllib.request.Request(
        rpc,
        data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode(),
        headers={"content-type": "application/json", "user-agent": "research-probe/0.1"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


head = int(call("eth_blockNumber", [])["result"], 16)
rows, blocks = [], []
errors = 0
for i in range(nb):
    n = head - step * i - 20
    try:
        b = call("eth_getBlockByNumber", [hex(n), True])["result"]
    except Exception as e:  # noqa: BLE001
        errors += 1
        continue
    if not b:
        errors += 1
        continue
    blocks.append(
        {
            "number": n,
            "timestamp": int(b["timestamp"], 16),
            "gasLimit": int(b["gasLimit"], 16),
            "gasUsed": int(b["gasUsed"], 16),
            "baseFeePerGas": int(b.get("baseFeePerGas", "0x0"), 16),
            "txs": len(b["transactions"]),
        }
    )
    for tx in b["transactions"][:nt]:
        try:
            r = call("eth_getTransactionReceipt", [tx["hash"]])["result"]
        except Exception:  # noqa: BLE001
            errors += 1
            continue
        if not r:
            errors += 1
            continue
        rows.append(
            {
                "block": n,
                "type": tx.get("type"),
                "gas_limit": int(tx["gas"], 16),
                "gas_used_receipt": int(r["gasUsed"], 16),
                "effective_gas_price": int(r.get("effectiveGasPrice", "0x0"), 16),
                "status": r["status"],
            }
        )
    time.sleep(0.1)

half = [x for x in rows if x["gas_used_receipt"] == (x["gas_limit"] + 1) // 2]
below = [x for x in rows if x["gas_used_receipt"] < (x["gas_limit"] + 1) // 2]
eq_limit = [x for x in rows if x["gas_used_receipt"] == x["gas_limit"]]
ratio = [x["gas_used_receipt"] / x["gas_limit"] for x in rows if x["gas_limit"]]
summary = {
    "rpc": rpc,
    "head": head,
    "n_blocks": len(blocks),
    "n_tx": len(rows),
    "errors": errors,
    "receipts_eq_half_limit_rounded_up": len(half),
    "receipts_below_half_limit": len(below),
    "receipts_eq_limit": len(eq_limit),
    "ratio_median": statistics.median(ratio) if ratio else None,
    "ratio_p10": sorted(ratio)[len(ratio) // 10] if ratio else None,
    "first_block_ts": blocks[0]["timestamp"] if blocks else None,
    "last_block_ts": blocks[-1]["timestamp"] if blocks else None,
    "fetched_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
}
json.dump(summary, open(out, "w", encoding="utf-8"), indent=1)
print({k: v for k, v in summary.items() if k not in ("rows", "blocks")})
print(blocks[:2])
print(rows[:6])
