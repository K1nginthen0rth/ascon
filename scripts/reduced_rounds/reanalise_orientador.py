"""
Análises pedidas pelo orientador (novembro de 2026), sem gerar dados novos de
cifra: tudo parte dos caches e das previsões já gravados.

- `sem-tag`: refaz o estudo principal (XOR do par, contador zero, `texto-en`)
  e a redução só da inicialização usando apenas os 64 bytes de texto cifrado,
  sem os 16 da tag. Separa o controle da parte cifrada do efeito da tag (4.3.2)
  e o efeito da inicialização do da finalização (5.4.1).
- `aa`: teste A/A. Duas amostras do mesmo processo aleatório (CTR_DRBG), uma
  contra a outra, pelo mesmo pipeline (três classificadores, bolsas de 1, 10 e
  100, 240/60 chaves). Mede a taxa de falso positivo do procedimento onde não
  pode haver sinal nenhum, inclusive na tag, e a calibração do p-valor da
  Eq. 4.1 por tamanho de bolsa.
- `permutacao`: p-valor por permutação dos rótulos dentro de cada chave de
  teste, para as células detectadas com F1 abaixo de 0,9, comparado com o
  p-valor da aproximação normal.

Uso:
    python scripts/reduced_rounds/reanalise_orientador.py sem-tag
    python scripts/reduced_rounds/reanalise_orientador.py aa --reps 20
    python scripts/reduced_rounds/reanalise_orientador.py permutacao
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src" / "crypto"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy.stats import norm  # noqa: E402

FLOOR = REPO_ROOT / "build" / "reduced_rounds" / "floor_v2"
OUT = FLOOR / "reanalise_orientador"
MSG = 64


def _log(m: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def p_normal(f1: float, lo: float, hi: float) -> float:
    """Eq. 4.1: p bicaudal com p = 1 quando F1 <= 0,50."""
    if f1 <= 0.5 or not np.isfinite(lo) or hi <= lo:
        return 1.0
    return float(2 * (1 - norm.cdf(abs((f1 - 0.5) / ((hi - lo) / 2 / 1.96)))))


def bh(p: np.ndarray, q: float = 0.05) -> np.ndarray:
    p = np.asarray(p, float)
    o = np.argsort(p)
    ok = p[o] <= q * np.arange(1, len(p) + 1) / len(p)
    k = np.flatnonzero(ok).max() + 1 if ok.any() else 0
    r = np.zeros(len(p), bool)
    r[o[:k]] = True
    return r


# ----------------------------------------------------------------- sem tag

ESTUDOS = {
    "principal": ("contador_zero_corpus_en", "ambos", ["ascon", "gift", "schwaemm"]),
    "init": ("contador_zero_corpus_en_init", "init", ["ascon", "schwaemm"]),
}


def sem_tag(estudos: list[str], algos: list[str] | None) -> None:
    from scripts.reduced_rounds import run_floor as rf

    for est in estudos:
        pasta, politica, lista = ESTUDOS[est]
        for algo in (algos or lista):
            if algo not in lista:
                continue
            base = FLOOR / pasta / f"{algo}_floor"
            rep = FLOOR / f"{pasta}_semtag" / f"{algo}_floor" / "reports"
            rep.mkdir(parents=True, exist_ok=True)
            for arm in ["texto-en", "aleatorio"]:
                suf = "" if politica == "ambos" else f"_{politica}"
                z = np.load(base / f"{algo}_{arm}{suf}_k300.npz")
                rodadas = sorted(int(k[1:]) for k in z.files if k.startswith("r") and k[1:].isdigit())
                dados = {"random": z["random"][:, :MSG], "key_idx": z["key_idx"]}
                for r in rodadas:
                    dados[f"r{r}"] = z[f"r{r}"][:, :MSG]
                _log(f"[sem-tag/{est}] {algo} {arm}: rodadas {rodadas}, {MSG * 8} bits")
                for r in rodadas:
                    rf.run_config(algo, arm, r, dados, 300, 60, 5, rep, "sweep",
                                  list(rf.DEFAULT_MODELS), politica, contador="zero",
                                  representacao="xor")
            _log(f"[sem-tag/{est}] {algo} pronto -> {rep}")


# ----------------------------------------------------------------- A/A

def aa(reps: int) -> None:
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    from scripts.reduced_rounds.run_gift_floor import (
        BAG_SIZES, DEFAULT_MODELS, NEEDS_SCALING, SEED_BOOT, SEED_SPLIT, _bags)
    from scripts.run_v2_caminho_a import build_models
    from src.crypto.ctr_drbg import CTRDRBG
    from src.eval.reporting import report_eval

    n_keys, ppk, n_test, largura = 300, 100, 60, 80
    n = n_keys * ppk
    kidx = np.repeat(np.arange(n_keys), ppk)
    keys = np.arange(n_keys)
    np.random.default_rng(SEED_SPLIT).shuffle(keys)
    te1 = np.isin(kidx, keys[:n_test])
    rep_dir = OUT / "aa" / "reports"
    rep_dir.mkdir(parents=True, exist_ok=True)
    linhas = []
    for r in range(reps):
        a = np.frombuffer(CTRDRBG(seed=999007, label=f"aa-{r}-a").generate(n * largura), np.uint8).reshape(n, largura)
        b = np.frombuffer(CTRDRBG(seed=999007, label=f"aa-{r}-b").generate(n * largura), np.uint8).reshape(n, largura)
        X = np.vstack([np.unpackbits(a, axis=1), np.unpackbits(b, axis=1)]).astype(np.float32)
        y = np.concatenate([np.zeros(n, int), np.ones(n, int)])
        kk = np.concatenate([kidx, kidx])
        key_ids = np.array([f"k{k:04d}" for k in kk])
        te = np.concatenate([te1, te1])
        modelos = build_models()
        for nome in DEFAULT_MODELS:
            m = modelos[nome]
            if nome in NEEDS_SCALING:
                m = Pipeline([("scaler", StandardScaler()), ("clf", m)])
            proba = m.fit(X[~te], y[~te]).predict_proba(X[te])
            for bag in BAG_SIZES:
                by, bp, bk = _bags(proba, y[te], key_ids[te], bag)
                d = report_eval(
                    run_id=f"aa_rep{r}", caminho="A", modelo=f"{nome}_bag{bag}", braco="aa",
                    fold="final", y_true=by, y_pred=bp.argmax(1), y_proba=bp,
                    sample_ids=[f"{k}_{l}_{i}" for i, (k, l) in enumerate(zip(bk, by))],
                    key_ids=list(bk), class_names=["aleatório A", "aleatório B"], labels=[0, 1],
                    out_dir=rep_dir, seed=SEED_BOOT,
                    extra=dict(teste="A/A", replica=r, pares_por_decisao=bag)).as_dict()
                auc = d.get("auc_roc")
                f1, lo, hi = d["f1_macro"], d["f1_macro_ci_lower"], d["f1_macro_ci_upper"]
                linhas.append(dict(rep=r, modelo=nome, bolsa=bag, f1=f1, lo=lo, hi=hi,
                                   auc=auc.get("auc") if isinstance(auc, dict) else auc,
                                   p=p_normal(f1, lo, hi)))
        df = pd.DataFrame(linhas)
        df.to_csv(OUT / "aa" / "aa.csv", index=False)
        _log(f"[aa] réplica {r + 1}/{reps}: p<0,05 até agora {int((df.p < 0.05).sum())} de {len(df)}")
    df = pd.DataFrame(linhas)
    df["bh_por_replica"] = df.groupby("rep")["p"].transform(lambda p: bh(p.values))
    df.to_csv(OUT / "aa" / "aa.csv", index=False)
    res = df.groupby("bolsa").agg(celulas=("p", "size"), p_menor_005=("p", lambda p: (p < 0.05).mean()),
                                  f1_max=("f1", "max"), f1_media=("f1", "mean"),
                                  auc_max=("auc", "max"))
    _log("A/A por tamanho de bolsa:\n" + res.round(4).to_string())
    _log(f"A/A: {int(df.bh_por_replica.sum())} célula(s) passam no BH (por réplica, 9 células), "
         f"de {len(df)}")


# ----------------------------------------------------------------- permutação

def _nulos_vetorizado(proba, y, k, bag, n_perm, seed=42):
    """F1 macro das bolsas sob troca dos rótulos por chave inteira.

    A unidade independente é a chave: as amostras da cifra de uma chave
    compartilham a chave, e as da classe aleatória não, então trocar rótulos
    amostra a amostra dentro da chave estreitaria demais a distribuição nula.
    Em cada permutação, um subconjunto sorteado de chaves tem os rótulos das
    suas duas classes trocados por inteiro; as decisões das bolsas não mudam,
    só o rótulo contra o qual são avaliadas. É a lógica do bootstrap por chave.
    """
    from scripts.reduced_rounds.run_gift_floor import _bags

    by, bp, bk = _bags(proba, y, k, bag)
    pred = bp.argmax(1)
    chaves = np.unique(bk)
    c = {}
    for kk in chaves:
        m = bk == kk
        c[kk] = (int(((by == 1) & m & (pred == 1)).sum()), int(((by == 1) & m).sum()),
                 int(((by == 0) & m & (pred == 1)).sum()), int(((by == 0) & m).sum()))
    rng = np.random.default_rng(seed)
    troca = rng.random((n_perm, len(chaves))) < 0.5
    tp = np.zeros(n_perm); fn = np.zeros(n_perm); fp = np.zeros(n_perm); tn = np.zeros(n_perm)
    for j, kk in enumerate(chaves):
        pos1, n1, pos0, n0 = c[kk]
        s = troca[:, j]
        tp += np.where(s, pos0, pos1)
        fn += np.where(s, n0 - pos0, n1 - pos1)
        fp += np.where(s, pos1, pos0)
        tn += np.where(s, n1 - pos1, n0 - pos0)
    f1_1 = 2 * tp / np.maximum(2 * tp + fp + fn, 1)
    f1_0 = 2 * tn / np.maximum(2 * tn + fn + fp, 1)
    return (f1_0 + f1_1) / 2


def permutacao(n_perm: int, estudos: list[str]) -> None:
    from sklearn.metrics import f1_score

    from scripts.reduced_rounds.run_gift_floor import _bags

    linhas = []
    for pasta in estudos:
        for algo in ["ascon", "gift", "schwaemm"]:
            pcsv = FLOOR / pasta / f"{algo}_floor" / "piso.csv"
            if not pcsv.exists():
                continue
            d = pd.read_csv(pcsv)
            d = d[(d.politica == "ambos") & (d.detectado) & (d.f1_macro < 0.9)]
            for _, c in d.iterrows():
                arq = glob.glob(str(FLOOR / pasta / f"{algo}_floor" / "reports" / "predictions" /
                                    f"floor_{algo}_{c.arm}_r{int(c['rounds'])}_A_{c.modelo}_floor_*_foldfinal.parquet"))
                if not arq:
                    continue
                pr = pd.read_parquet(arq[0])
                proba = np.vstack(pr.y_proba.values)
                y = pr.y_true.to_numpy()
                k = pr.key_id.to_numpy()
                bag = int(c.bolsa)
                by, bp, _ = _bags(proba, y, k, bag)
                obs = f1_score(by, bp.argmax(1), average="macro")
                nulos = _nulos_vetorizado(proba, y, k, bag, n_perm)
                p_perm = (1 + (nulos >= obs).sum()) / (n_perm + 1)
                linhas.append(dict(estudo=pasta, algo=algo, arm=c.arm, rodadas=int(c["rounds"]),
                                   modelo=c.modelo, bolsa=bag, f1=round(obs, 4),
                                   p_normal=c.p_value, p_perm=p_perm,
                                   nulo_p95=float(np.quantile(nulos, 0.95))))
                _log(f"[perm] {pasta} {algo} {c.arm} r{int(c['rounds'])} {c.modelo} bolsa {bag}: "
                     f"F1={obs:.3f} p_normal={c.p_value:.2g} p_perm={p_perm:.2g}")
    out = OUT / "permutacao.csv"
    OUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(linhas).to_csv(out, index=False)
    _log(f"fim -> {out}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("acao", choices=["sem-tag", "aa", "permutacao"])
    ap.add_argument("--estudos", nargs="+", default=None)
    ap.add_argument("--algos", nargs="+", default=None)
    ap.add_argument("--reps", type=int, default=20)
    ap.add_argument("--n-perm", type=int, default=1000)
    a = ap.parse_args()
    if a.acao == "sem-tag":
        sem_tag(a.estudos or list(ESTUDOS), a.algos)
    elif a.acao == "aa":
        aa(a.reps)
    else:
        permutacao(a.n_perm, a.estudos or ["contador_zero_corpus_en", "contador_zero_unico_corpus_en"])


if __name__ == "__main__":
    main()
