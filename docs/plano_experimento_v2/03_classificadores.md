# 3. Classificadores — os 6 Caminhos

| Caminho | Representação | Modelos | Status |
|---|---|---|---|
| A | features clássicas (~400D → seletor) | RF, SVM-RBF, LinearSVC, XGBoost, LR + stacking próprio + 3 réplicas da literatura (HKNNRF, XGB-LGBM, Transformer-E20) | ✅ |
| B | sequência de bytes crua (CT completo) | CNN1D `direct` + latente(512D)→RF/LinearSVC | ✅ |
| C | co-ocorrência de bigramas 256×256 | CNN2D `direct` + latente(128D)→RF/LinearSVC; + réplica E05 no subconjunto imagem | ✅ |
| D | fusão: clássicas + latentes de B, C **e E** | RF, XGBoost | ✅ |
| E | Transformer hierárquico sobre bytes | fim-a-fim + latente→clássico | ✅ novo |
| F | probabilidades de saída de A–E | meta-classificador (regressão logística) | ✅ novo |

**Dummy removido** ✅ — baselines já cobertos pelo acaso teórico (0,25) e pelo
teste de permutação empírico.

## 3.1 Caminho A

**Modelos:** RF(500), SVM-RBF, LinearSVC(C=1), XGBoost(500), LR — seeds 7,
protocolo inalterado.

**Correção do SVM ✅ (aceita pelo Nycolas):** a busca de hiperparâmetros
(grade 4×4 × 3-fold interno = 48 fits) passa a rodar numa **subamostra fixa de
~20–30k**; só o fit final (1 treino, sem grade) usa o treino completo do fold.
Motivo, com dado real do v1: a busca no fold inteiro custou 245–2.965s por fold
(soma 139 min; variação de 12× entre folds — que é, em si, evidência de segunda
ordem de H₀ e deve continuar sendo reportada). No v2 (76.800/fold, custo
O(n²)–O(n³)) o custo sem correção extrapolaria para 15–30h só de SVM. Com a
correção, a parte cara fica de tamanho constante.

**Stacking próprio ✅:** `StackingClassifier` (ou votação) sobre os 5 modelos —
quase grátis, os modelos-base já são treinados de qualquer forma.

**Réplicas nomeadas da literatura ✅:**
- **HKNNRF** (Yuan et al. 2022, PeerJ CS) — KNN+RF; KNN é adição trivial.
- **XGB-LGBM** (Zhao et al. 2023, IEEE Access — o maior resultado real entre
  compostos clássicos da RSL, 90,5%) — exige LightGBM como dependência nova.
  **Correção:** a representação que define o estudo é a distribuição de peso
  de Hamming, não features genéricas — sem ela a réplica testa só o
  classificador deles, não a técnica. Peso de Hamming passou de "descartada"
  para obrigatória no vetor padrão (`02_features_e_selecao.md`), então esta
  réplica já nasce com a representação correta.
- **Transformer sobre features NIST** (réplica fiel do E20 — Yuan et al.
  2026, **adicionada aqui**; ver correção de enquadramento em §3.5): filtro
  por estatística F seguido de RFE sobre a suíte NIST+entropia (reduzindo a
  ~8 features, como no artigo original) → Transformer encoder-only sobre esse
  vetor de baixa dimensão. Diferente do Caminho E, que opera sobre a
  sequência crua de bytes — esta réplica usa a mesma representação do estudo
  original, o que sustenta de fato a alegação "a técnica do Yuan et al., sob
  nosso protocolo, dá X".

Valor: poder afirmar "a técnica de Fulano, sob nosso protocolo, dá X" — não
apenas "tentamos algo parecido".

## 3.2 Caminho B — CNN1D

Como no v1 pós-correções: CT completo (65.552; 65.544 no braço controlado),
primeiro bloco kernel 8/stride 4, batch 8. **Participa da ablação de
truncamento do Grain** — é a representação mais vulnerável ao artefato de
comprimento (padding de zeros posicional).

## 3.3 Caminho C — CNN2D

Representação canônica: co-ocorrência 256×256 (adjacência real).

**✅ Correção de condicionamento numérico (aprovada 2026-08-21; protocolo no 06 Fase 7):** a matriz
normalizada para somar 1 tem média por célula ≈1,5e-5 — condicionamento ruim
para a primeira conv, possível causa parcial do colapso observado no v1.
Testar 3 variantes baratas: escala ×65536, `log1p`, padronização por canal.

**Réplica E05 ✅ (Mishra et al. 2021):** no **subconjunto imagem** (20% do
dataset), alimentar o criptograma reformatado nas dimensões da imagem original
(reshape 256×256) — réplica da metodologia deles sob protocolo rigoroso, como
comparação **secundária** à co-ocorrência (não substituição). **Correção:** o
reshape usa só o **payload** (65.536 bytes = 256×256 exato para amostras de
imagem, o mesmo tamanho da imagem original); a tag (16 ou 8 bytes) fica de
fora — o CT completo (65.552/65.544 bytes) não cabe num reshape 256×256 sem
sobra, e a operação precisa estar especificada, não decidida no código na
hora. Precedente relevante: E05 caiu de 98,78% (chave fixa) para 31,1% (chave
aleatória).

## 3.4 Caminho D — Híbrido

Atualização ✅: vetor de fusão passa a ter **4 representações** — 307D+
clássicas + latente CNN1D (512D) + latente CNN2D (128D) + **latente do
Transformer (E)**. Seletor (top_k/mrmr ampliados) dentro do fold → RF/XGBoost.
Depende de B, C e E treinados.

## 3.5 Caminho E — Transformer hierárquico sobre bytes ✅ (desenho "opção A")

**Correção de enquadramento:** este caminho **não é réplica do E20**. O E20
(Yuan et al. 2026) aplica Transformer encoder-only sobre um vetor de **8
features** (NIST+entropia, reduzidas de 76 por filtro F + RFE), e usa
"hierárquico" no sentido de **cascata de rótulos** — classifica primeiro a
estrutura (SP vs. Feistel), depois o algoritmo específico dentro do cluster.
O Caminho E aplica atenção diretamente sobre a **sequência crua de 65.552
bytes**, e "hierárquico" aqui é **arquitetura de atenção em duas escalas**
(janela local → global) — são dois usos distintos da mesma palavra que só
coincidem no rótulo. Chamar isso de réplica é frágil diante de qualquer
avaliador que conheça o E20; a réplica fiel (mesma representação, mesma
tarefa em cascata) foi movida para o Caminho A (§3.1).

- Janelas locais de ~1024 bytes (≈64 janelas por CT) → atenção intra-janela →
  embedding por janela → **atenção global** entre as 64 janelas → latente +
  cabeça de classificação. `extract_latent()` obrigatório (alimenta D e F).
- **Patch embedding de 16 bytes/token dentro da janela** (padrão ViT), não um
  token por byte: atenção byte-a-byte sobre janelas de 1024 aloca ~2,1 GB só
  na matriz de atenção com batch 2, e passa de 8 GB em GPU. O patch reduz a
  atenção por um fator de 256 e mantém intacta a hierarquia local→global, que
  é a contribuição de fato. **Precisa constar na descrição da arquitetura na
  dissertação** — é desvio do texto original deste plano, não do seu espírito.
- Atenção completa sobre 65.552 posições é matematicamente inviável (~4,3e9
  células por cabeça) — a hierarquia local→global é necessidade de
  engenharia, não escolha estilística.
- Racional, revisado: nenhum estudo da RSL aplica atenção diretamente sobre a
  sequência crua de bytes de um criptograma — é a lacuna representacional
  genuína que falta cobrir (dependência de longo alcance sem passar por
  features manuais), como **contribuição própria**, não como reprodução de
  método publicado. Resultado nulo fecha essa porta, positivo seria
  genuinamente novo — nenhum dos dois desfechos depende de semelhança com o
  E20.
- Opções B (stem CNN + atenção) e C (atenção sobre features) foram descartadas
  — B como fallback se A estourar o orçamento de engenharia.

## 3.6 Caminho F — meta-classificador ✅

- Entrada: vetor de probabilidades de saída de todos os modelos de A–E;
  meta-modelo: regressão logística; treinado/validado sob o MESMO key-holdout +
  CV; reportado como etapa final separada, **depois** dos caminhos individuais.
- **Pré-requisito duro, não opcional — probabilidades out-of-fold:** a
  probabilidade que entra no vetor de F para a amostra X **nunca** pode vir de
  um modelo que viu X no treino — senão F aprende a explorar memorização dos
  modelos-base em vez de combinação de sinal genuíno (vazamento clássico de
  stacking: é assim que `StackingClassifier` e qualquer framework sério de
  ensemble funcionam por padrão, e por isso não é opcional aqui). Duas
  consequências de infraestrutura, antes inexistentes na especificação:
  - Caminhos A–E precisam **compartilhar a mesma partição de folds** (mesmos
    `key_id` em cada fold, em todos os caminhos) — verificado por assert
    explícito, nunca assumido por coincidência de seed.
  - A função única de relato (`04_protocolo_metricas_validacao.md` §4.4)
    passa a persistir **predição e probabilidade por amostra**, não só
    métricas agregadas — sem isso a matriz out-of-fold que F exige não é
    reconstruível depois do fato, sobretudo para B/C/E (GPU, caros de
    re-treinar só para extrair predições — o mesmo tipo de perda de artefato
    já documentado para os Caminhos B/C do v1).
- **Pré-requisito de calibração — duro para os ramos com LinearSVC/SVM-RBF:**
  `LinearSVC` não tem `predict_proba` nativo (hinge loss) — exige
  `CalibratedClassifierCV` (Platt/isotônica) por cima. `SVC` com
  `probability=True` calibra via CV interna própria, que também precisa ser
  consciente de chave (senão é um segundo nível de vazamento aninhado dentro
  do primeiro). Reportar ECE por modelo-base continua obrigatório.
- Nota cética registrada: se F der sinal com TODOS os individuais no acaso,
  investigar vazamento/artefato antes de aceitar — combinação não cria sinal
  do nada.

## 3.7 ✅ Recomendações transversais — APROVADAS (2026-08-21, formatos reduzidos; execução no 06, Fases 7–8)

1. **Busca de hiperparâmetros também nos modelos profundos** (random search
   documentada: lr, profundidade, largura). Lógica: nulo com tuning fraco é
   evidência fraca — para defender H₀ é preciso ter tentado MAIS. Foi crítica
   explícita da Review 4 do SBSeg.
2. **3 seeds nos modelos profundos** — reportar média±dp entre inicializações;
   só 1/21 estudos da RSL faz reamostragem repetida, diferencial barato.
3. **Diagnóstico do latente** — medir posto efetivo/variância explicada dos
   latentes das CNNs/Transformer; evita a ambiguidade do v1 ("latente→RF no
   acaso" não significa nada se o latente estiver degenerado pós-colapso).
4. **Reportar contagem de parâmetros por arquitetura** — comparabilidade de
   capacidade entre CNN (~190k) e Transformer (potencialmente milhões).
