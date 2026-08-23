"""
Caminho A do experimento v2 — classificadores clássicos sobre as 641
features. Ver docs/plano_experimento_v2/06_implementacao_passo_a_passo.md
Fase 6 e 03_classificadores.md §3.1.

Protocolo (inviolável — Regras de Ouro 1-7):
  - Split e folds SEMPRE lidos de `data/processed/v2_folds.json` (partição
    canônica, compartilhada por todos os Caminhos — nunca resplitar aqui).
  - Seletor de features fitado APENAS no treino de cada fold.
  - `len_pt`/`len_ct` NUNCA entram como feature (exceto na rodada
    explicitamente rotulada `sanity`, que existe justamente para provar
    que o encanamento detecta esse vazamento quando ele é injetado).
  - Todo relato passa por `report_eval` (função única) — nada de
    print/save de métrica fora dela.

Análises disponíveis (`--analysis`):
  4class          : Ascon x GIFT-COFB x Grain x Schwaemm (sem ECB/PRNG)
  pairs           : 6 comparações par-a-par entre os 4 algoritmos
  ecb_control     : controle positivo AES-ECB x Ascon
  prng_control    : PRNG x cada um dos 4 algoritmos (4 binários)
  sanity_lenct    : 4class COM `len_ct` de propósito (deve dar F1 alto nos
                    pares com Grain; senão há bug no encanamento)
  learning_curve  : F1 x nº de chaves de treino (30/60/120/240), RF e LR
  all             : 4class + pairs + ecb_control + prng_control

Uso:
    python scripts/run_v2_caminho_a.py --analysis 4class --branch controlado
    python scripts/run_v2_caminho_a.py --analysis all --branch controlado
    python scripts/run_v2_caminho_a.py --analysis 4class --branch controlado --no-keyholdout
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
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.model_selection import StratifiedKFold  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402
from sklearn.svm import SVC, LinearSVC  # noqa: E402
from xgboost import XGBClassifier  # noqa: E402

from src.eval.reporting import report_eval  # noqa: E402
from src.features.selector import LWCFeatureSelector, SelectorConfig  # noqa: E402

DATASET_ID = "keyholdout_5class_v2"
PROCESSED = REPO_ROOT / "data" / "processed"
FOLDS_JSON = PROCESSED / "v2_folds.json"
OUT_ROOT = REPO_ROOT / "reports" / "v2" / "caminho_a"

SEED_MODEL = 7
SEED_SELECTOR = 13
SEED_SPLIT = 42

REAL_ALGORITHMS = ["Ascon-AEAD128", "GIFT-COFB", "Grain-128AEAD", "Schwaemm256-128"]

# Metadados do parquet de features — nunca entram como feature.
# `len_pt`/`len_ct` estão aqui de propósito (Regra de Ouro 5); a rodada
# `sanity_lenct` os reinsere explicitamente, e só ela.
_NON_FEATURE_COLS = {
    "sample_id", "algorithm", "key_id", "nonce_id", "branch",
    "len_pt", "len_ct", "len_ad", "plaintext_source", "plaintext_sha256",
    "image_id", "mode", "impl", "seed", "version", "timestamp", "ciphertext",
    # `y` é o rótulo codificado, criado por `run_analysis` ANTES de
    # selecionar as colunas de feature. Sem esta entrada ele entrava como
    # feature e o classificador lia a resposta direto — vazamento total
    # (detectado na validação: o seletor reportava 642 features em vez de
    # 641, e todo modelo dava F1=1,000).
    "y",
}

# Subamostra para a busca de hiperparâmetros do SVM. Motivo (dado real do
# v1): a busca em grade completa custou 139min a 38.400 amostras/fold;
# no v2 (76.800/fold) extrapolaria para 15-30h+. Busca em subamostra +
# fit final único no fold completo — decisão aceita no planejamento.
SVM_SEARCH_SUBSAMPLE = 6000
SVM_GRID = [
    {"C": c, "gamma": g}
    for c in (1.0, 10.0)
    for g in ("scale", 0.01)
]


# ---------------------------------------------------------------------------
# Carregamento
# ---------------------------------------------------------------------------

# Configuração do seletor, ajustável por CLI. Os defaults do plano
# (`top_k_mi=350`, `n_features_mrmr=150`, `boruta_max_iter=100`) são caros
# com 641 features: mRMR e sobretudo Boruta dominam o tempo de cada fold.
# `--selector-preset rapido` existe para validação de encanamento e para
# rodadas exploratórias — NUNCA para o resultado oficial, que usa `pleno`.
_SELECTOR_PRESETS = {
    "pleno": dict(top_k_mi=350, n_features_mrmr=150, boruta_max_iter=100),
    "rapido": dict(top_k_mi=60, n_features_mrmr=20, boruta_max_iter=10),
}
_SELECTOR_PRESET = "pleno"


def _selector_config() -> SelectorConfig:
    return SelectorConfig(random_state=SEED_SELECTOR, **_SELECTOR_PRESETS[_SELECTOR_PRESET])


def load_features(branch: str) -> pd.DataFrame:
    path = PROCESSED / f"{DATASET_ID}_features_{branch}.parquet"
    if not path.exists():
        raise FileNotFoundError(
            f"Features não encontradas: {path}\nRode antes:\n"
            f"  python scripts/extract_features_v2.py --branch {branch}\n"
            f"  python scripts/extract_features_v2.py --branch {branch} --consolidate"
        )
    df = pd.read_parquet(path)
    print(f"Features carregadas: {path.name} — {len(df):,} linhas x {len(df.columns)} colunas")
    return df


def load_folds() -> dict:
    if not FOLDS_JSON.exists():
        raise FileNotFoundError(
            f"Partição de folds não encontrada: {FOLDS_JSON}\n"
            "Rode antes: python scripts/generate_5class_v2.py"
        )
    return json.loads(FOLDS_JSON.read_text(encoding="utf-8"))


def feature_columns(df: pd.DataFrame, include_len_ct: bool = False) -> list[str]:
    """
    Colunas de feature = tudo que não é metadado nem rótulo.

    Asserts de vazamento (baratos e valem a pena — um deles já pegou o
    rótulo `y` entrando como feature durante a validação):
      1. nenhuma coluna não-numérica escapa como feature;
      2. `y`/`algorithm` nunca entram;
      3. `len_ct`/`len_pt` só entram quando pedidos explicitamente
         (rodada `sanity`, Regra de Ouro 5).
    """
    cols = [c for c in df.columns if c not in _NON_FEATURE_COLS]

    leaked = {"y", "algorithm", "key_id", "sample_id"} & set(cols)
    if leaked:
        raise AssertionError(f"VAZAMENTO: rótulo/metadado entre as features: {sorted(leaked)}")
    non_numeric = [c for c in cols if not pd.api.types.is_numeric_dtype(df[c])]
    if non_numeric:
        raise AssertionError(f"Colunas não-numéricas entre as features: {non_numeric[:10]}")
    if not include_len_ct and ({"len_ct", "len_pt"} & set(cols)):
        raise AssertionError("len_ct/len_pt entre as features fora da rodada `sanity`")

    if include_len_ct:
        cols = cols + ["len_ct"]
    return cols


# ---------------------------------------------------------------------------
# Modelos
# ---------------------------------------------------------------------------

def build_models(seed: int = SEED_MODEL) -> dict:
    """RF, LinearSVC, XGBoost, LR. O SVM-RBF entra à parte (busca de
    hiperparâmetros própria — ver `fit_svm_with_search`). Sem Dummy: o
    nível de acaso é conhecido analiticamente (1/n_classes) e já entra
    como referência nos relatórios."""
    return {
        "RandomForest": RandomForestClassifier(
            n_estimators=500, n_jobs=-1, random_state=seed, class_weight="balanced",
        ),
        "LinearSVC": LinearSVC(C=1.0, random_state=seed, max_iter=5000, dual="auto"),
        "XGBoost": XGBClassifier(
            n_estimators=500, max_depth=6, learning_rate=0.1,
            random_state=seed, n_jobs=-1, eval_metric="mlogloss", tree_method="hist",
        ),
        "LogisticRegression": LogisticRegression(
            max_iter=2000, random_state=seed, n_jobs=-1,
        ),
    }


def fit_svm_with_search(
    X_train: np.ndarray, y_train: np.ndarray, seed: int = SEED_MODEL,
) -> tuple[SVC, dict]:
    """
    SVM-RBF com busca de hiperparâmetros em SUBAMOSTRA e fit final no
    fold completo (ver constante SVM_SEARCH_SUBSAMPLE para o motivo).
    A busca usa CV estratificada interna sobre a subamostra; o vencedor
    é refitado no conjunto de treino inteiro do fold.
    """
    rng = np.random.default_rng(seed)
    n = len(y_train)
    if n > SVM_SEARCH_SUBSAMPLE:
        idx = rng.choice(n, size=SVM_SEARCH_SUBSAMPLE, replace=False)
        Xs, ys = X_train[idx], y_train[idx]
    else:
        Xs, ys = X_train, y_train

    best_score, best_params = -np.inf, SVM_GRID[0]
    inner_cv = StratifiedKFold(n_splits=3, shuffle=True, random_state=seed)
    for params in SVM_GRID:
        scores = []
        for tr, va in inner_cv.split(Xs, ys):
            m = SVC(kernel="rbf", random_state=seed, **params)
            m.fit(Xs[tr], ys[tr])
            scores.append(m.score(Xs[va], ys[va]))
        mean_score = float(np.mean(scores))
        if mean_score > best_score:
            best_score, best_params = mean_score, params

    final = SVC(kernel="rbf", random_state=seed, probability=False, **best_params)
    final.fit(X_train, y_train)
    return final, {**best_params, "search_subsample": min(n, SVM_SEARCH_SUBSAMPLE)}


def get_proba(model, X: np.ndarray) -> np.ndarray | None:
    """Probabilidades por classe. Para modelos sem `predict_proba`
    (LinearSVC, SVC sem probability), converte `decision_function` via
    softmax — suficiente para ECE/AUC e para alimentar o Caminho F, que
    recalibra explicitamente (Platt/isotônica) antes de usar."""
    if hasattr(model, "predict_proba"):
        try:
            return model.predict_proba(X)
        except Exception:
            pass
    if hasattr(model, "decision_function"):
        scores = model.decision_function(X)
        if scores.ndim == 1:
            scores = np.column_stack([-scores, scores])
        exp_s = np.exp(scores - scores.max(axis=1, keepdims=True))
        return exp_s / exp_s.sum(axis=1, keepdims=True)
    return None


# ---------------------------------------------------------------------------
# Núcleo: uma análise = subconjunto de classes + CV + teste final
# ---------------------------------------------------------------------------

def run_analysis(
    df: pd.DataFrame,
    folds: dict,
    analysis_name: str,
    classes: list[str],
    branch: str,
    out_dir: Path,
    include_len_ct: bool = False,
    keyholdout: bool = True,
    n_bootstrap: int = 1000,
    models_subset: list[str] | None = None,
) -> None:
    """
    Roda uma análise completa: 5-fold CV por chave + modelo final no
    holdout de teste, para cada modelo. Tudo relatado por `report_eval`.

    `keyholdout=False` é o braço da ablação: split ALEATÓRIO POR AMOSTRA
    (ignora `key_id`), estratificado por classe, com os mesmos tamanhos
    do split por chave e seed 42 — ver 04_protocolo §4.2.
    """
    sub = df[df["algorithm"].isin(classes)].copy()
    if sub.empty:
        raise ValueError(f"Nenhuma amostra para as classes {classes}")

    label_map = {c: i for i, c in enumerate(classes)}
    sub["y"] = sub["algorithm"].map(label_map)
    feat_cols = feature_columns(sub, include_len_ct=include_len_ct)

    test_keys = set(folds["test_keys"])
    trainval_keys = set(folds["trainval_keys"])

    if keyholdout:
        test_mask = sub["key_id"].isin(test_keys)
    else:
        # Ablação: split aleatório por amostra, estratificado por classe,
        # com o MESMO tamanho de teste do split por chave (para que a
        # comparação isole o efeito do key-holdout, não o do tamanho).
        n_test = int(sub["key_id"].isin(test_keys).sum())
        rng = np.random.default_rng(SEED_SPLIT)
        test_idx: list[int] = []
        for cls in classes:
            cls_pos = np.flatnonzero((sub["algorithm"] == cls).to_numpy())
            n_cls = int(round(n_test * len(cls_pos) / len(sub)))
            test_idx.extend(rng.choice(cls_pos, size=min(n_cls, len(cls_pos)),
                                       replace=False).tolist())
        test_mask = np.zeros(len(sub), dtype=bool)
        test_mask[np.array(test_idx, dtype=int)] = True
        test_mask = pd.Series(test_mask, index=sub.index)

    trainval_df = sub[~test_mask]
    test_df = sub[test_mask]

    tv_keys_set = set(trainval_df["key_id"].unique())
    tst_keys_set = set(test_df["key_id"].unique())
    if keyholdout:
        overlap = tv_keys_set & tst_keys_set
        if overlap:
            raise ValueError(f"VAZAMENTO: chaves em trainval∩test = {sorted(overlap)[:5]}")

    braco = f"{branch}" + ("" if keyholdout else "_sem_keyholdout")
    print(f"\n{'=' * 70}\n  Análise: {analysis_name} | braço: {braco}\n"
          f"  classes: {classes}\n"
          f"  trainval={len(trainval_df):,}  test={len(test_df):,}  "
          f"features={len(feat_cols)}\n{'=' * 70}")

    all_models = build_models()
    if models_subset:
        all_models = {k: v for k, v in all_models.items() if k in models_subset}
    use_svm = (models_subset is None) or ("SVM-RBF" in models_subset)

    # ---------------- CV por fold ----------------
    for fold_spec in folds["folds"]:
        fold_idx = fold_spec["fold"]
        if keyholdout:
            tr_mask = trainval_df["key_id"].isin(set(fold_spec["train_keys"]))
            va_mask = trainval_df["key_id"].isin(set(fold_spec["val_keys"]))
        else:
            # Sem key-holdout: reparticiona o trainval aleatoriamente por
            # amostra, mantendo a proporção de folds (4/5 treino, 1/5 val).
            rng = np.random.default_rng(SEED_SPLIT + fold_idx)
            perm = rng.permutation(len(trainval_df))
            cut = int(len(trainval_df) * 0.8)
            tr_pos, va_pos = perm[:cut], perm[cut:]
            tr_mask = np.zeros(len(trainval_df), dtype=bool); tr_mask[tr_pos] = True
            va_mask = np.zeros(len(trainval_df), dtype=bool); va_mask[va_pos] = True
            tr_mask = pd.Series(tr_mask, index=trainval_df.index)
            va_mask = pd.Series(va_mask, index=trainval_df.index)

        tr = trainval_df[tr_mask]
        va = trainval_df[va_mask]
        if len(tr) == 0 or len(va) == 0:
            print(f"  [fold {fold_idx}] vazio, pulando")
            continue

        X_tr_raw = tr[feat_cols].to_numpy(dtype=np.float64)
        X_va_raw = va[feat_cols].to_numpy(dtype=np.float64)
        y_tr = tr["y"].to_numpy()
        y_va = va["y"].to_numpy()

        t0 = time.perf_counter()
        sel = LWCFeatureSelector(_selector_config())
        sel.fit(X_tr_raw, y_tr, feature_names=feat_cols)
        X_tr = sel.transform(X_tr_raw)
        X_va = sel.transform(X_va_raw)
        sel_report = sel.get_stage_report()
        print(f"  [fold {fold_idx}] seletor: {len(feat_cols)} -> "
              f"VT={sel_report['stage1_after_variance']} MI={sel_report['stage1_output']} "
              f"mRMR={sel_report['stage2_output']} Boruta(diag)="
              f"{sel_report['stage3_boruta_confirmed']}  ({time.perf_counter() - t0:.0f}s)")

        scaler = StandardScaler().fit(X_tr)
        X_tr_s, X_va_s = scaler.transform(X_tr), scaler.transform(X_va)

        fold_models = dict(all_models)
        for name, model in fold_models.items():
            t_fit = time.perf_counter()
            Xa, Xb = (X_tr_s, X_va_s) if name in ("LinearSVC", "LogisticRegression") else (X_tr, X_va)
            model.fit(Xa, y_tr)
            y_pred = model.predict(Xb)
            report_eval(
                run_id=f"{DATASET_ID}_{analysis_name}", caminho="A", modelo=name,
                braco=braco, fold=fold_idx,
                y_true=y_va, y_pred=y_pred, y_proba=get_proba(model, Xb),
                sample_ids=va["sample_id"].tolist(), key_ids=va["key_id"].tolist(),
                class_names=classes, labels=list(range(len(classes))),
                out_dir=out_dir, n_bootstrap=n_bootstrap,
                extra={"train_time_s": round(time.perf_counter() - t_fit, 1),
                       "selector": sel_report, "n_features_used": int(X_tr.shape[1])},
            )

        if use_svm:
            t_fit = time.perf_counter()
            svm, svm_params = fit_svm_with_search(X_tr_s, y_tr)
            report_eval(
                run_id=f"{DATASET_ID}_{analysis_name}", caminho="A", modelo="SVM-RBF",
                braco=braco, fold=fold_idx,
                y_true=y_va, y_pred=svm.predict(X_va_s), y_proba=get_proba(svm, X_va_s),
                sample_ids=va["sample_id"].tolist(), key_ids=va["key_id"].tolist(),
                class_names=classes, labels=list(range(len(classes))),
                out_dir=out_dir, n_bootstrap=n_bootstrap,
                extra={"train_time_s": round(time.perf_counter() - t_fit, 1),
                       "best_params": svm_params, "n_features_used": int(X_tr.shape[1])},
            )

    # ---------------- Modelo final: trainval completo -> teste ----------------
    print(f"\n  --- modelo final (trainval completo -> teste) ---")
    X_tv_raw = trainval_df[feat_cols].to_numpy(dtype=np.float64)
    X_te_raw = test_df[feat_cols].to_numpy(dtype=np.float64)
    y_tv = trainval_df["y"].to_numpy()
    y_te = test_df["y"].to_numpy()

    sel = LWCFeatureSelector(SelectorConfig(random_state=SEED_SELECTOR))
    sel.fit(X_tv_raw, y_tv, feature_names=feat_cols)
    X_tv, X_te = sel.transform(X_tv_raw), sel.transform(X_te_raw)
    sel_report = sel.get_stage_report()
    scaler = StandardScaler().fit(X_tv)
    X_tv_s, X_te_s = scaler.transform(X_tv), scaler.transform(X_te)

    for name, model in build_models().items():
        if models_subset and name not in models_subset:
            continue
        t_fit = time.perf_counter()
        Xa, Xb = (X_tv_s, X_te_s) if name in ("LinearSVC", "LogisticRegression") else (X_tv, X_te)
        model.fit(Xa, y_tv)
        report_eval(
            run_id=f"{DATASET_ID}_{analysis_name}", caminho="A", modelo=name,
            braco=braco, fold="final",
            y_true=y_te, y_pred=model.predict(Xb), y_proba=get_proba(model, Xb),
            sample_ids=test_df["sample_id"].tolist(), key_ids=test_df["key_id"].tolist(),
            class_names=classes, labels=list(range(len(classes))),
            out_dir=out_dir, n_bootstrap=n_bootstrap,
            extra={"train_time_s": round(time.perf_counter() - t_fit, 1),
                   "selector": sel_report,
                   "selected_features": sel.get_selected_names()},
        )

    if use_svm:
        t_fit = time.perf_counter()
        svm, svm_params = fit_svm_with_search(X_tv_s, y_tv)
        report_eval(
            run_id=f"{DATASET_ID}_{analysis_name}", caminho="A", modelo="SVM-RBF",
            braco=braco, fold="final",
            y_true=y_te, y_pred=svm.predict(X_te_s), y_proba=get_proba(svm, X_te_s),
            sample_ids=test_df["sample_id"].tolist(), key_ids=test_df["key_id"].tolist(),
            class_names=classes, labels=list(range(len(classes))),
            out_dir=out_dir, n_bootstrap=n_bootstrap,
            extra={"train_time_s": round(time.perf_counter() - t_fit, 1),
                   "best_params": svm_params},
        )


# ---------------------------------------------------------------------------
# Análises
# ---------------------------------------------------------------------------

def analysis_4class(df, folds, branch, out_dir, **kw) -> None:
    run_analysis(df, folds, "4class", REAL_ALGORITHMS, branch, out_dir, **kw)


def analysis_pairs(df, folds, branch, out_dir, **kw) -> None:
    from itertools import combinations
    for a, b in combinations(REAL_ALGORITHMS, 2):
        name = f"pair_{a.split('-')[0]}_vs_{b.split('-')[0]}"
        run_analysis(df, folds, name, [a, b], branch, out_dir, **kw)


def analysis_ecb_control(df, folds, branch, out_dir, **kw) -> None:
    run_analysis(df, folds, "control_ecb_vs_ascon",
                 ["AES-128-ECB", "Ascon-AEAD128"], branch, out_dir, **kw)


def analysis_prng_control(df, folds, branch, out_dir, **kw) -> None:
    for algo in REAL_ALGORITHMS:
        name = f"control_prng_vs_{algo.split('-')[0]}"
        run_analysis(df, folds, name, ["PRNG", algo], branch, out_dir, **kw)


def analysis_sanity_lenct(df, folds, branch, out_dir, **kw) -> None:
    """Sanity de encanamento: inclui `len_ct` DE PROPÓSITO. Pares com
    Grain (len_ct 65.544 vs 65.552) devem dar F1 > 0,95 — se não derem,
    há bug no pipeline. Rodada fora das tabelas de resultado."""
    kw = {**kw, "include_len_ct": True, "models_subset": ["RandomForest"]}
    run_analysis(df, folds, "sanity_lenct_grain_vs_ascon",
                 ["Grain-128AEAD", "Ascon-AEAD128"], branch, out_dir, **kw)


def analysis_learning_curve(df, folds, branch, out_dir, **kw) -> None:
    """F1 x nº de chaves de treino (por chave, nunca por amostra), com
    teste FIXO — responde 'faltaram dados?' se o resultado for nulo."""
    sub = df[df["algorithm"].isin(REAL_ALGORITHMS)].copy()
    label_map = {c: i for i, c in enumerate(REAL_ALGORITHMS)}
    sub["y"] = sub["algorithm"].map(label_map)
    feat_cols = feature_columns(sub)

    test_keys = set(folds["test_keys"])
    trainval_keys = list(folds["trainval_keys"])
    test_df = sub[sub["key_id"].isin(test_keys)]
    X_te_raw = test_df[feat_cols].to_numpy(dtype=np.float64)
    y_te = test_df["y"].to_numpy()

    for n_keys in (30, 60, 120, 240):
        keys_subset = set(trainval_keys[:n_keys])
        tr = sub[sub["key_id"].isin(keys_subset)]
        if tr.empty:
            continue
        X_tr_raw = tr[feat_cols].to_numpy(dtype=np.float64)
        y_tr = tr["y"].to_numpy()

        sel = LWCFeatureSelector(_selector_config())
        sel.fit(X_tr_raw, y_tr, feature_names=feat_cols)
        X_tr, X_te = sel.transform(X_tr_raw), sel.transform(X_te_raw)
        scaler = StandardScaler().fit(X_tr)

        for name in ("RandomForest", "LogisticRegression"):
            model = build_models()[name]
            Xa, Xb = ((scaler.transform(X_tr), scaler.transform(X_te))
                      if name == "LogisticRegression" else (X_tr, X_te))
            model.fit(Xa, y_tr)
            report_eval(
                run_id=f"{DATASET_ID}_learning_curve", caminho="A", modelo=name,
                braco=branch, fold=f"nkeys{n_keys}",
                y_true=y_te, y_pred=model.predict(Xb), y_proba=get_proba(model, Xb),
                sample_ids=test_df["sample_id"].tolist(),
                key_ids=test_df["key_id"].tolist(),
                class_names=REAL_ALGORITHMS, labels=list(range(len(REAL_ALGORITHMS))),
                out_dir=out_dir, n_bootstrap=kw.get("n_bootstrap", 1000),
                extra={"n_train_keys": n_keys, "n_train_samples": int(len(tr))},
            )


ANALYSES = {
    "4class": analysis_4class,
    "pairs": analysis_pairs,
    "ecb_control": analysis_ecb_control,
    "prng_control": analysis_prng_control,
    "sanity_lenct": analysis_sanity_lenct,
    "learning_curve": analysis_learning_curve,
}


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser()
    parser.add_argument("--analysis", default="4class",
                        choices=list(ANALYSES) + ["all"])
    # `sintetico` não é um braço do experimento: é um parquet de features
    # aleatórias com o MESMO schema, usado só para validar o encanamento
    # (folds, seletor, modelos, relato) sem esperar as ~20h da extração
    # real. Nunca deve aparecer em tabela de resultado.
    parser.add_argument("--branch", default="controlado",
                        choices=["cru", "controlado", "shuffled", "sintetico"])
    parser.add_argument("--no-keyholdout", action="store_true",
                        help="Braço da ablação: split aleatório por amostra.")
    parser.add_argument("--n-bootstrap", type=int, default=1000)
    parser.add_argument("--models", default=None,
                        help="Lista separada por vírgula (ex.: RandomForest,LogisticRegression)")
    parser.add_argument("--selector-preset", default="pleno",
                        choices=list(_SELECTOR_PRESETS),
                        help="`pleno` = configuração oficial do plano; "
                             "`rapido` = só para validar encanamento/exploração.")
    args = parser.parse_args()

    global _SELECTOR_PRESET
    _SELECTOR_PRESET = args.selector_preset
    if _SELECTOR_PRESET != "pleno":
        print(f"[AVISO] seletor em preset '{_SELECTOR_PRESET}' "
              f"({_SELECTOR_PRESETS[_SELECTOR_PRESET]}) — NÃO use para resultado oficial.")

    df = load_features(args.branch)
    folds = load_folds()
    out_dir = OUT_ROOT / args.branch
    out_dir.mkdir(parents=True, exist_ok=True)

    kw = {
        "keyholdout": not args.no_keyholdout,
        "n_bootstrap": args.n_bootstrap,
        "models_subset": args.models.split(",") if args.models else None,
    }

    names = (["4class", "pairs", "ecb_control", "prng_control"]
             if args.analysis == "all" else [args.analysis])

    t0 = time.perf_counter()
    for name in names:
        fn = ANALYSES[name]
        if name == "learning_curve":
            fn(df, folds, args.branch, out_dir, n_bootstrap=args.n_bootstrap)
        elif name == "sanity_lenct":
            fn(df, folds, args.branch, out_dir,
               keyholdout=kw["keyholdout"], n_bootstrap=args.n_bootstrap)
        else:
            fn(df, folds, args.branch, out_dir, **kw)

    print(f"\nCaminho A concluído em {(time.perf_counter() - t0) / 60:.1f}min. "
          f"Resultados em {out_dir}")


if __name__ == "__main__":
    main()
