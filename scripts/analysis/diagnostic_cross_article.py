import os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as ticker
import numpy as np
from datetime import datetime

# ── Paths ────────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '../../'))
DATA_DIR = os.path.join(PROJECT_ROOT, 'data', 'processed')
CHART_DIR = os.path.join(PROJECT_ROOT, 'reports', 'charts', 'cross_article')

CSV_ART10 = os.path.join(DATA_DIR, 'dosare_art10.csv')
CSV_ART11 = os.path.join(DATA_DIR, 'dosare_art11.csv')
CSV_STAFFING = os.path.join(DATA_DIR, 'anc_staffing.csv')
CSV_EVENTS = os.path.join(DATA_DIR, 'important_events.csv')

# ── Chart Style ──────────────────────────────────────────────────────────────
plt.rcParams.update({
    'figure.figsize': (14, 6),
    'figure.dpi': 150,
    'axes.titlesize': 14,
    'axes.labelsize': 11,
    'xtick.labelsize': 9,
    'ytick.labelsize': 9,
    'legend.fontsize': 9,
    'font.family': 'sans-serif',
    'axes.grid': True,
    'grid.alpha': 0.3,
    'axes.spines.top': False,
    'axes.spines.right': False,
})

COLOR_ART10 = '#2563EB'
COLOR_ART11 = '#10B981'
COLOR_ACCENT = '#F59E0B'
COLOR_DANGER = '#EF4444'
COLOR_STAFFING = '#6366F1'

# ── Leadership Periods ──────────────────────────────────────────────────────
LEADERSHIP = [
    ('Pre-Lenghel', None, pd.Timestamp('2020-05-15')),
    ('Lenghel', pd.Timestamp('2020-05-15'), pd.Timestamp('2024-05-22')),
    ('Barbu', pd.Timestamp('2024-05-22'), pd.Timestamp('2025-11-01')),
    ('Țapardel', pd.Timestamp('2025-11-01'), None),
]

# ── Data Loading ─────────────────────────────────────────────────────────────

def load_dossiers(csv_path):
    df = pd.read_csv(csv_path)
    df['DATA ÎNREGISTRĂRII'] = pd.to_datetime(df['DATA ÎNREGISTRĂRII'], format='%d.%m.%Y', errors='coerce')
    df['TERMEN'] = pd.to_datetime(df['TERMEN'], format='%d.%m.%Y', errors='coerce')
    df['SOLUȚIE'] = pd.to_datetime(df['SOLUȚIE'], format='%d.%m.%Y', errors='coerce')
    df['reg_year'] = df['DATA ÎNREGISTRĂRII'].dt.year
    df['reg_month'] = df['DATA ÎNREGISTRĂRII'].dt.to_period('M')
    df['is_resolved'] = df['SOLUȚIE'].notna()
    df['wait_days'] = (df['SOLUȚIE'] - df['DATA ÎNREGISTRĂRII']).dt.days
    return df


def load_all():
    art10 = load_dossiers(CSV_ART10)
    art11 = load_dossiers(CSV_ART11)
    staffing = pd.read_csv(CSV_STAFFING)
    events = pd.read_csv(CSV_EVENTS)
    events['Exact Date'] = pd.to_datetime(events['Exact Date'], format='%B %d, %Y', errors='coerce')
    return art10, art11, staffing, events


# ── Q4: Law 14/2025 Impact ──────────────────────────────────────────────────

def chart_law14_impact(art10, art11):
    law_date = pd.Timestamp('2025-03-15')

    fig, axes = plt.subplots(1, 2, figsize=(16, 6))

    for ax, df, label, color in [
        (axes[0], art10, 'Article 10', COLOR_ART10),
        (axes[1], art11, 'Article 11', COLOR_ART11),
    ]:
        # Focus on 2024-2026
        recent = df[df['DATA ÎNREGISTRĂRII'] >= '2024-01-01']
        monthly = recent.groupby('reg_month').size()
        monthly.index = monthly.index.to_timestamp()

        ax.bar(monthly.index, monthly.values, width=20, color=color, zorder=3, alpha=0.8)
        ax.axvline(law_date, color=COLOR_DANGER, linestyle='-', linewidth=2, alpha=0.8)
        ax.annotate('Law 14/2025\n(B1 language req.)\n15 Mar 2025',
                    xy=(law_date, monthly.max() * 0.9),
                    fontsize=7, color=COLOR_DANGER, ha='left', va='top')

        # Pre/post averages
        pre = monthly[monthly.index < law_date].mean()
        post = monthly[monthly.index >= law_date]
        if len(post) > 0:
            post_avg = post.mean()
            ax.axhline(pre, color=color, linestyle='--', linewidth=1, alpha=0.5, label=f'Pre avg: {pre:,.0f}/mo')
            ax.axhline(post_avg, color=COLOR_ACCENT, linestyle='--', linewidth=1, alpha=0.5, label=f'Post avg: {post_avg:,.0f}/mo')
            ax.legend(fontsize=8)

        ax.set_title(f'{label} — Monthly Volume (2024–2026)')
        ax.set_ylabel('Dossiers Registered')
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))

    fig.suptitle('Law 14/2025 Impact — Before vs. After B1 Language Requirement', fontsize=15, fontweight='bold', y=1.02)
    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, 'law14_impact.png'), bbox_inches='tight')
    plt.close(fig)
    print('  ✓ law14_impact.png')


# ── Q7: Staffing vs. Per-Capita Productivity ────────────────────────────────

def chart_productivity_per_staff(art10, art11, staffing):
    # Combined resolutions per year
    res10 = art10[art10['is_resolved']].groupby(art10.loc[art10['is_resolved'], 'SOLUȚIE'].dt.year).size()
    res11 = art11[art11['is_resolved']].groupby(art11.loc[art11['is_resolved'], 'SOLUȚIE'].dt.year).size()
    total_res = (res10.add(res11, fill_value=0)).rename('Total Resolved')

    staff = staffing.set_index('Year')['Estimated_Actual_Staff']
    common_years = total_res.index.intersection(staff.index)
    productivity = total_res[common_years] / staff[common_years]

    fig, ax1 = plt.subplots()
    ax1.bar(common_years, productivity[common_years], color=COLOR_ART11, zorder=3, alpha=0.8, label='Dossiers/Staff/Year')
    ax1.set_ylabel('Dossiers Resolved per Staff Member')
    ax1.set_xlabel('Year')
    ax1.set_title('ANC Per-Capita Productivity (Combined Art. 10 + Art. 11)')
    ax1.xaxis.set_major_locator(ticker.MaxNLocator(integer=True))
    ax1.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: f'{v:,.0f}'))

    # Overlay staffing
    ax2 = ax1.twinx()
    ax2.plot(common_years, staff[common_years], color=COLOR_STAFFING,
             marker='s', linewidth=1.5, markersize=5, label='Estimated Staff', zorder=4)
    ax2.set_ylabel('Estimated Staff', color=COLOR_STAFFING)
    ax2.tick_params(axis='y', labelcolor=COLOR_STAFFING)
    ax2.spines['right'].set_visible(True)

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper right')

    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, 'productivity_per_staff.png'))
    plt.close(fig)
    print('  ✓ productivity_per_staff.png')

    print('\n  Per-capita productivity:')
    for year in common_years:
        print(f'    {year}: {productivity[year]:,.0f} dossiers/staff  (staff={staff[year]:.0f}, resolved={total_res[year]:,.0f})')


# ── Q8: Leadership Performance Comparison ───────────────────────────────────

def chart_leadership_comparison(art10, art11):
    combined = pd.concat([art10, art11], ignore_index=True)

    results = []
    for name, start, end in LEADERSHIP:
        # Intake: dossiers REGISTERED during this period
        mask_reg = pd.Series(True, index=combined.index)
        if start is not None:
            mask_reg &= combined['DATA ÎNREGISTRĂRII'] >= start
        if end is not None:
            mask_reg &= combined['DATA ÎNREGISTRĂRII'] < end
        period_intake = combined[mask_reg]

        # Output: dossiers RESOLVED during this period (by SOLUȚIE date)
        resolved_all = combined[combined['is_resolved']].copy()
        mask_sol = pd.Series(True, index=resolved_all.index)
        if start is not None:
            mask_sol &= resolved_all['SOLUȚIE'] >= start
        if end is not None:
            mask_sol &= resolved_all['SOLUȚIE'] < end
        period_resolved = resolved_all[mask_sol]

        # Duration of period in months
        if start is not None and end is not None:
            months = max((end - start).days / 30.44, 1)
        elif start is not None:
            months = max((pd.Timestamp('2026-01-19') - start).days / 30.44, 1)
        else:
            months = max((end - combined['DATA ÎNREGISTRĂRII'].min()).days / 30.44, 1)

        monthly_intake = len(period_intake) / months
        monthly_output = len(period_resolved) / months
        # Median wait of dossiers resolved during this period
        median_wait = period_resolved['wait_days'].median() if len(period_resolved) > 0 else 0

        results.append({
            'Period': name,
            'Monthly Avg Intake': monthly_intake,
            'Monthly Avg Output': monthly_output,
            'Median Wait (days)': median_wait,
        })

    results_df = pd.DataFrame(results)

    fig, axes = plt.subplots(1, 3, figsize=(16, 5))

    # Monthly intake
    ax = axes[0]
    bars = ax.bar(results_df['Period'], results_df['Monthly Avg Intake'], color=COLOR_ART10, zorder=3)
    ax.set_title('Avg Monthly Intake')
    ax.set_ylabel('Dossiers Registered/Month')
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: f'{v:,.0f}'))
    for bar in bars:
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                f'{bar.get_height():,.0f}', ha='center', va='bottom', fontsize=8)

    # Monthly output (throughput)
    ax = axes[1]
    bars = ax.bar(results_df['Period'], results_df['Monthly Avg Output'], color=COLOR_ART11, zorder=3)
    ax.set_title('Avg Monthly Throughput')
    ax.set_ylabel('Dossiers Resolved/Month')
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: f'{v:,.0f}'))
    for bar in bars:
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                f'{bar.get_height():,.0f}', ha='center', va='bottom', fontsize=8)

    # Median wait
    ax = axes[2]
    bars = ax.bar(results_df['Period'], results_df['Median Wait (days)'], color=COLOR_ACCENT, zorder=3)
    ax.set_title('Median Processing Time')
    ax.set_ylabel('Days')
    for bar in bars:
        days = bar.get_height()
        if days > 0:
            ax.text(bar.get_x() + bar.get_width() / 2, days,
                    f'{days:,.0f}d\n({days/365:.1f}yr)', ha='center', va='bottom', fontsize=7)

    fig.suptitle('ANC Leadership Performance Comparison (Combined Art. 10 + Art. 11)',
                 fontsize=15, fontweight='bold', y=1.02)
    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, 'leadership_comparison.png'), bbox_inches='tight')
    plt.close(fig)
    print('  ✓ leadership_comparison.png')

    print('\n  Leadership Comparison:')
    for _, row in results_df.iterrows():
        print(f'    {row["Period"]:15s}: intake={row["Monthly Avg Intake"]:>7,.0f}/mo  '
              f'output={row["Monthly Avg Output"]:>7,.0f}/mo  '
              f'median_wait={row["Median Wait (days)"]:>6,.0f}d')


# ── Q10: Legal Deadline Compliance ──────────────────────────────────────────

def chart_deadline_compliance(art10, art11):
    LEGAL_DEADLINE = 150  # 5 months ≈ 150 days

    fig, axes = plt.subplots(1, 2, figsize=(16, 6))

    for ax, df, label, color in [
        (axes[0], art10, 'Article 10', COLOR_ART10),
        (axes[1], art11, 'Article 11', COLOR_ART11),
    ]:
        resolved = df[df['is_resolved'] & df['wait_days'].notna() & (df['wait_days'] > 0)].copy()
        by_year = resolved.groupby('reg_year').apply(
            lambda g: (g['wait_days'] > LEGAL_DEADLINE).sum() / len(g) * 100,
            include_groups=False
        )

        ax.bar(by_year.index, by_year.values, color=color, zorder=3, alpha=0.8)
        ax.axhline(100, color=COLOR_DANGER, linestyle='--', linewidth=0.8, alpha=0.3)
        ax.set_title(f'{label} — % Exceeding 5-Month Legal Deadline')
        ax.set_ylabel('% Over 150 Days')
        ax.set_xlabel('Registration Year')
        ax.set_ylim(0, 105)
        ax.xaxis.set_major_locator(ticker.MaxNLocator(integer=True))

        for year, val in by_year.items():
            ax.text(year, val + 1, f'{val:.0f}%', ha='center', va='bottom', fontsize=7)

    fig.suptitle('Legal Deadline Compliance — % of Resolved Dossiers Exceeding 150 Days',
                 fontsize=15, fontweight='bold', y=1.02)
    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, 'deadline_compliance.png'), bbox_inches='tight')
    plt.close(fig)
    print('  ✓ deadline_compliance.png')


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    os.makedirs(CHART_DIR, exist_ok=True)
    print(f'Output directory: {CHART_DIR}\n')

    art10, art11, staffing, events = load_all()
    print(f'Loaded {len(art10):,} Art. 10 dossiers')
    print(f'Loaded {len(art11):,} Art. 11 dossiers')
    print(f'Loaded {len(staffing)} staffing records')
    print(f'Loaded {len(events)} events\n')

    print('Generating cross-article diagnostic charts...')
    chart_law14_impact(art10, art11)
    chart_productivity_per_staff(art10, art11, staffing)
    chart_leadership_comparison(art10, art11)
    chart_deadline_compliance(art10, art11)

    print('\nAll cross-article diagnostic charts generated successfully.')


if __name__ == '__main__':
    main()
