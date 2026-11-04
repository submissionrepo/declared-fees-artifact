"""Sui v2: bounds on shared objects declared mutable that a transaction did not write.

Input data/sui_v2.jsonl (scripts/sample_sui.py with child owners).  Output
results/sui_v2_summary.json.  Discovery only; identities are never printed.

For a successful transaction and a shared input declared mutable:
- upper bound (U): its own contents are unchanged;
- middle (M): contents unchanged and no changed object in the transaction is
  directly owned by it (dynamic fields hang under their parent's id);
- strict lower bound (L): contents unchanged and the transaction changed no
  object owned by another object at all (no dynamic-field change anywhere), so
  no write can hide below any shared input.
Failed transactions are reported separately (their writes are rolled back).
"""
import json
from collections import Counter, defaultdict

BASE = str(__import__("pathlib").Path(__file__).resolve().parents[1])


def main():
    rows = [json.loads(l) for l in open(f"{BASE}/data/sui_v2.jsonl", encoding="utf-8")]
    out = {"transactions": len(rows), "checkpoints": len({r["cp"] for r in rows}),
           "status": dict(Counter(r["status"] for r in rows))}
    heat = Counter()
    for r in rows:
        for a, mut, present, changed in r["shared"]:
            if mut:
                heat[a] += 1
    tiers = [("1", 1, 1), ("2-9", 2, 9), ("10-99", 10, 99), ("100+", 100, 10 ** 9)]
    agg = defaultdict(lambda: [0, 0, 0, 0])     # n, U, M, L
    failed = [0, 0]
    tx_any = [0, 0, 0, 0]
    for r in rows:
        muts = [(a, ch) for a, mut, present, ch in r["shared"] if mut]
        if not muts:
            continue
        if r["status"] != "SUCCESS":
            failed[0] += len(muts)
            failed[1] += sum(1 for _, ch in muts if not ch)
            continue
        owners = set(r.get("child_owners") or [])
        any_child = bool(owners)
        flags = []
        for a, ch in muts:
            u = not ch
            m = u and (a not in owners)
            l = u and not any_child
            flags.append((u, m, l))
            for key in ["all"] + [f"heat_{nm}" for nm, lo, hi in tiers if lo <= heat[a] <= hi]:
                agg[key][0] += 1
                agg[key][1] += int(u)
                agg[key][2] += int(m)
                agg[key][3] += int(l)
        tx_any[0] += 1
        tx_any[1] += int(any(f[0] for f in flags))
        tx_any[2] += int(any(f[1] for f in flags))
        tx_any[3] += int(any(f[2] for f in flags))
    out["successful_mutable_declarations"] = {
        k: {"n": v[0], "upper_unchanged_share": round(v[1] / max(1, v[0]), 4),
            "middle_no_direct_child_share": round(v[2] / max(1, v[0]), 4),
            "strict_lower_share": round(v[3] / max(1, v[0]), 4)} for k, v in sorted(agg.items())}
    out["failed_mutable_declarations"] = {"n": failed[0], "unchanged_share": round(failed[1] / max(1, failed[0]), 4)}
    out["successful_tx_with_mutable_shared"] = tx_any[0]
    out["tx_share_some_not_written"] = {"upper": round(tx_any[1] / max(1, tx_any[0]), 4),
                                        "middle": round(tx_any[2] / max(1, tx_any[0]), 4),
                                        "strict_lower": round(tx_any[3] / max(1, tx_any[0]), 4)}
    json.dump(out, open(f"{BASE}/results/sui_v2_summary.json", "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
