import pandas as pd
import numpy as np
import os
import hashlib
from datetime import datetime

class ProbabilisticImputer:
    def __init__(self, dist_csv_path):
        if not os.path.exists(dist_csv_path):
            self.choices = None
            self.probs = None
            return
            
        dist_df = pd.read_csv(dist_csv_path)
        dist_df.columns = ['month', 'day', 'prob']
        self.choices = dist_df[['month', 'day']].values
        self.probs = dist_df['prob'].values
        self.probs = self.probs / self.probs.sum()
        self.indices = np.arange(len(self.choices))

    def get_deterministic_seed(self, dossier_id):
        return int(hashlib.md5(dossier_id.encode()).hexdigest(), 16) % (2**32)

    def get_random_date(self, year, dossier_id):
        if self.choices is None:
            return f"01.07.{year}"
            
        seed = self.get_deterministic_seed(str(dossier_id))
        rng = np.random.default_rng(seed)
        idx = rng.choice(self.indices, p=self.probs)
        month, day = self.choices[idx]
        return f"{int(day):02d}.{int(month):02d}.{year}"
