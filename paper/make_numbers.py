"""Generate numbers.tex (LaTeX macros) and numbers.json from the research outputs.

Sources are in results/: the two Solana samples
(paper_numbers_day1.json, paper_numbers_day2.json, from scripts/analyze_paper_numbers.py), the whole
minutes of blocks (the same analyses with the tags of facts_minutes.json), Sui
(sui_v2_summary.json, facts_sui_unchanged_fee.json), Monad and Ethereum (caps_summary.json,
facts_monad_al_share.json, facts_eth_al_share.json, facts_monad_concentration.json).
"""
import json
import os
from datetime import datetime, timezone
from fractions import Fraction as Fr
from pathlib import Path

HERE = Path(__file__).resolve().parent
RES = HERE.parent / 'results'


def read(name):
    return json.loads((RES / name).read_text(encoding='utf-8'))


A = read('paper_numbers_day1.json')
B = read('paper_numbers_day2.json')
SUI = read('sui_v2_summary.json')
CAPS = read('caps_summary.json')
SUIFEE = read('facts_sui_unchanged_fee.json')
MONADAL = read('facts_monad_al_share.json')
ETHAL = read('facts_eth_al_share.json')
MONADCONC = read('facts_monad_concentration.json')
EXT = {'A': read('paper_extensions_day1.json'), 'B': read('paper_extensions_day2.json')}

M = {}


def put(name, value):
    assert name not in M, name
    M[name] = value


def pct(x, d=1):
    return f'{100 * x:.{d}f}'


def thousands(n):
    return f'{n:,}'.replace(',', '{,}')


def day(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc)


BUDGET = 20_000_000         # per-account budget at the 200 ms slot parameters


def of_budget(units):
    return f'{100 * units / BUDGET:.0f}'


def cap(name):
    return name[0].upper() + name[1:]


for tag, r in (('A', A), ('B', B)):
    m, d, h, s, l, u = r['meta'], r['declarations'], r['hot'], r['senders'], r['light'], r['use_hist']
    a = r['A']
    put(f'nBlocks{tag}', str(m['blocks']))
    put(f'hours{tag}', f"{m['hours']:.1f}")
    put(f'nTx{tag}', thousands(m['transactions']))
    put(f'shareFailedTx{tag}', pct(m['share_failed']))
    put(f'shareVone{tag}', pct(m['share_v1'], 0))
    put(f'nWritable{tag}', thousands(d['writable_nonsigner']))
    put(f'notWritten{tag}', pct(d['share_not_written_v3']))
    put(f'notWrittenR{tag}', pct(d['share_not_written_v3'], 0))
    put(f'notWrittenStrict{tag}', pct(d['share_not_written_strict']))
    put(f'notWrittenOk{tag}', pct(d['share_not_written_in_successful']))
    put(f'notWrittenOkR{tag}', pct(d['share_not_written_in_successful'], 0))
    put(f'inFailed{tag}', pct(d['share_failed']))
    put(f'tokenUnch{tag}', pct(d['share_token_unchanged']))
    put(f'routerLeg{tag}', pct(d['share_router']))
    for t, name in (('1', 'One'), ('2-9', 'Two'), ('10-99', 'Ten'), ('100+', 'Hund')):
        put(f'heat{name}{tag}', pct(d['by_heat'][t]['share_v3']))
        put(f'tokHeat{name}{tag}', pct(r['token_unchanged_by_heat']['by_heat'][t]['unchanged_share']))
    put(f'usedOverDeclared{tag}', f"{a['all']['used_over_declared']:.2f}")
    put(f'usedOverDeclaredMedian{tag}', f"{a['all']['p50']:.2f}")
    put(f'overLimitFail{tag}', str(a['over_limit_failures']))
    put(f'defaultTx{tag}', pct(a['default_limit']['n'] / a['all']['n']))
    put(f'defaultDecl{tag}', pct(a['share_declared_default']))
    put(f'hotRows{tag}', str(h['rows']))
    put(f'hotShare{tag}', pct(h['nonwriter_share_p50']))
    put(f'hotShareR{tag}', pct(h['nonwriter_share_p50'], 0))
    put(f'hotShareLo{tag}', pct(h['nonwriter_share_p25'], 0))
    put(f'hotShareHi{tag}', pct(h['nonwriter_share_p75'], 0))
    put(f'hotShareMean{tag}', pct(h['nonwriter_share_mean']))
    put(f'hotShareStrict{tag}', pct(h['nonwriter_share_strict_p50']))
    put(f'hotDeclShare{tag}', pct(h['declared_nonwriter_share_p50']))
    put(f'declLimMed{tag}', pct(h['declared_over_limit_p50']))
    put(f'declLimNinety{tag}', f"{h['declared_over_limit_p90']:.1f}")
    put(f'declLimMax{tag}', f"{h['declared_over_limit_max']:.1f}")
    put(f'declHalfRows{tag}', pct(h['rows_declared_half_limit'] / h['rows'], 0))
    put(f'declFullRows{tag}', pct(h['rows_declared_full_limit'] / h['rows'], 0))
    put(f'usedHalfRows{tag}', str(h['rows_used_half_limit']))
    put(f'usedLimMed{tag}', pct(h['used_over_limit_p50']))
    put(f'usedLimNinety{tag}', pct(h['used_over_limit_p90'], 0))
    put(f'usedLimMax{tag}', pct(h['used_over_limit_max']))
    put(f'usedOverDeclHot{tag}', pct(h['used_over_declared_p50'], 0))
    put(f'feeWriters{tag}', thousands(int(round(h['lamports_per_mcu_writers'], -3) / 1000)))
    put(f'feeNonwriters{tag}', thousands(int(round(h['lamports_per_mcu_nonwriters'], -3) / 1000)))
    put(f'feeRatio{tag}', f"{h['lamports_per_mcu_nonwriters'] / h['lamports_per_mcu_writers']:.2f}")
    put(f'nSenders{tag}', thousands(s['senders']))
    put(f'nFailSenders{tag}', thousands(s['failed_senders']))
    put(f'topHundredFail{tag}', pct(s['concentration']['100']['share_of_failures'], 0))
    put(f'topHundredRate{tag}', pct(s['concentration']['100']['own_failure_rate'], 0))
    put(f'topHundredDecl{tag}', pct(s['concentration']['100']['share_of_failed_writable_declarations'], 0))
    pc, inc = r['placement_cost'], r['incidence']
    for thr, name in (('0.25', 'Lo'), ('0.5', 'Mid'), ('0.75', 'Hi')):
        put(f'placeFirm{name}{tag}', pct(pc[thr]['menu_over_firm'], 0))
        put(f'placeSoft{name}{tag}', pct(pc[thr]['menu_over_soft'], 0))
    put(f'incOkFree{tag}', pct(inc['share_ok_tx_no_charge'], 0))
    put(f'incTopHundred{tag}', pct(inc['share_top100_senders'], 0))
    put(f'incSenders{tag}', thousands(inc['senders']))
    put(f'incFailedCharge{tag}', pct(inc['share_charge_failed_tx'], 0))
    put(f'incFailedTx{tag}', pct(inc['share_failed_tx'], 0))
    put(f'incOverUsage{tag}', pct(inc['charges_over_usage_fees'], 0))
    put(f'incOverUsageSigners{tag}', pct(inc['charges_over_usage_fees_with_signers'], 0))
    for key, name in (('sender_account', 'Pair'), ('sender', 'Sender'), ('account', 'Acct'), ('none', 'None')):
        put(f'src{name}{tag}', pct(r['estimate_sources'][key], 0))
    put(f'pairCover{tag}', pct(u['declarations_in_pairs_seen_3plus'] / d['writable_nonsigner'], 0))
    for order, pre in (('block', ''), ('free', 'free')):
        occ = r['occupier'][order]
        for n, nm in (('1', 'One'), ('5', 'Five'), ('20', 'Twenty')):
            for pol, pn in (('firm', 'Firm'), ('menu', 'Menu'), ('menu_soft', 'MenuSoft'), ('menu_read', 'MenuRead'), ('soft', 'Soft')):
                inc_ = occ[n][pol]['makespan_increase']
                put(f'{pre}{"occ" if not pre else "Occ"}{pn}{nm}{tag}', pct(inc_, 0 if abs(inc_) >= 0.1 else 1))
                assert occ[n][pol]['serializable_all']
        put(f'{pre}{"occ" if not pre else "Occ"}MenuAbs{tag}', f"{occ['5']['menu']['with_over_firm_with']:.2f}")
        put(f'{pre}{"occ" if not pre else "Occ"}MenuSoftAbs{tag}', f"{occ['5']['menu_soft']['with_over_firm_with']:.2f}")
    put(f'txPerBlock{tag}', f"{m['transactions'] / m['blocks']:.0f}")
    put(f'brier{tag}', f"{s['brier']:.3f}")
    put(f'brierBase{tag}', f"{s['brier_constant']:.3f}")
    put(f'holdout{tag}', thousands(s['holdout_declarations']))
    put(f'qZero{tag}', pct(u['share_q0'], 0))
    put(f'qOne{tag}', pct(u['share_q1'], 0))
    put(f'qBetween{tag}', pct(u['share_between'], 0))
    for thr, name in (('0.25', 'Lo'), ('0.5', 'Mid'), ('0.75', 'Hi')):
        put(f'freed{name}{tag}', pct(l[thr]['freed_share_aggregate'], 0))
        put(f'freedDecl{name}{tag}', pct(l[thr]['freed_declared_share_aggregate'], 0))
        put(f'softWrites{name}{tag}', pct(l[thr]['share_of_writes_declared_soft'], 0))
    for order, pre in (('block', ''), ('free', 'free')):
        rp = r['replay'][order]

        def mac(name):
            return (pre + cap(name) if pre else name) + nm + tag

        for n, nm in ((4, 'Four'), (8, 'Eight'), (16, 'Sixteen'), (32, 'Thirtytwo')):
            row = rp['reads'][f'threads={n}']
            rows = rp['reads_strict_proxy'][f'threads={n}']
            roww = rp['writes'][f'threads={n}']
            put(mac('firmBound'), f"{row['firm_over_capacity_bound']:.2f}")
            put(mac('oracleBound'), f"{row['firm_over_capacity_bound'] * row['oracle']['makespan_over_firm']:.2f}")
            put(mac('oracleCut'), pct(1 - row['oracle']['makespan_over_firm'], 0))
            put(mac('oracleRatio'), f"{row['oracle']['makespan_over_firm']:.2f}")
            put(mac('softCut'), pct(1 - row['soft']['makespan_over_firm'], 0))
            put(mac('softWaste'), pct(row['soft']['wasted_share'], 0))
            put(mac('softRatio'), f"{row['soft']['makespan_over_firm']:.2f}")
            for thr, name in (('0.25', 'Lo'), ('0.5', 'Mid'), ('0.75', 'Hi')):
                put(mac(f'menu{name}Cut'), pct(1 - row[f'menu_payer@{thr}']['makespan_over_firm'], 0))
                put(mac(f'menu{name}Waste'), pct(row[f'menu_payer@{thr}']['wasted_share'], 0))
                put(mac(f'menu{name}Ratio'), f"{row[f'menu_payer@{thr}']['makespan_over_firm']:.2f}")
                put(mac(f'acct{name}Ratio'), f"{row[f'menu_acct@{thr}']['makespan_over_firm']:.2f}")
            put(mac('postedRatio'), f"{row['menu_posted@3']['makespan_over_firm']:.2f}")
            put(mac('postedWaste'), pct(row['menu_posted@3']['wasted_share'], 0))
            bb = row['menu_payer@0.25']['by_block']
            put(mac('menuLoMedian'), f"{bb['median_ratio']:.2f}")
            put(mac('menuLoSlower'), str(bb['blocks_slower']))
            put(mac('menuLoCutCiLo'), pct(bb['cut_ci95'][0], 0))
            put(mac('menuLoCutCiHi'), pct(bb['cut_ci95'][1], 0))
            put(mac('firmMeanBudget'), of_budget(row['firm']['by_block']['mean_time']))
            put(mac('firmMaxBudget'), of_budget(row['firm']['by_block']['max_time']))
            put(mac('menuLoMeanBudget'), of_budget(bb['mean_time']))
            put(mac('menuLoMaxBudget'), of_budget(bb['max_time']))
            put(mac('strictOracleCut'), pct(1 - rows['oracle']['makespan_over_firm'], 0))
            put(mac('strictMenuLoCut'), pct(1 - rows['menu_payer@0.25']['makespan_over_firm'], 0))
            put(mac('writesOracleCut'), pct(1 - roww['oracle']['makespan_over_firm'], 0))
            put(mac('writesMenuLoCut'), pct(1 - roww['menu_payer@0.25']['makespan_over_firm'], 0))
            put(mac('writesMenuLoWaste'), pct(roww['menu_payer@0.25']['wasted_share'], 0))
            put(mac('writesSoftCut'), pct(1 - roww['soft']['makespan_over_firm'], 0))
            for name_, pol_ in list(row.items()) + list(rows.items()) + list(roww.items()):
                if isinstance(pol_, dict):
                    assert pol_['serializable_all'], name_

put('nBlocksHalf', str(A['meta']['blocks'] // 2))
put('nFailuresA', thousands(A['senders']['failures']))
ta, tb = day(A['meta']['t_min']), day(B['meta']['t_min'])
te = day(B['meta']['t_max'])
put('sampleGapDays', str((tb.date() - ta.date()).days))
put('sampleAdate', 'October 15--16, 2026')
put('sampleBdate', f'{tb.strftime("%B")} {tb.day}' + (f'--{te.day}' if te.month == tb.month else f' to {te.strftime("%B")} {te.day}') + ', 2026')

# ------------------------------------------------------------------ extended replay
for tag, e in EXT.items():
    r = {'A': A, 'B': B}[tag]
    h = r['hot']
    put(f'billToday{tag}', f"{1.4 * h['lamports_per_mcu_nonwriters'] / 1e9:.4f}")
    put(f'billFive{tag}', f"{5 * 1.4 * h['lamports_per_mcu_nonwriters'] / 1e9:.4f}")
    ro = e['read_only']
    put(f'roWritten{tag}', pct(ro['share_on_account_written_in_block'], 0))
    for order, pre in (('block', ''), ('free', 'free')):
        for view, vw in (('reads', ''), ('writes', 'Writes')):
            for n, nm in ((4, 'Four'), (8, 'Eight'), (16, 'Sixteen')):
                row = e['replay'][order][view][f'threads={n}']

                def x(name):
                    return (pre + cap(name) if pre else name) + vw + nm + tag

                put(x('rOverC'), f"{row['soft_over_firm_unused']:.2f}")
                put(x('rOverCPct'), pct(row['soft_over_firm_unused'], 0))
                put(x('perfectRatio'), f"{row['perfect']['over_firm']:.2f}")
                put(x('perfectWaste'), pct(row['perfect']['wasted_share'], 0))
                put(x('failedOnlyRatio'), f"{row['menu_failed']['over_firm']:.2f}")
                put(x('okOnlyRatio'), f"{row['menu_ok']['over_firm']:.2f}")
                put(x('leadSoft'), pct(row['menu_lead_over_soft']['point'], 0))
                put(x('leadSoftLo'), pct(row['menu_lead_over_soft']['ci95'][0], 0))
                put(x('leadSoftHi'), pct(row['menu_lead_over_soft']['ci95'][1], 0))
                put(x('leadPerfect'), pct(row['perfect_lead_over_menu']['point'], 0))
                put(x('leadPerfectLo'), pct(row['perfect_lead_over_menu']['ci95'][0], 0))
                put(x('leadPerfectHi'), pct(row['perfect_lead_over_menu']['ci95'][1], 0))
                for th, nmt in (('0.25', 'Lo'), ('0.75', 'Hi')):
                    put(x(f'useCost{nmt}'), f"{row[f'menu@{th}']['wasted_over_soft_used']:.2f}")
                if view == 'reads':
                    bl = row['by_load']
                    put(x('topMenuRatio'), f"{bl['menu@0.25']['top_over_firm']:.2f}")
                    put(x('restMenuRatio'), f"{bl['menu@0.25']['rest_over_firm']:.2f}")
                    put(x('restMenuCut'), pct(1 - bl['menu@0.25']['rest_over_firm'], 0))
                    put(x('topMenuCut'), pct(1 - bl['menu@0.25']['top_over_firm'], 0))
                    put(x('topMenuCutLo'), pct(bl['menu@0.25']['top_ci95_cut'][0], 0))
                    put(x('topMenuCutHi'), pct(bl['menu@0.25']['top_ci95_cut'][1], 0))
    put(f'topComputeM{tag}', f"{e['replay']['free']['reads']['threads=16']['by_load']['top_mean_compute'] / 1e6:.0f}")
    put(f'restComputeM{tag}', f"{e['replay']['free']['reads']['threads=16']['by_load']['rest_mean_compute'] / 1e6:.0f}")
    for order, pre in (('block', ''), ('free', 'free')):
        for n, nm in ((4, 'Four'), (16, 'Sixteen')):
            for tau, tn in (('0.05', 'Low'), ('0.25', 'Mid')):
                f = e['one_fee'][order][f'threads={n}'][tau]

                def y(name):
                    return (pre + cap(name) if pre else name) + tn + nm + tag

                put(y('oneFeeRatio'), f"{f['over_firm']:.2f}")
                if not pre and n == 16:
                    put(f'oneFeeDropped{tn}{tag}', pct(f['dropped_share'], 0))
                    put(f'oneFeeReverted{tn}{tag}', pct(f['reverted_share_of_successful']))
                    put(f'oneFeeRevertedCu{tn}{tag}', pct(f['reverted_compute_share'], 0))
                    put(f'oneFeeRevertedFee{tn}{tag}', pct(f['reverted_priority_fee_share'], 0))

put('blockRWritesMaxPct', pct(max(EXT[t]['replay'][o][v]['threads=16']['soft_over_firm_unused'] for t in 'AB' for o in ('block', 'free') for v in ('reads', 'writes')), 0))

# ------------------------------------------------------------------ who holds the hot accounts
OCC = {'A': read('occupancy_day1.json'), 'B': read('occupancy_day2.json')}
UNREF = read('facts_unreferenced.json')
put('unrefDecl', thousands(UNREF['writable_nonsigner']))
put('unrefBlocks', str(UNREF['blocks']))
put('unrefCount', 'none' if UNREF['writable_unreferenced'] == 0 else thousands(UNREF['writable_unreferenced']))
for tag, o in OCC.items():
    sh, de = o['shares_of_hot_lock_time'], o['shares_of_hot_declared_compute']
    put(f'hotWritten{tag}', pct(sh['written'], 0))
    put(f'hotWrittenDecl{tag}', pct(de['written'], 0))
    put(f'hotOkUnwritten{tag}', pct(sh['ok_token_unchanged'] + sh['ok_route_leg'], 0))
    put(f'hotFailWon{tag}', pct(sh['failed_sender_won_here'] + sh['failed_sender_won_elsewhere'], 0))
    put(f'hotNever{tag}', pct(sh['failed_never_won_repeat'], 0))
    put(f'hotNeverDecl{tag}', pct(de['failed_never_won_repeat'], 0))
    nv = o['senders_never_won']
    put(f'neverSenders{tag}', str(nv['holding_hot']))
    put(f'neverTx{tag}', thousands(nv['tx']))
    put(f'topHundredUnwritten{tag}', pct(o['top100_share_of_unwritten_hot_time'], 0))
    put(f'sameBlock{tag}', pct(o['share_of_unwritten_hot_time_by_senders_writing_it_in_the_block'], 0))
    put(f'posAll{tag}', f"{o['position_in_block_median']['all_unwritten']:.2f}")
    put(f'feeNever{tag}', thousands(int(round(o['priority_fee_per_mcu']['failed_never_won_repeat'], -3) / 1000)))
    put(f'feeNeverPerCu{tag}', f"{o['priority_fee_per_mcu']['failed_never_won_repeat'] / 1e6:.2f}")
    put(f'feeWritersPerCu{tag}', f"{(A if tag == 'A' else B)['hot']['lamports_per_mcu_writers'] / 1e6:.2f}")
    h = o['harm_at_16_threads']
    for order, nm in (('block', 'Block'), ('free', 'Free')):
        full = 1 - h[order]['all']['over_firm']
        put(f'harmTopHundred{nm}{tag}', pct((1 - h[order]['top100']['over_firm']) / full, 0))
        put(f'harmNever{nm}{tag}', pct((1 - h[order]['never_won']['over_firm']) / full, 0))
    put(f'topHundredTx{tag}', pct(h['replayed_tx_share']['top100'], 0))

# ------------------------------------------------------------------ Avalanche, before and after the charge on unused gas
AV = read('facts_avax_response.json')['sender_target_function']
ex, un = AV['exposed'], AV['unexposed']
put('avaxExposedCalls', str(ex['calls']))
put('avaxExposedRatio', f"{ex['limit_ratio_median']:.2f}")
put('avaxExposedLo', f"{ex['limit_ratio_ci95'][0]:.2f}")
put('avaxExposedHi', f"{ex['limit_ratio_ci95'][1]:.2f}")
put('avaxExposedCut', str(ex['cut']))
put('avaxUnexposedCalls', str(un['calls']))
put('avaxUnexposedRatio', f"{un['limit_ratio_median']:.2f}")
assert un['cut'] == 0
put('avaxFailBefore', str(ex['before']['failed']))
put('avaxTxBefore', str(ex['before']['txs']))
put('avaxFailAfter', str(ex['after']['failed']))
put('avaxTxAfter', str(ex['after']['txs']))

# ------------------------------------------------------------------ read-only declarations and what a hold costs, on the two samples
READS = {'A': read('reads_day1.json'), 'B': read('reads_day2.json')}
HOLD = {'A': read('hold_day1.json'), 'B': read('hold_day2.json')}
THREAD_NAMES = ((4, 'Four'), (8, 'Eight'), (16, 'Sixteen'), (32, 'Thirtytwo'))
for tag, rd in READS.items():
    for n, nm in THREAD_NAMES:
        told = rd[f'threads={n}']['block']['told']
        put(f'toldRatio{nm}{tag}', f"{told['over_firm']:.2f}")
        put(f'toldCut{nm}{tag}', pct(1 - told['over_firm'], 0))
        assert told['wasted_share'] == 0
        put(f'softReadBlockRatio{nm}{tag}', f"{rd[f'threads={n}']['block']['menu+softread']['over_firm']:.2f}")
        put(f'softReadBlockWaste{nm}{tag}', pct(rd[f'threads={n}']['block']['menu+softread']['wasted_share'], 0))
        put(f'softReadFreeRatio{nm}{tag}', f"{rd[f'threads={n}']['free']['menu+softread']['over_firm']:.2f}")
        put(f'softReadFreeWaste{nm}{tag}', pct(rd[f'threads={n}']['free']['menu+softread']['wasted_share'], 0))
    for n, nm in ((4, 'Four'), (16, 'Sixteen')):
        row = rd[f'threads={n}']
        for order, od in (('block', 'Block'), ('free', 'Free')):
            for head, hn in (('firm', 'Firm'), ('read', 'Read'), ('soft', 'Soft'), ('softread', 'SoftRead')):
                v = row[order]['occ_' + head]['increase']
                put(f'hold{od}{hn}{nm}{tag}', pct(max(v, 0.0), 0 if abs(v) >= 0.1 else 1))
        v = row['block']['occ_told_softread']['increase']
        put(f'holdTold{nm}{tag}', pct(max(v, 0.0), 0 if abs(v) >= 0.1 else 1))
    put(f'toldMaxBudget{tag}', of_budget(rd['threads=16']['block']['told']['max_time']))
for tag, h in HOLD.items():
    bill, pl = h['bill'], h['places']
    put(f'billWriters{tag}', f"{bill['five_at_writers_price_lamports'] / 1e9:.4f}")
    put(f'billNonwriters{tag}', f"{bill['five_at_nonwriters_price_lamports'] / 1e9:.4f}")
    put(f'billWritersShare{tag}', pct(bill['five_at_writers_over_block_priority'], 0))
    later = [pl['block'][x] for x in ('0.25', '0.5', '0.75')]
    put(f'billLocalLo{tag}', pct(min(v['bill_median_over_block_priority'] for v in later), 0))
    put(f'billLocalHi{tag}', pct(max(v['bill_median_over_block_priority'] for v in later), 0))
    put(f'billLocalSol{tag}', f"{sum(v['bill_median_lamports'] for v in later) / 3 / 1e9:.4f}")
    put(f'billHourSol{tag}', f"{sum(v['bill_median_lamports'] for v in later) / 3 / 1e9 * 5 * 3600:.0f}")
    put(f'blockPrioSol{tag}', f"{h['fees']['priority_per_block_lamports'] / 1e9:.4f}")
    for x, nm in (('0.0', 'Head'), ('0.25', 'Quarter'), ('0.5', 'Half'), ('0.75', 'Late')):
        put(f'placeBlock{nm}{tag}', pct(pl['block'][x]['increase'], 0))
        put(f'placeFree{nm}{tag}', pct(pl['free'][x]['increase'], 0))
    put(f'placeBlockLo{tag}', pct(min(pl['block'][x]['increase'] for x in pl['block']), 0))
    put(f'placeBlockHi{tag}', pct(max(pl['block'][x]['increase'] for x in pl['block']), 0))
    put(f'placeFreeLo{tag}', pct(min(pl['free'][x]['increase'] for x in pl['free']), 0))
    put(f'placeFreeHi{tag}', pct(max(pl['free'][x]['increase'] for x in pl['free']), 0))
    put(f'serialMedian{tag}', pct(h['serial_over_block_time']['median'], 0))
    u = h['use_over_budget']
    put(f'useFirmMedian{tag}', pct(u['firm']['median'], 1))
    put(f'useClassMedian{tag}', pct(u['classes']['median'], 1))
    for x, nm in (('0.1', 'Tenth'), ('0.25', 'Quarter'), ('0.5', 'Half')):
        put(f'useClassAt{nm}{tag}', pct(u['classes'][f'share_at_{x}'], 1))

# ------------------------------------------------------------------ whole minutes of consecutive blocks
BUSY = read('facts_busy_minutes.json')
BUSY2 = read('facts_busy_minutes_nov2.json')
PLAN = read('facts_windows_plan.json')
NAMES = read('facts_minutes.json')
DRAFT = bool(os.environ.get('DF_DRAFT'))    # while minutes are still being analyzed: only those that are done
if DRAFT:
    NAMES = {t: s for t, s in NAMES.items()
             if all((RES / f'{k}_{t}.json').exists() for k in ('paper_numbers', 'paper_extensions', 'occupancy', 'reads', 'hold', 'frontier', 'soft_last', 'failed_only'))}
TPS = {w['name']: w['tps'] for w in PLAN if w['kind'] != 'extension'}
for tag_, w in zip(('c1', 'c2', 'c3'), BUSY['windows']):
    TPS[f'solana_{tag_}_v4.jsonl+solana_{tag_}x.jsonl.gz'] = w['tps']


def minute_metrics(tag):
    pn, pe, po = read(f'paper_numbers_{tag}.json'), read(f'paper_extensions_{tag}.json'), read(f'occupancy_{tag}.json')
    rd, hd, fr, sl = read(f'reads_{tag}.json'), read(f'hold_{tag}.json'), read(f'frontier_{tag}.json'), read(f'soft_last_{tag}.json')
    fo = read(f'failed_only_{tag}.json')
    tips_recorded = '_v4' not in NAMES[tag]     # the minutes of November 1 were first recorded without tips
    if not tips_recorded:
        fr.pop('with_tips', None)
    m = {'Tps': TPS[NAMES[tag]], 'Blocks': pn['meta']['blocks'], 'Tx': pn['meta']['transactions'], 'Seconds': pn['meta']['t_max'] - pn['meta']['t_min'],
         'ShareFailed': 100 * pn['meta']['share_failed'], 'NotWritten': 100 * pn['declarations']['share_not_written_v3'],
         'UsedLimMed': 100 * pn['hot']['used_over_limit_p50'], 'RepBlocks': rd['blocks']}
    sh = po['shares_of_hot_lock_time']
    m['HotWritten'] = 100 * sh['written']
    m['HotWonHere'] = 100 * sh['failed_sender_won_here']
    m['HotFailed'] = 100 * (sh['failed_sender_won_here'] + sh['failed_sender_won_elsewhere'] + sh['failed_never_won_repeat'] + sh['failed_never_won_once'])
    blk = pn['replay']['block']['reads']['threads=16']
    m['FirmMax'] = 100 * blk['firm']['by_block']['max_time'] / BUDGET
    m['MenuMax'] = 100 * blk['menu_payer@0.25']['by_block']['max_time'] / BUDGET
    m['FirmMean'] = 100 * blk['firm']['by_block']['mean_time'] / BUDGET
    m['ToldMax'] = 100 * rd['threads=16']['block']['told']['max_time'] / BUDGET
    for order, od in (('free', 'Free'), ('block', 'Block')):
        for n, nm in ((4, 'Four'), (16, 'Sixteen')):
            row = pn['replay'][order]['reads'][f'threads={n}']
            m[f'{od}Cut{nm}'] = 100 * (1 - row['menu_payer@0.25']['makespan_over_firm'])
            m[f'{od}Waste{nm}'] = 100 * row['menu_payer@0.25']['wasted_share']
            m[f'{od}Oracle{nm}'] = 100 * (1 - row['oracle']['makespan_over_firm'])
            ex = pe['replay'][order]['reads'][f'threads={n}']
            m[f'{od}ROverC{nm}'] = ex['soft_over_firm_unused']
            m[f'{od}LeadSoft{nm}'] = 100 * ex['menu_lead_over_soft']['point']
        m[f'{od}ROverCWrites'] = pe['replay'][order]['writes']['threads=16']['soft_over_firm_unused']
        hh = po['harm_at_16_threads'][order]
        m[f'HarmHundred{od}'] = 100 * (1 - hh['top100']['over_firm']) / (1 - hh['all']['over_firm'])
    for n, nm in ((4, 'Four'), (16, 'Sixteen')):
        m[f'Told{nm}'] = 100 * (1 - rd[f'threads={n}']['block']['told']['over_firm'])
        for order, od in (('block', 'Block'), ('free', 'Free')):
            m[f'SoftRead{od}{nm}'] = rd[f'threads={n}'][order]['menu+softread']['over_firm']
            for head, hn in (('firm', 'Firm'), ('read', 'Read'), ('soft', 'Soft'), ('softread', 'SoftRead')):
                m[f'Hold{od}{hn}{nm}'] = 100 * max(0.0, rd[f'threads={n}'][order]['occ_' + head]['increase'])
        m[f'HoldTold{nm}'] = 100 * max(0.0, rd[f'threads={n}']['block']['occ_told_softread']['increase'])
    fee = pe['one_fee']['block']['threads=16']['0.05']
    m['OneFeeReverted'] = 100 * fee['reverted_share_of_successful']
    m['OneFeeRevertedFee'] = 100 * fee['reverted_priority_fee_share']
    m['OneFeeFree'] = pe['one_fee']['free']['threads=16']['0.05']['over_firm']
    lead = fr['lead']['m=3']
    m['FrOne'] = 100 * lead['one'][-1]['lost']
    m['FrTwo'] = 100 * lead['two']['producer_16'][-1]['lost']
    if 'with_tips' in fr:
        m['FrOneTips'] = 100 * fr['with_tips']['one'][-1]['lost']
        m['FrOneSame'], m['FrTwoSame'] = m['FrOne'], m['FrTwo']
        m['FrTwoTips'] = 100 * fr['with_tips']['two']['producer_16'][-1]['lost']
    s16 = sl['theta=0.25']['free']['threads=16']
    m['SlRank'], m['SlLast'] = s16['rank_over_firm'], s16['last_over_firm']
    if tips_recorded and 'tips' in hd:
        m['TipShare'] = 100 * hd['tips']['tip_share_of_payment']
        m['TipTx'] = 100 * hd['tips']['share_of_tx']
        m['TipsFailed'] = hd['tips']['tips_in_failed_tx']
    m['ClassUseMedian'] = 100 * hd['use_over_budget']['classes']['median']
    m['ClassUseAtTenth'] = 100 * hd['use_over_budget']['classes']['share_at_0.1']
    m['ClassUseAtQuarter'] = 100 * hd['use_over_budget']['classes']['share_at_0.25']
    m['SerialMedian'] = 100 * hd['serial_over_block_time']['median']
    later = [hd['places']['block'][x] for x in ('0.25', '0.5', '0.75')]
    m['PlaceBlock'] = 100 * sum(v['increase'] for v in later) / 3
    m['PlaceFree'] = 100 * sum(hd['places']['free'][x]['increase'] for x in ('0.25', '0.5', '0.75')) / 3
    m['BillLocalShare'] = 100 * sum(v['bill_median_over_block_priority'] for v in later) / 3
    m['BillLocalSol'] = sum(v['bill_median_lamports'] for v in later) / 3 / 1e9
    m['BillWriters'] = 100 * hd['bill']['five_at_writers_over_block_priority']
    every = [hd['places']['block'][x]['increase'] for x in ('0.0', '0.25', '0.5', '0.75')]
    m['PlaceSpread'] = 100 * (max(every) - min(every))
    for order, od in (('free', 'Free'), ('block', 'Block')):
        m[f'FailedOnly{od}'] = fo[order]['menu_failed']
        m[f'OkOnly{od}'] = fo[order]['menu_ok']
        m[f'FailedShare{od}'] = 100 * (fo[order]['firm'] - fo[order]['menu_failed']) / max(1e-9, fo[order]['firm'] - fo[order]['menu'])
    bl = pe['replay']['free']['reads']['threads=16']['by_load']['menu@0.25']
    m['TopCut'] = 100 * (1 - bl['top_over_firm'])
    m['RestCut'] = 100 * (1 - bl['rest_over_firm'])
    for tgt, nm in (('0.05', 'Twentieth'), ('0.1', 'Tenth'), ('0.25', 'Quarter')):
        path = hd['price_path'][tgt]
        m[f'PathAbove{nm}'] = 100 * path['share_of_blocks_above_target']
        m[f'PathHold{nm}'] = path['with_hold']['mean_price_median']
        m[f'PathFree{nm}'] = path['without_hold']['mean_price_median']
    return m, pn, pe, sl, fr


MINUTE = {tag: minute_metrics(tag) for tag in NAMES}
PEAK = [t for t in NAMES if t.startswith('w')]
MEDIAN = [t for t in NAMES if t.startswith('m')]
if DRAFT and not MEDIAN:
    MEDIAN = PEAK
TABLE = {'peak': {}, 'median': {}}
for group, prefix, tags in (('peak', 'win', PEAK), ('median', 'med', MEDIAN)):
    for key in MINUTE[tags[0]][0]:
        vals = sorted(MINUTE[t][0][key] for t in tags if key in MINUTE[t][0])
        if not vals:
            continue
        low, high = vals[0], vals[-1]
        mid = vals[len(vals) // 2] if len(vals) % 2 else (vals[len(vals) // 2 - 1] + vals[len(vals) // 2]) / 2
        TABLE[group][key] = [low, mid, high]
        d = 2 if key.startswith(('OneFeeFree', 'Sl', 'SoftRead', 'FailedOnly', 'OkOnly')) or 'ROverC' in key else 0
        if key in ('OneFeeReverted', 'TipShare', 'TipTx', 'ClassUseMedian', 'ClassUseAtTenth', 'ClassUseAtQuarter', 'HoldToldSixteen', 'HoldFreeSoftSixteen', 'HoldFreeSoftReadSixteen', 'HoldBlockSoftReadSixteen', 'PathFreeQuarter', 'PathFreeTenth'):
            d = 1
        put(f'{prefix}{key}Min', f'{low:.{d}f}')
        put(f'{prefix}{key}Med', f'{mid:.{d}f}')
        put(f'{prefix}{key}Max', f'{high:.{d}f}')
(HERE / 'numbers_minutes.json').write_text(json.dumps(TABLE, indent=1), encoding='utf-8')
put('nPeak', str(len(PEAK)))
put('nMedian', str(len(MEDIAN)))
put('nMinutes', str(len(NAMES)))
put('nTopAbove', str(sum(MINUTE[t][0]['TopCut'] > MINUTE[t][0]['RestCut'] for t in NAMES)))
put('nPathNear', str(sum(MINUTE[t][0]['PathFreeQuarter'] < 1.05 for t in NAMES)))


def rank_correlation(key_x, key_y):
    def ranks(key):
        vals = sorted(MINUTE[t][0][key] for t in NAMES)
        return [vals.index(MINUTE[t][0][key]) for t in NAMES]
    rx, ry = ranks(key_x), ranks(key_y)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    return num / (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** .5


put('rankTpsFree', f"{rank_correlation('Tps', 'FreeCutSixteen'):.2f}")
put('rankTpsBlock', f"{rank_correlation('Tps', 'BlockCutSixteen'):.2f}")
put('placeSpreadAll', f"{max(MINUTE[t][0]['PlaceSpread'] for t in NAMES):.0f}")
put('frRatioMin', f"{min(MINUTE[t][0]['FrTwo'] / MINUTE[t][0]['FrOne'] for t in NAMES):.2f}")
put('frRatioMax', f"{max(MINUTE[t][0]['FrTwo'] / MINUTE[t][0]['FrOne'] for t in NAMES):.2f}")
put('nTipMinutes', str(sum('TipShare' in MINUTE[t][0] for t in NAMES)))
assert all(MINUTE[t][0].get('TipsFailed', 0) == 0 for t in NAMES)
RETRY = {'A': read('retry_day1.json'), 'B': read('retry_day2.json')}
for tag, rt in RETRY.items():
    row = rt['threads=16']
    put(f'retryWaste{tag}', pct(row['menu@0.25|retry']['wasted_share'], 0))
    put(f'retryRatio{tag}', f"{row['menu@0.25|retry']['over_firm']:.2f}")
    put(f'retryHold{tag}', pct(row['occ_soft']['increase'], 0))
put('nMinuteBlocks', thousands(sum(MINUTE[t][0]['Blocks'] for t in NAMES)))
put('nMinuteTx', thousands(sum(MINUTE[t][0]['Tx'] for t in NAMES)))
put('winRecordHours', f"{(BUSY['records'] + BUSY2['records']) / 60:.0f}")
put('winTpsLo', thousands(round(min(MINUTE[t][0]['Tps'] for t in PEAK))))
put('winTpsHi', thousands(round(max(MINUTE[t][0]['Tps'] for t in PEAK))))
put('winTpsMedianOne', thousands(round(BUSY['tps_median'])))
put('winTpsMedianTwo', thousands(round(BUSY2['tps_median'])))
M['blockRWritesMaxPct'] = pct(max([EXT[t]['replay'][o][v]['threads=16']['soft_over_firm_unused'] for t in 'AB' for o in ('block', 'free') for v in ('reads', 'writes')]
                                  + [MINUTE[t][2]['replay'][o][v]['threads=16']['soft_over_firm_unused'] for t in NAMES for o in ('block', 'free') for v in ('reads', 'writes')]), 0)

# ------------------------------------------------------------------ the trade-off of Theorem 5.6 on Solana
def at_lost(points, x, key):
    pts = sorted(((p['lost'], p[key]) for p in points), key=lambda v: v[0])
    if x >= pts[-1][0]:
        return pts[-1][1]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x0 <= x <= x1:
            return y0 if x1 == x0 else y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return pts[0][1]


FR = {'A': read('frontier_day1.json'), 'B': read('frontier_day2.json')}
FR.update({t: MINUTE[t][4] for t in NAMES})
SIXTEEN = ('producer_16', 'validator_16', 'validator_16_writes')
points = violations = 0
for fr in FR.values():
    curves = [(fr['lead'][m]['one'], fr['lead'][m]['two'][n]) for m in ('m=1', 'm=3', 'm=10', 'm=30', 'm=100') for n in SIXTEEN]
    curves += [(fr[lab]['one'], fr[lab]['two'][n]) for lab in ('uniform_price', 'raw_q', 'with_tips') if lab in fr for n in SIXTEEN]
    curves += [(fr['lead']['m=3']['one'], fr['alt_k'][n]) for n in SIXTEEN]
    for one, two in curves:
        for p in two:
            points += 1
            violations += p['unpaid'] > at_lost(one, p['lost'], 'unpaid') + 1e-9
print('frontier points at 16 threads', points, 'outside the one-class curve', violations)
put('frPoints', thousands(points))
put('frPointsInside', 'all' if violations == 0 else thousands(points - violations))
gaps = {'free': [], 'block': []}
for tag in 'AB':
    fr = FR[tag]
    lead = fr['lead']['m=3']
    two = lead['two']['producer_16']
    put(f'frOneLost{tag}', pct(lead['one'][-1]['lost']))
    put(f'frOneLostR{tag}', pct(lead['one'][-1]['lost'], 0))
    put(f'frTwoLost{tag}', pct(two[-1]['lost']))
    put(f'frTwoLostR{tag}', pct(two[-1]['lost'], 0))
    put(f'frTwoWLost{tag}', pct(lead['two']['validator_16_writes'][-1]['lost']))
    put(f'frLeftLost{tag}', pct(two[0]['lost']))
    put(f'frLeftUnpaid{tag}', pct(two[0]['unpaid']))
    put(f'frLeftRev{tag}', pct(two[0]['reverted_successful']))
    put(f'frOneAtLeft{tag}', pct(at_lost(lead['one'], two[0]['lost'], 'unpaid'), 0))
    for order in gaps:
        gaps[order] += [at_lost(fr['time']['one'], p['lost'], order) - p[order] for p in fr['time']['two']]
for order, nm in (('free', 'Free'), ('block', 'Block')):
    put(f'frGap{nm}Min', f'{100 * min(gaps[order]):.0f}')
    put(f'frGap{nm}Max', f'{100 * max(gaps[order]):.0f}')
put('frGapAllMin', f"{100 * min(gaps['free'] + gaps['block']):.0f}")
put('frGapAllMax', f"{100 * max(gaps['free'] + gaps['block']):.0f}")
wone = [FR[t]['lead']['m=3']['one'][-1]['lost'] for t in PEAK]
wtwo = [FR[t]['lead']['m=3']['two']['producer_16'][-1]['lost'] for t in PEAK]
put('frWinOneMin', pct(min(wone), 0))
put('frWinOneMax', pct(max(wone), 0))
put('frWinTwoMin', pct(min(wtwo), 0))
put('frWinTwoMax', pct(max(wtwo), 0))
# the frontier's end points under other choices, for the appendix table
for tag in 'AB':
    fr = FR[tag]
    cases = {'MThree': (fr['lead']['m=3']['one'], fr['lead']['m=3']['two']['producer_16']),
             'MOne': (fr['lead']['m=1']['one'], fr['lead']['m=1']['two']['producer_16']),
             'MTen': (fr['lead']['m=10']['one'], fr['lead']['m=10']['two']['producer_16']),
             'MThirty': (fr['lead']['m=30']['one'], fr['lead']['m=30']['two']['producer_16']),
             'MHundred': (fr['lead']['m=100']['one'], fr['lead']['m=100']['two']['producer_16']),
             'Uniform': (fr['uniform_price']['one'], fr['uniform_price']['two']['producer_16']),
             'Raw': (fr['raw_q']['one'], fr['raw_q']['two']['producer_16']),
             'KThree': (fr['lead']['m=3']['one'], fr['alt_k']['producer_16'])}
    for case, (one, two) in cases.items():
        put(f'frTab{case}OneEnd{tag}', pct(one[-1]['lost']))
        put(f'frTab{case}TwoEnd{tag}', pct(two[-1]['lost']))
        put(f'frTab{case}LeftLost{tag}', pct(two[0]['lost']))
        put(f'frTab{case}LeftUnpaid{tag}', pct(two[0]['unpaid']))
        put(f'frTab{case}OneAtLeft{tag}', pct(at_lost(one, two[0]['lost'], 'unpaid'), 0))
put('frRatioProducerA', f"{FR['A']['ratios']['producer_16']:.2f}")
put('frRatioValidatorA', f"{FR['A']['ratios']['validator_16_writes']:.2f}")
put('frRatioFourA', f"{FR['A']['ratios']['producer_4']:.2f}")

# ------------------------------------------------------------------ soft transactions last
SL = {'A': read('soft_last_day1.json'), 'B': read('soft_last_day2.json')}
SL.update({t: MINUTE[t][3] for t in NAMES})
for tag in 'AB':
    r = SL[tag]['theta=0.25']
    fr16, bl16 = r['free']['threads=16'], r['block']['threads=16']
    put(f'slFreeRank{tag}', f"{fr16['rank_over_firm']:.2f}")
    put(f'slFreeLast{tag}', f"{fr16['last_over_firm']:.2f}")
    put(f'slBlockRank{tag}', f"{bl16['rank_over_firm']:.2f}")
    put(f'slBlockLast{tag}', f"{bl16['last_over_firm']:.2f}")
    put(f'slFreeRankWaste{tag}', pct(fr16['rank_wasted'], 0))
    put(f'slFreeLastWaste{tag}', pct(fr16['last_wasted'], 0))
    put(f'slMoved{tag}', pct(r['moved_share_of_successful'], 0))
    put(f'slUsed{tag}', pct(r['used_soft_share_of_successful'], 0))
    put(f'slUsedFee{tag}', pct(r['used_soft_share_of_successful_priority_fees'], 0))
wins = [SL[t]['theta=0.25'] for t in PEAK]
put('slWinFreeRankMin', f"{min(w['free']['threads=16']['rank_over_firm'] for w in wins):.2f}")
put('slWinFreeRankMax', f"{max(w['free']['threads=16']['rank_over_firm'] for w in wins):.2f}")
put('slWinFreeLastMin', f"{min(w['free']['threads=16']['last_over_firm'] for w in wins):.2f}")
put('slWinFreeLastMax', f"{max(w['free']['threads=16']['last_over_firm'] for w in wins):.2f}")
everything = [SL[t]['theta=0.25'] for t in SL]
over_budget = sum(x[o][f'threads={n}']['rank_blocks_over_budget'] for x in everything for o in ('free', 'block') for n in (4, 16))
firm_over_budget = sum(x[o][f'threads={n}']['firm_blocks_over_budget'] for x in everything for o in ('free', 'block') for n in (4, 16))
print('blocks at or over the budget with classes', over_budget, 'with every declaration firm', firm_over_budget)
put('slOverBudget', 'no' if over_budget == 0 else str(over_budget))
put('slFirmOverBudget', str(sum(x['block']['threads=16']['firm_blocks_over_budget'] for x in everything)))
put('slClassOverBudget', str(sum(x['block']['threads=16']['rank_blocks_over_budget'] for x in everything)))
put('slAllBlocks', thousands(sum(SL[t]['blocks'] for t in SL)))
put('slHalfMax', str(max(x['free']['threads=16']['rank_blocks_over_half_budget'] for x in everything)))
put('slHalfTotal', str(sum(x['free']['threads=16']['rank_blocks_over_half_budget'] for x in everything)))
put('slBlocksMin', str(min(SL[t]['blocks'] for t in SL)))
put('slBlocksMax', str(max(SL[t]['blocks'] for t in SL)))

# ------------------------------------------------------------------ Sui
s = SUI['successful_mutable_declarations']
put('suiTx', thousands(SUI['transactions']))
put('suiCheckpoints', str(SUI['checkpoints']))
put('suiMutable', thousands(s['all']['n']))
put('suiMid', pct(s['all']['middle_no_direct_child_share']))
put('suiLo', pct(s['all']['strict_lower_share']))
put('suiHi', pct(s['all']['upper_unchanged_share']))
put('suiHotHi', pct(s['heat_100+']['upper_unchanged_share']))
put('suiHotMid', pct(s['heat_100+']['middle_no_direct_child_share']))
put('suiHotLo', pct(s['heat_100+']['strict_lower_share']))
put('suiOneMid', pct(s['heat_1']['middle_no_direct_child_share']))
put('suiFailedMutable', thousands(SUI['failed_mutable_declarations']['n']))

# ------------------------------------------------------------------ Monad and Ethereum
mo, et, al = CAPS['monad'], CAPS['ethereum'], CAPS['ethereum_access_lists']
put('monadTx', thousands(mo['txs']))
put('monadEst', thousands(mo['with_estimate']))
put('monadAggregate', f"{mo['aggregate_estimate_over_limit']:.2f}")
put('monadMedian', f"{mo['p50']:.2f}")
put('monadFeeAbove', pct(mo['share_of_fee_paid_for_gas_above_estimate_lower_bound']))
put('monadAboveLimit', pct(mo['share_estimate_above_limit']))
put('ethTx', thousands(et['txs']))
put('ethAggregate', f"{et['aggregate_used_over_limit']:.2f}")
put('ethMedian', f"{et['p50']:.2f}")
put('ethListShare', pct(et['share_with_access_list'], 2))
put('listsChecked', str(al['txs_checked']))
put('listAddrN', thousands(al['declared_addresses']))
put('listKeyN', thousands(al['declared_keys']))
put('listAddrUnused', pct(al['declared_unused_address_share']))
put('listKeyUnused', pct(al['declared_unused_key_share']))
put('listInexact', pct(al['share_lists_not_exact']))
put('listLoss', pct(al['share_lists_with_net_loss'], 0))
put('listExcessGas', thousands(-al['net_gas_saved_by_lists_total']))

put('suiUnchangedFee', str(round(SUIFEE['unchanged_object_fee_mist_p10_50_90'][1])))
put('suiUnchangedShare', pct(SUIFEE['fee_over_computation_p10_50_90'][1], 2))
put('suiComputationMedian', thousands(int(SUIFEE['computation_cost_mist_p10_50_90'][1])))
put('monadListShare', pct(MONADAL['share_with_access_list']))
put('monadListTx', thousands(MONADAL['n_tx']))
put('ethListShareNov', pct(ETHAL['share_with_access_list'], 2))
put('ethListTxNov', thousands(ETHAL['n_tx']))
put('monadListSenders', str(MONADCONC['n_senders_with_list']))
put('monadAllSenders', str(MONADCONC['n_senders_all']))
put('monadListTopTen', pct(MONADCONC['top10_sender_share_of_list_txs'], 0))
put('monadConcTx', thousands(MONADCONC['n_tx']))
put('monadConcLists', str(MONADCONC['n_list_txs']))

# ------------------------------------------------------------------ access-list thresholds (posted gas schedules)
for name, decl, cold, warm in (('Addr', 2400, 2600, 100), ('Key', 1900, 2100, 100)):
    put(f'listThreshold{name}', f'{float(Fr(decl, cold - warm)):.2f}')

# ------------------------------------------------------------------ prototype
put('nTests', '39')

lines = [f'\\newcommand{{\\{k}}}{{{v}}}' for k, v in sorted(M.items())]
(HERE / 'numbers.tex').write_text('% Generated by make_numbers.py.\n' + '\n'.join(lines) + '\n', encoding='utf-8')
(HERE / 'numbers.json').write_text(json.dumps(M, indent=1), encoding='utf-8')
print(len(M), 'macros')
