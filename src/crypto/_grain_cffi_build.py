"""
Compilador cffi para Grain-128AEAD (implementação de referência C).

Uso (execução direta, uma vez):
    python src/crypto/_grain_cffi_build.py

Gera _grain_ref.cpXXX-win_amd64.pyd (Windows) ou _grain_ref.so (Linux/Mac)
no diretório src/crypto/, ao lado deste arquivo.

Requer:
    - grain-128aead/NIST/ref/  (fontes C de referência, cifra de fluxo
      LFSR+NFSR — chave 128 bits, nonce 96 bits, tag 64 bits)
    - cffi instalado (pip install cffi)
    - Compilador C compatível com Python (MSVC no Windows, gcc no Linux/Mac)

Nota: ao contrário do GIFT-COFB, o código de referência do Grain-128AEAD
é ANSI C portável (sem extensões GNU, sem __uint128_t, sem builtins) —
não foi necessário nenhum header de compatibilidade MSVC.
"""
from __future__ import annotations

from pathlib import Path

import cffi

# ---------------------------------------------------------------------------
# Caminhos
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GRAIN_REF_DIR = REPO_ROOT / "grain-128aead" / "NIST" / "ref"
OUT_DIR = Path(__file__).parent  # src/crypto/

if not GRAIN_REF_DIR.is_dir():
    raise FileNotFoundError(
        f"Diretório Grain-128AEAD não encontrado: {GRAIN_REF_DIR}\n"
        "Certifique-se de que grain-128aead/ está na raiz do repositório "
        "(git clone https://github.com/Grain-128AEAD/Grain-128AEAD-sw-ref.git "
        "grain-128aead)."
    )

# ---------------------------------------------------------------------------
# Definição cffi — mesma API SUPERCOP/eBACS do Ascon e GIFT-COFB
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
    "_grain_ref",
    _C_HEADER_SOURCE,
    sources=[str(GRAIN_REF_DIR / "grain128aead.c")],
    include_dirs=[str(GRAIN_REF_DIR)],
)


def build(verbose: bool = True) -> Path:
    """
    Compila a extensão cffi para Grain-128AEAD.

    Args:
        verbose: Se True, exibe saída do compilador.

    Returns:
        Caminho do arquivo .pyd/.so gerado.
    """
    out = ffi.compile(tmpdir=str(OUT_DIR), verbose=verbose)
    return Path(out)


if __name__ == "__main__":
    print(f"Compilando extensão Grain-128AEAD em {OUT_DIR} ...")
    result = build(verbose=True)
    print(f"\nSucesso: {result}")
