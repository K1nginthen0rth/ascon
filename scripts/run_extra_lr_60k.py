"""
Adiciona Regressao Logistica aos resultados do experimento 60k.

Reutiliza exatamente os mesmos folds e features selecionadas do experimento
principal (run_experiment_60k_cv.py), sem reprocessar feature extraction nem
feature selection. Atualiza os JSONs e tabelas de reports.

Uso:
    python scripts/run_extra_lr_60k.py
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

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score, f1_score
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler

from src.eval.metrics import compute_metrics, mcnemar_test

DATASET_ID   = "keyholdout_2class_60k_v1"
DATA_DIR     = REPO_ROOT / "data" / "processed"
FEAT_PARQUET = DATA_DIR / f"{DATASET_ID}_features.parquet"
RAW_PARQUET  = DATA_DIR / f"{DATASET_ID}.parquet"
REPORTS_DIR  = REPO_ROOT / "reports" / f"{DATASET_ID}_cv"

N_FOLDS        = 5
N_BOOTSTRAP    = 1000
SEED_MODELS    = 7
SEED_BOOTSTRAP = 42

_NON_FEATURE_COLS = {
    "sample_id", "algorithm", "key_id", "nonce_id",
    "len_pt", "len_ad", "len_ct", "split", "split_orig",
    "mode", "impl", "plaintext_source", "seed", "version",
    "timestamp", "ciphertext",
}


def _feature_cols(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if c not in _NON_FEATURE_COLS
            and df[c].dtype.kind in ("f", "i", "u")]


def _label_encode(y: pd.Series, classes: list[str]) -> np.ndarray:
    return y.map({c: i for i, c in enumerate(classes)}).to_numpy()


def _get_proba(model, X: np.ndarray) -> np.ndarray | None:
    if hasattr(model, "predict_proba"):
        try:
            return model.predict_proba(X)
        except Exception:
            pass
    return None


def _format_table(rows: list[list[str]], headers: list[str]) -> str:
    widths = [
        max(len(h), max((len(str(r[i])) for r in rows), default=0))
        for i, h in enumerate(headers)
    ]
    sep = "| " + " | ".join("-" * w for w in widths) + " |"
    out = ["| " + " | ".join(h.ljust(w) for h, w in zip(headers, widths)) + " |", sep]
    for r in rows:
        out.append("| " + " | ".join(str(c).ljust(w) for c, w in zip(r, widths)) + " |")
    return "\n".join(out)


def _build_lr() -> LogisticRegression:
    return LogisticRegression(
        C=1.0, max_iter=1000,
        class_weight="balanced",
        solver="lbfgs", random_state=SEED_MODELS, n_jobs=-1,
    )


def main() -> None:
    print("Adicionando Regressao Logistica ao experimento 60k...\n")

    # Carregar caches existentes
    cv_cache    = REPORTS_DIR / "_cv_cache.pkl"
    final_cache = REPORTS_DIR / "_final_cache.pkl"
    if not cv_cache.exists() or not final_cache.exists():
        print("ERRO: caches nao encontrados. Rode run_experiment_60k_cv.py primeiro.")
        sys.exit(1)

    with cv_cache.open("rb") as f:
        cv_data = pickle.load(f)
    with final_cache.open("rb") as f:
        predictions, final_data = pickle.load(f)

    # Carregar features
    print("Carregando features...")
    feat_df = pd.read_parquet(FEAT_PARQUET)
    need = [c for c in ("split", "key_id") if c not in feat_df.columns]
    if need:
        raw_meta = pd.read_parquet(RAW_PARQUET, columns=["sample_id"] + need)
        feat_df = feat_df.merge(raw_meta, on="sample_id", how="left")

    feat_df["split_orig"] = feat_df["split"]
    feat_df["split"] = feat_df["split"].map(
        {"train": "trainval", "val": "trainval", "test": "test"}
    )

    trainval_df = feat_df[feat_df["split"] == "trainval"].copy()
    test_df     = feat_df[feat_df["split"] == "test"].copy()
    feat_cols   = _feature_cols(trainval_df)
    classes     = sorted(feat_df["algorithm"].unique().tolist())
    label_map   = {c: i for i, c in enumerate(classes)}

    print(f"  TrainVal: {len(trainval_df):,} | Test: {len(test_df):,} | Features: {len(feat_cols)}")

    X_all  = trainval_df[feat_cols].to_numpy(dtype=np.float64).copy()
    y_all  = _label_encode(trainval_df["algorithm"], classes)
    groups = trainval_df["key_id"].to_numpy()
    np.nan_to_num(X_all, copy=False, nan=0.0)

    # -----------------------------------------------------------------------
    # CV — mesmos folds, mesmas features selecionadas
    # -----------------------------------------------------------------------
    print(f"\n--- LR: {N_FOLDS}-fold CV com features ja selecionadas ---")
    gkf = GroupKFold(n_splits=N_FOLDS)
    lr_cv_results: list[dict] = []

    for fold_idx, (tr_idx, val_idx) in enumerate(gkf.split(X_all, y_all, groups)):
        fold_num = fold_idx + 1
        selected = cv_data["folds"][fold_idx]["selector"]["stage_report"]
        n_sel    = cv_data["folds"][fold_idx]["selector"]["n_selected"]
        sel_names = cv_data["feature_stability"]["selected_per_fold"][fold_idx]

        # Reconstruir mascara a partir dos nomes selecionados no fold original
        sel_set  = set(sel_names)
        sel_mask = np.array([c in sel_set for c in feat_cols], dtype=bool)

        X_tr  = X_all[tr_idx][:, sel_mask].copy()
        X_val = X_all[val_idx][:, sel_mask].copy()
        y_tr  = y_all[tr_idx]
        y_val = y_all[val_idx]

        # Scaler fit apenas no treino do fold
        scaler   = StandardScaler().fit(X_tr)
        X_tr_sc  = scaler.transform(X_tr)
        X_val_sc = scaler.transform(X_val)

        lr  = _build_lr()
        t0  = time.perf_counter()
        lr.fit(X_tr_sc, y_tr)
        t_tr = time.perf_counter() - t0

        y_pred = lr.predict(X_val_sc)
        f1     = float(f1_score(y_val, y_pred, average="macro", zero_division=0))
        bac    = float(balanced_accuracy_score(y_val, y_pred))

        print(f"  [Fold {fold_num}/{N_FOLDS}]  {n_sel} features  "
              f"LR F1={f1:.4f}  BalAcc={bac:.4f}  t={t_tr:.1f}s")

        lr_cv_results.append({
            "fold":        fold_num,
            "n_features":  n_sel,
            "f1_macro":    f1,
            "balanced_accuracy": bac,
            "train_time_s": round(t_tr, 2),
        })

    f1s  = [r["f1_macro"]          for r in lr_cv_results]
    bacs = [r["balanced_accuracy"] for r in lr_cv_results]
    lr_cv_summary = {
        "f1_macro_mean": round(float(np.mean(f1s)), 4),
        "f1_macro_std":  round(float(np.std(f1s, ddof=1)), 4),
        "bal_acc_mean":  round(float(np.mean(bacs)), 4),
        "bal_acc_std":   round(float(np.std(bacs, ddof=1)), 4),
        "f1_per_fold":   [round(v, 4) for v in f1s],
    }
    print(f"\n  LR CV: F1={lr_cv_summary['f1_macro_mean']:.4f} +- {lr_cv_summary['f1_macro_std']:.4f}")

    # -----------------------------------------------------------------------
    # Modelo final — mesmas features do modelo final existente
    # -----------------------------------------------------------------------
    print("\n--- LR: modelo final (trainval -> test) ---")
    sel_names_final = final_data["selector"]["selected_features"]
    sel_set_final   = set(sel_names_final)
    sel_mask_final  = np.array([c in sel_set_final for c in feat_cols], dtype=bool)

    X_tv  = X_all[:, sel_mask_final].copy()
    X_tst = test_df[feat_cols].to_numpy(dtype=np.float64).copy()
    np.nan_to_num(X_tst, copy=False, nan=0.0)
    X_tst = X_tst[:, sel_mask_final]
    y_tv  = y_all
    y_tst = _label_encode(test_df["algorithm"], classes)

    scaler_final = StandardScaler().fit(X_tv)
    X_tv_sc      = scaler_final.transform(X_tv)
    X_tst_sc     = scaler_final.transform(X_tst)

    lr_final = _build_lr()
    t0 = time.perf_counter()
    lr_final.fit(X_tv_sc, y_tv)
    t_tr = time.perf_counter() - t0

    t1     = time.perf_counter()
    y_pred = lr_final.predict(X_tst_sc)
    t_pred = time.perf_counter() - t1
    y_prob = _get_proba(lr_final, X_tst_sc)

    rep = compute_metrics(y_tst, y_pred, y_proba=y_prob,
                          n_bootstrap=N_BOOTSTRAP, seed=SEED_BOOTSTRAP)
    ci  = rep.f1_macro_ci
    print(f"  LR  F1={rep.f1_macro:.4f}  IC=[{ci[0]:.3f},{ci[1]:.3f}]  "
          f"BalAcc={rep.balanced_accuracy:.4f}  t={t_tr:.1f}s")

    lr_final_metrics = {
        **rep.as_dict(),
        "train_time_s":   round(t_tr, 2),
        "predict_time_s": round(t_pred, 2),
        "best_params":    None,
    }

    # -----------------------------------------------------------------------
    # Atualizar caches e JSONs
    # -----------------------------------------------------------------------
    cv_data["cv_summary"]["LR"] = lr_cv_summary
    for i, fold in enumerate(cv_data["folds"]):
        fold["models"]["LR"] = lr_cv_results[i]

    predictions["LR"] = {
        "y_pred":           y_pred,
        "y_proba":          y_prob,
        "confusion_matrix": rep.confusion_matrix.tolist(),
    }
    final_data["model_metrics"]["LR"] = lr_final_metrics

    # Salvar caches atualizados
    with cv_cache.open("wb") as f:
        pickle.dump(cv_data, f)
    with final_cache.open("wb") as f:
        pickle.dump((predictions, final_data), f)

    # Atualizar JSONs
    (REPORTS_DIR / "cv_results.json").write_text(
        json.dumps(cv_data, indent=2, default=lambda x: x.tolist() if hasattr(x, "tolist") else x),
        encoding="utf-8",
    )

    y_tst_arr = final_data["y_true"]

    # McNemar completo (todos os pares incluindo LR)
    pairs  = list(combinations(predictions.keys(), 2))
    alpha_b = 0.05 / len(pairs)
    mcnemar_rows = []
    pair_results = []
    for a, b in pairs:
        ya  = predictions[a]["y_pred"]
        yb  = predictions[b]["y_pred"]
        res = mcnemar_test(y_tst_arr, ya, yb)
        sig = res["p_value"] < alpha_b
        mcnemar_rows.append([
            f"{a} vs {b}",
            f"{res['statistic']:.3f}",
            f"{res['p_value']:.4g}",
            "sim" if sig else "nao",
        ])
        pair_results.append({"pair": [a, b], "bonferroni_sig": sig, **res})

    (REPORTS_DIR / "final_results.json").write_text(
        json.dumps(
            {**final_data, "y_true": list(y_tst_arr),
             "mcnemar_alpha_bonferroni": alpha_b,
             "mcnemar": pair_results},
            indent=2, default=lambda x: x.tolist() if hasattr(x, "tolist") else x,
        ), encoding="utf-8",
    )

    # Tabela comparativa atualizada
    table_rows = []
    for mname, metrics in final_data["model_metrics"].items():
        cv_s   = cv_data["cv_summary"].get(mname, {})
        cv_str = (f"{cv_s['f1_macro_mean']:.4f} +- {cv_s['f1_macro_std']:.4f}"
                  if cv_s else "---")
        table_rows.append([
            mname,
            str(final_data["selector"]["n_selected"]),
            cv_str,
            f"{metrics['f1_macro']:.4f}",
            f"[{metrics['f1_macro_ci_lower']:.3f},{metrics['f1_macro_ci_upper']:.3f}]",
            f"{metrics['balanced_accuracy']:.4f}",
            f"{metrics['train_time_s']:.1f}s",
        ])

    headers = ["Modelo", "Features", "F1 CV (mean+-std)", "F1 test", "IC 95%", "BalAcc", "t treino"]
    md_table   = _format_table(table_rows, headers)
    mcnemar_md = _format_table(
        mcnemar_rows,
        [f"Comparacao (alpha={alpha_b:.4f})", "estatistica", "p-value", "Significativo?"]
    )

    (REPORTS_DIR / "comparison_table.md").write_text(
        f"# Ascon-AEAD128 vs GIFT-COFB -- 60k (80/20 key-holdout + 5-fold CV)\n\n"
        f"Baseline acaso = 0.5000\n\n{md_table}\n", encoding="utf-8",
    )
    (REPORTS_DIR / "mcnemar_table.md").write_text(
        f"# McNemar (Bonferroni, alpha={alpha_b:.4f})\n\n{mcnemar_md}\n",
        encoding="utf-8",
    )

    # Imprimir resultados finais
    label_names = [c for c, _ in sorted(label_map.items(), key=lambda kv: kv[1])]
    cm_lr = rep.confusion_matrix
    print(f"\n  Matriz de Confusao LR ({label_names[0]} | {label_names[1]}):")
    for i, row in enumerate(cm_lr):
        print(f"    {label_names[i]:15s}  {row[0]:6d}  {row[1]:6d}")

    print(f"\n{'='*70}\n  RESULTADOS FINAIS ATUALIZADOS\n{'='*70}")
    print(md_table)
    print(f"\n{mcnemar_md}")
    print(f"\n  Baseline acaso = 0.5000")
    print(f"  Relatorios: {REPORTS_DIR.relative_to(REPO_ROOT)}/")


if __name__ == "__main__":
    main()
