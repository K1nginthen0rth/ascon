"""
Pipeline de classificadores clássicos para LWC ciphertext-only.

Modelos:
  - Dummy (estratégia 'stratified') — baseline de chance
  - Random Forest (sklearn)
  - SVM (RBF)
  - XGBoost

Fluxo (executado dentro do split key-holdout):
  1. Carrega features + split
  2. Separa X_train, X_val, X_test, y_train, y_val, y_test
  3. fit do LWCFeatureSelector APENAS no X_train
  4. Transform X_train, X_val, X_test
  5. Treina cada modelo e avalia no test
  6. Retorna métricas comparativas

Seeds: modelos=7, seletor=13, bootstrap=42 (convenção do projeto).
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from xgboost import XGBClassifier

from src.eval.metrics import compute_metrics, MetricsReport
from src.features.selector import LWCFeatureSelector, SelectorConfig

# Colunas do parquet que NÃO são features (metadados ou rótulos).
_NON_FEATURE_COLS = {
    "sample_id", "algorithm", "key_id", "nonce_id",
    "len_pt", "len_ad", "len_ct", "split",
    "mode", "impl", "plaintext_source", "seed", "version", "timestamp",
    "ciphertext",
}


@dataclass
class ModelResult:
    """Resultado consolidado de um único modelo."""
    name:           str
    metrics:        MetricsReport
    train_time_s:   float
    predict_time_s: float
    y_pred:         np.ndarray
    y_proba:        Optional[np.ndarray] = None


@dataclass
class PipelineResult:
    """Resultado completo do pipeline (todos os modelos)."""
    selected_features: list[str]
    stage_report:      dict
    label_map:         dict[str, int]
    splits:            dict[str, int]  # {"train": n, "val": n, "test": n}
    models:            dict[str, ModelResult] = field(default_factory=dict)


def _label_encode(y: pd.Series, classes: Optional[list] = None) -> tuple[np.ndarray, dict]:
    """Encode rótulos string -> int (0, 1, ...). Retorna (y_int, label_map)."""
    if classes is None:
        classes = sorted(y.unique().tolist())
    label_map = {c: i for i, c in enumerate(classes)}
    return y.map(label_map).to_numpy(), label_map


def _get_feature_columns(df: pd.DataFrame) -> list[str]:
    """Retorna colunas numéricas que NÃO sejam metadados/rótulo."""
    return [c for c in df.columns if c not in _NON_FEATURE_COLS]


def _verify_no_leakage(feature_cols: list[str]) -> None:
    """Garante que len_pt, len_ct, len_ad NÃO estão na lista de features."""
    forbidden = {"len_pt", "len_ad", "len_ct"}
    leak = forbidden.intersection(feature_cols)
    if leak:
        raise ValueError(
            f"Colunas proibidas presentes em features: {leak}. "
            "len_pt/len_ad/len_ct são metadados, nao features."
        )


def _fit_one_model(name, model, X_train, y_train, X_test, y_test, n_bootstrap, seed) -> ModelResult:
    t0 = time.perf_counter()
    model.fit(X_train, y_train)
    train_time = time.perf_counter() - t0

    t1 = time.perf_counter()
    y_pred = model.predict(X_test)
    predict_time = time.perf_counter() - t1

    y_proba = None
    if hasattr(model, "predict_proba"):
        try:
            y_proba = model.predict_proba(X_test)
        except Exception:
            y_proba = None

    rep = compute_metrics(
        y_test, y_pred, y_proba=y_proba,
        n_bootstrap=n_bootstrap, seed=seed,
    )
    return ModelResult(
        name=name, metrics=rep,
        train_time_s=train_time, predict_time_s=predict_time,
        y_pred=y_pred, y_proba=y_proba,
    )


class ClassicalPipeline:
    """
    Orquestra o experimento clássico Caminho A.

    Args:
        n_bootstrap: número de reamostragens para IC.
        selector_config: configuração do LWCFeatureSelector.
        seed_models: seed para Dummy/RF/SVM/XGBoost (default 7).
        seed_bootstrap: seed para o bootstrap das métricas (default 42).
    """

    def __init__(
        self,
        n_bootstrap:     int  = 1000,
        selector_config: Optional[SelectorConfig] = None,
        seed_models:     int  = 7,
        seed_bootstrap:  int  = 42,
        scale_for_svm:   bool = True,
    ) -> None:
        self.n_bootstrap     = n_bootstrap
        self.selector_config = selector_config or SelectorConfig()
        self.seed_models     = seed_models
        self.seed_bootstrap  = seed_bootstrap
        self.scale_for_svm   = scale_for_svm

    # ------------------------------------------------------------------

    def run(
        self,
        features_df: pd.DataFrame,
        verbose: bool = True,
    ) -> PipelineResult:
        """
        Executa o pipeline completo.

        Espera coluna 'split' com valores em {'train','val','test'} e coluna
        'algorithm' como rótulo.

        Args:
            features_df: DataFrame com features + colunas de metadados.
        """
        if "split" not in features_df.columns:
            raise ValueError(
                "features_df precisa da coluna 'split'. "
                "Faça merge com o parquet original via key_id ou sample_id."
            )

        feat_cols = _get_feature_columns(features_df)
        _verify_no_leakage(feat_cols)

        train_df = features_df[features_df["split"] == "train"]
        val_df   = features_df[features_df["split"] == "val"]
        test_df  = features_df[features_df["split"] == "test"]
        if len(train_df) == 0 or len(test_df) == 0:
            raise ValueError("Splits vazios — verifique a coluna 'split'.")

        # Confirmar key-holdout: nenhuma chave compartilhada
        if "key_id" in features_df.columns:
            kt = set(train_df["key_id"].unique())
            kv = set(val_df["key_id"].unique())
            ke = set(test_df["key_id"].unique())
            if kt & ke or kt & kv or kv & ke:
                raise ValueError(
                    f"VAZAMENTO de chave entre splits! "
                    f"train∩test={kt & ke}, train∩val={kt & kv}, val∩test={kv & ke}"
                )

        X_train = np.asarray(train_df[feat_cols].to_numpy(), dtype=np.float64).copy()
        X_val   = np.asarray(val_df  [feat_cols].to_numpy(), dtype=np.float64).copy()
        X_test  = np.asarray(test_df [feat_cols].to_numpy(), dtype=np.float64).copy()

        classes = sorted(features_df["algorithm"].unique().tolist())
        y_train, label_map = _label_encode(train_df["algorithm"], classes=classes)
        y_val,  _          = _label_encode(val_df  ["algorithm"], classes=classes)
        y_test, _          = _label_encode(test_df ["algorithm"], classes=classes)

        # NaN imputation: 0 (para autocorr_lag_16 com CTs muito curtos)
        for arr in (X_train, X_val, X_test):
            np.nan_to_num(arr, copy=False, nan=0.0)

        if verbose:
            print(f"  Train: {X_train.shape}, Val: {X_val.shape}, Test: {X_test.shape}")
            print(f"  Classes: {label_map}")

        # ---------- Feature Selection (fit APENAS no train) ----------
        if verbose: print("  [1/2] Ajustando seletor (3 estágios)...")
        sel = LWCFeatureSelector(self.selector_config)
        t0  = time.perf_counter()
        sel.fit(X_train, y_train, feature_names=feat_cols)
        sel_time = time.perf_counter() - t0
        X_train_sel = sel.transform(X_train)
        X_val_sel   = sel.transform(X_val)
        X_test_sel  = sel.transform(X_test)
        selected = sel.get_selected_names()
        report = sel.get_stage_report()
        report["selector_fit_time_s"] = round(sel_time, 2)
        if verbose:
            print(f"     Selected {len(selected)}/{len(feat_cols)} features  "
                  f"(VT->{report['stage1_after_variance']}, MI->{report['stage1_output']}, "
                  f"mRMR->{report['stage2_output']}, Boruta->{report['stage3_output']})")

        # ---------- Modelos ----------
        if verbose: print("  [2/2] Treinando modelos...")
        models = self._build_models()
        results: dict[str, ModelResult] = {}

        # SVM precisa de scaling: ajustar StandardScaler APENAS no train
        scaler = StandardScaler().fit(X_train_sel)
        X_train_svm = scaler.transform(X_train_sel)
        X_test_svm  = scaler.transform(X_test_sel)

        for name, mdl in models.items():
            X_tr = X_train_svm if name == "SVM" else X_train_sel
            X_te = X_test_svm  if name == "SVM" else X_test_sel
            res  = _fit_one_model(
                name, mdl, X_tr, y_train, X_te, y_test,
                n_bootstrap=self.n_bootstrap, seed=self.seed_bootstrap,
            )
            results[name] = res
            if verbose:
                ci = res.metrics.f1_macro_ci
                print(f"     {name:10s} F1={res.metrics.f1_macro:.4f}  "
                      f"CI=[{ci[0]:.3f},{ci[1]:.3f}]  "
                      f"train={res.train_time_s:.1f}s")

        return PipelineResult(
            selected_features=selected,
            stage_report=report,
            label_map=label_map,
            splits={
                "train": int(len(X_train)),
                "val":   int(len(X_val)),
                "test":  int(len(X_test)),
            },
            models=results,
        )

    # ------------------------------------------------------------------

    def _build_models(self) -> dict:
        s = self.seed_models
        return {
            "Dummy": DummyClassifier(strategy="stratified", random_state=s),
            "RF": RandomForestClassifier(
                n_estimators=500, max_depth=None,
                class_weight="balanced", random_state=s, n_jobs=-1,
            ),
            "SVM": SVC(
                kernel="rbf", C=1.0, gamma="scale",
                class_weight="balanced", random_state=s,
                probability=True,
            ),
            "XGBoost": XGBClassifier(
                n_estimators=500, max_depth=6, learning_rate=0.1,
                random_state=s, n_jobs=-1, eval_metric="logloss",
                tree_method="hist",
            ),
        }
