import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import f1_score, accuracy_score
import os

def run_stress_test():
    print("Loading data for Leadership Stress Test...")
    # Using the engineered features from advanced_fast_track logic (roughly)
    df10 = pd.read_csv('data/processed/dosare_art10.csv')
    df11 = pd.read_csv('data/processed/dosare_art11.csv')
    df10['article'] = '10'
    df11['article'] = '11'
    df = pd.concat([df10, df11], ignore_index=True)
    
    df['reg_date'] = pd.to_datetime(df['DATA ÎNREGISTRĂRII'], format='%d.%m.%Y', errors='coerce')
    df['sol_date'] = pd.to_datetime(df['SOLUȚIE'], format='%d.%m.%Y', errors='coerce')
    df['wait_days'] = (df['sol_date'] - df['reg_date']).dt.days
    
    # Using the 377 day threshold found earlier
    df['is_fast'] = (df['wait_days'] < 377).astype(int)
    
    # Era Definitions
    def get_era(year):
        if 2012 <= year <= 2015: return 'Era 1 (2012-15)'
        if 2016 <= year <= 2019: return 'Era 2 (2016-19)'
        if 2020 <= year <= 2022: return 'Era 3 (2020-22)'
        if year >= 2023: return 'Era 4 (2023+)'
        return 'Other'

    df['era'] = df['reg_date'].dt.year.apply(get_era)
    df = df[df['era'] != 'Other'].copy()
    
    # Basic features for simplicity in era-based testing
    def get_seq(s):
        try: return int(str(s).split('/')[0])
        except: return 0
    df['dossier_seq'] = df['NR. DOSAR'].apply(get_seq)
    df['reg_month'] = df['reg_date'].dt.month
    
    features = ['reg_month', 'dossier_seq']
    X = pd.get_dummies(df[features + ['article', 'era']], columns=['article', 'era'])
    y = df['is_fast']
    
    # Perform Stress Test
    results = []
    eras = df['era'].unique()
    
    for era in eras:
        era_mask = df['era'] == era
        X_era = X[X[f'era_{era}'] == 1]
        y_era = y[era_mask]
        
        # We need cases where we actually have a target
        valid_indices = y_era.notna() & (df.loc[era_mask, 'wait_days'] >= 0)
        X_era = X_era[valid_indices]
        y_era = y_era[valid_indices]
        
        if len(y_era) < 100: continue
        
        X_train, X_test, y_train, y_test = train_test_split(X_era, y_era, test_size=0.2, random_state=42)
        
        model = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42)
        model.fit(X_train, y_train)
        
        y_pred = model.predict(X_test)
        f1 = f1_score(y_test, y_pred)
        acc = accuracy_score(y_test, y_pred)
        
        # Measure institutional volatility (Std of wait days)
        volatility = df.loc[era_mask & valid_indices, 'wait_days'].std()
        
        results.append({
            'Era': era,
            'Predictability (F1)': f1,
            'Accuracy': acc,
            'Queue Volatility (Std)': volatility,
            'Sample Size': len(y_era)
        })

    results_df = pd.DataFrame(results).sort_values(by='Era')
    print("\nLeadership Predictability Rankings:")
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 1000)
    print(results_df)

    os.makedirs('reports/charts/leadership', exist_ok=True)
    plt.figure(figsize=(10, 6))
    sns.barplot(data=results_df, x='Era', y='Predictability (F1)', hue='Era', palette='rocket')
    plt.title("Leadership Predictability Score (High = Consistent Rules)")
    plt.ylim(0, 1)
    plt.savefig('reports/charts/leadership/era_predictability.png')
    
    return results_df

if __name__ == "__main__":
    run_stress_test()
