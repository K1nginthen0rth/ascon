"""
Dados mínimos, varredura fina: o menor treino, em pares, com que cada
classificador detecta o piso, e o menor número de pares observados por decisão.

Complementa o `run_dados_minimos.py`, cuja grade (3 a 300 dispositivos) não
fechou o mínimo do Ascon e do Schwaemm (já detectados com 3 dispositivos) e
deixou o do GIFT entre 300 e 1.000 pares. Aqui o treino é contado em pares,
tomados de uma permutação fixa dos 300 dispositivos de treino (conjuntos
aninhados); o teste continua sendo os mesmos 1.000 dispositivos.

Critério: BH sobre todas as células do algoritmo e teto por (classificador,
treino, bolsa) igual ao maior F1 entre a rodada da especificação no braço de
texto e as duas rodadas do braço aleatório, que é mais estável que o teto de
uma célula só. O braço aleatório, controle negativo, é medido só contra a
rodada da especificação. O mínimo de um classificador é o menor treino a partir do qual
todos os níveis maiores da grade também são detectados.

Uso:
    python scripts/reduced_rounds/run_dados_minimos_fino.py --algos ascon
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
from scripts.reduced_rounds.run_dados_minimos import N_TESTE, OUT, PISOS, SPEC, _log  # noqa: E402

PARES_TREINO = {
    "ascon": [2, 5, 10, 20, 50, 100, 200, 300],
    "schwaemm": [2, 5, 10, 20, 50, 100, 200, 300],
    "gift": [300, 400, 500, 600, 700, 800, 1000, 2000],
}
BOLSAS = [1, 10, 100]
SEED_PARES = 2026


def avaliar(algo: str, arm: str, r: int, dados: dict, pares: list[int], bolsas: list[int]) -> list[dict]:
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    from scripts.reduced_rounds.run_gift_floor import (
        DEFAULT_MODELS, NEEDS_SCALING, SEED_BOOT, SEED_SPLIT, _bags)
    from scripts.run_v2_caminho_a import build_models
    from src.eval.reporting import report_eval

    pos, neg, dev = dados[f"r{r}"], dados["random"], dados["dev"]
    n_dev = int(dev.max()) + 1
    ordem = np.random.default_rng(SEED_SPLIT).permutation(n_dev)
    teste_dev = np.sort(ordem[:N_TESTE])
    pool = np.flatnonzero(np.isin(dev, ordem[N_TESTE:]))
    pool = np.random.default_rng(SEED_PARES).permutation(pool)
    idx_te = np.flatnonzero(np.isin(dev, teste_dev))
    Xte = np.vstack([np.unpackbits(neg[idx_te], axis=1),
                     np.unpackbits(pos[idx_te], axis=1)]).astype(np.float32)
    yte = np.concatenate([np.zeros(len(idx_te), int), np.ones(len(idx_te), int)])
    kte = np.concatenate([dev[idx_te], dev[idx_te]])
    key_ids = np.array([f"d{k:05d}" for k in kte])
    nomes = ["aleatório uniforme", f"{algo} {r}"]
    run_id = f"minimos_fino_{algo}_{arm}_r{r}"
    linhas = []

    for n_tr in pares:
        idx_tr = pool[:n_tr]
        Xtr = np.vstack([np.unpackbits(neg[idx_tr], axis=1),
                         np.unpackbits(pos[idx_tr], axis=1)]).astype(np.float32)
        ytr = np.concatenate([np.zeros(n_tr, int), np.ones(n_tr, int)])
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
                    run_id=run_id, caminho="A", modelo=f"{nome}_par{n_tr}_bag{bag}",
                    braco=f"minimos_fino_{algo}_{arm}", fold="final", y_true=by,
                    y_pred=bp.argmax(1), y_proba=bp,
                    sample_ids=[f"{k}_{l}_{i}" for i, (k, l) in enumerate(zip(bk, by))],
                    key_ids=list(bk), class_names=nomes, labels=[0, 1],
                    out_dir=OUT / "reports_fino", seed=SEED_BOOT,
                    extra=dict(algo=algo, rounds=r, arm=arm, contador="zero",
                               representacao="xor", pares_treino=n_tr,
                               dispositivos_teste=N_TESTE, pares_por_decisao=bag,
                               fit_seconds=round(t, 1)))
                d = rep.as_dict()
                linhas.append(dict(algo=algo, arm=arm, rodadas=r, modelo=nome,
                                   pares_treino=n_tr, bolsa=bag,
                                   f1=d.get("f1_macro"), f1_lo=d.get("f1_macro_ci_lower"),
                                   f1_hi=d.get("f1_macro_ci_upper"), auc=co._auc(d)))
    return linhas


def criterio(df: pd.DataFrame) -> pd.DataFrame:
    out = []
    chave = ["modelo", "pares_treino", "bolsa"]
    for algo, g in df.groupby("algo"):
        g = g.copy()
        meia = (g["f1_hi"] - g["f1_lo"]) / 2
        z = (g["f1"] - 0.5) / (meia / 1.96)
        p = 2 * (1 - norm.cdf(np.abs(z.to_numpy())))
        p[g["f1"].to_numpy() <= 0.5] = 1.0
        g["p"] = p
        ordem = np.argsort(p)
        m = len(p)
        passa = p[ordem] <= 0.05 * np.arange(1, m + 1) / m
        k = np.max(np.flatnonzero(passa)) + 1 if passa.any() else 0
        bh = np.zeros(m, bool)
        bh[ordem[:k]] = True
        g["bh"] = bh
        # O braço aleatório é medido contra a rodada da especificação no texto;
        # se entrasse no próprio teto, nunca poderia acusar falso positivo.
        spec = g[(g["arm"] != "aleatorio") & (g["rodadas"] == SPEC[algo])]
        teto_alea = spec.groupby(chave)["f1"].max()
        teto_txt = pd.concat([spec, g[g["arm"] == "aleatorio"]]).groupby(chave)["f1"].max()
        g["teto"] = [(teto_alea if arm == "aleatorio" else teto_txt).get(t, np.nan)
                     for arm, t in zip(g["arm"], zip(*(g[c] for c in chave)))]
        g["detectada"] = g["bh"] & (g["f1"] > g["teto"])
        out.append(g)
    return pd.concat(out)


def minimos(df: pd.DataFrame) -> pd.DataFrame:
    """Menor treino a partir do qual todos os níveis maiores são detectados."""
    piso = df[(df["arm"] != "aleatorio") & (df["rodadas"] == df["algo"].map(PISOS))]
    linhas = []
    for (algo, modelo, bag), g in piso.groupby(["algo", "modelo", "bolsa"]):
        g = g.sort_values("pares_treino")
        det = g["detectada"].to_numpy()
        n = g["pares_treino"].to_numpy()
        # sufixo detectado: do fim para o começo, enquanto detectado
        i = len(det)
        while i > 0 and det[i - 1]:
            i -= 1
        linhas.append(dict(algo=algo, modelo=modelo, bolsa=bag,
                           pares_treino_min=(n[i] if i < len(n) else np.nan),
                           abaixo_da_grade=(i == 0)))
    return pd.DataFrame(linhas)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--algos", nargs="+", default=["ascon", "gift", "schwaemm"])
    ap.add_argument("--arms", nargs="+", default=["texto-en", "aleatorio"])
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--pares", type=int, nargs="+",
                    help="níveis de treino (pares) no lugar da grade padrão; CSV com sufixo _ext")
    a = ap.parse_args()
    co.OUT = OUT
    if a.pares:
        for algo in a.algos:
            PARES_TREINO[algo] = a.pares
    csv = OUT / f"dados_minimos_fino_{'_'.join(a.algos)}{'_ext' if a.pares else ''}.csv"
    linhas = []
    for algo in a.algos:
        rodadas = [PISOS[algo], SPEC[algo]]
        for arm in a.arms:
            dados = co.gerar(algo, arm, 1300, rodadas, a.workers)
            for r in rodadas:
                _log(f"===== {algo} {arm} r{r}: treino {PARES_TREINO[algo]} pares, bolsas {BOLSAS} =====")
                linhas += avaliar(algo, arm, r, dados, PARES_TREINO[algo], BOLSAS)
                pd.DataFrame(linhas).to_csv(csv, index=False)
            del dados
    df = criterio(pd.DataFrame(linhas))
    df.to_csv(csv, index=False)
    mn = minimos(df)
    mn.to_csv(csv.with_name(csv.stem + "_minimos.csv"), index=False)
    _log("menor treino (pares) com detecção estável na rodada do piso:\n"
         + mn.pivot_table(index=["algo", "modelo"], columns="bolsa", values="pares_treino_min").to_string())
    fp = df[df["arm"] == "aleatorio"]["detectada"].sum()
    _log(f"braço aleatório: {fp} célula(s) detectada(s) de {(df['arm'] == 'aleatorio').sum()}")
    _log(f"fim -> {csv}")


if __name__ == "__main__":
    main()
