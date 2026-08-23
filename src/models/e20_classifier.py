"""
Wrapper scikit-learn-compatible do `TransformerE20`, para caber no mesmo
pipeline (`.fit/.predict/.predict_proba`) dos demais modelos do Caminho A.
Ver `transformer_e20.py` para a justificativa do desenho.
"""
from __future__ import annotations

import numpy as np
import torch
import torch.nn as nn

from src.models.transformer_e20 import TransformerE20


class E20Classifier:
    """
    Treina o `TransformerE20` sobre um vetor JÁ REDUZIDO de features
    (a redução — filtro F + RFE — é responsabilidade de `E20FeatureFilter`,
    fitado fora desta classe para reaproveitar a mesma disciplina de
    "fit só no treino" do resto do pipeline).
    """

    def __init__(self, n_features: int, n_classes: int, seed: int = 7,
                 n_epochs: int = 60, lr: float = 1e-3, batch_size: int = 64,
                 device: str = "cpu") -> None:
        self.n_features = n_features
        self.n_classes = n_classes
        self.seed = seed
        self.n_epochs = n_epochs
        self.lr = lr
        self.batch_size = batch_size
        self.device = device
        self.model_: TransformerE20 | None = None
        self.mean_: np.ndarray | None = None
        self.std_: np.ndarray | None = None

    def fit(self, X: np.ndarray, y: np.ndarray) -> "E20Classifier":
        torch.manual_seed(self.seed)
        # z-score interno: o Transformer espera entradas de escala
        # razoável; as features NIST já vêm em [0,1] (p-values) ou em
        # escalas variadas (entropia, χ²) — padronizar evita que uma
        # feature de escala maior domine a projeção linear inicial.
        self.mean_ = X.mean(axis=0)
        self.std_ = X.std(axis=0)
        self.std_[self.std_ < 1e-8] = 1.0
        Xs = (X - self.mean_) / self.std_

        self.model_ = TransformerE20(n_features=self.n_features, n_classes=self.n_classes).to(self.device)
        optim = torch.optim.Adam(self.model_.parameters(), lr=self.lr)
        crit = nn.CrossEntropyLoss()

        Xt = torch.from_numpy(Xs.astype(np.float32)).to(self.device)
        yt = torch.from_numpy(y.astype(np.int64)).to(self.device)
        n = len(y)
        rng = np.random.default_rng(self.seed)

        self.model_.train()
        for _ in range(self.n_epochs):
            perm = rng.permutation(n)
            for lo in range(0, n, self.batch_size):
                idx = perm[lo:lo + self.batch_size]
                optim.zero_grad()
                loss = crit(self.model_(Xt[idx]), yt[idx])
                loss.backward()
                optim.step()
        self.model_.eval()
        return self

    def _prepare(self, X: np.ndarray) -> torch.Tensor:
        Xs = (X - self.mean_) / self.std_
        return torch.from_numpy(Xs.astype(np.float32)).to(self.device)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        with torch.no_grad():
            logits = self.model_(self._prepare(X)).cpu().numpy()
        e = np.exp(logits - logits.max(axis=1, keepdims=True))
        return e / e.sum(axis=1, keepdims=True)

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self.predict_proba(X).argmax(axis=1)
