"""
Caminho F do experimento v2 — meta-classificador sobre as probabilidades
out-of-fold dos Caminhos A-E, avaliado no teste canônico. Ver
docs/plano_experimento_v2/06_implementacao_passo_a_passo.md Fase 10.

**Disciplina out-of-fold é pré-requisito duro, não opcional** (correção da
revisão crítica do plano): a matriz de TREINO do meta-modelo é montada
EXCLUSIVAMENTE a partir dos parquets de predição de VALIDAÇÃO da CV de
cada caminho (`report_eval`) — nunca de refits. Cada linha foi predita por
um modelo que não a viu no treino, então o meta-modelo não herda
vazamento dos modelos-base. Um `assert` confere que nenhuma chave de
teste aparece nessa matriz.

**Avaliação no teste canônico** (corrigido na verificação de aderência de
2026-08-22 — a versão anterior dividia as chaves de trainval 80/20 e
chamava isso de "teste", nunca tocando o holdout real; a Fase 10 pede
"teste final com modelos-base treinados no trainval", e sem isso o F não
é comparável a A-E na consolidação): o meta-modelo é fitado com 100% da
matriz OOF (não há razão para reservar uma fração dela — o holdout de
verdade é o teste canônico) e avaliado UMA VEZ nas predições `final` dos
modelos-base (trainval completo → teste), com os MESMOS calibradores
isotônicos ajustados na matriz OOF (nunca refitados no teste).

**Calibração (B6):** LinearSVC/SVM não têm `predict_proba` nativo; suas
"probabilidades" vêm de softmax sobre `decision_function`, que não é
calibrada. Cada coluna de probabilidade passa por calibração isotônica
ajustada na matriz OOF — ECE antes/depois é reportado.

**Regra registrada:** se o Caminho F der "significativo" com todos os
modelos-base no acaso, isso é bandeira de investigação de vazamento, NÃO
descoberta. O relatório imprime esse aviso automaticamente quando o caso
ocorre.

Uso:
    python scripts/run_v2_caminho_f.py --branch controlado
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.isotonic import IsotonicRegression  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import f1_score  # noqa: E402

from src.eval.metrics import expected_calibration_error  # noqa: E402
from src.eval.reporting import report_eval  # noqa: E402

DATASET_ID = "keyholdout_5class_v2"
PROCESSED = REPO_ROOT / "data" / "processed"
FOLDS_JSON = PROCESSED / "v2_folds.json"
REPORTS = REPO_ROOT / "reports" / "v2"
OUT_DIR = REPORTS / "caminho_f"

REAL_ALGORITHMS = ["Ascon-AEAD128", "GIFT-COFB", "Grain-128AEAD", "Schwaemm256-128"]
SEED_MODEL = 7
CHANCE_F1_4CLASS = 0.25

CAMINHO_DIRS = {
    "A": "caminho_a", "B": "caminho_b", "C": "caminho_c",
    "D": "caminho_d", "E": "caminho_e",
}

# Tags de fold que ALIMENTAM o F como "final" (trainval completo -> teste).
# B/C/E rodam 3 seeds no braço controlado (`FINAL_SEEDS = [7, 107, 207]` em
# run_v2_caminhos_bce.py); o F usa só a seed principal (7), a mesma do resto
# do projeto — as outras duas são o robustez-check DAQUELE caminho, não
# insumo do meta-modelo (usá-las daria várias predições da mesma fonte para
# o mesmo `sample_id`, resolvidas por um `drop_duplicates` arbitrário).
FINAL_SOURCE_TAGS = {"final", "final_seed7"}


def _is_final_fold(fold_series: pd.Series) -> pd.Series:
    """
    Máscara de QUALQUER rodada de modelo final (trainval completo -> teste).

    Distinta de `FINAL_SOURCE_TAGS` de propósito, e a distinção é um
    bloqueador real corrigido em 2026-08-23: a versão anterior usava o
    mesmo conjunto fixo para os dois lados, então `final_seed107` e
    `final_seed207` — que NÃO estão no conjunto — caíam no lado
    out-of-fold. Como são predições sobre chaves de TESTE, o assert de
    vazamento derrubava o script inteiro assim que B/C/E rodassem as 3
    seeds no braço controlado. Exclusão (OOF) usa este predicado amplo;
    inclusão (fonte do F) usa `FINAL_SOURCE_TAGS`.
    """
    return fold_series.astype(str).str.startswith("final")


def _collect(branch: str, run_id: str, want_final: bool) -> pd.DataFrame:
    """
    Junta os parquets de predição por amostra dos Caminhos A-E.

    `want_final=False`: só linhas de fold de CV (out-of-fold) — treino do
    meta-modelo e dos calibradores.
    `want_final=True`: só linhas de `FINAL_SOURCE_TAGS` — avaliação do F no
    teste canônico, com modelos-base treinados no trainval completo.
    """
    frames: list[pd.DataFrame] = []
    for caminho, dirname in CAMINHO_DIRS.items():
        pred_dir = REPORTS / dirname / branch / "predictions"
        if not pred_dir.exists():
            continue
        for pq_file in sorted(pred_dir.glob(f"{run_id}_*.parquet")):
            df = pd.read_parquet(pq_file)
            if df.empty or "y_proba" not in df.columns:
                continue
            # Assimétrico de propósito — ver `_is_final_fold`. Inclusão usa
            # o conjunto estrito (só a seed principal alimenta o F);
            # exclusão usa o predicado amplo (NENHUMA rodada final pode
            # vazar para o lado out-of-fold, seja qual for a seed).
            if want_final:
                df = df[df["fold"].astype(str).isin(FINAL_SOURCE_TAGS)]
            else:
                df = df[~_is_final_fold(df["fold"])]
            if df.empty:
                continue
            frames.append(df)
    if not frames:
        kind = "final (teste canônico)" if want_final else "out-of-fold"
        raise FileNotFoundError(
            f"Nenhuma predição {kind} encontrada para run_id={run_id!r}, "
            f"braço={branch!r}. Rode antes os Caminhos A-E "
            f"({'--mode final' if want_final else '--mode cv, ou a análise principal do A'})."
        )
    return pd.concat(frames, ignore_index=True)


def build_source_matrix(df: pd.DataFrame, label: str) -> tuple[pd.DataFrame, list[str]]:
    """
    Pivota: uma linha por `sample_id`, uma coluna por
    (caminho, modelo, classe). Amostras sem predição de algum modelo são
    descartadas (o meta-modelo exige o vetor completo). Usado tanto para
    a matriz OOF (treino) quanto para a matriz de teste canônico.
    """
    df = df.copy()
    df["source"] = df["caminho"] + "_" + df["modelo"]
    n_classes = len(df["y_proba"].iloc[0])

    wide: dict[str, pd.Series] = {}
    base = None
    per_source_ids: dict[str, set] = {}
    for source, grp in df.groupby("source"):
        grp = grp.drop_duplicates(subset=["sample_id"]).set_index("sample_id")
        per_source_ids[source] = set(grp.index)
        proba = np.vstack(grp["y_proba"].to_numpy())
        for c in range(n_classes):
            wide[f"p_{source}_c{c}"] = pd.Series(proba[:, c], index=grp.index)
        if base is None:
            base = grp[["y_true", "key_id"]]

    # Diagnóstico ANTES do join: se as fontes não compartilham `sample_id`,
    # o inner join zera silenciosamente e o erro genérico ("matriz vazia")
    # não diz onde está o problema.
    common = set.intersection(*per_source_ids.values()) if per_source_ids else set()
    print(f"  [{label}] amostras por fonte: "
          + ", ".join(f"{s}={len(ids)}" for s, ids in sorted(per_source_ids.items())))
    print(f"  [{label}] interseção de sample_id entre TODAS as fontes: {len(common)}")
    if not common:
        raise RuntimeError(
            f"[{label}] Nenhum `sample_id` em comum entre as fontes de predição. "
            "As fontes precisam ter predito as MESMAS amostras (mesma partição "
            "de folds e mesmo conjunto de classes). Fontes encontradas: "
            + ", ".join(f"{s} ({len(ids)} amostras)" for s, ids in sorted(per_source_ids.items()))
        )

    mat = pd.DataFrame(wide)
    mat = mat.join(base, how="inner").dropna()
    proba_cols = sorted(c for c in mat.columns if c.startswith("p_"))
    return mat.reset_index().rename(columns={"index": "sample_id"}), proba_cols


def _ece_of(frame: pd.DataFrame, proba_cols: list[str], y: np.ndarray) -> float:
    """ECE agregado sobre a média das fontes (visão global de calibração)."""
    n_classes = len({c.rsplit("_c", 1)[1] for c in proba_cols})
    by_class = []
    for c in range(n_classes):
        cols_c = [col for col in proba_cols if col.endswith(f"_c{c}")]
        by_class.append(frame[cols_c].to_numpy().mean(axis=1))
    proba = np.column_stack(by_class)
    proba = proba / np.clip(proba.sum(axis=1, keepdims=True), 1e-12, None)
    return expected_calibration_error(y, proba)


def fit_calibrators(
    mat: pd.DataFrame, proba_cols: list[str],
) -> dict[str, IsotonicRegression]:
    """Ajusta uma calibração isotônica por coluna de probabilidade,
    inteiramente na matriz OOF (nunca no teste)."""
    y = mat["y_true"].to_numpy()
    calibrators: dict[str, IsotonicRegression] = {}
    for col in proba_cols:
        cls = int(col.rsplit("_c", 1)[1])
        target = (y == cls).astype(float)
        iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
        iso.fit(mat[col].to_numpy(), target)
        calibrators[col] = iso
    return calibrators


def apply_calibrators(
    mat: pd.DataFrame, proba_cols: list[str], calibrators: dict[str, IsotonicRegression],
) -> pd.DataFrame:
    out = mat.copy()
    for col in proba_cols:
        out[col] = calibrators[col].predict(out[col].to_numpy())
    return out


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    p = argparse.ArgumentParser()
    p.add_argument("--branch", default="controlado", choices=["cru", "controlado"])
    p.add_argument("--run-id", default=f"{DATASET_ID}_4class")
    p.add_argument("--n-bootstrap", type=int, default=1000)
    args = p.parse_args()

    out_dir = OUT_DIR / args.branch
    out_dir.mkdir(parents=True, exist_ok=True)
    folds = json.loads(FOLDS_JSON.read_text(encoding="utf-8"))

    # ---------------- Treino do meta-modelo: 100% da matriz OOF ----------------
    print(f"Coletando predições out-of-fold (braço={args.branch})...")
    oof = _collect(args.branch, args.run_id, want_final=False)
    print(f"  {len(oof):,} linhas de predição, "
          f"caminhos={sorted(oof['caminho'].unique())}, "
          f"modelos={sorted(oof['modelo'].unique())}")

    mat, proba_cols = build_source_matrix(oof, "oof")
    if mat.empty:
        raise RuntimeError("Matriz OOF vazia após o join — verifique se os "
                           "caminhos rodaram sobre a MESMA partição de folds.")

    # Assert de partição: nenhuma chave de TESTE pode aparecer na matriz de
    # treino do meta-modelo — seria vazamento do holdout canônico.
    got_keys = set(mat["key_id"].dropna().unique())
    leaked_test_keys = got_keys & set(folds["test_keys"])
    if leaked_test_keys:
        raise AssertionError(
            f"Predições OOF contêm chaves de TESTE "
            f"(vazamento do holdout canônico): {sorted(leaked_test_keys)[:5]}")

    calibrators = fit_calibrators(mat, proba_cols)
    mat_cal = apply_calibrators(mat, proba_cols, calibrators)
    y_oof = mat_cal["y_true"].to_numpy()
    ece_before = _ece_of(mat, proba_cols, y_oof)
    ece_after = _ece_of(mat_cal, proba_cols, y_oof)
    print(f"  calibração isotônica (fitada no OOF): ECE {ece_before:.4f} -> {ece_after:.4f}")

    X_oof = mat_cal[proba_cols].to_numpy(np.float64)
    meta = LogisticRegression(max_iter=2000, random_state=SEED_MODEL)
    t0 = time.perf_counter()
    meta.fit(X_oof, y_oof)

    # ---------------- Avaliação: teste canônico, modelos-base do trainval ----------------
    print(f"\nColetando predições finais (teste canônico, braço={args.branch})...")
    final_df = _collect(args.branch, args.run_id, want_final=True)
    te_mat, te_cols = build_source_matrix(final_df, "final")

    missing_cols = set(proba_cols) - set(te_cols)
    if missing_cols:
        raise RuntimeError(
            f"As predições finais não cobrem todas as fontes usadas para "
            f"treinar o meta-modelo. Faltando: {sorted(missing_cols)}. Rode "
            f"`--mode final` para os caminhos ausentes antes do Caminho F."
        )
    te_leaked = set(te_mat["key_id"].dropna().unique()) - set(folds["test_keys"])
    if te_leaked:
        raise AssertionError(
            f"Predições `final` contêm chaves fora do teste canônico "
            f"(possível vazamento reverso): {sorted(te_leaked)[:5]}")

    te_cal = apply_calibrators(te_mat, proba_cols, calibrators)
    X_te = te_cal[proba_cols].to_numpy(np.float64)
    y_te = te_cal["y_true"].to_numpy()
    y_pred = meta.predict(X_te)
    y_proba = meta.predict_proba(X_te)

    report = report_eval(
        run_id=args.run_id, caminho="F", modelo="LogisticRegression_meta",
        braco=args.branch, fold="final",
        y_true=y_te, y_pred=y_pred, y_proba=y_proba,
        sample_ids=te_cal["sample_id"].tolist(),
        key_ids=te_cal["key_id"].tolist(),
        class_names=REAL_ALGORITHMS, labels=list(range(len(REAL_ALGORITHMS))),
        out_dir=out_dir, n_bootstrap=args.n_bootstrap,
        extra={"n_sources": len(proba_cols), "sources": proba_cols,
               "calibration_ece_before": round(float(ece_before), 4),
               "calibration_ece_after": round(float(ece_after), 4),
               "n_meta_train_oof": int(len(mat_cal)), "n_test": int(len(te_cal)),
               "train_time_s": round(time.perf_counter() - t0, 1)},
    )

    # Bandeira de vazamento: F acima do acaso com TODOS os bases no acaso.
    # F1-macro por (caminho, modelo) na matriz OOF — antes calculava
    # acurácia (achado na verificação de aderência), o que podia mascarar
    # um modelo-base degenerado (acurácia alta, F1-macro baixo em classes
    # desbalanceadas por predição).
    base_f1 = oof.groupby(["caminho", "modelo"]).apply(
        lambda g: float(f1_score(
            g["y_true"].to_numpy(), np.vstack(g["y_proba"].to_numpy()).argmax(1),
            average="macro")),
        include_groups=False,
    )
    bases_at_chance = bool((base_f1 < CHANCE_F1_4CLASS + 0.02).all())
    f_above_chance = report.f1_macro_ci[0] > CHANCE_F1_4CLASS
    if bases_at_chance and f_above_chance:
        print("\n" + "!" * 70)
        print("  ATENÇÃO: Caminho F acima do acaso com TODOS os modelos-base no")
        print("  acaso. Pela regra registrada no plano (Fase 10), isso é bandeira")
        print("  de INVESTIGAÇÃO DE VAZAMENTO, não achado. Verificar a disciplina")
        print("  out-of-fold e a partição de folds antes de reportar.")
        print("!" * 70)

    print(f"\nCaminho F concluído — {out_dir}")


if __name__ == "__main__":
    main()
