# Documentação do projeto

Dissertação de mestrado do IME-RJ (orientador Xexéo) sobre classificação de
algoritmos AEAD leves por aprendizado de máquina em cenário ciphertext-only.

As regras vivas do projeto (regras de ouro, comandos de build, arquitetura do
código) ficam no `CLAUDE.md` da raiz, não aqui. Esta pasta guarda o registro dos
experimentos, a revisão de literatura e os textos escritos para o orientador.

## Onde está o quê

| Arquivo | O que é | Estado |
|---|---|---|
| [piso_rodadas.md](piso_rodadas.md) | Estudo de piso de rodadas: protocolo, números por algoritmo, ressalvas e o que falta | Linha de trabalho corrente |
| [v1_experimento_concluido.md](v1_experimento_concluido.md) | Experimento v1 (Ascon vs GIFT-COFB, 60k): dataset, features, os 4 caminhos, resultados, ablação, controles | Encerrado em agosto de 2026 |
| [plano_experimento_v2/](plano_experimento_v2/) | Plano do experimento v2 (4 algoritmos, 6 caminhos, 180k amostras). Ver o `README.md` da pasta | Código pronto, execução pendente |
| [relatorio_orientador_piso_rodadas.md](relatorio_orientador_piso_rodadas.md) | Texto escrito para o orientador sobre o que a literatura fez e onde este trabalho difere | Enviado em setembro de 2026 |
| [referencias_e_posicionamento.md](referencias_e_posicionamento.md) | Bibliografia de seleção de atributos pronta para citar, mais o posicionamento crítico de Sikdar & Kule, Bhavya Shree e De Mello & Xexéo | Registro de abril de 2026 |
| [RSL_completa.txt](RSL_completa.txt) / [RSL_resumida.txt](RSL_resumida.txt) | Revisão sistemática, 21 estudos | Material-fonte |
| [pesquisa_distinguishers/RELATORIO.md](pesquisa_distinguishers/RELATORIO.md) | Série de nove buscas independentes sobre técnicas de distinção, com os prompts na íntegra | Material-fonte, setembro de 2026 |
| [Analise_sbseg_artigo.txt](Analise_sbseg_artigo.txt) | Os quatro pareceres do SBSeg | Material-fonte |
| Relatorio_de_acompanhamento_final.pdf | Relatório de acompanhamento entregue em junho de 2026 | Registro |

## Uma coisa que vale saber antes de citar qualquer número

Os três experimentos respondem perguntas diferentes e não são intercambiáveis:

- **v1** pergunta se Ascon-AEAD128 e GIFT-COFB, com rodadas completas, são
  separáveis um do outro. Resposta medida: não, F1 com IC cobrindo 0,50 nos
  quatro caminhos.
- **v2** estende isso para quatro algoritmos e seis caminhos, com dataset de
  180 mil amostras. Não executado.
- **piso de rodadas** pergunta outra coisa: quantas rodadas cada algoritmo
  precisa para que a saída pare de ser separável de aleatório. É por algoritmo,
  não um contra o outro. Pisos (pior caso testado): Ascon-AEAD128 3 de 12,
  GIFT-COFB 3 de 40, Grain-128AEAD 28 de 256, Schwaemm256-128 2 de 11. O GIFT e
  o Grain dependem do estado do contador de nonce; ver `piso_rodadas.md`.

## O que saiu daqui, e por quê

Limpeza de 26 e 27 de setembro de 2026. Tudo abaixo era rastreado pelo git e
segue recuperável pelo histórico, com uma exceção anotada no fim:

- `analise_completa/` (9 arquivos, agosto de 2026) virou
  `v1_experimento_concluido.md`, junto com `cnn_caminhos_b_c.md`.
- `CONTEXTO_ARTIGO.md` (raiz) era snapshot de junho de 2026 e o próprio banner
  dele apontava que estava desatualizado em quatro pontos. O sucessor correto é
  `v1_experimento_concluido.md`.
- `CONTEXTO_PARA_CLAUDE_WEB.md` e `relatorio_para_claude.md` eram, um, um
  briefing de abril de 2026 para outra ferramenta, e o outro, um modelo de
  prompt. Nenhum dos dois é documentação do projeto.
- `===================================.txt` era um recorte parcial da RSL com
  nome quebrado, 92,9% idêntico ao começo de `RSL_completa.txt`.
- `analise_critica_plano_v2.md` e `relatorio_orientador_novo_experimento.md`
  foram para dentro de `plano_experimento_v2/`, como `08_analise_critica.md` e
  `00_resumo_decisoes.md`, porque é do plano v2 que os dois tratam.
- `plano_piso_ascon.md` foi absorvido por `piso_rodadas.md`. É a exceção: não
  estava rastreado pelo git, então não há versão anterior para recuperar. O que
  ele tinha de específico, a previsão numérica para o eixo `pb` e as quatro
  fontes que apontavam para ela, está na seção 3 de `piso_rodadas.md`, junto do
  resultado que não a confirmou.
