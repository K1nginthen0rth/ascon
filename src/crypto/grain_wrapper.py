"""
Wrapper Python para Grain-128AEAD (implementação de referência C) via cffi.

Interface pública idêntica a AsconAEAD128/GiftCOFB:
    Grain128AEAD  — classe principal (encrypt / decrypt / validate_kat)
    AuthenticationError — re-exportada de ascon_wrapper

Compilação do backend: executar build_grain.bat (Windows/MSVC) ou
    python src/crypto/_grain_cffi_build.py  (com compilador C disponível)

Diferença estrutural vs Ascon-AEAD128/GIFT-COFB: nonce de 96 bits (12
bytes, não 16) e tag de 64 bits (8 bytes, não 16) — cifra de fluxo
(LFSR+NFSR), não cifra de bloco/esponja. `len(ciphertext) = len(plaintext)
+ 8`, não `+ 16`.
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
        import _grain_ref  # noqa: PLC0415
        return _grain_ref
    except ImportError:
        return None


def _load_cffi_module():
    mod = _try_import()
    if mod is not None:
        return mod

    build_script = _CRYPTO_DIR / "_grain_cffi_build.py"
    if not build_script.exists():
        raise ImportError(
            f"Script de build não encontrado: {build_script}\n"
            "Execute build_grain.bat (Windows) para compilar a extensão."
        )

    spec = importlib.util.spec_from_file_location("_grain_cffi_build", build_script)
    if spec is None or spec.loader is None:
        raise ImportError("Não foi possível carregar o script de build cffi.")

    builder = importlib.util.module_from_spec(spec)

    # exec_module tem de ficar DENTRO do try: as fontes C de referência são
    # gitignored e o script de build resolve os caminhos no nível de módulo, então
    # num clone limpo o FileNotFoundError escapava cru em vez do ImportError com
    # instruções. Achado na auditoria criptográfica de 2026-08-24.
    try:
        spec.loader.exec_module(builder)  # type: ignore[union-attr]
        builder.build(verbose=True)
    except Exception as exc:
        raise ImportError(
            f"Falha ao compilar extensão Grain-128AEAD via cffi: {exc}\n\n"
            "Windows: execute build_grain.bat com MSVC x64 no PATH.\n"
            "Manual: python src/crypto/_grain_cffi_build.py"
            "\n"
            "Se a árvore C de referência estiver ausente (são gitignored),\n"
            "restaure-a nos pinos: python scripts/vendor_sources.py --fetch"
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
class Grain128AEAD:
    """
    Wrapper Python para Grain-128AEAD (NIST LWC finalist).

    Grain-128AEAD é uma cifra de fluxo (LFSR+NFSR), não uma cifra de
    bloco/esponja como Ascon/GIFT-COFB — a diferença estrutural mais
    relevante para o experimento é que o nonce tem 96 bits (12 bytes) e a
    tag tem 64 bits (8 bytes), contra 128/128 bits nos outros três
    algoritmos. `len(ciphertext) = len(plaintext) + 8`.

    Interface idêntica a AsconAEAD128/GiftCOFB — implementa a API SUPERCOP
    crypto_aead_encrypt / crypto_aead_decrypt.

    Args:
        impl: Implementação C a utilizar. Valores aceitos: "ref".

    Raises:
        ValueError: Se impl não for suportado.
        ImportError: Se a extensão C não puder ser carregada.

    Example:
        >>> cipher = Grain128AEAD()
        >>> key   = bytes(range(16))
        >>> nonce = bytes(range(12))
        >>> ct    = cipher.encrypt(key, nonce, b"hello", b"header")
        >>> cipher.decrypt(key, nonce, ct, b"header")
        b'hello'
    """

    KEYBYTES: int = 16
    NPUBBYTES: int = 12
    ABYTES: int = 8

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
        Cifra plaintext com Grain-128AEAD e retorna ciphertext || tag.

        Args:
            key: Chave de 16 bytes.
            nonce: Nonce de 12 bytes (deve ser único por chave).
            plaintext: Mensagem em claro (qualquer tamanho, inclusive vazio).
            associated_data: Dados autenticados não cifrados (padrão: b"").

        Returns:
            bytes de comprimento len(plaintext) + 8 (tag de 8 bytes).

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
        Decifra ciphertext com Grain-128AEAD e verifica a tag.

        Args:
            key: Chave de 16 bytes.
            nonce: Nonce de 12 bytes.
            ciphertext: ciphertext || tag (mínimo 8 bytes = só a tag).
            associated_data: Dados autenticados não cifrados (padrão: b"").

        Returns:
            Plaintext decifrado.

        Raises:
            ValueError: Se key/nonce tiverem tamanho incorreto ou
                        ciphertext for menor que ABYTES (8 bytes).
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
                "Verificação da tag Grain-128AEAD falhou. "
                "Chave, nonce, AD ou ciphertext incorretos."
            )
        return bytes(ffi.buffer(m_buf, int(mlen_out[0])))

    def validate_kat(
        self, kat_path: str | Path
    ) -> tuple[int, int, list[int]]:
        """
        Valida todos os vetores KAT oficiais contra a implementação C.

        Args:
            kat_path: Caminho para LWC_AEAD_KAT_128_96.txt.

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
            "algo": "Grain-128AEAD",
            "standard": "NIST LWC finalist",
            "crypto_version": "grain128aead-nist-ref",
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
        """SHA256 do binário carregado, para rastreabilidade no manifesto."""
        patterns = ["_grain_ref*.pyd", "_grain_ref*.so", "_grain_ref*.dylib"]
        # Preferimos o __file__ do módulo JÁ IMPORTADO: com dois builds para
        # ABIs diferentes de Python convivendo em src/crypto/, o glob devolvia
        # o que o sistema de arquivos listasse primeiro, e o manifesto do
        # dataset — que é registro de proveniência — passava a depender da
        # ordem de listagem. Achado na auditoria criptográfica de 2026-08-24.
        carregado = getattr(self._mod, "__file__", None)
        if carregado and Path(carregado).is_file():
            return hashlib.sha256(Path(carregado).read_bytes()).hexdigest()

        hits = sorted(h for pat in patterns for h in _CRYPTO_DIR.glob(pat))
        if len(hits) == 1:
            return hashlib.sha256(hits[0].read_bytes()).hexdigest()
        if len(hits) > 1:
            # nunca escolher em silêncio: o valor vai para o manifesto
            return "ambiguo:" + ",".join(h.name for h in hits)
        return "unknown"
