"""Família 9: distribuição de peso de Hamming por byte (11 features).

Fonte: E07 (Zhao et al., 2023) — representação que define a réplica XGB-LGBM
(ver docs/plano_experimento_v2/03_classificadores.md §3.1). Peso de Hamming
de um byte = número de bits 1 (0-8). Reporta a distribuição normalizada
(9 bins) + média + variância — derivável do histograma de bytes por soma
linear, mas mantido como família própria para a réplica poder consumi-la
isoladamente (fidelidade ao desenho original do estudo).
"""
from __future__ import annotations

import numpy as np

_NAN = float("nan")

# popcount de 0..255, pré-computado uma vez no import do módulo.
_POPCOUNT = np.array([bin(i).count("1") for i in range(256)], dtype=np.uint8)


def extract_hamming(ct: bytes) -> dict[str, float]:
    """Distribuição do peso de Hamming (0-8 bits setados) por byte do CT.

    Args:
        ct: ciphertext como bytes.

    Returns:
        hamming_weight_0 ... hamming_weight_8: proporção de bytes com esse
            peso de Hamming (soma = 1).
        hamming_weight_mean: peso de Hamming médio por byte (esperado 4,0
            para bytes uniformes).
        hamming_weight_var: variância do peso de Hamming por byte.
        Todos NaN se ct estiver vazio.
    """
    keys = [f"hamming_weight_{k}" for k in range(9)] + [
        "hamming_weight_mean", "hamming_weight_var",
    ]
    if len(ct) == 0:
        return dict.fromkeys(keys, _NAN)

    arr = np.frombuffer(ct, dtype=np.uint8)
    weights = _POPCOUNT[arr]
    counts = np.bincount(weights, minlength=9).astype(float)
    proportions = counts / len(ct)

    result = {f"hamming_weight_{k}": float(proportions[k]) for k in range(9)}
    result["hamming_weight_mean"] = float(np.mean(weights))
    result["hamming_weight_var"] = float(np.var(weights))
    return result
