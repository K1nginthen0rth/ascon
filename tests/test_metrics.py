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


def test_accuracy_matches_manual_computation() -> None:
    """`accuracy` (simples, não balanceada) deve bater com a fração de acertos."""
    y_true = np.array([0, 0, 1, 1, 2, 2, 2, 2])
    y_pred = np.array([0, 1, 1, 1, 2, 2, 2, 0])
    rep = compute_metrics(y_true, y_pred, n_bootstrap=50)
    expected_acc = np.mean(y_true == y_pred)
    assert rep.accuracy == pytest.approx(expected_acc)


def test_per_class_precision_recall_present_and_correct() -> None:
    """Precisão/recall por classe (Golden Rule 7 / ponto 8 do orientador)."""
    y_true = np.array([0, 0, 0, 1, 1, 1])
    y_pred = np.array([0, 0, 1, 1, 1, 0])  # classe 0: recall 2/3; classe 1: recall 2/3
    rep = compute_metrics(y_true, y_pred, n_bootstrap=50, labels=[0, 1])
    assert rep.per_class is not None
    assert set(rep.per_class.keys()) == {"0", "1"}
    assert rep.per_class["0"]["recall"] == pytest.approx(2 / 3)
    assert rep.per_class["1"]["recall"] == pytest.approx(2 / 3)
    assert rep.per_class["0"]["support"] == 3
    assert rep.per_class["1"]["support"] == 3


def test_auc_per_class_multiclass_exposes_outlier_class() -> None:
    """AUC por classe deve expor uma classe que descola das demais — o
    agregado OVR sozinho poderia mascarar isso (ponto do plano v2 §4.3)."""
    rng = np.random.default_rng(5)
    n_per_class = 200
    y_true = np.repeat([0, 1, 2], n_per_class)
    n = len(y_true)
    proba = rng.dirichlet(alpha=[1, 1, 1], size=n)
    # Classe 0 "vaza" no y_proba (quase perfeitamente separável); 1 e 2 ficam ruidosas.
    proba[y_true == 0] = [0.9, 0.05, 0.05]
    y_pred = proba.argmax(axis=1)

    rep = compute_metrics(y_true, y_pred, y_proba=proba, n_bootstrap=50, labels=[0, 1, 2])
    assert rep.auc_roc is not None
    auc_per_class = rep.auc_roc["auc_per_class"]
    assert auc_per_class is not None
    assert set(auc_per_class.keys()) == {"0", "1", "2"}
    # Classe 0 deve ter AUC bem mais alto que 1/2 (separabilidade injetada).
    assert auc_per_class["0"] > auc_per_class["1"]
    assert auc_per_class["0"] > auc_per_class["2"]


def test_as_dict_includes_new_fields() -> None:
    rng = np.random.default_rng(2)
    y_true = rng.integers(0, 3, 150)
    y_pred = rng.integers(0, 3, 150)
    proba = rng.dirichlet(alpha=[1, 1, 1], size=150)
    rep = compute_metrics(y_true, y_pred, y_proba=proba, n_bootstrap=50, labels=[0, 1, 2])
    d = rep.as_dict()
    assert "accuracy" in d
    assert "per_class" in d
    assert d["auc_roc"]["auc_per_class"] is not None


def test_bootstrap_por_cluster_alarga_o_ic_sob_efeito_de_chave():
    """
    **M1 (achado 2026-08-24).** O desenho é agrupado (100 slots por chave) e
    todo o protocolo reconhece isso — menos o bootstrap, que reamostrava
    amostras individuais. Sob sinal correlacionado à chave o IC i.i.d. sai
    estreito demais, e o veredicto primário do projeto é "o IC 95% exclui o
    acaso": erra na direção do falso positivo.

    Sob H₀ pura os dois coincidem (é por isso que o bug era invisível);
    com efeito de chave, o IC por cluster tem de ser sensivelmente mais
    largo.
    """
    rng = np.random.default_rng(0)
    n_keys, n_slots = 60, 100
    key_effect = rng.normal(0, 0.10, n_keys)      # ICC ~ 0,01

    y_true, y_pred, groups = [], [], []
    for k in range(n_keys):
        p_acc = float(np.clip(0.25 + key_effect[k], 0.05, 0.95))
        for _ in range(n_slots):
            t = int(rng.integers(0, 4))
            hit = rng.random() < p_acc
            y_true.append(t)
            y_pred.append(t if hit else (t + int(rng.integers(1, 4))) % 4)
            groups.append(f"k{k}")

    y_true = np.array(y_true); y_pred = np.array(y_pred); groups = np.array(groups)
    iid = compute_metrics(y_true, y_pred, labels=[0, 1, 2, 3], n_bootstrap=300)
    clu = compute_metrics(y_true, y_pred, labels=[0, 1, 2, 3], n_bootstrap=300,
                          groups=groups)

    largura_iid = iid.f1_macro_ci[1] - iid.f1_macro_ci[0]
    largura_clu = clu.f1_macro_ci[1] - clu.f1_macro_ci[0]
    assert largura_clu > 1.5 * largura_iid, (
        f"IC por cluster deveria ser bem mais largo sob efeito de chave: "
        f"i.i.d.={largura_iid:.4f} cluster={largura_clu:.4f}")
    # A estimativa pontual não muda — só a incerteza.
    assert iid.f1_macro == clu.f1_macro


def test_bootstrap_por_cluster_valida_tamanho_de_groups():
    rng = np.random.default_rng(0)
    y = rng.integers(0, 2, 50)
    with pytest.raises(ValueError, match="groups"):
        compute_metrics(y, y, labels=[0, 1], n_bootstrap=10,
                        groups=np.array(["a"] * 10))
