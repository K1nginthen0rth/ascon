"""
Criptograma isolado de 64 KB contra dados aleatórios, com uma rodada.

Refaz o experimento da Seção 5.2.1 (que era Ascon contra GIFT) no mesmo
desenho do resto do trabalho: cada algoritmo contra a classe aleatória. Ascon
(pa = pb = 1), GIFT-COFB (1 rodada em todas as chamadas da cifra de bloco) e
Schwaemm (big = slim = 1).

Amostra igual à do piso: 300 dispositivos com 100 mensagens cada, texto
`texto-en`, contador de nonce começando do zero em cada dispositivo, mesmas
chaves e textos para os três algoritmos (Regra de Ouro 6), classe aleatória do
CTR_DRBG com o mesmo tamanho do criptograma (65 552 bytes). A diferença está no
que o classificador vê: um criptograma inteiro de 64 KB, descrito pelos 641
atributos estatísticos, em vez do XOR de um par de 80 bytes.

O GIFT-COFB usa a implementação de referência oficial com o número de rodadas
exposto (`scripts/reduced_rounds/gift_oficial/`); o Python puro seria lento
demais para 64 KB. Antes de gerar, o script confere que ela bate com o binário
de produção em 40 rodadas e com o Python puro em 1 rodada.

Avaliação: três classificadores, bolsas de 1, 10 e 100 mensagens, 60
dispositivos de teste, BH por algoritmo (nove células cada). Não há faixa de controle: ela só
seria rodada se alguma célula fosse detectada.

Uso:
    python scripts/reduced_rounds/run_isolado_64k.py --smoke
    python scripts/reduced_rounds/run_isolado_64k.py
"""
from __future__ import annotations

import argparse
import importlib.util
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

from scripts.generate_5class_v2 import CORPORA_DIR, _TextPlaintextSampler  # noqa: E402
from scripts.reduced_rounds.floor_algos import ALGOS  # noqa: E402
from src.crypto.ctr_drbg import CTRDRBG  # noqa: E402

SEED_GEN = 999005
N_KEYS = 300
MSGS = 100
N_TEST = 60
CT_BYTES = 65_536 + 16
RODADAS = 1
ORDEM = ("ascon", "gift", "schwaemm")
GIFT_DIR = REPO_ROOT / "build" / "reduced_rounds" / "_gift_oficial_rodadas"
OUT = REPO_ROOT / "build" / "reduced_rounds" / "floor_v2" / "isolado_64k"


def _log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


class GiftOficial:
    """GIFT-COFB de referência oficial, com `gift_rounds` rodadas por chamada."""

    def __init__(self, rounds: int) -> None:
        pyd = next(GIFT_DIR.glob("_gift_oficial_rodadas*.pyd"))
        spec = importlib.util.spec_from_file_location("_gift_oficial_rodadas", pyd)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self._ffi, self._lib, self.rounds = mod.ffi, mod.lib, rounds

    def encrypt(self, key: bytes, nonce: bytes, pt: bytes) -> bytes:
        ffi, lib = self._ffi, self._lib
        lib.gift_rounds = self.rounds
        c = ffi.new("unsigned char[]", len(pt) + 16)
        clen = ffi.new("unsigned long long *")
        lib.crypto_aead_encrypt(c, clen, pt, len(pt), b"", 0, ffi.NULL, nonce, key)
        return bytes(ffi.buffer(c, clen[0]))


def _conferir_gift() -> None:
    from src.crypto.gift_cofb_wrapper import GiftCOFB  # binário de produção (40 rodadas)

    from scripts.reduced_rounds.gift_pure_cipher import PureGiftCOFB

    d = CTRDRBG(seed=SEED_GEN, label="iso64k-conferencia")
    prod, of40, of1, py1 = GiftCOFB(), GiftOficial(40), GiftOficial(1), PureGiftCOFB(1)
    for n in (0, 15, 16, 33, 4096):
        k, nn, p = d.random_key(16), d.generate(16), (d.generate(n) if n else b"")
        assert of40.encrypt(k, nn, p) == prod.encrypt(k, nn, p), "GIFT oficial 40 != produção"
        if n <= 64:
            assert of1.encrypt(k, nn, p) == py1.encrypt(k, nn, p), "GIFT oficial 1 != Python puro"
    _log("GIFT oficial conferido: 40 rodadas = binário de produção, 1 rodada = Python puro")


_EXTRATOR = None


def _atributos(ct: bytes) -> np.ndarray:
    global _EXTRATOR
    if _EXTRATOR is None:
        from src.features.extractor import CiphertextFeatureExtractor
        _EXTRATOR = CiphertextFeatureExtractor()
    return np.fromiter(_EXTRATOR.extract(ct).values(), np.float64)


def gerar(n_keys: int, msgs: int, n_jobs: int) -> dict:
    """Atributos das quatro classes, com retomada por checkpoint."""
    ckpt = OUT / f"atributos_k{n_keys}_m{msgs}.npz"
    classes = ORDEM + ("random",)
    if ckpt.exists():
        z = np.load(ckpt)
        feats, feito = {c: z[c] for c in classes}, int(z["feito"])
    else:
        feats, feito = None, 0
    if feito == n_keys:
        _log(f"atributos completos em {ckpt.name}")
        return feats

    ciphers = {"ascon": ALGOS["ascon"].cipher(RODADAS), "schwaemm": ALGOS["schwaemm"].cipher(RODADAS),
               "gift": GiftOficial(RODADAS)}
    key_drbg = CTRDRBG(seed=SEED_GEN, label="iso64k-keys")
    pt_drbg = CTRDRBG(seed=SEED_GEN, label="iso64k-pt-texto-en")
    rnd_drbg = CTRDRBG(seed=SEED_GEN, label="iso64k-random")
    sample = _TextPlaintextSampler(CORPORA_DIR.parent / "corpora_en", pt_drbg).sample
    t0 = time.time()
    lote = 5  # chaves por lote de extração: 2 000 criptogramas
    with Parallel(n_jobs=n_jobs, prefer="processes") as par:
        k = 0
        while k < n_keys:
            # os DRBGs são sequenciais: as chaves já feitas são reproduzidas e descartadas
            cts, donos = [], []
            for kk in range(k, min(k + lote, n_keys)):
                key = key_drbg.random_key(16)
                for j in range(msgs):
                    pt = sample()
                    rnd = rnd_drbg.generate(CT_BYTES)
                    if kk < feito:
                        continue
                    for a in ORDEM:
                        nonce = j.to_bytes(ALGOS[a].nonce_bytes, "big")
                        ct = ciphers[a].encrypt(key, nonce, pt)
                        assert len(ct) == CT_BYTES
                        cts.append(ct)
                        donos.append((a, kk * msgs + j))
                    cts.append(rnd)
                    donos.append(("random", kk * msgs + j))
            k = min(k + lote, n_keys)
            if not cts:
                continue
            vets = par(delayed(_atributos)(c) for c in cts)
            if feats is None:
                feats = {c: np.full((n_keys * msgs, len(vets[0])), np.nan) for c in classes}
            for (c, i), v in zip(donos, vets):
                feats[c][i] = v
            feito = k
            np.savez(ckpt, feito=feito, **feats)
            _log(f"chaves {feito}/{n_keys} ({time.time() - t0:.0f}s desde o início)")
    return feats


def avaliar(feats: dict, n_keys: int, msgs: int, n_test: int) -> pd.DataFrame:
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    from scripts.reduced_rounds.run_gift_floor import (
        BAG_SIZES, DEFAULT_MODELS, NEEDS_SCALING, SEED_BOOT, SEED_SPLIT, _bags)
    from scripts.run_v2_caminho_a import build_models
    from src.eval.reporting import report_eval

    dev = np.repeat(np.arange(n_keys), msgs)
    teste = np.random.default_rng(SEED_SPLIT).permutation(n_keys)[:n_test]
    te = np.isin(dev, teste)
    bolsas = [b for b in BAG_SIZES if b <= msgs]
    linhas = []
    for algo in ORDEM:
        X = np.nan_to_num(np.vstack([feats["random"], feats[algo]]), posinf=0, neginf=0)
        y = np.concatenate([np.zeros(len(dev), int), np.ones(len(dev), int)])
        d2 = np.concatenate([dev, dev])
        m_te = np.concatenate([te, te])
        key_ids = np.array([f"d{k:03d}" for k in d2[m_te]])
        nomes = ["aleatório uniforme", f"{ALGOS[algo].rotulo} {RODADAS}"]
        modelos = build_models()
        for nome in DEFAULT_MODELS:
            m = modelos[nome]
            if nome in NEEDS_SCALING:
                m = Pipeline([("scaler", StandardScaler()), ("clf", m)])
            t0 = time.time()
            proba = m.fit(X[~m_te], y[~m_te]).predict_proba(X[m_te])
            t = time.time() - t0
            for bag in bolsas:
                by, bp, bk = _bags(proba, y[m_te], key_ids, bag)
                rep = report_eval(
                    run_id=f"isolado64k_{algo}_r{RODADAS}", caminho="A", modelo=f"{nome}_bag{bag}",
                    braco=f"isolado64k_{algo}", fold="final", y_true=by, y_pred=bp.argmax(1),
                    y_proba=bp, sample_ids=[f"{k}_{l}_{i}" for i, (k, l) in enumerate(zip(bk, by))],
                    key_ids=list(bk), class_names=nomes, labels=[0, 1], out_dir=OUT / "reports",
                    seed=SEED_BOOT,
                    extra=dict(algo=algo, rounds=RODADAS, arm="texto-en", contador="zero",
                               representacao="criptograma isolado de 64 KB, 641 atributos",
                               bolsa=bag, fit_seconds=round(t, 1)))
                d = rep.as_dict()
                auc = d.get("auc_roc")
                linhas.append(dict(algo=algo, modelo=nome, bolsa=bag, f1=d.get("f1_macro"),
                                   f1_lo=d.get("f1_macro_ci_lower"), f1_hi=d.get("f1_macro_ci_upper"),
                                   auc=auc.get("auc") if isinstance(auc, dict) else auc,
                                   matriz=json.dumps(d.get("confusion_matrix"))))
    df = pd.DataFrame(linhas)
    meia = (df["f1_hi"] - df["f1_lo"]) / 2
    p = 2 * (1 - norm.cdf(np.abs(((df["f1"] - 0.5) / (meia / 1.96)).to_numpy())))
    p[df["f1"].to_numpy() <= 0.5] = 1.0
    df["p"], df["bh"] = p, False
    # BH por algoritmo, como no critério do estudo principal (Seção 4.6)
    for _, g in df.groupby("algo"):
        pg = g["p"].to_numpy()
        ordem = np.argsort(pg)
        passa = pg[ordem] <= 0.05 * np.arange(1, len(pg) + 1) / len(pg)
        k = np.max(np.flatnonzero(passa)) + 1 if passa.any() else 0
        df.loc[g.index[ordem[:k]], "bh"] = True
    return df


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--smoke", action="store_true", help="20 chaves x 10 mensagens, 5 de teste")
    ap.add_argument("--jobs", type=int, default=-1)
    a = ap.parse_args()
    global OUT
    n_keys, msgs, n_test = (20, 10, 5) if a.smoke else (N_KEYS, MSGS, N_TEST)
    if a.smoke:
        OUT = OUT / "smoke"
    OUT.mkdir(parents=True, exist_ok=True)
    _conferir_gift()
    feats = gerar(n_keys, msgs, a.jobs)
    df = avaliar(feats, n_keys, msgs, n_test)
    csv = OUT / "isolado_64k_r1.csv"
    df.to_csv(csv, index=False)
    _log("resultado (F1 / AUC / BH):\n" + df.pivot_table(
        index=["algo", "modelo"], columns="bolsa", values="f1").round(3).to_string())
    _log("AUC:\n" + df.pivot_table(index=["algo", "modelo"], columns="bolsa",
                                    values="auc").round(3).to_string())
    _log(f"células detectadas pelo BH: {int(df['bh'].sum())} de {len(df)}")
    _log(f"fim -> {csv}")


if __name__ == "__main__":
    main()
