# Experimento v1: Ascon-AEAD128 vs GIFT-COFB (concluído)

Registro técnico do primeiro experimento da dissertação, encerrado em agosto de
2026. Condensa a antiga pasta `docs/analise_completa/` (9 arquivos, gerados em
2026-08-16) e `docs/cnn_caminhos_b_c.md`. Os detalhes que saíram na condensação
continuam no histórico do git.

**Pergunta:** um adversário com acesso só ao criptograma consegue dizer se ele
veio de Ascon-AEAD128 ou de GIFT-COFB, sem chave, sem nonce e sem plaintext?

**Resposta medida:** não, sob este protocolo. Os 4 caminhos convergem para
F1-macro com IC 95% cobrindo 0,50. H₀ não foi rejeitada em nenhum deles nem na
ablação de robustez.

> O v1 não é reproduzível bit a bit a partir do HEAD. Os parquets têm 307
> features; o código de hoje, para a mesma lista de 6 famílias, produz 308,
> porque `compression_ratio_lzma` entrou em `9012c55` (Fase 2 do v2), depois do
> v1 já ter rodado. Este documento descreve o v1-como-executado. Regenerar os
> números exigiria reverter essa adição.

---

## 1. Dataset

`keyholdout_2class_60k_v1`, gerado por `scripts/generate_2class_50k.py` (o nome
do arquivo ficou desatualizado, a config interna `CONFIG_50K` gera 60k).

| Parâmetro | Valor |
|---|---|
| Total | 60.000 (30.000 Ascon-AEAD128 + 30.000 GIFT-COFB) |
| Plaintext | 65.536 bytes fixos, 100% corpus Gutenberg (SPGC) |
| Chaves | 300, seed=42, `key_seed_offset=2000`, via `np.random.default_rng` (PCG64) |
| Amostras por chave por algoritmo | 100 |
| AD | vazio |
| Nonce | contador global de 128 bits |
| Split | 240 chaves trainval / 60 teste, com `GroupKFold` 5-fold por `key_id` no trainval |
| `len_ct` | 65.552 bytes (65.536 + 16 de tag) |
| Disco | ~3,93 GB |

Validado por `scripts/validate_2class_60k.py`: totais, splits, χ², compressão e
decrypt spot-check.

O RNG aqui é NumPy, não o CTR_DRBG do v2. Não é problema de correção, as chaves
só precisam ser distintas e independentes do rótulo, e são. Mas o texto da
dissertação precisa dizer isso em vez de deixar implícito que a disciplina do
CTR_DRBG vale para tudo.

### Controles positivos

| dataset_id | Composição | Offset |
|---|---|---|
| `control_vigenere_64k_v1` | 90k: 30k Ascon + 30k GIFT-COFB + 30k Vigenère-XOR, 3 classes | 4000 |
| `vigenere_vs_random_v1` | 60k: 30k Vigenère-XOR + 30k bytes de PRNG, 2 classes | 5000 |

### Reuso de material de chave entre datasets legados

`key_seed_offset` só desloca a mesma seed base 42, então datasets legados que
por coincidência usam o mesmo offset geram as mesmas chaves:

- offset 2000: as primeiras 100 chaves do dataset vivo são idênticas às do
  órfão `keyholdout_2class_50k_v1`.
- offset 3000: `control_3class_v1` e `control_vigenere_v1`, 30 chaves cada.
- offset 4000: `control_repetitive_3class_v1` (30 chaves) e
  `generate_vigenere_64k.py` (300), as 30 primeiras coincidem, apesar de os dois
  scripts comentarem "offset disjunto de 0/1000/2000/3000".

Não é vazamento, esses datasets nunca foram combinados no mesmo treino. Vale
registrar caso algum experimento futuro combine dois deles.

---

## 2. As 307 features

`CiphertextFeatureExtractor` orquestra 6 famílias, todas operando só sobre o
criptograma. Nenhuma recebe plaintext, chave ou nonce, então o cenário
ciphertext-only está respeitado no nível da implementação, não só do protocolo.

| Família | Dim | Features | Observação |
|---|---|---|---|
| Histograma | 256 | `byte_hist_000`…`_255` | `bincount/len(ct)` |
| Entropia | 4 | `shannon_entropy`, `chi2_statistic`, `chi2_pvalue`, `chi2_dof` | χ² só se `len(ct)>=16` |
| N-gramas | 15 | `ngram_{2,3,4}_{entropy,nunique,max_freq,chi2,collision_rate}` | 5 estatísticas × 3 ordens |
| Autocorrelação | 18 | `autocorr_lag_01`…`_16`, `runs_count`, `runs_zscore` | ACF + runs de Wald-Wolfowitz |
| Complexidade | 4 | `lz_complexity`, `lz_complexity_normalized`, `compression_ratio_zlib`, `compression_ratio_bz2` | LZ76 guloso, O(n²) |
| FFT | 10 | `fft_band_0`…`_7`, `fft_peak_freq`, `fft_spectral_entropy` | `np.fft.rfft` sobre os bytes, 8 bandas sem DC |

NaN é o retorno padrão para CT curto demais para uma dada estatística, e o
consumidor imputa NaN para 0.

### Seletor

Pipeline `VarianceThreshold(1e-5)` → `mutual_info_classif` top-200 → mRMR (100
features, define o conjunto final) → Boruta (diagnóstico).

Boruta era o filtro final até `5b46413`. Virou diagnóstico porque no
experimento principal ele colapsou o conjunto para 1 feature só
(`ngram_2_chi2`) em 2 dos 5 folds e no modelo final, o que levantava a objeção
de que o F1≈0,50 fosse artefato do seletor e não propriedade dos criptogramas.
A ablação da §5 respondeu essa objeção de forma direta.

`fit()` roda só em `X_train`, dentro de cada fold. O docstring cita Ambroise &
McLachlan (PNAS 2002): seleção fora do CV pode inflar acurácia em mais de 30
pontos percentuais. Todos os scripts vivos têm `assert` explícito de não
sobreposição de chaves entre treino e validação.

---

## 3. Os 4 caminhos

| Caminho | Representação | Modelos |
|---|---|---|
| A | 307 features clássicas | Dummy, RF, SVM-RBF (GridSearchCV), LinearSVC, XGBoost, LR |
| B | CNN 1D sobre a sequência de bytes, CT completo | fim-a-fim, ou latente 512D para RF/LinearSVC |
| C | CNN 2D sobre co-ocorrência de bigramas 256×256 | fim-a-fim, ou latente 128D para RF/LinearSVC |
| D | Híbrido 307D + 512D + 128D = 947D | RF, XGBoost |

**CNN 1D** (`cnn1d.py`): `Embedding(256, 32)` → 3 blocos
`[Conv1D, BatchNorm, ReLU, MaxPool]` com filtros 128, 256, 512 →
`AdaptiveAvgPool1d(1)` que é o `extract_latent()` → `Dropout(0.3)` → `Linear`.
Bytes entram como símbolos categóricos via embedding aprendível, para não impor
ordem métrica artificial entre valores de byte. Com `max_len >= 16384` o
primeiro bloco usa kernel 8 e stride 4 em vez de kernel 3 e stride 1, sem isso
os 65.552 bytes do CT completo ficariam proibitivos.

**CNN 2D** (`cnn2d.py`): 3 blocos `[Conv2D 3×3, BN, ReLU, MaxPool]` com canais
32, 64, 128 → `AdaptiveAvgPool2d(1)` → `Dropout(0.3)` → `Linear`. Treinada do
zero, sem pesos ImageNet, porque features de fotos naturais não têm
correspondência em dados que se aproximam de ruído. A representação canônica é
`bytes_to_cooccurrence`, o mapa `pixel[i,j] = freq(byte i seguido de byte j)`,
que só relaciona bytes de fato consecutivos. O reshape linear 32×32 é legado e
impõe adjacência vertical artificial.

**Híbrido** (`hybrid.py`): datasets lazy (`CiphertextSeqDataset`,
`CiphertextCoocDataset`) convertem bytes para tensor em `__getitem__`, porque
materializar 48 mil matrizes 256×256 float32 de antemão estoura RAM. Checkpoint
por época salvando `model_state, optimizer_state, rng_state, best_val,
best_epoch`, com `resume=True`, pensado para instância preemptível. Batch
adaptativo: `batch_size_1d = 8 if max_len_1d >= 16384 else 64`, porque 64
sequências de 65.552 posições não cabem em VRAM comum. `transform()` congela os
pesos com `.eval()` e `torch.no_grad()`.

`_NUM_WORKERS` do DataLoader é 0 no Windows e 4 no Linux. Com
`num_workers > 0` e múltiplos DataLoaders em sequência no mesmo processo, o
Windows trava de forma reprodutível.

---

## 4. Resultados

Baseline de acaso em todo experimento binário: F1-macro = 0,5000. Teste holdout
de 12.000 amostras, 6.000 por classe. Bootstrap 1000 repetições, seed 42.

### Caminho A

Fonte: `reports/keyholdout_2class_60k_v1_cv/`, presente no repositório.

| Modelo | F1 CV (5-fold) | F1 teste | IC 95% | Bal.Acc | AUC |
|---|---|---|---|---|---|
| RF | 0,4971 ± 0,0067 | 0,5011 | [0,492; 0,510] | 0,5011 | 0,4982 |
| SVM RBF | 0,4860 ± 0,0316 | 0,5012 | [0,492; 0,510] | 0,5017 | 0,5064 |
| LinearSVC | 0,5002 ± 0,0041 | 0,5024 | [0,494; 0,511] | 0,5024 | 0,5064 |
| XGBoost | 0,4984 ± 0,0043 | 0,4952 | [0,487; 0,504] | 0,4952 | 0,4906 |
| LR | 0,5011 ± 0,0033 | 0,5024 | [0,494; 0,511] | 0,5024 | 0,5064 |

Todos os IC cobrem 0,50. McNemar com Bonferroni: nenhum par significativo,
p > 0,23 em todos. O desvio-padrão de 0,0316 do SVM vem da grade sendo refeita
a cada fold, com 4 combinações de (C, γ) diferentes em 5 folds e uma quinta no
modelo final. Quando há estrutura real a grade tende a reencontrar a mesma
região; aqui oscila sem convergir.

O vetor de 307 caiu para 29 após o `VarianceThreshold`. Jaccard médio do Boruta
entre os 5 folds: 0,32.

### Caminhos B e C

Fonte: `dissertacao_rasc/resultados.tex` (2026-07-07), que cita um
`RESULTADOS_FINAIS_4_CAMINHOS.md` nunca localizado no repositório nem em
`Downloads/`. Números não verificados contra JSON bruto, diferente de A e D.

| Caminho | Modo | F1 CV | F1 teste | IC 95% |
|---|---|---|---|---|
| B | `direct` | 0,3343 ± 0,0017 | 0,3333 | [0,329; 0,337] |
| B | `latent_rf` | 0,4998 ± 0,0070 | 0,5040 | [0,495; 0,512] |
| B | `latent_lsvc` | 0,5043 ± 0,0053 | 0,5039 | [0,495; 0,512] |
| C | `direct` | 0,3333 ± 0,0000 | 0,3333 | [0,329; 0,337] |
| C | `latent_rf` | 0,4983 ± 0,0069 | 0,4978 | [0,489; 0,506] |
| C | `latent_lsvc` | 0,5021 ± 0,0025 | 0,4979 | [0,489; 0,507] |

O modo `direct` colapsa em 0,3333, que é prever sempre a mesma classe em
problema binário balanceado (F1 = 0,667 para a classe prevista, 0 para a outra,
média 1/3). É falha de otimização, não evidência de indistinguibilidade: os
latentes extraídos da mesma rede que colapsa, entregues a classificador
externo, voltam para o nível do acaso em vez de ficarem também em 0,33. A
evidência de B e C vem dos modos latentes.

### Caminho D

Fonte: `reports/keyholdout_2class_60k_v1_hybrid/`, sincronizado na Fase 0 do v2.
Os números batem exatamente com o texto da dissertação.

| Modelo | F1 CV | F1 teste | IC 95% | Bal.Acc |
|---|---|---|---|---|
| RF | 0,5002 ± 0,0030 | 0,5011 | [0,492; 0,510] | 0,5011 |
| XGBoost | 0,4978 ± 0,0040 | 0,4952 | [0,487; 0,504] | 0,4952 |

McNemar RF vs XGBoost: estatística 0,875, p = 0,3496. A fusão das três
representações não superou nenhuma isoladamente.

O Jaccard médio do Boruta no espaço híbrido caiu para 0,0013 (contra 0,32 no
Caminho A), com número de atributos confirmados variando de 1 a 73 entre folds.
Num espaço 3 vezes maior a seleção ficou essencialmente aleatória entre folds.
Junto com a não convergência do SVM, é o segundo indicador independente de
ausência de estrutura estável.

---

## 5. Ablação do seletor (2026-08-12)

Fonte: `reports/ablation_fs_60k/`, gerado por `scripts/run_ablation_fs_60k.py`.

Motivação: o `VarianceThreshold` em unidades absolutas elimina 278 das 307
features, incluindo todo o histograma de bytes, porque frequência relativa tem
variância na ordem de 5,9e-8. É corte de escala, não de informação. Restava
saber se o F1≈0,50 era propriedade dos criptogramas ou artefato do seletor.

Quatro braços, mesmo protocolo do experimento principal, com LR, LinearSVC, RF
e XGBoost:

| Braço | Nº features | Melhor F1 teste | Pior F1 teste |
|---|---|---|---|
| `all307` (sem seleção) | 307 | 0,5044 (LR/LinearSVC) | 0,4980 (RF) |
| `vt29` (só as que sobrevivem ao VT) | 29 | 0,5024 (LR) | 0,4918 (XGBoost) |
| `hist256` (só o histograma) | 256 | 0,5024 (LR) | 0,4918 (XGBoost) |
| `top1` (só `ngram_2_chi2`) | 1 | 0,5024 (LR/LinearSVC) | 0,4952 (XGBoost) |

Os 16 pares braço × modelo têm IC 95% cobrindo 0,50. Sem seletor nenhum o
resultado não muda, então o teto de F1≈0,50 não vem do `VarianceThreshold` nem
do Boruta.

Teste de permutação (20 repetições, braço `all307`, LR e XGBoost), com dois
esquemas de embaralhamento de rótulo: `by_key` (rótulo constante por chave) e
`within_key` (permuta dentro da chave, preserva o balanço 100/100). Nos dois, o
melhor F1 observado (0,5044) cai dentro da faixa nula, p2.5 a p97.5 de
aproximadamente [0,49; 0,51], com p empírico entre 0,19 e 0,29 pela correção de
Phipson & Smyth (2010).

## 6. Controles positivos

| Controle | Dataset | Classes | F1 |
|---|---|---|---|
| Vigenère 3-class 64KB | `control_vigenere_64k_v1` | 3 | RF 0,663 / XGB 0,670, com recall e precisão da classe Vigenère próximos de 1,0 |
| Vigenère vs PRNG 64KB | `vigenere_vs_random_v1` | 2 | 1,0000 em todos os modelos |
| ECB natural (legado) | `control_3class_v1` | 3 | RF 0,360 |
| ECB repetitivo (legado) | `control_repetitive_3class_v1` | 3 | RF 0,673, ECB com recall e precisão de 100% |

Os controles descartam a hipótese de que o pipeline seja incapaz de detectar
sinal quando ele existe.

---

## 7. Pendência que sobrou do v1

Os artefatos brutos dos Caminhos B e C nunca foram localizados, nem no
repositório nem em `Downloads/` até 5 níveis de profundidade. O texto da
dissertação cita um `RESULTADOS_FINAIS_4_CAMINHOS.md` que também não existe em
disco, provavelmente gerado no ambiente Kaggle e nunca copiado de volta. Sem
isso, o repositório não sustenta sozinho os números de B e C que já estão
escritos: `reports/keyholdout_2class_60k_v1_cnn/` tem só `ckpts/` e
`confusion_matrices/` vazios.

Isso não bloqueia o v2 (que gera B e C do zero) nem o estudo de piso de
rodadas. Afeta só a reprodutibilidade retroativa do v1.
