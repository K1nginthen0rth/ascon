"""Família 6: análise espectral via FFT (10 features)."""
from __future__ import annotations

import numpy as np

_NAN = float("nan")


def extract_frequency(ct: bytes, n_bands: int = 8) -> dict[str, float]:
    """Distribuição de energia espectral via FFT de bytes.

    Converte o ciphertext em série temporal (valores 0–255) e calcula a
    transformada de Fourier. O espectro de potência é dividido em n_bands
    bandas de frequência uniformes (sem incluir a componente DC).

    Args:
        ct: ciphertext como bytes.
        n_bands: número de bandas espectrais.

    Returns:
        fft_band_0 ... fft_band_{n_bands-1}: energia relativa por banda (soma ≈ 1).
        fft_peak_freq: posição normalizada do pico dominante (0–1).
        fft_spectral_entropy: entropia de Shannon do espectro de bandas.
        NaN se len(ct) < 8.
    """
    result: dict[str, float] = {}
    for i in range(n_bands):
        result[f"fft_band_{i}"] = _NAN
    result["fft_peak_freq"] = _NAN
    result["fft_spectral_entropy"] = _NAN

    if len(ct) < 8:
        return result

    arr = np.frombuffer(ct, dtype=np.uint8).astype(float)
    power = np.abs(np.fft.rfft(arr)) ** 2
    spectrum = power[1:]  # Remove componente DC

    total = float(spectrum.sum())
    if total < 1e-12:
        return result

    n_freq = len(spectrum)
    band_energies = np.array(
        [spectrum[i * n_freq // n_bands : (i + 1) * n_freq // n_bands].sum()
         for i in range(n_bands)],
        dtype=float,
    )
    band_energies /= total

    for i in range(n_bands):
        result[f"fft_band_{i}"] = float(band_energies[i])

    result["fft_peak_freq"] = float(int(np.argmax(spectrum)) / n_freq)

    nz = band_energies[band_energies > 0]
    result["fft_spectral_entropy"] = float(-np.sum(nz * np.log2(nz))) if nz.size > 0 else 0.0

    return result
