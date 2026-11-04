# Artifact for "What Should a Transaction Pay for a Lock It Does Not Use?"

Scripts, aggregate results, exact checks and a reference implementation for the paper. Run with Python 3.11.5, sympy 1.14.0, numpy 2.4.6, matplotlib 3.11.0 and pytest 9.1.1; `pip install sympy numpy matplotlib pytest`. All commands run from this directory.

## What is here

| Path | Contents |
|---|---|
| `scripts/` | Collection and analysis. `sample_solana_v4.py`: Solana samples through a public RPC node. `sample_sui.py`, `analyze_sui_v2.py`: Sui through the public GraphQL endpoint; `repair_sui_pages.py` rereads the transactions of an older sample whose lists ran past the first page, as the paper's sample needed. `sample_caps.py`, `analyze_caps.py`: Monad and Ethereum. `facts/`: small aggregate samples on access lists, their senders, storage charges and the gas charged on Avalanche, before and after its rule changed. `replay_solana.py`, `analyze_paper_numbers.py`: the Solana measurements and the replay. `analyze_extensions.py`: the cost of an unused soft declaration, foresight classes, one fee and the saving by load. `analyze_occupancy.py`: who holds the accounts most in demand. `analyze_frontier.py`: the trade-off of Theorem 5.6, with transactions taking their best response. `analyze_soft_last.py`: the replay with soft transactions placed last. `analyze_reads.py`: read-only declarations as a second placement, and a validator told what was written. `analyze_hold.py`: what a hold costs against what it does, the budget against use, tips, the price of equation (3.1) on consecutive blocks. `analyze_retry.py`: retries under locks, which the paper rejects. `analyze_failed_only.py`: how much of the saving comes from transactions that fail, on a minute. `sample_solana_v5.py`, `facts/fetch_windows.py`, `run_minutes.py`, `check_minutes.py`: whole minutes of consecutive blocks with tips recorded, the analyses on them, and a check that each rests on all the blocks of its minute. `scan_unreferenced.py`: writable accounts that no instruction references. |
| `results/` | Aggregate outputs of those scripts, with no account or sender identifiers, and the outputs of the exact checks. |
| `checks/` | Exact and symbolic checks of the theorems and propositions on finite instances. Each file's docstring lists what it checks. They certify the finite statements listed; the general statements rest on the proofs in the paper. `first_layer_paper_20261101.py` checks the statements as the paper states them, and its docstring gives the numbers. The three older files check an earlier form in which the unused firm fee is `(1 - rho) p t`: in `first_layer_20261016.py`, D1 is Proposition 4.1 and Theorem 4.2(a) and (c), D2 Theorem 5.2, D3 the first step of Theorem 6.4, D4 Theorem 6.2 and D5 Proposition 7.1; `first_layer_d6_20261016.py` is the bound after Corollary 5.3 and `first_layer_d7_20261016.py` is Proposition 5.4(b) and, in that earlier form, (a). |
| `prototype/` | `mechanism.py`: the fee rules, the class choice, the two ways of counting use, the damped premium, the cost of a sustained hold. `scheduler_sim.py`: the lock-based scheduler with firm and soft declarations, writable and read-only, and a validator told what was written. `test_prototype.py`: unit tests. `client_changes.md`: where the rule lands in a production client. |
| `paper/` | `make_numbers.py`, `make_tables.py`, `make_figures.py`: the macros, data tables and data figures of the paper from `results/`. |
| `data/` | Slot lists of the two Solana samples and of the 160 slots of the three earliest minutes; `results/facts_windows_plan.json` gives the slots of all the minutes. Raw samples contain account identifiers and are not included. |

## Reproduce

```
python -m pytest -q prototype/test_prototype.py
python checks/first_layer_paper_20261101.py
python checks/first_layer_20261016.py
python checks/first_layer_d6_20261016.py
python checks/first_layer_d7_20261016.py
cd paper && python make_numbers.py && python make_tables.py && python make_figures.py
```

`make_numbers.py` asserts that every replay schedule passed the simulator's check: block-order schedules follow the block's order and free-order schedules are serializable.

To refetch the two Solana samples by slot, while public nodes still serve those slots, and redo the analysis:

```
python scripts/sample_solana_v4.py slots_a.jsonl solana_a.jsonl
python scripts/analyze_paper_numbers.py solana_a.jsonl paper_numbers_day1.json
python scripts/analyze_extensions.py solana_a.jsonl paper_extensions_day1.json
python scripts/analyze_occupancy.py solana_a.jsonl occupancy_day1.json
python scripts/analyze_frontier.py solana_a.jsonl paper_extensions_day1.json frontier_day1.json
python scripts/analyze_soft_last.py solana_a.jsonl soft_last_day1.json
python scripts/analyze_reads.py solana_a.jsonl reads_day1.json 4 8 16 32
python scripts/analyze_hold.py solana_a.jsonl hold_day1.json
python scripts/analyze_retry.py solana_a.jsonl retry_day1.json 4 8 16
python scripts/sample_solana_v4.py slots_b.jsonl solana_b.jsonl
python scripts/analyze_paper_numbers.py solana_b.jsonl paper_numbers_day2.json
python scripts/analyze_extensions.py solana_b.jsonl paper_extensions_day2.json
python scripts/analyze_occupancy.py solana_b.jsonl occupancy_day2.json
python scripts/analyze_frontier.py solana_b.jsonl paper_extensions_day2.json frontier_day2.json
python scripts/analyze_soft_last.py solana_b.jsonl soft_last_day2.json
python scripts/analyze_reads.py solana_b.jsonl reads_day2.json 4 8 16 32
python scripts/analyze_hold.py solana_b.jsonl hold_day2.json
python scripts/analyze_retry.py solana_b.jsonl retry_day2.json 4 8 16
```

The whole minutes come from `facts/busy_minutes.py`, which ranks the minutes a public node remembers; given the slot where a selection stopped, it repeats that selection while the node still has the records. Nodes draw their minute boundaries about 75 slots apart, so its slots can differ from `results/facts_windows_plan.json`, which gives the slots replayed. `facts/fetch_windows.py` fetches the plan, and `run_minutes.py` runs every analysis on each minute, with `DF_LIGHT=1` restricting them to what the paper reports, and names the results by the tags of `results/facts_minutes.json`:

```
python scripts/facts/busy_minutes.py https://api.mainnet.solana.com results/facts_busy_minutes.json 3 464102874
python scripts/facts/busy_minutes.py https://api.mainnet.solana.com results/facts_busy_minutes_nov2.json 12 464469766
python scripts/facts/fetch_windows.py results/facts_busy_minutes_nov2.json results/facts_windows_plan.json 8 4 https://solana-rpc.publicnode.com https://api.mainnet.solana.com
python scripts/run_minutes.py 5
python scripts/check_minutes.py
STEP=3 python scripts/scan_unreferenced.py results/facts_unreferenced.json https://public.rpc.solanavibestation.com slots_a.jsonl slots_b.jsonl
```

A minute is about 50 MB of compressed records and takes from ten minutes to an hour on a public node, and its analyses take about an hour of one core and half a gigabyte each.

To collect fresh samples:

```
python scripts/sample_solana_v4.py fresh:120:1800 solana_sample.jsonl
python scripts/analyze_paper_numbers.py solana_sample.jsonl solana_sample_numbers.json
python scripts/sample_sui.py 160 1500 50 sui_v2.jsonl
python scripts/analyze_sui_v2.py
python scripts/sample_caps.py monad 150 2000
python scripts/sample_caps.py ethereum 40 180
python scripts/analyze_caps.py
python scripts/facts/monad_al_share.py https://rpc-mainnet.monadinfra.com results/facts_monad_al_share.json 200 1500
python scripts/facts/monad_al_share.py https://ethereum-rpc.publicnode.com results/facts_eth_al_share.json 30 200
python scripts/facts/monad_concentration.py https://rpc-mainnet.monadinfra.com results/facts_monad_concentration.json 200 1500
python scripts/facts/sui_unchanged_fee.py results/facts_sui_unchanged_fee.json 40 5000 50
python scripts/facts/avax_sample.py https://api.avax.network/ext/bc/C/rpc results/facts_avax_receipts.json 150 1500 8
python scripts/facts/avax_before_after.py https://api.avax.network/ext/bc/C/rpc results/facts_avax_before_after.json 600 8
python scripts/facts/analyze_avax_response.py results/facts_avax_response.json
```

`analyze_sui_v2.py`, `analyze_caps.py` and the `facts/` scripts overwrite files in `results/`, and `make_numbers.py` then writes the new values instead of the paper's. A fresh Solana sample of 120 blocks is about 60 MB and takes from a few minutes to an hour, depending on the node. The chain moves, so a fresh sample gives new numbers.
## Public package

Repository: https://github.com/submissionrepo/declared-fees-artifact

The linked manuscript PDF is included alongside its source. The release contains a ZIP of this repository.
Original code and documentation are available under the [MIT License](LICENSE). Third-party components retain their own licenses. The data descriptions above identify the public sources and the scope of the included aggregates.
