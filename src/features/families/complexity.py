"""Família 5: métricas de complexidade — LZ76 + compressão (4 features)."""
from __future__ import annotations

import bz2
import zlib

_NAN = float("nan")


def extract_complexity(ct: bytes) -> dict[str, float]:
    """Complexidade de Lempel-Ziv (LZ76) e razões de compressão zlib/bz2.

    Args:
        ct: ciphertext como bytes.

    Returns:
        lz_complexity: número de frases na decomposição LZ76.
        lz_complexity_normalized: lz_complexity / len(ct).
        compression_ratio_zlib: len(zlib.compress(ct)) / len(ct).
        compression_ratio_bz2: len(bz2.compress(ct)) / len(ct).
        Todos NaN se ct estiver vazio.
    """
    if len(ct) == 0:
        return {
            "lz_complexity": _NAN,
            "lz_complexity_normalized": _NAN,
            "compression_ratio_zlib": _NAN,
            "compression_ratio_bz2": _NAN,
        }

    lz = _lz76(ct)
    return {
        "lz_complexity": float(lz),
        "lz_complexity_normalized": float(lz) / len(ct),
        "compression_ratio_zlib": len(zlib.compress(ct, level=9)) / len(ct),
        "compression_ratio_bz2": len(bz2.compress(ct, compresslevel=9)) / len(ct),
    }


def _lz76(seq: bytes) -> int:
    """Complexidade LZ76: número de frases na decomposição greedy.

    Cada frase é a substring mais curta a partir da posição atual que não
    ocorre como substring do prefixo já processado.
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
