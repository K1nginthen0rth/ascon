"""Testes para src/models/cnn1d.py + cnn_trainer.py."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import torch

from src.models.cnn1d import CiphertextCNN1D
from src.models.cnn_trainer import CNN1DTrainer, _bytes_to_tensor


def test_forward_shape() -> None:
    """forward(x) → (batch, n_classes)."""
    model = CiphertextCNN1D(n_classes=2, max_len=128, n_filters=16, n_conv_blocks=2)
    x = torch.randint(0, 256, size=(4, 128))
    out = model(x)
    assert out.shape == (4, 2)


def test_extract_latent_shape() -> None:
    """extract_latent(x) → (batch, latent_dim)."""
    model = CiphertextCNN1D(n_classes=3, max_len=64, n_filters=8, n_conv_blocks=2)
    x = torch.randint(0, 256, size=(2, 64))
    z = model.extract_latent(x)
    assert z.shape == (2, model.latent_dim)


def test_bytes_to_tensor_padding() -> None:
    """Bytes < max_len são preenchidos com zeros."""
    arr = _bytes_to_tensor(b"\x01\x02\x03", max_len=8)
    assert arr.shape == (8,)
    assert list(arr) == [1, 2, 3, 0, 0, 0, 0, 0]
    assert arr.dtype == np.int64


def test_bytes_to_tensor_truncation() -> None:
    """Bytes > max_len são truncados."""
    arr = _bytes_to_tensor(bytes(range(20)), max_len=10)
    assert arr.shape == (10,)
    assert list(arr) == list(range(10))


@pytest.fixture(scope="module")
def synthetic_raw_df():
    """
    DataFrame sintético com:
    - 30 amostras, ciphertext de 64 bytes
    - 2 classes balanceadas; sinal: padrão de byte fixo no início para classe 0
    - splits train(20) / val(5) / test(5) com chaves disjuntas
    """
    rng = np.random.default_rng(0)
    n = 30
    rows = []
    keys = [f"key_{i:04d}" for i in range(6)]
    splits = ["train"] * 4 + ["val"] + ["test"]
    for i in range(n):
        algo = "Ascon-AEAD128" if i % 2 == 0 else "GIFT-COFB"
        ct = bytearray(rng.integers(0, 256, 64).tolist())
        if algo == "Ascon-AEAD128":
            ct[0] = 0xAA  # sinal fraco para o modelo aprender
        rows.append({
            "ciphertext": bytes(ct),
            "algorithm":  algo,
            "key_id":     keys[i % 6],
            "split":      splits[i % 6],
        })
    return pd.DataFrame(rows)


def test_trains_one_epoch(synthetic_raw_df) -> None:
    """O trainer completa pelo menos 1 época sem erro e retorna métricas."""
    trainer = CNN1DTrainer(
        max_len=64, batch_size=4, n_epochs=2, patience=5,
        seed=7, n_bootstrap=20,
    )
    res = trainer.train(synthetic_raw_df, verbose=False)
    assert res.metrics is not None
    assert 0.0 <= res.metrics.f1_macro <= 1.0
    assert res.y_pred.shape[0] > 0
    assert res.y_proba.shape == (res.y_pred.shape[0], 2)
    assert res.best_epoch >= 1


def test_prepare_split_label_consistency(synthetic_raw_df) -> None:
    """label_map deve ser ordenado e consistente entre splits."""
    trainer = CNN1DTrainer(max_len=64)
    _, _, lm_train = trainer.prepare_split(synthetic_raw_df, "train")
    _, _, lm_test  = trainer.prepare_split(synthetic_raw_df, "test")
    assert lm_train == lm_test
    assert lm_train == {"Ascon-AEAD128": 0, "GIFT-COFB": 1}
