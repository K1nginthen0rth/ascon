"""Família 1: histograma normalizado de bytes (256 features)."""
from __future__ import annotations

import numpy as np


def extract_histogram(ct: bytes) -> dict[str, float]:
    """Frequência relativa de cada valor de byte (0–255).

    Args:
        ct: ciphertext como bytes.

    Returns:
        byte_hist_000 ... byte_hist_255 — valor em [0, 1].
        Todos zeros se ct estiver vazio.
    """
    if len(ct) == 0:
        return {f"byte_hist_{i:03d}": 0.0 for i in range(256)}

    arr = np.frombuffer(ct, dtype=np.uint8)
    counts = np.bincount(arr, minlength=256).astype(float)
    hist = counts / len(ct)
    return {f"byte_hist_{i:03d}": float(hist[i]) for i in range(256)}
