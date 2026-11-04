"""Who holds the hot accounts of Solana without writing them, and what that costs others (2026-11-01).

Public data cannot show intent, so this measures occupancy in effect.  For each block's five accounts with the most
declared compute we split the time locks were held (consumed compute) and the budget they took before execution
(declared compute) by the holder: writers; successful transactions that did not write; failed transactions, by whether
the sender wrote this account elsewhere in the sample, succeeded elsewhere, or never succeeded.  Then we ask how few
senders account for it, what they pay, and how much of the waiting a validator or producer could avoid would go if
only they stopped holding.  Only aggregates are written.

Usage: python analyze_occupancy.py <sample.jsonl> <out.json>
"""
import json
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_paper_numbers as A  # noqa: E402
import replay_solana as R  # noqa: E402

BASE = Path(__file__).resolve().parents[1]
Tx, simulate = R.Tx, R.simulate
rnd = A.rnd
MIN_TX = 3


def hot_of(block, top=5):
    dec = defaultdict(int)
    for t in block["txs"]:
        for e in t["w"]:
            if not e[1]:
                dec[e[0]] += t["limit"]
    return set(sorted(dec, key=lambda k: -dec[k])[:top])


def sender_records(blocks):
    n, ok = Counter(), Counter()
    wrote_pair = set()
    for b in blocks:
        for t in b["txs"]:
            n[t["payer"]] += 1
            ok[t["payer"]] += not t["err"]
            for e in t["w"]:
                if not e[1] and R.written(t, e):
                    wrote_pair.add((t["payer"], e[0]))
    return n, ok, wrote_pair


def classify(t, e, n, ok, wrote_pair):
    if R.written(t, e):
        return "written"
    if not t["err"]:
        if e[2]:
            return "ok_token_unchanged"
        return "ok_route_leg"
    if (t["payer"], e[0]) in wrote_pair:
        return "failed_sender_won_here"
    if ok[t["payer"]]:
        return "failed_sender_won_elsewhere"
    return "failed_never_won_repeat" if n[t["payer"]] >= MIN_TX else "failed_never_won_once"


def holders(blocks):
    n, ok, wrote_pair = sender_records(blocks)
    used, declared, count = Counter(), Counter(), Counter()
    by_sender = Counter()
    by_sender_decl = Counter()
    same_block_time = other_block_time = 0
    pos_all, pos_never = [], []
    used_by_class = defaultdict(list)
    fee_by_class = defaultdict(lambda: [0, 0])
    for b in blocks:
        hot = hot_of(b)
        writers = defaultdict(set)
        for t in b["txs"]:
            for e in t["w"]:
                if not e[1] and e[0] in hot and R.written(t, e):
                    writers[e[0]].add(t["payer"])
        m = max(1, len(b["txs"]) - 1)
        for i, t in enumerate(b["txs"]):
            for e in t["w"]:
                if e[1] or e[0] not in hot:
                    continue
                c = classify(t, e, n, ok, wrote_pair)
                d = max(1, t["used"])
                used[c] += d
                declared[c] += t["limit"]
                count[c] += 1
                used_by_class[c].append(d)
                fee_by_class[c][0] += t["prio"]
                fee_by_class[c][1] += d
                if c != "written":
                    by_sender[t["payer"]] += d
                    by_sender_decl[t["payer"]] += t["limit"]
                    pos_all.append(i / m)
                    if t["payer"] in writers[e[0]]:
                        same_block_time += d
                    else:
                        other_block_time += d
                if c.startswith("failed_never"):
                    pos_never.append(i / m)
    tot = sum(used.values())
    totd = sum(declared.values())
    unwritten = sum(v for k, v in used.items() if k != "written")
    order = [a for a, _ in by_sender.most_common()]
    never = [a for a in n if not ok[a] and n[a] >= MIN_TX]
    never_hot = [a for a in never if by_sender[a] > 0]
    out = {"senders_holding_without_writing": len(by_sender),
           "shares_of_hot_lock_time": {k: rnd(v / tot) for k, v in sorted(used.items())},
           "shares_of_hot_declared_compute": {k: rnd(v / totd) for k, v in sorted(declared.items())},
           "declarations": dict(count),
           "median_compute": {k: st.median(v) for k, v in used_by_class.items()},
           "priority_fee_per_mcu": {k: rnd(v[0] / max(1, v[1]) * 1e6, 1) for k, v in fee_by_class.items()},
           "top10_share_of_unwritten_hot_time": rnd(sum(by_sender[a] for a in order[:10]) / max(1, unwritten)),
           "top100_share_of_unwritten_hot_time": rnd(sum(by_sender[a] for a in order[:100]) / max(1, unwritten)),
           "share_of_unwritten_hot_time_by_senders_writing_it_in_the_block": rnd(same_block_time / max(1, same_block_time + other_block_time)),
           "senders_never_won": {"n_with_3plus_tx": len(never), "holding_hot": len(never_hot),
                                 "tx": sum(n[a] for a in never_hot),
                                 "tx_per_sender_median": st.median([n[a] for a in never_hot]) if never_hot else 0},
           "position_in_block_median": {"all_unwritten": rnd(st.median(pos_all)) if pos_all else None,
                                        "never_won": rnd(st.median(pos_never)) if pos_never else None}}
    return out, order, never


def harm(blocks, threads=16):
    """Total time when only some senders stop holding what they do not write: firm on what they wrote, soft on the rest;
    everyone else stays firm.  Senders are ranked on the replayed half by unwritten hot lock time, which is an ex post
    attribution of who causes the avoidable waiting, not a classifier."""
    half = len(blocks) // 2
    rep = blocks[half:]
    n, ok, wrote_pair = sender_records(blocks)
    by_sender = Counter()
    for b in rep:
        hot = hot_of(b)
        for t in b["txs"]:
            for e in t["w"]:
                if not e[1] and e[0] in hot and not R.written(t, e):
                    by_sender[t["payer"]] += max(1, t["used"])
    order = [a for a, _ in by_sender.most_common()]
    never = {a for a in n if not ok[a] and n[a] >= MIN_TX}
    sets = {"top10": set(order[:10]), "top100": set(order[:100]), "never_won": never, "all": set(n)}
    data = [(A.base_txs(b, A.written_v3), b["txs"]) for b in rep]
    res = {}
    for order_name in ("block", "free"):
        res[order_name] = {}
        firm_total = 0.0
        for pairs, raw in data:
            txs = [Tx(tx.idx, tx.duration, tx.declared, tx.writes, tx.declared, tx.reads) for tx, _ in pairs]
            firm_total += simulate(txs, threads, validate_soft_reads=True, order=order_name).makespan
        for name, senders in sets.items():
            total = wasted = busy = 0.0
            for pairs, raw in data:
                txs = []
                for (tx, signers), r in zip(pairs, raw):
                    firm = (tx.writes | signers) if r["payer"] in senders else tx.declared
                    txs.append(Tx(tx.idx, tx.duration, tx.declared, tx.writes, firm, tx.reads))
                s = simulate(txs, threads, validate_soft_reads=True, order=order_name)
                assert s.serializable
                total += s.makespan
                wasted += s.wasted
                busy += s.busy
            res[order_name][name] = {"over_firm": rnd(total / firm_total), "wasted_share": rnd(wasted / max(1.0, busy))}
    res["senders"] = {k: len(v) for k, v in sets.items()}
    res["replayed_tx_share"] = {k: rnd(sum(t["payer"] in v for b in rep for t in b["txs"]) / max(1, sum(len(b["txs"]) for b in rep))) for k, v in sets.items()}
    return res


def main(sample, out):
    blocks = R.load(sample)
    res, _, _ = holders(blocks)
    res["sample"] = sample
    res["harm_at_16_threads"] = harm(blocks)
    (BASE / "results" / out).write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
