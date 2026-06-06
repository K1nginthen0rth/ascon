# CONTEXTO_ARTIGO.md — Fonte única de verdade para o artigo

**Projeto:** Atribuição de Algoritmos de Criptografia Leve (LWC) em cenário *ciphertext-only* via Machine Learning
**Dissertação:** Mestrado IME-RJ (orientador Xexéo)
**Pergunta de pesquisa:** Criptogramas de **Ascon-AEAD128** e **GIFT-COFB** são distinguíveis por ML sem acesso à chave ou ao plaintext?
**Hipóteses:** H₀ — cifras LWC padronizadas NIST são praticamente indistinguíveis em cenário ciphertext-only; H₁ — existem assinaturas residuais exploráveis por ML.
**Documento gerado a partir do repositório em:** `c:\Users\nycol\Documents\Mestrado\ascon`
**Data da extração:** 2026-06-04

> Princípio orientador (Cap. 1 da proposta): *"Em ambos os desfechos (H₀ ou H₁), o trabalho é útil: ou fornece evidência empírica a favor da robustez dos esquemas LWC, ou identifica pontos de melhoria. Rigor é mais importante que acurácia alta."*

> ⚠️ **AVISO DE STATUS (crítico para o artigo):** O experimento principal **60k (Caminho A — features clássicas)** está **concluído**. Os **Caminhos B (CNN1D), C (CNN2D) e D (Híbrido) sobre o dataset 60k NÃO foram executados** (diretórios `reports/keyholdout_2class_60k_v1_cnn/` e `_hybrid/` contêm apenas pastas `ckpts/` e `confusion_matrices/` vazias). Os resultados de CNN reportados neste documento (B e C) vêm de **datasets anteriores (15k e 50k, protocolo antigo)**. Ver §9 e §13.

---

## 1. VISÃO GERAL DO REPOSITÓRIO

### 1.1 Árvore de diretórios (2 níveis, principais)

```
ascon/
├── CLAUDE.md                       # Instruções do projeto (regras de ouro, dataset, arquitetura)
├── LICENSE
├── build_cffi.bat / build_gift_cofb.bat   # Build das extensões C (MSVC)
├── conftest.py                     # Adiciona src/ e src/crypto/ ao sys.path
├── run_tests.bat
├── mrmr.py                         # (shim/util local)
├── ascon-c/                        # Implementação de referência C do Ascon + KATs NIST
├── gift-cofb/                      # Implementação de referência C do GIFT-COFB
├── data/
│   ├── raw/corpora/                # Plaintexts (Project Gutenberg, .txt)
│   ├── interim/                    # keys.json, nonces.json, plaintexts.parquet (validação)
│   ├── kat/                        # LWC_AEAD_KAT_GIFTCOFB128_128.txt
│   └── processed/                  # parquets públicos + manifests + splits + features
├── docs/
│   ├── CONTEXTO_PARA_CLAUDE_WEB.md (399 linhas)
│   ├── contexto_inicial.md         (191 linhas) — papers, decisões, referências
│   └── relatorio_para_claude.md    (78 linhas)  — template de relatório
├── scripts/                        # ~45 scripts de geração/experimento/validação
├── src/
│   ├── crypto/                     # wrappers Ascon, GIFT-COFB, AES-ECB, Vigenère + cffi builds
│   ├── features/                   # extractor + families/ + selector
│   ├── models/                     # cnn1d, cnn2d, hybrid, classical, trainers, ciphertext_to_image
│   └── eval/                       # metrics
├── tests/                          # 130 testes pytest (10 módulos)
└── reports/                        # outputs de experimentos (gitignored)
```

110 arquivos versionados no git (`git ls-files`). `reports/`, `data/`, `.venv/`, `*.log` são **gitignored**.

### 1.2 Dependências e versões

⚠️ **NÃO ENCONTRADO:** não há `requirements.txt`, `environment.yml`, `pyproject.toml`, `setup.cfg` nem `setup.py`. As dependências são instaladas no venv manualmente. O notebook Kaggle instala via pip (ver §10).

Versões críticas (de `.venv/Scripts/python.exe -m pip freeze`):

| Lib | Versão |
|-----|--------|
| Python | **3.14.3** |
| numpy | 2.4.3 |
| scipy | 1.17.1 |
| scikit-learn | 1.8.0 |
| xgboost | 3.2.0 |
| torch | **2.11.0+cpu** (CPU local; GPU no Kaggle) |
| pandas | 3.0.1 |
| pyarrow | 24.0.0 |
| cffi | 2.0.0 |
| cryptography | 47.0.0 |
| Boruta | 0.4.3 |
| mrmr-selection | 0.2.8 |
| matplotlib | 3.10.9 |

⚠️ TensorFlow **não** é usado (só PyTorch). MLflow é opcional (graceful fallback se ausente).

### 1.3 Build das extensões C

```bat
build_cffi.bat          :: Ascon  → src/crypto/_ascon_ref.cp314-win_amd64.pyd
build_gift_cofb.bat     :: GIFT-COFB → src/crypto/_gift_cofb_ref.cp314-win_amd64.pyd
```
Requer MSVC 2022 Build Tools. Os `.pyd` compilam-se automaticamente na 1ª importação via cffi se ausentes.

---

## 2. ALGORITMOS E IMPLEMENTAÇÕES CRIPTOGRÁFICAS

### 2.1 Algoritmos implementados

| Algoritmo | Papel | Wrapper | Backend | Impl |
|-----------|-------|---------|---------|------|
| **Ascon-AEAD128** | Classe alvo (NIST SP 800-232) | `src/crypto/ascon_wrapper.py` | C via **cffi** | `ref` |
| **GIFT-COFB** | Classe alvo (NIST LWC Round 2 finalist) | `src/crypto/gift_cofb_wrapper.py` | C via **cffi** | `opt32` |
| **AES-128-ECB** | Controle positivo (inseguro, detectável) | `src/crypto/aes_ecb_wrapper.py` | `cryptography` (OpenSSL) | `python` |
| **Vigenère-XOR** | Controle positivo (estrutura residual) | `src/crypto/vigenere_wrapper.py` | Python puro | `python` |

- **Linkagem:** Ascon e GIFT-COFB usam **CFFI** (não ctypes/subprocess). O código cripto roda inteiramente na extensão C compilada (`_ascon_ref`, `_gift_cofb_ref`). Build scripts: `src/crypto/_ascon_cffi_build.py`, `src/crypto/_gift_cofb_cffi_build.py`.
- **API uniforme:** `.encrypt(key, nonce, pt, ad) → ct`, `.decrypt(...)`, `.validate_kat()`. `AuthenticationError` compartilhada.

### 2.2 Parâmetros fixos (Ascon-AEAD128 / GIFT-COFB)

- **Chave:** 16 bytes (128 bits)
- **Nonce:** 16 bytes (128 bits) — contador global
- **Tag:** 16 bytes (`ABYTES=16`) → `len_ct = len_pt + 16`
- **AD:** vazio (`b""`) em todos os datasets principais

**Controles (diferença estrutural intencional):** AES-ECB → sem nonce, sem tag, padding PKCS7, `len_ct = len(PT padded)`, determinístico. Vigenère → chave de **25 bits efetivos** (4 bytes), `CT[i] = PT[i] XOR key[i%4]`, sem nonce/tag/AD.

### 2.3 Validação KAT (NIST Known-Answer Tests)

| Algoritmo | Arquivo KAT | Registros | Resultado |
|-----------|-------------|-----------|-----------|
| Ascon-AEAD128 | `ascon-c/LWC_AEAD_KAT_128_128.txt` | 1089 | **1089/1089 passed** (registrado no manifesto) |
| GIFT-COFB | `data/kat/LWC_AEAD_KAT_GIFTCOFB128_128.txt` | **1089** (`grep -c "^Count = "`) | validado pelo wrapper `.validate_kat()` |

Método: `AsconAEAD128.validate_kat(kat_path)` retorna `(total, passed, failed)`. Testado em `tests/test_ascon_wrapper.py` (15 testes) e `tests/test_gift_cofb_wrapper.py` (16 testes).

**SHA-256 dos binários cffi** (registrados no manifesto do 60k):
- Ascon `ref`: `c657b6f0d90b95a3ccab032e0e701cd8db02166b5f41c61794ac5dfb952cc862`
- GIFT-COFB `opt32`: `c2c4e6f39dabf6ac6076f0bf1c7dc44ca337faf7818b5bf5fe8734eb5b37dc25`

---

## 3. GERAÇÃO DE DATASET

### 3.1 Scripts e dataset principal

- **Gerador genérico:** `src/crypto/dataset_generator.py` (`DatasetConfig` + `AsconDatasetGenerator`).
- **Gerador 2-classes (usado no principal):** `scripts/generate_2class_dataset.py` (`TwoClassConfig` + `generate_2class()`).
- **Dataset principal:** `keyholdout_2class_60k_v1`.

**Parâmetros do 60k** (de `data/processed/keyholdout_2class_60k_v1_manifest.json`):

| Parâmetro | Valor |
|-----------|-------|
| Total de amostras | **60.000** (30.000 Ascon + 30.000 GIFT-COFB) |
| n_keys | **300** |
| pt_sizes | **[65536]** (64 KB fixo) |
| samples_per_key_size | 100 |
| AD | vazio |
| Nonce | `global_counter_shared_per_pair` |
| seed | 42 |
| key_seed_offset | **2000** |
| plaintext_source | corpus (100%) |
| total_ciphertext_bytes | 3.933.120.000 (~3.93 GB) |
| generation_elapsed_s | 35.23 |
| generator_version (git) | `c6ec3b6` |

> Nota: o `len_ct` por amostra = 65536 + 16 = **65552 bytes**.
> O CLAUDE.md descreve "offset=1000 entre algoritmos" e "300 chaves (seed=42)"; no 60k o `key_seed_offset` registrado é **2000** (cada par usa a mesma chave/nonce/PT para ambos os algoritmos — a diferença é puramente algorítmica).

### 3.2 Fonte de plaintexts

- **Corpus:** Project Gutenberg (SPGC), arquivos `.txt` em `data/raw/corpora/`.
- **Amostragem** (`_PlaintextGenerator.sample`, [dataset_generator.py:62](src/crypto/dataset_generator.py#L62)): lê `.txt` UTF-8 ≥1000 bytes, normaliza espaços/quebras, sorteia trecho de exatamente `length` bytes UTF-8-válido via `numpy.random.Generator`. Fallback ASCII se falhar 2000 tentativas.
- RNGs determinísticas separadas: chaves `seed+offset`; plaintexts `seed+offset+500`.

### 3.3 Formato de saída (parquet público)

Colunas (de `_generate_samples`, [dataset_generator.py:301](src/crypto/dataset_generator.py#L301)):
`sample_id, algorithm, mode, impl, key_id, nonce_id, len_pt, len_ad, len_ct, ciphertext, plaintext_source, seed, version, timestamp` + `split` (key-holdout).

- **Plaintext, chave e nonce NÃO ficam no parquet público** — vão para `data/interim/{id}_keys.json`, `_nonces.json`, `_plaintexts.parquet` apenas para validação.
- `len_pt`/`len_ct`/`len_ad` são **metadados, nunca features** (verificação anti-vazamento em `classical.py:_verify_no_leakage`).

### 3.4 Datasets versionados em `data/processed/` (todos gitignored)

Principais e controles (parquet + manifest + splits + features):
- `keyholdout_2class_60k_v1` — **principal** (60k, 64 KB, 300 chaves)
- `keyholdout_2class_50k_v1` — 50k (réplica, protocolo antigo)
- `keyholdout_2class_v1` — 15k (50 chaves × 3 tam × 50 × 2)
- `pilot_2class_v1` — 22k piloto (10 chaves × 11 tam × 100 × 2)
- `control_3class_v1` / `control_repetitive_3class_v1` — controles 3-class com AES-ECB
- `control_vigenere_64k_v1`, `control_vigenere_v1`, `vigenere_vs_random` — controles Vigenère
- `ascon_aead128_pilot_v1/v2`, `ascon_aead128_keyholdout_v1/v2`, `ascon_aead128_base_v1` — single-class antigos

### 3.5 Sanity checks (protocolo de validação)

Script: `scripts/validate_all_datasets.py` (+ `validate_2class_50k.py`, `validate_pilot_dataset.py`). Checa:
1. Nonces únicos por chave
2. Rejeição χ² < 10% (α=0.05, CT ≥ 256 bytes)
3. Compressão média ~1.0×
4. Decrypt spot-check: 100 amostras aleatórias, 100% corretas
5. Manifesto JSON com SHA-256 do binário, seed, parâmetros, KAT

⚠️ **NÃO ENCONTRADO:** `keyholdout_2class_60k_v1_validation.json` não existe (o manifesto diz `"sanity_checks": "pending - run scripts/validate_all_datasets.py"`). Caracterização estatística independente existe para os controles (ver §9.4, `reports/control_analysis/`), confirmando entropia ~7.02 bits/byte e IC ~1/256 para Ascon/GIFT.

---

## 4. PIPELINE DE FEATURES (CAMINHO A — 307 features clássicas)

### 4.1 Extrator

- **Código:** `src/features/extractor.py` → `CiphertextFeatureExtractor`. Orquestra 6 famílias (`src/features/families/`). Paralelizado com joblib (`extract_dataset`, n_jobs=-1).
- **Cenário ciphertext-only:** nenhuma família usa plaintext/chave/nonce. `len_pt`/`len_ct` ficam só como metadados.
- Metadados preservados no parquet de features: `sample_id, algorithm, key_id, len_pt, len_ct`.

### 4.2 Lista completa das 307 features

| Família | Dim | Nomes | Fórmula / descrição |
|---------|-----|-------|---------------------|
| **Histograma** | 256 | `byte_hist_000`…`byte_hist_255` | freq. relativa de cada byte = `bincount/len(ct)` |
| **Entropia** | 4 | `shannon_entropy`, `chi2_statistic`, `chi2_pvalue`, `chi2_dof` | Shannon `-Σp·log₂p`; χ² vs uniforme 256 bins (p-value/dof=255 só se len≥16) |
| **N-gramas** | 15 | `ngram_{2,3,4}_{entropy,nunique,max_freq,chi2,collision_rate}` | 5 stats × ordens 2,3,4. collision_rate = `1 − k/256ⁿ` |
| **Autocorrelação** | 18 | `autocorr_lag_01`…`autocorr_lag_16`, `runs_count`, `runs_zscore` | ACF normalizada lags 1–16; teste de runs Wald-Wolfowitz (z-score) |
| **Complexidade** | 4 | `lz_complexity`, `lz_complexity_normalized`, `compression_ratio_zlib`, `compression_ratio_bz2` | LZ76 (nº de frases); razões zlib/bz2 (level 9) |
| **FFT** | 10 | `fft_band_0`…`fft_band_7`, `fft_peak_freq`, `fft_spectral_entropy` | FFT de bytes, 8 bandas de energia (sem DC) + pico normalizado + entropia espectral |

**Total = 256 + 4 + 15 + 18 + 4 + 10 = 307.** Código fonte de cada família em `src/features/families/{histogram,entropy,ngrams,autocorrelation,complexity,frequency}.py`.

NaN tratado como 0 (autocorrelação/FFT/ngrams com CT curto retornam NaN → imputados a 0).

### 4.3 Feature selection — pipeline 3 estágios

**Código:** `src/features/selector.py` → `LWCFeatureSelector` + `SelectorConfig`. **Fit APENAS no treino de cada fold** (regra de ouro anti-vazamento, [Ambroise & McLachlan, PNAS 2002]).

| Estágio | Método | Parâmetro (default `SelectorConfig`) |
|---------|--------|--------------------------------------|
| 1a | `VarianceThreshold` | `variance_threshold=1e-5` |
| 1b | `mutual_info_classif` → top-k | `top_k_mi=200` (300 no Híbrido), `random_state=13` |
| 2 | mRMR `mrmr_classif` (`mrmr-selection`) | `n_features_mrmr=100` (150 no Híbrido) |
| 3 | Boruta `BorutaPy` (RF max_depth=5, class_weight=balanced) | `boruta_max_iter=100`, `random_state=13` |

**Fallback:** se Boruta retornar conjunto vazio, usa-se a saída do mRMR como final.

### 4.4 Resultado da seleção (estabilidade entre folds)

No **60k**, o nº de features sobreviventes ao Boruta varia drasticamente por fold (de `cv_results.json`):

| Fold | Boruta (final) | Observação |
|------|----------------|------------|
| 1 | **1** | stage1: 307→29 (VT)→29 (MI)→29 (mRMR)→1 (Boruta) |
| 2 | 29 | Boruta vazio → fallback mRMR |
| (modelo final no trainval) | **1** | seleção instável; sinal ausente |

**Comparação 15k vs 50k** (`reports/comparison_15k_vs_50k.md`):
- 15k: Boruta → **1 feature** (`fft_band_7`)
- 50k: Boruta → **100 features** (majoritariamente `byte_hist_*`)
- **Features Boruta-validadas em comum entre 15k e 50k: NENHUMA** (Jaccard ≈ 0) → forte indício de **ausência de sinal estável** (features mudam entre tamanhos de amostra = ruído, não assinatura). É exatamente o sintoma de robustez esperado sob H₀.

Selectors dos controles (sinal presente): Vigenère 3-class → 93 features; Vigenère vs random → 100; Controle B (ECB repetitivo) → 39; Controle A (ECB natural) → 49.

---

## 5. PIPELINE CNN-1D (CAMINHO B)

**Código:** `src/models/cnn1d.py` → `CiphertextCNN1D`. **Status 60k: ⚠️ NÃO EXECUTADO** (resultados abaixo são de 15k/50k).

### 5.1 Arquitetura

```
Embedding(256, embed_dim=32)
→ permute → [Conv1D(k=3,pad=1) → BatchNorm1d → ReLU → MaxPool1d(2)] × 3 blocos
   (n_filters dobra: 128 → 256 → 512)
→ AdaptiveAvgPool1d(1)  ← latent (extract_latent), dim = 512
→ Dropout(0.3) → Linear(512 → n_classes)
```
- `latent_dim = 512` (128 × 2² com 3 blocos). Método `extract_latent(x)` retorna o vetor antes do FC.
- Bytes (0–255) tokenizados via Embedding learnable; GAP ignora alinhamento absoluto.
- ~190k parâmetros (embedding 256×32).

### 5.2 Hiperparâmetros (de `run_cnn_experiments_60k.py`)

| Param | Valor |
|-------|-------|
| MAX_LEN_B (Caminho B) | **4096** bytes (prefixo; viável em CPU) |
| MAX_LEN_D_CNN1D (Caminho D) | **65552** bytes (CT completo; requer GPU) |
| batch_size | 64 |
| epochs (máx) | 30 |
| optimizer | Adam, lr=1e-3 |
| loss | CrossEntropy |
| early stopping | patience=5 no `val_loss` (Δ < 1e-4) |
| seed por fold | `SEED_MODEL(7) + fold*100 + 1` |

### 5.3 Uso como extrator (latent → clássico)

Modos: `cnn1d_direct` (end-to-end), `cnn1d_latent_rf` (latent 512D → RandomForest n=300), `cnn1d_latent_lsvc` (latent → LinearSVC C=1.0). Latents passam por StandardScaler (fit no treino).

### 5.4 Resultados (datasets 15k/50k — protocolo antigo, image/byte reshape)

| Dataset | F1-macro | Bal.Acc | Tempo |
|---------|----------|---------|-------|
| 15k (Ascon vs GIFT) | 0.4885 [0.470, 0.506] | 0.5010 | 388s |
| 50k (Ascon vs GIFT) | 0.3333 [0.330, 0.336] (colapso) | 0.5000 | 2190.7s |
| Controle A (ECB natural, 3-class) | 0.3363 | 0.3370 | 2826s |
| Controle B (ECB repetitivo, 3-class) | 0.2841 (colapso) | 0.3984 | 1959s |

> A CNN1D **não detectou** o sinal de ECB no Controle B (estagnou em bal.acc 0.40, abaixo dos clássicos) — limitação do prefixo/representação 1D nesse protocolo.

### 5.5 Positive control AES-ECB
Ver §9.4. Os modelos clássicos e a CNN2D detectam ECB; a CNN1D não (no protocolo antigo).

---

## 6. PIPELINE CNN-2D (CAMINHO C)

**Código:** `src/models/cnn2d.py` → `CiphertextCNN2D`; representação em `src/models/ciphertext_to_image.py`. **Status 60k: ⚠️ NÃO EXECUTADO**.

### 6.1 Representação de entrada

- **Canônica (atual):** `bytes_to_cooccurrence(ct)` → **mapa de co-ocorrência de bigramas 256×256**. `pixel[i,j] = freq(byte i seguido de byte j)/total_pares`, CT completo, O(n) via bincount. Adjacência **real** (só bytes consecutivos).
- **Legada (experimentos 15k/50k antigos):** `ciphertext_to_image(ct, 32)` → reshape linear 32×32 normalizado /255. Impõe adjacência artificial (limitação documentada).

### 6.2 Arquitetura

```
Input (batch, 1, H, W)
[Conv2D(1→32,3×3,pad1) → BN → ReLU → MaxPool(2)]
[Conv2D(32→64,3×3,pad1) → BN → ReLU → MaxPool(2)]
[Conv2D(64→128,3×3,pad1) → BN → ReLU → MaxPool(2)]
→ AdaptiveAvgPool2d(1)  ← latent dim = 128
→ Dropout(0.3) → Linear(128 → n_classes)
```
~94k parâmetros. Treino **do zero** (sem pesos ImageNet — irrelevantes para ruído). `extract_latent` → 128D.

### 6.3 Hiperparâmetros
Idênticos à CNN1D (batch 64, 30 epochs, Adam lr=1e-3, patience 5, seed por fold `7 + fold*100 + 2`). Modos: `cnn2d_direct`, `cnn2d_latent_rf`, `cnn2d_latent_lsvc`.

### 6.4 Resultados (15k legado, reshape 32×32)

| Experimento | F1-macro | Bal.Acc | Tempo | Leitura |
|-------------|----------|---------|-------|---------|
| Ascon vs GIFT 15k | 0.3380 [0.330, 0.348] | 0.5013 | 52.4s | **colapso p/ classe GIFT** (2990/3000 preditos GIFT); ECE=0.0113 |
| Controle B (ECB repetitivo, 3-class) | 0.6717 [0.663, 0.680] | 0.6718 | 200.2s | **detecta AES-ECB 3006/3006 (100%)** |

Matriz de confusão CNN2D, Ascon vs GIFT 15k:
```
              pred:Ascon   pred:GIFT
true:Ascon          7        1493
true:GIFT           3        1497
```
Matriz CNN2D Controle B (3-class):
```
                 pred:AES-ECB  pred:Ascon  pred:GIFT
true:AES-ECB        3006           0          0
true:Ascon             0        1553       1453
true:GIFT              0        1507       1499
```
Loss travou em log(2)≈0.693 no Ascon vs GIFT (entropia binária máxima = não aprende nada). No Controle B convergiu para o teto teórico (1 classe perfeita + 2 no acaso → F1≈0.67). CNN2D é ~8× mais rápida que CNN1D.

---

## 7. PIPELINE HÍBRIDO (CAMINHO D)

**Código:** `src/models/hybrid.py` → `HybridExtractor` + `HybridConfig`; runner `scripts/run_hybrid_60k.py`. **Status: ⚠️ NÃO EXECUTADO (pendente, requer GPU).**

### 7.1 Design

- Vetor combinado = `[307D clássicas | latent CNN1D (512D) | latent CNN2D (128D)]` = **947D**.
- CNN1D usa **CT completo (65552 bytes)** se GPU disponível (`MAX_LEN_D_CNN1D`), senão prefixo 4096 (apenas debug — resultados não comparáveis). CNN2D usa co-ocorrência 256×256 (CT completo).
- Após concatenar: `LWCFeatureSelector` (top_k_mi=300, mrmr=150, Boruta) **dentro do fold** → RF(500) e XGBoost(500).
- Nomes: `feat_cols + latent1d_0..511 + latent2d_0..127`.

### 7.2 Infraestrutura (resiliência a spot/preempção)

- Datasets lazy (bytes→tensor no `__getitem__`), `num_workers=4`, `persistent_workers=True`, `worker_init_fn` para seed.
- **Checkpoint por época** (`ckpt_dir`), **resume automático** do último checkpoint (estado do modelo + optimizer + RNG).
- MLflow logging opcional (train_loss/val_loss/val_f1_macro por época).
- Seeds por fold: `seed_model(7) + fold*100 + {1 (1d), 2 (2d)}`.

### 7.3 Dependências
GPU recomendada (CNN1D sobre 65552 bytes é inviável em CPU). Executado no Kaggle T4 via `kaggle_notebook_lwc_1.py` (ver §10).

---

## 8. CROSS-VALIDATION E SPLITS

### 8.1 Protocolo (experimento 60k — `run_experiment_60k_cv.py`)

- **Split externo 80/20 key-holdout:** o split file original (60/20/20: `train_keys`=180, `val_keys`=60, `test_keys`=60) é **fundido** em `trainval` (train+val = **240 chaves**) vs `test` (**60 chaves**).
- **CV interno:** **5-fold `GroupKFold`** sobre o trainval, grupo = `key_id` → **192 chaves treino / 48 chaves val por fold** (38.400 treino / 9.600 val amostras).
- **Feature selection roda DENTRO de cada fold** (fit só no treino). StandardScaler também (para LinearSVC/SVM).
- **Modelo final:** treinado no trainval completo (240 chaves), avaliado no test holdout (60 chaves, 12.000 amostras). Bootstrap 1000× para IC 95%.

### 8.2 Variável de grupo e garantia de não-vazamento

Grupo = `key_id`. Verificações de vazamento **explícitas e redundantes** no código:
- `prepare_data()`: `overlap = tv_keys & tst_keys; if overlap: raise ValueError(...)` ([run_experiment_60k_cv.py:228](scripts/run_experiment_60k_cv.py#L228))
- Dentro do loop CV: `assert not (tr_keys & val_keys), "vazamento de chave!"`
- `classical.py`: `_verify_no_leakage` (len_pt/len_ct/len_ad fora) + checagem `kt & ke or kt & kv or kv & ke`.

### 8.3 Trecho do split CV (copiado)

```python
gkf = GroupKFold(n_splits=N_FOLDS)         # N_FOLDS=5
groups = trainval_df["key_id"].to_numpy()
for fold_idx, (tr_idx, val_idx) in enumerate(gkf.split(X_all, y_all, groups)):
    tr_keys  = set(groups[tr_idx]); val_keys = set(groups[val_idx])
    assert not (tr_keys & val_keys), f"Fold {fold_num}: vazamento de chave!"
    # FS fit só no treino do fold:
    sel = LWCFeatureSelector(SELECTOR_CFG); sel.fit(X_tr, y_tr, feature_names=feat_cols)
    X_tr_sel = sel.transform(X_tr); X_val_sel = sel.transform(X_val)
    scaler = StandardScaler().fit(X_tr_sel)   # scaler só no treino
```

### 8.4 Seeds fixas (regra de ouro)

`split=42`, `modelo=7`, `FS=13`, `bootstrap=42`. CNN: seed por fold = `7 + fold*100 + offset`.

---

## 9. RESULTADOS EXPERIMENTAIS

### 9.1 Caminho A — 60k (PRINCIPAL, concluído) — `reports/keyholdout_2class_60k_v1_cv/`

Test holdout = 12.000 amostras. Baseline acaso = **0.5000**. Bootstrap 1000× (seed 42).

| Modelo | Features | F1 CV (mean±std) | F1 test | IC 95% | BalAcc | t treino |
|--------|----------|------------------|---------|--------|--------|----------|
| RF | 1 | 0.4971 ± 0.0067 | 0.5011 | [0.492, 0.510] | 0.5011 | 11.2s |
| SVM (GridSearch RBF) | 1 | 0.4860 ± 0.0316 | 0.5012 | [0.492, 0.510] | 0.5017 | 390.0s |
| LinearSVC | 1 | 0.5002 ± 0.0041 | 0.5024 | [0.494, 0.511] | 0.5024 | 0.0s |
| XGBoost | 1 | 0.4984 ± 0.0043 | 0.4952 | [0.487, 0.504] | 0.4952 | 0.3s |
| LR | 1 | 0.5011 ± 0.0033 | 0.5024 | [0.494, 0.511] | 0.5024 | 0.0s |

**Todos os IC 95% cobrem 0.500 → H₀ confirmada no Caminho A 60k.**

McNemar (correção de continuidade + **Bonferroni**, α=0.0050): **nenhum par significativo** (todos p > 0.23):

| Comparação | estatística | p-value | Sig? |
|------------|-------------|---------|------|
| RF vs SVM | 0.006 | 0.9382 | não |
| RF vs LinearSVC | 0.038 | 0.8459 | não |
| RF vs XGBoost | 0.875 | 0.3496 | não |
| RF vs LR | 0.038 | 0.8459 | não |
| LinearSVC vs LR | 0.000 | 1.0 | não |
| XGBoost vs LR | 1.395 | 0.2375 | não |
| (demais) | — | >0.29 | não |

Modelos: RF(500, max_depth=None, class_weight=balanced), SVM RBF com **GridSearchCV 3-fold** (C∈{0.1,1,10,100}, gamma∈{scale,auto,1e-3,1e-2}), LinearSVC(C=1, max_iter=5000), XGBoost(500, depth=6, lr=0.1, hist), LR.

### 9.2 Caminhos B / C / D — 60k

⚠️ **NÃO EXECUTADOS.** `reports/keyholdout_2class_60k_v1_cnn/` e `_hybrid/` têm apenas `ckpts/` e `confusion_matrices/` vazios — sem `cv_results.json`/`final_results.json`. Devem ser rodados no Kaggle (T4). Ver §10 e §13.

### 9.3 Réplicas Caminho A — 15k e 50k (protocolo anterior) — `reports/comparison_15k_vs_50k.md`

| Modelo | F1 (15k) | IC 95% (15k) | F1 (50k) | IC 95% (50k) |
|--------|----------|--------------|----------|--------------|
| Dummy | 0.5116 | [0.493, 0.530] | 0.5019 | [0.495, 0.509] |
| RF | 0.4993 | [0.481, 0.516] | 0.4969 | [0.490, 0.504] |
| SVM | 0.3919 | [0.377, 0.407] | 0.5009 | [0.494, 0.508] |
| XGBoost | 0.4923 | [0.474, 0.509] | 0.5052 | [0.498, 0.512] |
| CNN 1D | 0.4885 | [0.470, 0.506] | 0.3333 | [0.330, 0.336] |

15k n_test=3000, 50k n_test=20.040. Convergência em F1≈0.50 → **H₀ confirmada por evidência convergente** (3 paradigmas: clássico, CNN1D, CNN2D).

### 9.4 Controles

| Controle | Dataset | Classes | F1 RF | IC 95% | Leitura |
|----------|---------|---------|-------|--------|---------|
| **Controle A** | ECB + PT natural | 3 (Ascon/GIFT/AES-ECB) | 0.3598 | [0.349, 0.369] | sinal fraco (ECB recall 22.99%, chance 0.333) |
| **Controle B** | ECB + PT repetitivo | 3 | **0.6727** | [0.664, 0.681] | sinal forte (ECB recall **100%**, F1 ECB=1.0) |
| **Vigenère 3-class** | Vigenère 64 KB | 3 | 0.6632 (RF) / 0.6697 (XGB) | [0.657, 0.676] | sinal detectável |
| **Vigenère vs PRNG-random** | 64 KB | 2 | **1.0000** | [1.000, 1.000] | sinal trivial, F1 perfeito (todos os modelos) |

- **Ganho Controle B vs A = +0.313 F1** (mesmo dataset, só muda o PT) → prova que o sinal limitado em A vem do **plaintext** (poucos blocos repetidos), não de falha do pipeline.
- Caracterização (`reports/control_analysis/`): Ascon e GIFT CT → entropia **7.021–7.022 bits/byte**, **0.00%** blocos 16B repetidos, χ²≈255, IC≈0.00391 (≈1/256 = 0.003906) em todos os cenários → **estatisticamente indistinguíveis**. AES-ECB sobre PT repetitivo → entropia 4.290, **90.86%** blocos repetidos, χ²≈7020.

**Conclusão dos controles:** o pipeline **funciona quando há sinal** (ECB repetitivo, Vigenère, PRNG); a indistinguibilidade Ascon vs GIFT não é artefato metodológico → **reforça H₀**.

### 9.5 Testes estatísticos e métricas

- **IC 95%:** bootstrap percentil, **1000 reamostragens**, seed 42 (`compute_metrics` em `src/eval/metrics.py`).
- **McNemar:** com correção de continuidade + Bonferroni (`mcnemar_test`).
- **ECE:** Expected Calibration Error (10 bins) calculado quando há `y_proba`.
- **Métricas:** F1-macro, balanced accuracy, ECE, top-k (k=1). ⚠️ **AUC/ROC NÃO é calculado** em nenhum pipeline.

### 9.6 TABELA RESUMO UNIFICADA

| Caminho | Dataset | Modelo | F1-macro (mean±std CV / test) | Bal.Acc | AUC | Resultado |
|---------|---------|--------|-------------------------------|---------|-----|-----------|
| A | 60k | RF | 0.4971±0.0067 / 0.5011 | 0.5011 | n/d | H₀ ✓ |
| A | 60k | SVM | 0.4860±0.0316 / 0.5012 | 0.5017 | n/d | H₀ ✓ |
| A | 60k | LinearSVC | 0.5002±0.0041 / 0.5024 | 0.5024 | n/d | H₀ ✓ |
| A | 60k | XGBoost | 0.4984±0.0043 / 0.4952 | 0.4952 | n/d | H₀ ✓ |
| A | 60k | LR | 0.5011±0.0033 / 0.5024 | 0.5024 | n/d | H₀ ✓ |
| A | 15k | RF | — / 0.4993 | 0.4993 | n/d | H₀ ✓ |
| A | 50k | RF | — / 0.4969 | 0.4970 | n/d | H₀ ✓ |
| B (CNN1D) | 15k | direct | — / 0.4885 | 0.5010 | n/d | H₀ ✓ |
| B (CNN1D) | 50k | direct | — / 0.3333 (colapso) | 0.5000 | n/d | H₀ ✓ |
| C (CNN2D) | 15k | direct | — / 0.3380 (colapso) | 0.5013 | n/d | H₀ ✓ |
| **B/C/D** | **60k** | — | **⚠️ NÃO EXECUTADO** | — | — | pendente |
| Ctrl A | ECB nat | RF | — / 0.3598 | 0.3663 | n/d | sinal fraco |
| Ctrl B | ECB rep | RF | — / 0.6727 | 0.6730 | n/d | sinal forte ✓ |
| Ctrl B | ECB rep | CNN2D | — / 0.6717 | 0.6718 | n/d | detecta ECB ✓ |
| Ctrl Vig | Vig 64k 3c | XGB | 0.6655±0.0033 / 0.6697 | 0.6697 | n/d | sinal ✓ |
| Ctrl Vig/rand | 64k 2c | todos | 1.000±0.000 / 1.0000 | 1.0000 | n/d | sinal trivial ✓ |

---

## 10. NOTEBOOK KAGGLE

- **Arquivo:** `kaggle_notebook_lwc_1.py` (aberto no IDE em `c:\Users\nycol\Downloads\`; é o runner dos Caminhos B/C/D em T4).
- **Estrutura (9 células):**
  1. Verificação de ambiente (PyTorch, CUDA, GPU, VRAM, RAM)
  2. `pip install -q pyarrow mlflow imbalanced-learn shap tqdm scikit-learn xgboost boruta`
  3. Paths: `REPO_DIR=/kaggle/working/ascon`, `DATA_DIR=/kaggle/input/datasets/nycolaswenderson/lwc-ml-dataset`
  4. **Smoke test** (`scripts/smoke_test.py`: 500 amostras, 2 folds, 3 épocas, <10 min)
  5. Experimento B: `run_cnn_experiments_60k.py` (CNN1D)
  6. Experimento C: `run_cnn_experiments_60k.py --mode cnn2d`
  7. Experimento D: `run_hybrid_60k.py` (CNN1D usa **CT completo 65.552 bytes** com GPU)
  8. Upload resultados → GCP (`gsutil -m cp -r reports/ mlruns/ gs://lwc-ml-checkpoints-nick/...`)
  9. Resumo final (varre `reports/**/*.json`)
- **GPU:** Tesla T4 (Kaggle). Checkpoints por época em `/kaggle/working/checkpoints/` (retomáveis em spot/preempção).
- **Dataset Kaggle:** `nycolaswenderson/lwc-ml-dataset` (parquet 60k + features).

---

## 11. INFRAESTRUTURA

- **GCP:** bucket `gs://lwc-ml-checkpoints-nick/` (subpastas `reports_kaggle/`, `mlruns_kaggle/`). ⚠️ **NÃO ENCONTRADO:** nome do projeto GCP, cotas.
- **Kaggle:** GPU T4, sessão limitada (~9–12h); workflow checkpoint+resume+upload GCS.
- **Testes:** **130 testes pytest** em 10 módulos:

| Módulo | nº |
|--------|----|
| test_extractor.py | 38 |
| test_gift_cofb_wrapper.py | 16 |
| test_ascon_wrapper.py | 15 |
| test_aes_ecb_wrapper.py | 12 |
| test_cnn2d.py | 10 |
| test_vigenere_wrapper.py | 10 |
| test_metrics.py | 9 |
| test_selector.py | 8 |
| test_classical.py | 6 |
| test_cnn1d.py | 6 |

`conftest.py` adiciona `src/` e `src/crypto/` ao path. Rodar: `pytest tests/ -v`.
- **CI/CD:** ⚠️ **NÃO ENCONTRADO** (sem `.github/`, sem GitHub Actions).
- **Docker:** ⚠️ **NÃO ENCONTRADO** (sem Dockerfile).
- **MLflow:** logging opcional (train_loss/val_loss/val_f1_macro). Histórico git: apenas 7 commits.

---

## 12. DECISÕES METODOLÓGICAS DOCUMENTADAS

(de `CLAUDE.md`, `docs/contexto_inicial.md`, `docs/CONTEXTO_PARA_CLAUDE_WEB.md`, docstrings)

- **Key-holdout (não random split):** evitar o viés documentado em [Ambroise & McLachlan, PNAS 2002] e o "trabalho (9)" da proposta IME (reuso de chave infla acurácia +30 p.p.). Chaves de teste **nunca** aparecem no treino.
- **FS dentro do fold:** mesmo motivo — seleção no dataset completo é vazamento massivo.
- **Corpus Gutenberg:** plaintexts realistas (texto natural UTF-8), reprodutíveis, domínio público; **mesmos PT e chaves** para Ascon e GIFT → diferença puramente algorítmica.
- **64 KB de plaintext:** maximiza material estatístico por amostra (vs piloto 0–2048 B).
- **300 chaves / 60k amostras:** 100 amostras por chave por algoritmo; escala suficiente para IC estreitos (50k já dava IC ~±0.007).
- **Ascon vs GIFT-COFB:** ambos finalistas/padrão NIST LWC de 128 bits, AEAD com nonce+tag — comparação justa entre cifras seguras (não cifras clássicas como na literatura criticada).
- **`len_pt`/`len_ct` fora do modelo:** são metadados; usá-los seria vazamento (crítica explícita a Bhavya Shree et al. 2025).
- **Sem tuning agressivo de CNN:** filosofia "testar a hipótese, não maximizar performance".
- **Referências no código:** Peng et al. 2005 (mRMR); Kursa & Rudnicki 2010 (Boruta); Saeys et al. 2007; Ambroise & McLachlan 2002; Sikdar & Kule 2024 (CNN2D); LeCun et al. 2015. Posicionamento crítico em `contexto_inicial.md`: De Mello & Xexéo (2016/2018), Yuan Chuxuan (2021), Sikdar & Kule (2024, acurácia 98% suspeita de vazamento), Bhavya Shree et al. (2025, não citar como fonte primária).
- **NIST SP 800-232** (padronização Ascon).

---

## 13. LIMITAÇÕES CONHECIDAS

- ⚠️ **Caminhos B/C/D no 60k pendentes** (requerem GPU; rodar no Kaggle). Resultados de CNN existentes são de 15k/50k em **protocolo antigo** (reshape 32×32 / prefixo), não diretamente comparáveis ao 60k.
- **Assimetria intencional CNN1D:** Caminho B usa prefixo 4096 bytes (CPU); Caminho D usa CT completo 65552 (GPU). Documentado como decisão metodológica.
- **Representação 2D legada (reshape):** impõe adjacência artificial; co-ocorrência 256×256 corrige isso. Variantes (Hilbert/espiral) deixadas como trabalho futuro.
- **Sanity-check do 60k não rodado** (`validation.json` ausente; manifesto "pending").
- **AUC/ROC não computado.**
- **CTs curtos (datasets antigos) preenchidos com zero** até 1024/4096 — possível atalho de tamanho, mitigado porque Ascon e GIFT compartilham `len_pt`.
- **Boruta legacy + numpy 2.x:** shim na 0.4.x; fallback para mRMR se vazio.
- Hardware local: torch **CPU-only**; SVM no 50k levou ~3849s.

---

## 14. FIGURAS E ARTEFATOS VISUAIS

Todas em `reports/` (gitignored). PNGs de matriz de confusão (dpi 120, cmap Blues), gerados pelos runners.

| Path | Conteúdo |
|------|----------|
| `reports/keyholdout_2class_60k_v1_cv/confusion_matrices/{RF,SVM,LinearSVC,XGBoost}.png` | **CM do experimento 60k principal** |
| `reports/confusion_matrices/{CNN_1D,Dummy,RF,SVM,XGBoost}.png` | CM 15k (Caminho A + CNN1D) |
| `reports/keyholdout_2class_50k_v1/confusion_matrices/*.png` | CM 50k |
| `reports/keyholdout_2class_v1/cnn2d/confusion_matrix.png` | CM CNN2D 15k (colapso) |
| `reports/control_analysis/confusion_matrix_control_{a,b}.png` | CM controles ECB A/B (RF) |
| `reports/control_repetitive_3class_v1/cnn2d/confusion_matrix.png` | CM CNN2D Controle B (ECB 100%) |
| `reports/control_vigenere_64k_v1_cv/confusion_matrices/*.png` | CM Vigenère 3-class |
| `reports/vigenere_vs_random_v1_cv/confusion_matrices/*.png` | CM Vigenère vs PRNG (F1=1.0) |
| `reports/control_3class_v1/confusion_matrices/*.png` | CM Controle A (3-class) |

⚠️ **NÃO ENCONTRADO:** curvas ROC, learning curves salvas como figura (histórico de treino existe em JSON: `cnn_history.json`, `cnn2d_history.json`).

---

## 15. REPRODUTIBILIDADE

### Passos mínimos
```bash
# 1. Ambiente: Python 3.14 + venv com as libs da §1.2 + MSVC 2022 Build Tools
# 2. Build extensões C
build_cffi.bat
build_gift_cofb.bat
# 3. Testes (valida KAT 1089/1089 + pipeline)
pytest tests/ -v                              # 130 testes
# 4. Gerar dataset 60k (≈35s de cripto; ~4GB parquet)
python scripts/generate_2class_dataset.py     # (variante 60k)
# 5. Caminho A (principal) — CPU
python scripts/run_experiment_60k_cv.py
# 6. Caminhos B/C/D — requer GPU (Kaggle T4)
python scripts/run_cnn_experiments_60k.py --mode cnn1d
python scripts/run_cnn_experiments_60k.py --mode cnn2d
python scripts/run_hybrid_60k.py
python scripts/validate_all_datasets.py
```
- **GPU obrigatória:** apenas Caminhos B/C/D no 60k (CNN sobre 64 KB). Caminho A roda em CPU.
- **Tempos documentados:** Caminho A 60k ~ minutos (RF 11s, SVM-grid 390s); 15k total 456s; 50k total 6480s. CNN1D 50k 2191s. ⚠️ Tempo B/C/D 60k não medido (pendente).
- **Docker:** ⚠️ NÃO ENCONTRADO.
- Caches `.pkl` (`_cv_cache.pkl`, `_final_cache.pkl`) e `--skip-cv`/`--resume` permitem retomar.

---

## 16. TEXTOS JÁ ESCRITOS

⚠️ **NÃO ENCONTRADO:** nenhum `.tex`, `.docx`, nem rascunho de artigo com seções abstract/introduction/methodology/results/conclusion.

Documentos de apoio existentes (não são o artigo):
- `docs/contexto_inicial.md` — revisão de papers (Sikdar & Kule 2024; Bhavya Shree 2025; De Mello & Xexéo; Yuan Chuxuan), decisão da FS 3-estágios, **bibliografia-chave completa de feature selection** (Ambroise & McLachlan, Bommert, Breiman, Chen & Guestrin, Kalousis, Kuncheva, Kursa & Rudnicki, Meinshausen & Bühlmann, Peng et al., Saeys et al., Strobl et al., Tibshirani, etc. — pronta para o artigo).
- `docs/CONTEXTO_PARA_CLAUDE_WEB.md` — objetivo, pergunta, hipóteses, escopo, 5 regras de ouro, pipeline FS, controles.
- `CLAUDE.md` — regras de ouro, especificação do dataset e arquitetura.

Tabelas-resumo prontas (Markdown, reutilizáveis no artigo):
`reports/comparison_all_approaches.md`, `reports/comparison_all_experiments.md`, `reports/comparison_15k_vs_50k.md`, `reports/comparison_table.md`, e os `comparison_table.md`/`mcnemar_table.md` por experimento.

---

## 17. CÓDIGO-FONTE CRÍTICO (trechos)

### 17.1 Geração de dataset — núcleo do loop ([dataset_generator.py:318](src/crypto/dataset_generator.py#L318))
```python
for key_id, key_bytes in keys_list:
    for pt_size in cfg.pt_sizes:
        for sample_idx in range(cfg.samples_per_key_size):
            nonce_bytes = nonce_counter.to_bytes(16, "big")   # contador global
            plaintext = self._pt_gen.sample(pt_size)           # corpus Gutenberg
            ciphertext = self._ascon.encrypt(key_bytes, nonce_bytes, plaintext, cfg.ad)
            rows.append({ "algorithm": "Ascon-AEAD128", "key_id": key_id,
                          "len_pt": pt_size, "len_ct": len(ciphertext),
                          "ciphertext": ciphertext, ... })   # PT/key/nonce NÃO entram aqui
```

### 17.2 Extração de features ([extractor.py:66](src/features/extractor.py#L66))
```python
_ALL_FAMILIES = ("histogram","entropy","ngrams","autocorrelation","complexity","frequency")
def extract(self, ct: bytes) -> dict[str, float]:
    result = {}
    for fname in self._families:        # 256+4+15+18+4+10 = 307
        result.update(_FAMILY_FUNCS[fname](ct))
    return result
```

### 17.3 CNN-1D ([cnn1d.py:50](src/models/cnn1d.py#L50))
```python
self.embedding = nn.Embedding(256, embed_dim)             # bytes 0-255
for i in range(n_conv_blocks):                            # 3 blocos, filtros 128→256→512
    out_channels = n_filters * (2 ** i)
    layers += [nn.Conv1d(in_c,out_channels,kernel_size,padding=kernel_size//2),
               nn.BatchNorm1d(out_channels), nn.ReLU(), nn.MaxPool1d(2)]
self.gap = nn.AdaptiveAvgPool1d(1); self.fc = nn.Linear(in_channels, n_classes)
def extract_latent(self, x):  # vetor 512D antes do FC
    emb = self.embedding(x).permute(0,2,1); h = self.conv_blocks(emb)
    return self.gap(h).squeeze(-1)
```

### 17.4 CNN-2D ([cnn2d.py:35](src/models/cnn2d.py#L35)) + representação ([ciphertext_to_image.py:18](src/models/ciphertext_to_image.py#L18))
```python
self.features = nn.Sequential(
    nn.Conv2d(1,32,3,padding=1),  nn.BatchNorm2d(32),  nn.ReLU(), nn.MaxPool2d(2),
    nn.Conv2d(32,64,3,padding=1), nn.BatchNorm2d(64),  nn.ReLU(), nn.MaxPool2d(2),
    nn.Conv2d(64,128,3,padding=1),nn.BatchNorm2d(128), nn.ReLU(), nn.MaxPool2d(2))
self.gap = nn.AdaptiveAvgPool2d(1); self.fc = nn.Linear(128, n_classes)  # latent 128D

def bytes_to_cooccurrence(ct):   # co-ocorrência de bigramas 256×256, CT completo
    arr = np.frombuffer(ct, np.uint8)
    indices = arr[:-1]*256 + arr[1:]
    matrix = np.bincount(indices, minlength=256*256).reshape(256,256).astype(np.float32)
    return matrix / matrix.sum()
```

### 17.5 Loop de CV (split + FS no fold + treino + avaliação) ([run_experiment_60k_cv.py:271](scripts/run_experiment_60k_cv.py#L271))
```python
gkf = GroupKFold(n_splits=5)
for fold_idx,(tr_idx,val_idx) in enumerate(gkf.split(X_all,y_all,groups)):  # groups=key_id
    assert not (set(groups[tr_idx]) & set(groups[val_idx]))      # key-holdout
    sel = LWCFeatureSelector(SELECTOR_CFG); sel.fit(X_tr,y_tr,feature_names=feat_cols)
    X_tr_sel, X_val_sel = sel.transform(X_tr), sel.transform(X_val)
    scaler = StandardScaler().fit(X_tr_sel)                      # scaler só no treino
    for name,mdl in _build_models().items():                    # RF, SVM(grid), LinearSVC, XGB
        mdl.fit(X_tr_m, y_tr); y_pred = mdl.predict(X_val_m)
        f1 = f1_score(y_val,y_pred,average="macro")
```

### 17.6 Avaliação / métricas ([metrics.py:57](src/eval/metrics.py#L57))
```python
def compute_metrics(y_true,y_pred,y_proba=None,n_bootstrap=1000,seed=42):
    f1  = f1_score(y_true,y_pred,average="macro")
    bal = balanced_accuracy_score(y_true,y_pred)
    rng = np.random.default_rng(seed)                           # bootstrap percentil
    for _ in range(n_bootstrap):
        idx = rng.integers(0,n,size=n)
        f1_boots.append(f1_score(y_true[idx],y_pred[idx],average="macro"))
    f1_lo,f1_hi = np.percentile(f1_boots,[2.5,97.5])            # IC 95%
    ece = expected_calibration_error(y_true,y_proba,10) if y_proba is not None else None
    # McNemar: chi2=(|n10-n01|-1)²/(n10+n01), 1 g.l.   (mcnemar_test)
```

### 17.7 Positive control AES-ECB ([aes_ecb_wrapper.py](src/crypto/aes_ecb_wrapper.py))
```python
# Sem nonce, sem tag, padding PKCS7, determinístico → len_ct = len(PT padded)
cipher = Cipher(algorithms.AES(key), modes.ECB())
padder = padding.PKCS7(128).padder(); padded = padder.update(pt)+padder.finalize()
ct = cipher.encryptor().update(padded) + ...
```

---

## LACUNAS (o que falta para o artigo)

1. ⚠️ **Resultados dos Caminhos B, C e D no dataset 60k** — não executados. Os únicos resultados de CNN são de 15k/50k (protocolo antigo). **Lacuna mais crítica.**
2. ⚠️ **Sanity-check formal do 60k** (`validation.json`): χ², nonces únicos, compressão, decrypt spot-check não rodados/registrados para o 60k.
3. ⚠️ **AUC/ROC**: não calculado em nenhum pipeline (só F1-macro, bal.acc, ECE, McNemar).
4. ⚠️ **Curvas ROC e learning curves** como figuras: ausentes (há histórico de loss em JSON).
5. ⚠️ **Texto de artigo** (abstract/intro/método/resultados/conclusão): inexistente — só docs de contexto.
6. ⚠️ **Detalhes de infra GCP**: projeto, cotas, região do bucket não documentados.
7. ⚠️ **requirements.txt / environment.yml**: não versionados (versões só via `pip freeze`).
8. ⚠️ **message-holdout e combined-split**: a "Regra 2" prevê 3 splits (key, message, combined); apenas **key-holdout** foi implementado/executado.
9. ⚠️ **Bibliografia LWC**: parcialmente numerada/implícita ("proposta IME") — referências completas de De Mello & Xexéo, Yuan, e demais LWC precisam ser consolidadas a partir da proposta de dissertação (fora do repo).
10. ⚠️ **CI/CD e Docker**: ausentes (não bloqueiam o artigo, mas afetam a seção de reprodutibilidade).
```
