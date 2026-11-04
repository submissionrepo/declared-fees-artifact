"""Exact check D6 (2026-10-16): Proposition 4 (estimation error) of
an earlier form of the theory section 5b.

Claim: choosing the class by q_hat (firm iff q_hat >= q_L) instead of the true q
costs at most |q - q_hat| ((1 - rho) c + k) more than the optimum
min{(1 - q)(1 - rho) c, q k}, and the excess is positive only when q and q_hat
lie on opposite sides of q_L (with the tie q = q_L costing nothing).

Exact rational grid: rho in {0, 1/3, 1/2, 1 - 1/8}, c in {1, 2, 5}, k in {1/4, 1, 3},
q and q_hat in multiples of 1/24 on [0, 1].  The bound is also checked to be
tight: the maximum of excess / (|q - q_hat| ((1 - rho) c + k)) over the grid
equals 1 when q_hat moves just across q_L ... reported, not asserted.
"""
import json
import sys
from fractions import Fraction as Fr


def cost(cls, q, rho, c, k):
    return (1 - q) * (1 - rho) * c if cls == "F" else q * k


def main():
    cases = fails = sign_fails = 0
    best_ratio = Fr(0)
    for rho in [Fr(0), Fr(1, 3), Fr(1, 2), Fr(7, 8)]:
        for c in [Fr(1), Fr(2), Fr(5)]:
            for k in [Fr(1, 4), Fr(1), Fr(3)]:
                a = (1 - rho) * c
                qL = a / (a + k)
                for i in range(25):
                    q = Fr(i, 24)
                    opt = min(cost("F", q, rho, c, k), cost("S", q, rho, c, k))
                    for j in range(25):
                        qh = Fr(j, 24)
                        cls = "F" if qh >= qL else "S"
                        excess = cost(cls, q, rho, c, k) - opt
                        bound = abs(q - qh) * (a + k)
                        cases += 1
                        if excess < 0 or excess > bound:
                            fails += 1
                        same_side = (q >= qL) == (qh >= qL)
                        if same_side and excess != 0:
                            sign_fails += 1
                        if bound > 0 and excess / bound > best_ratio:
                            best_ratio = excess / bound
    res = {"cases": cases, "bound_failures": fails, "same_side_positive_excess": sign_fails,
           "max_excess_over_bound": str(best_ratio)}
    print(json.dumps(res))
    json.dump(res, open(str(__import__("pathlib").Path(__file__).resolve().parents[1] / "results" / "first_layer_d6_20261016.json"), "w"))
    return fails == 0 and sign_fails == 0


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
