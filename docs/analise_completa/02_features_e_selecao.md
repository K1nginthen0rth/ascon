# 2. Features clássicas e seleção (`src/features/`)

## 2.1 As 307 features (`extractor.py` + `families/`)

`CiphertextFeatureExtractor` orquestra 6 famílias independentes
(`src/features/families/*.py`), todas operando **só sobre o ciphertext**
(nenhuma família recebe plaintext, chave ou nonce — cenário ciphertext-only
respeitado no nível de implementação, não só de protocolo).

| Família | Arquivo | Linhas | Dim | Features | Fórmula / observação |
|---|---|---|---|---|---|
| Histograma | `histogram.py` | 23 | 256 | `byte_hist_000`…`_255` | frequência relativa de cada byte = `bincount/len(ct)` |
| Entropia | `entropy.py` | 54 | 4 | `shannon_entropy`, `chi2_statistic`, `chi2_pvalue`, `chi2_dof` | Shannon `-Σp·log₂p`; χ² vs. uniforme (só calculado se `len(ct)≥16`) |
| N-gramas | `ngrams.py` | 78 | 15 | `ngram_{2,3,4}_{entropy,nunique,max_freq,chi2,collision_rate}` | 5 estatísticas × 3 ordens; `_count_ngrams` empacota bytes em inteiros e usa `np.unique` (sem loop Python) |
| Autocorrelação | `autocorrelation.py` | 64 | 18 | `autocorr_lag_01`…`_16`, `runs_count`, `runs_zscore` | ACF normalizada lags 1–16 + teste de runs Wald-Wolfowitz |
| Complexidade | `complexity.py` | 57 | 4 | `lz_complexity`, `lz_complexity_normalized`, `compression_ratio_zlib`, `compression_ratio_bz2` | LZ76 greedy (`_lz76`, O(n²) por construção — string search ingênuo); zlib/bz2 nível 9 |
| FFT | `frequency.py` | 59 | 10 | `fft_band_0`…`_7`, `fft_peak_freq`, `fft_spectral_entropy` | `np.fft.rfft` sobre os bytes como série temporal, 8 bandas de energia (sem componente DC) |

**Total = 256+4+15+18+4+10 = 307.** NaN é o valor de retorno padrão para CTs
curtos demais para uma dada estatística (ex.: `autocorr_lag_16` exige
`len(ct)≥17`); o consumidor (`selector.py`/`classical.py`) imputa NaN→0.

`CiphertextFeatureExtractor.extract_dataset()` paraleliza com
`joblib.Parallel(prefer="processes")` e preserva só metadados leves
(`sample_id, algorithm, key_id, len_pt, len_ct`) — a coluna `ciphertext` bruta
nunca entra no parquet de features.

## 2.2 Seletor de features (`selector.py`, 275 linhas) — ⚠️ mudança pendente de commit

### Pipeline atual (código já editado localmente, `git diff` sem commit)

```
Estágio 1 (screening, O(p)):
    VarianceThreshold(1e-5)  →  mutual_info_classif top-k (default k=200)
Estágio 2 (redundância — DEFINE O CONJUNTO FINAL):
    mRMR [Peng et al. 2005]  →  n_features_mrmr (default 100)
Estágio 3 (diagnóstico apenas, NÃO filtra mais):
    Boruta [Kursa & Rudnicki 2010] sobre a saída do mRMR
    → reporta stage3_boruta_confirmed / stage3_stability_ratio
```

`transform()` sempre aplica `self._final_mask = stage2_mask` (saída do mRMR).
O resultado do Boruta vira só um número no relatório
(`get_stage_report()["stage3_boruta_confirmed"]`), sem efeito no conjunto de
features que chega ao classificador.

### O que mudou e por quê

**Antes** (código no HEAD do git, ainda em produção nos artefatos já
publicados): Boruta era o Estágio 3 filtrante — `self._final_mask =
stage3_mask`. Se Boruta retornasse conjunto vazio, havia um fallback
explícito para a saída do mRMR.

**Motivo documentado da mudança** (via `scripts/run_ablation_fs_60k.py`,
não commitado — ver [07_resultados.md](07_resultados.md)): no experimento
principal (`run_experiment_60k_cv.py`), o Boruta colapsou o conjunto final
para **1 única feature** (`ngram_2_chi2`) em 2 dos 5 folds e no modelo final.
Isso levantou uma objeção metodológica legítima: a ausência de sinal
observada (F1≈0,50) poderia ser artefato do seletor cortando informação
demais, não uma propriedade real dos criptogramas. Redefinir Boruta como
diagnóstico (em vez de filtro) e reportar sua taxa de confirmação como
métrica de estabilidade, mantendo o mRMR como saída final, é uma resposta
direta a essa objeção — e a ablação (que testa inclusive rodar **sem
seletor nenhum**, com as 307 features cruas) confirma que o resultado nulo
não depende dessa escolha.

**Arquivos afetados por essa mudança, todos com alterações não commitadas
(`git status`)**:
`src/features/selector.py`, `src/models/classical.py`,
`scripts/run_experiment_60k_cv.py`, `scripts/run_hybrid_60k.py`,
`scripts/run_vigenere_cv.py`, `scripts/run_vigenere_random_cv.py`,
`tests/test_selector.py`. Todos os `print()`/logs de progresso trocaram
`Boruta->{stage3_output}` por `Boruta(diag)->{stage3_boruta_confirmed}`.

`tests/test_selector.py` já foi atualizado e está alinhado com a nova
semântica (confirmado por leitura direta e por um agente de exploração
dedicado — ver [06_testes.md](06_testes.md)): o teste-chave
(`test_selector_pure_noise_boruta_confirms_few`) afirma explicitamente
`rep["final_output"] == rep["stage2_output"]` mesmo quando o Boruta confirma
quase nada em ruído puro.

### Config default (`SelectorConfig`)

```python
variance_threshold=1e-5, top_k_mi=200, n_features_mrmr=100,
boruta_max_iter=100, boruta_n_estimators="auto", random_state=13
```

No Caminho D (híbrido, vetor 947D), os scripts sobrescrevem para
`top_k_mi=300, n_features_mrmr=150` — mais margem para o espaço maior.

### Regra crítica preservada

O `fit()` deve rodar **apenas em `X_train`**, dentro de cada fold de CV
(docstring do módulo cita `Ambroise & McLachlan, PNAS 2002` — vazamento de
seleção fora do CV pode inflar acurácia em 30+ pontos percentuais). Todos os
scripts vivos (`run_experiment_60k_cv.py`, `run_hybrid_60k.py`,
`run_vigenere_*_cv.py`) respeitam isso com `assert` explícito de não
sobreposição de chaves entre treino e validação de cada fold, além de
`StandardScaler` também ajustado só no treino.
