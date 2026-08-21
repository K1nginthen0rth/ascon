# 4. Protocolo, métricas, controles e validação estatística

## 4.1 Split e validação cruzada ✅

- **Inalterado do v1:** 80/20 por chave (240 trainval / 60 teste) + 5-fold
  `GroupKFold` por `key_id` (192/48 por fold). Split é por chave; como o
  dataset é encadeado, funciona idêntico no multiclasse.
- **Novo:** origem do plaintext (texto/imagem) sorteada **por amostra dentro de
  cada chave** — qualquer split por chave preserva o 80/20 automaticamente.
- Seeds canônicas inalteradas: split=42, modelo=7, FS=13, bootstrap=42.

## 4.2 Ablações ✅

| Ablação | O que compara | Escopo | Por quê |
|---|---|---|---|
| Key-holdout on/off | split por chave vs. split aleatório ignorando `key_id` | **Caminho A, em dois braços: controle AES-ECB e os 4 algoritmos íntegros** (barato) | **Correção de expectativa:** nos 4 algoritmos íntegros, IND-CPA com nonce único por amostra implica que não há nada a memorizar entre amostras da mesma chave — sob H₀, split aleatório e key-holdout devem dar o **mesmo** resultado nulo, não uma diferença; prometer "demonstrar a inflação" ali pede a um teste sem sinal esperado um resultado que só apareceria se o algoritmo estivesse quebrado. Quem garante inflação por mecanismo é o AES-ECB (determinístico por chave — blocos repetidos do corpus memorizáveis entre amostras da mesma chave). Rodar nos dois braços faz o ECB funcionar como **controle positivo do próprio método de ablação**: comprova que ele detecta inflação quando ela existe, antes de interpretar o silêncio nos 4 algoritmos reais como evidência (e não como teste sem poder) |
| Truncamento do Grain | braço `cru` (comprimentos reais) vs. `controlado` (todos em 65.544) | Caminhos **A e B** (CNN1D mais vulnerável); C esperado pouco afetado — comparação em si é resultado. **Não se aplica às features de tag** (sempre janela comum de 8 bytes sobre o CT cru — ver `02_features_e_selecao.md` e `01_algoritmos_e_dataset.md` §1.6); aplica-se às estatísticas sensíveis a comprimento total do CT/payload (`lz_complexity`, `runs_count`, autocorrelação) | isola o artefato do comprimento total (padding posicional na CNN1D; contagens absolutas no Caminho A) do sinal criptográfico real, sem reintroduzir o mesmo artefato pela porta das features de tag |
| Famílias de features | all / por família / top-1 | Caminho A | re-execução da ablação v1 sobre o seletor redesenhado e o dataset novo |

## 4.3 Métricas ✅

**Conjunto completo, reportado para todo modelo em todo fold e no teste:**

- F1-macro (primária), **acurácia simples** (novo — nome usado pela literatura;
  coincide numericamente com a balanceada no nosso desenho balanceado, mas
  reportar as duas evita confusão de comparação), acurácia balanceada
- **Precisão e recall por classe** — em TODA tabela (resultado principal,
  controles, ablações). Corrige a inconsistência apontada pela Review 1 do
  SBSeg e atende o ponto 8 do orientador
- Matriz de confusão N×N — **sempre** (ver 4.4)
- IC 95% bootstrap (1000×, seed 42)
- McNemar pareado (correção de continuidade + Bonferroni entre modelos)
- ECE (também insumo do Caminho F)
- AUC-ROC: agregado OVR **e por classe** (novo — expõe se um algoritmo
  específico descola dos demais)
- **Sem MSE** — deslize metodológico do E09, não replicar

**Validação multiclasse empírica** do código de métricas antes da rodada real
(mesma lógica do seletor: teste sintético de 4 classes).

## 4.4 Regra de relato obrigatória ✅ (pedido do orientador — sem exceção)

1. **Toda métrica imprime no console imediatamente ao ser calculada** — todo
   modelo, todo fold, todo Caminho, todo braço de ablação. Nada de "só no
   relatório final".
2. **Matriz de confusão sempre gerada e nas três formas:** impressa no console
   (tabela legível), salva em números (JSON), salva como imagem (PNG).
3. **Implementação: função única de relato compartilhada** — todos os Caminhos
   (A–F) chamam a mesma função, que imprime, salva JSON incremental e salva
   PNG. Uniformidade estrutural em vez de disciplina manual por script.
4. **Gravação incremental em disco** — cada resultado persiste assim que
   existe; queda de sessão não perde nada já calculado (mesma filosofia do
   checkpoint das CNNs, estendida à camada de resultados).
5. **Predição e probabilidade por amostra, persistidas por fold ✅ (adicionado
   — pré-requisito do Caminho F):** a função única salva, para cada amostra
   do fold de validação, `{sample_id, key_id, y_true, y_pred, y_proba}` — não
   só o agregado. Sem isso, a matriz de probabilidades out-of-fold que o
   Caminho F exige (`03_classificadores.md` §3.6) não é reconstruível depois
   do fato. Os Caminhos A–E precisam gerar essas predições sobre **a mesma
   partição de folds** (mesmos `key_id` por fold em todos os caminhos,
   verificado por assert).

Motivo: métricas foram perdidas no v1 por prints ad-hoc e relatórios só ao
final; matriz de confusão é exigência direta do orientador; predição por
amostra é pré-requisito técnico do Caminho F, que não existia como caminho no
v1 e por isso nunca tinha motivado essa exigência antes.

## 4.5 Controles

| Controle | Tipo | Desenho | Status |
|---|---|---|---|
| AES-128-ECB vs Ascon | positivo | binário, dados do mesmo parquet encadeado; fraqueza estrutural conhecida (determinismo/ECB) | ✅ |
| PRNG puro | negativo | bytes aleatórios (CTR_DRBG, seed própria), `key_id` sintético por slot; **binários contra cada um dos 4** (não classe extra); cada par deve dar acaso | ✅ |
| Embaralhamento de bytes | negativo/diagnóstico | shuffle da ordem dos bytes de CTs reais — destrói estrutura sequencial, preserva histograma; separa sinal marginal de estrutural (responde Review 1 SBSeg) | ✅ |
| Ascon rodadas reduzidas | calibração de sensibilidade | — | ❌ rejeitada (C2) |
| `len_ct` como feature de propósito | sanity de encanamento | uma única rodada rotulada `sanity`, fora das tabelas de resultado: pares com Grain devem dar F1 > 0,95; senão, bug no pipeline | ✅ |

Os controles negativos respondem diretamente ao ponto 3 do orientador
("os algoritmos já foram testados contra strings aleatórias; o que está sendo
testado é se são distinguíveis **entre si**") — hoje só existe controle
positivo.

## 4.6 Arcabouço estatístico — DECIDIDO em 2026-08-21 (redação final no 06 §5.3; abaixo, o registro original com placar)

Placar: item 1 ✅ **reformulado** (família primária = 6 pares par-a-par no
Caminho A, **F1 como métrica oficial**; FDR/BH no exploratório; positivo
sobrevivente ⇒ replicação com chaves novas — braço primário: **controlado**,
decidido 2026-08-21, com o cru como análise reportável do artefato);
item 2 ✅; item 3 ✅; item 4 ❌ (pré-registro rejeitado); itens 5, 6, 7 ✅.

1. **Hipótese primária declarada + correção de múltiplas comparações:** com 6
   pares × 6 caminhos × ~8 modelos + ablações, 200+ testes são esperados —
   ~10 "significativos" por puro acaso em α=0,05. Proposta: hipótese primária
   = F1-macro 4-classes no Caminho A; todo o resto secundário/exploratório com
   FDR (Benjamini-Hochberg); Bonferroni global mataria qualquer efeito real.
2. **Análise par a par obrigatória:** as 6 comparações par a par extraídas da
   matriz de confusão, cada uma com IC próprio — o agregado de 4 classes pode
   mascarar (ex.: Grain separável por artefato inflando o F1-macro enquanto
   Ascon/GIFT/Sparkle seguem no acaso).
3. **Poder estatístico a priori:** calcular e escrever ANTES de rodar o menor
   efeito detectável (com ~24k amostras de teste e IC ±0,008 no v1, detecta-se
   ~1 p.p. acima do acaso). Transforma o nulo de "ausência de evidência" em
   "tínhamos poder para detectar X e não detectamos".
4. **Pré-registro:** documento datado no repositório com hipótese primária,
   plano de análise e regra de parada, ANTES da primeira rodada — custa uma
   tarde, blinda a dissertação de nulo contra a acusação de pesca.
5. **Curvas de aprendizado:** F1 vs. tamanho de treino (Caminho A) — se plano
   no acaso de 10k a 96k, o nulo convergiu; responde "faltaram dados".
6. **Message-holdout / overlap:** no mínimo medir e reportar sobreposição de
   plaintexts entre splits (Regra 2 original nunca cumprida; com pool finito de
   imagens fica mais saliente).
7. **Estratificação de erro por metadados:** se algo separar, verificar
   correlação do erro com chave e com `plaintext_source` — "separa melhor em
   imagens" seria bandeira vermelha de artefato.

## 4.7 Valores de referência ✅

| Cenário | Acaso | Colapso |
|---|---|---|
| 4 classes | 0,25 | 0,10 |
| Binário (controle) | 0,50 | 0,333 |
