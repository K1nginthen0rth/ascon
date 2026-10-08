"""
Quanto dado seria preciso? O desequilíbrio quadrático (SEI) medido nos dados.

Base teórica: Baignères, Junod e Vaudenay (ASIACRYPT 2004), Teorema 6. O
distinguidor ótimo entre uma distribuição D0 e a uniforme, com n amostras
independentes, erra com probabilidade Pe ~ Phi(-sqrt(d)/2), onde
d = n * SEI(D0) e SEI(D0) = |Z| * soma_z (Pr[z] - 1/|Z|)^2. Ou seja, o número
de amostras necessário é n = d / SEI: para Pe = 5%, d ~ 10,8.

Este script estima o SEI do XOR dos pares, no cenário do piso (contador zero),
em três granularidades:
- bits: 640 distribuições de 1 bit (SEI = 4 * vies^2), somadas. É o que a
  contagem de bits e a regressão logística enxergam.
- bytes: 80 distribuições de 256 valores. Pega estrutura conjunta dentro do
  byte (a S-box de 4 bits do GIFT, por exemplo).
- pares de bytes vizinhos: 79 distribuições de 65.536 valores.

Para distribuição produto, 1 + SEI = prod(1 + SEI_i) ~ 1 + soma SEI_i; somar
as posições é a aproximação de primeira ordem (vieses pequenos).

Estimador sem viés: o SEI empírico de uma amostra uniforme de tamanho N vale
em média (|Z| - 1) / N; subtrai-se isso. O desvio padrão dessa estatística sob
a uniforme é sqrt(2 (|Z| - 1)) / N por posição. O braço aleatório (nulo
provado) é medido junto e serve de verificação do ruído.

Dados: os caches da curva de orçamento (31.000 dispositivos x 100 pares =
3,1 milhões de pares por classe) para o piso e o piso + 1, e os do pacote do
Kaggle (300 mil pares) para a rodada 1 e a especificação.

Uso:
    python scripts/reduced_rounds/sei_dados.py
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

import numpy as np  # noqa: E402

PISOS = {"ascon": 3, "gift": 3, "grain": 28, "schwaemm": 2}
SPEC = {"ascon": 12, "gift": 40, "grain": 256, "schwaemm": 11}
CURVA = REPO_ROOT / "build" / "reduced_rounds" / "floor_v2" / "curva_orcamento"
PACOTE = REPO_ROOT / "build" / "kaggle_piso" / "dados"
SAIDA = REPO_ROOT / "build" / "reduced_rounds" / "floor_v2" / "sei_dados.json"


def sei_bits(x: np.ndarray, passo: int = 500_000) -> tuple[float, float]:
    n = len(x)
    soma = np.zeros(x.shape[1] * 8)
    for i in range(0, n, passo):
        soma += np.unpackbits(x[i:i + passo], axis=1).sum(axis=0)
    p = soma / n
    termos = 4 * (p - 0.5) ** 2 - 1.0 / n          # sem viés, por bit
    return float(termos.sum()), math.sqrt(2 * len(p)) / n


def sei_bytes(x: np.ndarray) -> tuple[float, float]:
    n, L = x.shape
    total = 0.0
    for j in range(L):
        c = np.bincount(x[:, j], minlength=256) / n
        total += 256 * ((c - 1 / 256) ** 2).sum() - 255 / n
    return total, math.sqrt(2 * 255 * L) / n


def sei_pares_bytes(x: np.ndarray) -> tuple[float, float]:
    n, L = x.shape
    total = 0.0
    for j in range(L - 1):
        v = x[:, j].astype(np.int64) * 256 + x[:, j + 1]
        c = np.bincount(v, minlength=65536) / n
        total += 65536 * ((c - 1 / 65536) ** 2).sum() - 65535 / n
    return total, math.sqrt(2 * 65535 * (L - 1)) / n


def medir(x: np.ndarray) -> dict:
    out = {"n": int(len(x))}
    for nome, f in (("bits", sei_bits), ("bytes", sei_bytes), ("pares_bytes", sei_pares_bytes)):
        v, dp = f(x)
        out[nome] = v
        out[nome + "_dp"] = dp
    return out


def main() -> None:
    res = []
    for algo, piso in PISOS.items():
        for arm in ("texto", "aleatorio"):
            fontes = []
            zc = np.load(CURVA / f"{algo}_{arm}_dev31000.npz")
            for r in (piso, piso + 1):
                fontes.append((r, zc[f"r{r}"]))
            fontes.append(("uniforme", zc["random"]))
            zk = np.load(PACOTE / f"{algo}_{arm}_k3000.npz")
            for r in (1, SPEC[algo]):
                fontes.append((r, zk[f"r{r}"]))
            for r, x in fontes:
                m = medir(x)
                m.update(algo=algo, arm=arm, rodadas=r)
                res.append(m)
                print(f"{algo:9s} {arm:9s} r={str(r):9s} N={m['n']:>8d}  "
                      f"bits {m['bits']:.2e} (dp {m['bits_dp']:.1e})  "
                      f"bytes {m['bytes']:.2e} (dp {m['bytes_dp']:.1e})  "
                      f"pares {m['pares_bytes']:.2e} (dp {m['pares_bytes_dp']:.1e})", flush=True)
    SAIDA.write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(f"-> {SAIDA}")


if __name__ == "__main__":
    main()
