"""Testes da família opcional `blockalign` (features alinhadas ao bloco).

Cobre o que importa: que a família detecta estrutura de bloco que as
features marginais não veem (é a razão de ela existir), que ela NÃO entra
no vetor padrão de 641 dimensões, e que degrada sem quebrar em entrada
pequena/vazia.
"""
from __future__ import annotations

import os

import numpy as np
import pytest

from src.features.extractor import CiphertextFeatureExtractor
from src.features.families.blockalign import extract_blockalign

_RNG = np.random.default_rng(20260911)


def _random_ct(n: int = 4096) -> bytes:
    return _RNG.integers(0, 256, n, dtype=np.uint8).tobytes()


def test_retorna_18_features() -> None:
    feats = extract_blockalign(_random_ct())
    assert len(feats) == 18
    assert all(isinstance(v, float) for v in feats.values())


def test_entrada_vazia_ou_curta_vira_nan_sem_quebrar() -> None:
    for ct in (b"", b"\x00" * 8):  # 8 bytes: 1 bloco de 8, nenhum de 16
        feats = extract_blockalign(ct)
        assert len(feats) == 18
        assert any(np.isnan(v) for v in feats.values())


def test_aleatorio_fica_perto_do_ideal() -> None:
    """Bytes uniformes: Hamming entre blocos consecutivos ~0,5 e sem repetição."""
    feats = extract_blockalign(_random_ct(65536))
    assert feats["blk16_hamming_consec_mean"] == pytest.approx(0.5, abs=0.02)
    assert feats["blk8_hamming_consec_mean"] == pytest.approx(0.5, abs=0.02)
    assert feats["blk16_repeat_rate"] == 0.0
    assert feats["blk16_diff_entropy"] == pytest.approx(8.0, abs=0.05)


def test_deteta_repeticao_de_bloco_que_marginal_nao_ve() -> None:
    """O ponto da família: dois ciphertexts com a MESMA distribuição marginal
    de bytes, um com estrutura de bloco e outro sem, têm que se separar aqui.

    Construção: pega blocos aleatórios e repete cada um duas vezes. O
    histograma global de bytes é idêntico ao do material de origem (mesmos
    bytes, cada um duas vezes), mas metade dos pares de blocos consecutivos
    é idêntica — invisível para histograma/entropia, óbvia para `repeat_rate`.
    """
    base = _RNG.integers(0, 256, (2048, 16), dtype=np.uint8)
    repetido = np.repeat(base, 2, axis=0).tobytes()
    plano = base.tobytes()

    f_rep = extract_blockalign(repetido)
    f_plano = extract_blockalign(plano)

    assert f_rep["blk16_repeat_rate"] > 0.4
    assert f_plano["blk16_repeat_rate"] == 0.0
    assert f_rep["blk16_hamming_consec_mean"] < f_plano["blk16_hamming_consec_mean"]

    # as marginais de byte são as mesmas nos dois (é esse o ponto)
    h_rep = np.bincount(np.frombuffer(repetido, np.uint8), minlength=256) / len(repetido)
    h_plano = np.bincount(np.frombuffer(plano, np.uint8), minlength=256) / len(plano)
    assert np.allclose(h_rep, h_plano)


def test_deteta_vies_por_posicao_no_bloco() -> None:
    """Byte fixo numa posição do bloco: dispersão de entropia por offset sobe."""
    blocks = _RNG.integers(0, 256, (2048, 16), dtype=np.uint8)
    enviesado = blocks.copy()
    enviesado[:, 5] = 0x42  # posição 5 constante

    f_ok = extract_blockalign(blocks.tobytes())
    f_vies = extract_blockalign(enviesado.tobytes())

    assert f_vies["blk16_offset_entropy_range"] > f_ok["blk16_offset_entropy_range"]
    assert f_vies["blk16_offset_entropy_std"] > f_ok["blk16_offset_entropy_std"]


def test_nao_entra_no_vetor_padrao() -> None:
    """Regressão: o default continua com 641 dimensões, sem `blockalign`."""
    padrao = CiphertextFeatureExtractor()
    assert padrao.n_features() == 641
    assert not any(k.startswith("blk8_") or k.startswith("blk16_")
                   for k in padrao.feature_names())


def test_entra_quando_pedida_explicitamente() -> None:
    ext = CiphertextFeatureExtractor(families=["histogram", "blockalign"])
    names = ext.feature_names()
    assert any(n.startswith("blk16_") for n in names)
    assert len(names) == 256 + 18
