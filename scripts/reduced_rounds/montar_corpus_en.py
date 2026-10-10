"""
Monta o corpus `texto-en` a partir de `data/raw/corpora/` (o `texto-html`).

O corpus usado no v1, no v2 e no piso é, na verdade, o HTML bruto das páginas do
Gutenberg (84 de 85 arquivos, com CSS e tags; cerca de 23% dos bytes são
markup), com dois livros em chinês, um em tagalo, um em alemão e um e-mail da
base Enron. O `_TextPlaintextSampler` só colapsa espaços. Este script produz a
fonte que a dissertação descreve: prosa em inglês, sem markup.

Passos, por arquivo:
1. só páginas com `lang="en"`; o e-mail e os outros idiomas ficam de fora;
2. remove `<style>`, `<script>` e os blocos de cabeçalho e rodapé do Gutenberg
   (`id="pg-header"`, `id="pg-footer"`), e extrai o texto das tags restantes;
3. translitera a pontuação tipográfica para ASCII (aspas, apóstrofos, traços,
   reticências, espaço não separável) e decompõe acentos (é -> e); o que sobrar
   fora do ASCII é removido;
4. grava em `data/raw/corpora_en/` e imprime a fração residual de bytes >= 0x80.

Uso:
    python scripts/reduced_rounds/montar_corpus_en.py
"""
from __future__ import annotations

import re
import unicodedata
from html.parser import HTMLParser
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ORIGEM = REPO_ROOT / "data" / "raw" / "corpora"
DESTINO = REPO_ROOT / "data" / "raw" / "corpora_en"

TROCAS = {
    "“": '"', "”": '"', "„": '"', "«": '"', "»": '"',
    "‘": "'", "’": "'", "‚": "'", "′": "'",
    "—": "-", "–": "-", "‒": "-", "―": "-", "‐": "-",
    "…": "...", " ": " ", " ": " ", " ": " ", " ": " ",
    "æ": "ae", "Æ": "AE", "œ": "oe", "Œ": "OE", "ß": "ss",
}


class _Texto(HTMLParser):
    """Coleta o texto, pulando style, script, head e os blocos do Gutenberg."""

    PULAR = {"style", "script", "head", "title"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.partes: list[str] = []
        self._pilha: list[bool] = []          # True = dentro de bloco a pular
        self._fora = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        pular = tag in self.PULAR or a.get("id") in ("pg-header", "pg-footer")
        if tag in ("br", "img", "hr", "meta", "link", "input"):   # sem fechamento
            return
        self._pilha.append(pular)
        self._fora += pular

    def handle_endtag(self, tag):
        if tag in ("br", "img", "hr", "meta", "link", "input"):
            return
        if self._pilha:
            self._fora -= self._pilha.pop()

    def handle_data(self, data):
        if not self._fora:
            self.partes.append(data)


def ascii_en(texto: str) -> str:
    for de, para in TROCAS.items():
        texto = texto.replace(de, para)
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return texto.encode("ascii", "ignore").decode("ascii")


def main() -> None:
    DESTINO.mkdir(parents=True, exist_ok=True)
    total = residual_antes = 0
    usados, fora = [], []
    for p in sorted(ORIGEM.glob("*.txt")):
        bruto = p.read_text(encoding="utf-8", errors="replace")
        m = re.search(r'<html[^>]*lang="([a-z]+)"', bruto[:3000])
        if not m or m.group(1) != "en":
            fora.append((p.name, m.group(1) if m else "sem html"))
            continue
        parser = _Texto()
        parser.feed(bruto)
        texto = " ".join(" ".join(parser.partes).split())
        residual_antes += sum(1 for c in texto if ord(c) >= 128)
        limpo = ascii_en(texto)
        limpo = " ".join(limpo.split())
        (DESTINO / p.name).write_text(limpo, encoding="ascii")
        total += len(limpo)
        usados.append((p.name, len(limpo)))
    print(f"livros em inglês: {len(usados)}; fora: {fora}")
    print(f"caracteres finais: {total:,}; não ASCII antes da transliteração: "
          f"{residual_antes / max(total, 1):.4%}; depois: 0 (removidos)")
    pequenos = [n for n, t in usados if t < 65536]
    print(f"livros com menos de 64 KB (o amostrador do v2 os ignora): {pequenos}")


if __name__ == "__main__":
    main()
