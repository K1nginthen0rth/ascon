"""Família 10: PSD de Welch em nível de bit + descritores espectrais (5 features).

Fonte: E13 (Zhou, 2025) — granularidade (bit, não byte) e método (Welch,
não FFT única) distintos da família `frequency` (FFT de byte) já existente.
Sequência convertida para ±1 (mesma convenção da suíte NIST — ver
`nist_sts.py`), PSD estimada por `scipy.signal.welch` (janelas sobrepostas,
mais estável que uma FFT única para sequências longas).
"""
from __future__ import annotations

import numpy as np
from scipy.signal import welch

_NAN = float("nan")
_KEYS = (
    "welch_spectral_centroid", "welch_spectral_bandwidth",
    "welch_spectral_flatness", "welch_spectral_rolloff85",
    "welch_psd_mean",
)


def extract_spectral_welch(ct: bytes) -> dict[str, float]:
    """PSD de Welch (nível de bit, ±1) e descritores espectrais derivados.

    Args:
        ct: ciphertext como bytes.

    Returns:
        welch_spectral_centroid: frequência média ponderada pela potência
            (normalizada, 0-0,5 — Nyquist).
        welch_spectral_bandwidth: desvio padrão espectral em torno do centróide.
        welch_spectral_flatness: razão média geométrica/aritmética da PSD
            (1,0 = espectro plano/ruído branco; próximo de 0 = tonal).
        welch_spectral_rolloff85: frequência abaixo da qual está 85% da energia.
        welch_psd_mean: potência média (nível geral do espectro).
        NaN se len(ct) < 16 bytes (128 bits — mínimo para segmentação do Welch).
    """
    if len(ct) < 16:
        return dict.fromkeys(_KEYS, _NAN)

    bits = np.unpackbits(np.frombuffer(ct, dtype=np.uint8)).astype(np.float64)
    signal = 2.0 * bits - 1.0  # 0/1 -> -1/+1

    nperseg = min(256, signal.size)
    freqs, psd = welch(signal, nperseg=nperseg)
    # Remove a componente DC (freq=0) do cálculo dos descritores.
    freqs = freqs[1:]
    psd = psd[1:]

    total = float(psd.sum())
    if total <= 0 or freqs.size == 0:
        return dict.fromkeys(_KEYS, _NAN)

    centroid = float(np.sum(freqs * psd) / total)
    bandwidth = float(np.sqrt(np.sum(((freqs - centroid) ** 2) * psd) / total))

    psd_positive = psd[psd > 0]
    geometric_mean = float(np.exp(np.mean(np.log(psd_positive)))) if psd_positive.size > 0 else 0.0
    arithmetic_mean = float(np.mean(psd))
    flatness = geometric_mean / arithmetic_mean if arithmetic_mean > 0 else _NAN

    cumulative = np.cumsum(psd) / total
    rolloff_idx = int(np.searchsorted(cumulative, 0.85))
    rolloff_idx = min(rolloff_idx, freqs.size - 1)
    rolloff85 = float(freqs[rolloff_idx])

    return {
        "welch_spectral_centroid": centroid,
        "welch_spectral_bandwidth": bandwidth,
        "welch_spectral_flatness": flatness,
        "welch_spectral_rolloff85": rolloff85,
        "welch_psd_mean": arithmetic_mean,
    }
