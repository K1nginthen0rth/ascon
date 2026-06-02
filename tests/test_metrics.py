"""Testes para src/eval/metrics.py."""
from __future__ import annotations

import numpy as np
import pytest

from src.eval.metrics import (
    compute_metrics,
    expected_calibration_error,
    mcnemar_test,
)


def test_bootstrap_ci_contains_point_estimate() -> None:
    """O IC bootstrap deve conter o valor pontual de F1 e balanced accuracy."""
    rng = np.random.default_rng(0)
    y_true = rng.integers(0, 2, 200)
    y_pred = y_true.copy()
    # Introduz alguns erros para evitar IC degenerado [1, 1]
    flip   = rng.choice(200, size=20, replace=False)
    y_pred[flip] = 1 - y_pred[flip]

    rep = compute_metrics(y_true, y_pred, n_bootstrap=300, seed=42)
    f1_lo, f1_hi   = rep.f1_macro_ci
    bal_lo, bal_hi = rep.balanced_accuracy_ci

    assert f1_lo  <= rep.f1_macro          <= f1_hi
    assert bal_lo <= rep.balanced_accuracy <= bal_hi
    assert 0.0 <= rep.f1_macro          <= 1.0
    assert 0.0 <= rep.balanced_accuracy <= 1.0


def test_perfect_predictions_f1_one() -> None:
    """Predições perfeitas → F1 = 1, balanced_acc = 1."""
    y = np.array([0, 1, 0, 1, 0, 1, 0, 1])
    rep = compute_metrics(y, y, n_bootstrap=100)
    assert rep.f1_macro == pytest.approx(1.0)
    assert rep.balanced_accuracy == pytest.approx(1.0)


def test_random_predictions_balanced_chance() -> None:
    """Predições aleatórias em 2 classes balanceadas: F1-macro próximo de 0.5."""
    rng = np.random.default_rng(7)
    n = 2000
    y_true = rng.integers(0, 2, n)
    y_pred = rng.integers(0, 2, n)
    rep = compute_metrics(y_true, y_pred, n_bootstrap=300, seed=7)
    # Em 2k amostras, esperamos F1 ~0.5 com tolerância larga
    assert 0.40 < rep.f1_macro < 0.60
    # IC deve cobrir o valor de chance (0.5)
    assert rep.f1_macro_ci[0] < 0.5 < rep.f1_macro_ci[1]


def test_mcnemar_identical_predictions() -> None:
    """Modelos idênticos → discordância 0 → p_value = 1."""
    y_true = np.array([0, 1, 0, 1, 0, 1])
    y_pred = np.array([0, 1, 0, 1, 1, 0])
    res = mcnemar_test(y_true, y_pred, y_pred)
    assert res["n10"] == 0
    assert res["n01"] == 0
    assert res["p_value"] == 1.0
    assert res["significant"] is False


def test_mcnemar_one_clearly_better() -> None:
    """Um modelo claramente melhor → p_value baixo, significant True."""
    rng = np.random.default_rng(0)
    n = 500
    y_true = rng.integers(0, 2, n)

    # Modelo A: 90% de acerto
    y_pred_a = y_true.copy()
    flip_a = rng.choice(n, size=int(n * 0.1), replace=False)
    y_pred_a[flip_a] = 1 - y_pred_a[flip_a]

    # Modelo B: 60% de acerto
    y_pred_b = y_true.copy()
    flip_b = rng.choice(n, size=int(n * 0.4), replace=False)
    y_pred_b[flip_b] = 1 - y_pred_b[flip_b]

    res = mcnemar_test(y_true, y_pred_a, y_pred_b)
    assert res["p_value"] < 0.01
    assert res["significant"] is True


def test_mcnemar_table_sums_to_n() -> None:
    """n11 + n10 + n01 + n00 = n_samples."""
    rng = np.random.default_rng(3)
    n = 200
    y_true = rng.integers(0, 2, n)
    y_a    = rng.integers(0, 2, n)
    y_b    = rng.integers(0, 2, n)
    res = mcnemar_test(y_true, y_a, y_b)
    assert res["n11"] + res["n10"] + res["n01"] + res["n00"] == n


def test_ece_perfect_calibration() -> None:
    """Probas one-hot perfeitamente calibradas → ECE ~0."""
    n = 100
    y = np.array([0, 1] * (n // 2))
    proba = np.zeros((n, 2))
    proba[np.arange(n), y] = 1.0
    ece = expected_calibration_error(y, proba, n_bins=10)
    assert ece == pytest.approx(0.0, abs=1e-6)


def test_ece_miscalibrated() -> None:
    """Modelo overconfident e errado → ECE alto."""
    n = 100
    y = np.zeros(n, dtype=int)
    proba = np.tile([0.05, 0.95], (n, 1))  # diz classe 1 com 95% confianca, mas y=0
    ece = expected_calibration_error(y, proba, n_bins=10)
    assert ece > 0.8


def test_compute_metrics_returns_dict() -> None:
    """as_dict() deve produzir um dict serializável."""
    rng = np.random.default_rng(1)
    y_true = rng.integers(0, 2, 100)
    y_pred = rng.integers(0, 2, 100)
    rep = compute_metrics(y_true, y_pred, n_bootstrap=50)
    d = rep.as_dict()
    assert isinstance(d, dict)
    assert "f1_macro" in d
    assert "confusion_matrix" in d
    assert isinstance(d["confusion_matrix"], list)
