"""Data figures for the paper.

fig_costs.pdf    Expected extra fee of each class against the probability of use, with the threshold of a
                 one-class fee marked (Sections 4 and 5).  Illustrative parameters, stated in the caption.
fig_declared.pdf (a) Share of declared writable objects not written, by how often the object was declared in
                 the sample: Solana token accounts, Solana all accounts, Sui mutable shared objects.
                 (b) Who holds the hottest accounts of each block, as a share of the lock time and of the
                 compute declared on them, in both samples.
fig_frontier.pdf What each rule gives up in fees against what it leaves unpaid, and against time at a producer.
fig_replay.pdf   Replay in block order: total time relative to every declaration firm in each sample, and
                 wasted execution, by number of threads.
Inputs are the aggregate JSON files under results/.
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
RES = HERE.parent / 'results'
import figstyle  # noqa: E402

figstyle.apply()
import matplotlib.pyplot as plt  # noqa: E402

INK, MID, LIGHT = '0.10', '0.42', '0.68'
OUT = HERE / 'figures'


def read(name):
    return json.loads((RES / name).read_text(encoding='utf-8'))


def costs():
    cp, k = 1.0, 3.0            # (1 - rho) c and the premium: threshold q_L = 1/4
    fn, xk = 1.0, 5.0           # one-class fee and x + kappa: threshold q* = 1/6
    q = np.linspace(0, 1, 401)
    firm, soft = (1 - q) * cp, q * k
    qL = cp / (cp + k)
    qstar = fn / (fn + xk)
    fig, ax = plt.subplots(figsize=(3.3, 1.5))
    ax.axvspan(0, qstar, color='0.90', lw=0)
    ax.plot(q, firm, color=MID, lw=0.9, ls='--')
    ax.plot(q, soft, color=MID, lw=0.9, ls=':')
    ax.plot(q, np.minimum(firm, soft), color=INK, lw=1.6)
    ax.axvline(qL, color=LIGHT, lw=0.7)
    ax.text(0.53, 0.60, "firm: $(1-q)c'$", color=INK, fontsize=7, ha='left')
    ax.text(0.70, 1.72, 'soft: $qk$', color=INK, fontsize=7, ha='left')
    ax.text(qL + 0.015, 1.72, '$q_L$', color=INK, fontsize=7, ha='left')
    ax.text(qstar / 2, 1.42, 'dropped\nunder\none fee', color=MID, fontsize=6.5, ha='center', va='center')
    ax.annotate('the menu', xy=(0.47, 0.53), xytext=(0.30, 0.13), color=INK, fontsize=7,
                arrowprops=dict(arrowstyle='-', color=LIGHT, lw=0.6), ha='left', va='center')
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 2)
    ax.set_xlabel('Probability of use $q$')
    ax.set_ylabel('Expected extra fee')
    figstyle.save(fig, OUT / 'fig_costs.pdf')


def declared():
    a = read('paper_numbers_day1.json')
    b = read('paper_numbers_day2.json')
    sui = read('sui_v2_summary.json')['successful_mutable_declarations']
    tiers = ['1', '2-9', '10-99', '100+']
    labels = ['1', '2\u20139', '10\u201399', '100+']
    x = np.arange(4)
    fig, axes = plt.subplots(1, 2, figsize=(6.9, 1.85), gridspec_kw={'width_ratios': [1, 1], 'wspace': 0.42})
    ax = axes[0]
    tok = [100 * a['token_unchanged_by_heat']['by_heat'][t]['unchanged_share'] for t in tiers]
    all_ = [100 * a['declarations']['by_heat'][t]['share_v3'] for t in tiers]
    sui_mid = [100 * sui['heat_' + t]['middle_no_direct_child_share'] for t in tiers]
    sui_lo = [100 * sui['heat_' + t]['strict_lower_share'] for t in tiers]
    sui_hi = [100 * sui['heat_' + t]['upper_unchanged_share'] for t in tiers]
    ax.plot(x, tok, color=INK, lw=1.4, marker='o', ms=3, label='Solana token accounts (succeeded)')
    ax.plot(x, all_, color=MID, lw=1.1, marker='s', ms=3, label='Solana, all accounts (with failures)')
    yerr = [np.array(sui_mid) - np.array(sui_lo), np.array(sui_hi) - np.array(sui_mid)]
    ax.errorbar(x + 0.04, sui_mid, yerr=yerr, color=LIGHT, lw=1.0, marker='^', ms=3, capsize=2,
                label='Sui mutable shared objects (range)')
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_xlabel('Times the object was declared in the sample')
    ax.set_ylabel('Not written or not changed (%)')
    ax.set_ylim(0, 100)
    ax.legend(frameon=False, fontsize=6.5, loc='upper left', handlelength=1.6, borderaxespad=0.1)
    figstyle.tag(ax, '(a)')
    ax = axes[1]
    oa, ob = read('occupancy_day1.json'), read('occupancy_day2.json')
    parts = [('Writers', ('written',), INK), ('Succeeded, not written', ('ok_token_unchanged', 'ok_route_leg'), MID),
             ('Failed, sender succeeds at times', ('failed_sender_won_here', 'failed_sender_won_elsewhere'), LIGHT),
             ('Failed, sender never succeeds', ('failed_never_won_repeat', 'failed_never_won_once'), '0.88')]
    rows = [('A, lock time', oa['shares_of_hot_lock_time']), ('A, declared', oa['shares_of_hot_declared_compute']),
            ('B, lock time', ob['shares_of_hot_lock_time']), ('B, declared', ob['shares_of_hot_declared_compute'])]
    for i, (label, sh) in enumerate(rows):
        left = 0.0
        y = len(rows) - 1 - i
        for pname, keys, color in parts:
            w = 100 * sum(sh[k] for k in keys)
            ax.barh(y, w, left=left, color=color, edgecolor='white', linewidth=0.5, height=0.72, label=pname if i == 0 else None)
            left += w
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([r[0] for r in rows][::-1])
    ax.set_xlim(0, 100)
    ax.set_xlabel('Share on the hot accounts of each block (%)')
    ax.legend(frameon=False, fontsize=6, loc='lower right', bbox_to_anchor=(1.0, 1.0), ncol=2, handlelength=1.2, columnspacing=0.8, borderaxespad=0.1)
    ax.annotate('(b)', xy=(-0.22, 1.01), xycoords='axes fraction', fontsize=9, va='bottom', color=INK)
    figstyle.save(fig, OUT / 'fig_declared.pdf')


def frontier():
    a, b = read('frontier_day1.json'), read('frontier_day2.json')
    fig, axes = plt.subplots(1, 2, figsize=(3.45, 1.55), gridspec_kw={'wspace': 0.48})
    ax = axes[0]
    lead = a['lead']['m=3']

    def curve(points):
        return [100 * p['lost'] for p in points], [100 * p['unpaid'] for p in points]

    ax.plot(*curve(lead['one']), color=INK, lw=1.4, label='One class')
    for name, color, ls in (('producer_16', INK, ':'), ('validator_16_writes', MID, '--'), ('producer_4', LIGHT, '-')):
        ax.plot(*curve(lead['two'][name]), color=color, lw=1.1, ls=ls, label=f"Two, $r_o/c'_o$ = {a['ratios'][name]:.2f}")
    ax.set_xlim(0, 12.5)
    ax.set_ylim(0, 60)
    ax.set_xlabel('Fees lost (%)')
    ax.set_ylabel('Cost left unpaid (%)')
    ax.legend(frameon=False, fontsize=5.5, loc='upper right', handlelength=1.7, borderaxespad=0.0, labelspacing=0.25)
    figstyle.tag(ax, '(a)')
    ax = axes[1]
    for r, ls, tag in ((a, '-', 'A'), (b, '--', 'B')):
        t = r['time']
        one = [p for p in t['one'] if p['lost'] > 0]
        ax.plot([100 * p['lost'] for p in one], [p['free'] for p in one], color=INK, lw=1.2, ls=ls, label=f'One class, {tag}')
        ax.plot([100 * p['lost'] for p in t['two']], [p['free'] for p in t['two']], color=MID, lw=1.2, ls=ls, marker='o', ms=2.5, label=f'Two classes, {tag}')
    ax.set_xlim(0, 12.5)
    ax.set_ylim(0.6, 1.0)
    ax.set_xlabel('Fees lost (%)')
    ax.set_ylabel('Time relative to all firm')
    ax.legend(frameon=False, fontsize=5.5, loc='upper right', handlelength=1.9, borderaxespad=0.0, labelspacing=0.25)
    figstyle.tag(ax, '(b)')
    figstyle.save(fig, OUT / 'fig_frontier.pdf')


def replay():
    a = read('paper_numbers_day1.json')['replay']['block']['reads']
    b = read('paper_numbers_day2.json')['replay']['block']['reads']
    told = {'(a) Sample A': read('reads_day1.json'), '(b) Sample B': read('reads_day2.json')}
    threads = [4, 8, 16, 32]
    series = [('oracle', 'Foresight', INK, '-', 'o'),
              ('menu_payer@0.25', 'Menu, threshold 0.25', MID, '-', 's'),
              ('menu_payer@0.75', 'Menu, threshold 0.75', MID, '--', '^'),
              ('soft', 'All soft', LIGHT, '-', 'D')]
    fig, axes = plt.subplots(1, 3, figsize=(6.9, 1.72), gridspec_kw={'wspace': 0.32})
    for ax, r, tag in ((axes[0], a, '(a) Sample A'), (axes[1], b, '(b) Sample B')):
        y = [told[tag][f'threads={n}']['block']['told']['over_firm'] for n in threads]
        ax.plot(threads, y, color=INK, ls=':', marker='v', ms=2.6, lw=1.1, label='Told, with versions')
        for key, name, color, ls, marker in series:
            y = [r[f'threads={n}'][key]['makespan_over_firm'] for n in threads]
            ax.plot(threads, y, color=color, ls=ls, marker=marker, ms=2.6, lw=1.1, label=name)
        ax.axhline(1, color=LIGHT, lw=0.6)
        ax.set_ylim(0.4, 1.08)
        figstyle.tag(ax, tag)
    axes[0].set_ylabel('Total time relative to all firm')
    handles, labels = axes[0].get_legend_handles_labels()
    ax = axes[2]
    for r, alpha in ((a, 1.0), (b, 0.5)):
        for key, name, color, ls, marker in series:
            if key != 'oracle':
                w = [100 * r[f'threads={n}'][key]['wasted_share'] for n in threads]
                ax.plot(threads, w, color=color, ls=ls, marker=marker, ms=2.6, lw=1.1, alpha=alpha)
    ax.set_ylabel('Wasted execution (%)')
    ax.set_ylim(0, 100)
    ax.legend(handles[2:], labels[2:], frameon=False, fontsize=6, loc='upper left', handlelength=1.9, borderaxespad=0.1)
    axes[0].legend(handles[:2], labels[:2], frameon=False, fontsize=6, loc='lower left', handlelength=1.9, borderaxespad=0.1)
    figstyle.tag(ax, '(c)')
    for ax in axes:
        ax.set_xscale('log', base=2)
        ax.set_xticks(threads)
        ax.set_xticklabels([str(n) for n in threads])
        ax.minorticks_off()
        ax.set_xlabel('Threads')
    figstyle.save(fig, OUT / 'fig_replay.pdf')


if __name__ == '__main__':
    OUT.mkdir(exist_ok=True)
    costs()
    if (RES / 'paper_numbers_day2.json').exists():
        declared()
        frontier()
        replay()
