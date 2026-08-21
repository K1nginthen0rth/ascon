# CNN 1D e CNN 2D como extratores de features (Caminhos B e C)

Este documento descreve o que foi implementado nas duas Redes Neurais Convolucionais (Convolutional Neural Networks, CNN) do experimento Ascon-AEAD128 vs GIFT-COFB: a CNN 1D (Caminho B), a CNN 2D (Caminho C) e o protocolo de treino e avaliação comum às duas. Ambas cumprem papel duplo: classificador end-to-end e extrator de representação latente para o modelo híbrido (Caminho D).

Arquivos envolvidos:

| Arquivo | Conteúdo |
|---|---|
| `src/models/cnn1d.py` | `CiphertextCNN1D` (embedding de bytes + convoluções 1D) |
| `src/models/cnn2d.py` | `CiphertextCNN2D` (convoluções 2D sobre representação matricial) |
| `src/models/ciphertext_to_image.py` | Conversão bytes → co-ocorrência 256×256 (e reshape 32×32 legado) |
| `src/models/cnn_trainer.py` | `CNN1DTrainer` (loop de treino do protocolo antigo, 1 KB) |
| `scripts/run_cnn_experiments_60k.py` | Experimento completo no dataset 60k: CV 5-fold + modelo final |

---

## 1. CNN 1D (Caminho B)

### 1.1 Representação de entrada

O criptograma é tratado como sequência de tokens: cada byte (0 a 255) passa por uma camada `nn.Embedding(256, 32)` treinável, em vez de ser normalizado como escalar. A escolha evita impor uma ordem métrica artificial entre valores de byte (o byte 0x80 não é "maior" que o 0x7F em nenhum sentido criptográfico); a rede aprende a própria representação de cada símbolo.

A sequência tem comprimento fixo: criptogramas mais curtos recebem pad com zero e mais longos são truncados. No protocolo 60k, o Caminho B usa o criptograma completo, com `max_len = 65552` bytes (65536 de plaintext + 16 de tag). Versões anteriores usavam prefixo de 4096 bytes por limitação de CPU; o script híbrido mantém esse fallback quando não há GPU disponível.

### 1.2 Arquitetura

```
Embedding(256, 32)
→ [Conv1D → BatchNorm1D → ReLU → MaxPool1D(2)] × 3   (filtros: 128 → 256 → 512)
→ GlobalAvgPool1D                                      → vetor latente (512D)
→ Dropout(0.3)
→ FC(512 → 2)                                          → logits
```

O número de filtros dobra a cada bloco (128, 256, 512), com kernel 3 e padding que preserva o comprimento antes do pooling. O Global Average Pooling agrega a sequência inteira em um vetor por canal, o que torna a decisão invariante à posição absoluta dos padrões, propriedade desejável quando não há alinhamento estrutural conhecido entre criptogramas.

Para sequências longas (`max_len ≥ 16384`), o primeiro bloco usa kernel 8 com stride 4, reduzindo a sequência por um fator de 4 logo na entrada. Sem essa redução, o custo de convoluções com stride 1 sobre 65552 posições inviabiliza o treino. Sequências curtas mantêm kernel 3 e stride 1, preservando a comparabilidade com resultados anteriores.

Pelo mesmo motivo de custo, o batch size da CNN 1D cai de 64 para 8 quando o criptograma completo é usado (constante `CNN1D_BATCH_SIZE` em `run_cnn_experiments_60k.py`); a memória de ativações de um batch de 64 sequências de 65552 posições não cabe na VRAM disponível.

---

## 2. CNN 2D (Caminho C)

### 2.1 Representação de entrada: co-ocorrência de bigramas

A representação canônica é um mapa de co-ocorrência 256×256 (`bytes_to_cooccurrence`): o pixel [i, j] guarda a frequência relativa do par de bytes consecutivos (i, j) no criptograma, com a matriz normalizada para somar 1. A construção usa `np.bincount` sobre os índices `i*256 + j`, com custo O(n) e sem loop Python.

Essa representação foi adotada no lugar do reshape linear 32×32 usado no protocolo antigo (mantido em `ciphertext_to_image()` por compatibilidade). O reshape impõe adjacência vertical artificial: bytes separados por 32 posições viram vizinhos na imagem sem qualquer relação real. O mapa de co-ocorrência só relaciona bytes que são de fato consecutivos no criptograma, usa o CT completo sem truncamento e é invariante a permutações que preservem os pares consecutivos.

### 2.2 Arquitetura

```
Input (1, 256, 256)
→ [Conv2D 3×3 → BatchNorm2D → ReLU → MaxPool2D(2)] × 3   (canais: 32 → 64 → 128)
→ GlobalAvgPool2D                                          → vetor latente (128D)
→ Dropout(0.3)
→ FC(128 → 2)                                              → logits
```

A rede é treinada do zero, sem pesos pré-treinados de ImageNet: features aprendidas em fotografias naturais (bordas, texturas, objetos) não têm correspondência em criptogramas, que se aproximam de ruído uniforme. O Global Average Pooling torna a arquitetura independente da resolução de entrada, então o mesmo módulo atende tanto o 32×32 legado quanto o 256×256 atual.

---

## 3. Modo extrator (interface comum)

As duas redes expõem a mesma interface para o Caminho D:

- `extract_latent(x)`: retorna o vetor após o Global Average Pooling e antes do Dropout/FC (512D na CNN 1D, 128D na CNN 2D).
- `latent_dim`: propriedade com a dimensão do latente.

O treino é feito com cross-entropy na tarefa de classificação binária, o que guia a representação latente a separar as classes. No Caminho D os pesos são congelados (`model.eval()` + `torch.no_grad()`) e os latentes extraídos são concatenados com as 307 features clássicas, formando o vetor híbrido de 307 + 512 + 128 = 947 dimensões.

---

## 4. Protocolo de treino e avaliação (`run_cnn_experiments_60k.py`)

O script executa seis modos: cada CNN é avaliada end-to-end (`cnn1d_direct`, `cnn2d_direct`) e como extrator com dois classificadores sobre o latente padronizado por `StandardScaler` (Random Forest com 300 árvores e LinearSVC com C=1), totalizando `cnn1d_latent_rf`, `cnn1d_latent_lsvc`, `cnn2d_latent_rf` e `cnn2d_latent_lsvc`.

### 4.1 Validação cruzada com key-holdout

- 5-fold `GroupKFold` agrupado por `key_id` sobre o bloco treino+validação (240 chaves); um `assert` por fold garante que nenhuma chave aparece em treino e validação ao mesmo tempo.
- As 60 chaves de teste ficam fora de toda a CV (holdout).
- Treino com Adam (lr = 1e-3), CrossEntropyLoss, até 30 épocas, early stopping na val_loss com paciência 5.
- Seeds por fold: `7 + fold*100 + 1` (CNN 1D) e `7 + fold*100 + 2` (CNN 2D); bootstrap com seed 42.

### 4.2 Modelo final e métricas

O modelo final é treinado no bloco treino+validação completo por um número fixo de épocas igual a `ceil(média dos best_epoch da CV)`, sem early stopping (não há mais conjunto de validação para monitorar). A avaliação no holdout de teste reporta F1-macro com intervalo de confiança bootstrap (1000 reamostragens, seed 42), balanced accuracy e teste de McNemar com correção de continuidade e Bonferroni entre todos os pares de modos.

### 4.3 Engenharia para viabilizar o 60k

- Datasets lazy (`_SeqDataset`, `_CoocDataset`): a conversão bytes → tensor acontece no `__getitem__`, amostra a amostra. Materializar 48 mil criptogramas de 64 KB (ou 48 mil matrizes 256×256 float32) de uma vez estoura a RAM.
- Checkpoint por época e progresso por fold em disco, com `--resume`: o experimento sobrevive a interrupções (instâncias spot, quedas de energia) sem repetir folds concluídos.
- Cache separado de CV e de modelo final por modo (`--mode cnn1d | cnn2d | both`), permitindo rodar as duas redes em máquinas diferentes.
- Logging opcional no MLflow, com fallback silencioso quando a biblioteca não está instalada.

---

## 5. Decisões de projeto (resumo)

| Decisão | Justificativa |
|---|---|
| Embedding em vez de byte normalizado (CNN 1D) | Bytes são símbolos categóricos, não grandezas; a ordem numérica é arbitrária |
| CT completo no Caminho B (65552) | Elimina a assimetria com o Caminho C e com as features clássicas, que já usavam o CT inteiro |
| Kernel 8 / stride 4 no primeiro bloco (seq. longas) | Reduz o custo por um fator de 4; stride 1 sobre 65552 posições é inviável |
| Batch 8 na CNN 1D com CT longo | Ativações de batch 64 × 65552 posições não cabem na VRAM |
| Co-ocorrência 256×256 em vez de reshape 32×32 | Adjacência real de bytes, CT completo, sem vizinhança artificial |
| Treino do zero na CNN 2D | Features de ImageNet não se aplicam a dados com aparência de ruído |
| Global Average Pooling nas duas redes | Invariância posicional e latente de dimensão fixa para o Caminho D |
| Early stopping na CV, épocas fixas no final | Sem conjunto de validação no treino final; a média da CV estima o ponto de parada |

---

## 6. Status e pendências

- Código dos Caminhos B e C implementado e integrado ao Caminho D (`run_hybrid_60k.py` consome as duas redes via `HybridExtractor`).
- ⚠️ **Atualização 2026-08-16:** a execução completa no dataset 60k **já ocorreu** (números em `dissertacao/resultados.tex`, também confirmam H₀ — modos latentes de B e C com IC 95% cobrindo 0,50). Porém `reports/keyholdout_2class_60k_v1_cnn/` continua com `ckpts/`/`confusion_matrices/` vazios **neste repositório**: os artefatos brutos da execução não foram sincronizados de volta para cá. Ver `docs/analise_completa/07_resultados.md` §7.2 e `08_achados_e_pendencias.md` item 1.
- Resultados anteriores (protocolo 1 KB, CNN 2D 32×32) confirmaram H₀ e ficam como histórico; não são comparáveis ao protocolo atual.

## 7. Como reproduzir

```bash
python scripts/run_cnn_experiments_60k.py                 # CV + modelo final, ambas as CNNs
python scripts/run_cnn_experiments_60k.py --mode cnn1d    # só CNN 1D
python scripts/run_cnn_experiments_60k.py --resume        # retoma de checkpoint (fold + época)
```
