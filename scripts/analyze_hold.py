"""What a hold costs and what it does (2026-11-02).

Fees in a block; the bill for holding the hot accounts against the block's fees; who pays outside the protocol; how much of an
account's budget it uses, with every declaration firm and under classes; how much of the block's time the longest serial run on
one account explains; whether a higher bid buys an earlier place; a hold at several places in the block; and, on consecutive
blocks, where the price of equation (3.1) goes at several targets, with and without the hold.  Only aggregates are written.

Usage: python analyze_hold.py <sample> <out.json> [processes]
"""
import json
import statistics as st
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
BUDGET = 20_000_000
DURATION = 1_400_000
ETA = 1 / 8
TARGETS = (0.05, 0.1, 0.25, 0.5)
PLACES = (0.0, 0.25, 0.5, 0.75)
THREADS = 16


def hot_of(block, top=5):
    dec = defaultdict(int)
    for t in block["txs"]:
        for e in t["w"]:
            if not e[1]:
                dec[e[0]] += t["limit"]
    return sorted(dec, key=lambda k: -dec[k])[:top]


def bid(t, tips=False):
    return (t["prio"] + (t.get("tip", 0) if tips else 0)) / max(1, t["used"])


def counted(block, tabs):
    """Per account: compute charged with every declaration firm; and under classes, by firm declarers and soft writers only."""
    firm, cls = defaultdict(int), defaultdict(int)
    for t in block["txs"]:
        c = t.get("cost") or t["used"]
        for e in t["w"]:
            if e[1]:
                continue
            firm[e[0]] += c
            if R.q_for(t["payer"], e[0], tabs) >= 0.25 or R.written(t, e):
                cls[e[0]] += c
    return firm, cls


def place_job(job):
    pairs, raw, tabs, q_acct, hot = job
    n = len(pairs)
    pol = A.policy_txs(pairs, raw, "menu_payer", q_acct, tabs, .25, True)
    out = {}
    none = frozenset()
    bids = [bid(t) for t in raw]
    serial = defaultdict(int)
    for t in raw:
        for e in t["w"]:
            if not e[1]:
                serial[e[0]] += max(1, t["used"])
    firm_txs = A.policy_txs(pairs, raw, "firm", q_acct, tabs, None, True)
    firm_time = simulate(firm_txs, THREADS, validate_soft_reads=True, order="block").makespan
    out["serial"] = (max(serial.values(), default=0), firm_time)
    for order in ("block", "free"):
        base = simulate(pol, THREADS, validate_soft_reads=True, order=order).makespan
        for x in PLACES:
            k = int(x * n)
            head = Tx(0, DURATION, hot, none, hot)
            txs = pol[:k] + [head] + pol[k:]
            s = simulate(txs, THREADS, validate_soft_reads=True, order=order)
            assert s.serializable
            others = max(e for i, e in s.ends.items() if i != k)
            lo, hi = max(0, k - max(5, n // 20)), min(n, k + max(5, n // 20))
            local = st.median(bids[lo:hi]) if hi > lo else 0.0
            out[(order, x)] = (others, base, 5 * DURATION * local)
    return out


def main(sample, out_name, procs=1):
    blocks = R.load(sample)
    half = len(blocks) // 2
    first, rep = blocks[:half], [b for b in blocks[half:] if b["txs"]]
    tabs = R.estimate_q_payer(first)
    qhat, nobs = R.estimate_q(first)
    q_acct = {k: v for k, v in qhat.items() if nobs[k] >= 3}
    res = {"sample": sample, "blocks": len(rep)}

    # fees per block, inside and outside the protocol
    has_tip = any("tip" in t for b in rep for t in b["txs"])
    prio = [sum(t["prio"] for t in b["txs"]) for b in rep]
    fees = [sum(t["fee"] for t in b["txs"]) for b in rep]
    res["fees"] = {"priority_per_block_lamports": st.mean(prio), "fee_per_block_lamports": st.mean(fees),
                   "priority_per_block_median": st.median(prio), "tx_per_block": st.mean(len(b["txs"]) for b in rep)}
    if has_tip:
        tips = [sum(max(0, t.get("tip", 0)) for t in b["txs"]) for b in rep]
        tipped = [t for b in rep for t in b["txs"] if t.get("tip", 0) > 0]
        n = sum(len(b["txs"]) for b in rep)
        res["tips"] = {"tips_per_block_lamports": st.mean(tips), "share_of_tx": rnd(len(tipped) / n),
                       "tips_over_priority": rnd(sum(tips) / max(1, sum(prio))),
                       "tips_in_failed_tx": sum(1 for t in tipped if t["err"]),
                       "tip_share_of_payment": rnd(sum(tips) / max(1, sum(tips) + sum(prio)))}

    # prices on the hot accounts, inside the protocol and with tips
    pw = uw = pn = un = tw = 0
    for b in rep:
        hot = set(hot_of(b))
        for t in b["txs"]:
            for e in t["w"]:
                if e[1] or e[0] not in hot:
                    continue
                if R.written(t, e):
                    pw += t["prio"]
                    tw += max(0, t.get("tip", 0))
                    uw += t["used"]
                else:
                    pn += t["prio"]
                    un += t["used"]
    per_mcu_w, per_mcu_n = pw / max(1, uw) * 1e6, pn / max(1, un) * 1e6
    bill = lambda per_mcu: 5 * DURATION / 1e6 * per_mcu       # lamports for a hold of DURATION on five accounts
    res["bill"] = {"writers_lamports_per_mcu": rnd(per_mcu_w, 1), "nonwriters_lamports_per_mcu": rnd(per_mcu_n, 1),
                   "writers_with_tips_lamports_per_mcu": rnd((pw + tw) / max(1, uw) * 1e6, 1) if has_tip else None,
                   "five_at_writers_price_lamports": rnd(bill(per_mcu_w), 0), "five_at_nonwriters_price_lamports": rnd(bill(per_mcu_n), 0),
                   "one_at_nonwriters_price_lamports": rnd(bill(per_mcu_n) / 5, 0),
                   "five_at_writers_over_block_priority": rnd(bill(per_mcu_w) / max(1.0, st.mean(prio))),
                   "five_at_nonwriters_over_block_priority": rnd(bill(per_mcu_n) / max(1.0, st.mean(prio)))}

    # budget use on the hot accounts
    rows_firm, rows_cls, top_firm, top_cls = [], [], [], []
    for b in rep:
        firm, cls = counted(b, tabs)
        hot = hot_of(b)
        rows_firm += [firm[a] / BUDGET for a in hot]
        rows_cls += [cls[a] / BUDGET for a in hot]
        top_firm.append(max(firm.values(), default=0) / BUDGET)
        top_cls.append(max(cls.values(), default=0) / BUDGET)
    res["use_over_budget"] = {"pairs": len(rows_firm)}
    for name, xs, tops in (("firm", rows_firm, top_firm), ("classes", rows_cls, top_cls)):
        res["use_over_budget"][name] = {"median": rnd(st.median(xs)), "p90": rnd(A.qt(xs, .9)), "max": rnd(max(xs)),
                                        **{f"share_at_{x}": rnd(sum(v >= x for v in xs) / len(xs)) for x in TARGETS + (1.0,)},
                                        "blocks_top_median": rnd(st.median(tops)), "blocks_top_max": rnd(max(tops))}

    # does a higher bid buy an earlier place?
    deciles = defaultdict(list)
    for b in rep:
        n = len(b["txs"])
        for i, t in enumerate(b["txs"]):
            deciles[min(9, 10 * i // max(1, n))].append(bid(t))
    res["bid_by_place"] = {str(d): rnd(st.median(v), 6) for d, v in sorted(deciles.items())}

    # a hold at several places, and the longest serial run against the block's time
    hot_sample = frozenset(R_hot(first))
    jobs = [(A.base_txs(b, A.written_v3), b["txs"], tabs, q_acct, hot_sample) for b in rep]
    if procs > 1:
        with Pool(procs) as pool:
            rows = pool.map(place_job, jobs, chunksize=1)
    else:
        rows = [place_job(j) for j in jobs]
    ratios = [r["serial"][0] / max(1.0, r["serial"][1]) for r in rows]
    res["serial_over_block_time"] = {"median": rnd(st.median(ratios)), "p10": rnd(A.qt(ratios, .1)), "p90": rnd(A.qt(ratios, .9)),
                                     "share_within_10pct": rnd(sum(x >= .9 for x in ratios) / len(ratios))}
    top_q = sorted(rows, key=lambda r: -r["serial"][1])[:max(1, len(rows) // 4)]
    res["serial_over_block_time"]["slowest_quarter_median"] = rnd(st.median(r["serial"][0] / max(1.0, r["serial"][1]) for r in top_q))
    res["places"] = {}
    for order in ("block", "free"):
        res["places"][order] = {}
        for x in PLACES:
            o = sum(r[(order, x)][0] for r in rows)
            b = sum(r[(order, x)][1] for r in rows)
            lam = st.mean(r[(order, x)][2] for r in rows)
            res["places"][order][str(x)] = {"increase": rnd(o / b - 1), "bill_at_local_bid_lamports": rnd(lam, 0), "bill_over_block_priority": rnd(lam / max(1.0, st.mean(prio))),
                                            "bill_median_lamports": rnd(st.median(r[(order, x)][2] for r in rows), 0),
                                            "bill_median_over_block_priority": rnd(st.median(r[(order, x)][2] / max(1.0, p) for r, p in zip(rows, prio)))}

    # the price of equation (3.1) on consecutive blocks, in units of its floor, on the five accounts hottest over the replay
    slots = [b["slot"] for b in rep]
    consecutive = len(slots) > 1 and (slots[-1] - slots[0]) <= 2 * len(slots)
    if consecutive:
        total = defaultdict(int)
        uses = []
        for b in rep:
            firm, cls = counted(b, tabs)
            uses.append(cls)
            for a, v in cls.items():
                total[a] += v
        hottest = sorted(total, key=lambda a: -total[a])[:5]
        res["price_path"] = {}
        for tgt in TARGETS:
            target = tgt * BUDGET
            row = {"share_of_blocks_above_target": rnd(sum(u[a] > target for u in uses for a in hottest) / (len(uses) * 5))}
            for label, held in (("without_hold", 0), ("with_hold", DURATION)):
                ends, peaks, paid = [], [], []
                for a in hottest:
                    p, peak, s = 1.0, 1.0, 0.0
                    for u in uses:
                        s += p
                        p = max(1.0, p * (1 + ETA * (u[a] + held - target) / target))
                        peak = max(peak, p)
                    ends.append(p)
                    peaks.append(peak)
                    paid.append(s / len(uses))
                row[label] = {"end_median": rnd(st.median(ends)), "peak_max": rnd(max(peaks), 3), "mean_price_median": rnd(st.median(paid)), "mean_price_max": rnd(max(paid), 3)}
            res["price_path"][str(tgt)] = row
    (BASE / "results" / out_name).write_text(json.dumps(res, indent=1), encoding="utf-8")
    return res


def R_hot(blocks, top=5):
    heat = defaultdict(int)
    for b in blocks:
        for t in b["txs"]:
            for e in t["w"]:
                if not e[1]:
                    heat[e[0]] += t["limit"]
    return sorted(heat, key=lambda a: -heat[a])[:top]


if __name__ == "__main__":
    r = main(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 1)
    print(json.dumps(r, indent=1))
