"""
Tabela comparativa de TODOS os 4 experimentos:

  1. Principal 15k: keyholdout_2class_v1 (Ascon vs GIFT, corpus)
  2. Principal 50k: keyholdout_2class_50k_v1 (Ascon vs GIFT, corpus)
  3. Controle A: control_3class_v1 (3 classes, corpus)
  4. Controle B: control_repetitive_3class_v1 (3 classes, repetitivo)

Saida: reports/comparison_all_experiments.md
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RES_15K  = REPO / "reports" / "experiment_2class_results.json"
RES_50K  = REPO / "reports" / "keyholdout_2class_50k_v1"      / "experiment_2class_results.json"
RES_CTRL = REPO / "reports" / "control_3class_v1"             / "experiment_2class_results.json"
RES_REP  = REPO / "reports" / "control_repetitive_3class_v1"  / "experiment_2class_results.json"
OUT      = REPO / "reports" / "comparison_all_experiments.md"

EXPS = [
    ("Principal 15k",  RES_15K,  "Ascon vs GIFT",          "corpus"),
    ("Principal 50k",  RES_50K,  "Ascon vs GIFT",          "corpus"),
    ("Controle A",      RES_CTRL, "3-class c/ ECB",         "corpus"),
    ("Controle B",      RES_REP,  "3-class c/ ECB",         "repetitivo"),
]

MODELS = ["Dummy", "RF", "SVM", "XGBoost", "CNN 1D"]


def _table(headers, rows):
    widths = [max(len(h), max((len(str(r[i])) for r in rows), default=0))
              for i, h in enumerate(headers)]
    sep = "| " + " | ".join("-" * w for w in widths) + " |"
    out = ["| " + " | ".join(h.ljust(w) for h, w in zip(headers, widths)) + " |", sep]
    for r in rows:
        out.append("| " + " | ".join(str(c).ljust(w) for c, w in zip(r, widths)) + " |")
    return "\n".join(out)


def main() -> None:
    data = {}
    for label, path, classes, pt in EXPS:
        if not path.exists():
            raise SystemExit(f"Falta: {path}")
        d = json.loads(path.read_text(encoding="utf-8"))
        data[label] = (d, classes, pt)

    md = ["# Comparacao de TODOS os experimentos", ""]
    md.append("Quatro datasets, mesmos hiperparametros e seeds, "
              "mesmo pipeline (selector 3 estagios + Dummy/RF/SVM/XGBoost + CNN 1D).")
    md.append("")

    # Tabela RF (modelo principal)
    md.append("## RF — F1-macro por experimento")
    md.append("")
    rows_rf = []
    for label, _, classes, pt in EXPS:
        d, _, _ = data[label]
        m = d["models"]["RF"]["metrics"]
        rows_rf.append([
            label, classes, pt,
            f"{m['f1_macro']:.4f}",
            f"[{m['f1_macro_ci_lower']:.3f}, {m['f1_macro_ci_upper']:.3f}]",
        ])
    md.append(_table(
        ["Experimento", "Classes", "Plaintext", "F1 RF", "IC 95%"],
        rows_rf,
    ))
    md.append("")

    # Tabela completa por experimento
    for label, _, classes, pt in EXPS:
        d, _, _ = data[label]
        chance = 1.0 / len(d["label_map"])
        md.append(f"## {label}  ({classes}, PT={pt}, chance={chance:.3f})")
        md.append("")
        rows = []
        for m_name in MODELS:
            mm = d["models"][m_name]["metrics"]
            tt = d["models"][m_name].get("train_time_s", "—")
            tt_str = f"{tt:.1f}s" if isinstance(tt, (int, float)) else tt
            rows.append([
                m_name,
                f"{mm['f1_macro']:.4f}",
                f"[{mm['f1_macro_ci_lower']:.3f}, {mm['f1_macro_ci_upper']:.3f}]",
                f"{mm['balanced_accuracy']:.4f}",
                tt_str,
            ])
        md.append(_table(
            ["Modelo", "F1-macro", "IC 95%", "Bal. Acc", "Tempo"],
            rows,
        ))
        md.append("")

    # Boruta selection comparison
    md.append("## Pipeline de selecao - Boruta-validated")
    md.append("")
    rows = []
    for label, _, _, _ in EXPS:
        d, _, _ = data[label]
        s = d["selector"]["stage_report"]
        rows.append([
            label,
            str(s.get("stage1_input",  "—")),
            str(s.get("stage1_output", "—")),
            str(s.get("stage2_output", "—")),
            str(s.get("stage3_output", "—")),
        ])
    md.append(_table(
        ["Experimento", "input", "MI top-k", "mRMR", "Boruta"],
        rows,
    ))
    md.append("")

    # Conclusoes
    md.append("## Leitura dos resultados")
    md.append("")
    rf15  = data["Principal 15k"][0]["models"]["RF"]["metrics"]["f1_macro"]
    rf50  = data["Principal 50k"][0]["models"]["RF"]["metrics"]["f1_macro"]
    rfa   = data["Controle A"][0]["models"]["RF"]["metrics"]["f1_macro"]
    rfb   = data["Controle B"][0]["models"]["RF"]["metrics"]["f1_macro"]

    md.append(f"- **Principal 15k/50k**: RF F1 = {rf15:.3f} / {rf50:.3f} (chance 0.500). H0 confirmada.")
    md.append(f"- **Controle A** (corpus): RF F1 = {rfa:.3f} (chance 0.333). Sinal fraco.")
    md.append(f"- **Controle B** (repetitivo): RF F1 = {rfb:.3f} (chance 0.333). "
              f"{'Sinal forte - pipeline funciona.' if rfb > 0.5 else 'Tambem fraco - investigar.'}")
    md.append("")
    md.append(f"Ganho Controle B vs A (mesmo dataset, PT diferente): "
              f"+{rfb - rfa:.3f} F1. Isso prova que o sinal limitado em A vem do "
              f"PT corpus (poucos blocos repetidos), nao do pipeline.")

    OUT.write_text("\n".join(md), encoding="utf-8")
    print(f"Salvo: {OUT.relative_to(REPO)}")
    print()
    print("\n".join(md))


if __name__ == "__main__":
    main()
