"""
Tamanho do criptograma x representação, com o criptograma isolado.

O primeiro experimento (64 KB, 641 atributos) não detectou nada, e o segundo
(80 bytes, bits crus) detectou a primeira rodada. Entre os dois mudaram, ao
mesmo tempo, o tamanho e a representação. Este script mede as duas células que
faltam no 2 x 2:

  atributos80  Os 641 atributos calculados sobre os criptogramas isolados de
               80 bytes do estudo com bits crus (mesmo cache, contador zero,
               `texto-en`), com os mesmos classificadores, bolsas e critério.
               Em 80 bytes, a família da tag e alguns testes do NIST ficam
               indefinidos ou constantes (NaN vira 0, como no de 64 KB).

  bits64k      Os bits crus dos criptogramas de 64 KB, sem atributos. Os
               criptogramas são regerados com o mesmo gerador e as mesmas
               sementes do experimento de 64 KB (mesma amostra) e guardados em
               disco. Com 524 288 bits por amostra, só a regressão logística
               treinada por SGD em minilotes é viável; ela é avaliada no mesmo
               criptograma truncado em 80 bytes, 1 KB, 8 KB e 64 KB, para ver o
               efeito do tamanho com a representação e o modelo fixos.

Uso:
    python scripts/reduced_rounds/run_representacao.py atributos80 [--smoke]
    python scripts/reduced_rounds/run_representacao.py bits64k [--smoke]
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
import pandas as pd  # noqa: E402
from joblib import Parallel, delayed  # noqa: E402
from scipy.stats import norm  # noqa: E402

from scripts.reduced_rounds import run_isolado_64k as iso  # noqa: E402
from scripts.reduced_rounds.floor_algos import ALGOS  # noqa: E402
from scripts.reduced_rounds.run_gift_floor import (  # noqa: E402
    BAG_SIZES, DEFAULT_MODELS, NEEDS_SCALING, SEED_BOOT, SEED_SPLIT, _bags)
from src.crypto.ctr_drbg import CTRDRBG  # noqa: E402

FLOOR = REPO_ROOT / "build" / "reduced_rounds" / "floor_v2"
UNICO = FLOOR / "contador_zero_unico_corpus_en"
OUT = FLOOR / "representacao"
ORDEM = ("ascon", "gift", "schwaemm")
TAMANHOS = (80, 1024, 8192, 65_552)
_log = iso._log


# --------------------------------------------------------------------- comum
def _pvalor_bh(df: pd.DataFrame, grupo: str) -> pd.DataFrame:
    meia = (df["f1_hi"] - df["f1_lo"]) / 2
    p = 2 * (1 - norm.cdf(np.abs(((df["f1"] - 0.5) / (meia / 1.96)).to_numpy())))
    p[df["f1"].to_numpy() <= 0.5] = 1.0
    df["p"], df["bh"] = p, False
    for _, g in df.groupby(grupo):
        pg = g["p"].to_numpy()
        ordem = np.argsort(pg)
        passa = pg[ordem] <= 0.05 * np.arange(1, len(pg) + 1) / len(pg)
        k = np.max(np.flatnonzero(passa)) + 1 if passa.any() else 0
        df.loc[g.index[ordem[:k]], "bh"] = True
    return df


def _relatar(proba, y, keys, run_id, modelo, braco, extra, nomes, linhas, base, bolsas=BAG_SIZES):
    from src.eval.reporting import report_eval
    for bag in bolsas:
        by, bp, bk = _bags(proba, y, keys, bag)
        rep = report_eval(
            run_id=run_id, caminho="A", modelo=f"{modelo}_bag{bag}", braco=braco, fold="final",
            y_true=by, y_pred=bp.argmax(1), y_proba=bp,
            sample_ids=[f"{k}_{l}_{i}" for i, (k, l) in enumerate(zip(bk, by))],
            key_ids=list(bk), class_names=nomes, labels=[0, 1], out_dir=OUT / "reports",
            seed=SEED_BOOT, extra={**extra, "bolsa": bag})
        d = rep.as_dict()
        auc = d.get("auc_roc")
        linhas.append({**base, "modelo": modelo, "bolsa": bag, "f1": d.get("f1_macro"),
                       "f1_lo": d.get("f1_macro_ci_lower"), "f1_hi": d.get("f1_macro_ci_upper"),
                       "auc": auc.get("auc") if isinstance(auc, dict) else auc})


# ---------------------------------------------------------- atributos em 80 B
def _atr(linhas: np.ndarray) -> np.ndarray:
    return np.vstack([iso._atributos(bytes(r)) for r in linhas])


def atributos80(smoke: bool, jobs: int) -> pd.DataFrame:
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    from scripts.run_v2_caminho_a import build_models

    linhas = []
    n_keys, n_test = (20, 5) if smoke else (300, 60)
    for algo in ORDEM:
        z = np.load(UNICO / f"{algo}_floor" / f"{algo}_texto-en_k300.npz")
        rodadas = sorted(int(k[1:]) for k in z.files if k.startswith("r") and k[1:].isdigit())
        kidx = z["key_idx"]
        sel = kidx < n_keys
        cache = OUT / f"atributos80_{algo}{'_smoke' if smoke else ''}.npz"
        feats = dict(np.load(cache)) if cache.exists() else {}
        with Parallel(n_jobs=jobs, prefer="processes") as par:
            for nome in ["random"] + [f"r{r}" for r in rodadas]:
                if nome in feats:
                    continue
                X = z[nome][sel]
                partes = par(delayed(_atr)(X[i:i + 500]) for i in range(0, len(X), 500))
                feats[nome] = np.vstack(partes)
                np.savez(cache, **feats)
                _log(f"[{algo}] atributos de {nome}: {feats[nome].shape}")
        keys = np.arange(n_keys)
        np.random.default_rng(SEED_SPLIT).shuffle(keys)
        teste = keys[:n_test]
        dev = kidx[sel]
        te = np.isin(dev, teste)
        for r in rodadas:
            X = np.nan_to_num(np.vstack([feats["random"], feats[f"r{r}"]]), posinf=0, neginf=0)
            y = np.concatenate([np.zeros(len(dev), int), np.ones(len(dev), int)])
            m_te = np.concatenate([te, te])
            key_ids = np.array([f"d{k:03d}" for k in np.concatenate([dev, dev])[m_te]])
            modelos = build_models()
            for nome in DEFAULT_MODELS:
                m = modelos[nome]
                if nome in NEEDS_SCALING:
                    m = Pipeline([("scaler", StandardScaler()), ("clf", m)])
                proba = m.fit(X[~m_te], y[~m_te]).predict_proba(X[m_te])
                _relatar(proba, y[m_te], key_ids, f"atributos80_{algo}_r{r}", nome,
                         f"atributos80_{algo}", dict(algo=algo, rounds=r, arm="texto-en",
                         representacao="criptograma isolado de 80 bytes, 641 atributos"),
                         ["aleatório uniforme", f"{ALGOS[algo].rotulo} {r}"], linhas,
                         dict(algo=algo, rodadas=r))
            _log(f"[{algo}] r{r} avaliado")
    df = _pvalor_bh(pd.DataFrame(linhas), "algo")
    # teto: maior F1 na rodada da especificação, por modelo e bolsa
    df["teto"] = np.nan
    for algo, g in df.groupby("algo"):
        spec = g["rodadas"].max()
        for (mod, bag), gg in g.groupby(["modelo", "bolsa"]):
            t = gg.loc[gg["rodadas"] == spec, "f1"].max()
            df.loc[gg.index, "teto"] = t
    df["detectado"] = df["bh"] & (df["f1"] > df["teto"])
    return df


# ------------------------------------------------------------- bits em 64 KB
def gerar_64k(n_keys: int, msgs: int) -> dict:
    """Mesma amostra do experimento de 64 KB (sementes e rótulos de iso.gerar),
    guardada em bytes, num memmap por classe."""
    OUT.mkdir(parents=True, exist_ok=True)
    n = n_keys * msgs
    classes = ORDEM + ("random",)
    caminhos = {c: OUT / f"ct64k_{c}_k{n_keys}_m{msgs}.u8" for c in classes}
    pronto = OUT / f"ct64k_k{n_keys}_m{msgs}.ok"
    if pronto.exists():
        return {c: np.memmap(p, np.uint8, "r", shape=(n, iso.CT_BYTES)) for c, p in caminhos.items()}
    mm = {c: np.memmap(p, np.uint8, "w+", shape=(n, iso.CT_BYTES)) for c, p in caminhos.items()}
    iso._conferir_gift()
    ciphers = {"ascon": ALGOS["ascon"].cipher(iso.RODADAS),
               "schwaemm": ALGOS["schwaemm"].cipher(iso.RODADAS), "gift": iso.GiftOficial(iso.RODADAS)}
    key_drbg = CTRDRBG(seed=iso.SEED_GEN, label="iso64k-keys")
    pt_drbg = CTRDRBG(seed=iso.SEED_GEN, label="iso64k-pt-texto-en")
    rnd_drbg = CTRDRBG(seed=iso.SEED_GEN, label="iso64k-random")
    sample = iso._TextPlaintextSampler(iso.CORPORA_DIR.parent / "corpora_en", pt_drbg).sample
    t0 = time.time()
    for k in range(n_keys):
        key = key_drbg.random_key(16)
        for j in range(msgs):
            pt, rnd, i = sample(), rnd_drbg.generate(iso.CT_BYTES), k * msgs + j
            for a in ORDEM:
                ct = ciphers[a].encrypt(key, j.to_bytes(ALGOS[a].nonce_bytes, "big"), pt)
                mm[a][i] = np.frombuffer(ct, np.uint8)
            mm["random"][i] = np.frombuffer(rnd, np.uint8)
        if (k + 1) % 25 == 0:
            _log(f"64 KB: chaves {k + 1}/{n_keys} ({time.time() - t0:.0f}s)")
    for m in mm.values():
        m.flush()
    pronto.write_text("ok")
    return {c: np.memmap(p, np.uint8, "r", shape=(n, iso.CT_BYTES)) for c, p in caminhos.items()}


def _lr_sgd(Xc, Xr, idx_tr, idx_te, tam, epocas=5, lote=128, seed=7):
    """Regressão logística por SGD sobre os bits dos primeiros `tam` bytes."""
    from sklearn.linear_model import SGDClassifier
    clf = SGDClassifier(loss="log_loss", alpha=1e-4, random_state=seed)
    rng = np.random.default_rng(seed)
    amostras = np.concatenate([np.stack([idx_tr, np.zeros_like(idx_tr)], 1),
                               np.stack([idx_tr, np.ones_like(idx_tr)], 1)])

    def _bits(pares):
        rows = [(Xr if c == 0 else Xc)[i, :tam] for i, c in pares]
        return np.unpackbits(np.stack(rows), axis=1).astype(np.float32) * 2 - 1

    for ep in range(epocas):
        rng.shuffle(amostras)
        for s in range(0, len(amostras), lote):
            pares = amostras[s:s + lote]
            clf.partial_fit(_bits(pares), pares[:, 1], classes=[0, 1])
    te_pares = np.concatenate([np.stack([idx_te, np.zeros_like(idx_te)], 1),
                               np.stack([idx_te, np.ones_like(idx_te)], 1)])
    proba = np.vstack([clf.predict_proba(_bits(te_pares[s:s + 512]))
                       for s in range(0, len(te_pares), 512)])
    return proba, te_pares[:, 1]


def bits64k(smoke: bool) -> pd.DataFrame:
    n_keys, msgs, n_test = (20, 10, 5) if smoke else (iso.N_KEYS, iso.MSGS, iso.N_TEST)
    dados = gerar_64k(n_keys, msgs)
    dev = np.repeat(np.arange(n_keys), msgs)
    teste = np.random.default_rng(SEED_SPLIT).permutation(n_keys)[:n_test]
    te = np.isin(dev, teste)
    idx_tr, idx_te = np.flatnonzero(~te), np.flatnonzero(te)
    linhas = []
    for algo in ORDEM:
        for tam in TAMANHOS:
            t0 = time.time()
            proba, y = _lr_sgd(dados[algo], dados["random"], idx_tr, idx_te, tam)
            key_ids = np.array([f"d{k:03d}" for k in np.concatenate([dev[idx_te], dev[idx_te]])])
            _relatar(proba, y, key_ids, f"bits64k_{algo}_t{tam}", "LogReg_SGD", f"bits64k_{algo}",
                     dict(algo=algo, rounds=1, tamanho_bytes=tam, arm="texto-en",
                          representacao=f"bits crus dos primeiros {tam} bytes do criptograma de 64 KB"),
                     ["aleatório uniforme", f"{ALGOS[algo].rotulo} 1"], linhas,
                     dict(algo=algo, tamanho=tam), bolsas=[b for b in BAG_SIZES if b <= msgs])
            _log(f"[{algo}] {tam} bytes: {time.time() - t0:.0f}s")
    return _pvalor_bh(pd.DataFrame(linhas), "algo")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("modo", choices=["atributos80", "bits64k"])
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--jobs", type=int, default=6)
    a = ap.parse_args()
    global OUT
    if a.smoke:
        OUT = OUT / "smoke"
    OUT.mkdir(parents=True, exist_ok=True)
    df = atributos80(a.smoke, a.jobs) if a.modo == "atributos80" else bits64k(a.smoke)
    csv = OUT / f"{a.modo}.csv"
    df.to_csv(csv, index=False)
    _log(f"resultado em {csv}")
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
