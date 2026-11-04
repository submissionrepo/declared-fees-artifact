"""Every analysis of a minute has to rest on all the blocks of its sample (2026-11-02).  Prints what does not, by comparing block counts.

Usage: python check_minutes.py
"""
import gzip
import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
RES = BASE / "results"
names = json.loads((RES / "facts_minutes.json").read_text(encoding="utf-8"))
plan = {w["name"]: w for w in json.loads((RES / "facts_windows_plan.json").read_text(encoding="utf-8"))}


def lines(part):
    path = BASE / "data" / part
    if not path.exists():
        return None
    with (gzip.open(path, "rt", encoding="utf-8") if part.endswith(".gz") else open(path, encoding="utf-8")) as fh:
        return sum(1 for _ in fh)


for tag, sample in names.items():
    counts = [lines(p) for p in sample.split("+")]
    if None in counts:
        print(tag, sample, "not yet fetched")
        continue
    total = sum(counts)
    expected = sum(plan[p]["last"] - plan[p]["first"] + 1 for p in sample.split("+") if p in plan)
    row = []
    pn = RES / f"paper_numbers_{tag}.json"
    if pn.exists():
        row.append(("numbers", json.loads(pn.read_text(encoding="utf-8"))["meta"]["blocks"]))
    halves = []
    for name in ("reads", "hold", "paper_extensions", "soft_last", "failed_only"):
        p = RES / f"{name}_{tag}.json"
        if p.exists():
            halves.append((name, json.loads(p.read_text(encoding="utf-8"))["blocks"]))
    stale = [n for n, b in row if b != total] + [n for n, b in halves if abs(b - (total - total // 2)) > 1]
    print(tag, "blocks", total, "of plan part", expected, "numbers", row, "replayed", halves, "STALE" if stale else "ok", stale)
