# Plano do Experimento v2 — índice

**Data de fechamento do planejamento:** 2026-08-21.
**Origem:** reunião com o orientador (27/07/2026, 15 pontos), pareceres do SBSeg
(4 revisões), RSL (21 estudos, `docs/RSL_completa.txt`) e as sessões de
planejamento que produziram esta pasta.

Este é o documento-mestre do próximo experimento. O que está aqui **substitui**
o planejamento parcial de `docs/relatorio_orientador_novo_experimento.md`
(mantido como resumo simples para o orientador, atualizado) e **estende** o
estado descrito em `docs/analise_completa/` (que documenta o experimento v1, já
concluído).

## Legenda de status usada em todos os arquivos

| Marca | Significado |
|---|---|
| ✅ | Decidido explicitamente em conversa — pode implementar |
| 🔶 | Recomendado na revisão de especialista — **aguarda confirmação** do Nycolas/orientador |
| ⏳ | Verificação técnica pendente antes de implementar |

## O que muda do v1 para o v2

| Eixo | v1 (concluído) | v2 (planejado) |
|---|---|---|
| Pergunta | Ascon vs GIFT-COFB (binário) | 4 LWC multiclasse + controle separado |
| Algoritmos | 2 | 4 principais + AES-ECB (controle) |
| Parametrização do Ascon | `ascon128v13` (taxa 64 bits, pré-padrão) | `ascon128av13` (taxa 128 bits = NIST SP 800-232 final) |
| Dataset | 60k amostras, 100% SPGC | 150k encadeado (5 algs × 30k), 80% texto / 20% imagem |
| RNG de geração | NumPy PCG64 | CTR_DRBG AES (NIST SP 800-90A), validado por CAVP |
| Caminhos | A–D | A–F (novo: E=Transformer, F=meta-classificador) |
| Features | 307 | ~400+ (NIST SP 800-22 completo + 5 da literatura + tag/payload, janela comum de 8 bytes) |
| Seletor | VT bruto → MI top-k → mRMR → Boruta(diag) | z-score → VT → MI (corte generoso, não-estatístico) → mRMR → Boruta(diag) |
| Controle positivo | Vigenère | AES-128-ECB vs Ascon (resposta direta ao SBSeg) |
| Controles negativos | — (nunca executados) | 🔶 PRNG puro + embaralhamento de bytes |
| Validação estatística | IC bootstrap + McNemar | + 🔶 poder a priori, hipótese primária + FDR, pré-registro |
| Relato | prints ad-hoc por script | **função única obrigatória**: toda métrica impressa na hora + matriz de confusão sempre (console + JSON + PNG) + predição/probabilidade por amostra (pré-requisito do Caminho F) |

**Revisão de 2026-08-21 (pós-fechamento):** uma leitura crítica encontrou 5
erros/lacunas no plano abaixo — Caminho E rotulado erroneamente como réplica
do E20, features de tag vazando `len_ct` via viés de amostra pequena (e
colidindo com o truncamento do Grain), reshape da réplica E05 incompatível
com o tamanho do CT, mapeamento de nonce do Sparkle indefinido, réplica
XGB-LGBM sem a representação do estudo original, ablação key-holdout
prometendo um efeito que não existe nos 4 algoritmos íntegros, e Caminho F
sem disciplina out-of-fold. Todos corrigidos diretamente nos arquivos 01–04;
detalhe e rastreabilidade em
[05_execucao_riscos_pendencias.md §5.5](05_execucao_riscos_pendencias.md#55-correções-aplicadas-revisão-crítica-2026-08-21)
e em `docs/analise_critica_plano_v2.md`.

## Arquivos desta pasta

| Arquivo | Conteúdo |
|---|---|
| [01_algoritmos_e_dataset.md](01_algoritmos_e_dataset.md) | Os 5 algoritmos, correção do Ascon, especificação completa do dataset, RNG CTR_DRBG, wrappers |
| [02_features_e_selecao.md](02_features_e_selecao.md) | Suíte completa de features (com fontes) e o redesenho do seletor |
| [03_classificadores.md](03_classificadores.md) | Os 6 Caminhos (A–F), correção do SVM, réplicas da literatura |
| [04_protocolo_metricas_validacao.md](04_protocolo_metricas_validacao.md) | Split/CV, ablações, métricas, regra de relato obrigatória, controles, arcabouço estatístico |
| [05_execucao_riscos_pendencias.md](05_execucao_riscos_pendencias.md) | Ordem de execução, orçamento computacional, riscos, pendências |
| **[06_implementacao_passo_a_passo.md](06_implementacao_passo_a_passo.md)** | **Documento-norte executável** — fases, arquivos, critérios de aceite. Incorpora a rodada final de decisões (2026-08-21) e a análise crítica. **Em divergência com 01–05, o 06 prevalece.** |

## Ordem de execução (proposta, por dependência)

1. **Wrappers + RNG** — corrigir Ascon (`ascon128av13`), implementar Grain-128AEAD e Sparkle (KAT cada), implementar CTR_DRBG (validação CAVP)
2. **Dataset** — geração encadeada 5 algoritmos + script de validação v2
3. **Caminho A** (CPU) + ablações baratas (key-holdout on/off, truncamento do Grain, famílias de features)
4. **Caminhos B e C** (GPU)
5. **Caminho E** (Transformer — maior risco de engenharia, depois de B/C estabilizarem a infra)
6. **Caminho D** (híbrido — depende dos latentes de B, C e E)
7. **Caminho F** (meta-classificador — depende de A–E)

## Valores de referência (pré-calculados, para não diagnosticar errado)

| Cenário | Acaso | Colapso (prever sempre 1 classe) |
|---|---|---|
| 4 classes balanceadas (experimento principal) | F1-macro = 0,25 | F1-macro = **0,10** |
| 2 classes balanceadas (controle AES-ECB vs Ascon) | 0,50 | 0,333 |

Nota: no caso 4-classes o colapso fica **abaixo** do acaso por margem grande
(0,10 vs 0,25) — o inverso da intuição herdada do caso binário, onde colapso
(0,333) fica mais perto do acaso (0,50).
