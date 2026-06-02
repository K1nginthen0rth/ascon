"""
Wrapper Python para GIFT-COFB (opt32, NIST LWC Round 2 finalist) via cffi.

Interface pública idêntica a AsconAEAD128:
    GiftCOFB  — classe principal (encrypt / decrypt / validate_kat)
    AuthenticationError — re-exportada de ascon_wrapper

Compilação do backend: executar build_gift_cofb.bat (Windows/MSVC) ou
    python src/crypto/_gift_cofb_cffi_build.py  (com compilador C disponível)
"""
from __future__ import annotations

import hashlib
import importlib
import sys
from pathlib import Path

from .ascon_wrapper import AuthenticationError  # re-usa a mesma exceção

_CRYPTO_DIR = Path(__file__).parent


# ---------------------------------------------------------------------------
# Carregamento do módulo cffi
# ---------------------------------------------------------------------------

def _ensure_path() -> None:
    s = str(_CRYPTO_DIR)
    if s not in sys.path:
        sys.path.insert(0, s)


def _try_import():
    _ensure_path()
    try:
        import _gift_cofb_ref  # noqa: PLC0415
        return _gift_cofb_ref
    except ImportError:
        return None


def _load_cffi_module():
    mod = _try_import()
    if mod is not None:
        return mod

    build_script = _CRYPTO_DIR / "_gift_cofb_cffi_build.py"
    if not build_script.exists():
        raise ImportError(
            f"Script de build não encontrado: {build_script}\n"
            "Execute build_gift_cofb.bat (Windows) para compilar a extensão."
        )

    spec = importlib.util.spec_from_file_location("_gift_cofb_cffi_build", build_script)
    if spec is None or spec.loader is None:
        raise ImportError("Não foi possível carregar o script de build cffi.")

    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)  # type: ignore[union-attr]

    try:
        builder.build(verbose=True)
    except Exception as exc:
        raise ImportError(
            f"Falha ao compilar extensão GIFT-COFB via cffi: {exc}\n\n"
            "Windows: execute build_gift_cofb.bat com MSVC x64 no PATH.\n"
            "Manual: python src/crypto/_gift_cofb_cffi_build.py"
        ) from exc

    importlib.invalidate_caches()
    mod = _try_import()
    if mod is None:
        raise ImportError(
            "Extensão compilada, mas importação falhou. "
            f"Verifique o conteúdo de {_CRYPTO_DIR}."
        )
    return mod


# ---------------------------------------------------------------------------
# Classe principal
# ---------------------------------------------------------------------------

class GiftCOFB:
    """
    Wrapper Python para GIFT-COFB (opt32, NIST LWC Round 2 finalist).

    GIFT-COFB usa GIFT-128 como permutação subjacente com o modo COFB
    (Combined FeedBack). Parâmetros: chave 128 bits, nonce 128 bits, tag 128 bits.

    Interface idêntica a AsconAEAD128 — ambas implementam a API SUPERCOP
    crypto_aead_encrypt / crypto_aead_decrypt.

    Args:
        impl: Implementação C a utilizar. Valores aceitos: "opt32".

    Raises:
        ValueError: Se impl não for suportado.
        ImportError: Se a extensão C não puder ser carregada.

    Example:
        >>> cipher = GiftCOFB()
        >>> key   = bytes(range(16))
        >>> nonce = bytes(range(16))
        >>> ct    = cipher.encrypt(key, nonce, b"hello", b"header")
        >>> cipher.decrypt(key, nonce, ct, b"header")
        b'hello'
    """

    KEYBYTES: int = 16
    NPUBBYTES: int = 16
    ABYTES: int = 16

    _SUPPORTED_IMPLS: tuple[str, ...] = ("opt32",)

    def __init__(self, impl: str = "opt32") -> None:
        if impl not in self._SUPPORTED_IMPLS:
            raise ValueError(
                f"impl={impl!r} não suportado. "
                f"Opções disponíveis: {self._SUPPORTED_IMPLS}"
            )
        self.impl = impl
        self._mod = _load_cffi_module()
        self._ffi = self._mod.ffi
        self._lib = self._mod.lib
        self._binary_sha256 = self._compute_binary_hash()

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def encrypt(
        self,
        key: bytes,
        nonce: bytes,
        plaintext: bytes,
        associated_data: bytes = b"",
    ) -> bytes:
        """
        Cifra plaintext com GIFT-COFB e retorna ciphertext || tag.

        Args:
            key: Chave de 16 bytes.
            nonce: Nonce de 16 bytes (deve ser único por chave).
            plaintext: Mensagem em claro (qualquer tamanho, inclusive vazio).
            associated_data: Dados autenticados não cifrados (padrão: b"").

        Returns:
            bytes de comprimento len(plaintext) + 16.

        Raises:
            ValueError: Se key ou nonce não tiverem o tamanho correto.
            RuntimeError: Se a função C retornar código de erro não-zero.
        """
        self._check_key_nonce(key, nonce)
        ffi = self._ffi
        lib = self._lib

        ct_len = len(plaintext) + self.ABYTES
        c_buf  = ffi.new(f"unsigned char[{max(ct_len, 1)}]")
        clen   = ffi.new("unsigned long long *", ct_len)

        rc = lib.crypto_aead_encrypt(
            c_buf, clen,
            plaintext, len(plaintext),
            associated_data, len(associated_data),
            ffi.NULL,
            nonce,
            key,
        )
        if rc != 0:
            raise RuntimeError(f"crypto_aead_encrypt retornou código de erro {rc}.")
        return bytes(ffi.buffer(c_buf, int(clen[0])))

    def decrypt(
        self,
        key: bytes,
        nonce: bytes,
        ciphertext: bytes,
        associated_data: bytes = b"",
    ) -> bytes:
        """
        Decifra ciphertext com GIFT-COFB e verifica a tag.

        Args:
            key: Chave de 16 bytes.
            nonce: Nonce de 16 bytes.
            ciphertext: ciphertext || tag (mínimo 16 bytes).
            associated_data: Dados autenticados não cifrados (padrão: b"").

        Returns:
            Plaintext decifrado.

        Raises:
            ValueError: Se key/nonce/ciphertext tiverem tamanho incorreto.
            AuthenticationError: Se a tag AEAD for inválida.
        """
        self._check_key_nonce(key, nonce)
        if len(ciphertext) < self.ABYTES:
            raise ValueError(
                f"ciphertext tem {len(ciphertext)} bytes; "
                f"mínimo é {self.ABYTES} (apenas a tag)."
            )
        ffi = self._ffi
        lib = self._lib

        pt_max = len(ciphertext)
        m_buf  = ffi.new(f"unsigned char[{max(pt_max, 1)}]")
        mlen   = ffi.new("unsigned long long *", 0)

        rc = lib.crypto_aead_decrypt(
            m_buf, mlen,
            ffi.NULL,
            ciphertext, len(ciphertext),
            associated_data, len(associated_data),
            nonce,
            key,
        )
        if rc != 0:
            raise AuthenticationError(
                "Verificação da tag GIFT-COFB falhou. "
                "Chave, nonce, AD ou ciphertext incorretos."
            )
        return bytes(ffi.buffer(m_buf, int(mlen[0])))

    def validate_kat(
        self, kat_path: str | Path
    ) -> tuple[int, int, list[int]]:
        """
        Valida todos os vetores KAT contra a implementação C.

        Args:
            kat_path: Caminho para LWC_AEAD_KAT_GIFTCOFB128_128.txt.

        Returns:
            Tupla (total, passed, failed_indices).
        """
        from .kat_parser import parse_kat_file  # noqa: PLC0415

        vectors = parse_kat_file(kat_path)
        failed: list[int] = []

        for vec in vectors:
            try:
                computed = self.encrypt(vec.key, vec.nonce, vec.pt, vec.ad)
                if computed != vec.ct:
                    failed.append(vec.count)
            except Exception:
                failed.append(vec.count)

        total = len(vectors)
        return total, total - len(failed), failed

    @property
    def metadata(self) -> dict[str, object]:
        """Metadados para rastreabilidade de experimentos."""
        return {
            "algo": "GIFT-COFB",
            "standard": "NIST LWC Round 2 finalist",
            "crypto_version": "giftcofb128v1",
            "impl": self.impl,
            "backend": "cffi",
            "binary_sha256": self._binary_sha256,
            "key_bytes": self.KEYBYTES,
            "nonce_bytes": self.NPUBBYTES,
            "tag_bytes": self.ABYTES,
        }

    # ------------------------------------------------------------------
    # Privados
    # ------------------------------------------------------------------

    def _check_key_nonce(self, key: bytes, nonce: bytes) -> None:
        if len(key) != self.KEYBYTES:
            raise ValueError(
                f"key deve ter {self.KEYBYTES} bytes; recebeu {len(key)}."
            )
        if len(nonce) != self.NPUBBYTES:
            raise ValueError(
                f"nonce deve ter {self.NPUBBYTES} bytes; recebeu {len(nonce)}."
            )

    def _compute_binary_hash(self) -> str:
        patterns = ["_gift_cofb_ref*.pyd", "_gift_cofb_ref*.so"]
        for pat in patterns:
            hits = list(_CRYPTO_DIR.glob(pat))
            if hits:
                return hashlib.sha256(hits[0].read_bytes()).hexdigest()
        return "unknown"
