# CONTEXTO COMPLETO DO PROJETO ASCON-ML

**Data:** 2026-04-26 | **Usuário:** nycol (IME-RJ) | **Status:** Implementação inicial em andamento

---

## 1. OBJETIVO E PERGUNTA DE PESQUISA

### Dissertação
*Atribuição de Algoritmos de Criptografia Leve em Cenário Ciphertext-Only via Aprendizado de Máquina*

### Pergunta Central
**É possível, a partir EXCLUSIVAMENTE de criptogramas, identificar o algoritmo de criptografia leve (LWC) que os gerou, utilizando ML, com desempenho estatisticamente superior ao acaso?**

### Hipóteses
- **H₀ (nula):** Algoritmos LWC padronizados NIST são praticamente indistinguíveis em cenário ciphertext-only
- **H₁ (alternativa):** Existem assinaturas residuais e exploráveis por ML

### Valor da Dissertação
> "Em ambos os desfechos (H₀ ou H₁), o trabalho é útil: ou fornece evidência empírica a favor da robustez esperada dos esquemas LWC, ou identifica pontos de melhoria concretos para o ecossistema."

---

## 2. ESCOPO TÉCNICO

### 2.1 Algoritmos Criptográficos

| Algoritmo | Papel | Tamanho | Status |
|-----------|-------|--------|--------|
| **Ascon-AEAD128** | **Prioritário (NIST SP 800-232)** | 128 bits | ✅ Wrappers prontos |
| GIFT-128 | Candidato LWC NIST | 128 bits | ⏳ Futuro |
| PRESENT-128 | Candidato LWC NIST | 128 bits | ⏳ Futuro |
| Piccolo-128 | Candidato LWC NIST | 128 bits | ⏳ Futuro |
| AES-128 | **Controle (fora do escopo LWC)** | 128 bits | ⏳ Para ablação |
| ECB puro | **Controle negativo (trivial)** | 128 bits | ⏳ Baseline |

### 2.2 Modo de Operação
- **AEAD** (Autenticação + Encriptação): Ascon no modo autenticado
- **Chave:** 128 bits (fixa)
- **Nonce:** 128 bits (único por mensagem)
- **AD (Dados Autenticados):** Variável (controlado em experimento)
- **Plaintext:** Variável (0 a 2048 bytes, com múltiplos tamanhos)

### 2.3 Cenário de Ataque
- **Observável pelo atacante:** criptogramas apenas (ciphertext-only)
- **NÃO observável:** chave, nonce, plaintext, AD
- **Protocolo:** Múltiplas amostras com mesma chave mas nonces diferentes

---

## 3. REGRAS DE OURO (INVIOLÁVEIS)

Toda entrega deve respeitar estas **cinco regras** sob pena de invalidade:

### Regra 1: Reprodutibilidade
✅ Seeds fixas em `configs/seeds.yaml` (padrão: 42, 7, 13)  
✅ Versões de bibliotecas em `environment.yml`  
✅ Parâmetros registrados em manifesto YAML por dataset

### Regra 2: Sem Vazamento (CRÍTICA)
❌ **NUNCA** misturar chaves entre treino/teste  
❌ **NUNCA** usar mensagens repetidas entre treino/teste  
❌ **NUNCA** usar tamanho PT/AD como feature no modelo final  
✅ **SEMPRE** segregar por key_id e message_id

**Três splits obrigatórios:**
1. **key-holdout:** Chaves inéditas no teste
2. **message-holdout:** Mensagens inéditas no teste
3. **combined:** Ambos inéditos

### Regra 3: Controles Obrigatórios
✅ **ECB como controle negativo:** ECB em modo bruto (sem nonce) deve dar acurácia ~1/K (chance)  
✅ **AES-128 como classe "fora de escopo":** Deve ser distinguível das LWC  
✅ **PRNG puro:** Bytes aleatórios não devem permitir classificação acima de 1/K  
✅ **Bytes embaralhados:** Se embaralhar os bits de um ciphertext, modelo deve desmoronar

### Regra 4: Metadados Obrigatórios
Cada amostra gerada deve carregar:
```
{
  algoritmo: string,
  modo: string (AEAD, ECB, etc.),
  implementacao: string (ref, opt32, etc.),
  key_id: string (key_0001, key_0002, ...),
  nonce_id: string (nonce_0001, ...),
  len_pt: int,
  len_ad: int,
  seed: string,
  versao: string (v1, v2, ...)
}
```

### Regra 5: Ética e Segurança
✅ Nenhum dado real ou de produção  
✅ Licenças compatíveis (Ascon: public domain, NIST SP 800-232)  
✅ Documentar limitações (ex: "ECB trivial, não representa NIST standard")

---

## 4. PIPELINE DE FEATURE SELECTION (DECISÃO ARQUITETURAL)

### 4.1 Problema
Conjunto de features (histograma 256D + χ² + entropia + n-grams 2–4 + autocorrelação + FFT) facilmente ultrapassa **20–70 mil dimensões** com forte **redundância** e risco de **overfitting**.

### 4.2 Solução: 3 Estágios (Dentro de Cada Fold!)

```
┌─ ESTÁGIO 1: SCREENING UNIVARIADO (O(p) rápido)
│  ├─ Variance Threshold: remove features com variância ~0
│  └─ Mutual Information classif → top-k (k=1000 ou 2000)
│
├─ ESTÁGIO 2: REDUÇÃO DE REDUNDÂNCIA
│  └─ mRMR [Peng et al. 2005]: remove correlações
│     (n-grams 2/3/4 são altamente redundantes por construção)
│     Reduz para ~100–300 features
│
└─ ESTÁGIO 3: VALIDAÇÃO POR ESTABILIDADE
   └─ Boruta [Kursa & Rudnicki 2010]: all-relevant
      Sobre as ~200 sobreviventes → top features estáveis
```

### 4.3 Por Que Esse Design?

| Referência | Argumento |
|------------|-----------|
| **[Saeys et al. 2007]** | Filtros univariados são O(p) e indispensáveis em alta dimensionalidade |
| **[Peng et al. 2005]** | mRMR remove redundância que filtros univariados ignoram |
| **[Kursa & Rudnicki 2010]** | Boruta é all-relevant, útil para interpretabilidade |
| **[Ambroise & McLachlan 2002]** | **CRÍTICO:** Seleção fora do CV infla acurácia em ~30pp (erro documentado em bioinformática) |

### 4.4 CLÁUSULA CRÍTICA: Validação Dentro do Fold
```python
for fold in cross_validation_splits:
    train_idx, test_idx = fold
    # ⚠️ NUNCA ANTES:
    # selector = mRMR(X_train, y_train)  # ❌ VAZAMENTO!
    
    # ✅ CORRETO:
    selector = mRMR(X_train[train_idx], y_train[train_idx])
    features = selector.select()
    # Usar 'features' apenas em test_idx
```

### 4.5 Validação do Seletor
1. **Estabilidade entre folds:** Jaccard ≥ 0,5 [Kalousis et al. 2007]
2. **Comparação com aleatório:** McNemar significativo
3. **Sanity check PRNG:** Boruta em bytes aleatórios → conjunto vazio
4. **Sobrevivência ao key-holdout:** Features não devem mudar drasticamente entre seeds

---

## 5. ESTADO ATUAL DO PROJETO

### 5.1 ✅ Já Decidido e Documentado

- Escopo de algoritmos e modos
- Métrica-alvo: **F1-macro com IC bootstrap + teste McNemar pareado**
- Splits e protocolo de validação
- Pipeline de feature selection (3 estágios, mRMR + Boruta)
- Revisão crítica da literatura (Capítulo 3 da proposta)

### 5.2 🟡 Em Andamento

- ✅ **ascon-c/build/** pronto (VCXPROJ compilados)
- ✅ **scripts/generate_ascon_variable_sizes.py** escrito (11k amostras)
- ✅ **scripts/ascon_cli_ref.exe** compilado e testado
- ✅ **data/raw/corpora/** carregado (~3600 arquivos de texto, ~1.2 GB)
- 🟡 **data/processed/ascon_aead128_variable_sizes_v1.parquet** gerando...
- ❌ **scripts/validate_all_datasets.py** escrito mas não validado contra KATs

### 5.3 ❌ Não Iniciado (Bloqueadores)

| Componente | Arquivo | Prioridade |
|------------|---------|-----------|
| Wrapper Ascon com validação KAT | `src/crypto/ascon_wrapper.py` | **BLOQUEADOR** |
| Extrator de features | `src/features/extractor.py` | Normal |
| Seletor (3-estágios) | `src/features/selector.py` | Normal |
| Modelos (RF, SVM, CNN-1D) | `src/models/` | Normal |
| Avaliação com IC + McNemar | `src/eval/` | Normal |
| Testes unitários | `tests/` | Normal |

---

## 6. ARTIFACTS E ESTRUTURA

### 6.1 Estrutura do Repositório

```
lwc-ml/
├── CLAUDE.md                    ← Regras permanentes (meta)
├── docs/
│   ├── contexto_inicial.md      ← Decisões e papers revisados
│   ├── CONTEXTO_PARA_CLAUDE_WEB.md  ← Este arquivo
│   ├── papers/                  ← PDFs anotados (Sikdar, NIST, etc.)
│   └── ADRs/                    ← Architecture Decision Records (futuro)
├── ascon-c/                     ← Ascon reference implementation (C)
│   ├── build/                   ← VCXPROJ + .exe compilados
│   ├── src/                     ← Impls (ref, opt32, opt64, bi8, bi32, ...)
│   ├── tests/                   ← Testes oficiais Ascon
│   └── LWC_AEAD_KAT_128_128.txt ← KATs NIST
├── data/
│   ├── raw/
│   │   └── corpora/             ← 3600+ arquivos de texto (plaintext)
│   ├── interim/                 ← Datasets em processamento
│   └── processed/               ← Parquets finais + manifestos + profiles
├── src/
│   ├── crypto/                  ← ⚠️ VAZIO: wrappers de cifras + validação
│   ├── features/                ← ⚠️ VAZIO: extractores + selector
│   ├── models/                  ← ⚠️ VAZIO: sklearn/torch
│   ├── eval/                    ← ⚠️ VAZIO: métricas + relatórios
│   └── utils/                   ← ⚠️ VAZIO: helper funcs
├── configs/                     ← Hydra configs (futuro)
├── experiments/                 ← YAMLs de cada cenário (futuro)
├── notebooks/                   ← EDA e sanity checks (futuro)
├── reports/                     ← Figuras e PDFs de resultados
├── tests/                       ← ⚠️ VAZIO: pytest
├── scripts/                     ← Scripts standalone
│   ├── generate_ascon_variable_sizes.py  ✅ Pronto
│   ├── plaintext_generator.py            ✅ Pronto
│   ├── validate_all_datasets.py          ⚠️ Escrito, não testado
│   ├── test_wrapper_python.py            ✅ Mínimo teste
│   ├── ascon_cli_ref.exe                 ✅ Compilado
│   └── generate_random_control.py        ⚠️ Futuro
├── environment.yml              ← Dependências Python
├── Makefile                     ← Comandos build/run (futuro)
└── .git/                        ← Git repo
```

### 6.2 Datasets Esperados

| Dataset | Tamanho | Amostras | Algo | Feature |
|---------|---------|----------|------|---------|
| `ascon_aead128_variable_sizes_v1` | ~200 MB | 11.000 | Ascon-AEAD128 | PT: 0, 1, 8, 16, ..., 2048 bytes |
| `ascon_aead128_key_holdout_v1` | TBD | ~50k | Ascon-AEAD128 | 100 chaves diferentes |
| `ascon_aead128_msg_holdout_v1` | TBD | ~50k | Ascon-AEAD128 | Mensagens únicas |
| `control_aes128_v1` | TBD | ~10k | AES-128 CBC | Para ablação |
| `control_ecb_pure_v1` | TBD | ~10k | ECB direto | Baseline negativo |

---

## 7. PRÓXIMAS TAREFAS (ROADMAP)

### Fase 1: Validação Criptográfica (BLOQUEADOR)
- [ ] **Task 1:** Ler KATs oficiais de Ascon em `ascon-c/LWC_AEAD_KAT_128_128.txt`
- [ ] **Task 2:** Implementar `src/crypto/ascon_wrapper.py`:
  - [ ] Wrapper Python sobre `ascon_cli_ref.exe`
  - [ ] Validação KAT contra arquivo oficial
  - [ ] Tratamento de erro robusto
- [ ] **Task 3:** Rodar `scripts/validate_all_datasets.py` com assinatura de criptografia (HMAC check)

### Fase 2: Geração de Dados
- [ ] **Task 4:** Confirmar dataset-piloto `ascon_aead128_variable_sizes_v1.parquet` (11k amostras)
- [ ] **Task 5:** Gerar `ascon_aead128_key_holdout_v1` (100 chaves, 500 samples cada)
- [ ] **Task 6:** Sanity check: uniformidade bytes (χ²), compressibilidade, ausência padrões triviais

### Fase 3: Feature Extraction
- [ ] **Task 7:** Implementar `src/features/extractor.py`:
  - [ ] Histograma 256D
  - [ ] χ² de uniformidade
  - [ ] Entropia de Shannon
  - [ ] N-gramas 2–4
  - [ ] Autocorrelação
  - [ ] Runs test
  - [ ] Lempel-Ziv
  - [ ] FFT por banda
- [ ] **Task 8:** Benchmark: extrair features em <1s por amostra

### Fase 4: Feature Selection (3-Estágios)
- [ ] **Task 9:** Implementar `src/features/selector.py`:
  - [ ] Variance Threshold + MI
  - [ ] mRMR com scikit-learn compatível
  - [ ] Boruta wrapper
  - [ ] Validação dentro do CV
- [ ] **Task 10:** Testar estabilidade (Jaccard ≥ 0.5)
- [ ] **Task 11:** Sanity: Boruta em PRNG → conjunto vazio

### Fase 5: Modelagem
- [ ] **Task 12:** Treinar RF, SVM no dataset-piloto
- [ ] **Task 13:** Baseline CNN-1D com embeddings de byte
- [ ] **Task 14:** Matriz de confusão + análise de erro (3–5 insights)

### Fase 6: Avaliação Rigorosa
- [ ] **Task 15:** Métricas: F1-macro, balanced acc, top-k, ECE
- [ ] **Task 16:** Bootstrap IC 95% em todas as métricas
- [ ] **Task 17:** McNemar teste pareado em ablações
- [ ] **Task 18:** Relatório de reprodutibilidade

### Fase 7: Testes Negativos
- [ ] **Task 19:** Verificar ECB puro ~ acaso (1/K)
- [ ] **Task 20:** Verificar PRNG puro ~ acaso (1/K)
- [ ] **Task 21:** Truncar mensagens (25/50/75%) → modelo degrada?
- [ ] **Task 22:** Trocar implementação (ref vs opt32) → estável?

---

## 8. SEEDS E CONVENÇÕES

### Seeds Principais
```yaml
random_seed: 42      # split treino/val/teste
model_seed: 7        # parâmetros iniciais RF/SVM
fs_seed: 13          # feature selection
crypto_seed: "base"  # geração de PT (corpus sampling)
```

### Nomenclatura de IDs
```
key_0001, key_0002, ..., key_0100
nonce_0001, nonce_0002, ...
sample_{algo}_{tamanho}_{seed}_{idx}.bin
```

### Versão de Artefatos
```
ascon_aead128_variable_sizes_v1_20260426.parquet
ascon_aead128_variable_sizes_v1_20260426_manifest.json
ascon_aead128_variable_sizes_v1_20260426_profile.json
```

---

## 9. MÉTRICAS E CRITÉRIOS DE SUCESSO

### 9.1 Métrica Primária: F1-Macro
```
F1-macro = (1/K) * Σ F1(class_i)
```
Escolhido porque:
- Sensível a ambas as classes (não penaliza classe majoritária)
- Padrão em multi-class balanceado
- Interpretável (média de recalls por classe)

### 9.2 Intervalo de Confiança Bootstrap
```python
from sklearn.utils import resample
for i in range(1000):
    X_boot, y_boot = resample(X_test, y_test)
    f1_boot[i] = f1_score(y_boot, y_pred_boot)
ic_lower = np.percentile(f1_boot, 2.5)
ic_upper = np.percentile(f1_boot, 97.5)
```

### 9.3 Baseline (Chance)
**Para K=4 algoritmos:** F1-macro = 0.25 (acaso)  
**Teste:** IC de F1 **não deve conter** 0.25 para ser "significativo"

### 9.4 McNemar Pareado
Para comparar dois modelos:
```
McNemar(modelo1 vs modelo2, X_test, y_test)
p-value < 0.05 → diferença significativa
```

---

## 10. RISCOS CATALOGADOS

| Risco | Gravidade | Mitigação |
|-------|-----------|-----------|
| **Vazamento por chave fixa** | 🔴 CRÍTICA | Sempre segregar key_id em splits |
| **Mismatch KAT** | 🔴 CRÍTICA | Validar contra NIST antes de usar |
| **Seleção fora do CV** | 🔴 CRÍTICA | Ambroise & McLachlan 2002: infla ~30pp |
| **Overfit em features** | 🟠 ALTA | Boruta + stability + CV rigorosa |
| **ECB trivial** | 🟡 MÉDIA | Documentar que ECB não é NIST standard |
| **Tamanho PT como feature** | 🟡 MÉDIA | Nunca incluir len_pt, len_ad no modelo final |
| **Implementação-específico** | 🟡 MÉDIA | Testar com múltiplas impls (ref, opt32) |

---

## 11. REFERÊNCIAS-CHAVE

### Feature Selection
- Ambroise & McLachlan (2002). Selection bias in gene extraction. **PNAS** 99(10)
- Peng et al. (2005). Minimum redundancy feature selection. **IEEE TPAMI** 27(8)
- Kursa & Rudnicki (2010). Feature selection with Boruta. **JSS** 36(11)
- Kalousis et al. (2007). Stability of feature selection algorithms. **KIS** 12(1)
- Strobl et al. (2007). Bias in random forest variable importance. **BMC Bioinformatics** 8

### Criptografia LWC
- NIST SP 800-232 (2024). Ascon AEAD standard
- Sikdar & Kule (2024). Intelligent Identification of Cryptographic Ciphers. **IJISA** 16(6)
- De Mello & Xexéo (2016, 2018). SVM sobre metadados [Proposta IME, ref 8]
- Yuan Chuxuan (2021). Random Forest + features de convolução [Proposta IME, ref 33]

---

## 12. CONTATOS E RESPONSABILIDADES

| Papel | Responsável | Contato |
|-------|-------------|---------|
| Pesquisador Principal | nycol | Mestrado IME-RJ |
| Orientador (Proposta) | - | IME-RJ |
| Assistente de IA | Claude (Copilot) | Este documento |

---

**Última atualização:** 2026-04-26  
**Próxima revisão:** Após Task 3 (Validação KAT)  
**Status:** Pronto para Fase 1 (Bloqueadores)
