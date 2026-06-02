"""Testes para src/features/ — famílias individuais e orquestrador."""
from __future__ import annotations

import math
import os
import time
from pathlib import Path

import numpy as np
import pytest

from src.features.families.autocorrelation import extract_autocorrelation
from src.features.families.complexity import extract_complexity, _lz76
from src.features.families.entropy import extract_entropy_stats
from src.features.families.frequency import extract_frequency
from src.features.families.histogram import extract_histogram
from src.features.families.ngrams import extract_ngrams
from src.features.extractor import CiphertextFeatureExtractor

_PILOT = Path("data/processed/ascon_aead128_pilot_v2.parquet")
_RNG = np.random.default_rng(0)

# ---------------------------------------------------------------------------
# Utilitários
# ---------------------------------------------------------------------------

def rand_bytes(n: int) -> bytes:
    return bytes(_RNG.integers(0, 256, n, dtype=np.uint8))


def all_nan_or_float(d: dict) -> bool:
    for v in d.values():
        if not (isinstance(v, float) or isinstance(v, int)):
            return False
    return True


# ---------------------------------------------------------------------------
# Família 1 — histograma
# ---------------------------------------------------------------------------

def test_histogram_sums_to_one():
    ct = rand_bytes(1000)
    h = extract_histogram(ct)
    assert abs(sum(h.values()) - 1.0) < 1e-9


def test_histogram_empty_ct():
    h = extract_histogram(b"")
    assert len(h) == 256
    assert all(v == 0.0 for v in h.values())


def test_histogram_single_byte():
    ct = bytes([42]) * 500
    h = extract_histogram(ct)
    assert abs(h["byte_hist_042"] - 1.0) < 1e-9
    others = [v for k, v in h.items() if k != "byte_hist_042"]
    assert all(v == 0.0 for v in others)


def test_histogram_key_format():
    h = extract_histogram(rand_bytes(32))
    assert "byte_hist_000" in h
    assert "byte_hist_255" in h
    assert len(h) == 256


# ---------------------------------------------------------------------------
# Família 2 — entropia
# ---------------------------------------------------------------------------

def test_entropy_bounds():
    for n in [1, 16, 256, 1024]:
        ct = rand_bytes(n)
        s = extract_entropy_stats(ct)
        assert 0.0 <= s["shannon_entropy"] <= 8.0 + 1e-9


def test_entropy_uniform_near_8():
    ct = os.urandom(10000)
    s = extract_entropy_stats(ct)
    assert s["shannon_entropy"] > 7.9


def test_entropy_constant_is_zero():
    ct = bytes([0x00]) * 1000
    s = extract_entropy_stats(ct)
    assert abs(s["shannon_entropy"]) < 1e-9


def test_entropy_chi2_nan_for_short_ct():
    ct = rand_bytes(8)
    s = extract_entropy_stats(ct)
    assert math.isnan(s["chi2_statistic"])
    assert math.isnan(s["chi2_pvalue"])


def test_entropy_chi2_present_for_long_ct():
    ct = rand_bytes(256)
    s = extract_entropy_stats(ct)
    assert not math.isnan(s["chi2_statistic"])
    assert 0.0 <= s["chi2_pvalue"] <= 1.0
    assert s["chi2_dof"] == 255.0


# ---------------------------------------------------------------------------
# Família 3 — n-gramas
# ---------------------------------------------------------------------------

def test_ngram_stats_keys():
    ct = rand_bytes(128)
    ng = extract_ngrams(ct)
    for n in [2, 3, 4]:
        for stat in ["entropy", "nunique", "max_freq", "chi2", "collision_rate"]:
            assert f"ngram_{n}_{stat}" in ng


def test_ngram_total_features():
    ng = extract_ngrams(rand_bytes(128))
    assert len(ng) == 15


def test_ngram_entropy_positive():
    ct = rand_bytes(1000)
    ng = extract_ngrams(ct)
    for n in [2, 3, 4]:
        assert ng[f"ngram_{n}_entropy"] > 0


def test_ngram_nan_for_short_ct():
    ct = b"\x00"  # len=1 < 2 (min n)
    ng = extract_ngrams(ct)
    for n in [2, 3, 4]:
        assert math.isnan(ng[f"ngram_{n}_entropy"])


def test_ngram_collision_rate_near_one_for_n4():
    ct = rand_bytes(256)
    ng = extract_ngrams(ct)
    assert ng["ngram_4_collision_rate"] > 0.999


# ---------------------------------------------------------------------------
# Família 4 — autocorrelação + runs
# ---------------------------------------------------------------------------

def test_autocorrelation_keys():
    ac = extract_autocorrelation(rand_bytes(64))
    for lag in range(1, 17):
        assert f"autocorr_lag_{lag:02d}" in ac
    assert "runs_count" in ac
    assert "runs_zscore" in ac


def test_autocorrelation_random_near_zero():
    ct = rand_bytes(4096)
    ac = extract_autocorrelation(ct)
    for lag in range(1, 17):
        assert abs(ac[f"autocorr_lag_{lag:02d}"]) < 0.1


def test_autocorrelation_lag0_implicit_is_one():
    ct = rand_bytes(100)
    arr = np.frombuffer(ct, dtype=np.uint8).astype(float)
    var = float(np.var(arr))
    lag1 = extract_autocorrelation(ct)["autocorr_lag_01"]
    assert abs(lag1) <= 1.0 + 1e-9


def test_autocorrelation_short_ct_nan():
    ct = b"\x01"  # len=1 < 2
    ac = extract_autocorrelation(ct)
    assert math.isnan(ac["autocorr_lag_01"])
    assert math.isnan(ac["runs_zscore"])


def test_runs_count_positive():
    ct = rand_bytes(200)
    ac = extract_autocorrelation(ct)
    assert ac["runs_count"] >= 1.0


# ---------------------------------------------------------------------------
# Família 5 — complexidade
# ---------------------------------------------------------------------------

def test_complexity_keys():
    c = extract_complexity(rand_bytes(64))
    assert set(c) == {
        "lz_complexity",
        "lz_complexity_normalized",
        "compression_ratio_zlib",
        "compression_ratio_bz2",
    }


def test_complexity_random_high():
    ct = rand_bytes(1000)
    c = extract_complexity(ct)
    assert c["lz_complexity_normalized"] > 0.02


def test_complexity_constant_low():
    ct = bytes([0xAB]) * 1000
    c = extract_complexity(ct)
    assert c["lz_complexity"] <= 5


def test_complexity_empty_nan():
    c = extract_complexity(b"")
    assert all(math.isnan(v) for v in c.values())


def test_compression_ratio_random_near_one():
    ct = rand_bytes(1000)
    c = extract_complexity(ct)
    assert c["compression_ratio_zlib"] > 0.9
    assert c["compression_ratio_bz2"] > 0.9


def test_lz76_correctness():
    assert _lz76(b"") == 0
    assert _lz76(b"\x00") == 1
    assert _lz76(bytes([0] * 100)) == 2
    constant_complex = _lz76(bytes([0xAB] * 100))
    random_complex = _lz76(rand_bytes(100))
    assert random_complex > constant_complex


# ---------------------------------------------------------------------------
# Família 6 — frequência (FFT)
# ---------------------------------------------------------------------------

def test_fft_bands_sum_to_one():
    ct = rand_bytes(256)
    f = extract_frequency(ct)
    band_sum = sum(f[f"fft_band_{i}"] for i in range(8))
    assert abs(band_sum - 1.0) < 1e-6


def test_fft_nan_for_short_ct():
    ct = rand_bytes(4)
    f = extract_frequency(ct)
    assert math.isnan(f["fft_band_0"])
    assert math.isnan(f["fft_spectral_entropy"])


def test_fft_peak_freq_in_range():
    ct = rand_bytes(512)
    f = extract_frequency(ct)
    assert 0.0 <= f["fft_peak_freq"] <= 1.0


def test_fft_spectral_entropy_positive():
    ct = rand_bytes(512)
    f = extract_frequency(ct)
    assert f["fft_spectral_entropy"] > 0.0


# ---------------------------------------------------------------------------
# Orquestrador
# ---------------------------------------------------------------------------

def test_extract_all_families():
    extractor = CiphertextFeatureExtractor()
    ct = rand_bytes(256)
    feats = extractor.extract(ct)
    # Esperado: 256 + 4 + 15 + 18 + 4 + 10 = 307
    assert len(feats) == 307
    assert all_nan_or_float(feats)


def test_extract_empty_ct():
    extractor = CiphertextFeatureExtractor()
    feats = extractor.extract(b"")
    for name, val in feats.items():
        assert isinstance(val, float), f"{name} nao e float"


def test_extract_short_ct():
    extractor = CiphertextFeatureExtractor()
    ct = b"\xff"
    feats = extractor.extract(ct)
    assert abs(feats["byte_hist_255"] - 1.0) < 1e-9
    assert math.isnan(feats["chi2_statistic"])
    assert math.isnan(feats["ngram_2_entropy"])


def test_extract_subset_families():
    extractor = CiphertextFeatureExtractor(families=["histogram", "entropy"])
    feats = extractor.extract(rand_bytes(64))
    assert len(feats) == 256 + 4


def test_unknown_family_raises():
    with pytest.raises(ValueError):
        CiphertextFeatureExtractor(families=["unknown"])


def test_no_inf_in_output():
    extractor = CiphertextFeatureExtractor()
    for _ in range(50):
        ct = rand_bytes(int(_RNG.integers(16, 512)))
        feats = extractor.extract(ct)
        for name, val in feats.items():
            assert not math.isinf(val), f"Inf em {name}"


@pytest.mark.skipif(not _PILOT.exists(), reason="dataset piloto nao encontrado")
def test_extract_dataset_pilot(tmp_path):
    extractor = CiphertextFeatureExtractor()
    import pandas as pd
    df_pilot = pd.read_parquet(_PILOT).head(100)
    tmp_pq = str(tmp_path / "pilot_head100.parquet")
    df_pilot.to_parquet(tmp_pq, index=False)
    out = extractor.extract_dataset(
        tmp_pq,
        show_progress=False,
        n_jobs=1,
    )
    assert len(out) == 100
    assert "ciphertext" not in out.columns
    assert "sample_id" in out.columns
    feature_cols = [c for c in out.columns if c not in ("sample_id", "algorithm", "key_id", "len_pt", "len_ct")]
    assert len(feature_cols) == 307
    assert not out[feature_cols].isin([float("inf"), float("-inf")]).any().any()


@pytest.mark.skipif(not _PILOT.exists(), reason="dataset piloto nao encontrado")
def test_no_ciphertext_in_output(tmp_path):
    extractor = CiphertextFeatureExtractor()
    import pandas as pd
    df_pilot = pd.read_parquet(_PILOT).head(10)
    tmp_pq = str(tmp_path / "pilot_head10.parquet")
    df_pilot.to_parquet(tmp_pq, index=False)
    out = extractor.extract_dataset(
        tmp_pq,
        show_progress=False,
        n_jobs=1,
    )
    assert "ciphertext" not in out.columns


def test_benchmark_single_extraction():
    extractor = CiphertextFeatureExtractor()
    ct = rand_bytes(1024)
    # Warm-up
    extractor.extract(ct)

    times = []
    for _ in range(10):
        t0 = time.perf_counter()
        extractor.extract(ct)
        times.append(time.perf_counter() - t0)

    median_ms = sorted(times)[5] * 1000
    assert median_ms < 10.0, f"Extracao de 1024B levou {median_ms:.2f}ms (limite: 10ms)"
