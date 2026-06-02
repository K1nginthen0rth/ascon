"""Testes para src/crypto/aes_ecb_wrapper.py."""
from __future__ import annotations

import pytest

from src.crypto.aes_ecb_wrapper import AES128ECB

_KEY    = bytes(range(16))
_NONCE  = bytes(range(16))   # ECB ignora, mas gerador passa


@pytest.fixture(scope="module")
def cipher() -> AES128ECB:
    return AES128ECB()


def test_encrypt_decrypt_roundtrip(cipher: AES128ECB) -> None:
    pt = b"mensagem de teste AES-ECB"
    ct = cipher.encrypt(_KEY, _NONCE, pt, b"")
    assert cipher.decrypt(_KEY, _NONCE, ct, b"") == pt


def test_ecb_deterministic(cipher: AES128ECB) -> None:
    """Mesma key + mesmo PT -> mesmo CT (sem nonce)."""
    pt = b"hello world block-1"
    ct1 = cipher.encrypt(_KEY, _NONCE, pt, b"")
    ct2 = cipher.encrypt(_KEY, bytes(16), pt, b"")  # nonce diferente
    ct3 = cipher.encrypt(_KEY, b"\xff" * 16, pt, b"")
    # ECB ignora nonce: tudo deve dar o mesmo ciphertext
    assert ct1 == ct2 == ct3


def test_ecb_pattern_preservation(cipher: AES128ECB) -> None:
    """PT com blocos repetidos -> CT com blocos repetidos.

    Esse e' o vazamento classico do ECB e o padrao que o classificador
    deve aprender a detectar.
    """
    pt = b"A" * 32  # dois blocos identicos de 16 bytes
    ct = cipher.encrypt(_KEY, _NONCE, pt, b"")
    # CT eh PT padded (32) + 16 bytes de padding -> 48 bytes
    assert len(ct) == 48
    block0, block1, block2 = ct[0:16], ct[16:32], ct[32:48]
    # Blocos de PT iguais -> blocos de CT iguais
    assert block0 == block1
    # block2 e' o padding, deve ser diferente
    assert block2 != block0


def test_different_keys_different_ct(cipher: AES128ECB) -> None:
    """Chaves diferentes -> CTs diferentes para o mesmo PT."""
    pt = b"mesmo plaintext aqui ok"
    ct1 = cipher.encrypt(_KEY,                 _NONCE, pt, b"")
    ct2 = cipher.encrypt(b"\x01" * 16,         _NONCE, pt, b"")
    assert ct1 != ct2


def test_key_size_validation(cipher: AES128ECB) -> None:
    with pytest.raises(ValueError, match="key deve ter"):
        cipher.encrypt(b"chave_curta", _NONCE, b"test", b"")
    with pytest.raises(ValueError, match="key deve ter"):
        cipher.decrypt(b"chave_curta", _NONCE, b"\x00" * 16, b"")


def test_padding_correct(cipher: AES128ECB) -> None:
    """PT de 7 bytes -> CT de 16 bytes (1 bloco padded)."""
    pt = b"abcdefg"
    ct = cipher.encrypt(_KEY, _NONCE, pt, b"")
    assert len(ct) == 16
    assert cipher.decrypt(_KEY, _NONCE, ct, b"") == pt


def test_empty_plaintext(cipher: AES128ECB) -> None:
    """PT vazio -> CT de 16 bytes (PKCS7 sempre adiciona >= 1 byte)."""
    ct = cipher.encrypt(_KEY, _NONCE, b"", b"")
    assert len(ct) == 16
    assert cipher.decrypt(_KEY, _NONCE, ct, b"") == b""


def test_ct_length_is_multiple_of_16(cipher: AES128ECB) -> None:
    """len(CT) sempre multiplo de 16, independente de len(PT)."""
    for pt_len in (0, 1, 7, 15, 16, 17, 32, 64, 100, 1024):
        pt = bytes(i % 256 for i in range(pt_len))
        ct = cipher.encrypt(_KEY, _NONCE, pt, b"")
        assert len(ct) % 16 == 0
        # CT eh sempre maior que PT (PKCS7 adiciona ao menos 1 byte)
        assert len(ct) > pt_len


def test_decrypt_invalid_ct_length_raises(cipher: AES128ECB) -> None:
    """CT nao-multiplo de 16 deve levantar ValueError."""
    with pytest.raises(ValueError, match="multiplo"):
        cipher.decrypt(_KEY, _NONCE, b"\x00" * 17, b"")


def test_metadata_fields(cipher: AES128ECB) -> None:
    meta = cipher.metadata
    assert meta["algo"]        == "AES-128-ECB"
    assert meta["key_bytes"]   == 16
    assert meta["nonce_bytes"] == 0
    assert meta["tag_bytes"]   == 0
    assert "CONTROLE POSITIVO" in meta["note"]


def test_impl_invalid_raises() -> None:
    with pytest.raises(ValueError, match="suportado"):
        AES128ECB(impl="ref")


def test_nonce_and_ad_ignored(cipher: AES128ECB) -> None:
    """Sanity: nonces e ADs diferentes nao mudam o CT do ECB."""
    pt = b"identical PT here ok"
    ct_a = cipher.encrypt(_KEY, b"\x00" * 16, pt, b"ad-A")
    ct_b = cipher.encrypt(_KEY, b"\xff" * 16, pt, b"ad-B")
    assert ct_a == ct_b
