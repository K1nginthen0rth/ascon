"""
Roda CNN 2D em dois datasets (mesmos splits dos experimentos anteriores):
  1. keyholdout_2class_v1            (Ascon vs GIFT-COFB, 15k)
  2. control_repetitive_3class_v1    (3-class com ECB+PT repetitivo)

Filosofia idêntica aos outros experimentos:
  - sem tuning de hiperparâmetros
  - seeds: modelo=7, bootstrap=42, image_size=32 fixo
  - mesmo protocolo de split (key-holdout via coluna 'split')

Saídas (reports/<dataset_id>/cnn2d/):
  cnn2d_results.json
  cnn2d_history.json
  confusion_matrix.png
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import numpy as np
import pandas as pd

from src.models.cnn2d_trainer import CNN2DTrainer

# ---------------------------------------------------------------------------
# Datasets
# ---------------------------------------------------------------------------
DATASETS = [
    {
        "id":            "keyholdout_2class_v1",
        "label":         "Ascon vs GIFT-COFB (15k)",
        "n_classes":     2,
        "chance":        0.500,
    },
    {
        "id":            "control_repetitive_3class_v1",
        "label":         "Controle B: 3-class c/ ECB + PT repetitivo",
        "n_classes":     3,
        "chance":        0.333,
    },
]

N_BOOTSTRAP = 1000


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


def _save_confusion_matrix(cm: np.ndarray, label_names: list[str], out_path: Path) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("  matplotlib indisponível — pulando matriz em PNG.")
        return
    fig, ax = plt.subplots(figsize=(4, 4))
    im = ax.imshow(cm, cmap="Blues")
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            ax.text(j, i, str(int(cm[i, j])),
                    ha="center", va="center", color="black")
    ax.set_xticks(range(len(label_names))); ax.set_yticks(range(len(label_names)))
    ax.set_xticklabels(label_names); ax.set_yticklabels(label_names)
    ax.set_xlabel("Predito"); ax.set_ylabel("Verdadeiro")
    ax.set_title("CNN 2D — Matriz de confusão")
    plt.colorbar(im, ax=ax)
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def run_one(ds_cfg: dict) -> dict:
    ds_id = ds_cfg["id"]
    raw_path = REPO_ROOT / "data" / "processed" / f"{ds_id}.parquet"

    out_dir = REPO_ROOT / "reports" / ds_id / "cnn2d"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*70}")
    print(f"  CNN 2D — {ds_cfg['label']}")
    print(f"  Dataset: {raw_path.relative_to(REPO_ROOT)}")
    print(f"  Esperado (chance): {ds_cfg['chance']:.3f}")
    print(f"{'='*70}")

    raw_df = pd.read_parquet(raw_path)
    _verify_key_holdout(raw_df)
    print(f"  N={len(raw_df)}, classes={sorted(raw_df['algorithm'].unique().tolist())}")

    trainer = CNN2DTrainer(
        image_size=32, batch_size=64, n_epochs=30, lr=1e-3, patience=5,
        seed=7, n_bootstrap=N_BOOTSTRAP, seed_bootstrap=42,
    )
    t_start = time.perf_counter()
    res = trainer.train(raw_df, verbose=True)
    t_total = time.perf_counter() - t_start
    print(f"  Total: {t_total:.1f}s  (best epoch: {res.best_epoch})")
    print(f"  F1-macro: {res.metrics.f1_macro:.4f}  IC95% "
          f"[{res.metrics.f1_macro_ci[0]:.3f}, {res.metrics.f1_macro_ci[1]:.3f}]")

    # Salvar artefatos
    classes = sorted(raw_df["algorithm"].unique().tolist())
    label_map = {c: i for i, c in enumerate(classes)}

    payload = {
        "dataset":          ds_id,
        "label":            ds_cfg["label"],
        "n_classes":        ds_cfg["n_classes"],
        "chance":           ds_cfg["chance"],
        "label_map":        label_map,
        "image_size":       trainer.image_size,
        "batch_size":       trainer.batch_size,
        "n_epochs_max":     trainer.n_epochs,
        "lr":               trainer.lr,
        "patience":         trainer.patience,
        "seed":             trainer.seed,
        "best_epoch":       res.best_epoch,
        "metrics":          res.metrics.as_dict(),
        "train_time_s":     res.train_time_s,
        "predict_time_s":   res.predict_time_s,
        "total_time_s":     round(t_total, 1),
    }
    (out_dir / "cnn2d_results.json").write_text(
        json.dumps(payload, indent=2, default=lambda x: x.tolist()
                   if hasattr(x, "tolist") else x),
        encoding="utf-8",
    )
    (out_dir / "cnn2d_history.json").write_text(
        json.dumps({"best_epoch": res.best_epoch, "history": res.history}, indent=2),
        encoding="utf-8",
    )
    label_names = [c for c, _ in sorted(label_map.items(), key=lambda kv: kv[1])]
    _save_confusion_matrix(res.metrics.confusion_matrix,
                           label_names, out_dir / "confusion_matrix.png")
    print(f"  Artefatos: {out_dir.relative_to(REPO_ROOT)}")
    return payload


def main() -> None:
    summaries = []
    for ds_cfg in DATASETS:
        summaries.append(run_one(ds_cfg))

    # Tabela resumo
    print(f"\n{'='*70}\n  RESUMO — CNN 2D nos dois datasets\n{'='*70}")
    print(f"{'Dataset':<45} {'F1-macro':<10} {'IC 95%':<22} {'Bal. Acc'}")
    for s in summaries:
        m = s["metrics"]
        ci = (m["f1_macro_ci_lower"], m["f1_macro_ci_upper"])
        print(f"{s['label']:<45} {m['f1_macro']:<10.4f} "
              f"[{ci[0]:.3f}, {ci[1]:.3f}]      {m['balanced_accuracy']:.4f}")


if __name__ == "__main__":
    main()
