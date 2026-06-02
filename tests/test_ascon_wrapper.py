"""
Testes pytest para src/crypto/ascon_wrapper.py.

Execução:
    pytest tests/test_ascon_wrapper.py -v

Cobertura:
    - Roundtrip encrypt/decrypt com dados arbitrários
    - Validação KAT oficial NIST (todos os 1089 vetores)
    - Rejeição com chave errada
    - Rejeição com nonce errado
    - Rejeição com ciphertext adulterado (1 bit)
    - Plaintext vazio (CT = apenas tag de 16 bytes)
    - AD vazio
    - Validação de tamanho de key e nonce
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.crypto.ascon_wrapper import AsconAEAD128, AuthenticationError

# ---------------------------------------------------------------------------
# Constantes de teste
# ---------------------------------------------------------------------------
_KEY = bytes(range(16))           # 0x00 … 0x0F
_NONCE = bytes(range(16, 32))     # 0x10 … 0x1F
_KAT_PATH = Path(__file__).parent.parent / "ascon-c" / "LWC_AEAD_KAT_128_128.txt"


# ---------------------------------------------------------------------------
# Fixture: instância compartilhada (compila cffi uma única vez por sessão)
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def ascon() -> AsconAEAD128:
    """Instância de AsconAEAD128 reutilizada em todos os testes do módulo."""
    return AsconAEAD128(impl="ref")


# ---------------------------------------------------------------------------
# Testes funcionais
# ---------------------------------------------------------------------------

def test_encrypt_decrypt_roundtrip(ascon: AsconAEAD128) -> None:
    """encrypt + decrypt com dados arbitrários deve retornar o plaintext original."""
    pt = b"Mensagem de teste Ascon-AEAD128"
    ad = b"header-autenticado"
    ct = ascon.encrypt(_KEY, _NONCE, pt, ad)
    recovered = ascon.decrypt(_KEY, _NONCE, ct, ad)
    assert recovered == pt


def test_kat_validation_passes(ascon: AsconAEAD128) -> None:
    """Todos os vetores KAT oficiais NIST devem passar."""
    assert _KAT_PATH.exists(), f"Arquivo KAT não encontrado: {_KAT_PATH}"
    total, passed, failed = ascon.validate_kat(_KAT_PATH)
    assert total > 0, "Nenhum vetor KAT encontrado no arquivo."
    assert failed == [], (
        f"KAT falhou em {len(failed)}/{total} vetores. "
        f"Primeiros falhos: {failed[:10]}"
    )
    assert passed == total


def test_wrong_key_fails_decrypt(ascon: AsconAEAD128) -> None:
    """Decrypt com chave errada deve levantar AuthenticationError."""
    ct = ascon.encrypt(_KEY, _NONCE, b"segredo", b"")
    wrong_key = bytes([0xFF] * 16)
    with pytest.raises(AuthenticationError):
        ascon.decrypt(wrong_key, _NONCE, ct, b"")


def test_wrong_nonce_fails_decrypt(ascon: AsconAEAD128) -> None:
    """Decrypt com nonce errado deve levantar AuthenticationError."""
    ct = ascon.encrypt(_KEY, _NONCE, b"segredo", b"")
    wrong_nonce = bytes([0xFF] * 16)
    with pytest.raises(AuthenticationError):
        ascon.decrypt(_KEY, wrong_nonce, ct, b"")


def test_tampered_ciphertext_fails(ascon: AsconAEAD128) -> None:
    """Flip de 1 bit no ciphertext deve falhar a autenticação."""
    pt = b"dado original"
    ct = bytearray(ascon.encrypt(_KEY, _NONCE, pt, b""))
    ct[0] ^= 0x01  # flip bit 0 do primeiro byte
    with pytest.raises(AuthenticationError):
        ascon.decrypt(_KEY, _NONCE, bytes(ct), b"")


def test_tampered_tag_fails(ascon: AsconAEAD128) -> None:
    """Flip de 1 bit na tag deve falhar a autenticação."""
    pt = b"dado original"
    ct = bytearray(ascon.encrypt(_KEY, _NONCE, pt, b""))
    ct[-1] ^= 0x80  # flip bit na tag (último byte)
    with pytest.raises(AuthenticationError):
        ascon.decrypt(_KEY, _NONCE, bytes(ct), b"")


def test_empty_plaintext(ascon: AsconAEAD128) -> None:
    """PT vazio é válido. CT deve ter exatamente ABYTES (16 bytes = só tag)."""
    ct = ascon.encrypt(_KEY, _NONCE, b"", b"")
    assert len(ct) == AsconAEAD128.ABYTES, (
        f"CT com PT vazio deve ter {AsconAEAD128.ABYTES} bytes; "
        f"obteve {len(ct)}."
    )
    pt = ascon.decrypt(_KEY, _NONCE, ct, b"")
    assert pt == b""


def test_empty_ad(ascon: AsconAEAD128) -> None:
    """AD vazio é válido. Encrypt/decrypt devem funcionar normalmente."""
    pt = b"dados sem AD"
    ct = ascon.encrypt(_KEY, _NONCE, pt, b"")
    recovered = ascon.decrypt(_KEY, _NONCE, ct, b"")
    assert recovered == pt


def test_ad_mismatch_fails_decrypt(ascon: AsconAEAD128) -> None:
    """Decrypt com AD diferente do usado em encrypt deve falhar."""
    pt = b"mensagem com AD"
    ct = ascon.encrypt(_KEY, _NONCE, pt, b"ad-original")
    with pytest.raises(AuthenticationError):
        ascon.decrypt(_KEY, _NONCE, ct, b"ad-errado")


# ---------------------------------------------------------------------------
# Testes de validação de entrada
# ---------------------------------------------------------------------------

def test_key_size_validation(ascon: AsconAEAD128) -> None:
    """Key != 16 bytes deve levantar ValueError."""
    with pytest.raises(ValueError, match="key deve ter"):
        ascon.encrypt(b"chave_curta", _NONCE, b"test")


def test_nonce_size_validation(ascon: AsconAEAD128) -> None:
    """Nonce != 16 bytes deve levantar ValueError."""
    with pytest.raises(ValueError, match="nonce deve ter"):
        ascon.encrypt(_KEY, b"nonce_curto", b"test")


def test_ciphertext_too_short_raises(ascon: AsconAEAD128) -> None:
    """CT menor que ABYTES (16 bytes) em decrypt deve levantar ValueError."""
    with pytest.raises(ValueError, match="mínimo"):
        ascon.decrypt(_KEY, _NONCE, b"\x00" * 8)


# ---------------------------------------------------------------------------
# Testes de metadados
# ---------------------------------------------------------------------------

def test_metadata_fields(ascon: AsconAEAD128) -> None:
    """metadata deve conter os campos obrigatórios com valores corretos."""
    meta = ascon.metadata
    assert meta["algo"] == "Ascon-AEAD128"
    assert meta["standard"] == "NIST SP 800-232"
    assert meta["key_bytes"] == 16
    assert meta["nonce_bytes"] == 16
    assert meta["tag_bytes"] == 16
    assert meta["backend"] == "cffi"
    assert isinstance(meta["binary_sha256"], str)


def test_impl_invalid_raises() -> None:
    """impl desconhecido deve levantar ValueError na construção."""
    with pytest.raises(ValueError, match="não suportado"):
        AsconAEAD128(impl="invalid_impl")


# ---------------------------------------------------------------------------
# Consistência com o KAT: CT de PT vazio = 16 bytes (vetor Count=1)
# ---------------------------------------------------------------------------

def test_kat_vector_1_empty_pt(ascon: AsconAEAD128) -> None:
    """Vetor Count=1: PT vazio, AD vazio → CT deve ser 16 bytes exatos."""
    from src.crypto.kat_parser import parse_kat_file

    vectors = parse_kat_file(_KAT_PATH)
    v = vectors[0]
    assert v.count == 1
    assert v.pt == b""
    assert v.ad == b""
    assert len(v.ct) == AsconAEAD128.ABYTES

    computed = ascon.encrypt(v.key, v.nonce, v.pt, v.ad)
    assert computed == v.ct, (
        f"Vector 1 falhou:\n  esperado: {v.ct.hex()}\n  obtido:   {computed.hex()}"
    )
