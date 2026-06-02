"""Família 2: entropia de Shannon + teste chi-quadrado (4 features)."""
from __future__ import annotations

import math

import numpy as np
from scipy.stats import chisquare

_NAN = float("nan")


def extract_entropy_stats(ct: bytes) -> dict[str, float]:
    """Entropia de Shannon e estatística chi² contra distribuição uniforme.

    Args:
        ct: ciphertext como bytes.

    Returns:
        shannon_entropy: entropia em bits (0–8).
        chi2_statistic: valor da estatística χ² contra uniforme de 256 bins.
        chi2_pvalue: p-value do teste (NaN se len(ct) < 16).
        chi2_dof: graus de liberdade — sempre 255 quando calculado.
    """
    if len(ct) == 0:
        return {
            "shannon_entropy": 0.0,
            "chi2_statistic": _NAN,
            "chi2_pvalue": _NAN,
            "chi2_dof": _NAN,
        }

    arr = np.frombuffer(ct, dtype=np.uint8)
    counts = np.bincount(arr, minlength=256).astype(float)

    probs = counts / len(ct)
    nz = probs[probs > 0]
    shannon = float(-np.sum(nz * np.log2(nz)))

    if len(ct) >= 16:
        expected = np.full(256, len(ct) / 256.0)
        stat, pvalue = chisquare(counts, f_exp=expected)
        return {
            "shannon_entropy": shannon,
            "chi2_statistic": float(stat),
            "chi2_pvalue": float(pvalue),
            "chi2_dof": 255.0,
        }

    return {
        "shannon_entropy": shannon,
        "chi2_statistic": _NAN,
        "chi2_pvalue": _NAN,
        "chi2_dof": _NAN,
    }
