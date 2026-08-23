"""
Réplica fiel do E20 (Yuan et al., 2026) — Transformer sobre um vetor curto
de features NIST+entropia, não sobre bytes crus. Ver
docs/plano_experimento_v2/03_classificadores.md §3.1/§3.5.

**Por que existe separado do Caminho E:** o Caminho E (`transformer1d.py`)
é uma contribuição própria — atenção hierárquica sobre a sequência crua de
bytes. Esta classe é a réplica do estudo original, que usa uma
representação totalmente diferente (poucas features estatísticas
pré-filtradas). Sem esta réplica, a alegação "a técnica do Yuan et al.,
sob nosso protocolo, dá X" não seria sustentável — estaríamos testando uma
arquitetura parecida sobre dados que o estudo original nunca viu.

**Operacionalização (o artigo não expõe hiperparâmetros arquiteturais
exatos, então as escolhas abaixo são documentadas explicitamente para a
seção de métodos da dissertação):**
- Seleção de features: filtro por estatística F (`sklearn.f_classif`) na
  suíte NIST+entropia, seguido de RFE (Recursive Feature Elimination) com
  um RandomForest raso como estimador de importância, reduzindo a ~8
  features — como no artigo original.
- Cada uma das ~8 features vira um "token" escalar, projetado para
  `d_model` por uma camada linear compartilhada + embedding posicional
  aprendido (a ORDEM das 8 features é arbitrária — o papel do posicional
  aqui é só permitir que o modelo distinga os tokens entre si, não
  codificar uma ordem semântica real, ao contrário do Caminho E onde a
  posição no ciphertext é informativa).
- Encoder-only, poucas camadas (é um vetor de 8 tokens — não há
  necessidade de hierarquia local/global como no Caminho E).
- Pooling por média + cabeça linear.

Este módulo expõe `E20FeatureFilter` (seleção de features fitada só no
treino) e `TransformerE20` (o modelo). Um wrapper scikit-learn-compatible
(`E20Classifier`, em `src/models/e20_classifier.py`) integra os dois ao
pipeline do Caminho A.
"""
from __future__ import annotations

import numpy as np
import torch
import torch.nn as nn
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_selection import RFE, f_classif


class E20FeatureFilter:
    """
    Filtro por estatística F + RFE, reduzindo a suíte NIST+entropia a
    `n_features_out` colunas. Fitado SEMPRE só no treino de cada fold
    (mesma disciplina do `LWCFeatureSelector` principal).
    """

    def __init__(self, n_features_out: int = 8, f_prefilter: int = 20,
                 random_state: int = 13) -> None:
        self.n_features_out = n_features_out
        self.f_prefilter = f_prefilter
        self.random_state = random_state
        self.selected_indices_: np.ndarray | None = None
        self.selected_names_: list[str] | None = None

    def fit(self, X: np.ndarray, y: np.ndarray, feature_names: list[str]) -> "E20FeatureFilter":
        k = min(self.f_prefilter, X.shape[1])
        f_scores, _ = f_classif(X, y)
        f_scores = np.nan_to_num(f_scores, nan=-np.inf)
        pre_idx = np.argsort(f_scores)[::-1][:k]

        n_out = min(self.n_features_out, len(pre_idx))
        estimator = RandomForestClassifier(
            n_estimators=100, max_depth=6, random_state=self.random_state, n_jobs=-1,
        )
        rfe = RFE(estimator, n_features_to_select=n_out, step=1)
        rfe.fit(X[:, pre_idx], y)
        self.selected_indices_ = pre_idx[rfe.support_]
        self.selected_names_ = [feature_names[i] for i in self.selected_indices_]
        return self

    def transform(self, X: np.ndarray) -> np.ndarray:
        if self.selected_indices_ is None:
            raise RuntimeError("E20FeatureFilter não foi fitado")
        return X[:, self.selected_indices_]


class TransformerE20(nn.Module):
    """
    Encoder-only Transformer sobre um vetor curto de features (réplica
    E20). Cada feature escalar é um token; ver docstring do módulo para a
    justificativa do desenho.
    """

    def __init__(
        self, n_features: int = 8, n_classes: int = 4, d_model: int = 32,
        n_heads: int = 4, n_layers: int = 2, dim_ff: int = 64, dropout: float = 0.1,
    ) -> None:
        super().__init__()
        if d_model % n_heads != 0:
            raise ValueError(f"d_model ({d_model}) deve ser divisível por n_heads ({n_heads})")
        self.n_features = n_features
        self.d_model = d_model

        self.token_proj = nn.Linear(1, d_model)
        self.pos_embed = nn.Parameter(torch.zeros(1, n_features, d_model))
        nn.init.trunc_normal_(self.pos_embed, std=0.02)

        layer = nn.TransformerEncoderLayer(
            d_model=d_model, nhead=n_heads, dim_feedforward=dim_ff,
            dropout=dropout, batch_first=True, norm_first=True,
        )
        self.encoder = nn.TransformerEncoder(layer, num_layers=n_layers)
        self.norm = nn.LayerNorm(d_model)
        self.dropout = nn.Dropout(dropout)
        self.fc = nn.Linear(d_model, n_classes)

    def extract_latent(self, x: torch.Tensor) -> torch.Tensor:
        """x: (batch, n_features) float. Returns (batch, d_model)."""
        tokens = self.token_proj(x.unsqueeze(-1))  # (B, n_features, d_model)
        tokens = tokens + self.pos_embed
        enc = self.encoder(tokens)
        return self.norm(enc.mean(dim=1))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.fc(self.dropout(self.extract_latent(x)))

    def count_parameters(self, trainable_only: bool = True) -> int:
        params = self.parameters()
        if trainable_only:
            params = (p for p in params if p.requires_grad)
        return sum(p.numel() for p in params)
