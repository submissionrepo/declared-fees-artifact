"""Exact checks for the statements as the paper states them (2026-11-01).

The paper tightens the v1 theory (an earlier form of the theory) in four ways:
the unused firm fee scales with the bid (c = pi p t), the conflict premium is burned,
each branch has its own value, and a new proposition treats the posted premium.  All
arithmetic is exact.  Finite checks certify the finite statements listed; the general
statements rest on the proofs in the paper.

P1  Theorem 4.2: threshold with f_n = alpha p t; omitted region at alpha_min; one-class
    placement cost against the other placement, with the cost r of an unused soft declaration.
P2  Theorem 5.2 at u = 0: joint use distributions, per-branch values at the weak and at the
    strict branch margin, every vector in {omit, firm, soft}^m.
P2b Theorem 5.2 with a charge u on an unused soft declaration: soft against omitting, the
    object-by-object split of every full declaration, the threshold in class.
P3  Corollary 5.3: min-sum against all-firm and all-soft.
P4  The bound after Corollary 5.3: estimation error and stale posted terms, with r.
P5  Theorem 6.5(a): per-unit price of occupying.
P6  Proposition 5.4(a): ordering neutrality with c = pi p t, firm and soft objects.
P7  Proposition 5.5: stationary premium example; damped map slope bound.
P8  Theorem 6.2: shills under pay-what-you-count, premium burned or partly retained,
    horizon Lambda; identity for next-block revenue.
P9  Proposition 7.1: the two-point instance of the necessity proof.
P10 Ethereum access-list thresholds from the posted gas schedules.
P11 Proposition 5.4(d): what a scheduler earns across a route with one firm and one soft object.
P12 Theorem 6.4 with r: cost matching forces b0 = r, b1 = k; the omission threshold at u = r.
P13 Theorem 5.6: random rules with several classes; the drop region, the unpaid cost, and the trade-off.
P14 Proposition 5.7: what a producer gains from running a soft transaction at its rank rather than last, and the class a
    transaction picks against a producer that places it last.
P15 Theorem 6.4: every two-class rule on a grid of fees and shares has the four goals exactly when it is the menu with everything
    beyond the usage fee burned and the usage share below the shill bound.
P16 Theorem 6.5: per-unit price of each lock under any key split and priority, what a scheduler gets back, the sustained
    cost against the exact price path, the most blocks a budget buys; a soft read against omitting.
P17 Proposition 6.6: transactions and the scheduler as one party with any transfers: what a held unit burns, the party as a lone
    transaction with a higher value and a lower revert charge, what a moved bid saves, and running a soft transaction at its rank.
"""
import itertools
import json
import random
import sys
from fractions import Fraction as Fr
from pathlib import Path

import sympy as sp

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "results" / "first_layer_paper_20261101.json"
RESULTS = {}


def compositions(total, parts):
    if parts == 1:
        yield (total,)
        return
    for first in range(total + 1):
        for rest in compositions(total - first, parts - 1):
            yield (first,) + rest


# ------------------------------------------------------------------ P1
def check_p1():
    cases = fails = 0
    p, t = Fr(1), Fr(1)
    for gamma in [Fr(1, 4), Fr(1, 2), Fr(2, 3)]:
        for eta in [Fr(1, 8), Fr(1, 4)]:
            for pi_o in [Fr(6, 5), Fr(5), Fr(16)]:
                amin = pi_o * eta * gamma / (1 - gamma)
                fn = amin * p * t
                for x in [Fr(1, 10), Fr(1), Fr(5)]:
                    for kbar in [Fr(0), Fr(1, 2), Fr(1)]:
                        qstar = fn / (fn + x + kbar)
                        for q, expect_omit in [(qstar / 2, True), ((qstar + 1) / 2, False)]:
                            declare_minus_omit = q * (x + kbar) - (1 - q) * fn
                            cases += 1
                            if (declare_minus_omit < 0) != expect_omit:
                                fails += 1
    # part (c): a feasible alpha <= 1 exists iff pi eta gamma / (1 - gamma) <= 1
    assert Fr(16) * Fr(1, 8) * Fr(1, 2) / Fr(1, 2) == 2
    # part (d): each placement is the costlier one on one side of q_L
    place_cases = place_fails = 0
    for cp in [Fr(1, 2), Fr(1), Fr(3)]:
        for k in [Fr(1, 4), Fr(1), Fr(5)]:
            for r in [Fr(0), cp / 4, cp / 2, cp]:
                qL = (cp - r) / (cp - r + k)
                for num in range(0, 25):
                    q = Fr(num, 24)
                    firm, soft = (1 - q) * cp, q * k + (1 - q) * r
                    place_cases += 1
                    ok = (firm > soft) == (q < qL) and (firm < soft) == (q > qL) and (firm == soft) == (q == qL or q == 1 and qL == 1)
                    place_fails += not ok
    RESULTS["P1"] = {"threshold_cases": cases, "threshold_failures": fails,
                     "placement_cases": place_cases, "placement_failures": place_fails}
    return fails == 0 and place_fails == 0


# ------------------------------------------------------------------ P2
def payoff(dist, values, decl, kappa, usage, cp, k):
    m = len(decl)
    total = Fr(0)
    for X, pr in dist.items():
        if pr == 0:
            continue
        if any(o in X and decl[o] == "N" for o in range(m)):
            total += pr * (-kappa)
            continue
        fee = Fr(0)
        for o in range(m):
            if o in X:
                fee += usage[o] + (k[o] if decl[o] == "S" else 0)
            elif decl[o] == "F":
                fee += cp[o]
        total += pr * (values[X] - fee)
    return total


def check_p2():
    cases = fails = strict_cases = 0
    first = []
    for m, denom in [(2, 4), (3, 3)]:
        subsets = [frozenset(s) for r in range(m + 1) for s in itertools.combinations(range(m), r)]
        dists = [{subsets[i]: Fr(comp[i], denom) for i in range(len(subsets))}
                 for comp in compositions(denom, len(subsets))]
        for dist in dists:
            qo = [sum(pr for X, pr in dist.items() if o in X) for o in range(m)]
            for rho, pi, pval, kval in itertools.product([Fr(0), Fr(1, 2)], [Fr(1), Fr(5, 2)], [Fr(1)], [Fr(1, 2), Fr(2)]):
                t = Fr(1)
                usage = [pi * pval * t] * m
                c = [pi * pval * t] * m                     # c = pi p t
                cp = [(1 - rho) * ci for ci in c]
                k = [kval] + [kval * 2] * (m - 1)
                kappa = Fr(1, 2)
                top = {X: sum(usage[o] + k[o] for o in X) + sum(cp[o] for o in range(m) if o not in X)
                       for X in subsets}
                for margin in [Fr(0), Fr(1, 2)]:
                    # each branch gets its own value, at or above the branch margin
                    values = {X: top[X] - kappa + margin + Fr(len(X), 7) * (margin > 0) for X in subsets}
                    best_val, best = None, []
                    for decl in itertools.product("NFS", repeat=m):
                        eu = payoff(dist, values, decl, kappa, usage, cp, k)
                        if best_val is None or eu > best_val:
                            best_val, best = eu, [decl]
                        elif eu == best_val:
                            best.append(decl)
                    thr = tuple(("S" if qo[o] == 0 else ("F" if (1 - qo[o]) * cp[o] <= qo[o] * k[o] else "S"))
                                for o in range(m))
                    eu_thr = payoff(dist, values, thr, kappa, usage, cp, k)
                    cases += 1
                    ok = eu_thr == best_val
                    if margin > 0:
                        strict_cases += 1
                        for decl in best:
                            if any(decl[o] == "N" and qo[o] > 0 for o in range(m)):
                                ok = False
                    # additive decomposition and cost equality
                    base = sum(pr * (values[X] - sum(usage[o] for o in X)) for X, pr in dist.items())
                    mincost = sum(min((1 - qo[o]) * cp[o], qo[o] * k[o]) for o in range(m))
                    if base - mincost != eu_thr:
                        ok = False
                    if not ok:
                        fails += 1
                        if len(first) < 3:
                            first.append({"m": m, "rho": str(rho), "pi": str(pi), "k": str(kval), "margin": str(margin)})
    RESULTS["P2"] = {"cases": cases, "strict_margin_cases": strict_cases, "failures": fails, "first": first}
    return fails == 0


# ------------------------------------------------------------------ P2b
def check_p2b():
    rng = random.Random(3)
    soft_cases = soft_fails = split_cases = split_fails = thr_cases = thr_fails = 0
    m = 3
    subsets = [frozenset(s) for n in range(m + 1) for s in itertools.combinations(range(m), n)]
    for _ in range(4000):
        w = [Fr(rng.randint(0, 6)) for _ in subsets]
        tot = sum(w)
        if tot == 0:
            continue
        pr = {X: wi / tot for X, wi in zip(subsets, w)}
        usage = [Fr(rng.randint(1, 3)) for _ in range(m)]
        cp = [Fr(rng.randint(1, 3)) for _ in range(m)]
        k = [Fr(rng.randint(1, 3), 2) for _ in range(m)]
        u = [Fr(rng.randint(0, 2), 2) for _ in range(m)]
        kappa = Fr(rng.randint(0, 2))
        v = {X: Fr(rng.randint(0, 20)) for X in subsets}

        def fee(X, cls):
            total = Fr(0)
            for j in range(m):
                if cls[j] == "N":
                    continue
                if j in X:
                    total += usage[j] + (k[j] if cls[j] == "S" else 0)
                else:
                    total += cp[j] if cls[j] == "F" else u[j]
            return total

        def value(cls):
            total = Fr(0)
            for X, p in pr.items():
                if any(j in X and cls[j] == "N" for j in range(m)):
                    total -= p * kappa
                else:
                    total += p * (v[X] - fee(X, cls))
            return total

        # (i) soft against omitting one object, the others declared
        cls = [rng.choice("FS") for _ in range(m)]
        o = rng.randrange(m)
        with_soft, omit = list(cls), list(cls)
        with_soft[o], omit[o] = "S", "N"
        q = sum(p for X, p in pr.items() if o in X)
        if q > 0:
            x = sum(p * (v[X] - fee(X, with_soft)) for X, p in pr.items() if o in X) / q
            soft_cases += 1
            soft_fails += value(with_soft) - value(omit) != q * (x + kappa) - (1 - q) * u[o]
        # (ii), (iii) every full declaration splits object by object, and the threshold picks the best
        qs = [sum(p for X, p in pr.items() if j in X) for j in range(m)]
        base = sum(p * (v[X] - sum(usage[j] for j in X)) for X, p in pr.items())
        best = None
        for full in itertools.product("FS", repeat=m):
            cost = sum((1 - qs[j]) * cp[j] if full[j] == "F" else qs[j] * k[j] + (1 - qs[j]) * u[j] for j in range(m))
            split_cases += 1
            split_fails += value(list(full)) != base - cost
            best = value(list(full)) if best is None or value(list(full)) > best else best
        if all(cp[j] >= u[j] for j in range(m)):
            pick = ["F" if qs[j] >= (cp[j] - u[j]) / (cp[j] - u[j] + k[j]) else "S" for j in range(m)]
            thr_cases += 1
            thr_fails += value(pick) != best
    RESULTS["P2b"] = {"soft_against_omit_cases": soft_cases, "soft_against_omit_failures": soft_fails,
                      "split_cases": split_cases, "split_failures": split_fails,
                      "threshold_cases": thr_cases, "threshold_failures": thr_fails}
    return soft_fails == 0 and split_fails == 0 and thr_fails == 0


# ------------------------------------------------------------------ P3
def check_p3():
    cases = fails = 0
    grid = [Fr(n, 8) for n in range(0, 9)]
    for qs in itertools.product(grid, repeat=2):
        for cp, k in itertools.product([Fr(1, 2), Fr(2)], [Fr(1, 2), Fr(3)]):
            firm = [(1 - q) * cp for q in qs]
            soft = [q * k for q in qs]
            menu = [min(a, b) for a, b in zip(firm, soft)]
            both_sides = any(a < b for a, b in zip(firm, soft)) and any(b < a for a, b in zip(firm, soft))
            cases += 1
            ok = sum(menu) <= min(sum(firm), sum(soft))
            if both_sides:
                ok = ok and sum(menu) < min(sum(firm), sum(soft))
            fails += not ok
    RESULTS["P3"] = {"cases": cases, "failures": fails}
    return fails == 0


# ------------------------------------------------------------------ P4
def check_p4():
    cases = fails = attained = 0
    grid = [Fr(n, 6) for n in range(0, 7)]
    for q in grid:
        for cp, k in itertools.product([Fr(1, 2), Fr(1), Fr(3)], repeat=2):
            for chat, khat in itertools.product([Fr(1, 2), Fr(1), Fr(3)], repeat=2):
                for r, rhat in itertools.product([Fr(0), Fr(1, 2)], repeat=2):
                    firm_true, soft_true = (1 - q) * cp, q * k + (1 - q) * r
                    pick_firm = (1 - q) * chat <= q * khat + (1 - q) * rhat
                    regret = (firm_true if pick_firm else soft_true) - min(firm_true, soft_true)
                    bound = (1 - q) * (abs(cp - chat) + abs(r - rhat)) + q * abs(k - khat)
                    cases += 1
                    if regret > bound:
                        fails += 1
                    if regret == bound and regret > 0:
                        attained += 1
    est_cases = est_fails = same_side_fails = 0
    for cp, k, r in itertools.product([Fr(1), Fr(3)], [Fr(1, 2), Fr(2)], [Fr(0), Fr(1, 2), Fr(1)]):
        qL = (cp - r) / (cp - r + k)
        for q, qhat in itertools.product(grid, repeat=2):
            firm, soft = (lambda z: (1 - z) * cp), (lambda z: z * k + (1 - z) * r)
            regret = (firm(q) if firm(qhat) <= soft(qhat) else soft(q)) - min(firm(q), soft(q))
            est_cases += 1
            est_fails += regret > abs(q - qhat) * (cp - r + k)
            same_side_fails += ((q - qL) * (qhat - qL) > 0) and regret != 0
    RESULTS["P4"] = {"stale_cases": cases, "stale_failures": fails, "bound_attained_cases": attained,
                     "estimation_cases": est_cases, "estimation_failures": est_fails, "same_side_failures": same_side_fails}
    return fails == 0 and est_fails == 0 and same_side_fails == 0


# ------------------------------------------------------------------ P5, P6
def check_p5_p6():
    pi, p, t, rho, s = sp.symbols("pi p t rho s")
    occupy = sp.simplify((1 - rho) * pi * p * t / ((1 - rho) * t))
    assert occupy == pi * p
    gap = sp.expand(pi * p * t - ((1 - rho) * pi * p * t + s * rho * p * t))
    assert sp.simplify(gap - rho * p * t * (pi - s)) == 0
    gamma = sp.symbols("gamma")
    assert sp.simplify(gamma * pi * p * t - gamma * s * p * t - gamma * p * t * (pi - s)) == 0
    # the fee on an unused lock is burned, so a firm object keeps gamma pi p t used and gamma s rho p t unused
    assert sp.simplify(gamma * pi * p * t - gamma * s * rho * p * t - gamma * p * t * (pi - s * rho)) == 0
    cases = fails = 0
    for piv, rv, sv in itertools.product([Fr(1), Fr(5, 4), Fr(3)], [Fr(n, 4) for n in range(5)], [Fr(n, 4) for n in range(5)]):
        cases += 1
        fails += not (piv >= (1 - rv) * piv + sv * rv)      # with a share kept on the unused fee
        fails += not (piv >= sv * rv)                        # with it burned
        fails += not (piv >= sv)                             # on a soft object
    RESULTS["P5"] = {"identity": "unit occupancy price = pi p"}
    RESULTS["P6"] = {"identity": "firm, burned: gamma p t (pi - s rho); kept: pi p t - (1-rho) pi p t - s rho p t = rho p t (pi - s); soft: gamma p t (pi - s)", "cases": cases, "failures": fails}
    return fails == 0


# ------------------------------------------------------------------ P7
def check_p7():
    k = sp.symbols("k")
    a, cp = sp.Integer(36), sp.Integer(1)
    # uniform q on [0,1], unit mass: soft use mass q_L^2 / 2; premium a * s
    T = a * sp.Rational(1, 2) * (cp / (cp + k)) ** 2
    assert sp.simplify(T.subs(k, 2) - 2) == 0
    poly = sp.Poly(sp.expand(k * (1 + k) ** 2 - 18), k)
    assert sp.factor(poly.as_expr()) == (k - 2) * (k ** 2 + 4 * k + 9)
    assert sp.discriminant(k ** 2 + 4 * k + 9, k) < 0
    slope = sp.diff(T, k).subs(k, 2)
    assert slope == sp.Rational(-4, 3)
    # direct posting moves away from the fixed point: exact iteration from k = 2 + 1/100
    x = Fr(201, 100)
    dist = [abs(x - 2)]
    for _ in range(6):
        x = Fr(18) / (1 + x) ** 2
        x = x.limit_denominator(10 ** 12)
        dist.append(abs(x - 2))
    grows = all(dist[i + 1] > dist[i] for i in range(len(dist) - 1))
    # a two-cycle exists: k -> T(T(k)) has a root pair away from 2 (exact bracketing on rationals)
    TT = lambda v: Fr(18) / (1 + Fr(18) / (1 + v) ** 2) ** 2
    lo, hi = Fr(1, 100), Fr(1)
    bracket = (TT(lo) - lo > 0 or TT(lo) - lo < 0) and (TT(lo) - lo) * (TT(hi) - hi) < 0
    # damped map: slope bound 1 - theta (1 + L) .. 1 - theta; at theta = 1/8, L = 4/3
    theta = Fr(1, 8)
    damped = 1 - theta * (1 + Fr(4, 3))
    assert damped == Fr(17, 24)
    # Lipschitz constant of T on k >= 0 is a / cp = 36, so theta < 2/37 is enough globally
    Lip = sp.Abs(sp.diff(T, k).subs(k, 0))
    assert Lip == 36
    y = Fr(10)
    for _ in range(200):
        y = ((1 - Fr(1, 20)) * y + Fr(1, 20) * Fr(18) / (1 + y) ** 2).limit_denominator(10 ** 15)
    converged = abs(y - 2) < Fr(1, 10 ** 3)
    RESULTS["P7"] = {"fixed_point": 2, "slope": "-4/3", "direct_distance_grows": grows,
                     "two_cycle_bracket": bool(bracket), "theta_1_20_from_10_200_steps_within_1e-3": converged}
    return grows and bracket and converged


# ------------------------------------------------------------------ P8
def check_p8():
    gamma, eta, pio, p, w, U, gk, gp, S, Lam = sp.symbols("gamma eta pi_o p w U gamma_k g S Lambda")
    # next-block revenue under pay-what-you-count: every counted unit pays pi_o times the price
    revenue = gamma * pio * p * (1 + eta * w / U) * U
    assert sp.simplify(sp.diff(revenue, w) - gamma * eta * pio * p) == 0
    cases = fails = 0
    pv = Fr(1)
    for g, e, po, rho, lam, gkv, gs in itertools.product(
            [Fr(n, 12) for n in range(1, 12)], [Fr(1, 8), Fr(1, 4)], [Fr(6, 5), Fr(5), Fr(16)],
            [Fr(0), Fr(1, 3), Fr(1, 2)], [Fr(1), Fr(3)], [Fr(0), Fr(1, 2)], [Fr(0), Fr(1, 4)]):
        predicted_ok = g * e * po * lam * pv + gkv * gs <= (1 - g) * pv
        profitable = False
        for cls, used, ts, pis, kk in itertools.product(["F", "S"], [0, 1], [Fr(1), Fr(2)], [Fr(1), Fr(2)], [Fr(0), Fr(1, 2)]):
            if used:
                w_ = ts
                fee = pis * pv * ts
                premium = kk if cls == "S" else Fr(0)
            else:
                w_ = (1 - rho) * ts if cls == "F" else Fr(0)
                fee = (1 - rho) * pis * pv * ts if cls == "F" else Fr(0)
                premium = Fr(0)
            gain = (g * e * po * lam * pv + gkv * gs) * w_
            # what the scheduler keeps of the fee: its share of a usage fee, nothing of the fee on an unused lock
            cost = ((1 - g) * fee if used else fee) + (1 - gkv) * premium
            if gain > cost:
                profitable = True
        cases += 1
        if profitable == predicted_ok:
            fails += 1
    RESULTS["P8"] = {"revenue_identity": "d revenue / d w = gamma eta pi_o p", "cases": cases, "failures": fails}
    return fails == 0


# ------------------------------------------------------------------ P9
def check_p9():
    y, v, c, p, rho, alpha = sp.symbols("y v c p rho alpha")
    dS = v * (1 - y) - c * (1 - rho) - c * rho * (1 - y)
    dU = v * (1 - y) - p * alpha - p * (1 - alpha) * (1 - y)
    assert sp.simplify((dU - dS) - ((c - p) + y * (p * (1 - alpha) - c * rho))) == 0

    def caps(val, yv, a, b):
        """Payoff for caps 0, 1, 2 with need 1 w.p. yv and 2 otherwise; fixed coef a, use coef b."""
        return {0: Fr(0),
                1: val * yv - a - b,
                2: val - 2 * a - b * (yv + 2 * (1 - yv))}

    points = found = 0
    for rv, cv in itertools.product([Fr(0), Fr(1, 4), Fr(1, 2), Fr(1)], [Fr(1), Fr(2)]):
        for pv, av in itertools.product([Fr(1, 2), Fr(1), Fr(2), Fr(3)], [Fr(0), Fr(1, 4), Fr(1, 2), Fr(3, 4), Fr(1)]):
            if pv == cv and av == 1 - rv:
                continue
            points += 1
            if rv == 1 and av == 0:
                # both fees stop charging the reservation: a single need and v between c and p separates them
                val = (cv + pv) / 2
                found += (val - cv > 0) != (val - pv > 0)
                continue
            for yv in [Fr(99, 100), Fr(49, 50), Fr(97, 100)]:
                D = (cv - pv) + yv * (pv * (1 - av) - cv * rv)
                if D == 0:
                    continue
                # value that puts the efficient increment and the user's increment on opposite sides of zero
                cost_s = cv * (1 - rv) + cv * rv * (1 - yv)
                cost_u = pv * av + pv * (1 - av) * (1 - yv)
                val = (cost_s + cost_u) / 2 / (1 - yv)
                S = caps(val, yv, cv * (1 - rv), cv * rv)
                U = caps(val, yv, pv * av, pv * (1 - av))
                if S[2] - S[1] != 0 and (S[2] > S[1]) != (U[2] > U[1]) and max(S.values()) > 0 and max(U.values()) > 0:
                    found += 1
                    break
    RESULTS["P9"] = {"identity": "dU - dS = (c-p) + y (p(1-alpha) - c rho)", "points": points, "instance_found": found}
    return points == found


# ------------------------------------------------------------------ P10
def check_p10():
    table = {}
    for name, decl, cold, warm, data in [("EIP-2930 address", 2400, 2600, 100, 0), ("EIP-2930 key", 1900, 2100, 100, 0),
                                         ("EIP-8038 address", 2900, 3000, 100, 0), ("EIP-8038 key", 2000, 2100, 100, 0),
                                         ("EIP-8038+7981 address", 2900, 3000, 100, 1280),
                                         ("EIP-8038+7981 key", 2000, 2100, 100, 2048)]:
        total = decl + data
        table[name] = str(Fr(total, cold - warm))
    assert table["EIP-2930 address"] == "24/25" and table["EIP-2930 key"] == "19/20"
    assert table["EIP-8038 address"] == "1" and table["EIP-8038 key"] == "1"
    assert Fr(table["EIP-8038+7981 address"]) > 1 and Fr(table["EIP-8038+7981 key"]) > 1
    RESULTS["P10"] = table
    return True


# ------------------------------------------------------------------ P11
def check_p11():
    pi, pa, pb, t, rho, sig, g, gp, p = sp.symbols("pi p_A p_B t rho sigma gamma gamma_prime p")
    on_a = g * pi * pa * t + g * sig * pb * t
    on_b = gp * (1 - rho) * pi * pa * t + g * pi * pb * t + g * sig * rho * pa * t
    gap = sp.expand(on_b - on_a)
    assert sp.simplify(gap.subs({pa: p, pb: p}) - (1 - rho) * p * t * (gp * pi - g * sig)) == 0
    assert sp.simplify(gap.subs(gp, g) - g * t * (pi - sig) * (pb - rho * pa)) == 0
    cases = fails = 0
    for gv, gpv, piv, rv in itertools.product([Fr(1, 4), Fr(1, 2), Fr(2, 3)], [Fr(0), Fr(1, 4), Fr(1, 2), Fr(2, 3)],
                                              [Fr(1), Fr(5, 4), Fr(3)], [Fr(0), Fr(1, 4), Fr(1, 2), Fr(3, 4)]):
        gains = []
        for sv in [Fr(n, 4) for n in range(5)]:
            a = gv * piv + gv * sv
            b = gpv * (1 - rv) * piv + gv * piv + gv * sv * rv
            gains.append(b - a)
            cases += 1
            fails += (b - a) != (1 - rv) * (gpv * piv - gv * sv)
        # no gain at every resale share exactly when the scheduler keeps none of the fee on unused firm objects
        fails += (all(x <= 0 for x in gains)) != (gpv == 0)
    RESULTS["P11"] = {"identity": "on B - on A = (1-rho) p t (gamma' pi - gamma sigma) at equal prices", "cases": cases, "failures": fails}
    return fails == 0


# ------------------------------------------------------------------ P12
def check_p12():
    q, b0, b1, k, r, x = sp.symbols("q b0 b1 k r x")
    expr = sp.expand(q * b1 + (1 - q) * b0 - (q * k + (1 - q) * r))
    sol = sp.solve(sp.Poly(expr, q).coeffs(), [b0, b1], dict=True)
    assert sol == [{b0: r, b1: k}]
    cases = fails = 0
    for rv, xk in itertools.product([Fr(1, 10), Fr(1, 2), Fr(1)], [Fr(1, 2), Fr(1), Fr(5)]):
        qstar = rv / (rv + xk)
        for qv in [Fr(n, 40) for n in range(41)]:
            cases += 1
            gain = qv * xk - (1 - qv) * rv
            fails += (gain >= 0) != (qv >= qstar)
    RESULTS["P12"] = {"matching": "b0 = r, b1 = k", "threshold_cases": cases, "failures": fails}
    return fails == 0


# ------------------------------------------------------------------ P13
def check_p13():
    rng = random.Random(3)
    drop_cases = drop_fails = unpaid_cases = unpaid_fails = trade_cases = trade_fails = 0
    for _ in range(20000):
        n = rng.randint(1, 4)
        a = [Fr(rng.randint(0, 8), 4) for _ in range(n)]       # charge if unused, by class
        b = [Fr(rng.randint(0, 8), 4) for _ in range(n)]       # charge if used, by class
        cost = [Fr(rng.randint(0, 8), 4) for _ in range(n)]    # what an unused declaration in the class costs the chain
        y = Fr(rng.randint(0, 12), 2)                          # value of the branch, net of everything else
        kbar = Fr(rng.randint(0, 4), 2)
        u, rstar = min(a), min(cost)
        x = y - min(b)                                         # largest net value of the branch across classes
        if x + kbar <= 0:
            continue
        floor = u / (u + x + kbar)
        for qn in range(1, 41):
            q = Fr(qn, 40)
            if q >= floor:
                continue
            drop_cases += 1
            drop_fails += any(q * (y - bi) - (1 - q) * ai >= -q * kbar for ai, bi in zip(a, b))
        for ai, ci in zip(a, cost):
            if ai == u:
                unpaid_cases += 1
                unpaid_fails += ci - ai < rstar - u
        # no drops needs a class with no charge, which leaves at least r* unpaid; paying every cost means u >= r*
        trade_cases += 1
        if u == 0:
            trade_fails += min(c for ai, c in zip(a, cost) if ai == 0) < rstar
        if all(ai >= ci for ai, ci in zip(a, cost)):
            trade_fails += u < rstar
            if rstar > 0:
                trade_fails += floor < rstar / (rstar + x + kbar)
    RESULTS["P13"] = {"drop_cases": drop_cases, "drop_failures": drop_fails, "unpaid_cases": unpaid_cases,
                      "unpaid_failures": unpaid_fails, "trade_cases": trade_cases, "trade_failures": trade_fails}
    return drop_fails == 0 and unpaid_fails == 0 and trade_fails == 0


# ------------------------------------------------------------------ P14
def check_p14():
    q, qp, g, pi, sig, p, t, gk, k, c, u, V = sp.symbols("q q_prime gamma pi sigma p t gamma_k k c u V")
    rank = q * (g * pi * p * t + gk * k - k) + (1 - q) * g * sig * p * t
    last = qp * (g * pi * p * t + gk * k) + (1 - qp) * g * sig * p * t
    claim = (q - qp) * (g * (pi - sig) * p * t + gk * k) - q * k
    assert sp.simplify(rank - last - claim) == 0
    # with use independent of position the premium share drops out
    assert sp.simplify(claim.subs(qp, q) + q * k) == 0
    firm = q * V - (1 - q) * c
    soft_last = qp * (V - k) - (1 - qp) * u
    margin = (q - qp) * V + qp * k + (1 - qp) * u - (1 - q) * c
    assert sp.simplify(firm - soft_last - margin) == 0
    # at q' = q this is the comparison of Theorem 5.2, and at q' = 0 a soft declaration is worth -u against omitting
    assert sp.simplify(margin.subs(qp, q) - (q * k + (1 - q) * u - (1 - q) * c)) == 0
    assert sp.simplify(soft_last.subs(qp, 0) + u) == 0
    cases = fails = 0
    grid = [Fr(n, 8) for n in range(9)]
    for qv, cv, vv, uv, kv in itertools.product(grid, [Fr(1, 2), Fr(1), Fr(2)], [Fr(1, 2), Fr(1), Fr(5)], [Fr(0), Fr(1, 4)], [Fr(1, 3), Fr(3)]):
        # a racer that wins only at its rank: its best response is firm or omit, by the threshold of one class with f_n = c'
        options = {"F": qv * vv - (1 - qv) * cv, "S": -uv, "N": Fr(0)}
        best = max(options.values())
        cases += 1
        fails += (options["F"] >= 0 and best == options["F"]) != (qv >= cv / (cv + vv))
    RESULTS["P14"] = {"identities": "rank - last; firm - soft last", "racer_cases": cases, "racer_failures": fails}
    return fails == 0


# ------------------------------------------------------------------ P15
def check_p15():
    # the route: A firm and B soft at equal prices, taking one of them
    pi, p, t, rho, sig, g, gu, gk, k, a0 = sp.symbols("pi p t rho sigma gamma gamma_u gamma_k k a0")
    on_a = g * pi * p * t + g * sig * p * t
    on_b = gu * a0 + g * pi * p * t + gk * k + g * sig * rho * p * t
    assert sp.simplify(on_b - on_a - (gu * a0 + gk * k - g * sig * (1 - rho) * p * t)) == 0
    cases = rule_cases = fails = 0
    pv, tv, kappa = Fr(1), Fr(1), Fr(1)
    grid_q = [Fr(n, 8) for n in range(9)]
    tiny = [Fr(1, 1000), Fr(1, 100)]
    sigmas = [Fr(n, 4) for n in range(5)]
    for rv, piv in itertools.product([Fr(0), Fr(1, 2)], [Fr(1), Fr(2)]):
        cp = (1 - rv) * piv * pv * tv
        kv = Fr(1, 2)
        usage = piv * pv * tv
        fees = [Fr(0), Fr(1, 4), kv, cp, 2 * cp]
        for a1, a0v, b1, b0 in itertools.product(fees, repeat=4):
            matching = all(q * a1 + (1 - q) * a0v == (1 - q) * cp and q * b1 + (1 - q) * b0 == q * kv for q in grid_q)
            # complete declaration on a low-use type whose branch is worth more than the highest fee
            x = usage + max(a1, b1) + 1
            complete = all(max(q * (x - usage - a1 + kappa) - (1 - q) * a0v, q * (x - usage - b1 + kappa) - (1 - q) * b0) >= 0 for q in tiny)
            for gv, guv, gkv, eta, pio in itertools.product([Fr(1, 4), Fr(1, 2), Fr(5, 6)], [Fr(0), Fr(1, 4)], [Fr(0), Fr(1, 4)], [Fr(1, 8)], [Fr(5), Fr(16)]):
                cases += 1
                # a shill at any priority and class, used or not: gain on next block's fees against what it loses
                shill_free = True
                for cls, used, pis in itertools.product("FS", (True, False), [Fr(1), Fr(2)]):
                    if used:
                        w = tv
                        lost = (1 - gv) * pis * pv * tv + (0 if cls == "F" else (1 - gkv) * b1) + (a1 if cls == "F" else 0)
                    elif cls == "F":
                        w = (1 - rv) * tv
                        lost = (1 - guv) * a0v * pis / piv
                    else:
                        w = Fr(0)
                        lost = b0
                    if gv * eta * pio * pv * w > lost:
                        shill_free = False
                neutral = all(guv * a0v + gkv * b1 + a1 * 0 - gv * s * (1 - rv) * pv * tv <= 0 for s in sigmas)
                has_goals = matching and complete and shill_free and neutral
                predicted = (a1 == 0 and a0v == cp and b1 == kv and b0 == 0 and guv == 0 and gkv == 0 and gv <= 1 / (1 + eta * pio))
                fails += has_goals != predicted
                rule_cases += predicted
    RESULTS["P15"] = {"route_identity": "on B - on A = gamma_u a0 + gamma_k k - gamma sigma (1 - rho) p t", "cases": cases, "rules_with_all_goals": rule_cases, "failures": fails}
    return fails == 0 and rule_cases > 0


# ------------------------------------------------------------------ P16
def check_p16():
    cases = fails = 0
    pv = Fr(3)
    for rv, piv, gv in itertools.product([Fr(0), Fr(1, 4), Fr(1, 2)], [Fr(1), Fr(2), Fr(5)], [Fr(0), Fr(1, 2)]):
        # any split of a hold across keys pays the same, at least p per unit, and a scheduler gets nothing back
        for parts in ([Fr(6)], [Fr(2), Fr(4)], [Fr(1), Fr(2), Fr(3)]):
            held = sum((1 - rv) * ti for ti in parts)
            for paid in (sum((1 - rv) * piv * pv * ti for ti in parts),):      # firm unused or firm read, same fee
                cases += 1
                fails += paid != piv * pv * held or paid < pv * held
            # a used hold pays the usage fee, of which a scheduler gets back its share
            used_paid = sum(piv * pv * ti for ti in parts)
            used_held = sum(parts)
            cases += 1
            fails += (1 - gv) * used_paid < (1 - gv) * pv * used_held
    # the sustained cost against the exact path, with other use at or above the target
    rng = random.Random(9)
    path_cases = path_fails = budget_cases = budget_fails = 0
    for _ in range(600):
        target, held, eta, p0 = Fr(rng.randint(4, 20)), Fr(rng.randint(1, 6)), Fr(1, rng.choice([8, 4, 2])), Fr(rng.randint(1, 5))
        g = eta * held / target
        p, paid = p0, Fr(0)
        for n in range(1, 25):
            paid += p * held
            bound = p0 * held * ((1 + g) ** n - 1) / g
            path_cases += 1
            path_fails += paid < bound
            other = target + Fr(rng.randint(0, 3))
            p = p * (1 + eta * (other + held - target) / target)
        # with other use exactly at the target the bound is attained
        p, paid = p0, Fr(0)
        for n in range(1, 25):
            paid += p * held
            path_cases += 1
            path_fails += paid != p0 * held * ((1 + g) ** n - 1) / g
            p = p * (1 + g)
        # a count at or above (1 + g) target, however it is reached: other use below the target and a larger hold
        big = target + Fr(rng.randint(1, 6))
        gen = eta * (big - target) / target
        p, paid = p0, Fr(0)
        for n in range(1, 25):
            paid += p * big
            path_cases += 1
            path_fails += paid < p0 * big * ((1 + gen) ** n - 1) / gen
            p = p * (1 + eta * (big + Fr(rng.randint(0, 3)) - target) / target)
        # the most blocks a budget buys
        budget = Fr(rng.randint(1, 2000))
        cost = lambda m: p0 * held * ((1 + g) ** m - 1) / g
        most = 0
        while cost(most + 1) <= budget:
            most += 1
        budget_cases += 1
        budget_fails += not (cost(most) <= budget < cost(most + 1))
    # a soft read pays nothing, so against omitting it gains q (x + kappa) >= 0 at every q: no read is dropped
    read_cases = read_fails = 0
    for qv, xk in itertools.product([Fr(n, 8) for n in range(9)], [Fr(0), Fr(1, 2), Fr(5)]):
        read_cases += 1
        read_fails += qv * xk < 0
    RESULTS["P16"] = {"hold_cases": cases, "hold_failures": fails, "path_cases": path_cases, "path_failures": path_fails,
                      "budget_cases": budget_cases, "budget_failures": budget_fails, "read_cases": read_cases, "read_failures": read_fails}
    return fails == 0 and path_fails == 0 and budget_fails == 0 and read_fails == 0


# ------------------------------------------------------------------ P17
def check_p17():
    # what a moved bid saves, and the sum of the gains from running at the rank (Proposition 5.7 at gamma_k = 0)
    g, pi, pip, p, t, rho, q, qp, V, k, u, sig = sp.symbols("gamma pi pi_prime p t rho q q_prime V k u sigma")
    burn_used = lambda b: (1 - g) * b * p * t
    burn_unused = lambda b: (1 - rho) * b * p * t
    assert sp.simplify(burn_used(pi) - burn_used(pip) - (1 - g) * (pi - pip) * p * t) == 0
    assert sp.simplify(burn_unused(pi) - burn_unused(pip) - (1 - rho) * (pi - pip) * p * t) == 0
    tx_gain = (q * (V - k) - (1 - q) * u) - (qp * (V - k) - (1 - qp) * u)
    producer_gain = (q * (g * pip * p * t - k) + (1 - q) * g * sig * p * t) - (qp * g * pip * p * t + (1 - qp) * g * sig * p * t)
    claim = (q - qp) * (V - k + u + g * (pip - sig) * p * t) - q * k
    assert sp.simplify(tx_gain + producer_gain - claim) == 0
    assert sp.simplify(claim.subs(qp, 0) - q * (V + u + g * (pip - sig) * p * t - 2 * k)) == 0

    # (a) a held unit, under any split across keys, priority and transfer
    rng = random.Random(17)
    hold_cases = hold_fails = 0
    pv = Fr(3)
    for rv, piv, gv in itertools.product([Fr(0), Fr(1, 4), Fr(1, 2)], [Fr(1), Fr(2), Fr(5)], [Fr(0), Fr(1, 4), Fr(1, 2)]):
        for parts in ([Fr(6)], [Fr(2), Fr(4)], [Fr(1), Fr(2), Fr(3)]):
            transfer = Fr(rng.randint(-20, 20), 3)
            # an unused or read-only lock: the transaction pays it all and the scheduler receives only the transfer
            held = sum((1 - rv) * ti for ti in parts)
            fee = sum((1 - rv) * piv * pv * ti for ti in parts)
            party = (-fee - transfer) + transfer
            hold_cases += 1
            hold_fails += -party != piv * pv * held or -party < pv * held
            # a write: the scheduler receives its share of the usage fee as well
            written = sum(parts)
            fee = sum(piv * pv * ti for ti in parts)
            party = (-fee - transfer) + (gv * fee + transfer)
            hold_cases += 1
            hold_fails += -party != (1 - gv) * piv * pv * written or -party < (1 - gv) * pv * written

    # (b) the party's payoff, from the two members' payoffs and transfers on every branch, against a lone transaction's
    party_cases = party_fails = class_cases = class_fails = 0
    m = 2
    subsets = [frozenset(s) for n in range(m + 1) for s in itertools.combinations(range(m), n)]
    for _ in range(3000):
        w = [Fr(rng.randint(0, 6)) for _ in subsets]
        if sum(w) == 0:
            continue
        pr = {X: wi / sum(w) for X, wi in zip(subsets, w)}
        gv = Fr(rng.randint(0, 4), 4)
        rv = Fr(rng.randint(0, 3), 4)
        posted = Fr(rng.randint(1, 5))
        tv = [Fr(rng.randint(1, 3)) for _ in range(m)]
        pv = [Fr(rng.randint(1, 3)) for _ in range(m)]
        usage = [posted * pv[j] * tv[j] for j in range(m)]
        cp = [(1 - rv) * usage[j] for j in range(m)]
        k = [Fr(rng.randint(1, 6), 2) for _ in range(m)]
        u = [Fr(rng.randint(0, 2), 4) for _ in range(m)]
        kappa = Fr(rng.randint(0, 4), 2)
        v = {X: Fr(rng.randint(0, 24)) for X in subsets}
        transfer = {X: Fr(rng.randint(-10, 10)) for X in subsets}

        def added(X, cls):
            total = Fr(0)
            for j in range(m):
                if j in X:
                    total += k[j] if cls[j] == "S" else 0
                elif cls[j] == "F":
                    total += cp[j]
                elif cls[j] == "S":
                    total += u[j]
            return total

        def reverts(X, cls):
            return any(j in X and cls[j] == "N" for j in range(m))

        def party_value(cls):
            total = Fr(0)
            for X, prob in pr.items():
                if reverts(X, cls):
                    tx = -kappa - transfer[X]
                    scheduler = gv * kappa + transfer[X]
                else:
                    use = sum(usage[j] for j in X)
                    tx = v[X] - use - added(X, cls) - transfer[X]
                    scheduler = gv * use + transfer[X]
                total += prob * (tx + scheduler)
            return total

        def lone_value(cls):
            total = Fr(0)
            for X, prob in pr.items():
                if reverts(X, cls):
                    total -= prob * (1 - gv) * kappa
                else:
                    use = sum(usage[j] for j in X)
                    total += prob * (v[X] + gv * use - use - added(X, cls))
            return total

        for cls in itertools.product("NFS", repeat=m):
            party_cases += 1
            party_fails += party_value(cls) != lone_value(cls)
        # the class on each object is the one with the lower cost, as in Theorem 5.2(ii), at the posted priority
        qo = [sum(prob for X, prob in pr.items() if j in X) for j in range(m)]
        full = list(itertools.product("FS", repeat=m))
        best = max(party_value(cls) for cls in full)
        base = sum(prob * (v[X] - (1 - gv) * sum(usage[j] for j in X)) for X, prob in pr.items())
        cost = sum(min((1 - qo[j]) * cp[j], qo[j] * k[j] + (1 - qo[j]) * u[j]) for j in range(m))
        class_cases += 1
        class_fails += best != base - cost

    # (c) running a soft transaction at its rank: direct payoffs, the condition, and a transfer that leaves both no worse
    rank_cases = rank_fails = 0
    for qv, qpv in itertools.combinations_with_replacement([Fr(n, 6) for n in range(7)], 2):
        low, high = qv, qpv                      # q' <= q
        for vv, kv, uv, gv, piv, sv in itertools.product([Fr(1, 2), Fr(2), Fr(7)], [Fr(1, 3), Fr(1), Fr(3)], [Fr(0), Fr(1, 4)], [Fr(0), Fr(1, 2)], [Fr(1), Fr(5)], [Fr(0), Fr(1)]):
            pv, tv = Fr(1), Fr(1)
            tx = (high * (vv - kv) - (1 - high) * uv) - (low * (vv - kv) - (1 - low) * uv)
            prod = (high * (gv * piv * pv * tv - kv) + (1 - high) * gv * sv * pv * tv) - (low * gv * piv * pv * tv + (1 - low) * gv * sv * pv * tv)
            joint = (high - low) * (vv - kv + uv + gv * (piv - sv) * pv * tv) - high * kv
            side = (tx - prod) / 2           # after this transfer both gain (tx + prod) / 2
            rank_cases += 1
            rank_fails += tx + prod != joint or ((tx - side >= 0 and prod + side >= 0) != (joint >= 0))
            if low == 0 and high > 0:
                rank_fails += (joint >= 0) != (vv + uv + gv * (piv - sv) * pv * tv >= 2 * kv)
    RESULTS["P17"] = {"hold_cases": hold_cases, "hold_failures": hold_fails, "party_cases": party_cases, "party_failures": party_fails,
                      "class_cases": class_cases, "class_failures": class_fails, "rank_cases": rank_cases, "rank_failures": rank_fails}
    return hold_fails == 0 and party_fails == 0 and class_fails == 0 and rank_fails == 0


if __name__ == "__main__":
    ok = {}
    for name, fn in [("P1", check_p1), ("P2", check_p2), ("P2b", check_p2b), ("P3", check_p3), ("P4", check_p4), ("P5P6", check_p5_p6),
                     ("P7", check_p7), ("P8", check_p8), ("P9", check_p9), ("P10", check_p10), ("P11", check_p11), ("P12", check_p12),
                     ("P13", check_p13), ("P14", check_p14), ("P15", check_p15), ("P16", check_p16), ("P17", check_p17)]:
        ok[name] = bool(fn())
        print(name, "PASS" if ok[name] else "FAIL", flush=True)
    print(json.dumps(RESULTS, indent=1, default=str))
    OUT.write_text(json.dumps({"ok": ok, "results": RESULTS}, indent=1, default=str), encoding="utf-8")
    sys.exit(0 if all(ok.values()) else 1)
