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

COLOR_A = '#EF4444'   # Hiring first (red)
COLOR_B = '#F59E0B'   # Reform first (amber)
COLOR_C = '#10B981'   # Law 14 only (green)
COLOR_D = '#2563EB'   # Combined (blue)
COLOR_GRAY = '#6B7280'

# ── Baseline Constants ───────────────────────────────────────────────────────
CURRENT_STAFF = 122
CURRENT_PRODUCTIVITY = 239  # dossiers/staff/year
CURRENT_MONTHLY_OUTPUT = 3300  # approximate from leadership analysis
INTAKE_STAFF_FRACTION = 0.20  # assumed fraction handling new registrations


# ── Data Loading ─────────────────────────────────────────────────────────────

def load_baselines():
    art10 = pd.read_csv(CSV_ART10)
    art11 = pd.read_csv(CSV_ART11)
    for df in [art10, art11]:
        df['DATA ÎNREGISTRĂRII'] = pd.to_datetime(df['DATA ÎNREGISTRĂRII'], format='%d.%m.%Y', errors='coerce')
        df['SOLUȚIE'] = pd.to_datetime(df['SOLUȚIE'], format='%d.%m.%Y', errors='coerce')
        df['reg_year'] = df['DATA ÎNREGISTRĂRII'].dt.year
        df['is_resolved'] = df['SOLUȚIE'].notna()
        df['wait_days'] = (df['SOLUȚIE'] - df['DATA ÎNREGISTRĂRII']).dt.days

    # Compute baselines
    def yearly_output_avg(df):
        resolved = df[df['is_resolved']].copy()
        resolved['sol_year'] = resolved['SOLUȚIE'].dt.year
        output = resolved.groupby('sol_year').size()
        return output.loc[2023:2025].mean()
    
    def current_backlog(df):
        intake = df.groupby('reg_year').size()
        resolved = df[df['is_resolved']].copy()
        resolved['sol_year'] = resolved['SOLUȚIE'].dt.year
        output = resolved.groupby('sol_year').size()
        combined = pd.DataFrame({'Intake': intake, 'Resolved': output}).fillna(0)
        combined = combined[combined.index <= 2025]
        combined['Net'] = combined['Intake'] - combined['Resolved']
        return combined['Net'].cumsum().iloc[-1]

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
        # (Using 2024 as the 'before' state rather than the long-term average)
        v24_avg = monthly[monthly.index.year == 2024].mean()
        floor_val = v24_avg * 0.25
        y_proj_post = np.maximum(np.polyval(coeffs_post, x_proj_post), floor_val)

        forecast_years = [2026, 2027, 2028]
        total_proj = 0
        for yr in forecast_years:
            idx_yr = (full_months_idx.year == yr) & (full_months_idx >= '2025-04')
            if any(idx_yr):
                # Calculate start index within the projected array
                first_month = full_months_idx[idx_yr][0]
                idx_in_post = len(pd.period_range(start='2025-04', end=first_month, freq='M')) - 1
                length = sum(idx_yr)
                val = np.sum(y_proj_post[idx_in_post:idx_in_post+length])
                total_proj += val
        
        return total_proj / len(forecast_years)

    backlog_10 = current_backlog(art10)
    backlog_11 = current_backlog(art11)
    
    # Use projected decaying Law 14 rates as the new baseline
    intake_10 = post_law14_intake_projected(art10)
    intake_11 = post_law14_intake_projected(art11)
    
    output_10 = yearly_output_avg(art10)
    output_11 = yearly_output_avg(art11)

    return {
        'backlog': backlog_10 + backlog_11,
        'backlog_10': backlog_10,
        'backlog_11': backlog_11,
        'intake': intake_10 + intake_11,
        'intake_10': intake_10,
        'intake_11': intake_11,
        'output': output_10 + output_11,
        'output_10': output_10,
        'output_11': output_11,
        'plateau_11': 76686,  # pre-COVID Art. 11 avg
    }


# ── P1: Reform Roadmap ──────────────────────────────────────────────────────

def chart_reform_roadmap(b):
    proj_years = list(range(2026, 2036))

    def project(intake_fn, staff_fn, prod_fn):
        bl = b['backlog']
        backlogs = []
        wait_years_cum = 0
        for i, yr in enumerate(proj_years):
            annual_intake = intake_fn(i)
            annual_output = staff_fn(i) * prod_fn(i)
            bl = max(0, bl + annual_intake - annual_output)
            backlogs.append(bl)
            wait_years_cum += bl
        return backlogs, wait_years_cum

    # Scenario A: Hiring first (+50 Y1, +50 Y2)
    bl_a, cum_a = project(
        intake_fn=lambda i: b['intake'],
        staff_fn=lambda i: CURRENT_STAFF + (50 if i >= 0 else 0) + (50 if i >= 1 else 0),
        prod_fn=lambda i: CURRENT_PRODUCTIVITY,
    )

    # Scenario B: Reform first (prod→400 by Y2, +50 staff Y3)
    bl_b, cum_b = project(
        intake_fn=lambda i: b['intake'],
        staff_fn=lambda i: CURRENT_STAFF + (50 if i >= 2 else 0),
        prod_fn=lambda i: 400 if i >= 1 else (320 if i >= 0 else CURRENT_PRODUCTIVITY),
    )

    # Scenario C: Status Quo (Post-Law 14 baseline)
    bl_c, cum_c = project(
        intake_fn=lambda i: b['intake'],
        staff_fn=lambda i: CURRENT_STAFF,
        prod_fn=lambda i: CURRENT_PRODUCTIVITY,
    )

    # Scenario D: Combined (Hiring + Reform + Law 14 baseline)
    bl_d, cum_d = project(
        intake_fn=lambda i: b['intake'],
        staff_fn=lambda i: CURRENT_STAFF + (50 if i >= 0 else 0),
        prod_fn=lambda i: 400 if i >= 1 else (320 if i >= 0 else CURRENT_PRODUCTIVITY),
    )

    fig, axes = plt.subplots(1, 2, figsize=(16, 6))

    # Backlog trajectory
    ax = axes[0]
    ax.plot(proj_years, bl_a, marker='o', color=COLOR_A, linewidth=1.5, markersize=4, label='A: Hiring first')
    ax.plot(proj_years, bl_b, marker='s', color=COLOR_B, linewidth=1.5, markersize=4, label='B: Reform first')
    ax.plot(proj_years, bl_c, marker='^', color=COLOR_C, linewidth=1.5, markersize=4, label='C: Law 14 only')
    ax.plot(proj_years, bl_d, marker='D', color=COLOR_D, linewidth=1.5, markersize=4, label='D: Combined')
    ax.axhline(0, color='gray', linewidth=0.5, alpha=0.3)
    ax.set_title('Backlog Trajectory by Reform Scenario')
    ax.set_ylabel('Pending Dossiers')
    ax.set_xlabel('Year')
    ax.xaxis.set_major_locator(ticker.MaxNLocator(integer=True))
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: f'{v:,.0f}'))
    ax.legend(fontsize=8)

    # Cumulative wait-years
    ax = axes[1]
    scenarios = ['A: Hiring\nfirst', 'B: Reform\nfirst', 'C: Status Quo\n(Law 14 only)', 'D: Combined\nReform']
    cum_values = [cum_a, cum_b, cum_c, cum_d]
    colors = [COLOR_A, COLOR_B, COLOR_C, COLOR_D]
    bars = ax.bar(scenarios, cum_values, color=colors, zorder=3)
    ax.set_title('Cumulative Wait-Years (10-Year Horizon)')
    ax.set_ylabel('Person-Years of Waiting')
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: f'{v:,.0f}'))
    for bar in bars:
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                f'{bar.get_height():,.0f}', ha='center', va='bottom', fontsize=8)

    fig.suptitle('P1 — Reform Roadmap: Sequenced Scenario Comparison',
                 fontsize=15, fontweight='bold', y=1.02)
    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, 'reform_roadmap.png'), bbox_inches='tight')
    plt.close(fig)
    print('  ✓ reform_roadmap.png')

    print('\n  Reform Roadmap (10-year cumulative wait-years):')
    for name, cum in zip(['A: Hiring first', 'B: Reform first', 'C: Status Quo (Post-Law 14)', 'D: Combined'], cum_values):
        print(f'    {name:30s}: {cum:>12,.0f}')


# ── P2: Law 14/2025 Clearance Window ────────────────────────────────────────

def chart_law14_clearance(b):
    proj_years = list(range(2026, 2046))  # 20-year horizon

    fig, ax = plt.subplots()

    for reduction, color, label in [
        (0.50, 'red', 'Law 14 Repeal (Intake +50%)'),
        (0.00, COLOR_C, 'Status Quo (Law 14 Baseline)'),
        (-0.20, COLOR_D, 'Optimistic (Law 14 -20%)'),
    ]:
        # reduction positive means INCREASING intake (repeal), negative means DECREASING
        sim_intake = b['intake'] * (1 + reduction)
        bl = b['backlog']
        proj = []
        clearance_year = None
        for yr in proj_years:
            bl = max(0, bl + sim_intake - b['output'])
            proj.append(bl)
            if bl <= 0 and clearance_year is None:
                clearance_year = yr

        ax.plot(proj_years, proj, linewidth=2, color=color, 
                label=f'{label} → {"cleared " + str(clearance_year) if clearance_year else "not cleared"}')

    ax.axhline(0, color='black', linewidth=0.8)
    ax.set_title('P2 — Law 14/2025: Long-Term Organic Clearance Window')
    ax.set_ylabel('Combined Pending Dossiers')
    ax.set_xlabel('Year')
    ax.set_ylim(0, 300000)
    ax.xaxis.set_major_locator(ticker.MaxNLocator(integer=True))
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: f'{v:,.0f}'))
    ax.legend(fontsize=9)

    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, 'law14_clearance_window.png'))
    plt.close(fig)
    print('  ✓ law14_clearance_window.png')


# ── P3: Capacity Redeployment ───────────────────────────────────────────────

def chart_capacity_redeployment(b):
    proj_years = list(range(2026, 2036))

    fig, ax = plt.subplots()

    # With Law 14 as the new baseline, we assess what redeployment of freed staff looks like vs status quo
    # Pre-Law 14 intake was higher. Let's assume INTAKE_STAFF_FRACTION was handling the pre-Law 14 volume.
    # The drop is ~60% combined.
    drop_fraction = 0.60 

    for redeploy, label, color in [
        (False, 'Status Quo (No redeployment)', COLOR_A),
        (True, 'With Redeployment of freed intake staff', COLOR_D),
    ]:
        bl = b['backlog']
        proj = []

        if redeploy:
            freed_staff = INTAKE_STAFF_FRACTION * CURRENT_STAFF * drop_fraction
            extra_output = freed_staff * CURRENT_PRODUCTIVITY
            total_output = b['output'] + extra_output
        else:
            total_output = b['output']

        for yr in proj_years:
            bl = max(0, bl + b['intake'] - total_output)
            proj.append(bl)

        ax.plot(proj_years, proj, marker='o' if redeploy else '', linestyle='-' if redeploy else '--', linewidth=1.5, markersize=4,
                color=color, label=label)

    ax.axhline(0, color='gray', linewidth=0.5, alpha=0.3)
    ax.set_title('P3 — Capacity Redeployment Under Law 14 Demand Reduction')
    ax.set_ylabel('Combined Pending Dossiers')
    ax.set_xlabel('Year')
    ax.xaxis.set_major_locator(ticker.MaxNLocator(integer=True))
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: f'{v:,.0f}'))
    ax.legend(fontsize=8)

    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, 'capacity_redeployment.png'))
    plt.close(fig)
    print('  ✓ capacity_redeployment.png')


# ── P5: Stress Test ─────────────────────────────────────────────────────────

def chart_stress_test(b):
    proj_years = list(range(2026, 2036))

    fig, axes = plt.subplots(1, 2, figsize=(16, 6))

    # Left: Status quo + shocks
    ax = axes[0]
    ax.set_title('Shock on Status Quo')
    for shock, color, label in [
        (1.0, COLOR_GRAY, 'No shock (baseline)'),
        (1.5, COLOR_B, '+50% demand surge in 2027'),
        (2.0, COLOR_A, '+100% demand surge in 2027'),
    ]:
        bl = b['backlog']
        proj = []
        for i, yr in enumerate(proj_years):
            intake = b['intake'] * (shock if i == 1 else 1.0)  # shock in Year 2 (2027)
            bl += intake - b['output']
            proj.append(bl)
        ax.plot(proj_years, proj, marker='o', linewidth=1.5, markersize=4,
                color=color, label=label)

    ax.set_ylabel('Pending Dossiers')
    ax.set_xlabel('Year')
    ax.xaxis.set_major_locator(ticker.MaxNLocator(integer=True))
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: f'{v:,.0f}'))
    ax.legend(fontsize=8)

    # Right: Reform scenario D + shocks
    ax = axes[1]
    ax.set_title('Shock on Reform Scenario D')
    for shock, color, label in [
        (1.0, COLOR_GRAY, 'No shock'),
        (1.5, COLOR_B, '+50% surge in 2027'),
        (2.0, COLOR_A, '+100% surge in 2027'),
    ]:
        bl = b['backlog']
        proj = []
        for i, yr in enumerate(proj_years):
            intake = b['intake'] * (shock if i == 1 else 1.0)
            staff = CURRENT_STAFF + (50 if i >= 0 else 0)
            prod = 400 if i >= 1 else 320
            output = staff * prod
            bl = max(0, bl + intake - output)
            proj.append(bl)
        ax.plot(proj_years, proj, marker='o', linewidth=1.5, markersize=4,
                color=color, label=label)

    ax.set_ylabel('Pending Dossiers')
    ax.set_xlabel('Year')
    ax.xaxis.set_major_locator(ticker.MaxNLocator(integer=True))
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: f'{v:,.0f}'))
    ax.legend(fontsize=8)

    fig.suptitle('P5 — Stress Test: Demand Shock Resilience',
                 fontsize=15, fontweight='bold', y=1.02)
    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, 'stress_test_scenarios.png'), bbox_inches='tight')
    plt.close(fig)
    print('  ✓ stress_test_scenarios.png')


# ── P6: Law 14 Repeal Scenario ──────────────────────────────────────────────

def chart_law14_repeal(b):
    proj_years = list(range(2026, 2036))

    fig, ax = plt.subplots()

    # Baseline: Law 14 holds (−30% intake)
    bl_holds = b['backlog']
    holds = []
    for yr in proj_years:
        bl_holds = max(0, bl_holds + b['intake'] * 0.7 - b['output'])
        holds.append(bl_holds)

    # Repeal in 2028: intake returns to pre-COVID plateau
    bl_repeal = b['backlog']
    repeal = []
    pre_covid_intake = b['intake_10'] + b['plateau_11']  # Art.10 current + Art.11 plateau
    for i, yr in enumerate(proj_years):
        if yr < 2028:
            intake = b['intake']
        else:
            intake = pre_covid_intake
        bl_repeal += intake - b['output']
        repeal.append(bl_repeal)

    ax.plot(proj_years, holds, marker='o', color=COLOR_C, linewidth=1.5, markersize=4,
            label='Status quo (Law 14 holds)')
    ax.plot(proj_years, repeal, marker='s', color=COLOR_A, linewidth=1.5, markersize=4,
            label=f'Law 14 repealed 2028 (intake→{pre_covid_intake:,.0f}/yr)')

    ax.set_title('P6 — Law 14/2025 Repeal Risk')
    ax.set_ylabel('Combined Pending Dossiers')
    ax.set_xlabel('Year')
    ax.xaxis.set_major_locator(ticker.MaxNLocator(integer=True))
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: f'{v:,.0f}'))
    ax.legend(fontsize=8)

    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, 'law14_repeal_risk.png'))
    plt.close(fig)
    print('  ✓ law14_repeal_risk.png')


# ── P7: KPI Dashboard ───────────────────────────────────────────────────────

def print_kpi_dashboard(b):
    monthly_output = CURRENT_MONTHLY_OUTPUT
    wait_years = b['backlog'] / b['output'] if b['output'] > 0 else 0

    print('\n' + '=' * 78)
    print('  P7 — KPI DASHBOARD')
    print('=' * 78)
    print(f'  {"KPI":<35s} {"Baseline":<15s} {"3-Year":<15s} {"5-Year":<15s}')
    print(f'  {"-"*35:<35s} {"-"*15:<15s} {"-"*15:<15s} {"-"*15:<15s}')
    print(f'  {"Monthly throughput":<35s} {f"{monthly_output:,}/mo":<15s} {"5,000/mo":<15s} {"6,500/mo":<15s}')
    print(f'  {"Queue depth":<35s} {f"{b['backlog']:,.0f}":<15s} {"120,000":<15s} {"50,000":<15s}')
    print(f'  {"New-applicant est. wait":<35s} {f"{wait_years:.1f} yr":<15s} {"4.0 yr":<15s} {"2.0 yr":<15s}')
    print(f'  {"Per-capita productivity":<35s} {f"{CURRENT_PRODUCTIVITY}/yr":<15s} {"400/yr":<15s} {"500/yr":<15s}')
    print(f'  {"2-year deadline compliance":<35s} {"~0%":<15s} {"30%":<15s} {"60%":<15s}')
    print('=' * 78)


# ── P8: Reform Impact Timeline ──────────────────────────────────────────────

def chart_reform_timeline(b):
    """Under Scenario D, when does each KPI hit its target?"""
    proj_years = list(range(2026, 2041))

    # Scenario D: +50 staff Y1, prod→400 Y2, −30% intake
    backlogs = []
    throughputs = []
    productivities = []
    wait_estimates = []

    bl = b['backlog']
    for i, yr in enumerate(proj_years):
        intake = b['intake']
        staff = CURRENT_STAFF + 50
        prod = 400 if i >= 1 else 320
        output = staff * prod
        bl = max(0, bl + intake - output)
        backlogs.append(bl)
        throughputs.append(output / 12)
        productivities.append(prod)
        wait_est = bl / output if output > 0 else 0
        wait_estimates.append(wait_est)

    fig, axes = plt.subplots(2, 2, figsize=(16, 10))

    # Queue depth
    ax = axes[0, 0]
    ax.plot(proj_years, backlogs, marker='o', color=COLOR_D, linewidth=1.5, markersize=4)
    ax.axhline(120000, color=COLOR_B, linestyle='--', alpha=0.5, label='3-yr target: 120K')
    ax.axhline(50000, color=COLOR_C, linestyle='--', alpha=0.5, label='5-yr target: 50K')
    ax.set_title('Queue Depth')
    ax.set_ylabel('Pending Dossiers')
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: f'{v:,.0f}'))
    ax.xaxis.set_major_locator(ticker.MaxNLocator(integer=True))
    ax.legend(fontsize=8)

    # Monthly throughput
    ax = axes[0, 1]
    ax.plot(proj_years, throughputs, marker='o', color=COLOR_D, linewidth=1.5, markersize=4)
    ax.axhline(5000, color=COLOR_B, linestyle='--', alpha=0.5, label='3-yr target: 5K/mo')
    ax.axhline(6500, color=COLOR_C, linestyle='--', alpha=0.5, label='5-yr target: 6.5K/mo')
    ax.set_title('Monthly Throughput')
    ax.set_ylabel('Dossiers/Month')
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: f'{v:,.0f}'))
    ax.xaxis.set_major_locator(ticker.MaxNLocator(integer=True))
    ax.legend(fontsize=8)

    # New-applicant wait
    ax = axes[1, 0]
    ax.plot(proj_years, wait_estimates, marker='o', color=COLOR_D, linewidth=1.5, markersize=4)
    ax.axhline(4.0, color=COLOR_B, linestyle='--', alpha=0.5, label='3-yr target: 4 yr')
    ax.axhline(2.0, color=COLOR_C, linestyle='--', alpha=0.5, label='5-yr target: 2 yr')
    ax.set_title('Estimated Wait for New Applicant')
    ax.set_ylabel('Years')
    ax.xaxis.set_major_locator(ticker.MaxNLocator(integer=True))
    ax.legend(fontsize=8)

    # Per-capita productivity
    ax = axes[1, 1]
    ax.plot(proj_years, productivities, marker='o', color=COLOR_D, linewidth=1.5, markersize=4)
    ax.axhline(400, color=COLOR_B, linestyle='--', alpha=0.5, label='3-yr target: 400/yr')
    ax.axhline(500, color=COLOR_C, linestyle='--', alpha=0.5, label='5-yr target: 500/yr')
    ax.set_title('Per-Capita Productivity')
    ax.set_ylabel('Dossiers/Staff/Year')
    ax.xaxis.set_major_locator(ticker.MaxNLocator(integer=True))
    ax.legend(fontsize=8)

    fig.suptitle('P8 — Reform Impact Timeline (Scenario D: Combined)',
                 fontsize=15, fontweight='bold', y=1.02)
    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, 'reform_timeline.png'), bbox_inches='tight')
    plt.close(fig)
    print('  ✓ reform_timeline.png')

    # Find when targets are hit
    print('\n  Reform Timeline (Scenario D):')
    for kpi, values, targets in [
        ('Queue depth', backlogs, [(120000, '3-yr'), (50000, '5-yr')]),
        ('Monthly throughput', throughputs, [(5000, '3-yr'), (6500, '5-yr')]),
        ('Wait estimate', wait_estimates, [(4.0, '3-yr'), (2.0, '5-yr')]),
        ('Productivity', productivities, [(400, '3-yr'), (500, '5-yr')]),
    ]:
        for target_val, target_name in targets:
            hit_year = None
            for yr, val in zip(proj_years, values):
                # For queue depth and wait, we want val <= target
                # For throughput and productivity, we want val >= target
                if kpi in ['Queue depth', 'Wait estimate']:
                    if val <= target_val:
                        hit_year = yr
                        break
                else:
                    if val >= target_val:
                        hit_year = yr
                        break
            status = f'reached in {hit_year}' if hit_year else 'not reached by 2040'
            print(f'    {kpi:25s} ({target_name:5s} target): {status}')


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    os.makedirs(CHART_DIR, exist_ok=True)
    print(f'Output directory: {CHART_DIR}\n')

    b = load_baselines()
    print(f'Baselines:')
    print(f'  Combined backlog: {b["backlog"]:,.0f}')
    print(f'  Annual intake:    {b["intake"]:,.0f}')
    print(f'  Annual output:    {b["output"]:,.0f}')
    print(f'  Net gap:          {b["intake"] - b["output"]:+,.0f}/yr\n')

    print('Generating prescriptive charts...')
    chart_reform_roadmap(b)
    chart_law14_clearance(b)
    chart_capacity_redeployment(b)
    chart_stress_test(b)
    chart_law14_repeal(b)
    print_kpi_dashboard(b)
    chart_reform_timeline(b)

    print('\nAll prescriptive charts generated successfully.')


if __name__ == '__main__':
    main()
