"""A producer that retries under locks (2026-11-02).

A first run takes the locks of its class; a run that aborts runs again holding a lock on everything it declared, firm or
shared.  So no transaction runs more than twice, and a soft declaration that holds a lock on a retry can be charged like a firm
one.  For each sample, in free order: time and waste for each class policy, with reads under shared locks or soft, and the
share of unused soft declarations that come to hold a lock.  An occupier at the head of the block under each class.  Only
aggregates are written.

Usage: python analyze_retry.py <sample> <out.json> [threads ...]
"""
import json
import sys
from collections import defaultdict
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_paper_numbers as A  # noqa: E402
import analyze_reads as AR  # noqa: E402
import replay_solana as R  # noqa: E402

BASE = Path(__file__).resolve().parents[1]
Tx, simulate = R.Tx, R.simulate
rnd = A.rnd
THETAS = (0.05, 0.1, 0.25, 0.5)
DURATION = 1_400_000


def soft_rarely_written(txs, write_rate, cut):
    """Reads of accounts written at most `cut` times per block in the first half go soft; the rest keep their shared locks."""
    out = []
    for t in txs:
        s = frozenset(a for a in t.reads if write_rate.get(a, 0.0) <= cut)
        out.append(Tx(t.idx, t.duration, t.declared, t.writes, t.firm, t.reads - s, s))
    return out


def work(job):
    pairs, raw, tabs, q_acct, hot, threads, write_rate = job
    out = {}
    extra = {}

    def run(name, txs, retry):
        s = simulate(txs, threads, validate_soft_reads=True, order="free", retry_locks=retry)
        assert s.serializable, (name, threads)
        out[name] = (s.makespan, s.wasted, s.busy, s.reexecutions)
        return s

    firm = A.policy_txs(pairs, raw, "firm", q_acct, tabs, None, True)
    soft = A.policy_txs(pairs, raw, "soft", q_acct, tabs, None, True)
    run("firm", firm, False)
    for name, base in (("soft", soft), ("firm", firm)):
        run(name + "|retry", base, True)
        run(name + "+softread|retry", AR.soften(base), True)
    run("soft+softread", AR.soften(soft), False)
    run("soft", soft, False)
    for th in THETAS:
        m = A.policy_txs(pairs, raw, "menu_payer", q_acct, tabs, th, True)
        run(f"menu@{th}", m, False)
        s = run(f"menu@{th}|retry", m, True)
        run(f"menu@{th}+softread|retry", AR.soften(m), True)
        run(f"menu@{th}+softcold|retry", soft_rarely_written(m, write_rate, 0.0), True)
        if th == 0.25:
            unused = held = 0
            for t in m:
                k = len(t.declared - t.firm - t.writes)
                unused += k
                held += k if t.idx in s.retried else 0
            extra["unused_soft"] = unused
            extra["unused_soft_retried"] = held

    # an occupier at the head of the block, which counts only until every other transaction has committed
    none = frozenset()
    menu = A.policy_txs(pairs, raw, "menu_payer", q_acct, tabs, .25, True)
    menu_soft = AR.soften(menu)
    for label, others in (("", menu), ("softread_", menu_soft)):
        base = simulate(others, threads, validate_soft_reads=True, order="free", retry_locks=True).makespan
        for name, head in (("firm", Tx(0, DURATION, hot, none, hot)), ("read", Tx(0, DURATION, none, none, none, hot)),
                           ("softread", Tx(0, DURATION, none, none, none, none, hot)), ("soft", Tx(0, DURATION, hot, none, none))):
            s = simulate([head] + AR.shifted(others), threads, validate_soft_reads=True, order="free", retry_locks=True)
            assert s.serializable
            out[f"occ_{label}{name}"] = (max(e for i, e in s.ends.items() if i != 0), base, 0, 0)
    return out, extra


def main(sample, out_name, threads=(4, 8, 16), procs=8):
    blocks = R.load(sample)
    half = len(blocks) // 2
    tabs = R.estimate_q_payer(blocks[:half])
    qhat, nobs = R.estimate_q(blocks[:half])
    q_acct = {k: v for k, v in qhat.items() if nobs[k] >= 3}
    heat = defaultdict(int)
    wrote = defaultdict(int)
    for b in blocks[:half]:
        for t in b["txs"]:
            for e in t["w"]:
                if not e[1]:
                    heat[e[0]] += t["limit"]
                    wrote[e[0]] += int(R.written(t, e))
    write_rate = {a: v / max(1, half) for a, v in wrote.items()}
    hot = frozenset(sorted(heat, key=lambda a: -heat[a])[:5])
    rep = [b for b in blocks[half:] if b["txs"]]
    res = {"sample": sample, "blocks": len(rep)}
    with Pool(procs) as pool:
        for n in threads:
            jobs = [(A.base_txs(b, A.written_v3), b["txs"], tabs, q_acct, hot, n, write_rate) for b in rep]
            rows = pool.map(work, jobs, chunksize=1)
            agg = defaultdict(lambda: [0.0, 0.0, 0.0, 0])
            ex = defaultdict(int)
            for r, e in rows:
                for k, v in r.items():
                    for i in range(4):
                        agg[k][i] += v[i]
                for k, v in e.items():
                    ex[k] += v
            row = {}
            for name, (m, w, b, x) in agg.items():
                if name.startswith("occ_"):
                    row[name] = {"increase": rnd(m / w - 1)}
                else:
                    row[name] = {"over_firm": rnd(m / agg["firm"][0]), "wasted_share": rnd(w / max(1.0, b)), "reruns": int(x)}
            row["share_unused_soft_retried"] = rnd(ex["unused_soft_retried"] / max(1, ex["unused_soft"]))
            res[f"threads={n}"] = row
    (BASE / "results" / out_name).write_text(json.dumps(res, indent=1), encoding="utf-8")
    return res


if __name__ == "__main__":
    r = main(sys.argv[1], sys.argv[2], tuple(int(x) for x in sys.argv[3:]) or (4, 8, 16))
    for k, row in r.items():
        if not k.startswith("threads"):
            continue
        print(k)
        for name, v in row.items():
            print("  ", name, v)
