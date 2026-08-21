# Análise crítica do plano do experimento v2

**Data:** 2026-08-21. **Escopo:** leitura crítica de `docs/plano_experimento_v2/`
(5 arquivos), cruzada com a RSL (`RSL_resumida`, trechos da `RSL_completa`),
os 4 pareceres do SBSeg (`Analise_sbseg_artigo.txt`), o relatório ao orientador
e os resultados do v1 (`docs/analise_completa/`). Busca por erros factuais,
conflitos internos de especificação, riscos subestimados e melhorias.

O que foi conferido e **passou**: valores de referência (acaso 0,25 / colapso
0,10 no 4-classes; 0,50/0,333 no binário — contas corretas), contagens de
amostras (150k, 24k teste, 76.800 por fold), aritmética da atenção completa
(65.552² ≈ 4,3e9), limiar do Maurer (524.288 > 387.840 para L=6), armazenamento,
lógica do encadeamento com split por chave (slots inteiros caem do mesmo lado do
split — correto). A decisão de rebaixar o Boruta a diagnóstico, o escopo do
CTR_DRBG (só geração), o descarte do Romulus, a ausência de RFE e o MI como
corte de conveniência estão bem justificados e eu os manteria como estão.

---

## 1. Erros factuais e de especificação

### 1.1 O Caminho E **não é** réplica do E20 — o enquadramento está errado

O plano (§3.5) diz que o Transformer hierárquico sobre bytes "é essencialmente
o desenho hierárquico do E20", e o relatório ao orientador vai além: "réplica do
desenho de Yuan et al. 2026". A RSL descreve outra coisa: o E20 aplica um
**Transformer encoder-only sobre 76 features candidatas (NIST + entropia)
reduzidas a 8 por filtro F + RFE** — não sobre bytes crus — e o "esquema
hierárquico" dele é hierarquia **no espaço de rótulos** (primeiro estrutura,
depois algoritmo dentro do cluster), não atenção hierárquica em janelas.

Consequências:

- O Caminho E como desenhado é uma **contribuição própria** (atenção sobre
  bytes crus é justamente o que nenhum estudo da RSL faz) — o que é *melhor*
  para a dissertação, mas precisa ser vendido como tal, não como réplica.
  Se um revisor da banca conhecer o E20, o enquadramento atual vira uma
  fragilidade gratuita.
- A réplica **fiel** do E20 é barata: Transformer raso sobre o vetor de
  features NIST (que o v2 já vai calcular de qualquer forma). Cabe como mais
  um modelo do Caminho A, na mesma prateleira do HKNNRF e do XGB-LGBM.

### 1.2 Features de tag × braço de truncamento: conflito interno que fabrica artefato

Este é, na minha leitura, o problema técnico mais sério do plano. Três fatos
que os documentos afirmam separadamente colidem entre si:

1. §2.1: features de tag = estatísticas sobre os "últimos `ABYTES`" (16 bytes;
   8 no Grain), incluindo histograma, entropia e χ².
2. §1.6: braço `controlado` = "todos cortados para 65.544 **antes de qualquer
   feature/CNN**".
3. CT = payload ‖ tag: cortar no fim corta a **tag**.

Colisão A — no braço controlado, "os últimos 16 bytes" de Ascon/GIFT/Sparkle
viram 8 bytes de payload + 8 bytes de meia-tag: a feature perde o significado
declarado. Colisão B — pior e independente do braço: **estatísticas em janelas
de 8 vs. 16 bytes separam o Grain por viés de estimador, não por conteúdo**. A
entropia de Shannon de n bytes uniformes com n≪256 é ≈log₂(n): ~3,0 bits para
8 bytes vs. ~4,0 bits para 16 — separação quase determinística. O mesmo vale
para `nunique`, `max_freq` normalizado e qualquer χ². As features de tag, como
especificadas, são **`len_ct` disfarçado** — exatamente o metadado que a Regra
de Ouro 5 proíbe como feature.

Correção que resolve os dois problemas de uma vez:

- **Janela de tag comum de 8 bytes** (o `min(ABYTES)` entre os algoritmos)
  para as features comparáveis do experimento principal — mesma janela, mesmo
  estimador, mesmo viés para todos.
- Features sobre a tag completa por algoritmo ficam como análise
  **exploratória, só no braço cru**, com o viés de estimador declarado.
- No braço controlado, se o truncamento for mantido para o Caminho A, cortar
  **payload** (usar `payload[:65.528] ‖ tag` para os de tag 16) em vez de
  cortar a tag — ou, mais simples: manter o truncamento apenas para a CNN1D
  (onde o canal de vazamento é o padding posicional) e resolver o Caminho A
  pela janela comum + auditoria das features de contagem absoluta
  (`runs_count`, `lz_complexity` bruto), que são o único canal de comprimento
  restante nas 307.

### 1.3 Réplica XGB-LGBM sem a representação do estudo replicado

O argumento de venda das réplicas é "a técnica de Fulano, sob nosso protocolo,
dá X". O E07 (Zhao et al. 2023) é definido pela **distribuição de peso de
Hamming** como representação — e o plano lista peso de Hamming como descartado,
com um "opcional apenas para fidelidade da réplica" em nota. Isso é
inconsistente: sem a representação, o que se tem é "o classificador deles sobre
as nossas features", que não sustenta a frase de venda. Como a feature é
trivial de calcular, a resolução óbvia é incluí-la no braço da réplica (e ela é
mais uma família candidata para o seletor, de graça).

### 1.4 Réplica E05: o reshape não fecha

256×256 = 65.536, mas o CT tem 65.552 bytes (65.544 no Grain). O reshape da
réplica precisa operar sobre o **payload sem a tag** — um detalhe de uma linha,
mas que precisa estar na especificação para não virar decisão silenciosa de
implementação (e o E05 original, em ECB, tinha CT do tamanho exato do PT — a
diferença é nossa, não deles).

### 1.5 Nonce do Sparkle não especificado

O plano fixa a injeção do nonce só para o Grain (12 bytes menos
significativos). Schwaemm256-128 tem nonce de **256 bits** — o mapeamento do
contador global de 128 bits para 256 (zero-padding? em qual extremidade?)
precisa ser definido antes do wrapper, pela mesma razão que motivou a regra do
Grain.

---

## 2. Lógica experimental: dois pontos onde o plano promete o que o desenho não entrega

### 2.1 A ablação key-holdout on/off provavelmente não vai "demonstrar a inflação"

O plano (§4.2) vende a ablação como demonstração empírica da inflação por reuso
de chave. Mas nos 4 AEADs íntegros, sob H₀, **não há o que memorizar**: com
nonce único por amostra, duas amostras da mesma chave são estatisticamente
independentes no ciphertext-only. O resultado esperado da ablação no
experimento principal é *nenhuma diferença* — informativo (mostra que nem o
protocolo frouxo acha sinal), mas o oposto da inflação prometida.

Onde a inflação **é** demonstrável: no controle AES-ECB. Chave fixa → codebook
fixo → blocos de 16 bytes frequentes do corpus reaparecem idênticos entre
amostras da mesma chave → um modelo memoriza blocos de CT específicos da
chave → split aleatório infla, key-holdout desinfla. Recomendação: rodar a
ablação **nos dois braços** (4-classes e controle ECB) e pré-registrar as
predições divergentes — vira uma demonstração muito mais forte do que a versão
atual, e responde melhor ao ponto do orientador.

### 2.2 Caminho F: o risco não está listado onde deveria

A nota cética do §3.6 está certa, mas o plano não especifica a única disciplina
que evita o problema: o meta-classificador precisa ser treinado sobre
**probabilidades out-of-fold** dos modelos-base, com a mesma partição de folds
em todos os caminhos. Se as probabilidades vierem de modelos que viram aquelas
amostras no treino, o F "acha sinal" por construção. Isso puxa dois requisitos
de infraestrutura que hoje não estão em nenhuma especificação:

1. **A função única de relato precisa persistir predições e probabilidades por
   amostra** (não só métricas e matrizes). Sem isso, F, McNemar, ECE e a
   calibração não podem ser recomputados post-hoc — e o v1 já perdeu artefatos
   por menos (Caminhos B/C até hoje sem JSON bruto no repositório).
2. LinearSVC e SVM não emitem probabilidade nativamente — a calibração
   (Platt/isotônica nos folds de validação) deixa de ser "pré-requisito
   recomendado" e vira dependência dura do F.

No mesmo tema: o `StackingClassifier` do sklearn faz CV interna **não
group-aware** — os meta-features do stacking do Caminho A vazariam entre chaves
dentro do trainval. Precisa de `cv=` com splits pré-definidos por chave (ou
stacking manual). O mesmo vale para a CV interna do GridSearchCV do SVM.

---

## 3. Inversão de prioridades: o que é 🔶 deveria ser ✅, e vice-versa

A RSL do próprio projeto prevê o resultado do v2: o que separa de forma estável
é propriedade estrutural grosseira, payload de AEAD íntegro é uniforme por
construção, e o confounder de comprimento (Grain) está controlado por desenho.
O prior honesto é H₀ de novo. Nesse cenário, o valor da dissertação **não** vem
dos classificadores — vem do protocolo que torna o nulo interpretável e
citável. Só que os itens que fazem exatamente isso estão todos pendentes de
confirmação (🔶): poder a priori, pré-registro, análise par a par, controles
negativos, FDR, benchmark público. Enquanto isso, os itens mais caros e de
menor valor evidencial esperado (E, F, réplicas, 3 seeds × HP search) estão ✅.

Se o orçamento apertar no meio do caminho, o corte vai acontecer na ordem
errada. Minha posição: promover a ✅ obrigatório, antes de qualquer geração de
dados — (a) hipótese primária completa, (b) poder/equivalência, (c) pré-registro,
(d) análise par a par, (e) controles negativos, (f) sanity check do `len_ct`,
(g) benchmark de extração. E aceitar explicitamente que E/F/réplicas são a
camada sacrificável do plano.

### 3.1 A hipótese primária está subespecificada

"F1-macro 4-classes no Caminho A" não fecha o endpoint. Faltam três decisões,
todas com potencial de virar acusação de pesca se ficarem para depois:

- **Qual braço?** No braço cru, o Grain separável por artefato de comprimento
  produz F1-macro ≈ 0,50 com os outros três no acaso — 2× o acaso de 0,25 sem
  nenhum sinal criptográfico. O primário tem que ser o braço **controlado**
  (com o cru como análise do artefato).
- **Qual teste?** "IC cobre 0,25" não é evidência *a favor* de H₀ — ausência
  de significância não é evidência de ausência. Para uma dissertação que
  defende um nulo, o arcabouço correto é **teste de equivalência (TOST)**:
  pré-registrar uma margem δ (ex.: 1 p.p., justificada pelo poder) e mostrar
  que o IC 95% cai inteiro dentro de [0,25−δ, 0,25+δ]. Isso transforma "não
  achamos" em "demonstramos equivalência ao acaso com margem δ" — a versão
  forte da resposta à Review 4.
- **Qual bootstrap?** As 24.000 amostras de teste são 100 por chave × 60
  chaves × 4 algoritmos — amostras agrupadas. O IC deve vir de **bootstrap por
  cluster de chave** (reamostrar chaves, não amostras). Sob H₀ dá quase o
  mesmo número; sob qualquer sinal correlacionado a chave, o bootstrap i.i.d.
  subestima o IC — e é exatamente a objeção "aprendeu correlação chave-
  mensagem?" da Review 1. Custa uma linha.

---

## 4. Riscos práticos subestimados

### 4.1 Custo de extração das features NIST — o maior risco de cronograma do plano

O §5.2 trata o benchmark de extração como recomendação 🔶. Os números dizem que
é bloqueante: 150.000 amostras × 524.288 bits. Berlekamp-Massey em blocos de
M=500 → ~1.050 blocos × O(M²) ≈ 2,6e8 operações por amostra; templates
não-sobrepostos → 148 varreduras de 524k bits por amostra. Em Python puro, a
suíte completa custa dezenas de segundos a minutos por amostra → **semanas de
CPU** no total, mesmo paralelizado. Isso não inviabiliza, mas exige decisão
antecipada: implementação vetorizada/numba (ou C), paralelização planejada, e
possivelmente parâmetros documentados de compromisso (ex.: testes caros sobre
prefixo de bits fixo). O benchmark em ~500 amostras precisa ser gate da fase 2,
não recomendação.

### 4.2 A matriz GPU não fecha sem um teto declarado

B, C e E × 5 folds × 2 braços × 3 seeds × busca de hiperparâmetros é
multiplicativo: só o produto folds×braços×seeds já são 30 treinos por
arquitetura, antes de qualquer busca. O plano precisa de uma **matriz de
execução explícita** — proposta concreta: HP search e variantes de
condicionamento da CNN2D só no smoke/braço controlado com 1 seed; a
configuração vencedora roda os 5 folds × 3 seeds; braço cru só na ablação de
truncamento, com configuração congelada e 1 seed. Sem um teto de horas A100
declarado, "3 seeds + HP search + 2 braços" é uma promessa, não um plano.

### 4.3 Falta uma fase 0 de housekeeping

O v2 vai ser construído sobre um repositório que hoje: (a) tem a mudança do
seletor **não commitada** (7 arquivos, `git status` atual), (b) não contém os
artefatos brutos dos Caminhos B/C do v1 (números da dissertação não auditáveis
pelo repo), (c) tem o Caminho D só em `Downloads/`. Antes da fase 1: commitar o
seletor, sincronizar os artefatos localizados, registrar a busca pelos de B/C.
Custa uma sessão e evita que o v2 herde a mesma fragilidade de auditoria que a
`analise_completa` já apontou no v1.

### 4.4 Rodadas reduzidas: prometer a curva antes de saber se ela existe

A variante de rodadas reduzidas é a melhor resposta à Review 4, mas tem uma
incerteza não registrada: não é garantido que Ascon com rodadas reduzidas
produza viés estatístico **detectável em ciphertext-only** em qualquer contagem
de rodadas acima de ~2 — os distinguishers conhecidos de rodada reduzida são
ataques com controle de nonce/dados escolhidos, não desvios marginais do CT. O
risco é a "curva de sensibilidade" sair binária (detecta em 1–2 rodadas, nada
acima), o que esvazia o argumento. Antes de prometer a curva no texto: piloto
barato (χ²/compressão/permutação em ~1k amostras por contagem de rodadas) para
calibrar quais pontos da curva existem. Nota adicional: KATs oficiais não
cobrem variantes de rodada reduzida — a validação vira roundtrip
encrypt/decrypt + diff da configuração, e isso deve ser dito no manifesto.

---

## 5. Pontos menores (baratos de corrigir, caros de ignorar)

1. **NaN→0 em p-values** (excursões aleatórias): 0 é o valor mais extremo de
   um p-value — imputar "teste não aplicável" como "falha máxima de
   aleatoriedade" é semanticamente errado. Usar indicador de missing + imputar
   neutro (0,5), ou só o indicador.
2. **VT sobre z-score** remove apenas features exatamente constantes (variância
   padronizada é 1 por construção) — o estágio vira um "drop constantes".
   Correto e desejado, mas dizer isso na metodologia evita a pergunta "por que
   um threshold de variância depois de padronizar?". Cuidar da divisão por zero
   no z-score de features constantes no fold.
3. **Controle PRNG** precisa de `key_id` sintético (300 grupos) para passar
   pelo GroupKFold — e decidir se entra como classe extra ou só em binários
   contra cada algoritmo (o plano diz as duas coisas em lugares diferentes;
   binários é o desenho limpo, classe extra muda todos os baselines).
4. **`ECE`**: especificar binning e variante (top-label) antes de comparar
   entre modelos.
5. O argumento de venda do conjunto de algoritmos pode ser mais forte do que o
   texto atual: pela mecânica da própria RSL (estrutura separa, identidade
   não), 4 famílias construtivas diferentes é o **caso mais favorável ao
   sinal**. Um nulo aqui não é "mais um nulo" — é o teste da hipótese de
   vazamento estrutural no cenário em que ela tinha mais chance. O flip side,
   que vale registrar como limitação consciente: sem par mesma-família
   (Romulus descartado), o gradiente de granularidade — o achado mais robusto
   da RSL — não é mensurável no desenho.

---

## 6. Perguntas de volta (decisões que são suas, não minhas)

1. **Endpoint primário:** fecha o quarteto {F1-macro 4-classes, Caminho A,
   braço controlado, TOST com δ=1 p.p. + permutação} antes de gerar dados? Se
   discorda do braço controlado como primário, qual é a defesa contra o
   artefato do Grain inflando o agregado?
2. **Teto de GPU:** quantas horas A100 o Colab+ realmente comporta para E? A
   matriz de execução do §4.2 acima só pode ser fechada com esse número na mão.
3. **Caminho E:** aceita reposicioná-lo como contribuição própria e adicionar a
   réplica fiel do E20 (Transformer sobre features NIST — barata) ao Caminho A?
4. **Rodadas reduzidas:** o piloto de calibração entra antes do compromisso com
   a "curva" no texto?
5. Dos 20 itens 🔶, quais você promove a obrigatórios? Minha lista mínima está
   no §3; se a sua for diferente, é a conversa mais importante a ter com o
   orientador antes da fase 1.
