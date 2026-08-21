# 8. Achados críticos e pendências

Lista priorizada. Itens 1–2 são os que mais valem a atenção do usuário;
os demais são discrepâncias de documentação/código encontradas durante a
leitura linha a linha, úteis para limpeza mas não urgentes.

## 1. Resultados dos Caminhos B, C, D existem mas não estão sincronizados no repositório

**O que se verificou:** `dissertacao/resultados.tex` (2026-07-07) já contém
uma seção de resultados completa e redigida para os 4 Caminhos, com números
específicos por modo/classificador. Cruzando com artefatos brutos:

- Caminho A: artefato bruto **está** neste repositório
  (`reports/keyholdout_2class_60k_v1_cv/`) — consistente.
- Caminho D: **resolvido (Fase 0 do plano v2, 2026-08-21)** — copiado de
  `C:\Users\nycol\Downloads\resultados_caminhoD_final\
  reports\keyholdout_2class_60k_v1_hybrid\` para
  `reports/keyholdout_2class_60k_v1_hybrid/` neste repositório
  (`cv_results.json`, `final_results.json`, `_cv_cache.pkl`,
  `_final_cache.pkl`, `comparison_table.md`, `mcnemar_table.md`); os
  números batem exatamente com o texto da dissertação. `reports/` é
  gitignored, então o artefato fica local — não versionado, mas presente.
- Caminhos B e C: artefato bruto **ainda não localizado** em nenhum lugar
  verificado (nem no repositório, nem em `Downloads/` até 5 níveis de
  profundidade — reconfirmado ao sincronizar o D). O texto da dissertação
  cita como fonte um arquivo `RESULTADOS_FINAIS_4_CAMINHOS.md` que também
  não foi encontrado.

**Recomendação:** localizar (provavelmente no ambiente Kaggle onde os
treinos rodaram, ou em outro backup local) e copiar para
`reports/keyholdout_2class_60k_v1_cnn/` os artefatos de B e C. Sem isso, o
repositório de código não sustenta sozinho os números que já estão na
dissertação — qualquer tentativa de reproduzir ou auditar os resultados de
B/C esbarra em diretórios vazios (`ckpts/`, `confusion_matrices/`, sem
`cv_results.json`). Nota: isso é sobre o experimento v1 (2 classes); o
plano v2 (`docs/plano_experimento_v2/`) gera Caminhos B/C novos do zero,
então essa lacuna não bloqueia o v2 — só a reprodutibilidade retroativa
do v1.

## 2. Mudança metodológica no seletor de features — ✅ commitada (Fase 0, 2026-08-21)

Boruta deixou de ser o filtro final do pipeline de seleção e virou
diagnóstico puro (o conjunto final passou a ser sempre a saída do mRMR).
Motivo: no experimento principal, Boruta colapsava para 1 feature em 2/5
folds. Testes já atualizados e alinhados (`tests/test_selector.py`).
Commit `5b46413` — `src/features/selector.py`, `src/models/classical.py`,
`scripts/run_experiment_60k_cv.py`, `scripts/run_hybrid_60k.py`,
`scripts/run_vigenere_cv.py`, `scripts/run_vigenere_random_cv.py`,
`tests/test_selector.py`.

Detalhe completo em [02_features_e_selecao.md](02_features_e_selecao.md).

## 3. `CLAUDE.md` tem descrições desatualizadas

Corrigido nesta sessão (ver diff do arquivo):

- `src/models/hybrid.py` estava marcado como "❌ a implementar" — já existe
  (610 linhas, `HybridConfig`/`HybridExtractor` completos).
- Descrição da CNN2D não mencionava a representação canônica atual
  (co-ocorrência de bigramas 256×256, `bytes_to_cooccurrence`) — só citava
  o reshape linear legado.
- Lista de modelos do Caminho A ("RF/SVM/XGBoost") omitia LinearSVC e LR,
  que fazem parte do conjunto vivo de modelos treinados no protocolo 60k.
- Comando `validate_all_datasets.py` descrito como fazendo checks (χ²,
  nonces, compressão, decrypt) que o script real não implementa — o script
  real só verifica existência de arquivo em 2 datasets legados hardcoded.

## 4. `CONTEXTO_ARTIGO.md` — snapshot de 2026-06-04, parcialmente superado

Adicionado um banner no topo do arquivo apontando para
`docs/analise_completa/`. Pontos específicos que ficaram desatualizados com
o tempo (não reescritos in-loco, para preservar o documento como registro
histórico daquele momento):

- §9.2 e o aviso de status no topo afirmam que B/C/D não foram executados
  no 60k — corrigido em [07_resultados.md](07_resultados.md) §7.2–7.3.
- §9.5 afirma "AUC/ROC NÃO é calculado em nenhum pipeline" — não é mais
  verdade: `compute_auc_roc()` foi adicionado a `src/eval/metrics.py` e
  `scripts/compute_auc_all_paths.py` foi criado (ambos no commit `cf91290`,
  2026-06-29, depois da geração daquele documento).
- Não menciona a ablação do seletor (`run_ablation_fs_60k.py`, 2026-08-12)
  nem a mudança de semântica do Boruta — ambos posteriores.
- Não menciona que a redação da dissertação (`dissertacao/*.tex`) já
  começou — a seção 16 do documento ("TEXTOS JÁ ESCRITOS") afirma que não
  existe nenhum rascunho de artigo, o que era verdade em junho e não é mais.

## 5. `docs/cnn_caminhos_b_c.md` — uma linha de status corrigida

A frase "a execução completa no dataset 60k ainda não gerou relatórios"
(seção 6, "Status e pendências") foi atualizada para refletir que a
execução ocorreu, com nota sobre a mesma questão de sincronização do item 1.

## 6. Inconsistências menores de código (não bloqueiam nada, mas valem registro)

| Item | Onde | Detalhe |
|---|---|---|
| Nome de arquivo desatualizado | `scripts/generate_2class_50k.py` | Gera o dataset `_60k_`, não `_50k_` — a config interna foi editada in-place |
| Dataset órfão | `data/processed/keyholdout_2class_50k_v1.parquet` | Nenhum script atual o regenera; só existe como artefato herdado |
| Reuso de `key_seed_offset` | `generate_3class_control.py`/`generate_vigenere_control.py` (offset 3000); `generate_3class_repetitive.py`/`generate_vigenere_64k.py` (offset 4000) | Datasets distintos acabam com as mesmas chaves por coincidência de offset — não documentado, não é vazamento real (datasets nunca combinados no mesmo experimento) |
| Código duplicado | `validate_2class_50k.py` vs. `validate_2class_60k.py` | Praticamente cópia trocando só `DATASET_ID` e totais esperados |
| Hiperparâmetro de SVM inconsistente | `run_vigenere_random_cv.py` (fixo C=10/gamma=scale) vs. `run_experiment_60k_cv.py`/`run_vigenere_cv.py` (GridSearchCV) | Não documentado por que esse script foge do padrão |
| Constante com dois valores | `MAX_LEN_B` — `run_cnn_experiments_60k.py`=65552 vs. `src/models/hybrid.py`/`run_hybrid_60k.py`=4096 (só valor de referência para log, o Caminho B real não é treinado em `run_hybrid_60k.py`) | Pode confundir leitura cruzada dos dois arquivos |
| Comentário desatualizado | `scripts/generate_vigenere_control.py` (legado) | Docstring diz "Vigenère usa apenas key[:3]" mas o wrapper real usa `key[:4]` com máscara de 25 bits — o dataset gerado está correto, só o comentário está errado |

## 7. Estado da redação da dissertação (contexto, não é um "bug" de código)

`dissertacao/` (LaTeX, template AbNTeX2/IME) já tem: introdução,
fundamentação teórica, trabalhos relacionados, metodologia, resultados
(completo, com os números dos 4 Caminhos + controle + discussão de validade)
e conclusão — 1.509 linhas de `.tex` no total. `dissertacao.zip` no
repositório é um backup do mesmo conteúdo. Isso não é uma pendência de
código, mas é informação relevante para calibrar quanto do "o que falta"
listado em `CONTEXTO_ARTIGO.md` §16 (que dizia "nenhum rascunho de artigo
existe") já não se aplica mais.

## 8. O que NÃO foi verificado nesta análise (limitações desta rodada)

- O conteúdo completo dos capítulos `.tex` da dissertação não foi lido
  linha a linha (só `resultados.tex` e `dados.tex`, por serem os que mais
  diretamente cruzam com código/resultados). `metodologia.tex`,
  `fundamentacao.tex`, `trabalhos-relacionados.tex`, `introducao.tex` e
  `conclusao.tex` não foram auditados quanto a consistência com o código.
- Os artefatos brutos dos Caminhos B e C não foram encontrados nesta busca
  (limitada a este repositório e a até ~3 níveis dentro de
  `C:\Users\nycol\Downloads\`); podem existir em outro local (ex.: ainda só
  no ambiente Kaggle, ou em outra pasta não coberta pela busca).
- Não foi executado `pytest` nesta sessão para confirmar que os 130 testes
  passam com as mudanças não commitadas do seletor — a análise é de leitura
  de código, não de execução.
