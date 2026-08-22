# 6. Implementação passo a passo — guia executável

**Data:** 2026-08-21. **Este é o documento-norte da implementação do v2.**
Em caso de divergência entre este arquivo e os arquivos 01–05 (que registram o
histórico das decisões), **este arquivo prevalece** — ele incorpora a rodada
final de decisões e as correções da análise crítica
(`docs/analise_critica_plano_v2.md`).

## Como usar este documento (regras para quem implementa — humano ou LLM)

1. **Siga as fases em ordem.** Cada fase tem critérios de aceite; não avance
   sem cumpri-los.
2. **Não tome nenhuma decisão marcada `[PENDENTE]`** (§P no fim). Se encontrar
   ambiguidade não coberta aqui, **pare e pergunte** — não improvise.
3. **Toda avaliação de modelo passa pela função única de relato** (Fase 5).
   Nunca imprima/salve métricas por conta própria.
4. **Seeds canônicas imutáveis:** split=42, modelo=7, FS=13, bootstrap=42.
5. **Nunca** usar NumPy RNG para material criptográfico (chaves/plaintexts/
   nonces/PRNG-controle) — só o CTR_DRBG (Fase 1). NumPy permanece no
   bootstrap de métricas; torch nos treinos.
6. **`len_pt`/`len_ct`/`len_ad` nunca são features** — exceção única e
   deliberada: o sanity check da Fase 6.7.
7. Idioma dos artefatos: português, no estilo dos módulos existentes.

## Placar de decisões (resolve todos os 🔶 dos arquivos 01–05)

**Aprovado:** controles negativos PRNG+shuffle · família primária = 6 pares
par-a-par no Caminho A com F1 oficial · FDR (Benjamini-Hochberg) no
exploratório · replicação com chaves novas para positivos · poder a priori ·
curvas de aprendizado · calibração antes do F · HP search reduzida nos
profundos (8–12 configs, 1 fold) · 3 seeds no modelo final de B/C/E ·
validação de TODAS as features NIST contra vetores · benchmark de extração
(gate) · sanity `len_ct` · posto dos latentes · contagem de parâmetros ·
estratificação de erro · overlap de plaintext · condicionamento CNN2D ·
CTR_DRBG só na geração · ordem de fases abaixo · propor Zenodo ao orientador.

**Rejeitado:** pré-registro formal · variante Ascon de rodadas reduzidas ·
dataset secundário de 1KB.

**[PENDENTE] (não implementar sem decisão):** ver §P.

---

## FASE 0 — Housekeeping ✅ CONCLUÍDA (2026-08-21)

1. ✅ Commitado (`5b46413`) — Boruta diagnóstico (7 arquivos).
2. ✅ Artefatos do Caminho D copiados para
   `reports/keyholdout_2class_60k_v1_hybrid/` (gitignored, local).
3. ✅ `docs/analise_completa/08_achados_e_pendencias.md` §1 atualizado —
   D resolvido, B/C do v1 seguem não localizados (não bloqueia o v2, que
   gera B/C do zero).

**Aceite:** `git status` limpo nos 7 arquivos; artefatos D no repositório. ✅

## FASE 1 — Fundações criptográficas ✅ CONCLUÍDA (2026-08-21)

### 1.1 Correção do Ascon ✅
- `src/crypto/_ascon_cffi_build.py`: `ASCON_REF_DIR` →
  `ascon-c/crypto_aead/ascon128av13/ref` (commit `f4b4f3c`).
- KAT revalidado contra `ascon128av13/LWC_AEAD_KAT_128_128.txt` — **1089/1089**.
- `tests/test_ascon_wrapper.py`, `ascon_cli_ref.c`, `sanity_ascon_ref.c`
  atualizados junto (mesma correção de path).
- **Aceite:** KAT 1089/1089 ✅; `pytest tests/test_ascon_wrapper.py` verde ✅.

### 1.2 CTR_DRBG ✅
- `src/crypto/ctr_drbg.py`: `CTRDRBGCore` (Instantiate/Reseed/Generate/Update,
  fiel ao SP 800-90A §10.2.1) + `CTRDRBG` (API de alto nível: `generate`,
  `random_key`, `randint`, `choice_bool`) — AES-128, sem função de derivação
  (commit `998610e`).
- Vetores CAVP (DRBGVS, `[AES-128 no df]`, 240 casos) extraídos de
  `CTR_DRBG.txt` oficial do NIST e salvos em
  `tests/vectors/ctr_drbg_aes128_nodf.json` (proveniência em
  `tests/vectors/README.md`). `tests/test_ctr_drbg.py::test_cavp_vectors`
  valida — **240/240 batem byte-a-byte, sem correção necessária**.
- Entropia de entrada derivada via SHA-256 da seed fixa do projeto (uso do
  *mecanismo* como PRNG reprodutível, documentado no docstring do módulo).
- **Aceite:** vetores CAVP passam ✅; mesma seed ⇒ mesma sequência ✅.

### 1.3 Wrapper Grain-128AEAD ✅
- Fonte: implementação de referência oficial dos designers
  (`github.com/Grain-128AEAD/Grain-128AEAD-sw-ref`), vendorizada em
  `grain-128aead/` (gitignored). KAT oficial já incluso (1089 vetores).
- Compilação MSVC de primeira, sem patch — código já era ANSI C portável
  (risco nº 1 do §5.3 não se concretizou).
- `src/crypto/_grain_cffi_build.py` + `src/crypto/grain_wrapper.py` +
  `build_grain.bat`, molde idêntico ao GIFT-COFB.
  **`KEYBYTES=16, NPUBBYTES=12, ABYTES=8`.**
- `tests/test_grain_wrapper.py` — 16 testes, KAT **1089/1089**. Commit `85af5ef`.
- **Aceite:** KAT 100% ✅; roundtrip ✅; testes verdes ✅.

### 1.4 Wrapper Sparkle/Schwaemm ✅
- Variante confirmada: **Schwaemm256-128** (chave 128 / nonce 256 / tag 128
  bits) — `schwaemm_cfg.h` já fixa `SCHWAEMM256_128`, sem depender de macro
  externa.
- Fonte: `ref/` do pacote **oficial de submissão ao NIST LWC**
  (`csrc.nist.gov/.../updated-submissions/sparkle.zip`,
  `Implementations/crypto_aead/schwaemm256128v2/ref/`), vendorizado em
  `sparkle/crypto_aead/schwaemm256128v2/` (gitignored) — preferido ao clone
  GitHub `cryptolu/sparkle` (também obtido, mas descartado: não trazia KAT
  para a variante 256-128, exigiria autogeração pela própria implementação
  sob teste, o que só validaria a compilação, não o algoritmo).
- Compilação MSVC de primeira, sem patch (C99 portável, igual ao Grain).
- `_sparkle_cffi_build.py` + `sparkle_wrapper.py` + `build_sparkle.bat`.
  `NPUBBYTES=32, ABYTES=16`.
- `tests/test_sparkle_wrapper.py` — 16 testes, KAT oficial **1089/1089**
  (não autogerado). Commit `e6be72c`.
- **Aceite:** KAT 100% ✅; testes verdes ✅.

**Aceite da fase:** `pytest tests/ -v` inteiro verde — **182/182 passando**. ✅

## FASE 2 — Features novas

### 2.1 Suíte NIST SP 800-22 (15 testes, nível de bit) ✅ CONCLUÍDA (2026-08-21)

- `src/features/families/nist_sts.py`, prefixo `nist_`, 25 features (alguns
  testes produzem múltiplos p-values — serial, cusum, excursões — e os
  templates são agregados, não expandidos em colunas). Backend: pacote
  `nistrng` (BSD-3), auditado linha a linha em vez de reimplementado do zero
  — decisão tomada em sessão pelo risco de reintroduzir bugs sutis nos 15
  testes ao reimplementar sem essa base.
- **Validação:** em vez de vetores numéricos oficiais recordados de memória
  (risco de citar mal um valor "oficial"), `tests/test_nist_sts.py` valida
  por reimplementação independente das fórmulas (Monobit, Runs) e por casos
  pequenos computáveis à mão (Berlekamp-Massey contra LFSRs de complexidade
  conhecida; Binary Matrix Rank contra matrizes de posto conhecido) — mesmo
  princípio do documento original, executado de forma mais robusta a erro
  de memória do que citar exemplos textuais.
- **[CRÍTICO] Bug de corrupção silenciosa encontrado e corrigido:**
  `BinaryMatrix` (dentro do teste Binary Matrix Rank do `nistrng`) faz
  eliminação gaussiana diretamente sobre uma VIEW do array de bits de
  entrada (sem copiar) — mutava `bits` in-place, corrompendo os 7 testes
  seguintes na ordem de execução (DFT, Approximate Entropy, Maurer's
  Universal, Serial, Cumulative Sums, Linear Complexity, Excursões), que
  passavam a operar sobre lixo em vez do ciphertext real. Confirmado
  reproduzindo com 4 sequências aleatórias independentes: os mesmos 7
  testes davam p=0.0 exato toda vez (assinatura de corrupção sistemática,
  não variância estatística). Corrigido: toda chamada a um teste do
  `nistrng` passa `bits.copy()`, nunca a referência compartilhada — teste
  de regressão dedicado em `test_nist_sts.py`. **Se não tivesse sido
  encontrado, ~metade da suíte NIST estaria computando estatísticas sobre
  dados corrompidos, silenciosamente, no experimento inteiro.**
- **Dois outros desvios do `nistrng` corrigidos/contornados** (não no
  pacote vendorizado, na camada `nist_sts.py`): Non-overlapping Template
  Matching sorteava 1 template aleatório sem seed a cada chamada
  (não-determinístico — reimplementado agregando os 154 templates
  disponíveis, deterministicamente, com casamento vetorizado — a versão
  ingênua posição-a-posição não terminava em tempo viável em CTs de 64KB,
  ~1000x mais lenta); Random Excursion Variant calculava o argumento de
  `erfc` mas esquecia de aplicar `erfc` (bug confirmado por leitura,
  corrigido). Cumulative Sums também tinha overflow silencioso de `int8`
  no acumulador manual — contornado alimentando esse teste com `int32`.
- **Limitações estruturais na escala de 64KB (524.416 bits), não bugs:**
  Overlapping Template Matching exige ≥1.028.016 bits — **sempre**
  inelegível em qualquer amostra do dataset v2 (`nist_overlapping_template_valid=0`
  sempre; feature permanece no vetor por consistência de dimensão, nunca
  contribui variância real). Linear Complexity exige oficialmente ≥1e6 bits,
  mas 524.416/512=1024 blocos EXATOS (divisão limpa) — eligibilidade
  relaxada deliberadamente para esse caso específico (matematicamente
  válido, só com menos blocos que o recomendado), diferente do Overlapping
  Template (blocos ficariam parciais — rodar seria lixo, não sinal fraco).
  Excursões: precisam de J≥500 ciclos; medido empiricamente ~100-700 ciclos
  em CTs de 64KB reais — `nist_excursions_valid=0` esperado em fração
  relevante das amostras, não uma falha rara.
- **Aceite:** 24 testes em `test_nist_sts.py`, todos verdes; performance
  medida (ver 2.4) — extração de ~2s/amostra após vetorizar o template
  matching (era >100s/amostra na versão ingênua, inviável para 180k amostras).

### 2.2 Features da literatura
- `src/features/families/moments.py`: skewness + kurtosis (scipy).
- `src/features/families/spectral_welch.py`: Welch PSD (nível de bit ±1) +
  centróide, largura de banda, flatness, roll-off 85%.
- `src/features/families/bitblock.py`: histograma de blocos de bits — blocos
  de 2/4/8 bruto; 12/16 como agregados (entropia, nunique, max_freq).
- `src/features/families/hamming.py`: distribuição de peso de Hamming
  (obrigatória — representação da réplica XGB-LGBM).
- lzma: adicionar `compression_ratio_lzma` em `complexity.py`.

### 2.3 Tag vs. payload
- `src/features/families/tag_region.py`. **Janela comum de 8 bytes finais**
  (min ABYTES) para as features comparáveis: histograma agregado, entropia,
  χ² da janela + o mesmo para o payload (tudo-menos-tag do algoritmo).
- **Sempre sobre o CT cru** — a extração de tag ignora o braço de truncamento.
- Tag completa por algoritmo (16 vs. 8): só análise exploratória, braço cru,
  viés de estimador declarado no relatório.
- Fronteira via `ABYTES` do wrapper — nunca offset fixo.

### 2.4 Benchmark de extração — **GATE da Fase 4** ✅ RODADO (2026-08-21, 20 amostras)

`scripts/benchmark_extraction_v2.py` — números reais sobre CTs de 65.552
bytes do dataset v1 (`reports/v2/benchmark_extracao.md`, gitignored —
reprodutível a qualquer momento):

| Família | ms/amostra | Horas projetadas (180k, serial) |
|---|---|---|
| **nist_sts** | 4115 | **205,8** |
| **complexity** | 745 | **37,2** |
| spectral_welch | 104 | 5,2 |
| ngrams / bitblock / moments | 6 | ~0,3 cada |
| demais (histogram/entropy/autocorr/frequency/hamming/tag_region) | <4 | ~0,01–0,17 cada |
| **TOTAL (serial, 1 processo)** | — | **249,5h** |

**Dois pontos concentram >95% do custo:**
- `nist_sts` (205,8h): já reduzido de uma estimativa >100s/amostra (>5000h
  projetadas) para ~4-5s/amostra por três rodadas de otimização
  (vetorização do template matching, vetorização de approximate
  entropy/serial, numba no Berlekamp-Massey) — ver Fase 2.1. Custo
  residual é inerente à suíte (15 testes estatísticos reais por amostra).
- `complexity` (37,2h) — **não otimizado nesta sessão, risco já registrado
  no plano original (§5.2):** `lz_complexity` (LZ76) é O(n²) na
  implementação atual (`src/features/families/complexity.py::_lz76`),
  cara em CTs de 64KB. Já existia no v1 sem problema reportado (60k
  amostras rodaram); o benchmark sistemático da Fase 2.4 é o que agora
  quantifica o custo formalmente pela primeira vez.

**Total projetado (249,5h serial) fica ABAIXO do teto de 48h de CPU
paralelizada** do critério de aceite quando dividido pelo nº de cores via
`joblib.Parallel(n_jobs=-1)` (ex.: 8 cores ⇒ ~31h; 16 cores ⇒ ~15,6h) —
**não** dispara automaticamente a exigência de otimizar antes de prosseguir.
Ainda assim, decisão de investir em otimizar `_lz76` (ex.: numba, ou
substituir por um LZ76 O(n log n) baseado em suffix automaton) antes da
Fase 4 **fica para o Nycolas** — não é automática (mesmo critério já
registrado no docstring do script).

**Aceite:** custo total projetado conhecido — ✅ 249,5h serial / ~15-31h
paralelizado estimado, abaixo do teto de 48h.

## FASE 3 — Seletor v2 ✅ CONCLUÍDA (2026-08-21)

`src/features/selector.py` editado:
1. ✅ z-score fitado no treino (`train_mean`/`train_std` locais ao `fit()`);
   dp=0 (feature constante) usa dp seguro de 1.0 só para a divisão não gerar
   NaN/inf — como (x-mean)=0 para essa coluna inteira, o z-score fica
   identicamente 0, então o VT descarta de qualquer forma (testado sem
   warning de divisão por zero, `np.errstate` estrito).
2. ✅ VT aplicado sobre as features PADRONIZADAS (estágio 0), na prática
   dropando só constantes verdadeiras — corrige o viés de escala absoluta
   do v1 que descartava o histograma de bytes inteiro (ver docstring do
   módulo e `scripts/run_ablation_fs_60k.py`). Regressão testada
   explicitamente: feature de escala ~1/256 com sinal real sobrevive ao VT
   depois de padronizada, onde antes seria descartada por escala.
3. ✅ MI = corte de conveniência top-`top_k_mi` (default recalibrado para
   350, era 200 no v1), docstring do módulo explícito sobre não ter
   pretensão estatística.
4. ✅ mRMR define o conjunto final (`n_features_mrmr` default recalibrado
   para 150, era 100 no v1; aceita menos se sobreviverem menos ao corte).
5. ✅ Boruta diagnóstico (inalterado da Fase 0 — não filtra o resultado).
- ✅ **Sem RFE** no seletor do projeto — documentado explicitamente no
  docstring do módulo (a réplica E20 usa RFE *dentro do braço da réplica*,
  fora deste `LWCFeatureSelector`, exceção isolada e deliberada).
- `tests/test_selector.py`: 14 testes (eram 8) — 4 novos testes 4-classes
  (sinal/redundante/ruído) validando MI/mRMR/Boruta multiclasse (nunca
  exercitado além de binário neste projeto até agora) + 2 novos testes de
  regressão para a padronização (mantém sinal de escala pequena; não gera
  NaN/warning em feature constante).
- **Aceite:** ✅ testes verdes (14/14 no módulo, 215/215 no projeto
  inteiro), incluindo o multiclasse.

## FASE 4 — Dataset v2

### 4.1 Corpus de imagens ✅ CONCLUÍDA (2026-08-21)

`scripts/prepare_imagenet_subset.py` — baixado shard 0 (25.000 imagens) do
split de validação de `benjamin-paine/imagenet-1k-256x256` (HF); só esse
shard foi necessário (25.000 > 6.000 requeridas, evita baixar o shard 1 à
toa). 6.000 imagens selecionadas **via `CTRDRBG(seed=42, label="imagens_v2_selecao")`**
sem reposição, convertidas `PIL .convert("L")` → 65.536 bytes cada, salvas
em `data/raw/imagens_v2/img_v2_XXXXX.bin` + `manifest.json` (ids, índice de
origem no shard, sha256, licença — ImageNet Terms of Access, `license:
other`/`license_details: imagenet-agreement`, uso não-comercial de
pesquisa, já confirmado pelo Nycolas). 380MB em disco.

**Achado menor:** 5.999 SHA-256 únicos em 6.000 imagens (1 par de conteúdo
idêntico após conversão para tons de cinza) — os 6.000 ÍNDICES de origem no
shard são todos únicos (a seleção em si não tem bug); o par de conteúdo
idêntico é uma característica do dataset de origem (imagens quase-duplicadas
no ImageNet, artefato conhecido), não do pipeline de seleção — negligenciável
(0,02% do total).

### 4.2 Geração
- `scripts/generate_5class_v2.py`:
  - 300 chaves (`CtrDrbg`, offset 6000), 100 slots/chave.
  - Por slot: plaintext (80/20 texto/imagem, sorteio por amostra via DRBG),
    nonce = contador global 128 bits (Grain: 12 bytes LSB; Sparkle: zero-pad
    para 32 bytes nos MSB; ECB: ignora).
  - **6 linhas por slot:** Ascon, GIFT-COFB, Grain, Sparkle, AES-ECB e
    **PRNG-controle** (65.552 bytes de `CtrDrbg` com seed própria; recebe o
    `key_id` do slot como grupo sintético; colunas de nonce/pt marcadas n/a).
    Total: **180.000 amostras** (150k cifras + 30k PRNG), ~11,8 GB.
  - Colunas: as do v1 + `plaintext_source` (`corpus`/`imagem`/`n/a`) +
    `plaintext_sha256` (metadado p/ overlap; nunca feature).
  - CTs crus (Grain 65.544). Manifesto: SHA-256 dos binários, versão DRBG,
    resultado CAVP/KATs, mapeamentos de nonce.
- `data/processed/v2_folds.json`: partição única — 240/60 chaves (seed 42) +
  os 5 folds do GroupKFold (192/48). **Todos os caminhos leem deste arquivo**;
  assert de consistência em cada runner.

### 4.3 Validação
- `scripts/validate_5class_v2.py`: nonces únicos (ciente: Grain 96 bits, ECB
  e PRNG sem nonce), χ²/compressão (desvio **esperado** no ECB — reportar sem
  falhar), decrypt spot-check por algoritmo (100 amostras; pula PRNG),
  proporção 80/20 global e por split, encadeamento (mesma chave+pt nas 5
  linhas de cifra do slot), overlap de `plaintext_sha256` entre splits
  (relatório A7).
- **Aceite:** validação 100%; relatório salvo em `reports/v2/`.

## FASE 5 — Infraestrutura de relato e estatística

### 5.1 Função única de relato (obrigatória — regra de ouro 7)
- `src/eval/reporting.py::report_eval(run_id, caminho, modelo, braço, fold,
  y_true, y_pred, y_proba, key_ids, class_names, out_dir)`:
  1. imprime TODAS as métricas na hora (F1-macro, acurácia, acurácia
     balanceada, precisão/recall por classe, ECE top-label 10 bins, AUC OVR
     e por classe quando `y_proba` presente);
  2. imprime matriz de confusão como tabela legível no console;
  3. salva JSON **incremental** (um por run, append por chamada);
  4. salva PNG da matriz;
  5. **persiste por amostra:** `sample_id, key_id, fold, braço, y_true,
     y_pred, y_proba[]` em parquet — insumo obrigatório do F, do McNemar e
     da calibração.
- Refatorar os runners para usá-la; **proibido** print/save de métrica fora
  dela.

### 5.2 Poder a priori (antes de qualquer treino do v2)
- `scripts/power_analysis_v2.py`: simulação sob H₀ (bootstrap com n=24.000 do
  teste 4-classes e n=12.000 dos pares) → menor efeito detectável com 80% de
  poder a α=0,05. Salvar `reports/v2/power_analysis.md`. Citável no texto.

### 5.3 Arcabouço de decisão
- Família primária: **6 pares par-a-par, Caminho A, F1 com IC 95%, braço
  controlado** (decidido 2026-08-21; o braço cru repete as mesmas análises
  como caracterização do artefato de comprimento — resultado reportável).
  Exploratório: todo o resto, com BH-FDR
  (`statsmodels.stats.multitest`, q=0,05) aplicado na consolidação (Fase 11).
- Positivo sobrevivente ⇒ **replicação**: dataset novo só do par (chaves
  novas, offset 7000), teste único pré-especificado. Só então "achado".

## FASE 6 — Caminho A (CPU) — `scripts/run_v2_caminho_a.py`

1. **Modelos:** RF(500), SVM-RBF (busca 4×4 numa **subamostra de 24k
   estratificada por chave**, CV interna **group-aware** com folds de
   `v2_folds.json`; fit final com o par vencedor no fold completo),
   LinearSVC, XGBoost(500), LR. Sem Dummy.
2. **Stacking próprio:** `StackingClassifier` com `cv=` splits pré-computados
   por chave (nunca a CV interna default, que vaza entre chaves).
3. **Réplicas:** HKNNRF (KNN+RF); XGB-LGBM sobre **peso de Hamming**
   (dependência LightGBM); Transformer-E20 (filtro F + RFE → ~8 features
   NIST+entropia → encoder raso; RFE só aqui).
4. **Análises:** 4-classes (sem ECB/PRNG) + 6 pares binários + controle
   AES-ECB vs Ascon + **PRNG binário contra cada um dos 4** (grupos = key_id
   sintético) + braço `shuffled` (bytes de cada CT permutados via DRBG, seed
   por amostra; repete o 4-classes e os 6 pares; expectativa: features
   sequenciais colapsam, histograma sobrevive).
5. **Ablações:** key-holdout on/off — o braço "off" é split **aleatório por
   amostra** (ignora `key_id`), estratificado por classe, com os mesmos
   tamanhos de treino/teste do split por chave e seed 42; roda em dois
   recortes (4-classes e controle ECB — ECB é o controle positivo do método;
   expectativa nos íntegros = sem diferença); truncamento (cru × controlado;
   tag features sempre do cru); famílias (all / clássicas-307 / NIST /
   por-família / top-1).
6. **Curvas de aprendizado:** RF e LR com 30/60/120/240 chaves de treino,
   teste fixo — 4 pontos, por chave (nunca por amostra).
7. **Sanity `len_ct`:** uma rodada com `len_ct` incluído de propósito, braço
   cru ⇒ pares com Grain devem dar F1 > 0,95; senão, bug no encanamento.
   Rodada claramente rotulada `sanity`, fora das tabelas de resultado.
8. **Permutação:** nulo empírico (20×, esquemas by_key e within_key) como no
   v1, sobre o braço primário.
- **Aceite:** tudo via `report_eval`; predições por amostra persistidas;
  tabelas gerada com precisão/recall por classe; `reports/v2/caminho_a/`.

## FASE 7 — Caminhos B e C (GPU) — gate: smoke test

- `scripts/smoke_test_v2.py` (adaptar o existente): 500 amostras, 2 folds,
  3 épocas, 4 classes — mede tempo/VRAM por arquitetura antes das rodadas.
- **B (CNN1D):** CT completo, primeiro bloco kernel 8/stride 4, batch 8;
  braços cru E controlado (o truncamento importa aqui).
- **C (CNN2D):** co-ocorrência; **condicionamento — rodar as 3 variantes
  (×65536, log1p, padronização por canal) no smoke/1 fold, congelar a
  vencedora por `val_loss` e só ela vai à CV completa.** Réplica E05: reshape
  do **payload (65.536 bytes → 256×256)**, só subconjunto imagem, secundária.
- **HP search (C3):** 8–12 configs random (lr, filtros, blocos, dropout) ×
  **1 fold** por arquitetura; registrar tudo; se alguma config sair do acaso
  na validação, ela entra na CV completa.
- **3 seeds (C4):** só o modelo final (trainval completo → teste) roda com
  seeds {7, 107, 207}, e **só no braço controlado** (primário); o braço cru
  roda o final com seed 7 apenas (decidido 2026-08-21). CV com seed 7.
- Diagnóstico do latente: posto efetivo (SVD, variância explicada 95%) de
  cada `extract_latent` no teste — junto ao relatório do caminho.
- **Contagem de parâmetros** de cada arquitetura reportada no relatório do
  caminho (vale também para a Fase 8).
- **Aceite:** smoke verde antes de CV; braços e variantes documentados.

## FASE 8 — Caminho E (Transformer hierárquico)

- `src/models/transformer1d.py`: embedding de byte (+posicional) → janelas de
  1024 (64 janelas) → encoder local (2 camadas) → pooling por janela →
  encoder global (2 camadas) sobre 64 tokens (+posicional de janela) →
  `extract_latent()` (dim ~256) → cabeça.
- Contribuição própria (não é réplica do E20 — enquadramento correto no
  texto). Contagem de parâmetros reportada.
- Mesmo protocolo de B/C: smoke → HP search 1 fold → CV → final 3 seeds.
- **Aceite:** treina no orçamento medido pelo smoke; latente persistido.

## FASE 9 — Caminho D (híbrido, 4 representações)

- Estender `HybridExtractor`: [~400D clássicas | 512 CNN1D | 128 CNN2D |
  ~256 Transformer]. Latentes das redes com seed principal (7). Seletor
  (mi_pool/mrmr ampliados) dentro do fold → RF/XGBoost.
- **Aceite:** dimensões conferidas por assert; mesmo protocolo de relato.

## FASE 10 — Caminho F (meta-classificador)

- Insumo: parquet de predições **out-of-fold** da Fase 5 (nunca refits).
  Assert: partição de folds idêntica entre A–E.
- Calibração (B6): Platt/isotônica fitada na validação de cada fold —
  **dependência dura** para LinearSVC/SVM (sem `predict_proba` nativo).
  ECE antes/depois reportado.
- Meta-modelo: LR sobre o vetor de probabilidades concatenado; CV por chave;
  teste final com modelos-base treinados no trainval.
- Regra registrada: F "significativo" com todos os bases no acaso ⇒
  investigar vazamento antes de reportar como achado.
- **Aceite:** matriz OOF reconstruída só do parquet (prova de auditabilidade).

## FASE 11 — Consolidação

1. Aplicar BH-FDR à tabela exploratória completa; tabela final com p brutos e
   q-values.
2. Estratificação de erro (por chave, por `plaintext_source`) para qualquer
   resultado acima do acaso.
3. Consolidado geral (estilo `AUC_ROC_consolidado.md` do v1) + parecer:
   família primária respondida, exploratórios sobreviventes, replicações
   necessárias.
4. Se houver positivo: rodar a replicação (§5.3) antes de qualquer texto.
5. Proposta Zenodo por escrito para o orientador (dataset + manifesto).

---

## §R — Roteiro operacional (o experimento de ponta a ponta)

1. **Fundações (local):** Fases 0–3 — wrappers validados por KAT, DRBG por
   CAVP, features por vetores NIST, seletor por teste multiclasse. Nada de
   dataset antes de tudo verde.
2. **Dataset (local):** imagens preparadas → geração (180k) → validação →
   `v2_folds.json` → extração de features (após o gate do benchmark) →
   **poder a priori calculado e escrito** → upload (Kaggle + Drive).
3. **Caminho A (local):** sanity checks primeiro (`len_ct`, permutação);
   depois a rodada primária (braço controlado), controles, ablações, curvas.
   **Ao fim desta etapa a resposta primária da dissertação já existe** —
   B–F verificam se ela depende da representação.
4. **GPU (Kaggle + Colab, paralelo):** smoke tests → HP search →
   CV → finais 3 seeds. Download de artefatos ao fim de CADA sessão.
5. **Fusões (local):** latentes baixados → D; matriz OOF → calibração → F.
6. **Veredito (local):** tabela primária sem correção + exploratório com
   FDR + diagnósticos; positivo sobrevivente ⇒ replicação (offset 7000)
   antes de virar achado; consolidado final + proposta Zenodo.

Regras de rota pré-definidas: benchmark estoura → otimizar antes de gerar;
smoke do E não cabe em T4 → A100; config de HP sai do acaso → entra na CV
completa; positivo sobrevive ao FDR → replicação obrigatória.

## §E — Matriz de execução por plataforma (decidida 2026-08-21)

| Plataforma | Capacidade | O que roda |
|---|---|---|
| **Local (CPU/MSVC)** | ilimitado em calendário | Fases 0–6 inteiras: wrappers (os `.pyd` são MSVC — só compilam aqui), CTR_DRBG, features + benchmark, seletor, **geração do dataset**, validação, **extração de features** (paralelizada), **Caminho A completo** (com todos os braços/ablações/controles), **Caminho F**, treino RF/XGB do D, consolidação/FDR (Fase 11) |
| **Kaggle (T4 grátis, ~30h/sem, resume)** | ~120h/mês | **Caminhos B e C completos** (smoke → HP search → CV → finais), variantes de condicionamento da CNN2D, réplica E05, **extração de latentes** de B/C/E para o D (inferência). Dataset sobe como Kaggle Dataset (~11,8 GB; molde do v1) |
| **Colab Pro (100 CU/mês)** | ~50h T4 **ou** ~7,5h A100 | **Caminho E**: smoke e HP search em **T4**; CV + finais em **A100 somente se** o smoke mostrar que T4 não comporta — senão E inteiro fica em T4/Kaggle e as unidades viram reserva |

**Fluxo de dados:**
1. Dataset gerado local → upload único (Kaggle Dataset + Drive para o Colab).
2. Features clássicas extraídas localmente → sobem junto (parquet).
3. **Ao fim de CADA sessão de GPU:** baixar `reports/v2/` da sessão
   (JSON + parquet de predições + checkpoints) para o repositório local,
   **antes** de encerrar. Regra dura — o v1 perdeu os artefatos de B/C
   exatamente por não ter esse passo; não se repete.
4. Latentes (B/C/E) baixados → D treina local.

**Sequência de calendário (estimativa):** semanas 1–3 local (Fases 0–5);
semana 3–4 Caminho A local + upload do dataset; semanas 4–6 Kaggle (B, C) e
Colab (E) em paralelo; semana 6+ D, F e consolidação local. Colab Pro ativo
por 1–2 meses.

## §P — PENDENTES (não implementar sem decisão do Nycolas)

| # | Pendência | Efeito enquanto aberta |
|---|---|---|
| P1 | ✅ **RESOLVIDO (2026-08-21):** braço **controlado** é o primário; o braço cru roda as mesmas análises como **resultado reportável do artefato** — narrativa: "sem normalização de comprimento, o Grain é identificável trivialmente pelo tamanho da tag; controlado o comprimento, a separabilidade desaparece (ou persiste — e aí é conteúdo)" | — |
| P2 | TOST (teste de equivalência, margem δ≈1 p.p.) além do IC | Sem TOST, conclusão fica "IC cobre o acaso + poder X" |
| P3 | Bootstrap por cluster de chave (reamostrar chaves, não amostras) | IC atual (i.i.d.) pode subestimar sob sinal correlacionado a chave |
| P4 | Baseline de features aleatórias vs. mRMR (McNemar) | Validação do seletor fica sem esse braço |
| P5 | **Teto conhecido (2026-08-21): Colab Pro, 100 unidades/mês** (≈7–8h A100, ≈20h V100 ou ≈50–55h T4). Estratégia: Kaggle T4 grátis (~30h/semana, infra de resume do v1) para B/C; Colab T4 para HP search/overflow; A100 reservada ao Caminho E se o smoke mostrar necessidade; nenhuma unidade antes do smoke. **Ainda pendente: ordem de corte** (proposta, não confirmada: HP search extra → 3ª seed → réplica E05 → F → E; família primária e controles intocáveis) | Fases 7–10 dimensionadas pelo smoke antes de gastar unidades |
| P6 | Zenodo — depende da conversa com o orientador (C6 aprovou só *propor*) | Fase 11.5 fica em rascunho |

## Critérios de aceite globais

- `pytest tests/ -v` verde ao fim de cada fase.
- Nenhuma métrica impressa/salva fora de `report_eval`.
- Nenhum RNG NumPy em geração de material criptográfico.
- Todo artefato de resultado em `reports/v2/` com JSON + parquet por amostra.
- Qualquer desvio deste documento: registrado por escrito antes de codar.
