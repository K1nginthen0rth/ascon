# 2. Features e seleção

## 2.1 Suíte de features v2

### Mantidas do v1 ✅ (307D, 6 famílias)

Histograma de byte (256) · Entropia byte (4) · N-gramas (15) · Autocorrelação +
runs de byte (18) · Complexidade LZ76/zlib/bz2 (4) · FFT de byte (10).

### Suíte NIST SP 800-22 completa — nível de bit ✅ IMPLEMENTADA (2026-08-21)

Decisão do Nycolas: implementar **os 15 testes**; se alguma implementação não
render sinal, o seletor filtra. Com uma ressalva imposta pelo Claude e aceita:
falha silenciosa ≠ cálculo errado — ver validação abaixo.

**Implementado em `src/features/families/nist_sts.py` (25 features, 24
testes em `tests/test_nist_sts.py`).** Um bug crítico de corrupção
silenciosa de dados foi encontrado e corrigido durante a implementação
(Binary Matrix Rank mutava o array de bits compartilhado in-place,
afetando os 7 testes seguintes na ordem de execução) — detalhe completo em
`06_implementacao_passo_a_passo.md` Fase 2.1. Duas limitações estruturais
documentadas (não bugs): Overlapping Template Matching sempre inelegível
em CTs de 64KB (exige ≥1.028.016 bits); Excursões inelegíveis numa fração
relevante das amostras (exigem J≥500 ciclos, medido ~100-700 em CTs reais).

| Grupo | Testes | Observação |
|---|---|---|
| Núcleo (baratos/médios) | Monobit, Frequência em Blocos, Runs-bit, Cusum, Rank de matriz GF(2), Espectral-bit (DFT ±1), Maior sequência de 1s, Entropia aproximada, Serial | risco baixo |
| Condicionais (caros) | Template não-sobreposto, Template sobreposto, Universal (Maurer), **Complexidade linear (Berlekamp-Massey)**, Excursões aleatórias, Excursões (variante) | ver ressalvas |

**Ressalvas obrigatórias:**
- **Complexidade linear:** validar contra vetores de exemplo do próprio SP
  800-22 **antes** de entrar no pipeline. Motivo: um bug de Berlekamp-Massey
  produz números plausíveis-mas-errados que o seletor não distingue de sinal —
  pode fabricar falso positivo, não só "não achar nada".
- **Todas as demais implementações NIST** 🔶: validar contra os exemplos de
  referência do SP 800-22 (o documento traz sequências com valores esperados).
  Extensão da mesma lógica, recomendada na revisão de especialista.
- **Excursões aleatórias:** NaN esperado com frequência (exige ≥500 ciclos do
  passeio; propriedade da amostra, não bug). Imputação NaN→0 já existente cobre.
- **Universal (Maurer):** 64KB = 524.288 bits passa do mínimo (~387.840) só
  para L=6, sem margem — documentar o parâmetro usado.

### Da RSL — 5 selecionadas ✅ IMPLEMENTADAS (2026-08-21)

`moments.py` (2), `spectral_welch.py` (5), `bitblock.py` (~282, blocos 2/4/8
brutos + 12/16 agregados), `compression_ratio_lzma` em `complexity.py`,
`hamming.py` (11) — todos registrados no extractor e testados.

| Feature | Fonte | Detalhe |
|---|---|---|
| Skewness + kurtosis da distribuição de bytes | E13 — Zhou, 2025 (SIL, modalidade Signal) | `scipy.stats`, trivial |
| Welch PSD + descritores espectrais (centróide, largura de banda, flatness, roll-off 85%) | E13 — Zhou, 2025 | `scipy.signal.welch`; granularidade e método distintos do FFT de byte existente |
| Histograma de blocos de bits em tamanho variável | E01 — de Mello & Xexéo, 2016 (blocos 2–34 bits); E03 — Barbosa et al., 2017 (4–16 bits) | blocos pequenos: histograma bruto; blocos ≥16 bits: estatísticas agregadas (entropia, nunique, max_freq — como os n-gramas já fazem) |
| Razão de compressão lzma | E13 — Zhou, 2025 | stdlib; complementa zlib/bz2 |
| Distribuição de peso de Hamming | E07 — Zhao et al., 2023 | derivável do histograma por soma linear (popcount por valor de byte); **promovida de "descartada" para obrigatória** — é a representação que define o estudo, e a réplica XGB-LGBM (`03_classificadores.md` §3.1) precisa dela para sustentar a alegação "a técnica de Zhao, sob nosso protocolo" |

### Primeiros princípios — 1 selecionada ✅ IMPLEMENTADA (janela corrigida, 2026-08-21)

`src/features/families/tag_region.py`: `extract_tag_region` (janela comum
8B, registrada no extractor — 8 features) + `extract_tag_region_full`
(exploratório, ABYTES real por algoritmo, chamada separada fora do
extractor por precisar do metadado `algorithm`/`abytes` por amostra).

**Separação tag vs. payload:** estatísticas calculadas separadamente para a
tag e para o payload. Justificativa inalterada: a tag é gerada por mecanismo
estruturalmente distinto em cada algoritmo (squeeze da permutação / máscara
COFB / acumulador dedicado / finalização Schwaemm), enquanto o payload é
desenhado para parecer uniforme nos quatro — se há lugar provável para
assinatura, é a tag.

**Correção — janela comum de 8 bytes na comparação principal:** usar
`ABYTES` real de cada algoritmo (16 para Ascon/GIFT/Sparkle, 8 para Grain)
introduz um viés conhecido de estimador em amostra pequena: para `n` bytes
i.i.d. uniformes com `n≪256`, a entropia de Shannon do histograma observado
tende a `log₂(n)` sempre que a amostra não tem repetição (caso dominante
nessa faixa) — ou seja, ≈3,0 bits para uma janela de 8 bytes e ≈4,0 bits para
16, **independente de qualquer propriedade da fonte**. `nunique`, `max_freq`
normalizado e o χ² seguem o mesmo padrão. Nessas condições, "estatística da
tag" com `ABYTES` real separa o Grain dos outros três por tamanho de janela,
não por mecanismo criptográfico — reintroduzindo `len_ct` como feature pela
porta dos fundos (violação de fato, não só de forma, da Regra de Ouro 5).

Correção: a comparação principal usa **janela comum de 8 bytes** (o mínimo
entre os algoritmos, tomada sempre sobre o CT **cru**, nunca sobre o braço
`controlado` — ver `01_algoritmos_e_dataset.md` §1.6) para todos os quatro
algoritmos — mesmo estimador, mesmo viés, para todos, então o viés deixa de
correlacionar com identidade. Estatísticas sobre a tag completa (16 bytes) dos
três algoritmos que a têm ficam como análise **exploratória separada**, com o
viés de amostra pequena declarado no texto. Escopo mantido: só estatísticas
que fazem sentido em 8 bytes (histograma, entropia, χ²) — LZ, autocorrelação
de 16 lags e FFT não operam nessa escala. Fronteira definida pelo `ABYTES` do
wrapper para a versão exploratória; janela fixa de 8 para a principal.

### Consideradas e descartadas ✅

| Feature | Motivo do descarte |
|---|---|
| TF-IDF + SVD ("language" do SIL) | exige fit por fold (risco de vazamento); retorno modesto no próprio estudo de origem |
| Frequência de caracteres (E16, Dhawade) | versão mais grosseira do histograma de byte já existente |
| Mapa de p-values NIST como imagem (E11, Li & Chen) | ideia registrada como variação possível dos Caminhos C/E — não adotada nesta rodada |
| Deriva posicional (segmentos) | proposta de primeiros princípios rejeitada pelo Nycolas |

**Total estimado: 641 (medido; a estimativa de projeto era ~380–420) features** (o número exato depende de decisões de
agregação nos templates e blocos de bits — fixar na implementação).

## 2.2 Redesenho do seletor ✅ IMPLEMENTADO (2026-08-21)

`src/features/selector.py` — 14 testes em `tests/test_selector.py`
(incluindo validação multiclasse, nunca exercitada além de binário antes
desta sessão). Detalhe completo em `06_implementacao_passo_a_passo.md` Fase 3.

Pipeline final, na ordem, **fitado só no treino de cada fold** (regra
inalterada):

```
0. Padronização z-score          (fit no treino do fold)
1. VarianceThreshold             sobre features PADRONIZADAS
2. MI — corte generoso           (~top 300-350; explicitamente NÃO-estatístico)
3. mRMR                          (seleção real: relevância − redundância)
4. Boruta                        (diagnóstico apenas; não filtra — já em vigor)
```

**Mudanças e porquês:**

1. **VT sobre z-score:** o corte bruto (1e-5) comprovadamente descartava 278/307
   features (todo o histograma) por escala, não por falta de informação
   (ablação v1). Padronizado, "baixa variância" volta a significar
   "genuinamente constante".
2. **MI rebaixado a corte de conveniência:** um limiar de MI com pretensão
   estatística seria tão arbitrário quanto o top-k antigo (o estimador dá
   valores positivos pequenos até para ruído puro; média dos ≠0 deixaria ~40%
   do ruído passar). Decisão conjunta: MI só reduz volume para o mRMR; **a
   validação sinal-vs-ruído acontece no resultado final**, por teste de
   permutação (mesma metodologia da ablação v1). A ideia de cota por família
   foi superada por esta abordagem.
3. **mRMR é o estágio que define o conjunto** — alvos (`n_features_mrmr`)
   recalibrados para o total novo; se menos features sobreviverem ao corte do
   que o alvo, aceitar menos (não forçar).
4. **Sem RFE** (deliberado, documentar na metodologia): RFE amarraria a seleção
   à importância de um classificador específico e quebraria a comparação justa
   do Caminho A, onde todos os modelos recebem o mesmo conjunto.
5. **Validação multiclasse empírica** antes da rodada real: teste unitário com
   dado sintético de 4 classes para MI/mRMR/Boruta (nunca usados além de 2
   classes neste projeto).

## 2.3 [PENDENTE-P4] Baseline de features aleatórias (item que ficou órfão nas rodadas de decisão — nunca foi aprovado nem rejeitado; ver 06 §P)

Validação do seletor prevista em `contexto_inicial.md` e nunca executada:
comparar N features selecionadas pelo mRMR contra N features **sorteadas**, via
McNemar. Se o desempenho for igual, a seleção não agrega — precisa ser sabido e
reportado.
