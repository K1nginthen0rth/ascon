"""
Wrapper Python para Ascon-AEAD128 via cffi (implementação de referência C).

O código criptográfico roda inteiramente na extensão C compilada (_ascon_ref).
Na primeira importação, a extensão é compilada automaticamente via cffi se
não estiver presente em src/crypto/.

Interface pública:
    AsconAEAD128  — classe principal (encrypt / decrypt / validate_kat)
    AuthenticationError — levantada quando a tag AEAD é inválida
"""
from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

# ---------------------------------------------------------------------------
# Localização do diretório deste módulo (src/crypto/)
# ---------------------------------------------------------------------------
_CRYPTO_DIR = Path(__file__).parent


# ---------------------------------------------------------------------------
# Exceção pública
# ---------------------------------------------------------------------------
class AuthenticationError(Exception):
    """Levantada quando a verificação da tag Ascon-AEAD falha."""


# ---------------------------------------------------------------------------
# Carregamento / compilação do módulo cffi
# ---------------------------------------------------------------------------
def _ensure_crypto_dir_in_path() -> None:
    """Garante que src/crypto/ está em sys.path para importar _ascon_ref."""
    s = str(_CRYPTO_DIR)
    if s not in sys.path:
        sys.path.insert(0, s)


def _try_import_ascon_ref():
    """Tenta importar _ascon_ref; retorna o módulo ou None."""
    _ensure_crypto_dir_in_path()
    try:
        import _ascon_ref  # noqa: PLC0415
        return _ascon_ref
    except ImportError:
        return None


def _compile_and_import():
    """
    Compila a extensão cffi e retorna o módulo.

    Raises:
        ImportError: Se a compilação falhar ou o compilador não for encontrado.
    """
    build_script = _CRYPTO_DIR / "_ascon_cffi_build.py"
    if not build_script.exists():
        raise ImportError(
            f"Script de build não encontrado: {build_script}\n"
            "Verifique se src/crypto/_ascon_cffi_build.py está presente."
        )

    spec = importlib.util.spec_from_file_location("_ascon_cffi_build", build_script)
    if spec is None or spec.loader is None:
        raise ImportError("Não foi possível carregar o script de build cffi.")

    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)  # type: ignore[union-attr]

    try:
        builder.build(verbose=True)
    except Exception as exc:
        raise ImportError(
            f"Falha ao compilar extensão Ascon via cffi: {exc}\n\n"
            "Certifique-se de que um compilador C compatível com Python está "
            "disponível:\n"
            "  Windows: MSVC (Visual Studio Build Tools)\n"
            "  Linux/Mac: gcc ou clang\n\n"
            "Compilação manual:\n"
            "  python src/crypto/_ascon_cffi_build.py"
        ) from exc

    # Invalida cache de importação (necessário em alguns sistemas)
    importlib.invalidate_caches()

    mod = _try_import_ascon_ref()
    if mod is None:
        raise ImportError(
            "Extensão compilada com sucesso, mas importação falhou. "
            f"Verifique o conteúdo de {_CRYPTO_DIR}."
        )
    return mod


def _load_cffi_module():
    """Retorna o módulo _ascon_ref, compilando se necessário."""
    mod = _try_import_ascon_ref()
    if mod is not None:
        return mod
    return _compile_and_import()


# ---------------------------------------------------------------------------
# Classe principal
# ---------------------------------------------------------------------------
class AsconAEAD128:
    """
    Wrapper Python para Ascon-AEAD128 (Ascon v1.3, NIST SP 800-232).

    Usa a implementação de referência C via cffi. Todo processamento
    criptográfico ocorre no código C compilado — não há reimplementação
    do algoritmo em Python.

    Args:
        impl: Implementação C a utilizar. Valores aceitos: "ref".
              Reservado para expansão futura com "opt32" / "opt64".

    Raises:
        ValueError: Se impl não for suportado.
        ImportError: Se a extensão C não puder ser compilada.

    Example:
        >>> ascon = AsconAEAD128()
        >>> key   = bytes(range(16))
        >>> nonce = bytes(range(16, 32))
        >>> ct    = ascon.encrypt(key, nonce, b"hello", b"header")
        >>> ascon.decrypt(key, nonce, ct, b"header")
        b'hello'
    """

    KEYBYTES: int = 16
    NPUBBYTES: int = 16
    ABYTES: int = 16

    _SUPPORTED_IMPLS: tuple[str, ...] = ("ref",)

    def __init__(self, impl: str = "ref") -> None:
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
        Cifra plaintext com Ascon-AEAD128 e retorna ciphertext || tag.

        Args:
            key: Chave de 16 bytes.
            nonce: Nonce de 16 bytes (deve ser único por chave).
            plaintext: Mensagem em claro (qualquer tamanho, inclusive vazio).
            associated_data: Dados autenticados não cifrados (padrão: b"").

        Returns:
            bytes de comprimento len(plaintext) + 16.
            Os últimos 16 bytes são a tag de autenticação.

        Raises:
            ValueError: Se key ou nonce não tiverem o tamanho correto.
            RuntimeError: Se a função C retornar código de erro não-zero.
        """
        self._check_key_nonce(key, nonce)
        ffi = self._ffi
        lib = self._lib

        ct_len = len(plaintext) + self.ABYTES
        c_buf = ffi.new(f"unsigned char[{max(ct_len, 1)}]")
        clen_out = ffi.new("unsigned long long *", ct_len)

        rc = lib.crypto_aead_encrypt(
            c_buf, clen_out,
            plaintext, len(plaintext),
            associated_data, len(associated_data),
            ffi.NULL,
            nonce,
            key,
        )
        if rc != 0:
            raise RuntimeError(
                f"crypto_aead_encrypt retornou código de erro {rc}."
            )
        return bytes(ffi.buffer(c_buf, int(clen_out[0])))

    def decrypt(
        self,
        key: bytes,
        nonce: bytes,
        ciphertext: bytes,
        associated_data: bytes = b"",
    ) -> bytes:
        """
        Decifra ciphertext com Ascon-AEAD128 e verifica a tag.

        Args:
            key: Chave de 16 bytes.
            nonce: Nonce de 16 bytes.
            ciphertext: ciphertext || tag (mínimo 16 bytes = só a tag).
            associated_data: Dados autenticados não cifrados (padrão: b"").

        Returns:
            Plaintext decifrado.

        Raises:
            ValueError: Se key/nonce tiverem tamanho incorreto ou
                        ciphertext for menor que ABYTES (16 bytes).
            AuthenticationError: Se a tag AEAD for inválida (chave, nonce,
                                 AD ou ciphertext corrompidos/incorretos).
        """
        self._check_key_nonce(key, nonce)
        if len(ciphertext) < self.ABYTES:
            raise ValueError(
                f"ciphertext tem {len(ciphertext)} bytes; "
                f"mínimo é {self.ABYTES} (apenas a tag)."
            )
        ffi = self._ffi
        lib = self._lib

        pt_max = len(ciphertext)  # plaintext <= ciphertext size
        m_buf = ffi.new(f"unsigned char[{max(pt_max, 1)}]")
        mlen_out = ffi.new("unsigned long long *", 0)

        rc = lib.crypto_aead_decrypt(
            m_buf, mlen_out,
            ffi.NULL,
            ciphertext, len(ciphertext),
            associated_data, len(associated_data),
            nonce,
            key,
        )
        if rc != 0:
            raise AuthenticationError(
                "Verificação da tag Ascon falhou. "
                "Chave, nonce, AD ou ciphertext incorretos."
            )
        return bytes(ffi.buffer(m_buf, int(mlen_out[0])))

    def validate_kat(
        self, kat_path: str | Path
    ) -> tuple[int, int, list[int]]:
        """
        Valida todos os vetores KAT oficiais NIST contra a implementação C.

        Para cada vetor, chama encrypt(key, nonce, pt, ad) e compara o
        resultado com o CT esperado. Um vetor falha se os bytes diferirem.

        Args:
            kat_path: Caminho para LWC_AEAD_KAT_128_128.txt.

        Returns:
            Tupla (total, passed, failed_indices) onde:
            - total: número de vetores no arquivo
            - passed: número de vetores que passaram
            - failed_indices: lista de Count dos vetores que falharam

        Example:
            >>> total, passed, failed = ascon.validate_kat(
            ...     "ascon-c/LWC_AEAD_KAT_128_128.txt"
            ... )
            >>> assert passed == total and failed == []
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
        passed = total - len(failed)
        return total, passed, failed

    @property
    def metadata(self) -> dict[str, object]:
        """
        Metadados da instância para rastreabilidade de experimentos.

        Returns:
            Dict com: algo, standard, impl, backend, binary_sha256,
            key_bytes, nonce_bytes, tag_bytes.
        """
        return {
            "algo": "Ascon-AEAD128",
            "standard": "NIST SP 800-232",
            "crypto_version": "1.3.0",
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
        """Retorna SHA256 do binário compilado para rastreabilidade."""
        patterns = ["_ascon_ref*.pyd", "_ascon_ref*.so", "_ascon_ref*.dylib"]
        for pat in patterns:
            hits = list(_CRYPTO_DIR.glob(pat))
            if hits:
                return hashlib.sha256(hits[0].read_bytes()).hexdigest()
        return "unknown"
