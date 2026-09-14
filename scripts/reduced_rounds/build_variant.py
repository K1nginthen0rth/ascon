"""
Compila variantes de rodadas reduzidas de Ascon-AEAD128, GIFT-COFB e
Schwaemm256-128, a partir das MESMAS fontes vendorizadas de produção, já
patchadas por `scripts/patch_reduced_rounds.py` (rodar aquele script antes
deste, uma vez).

Cada variante vira um módulo `.pyd`/`.so` com nome único, compilado num
diretório PRÓPRIO (`build/reduced_rounds/<nome>/`), nunca em `src/crypto/` —
os wrappers de produção (`AsconAEAD128`, `GiftCOFB`, `Schwaemm256_128`) não
são tocados nem re-importados por este módulo. É um sistema paralelo, de
propósito único: o estudo de sensibilidade a rodadas reduzidas.

Requer ambiente MSVC ativo (rodar via `build_reduced_variant.bat`, que chama
vcvarsall.bat, assim como os build_*.bat de produção — cffi via `import` puro
não encontra cl.exe fora desse ambiente no Windows).

Uso:
    python scripts/reduced_rounds/build_variant.py --algo ascon --pa 12 --pb 4
    python scripts/reduced_rounds/build_variant.py --algo gift --rounds 20
    python scripts/reduced_rounds/build_variant.py --algo schwaemm --slim 3 --big 11
    python scripts/reduced_rounds/build_variant.py --all-baseline   # 3 variantes na spec, p/ diff vs. producao
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cffi

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUT_ROOT = REPO_ROOT / "build" / "reduced_rounds"

ASCON_REF_DIR = REPO_ROOT / "ascon-c" / "crypto_aead" / "ascon128av13" / "ref"
ASCON_TESTS_DIR = REPO_ROOT / "ascon-c" / "tests"  # crypto_aead.h vive aqui, não em ref/
GIFT_OPT32_DIR = REPO_ROOT / "gift-cofb" / "crypto_aead" / "giftcofb128v1" / "opt32"
GIFT_MSVC_COMPAT_DIR = REPO_ROOT / "src" / "crypto" / "_gift_cofb_msvc"
SPARKLE_REF_DIR = REPO_ROOT / "sparkle" / "crypto_aead" / "schwaemm256128v2" / "ref"

_CDEF = """
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

_C_HEADER_DECLS = """
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


def _out_dir(module_name: str) -> Path:
    d = OUT_ROOT / module_name
    d.mkdir(parents=True, exist_ok=True)
    return d


def _already_built(module_name: str) -> Path | None:
    """Retorna o .pyd/.so já compilado, se existir.

    Evita chamar `ffi.compile()` quando não há nada a fazer: o link.exe do MSVC
    falha com LNK1104 se QUALQUER processo ainda tiver o .pyd carregado, e isso
    já derrubou uma rodada de 12h no meio (processos python de sessões antigas
    segurando o handle). Pular o link quando o artefato existe elimina essa
    classe de falha inteira.
    """
    d = OUT_ROOT / module_name
    for pattern in (f"{module_name}.*.pyd", f"{module_name}.*.so", f"{module_name}.pyd"):
        for hit in d.glob(pattern):
            return hit
    return None


def build_ascon(pa: int, pb: int) -> Path:
    """pa=ASCON_PA_ROUNDS_OVERRIDE (init/final), pb=ASCON_PB_ROUNDS_OVERRIDE (dados).
    Defaults de produção: pa=12, pb=8."""
    module_name = f"_ascon_ref_pa{pa}_pb{pb}"
    cached = _already_built(module_name)
    if cached is not None:
        return cached
    ffi = cffi.FFI()
    ffi.cdef(_CDEF)
    ffi.set_source(
        module_name,
        _C_HEADER_DECLS,
        sources=[str(ASCON_REF_DIR / "aead.c")],
        include_dirs=[str(ASCON_REF_DIR), str(ASCON_TESTS_DIR)],
        define_macros=[
            ("ASCON_PA_ROUNDS_OVERRIDE", str(pa)),
            ("ASCON_PB_ROUNDS_OVERRIDE", str(pb)),
        ],
    )
    return Path(ffi.compile(tmpdir=str(_out_dir(module_name)), verbose=True))


def build_gift(rounds: int) -> Path:
    """rounds=GIFT_ROUNDS_OVERRIDE, múltiplo de 5 (granularidade do fixslicing).
    Default de produção: 40."""
    if rounds % 5 != 0 or not (5 <= rounds <= 40):
        raise ValueError(f"rounds deve ser múltiplo de 5 em [5,40], recebido {rounds}")
    module_name = f"_gift_cofb_ref_r{rounds}"
    cached = _already_built(module_name)
    if cached is not None:
        return cached
    ffi = cffi.FFI()
    ffi.cdef(_CDEF)
    c_header_source = f"""
#include "api.h"
#include "encrypt.c"
#include "giftb128.c"
"""
    force_includes = [
        f"/FI{GIFT_MSVC_COMPAT_DIR / 'cofb.h'}",
        f"/FI{GIFT_MSVC_COMPAT_DIR / 'giftb128.h'}",
        f"/FI{GIFT_MSVC_COMPAT_DIR / 'key_schedule.h'}",
    ]
    ffi.set_source(
        module_name,
        c_header_source,
        include_dirs=[str(GIFT_MSVC_COMPAT_DIR), str(GIFT_OPT32_DIR)],
        extra_compile_args=force_includes,
        define_macros=[("GIFT_ROUNDS_OVERRIDE", str(rounds))],
    )
    return Path(ffi.compile(tmpdir=str(_out_dir(module_name)), verbose=True))


def build_schwaemm(slim: int, big: int) -> Path:
    """slim=SPARKLE_STEPS_SLIM (dados), big=SPARKLE_STEPS_BIG (init/final/AD final).
    Defaults de produção: slim=7, big=11."""
    module_name = f"_sparkle_ref_slim{slim}_big{big}"
    cached = _already_built(module_name)
    if cached is not None:
        return cached
    ffi = cffi.FFI()
    ffi.cdef(_CDEF)
    ffi.set_source(
        module_name,
        _C_HEADER_DECLS,
        sources=[
            str(SPARKLE_REF_DIR / "encrypt.c"),
            str(SPARKLE_REF_DIR / "sparkle_ref.c"),
        ],
        include_dirs=[str(SPARKLE_REF_DIR)],
        define_macros=[
            ("SPARKLE_STEPS_SLIM", str(slim)),
            ("SPARKLE_STEPS_BIG", str(big)),
        ],
    )
    return Path(ffi.compile(tmpdir=str(_out_dir(module_name)), verbose=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--algo", choices=["ascon", "gift", "schwaemm"])
    parser.add_argument("--pa", type=int, default=12)
    parser.add_argument("--pb", type=int, default=8)
    parser.add_argument("--rounds", type=int, default=40)
    parser.add_argument("--slim", type=int, default=7)
    parser.add_argument("--big", type=int, default=11)
    parser.add_argument("--all-baseline", action="store_true",
                        help="compila as 3 variantes na spec (para diff binário vs. producao)")
    args = parser.parse_args()

    if args.all_baseline:
        print("ascon  (12/8):", build_ascon(12, 8))
        print("gift   (40):  ", build_gift(40))
        print("schwaemm(7/11):", build_schwaemm(7, 11))
        sys.exit(0)

    if args.algo == "ascon":
        print(build_ascon(args.pa, args.pb))
    elif args.algo == "gift":
        print(build_gift(args.rounds))
    elif args.algo == "schwaemm":
        print(build_schwaemm(args.slim, args.big))
    else:
        parser.error("--algo é obrigatório (exceto com --all-baseline)")
