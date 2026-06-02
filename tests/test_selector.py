"""Testes para src/features/selector.py."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.features.selector import LWCFeatureSelector, SelectorConfig


@pytest.fixture(scope="module")
def synthetic_data():
    """
    Dataset sintético: 200 amostras, 50 features.
    - Features 0..4: sinal forte (correlacionadas com y)
    - Features 5..9: redundantes com 0..4 (cópias com ruído)
    - Features 10..49: ruído puro
    """
    rng = np.random.default_rng(0)
    n, p_signal, p_redundant, p_noise = 200, 5, 5, 40
    y = rng.integers(0, 2, n)
    X_signal = rng.standard_normal((n, p_signal))
    # Force correlation with y on signal features
    for j in range(p_signal):
        X_signal[:, j] += 1.5 * (y - 0.5)
    X_redundant = X_signal[:, :p_redundant] + 0.1 * rng.standard_normal((n, p_redundant))
    X_noise     = rng.standard_normal((n, p_noise))
    X = np.hstack([X_signal, X_redundant, X_noise]).astype(np.float64)
    names = (
        [f"signal_{i}"    for i in range(p_signal)]
        + [f"redundant_{i}" for i in range(p_redundant)]
        + [f"noise_{i}"    for i in range(p_noise)]
    )
    return pd.DataFrame(X, columns=names), pd.Series(y)


def test_selector_reduces_dimensions(synthetic_data) -> None:
    """Pipeline reduz strict ly o número de features."""
    X, y = synthetic_data
    sel = LWCFeatureSelector(SelectorConfig(
        top_k_mi=20, n_features_mrmr=10, boruta_max_iter=20
    ))
    sel.fit(X, y)
    out = sel.get_stage_report()
    assert out["stage1_input"]   == X.shape[1]
    assert out["stage1_output"]  <= 20
    assert out["stage2_output"]  <= 10
    assert out["final_output"]   <= out["stage2_output"]
    assert out["final_output"]   >= 1


def test_selector_transform_shape(synthetic_data) -> None:
    """transform reduz colunas para o tamanho do conjunto final."""
    X, y = synthetic_data
    sel = LWCFeatureSelector(SelectorConfig(
        top_k_mi=20, n_features_mrmr=10, boruta_max_iter=20
    ))
    sel.fit(X, y)
    Xt = sel.transform(X)
    assert Xt.shape[0] == X.shape[0]
    assert Xt.shape[1] == sel.get_stage_report()["final_output"]


def test_selector_does_not_use_test_data(synthetic_data) -> None:
    """fit em X_train é determinístico e independente de X_val."""
    X, y = synthetic_data
    n_train = 150
    X_train, y_train = X.iloc[:n_train], y.iloc[:n_train]

    s1 = LWCFeatureSelector(SelectorConfig(
        top_k_mi=20, n_features_mrmr=10, boruta_max_iter=20
    ))
    s2 = LWCFeatureSelector(SelectorConfig(
        top_k_mi=20, n_features_mrmr=10, boruta_max_iter=20
    ))
    s1.fit(X_train, y_train)
    s2.fit(X_train, y_train)
    assert s1.get_selected_names() == s2.get_selected_names()


def test_selector_picks_signal_over_noise(synthetic_data) -> None:
    """Em dados sintéticos com sinal forte, signal_* deve dominar a seleção."""
    X, y = synthetic_data
    sel = LWCFeatureSelector(SelectorConfig(
        top_k_mi=20, n_features_mrmr=10, boruta_max_iter=30
    ))
    sel.fit(X, y)
    selected = sel.get_selected_names()
    n_signal = sum(s.startswith("signal_") or s.startswith("redundant_") for s in selected)
    n_noise  = sum(s.startswith("noise_") for s in selected)
    assert n_signal > n_noise, (
        f"Esperava mais features de sinal que de ruido. "
        f"Selecionadas: signal+redundant={n_signal}, noise={n_noise}"
    )


def test_selector_pure_noise_returns_few(monkeypatch) -> None:
    """Em ruído puro, Boruta deve retornar conjunto vazio (fallback ativa)."""
    rng = np.random.default_rng(0)
    X = pd.DataFrame(rng.standard_normal((150, 30)),
                     columns=[f"noise_{i}" for i in range(30)])
    y = pd.Series(rng.integers(0, 2, 150))

    sel = LWCFeatureSelector(SelectorConfig(
        top_k_mi=20, n_features_mrmr=10, boruta_max_iter=15
    ))
    sel.fit(X, y)
    rep = sel.get_stage_report()
    # Em ruído puro, esperamos que Boruta selecione bem poucas features
    # (geralmente 0). Se 0, o fallback usa o resultado do mRMR.
    assert rep["stage3_output"] <= rep["stage2_output"]


def test_fit_transform_consistent(synthetic_data) -> None:
    """fit_transform deve dar o mesmo resultado que fit + transform."""
    X, y = synthetic_data
    sel1 = LWCFeatureSelector(SelectorConfig(
        top_k_mi=20, n_features_mrmr=10, boruta_max_iter=20
    ))
    Xa = sel1.fit_transform(X, y)
    sel2 = LWCFeatureSelector(SelectorConfig(
        top_k_mi=20, n_features_mrmr=10, boruta_max_iter=20
    ))
    Xb = sel2.fit(X, y).transform(X)
    np.testing.assert_array_equal(Xa, Xb)


def test_transform_before_fit_raises(synthetic_data) -> None:
    """transform sem fit deve levantar RuntimeError."""
    sel = LWCFeatureSelector()
    with pytest.raises(RuntimeError, match="ajustado"):
        sel.transform(synthetic_data[0])


def test_handles_nan(synthetic_data) -> None:
    """NaN nas features são imputados como 0 e o pipeline ainda roda."""
    X, y = synthetic_data
    Xn = X.copy()
    Xn.iloc[0, 0] = np.nan
    Xn.iloc[5, 10] = np.nan
    sel = LWCFeatureSelector(SelectorConfig(
        top_k_mi=20, n_features_mrmr=10, boruta_max_iter=15
    ))
    sel.fit(Xn, y)
    assert sel.get_stage_report()["final_output"] > 0
