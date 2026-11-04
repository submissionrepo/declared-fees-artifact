"""Measurement and menu replay on the Solana day sample (2026-10-16).

Input: a sample in data/ (scripts/sample_solana_v4.py).  Output: a JSON summary in
results/ and a printed report.

Sections A to C and the helpers feed analyze_paper_numbers.py.  Sections D and E are an earlier report and are not
used for the paper.
"""
import gzip
import json
import statistics as st
import sys
from collections import defaultdict

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1] / "prototype"))
from scheduler_sim import Tx, simulate, with_policy  # noqa: E402

BASE = str(__import__("pathlib").Path(__file__).resolve().parents[1])
ACCOUNT_LIMIT = 20_000_000


def load(name="solana_day.jsonl"):
    """One sample, or several joined by '+'; a name ending in .gz is read as gzip."""
    blocks = []
    pool = {}       # one string per account, since a sample names the same accounts many thousand times
    for part in name.split("+"):
        path = f"{BASE}/data/{part}"
        with (gzip.open(path, "rt", encoding="utf-8") if part.endswith(".gz") else open(path, encoding="utf-8")) as fh:
            for line in fh:
                b = json.loads(line)
                for t in b["txs"]:
                    t.pop("progs", None)
                    t["payer"] = pool.setdefault(t["payer"], t["payer"])
                    for e in t["w"]:
                        e[0] = pool.setdefault(e[0], e[0])
                    if "ro" in t:
                        t["ro"] = [pool.setdefault(a, a) for a in t["ro"]]
                blocks.append(b)
    blocks.sort(key=lambda b: b["slot"])
    return blocks


def q(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p * len(xs)))] if xs else None


def section_a(blocks):
    out = {}
    txs = [t for b in blocks for t in b["txs"]]
    groups = {
        "all": txs,
        "legacy": [t for t in txs if t["v"] == "legacy"],
        "v0": [t for t in txs if t["v"] == 0],
        "v1": [t for t in txs if t["v"] == 1],
        "failed": [t for t in txs if t["err"]],
        "succeeded": [t for t in txs if not t["err"]],
        "default_limit": [t for t in txs if not t["explicit"]],
    }
    for k, g in groups.items():
        dec = sum(t["limit"] for t in g)
        used = sum(t["used"] for t in g)
        ratios = [t["used"] / t["limit"] for t in g if t["limit"] > 0]
        out[k] = {"n": len(g), "declared": dec, "used": used,
                  "used_over_declared": round(used / max(1, dec), 4),
                  "p10": round(q(ratios, 0.1) or 0, 4), "p50": round(q(ratios, 0.5) or 0, 4),
                  "p90": round(q(ratios, 0.9) or 0, 4)}
    out["n_blocks"] = len(blocks)
    out["share_declared_default"] = round(groups["default_limit"] and sum(t["limit"] for t in groups["default_limit"]) / max(1, sum(t["limit"] for t in txs)), 4)
    out["over_limit_failures"] = sum(1 for t in txs if t["err"] and t["limit"] > 0 and t["used"] >= t["limit"])
    out["failures"] = sum(1 for t in txs if t["err"])
    return out


def section_b(blocks):
    by = defaultdict(lambda: {"old": [], "v1": []})
    for b in blocks:
        for t in b["txs"]:
            if t["limit"] <= 0 or t["err"]:
                continue
            key = "v1" if t["v"] == 1 else "old"
            by[t["payer"]][key].append(t["used"] / t["limit"])
    both = [(st.median(v["old"]), st.median(v["v1"])) for v in by.values() if v["old"] and v["v1"]]
    diffs = [b - a for a, b in both]
    return {"payers_with_both": len(both),
            "median_old": round(st.median([a for a, _ in both]), 4) if both else None,
            "median_v1": round(st.median([b for _, b in both]), 4) if both else None,
            "median_within_payer_diff": round(st.median(diffs), 4) if diffs else None,
            "share_payers_tighter_in_v1": round(sum(d > 0 for d in diffs) / max(1, len(diffs)), 4)}


def section_c(blocks):
    heat = defaultdict(int)
    for b in blocks:
        for t in b["txs"]:
            for e in t["w"]:
                k, signer, tok, ch = e[0], e[1], e[2], e[3]
                if tok and not signer:
                    heat[k] += 1
    tiers = {"1": (1, 1), "2-9": (2, 9), "10-99": (10, 99), "100+": (100, 10 ** 12)}
    agg = {name: [0, 0] for name in tiers}
    total = [0, 0]
    for b in blocks:
        for t in b["txs"]:
            if t["err"]:
                continue
            for e in t["w"]:
                k, signer, tok, ch = e[0], e[1], e[2], e[3]
                if not tok or signer:
                    continue
                h = heat[k]
                for name, (lo, hi) in tiers.items():
                    if lo <= h <= hi:
                        agg[name][0] += 1
                        agg[name][1] += int(not ch)
                total[0] += 1
                total[1] += int(not ch)
    return {"writable_token_accounts": total[0], "unchanged": total[1],
            "unchanged_share": round(total[1] / max(1, total[0]), 4),
            "by_heat": {k: {"n": v[0], "unchanged_share": round(v[1] / max(1, v[0]), 4)} for k, v in agg.items()}}


def section_d(blocks):
    shares = []
    near = 0
    rows = 0
    top_ratio = []
    for b in blocks:
        dec = defaultdict(int)
        used = defaultdict(int)
        for t in b["txs"]:
            for e in t["w"]:
                k, signer = e[0], e[1]
                if signer:
                    continue
                dec[k] += t["limit"]
                used[k] += t["used"]
        if not dec:
            continue
        top = sorted(dec, key=lambda k: -dec[k])[:5]
        for k in top:
            shares.append(dec[k] / ACCOUNT_LIMIT)
            top_ratio.append(used[k] / max(1, dec[k]))
            rows += 1
            near += int(dec[k] >= 0.5 * ACCOUNT_LIMIT)
    return {"top5_rows": rows, "declared_over_limit_p50": round(q(shares, 0.5), 4),
            "declared_over_limit_p90": round(q(shares, 0.9), 4), "declared_over_limit_max": round(max(shares), 4),
            "rows_at_least_half_limit": near, "used_over_declared_p50": round(q(top_ratio, 0.5), 4)}


def written(t, e):
    """Usage proxy for one declared writable account entry e of transaction t.

    v2 entries [key, signer, token, changed]: non-token accounts are treated as
    written (data writes invisible).  v3 entries add [inner_ref, router_only]:
    a non-token account counts as written unless only router-like top-level
    instructions referenced it and no executed leg received it.  Failed
    transactions write nothing except the fee payer (signers)."""
    signer, tok, ch = e[1], e[2], e[3]
    if signer:
        return True
    if t["err"]:
        return False
    if tok:
        return bool(ch)
    if len(e) >= 6:
        return not e[5]
    return True


def estimate_q(blocks):
    n = defaultdict(int)
    w = defaultdict(int)
    for b in blocks:
        for t in b["txs"]:
            for e in t["w"]:
                if e[1]:
                    continue
                if len(e) < 6 and not e[2]:
                    continue                    # v2 sample: non-token usage unobserved
                n[e[0]] += 1
                w[e[0]] += int(written(t, e))
    return {k: w[k] / n[k] for k in n}, n


def block_txs(b):
    txs = []
    for i, t in enumerate(b["txs"]):
        declared, writes = set(), set()
        for e in t["w"]:
            declared.add(e[0])
            if written(t, e):
                writes.add(e[0])
        txs.append(Tx(i, max(1, t["used"]), frozenset(declared), frozenset(writes)))
    return txs


def section_c3(blocks):
    """v3 proxy: declared writable non-signer accounts that the transaction did not write."""
    tot = fail = router = tokun = 0
    for b in blocks:
        for t in b["txs"]:
            for e in t["w"]:
                if e[1]:
                    continue
                tot += 1
                if t["err"]:
                    fail += 1
                elif e[2] and not e[3]:
                    tokun += 1
                elif (not e[2]) and len(e) >= 6 and e[5]:
                    router += 1
    return {"writable_nonsigner": tot, "in_failed_tx": fail, "token_unchanged": tokun,
            "router_leg_not_executed": router,
            "not_written_share": round((fail + tokun + router) / max(1, tot), 4)}


def estimate_q_payer(blocks):
    """Use probability per (payer, account), per payer, and per account (for backoff)."""
    npa, wpa = defaultdict(int), defaultdict(int)
    np_, wp = defaultdict(int), defaultdict(int)
    na, wa = defaultdict(int), defaultdict(int)
    for b in blocks:
        for t in b["txs"]:
            for e in t["w"]:
                if e[1] or (len(e) < 6 and not e[2]):
                    continue
                u = int(written(t, e))
                npa[(t["payer"], e[0])] += 1
                wpa[(t["payer"], e[0])] += u
                np_[t["payer"]] += 1
                wp[t["payer"]] += u
                na[e[0]] += 1
                wa[e[0]] += u
    return (npa, wpa), (np_, wp), (na, wa)


def q_for(payer, acct, tabs, min_obs=3):
    (npa, wpa), (np_, wp), (na, wa) = tabs
    if npa.get((payer, acct), 0) >= min_obs:
        return wpa[(payer, acct)] / npa[(payer, acct)]
    if np_.get(payer, 0) >= min_obs:
        return wp[payer] / np_[payer]
    if na.get(acct, 0) >= min_obs:
        return wa[acct] / na[acct]
    return 1.0


def section_e(blocks, threads_list=(4, 8, 16, 32), thresholds=(0.25, 0.5, 0.75), min_obs=3):
    half = len(blocks) // 2
    qhat, nobs = estimate_q(blocks[:half])
    q_acct = {k: v for k, v in qhat.items() if nobs[k] >= min_obs}
    tabs = estimate_q_payer(blocks[:half])
    res = {}
    for threads in threads_list:
        agg = defaultdict(float)
        for b in blocks[half:]:
            txs = block_txs(b)
            if not txs:
                continue
            raw = b["txs"]
            runs = {"firm": with_policy(txs, "firm"), "soft": with_policy(txs, "soft")}
            runs["oracle"] = [Tx(t.idx, t.duration, t.declared, t.writes, t.writes) for t in txs]
            for thr in thresholds:
                acct_pol = []
                payer_pol = []
                for t, r in zip(txs, raw):
                    fa = frozenset(a for a in t.declared if q_acct.get(a, 1.0) >= thr)
                    fp = frozenset(a for a in t.declared if q_for(r["payer"], a, tabs, min_obs) >= thr)
                    acct_pol.append(Tx(t.idx, t.duration, t.declared, t.writes, fa))
                    payer_pol.append(Tx(t.idx, t.duration, t.declared, t.writes, fp))
                runs[f"menu_acct@{thr}"] = acct_pol
                runs[f"menu_payer@{thr}"] = payer_pol
            for name, pol in runs.items():
                r = simulate(pol, threads)
                agg[name + "|makespan"] += r.makespan
                agg[name + "|wasted"] += r.wasted
                agg[name + "|busy"] += r.busy
                agg[name + "|reexec"] += r.reexecutions
                agg[name + "|ser"] += int(r.serializable)
            agg["capacity_bound"] += sum(t.duration for t in txs) / threads
            agg["blocks"] += 1
        names = sorted({k.split("|")[0] for k in agg if "|" in k})
        row = {"blocks": int(agg["blocks"]),
               "firm_over_capacity_bound": round(agg["firm|makespan"] / max(1, agg["capacity_bound"]), 4)}
        for nme in names:
            row[nme] = {"makespan_over_firm": round(agg[nme + "|makespan"] / max(1, agg["firm|makespan"]), 4),
                        "wasted_share": round(agg[nme + "|wasted"] / max(1, agg[nme + "|busy"]), 4),
                        "reexec": int(agg[nme + "|reexec"]),
                        "serializable_all": agg[nme + "|ser"] == agg["blocks"]}
        res[f"threads={threads}"] = row
    res["accounts_with_q"] = len(q_acct)
    res["share_q_below_half"] = round(sum(1 for v in q_acct.values() if v < 0.5) / max(1, len(q_acct)), 4)
    return res


if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else "solana_day.jsonl"
    blocks = load(name)
    out = {"A": section_a(blocks), "B": section_b(blocks), "C": section_c(blocks), "D": section_d(blocks)}
    if blocks and blocks[0]["txs"] and len(blocks[0]["txs"][0]["w"][0]) >= 6:
        out["C3"] = section_c3(blocks)
    print(json.dumps(out, indent=1))
    out["E"] = section_e(blocks)
    print(json.dumps(out["E"], indent=1))
    json.dump(out, open(f"{BASE}/results/replay_solana_{name.replace('.jsonl', '')}.json", "w"), indent=1)
