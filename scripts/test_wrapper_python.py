from __future__ import annotations

import secrets
import subprocess
from pathlib import Path


ROOT = Path(r"C:\Users\nycol\Documents\Mestrado\ascon")
WRAPPER_EXE = ROOT / "scripts" / "ascon_cli_ref.exe"

CRYPTO_KEYBYTES = 16
CRYPTO_NPUBBYTES = 16
CRYPTO_ABYTES = 16


def rand_bytes(n: int) -> bytes:
    """Gera n bytes aleatórios."""
    return secrets.token_bytes(n)


def encrypt_with_wrapper(key: bytes, nonce: bytes, ad: bytes, pt: bytes) -> tuple[bytes, bytes]:
    """
    Chama o wrapper CLI do Ascon e retorna (ct, tag).

    A saída do wrapper é ciphertext||tag em hex.
    """
    cmd = [
        str(WRAPPER_EXE),
        key.hex(),
        nonce.hex(),
        ad.hex(),
        pt.hex(),
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=True,
    )

    ct_full = bytes.fromhex(result.stdout.strip())
    ct = ct_full[: len(pt)]
    tag = ct_full[len(pt) : len(pt) + CRYPTO_ABYTES]
    return ct, tag


def main() -> None:
    """Teste mínimo da integração Python -> wrapper -> Ascon."""
    key = rand_bytes(CRYPTO_KEYBYTES)
    seen_nonces: set[bytes] = set()

    for i in range(3):
        nonce = rand_bytes(CRYPTO_NPUBBYTES)
        while nonce in seen_nonces:
            nonce = rand_bytes(CRYPTO_NPUBBYTES)
        seen_nonces.add(nonce)

        len_pt = 16 + secrets.randbelow(256 - 16 + 1)   # 16–256
        len_ad = secrets.randbelow(64 + 1)              # 0–64

        pt = rand_bytes(len_pt)
        ad = rand_bytes(len_ad)

        ct, tag = encrypt_with_wrapper(key, nonce, ad, pt)

        print(f"Amostra {i}")
        print(f"  len_pt = {len_pt}")
        print(f"  len_ad = {len_ad}")
        print(f"  len_ct = {len(ct)}")
        print(f"  len_tag = {len(tag)}")
        print(f"  nonce = {nonce.hex()}")
        print(f"  pt    = {pt.hex()[:64]}{'...' if len(pt) > 32 else ''}")
        print(f"  ad    = {ad.hex()[:64]}{'...' if len(ad) > 32 else ''}")
        print(f"  ct    = {ct.hex()[:64]}{'...' if len(ct) > 32 else ''}")
        print(f"  tag   = {tag.hex()}")
        print()

        assert len(ct) == len_pt, "len(ct) deve ser igual a len_pt"
        assert len(tag) == CRYPTO_ABYTES, "tag deve ter 16 bytes"

    print("Teste Python-wrapper concluído com sucesso.")


if __name__ == "__main__":
    main()