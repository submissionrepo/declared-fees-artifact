"""Exact check D7 (2026-10-16): Proposition 5 (ordering neutrality) of
an earlier form of the theory section 5b.

(a) menu M with c = p t: firm used pi p t >= (1 - rho) p t + s rho p t and soft
    used pi p t + k >= 0, for all pi >= 1, rho, s in [0, 1], k >= 0: sympy proof
    of nonnegativity on the box plus exact grid.
(b) Savage-form payment with expected cost K: used minus unused payment equals
    K'(q_hat) + pi p t (sympy identity); for Brier-type K = lam q (1 - q) the
    rule is ordering neutral at every report iff lam <= (pi - s rho) p t (exact
    grid over lam, pi, rho, s and reports q_hat).
"""
import json
import sys
from fractions import Fraction as Fr

import sympy as sp

res = {}

# (a)
pi, rho, s, p, t, k = sp.symbols("pi rho s p t k", real=True)
firm_gap = sp.expand(pi * p * t - ((1 - rho) * p * t + s * rho * p * t))
# rewrite as p t [(pi - 1) + rho (1 - s)] which is >= 0 on pi >= 1, rho, s in [0,1], p, t >= 0
assert sp.simplify(firm_gap - p * t * ((pi - 1) + rho * (1 - s))) == 0
res["a_identity"] = "pi p t - ((1-rho) p t + s rho p t) = p t [(pi - 1) + rho (1 - s)]"
cases = fails = 0
for piv in [Fr(1), Fr(6, 5), Fr(5), Fr(16)]:
    for rv in [Fr(0), Fr(1, 4), Fr(1, 2), Fr(1)]:
        for sv in [Fr(0), Fr(1, 2), Fr(1)]:
            for kv in [Fr(0), Fr(1, 2), Fr(3)]:
                for pv, tv in [(Fr(1), Fr(1)), (Fr(2), Fr(3, 2))]:
                    cases += 1
                    if piv * pv * tv < (1 - rv) * pv * tv + sv * rv * pv * tv or piv * pv * tv + kv < 0:
                        fails += 1
res["a_grid"] = {"cases": cases, "failures": fails}

# (b) identity
qh, y = sp.symbols("qhat y", real=True)
K = sp.Function("K")
pay = K(qh) + sp.diff(K(qh), qh) * (y - qh) + pi * p * t * y
diff = sp.simplify(pay.subs(y, 1) - pay.subs(y, 0))
assert sp.simplify(diff - (sp.diff(K(qh), qh) + pi * p * t)) == 0
res["b_identity"] = str(diff)

# (b) Brier grid: neutral at every report iff lam <= (pi - s rho) p t
cases_b = fails_b = 0
for lam in [Fr(i, 4) for i in range(0, 41)]:
    for piv in [Fr(1), Fr(5, 4), Fr(2), Fr(5)]:
        for rv in [Fr(0), Fr(1, 2), Fr(1)]:
            for sv in [Fr(0), Fr(1, 2), Fr(1)]:
                pv = tv = Fr(1)
                neutral_all = True
                for j in range(0, 49):
                    q = Fr(j, 48)
                    Kp = lam * (1 - 2 * q)            # derivative of lam q (1 - q)
                    used = lam * q * (1 - q) + Kp * (1 - q) + piv * pv * tv
                    unused = lam * q * (1 - q) - Kp * q
                    if used < unused + sv * rv * pv * tv:
                        neutral_all = False
                predicted = lam <= (piv - sv * rv) * pv * tv
                cases_b += 1
                if neutral_all != predicted:
                    fails_b += 1
res["b_brier_grid"] = {"cases": cases_b, "failures": fails_b}
print(json.dumps(res))
json.dump(res, open(str(__import__("pathlib").Path(__file__).resolve().parents[1] / "results" / "first_layer_d7_20261016.json"), "w"))
sys.exit(0 if fails == 0 and fails_b == 0 else 1)
