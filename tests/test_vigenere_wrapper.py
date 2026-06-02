"""Testes para src/crypto/vigenere_wrapper.py."""
from __future__ import annotations

import pytest

from src.crypto.vigenere_wrapper import VigenereWrapper

_KEY16 = bytes(range(16))   # Vigenere usa apenas os 4 primeiros bytes (25 bits efetivos)
_KEY4  = b"ABCD"
_NONCE = bytes(16)


@pytest.fixture(scope="module")
def cipher() -> VigenereWrapper:
    return VigenereWrapper()


def test_encrypt_decrypt_roundtrip(cipher: VigenereWrapper) -> None:
    """encrypt seguido de decrypt retorna plaintext original."""
    pt = b"mensagem de teste para Vigenere XOR"
    ct = cipher.encrypt(_KEY16, _NONCE, pt, b"")
    assert cipher.decrypt(_KEY16, _NONCE, ct, b"") == pt


def test_periodicity(cipher: VigenereWrapper) -> None:
    """CT de b'\\x00'*12 com chave b'ABC\\x01' == b'ABC\\x01ABC\\x01ABC\\x01'."""
    key = b"ABC" + bytes([0x01])
    ct = cipher.encrypt(key, _NONCE, b"\x00" * 12, b"")
    assert ct == b"ABC\x01ABC\x01ABC\x01"


def test_xor_is_its_own_inverse(cipher: VigenereWrapper) -> None:
    """encrypt(encrypt(pt)) == pt (XOR involutivo)."""
    pt = b"qualquer texto aqui 1234567890"
    ct = cipher.encrypt(_KEY4, _NONCE, pt, b"")
    assert cipher.encrypt(_KEY4, _NONCE, ct, b"") == pt


def test_same_key_same_ct(cipher: VigenereWrapper) -> None:
    """Mesma key + mesmo PT = mesmo CT (sem nonce, deterministico)."""
    pt = b"identical plaintext here"
    ct1 = cipher.encrypt(_KEY4, _NONCE,           pt, b"")
    ct2 = cipher.encrypt(_KEY4, b"\xff" * 16,     pt, b"ad-A")
    ct3 = cipher.encrypt(_KEY4, b"",              pt, b"")
    assert ct1 == ct2 == ct3


def test_only_low_25_bits_used(cipher: VigenereWrapper) -> None:
    """Chaves que diferem apenas nos bits ignorados produzem o mesmo CT."""
    pt  = b"\x00" * 12
    key1 = b"ABC" + bytes([0x01])
    key2 = b"ABC" + bytes([0x81])  # difere apenas nos bits superiores do quarto byte
    ct1 = cipher.encrypt(key1, _NONCE, pt, b"")
    ct2 = cipher.encrypt(key2, _NONCE, pt, b"")
    assert ct1 == ct2 == b"ABC\x01ABC\x01ABC\x01"


def test_key_too_short_raises(cipher: VigenereWrapper) -> None:
    """Key com < 4 bytes levanta ValueError."""
    with pytest.raises(ValueError, match="at least 4 bytes"):
        cipher.encrypt(b"ABC", _NONCE, b"test", b"")
    with pytest.raises(ValueError, match="at least 4 bytes"):
        cipher.decrypt(b"ABC", _NONCE, b"test", b"")


def test_ct_len_equals_pt_len(cipher: VigenereWrapper) -> None:
    """Vigenere: len(CT) == len(PT) (sem tag, sem padding)."""
    for n in (0, 1, 7, 16, 64, 256, 1024):
        pt = bytes(i % 256 for i in range(n))
        ct = cipher.encrypt(_KEY4, _NONCE, pt, b"")
        assert len(ct) == n


def test_empty_plaintext(cipher: VigenereWrapper) -> None:
    """PT vazio -> CT vazio."""
    assert cipher.encrypt(_KEY4, _NONCE, b"", b"") == b""


def test_metadata_fields(cipher: VigenereWrapper) -> None:
    meta = cipher.metadata
    assert meta["algo"]        == "Vigenere-XOR"
    assert meta["key_bytes"]   == 4
    assert meta["nonce_bytes"] == 0
    assert meta["tag_bytes"]   == 0
    assert "CONTROLE POSITIVO" in meta["note"]


def test_impl_invalid_raises() -> None:
    with pytest.raises(ValueError, match="suportado"):
        VigenereWrapper(impl="ref")
