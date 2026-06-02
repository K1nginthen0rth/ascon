"""
Gera tabela comparativa Fase 4B (15k) vs 4B-Extended (50k).

Le os JSONs gerados por scripts/run_experiment_2class.py para ambos os datasets
e produz reports/comparison_15k_vs_50k.md.
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PATH_15K = REPO / "reports" / "experiment_2class_results.json"
PATH_50K = REPO / "reports" / "keyholdout_2class_50k_v1" / "experiment_2class_results.json"
OUT      = REPO / "reports" / "comparison_15k_vs_50k.md"

ALL_MODELS = ["Dummy", "RF", "SVM", "XGBoost", "CNN 1D"]


def _fmt_ci(d: dict, key: str = "f1_macro") -> str:
    lo = d[f"{key}_ci_lower"]
    hi = d[f"{key}_ci_upper"]
    return f"[{lo:.3f}, {hi:.3f}]"


def _fmt_delta(a: float, b: float) -> str:
    delta = b - a
    sign  = "+" if delta >= 0 else ""
    return f"{sign}{delta:.4f}"


def _table(headers: list[str], rows: list[list[str]]) -> str:
    widths = [max(len(h), max((len(r[i]) for r in rows), default=0)) for i, h in enumerate(headers)]
    sep = "| " + " | ".join("-" * w for w in widths) + " |"
    out = ["| " + " | ".join(h.ljust(w) for h, w in zip(headers, widths)) + " |", sep]
    for r in rows:
        out.append("| " + " | ".join(str(c).ljust(w) for c, w in zip(r, widths)) + " |")
    return "\n".join(out)


def main() -> None:
    if not PATH_15K.exists():
        raise SystemExit(f"Falta: {PATH_15K}")
    if not PATH_50K.exists():
        raise SystemExit(f"Falta: {PATH_50K}")

    d15 = json.loads(PATH_15K.read_text(encoding="utf-8"))
    d50 = json.loads(PATH_50K.read_text(encoding="utf-8"))

    rows: list[list[str]] = []
    for name in ALL_MODELS:
        m15 = d15["models"][name]["metrics"]
        m50 = d50["models"][name]["metrics"]
        rows.append([
            name,
            f"{m15['f1_macro']:.4f}",
            _fmt_ci(m15),
            f"{m50['f1_macro']:.4f}",
            _fmt_ci(m50),
            _fmt_delta(m15["f1_macro"], m50["f1_macro"]),
        ])
    headers = ["Modelo", "F1 (15k)", "IC 95% (15k)", "F1 (50k)", "IC 95% (50k)", "Delta"]
    main_table = _table(headers, rows)

    # Tempos
    time_rows: list[list[str]] = []
    for name in ALL_MODELS:
        t15 = d15["models"][name].get("train_time_s", "—")
        t50 = d50["models"][name].get("train_time_s", "—")
        time_rows.append([name, f"{t15:.1f}s" if isinstance(t15, (int, float)) else t15,
                                f"{t50:.1f}s" if isinstance(t50, (int, float)) else t50])
    time_table = _table(["Modelo", "Tempo (15k)", "Tempo (50k)"], time_rows)

    # Boruta selection
    b15 = d15["selector"]["selected_features"]
    b50 = d50["selector"]["selected_features"]
    intersect = set(b15) & set(b50)
    only15    = set(b15) - set(b50)
    only50    = set(b50) - set(b15)

    # Tabela do seletor
    s15 = d15["selector"]["stage_report"]
    s50 = d50["selector"]["stage_report"]
    sel_table = _table(
        ["Estagio", "15k", "50k"],
        [
            ["entrada (VT->MI top-k)", str(s15["stage1_output"]),     str(s50["stage1_output"])],
            ["mRMR",                    str(s15["stage2_output"]),     str(s50["stage2_output"])],
            ["Boruta",                  str(s15["stage3_output"]),     str(s50["stage3_output"])],
            ["selector_fit_time_s",     f"{s15.get('selector_fit_time_s', 0):.1f}",
                                        f"{s50.get('selector_fit_time_s', 0):.1f}"],
        ],
    )

    # n_test
    nt15 = d15["n_test_samples"]
    nt50 = d50["n_test_samples"]

    md = [
        "# Replicacao 15k vs 50k - Fase 4B-Extended",
        "",
        f"- Dataset 15k: keyholdout_2class_v1 ({nt15:,} amostras de teste)",
        f"- Dataset 50k: keyholdout_2class_50k_v1 ({nt50:,} amostras de teste)",
        "",
        "## Tabela principal: F1-macro com IC bootstrap 95%",
        "",
        main_table,
        "",
        "## Pipeline de selecao",
        "",
        sel_table,
        "",
        f"**Features Boruta-validadas em comum:** {sorted(intersect) or 'nenhuma'}",
        f"**Apenas 15k:** {sorted(only15) or 'nenhuma'}",
        f"**Apenas 50k:** {sorted(only50) or 'nenhuma'}",
        "",
        "## Tempos de treino",
        "",
        time_table,
        "",
        f"Tempo total 15k: {d15.get('total_time_s', '?')}s",
        f"Tempo total 50k: {d50.get('total_time_s', '?')}s",
    ]

    OUT.write_text("\n".join(md), encoding="utf-8")
    print(f"Tabela salva em: {OUT.relative_to(REPO)}")
    print()
    print("\n".join(md))


if __name__ == "__main__":
    main()
