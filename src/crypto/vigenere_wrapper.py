"""
Wrapper Vigenere-XOR (cifra classica) — CONTROLE POSITIVO do pipeline ML.

Cifra de Vigenere implementada como XOR ciclico com chave curta repetida.
Chave efetiva de 25 bits — codificada em 4 bytes, mas apenas os 25 bits
menores do valor sao usados. Essa configuracao preserva a ideia de um
controle de chave fraca e introduz periodicidade detectavel no criptograma.
NAO e' algoritmo LWC; existe apenas para verificar que o pipeline detecta
sinal evidente.

NUNCA usar em producao.
"""
from __future__ import annotations


class VigenereWrapper:
    """
    Cifra de Vigenere com chave curta repetida.

    Interface compativel com os outros wrappers do projeto.
    Implementacao Python pura (nao usa cffi nem C).

    Funcionamento:
        - Chave de 25 bits efetivos codificada em 4 bytes
        - XOR de cada byte do plaintext com o byte correspondente
          da chave ciclicamente repetida
        - CT[i] = PT[i] XOR key[i % 4]
        - Sem nonce, sem tag, sem autenticacao (cifra classica)

    Por que 25 bits:
        - Chave curta e limitada em entropia para manter o controle fraco
        - Ciclo de 4 bytes ainda produz periodicidade detectavel
        - Alta probabilidade de sinais estatisticos claros em CT
    """

    KEY_BITS: int = 25
    KEY_SIZE: int = 4   # bytes de input necessarios para codificar 25 bits
    KEYBYTES: int = 4   # alias para compatibilidade com outros wrappers
    KEY_MASK: int = (1 << KEY_BITS) - 1
    NPUBBYTES: int = 0  # Vigenere nao usa nonce
    ABYTES: int = 0     # Vigenere nao autentica

    _SUPPORTED_IMPLS: tuple[str, ...] = ("python",)

    def __init__(self, impl: str = "python") -> None:
        if impl not in self._SUPPORTED_IMPLS:
            raise ValueError(
                f"impl={impl!r} nao suportado. Opcoes: {self._SUPPORTED_IMPLS}"
            )
        self.impl = impl

    # ------------------------------------------------------------------

    def _normalize_key(self, key: bytes) -> bytes:
        if len(key) < self.KEY_SIZE:
            raise ValueError(
                f"Key must be at least {self.KEY_SIZE} bytes; got {len(key)}."
            )
        raw = int.from_bytes(key[:self.KEY_SIZE], "little") & self.KEY_MASK
        return raw.to_bytes(self.KEY_SIZE, "little")

    def encrypt(
        self,
        key: bytes,
        nonce: bytes,
        plaintext: bytes,
        associated_data: bytes = b"",
    ) -> bytes:
        """
        Cifra com XOR ciclico: CT[i] = PT[i] XOR key[i % 4].

        Aceita qualquer tamanho de key >= 4 e considera apenas os 25 bits
        menos significativos (os bits superiores do quarto byte sao ignorados).
        nonce e associated_data sao ignorados (Vigenere nao os usa).
        """
        k = self._normalize_key(key)
        return bytes(b ^ k[i % self.KEY_SIZE] for i, b in enumerate(plaintext))

    def decrypt(
        self,
        key: bytes,
        nonce: bytes,
        ciphertext: bytes,
        associated_data: bytes = b"",
    ) -> bytes:
        """XOR e' sua propria inversa: decrypt == encrypt."""
        return self.encrypt(key, nonce, ciphertext, associated_data)

    @property
    def metadata(self) -> dict[str, object]:
        """Metadados para rastreabilidade nos manifests."""
        return {
            "algo":           "Vigenere-XOR",
            "standard":       "Classical (XOR with 25-bit repeating key)",
            "crypto_version": "n/a",
            "impl":           self.impl,
            "backend":        "python-pure",
            "binary_sha256":  "n/a",
            "key_bytes":      self.KEY_SIZE,
            "nonce_bytes":    self.NPUBBYTES,
            "tag_bytes":      self.ABYTES,
            "note": (
                "CONTROLE POSITIVO — cifra classica fraca, chave efetiva de 25 bits "
                "codificada em 4 bytes. NAO e' algoritmo LWC."
            ),
        }
