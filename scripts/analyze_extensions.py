"""Further replay measurements behind Sections 8 and 9 of the paper (2026-11-01).

What an unused soft declaration costs against an unused firm one, in each order and view; classes chosen with full
knowledge of what is written, the upper bound on what self-selection can add to classes from history; the realized
cost of a use against the posted premium, and the fixed point of the two; where the saving comes from (failed or
successful transactions); the one-fee rule in the same replay; the saving by block load; and what read-only
declarations hold.  Only aggregates are written.

Usage: python analyze_extensions.py <sample.jsonl> <out.json>
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_paper_numbers as A  # noqa: E402
import replay_solana as R  # noqa: E402

BASE = Path(__file__).resolve().parents[1]
Tx, simulate = R.Tx, R.simulate
rnd = A.rnd
LIGHT = A.LIGHT
THREADS = (4, 16) if LIGHT else (4, 8, 16)
THETAS = (0.25,) if LIGHT else (0.05, 0.1, 0.15, 0.25, 0.35, 0.5, 0.75)
TAUS = (0.05,) if LIGHT else (0.05, 0.25, 0.5)


def extra_policy(pairs, raw, name, tabs, thr, validate):
    """Policies that A.policy_txs does not have.  'perfect' knows what is written; 'menu_failed' and 'menu_ok' apply
    the menu only to failed or only to successful transactions and keep the others firm."""
    out = []
    for (tx, signers), r in zip(pairs, raw):
        rest = tx.declared - signers
        if name == "perfect":
            firm = tx.writes | signers
        elif name == "menu_failed":
            firm = (signers | frozenset(a for a in rest if R.q_for(r["payer"], a, tabs) >= thr)) if r["err"] else tx.declared
        elif name == "menu_ok":
            firm = (signers | frozenset(a for a in rest if R.q_for(r["payer"], a, tabs) >= thr)) if not r["err"] else tx.declared
        else:
            raise ValueError(name)
        out.append(Tx(tx.idx, tx.duration, tx.declared, tx.writes, firm, tx.reads))
    return out


def one_fee_txs(pairs, raw, tabs, tau):
    """Drop a declaration estimated to be used less often than tau and lock the rest.  A transaction that needs a
    dropped account reverts; it is taken to run for its recorded compute and to write only its signers."""
    out, reverted = [], []
    n_decl = n_drop = 0
    for (tx, signers), r in zip(pairs, raw):
        rest = tx.declared - signers
        drop = frozenset(a for a in rest if R.q_for(r["payer"], a, tabs) < tau)
        n_decl += len(rest)
        n_drop += len(drop)
        rev = bool(drop & tx.writes)
        reverted.append(rev)
        keep = tx.declared - drop
        out.append(Tx(tx.idx, tx.duration, keep, (tx.writes & signers) if rev else tx.writes, keep, tx.reads))
    return out, n_decl, n_drop, reverted


def soft_compute(txs):
    """Compute behind soft declarations that were written and that were not, one unit per unit of compute."""
    used = unused = 0.0
    for t in txs:
        for a in t.declared - t.firm:
            if a in t.writes:
                used += t.duration
            else:
                unused += t.duration
    return used, unused


def boot_ci(x, f, draws=4000):
    x, f = np.array(x), np.array(f)
    idx = np.random.default_rng(0).integers(0, len(x), size=(draws, len(x)))
    cuts = 1 - x[idx].sum(axis=1) / f[idx].sum(axis=1)
    return [rnd(float(np.quantile(cuts, .025))), rnd(float(np.quantile(cuts, .975)))]


def paired_ci(x, y, f, draws=4000):
    """Bootstrap over blocks of (sum y - sum x) / sum f, the lead of policy x over policy y in units of all-firm."""
    x, y, f = np.array(x), np.array(y), np.array(f)
    idx = np.random.default_rng(0).integers(0, len(x), size=(draws, len(x)))
    d = (y[idx].sum(axis=1) - x[idx].sum(axis=1)) / f[idx].sum(axis=1)
    return [rnd(float(np.quantile(d, .025))), rnd(float(np.quantile(d, .975)))]


def main(sample, out):
    blocks = R.load(sample)
    half = len(blocks) // 2
    tabs = R.estimate_q_payer(blocks[:half])
    qhat, nobs = R.estimate_q(blocks[:half])
    q_acct = {k: v for k, v in qhat.items() if nobs[k] >= 3}
    rep = blocks[half:]
    data = [(A.base_txs(b, A.written_v3), b["txs"]) for b in rep]
    res = {"sample": sample, "blocks": len(rep)}

    def base(pairs, raw, name, thr, validate):
        return A.policy_txs(pairs, raw, name, q_acct, tabs, thr, validate)

    res["replay"] = {}
    for order in ("block", "free"):
        res["replay"][order] = {}
        for view, validate in (("reads", True), ("writes", False)):
            res["replay"][order][view] = {}
            for threads in THREADS:
                if LIGHT and view == "writes" and threads != 16:
                    continue
                row = {}
                series = defaultdict(list)
                wasted = defaultdict(float)
                busy = defaultdict(float)
                used_c = defaultdict(float)
                unused_c = defaultdict(float)
                runs = [("firm", lambda p, r: base(p, r, "firm", None, validate)),
                        ("oracle", lambda p, r: base(p, r, "oracle", None, validate)),
                        ("soft", lambda p, r: base(p, r, "soft", None, validate)),
                        ("perfect", lambda p, r: extra_policy(p, r, "perfect", tabs, None, validate))]
                if not LIGHT:
                    runs += [("menu_failed", lambda p, r: extra_policy(p, r, "menu_failed", tabs, .25, validate)),
                             ("menu_ok", lambda p, r: extra_policy(p, r, "menu_ok", tabs, .25, validate))]
                for thr in THETAS:
                    runs.append((f"menu@{thr}", lambda p, r, th=thr: base(p, r, "menu_payer", th, validate)))
                for name, make in runs:
                    for pairs, raw in data:
                        txs = make(pairs, raw)
                        s = simulate(txs, threads, validate_soft_reads=validate, order=order)
                        assert s.serializable, (name, order, view, threads)
                        series[name].append(s.makespan)
                        wasted[name] += s.wasted
                        busy[name] += s.busy
                        u, v = soft_compute(txs)
                        used_c[name] += u
                        unused_c[name] += v
                firm_total = sum(series["firm"])
                for name in series:
                    row[name] = {"over_firm": rnd(sum(series[name]) / firm_total), "wasted_share": rnd(wasted[name] / max(1.0, busy[name])),
                                 "wasted_over_soft_used": rnd(wasted[name] / max(1.0, used_c[name])),
                                 "wasted_total": rnd(wasted[name], 1), "soft_used_compute": rnd(used_c[name], 1), "soft_unused_compute": rnd(unused_c[name], 1)}
                none = sum(series["oracle"]) / firm_total
                row["soft_over_firm_unused"] = rnd((sum(series["perfect"]) / firm_total - none) / max(1e-9, 1 - none))
                row["menu_lead_over_soft"] = {"point": rnd((sum(series["soft"]) - sum(series["menu@0.25"])) / firm_total),
                                              "ci95": paired_ci(series["menu@0.25"], series["soft"], series["firm"])}
                row["perfect_lead_over_menu"] = {"point": rnd((sum(series["menu@0.25"]) - sum(series["perfect"])) / firm_total),
                                                 "ci95": paired_ci(series["perfect"], series["menu@0.25"], series["firm"])}
                if view == "reads":
                    # block load: the top quartile of blocks by total compute against the rest
                    total = [sum(tx.duration for tx, _ in p) for p, _ in data]
                    cut = np.quantile(total, .75)
                    top = [i for i, x in enumerate(total) if x >= cut]
                    rest = [i for i, x in enumerate(total) if x < cut]
                    row["by_load"] = {}
                    for name in ("oracle", "menu@0.25", "soft"):
                        row["by_load"][name] = {
                            "top_over_firm": rnd(sum(series[name][i] for i in top) / sum(series["firm"][i] for i in top)),
                            "rest_over_firm": rnd(sum(series[name][i] for i in rest) / sum(series["firm"][i] for i in rest)),
                            "top_ci95_cut": boot_ci([series[name][i] for i in top], [series["firm"][i] for i in top])}
                    row["by_load"]["top_mean_compute"] = rnd(float(np.mean([total[i] for i in top])), 1)
                    row["by_load"]["rest_mean_compute"] = rnd(float(np.mean([total[i] for i in rest])), 1)
                    row["by_load"]["top_firm_mean_time"] = rnd(float(np.mean([series["firm"][i] for i in top])), 1)
                res["replay"][order][view][f"threads={threads}"] = row

    # the one-fee rule at the same estimate of use
    res["one_fee"] = {}
    for order in ("block", "free"):
        res["one_fee"][order] = {}
        for threads in ((16,) if LIGHT else (4, 16)):
            firm_total = sum(simulate(base(p, r, "firm", None, True), threads, validate_soft_reads=True, order=order).makespan for p, r in data)
            res["one_fee"][order][f"threads={threads}"] = {}
            for tau in TAUS:
                t = 0.0
                dec = drop = ok_tx = rev_tx = 0
                ok_cu = rev_cu = ok_fee = rev_fee = 0.0
                for pairs, raw in data:
                    txs, n_decl, n_drop, reverted = one_fee_txs(pairs, raw, tabs, tau)
                    s = simulate(txs, threads, validate_soft_reads=True, order=order)
                    assert s.serializable
                    t += s.makespan
                    dec += n_decl
                    drop += n_drop
                    for rv, r, (tx, _) in zip(reverted, raw, pairs):
                        if r["err"]:
                            continue
                        ok_tx += 1
                        ok_cu += tx.duration
                        ok_fee += r["prio"]
                        if rv:
                            rev_tx += 1
                            rev_cu += tx.duration
                            rev_fee += r["prio"]
                res["one_fee"][order][f"threads={threads}"][str(tau)] = {
                    "over_firm": rnd(t / firm_total), "dropped_share": rnd(drop / max(1, dec)),
                    "reverted_share_of_successful": rnd(rev_tx / max(1, ok_tx)),
                    "reverted_compute_share": rnd(rev_cu / max(1.0, ok_cu)), "reverted_priority_fee_share": rnd(rev_fee / max(1.0, ok_fee))}

    # what read-only declarations hold: how many sit on an account some transaction in the block wrote
    ro_all = ro_written = 0
    cu_all = cu_written = 0.0
    tx_any = tx_n = 0
    for pairs, raw in data:
        written = set()
        for tx, _ in pairs:
            written |= tx.writes
        for tx, signers in pairs:
            n = len(tx.reads)
            k = len(tx.reads & written)
            ro_all += n
            ro_written += k
            cu_all += n * tx.duration
            cu_written += k * tx.duration
            tx_n += 1
            tx_any += bool(k)
    res["read_only"] = {"declarations": ro_all, "share_on_account_written_in_block": rnd(ro_written / max(1, ro_all)),
                        "compute_share_on_account_written_in_block": rnd(cu_written / max(1.0, cu_all)),
                        "tx_share_with_one": rnd(tx_any / max(1, tx_n))}
    (BASE / "results" / out).write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items() if k != "replay"}, indent=1))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
