"""
Métricas de avaliação para classificação LWC ciphertext-only.

Inclui:
  - compute_metrics: F1-macro + balanced accuracy + IC bootstrap 95%
  - mcnemar_test: comparação pareada entre dois modelos
  - expected_calibration_error: ECE para verificar calibração

Convenções:
  - Seed do bootstrap: 42 (configurável)
  - n_bootstrap default: 1000
  - alpha default: 0.05 (IC 95%)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
from sklearn.metrics import (
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    roc_auc_score,
    roc_curve,
    top_k_accuracy_score,
)


@dataclass
class MetricsReport:
    """Resultado consolidado das métricas de um modelo."""
    f1_macro:              float
    f1_macro_ci:           tuple[float, float]
    balanced_accuracy:     float
    balanced_accuracy_ci:  tuple[float, float]
    top_k_accuracy:        Optional[float]
    ece:                   Optional[float]
    confusion_matrix:      np.ndarray
    n_samples:             int
    n_bootstrap:           int
    auc_roc:               Optional[dict] = None

    def as_dict(self) -> dict:
        return {
            "f1_macro":             self.f1_macro,
            "f1_macro_ci_lower":    self.f1_macro_ci[0],
            "f1_macro_ci_upper":    self.f1_macro_ci[1],
            "balanced_accuracy":    self.balanced_accuracy,
            "bal_acc_ci_lower":     self.balanced_accuracy_ci[0],
            "bal_acc_ci_upper":     self.balanced_accuracy_ci[1],
            "top_k_accuracy":       self.top_k_accuracy,
            "ece":                  self.ece,
            "confusion_matrix":     self.confusion_matrix.tolist(),
            "n_samples":            self.n_samples,
            "n_bootstrap":          self.n_bootstrap,
            "auc_roc":              (
                {
                    "auc": self.auc_roc["auc"],
                    "fpr": self.auc_roc["fpr"],
                    "tpr": self.auc_roc["tpr"],
                }
                if self.auc_roc is not None else None
            ),
        }


def compute_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_proba: Optional[np.ndarray] = None,
    labels: Optional[list] = None,
    n_bootstrap: int = 1000,
    seed: int = 42,
    top_k: int = 1,
) -> MetricsReport:
    """
    Calcula F1-macro + balanced accuracy + IC bootstrap 95% (percentil).

    Args:
        y_true: rótulos verdadeiros (n_samples,).
        y_pred: predições do modelo (n_samples,).
        y_proba: probabilidades por classe (n_samples, n_classes). Opcional.
        labels: lista de rótulos para confusion_matrix. Default: np.unique(y_true).
        n_bootstrap: número de reamostragens bootstrap.
        seed: semente para reprodutibilidade.
        top_k: k em top-k accuracy (válido se y_proba presente e n_classes > 1).

    Returns:
        MetricsReport com todos os campos calculados.
    """
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    n      = len(y_true)
    if labels is None:
        labels = sorted(np.unique(np.concatenate([y_true, y_pred])).tolist())

    # Pontuais
    f1   = f1_score(y_true, y_pred, average="macro", labels=labels, zero_division=0)
    bal  = balanced_accuracy_score(y_true, y_pred)
    cm   = confusion_matrix(y_true, y_pred, labels=labels)

    # Bootstrap percentil
    rng = np.random.default_rng(seed)
    f1_boots:  list[float] = []
    bal_boots: list[float] = []
    for _ in range(n_bootstrap):
        idx = rng.integers(0, n, size=n)
        yt, yp = y_true[idx], y_pred[idx]
        f1_boots.append(
            f1_score(yt, yp, average="macro", labels=labels, zero_division=0)
        )
        bal_boots.append(balanced_accuracy_score(yt, yp))
    f1_lo, f1_hi   = np.percentile(f1_boots,  [2.5, 97.5])
    bal_lo, bal_hi = np.percentile(bal_boots, [2.5, 97.5])

    # Top-k e ECE (se y_proba disponível)
    top_k_acc = None
    ece       = None
    if y_proba is not None:
        n_classes = np.asarray(y_proba).shape[1]
        if top_k > 1 and n_classes > top_k:
            top_k_acc = float(
                top_k_accuracy_score(y_true, y_proba, k=top_k, labels=labels)
            )
        ece = expected_calibration_error(y_true, y_proba, n_bins=10)

    auc_roc = compute_auc_roc(y_true, y_proba, labels=labels)

    return MetricsReport(
        f1_macro=float(f1),
        f1_macro_ci=(float(f1_lo), float(f1_hi)),
        balanced_accuracy=float(bal),
        balanced_accuracy_ci=(float(bal_lo), float(bal_hi)),
        top_k_accuracy=top_k_acc,
        ece=ece,
        confusion_matrix=cm,
        n_samples=n,
        n_bootstrap=n_bootstrap,
        auc_roc=auc_roc,
    )


def compute_auc_roc(
    y_true: np.ndarray,
    y_proba: Optional[np.ndarray],
    labels: Optional[list] = None,
) -> Optional[dict]:
    """
    Calcula AUC-ROC e os pontos da curva ROC (fpr/tpr) para plotagem.

    Para problema binário, usa y_proba[:, 1] (classe positiva) como score,
    considerando as classes ordenadas conforme `labels` (ou np.unique(y_true)
    se `labels` for None).

    Args:
        y_true: rótulos verdadeiros (n_samples,).
        y_proba: probabilidades por classe (n_samples, n_classes). Se None,
            retorna None (mesmo padrão de top_k_accuracy em compute_metrics).
        labels: lista de rótulos ordenados. Default: np.unique(y_true).

    Returns:
        dict {"auc": float, "fpr": list, "tpr": list, "thresholds": list}
        ou None se y_proba for None.
    """
    if y_proba is None:
        return None

    y_true  = np.asarray(y_true)
    y_proba = np.asarray(y_proba)
    if labels is None:
        labels = sorted(np.unique(y_true).tolist())

    n_classes = y_proba.shape[1]
    if n_classes == 2:
        # pos_label so confiavel quando `labels` cobre as 2 classes; caso
        # contrario (ex.: batch com 1 unica classe), assume convencao
        # padrao sklearn de classes 0..n_classes-1 para a coluna 1.
        pos_label = labels[1] if len(labels) == n_classes else 1
        scores = y_proba[:, 1]
        auc = float(roc_auc_score(y_true, scores))
        fpr, tpr, thresholds = roc_curve(y_true, scores, pos_label=pos_label)
    else:
        auc = float(
            roc_auc_score(y_true, y_proba, labels=labels, multi_class="ovr")
        )
        fpr, tpr, thresholds = [], [], []

    return {
        "auc":        auc,
        "fpr":        np.asarray(fpr).tolist(),
        "tpr":        np.asarray(tpr).tolist(),
        "thresholds": np.asarray(thresholds).tolist(),
    }


def mcnemar_test(
    y_true: np.ndarray,
    y_pred_a: np.ndarray,
    y_pred_b: np.ndarray,
    alpha: float = 0.05,
    continuity_correction: bool = True,
) -> dict:
    """
    Teste de McNemar para comparar dois classificadores (predições pareadas).

    Tabela de contingência:
        n11: ambos acertam     n10: A acerta, B erra
        n01: A erra, B acerta  n00: ambos erram
    Estatística (com correção de continuidade):
        chi2 = (|n10 - n01| - 1)^2 / (n10 + n01)

    Returns:
        dict com:
          n10, n01, n11, n00, statistic, p_value,
          significant (bool), alpha, conclusion (str)
    """
    y_true   = np.asarray(y_true)
    y_pred_a = np.asarray(y_pred_a)
    y_pred_b = np.asarray(y_pred_b)

    a_correct = (y_pred_a == y_true)
    b_correct = (y_pred_b == y_true)

    n11 = int(np.sum( a_correct &  b_correct))
    n10 = int(np.sum( a_correct & ~b_correct))
    n01 = int(np.sum(~a_correct &  b_correct))
    n00 = int(np.sum(~a_correct & ~b_correct))

    discordant = n10 + n01

    if discordant == 0:
        # Modelos idênticos em todas as predições
        return {
            "n11": n11, "n10": n10, "n01": n01, "n00": n00,
            "statistic": 0.0, "p_value": 1.0,
            "significant": False, "alpha": alpha,
            "conclusion": "modelos identicos (sem discordancia)",
        }

    if continuity_correction:
        statistic = (abs(n10 - n01) - 1) ** 2 / discordant
    else:
        statistic = (n10 - n01) ** 2 / discordant

    # chi^2 com 1 grau de liberdade
    from scipy.stats import chi2
    p_value = float(chi2.sf(statistic, df=1))
    significant = p_value < alpha

    return {
        "n11": n11, "n10": n10, "n01": n01, "n00": n00,
        "statistic":   float(statistic),
        "p_value":     p_value,
        "significant": bool(significant),
        "alpha":       alpha,
        "conclusion":  "significativo" if significant else "nao significativo",
    }


def expected_calibration_error(
    y_true: np.ndarray,
    y_proba: np.ndarray,
    n_bins: int = 10,
) -> float:
    """
    Expected Calibration Error (ECE).

    Particiona predições em n_bins por confiança máxima e calcula a diferença
    média ponderada |conf - acc| em cada bin. ECE=0 indica calibração perfeita.
    """
    y_true  = np.asarray(y_true)
    y_proba = np.asarray(y_proba)
    n       = len(y_true)

    if y_proba.ndim != 2:
        raise ValueError("y_proba deve ser 2D (n_samples, n_classes)")

    confidences = y_proba.max(axis=1)
    predictions = y_proba.argmax(axis=1)
    # Mapear y_true para mesma ordem dos índices das colunas (assume sorted)
    # Para classes int 0..K-1 contiguas:
    correct = (predictions == y_true).astype(float)

    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    for i in range(n_bins):
        lo, hi = bin_edges[i], bin_edges[i + 1]
        if i == n_bins - 1:
            mask = (confidences >= lo) & (confidences <= hi)
        else:
            mask = (confidences >= lo) & (confidences <  hi)
        m = mask.sum()
        if m == 0:
            continue
        avg_conf = confidences[mask].mean()
        avg_acc  = correct[mask].mean()
        ece += (m / n) * abs(avg_conf - avg_acc)
    return float(ece)
