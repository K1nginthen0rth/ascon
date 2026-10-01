"""Testes do GIFT-COFB de granularidade fina (`scripts/reduced_rounds/gift_pure_cipher.py`).

O ponto central é o teste de equivalência: com 40 rodadas, a implementação em
Python tem que reproduzir o binário de produção byte a byte, em vários tamanhos
de payload e com dados associados. Se isso valer, a redução de rodadas mexe só
no cifrador de bloco interno, e não no modo COFB em volta.
"""
from __future__ import annotations

import pytest

from scripts.reduced_rounds.gift_pure_cipher import MAX_ROUNDS, PureGiftCOFB
from src.crypto.gift_cofb_wrapper import GiftCOFB

KEY = bytes(range(16))
NONCE = bytes(range(16, 32))


@pytest.mark.parametrize("n_pt", [0, 1, 15, 16, 17, 64, 100])
def test_40_rodadas_bate_com_o_binario_de_producao(n_pt: int) -> None:
    pt = bytes((i * 7 + 3) & 0xFF for i in range(n_pt))
    assert PureGiftCOFB(40).encrypt(KEY, NONCE, pt) == GiftCOFB().encrypt(KEY, NONCE, pt)


@pytest.mark.parametrize("n_ad", [1, 16, 33])
def test_40_rodadas_bate_com_dados_associados(n_ad: int) -> None:
    pt = bytes(range(48))
    ad = bytes((i * 11) & 0xFF for i in range(n_ad))
    assert (PureGiftCOFB(40).encrypt(KEY, NONCE, pt, ad)
            == GiftCOFB().encrypt(KEY, NONCE, pt, ad))


def test_tamanho_do_criptograma_e_payload_mais_tag() -> None:
    pt = bytes(range(64))
    assert len(PureGiftCOFB(7).encrypt(KEY, NONCE, pt)) == len(pt) + 16


@pytest.mark.parametrize("rounds", [1, 2, 3, 4, 5, 6, 13, 39])
def test_rodadas_reduzidas_mudam_o_criptograma(rounds: int) -> None:
    pt = bytes(range(64))
    assert (PureGiftCOFB(rounds).encrypt(KEY, NONCE, pt)
            != PureGiftCOFB(40).encrypt(KEY, NONCE, pt))


def test_cada_numero_de_rodadas_da_um_criptograma_distinto() -> None:
    """Granularidade de 1 rodada: nenhuma contagem colide com outra."""
    pt = bytes(range(64))
    saidas = {r: PureGiftCOFB(r).encrypt(KEY, NONCE, pt) for r in range(1, 13)}
    assert len(set(saidas.values())) == len(saidas)


def test_e_deterministico() -> None:
    pt = bytes(range(32))
    c = PureGiftCOFB(4)
    assert c.encrypt(KEY, NONCE, pt) == c.encrypt(KEY, NONCE, pt)


@pytest.mark.parametrize("rounds", [0, -1, 41, 100, 3.5, "4"])
def test_rejeita_numero_de_rodadas_invalido(rounds) -> None:
    with pytest.raises(ValueError):
        PureGiftCOFB(rounds)


@pytest.mark.parametrize("key,nonce", [
    (bytes(15), NONCE),
    (bytes(17), NONCE),
    (KEY, bytes(15)),
    (KEY, bytes(32)),
])
def test_rejeita_chave_ou_nonce_de_tamanho_errado(key: bytes, nonce: bytes) -> None:
    with pytest.raises(ValueError):
        PureGiftCOFB(10).encrypt(key, nonce, b"abc")


def test_interface_compativel_com_o_wrapper_das_variantes() -> None:
    """Os runners chamam `.encrypt(key, nonce, pt)` sem saber qual classe é."""
    from scripts.reduced_rounds.reduced_wrapper import ReducedRoundsCipher

    for nome in ("encrypt",):
        assert hasattr(PureGiftCOFB(40), nome)
        assert hasattr(ReducedRoundsCipher, nome)
    assert MAX_ROUNDS == 40
