"""
Curva de orçamento: o piso em função de quantos criptogramas o atacante usa.

Pergunta: a rodada logo acima do piso continua indistinguível se o atacante
tiver 10 ou 100 vezes mais criptogramas para montar o detector? Se continuar,
dá para dizer "com até N criptogramas observados, nenhum detector que testamos
passou da rodada X", que é a forma honesta de dizer "o máximo que conseguimos".

Desenho:
- Cenário do contador zero (o que define o piso da tese), representação XOR,
  e a MESMA amostragem de `run_floor.py` (mesmos rótulos do DRBG, mesma
  ordem): os primeiros 300 dispositivos são os mesmos das rodadas anteriores.
  `--validar` confere isso byte a byte contra `run_floor.generate`.
- Um conjunto grande de dispositivos (100 pares cada). 1.000 ficam para teste,
  sempre os mesmos; o treino usa 300, 3.000 ou 30.000 dos restantes (aninhados).
  São 1x, 10x e 100x o orçamento das rodadas anteriores.
- Rodadas: o piso de cada algoritmo (checagem de sanidade, tem que detectar
  com folga) e a rodada seguinte (a pergunta).

Detectores:
- `NB_bits`: Bernoulli ingênuo sobre os bits do XOR, por contagem. Para um
  sinal feito de bits com viés independentes, que é o que medimos, a razão de
  verossimilhança por bit é o detector ótimo, e por ser só contagem escala para
  milhões de pares sem carregar tudo na memória.
- `LR`: a regressão logística das rodadas anteriores (melhor detector até aqui),
  em 1x e 10x. Em 100x ela precisaria de ~15 GB de memória.

Geração em paralelo: a amostragem (chaves, textos, classe aleatória) é feita em
sequência no processo principal, igual ao `run_floor.py`, e só as cifragens vão
para os processos filhos. O GIFT com granularidade de uma rodada é Python puro,
e é ele que dita o tempo.

Uso:
    python scripts/reduced_rounds/run_curva_orcamento.py --validar
    python scripts/reduced_rounds/run_curva_orcamento.py --smoke
    python scripts/reduced_rounds/run_curva_orcamento.py
"""
from __future__ import annotations

import argparse
import sys
import time
from multiprocessing import Pool
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src" / "crypto"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

PISOS = {"ascon": 3, "gift": 3, "grain": 28, "schwaemm": 2}
PARES = 100
OUT = REPO_ROOT / "build" / "reduced_rounds" / "floor_v2" / "curva_orcamento"


def _log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# --------------------------------------------------------------------------
# geração
# --------------------------------------------------------------------------

def sortear(algo: str, arm: str, n_dev: int):
    """Chaves, textos e classe aleatória, na MESMA ordem do run_floor.generate
    (contador zero, representação xor)."""
    from scripts.reduced_rounds import run_floor as rf
    from scripts.reduced_rounds.floor_algos import ALGOS
    from src.crypto.ctr_drbg import CTRDRBG

    spec = ALGOS[algo]
    largura = rf.MSG_BYTES + spec.tag_bytes
    key_drbg = CTRDRBG(seed=rf.SEED_GEN, label="floor-keys")
    pt_drbg = CTRDRBG(seed=rf.SEED_GEN, label=f"floor-pt-{arm}")
    rnd_drbg = CTRDRBG(seed=rf.SEED_GEN, label=f"floor-random-{arm}")
    nonce_drbg = CTRDRBG(seed=rf.SEED_GEN, label="floor-nonceoffset")
    sample, _ = rf._sampler(arm, pt_drbg)

    n = n_dev * PARES
    chaves = np.zeros((n_dev, spec.key_bytes), np.uint8)
    p1 = np.zeros((n, rf.MSG_BYTES), np.uint8)
    p2 = np.zeros((n, rf.MSG_BYTES), np.uint8)
    rnd = np.zeros((n, largura), np.uint8)
    t0 = time.time()
    for k in range(n_dev):
        chaves[k] = np.frombuffer(key_drbg.random_key(spec.key_bytes), np.uint8)
        nonce_drbg.generate(32)        # consumido como no run_floor; com contador zero o offset é 0
        for j in range(PARES):
            a, b = sample()[:rf.MSG_BYTES], sample()[:rf.MSG_BYTES]
            while b == a:
                b = sample()[:rf.MSG_BYTES]
            i = k * PARES + j
            p1[i] = np.frombuffer(a, np.uint8)
            p2[i] = np.frombuffer(b, np.uint8)
            rnd[i] = np.frombuffer(rnd_drbg.generate(largura), np.uint8)
        if (k + 1) % 2000 == 0:
            _log(f"  [{algo}/{arm}] sorteio {k + 1}/{n_dev} dispositivos ({time.time() - t0:.0f}s)")
    return chaves, p1, p2, rnd


def _cifrar_bloco(args):
    algo, rodadas, k0, chaves, p1, p2 = args
    from scripts.reduced_rounds import run_floor as rf
    from scripts.reduced_rounds.floor_algos import ALGOS

    spec = ALGOS[algo]
    largura = rf.MSG_BYTES + spec.tag_bytes
    cifras = {r: spec.cipher(r, "ambos") for r in rodadas}
    n = len(chaves) * PARES
    out = {r: np.zeros((n, largura), np.uint8) for r in rodadas}
    for kk in range(len(chaves)):
        key = chaves[kk].tobytes()
        for j in range(PARES):
            i = kk * PARES + j
            n1 = (2 * j).to_bytes(spec.nonce_bytes, "big")       # contador zero
            n2 = (2 * j + 1).to_bytes(spec.nonce_bytes, "big")
            a1, a2 = p1[i].tobytes(), p2[i].tobytes()
            for r, c in cifras.items():
                x = c.encrypt(key, n1, a1)
                y = c.encrypt(key, n2, a2)
                out[r][i] = (np.frombuffer(x[:rf.MSG_BYTES] + x[-spec.tag_bytes:], np.uint8)
                             ^ np.frombuffer(y[:rf.MSG_BYTES] + y[-spec.tag_bytes:], np.uint8))
    return k0, out


def gerar(algo: str, arm: str, n_dev: int, rodadas: list[int], workers: int) -> dict:
    cache = OUT / f"{algo}_{arm}_dev{n_dev}.npz"
    if cache.exists():
        z = np.load(cache)
        if all(f"r{r}" in z.files for r in rodadas):
            _log(f"[{algo}/{arm}] cache {cache.name}")
            return {k: z[k] for k in z.files}
    t0 = time.time()
    chaves, p1, p2, rnd = sortear(algo, arm, n_dev)
    _log(f"[{algo}/{arm}] sorteio pronto ({time.time() - t0:.0f}s); cifrando com {workers} processos")
    passo = 100
    tarefas = [(algo, rodadas, k0, chaves[k0:k0 + passo],
                p1[k0 * PARES:(k0 + passo) * PARES], p2[k0 * PARES:(k0 + passo) * PARES])
               for k0 in range(0, n_dev, passo)]
    dados = {f"r{r}": np.zeros_like(rnd) for r in rodadas}
    feitos = 0
    with Pool(workers) as pool:
        for k0, out in pool.imap_unordered(_cifrar_bloco, tarefas):
            for r, arr in out.items():
                dados[f"r{r}"][k0 * PARES:k0 * PARES + len(arr)] = arr
            feitos += 1
            if feitos % 50 == 0 or feitos == len(tarefas):
                _log(f"  [{algo}/{arm}] cifragem {feitos}/{len(tarefas)} blocos ({time.time() - t0:.0f}s)")
    dados["random"] = rnd
    dados["dev"] = np.repeat(np.arange(n_dev), PARES).astype(np.int32)
    OUT.mkdir(parents=True, exist_ok=True)
    np.savez(cache, **dados)
    _log(f"[{algo}/{arm}] geração completa em {time.time() - t0:.0f}s -> {cache.name}")
    return dados


# --------------------------------------------------------------------------
# detectores
# --------------------------------------------------------------------------

def _contar(packed: np.ndarray, idx: np.ndarray, passo: int = 200_000) -> np.ndarray:
    soma = np.zeros(packed.shape[1] * 8, np.float64)
    for i in range(0, len(idx), passo):
        soma += np.unpackbits(packed[idx[i:i + passo]], axis=1).sum(axis=0)
    return soma


class NBBits:
    """Bernoulli ingênuo por contagem (Laplace 1). Classe 1 = cifra."""

    def fit_counts(self, pos: np.ndarray, neg: np.ndarray, idx: np.ndarray):
        n = len(idx)
        p1 = (_contar(pos, idx) + 1) / (n + 2)
        p0 = (_contar(neg, idx) + 1) / (n + 2)
        self.w = np.log(p1 / p0) - np.log((1 - p1) / (1 - p0))
        self.b = np.log((1 - p1) / (1 - p0)).sum()
        return self

    def proba(self, bits: np.ndarray) -> np.ndarray:
        logit = bits @ self.w + self.b
        p = 1.0 / (1.0 + np.exp(-np.clip(logit, -50, 50)))
        return np.column_stack([1 - p, p])


def avaliar(algo: str, arm: str, r: int, dados: dict, treino_niveis: list[int],
            n_test: int, n_lr_max: int) -> list[dict]:
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    from scripts.reduced_rounds.run_gift_floor import BAG_SIZES, SEED_BOOT, SEED_MODEL, SEED_SPLIT, _bags
    from src.eval.reporting import report_eval

    pos, neg, dev = dados[f"r{r}"], dados["random"], dados["dev"]
    n_dev = int(dev.max()) + 1
    ordem = np.random.default_rng(SEED_SPLIT).permutation(n_dev)
    teste_dev = np.sort(ordem[:n_test])
    pool_treino = ordem[n_test:]
    idx_teste = np.flatnonzero(np.isin(dev, teste_dev))
    Xte = np.vstack([np.unpackbits(neg[idx_teste], axis=1),
                     np.unpackbits(pos[idx_teste], axis=1)]).astype(np.float32)
    yte = np.concatenate([np.zeros(len(idx_teste), int), np.ones(len(idx_teste), int)])
    kte = np.concatenate([dev[idx_teste], dev[idx_teste]])
    key_ids = np.array([f"d{k:05d}" for k in kte])
    nomes = ["aleatório uniforme", f"{algo} {r}"]
    run_id = f"curva_{algo}_{arm}_r{r}"
    linhas = []

    def relatar(modelo: str, proba: np.ndarray, n_dev_treino: int, t: float):
        for bag in BAG_SIZES:
            by, bp, bk = _bags(proba, yte, key_ids, bag)
            rep = report_eval(
                run_id=run_id, caminho="A", modelo=f"{modelo}_bag{bag}", braco=f"curva_{algo}_{arm}",
                fold="final", y_true=by, y_pred=bp.argmax(1), y_proba=bp,
                sample_ids=[f"{k}_{l}_{i}" for i, (k, l) in enumerate(zip(bk, by))],
                key_ids=list(bk), class_names=nomes, labels=[0, 1], out_dir=OUT / "reports",
                seed=SEED_BOOT,
                extra=dict(algo=algo, rounds=r, arm=arm, politica="ambos", contador="zero",
                           representacao="xor", detector=modelo.split("_n")[0],
                           dispositivos_treino=n_dev_treino, pares_treino=n_dev_treino * PARES,
                           dispositivos_teste=n_test, pares_por_decisao=bag, nivel="bolsa",
                           fit_seconds=round(t, 1)))
            d = rep.as_dict()
            linhas.append(dict(algo=algo, arm=arm, rodadas=r, detector=modelo.split("_n")[0],
                               dispositivos_treino=n_dev_treino, bolsa=bag,
                               f1=d.get("f1_macro"), f1_lo=d.get("f1_macro_ci_lower"),
                               f1_hi=d.get("f1_macro_ci_upper"), auc=_auc(d)))

    for n_tr in treino_niveis:
        idx_tr = np.flatnonzero(np.isin(dev, pool_treino[:n_tr]))
        t0 = time.time()
        nb = NBBits().fit_counts(pos, neg, idx_tr)
        relatar(f"NB_bits_n{n_tr}", nb.proba(Xte), n_tr, time.time() - t0)
        if n_tr <= n_lr_max:
            Xtr = np.vstack([np.unpackbits(neg[idx_tr], axis=1),
                             np.unpackbits(pos[idx_tr], axis=1)]).astype(np.float32)
            ytr = np.concatenate([np.zeros(len(idx_tr), int), np.ones(len(idx_tr), int)])
            t0 = time.time()
            lr = Pipeline([("s", StandardScaler()),
                           ("c", LogisticRegression(max_iter=2000, random_state=SEED_MODEL))]).fit(Xtr, ytr)
            relatar(f"LR_n{n_tr}", lr.predict_proba(Xte), n_tr, time.time() - t0)
            del Xtr
    return linhas


def _auc(d: dict):
    a = d.get("auc_roc")
    return a.get("auc") if isinstance(a, dict) else a


# --------------------------------------------------------------------------

def validar() -> None:
    """Os primeiros dispositivos têm que ser byte a byte os do run_floor."""
    import tempfile

    from scripts.reduced_rounds import run_floor as rf
    for algo, arm in (("ascon", "texto"), ("grain", "aleatorio")):
        r = PISOS[algo]
        with tempfile.TemporaryDirectory() as tmp:
            ref = rf.generate(algo, arm, 3, [r], Path(tmp) / "x.npz", "ambos", contador="zero")
        chaves, p1, p2, rnd = sortear(algo, arm, 3)
        _, out = _cifrar_bloco((algo, [r], 0, chaves, p1, p2))
        ok = np.array_equal(out[r], ref[f"r{r}"]) and np.array_equal(rnd, ref["random"])
        print(f"{algo}/{arm}: idêntico ao run_floor = {ok}")
        assert ok


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--algos", nargs="+", default=["ascon", "schwaemm", "grain", "gift"])
    ap.add_argument("--arms", nargs="+", default=["texto", "aleatorio"])
    ap.add_argument("--n-dev", type=int, default=31_000)
    ap.add_argument("--n-test", type=int, default=1_000)
    ap.add_argument("--treino", nargs="+", type=int, default=[300, 3_000, 30_000])
    ap.add_argument("--lr-max", type=int, default=3_000, help="maior orçamento em que a LR roda")
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--validar", action="store_true")
    ap.add_argument("--smoke", action="store_true")
    a = ap.parse_args()
    if a.validar:
        validar()
        return
    global OUT
    if a.smoke:
        a.n_dev, a.n_test, a.treino, a.algos = 400, 100, [30, 300], ["ascon"]
        OUT = OUT / "smoke"

    linhas = []
    for algo in a.algos:
        rodadas = [PISOS[algo], PISOS[algo] + 1]
        for arm in a.arms:
            dados = gerar(algo, arm, a.n_dev, rodadas, a.workers)
            for r in rodadas:
                _log(f"===== {algo} {arm} r{r}: orçamentos {a.treino} dispositivos =====")
                linhas += avaliar(algo, arm, r, dados, a.treino, a.n_test, a.lr_max)
                pd.DataFrame(linhas).to_csv(OUT / "curva.csv", index=False)
            del dados
    _log(f"fim -> {OUT / 'curva.csv'}")


if __name__ == "__main__":
    main()
