"""Família 5: métricas de complexidade — LZ76 + compressão (5 features)."""
from __future__ import annotations

import bz2
import lzma
import zlib

_NAN = float("nan")


def extract_complexity(ct: bytes) -> dict[str, float]:
    """Complexidade de Lempel-Ziv (LZ76) e razões de compressão zlib/bz2/lzma.

    Args:
        ct: ciphertext como bytes.

    Returns:
        lz_complexity: número de frases na decomposição LZ76.
        lz_complexity_normalized: lz_complexity / len(ct).
        compression_ratio_zlib: len(zlib.compress(ct)) / len(ct).
        compression_ratio_bz2: len(bz2.compress(ct)) / len(ct).
        compression_ratio_lzma: len(lzma.compress(ct)) / len(ct) (E13 — Zhou, 2025).
        Todos NaN se ct estiver vazio.
    """
    if len(ct) == 0:
        return {
            "lz_complexity": _NAN,
            "lz_complexity_normalized": _NAN,
            "compression_ratio_zlib": _NAN,
            "compression_ratio_bz2": _NAN,
            "compression_ratio_lzma": _NAN,
        }

    lz = _lz76(ct)
    return {
        "lz_complexity": float(lz),
        "lz_complexity_normalized": float(lz) / len(ct),
        "compression_ratio_zlib": len(zlib.compress(ct, level=9)) / len(ct),
        "compression_ratio_bz2": len(bz2.compress(ct, compresslevel=9)) / len(ct),
        "compression_ratio_lzma": len(lzma.compress(ct)) / len(ct),
    }


def _lz76(seq: bytes) -> int:
    """Complexidade LZ76: número de frases na decomposição greedy.

    Cada frase é a substring mais curta a partir da posição atual que não
    ocorre como substring do prefixo já processado.

    **Nota de performance (medida em 2026-08-22, não especular):** esta é
    a função mais cara da família (~0,56s por amostra de 64KB). Foi
    testada uma reimplementação com `@numba.njit` pelo algoritmo clássico
    de Kaspar & Schuster — validada EQUIVALENTE (0 divergências em 200
    sequências aleatórias) mas **mais LENTA** (0,64s vs 0,56s), porque o
    operador `in` sobre `bytes` usa `memmem` em C (vetorizado) enquanto o
    numba faz comparação byte-a-byte. Mantida a versão original. Uma
    aceleração real exigiria o algoritmo O(n) com autômato de sufixos
    (LPF), cuja complexidade de implementação não se justifica no
    orçamento atual — ver `reports/v2/benchmark_extracao.md`.
    """
    n = len(seq)
    if n == 0:
        return 0
    phrases = 0
    start = 0
    while start < n:
        end = start + 1
        while end < n and seq[start:end] in seq[: end - 1]:
            end += 1
        phrases += 1
        start = end
    return phrases
