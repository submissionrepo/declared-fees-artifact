"""Unit tests for the prototype (run: python -m pytest -q test_prototype.py)."""
import itertools
import random
from fractions import Fraction as Fr

import pytest

from mechanism import (FIRM, FIRM_READ, OMIT, SOFT, SOFT_READ, Declaration, ObjectTerms, bid, blocks_held, choose_class,
                       counted_usage_declared_set, counted_usage_pay_what_you_count,
                       damped_premium, drop_floor, held_capacity, menu_fee, producer_gain_at_rank, owtfm_fee, price_update, scheduler_share,
                       shill_profitable, single_class_declares, stationary_premium_map, sustained_hold_cost,
                       threshold_q)
from scheduler_sim import Tx, simulate, with_policy


# ------------------------------------------------------------ mechanism
def terms(c=1.0, rho=0.0, k=1.0, p=1.0):
    return ObjectTerms(price=p, rho=rho, k=k, c=c)


def test_charge_on_an_unused_soft_declaration():
    tm = ObjectTerms(price=Fr(1), rho=Fr(0), k=Fr(3), u=Fr(1, 2))
    terms = {"o": tm}
    pi, t = Fr(1), Fr(1)
    assert menu_fee([Declaration("o", SOFT, False)], terms, pi, t) == Fr(1, 2)
    assert menu_fee([Declaration("o", SOFT, True)], terms, pi, t) == 1 + 3
    assert menu_fee([Declaration("o", FIRM, False)], terms, pi, t) == 1
    assert scheduler_share([Declaration("o", SOFT, False)], terms, pi, t, Fr(1, 2)) == 0
    qL = threshold_q(tm, pi, t)
    assert qL == Fr(1, 2) / (Fr(1, 2) + 3)
    assert (1 - qL) * 1 == qL * 3 + (1 - qL) * Fr(1, 2)
    assert choose_class(qL / 2, tm, pi, t) == SOFT and choose_class((qL + 1) / 2, tm, pi, t) == FIRM


def test_producer_gain_at_rank():
    g, pi, s, p, t, k = Fr(1, 2), Fr(3), Fr(1), Fr(1), Fr(1), Fr(1, 3)
    # use that does not depend on position: no share of the premium changes the answer
    for gk in (Fr(0), Fr(1, 2), Fr(1)):
        assert producer_gain_at_rank(Fr(1, 2), Fr(1, 2), g, pi, s, p, t, gk, k) == -Fr(1, 2) * k
    # a racer that wins only at its rank: the producer keeps it there when its fee share covers the reruns
    assert producer_gain_at_rank(Fr(1, 2), Fr(0), g, pi, s, p, t, Fr(0), k) == Fr(1, 2) * (g * (pi - s) - k)
    assert producer_gain_at_rank(Fr(1, 2), Fr(0), g, pi, s, p, t, Fr(0), k) > 0
    assert producer_gain_at_rank(Fr(1, 2), Fr(0), g, Fr(1), s, p, t, Fr(0), k) < 0


def test_read_only_classes():
    tm = {"a": ObjectTerms(price=Fr(2), rho=Fr(1, 4), k=Fr(3))}
    pi, t = Fr(3), Fr(2)
    # a shared lock pays what an unused firm lock pays, read or not; a soft read pays nothing
    for used in (True, False):
        assert menu_fee([Declaration("a", FIRM_READ, used)], tm, pi, t) == menu_fee([Declaration("a", FIRM, False)], tm, pi, t)
        assert menu_fee([Declaration("a", SOFT_READ, used)], tm, pi, t) == 0
        assert scheduler_share([Declaration("a", FIRM_READ, used)], tm, pi, t, Fr(1, 2)) == 0
    assert counted_usage_pay_what_you_count([Declaration("a", FIRM_READ, False)], tm, t)["a"] == held_capacity(t, Fr(1, 4))
    assert counted_usage_pay_what_you_count([Declaration("a", SOFT_READ, True)], tm, t)["a"] == 0


def test_the_fee_on_an_unused_lock_is_burned():
    tm = {"a": ObjectTerms(price=Fr(1), rho=Fr(0), k=Fr(1))}
    assert scheduler_share([Declaration("a", FIRM, False)], tm, Fr(2), Fr(1), Fr(1, 2)) == 0
    assert scheduler_share([Declaration("a", FIRM, False)], tm, Fr(2), Fr(1), Fr(1, 2), gamma_unused=Fr(1, 4)) == Fr(1, 2)


def test_every_held_unit_pays_the_price_under_any_keys():
    tm = {"a": ObjectTerms(price=Fr(5), rho=Fr(1, 2), k=Fr(1))}
    held = held_capacity(Fr(6), Fr(1, 2))
    one_key = menu_fee([Declaration("a", FIRM, False)], tm, Fr(1), Fr(6))
    two_keys = sum(menu_fee([Declaration("a", FIRM, False)], tm, Fr(1), ti) for ti in (Fr(2), Fr(4)))
    assert one_key == two_keys == tm["a"].price * held
    # a higher priority pays more
    assert menu_fee([Declaration("a", FIRM_READ, False)], tm, Fr(4), Fr(6)) == 4 * tm["a"].price * held


def test_sustained_hold_matches_the_price_path():
    p0, held, target, eta = Fr(3), Fr(2), Fr(8), Fr(1, 8)
    p, paid = p0, Fr(0)
    for n in range(1, 40):
        paid += p * held
        assert sustained_hold_cost(p0, held, target, eta, n) == paid
        # the object's other use stays at its target, so the count is target + held
        p = price_update(p, target + held, target, eta)
    budget = sustained_hold_cost(p0, held, target, eta, 25)
    assert blocks_held(budget, p0, held, target, eta) == 25
    assert blocks_held(budget - 1, p0, held, target, eta) == 24
    assert sustained_hold_cost(p0, Fr(0), target, eta, 5) == 0
    # a hold above the target with no other use still drives the price up, at a lower rate
    p, paid, big = p0, Fr(0), target + 3
    for n in range(1, 20):
        paid += p * big
        assert sustained_hold_cost(p0, big, target, eta, n, other=Fr(0)) == paid
        p = price_update(p, big, target, eta)


def test_drop_floor():
    u, x, kbar = Fr(1), Fr(4), Fr(1)
    q = drop_floor(u, x, kbar)
    assert q == Fr(1, 6)
    assert single_class_declares(q, x, kbar, u) and not single_class_declares(q / 2, x, kbar, u)
    assert drop_floor(Fr(0), x, kbar) == 0


def test_threshold_and_choice():
    tm = terms(c=2.0, rho=0.5, k=1.0)          # (1-rho)c = 1 -> q_L = 1/2
    assert threshold_q(tm) == pytest.approx(0.5)
    assert choose_class(0.6, tm) == FIRM
    assert choose_class(0.4, tm) == SOFT
    assert choose_class(0.0, tm) == SOFT


def test_menu_fee_cases():
    tm = {"a": terms(c=2.0, rho=0.25, k=0.5, p=1.0)}
    pi, t = 2.0, 1.0
    assert menu_fee([Declaration("a", FIRM, True)], tm, pi, t) == pytest.approx(2.0)
    assert menu_fee([Declaration("a", FIRM, False)], tm, pi, t) == pytest.approx(1.5)
    assert menu_fee([Declaration("a", SOFT, True)], tm, pi, t) == pytest.approx(2.5)
    assert menu_fee([Declaration("a", SOFT, False)], tm, pi, t) == pytest.approx(0.0)
    with pytest.raises(ValueError):
        menu_fee([Declaration("a", OMIT, True)], tm, pi, t)


def test_menu_expected_fee_equals_min_cost():
    rnd = random.Random(7)
    for _ in range(500):
        c, rho, k, q = rnd.uniform(0.1, 3), rnd.uniform(0, 1), rnd.uniform(0.01, 3), rnd.uniform(0, 1)
        tm = terms(c=c, rho=rho, k=k)
        cls = choose_class(q, tm)
        exp = q * menu_fee([Declaration("a", cls, True)], {"a": tm}, 1.0, 0.0) + \
            (1 - q) * menu_fee([Declaration("a", cls, False)], {"a": tm}, 1.0, 0.0)
        assert exp == pytest.approx(min((1 - q) * (1 - rho) * c, q * k), abs=1e-12)


def test_unused_firm_fee_scales_with_the_bid():
    tm = {"a": ObjectTerms(price=1.0, rho=0.25, k=0.5)}
    assert bid(tm["a"], 3.0, 2.0) == pytest.approx(6.0)
    assert menu_fee([Declaration("a", FIRM, False)], tm, 3.0, 2.0) == pytest.approx(4.5)
    # each counted unit pays pi * p, used or not
    used = counted_usage_pay_what_you_count([Declaration("a", FIRM, True)], tm, 2.0)["a"]
    unused = counted_usage_pay_what_you_count([Declaration("a", FIRM, False)], tm, 2.0)["a"]
    assert menu_fee([Declaration("a", FIRM, True)], tm, 3.0, 2.0) / used == pytest.approx(3.0)
    assert menu_fee([Declaration("a", FIRM, False)], tm, 3.0, 2.0) / unused == pytest.approx(3.0)


def test_premium_is_burned():
    tm = {"a": ObjectTerms(price=1.0, rho=0.25, k=0.5)}
    keep_soft = scheduler_share([Declaration("a", SOFT, True)], tm, 2.0, 1.0, 0.5)
    keep_firm = scheduler_share([Declaration("a", FIRM, True)], tm, 2.0, 1.0, 0.5)
    assert keep_soft == pytest.approx(keep_firm) == pytest.approx(1.0)


def test_ordering_neutrality_of_the_menu():
    rnd = random.Random(3)
    for _ in range(500):
        pi, p, t, rho, s, gamma = (rnd.uniform(1, 4), rnd.uniform(.1, 3), rnd.uniform(.1, 3), rnd.random(), rnd.random(),
                                   rnd.uniform(.05, .95))
        tm = {"a": ObjectTerms(price=p, rho=rho, k=1.0)}
        used = scheduler_share([Declaration("a", FIRM, True)], tm, pi, t, gamma)
        unused = scheduler_share([Declaration("a", FIRM, False)], tm, pi, t, gamma)
        assert used + 1e-12 >= unused + gamma * s * rho * p * t


def test_stationary_premium_example():
    T = lambda k: stationary_premium_map(k, 1.0, 36.0)
    assert T(2.0) == pytest.approx(2.0)
    # posting last block's cost moves away from k* = 2 at slope -4/3
    k = 2.01
    gaps = [abs(k - 2)]
    for _ in range(6):
        k = T(k)
        gaps.append(abs(k - 2))
    assert all(b > a for a, b in zip(gaps, gaps[1:]))
    # the damped update converges from any start when theta < 2 / (1 + L), L = 36
    for start in (0.0, 0.5, 10.0, 100.0):
        k = start
        for _ in range(400):
            k = damped_premium(k, T(k), 0.05)
        assert k == pytest.approx(2.0, abs=1e-6)


def test_owtfm_fee():
    prices = {"px": 1.0, "pool": 3.0, "bal": 1.0}
    # Wadhwa 2026 Example 8: under-executed branch pays 1 + 4 alpha
    for alpha in [0.0, 0.5, 1.0]:
        d = [Declaration("px", FIRM, True), Declaration("pool", FIRM, False), Declaration("bal", FIRM, False)]
        assert owtfm_fee(d, prices, 1.0, 1.0, alpha) == pytest.approx(1 + 4 * alpha)


def test_counting_rules():
    tm = {"a": terms(rho=0.25), "b": terms(rho=0.25)}
    d = [Declaration("a", FIRM, False), Declaration("b", SOFT, False)]
    assert counted_usage_pay_what_you_count(d, tm, 2.0) == {"a": 1.5, "b": 0.0}
    assert counted_usage_declared_set(d, 2.0) == {"a": 2.0, "b": 2.0}


def test_price_update():
    assert price_update(1.0, 2.0, 1.0, 0.125) == pytest.approx(1.125)
    assert price_update(1.0, 1.0, 1.0, 0.125, linear=False) == pytest.approx(1.0)


def test_shill_condition_pay_what_you_count():
    # profitable iff gamma > 1/(1 + eta pi_o), for every shill option
    for gamma in [Fr(i, 12) for i in range(1, 12)]:
        for pi_o in [Fr(6, 5), Fr(5), Fr(16)]:
            eta = Fr(1, 8)
            any_prof = False
            for used in [True, False]:
                for rho in [Fr(0), Fr(1, 2)]:
                    paid = Fr(1) if used else (1 - rho)
                    counted = Fr(1) if used else (1 - rho)
                    if counted == 0:
                        continue
                    any_prof |= shill_profitable(gamma, eta, pi_o, paid, counted, Fr(1))
            assert any_prof == (gamma > 1 / (1 + eta * pi_o))


def test_single_class_threshold():
    # Proposition 4.1 at the Wadhwa example values (x = 6 per object group, kappa = 0, f_n = alpha p_C, p_C = 4)
    for alpha, qstar in [(0.15, 0.6 / 6.6), (1.0, 0.4)]:
        f = alpha * 4
        assert single_class_declares(qstar + 1e-9, 6.0, 0.0, f)
        assert not single_class_declares(qstar - 1e-6, 6.0, 0.0, f)


# ------------------------------------------------------------ scheduler
def mk(i, dur, declared, writes):
    return Tx(i, dur, frozenset(declared), frozenset(writes))


def test_firm_serializes_on_declared_accounts():
    txs = [mk(0, 1, "a", "a"), mk(1, 1, "a", "")]
    for order in ("free", "block"):
        r = simulate(with_policy(txs, "firm"), threads=2, order=order)
        assert r.makespan == pytest.approx(2.0) and r.reexecutions == 0 and r.serializable


def test_soft_runs_parallel_when_unused():
    txs = [mk(0, 1, "a", "a"), mk(1, 1, "a", "")]
    for order in ("free", "block"):
        r = simulate(with_policy(txs, "soft"), threads=2, order=order)
        assert r.makespan == pytest.approx(1.0) and r.reexecutions == 0 and r.serializable


def test_soft_reexecutes_on_real_conflict():
    txs = [mk(0, 1, "a", "a"), mk(1, 1, "a", "a")]
    for order in ("free", "block"):
        r = simulate(with_policy(txs, "soft"), threads=2, order=order)
        assert r.reexecutions == 1 and r.wasted == pytest.approx(1.0) and r.makespan == pytest.approx(2.0)
        assert r.serializable


def test_menu_mixes():
    txs = [mk(0, 1, "ab", "a"), mk(1, 1, "b", ""), mk(2, 1, "a", "a")]
    q = {"a": 0.9, "b": 0.1}
    for order in ("free", "block"):
        r = simulate(with_policy(txs, "menu", q=q, q_threshold=0.5), threads=3, order=order)
        assert r.makespan == pytest.approx(2.0) and r.reexecutions == 0 and r.serializable


def test_read_lock_blocks_firm_writer_and_readers_share():
    a = frozenset("a")
    none = frozenset()
    for order in ("free", "block"):
        r = simulate([Tx(0, 1, none, none, none, a), Tx(1, 1, a, a, a)], threads=2, order=order)
        assert r.makespan == pytest.approx(2.0) and r.reexecutions == 0 and r.serializable
        r = simulate([Tx(0, 1, none, none, none, a), Tx(1, 1, none, none, none, a)], threads=2, order=order)
        assert r.makespan == pytest.approx(1.0) and r.serializable


def test_soft_read_validation_free():
    # tx1 runs for 1 and writes a; tx0 runs for 2, declares a soft and does not write it
    txs = [Tx(0, 2, frozenset("a"), frozenset()), Tx(1, 1, frozenset("a"), frozenset("a"))]
    ignored = simulate(with_policy(txs, "soft"), threads=2)
    assert ignored.reexecutions == 0 and ignored.makespan == pytest.approx(2.0)
    validated = simulate(with_policy(txs, "soft"), threads=2, validate_soft_reads=True)
    assert validated.reexecutions == 1 and validated.wasted == pytest.approx(2.0)
    assert validated.makespan == pytest.approx(4.0) and validated.serializable


def test_soft_read_holds_nothing_and_runs_again_on_a_write():
    a = frozenset("a")
    none = frozenset()
    for order in ("free", "block"):
        # an earlier long soft reader does not hold back a later writer
        r = simulate([Tx(0, 5, none, none, none, none, a), Tx(1, 1, a, a, a)], threads=2, order=order)
        assert r.ends[1] == pytest.approx(1.0) and r.serializable
    # in free order the write commits during the read's run, so the reader runs again
    r = simulate([Tx(0, 5, none, none, none, none, a), Tx(1, 1, a, a, a)], threads=2, order="free")
    assert r.reexecutions == 1 and r.wasted == pytest.approx(5.0) and r.ends[0] == pytest.approx(10.0)
    # in block order the earlier reader reads the version its place requires and runs once
    r = simulate([Tx(0, 5, none, none, none, none, a), Tx(1, 1, a, a, a)], threads=2, order="block")
    assert r.reexecutions == 0 and r.ends[0] == pytest.approx(5.0)
    # a later soft reader of an earlier writer runs again if it started before the write committed
    r = simulate([Tx(0, 3, a, a, a), Tx(1, 1, none, none, none, none, a)], threads=2, order="block")
    assert r.reexecutions >= 1 and r.ends[1] > r.ends[0] and r.serializable
    # without versions a later writer's commit waits for the earlier soft reader
    r = simulate([Tx(0, 5, none, none, none, none, a), Tx(1, 1, a, a, a)], threads=2, order="block", versions=False)
    assert r.ends[1] == pytest.approx(5.0) and r.serializable


def test_a_validator_told_the_write_sets_never_runs_anything_twice():
    a = frozenset("a")
    none = frozenset()
    # the soft reader waits for the earlier writer, and the later writer does not wait for it
    txs = [Tx(0, 3, a, a, a), Tx(1, 2, none, none, none, none, a), Tx(2, 1, a, a, a)]
    r = simulate(txs, threads=3, order="block", told=True)
    assert r.reexecutions == 0 and r.ends[0] == pytest.approx(3.0) and r.ends[1] == pytest.approx(5.0) and r.ends[2] == pytest.approx(4.0)
    assert r.serializable
    rnd = random.Random(31)
    accts = list("abcdef")
    for _ in range(200):
        txs = []
        for i in range(rnd.randint(1, 12)):
            w = frozenset(rnd.sample(accts, rnd.randint(0, 2)))
            s = frozenset(rnd.sample(accts, rnd.randint(0, 3))) - w
            txs.append(Tx(i, rnd.choice([1, 2, 3]), w, w, w, none, s))
        r = simulate(txs, threads=rnd.choice([1, 2, 4]), validate_soft_reads=True, order="block", told=True)
        assert r.reexecutions == 0 and r.serializable and len(r.ends) == len(txs)


def test_a_retry_under_locks_runs_at_most_twice():
    a = frozenset("a")
    none = frozenset()
    txs = [Tx(i, 2, a, a, none) for i in range(5)]
    free = simulate(txs, threads=5, order="free")
    retry = simulate(txs, threads=5, order="free", retry_locks=True)
    assert free.reexecutions > retry.reexecutions and retry.reexecutions <= 5 and retry.serializable
    assert retry.retried <= set(range(5))


def test_random_blocks_with_soft_reads_are_serializable():
    rnd = random.Random(17)
    accts = list("abcdefgh")
    for _ in range(300):
        txs = []
        for i in range(rnd.randint(1, 12)):
            dec = frozenset(rnd.sample(accts, rnd.randint(1, 3)))
            wr = frozenset(a for a in dec if rnd.random() < 0.5)
            rest = [a for a in accts if a not in dec]
            s = frozenset(rnd.sample(rest, rnd.randint(0, 2)))
            f = frozenset(rnd.sample([a for a in rest if a not in s], rnd.randint(0, 2)))
            firm = frozenset(a for a in dec if rnd.random() < 0.5)
            txs.append(Tx(i, rnd.choice([1, 2, 3]), dec, wr, firm, f, s))
        for order in ("free", "block"):
            for validate in (False, True):
                for versions in (True, False):
                    r = simulate(txs, threads=rnd.choice([1, 2, 4]), validate_soft_reads=validate, order=order, versions=versions)
                    assert r.serializable and len(r.ends) == len(txs)
        for validate in (False, True):
            r = simulate(txs, threads=rnd.choice([1, 2, 4]), validate_soft_reads=validate, order="free", retry_locks=True)
            assert r.serializable and len(r.ends) == len(txs)


def test_single_thread_never_reexecutes():
    rnd = random.Random(5)
    for trial in range(100):
        txs = [mk(i, rnd.choice([1, 2]), set("ab"), set(rnd.sample("ab", rnd.randint(0, 2)))) for i in range(6)]
        for order in ("free", "block"):
            r = simulate(with_policy(txs, "soft"), threads=1, order=order)
            assert r.reexecutions == 0


# ------------------------------------------------------------ soft writers and lock holders
def test_free_soft_writer_cannot_interrupt_a_firm_holder():
    a = frozenset("a")
    # tx0 holds a firm for 3 and writes nothing; tx1 writes a softly in 1: its result waits for tx0 to finish
    txs = [Tx(0, 3, a, frozenset(), a), Tx(1, 1, a, a, frozenset())]
    r = simulate(txs, threads=2, validate_soft_reads=True)
    assert r.reexecutions == 0 and r.ends[0] == pytest.approx(3.0) and r.ends[1] == pytest.approx(3.0)
    assert r.serializable


def test_free_soft_writer_runs_again_if_the_holder_wrote():
    a = frozenset("a")
    txs = [Tx(0, 3, a, a, a), Tx(1, 1, a, a, frozenset())]
    r = simulate(txs, threads=2)
    assert r.reexecutions == 1 and r.wasted == pytest.approx(1.0)
    assert r.ends[0] == pytest.approx(3.0) and r.ends[1] == pytest.approx(4.0) and r.serializable


def test_free_soft_writer_waits_for_a_read_only_declaration():
    a = frozenset("a")
    none = frozenset()
    txs = [Tx(0, 2, none, none, none, a), Tx(1, 1, a, a, none)]
    r = simulate(txs, threads=2)
    assert r.reexecutions == 0 and r.ends[1] == pytest.approx(2.0) and r.serializable


def test_block_commits_conflicting_transactions_in_order():
    # tx1 finishes first but declares what tx0 declares: it commits when tx0 does
    txs = [Tx(0, 3, frozenset("a"), frozenset()), Tx(1, 1, frozenset("a"), frozenset("a"))]
    r = simulate(with_policy(txs, "soft"), threads=2, order="block")
    assert r.reexecutions == 0 and r.ends[1] == pytest.approx(3.0) and r.serializable


def test_block_earlier_soft_writer_makes_a_later_firm_holder_run_again():
    a = frozenset("a")
    txs = [Tx(0, 2, a, a, frozenset()), Tx(1, 3, a, a, a)]
    r = simulate(txs, threads=2, order="block")
    assert r.reexecutions == 1 and r.ends[0] == pytest.approx(2.0) and r.serializable
    # tx1 finishes its doomed run at 3 and runs again until 6
    assert r.ends[1] == pytest.approx(6.0)


def test_block_later_soft_writer_runs_again_when_the_earlier_holder_wrote():
    a = frozenset("a")
    txs = [Tx(0, 3, a, a, a), Tx(1, 1, a, a, frozenset())]
    r = simulate(txs, threads=2, order="block")
    assert r.reexecutions == 1 and r.ends[0] == pytest.approx(3.0) and r.ends[1] == pytest.approx(4.0)
    assert r.serializable


def test_block_firm_chain_follows_block_order():
    # a later short transaction cannot overtake an earlier one on the same account
    a = frozenset("a")
    b = frozenset("b")
    txs = [Tx(0, 2, b, b, b), Tx(1, 2, a | b, a | b, a | b), Tx(2, 1, a, a, a)]
    assert simulate(txs, threads=2, order="block").ends[2] == pytest.approx(5.0)
    assert simulate(txs, threads=2, order="free").ends[2] == pytest.approx(1.0)


def test_random_blocks_are_serializable():
    rnd = random.Random(11)
    accts = list("abcdefgh")
    for trial in range(300):
        n = rnd.randint(1, 12)
        txs = []
        for i in range(n):
            dec = set(rnd.sample(accts, rnd.randint(1, 4)))
            wr = set(a for a in dec if rnd.random() < 0.6)
            ro = set(rnd.sample(accts, rnd.randint(0, 2))) - dec
            txs.append(Tx(i, rnd.choice([1, 2, 3]), frozenset(dec), frozenset(wr), frozenset(), frozenset(ro)))
        q = {a: rnd.random() for a in accts}
        for pol in ["firm", "soft", "menu"]:
            threads = rnd.choice([1, 2, 4])
            for validate in (False, True):
                for order in ("free", "block"):
                    r = simulate(with_policy(txs, pol, q=q, q_threshold=0.5), threads=threads,
                                 validate_soft_reads=validate, order=order)
                    assert r.serializable
                    if pol == "firm":
                        assert r.reexecutions == 0
                    assert len(r.ends) == n


def _state_replay(txs, r, validate):
    """Independent check of block-order equivalence on versions: replay the committed schedule and compare what
    each final run saw with what it sees in the serial block order."""
    serial = {}
    want = {}
    for i, t in enumerate(txs):
        watch = t.writes | t.reads | (t.declared if validate else frozenset())
        want[i] = {a: serial.get(a) for a in watch}
        for a in t.writes:
            serial[a] = i
    return want


def test_block_order_equivalence_on_versions():
    rnd = random.Random(23)
    accts = list("abcdef")
    for trial in range(150):
        n = rnd.randint(2, 10)
        txs = []
        for i in range(n):
            dec = set(rnd.sample(accts, rnd.randint(1, 3)))
            wr = set(a for a in dec if rnd.random() < 0.5)
            txs.append(Tx(i, rnd.choice([1, 2, 5]), frozenset(dec), frozenset(wr)))
        q = {a: rnd.random() for a in accts}
        for pol in ["firm", "soft", "menu"]:
            for validate in (False, True):
                p = with_policy(txs, pol, q=q, q_threshold=0.5)
                r = simulate(p, threads=3, validate_soft_reads=validate, order="block")
                want = _state_replay(p, r, validate)
                # a writer's commit is visible from its commit time on
                for i, t in enumerate(p):
                    for a, w in want[i].items():
                        later = [j for j, u in enumerate(p) if a in u.writes and j > i]
                        if w is not None:
                            assert r.ends[w] <= r.ends[i]
                        for j in later:
                            assert r.ends[j] >= r.ends[i]
