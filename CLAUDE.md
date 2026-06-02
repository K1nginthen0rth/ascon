# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## CONTEXTO DO PROJETO

Dissertação de mestrado (IME-RJ, orientador Xexéo) sobre classificação de algoritmos LWC AEAD via ML em cenário ciphertext-only.

**Pergunta:** criptogramas de Ascon-AEAD128 e GIFT-COFB são distinguíveis por ML sem acesso à chave ou ao plaintext?

**4 caminhos experimentais:**
- A: 307 features clássicas → RF/SVM/XGBoost
- B: CNN 1D como extrator de features → latent → classificador
- C: CNN 2D como extrator de features → latent → classificador
- D: Híbrido — [307D] + [latent B] + [latent C] → classificador

---

## COMANDOS DE DESENVOLVIMENTO

### Build (extensões C via CFFI + MSVC)

```bat
build_cffi.bat          :: Compila Ascon → src/crypto/_ascon_ref.cp314-win_amd64.pyd
build_gift_cofb.bat     :: Compila GIFT-COFB → src/crypto/_gift_cofb_ref.cp314-win_amd64.pyd
```

Requer MSVC 2022 Build Tools e venv ativado. Os `.pyd` já compilados estão em `src/crypto/`.

### Testes

```bash
pytest tests/ -v                                      # todos os 130 testes
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
python scripts/validate_all_datasets.py     # checar χ², nonces, compressão, decrypt
```

---

## REGRAS DE OURO (NUNCA VIOLAR)

1. **Seeds fixas:** split=42, modelo=7, FS=13, bootstrap=42
2. **Key-holdout:** chaves de teste NUNCA aparecem no treino. Split 80/20 por chave.
3. **CV 5-fold dentro do treino:** estratificado por chave (192 treino / 48 val por fold)
4. **Feature selection dentro do fold:** MI → mRMR → Boruta APENAS no treino de cada fold
5. **len_pt/len_ct NÃO são features:** são metadados, nunca entram no modelo
6. **Mesmos plaintexts e chaves** para Ascon e GIFT-COFB

---

## DATASET

| Parâmetro | Valor |
|-----------|-------|
| Corpus | Project Gutenberg (SPGC) apenas |
| Total | 60.000 amostras (30.000 por algoritmo) |
| Plaintext | 64 KB fixo |
| Chaves | 300 (seed=42), offset=1000 entre algoritmos |
| Amostras | 100 por chave por algoritmo |
| Nonces | Contador global 128 bits |
| AD | b"" (vazio) |
| Split | 240 chaves treino+val / 60 chaves teste |

**Metadados obrigatórios em todo parquet:**
`{algorithm, mode, impl, key_id, nonce_id, len_pt, len_ct, len_ad, plaintext_source, seed, version, timestamp}`

Plaintexts e chaves NÃO ficam no parquet final — ficam em `data/interim/` só para validação.

---

## ARQUITETURA DO CÓDIGO

### `src/crypto/`
- **ascon_wrapper.py** — CFFI binding para Ascon-AEAD128. API: `AsconAEAD128.encrypt()`, `.decrypt()`, `.validate_kat()`. 1089 KATs validados.
- **gift_cofb_wrapper.py** — Idem para GIFT-COFB.
- **vigenere_wrapper.py** — Vigenère XOR (controle positivo: estrutura residual detectável). Interface: `encrypt(key, pt) → ct`. Sem nonce/tag/AD.
- **dataset_generator.py** — `DatasetConfig` + `AsconDatasetGenerator`: gera parquets criptografados a partir do corpus Gutenberg.
- **_ascon_cffi_build.py**, **_gift_cofb_cffi_build.py** — Compilam os `.pyd` se ausentes.

### `src/features/`
- **extractor.py** — `CiphertextFeatureExtractor`: orquestra 6 famílias → vetor 307D.
- **families/** — Uma classe por família (histogram, entropy, ngrams, autocorrelation, complexity, frequency).
- **selector.py** — `LWCFeatureSelector`: pipeline MI → mRMR → Boruta. Deve ser fitado **somente no treino de cada fold**.

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
- **classical.py** — Pipeline scikit-learn: Dummy, RF, SVM, XGBoost.
- **cnn1d.py** — `CiphertextCNN1D`: Embedding(256, embed_dim) → 3×[Conv1D+BN+ReLU+MaxPool] → GlobalAvgPool → `[LATENT]` → Dropout → FC. Método `extract_latent(x)` obrigatório.
- **cnn2d.py** — `CiphertextCNN2D`: bytes → imagem H×W → 3×[Conv2D+BN+ReLU+MaxPool] → GlobalAvgPool → `[LATENT]` → FC. Não usar pesos pré-treinados.
- **cnn_trainer.py** — Trainer genérico PyTorch para CNN1D e CNN2D.
- **ciphertext_to_image.py** — Reshape bytes → imagem 2D grayscale para CNN2D.
- **hybrid.py** — ❌ a implementar: concatena [307D] + [latent B] + [latent C] → RF/XGB.

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
