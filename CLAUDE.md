# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## CONTEXTO DO PROJETO

Dissertação de mestrado (IME-RJ, orientador Xexéo) sobre classificação de algoritmos LWC AEAD via ML em cenário ciphertext-only.

**Pergunta:** criptogramas de Ascon-AEAD128 e GIFT-COFB são distinguíveis por ML sem acesso à chave ou ao plaintext?

**4 caminhos experimentais:**
- A: 307 features clássicas → RF/SVM/LinearSVC/XGBoost/LR
- B: CNN 1D como extrator de features → latent → classificador
- C: CNN 2D como extrator de features → latent → classificador
- D: Híbrido — [307D] + [latent B] + [latent C] → classificador

Os 4 caminhos já foram executados no dataset principal (60k/64KB) e convergem
para H₀ (F1≈0,50). Referência técnica completa e atualizada, incluindo
resultados, catálogo de scripts/testes e pendências conhecidas:
**`docs/analise_completa/`** (gerado 2026-08-16; ver `README.md` daquela pasta
antes de assumir que este arquivo ou `CONTEXTO_ARTIGO.md` estão 100% atuais).

**Experimento v2 (planejado 2026-08-21, implementação em andamento):** 4
algoritmos (Ascon-AEAD128 corrigido p/ `ascon128av13`, GIFT-COFB,
Grain-128AEAD, Schwaemm256-128) + AES-ECB como controle, dataset encadeado de
150k (80% texto/20% imagem), 6 caminhos (A–F: +Transformer hierárquico, +meta-
classificador), features ampliadas (NIST SP 800-22 completo), seletor
redesenhado, RNG de geração CTR_DRBG (SP 800-90A). Plano completo:
**`docs/plano_experimento_v2/`** (ver `06_implementacao_passo_a_passo.md` para
o estado fase-a-fase). **Fase 1 (fundações criptográficas) concluída
2026-08-21:** os 4 algoritmos LWC + CTR_DRBG estão implementados e validados
por KAT/CAVP oficial (182/182 testes passando).

---

## COMANDOS DE DESENVOLVIMENTO

### Build (extensões C via CFFI + MSVC)

```bat
build_cffi.bat          :: Compila Ascon → src/crypto/_ascon_ref.cp314-win_amd64.pyd
build_gift_cofb.bat     :: Compila GIFT-COFB → src/crypto/_gift_cofb_ref.cp314-win_amd64.pyd
build_grain.bat         :: Compila Grain-128AEAD → src/crypto/_grain_ref.cp314-win_amd64.pyd
build_sparkle.bat       :: Compila Schwaemm256-128 → src/crypto/_sparkle_ref.cp314-win_amd64.pyd
```

Requer MSVC 2022 Build Tools e venv ativado. Os `.pyd` já compilados estão em `src/crypto/`.

### Testes

```bash
pytest tests/ -v                                      # todos os 182 testes
pytest tests/test_ascon_wrapper.py -v                 # um módulo
pytest tests/test_extractor.py::test_histogram -v     # um teste específico
pytest tests/ --timeout=30                            # com timeout
```

`conftest.py` na raiz adiciona `src/` e `src/crypto/` ao `sys.path` — nenhuma instalação necessária.

### Geração de dataset e experimentos

```bash
python scripts/generate_2class_dataset.py   # gerar dataset Ascon vs GIFT-COFB
python scripts/run_experiment_2class.py     # treinar os 4 caminhos ML
python scripts/run_experiment_60k_cv.py     # cross-validation no dataset 60K
python scripts/validate_all_datasets.py     # checa apenas existência+manifest de 2 datasets legados hardcoded
```

⚠️ Os checks reais de χ², nonces, compressão e decrypt spot-check (protocolo descrito
abaixo) estão em `scripts/validate_2class_60k.py` (dataset principal) e
`scripts/validate_pilot_dataset.py`/`validate_3class_*.py` (legados) — não em
`validate_all_datasets.py`. Ver `docs/analise_completa/05_scripts.md`.

---

## REGRAS DE OURO (NUNCA VIOLAR)

1. **Seeds fixas:** split=42, modelo=7, FS=13, bootstrap=42
2. **Key-holdout:** chaves de teste NUNCA aparecem no treino. Split 80/20 por chave.
3. **CV 5-fold dentro do treino:** estratificado por chave (192 treino / 48 val por fold)
4. **Feature selection dentro do fold:** MI → mRMR → Boruta APENAS no treino de cada fold
5. **len_pt/len_ct NÃO são features:** são metadados, nunca entram no modelo
6. **Mesmos plaintexts, chaves e nonces** para TODOS os algoritmos comparados (encadeamento)
7. **Relato imediato (pedido do orientador):** toda métrica é impressa no console assim que calculada, e matriz de confusão é SEMPRE gerada (console + JSON + PNG), em todo modelo/fold/caminho — via função de relato única, com gravação incremental em disco
8. **Geração pseudoaleatória (v2):** chaves e amostragem de plaintext via CTR_DRBG (NIST SP 800-90A, AES, seed fixa), validado contra vetores CAVP — não usar NumPy para material criptográfico de teste

---

## DATASET

### v1 — `keyholdout_2class_60k_v1` (executado, concluído)

| Parâmetro | Valor |
|-----------|-------|
| Corpus | Project Gutenberg (SPGC) apenas |
| Total | 60.000 amostras (30.000 por algoritmo) |
| Plaintext | 64 KB fixo |
| Chaves | 300 (seed=42), key_seed_offset=2000 |
| Amostras | 100 por chave por algoritmo |
| Nonces | Contador global 128 bits |
| AD | b"" (vazio) |
| Split | 240 chaves treino+val / 60 chaves teste |

### v2 (planejado — ver `docs/plano_experimento_v2/01_algoritmos_e_dataset.md`)

| Parâmetro | Valor |
|-----------|-------|
| Total | 150.000 (300 chaves × 100 slots × 5 algoritmos encadeados) |
| Plaintext | 64 KB fixo; 80% SPGC / 20% ImageNet 256×256 grayscale (sorteio por amostra) |
| Chaves | 300, key_seed_offset=6000, geradas via CTR_DRBG |
| Grain-128AEAD | nonce 96 bits, tag 64 bits → len_ct=65.544 (truncamento é etapa de ANÁLISE, nunca de geração) |
| AES-ECB | controle; mesma linha encadeada; sem nonce; len_ct=65.552 (PKCS7 bloco cheio) |

**Metadados obrigatórios em todo parquet:**
`{algorithm, mode, impl, key_id, nonce_id, len_pt, len_ct, len_ad, plaintext_source, seed, version, timestamp}`

Plaintexts e chaves NÃO ficam no parquet final — ficam em `data/interim/` só para validação.

---

## ARQUITETURA DO CÓDIGO

### `src/crypto/`
- **ascon_wrapper.py** — CFFI binding para Ascon-AEAD128 (`ascon128av13`, taxa 128/SP 800-232 final). API: `AsconAEAD128.encrypt()`, `.decrypt()`, `.validate_kat()`. 1089 KATs validados.
- **gift_cofb_wrapper.py** — Idem para GIFT-COFB (`opt32`).
- **grain_wrapper.py** — Idem para Grain-128AEAD (cifra de fluxo LFSR+NFSR; `KEYBYTES=16, NPUBBYTES=12, ABYTES=8` — nonce/tag menores que os demais). 1089 KATs oficiais validados.
- **sparkle_wrapper.py** — Idem para Schwaemm256-128 (esponja ARX, família SPARKLE; `NPUBBYTES=32, ABYTES=16` — maior nonce do conjunto). KAT oficial (submissão NIST) 1089/1089 validado, não autogerado.
- **aes_ecb_wrapper.py** — AES-128-ECB (controle positivo — modo inseguro, deliberado). Interface: `.encrypt()/.decrypt()` com PKCS7; sem nonce/tag.
- **ctr_drbg.py** — CTR_DRBG (NIST SP 800-90A, AES-128, sem função de derivação) para geração determinística de material criptográfico do dataset v2 (chaves, amostragem de plaintext). `CTRDRBGCore` (fiel ao padrão, validado contra 240 vetores CAVP oficiais) + `CTRDRBG` (API de alto nível: `.generate()/.random_key()/.randint()/.choice_bool()`). NÃO é fonte de entropia real — mecanismo determinístico, ver docstring do módulo.
- **vigenere_wrapper.py** — Vigenère XOR (controle positivo legado do v1; aposentado no v2 em favor do AES-ECB). Interface: `encrypt(key, pt) → ct`. Sem nonce/tag/AD.
- **dataset_generator.py** — `DatasetConfig` + `AsconDatasetGenerator`: gera parquets criptografados a partir do corpus Gutenberg (v1, 2 classes; v2 generaliza para N algoritmos — ver `docs/plano_experimento_v2/`).
- **_ascon_cffi_build.py**, **_gift_cofb_cffi_build.py**, **_grain_cffi_build.py**, **_sparkle_cffi_build.py** — Compilam os `.pyd` se ausentes.
- Fontes C de referência (Ascon/GIFT-COFB/Grain/Sparkle) vivem em pastas irmãs na raiz (`ascon-c/`, `gift-cofb/`, `grain-128aead/`, `sparkle/`), todas gitignored — vendorizadas localmente, não fazem parte do histórico do repo.

### `src/features/`
- **extractor.py** — `CiphertextFeatureExtractor`: orquestra 6 famílias → vetor 307D.
- **families/** — Uma classe por família (histogram, entropy, ngrams, autocorrelation, complexity, frequency).
- **selector.py** — `LWCFeatureSelector`: pipeline MI → mRMR (define o conjunto final) → Boruta (diagnóstico de estabilidade, não filtra mais o resultado — mudança de 2026-08, motivada pelo Boruta colapsando o experimento principal para 1 feature; ver `docs/analise_completa/02_features_e_selecao.md`). Deve ser fitado **somente no treino de cada fold**.

**Famílias de features (307D total):**

| Família | Dim | Descrição |
|---------|-----|-----------|
| Histograma | 256 | Frequência de cada byte |
| Entropia | 4 | Shannon, χ² vs. uniforme |
| N-gramas | 15 | Bigrama/trigrama/4-grama agregados |
| Autocorrelação | 18 | ACF lags 1-16 + Runs test |
| Complexidade | 4 | LZ76 + razões zlib/bz2/lzma |
| FFT | 10 | 8 bandas de energia + pico + entropia espectral |

### `src/models/`
- **classical.py** — Pipeline scikit-learn: Dummy, RF, SVM, XGBoost. Scripts de produção (`run_experiment_60k_cv.py`, `run_hybrid_60k.py`) acrescentam LinearSVC; `run_extra_lr_60k.py` acrescenta LogisticRegression reaproveitando os mesmos folds.
- **cnn1d.py** — `CiphertextCNN1D`: Embedding(256, embed_dim) → 3×[Conv1D+BN+ReLU+MaxPool] → GlobalAvgPool → `[LATENT]` → Dropout → FC. Método `extract_latent(x)` obrigatório. Para `max_len≥16384` (CT completo, 65552 bytes), o 1º bloco usa kernel=8/stride=4 em vez de kernel=3/stride=1.
- **cnn2d.py** — `CiphertextCNN2D`: 3×[Conv2D+BN+ReLU+MaxPool] → GlobalAvgPool → `[LATENT]` → FC. Não usar pesos pré-treinados. Representação de entrada canônica (`ciphertext_to_image.py::bytes_to_cooccurrence`): mapa de co-ocorrência de bigramas 256×256, CT completo; o reshape linear 32×32 (`ciphertext_to_image`) é legado, mantido só para experimentos antigos.
- **cnn_trainer.py** / **cnn2d_trainer.py** — Trainers do protocolo legado (key-holdout simples, sem CV). O treino de produção no dataset 60k usa a infraestrutura em `hybrid.py` (`train_cnn`/`train_cnn_fixed`, com checkpoint por época e resume).
- **ciphertext_to_image.py** — `bytes_to_cooccurrence` (canônica, 256×256) + `ciphertext_to_image` (legado, reshape linear 32×32).
- **hybrid.py** — Implementado: `HybridExtractor`/`HybridConfig` concatenam [307D] + [latent CNN1D 512D] + [latent CNN2D 128D] = 947D → RF/XGB. Runner: `scripts/run_hybrid_60k.py`.

### `src/eval/`
- **metrics.py** — `compute_metrics()`: F1-macro, balanced accuracy, bootstrap CI (seed=42), ECE, McNemar test.

---

## CNN — MODO EXTRATOR

Ambas as CNNs devem:
1. Ter método `model.extract_latent(x)` que retorna o vetor antes do FC.
2. Ser treinadas com cross-entropy para guiar a representação.
3. Ter pesos congelados ao serem usadas no Caminho D.
4. `max_len` para 64KB: 65552 bytes (65536 + 16 tag). CNN2D: 256×256 pixels.

---

## PROTOCOLO DE VALIDAÇÃO DO DATASET

Para cada parquet gerado:
1. Nonces únicos por chave
2. χ² rejeição < 10% (α=0.05, CT ≥ 256 bytes)
3. Compressão média ~1.0×
4. Decrypt spot-check: 100 amostras aleatórias, 100% corretas
5. Manifesto JSON com SHA-256 do binário, seed, parâmetros, resultado KAT

---

## FORMATO DE RELATÓRIO (após cada tarefa)

1. Arquivos criados/modificados (com nº de linhas)
2. Decisões de design (com justificativa)
3. Outputs do terminal (completos)
4. Pendências e limitações conhecidas
5. Como reproduzir (comando único)
