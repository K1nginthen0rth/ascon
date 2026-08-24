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
