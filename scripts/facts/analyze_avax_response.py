"""Did senders on Avalanche respond to the charge on unused gas?  Aggregates from the reduced rows of avax_before_after.py.

A call is a sender, target and function seen at least MIN_USES times in each window, or a target and function across
senders.  It is exposed if it used at most half its limit in at least half of its uses before the change, which is
when lowering the limit saves money.  We report the limit after over the limit before by exposure, with a bootstrap
over calls, how many calls cut or raised the limit, and failures before and after, among them failures at the limit.
After the change a receipt records the charged amount, so failures at the limit are comparable and gas used is not.

Usage: python analyze_avax_response.py <out.json>
"""
import json
import random
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

DATA = Path(__file__).resolve().parents[2] / "data" / "avax_before_after.jsonl"
MIN_USES = 3
rows = [json.loads(line) for line in open(DATA, encoding="utf-8")]


def at_half(r):
    return r["gas"] * 2 <= r["limit"] + 1


def boot(xs, draws=4000):
    if not xs:
        return None
    rng = random.Random(0)
    meds = sorted(st.median(rng.choices(xs, k=len(xs))) for _ in range(draws))
    return [round(meds[int(0.025 * draws)], 4), round(meds[int(0.975 * draws)], 4)]


def failures(rs):
    return {"txs": len(rs), "failed": sum(not r["ok"] for r in rs), "failed_at_limit": sum((not r["ok"]) and r["gas"] >= r["limit"] for r in rs)}


def study(key, min_uses=MIN_USES):
    groups = defaultdict(lambda: {"before": [], "after": []})
    for r in rows:
        groups[key(r)][r["w"]].append(r)
    pairs = [(g["before"], g["after"]) for g in groups.values() if len(g["before"]) >= min_uses and len(g["after"]) >= min_uses]
    res = {"calls": len(pairs)}
    for name, test in (("exposed", lambda share: share >= 0.5), ("unexposed", lambda share: share < 0.5)):
        sel = [(b, a) for b, a in pairs if test(sum(at_half(x) for x in b) / len(b))]
        ratios = [st.median(x["limit"] for x in a) / st.median(x["limit"] for x in b) for b, a in sel]
        res[name] = {"calls": len(sel), "limit_ratio_median": round(st.median(ratios), 4) if ratios else None, "limit_ratio_ci95": boot(ratios),
                     "cut": sum(x < 0.99 for x in ratios), "raised": sum(x > 1.01 for x in ratios), "same": sum(0.99 <= x <= 1.01 for x in ratios),
                     "before": failures([x for b, _ in sel for x in b]), "after": failures([x for _, a in sel for x in a])}
    return res


def main(out):
    res = {"all": {w: failures([r for r in rows if r["w"] == w]) for w in ("before", "after")},
           "sender_target_function": study(lambda r: (r["from"], r["to"], r["sel"])),
           "sender_target_function_5_uses": study(lambda r: (r["from"], r["to"], r["sel"]), 5),
           "target_function": study(lambda r: (r["to"], r["sel"])),
           "target_function_5_uses": study(lambda r: (r["to"], r["sel"]), 5)}
    Path(out).write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
