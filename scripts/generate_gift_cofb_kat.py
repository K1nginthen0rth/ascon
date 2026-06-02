"""
Gera o arquivo KAT (Known Answer Test) para GIFT-COFB no formato NIST LWC.

Padrão NIST genkat: 1089 vetores (mlen 0..32 x adlen 0..32).
  key   = bytes(range(16))
  nonce = bytes(range(16))
  pt    = bytes(range(mlen))
  ad    = bytes(range(adlen))

Saída: data/kat/LWC_AEAD_KAT_GIFTCOFB128_128.txt
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src" / "crypto"))

import _gift_cofb_ref  # noqa: E402

ffi = _gift_cofb_ref.ffi
lib = _gift_cofb_ref.lib

OUT_DIR = REPO_ROOT / "data" / "kat"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_PATH = OUT_DIR / "LWC_AEAD_KAT_GIFTCOFB128_128.txt"

KEY_BYTES   = 16
NONCE_BYTES = 16
TAG_BYTES   = 16

key   = bytes(range(KEY_BYTES))
nonce = bytes(range(NONCE_BYTES))

lines: list[str] = []
count = 0

for mlen in range(33):
    for adlen in range(33):
        count += 1
        pt = bytes(range(mlen))
        ad = bytes(range(adlen))

        ct_buf  = ffi.new(f"unsigned char[{max(mlen + TAG_BYTES, 1)}]")
        clen    = ffi.new("unsigned long long *", 0)

        rc = lib.crypto_aead_encrypt(
            ct_buf, clen,
            pt, mlen,
            ad, adlen,
            ffi.NULL,
            nonce,
            key,
        )
        assert rc == 0, f"encrypt falhou no vetor {count}"

        ct = bytes(ffi.buffer(ct_buf, int(clen[0])))

        lines.append(f"Count = {count}")
        lines.append(f"Key = {key.hex().upper()}")
        lines.append(f"Nonce = {nonce.hex().upper()}")
        lines.append(f"PT = {pt.hex().upper()}")
        lines.append(f"AD = {ad.hex().upper()}")
        lines.append(f"CT = {ct.hex().upper()}")
        lines.append("")

OUT_PATH.write_text("\n".join(lines), encoding="ascii")
print(f"KAT gerado: {OUT_PATH}  ({count} vetores)")
