"""Cap and access-list analysis for Monad and Ethereum samples (2026-10-16).  Discovery only.

Monad: limit is charged in full; estimate (parent-state eth_estimateGas) bounds the
need from above, so limit - estimate bounds the paid-but-unneeded gas from below.
Ethereum: gasUsed is charged; limit - used is free slack.  Access lists: declared
items not in the parent-state touched set (declared-unused), and touched items not
declared (used-undeclared), with EIP-2930 pricing: 2400 gas per declared address,
1900 per declared storage key; declared items then cost 100 to access instead of
2600 (address) or 2100 (key).
"""
import json
import statistics as st

BASE = str(__import__("pathlib").Path(__file__).resolve().parents[1])


def q(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p * len(xs)))] if xs else None


def main():
    out = {}
    try:
        M = [json.loads(l) for l in open(f"{BASE}/data/monad_caps.jsonl", encoding="utf-8")]
    except FileNotFoundError:
        M = []
    ok = [r for r in M if r.get("estimate") and r.get("price")]
    if ok:
        ratio = [r["estimate"] / r["limit"] for r in ok]
        slack_gas = [max(0, r["limit"] - r["estimate"]) for r in ok]
        paid = sum(r["limit"] * r["price"] for r in ok)
        unneeded = sum(max(0, r["limit"] - r["estimate"]) * r["price"] for r in ok)
        out["monad"] = {"txs": len(M), "with_estimate": len(ok),
                        "estimate_over_limit_p10": round(q(ratio, 0.1), 4), "p50": round(q(ratio, 0.5), 4),
                        "p90": round(q(ratio, 0.9), 4),
                        "aggregate_estimate_over_limit": round(sum(r["estimate"] for r in ok) / sum(r["limit"] for r in ok), 4),
                        "share_of_fee_paid_for_gas_above_estimate_lower_bound": round(unneeded / paid, 4),
                        "total_fee_mon": round(paid / 1e18, 6), "fee_above_estimate_mon_lower_bound": round(unneeded / 1e18, 6),
                        "share_estimate_above_limit": round(sum(1 for r in ok if r["estimate"] > r["limit"]) / len(ok), 4),
                        "share_limit_near_1p25_estimate": round(sum(1 for r in ok if abs(r["limit"] / r["estimate"] - 1.25) < 0.01) / len(ok), 4)}
    try:
        E = [json.loads(l) for l in open(f"{BASE}/data/ethereum_caps.jsonl", encoding="utf-8")]
        A = [json.loads(l) for l in open(f"{BASE}/data/ethereum_access.jsonl", encoding="utf-8")]
    except FileNotFoundError:
        E, A = [], []
    okE = [r for r in E if r.get("used")]
    if okE:
        ratio = [r["used"] / r["limit"] for r in okE]
        out["ethereum"] = {"txs": len(E), "used_over_limit_p10": round(q(ratio, 0.1), 4), "p50": round(q(ratio, 0.5), 4),
                           "p90": round(q(ratio, 0.9), 4),
                           "aggregate_used_over_limit": round(sum(r["used"] for r in okE) / sum(r["limit"] for r in okE), 4),
                           "share_with_access_list": round(sum(1 for r in E if r["n_access"] > 0) / len(E), 4)}
    okA = [r for r in A if "addr_unused" in r]
    if okA:
        da = sum(r["n_addr"] for r in okA)
        dk = sum(r["n_keys"] for r in okA)
        ua = sum(r["addr_unused"] for r in okA)
        uk = sum(r["keys_unused"] for r in okA)
        ma = sum(r["addr_missing"] for r in okA)
        mk = sum(r["keys_missing"] for r in okA)
        wrong = sum(1 for r in okA if r["addr_unused"] or r["keys_unused"] or r["addr_missing"] or r["keys_missing"])
        # net gas effect of the declared list versus none, at parent-state touches:
        # declared item used: saves 2600-100-2400 = +100 (address) or 2100-100-1900 = +100 (key);
        # declared unused: costs 2400 / 1900; undeclared used: cost unchanged (cold access)
        net = sum(100 * (r["n_addr"] - r["addr_unused"]) + 100 * (r["n_keys"] - r["keys_unused"])
                  - 2400 * r["addr_unused"] - 1900 * r["keys_unused"] for r in okA)
        out["ethereum_access_lists"] = {"txs_checked": len(okA), "txs_err": len(A) - len(okA),
                                        "declared_addresses": da, "declared_keys": dk,
                                        "declared_unused_address_share": round(ua / max(1, da), 4),
                                        "declared_unused_key_share": round(uk / max(1, dk), 4),
                                        "touched_undeclared_addresses": ma, "touched_undeclared_keys": mk,
                                        "share_lists_not_exact": round(wrong / len(okA), 4),
                                        "net_gas_saved_by_lists_total": net,
                                        "share_lists_with_net_loss": round(sum(1 for r in okA if 100 * (r["n_addr"] - r["addr_unused"]) + 100 * (r["n_keys"] - r["keys_unused"]) - 2400 * r["addr_unused"] - 1900 * r["keys_unused"] < 0) / len(okA), 4)}
    json.dump(out, open(f"{BASE}/results/caps_summary.json", "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
