"""
Redes com 100x os dados no piso e na rodada seguinte (pensado para o GIFT).

Motivação: no GIFT com 3 rodadas a ResNet extraiu mais sinal que a contagem de
bits (bolsa de 100: 85% contra 74%, com 10x os dados), então lá capacidade a
mais fez diferença. Se um modelo mais forte sobe algum piso, é ali. Este script
treina a ResNet (e a MLP) com 10x e 100x os dispositivos e mede o piso e a
rodada seguinte.

Desenho, idêntico ao da curva de orçamento (`run_curva_orcamento.py`), para os
números serem comparáveis com a contagem de bits:
- dados: os caches da curva (31.000 dispositivos x 100 pares, contador zero, XOR);
- teste: os mesmos 1.000 dispositivos (permutação com seed 42, primeiros 1.000);
- treino: 3.000 e 30.000 dos restantes (aninhados);
- braços texto e aleatório (o aleatório é nulo provado);
- a contagem de bits roda junto, no mesmo split, como referência.

Memória: 100x em float seria ~15 GB. Os bits ficam compactados (uint8) e cada
lote é desempacotado na hora. Lote 1.024 e 10 épocas (com 10x mais dados que as
rodadas anteriores, menos épocas bastam); os dois orçamentos usam os mesmos
hiperparâmetros, então a comparação 10x contra 100x é limpa.

Cada métrica sai numa linha RESULTADO no log assim que é calculada.

Uso:
    python scripts/reduced_rounds/kaggle_100x.py --algo gift --rounds 3 4 --dados <pasta com os .npz da curva>
    python scripts/reduced_rounds/kaggle_100x.py --algo gift --rounds 3 4 --smoke
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

import numpy as np  # noqa: E402
import torch  # noqa: E402
from torch import nn  # noqa: E402

from scripts.reduced_rounds.neural_floor import DISPOSITIVO, _MLP, _ResNetGohr, _por_posicao  # noqa: E402

PARES = 100
SEED_SPLIT, SEED_MODEL, SEED_BOOT = 42, 7, 42
BAGS = (1, 10, 100)


def _log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def _lote(pos, neg, linhas, classe, modelo):
    packed = np.where(classe[:, None], pos[linhas], neg[linhas])
    bits = np.unpackbits(packed, axis=1).astype(np.float32)
    x = bits if modelo == "MLP_Shen" else _por_posicao(bits, 1)
    return torch.from_numpy(x)


def treinar(modelo, pos, neg, idx_tr, epocas, lote, lr, seed):
    torch.manual_seed(seed)
    nbits = pos.shape[1] * 8
    rede = (_MLP(nbits) if modelo == "MLP_Shen" else _ResNetGohr(8, nbits // 8)).to(DISPOSITIVO)
    otim = torch.optim.Adam(rede.parameters(), lr=lr, weight_decay=1e-5)
    perda = nn.CrossEntropyLoss()
    rng = np.random.default_rng(seed)
    n = len(idx_tr)
    rede.train()
    for ep in range(epocas):
        t0 = time.time()
        ordem = rng.permutation(2 * n)
        soma, passos = 0.0, 0
        for i in range(0, 2 * n, lote):
            sel = ordem[i:i + lote]
            if len(sel) < 2:
                continue
            classe = sel >= n
            linhas = idx_tr[sel % n]
            x = _lote(pos, neg, linhas, classe, modelo).to(DISPOSITIVO, non_blocking=True)
            y = torch.from_numpy(classe.astype(np.int64)).to(DISPOSITIVO)
            otim.zero_grad()
            l = perda(rede(x), y)
            l.backward()
            otim.step()
            soma += float(l)
            passos += 1
        _log(f"    {modelo} época {ep + 1}/{epocas}: perda {soma / max(passos, 1):.4f} ({time.time() - t0:.0f}s)")
    return rede


@torch.no_grad()
def prever(rede, modelo, pos, neg, idx, classe):
    rede.eval()
    saidas = []
    for i in range(0, len(idx), 8192):
        x = _lote(pos, neg, idx[i:i + 8192], classe[i:i + 8192], modelo).to(DISPOSITIVO)
        saidas.append(torch.softmax(rede(x), dim=1).cpu().numpy())
    return np.concatenate(saidas)


def nb_bits(pos, neg, idx_tr, idx_te_l, classe_te):
    """Contagem de bits (Bernoulli ingênuo, Laplace 1), a referência da curva."""
    def contar(arr):
        s = np.zeros(arr.shape[1] * 8)
        for i in range(0, len(idx_tr), 200_000):
            s += np.unpackbits(arr[idx_tr[i:i + 200_000]], axis=1).sum(axis=0)
        return s
    n = len(idx_tr)
    p1 = (contar(pos) + 1) / (n + 2)
    p0 = (contar(neg) + 1) / (n + 2)
    w = np.log(p1 / p0) - np.log((1 - p1) / (1 - p0))
    b = np.log((1 - p1) / (1 - p0)).sum()
    out = []
    for i in range(0, len(idx_te_l), 100_000):
        sl = slice(i, i + 100_000)
        packed = np.where(classe_te[sl, None], pos[idx_te_l[sl]], neg[idx_te_l[sl]])
        logit = np.unpackbits(packed, axis=1) @ w + b
        p = 1 / (1 + np.exp(-np.clip(logit, -50, 50)))
        out.append(np.column_stack([1 - p, p]))
    return np.concatenate(out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--algo", default="gift")
    ap.add_argument("--rounds", nargs="+", type=int, default=[3, 4])
    ap.add_argument("--arms", nargs="+", default=["texto", "aleatorio"])
    ap.add_argument("--dados", type=Path,
                    default=REPO_ROOT / "build" / "reduced_rounds" / "floor_v2" / "curva_orcamento")
    ap.add_argument("--saida", type=Path,
                    default=REPO_ROOT / "build" / "reduced_rounds" / "floor_v2" / "kaggle_100x")
    ap.add_argument("--treino", nargs="+", type=int, default=[3_000, 30_000])
    ap.add_argument("--n-test", type=int, default=1_000)
    ap.add_argument("--modelos", nargs="+", default=["ResNet_Gohr", "MLP_Shen"])
    ap.add_argument("--epocas", type=int, default=10)
    ap.add_argument("--lote", type=int, default=1024)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--sem-binarios", action="store_true",
                    help="força os substitutos, para testar localmente o caminho do Kaggle")
    a = ap.parse_args()
    # No Kaggle não há os .pyd das cifras nem o nistrng; o run_gift_floor os
    # importa no carregamento. Mesmos substitutos do kaggle_piso.py.
    from scripts.reduced_rounds.kaggle_piso import preparar_ambiente
    trocados = preparar_ambiente(a.sem_binarios)
    if trocados:
        _log(f"substitutos (sem binários): {trocados}")
    from scripts.reduced_rounds.run_gift_floor import _bags
    from src.eval.reporting import report_eval
    if a.smoke:
        a.treino, a.n_test, a.epocas = [30, 300], 100, 1
        a.saida = a.saida / "smoke"
    a.saida.mkdir(parents=True, exist_ok=True)
    _log(f"torch {torch.__version__} | dispositivo {DISPOSITIVO}"
         + (f" ({torch.cuda.get_device_name(0)})" if DISPOSITIVO == "cuda" else ""))

    for arm in a.arms:
        z = np.load(a.dados / f"{a.algo}_{arm}_dev31000.npz")
        dev = z["dev"]
        n_dev = int(dev.max()) + 1
        ordem = np.random.default_rng(SEED_SPLIT).permutation(n_dev)
        teste_dev = np.sort(ordem[:a.n_test])
        pool = ordem[a.n_test:]
        idx_te = np.flatnonzero(np.isin(dev, teste_dev))
        idx_te_l = np.concatenate([idx_te, idx_te])
        classe_te = np.concatenate([np.zeros(len(idx_te), bool), np.ones(len(idx_te), bool)])
        yte = classe_te.astype(int)
        key_ids = np.array([f"d{k:05d}" for k in dev[idx_te_l]])
        neg = z["random"]
        for r in a.rounds:
            pos = z[f"r{r}"]
            for n_tr in a.treino:
                idx_tr = np.flatnonzero(np.isin(dev, pool[:n_tr]))
                for modelo in ["NB_bits"] + a.modelos:
                    _log(f"######## {a.algo} {arm} r{r} {modelo} treino={n_tr} dispositivos "
                         f"({2 * len(idx_tr)} amostras)")
                    t0 = time.time()
                    if modelo == "NB_bits":
                        proba = nb_bits(pos, neg, idx_tr, idx_te_l, classe_te)
                    else:
                        rede = treinar(modelo, pos, neg, idx_tr, a.epocas, a.lote, a.lr, SEED_MODEL)
                        proba = prever(rede, modelo, pos, neg, idx_te_l, classe_te)
                        del rede
                        if DISPOSITIVO == "cuda":
                            torch.cuda.empty_cache()
                    seg = time.time() - t0
                    for bag in BAGS:
                        by, bp, bk = _bags(proba, yte, key_ids, bag)
                        nome = f"{modelo}_n{n_tr}_bag{bag}"
                        rep = report_eval(
                            run_id=f"x100_{a.algo}_{arm}_r{r}", caminho="A", modelo=nome,
                            braco=f"x100_{a.algo}_{arm}", fold="final", y_true=by,
                            y_pred=bp.argmax(1), y_proba=bp,
                            sample_ids=[f"{k}_{l}_{i}" for i, (k, l) in enumerate(zip(bk, by))],
                            key_ids=list(bk), class_names=["aleatório uniforme", f"{a.algo} {r}"],
                            labels=[0, 1], out_dir=a.saida / "reports", seed=SEED_BOOT,
                            extra=dict(algo=a.algo, rounds=r, arm=arm, dispositivos_treino=n_tr,
                                       pares_por_decisao=bag, epocas=a.epocas, lote=a.lote,
                                       fit_seconds=round(seg, 1)))
                        d = rep.as_dict()
                        auc = d.get("auc_roc")
                        print("RESULTADO " + json.dumps(dict(
                            algo=a.algo, run_id=f"x100_{a.algo}_{arm}_r{r}", modelo=nome,
                            fold="final", arm=arm, rounds=r, bolsa=bag, n=len(by),
                            dispositivos_treino=n_tr, f1=d.get("f1_macro"),
                            f1_lo=d.get("f1_macro_ci_lower"), f1_hi=d.get("f1_macro_ci_upper"),
                            auc=auc.get("auc") if isinstance(auc, dict) else auc,
                            fit_s=round(seg, 1)), ensure_ascii=False, default=float), flush=True)
                    print(f"FEITO {a.algo}\t{arm} r{r} {modelo} n{n_tr}\t{seg:.0f}s", flush=True)
        del z
    _log("fim")


if __name__ == "__main__":
    main()
