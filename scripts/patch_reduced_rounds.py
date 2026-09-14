"""
Aplica, de forma idempotente, patches de redução de rodadas nas fontes C
vendorizadas de Ascon, GIFT-COFB e Schwaemm256-128 (Grain fica de fora desta
rodada — decisão registrada no plano do estudo de sensibilidade).

Por que um script, e não editar `ascon-c/`/`gift-cofb/`/`sparkle/` direto:
essas pastas são gitignored (vendorizadas via `scripts/vendor_sources.py`) e
`--fetch` as restaura para o pino original, apagando qualquer edição manual.
Este script é o que fica versionado; ele é reaplicável a qualquer momento
sobre um clone limpo.

Todo patch é guardado por `#ifndef`/macro override, de modo que a build SEM
nenhuma flag de compilação extra produz bit a bit a mesma saída de antes do
patch. Isso é o que permite usar os 1.089 KATs oficiais de cada algoritmo
como critério de aceite do patch em si (ver `verify_patches_inertes()`).

Uso:
    python scripts/patch_reduced_rounds.py            # aplica os 3 patches
    python scripts/patch_reduced_rounds.py --check     # só verifica, não escreve
    python scripts/patch_reduced_rounds.py --unpatch    # tenta reverter (ver nota)

Nota sobre reversão: a forma robusta de reverter é `vendor_sources.py --fetch`,
que restaura do zero. `--unpatch` aqui é um best-effort para desenvolvimento
local, não uma garantia.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

ASCON_PERM_H = (
    REPO_ROOT / "ascon-c" / "crypto_aead" / "ascon128av13" / "ref" / "permutations.h"
)
GIFT_C = (
    REPO_ROOT / "gift-cofb" / "crypto_aead" / "giftcofb128v1" / "opt32" / "giftb128.c"
)
SCHWAEMM_CFG_H = (
    REPO_ROOT / "sparkle" / "crypto_aead" / "schwaemm256128v2" / "ref" / "schwaemm_cfg.h"
)

_MARKER = "REDUCED_ROUNDS_PATCH"


# ---------------------------------------------------------------------------
# Ascon: ref/permutations.h define P12/P8/P6 com as 12 constantes de rodada
# como literais hardcoded em cada chamada ROUND(s, C). O aead.c deste diretório
# chama P12()/P8() sem nenhum parâmetro de contagem — diferente do
# ascon-c/src/permutations.h genérico (PROUNDS(s,nr)), que existe no repo mas
# NÃO é o que este build usa. Substituímos P12/P8 por versões que fatiam uma
# tabela de constantes conforme ASCON_PA_ROUNDS_OVERRIDE/ASCON_PB_ROUNDS_OVERRIDE.
# ---------------------------------------------------------------------------

_ASCON_ORIGINAL = '''static inline void P12(ascon_state_t* s) {
  ROUND(s, 0xf0);
  ROUND(s, 0xe1);
  ROUND(s, 0xd2);
  ROUND(s, 0xc3);
  ROUND(s, 0xb4);
  ROUND(s, 0xa5);
  ROUND(s, 0x96);
  ROUND(s, 0x87);
  ROUND(s, 0x78);
  ROUND(s, 0x69);
  ROUND(s, 0x5a);
  ROUND(s, 0x4b);
}

static inline void P8(ascon_state_t* s) {
  ROUND(s, 0xb4);
  ROUND(s, 0xa5);
  ROUND(s, 0x96);
  ROUND(s, 0x87);
  ROUND(s, 0x78);
  ROUND(s, 0x69);
  ROUND(s, 0x5a);
  ROUND(s, 0x4b);
}'''

_ASCON_PATCHED = f'''/* {_MARKER}: P12/P8 parametrizadas por numero de rodadas.
 * Defaults (12/8) reproduzem byte a byte as funcoes originais — ver
 * scripts/patch_reduced_rounds.py::verify_patches_inertes(). */
#ifndef ASCON_PA_ROUNDS_OVERRIDE
#define ASCON_PA_ROUNDS_OVERRIDE 12
#endif
#ifndef ASCON_PB_ROUNDS_OVERRIDE
#define ASCON_PB_ROUNDS_OVERRIDE 8
#endif

static const uint8_t ASCON_RC_TABLE[12] = {{
    0xf0, 0xe1, 0xd2, 0xc3, 0xb4, 0xa5, 0x96, 0x87, 0x78, 0x69, 0x5a, 0x4b
}};

static inline void P12(ascon_state_t* s) {{
  for (int _i = 12 - ASCON_PA_ROUNDS_OVERRIDE; _i < 12; _i++) {{
    ROUND(s, ASCON_RC_TABLE[_i]);
  }}
}}

static inline void P8(ascon_state_t* s) {{
  for (int _i = 12 - ASCON_PB_ROUNDS_OVERRIDE; _i < 12; _i++) {{
    ROUND(s, ASCON_RC_TABLE[_i]);
  }}
}}'''


# ---------------------------------------------------------------------------
# GIFT-COFB: opt32/giftb128.c aplica 8 chamadas de QUINTUPLE_ROUND hardcoded
# (rkey/rconst avançando de 10/5 em 10/5) dentro de giftb128(). Substituímos
# por um laço limitado por GIFT_ROUNDS_OVERRIDE (múltiplo de 5 — granularidade
# imposta pelo fixslicing, ver plano). O laço com override=40 reproduz a
# mesma sequência de chamadas, na mesma ordem.
# ---------------------------------------------------------------------------

_GIFT_ORIGINAL = """    QUINTUPLE_ROUND(state, rkey, rconst);
    QUINTUPLE_ROUND(state, rkey + 10, rconst + 5);
    QUINTUPLE_ROUND(state, rkey + 20, rconst + 10);
    QUINTUPLE_ROUND(state, rkey + 30, rconst + 15);
    QUINTUPLE_ROUND(state, rkey + 40, rconst + 20);
    QUINTUPLE_ROUND(state, rkey + 50, rconst + 25);
    QUINTUPLE_ROUND(state, rkey + 60, rconst + 30);
    QUINTUPLE_ROUND(state, rkey + 70, rconst + 35);"""

_GIFT_PATCHED = f"""    /* {_MARKER}: 8 chamadas fixas -> laco ate GIFT_ROUNDS_OVERRIDE/5.
     * Default (40) reproduz a mesma sequencia rkey+10*i / rconst+5*i, na
     * mesma ordem, para i=0..7. */
#ifndef GIFT_ROUNDS_OVERRIDE
#define GIFT_ROUNDS_OVERRIDE 40
#endif
    for (int _i = 0; _i < (GIFT_ROUNDS_OVERRIDE / 5); _i++) {{
        QUINTUPLE_ROUND(state, rkey + _i * 10, rconst + _i * 5);
    }}"""


# ---------------------------------------------------------------------------
# Schwaemm256-128: schwaemm_cfg.h define SPARKLE_STEPS_BIG/SLIM como literais.
# sparkle_ref(state, brans, steps) do encrypt.c JA recebe steps como parametro
# de execucao — não precisa tocar em nenhum .c, só liberar os dois #define via
# #ifndef. Caso mais simples dos três.
# ---------------------------------------------------------------------------

_SCHWAEMM_ORIGINAL = """#define SPARKLE_STEPS_SLIM  7
#define SPARKLE_STEPS_BIG   11"""

_SCHWAEMM_PATCHED = f"""/* {_MARKER}: liberados para override externo via define_macros do CFFI. */
#ifndef SPARKLE_STEPS_SLIM
#define SPARKLE_STEPS_SLIM  7
#endif
#ifndef SPARKLE_STEPS_BIG
#define SPARKLE_STEPS_BIG   11
#endif"""


def _apply(path: Path, original: str, patched: str, label: str, check_only: bool) -> bool:
    if not path.is_file():
        raise FileNotFoundError(
            f"{label}: arquivo não encontrado em {path}. "
            "Rode `python scripts/vendor_sources.py --fetch` primeiro."
        )
    text = path.read_text(encoding="utf-8")
    if _MARKER in text:
        print(f"[{label}] já patchado (marcador presente) — nada a fazer.")
        return True
    if original not in text:
        raise RuntimeError(
            f"[{label}] bloco original não encontrado em {path}.\n"
            "As fontes vendorizadas podem ter mudado de versão — revisar "
            "este script antes de continuar (não aplicar patch às cegas)."
        )
    if check_only:
        print(f"[{label}] NÃO patchado (--check, nenhuma escrita feita).")
        return False
    path.write_text(text.replace(original, patched), encoding="utf-8")
    print(f"[{label}] patch aplicado em {path}")
    return True


def _unpatch(path: Path, patched: str, original: str, label: str) -> None:
    if not path.is_file():
        print(f"[{label}] arquivo não encontrado, nada a reverter.")
        return
    text = path.read_text(encoding="utf-8")
    if _MARKER not in text:
        print(f"[{label}] não estava patchado.")
        return
    if patched not in text:
        print(
            f"[{label}] marcador presente mas bloco patchado não bate "
            "exatamente (foi editado à mão?). Use "
            "`python scripts/vendor_sources.py --fetch` para restaurar do zero."
        )
        return
    path.write_text(text.replace(patched, original), encoding="utf-8")
    print(f"[{label}] revertido.")


def apply_all(check_only: bool = False) -> bool:
    ok = True
    ok &= _apply(ASCON_PERM_H, _ASCON_ORIGINAL, _ASCON_PATCHED, "ascon", check_only)
    ok &= _apply(GIFT_C, _GIFT_ORIGINAL, _GIFT_PATCHED, "gift-cofb", check_only)
    ok &= _apply(SCHWAEMM_CFG_H, _SCHWAEMM_ORIGINAL, _SCHWAEMM_PATCHED, "schwaemm", check_only)
    return ok


def unpatch_all() -> None:
    _unpatch(ASCON_PERM_H, _ASCON_PATCHED, _ASCON_ORIGINAL, "ascon")
    _unpatch(GIFT_C, _GIFT_PATCHED, _GIFT_ORIGINAL, "gift-cofb")
    _unpatch(SCHWAEMM_CFG_H, _SCHWAEMM_PATCHED, _SCHWAEMM_ORIGINAL, "schwaemm")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="só verifica, não escreve")
    parser.add_argument("--unpatch", action="store_true", help="tenta reverter (best-effort)")
    args = parser.parse_args()

    if args.unpatch:
        unpatch_all()
        sys.exit(0)

    all_ok = apply_all(check_only=args.check)
    sys.exit(0 if all_ok else 1)
