"""
Compilador cffi para Schwaemm256-128 (implementação de referência C, família
SPARKLE — esponja ARX, NIST LWC finalist).

Uso (execução direta, uma vez):
    python src/crypto/_sparkle_cffi_build.py

Gera _sparkle_ref.cpXXX-win_amd64.pyd (Windows) ou _sparkle_ref.so
(Linux/Mac) no diretório src/crypto/, ao lado deste arquivo.

Requer:
    - sparkle/crypto_aead/schwaemm256128v2/ref/  (fontes C de referência,
      vendorizadas do pacote de submissão oficial ao NIST LWC — key 128
      bits, nonce 256 bits, tag 128 bits; schwaemm_cfg.h já fixa a
      variante SCHWAEMM256_128, não depende de macro externa)
    - cffi instalado (pip install cffi)
    - Compilador C compatível com Python (MSVC no Windows, gcc no Linux/Mac)

Nota: assim como o Grain-128AEAD, este código de referência é C99 portável
(sem extensões GNU, sem __uint128_t, sem builtins) — nenhum header de
compatibilidade MSVC foi necessário.
"""
from __future__ import annotations

from pathlib import Path

import cffi

# ---------------------------------------------------------------------------
# Caminhos
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SPARKLE_REF_DIR = (
    REPO_ROOT / "sparkle" / "crypto_aead" / "schwaemm256128v2" / "ref"
)
OUT_DIR = Path(__file__).parent  # src/crypto/

if not SPARKLE_REF_DIR.is_dir():
    raise FileNotFoundError(
        f"Diretório Schwaemm256-128 não encontrado: {SPARKLE_REF_DIR}\n"
        "Certifique-se de que sparkle/crypto_aead/schwaemm256128v2/ref/ "
        "está na raiz do repositório (vendorizado do pacote de submissão "
        "oficial ao NIST LWC: csrc.nist.gov .../updated-submissions/"
        "sparkle.zip)."
    )

# ---------------------------------------------------------------------------
# Definição cffi — mesma API SUPERCOP/eBACS do Ascon, GIFT-COFB e Grain
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

_C_HEADER_SOURCE = """
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
"""

ffi.set_source(
    "_sparkle_ref",
    _C_HEADER_SOURCE,
    sources=[
        str(SPARKLE_REF_DIR / "encrypt.c"),
        str(SPARKLE_REF_DIR / "sparkle_ref.c"),
    ],
    include_dirs=[str(SPARKLE_REF_DIR)],
)


def build(verbose: bool = True) -> Path:
    """
    Compila a extensão cffi para Schwaemm256-128.

    Args:
        verbose: Se True, exibe saída do compilador.

    Returns:
        Caminho do arquivo .pyd/.so gerado.
    """
    out = ffi.compile(tmpdir=str(OUT_DIR), verbose=verbose)
    return Path(out)


if __name__ == "__main__":
    print(f"Compilando extensão Schwaemm256-128 em {OUT_DIR} ...")
    result = build(verbose=True)
    print(f"\nSucesso: {result}")
