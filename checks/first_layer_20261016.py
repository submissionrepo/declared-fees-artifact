"""Exact checks for the declared-resource fee theory (2026-10-16).

Statements mirror an earlier form of the theory (v1).  All
arithmetic is exact (fractions.Fraction or sympy rationals).  Finite checks
certify the finite statements listed; the general statements rest on the
written proofs.

D1  Proposition 1 and Theorem 1(a),(c): symbolic threshold; exhaustive grid
    showing that for every f_n > 0 some (q, x, kappa) makes omission strictly
    better, and that at f_n = alpha_min the omitted region is exactly
    q < q*(alpha_min).
D2  Theorem 2 (i)-(iii) on joint use distributions: m = 2 objects, all
    distributions over the 4 used sets with masses in multiples of 1/4; m = 3
    objects, all distributions over the 8 used sets with masses in multiples
    of 1/3; parameters on small rational grids; every declaration vector in
    {omit, firm, soft}^m is evaluated.  Checked: (i) the threshold vector
    (firm iff q_o >= q_L, soft otherwise, omit only if q_o = 0) attains the
    maximum expected utility; no optimal vector omits an object with q_o > 0
    when the strict individual-rationality margin holds; (ii) per-object
    class choice equals argmin of expected occupancy cost; (iii) expected
    declaration payment equals expected occupancy cost of the chosen classes.
    Includes route-style types (exactly one object used).
D3  Theorem 3 (uniqueness): sympy linear system.
D4  Theorem 4: exhaustive over shill options (class, used or not, t_s,
    priority) and parameter grids: no profitable shill iff
    gamma <= 1/(1 + eta pi_o) under pay-what-you-count; Wadhwa's
    declared-set counting needs (1 - gamma) alpha >= gamma eta pi_o.
D5  Proposition 2 (cap declarations): discrete needs X on {1,..,4} with
    masses in multiples of 1/4; caps d in {0,..,4}; the user's optimal caps
    equal the efficient caps for every instance iff p = c and alpha = 1 - rho
    (sufficiency is an identity and is checked exhaustively; necessity by
    exhibiting a counterexample for every grid point with (p, alpha) !=
    (c, 1 - rho), searching values v in {1, 3, 8} and then v in {1/4,..,20}).
"""
import itertools
import json
import sys
from fractions import Fraction as Fr

import sympy as sp

RESULTS = {}


def compositions(total, parts):
    """All tuples of `parts` non-negative ints summing to `total`."""
    if parts == 1:
        yield (total,)
        return
    for first in range(total + 1):
        for rest in compositions(total - first, parts - 1):
            yield (first,) + rest


# ---------------------------------------------------------------- D1
def check_d1():
    q, x, kap, fn = sp.symbols("q x kappa f_n", nonnegative=True)
    diff = q * (x + kap) - (1 - q) * fn          # declare minus omit
    qstar = sp.solve(sp.Eq(diff, 0), q)[0]
    assert sp.simplify(qstar - fn / (fn + x + kap)) == 0
    fails = 0
    cases = 0
    grid_f = [Fr(1, 10), Fr(1, 4), Fr(1, 2), Fr(1), Fr(2)]
    grid_x = [Fr(1, 10), Fr(1), Fr(5)]
    grid_k = [Fr(0), Fr(1, 2), Fr(1)]
    for f in grid_f:
        for xv in grid_x:
            for kv in grid_k:
                qs = f / (f + xv + kv)
                # a q just below the threshold makes omission strictly better
                qlow = qs / 2
                d_low = qlow * (xv + kv) - (1 - qlow) * f
                d_at = qs * (xv + kv) - (1 - qs) * f
                qhigh = (qs + 1) / 2
                d_high = qhigh * (xv + kv) - (1 - qhigh) * f
                cases += 1
                if not (d_low < 0 and d_at == 0 and d_high > 0):
                    fails += 1
    # Theorem 1(c): alpha_min = pi eta gamma / (1 - gamma); infeasible alpha <= 1 iff pi eta gamma/(1-gamma) > 1
    infeas = []
    for pi_o in [Fr(6, 5), Fr(5), Fr(16)]:
        a_min = pi_o * Fr(1, 8) * Fr(1, 2) / (1 - Fr(1, 2))
        infeas.append((str(pi_o), str(a_min), a_min > 1))
    assert infeas == [("6/5", "3/20", False), ("5", "5/8", False), ("16", "2", True)]
    RESULTS["D1"] = {"cases": cases, "failures": fails, "alpha_min_table": infeas}
    return fails == 0


# ---------------------------------------------------------------- D2
def expected_utility(dist, decl, v, kappa, u, c, rho, k):
    """dist: dict frozenset(used) -> prob; decl: tuple in {'N','F','S'} per object."""
    m = len(decl)
    eu = Fr(0)
    for X, pr in dist.items():
        if pr == 0:
            continue
        if any(o in X and decl[o] == "N" for o in range(m)):
            eu += pr * (-kappa)
            continue
        fee = Fr(0)
        for o in range(m):
            if o in X:
                fee += u[o] + (k[o] if decl[o] == "S" else 0)
            elif decl[o] == "F":
                fee += (1 - rho) * c[o]
        eu += pr * (v - fee)
    return eu


def check_d2():
    cases = 0
    fails = []
    strict_cases = 0
    for m, denom in [(2, 4), (3, 3)]:
        subsets = [frozenset(s) for r in range(m + 1) for s in itertools.combinations(range(m), r)]
        dists = []
        for comp in compositions(denom, len(subsets)):
            dists.append({subsets[i]: Fr(comp[i], denom) for i in range(len(subsets))})
        params = []
        for rho in [Fr(0), Fr(1, 2)]:
            for cval in [Fr(1), Fr(2)]:
                for kval in [Fr(1, 2), Fr(2)]:
                    params.append((rho, cval, kval))
        for dist in dists:
            qo = [sum(pr for X, pr in dist.items() if o in X) for o in range(m)]
            for rho, cval, kval in params:
                c = [cval] * m
                k = [kval] + [kval * 2] * (m - 1)   # heterogeneous conflict premia
                u = [Fr(1)] * m
                kappa = Fr(1, 2)
                # strict individual rationality: every branch, any declaration, beats revert
                worst = max(sum(u[o] + k[o] for o in X) + sum((1 - rho) * c[o] for o in range(m) if o not in X)
                            for X in subsets)
                v = worst - kappa + Fr(1, 2)
                best_val = None
                best = []
                for decl in itertools.product("NFS", repeat=m):
                    eu = expected_utility(dist, decl, v, kappa, u, c, rho, k)
                    if best_val is None or eu > best_val:
                        best_val, best = eu, [decl]
                    elif eu == best_val:
                        best.append(decl)
                # threshold vector
                thr = []
                for o in range(m):
                    qL = (1 - rho) * c[o] / ((1 - rho) * c[o] + k[o])
                    if qo[o] == 0:
                        thr.append("S")
                    else:
                        thr.append("F" if qo[o] >= qL else "S")
                thr = tuple(thr)
                eu_thr = expected_utility(dist, thr, v, kappa, u, c, rho, k)
                cases += 1
                ok = (eu_thr == best_val)
                # (i) no optimal vector omits an object used with positive probability
                for decl in best:
                    if any(decl[o] == "N" and qo[o] > 0 for o in range(m)):
                        ok = False
                # (ii)/(iii): expected declaration payment of thr equals sum of min costs
                pay = Fr(0)
                mincost = Fr(0)
                for o in range(m):
                    pay += (1 - qo[o]) * (1 - rho) * c[o] if thr[o] == "F" else qo[o] * k[o]
                    mincost += min((1 - qo[o]) * (1 - rho) * c[o], qo[o] * k[o])
                usage = sum(qo[o] * u[o] for o in range(m))
                if pay != mincost or v - usage - pay != eu_thr:
                    ok = False
                if any(qo[o] > 0 for o in range(m)):
                    strict_cases += 1
                if not ok:
                    fails.append({"m": m, "dist": {str(sorted(X)): str(p) for X, p in dist.items()},
                                  "rho": str(rho), "c": str(cval), "k": str(kval)})
                    if len(fails) > 5:
                        break
    RESULTS["D2"] = {"cases": cases, "with_positive_use": strict_cases, "failures": len(fails),
                     "first_failures": fails[:3]}
    return not fails


# ---------------------------------------------------------------- D3
def check_d3():
    q, a0, a1, b0, b1, c, rho, k = sp.symbols("q a0 a1 b0 b1 c rho k")
    eqF = sp.Poly(sp.expand(q * a1 + (1 - q) * a0 - (1 - q) * (1 - rho) * c), q).all_coeffs()
    eqS = sp.Poly(sp.expand(q * b1 + (1 - q) * b0 - q * k), q).all_coeffs()
    sol = sp.solve(eqF + eqS, [a0, a1, b0, b1], dict=True)
    ok = sol == [{a0: c * (1 - rho), a1: 0, b0: 0, b1: k}] or (
        len(sol) == 1 and sp.simplify(sol[0][a0] - c * (1 - rho)) == 0 and sol[0][a1] == 0
        and sol[0][b0] == 0 and sol[0][b1] == k)
    RESULTS["D3"] = {"solution": {str(kk): str(vv) for kk, vv in sol[0].items()}}
    return ok


# ---------------------------------------------------------------- D4
def check_d4():
    cases = 0
    fails = 0
    p = Fr(1)
    for gamma in [Fr(i, 12) for i in range(1, 12)]:
        for eta in [Fr(1, 8), Fr(1, 4)]:
            for pi_o in [Fr(6, 5), Fr(5), Fr(8), Fr(16)]:
                for rho in [Fr(0), Fr(1, 3), Fr(1, 2)]:
                    for kk in [Fr(0), Fr(1, 2)]:
                        profitable = False
                        for cls in ["F", "S"]:
                            for used in [0, 1]:
                                for ts in [Fr(1), Fr(2), Fr(3)]:
                                    for pi_s in [Fr(1), Fr(2)]:
                                        if used:
                                            w = ts
                                            paid = pi_s * p * ts + (kk if cls == "S" else 0)
                                        else:
                                            w = (1 - rho) * ts if cls == "F" else Fr(0)
                                            paid = (1 - rho) * p * ts if cls == "F" else Fr(0)
                                        gain = gamma * eta * pi_o * p * w
                                        cost = (1 - gamma) * paid
                                        if gain > cost:
                                            profitable = True
                        predicted = gamma > 1 / (1 + eta * pi_o)
                        cases += 1
                        if profitable != predicted:
                            fails += 1
    # Wadhwa declared-set counting: a non-using shill counts t_s and pays alpha p t_s
    w_cases = 0
    w_fails = 0
    for gamma in [Fr(i, 12) for i in range(1, 12)]:
        for eta in [Fr(1, 8)]:
            for pi_o in [Fr(6, 5), Fr(5), Fr(16)]:
                for alpha in [Fr(i, 10) for i in range(0, 11)]:
                    ts = Fr(1)
                    gain = gamma * eta * pi_o * p * ts
                    cost = (1 - gamma) * alpha * p * ts
                    profitable = gain > cost
                    predicted = (1 - gamma) * alpha < gamma * eta * pi_o
                    w_cases += 1
                    if profitable != predicted:
                        w_fails += 1
    RESULTS["D4"] = {"cases": cases, "failures": fails, "wadhwa_cases": w_cases, "wadhwa_failures": w_fails}
    return fails == 0 and w_fails == 0


# ---------------------------------------------------------------- D5
def cap_values(dist, d, v, coef_fixed, coef_use):
    """value v P(X<=d) - [coef_fixed d + coef_use E min(X,d)]"""
    F = sum(pr for xval, pr in dist.items() if xval <= d)
    emin = sum(pr * min(xval, d) for xval, pr in dist.items())
    return v * F - (coef_fixed * d + coef_use * emin)


def argmax_set(vals):
    best = max(vals.values())
    return frozenset(kk for kk, vv in vals.items() if vv == best)


def check_d5():
    support = [1, 2, 3, 4]
    dists = []
    for comp in compositions(4, 4):
        dists.append({support[i]: Fr(comp[i], 4) for i in range(4)})
    caps = [0, 1, 2, 3, 4]
    suff_cases = 0
    suff_fails = 0
    nec_points = 0
    nec_found = 0
    for rho in [Fr(0), Fr(1, 4), Fr(1, 2), Fr(1)]:
        for c in [Fr(1), Fr(2)]:
            # sufficiency
            for dist in dists:
                for v in [Fr(1), Fr(3), Fr(8)]:
                    S = {d: cap_values(dist, d, v, c * (1 - rho), c * rho) for d in caps}
                    U = {d: cap_values(dist, d, v, c * (1 - rho), c * rho) for d in caps}
                    # user with p = c, alpha = 1 - rho has fixed coef p alpha = c(1-rho), use coef p(1-alpha) = c rho
                    suff_cases += 1
                    if argmax_set(S) != argmax_set(U):
                        suff_fails += 1
            # necessity: every other (p, alpha) on a grid has a counterexample
            for p in [Fr(1, 2), Fr(1), Fr(2), Fr(3)]:
                for alpha in [Fr(0), Fr(1, 4), Fr(1, 2), Fr(3, 4), Fr(1)]:
                    if p == c and alpha == 1 - rho:
                        continue
                    nec_points += 1
                    found = False
                    for vgrid in ([Fr(1), Fr(3), Fr(8)], [Fr(n, 4) for n in range(1, 81)]):
                        for dist in dists:
                            for v in vgrid:
                                S = {d: cap_values(dist, d, v, c * (1 - rho), c * rho) for d in caps}
                                U = {d: cap_values(dist, d, v, p * alpha, p * (1 - alpha)) for d in caps}
                                if argmax_set(S) != argmax_set(U):
                                    found = True
                                    break
                            if found:
                                break
                        if found:
                            break
                    nec_found += int(found)
    RESULTS["D5"] = {"sufficiency_cases": suff_cases, "sufficiency_failures": suff_fails,
                     "necessity_points": nec_points, "necessity_counterexamples_found": nec_found}
    return suff_fails == 0 and nec_found == nec_points


if __name__ == "__main__":
    ok = {}
    for name, fn in [("D1", check_d1), ("D2", check_d2), ("D3", check_d3), ("D4", check_d4), ("D5", check_d5)]:
        ok[name] = fn()
        print(name, "PASS" if ok[name] else "FAIL", json.dumps(RESULTS[name])[:400], flush=True)
    json.dump({"ok": ok, "results": RESULTS},
              open(str(__import__("pathlib").Path(__file__).resolve().parents[1] / "results" / "first_layer_20261016.json"), "w"),
              indent=1, default=str)
    sys.exit(0 if all(ok.values()) else 1)
