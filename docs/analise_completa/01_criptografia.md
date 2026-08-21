# 1. Camada de criptografia (`src/crypto/`)

Quatro cifras, todas atrás de uma interface uniforme:
`encrypt(key, nonce, plaintext, associated_data=b"") -> bytes`,
`decrypt(key, nonce, ciphertext, associated_data=b"") -> bytes`,
`.metadata` (dict de rastreabilidade), e para as duas cifras-alvo também
`.validate_kat(path) -> (total, passed, failed_indices)`.

| Arquivo | Classe | Papel | Backend |
|---|---|---|---|
| `ascon_wrapper.py` (343 linhas) | `AsconAEAD128` | Classe-alvo 1 (NIST SP 800-232) | C via cffi (`_ascon_ref`), impl `ref` |
| `gift_cofb_wrapper.py` (290 linhas) | `GiftCOFB` | Classe-alvo 2 (NIST LWC Round 2 finalist) | C via cffi (`_gift_cofb_ref`), impl `opt32` |
| `aes_ecb_wrapper.py` (133 linhas) | `AES128ECB` | Controle positivo legado (protocolo antigo com AES-ECB) | `cryptography` (OpenSSL) |
| `vigenere_wrapper.py` (107 linhas) | `VigenereWrapper` | Controle positivo atual | Python puro |
| `kat_parser.py` (115 linhas) | `parse_kat_file` / `KATVector` | Parser do formato NIST KAT | — |
| `dataset_generator.py` (458 linhas) | `AsconDatasetGenerator`, `DatasetConfig`, `GenerationResult` | Gerador genérico de datasets single-class (usado como base pelo gerador 2-classes em `scripts/`) | — |

## 1.1 Ascon-AEAD128 (`ascon_wrapper.py`)

- `KEYBYTES=16`, `NPUBBYTES=16`, `ABYTES=16` → `len(ct) = len(pt) + 16`.
- Compila a extensão cffi (`_ascon_ref`) automaticamente na primeira importação
  via `_ascon_cffi_build.py`, se o `.pyd`/`.so` não existir em `src/crypto/`.
  Não há reimplementação do algoritmo em Python — todo o cálculo roda no C
  compilado.
- `.metadata["binary_sha256"]` — hash do binário compilado, registrado no
  manifesto de cada dataset para rastreabilidade (garante que todos os
  criptogramas de um dataset vieram do mesmo binário).
- `validate_kat()`: itera todos os vetores de `ascon-c/LWC_AEAD_KAT_128_128.txt`
  (1089 vetores), chama `encrypt(key, nonce, pt, ad)` e compara byte a byte com
  o CT esperado. **1089/1089 passam** — coberto por `tests/test_ascon_wrapper.py`.
- Erros: `ValueError` para key/nonce de tamanho errado; `AuthenticationError`
  (definida aqui, reexportada por `gift_cofb_wrapper.py`) quando a tag AEAD
  falha na verificação.

## 1.2 GIFT-COFB (`gift_cofb_wrapper.py`)

- Mesmos `KEYBYTES/NPUBBYTES/ABYTES=16`. Interface idêntica ao Ascon (ambos
  implementam a API SUPERCOP `crypto_aead_encrypt`/`crypto_aead_decrypt`).
- Backend `opt32` (implementação de referência otimizada para 32 bits) via
  cffi, compilado por `_gift_cofb_cffi_build.py`.
- **Detalhe de compilação relevante (registrado em memória, verificado ainda
  válido):** o código `opt32` original usa GCC *statement expressions*
  (`({ ... })`), que o MSVC não suporta. A correção foi isolar headers
  MSVC-compatíveis em `src/crypto/_gift_cofb_msvc/` (macros void viram
  `do {} while(0)`, macros de valor viram `static __inline`), forçados via
  `/FI` no build script. Isso não é um detalhe cosmético: é o motivo pelo qual
  o GIFT-COFB compila no Windows com MSVC sem alterar a implementação de
  referência original.
- KAT: `data/kat/LWC_AEAD_KAT_GIFTCOFB128_128.txt` (1089 vetores, gerado por
  `scripts/generate_gift_cofb_kat.py` porque não vinha no repositório de
  referência). **1089/1089 passam.**

## 1.3 Controles positivos

### AES-128-ECB (`aes_ecb_wrapper.py`) — legado

- Pertence ao **protocolo antigo** (datasets `control_3class_v1`,
  `control_repetitive_3class_v1`), hoje substituído pelo Vigenère como controle
  positivo principal — ver [04_datasets.md](04_datasets.md). O wrapper e os
  testes continuam no repositório e funcionam; não está quebrado, só não é
  mais usado no fluxo de dataset vivo.
- Estruturalmente diferente das cifras-alvo por construção (isso é
  intencional — o controle precisa ser trivialmente distinguível quando há
  sinal): **sem nonce** (parâmetro aceito e ignorado), **sem tag**, padding
  PKCS7 até múltiplo de 16 bytes, `len(ct) = len(pt_padded)` em vez de
  `len(pt)+16`, determinístico (mesma chave + mesmo PT → sempre o mesmo CT).

### Vigenère-XOR (`vigenere_wrapper.py`) — controle atual

- `CT[i] = PT[i] XOR key[i % 4]` — XOR cíclico com chave efetiva de **25 bits**
  (codificada em 4 bytes, mas só os 25 bits menos significativos são usados
  via `KEY_MASK = (1 << 25) - 1`). `decrypt == encrypt` (XOR é sua própria
  inversa).
- Sem nonce, sem tag, sem AD — `NPUBBYTES=0`, `ABYTES=0`.
- Existe exclusivamente como controle positivo (docstring é explícito: "NUNCA
  usar em produção"). A periodicidade de 4 bytes é o sinal que o pipeline deve
  conseguir detectar — e detecta (ver [07_resultados.md](07_resultados.md)).

## 1.4 KAT parser (`kat_parser.py`)

Parser de formato NIST puro (blocos `Count/Key/Nonce/PT/AD/CT` separados por
linha em branco). `PT`/`AD` podem ser vazios; campos obrigatórios são
`Count/Key/Nonce/CT` — bloco incompleto levanta `ValueError` citando o `Count`
faltante. Usado tanto pelo Ascon quanto pelo GIFT-COFB (`validate_kat()` de
ambos importa daqui).

## 1.5 Gerador de dataset genérico (`dataset_generator.py`)

`AsconDatasetGenerator` + `DatasetConfig` é a base sobre a qual o gerador
2-classes de produção (`scripts/generate_2class_dataset.py`,
`generate_2class_50k.py`) foi construído — mas hoje só é usado diretamente
pelos scripts single-class legados (`generate_pilot_dataset.py`,
`generate_ascon_parquet.py`, etc., ver [05_scripts.md](05_scripts.md)).

Pontos de design que valem registro:

- **Duas RNGs numpy separadas e determinísticas**: `_key_rng` (seed +
  `key_seed_offset`) e `_pt_rng` (seed + `key_seed_offset + 500`) — chaves e
  amostragem de plaintext nunca compartilham estado aleatório, mesmo com a
  mesma seed base.
- **Nonce = contador global** (`nonce_counter.to_bytes(16, "big")`,
  incrementado a cada amostra do dataset inteiro, não por chave) — garante
  unicidade sem depender de sorteio.
- `_PlaintextGenerator.sample(length)`: lê todos os `.txt` ≥1000 bytes de
  `corpora_dir`, normaliza espaços/quebras de linha, sorteia um trecho exato
  de `length` bytes validado como UTF-8 (até 2000 tentativas; se falhar todas,
  cai num fallback ASCII fixo repetitivo — nunca visto acontecer em uso
  normal com o corpus Gutenberg, mas existe).
- `GenerationResult.save()` grava o parquet público (sem PT/key/nonce) em
  `out_dir`, e chaves/nonces/plaintexts brutos em `interim_dir` — separação
  física que torna impossível acidentalmente treinar com dados que deveriam
  ficar ocultos, e que reforça a Regra de Ouro 5 do `CLAUDE.md` (`len_pt`/
  `len_ct` são metadados, plaintext nunca entra no parquet final).
- `_build_manifest()` registra `git rev-parse --short HEAD`, o SHA-256 do
  binário cffi usado, e resultado do KAT — cada dataset carrega proveniência
  completa do binário que o gerou.
