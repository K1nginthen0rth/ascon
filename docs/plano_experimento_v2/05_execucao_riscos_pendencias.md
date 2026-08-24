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
    após otimizar os dois gargalos reais medidos.
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
| ✅ Berlekamp-Massey (e demais NIST) com bug plausível-mas-errado | **MATERIALIZOU-SE — na biblioteca, não no nosso código.** A suíte NIST é construída sobre o pacote `nistrng`, cujos desvios em relação à norma estão documentados e corrigidos em `src/features/families/nist_sts.py`. |
| ✅ Memória em datasets multi-GB | **MATERIALIZOU-SE** na geração e na validação. Corrigido com leitura/escrita incremental via `pyarrow`. Risco permanece vivo para B/C/E — mitigado com `--max-train-samples`. |
| 🔶 Colapso de CNN mal diagnosticado no 4-classes | valores de referência pré-calculados (colapso 0,10 vs acaso 0,25) + diagnóstico de **posto efetivo do latente** (SVD, 95% da variância) implementado em `run_v2_caminhos_bce.py`. Só verificável na execução real. |
| 🔶 Caminho F "achar sinal" com individuais no acaso | Implementado: o script **imprime automaticamente a bandeira de investigação de vazamento** quando o caso ocorre. Tratado como bandeira, não descoberta. |
| ✅ Perda de resultados por queda de sessão | `report_eval` com JSONL append-only + parquet por chamada; extração retomável por chunk com gravação atômica. |
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


## 5.10 Quarta auditoria (2026-08-23) — 2 bloqueadores e 2 erros de fórmula NIST

**B1 — Caminho F abortava na sequência exata do runbook.** `_collect()`
filtrava por `run_id` e por fold, nunca por **braço**. A ablação
`--no-keyholdout` grava no mesmo diretório com o mesmo `run_id`, mudando
só o `braco`; como o split dela é aleatório POR AMOSTRA, seus folds de CV
contêm chaves do teste canônico, e o assert de vazamento derrubava o
script. O runbook manda rodar `--no-keyholdout` na Etapa 4 e o Caminho F
na Etapa 7 — era a sequência documentada que quebrava. Mesmo padrão do
bloqueador da 2ª auditoria (filtro assimétrico), agora vindo do braço em
vez da seed.

**B2 — `len_ct` entrava como feature nos braços `cru` e `shuffled`.**
Medido com bytes uniformes que diferem só no comprimento (65.552 vs
65.544), seis features separam com **AUC 1,0000**:
`compression_ratio_zlib`, `compression_ratio_lzma`, `ngram_4_nunique`,
`ngram_4_entropy`, `ngram_4_collision_rate`, `ngram_3_max_freq`. Em CTs
reais, `compression_ratio_zlib` vale 1,00039668 no Grain e 1,00039663 nos
outros três — determinístico, sem sobreposição.

Três consequências: (a) **o controle negativo `shuffled` estava
invalidado** — permutar não apaga comprimento, então toda comparação com
Grain daria F1≈1,0 e a leitura viraria "o sinal é de histograma" quando é
de comprimento, a conclusão oposta da verdadeira; (b) o assert da Regra de
Ouro 5 dava falsa garantia — bloqueia a coluna chamada `len_ct` enquanto
seis features que são função exata dela passam; (c) a rodada
`sanity_lenct` ficava vazia de conteúdo. **O braço `controlado` não é
afetado** (verificado em CT real: todos convergem para o mesmo valor), então
a hipótese primária estava protegida. Corrigido: `shuffled` passa a truncar
antes de embaralhar. O `cru` mantém o vazamento de propósito — é o braço
que existe para medir o artefato — mas 04 §4.2 agora lista as features
certas (a lista anterior, `lz_complexity`/`runs_count`/autocorrelação,
estava errada e omitia justamente as que separam).

**C1 — Random Excursion (não-variante) devolvia p-value ≡ 0.** Os 7
desvios do `nistrng` corrigidos antes cobriam a *Variant*; o não-variante
seguia vindo cru do pacote. A contagem de buckets é
`if 5 > k == occurrences: ... elif occurrences >= 5: count += 1` — o
`elif` dispara para todo k de 0 a 5, então **todo ciclo com ≥5 visitas é
contado nos seis buckets**. Numa sequência uniforme com J=1932, o pacote
devolve `[0,0,0,0,0,0,0,0]` e a especificação devolve 0,017 a 0,913. As
duas features do teste eram função determinística da flag `valid` — 3
features carregando 1 bit, e esse bit é "J≥500", não o resultado do teste.
Na dissertação viraria "o Random Excursion rejeita aleatoriedade em TODO
criptograma". Reimplementado.

**C2 — Maurer's Universal com denominador ~518× fora da especificação.**
A §2.9.4 passo 5 manda `σ = c·sqrt(variance(L)/K)` com
`c = 0,7 − 0,8/L + (4+32/L)·K^(−3/L)/15`; o `nistrng` usa
`σ = sqrt(variance(L))` — sem o `c` e sem o `/√K`. Medido: denominador
2,500 contra 0,00483 (razão 517,9×, c=0,5688, K=86.762), p-value 0,99951
contra 0,75268. Como no erro de √2 da 3ª auditoria, RF/XGBoost são
invariantes (transformação monótona) mas LinearSVC/SVM/LR sofrem, e a
afirmação quebra. Reimplementado. **Detalhe que quase passou:** a §2.9.5
fixa L por faixa de n — para os 524.416 bits do nosso CT é **L=6**, não 7
(a faixa de L=7 começa em 904.960).

C1 e C2 pesam mais que "3 de 641": a réplica E20 roda sobre as 25 NIST + 4
de entropia, então são **3 de 29** na entrada dela.

**Metodológicos:** BH-FDR incluía os folds de CV (a mesma hipótese entrava
6× no denominador, com dependência forte, e uma linha de validação recebia
`significativo_fdr`) — família exploratória restrita a `fold == "final"`,
folds seguem no CSV como diagnóstico. `selector.transform()` não imputava
NaN enquanto o `fit` imputava — latente hoje (0 NaN nas 641 em CT real),
mas qualquer família que volte a devolver NaN derrubaria metade do
Caminho A no meio de uma rodada de horas.

**Aberto, não corrigido:** a calibração isotônica do Caminho F é
in-sample (fitada na matriz OOF e aplicada a ela mesma). A direção é
conservadora — o teste usa calibradores fora de amostra — mas o LR treina
em features informadas pelos próprios rótulos. Cross-fitting por chave
resolve; fica registrado como pendência.

253/253 testes.

## 5.11 Quinta auditoria (2026-08-24) — proveniência falsa e ressalvas de escopo

Auditoria independente que reexecutou tudo que era verificável e construiu
âncoras externas onde a validação era circular. **A maior parte do relatório
é confirmação** — camada cripto, dataset, folds, Regras de Ouro 1/5/7,
os 7 desvios do `nistrng`, e o braço `controlado` limpo de vazamento por
comprimento, tudo verificado de forma independente. Os achados:

**A1 [CRÍTICO, documentação] — a proveniência do KAT do GIFT-COFB estava
declarada de forma FALSA, e a afirmação era minha.** `data/kat/README.md`
atribuía o arquivo ao "pacote de submissão NIST LWC". Não é: ele é
produzido por `scripts/generate_gift_cofb_kat.py`, que importa a própria
`_gift_cofb_ref` e chama `crypto_aead_encrypt` para gerar os 1089 vetores
— **o KAT valida a implementação contra ela mesma**. O repo vendorizado
(`github.com/aadomn/gift`, de terceiro) não contém KAT algum. Ou seja,
"GIFT-COFB: 1089/1089" era tautologia: teria passado igual com a
implementação errada.

A auditoria construiu a âncora que faltava: implementou GIFT-128 do zero a
partir da especificação (S-box, P128, LFSR das constantes, key schedule),
conferiu contra os 3 vetores de `test_vectors.c`, estabeleceu a ponte
`giftb128`↔`gift128` e implementou COFB com os macros upstream — **13/13
batem com o wrapper**, incluindo `Count=1`. A implementação está correta;
o que não se sustentava era a frase. Corrigido em `data/kat/README.md`,
`CLAUDE.md` e no banner do próprio gerador.

> **Substituído por algo mais forte em §5.13**: aquela verificação foi
> feita numa sessão e não ficou versionada, e o COFB dela reusava os macros
> do `cofb.h` upstream. A sétima auditoria escreveu o modo COFB inteiro da
> especificação e o resultado virou `tests/test_crypto_independente.py`:
> **1089 + 60 casos**, rodando no CI de testes.

**A2 — Random Excursion e Variant valem em ~46-48% das amostras.** Medido
em ciphertexts reais: J tem mediana ~450-490 contra o teórico 578, e o
corte J≥500 cai praticamente sobre a mediana. Equilibrado entre os 6
algoritmos (40-50%), então não é vazamento — mas 2 dos 15 testes NIST são
avaliados em pouco menos da metade do dataset, e 4 features ficam
constantes em 0,5 no restante. "Rodamos a suíte NIST completa" precisa
dessa ressalva.

**A3 — o v1 não é reproduzível bit a bit a partir do HEAD.** Os parquets
do v1 têm 307 features; o código de hoje produz 308 para a mesma lista de
famílias — `compression_ratio_lzma` entrou em `9012c55` (Fase 2 do v2),
depois do v1 rodar. Nada registrava a divergência. Registrado em
`CLAUDE.md`; não afeta o v2.

**A4 — a docstring do `consolidate_v2.py` descrevia um teste diferente do
implementado.** Dizia "fração de reamostragens em que F1 ≤ acaso, ×2"
(p-value percentílico); o código faz aproximação normal a partir da
semilargura do IC. O comentário inline estava honesto; a docstring — que é
o que vira seção de métodos — não. Alinhado, com a limitação declarada e a
migração para o percentílico registrada como melhoria (exige guardar as
reamostragens, hoje só os percentis são persistidos).

**A6 — duas features são constantes por construção.** Overlapping Template
é estruturalmente inelegível em 64KB. **O número informativo é 639, não
641** — o VT as descarta, então o efeito prático é nulo, mas é 639 que vai
para o texto.

**A7 — os números do Maurer na docstring estavam no L errado.** Citavam
c=0,5904 / K=73.636 / "~460x", que são os valores de L=7. Para o n real a
§2.9.5 manda L=6 (c=0,5688, K=86.762, fator 517,9x). O **código** sempre
escolheu L=6 corretamente; era só a documentação.

**A8 — ApEn roda sempre com m=2, e não por escolha do n.** A expressão do
`nistrng`, `min(2, max(3, floor(log2 n) − 6))`, é malformada: `max(3,·)`
nunca é < 3, então o `min(2,·)` devolve 2 para qualquer entrada. A norma
permitiria m até ~13 para n≈524k. **Decisão: manter m=2** (é o que já foi
validado bit-a-bit e mudar tornaria a feature incomparável), mas agora
como constante literal `_APEN_BLOCK_LEN` com a escolha registrada, em vez
de uma aritmética enganosa que ninguém tinha lido.

**A9** — o índice do plano ainda dizia 150k amostras e ~400+ features
enquanto a seção logo abaixo, no mesmo arquivo, já dizia 180k. Corrigido
para 180k / 641 (639 informativas).

**A10** — `_random_excursion_variant_fixed` iterava sobre `np.unique`, o
que **omitia** um estado nunca visitado em vez de deixá-lo contribuir com
ξ=0; os 18 estados são fixos pela especificação. Corrigido. Banner de
obsolescência adicionado ao próprio `benchmark_extracao.md`.

**A5 — elevado de bullet a pendência com peso próprio.** O IC bootstrap
reamostra índices i.i.d. num desenho agrupado por chave (100 amostras por
chave). Sob sinal correlacionado à chave o IC sai **estreito demais**, e o
veredicto primário do projeto inteiro é "o IC 95% exclui o acaso" — é a
única pendência aberta que afeta diretamente a conclusão principal, e
estava listada como um item entre cinco em §5.4. Bootstrap por cluster de
chave resolve. **Continua pendente de decisão** (§P do 06).

### O que a auditoria NÃO conseguiu fechar (registrado como limitação)

- **Grain-128AEAD e Schwaemm256-128:** os KAT vêm de arquivos de terceiros
  já versionados; não houve reimplementação independente como a feita para
  o GIFT-COFB. A proveniência declarada é plausível e os formatos batem,
  mas não é âncora externa no mesmo nível.
- **Ascon:** o KAT é byte-idêntico ao do repo oficial (SHA-256
  `068f4e25…`), o que É âncora genuína — mas num clone limpo ela depende
  do arquivo em `data/kat/`, cuja integridade só o SHA-256 do README
  garante.
- Nenhum Caminho foi executado sobre features reais (a extração não
  rodou), então a validação dos caminhos é de **encanamento**, não de
  resultado.

253/253 testes.

## 5.12 Sexta auditoria (2026-08-24) — IA/Ciência de Dados

Auditoria feita direto no código, sem se apoiar em relatórios anteriores.
Confirmou de forma independente: 253 testes, 641 features sem NaN/Inf,
dataset 180k com encadeamento e nonces íntegros, decrypt 30/30, KAT
1089/1089 nos 4, CAVP 240/240, folds disjuntos, e os 6 caminhos
implementados. Também confirmou que **nenhum resultado experimental do v2
existe no repositório** — a validação é de desenho e código.

### Corrigido

**B1 [BLOQUEADOR] — `train_cnn_fixed` quebrava em TODA retomada.**
Desempacotava 3 valores de `_load_ckpt`, que devolve 4 desde a correção do
`best_state`: `ValueError: too many values to unpack`. Reproduzi. É a
função do modelo final de B/C/E, que grava checkpoint por época e roda em
Kaggle/Colab — a primeira execução passava, qualquer retomada morria. O
teste existente cobria `train_cnn`, não esta; por isso passou pelas 253.

**M1 [o mais importante] — toda a inferência ignorava o agrupamento por
chave.** O bootstrap reamostrava amostras individuais num desenho com 100
slots por chave; `key_ids` chegava ao `report_eval` e era persistido, mas
nunca usado. Reproduzi o impacto: com efeito de chave (ICC~0,01) o IC por
cluster fica **2,25x mais largo** que o i.i.d. Sob H₀ pura os dois
coincidem — ou seja, **o método antigo só estava correto sob a hipótese
que um resultado positivo violaria**. Como o veredicto primário é "o IC
95% exclui o acaso", errava na direção do falso positivo. `compute_metrics`
ganhou `groups=`, e o `report_eval` passa `key_ids` automaticamente —
todo caminho herda a correção sem mudar runner nenhum. Sem `groups`, o
comportamento antigo é preservado.

**M2 — o detector de artefato era cego ao artefato mais provável.** O
runbook manda rodar `pairs`/`4class` no braço `cru`, e os 3 pares com
Grain sairão com F1≈1,0 e `significativo_fdr=True` por separação de
comprimento. A estratificação de erro não pega: um classificador que
separa por comprimento acerta 100% em toda chave e toda fonte de
plaintext, então dispersão e desvio são zero. Adicionada a coluna
`artefato_conhecido` (braço `cru` + comparação com Grain) e um aviso no
consolidado.

**M3 — o teste de permutação não cobria a seleção de features.** O
seletor era fitado uma vez com os rótulos VERDADEIROS e reusado nas 20
permutações, então o nulo media a variabilidade do classificador sobre um
conjunto de features já escolhido com informação do rótulo — não a da
pipeline (Ojala & Garriga 2010). Corrigido: seletor refitado dentro de
cada permutação. **N_PERM 20 → 200** (com 20 o menor p obtenível é
1/21≈0,048, perto demais de α=0,05 para um nulo que sustenta a conclusão
principal); o XGBoost saiu do laço para viabilizar o custo — a LR sozinha
caracteriza o nulo.

**M5 — os caminhos profundos rodavam sem controle positivo.** `--analysis`
adicionado a `run_v2_caminhos_bce.py` (`4class` / `ecb_control` /
`prng_control`). Sem isso, um F1≈0,25 em B/C/E não distinguia "não há
sinal" de "esta arquitetura, com este orçamento, não aprende nada".
Validado ponta a ponta.

**N1** — `_prepare` do seletor imputava só NaN enquanto o `transform` já
sanitizava NaN e ±inf; as duas metades agora concordam.

### Registrado como limitação (não corrigido)

**M4 — Caminho D treina em latentes in-sample.** O híbrido treina com
`fold{fi}_train` (latentes da rede que viu aquelas amostras) e valida com
`fold{fi}` (out-of-sample). A correção anterior resolveu um problema real
(espaços latentes incompatíveis entre folds) mas trocou por outro: as
colunas de treino são sistematicamente mais separáveis, o RF confia demais
nelas e a métrica de validação fica **pessimista**. Sob H₀ enviesa na
direção segura (erro tipo II), mas compromete a afirmação "o híbrido não
agrega sinal" — pode ser desalinhamento de representação. O correto seria
latentes OOF por split interno ao fold. **Precisa constar como limitação
no texto.**

**M6 — o ECE de LinearSVC/SVM-RBF não é medida de calibração.**
`get_proba` converte `decision_function` por softmax: preserva ranking
(AUC vale) mas a saída não é probabilidade, então o ECE mede a distância
entre acurácia e uma margem reescalada arbitrariamente. O Caminho F
recalibra explicitamente, então não se propaga — mas o ECE desses dois
modelos no `.jsonl` e no console é ruído com aparência de métrica. Não
citar.

**§5 do relatório — o SVM-RBF é muito mais caro que o orçado.** O plano
contabiliza a busca de hiperparâmetros (corrigida por subamostra) mas
**não o fit final no fold completo**. Escalabilidade medida (150
features): 2k→0,3s, 4k→1,3s, 8k→8,1s, 16k→58,5s, expoente empírico
n^2,85. Extrapolando: ~1,4h por fold (76.800) e ~2,7h no modelo final
(96.000) — só o SVM do 4-classes ≈10h, com os 6 pares ≈18h. Pior: o
`StackingClassifier` inclui um SVC como base com `cv=3` → 4 fits de SVC
por chamada × 36 rodadas ≈ mais 12-15h. **O Caminho A completo deve ficar
entre 40 e 80h de CPU, não "na ordem de horas".** É decisão de
planejamento: reduzir a grade, subamostrar também o fit final, ou aceitar
o custo. **PENDENTE.**

### Menores registrados

**N2** — 3 features são estruturalmente constantes
(`nist_overlapping_template`, `_valid`, `nist_linear_complexity_valid`):
**638 efetivas**, não 641 (a auditoria anterior tinha contado 639;
`linear_complexity_valid` também é constante em 64KB).
**N3** — vazamento leve de comprimento sobrevive no braço primário via
`tag_region` (que por desenho usa o CT cru): d≈0,03σ em
`payload_rest_max_freq`, AUC≈0,508. Detectável por teste t com 30k
amostras, irrelevante para classificação — mas é assimetria sistemática de
comprimento no braço que existe para eliminá-la.
**N4** — o HP search de B/C/E usa o fold 0, que depois volta como fold de
CV; o fold 0 fica otimista (não contamina o teste).
**N5** — o split do smoke não respeita chave (é gate de tempo/VRAM, mas
grava métrica).
**N6** — no Caminho F o calibrador isotônico e o meta-modelo compartilham
as mesmas linhas; enviesa para pessimista.
**N7** — McNemar usa χ² com correção de continuidade mesmo com poucas
discordâncias; o recomendado é binomial exato para n<25.
**N8** — o parquet `..._features_sintetico.parquet` não tem script
versionado que o gere, e seus valores são N(0,1) puro (o real é ~0,0039 no
`byte_hist_000`): valida encanamento, não o comportamento numérico do
VT/mRMR nas escalas reais.

### Observações de desenho (entram nas limitações do texto)

- **O Caminho E é cego para a tag** (`max_len=65536` = só payload),
  enquanto o próprio projeto argumenta que a tag é o lugar mais provável
  de assinatura residual. O caminho de maior capacidade é o único sem
  acesso a ela.
- **A co-ocorrência 256×256 tem SNR estruturalmente ruim**: 65.543
  bigramas em 65.536 células ≈ 1 contagem/célula, ruído de Poisson puro.
  As 4 variantes de condicionamento corrigem escala, não SNR. Um nulo no
  Caminho C pode ser propriedade da representação.
- **`hamming` é derivável linearmente do histograma** — colinearidade
  perfeita com 256 features já presentes. É escolha de fidelidade à
  réplica E07; o texto não deve tratá-la como família independente.
- **Nonces de baixa entropia**: o contador global vai a 30.000, então todo
  nonce de 16 bytes tem 14 bytes zerados (30 de 32 no Schwaemm). Isso é
  FAVORÁVEL ao atacante — mais estrutura compartilhada. Um nulo sob essa
  condição é mais forte, não mais fraco; e não se transporta
  automaticamente para nonces aleatórios. Vale dizer as duas coisas.
- **2 plaintexts sobrepostos** entre trainval e teste (0,03%): o texto
  deve dar o número, não "sem sobreposição".

256/256 testes.


---

## 5.13 Sétima auditoria (2026-08-24) — criptográfica, por reimplementação

Auditoria feita **reimplementando do zero, da especificação**, os dois
algoritmos cuja cadeia de evidência não fechava por proveniência externa
(GIFT-COFB e Ascon-AEAD128), e usando essas implementações como oráculo
contra os binários. Depois validou o artefato real de 11,8 GB decifrando
amostras dele.

O veredicto separa duas coisas que vinham juntas: **a criptografia está
certa; a cadeia de evidência é que não estava.** Um dos quatro pilares era
circular e documentado como se não fosse, e a reprodutibilidade que o repo
declarava ter, ele não tinha.

### Confirmado independentemente (não é achado — é o que passou)

- **Ascon-AEAD128 é mesmo o SP 800-232.** `ascon-c/` está no commit
  `b7ca60b` ("Change Ascon version from v1.2 to v1.3"), que já adota as
  convenções do padrão final. As três diferenças contra o Ascon-128a v1.2
  foram conferidas uma a uma: IV `0x00001000808c0001` (era
  `0x80800c0800000000`), carga little-endian (era big-endian), padding
  `0x01` (era `0x80`) e separação de domínio no MSB (era LSB).
  Ancoragem cruzada que fixa a variante: o binário dá **0/1089** contra
  `ascon-c/LWC_AEAD_KAT_128_128.txt` (raiz), cujo SHA-256 é idêntico ao de
  `ascon128v13/` — Ascon-128, taxa 64. Confirmado aqui.
- **A porta MSVC do GIFT-COFB é fiel.** `cofb.h` e `giftb128.h` são macro a
  macro idênticos aos originais, só trocando `({...})` por `do{...}while(0)`;
  em `key_schedule.h`, `REARRANGE_RKEY_0..3` viraram `static __inline` com
  `tmp` local — semanticamente equivalente nos pontos de uso.
- **O dataset de 180k é criptograficamente sólido**: 153 amostras
  decifradas com SHA-256 do plaintext conferindo, nonces sem duplicata,
  encadeamento real, e os SHA-256 dos quatro `.pyd` batendo com o manifesto.
- **Os quatro AEAD rejeitam** payload, tag, AD, nonce e chave adulterados.
- **CTR_DRBG conferido linha a linha** contra o SP 800-90A §10.2.1, com
  `randint` por rejection sampling (sem viés de módulo) e os 240 vetores
  CAVP genuínos.

### Corrigido

**2.1 [ALTA] — o KAT do GIFT-COFB é autogerado; a tabela de proveniência
afirmava o contrário.** Já havia sido corrigido no texto do
`data/kat/README.md` (§5.11/A1), mas a correção deixava a lacuna aberta:
não existia âncora externa versionada. Agora existe.

`tests/test_crypto_independente.py` (≈450 linhas) reimplementa
**Ascon-AEAD128 do SP 800-232** e **GIFT-128/COFB da especificação** em
Python puro e roda os dois contra os binários. A cadeia do GIFT-COFB passou
a ser:

> 3 vetores **oficiais** do cifrador de bloco (embutidos como literais,
> porque `gift-cofb/` é gitignored) → validam o GIFT-128 independente →
> que sustenta o GIFTb-128 e o COFB escritos da especificação → que
> concordam com `_gift_cofb_ref.pyd` em **1089 + 60 casos aleatórios**.

Reproduzido aqui do zero, sem copiar o C: a fórmula `P128`, o LFSR de 6
bits das constantes, o key schedule `k1>>>2 ‖ k0>>>12 ‖ k7 ‖ …`, a dobra em
GF(2⁶⁴) com `0x1b`, `G(Y1‖Y2) = Y2‖(Y1<<<1)` e o expoente
`3^(1 + [A_a parcial] + 2·[M vazio])` antes do último bloco de AD. O único
elemento tomado da implementação — e não do papel — é a convenção de
ordenação de bits da interface do GIFTb-128 (representação bitsliced
`W_j[i] = b_{4i+j}` do paper Fixslicing): uma escolha entre duas
alternativas naturais, fixada empiricamente e documentada em `_rho_in`.

O arquivo é **autocontido de propósito** e roda em 1,06 s.

**2.2 [ALTA] — nenhuma extensão era reconstruível num clone limpo.** O
`.gitignore` afirmava que "o C amalgamado para rebuild fica em
`src/crypto/`". Era falso: os `_*_ref.c` de lá são só o glue do cffi, sem
nenhum símbolo dos algoritmos. Isso derrubava o objetivo declarado do
próprio `data/kat/README.md` — num clone limpo os testes falhavam no
import, não na comparação.

- `scripts/vendor_sources.py` (novo): fixa as quatro árvores por **commit**
  (as três com git) e por **SHA-256 de cada arquivo efetivamente
  compilado** (as quatro). `--check` (padrão) confere o que está em disco;
  `--fetch` clona/baixa nos pinos. Roda em 4/4 OK hoje.
- Comentário do `.gitignore` corrigido, apontando para o script.
- O modo de falha era feio de propósito nenhum: `spec.loader.exec_module()`
  ficava FORA do `try`, então o `FileNotFoundError` levantado no nível de
  módulo do script de build escapava cru em vez do `ImportError` com
  instruções. Corrigido nos quatro wrappers, com a dica do
  `vendor_sources.py --fetch` na mensagem.

**2.3 [MÉDIA] — GIFT-COFB não é "Round 2 finalist".** Foi finalista da
**Rodada 3** (um dos 10 anunciados em março de 2021); na Rodada 2 havia
candidatos, não finalistas. O rótulo estava em duas docstrings e — o que
pesa — em `metadata["standard"]`, de onde foi copiado literalmente para
`keyholdout_5class_v2_manifest.json`. Corrigido no código, no manifesto (só
o rótulo descritivo; hashes, seeds e parâmetros intactos) e em
`01_criptografia.md`. Grain e Schwaemm já estavam certos.

**2.5 [BAIXA] — as docstrings apontavam para o KAT da variante errada do
Ascon.** `validate_kat` e `parse_kat_file` davam como exemplo
`ascon-c/LWC_AEAD_KAT_128_128.txt`, que é o da taxa 64. Nada estava
quebrado (os testes usam o caminho certo), mas era armadilha ativa:
qualquer script novo que copiasse o exemplo "falharia a validação KAT" de
um algoritmo correto. Corrigido em `ascon_wrapper.py`, `kat_parser.py`,
`01_criptografia.md` e `CONTEXTO_ARTIGO.md`, com a explicação do porquê.

**2.6 [BAIXA] — a checagem de nonce validava o rótulo, não o nonce.**
`_check_nonce_uniqueness` contava duplicatas de `(key_id, nonce_id)`, e
`nonce_id` é a string do contador — única **por construção**. O que
interessa é se os BYTES colidem, especialmente no Grain, onde 16 bytes
viram 12 por truncamento. Reescrita: reconstrói o nonce derivado de cada
algoritmo e mede colisões globais e reuso dentro de uma mesma chave.
Testada com uma colisão de truncamento proposital (dois contadores que só
diferem acima do byte 12) — a versão antiga dava OK, a nova acusa.
No dataset real: 30.000/30.000 distintos nos três comprimentos
(npub 16, 12 e 32), zero reuso por chave.

**2.7 [BAIXA] — o controle "PRNG" é AES-CTR.** É saída de
`CTRDRBG.generate()`, ou seja, AES-128 em modo contador; e os 30.000
vetores saem de **uma** instanciação em fluxo contíguo (~2 GB), enquanto
cada cifra usa 300 chaves independentes. Como controle negativo é válido
(saída de AES-CTR é indistinguível de aleatório sob as hipóteses padrão, e
2 GB está muito abaixo dos limites do SP 800-90A), mas a dissertação não
pode chamá-lo de "PRNG" genérico. O rótulo no parquet **não** muda (é chave
de dados, de que tudo depende); o `consolidate_v2.py` passou a emitir uma
seção *"Como nomear as classes na dissertação"*, que é de onde o texto
copia.

**2.8 [BAIXA] — `_compute_binary_hash` dependia da ordem do filesystem.**
Os quatro wrappers faziam `list(glob(pat))[0]`: com dois builds para ABIs
diferentes convivendo, o hash gravado no manifesto passava a ser o que o
sistema listasse primeiro. Agora hasheia o `__file__` do módulo **de fato
importado**; o glob virou fallback ordenado que devolve `"ambiguo:..."` em
vez de escolher em silêncio. Verificado: os quatro hashes continuam
idênticos aos do manifesto do dataset.

### Registrado, não corrigido

**2.4 [MÉDIA] — `sparkle/` é a única árvore sem proveniência verificável.**
Não tem `.git`; a origem é uma afirmação em docstring (pacote de submissão
`sparkle.zip`) e o SHA-256 do zip **não foi registrado na época**. Os
parâmetros conferem (estado 384, taxa 256, capacidade 128, passos 7/11, as
oito constantes RCON) e o KAT bate — mas o KAT veio do mesmo zip que o
código, então se o zip não fosse autêntico nada aqui detectaria.

Fecha-se **para frente, não para trás**: `vendor_sources.py` pina os
SHA-256 dos arquivos em disco e o `--fetch` baixa da URL oficial do NIST e
confere arquivo a arquivo. O que não dá para reconstruir é a autenticidade
do download original — e o script diz isso, em vez de fingir que pina.

**2.9 [OBSERVAÇÃO] — o v1 gerou chaves com NumPy.**
`dataset_generator.py` deriva chaves com `np.random.default_rng` (PCG64) —
exatamente a prática que a Regra de Ouro 8 criou o CTR_DRBG para
substituir. A Regra 8 vale só para o v2, então não há violação; e não é
problema de correção (as chaves só precisam ser distintas e independentes
do rótulo, e são). Mas os resultados do v1 que estão na dissertação foram
gerados assim, e **o texto precisa dizer isso explicitamente** em vez de
deixar implícito que a disciplina do CTR_DRBG vale para tudo.

### Pontos de desenho que estão certos e valem uma frase no texto

- **Nonce contador de 128 bits** ⇒ 14 bytes zerados à esquerda. É nonce
  estruturado e de baixa entropia. Legal para os quatro (exigem unicidade,
  não imprevisibilidade) e **idêntico entre algoritmos**, logo não pode
  discriminar. Um avaliador vai perguntar — melhor antecipar. (Reforça o
  que já estava em §5.12: um nulo sob essa condição é mais forte.)
- **Reúso de chave entre algoritmos** (os mesmos 16 bytes para os 5 no
  slot) é a Regra 6 e é criptograficamente inócuo: cifras distintas com a
  mesma chave não se relacionam.
- **`feature_columns()` impõe a Regra 5 com `AssertionError`**, e a rodada
  `sanity_lenct` inclui `len_ct` de propósito para provar que o encanamento
  detecta o sinal trivial.
- **O truncamento do braço controlado** para 65.544 elimina o comprimento
  como discriminador, e o `shuffled` trunca antes de embaralhar.

265/265 testes.
