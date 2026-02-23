import pandas as pd
import numpy as np
import os
import hashlib
from sklearn.ensemble import RandomForestClassifier

def calculate_prob():
    # 1. Load data and rebuild state timeline (logic from advanced_fast_track)
    df10 = pd.read_csv('data/processed/dosare_art10.csv')
    df11 = pd.read_csv('data/processed/dosare_art11.csv')
    df10['article'] = '10'
    df11['article'] = '11'
    df = pd.concat([df10, df11], ignore_index=True)
    
    df['reg_date'] = pd.to_datetime(df['DATA ÎNREGISTRĂRII'], format='%d.%m.%Y', errors='coerce')
    df['sol_date'] = pd.to_datetime(df['SOLUȚIE'], format='%d.%m.%Y', errors='coerce')
    df = df[df['reg_date'].notna()].copy()
    
    min_date = df['reg_date'].min()
    max_date = pd.to_datetime('today')
    date_range = pd.date_range(start=min_date, end=max_date)
    daily = pd.DataFrame(index=date_range)
    daily['intake'] = df.groupby('reg_date').size()
    daily['output'] = df.groupby('sol_date').size()
    daily.fillna(0, inplace=True)
    daily['backlog'] = (daily['intake'] - daily['output']).cumsum()
    daily['throughput_90d'] = daily['output'].rolling(window=90).mean()
    
    # 2. Extract state for July 1, 2025
    target_date = pd.to_datetime('2025-07-01')
    backlog_july = daily.loc[target_date, 'backlog']
    throughput_july = daily.loc[target_date, 'throughput_90d']
    
    # Estimate relative position (July is ~middle of year)
    # Let's get actual 2025 intake distribution
    intake_2025 = df[df['reg_date'].dt.year == 2025]
    total_2025 = len(intake_2025)
    july_intake_start = len(intake_2025[intake_2025['reg_date'] < target_date])
    rel_pos_july = july_intake_start / total_2025
    
    print(f"Institutional State for {target_date.date()}:")
    print(f"  Backlog: {backlog_july:,.0f}")
    print(f"  Throughput (90d): {throughput_july:.1f}")
    print(f"  Relative Queue Pos: {rel_pos_july:.2f}")

    # 3. Re-train model (simplified) or load features
    df['wait_days'] = (df['sol_date'] - df['reg_date']).dt.days
    train_df = df[df['wait_days'].notna() & (df['wait_days'] >= 0)].copy()
    threshold = train_df['wait_days'].quantile(0.15)
    train_df['is_fast'] = (train_df['wait_days'] < threshold).astype(int)
    
    train_df['backlog_at_reg'] = train_df['reg_date'].map(daily['backlog'])
    train_df['throughput_at_reg'] = train_df['reg_date'].map(daily['throughput_90d'])
    train_df['reg_month'] = train_df['reg_date'].dt.month
    train_df['reg_year'] = train_df['reg_date'].dt.year
    
    year_intake = df.groupby(df['reg_date'].dt.year).size()
    def get_seq(s):
        try: return int(s.split('/')[0])
        except: return 0
    train_df['dossier_seq'] = train_df['NR. DOSAR'].apply(get_seq)
    train_df['rel_pos'] = train_df.apply(lambda x: x['dossier_seq'] / year_intake.get(x['reg_date'].year, 1), axis=1)
    
    features = ['backlog_at_reg', 'throughput_at_reg', 'rel_pos', 'reg_month', 'reg_year', 'article']
    X = pd.get_dummies(train_df[features], columns=['article'])
    y = train_df['is_fast']
    X.fillna(0, inplace=True)
    
    model = RandomForestClassifier(n_estimators=100, max_depth=12, random_state=42)
    model.fit(X, y)
    
    # 4. Predict
    # Create input vector for Art 10
    input_10 = pd.DataFrame([{
        'backlog_at_reg': backlog_july,
        'throughput_at_reg': throughput_july,
        'rel_pos': rel_pos_july,
        'reg_month': 7,
        'reg_year': 2025,
        'article_10': 1,
        'article_11': 0
    }])[X.columns]
    
    # Create input vector for Art 11
    input_11 = pd.DataFrame([{
        'backlog_at_reg': backlog_july,
        'throughput_at_reg': throughput_july,
        'rel_pos': rel_pos_july,
        'reg_month': 7,
        'reg_year': 2025,
        'article_10': 0,
        'article_11': 1
    }])[X.columns]
    
    prob_10 = model.predict_proba(input_10)[0][1]
    prob_11 = model.predict_proba(input_11)[0][1]
    
    print(f"\nPredicted Fast-Track Probability (July 2025):")
    print(f"  Article 10: {prob_10*100:.1f}%")
    print(f"  Article 11: {prob_11*100:.1f}%")

if __name__ == "__main__":
    calculate_prob()
