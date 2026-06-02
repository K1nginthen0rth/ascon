"""
CNN 1D para classificação ciphertext-only de algoritmos LWC.

Arquitetura (Caminho B):
    Embedding(256, embed_dim) → [Conv1D → BN → ReLU → MaxPool] × n_conv_blocks
    → GlobalAvgPool → Dropout → FC → Softmax

Bytes (0-255) são tokenizados via Embedding learnable. Convoluções 1D capturam
padrões locais; pooling global ignora alinhamento absoluto.

A camada antes do FC (`extract_latent`) pode ser usada para modelos híbridos
no futuro.
"""
from __future__ import annotations

import torch
import torch.nn as nn


class CiphertextCNN1D(nn.Module):
    """
    CNN 1D com embedding de bytes para classificação de criptogramas.

    Args:
        n_classes:     número de classes de saída (default: 2).
        embed_dim:     dimensão do embedding por byte (default: 32).
        max_len:       comprimento fixo da sequência (pad/truncate; default: 1040).
        n_filters:     filtros do primeiro bloco conv; dobra a cada bloco.
        kernel_size:   tamanho do kernel (default: 3).
        n_conv_blocks: número de blocos Conv→BN→ReLU→MaxPool (default: 3).
        dropout:       probabilidade de dropout antes do FC (default: 0.3).

    Notes:
        max_len = 1040 cobre PT até 1024B + 16B tag (cenário key-holdout 2class).
    """

    def __init__(
        self,
        n_classes:     int   = 2,
        embed_dim:     int   = 32,
        max_len:       int   = 1040,
        n_filters:     int   = 128,
        kernel_size:   int   = 3,
        n_conv_blocks: int   = 3,
        dropout:       float = 0.3,
    ) -> None:
        super().__init__()
        self.max_len = max_len

        self.embedding = nn.Embedding(num_embeddings=256, embedding_dim=embed_dim)

        layers: list[nn.Module] = []
        in_channels = embed_dim
        for i in range(n_conv_blocks):
            out_channels = n_filters * (2 ** i)
            layers += [
                nn.Conv1d(in_channels, out_channels, kernel_size, padding=kernel_size // 2),
                nn.BatchNorm1d(out_channels),
                nn.ReLU(),
                nn.MaxPool1d(2),
            ]
            in_channels = out_channels
        self.conv_blocks = nn.Sequential(*layers)

        self.gap     = nn.AdaptiveAvgPool1d(1)
        self.dropout = nn.Dropout(dropout)
        self.fc      = nn.Linear(in_channels, n_classes)

        self._latent_dim = in_channels

    @property
    def latent_dim(self) -> int:
        return self._latent_dim

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: tensor (batch, seq_len) de inteiros 0-255.
        Returns:
            logits (batch, n_classes).
        """
        emb = self.embedding(x)              # (batch, seq_len, embed_dim)
        emb = emb.permute(0, 2, 1)           # (batch, embed_dim, seq_len)
        h   = self.conv_blocks(emb)          # (batch, channels, reduced_len)
        h   = self.gap(h).squeeze(-1)        # (batch, channels)
        h   = self.dropout(h)
        return self.fc(h)                    # (batch, n_classes)

    def extract_latent(self, x: torch.Tensor) -> torch.Tensor:
        """Vetor latente antes do FC — para modelos híbridos."""
        emb = self.embedding(x)
        emb = emb.permute(0, 2, 1)
        h   = self.conv_blocks(emb)
        return self.gap(h).squeeze(-1)
