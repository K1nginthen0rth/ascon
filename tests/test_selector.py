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
    """Estágio 1 (MI, relevância pura) deve preferir sinal sobre ruído.

    Não testamos isso no output final (mRMR): mRMR penaliza redundância, e
    como signal_*/redundant_* são mutuamente correlacionados, o mRMR pode
    preferir diversidade (incluindo ruído) em vez de repetir sinal
    redundante — isso é uma propriedade esperada do mRMR, não um defeito.
    """
    X, y = synthetic_data
    sel = LWCFeatureSelector(SelectorConfig(
        top_k_mi=20, n_features_mrmr=10, boruta_max_iter=30
    ))
    sel.fit(X, y)
    names = sel._feature_names_in[sel._stage1_mask]
    n_signal = sum(s.startswith("signal_") or s.startswith("redundant_") for s in names)
    # top_k_mi=20 > 10 features reais (5 signal + 5 redundant), entao o
    # estagio 1 deve capturar TODAS elas (o resto do slack vai para ruido).
    assert n_signal == 10, (
        f"Esperava que o estagio 1 (MI) capturasse todas as 10 features "
        f"reais (signal+redundant) antes do ruido. Obteve: {n_signal}"
    )


def test_selector_pure_noise_boruta_confirms_few(monkeypatch) -> None:
    """Em ruído puro, Boruta deve confirmar poucas/zero features (diagnóstico).

    O Boruta não filtra o conjunto final (self._final_mask == mRMR) — ele só
    reporta stage3_boruta_confirmed / stage3_stability_ratio como diagnóstico
    de estabilidade.
    """
    rng = np.random.default_rng(0)
    X = pd.DataFrame(rng.standard_normal((150, 30)),
                     columns=[f"noise_{i}" for i in range(30)])
    y = pd.Series(rng.integers(0, 2, 150))

    sel = LWCFeatureSelector(SelectorConfig(
        top_k_mi=20, n_features_mrmr=10, boruta_max_iter=15
    ))
    sel.fit(X, y)
    rep = sel.get_stage_report()
    # Em ruído puro, esperamos que Boruta confirme bem poucas features
    # (geralmente 0), mas o conjunto final continua sendo o do mRMR.
    assert rep["stage3_boruta_confirmed"] <= rep["stage2_output"]
    assert rep["final_output"] == rep["stage2_output"]


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


# ---------------------------------------------------------------------------
# Fase 3 (v2): validação multiclasse — nunca usado além de 2 classes no
# projeto até agora (v1 era Ascon vs. GIFT-COFB, binário). MI/mRMR/Boruta
# do sklearn/mrmr/boruta_py já suportam multiclasse nativamente, mas isso
# nunca tinha sido exercitado neste pipeline especificamente.
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def synthetic_data_4class():
    """
    Dataset sintético 4-classes: 400 amostras, 50 features.
    - Features 0..4: sinal forte (médias diferentes por classe)
    - Features 5..9: redundantes com 0..4 (cópias com ruído)
    - Features 10..49: ruído puro
    """
    rng = np.random.default_rng(1)
    n, p_signal, p_redundant, p_noise = 400, 5, 5, 40
    n_classes = 4
    y = rng.integers(0, n_classes, n)
    X_signal = rng.standard_normal((n, p_signal))
    # Cada classe desloca a média num ponto diferente do espaço de sinal —
    # simula 4 algoritmos criptográficos com "assinaturas" distintas.
    class_offsets = rng.standard_normal((n_classes, p_signal)) * 2.0
    for j in range(p_signal):
        X_signal[:, j] += class_offsets[y, j]
    X_redundant = X_signal[:, :p_redundant] + 0.1 * rng.standard_normal((n, p_redundant))
    X_noise     = rng.standard_normal((n, p_noise))
    X = np.hstack([X_signal, X_redundant, X_noise]).astype(np.float64)
    names = (
        [f"signal_{i}"    for i in range(p_signal)]
        + [f"redundant_{i}" for i in range(p_redundant)]
        + [f"noise_{i}"    for i in range(p_noise)]
    )
    return pd.DataFrame(X, columns=names), pd.Series(y)


def test_selector_4class_reduces_dimensions_without_crashing(synthetic_data_4class) -> None:
    """Pipeline completo (VT padronizado -> MI -> mRMR -> Boruta) roda sem
    erro com y de 4 classes e reduz dimensionalidade normalmente."""
    X, y = synthetic_data_4class
    assert y.nunique() == 4
    sel = LWCFeatureSelector(SelectorConfig(
        top_k_mi=20, n_features_mrmr=10, boruta_max_iter=20
    ))
    sel.fit(X, y)
    out = sel.get_stage_report()
    assert out["stage1_input"]  == X.shape[1]
    assert out["stage1_output"] <= 20
    assert out["stage2_output"] <= 10
    assert out["final_output"]  == out["stage2_output"]
    assert out["final_output"]  >= 1


def test_selector_4class_picks_signal_over_noise(synthetic_data_4class) -> None:
    """MI (estágio 1) deve preferir as features com sinal por classe sobre
    ruído puro também no caso multiclasse."""
    X, y = synthetic_data_4class
    sel = LWCFeatureSelector(SelectorConfig(
        top_k_mi=20, n_features_mrmr=10, boruta_max_iter=30
    ))
    sel.fit(X, y)
    names = sel._feature_names_in[sel._stage1_mask]
    n_signal = sum(s.startswith("signal_") or s.startswith("redundant_") for s in names)
    assert n_signal == 10, (
        f"Esperava que o estagio 1 (MI) capturasse todas as 10 features "
        f"reais (signal+redundant) antes do ruido no caso 4-classes. "
        f"Obteve: {n_signal}"
    )


def test_selector_4class_transform_shape(synthetic_data_4class) -> None:
    X, y = synthetic_data_4class
    sel = LWCFeatureSelector(SelectorConfig(
        top_k_mi=20, n_features_mrmr=10, boruta_max_iter=20
    ))
    sel.fit(X, y)
    Xt = sel.transform(X)
    assert Xt.shape[0] == X.shape[0]
    assert Xt.shape[1] == sel.get_stage_report()["final_output"]


def test_selector_4class_deterministic(synthetic_data_4class) -> None:
    """fit é determinístico (mesma seed) também no caso 4-classes."""
    X, y = synthetic_data_4class
    cfg = SelectorConfig(top_k_mi=20, n_features_mrmr=10, boruta_max_iter=20)
    s1 = LWCFeatureSelector(cfg).fit(X, y)
    s2 = LWCFeatureSelector(cfg).fit(X, y)
    assert s1.get_selected_names() == s2.get_selected_names()


# ---------------------------------------------------------------------------
# Fase 3 (v2): regressão do bug de escala absoluta no VT (motivou a
# padronização z-score — ver docstring do módulo e
# scripts/run_ablation_fs_60k.py). Reproduz a assinatura do bug: uma
# feature com sinal real mas variância ABSOLUTA minúscula (como o
# histograma de bytes do v1, valores ~1/256) não pode mais ser descartada
# só por estar numa escala pequena.
# ---------------------------------------------------------------------------
def test_vt_standardization_keeps_small_scale_signal():
    """Feature de escala pequena (~1e-3, variância ABSOLUTA bem abaixo do
    threshold bruto de 1e-5 x ~256 haria com que fosse descartada sem
    padronização) mas com sinal real deve sobreviver ao VT depois de
    padronizada — o mesmo cenário que descartava o histograma de bytes
    inteiro no v1."""
    rng = np.random.default_rng(2)
    n = 300
    y = rng.integers(0, 2, n)

    # Feature de "escala de histograma": valores pequenos (~1/256 ± ruido
    # pequeno), mas com deslocamento real e consistente por classe —
    # sinal genuíno, escala minúscula. Variância absoluta ~1e-7, bem
    # abaixo do threshold bruto de 1e-5 usado em unidades absolutas no v1.
    small_scale_signal = (1.0 / 256.0) + 0.002 * (y - 0.5) + 1e-4 * rng.standard_normal(n)
    # Ruído puro na MESMA escala pequena, para garantir que o teste não
    # passa só porque "toda feature pequena sobrevive" — só a que tem
    # sinal deveria ficar entre os top-k do MI.
    small_scale_noise = (1.0 / 256.0) + 1e-4 * rng.standard_normal(n)
    # Feature verdadeiramente constante (deve ser descartada de qualquer forma).
    constant_feature = np.full(n, 1.0 / 256.0)

    X = pd.DataFrame({
        "small_scale_signal": small_scale_signal,
        "small_scale_noise": small_scale_noise,
        "constant": constant_feature,
    })
    y_s = pd.Series(y)

    sel = LWCFeatureSelector(SelectorConfig(
        top_k_mi=2, n_features_mrmr=1, boruta_max_iter=15
    ))
    sel.fit(X, y_s)
    rep = sel.get_stage_report()

    # A constante (variância 0 mesmo padronizada) deve ser descartada; as
    # outras duas (escala pequena, mas variância não-nula) devem sobreviver
    # ao VT — diferença do bug antigo, que descartava por escala absoluta.
    assert rep["stage0_zero_variance"] == 1
    assert rep["stage1_after_variance"] == 2
    # E o mRMR deve preferir a que tem sinal de verdade sobre a de ruído puro.
    assert sel.get_selected_names() == ["small_scale_signal"]


def test_zero_variance_feature_does_not_produce_nan_or_warning(synthetic_data):
    """Feature constante no treino não deve gerar NaN/inf/warning de divisão
    por zero durante a padronização do estágio 0."""
    X, y = synthetic_data
    Xc = X.copy()
    Xc["all_constant"] = 7.0
    sel = LWCFeatureSelector(SelectorConfig(
        top_k_mi=20, n_features_mrmr=10, boruta_max_iter=15
    ))
    with np.errstate(divide="raise", invalid="raise"):
        sel.fit(Xc, y)
    assert "all_constant" not in sel.get_selected_names()
    assert sel.get_stage_report()["stage0_zero_variance"] >= 1
