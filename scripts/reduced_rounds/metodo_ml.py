"""
Método de ML do piso: busca aninhada de hiperparâmetros (pré-registro no plano
v3, seção "Pré-registro do método de ML", 12/10/2026).

Para cada algoritmo e modelo:
1. seleção, só nas chaves de treino da célula piso+1 / `texto-en`:
   GroupKFold(3) por chave, AUC média na validação interna, sobre o espaço
   pré-registrado (grade completa na LR e no SVM, 20 sorteios no RF e no
   XGBoost, seed 13; o SVM busca numa subamostra de 8 000 amostras);
2. a configuração escolhida é aplicada a todas as células do algoritmo (piso,
   piso+1, especificação; braços `texto-en` e `aleatorio`), cada uma
   retreinada nas suas 240 chaves e avaliada uma vez no teste, pelo próprio
   `run_floor.run_config` (mesmo split, mesmas bolsas, mesmo relato), para o
   `report_floor.py` decidir o piso com o critério de sempre.

Saída: floor_v2/metodo_ml/<algo>_floor/reports/ (relatórios) e
floor_v2/metodo_ml/selecao.jsonl (todas as configurações avaliadas na busca,
com a AUC interna de cada uma, para a análise de sensibilidade).

Uso:
    python scripts/reduced_rounds/metodo_ml.py --algo ascon --modelos LR RF XGB SVM
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src" / "crypto"))

import numpy as np  # noqa: E402
from sklearn.ensemble import RandomForestClassifier  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import roc_auc_score  # noqa: E402
from sklearn.model_selection import GroupKFold, ParameterGrid, ParameterSampler  # noqa: E402
from sklearn.pipeline import Pipeline  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402
from sklearn.svm import SVC  # noqa: E402
from xgboost import XGBClassifier  # noqa: E402

from scripts.reduced_rounds import run_floor as rf  # noqa: E402
from scripts.run_v2_caminho_a import get_proba  # noqa: E402

CELULAS = {"ascon": (3, 4, 12), "gift": (3, 4, 40), "grain": (28, 29, 256), "schwaemm": (2, 3, 11)}
BASE = rf.OUT_ROOT / "contador_zero_corpus_en"
OUT = rf.OUT_ROOT / "metodo_ml"
# Célula da seleção: índice em CELULAS (0 = rodada do piso, 1 = piso+1, a
# original). Com --celula-selecao piso, a saída vai para metodo_ml_piso/, para
# não misturar com a busca original. Pergunta dessa variante: o ajuste melhora
# o F1 e a AUC na rodada do piso? (não muda o piso, que já é detectado ali)
IDX_SELECAO = 1
SEED_FS = 13
N_SORTEIOS = 20
SVM_SUB = 8000

ESPACO = {
    "LR": ParameterGrid({"C": [1e-3, 1e-2, 1e-1, 1, 10, 100]}),
    "RF": ParameterSampler({"n_estimators": [200, 500, 1000], "max_features": ["sqrt", 0.1, 0.3],
                            "min_samples_leaf": [1, 5, 20], "max_depth": [None, 12, 24]},
                           n_iter=N_SORTEIOS, random_state=SEED_FS),
    "XGB": ParameterSampler({"n_estimators": [200, 500, 1000, 2000], "max_depth": [3, 6, 9, 12],
                             "learning_rate": [0.01, 0.03, 0.1, 0.3], "subsample": [0.6, 0.8, 1.0],
                             "colsample_bytree": [0.3, 0.6, 1.0]},
                            n_iter=N_SORTEIOS, random_state=SEED_FS),
    "SVM": ParameterGrid({"C": [0.1, 1, 10], "gamma_fator": [0.1, 1, 10]}),
}
NOME = {"LR": "LogReg_ajustada", "RF": "RandomForest_ajustada", "XGB": "XGBoost_ajustado",
        "SVM": "SVM_RBF_ajustado"}


def _log(m: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def construir(modelo: str, p: dict, n_features: int):
    s = rf.SEED_MODEL
    if modelo == "LR":
        return Pipeline([("s", StandardScaler()), ("c", LogisticRegression(C=p["C"], max_iter=2000, random_state=s))])
    if modelo == "RF":
        return RandomForestClassifier(n_jobs=-1, random_state=s, class_weight="balanced", **p)
    if modelo == "XGB":
        return XGBClassifier(n_jobs=-1, random_state=s, tree_method="hist", eval_metric="logloss", **p)
    # gamma "scale" = 1 / (n_features * var(X)); com padronização, var = 1
    return Pipeline([("s", StandardScaler()),
                     ("c", SVC(kernel="rbf", C=p["C"], gamma=p["gamma_fator"] / n_features,
                               random_state=s))])


def dados(algo: str, arm: str, r: int):
    """Mesmos X, y, chaves e split do run_floor.run_config."""
    cache = BASE / f"{algo}_floor" / f"{algo}_{arm}_k300.npz"
    d = rf.generate(algo, arm, 300, [r], cache, "ambos", contador="zero")
    n = 300 * rf.PAIRS_PER_KEY
    X = np.vstack([np.unpackbits(d["random"], axis=1), np.unpackbits(d[f"r{r}"], axis=1)]).astype(np.float32)
    y = np.concatenate([np.zeros(n, int), np.ones(n, int)])
    kidx = np.concatenate([d["key_idx"], d["key_idx"]])
    keys = np.arange(300)
    np.random.default_rng(rf.SEED_SPLIT).shuffle(keys)
    tr = ~np.isin(kidx, keys[:60])
    return d, X, y, kidx, tr


def selecionar(algo: str, modelo: str) -> dict:
    r = CELULAS[algo][IDX_SELECAO]
    _, X, y, kidx, tr = dados(algo, "texto-en", r)
    Xt, yt, gt = X[tr], y[tr], kidx[tr]
    if modelo == "SVM":
        idx = np.random.default_rng(SEED_FS).choice(len(yt), SVM_SUB, replace=False)
        Xt, yt, gt = Xt[idx], yt[idx], gt[idx]
    melhores = []
    for p in ESPACO[modelo]:
        aucs, t0 = [], time.time()
        for a, b in GroupKFold(n_splits=3).split(Xt, yt, gt):
            m = construir(modelo, p, X.shape[1]).fit(Xt[a], yt[a])
            aucs.append(roc_auc_score(yt[b], get_proba(m, Xt[b])[:, 1]))
        reg = dict(algo=algo, modelo=modelo, rodadas=r, params=p, auc_media=float(np.mean(aucs)),
                   auc_folds=[float(x) for x in aucs], segundos=round(time.time() - t0, 1))
        melhores.append(reg)
        _log(f"  {algo} {modelo} {p}: AUC interna {reg['auc_media']:.4f} ({reg['segundos']}s)")
        OUT.mkdir(parents=True, exist_ok=True)
        with (OUT / "selecao.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(reg, default=str) + "\n")
    melhor = max(melhores, key=lambda x: x["auc_media"])
    _log(f"{algo} {modelo}: escolhida {melhor['params']} (AUC interna {melhor['auc_media']:.4f}; "
         f"faixa {min(x['auc_media'] for x in melhores):.4f} a {melhor['auc_media']:.4f})")
    return melhor["params"]


def avaliar(algo: str, modelo: str, params: dict) -> None:
    rep = OUT / f"{algo}_floor" / "reports"
    rep.mkdir(parents=True, exist_ok=True)
    nome = NOME[modelo]
    for arm in ("texto-en", "aleatorio"):
        for r in CELULAS[algo]:
            d, X, *_ = dados(algo, arm, r)
            est = construir(modelo, params, X.shape[1])
            original = rf.build_models
            rf.build_models = lambda seed=7, _e=est: {nome: _e}
            try:
                rf.run_config(algo, arm, r, d, 300, 60, 5, rep, "sweep", [nome], "ambos", "zero", "xor")
            finally:
                rf.build_models = original
            with (OUT / "escolhas.jsonl").open("a", encoding="utf-8") as f:
                f.write(json.dumps(dict(algo=algo, modelo=nome, arm=arm, rodadas=r, params=params),
                                   default=str) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--algo", required=True, choices=sorted(CELULAS))
    ap.add_argument("--modelos", nargs="+", default=["LR", "RF", "XGB", "SVM"], choices=list(ESPACO))
    ap.add_argument("--celula-selecao", choices=["piso", "piso1"], default="piso1",
                    help="rodada em que os hiperparâmetros são escolhidos: piso+1 (original) "
                         "ou a própria rodada do piso (saída em metodo_ml_piso/)")
    a = ap.parse_args()
    global OUT, IDX_SELECAO
    if a.celula_selecao == "piso":
        OUT, IDX_SELECAO = rf.OUT_ROOT / "metodo_ml_piso", 0
    rotulo = "piso" if IDX_SELECAO == 0 else "piso+1"
    for m in a.modelos:
        _log(f"===== {a.algo} {m}: seleção na célula {rotulo} / texto-en =====")
        p = selecionar(a.algo, m)
        _log(f"===== {a.algo} {m}: avaliação nas {2 * len(CELULAS[a.algo])} células =====")
        avaliar(a.algo, m, p)
    _log("fim")


if __name__ == "__main__":
    main()
