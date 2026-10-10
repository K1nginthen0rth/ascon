# Plano de execução — Experimento v3 em três dias (Kaggle/Colab)

Oct 7, 2026 · @Nycolas

Três dias, três resultados que se sustentam sozinhos, nesta ordem: a cota de sinal em escala (decide a frase central da dissertação), o piso como propriedade da implantação (reescreve a Tabela 1 como faixa) e os cubos passivos no Grain (a aposta). Tudo roda em notebooks Linux (Kaggle/Colab) com os cifradores compilados; o GIFT em Python puro entra só em lotes pequenos.

## Contexto em cinco linhas

A branch `piso-rodadas-v2` mede, para um observador passivo que vê só criptogramas e nonces de contador, até quantas rodadas o XOR de pares consecutivos separa cada AEAD de aleatório: Ascon 3/12, GIFT-COFB 3/40, Grain 28/256, Schwaemm 2/11 (contador zero, política `ambos`, BH-FDR q = 0,05, monotonicidade, teto de controle). `docs/suficiencia_dados.md` mostra que na rodada piso+1, com 3,1 milhões de pares, o SEI somado sobre os 640 bits fica abaixo de 2,3·10⁻⁵: viés espalhado está excluído; viés concentrado num bit ou numa paridade, entre 0,06% e 0,24%, ainda não foi testado. O Ascon do build (`ascon128av13`) é o Ascon-AEAD128 do SP 800-232 (IV `0x00001000808C0001`, carga little-endian), confirmado por `tests/test_crypto_independente.py`. O contador big-endian do v2 põe o bit 0 no byte 15, que o Ascon carrega no bit 56 de x4; a triagem de setembro deu 0,85 por par em 3 rodadas com contador little-endian (bit 0 de x3) contra 0,64 em big-endian. No GIFT-COFB o nonce atravessa duas cifragens antes de C1 (AD vazio vira um bloco de padding; 1 bloco de AD também dá duas chamadas; 2 blocos, três), então exposição = r × (1 + max(1, n\_ad)).

## Decisões fixadas

1. Modelo de ameaça inalterado: ciphertext-only, mesma chave por dispositivo, contador público, claros de texto Gutenberg em inglês, distintos e desconhecidos. Nada de claro escolhido.
2. Política `ambos` em todo lugar (`pa = r`, `pb = min(r, 8)`; `big = r`, `slim = min(r, 7)`), para comparar com a Tabela 1.
3. Bit limpo = posição onde o XOR (ou a soma módulo 2, para cubos) dos claros é determinística, estimada do corpus com 100 mil trechos de 64 bytes (`p >= 0,999`), nunca assumida. Esperado antes de medir: bit 7 de cada byte. **Medido em 08/10: no corpus atual nenhum bit passa de 0,999** (3,2% dos bytes são ≥ 0x80; o bit 7 do XOR de dois trechos é zero com probabilidade ≈ 0,955). Ver decisão em aberto sobre a fonte.
4. Detector primário = contagem por bit em streaming, sem cache, com o máximo de z² e correção de Šidák sobre todos os bits do primeiro bloco de taxa (128 no Ascon, GIFT e Grain; 256 no Schwaemm), com os bits limpos (ou ponderados pelo viés do texto) como teste secundário. Escolha feita olhando os dados do piso, não do piso+1: no Grain, o sinal do piso não está no bit 7 (|z| = 1,9 no clock 28), e sim nos bits 6, 5 e 3; a soma sobre os 640 bits entra só como réplica do SEI. Nada é estimado em treino, então todos os dispositivos são teste.
5. Duas famílias de testes pré-registradas, cada uma com seu BH-FDR (q = 0,05): primária (uma configuração por algoritmo na rodada piso+1, bloco de taxa inteiro) e exploratória (paridades, layouts, cabeçalhos, cubos). Viés mínimo detectável declarado antes dos dados, por M.
6. Controles obrigatórios em toda configuração: braço `aleatorio` (claros uniformes; qualquer detecção ali é falso positivo e invalida o detector) e rodada de especificação como teto.
7. Reutilizar `floor_algos.py` (variantes), `gift_pure_cipher.py`, `CTRDRBG` com um `label` por fonte, `apply_bh_fdr`, `_TextPlaintextSampler` e o esquema JSONL de `report_floor.py`; ler os docstrings antes de escrever código.

## Primeira hora: infraestrutura

- [ ] `vendor_sources.py` baixa as fontes com a internet do notebook ligada; `build_variant.py` compila no Linux (o repo foi feito pensando em `.pyd` do Windows: trocar extensão e flags do compilador se preciso).
- [ ] Medir a vazão real (cifragens/s por núcleo) do Ascon, Schwaemm e Grain reduzidos via CFFI, e ajustar as metas de pares do dia 1 ao que a sessão entrega.
- [x] O GIFT-COFB vendorizado não tem `ref` com laço por rodada (só `opt32` fixsliced, de 5 em 5, e assembly). Escrever a rodada em C a partir da reimplementação de `tests/test_crypto_independente.py`, time-box de 2 h, validando contra os vetores embutidos e contra `PureGiftCOFB` em 1, 2, 3 e 40 rodadas; se estourar, o GIFT fica fora da escala.
- [ ] Checkpoint das contagens parciais a cada 10⁷ pares no Drive ou num dataset do Kaggle, com seed por shard, para sobreviver ao limite de sessão e para a curva piso(N).

## Dia 1: a cota de sinal em escala

Um notebook por algoritmo, em paralelo: Ascon rodada 4, Schwaemm rodada 3, Grain clock 29, GIFT rodada 4 se a rodada em C ficar pronta (e as rodadas piso para calibração), braços texto e aleatório, contador zero. O laço inteiro em C para não pagar Python por mensagem: 100 pares por dispositivo (nonces 2j e 2j+1 big-endian, j < 100, a mesma vizinhança do v2), chaves geradas pelo CTR_DRBG em Python e passadas ao C, claro tirado de um buffer com 10⁶ trechos do corpus com os índices também sorteados pelo DRBG em lotes NumPy e passados ao C (sem xorshift), reamostrando quando P1 = P2, XOR do primeiro bloco de taxa e da tag, e acumulação em três vetores: contagem de 1 por bit, contagem das paridades de dois bits entre todos os bits do bloco (8 128 no bloco de 128 bits; é onde a rede venceu a contagem de bits no GIFT), e M. Metas: 10⁹ pares no Ascon e no Schwaemm, 10⁸ no Grain (o `ref` é bit a bit). Estatísticas: z\_b por bit, máximo de z² com Šidák no bloco de taxa (família primária, 3 ou 4 testes), idem nas paridades (exploratória), e a soma sobre 640 bits como réplica do SEI. Entrega: por algoritmo, ou a rodada a mais, ou a cota de viés por bit (0,003% a 0,01%), mais a curva piso(N) de 10⁶ a 10⁹ tirada dos checkpoints. Escrever o resultado no mesmo dia, mesmo negativo: o negativo em 10⁹ pares é a parte mais forte do argumento.

**Resultado do Dia 1 (08 e 09/10).** GIFT rodada 4 detectada com ~10⁷ pares (paridades entre metades de 64 bits, z = 140 em 10⁹; rodadas 5 e 6 no acaso, a 5 com 10¹⁰); Ascon rodada 4 detectada com 10¹⁰ pares (paridade 66,104, z = −7,85) e confirmada em réplica independente com mais 10¹⁰ (z = −7,91); Schwaemm 3 (10¹⁰) e Grain 29 (10⁹) no acaso. Pisos com este detector: Ascon 4, GIFT 4, Grain 28, Schwaemm 2. Laço em C validado contra o caminho de referência; GIFT de uma rodada em C validado contra o `PureGiftCOFB` e o binário. Rodou localmente (12 núcleos), não no Kaggle. Ver `build/reduced_rounds/floor_v2/RESULTADOS_2026-10-09.md`.

## Dia 2: o piso como propriedade da implantação

Lotes de 300 dispositivos × 100 mensagens, rodadas piso−1 a piso+2, contador zero, braços texto e aleatório, três eixos independentes:

| Eixo | Valores | Algoritmos | O que responde |
| --- | --- | --- | --- |
| Layout do contador | big-endian no fim (v2); little-endian no início; no Ascon, também big-endian no byte 7 (bit 56 de x3) | os quatro | se a Tabela 1 depende de onde o fabricante pôs o contador; no Ascon, se o little-endian leva o piso a 4 |
| Cabeçalho fixo no claro | 0, 8 e 16 bytes constantes no início de cada mensagem (resto texto) | os quatro | quanto o piso sobe quando os bits limpos vão de 16 para 64 e 128 por bloco; ponte para o teto de texto conhecido |
| Blocos de AD | 0, 1 e 2 blocos de 16 bytes, constantes por dispositivo | só GIFT, rodadas 1 a 6 | H6: piso 3 com 0 ou 1 bloco e 2 com 2 blocos; se cair já com 1, o mecanismo de exposição está errado |

Detector: a contagem por bit do dia 1 (em Python/NumPy aqui, M é pequeno) e o XGBoost do v2 por par, para manter a comparação com a Tabela 1. São cerca de 40 lotes; o GIFT puro custa 30 s por lote. Entrega: a Tabela 1 reescrita como faixa por algoritmo (piso mínimo e máximo entre layouts), o piso em função dos bytes de cabeçalho, e a coluna de rodadas de exposição ao lado de rodadas e fração da spec. Acrescentar a `floor_algos.py` a função `exposicao(algo, rounds, n_ad_blocks)` sem alterar nada existente.

**Resultado do Dia 2 (09/10).** Layout little-endian: Ascon 4 (r4 com 10⁸), GIFT 3, Schwaemm 1, Grain sem piso. Cabeçalho constante: Grain 30, GIFT 4, Ascon 3, Schwaemm 2. AD no GIFT: 0 e 1 bloco piso 4, 2 blocos piso 2 (exposição ~8 rodadas nos três). Ver RESULTADOS_2026-10-09.md.

## Dia 3: cubos passivos no Grain e os brindes

Só no Grain, porque é o único em que o grau cresce devagar o bastante para um cubo de dimensão 10 sobre o contador ter chance, e porque 28 de 256 clocks é onde há mais espaço. Expectativa declarada como indefinida: a ausência de viés de primeira ordem no bit 7 perto do piso não diz nada sobre o grau. **Roda no modelo de cabeçalho constante** (ver acima); no texto livre fica inviável; no texto livre, com 3,2% de bytes ≥ 0x80, a soma de 2^d bits 7 só zera com probabilidade (1 + 0,955^(2^(d−1)))/2, ≈ 0,73 em d = 4, 0,52 em d = 6 e 0,50 em d = 10; sem trocar a fonte, cubos de dimensão 6 ou mais não têm nenhuma posição em que os claros se cancelem. Lotes de 300 dispositivos × 1024 mensagens, contador zero (o cubo sobre os d bits baixos sai sem alinhamento), clocks 24 a 48 de 2 em 2 e depois 64, 96 e 128, braços texto e aleatório; cerca de 9 milhões de cifragens. Para cada d de 1 a 10 e cada posição limpa do bloco 1, a soma módulo 2 dos 2^d criptogramas em blocos consecutivos de índices é a soma do keystream sobre o cubo (os claros somam zero nas posições limpas). Reportar dois níveis: zero-sum exato (fração de cubos com soma 0 igual a 1,0) e viés (máximo de z² sobre as posições limpas, com Šidák), e a consistência d = 1 com o detector de pares. Critério de parada: sem viés até o clock 40, encerra e vira trabalho futuro. Brindes, em paralelo e sobre o que já existe: ablação por região (bloco 1, blocos 2 a 4, tag) nos caches da curva, para saber se a tag carrega sinal na política `ambos`; e a figura de importância do RF por posição de bit no piso, que mostra o classificador encontrando os bits limpos sem saber criptografia.

## Resultados das análises de custo zero (08/10, caches atuais)

- **Grain: o viés depende de c + 2t, não de c + t.** Na referência, a cifragem usa só os bits pares da pré-saída, e entre a inicialização reduzida e o primeiro bit de keystream há 128 clocks de ADDKEY e 16 de AD, sem realimentação: o bit t sai no clock c + 144 + 2t. Estimando o viés do keystream nos bits 7, 6 e 5, o viés em (c + 2, t) tem correlação 0,985 com o de (c, t + 1); na mesma posição, −0,20; na hipótese c + t, −0,13. A não monotonicidade entre 1 e 12 clocks é o bit enviesado caindo ou não numa posição redundante do texto. O piso do Grain passa a ser reportado também na escala c + 2t.
- **Schwaemm: no piso, os bytes 24 a 31 vazam P1 ⊕ P2.** O viés observado no bit 7 é 0,997 vezes o do XOR dos textos: diferença de keystream nula ali. No piso+1 (3 passos), nada nesses bytes.
- **Fonte: o corpus não é ASCII.** 3,2% dos bytes são ≥ 0x80; 56 dos 85 livros têm mais de 1% (provavelmente pontuação tipográfica em UTF-8), e dois têm 67% e 93% (escrita não latina, a conferir). Para pares o efeito é só atenuar (fator 0,91 no bit 7); para cubos de dimensão alta, inviabiliza.

**Resultado do Dia 3 (09/10).** Cubos no Grain, modelo de cabeçalho: detectado até o clock 44 (d = 3 a 5; z = 22 com 30 000 dispositivos), 46 a 128 no acaso; zero-sum exato até 32; controle limpo em tudo.

## Fora deste ciclo (trabalho futuro no texto)

Cubos no Ascon, Schwaemm e GIFT (o contador entra em posição ruim e a soma só é lida em 16 das 128 posições de saída); paridades de três bits; agregação por dispositivo como experimento próprio (as bolsas da curva já responderam); corpora em português e chinês; GIFT em escala, salvo se a `ref` tiver laço por rodada; redes neurais grandes.

## Dia 0 (antes de tudo): a fonte

*Decidido em 08/10: `texto-en` é a fonte principal; o HTML (`texto-html`) fica como segunda fonte na tabela de robustez; no v1 e no v2 a correção é só de descrição.* Resultado da varredura (08/10): Ascon 3, GIFT 3 e Schwaemm 2 nas duas fontes; Grain 28 no HTML (4 de 9 células, 29 a 31 no acaso) e 29 no `texto-en` (1 de 9 células, bolsa de 100 a 60,6%, no limiar). Aumento de amostra declarado (Grain em 28, 29, 30 e 256, 3 000 dispositivos, as duas fontes e o aleatório, `floor_v2/contador_zero_grain3000/`): 28 com 9 de 9 células nas duas fontes, 29 no acaso nas duas. O 29 com 300 dispositivos era falso positivo no limiar; o piso do Grain é 28 nas duas fontes, e os quatro pisos não mudam entre HTML e prosa.

O corpus usado até aqui (`data/raw/corpora/`) é HTML bruto do Gutenberg em 84 de 85 arquivos (cerca de 23% de markup), com dois livros em chinês, um em tagalo, um em alemão e um e-mail da base Enron. Ele passa a se chamar `texto-html` (braço `texto` do `run_floor.py`). O `texto-en` (`montar_corpus_en.py` → `data/raw/corpora_en/`) tem os 80 livros em inglês, sem markup, com pontuação transliterada e só ASCII (0,87% de caracteres não ASCII antes da transliteração). Varredura de 1 a piso+2 nos quatro algoritmos, 300 dispositivos, contador zero, braços `texto-en` e `aleatorio`, critério do `report_floor.py`, em `floor_v2/contador_zero_corpus_en/`. A Tabela 1 passa a ter as duas fontes lado a lado; a diferença é o resultado de dependência da fonte. Decidido: a escala do Dia 1 roda sobre o `texto-en`, depois do aumento de amostra do Grain, com o fator (2p − 1) por bit remedido pelo amostrador nos pares reais e usado como peso (sem limiar de 0,999).

## Dois modelos de claro

*Decidido em 08/10: aceito como segundo modelo de claro, com nome próprio, separado da Tabela 1. Ele relaxa explicitamente a regra de 13/09 (saber que o bloco 1 é igual entre mensagens é conhecimento sobre a relação entre os claros), e o texto deve dizer isso; a Tabela 1 continua só com texto livre.*

- **Texto livre** (Tabela 1): claros distintos e desconhecidos. Cubos inviáveis em dimensão alta, porque a soma dos claros não se anula.
- **Cabeçalho constante de valor desconhecido** (teto): os primeiros 16 bytes iguais em todas as mensagens do dispositivo, valor não conhecido pelo atacante. É o mesmo conteúdo de informação do XOR com claro igual no bloco 1, então nunca entra na Tabela 1. Usado no eixo de cabeçalho do Dia 2 (0 bytes = Tabela 1, 16 bytes = teto) e nos cubos do Dia 3, onde a soma dos claros zera nos 128 bits do bloco 1. Controle: cabeçalho aleatório por mensagem.

No Grain: no texto livre, reportar o piso na janela dos primeiros 16 bits de keystream (t < 16) e no bloco inteiro; no modelo de cabeçalho, a curva por c + 2t completa, com a ressalva de que os 144 clocks e os 2t são sem realimentação da saída (e os 128 de ADDKEY com a chave reinjetada), então não viram clocks equivalentes de inicialização.

## Saída e aceite

- [ ] Uma linha JSONL por configuração (algoritmo, rodada, braço, eixo, valor, detector, família, M, estatística, p-valor, `git_sha`, `seed`, `tempo_s`), no esquema que `report_floor.py` lê; relatório gerado em `docs/exp_contador.md` com a tabela de cota por algoritmo, a Tabela 1 como faixa, a curva piso(N), o piso × cabeçalho, o resultado do Grain e a lista de falsos positivos no braço aleatório, mesmo que vazia.
- [ ] Reprodução dos pisos 3/3/28/2 pelo detector primário (bloco de taxa inteiro) no layout do v2 e com a fonte original, antes de qualquer resultado novo; se ficar abaixo em algum, o pipeline está errado e para aí.
- [ ] Zero detecções no braço aleatório e nas rodadas de especificação.
- [ ] Viés mínimo detectável declarado por configuração antes de olhar os dados.
- [ ] Testes em `tests/test_exp_contador_*.py`: determinismo por seed, máscara de bits limpos em ASCII sintético (só o bit 7) e em claros aleatórios (nenhum), p-valores uniformes sob H0 (200 réplicas, KS p > 0,01), sinal plantado de 0,5% num bit detectado com 10⁵ pares, soma de cubo zero para um cifrador de brinquedo de grau 3 com d ≥ 4, pares por posição com diferença exatamente 2^j, `exposicao("gift", 3, 0) == 6` e `exposicao("gift", 3, 2) == 9`.
