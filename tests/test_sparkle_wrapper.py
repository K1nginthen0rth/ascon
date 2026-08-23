"""
Testes pytest para src/crypto/sparkle_wrapper.py.

Execução:
    pytest tests/test_sparkle_wrapper.py -v

Cobertura:
    - Roundtrip encrypt/decrypt com dados arbitrários
    - Validação KAT oficial (todos os 1089 vetores, do pacote de submissão
      NIST — não autogerados pela mesma implementação sob teste)
    - Rejeição com chave errada
    - Rejeição com nonce errado
    - Rejeição com ciphertext adulterado (corpo e tag)
    - Plaintext vazio (CT = apenas tag de 16 bytes)
    - AD vazio / AD incorreto em decrypt
    - Validação de tamanho de key (16) e nonce (32, o maior do conjunto —
      256 bits, diferente dos outros três algoritmos do projeto)
    - len(CT) = len(PT) + 16
    - Metadados obrigatórios
    - impl inválido
    - Vetor KAT Count=1 (PT vazio, AD vazio)
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.crypto.ascon_wrapper import AuthenticationError
from src.crypto.sparkle_wrapper import Schwaemm256_128

# ---------------------------------------------------------------------------
# Constantes de teste
# ---------------------------------------------------------------------------
_KEY = bytes(range(16))       # 0x00 … 0x0F
_NONCE = bytes(range(32))     # 0x00 … 0x1F (256 bits — o maior nonce do conjunto)
# KAT oficial. Preferimos a cópia VERSIONADA em `data/kat/` — as fontes C
# de referência são gitignored, então num clone limpo o teste falharia por
# arquivo ausente (auditoria de 2026-08-23). Proveniência e SHA-256 em
# `data/kat/README.md`.
_KAT_VERSIONADO = Path(__file__).parent.parent / "data" / "kat" / "LWC_AEAD_KAT_SCHWAEMM256_128.txt"
_KAT_VENDORIZADO = (
    Path(__file__).parent.parent
    / "sparkle" / "crypto_aead" / "schwaemm256128v2" / "LWC_AEAD_KAT_128_256.txt"
)
_KAT_PATH = _KAT_VERSIONADO if _KAT_VERSIONADO.exists() else _KAT_VENDORIZADO


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def cipher() -> Schwaemm256_128:
    """Instância de Schwaemm256_128 reutilizada em todos os testes do módulo."""
    return Schwaemm256_128(impl="ref")


# ---------------------------------------------------------------------------
# Testes funcionais
# ---------------------------------------------------------------------------

def test_encrypt_decrypt_roundtrip(cipher: Schwaemm256_128) -> None:
    pt = "Mensagem de teste Schwaemm256-128".encode()
    ad = b"header-autenticado"
    ct = cipher.encrypt(_KEY, _NONCE, pt, ad)
    assert cipher.decrypt(_KEY, _NONCE, ct, ad) == pt


def test_kat_validation_passes(cipher: Schwaemm256_128) -> None:
    """Todos os 1089 vetores KAT oficiais (submissão NIST) devem passar."""
    assert _KAT_PATH.exists(), f"Arquivo KAT nao encontrado: {_KAT_PATH}"
    total, passed, failed = cipher.validate_kat(_KAT_PATH)
    assert total == 1089, f"Esperava 1089 vetores; encontrou {total}."
    assert failed == [], (
        f"KAT falhou em {len(failed)}/{total} vetores. "
        f"Primeiros falhos: {failed[:10]}"
    )
    assert passed == total


def test_wrong_key_fails_decrypt(cipher: Schwaemm256_128) -> None:
    ct = cipher.encrypt(_KEY, _NONCE, b"segredo", b"")
    with pytest.raises(AuthenticationError):
        cipher.decrypt(bytes([0xFF] * 16), _NONCE, ct, b"")


def test_wrong_nonce_fails_decrypt(cipher: Schwaemm256_128) -> None:
    ct = cipher.encrypt(_KEY, _NONCE, b"segredo", b"")
    with pytest.raises(AuthenticationError):
        cipher.decrypt(_KEY, bytes([0xFF] * 32), ct, b"")


def test_tampered_ciphertext_body_fails(cipher: Schwaemm256_128) -> None:
    ct = bytearray(cipher.encrypt(_KEY, _NONCE, b"dado original", b""))
    ct[0] ^= 0x01
    with pytest.raises(AuthenticationError):
        cipher.decrypt(_KEY, _NONCE, bytes(ct), b"")


def test_tampered_tag_fails(cipher: Schwaemm256_128) -> None:
    ct = bytearray(cipher.encrypt(_KEY, _NONCE, b"dado original", b""))
    ct[-1] ^= 0x80
    with pytest.raises(AuthenticationError):
        cipher.decrypt(_KEY, _NONCE, bytes(ct), b"")


def test_empty_plaintext(cipher: Schwaemm256_128) -> None:
    """PT vazio e valido. CT deve ter exatamente ABYTES (16 bytes = so tag)."""
    ct = cipher.encrypt(_KEY, _NONCE, b"", b"")
    assert len(ct) == Schwaemm256_128.ABYTES, (
        f"CT com PT vazio deve ter {Schwaemm256_128.ABYTES} bytes; obteve {len(ct)}."
    )
    assert cipher.decrypt(_KEY, _NONCE, ct, b"") == b""


def test_empty_ad(cipher: Schwaemm256_128) -> None:
    pt = b"dados sem AD"
    ct = cipher.encrypt(_KEY, _NONCE, pt, b"")
    assert cipher.decrypt(_KEY, _NONCE, ct, b"") == pt


def test_ad_mismatch_fails_decrypt(cipher: Schwaemm256_128) -> None:
    ct = cipher.encrypt(_KEY, _NONCE, b"mensagem", b"ad-original")
    with pytest.raises(AuthenticationError):
        cipher.decrypt(_KEY, _NONCE, ct, b"ad-errado")


def test_ciphertext_length(cipher: Schwaemm256_128) -> None:
    """len(CT) deve ser len(PT) + ABYTES (16) para qualquer tamanho de PT."""
    for pt_len in (0, 1, 15, 16, 17, 100, 1024):
        pt = bytes(i % 256 for i in range(pt_len))
        ct = cipher.encrypt(_KEY, _NONCE, pt, b"")
        assert len(ct) == pt_len + Schwaemm256_128.ABYTES


# ---------------------------------------------------------------------------
# Testes de validacao de entrada
# ---------------------------------------------------------------------------

def test_key_size_validation(cipher: Schwaemm256_128) -> None:
    with pytest.raises(ValueError, match="key deve ter"):
        cipher.encrypt(b"chave_curta", _NONCE, b"test")


def test_nonce_size_validation(cipher: Schwaemm256_128) -> None:
    """Nonce != 32 bytes deve levantar ValueError (Schwaemm256-128 usa 256 bits)."""
    with pytest.raises(ValueError, match="nonce deve ter"):
        cipher.encrypt(_KEY, bytes(range(16)), b"test")


def test_ciphertext_too_short_raises(cipher: Schwaemm256_128) -> None:
    with pytest.raises(ValueError, match=r"16 \(apenas"):
        cipher.decrypt(_KEY, _NONCE, b"\x00" * 8)


# ---------------------------------------------------------------------------
# Testes de metadados
# ---------------------------------------------------------------------------

def test_metadata_fields(cipher: Schwaemm256_128) -> None:
    meta = cipher.metadata
    assert meta["algo"] == "Schwaemm256-128"
    assert meta["key_bytes"] == 16
    assert meta["nonce_bytes"] == 32
    assert meta["tag_bytes"] == 16
    assert meta["backend"] == "cffi"
    assert isinstance(meta["binary_sha256"], str)


def test_impl_invalid_raises() -> None:
    with pytest.raises(ValueError, match="suportado"):
        Schwaemm256_128(impl="opt")


# ---------------------------------------------------------------------------
# Consistencia com o KAT: vetor Count=1 (PT vazio, AD vazio)
# ---------------------------------------------------------------------------

def test_kat_vector_1_empty_pt(cipher: Schwaemm256_128) -> None:
    from src.crypto.kat_parser import parse_kat_file

    vectors = parse_kat_file(_KAT_PATH)
    v = vectors[0]
    assert v.count == 1
    assert v.pt == b""
    assert v.ad == b""
    assert len(v.nonce) == 32
    assert len(v.ct) == Schwaemm256_128.ABYTES

    computed = cipher.encrypt(v.key, v.nonce, v.pt, v.ad)
    assert computed == v.ct, (
        f"Vector 1 falhou:\n  esperado: {v.ct.hex()}\n  obtido:   {computed.hex()}"
    )
