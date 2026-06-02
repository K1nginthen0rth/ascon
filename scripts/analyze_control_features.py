"""
Analisa features selecionadas pelo Boruta no controle positivo (3-classes).

Carrega:
  - reports/control_3class_v1/_caminho_a.pkl  (cache do ClassicalPipeline)
  - reports/keyholdout_2class_50k_v1/_caminho_a.pkl (caso 50k para comparacao)

Produz:
  reports/control_3class_v1/feature_analysis.md
   - Lista completa Boruta para o controle
   - Top-10 features por importancia do RF (Gini)
   - Comparacao com Boruta de 15k e 50k Ascon-vs-GIFT
"""
from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

import numpy as np
import pandas as pd

CONTROL_PKL  = _REPO / "reports" / "control_3class_v1"        / "_caminho_a.pkl"
RESULTS_50K  = _REPO / "reports" / "keyholdout_2class_50k_v1" / "experiment_2class_results.json"
RESULTS_15K  = _REPO / "reports"                              / "experiment_2class_results.json"
OUT          = _REPO / "reports" / "control_3class_v1"        / "feature_analysis.md"

FEATURES_PARQUET = _REPO / "data" / "processed" / "control_3class_v1_features.parquet"


def _table(headers, rows):
    widths = [max(len(h), max((len(str(r[i])) for r in rows), default=0))
              for i, h in enumerate(headers)]
    sep = "| " + " | ".join("-" * w for w in widths) + " |"
    out = ["| " + " | ".join(h.ljust(w) for h, w in zip(headers, widths)) + " |", sep]
    for r in rows:
        out.append("| " + " | ".join(str(c).ljust(w) for c, w in zip(r, widths)) + " |")
    return "\n".join(out)


def main() -> None:
    if not CONTROL_PKL.exists():
        raise SystemExit(f"Falta cache do controle: {CONTROL_PKL}")

    with CONTROL_PKL.open("rb") as f:
        res_a, t_a = pickle.load(f)

    selected = res_a.selected_features
    stage    = res_a.stage_report
    print(f"Controle 3-classes:")
    print(f"  Boruta validou {len(selected)}/{stage['stage1_input']} features")
    print(f"  Estagios: VT={stage['stage1_after_variance']}, "
          f"MI={stage['stage1_output']}, mRMR={stage['stage2_output']}, "
          f"Boruta={stage['stage3_output']}")

    # Top-10 RF importance (Gini) no conjunto de features pos-Boruta
    rf_result = res_a.models.get("RF")
    if rf_result is None:
        raise SystemExit("RF nao encontrado em res_a.models")

    # Importancias do RF: precisamos do modelo treinado, que NAO esta cacheado
    # diretamente em ModelResult. Vamos retreinar rapido sobre as features
    # selecionadas para obter feature_importances_.
    print(f"\n  Re-treinando RF para obter importancias...")
    df       = pd.read_parquet(FEATURES_PARQUET)
    raw_df   = pd.read_parquet(_REPO / "data/processed/control_3class_v1.parquet")
    if "split" not in df.columns:
        df = df.merge(raw_df[["sample_id", "split"]], on="sample_id",
                       how="left", validate="one_to_one")
    META = {"sample_id","algorithm","key_id","nonce_id","len_pt","len_ad",
            "len_ct","split","mode","impl","plaintext_source","seed",
            "version","timestamp","ciphertext"}

    train_df = df[df["split"] == "train"]
    classes  = sorted(df["algorithm"].unique().tolist())
    label_map = {c: i for i, c in enumerate(classes)}
    y_train  = train_df["algorithm"].map(label_map).to_numpy()

    X_train_full = np.asarray(
        train_df.drop(columns=[c for c in df.columns if c in META]).to_numpy(),
        dtype=np.float64,
    ).copy()
    np.nan_to_num(X_train_full, copy=False, nan=0.0)
    full_cols = [c for c in df.columns if c not in META]

    # Subset apenas pelas features selecionadas
    sel_idx = [full_cols.index(s) for s in selected]
    X_train_sel = X_train_full[:, sel_idx]

    from sklearn.ensemble import RandomForestClassifier
    rf = RandomForestClassifier(
        n_estimators=500, max_depth=None, class_weight="balanced",
        random_state=7, n_jobs=-1,
    ).fit(X_train_sel, y_train)
    importances = rf.feature_importances_
    top_idx = np.argsort(importances)[::-1]
    top10 = [(selected[i], float(importances[i])) for i in top_idx[:10]]

    # Comparacao com runs anteriores
    sel_15k = []
    sel_50k = []
    if RESULTS_15K.exists():
        sel_15k = json.loads(RESULTS_15K.read_text(encoding="utf-8"))[
            "selector"]["selected_features"]
    if RESULTS_50K.exists():
        sel_50k = json.loads(RESULTS_50K.read_text(encoding="utf-8"))[
            "selector"]["selected_features"]

    sel_set = set(selected)
    s15 = set(sel_15k); s50 = set(sel_50k)
    in_control_only = sel_set - (s15 | s50)
    in_all_three    = sel_set & s15 & s50
    in_both_50_ctrl = sel_set & s50

    # Markdown
    md = []
    md.append("# Analise de features - controle positivo 3-classes")
    md.append("")
    md.append(f"Dataset: control_3class_v1 ({len(df):,} amostras)")
    md.append(f"Splits: train={stage.get('train_n','?')}, "
              f"sel_fit_time={stage.get('selector_fit_time_s', '?')}s")
    md.append("")
    md.append("## Pipeline de selecao")
    md.append("")
    md.append(_table(
        ["Estagio", "Saida"],
        [["Entrada (307)",                    str(stage["stage1_input"])],
         ["VarianceThreshold (1e-5)",         str(stage["stage1_after_variance"])],
         ["MI top-k (200)",                   str(stage["stage1_output"])],
         ["mRMR (100)",                       str(stage["stage2_output"])],
         ["Boruta validate",                  str(stage["stage3_output"])]],
    ))
    md.append("")

    md.append(f"**{len(selected)} features validadas pelo Boruta** "
              f"(esperado >> 1 se pipeline funciona).")
    md.append("")

    md.append("## Top-10 por importancia Gini do RF")
    md.append("")
    md.append(_table(
        ["Feature", "Importancia"],
        [[name, f"{imp:.4f}"] for name, imp in top10],
    ))
    md.append("")

    md.append("## Lista completa Boruta-validada")
    md.append("")
    md.append("```")
    for s in selected:
        md.append(s)
    md.append("```")
    md.append("")

    md.append("## Comparacao com Ascon vs GIFT-COFB")
    md.append("")
    md.append(_table(
        ["Conjunto", "n features"],
        [["Boruta 15k Ascon-vs-GIFT",   str(len(s15))],
         ["Boruta 50k Ascon-vs-GIFT",   str(len(s50))],
         ["Boruta controle 3-classes",  str(len(sel_set))],
         ["intersect (todos os 3)",      str(len(in_all_three))],
         ["intersect (50k & controle)",  str(len(in_both_50_ctrl))],
         ["apenas controle",             str(len(in_control_only))]],
    ))
    md.append("")
    md.append("**Features que aparecem APENAS no controle positivo (distinguem ECB):**")
    md.append("")
    md.append("```")
    for f in sorted(in_control_only):
        md.append(f)
    md.append("```")
    md.append("")
    md.append("Estas sao as features que respondem por sinal estrutural detectavel "
              "(ECB vs AEAD). Como nao aparecem nas runs Ascon-vs-GIFT, nao ajudam "
              "a distinguir AEADs entre si.")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(md), encoding="utf-8")
    print(f"\nSalvo: {OUT.relative_to(_REPO)}")


if __name__ == "__main__":
    main()
