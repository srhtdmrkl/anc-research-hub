import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import os

def analyze_orphans():
    print("Loading and preprocessing data...")
    df10 = pd.read_csv('data/processed/dosare_art10.csv')
    df11 = pd.read_csv('data/processed/dosare_art11.csv')
    
    df10['article'] = '10'
    df11['article'] = '11'
    df = pd.concat([df10, df11], ignore_index=True)
    
    # Standardize column names if needed
    df['reg_date'] = pd.to_datetime(df['DATA ÎNREGISTRĂRII'], format='%d.%m.%Y', errors='coerce')
    df['sol_date'] = pd.to_datetime(df['SOLUȚIE'], format='%d.%m.%Y', errors='coerce')
    
    # 1. Define Orphans
    # Registered before 2020-01-01 and still pending (no sol_date)
    cutoff_date = pd.to_datetime('2020-01-01')
    df['is_orphan'] = (df['reg_date'] < cutoff_date) & (df['sol_date'].isna())
    df['is_mature'] = (df['reg_date'] < cutoff_date) # Total eligible for being an orphan (old enough)
    
    mature_df = df[df['is_mature'] & df['reg_date'].notna()].copy()
    
    print(f"Total Mature Dossiers (Pre-2020): {len(mature_df):,}")
    print(f"Total Orphaned Dossiers: {mature_df['is_orphan'].sum():,}")
    print(f"Overall Orphan Rate: {mature_df['is_orphan'].mean()*100:.1f}%")
    
    # 2. Article Disparity
    print("\nOrphan Rate by Article:")
    print(mature_df.groupby('article')['is_orphan'].mean() * 100)
    
    # 3. Temporal Analysis (By Year/Month)
    mature_df['reg_month'] = mature_df['reg_date'].dt.month
    mature_df['reg_year'] = mature_df['reg_date'].dt.year
    
    orphan_trend = mature_df.groupby(['reg_year', 'reg_month'])['is_orphan'].mean().unstack()
    
    os.makedirs('reports/charts/orphans', exist_ok=True)
    plt.figure(figsize=(12, 8))
    sns.heatmap(orphan_trend, annot=True, fmt=".1%", cmap="YlOrRd")
    plt.title("Orphan Rate Heatmap (Pre-2020 Cohorts)\n% of dossiers still pending after 6+ years")
    plt.savefig('reports/charts/orphans/orphan_rate_heatmap.png')
    
    # 4. Sequence Analysis
    def get_seq(s):
        try: return int(str(s).split('/')[0])
        except: return 0
    mature_df['dossier_seq'] = mature_df['NR. DOSAR'].apply(get_seq)
    
    # Binning sequence positions
    mature_df['seq_bucket'] = pd.qcut(mature_df['dossier_seq'], 10, labels=False, duplicates='drop')
    
    plt.figure(figsize=(10, 6))
    sns.barplot(data=mature_df, x='seq_bucket', y='is_orphan', hue='article', palette='viridis')
    plt.title("Probability of being 'Orphaned' by Sequence Position")
    plt.xlabel("Dossier Sequence Decile (0=Early Year, 9=Late Year)")
    plt.ylabel("Orphan Probability")
    plt.savefig('reports/charts/orphans/sequence_trap_analysis.png')
    
    # 5. Narrative Identification
    # Finding the 'Trap Months'
    monthly_rates = mature_df.groupby(['reg_year', 'reg_month'])['is_orphan'].agg(['mean', 'count'])
    traps = monthly_rates[monthly_rates['mean'] > 0.15].sort_values(by='mean', ascending=False)
    
    print("\nTop 'Institutional Traps' (Months with >15% Orphan Rate):")
    print(traps.head(10))
    
    return mature_df

if __name__ == "__main__":
    analyze_orphans()
