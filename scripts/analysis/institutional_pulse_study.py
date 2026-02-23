import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import os

def analyze_institutional_pulse():
    print("Loading data for institutional pulse analysis...")
    df10 = pd.read_csv('data/processed/dosare_art10.csv')
    df11 = pd.read_csv('data/processed/dosare_art11.csv')
    
    df10['article'] = '10'
    df11['article'] = '11'
    df = pd.concat([df10, df11], ignore_index=True)
    
    # 0. Ground Truth Filter (CRITICAL)
    # Based on Article 10/11 reports, ground truth (exact dates) is:
    # - Article 10: 2010 - 2016
    # - Article 11: 2012 - 2014
    
    # We filter for these years to ensure we analyze ACTUAL institutional rhythms, 
    # not the imputation algorithm's distribution.
    
    # First, parse year from the original string if possible, or use sol_date year
    df['sol_date'] = pd.to_datetime(df['SOLUȚIE'], format='%d.%m.%Y', errors='coerce')
    df['sol_year'] = df['sol_date'].dt.year
    
    mask_10 = (df['article'] == '10') & (df['sol_year'] <= 2016)
    mask_11 = (df['article'] == '11') & (df['sol_year'] <= 2014)
    
    resolved_df = df[mask_10 | mask_11].copy()
    print(f"Total Ground-Truth Resolved Dossiers (Art 10 <= 2016, Art 11 <= 2014): {len(resolved_df):,}")
    
    if len(resolved_df) == 0:
        print("ERROR: No ground truth data found within specified ranges.")
        return None
    
    # 1. Day of the Week Analysis
    resolved_df['day_of_week'] = resolved_df['sol_date'].dt.day_name()
    day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    
    day_dist = resolved_df.groupby('day_of_week').size().reindex(day_order)
    
    os.makedirs('reports/charts/pulse', exist_ok=True)
    plt.figure(figsize=(10, 6))
    sns.barplot(x=day_dist.index, y=day_dist.values, hue=day_dist.index, palette='viridis', legend=False)
    plt.title("Signature Intensity by Day of Week")
    plt.ylabel("Number of Orders Signed")
    plt.savefig('reports/charts/pulse/day_of_week_pulse.png')
    
    # 2. Quarterly Target Analysis
    resolved_df['month'] = resolved_df['sol_date'].dt.month
    resolved_df['day'] = resolved_df['sol_date'].dt.day
    resolved_df['is_q_end'] = resolved_df['month'].isin([3, 6, 9, 12]) & (resolved_df['day'] >= 21)
    
    q_end_rate = resolved_df.groupby(['month', 'is_q_end']).size().unstack()
    print("\nResolution Volume: Quarter-End (Last 10 days) vs. Baseline:")
    print(q_end_rate)
    
    # 3. Batching Effect (Daily Volatility)
    daily_vol = resolved_df.groupby('sol_date').size()
    mean_vol = daily_vol.mean()
    std_vol = daily_vol.std()
    
    massive_days = daily_vol[daily_vol > (mean_vol + 3*std_vol)]
    print(f"\nMean Daily Resolutions: {mean_vol:.1f}")
    print(f"Days with 'Massive' Output (>3 Sigma): {len(massive_days)}")
    print("Top 5 Batching Events:")
    print(massive_days.sort_values(ascending=False).head(5))
    
    # 4. Seasonal Heatmap of Output
    resolved_df['year'] = resolved_df['sol_date'].dt.year
    output_heatmap = resolved_df.pivot_table(index='year', columns='month', values='NR. DOSAR', aggfunc='count')
    
    plt.figure(figsize=(12, 8))
    sns.heatmap(output_heatmap, cmap="YlGnBu", annot=False)
    plt.title("Institutional Output Heatmap (Resolutions per Month)")
    plt.savefig('reports/charts/pulse/output_heatmap.png')
    
    # 5. Article Alignment
    # Do Art 10 and Art 11 peak together?
    art_pulse = resolved_df.groupby(['sol_date', 'article']).size().unstack().fillna(0)
    correlation = art_pulse['10'].corr(art_pulse['11'])
    print(f"\nCorrelation between Art 10 and Art 11 signature days: {correlation:.3f}")
    
    return resolved_df

if __name__ == "__main__":
    analyze_institutional_pulse()
