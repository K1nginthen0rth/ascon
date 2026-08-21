"""Família 11: histograma de blocos de bits em tamanho variável.

Fonte: E01 (de Mello & Xexéo, 2016 — blocos 2-34 bits) e E03 (Barbosa et
al., 2017 — blocos 4-16 bits) — ver docs/plano_experimento_v2/02_features_e_selecao.md.

Blocos pequenos (2, 4, 8 bits): histograma bruto normalizado (4 + 16 + 256 =
276 features). Blocos maiores (12, 16 bits): inviável reportar 2^12/2^16
colunas — reportado como estatísticas agregadas (entropia, nunique
normalizado, max_freq), mesmo padrão já usado pelos n-gramas.
"""
from __future__ import annotations

import numpy as np

_NAN = float("nan")
_RAW_BLOCK_SIZES = (2, 4, 8)
_AGG_BLOCK_SIZES = (12, 16)


def _bits_to_block_values(bits: np.ndarray, block_size: int) -> np.ndarray:
    """Agrupa um array de bits (0/1) em blocos de `block_size`, retorna os
    valores inteiros de cada bloco completo (blocos parciais no final são
    descartados)."""
    n_blocks = bits.size // block_size
    trimmed = bits[: n_blocks * block_size].reshape(n_blocks, block_size)
    weights = (1 << np.arange(block_size - 1, -1, -1)).astype(np.uint32)
    return trimmed.astype(np.uint32) @ weights


def extract_bitblock(ct: bytes) -> dict[str, float]:
    """Histograma de blocos de bits (brutos p/ 2-8 bits; agregados p/ 12-16).

    Args:
        ct: ciphertext como bytes.

    Returns:
        bitblock_{k}_{i}: proporção do valor i no histograma de blocos de
            k bits, para k em {2, 4, 8}.
        bitblock_{k}_entropy / _nunique_ratio / _max_freq: estatísticas
            agregadas para k em {12, 16}.
        NaN (ou 0.0 nos bins do histograma) se não houver blocos completos
        suficientes para aquele tamanho.
    """
    result: dict[str, float] = {}
    keys_raw = [
        f"bitblock_{k}_{i}" for k in _RAW_BLOCK_SIZES for i in range(2 ** k)
    ]
    keys_agg = [
        f"bitblock_{k}_{suffix}"
        for k in _AGG_BLOCK_SIZES
        for suffix in ("entropy", "nunique_ratio", "max_freq")
    ]
    for k in keys_raw + keys_agg:
        result[k] = _NAN

    if len(ct) == 0:
        return result

    bits = np.unpackbits(np.frombuffer(ct, dtype=np.uint8))

    for block_size in _RAW_BLOCK_SIZES:
        if bits.size < block_size:
            continue
        values = _bits_to_block_values(bits, block_size)
        counts = np.bincount(values, minlength=2 ** block_size).astype(float)
        proportions = counts / values.size
        for i in range(2 ** block_size):
            result[f"bitblock_{block_size}_{i}"] = float(proportions[i])

    for block_size in _AGG_BLOCK_SIZES:
        if bits.size < block_size:
            continue
        values = _bits_to_block_values(bits, block_size)
        n_total = values.size
        if n_total == 0:
            continue
        counts = np.bincount(values, minlength=2 ** block_size).astype(float)
        probs = counts / n_total
        nz = probs[probs > 0]
        entropy = float(-np.sum(nz * np.log2(nz))) if nz.size > 0 else 0.0
        nunique = float(np.count_nonzero(counts)) / min(n_total, 2 ** block_size)
        max_freq = float(probs.max())
        result[f"bitblock_{block_size}_entropy"] = entropy
        result[f"bitblock_{block_size}_nunique_ratio"] = nunique
        result[f"bitblock_{block_size}_max_freq"] = max_freq

    return result
