# Vetores KAT oficiais (Known Answer Tests)

Vetores de teste oficiais dos quatro algoritmos AEAD do experimento,
**versionados no repositório de propósito**.

## Por que estão aqui

As implementações C de referência (`ascon-c/`, `gift-cofb/`,
`grain-128aead/`, `sparkle/`) são vendorizadas localmente e **gitignored** —
não fazem parte do histórico do repo. Até 2026-08-23 os testes de KAT liam
os vetores de dentro dessas pastas, então **num clone limpo três das cinco
validações-âncora do projeto falhavam por arquivo ausente** (só GIFT-COFB
e o CTR_DRBG tinham vetores versionados). Achado numa auditoria de
aderência.

Isso importa além da conveniência: a validação KAT é o que sustenta a
afirmação "os quatro algoritmos estão corretamente implementados", que é
premissa de todo o resto da dissertação. Ela precisa ser reproduzível por
quem avalia o trabalho. Os vetores versionados resolvem metade disso; a
outra metade — reconstruir as implementações C que eles validam — é o que
`scripts/vendor_sources.py` faz. Também é pré-requisito para a proposta de
publicação do dataset (Zenodo).

Os testes preferem estes arquivos e caem para a pasta vendorizada só se
eles não existirem (`_KAT_VERSIONADO if ... else _KAT_VENDORIZADO`).

## Arquivos, proveniência e integridade

| Arquivo | Algoritmo | Origem | SHA-256 |
|---|---|---|---|
| `LWC_AEAD_KAT_ASCON128AV13.txt` | Ascon-AEAD128 (`ascon128av13`, taxa 128 = NIST SP 800-232 final) | `ascon-c/crypto_aead/ascon128av13/LWC_AEAD_KAT_128_128.txt` — repositório oficial dos designers (`github.com/ascon/ascon-c`) | `068f4e256d48f8639754d07efed87588f183f08501acc48efce39f28bd70e0bf` |
| `LWC_AEAD_KAT_GIFTCOFB128_128.txt` | GIFT-COFB (`opt32`) | ⚠️ **AUTOGERADO** por `scripts/generate_gift_cofb_kat.py` a partir da própria `_gift_cofb_ref.pyd` — **não** é um KAT oficial. Ver a nota abaixo. | `07e66d5d6bb052e2df10d9032c404025328c0528c169156c0f7cc7b40d4bfec1` |
| `LWC_AEAD_KAT_GRAIN128AEAD.txt` | Grain-128AEAD (nonce 96 bits, tag 64) | `grain-128aead/NIST/ref/LWC_AEAD_KAT_128_96.txt` — implementação de referência oficial dos designers (`github.com/Grain-128AEAD/Grain-128AEAD-sw-ref`) | `0566ee61b5c28c25b67aedf2190892b8ac460f69259628af9a09ffeffdfdaa06` |
| `LWC_AEAD_KAT_SCHWAEMM256_128.txt` | Schwaemm256-128 (família SPARKLE; nonce 256 bits, tag 128) | `sparkle/crypto_aead/schwaemm256128v2/LWC_AEAD_KAT_128_256.txt` — pacote **oficial de submissão ao NIST LWC** (`csrc.nist.gov/.../updated-submissions/sparkle.zip`), não o clone GitHub `cryptolu/sparkle` (que não traz KAT para esta variante). ⚠️ SHA-256 do zip de origem não registrado — ver a nota abaixo | `1bfdd3439c0b89441d77149d28e5c13d54ddd8ca5671a5247d2d2923eae23851` |

Cada arquivo tem **1089 vetores** (o formato padrão do NIST LWC: todas as
combinações de plaintext 0–31 bytes × AD 0–31 bytes). Os quatro wrappers
validam **1089/1089**.

## ⚠️ O KAT do GIFT-COFB é autogerado — leia antes de citar

**Correção de proveniência (2026-08-24).** Este README afirmava que o
arquivo do GIFT-COFB vinha do "pacote de submissão NIST LWC". **É falso**,
e a afirmação era minha: o arquivo é produzido por
`scripts/generate_gift_cofb_kat.py`, que importa `_gift_cofb_ref` (a mesma
extensão que o KAT depois "valida") e chama `crypto_aead_encrypt` para
gerar os 1089 vetores. O repositório vendorizado
(`github.com/aadomn/gift`, de terceiro — não a submissão oficial) **não
contém KAT algum**; seu próprio README manda usar o `TestVectorGen` do
NIST.

Consequência: **"GIFT-COFB: 1089/1089 validados" era uma tautologia** — o
teste confirmava que a implementação concorda consigo mesma, e teria
passado igual com a implementação errada. Os outros três algoritmos NÃO
têm esse problema (KAT oficial dos designers / da submissão NIST).

### A âncora externa que substitui isso

`tests/test_crypto_independente.py` reimplementa **GIFT-128 e o modo COFB a
partir das especificações publicadas** (paper CHES 2017 + submissão
GIFT-COFB), em Python puro, sem copiar uma linha do C de referência, e usa
essa implementação como oráculo. A cadeia de evidência é:

1. **3 vetores OFICIAIS do cifrador de bloco** — do `test_vectors.c` dos
   designers, embutidos como literais no teste porque `gift-cofb/` é
   gitignored. É o único elo que não depende de nada gerado aqui.
2. Eles validam o **GIFT-128 independente** (S-box `GS`, permutação `P128`,
   LFSR de 6 bits das constantes, key schedule
   `k1>>>2 ‖ k0>>>12 ‖ k7 ‖ …`).
3. Sobre ele, o **GIFTb-128** (mesmo cifrador na representação bitsliced
   `W_j[i] = b_{4i+j}` do paper *Fixslicing*) e o **modo COFB** — dobra em
   GF(2⁶⁴) com `0x1b`, `G(Y1‖Y2) = Y2‖(Y1<<<1)`, e o expoente
   `3^(1 + [A_a parcial] + 2·[M vazio])` antes do último bloco de AD.
4. O resultado concorda com `_gift_cofb_ref.pyd` em **1089 vetores + 60
   casos aleatórios** de comprimento arbitrário (multi-bloco, até 100 B).

**A porta MSVC feita à mão (`src/crypto/_gift_cofb_msvc/`) está correta** —
mas quem sustenta isso é essa verificação, não o arquivo de KAT deste
diretório. Depois dela o arquivo deixa de ser circular: passa a ser um
registro conferido por uma segunda implementação
(`test_gift_cofb_independente_vs_kat_versionado`).

Na dissertação, o GIFT-COFB precisa ser descrito assim, e não como
"validado contra KAT oficial".

O mesmo teste faz a verificação redundante do Ascon: uma implementação
escrita do SP 800-232 dá **1089/1089** contra o KAT oficial e bate com o
`.pyd` em 80 casos aleatórios até 300 B.

## ⚠️ Sobre a proveniência do Schwaemm256-128

`sparkle/` é a única das quatro árvores **sem `.git`**: veio do pacote de
submissão ao NIST LWC (`sparkle.zip`) e o SHA-256 do zip **não foi
registrado na época**. Os parâmetros conferem (estado 384, taxa 256,
capacidade 128, passos 7/11, as oito constantes RCON) e o KAT bate — mas o
KAT veio do mesmo zip que o código, então se o zip não fosse autêntico nada
aqui detectaria. `scripts/vendor_sources.py` pina os SHA-256 dos arquivos
que estão em disco e o `--fetch` baixa da URL oficial conferindo arquivo a
arquivo: fecha para frente, não para trás.

## Reconstruir as fontes C num clone limpo

As implementações C são gitignored. Versionar os vetores sem poder
reconstruir as implementações resolveria pela metade — num clone limpo os
testes falhariam no import, não na comparação. Para restaurá-las nos
commits e hashes fixados:

```bash
python scripts/vendor_sources.py            # confere o que está em disco
python scripts/vendor_sources.py --fetch    # clona/baixa nos pinos
python scripts/vendor_sources.py --pins     # imprime o manifesto
```

Verificar integridade:

```bash
sha256sum -c <<'EOF'
068f4e256d48f8639754d07efed87588f183f08501acc48efce39f28bd70e0bf *LWC_AEAD_KAT_ASCON128AV13.txt
07e66d5d6bb052e2df10d9032c404025328c0528c169156c0f7cc7b40d4bfec1 *LWC_AEAD_KAT_GIFTCOFB128_128.txt
0566ee61b5c28c25b67aedf2190892b8ac460f69259628af9a09ffeffdfdaa06 *LWC_AEAD_KAT_GRAIN128AEAD.txt
1bfdd3439c0b89441d77149d28e5c13d54ddd8ca5671a5247d2d2923eae23851 *LWC_AEAD_KAT_SCHWAEMM256_128.txt
EOF
```

## Licenciamento

São vetores de teste de submissões públicas ao processo NIST Lightweight
Cryptography, redistribuídos aqui para reprodutibilidade da validação.
As implementações C em si **não** estão versionadas — só os vetores.

## Vetores relacionados (outro diretório)

Os vetores CAVP do CTR_DRBG (NIST SP 800-90A, 240 casos) ficam em
`tests/vectors/ctr_drbg_aes128_nodf.json`, com proveniência própria em
`tests/vectors/README.md`.
