# Where the two classes land in a production client

Based on Agave at commit `dd4c9ac8b050d881de5640b38cecfffb1c516942`. This note names the places to change and what changes; it contains no code. The rule itself is in `mechanism.py` and the scheduling in `scheduler_sim.py`.

## Current behavior

| Step | File and function | Behavior |
|---|---|---|
| Rank | `core/src/transaction_priority.rs::calculate_priority_and_cost` | `P = R / (1 + C)`; `C` comes from the cost model using the declared compute limit and includes a write-lock cost per writable account |
| Budget before execution | `core/src/banking_stage/qos_service.rs::select_transactions_per_cost` | `cost_tracker.try_add(cost, writable_accounts(tx))`: the estimated cost is charged to every declared writable account and to the block |
| Budget after execution | `qos_service.rs::remove_or_update_recorded_transaction_costs` | a committed transaction calls `cost_tracker.update_cost(estimated, actual, writable_accounts(transaction))`, which adjusts every declared writable account by the same difference; an uncommitted one calls `remove` |
| Per-account and block limits | `runtime/src/slot_params.rs` | 20,000,000 per writable account and 50,000,000 per block at the 200 ms slot parameters, with SIMD-0286 and SIMD-0525 active |
| Replay | `runtime/src/transaction_execution.rs` | the post-execution cost is charged to the same declared writable set |
| Commit | `runtime/src/account_saver.rs` | write-locked accounts the transaction left untouched are not saved. A program's return marks as touched every writable account it owns and was passed, so this record is wider than a write: a fee on it counts some unwritten accounts as used, which can only raise what a transaction pays, and comparing contents at commit would narrow it |
| Locks | `accounts-db/src/account_locks.rs` | a writable declaration takes an exclusive lock; a read-only one takes a shared lock |

So a transaction that does not write an account it declared writable still holds the exclusive lock while it runs, and its actual cost stays charged to that account's budget for the block.

## Two classes

1. **Format.** A v1 transaction's configuration carries a field listing the indices of its soft accounts, writable or read-only. Unlisted accounts are firm. Older formats are all firm and behave as today.
2. **Locks.** A firm writable account takes the exclusive lock and a firm read-only account the shared lock, as today. A soft account takes no lock. Before commit, if another transaction committed during this transaction's run and wrote anything it read or wrote, this transaction aborts and runs again, in the manner of Block-STM's validation of read sets. A soft write waits at commit for any holder of the account. A validator also has to commit conflicting transactions in block order, so a later declarer waits until an earlier soft writable declarer has finished, unless the producer publishes what each transaction wrote. An earlier soft read never holds back a later writer, provided the validator keeps the account's earlier version until the reader has started. This needs validated reads and is the largest of these changes.
3. **Budget.** The estimated cost is charged only to firm writable accounts and the block. The actual cost is charged to firm writable accounts and to soft writable accounts actually written.
4. **Fee.** A firm writable account that was not written and a firm read-only account add `(1 - rho) c_o`, with `c_o = pi p_o t`. A soft writable account that was written adds the premium `k_o`. All of this is burned. `p_o` and `k_o` are posted per account like a local base fee, and move by the damped update.
5. **Rank.** `C` counts write-lock costs for firm accounts only. A soft account is paid for by item 4 when it is written.

## The first steps

**Telling validators.** A block carries what each transaction wrote, and the block is invalid if the list is wrong, as with EIP-7928. A validator then schedules a transaction once every earlier writer of anything it declared has committed, and a later writer does not wait for an earlier reader. This needs no fee and no class, and it is the largest saving in the replay.

**Accounting without new locks.** Items 1, 3 and 4, under a feature gate on every client, since replay checks the same budgets. A soft writable account keeps its exclusive lock during execution, so parallelism does not change, but it stays out of the account's budget until it is written. An unused soft declaration then holds the lock and pays nothing, and the budget no longer bounds the serial run on that account. A chain can begin with no fee on unused firm declarations and a large premium, where every transaction stays firm and the rule is today's, then raise the first and lower the second in steps.
