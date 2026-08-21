"""Família 8: momentos de ordem superior da distribuição de bytes (2 features).

Fonte: E13 (Zhou, 2025) — skewness e kurtosis como descritores complementares
à entropia/histograma já existentes (ver docs/plano_experimento_v2/02_features_e_selecao.md).
"""
from __future__ import annotations

from scipy.stats import kurtosis, skew

_NAN = float("nan")


def extract_moments(ct: bytes) -> dict[str, float]:
    """Skewness e kurtosis (Fisher, excess) da distribuição de bytes do CT.

    Args:
        ct: ciphertext como bytes.

    Returns:
        byte_skewness: assimetria da distribuição de bytes (0 = simétrica).
        byte_kurtosis: curtose em excesso (0 = mesocúrtica/normal).
        NaN se len(ct) < 2 (momentos indefinidos).
    """
    if len(ct) < 2:
        return {"byte_skewness": _NAN, "byte_kurtosis": _NAN}

    arr = list(ct)
    return {
        "byte_skewness": float(skew(arr)),
        "byte_kurtosis": float(kurtosis(arr, fisher=True)),
    }
