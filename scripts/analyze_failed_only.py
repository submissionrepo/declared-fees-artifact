"""How much of what classes save comes from transactions that fail, on a sample or a minute (2026-11-02).

The menu at theta = 0.25 is applied to all transactions, only to those that fail and only to those that succeed, the others
staying firm, at 16 threads in each order.  Only aggregates are written.

Usage: python analyze_failed_only.py <sample> <out.json>
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_extensions as E  # noqa: E402
import analyze_paper_numbers as A  # noqa: E402
import replay_solana as R  # noqa: E402

BASE = Path(__file__).resolve().parents[1]


def main(sample, out):
    blocks = R.load(sample)
    half = len(blocks) // 2
    tabs = R.estimate_q_payer(blocks[:half])
    qhat, nobs = R.estimate_q(blocks[:half])
    q_acct = {k: v for k, v in qhat.items() if nobs[k] >= 3}
    data = [(A.base_txs(b, A.written_v3), b["txs"]) for b in blocks[half:]]
    res = {"sample": sample, "blocks": len(data)}
    runs = {"firm": lambda p, r: A.policy_txs(p, r, "firm", q_acct, tabs, None, True),
            "menu": lambda p, r: A.policy_txs(p, r, "menu_payer", q_acct, tabs, .25, True),
            "menu_failed": lambda p, r: E.extra_policy(p, r, "menu_failed", tabs, .25, True),
            "menu_ok": lambda p, r: E.extra_policy(p, r, "menu_ok", tabs, .25, True)}
    for order in ("block", "free"):
        total = {}
        for name, make in runs.items():
            total[name] = 0
            for pairs, raw in data:
                s = R.simulate(make(pairs, raw), 16, validate_soft_reads=True, order=order)
                assert s.serializable
                total[name] += s.makespan
        res[order] = {name: A.rnd(v / total["firm"]) for name, v in total.items()}
    (BASE / "results" / out).write_text(json.dumps(res, indent=1), encoding="utf-8")
    return res


if __name__ == "__main__":
    print(json.dumps(main(sys.argv[1], sys.argv[2]), indent=1))
