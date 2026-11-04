"""Read-only declarations as a second placement (2026-11-02).

A firm read holds a shared lock, so writers wait for it.  A soft read holds nothing and is checked at commit; a write that
commits during its run makes it run again, and with every declared account watched the runtime need not see what was read.
For each sample: time and waste with today's shared locks against soft reads, under every declaration firm, classes from
history, every declaration soft and foresight; the same at a validator told what was written; and an occupier that holds the
hot accounts under each read class.  Only aggregates are written.

Usage: python analyze_reads.py <sample> <out.json> [threads ...]
"""
import json
import sys
from collections import defaultdict
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_paper_numbers as A  # noqa: E402
import replay_solana as R  # noqa: E402

BASE = Path(__file__).resolve().parents[1]
Tx, simulate = R.Tx, R.simulate
rnd = A.rnd
DURATION = 1_400_000
LIGHT = A.LIGHT


def soften(txs):
    return [Tx(t.idx, t.duration, t.declared, t.writes, t.firm, frozenset(), t.reads | t.soft_reads) for t in txs]


def told(pairs):
    """What a validator told the write sets can run: locks on what was written, soft reads of the rest."""
    return [Tx(tx.idx, tx.duration, tx.writes | signers, tx.writes, tx.writes | signers, frozenset(), (tx.reads | (tx.declared - tx.writes - signers)) - tx.writes - signers)
            for tx, signers in pairs]


def shifted(txs):
    return [Tx(t.idx + 1, t.duration, t.declared, t.writes, t.firm, t.reads, t.soft_reads) for t in txs]


def work(job):
    pairs, raw, tabs, q_acct, hot, threads = job
    out = {}

    def run(name, txs, order, **kw):
        s = simulate(txs, threads, validate_soft_reads=True, order=order, **kw)
        assert s.serializable, (name, order, threads)
        out[(name, order)] = (s.makespan, s.wasted, s.busy, s.reexecutions)
        return s

    pol = {k: A.policy_txs(pairs, raw, n, q_acct, tabs, th, True) for k, n, th in (("firm", "firm", None), ("menu", "menu_payer", .25), ("soft", "soft", None), ("oracle", "oracle", None))}
    perfect = [Tx(tx.idx, tx.duration, tx.declared, tx.writes, tx.writes | signers, tx.reads) for tx, signers in pairs]
    for order in ("block", "free"):
        for name, txs in pol.items():
            run(name, txs, order)
        run("menu+softread", soften(pol["menu"]), order)
        if not LIGHT:
            run("perfect", perfect, order)
            run("firm+softread", soften(pol["firm"]), order)
            run("soft+softread", soften(pol["soft"]), order)
            run("perfect+softread", soften(perfect), order)
    if not LIGHT:
        run("menu+softread,noversions", soften(pol["menu"]), "block", versions=False)
    run("told", told(pairs), "block", told=True)

    # an occupier at the head of the block that declares the hot accounts and writes none of them
    none = frozenset()
    heads = {"firm": Tx(0, DURATION, hot, none, hot), "read": Tx(0, DURATION, none, none, none, hot), "softread": Tx(0, DURATION, none, none, none, none, hot), "soft": Tx(0, DURATION, hot, none, none)}
    for order in ("block", "free"):
        base = simulate(pol["menu"], threads, validate_soft_reads=True, order=order).makespan
        for name, head in heads.items():
            s = simulate([head] + shifted(pol["menu"]), threads, validate_soft_reads=True, order=order)
            assert s.serializable
            out[("occ_" + name, order)] = (max(e for i, e in s.ends.items() if i != 0), base, 0, 0)
    told_txs = told(pairs)
    base = simulate(told_txs, threads, validate_soft_reads=True, order="block", told=True).makespan
    for name, head in (("firm", heads["firm"]), ("softread", heads["softread"])):
        s = simulate([head] + shifted(told_txs), threads, validate_soft_reads=True, order="block", told=True)
        assert s.serializable
        out[("occ_told_" + name, "block")] = (max(e for i, e in s.ends.items() if i != 0), base, 0, 0)
    return out


def main(sample, out_name, threads=(4, 8, 16), procs=8):
    if LIGHT:
        procs = 1
    blocks = R.load(sample)
    half = len(blocks) // 2
    tabs = R.estimate_q_payer(blocks[:half])
    qhat, nobs = R.estimate_q(blocks[:half])
    q_acct = {k: v for k, v in qhat.items() if nobs[k] >= 3}
    heat = defaultdict(int)
    for b in blocks[:half]:
        for t in b["txs"]:
            for e in t["w"]:
                if not e[1]:
                    heat[e[0]] += t["limit"]
    hot = frozenset(sorted(heat, key=lambda a: -heat[a])[:5])
    rep = [b for b in blocks[half:] if b["txs"]]
    res = {"sample": sample, "blocks": len(rep)}
    pool = Pool(procs) if procs > 1 else None
    try:
        for n in threads:
            jobs = [(A.base_txs(b, A.written_v3), b["txs"], tabs, q_acct, hot, n) for b in rep]
            rows = pool.map(work, jobs, chunksize=1) if pool else [work(j) for j in jobs]
            agg = defaultdict(lambda: [0.0, 0.0, 0.0, 0])
            slowest = defaultdict(float)
            for r in rows:
                for k, v in r.items():
                    slowest[k] = max(slowest[k], v[0])
                    for i in range(4):
                        agg[k][i] += v[i]
            row = {"block": {}, "free": {}}
            for (name, order), (m, w, b, x) in agg.items():
                if name.startswith("occ_"):
                    row[order][name] = {"increase": rnd(m / w - 1)}
                else:
                    row[order][name] = {"over_firm": rnd(m / agg[("firm", order)][0]), "wasted_share": rnd(w / max(1.0, b)), "reruns": int(x),
                                        "max_time": slowest[(name, order)], "mean_time": m / len(rows)}
            res[f"threads={n}"] = row
    finally:
        if pool:
            pool.close()
    (BASE / "results" / out_name).write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], tuple(int(x) for x in sys.argv[3:]) or (4, 8, 16))
