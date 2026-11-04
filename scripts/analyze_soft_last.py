"""A producer that bears reruns has a reason to place soft transactions last (2026-11-02).

Classes come from public history as in the replay.  Every transaction with a soft declaration moves behind every
transaction without one, keeping the recorded order within each group, and we replay that order against the recorded one.
Outcomes stay at their recorded values, which a real change of order could change.  We also report who moves: transactions
that succeeded, and those that wrote an account they declared soft, whose use may depend on running early.  And how often the
block's time comes near the account budget, the only case in which reruns cost the producer anything.  Only aggregates are
written.

Usage: python analyze_soft_last.py <sample.jsonl> <out.json>
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import replay_solana as R  # noqa: E402

BASE = Path(__file__).resolve().parents[1]
BUDGET = 20_000_000
LIGHT = bool(os.environ.get("DF_LIGHT"))
THREADS = (4, 16) if LIGHT else (4, 8, 16)
THETAS = (0.25,) if LIGHT else (0.25, 0.75)


def build(blocks, tabs, theta):
    """For each block: the transactions with their classes, the flag for a soft declaration, and the raw record."""
    out = []
    for b in blocks:
        rows = []
        for t in b["txs"]:
            declared = frozenset(e[0] for e in t["w"])
            signers = frozenset(e[0] for e in t["w"] if e[1])
            writes = frozenset(e[0] for e in t["w"] if R.written(t, e))
            firm = signers | frozenset(a for a in declared - signers if R.q_for(t["payer"], a, tabs) >= theta)
            rows.append((max(1, t["used"]), declared, writes, firm, frozenset(t.get("ro", ())), bool(declared - firm), t))
        out.append(rows)
    return out


def run(rows, n, order, soft_last):
    seq = sorted(rows, key=lambda r: r[5]) if soft_last else rows   # sorted is stable, so the recorded order stays within each group
    txs = [R.Tx(i, r[0], r[1], r[2], r[3], r[4]) for i, r in enumerate(seq)]
    s = R.simulate(txs, n, validate_soft_reads=True, order=order)
    assert s.serializable
    return s


def main(sample, out):
    blocks = R.load(sample)
    half = len(blocks) // 2
    tabs = R.estimate_q_payer(blocks[:half])
    rep = blocks[half:]
    res = {"sample": sample, "blocks": len(rep)}
    all_firm = [[(r[0], r[1], r[2], r[1], r[4], False, r[6]) for r in rows] for rows in build(rep, tabs, 0.0)]
    for theta in THETAS:
        data = build(rep, tabs, theta)
        ok = [r for rows in data for r in rows if not r[6]["err"]]
        prio_ok = sum(r[6]["prio"] for r in ok)
        moved = [r for r in ok if r[5]]
        used_soft = [r for r in ok if (r[1] - r[3]) & r[2]]
        row = {"moved_share_of_all": round(sum(r[5] for rows in data for r in rows) / sum(len(rows) for rows in data), 4),
               "moved_share_of_successful": round(len(moved) / len(ok), 4),
               "moved_share_of_successful_priority_fees": round(sum(r[6]["prio"] for r in moved) / max(1, prio_ok), 4),
               "used_soft_share_of_successful": round(len(used_soft) / len(ok), 4),
               "used_soft_share_of_successful_priority_fees": round(sum(r[6]["prio"] for r in used_soft) / max(1, prio_ok), 4)}
        for order in ("free", "block"):
            row[order] = {}
            for n in THREADS:
                firm_times = [run(rows, n, order, False).makespan for rows in all_firm]
                rank = [run(rows, n, order, False) for rows in data]
                last = [run(rows, n, order, True) for rows in data]
                firm = sum(firm_times)
                row[order][f"threads={n}"] = {
                    "rank_over_firm": round(sum(s.makespan for s in rank) / firm, 4),
                    "last_over_firm": round(sum(s.makespan for s in last) / firm, 4),
                    "rank_wasted": round(sum(s.wasted for s in rank) / max(1.0, sum(s.busy for s in rank)), 4),
                    "last_wasted": round(sum(s.wasted for s in last) / max(1.0, sum(s.busy for s in last)), 4),
                    "firm_blocks_over_half_budget": sum(t >= BUDGET / 2 for t in firm_times),
                    "firm_blocks_over_budget": sum(t >= BUDGET for t in firm_times),
                    "rank_blocks_over_half_budget": sum(s.makespan >= BUDGET / 2 for s in rank),
                    "rank_blocks_over_budget": sum(s.makespan >= BUDGET for s in rank),
                    "firm_mean_of_budget": round(sum(firm_times) / len(firm_times) / BUDGET, 4)}
        res[f"theta={theta}"] = row
    (BASE / "results" / out).write_text(json.dumps(res, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
