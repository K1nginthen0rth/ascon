"""
Testes pytest para src/crypto/grain_wrapper.py.

Execução:
    pytest tests/test_grain_wrapper.py -v

Cobertura:
    - Roundtrip encrypt/decrypt com dados arbitrários
    - Validação KAT oficial (todos os 1089 vetores)
    - Rejeição com chave errada
    - Rejeição com nonce errado
    - Rejeição com ciphertext adulterado (corpo e tag)
    - Plaintext vazio (CT = apenas tag de 8 bytes)
    - AD vazio / AD incorreto em decrypt
    - Validação de tamanho de key (16) e nonce (12, diferente dos outros
      três algoritmos do projeto — 96 bits, não 128)
    - len(CT) = len(PT) + 8 (tag de 64 bits, não 128)
    - Metadados obrigatórios
    - impl inválido
    - Vetor KAT Count=1 (PT vazio, AD vazio)
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.crypto.ascon_wrapper import AuthenticationError
from src.crypto.grain_wrapper import Grain128AEAD

# ---------------------------------------------------------------------------
# Constantes de teste
# ---------------------------------------------------------------------------
_KEY = bytes(range(16))       # 0x00 … 0x0F
_NONCE = bytes(range(12))     # 0x00 … 0x0B (96 bits — Grain usa nonce menor)
# KAT oficial. Preferimos a cópia VERSIONADA em `data/kat/` — as fontes C
# de referência são gitignored, então num clone limpo o teste falharia por
# arquivo ausente (auditoria de 2026-08-23). Proveniência e SHA-256 em
# `data/kat/README.md`.
_KAT_VERSIONADO = Path(__file__).parent.parent / "data" / "kat" / "LWC_AEAD_KAT_GRAIN128AEAD.txt"
_KAT_VENDORIZADO = (
    Path(__file__).parent.parent
    / "grain-128aead" / "NIST" / "ref" / "LWC_AEAD_KAT_128_96.txt"
)
_KAT_PATH = _KAT_VERSIONADO if _KAT_VERSIONADO.exists() else _KAT_VENDORIZADO


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def cipher() -> Grain128AEAD:
    """Instância de Grain128AEAD reutilizada em todos os testes do módulo."""
    return Grain128AEAD(impl="ref")


# ---------------------------------------------------------------------------
# Testes funcionais
# ---------------------------------------------------------------------------

def test_encrypt_decrypt_roundtrip(cipher: Grain128AEAD) -> None:
    pt = "Mensagem de teste Grain-128AEAD".encode()
    ad = b"header-autenticado"
    ct = cipher.encrypt(_KEY, _NONCE, pt, ad)
    assert cipher.decrypt(_KEY, _NONCE, ct, ad) == pt


def test_kat_validation_passes(cipher: Grain128AEAD) -> None:
    """Todos os 1089 vetores KAT oficiais devem passar."""
    assert _KAT_PATH.exists(), f"Arquivo KAT nao encontrado: {_KAT_PATH}"
    total, passed, failed = cipher.validate_kat(_KAT_PATH)
    assert total == 1089, f"Esperava 1089 vetores; encontrou {total}."
    assert failed == [], (
        f"KAT falhou em {len(failed)}/{total} vetores. "
        f"Primeiros falhos: {failed[:10]}"
    )
    assert passed == total


def test_wrong_key_fails_decrypt(cipher: Grain128AEAD) -> None:
    ct = cipher.encrypt(_KEY, _NONCE, b"segredo", b"")
    with pytest.raises(AuthenticationError):
        cipher.decrypt(bytes([0xFF] * 16), _NONCE, ct, b"")


def test_wrong_nonce_fails_decrypt(cipher: Grain128AEAD) -> None:
    ct = cipher.encrypt(_KEY, _NONCE, b"segredo", b"")
    with pytest.raises(AuthenticationError):
        cipher.decrypt(_KEY, bytes([0xFF] * 12), ct, b"")


def test_tampered_ciphertext_body_fails(cipher: Grain128AEAD) -> None:
    ct = bytearray(cipher.encrypt(_KEY, _NONCE, b"dado original", b""))
    ct[0] ^= 0x01
    with pytest.raises(AuthenticationError):
        cipher.decrypt(_KEY, _NONCE, bytes(ct), b"")


def test_tampered_tag_fails(cipher: Grain128AEAD) -> None:
    ct = bytearray(cipher.encrypt(_KEY, _NONCE, b"dado original", b""))
    ct[-1] ^= 0x80
    with pytest.raises(AuthenticationError):
        cipher.decrypt(_KEY, _NONCE, bytes(ct), b"")


def test_empty_plaintext(cipher: Grain128AEAD) -> None:
    """PT vazio e valido. CT deve ter exatamente ABYTES (8 bytes = so tag)."""
    ct = cipher.encrypt(_KEY, _NONCE, b"", b"")
    assert len(ct) == Grain128AEAD.ABYTES, (
        f"CT com PT vazio deve ter {Grain128AEAD.ABYTES} bytes; obteve {len(ct)}."
    )
    assert cipher.decrypt(_KEY, _NONCE, ct, b"") == b""


def test_empty_ad(cipher: Grain128AEAD) -> None:
    pt = b"dados sem AD"
    ct = cipher.encrypt(_KEY, _NONCE, pt, b"")
    assert cipher.decrypt(_KEY, _NONCE, ct, b"") == pt


def test_ad_mismatch_fails_decrypt(cipher: Grain128AEAD) -> None:
    ct = cipher.encrypt(_KEY, _NONCE, b"mensagem", b"ad-original")
    with pytest.raises(AuthenticationError):
        cipher.decrypt(_KEY, _NONCE, ct, b"ad-errado")


def test_ciphertext_length(cipher: Grain128AEAD) -> None:
    """len(CT) deve ser len(PT) + ABYTES (8) para qualquer tamanho de PT."""
    for pt_len in (0, 1, 15, 16, 17, 100, 1024):
        pt = bytes(i % 256 for i in range(pt_len))
        ct = cipher.encrypt(_KEY, _NONCE, pt, b"")
        assert len(ct) == pt_len + Grain128AEAD.ABYTES


# ---------------------------------------------------------------------------
# Testes de validacao de entrada
# ---------------------------------------------------------------------------

def test_key_size_validation(cipher: Grain128AEAD) -> None:
    with pytest.raises(ValueError, match="key deve ter"):
        cipher.encrypt(b"chave_curta", _NONCE, b"test")


def test_nonce_size_validation(cipher: Grain128AEAD) -> None:
    """Nonce != 12 bytes deve levantar ValueError (Grain usa 96 bits, nao 128)."""
    with pytest.raises(ValueError, match="nonce deve ter"):
        cipher.encrypt(_KEY, b"nonce_errado_de_16_bytes", b"test")


def test_ciphertext_too_short_raises(cipher: Grain128AEAD) -> None:
    with pytest.raises(ValueError, match=r"8 \(apenas"):
        cipher.decrypt(_KEY, _NONCE, b"\x00" * 4)


# ---------------------------------------------------------------------------
# Testes de metadados
# ---------------------------------------------------------------------------

def test_metadata_fields(cipher: Grain128AEAD) -> None:
    meta = cipher.metadata
    assert meta["algo"] == "Grain-128AEAD"
    assert meta["key_bytes"] == 16
    assert meta["nonce_bytes"] == 12
    assert meta["tag_bytes"] == 8
    assert meta["backend"] == "cffi"
    assert isinstance(meta["binary_sha256"], str)


def test_impl_invalid_raises() -> None:
    with pytest.raises(ValueError, match="suportado"):
        Grain128AEAD(impl="opt32")


# ---------------------------------------------------------------------------
# Consistencia com o KAT: vetor Count=1 (PT vazio, AD vazio)
# ---------------------------------------------------------------------------

def test_kat_vector_1_empty_pt(cipher: Grain128AEAD) -> None:
    from src.crypto.kat_parser import parse_kat_file

    vectors = parse_kat_file(_KAT_PATH)
    v = vectors[0]
    assert v.count == 1
    assert v.pt == b""
    assert v.ad == b""
    assert len(v.nonce) == 12
    assert len(v.ct) == Grain128AEAD.ABYTES

    computed = cipher.encrypt(v.key, v.nonce, v.pt, v.ad)
    assert computed == v.ct, (
        f"Vector 1 falhou:\n  esperado: {v.ct.hex()}\n  obtido:   {computed.hex()}"
    )
