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
| Dataset | 60k amostras, 100% SPGC | **180k** encadeado (6 "algoritmos" × 30k, incluindo PRNG), 80% texto / 20% imagem |
| RNG de geração | NumPy PCG64 | CTR_DRBG AES (NIST SP 800-90A), validado por CAVP |
| Caminhos | A–D | A–F (novo: E=Transformer, F=meta-classificador) |
| Features | 307 | **641 medidas** (a estimativa de projeto era ~400+): NIST SP 800-22 completo + 5 da literatura + tag/payload, janela comum de 8 bytes. Duas são constantes por construção (Overlapping Template, estruturalmente inelegível em 64KB) — **639 informativas** |
| Seletor | VT bruto → MI top-k → mRMR → Boruta(diag) | z-score → VT → MI (corte generoso, não-estatístico) → mRMR → Boruta(diag) |
| Controle positivo | Vigenère | AES-128-ECB vs Ascon (resposta direta ao SBSeg) |
| Controles negativos | — (nunca executados) | 🔶 PRNG puro + embaralhamento de bytes |
| Validação estatística | IC bootstrap + McNemar | + 🔶 poder a priori, hipótese primária + FDR, pré-registro |
| Relato | prints ad-hoc por script | **função única obrigatória**: toda métrica impressa na hora + matriz de confusão sempre (console + JSON + PNG) + predição/probabilidade por amostra (pré-requisito do Caminho F) |

## Arquivos desta pasta

| Arquivo | Conteúdo |
|---|---|
| [01_algoritmos_e_dataset.md](01_algoritmos_e_dataset.md) | Os 5 algoritmos, correção do Ascon, especificação completa do dataset, RNG CTR_DRBG, wrappers |
| [02_features_e_selecao.md](02_features_e_selecao.md) | Suíte completa de features (com fontes) e o redesenho do seletor |
| [03_classificadores.md](03_classificadores.md) | Os 6 Caminhos (A–F), correção do SVM, réplicas da literatura |
| [04_protocolo_metricas_validacao.md](04_protocolo_metricas_validacao.md) | Split/CV, ablações, métricas, regra de relato obrigatória, controles, arcabouço estatístico |
| [05_execucao_riscos_pendencias.md](05_execucao_riscos_pendencias.md) | Ordem de execução, orçamento computacional, riscos e pendências |
| **[06_implementacao_passo_a_passo.md](06_implementacao_passo_a_passo.md)** | **Documento-norte executável** — fases, arquivos, critérios de aceite. Incorpora a rodada final de decisões (2026-08-21). **Em divergência com 01–05, o 06 prevalece.** |
| **[07_runbook_execucao.md](07_runbook_execucao.md)** | **Sequência exata de comandos** para rodar o experimento do dataset ao consolidado — o que falta é EXECUTAR, não implementar (ver estado abaixo). |

## Estado atual (2026-08-22) — todo o código está implementado

**Fases 0–11 têm código completo e testado (253/253 testes).** O gargalo
agora é rodar, não escrever: a extração de features nas 180k amostras
reais leva ~20h por braço (`controlado`/`cru`/`shuffled`), e os Caminhos
B/C/E dependem de sessão de GPU (Kaggle/Colab). Sequência exata de
comandos: [07_runbook_execucao.md](07_runbook_execucao.md). Detalhe
fase-a-fase do que está pronto: [06_implementacao_passo_a_passo.md](06_implementacao_passo_a_passo.md)
(status em cada cabeçalho de Fase).

## Ordem de execução (ver 07 para os comandos exatos)

1. **Wrappers + RNG** ✅ — Ascon (`ascon128av13`), Grain-128AEAD, Sparkle (KAT cada), CTR_DRBG (CAVP)
2. **Dataset** ✅ — 180k amostras geradas e validadas (PASS)
3. **Extração de features** ⏳ — código pronto, ~20h/braço, ainda não rodada
4. **Caminho A** (CPU) ✅ código pronto — clássicos + stacking + 3 réplicas + ablações + permutação
5. **Caminhos B e C** (GPU) ✅ código pronto — inclui as 3 variantes de condicionamento da CNN2D e a réplica E05
6. **Caminho E** (Transformer) ✅ código pronto
7. **Caminho D** (híbrido) ✅ código pronto — latentes alinhados por fold
8. **Caminho F** (meta-classificador) ✅ código pronto — avalia no teste canônico
9. **Consolidação** ✅ código pronto — BH-FDR, McNemar+Bonferroni, estratificação de erro

## Valores de referência (pré-calculados, para não diagnosticar errado)

| Cenário | Acaso | Colapso (prever sempre 1 classe) |
|---|---|---|
| 4 classes balanceadas (experimento principal) | F1-macro = 0,25 | F1-macro = **0,10** |
| 2 classes balanceadas (controle AES-ECB vs Ascon) | 0,50 | 0,333 |

Nota: no caso 4-classes o colapso fica **abaixo** do acaso por margem grande
(0,10 vs 0,25) — o inverso da intuição herdada do caso binário, onde colapso
(0,333) fica mais perto do acaso (0,50).
