#!/usr/bin/env python
"""Fixa e reconstrói as fontes C de referência dos quatro algoritmos AEAD.

Por que existe
--------------
`ascon-c/`, `gift-cofb/`, `grain-128aead/` e `sparkle/` são gitignored, e o
comentário do `.gitignore` afirmava que "o C amalgamado para rebuild fica em
`src/crypto/`". **Era falso**: `src/crypto/_ascon_ref.c` e companhia são só o
glue do cffi, com declarações forward — nenhum símbolo dos algoritmos. Achado
numa auditoria criptográfica independente (2026-08-24). Consequência: num
clone limpo as extensões não compilavam e os testes de KAT falhavam no import,
não na comparação — o que derruba o objetivo declarado em `data/kat/README.md`
("a validação KAT precisa ser reproduzível por quem avalia o trabalho").

Este script substitui aquela afirmação por um mecanismo real: as fontes não
são versionadas (licenças distintas, e vendorizar C de terceiros num repo de
dissertação polui a autoria), mas ficam **fixadas por commit e por SHA-256 de
cada arquivo efetivamente compilado**.

Uso
---
    python scripts/vendor_sources.py            # confere o que está em disco
    python scripts/vendor_sources.py --fetch    # baixa/clona nos pinos
    python scripts/vendor_sources.py --pins     # imprime o manifesto

O `--check` é o modo padrão e é o que responde "as fontes em disco são as que
geraram os `.pyd` do manifesto do dataset?".

Sobre o Sparkle
---------------
É a única árvore sem `.git`: veio do pacote de submissão ao NIST LWC
(`sparkle.zip`), e o SHA-256 do zip original **não foi registrado na época**.
Os hashes abaixo pinam *o que está em disco e foi compilado*, não a
autenticidade do download — a diferença importa e está declarada em
`data/kat/README.md`. `--fetch` baixa o zip da URL oficial e confere arquivo a
arquivo contra estes hashes, o que fecha a lacuna para quem reproduzir daqui
em diante.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import shutil
import subprocess
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Fonte:
    nome: str
    destino: str
    url: str
    commit: str | None            # None => pacote zip, sem git
    arquivos: dict[str, str] = field(default_factory=dict)  # caminho relativo -> sha256
    zip_subdir: str | None = None  # prefixo a remover ao extrair o zip
    nota: str = ""


FONTES: list[Fonte] = [
    Fonte(
        nome="ascon-c",
        destino="ascon-c",
        url="https://github.com/ascon/ascon-c.git",
        commit="b7ca60bbf86479785de08b75aab2425dce4e9e8b",
        nota=(
            'commit "Change Ascon version from v1.2 to v1.3" — é a árvore que '
            "já adota as convenções do SP 800-232 final (IV 0x00001000808c0001, "
            "carga little-endian, padding 0x01). O predecessor NÃO serve."
        ),
        arquivos={
            "crypto_aead/ascon128av13/ref/aead.c":
                "2cfee9658ae8e4cd6e2219e3281f5ad067207b0140f0b227b1732ad6894294f0",
            "crypto_aead/ascon128av13/ref/api.h":
                "60900c5f806064cc9aff80a15430713870c0772140c4d3cf6699f3b74447fd2b",
            "crypto_aead/ascon128av13/ref/ascon.h":
                "24b8b35c623b30f6fb55908170f920a8e059842c7e4f12cad0fdd04ad5f9be99",
            "crypto_aead/ascon128av13/ref/constants.h":
                "6e95f0ca2457f41fd6f0f301e608804c492a3c9244e21d0e8354b5cd564b1875",
            "crypto_aead/ascon128av13/ref/permutations.h":
                "b9f0d9c50549a0a5c8733196217a352bea10c12420249ceccd809a7ccf0a97c1",
            "crypto_aead/ascon128av13/ref/round.h":
                "b44435ff8c33966a2fdc11aefce83df3f1923b956e82913734480dc6da66d294",
            "crypto_aead/ascon128av13/ref/word.h":
                "77409ad234d666bb3fa14a5fb34cf6f40196bac40eeff8ca73f9fbe54d8f3bb3",
            "crypto_aead/ascon128av13/ref/printstate.c":
                "1f7c69900b61138987d46f27837a8249a7a19adcd5290b71574fd4e90b037b32",
            "crypto_aead/ascon128av13/ref/printstate.h":
                "49d911e69a3ee4873be8a3a2211549659d9efbc97ec5297e18200c6fd19c8381",
        },
    ),
    Fonte(
        nome="gift-cofb",
        destino="gift-cofb",
        url="https://github.com/aadomn/gift",
        commit="962e0e46fa3dcd24743a293f934c86a5a68d29e1",
        nota=(
            "implementação de TERCEIRO (Adomnicai et al., paper Fixslicing), não "
            "a submissão oficial. Não traz KAT do GIFT-COFB — daí o KAT "
            "autogerado e a âncora independente em "
            "tests/test_crypto_independente.py. Os headers em "
            "src/crypto/_gift_cofb_msvc/ (versionados) substituem estes na "
            "compilação MSVC."
        ),
        arquivos={
            "crypto_aead/giftcofb128v1/opt32/encrypt.c":
                "3fd5180b4cd87b0a2fe20672dc6da9c13eee8e216ac90be6920ba50418a2dcf1",
            "crypto_aead/giftcofb128v1/opt32/giftb128.c":
                "2f55b2863244110e7339536b9a498297e66285764532ae8b2a358c50c13906aa",
            "crypto_aead/giftcofb128v1/opt32/api.h":
                "85412554a6a1e937b2908a29f4ff21dc293b98fcd537d5279706fbe28a02756d",
            "crypto_aead/giftcofb128v1/opt32/cofb.h":
                "93b731928095f6bff9e4117b9f5ff872047c231974be9a1bdd990160a95e1f13",
            "crypto_aead/giftcofb128v1/opt32/endian.h":
                "4f0e9f3b66ba8e331d00748243bf12bfb67763529e96dcef6a351406d076c2d4",
            "crypto_aead/giftcofb128v1/opt32/giftb128.h":
                "b0a74e853160f8af93a87103299d33f9b224f1ed5317ab57a550b92b59619c32",
            "crypto_aead/giftcofb128v1/opt32/key_schedule.h":
                "19503759bdee2a29b1b2e4c5da36863e962263bcaf7db9f1527f72a50e9752f3",
            # os 3 vetores oficiais do cifrador de bloco — âncora externa do
            # GIFT-COFB, replicados como literais no teste independente
            "crypto_bc/gift128/opt32/test_vectors.c":
                "055653cfe53a2c64edd7d2d6ec4b5b03bab8a8b3cbfc0c2e83e75a7d5396b866",
        },
    ),
    Fonte(
        nome="grain-128aead",
        destino="grain-128aead",
        url="https://github.com/Grain-128AEAD/Grain-128AEAD-sw-ref.git",
        commit="94765ed6433338a47d46eb19283c6bd7aebbda97",
        nota=(
            "implementação de referência dos próprios designers; o KAT é "
            "byte a byte idêntico em NIST/ref/ e NIST/optimized/, o que o torna "
            "âncora cruzada real entre duas implementações."
        ),
        arquivos={
            "NIST/ref/grain128aead.c":
                "0ad771835c789a2cdce8f48b22d09c6e402def1c8bf0037560c1d49fdf874ffe",
            "NIST/ref/grain128aead.h":
                "1952d914386f6f6ac1d074bcac022e77ea49762420b2b3257e102efdce9eb426",
            "NIST/ref/api.h":
                "642ef822cb04ad9e44a2e0f3a987321aa95e849de17e22f21a93874892279509",
            "NIST/ref/crypto_aead.h":
                "961c32f185a535db541cf1312e55c46a4b20bd9baf15482ba14b22d0835a5b6b",
        },
    ),
    Fonte(
        nome="sparkle",
        destino="sparkle",
        url=(
            "https://csrc.nist.gov/CSRC/media/Projects/lightweight-cryptography/"
            "documents/finalist-round/updated-submissions/sparkle.zip"
        ),
        commit=None,
        zip_subdir="Implementations/crypto_aead",
        nota=(
            "ÚNICA árvore sem proveniência verificável por git. O SHA-256 do "
            "sparkle.zip original não foi registrado na época; os hashes abaixo "
            "pinam o que está em disco e foi compilado, não a autenticidade do "
            "download. O clone GitHub cryptolu/sparkle NÃO serve: não traz KAT "
            "para esta variante."
        ),
        arquivos={
            "crypto_aead/schwaemm256128v2/ref/encrypt.c":
                "5accbb47f889dce03a8d80f972e15ac4c14df73c758b72fa4e7fcd581a124d9d",
            "crypto_aead/schwaemm256128v2/ref/sparkle_ref.c":
                "ab86f5d5c57300e7cc37c8325b9c8e344bb2011aa48bbadb92a91d7251440b6b",
            "crypto_aead/schwaemm256128v2/ref/genkat_aead.c":
                "8e4e6b06c9738aac94553d8b28fa2dbbdf3e5f89409810689986c39688e70222",
            "crypto_aead/schwaemm256128v2/ref/api.h":
                "61ed9eae59e115bd4adef531fa9c97f641a4390998cf1028c2dfaa47897165e4",
            "crypto_aead/schwaemm256128v2/ref/schwaemm_cfg.h":
                "45ea0be77cd0f3ad6e01638d6ead2e1e14fa22b4ab64db5a07fe478ad34c6318",
            "crypto_aead/schwaemm256128v2/ref/sparkle_ref.h":
                "4fbef7a71bc1b916009d9e4f97f54764bc12f96b7214a3add5eb84bcc9cfc55d",
        },
    ),
]


def _sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with caminho.open("rb") as fh:
        for bloco in iter(lambda: fh.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def _git(destino: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", "-C", str(destino), *args],
        capture_output=True, text=True, check=False,
    )
    return out.stdout.strip()


def checar(fonte: Fonte) -> tuple[bool, list[str]]:
    destino = REPO_ROOT / fonte.destino
    problemas: list[str] = []
    if not destino.is_dir():
        return False, [f"árvore ausente: {destino} (rode --fetch)"]

    if fonte.commit is not None:
        head = _git(destino, "rev-parse", "HEAD")
        if head != fonte.commit:
            problemas.append(f"HEAD={head or '?'} != pino {fonte.commit}")
        sujo = _git(destino, "status", "--porcelain", "--untracked-files=no")
        if sujo:
            problemas.append(f"árvore com modificações locais ({len(sujo.splitlines())} arquivos)")

    for rel, esperado in fonte.arquivos.items():
        alvo = destino / rel
        if not alvo.is_file():
            problemas.append(f"ausente: {rel}")
            continue
        obtido = _sha256(alvo)
        if obtido != esperado:
            problemas.append(f"sha256 diverge: {rel}\n      esperado {esperado}\n      obtido   {obtido}")
    return not problemas, problemas


def buscar(fonte: Fonte) -> None:
    destino = REPO_ROOT / fonte.destino
    if destino.exists():
        print(f"  [{fonte.nome}] já existe em {destino} — removendo para refazer no pino")
        shutil.rmtree(destino)

    if fonte.commit is not None:
        print(f"  [{fonte.nome}] clonando {fonte.url}")
        subprocess.run(["git", "clone", "--quiet", fonte.url, str(destino)], check=True)
        subprocess.run(
            ["git", "-C", str(destino), "checkout", "--quiet", fonte.commit], check=True
        )
        return

    # pacote zip (Sparkle)
    import urllib.request

    print(f"  [{fonte.nome}] baixando {fonte.url}")
    with urllib.request.urlopen(fonte.url) as resp:  # noqa: S310 - URL fixa do NIST
        bruto = resp.read()
    print(f"  [{fonte.nome}] sha256 do pacote baixado: {hashlib.sha256(bruto).hexdigest()}")
    destino.mkdir(parents=True)
    with zipfile.ZipFile(io.BytesIO(bruto)) as z:
        prefixo = (fonte.zip_subdir or "").strip("/")
        for membro in z.namelist():
            if membro.endswith("/"):
                continue
            partes = membro.split("/")
            # localiza o subdiretório de interesse dentro do layout do pacote
            if prefixo and prefixo.split("/")[-1] in partes:
                idx = partes.index(prefixo.split("/")[-1])
                rel = Path("crypto_aead", *partes[idx + 1:])
            else:
                continue
            alvo = destino / rel
            alvo.parent.mkdir(parents=True, exist_ok=True)
            alvo.write_bytes(z.read(membro))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fetch", action="store_true",
                    help="baixa/clona as fontes nos pinos (sobrescreve o que existir)")
    ap.add_argument("--pins", action="store_true", help="imprime o manifesto e sai")
    ap.add_argument("--only", metavar="NOME", help="restringe a uma fonte")
    args = ap.parse_args(argv)

    fontes = [f for f in FONTES if not args.only or f.nome == args.only]
    if not fontes:
        print(f"nenhuma fonte com nome {args.only!r}", file=sys.stderr)
        return 2

    if args.pins:
        for f in fontes:
            print(f"\n## {f.nome}\n  url:    {f.url}")
            print(f"  commit: {f.commit or '(pacote zip — sem git)'}")
            print(f"  nota:   {f.nota}")
            for rel, h in f.arquivos.items():
                print(f"    {h}  {rel}")
        return 0

    if args.fetch:
        for f in fontes:
            buscar(f)
        print()

    falhas = 0
    for f in fontes:
        ok, problemas = checar(f)
        print(f"[{'OK  ' if ok else 'FALHA'}] {f.nome}")
        for p in problemas:
            print(f"    - {p}")
        falhas += not ok

    print()
    if falhas:
        print(f"{falhas}/{len(fontes)} fontes divergem dos pinos. "
              f"Os .pyd em src/crypto/ podem NÃO corresponder ao que está em disco.")
        return 1
    print(f"{len(fontes)}/{len(fontes)} fontes conferem com os pinos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
