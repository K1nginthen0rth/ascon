"""Testes para src/models/ciphertext_to_image.py + cnn2d.py + cnn2d_trainer.py."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import torch

from src.models.ciphertext_to_image import (
    ciphertext_to_image,
    batch_ciphertexts_to_images,
)
from src.models.cnn2d import CiphertextCNN2D
from src.models.cnn2d_trainer import CNN2DTrainer


# ---------------------------------------------------------------------------
# Conversão CT → imagem
# ---------------------------------------------------------------------------

def test_ciphertext_to_image_shape() -> None:
    """CT de 1040 bytes → imagem (32, 32) float32 (truncamento)."""
    ct = bytes(range(256)) * 4 + bytes(range(16))  # 1040 bytes
    img = ciphertext_to_image(ct, image_size=32)
    assert img.shape == (32, 32)
    assert img.dtype == np.float32


def test_ciphertext_to_image_short_ct() -> None:
    """CT de 80 bytes → imagem (32, 32) com padding zeros nas posições restantes."""
    ct = bytes(range(80))
    img = ciphertext_to_image(ct, image_size=32)
    assert img.shape == (32, 32)
    flat = img.flatten()
    assert np.allclose(flat[:80], np.arange(80) / 255.0)
    assert np.all(flat[80:] == 0.0)


def test_ciphertext_to_image_normalized() -> None:
    """Todos os valores entre 0.0 e 1.0."""
    rng = np.random.default_rng(0)
    for size in (80, 272, 1040, 2000):
        ct = bytes(rng.integers(0, 256, size).tolist())
        img = ciphertext_to_image(ct, image_size=32)
        assert img.min() >= 0.0
        assert img.max() <= 1.0


def test_ciphertext_to_image_truncates_when_long() -> None:
    """CT > image_size**2 é truncado nos primeiros image_size**2 bytes."""
    ct = bytes([1] * 1040)
    img = ciphertext_to_image(ct, image_size=32)
    assert img.shape == (32, 32)
    assert np.allclose(img, 1.0 / 255.0)


def test_batch_ciphertexts_to_images_shape() -> None:
    """Batch retorna (N, 1, image_size, image_size)."""
    rng = np.random.default_rng(0)
    cts = [
        bytes(rng.integers(0, 256, 80).tolist()),
        bytes(rng.integers(0, 256, 272).tolist()),
        bytes(rng.integers(0, 256, 1040).tolist()),
    ]
    arr = batch_ciphertexts_to_images(cts, image_size=32)
    assert arr.shape == (3, 1, 32, 32)
    assert arr.dtype == np.float32


# ---------------------------------------------------------------------------
# CiphertextCNN2D
# ---------------------------------------------------------------------------

def test_cnn2d_forward_shape() -> None:
    """Input (batch, 1, 32, 32) → output (batch, n_classes)."""
    model = CiphertextCNN2D(n_classes=2)
    x = torch.randn(4, 1, 32, 32)
    out = model(x)
    assert out.shape == (4, 2)


def test_cnn2d_extract_latent_shape() -> None:
    """Latent: (batch, 128)."""
    model = CiphertextCNN2D(n_classes=3)
    x = torch.randn(2, 1, 32, 32)
    z = model.extract_latent(x)
    assert z.shape == (2, model.latent_dim) == (2, 128)


def test_cnn2d_deterministic() -> None:
    """Mesma seed → mesmos pesos iniciais → mesma saída no forward."""
    torch.manual_seed(7)
    m1 = CiphertextCNN2D(n_classes=2)
    torch.manual_seed(7)
    m2 = CiphertextCNN2D(n_classes=2)

    m1.eval(); m2.eval()
    x = torch.randn(2, 1, 32, 32)
    with torch.no_grad():
        o1 = m1(x)
        o2 = m2(x)
    assert torch.allclose(o1, o2, atol=1e-6)


# ---------------------------------------------------------------------------
# Trainer (sintético, key-holdout)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def synthetic_raw_df():
    """
    DataFrame sintético:
    - 30 amostras, ciphertext de 1040 bytes
    - 2 classes balanceadas; sinal: byte 0 fixo para classe 0
    - splits train(20) / val(5) / test(5) com chaves disjuntas
    """
    rng = np.random.default_rng(0)
    n = 30
    rows = []
    keys   = [f"key_{i:04d}" for i in range(6)]
    splits = ["train"] * 4 + ["val"] + ["test"]
    for i in range(n):
        algo = "Ascon-AEAD128" if i % 2 == 0 else "GIFT-COFB"
        ct = bytearray(rng.integers(0, 256, 1040).tolist())
        if algo == "Ascon-AEAD128":
            ct[0] = 0xAA  # sinal fraco para o modelo aprender
        rows.append({
            "ciphertext": bytes(ct),
            "algorithm":  algo,
            "key_id":     keys[i % 6],
            "split":      splits[i % 6],
        })
    return pd.DataFrame(rows)


def test_cnn2d_trains_one_epoch(synthetic_raw_df) -> None:
    """O trainer completa pelo menos 1 época sem erro e retorna métricas."""
    trainer = CNN2DTrainer(
        image_size=32, batch_size=4, n_epochs=2, patience=5,
        seed=7, n_bootstrap=20,
    )
    res = trainer.train(synthetic_raw_df, verbose=False)
    assert res.metrics is not None
    assert 0.0 <= res.metrics.f1_macro <= 1.0
    assert res.y_pred.shape[0] > 0
    assert res.y_proba.shape == (res.y_pred.shape[0], 2)
    assert res.best_epoch >= 1


def test_cnn2d_prepare_split_label_consistency(synthetic_raw_df) -> None:
    """label_map deve ser ordenado e consistente entre splits."""
    trainer = CNN2DTrainer(image_size=32)
    _, _, lm_train = trainer.prepare_split(synthetic_raw_df, "train")
    _, _, lm_test  = trainer.prepare_split(synthetic_raw_df, "test")
    assert lm_train == lm_test
    assert lm_train == {"Ascon-AEAD128": 0, "GIFT-COFB": 1}
