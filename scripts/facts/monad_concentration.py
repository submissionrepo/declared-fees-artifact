"""Discovery sample on Monad mainnet: who sends access lists (aggregates only), and
whether a block header's gasUsed equals the sum of its transactions' gas limits.

Stores no addresses. Pure stdlib; run with python -I.
usage: python -I monad_concentration.py <rpc> <out.json> [n_blocks] [step]
"""
import json
import sys
import time
import urllib.request
from collections import Counter

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
senders_all = Counter()
senders_al = Counter()
to_al = Counter()
hdr_match = hdr_total = 0
n_tx = 0
for i in range(nb):
    n = head - step * i - 10
    b = call("eth_getBlockByNumber", [hex(n), True])["result"]
    if not b:
        continue
    s = 0
    for tx in b["transactions"]:
        n_tx += 1
        s += int(tx["gas"], 16)
        senders_all[tx["from"]] += 1
        if tx.get("accessList"):
            senders_al[tx["from"]] += 1
            to_al[tx.get("to") or "create"] += 1
    hdr_total += 1
    if s == int(b["gasUsed"], 16):
        hdr_match += 1
    time.sleep(0.05)


def top_share(c, k):
    t = sum(c.values())
    return sum(v for _, v in c.most_common(k)) / t if t else None


summary = {
    "head": head,
    "n_blocks": hdr_total,
    "n_tx": n_tx,
    "header_gasUsed_equals_sum_of_limits": hdr_match,
    "n_senders_all": len(senders_all),
    "n_senders_with_list": len(senders_al),
    "n_list_txs": sum(senders_al.values()),
    "top1_sender_share_of_list_txs": top_share(senders_al, 1),
    "top5_sender_share_of_list_txs": top_share(senders_al, 5),
    "top10_sender_share_of_list_txs": top_share(senders_al, 10),
    "top10_target_share_of_list_txs": top_share(to_al, 10),
    "n_targets_with_list": len(to_al),
    "fetched_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
}
json.dump(summary, open(out, "w", encoding="utf-8"), indent=1)
print(json.dumps(summary, indent=1))
