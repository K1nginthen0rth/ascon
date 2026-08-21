# Análise completa do projeto — índice

Documentação técnica gerada a partir de leitura linha a linha de todo o repositório
(`src/`, `scripts/`, `tests/`, `docs/`, histórico git, memória de sessões anteriores)
em **2026-08-16**. Objetivo: ser a referência única e atualizada do que existe e do
que foi de fato executado, substituindo a necessidade de reconstruir esse contexto
a cada conversa nova.

Relação com os outros documentos do repositório:

| Documento | Papel |
|---|---|
| `CLAUDE.md` (raiz) | Regras vivas do projeto (regras de ouro, comandos). Deve ser sempre atual — corrigido nesta rodada em alguns pontos (ver [08_achados_e_pendencias.md](08_achados_e_pendencias.md)). |
| `CONTEXTO_ARTIGO.md` (raiz) | Snapshot detalhado gerado em 2026-06-04. Muito completo, mas parcialmente desatualizado (ver banner adicionado no topo do arquivo). Útil como registro histórico. |
| `docs/cnn_caminhos_b_c.md` | Descrição de arquitetura das CNNs (Caminhos B/C). Ainda válido, com uma correção de status aplicada. |
| `docs/contexto_inicial.md`, `docs/CONTEXTO_PARA_CLAUDE_WEB.md` | Registros de decisões de **2026-04-26** (antes da implementação começar). Históricos, não vivos — não foram alterados. |
| **`docs/analise_completa/` (esta pasta)** | Referência técnica corrente, cobrindo código, scripts, testes, datasets e resultados reais — incluindo o que os outros documentos ainda não refletem. |
| `docs/plano_experimento_v2/` | **Planejamento do próximo experimento** (2026-08-21): 4 algoritmos + controle, 6 caminhos, features/seletor redesenhados. Esta pasta (analise_completa) descreve o v1 concluído; aquela descreve o v2 planejado. |

## Como navegar

| Arquivo | Conteúdo |
|---|---|
| [01_criptografia.md](01_criptografia.md) | Wrappers Ascon-AEAD128, GIFT-COFB, AES-ECB, Vigenère; KAT; `dataset_generator.py` |
| [02_features_e_selecao.md](02_features_e_selecao.md) | As 307 features (6 famílias) e o seletor MI→mRMR→Boruta — **inclui mudança metodológica pendente de commit** |
| [03_modelos.md](03_modelos.md) | `classical.py`, CNN1D, CNN2D, `hybrid.py`, `metrics.py` |
| [04_datasets.md](04_datasets.md) | Todos os datasets gerados, vivos vs. legados, parâmetros e colisões de seed |
| [05_scripts.md](05_scripts.md) | Catálogo dos ~48 scripts de `scripts/` — o que cada um faz, vivo ou legado |
| [06_testes.md](06_testes.md) | Suíte de 130 testes pytest — cobertura por módulo |
| [07_resultados.md](07_resultados.md) | Resultados reais dos 4 Caminhos + controles + ablação — **corrige a narrativa de "B/C/D não executados"** |
| [08_achados_e_pendencias.md](08_achados_e_pendencias.md) | Lista consolidada de achados críticos, inconsistências e ações recomendadas |

## Pergunta de pesquisa e hipóteses (contexto para quem abrir só este arquivo)

Dissertação de mestrado (IME-RJ, orientador José Antonio Moreira Xexéo — dissertação
em `dissertacao/`, autor Nycolas Wenderson Da Silva dos Santos).

**Pergunta:** um adversário com acesso apenas ao criptograma (*ciphertext-only*)
consegue identificar se um texto cifrado foi gerado por Ascon-AEAD128 ou por
GIFT-COFB, sem acesso a chave, nonce ou plaintext?

- **H₀:** os dois algoritmos LWC padronizados NIST são praticamente indistinguíveis nesse cenário.
- **H₁:** existem assinaturas residuais exploráveis por ML.

**4 caminhos experimentais:**

| Caminho | Representação | Modelo |
|---|---|---|
| A | 307 features estatísticas clássicas | RF / SVM / LinearSVC / XGBoost / LR |
| B | CNN 1D sobre a sequência de bytes (CT completo, 65.552 bytes) | fim-a-fim ou extrator de latente (512D) → RF/LinearSVC |
| C | CNN 2D sobre mapa de co-ocorrência de bigramas 256×256 (CT completo) | fim-a-fim ou extrator de latente (128D) → RF/LinearSVC |
| D | Híbrido: 307D + latente CNN1D (512D) + latente CNN2D (128D) = 947D | RF / XGBoost |

## Resumo do estado atual (2026-08-16)

| Item | Status |
|---|---|
| Caminho A no dataset principal (60k, 64KB, 300 chaves) | ✅ Concluído. F1≈0,50 em todos os modelos — H₀ confirmada. |
| Caminhos B, C e D no dataset principal | ✅ **Foram executados** (provavelmente no Kaggle/GPU) e **também confirmam H₀** (F1≈0,50). Os números já estão redigidos em `dissertacao/resultados.tex`. **Mas os artefatos brutos (`cv_results.json`, `final_results.json`, `_final_cache.pkl`) não estão sincronizados neste repositório local** — só foram localizados para o Caminho D, em `C:\Users\nycol\Downloads\resultados_caminhoD_final\`. Ver [07_resultados.md](07_resultados.md) e [08_achados_e_pendencias.md](08_achados_e_pendencias.md). |
| Ablação do seletor de features (novo, 2026-08-12) | ✅ Concluída. Remove o seletor da equação (testa com as 307 features, com só as 29 que sobrevivem ao VarianceThreshold, com só o histograma, com só a 1 feature usada no relatório principal) + teste de permutação de rótulo. Resultado: H₀ se mantém em todos os braços — não é artefato do seletor. |
| Controles positivos (Vigenère) | ✅ Concluídos. Confirmam que o pipeline detecta sinal quando ele existe. |
| Pipeline de seleção de features | ⚠️ Mudança metodológica em andamento, **não commitada**: Boruta deixou de filtrar o conjunto final; agora é só diagnóstico. Ver [02_features_e_selecao.md](02_features_e_selecao.md). |
| Redação da dissertação | 🟡 Em andamento — `dissertacao/*.tex` já tem introdução, fundamentação, metodologia, resultados (completo com números dos 4 Caminhos) e conclusão escritos. |
| Testes automatizados | ✅ 130 testes, todos alinhados com o código atual (incluindo a mudança de Boruta). |

O achado mais importante desta análise: **o projeto está mais adiantado do que os
documentos vivos do repositório (CLAUDE.md, CONTEXTO_ARTIGO.md) sugerem.** Os
Caminhos B/C/D já rodaram e os quatro caminhos convergem para H₀, mas essa
informação só existia até agora espalhada entre `dissertacao/resultados.tex` e uma
pasta fora do repositório em `Downloads/`. Este pacote de documentos consolida
isso dentro do projeto.
