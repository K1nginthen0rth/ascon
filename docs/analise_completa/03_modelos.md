# 3. Modelos (`src/models/`) e métricas (`src/eval/`)

## 3.1 Caminho A — `classical.py` (277 linhas)

`ClassicalPipeline.run(features_df)` — pipeline completo dentro de um único
split (o CV 5-fold que o protocolo 60k usa é implementado *fora* desta
classe, diretamente em `scripts/run_experiment_60k_cv.py`; `classical.py` é
usado por scripts de key-holdout simples como `run_experiment_2class.py` e é
a peça reutilizada — via `LWCFeatureSelector` — dentro do loop de CV dos
scripts vivos).

Passos: separa `train/val/test` pela coluna `split` → `_verify_no_leakage`
(garante que `len_pt/len_ad/len_ct` não estão entre as features) →
verificação explícita de não sobreposição de `key_id` entre splits (levanta
`ValueError` citando a interseção exata se houver vazamento) → fit do
`LWCFeatureSelector` só no treino → `StandardScaler` (só para SVM, fit só no
treino) → treina 4 modelos e computa métricas via `compute_metrics`.

Modelos default (`_build_models`, seed=7):

| Modelo | Hiperparâmetros |
|---|---|
| Dummy | `strategy="stratified"` — baseline de chance |
| RF | `n_estimators=500, class_weight=balanced` |
| SVM | `kernel=rbf, C=1.0, gamma=scale, class_weight=balanced, probability=True` |
| XGBoost | `n_estimators=500, max_depth=6, lr=0.1, tree_method=hist` |

**Nota:** o conjunto real de modelos treinados no protocolo vivo (60k) é
maior — `run_experiment_60k_cv.py` adiciona `LinearSVC` e roda o SVM via
`GridSearchCV`, e `run_extra_lr_60k.py` acrescenta `LogisticRegression`
reaproveitando os folds já computados. `classical.py` propriamente dito só
cobre Dummy/RF/SVM/XGBoost.

## 3.2 Caminho B — CNN 1D (`cnn1d.py`, 110 linhas + `cnn_trainer.py`, 226 linhas)

`CiphertextCNN1D`: `Embedding(256, embed_dim=32)` → 3 blocos
`[Conv1D→BatchNorm1D→ReLU→MaxPool1D(2)]` (filtros 128→256→512) →
`AdaptiveAvgPool1d(1)` (= `extract_latent()`, 512D) → `Dropout(0.3)` →
`Linear(512→n_classes)`.

Bytes (0–255) são tratados como símbolos categóricos via embedding
aprendível — decisão de design explícita para não impor ordem métrica
artificial entre valores de byte.

**Ajuste para sequências longas** (commit `25dcf24`, "atualização padding",
2026-06-20): quando `max_len >= 16384`, o primeiro bloco conv usa
`kernel=8, stride=4` em vez de `kernel=3, stride=1` — reduz a sequência por
4× já na entrada, necessário para tornar viável processar os 65.552 bytes do
CT completo (com stride 1, o custo seria proibitivo). Sequências curtas
mantêm o comportamento original para não invalidar resultados antigos.

`CNN1DTrainer` (protocolo mais antigo, `max_len=1040` default — cobre PT até
1024B, usado pelos scripts legados) implementa o loop de treino:
Adam(lr=1e-3), CrossEntropyLoss, early stopping em `val_loss` (paciência 5),
inferência em batches para evitar OOM. O treino de produção no 60k usa a
infraestrutura mais nova em `hybrid.py` (`train_cnn`/`train_cnn_fixed`), não
esta classe diretamente — ver §3.4.

## 3.3 Caminho C — CNN 2D (`cnn2d.py`, 70 linhas + `ciphertext_to_image.py`, 79 linhas)

`CiphertextCNN2D`: 3 blocos `[Conv2D 3×3→BN→ReLU→MaxPool(2)]` (canais
32→64→128) → `AdaptiveAvgPool2d(1)` (= `extract_latent()`, 128D) →
`Dropout(0.3)` → `Linear(128→n_classes)`. Treinada do zero — sem pesos
ImageNet, justificado no docstring (features de fotos naturais não têm
correspondência em dados que se aproximam de ruído).

**Representação de entrada — duas versões coexistem no código:**

| Função | Representação | Uso |
|---|---|---|
| `bytes_to_cooccurrence(ct)` | Mapa de co-ocorrência de bigramas 256×256: `pixel[i,j] = freq(byte i seguido de byte j)`, via `np.bincount` (O(n), sem loop Python), CT completo | **Canônica/atual** — Caminho C vivo |
| `ciphertext_to_image(ct, 32)` | Reshape linear 32×32, normalizado `/255` | **Legada** — mantida só para os experimentos antigos (`cnn2d_trainer.py`, `run_cnn2d_experiments.py`) |

A co-ocorrência só relaciona bytes de fato consecutivos (adjacência real);
o reshape linear antigo impõe adjacência vertical artificial (bytes
separados por 32 posições viram "vizinhos" na imagem sem relação real) —
limitação documentada explicitamente no docstring do módulo.

`cnn2d_trainer.py` é o trainer do protocolo **legado** (imagem 32×32,
key-holdout simples sem CV) — caminho de código paralelo ao usado hoje, que
passa pela infraestrutura de `hybrid.py`.

## 3.4 Caminho D — Híbrido (`hybrid.py`, 610 linhas)

`HybridExtractor` combina os latentes de CNN1D e CNN2D com as 307 features
clássicas: `[307D | latent CNN1D 512D | latent CNN2D 128D] = 947D`.

Infraestrutura pensada para viabilizar treino de horas em instâncias
possivelmente preemptíveis (Kaggle/GPU spot):

- **Datasets lazy** (`CiphertextSeqDataset`, `CiphertextCoocDataset`):
  conversão bytes→tensor acontece em `__getitem__`, não de uma vez —
  materializar 48 mil CTs de 64KB (ou 48 mil matrizes 256×256 float32) de
  antemão estouraria RAM.
- **Checkpoint por época** (`_save_ckpt`/`_load_ckpt`): salva
  `model_state, optimizer_state, rng_state, best_val, best_epoch` a cada
  época; `resume=True` retoma do último checkpoint, inclusive restaurando o
  estado do RNG do PyTorch (com correção de compatibilidade de device — ver
  commit `0878206`, "fix RNG state compatível com qualquer device no
  resume").
- MLflow opcional, com fallback silencioso se a lib não estiver instalada.
- `train_cnn()` (com early stopping, usado na CV) e `train_cnn_fixed()` (sem
  early stopping, épocas fixas, usado no modelo final treinado no
  trainval completo).

**Constantes de comprimento** (`MAX_LEN_B=4096`, `MAX_LEN_D_CNN1D=65552`) —
a assimetria é **intencional e documentada**: o Caminho B (`run_
cnn_experiments_60k.py`, que define sua própria constante local
`MAX_LEN_B=65552`, sobrescrevendo o default de `hybrid.py`) usa o CT
completo quando há GPU disponível; o Caminho D usa CT completo sempre que
possível, com fallback de prefixo 4096 só para debug/smoke test em CPU —
`run_hybrid_60k.py` imprime um aviso explícito nesse caso avisando que os
resultados não são comparáveis a uma execução em GPU.

**Batch size adaptativo**: `HybridConfig.__post_init__` define
`batch_size_1d = 8 if max_len_1d >= 16384 else 64` — ativações de um batch de
64 sequências de 65.552 posições não cabem em VRAM comum; batch 8 é o valor
que viabilizou rodar em GPU (commits `d809a0d`, `caeb842`, 2026-06-05/06).

`HybridExtractor.transform(feat_matrix, cts)` congela os pesos (`.eval()` +
`torch.no_grad()`) e concatena os três blocos em float64.

## 3.5 Métricas (`src/eval/metrics.py`, 299 linhas)

`compute_metrics(y_true, y_pred, y_proba, n_bootstrap=1000, seed=42)` retorna
um `MetricsReport` com:

- F1-macro + balanced accuracy, cada um com **IC 95% via bootstrap
  percentil** (reamostragem com reposição, `n_bootstrap` iterações).
- `top_k_accuracy` (só calculado se `n_classes > top_k`).
- `expected_calibration_error` (ECE, 10 bins) — só se `y_proba` disponível.
- `compute_auc_roc(y_true, y_proba, labels)` — **presente no código atual**,
  apesar de `CONTEXTO_ARTIGO.md` (2026-06-04) afirmar "AUC/ROC NÃO é
  calculado em nenhum pipeline". Essa função foi adicionada depois (commit
  `cf91290`, "atualização padding", 2026-06-29, junto com
  `scripts/compute_auc_all_paths.py`) — ver correção em
  [08_achados_e_pendencias.md](08_achados_e_pendencias.md).

`mcnemar_test(y_true, y_pred_a, y_pred_b, alpha=0.05, continuity_correction=True)`
— teste pareado clássico (estatística com correção de continuidade,
`chi2.sf(stat, df=1)`), usado para comparar todos os pares de classificadores
em cada Caminho, com correção de Bonferroni aplicada nos scripts que chamam
essa função.
