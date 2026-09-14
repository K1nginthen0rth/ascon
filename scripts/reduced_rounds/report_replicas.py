"""Roda o Stacking próprio + as 3 réplicas da literatura (HKNNRF, XGB-LGBM
sobre peso de Hamming, Transformer E20) nos datasets de rodadas reduzidas
(amostra única, ciphertext-only), reusando `run_literature_replicas` da
produção — não reimplementa nada, chama a mesma função que o Caminho A
oficial usa, com o mesmo `report_eval` (bootstrap por chave, JSON, PNG).

Por que isso ainda falta. `report_stats.py` cobre RF/LinearSVC/XGBoost/LR/
SVM-RBF (os 5 modelos "base" do Caminho A). Os 4 modelos compostos ficaram
de fora porque exigem estado extra (`groups` para o CV interno do Stacking/
HKNNRF, subconjuntos de coluna diferentes para XGB-LGBM e E20) que os 5
base não precisam.

Mesmo split (seed, N_TEST_KEYS, N_CV_FOLDS) de `report_stats.py`, para os
números ficarem diretamente comparáveis.

Saída: `reports/reduced_rounds_replicas/<config>/` — mesmo formato de
`reports/v2/caminho_a/` (metrics jsonl, confusion matrices, predictions).

Uso:
    python scripts/reduced_rounds/report_replicas.py --features build/.../features_init_fraca.parquet
    python scripts/reduced_rounds/report_replicas.py --all
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.model_selection import GroupKFold  # noqa: E402

from scripts.reduced_rounds.report_stats import META_COLS, N_CV_FOLDS, N_TEST_KEYS, SEED, _split  # noqa: E402
from scripts.run_v2_caminho_a import REPLICA_MODEL_NAMES, run_literature_replicas  # noqa: E402

OUT_DIR = REPO_ROOT / "reports" / "reduced_rounds_replicas"


def _log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def run_for_features(features_path: Path, config_name: str | None = None) -> None:
    features_path = Path(features_path)
    name = config_name or features_path.stem.replace("features_", "")
    out_dir = OUT_DIR / name
    t0 = time.time()
    _log(f"===== [{name}] {features_path.name} =====")

    df = pd.read_parquet(features_path)
    fcols = [c for c in df.columns if c not in META_COLS]
    classes = sorted(df["algorithm"].unique().tolist())
    code = {lab: i for i, lab in enumerate(classes)}

    trainval, test = _split(df)
    _log(f"  {len(df)} amostras, {len(fcols)} features, classes={classes}, "
         f"{trainval['key_id'].nunique()} chaves treino / {test['key_id'].nunique()} teste")

    X_trainval = np.nan_to_num(trainval[fcols].to_numpy(np.float64), nan=0.0)
    y_trainval = trainval["algorithm"].map(code).to_numpy()
    g_trainval = trainval["key_id"].to_numpy()
    X_test = np.nan_to_num(test[fcols].to_numpy(np.float64), nan=0.0)
    y_test = test["algorithm"].map(code).to_numpy()

    for fold_i, (tr_idx, va_idx) in enumerate(
        GroupKFold(n_splits=N_CV_FOLDS).split(X_trainval, y_trainval, g_trainval)
    ):
        tr_df, va_df = trainval.iloc[tr_idx], trainval.iloc[va_idx]
        run_literature_replicas(
            tr=tr_df, va=va_df, y_tr=y_trainval[tr_idx], y_va=y_trainval[va_idx],
            X_tr=X_trainval[tr_idx], X_va=X_trainval[va_idx],
            run_id=f"reduced_rounds_{name}", braco="ciphertext_only", fold_tag=fold_i,
            classes=classes, out_dir=out_dir, n_bootstrap=1000, seed=SEED,
            models_subset=REPLICA_MODEL_NAMES,
        )
        _log(f"  fold {fold_i} concluído")

    run_literature_replicas(
        tr=trainval, va=test, y_tr=y_trainval, y_va=y_test,
        X_tr=X_trainval, X_va=X_test,
        run_id=f"reduced_rounds_{name}", braco="ciphertext_only", fold_tag="final",
        classes=classes, out_dir=out_dir, n_bootstrap=1000, seed=SEED,
        models_subset=REPLICA_MODEL_NAMES,
    )
    _log(f"  FINAL concluído. Salvo em {out_dir} ({(time.time() - t0) / 60:.1f} min)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--features", nargs="+", default=None)
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()

    if args.all or not args.features:
        base = REPO_ROOT / "build" / "reduced_rounds"
        targets = sorted(base.glob("full/features_*.parquet"))
    else:
        targets = [Path(p) for p in args.features]

    _log(f"Alvos: {[p.name for p in targets]}")
    for p in targets:
        run_for_features(p)
    _log("Concluído.")
