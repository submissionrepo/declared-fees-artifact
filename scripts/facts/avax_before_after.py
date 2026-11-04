"""Avalanche C-Chain before and after ACP-194, which from September 22, 2026 charges max(used, limit / 2).

Does a charge on unused gas change what senders declare?  We read evenly spaced blocks from a window before the change
and a window after it, with each transaction's limit, status and gas used (the receipt records the charged amount after
the change).  Reduced records with sender identities go to data/ and are never reported; results hold aggregates only.

Usage: python avax_before_after.py <rpc-url> <out.json> [n_blocks_per_window] [txs_per_block]
"""
import json
import statistics as st
import sys
import time
import urllib.request
from calendar import timegm
from collections import defaultdict
from pathlib import Path

rpc, out = sys.argv[1], sys.argv[2]
NB = int(sys.argv[3]) if len(sys.argv) > 3 else 600
NT = int(sys.argv[4]) if len(sys.argv) > 4 else 8
DATA = Path(__file__).resolve().parents[2] / "data" / "avax_before_after.jsonl"
WINDOWS = {"before": ((2026, 8, 25), (2026, 9, 22)), "after": ((2026, 10, 4), (2026, 11, 1))}


def call(method, params, tries=6):
    wait = 1.0
    for t in range(tries):
        try:
            req = urllib.request.Request(rpc, data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode(),
                                         headers={"content-type": "application/json", "user-agent": "research-probe/0.1"})
            with urllib.request.urlopen(req, timeout=40) as r:
                d = json.load(r)
            if "result" in d:
                return d["result"]
        except Exception:  # noqa: BLE001
            pass
        time.sleep(wait)
        wait = min(wait * 2, 30)
    return None


def block_ts(n):
    b = call("eth_getBlockByNumber", [hex(n), False])
    return int(b["timestamp"], 16)


def at_time(ts, hi):
    lo = 0
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if block_ts(mid) < ts:
            lo = mid
        else:
            hi = mid
    return hi


def stamp(y, m, d, h=0):
    return timegm((y, m, d, h, 0, 0))


def collect(head):
    rows = []
    for name, (start, end) in WINDOWS.items():
        a = at_time(stamp(*start), head)
        b = at_time(stamp(*end, 15) if name == "before" else stamp(*end), head)
        step = max(1, (b - a) // NB)
        for i in range(NB):
            n = a + i * step
            blk = call("eth_getBlockByNumber", [hex(n), True])
            if not blk:
                continue
            for tx in blk["transactions"][:NT]:
                if not tx.get("to"):
                    continue
                rc = call("eth_getTransactionReceipt", [tx["hash"]])
                if not rc:
                    continue
                rows.append({"w": name, "n": n, "t": int(blk["timestamp"], 16), "from": tx["from"], "to": tx["to"], "sel": tx["input"][:10],
                             "limit": int(tx["gas"], 16), "gas": int(rc["gasUsed"], 16), "ok": int(rc["status"], 16)})
            time.sleep(0.05)
        print(name, "blocks", a, b, "rows so far", len(rows), flush=True)
    with open(DATA, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    return rows


def half(limit):
    return (limit + 1) // 2


def summarize(rows):
    res = {}
    by = {"before": [r for r in rows if r["w"] == "before"], "after": [r for r in rows if r["w"] == "after"]}
    for name, rs in by.items():
        lim = [r["limit"] for r in rs]
        # at or below half the limit: gas used before the change, the charged amount sitting at the floor after it
        at_half = [r["gas"] * 2 <= r["limit"] + 1 for r in rs]
        res[name] = {"txs": len(rs), "senders": len({r["from"] for r in rs}), "limit_median": st.median(lim),
                     "share_used_at_or_below_half": round(sum(at_half) / max(1, len(rs)), 4),
                     "share_failed": round(sum(not r["ok"] for r in rs) / max(1, len(rs)), 4),
                     "ratio_gas_over_limit_median": round(st.median(r["gas"] / r["limit"] for r in rs), 4)}
    # the same call before and after: sender, target and function
    for key_name, key in (("sender_target_function", lambda r: (r["from"], r["to"], r["sel"])), ("target_function", lambda r: (r["to"], r["sel"]))):
        groups = defaultdict(lambda: {"before": [], "after": []})
        for r in rows:
            groups[key(r)][r["w"]].append(r)
        pairs = [(g["before"], g["after"]) for g in groups.values() if len(g["before"]) >= 3 and len(g["after"]) >= 3]
        ratios = [st.median(x["limit"] for x in a) / st.median(x["limit"] for x in b) for b, a in pairs]
        over_before = [sum(x["gas"] * 2 <= x["limit"] + 1 for x in b) / len(b) for b, a in pairs]
        over_after = [sum(x["gas"] * 2 <= x["limit"] + 1 for x in a) / len(a) for b, a in pairs]
        res[key_name] = {"pairs": len(pairs), "txs_before": sum(len(b) for b, a in pairs), "txs_after": sum(len(a) for b, a in pairs),
                         "limit_ratio_after_over_before_median": round(st.median(ratios), 4) if ratios else None,
                         "share_pairs_limit_fell": round(sum(x < 0.99 for x in ratios) / max(1, len(ratios)), 4),
                         "share_pairs_limit_rose": round(sum(x > 1.01 for x in ratios) / max(1, len(ratios)), 4),
                         "at_half_share_before_mean": round(st.mean(over_before), 4) if over_before else None,
                         "at_half_share_after_mean": round(st.mean(over_after), 4) if over_after else None,
                         # the calls most exposed to the charge: at or below half the limit in most of their uses before
                         "exposed_pairs": sum(x >= 0.5 for x in over_before),
                         "exposed_limit_ratio_median": round(st.median(r for r, o in zip(ratios, over_before) if o >= 0.5), 4) if any(o >= 0.5 for o in over_before) else None,
                         "exposed_at_half_share_after_mean": round(st.mean(o2 for o, o2 in zip(over_before, over_after) if o >= 0.5), 4) if any(o >= 0.5 for o in over_before) else None,
                         "unexposed_limit_ratio_median": round(st.median(r for r, o in zip(ratios, over_before) if o < 0.5), 4) if any(o < 0.5 for o in over_before) else None}
    return res


if __name__ == "__main__":
    head = int(call("eth_blockNumber", []), 16)
    rows = collect(head)
    res = {"rpc": rpc, "head": head, "windows": WINDOWS, "blocks_per_window": NB, "txs_per_block": NT, **summarize(rows)}
    Path(out).write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))
