# Relatório — Planejamento do novo experimento (v2)

**Atualizado em 2026-08-21.** Resumo das decisões para a próxima rodada
experimental — a ação e o motivo de cada uma. O plano técnico completo está em
`docs/plano_experimento_v2/`.

---

## 1. Algoritmos

**Ação:** o experimento principal compara quatro esquemas AEAD leves —
Ascon-AEAD128, GIFT-COFB, Grain-128AEAD e Sparkle (Schwaemm) — em classificação
de 4 classes. O AES-128-ECB entra como controle positivo, analisado à parte
(binário, contra o Ascon), mas gerado no mesmo dataset.

**Correção:** o wrapper do Ascon será ajustado para a parametrização de taxa
128 bits (`ascon128av13`), que é a que o NIST SP 800-232 final define como
"Ascon-AEAD128" — a implementação atual usa a parametrização pré-padronização
(taxa 64 bits). Todo o dataset será regerado.

**Por quê:** os quatro algoritmos cobrem três mecanismos de não-linearidade
distintos (S-box, ARX, realimentação NFSR) e três famílias construtivas
(esponja, cifra de bloco, fluxo) — nenhum estudo da RSL testa qualquer
finalista LWC do NIST nem modo AEAD, então o conjunto preenche a lacuna
identificada na revisão. O AES-ECB substitui o Vigenère como controle,
respondendo à crítica do SBSeg.

## 2. Dataset

**Ação:** 300 chaves × 100 amostras/chave × 5 algoritmos = 150.000 criptogramas
de 64 KB, encadeados (mesma chave, nonce e plaintext para os cinco algoritmos
em cada amostra). Plaintext: 80% texto (corpus Gutenberg) e 20% imagens
(ImageNet 256×256 em tons de cinza = exatamente 64 KB), sorteio por amostra
dentro de cada chave.

**Geração pseudoaleatória:** as chaves e a amostragem de plaintext passam a
usar um gerador CTR_DRBG com AES, conforme o padrão NIST SP 800-90A, com seed
fixa (reprodutível) e validado contra os vetores de teste oficiais do NIST —
substituindo o gerador do NumPy, que não tem aceitação na literatura de
criptografia.

**Por quê:** o encadeamento garante que qualquer diferença detectada só pode
vir do algoritmo; a mistura de fontes de plaintext amplia a generalidade do
resultado e viabiliza a réplica de um estudo da literatura que usa imagens
cifradas (Mishra et al., 2021); o DRBG alinha a geração ao mesmo arcabouço de
padrões NIST já usado no resto do trabalho (SP 800-232, SP 800-22).

## 3. Classificadores — seis caminhos

**Ação:** além dos quatro caminhos do experimento anterior (A: features
clássicas com RF/SVM/LinearSVC/XGBoost/LR + stacking + réplicas de HKNNRF,
XGB-LGBM e do Transformer do E20 da literatura; B: CNN-1D; C: CNN-2D; D:
híbrido), dois novos: **E** — Transformer com atenção hierárquica sobre o
criptograma completo, **contribuição própria** (nenhum estudo da RSL aplica
atenção diretamente sobre bytes crus; a réplica fiel do E20, que usa features
reduzidas em vez de bytes crus, foi movida para o Caminho A — ver correção
abaixo); **F** — meta-classificador sobre as probabilidades de saída de todos
os modelos, calculadas **out-of-fold** (nunca de um modelo que viu a amostra
no treino, para não vazar por memorização). A busca de hiperparâmetros do SVM
passa a rodar em subamostra (correção de custo, mantendo a busca em si).

**Correção (revisão crítica de 2026-08-21):** o plano original descrevia o
Caminho E como "réplica do desenho de Yuan et al. 2026". Não é: o E20 aplica
Transformer sobre um vetor de 8 features (NIST+entropia, filtradas), e sua
"hierarquia" é uma cascata de rótulos (estrutura → algoritmo); o Caminho E
aplica atenção sobre a sequência crua de bytes, com hierarquia de atenção
(janela local → global) — mesma palavra, duas coisas diferentes. Corrigido
para: E como contribuição própria, e uma réplica fiel do E20 adicionada ao
Caminho A. Detalhe em `plano_experimento_v2/03_classificadores.md` §3.1/§3.5.

**Por quê:** o Transformer cobre a única representação ainda não testada
(dependência de longo alcance) e foi pedido explícito de dois revisores do
SBSeg; o meta-classificador testa combinação de decisões (diferente da fusão
de representações do caminho D); as réplicas nomeadas permitem afirmar que as
técnicas específicas da literatura foram testadas sob nosso protocolo.

## 4. Features

**Ação:** as 307 features atuais + a suíte NIST SP 800-22 completa (15 testes,
em nível de bit, com validação contra os vetores de referência do próprio
padrão) + 5 features da literatura (assimetria/curtose e densidade espectral
de Welch, de Zhou 2025; histograma de blocos de bits variáveis, de de Mello &
Xexéo 2016 e Barbosa et al. 2017; compressão lzma; peso de Hamming, de Zhao et
al. 2023) + estatísticas separadas para a região da tag e do payload, com
**janela de tag comum de 8 bytes** (o mínimo entre os algoritmos) na
comparação principal.

**Correção (revisão crítica de 2026-08-21):** a especificação original usava
o `ABYTES` real de cada algoritmo (16 bytes; 8 no Grain) para as estatísticas
de tag. Isso introduz viés: entropia/nunique/χ² calculados sobre amostras tão
pequenas (n≪256 símbolos possíveis) tendem a valores que dependem quase só do
tamanho da janela, não do conteúdo — ou seja, a "estatística da tag" separaria
o Grain dos outros três por comprimento de janela, reintroduzindo `len_ct`
como feature pela porta dos fundos. Corrigido para janela comum de 8 bytes na
comparação principal; a tag completa por algoritmo vira análise exploratória
à parte, com o viés declarado. Peso de Hamming também deixou de ser
"descartado" — é a representação que define a réplica do XGB-LGBM (Zhao et
al. 2023), sem ela a réplica não testa a técnica deles. Detalhe em
`plano_experimento_v2/02_features_e_selecao.md`.

**Por quê:** a tag é gerada por mecanismo estruturalmente diferente em cada
algoritmo, enquanto o payload é desenhado para parecer uniforme nos quatro —
é o lugar mais provável de assinatura. As demais adições cobrem granularidades
e famílias que a literatura usa e o conjunto atual não cobria.

## 5. Seleção de features

**Ação:** padronização z-score antes do filtro de variância (corrige o corte
por escala que descartava o histograma inteiro); Informação Mútua rebaixada a
corte de conveniência (sem pretensão estatística); mRMR define o conjunto
final; Boruta segue como diagnóstico; a validação sinal-vs-ruído acontece no
resultado final, por teste de permutação. Sem RFE (preservar a comparação
justa entre classificadores).

## 6. Protocolo, métricas e relato

**Ação:** split por chave e validação cruzada inalterados. Ablações: com/sem
key-holdout (demonstra empiricamente a inflação por reuso de chave); com/sem
truncamento do criptograma do Grain (isola o artefato do tamanho da tag).
Métricas: F1-macro, acurácia (simples e balanceada), **precisão e recall por
classe em todas as tabelas**, IC bootstrap, McNemar, ECE, AUC-ROC por classe.
**Regra fixa: toda métrica é impressa no momento em que é calculada, e a
matriz de confusão é sempre gerada — impressa no console, salva em números e
salva como imagem — por uma função de relato única usada em todos os
caminhos, com gravação incremental em disco.**

**Por quê:** as duas ablações transformam salvaguardas do protocolo em
demonstrações empíricas; o relato imediato e uniforme atende ao pedido de
explicitação de métricas e evita a perda de resultados ocorrida na rodada
anterior.

## 7. Recomendações em avaliação (ainda não confirmadas)

Da revisão técnica do plano, os itens mais relevantes pendentes de decisão:
controles negativos (classe de bytes aleatórios + embaralhamento de bytes de
criptogramas reais — conecta com o ponto 3 da reunião de 27/07); análise par a
par das 6 combinações de algoritmos além do agregado; cálculo de poder
estatístico a priori; hipótese primária declarada com correção de múltiplas
comparações; pré-registro do plano de análise; variante do Ascon com rodadas
reduzidas como calibração de sensibilidade; publicação do dataset como
benchmark público. Lista completa em
`docs/plano_experimento_v2/05_execucao_riscos_pendencias.md`.

## 8. Pendências de redação (deferidas para depois do experimento)

Reformulação do objetivo/caracterização do problema, uniformização da
definição de IND-CPA, parágrafo explícito sobre overfitting, incorporação da
RSL como base da lacuna, e itens de forma apontados pelo SBSeg.
