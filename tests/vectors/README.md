# Vetores de teste externos

## `ctr_drbg_aes128_nodf.json`

240 casos oficiais NIST CAVP (Cryptographic Algorithm Validation Program),
suíte DRBGVS (DRBG Validation System), extraídos da seção `[AES-128 no df]`
de `CTR_DRBG.txt` — configuração AES-128, sem função de derivação, sem
resistência a predição (16 subgrupos de comprimento de
`PersonalizationString`/`AdditionalInput` × 15 casos cada).

- **Fonte:** `csrc.nist.gov/CSRC/media/Projects/Cryptographic-Algorithm-Validation-Program/documents/drbg/drbgtestvectors.zip`
  (arquivo `drbgvectors_pr_false/CTR_DRBG.txt`), conforme listado na página
  do CAVP para geradores de números aleatórios
  (`csrc.nist.gov/projects/cryptographic-algorithm-validation-program/random-number-generators`).
  Especificação normativa correspondente: NIST SP 800-90A Rev.1 §10.2.1.
- **Extraído em:** 2026-08-21, via `scripts` ad-hoc de parsing (não versionado
  — o `.txt` bruto tem ~51k linhas cobrindo 3KeyTDEA/AES-128/192/256 × use-df/
  no-df; só a seção `[AES-128 no df]` foi convertida para este JSON).
- **Formato de cada caso:** `entropy_input`, `personalization_string`,
  `entropy_input_reseed`, `additional_input_reseed`, `additional_input_1`
  (usado na 1ª chamada de generate, descartada), `additional_input_2`
  (usado na 2ª chamada, comparada), `returned_bits` (saída esperada da 2ª
  chamada de generate) — todos em hex. O CAVP testa duas chamadas
  consecutivas de generate propositalmente, para validar a transição de
  estado (Key, V) entre chamadas, não só uma instanciação isolada.
- **Uso:** `tests/test_ctr_drbg.py::test_cavp_vectors` — valida
  `CTRDRBGCore` (Instantiate → Reseed → Generate × 2) byte-a-byte contra
  os 240 casos. Estado em 2026-08-21: **240/240 passam**.
