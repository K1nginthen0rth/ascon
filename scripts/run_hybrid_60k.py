"""
Caminho D — Modelo Híbrido (60k, 64KB CT)

Pipeline:
  1. Features clássicas (307D) — do parquet de features pré-computado
  2. Latent CNN 1D — treinado no fold, pesos congelados para extração
  3. Latent CNN 2D — idem
  4. Concatenação → vetor (307 + 512 + 128) = 947D
  5. MI → mRMR → Boruta (dentro de cada fold)
  6. RF e XGBoost no vetor selecionado

Protocolo: 5-fold GroupKFold CV (key-holdout) + modelo final no test holdout.
Seeds: modelo=7, FS=13, bootstrap=42.

Uso:
    python scripts/run_hybrid_60k.py
    python scripts/run_hybrid_60k.py --skip-cv
"""
from __future__ import annotations

import json
import math
import pickle
import sys
import time
from itertools import combinations
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src" / "crypto"))

import numpy as np
import pandas as pd
import torch
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import balanced_accuracy_score, f1_score
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

from src.eval.metrics import compute_metrics, mcnemar_test
from src.features.selector import LWCFeatureSelector, SelectorConfig
from src.models.hybrid import HybridConfig, HybridExtractor

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

DATASET_ID   = "keyholdout_2class_60k_v1"
DATA_DIR     = REPO_ROOT / "data" / "processed"
RAW_PARQUET  = DATA_DIR / f"{DATASET_ID}.parquet"
FEAT_PARQUET = DATA_DIR / f"{DATASET_ID}_features.parquet"
REPORTS_DIR  = REPO_ROOT / "reports" / f"{DATASET_ID}_hybrid"
CM_DIR       = REPORTS_DIR / "confusion_matrices"

REPORTS_DIR.mkdir(parents=True, exist_ok=True)
CM_DIR.mkdir(parents=True, exist_ok=True)

N_FOLDS        = 5
N_BOOTSTRAP    = 1000
SEED_BOOTSTRAP = 42
SEED_MODELS    = 7

# Caminho B usa prefixo por viabilidade computacional em CPU.
# Caminho D usa CT completo para simetria com CNN2D e features clássicas.
# Assimetria INTENCIONAL — documentada na dissertação (Seção Metodologia).
MAX_LEN_B       = 4096    # CNN1D Caminho B — prefixo; viável em CPU
MAX_LEN_D_CNN1D = 65552   # CNN1D Caminho D — CT completo; requer GPU

try:
    import mlflow as _mlflow_mod
    _MLFLOW = True
except ImportError:
    _MLFLOW = False

CNN_CFG = HybridConfig(
    max_len_1d   = MAX_LEN_D_CNN1D if torch.cuda.is_available() else MAX_LEN_B,
    n_classes    = 2,
    n_filters_1d = 128,
    n_conv_1d    = 3,
    lr           = 1e-3,
    n_epochs     = 30,
    patience     = 5,
    seed_model   = SEED_MODELS,
)

# Feature selection: top_k_mi aumentado para cobrir os ~947D do vetor combinado
SELECTOR_CFG = SelectorConfig(
    variance_threshold = 1e-5,
    top_k_mi           = 300,
    n_features_mrmr    = 150,
    boruta_max_iter    = 100,
    random_state       = 13,
)

_NON_FEATURE_COLS = {
    "sample_id", "algorithm", "key_id", "nonce_id",
    "len_pt", "len_ad", "len_ct", "split", "split_orig",
    "mode", "impl", "plaintext_source", "seed", "version",
    "timestamp", "ciphertext",
}


# ---------------------------------------------------------------------------
# Funções auxiliares
# ---------------------------------------------------------------------------

def _feature_cols(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns
            if c not in _NON_FEATURE_COLS and df[c].dtype.kind in ("f", "i", "u")]


def _label_encode(series: pd.Series, classes: list[str]) -> np.ndarray:
    return series.map({c: i for i, c in enumerate(classes)}).to_numpy()


def _build_classifiers() -> dict:
    s = SEED_MODELS
    return {
        "RF": RandomForestClassifier(
            n_estimators=500, max_depth=None,
            class_weight="balanced", random_state=s, n_jobs=-1,
        ),
        "XGBoost": XGBClassifier(
            n_estimators=500, max_depth=6, learning_rate=0.1,
            random_state=s, n_jobs=-1, eval_metric="logloss",
            tree_method="hist",
        ),
    }


def _get_proba(model, X: np.ndarray) -> np.ndarray | None:
    if hasattr(model, "predict_proba"):
        try:
            return model.predict_proba(X)
        except Exception:
            pass
    return None


def _jaccard(a: list, b: list) -> float:
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 1.0
    return len(sa & sb) / len(sa | sb)


def _md_table(rows: list[list[str]], headers: list[str]) -> str:
    widths = [max(len(h), max((len(str(r[i])) for r in rows), default=0))
              for i, h in enumerate(headers)]
    sep  = "| " + " | ".join("-" * w for w in widths) + " |"
    hrow = "| " + " | ".join(h.ljust(w) for h, w in zip(headers, widths)) + " |"
    lines = [hrow, sep]
    for r in rows:
        lines.append("| " + " | ".join(str(c).ljust(w) for c, w in zip(r, widths)) + " |")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Carregamento e preparação dos dados
# ---------------------------------------------------------------------------

def load_data() -> tuple[pd.DataFrame, pd.DataFrame, list[str], dict[str, int]]:
    """
    Carrega e mescla features (307D) com raw CT bytes.
    Aplica mapeamento 80/20: train+val → trainval, test → test.
    """
    print(f"  Carregando features: {FEAT_PARQUET.name}")
    feat_df = pd.read_parquet(FEAT_PARQUET, memory_map=True)

    # Garantir split e key_id no feat_df
    need = [c for c in ("split", "key_id") if c not in feat_df.columns]
    if need:
        meta = pd.read_parquet(RAW_PARQUET, columns=["sample_id"] + need, memory_map=True)
        feat_df = feat_df.merge(meta, on="sample_id", how="left")

    # Carregar CT bytes do parquet raw (apenas colunas necessárias)
    print(f"  Carregando ciphertexts: {RAW_PARQUET.name}")
    raw_df = pd.read_parquet(RAW_PARQUET, columns=["sample_id", "ciphertext"], memory_map=True)
    merged = feat_df.merge(raw_df, on="sample_id", how="left")

    if merged["ciphertext"].isna().any():
        raise ValueError("Ciphertexts ausentes após merge — verifique sample_id.")

    # Protocolo 80/20
    merged["split_orig"] = merged["split"]
    merged["split"] = merged["split"].map(
        {"train": "trainval", "val": "trainval", "test": "test"}
    ).fillna(merged["split"])

    trainval = merged[merged["split"] == "trainval"].copy().reset_index(drop=True)
    test     = merged[merged["split"] == "test"].copy().reset_index(drop=True)

    tv_keys  = set(trainval["key_id"].unique())
    tst_keys = set(test["key_id"].unique())
    overlap  = tv_keys & tst_keys
    if overlap:
        raise ValueError(f"VAZAMENTO: {len(overlap)} chaves em trainval∩test!")

    classes   = sorted(merged["algorithm"].unique().tolist())
    label_map = {c: i for i, c in enumerate(classes)}

    print(f"  TrainVal : {len(trainval):,} | {len(tv_keys)} chaves")
    print(f"  Test     : {len(test):,} | {len(tst_keys)} chaves")
    print(f"  Classes  : {label_map}")
    return trainval, test, classes, label_map


# ---------------------------------------------------------------------------
# CV loop
# ---------------------------------------------------------------------------

def run_cv(
    trainval:  pd.DataFrame,
    classes:   list[str],
    label_map: dict[str, int],
    feat_cols: list[str],
) -> dict:
    """
    5-fold GroupKFold CV.
    Cada fold:
      1. Treina CNN1D + CNN2D no treino do fold (early stopping no val)
      2. Extrai latents para treino e val
      3. Concatena [307D | latent1D | latent2D]
      4. Feature selection MI→mRMR→Boruta no treino do fold
      5. Treina RF e XGBoost nos features selecionados
      6. Avalia no val
    """
    gkf    = GroupKFold(n_splits=N_FOLDS)
    groups = trainval["key_id"].to_numpy()
    y_all  = _label_encode(trainval["algorithm"], classes)

    fold_results: list[dict] = []
    selected_per_fold: list[list[str]] = []
    best_epochs_1d: list[int] = []
    best_epochs_2d: list[int] = []

    for fold_idx, (tr_idx, val_idx) in enumerate(gkf.split(trainval, y_all, groups)):
        fold_num = fold_idx + 1
        tr_keys  = set(groups[tr_idx])
        val_keys = set(groups[val_idx])
        assert not (tr_keys & val_keys), f"Fold {fold_num}: vazamento!"

        df_tr  = trainval.iloc[tr_idx]
        df_val = trainval.iloc[val_idx]
        y_tr   = y_all[tr_idx]
        y_val  = y_all[val_idx]

        print(f"\n  [Fold {fold_num}/{N_FOLDS}]  "
              f"treino={len(tr_keys)} chaves ({len(tr_idx):,})  "
              f"val={len(val_keys)} chaves ({len(val_idx):,})")

        # ── Treinar CNNs e extrair latents ───────────────────────────────
        extractor = HybridExtractor(CNN_CFG)
        extractor.fit(
            cts_train = df_tr["ciphertext"].tolist(),
            y_train   = y_tr,
            cts_val   = df_val["ciphertext"].tolist(),
            y_val     = y_val,
            verbose   = True,
        )
        best_epochs_1d.append(extractor.best_epoch_1d)
        best_epochs_2d.append(extractor.best_epoch_2d)

        # ── Construir vetor híbrido ──────────────────────────────────────
        F_tr  = df_tr [feat_cols].to_numpy(dtype=np.float64)
        F_val = df_val[feat_cols].to_numpy(dtype=np.float64)
        np.nan_to_num(F_tr,  copy=False, nan=0.0)
        np.nan_to_num(F_val, copy=False, nan=0.0)

        X_tr  = extractor.transform(F_tr,  df_tr ["ciphertext"].tolist())
        X_val = extractor.transform(F_val, df_val["ciphertext"].tolist())

        hybrid_feat_names = (
            feat_cols
            + [f"latent1d_{i}" for i in range(extractor.model1d.latent_dim)]
            + [f"latent2d_{i}" for i in range(extractor.model2d.latent_dim)]
        )
        print(f"    Vetor híbrido: {X_tr.shape[1]}D "
              f"(307 clássicas + {extractor.model1d.latent_dim} CNN1D "
              f"+ {extractor.model2d.latent_dim} CNN2D)")

        # ── Feature selection — fit APENAS no treino do fold ────────────
        t_sel = time.perf_counter()
        sel   = LWCFeatureSelector(SELECTOR_CFG)
        sel.fit(X_tr, y_tr, feature_names=hybrid_feat_names)
        X_tr_sel  = sel.transform(X_tr)
        X_val_sel = sel.transform(X_val)
        sel_time  = time.perf_counter() - t_sel
        selected  = sel.get_selected_names()
        rep_sel   = sel.get_stage_report()
        selected_per_fold.append(selected)
        print(f"    FS: {X_tr.shape[1]} → {len(selected)} features  "
              f"({sel_time:.1f}s)  "
              f"(MI→{rep_sel.get('stage1_output','?')}  "
              f"mRMR→{rep_sel.get('stage2_output','?')}  "
              f"Boruta→{rep_sel.get('stage3_output','?')})")

        # ── Classificadores ──────────────────────────────────────────────
        fold_res: dict = {
            "fold": fold_num,
            "n_train_keys":    len(tr_keys),
            "n_val_keys":      len(val_keys),
            "hybrid_dim":      int(X_tr.shape[1]),
            "n_selected":      len(selected),
            "best_epoch_1d":   extractor.best_epoch_1d,
            "best_epoch_2d":   extractor.best_epoch_2d,
        }

        for name, clf in _build_classifiers().items():
            t0    = time.perf_counter()
            clf.fit(X_tr_sel, y_tr)
            t_tr  = time.perf_counter() - t0
            y_pred = clf.predict(X_val_sel)
            f1    = float(f1_score(y_val, y_pred, average="macro", zero_division=0))
            bac   = float(balanced_accuracy_score(y_val, y_pred))
            print(f"    {name:10s}  F1={f1:.4f}  BalAcc={bac:.4f}  t={t_tr:.1f}s")
            fold_res[name] = {"f1_macro": f1, "balanced_accuracy": bac,
                              "train_time_s": round(t_tr, 2)}

        fold_results.append(fold_res)

    # Estabilidade Jaccard das features híbridas selecionadas
    pairs_jac = []
    for i, j in combinations(range(N_FOLDS), 2):
        jac = _jaccard(selected_per_fold[i], selected_per_fold[j])
        pairs_jac.append({"fold_i": i + 1, "fold_j": j + 1, "jaccard": round(jac, 4)})
    mean_jac = float(np.mean([p["jaccard"] for p in pairs_jac]))

    # Resumo por modelo
    model_names = list(_build_classifiers().keys())
    cv_summary: dict = {}
    for mname in model_names:
        f1s  = [r[mname]["f1_macro"]          for r in fold_results]
        bacs = [r[mname]["balanced_accuracy"]  for r in fold_results]
        cv_summary[mname] = {
            "f1_macro_mean": round(float(np.mean(f1s)),       4),
            "f1_macro_std":  round(float(np.std(f1s, ddof=1)), 4),
            "bal_acc_mean":  round(float(np.mean(bacs)),       4),
            "f1_per_fold":   [round(v, 4) for v in f1s],
        }

    return {
        "n_folds":              N_FOLDS,
        "folds":                fold_results,
        "cv_summary":           cv_summary,
        "feature_stability":    {
            "mean_jaccard_cross_fold": round(mean_jac, 4),
            "pairs":                  pairs_jac,
            "selected_per_fold":      [list(s) for s in selected_per_fold],
        },
        "mean_best_epoch_1d": math.ceil(float(np.mean(best_epochs_1d))),
        "mean_best_epoch_2d": math.ceil(float(np.mean(best_epochs_2d))),
    }


# ---------------------------------------------------------------------------
# Modelo final
# ---------------------------------------------------------------------------

def run_final(
    trainval:   pd.DataFrame,
    test:       pd.DataFrame,
    classes:    list[str],
    label_map:  dict[str, int],
    feat_cols:  list[str],
    mean_ep_1d: int,
    mean_ep_2d: int,
) -> tuple[dict, np.ndarray]:
    """
    Treina CNNs por épocas fixas no trainval completo (sem early stopping),
    aplica feature selection, treina RF/XGB e avalia no test holdout.
    """
    print(f"\n--- Modelo Final: trainval ({len(trainval):,}) → test ({len(test):,}) ---")
    print(f"  CNN1D épocas={mean_ep_1d}  CNN2D épocas={mean_ep_2d}")

    y_tv  = _label_encode(trainval["algorithm"], classes)
    y_tst = _label_encode(test["algorithm"],     classes)

    # Treinar CNNs
    extractor = HybridExtractor(CNN_CFG)
    extractor.fit_fixed(
        cts_train   = trainval["ciphertext"].tolist(),
        y_train     = y_tv,
        n_epochs_1d = mean_ep_1d,
        n_epochs_2d = mean_ep_2d,
        verbose     = True,
    )

    # Construir vetores híbridos
    F_tv  = trainval[feat_cols].to_numpy(dtype=np.float64)
    F_tst = test    [feat_cols].to_numpy(dtype=np.float64)
    np.nan_to_num(F_tv,  copy=False, nan=0.0)
    np.nan_to_num(F_tst, copy=False, nan=0.0)

    X_tv  = extractor.transform(F_tv,  trainval["ciphertext"].tolist())
    X_tst = extractor.transform(F_tst, test    ["ciphertext"].tolist())

    hybrid_feat_names = (
        feat_cols
        + [f"latent1d_{i}" for i in range(extractor.model1d.latent_dim)]
        + [f"latent2d_{i}" for i in range(extractor.model2d.latent_dim)]
    )
    print(f"  Vetor híbrido: {X_tv.shape[1]}D")

    # Feature selection no trainval completo
    t_sel = time.perf_counter()
    sel   = LWCFeatureSelector(SELECTOR_CFG)
    sel.fit(X_tv, y_tv, feature_names=hybrid_feat_names)
    X_tv_sel  = sel.transform(X_tv)
    X_tst_sel = sel.transform(X_tst)
    print(f"  FS: {X_tv.shape[1]} → {len(sel.get_selected_names())} features  "
          f"({time.perf_counter()-t_sel:.1f}s)")

    # Classificadores
    final_metrics: dict = {}
    predictions:   dict = {}

    for name, clf in _build_classifiers().items():
        t0     = time.perf_counter()
        clf.fit(X_tv_sel, y_tv)
        t_tr   = time.perf_counter() - t0
        t1     = time.perf_counter()
        y_pred = clf.predict(X_tst_sel)
        t_pred = time.perf_counter() - t1
        y_proba = _get_proba(clf, X_tst_sel)

        rep = compute_metrics(
            y_tst, y_pred, y_proba=y_proba,
            n_bootstrap=N_BOOTSTRAP, seed=SEED_BOOTSTRAP,
        )
        ci = rep.f1_macro_ci
        print(f"  {name:10s}  F1={rep.f1_macro:.4f}  "
              f"IC=[{ci[0]:.3f},{ci[1]:.3f}]  "
              f"BalAcc={rep.balanced_accuracy:.4f}  t={t_tr:.1f}s")

        final_metrics[name] = {
            **rep.as_dict(),
            "train_time_s":   round(t_tr,   2),
            "predict_time_s": round(t_pred, 2),
            "y_pred":         y_pred.tolist(),
        }
        predictions[name] = y_pred

    return final_metrics, y_tst


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    skip_cv   = "--skip-cv" in sys.argv
    cv_cache  = REPORTS_DIR / "_cv_cache.pkl"
    fin_cache = REPORTS_DIR / "_final_cache.pkl"

    print(f"\n{'='*70}")
    print(f"  Caminho D — Híbrido (60k, 64KB CT)")
    print(f"  [307D clássicas | latent CNN1D | latent CNN2D] → MI→mRMR→Boruta → RF/XGB")
    print(f"  Protocolo: 80/20 key-holdout + {N_FOLDS}-fold GroupKFold CV")
    print(f"  CNN1D max_len (Caminho B ref.) : {MAX_LEN_B} bytes")
    print(f"  CNN1D max_len (Caminho D)      : {CNN_CFG.max_len_1d} bytes")
    print(f"{'='*70}\n")

    if CNN_CFG.max_len_1d == MAX_LEN_B:
        print("  AVISO METODOLOGICO: GPU nao disponivel.")
        print(f"  CNN1D no Caminho D usando prefixo {MAX_LEN_B} bytes em vez do CT completo.")
        print("  Resultados do Caminho D NAO sao comparaveis com execucao em GPU.")
        print("  Use apenas para debug/smoke test.\n")
    else:
        print(f"  GPU disponivel — CNN1D usa CT completo ({CNN_CFG.max_len_1d} bytes)\n")

    if _MLFLOW:
        try:
            _mlflow_mod.log_param("cnn1d_max_len_caminhoB", MAX_LEN_B)
            _mlflow_mod.log_param("cnn1d_max_len_caminhoD", CNN_CFG.max_len_1d)
            _mlflow_mod.log_param("caminho_d_ct_completo",  torch.cuda.is_available())
        except Exception:
            pass

    t_total = time.perf_counter()

    trainval, test, classes, label_map = load_data()
    feat_cols = _feature_cols(trainval)
    assert len(feat_cols) == 307, f"Esperava 307 features clássicas, obteve {len(feat_cols)}"
    print(f"  Features clássicas: {len(feat_cols)}")
    print(f"  Vetor híbrido esperado: {len(feat_cols) + 512 + 128}D "
          f"(307 + {512} CNN1D + {128} CNN2D)")

    # ── CV ───────────────────────────────────────────────────────────────────
    if cv_cache.exists() and skip_cv:
        print(f"\n  [--skip-cv] Carregando cache CV: {cv_cache.name}")
        with cv_cache.open("rb") as f:
            cv_data = pickle.load(f)
    elif cv_cache.exists():
        print(f"\n  Cache CV encontrado ({cv_cache.name}). Carregando.")
        with cv_cache.open("rb") as f:
            cv_data = pickle.load(f)
    else:
        print(f"\n--- {N_FOLDS}-fold GroupKFold CV ---")
        cv_data = run_cv(trainval, classes, label_map, feat_cols)
        with cv_cache.open("wb") as f:
            pickle.dump(cv_data, f)
        print(f"  Cache CV salvo: {cv_cache.name}")

    print(f"\n  CV Summary (mean ± std F1):")
    for mname, stats in cv_data["cv_summary"].items():
        folds_str = "  ".join(f"f{i+1}={v:.4f}"
                              for i, v in enumerate(stats["f1_per_fold"]))
        print(f"    {mname:10s}  "
              f"F1={stats['f1_macro_mean']:.4f} ± {stats['f1_macro_std']:.4f}  "
              f"[{folds_str}]")
    stab = cv_data["feature_stability"]["mean_jaccard_cross_fold"]
    print(f"  Estabilidade features (Jaccard médio): {stab:.4f}")
    print(f"  Best epoch médio: CNN1D={cv_data['mean_best_epoch_1d']}  "
          f"CNN2D={cv_data['mean_best_epoch_2d']}")

    # ── Modelo final ─────────────────────────────────────────────────────────
    if fin_cache.exists():
        print(f"\n  Cache final encontrado ({fin_cache.name}). Carregando.")
        with fin_cache.open("rb") as f:
            final_metrics, y_tst = pickle.load(f)
    else:
        final_metrics, y_tst = run_final(
            trainval, test, classes, label_map, feat_cols,
            mean_ep_1d = cv_data["mean_best_epoch_1d"],
            mean_ep_2d = cv_data["mean_best_epoch_2d"],
        )
        with fin_cache.open("wb") as f:
            pickle.dump((final_metrics, y_tst), f)
        print(f"  Cache final salvo: {fin_cache.name}")

    # ── McNemar ──────────────────────────────────────────────────────────────
    model_names = list(final_metrics.keys())
    pairs       = list(combinations(model_names, 2))
    alpha_b     = 0.05 / len(pairs) if pairs else 0.05
    mcn_rows    = []
    for a, b in pairs:
        ya  = np.array(final_metrics[a]["y_pred"])
        yb  = np.array(final_metrics[b]["y_pred"])
        res = mcnemar_test(y_tst, ya, yb)
        sig = res["p_value"] < alpha_b
        mcn_rows.append([f"{a} vs {b}", f"{res['statistic']:.3f}",
                         f"{res['p_value']:.4g}", "sim" if sig else "nao"])

    # ── Tabela comparativa ───────────────────────────────────────────────────
    tbl_rows: list[list[str]] = []
    for mname, metrics in final_metrics.items():
        cv_stats = cv_data["cv_summary"].get(mname, {})
        cv_str   = (f"{cv_stats['f1_macro_mean']:.4f} ± {cv_stats['f1_macro_std']:.4f}"
                    if cv_stats else "—")
        tbl_rows.append([
            mname,
            cv_str,
            f"{metrics['f1_macro']:.4f}",
            f"[{metrics['f1_macro_ci_lower']:.3f},{metrics['f1_macro_ci_upper']:.3f}]",
            f"{metrics['balanced_accuracy']:.4f}",
            f"{metrics['train_time_s']:.1f}s",
        ])

    headers = ["Modelo", "F1 CV (mean±std)", "F1 test", "IC 95%", "BalAcc", "t treino"]
    md_tbl  = _md_table(tbl_rows, headers)
    mcn_md  = _md_table(mcn_rows,
                        [f"Comparação (α_bonf={alpha_b:.4f})", "estatística", "p-value", "Sig?"])

    elapsed = time.perf_counter() - t_total

    # ── Salvar outputs ───────────────────────────────────────────────────────
    def _serial(x):
        return x.tolist() if hasattr(x, "tolist") else str(x)

    (REPORTS_DIR / "cv_results.json").write_text(
        json.dumps(cv_data, indent=2, default=_serial), encoding="utf-8"
    )
    (REPORTS_DIR / "final_results.json").write_text(
        json.dumps({"model_metrics": final_metrics, "y_true": y_tst.tolist(),
                    "elapsed_s": round(elapsed, 1)},
                   indent=2, default=_serial),
        encoding="utf-8",
    )
    (REPORTS_DIR / "comparison_table.md").write_text(
        f"# Híbrido — Ascon vs GIFT (60k, 64KB CT)\n\n"
        f"Vetor: 307D clássicas + 512D CNN1D + 128D CNN2D = 947D\n"
        f"Baseline acaso = 0.5000\n\n{md_tbl}\n",
        encoding="utf-8",
    )
    (REPORTS_DIR / "mcnemar_table.md").write_text(
        f"# McNemar (correção continuidade + Bonferroni)\n\n{mcn_md}\n",
        encoding="utf-8",
    )

    print(f"\n{'='*70}")
    print(f"  RESULTADOS FINAIS (test holdout — {len(y_tst):,} amostras)")
    print(f"  Baseline acaso = 0.5000")
    print(f"{'='*70}")
    print(md_tbl)
    print(f"\n{mcn_md}")
    print(f"\n  Tempo total: {elapsed:.1f}s")
    print(f"  Relatórios : {REPORTS_DIR.relative_to(REPO_ROOT)}/")


if __name__ == "__main__":
    main()
