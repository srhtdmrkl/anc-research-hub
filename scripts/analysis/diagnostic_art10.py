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
CHART_DIR = os.path.join(PROJECT_ROOT, 'reports', 'charts', 'article_10')

CSV_DOSSIERS = os.path.join(DATA_DIR, 'dosare_art10.csv')
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

COLOR_PRIMARY = '#2563EB'
COLOR_SECONDARY = '#10B981'
COLOR_ACCENT = '#F59E0B'
COLOR_DANGER = '#EF4444'
COLOR_PENDING = '#8B5CF6'

# ── Data Loading ─────────────────────────────────────────────────────────────

def load_data():
    """Load and parse dossier + events datasets."""
    df = pd.read_csv(CSV_DOSSIERS)
    df['DATA ÎNREGISTRĂRII'] = pd.to_datetime(df['DATA ÎNREGISTRĂRII'], format='%d.%m.%Y', errors='coerce')
    df['TERMEN'] = pd.to_datetime(df['TERMEN'], format='%d.%m.%Y', errors='coerce')
    df['SOLUȚIE'] = pd.to_datetime(df['SOLUȚIE'], format='%d.%m.%Y', errors='coerce')

    df['reg_year'] = df['DATA ÎNREGISTRĂRII'].dt.year
    df['reg_month'] = df['DATA ÎNREGISTRĂRII'].dt.to_period('M')
    df['is_resolved'] = df['SOLUȚIE'].notna()
    df['is_pending'] = df['SOLUȚIE'].isna() & df['TERMEN'].notna()
    df['wait_days'] = (df['SOLUȚIE'] - df['DATA ÎNREGISTRĂRII']).dt.days

    events = pd.read_csv(CSV_EVENTS)
    events['Exact Date'] = pd.to_datetime(events['Exact Date'], format='%B %d, %Y', errors='coerce')

    return df, events


# ── Q6/Q11: Throughput vs. Cumulative Backlog ───────────────────────────────

def chart_throughput_vs_backlog(df):
    intake = df.groupby('reg_year').size().rename('Intake')
    resolved_by_year = df[df['is_resolved']].copy()
    resolved_by_year['sol_year'] = resolved_by_year['SOLUȚIE'].dt.year
    output = resolved_by_year.groupby('sol_year').size().rename('Resolved')

    combined = pd.DataFrame({'Intake': intake, 'Resolved': output}).fillna(0)
    combined['Net'] = combined['Intake'] - combined['Resolved']
    combined['Cumulative Backlog'] = combined['Net'].cumsum()

    fig, ax1 = plt.subplots()
    width = 0.35
    x = combined.index

    ax1.bar(x - width / 2, combined['Intake'], width, label='Intake', color=COLOR_PRIMARY, zorder=3)
    ax1.bar(x + width / 2, combined['Resolved'], width, label='Resolved', color=COLOR_SECONDARY, zorder=3)
    ax1.set_ylabel('Dossier Count')
    ax1.set_xlabel('Year')
    ax1.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: f'{v:,.0f}'))
    ax1.xaxis.set_major_locator(ticker.MaxNLocator(integer=True))
    ax1.set_title('Article 10 — Annual Throughput vs. Cumulative Backlog')

    ax2 = ax1.twinx()
    ax2.plot(x, combined['Cumulative Backlog'], color=COLOR_DANGER,
             marker='o', linewidth=2, markersize=5, label='Cumulative Backlog', zorder=4)
    ax2.set_ylabel('Cumulative Backlog', color=COLOR_DANGER)
    ax2.tick_params(axis='y', labelcolor=COLOR_DANGER)
    ax2.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: f'{v:,.0f}'))
    ax2.spines['right'].set_visible(True)

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')

    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, 'throughput_vs_backlog_art10.png'))
    plt.close(fig)
    print('  ✓ throughput_vs_backlog_art10.png')

    # Print the table
    print('\n  Yearly Intake vs. Output:')
    for year, row in combined.iterrows():
        print(f'    {year}: Intake={int(row["Intake"]):>6,}  Resolved={int(row["Resolved"]):>6,}  '
              f'Net={int(row["Net"]):>+6,}  Backlog={int(row["Cumulative Backlog"]):>7,}')


# ── Q13: Seasonality ────────────────────────────────────────────────────────

def chart_seasonality(df):
    # Registration seasonality
    reg_by_month = df.groupby(df['DATA ÎNREGISTRĂRII'].dt.month).size()

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
              'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

    # Registrations by calendar month
    ax = axes[0]
    ax.bar(reg_by_month.index, reg_by_month.values, color=COLOR_PRIMARY, zorder=3)
    ax.set_title('Art. 10 — Registrations by Calendar Month')
    ax.set_ylabel('Total Dossiers')
    ax.set_xticks(range(1, 13))
    ax.set_xticklabels(months, fontsize=8)
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: f'{v:,.0f}'))

    # Resolutions by calendar month — EXCLUDE imputed July 1 dates
    resolved = df[df['is_resolved']].copy()
    # Filter out imputed dates (July 1 = mid-year imputation for year-only resolution dates)
    non_imputed = resolved[~((resolved['SOLUȚIE'].dt.month == 7) & (resolved['SOLUȚIE'].dt.day == 1))]
    sol_by_month = non_imputed.groupby(non_imputed['SOLUȚIE'].dt.month).size()

    ax = axes[1]
    ax.bar(sol_by_month.index, sol_by_month.values, color=COLOR_SECONDARY, zorder=3)
    ax.set_title('Art. 10 — Resolutions by Calendar Month\n(excl. imputed July 1 dates)')
    ax.set_ylabel('Total Dossiers')
    ax.set_xticks(range(1, 13))
    ax.set_xticklabels(months, fontsize=8)
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: f'{v:,.0f}'))

    excluded = len(resolved) - len(non_imputed)
    ax.annotate(f'{excluded:,} imputed Jul 1 dates excluded\n({excluded/len(resolved)*100:.0f}% of resolutions)',
                xy=(0.98, 0.95), xycoords='axes fraction', fontsize=7,
                ha='right', va='top', color='gray', style='italic')

    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, 'seasonality_art10.png'))
    plt.close(fig)
    print('  ✓ seasonality_art10.png')


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    os.makedirs(CHART_DIR, exist_ok=True)
    print(f'Output directory: {CHART_DIR}\n')

    df, events = load_data()
    print(f'Loaded {len(df):,} dossiers from {os.path.basename(CSV_DOSSIERS)}')
    print(f'Loaded {len(events)} events\n')

    print('Generating diagnostic charts...')
    chart_throughput_vs_backlog(df)
    chart_seasonality(df)

    print('\nAll Article 10 diagnostic charts generated successfully.')


if __name__ == '__main__':
    main()
