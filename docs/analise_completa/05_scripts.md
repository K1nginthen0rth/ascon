# 5. Catálogo de scripts (`scripts/`)

48 scripts. Legenda: 🟢 vivo (parte do fluxo do protocolo 60k/64KB atual) —
⚪ legado (protocolo antigo: PT variável 0–2048B, datasets 15k/22k/50k, ou
controle AES-ECB).

## 5.1 Geração de datasets

| Script | Linhas | Status | O que faz |
|---|---|---|---|
| `generate_2class_50k.py` | 50 | 🟢 | **Gera o dataset principal** `keyholdout_2class_60k_v1` (nome do arquivo desatualizado) |
| `generate_vigenere_64k.py` | 245 | 🟢 | Gera `control_vigenere_64k_v1` (controle 3-classes) |
| `generate_vigenere_random_dataset.py` | 221 | 🟢 | Gera `vigenere_vs_random_v1` (reaproveita linhas do dataset acima) |
| `generate_gift_cofb_kat.py` | 69 | 🟢 | Gera o arquivo KAT do GIFT-COFB a partir da própria `.pyd` — ⚠️ **autogerado, logo circular**; a âncora externa é `tests/test_crypto_independente.py` |
| `vendor_sources.py` | 312 | 🟢 | Fixa e reconstrói as 4 árvores C de referência por commit + SHA-256 por arquivo (`--check` / `--fetch` / `--pins`) |
| `generate_2class_dataset.py` | 358 | 🟡 misto | `TwoClassConfig`/`generate_2class()` são importados por outros scripts (vivo como biblioteca); seu `__main__` gera `pilot_2class_v1`/`keyholdout_2class_v1` (legados) |
| `generate_pilot_dataset.py` | 140 | ⚪ | `ascon_aead128_pilot_v2` / `_keyholdout_v2` (single-class) |
| `generate_ascon_parquet.py` | 174 | ⚪ | `ascon_aead128_base_v1` — 1 única chave, via `ascon_cli_ref.exe` |
| `generate_ascon_variable_sizes.py` | 201 | ⚪ | `ascon_aead128_variable_sizes_v1` — 1 única chave |
| `generate_3class_control.py` | 269 | ⚪ | `control_3class_v1` (AES-ECB + PT natural) |
| `generate_3class_repetitive.py` | 247 | ⚪ | `control_repetitive_3class_v1` (AES-ECB + PT repetitivo) |
| `generate_vigenere_control.py` | 279 | ⚪ | `control_vigenere_v1` (protocolo antigo) |
| `generate_random_control.py` | 142 | ⚪ | `random_control_v1` (bytes aleatórios puros) |
| `plaintext_generator.py` | 65 | ⚪ | `PlaintextGenerator` usado só pelos geradores legados acima (RNG não seedada — `random` global, diferente da versão determinística em `src/crypto/dataset_generator.py`) |

## 5.2 Validação de datasets

| Script | Linhas | Status | Cobre |
|---|---|---|---|
| `validate_2class_60k.py` | 218 | 🟢 | `keyholdout_2class_60k_v1`: totais, splits, χ², compressão, decrypt spot-check |
| `validate_pilot_dataset.py` | 439 | ⚪ | pilot/keyholdout v2 (single-class) |
| `validate_2class_50k.py` | 207 | ⚪ | dataset órfão `keyholdout_2class_50k_v1` — quase-duplicata linha a linha de `validate_2class_60k.py` |
| `validate_3class_control.py` | 109 | ⚪ | `control_3class_v1` (não grava JSON, só imprime) |
| `validate_3class_repetitive.py` | 138 | ⚪ | `control_repetitive_3class_v1` (idem) |
| `validate_all_datasets.py` | 66 | ⚪ **desatualizado vs. CLAUDE.md** | só checa existência de arquivo + manifest de 2 datasets antigos hardcoded — não faz χ²/compressão/decrypt apesar de ser isso que o CLAUDE.md descreve |

## 5.3 Experimentos (treino + avaliação)

| Script | Linhas | Status | Caminho(s) | Protocolo |
|---|---|---|---|---|
| `run_experiment_60k_cv.py` | 670 | 🟢 | A | 80/20 + 5-fold `GroupKFold` CV — **executado**, H₀ confirmada |
| `run_cnn_experiments_60k.py` | 1004 | 🟢 | B, C | idem — **executado** (ver §4 de [07_resultados.md](07_resultados.md); artefatos brutos não estão neste repo) |
| `run_hybrid_60k.py` | 670 | 🟢 | D | idem — **executado**, artefato bruto do Caminho D localizado em `Downloads/resultados_caminhoD_final/` |
| `run_vigenere_cv.py` | 583 | 🟢 | controle 3-class | idem — executado, F1≈0,66 |
| `run_vigenere_random_cv.py` | 617 | 🟢 | controle 2-class | idem — executado, F1≈1,00; SVM com hiperparâmetros **fixos** (C=10, gamma=scale), diferente dos outros scripts irmãos que usam `GridSearchCV` |
| `run_extra_lr_60k.py` | 332 | 🟢 | A (+LR) | reaproveita cache (`_cv_cache.pkl`/`_final_cache.pkl`) do `run_experiment_60k_cv.py`, sem reprocessar features — só adiciona `LogisticRegression` |
| `run_experiment_2class.py` | 366 | ⚪ | A, B | key-holdout simples (sem CV 5-fold), dataset default 15k |
| `run_cnn2d_experiments.py` | 171 | ⚪ | C | usa `CNN2DTrainer`/reshape 32×32 (caminho de código paralelo ao vivo) |
| `run_vigenere_experiment.py` | 269 | ⚪ | A | controle Vigenère no dataset legado `control_vigenere_v1` |
| `run_ablation_fs_60k.py` | 474 | 🟢 novo (não documentado antes) | A (variantes) | ablação do seletor — ver [07_resultados.md §4](07_resultados.md) |

## 5.4 Pós-processamento / análise / comparação

| Script | Linhas | Status | Faz |
|---|---|---|---|
| `compute_auc_all_paths.py` | 145 | 🟢 | Extrai AUC-ROC dos `_final_cache*.pkl` dos 4 Caminhos 60k → `reports/AUC_ROC_consolidado.md` (hoje só A está presente localmente) |
| `run_control_analysis.py` | 412 | ⚪ | Caracterização estatística dos controles AES-ECB legados (entropia, χ², %blocos repetidos) |
| `compare_15k_vs_50k.py` | 132 | ⚪ | Tabela comparativa 15k vs 50k |
| `compare_all_experiments.py` | 142 | ⚪ | Tabela comparativa entre 4 experimentos legados |
| `analyze_control_features.py` | 188 | ⚪ | Features Boruta-validadas do controle legado (pressupõe semântica antiga de Boruta-filtrante) |
| `analyze_vigenere_control.py` | 192 | ⚪ | Caracterização estatística do Vigenère legado |
| `analyze_plaintexts.py` | 31 | ⚪ | Wrapper fino sobre `run_control_analysis.py` |
| `save_confusion_matrices.py` | 42 | ⚪ | Regera PNGs de matriz de confusão do resultado 15k |
| `extract_2class_features.py` | 36 | ⚪ | Extração genérica de features (default aponta para datasets 15k) |
| `extract_vigenere_features.py` | 17 | ⚪ | Extração hardcoded para `control_vigenere_v1` |

## 5.5 Utilitários

| Script | Linhas | Status | Faz |
|---|---|---|---|
| `smoke_test.py` | 520 | 🟢 | Testa Caminhos B/C/D em modo reduzido: 500 amostras, 2 folds, 3 épocas, alvo <10min CPU; testa checkpoint/resume explicitamente |
| `check_ml_env.py` | 41 | 🟢 (uso manual) | Sanidade do ambiente (sklearn/xgboost/torch/boruta/mrmr) |
| `test_wrapper_python.py` | 86 | ⚪ | Verificação pontual pré-cffi (chama `ascon_cli_ref.exe` via subprocess) — superado por `tests/test_ascon_wrapper.py` |
| `mrmr.py` (raiz, fora de `scripts/`) | ~50 | 🟢 | Reimplementação local simplificada do mRMR (seleção gulosa MI − correlação média), **sombreia deliberadamente** o pacote `mrmr-selection` (v0.2.8, instalado mas não usado) porque a raiz do projeto entra no `sys.path` antes do `site-packages` — evita dependências pesadas (`category-encoders`, `jinja2`, `polars`) sob Python 3.14 |

## 5.6 Discrepâncias identificadas no inventário (resumo — detalhe completo em [08_achados_e_pendencias.md](08_achados_e_pendencias.md))

1. `validate_all_datasets.py` não faz o que o CLAUDE.md diz que faz.
2. `generate_2class_50k.py` gera o dataset `_60k_`, não `_50k_` — nome do arquivo confunde.
3. `validate_2class_50k.py` e `validate_2class_60k.py` são quase 100% código duplicado.
4. SVM com hiperparâmetros inconsistentes entre `run_vigenere_random_cv.py` (fixo) e seus scripts irmãos (GridSearchCV).
5. `MAX_LEN_B` tem dois valores diferentes em dois arquivos (`run_cnn_experiments_60k.py`=65552 vs. `hybrid.py`/`run_hybrid_60k.py`=4096, este último só como referência de log).
6. Scripts mais antigos (`generate_ascon_parquet.py` etc.) usam caminho absoluto Windows hardcoded em vez de `Path(__file__).resolve().parent.parent`.
