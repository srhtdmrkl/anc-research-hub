import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import os

def run_crossover_simulation():
    print("Initializing Crossover Simulation...")
    df10 = pd.read_csv('data/processed/dosare_art10.csv')
    df11 = pd.read_csv('data/processed/dosare_art11.csv')
    
    # 1. Calculate Baselines (Active Backlog as of now)
    # Status is implicit: pending if SOLUȚIE is empty
    backlog_10 = df10['SOLUȚIE'].isna().sum()
    backlog_11 = df11['SOLUȚIE'].isna().sum()
    
    print(f"Current Backlog (Art 10): {backlog_10:,}")
    print(f"Current Backlog (Art 11): {backlog_11:,}")
    
    # 2. Estimate Current Velocity (Last 6 months of 2025/early 2026)
    df10['reg_date'] = pd.to_datetime(df10['DATA ÎNREGISTRĂRII'], format='%d.%m.%Y', errors='coerce')
    df11['reg_date'] = pd.to_datetime(df11['DATA ÎNREGISTRĂRII'], format='%d.%m.%Y', errors='coerce')
        
    MONTHLY_OUTPUT_11 = 3500 
    MONTHLY_OUTPUT_10 = 500
    
    # Current Intake (approx)
    MONTHLY_INTAKE_10 = 500 # Art 10 is resilient
    MONTHLY_INTAKE_11 = 2000 # Law 14 Post-B1 Floor
    
    months = pd.date_range(start='2026-04-01', periods=60, freq='MS')
    
    results = []
    curr_10 = backlog_10
    curr_11 = backlog_11
    
    crossover_date = None
    
    for m in months:
        # Article 11 Decay (Intake continues to drop as language gate fully matures)
        # We model a 2% monthly structural decline until it hits a base floor of 800
        MONTHLY_INTAKE_11 = max(800, MONTHLY_INTAKE_11 * 0.98)
        
        # Article 10 stability
        
        # Update Backlogs
        curr_10 = max(0, curr_10 + MONTHLY_INTAKE_10 - MONTHLY_OUTPUT_10)
        curr_11 = max(0, curr_11 + MONTHLY_INTAKE_11 - MONTHLY_OUTPUT_11)
        
        results.append({
            'Date': m,
            'Art 10 Backlog': curr_10,
            'Art 11 Backlog': curr_11
        })
        
        if crossover_date is None and curr_10 >= curr_11:
            crossover_date = m

    sim_df = pd.DataFrame(results)
    
    print(f"\nSimulation Complete.")
    if crossover_date:
        print(f"CRITICAL: Crossover predicted for {crossover_date.strftime('%B %Y')}")
    else:
        print("No crossover found in 5-year window.")
        
    # Visualizations
    os.makedirs('reports/charts/realization', exist_ok=True)
    plt.figure(figsize=(12, 7))
    plt.plot(sim_df['Date'], sim_df['Art 11 Backlog'], label='Art 11 (Re-acquisition)', color='teal', linewidth=3)
    plt.plot(sim_df['Date'], sim_df['Art 10 Backlog'], label='Art 10 (Restoration)', color='coral', linewidth=3)
    
    if crossover_date:
        plt.axvline(crossover_date, color='red', linestyle='--', alpha=0.5)
        plt.annotate(f'The Crossover\n{crossover_date.strftime("%b %Y")}', 
                     xy=(crossover_date, curr_10), xytext=(20, 40),
                     textcoords='offset points', arrowprops=dict(arrowstyle='->'))

    plt.title("Backlog Convergeance Simulation (Law 14 Effect)\nPredicting the pivot in ANC institutional focus")
    plt.ylabel("Pending Dossiers")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.savefig('reports/charts/realization/backlog_crossover.png')
    
    return sim_df, crossover_date

if __name__ == "__main__":
    run_crossover_simulation()
