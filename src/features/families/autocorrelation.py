"""Família 4: autocorrelação de bytes + teste de runs (18 features)."""
from __future__ import annotations

import math

import numpy as np

_NAN = float("nan")


def extract_autocorrelation(ct: bytes, max_lag: int = 16) -> dict[str, float]:
    """Autocorrelação normalizada nos lags 1–max_lag + teste de runs Wald-Wolfowitz.

    Args:
        ct: ciphertext como bytes.
        max_lag: número máximo de lags a calcular.

    Returns:
        autocorr_lag_01 ... autocorr_lag_16: coeficientes de autocorrelação em [-1, 1].
        runs_count: número de runs observados.
        runs_zscore: z-score do teste de runs (H₀: sequência aleatória).
        NaN quando o CT é curto demais para o lag/teste.
    """
    result: dict[str, float] = {}
    for lag in range(1, max_lag + 1):
        result[f"autocorr_lag_{lag:02d}"] = _NAN
    result["runs_count"] = _NAN
    result["runs_zscore"] = _NAN

    n = len(ct)
    if n < 2:
        return result

    arr = np.frombuffer(ct, dtype=np.uint8).astype(float)
    mean = arr.mean()
    var = float(np.var(arr))

    if var < 1e-12:
        for lag in range(1, min(max_lag, n - 1) + 1):
            result[f"autocorr_lag_{lag:02d}"] = 1.0
        result["runs_count"] = 1.0
        return result

    x = arr - mean
    for lag in range(1, min(max_lag, n - 1) + 1):
        acf = float(np.mean(x[:-lag] * x[lag:])) / var
        result[f"autocorr_lag_{lag:02d}"] = float(np.clip(acf, -1.0, 1.0))

    median = np.median(arr)
    binary = (arr > median).astype(int)

    runs = 1 + int(np.sum(binary[1:] != binary[:-1]))
    n1 = int(binary.sum())
    n2 = n - n1

    result["runs_count"] = float(runs)

    if n1 > 0 and n2 > 0 and n > 1:
        expected = 2.0 * n1 * n2 / n + 1.0
        denom = 2.0 * n1 * n2 * (2.0 * n1 * n2 - n) / (n * n * (n - 1))
        if denom > 0:
            result["runs_zscore"] = float((runs - expected) / math.sqrt(denom))

    return result
