"""Testes do catálogo de algoritmos do estudo de piso (`floor_algos.py`).

O catálogo é pequeno mas carrega decisões que mudam o significado do resultado:
qual parâmetro conta como rodada, até onde ele vai, e o que acontece com o
segundo parâmetro dos algoritmos que têm dois. Um erro aqui não quebra nada —
só faz o piso medir outra coisa, silenciosamente. Daí os testes.

A propriedade mais importante é a do ponto de controle: com `rounds` no valor
de spec, a construção tem que ser a especificação EXATA. Se o controle não for
o algoritmo de verdade, "o controle deu acaso" não prova nada.
"""
from __future__ import annotations

import pytest

from scripts.reduced_rounds.floor_algos import ALGOS, fracao_da_spec

# Valores de especificação, escritos aqui de novo de propósito: se alguém mudar
# o catálogo por engano, o teste tem que discordar em vez de acompanhar.
SPEC = {
    "gift": dict(max_rounds=40, key=16, nonce=16, tag=16),
    "grain": dict(max_rounds=256, key=16, nonce=12, tag=8),
    "ascon": dict(max_rounds=12, key=16, nonce=16, tag=16),
    "schwaemm": dict(max_rounds=11, key=16, nonce=32, tag=16),
}


def test_catalogo_cobre_os_quatro_finalistas() -> None:
    assert set(ALGOS) == set(SPEC)


@pytest.mark.parametrize("algo", sorted(SPEC))
def test_parametros_batem_com_a_especificacao(algo: str) -> None:
    s, esperado = ALGOS[algo], SPEC[algo]
    assert (s.max_rounds, s.key_bytes, s.nonce_bytes, s.tag_bytes) == (
        esperado["max_rounds"], esperado["key"], esperado["nonce"], esperado["tag"])


@pytest.mark.parametrize("algo", sorted(SPEC))
def test_rejeita_contagem_fora_do_intervalo(algo: str) -> None:
    s = ALGOS[algo]
    for r in (0, -1, s.max_rounds + 1):
        with pytest.raises(ValueError):
            s.cipher(r)


def test_politica_dados_so_vale_para_quem_tem_dois_parametros() -> None:
    for algo in ("gift", "grain"):
        assert ALGOS[algo].dois_parametros is False
        with pytest.raises(ValueError):
            ALGOS[algo].cipher(1, politica="dados")
    for algo in ("ascon", "schwaemm"):
        assert ALGOS[algo].dois_parametros is True


def test_rejeita_politica_desconhecida() -> None:
    with pytest.raises(ValueError):
        ALGOS["ascon"].cipher(4, politica="metade")


def test_fracao_da_spec_e_um_no_ponto_de_controle() -> None:
    for algo, s in ALGOS.items():
        assert fracao_da_spec(algo, s.max_rounds) == pytest.approx(1.0)
        assert fracao_da_spec(algo, 1) == pytest.approx(1.0 / s.max_rounds)


# --- ponto de controle: tem que ser a especificação exata ------------------

def test_ascon_no_ponto_de_controle_e_12_8_e_nao_12_12() -> None:
    """A política `ambos` limita pb a 8, que é o valor de spec do Ascon."""
    from unittest import mock

    chamadas = []
    with mock.patch("scripts.reduced_rounds.build_variant.build_ascon",
                    side_effect=lambda pa, pb: chamadas.append((pa, pb))), \
         mock.patch("scripts.reduced_rounds.reduced_wrapper.ReducedRoundsCipher"):
        ALGOS["ascon"].cipher(12)
        ALGOS["ascon"].cipher(4)
        ALGOS["ascon"].cipher(10)
    assert chamadas == [(12, 8), (4, 4), (10, 8)]


def test_schwaemm_no_ponto_de_controle_e_slim7_big11() -> None:
    from unittest import mock

    chamadas = []
    with mock.patch("scripts.reduced_rounds.build_variant.build_schwaemm",
                    side_effect=lambda slim, big: chamadas.append((slim, big))), \
         mock.patch("scripts.reduced_rounds.reduced_wrapper.ReducedRoundsCipher"):
        ALGOS["schwaemm"].cipher(11)
        ALGOS["schwaemm"].cipher(3)
        ALGOS["schwaemm"].cipher(9)
    assert chamadas == [(7, 11), (3, 3), (7, 9)]


def test_politica_dados_mantem_a_inicializacao_na_spec() -> None:
    from unittest import mock

    ascon, schwaemm = [], []
    with mock.patch("scripts.reduced_rounds.build_variant.build_ascon",
                    side_effect=lambda pa, pb: ascon.append((pa, pb))), \
         mock.patch("scripts.reduced_rounds.build_variant.build_schwaemm",
                    side_effect=lambda slim, big: schwaemm.append((slim, big))), \
         mock.patch("scripts.reduced_rounds.reduced_wrapper.ReducedRoundsCipher"):
        ALGOS["ascon"].cipher(3, politica="dados")
        ALGOS["schwaemm"].cipher(2, politica="dados")
    assert ascon == [(12, 3)]       # pa fica na spec, pb cai
    assert schwaemm == [(2, 11)]    # big fica na spec, slim cai


def test_gift_usa_o_cifrador_de_granularidade_fina() -> None:
    """O piso do GIFT cai abaixo de 5, e o `.pyd` fixsliced só desce de 5 em 5."""
    from scripts.reduced_rounds.gift_pure_cipher import PureGiftCOFB

    c = ALGOS["gift"].cipher(3)
    assert isinstance(c, PureGiftCOFB)
    assert c.rounds == 3
