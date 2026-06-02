from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.feature_selection import mutual_info_classif

__all__ = ["mrmr_classif"]


def mrmr_classif(X: pd.DataFrame, y: pd.Series, K: int, show_progress: bool = False) -> list[str]:
    """Approximate mRMR using mutual information and greedy redundancy penalty."""
    if K <= 0:
        return []
    X = X.copy()
    y = y.copy()
    features = list(X.columns)
    mi = mutual_info_classif(X, y, discrete_features='auto', random_state=0)
    relevance = dict(zip(features, mi))
    selected: list[str] = []
    remaining = set(features)

    def redundancy_score(feature_name: str, selected_names: list[str]) -> float:
        if not selected_names:
            return 0.0
        x = X[feature_name].to_numpy(dtype=np.float64)
        scores = []
        for other in selected_names:
            yv = X[other].to_numpy(dtype=np.float64)
            corr = np.corrcoef(x, yv)[0, 1]
            if np.isnan(corr):
                corr = 0.0
            scores.append(abs(corr))
        return float(np.mean(scores))

    while remaining and len(selected) < K:
        best_feature = None
        best_score = -np.inf
        for feature in remaining:
            score = relevance[feature]
            if selected:
                score -= redundancy_score(feature, selected)
            if score > best_score:
                best_score = score
                best_feature = feature
        if best_feature is None:
            break
        selected.append(best_feature)
        remaining.remove(best_feature)

    return selected
