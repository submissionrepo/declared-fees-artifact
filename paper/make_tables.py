"""Generate the data tables of the paper from numbers.json (run make_numbers.py first).

tab_measure.tex  What is declared and what is used, by chain.
tab_replay.tex   Replay values behind Fig. 4 for both samples and both orders.
tab_windows.tex  Each window of consecutive blocks.
tab_frontier.tex The end points of Fig. 5 under other choices.
tab_chains.tex and tab_compare.tex hold statements from public documents and from the paper's own
results, and are written by hand.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
N = json.loads((HERE / 'numbers.json').read_text(encoding='utf-8'))
THREADS = [('Four', 4), ('Eight', 8), ('Sixteen', 16), ('Thirtytwo', 32)]


def measure():
    rows = [
        ('Solana, Sample A', f"{N['nWritableA']} writable declarations", f"{N['notWrittenA']}\\% ({N['notWrittenStrictA']}\\%)"),
        ('', 'failed; token; route leg', f"{N['inFailedA']}; {N['tokenUnchA']}; {N['routerLegA']}\\%"),
        ('Solana, Sample B', f"{N['nWritableB']} writable declarations", f"{N['notWrittenB']}\\% ({N['notWrittenStrictB']}\\%)"),
        ('', 'failed; token; route leg', f"{N['inFailedB']}; {N['tokenUnchB']}; {N['routerLegB']}\\%"),
        ('Sui', f"{N['suiMutable']} mutable declarations", f"{N['suiMid']}\\% ({N['suiLo']}--{N['suiHi']}\\%)"),
        ('Ethereum lists', f"{N['listAddrN']} addresses", f"{N['listAddrUnused']}\\%"),
        ('', f"{N['listKeyN']} storage keys", f"{N['listKeyUnused']}\\%"),
        ('Solana, Sample A', f"{N['nTxA']} compute limits", f"{N['usedOverDeclaredA']}"),
        ('Solana, Sample B', f"{N['nTxB']} compute limits", f"{N['usedOverDeclaredB']}"),
        ('Monad', f"{N['monadEst']} gas limits", f"{N['monadAggregate']} (estimated need)"),
        ('Ethereum', f"{N['ethTx']} gas limits", f"{N['ethAggregate']}"),
    ]
    holders = [
        ('Hot lock time: writers; succeeded, not written', f"{N['hotWrittenA']}, {N['hotWrittenB']}; {N['hotOkUnwrittenA']}, {N['hotOkUnwrittenB']}\\%"),
        ('\\quad failed, sender succeeds at times; never', f"{N['hotFailWonA']}, {N['hotFailWonB']}; {N['hotNeverA']}, {N['hotNeverB']}\\%"),
        ('Senders that never succeed: number; transactions', f"{N['neverSendersA']}, {N['neverSendersB']}; {N['neverTxA']}, {N['neverTxB']}"),
        ('\\quad share of declared hot compute', f"{N['hotNeverDeclA']}, {N['hotNeverDeclB']}\\%"),
        ('Non-writers in cost charged, median pair', f"{N['hotShareA']}, {N['hotShareB']}\\%"),
        ('Cost charged over the budget, median pair', f"{N['usedLimMedA']}, {N['usedLimMedB']}\\%"),
        ('\\quad pairs at half the budget, of ' + N['hotRowsA'], f"{N['usedHalfRowsA']}, {N['usedHalfRowsB']}"),
        ('Holders\' place in the block, median', f"{N['posAllA']}, {N['posAllB']}"),
        ('Priority fee, writers; never (lamports per CU)', f"{N['feeWritersPerCuA']}, {N['feeWritersPerCuB']}; {N['feeNeverPerCuA']}, {N['feeNeverPerCuB']}"),
    ]
    out = ['\\begin{table}[t]', '\\centering',
           '\\caption{What is declared and what is used. Upper rows: share of declarations not written (Solana), not changed (Sui) or not in the set the node returned (Ethereum lists), with the stricter count for Solana and the range for Sui in parentheses. Solana includes failed transactions and Sui does not. Middle rows: aggregate use over the declared limit. Lower rows: the five accounts with the most declared compute in each block, Samples A and B.}',
           '\\label{tab:measure}', '\\scriptsize', '\\setlength{\\tabcolsep}{2pt}',
           '\\begin{tabular}{@{}lll@{}}', '\\toprule', 'Chain & Declared & Share unused \\\\', '\\midrule']
    for i, r in enumerate(rows):
        if i == 7:
            out += ['\\midrule', 'Chain & Declared & Use over limit \\\\', '\\midrule']
        out.append(' & '.join(r) + ' \\\\')
    out += ['\\midrule']
    for label, value in holders:
        out.append(f'\\multicolumn{{2}}{{@{{}}l}}{{{label}}} & {value} \\\\')
    out += ['\\bottomrule', '\\end{tabular}', '\\end{table}']
    (HERE / 'tab_measure.tex').write_text('\n'.join(out) + '\n', encoding='utf-8')


def settings():
    def pair(name):
        return f"{N[name + 'A']}, {N[name + 'B']}"

    rows = [
        ('Producer, 4 threads', 'freeRatio', 'Four'),
        ('Producer, 16 threads', 'freeRatio', 'Sixteen'),
        ('Validator, 4 threads', 'ratio', 'Four'),
        ('Validator, 16 threads', 'ratio', 'Sixteen'),
    ]
    out = ['\\begin{table*}[t]', '\\centering',
           '\\caption{What the classes buy and what a hold does, by setting, in pairs for Samples A and B.}',
           '\\label{tab:settings}', '\\footnotesize', '\\setlength{\\tabcolsep}{2.5pt}',
           '\\begin{tabular}{@{}llllllll@{}}', '\\toprule',
           'Setting & $r_o/\\cp_o$ & Foresight & Told & \\begin{tabular}{@{}l@{}}Classes\\\\from writes\\end{tabular} & Menu & All soft & Hold: write; shared lock; soft; soft read (\\%) \\\\', '\\midrule']
    for label, kind, nm in rows:
        pre = 'free' if kind == 'freeRatio' else ''

        def m(name, tag, vw=''):
            key = (pre + name[0].upper() + name[1:] if pre else name) + vw + nm + tag
            return N[key]

        od = 'Free' if pre else 'Block'

        def hold(head):
            return f"{N[f'hold{od}{head}{nm}A']}, {N[f'hold{od}{head}{nm}B']}"

        r = f"{m('rOverC', 'A')}, {m('rOverC', 'B')} ({m('rOverC', 'A', 'Writes')}, {m('rOverC', 'B', 'Writes')})"
        cells = [label, r, f"{m('oracleRatio', 'A')}, {m('oracleRatio', 'B')}",
                 '' if pre else f"{N[f'toldRatio{nm}A']}, {N[f'toldRatio{nm}B']}",
                 f"{m('perfectRatio', 'A')}, {m('perfectRatio', 'B')}",
                 f"{m('menuLoRatio', 'A')}, {m('menuLoRatio', 'B')}", f"{m('softRatio', 'A')}, {m('softRatio', 'B')}",
                 f"{hold('Firm')}; {hold('Read')}; {hold('Soft')}; {hold('SoftRead')}"]
        out.append(' & '.join(cells) + ' \\\\')
    note = ('A producer picks its order and is replayed in free order; a validator re-executes in block order and, outside the column Told, is not told what was written. '
            'Told: it is told what was written, and each run reads the version its place in the block requires; nothing runs twice. $r_o/\\cp_o$: the cost of an unused soft declaration against an unused lock, '
            'with every declared account counted as read and, in parentheses, with only writes counted. Times are totals over the replayed blocks relative to every declaration firm; '
            'classes use the menu at $\\theta = 0.25$. Hold: how much longer the other transactions take with one hold of the five hot accounts in each block, under the menu, by the class it declares. '
            f"At a validator told what was written any hold adds only what its thread takes: {N['holdToldFourA']}, {N['holdToldFourB']} at 4 threads and {N['holdToldSixteenA']}, {N['holdToldSixteenB']} at 16.")
    out += ['\\bottomrule', '\\end{tabular}', '\\par\\smallskip\\parbox{\\textwidth}{\\scriptsize ' + note + '}', '\\end{table*}']
    (HERE / 'tab_settings.tex').write_text('\n'.join(out) + '\n', encoding='utf-8')


def windows():
    T = json.loads((HERE / 'numbers_minutes.json').read_text(encoding='utf-8'))

    def fmt(v, d):
        s = f'{v:.{d}f}'
        return f'${s}$' if s.startswith('-') else s

    def cell(group, key, d):
        low, mid, high = T[group][key]
        return f"{fmt(mid, d)} ({fmt(low, d)}--{fmt(high, d)})"

    def row(label, key, d=0):
        return f"{label} & {cell('peak', key, d)} & {cell('median', key, d)} \\\\"

    rows = [row('Non-vote transactions per second', 'Tps'),
            row('Transactions that fail (\\%)', 'ShareFailed'), row('Declarations unwritten (\\%)', 'NotWritten'),
            row('Hot lock time, writers (\\%)', 'HotWritten'), row('Hot lock time, failed (\\%)', 'HotFailed'),
            row('\\quad sender writes it elsewhere (\\%)', 'HotWonHere'),
            row('Menu, producer, 16 threads (\\%)', 'FreeCutSixteen'), row('Menu, producer, 4 threads (\\%)', 'FreeCutFour'),
            row('Menu, validator, 16 threads (\\%)', 'BlockCutSixteen'), row('Menu, validator, 4 threads (\\%)', 'BlockCutFour'),
            row('Foresight, validator, 16 threads (\\%)', 'BlockOracleSixteen'),
            row('Told, validator, 16 threads (\\%)', 'ToldSixteen'), row('Told, validator, 4 threads (\\%)', 'ToldFour'),
            row('$r_o/\\cp_o$, producer, 16 threads', 'FreeROverCSixteen', 2), row('$r_o/\\cp_o$, validator, writes only', 'BlockROverCWrites', 2),
            row('$r_o/\\cp_o$, producer, 4 threads', 'FreeROverCFour', 2),
            row('Slowest block, all firm (\\%)', 'FirmMax'), row('Slowest block, menu (\\%)', 'MenuMax'), row('Slowest block, told (\\%)', 'ToldMax'),
            row('Hold, write lock, producer (\\%)', 'HoldFreeFirmSixteen'), row('Hold, soft, producer (\\%)', 'HoldFreeSoftSixteen', 1),
            row('Hold, soft, producer, 4 threads (\\%)', 'HoldFreeSoftFour'),
            row('Hold, told validator (\\%)', 'HoldToldSixteen', 1),
            row('Bill at writers\' price, of block fees (\\%)', 'BillWriters'),
            row('Bill at bids around it, of block fees (\\%)', 'BillLocalShare', 1),
            row('Top 100, producer (\\%)', 'HarmHundredFree'),
            row('Fees for none unpaid, one class (\\%)', 'FrOne'), row('Fees for none unpaid, two classes (\\%)', 'FrTwo'),
            row('Tips over what is paid (\\%)', 'TipShare', 1), row('Hot pairs at a tenth of the budget (\\%)', 'ClassUseAtTenth', 1)]
    out = ['\\begin{table}[t]', '\\centering',
           f"\\caption{{Whole minutes of consecutive blocks: median (range) over the {N['nPeak']} busiest and the {N['nMedian']} at the median. Savings are against all firm. The slowest block is a share of the budget at a validator at 16 threads. Hold at 16 threads unless stated; its bill at the bids around it is the median over blocks. Tips: minutes recorded with them; at the median the top of the range is one transfer of 3.4 SOL. Top 100: their share of what classes from writes save. Fees: lost to leave nothing unpaid. Hot pairs: counted use under the menu.}}", '\\label{tab:windows}',
           '\\scriptsize', '\\setlength{\\tabcolsep}{2pt}', '\\begin{tabular}{@{}lll@{}}', '\\toprule', ' & Busiest & Median \\\\', '\\midrule'] + rows + \
          ['\\bottomrule', '\\end{tabular}', '\\end{table}']
    (HERE / 'tab_windows.tex').write_text('\n'.join(out) + '\n', encoding='utf-8')


def frontier_table():
    cases = [('$m = 3$, the lead', 'MThree'), ('$m = 1$', 'MOne'), ('$m = 10$', 'MTen'), ('$m = 30$', 'MThirty'), ('$m = 100$', 'MHundred'), ('One price', 'Uniform'), ('No smoothing', 'Raw'), ("$k_o = 3\\cp_o$", 'KThree')]

    def pair(case, col):
        return f"{N[f'frTab{case}{col}A']}, {N[f'frTab{case}{col}B']}"

    out = ['\\begin{table}[t]', '\\centering', '\\caption{Fig.~\\ref{fig:frontier} under other choices, in pairs for Samples A and B, with $r_o$ at a producer at 16 threads (\\%).}', '\\label{tab:frontier}',
           '\\footnotesize', '\\setlength{\\tabcolsep}{3pt}', '\\begin{tabular}{@{}lll@{}}', '\\toprule',
           'Choice & \\begin{tabular}{@{}l@{}}Fees lost for none\\\\unpaid: one; two\\end{tabular} & \\begin{tabular}{@{}l@{}}Two at $u_o = 0$: lost; unpaid;\\\\one at equal loss: unpaid\\end{tabular} \\\\', '\\midrule']
    for label, case in cases:
        out.append(f"{label} & {pair(case, 'OneEnd')}; {pair(case, 'TwoEnd')} & {pair(case, 'LeftLost')}; {pair(case, 'LeftUnpaid')}; {pair(case, 'OneAtLeft')} \\\\")
    out += ['\\bottomrule', '\\end{tabular}', '\\end{table}']
    (HERE / 'tab_frontier.tex').write_text('\n'.join(out) + '\n', encoding='utf-8')


def replay():
    out = ['\\begin{table}[t]', '\\centering',
           '\\caption{Appendix table. Replay on the second half of each sample: total time relative to every declaration firm, with the percentage of execution wasted on aborted runs in parentheses. Every declared account counts as read, and foresight and a validator told what was written abort nothing. The first row of each group gives the all-firm time over the bound set by total compute over threads.}',
           '\\label{tab:replay}', '\\footnotesize', '\\setlength{\\tabcolsep}{3pt}',
           '\\begin{tabular}{@{}lllll@{}}', '\\toprule', 'Threads & 4 & 8 & 16 & 32 \\\\']

    def m(pre, name, k, tag):
        return N[(pre + name[0].upper() + name[1:] if pre else name) + k + tag]

    for pre, order in (('', 'block order'), ('free', 'free order')):
        for tag, name in (('A', 'Sample A'), ('B', 'Sample B')):
            out.append('\\midrule')
            out.append(f'\\multicolumn{{5}}{{@{{}}l}}{{\\emph{{{name}, {order}}}}} \\\\')
            out.append('All firm / bound & ' + ' & '.join(m(pre, 'firmBound', k, tag) for k, _ in THREADS) + ' \\\\')
            out.append('Foresight & ' + ' & '.join(m(pre, 'oracleRatio', k, tag) for k, _ in THREADS) + ' \\\\')
            if not pre:
                out.append('Told, with versions & ' + ' & '.join(N[f'toldRatio{k}{tag}'] for k, _ in THREADS) + ' \\\\')
            for th, label in (('Lo', 'Menu, $\\theta = 0.25$'), ('Hi', 'Menu, $\\theta = 0.75$')):
                out.append(label + ' & ' + ' & '.join(f"{m(pre, f'menu{th}Ratio', k, tag)} ({m(pre, f'menu{th}Waste', k, tag)})" for k, _ in THREADS) + ' \\\\')
            out.append('All soft & ' + ' & '.join(f"{m(pre, 'softRatio', k, tag)} ({m(pre, 'softWaste', k, tag)})" for k, _ in THREADS) + ' \\\\')
    out += ['\\bottomrule', '\\end{tabular}', '\\end{table}']
    (HERE / 'tab_replay.tex').write_text('\n'.join(out) + '\n', encoding='utf-8')


if __name__ == '__main__':
    measure()
    settings()
    windows()
    frontier_table()
    replay()
