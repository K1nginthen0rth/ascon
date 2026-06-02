"""
Analise complementar dos controles positivos (A: corpus natural, B: repetitivo).

Roda 4 analises em sequencia:
  1. Caracterizacao dos plaintexts (entropia, % blocos repetidos, chi2, IC)
  2. Caracterizacao dos ciphertexts ECB e AEAD (mesmas metricas)
  3. Matrizes de confusao 3x3 (RF) reordenadas para Ascon/GIFT/ECB
  4. Indice de coincidencia para todos os grupos (PT + CT)

Saidas (reports/control_analysis/):
  plaintext_characterization.json
  ciphertext_characterization.json
  confusion_matrix_control_a.png
  confusion_matrix_control_b.png
  confusion_matrix_control_a.json
  confusion_matrix_control_b.json
  coincidence_index.json
  summary_table.md

Como rodar:
  python scripts/run_control_analysis.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Iterable

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

_REPO = Path(__file__).resolve().parent.parent
OUT_DIR = _REPO / "reports" / "control_analysis"

INTERIM = _REPO / "data" / "interim"
PROCESSED = _REPO / "data" / "processed"

PT_NATURAL = INTERIM / "control_3class_v1_plaintexts.parquet"
PT_REPETITIVE = INTERIM / "control_repetitive_3class_v1_plaintexts.parquet"

CT_NATURAL = PROCESSED / "control_3class_v1.parquet"
CT_REPETITIVE = PROCESSED / "control_repetitive_3class_v1.parquet"

RESULTS_NATURAL = _REPO / "reports" / "control_3class_v1" / "experiment_2class_results.json"
RESULTS_REPETITIVE = _REPO / "reports" / "control_repetitive_3class_v1" / "experiment_2class_results.json"

DISPLAY_ORDER = ["Ascon-AEAD128", "GIFT-COFB", "AES-128-ECB"]


# ---------- metrics ----------

def shannon_entropy(data: bytes) -> float:
    """Entropia de Shannon em bits/byte."""
    if not data:
        return 0.0
    counts = np.bincount(np.frombuffer(data, dtype=np.uint8), minlength=256).astype(np.float64)
    p = counts / counts.sum()
    nz = p[p > 0]
    return float(-np.sum(nz * np.log2(nz)))


def block_repetition_rate(data: bytes, block_size: int = 16) -> float:
    """Fracao de blocos de `block_size` bytes que aparecem mais de uma vez."""
    n = len(data) // block_size
    if n < 2:
        return 0.0
    blocks = [bytes(data[i * block_size:(i + 1) * block_size]) for i in range(n)]
    c = Counter(blocks)
    repeated = sum(cnt for cnt in c.values() if cnt > 1)
    return repeated / n


def chi_squared(data: bytes) -> float:
    """Chi2 contra distribuicao uniforme de bytes (df=255, esperado ~255)."""
    if not data:
        return 0.0
    counts = np.bincount(np.frombuffer(data, dtype=np.uint8), minlength=256).astype(np.float64)
    expected = len(data) / 256.0
    return float(np.sum((counts - expected) ** 2 / expected))


def index_of_coincidence(data: bytes) -> float:
    """IC = sum(n_i*(n_i-1)) / (N*(N-1)). Uniforme: 1/256 ~ 0.00391."""
    n = len(data)
    if n < 2:
        return 0.0
    counts = np.bincount(np.frombuffer(data, dtype=np.uint8), minlength=256).astype(np.float64)
    return float(np.sum(counts * (counts - 1)) / (n * (n - 1)))


def summarize(samples: Iterable[bytes]) -> dict:
    """Calcula metricas amostra a amostra e devolve media + std + n."""
    H, R, X, IC = [], [], [], []
    n = 0
    for b in samples:
        b = bytes(b)
        H.append(shannon_entropy(b))
        R.append(block_repetition_rate(b))
        X.append(chi_squared(b))
        IC.append(index_of_coincidence(b))
        n += 1
    H, R, X, IC = map(np.asarray, (H, R, X, IC))
    return {
        "n": int(n),
        "entropy_bits_per_byte": {"mean": float(H.mean()), "std": float(H.std())},
        "block_rep_rate_16B":    {"mean": float(R.mean()), "std": float(R.std())},
        "chi_squared":           {"mean": float(X.mean()), "std": float(X.std())},
        "index_of_coincidence":  {"mean": float(IC.mean()), "std": float(IC.std())},
    }


# ---------- I/O ----------

def load_plaintexts(path: Path) -> list[bytes]:
    df = pd.read_parquet(path)
    return df["plaintext"].tolist()


def load_ciphertexts(path: Path, algorithm: str) -> list[bytes]:
    df = pd.read_parquet(path, columns=["algorithm", "ciphertext"])
    return df.loc[df["algorithm"] == algorithm, "ciphertext"].tolist()


# ---------- confusion matrix ----------

def reorder_cm(cm: np.ndarray, label_map: dict[str, int], target: list[str]) -> tuple[np.ndarray, list[str]]:
    """Reordena CM (linhas+colunas) para a ordem `target`."""
    idx = [label_map[lbl] for lbl in target]
    cm2 = cm[np.ix_(idx, idx)]
    return cm2, target


def metrics_per_class(cm: np.ndarray, labels: list[str]) -> dict:
    out = {}
    tot = cm.sum()
    for i, lbl in enumerate(labels):
        tp = cm[i, i]
        fn = cm[i, :].sum() - tp
        fp = cm[:, i].sum() - tp
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall    = tp / (tp + fn) if (tp + fn) else 0.0
        f1        = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        out[lbl] = {
            "tp": int(tp), "fn": int(fn), "fp": int(fp),
            "precision": float(precision),
            "recall":    float(recall),
            "f1":        float(f1),
        }
    out["accuracy"] = float(np.trace(cm) / tot) if tot else 0.0
    return out


def plot_cm(cm: np.ndarray, labels: list[str], title: str, out_png: Path) -> None:
    fig, ax = plt.subplots(figsize=(5, 4.5))
    im = ax.imshow(cm, cmap="Blues")
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            v = int(cm[i, j])
            color = "white" if v > cm.max() * 0.55 else "black"
            ax.text(j, i, str(v), ha="center", va="center", color=color, fontsize=12)
    ax.set_xticks(range(len(labels)))
    ax.set_yticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=15)
    ax.set_yticklabels(labels)
    ax.set_xlabel("Predito")
    ax.set_ylabel("Real")
    ax.set_title(title)
    plt.colorbar(im, ax=ax)
    fig.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=130)
    plt.close(fig)


# ---------- analyses ----------

def analyse_plaintexts() -> dict:
    print("\n[1/4] Caracterizacao dos plaintexts")
    out: dict = {}
    for name, path in [("natural", PT_NATURAL), ("repetitivo", PT_REPETITIVE)]:
        print(f"  - {name}: lendo {path.name}")
        pts = load_plaintexts(path)
        out[name] = summarize(pts)
        print(f"      n={out[name]['n']}, H={out[name]['entropy_bits_per_byte']['mean']:.3f} "
              f"bits/byte, rep={out[name]['block_rep_rate_16B']['mean']*100:.2f}%, "
              f"chi2={out[name]['chi_squared']['mean']:.2f}, "
              f"IC={out[name]['index_of_coincidence']['mean']:.5f}")
    return out


def analyse_ciphertexts() -> dict:
    print("\n[2/4] Caracterizacao dos ciphertexts")
    out: dict = {}
    pairs = [
        ("Ascon (natural)",    CT_NATURAL,    "Ascon-AEAD128"),
        ("GIFT-COFB (natural)", CT_NATURAL,    "GIFT-COFB"),
        ("AES-ECB (natural)",   CT_NATURAL,    "AES-128-ECB"),
        ("Ascon (repetitivo)",  CT_REPETITIVE, "Ascon-AEAD128"),
        ("GIFT-COFB (repetitivo)", CT_REPETITIVE, "GIFT-COFB"),
        ("AES-ECB (repetitivo)",   CT_REPETITIVE, "AES-128-ECB"),
    ]
    for label, path, algo in pairs:
        print(f"  - {label}: lendo de {path.name}")
        cts = load_ciphertexts(path, algo)
        out[label] = summarize(cts)
        print(f"      n={out[label]['n']}, H={out[label]['entropy_bits_per_byte']['mean']:.3f}, "
              f"rep={out[label]['block_rep_rate_16B']['mean']*100:.2f}%, "
              f"chi2={out[label]['chi_squared']['mean']:.2f}, "
              f"IC={out[label]['index_of_coincidence']['mean']:.5f}")
    return out


def analyse_confusion_matrices() -> dict:
    print("\n[3/4] Matrizes de confusao (RF, 3x3 reordenadas)")
    out: dict = {}
    for tag, results_path, png_name in [
        ("control_a", RESULTS_NATURAL,    "confusion_matrix_control_a.png"),
        ("control_b", RESULTS_REPETITIVE, "confusion_matrix_control_b.png"),
    ]:
        data = json.loads(results_path.read_text(encoding="utf-8"))
        label_map = data["label_map"]
        rf = data["models"]["RF"]
        cm_raw = np.asarray(rf["metrics"]["confusion_matrix"])
        cm, labels = reorder_cm(cm_raw, label_map, DISPLAY_ORDER)
        f1_macro = float(rf["metrics"]["f1_macro"])
        per_cls = metrics_per_class(cm, labels)
        title = (f"{'Controle A (natural)' if tag == 'control_a' else 'Controle B (repetitivo)'}"
                 f" - RF, F1-macro={f1_macro:.4f}")
        plot_cm(cm, labels, title, OUT_DIR / png_name)
        out[tag] = {
            "labels": labels,
            "f1_macro": f1_macro,
            "confusion_matrix": cm.tolist(),
            "per_class": per_cls,
        }
        print(f"  - {tag}: F1-macro={f1_macro:.4f}, "
              f"ECB precision={per_cls['AES-128-ECB']['precision']:.4f}, "
              f"ECB recall={per_cls['AES-128-ECB']['recall']:.4f}")
        (OUT_DIR / png_name).with_suffix(".json").write_text(
            json.dumps(out[tag], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    return out


def analyse_coincidence_index(pt_stats: dict, ct_stats: dict) -> dict:
    """Apenas reexpoe o IC ja calculado, agrupado pela visao pedida pelo orientador."""
    print("\n[4/4] Indice de coincidencia (consolidando)")
    rows = {
        "PT natural":        pt_stats["natural"]["index_of_coincidence"],
        "PT repetitivo":     pt_stats["repetitivo"]["index_of_coincidence"],
        "CT Ascon (natural)":     ct_stats["Ascon (natural)"]["index_of_coincidence"],
        "CT GIFT-COFB (natural)": ct_stats["GIFT-COFB (natural)"]["index_of_coincidence"],
        "CT AES-ECB (natural)":   ct_stats["AES-ECB (natural)"]["index_of_coincidence"],
        "CT AES-ECB (repetitivo)": ct_stats["AES-ECB (repetitivo)"]["index_of_coincidence"],
        "CT Ascon (repetitivo)":   ct_stats["Ascon (repetitivo)"]["index_of_coincidence"],
        "CT GIFT-COFB (repetitivo)": ct_stats["GIFT-COFB (repetitivo)"]["index_of_coincidence"],
    }
    out = {"uniform_reference": 1 / 256.0, "rows": rows}
    for k, v in rows.items():
        print(f"  - {k}: IC={v['mean']:.6f}")
    return out


# ---------- summary table ----------

def _fmt(x: float, p: int = 4) -> str:
    return f"{x:.{p}f}"


def write_summary_table(pt: dict, ct: dict, cms: dict, ic: dict) -> Path:
    lines: list[str] = []
    lines.append("# Caracterizacao dos controles positivos (A: natural, B: repetitivo)")
    lines.append("")
    lines.append("Todas as metricas sao medias amostra-a-amostra. n = numero de amostras.")
    lines.append("")

    # PT
    lines.append("## Caracterizacao dos plaintexts")
    lines.append("")
    lines.append("| Corpus      | n     | Entropia (bits/byte) | % Blocos 16B Repetidos | chi2 medio | IC medio |")
    lines.append("|-------------|-------|----------------------|------------------------|------------|----------|")
    for name in ("natural", "repetitivo"):
        s = pt[name]
        lines.append(
            f"| {name:<11} | {s['n']:>5} | "
            f"{_fmt(s['entropy_bits_per_byte']['mean'], 3)} | "
            f"{_fmt(s['block_rep_rate_16B']['mean']*100, 2)}% | "
            f"{_fmt(s['chi_squared']['mean'], 2)} | "
            f"{_fmt(s['index_of_coincidence']['mean'], 5)} |"
        )
    lines.append("")

    # CT
    lines.append("## Caracterizacao dos ciphertexts")
    lines.append("")
    lines.append("| Algoritmo / Corpus PT      | n     | Entropia (bits/byte) | % Blocos CT 16B Repetidos | chi2 medio | IC medio |")
    lines.append("|----------------------------|-------|----------------------|---------------------------|------------|----------|")
    order = [
        "Ascon (natural)", "GIFT-COFB (natural)", "AES-ECB (natural)",
        "Ascon (repetitivo)", "GIFT-COFB (repetitivo)", "AES-ECB (repetitivo)",
    ]
    for k in order:
        s = ct[k]
        lines.append(
            f"| {k:<26} | {s['n']:>5} | "
            f"{_fmt(s['entropy_bits_per_byte']['mean'], 3)} | "
            f"{_fmt(s['block_rep_rate_16B']['mean']*100, 2)}% | "
            f"{_fmt(s['chi_squared']['mean'], 2)} | "
            f"{_fmt(s['index_of_coincidence']['mean'], 5)} |"
        )
    lines.append("")

    # IC reference
    lines.append("## Indice de coincidencia - referencia")
    lines.append("")
    lines.append(f"- Uniforme (esperado para CT seguro): 1/256 = {1/256:.6f}")
    lines.append("- Portugues/ingles textual: ~0.06 - 0.07")
    lines.append("")

    # Confusion matrices
    lines.append("## Matrizes de confusao (Random Forest)")
    lines.append("")
    for tag, label in [("control_a", "Controle A (corpus natural)"),
                        ("control_b", "Controle B (corpus repetitivo)")]:
        c = cms[tag]
        cm = np.asarray(c["confusion_matrix"])
        labels = c["labels"]
        lines.append(f"### {label} - F1-macro = {c['f1_macro']:.4f}")
        lines.append("")
        header = "| Real \\ Predito | " + " | ".join(labels) + " |"
        sep    = "|" + "----|" * (len(labels) + 1)
        lines.append(header)
        lines.append(sep)
        for i, row_lbl in enumerate(labels):
            cells = " | ".join(str(int(v)) for v in cm[i])
            lines.append(f"| {row_lbl} | {cells} |")
        lines.append("")
        ecb = c["per_class"]["AES-128-ECB"]
        lines.append(f"- ECB: precision={ecb['precision']:.4f}, recall={ecb['recall']:.4f}, f1={ecb['f1']:.4f}")
        lines.append(f"- Acuracia global: {c['per_class']['accuracy']:.4f}")
        lines.append("")

    # Interpretacao
    pt_nat_rep  = pt["natural"]["block_rep_rate_16B"]["mean"] * 100
    pt_rep_rep  = pt["repetitivo"]["block_rep_rate_16B"]["mean"] * 100
    ct_ecb_nat_rep = ct["AES-ECB (natural)"]["block_rep_rate_16B"]["mean"] * 100
    ct_ecb_rep_rep = ct["AES-ECB (repetitivo)"]["block_rep_rate_16B"]["mean"] * 100
    ct_ascon_nat = ct["Ascon (natural)"]["block_rep_rate_16B"]["mean"] * 100
    ct_ascon_rep = ct["Ascon (repetitivo)"]["block_rep_rate_16B"]["mean"] * 100
    ct_gift_nat = ct["GIFT-COFB (natural)"]["block_rep_rate_16B"]["mean"] * 100
    ct_gift_rep = ct["GIFT-COFB (repetitivo)"]["block_rep_rate_16B"]["mean"] * 100

    lines.append("## Interpretacao")
    lines.append("")
    lines.append(
        f"- **Texto natural** tem repeticao de blocos de 16B em ~{pt_nat_rep:.2f}% dos blocos. "
        f"ECB sobre esse PT produz repeticao no CT em ~{ct_ecb_nat_rep:.2f}% dos blocos. "
        f"Esse sinal residual explica F1={cms['control_a']['f1_macro']:.2f} no Controle A "
        f"(ECB recall={cms['control_a']['per_class']['AES-128-ECB']['recall']:.2%})."
    )
    lines.append(
        f"- **Texto repetitivo** tem ~{pt_rep_rep:.2f}% blocos repetidos. "
        f"ECB preserva integralmente esse sinal: CT tem ~{ct_ecb_rep_rep:.2f}% blocos repetidos. "
        f"O classificador identifica ECB com F1={cms['control_b']['per_class']['AES-128-ECB']['f1']:.4f} "
        f"(recall {cms['control_b']['per_class']['AES-128-ECB']['recall']:.2%})."
    )
    lines.append(
        f"- **Ascon e GIFT-COFB** mascaram qualquer padrao: CT tem repeticao "
        f"~{ct_ascon_nat:.2f}% (Ascon nat) / ~{ct_ascon_rep:.2f}% (Ascon rep) / "
        f"~{ct_gift_nat:.2f}% (GIFT nat) / ~{ct_gift_rep:.2f}% (GIFT rep). "
        f"IC ~ 1/256 e chi2 ~ 255 em todos os cenarios => indistinguiveis "
        f"(corroborado pelos F1 dos 2-classes Ascon vs GIFT no IC do acaso)."
    )
    lines.append("")

    out_path = OUT_DIR / "summary_table.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


# ---------- main ----------

def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    pt_stats = analyse_plaintexts()
    (OUT_DIR / "plaintext_characterization.json").write_text(
        json.dumps(pt_stats, indent=2, ensure_ascii=False), encoding="utf-8")

    ct_stats = analyse_ciphertexts()
    (OUT_DIR / "ciphertext_characterization.json").write_text(
        json.dumps(ct_stats, indent=2, ensure_ascii=False), encoding="utf-8")

    cm_stats = analyse_confusion_matrices()

    ic_stats = analyse_coincidence_index(pt_stats, ct_stats)
    (OUT_DIR / "coincidence_index.json").write_text(
        json.dumps(ic_stats, indent=2, ensure_ascii=False), encoding="utf-8")

    summary = write_summary_table(pt_stats, ct_stats, cm_stats, ic_stats)
    print(f"\nResumo consolidado: {summary.relative_to(_REPO)}")
    print(f"Todos os artefatos em: {OUT_DIR.relative_to(_REPO)}/")


if __name__ == "__main__":
    main()
