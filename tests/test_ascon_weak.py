"""Corretude do gerador de Ascon com p^b reduzido (`src/crypto/ascon_weak.py`).

O único uso deste módulo é gerar dados para o experimento de instância fraca
(ver docstring do módulo). O que importa validar aqui é que `pb_rounds=8`
(o valor oficial) é indistinguível do wrapper C sob teste no resto do
projeto — ou seja, que a única forma de o ciphertext gerado divergir do
"Ascon de verdade" é a redução INTENCIONAL de rodadas, não um bug de
transcrição.
"""
from __future__ import annotations

import random

from src.crypto.ascon_wrapper import AsconAEAD128
from src.crypto.ascon_weak import PB_ROUNDS_OFICIAL, ascon_weak_encrypt


def test_pb_rounds_oficial_bate_com_wrapper_c() -> None:
    a = AsconAEAD128()
    rng = random.Random(20260825)
    for _ in range(40):
        key = bytes(rng.getrandbits(8) for _ in range(16))
        nonce = bytes(rng.getrandbits(8) for _ in range(16))
        pt = bytes(rng.getrandbits(8) for _ in range(rng.randint(0, 200)))
        ad = bytes(rng.getrandbits(8) for _ in range(rng.randint(0, 200)))
        assert ascon_weak_encrypt(key, nonce, pt, ad, PB_ROUNDS_OFICIAL) == a.encrypt(
            key, nonce, pt, ad
        )


def test_reduzir_rounds_muda_o_ciphertext() -> None:
    key = bytes(range(16))
    nonce = bytes(range(16, 32))
    pt = bytes(range(64)) * 4
    oficial = ascon_weak_encrypt(key, nonce, pt, b"", pb_rounds=8)
    for r in (1, 2, 3, 4, 6):
        fraco = ascon_weak_encrypt(key, nonce, pt, b"", pb_rounds=r)
        assert fraco != oficial
        assert len(fraco) == len(oficial)  # ABYTES não muda com as rodadas


def test_pb_rounds_zero_e_identidade_e_vaza_estrutura_do_plaintext() -> None:
    """pb_rounds=0: sem NENHUMA mistura entre blocos, o estado só acumula o
    XOR dos blocos de plaintext (nada mais muda entre um bloco e o
    próximo). Com blocos de plaintext IDÊNTICOS, isso produz um padrão
    periódico de período 2 nos blocos de ciphertext: ct_i = ct_{i-1} XOR
    pt_i, e pt_i constante faz ct_0=ct_2=ct_4..., ct_1=ct_3=ct_5... — só 2
    valores distintos entre 4 blocos, um padrão tão explorável quanto o do
    controle positivo AES-ECB. Com pb_rounds>=1 a permutação já quebra essa
    periodicidade."""
    key = bytes(range(16))
    nonce = bytes(range(16, 32))
    bloco = bytes(range(16))
    pt = bloco * 4  # 4 blocos IDÊNTICOS
    ct0 = ascon_weak_encrypt(key, nonce, pt, b"", pb_rounds=0)
    ct_blocks = [ct0[i:i + 16] for i in range(0, 64, 16)]
    assert len(set(ct_blocks)) <= 2, "pb_rounds=0 deveria produzir período <= 2 nos blocos"
    assert ct_blocks[0] == ct_blocks[2] and ct_blocks[1] == ct_blocks[3]

    ct1 = ascon_weak_encrypt(key, nonce, pt, b"", pb_rounds=1)
    ct1_blocks = [ct1[i:i + 16] for i in range(0, 64, 16)]
    assert len(set(ct1_blocks)) == 4, "1 rodada já deveria quebrar a periodicidade"


def test_rejeita_rounds_fora_do_intervalo() -> None:
    key = bytes(16)
    nonce = bytes(16)
    try:
        ascon_weak_encrypt(key, nonce, b"", b"", pb_rounds=-1)
        assert False, "deveria ter levantado ValueError"
    except ValueError:
        pass
    try:
        ascon_weak_encrypt(key, nonce, b"", b"", pb_rounds=13)
        assert False, "deveria ter levantado ValueError"
    except ValueError:
        pass
