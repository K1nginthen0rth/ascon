# 5. Execução, riscos e pendências

## 5.1 Fases de execução — estado real (2026-08-22)

**Todo o código dos 6 caminhos está implementado.** O que resta é
executar. Sequência exata de comandos: `07_runbook_execucao.md`.

| Fase | Conteúdo | Hardware | Estado |
|---|---|---|---|
| 0-1 | Ascon corrigido + Grain/Sparkle + CTR_DRBG (KAT/CAVP) | CPU | ✅ concluída |
| 2 | Features novas (NIST SP 800-22 + literatura) + benchmark | CPU | ✅ concluída |
| 3 | Seletor v2 (z-score → VT → MI → mRMR → Boruta diag.) | CPU | ✅ concluída |
| 4 | Dataset v2 (180k, 11,8GB) + validação | CPU | ✅ concluída — **PASS** |
| 5 | Relato único (`report_eval`) + poder a priori | CPU | ✅ concluída |
| — | **Extração das features das 180k amostras** | CPU | ⏳ código pronto, **~20h por braço** |
| 6 | Caminho A (clássicos + réplicas + ablações) | CPU | ⏳ código pronto e validado |
| 7 | Caminhos B e C (CNN1D/CNN2D) | GPU | ⏳ código pronto |
| 8 | Caminho E (Transformer hierárquico) | GPU | ⏳ código pronto |
| 9 | Caminho D (híbrido, 4 representações) | CPU/GPU | ⏳ código pronto |
| 10 | Caminho F (meta out-of-fold) | CPU | ⏳ código pronto e validado |
| 11 | Consolidação (BH-FDR) | CPU | ⏳ código pronto e validado |

O Caminho A primeiro **não é gate de desistência** (nulo é esperado e não
interrompe nada) — é validação barata de wrappers/dataset/pipeline antes de
comprometer GPU.

## 5.2 Orçamento computacional — números medidos

- **Geração do dataset:** 2.461,6s (~41 min) para 180.000 amostras,
  11,80 GB. Memória estável em ~1,2 GB (escrita incremental).
- **Extração de features: ~2,2 s/amostra medidos em dados reais** (2,21 s
  em CTs do v2 no laço real; 1,69 s numa medição isolada de amostra
  quente — a diferença é o custo de leitura/streaming, então use 2,2 s
  para planejar). 180k amostras = **~110h de CPU serial por braço**, ou
  **~18-20h com 6 shards** paralelos. Bem abaixo do teto de 48h.
  - Custo residual concentrado em: `complexity`/LZ76 (0,56 s — maior
    item isolado, O(n²), numba testado e REJEITADO por ser mais lento
    que o `memmem` em C) e `nist_sts` (0,80 s, já otimizado 5,2x).
  - Histórico: a estimativa inicial era 249,5h serial; caiu para ~110h
    após otimizar os dois gargalos reais medidos (ver 5.6).
- **SVM (dado real do v1):** busca em grade nos 5 folds = 8.365s (~139 min) a
  38.400 amostras/fold. Com a correção por subamostra + CV interna
  group-aware (implementada), estimado em dezenas de minutos.
- **GPU:** números reais de B/C/E/D **ainda não existem** — o modo
  `--mode smoke` de `run_v2_caminhos_bce.py` mede tempo/época, VRAM e
  parâmetros e **extrapola o custo da CV completa**. É gate: rodar antes
  de comprometer qualquer sessão longa.
- **Armazenamento real:** 11,8 GB (parquet de CTs) + 380 MB (imagens) +
  ~460 MB por braço de features (180k × 650 float32) + latentes.

## 5.3 Riscos e planos B

| Risco | Estado |
|---|---|
| ✅ Grain/Sparkle não compilarem no MSVC | **Não se concretizou:** ambos ANSI C/C99 portável, compilaram de primeira sem patch. |
| ✅ Variante/parâmetros exatos do Schwaemm | **Confirmado:** Schwaemm256-128 (128/256/128), fixado em `schwaemm_cfg.h`. |
| ✅ Berlekamp-Massey (e demais NIST) com bug plausível-mas-errado | **MATERIALIZOU-SE — na biblioteca, não no nosso código.** A validação obrigatória encontrou 3 bugs críticos no `nistrng` (ver 5.6). Sem ela, ~metade da suíte NIST teria rodado sobre dados corrompidos, silenciosamente. |
| ✅ Memória em datasets multi-GB | **MATERIALIZOU-SE 2x** (geração e validação; ver 5.6). Corrigido com leitura/escrita incremental via `pyarrow`. Risco permanece vivo para B/C/E — mitigado com `--max-train-samples`. |
| 🔶 Colapso de CNN mal diagnosticado no 4-classes | valores de referência pré-calculados (colapso 0,10 vs acaso 0,25) + diagnóstico de **posto efetivo do latente** (SVD, 95% da variância) implementado em `run_v2_caminhos_bce.py`. Só verificável na execução real. |
| 🔶 Caminho F "achar sinal" com individuais no acaso | Implementado: o script **imprime automaticamente a bandeira de investigação de vazamento** quando o caso ocorre. Tratado como bandeira, não descoberta. |
| ✅ Perda de resultados por queda de sessão | `report_eval` com JSONL append-only + parquet por chamada; extração retomável por chunk com gravação atômica. Reforçado depois que uma exceção de AUC quase derrubou um fold inteiro (ver 5.6). |
| 🔶 Orçamento de GPU insuficiente para B/C/E | Sem número real até o smoke test. Estratégia Kaggle-first já definida; ordem de corte segue **pendente de decisão** (§P5 do 06). |

## 5.4 Placar de decisões (rodada final 2026-08-21 — detalhes no 06)

**✅ Aprovados:** controles negativos (PRNG binário contra cada algoritmo +
embaralhamento de bytes) · família primária = 6 pares par-a-par no Caminho A
com **F1 como métrica oficial** · FDR (BH) no exploratório · replicação com
chaves novas para positivos · poder a priori · análise par a par · curvas de
aprendizado · calibração antes do F · HP search reduzida nos profundos
(8–12 configs, 1 fold) · 3 seeds no modelo final de B/C/E · validação de
TODAS as implementações NIST contra vetores · benchmark de extração (gate) ·
sanity `len_ct` · posto dos latentes · contagem de parâmetros ·
estratificação de erro · overlap de plaintext · condicionamento CNN2D ·
escopo do CTR_DRBG (só geração) · ordem de execução (5.1) · **propor**
Zenodo ao orientador.

**❌ Rejeitados:** pré-registro formal · variante Ascon de rodadas reduzidas ·
dataset secundário de 1KB (adiado pós-v2).

**✅ Resolvidos em seguida (2026-08-21):** braço primário = **controlado**
(cru roda completo como análise reportável do artefato de comprimento do
Grain) · teto de GPU conhecido (Colab Pro, 100 unidades/mês; estratégia
Kaggle-first no 06 §P5).

**[PENDENTE] — ver §P do 06:** TOST · bootstrap por cluster de chave ·
baseline de features aleatórias · ordem de corte de GPU (proposta no §P5,
não confirmada) · Zenodo (após conversa com orientador).

**Pendências de redação (deferidas por decisão do Nycolas para depois do
experimento; pontos da reunião de 27/07):**

- Reformular objetivo/caracterização do problema (retirar a formulação genérica
  "A={A1..Ak}"; instanciar nos algoritmos reais) — `introducao.tex:53-57,105-107`
- Corrigir/uniformizar definição de IND-CPA na introdução (a de
  `fundamentacao.tex:69` está correta; a da introdução, vaga)
- Adicionar parágrafo explícito sobre overfitting e como o protocolo o mitiga
  (palavra hoje ausente de todos os .tex)
- RSL entra como capítulo/base da lacuna
- Itens de higiene apontados pelo SBSeg (siglas, hifenização, itálicos,
  consistência PT/EN, nomes de autores)

## 5.5 Correções aplicadas (revisão crítica, 2026-08-21)

Cinco erros/lacunas encontrados numa leitura crítica do plano fechado,
corrigidos diretamente nos arquivos 01–04 desta pasta (e no relatório ao
orientador, que repetia o primeiro):

1. **Caminho E rotulado como "réplica do E20"** — não é (E20 usa Transformer
   sobre 8 features filtradas, com hierarquia de rótulos; Caminho E usa
   atenção sobre bytes crus, com hierarquia de atenção). Corrigido: E vira
   contribuição própria; réplica fiel do E20 adicionada ao Caminho A.
   (`03_classificadores.md` §3.1, §3.5)
2. **Features de tag com `ABYTES` real (16 vs. 8 no Grain) vazam `len_ct`** —
   entropia/nunique/χ² em janelas tão pequenas (n≪256) são dominadas pelo
   viés de amostra pequena do estimador, não pelo conteúdo; separam o Grain
   por tamanho de janela. Corrigido: janela comum de 8 bytes na comparação
   principal; tag completa por algoritmo vira exploratório à parte. Colide
   com o truncamento do braço `controlado` (cortar os últimos bytes do CT
   corta a tag) — corrigido junto: features de tag sempre sobre o CT cru.
   (`02_features_e_selecao.md`, `01_algoritmos_e_dataset.md` §1.6)
3. **Três lacunas de especificação:** reshape da réplica E05 não fecha
   aritmeticamente com o CT completo (corrigido: reshape só do payload,
   65.536 bytes); nonce do Sparkle (256 bits) sem mapeamento a partir do
   contador de 128 bits (corrigido: zero-pad nos bits mais significativos,
   documentado no manifesto); réplica XGB-LGBM sem a representação
   (peso de Hamming) que define o estudo original (corrigido: peso de
   Hamming promovido de "descartado" a obrigatório). (`03_classificadores.md`
   §3.1/§3.3, `01_algoritmos_e_dataset.md` §1.4, `02_features_e_selecao.md`)
4. **Ablação key-holdout on/off prometia demonstrar inflação onde não há o
   que memorizar** — nos 4 AEADs íntegros, IND-CPA com nonce único implica
   ausência de correlação explorável entre amostras da mesma chave; o efeito
   só é garantido no AES-ECB (codebook determinístico). Corrigido: ablação
   roda nos dois braços, com o ECB funcionando como controle positivo do
   próprio método de ablação. (`04_protocolo_metricas_validacao.md` §4.2)
5. **Caminho F sem disciplina out-of-fold fabricaria sinal por vazamento de
   stacking.** Corrigido: probabilidades de entrada do F devem ser
   out-of-fold, com partição de folds compartilhada entre A–E (verificada por
   assert) e persistência de predição/probabilidade por amostra na função de
   relato (novo item 5 da regra obrigatória) — sem isso a matriz OOF não é
   reconstruível depois do fato. Calibração (Platt/isotônica para
   LinearSVC/SVM) passa de recomendação a dependência dura desses ramos.
   (`03_classificadores.md` §3.6, `04_protocolo_metricas_validacao.md` §4.4)

Não corrigidos aqui, por serem decisões de escopo/estratégia e não erros
técnicos — permanecem como perguntas em aberto para Nycolas/orientador: a
promoção de itens 🔶 para ✅ (hipótese primária + TOST, pré-registro, poder a
priori, controles negativos), o teto de horas de GPU, e o corte de escopo se
o orçamento apertar. Ver `docs/analise_critica_plano_v2.md` §3–§6.

## 5.6 Achados da implementação (2026-08-21/22)

Problemas que **só apareceram ao escrever e rodar o código** — nenhum
deles era previsível na fase de planejamento. Registrados aqui porque
vários têm consequência metodológica direta e precisam constar na
dissertação como parte da validação do instrumento.

### Bugs em biblioteca de terceiros (`nistrng`) — 3 críticos de 7

A suíte NIST SP 800-22 foi construída sobre o pacote `nistrng` (BSD-3)
em vez de reimplementada do zero. A auditoria linha a linha exigida pelo
plano encontrou **sete desvios, três deles produzindo resultado
sistematicamente errado** (não apenas ausência de sinal):

1. **Binary Matrix Rank corrompia o array de bits compartilhado** —
   fazia eliminação gaussiana sobre uma *view* do array de entrada,
   mutando-o in-place e corrompendo os 7 testes seguintes na ordem de
   execução. Confirmado com 4 sequências aleatórias independentes: os
   mesmos 7 testes davam p=0,0 exato toda vez (assinatura de corrupção,
   não de variância). **Sem essa correção, ~metade da suíte NIST teria
   rodado sobre lixo, silenciosamente, no experimento inteiro.**
2. **Berlekamp-Massey com aliasing** — `t = c[:]` seguido de `b = t`: em
   NumPy isso é *view*, não cópia (ao contrário de lista Python).
   Resultado errado em ~65% das sequências testadas.
3. **Linear Complexity com bucketing errado** — classificava ~60% dos
   "tickets" na classe errada, inflando χ² e colapsando o p-value para
   0,0 em *qualquer* ciphertext.

Os outros quatro: template matching não-determinístico (sorteava 1
template sem seed), `erfc` faltando no Random Excursion Variant,
overflow de `int8` no Cumulative Sums, e dois testes com loops
Python inviáveis em escala.

**Consequência metodológica:** a exigência de validar cada implementação
NIST antes de usá-la (§5.3) não foi burocracia — foi o que separou um
experimento válido de um com metade das features corrompidas.

### Vazamentos e desvios de protocolo no nosso código

4. **Rótulo `y` entrando como feature** (Caminho A) — o seletor
   reportava 642 features em vez de 641 e todo modelo dava F1=1,000
   trivialmente. Pego por conferir a contagem na validação. Blindado com
   asserts que quebram se rótulo, metadado ou `len_ct` escaparem.
5. **Busca de HP do SVM não era group-aware** — usava
   `StratifiedKFold`, mas o plano exige CV interna por chave. Não
   contaminaria a métrica reportada, mas escolheria C/gamma calibrados
   para um cenário que não existe no teste. Trocado por `GroupKFold`.

### Limites físicos que forçaram redesenho

6. **Memória — dois quase-acidentes reais** (máquina de 16GB): o gerador
   mantinha as 180k linhas em RAM antes de gravar; o validador carregava
   o parquet de 11,8GB inteiro e derrubou a memória livre para **0,13
   GB**, exigindo `kill -9`. Ambos reescritos com `pyarrow` incremental.
7. **Atenção byte-a-byte é inviável** — o Caminho E, como descrito no
   plano ("janelas de ~1024 bytes"), alocava **2,1 GB só na matriz de
   atenção** com batch 2 em CPU, e passaria de 8 GB em GPU. Redesenhado
   com *patch embedding* (16 bytes/token, padrão ViT): reduz a atenção
   por um fator de 256 e mantém intacta a hierarquia local/global, que é
   a contribuição de fato. **Precisa constar na descrição da arquitetura
   na dissertação** — é desvio do texto do plano, ainda que não do seu
   espírito.
8. **`joblib` inutilizável neste ambiente** — `TerminatedWorkerError`
   reprodutível (Windows + spawn + numba JIT por worker), mesmo com
   lotes pequenos e memória de sobra, enquanto a mesma função rodava sem
   problema em processo único. Paralelismo movido para *sharding de
   processos independentes*, sem IPC.

### Otimização guiada por medição, não por suposição

9. O plano apontava o **LZ76** como o gargalo da extração. O
   perfilamento mostrou que os custos reais eram **template matching**
   (2,13 s) e **binary matrix rank** (0,77 s) — otimizados para 0,067 s
   e 0,004 s. O LZ76 (0,56 s) resistiu: a reimplementação em numba foi
   validada equivalente mas é **mais lenta** que o `memmem` em C do
   operador `in` do Python. Extração total: **5,9 s → 1,69 s por
   amostra**.

## 5.7 Auditoria de aderência externa (2026-08-22) — todos os itens fechados

Uma segunda leitura, linha a linha, do plano inteiro contra o código dos
6 caminhos (feita de forma independente e verificada por conferência
direta antes de aceitar qualquer achado, não por confiança no relatório)
encontrou 4 bugs metodológicos reais e 10 itens do escopo da Fase 6/7/11
que a §5.1 desta mesma seção afirmava incorretamente estarem
implementados. Todos corrigidos/implementados nesta rodada:

**Bugs corrigidos (mudam número, não só forma):**
1. Caminho D misturava latentes de redes B/C/E de FOLDS diferentes —
   espaços vetoriais não comparáveis entre si. Corrigido: treino e
   validação de cada fold usam sempre a rede DAQUELE fold.
2. Modelo final de B/C/E fazia early stopping olhando o próprio teste
   (`train_cnn(model, tr_ds, te_ds, ...)`). Corrigido com
   `train_cnn_fixed` (épocas fixas, vindas da média do `best_epoch` da
   CV).
3. Caminho F nunca chegava ao teste canônico — avaliava num split
   80/20 artificial dentro do trainval. Corrigido: meta-modelo fitado
   em 100% do OOF, avaliado uma vez no teste canônico via as predições
   `final` de A-E.
4. Modelo final do Caminho A ignorava `--selector-preset`.

**Escopo implementado** (estava ausente, não por decisão registrada —
resposta honesta à pergunta "foi corte ou esquecimento": foi
esquecimento): Stacking próprio · réplicas HKNNRF/XGB-LGBM(Hamming)/
Transformer-E20 · ablação de famílias · teste de permutação (20×,
by_key/within_key) · 3 variantes de condicionamento da CNN2D · réplica
E05 · estratificação de erro · McNemar pareado + Bonferroni.

**Achado colateral:** um crash reprodutível de `DataLoader` no Windows
(`num_workers=4` + `persistent_workers=True` com múltiplos loaders em
sequência no mesmo processo) só apareceu ao validar esses itens de
ponta a ponta pela primeira vez — corrigido com `num_workers=0` no
Windows (Kaggle/Colab, onde os treinos de produção rodam, mantêm 4).

Todos os itens validados com fixtures usando `sample_id` reais do
dataset (não só sintéticos) onde a correção dependia de dado real —
notavelmente a estratificação de erro, que detectou corretamente um
viés de `plaintext_source` injetado deliberadamente num modelo de teste
e não disparou falso-positivo no modelo sem esse viés. 232/232 testes
do projeto passando. Detalhe completo nos commits `153a337` a `a808549`.
