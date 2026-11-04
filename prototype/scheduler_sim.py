"""Lock-based parallel scheduler with firm and soft write declarations.

A block is a list of transactions; the list index is the block order and the dispatch priority (lower first).
Each transaction has a duration (consumed compute, used as time), a declared writable set, the subset it actually
writes, a set of read-only declarations, and per policy a firm subset of the declared set.  Firm accounts take an
exclusive lock, read-only declarations take a shared lock, and soft accounts take no lock.

A read-only declaration is firm (`reads`: a shared lock) or soft (`soft_reads`: no lock).  Each run watches what it wrote
and its read-only declarations of either class; with `validate_soft_reads` it also watches every declared account, since
a transaction may read an account it declared and did not write.

order="block": conflicting transactions commit in block order, as a validator that re-executes a block must.
- A firm account waits for every earlier transaction that holds it firm or read-only to commit; a read-only account
  waits for every earlier firm holder to commit.  A lock lasts until its holder commits.
- A finished run commits once every earlier transaction whose declaration overlaps its own in a conflicting way has
  committed; its result waits without a thread.  It runs again if an earlier transaction committed during its run
  with a write in its watch set, so an earlier soft writer can make a later firm holder run again.
- A soft read never makes a later transaction wait.  With `versions` (the default) a run reads the version its place in
  the block requires, so a later writer may commit before an earlier soft reader has finished; without it the writer's
  commit waits for the reader's.  With `told` the validator knows what each transaction wrote: `declared` holds only those
  accounts, and a soft read starts once every earlier writer of it has committed, so nothing runs twice.

order="free": the block order is only a priority, as for a block producer that picks its own order.
- Whenever a worker is free, scan waiting transactions in priority order and start each one whose locks are available:
  no exclusive or shared holder on a firm account, no exclusive holder on a read-only account.  A later transaction
  can start ahead of an earlier one that waits.  A lock lasts until its holder's run ends.
- A finished run aborts if some transaction committed during it with a write in its watch set.  Otherwise it commits,
  unless it wrote a soft account that another transaction holds; then its result waits without a thread and is
  validated again when the holders are gone.

An aborted transaction rejoins the waiting set at once and its execution counts as wasted work.

Policies: "firm" (every declared writable account firm: the current lock-based design), "soft" (none firm:
optimistic execution), "menu" (firm iff the account's estimated use probability is at least the threshold).
"""
from __future__ import annotations

import heapq
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, FrozenSet, List, Optional, Sequence, Set, Tuple


@dataclass
class Tx:
    idx: int
    duration: float
    declared: FrozenSet[str]
    writes: FrozenSet[str]              # subset of declared that is actually written
    firm: FrozenSet[str] = frozenset()  # policy-dependent
    reads: FrozenSet[str] = frozenset()  # read-only declarations under a shared lock
    soft_reads: FrozenSet[str] = frozenset()  # read-only declarations under no lock

    def __post_init__(self):
        assert self.writes <= self.declared, "writes must be declared"
        assert self.firm <= self.declared


@dataclass
class SimResult:
    makespan: float
    busy: float
    wasted: float
    reexecutions: int
    lock_wait: float
    serializable: bool
    ends: Optional[Dict[int, float]] = None     # commit time per transaction index
    retried: Optional[Set[int]] = None          # transactions that ran again under locks


def _watch(txs: Sequence[Tx], validate_soft_reads: bool) -> List[FrozenSet[str]]:
    return [t.writes | t.reads | t.soft_reads | (t.declared if validate_soft_reads else frozenset()) for t in txs]


def simulate(txs: Sequence[Tx], threads: int, max_attempts: int = 100000,
             validate_soft_reads: bool = False, order: str = "free", versions: bool = True, told: bool = False,
             retry_locks: bool = False) -> SimResult:
    if not txs:
        return SimResult(0.0, 0.0, 0.0, 0, 0.0, True)
    if order == "block":
        return _simulate_block(txs, threads, validate_soft_reads, versions, told)
    if order != "free":
        raise ValueError(order)
    return _simulate_free(txs, threads, max_attempts, validate_soft_reads, retry_locks)


def _simulate_free(txs: Sequence[Tx], threads: int, max_attempts: int, validate_soft_reads: bool, retry_locks: bool = False) -> SimResult:
    """With retry_locks a run that aborts runs again holding a lock on everything it declared, so it runs at most twice."""
    n = len(txs)
    watch = _watch(txs, validate_soft_reads)
    firm_now = [t.firm for t in txs]
    read_now = [t.reads for t in txs]
    retried: Set[int] = set()
    waiting: List[int] = list(range(n))
    ready_since = [0.0] * n
    running: List[Tuple[float, int, float]] = []    # (end, idx, start)
    held: List[Tuple[int, float, float]] = []       # finished runs waiting for a holder to go: (idx, start, run end)
    excl: Dict[str, int] = {}
    shared: Dict[str, int] = {}
    commits: List[Tuple[float, int]] = []           # (commit time, idx) in commit order
    final_run: Dict[int, Tuple[float, float]] = {}  # idx -> (start, end) of the run that committed
    attempts = [0] * n
    busy = wasted = lock_wait = 0.0
    reexec = 0
    t = 0.0

    def available(i: int) -> bool:
        return (all(a not in excl and a not in shared for a in firm_now[i])
                and all(a not in excl for a in read_now[i]))

    def dispatch(now: float):
        nonlocal lock_wait
        free = threads - len(running)
        started = []
        for i in waiting:
            if free <= 0:
                break
            if available(i):
                for a in firm_now[i]:
                    excl[a] = i
                for a in read_now[i]:
                    shared[a] = shared.get(a, 0) + 1
                heapq.heappush(running, (now + txs[i].duration, i, now))
                lock_wait += now - ready_since[i]
                attempts[i] += 1
                started.append(i)
                free -= 1
        for i in started:
            waiting.remove(i)

    def collided(i: int, start: float) -> bool:
        for (ct, j) in reversed(commits):
            if ct <= start:
                return False
            if txs[j].writes & watch[i]:
                return True
        return False

    def settle(i: int, start: float, end: float, now: float):
        nonlocal wasted, reexec
        if collided(i, start) and attempts[i] < max_attempts:
            wasted += end - start
            reexec += 1
            ready_since[i] = now
            if retry_locks:
                firm_now[i] = txs[i].declared | txs[i].firm
                read_now[i] = (txs[i].reads | txs[i].soft_reads) - firm_now[i]
                retried.add(i)
            waiting.append(i)
            waiting.sort()
        elif any(a in excl or a in shared for a in txs[i].writes - firm_now[i]):
            held.append((i, start, end))
        else:
            commits.append((now, i))
            final_run[i] = (start, end)

    dispatch(t)
    while running or held:
        if running:
            end, i, start = heapq.heappop(running)
            t = end
            for a in firm_now[i]:
                if excl.get(a) == i:
                    del excl[a]
            for a in read_now[i]:
                shared[a] -= 1
                if not shared[a]:
                    del shared[a]
            busy += end - start
            settle(i, start, end, t)
        if held:
            again, held[:] = list(held), []
            for i, start, end in again:
                settle(i, start, end, t)
        dispatch(t)
    if waiting:
        raise RuntimeError("no progress")
    ends = {i: ct for ct, i in commits}
    # The commit order is a serial order: no final run overlaps a conflicting lock, and nothing it watches was
    # written by a commit between its start and its own commit.
    ser = True
    for x, (ct, i) in enumerate(commits):
        si, ei = final_run[i]
        for y in range(x):
            cj, j = commits[y]
            sj, ej = final_run[j]
            if sj < ei and si < ej and (firm_now[i] & firm_now[j] or firm_now[i] & read_now[j] or firm_now[j] & read_now[i]):
                ser = False
            if cj > si and txs[j].writes & watch[i]:
                ser = False
    return SimResult(max(ends.values()), busy, wasted, reexec, lock_wait, ser, ends, retried)


def _simulate_block(txs: Sequence[Tx], threads: int, validate_soft_reads: bool, versions: bool = True, told: bool = False) -> SimResult:
    n = len(txs)
    watch = _watch(txs, validate_soft_reads)
    may_write = [t.declared - (t.reads - t.firm) for t in txs]
    declared_w: Dict[str, List[int]] = defaultdict(list)
    declared_r: Dict[str, List[int]] = defaultdict(list)
    firm_h: Dict[str, List[int]] = defaultdict(list)
    read_h: Dict[str, List[int]] = defaultdict(list)
    after: List[List[int]] = [[] for _ in range(n)]         # later transactions whose commit waits for this one
    lock_after: List[List[int]] = [[] for _ in range(n)]    # later transactions whose start waits for this one
    n_before = [0] * n
    n_lock = [0] * n
    for i, t in enumerate(txs):
        before: Set[int] = set()
        for a in may_write[i]:
            before.update(declared_w[a])
            before.update(declared_r[a])
        for a in t.reads | t.soft_reads:
            before.update(declared_w[a])
        before.discard(i)
        n_before[i] = len(before)
        for j in before:
            after[j].append(i)
        locks: Set[int] = set()
        for a in t.firm:
            locks.update(firm_h[a])
            locks.update(read_h[a])
        for a in t.reads:
            locks.update(firm_h[a])
        if told:
            for a in t.soft_reads:
                locks.update(firm_h[a])
        locks.discard(i)
        n_lock[i] = len(locks)
        for j in locks:
            lock_after[j].append(i)
        for a in may_write[i]:
            declared_w[a].append(i)
        for a in t.reads:
            declared_r[a].append(i)
        if not versions:
            for a in t.soft_reads:
                declared_r[a].append(i)
        for a in t.firm:
            firm_h[a].append(i)
        for a in t.reads:
            read_h[a].append(i)
    waiting: List[int] = list(range(n))
    running: List[Tuple[float, int, float]] = []
    held: Set[int] = set()
    last_run: Dict[int, Tuple[float, float]] = {}           # idx -> (start, duration) of its latest run
    commits: List[Tuple[float, int]] = []
    final_start: Dict[int, float] = {}
    ends: Dict[int, float] = {}
    ready_since = [0.0] * n
    busy = wasted = lock_wait = 0.0
    reexec = 0

    def dispatch(now: float):
        nonlocal lock_wait
        free = threads - len(running)
        started = []
        for i in waiting:
            if free <= 0:
                break
            if n_lock[i] == 0:
                heapq.heappush(running, (now + txs[i].duration, i, now))
                lock_wait += now - ready_since[i]
                started.append(i)
                free -= 1
        for i in started:
            waiting.remove(i)

    def rerun(i: int, now: float):
        nonlocal wasted, reexec
        wasted += last_run[i][1]
        reexec += 1
        ready_since[i] = now
        held.discard(i)
        waiting.append(i)
        waiting.sort()

    def collided(i: int, start: float) -> bool:
        for (ct, j) in reversed(commits):
            if ct <= start:
                return False
            if j < i and txs[j].writes & watch[i]:
                return True
        return False

    def commit(i: int, now: float):
        ready = [i]
        while ready:
            x = ready.pop()
            held.discard(x)
            commits.append((now, x))
            final_start[x] = last_run[x][0]
            ends[x] = now
            for k in lock_after[x]:
                n_lock[k] -= 1
            for k in after[x]:
                n_before[k] -= 1
                if k in held:
                    if txs[x].writes & watch[k] and last_run[k][0] < now:
                        rerun(k, now)
                    elif n_before[k] == 0:
                        ready.append(k)

    dispatch(0.0)
    t = 0.0
    while running:
        end, i, start = heapq.heappop(running)
        t = end
        busy += end - start
        last_run[i] = (start, end - start)
        if collided(i, start):
            rerun(i, t)
        elif n_before[i] == 0:
            commit(i, t)
        else:
            held.add(i)
        dispatch(t)
    if len(ends) != n:
        raise RuntimeError("no progress")
    return SimResult(max(ends.values()), busy, wasted, reexec, lock_wait,
                     _follows_block_order(txs, watch, final_start, ends, versions), ends)


def _follows_block_order(txs: Sequence[Tx], watch: Sequence[FrozenSet[str]],
                         final_start: Dict[int, float], ends: Dict[int, float], versions: bool = True) -> bool:
    """Every account a transaction watches holds, when its final run starts, the value left by the last earlier
    writer in block order, and no later writer of it commits before the transaction does.  With versions, a later writer
    of an account the transaction only reads softly may commit first, since the run reads the version its place requires."""
    writers: Dict[str, List[int]] = defaultdict(list)
    for j, t in enumerate(txs):
        for a in t.writes:
            writers[a].append(j)
    for js in writers.values():
        times = [ends[j] for j in js]
        if any(times[x] > times[x + 1] for x in range(len(times) - 1)):
            return False
    for i in range(len(txs)):
        versioned = (txs[i].soft_reads - txs[i].declared - txs[i].reads) if versions else frozenset()
        for a in watch[i]:
            for j in writers.get(a, ()):
                if j < i and ends[j] > final_start[i]:
                    return False
                if j > i and ends[j] < ends[i] and a not in versioned:
                    return False
    return True


def with_policy(txs: Sequence[Tx], policy: str, q: Optional[Dict[str, float]] = None,
                q_threshold: float = 0.5) -> List[Tx]:
    out = []
    for tx in txs:
        if policy == "firm":
            firm = tx.declared
        elif policy == "soft":
            firm = frozenset()
        elif policy == "menu":
            assert q is not None
            firm = frozenset(a for a in tx.declared if q.get(a, 1.0) >= q_threshold)
        else:
            raise ValueError(policy)
        out.append(Tx(tx.idx, tx.duration, tx.declared, tx.writes, frozenset(firm), tx.reads, tx.soft_reads))
    return out
