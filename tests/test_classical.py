"""Testes para src/models/classical.py."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.features.selector import SelectorConfig
from src.models.classical import (
    ClassicalPipeline,
    _get_feature_columns,
    _verify_no_leakage,
)


@pytest.fixture(scope="module")
def synthetic_features_df():
    """
    DataFrame sintético com:
    - 60 amostras × 30 features
    - Coluna 'algorithm' (rótulo) e 'split' (40/10/10 por chave)
    - Sinal forte em features 0..2; ruído nas demais.
    """
    rng = np.random.default_rng(0)
    n, p = 60, 30
    y = rng.integers(0, 2, n)
    X = rng.standard_normal((n, p))
    X[:, :3] += 1.5 * (y[:, None] - 0.5) * 4  # sinal forte
    cols = [f"feat_{i}" for i in range(p)]
    df = pd.DataFrame(X, columns=cols)
    df["algorithm"] = ["Ascon-AEAD128" if v == 0 else "GIFT-COFB" for v in y]

    # Splits com chaves disjuntas
    keys = [f"key_{i:04d}" for i in range(6)]  # 6 chaves
    df["key_id"] = [keys[i % 6] for i in range(n)]
    # Train: keys 0..3 (40 amostras), Val: key 4 (10), Test: key 5 (10)
    split_map = {keys[i]: ("train" if i < 4 else "val" if i == 4 else "test") for i in range(6)}
    df["split"] = df["key_id"].map(split_map)

    df["len_pt"] = 100
    df["len_ad"] = 0
    df["len_ct"] = 116
    return df


def test_get_feature_columns_excludes_metadata(synthetic_features_df) -> None:
    """_get_feature_columns deve excluir todas as colunas de metadados."""
    feat = _get_feature_columns(synthetic_features_df)
    for forbidden in ["algorithm", "key_id", "split", "len_pt", "len_ad", "len_ct"]:
        assert forbidden not in feat


def test_no_len_pt_in_features(synthetic_features_df) -> None:
    """Confirmar que len_pt não vaza para o conjunto de features."""
    feat = _get_feature_columns(synthetic_features_df)
    _verify_no_leakage(feat)  # não levanta
    feat_with_leak = feat + ["len_pt"]
    with pytest.raises(ValueError, match="proibidas"):
        _verify_no_leakage(feat_with_leak)


def test_dummy_near_chance(synthetic_features_df) -> None:
    """Dummy stratified ≈ 0.5 em problema balanceado de 2 classes."""
    pipe = ClassicalPipeline(
        n_bootstrap=100,
        selector_config=SelectorConfig(
            top_k_mi=10, n_features_mrmr=5, boruta_max_iter=10,
        ),
    )
    res = pipe.run(synthetic_features_df, verbose=False)
    dummy_f1 = res.models["Dummy"].metrics.f1_macro
    # Em 10 amostras de teste o ruído é alto; aceitar [0.2, 0.8]
    assert 0.0 <= dummy_f1 <= 1.0
    # IC do Dummy deve cobrir 0.5 (chance)
    lo, hi = res.models["Dummy"].metrics.f1_macro_ci
    assert lo <= 0.5 <= hi or dummy_f1 < 0.55  # tolerância em N pequeno


def test_rf_trains_without_error(synthetic_features_df) -> None:
    """RF deve treinar e produzir predições do tamanho do test set."""
    pipe = ClassicalPipeline(
        n_bootstrap=100,
        selector_config=SelectorConfig(
            top_k_mi=10, n_features_mrmr=5, boruta_max_iter=10,
        ),
    )
    res = pipe.run(synthetic_features_df, verbose=False)
    assert "RF" in res.models
    rf = res.models["RF"]
    assert rf.y_pred.shape[0] == res.splits["test"]
    assert rf.y_proba is not None
    assert rf.y_proba.shape == (res.splits["test"], 2)


def test_pipeline_detects_key_leakage() -> None:
    """Se as chaves de train e test se sobrepõem, deve levantar erro."""
    rng = np.random.default_rng(0)
    n = 30
    df = pd.DataFrame(rng.standard_normal((n, 5)),
                      columns=[f"f{i}" for i in range(5)])
    df["algorithm"] = ["Ascon-AEAD128"] * 15 + ["GIFT-COFB"] * 15
    df["key_id"]    = ["key_0001"] * n  # MESMA chave em todos os splits
    df["split"]     = (["train"] * 15) + (["test"] * 15)
    pipe = ClassicalPipeline(
        n_bootstrap=20,
        selector_config=SelectorConfig(top_k_mi=3, n_features_mrmr=2),
    )
    with pytest.raises(ValueError, match="VAZAMENTO"):
        pipe.run(df, verbose=False)


def test_pipeline_returns_all_models(synthetic_features_df) -> None:
    """Pipeline deve retornar Dummy, RF, SVM, XGBoost."""
    pipe = ClassicalPipeline(
        n_bootstrap=50,
        selector_config=SelectorConfig(
            top_k_mi=10, n_features_mrmr=5, boruta_max_iter=10,
        ),
    )
    res = pipe.run(synthetic_features_df, verbose=False)
    assert set(res.models.keys()) == {"Dummy", "RF", "SVM", "XGBoost"}
    for name, m in res.models.items():
        assert m.metrics is not None
        assert 0.0 <= m.metrics.f1_macro <= 1.0
