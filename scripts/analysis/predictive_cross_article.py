import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

# ── Paths ────────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '../../'))
DATA_DIR = os.path.join(PROJECT_ROOT, 'data', 'processed')
CHART_DIR = os.path.join(PROJECT_ROOT, 'reports', 'charts', 'cross_article')

CSV_ART10 = os.path.join(DATA_DIR, 'dosare_art10.csv')
CSV_ART11 = os.path.join(DATA_DIR, 'dosare_art11.csv')
CSV_STAFFING = os.path.join(DATA_DIR, 'anc_staffing.csv')

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
COLOR_REFORM = '#8B5CF6'

# ── Data Loading ─────────────────────────────────────────────────────────────

def load_dossiers(csv_path):
    df = pd.read_csv(csv_path)
    df['DATA ÎNREGISTRĂRII'] = pd.to_datetime(df['DATA ÎNREGISTRĂRII'], format='%d.%m.%Y', errors='coerce')
    df['SOLUȚIE'] = pd.to_datetime(df['SOLUȚIE'], format='%d.%m.%Y', errors='coerce')
    df['reg_year'] = df['DATA ÎNREGISTRĂRII'].dt.year
    df['is_resolved'] = df['SOLUȚIE'].notna()
    df['wait_days'] = (df['SOLUȚIE'] - df['DATA ÎNREGISTRĂRII']).dt.days
    return df


def compute_backlog(df):
    yearly_intake = df.groupby('reg_year').size()
    resolved = df[df['is_resolved']].copy()
    resolved['sol_year'] = resolved['SOLUȚIE'].dt.year
    yearly_output = resolved.groupby('sol_year').size()
    combined = pd.DataFrame({'Intake': yearly_intake, 'Resolved': yearly_output}).fillna(0)
    combined = combined[combined.index <= 2025]
    combined['Net'] = combined['Intake'] - combined['Resolved']
    combined['Backlog'] = combined['Net'].cumsum()
    return combined


def post_law14_intake_projected(df):
    df_m = df.copy()
    df_m['month'] = df_m['DATA ÎNREGISTRĂRII'].dt.to_period('M')
    monthly = df_m.groupby('month').size()
    monthly = monthly[monthly.index >= '2021-01']
    post_l14 = monthly[monthly.index >= '2025-04']
    
    if len(post_l14) <= 1:
        return post_l14.mean() * 12 if len(post_l14) == 1 else 0
        
    x_post = np.arange(len(post_l14))
    y_post = post_l14.values
    coeffs_post = np.polyfit(x_post, y_post, 1)

    full_months_idx = pd.period_range(start='2021-01', end='2028-12', freq='M')
    post_start_idx = len(pd.period_range(start='2021-01', end='2025-03', freq='M'))
    x_proj_post = np.arange(len(full_months_idx) - post_start_idx)
    
    # B1 Structural Floor: Assume long-term demand stabilizes at 25% of the 2024 Peak levels
    v24_avg = monthly[monthly.index.year == 2024].mean()
    floor_val = v24_avg * 0.25
    y_proj_post = np.maximum(np.polyval(coeffs_post, x_proj_post), floor_val)

    # Average over next 3 years
    forecast_years = [2026, 2027, 2028]
    total_proj = 0
    for yr in forecast_years:
        idx_yr = (full_months_idx.year == yr) & (full_months_idx >= '2025-04')
        if any(idx_yr):
            first_month = full_months_idx[idx_yr][0]
            idx_in_post = len(pd.period_range(start='2025-04', end=first_month, freq='M')) - 1
            length = sum(idx_yr)
            val = np.sum(y_proj_post[idx_in_post:idx_in_post+length])
            total_proj += val
    
    return total_proj / len(forecast_years)


def load_all():
    art10 = load_dossiers(CSV_ART10)
    art11 = load_dossiers(CSV_ART11)
    staffing = pd.read_csv(CSV_STAFFING)
    return art10, art11, staffing


# ── Q3: Scenario Backlog Analysis ───────────────────────────────────────────

def chart_scenario_backlog(art10, art11):
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))

    for ax, df, label, color in [
        (axes[0], art10, 'Article 10', COLOR_ART10),
        (axes[1], art11, 'Article 11', COLOR_ART11),
    ]:
        combined = compute_backlog(df)
        current_backlog = combined['Backlog'].iloc[-1]
        
        # Use Law 14 adjusted baseline rather than historical avg
        baseline_intake = post_law14_intake_projected(df)
        recent_output = combined.loc[2023:2025, 'Resolved'].mean()

        proj_years = list(range(2026, 2036))

        # Status quo (Law 14 adjustment)
        bl_sq = current_backlog
        sq = []
        for _ in proj_years:
            bl_sq += (baseline_intake - recent_output)
            sq.append(max(bl_sq, 0))

        # Reform: output doubles
        bl_ref = current_backlog
        ref = []
        for _ in proj_years:
            bl_ref += (baseline_intake - recent_output * 2)
            ref.append(max(bl_ref, 0))

        # Demand shock: baseline intake drops ANOTHER 30%
        bl_ds = current_backlog
        ds = []
        for _ in proj_years:
            bl_ds += (baseline_intake * 0.7 - recent_output)
            ds.append(max(bl_ds, 0))

        # Historical
        ax.plot(combined.index, combined['Backlog'], marker='o', color=color,
                linewidth=1.5, markersize=4, zorder=3, label='Historical')
        ax.plot(proj_years, sq, '--', color=COLOR_DANGER, linewidth=1.5, label='Status quo')
        ax.plot(proj_years, ref, '--', color=COLOR_REFORM, linewidth=1.5, label='Reform (2× output)')
        ax.plot(proj_years, ds, '--', color=COLOR_ACCENT, linewidth=1.5, label='Demand −30%')

        ax.axvspan(2025.5, 2035.5, alpha=0.04, color='gray')
        ax.set_title(f'{label} — Backlog Scenarios')
        ax.set_ylabel('Pending Dossiers')
        ax.set_xlabel('Year')
        ax.xaxis.set_major_locator(ticker.MaxNLocator(integer=True))
        ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: f'{v:,.0f}'))
        ax.legend(fontsize=7)

    fig.suptitle('Backlog Trajectory — Three Scenarios (10-Year Horizon)',
                 fontsize=15, fontweight='bold', y=1.02)
    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, 'scenario_backlog.png'), bbox_inches='tight')
    plt.close(fig)
    print('  ✓ scenario_backlog.png')


# ── Q4: Break-Even Staffing Levels ──────────────────────────────────────────

def chart_staffing_requirements(art10, art11, staffing):
    combined_10 = compute_backlog(art10)
    combined_11 = compute_backlog(art11)

    backlog_10 = combined_10['Backlog'].iloc[-1]
    backlog_11 = combined_11['Backlog'].iloc[-1]
    total_backlog = backlog_10 + backlog_11

    intake_10 = post_law14_intake_projected(art10)
    intake_11 = post_law14_intake_projected(art11)
    total_intake = intake_10 + intake_11

    current_staff = staffing.iloc[-1]['Estimated_Actual_Staff']
    productivity_current = 239  # 2025 measured
    productivity_recovered = 500  # 2016-era target

    scenarios = {
        'Match intake\n(zero growth)': total_intake,
        'Clear in\n10 years': total_intake + total_backlog / 10,
        'Clear in\n5 years': total_intake + total_backlog / 5,
        'Clear in\n3 years': total_intake + total_backlog / 3,
    }

    labels = list(scenarios.keys())
    staff_239 = [v / productivity_current for v in scenarios.values()]
    staff_500 = [v / productivity_recovered for v in scenarios.values()]

    fig, ax = plt.subplots(figsize=(12, 6))
    x = np.arange(len(labels))
    width = 0.35

    bars1 = ax.bar(x - width/2, staff_239, width, label=f'At current productivity ({productivity_current}/staff/yr)',
                   color=COLOR_DANGER, zorder=3, alpha=0.8)
    bars2 = ax.bar(x + width/2, staff_500, width, label=f'At recovered productivity ({productivity_recovered}/staff/yr)',
                   color=COLOR_REFORM, zorder=3, alpha=0.8)

    ax.axhline(current_staff, color=COLOR_ACCENT, linestyle='--', linewidth=1.5,
               label=f'Current staff: {current_staff:.0f}')

    ax.set_title(f'Required Staffing Levels (Combined Backlog: {total_backlog:,.0f})')
    ax.set_ylabel('Staff Required')
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=9)
    ax.legend(fontsize=8)

    for bar in bars1:
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height(),
                f'{bar.get_height():.0f}', ha='center', va='bottom', fontsize=8)
    for bar in bars2:
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height(),
                f'{bar.get_height():.0f}', ha='center', va='bottom', fontsize=8)

    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, 'staffing_requirements.png'))
    plt.close(fig)
    print('  ✓ staffing_requirements.png')

    print(f'\n  Staffing Requirements (backlog={total_backlog:,.0f}, intake={total_intake:,.0f}/yr):')
    for label, s239, s500 in zip(labels, staff_239, staff_500):
        print(f'    {label:20s}: @239/yr → {s239:>5.0f} staff  |  @500/yr → {s500:>5.0f} staff')


# ── Q5: Productivity Recovery Impact ────────────────────────────────────────

def chart_productivity_recovery(art10, art11, staffing):
    combined_10 = compute_backlog(art10)
    combined_11 = compute_backlog(art11)

    total_backlog = combined_10['Backlog'].iloc[-1] + combined_11['Backlog'].iloc[-1]
    total_intake = (post_law14_intake_projected(art10) +
                    post_law14_intake_projected(art11))

    current_staff = staffing.iloc[-1]['Estimated_Actual_Staff']
    proj_years = list(range(2026, 2036))

    fig, ax = plt.subplots()

    for prod, color, label in [
        (239, COLOR_DANGER, 'Current (239/staff/yr)'),
        (400, COLOR_ACCENT, 'Partial recovery (400)'),
        (500, COLOR_REFORM, 'Target recovery (500)'),
        (600, COLOR_ART11, 'Optimistic (600)'),
    ]:
        annual_output = current_staff * prod
        bl = total_backlog
        proj = []
        for _ in proj_years:
            bl += (total_intake - annual_output)
            proj.append(max(bl, 0))
        ax.plot(proj_years, proj, marker='o', linewidth=1.5, markersize=4,
                color=color, label=label)

    ax.axhline(0, color='gray', linestyle='-', linewidth=0.5, alpha=0.3)
    ax.axvspan(2025.5, 2035.5, alpha=0.04, color='gray')
    ax.set_title(f'Backlog Trajectory by Per-Capita Productivity (Staff={current_staff:.0f})')
    ax.set_ylabel('Combined Pending Dossiers')
    ax.set_xlabel('Year')
    ax.xaxis.set_major_locator(ticker.MaxNLocator(integer=True))
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: f'{v:,.0f}'))
    ax.legend(fontsize=8)

    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, 'productivity_recovery_impact.png'))
    plt.close(fig)
    print('  ✓ productivity_recovery_impact.png')


# ── Q11/Q12: Cost of Inaction & Reform Package ─────────────────────────────

def print_prescriptive_summary(art10, art11, staffing):
    combined_10 = compute_backlog(art10)
    combined_11 = compute_backlog(art11)

    backlog_10 = combined_10['Backlog'].iloc[-1]
    backlog_11 = combined_11['Backlog'].iloc[-1]
    total_backlog = backlog_10 + backlog_11

    intake_10 = post_law14_intake_projected(art10)
    intake_11 = post_law14_intake_projected(art11)
    output_10 = combined_10.loc[2023:2025, 'Resolved'].mean()
    output_11 = combined_11.loc[2023:2025, 'Resolved'].mean()
    total_intake = intake_10 + intake_11
    total_output = output_10 + output_11

    current_staff = staffing.iloc[-1]['Estimated_Actual_Staff']

    # Cost of inaction: person-years of waiting over 5 years
    bl = total_backlog
    cumulative_person_years = 0
    for _ in range(5):
        bl += (total_intake - total_output)
        cumulative_person_years += bl

    print('\n' + '=' * 70)
    print('  PRESCRIPTIVE SUMMARY')
    print('=' * 70)

    print(f'\n  Q11 — Cost of Inaction (5-year horizon):')
    print(f'    Current backlog:           {total_backlog:>10,.0f} dossiers')
    print(f'    Projected backlog (2030):   {bl:>10,.0f} dossiers')
    print(f'    Cumulative wait burden:     {cumulative_person_years:>10,.0f} person-years')
    print(f'    → Every year of delay adds ~{total_intake - total_output:,.0f} person-years to the queue')

    print(f'\n  Q12 — Minimum Viable Reform Package (5-year clearance):')
    # Need output = intake + backlog/5
    required_output = total_intake + total_backlog / 5

    # Option A: Staffing only (at current productivity 239)
    staff_needed_239 = required_output / 239
    # Option B: Productivity recovery to 500 (at current staff)
    prod_needed = required_output / current_staff
    # Option C: Hybrid — raise staff to 200, need productivity = required_output / 200
    hybrid_prod = required_output / 200

    print(f'    Required annual output:     {required_output:>10,.0f}')
    print(f'    Option A (hire only):        {staff_needed_239:>10,.0f} staff @ 239/yr productivity')
    print(f'    Option B (reform only):      productivity must reach {prod_needed:>,.0f}/staff/yr @ {current_staff:.0f} staff')
    print(f'    Option C (hybrid):           200 staff @ {hybrid_prod:,.0f}/staff/yr productivity')

    print('=' * 70)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    os.makedirs(CHART_DIR, exist_ok=True)
    print(f'Output directory: {CHART_DIR}\n')

    art10, art11, staffing = load_all()
    print(f'Loaded {len(art10):,} Art. 10 dossiers')
    print(f'Loaded {len(art11):,} Art. 11 dossiers\n')

    print('Generating cross-article predictive charts...')
    chart_scenario_backlog(art10, art11)
    chart_staffing_requirements(art10, art11, staffing)
    chart_productivity_recovery(art10, art11, staffing)
    print_prescriptive_summary(art10, art11, staffing)

    print('\nAll cross-article predictive charts generated successfully.')


if __name__ == '__main__':
    main()
