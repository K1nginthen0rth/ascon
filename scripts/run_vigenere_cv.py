"""
Controle Positivo Vigenere 64KB — 3 classes com 5-fold GroupKFold CV.

Dataset  : control_vigenere_64k_v1 (90k amostras, PT=64KB, 300 chaves)
Classes  : Ascon-AEAD128, GIFT-COFB, Vigenere-XOR (25 bits / 4 bytes)
Split    : 240 chaves trainval (80%) / 60 chaves test holdout (20%)
CV       : 5-fold GroupKFold por chave
Feature selection: dentro de cada fold (anti-vazamento)
Modelos  : RF(500) . SVM-RBF (GridSearchCV 3-fold sobre C x gamma) . LinearSVC . XGBoost(500)

Hipotese: Vigenere e' cifra classica fraca -> pipeline DEVE distingui-la com
acuracia proxima de 1.0 na classe Vigenere, validando que o seletor e os
classificadores detectam sinal quando ele existe.

Saidas em reports/control_vigenere_64k_v1_cv/:
  cv_results.json
  final_results.json
  comparison_table.md
  mcnemar_table.md
  confusion_matrices/

Uso:
    python scripts/run_vigenere_cv.py
    python scripts/run_vigenere_cv.py --skip-cv
"""
from __future__ import annotations

import json
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
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import balanced_accuracy_score, f1_score
from sklearn.model_selection import GridSearchCV, GroupKFold
from sklearn.preprocessing import StandardScaler
from sklearn.svm import LinearSVC, SVC
from xgboost import XGBClassifier

from src.eval.metrics import compute_metrics, mcnemar_test
from src.features.extractor import CiphertextFeatureExtractor
from src.features.selector import LWCFeatureSelector, SelectorConfig

DATASET_ID   = "control_vigenere_64k_v1"
DATA_DIR     = REPO_ROOT / "data" / "processed"
RAW_PARQUET  = DATA_DIR / f"{DATASET_ID}.parquet"
FEAT_PARQUET = DATA_DIR / f"{DATASET_ID}_features.parquet"
REPORTS_DIR  = REPO_ROOT / "reports" / f"{DATASET_ID}_cv"
CM_DIR       = REPORTS_DIR / "confusion_matrices"

REPORTS_DIR.mkdir(parents=True, exist_ok=True)
CM_DIR.mkdir(parents=True, exist_ok=True)

N_FOLDS        = 5
N_BOOTSTRAP    = 1000
SEED_MODELS    = 7
SEED_BOOTSTRAP = 42

SELECTOR_CFG = SelectorConfig(
    variance_threshold=1e-5,
    top_k_mi=200,
    n_features_mrmr=100,
    boruta_max_iter=100,
    random_state=13,
)

_NON_FEATURE_COLS = {
    "sample_id", "algorithm", "key_id", "nonce_id",
    "len_pt", "len_ad", "len_ct", "split", "split_orig",
    "mode", "impl", "plaintext_source", "seed", "version",
    "timestamp", "ciphertext", "key_bytes_used",
}

_NEEDS_SCALING = {"LinearSVC", "SVM"}

SVM_PARAM_GRID = {
    "C":     [0.1, 1, 10, 100],
    "gamma": ["scale", "auto", 1e-3, 1e-2],
}


def _feature_cols(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if c not in _NON_FEATURE_COLS
            and df[c].dtype.kind in ("f", "i", "u")]


def _label_encode(y: pd.Series, classes: list[str]) -> np.ndarray:
    return y.map({c: i for i, c in enumerate(classes)}).to_numpy()


def _jaccard(a: list[str], b: list[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 1.0
    return len(sa & sb) / len(sa | sb)


def _format_table(rows: list[list[str]], headers: list[str]) -> str:
    widths = [
        max(len(h), max((len(str(r[i])) for r in rows), default=0))
        for i, h in enumerate(headers)
    ]
    sep = "| " + " | ".join("-" * w for w in widths) + " |"
    header_row = "| " + " | ".join(h.ljust(w) for h, w in zip(headers, widths)) + " |"
    out = [header_row, sep]
    for r in rows:
        out.append("| " + " | ".join(str(c).ljust(w) for c, w in zip(r, widths)) + " |")
    return "\n".join(out)


def _build_models() -> dict:
    s = SEED_MODELS
    return {
        "RF": RandomForestClassifier(
            n_estimators=500, max_depth=None,
            class_weight="balanced", random_state=s, n_jobs=-1,
        ),
        "SVM": GridSearchCV(
            SVC(kernel="rbf", class_weight="balanced", random_state=s),
            param_grid=SVM_PARAM_GRID,
            cv=3, scoring="f1_macro", n_jobs=-1, refit=True, verbose=0,
        ),
        "LinearSVC": LinearSVC(
            C=1.0, class_weight="balanced", random_state=s, max_iter=5000,
        ),
        "XGBoost": XGBClassifier(
            n_estimators=500, max_depth=6, learning_rate=0.1,
            random_state=s, n_jobs=-1, eval_metric="mlogloss",
            tree_method="hist",
        ),
    }


def _get_proba(model, X: np.ndarray) -> np.ndarray | None:
    if hasattr(model, "predict_proba"):
        try:
            return model.predict_proba(X)
        except Exception:
            pass
    if hasattr(model, "decision_function"):
        scores = model.decision_function(X)
        if scores.ndim == 1:
            scores = np.column_stack([-scores, scores])
        exp_s = np.exp(scores - scores.max(axis=1, keepdims=True))
        return exp_s / exp_s.sum(axis=1, keepdims=True)
    return None


def ensure_features() -> pd.DataFrame:
    if FEAT_PARQUET.exists():
        print(f"  Features ja extraidas: {FEAT_PARQUET.name}")
        return pd.read_parquet(FEAT_PARQUET)
    print(f"  Extraindo features de {RAW_PARQUET.name}  (alguns minutos)...")
    extractor = CiphertextFeatureExtractor()
    df = extractor.extract_dataset(RAW_PARQUET, output_path=FEAT_PARQUET, n_jobs=-1)
    return df


def prepare_data() -> tuple[pd.DataFrame, pd.DataFrame, list[str], dict[str, int]]:
    feat_df = ensure_features()

    need = [c for c in ("split", "key_id") if c not in feat_df.columns]
    if need:
        raw_meta = pd.read_parquet(RAW_PARQUET, columns=["sample_id"] + need)
        feat_df = feat_df.merge(raw_meta, on="sample_id", how="left")

    if feat_df["split"].isna().any():
        raise ValueError("Amostras sem coluna 'split' apos merge.")

    feat_df["split_orig"] = feat_df["split"]
    feat_df["split"] = feat_df["split"].map(
        {"train": "trainval", "val": "trainval", "test": "test"}
    )

    trainval_df = feat_df[feat_df["split"] == "trainval"].copy()
    test_df     = feat_df[feat_df["split"] == "test"].copy()

    if len(trainval_df) == 0 or len(test_df) == 0:
        raise ValueError("Bloco trainval ou test vazio — verifique os splits.")

    tv_keys  = set(trainval_df["key_id"].unique())
    tst_keys = set(test_df["key_id"].unique())
    if tv_keys & tst_keys:
        raise ValueError(f"VAZAMENTO: chaves em trainval∩test = {tv_keys & tst_keys}")

    print(f"  TrainVal : {len(trainval_df):,} amostras | {len(tv_keys)} chaves")
    print(f"  Test     : {len(test_df):,} amostras | {len(tst_keys)} chaves")

    classes   = sorted(feat_df["algorithm"].unique().tolist())
    label_map = {c: i for i, c in enumerate(classes)}
    return trainval_df, test_df, classes, label_map


def run_cv(
    trainval_df: pd.DataFrame,
    classes: list[str],
    label_map: dict[str, int],
    feat_cols: list[str],
) -> dict:
    X_all  = trainval_df[feat_cols].to_numpy(dtype=np.float64).copy()
    y_all  = _label_encode(trainval_df["algorithm"], classes)
    groups = trainval_df["key_id"].to_numpy()
    np.nan_to_num(X_all, copy=False, nan=0.0)

    gkf = GroupKFold(n_splits=N_FOLDS)
    cv_folds: list[dict] = []
    selected_per_fold: list[list[str]] = []

    for fold_idx, (tr_idx, val_idx) in enumerate(gkf.split(X_all, y_all, groups)):
        fold_num = fold_idx + 1
        tr_keys  = set(groups[tr_idx])
        val_keys = set(groups[val_idx])
        assert not (tr_keys & val_keys), f"Fold {fold_num}: vazamento de chave!"

        print(f"\n  [Fold {fold_num}/{N_FOLDS}]  "
              f"treino={len(tr_keys)} chaves ({len(tr_idx):,} amostras)  "
              f"val={len(val_keys)} chaves ({len(val_idx):,} amostras)")

        X_tr  = X_all[tr_idx].copy()
        X_val = X_all[val_idx].copy()
        y_tr  = y_all[tr_idx]
        y_val = y_all[val_idx]

        t_sel = time.perf_counter()
        sel   = LWCFeatureSelector(SELECTOR_CFG)
        sel.fit(X_tr, y_tr, feature_names=feat_cols)
        X_tr_sel  = sel.transform(X_tr)
        X_val_sel = sel.transform(X_val)
        sel_time  = time.perf_counter() - t_sel
        selected  = sel.get_selected_names()
        rep_sel   = sel.get_stage_report()
        selected_per_fold.append(selected)
        print(f"     FS: {len(feat_cols)} -> {len(selected)} features  "
              f"(VT->{rep_sel.get('stage1_after_variance','?')}, "
              f"MI->{rep_sel.get('stage1_output','?')}, "
              f"mRMR->{rep_sel.get('stage2_output','?')}, "
              f"Boruta->{rep_sel.get('stage3_output','?')})  {sel_time:.1f}s")

        scaler   = StandardScaler().fit(X_tr_sel)
        X_tr_sc  = scaler.transform(X_tr_sel)
        X_val_sc = scaler.transform(X_val_sel)

        fold_models = _build_models()
        fold_res: dict[str, dict] = {}
        for name, mdl in fold_models.items():
            X_tr_m  = X_tr_sc  if name in _NEEDS_SCALING else X_tr_sel
            X_val_m = X_val_sc if name in _NEEDS_SCALING else X_val_sel

            t0 = time.perf_counter()
            mdl.fit(X_tr_m, y_tr)
            t_tr = time.perf_counter() - t0

            y_pred = mdl.predict(X_val_m)
            f1  = float(f1_score(y_val, y_pred, average="macro", zero_division=0))
            bac = float(balanced_accuracy_score(y_val, y_pred))
            best_params = mdl.best_params_ if hasattr(mdl, "best_params_") else None
            params_str  = f"  best={best_params}" if best_params else ""
            print(f"     {name:10s}  F1={f1:.4f}  BalAcc={bac:.4f}  t={t_tr:.1f}s{params_str}")
            fold_res[name] = {
                "f1_macro":          f1,
                "balanced_accuracy": bac,
                "train_time_s":      round(t_tr, 2),
                "best_params":       best_params,
            }

        cv_folds.append({
            "fold":            fold_num,
            "n_train_keys":    len(tr_keys),
            "n_val_keys":      len(val_keys),
            "n_train_samples": int(len(tr_idx)),
            "n_val_samples":   int(len(val_idx)),
            "selector": {"n_selected": len(selected), "stage_report": rep_sel},
            "models": fold_res,
        })

    pairs_jac = []
    for i, j in combinations(range(N_FOLDS), 2):
        j_val = _jaccard(selected_per_fold[i], selected_per_fold[j])
        pairs_jac.append({"fold_i": i + 1, "fold_j": j + 1, "jaccard": round(j_val, 4)})
    mean_jac = float(np.mean([p["jaccard"] for p in pairs_jac]))

    model_names = list(cv_folds[0]["models"].keys())
    cv_summary: dict[str, dict] = {}
    for mname in model_names:
        f1s  = [r["models"][mname]["f1_macro"]         for r in cv_folds]
        bacs = [r["models"][mname]["balanced_accuracy"] for r in cv_folds]
        cv_summary[mname] = {
            "f1_macro_mean": round(float(np.mean(f1s)), 4),
            "f1_macro_std":  round(float(np.std(f1s, ddof=1)), 4),
            "bal_acc_mean":  round(float(np.mean(bacs)), 4),
            "bal_acc_std":   round(float(np.std(bacs, ddof=1)), 4),
            "f1_per_fold":   [round(v, 4) for v in f1s],
        }

    return {
        "n_folds":    N_FOLDS,
        "folds":      cv_folds,
        "cv_summary": cv_summary,
        "feature_stability": {
            "mean_jaccard_cross_fold": round(mean_jac, 4),
            "pairs":                  pairs_jac,
            "selected_per_fold":      [list(s) for s in selected_per_fold],
        },
    }


def run_final(
    trainval_df: pd.DataFrame,
    test_df: pd.DataFrame,
    classes: list[str],
    label_map: dict[str, int],
    feat_cols: list[str],
) -> tuple[dict, dict]:
    print(f"\n--- Modelo Final: trainval ({len(trainval_df):,}) -> test ({len(test_df):,}) ---")

    X_tv  = trainval_df[feat_cols].to_numpy(dtype=np.float64).copy()
    X_tst = test_df    [feat_cols].to_numpy(dtype=np.float64).copy()
    y_tv  = _label_encode(trainval_df["algorithm"], classes)
    y_tst = _label_encode(test_df    ["algorithm"], classes)
    np.nan_to_num(X_tv,  copy=False, nan=0.0)
    np.nan_to_num(X_tst, copy=False, nan=0.0)

    t_sel = time.perf_counter()
    sel   = LWCFeatureSelector(SELECTOR_CFG)
    sel.fit(X_tv, y_tv, feature_names=feat_cols)
    X_tv_sel  = sel.transform(X_tv)
    X_tst_sel = sel.transform(X_tst)
    sel_time  = time.perf_counter() - t_sel
    selected  = sel.get_selected_names()
    rep_sel   = sel.get_stage_report()
    print(f"  FS: {len(feat_cols)} -> {len(selected)} features  ({sel_time:.1f}s)")

    scaler   = StandardScaler().fit(X_tv_sel)
    X_tv_sc  = scaler.transform(X_tv_sel)
    X_tst_sc = scaler.transform(X_tst_sel)

    models = _build_models()
    predictions: dict[str, dict] = {}
    final_metrics: dict[str, dict] = {}

    for name, mdl in models.items():
        X_tr_m  = X_tv_sc  if name in _NEEDS_SCALING else X_tv_sel
        X_tst_m = X_tst_sc if name in _NEEDS_SCALING else X_tst_sel

        t0 = time.perf_counter()
        mdl.fit(X_tr_m, y_tv)
        t_tr = time.perf_counter() - t0

        t1     = time.perf_counter()
        y_pred = mdl.predict(X_tst_m)
        t_pred = time.perf_counter() - t1

        y_proba = _get_proba(mdl, X_tst_m)

        rep = compute_metrics(
            y_tst, y_pred, y_proba=y_proba,
            n_bootstrap=N_BOOTSTRAP, seed=SEED_BOOTSTRAP,
        )
        best_params = mdl.best_params_ if hasattr(mdl, "best_params_") else None
        ci = rep.f1_macro_ci
        params_str = f"  best={best_params}" if best_params else ""
        print(f"  {name:10s}  F1={rep.f1_macro:.4f}  "
              f"IC=[{ci[0]:.3f},{ci[1]:.3f}]  "
              f"BalAcc={rep.balanced_accuracy:.4f}  t={t_tr:.1f}s{params_str}")

        predictions[name] = {
            "y_pred":           y_pred,
            "y_proba":          y_proba,
            "confusion_matrix": rep.confusion_matrix.tolist(),
        }
        final_metrics[name] = {
            **rep.as_dict(),
            "train_time_s":   round(t_tr, 2),
            "predict_time_s": round(t_pred, 2),
            "best_params":    best_params,
        }

    return predictions, {
        "y_true":    y_tst,
        "label_map": label_map,
        "model_metrics": final_metrics,
        "selector": {
            "n_selected":        len(selected),
            "stage_report":      rep_sel,
            "selected_features": selected,
        },
    }


def _save_confusion_matrices(predictions: dict, label_names: list[str]) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("  matplotlib indisponivel — pulando CMs em PNG.")
        return

    for name, payload in predictions.items():
        cm  = np.asarray(payload["confusion_matrix"])
        fig, ax = plt.subplots(figsize=(5, 5))
        im = ax.imshow(cm, cmap="Blues")
        for i in range(cm.shape[0]):
            for j in range(cm.shape[1]):
                ax.text(j, i, str(int(cm[i, j])),
                        ha="center", va="center", fontsize=9, color="black")
        ax.set_xticks(range(len(label_names)))
        ax.set_yticks(range(len(label_names)))
        ax.set_xticklabels(label_names, fontsize=8, rotation=15)
        ax.set_yticklabels(label_names, fontsize=8)
        ax.set_xlabel("Predito", fontsize=10)
        ax.set_ylabel("Verdadeiro", fontsize=10)
        ax.set_title(f"Confusao — {name}", fontsize=10)
        plt.colorbar(im, ax=ax)
        fig.tight_layout()
        safe = name.replace(" ", "_").replace("/", "_")
        fig.savefig(CM_DIR / f"{safe}.png", dpi=120)
        plt.close(fig)


def main() -> None:
    print(f"\n{'='*70}")
    print(f"  Controle Positivo Vigenere 64KB — 3 classes")
    print(f"  Protocolo: 80/20 key-holdout + {N_FOLDS}-fold GroupKFold CV")
    print(f"  Seeds: modelos={SEED_MODELS}  bootstrap={SEED_BOOTSTRAP}  FS=13")
    print(f"{'='*70}\n")

    t_total = time.perf_counter()

    trainval_df, test_df, classes, label_map = prepare_data()
    feat_cols = _feature_cols(trainval_df)
    print(f"  Classes  : {classes}")
    print(f"  Features : {len(feat_cols)}")

    cv_cache = REPORTS_DIR / "_cv_cache.pkl"
    skip_cv  = "--skip-cv" in sys.argv

    if cv_cache.exists() and skip_cv:
        print(f"\n  [--skip-cv] Carregando cache CV de {cv_cache.name}")
        with cv_cache.open("rb") as f:
            cv_data = pickle.load(f)
    elif cv_cache.exists():
        print(f"\n  Cache CV encontrado: {cv_cache.name}  (use --skip-cv para reusar)")
        with cv_cache.open("rb") as f:
            cv_data = pickle.load(f)
    else:
        print(f"\n--- {N_FOLDS}-fold GroupKFold CV  ({len(trainval_df):,} amostras trainval) ---")
        cv_data = run_cv(trainval_df, classes, label_map, feat_cols)
        with cv_cache.open("wb") as f:
            pickle.dump(cv_data, f)
        print(f"\n  Cache CV salvo em: {cv_cache.name}")

    print(f"\n  CV Summary (mean +- std F1 em {N_FOLDS} folds):")
    for mname, stats in cv_data["cv_summary"].items():
        folds_str = "  ".join(f"f{i+1}={v:.4f}"
                              for i, v in enumerate(stats["f1_per_fold"]))
        print(f"    {mname:10s}  "
              f"F1={stats['f1_macro_mean']:.4f} +- {stats['f1_macro_std']:.4f}  "
              f"[{folds_str}]")
    stab = cv_data["feature_stability"]["mean_jaccard_cross_fold"]
    print(f"  Estabilidade features (Jaccard medio cross-fold): {stab:.4f}")

    final_cache = REPORTS_DIR / "_final_cache.pkl"
    if final_cache.exists():
        print(f"\n  Cache final encontrado: {final_cache.name}")
        with final_cache.open("rb") as f:
            predictions, final_data = pickle.load(f)
    else:
        predictions, final_data = run_final(
            trainval_df, test_df, classes, label_map, feat_cols
        )
        with final_cache.open("wb") as f:
            pickle.dump((predictions, final_data), f)
        print(f"  Cache final salvo em: {final_cache.name}")

    y_tst = final_data["y_true"]

    pairs = list(combinations(predictions.keys(), 2))
    alpha_bonf = 0.05 / len(pairs) if pairs else 0.05
    mcnemar_rows: list[list[str]] = []
    pair_results: list[dict] = []
    for a, b in pairs:
        res = mcnemar_test(y_tst, predictions[a]["y_pred"], predictions[b]["y_pred"])
        sig = res["p_value"] < alpha_bonf
        mcnemar_rows.append([
            f"{a} vs {b}",
            f"{res['statistic']:.3f}",
            f"{res['p_value']:.4g}",
            "sim" if sig else "nao",
        ])
        pair_results.append({"pair": [a, b], "bonferroni_sig": sig, **res})

    table_rows: list[list[str]] = []
    for mname, metrics in final_data["model_metrics"].items():
        cv_stats = cv_data["cv_summary"].get(mname, {})
        cv_str   = (
            f"{cv_stats['f1_macro_mean']:.4f} +- {cv_stats['f1_macro_std']:.4f}"
            if cv_stats else "---"
        )
        table_rows.append([
            mname,
            str(final_data["selector"]["n_selected"]),
            cv_str,
            f"{metrics['f1_macro']:.4f}",
            f"[{metrics['f1_macro_ci_lower']:.3f},{metrics['f1_macro_ci_upper']:.3f}]",
            f"{metrics['balanced_accuracy']:.4f}",
            f"{metrics['train_time_s']:.1f}s",
        ])

    headers_tbl = [
        "Modelo", "Features",
        f"F1 CV (mean+-std,{N_FOLDS}fold)", "F1 test", "IC 95%", "BalAcc", "t treino",
    ]
    md_table   = _format_table(table_rows, headers_tbl)
    mcnemar_md = _format_table(
        mcnemar_rows,
        [f"Comparacao (alpha={alpha_bonf:.4f})", "estatistica", "p-value", "Significativo?"],
    )

    elapsed = time.perf_counter() - t_total

    (REPORTS_DIR / "cv_results.json").write_text(
        json.dumps(cv_data, indent=2, default=lambda x: x.tolist() if hasattr(x, "tolist") else x),
        encoding="utf-8",
    )
    (REPORTS_DIR / "final_results.json").write_text(
        json.dumps(
            {
                **final_data,
                "y_true": y_tst.tolist(),
                "mcnemar_alpha_bonferroni": alpha_bonf,
                "mcnemar": pair_results,
                "total_elapsed_s": round(elapsed, 1),
            },
            indent=2,
            default=lambda x: x.tolist() if hasattr(x, "tolist") else x,
        ),
        encoding="utf-8",
    )
    (REPORTS_DIR / "comparison_table.md").write_text(
        f"# Controle Positivo Vigenere 64KB — 3 classes "
        f"(80/20 key-holdout + {N_FOLDS}-fold CV)\n\n"
        f"Baseline acaso (1/3) = 0.3333\n\n{md_table}\n",
        encoding="utf-8",
    )
    (REPORTS_DIR / "mcnemar_table.md").write_text(
        f"# Teste de McNemar (Bonferroni, alpha={alpha_bonf:.4f})\n\n{mcnemar_md}\n",
        encoding="utf-8",
    )

    label_names = [c for c, _ in sorted(label_map.items(), key=lambda kv: kv[1])]
    _save_confusion_matrices(predictions, label_names)

    print(f"\n{'='*70}")
    print(f"  RESULTADOS FINAIS (test holdout — {len(y_tst):,} amostras)")
    print(f"{'='*70}")
    print(md_table)
    print(f"\n{mcnemar_md}")

    print(f"\n--- Matrizes de Confusao ---")
    header_cm = "  {:15s}  " .format("") + "  ".join(f"{n:>15s}" for n in label_names)
    for name, payload in predictions.items():
        cm = payload["confusion_matrix"]
        print(f"\n  {name}")
        print(header_cm)
        for i, row in enumerate(cm):
            print("  {:15s}  ".format(label_names[i]) + "  ".join(f"{v:>15d}" for v in row))

    print(f"\n  Baseline acaso (1/3) = 0.3333")
    print(f"  Tempo total: {elapsed:.1f}s")
    print(f"  Relatorios : {REPORTS_DIR.relative_to(REPO_ROOT)}/")


if __name__ == "__main__":
    main()
