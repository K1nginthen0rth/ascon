"""
Compilador cffi para Ascon-AEAD128 (implementação de referência C).

Uso (execução direta, uma vez):
    python src/crypto/_ascon_cffi_build.py

Gera _ascon_ref.cpXXX-win_amd64.pyd (Windows) ou _ascon_ref.so (Linux/Mac)
no diretório src/crypto/, ao lado deste arquivo.

Requer:
    - ascon-c/crypto_aead/ascon128v13/ref/  (fontes C de referência)
    - ascon-c/tests/crypto_aead.h           (declarações das funções)
    - cffi instalado (pip install cffi)
    - Compilador C compatível com Python (MSVC no Windows, gcc no Linux/Mac)
"""
from __future__ import annotations

from pathlib import Path

import cffi

# ---------------------------------------------------------------------------
# Caminhos
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ASCON_REF_DIR = REPO_ROOT / "ascon-c" / "crypto_aead" / "ascon128v13" / "ref"
ASCON_TESTS_DIR = REPO_ROOT / "ascon-c" / "tests"
OUT_DIR = Path(__file__).parent  # src/crypto/

# Validação antecipada de paths
for _p in (ASCON_REF_DIR, ASCON_TESTS_DIR):
    if not _p.is_dir():
        raise FileNotFoundError(
            f"Diretório Ascon não encontrado: {_p}\n"
            "Certifique-se de que ascon-c/ está no repositório."
        )

# ---------------------------------------------------------------------------
# Definição cffi
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

# c_header_source: código C incluído no wrapper gerado pelo cffi.
# Fornece as declarações para que o compilador saiba os tipos no momento
# da geração do wrapper — as implementações vêm de aead.c via sources=[].
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
    "_ascon_ref",
    _C_HEADER_SOURCE,
    sources=[str(ASCON_REF_DIR / "aead.c")],
    include_dirs=[str(ASCON_REF_DIR), str(ASCON_TESTS_DIR)],
)


def build(verbose: bool = True) -> Path:
    """
    Compila a extensão cffi para Ascon-AEAD128.

    Args:
        verbose: Se True, exibe saída do compilador.

    Returns:
        Caminho do arquivo .pyd/.so gerado.
    """
    out = ffi.compile(tmpdir=str(OUT_DIR), verbose=verbose)
    return Path(out)


if __name__ == "__main__":
    print(f"Compilando extensão Ascon em {OUT_DIR} ...")
    result = build(verbose=True)
    print(f"\nSucesso: {result}")
