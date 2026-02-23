import pandas as pd
import numpy as np
import os
import hashlib

def get_deterministic_seed(dossier_id):
    """Generate a deterministic seed from the dossier ID string."""
    return int(hashlib.md5(dossier_id.encode()).hexdigest(), 16) % (2**32)

def load_distribution(csv_path):
    dist_df = pd.read_csv(csv_path)
    # The debug script saved it as 'month', 'day', '0' (size)
    # Let's adjust based on how it was saved
    # Column 0: month, Column 1: day, Column 2: probability
    return dist_df

def reimpute_csv(csv_path, dist_path, label):
    print(f"Applying probabilistic imputation to {csv_path}...")
    df = pd.read_csv(csv_path)
    dist_df = load_distribution(dist_path)
    
    # Standardize distribution columns
    dist_df.columns = ['month', 'day', 'prob']
    
    # Identify previously imputed dates (01.07.YYYY)
    df['is_imputed'] = df['SOLUȚIE'].str.startswith('01.07.') == True
    
    imputed_count = 0
    
    # For each imputed row, pick a new month/day from the distribution
    # seeded by the dossier number for reproducibility
    choices = dist_df[['month', 'day']].values
    probs = dist_df['prob'].values
    # Normalize probs just in case of rounding errors
    probs = probs / probs.sum()
    
    indices = np.arange(len(choices))
    
    def pick_date(row):
        nonlocal imputed_count
        if row['is_imputed']:
            year = row['SOLUȚIE'].split('.')[-1]
            seed = get_deterministic_seed(str(row['NR. DOSAR']))
            rng = np.random.default_rng(seed)
            idx = rng.choice(indices, p=probs)
            month, day = choices[idx]
            imputed_count += 1
            return f"{int(day):02d}.{int(month):02d}.{year}"
        return row['SOLUȚIE']

    df['SOLUȚIE'] = df.apply(pick_date, axis=1)
    df.drop(columns=['is_imputed'], inplace=True)
    
    df.to_csv(csv_path, index=False)
    print(f"  Successfully re-imputed {imputed_count:,} dates in {csv_path}")

if __name__ == "__main__":
    reimpute_csv('data/processed/dosare_art10.csv', 'data/processed/dist_art10.csv', 'art10')
    reimpute_csv('data/processed/dosare_art11.csv', 'data/processed/dist_art11.csv', 'art11')
