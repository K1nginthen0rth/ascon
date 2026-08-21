"""
CTR_DRBG (NIST SP 800-90A Rev. 1) para geração determinística de material
criptográfico do dataset v2 (chaves + amostragem de plaintext/posição).

*** IMPORTANTE — leitura obrigatória antes de usar ***
Este módulo usa o CTR_DRBG como MECANISMO determinístico (PRNG), não como
gerador de aleatoriedade de segurança. Não há fonte de entropia física: a
"entropia de entrada" exigida pelo padrão é derivada deterministicamente da
seed fixa do projeto via SHA-256. Isso é uso deliberado do *mecanismo* do
padrão (a construção Key/V + AES em modo contador) para obter um PRNG
determinístico e reprodutível que a literatura de segurança não rejeita —
não é uma alegação de segurança real do gerador. Ver
docs/plano_experimento_v2/01_algoritmos_e_dataset.md §1.7.

Configuração: AES-128, SEM função de derivação (no df), SEM resistência a
predição (no prediction resistance) — a configuração mais simples e mais
testada do padrão (SP 800-90A §10.2.1).

Escopo: usado SOMENTE na geração do dataset (chaves, amostragem de
plaintext/posição/nonce). Bootstrap de métricas continua NumPy
(`default_rng(42)`); treino de CNN/Transformer continua `torch.manual_seed`
— não são material criptográfico de teste, e trocar mudaria resultados sem
ganho de rigor.

Referência normativa: NIST SP 800-90A Rev.1, Seção 10.2.1
(CTR_DRBG: Instantiate, Reseed, Generate, Update — caso "no df").
"""
from __future__ import annotations

import hashlib
from typing import Optional

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

# ---------------------------------------------------------------------------
# Constantes do padrão (AES-128, sem função de derivação)
# ---------------------------------------------------------------------------
BLOCKLEN: int = 16                     # bytes — tamanho de bloco do AES (128 bits)
KEYLEN: int = 16                       # bytes — chave do AES-128 (128 bits)
SEEDLEN: int = KEYLEN + BLOCKLEN       # 32 bytes (256 bits) — seedlen p/ AES-128 no-df
MAX_BYTES_PER_REQUEST: int = 2 ** 19 // 8  # 65.536 bytes (Tabela 3, SP 800-90A)
RESEED_INTERVAL: int = 2 ** 48         # requests entre reseeds (Tabela 3)


class CTRDRBGError(Exception):
    """Erro no mecanismo CTR_DRBG (entrada de tamanho inválido, etc.)."""


def _xor_bytes(a: bytes, b: bytes) -> bytes:
    return bytes(x ^ y for x, y in zip(a, b))


def _pad_right_zeros(data: bytes, length: int) -> bytes:
    if len(data) > length:
        raise CTRDRBGError(f"dado excede o comprimento máximo de {length} bytes.")
    return data + b"\x00" * (length - len(data))


def _encrypt_block(key: bytes, block: bytes) -> bytes:
    """AES-128-ECB de um único bloco de 16 bytes (primitiva do CTR_DRBG)."""
    cipher = Cipher(algorithms.AES(key), modes.ECB())
    enc = cipher.encryptor()
    return enc.update(block) + enc.finalize()


def _increment_counter(v: bytes) -> bytes:
    """V = (V + 1) mod 2^blocklen, big-endian, conforme SP 800-90A."""
    as_int = (int.from_bytes(v, "big") + 1) % (2 ** (BLOCKLEN * 8))
    return as_int.to_bytes(BLOCKLEN, "big")


def _ctr_drbg_update(key: bytes, v: bytes, provided_data: bytes) -> tuple[bytes, bytes]:
    """
    CTR_DRBG_Update (SP 800-90A §10.2.1.2). Função pura: recebe (Key, V,
    provided_data) — provided_data deve ter exatamente SEEDLEN bytes — e
    retorna o novo (Key, V). Não depende de estado externo.
    """
    if len(provided_data) != SEEDLEN:
        raise CTRDRBGError(
            f"provided_data deve ter exatamente {SEEDLEN} bytes; "
            f"recebeu {len(provided_data)}."
        )
    temp = b""
    while len(temp) < SEEDLEN:
        v = _increment_counter(v)
        temp += _encrypt_block(key, v)
    temp = temp[:SEEDLEN]
    temp = _xor_bytes(temp, provided_data)
    new_key = temp[:KEYLEN]
    new_v = temp[KEYLEN:]
    return new_key, new_v


class CTRDRBGCore:
    """
    Implementação de baixo nível do CTR_DRBG (AES-128, sem função de
    derivação, sem resistência a predição), fiel ao texto normativo do
    SP 800-90A §10.2.1. Opera diretamente sobre bytes já nos tamanhos
    exatos exigidos pelo padrão (sem derivar entropia de uma seed inteira)
    — é a camada validada bit-a-bit contra os vetores CAVP (ver
    tests/test_ctr_drbg.py). Uso de alto nível: classe `CTRDRBG` abaixo.
    """

    def __init__(
        self,
        entropy_input: bytes,
        nonce: bytes = b"",
        personalization_string: bytes = b"",
    ) -> None:
        """
        Instantiate (SP 800-90A §10.2.1.3.1, caso no df).

        Args:
            entropy_input: exatamente SEEDLEN (32) bytes. Sem função de
                derivação, o padrão exige que a entropia de entrada já
                venha no tamanho do seed — nenhuma expansão é feita aqui.
            nonce: não utilizado nesta configuração (sem DF, a entropia de
                entrada já cobre sozinha o seedlen; mantido no construtor
                só por fidelidade de assinatura ao padrão/aos vetores CAVP,
                que listam o campo mesmo quando vazio).
            personalization_string: até SEEDLEN bytes; preenchido com
                zeros à direita se mais curto, XORado com entropy_input.
        """
        if len(entropy_input) != SEEDLEN:
            raise CTRDRBGError(
                f"entropy_input deve ter exatamente {SEEDLEN} bytes "
                f"(seedlen, sem função de derivação); recebeu "
                f"{len(entropy_input)}."
            )
        del nonce  # não usado no caso no-df; parâmetro mantido por clareza
        seed_material = _xor_bytes(
            entropy_input, _pad_right_zeros(personalization_string, SEEDLEN)
        )
        key = b"\x00" * KEYLEN
        v = b"\x00" * BLOCKLEN
        self._key, self._v = _ctr_drbg_update(key, v, seed_material)
        self._reseed_counter = 1

    def reseed(self, entropy_input: bytes, additional_input: bytes = b"") -> None:
        """Reseed (SP 800-90A §10.2.1.4.1, caso no df)."""
        if len(entropy_input) != SEEDLEN:
            raise CTRDRBGError(
                f"entropy_input de reseed deve ter exatamente {SEEDLEN} bytes; "
                f"recebeu {len(entropy_input)}."
            )
        seed_material = _xor_bytes(
            entropy_input, _pad_right_zeros(additional_input, SEEDLEN)
        )
        self._key, self._v = _ctr_drbg_update(self._key, self._v, seed_material)
        self._reseed_counter = 1

    def generate(
        self, requested_bytes: int, additional_input: bytes = b""
    ) -> bytes:
        """
        Generate (SP 800-90A §10.2.1.5.1, caso no df).

        Retorna exatamente `requested_bytes` bytes pseudo-aleatórios.
        Requer requested_bytes <= MAX_BYTES_PER_REQUEST (65.536); chamadas
        maiores devem ser fatiadas pela camada de alto nível (`CTRDRBG`).
        """
        if requested_bytes <= 0:
            raise CTRDRBGError("requested_bytes deve ser positivo.")
        if requested_bytes > MAX_BYTES_PER_REQUEST:
            raise CTRDRBGError(
                f"requested_bytes ({requested_bytes}) excede o máximo por "
                f"request do padrão ({MAX_BYTES_PER_REQUEST}); use CTRDRBG "
                "(camada de alto nível), que fationa automaticamente."
            )
        if self._reseed_counter > RESEED_INTERVAL:
            raise CTRDRBGError(
                "reseed_interval excedido — reseed manual necessário "
                "(não deveria ocorrer no volume de uso deste projeto)."
            )

        if additional_input:
            padded_additional = _pad_right_zeros(additional_input, SEEDLEN)
            self._key, self._v = _ctr_drbg_update(
                self._key, self._v, padded_additional
            )
        else:
            padded_additional = b"\x00" * SEEDLEN

        temp = b""
        key, v = self._key, self._v
        while len(temp) < requested_bytes:
            v = _increment_counter(v)
            temp += _encrypt_block(key, v)
        self._v = v
        returned_bits = temp[:requested_bytes]

        self._key, self._v = _ctr_drbg_update(self._key, self._v, padded_additional)
        self._reseed_counter += 1
        return returned_bits


# ---------------------------------------------------------------------------
# Camada de alto nível — API de uso no gerador de dataset
# ---------------------------------------------------------------------------
def _derive_deterministic_entropy(seed: int, label: str = "") -> bytes:
    """
    Deriva os SEEDLEN (32) bytes de "entropia de entrada" deterministicamente
    de um inteiro de seed do projeto, via SHA-256. Documentado como não-
    -entropia real: existe só para instanciar o mecanismo CTR_DRBG de forma
    reprodutível (ver aviso no topo do módulo).
    """
    material = f"ascon-lwc-ctrdrbg:{label}:{seed}".encode("utf-8")
    return hashlib.sha256(material).digest()  # 32 bytes = SEEDLEN


class CTRDRBG:
    """
    Gerador determinístico de material criptográfico do dataset (chaves,
    sorteio de plaintext/posição/corpus), construído sobre o mecanismo
    CTR_DRBG (NIST SP 800-90A, AES-128, sem função de derivação). NÃO é
    fonte de aleatoriedade de segurança — ver aviso no topo do módulo.

    Interface mínima e deliberadamente NÃO compatível com a API completa do
    NumPy — só o necessário para o gerador de dataset.

    Uso:
        drbg = CTRDRBG(seed=42)
        key  = drbg.random_key()          # 16 bytes
        idx  = drbg.randint(0, 1000)      # inteiro uniforme em [0, 1000)
        raw  = drbg.generate(65536)       # bytes crus (fatiado automaticamente
                                           # se > 65.536 bytes por request)
    """

    def __init__(self, seed: int, label: str = "") -> None:
        entropy_input = _derive_deterministic_entropy(seed, label=label)
        self._core = CTRDRBGCore(entropy_input)
        self.seed = seed
        self.label = label

    def generate(self, n_bytes: int) -> bytes:
        """
        Retorna `n_bytes` bytes pseudo-aleatórios, fatiando automaticamente
        em múltiplas chamadas ao mecanismo quando n_bytes excede o limite
        de 65.536 bytes por request do padrão.
        """
        if n_bytes <= 0:
            raise CTRDRBGError("n_bytes deve ser positivo.")
        chunks: list[bytes] = []
        remaining = n_bytes
        while remaining > 0:
            take = min(remaining, MAX_BYTES_PER_REQUEST)
            chunks.append(self._core.generate(take))
            remaining -= take
        return b"".join(chunks)

    def random_key(self, n_bytes: int = 16) -> bytes:
        """Chave criptográfica de n_bytes bytes (padrão: 16 = AES-128/Ascon/GIFT)."""
        return self.generate(n_bytes)

    def randint(self, low: int, high: int) -> int:
        """
        Inteiro uniforme em [low, high) via rejection sampling (sem viés de
        módulo). Usado para sortear posição/índice no corpus de plaintext.
        """
        if high <= low:
            raise CTRDRBGError("high deve ser maior que low.")
        span = high - low
        n_bits = max(1, span.bit_length())
        n_bytes = (n_bits + 7) // 8
        mask = (1 << n_bits) - 1
        while True:
            raw = self.generate(n_bytes)
            candidate = int.from_bytes(raw, "big") & mask
            if candidate < span:
                return low + candidate

    def choice_bool(self, p_true: float) -> bool:
        """
        Sorteio booleano com probabilidade `p_true` de retornar True. Usado
        para a decisão texto/imagem por amostra (ver 01_algoritmos_e_dataset
        §1.5 — sorteio por amostra dentro de cada chave, proporção 80/20).
        """
        if not 0.0 <= p_true <= 1.0:
            raise CTRDRBGError("p_true deve estar em [0, 1].")
        # Resolução de 1/65536 (2 bytes) é suficiente para uma proporção 80/20.
        threshold = int(round(p_true * 65536))
        draw = int.from_bytes(self.generate(2), "big")
        return draw < threshold
