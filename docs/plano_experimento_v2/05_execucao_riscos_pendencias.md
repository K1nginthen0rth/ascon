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


---

## 5.14 Sessão autônoma (2026-08-26/28) — extração completa + achado de vazamento em Grain

Sessão sem supervisão (Nycolas em viagem, 24h de janela, checagem horária).
Concluiu a Etapa 3 do runbook e, no tempo excedente, achou um vazamento real
que **contamina qualquer comparação envolvendo Grain-128AEAD no braço
`controlado`**.

### O que foi executado

1. **Extração completa dos 3 braços** (`controlado`, `cru`, `shuffled`) —
   180k amostras × 641 features cada, ~20h/braço. Uma queda de energia
   real interrompeu a extração do `controlado` na hora ~11 (20/30 row
   groups) — a retomada por chunk atômico funcionou exatamente como
   projetado, zero perda, zero `.tmp` corrompido. Os 3 parquets de
   features estão consolidados e validados (837 NaN esparsos em 115,7M
   valores, 0 Inf, 0 colunas 100% NaN, 300 chaves, balanceado).
2. **Diagnósticos planejados** (não dependiam de decisão do Nycolas):
   `sanity_lenct` no braço `cru` — F1=1,0000 como esperado (RF, Grain vs
   Ascon, comprimento cru inclui `len_ct` de propósito). `learning_curve`
   no braço `controlado` — é aqui que o achado começa.

### O achado: RF e XGBoost distinguem Grain-128AEAD no braço `controlado` — sem nenhuma feature individual mostrar separação

`learning_curve` (RF + LogisticRegression, 4/60/120/240 chaves de treino,
4 classes reais) mostrou LogisticRegression travada em F1≈0,25 (acaso) em
todo ponto, mas RandomForest **crescendo** de 0,249 (30 chaves) até 0,353
(240 chaves) — com o ganho quase todo em identificar corretamente
Grain-128AEAD (recall 0,247→0,592), enquanto os outros 3 permanecem perto
do acaso entre si.

Investigação (reproduzida fielmente fora do `learning_curve`, confirmando
F1=0,3533 com as mesmas 150 features do seletor mRMR):
- **Nenhuma feature individual separa** — maior |Cohen's d| entre Grain e
  o resto é ≈0,018 (ruído), espalhado por famílias não relacionadas
  (histograma, autocorrelação, NIST STS). As features de `tag_region`
  (`tag8_*`) têm d≈0,02 — consistente com o resíduo já documentado em
  §5.11/§5.12 (d≈0,03σ), mas pequeno demais para explicar sozinho o que
  segue.
- **Reformular como binário "Grain vs. os outros 3 combinados", com as
  MESMAS 150 features, zera o sinal (F1=0,00, recall de Grain = 0)** —
  ou seja, o RF multiclasse não estava achando "assinatura do Grain"; a
  hipótese de trabalho passou a ser "Grain só parece diferente por não
  participar da confusão mútua entre os outros 3".
- **Essa hipótese caiu ao testar o par de verdade.** Rodando
  `run_analysis` real (a mesma função que `pairs` usa) para o par
  Grain-vs-Ascon isolado, sem SVM (orçamento pendente) e sem réplicas
  (`run_replicas=False` — exploração, nunca oficial):

  | Modelo | F1-macro (fold final, n=12.000) |
  |---|---|
  | LogisticRegression | 0,4971 (acaso) |
  | LinearSVC | 0,4970 (acaso) |
  | RandomForest | 0,6944 |
  | **XGBoost** | **0,9994** (IC95%=[0,9990, 0,9998]) |

  Consistente nos 5 folds de CV (0,9976–0,9994), não é artefato de um
  fold só.

- **A feature que o XGBoost usa é `payload_rest_max_freq`, com
  importância 0,42 — 22× a segunda colocada (0,019)** — mas o Cohen's d
  DESSA MESMA feature é 0,007 (médias iguais a 5 casas decimais, std
  minúsculo em ambas as classes; percentis 1–99% quase idênticos). Ou
  seja: nenhuma feature isolada é fraudulentamente forte — o que quer que
  o XGBoost esteja explorando é uma combinação não-linear fraca e difusa
  entre muitas features (bitblock, histograma), do tipo que boosting
  sequencial é excelente em amplificar e que bagging (RF, capturou só
  parte: 0,69) e modelos lineares (não capturam nada: 0,50) não
  conseguem.

### O controle que isola a causa

Se o mecanismo fosse geral (falha do pipeline, ou XGBoost "trapaceando"
de alguma forma universal), o mesmo padrão apareceria em QUALQUER par.
Testado nos 3 pares entre os algoritmos com ABYTES=16 (Ascon, GIFT-COFB,
Schwaemm256-128 — os únicos SEM a assimetria abaixo):

| Par | F1 XGBoost | Feature dominante |
|---|---|---|
| Ascon vs GIFT-COFB | 0,4959 | nenhuma (top ≈0,012) |
| Ascon vs Schwaemm | 0,4957 | nenhuma (top ≈0,013) |
| GIFT-COFB vs Schwaemm | 0,5011 | nenhuma (top ≈0,009) |

**Acaso puro nos três, mesmo com XGBoost.** O efeito é específico a
comparações que envolvem Grain — o único dos 4 algoritmos com ABYTES=8 em
vez de 16.

### Causa — confirmada por experimento, não só por inferência (2026-08-28, tarde)

`src/features/families/tag_region.py`: `payload_rest = ct[:-8]` (janela
comum de 8 bytes, decisão de desenho documentada — usar o `ABYTES` real
teria comparado tags de tamanhos diferentes entre si). E `_extract_row`
em `extract_features_v2.py` computa a família `tag_region` sobre
`ct_raw` (o CT ORIGINAL, não o truncado do braço) — decisão também
documentada, para não cortar a tag do Ascon ao meio (achado da auditoria
de 2026-08-23, comentário no código).

A combinação das duas decisões — cada uma correta isoladamente — cria uma
assimetria não coberta por nenhuma auditoria anterior: **`payload_rest`
do Ascon/GIFT-COFB/Schwaemm (ABYTES=16) sobra com 8 bytes residuais da
PRÓPRIA tag dentro da janela "payload"; o de Grain (ABYTES=8) é payload
puro, zero bytes de tag misturados.**

**Teste decisivo, pedido pelo Nycolas ("será que a costura em si não
carrega sinal de verdade?").** Reconstruí a fronteira payload/tag usando
o `ABYTES` REAL de cada algoritmo (não os 8 bytes fixos), lendo o parquet
de 11,8GB em streaming (nunca inteiro em memória):

1. **Payload puro** (`ct_raw[:-ABYTES]`, zero bytes de tag para os dois —
   e como os dois cifram o mesmo plaintext de 64KB, dá exatamente 65.536
   bytes para ambos, sem precisar normalizar nada): histograma de bytes
   → XGBoost → **F1=0,4943** (acaso).
2. **Costura simétrica de verdade** (8 bytes finais do payload real + 8
   bytes iniciais da tag real, ancorados na fronteira genuína de cada
   algoritmo — sempre 16 bytes, não importa se a tag é de 8 ou 16):
   XGBoost sobre os 16 bytes crus → **F1=0,4960** (acaso).

**Conclusão fechada: não existe nenhum sinal real, nem na fronteira, nem
no payload.** A hipótese de efeito de fronteira/finalização (squeeze do
sponge vs. keystream contínuo) está DESCARTADA — quando a régua mede
igual pros dois, mesmo o XGBoost (o método que achou F1=0,9994 com a
régua torta) não acha absolutamente nada. O F1=0,9994 original era
100% explicado pela assimetria de medição; não sobra resíduo nenhum de
uma propriedade real dos algoritmos. Script:
`.autonomo_logs/teste_costura_justa.py` (não versionado — reproduzir se
necessário, é ~25s de I/O).

### Por que isso importa — e o que NÃO fazer com o resultado

**Isto não é o "cenário demonstrável de distinguibilidade" que se buscava
(ver conversa de 2026-08-25)** — não é uma propriedade do Grain como
algoritmo correto e bem implementado; é uma assimetria de instrumentação
específica do braço `controlado` que só se manifesta contra o único
algoritmo com ABYTES diferente. Reportar F1=0,9994 como "Grain é
distinguível" seria repetir, numa forma mais sutil, o mesmo erro que o
braço `controlado` inteiro foi desenhado para evitar (comparar
comprimentos, não criptografia).

**Consequência prática, urgente:** qualquer rodada da `pairs`/`4class`
OFICIAL no braço `controlado`, como o código está HOJE, vai produzir
resultados contaminados nos 3 pares que envolvem Grain (e no `4class`
geral, via ele). **Não rodar `pairs`/`4class` oficial antes de decidir o
que fazer com isto** — ficou de fora do trabalho autônomo de propósito
(não é uma correção que dá pra fazer sem julgamento: mexer em
`tag_region`/`payload_rest` afeta o braço `cru` também, que sanity_lenct
depende do comportamento atual).

### Pendente — decisão do Nycolas

1. Como corrigir a assimetria: (a) usar `ct_branch` para TUDO, aceitando
   que a tag do Ascon fica pela metade nas famílias afetadas [ver o
   próprio comentário no código sobre por que isso foi rejeitado antes];
   (b) mudar `payload_rest` para excluir SEMPRE os últimos
   `max(ABYTES)=16` bytes do `ct_raw`, não um número fixo de 8 —
   simétrico para todos, mas passa a excluir metade do payload real do
   Grain também; (c) outra normalização. Cada opção tem trade-off e é
   decisão de desenho, não bug de código a corrigir sozinho.
2. Vale rastrear o mecanismo byte a byte antes de decidir, ou a
   caracterização acima (real, específica a ABYTES≠16, robusta ao
   controle) já é suficiente para agir?
3. Depois de corrigida (ou conscientemente aceita), a `pairs`/`4class`
   oficial precisa rodar de novo — o resultado de hoje não é utilizável
   como está.

265/265 testes (nenhum teste novo — investigação, não implementação;
nenhum código de produção foi alterado nesta sessão).

### Correção implementada (2026-08-28, à tarde, com o Nycolas de volta)

Decisão tomada em conversa: `payload_rest` passa a excluir sempre um
comprimento FIXO (`_PAYLOAD_REST_LEN = 65528`, derivado do menor
comprimento cru entre as 6 classes menos o maior ABYTES real), nunca
consultando o algoritmo da amostra para decidir quanto cortar — ponto
levantado pelo próprio Nycolas ("a régua não pode perguntar de quem é a
carta antes de medir"). `tag8` não muda (já era comum e comparável, é o
`payload_rest` que reusava a mesma janela por engano).

- `src/features/families/tag_region.py`: `payload_rest = ct[:-8]` →
  `ct[:_PAYLOAD_REST_LEN]`. Docstring do módulo reescrita para explicar o
  bug, a diferença entre o argumento do `tag8` (janela pequena e
  COMPARÁVEL, evita viés de amostra pequena) e o do `payload_rest`
  (janela GRANDE e FIXA, evita qualquer resíduo de tag — os dois
  argumentos são opostos, e a versão antiga aplicava o do `tag8` nos
  dois lugares por engano).
- `tests/test_tag_region.py` (novo, 8 testes) — o módulo não tinha
  NENHUM teste direto antes; é por isso que o bug sobreviveu a 7
  auditorias. Regressão específica: CT sintético com payload e tag em
  bytes diferentes (0x00 vs 0xFF), confere que `payload_rest` não tem
  NENHUM byte de tag para ABYTES=8 e ABYTES=16, e que o comprimento do
  `payload_rest` não muda com ABYTES (senão reintroduz comprimento como
  discriminador escondido).
- **Confirmado em dado real, não só no teste sintético**: recomputando
  só as 8 features de `tag_region` sobre os ciphertexts crus reais de
  Grain e Ascon (60.000 amostras, via streaming do parquet de 11,8GB),
  XGBoost volta a **F1=0,4949** (era 0,9994). `payload_rest_max_freq`,
  que antes sozinho valia importância 0,42 no modelo de 150 features,
  deixa de carregar qualquer sinal.

277/277 testes (269 + 8 novos de `tag_region`).

### Pendente: reextração

O `payload_rest` errado já está gravado nos 3 parquets de features
extraídos (`controlado`, `cru`, `shuffled` — os dois primeiros usam
`ct_raw` para `tag_region`, então têm o bug; `shuffled` usa `ct_branch`
já truncado e embaralhado, efeito ainda não confirmado — o conteúdo
residual da tag sobrevive ao embaralhamento em estatísticas de
frequência, mas a posição não, então pode ou não ter o mesmo problema
pra features que dependem de posição). Rodar `pairs`/`4class` oficial
exige reextrair pelo menos `controlado` e `cru` (~20h cada) com o código
corrigido. Decisão do Nycolas: reextrair agora, ou esperar juntar com a
decisão do orçamento do SVM pra não gastar a máquina duas vezes.


### Reextração concluída (2026-09-02) + decisão do orçamento do SVM

`controlado` e `cru` reextraídos com o `payload_rest` corrigido — 30/30
row groups cada, consolidados, e reconfirmados no dado final: F1=0,4949
(acaso) nas 8 features de `tag_region` para Grain-vs-Ascon, nos dois
braços. `shuffled` não precisou (já estava limpo — embaralhamento destrói
a posição fixa do vazamento antigo). Os 3 braços agora estão íntegros.

**Decisão do orçamento do SVM (Nycolas, 2026-09-02): subamostrar também o
fit final**, não só a busca de hiperparâmetros. `scripts/run_v2_caminho_a.py`:

- `SVM_SEARCH_SUBSAMPLE = 6000` (já existia) — busca de hiperparâmetros.
- `SVM_FINAL_FIT_SUBSAMPLE = 20000` (novo) — o fit que produz o modelo
  reportado passa a rodar numa subamostra de 20 mil, não no fold completo
  (que passava de 70 mil em algumas comparações). Com a escala medida de
  n^2,85, isso reduz o custo do fit final por várias dezenas de vezes.
  Vale só para o SVM-RBF — os outros 4 modelos (RandomForest, LinearSVC,
  XGBoost, LogisticRegression) continuam no fold completo, sem alteração.
- Custo aceito: um pouco menos de poder estatístico no resultado do SVM
  especificamente. Registrado nos metadados de cada fit
  (`final_fit_subsample` no dict retornado por `fit_svm_with_search`),
  então qualquer leitura do resultado sabe quantas amostras sustentaram
  aquele SVM em particular.
- 4 testes novos em `tests/test_v2_runners.py` (dataset sintético,
  confere que o fit final trunca para `SVM_FINAL_FIT_SUBSAMPLE`, que o
  caminho de fallback com poucos grupos também respeita o teto, e que
  nada trunca quando o fold já é menor que o alvo). 281/281 testes.

Com isso, os dois bloqueios da `pairs`/`4class` oficial (o vazamento do
`payload_rest` e o orçamento do SVM) estão resolvidos. Rodando agora a
sequência completa da Etapa 4 do runbook.

### Dois bugs achados AO VIVO rodando o Caminho A completo pela primeira vez (2026-09-02)

Nenhum dos dois apareceu em teste sintético nem no benchmark rápido de
57,3s citado acima — só rodando em dado real, no tamanho real, é que se
manifestaram. Registro para o texto: a suíte de 284 testes garante que o
código faz o que foi desenhado pra fazer, não que os hiperparâmetros
escolhidos se comportam bem em TODO tamanho de amostra — isso só se
descobre rodando.

**1. O SVM-RBF dentro do `StackingClassifier` também precisava de
subamostra — não só o SVM-RBF principal.** `fit_svm_with_search` (a
correção da tarde) só cobria o modelo "SVM-RBF" isolado. O Stacking cria
seu PRÓPRIO SVM-RBF, com hiperparâmetros fixos por desenho (documentado:
buscar hiperparâmetros dentro de cada split interno do stacking
multiplicaria o custo da busca pelo nº de splits). Esse SVM interno é
ajustado ~4 vezes por fold (3 splits internos de CV + 1 no treino
completo), sem NENHUMA subamostra — sozinho, travou um fold real por mais
de 2h20 sem produzir nenhuma linha de log nova, rodando a sequência
completa pela primeira vez. `SubsampledSVC` (novo, em
`scripts/run_v2_caminho_a.py`): wrapper de `SVC` que aplica
`SVM_FINAL_FIT_SUBSAMPLE` antes do `.fit()`, plugado no lugar do `SVC` cru
dentro de `build_stacking_model`. Confirmado em dado real: 57,3s por fold
(era >2h20 e ainda não tinha terminado).

**2. `gamma="scale"` degenera na subamostra — achado DEPOIS de corrigir o
#1.** Com o SVM do Stacking agora rodando rápido, os 3 primeiros pares
completaram — e o modelo "Stacking" deu F1≈0,33-0,40 em vez de ≈0,50,
sistematicamente. Investigado com o confusion matrix salvo: **previa uma
única classe para as 12.000 amostras de teste, nas duas classes
verdadeiras.** Isolado experimentalmente: com a subamostra de 20.000, os
2 valores de C testados (1 e 10) davam o MESMO resultado degenerado com
`gamma="scale"` (todos os 20.000 pontos da subamostra viravam vetor de
suporte — kernel achatado a ponto de virar quase constante), e o MESMO
resultado saudável com `gamma=0.01` ou `gamma="auto"`. `gamma="scale"` é
calculado a partir de `1/(n_features×X.var())` — depende da variância da
amostra que recebe; no fold/trainval completo (48 mil, sem subamostra)
isso nunca tinha dado problema, porque a variância medida ali era
diferente o suficiente para não cair nessa zona degenerada. Corrigido:
`gamma=0.01` fixo (o mesmo valor já testado em `SVM_GRID`) em vez de
`"scale"`. Confirmado em dado real, no trainval completo (n=48.000):
F1=0,4971, previsões balanceadas [5967, 6033] contra real [6000, 6000].

**2 testes novos** (`tests/test_v2_runners.py`) travam os dois achados:
`SubsampledSVC` de fato trunca e não define `predict_proba` (evitaria o
custo de calibração Platt); `build_stacking_model` nunca mais usa
`gamma="scale"`. 284/284 testes.

**As 3 primeiras execuções de `pairs controlado` (Ascon-GIFT, Ascon-Grain,
Ascon-Schwaemm) ficaram contaminadas com o resultado degenerado do
Stacking** — os JSONL de métrica são append-only, então as duas rodadas
(antes e depois da correção do `gamma`) ficaram misturadas no mesmo
arquivo, distinguíveis só por timestamp. **Apagados e a sequência inteira
relançada do zero** depois da segunda correção — os números anteriores
citados nesta seção vieram de scripts de diagnóstico isolados, não da
rodada oficial, que não deve ser lida até terminar limpa.

### Etapas 1-6 concluídas (2026-09-03) — resultados primários + 1 observação

`pairs` e `4class` (a família primária) completos, sem o problema de
degeneração se repetir. `ecb_control` (F1=0,9773, RF) e `prng_control`
(F1≈0,50 nos 4) confirmam que o pipeline detecta sinal quando ele existe e
fica no acaso quando não existe — os dois controles funcionando como
esperado.

**Observação, não bug: instabilidade pontual do Stacking em 1 dos 6 pares.**
GIFT-COFB vs Schwaemm256, modelo `Stacking`, `fold=final`: F1=0,3955
(cm=[[5545,455],[5511,489]] — víes de 92%/8% entre as classes), destoando
dos outros 5 pares (todos ~0,49-0,51). Investigado:

- Os 5 folds de CV desse MESMO par, MESMO modelo Stacking: todos normais
  (~0,50, matrizes balanceadas). Só o ajuste final (o único que passa pela
  subamostra de 20 mil) mostra o desvio.
- Todos os OUTROS 8 modelos desse par no ajuste final — incluindo o
  SVM-RBF isolado e o **RandomForest, que é o modelo oficial da
  comparação** — deram resultado normal (~0,49-0,51).

Ou seja: não é um hiperparâmetro errado nem um mecanismo quebrado (como os
dois achados anteriores) — parece ruído genuíno do meta-modelo do
Stacking numa única instância da subamostra, quando a base inteira é H0.
**Não afeta o resultado primário do par** (RandomForest normal). Registrado
como limitação observada da réplica de Stacking sob subamostra — não
refeito, porque forçar até sair diferente seria manipular o resultado, não
corrigir um bug.

### Escopo da Etapa 4 reduzido por decisão do Nycolas (2026-09-04)

Debatido em conversa, depois de ver os custos reais (~11h por análise tipo
`pairs`) e os resultados das etapas 1-8 já rodadas:

- **`shuffled` (etapas 9 e 10, controle negativo) — descartado.** Já tinha
  rodado o `4class` (etapa 9) antes da decisão; o `pairs` (etapa 10) foi
  interrompido no meio (só o par Ascon-vs-GIFT parcial, descartado). Meu
  argumento contra descartar: é a defesa contra exatamente a CLASSE de bug
  que o `payload_rest` já mostrou existir (um artefato de posição/conteúdo
  que sobrevive a leitura casual do resultado) — mas é uma decisão de
  escopo legítima do Nycolas, não um erro. Registrado aqui para quem ler
  os resultados depois: **as etapas 1-8 e 11-12 não têm o controle negativo
  de embaralhamento como respaldo.** Se um resultado de `pairs`/`4class`
  vier positivo, essa lacuna deveria ser reaberta antes de reportar o
  achado como definitivo (rodar 9/10 especificamente para o par/cenário
  positivo, não a suíte inteira de novo).
- **`family_ablation` (etapa 13) e `permutation` (etapa 14) — adiadas, não
  descartadas.** Ficam para depois, principalmente se a `4class` oficial
  vier positiva — description do porquê (qual família carrega o sinal;
  validação estatística formal contra o nulo empírico) na conversa que
  gerou esta decisão.
- **Etapa 11 (4class sem key-holdout) mantida** — o Nycolas concordou que
  essa continua necessária.

Sequência final rodada oficialmente: 1, 2, 3, 4, 5, 6, 7, 8, 11, 12.
