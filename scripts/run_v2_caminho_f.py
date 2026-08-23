"""
Caminho F do experimento v2 — meta-classificador sobre as probabilidades
out-of-fold dos Caminhos A-E. Ver
docs/plano_experimento_v2/06_implementacao_passo_a_passo.md Fase 10.

**Disciplina out-of-fold é pré-requisito duro, não opcional** (correção da
revisão crítica do plano): a matriz de entrada do meta-modelo é montada
EXCLUSIVAMENTE a partir dos parquets de predição por amostra gravados por
`report_eval` durante a CV de cada caminho — nunca de refits. Cada linha
de validação de um fold foi predita por um modelo que não a viu no treino,
então o meta-modelo não herda vazamento dos modelos-base. Um `assert`
confere que os caminhos compartilham a MESMA partição de folds.

**Calibração (B6):** LinearSVC/SVM não têm `predict_proba` nativo; suas
"probabilidades" vêm de softmax sobre `decision_function`, que não é
calibrada. Antes de entrar no meta-modelo, cada coluna de probabilidade
passa por calibração isotônica ajustada em uma parte da validação — ECE
antes/depois é reportado.

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


def collect_oof(branch: str, run_id: str) -> pd.DataFrame:
    """
    Junta todos os parquets de predição por amostra dos Caminhos A-E,
    ficando só com as linhas de FOLD de CV (descarta `final*`, que vê o
    teste). Uma coluna de probabilidade por (caminho, modelo, classe).
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
            # Só folds de CV (out-of-fold); `final*` veria o teste.
            df = df[~df["fold"].astype(str).str.startswith("final")]
            if df.empty:
                continue
            frames.append(df)
    if not frames:
        raise FileNotFoundError(
            f"Nenhuma predição out-of-fold encontrada para run_id={run_id!r}, "
            f"braço={branch!r}. Rode antes a CV dos Caminhos A-E.")
    return pd.concat(frames, ignore_index=True)


def build_oof_matrix(oof: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """
    Pivota: uma linha por `sample_id`, uma coluna por
    (caminho, modelo, classe). Amostras sem predição de algum modelo são
    descartadas (o meta-modelo exige o vetor completo).
    """
    oof = oof.copy()
    oof["source"] = oof["caminho"] + "_" + oof["modelo"]
    n_classes = len(oof["y_proba"].iloc[0])

    wide: dict[str, pd.Series] = {}
    base = None
    per_source_ids: dict[str, set] = {}
    for source, grp in oof.groupby("source"):
        grp = grp.drop_duplicates(subset=["sample_id"]).set_index("sample_id")
        per_source_ids[source] = set(grp.index)
        proba = np.vstack(grp["y_proba"].to_numpy())
        for c in range(n_classes):
            wide[f"p_{source}_c{c}"] = pd.Series(proba[:, c], index=grp.index)
        if base is None:
            base = grp[["y_true", "key_id"]]

    # Diagnóstico ANTES do join: se as fontes não compartilham `sample_id`,
    # o inner join zera silenciosamente e o erro genérico ("matriz vazia")
    # não diz onde está o problema. Aqui reportamos quantas amostras cada
    # fonte tem e o tamanho da interseção — normalmente o culpado é um
    # caminho ter rodado sobre outra partição de folds ou outro subconjunto
    # de classes.
    common = set.intersection(*per_source_ids.values()) if per_source_ids else set()
    print("  amostras por fonte: "
          + ", ".join(f"{s}={len(ids)}" for s, ids in sorted(per_source_ids.items())))
    print(f"  interseção de sample_id entre TODAS as fontes: {len(common)}")
    if not common:
        raise RuntimeError(
            "Nenhum `sample_id` em comum entre as fontes de predição. As "
            "fontes precisam ter predito as MESMAS amostras (mesma partição "
            "de folds e mesmo conjunto de classes) para o meta-modelo "
            "existir. Fontes encontradas: "
            + ", ".join(f"{s} ({len(ids)} amostras)" for s, ids in sorted(per_source_ids.items()))
        )

    mat = pd.DataFrame(wide)
    mat = mat.join(base, how="inner").dropna()
    proba_cols = [c for c in mat.columns if c.startswith("p_")]
    return mat.reset_index().rename(columns={"index": "sample_id"}), proba_cols


def calibrate_columns(
    mat: pd.DataFrame, proba_cols: list[str], fit_mask: np.ndarray,
) -> tuple[pd.DataFrame, dict]:
    """
    Calibração isotônica por coluna de probabilidade, ajustada SÓ nas
    linhas de `fit_mask`. Reporta ECE agregado antes/depois.
    """
    out = mat.copy()
    y = mat["y_true"].to_numpy()
    n_classes = len({c.rsplit("_c", 1)[1] for c in proba_cols})

    def _ece_of(frame: pd.DataFrame) -> float:
        # ECE agregado sobre a média das fontes (visão global de calibração).
        by_class = []
        for c in range(n_classes):
            cols_c = [col for col in proba_cols if col.endswith(f"_c{c}")]
            by_class.append(frame[cols_c].to_numpy().mean(axis=1))
        proba = np.column_stack(by_class)
        proba = proba / np.clip(proba.sum(axis=1, keepdims=True), 1e-12, None)
        return expected_calibration_error(y, proba)

    ece_before = _ece_of(out)
    for col in proba_cols:
        cls = int(col.rsplit("_c", 1)[1])
        target = (y == cls).astype(float)
        iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
        iso.fit(out.loc[fit_mask, col].to_numpy(), target[fit_mask])
        out[col] = iso.predict(out[col].to_numpy())
    ece_after = _ece_of(out)
    return out, {"ece_before": round(float(ece_before), 4),
                 "ece_after": round(float(ece_after), 4)}


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

    print(f"Coletando predições out-of-fold (braço={args.branch})...")
    oof = collect_oof(args.branch, args.run_id)
    print(f"  {len(oof):,} linhas de predição, "
          f"caminhos={sorted(oof['caminho'].unique())}, "
          f"modelos={sorted(oof['modelo'].unique())}")

    mat, proba_cols = build_oof_matrix(oof)
    print(f"  matriz OOF: {len(mat):,} amostras x {len(proba_cols)} colunas de probabilidade")
    if mat.empty:
        raise RuntimeError("Matriz OOF vazia após o join — verifique se os "
                           "caminhos rodaram sobre a MESMA partição de folds.")

    # Assert de partição compartilhada: as chaves de validação vistas pelos
    # caminhos devem ser as mesmas (é o que torna as predições comparáveis).
    folds = json.loads(FOLDS_JSON.read_text(encoding="utf-8"))
    expected_keys = set(folds["trainval_keys"])
    got_keys = set(mat["key_id"].dropna().unique())
    unexpected = got_keys - expected_keys
    if unexpected:
        raise AssertionError(
            f"Predições OOF contêm chaves fora do trainval "
            f"(possível vazamento de teste): {sorted(unexpected)[:5]}")

    # Split do meta-modelo POR CHAVE (nunca por amostra) — o meta-modelo
    # herda a mesma disciplina de key-holdout dos modelos-base.
    keys = sorted(got_keys)
    rng = np.random.default_rng(SEED_MODEL)
    keys_perm = rng.permutation(keys)
    n_meta_test = max(1, len(keys_perm) // 5)
    meta_test_keys = set(keys_perm[:n_meta_test])
    is_test = mat["key_id"].isin(meta_test_keys).to_numpy()
    is_train = ~is_test

    mat_cal, ece_info = calibrate_columns(mat, proba_cols, fit_mask=is_train)
    print(f"  calibração isotônica: ECE {ece_info['ece_before']} -> {ece_info['ece_after']}")

    X = mat_cal[proba_cols].to_numpy(np.float64)
    y = mat_cal["y_true"].to_numpy()

    # sem `n_jobs`: sem efeito desde sklearn 1.8 e removido na 1.10.
    meta = LogisticRegression(max_iter=2000, random_state=SEED_MODEL)
    t0 = time.perf_counter()
    meta.fit(X[is_train], y[is_train])
    y_pred = meta.predict(X[is_test])
    y_proba = meta.predict_proba(X[is_test])

    report = report_eval(
        run_id=args.run_id, caminho="F", modelo="LogisticRegression_meta",
        braco=args.branch, fold="meta_test",
        y_true=y[is_test], y_pred=y_pred, y_proba=y_proba,
        sample_ids=mat_cal.loc[is_test, "sample_id"].tolist(),
        key_ids=mat_cal.loc[is_test, "key_id"].tolist(),
        class_names=REAL_ALGORITHMS, labels=list(range(len(REAL_ALGORITHMS))),
        out_dir=out_dir, n_bootstrap=args.n_bootstrap,
        extra={"n_sources": len(proba_cols), "calibration": ece_info,
               "n_meta_train": int(is_train.sum()), "n_meta_test": int(is_test.sum()),
               "train_time_s": round(time.perf_counter() - t0, 1)},
    )

    # Bandeira de vazamento: F acima do acaso com todos os bases no acaso.
    base_f1 = oof.groupby(["caminho", "modelo"]).apply(
        lambda g: float((np.vstack(g["y_proba"].to_numpy()).argmax(1)
                         == g["y_true"].to_numpy()).mean()), include_groups=False)
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
