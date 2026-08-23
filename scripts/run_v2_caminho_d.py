"""
Caminho D do experimento v2 — híbrido com 4 representações. Ver
docs/plano_experimento_v2/06_implementacao_passo_a_passo.md Fase 9.

Vetor de entrada por amostra:
    [ ~641 features clássicas | latente CNN1D | latente CNN2D | latente Transformer ]

Os latentes vêm dos parquets/npy salvos pelo `run_v2_caminhos_bce.py`
(modo `cv` para os folds e `final` para o teste), cada um acompanhado de
um índice com `sample_id` — o alinhamento é feito por **merge em
`sample_id`**, nunca por posição de linha.

Pesos das redes CONGELADOS (os latentes já são a saída de modelos
treinados no fold correspondente) — o Caminho D só treina o classificador
final (RF/XGBoost) sobre a concatenação, com o seletor fitado dentro do
fold, como em todos os outros caminhos.

Uso:
    python scripts/run_v2_caminho_d.py --branch controlado
    python scripts/run_v2_caminho_d.py --branch controlado --paths B,C
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
from sklearn.ensemble import RandomForestClassifier  # noqa: E402
from xgboost import XGBClassifier  # noqa: E402

from src.eval.reporting import report_eval  # noqa: E402
from src.features.selector import LWCFeatureSelector, SelectorConfig  # noqa: E402

DATASET_ID = "keyholdout_5class_v2"
PROCESSED = REPO_ROOT / "data" / "processed"
FOLDS_JSON = PROCESSED / "v2_folds.json"
REPORTS = REPO_ROOT / "reports" / "v2"
OUT_ROOT = REPORTS / "caminho_d"

REAL_ALGORITHMS = ["Ascon-AEAD128", "GIFT-COFB", "Grain-128AEAD", "Schwaemm256-128"]
SEED_MODEL = 7
SEED_SELECTOR = 13

_NON_FEATURE_COLS = {
    "sample_id", "algorithm", "key_id", "nonce_id", "branch", "y",
    "len_pt", "len_ct", "len_ad", "plaintext_source", "plaintext_sha256",
    "image_id", "mode", "impl", "seed", "version", "timestamp", "ciphertext",
}


def load_latents(path: str, branch: str, tag: str) -> pd.DataFrame | None:
    """Carrega latente + índice de um caminho profundo. Retorna None se
    aquele caminho ainda não foi rodado (o híbrido então roda com as
    representações disponíveis, registrando quais)."""
    d = REPORTS / f"caminho_{path.lower()}" / branch
    npy = d / f"latents_{path}_{branch}_{tag}.npy"
    idx = d / f"latents_{path}_{branch}_{tag}_index.parquet"
    if not npy.exists() or not idx.exists():
        return None
    lat = np.load(npy)
    index = pd.read_parquet(idx)
    if len(index) != len(lat):
        raise AssertionError(
            f"Latente e índice desalinhados em {npy.name}: "
            f"{len(lat)} linhas x {len(index)} do índice"
        )
    cols = {f"lat{path}_{i:03d}": lat[:, i] for i in range(lat.shape[1])}
    return pd.concat([index[["sample_id"]], pd.DataFrame(cols)], axis=1)


def build_matrix(feat_df: pd.DataFrame, sample_ids: list[str], branch: str,
                 tag: str, paths: list[str]) -> tuple[pd.DataFrame, list[str]]:
    """
    Monta [features clássicas | latentes] alinhado por `sample_id`.

    Returns:
        (dataframe, lista dos caminhos profundos efetivamente usados)
    """
    base = feat_df[feat_df["sample_id"].isin(set(sample_ids))].copy()
    used: list[str] = []
    for p in paths:
        lat_df = load_latents(p, branch, tag)
        if lat_df is None:
            print(f"  [aviso] latentes do Caminho {p} ({tag}) não encontrados — "
                  f"seguindo sem essa representação")
            continue
        before = len(base)
        base = base.merge(lat_df, on="sample_id", how="inner")
        if len(base) == 0:
            raise AssertionError(f"merge com latentes do Caminho {p} zerou as linhas")
        if len(base) < before:
            print(f"  [aviso] merge com Caminho {p}: {before} -> {len(base)} linhas")
        used.append(p)
    return base, used


def feature_cols(df: pd.DataFrame) -> list[str]:
    cols = [c for c in df.columns if c not in _NON_FEATURE_COLS]
    leaked = {"y", "algorithm"} & set(cols)
    if leaked:
        raise AssertionError(f"VAZAMENTO: rótulo entre as features: {sorted(leaked)}")
    return cols


def build_models(seed: int = SEED_MODEL) -> dict:
    return {
        "RandomForest": RandomForestClassifier(
            n_estimators=500, n_jobs=-1, random_state=seed, class_weight="balanced"),
        "XGBoost": XGBClassifier(
            n_estimators=500, max_depth=6, learning_rate=0.1, random_state=seed,
            n_jobs=-1, eval_metric="mlogloss", tree_method="hist"),
    }


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    p = argparse.ArgumentParser()
    p.add_argument("--branch", default="controlado", choices=["cru", "controlado"])
    p.add_argument("--paths", default="B,C,E",
                   help="Caminhos profundos cujos latentes entram no híbrido.")
    p.add_argument("--n-bootstrap", type=int, default=1000)
    args = p.parse_args()

    paths = [s.strip() for s in args.paths.split(",") if s.strip()]
    feat_path = PROCESSED / f"{DATASET_ID}_features_{args.branch}.parquet"
    if not feat_path.exists():
        raise FileNotFoundError(
            f"Features não encontradas: {feat_path}\n"
            f"Rode antes: python scripts/extract_features_v2.py --branch {args.branch}")
    feat_df = pd.read_parquet(feat_path)
    label_map = {c: i for i, c in enumerate(REAL_ALGORITHMS)}
    feat_df = feat_df[feat_df["algorithm"].isin(label_map)].copy()
    feat_df["y"] = feat_df["algorithm"].map(label_map)

    folds = json.loads(FOLDS_JSON.read_text(encoding="utf-8"))
    out_dir = OUT_ROOT / args.branch
    out_dir.mkdir(parents=True, exist_ok=True)

    def _fit_eval(tr_df, va_df, cols, used, braco, fold_tag, n_bootstrap):
        X_tr, y_tr = tr_df[cols].to_numpy(np.float64), tr_df["y"].to_numpy()
        X_va, y_va = va_df[cols].to_numpy(np.float64), va_df["y"].to_numpy()

        sel = LWCFeatureSelector(SelectorConfig(random_state=SEED_SELECTOR))
        sel.fit(X_tr, y_tr, feature_names=cols)
        X_tr_s, X_va_s = sel.transform(X_tr), sel.transform(X_va)
        print(f"[{fold_tag}] representações={['A'] + used}  "
              f"dim={len(cols)} -> {X_tr_s.shape[1]}  "
              f"treino={len(tr_df)} val={len(va_df)}")

        for name, model in build_models().items():
            t_fit = time.perf_counter()
            model.fit(X_tr_s, y_tr)
            proba = (model.predict_proba(X_va_s)
                     if hasattr(model, "predict_proba") else None)
            report_eval(
                run_id=f"{DATASET_ID}_4class", caminho="D", modelo=name,
                braco=braco, fold=fold_tag,
                y_true=y_va, y_pred=model.predict(X_va_s), y_proba=proba,
                sample_ids=va_df["sample_id"].tolist(),
                key_ids=va_df["key_id"].tolist() if "key_id" in va_df else None,
                class_names=REAL_ALGORITHMS, labels=list(range(len(REAL_ALGORITHMS))),
                out_dir=out_dir, n_bootstrap=n_bootstrap,
                extra={"representations": ["A"] + used,
                       "input_dim": len(cols),
                       "selected_dim": int(X_tr_s.shape[1]),
                       "train_time_s": round(time.perf_counter() - t_fit, 1),
                       "selector": sel.get_stage_report()},
            )

    t0 = time.perf_counter()
    for fold_spec in folds["folds"]:
        fi = fold_spec["fold"]
        tr_keys, va_keys = set(fold_spec["train_keys"]), set(fold_spec["val_keys"])
        tr_ids = feat_df.loc[feat_df["key_id"].isin(tr_keys), "sample_id"].tolist()
        va_ids = feat_df.loc[feat_df["key_id"].isin(va_keys), "sample_id"].tolist()

        # Correção de alinhamento (achada na verificação de aderência): a
        # versão anterior montava o treino do híbrido concatenando latentes
        # de VALIDAÇÃO de OUTROS folds — cada fold treina uma rede B/C/E
        # independente (init e dados diferentes), então esses espaços
        # latentes não são o mesmo espaço vetorial. `latB_000` não
        # significava a mesma coisa nas linhas de treino e nas de validação.
        # Agora treino e validação usam SEMPRE a rede DESTE MESMO fold:
        # `fold{fi}_train` para o treino do híbrido, `fold{fi}` (validação)
        # para a avaliação — como o `HybridExtractor` do v1 já fazia.
        tr_df, used_tr = build_matrix(feat_df, tr_ids, args.branch, f"fold{fi}_train", paths)
        va_df, used_va = build_matrix(feat_df, va_ids, args.branch, f"fold{fi}", paths)
        used = [pth for pth in used_tr if pth in used_va]
        if len(used) < len(paths):
            missing = set(paths) - set(used)
            print(f"[fold {fi}] representações incompletas em algum lado "
                  f"(treino={used_tr}, val={used_va}) — usando só {['A'] + used}. "
                  f"Faltando: {sorted(missing)}")

        cols = feature_cols(tr_df)
        cols = [c for c in cols if c in va_df.columns]
        _fit_eval(tr_df, va_df, cols, used, args.branch, fi, args.n_bootstrap)

    # ---------------- Modelo final: trainval completo -> teste ----------------
    # Usa a rede final (seed 7, mesma seed principal das demais). Os latentes
    # do trainval final vêm de `run_v2_caminhos_bce.py --mode final`, que
    # agora salva ambos os lados (ver correção do bug de teste-como-validação
    # naquele script).
    tv_keys, te_keys = set(folds["trainval_keys"]), set(folds["test_keys"])
    tv_ids = feat_df.loc[feat_df["key_id"].isin(tv_keys), "sample_id"].tolist()
    te_ids = feat_df.loc[feat_df["key_id"].isin(te_keys), "sample_id"].tolist()
    tv_df, used_tv = build_matrix(feat_df, tv_ids, args.branch, "final_s7_trainval", paths)
    te_df, used_te = build_matrix(feat_df, te_ids, args.branch, "final_s7", paths)
    used_final = [pth for pth in used_tv if pth in used_te]
    if not used_final:
        print("\n[final] nenhum latente final encontrado (rode "
              "`run_v2_caminhos_bce.py --mode final` antes) — pulando modelo final do D.")
    else:
        cols = feature_cols(tv_df)
        cols = [c for c in cols if c in te_df.columns]
        _fit_eval(tv_df, te_df, cols, used_final, args.branch, "final", args.n_bootstrap)

    print(f"\nCaminho D concluído em {(time.perf_counter() - t0) / 60:.1f}min — {out_dir}")


if __name__ == "__main__":
    main()
