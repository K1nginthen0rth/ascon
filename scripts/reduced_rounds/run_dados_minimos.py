"""
Dados mínimos: quanto treino o classificador precisa e quantas mensagens o
atacante precisa observar para detectar o piso.

Duas perguntas, uma grade só:
- treino: 3, 10, 30, 100 e 300 dispositivos (100 pares cada), aninhados. É o
  custo offline do atacante, que gera exemplos com chaves próprias;
- mensagens observadas: bolsas de 1, 2, 5, 10, 20, 50 e 100 pares do mesmo
  dispositivo no teste. É o custo online, contra o dispositivo-alvo.

O teste é sempre o mesmo, 1.000 dispositivos, para que só o treino varie. Os
dados seguem a amostragem do `run_floor.py` (contador zero, XOR, `texto-en`),
via `run_curva_orcamento.gerar`.

Critério igual ao do estudo principal: Benjamini-Hochberg sobre todas as
células do algoritmo (os dois braços, as duas rodadas, todos os níveis) e teto
da faixa de controle, que aqui é o maior F1 na rodada da especificação, no
braço de texto, para o mesmo classificador, bolsa e nível de treino. O braço
aleatório entra como controle negativo.

Uso:
    python scripts/reduced_rounds/run_dados_minimos.py --smoke
    python scripts/reduced_rounds/run_dados_minimos.py
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src" / "crypto"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy.stats import norm  # noqa: E402

from scripts.reduced_rounds import run_curva_orcamento as co  # noqa: E402

PISOS = {"ascon": 3, "gift": 3, "schwaemm": 2}
SPEC = {"ascon": 12, "gift": 40, "schwaemm": 11}
TREINO = [3, 10, 30, 100, 300]
BOLSAS = [1, 2, 5, 10, 20, 50, 100]
N_TESTE = 1_000
OUT = REPO_ROOT / "build" / "reduced_rounds" / "floor_v2" / "dados_minimos"


def _log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def avaliar(algo: str, arm: str, r: int, dados: dict, treino: list[int], bolsas: list[int],
            n_teste: int) -> list[dict]:
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    from scripts.reduced_rounds.run_gift_floor import (
        DEFAULT_MODELS, NEEDS_SCALING, SEED_BOOT, SEED_SPLIT, _bags)
    from scripts.run_v2_caminho_a import build_models
    from src.eval.reporting import report_eval

    pos, neg, dev = dados[f"r{r}"], dados["random"], dados["dev"]
    n_dev = int(dev.max()) + 1
    ordem = np.random.default_rng(SEED_SPLIT).permutation(n_dev)
    teste_dev = np.sort(ordem[:n_teste])
    pool_treino = ordem[n_teste:]
    idx_te = np.flatnonzero(np.isin(dev, teste_dev))
    Xte = np.vstack([np.unpackbits(neg[idx_te], axis=1),
                     np.unpackbits(pos[idx_te], axis=1)]).astype(np.float32)
    yte = np.concatenate([np.zeros(len(idx_te), int), np.ones(len(idx_te), int)])
    kte = np.concatenate([dev[idx_te], dev[idx_te]])
    key_ids = np.array([f"d{k:05d}" for k in kte])
    nomes = ["aleatório uniforme", f"{algo} {r}"]
    run_id = f"minimos_{algo}_{arm}_r{r}"
    linhas = []

    for n_tr in treino:
        idx_tr = np.flatnonzero(np.isin(dev, pool_treino[:n_tr]))
        Xtr = np.vstack([np.unpackbits(neg[idx_tr], axis=1),
                         np.unpackbits(pos[idx_tr], axis=1)]).astype(np.float32)
        ytr = np.concatenate([np.zeros(len(idx_tr), int), np.ones(len(idx_tr), int)])
        modelos = build_models()
        for nome in DEFAULT_MODELS:
            m = modelos[nome]
            if nome in NEEDS_SCALING:
                m = Pipeline([("scaler", StandardScaler()), ("clf", m)])
            t0 = time.time()
            proba = m.fit(Xtr, ytr).predict_proba(Xte)
            t = time.time() - t0
            for bag in bolsas:
                by, bp, bk = _bags(proba, yte, key_ids, bag)
                rep = report_eval(
                    run_id=run_id, caminho="A", modelo=f"{nome}_tr{n_tr}_bag{bag}",
                    braco=f"minimos_{algo}_{arm}", fold="final", y_true=by,
                    y_pred=bp.argmax(1), y_proba=bp,
                    sample_ids=[f"{k}_{l}_{i}" for i, (k, l) in enumerate(zip(bk, by))],
                    key_ids=list(bk), class_names=nomes, labels=[0, 1],
                    out_dir=OUT / "reports", seed=SEED_BOOT,
                    extra=dict(algo=algo, rounds=r, arm=arm, contador="zero",
                               representacao="xor", dispositivos_treino=n_tr,
                               pares_treino=n_tr * co.PARES, dispositivos_teste=n_teste,
                               pares_por_decisao=bag, fit_seconds=round(t, 1)))
                d = rep.as_dict()
                linhas.append(dict(algo=algo, arm=arm, rodadas=r, modelo=nome,
                                   dispositivos_treino=n_tr, bolsa=bag,
                                   f1=d.get("f1_macro"), f1_lo=d.get("f1_macro_ci_lower"),
                                   f1_hi=d.get("f1_macro_ci_upper"), auc=co._auc(d)))
        del Xtr
    return linhas


def criterio(df: pd.DataFrame) -> pd.DataFrame:
    """BH por algoritmo + teto da rodada da especificação (braço de texto)."""
    out = []
    for algo, g in df.groupby("algo"):
        g = g.copy()
        meia = (g["f1_hi"] - g["f1_lo"]) / 2
        z = (g["f1"] - 0.5) / (meia / 1.96)
        p = 2 * (1 - norm.cdf(np.abs(z.to_numpy())))
        p[g["f1"].to_numpy() <= 0.5] = 1.0
        g["p"] = p
        ordem = np.argsort(p)
        m = len(p)
        lim = 0.05 * np.arange(1, m + 1) / m
        passa = p[ordem] <= lim
        k = np.max(np.flatnonzero(passa)) + 1 if passa.any() else 0
        bh = np.zeros(m, bool)
        bh[ordem[:k]] = True
        g["bh"] = bh
        teto = (g[(g["arm"] != "aleatorio") & (g["rodadas"] == SPEC[algo])]
                .set_index(["modelo", "dispositivos_treino", "bolsa"])["f1"])
        g["teto"] = [teto.get((a, b, c), np.nan) for a, b, c in
                     zip(g["modelo"], g["dispositivos_treino"], g["bolsa"])]
        g["detectada"] = g["bh"] & (g["f1"] > g["teto"])
        out.append(g)
    return pd.concat(out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--algos", nargs="+", default=["ascon", "gift", "schwaemm"])
    ap.add_argument("--arms", nargs="+", default=["texto-en", "aleatorio"])
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--smoke", action="store_true")
    a = ap.parse_args()
    global OUT
    treino, bolsas, n_teste = TREINO, BOLSAS, N_TESTE
    if a.smoke:
        treino, bolsas, n_teste, a.algos = [3, 30], [1, 10], 100, ["ascon"]
        OUT = OUT / "smoke"
    co.OUT = OUT
    OUT.mkdir(parents=True, exist_ok=True)
    # Um CSV por chamada: os algoritmos podem rodar em processos paralelos.
    csv = OUT / f"dados_minimos_{'_'.join(a.algos)}.csv"
    n_dev = n_teste + max(treino)

    linhas = []
    for algo in a.algos:
        rodadas = [PISOS[algo], SPEC[algo]]
        for arm in a.arms:
            dados = co.gerar(algo, arm, n_dev, rodadas, a.workers)
            for r in rodadas:
                _log(f"===== {algo} {arm} r{r}: treino {treino} dispositivos, bolsas {bolsas} =====")
                linhas += avaliar(algo, arm, r, dados, treino, bolsas, n_teste)
                pd.DataFrame(linhas).to_csv(csv, index=False)
            del dados
    df = criterio(pd.DataFrame(linhas))
    df.to_csv(csv, index=False)
    piso = df[(df["arm"] != "aleatorio") & (df["rodadas"] == df["algo"].map(PISOS))]
    tab = (piso.groupby(["algo", "dispositivos_treino", "bolsa"])["detectada"].sum()
           .unstack("bolsa"))
    _log("células detectadas na rodada do piso (de 3 classificadores):\n" + tab.to_string())
    fp = df[df["arm"] == "aleatorio"]["detectada"].sum()
    _log(f"braço aleatório: {fp} célula(s) detectada(s) de {(df['arm'] == 'aleatorio').sum()}")
    _log(f"fim -> {csv}")


if __name__ == "__main__":
    main()
