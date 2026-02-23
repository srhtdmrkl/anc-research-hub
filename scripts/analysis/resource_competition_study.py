import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import os

def analyze_resource_competition():
    print("Loading data for resource competition analysis...")
    df10 = pd.read_csv('data/processed/dosare_art10.csv')
    df11 = pd.read_csv('data/processed/dosare_art11.csv')
    
    # Parse dates
    df10['reg_date'] = pd.to_datetime(df10['DATA ÎNREGISTRĂRII'], format='%d.%m.%Y', errors='coerce')
    df11['sol_date'] = pd.to_datetime(df11['SOLUȚIE'], format='%d.%m.%Y', errors='coerce')
    
    # 1. Construct Monthly Series
    # Art 10 Intake
    art10_intake = df10.set_index('reg_date').resample('M').size().rename('art10_intake')
    
    # Art 11 Throughput
    art11_throughput = df11.set_index('sol_date').resample('M').size().rename('art11_throughput')
    
    # Align
    analysis_df = pd.concat([art10_intake, art11_throughput], axis=1).fillna(0)
    
    # Filter to era where both have data (2012-2025)
    analysis_df = analysis_df.loc['2012-01-01':'2025-12-31']
    
    # 2. Correlation Analysis
    correlation = analysis_df.corr().iloc[0, 1]
    print(f"Overall Correlation (Art 10 Intake vs Art 11 Throughput): {correlation:.3f}")
    
    # Lag Analysis
    lags = []
    for i in range(7):
        lag_corr = analysis_df['art10_intake'].corr(analysis_df['art11_throughput'].shift(-i))
        lags.append({'lag_months': i, 'correlation': lag_corr})
    
    lags_df = pd.DataFrame(lags)
    print("\nLag Analysis (Does Art 10 surge affect Art 11 later?):")
    print(lags_df)
    
    # 3. Visualization: The Scissors Plot
    os.makedirs('reports/charts/competition', exist_ok=True)
    
    # Standardize for visual comparison
    analysis_df_std = (analysis_df - analysis_df.mean()) / analysis_df.std()
    
    plt.figure(figsize=(14, 7))
    plt.plot(analysis_df_std.index, analysis_df_std['art10_intake'], label='Art 10 Intake (Z-Score)', color='coral', linewidth=2)
    plt.plot(analysis_df_std.index, analysis_df_std['art11_throughput'], label='Art 11 Throughput (Z-Score)', color='teal', linewidth=2, linestyle='--')
    
    # Highlight "Scissors" events (Art 10 high, Art 11 low)
    scissors_events = analysis_df_std[(analysis_df_std['art10_intake'] > 1) & (analysis_df_std['art11_throughput'] < -0.5)]
    plt.scatter(scissors_events.index, [0]*len(scissors_events), color='red', marker='x', s=100, label='Scissors Event')
    
    plt.title("The 'Scissors Effect': Resource Competition Analysis\nDo Article 10 Surges Cannibalize Article 11 Capacity?")
    plt.xlabel("Year")
    plt.ylabel("Standardized Volume (Z-Score)")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig('reports/charts/competition/scissors_plot.png')
    
    # 4. Rolling Correlation
    analysis_df['rolling_corr'] = analysis_df['art10_intake'].rolling(12).corr(analysis_df['art11_throughput'])
    
    plt.figure(figsize=(14, 5))
    plt.plot(analysis_df.index, analysis_df['rolling_corr'], color='purple')
    plt.axhline(0, color='black', linestyle='--')
    plt.title("12-Month Rolling Correlation: Resource Competition Over Time")
    plt.ylabel("Correlation Coefficient")
    plt.savefig('reports/charts/competition/rolling_competition_corr.png')
    
    print(f"\nSaved plots to reports/charts/competition/")
    
    return analysis_df

if __name__ == "__main__":
    analyze_resource_competition()
