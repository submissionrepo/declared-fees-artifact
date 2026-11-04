"""The busiest minutes a public node remembers, for choosing windows of consecutive blocks.

A node keeps one performance record per minute.  We rank the minutes by non-vote transactions per second and keep the
top ones at least MIN_GAP slots apart.  Each window is the 160 slots that end at the minute's recorded slot.  With
up_to_slot, only the records up to that slot count, which repeats a selection made earlier while the node still has them.

Usage: python busy_minutes.py <rpc-url> <out.json> [n_windows] [up_to_slot]
"""
import json
import statistics as st
import sys
import urllib.request
from pathlib import Path

rpc, out = sys.argv[1], sys.argv[2]
N = int(sys.argv[3]) if len(sys.argv) > 3 else 3
UP_TO = int(sys.argv[4]) if len(sys.argv) > 4 else None
MIN_GAP = 2000
WINDOW = 160

body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "getRecentPerformanceSamples", "params": [720]}).encode()
req = urllib.request.Request(rpc, data=body, headers={"content-type": "application/json", "user-agent": "research-probe/0.1"})
with urllib.request.urlopen(req, timeout=60) as r:
    samples = json.load(r)["result"]
rows = [{"slot": s["slot"], "tps": round(s["numNonVoteTransactions"] / s["samplePeriodSecs"], 1)} for s in samples
        if UP_TO is None or s["slot"] <= UP_TO]
tps = [r["tps"] for r in rows]
chosen = []
for row in sorted(rows, key=lambda r: -r["tps"]):
    if all(abs(row["slot"] - c["slot"]) >= MIN_GAP for c in chosen):
        chosen.append(row)
    if len(chosen) == N:
        break
res = {"rpc": rpc, "up_to_slot": UP_TO, "records": len(rows), "slot_first": min(r["slot"] for r in rows), "slot_last": max(r["slot"] for r in rows),
       "tps_median": st.median(tps), "tps_p90": sorted(tps)[int(0.9 * len(tps))], "tps_max": max(tps),
       "min_gap_slots": MIN_GAP, "window_slots": WINDOW, "windows": chosen}
Path(out).write_text(json.dumps({**res, "rows": rows}, indent=1), encoding="utf-8")
print(json.dumps(res, indent=1))
