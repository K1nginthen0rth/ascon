"""Gera as matrizes de confusao em PNG a partir do experiment_2class_results.json salvo."""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parent.parent
RESULTS = REPO / "reports" / "experiment_2class_results.json"
CM_DIR  = REPO / "reports" / "confusion_matrices"
CM_DIR.mkdir(parents=True, exist_ok=True)

data = json.loads(RESULTS.read_text(encoding="utf-8"))
label_map = data["label_map"]
label_names = [c for c, _ in sorted(label_map.items(), key=lambda kv: kv[1])]

for name, payload in data["models"].items():
    cm = np.asarray(payload["metrics"]["confusion_matrix"])
    fig, ax = plt.subplots(figsize=(4, 4))
    im = ax.imshow(cm, cmap="Blues")
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            ax.text(j, i, str(int(cm[i, j])), ha="center", va="center",
                    color="black", fontsize=11)
    ax.set_xticks(range(len(label_names)))
    ax.set_yticks(range(len(label_names)))
    ax.set_xticklabels(label_names, rotation=15)
    ax.set_yticklabels(label_names)
    ax.set_xlabel("Predito"); ax.set_ylabel("Verdadeiro")
    f1 = payload["metrics"]["f1_macro"]
    ax.set_title(f"{name}  F1={f1:.4f}")
    plt.colorbar(im, ax=ax)
    fig.tight_layout()
    safe = name.replace(" ", "_").replace("/", "_")
    out = CM_DIR / f"{safe}.png"
    fig.savefig(out, dpi=120)
    plt.close(fig)
    print(f"  Salvo: {out.relative_to(REPO)}")

print(f"\nTotal: {len(data['models'])} matrizes em {CM_DIR.relative_to(REPO)}/")
