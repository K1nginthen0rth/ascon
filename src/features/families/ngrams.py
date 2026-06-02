"""Família 3: estatísticas de n-gramas de bytes (5 stats × 3 ordens = 15 features)."""
from __future__ import annotations

import numpy as np

_NAN = float("nan")
_DEFAULT_NS = (2, 3, 4)


def extract_ngrams(ct: bytes, ns: tuple[int, ...] = _DEFAULT_NS) -> dict[str, float]:
    """Estatísticas agregadas sobre distribuições de n-gramas de bytes.

    Não retorna histogramas completos (256^n bins seria inviável para n>=2).
    Em vez disso, extrai 5 estatísticas por ordem n:

    Args:
        ct: ciphertext como bytes.
        ns: ordens de n-gramas a calcular.

    Returns:
        ngram_{n}_entropy: entropia da distribuição de n-gramas observados.
        ngram_{n}_nunique: número de n-gramas distintos.
        ngram_{n}_max_freq: frequência relativa do n-grama mais comum.
        ngram_{n}_chi2: χ² sobre os bins observados (uniforme sobre k distintos).
        ngram_{n}_collision_rate: 1 - nunique / 256^n (saturação do espaço).
    """
    result: dict[str, float] = {}
    for n in ns:
        result.update(_ngram_stats(ct, n))
    return result


def _ngram_stats(ct: bytes, n: int) -> dict[str, float]:
    prefix = f"ngram_{n}_"
    nan_block = {
        prefix + "entropy": _NAN,
        prefix + "nunique": _NAN,
        prefix + "max_freq": _NAN,
        prefix + "chi2": _NAN,
        prefix + "collision_rate": _NAN,
    }

    if len(ct) < n:
        return nan_block

    total = len(ct) - n + 1
    vals, counts = _count_ngrams(ct, n)

    k = len(counts)
    freqs = counts / total
    nz = freqs[freqs > 0]
    entropy = float(-np.sum(nz * np.log2(nz))) if nz.size > 0 else 0.0

    nunique = float(k)
    max_freq = float(counts.max()) / total

    expected_per = total / k if k > 1 else total
    chi2 = float(np.sum((counts - expected_per) ** 2 / expected_per)) if k > 1 else 0.0

    max_possible = 256 ** n
    collision_rate = 1.0 - k / max_possible

    return {
        prefix + "entropy": entropy,
        prefix + "nunique": nunique,
        prefix + "max_freq": max_freq,
        prefix + "chi2": chi2,
        prefix + "collision_rate": collision_rate,
    }


def _count_ngrams(ct: bytes, n: int) -> tuple[np.ndarray, np.ndarray]:
    """Pack n-grams into integers and count with numpy unique."""
    arr = np.frombuffer(ct, dtype=np.uint8)
    packed = np.zeros(len(arr) - n + 1, dtype=np.int64)
    for i in range(n):
        packed = packed * 256 + arr[i : len(arr) - n + 1 + i].astype(np.int64)
    return np.unique(packed, return_counts=True)
