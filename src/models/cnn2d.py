"""
CNN 2D para classificação ciphertext-only (criptograma como imagem).

Arquitetura simples treinada do zero (NÃO usar pretrained ImageNet — features
de fotos naturais são irrelevantes para criptogramas, que parecem ruído):

    Input: (batch, 1, 32, 32)
    [Conv2D(1→32, 3×3, pad=1) → BN → ReLU → MaxPool(2)]   → (batch, 32, 16, 16)
    [Conv2D(32→64, 3×3, pad=1) → BN → ReLU → MaxPool(2)]  → (batch, 64,  8,  8)
    [Conv2D(64→128, 3×3, pad=1) → BN → ReLU → MaxPool(2)] → (batch, 128, 4,  4)
    Global Average Pooling                                  → (batch, 128)
    Dropout(0.3)
    FC(128 → n_classes)

Referências:
    - Sikdar & Kule (2024): ResNet50V2 / MobileNetV2 sobre punched-tape images.
    - LeCun et al. (2015): Deep Learning, Nature 521.
"""
from __future__ import annotations

import torch
import torch.nn as nn


class CiphertextCNN2D(nn.Module):
    """CNN 2D simples (treino do zero) para imagens 32x32 de criptogramas.

    Args:
        n_classes: número de classes (default 2).
        dropout:   dropout antes do FC (default 0.3).
    """

    def __init__(self, n_classes: int = 2, dropout: float = 0.3) -> None:
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(1, 32, kernel_size=3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(),
            nn.MaxPool2d(2),

            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(),
            nn.MaxPool2d(2),

            nn.Conv2d(64, 128, kernel_size=3, padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(),
            nn.MaxPool2d(2),
        )
        self.gap = nn.AdaptiveAvgPool2d(1)
        self.dropout = nn.Dropout(dropout)
        self.fc = nn.Linear(128, n_classes)
        self._latent_dim = 128

    @property
    def latent_dim(self) -> int:
        return self._latent_dim

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Args: x shape (batch, 1, H, W). Returns logits (batch, n_classes)."""
        h = self.features(x)
        h = self.gap(h).squeeze(-1).squeeze(-1)
        h = self.dropout(h)
        return self.fc(h)

    def extract_latent(self, x: torch.Tensor) -> torch.Tensor:
        """Vetor latente (batch, 128) antes do FC."""
        h = self.features(x)
        return self.gap(h).squeeze(-1).squeeze(-1)
