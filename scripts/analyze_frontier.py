"""Theorem 5.6 on Solana: what each rule gives up in drops against what it leaves unpaid (2026-11-02).

Every non-signer writable declaration of the replayed half gets a cost and a choice.  The price of an account is the
priority fee per unit of compute its writers paid in the first half (the sample's overall price if nobody wrote it there),
so an unused lock costs c' = p_o t at rho = 0.  The net value of a branch that uses the account, x + kappa, is m times what
the transaction paid: on Solana the fee is due whether it runs or reverts, and it would not bid more than the trade is
worth, so m = 1 is a lower bound.  Use is estimated from public history by the sender's record for the account, then the
sender's record, then the account's record, each with at least three observations, as (w + 1/2) / (n + 1) so that a record
with no writes does not read as a use probability of exactly zero; with no record the account counts as used.

Each declaration takes its best response.  Against omitting it, one class with fee f = alpha c' gains q V - (1 - q) f.  Two
classes with r = ratio c' and u = beta r gain q V - (1 - q) c' if firm and q (V - k) - (1 - q) u if soft.  A declaration stays
if the better of these is at least zero.  The lead premium is k = c' / 3, where the cost of reruns in the replay matches it;
k = 3 c' is the threshold theta = 0.25 of the replay's lead.

Lost: the share of the fees of successful transactions on those that need a dropped account and so revert.
Unpaid: over declarations left unused, what they cost less what they pay, as a share of what all of them cost when firm.
A dropped declaration left unused costs nothing.  Time: the replay at 16 threads under the same choices, against all firm.
Only aggregates are written.

Usage: python analyze_frontier.py <sample.jsonl> <extensions.json> <out.json>
"""
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import replay_solana as R  # noqa: E402

BASE = Path(__file__).resolve().parents[1]
LIGHT = bool(os.environ.get("DF_LIGHT"))
ALPHAS = [0.0, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.35, 0.5, 0.75, 1.0]
BETAS = [0.0, 0.05, 0.1, 0.2, 0.35, 0.5, 0.75, 1.0]
MS = [1, 3, 10, 30, 100]    # only c' / (x + kappa) matters, so m = 30 at the lead price is m = 3 at a tenth of it
LEAD_M = 3
LEAD_K = 1 / 3
ALT_K = 3.0
THREADS = 16
TIME_ALPHAS = [0.0, 0.01, 0.05, 0.1, 0.2, 0.5, 1.0]
TIME_BETAS = [0.0, 0.2, 1.0]


def q_smooth(payer, acct, tabs, raw=False, min_obs=3):
    if raw:
        return R.q_for(payer, acct, tabs)
    (npa, wpa), (np_, wp), (na, wa) = tabs
    for n, w in ((npa.get((payer, acct), 0), wpa.get((payer, acct), 0)), (np_.get(payer, 0), wp.get(payer, 0)), (na.get(acct, 0), wa.get(acct, 0))):
        if n >= min_obs:
            return (w + 0.5) / (n + 1)
    return 1.0


def prices(blocks, tips=False):
    prio, used = defaultdict(float), defaultdict(float)
    for b in blocks:
        for t in b["txs"]:
            for e in t["w"]:
                if not e[1] and R.written(t, e):
                    prio[e[0]] += t["prio"] + (max(0, t.get("tip", 0)) if tips else 0)
                    used[e[0]] += max(1, t["used"])
    overall = sum(prio.values()) / max(1.0, sum(used.values()))
    return {a: prio[a] / used[a] for a in prio}, overall


def records(blocks, uniform=False, raw=False, tips=False):
    """One row per non-signer writable declaration of the replayed half, and one per transaction.  With tips, what a transaction
    pays and what writers pay count the tips they move outside the protocol."""
    half = len(blocks) // 2
    tabs = R.estimate_q_payer(blocks[:half])
    price, overall = prices(blocks[:half], tips)
    tx_of, q, c, use = [], [], [], []
    fee, ok = [], []
    for b in blocks[half:]:
        for t in b["txs"]:
            i = len(fee)
            fee.append(float(t["fee"]) + (max(0, t.get("tip", 0)) if tips else 0.0))
            ok.append(not t["err"])
            for e in t["w"]:
                if e[1]:
                    continue
                tx_of.append(i)
                q.append(q_smooth(t["payer"], e[0], tabs, raw))
                c.append((overall if uniform else price.get(e[0], overall)) * max(1, t["used"]))
                use.append(bool(R.written(t, e)))
    return tuple(np.array(x) for x in (tx_of, q, c, use, fee, ok))


def one_class(alpha, m, rec):
    tx_of, q, c, use, fee, ok = rec
    v = m * fee[tx_of]
    f = alpha * c
    keep = q * v - (1 - q) * f >= 0
    return keep, keep.copy(), np.where(keep, c - f, 0.0)


def two_classes(beta, ratio, k_over_c, m, rec):
    tx_of, q, c, use, fee, ok = rec
    v = m * fee[tx_of]
    r = min(ratio, 1.0) * c
    u = beta * r
    gain_firm = q * v - (1 - q) * c
    gain_soft = q * (v - k_over_c * c) - (1 - q) * u
    firm = gain_firm >= gain_soft
    keep = np.maximum(gain_firm, gain_soft) >= 0
    return keep, keep & firm, np.where(keep & ~firm, r - u, 0.0)


def score(choice, rec):
    tx_of, q, c, use, fee, ok = rec
    keep, firm, unpaid = choice
    reverted = np.zeros(len(fee), dtype=bool)
    reverted[tx_of[use & ~keep]] = True
    return {"lost": round(float(fee[reverted & ok].sum() / fee[ok].sum()), 4),
            "unpaid": round(float(unpaid[~use].sum() / max(1e-12, c[~use].sum())), 4),
            "dropped": round(float(1 - keep.mean()), 4),
            "soft": round(float((keep & ~firm).mean()), 4),
            "reverted_successful": round(float((reverted & ok).sum() / ok.sum()), 4)}


def replay(blocks, choice, order):
    """Total time at THREADS under one rule's choices, row by row in the order records() made them."""
    keep, firm, _ = choice
    half = len(blocks) // 2
    row = 0
    total = 0.0
    for b in blocks[half:]:
        txs = []
        for i, t in enumerate(b["txs"]):
            signers = frozenset(e[0] for e in t["w"] if e[1])
            kept, firm_set, needs_dropped = set(signers), set(signers), False
            writes = set(e[0] for e in t["w"] if e[1] and R.written(t, e))
            for e in t["w"]:
                if e[1]:
                    continue
                if keep[row]:
                    kept.add(e[0])
                    if firm[row]:
                        firm_set.add(e[0])
                    if R.written(t, e):
                        writes.add(e[0])
                elif R.written(t, e):
                    needs_dropped = True
                row += 1
            if needs_dropped:
                writes &= signers
            txs.append(R.Tx(i, max(1, t["used"]), frozenset(kept), frozenset(writes), frozenset(firm_set), frozenset(t.get("ro", ()))))
        s = R.simulate(txs, THREADS, validate_soft_reads=True, order=order)
        assert s.serializable
        total += s.makespan
    return total


def main(sample, ext, out):
    blocks = R.load(sample)
    e = json.loads((BASE / "results" / ext).read_text(encoding="utf-8"))["replay"]
    ratios = {"producer_16": e["free"]["reads"]["threads=16"]["soft_over_firm_unused"],
              "validator_16": e["block"]["reads"]["threads=16"]["soft_over_firm_unused"],
              "validator_16_writes": e["block"]["writes"]["threads=16"]["soft_over_firm_unused"],
              "producer_4": e["free"]["reads"]["threads=4"]["soft_over_firm_unused"]}
    ratios = {k: max(0.0, v) for k, v in ratios.items()}
    res = {"sample": sample, "ratios": ratios, "alphas": ALPHAS, "betas": BETAS, "time_alphas": TIME_ALPHAS, "time_betas": TIME_BETAS,
           "lead_m": LEAD_M, "lead_k_over_c": LEAD_K, "alt_k_over_c": ALT_K}
    rec = records(blocks)
    tx_of, q, c, use, fee, ok = rec
    res["meta"] = {"declarations": int(len(q)), "unused": int((~use).sum()), "successful": int(ok.sum())}
    res["lead"] = {}
    for m in MS:
        res["lead"][f"m={m}"] = {"one": [score(one_class(a, m, rec), rec) for a in ALPHAS],
                                 "two": {name: [score(two_classes(b, v, LEAD_K, m, rec), rec) for b in BETAS] for name, v in ratios.items()}}
    # the same curves under other choices, at the lead m
    others = [("uniform_price", records(blocks, uniform=True)), ("raw_q", records(blocks, raw=True))]
    if any("tip" in t for b in blocks for t in b["txs"][:1]):
        others.append(("with_tips", records(blocks, tips=True)))
    for label, other in others:
        res[label] = {"one": [score(one_class(a, LEAD_M, other), other) for a in ALPHAS],
                      "two": {name: [score(two_classes(b, v, LEAD_K, LEAD_M, other), other) for b in BETAS] for name, v in ratios.items()}}
    res["alt_k"] = {name: [score(two_classes(b, v, ALT_K, LEAD_M, rec), rec) for b in BETAS] for name, v in ratios.items()}
    if LIGHT:
        (BASE / "results" / out).write_text(json.dumps(res, indent=1), encoding="utf-8")
        return res
    # time under the same choices
    base = {}
    time = {"one": [], "two": [], "two_alt_k": []}
    for order in ("free", "block"):
        all_firm = np.ones(len(q), dtype=bool)
        base[order] = replay(blocks, (all_firm, all_firm, None), order)
    for a in TIME_ALPHAS:
        ch = one_class(a, LEAD_M, rec)
        time["one"].append({**score(ch, rec), **{o: round(replay(blocks, ch, o) / base[o], 4) for o in base}})
    for b in TIME_BETAS:
        row, alt = {}, {}
        for o, name in (("free", "producer_16"), ("block", "validator_16")):
            ch = two_classes(b, ratios[name], LEAD_K, LEAD_M, rec)
            row = {**row, **score(ch, rec), o: round(replay(blocks, ch, o) / base[o], 4)}
            ch = two_classes(b, ratios[name], ALT_K, LEAD_M, rec)
            alt = {**alt, **score(ch, rec), o: round(replay(blocks, ch, o) / base[o], 4)}
        time["two"].append(row)
        time["two_alt_k"].append(alt)
    res["time"] = time
    (BASE / "results" / out).write_text(json.dumps(res, indent=1), encoding="utf-8")
    return res


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
