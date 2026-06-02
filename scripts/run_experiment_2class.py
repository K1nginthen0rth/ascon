"""
Executa o experimento central da tese: Ascon-AEAD128 vs GIFT-COFB.

Caminho A — features clássicas + seletor 3 estágios + Dummy/RF/SVM/XGBoost.
Caminho B — CNN 1D sobre bytes crus.
Comparação — McNemar pareado entre todos os pares de modelos.

Uso:
    python scripts/run_experiment_2class.py [dataset_id]

Default dataset_id = keyholdout_2class_v1 (15k amostras).
Para 50k: python scripts/run_experiment_2class.py keyholdout_2class_50k_v1

Saídas (reports/<dataset_id>/):
  experiment_2class_results.json
  comparison_table.md
  mcnemar_table.md
  confusion_matrices/{Modelo}.png
  selected_features.json
  cnn_history.json
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
from src.models.classical import ClassicalPipeline
from src.models.cnn_trainer import CNN1DTrainer

# ---------------------------------------------------------------------------
# Configuração (sobrescrita opcional via argv[1])
# ---------------------------------------------------------------------------
DATASET_ID = sys.argv[1] if len(sys.argv) > 1 else "keyholdout_2class_v1"

FEATURES_PARQUET = REPO_ROOT / "data" / "processed" / f"{DATASET_ID}_features.parquet"
RAW_PARQUET      = REPO_ROOT / "data" / "processed" / f"{DATASET_ID}.parquet"
SPLITS_JSON      = REPO_ROOT / "data" / "processed" / f"{DATASET_ID}_splits.json"

# Para o dataset default, mantemos saída em reports/ (compatibilidade).
# Para outros datasets, criamos subpasta reports/<dataset_id>/ para nao
# sobrescrever resultados anteriores.
if DATASET_ID == "keyholdout_2class_v1":
    REPORTS_DIR = REPO_ROOT / "reports"
else:
    REPORTS_DIR = REPO_ROOT / "reports" / DATASET_ID
CM_DIR = REPORTS_DIR / "confusion_matrices"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
CM_DIR.mkdir(parents=True, exist_ok=True)

N_BOOTSTRAP   = 1000
SELECTOR_CFG  = SelectorConfig(
    variance_threshold=1e-5,
    top_k_mi=200,
    n_features_mrmr=100,
    boruta_max_iter=100,
    random_state=13,
)


def _attach_split(features_df: pd.DataFrame, raw_df: pd.DataFrame) -> pd.DataFrame:
    """
    Garante que features_df tem coluna 'split'. Se não tiver, faz merge via
    sample_id com o parquet original.
    """
    if "split" in features_df.columns:
        return features_df
    if "split" not in raw_df.columns:
        raise ValueError("Nem features_df nem raw_df têm coluna 'split'. Regere os dados.")
    if "sample_id" not in features_df.columns:
        raise ValueError("features_df precisa de 'sample_id' para merge.")

    merged = features_df.merge(
        raw_df[["sample_id", "split"]], on="sample_id", how="left", validate="one_to_one"
    )
    if merged["split"].isna().any():
        n_miss = int(merged["split"].isna().sum())
        raise ValueError(f"{n_miss} amostras sem split após merge — verifique sample_id.")
    return merged


def _verify_key_holdout(df: pd.DataFrame) -> None:
    train = set(df.loc[df["split"] == "train", "key_id"].unique())
    val   = set(df.loc[df["split"] == "val",   "key_id"].unique())
    test  = set(df.loc[df["split"] == "test",  "key_id"].unique())
    if train & test or train & val or val & test:
        raise ValueError(
            f"VAZAMENTO de chave entre splits! "
            f"train∩test={train & test}, train∩val={train & val}, val∩test={val & test}"
        )
    print(f"  Chaves: train={len(train)}, val={len(val)}, test={len(test)} (disjuntas OK)")


def _save_confusion_matrices(predictions: dict, label_names: list[str]) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("  matplotlib indisponível — pulando matrizes em PNG.")
        return

    for name, payload in predictions.items():
        cm = np.asarray(payload["confusion_matrix"])
        fig, ax = plt.subplots(figsize=(4, 4))
        im = ax.imshow(cm, cmap="Blues")
        for i in range(cm.shape[0]):
            for j in range(cm.shape[1]):
                ax.text(j, i, str(int(cm[i, j])),
                        ha="center", va="center", color="black")
        ax.set_xticks(range(len(label_names))); ax.set_yticks(range(len(label_names)))
        ax.set_xticklabels(label_names); ax.set_yticklabels(label_names)
        ax.set_xlabel("Predito"); ax.set_ylabel("Verdadeiro")
        safe = name.replace(" ", "_").replace("/", "_")
        ax.set_title(f"Matriz de confusao — {name}")
        plt.colorbar(im, ax=ax)
        fig.tight_layout()
        fig.savefig(CM_DIR / f"{safe}.png", dpi=120)
        plt.close(fig)


def _format_table(rows: list[list[str]], headers: list[str]) -> str:
    widths = [max(len(h), max((len(r[i]) for r in rows), default=0)) for i, h in enumerate(headers)]
    sep = "| " + " | ".join("-" * w for w in widths) + " |"
    out = ["| " + " | ".join(h.ljust(w) for h, w in zip(headers, widths)) + " |", sep]
    for r in rows:
        out.append("| " + " | ".join(str(c).ljust(w) for c, w in zip(r, widths)) + " |")
    return "\n".join(out)


def main() -> None:
    print(f"\n{'='*70}\n  Experimento 2-classes: Ascon-AEAD128 vs GIFT-COFB\n{'='*70}")
    print(f"  Features:  {FEATURES_PARQUET.relative_to(REPO_ROOT)}")
    print(f"  Raw bytes: {RAW_PARQUET.relative_to(REPO_ROOT)}")

    # 1. Carregar dados
    feat_df = pd.read_parquet(FEATURES_PARQUET)
    raw_df  = pd.read_parquet(RAW_PARQUET)
    feat_df = _attach_split(feat_df, raw_df)
    _verify_key_holdout(feat_df)

    n_features = sum(
        1 for c in feat_df.columns
        if c not in {"sample_id","algorithm","key_id","nonce_id","len_pt","len_ad",
                     "len_ct","split","mode","impl","plaintext_source","seed",
                     "version","timestamp","ciphertext"}
    )
    print(f"  Features brutas: {n_features}")
    assert n_features == 307, f"Esperava 307 features, obteve {n_features}"

    # 2. CAMINHO A — clássico (com cache em pickle para resume após crash)
    import pickle
    cache_path = REPORTS_DIR / "_caminho_a.pkl"
    if cache_path.exists():
        print(f"\n--- CAMINHO A: usando cache de {cache_path.relative_to(REPORTS_DIR.parent)} ---")
        with cache_path.open("rb") as f:
            res_a, t_a = pickle.load(f)
        print(f"  Cache hit: {len(res_a.models)} modelos, t={t_a:.1f}s")
    else:
        print(f"\n--- CAMINHO A: features clássicas + seletor 3 estágios ---")
        pipe = ClassicalPipeline(
            n_bootstrap=N_BOOTSTRAP,
            selector_config=SELECTOR_CFG,
            seed_models=7,
            seed_bootstrap=42,
        )
        t_start_a = time.perf_counter()
        res_a = pipe.run(feat_df, verbose=True)
        t_a   = time.perf_counter() - t_start_a
        print(f"  Caminho A total: {t_a:.1f}s")
        with cache_path.open("wb") as f:
            pickle.dump((res_a, t_a), f)
        print(f"  Cache salvo em: {cache_path.relative_to(REPORTS_DIR.parent)}")

    # 3. CAMINHO B — CNN 1D (sobre raw bytes)
    print(f"\n--- CAMINHO B: CNN 1D sobre bytes crus ---")
    raw_df_split = raw_df.copy()
    if "split" not in raw_df_split.columns:
        raise ValueError("raw_df precisa da coluna 'split'.")

    cnn_trainer = CNN1DTrainer(
        max_len=1040, batch_size=64, n_epochs=20, lr=1e-3, patience=5,
        seed=7, n_bootstrap=N_BOOTSTRAP, seed_bootstrap=42,
    )
    t_start_b = time.perf_counter()
    res_b = cnn_trainer.train(raw_df_split, verbose=True)
    t_b   = time.perf_counter() - t_start_b
    print(f"  Caminho B total: {t_b:.1f}s  (best epoch: {res_b.best_epoch})")

    # 4. Reunir y_test e predições para McNemar
    test_df = feat_df[feat_df["split"] == "test"]
    classes = sorted(feat_df["algorithm"].unique().tolist())
    label_map = {c: i for i, c in enumerate(classes)}
    y_test = test_df["algorithm"].map(label_map).to_numpy()

    # CNN também usa os mesmos sample_ids no test? Verificar:
    raw_test = raw_df_split[raw_df_split["split"] == "test"]
    cnn_y_true = raw_test["algorithm"].map(label_map).to_numpy()
    if not np.array_equal(np.sort(cnn_y_true), np.sort(y_test)):
        print(f"  Aviso: ordem do test no CNN difere — ambos têm {len(y_test)} e {len(cnn_y_true)} amostras")
    # Para McNemar precisamos da MESMA ordem; usar sample_id como índice:
    feat_test_ids = test_df["sample_id"].tolist()
    raw_test_ids  = raw_test["sample_id"].tolist()
    if feat_test_ids != raw_test_ids:
        # Reordenar predições do CNN para casar com feat_test_ids
        idx_map = {sid: i for i, sid in enumerate(raw_test_ids)}
        try:
            cnn_perm = np.array([idx_map[sid] for sid in feat_test_ids])
            cnn_y_pred = res_b.y_pred[cnn_perm]
            cnn_y_proba = res_b.y_proba[cnn_perm]
        except KeyError:
            print("  Aviso: sample_ids não alinham entre features e raw — usando CNN como está")
            cnn_y_pred  = res_b.y_pred
            cnn_y_proba = res_b.y_proba
    else:
        cnn_y_pred  = res_b.y_pred
        cnn_y_proba = res_b.y_proba

    # 5. Tabela comparativa
    rows: list[list[str]] = []
    predictions: dict[str, dict] = {}
    for name, mres in res_a.models.items():
        m   = mres.metrics
        ci  = m.f1_macro_ci
        rows.append([
            name,
            str(len(res_a.selected_features)),
            f"{m.f1_macro:.4f}",
            f"[{ci[0]:.3f}, {ci[1]:.3f}]",
            f"{m.balanced_accuracy:.4f}",
            f"{mres.train_time_s:.1f}s",
        ])
        predictions[name] = {
            "y_pred":            mres.y_pred,
            "y_proba":           mres.y_proba,
            "confusion_matrix":  m.confusion_matrix.tolist(),
            "metrics_dict":      m.as_dict(),
        }

    cnn_ci = res_b.metrics.f1_macro_ci
    rows.append([
        "CNN 1D",
        "raw bytes",
        f"{res_b.metrics.f1_macro:.4f}",
        f"[{cnn_ci[0]:.3f}, {cnn_ci[1]:.3f}]",
        f"{res_b.metrics.balanced_accuracy:.4f}",
        f"{res_b.train_time_s:.1f}s",
    ])
    predictions["CNN 1D"] = {
        "y_pred":           cnn_y_pred,
        "y_proba":          cnn_y_proba,
        "confusion_matrix": res_b.metrics.confusion_matrix.tolist(),
        "metrics_dict":     res_b.metrics.as_dict(),
    }

    headers = ["Modelo", "Features", "F1-macro", "IC 95%", "Bal. Acc", "Tempo treino"]
    md_table = _format_table(rows, headers)

    # 6. McNemar entre todos os pares
    mcnemar_rows: list[list[str]] = []
    pair_results: list[dict] = []
    for a, b in combinations(predictions.keys(), 2):
        ya = predictions[a]["y_pred"]
        yb = predictions[b]["y_pred"]
        res = mcnemar_test(y_test, ya, yb)
        mcnemar_rows.append([
            f"{a} vs {b}",
            f"{res['statistic']:.3f}",
            f"{res['p_value']:.4g}",
            "sim" if res["significant"] else "nao",
        ])
        pair_results.append({"pair": (a, b), **res})

    mcnemar_md = _format_table(
        mcnemar_rows,
        ["Comparação", "estatística", "p-value", "Significativo?"],
    )

    # 7. Salvar artefatos
    print(f"\n--- Salvando artefatos em reports/ ---")

    results_payload = {
        "dataset":            "keyholdout_2class_v1",
        "n_test_samples":     int(len(y_test)),
        "label_map":          label_map,
        "selector": {
            "config":          {k: getattr(SELECTOR_CFG, k) for k in (
                "variance_threshold","top_k_mi","n_features_mrmr",
                "boruta_max_iter","random_state",
            )},
            "stage_report":    res_a.stage_report,
            "selected_features": res_a.selected_features,
        },
        "models": {
            **{name: {
                "metrics":      mres.metrics.as_dict(),
                "train_time_s": mres.train_time_s,
                "predict_time_s": mres.predict_time_s,
            } for name, mres in res_a.models.items()},
            "CNN 1D": {
                "metrics":      res_b.metrics.as_dict(),
                "train_time_s": res_b.train_time_s,
                "predict_time_s": res_b.predict_time_s,
                "best_epoch":   res_b.best_epoch,
            },
        },
        "mcnemar":            pair_results,
        "total_time_s":       round(t_a + t_b, 1),
    }
    (REPORTS_DIR / "experiment_2class_results.json").write_text(
        json.dumps(results_payload, indent=2, default=lambda x: x.tolist()
                   if hasattr(x, "tolist") else x),
        encoding="utf-8",
    )

    (REPORTS_DIR / "comparison_table.md").write_text(
        f"# Tabela comparativa — Ascon vs GIFT-COFB (key-holdout)\n\n{md_table}\n",
        encoding="utf-8",
    )
    (REPORTS_DIR / "mcnemar_table.md").write_text(
        f"# Teste de McNemar entre pares\n\n(alpha=0.05, "
        f"correção de continuidade ativa)\n\n{mcnemar_md}\n",
        encoding="utf-8",
    )
    (REPORTS_DIR / "selected_features.json").write_text(
        json.dumps({
            "n_selected":         len(res_a.selected_features),
            "stage_report":       res_a.stage_report,
            "selected_features":  res_a.selected_features,
        }, indent=2),
        encoding="utf-8",
    )
    (REPORTS_DIR / "cnn_history.json").write_text(
        json.dumps({
            "best_epoch": res_b.best_epoch,
            "history":    res_b.history,
        }, indent=2),
        encoding="utf-8",
    )

    label_names = [c for c, _ in sorted(label_map.items(), key=lambda kv: kv[1])]
    _save_confusion_matrices(predictions, label_names)

    print(f"\n{'='*70}\n  RESULTADOS\n{'='*70}")
    print(md_table)
    print(f"\n{mcnemar_md}\n")
    print(f"  Tempo total: {t_a + t_b:.1f}s")
    print(f"  Artefatos:   reports/experiment_2class_results.json")
    print(f"               reports/comparison_table.md")
    print(f"               reports/mcnemar_table.md")
    print(f"               reports/confusion_matrices/")


if __name__ == "__main__":
    main()
