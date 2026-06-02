"""Verifica versões e sanidade dos pacotes ML necessários para Phase 4B."""
import numpy as np
import sklearn, xgboost, torch, boruta, mrmr

print(f"sklearn  {sklearn.__version__}")
print(f"xgboost  {xgboost.__version__}")
print(f"torch    {torch.__version__}")
boruta_v = getattr(boruta, "__version__", "?")
mrmr_v   = getattr(mrmr,   "__version__", "?")
print(f"boruta   {boruta_v}")
print(f"mrmr     {mrmr_v}")

# Boruta sanity (often breaks on numpy 2.x via np.int)
from sklearn.ensemble import RandomForestClassifier
from boruta import BorutaPy

X = np.random.RandomState(0).randn(50, 10).astype(np.float32)
y = np.random.RandomState(0).randint(0, 2, 50)
try:
    bp = BorutaPy(
        RandomForestClassifier(n_estimators=10, n_jobs=1, random_state=0),
        n_estimators="auto",
        max_iter=5,
        random_state=0,
        verbose=0,
    )
    bp.fit(X, y)
    print(f"boruta sanity OK -- support={bp.support_.sum()}, weak={bp.support_weak_.sum()}")
except Exception as e:
    print(f"boruta sanity FAIL: {type(e).__name__}: {e}")

# mrmr sanity
try:
    import pandas as pd
    from mrmr import mrmr_classif
    X_df = pd.DataFrame(X, columns=[f"f{i}" for i in range(X.shape[1])])
    y_s  = pd.Series(y)
    sel = mrmr_classif(X=X_df, y=y_s, K=3)
    print(f"mrmr sanity OK -- selected={sel}")
except Exception as e:
    print(f"mrmr sanity FAIL: {type(e).__name__}: {e}")
