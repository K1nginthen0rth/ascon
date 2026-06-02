"""
Wrapper AES-128-ECB - controle positivo para validacao do pipeline ML.

CONTROLE POSITIVO: ECB e' um modo INSEGURO. Usado aqui APENAS para verificar
que o pipeline de classificacao consegue distinguir cifras estruturalmente
diferentes (ECB sem nonce vs AEAD com nonce e tag) quando ha sinal real.

NUNCA usar AES-ECB em producao. Modos seguros: GCM, CCM, ChaCha20-Poly1305.

Backend: cryptography (Python puro / OpenSSL via cffi).
"""
from __future__ import annotations

from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


class AES128ECB:
    """
    Wrapper AES-128-ECB com interface compativel com o gerador de datasets.

    Diferencas estruturais vs Ascon-AEAD128 / GIFT-COFB:
      - SEM nonce (parametro nonce e' aceito mas IGNORADO)
      - SEM tag de autenticacao
      - Plaintext PADDED com PKCS7 ate multiplo de 16 bytes
      - len(CT) = len(PT padded)  (NAO len(PT) + 16)
      - Determinismo: mesma chave + mesmo PT -> sempre o mesmo CT

    Args:
        impl: implementacao a usar. Aceito: "python".
    """

    KEYBYTES:  int = 16
    NPUBBYTES: int = 0   # ECB nao usa nonce
    ABYTES:    int = 0   # ECB nao autentica
    BLOCK_BYTES: int = 16

    _SUPPORTED_IMPLS: tuple[str, ...] = ("python",)

    def __init__(self, impl: str = "python") -> None:
        if impl not in self._SUPPORTED_IMPLS:
            raise ValueError(
                f"impl={impl!r} nao suportado. Opcoes: {self._SUPPORTED_IMPLS}"
            )
        self.impl = impl

    # ------------------------------------------------------------------

    def encrypt(
        self,
        key: bytes,
        nonce: bytes,
        plaintext: bytes,
        associated_data: bytes = b"",
    ) -> bytes:
        """
        Cifra com AES-128-ECB e retorna ciphertext (sem tag).

        Args:
            key:             chave de 16 bytes.
            nonce:           IGNORADO (compat com gerador).
            plaintext:       mensagem em claro (qualquer tamanho, inclusive vazio).
            associated_data: IGNORADO (ECB nao autentica).

        Returns:
            ciphertext = AES-ECB(key, PKCS7_pad(plaintext)).
            len(ciphertext) = ((len(plaintext) // 16) + 1) * 16.
        """
        if len(key) != self.KEYBYTES:
            raise ValueError(
                f"key deve ter {self.KEYBYTES} bytes; recebeu {len(key)}."
            )
        # PKCS7 pad (sempre adiciona ao menos 1 byte; PT vazio -> 16 bytes de pad)
        padder      = padding.PKCS7(self.BLOCK_BYTES * 8).padder()
        padded_pt   = padder.update(plaintext) + padder.finalize()
        cipher      = Cipher(algorithms.AES(key), modes.ECB())
        encryptor   = cipher.encryptor()
        return encryptor.update(padded_pt) + encryptor.finalize()

    def decrypt(
        self,
        key: bytes,
        nonce: bytes,
        ciphertext: bytes,
        associated_data: bytes = b"",
    ) -> bytes:
        """
        Decifra ciphertext e remove o padding PKCS7.

        Args:
            key:             chave de 16 bytes.
            nonce:           IGNORADO.
            ciphertext:      multiplo de 16 bytes.
            associated_data: IGNORADO.

        Returns:
            plaintext original.

        Raises:
            ValueError: se key tiver tamanho errado ou ciphertext nao for
                        multiplo de 16, ou se o PKCS7 unpadding falhar.
        """
        if len(key) != self.KEYBYTES:
            raise ValueError(
                f"key deve ter {self.KEYBYTES} bytes; recebeu {len(key)}."
            )
        if len(ciphertext) == 0 or len(ciphertext) % self.BLOCK_BYTES != 0:
            raise ValueError(
                f"ciphertext deve ser multiplo de {self.BLOCK_BYTES} bytes; "
                f"recebeu {len(ciphertext)}."
            )
        cipher    = Cipher(algorithms.AES(key), modes.ECB())
        decryptor = cipher.decryptor()
        padded_pt = decryptor.update(ciphertext) + decryptor.finalize()
        unpadder  = padding.PKCS7(self.BLOCK_BYTES * 8).unpadder()
        return unpadder.update(padded_pt) + unpadder.finalize()

    @property
    def metadata(self) -> dict[str, object]:
        """Metadados para rastreabilidade nos manifests."""
        return {
            "algo":          "AES-128-ECB",
            "standard":      "FIPS 197 (modo ECB)",
            "crypto_version": "cryptography-47.0.0",
            "impl":          self.impl,
            "backend":       "python-cryptography",
            "binary_sha256": "n/a",
            "key_bytes":     self.KEYBYTES,
            "nonce_bytes":   self.NPUBBYTES,
            "tag_bytes":     self.ABYTES,
            "note":          "CONTROLE POSITIVO - ECB e' inseguro, usado apenas para validar pipeline",
        }
