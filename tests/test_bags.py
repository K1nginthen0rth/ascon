"""Testes da agregação por bolsa (`run_gift_floor._bags`).

É a decisão "por dispositivo": o atacante vê N criptogramas da mesma chave e
combina os escores. A combinação é a MÉDIA DO LOG-ODDS, e não um modelo
multi-par, porque Gohr, Leander e Neumann (ePrint 2022/1521) mostraram que os
ganhos alegados por modelos multi-par somem quando comparados contra a
combinação justa de escores independentes.

O que precisa valer:
 - a bolsa só junta amostras da MESMA chave e da MESMA classe verdadeira;
 - a média é no espaço de log-odds, não de probabilidade (são diferentes);
 - rótulos, chaves e escores saem alinhados índice a índice;
 - bolsa que não cabe é ERRO, não array vazio. Antes desta checagem o erro só
   aparecia lá dentro do `report_eval`, como "empty input array" do sklearn,
   sem dizer que a causa era o tamanho da bolsa.
"""
from __future__ import annotations

import numpy as np
import pytest

from scripts.reduced_rounds.run_gift_floor import _bags


def _cenario(n_por_classe: int = 4, chaves: tuple[str, ...] = ("k0", "k1")):
    keys, y = [], []
    for k in chaves:
        for lab in (0, 1):
            keys += [k] * n_por_classe
            y += [lab] * n_por_classe
    n = len(y)
    p1 = np.linspace(0.1, 0.9, n)
    return np.column_stack([1 - p1, p1]), np.array(y), np.array(keys)


@pytest.mark.parametrize("bag,esperado", [(1, 16), (2, 8), (4, 4)])
def test_numero_de_bolsas(bag: int, esperado: int) -> None:
    proba, y, keys = _cenario()
    by, bp, bk = _bags(proba, y, keys, bag)
    assert len(by) == len(bk) == len(bp) == esperado


def test_bolsa_nao_mistura_chave_nem_classe() -> None:
    proba, y, keys = _cenario()
    by, _bp, bk = _bags(proba, y, keys, 4)
    # 2 chaves x 2 classes, uma bolsa cheia cada
    assert sorted(zip(bk.tolist(), by.tolist())) == [
        ("k0", 0), ("k0", 1), ("k1", 0), ("k1", 1)]


def test_media_e_no_espaco_de_log_odds() -> None:
    """Média de log-odds != média de probabilidade; o teste fixa qual é."""
    keys = np.array(["k0"] * 2)
    y = np.array([1, 1])
    p = np.array([0.1, 0.9])
    proba = np.column_stack([1 - p, p])
    _by, bp, _bk = _bags(proba, y, keys, 2)
    # log-odds(0,1) = -log-odds(0,9), média zero, sigmoide(0) = 0,5
    assert bp[0, 1] == pytest.approx(0.5, abs=1e-9)


def test_saidas_ficam_alinhadas_indice_a_indice() -> None:
    proba, y, keys = _cenario(n_por_classe=2)
    by, bp, bk = _bags(proba, y, keys, 2)
    for i in range(len(by)):
        idx = np.where((keys == bk[i]) & (y == by[i]))[0]
        logit = np.log(proba[idx, 1]) - np.log(proba[idx, 0])
        esperado = 1.0 / (1.0 + np.exp(-logit.mean()))
        assert bp[i, 1] == pytest.approx(esperado, abs=1e-9)
        assert bp[i, 0] + bp[i, 1] == pytest.approx(1.0)


def test_bolsa_que_nao_cabe_levanta_em_vez_de_devolver_vazio() -> None:
    proba, y, keys = _cenario(n_por_classe=4)
    for bag in (5, 100):
        with pytest.raises(ValueError, match="não cabe"):
            _bags(proba, y, keys, bag)


@pytest.mark.parametrize("bag", [0, -1, 2.5, "10"])
def test_rejeita_tamanho_de_bolsa_invalido(bag) -> None:
    proba, y, keys = _cenario()
    with pytest.raises(ValueError):
        _bags(proba, y, keys, bag)


def test_resto_descartado_e_anunciado(capsys) -> None:
    """Bolsa que não divide joga fora parte do teste; isso tem que aparecer."""
    proba, y, keys = _cenario(n_por_classe=5)
    _bags(proba, y, keys, 2)   # 5 = 2 bolsas de 2 + 1 de resto, por (chave, classe)
    assert "descartou" in capsys.readouterr().out


def test_chave_sem_uma_das_classes_nao_quebra() -> None:
    keys = np.array(["k0"] * 8 + ["k1"] * 4)
    y = np.array([0] * 4 + [1] * 4 + [0] * 4)      # k1 só tem a classe 0
    p1 = np.linspace(0.1, 0.9, 12)
    by, _bp, bk = _bags(np.column_stack([1 - p1, p1]), y, keys, 4)
    assert sorted(zip(bk.tolist(), by.tolist())) == [("k0", 0), ("k0", 1), ("k1", 0)]
