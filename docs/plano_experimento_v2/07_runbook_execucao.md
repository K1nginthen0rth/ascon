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
pytest tests/ -q          # esperado: 229 passed
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

**Este é o gargalo.** 2,43 s/amostra medidos; 180k amostras = ~121h
serial. Rode em shards paralelos — processos independentes, retomáveis
(um chunk pronto é pulado na retomada).

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

---

## Etapa 5 — Caminhos B/C/E (GPU: Kaggle T4 / Colab Pro)

**Gate: smoke test antes de qualquer CV.** O smoke mede tempo/época,
VRAM e parâmetros, e extrapola o custo da CV completa — é o número que
decide se cabe no orçamento de GPU.

```bash
python scripts/run_v2_caminhos_bce.py --path B --mode smoke --branch controlado
python scripts/run_v2_caminhos_bce.py --path C --mode smoke --branch controlado
python scripts/run_v2_caminhos_bce.py --path E --mode smoke --branch controlado
```

Depois, por caminho:

```bash
python scripts/run_v2_caminhos_bce.py --path B --mode hpsearch --branch controlado --n-configs 10
python scripts/run_v2_caminhos_bce.py --path B --mode cv       --branch controlado --hp-json best_B.json
python scripts/run_v2_caminhos_bce.py --path B --mode final    --branch controlado --hp-json best_B.json
```

**Memória:** um fold de treino completo são ~5,0 GB só de ciphertexts em
RAM (76.800 × 65KB). Em Kaggle (13GB) use `--max-train-samples` para
limitar — o valor usado fica registrado no relatório.

**Regra dura de sessão de GPU:** baixe os artefatos
(`reports/v2/caminho_*/`, `latents_*.npy` e `*_index.parquet`) **antes
de fechar a sessão**. Os artefatos dos Caminhos B/C do v1 foram perdidos
exatamente assim.

O braço `cru` só é necessário para B (o truncamento afeta o padding
posicional da CNN1D); C e E podem ficar só no `controlado`.

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

Depende das predições out-of-fold de A–E (modo `cv` de cada um).

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
BH-FDR (q=0,05) aplicado só no exploratório.

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
