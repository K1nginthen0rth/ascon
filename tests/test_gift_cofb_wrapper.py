"""
Testes pytest para src/crypto/gift_cofb_wrapper.py.

Execução:
    pytest tests/test_gift_cofb_wrapper.py -v

Cobertura:
    - Roundtrip encrypt/decrypt com dados arbitrários
    - Validação KAT (todos os 1089 vetores gerados)
    - Rejeição com chave errada
    - Rejeição com nonce errado
    - Rejeição com ciphertext adulterado (1 bit no corpo e 1 bit na tag)
    - Plaintext vazio (CT = apenas tag de 16 bytes)
    - AD vazio
    - AD incorreto em decrypt
    - Validação de tamanho de key e nonce
    - Metadados obrigatórios
    - impl inválido
    - Vetor KAT Count=1 (PT vazio, AD vazio)
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.crypto.ascon_wrapper import AuthenticationError
from src.crypto.gift_cofb_wrapper import GiftCOFB

# ---------------------------------------------------------------------------
# Constantes de teste
# ---------------------------------------------------------------------------
_KEY   = bytes(range(16))        # 0x00 … 0x0F
_NONCE = bytes(range(16, 32))    # 0x10 … 0x1F
_KAT_PATH = Path(__file__).parent.parent / "data" / "kat" / "LWC_AEAD_KAT_GIFTCOFB128_128.txt"


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def cipher() -> GiftCOFB:
    """Instância de GiftCOFB reutilizada em todos os testes do módulo."""
    return GiftCOFB(impl="opt32")


# ---------------------------------------------------------------------------
# Testes funcionais
# ---------------------------------------------------------------------------

def test_encrypt_decrypt_roundtrip(cipher: GiftCOFB) -> None:
    """encrypt + decrypt com dados arbitrários deve retornar o plaintext original."""
    pt = b"Mensagem de teste GIFT-COFB"
    ad = b"header-autenticado"
    ct = cipher.encrypt(_KEY, _NONCE, pt, ad)
    assert cipher.decrypt(_KEY, _NONCE, ct, ad) == pt


def test_kat_validation_passes(cipher: GiftCOFB) -> None:
    """Todos os 1089 vetores KAT devem passar."""
    assert _KAT_PATH.exists(), f"Arquivo KAT nao encontrado: {_KAT_PATH}"
    total, passed, failed = cipher.validate_kat(_KAT_PATH)
    assert total == 1089, f"Esperava 1089 vetores; encontrou {total}."
    assert failed == [], (
        f"KAT falhou em {len(failed)}/{total} vetores. "
        f"Primeiros falhos: {failed[:10]}"
    )
    assert passed == total


def test_wrong_key_fails_decrypt(cipher: GiftCOFB) -> None:
    """Decrypt com chave errada deve levantar AuthenticationError."""
    ct = cipher.encrypt(_KEY, _NONCE, b"segredo", b"")
    with pytest.raises(AuthenticationError):
        cipher.decrypt(bytes([0xFF] * 16), _NONCE, ct, b"")


def test_wrong_nonce_fails_decrypt(cipher: GiftCOFB) -> None:
    """Decrypt com nonce errado deve levantar AuthenticationError."""
    ct = cipher.encrypt(_KEY, _NONCE, b"segredo", b"")
    with pytest.raises(AuthenticationError):
        cipher.decrypt(_KEY, bytes([0xFF] * 16), ct, b"")


def test_tampered_ciphertext_body_fails(cipher: GiftCOFB) -> None:
    """Flip de 1 bit no corpo do ciphertext deve falhar a autenticacao."""
    ct = bytearray(cipher.encrypt(_KEY, _NONCE, b"dado original", b""))
    ct[0] ^= 0x01
    with pytest.raises(AuthenticationError):
        cipher.decrypt(_KEY, _NONCE, bytes(ct), b"")


def test_tampered_tag_fails(cipher: GiftCOFB) -> None:
    """Flip de 1 bit na tag (ultimo byte) deve falhar a autenticacao."""
    ct = bytearray(cipher.encrypt(_KEY, _NONCE, b"dado original", b""))
    ct[-1] ^= 0x80
    with pytest.raises(AuthenticationError):
        cipher.decrypt(_KEY, _NONCE, bytes(ct), b"")


def test_empty_plaintext(cipher: GiftCOFB) -> None:
    """PT vazio e valido. CT deve ter exatamente ABYTES (16 bytes = so tag)."""
    ct = cipher.encrypt(_KEY, _NONCE, b"", b"")
    assert len(ct) == GiftCOFB.ABYTES, (
        f"CT com PT vazio deve ter {GiftCOFB.ABYTES} bytes; obteve {len(ct)}."
    )
    assert cipher.decrypt(_KEY, _NONCE, ct, b"") == b""


def test_empty_ad(cipher: GiftCOFB) -> None:
    """AD vazio e valido. Encrypt/decrypt devem funcionar normalmente."""
    pt = b"dados sem AD"
    ct = cipher.encrypt(_KEY, _NONCE, pt, b"")
    assert cipher.decrypt(_KEY, _NONCE, ct, b"") == pt


def test_ad_mismatch_fails_decrypt(cipher: GiftCOFB) -> None:
    """Decrypt com AD diferente do usado em encrypt deve falhar."""
    ct = cipher.encrypt(_KEY, _NONCE, b"mensagem", b"ad-original")
    with pytest.raises(AuthenticationError):
        cipher.decrypt(_KEY, _NONCE, ct, b"ad-errado")


def test_ciphertext_length(cipher: GiftCOFB) -> None:
    """len(CT) deve ser len(PT) + ABYTES para qualquer tamanho de PT."""
    for pt_len in (0, 1, 15, 16, 17, 100, 1024):
        pt = bytes(i % 256 for i in range(pt_len))
        ct = cipher.encrypt(_KEY, _NONCE, pt, b"")
        assert len(ct) == pt_len + GiftCOFB.ABYTES


# ---------------------------------------------------------------------------
# Testes de validacao de entrada
# ---------------------------------------------------------------------------

def test_key_size_validation(cipher: GiftCOFB) -> None:
    """Key != 16 bytes deve levantar ValueError."""
    with pytest.raises(ValueError, match="key deve ter"):
        cipher.encrypt(b"chave_curta", _NONCE, b"test")


def test_nonce_size_validation(cipher: GiftCOFB) -> None:
    """Nonce != 16 bytes deve levantar ValueError."""
    with pytest.raises(ValueError, match="nonce deve ter"):
        cipher.encrypt(_KEY, b"nonce_curto", b"test")


def test_ciphertext_too_short_raises(cipher: GiftCOFB) -> None:
    """CT menor que ABYTES em decrypt deve levantar ValueError."""
    with pytest.raises(ValueError, match="8 bytes"):
        cipher.decrypt(_KEY, _NONCE, b"\x00" * 8)


# ---------------------------------------------------------------------------
# Testes de metadados
# ---------------------------------------------------------------------------

def test_metadata_fields(cipher: GiftCOFB) -> None:
    """metadata deve conter os campos obrigatorios com valores corretos."""
    meta = cipher.metadata
    assert meta["algo"] == "GIFT-COFB"
    assert meta["key_bytes"] == 16
    assert meta["nonce_bytes"] == 16
    assert meta["tag_bytes"] == 16
    assert meta["backend"] == "cffi"
    assert isinstance(meta["binary_sha256"], str)


def test_impl_invalid_raises() -> None:
    """impl desconhecido deve levantar ValueError na construcao."""
    with pytest.raises(ValueError, match="suportado"):
        GiftCOFB(impl="ref")


# ---------------------------------------------------------------------------
# Consistencia com o KAT: vetor Count=1 (PT vazio, AD vazio)
# ---------------------------------------------------------------------------

def test_kat_vector_1_empty_pt(cipher: GiftCOFB) -> None:
    """Vetor Count=1: PT vazio, AD vazio -> CT deve ser 16 bytes exatos."""
    from src.crypto.kat_parser import parse_kat_file

    vectors = parse_kat_file(_KAT_PATH)
    v = vectors[0]
    assert v.count == 1
    assert v.pt == b""
    assert v.ad == b""
    assert len(v.ct) == GiftCOFB.ABYTES

    computed = cipher.encrypt(v.key, v.nonce, v.pt, v.ad)
    assert computed == v.ct, (
        f"Vector 1 falhou:\n  esperado: {v.ct.hex()}\n  obtido:   {computed.hex()}"
    )
