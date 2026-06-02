# Contexto Inicial — Decisões e Histórico

Este arquivo registra o histórico de decisões técnicas e revisões críticas
feitas até **2026-04-26**, antes da implementação no Claude Code começar.

---

## 1. PAPERS REVISADOS E POSICIONAMENTO

### 1.1 Sikdar & Kule (2024) — IJISA, "Intelligent Identification of Cryptographic Ciphers using Machine Learning Techniques"

**Resumo:** Classificação de cifras clássicas (Caesar, Affine, Vigenère, Substitution, Rail Fence) e modernas (AES-128, RC-4) usando CNN, Transformers (GPT-Neo, OPT) e BERT. Pico de 98% de acurácia com BERT pretreinado em dataset-4 (134k amostras).

**O que aproveitar:**
- Estrutura geral de pipeline (geração → extração → modelo → avaliação)
- Comparação de arquiteturas

**O que NÃO seguir:**
- Sem documentação de splits por chave/mensagem (provável vazamento)
- Sem IC nem McNemar
- Sem ECE
- Foca em cifras clássicas, não em LWC padronizadas
- Acurácia de 98% é compatível com vazamento por chave fixa por classe — **ponto de crítica
  explícito a fazer no Capítulo 3 da dissertação.**

### 1.2 Bhavya Shree et al. (2025) — IJIRSET, "Cryptographic Algorithm Detection from Dataset using AI/ML Techniques"

**Status:** Descritivo de projeto, **não estudo experimental**.

**Problemas identificados:**
- Sem resultados numéricos, métricas ou matriz de confusão
- Lista `key length` e `ciphertext length` como features (vazamento puro)
- Mistura RSA com simétricos (trivializa o problema)
- Diagrama copiado de outro contexto ("deepfake detection")
- Referências [1]–[10] possivelmente alucinadas (verificar antes de usar)
- Foco em AES/DES/3DES/RC4/RSA/Blowfish/Twofish — fora do escopo LWC

**Decisão:** **Não citar como fonte primária.** Usar no máximo como exemplo de
"trabalho que ilustra a lacuna metodológica" da literatura recente.

### 1.3 Outros papers do estado da arte (já no Capítulo 3 da proposta IME)

- **De Mello & Xexéo (2016, 2018):** SVM sobre metadados; ECB trivial, CBC marginal.
- **Yuan Chuxuan (2021):** Random Forest + features de convolução; AES/3DES/Blowfish/RSA.
- **Trabalho (9) na proposta:** mostrou que reuso de chave entre treino/teste infla acurácia
  artificialmente — **referência-chave para justificar protocolo rigoroso.**
- **Trabalho (33) na proposta:** ResNet-1D + NIST STS sobre AES/KASUMI/3DES/PRESENT/RSA/ElGamal
  em CBC, >90% de acurácia. Inclui apenas uma cifra leve.
- **Trabalho (8) na proposta:** CNN-1D sobre PRESENT/SIMON em ambiente controlado.

**Lacuna que esta dissertação preenche:** ausência de avaliação sistemática com
algoritmos LWC padronizados (família NIST), com protocolo experimental rigoroso
contra vazamentos por chave/nonce/implementação.

---

## 2. DECISÃO ARQUITETURAL — PIPELINE DE FEATURE SELECTION

### Contexto

Conjunto de features extraídas (histograma 256D + χ² + entropia + n-grams 2–4 +
autocorrelação + runs + LZ + razão de compressão + FFT por banda) facilmente
ultrapassa 20–70 mil dimensões com forte redundância e risco de overfitting.

### Decisão

Adotar pipeline em **3 estágios** rodado **dentro de cada fold de CV**:

1. **Screening univariado**
   - Variance Threshold (descarta n-grams nulos)
   - Mutual Information classif → top-k (default k=1000 ou k=2000)
2. **Redução de redundância**
   - mRMR [Peng, Long & Ding, IEEE TPAMI 2005]
   - Reduz para ~100–300 features
3. **Validação por estabilidade**
   - Boruta [Kursa & Rudnicki, JSS 2010] sobre as ~200 sobreviventes
   - Alternativa: Stability Selection [Meinshausen & Bühlmann, JRSS-B 2010]

### Justificativas-chave

- **Filtros são O(p)** e indispensáveis em alta dimensionalidade [Saeys et al. 2007;
  Bommert et al. 2020]
- **mRMR remove redundância** que filtros univariados ignoram — n-grams 2/3/4 são
  altamente correlacionados por construção [Peng et al. 2005]
- **Boruta é all-relevant** — útil para entender *quais features carregam sinal*,
  não apenas qual subset minimiza erro de um classificador específico
- **Validação dentro do fold** evita o erro documentado em [Ambroise & McLachlan,
  PNAS 2002] que infla acurácia em 30+ pontos percentuais

### Implementação

`src/features/selector.py` → classe `LWCFeatureSelector` com config dataclass.

Dependências: `scikit-learn`, `mrmr-selection`, `Boruta`.

### Validação obrigatória do seletor

1. **Estabilidade entre folds** (Kuncheva index ou Jaccard ≥ 0,5 [Kalousis et al. 2007])
2. **Comparação com features sorteadas aleatoriamente** (McNemar)
3. **Sobrevivência ao key-holdout** — features não devem mudar drasticamente
   entre seeds de chave diferentes (sintoma de vazamento)
4. **Sanity em PRNG puro** — Boruta deve retornar conjunto vazio em bytes
   verdadeiramente aleatórios

### Riscos catalogados

- Seleção fora do CV → vazamento massivo [Ambroise & McLachlan 2002]
- Boruta com p > 10k é inviável (custo) → solucionado pelos estágios anteriores
- mRMR com features mistas → discretizar com KBinsDiscretizer
- Importância Gini de RF é enviesada para features de alta cardinalidade
  [Strobl et al. 2007] → usar permutation importance ou Boruta

---

## 3. REFERÊNCIAS BIBLIOGRÁFICAS-CHAVE

### Feature selection (citáveis na metodologia)

- Ambroise, C., & McLachlan, G. J. (2002). Selection bias in gene extraction
  on the basis of microarray gene-expression data. *PNAS*, 99(10), 6562–6566.
- Bolón-Canedo, V., Sánchez-Maroño, N., & Alonso-Betanzos, A. (2015).
  *Feature Selection for High-Dimensional Data*. Springer.
- Bommert, A., Sun, X., Bischl, B., Rahnenführer, J., & Lang, M. (2020).
  Benchmark for filter methods for feature selection in high-dimensional
  classification data. *Computational Statistics & Data Analysis*, 143, 106839.
- Breiman, L. (2001). Random forests. *Machine Learning*, 45(1), 5–32.
- Chen, T., & Guestrin, C. (2016). XGBoost: A scalable tree boosting system.
  *KDD '16*, 785–794.
- Cover, T. M., & Thomas, J. A. (2006). *Elements of Information Theory* (2nd ed.). Wiley.
- Ding, C., & Peng, H. (2005). Minimum redundancy feature selection from
  microarray gene expression data. *J. Bioinformatics and Computational Biology*, 3(2), 185–205.
- Kalousis, A., Prados, J., & Hilario, M. (2007). Stability of feature
  selection algorithms. *Knowledge and Information Systems*, 12(1), 95–116.
- Kuncheva, L. I. (2007). A stability index for feature selection. *AIA '07*, 421–427.
- Kursa, M. B., & Rudnicki, W. R. (2010). Feature selection with the Boruta
  package. *Journal of Statistical Software*, 36(11), 1–13.
- Lundberg, S. M., & Lee, S.-I. (2017). A unified approach to interpreting
  model predictions. *NeurIPS 30*.
- Meinshausen, N., & Bühlmann, P. (2010). Stability selection.
  *Journal of the Royal Statistical Society: Series B*, 72(4), 417–473.
- Peng, H., Long, F., & Ding, C. (2005). Feature selection based on mutual
  information: criteria of max-dependency, max-relevance, and min-redundancy.
  *IEEE TPAMI*, 27(8), 1226–1238.
- Pudjihartono, N., Fadason, T., Kempa-Liehr, A. W., & O'Sullivan, J. M. (2022).
  A review of feature selection methods for machine learning-based disease
  risk prediction. *Frontiers in Bioinformatics*, 2, 927312.
- Ramírez-Gallego, S., Lastra, I., Martínez-Rego, D., et al. (2017). Fast-mRMR:
  Fast minimum redundancy maximum relevance algorithm for high-dimensional
  big data. *International Journal of Intelligent Systems*, 32(2), 134–152.
- Saeys, Y., Inza, I., & Larrañaga, P. (2007). A review of feature selection
  techniques in bioinformatics. *Bioinformatics*, 23(19), 2507–2517.
- Shah, R. D., & Samworth, R. J. (2013). Variable selection with error control:
  another look at stability selection. *JRSS-B*, 75(1), 55–80.
- Strobl, C., Boulesteix, A.-L., Zeileis, A., & Hothorn, T. (2007). Bias in
  random forest variable importance measures. *BMC Bioinformatics*, 8, 25.
- Tibshirani, R. (1996). Regression shrinkage and selection via the lasso.
  *JRSS-B*, 58(1), 267–288.
- Zhao, P., & Yu, B. (2006). On model selection consistency of Lasso.
  *JMLR*, 7, 2541–2563.

### Cripto e LWC (já no Capítulo 3 da proposta IME)

- Padronização Ascon: NIST SP 800-232.
- Sikdar, S., & Kule, M. (2024). Intelligent Identification of Cryptographic
  Ciphers using Machine Learning Techniques. *IJISA*, 16(6), 20–39.
- (demais referências numeradas conforme proposta IME — manter alinhadas)

---

## 4. NOTAS DE TRABALHO

### Dúvidas ainda em aberto
- [ ] Lista final de algoritmos LWC além do Ascon (GIFT-COFB? Xoodyak? PRESENT?)
- [ ] Tamanho do dataset-piloto (10k? 50k? 100k amostras?)
- [ ] Política de nonce: estritamente único por chave ou amostragem aleatória?
- [ ] Implementação de referência: ascon-c oficial ou bindings Python (pyascon)?

### Convenções acordadas
- Seeds principais: `42` para split, `7` para modelo, `13` para feature selection
- Formato de manifesto: YAML em `data/manifests/{dataset_id}.yaml`
- Versão de cada artefato: `git rev-parse --short HEAD` registrado nos metadados

### Princípio orientador
> "Em ambos os desfechos (H₀ ou H₁), o trabalho é útil: ou fornece evidência
> empírica a favor da robustez esperada dos esquemas LWC, ou identifica pontos
> de melhoria concretos para o ecossistema."
> — Capítulo 1 da proposta

Este princípio guia toda decisão metodológica: **rigor é mais importante que
acurácia alta.** Resultados altos sem controle de vazamento valem menos que
resultados modestos com protocolo blindado.
