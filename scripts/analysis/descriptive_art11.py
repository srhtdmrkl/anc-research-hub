import os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as ticker
from datetime import datetime

# ── Paths ────────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '../../'))
DATA_DIR = os.path.join(PROJECT_ROOT, 'data', 'processed')
CHART_DIR = os.path.join(PROJECT_ROOT, 'reports', 'charts', 'article_11')

CSV_DOSSIERS = os.path.join(DATA_DIR, 'dosare_art11.csv')

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

COLOR_PRIMARY = '#2563EB'
COLOR_SECONDARY = '#10B981'
COLOR_ACCENT = '#F59E0B'
COLOR_DANGER = '#EF4444'
COLOR_PENDING = '#8B5CF6'
COLOR_STAFFING = '#6366F1'

# ── Data Loading ─────────────────────────────────────────────────────────────

def load_data():
    """Load and parse all datasets."""
    df = pd.read_csv(CSV_DOSSIERS)
    df['DATA ÎNREGISTRĂRII'] = pd.to_datetime(df['DATA ÎNREGISTRĂRII'], format='%d.%m.%Y', errors='coerce')
    df['TERMEN'] = pd.to_datetime(df['TERMEN'], format='%d.%m.%Y', errors='coerce')
    df['SOLUȚIE'] = pd.to_datetime(df['SOLUȚIE'], format='%d.%m.%Y', errors='coerce')

    # Derived fields
    df['reg_year'] = df['DATA ÎNREGISTRĂRII'].dt.year
    df['reg_month'] = df['DATA ÎNREGISTRĂRII'].dt.to_period('M')
    df['is_resolved'] = df['SOLUȚIE'].notna()
    df['is_pending'] = df['SOLUȚIE'].isna() & df['TERMEN'].notna()
    df['wait_days'] = (df['SOLUȚIE'] - df['DATA ÎNREGISTRĂRII']).dt.days

    return df


# ── Chart 1: Monthly Registrations ──────────────────────────────────────────

def chart_monthly_registrations(df):
    monthly = df.groupby('reg_month').size()
    monthly.index = monthly.index.to_timestamp()

    fig, ax = plt.subplots()
    ax.plot(monthly.index, monthly.values, color=COLOR_PRIMARY, linewidth=1.2)
    ax.fill_between(monthly.index, monthly.values, alpha=0.08, color=COLOR_PRIMARY)
    ax.set_title('Article 11 — Monthly Registration Volume')
    ax.set_ylabel('Dossiers Registered')
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f'{x:,.0f}'))

    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, 'monthly_registrations.png'))
    plt.close(fig)
    print('  ✓ monthly_registrations.png')


# ── Chart 2: Yearly Registrations ───────────────────────────────────────────

def chart_yearly_registrations(df):
    yearly = df.groupby('reg_year').size()

    fig, ax = plt.subplots()
    bars = ax.bar(yearly.index, yearly.values, color=COLOR_PRIMARY, width=0.7, zorder=3)
    ax.set_title('Article 11 — Yearly Registration Volume')
    ax.set_ylabel('Dossiers Registered')
    ax.set_xlabel('Registration Year')
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f'{x:,.0f}'))
    ax.xaxis.set_major_locator(ticker.MaxNLocator(integer=True))

    # Value labels
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2, height, f'{int(height):,}',
                ha='center', va='bottom', fontsize=7)

    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, 'yearly_registrations.png'))
    plt.close(fig)
    print('  ✓ yearly_registrations.png')


# ── Chart 3: Status Breakdown ───────────────────────────────────────────────

def chart_status_breakdown(df):
    resolved = df['is_resolved'].sum()
    pending = df['is_pending'].sum()
    no_data = len(df) - resolved - pending

    labels = ['Resolved', 'Scheduled (Pending)', 'No Status']
    sizes = [resolved, pending, no_data]
    colors = [COLOR_SECONDARY, COLOR_PENDING, '#D1D5DB']
    explode = (0.03, 0.03, 0.03)

    fig, ax = plt.subplots(figsize=(8, 6))
    wedges, texts, autotexts = ax.pie(
        sizes, labels=labels, colors=colors, explode=explode,
        autopct=lambda pct: f'{pct:.1f}%\n({int(round(pct / 100 * sum(sizes))):,})',
        startangle=140, textprops={'fontsize': 10}
    )
    ax.set_title('Article 11 — Dossier Status Breakdown')
    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, 'status_breakdown.png'))
    plt.close(fig)
    print('  ✓ status_breakdown.png')


# ── Chart 4: Resolution Rate by Year ────────────────────────────────────────

def chart_resolution_rate_by_year(df):
    by_year = df.groupby('reg_year').agg(
        total=('is_resolved', 'size'),
        resolved=('is_resolved', 'sum')
    )
    by_year['rate'] = (by_year['resolved'] / by_year['total']) * 100

    fig, ax = plt.subplots()
    ax.bar(by_year.index, by_year['rate'], color=COLOR_SECONDARY, width=0.7, zorder=3)
    ax.set_title('Article 11 — Resolution Rate by Registration Year')
    ax.set_ylabel('Resolved (%)')
    ax.set_xlabel('Registration Year')
    ax.set_ylim(0, 105)
    ax.xaxis.set_major_locator(ticker.MaxNLocator(integer=True))

    for i, (year, row) in enumerate(by_year.iterrows()):
        ax.text(year, row['rate'] + 1.5, f"{row['rate']:.0f}%", ha='center', va='bottom', fontsize=7)

    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, 'resolution_rate_by_year.png'))
    plt.close(fig)
    print('  ✓ resolution_rate_by_year.png')


# ── Chart 5: Wait Time Distribution ─────────────────────────────────────────

def chart_wait_time_distribution(df):
    resolved = df.loc[df['is_resolved'] & df['wait_days'].notna(), 'wait_days']
    resolved = resolved[resolved > 0]

    fig, ax = plt.subplots()
    ax.hist(resolved, bins=100, color=COLOR_PRIMARY, edgecolor='white', linewidth=0.3, zorder=3)
    ax.axvline(resolved.median(), color=COLOR_DANGER, linestyle='--', linewidth=1.2,
               label=f'Median: {resolved.median():,.0f} days ({resolved.median() / 365:.1f} yrs)')
    ax.axvline(resolved.mean(), color=COLOR_ACCENT, linestyle='--', linewidth=1.2,
               label=f'Mean: {resolved.mean():,.0f} days ({resolved.mean() / 365:.1f} yrs)')
    ax.set_title('Article 11 — Processing Duration Distribution (Resolved Dossiers)')
    ax.set_xlabel('Wait Time (days)')
    ax.set_ylabel('Frequency')
    ax.xaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f'{x:,.0f}'))
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f'{x:,.0f}'))
    ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, 'wait_time_distribution.png'))
    plt.close(fig)
    print('  ✓ wait_time_distribution.png')


# ── Chart 6: Median Wait by Year ────────────────────────────────────────────

def chart_median_wait_by_year(df):
    resolved = df[df['is_resolved'] & df['wait_days'].notna() & (df['wait_days'] > 0)]
    by_year = resolved.groupby('reg_year')['wait_days'].median()

    fig, ax = plt.subplots()
    ax.plot(by_year.index, by_year.values, marker='o', color=COLOR_PRIMARY, linewidth=1.5, markersize=5, zorder=3)
    ax.fill_between(by_year.index, by_year.values, alpha=0.08, color=COLOR_PRIMARY)
    ax.set_title('Article 11 — Median Processing Time by Registration Year')
    ax.set_ylabel('Median Wait (days)')
    ax.set_xlabel('Registration Year')
    ax.xaxis.set_major_locator(ticker.MaxNLocator(integer=True))

    for year, val in by_year.items():
        ax.annotate(f'{val / 365:.1f} yr', (year, val), textcoords='offset points',
                    xytext=(0, 10), ha='center', fontsize=7, color=COLOR_PRIMARY)

    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, 'median_wait_by_year.png'))
    plt.close(fig)
    print('  ✓ median_wait_by_year.png')




# ── Summary Statistics ───────────────────────────────────────────────────────

def print_summary(df):
    total = len(df)
    resolved = df['is_resolved'].sum()
    pending = df['is_pending'].sum()
    wait = df.loc[df['is_resolved'] & df['wait_days'].notna() & (df['wait_days'] > 0), 'wait_days']

    print('\n' + '=' * 60)
    print('  ARTICLE 11 — DESCRIPTIVE SUMMARY')
    print('=' * 60)
    print(f'  Total dossiers:        {total:>10,}')
    print(f'  Registration range:    {df["DATA ÎNREGISTRĂRII"].min().strftime("%d.%m.%Y")} – '
          f'{df["DATA ÎNREGISTRĂRII"].max().strftime("%d.%m.%Y")}')
    print(f'  Resolved:              {resolved:>10,}  ({resolved / total * 100:.1f}%)')
    print(f'  Pending (scheduled):   {pending:>10,}  ({pending / total * 100:.1f}%)')
    print(f'  No status:             {total - resolved - pending:>10,}  ({(total - resolved - pending) / total * 100:.1f}%)')
    print()
    print(f'  Wait time (resolved):')
    print(f'    Median:              {wait.median():>10,.0f} days  ({wait.median() / 365:.1f} years)')
    print(f'    Mean:                {wait.mean():>10,.0f} days  ({wait.mean() / 365:.1f} years)')
    print(f'    Min:                 {wait.min():>10,.0f} days')
    print(f'    Max:                 {wait.max():>10,.0f} days  ({wait.max() / 365:.1f} years)')
    print(f'    Std Dev:             {wait.std():>10,.0f} days')
    print('=' * 60 + '\n')


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    os.makedirs(CHART_DIR, exist_ok=True)
    print(f'Output directory: {CHART_DIR}\n')

    df = load_data()
    print(f'Loaded {len(df):,} dossiers from {os.path.basename(CSV_DOSSIERS)}')

    print('\nGenerating charts...')
    chart_monthly_registrations(df)
    chart_yearly_registrations(df)
    chart_status_breakdown(df)
    chart_resolution_rate_by_year(df)
    chart_wait_time_distribution(df)
    chart_median_wait_by_year(df)

    print_summary(df)
    print('All Article 11 descriptive charts generated successfully.')


if __name__ == '__main__':
    main()
