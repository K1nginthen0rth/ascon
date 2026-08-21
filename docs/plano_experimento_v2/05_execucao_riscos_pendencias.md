# 5. Execução, riscos e pendências

## 5.1 Fases de execução (proposta — ordem por dependência)

| Fase | Conteúdo | Depende de | Hardware |
|---|---|---|---|
| 1 | Correção Ascon (`ascon128av13`) + wrappers Grain e Sparkle (KAT cada) + CTR_DRBG (validação CAVP) + features novas (validação contra vetores SP 800-22) | — | CPU |
| 2 | Geração do dataset v2 (150k encadeado, 80/20 texto/imagem) + validação v2 | fase 1 | CPU |
| 3 | Caminho A completo + ablações baratas (key-holdout on/off, truncamento Grain, famílias) + controles no A | fase 2 | CPU |
| 4 | Caminhos B e C | fase 2 (3 valida o encanamento antes) | GPU |
| 5 | Caminho E (Transformer) | infra de 4 estabilizada | GPU |
| 6 | Caminho D (híbrido) | latentes de B, C, E | GPU |
| 7 | Caminho F (meta) | saídas de A–E | CPU/GPU leve |

O Caminho A primeiro **não é gate de desistência** (nulo é esperado e não
interrompe nada) — é validação barata de wrappers/dataset/pipeline antes de
comprometer GPU.

## 5.2 Orçamento computacional — o que se sabe de fato

- **SVM (dado real do v1):** busca em grade nos 5 folds = 8.365s (~139 min) a
  38.400 amostras/fold, variação 245–2.965s entre folds. Sem correção, no v2
  (76.800/fold) extrapolaria para 15–30h+; **com a correção por subamostra
  (aceita), estimado em dezenas de minutos.**
- **GPU:** Colab+ planejado (A100 provável). Números reais de B/C/E/D não
  existem — **medir com smoke test adaptado** (4 algoritmos, amostra reduzida)
  antes de comprometer sessões longas; o `smoke_test.py` existente é o molde.
- **✅ Benchmark de extração rodado (2026-08-21, 20 amostras):** total
  projetado 249,5h de CPU serial para 180k amostras — abaixo do teto de
  48h paralelizado (~15-31h com 8-16 cores via joblib). Dois pontos
  concentram >95% do custo: `nist_sts` (205,8h — já otimizado nesta sessão
  de uma estimativa inicial >5000h) e `complexity`/LZ76 (37,2h — O(n²),
  não otimizado, decisão de investir mais fica para o Nycolas). Detalhe
  completo em `06_implementacao_passo_a_passo.md` Fase 2.4.
- Armazenamento: ~9,8 GB parquet + features (~120k × ~400 floats, trivial).

## 5.3 Riscos e planos B

| Risco | Mitigação |
|---|---|
| ✅ Código de referência Grain/Sparkle não compilar limpo no MSVC (precedente: GIFT-COFB exigiu headers customizados) | **Não se concretizou (2026-08-21):** ambos ANSI C/C99 portável, compilaram de primeira sem patch. |
| ✅ Variante/parâmetros exatos do Schwaemm | **Confirmado (2026-08-21):** Schwaemm256-128 (128/256/128), `schwaemm_cfg.h` já fixa a variante. |
| Berlekamp-Massey (e demais NIST) com bug plausível-mas-errado | validação obrigatória contra vetores do SP 800-22 antes de entrar no pipeline (ver 02) |
| Colapso de CNN mal diagnosticado no 4-classes | valores de referência pré-calculados (colapso 0,10 vs acaso 0,25) + 🔶 diagnóstico de posto do latente |
| Caminho F "achar sinal" com individuais no acaso | tratado como bandeira de investigação de artefato, não como descoberta (registrado em 03) |
| Perda de resultados por queda de sessão | função de relato única com gravação incremental (regra obrigatória, ver 04) |

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
