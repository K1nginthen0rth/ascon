"""
Compilador cffi para GIFT-COFB (opt32, NIST LWC Round 2 finalist).

Uso (execução direta, uma vez):
    python src/crypto/_gift_cofb_cffi_build.py

Gera _gift_cofb_ref.cpXXX-win_amd64.pyd (Windows) em src/crypto/.

Requer:
    - gift-cofb/crypto_aead/giftcofb128v1/opt32/  (fontes C originais)
    - src/crypto/_gift_cofb_msvc/  (headers MSVC-compatíveis)
    - cffi instalado, compilador MSVC (Windows)

Nota sobre MSVC: a implementação opt32 usa expressões statement ({ ... }) do
GCC que o MSVC não suporta. Os headers em _gift_cofb_msvc/ são versões
funcionalmente idênticas que usam do { ... } while(0) em vez disso.
"""
from __future__ import annotations

from pathlib import Path

import cffi

# ---------------------------------------------------------------------------
# Caminhos
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OPT32_DIR = REPO_ROOT / "gift-cofb" / "crypto_aead" / "giftcofb128v1" / "opt32"
MSVC_COMPAT_DIR = Path(__file__).parent / "_gift_cofb_msvc"
OUT_DIR = Path(__file__).parent  # src/crypto/

for _p in (OPT32_DIR, MSVC_COMPAT_DIR):
    if not _p.is_dir():
        raise FileNotFoundError(
            f"Diretório não encontrado: {_p}\n"
            "Verifique se gift-cofb/ está na raiz do repositório."
        )

# ---------------------------------------------------------------------------
# Definição cffi — mesma API SUPERCOP/eBACS do Ascon
# ---------------------------------------------------------------------------
ffi = cffi.FFI()

ffi.cdef("""
    int crypto_aead_encrypt(
        unsigned char *c, unsigned long long *clen,
        const unsigned char *m, unsigned long long mlen,
        const unsigned char *ad, unsigned long long adlen,
        const unsigned char *nsec,
        const unsigned char *npub,
        const unsigned char *k
    );

    int crypto_aead_decrypt(
        unsigned char *m, unsigned long long *mlen,
        unsigned char *nsec,
        const unsigned char *c, unsigned long long clen,
        const unsigned char *ad, unsigned long long adlen,
        const unsigned char *npub,
        const unsigned char *k
    );
""")

# O _C_HEADER_SOURCE inclui api.h (do opt32) para CRYPTO_* defines.
# Os headers problemáticos (cofb.h, giftb128.h) são shadowed pelo
# MSVC_COMPAT_DIR que vem primeiro no include_dirs.
_C_HEADER_SOURCE = r"""
#include "api.h"
#include "encrypt.c"
#include "giftb128.c"
"""

# /FI force-includes our MSVC-compatible headers before any source file is
# processed. Their include guards (COFB_H_, GIFT128_H_) prevent the originals
# from being picked up when encrypt.c / giftb128.c do #include "cofb.h" etc.
_force_includes = [
    f"/FI{MSVC_COMPAT_DIR / 'cofb.h'}",
    f"/FI{MSVC_COMPAT_DIR / 'giftb128.h'}",
    f"/FI{MSVC_COMPAT_DIR / 'key_schedule.h'}",
]

ffi.set_source(
    "_gift_cofb_ref",
    _C_HEADER_SOURCE,
    include_dirs=[str(MSVC_COMPAT_DIR), str(OPT32_DIR)],
    extra_compile_args=_force_includes,
)


def build(verbose: bool = True) -> Path:
    """Compila a extensão cffi e retorna o path do arquivo gerado."""
    out = ffi.compile(tmpdir=str(OUT_DIR), verbose=verbose)
    return Path(out)


if __name__ == "__main__":
    result = build()
    print(f"Compilado: {result}")
