# 7. Resultados experimentais

**Correção central deste documento:** `CONTEXTO_ARTIGO.md` (2026-06-04) e
`docs/cnn_caminhos_b_c.md` afirmam que os Caminhos B, C e D não foram
executados no dataset 60k. Isso **era** verdade em junho. Não é mais: o
rascunho da dissertação (`dissertacao/resultados.tex`, escrito em
2026-07-07) já contém uma seção de resultados completa para os 4 Caminhos,
com números que — onde foi possível cruzar com artefato bruto — batem
exatamente. Ver §7.5 para a ressalva sobre onde esses artefatos brutos
realmente estão.

Baseline de acaso em todos os experimentos binários: **F1-macro = 0,5000**.

## 7.1 Caminho A — features clássicas (60k)

**Fonte:** `reports/keyholdout_2class_60k_v1_cv/` (presente neste repositório
— cv_results.json, final_results.json, _final_cache.pkl). Confirmado
diretamente.

Test holdout = 12.000 amostras (6.000/classe). Bootstrap 1000× (seed 42).

| Modelo | F1 CV (5-fold, média±dp) | F1 teste | IC 95% | Bal.Acc | AUC |
|---|---|---|---|---|---|
| RF | 0,4971 ± 0,0067 | 0,5011 | [0,492; 0,510] | 0,5011 | 0,4982 |
| SVM RBF (GridSearchCV) | 0,4860 ± 0,0316 | 0,5012 | [0,492; 0,510] | 0,5017 | 0,5064 |
| LinearSVC | 0,5002 ± 0,0041 | 0,5024 | [0,494; 0,511] | 0,5024 | 0,5064 |
| XGBoost | 0,4984 ± 0,0043 | 0,4952 | [0,487; 0,504] | 0,4952 | 0,4906 |
| LR | 0,5011 ± 0,0033 | 0,5024 | [0,494; 0,511] | 0,5024 | 0,5064* |

*AUC da LR não está em `AUC_ROC_consolidado.md` (script rodou antes de
`run_extra_lr_60k.py` existir); valor de F1/teste vem de
`reports/keyholdout_2class_60k_v1_cv/` via `run_extra_lr_60k.py`.

Todos os IC 95% cobrem 0,50. McNemar (Bonferroni) — nenhum par significativo
(p>0,23 em todos). O desvio-padrão alto do SVM (0,0316) vem da grade sendo
refeita a cada fold: **4 combinações de (C,γ) diferentes em 5 folds**, e um
5º par diferente no modelo final — lido como evidência de segunda ordem
(quando há estrutura real, a grade tende a reencontrar a mesma região;
aqui oscila sem convergir).

**Seleção de features neste experimento:** o vetor de 307 caiu para **29**
após VarianceThreshold, e o modelo final usou a saída do mRMR sobre essas
29 (protocolo atual, pós-mudança do Boruta — ver §7.4). Jaccard médio do
Boruta entre os 5 folds: **0,32** — concordância parcial, consistente com
seleção respondendo a flutuação amostral, não a estrutura estável.

## 7.2 Caminhos B e C — CNN1D e CNN2D (60k)

**Fonte:** `dissertacao/resultados.tex` (2026-07-07), que cita como fonte
primária um arquivo `RESULTADOS_FINAIS_4_CAMINHOS.md` **não localizado**
neste repositório nem nas buscas feitas em `Downloads/` — provavelmente
gerado no ambiente de treino (Kaggle) e usado para escrever o texto sem
nunca ter sido copiado de volta. **Números abaixo não puderam ser
verificados aqui contra o JSON bruto** (diferente de A e D — ver §7.1 e
§7.3), mas o valor do Caminho D bate exatamente entre o texto da
dissertação e o `_final_cache.pkl` recuperado (§7.3), o que dá confiança
razoável na consistência da fonte.

CNN1D (Caminho B) processa o CT completo (65.552 bytes); CNN2D (Caminho C)
usa o mapa de co-ocorrência 256×256 do CT completo. Ambos avaliados em 3
modos: `direct` (fim-a-fim), `latent_rf` (latente → RF), `latent_lsvc`
(latente → LinearSVC).

| Caminho | Modo | F1 CV | F1 teste | IC 95% |
|---|---|---|---|---|
| B (CNN1D) | `direct` | 0,3343 ± 0,0017 | 0,3333 | [0,329; 0,337] |
| B (CNN1D) | `latent_rf` | 0,4998 ± 0,0070 | 0,5040 | [0,495; 0,512] |
| B (CNN1D) | `latent_lsvc` | 0,5043 ± 0,0053 | 0,5039 | [0,495; 0,512] |
| C (CNN2D) | `direct` | 0,3333 ± 0,0000 | 0,3333 | [0,329; 0,337] |
| C (CNN2D) | `latent_rf` | 0,4983 ± 0,0069 | 0,4978 | [0,489; 0,506] |
| C (CNN2D) | `latent_lsvc` | 0,5021 ± 0,0025 | 0,4979 | [0,489; 0,507] |

**Leitura do modo `direct`:** colapsa para 0,3333 (= prever sempre a mesma
classe em problema binário balanceado: F1=0,667 para a classe prevista,
F1=0 para a outra, média 1/3). O texto da dissertação trata isso
explicitamente como **falha de otimização, não evidência de
indistinguibilidade** — os próprios latentes extraídos da mesma rede que
colapsa, entregues a um classificador externo, voltam ao nível do acaso
(não ficam também em 0,33), o que mostra que o colapso é do treino
fim-a-fim, não da representação. A evidência dos Caminhos B e C vem dos
modos latentes.

Ambos os modos latentes de B e C ficam com IC cobrindo 0,50 — mesmo teto do
Caminho A, mesmo com representações aprendidas diretamente dos bytes
(sem qualquer suposição manual sobre quais padrões importam).

## 7.3 Caminho D — Híbrido (60k)

**Fonte:** `dissertacao/resultados.tex` **e** artefato bruto localizado em
`C:\Users\nycol\Downloads\resultados_caminhoD_final\reports\
keyholdout_2class_60k_v1_hybrid\` (`cv_results.json`, `final_results.json`,
`_final_cache.pkl`, `comparison_table.md`, `mcnemar_table.md`) — **não
está neste repositório**, mas foi lido e cruzado diretamente. Os dois
números batem exatamente.

| Modelo | F1 CV | F1 teste | IC 95% | Bal.Acc |
|---|---|---|---|---|
| RF | 0,5002 ± 0,0030 | 0,5011 | [0,492; 0,510] | 0,5011 |
| XGBoost | 0,4978 ± 0,0040 | 0,4952 | [0,487; 0,504] | 0,4952 |

McNemar RF vs XGBoost: estatística 0,875, p=0,3496, não significativo.

Vetor de entrada: 307D clássicas + 512D latente CNN1D + 128D latente CNN2D =
**947D**. A fusão das três representações não superou nenhuma isoladamente.

**Achado adicional (só no texto da dissertação, não verificável aqui sem o
JSON bruto de seleção do fold):** o Jaccard médio do Boruta sobre o espaço
híbrido caiu para **0,0013** (vs. 0,32 no Caminho A), com número de
atributos confirmados variando de 1 a 73 entre os folds — em um espaço 3×
maior, a seleção ficou essencialmente aleatória entre folds. Combinado com
a não convergência do SVM no Caminho A (§7.1), é citado no texto como
segundo indicador independente de ausência de estrutura estável.

## 7.4 Ablação do seletor de features (2026-08-12) — não documentada em nenhum outro lugar

**Fonte:** `reports/ablation_fs_60k/` (presente neste repositório —
`ablation_results.json`, `ablation_table.md`, `permutation_null.json`,
`run.log`), gerado por `scripts/run_ablation_fs_60k.py` (474 linhas, script
novo, não referenciado em nenhum CLAUDE.md/CONTEXTO_ARTIGO.md/memória
anterior a esta análise).

**Motivação declarada no próprio script:** o experimento principal (§7.1)
reportou F1≈0,50 com o pipeline de seleção reduzindo para **1 única
feature sobrevivente** (`ngram_2_chi2`) no modelo final — o que levanta a
pergunta legítima de saber se a ausência de sinal é uma propriedade dos
criptogramas ou um artefato do seletor (em particular, o `VarianceThreshold`
em unidades absolutas elimina 278 das 307 features, incluindo todo o
histograma de bytes, porque frequência relativa tem variância ~5,9e-8 —
um corte de escala, não de informação).

**4 braços testados**, todos sob o mesmo protocolo do experimento principal
(240/60 chaves, 5-fold `GroupKFold`, `StandardScaler` só no treino, IC 95%
bootstrap 1000×), com LR/LinearSVC/RF/XGBoost (SVM-RBF omitido por custo):

| Braço | Nº features | Melhor F1 teste | Pior F1 teste |
|---|---|---|---|
| `all307` — todas as 307, sem seleção | 307 | 0,5044 (LR/LinearSVC) | 0,4980 (RF) |
| `vt29` — só as 29 que sobrevivem ao VT | 29 | 0,5024 (LR) | 0,4918 (XGBoost) |
| `hist256` — só o histograma (descartado pelo VT) | 256 | 0,5024 (LR) | 0,4918 (XGBoost) |
| `top1` — só `ngram_2_chi2` (o que sobra no relatório principal) | 1 | 0,5024 (LR/LinearSVC) | 0,4952 (XGBoost) |

**Todos os 16 pares braço×modelo têm IC 95% cobrindo 0,50.** Removendo o
seletor inteiramente (`all307`) o resultado não muda — o teto de F1≈0,50 não
é efeito do `VarianceThreshold` nem do Boruta.

**Teste de permutação** (distribuição nula empírica, 20 repetições, braço
`all307`, LR e XGBoost): dois esquemas de embaralhamento de rótulo —
`by_key` (rótulo constante por chave) e `within_key` (permuta dentro da
chave, preserva balanço 100/100). Em ambos os esquemas, o melhor F1
observado (0,5044) fica dentro da faixa nula (p2.5–p97.5 ≈ [0,49; 0,51]),
com **p empírico entre 0,19 e 0,29** (correção de Phipson & Smyth 2010) —
não significativo. Isso estabelece o baseline nulo contra um valor medido
empiricamente, não só contra o 0,50 teórico.

## 7.5 Controles positivos

| Controle | Dataset | Classes | F1 | Fonte |
|---|---|---|---|---|
| Vigenère 3-class (64KB) | `control_vigenere_64k_v1` | 3 (Ascon/GIFT/Vigenère) | RF 0,663 / XGB 0,670, IC não cobre 0,50 para a classe Vigenère (recall/precisão ≈1,0) | `reports/control_vigenere_64k_v1_cv/` (repo) |
| Vigenère vs. PRNG-Random (64KB) | `vigenere_vs_random_v1` | 2 | **1,0000** em todos os modelos | `reports/vigenere_vs_random_v1_cv/` (repo) |
| ECB natural (legado) | `control_3class_v1` | 3 | RF 0,360 | histórico (memória) |
| ECB repetitivo (legado) | `control_repetitive_3class_v1` | 3 | RF 0,673, ECB recall/precisão 100% | histórico (memória) |

O texto da dissertação usa a versão consolidada (30k Vigenère + 30k random =
60k, 93 features retidas, recall/precisão 1,0) como o controle positivo
citado no capítulo de resultados — consistente com `vigenere_vs_random_v1`.

## 7.6 Onde ficam fisicamente os artefatos — mapa de sincronização

| Caminho | `reports/` neste repositório | Local real dos artefatos |
|---|---|---|
| A | ✅ completo (`keyholdout_2class_60k_v1_cv/`) | — |
| B, C | ❌ `keyholdout_2class_60k_v1_cnn/{ckpts,confusion_matrices}` vazios | não localizado (nem no repo nem em `Downloads/`, nas buscas feitas) |
| D | ❌ `keyholdout_2class_60k_v1_hybrid/{ckpts,confusion_matrices}` vazios | ✅ `C:\Users\nycol\Downloads\resultados_caminhoD_final\reports\keyholdout_2class_60k_v1_hybrid\` |
| Ablação | ✅ completo (`ablation_fs_60k/`) | — |

Ação recomendada em [08_achados_e_pendencias.md](08_achados_e_pendencias.md).

## 7.7 Síntese

Os 4 Caminhos (10 combinações de representação/classificador, excluindo os
2 modos diagnósticos `direct` de B/C) convergem para IC 95% de F1-macro
cobrindo 0,50, com McNemar não significativo entre classificadores em todos
os pares testados. A ablação (§7.4) descarta a hipótese de que isso seja
artefato do seletor de features. Os controles positivos (§7.5) descartam a
hipótese de que o pipeline seja incapaz de detectar sinal quando ele existe.
Sob o protocolo avaliado (key-holdout estrito, 64KB, corpus Gutenberg,
implementações de referência), **H₀ não foi rejeitada em nenhum dos quatro
caminhos experimentais nem na ablação de robustez.**
