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
from lightgbm import LGBMClassifier  # noqa: E402
from sklearn.base import BaseEstimator, ClassifierMixin, clone  # noqa: E402
from sklearn.ensemble import (  # noqa: E402
    RandomForestClassifier, StackingClassifier, VotingClassifier,
)
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import f1_score  # noqa: E402
from sklearn.model_selection import GroupKFold  # noqa: E402
from sklearn.neighbors import KNeighborsClassifier  # noqa: E402
from sklearn.pipeline import Pipeline  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402
from sklearn.svm import SVC, LinearSVC  # noqa: E402
from xgboost import XGBClassifier  # noqa: E402

from src.eval.reporting import report_eval  # noqa: E402
from src.features.families.nist_sts import _feature_keys as _nist_feature_keys  # noqa: E402
from src.features.selector import LWCFeatureSelector, SelectorConfig  # noqa: E402
from src.models.e20_classifier import E20Classifier  # noqa: E402
from src.models.transformer_e20 import E20FeatureFilter  # noqa: E402

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
# no v2 (76.800/fold) extrapolaria para 15-30h+.
SVM_SEARCH_SUBSAMPLE = 6000

# Subamostra também para o FIT FINAL (não só a busca) — decisão do
# Nycolas em 2026-09-02. O plano original só subamostrava a busca de
# hiperparâmetros e fazia o ajuste final no fold completo; a 6a auditoria
# mediu escala empírica de n^2,85 para o SVM-RBF e projetou 40-80h de CPU
# só para essa etapa no Caminho A inteiro — orçamento que nunca tinha
# sido contabilizado. Com escala n^2,85, subamostrar o fit final para
# 20.000 (>3x a subamostra da busca, para não jogar fora toda a vantagem
# de mais dados) reduz o custo do fit final por um fator de
# aproximadamente (N_fold/20000)^2,85 em relação ao fold completo — dezenas
# de vezes mais rápido. Custo: menos poder estatístico no resultado do
# SVM especificamente. Os outros 4 modelos (RandomForest, LinearSVC,
# XGBoost, LogisticRegression) continuam no fold completo, sem alteração.
SVM_FINAL_FIT_SUBSAMPLE = 20000
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
        # sem `n_jobs`: sem efeito desde sklearn 1.8 e removido na 1.10.
        "LogisticRegression": LogisticRegression(max_iter=2000, random_state=seed),
    }


def _svm_subsample(
    X: np.ndarray, y: np.ndarray, groups: np.ndarray, size: int, seed: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Subamostra aleatória por amostra (não por chave — não há CV nem
    key-holdout dentro desta subamostra, só um `.fit()` direto, então não
    há vazamento a evitar aqui)."""
    n = len(y)
    if n <= size:
        return X, y, np.asarray(groups)
    rng = np.random.default_rng(seed)
    idx = rng.choice(n, size=size, replace=False)
    return X[idx], y[idx], np.asarray(groups)[idx]


class SubsampledSVC(BaseEstimator, ClassifierMixin):
    """SVC(kernel="rbf") que subamostra para `SVM_FINAL_FIT_SUBSAMPLE`
    antes de ajustar — achado de 2026-09-02.

    O `StackingClassifier` chama `.fit()` no SVM-RBF de `base_estimator`
    uma vez por split da CV interna (para gerar as features OOF do
    meta-modelo) MAIS uma vez no treino completo — no fold inteiro
    (~9.600 amostras) ou no trainval inteiro do modelo final (~48.000+),
    SEM NENHUMA subamostra. É um SVM-RBF diferente do "SVM-RBF" isolado
    que `fit_svm_with_search` já corrigia; a correção daquele não cobria
    este, escondido dentro de `build_stacking_model`. Com a escala n^2,85
    medida pela 6a auditoria, isso sozinho travou uma rodada real por
    horas num fold só (achado ao vivo rodando o Caminho A completo).
    Mesmo tratamento aqui: subamostra por amostra (sem CV própria dentro
    do `.fit()`, então não há vazamento de chave a evitar na subamostra
    em si)."""

    def __init__(self, C: float = 1.0, gamma="scale", random_state: int = SEED_MODEL):
        self.C = C
        self.gamma = gamma
        self.random_state = random_state

    def fit(self, X, y):
        Xs, ys, _ = _svm_subsample(
            np.asarray(X), np.asarray(y), np.zeros(len(y)),
            SVM_FINAL_FIT_SUBSAMPLE, self.random_state,
        )
        # SEM probability=True de propósito, igual ao SVC original que
        # substitui: Platt scaling roda sua PRÓPRIA CV interna dentro do
        # .fit(), multiplicando o custo de novo. StackingClassifier cai
        # para decision_function automaticamente quando predict_proba
        # não existe (por isso esta classe não define esse método).
        self._svc = SVC(kernel="rbf", C=self.C, gamma=self.gamma,
                        random_state=self.random_state)
        self._svc.fit(Xs, ys)
        self.classes_ = self._svc.classes_
        return self

    def predict(self, X):
        return self._svc.predict(X)

    def decision_function(self, X):
        return self._svc.decision_function(X)


def fit_svm_with_search(
    X_train: np.ndarray, y_train: np.ndarray, groups: np.ndarray,
    seed: int = SEED_MODEL,
) -> tuple[SVC, dict]:
    """
    SVM-RBF com busca de hiperparâmetros em SUBAMOSTRA e fit final TAMBÉM
    em subamostra (ver `SVM_SEARCH_SUBSAMPLE`/`SVM_FINAL_FIT_SUBSAMPLE`
    para o motivo e o custo — decisão do Nycolas em 2026-09-02, resolvendo
    o orçamento medido pela 6a auditoria em 40-80h para o fit final sozinho
    no fold completo).

    **CV interna GROUP-AWARE (por `key_id`), não estratificada simples.**
    O plano exige isso explicitamente e a diferença é real: com
    `StratifiedKFold`, amostras da MESMA chave caem em treino e validação
    internos, e a escolha de C/gamma fica otimista. O vazamento não
    contaminaria a métrica reportada (essa é medida na validação do fold,
    com key-holdout íntegro), mas escolheria hiperparâmetros calibrados
    para um cenário que não existe no teste.
    """
    Xs, ys, gs = _svm_subsample(X_train, y_train, groups, SVM_SEARCH_SUBSAMPLE, seed)

    n_groups = len(np.unique(gs))
    n_splits = min(3, n_groups)
    if n_splits < 2:
        # Chaves de menos para CV group-aware: usa a grade default em vez
        # de cair silenciosamente numa CV que vaza por chave. O fit final
        # ainda respeita a subamostra — esse caminho é raro (poucos grupos
        # no treino), não o custo dominante do Caminho A.
        Xf, yf, _ = _svm_subsample(X_train, y_train, groups, SVM_FINAL_FIT_SUBSAMPLE, seed)
        final = SVC(kernel="rbf", random_state=seed, **SVM_GRID[0])
        final.fit(Xf, yf)
        return final, {**SVM_GRID[0], "search": "pulada (grupos insuficientes)",
                       "final_fit_subsample": len(yf)}

    best_score, best_params = -np.inf, SVM_GRID[0]
    inner_cv = GroupKFold(n_splits=n_splits)
    for params in SVM_GRID:
        scores = []
        for tr, va in inner_cv.split(Xs, ys, groups=gs):
            m = SVC(kernel="rbf", random_state=seed, **params)
            m.fit(Xs[tr], ys[tr])
            scores.append(m.score(Xs[va], ys[va]))
        mean_score = float(np.mean(scores))
        if mean_score > best_score:
            best_score, best_params = mean_score, params

    Xf, yf, _ = _svm_subsample(X_train, y_train, groups, SVM_FINAL_FIT_SUBSAMPLE, seed)
    final = SVC(kernel="rbf", random_state=seed, probability=False, **best_params)
    final.fit(Xf, yf)
    return final, {**best_params,
                   "search_subsample": len(ys),
                   "final_fit_subsample": len(yf),
                   "inner_cv": f"GroupKFold({n_splits}) por key_id",
                   "inner_cv_score": round(best_score, 4)}


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
# Stacking próprio + réplicas nomeadas da literatura (03_classificadores.md §3.1)
# ---------------------------------------------------------------------------

def _group_cv_splits(groups: np.ndarray, n_splits: int = 3, seed: int = SEED_MODEL):
    """
    Splits pré-computados por chave, para o parâmetro `cv=` do
    `StackingClassifier`. A CV interna DEFAULT do sklearn (KFold simples)
    vazaria entre chaves — a mesma chave apareceria no treino e na
    validação interna do stacking, inflando as probabilidades OOF que
    alimentam o `final_estimator`. `n_splits` é limitado ao nº de chaves
    disponíveis (grupos pequenos demais caem para o mínimo viável).
    """
    n_groups = len(np.unique(groups))
    k = max(2, min(n_splits, n_groups))
    return list(GroupKFold(n_splits=k).split(np.zeros(len(groups)), groups=groups))


def build_stacking_model(seed: int, groups: np.ndarray) -> StackingClassifier:
    """
    `StackingClassifier` sobre os 5 modelos-base do Caminho A (RF,
    LinearSVC, XGBoost, LR + um SVM-RBF com hiperparâmetros FIXOS —
    repetir a busca de HP dentro de cada fold interno do stacking
    multiplicaria o custo da busca pelo nº de splits internos, e o plano
    não pede isso; documentado aqui como simplificação deliberada).
    LinearSVC/LR entram como `Pipeline(StandardScaler, modelo)` porque o
    `StackingClassifier` passa a MESMA matriz de entrada (não escalada)
    para todos os estimadores-base.
    """
    estimators = [
        ("rf", RandomForestClassifier(n_estimators=500, n_jobs=-1,
                                      random_state=seed, class_weight="balanced")),
        ("linearsvc", Pipeline([("scaler", StandardScaler()),
                                ("clf", LinearSVC(C=1.0, random_state=seed,
                                                  max_iter=5000, dual="auto"))])),
        ("xgb", XGBClassifier(n_estimators=500, max_depth=6, learning_rate=0.1,
                              random_state=seed, n_jobs=-1, eval_metric="mlogloss",
                              tree_method="hist")),
        ("lr", Pipeline([("scaler", StandardScaler()),
                         ("clf", LogisticRegression(max_iter=2000, random_state=seed))])),
        # gamma="scale" (não fixo -- calculado a partir de 1/(n_features*X.var()))
        # colapsa nesta subamostra: medido, os 20.000 pontos viram vetor de
        # suporte inteiros e o modelo passa a prever uma única classe sempre
        # (achado ao vivo, 2026-09-02, rodando o Caminho A completo pela
        # primeira vez em dado real -- ver SubsampledSVC). gamma=0.01 (o
        # mesmo valor já testado em SVM_GRID) não degenera.
        ("svm", SubsampledSVC(C=1.0, gamma=0.01, random_state=seed)),
    ]
    return StackingClassifier(
        estimators=estimators, final_estimator=LogisticRegression(max_iter=2000, random_state=seed),
        cv=_group_cv_splits(groups, seed=seed), n_jobs=-1,
    )


def build_hknnrf_model(seed: int, groups: np.ndarray) -> StackingClassifier:
    """
    Réplica HKNNRF (Yuan et al. 2022, PeerJ CS) — KNN+RF.

    **Operacionalização (o artigo não expõe a arquitetura interna de
    combinação, só o nome):** KNN e RF como estimadores-base de um
    `StackingClassifier` com combinador logístico — um padrão comum de
    "híbrido KNN-RF" na literatura de ensemble (KNN contribui estrutura
    local de vizinhança, RF contribui decisão de ensemble). Documentado
    aqui explicitamente para a seção de métodos: esta é NOSSA
    operacionalização do nome "HKNNRF", não uma reprodução linha a linha
    de uma arquitetura publicada em detalhe.
    """
    estimators = [
        ("knn", Pipeline([("scaler", StandardScaler()),
                          ("clf", KNeighborsClassifier(n_neighbors=5))])),
        ("rf", RandomForestClassifier(n_estimators=500, n_jobs=-1,
                                      random_state=seed, class_weight="balanced")),
    ]
    return StackingClassifier(
        estimators=estimators, final_estimator=LogisticRegression(max_iter=2000, random_state=seed),
        cv=_group_cv_splits(groups, seed=seed), n_jobs=-1,
    )


def build_xgblgbm_model(seed: int) -> VotingClassifier:
    """
    Réplica XGB-LGBM (Zhao et al. 2023, IEEE Access) — o maior resultado
    real entre compostos clássicos da RSL (90,5%). A representação que
    define o estudo é a distribuição de PESO DE HAMMING por byte (11
    features, `hamming.py`) — não o vetor de 641 features. Sem essa
    restrição de representação, a réplica testaria só o classificador
    deles, não a técnica publicada. Ver `_hamming_columns`.

    **Operacionalização:** votação suave (probabilidades médias) entre
    XGBoost e LightGBM — o artigo nomeia os dois algoritmos sem detalhar
    o mecanismo exato de combinação.
    """
    return VotingClassifier(
        estimators=[
            ("xgb", XGBClassifier(n_estimators=300, max_depth=6, learning_rate=0.1,
                                  random_state=seed, n_jobs=-1, eval_metric="mlogloss",
                                  tree_method="hist")),
            ("lgbm", LGBMClassifier(n_estimators=300, max_depth=6, learning_rate=0.1,
                                    random_state=seed, n_jobs=-1, verbosity=-1)),
        ],
        voting="soft", n_jobs=-1,
    )


def _hamming_columns(df: pd.DataFrame) -> list[str]:
    cols = [f"hamming_weight_{k}" for k in range(9)] + [
        "hamming_weight_mean", "hamming_weight_var"]
    return [c for c in cols if c in df.columns]


def _e20_columns(df: pd.DataFrame) -> list[str]:
    """Colunas NIST+entropia disponíveis no dataframe — representação da
    réplica E20 (filtro F + RFE reduz isso a ~8 antes do Transformer)."""
    nist_cols = [c for c in _nist_feature_keys() if c in df.columns]
    entropy_cols = [c for c in
                    ["shannon_entropy", "chi2_statistic", "chi2_pvalue", "chi2_dof"]
                    if c in df.columns]
    return nist_cols + entropy_cols


# Nomes reportáveis das rodadas de `run_literature_replicas` — usados para
# que `--models` filtre também estas (antes ele só filtrava `build_models()`,
# então `--models RandomForest` ainda rodava as 5 rodadas de réplica).
REPLICA_MODEL_NAMES = [
    "Stacking", "HKNNRF_replica",
    "XGB_LGBM_hamming_replica", "Transformer_E20_replica",
]


def run_literature_replicas(
    tr: pd.DataFrame, va: pd.DataFrame, y_tr: np.ndarray, y_va: np.ndarray,
    X_tr: np.ndarray, X_va: np.ndarray, run_id: str, braco: str, fold_tag,
    classes: list[str], out_dir, n_bootstrap: int, seed: int = SEED_MODEL,
    models_subset: list[str] | None = None,
) -> None:
    """
    Roda o Stacking próprio + as 3 réplicas nomeadas sobre um fold já
    preparado (mesmos X_tr/X_va — features selecionadas — do restante do
    Caminho A). Chamado uma vez por fold de CV e uma vez no modelo final.

    `models_subset` filtra quais rodam (ver `REPLICA_MODEL_NAMES`).
    """
    def _want(name: str) -> bool:
        return models_subset is None or name in models_subset

    groups_tr = tr["key_id"].to_numpy()
    labels = list(range(len(classes)))

    # --- Stacking próprio ---
    if _want("Stacking"):
        t0 = time.perf_counter()
        stack = build_stacking_model(seed, groups_tr)
        stack.fit(X_tr, y_tr)
        report_eval(
            run_id=run_id, caminho="A", modelo="Stacking",
            braco=braco, fold=fold_tag,
            y_true=y_va, y_pred=stack.predict(X_va), y_proba=get_proba(stack, X_va),
            sample_ids=va["sample_id"].tolist(), key_ids=va["key_id"].tolist(),
            class_names=classes, labels=labels, out_dir=out_dir, n_bootstrap=n_bootstrap,
            extra={"train_time_s": round(time.perf_counter() - t0, 1),
                   "base_estimators": [e[0] for e in stack.estimators]},
        )

    # --- HKNNRF (Yuan et al. 2022) ---
    if _want("HKNNRF_replica"):
        t0 = time.perf_counter()
        hknnrf = build_hknnrf_model(seed, groups_tr)
        hknnrf.fit(X_tr, y_tr)
        report_eval(
            run_id=run_id, caminho="A", modelo="HKNNRF_replica",
            braco=braco, fold=fold_tag,
            y_true=y_va, y_pred=hknnrf.predict(X_va), y_proba=get_proba(hknnrf, X_va),
            sample_ids=va["sample_id"].tolist(), key_ids=va["key_id"].tolist(),
            class_names=classes, labels=labels, out_dir=out_dir, n_bootstrap=n_bootstrap,
            extra={"train_time_s": round(time.perf_counter() - t0, 1),
                   "referencia": "Yuan et al. 2022, PeerJ CS",
                   "operacionalizacao": "StackingClassifier(KNN, RF) + LR"},
        )

    # --- XGB-LGBM sobre peso de Hamming (Zhao et al. 2023) ---
    ham_cols = _hamming_columns(tr) if _want("XGB_LGBM_hamming_replica") else []
    if ham_cols:
        X_tr_h = tr[ham_cols].to_numpy(np.float64)
        X_va_h = va[ham_cols].to_numpy(np.float64)
        t0 = time.perf_counter()
        xgblgbm = build_xgblgbm_model(seed)
        xgblgbm.fit(X_tr_h, y_tr)
        report_eval(
            run_id=run_id, caminho="A", modelo="XGB_LGBM_hamming_replica",
            braco=braco, fold=fold_tag,
            y_true=y_va, y_pred=xgblgbm.predict(X_va_h), y_proba=get_proba(xgblgbm, X_va_h),
            sample_ids=va["sample_id"].tolist(), key_ids=va["key_id"].tolist(),
            class_names=classes, labels=labels, out_dir=out_dir, n_bootstrap=n_bootstrap,
            extra={"train_time_s": round(time.perf_counter() - t0, 1),
                   "referencia": "Zhao et al. 2023, IEEE Access",
                   "representacao": ham_cols, "n_features": len(ham_cols)},
        )
    elif _want("XGB_LGBM_hamming_replica"):
        print("  [aviso] colunas de peso de Hamming ausentes — pulando réplica XGB-LGBM")

    # --- Transformer sobre features NIST (réplica fiel do E20) ---
    e20_cols = _e20_columns(tr) if _want("Transformer_E20_replica") else []
    if len(e20_cols) >= 8:
        X_tr_n = tr[e20_cols].to_numpy(np.float64)
        X_va_n = va[e20_cols].to_numpy(np.float64)
        # Imputação simples de NaN (p-values inelegíveis viram 0,5 — mesma
        # convenção neutra do módulo nist_sts.py) antes do filtro F/RFE,
        # que não aceitam NaN.
        X_tr_n = np.nan_to_num(X_tr_n, nan=0.5)
        X_va_n = np.nan_to_num(X_va_n, nan=0.5)

        t0 = time.perf_counter()
        e20_filter = E20FeatureFilter(n_features_out=8, random_state=seed)
        e20_filter.fit(X_tr_n, y_tr, feature_names=e20_cols)
        Xr_tr = e20_filter.transform(X_tr_n)
        Xr_va = e20_filter.transform(X_va_n)

        e20_model = E20Classifier(n_features=Xr_tr.shape[1], n_classes=len(classes), seed=seed)
        e20_model.fit(Xr_tr, y_tr)
        report_eval(
            run_id=run_id, caminho="A", modelo="Transformer_E20_replica",
            braco=braco, fold=fold_tag,
            y_true=y_va, y_pred=e20_model.predict(Xr_va), y_proba=e20_model.predict_proba(Xr_va),
            sample_ids=va["sample_id"].tolist(), key_ids=va["key_id"].tolist(),
            class_names=classes, labels=labels, out_dir=out_dir, n_bootstrap=n_bootstrap,
            extra={"train_time_s": round(time.perf_counter() - t0, 1),
                   "referencia": "Yuan et al. 2026 (E20)",
                   "features_selecionadas": e20_filter.selected_names_,
                   "n_params": e20_model.model_.count_parameters()},
        )
    elif _want("Transformer_E20_replica"):
        print(f"  [aviso] só {len(e20_cols)} colunas NIST+entropia disponíveis "
              f"(<8) — pulando réplica Transformer-E20")


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
    run_replicas: bool = True,
) -> None:
    """
    Roda uma análise completa: 5-fold CV por chave + modelo final no
    holdout de teste, para cada modelo. Tudo relatado por `report_eval`.

    `keyholdout=False` é o braço da ablação: split ALEATÓRIO POR AMOSTRA
    (ignora `key_id`), estratificado por classe, com os mesmos tamanhos
    do split por chave e seed 42 — ver 04_protocolo §4.2.

    `run_replicas=True` (default) também roda o Stacking próprio e as 3
    réplicas nomeadas da literatura (HKNNRF, XGB-LGBM/Hamming,
    Transformer-E20) — ver `run_literature_replicas`. Desligado nas
    ablações/controles onde eles não agregam informação nova (ex.:
    `learning_curve`, `sanity_lenct`) para não multiplicar o custo.
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

        # Modelos NOVOS a cada fold. `dict(all_models)` era uma cópia rasa:
        # os mesmos objetos eram refitados fold após fold. O sklearn refita
        # limpo, então não havia erro hoje — mas é estado compartilhado
        # entre folds que só não vaza por detalhe de implementação, e
        # instanciar de novo custa nada.
        fold_models = build_models()
        if models_subset:
            fold_models = {k: v for k, v in fold_models.items() if k in models_subset}
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
            svm, svm_params = fit_svm_with_search(
                X_tr_s, y_tr, groups=tr["key_id"].to_numpy())
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

        if run_replicas:
            run_literature_replicas(
                tr, va, y_tr, y_va, X_tr, X_va,
                run_id=f"{DATASET_ID}_{analysis_name}", braco=braco, fold_tag=fold_idx,
                classes=classes, out_dir=out_dir, n_bootstrap=n_bootstrap,
                models_subset=models_subset,
            )

    # ---------------- Modelo final: trainval completo -> teste ----------------
    print(f"\n  --- modelo final (trainval completo -> teste) ---")
    X_tv_raw = trainval_df[feat_cols].to_numpy(dtype=np.float64)
    X_te_raw = test_df[feat_cols].to_numpy(dtype=np.float64)
    y_tv = trainval_df["y"].to_numpy()
    y_te = test_df["y"].to_numpy()

    sel = LWCFeatureSelector(_selector_config())
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
        svm, svm_params = fit_svm_with_search(
            X_tv_s, y_tv, groups=trainval_df["key_id"].to_numpy())
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

    if run_replicas:
        run_literature_replicas(
            trainval_df, test_df, y_tv, y_te, X_tv, X_te,
            run_id=f"{DATASET_ID}_{analysis_name}", braco=braco, fold_tag="final",
            classes=classes, out_dir=out_dir, n_bootstrap=n_bootstrap,
            models_subset=models_subset,
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
    # Réplicas desligadas por padrão: controles positivos/negativos servem
    # para validar o protocolo (o ECB deve separar quase perfeitamente),
    # não para sustentar a alegação "a técnica de Fulano dá X" — isso é
    # papel de `pairs`/`4class`, onde as réplicas ficam ligadas.
    kw.setdefault("run_replicas", False)
    run_analysis(df, folds, "control_ecb_vs_ascon",
                 ["AES-128-ECB", "Ascon-AEAD128"], branch, out_dir, **kw)


def analysis_prng_control(df, folds, branch, out_dir, **kw) -> None:
    kw.setdefault("run_replicas", False)
    for algo in REAL_ALGORITHMS:
        name = f"control_prng_vs_{algo.split('-')[0]}"
        run_analysis(df, folds, name, ["PRNG", algo], branch, out_dir, **kw)


def analysis_sanity_lenct(df, folds, branch, out_dir, **kw) -> None:
    """Sanity de encanamento: inclui `len_ct` DE PROPÓSITO. Pares com
    Grain (len_ct 65.544 vs 65.552) devem dar F1 > 0,95 — se não derem,
    há bug no pipeline. Rodada fora das tabelas de resultado."""
    if branch != "cru":
        print(f"  [AVISO] 06 §6.7 especifica o braço `cru` para o sanity de "
              f"`len_ct`; rodando em `{branch}`. Funciona (a coluna `len_ct` do "
              f"parquet de features é o comprimento ORIGINAL, herdado do CT "
              f"cru, em qualquer braço), mas nesse caso ela não corresponde ao "
              f"comprimento dos CTs efetivamente usados — rode com "
              f"`--branch cru` para o sanity canônico.")
    kw = {**kw, "include_len_ct": True, "models_subset": ["RandomForest"], "run_replicas": False}
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


# ---------------------------------------------------------------------------
# Ablação de famílias de features (06 Fase 6.5)
# ---------------------------------------------------------------------------

# Famílias originais do v1 (307D antes da adição do lzma a `complexity`,
# ver `docs/analise_completa/`). O nome "clássicas-307" é histórico — a
# contagem real hoje é ligeiramente diferente; o que importa é o CONJUNTO
# de famílias, não o número exato no nome.
_CLASSICAS_FAMILIES = [
    "histogram", "entropy", "ngrams", "autocorrelation", "complexity", "frequency",
]


def _family_column_sets(available_cols: set[str]) -> dict[str, list[str]]:
    """Nome da família -> lista de colunas dessa família presentes no
    parquet de features. Deriva os nomes chamando cada função de família
    uma vez (mesma técnica usada para listar as 641 features em outros
    pontos do projeto), em vez de manter uma lista hardcoded que
    dessincronizaria da implementação real."""
    from src.features.extractor import _FAMILY_FUNCS
    dummy_ct = bytes(range(256)) * 256  # 65.536 bytes — evita casos de borda
    out: dict[str, list[str]] = {}
    for name, fn in _FAMILY_FUNCS.items():
        keys = list(fn(dummy_ct).keys())
        out[name] = [k for k in keys if k in available_cols]
    return out


def _fit_predict_rf_on_columns(
    tr: pd.DataFrame, va: pd.DataFrame, y_tr: np.ndarray, y_va: np.ndarray,
    cols: list[str], seed: int = SEED_MODEL,
) -> RandomForestClassifier:
    """RF fixo, SEM seletor — a ablação de famílias mede quanto sinal existe
    NA FAMÍLIA INTEIRA, não depois de outra rodada de seleção por cima
    (que dominaria o resultado em famílias pequenas, tipo Hamming com 11
    colunas, e mascararia a comparação entre famílias)."""
    model = RandomForestClassifier(n_estimators=500, n_jobs=-1, random_state=seed,
                                   class_weight="balanced")
    model.fit(tr[cols].to_numpy(np.float64), y_tr)
    return model


def analysis_family_ablation(df, folds, branch, out_dir, classes=None, n_bootstrap=1000,
                             keyholdout=True, **_ignored) -> None:
    """
    Ablação de famílias (all / clássicas / NIST / por-família / top-1) —
    06 Fase 6.5. Modelo fixo (RF) por corte, para isolar o efeito da
    REPRESENTAÇÃO, não do classificador. Roda no braço `controlado`
    (ou o passado), sobre o cenário 4-classes por default.
    """
    classes = classes or REAL_ALGORITHMS
    sub = df[df["algorithm"].isin(classes)].copy()
    label_map = {c: i for i, c in enumerate(classes)}
    sub["y"] = sub["algorithm"].map(label_map)

    all_cols = set(feature_columns(sub))
    family_cols = _family_column_sets(all_cols)
    classicas_cols = [c for fam in _CLASSICAS_FAMILIES for c in family_cols.get(fam, [])]
    nist_cols = family_cols.get("nist_sts", [])

    cuts: dict[str, list[str]] = {"all": sorted(all_cols), "classicas": classicas_cols,
                                  "NIST": nist_cols}
    for fam, cols in family_cols.items():
        if cols:
            cuts[f"familia_{fam}"] = cols

    test_keys = set(folds["test_keys"])
    test_mask = sub["key_id"].isin(test_keys) if keyholdout else None
    if not keyholdout:
        rng = np.random.default_rng(SEED_SPLIT)
        n_test = int(sub["key_id"].isin(test_keys).sum())
        test_mask = pd.Series(np.zeros(len(sub), dtype=bool), index=sub.index)
        idx = rng.choice(len(sub), size=min(n_test, len(sub)), replace=False)
        test_mask.iloc[idx] = True
    trainval_df = sub[~test_mask]
    test_df = sub[test_mask]
    y_tv, y_te = trainval_df["y"].to_numpy(), test_df["y"].to_numpy()

    final_f1: dict[str, float] = {}
    for cut_name, cols in cuts.items():
        if not cols:
            continue
        print(f"\n  [ablação de famílias] corte='{cut_name}' ({len(cols)} colunas)")
        model = _fit_predict_rf_on_columns(trainval_df, test_df, y_tv, y_te, cols)
        y_pred = model.predict(test_df[cols].to_numpy(np.float64))
        proba = model.predict_proba(test_df[cols].to_numpy(np.float64))
        report = report_eval(
            run_id=f"{DATASET_ID}_family_ablation", caminho="A",
            modelo="RandomForest", braco=f"{branch}_familia_{cut_name}", fold="final",
            y_true=y_te, y_pred=y_pred, y_proba=proba,
            sample_ids=test_df["sample_id"].tolist(), key_ids=test_df["key_id"].tolist(),
            class_names=classes, labels=list(range(len(classes))),
            out_dir=out_dir, n_bootstrap=n_bootstrap,
            extra={"cut": cut_name, "n_features": len(cols)},
        )
        final_f1[cut_name] = report.f1_macro

    fam_only = {k: v for k, v in final_f1.items() if k.startswith("familia_")}
    if fam_only:
        top1_name = max(fam_only, key=fam_only.get)
        print(f"\n  [ablação de famílias] TOP-1 (melhor família isolada): "
              f"{top1_name} (F1-macro={fam_only[top1_name]:.4f})")
        (out_dir / f"{DATASET_ID}_family_ablation_top1.json").write_text(
            json.dumps({"top1_family": top1_name, "f1_macro": fam_only[top1_name],
                       "all_families": fam_only}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )


# ---------------------------------------------------------------------------
# Teste de permutação — nulo empírico (06 Fase 6.8)
# ---------------------------------------------------------------------------

# 200 permutações: com 20, o menor p-valor obtenível é 1/21 ≈ 0,048 — perto
# demais de α=0,05 para um nulo que sustenta a conclusão principal — e
# estimar o percentil 97,5 com 20 pontos é muito instável. Com 200, o piso
# cai para ~0,005. O XGBoost foi retirado do laço (500 árvores x 200
# permutações x 2 esquemas era proibitivo); a LR sozinha basta para
# caracterizar o nulo, e o XGBoost segue reportado nas análises normais.
N_PERM = 200
SEED_PERM = 101


def _shuffle_by_key(rng: np.random.Generator, groups: np.ndarray,
                    uniq_keys: np.ndarray, n_classes: int) -> np.ndarray:
    """
    Rótulo aleatório CONSTANTE dentro de cada chave (generalização
    multi-classe do esquema do v1 — ver `run_ablation_fs_60k.py`). Mede o
    F1 alcançável em chaves novas quando o modelo pode decorar a chave no
    treino, mas isso não transfere ao holdout (chaves inéditas).
    """
    reps = len(uniq_keys) // n_classes + 1
    lab = rng.permutation(np.tile(np.arange(n_classes), reps)[:len(uniq_keys)])
    key2lab = dict(zip(uniq_keys, lab))
    return np.array([key2lab[g] for g in groups])


def _shuffle_within_key(rng: np.random.Generator, groups: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Permuta os rótulos DENTRO de cada chave — nulo mais estrito: destrói
    só a associação criptograma-algoritmo, preservando estrutura de grupos
    e distribuição marginal dos atributos."""
    y_shuf = y.copy()
    for k in np.unique(groups):
        m = groups == k
        y_shuf[m] = rng.permutation(y[m])
    return y_shuf


def analysis_permutation(df, folds, branch, out_dir, classes=None,
                        keyholdout=True, **_ignored) -> None:
    """
    Distribuição nula empírica do F1 (20 repetições, esquemas `by_key` e
    `within_key`) — 06 Fase 6.8. Sobre o braço primário, cenário
    4-classes por default. LR + XGBoost, mesmo par de modelos do v1.

    Sempre roda COM key-holdout: os dois esquemas de permutação são
    definidos em termos de `key_id` (`by_key` sorteia rótulo por chave,
    `within_key` permuta dentro da chave), então "nulo empírico sem
    key-holdout" não é uma coisa que exista neste desenho. `--no-keyholdout`
    é avisado e ignorado, em vez de silenciosamente ignorado.
    """
    if not keyholdout:
        print("  [AVISO] `--no-keyholdout` não se aplica ao teste de permutação "
              "(os dois esquemas são definidos por `key_id`) — rodando COM "
              "key-holdout.")
    classes = classes or REAL_ALGORITHMS
    sub = df[df["algorithm"].isin(classes)].copy()
    label_map = {c: i for i, c in enumerate(classes)}
    sub["y"] = sub["algorithm"].map(label_map)
    feat_cols = feature_columns(sub)

    test_keys = set(folds["test_keys"])
    trainval_df = sub[~sub["key_id"].isin(test_keys)]
    test_df = sub[sub["key_id"].isin(test_keys)]

    X_tv_raw = trainval_df[feat_cols].to_numpy(np.float64)
    X_te_raw = test_df[feat_cols].to_numpy(np.float64)
    y_tv = trainval_df["y"].to_numpy()
    y_te = test_df["y"].to_numpy()
    groups = trainval_df["key_id"].to_numpy()
    uniq_keys = np.unique(groups)

    rng = np.random.default_rng(SEED_PERM)
    results: dict[str, dict] = {}
    for scheme in ("by_key", "within_key"):
        print(f"\n{'=' * 70}\nTESTE DE PERMUTAÇÃO — esquema '{scheme}' "
              f"({N_PERM} repetições, pipeline COMPLETA por permutação)"
              f"\n{'=' * 70}")
        null_f1: dict[str, list[float]] = {"LogisticRegression": []}
        for rep in range(N_PERM):
            if scheme == "by_key":
                y_shuf = _shuffle_by_key(rng, groups, uniq_keys, len(classes))
            else:
                y_shuf = _shuffle_within_key(rng, groups, y_tv)

            # **Seletor refitado DENTRO da permutação** (correção 2026-08-24).
            # A versão anterior fitava o seletor UMA vez com os rótulos
            # VERDADEIROS e reusava nas 20 permutações — o nulo media então a
            # variabilidade do classificador sobre um conjunto de features já
            # escolhido com informação do rótulo, não a variabilidade da
            # PIPELINE. Ojala & Garriga (2010) exigem refazer todo o
            # procedimento sob rótulos permutados; do contrário o nulo sai
            # otimista e o teste perde justamente o que deveria capturar (o
            # seletor "encontrar" sinal em ruído).
            sel_perm = LWCFeatureSelector(_selector_config())
            sel_perm.fit(X_tv_raw, y_shuf, feature_names=feat_cols)
            X_tv_p = sel_perm.transform(X_tv_raw)
            X_te_p = sel_perm.transform(X_te_raw)
            scaler_p = StandardScaler().fit(X_tv_p)

            lr = LogisticRegression(max_iter=2000, random_state=SEED_MODEL).fit(
                scaler_p.transform(X_tv_p), y_shuf)
            f_lr = float(f1_score(y_te, lr.predict(scaler_p.transform(X_te_p)),
                                  average="macro", zero_division=0))
            null_f1["LogisticRegression"].append(f_lr)
            if (rep + 1) % 10 == 0 or rep == 0:
                print(f"  [perm {rep + 1:03d}/{N_PERM}] LR={f_lr:.4f}", flush=True)

        results[scheme] = {
            m: {"mean": float(np.mean(v)), "std": float(np.std(v)),
               "p2.5": float(np.percentile(v, 2.5)), "p97.5": float(np.percentile(v, 97.5)),
               "max": float(np.max(v)), "values": [round(x, 4) for x in v]}
            for m, v in null_f1.items()
        }

    out_path = out_dir / f"{DATASET_ID}_permutation_null.json"
    out_path.write_text(
        json.dumps({"n_perm": N_PERM, "seed": SEED_PERM, "classes": classes,
                   "p_minimo_obtenivel": round(1.0 / (N_PERM + 1), 5),
                   "pipeline_refitada_por_permutacao": True,
                   "modelos": ["LogisticRegression"],
                   "schemes": results}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nNulo empírico salvo em {out_path}")
    print(f"  menor p-valor obtenível com N_PERM={N_PERM}: "
          f"{1.0 / (N_PERM + 1):.5f}")


ANALYSES = {
    "4class": analysis_4class,
    "pairs": analysis_pairs,
    "ecb_control": analysis_ecb_control,
    "prng_control": analysis_prng_control,
    "sanity_lenct": analysis_sanity_lenct,
    "learning_curve": analysis_learning_curve,
}
ANALYSES["family_ablation"] = analysis_family_ablation
ANALYSES["permutation"] = analysis_permutation



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
    parser.add_argument("--skip-replicas", action="store_true",
                        help="Desliga Stacking + as 3 réplicas da literatura "
                             "(útil para exploração rápida; NUNCA no resultado oficial "
                             "de 4class/pairs, onde elas sustentam a comparação com a RSL).")
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
    # Só força `run_replicas=False` quando pedido explicitamente — do
    # contrário, cada análise decide seu próprio default (True em
    # 4class/pairs, False em ecb_control/prng_control via `setdefault`).
    if args.skip_replicas:
        kw["run_replicas"] = False

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
