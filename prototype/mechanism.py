"""Reference implementation of the declaration fee rules.

Rules
- single class (Wadhwa 2026 OW-TFM): a declared object pays pi * p * t if used and
  alpha * p if declared but unused; prices update on declared-set usage.
- menu M (this paper): each declared object is firm or soft.  Firm: pays the
  usage fee pi * p * t if used, (1 - rho) * c if unused, with c = pi * p * t.  Soft:
  pays the usage fee plus the posted conflict premium k if used, a charge u if unused
  (u = 0 by default; u = r makes each class pay its own cost).  A read-only declaration
  is firm (a shared lock, which pays (1 - rho) * c whether or not it reads, since the
  runtime does not see reads) or soft (no lock, nothing).  Everything beyond the usage
  fee is burned; the scheduler keeps gamma of the usage fee.  Usage counted for the
  price update is what was paid at the posted price ("pay what you count"): t if used,
  (1 - rho) * t if it holds a lock and is unused or read-only, 0 otherwise.

All functions are pure and work with fractions.Fraction or floats.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Iterable, Optional

FIRM = "F"
SOFT = "S"
OMIT = "N"
FIRM_READ = "FR"
SOFT_READ = "SR"


@dataclass(frozen=True)
class Declaration:
    obj: str
    cls: str            # FIRM, SOFT, FIRM_READ, SOFT_READ (or OMIT, never charged)
    used: bool          # realized at execution; for a read-only declaration the runtime cannot see it


@dataclass
class ObjectTerms:
    """Posted per-object terms for one block."""
    price: float        # p_o, posted price per unit of compute
    rho: float          # share of an unused firm reservation recovered after execution
    k: float            # posted conflict premium for a used soft declaration
    c: Optional[float] = None   # override of the bid for the capacity; None means pi * p_o * t
    u: float = 0.0      # charge on an unused soft declaration, at most (1 - rho) * c


def bid(tm: ObjectTerms, pi: float, t: float) -> float:
    """c_o = pi * p_o * t, what the transaction bid for the object over its running time."""
    return pi * tm.price * t if tm.c is None else tm.c


def threshold_q(terms: ObjectTerms, pi: float = 1.0, t: float = 1.0) -> float:
    """(c' - u) / (c' - u + k) with c' = (1 - rho) c; firm is cheaper in expectation iff q is at least this."""
    a = (1 - terms.rho) * bid(terms, pi, t) - terms.u
    if a + terms.k == 0:
        return 0.0
    return a / (a + terms.k)


def choose_class(q: float, terms: ObjectTerms, pi: float = 1.0, t: float = 1.0) -> str:
    """Expected-fee-minimizing class for an object used with probability q (Theorem 5.2(ii))."""
    if q <= 0:
        return SOFT
    return FIRM if q >= threshold_q(terms, pi, t) else SOFT


def menu_fee(decls: Iterable[Declaration], terms: Dict[str, ObjectTerms], pi: float, t: float) -> float:
    """Fee under menu M for one transaction.  Raises if a used object was omitted
    (the transaction reverts; the revert charge is outside this function)."""
    total = 0.0
    for d in decls:
        tm = terms[d.obj]
        if d.cls == OMIT:
            if d.used:
                raise ValueError(f"object {d.obj} used but not declared: transaction reverts")
            continue
        if d.cls == FIRM_READ:
            total += (1 - tm.rho) * bid(tm, pi, t)
        elif d.cls == SOFT_READ:
            continue
        elif d.used:
            total += pi * tm.price * t + (tm.k if d.cls == SOFT else 0)
        elif d.cls == FIRM:
            total += (1 - tm.rho) * bid(tm, pi, t)
        else:
            total += tm.u
    return total


def scheduler_share(decls: Iterable[Declaration], terms: Dict[str, ObjectTerms], pi: float, t: float,
                    gamma: float, gamma_unused: float = 0.0) -> float:
    """What the scheduler keeps under menu M: gamma of the usage fee.  Everything else is burned; gamma_unused > 0 is the
    variant that pays the scheduler a share of the fee on unused firm objects (Proposition 5.4(d))."""
    total = 0.0
    for d in decls:
        tm = terms[d.obj]
        if d.cls in (OMIT, FIRM_READ, SOFT_READ):
            continue
        if d.used:
            total += gamma * pi * tm.price * t
        elif d.cls == FIRM:
            total += gamma_unused * (1 - tm.rho) * bid(tm, pi, t)
    return total


def stationary_premium_map(k: float, c_prime: float, a: float) -> float:
    """T(k) for uniform q on [0, 1], unit mass and re-execution cost a * s (Proposition 5.5's example):
    soft use mass s(k) = q_L(k)^2 / 2 with q_L(k) = c_prime / (c_prime + k)."""
    q_l = c_prime / (c_prime + k)
    return a * q_l * q_l / 2


def damped_premium(k: float, realized: float, delta: float) -> float:
    """The damped posting rule of Proposition 5.5(c)."""
    return (1 - delta) * k + delta * realized


def owtfm_fee(decls: Iterable[Declaration], prices: Dict[str, float], pi: float, t: float, alpha: float) -> float:
    """Fee under the single-class OW-TFM (used: pi p t; declared unused: alpha p)."""
    total = 0.0
    for d in decls:
        if d.cls == OMIT:
            if d.used:
                raise ValueError(f"object {d.obj} used but not declared: transaction reverts")
            continue
        p = prices[d.obj]
        total += pi * p * t if d.used else alpha * p
    return total


def counted_usage_pay_what_you_count(decls: Iterable[Declaration], terms: Dict[str, ObjectTerms], t: float) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for d in decls:
        if d.cls == OMIT:
            continue
        if d.cls in (FIRM_READ, SOFT_READ):
            w = (1 - terms[d.obj].rho) * t if d.cls == FIRM_READ else 0.0
        else:
            w = t if d.used else ((1 - terms[d.obj].rho) * t if d.cls == FIRM else 0.0)
        out[d.obj] = out.get(d.obj, 0.0) + w
    return out


def counted_usage_declared_set(decls: Iterable[Declaration], t: float) -> Dict[str, float]:
    """Wadhwa 2026 U_{o,b}: every declared object counts t, used or not."""
    out: Dict[str, float] = {}
    for d in decls:
        if d.cls == OMIT:
            continue
        out[d.obj] = out.get(d.obj, 0.0) + t
    return out


def price_update(p: float, usage: float, target: float, eta: float, linear: bool = True) -> float:
    x = eta * (usage - target) / target
    return p * (1 + x) if linear else p * math.exp(x)


def shill_profitable(gamma: float, eta: float, pi_o: float, paid: float, counted: float, p: float) -> bool:
    """Lemma 4 setting, linearized: scheduler gain gamma*eta*pi_o*p*counted versus burned (1-gamma)*paid."""
    return gamma * eta * pi_o * p * counted > (1 - gamma) * paid


def single_class_declares(q: float, x: float, kappa: float, f_n: float) -> bool:
    """Proposition 4.1: declare iff q (x + kappa) >= (1 - q) f_n."""
    return q * (x + kappa) >= (1 - q) * f_n


def producer_gain_at_rank(q: float, q_last: float, gamma: float, pi: float, sigma: float, price: float, t: float,
                          gamma_k: float, k: float) -> float:
    """Proposition 5.7(a): what a producer that bears reruns gains from running a soft transaction at its rank, where it is
    used with probability q and costs k per use in reruns, rather than last, where it is used with probability q_last."""
    return (q - q_last) * (gamma * (pi - sigma) * price * t + gamma_k * k) - q * k


def drop_floor(u: float, x: float, kappa_bar: float) -> float:
    """Theorem 5.6(a): with at least u charged on every unused declaration, objects used less often than this are dropped."""
    return u / (u + x + kappa_bar)


def held_capacity(duration: float, rho: float) -> float:
    """Capacity a lock holds and the count it adds: (1 - rho) t."""
    return (1 - rho) * duration


def sustained_hold_cost(price: float, held: float, target: float, eta: float, blocks: int, other: Optional[float] = None) -> float:
    """Theorem 6.5(c): the least a hold of `held` per block pays over `blocks` blocks while the object's other use is at least
    `other` (the target by default), so that the price grows by the factor 1 + eta g with g = (other + held - target) / target."""
    g = eta * ((target if other is None else other) + held - target) / target
    if g == 0:
        return price * held * blocks
    return price * held * ((1 + g) ** blocks - 1) / g


def blocks_held(budget: float, price: float, held: float, target: float, eta: float, other: Optional[float] = None) -> int:
    """Theorem 6.5(c): the most blocks that budget can hold the object for at that least cost."""
    n = 0
    while sustained_hold_cost(price, held, target, eta, n + 1, other) <= budget:
        n += 1
    return n
