import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from datetime import datetime
from lifelines import KaplanMeierFitter

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

# ── Data Loading ─────────────────────────────────────────────────────────────

def load_data():
    df = pd.read_csv(CSV_DOSSIERS)
    df['DATA ÎNREGISTRĂRII'] = pd.to_datetime(df['DATA ÎNREGISTRĂRII'], format='%d.%m.%Y', errors='coerce')
    df['SOLUȚIE'] = pd.to_datetime(df['SOLUȚIE'], format='%d.%m.%Y', errors='coerce')
    df['reg_year'] = df['DATA ÎNREGISTRĂRII'].dt.year
    df['is_resolved'] = df['SOLUȚIE'].notna()
    df['wait_days'] = (df['SOLUȚIE'] - df['DATA ÎNREGISTRĂRII']).dt.days
    return df


# ── Q1: Intake Demand Forecast ──────────────────────────────────────────────

def chart_intake_forecast(df):
    df_months = df.copy()
    df_months['month'] = df_months['DATA ÎNREGISTRĂRII'].dt.to_period('M')
    monthly = df_months.groupby('month').size()
    
    # Filter for post-COVID period
    monthly = monthly[monthly.index >= '2021-01']
    
    # Pre-Law 14 (Jan 2021 to Feb 2025)
    pre_law = monthly[monthly.index <= '2025-02']
    x_pre = np.arange(len(pre_law))
    y_pre = pre_law.values
    coeffs_pre = np.polyfit(x_pre, y_pre, 1)

    # Post-Law 14 (Apr 2025 onwards)
    post_law = monthly[monthly.index >= '2025-04']
    x_post = np.arange(len(post_law))
    y_post = post_law.values
    
    if len(post_law) > 1:
        coeffs_post = np.polyfit(x_post, y_post, 1)
    else:
        coeffs_post = [0, post_law.mean() if len(post_law) > 0 else 0]

    # Full Timeline for X-axis (Jan 2021 to Dec 2028)
    full_months_idx = pd.period_range(start='2021-01', end='2028-12', freq='M')
    x_full = np.arange(len(full_months_idx))

    # Pre-Law Projection over full timeline
    y_proj_pre = np.polyval(coeffs_pre, x_full)

    # Post-Law Projection starting from Apr 2025
    post_start_idx = len(pd.period_range(start='2021-01', end='2025-03', freq='M'))
    x_proj_post = np.arange(len(full_months_idx) - post_start_idx)
    y_proj_post = np.polyval(coeffs_post, x_proj_post)
    
    # B1 Structural Floor: Assume long-term demand stabilizes at 25% of the 2024 Peak levels
    # (Using 2024 as the 'before' state rather than the 5-year average)
    v24_avg = monthly[monthly.index.year == 2024].mean()
    floor_val = v24_avg * 0.25
    y_proj_post = np.maximum(y_proj_post, floor_val)

    fig, ax = plt.subplots(figsize=(14, 6))
    
    # Convert period index to datetime for plotting natively
    hist_dates = monthly.index.to_timestamp()
    full_dates = full_months_idx.to_timestamp()
    post_dates = full_months_idx[post_start_idx:].to_timestamp()

    # Historical
    ax.bar(hist_dates, monthly.values, width=20, color=COLOR_PRIMARY, alpha=0.6, zorder=3, label='Historical Monthly Intake')

    # Pre-Law Trend
    ax.plot(full_dates, y_proj_pre, '--', color=COLOR_SECONDARY, linewidth=2,
            label='Pre-Law 14 Trend (What-if Scenario)')

    # Post-Law Trend
    ax.plot(post_dates, y_proj_post, '-', color='purple', linewidth=2.5,
            label='Post-Law 14 Trend (Decaying to B1 Structural Floor)')

    # Law 14 marker
    law14_date = pd.to_datetime('2025-03-01')
    ax.axvline(law14_date, color=COLOR_DANGER, linestyle=':', linewidth=2, label='Law 14 Effective (Mar 2025)')

    # Shade forecast zone
    forecast_start = pd.to_datetime('2026-01-01')
    forecast_end = pd.to_datetime('2028-12-31')
    ax.axvspan(forecast_start, forecast_end, alpha=0.06, color='gray', label='Forecast Zone (2026-2028)')

    ax.set_title('Article 11 — Monthly Intake Demand Forecast (2021–2028)\nContinuing Post-Law 14 Decay')
    ax.set_ylabel('Dossiers Registered per Month')
    ax.set_xlabel('Month')
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: f'{v:,.0f}'))
    ax.legend(fontsize=9, loc='upper left')

    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, 'intake_forecast_art11.png'))
    plt.close(fig)
    print('  ✓ intake_forecast_art11.png')

    # Calculate annualized post-law 14 averages for the next 3 years
    print('\n  Intake Forecast (Post-Law 14 Annualized):')
    annualized_avg = 0
    forecast_years = [2026, 2027, 2028]
    total_proj = 0
    for yr in forecast_years:
        idx_yr = (full_months_idx.year == yr) & (full_months_idx >= '2025-04')
        if not any(idx_yr):
            val = 0
        else:
            # We need to map boolean index back to the slice for post
            idx_in_post = np.where(full_dates == full_months_idx[idx_yr][0].to_timestamp())[0][0] - post_start_idx
            val = np.sum(y_proj_post[idx_in_post:idx_in_post+12])
        print(f'    {yr}: {val:>8,.0f}')
        total_proj += val
    
    post_law14_annualized = total_proj / len(forecast_years)
    print(f'    -> 3-Year Avg: {post_law14_annualized:,.0f}/yr')

    return post_law14_annualized


# ── Q2: Backlog Projection ──────────────────────────────────────────────────

def chart_backlog_projection(df, projected_annual_intake):
    yearly_intake = df.groupby('reg_year').size()
    resolved = df[df['is_resolved']].copy()
    resolved['sol_year'] = resolved['SOLUȚIE'].dt.year
    yearly_output = resolved.groupby('sol_year').size()

    combined = pd.DataFrame({
        'Intake': yearly_intake,
        'Resolved': yearly_output
    }).fillna(0)
    combined = combined[combined.index <= 2025]
    combined['Net'] = combined['Intake'] - combined['Resolved']
    combined['Backlog'] = combined['Net'].cumsum()

    # Project forward: use Law 14 adjusted intake, keep recent output baseline
    recent_output = combined.loc[2023:2025, 'Resolved'].mean()
    current_backlog = combined['Backlog'].iloc[-1]

    proj_years = list(range(2026, 2031))
    proj_backlog = []
    bl = current_backlog
    for _ in proj_years:
        bl += (projected_annual_intake - recent_output)
        proj_backlog.append(bl)

    fig, ax = plt.subplots()
    ax.plot(combined.index, combined['Backlog'], marker='o', color=COLOR_PRIMARY,
            linewidth=1.5, markersize=5, zorder=3, label='Historical Backlog')
    ax.plot(proj_years, proj_backlog, marker='s', color=COLOR_DANGER,
            linewidth=1.5, markersize=5, linestyle='--', zorder=3, label='Projected (Law 14 adjustment)')

    ax.axvspan(2025.5, 2030.5, alpha=0.06, color='gray')
    ax.set_title('Article 11 — Cumulative Backlog Projection (Law 14 Adjusted)')
    ax.set_ylabel('Pending Dossiers')
    ax.set_xlabel('Year')
    ax.xaxis.set_major_locator(ticker.MaxNLocator(integer=True))
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: f'{v:,.0f}'))
    ax.legend()

    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, 'backlog_projection_art11.png'))
    plt.close(fig)
    print('  ✓ backlog_projection_art11.png')

    print(f'\n  Backlog Projection (adj intake={projected_annual_intake:,.0f}, avg output={recent_output:,.0f}):')
    for yr, bl in zip(proj_years, proj_backlog):
        print(f'    {yr}: {bl:>10,.0f}')

    return current_backlog, recent_output


# ── Q6: Queue Wait Estimate ─────────────────────────────────────────────────

def print_queue_wait(current_backlog, annual_output):
    if annual_output > 0:
        wait_years = current_backlog / annual_output
        print(f'\n  Q6 — Expected Wait for a Dossier Filed Today:')
        print(f'    Current backlog:     {current_backlog:>10,.0f}')
        print(f'    Annual output (avg): {annual_output:>10,.0f}')
        print(f'    Estimated wait:      {wait_years:>10.1f} years ({wait_years * 365:,.0f} days)')


# ── Q7: Kaplan-Meier Survival Analysis ──────────────────────────────────────

def chart_survival_analysis(df):
    ref_date = df['DATA ÎNREGISTRĂRII'].max()

    analysis = df[df['DATA ÎNREGISTRĂRII'].notna()].copy()
    analysis['duration'] = np.where(
        analysis['is_resolved'],
        analysis['wait_days'],
        (ref_date - analysis['DATA ÎNREGISTRĂRII']).dt.days
    )
    analysis['observed'] = analysis['is_resolved'].astype(int)
    analysis = analysis[analysis['duration'] > 0]

    kmf = KaplanMeierFitter()
    kmf.fit(analysis['duration'], event_observed=analysis['observed'],
            label='Article 11')

    fig, ax = plt.subplots()
    kmf.plot_survival_function(ax=ax, color=COLOR_PRIMARY, linewidth=1.5)
    ax.set_title('Article 11 — Kaplan-Meier Survival Curve (Time to Resolution)')
    ax.set_xlabel('Days Since Registration')
    ax.set_ylabel('Probability of Still Waiting')
    ax.axhline(0.5, color=COLOR_ACCENT, linestyle='--', linewidth=0.8, alpha=0.5, label='50% (Median)')
    ax.axhline(0.25, color=COLOR_DANGER, linestyle='--', linewidth=0.8, alpha=0.5, label='25% (75th pct)')
    ax.legend()

    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, 'survival_curve_art11.png'))
    plt.close(fig)
    print('  ✓ survival_curve_art11.png')

    median_surv = kmf.median_survival_time_
    naive_median = df.loc[df['is_resolved'] & (df['wait_days'] > 0), 'wait_days'].median()
    print(f'\n  Survival Analysis:')
    print(f'    Naive median (resolved only):   {naive_median:>8,.0f} days ({naive_median/365:.1f} yrs)')
    print(f'    KM corrected median (all):      {median_surv:>8,.0f} days ({median_surv/365:.1f} yrs)')
    print(f'    Bias correction:                {median_surv - naive_median:>+8,.0f} days')


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    os.makedirs(CHART_DIR, exist_ok=True)
    print(f'Output directory: {CHART_DIR}\n')

    df = load_data()
    print(f'Loaded {len(df):,} dossiers\n')

    print('Generating predictive charts...')
    post_law14_annualized = chart_intake_forecast(df)
    current_backlog, recent_output = chart_backlog_projection(df, post_law14_annualized)
    print_queue_wait(current_backlog, recent_output)
    chart_survival_analysis(df)

    print('\nAll Article 11 predictive charts generated successfully.')


if __name__ == '__main__':
    main()
