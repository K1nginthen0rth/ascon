"""
Parser para o formato NIST KAT (Known Answer Test) de algoritmos AEAD.

Formato esperado (um bloco por vetor, separado por linha em branco):

    Count = 1
    Key = 000102030405060708090A0B0C0D0E0F
    Nonce = 000102030405060708090A0B0C0D0E0F
    PT =
    AD =
    CT = B78B4D5A41B71DF8F18A3DEA2F78C1C5

Campos PT e AD podem ser vazios (resultado = b"").
CT inclui ciphertext || tag (tag = 16 bytes para Ascon-AEAD128).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class KATVector:
    """Um vetor KAT do arquivo NIST.

    Attributes:
        count: Índice sequencial do vetor (começa em 1).
        key: Chave de 16 bytes.
        nonce: Nonce de 16 bytes.
        pt: Plaintext (pode ser vazio).
        ad: Associated data (pode ser vazio).
        ct: Ciphertext concatenado com tag de autenticação.
    """

    count: int
    key: bytes
    nonce: bytes
    pt: bytes
    ad: bytes
    ct: bytes


def _hex_to_bytes(s: str) -> bytes:
    """Converte string hex (possivelmente vazia) para bytes."""
    s = s.strip()
    return bytes.fromhex(s) if s else b""


def parse_kat_file(path: str | Path) -> list[KATVector]:
    """
    Parseia o arquivo KAT no formato NIST e retorna lista de vetores.

    Args:
        path: Caminho para o arquivo .txt de KAT
              (ex.: "ascon-c/LWC_AEAD_KAT_128_128.txt").

    Returns:
        Lista de KATVector com todos os vetores do arquivo, em ordem.

    Raises:
        FileNotFoundError: Se o arquivo não existir.
        ValueError: Se um campo obrigatório (Count, Key, Nonce, CT) estiver
                    ausente em algum bloco.

    Example:
        >>> vectors = parse_kat_file("ascon-c/LWC_AEAD_KAT_128_128.txt")
        >>> len(vectors)
        1089
        >>> vectors[0].key.hex()
        '000102030405060708090a0b0c0d0e0f'
        >>> vectors[0].ct.hex()[:8]
        'b78b4d5a'
    """
    path = Path(path)
    lines = path.read_text(encoding="ascii").splitlines()

    vectors: list[KATVector] = []
    current: dict[str, str] = {}

    for line in lines:
        line = line.strip()
        if not line:
            if current:
                vectors.append(_make_vector(current))
                current = {}
            continue
        if " = " in line:
            key, _, value = line.partition(" = ")
            current[key.strip()] = value.strip()

    # Captura último bloco caso o arquivo não termine com linha em branco
    if current:
        vectors.append(_make_vector(current))

    return vectors


def _make_vector(fields: dict[str, str]) -> KATVector:
    """Constrói um KATVector a partir de um dict de campos parsed."""
    required = ("Count", "Key", "Nonce", "CT")
    missing = [f for f in required if f not in fields]
    if missing:
        raise ValueError(
            f"Bloco KAT incompleto — campos faltando: {missing}. "
            f"Count={fields.get('Count', '?')}"
        )
    return KATVector(
        count=int(fields["Count"]),
        key=_hex_to_bytes(fields["Key"]),
        nonce=_hex_to_bytes(fields["Nonce"]),
        pt=_hex_to_bytes(fields.get("PT", "")),
        ad=_hex_to_bytes(fields.get("AD", "")),
        ct=_hex_to_bytes(fields["CT"]),
    )
