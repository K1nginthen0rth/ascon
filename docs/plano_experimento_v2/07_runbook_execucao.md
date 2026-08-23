# 7. Runbook de execução — do dataset ao consolidado

Sequência exata de comandos para reproduzir o experimento v2 inteiro.
Cada etapa diz **onde roda** (local/Kaggle/Colab), **quanto custa** e
**o que precisa estar pronto antes**. Números de custo são medidos, não
estimados, exceto onde marcado.

> **Antes de uma rodada oficial:** limpe `reports/v2/` e
> `data/interim/features_v2_*`. Os `.jsonl` de métrica são append-only
> (proposital: sobrevivem a queda de sessão), e a consolidação deduplica
> por timestamp — mas partir do limpo elimina qualquer dúvida.

---

## Etapa 0 — Pré-requisitos (uma vez)

```bash
# extensões C (MSVC): Ascon, GIFT-COFB, Grain, Schwaemm
build_cffi.bat && build_gift_cofb.bat && build_grain.bat && build_sparkle.bat
pytest tests/ -q          # esperado: 243 passed
```

Repos de referência C (`ascon-c/`, `gift-cofb/`, `grain-128aead/`,
`sparkle/`) são gitignored — se o ambiente for recriado, veja as fontes
em `06_implementacao_passo_a_passo.md` Fase 1.

---

## Etapa 1 — Dataset (local, ~45 min) ✅ JÁ EXECUTADO

```bash
python scripts/prepare_imagenet_subset.py        # 6.000 imagens, ~10 min, 380MB
python scripts/generate_5class_v2.py --keys-per-batch 10   # 180k amostras, ~41 min, 11,8GB
python scripts/validate_5class_v2.py             # esperado: VEREDICTO PASS
```

Produz `data/processed/keyholdout_5class_v2.parquet`,
`..._manifest.json`, `v2_folds.json` (partição canônica — **todos os
caminhos leem dela**) e as chaves em `data/interim/` (nunca versionar).

---

## Etapa 2 — Poder a priori (local, ~8 min) ✅ JÁ EXECUTADO

```bash
python scripts/power_analysis_v2.py
```

Resultado registrado: MDE de **+1,02 p.p.** (4 classes, n=24.000) e
**+1,27 p.p.** (par binário, n=12.000) a 80% de poder, α=0,05.

---

## Etapa 3 — Extração de features (local, ~20h com 6 shards)

**Este é o gargalo.** **~2,2 s/amostra** medidos em ciphertexts reais do
v2; 180k amostras = **~110h serial**, ou **~18-20h com 6 shards**. Rode em
shards paralelos — processos independentes, retomáveis (um chunk pronto é
pulado na retomada).

> Sobre o número: medições isoladas de uma amostra "quente" dão 1,69 s
> (só o custo de CPU das famílias); no laço real, com leitura do parquet,
> a média em CTs do v2 é 2,21 s. Use **2,2 s** para planejar — é a que
> inclui I/O. O relatório `reports/v2/benchmark_extracao.md` é
> PRÉ-otimização (249,5h) e está obsoleto; regere com
> `scripts/benchmark_extraction_v2.py` se precisar dele.

```bash
# braço primário
for i in 0 1 2 3 4 5; do
  python scripts/extract_features_v2.py --branch controlado --shard $i --n-shards 6 &
done; wait
python scripts/extract_features_v2.py --branch controlado --consolidate

# braço cru (análise do artefato de comprimento do Grain)
for i in 0 1 2 3 4 5; do
  python scripts/extract_features_v2.py --branch cru --shard $i --n-shards 6 &
done; wait
python scripts/extract_features_v2.py --branch cru --consolidate

# controle negativo (bytes embaralhados) — só se for rodar esse braço
for i in 0 1 2 3 4 5; do
  python scripts/extract_features_v2.py --branch shuffled --shard $i --n-shards 6 &
done; wait
python scripts/extract_features_v2.py --branch shuffled --consolidate
```

Ajuste `--n-shards` ao nº de núcleos. Cada shard usa ~300MB
(streaming interno por `sub_batch`), então 6 shards ≈ 1,8GB.

---

## Etapa 4 — Caminho A (local, CPU)

O seletor `pleno` (mRMR 150 + Boruta 100 iterações sobre 641 features)
domina o tempo de cada fold. Rode a análise primária primeiro.

```bash
# FAMÍLIA PRIMÁRIA — é ela que responde à pergunta da dissertação
python scripts/run_v2_caminho_a.py --analysis pairs   --branch controlado
python scripts/run_v2_caminho_a.py --analysis 4class  --branch controlado

# controles
python scripts/run_v2_caminho_a.py --analysis ecb_control  --branch controlado
python scripts/run_v2_caminho_a.py --analysis prng_control --branch controlado

# sanity de encanamento (fora das tabelas de resultado)
python scripts/run_v2_caminho_a.py --analysis sanity_lenct --branch controlado

# curvas de aprendizado (responde "faltaram dados?")
python scripts/run_v2_caminho_a.py --analysis learning_curve --branch controlado

# ABLAÇÕES
python scripts/run_v2_caminho_a.py --analysis 4class      --branch cru          # truncamento
python scripts/run_v2_caminho_a.py --analysis pairs       --branch cru
python scripts/run_v2_caminho_a.py --analysis 4class      --branch shuffled     # controle negativo
python scripts/run_v2_caminho_a.py --analysis pairs       --branch shuffled
python scripts/run_v2_caminho_a.py --analysis 4class      --branch controlado --no-keyholdout
python scripts/run_v2_caminho_a.py --analysis ecb_control --branch controlado --no-keyholdout

# ablação de famílias (all/clássicas/NIST/por-família/top-1) e permutação
python scripts/run_v2_caminho_a.py --analysis family_ablation --branch controlado
python scripts/run_v2_caminho_a.py --analysis permutation     --branch controlado
```

A ablação `--no-keyholdout` roda nos **dois recortes** (4 classes e o
controle ECB) de propósito: nos 4 algoritmos íntegros não há o que
memorizar entre amostras da mesma chave (nonce único por amostra), então
o esperado é *nenhuma* diferença; quem garante que o método de ablação
detecta inflação quando ela existe é o AES-ECB, cujo codebook é
determinístico por chave. Sem o ECB, o silêncio nos 4 seria ambíguo
entre "não há inflação" e "o teste não tem poder".

`--selector-preset rapido` existe para exploração — **nunca** para o
resultado oficial.

**Stacking + 3 réplicas da literatura** (HKNNRF, XGB-LGBM/Hamming,
Transformer-E20) rodam automaticamente dentro de `4class`/`pairs` (é lá
que sustentam a comparação com a RSL) — `--skip-replicas` desliga para
exploração rápida, nunca no resultado oficial. `ecb_control`/
`prng_control` já vêm com replicas desligadas por padrão (são controles
do método, não parte da comparação entre algoritmos).

---

## Etapa 5 — Caminhos B/C/E (GPU: Kaggle T4 / Colab Pro)

**Gate: smoke test antes de qualquer CV.** O smoke mede tempo/época,
VRAM e parâmetros, e extrapola o custo da CV completa — é o número que
decide se cabe no orçamento de GPU.

```bash
python scripts/run_v2_caminhos_bce.py --path B --mode smoke --branch controlado
python scripts/run_v2_caminhos_bce.py --path E --mode smoke --branch controlado

# Path C: --mode smoke roda as 4 variantes de condicionamento (sum1/raw/
# log1p/standardized) automaticamente e imprime a vencedora por val_loss
# — ignora --cond neste modo.
python scripts/run_v2_caminhos_bce.py --path C --mode smoke --branch controlado
```

Depois, por caminho (`--cond` só tem efeito em C; default `sum1`):

```bash
python scripts/run_v2_caminhos_bce.py --path B --mode hpsearch --branch controlado --n-configs 10
python scripts/run_v2_caminhos_bce.py --path B --mode cv       --branch controlado --hp-json best_B.json
python scripts/run_v2_caminhos_bce.py --path B --mode final    --branch controlado --hp-json best_B.json

python scripts/run_v2_caminhos_bce.py --path C --mode cv    --branch controlado --cond log1p
python scripts/run_v2_caminhos_bce.py --path C --mode final --branch controlado --cond log1p

# Réplica E05 (secundária) — ignora --mode, roda CV+final de uma vez,
# só no subconjunto plaintext_source=imagem, sem alimentar o Caminho D.
python scripts/run_v2_caminhos_bce.py --path E05 --mode cv --branch controlado
```

**Memória:** um fold de treino completo são ~5,0 GB só de ciphertexts em
RAM (76.800 × 65KB). Em Kaggle (13GB) use `--max-train-samples` para
limitar — o valor usado fica registrado no relatório.

**Regra dura de sessão de GPU:** baixe os artefatos
(`reports/v2/caminho_*/`, `latents_*.npy` e `*_index.parquet`) **antes
de fechar a sessão**. Os artefatos dos Caminhos B/C do v1 foram perdidos
exatamente assim.

O braço `cru` só é necessário para **B** (o truncamento afeta o padding
posicional da CNN1D). **C** pode ficar só no `controlado`. **E é idêntico
nos dois braços** — o Transformer trunca para 65.536 em qualquer caso
(`max_len` default), então `--branch cru` para E não gera informação nova;
não rode.

---

## Etapa 6 — Caminho D (híbrido)

Depende dos latentes de B/C/E já extraídos (etapa 5, modo `cv`).

```bash
python scripts/run_v2_caminho_d.py --branch controlado --paths B,C,E
```

Roda com as representações disponíveis e registra quais entraram — se um
caminho profundo ainda não rodou, ele avisa e segue sem aquela
representação em vez de falhar.

---

## Etapa 7 — Caminho F (meta-classificador)

Depende de **duas** coisas de A–E: as predições out-of-fold (modo `cv`, que treinam o meta-modelo) **e** as predições `final` (modo `final`, trainval→teste, onde o F é avaliado). Sem as duas ele para com erro explícito dizendo qual falta.

```bash
python scripts/run_v2_caminho_f.py --branch controlado
```

Monta a matriz OOF **só** dos parquets de predição de `report_eval`
(nunca refits), confere que nenhuma chave de teste vazou, calibra por
isotônica e reporta ECE antes/depois. Se F ficar acima do acaso com
todos os modelos-base no acaso, imprime a bandeira de investigação de
vazamento — isso é bandeira, não achado.

---

## Etapa 8 — Consolidação

```bash
python scripts/consolidate_v2.py
```

Gera `reports/v2/consolidado_v2.md` e `.csv`: família primária (6 pares,
Caminho A, braço controlado, fold final) separada do exploratório, com
BH-FDR (q=0,05) aplicado só no exploratório. Também reconstrói, a partir
dos parquets de predição já salvos: McNemar pareado + Bonferroni entre
todos os pares de modelos de cada comparação primária
(`consolidado_v2_mcnemar.csv`), e estratificação de erro por `key_id`/
`plaintext_source` para todo resultado acima do acaso
(`consolidado_v2_estratificacao.csv`) — uma bandeira em
`plaintext_source` ("separa melhor em imagens") é sinal de artefato, não
achado sobre o algoritmo.

**Leitura do resultado:**
- Positivo (primário, ou exploratório que sobrevive ao FDR) ⇒ exige
  **replicação** com chaves novas (offset 7000) e teste único
  pré-especificado antes de virar achado.
- Nulo ⇒ leia junto do poder a priori: o desenho detecta ~1 p.p. acima
  do acaso com 80% de poder. Efeitos menores não são detectáveis nesta
  escala — limitação declarada, não prova de ausência.

---

## Pendências que exigem decisão do Nycolas

Ver `06_implementacao_passo_a_passo.md` §P. Nenhuma delas está
implementada, de propósito: TOST, bootstrap por cluster de chave,
baseline de features aleatórias, ordem de corte se o orçamento de GPU
apertar, e Zenodo (depende de conversa com o orientador).
