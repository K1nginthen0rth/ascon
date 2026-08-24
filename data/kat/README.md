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
quem avalia o trabalho, sem depender de baixar quatro repositórios
externos primeiro. Também é pré-requisito para a proposta de publicação do
dataset (Zenodo).

Os testes preferem estes arquivos e caem para a pasta vendorizada só se
eles não existirem (`_KAT_VERSIONADO if ... else _KAT_VENDORIZADO`).

## Arquivos, proveniência e integridade

| Arquivo | Algoritmo | Origem | SHA-256 |
|---|---|---|---|
| `LWC_AEAD_KAT_ASCON128AV13.txt` | Ascon-AEAD128 (`ascon128av13`, taxa 128 = NIST SP 800-232 final) | `ascon-c/crypto_aead/ascon128av13/LWC_AEAD_KAT_128_128.txt` — repositório oficial dos designers (`github.com/ascon/ascon-c`) | `068f4e256d48f8639754d07efed87588f183f08501acc48efce39f28bd70e0bf` |
| `LWC_AEAD_KAT_GIFTCOFB128_128.txt` | GIFT-COFB (`opt32`) | ⚠️ **AUTOGERADO** por `scripts/generate_gift_cofb_kat.py` a partir da própria `_gift_cofb_ref.pyd` — **não** é um KAT oficial. Ver a nota abaixo. | `07e66d5d6bb052e2df10d9032c404025328c0528c169156c0f7cc7b40d4bfec1` |
| `LWC_AEAD_KAT_GRAIN128AEAD.txt` | Grain-128AEAD (nonce 96 bits, tag 64) | `grain-128aead/NIST/ref/LWC_AEAD_KAT_128_96.txt` — implementação de referência oficial dos designers (`github.com/Grain-128AEAD/Grain-128AEAD-sw-ref`) | `0566ee61b5c28c25b67aedf2190892b8ac460f69259628af9a09ffeffdfdaa06` |
| `LWC_AEAD_KAT_SCHWAEMM256_128.txt` | Schwaemm256-128 (família SPARKLE; nonce 256 bits, tag 128) | `sparkle/crypto_aead/schwaemm256128v2/LWC_AEAD_KAT_128_256.txt` — pacote **oficial de submissão ao NIST LWC** (`csrc.nist.gov/.../updated-submissions/sparkle.zip`), não o clone GitHub `cryptolu/sparkle` (que não traz KAT para esta variante) | `1bfdd3439c0b89441d77149d28e5c13d54ddd8ca5671a5247d2d2923eae23851` |

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

**A âncora externa que substitui isso** (auditoria independente,
2026-08-24): uma implementação de GIFT-128 escrita do zero a partir da
especificação publicada (S-box, permutação P128, LFSR das constantes de
rodada, key schedule) foi conferida contra os 3 vetores oficiais de
`test_vectors.c`; estabelecida a ponte `giftb128`↔`gift128` (diferem só
pela transposição de packing/unpacking); e o modo COFB implementado com
os macros do `cofb.h` upstream (não os portados à mão para MSVC).
Resultado: **13/13 casos batem com o wrapper**, incluindo o vetor
`Count=1` = `368965836D36614DE2FC24D0F801B9AF`. **O port MSVC feito à mão
está correto** — mas quem sustenta isso é essa verificação, não o arquivo
de KAT deste diretório.

Na dissertação, o GIFT-COFB precisa ser descrito assim, e não como
"validado contra KAT oficial".

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
