"""Solana numbers for the paper, one output per sample (2026-11-01).

Same usage proxy as replay_solana.py (v3), plus a stricter proxy that gives a lower bound: a token
account whose balance did not change counts as unwritten only if no inner instruction received it (a
multi-hop route can leave an intermediate account's balance unchanged after writing it twice).  The
replay holds read-only declarations under shared locks and reports two ways of treating a soft
declaration that was not written: validated as a read ("reads"), or ignored ("writes"); and two orders:
conflicting transactions commit in block order ("block"), or the block order is only a priority ("free").
Signer accounts stay firm under every policy, since the fee payer's debit is a known write.  Ratios are
totals over the replayed blocks.  Only aggregates
are written; identities stay in data/.

Usage: python analyze_paper_numbers.py <sample.jsonl> <out.json> [--no-replay]
"""
import json
import os
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import replay_solana as R  # noqa: E402

BASE = Path(__file__).resolve().parents[1]
LIMIT = 20_000_000          # per-account limit at the 200 ms slot parameters in force for both samples
written_v3 = R.written
LIGHT = bool(os.environ.get("DF_LIGHT"))    # whole minutes of blocks: only what the paper reports for them
THREADS = (4, 16) if LIGHT else (4, 8, 16, 32)
Tx, simulate = R.Tx, R.simulate


def written_strict(t, e):
    signer, tok, ch = e[1], e[2], e[3]
    if signer:
        return True
    if t["err"]:
        return False
    if tok:
        return bool(ch) or bool(e[4])
    return not e[5]


def qt(xs, p):
    if not xs:
        return None
    xs = sorted(xs)
    k = p * (len(xs) - 1)
    lo = int(k)
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def rnd(x, d=4):
    return None if x is None else round(x, d)


def meta(blocks):
    txs = [t for b in blocks for t in b["txs"]]
    times = [b["t"] for b in blocks if b.get("t")]
    return {"blocks": len(blocks), "transactions": len(txs), "t_min": min(times), "t_max": max(times),
            "hours": rnd((max(times) - min(times)) / 3600, 1),
            "slot_min": blocks[0]["slot"], "slot_max": blocks[-1]["slot"],
            "share_v1": rnd(sum(t["v"] == 1 for t in txs) / len(txs)),
            "share_failed": rnd(sum(t["err"] for t in txs) / len(txs))}


def declarations(blocks):
    """Declared writable non-signer accounts: who did not write them, under each proxy."""
    tot = failed = tok_unch = tok_unch_noinner = router = 0
    heat = defaultdict(int)
    for b in blocks:
        for t in b["txs"]:
            for e in t["w"]:
                if not e[1]:
                    heat[e[0]] += 1
    tiers = {"1": (1, 1), "2-9": (2, 9), "10-99": (10, 99), "100+": (100, 10 ** 12)}
    by = {k: [0, 0, 0] for k in tiers}
    for b in blocks:
        for t in b["txs"]:
            for e in t["w"]:
                if e[1]:
                    continue
                tot += 1
                if t["err"]:
                    failed += 1
                elif e[2] and not e[3]:
                    tok_unch += 1
                    tok_unch_noinner += int(not e[4])
                elif (not e[2]) and e[5]:
                    router += 1
                for name, (lo, hi) in tiers.items():
                    if lo <= heat[e[0]] <= hi:
                        by[name][0] += 1
                        by[name][1] += int(not written_v3(t, e))
                        by[name][2] += int(not written_strict(t, e))
    nw = failed + tok_unch + router
    nws = failed + tok_unch_noinner + router
    return {"writable_nonsigner": tot, "in_failed": failed, "token_unchanged": tok_unch,
            "share_not_written_in_successful": rnd((tok_unch + router) / max(1, tot - failed)),
            "token_unchanged_no_inner": tok_unch_noinner, "router_leg": router,
            "share_not_written_v3": rnd(nw / tot), "share_not_written_strict": rnd(nws / tot),
            "share_failed": rnd(failed / tot), "share_token_unchanged": rnd(tok_unch / tot),
            "share_router": rnd(router / tot),
            "by_heat": {k: {"n": v[0], "share_v3": rnd(v[1] / max(1, v[0])), "share_strict": rnd(v[2] / max(1, v[0]))}
                        for k, v in by.items()}}


def hot_accounts(blocks, top=5):
    """Top accounts per block by declared CU: budget use and who occupies it."""
    rows = []
    for b in blocks:
        dec = defaultdict(int)
        used = defaultdict(int)
        nw = defaultdict(int)
        nws = defaultdict(int)
        dec_nw = defaultdict(int)
        prio_w = defaultdict(int)
        used_w = defaultdict(int)
        prio_nw = defaultdict(int)
        used_nw = defaultdict(int)
        for t in b["txs"]:
            for e in t["w"]:
                if e[1]:
                    continue
                a = e[0]
                cost = t.get("cost") or t["used"]
                dec[a] += t["limit"]
                used[a] += cost
                if not written_v3(t, e):
                    nw[a] += cost
                    dec_nw[a] += t["limit"]
                    prio_nw[a] += t["prio"]
                    used_nw[a] += t["used"]
                else:
                    prio_w[a] += t["prio"]
                    used_w[a] += t["used"]
                if not written_strict(t, e):
                    nws[a] += cost
        for a in sorted(dec, key=lambda k: -dec[k])[:top]:
            if used[a] == 0:
                continue
            rows.append({"dec": dec[a], "used": used[a], "nw": nw[a], "nws": nws[a], "dec_nw": dec_nw[a],
                         "pw": prio_w[a], "uw": used_w[a], "pn": prio_nw[a], "un": used_nw[a]})
    shares = [r["nw"] / r["used"] for r in rows]
    shares_s = [r["nws"] / r["used"] for r in rows]
    dshares = [r["dec_nw"] / max(1, r["dec"]) for r in rows]
    dlim = [r["dec"] / LIMIT for r in rows]
    ulim = [r["used"] / LIMIT for r in rows]
    pw, uw = sum(r["pw"] for r in rows), sum(r["uw"] for r in rows)
    pn, un = sum(r["pn"] for r in rows), sum(r["un"] for r in rows)
    return {"rows": len(rows),
            "nonwriter_share_p25": rnd(qt(shares, .25)), "nonwriter_share_p50": rnd(qt(shares, .5)),
            "nonwriter_share_p75": rnd(qt(shares, .75)), "nonwriter_share_mean": rnd(st.mean(shares)),
            "nonwriter_share_strict_p50": rnd(qt(shares_s, .5)), "nonwriter_share_strict_mean": rnd(st.mean(shares_s)),
            "declared_nonwriter_share_p50": rnd(qt(dshares, .5)),
            "declared_over_limit_p50": rnd(qt(dlim, .5)), "declared_over_limit_p90": rnd(qt(dlim, .9)),
            "declared_over_limit_max": rnd(max(dlim)), "rows_declared_half_limit": sum(x >= .5 for x in dlim),
            "rows_declared_full_limit": sum(x >= 1 for x in dlim),
            "used_over_limit_p50": rnd(qt(ulim, .5)), "used_over_limit_p90": rnd(qt(ulim, .9)),
            "used_over_limit_max": rnd(max(ulim)), "rows_used_half_limit": sum(x >= .5 for x in ulim),
            "used_over_declared_p50": rnd(qt([r["used"] / max(1, r["dec"]) for r in rows], .5)),
            "lamports_per_mcu_writers": rnd(pw / max(1, uw) * 1e6, 1), "lamports_per_mcu_nonwriters": rnd(pn / max(1, un) * 1e6, 1),
            "nonwriter_cdf": [rnd(qt(shares, i / 20)) for i in range(21)],
            "shares_sorted": [rnd(x, 3) for x in sorted(shares)]}


def senders(blocks):
    """Failure concentration and the calibration of use probabilities by sender and account."""
    fails = defaultdict(int)
    txs = defaultdict(int)
    for b in blocks:
        for t in b["txs"]:
            txs[t["payer"]] += 1
            fails[t["payer"]] += t["err"]
    total = sum(fails.values())
    order = sorted(fails, key=lambda k: -fails[k])
    conc = {}
    fw = defaultdict(int)
    for b in blocks:
        for t in b["txs"]:
            if t["err"]:
                fw[t["payer"]] += sum(1 for e in t["w"] if not e[1])
    for n in (1, 10, 100):
        top = order[:n]
        conc[str(n)] = {"share_of_failures": rnd(sum(fails[k] for k in top) / total),
                        "own_failure_rate": rnd(sum(fails[k] for k in top) / sum(txs[k] for k in top)),
                        "share_of_failed_writable_declarations": rnd(sum(fw[k] for k in top) / max(1, sum(fw.values())))}
    half = len(blocks) // 2
    tabs = R.estimate_q_payer(blocks[:half])
    bins = defaultdict(lambda: [0, 0.0, 0.0])
    brier = base = 0.0
    n = 0
    uses = []
    for b in blocks[half:]:
        for t in b["txs"]:
            for e in t["w"]:
                if e[1]:
                    continue
                u = int(R.written(t, e))
                uses.append(u)
    rate = sum(uses) / max(1, len(uses))
    for b in blocks[half:]:
        for t in b["txs"]:
            for e in t["w"]:
                if e[1]:
                    continue
                u = int(R.written(t, e))
                qh = R.q_for(t["payer"], e[0], tabs)
                brier += (qh - u) ** 2
                base += (rate - u) ** 2
                n += 1
                i = min(9, int(qh * 10))
                bins[i][0] += 1
                bins[i][1] += qh
                bins[i][2] += u
    hist = {f"{i / 10:.1f}": {"n": bins[i][0], "mean_estimate": rnd(bins[i][1] / max(1, bins[i][0])),
                              "realized": rnd(bins[i][2] / max(1, bins[i][0]))} for i in sorted(bins)}
    return {"senders": len(txs), "failed_senders": sum(v > 0 for v in fails.values()), "failures": total,
            "concentration": conc, "holdout_declarations": n, "brier": rnd(brier / max(1, n)),
            "brier_constant": rnd(base / max(1, n)), "base_rate_used": rnd(rate), "calibration": hist}


def light_version(blocks, thresholds=(0.25, 0.5, 0.75), top=5):
    """Budget accounting only: a soft declarer is charged to the account only if it wrote it.
    Classes come from the first half of the sample; the rows are the second half's hot accounts."""
    half = len(blocks) // 2
    tabs = R.estimate_q_payer(blocks[:half])
    out = {}
    for thr in thresholds:
        cur_total = new_total = dec_total = dec_firm_total = wrongly_soft = written_total = 0
        ratios = []
        for b in blocks[half:]:
            dec, cur, new, dfirm = defaultdict(int), defaultdict(int), defaultdict(int), defaultdict(int)
            wsoft, wtot = defaultdict(int), defaultdict(int)
            for t in b["txs"]:
                for e in t["w"]:
                    if e[1]:
                        continue
                    a = e[0]
                    cost = t.get("cost") or t["used"]
                    dec[a] += t["limit"]
                    cur[a] += cost
                    firm = R.q_for(t["payer"], a, tabs) >= thr
                    wrote = R.written(t, e)
                    if firm:
                        dfirm[a] += t["limit"]
                    if firm or wrote:
                        new[a] += cost
                    if wrote:
                        wtot[a] += 1
                        wsoft[a] += int(not firm)
            for a in sorted(dec, key=lambda k: -dec[k])[:top]:
                if cur[a] == 0:
                    continue
                cur_total += cur[a]
                new_total += new[a]
                dec_total += dec[a]
                dec_firm_total += dfirm[a]
                wrongly_soft += wsoft[a]
                written_total += wtot[a]
                ratios.append(1 - new[a] / cur[a])
        out[str(thr)] = {"rows": len(ratios), "freed_share_aggregate": rnd(1 - new_total / max(1, cur_total)),
                         "freed_share_p50": rnd(qt(ratios, .5)),
                         "freed_declared_share_aggregate": rnd(1 - dec_firm_total / max(1, dec_total)),
                         "share_of_writes_declared_soft": rnd(wrongly_soft / max(1, written_total))}
    return out


def use_histogram(blocks):
    """Distribution of estimated use probability, weighted by declarations, sender x account pairs seen 3+ times."""
    npa, wpa = defaultdict(int), defaultdict(int)
    for b in blocks:
        for t in b["txs"]:
            for e in t["w"]:
                if e[1]:
                    continue
                npa[(t["payer"], e[0])] += 1
                wpa[(t["payer"], e[0])] += int(R.written(t, e))
    bins = [0] * 11
    tot = 0
    for k, n in npa.items():
        if n < 3:
            continue
        q = wpa[k] / n
        i = 10 if q == 1 else (0 if q == 0 else 1 + min(8, int(q * 9)))
        bins[i] += n
        tot += n
    return {"declarations_in_pairs_seen_3plus": tot,
            "share_q0": rnd(bins[0] / max(1, tot)), "share_q1": rnd(bins[10] / max(1, tot)),
            "share_between": rnd(sum(bins[1:10]) / max(1, tot))}


def placement_cost(blocks, thresholds=(0.25, 0.5, 0.75)):
    """Realized placement cost on the second half, in units of the cost of an unused lock per unit of
    compute.  Firm and unwritten costs t; soft and written costs k t with k = (1 - theta) / theta, the
    premium that makes theta the threshold.  Classes come from the first half."""
    half = len(blocks) // 2
    tabs = R.estimate_q_payer(blocks[:half])
    out = {}
    for thr in thresholds:
        k = (1 - thr) / thr
        firm = soft = menu = oracle = 0.0
        for b in blocks[half:]:
            for t in b["txs"]:
                dur = max(1, t["used"])
                for e in t["w"]:
                    if e[1]:
                        continue
                    wrote = R.written(t, e)
                    firm += 0 if wrote else dur
                    soft += k * dur if wrote else 0
                    is_firm = R.q_for(t["payer"], e[0], tabs) >= thr
                    menu += (0 if wrote else dur) if is_firm else (k * dur if wrote else 0)
        out[str(thr)] = {"k_over_cprime": rnd(k), "menu_over_firm": rnd(menu / firm), "menu_over_soft": rnd(menu / soft),
                         "soft_over_firm": rnd(soft / firm)}
    return out


def incidence(blocks, thr=0.25):
    """Who would pay the menu's charges on the second half, with behavior fixed.  Charges are in units of
    the price: t per unwritten firm declaration, k t per written soft declaration (k from thr)."""
    half = len(blocks) // 2
    tabs = R.estimate_q_payer(blocks[:half])
    k = (1 - thr) / thr
    by_sender = defaultdict(float)
    fails = defaultdict(int)
    txs = defaultdict(int)
    tx_charge = []
    total_failed = total_ok = usage = usage_signers = 0.0
    for b in blocks[half:]:
        for t in b["txs"]:
            dur = max(1, t["used"])
            c = 0.0
            for e in t["w"]:
                if e[1]:
                    usage_signers += dur
                    continue
                wrote = R.written(t, e)
                usage += dur if wrote else 0
                if R.q_for(t["payer"], e[0], tabs) >= thr:
                    c += 0 if wrote else dur
                else:
                    c += k * dur if wrote else 0
            by_sender[t["payer"]] += c
            fails[t["payer"]] += t["err"]
            txs[t["payer"]] += 1
            tx_charge.append((c, dur, t["err"]))
            if t["err"]:
                total_failed += c
            else:
                total_ok += c
    total = sum(by_sender.values())
    order = sorted(by_sender, key=lambda a: -by_sender[a])
    ok = [c / d for c, d, e in tx_charge if not e]
    return {"transactions": len(tx_charge), "share_charge_failed_tx": rnd(total_failed / max(1, total)),
            "share_failed_tx": rnd(sum(e for _, _, e in tx_charge) / len(tx_charge)),
            "share_top10_senders": rnd(sum(by_sender[a] for a in order[:10]) / max(1, total)),
            "share_top100_senders": rnd(sum(by_sender[a] for a in order[:100]) / max(1, total)),
            "share_ok_tx_no_charge": rnd(sum(x == 0 for x in ok) / max(1, len(ok))),
            "ok_charge_per_compute_p50": rnd(qt(ok, .5)), "ok_charge_per_compute_p90": rnd(qt(ok, .9)),
            "senders": len(by_sender), "charges_over_usage_fees": rnd(total / max(1, usage)),
            "charges_over_usage_fees_with_signers": rnd(total / max(1, usage + usage_signers))}


def occupier(blocks, order, sizes=(1, 5, 20), threads=16, thr=0.25, duration=1_400_000, validate=True):
    """One transaction at the head of each replayed block that declares the sample's n hottest accounts
    (by declared compute in the first half), runs for `duration`, and writes none of them.  It holds them firm;
    under "menu_soft" and "soft" it declares them soft and holds no lock; under "menu_read" it declares them
    read-only and holds a shared lock."""
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
    ranked = sorted(heat, key=lambda a: -heat[a])
    out = {}
    for n in sizes:
        hot = frozenset(ranked[:n])
        agg = defaultdict(float)
        for b in blocks[half:]:
            pairs = base_txs(b, written_v3)
            if not pairs:
                continue
            raw = b["txs"]
            none = frozenset()
            cases = (("firm", "firm", None, Tx(0, duration, hot, none, hot)),
                     ("menu", "menu_payer", thr, Tx(0, duration, hot, none, hot)),
                     ("menu_soft", "menu_payer", thr, Tx(0, duration, hot, none, none)),
                     ("menu_read", "menu_payer", thr, Tx(0, duration, none, none, none, hot)),
                     ("soft", "soft", None, Tx(0, duration, hot, none, none)))
            for name, key, th, head in cases:
                pol = policy_txs(pairs, raw, key, q_acct, tabs, th, validate)
                shifted = [Tx(t.idx + 1, t.duration, t.declared, t.writes, t.firm, t.reads) for t in pol]
                without = simulate(pol, threads, validate_soft_reads=validate, order=order)
                withh = simulate([head] + shifted, threads, validate_soft_reads=validate, order=order)
                agg[name + "|without"] += without.makespan
                # the time until every other transaction has committed; the occupier's own reruns do not count
                agg[name + "|with"] += max(e for i, e in withh.ends.items() if i != 0)
                agg[name + "|ser"] += int(withh.serializable)
            agg["blocks"] += 1
        out[str(n)] = {"blocks": int(agg["blocks"])}
        for name in ("firm", "menu", "menu_soft", "menu_read", "soft"):
            out[str(n)][name] = {"makespan_increase": rnd(agg[name + "|with"] / agg[name + "|without"] - 1),
                                 "with_over_firm_with": rnd(agg[name + "|with"] / agg["firm|with"]),
                                 "serializable_all": agg[name + "|ser"] == agg["blocks"]}
    return out


def base_txs(b, written_fn):
    """One Tx per transaction, with its signers; firm sets are filled in per policy."""
    out = []
    for i, t in enumerate(b["txs"]):
        declared, writes, signers = set(), set(), set()
        for e in t["w"]:
            declared.add(e[0])
            if e[1]:
                signers.add(e[0])
            if written_fn(t, e):
                writes.add(e[0])
        out.append((Tx(i, max(1, t["used"]), frozenset(declared), frozenset(writes), frozenset(),
                       frozenset(t.get("ro", ()))), frozenset(signers)))
    return out


def posted_premiums(blocks):
    """Median compute of the first half's declarers of each account, and overall.  A posted premium of x times this
    is the per-account analogue of the threshold 1 / (1 + x)."""
    half = len(blocks) // 2
    durs = defaultdict(list)
    every = []
    for b in blocks[:half]:
        for t in b["txs"]:
            d = max(1, t["used"])
            every.append(d)
            for e in t["w"]:
                if not e[1]:
                    durs[e[0]].append(d)
    return {a: st.median(v) for a, v in durs.items()}, st.median(every)


def policy_txs(pairs, raw, name, q_acct, tabs, thr, validate, posted=None):
    out = []
    for (tx, signers), r in zip(pairs, raw):
        reads = tx.reads
        rest = tx.declared - signers
        if name == "firm":
            firm = tx.declared
        elif name == "soft":
            firm = signers
        elif name == "oracle":
            firm = tx.writes | signers
            if validate:                         # what is declared and not written is held as a read
                reads = reads | (tx.declared - firm)
        elif name == "menu_payer":
            firm = signers | frozenset(a for a in rest if R.q_for(r["payer"], a, tabs) >= thr)
        elif name == "menu_acct":
            firm = signers | frozenset(a for a in rest if q_acct.get(a, 1.0) >= thr)
        elif name == "menu_posted":
            # a transaction goes firm iff q >= c' / (c' + k), with c' its own compute and k posted per account
            med, med_all = posted
            firm = signers | frozenset(a for a in rest if R.q_for(r["payer"], a, tabs) >=
                                       tx.duration / (tx.duration + thr * med.get(a, med_all)))
        else:
            raise ValueError(name)
        # foresight knows what is written, so in the writes view nothing else counts as a possible write
        declared = firm if name == "oracle" and not validate else tx.declared
        out.append(Tx(tx.idx, tx.duration, declared, tx.writes, firm, reads))
    return out


def block_stats(times, firm_times, draws=4000):
    """Block-level view of one policy against all-firm: ratios by block and a bootstrap over blocks of the total cut."""
    x, f = np.array(times), np.array(firm_times)
    idx = np.random.default_rng(0).integers(0, len(x), size=(draws, len(x)))
    cuts = 1 - x[idx].sum(axis=1) / f[idx].sum(axis=1)
    ratios = sorted((x / f).tolist())
    return {"median_ratio": rnd(qt(ratios, .5)), "p10_ratio": rnd(qt(ratios, .1)), "p90_ratio": rnd(qt(ratios, .9)),
            "blocks_slower": int(sum(r > 1 + 1e-9 for r in ratios)),
            "cut_ci95": [rnd(float(np.quantile(cuts, .025))), rnd(float(np.quantile(cuts, .975)))],
            "mean_time": rnd(float(x.mean()), 1), "p90_time": rnd(float(np.quantile(x, .9)), 1), "max_time": rnd(float(x.max()), 1)}


def replay_mode(blocks, written_fn, validate, order, thresholds=(0.25, 0.5, 0.75)):
    R.written = written_fn
    half = len(blocks) // 2
    qhat, nobs = R.estimate_q(blocks[:half])
    q_acct = {k: v for k, v in qhat.items() if nobs[k] >= 3}
    tabs = R.estimate_q_payer(blocks[:half])
    posted = posted_premiums(blocks)
    res = {}
    for threads in THREADS:
        agg = defaultdict(float)
        per_block = defaultdict(list)
        for b in blocks[half:]:
            pairs = base_txs(b, written_fn)
            if not pairs:
                continue
            raw = b["txs"]
            runs = [("firm", "firm", None), ("soft", "soft", None), ("oracle", "oracle", None)]
            if LIGHT:
                runs.append(("menu_payer@0.25", "menu_payer", 0.25))
            else:
                runs.append(("menu_posted@3", "menu_posted", 3.0))
                for thr in thresholds:
                    runs.append((f"menu_payer@{thr}", "menu_payer", thr))
                    runs.append((f"menu_acct@{thr}", "menu_acct", thr))
            for label, name, thr in runs:
                r = simulate(policy_txs(pairs, raw, name, q_acct, tabs, thr, validate, posted), threads,
                             validate_soft_reads=validate, order=order)
                agg[label + "|makespan"] += r.makespan
                agg[label + "|wasted"] += r.wasted
                agg[label + "|busy"] += r.busy
                agg[label + "|reexec"] += r.reexecutions
                agg[label + "|ser"] += int(r.serializable)
                per_block[label].append(r.makespan)
            agg["capacity_bound"] += sum(tx.duration for tx, _ in pairs) / threads
            agg["blocks"] += 1
        names = sorted({k.split("|")[0] for k in agg if "|" in k})
        row = {"blocks": int(agg["blocks"]),
               "firm_over_capacity_bound": rnd(agg["firm|makespan"] / max(1, agg["capacity_bound"]))}
        for nme in names:
            row[nme] = {"makespan_over_firm": rnd(agg[nme + "|makespan"] / max(1, agg["firm|makespan"])),
                        "wasted_share": rnd(agg[nme + "|wasted"] / max(1, agg[nme + "|busy"])),
                        "reexec": int(agg[nme + "|reexec"]),
                        "serializable_all": agg[nme + "|ser"] == agg["blocks"],
                        "by_block": block_stats(per_block[nme], per_block["firm"])}
        res[f"threads={threads}"] = row
    R.written = written_v3
    return res


def replay(blocks):
    if LIGHT:
        return {order: {"reads": replay_mode(blocks, written_v3, True, order)} for order in ("block", "free")}
    return {order: {"reads": replay_mode(blocks, written_v3, True, order),
                    "writes": replay_mode(blocks, written_v3, False, order),
                    "reads_strict_proxy": replay_mode(blocks, written_strict, True, order)}
            for order in ("block", "free")}


def estimate_sources(blocks):
    """Which record the estimate of use falls back on, over the declarations of the second half."""
    half = len(blocks) // 2
    (npa, _), (np_, _), (na, _) = R.estimate_q_payer(blocks[:half])
    n = defaultdict(int)
    for b in blocks[half:]:
        for t in b["txs"]:
            for e in t["w"]:
                if e[1]:
                    continue
                if npa.get((t["payer"], e[0]), 0) >= 3:
                    n["sender_account"] += 1
                elif np_.get(t["payer"], 0) >= 3:
                    n["sender"] += 1
                elif na.get(e[0], 0) >= 3:
                    n["account"] += 1
                else:
                    n["none"] += 1
    tot = max(1, sum(n.values()))
    return {k: rnd(n[k] / tot) for k in ("sender_account", "sender", "account", "none")}


def main(sample, out, do_replay=True):
    blocks = R.load(sample)
    res = {"sample": sample, "meta": meta(blocks), "A": R.section_a(blocks), "declarations": declarations(blocks),
           "hot": hot_accounts(blocks), "senders": senders(blocks), "light": light_version(blocks),
           "use_hist": use_histogram(blocks), "placement_cost": placement_cost(blocks), "incidence": incidence(blocks),
           "estimate_sources": estimate_sources(blocks),
           "occupier": {} if LIGHT else {order: occupier(blocks, order) for order in ("block", "free")}}
    res["B"] = R.section_b(blocks)
    res["token_unchanged_by_heat"] = R.section_c(blocks)
    if do_replay:
        res["replay"] = replay(blocks)
    (BASE / "results" / out).write_text(json.dumps(res, indent=1), encoding="utf-8")
    brief = {k: v for k, v in res.items() if k not in ("hot", "replay", "token_unchanged_by_heat")}
    brief["hot"] = {k: v for k, v in res["hot"].items() if k not in ("shares_sorted", "nonwriter_cdf")}
    print(json.dumps(brief, indent=1))
    if do_replay:
        print(json.dumps(res["replay"], indent=1))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], "--no-replay" not in sys.argv)
