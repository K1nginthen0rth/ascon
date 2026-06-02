"""
Executa o experimento de CONTROLE POSITIVO Vigenere-XOR.

3 classes: Ascon-AEAD128 vs GIFT-COFB vs Vigenere-XOR.
Caminho A apenas — features classicas + seletor 3 estagios + Dummy/RF/SVM/XGBoost.
McNemar pareado entre todos os pares de modelos.

Hipotese: Vigenere e' cifra classica fraca; o pipeline DEVE detectar
facilmente (F1-macro RF >> 0.50, ideal proximo de 1.0 para a classe Vigenere).

Saidas (reports/control_vigenere_v1/):
  experiment_results.json
  comparison_table.md
  mcnemar_table.md
  selected_features.json
  confusion_matrices/{Modelo}.png

Uso:
    python scripts/run_vigenere_experiment.py
"""
from __future__ import annotations

import json
import sys
import time
from itertools import combinations
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src" / "crypto"))

import numpy as np
import pandas as pd

from src.eval.metrics import mcnemar_test
from src.features.selector import SelectorConfig
from src.models.classical import ClassicalPipeline, _NON_FEATURE_COLS

DATASET_ID       = "control_vigenere_v1"
FEATURES_PARQUET = REPO_ROOT / "data" / "processed" / f"{DATASET_ID}_features.parquet"
RAW_PARQUET      = REPO_ROOT / "data" / "processed" / f"{DATASET_ID}.parquet"

REPORTS_DIR = REPO_ROOT / "reports" / DATASET_ID
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

N_BOOTSTRAP  = 1000
SELECTOR_CFG = SelectorConfig(
    variance_threshold=1e-5,
    top_k_mi=200,
    n_features_mrmr=100,
    boruta_max_iter=100,
    random_state=13,
)


def _attach_split(features_df: pd.DataFrame, raw_df: pd.DataFrame) -> pd.DataFrame:
    if "split" in features_df.columns:
        return features_df
    if "sample_id" not in features_df.columns:
        raise ValueError("features_df precisa de 'sample_id'.")
    merged = features_df.merge(
        raw_df[["sample_id", "split"]], on="sample_id", how="left",
        validate="one_to_one",
    )
    if merged["split"].isna().any():
        n = int(merged["split"].isna().sum())
        raise ValueError(f"{n} amostras sem split apos merge.")
    return merged


def _verify_key_holdout(df: pd.DataFrame) -> None:
    tr = set(df.loc[df["split"] == "train", "key_id"].unique())
    va = set(df.loc[df["split"] == "val",   "key_id"].unique())
    te = set(df.loc[df["split"] == "test",  "key_id"].unique())
    if tr & te or tr & va or va & te:
        raise ValueError(
            f"VAZAMENTO de chave! train∩test={tr & te}, "
            f"train∩val={tr & va}, val∩test={va & te}"
        )
    print(f"  Chaves: train={len(tr)}, val={len(va)}, test={len(te)} (disjuntas OK)")


def _verify_no_len_leakage(features_df: pd.DataFrame) -> dict:
    """
    Vigenere CT_len = PT_len (sem tag); AEADs CT_len = PT_len + 16.
    len_ct ate' poderia mapear 1:1 para classe (Vigenere) — vazamento trivial.
    Confirmar que NAO esta entre as colunas de feature.
    """
    feat_cols = [c for c in features_df.columns if c not in _NON_FEATURE_COLS]
    forbidden = {"len_pt", "len_ad", "len_ct"}
    leak = forbidden.intersection(feat_cols)
    info = {
        "n_feature_cols":          len(feat_cols),
        "forbidden_cols_in_feats": sorted(leak),
        "len_ct_excluded":         "len_ct" not in feat_cols,
        "ct_lens_per_algorithm": {
            algo: sorted(features_df[features_df["algorithm"] == algo]
                         ["len_ct"].unique().tolist())
            for algo in features_df["algorithm"].unique()
        },
    }
    if leak:
        raise ValueError(
            f"VAZAMENTO: colunas {leak} presentes em features. "
            "Vigenere tem len_ct=len_pt mas AEADs tem +16 — viraria atalho trivial."
        )
    print(f"  len_ct/len_pt/len_ad excluidos das features: OK ({len(feat_cols)} features ativas)")
    return info



def _format_table(rows: list[list[str]], headers: list[str]) -> str:
    widths = [max(len(h), max((len(r[i]) for r in rows), default=0))
              for i, h in enumerate(headers)]
    sep = "| " + " | ".join("-" * w for w in widths) + " |"
    out = ["| " + " | ".join(h.ljust(w) for h, w in zip(headers, widths)) + " |", sep]
    for r in rows:
        out.append("| " + " | ".join(str(c).ljust(w) for c, w in zip(r, widths)) + " |")
    return "\n".join(out)


def main() -> None:
    print(f"\n{'='*70}\n  Controle Positivo Vigenere — 3 classes\n{'='*70}")
    print(f"  Features:  {FEATURES_PARQUET.relative_to(REPO_ROOT)}")
    print(f"  Raw bytes: {RAW_PARQUET.relative_to(REPO_ROOT)}")

    feat_df = pd.read_parquet(FEATURES_PARQUET)
    raw_df  = pd.read_parquet(RAW_PARQUET)
    feat_df = _attach_split(feat_df, raw_df)
    _verify_key_holdout(feat_df)
    leakage_info = _verify_no_len_leakage(feat_df)

    print(f"\n--- CAMINHO A: features classicas + seletor 3 estagios ---")
    pipe = ClassicalPipeline(
        n_bootstrap     = N_BOOTSTRAP,
        selector_config = SELECTOR_CFG,
        seed_models     = 7,
        seed_bootstrap  = 42,
    )
    t0 = time.perf_counter()
    res = pipe.run(feat_df, verbose=True)
    t_total = time.perf_counter() - t0
    print(f"  Caminho A total: {t_total:.1f}s")

    test_df  = feat_df[feat_df["split"] == "test"]
    classes  = sorted(feat_df["algorithm"].unique().tolist())
    label_map = {c: i for i, c in enumerate(classes)}
    y_test   = test_df["algorithm"].map(label_map).to_numpy()

    rows: list[list[str]] = []
    predictions: dict[str, dict] = {}
    for name, mres in res.models.items():
        m   = mres.metrics
        acc = float(np.mean(np.asarray(mres.y_pred) == y_test))
        rows.append([
            name,
            str(len(res.selected_features)),
            f"{acc:.4f}",
            f"{m.balanced_accuracy:.4f}",
            f"{mres.train_time_s:.1f}s",
        ])
        predictions[name] = {
            "y_pred":           mres.y_pred,
            "y_proba":          mres.y_proba,
            "confusion_matrix": m.confusion_matrix.tolist(),
            "metrics": {
                "accuracy":          acc,
                "balanced_accuracy": m.balanced_accuracy,
                "bal_acc_ci_lower":  m.balanced_accuracy_ci[0],
                "bal_acc_ci_upper":  m.balanced_accuracy_ci[1],
            },
        }

    headers = ["Modelo", "Features", "Acuracia", "Bal. Acc", "Tempo treino"]
    md_table = _format_table(rows, headers)

    mcnemar_rows: list[list[str]] = []
    pair_results: list[dict] = []
    for a, b in combinations(predictions.keys(), 2):
        ya = predictions[a]["y_pred"]
        yb = predictions[b]["y_pred"]
        r  = mcnemar_test(y_test, ya, yb)
        mcnemar_rows.append([
            f"{a} vs {b}",
            f"{r['statistic']:.3f}",
            f"{r['p_value']:.4g}",
            "sim" if r["significant"] else "nao",
        ])
        pair_results.append({"pair": (a, b), **r})

    mcnemar_md = _format_table(
        mcnemar_rows,
        ["Comparacao", "estatistica", "p-value", "Significativo?"],
    )

    # ---- Salvar artefatos ----
    print(f"\n--- Salvando em reports/{DATASET_ID}/ ---")

    results_payload = {
        "dataset":        DATASET_ID,
        "purpose":        "POSITIVE CONTROL via Vigenere-XOR (3-byte key)",
        "n_test_samples": int(len(y_test)),
        "label_map":      label_map,
        "leakage_check":  leakage_info,
        "selector": {
            "config": {k: getattr(SELECTOR_CFG, k) for k in (
                "variance_threshold", "top_k_mi", "n_features_mrmr",
                "boruta_max_iter", "random_state",
            )},
            "stage_report":      res.stage_report,
            "selected_features": res.selected_features,
        },
        "models": {
            name: {
                "metrics":        predictions[name]["metrics"],
                "confusion_matrix": predictions[name]["confusion_matrix"],
                "train_time_s":   mres.train_time_s,
                "predict_time_s": mres.predict_time_s,
            } for name, mres in res.models.items()
        },
        "mcnemar":      pair_results,
        "total_time_s": round(t_total, 1),
    }
    (REPORTS_DIR / "experiment_results.json").write_text(
        json.dumps(results_payload, indent=2,
                   default=lambda x: x.tolist() if hasattr(x, "tolist") else x),
        encoding="utf-8",
    )
    (REPORTS_DIR / "comparison_table.md").write_text(
        f"# Tabela comparativa - Controle Vigenere (key-holdout, 3 classes)\n\n"
        f"{md_table}\n",
        encoding="utf-8",
    )
    (REPORTS_DIR / "mcnemar_table.md").write_text(
        f"# Teste de McNemar entre pares\n\n(alpha=0.05, correcao de "
        f"continuidade ativa)\n\n{mcnemar_md}\n",
        encoding="utf-8",
    )
    (REPORTS_DIR / "selected_features.json").write_text(
        json.dumps({
            "n_selected":         len(res.selected_features),
            "stage_report":       res.stage_report,
            "selected_features":  res.selected_features,
        }, indent=2),
        encoding="utf-8",
    )

    label_names = [c for c, _ in sorted(label_map.items(), key=lambda kv: kv[1])]

    print(f"\n{'='*70}\n  RESULTADOS\n{'='*70}")
    print(md_table)
    print(f"\n{mcnemar_md}\n")

    print(f"\n--- Matrizes de Confusao (pred x real) ---")
    header_cm = "  {:12s}  ".format("") + "  ".join(f"{n:>15s}" for n in label_names)
    for name, payload in predictions.items():
        cm = payload["confusion_matrix"]
        print(f"\n  {name}")
        print(header_cm)
        for i, row in enumerate(cm):
            print("  {:12s}  ".format(label_names[i]) + "  ".join(f"{v:>15d}" for v in row))

    print(f"\n  Tempo total: {t_total:.1f}s")
    print(f"  Artefatos em: reports/{DATASET_ID}/")


if __name__ == "__main__":
    main()
