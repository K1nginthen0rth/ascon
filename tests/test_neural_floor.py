"""As redes do estudo de piso: formato de entrada, interface e capacidade.

O teste que importa é o da capacidade: com a representação `par`, uma
regressão logística não consegue separar um XOR, e a ResNet no estilo Gohr
tem que conseguir, porque alinha o bit b de C1 com o bit b de C2 no mesmo
passo da sequência. Se isso falhar, a comparação "modelo mais forte" não mede
o que diz medir.
"""
from __future__ import annotations

import numpy as np
import pytest
from sklearn.linear_model import LogisticRegression

from scripts.reduced_rounds.neural_floor import (
    ARQUITETURAS, HibridoD, NeuralBitClassifier, _meta_f, _por_posicao, build_neural_models)


def test_alinhamento_por_posicao_poe_o_mesmo_bit_dos_dois_blocos_no_mesmo_passo() -> None:
    L = 4
    c1 = np.zeros((1, L * 8)); c2 = np.zeros((1, L * 8))
    c1[0, 2 * 8 + 5] = 1          # bit 5 do byte 2 do C1
    c2[0, 2 * 8 + 5] = 1          # bit 5 do byte 2 do C2
    x = _por_posicao(np.hstack([c1, c2]), blocos=2)
    assert x.shape == (1, 16, L)
    assert x[0, 5, 2] == 1 and x[0, 8 + 5, 2] == 1 and x.sum() == 2


@pytest.mark.parametrize("arq", ARQUITETURAS)
def test_cada_arquitetura_treina_e_devolve_probabilidades(arq) -> None:
    rng = np.random.default_rng(0)
    X = rng.integers(0, 2, (64, 2 * 10 * 8)).astype(np.float32)
    y = rng.integers(0, 2, 64)
    m = NeuralBitClassifier(arquitetura=arq, blocos=2, epocas=1, lote=16).fit(X, y)
    p = m.predict_proba(X)
    assert p.shape == (64, 2) and np.allclose(p.sum(axis=1), 1, atol=1e-5)


@pytest.mark.parametrize("arq", ["ResNet_Gohr", "CNN2D_bits"])
def test_rede_aprende_xor_entre_blocos_que_a_regressao_logistica_nao_aprende(arq) -> None:
    """Rótulo = XOR do bit 0 do byte 3 dos dois blocos. Linearmente impossível.

    Com 3.000 exemplos de treino nenhuma das redes aprende (medido: 52%); com
    12.000 as quatro chegam a 100%. Os experimentos reais treinam com ~38 mil.
    """
    rng = np.random.default_rng(1)
    n, L = 15000, 10
    X = rng.integers(0, 2, (n, 2 * L * 8)).astype(np.float32)
    y = (X[:, 3 * 8] != X[:, L * 8 + 3 * 8]).astype(int)
    tr, te = slice(0, 12000), slice(12000, None)
    lr = LogisticRegression(max_iter=2000).fit(X[tr], y[tr])
    rede = NeuralBitClassifier(arquitetura=arq, blocos=2, epocas=15, seed=7).fit(X[tr], y[tr])
    acc_lr = (lr.predict(X[te]) == y[te]).mean()
    acc_rede = (rede.predict(X[te]) == y[te]).mean()
    assert acc_lr < 0.6, acc_lr
    assert acc_rede > 0.95, acc_rede


def test_hibrido_e_meta_treinam_e_devolvem_probabilidades() -> None:
    rng = np.random.default_rng(2)
    X = rng.integers(0, 2, (90, 2 * 10 * 8)).astype(np.float32)
    y = rng.integers(0, 2, 90)
    for m in (HibridoD(blocos=2, epocas=1), _meta_f(seed=7, blocos=2, epocas=1)):
        p = m.fit(X, y).predict_proba(X)
        assert p.shape == (90, 2) and np.allclose(p.sum(axis=1), 1, atol=1e-5)


def test_registro_tem_os_caminhos_b_c_d_f_e_nao_tem_transformer() -> None:
    nomes = set(build_neural_models(seed=7, blocos=1))
    assert {"CNN1D_bytes", "CNN2D_bits", "Hibrido_D", "Meta_F", "ResNet_Gohr", "MLP_Shen"} <= nomes
    assert not any("Transformer" in n for n in nomes)
