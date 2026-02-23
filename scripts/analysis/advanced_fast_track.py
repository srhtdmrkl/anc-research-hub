import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
import os
import hashlib

def get_deterministic_seed(dossier_id):
    return int(hashlib.md5(dossier_id.encode()).hexdigest(), 16) % (2**32)

def engineer_features():
    print("Loading data for feature engineering...")
    df10 = pd.read_csv('data/processed/dosare_art10.csv')
    df11 = pd.read_csv('data/processed/dosare_art11.csv')
    
    df10['article'] = '10'
    df11['article'] = '11'
    df = pd.concat([df10, df11], ignore_index=True)
    
    df['reg_date'] = pd.to_datetime(df['DATA ÎNREGISTRĂRII'], format='%d.%m.%Y', errors='coerce')
    df['sol_date'] = pd.to_datetime(df['SOLUȚIE'], format='%d.%m.%Y', errors='coerce')
    
    # Drop rows with invalid registration dates
    df = df[df['reg_date'].notna()].copy()
    
    # 1. Create a daily timeline for state variables
    print("Constructing daily institutional timeline...")
    min_date = df['reg_date'].min()
    max_date = pd.to_datetime('today')
    date_range = pd.date_range(start=min_date, end=max_date)
    
    daily = pd.DataFrame(index=date_range)
    daily['intake'] = df.groupby('reg_date').size()
    daily['output'] = df.groupby('sol_date').size()
    daily.fillna(0, inplace=True)
    
    # Daily Backlog (cumulative)
    daily['backlog'] = (daily['intake'] - daily['output']).cumsum()
    
    # 90-day Rolling Throughput
    daily['throughput_90d'] = daily['output'].rolling(window=90).mean()
    daily['intake_velocity_30d'] = daily['intake'].rolling(window=30).mean()
    
    # 2. Institutional State Metrics
    # Map back to dossier dataframe
    print("Mapping state variables to dossiers...")
    df['backlog_at_reg'] = df['reg_date'].map(daily['backlog'])
    df['throughput_at_reg'] = df['reg_date'].map(daily['throughput_90d'])
    df['intake_velocity_at_reg'] = df['reg_date'].map(daily['intake_velocity_30d'])
    
    # Derived Feature: Estimated Queue Wait at time of registration
    # Units: Days (Backlog / daily throughput)
    df['queue_wait_est_at_reg'] = df['backlog_at_reg'] / (df['throughput_at_reg'] + 1)
    
    # 3. Temporal & Seasonal Engineering
    print("Engineering temporal features...")
    df['reg_month'] = df['reg_date'].dt.month
    df['reg_year'] = df['reg_date'].dt.year
    
    # Days to year end (captures the "throttle" effect observed in Art 11)
    df['days_to_year_end'] = (pd.to_datetime(df['reg_year'].astype(str) + '-12-31') - df['reg_date']).dt.days
    
    # 4. Relative Position Feature
    year_intake = df.groupby(df['reg_date'].dt.year).size()
    def get_seq(s):
        try: return int(s.split('/')[0])
        except: return 0
    df['dossier_seq'] = df['NR. DOSAR'].apply(get_seq)
    df['relative_queue_pos'] = df.apply(lambda x: x['dossier_seq'] / year_intake.get(x['reg_date'].year, 1), axis=1)
    
    # 5. Target Variable
    df['wait_days'] = (df['sol_date'] - df['reg_date']).dt.days
    # Filter to resolved dossiers only for training
    train_df = df[df['wait_days'].notna() & (df['wait_days'] >= 0)].copy()
    
    threshold = train_df['wait_days'].quantile(0.15)
    print(f"Defining 'Fast-Track' as wait_days < {threshold:.0f} days")
    train_df['is_fast'] = (train_df['wait_days'] < threshold).astype(int)
    
    # Additional temporal features
    train_df['reg_month'] = train_df['reg_date'].dt.month
    train_df['reg_year'] = train_df['reg_date'].dt.year
    
    features = [
        'backlog_at_reg', 'throughput_at_reg', 'intake_velocity_at_reg',
        'queue_wait_est_at_reg', 'relative_queue_pos', 
        'reg_month', 'reg_year', 'days_to_year_end', 'article'
    ]
    
    X = pd.get_dummies(train_df[features], columns=['article'])
    y = train_df['is_fast']
    
    # Standardize/Fill NaNs for state vars
    X.fillna(0, inplace=True)
    
    return X, y, train_df

def train_and_visualize(X, y):
    print("\nTraining Advanced Random Forest Model...")
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    
    model = RandomForestClassifier(n_estimators=200, max_depth=15, random_state=42, n_jobs=-1)
    model.fit(X_train, y_train)
    
    print("\nModel Performance:")
    print(classification_report(y_test, model.predict(X_test)))
    
    importances = pd.Series(model.feature_importances_, index=X.columns).sort_values(ascending=False)
    print("\nFeature Impact Analysis:")
    print(importances)
    
    # Define descriptive labels for the chart
    label_map = {
        'reg_year': 'Registration Year (Cohort)',
        'queue_wait_est_at_reg': 'Estimated Queue Wait',
        'relative_queue_pos': 'Relative Queue Position',
        'backlog_at_reg': 'Institutional Backlog',
        'throughput_at_reg': '90d Rolling Throughput',
        'days_to_year_end': 'Days to Year End',
        'intake_velocity_at_reg': '30d Intake Velocity',
        'reg_month': 'Registration Month',
        'article_10': 'Article 10 (Restoration)',
        'article_11': 'Article 11 (Re-acquisition)'
    }
    
    # Apply labels to the importances Series
    labeled_importances = importances.rename(index=label_map)
    
    os.makedirs('reports/charts/fast_track', exist_ok=True)
    plt.figure(figsize=(10, 8))
    sns.barplot(x=labeled_importances.values, y=labeled_importances.index, hue=labeled_importances.index, palette='magma', legend=False)
    plt.title('Impact of Institutional State vs. Cohort on Resolution Speed')
    plt.xlabel('Relative Importance (GINI Score)')
    plt.ylabel('Analytical Predictors')
    plt.tight_layout()
    plt.savefig('reports/charts/fast_track/feature_importance.png')
    
    # Also save a version with the new features highlighted
    plt.title('Advanced Fast-Track Predictors (Refined Model)')
    plt.savefig('reports/charts/fast_track/advanced_feature_importance.png')
    
    return model

if __name__ == "__main__":
    X, y, df = engineer_features()
    model = train_and_visualize(X, y)
    
    # Calculate SHAP-like breakdown for a few cases
    print("\nSample Insights:")
    avg_backlog_fast = df[df['is_fast'] == 1]['backlog_at_reg'].mean()
    avg_backlog_slow = df[df['is_fast'] == 0]['backlog_at_reg'].mean()
    print(f"Average Backlog at registration for Fast dossiers: {avg_backlog_fast:,.0f}")
    print(f"Average Backlog at registration for Slow dossiers: {avg_backlog_slow:,.0f}")
    
    print(f"\nAverage Throughput (90d) for Fast dossiers: {df[df['is_fast'] == 1]['throughput_at_reg'].mean():.1f}")
    print(f"Average Throughput (90d) for Slow dossiers: {df[df['is_fast'] == 0]['throughput_at_reg'].mean():.1f}")
