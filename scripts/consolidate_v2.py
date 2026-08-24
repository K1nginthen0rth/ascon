"""
Consolidação do experimento v2 — Fase 11. Ver
docs/plano_experimento_v2/06_implementacao_passo_a_passo.md Fase 11 e
04_protocolo_metricas_validacao.md §4.6.

Lê TODOS os `*_metrics.jsonl` gravados por `report_eval` (a única fonte de
métricas do projeto) e produz:

1. **Tabela primária** — a família de hipóteses declarada ANTES de rodar:
   os 6 pares par-a-par do Caminho A, braço `controlado`, F1-macro com IC
   95%. Só esta família responde à pergunta da dissertação.
2. **Tabela exploratória** — todo o resto (outros caminhos, outros braços,
   ablações, controles), com **BH-FDR** (`statsmodels`, q=0,05) aplicado
   aos p-values.
3. **Veredicto por comparação**: o IC 95% de F1 exclui o nível de acaso?
   Combinado com o MDE do poder a priori (`reports/v2/power_analysis.md`),
   é isso que transforma um nulo em "tínhamos poder para detectar X e não
   detectamos".

p-value de cada comparação: **aproximação normal a partir do IC 95%
bootstrap** — a semilargura do IC vira erro padrão (`SE = meia_largura /
1,96`) e aplica-se o z usual, bicaudal. Ver `add_verdicts`.

> **Correção de 2026-08-24:** este cabeçalho descrevia um teste diferente
> do implementado ("a fração de reamostragens em que F1 <= acaso, ×2"),
> que é o p-value percentílico do bootstrap. O código sempre fez a
> aproximação normal; só o comentário inline estava honesto. Como esta
> docstring é o que vira seção de métodos, a divergência ia parar no
> texto. O método percentílico é mais defensável para bootstrap (não
> supõe normalidade da distribuição amostral de F1), mas exige guardar as
> reamostragens — hoje `report_eval` persiste só os percentis 2,5/97,5.
> Migrar é possível e está registrado como melhoria; enquanto não migra,
> a aproximação normal fica DECLARADA, não descrita como outra coisa.

**Antes de uma rodada OFICIAL, limpe `reports/v2/`.** Os `.jsonl` são
append-only (de propósito — gravação incremental sobrevive a queda de
sessão). Este script deduplica mantendo o registro mais recente de cada
(run_id, caminho, modelo, braço, fold), o que resolve o caso normal de
"rodei de novo depois de ajustar algo"; mas se rodadas de versões
diferentes do código se sobrepuserem no tempo, a ordem por timestamp
deixa de ser confiável. Partir de um diretório limpo elimina a dúvida.

Uso:
    python scripts/consolidate_v2.py
    python scripts/consolidate_v2.py --branch controlado
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

REPORTS = REPO_ROOT / "reports" / "v2"
OUT_MD = REPORTS / "consolidado_v2.md"
OUT_CSV = REPORTS / "consolidado_v2.csv"

PRIMARY_CAMINHO = "A"
PRIMARY_BRANCH = "controlado"
# Modelo OFICIAL da família primária — pré-declarado, não escolhido pelo
# resultado. Ver `is_primary` para o porquê de existir um único modelo.
PRIMARY_MODEL = "RandomForest"


def chance_level(n_classes: int) -> float:
    return 1.0 / max(n_classes, 1)


# Braços que NUNCA podem entrar numa tabela de resultado. `sintetico` é o
# parquet de features aleatórias usado para validar encanamento (folds,
# seletor, modelos, relato) sem esperar as ~20h da extração real — por
# construção não contém sinal nenhum, mas os `.jsonl` são append-only e o
# `rglob` não distingue braço. Sem este filtro, uma rodada de validação
# entra na tabela exploratória E no denominador do BH-FDR (demonstrado na
# auditoria de 2026-08-23: o HKNNRF saiu com p bruto de 0,0296 sobre ruído
# puro). O runbook manda limpar `reports/v2/` antes de rodada oficial, o
# que mitiga — mas depender só de disciplina de operador para não
# contaminar a estatística é frágil demais.
_NON_OFFICIAL_BRANCHES = {"sintetico"}


def load_all_metrics(drop_non_official: bool = True) -> pd.DataFrame:
    """Varre recursivamente os .jsonl de métricas de todos os caminhos."""
    rows: list[dict] = []
    for jsonl in sorted(REPORTS.rglob("*_metrics.jsonl")):
        for line in jsonl.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            cm = rec.get("confusion_matrix") or []
            n_classes = len(cm) if cm else 0
            rows.append({
                "run_id": rec.get("run_id"),
                "caminho": rec.get("caminho"),
                "modelo": rec.get("modelo"),
                "braco": rec.get("braco"),
                "fold": str(rec.get("fold")),
                "timestamp": rec.get("timestamp"),
                "n_classes": n_classes,
                "n_samples": rec.get("n_samples"),
                "f1_macro": rec.get("f1_macro"),
                "f1_ci_lo": rec.get("f1_macro_ci_lower"),
                "f1_ci_hi": rec.get("f1_macro_ci_upper"),
                "accuracy": rec.get("accuracy"),
                "balanced_accuracy": rec.get("balanced_accuracy"),
                "ece": rec.get("ece"),
                "source_file": str(jsonl.relative_to(REPORTS)),
            })
    if not rows:
        raise FileNotFoundError(
            f"Nenhum *_metrics.jsonl encontrado em {REPORTS}. "
            "Rode antes pelo menos um caminho.")
    df = pd.DataFrame(rows)

    # Os .jsonl de `report_eval` são append-only (de propósito: gravação
    # incremental sobrevive a queda de sessão). O efeito colateral é que
    # rodar de novo a mesma configuração — por exemplo depois de corrigir
    # um bug — deixa a linha ANTIGA no arquivo. Sem deduplicar, a
    # consolidação misturaria resultado velho e novo da mesma célula.
    # Mantemos o registro MAIS RECENTE de cada
    # (run_id, caminho, modelo, braço, fold).
    if drop_non_official:
        # Casa por prefixo: os braços da ablação viram `sintetico_...`
        # (ex.: `sintetico_sem_keyholdout`, `sintetico_familia_NIST`).
        mask = df["braco"].astype(str).str.split("_").str[0].isin(_NON_OFFICIAL_BRANCHES)
        if mask.any():
            print(f"[filtro] {int(mask.sum())} registro(s) de braço não-oficial "
                  f"descartado(s) ({sorted(df.loc[mask, 'braco'].unique())}) — "
                  f"validação de encanamento não entra em tabela de resultado")
            df = df[~mask].reset_index(drop=True)

    key = ["run_id", "caminho", "modelo", "braco", "fold"]
    n_before = len(df)
    df = (df.sort_values("timestamp")
            .drop_duplicates(subset=key, keep="last")
            .reset_index(drop=True))
    if len(df) < n_before:
        print(f"[dedup] {n_before - len(df)} registro(s) antigo(s) descartado(s) "
              f"— mantido o mais recente por (run_id, caminho, modelo, braço, fold)")
    return df


def add_verdicts(df: pd.DataFrame) -> pd.DataFrame:
    """Acaso, veredicto pelo IC e p-value aproximado a partir do IC."""
    df = df.copy()
    df["acaso"] = df["n_classes"].map(chance_level)
    df["acima_do_acaso"] = df["f1_ci_lo"] > df["acaso"]
    df["abaixo_do_acaso"] = df["f1_ci_hi"] < df["acaso"]

    # p-value bicaudal aproximado a partir do IC 95% bootstrap: converte a
    # meia-largura do IC em erro padrão (IC ~ estimativa +- 1,96 SE) e
    # aplica o z usual. Aproximação normal — declarada, e coerente com o
    # bootstrap percentil que gerou o IC.
    half_width = (df["f1_ci_hi"] - df["f1_ci_lo"]) / 2.0
    se = (half_width / 1.96).replace(0, np.nan)
    z = (df["f1_macro"] - df["acaso"]) / se
    from scipy.stats import norm
    df["p_value"] = 2.0 * (1.0 - norm.cdf(z.abs()))
    df.loc[se.isna(), "p_value"] = np.nan
    return df


def apply_bh_fdr(df: pd.DataFrame, q: float = 0.05) -> pd.DataFrame:
    """BH-FDR sobre a tabela exploratória (q=0,05)."""
    df = df.copy()
    df["q_value"] = np.nan
    df["significativo_fdr"] = False
    valid = df["p_value"].notna()
    if not valid.any():
        return df
    try:
        from statsmodels.stats.multitest import multipletests
        reject, qvals, _, _ = multipletests(
            df.loc[valid, "p_value"].to_numpy(), alpha=q, method="fdr_bh")
    except ImportError:
        # Fallback: BH implementado à mão (evita depender de statsmodels
        # só para isso; resultado idêntico ao `fdr_bh`).
        p = df.loc[valid, "p_value"].to_numpy()
        order = np.argsort(p)
        n = len(p)
        qvals_sorted = p[order] * n / (np.arange(n) + 1)
        qvals_sorted = np.minimum.accumulate(qvals_sorted[::-1])[::-1]
        qvals = np.empty(n)
        qvals[order] = np.clip(qvals_sorted, 0, 1)
        reject = qvals < q
    df.loc[valid, "q_value"] = qvals
    df.loc[valid, "significativo_fdr"] = reject
    return df


def is_primary(df: pd.DataFrame) -> pd.Series:
    """
    Família primária: **exatamente 6 testes** — os 6 pares par-a-par,
    Caminho A, braço controlado, resultado FINAL, **e só o modelo oficial
    (`PRIMARY_MODEL`)**.

    O filtro por modelo é a correção de um problema real (auditoria de
    2026-08-23): sem ele, a "família primária de 6 comparações" capturava
    os 9 modelos de cada par (RF, LinearSVC, XGBoost, LR, SVM-RBF,
    Stacking e as 3 réplicas) = **54 testes sem correção**. A α=0,05 isso
    dá P(≥1 falso positivo) ≈ 94%, e um positivo primário dispara a
    réplica obrigatória com chaves novas (offset 7000) — caro. Pior: todo
    o argumento para NÃO corrigir a família primária é ela ser pequena e
    pré-declarada, o que 54 testes não são.

    **Por que RandomForest** (decidido 2026-08-23): é pré-declarado (não
    escolhido olhando o resultado), é o modelo que o v1 usou como
    referência, e manter UM teste por par preserva a validade da análise
    de poder já rodada — o MDE de +1,02 p.p. foi calculado a α=0,05 para
    um único teste. Os outros 8 modelos por par continuam sendo rodados e
    reportados, mas na tabela exploratória, sob BH-FDR.
    """
    return (
        (df["caminho"] == PRIMARY_CAMINHO)
        & (df["braco"] == PRIMARY_BRANCH)
        & (df["modelo"] == PRIMARY_MODEL)
        & (df["run_id"].astype(str).str.contains("_pair_"))
        & (df["fold"] == "final")
    )


# ---------------------------------------------------------------------------
# McNemar pareado + Bonferroni (04_protocolo §4.3) — família primária
# ---------------------------------------------------------------------------

def run_mcnemar_primary(primary: pd.DataFrame) -> pd.DataFrame:
    """
    McNemar pareado entre TODOS os pares de modelos, dentro de cada
    comparação da família primária (mesmo run_id/braço/fold — nunca entre
    análises diferentes, o que compararia amostras distintas). Bonferroni
    aplicado sobre o nº de pares de modelos DENTRO de cada comparação
    (não globalmente — cada comparação primária é sua própria família de
    testes pareados).
    """
    from src.eval.metrics import mcnemar_test
    from src.eval.reporting import load_predictions
    from itertools import combinations

    rows = []
    for run_id, grp in primary.groupby("run_id"):
        src = REPORTS / Path(grp.iloc[0]["source_file"]).parent
        try:
            preds = load_predictions(src, run_id, caminho=PRIMARY_CAMINHO)
        except FileNotFoundError:
            continue
        preds = preds[(preds["braco"] == PRIMARY_BRANCH) & (preds["fold"].astype(str) == "final")]
        by_model = {m: g.sort_values("sample_id") for m, g in preds.groupby("modelo")}
        models = sorted(by_model)
        if len(models) < 2:
            continue
        pairs = list(combinations(models, 2))
        for m_a, m_b in pairs:
            ga, gb = by_model[m_a], by_model[m_b]
            merged = ga[["sample_id", "y_true", "y_pred"]].merge(
                gb[["sample_id", "y_pred"]], on="sample_id", suffixes=("_a", "_b"))
            if merged.empty:
                continue
            res = mcnemar_test(merged["y_true"].to_numpy(),
                               merged["y_pred_a"].to_numpy(), merged["y_pred_b"].to_numpy())
            res["p_bonferroni"] = min(1.0, res["p_value"] * len(pairs))
            res["significativo_bonferroni"] = res["p_bonferroni"] < 0.05
            rows.append({"run_id": run_id, "modelo_a": m_a, "modelo_b": m_b,
                        "n_pares_na_comparacao": len(pairs), **res})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Estratificação de erro (06 Fase 11.2 / 04 §4.6.7) — todo resultado acima
# do acaso é conferido contra artefato de chave ou de plaintext_source.
# ---------------------------------------------------------------------------

_RAW_DATASET = REPO_ROOT / "data" / "processed" / "keyholdout_5class_v2.parquet"
_ARTIFACT_THRESHOLD = 0.05  # diferença de acurácia entre estratos que vira bandeira


def _sample_metadata() -> pd.DataFrame:
    """`sample_id -> plaintext_source`, lido só dessas duas colunas (nunca
    o parquet inteiro de 11,8GB — mesma disciplina de memória do resto
    do projeto)."""
    if not _RAW_DATASET.exists():
        return pd.DataFrame(columns=["sample_id", "plaintext_source"])
    return pd.read_parquet(_RAW_DATASET, columns=["sample_id", "plaintext_source"])


def stratify_row(row: pd.Series, meta: pd.DataFrame) -> dict | None:
    """Estratificação de erro de UMA linha da tabela consolidada (um
    run_id/caminho/modelo/braço/fold específico). None se não há
    predições persistidas para reconstruir (ex.: rodadas antigas)."""
    from src.eval.reporting import load_predictions

    src = REPORTS / Path(row["source_file"]).parent
    try:
        preds = load_predictions(src, row["run_id"], caminho=row["caminho"])
    except FileNotFoundError:
        return None
    preds = preds[(preds["modelo"] == row["modelo"]) & (preds["braco"] == row["braco"])
                 & (preds["fold"].astype(str) == str(row["fold"]))]
    if preds.empty:
        return None

    preds = preds.merge(meta, on="sample_id", how="left")
    preds["correct"] = preds["y_true"] == preds["y_pred"]

    out: dict = {}
    if preds["plaintext_source"].notna().any():
        by_source = preds.groupby("plaintext_source")["correct"].mean()
        out["acc_por_plaintext_source"] = by_source.round(4).to_dict()
        if len(by_source) >= 2:
            spread = float(by_source.max() - by_source.min())
            out["spread_plaintext_source"] = round(spread, 4)
            out["bandeira_plaintext_source"] = spread > _ARTIFACT_THRESHOLD

    if "key_id" in preds.columns and preds["key_id"].notna().any():
        by_key = preds.groupby("key_id")["correct"].mean()
        out["acc_por_chave_desvio"] = round(float(by_key.std()), 4)
        out["acc_por_chave_min_max"] = [round(float(by_key.min()), 4), round(float(by_key.max()), 4)]
        out["bandeira_chave"] = bool(by_key.std() > 0.15)

    return out or None


def stratify_above_chance(df: pd.DataFrame) -> pd.DataFrame:
    """Roda `stratify_row` em toda linha (primária ou exploratória) com
    `acima_do_acaso=True` — a checagem de artefato só faz sentido quando
    há algo acima do acaso para explicar."""
    meta = _sample_metadata()
    if meta.empty:
        print("[aviso] dataset bruto não encontrado — estratificação de erro pulada")
        return pd.DataFrame()
    targets = df[df.get("acima_do_acaso", False) == True]  # noqa: E712
    rows = []
    for _, row in targets.iterrows():
        strat = stratify_row(row, meta)
        if strat:
            rows.append({"run_id": row["run_id"], "caminho": row["caminho"],
                        "modelo": row["modelo"], "braco": row["braco"],
                        "fold": row["fold"], **strat})
    return pd.DataFrame(rows)


def md_table(df: pd.DataFrame, cols: list[str]) -> str:
    if df.empty:
        return "_(vazio)_\n"
    head = "| " + " | ".join(cols) + " |\n"
    head += "|" + "|".join(["---"] * len(cols)) + "|\n"
    body = ""
    for _, r in df.iterrows():
        vals = []
        for c in cols:
            v = r[c]
            if isinstance(v, float):
                vals.append("—" if pd.isna(v) else f"{v:.4f}")
            elif isinstance(v, (bool, np.bool_)):
                vals.append("sim" if v else "não")
            else:
                vals.append(str(v))
        body += "| " + " | ".join(vals) + " |\n"
    return head + body


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    p = argparse.ArgumentParser()
    p.add_argument("--branch", default=None,
                   help="Filtra por braço (default: todos).")
    p.add_argument("--q", type=float, default=0.05)
    args = p.parse_args()

    df = load_all_metrics()
    if args.branch:
        df = df[df["braco"] == args.branch]
    df = add_verdicts(df)

    primary_mask = is_primary(df)
    primary = df[primary_mask].copy()

    # **A família exploratória é só de resultados FINAIS.** Os folds de CV
    # (0..4) são diagnóstico de estabilidade, não hipóteses — incluí-los
    # colocava a MESMA hipótese 6x no denominador do BH-FDR (5 folds + o
    # final), com dependência forte entre as linhas, e fazia uma linha de
    # validação receber `significativo_fdr`, um status inferencial que ela
    # não tem. Corrigido na auditoria de 2026-08-23. Os folds continuam no
    # CSV completo, só não entram na correção de múltiplas comparações.
    resto = df[~primary_mask].copy()
    e_final = resto["fold"].astype(str).str.startswith("final")
    n_folds_cv = int((~e_final).sum())
    if n_folds_cv:
        print(f"[FDR] {n_folds_cv} linha(s) de fold de CV fora da família "
              f"exploratória (diagnóstico, não hipótese) — seguem no CSV")
    exploratory = apply_bh_fdr(resto[e_final].copy(), q=args.q)
    exploratory_cv = resto[~e_final].copy()

    print(f"Registros de métrica: {len(df):,}  "
          f"(primários: {len(primary)}, exploratórios: {len(exploratory)})")
    if primary.empty:
        print("[aviso] família primária vazia — os 6 pares do Caminho A "
              "(braço controlado, fold=final) ainda não foram rodados.")

    cols_primary = ["run_id", "modelo", "f1_macro", "f1_ci_lo", "f1_ci_hi",
                    "acaso", "acima_do_acaso", "p_value", "n_samples"]
    cols_expl = ["run_id", "caminho", "modelo", "braco", "fold", "f1_macro",
                 "f1_ci_lo", "f1_ci_hi", "acaso", "p_value", "q_value",
                 "significativo_fdr"]

    REPORTS.mkdir(parents=True, exist_ok=True)
    pd.concat([primary.assign(familia="primaria"),
               exploratory.assign(familia="exploratoria"),
               exploratory_cv.assign(familia="fold_cv_diagnostico")],
              ignore_index=True).to_csv(OUT_CSV, index=False)

    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("# Consolidação — experimento v2\n\n")
        f.write("Gerado por `scripts/consolidate_v2.py` a partir dos "
                "`*_metrics.jsonl` de `report_eval` (fonte única de métricas).\n\n")

        f.write("## 1. Família primária (declarada antes de rodar)\n\n")
        f.write(f"6 comparações par-a-par entre os 4 algoritmos, **Caminho A, "
                f"braço controlado, modelo `{PRIMARY_MODEL}`**, F1-macro com IC "
                f"95% bootstrap. **Exatamente 6 testes** — um por par, com o "
                f"modelo pré-declarado. Sem correção de múltiplas comparações: "
                f"é a família primária, pequena e pré-declarada, e é essa "
                f"pequenez que justifica não corrigir (com os 9 modelos de cada "
                f"par seriam 54 testes e P(≥1 falso positivo) ≈ 94%). Os demais "
                f"modelos de cada par (LinearSVC, XGBoost, LR, SVM-RBF, Stacking "
                f"e as 3 réplicas) são rodados e reportados, mas na tabela "
                f"exploratória abaixo, sob BH-FDR.\n\n")
        f.write(md_table(primary.sort_values("run_id"), cols_primary))

        f.write("\n## 2. Exploratório (BH-FDR, q=%.2f)\n\n" % args.q)
        f.write("Todo o resto — demais caminhos, braços, ablações e controles. "
                "`q_value` é o p-value ajustado por Benjamini-Hochberg; "
                "`significativo_fdr` marca o que sobrevive à correção. "
                "Bonferroni global mataria qualquer efeito real nesta escala "
                "de testes, por isso FDR.\n\n")
        f.write(md_table(
            exploratory.sort_values("p_value", na_position="last").head(80),
            cols_expl))
        if len(exploratory) > 80:
            f.write(f"\n_(mostrando 80 de {len(exploratory)} linhas; "
                    f"tabela completa em `{OUT_CSV.name}`)_\n")

        n_sig = int(exploratory["significativo_fdr"].sum())
        f.write("\n## 3. Leitura\n\n")
        f.write(f"- Comparações primárias acima do acaso (IC 95% exclui o acaso): "
                f"**{int(primary['acima_do_acaso'].sum())} de {len(primary)}**.\n")
        f.write(f"- Resultados exploratórios que sobrevivem ao FDR: **{n_sig}**.\n")
        f.write("- Qualquer positivo (primário ou exploratório sobrevivente ao "
                "FDR) exige **replicação** com chaves novas (offset 7000) e "
                "teste único pré-especificado antes de ser reportado como "
                "achado — protocolo definido no planejamento.\n")
        f.write("- Um nulo aqui deve ser lido junto do poder a priori "
                "(`power_analysis.md`): o desenho detecta **+1,02 p.p.** acima "
                "do acaso no teste 4-classes (poder empírico MEDIDO: 96%) e "
                "**+1,27 p.p.** no par binário (78%) — 80% era o alvo de "
                "projeto, não o valor obtido. Efeitos menores que isso não "
                "são detectáveis nesta escala — limitação declarada, não "
                "prova de ausência.\n")

        f.write("\n## 4. McNemar pareado entre modelos (família primária, "
                "Bonferroni)\n\n")
        f.write("Comparação pareada modelo-a-modelo, SÓ dentro da mesma "
                "comparação (run_id) — nunca entre pares diferentes, que "
                "teriam amostras distintas. Bonferroni sobre o nº de pares "
                "de modelos dentro de cada comparação.\n\n")
        try:
            mcnemar_df = run_mcnemar_primary(primary) if not primary.empty else pd.DataFrame()
        except Exception as exc:  # noqa: BLE001
            print(f"[aviso] McNemar pulado: {type(exc).__name__}: {exc}")
            mcnemar_df = pd.DataFrame()
        if mcnemar_df.empty:
            f.write("_(sem predições persistidas suficientes — rode o Caminho A "
                    "com `--analysis pairs` antes)_\n")
        else:
            f.write(md_table(mcnemar_df, ["run_id", "modelo_a", "modelo_b", "n10", "n01",
                                          "p_value", "p_bonferroni", "significativo_bonferroni"]))
            mcnemar_df.to_csv(REPORTS / "consolidado_v2_mcnemar.csv", index=False)

        f.write("\n## 5. Estratificação de erro (todo resultado acima do acaso)\n\n")
        f.write("Confere se o erro correlaciona com `key_id` ou "
                "`plaintext_source` — \"separa melhor em imagens\" é bandeira "
                "de artefato, não achado sobre o algoritmo (04 §4.6.7). "
                f"Bandeira: diferença de acurácia entre plaintext_source > "
                f"{_ARTIFACT_THRESHOLD} ou desvio-padrão de acurácia por chave > 0,15.\n\n")
        try:
            strat_df = stratify_above_chance(pd.concat([primary, exploratory], ignore_index=True))
        except Exception as exc:  # noqa: BLE001
            print(f"[aviso] estratificação de erro pulada: {type(exc).__name__}: {exc}")
            strat_df = pd.DataFrame()
        if strat_df.empty:
            f.write("_(nenhum resultado acima do acaso com predições persistidas "
                    "para estratificar)_\n")
        else:
            flag_cols = [c for c in strat_df.columns if c.startswith("bandeira_")]
            n_flagged = int(strat_df[flag_cols].any(axis=1).sum()) if flag_cols else 0
            f.write(f"**{n_flagged} de {len(strat_df)}** resultado(s) acima do acaso "
                    f"levantam bandeira de possível artefato.\n\n")
            f.write(md_table(strat_df, ["run_id", "caminho", "modelo", "braco", "fold"]
                            + [c for c in strat_df.columns if c not in
                               ("run_id", "caminho", "modelo", "braco", "fold")]))
            strat_df.to_csv(REPORTS / "consolidado_v2_estratificacao.csv", index=False)

    print(f"Consolidado salvo em:\n  {OUT_MD}\n  {OUT_CSV}")


if __name__ == "__main__":
    main()
