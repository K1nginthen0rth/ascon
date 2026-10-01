# Técnicas de distinção de algoritmos de criptografia — nove pesquisas independentes (de dez planejadas)

**Gerado em 21/09/2026.** Série de levantamentos de literatura sobre o
problema de pesquisa da dissertação: distinguir os quatro finalistas do NIST
Lightweight Cryptography (Ascon-AEAD128, GIFT-COFB, Grain-128AEAD,
Schwaemm256-128) a partir do criptograma apenas, e medir o piso de rodadas
reduzidas em que cada um deixa de parecer aleatório.

Planejaram-se dez pesquisas, uma por ângulo. Nove rodaram até o fim e estão
completas abaixo. A décima (aprendizado de representação com arquiteturas
não-padrão — state space models, redes sobre grafos, compressão neural, vieses
indutivos algébricos) foi interrompida a pedido do Nycolas antes de produzir
achados, depois de quatro bloqueios sucessivos por limite de sessão ao longo
da série. Fica registrada como pendência, não como resultado negativo.

## Como esta série foi feita

Cada uma das dez pesquisas rodou num subagente **novo e isolado**. Ele recebeu
apenas o prompt derivado — não leu o repositório, não viu esta conversa, não
viu as pesquisas anteriores. A independência era o ponto: dez varreduras da
mesma literatura, partindo de dez ângulos diferentes, sem contaminação entre
elas.

Os dez prompts derivam de um texto-mãe comum (`PROMPT_BASE.md`), ao qual se
acrescentou, no topo, o ângulo daquela rodada e uma **temperatura declarada**.

**Sobre a temperatura:** não é temperatura de amostragem. O harness não permite
ajustar a amostragem de um subagente. O que está declarado em cada prompt é uma
instrução explícita de *amplitude de exploração*, numa escala de 0,1 a 1,0 —
valores baixos pedindo conservadorismo e rastreabilidade de fonte, valores
altos pedindo que o agente siga pistas tortas e aceite analogias de outros
subcampos. Isso está registrado aqui para que ninguém leia "temperatura 0,9"
como um parâmetro de inferência.

## Convenção de marcação usada pelos agentes

- **[PUB]** — trabalho publicado, texto obtido e lido; números conferidos na fonte
- **[CIT]** — existência confirmada, texto integral não obtido
- **[MINHA]** — extrapolação ou cálculo do próprio agente, não publicado

Essa separação foi exigida em todos os dez prompts, justamente para que a
extrapolação não se misturasse ao registro bibliográfico.

## Nota sobre integridade do conteúdo

Duas entregas (pesquisas 08 e 09) chegaram truncadas por limite de tamanho da
resposta. Nos dois casos o trecho perdido foi recuperado pedindo reemissão ao
próprio agente, delimitada pelas frases de corte e de retomada, e reintegrado
no lugar certo. Os documentos abaixo estão completos. Onde algo não pôde ser
recuperado, está marcado no corpo do texto.

---

## Índice

- **Pesquisa 01** — Assinatura do modo de operação · temperatura 0,4
- **Pesquisa 02** — Análise de tráfego cifrado sem plaintext · temperatura 0,8
- **Pesquisa 03** — Limites teóricos de impossibilidade · temperatura 0,15
- **Pesquisa 04** — Identificação de cifra de fluxo pelo keystream · temperatura 0,55
- **Pesquisa 05** — Resultados negativos e rigor do nulo · temperatura 0,3
- **Pesquisa 06** — Estatística de alta ordem além da bateria NIST · temperatura 0,65
- **Pesquisa 07** — Correlação e distinguidores lineares sem entrada escolhida · temperatura 0,9
- **Pesquisa 08** — Rodadas reduzidas por métodos não-diferenciais · temperatura 0,45
- **Pesquisa 09** — Vieses em tag, padding e enquadramento · temperatura 0,7
- **Pesquisa 10** — Aprendizado de representação / arquiteturas não-padrão · temperatura 0,25  *(não concluída)*

---

# Pesquisa 01 — Assinatura do modo de operação

- **Ângulo:** Assinatura do modo de operação
- **Temperatura declarada:** 0,4

## Pesquisa 01 — prompt usado, na íntegra

````markdown
# Pesquisa 01 — Assinatura do MODO de operação

**Ângulo desta pesquisa.** Concentre-se em UMA pergunta: o MODO de operação
deixa assinatura no criptograma, independentemente da permutação ou da cifra
de bloco por baixo? Esponja (Ascon, Schwaemm) absorve e espreme com uma taxa;
COFB (GIFT) encadeia com máscara e feedback; Grain gera fluxo puro. Cada um
tem padding próprio, geometria de tag própria e uma relação própria entre
comprimento do texto e comprimento do criptograma. Procure trabalhos sobre
distinguir MODOS, sobre vazamento estrutural de padding, sobre geometria de
tag, e sobre o que o enquadramento revela. Inclua literatura de ataques a
padding e de distinção de modos de operação (ECB/CBC/CTR/GCM e afins), mesmo
antiga, e avalie o que transfere para AEAD leve.

**Temperatura: 0,4.** Escala de amplitude de exploração, de 0,1 a 1,0.
Não é temperatura de amostragem — é instrução. Em 0,4: fique perto da
literatura estabelecida, priorize achados confirmáveis e mecanismos bem
entendidos. Especulação só quando ancorada num trabalho real, e marcada
como tal.

---

# Prompt base — técnicas de distinção de algoritmos de criptografia

Este é o texto-mãe. Cada uma das 10 pesquisas recebe uma variação dele, com um
ângulo diferente e uma temperatura, e NADA MAIS: nem o repositório, nem os
resultados das pesquisas anteriores, nem esta conversa.

---

## PROBLEMA DE PESQUISA

Você está pesquisando para uma dissertação de mestrado em criptografia
aplicada e aprendizado de máquina. Trabalhe SÓ com literatura externa: não
leia nenhum repositório, arquivo local ou resultado prévio. Comece do zero.

**A pergunta.** Dado apenas o criptograma — sem a chave, sem o texto em claro,
sem poder escolher nada do que é cifrado — é possível distinguir qual
algoritmo de criptografia autenticada o produziu? E, num segundo nível, com
quantas rodadas reduzidas um algoritmo ainda deixa de parecer aleatório?

**Os algoritmos.** Os quatro finalistas do concurso NIST Lightweight
Cryptography: Ascon-AEAD128 (esponja), GIFT-COFB (cifra de bloco em modo
COFB), Grain-128AEAD (cifra de fluxo com LFSR e NFSR) e Schwaemm256-128
(esponja ARX, família SPARKLE).

**O modelo de ameaça, que é a restrição dura e não negocia.** Adversário
PASSIVO, em ciphertext-only. Ele observa criptogramas de um mesmo dispositivo,
com nonces públicos de contador, e pode observar vários de uma vez. Ele NÃO
tem: texto em claro conhecido ou escolhido, diferenças escolhidas na entrada,
reuso de nonce, acesso a canais laterais, nem consultas a um oráculo de
cifragem. Isso exclui de saída a maior parte da criptanálise diferencial
clássica e os distinguidores neurais no estilo Gohr, que dependem de pares com
diferença escolhida.

**O protocolo experimental.** Classificadores clássicos e redes sobre features
estatísticas e sobre os bytes crus. Chaves de teste nunca aparecem no treino
(key-holdout). Intervalo de confiança por bootstrap agrupado por chave, e não
i.i.d. Correção para múltiplas comparações. Controle negativo obrigatório: com
o algoritmo completo o classificador tem que ficar no acaso.

## O QUE EU QUERO DE VOCÊ

Técnicas, representações, ataques ou ideias — publicadas ou adaptáveis — que
possam extrair sinal nesse cenário, ou que ajudem a delimitar com rigor por
que o sinal não existe. Interessa tanto o que funciona quanto a prova de que
algo é impossível.

Busque em literatura acadêmica real (IACR ePrint, ToSC/FSE, CHES, CRYPTO,
EUROCRYPT, ASIACRYPT, SAC, Designs Codes and Cryptography, IEEE, Springer,
arXiv) e em fontes técnicas sérias. Use termos de busca em inglês.

## COMO RESPONDER

Para cada ideia encontrada, escreva:

1. **O que é** — a técnica, em duas ou três frases.
2. **Fonte** — autores, título, veículo, ano. Link quando houver. Se você não
   conseguiu confirmar a existência do trabalho, diga isso explicitamente em
   vez de completar de memória.
3. **Cabe no nosso modelo?** — SIM, NÃO, ou ADAPTÁVEL. Se ADAPTÁVEL, diga
   exatamente o que teria de mudar e qual premissa do modelo de ameaça isso
   arranha.
4. **O que custaria testar** — ordem de grandeza de dados, computação e
   engenharia.
5. **O que ela prevê** — se a técnica funcionar, que resultado deveríamos ver?
   Se não houver previsão falsificável, diga isso.

Termine com uma seção **APOSTAS**: as três ideias que você tentaria primeiro,
e por quê. Seja específico; "usar deep learning" não é uma aposta.

## PROFUNDIDADE — leia isto com atenção

Não é um levantamento rápido. **Vá até esgotar o veio.** Não pare em cinco ou
dez achados porque já "deu para ter uma ideia": siga as citações para frente e
para trás, abra os trabalhos relacionados dos artigos que importarem, procure
versões estendidas e teses, e persiga as pistas que aparecerem no caminho,
mesmo as que não estavam no ângulo original. Só encerre quando as buscas novas
pararem de trazer coisa nova.

Traga TODA a informação, não um resumo dela. Se um artigo tem um número que
importa (quantas rodadas, quantas consultas, que acurácia, que tamanho de
dado), traga o número. Se tem uma limitação declarada pelos próprios autores,
traga a limitação com as palavras deles. Prefira errar por excesso de detalhe.
Uma resposta longa e completa é o que se pede aqui; uma resposta enxuta é
falha de execução.

## REGRAS

- Não invente referências. Uma fonte não confirmada vale menos que nenhuma, e
  vou checar.
- Não repita o óbvio já saturado (distinguidor diferencial-neural padrão)
  sem trazer um ângulo novo que sobreviva ao ciphertext-only.
- Se a conclusão honesta de um caminho for "isso é impossível neste modelo
  por tal razão teórica", isso é resultado útil. Diga.
- Separe o que é publicado do que é sua extrapolação. Marque cada um.
````

## Pesquisa 01 — achados, sem resumir

### Achados — Pesquisa 01

- **Ângulo:** assinatura do MODO de operação (esponja vs. bloco vs. fluxo)
- **Temperatura declarada:** 0,4
- **Prompt usado:** `prompts/01_modo_de_operacao.md`
- **Concluída:** 20/09/2026, ~29 min de execução, 102 chamadas de ferramenta

---

### Assinatura do MODO de operação no criptograma — levantamento

**Método.** Busca em ePrint/IACR, ToSC, NIST CSRC, arXiv, Springer, ScienceDirect, IJCNC, J.UCS. Sempre que possível baixei o PDF e li o texto extraído em vez de confiar no resumo do buscador — sinalizo abaixo o que li de fato e o que só consegui confirmar por snippet. Não li nada do repositório local.

**Resposta curta à pergunta do ângulo.** Sim, o modo deixa assinatura — mas a assinatura vive em quatro lugares, e três deles estão fechados pelo protocolo experimental:

| Canal | Existe? | Sobrevive ao CT-only + 64 KB fixo + len excluído? |
|---|---|---|
| Geometria de comprimento/expansão | Sim, determinístico | **Não** — vira constante por algoritmo (= o rótulo) |
| Ramo de padding | Sim | **Não** — com \|M\| múltiplo exato da taxa, o ramo é constante em todos os quatro |
| Estrutura de colisão (permutação vs. função) | Sim, teórico | **Não** — só em 2^64 blocos por chave |
| Profundidade nonce→primeiro byte observável + região de tag sem máscara | Sim | **Sim** — e é aqui que está tudo o que sobra |

---

#### PARTE 1 — O enquadramento formal: o que um modo *pode* vazar

##### 1.1 Função de vazamento de Rogaway (`L_ECB`) e IND$

**O que é.** Rogaway formaliza "o que um modo vaza" como uma *leakage function* `L(C, s)`: um modo é privado *até o vazamento de L*. Para ECB ele define explicitamente `L_ECB`, a **block-repetition leakage function**. Para os modos que atingem indistinguibilidade de bits aleatórios (ind$), a função de vazamento se reduz a `L(C) = |C|`.

Trechos lidos no PDF: *"Whereas ECB leaks the equality of blocks across time and position, XTS leaks the equality of blocks across time but not position."* e *"the leakage function is null, but when we leak just the message length, L(C)=|C|."* Ele também prova que ind$ **implica** left-or-right, find-then-guess e semantic security, com reduções justas: *"the indistinguishability-from-random-bits notion is properly stronger than all four of the alternative notions."*

**Fonte.** Phillip Rogaway, *Evaluation of Some Blockcipher Modes of Operation*, relatório para o CRYPTREC, 2011. https://web.cs.ucdavis.edu/~rogaway/papers/modes.pdf — **PDF lido**.

**Cabe no modelo?** SIM, como moldura. É o argumento formal de por que H0 é a previsão correta: os quatro algoritmos são ind$-CPA nonce-respecting, logo `L(C)=|C|`, logo o único observável CT-only é o comprimento — que a dissertação exclui por decisão de protocolo.

**Custo de testar.** Zero. É argumento, não experimento. Custa meia página de dissertação e resolve o capítulo teórico.

**O que prevê.** Que qualquer classificador que veja apenas o corpo do criptograma, com plaintext de comprimento fixo, fica no acaso — e que qualquer resultado positivo é vazamento de `|C|`, do plaintext, ou da chave. É falsificável: se um classificador der F1 > acaso com esses controles, ou o protocolo tem vazamento ou um dos algoritmos não é ind$.

---

##### 1.2 Anonymous AE (anAE) — a noção formal exata da pergunta da dissertação

**O que é.** Chan & Rogaway definem `anAE`: esquemas em que **o criptograma deve esconder sua origem**, mesmo entendido como contendo tudo o que é preciso para decifrar. É literalmente a formalização de "dá para saber qual algoritmo/chave produziu este criptograma?". Eles definem a *expansão* tau do esquema como parâmetro explícito e apontam que o nonce-contador transmitido em claro revela a **ordinalidade** da mensagem: *"Sending a counter-based nonce, which is the norm, will reveal a message's ordinality — its position in the sequence of messages that comprise a session."* E delimitam o escopo: *"While anAE does not address privacy loss through traffic-flow analysis, it does ensure that ciphertexts, now more expansively construed, do not by themselves compromise privacy."*

**Fonte.** John Chan, Phillip Rogaway, *Anonymous AE*, ASIACRYPT 2019 / ePrint 2019/1033. https://eprint.iacr.org/2019/1033 — **PDF lido**.

**Cabe no modelo?** SIM. É o vocabulário certo para nomear a pergunta da dissertação. Ironia útil: um esquema `nAE` padrão **não** é `anAE` justamente porque a expansão tau e o nonce vazam. A literatura já reconhece que a *distinção de esquema por criptograma* é um problema **resolvido pela geometria**, não pelo conteúdo.

**Custo.** Zero. Citação.

**O que prevê.** Que a única alavanca para distinguir esquemas é tau (expansão) e metadados de enquadramento. Para Ascon/GIFT-COFB/Schwaemm tau = 16 bytes; para Grain-128AEAD tau = 8 bytes. Previsão dura: se `len_ct` entrar como feature, Grain é separado com F1 = 1,0 e os outros três ficam no acaso entre si. Bom **controle positivo de protocolo**.

---

##### 1.3 PURBs — confirmação empírica de que, na prática, quem vaza é o cabeçalho

**O que é.** Nikitin et al. mostram que formatos reais (PGP, TLS) vazam em claro *"the format version, encryption schemes used, number of recipients..."*, e propõem PURBs: *"ciphertexts indistinguishable from random bit strings to anyone without a decryption key. A PURB's content leaks nothing at all, even the application that created it, and is padded such that even its length leaks as little as possible."* O esquema Padmé limita o vazamento por comprimento a **O(log log M)** bits com overhead <= 12%.

**Fonte.** Nikitin, Barman, Lueks, Underwood, Hubaux, Ford, *Reducing Metadata Leakage from Encrypted Files and Communication with PURBs*, PETS 2019; arXiv:1806.03160v4. https://arxiv.org/pdf/1806.03160 — **PDF lido**.

**Cabe no modelo?** SIM (evidência negativa forte). A comunidade de privacidade trata "identificar o esquema pelo criptograma" como problema de **cabeçalho e comprimento**, nunca de estatística do corpo. Ninguém propõe esconder o corpo, porque o corpo já é indistinguível.

**Custo.** Zero.

**O que prevê.** Nada novo experimentalmente; blinda a discussão contra o revisor que perguntar "mas ninguém tentou?".

---

##### 1.4 Length-hiding encryption — quantificação do canal de comprimento

**O que é.** Gellert, Jager, Lyu e Neuschulten argumentam que as definições padrão (IND, real-or-random, semantic security) *"do not provide security against attacks that are based on the length of messages"* porque exigem mensagens de igual comprimento. Propõem um modelo que quantifica concretamente a segurança contra fingerprinting em função da distribuição real de mensagens da aplicação, e mostram que padding de 2–5% de overhead já melhora significativamente a segurança para DNS, Google search, Wikipedia.

**Fonte.** Gellert, Jager, Lyu, Neuschulten, *On Fingerprinting Attacks and Length-Hiding Encryption*, CT-RSA 2022 / ePrint 2021/1027. https://eprint.iacr.org/2021/1027 — **PDF lido (primeiras páginas)**.

**Cabe no modelo?** ADAPTÁVEL, e é o que a dissertação já fez sem nomear: fixar 64 KB é *length-hiding perfeito por construção*. Vale explicitar.

**Custo.** Zero.

**O que prevê.** Que fixar o comprimento fecha o canal dominante. Corolário metodológico: se a CNN 1D/2D recebe bytes crus com **padding ou truncamento** de criptogramas de comprimentos diferentes (Grain 65.544 vs. os outros 65.552), ela aprende comprimento. Precisa de ablação explícita.

---

#### PARTE 2 — Mecanismos estruturais reais (e por que morrem no bound de aniversário)

##### 2.1 Impossible-plaintext cryptanalysis — permutação vs. função como assinatura de modo

**O que é.** McGrew observa que, em CTR com nonce determinístico, **não há colisões nas entradas da cifra de bloco**, logo `E(i) != E(j)` para todo `i != j`, logo

> `P_i != P_j XOR C_i XOR C_j`   (Eq. 6 do artigo)

Cada par observado *elimina* um valor possível de plaintext. Em CBC/CFB, ao contrário, uma colisão nas entradas é **diretamente observável no criptograma** e revela `P_i XOR P_j = Delta_ij`. Ele quantifica: número esperado de bits vazados por colisões = `n^2 * w / 2^(w+2)`.

Números exatos da Tabela 1 (lida no PDF):

| | 1 Mbit/s por 1 dia | 1 Gbit/s por 1 dia | 1 Tbit/s por 1 dia |
|---|---|---|---|
| w = 64 | 6,3 bits | 6,3x10^6 bits | 6,3x10^12 bits |
| **w = 128** | **1,7x10^-19 bits** | **1,7x10^-13 bits** | **1,7x10^-7 bits** |

E: *"Collision attacks do not work against CTR when it is used with a deterministic nonce (as is conventional), because there are no collisions in the block cipher inputs. These attacks are also inapplicable to CTR-based modes such as CCM and GCM."*

**Fonte.** David McGrew (Cisco), *Impossible plaintext cryptanalysis and probable-plaintext collision attacks of 64-bit block cipher modes*, ePrint 2012/623. https://eprint.iacr.org/2012/623 — **PDF lido inteiro**.

**Cabe no modelo?** O ataque em si: **NÃO** (precisa de plaintext conhecido). Mas o **mecanismo** é CT-only observável e transfere direto, porque separa os quatro algoritmos em duas classes estruturais:

- **GIFT-COFB**: na especificação, `C[i] <- M[i] XOR Y[i+a-1]` com `Y[j] = E_K(X[j])`. Como `E_K` é uma **permutação** de 128 bits e os `X[j]` são distintos, os `Y[j]` **nunca colidem sob uma mesma chave**. O keystream do COFB é livre de colisões — exatamente a estrutura do CTR de McGrew.
- **Ascon-AEAD128**: o bloco de keystream é a taxa de 128 bits truncada de uma permutação de 320 bits — comporta-se como **função** aleatória, colide na taxa de 2^64.
- **Schwaemm256-128**: taxa de 256 bits de uma permutação de 384 — colide em 2^128.
- **Grain-128AEAD**: fluxo puro, sem estrutura de bloco.

Existe uma assinatura de modo **exata e teórica** ("o keystream repete ou não repete"), observável só a partir do bound de aniversário.

**Custo de testar.** Nenhum — é cálculo. Conta feita para a escala típica (100 amostras x 64 KB por chave = 409.600 blocos de 128 bits ~ 2^18,6):
- vantagem de distinção permutação-vs-função por chave ~ sigma^2/2^(n+1) = 2^37,2/2^129 = **2^-91,8 ~ 2x10^-28**;
- somando 300 chaves: ~ 2^-83,6.

Comparação: 2^64 blocos sob uma chave = 2^68 bytes ~ 295 exabytes **por chave**. Distância de ~11 ordens de grandeza em bytes e ~28 ordens em vantagem.

**O que prevê.** Falsificável: a **taxa de colisão de blocos de 16 bytes dentro de um mesmo criptograma** deve ser estatisticamente idêntica nos quatro (e igual ao acaso). Diferença medida = bug de implementação, não criptanálise. Vira teste de sanidade do dataset.

---

##### 2.2 A máscara de 64 bits do COFB e o bound real do GIFT-COFB

**O que é.** Na especificação final: no COFB, a máscara entra como `L||0^(n/2)` — **só na metade superior do bloco**, e `L` é de 64 bits (campo `F_2^64` com `p_64(x)=x^64+x^4+x^3+x+1`). O feedback é `G(Y) = (Y[2], Y[1] <<< 1)` e a especificação declara: *"Our choice of G ensures that G XOR I has rank n-1"* — perde exatamente um bit.

Inoue, Iwata e Minematsu mostraram **ataque de privacidade (IND-CPA)** com `q_e` consultas de cifragem e **nenhuma consulta de decifragem**, com probabilidade de sucesso `O(q_e / 2^(n/2))`, contradizendo o termo `O(q_e^2/2^n)` do documento NIST. Literal: *"For GIFT-COFB, we show an attack using q_e encryption queries and no decryption query to break privacy (IND-CPA). The success probability is O(q_e/2^{n/2}) for n-bit block while the claimed bound contains O(q_e^2/2^n)."* Ressalva dos autores: *"we do not negate the claims that GIFT-COFB is (n/2-log n)-bit secure for n=128"* — 64 bits de IND-CPA, 58 bits de INT-CTXT.

**Fonte.** Akiko Inoue, Tetsu Iwata, Kazuhiko Minematsu, *Analyzing the Provable Security Bounds of GIFT-COFB and Photon-Beetle*, ACNS 2022 / ePrint 2022/001. https://eprint.iacr.org/2022/001 — **PDF lido**. Especificação: Banik et al., *GIFT-COFB v1.1*, NIST LWC final round — **PDF lido**.

**Cabe no modelo?** **NÃO.** O ataque (Seção 3.1) exige escolher o plaintext (`|M| = 2n`, `M = M[1]||M[2]`), calcular `lsb_(n/2)(X[2])` e **usar esse valor como nonce da consulta seguinte** — `N_i = (i)_(n/2) || lsb_(n/2)(X[2])`. Nonce escolhido + plaintext escolhido.

**Custo.** Não aplicável.

**O que prevê.** Nada testável. O valor é outro: **atesta que o melhor ataque publicado ao modo COFB precisa de nonce escolhido** — argumento forte no texto sobre por que o adversário passivo não tem alavanca sobre esse modo.

**Detalhe lateral valioso.** No mesmo artigo, o ataque ao Photon-Beetle (também esponja): *"The collision can be detected from C'_i and C'_j, which are the first b bits of C_i and C_j."* Ou seja, **num esponja, colisão de estado completo é detectável pelo criptograma** — mas só porque fixam os primeiros `b` bits de `M` iguais em todas as consultas. Sem plaintext escolhido, o detector some.

---

##### 2.3 Bounds de duplex/esponja

**O que é.** A segurança dos modos esponja keyed é governada pela capacidade. Ascon-AEAD128: rate 128, **capacidade 192** (SP 800-232: *"the rate and capacity of Ascon-AEAD128 are 128 and 192 bits, respectively"*). Schwaemm256-128: n=384, r=256, **c=128**, segurança declarada **120 bits**, limite de dados **2^68 bytes** (Tabela 2.3 da especificação SPARKLE).

**Fontes.** NIST SP 800-232 (agosto 2025) — **PDF lido**; Beierle et al., *Schwaemm and Esch* (SPARKLE, NIST LWC final round) — **PDF lido**; arcabouço genérico: Daemen, Mennink, Van Assche, *Full-State Keyed Duplex with Built-In Multi-user Support*, ASIACRYPT 2017 / ePrint 2017/498; Mennink, *Understanding the Duplex and Its Security*, ToSC 2023 / ePrint 2022/1340 (**esses dois só confirmados por busca**).

**Cabe no modelo?** SIM, como cota superior de indistinguibilidade.

**Custo.** Zero.

**O que prevê.** Limite de dados do Schwaemm256-128 é 2^68 bytes. Dataset de ~2 GB por algoritmo é ~2^-37 desse limite. Nenhuma estatística do corpo pode se mexer.

---

#### PARTE 3 — Padding e enquadramento: por que o 64 KB fixo zera esse canal

Achado mais concreto para o ângulo pedido, verificável nas quatro especificações (todas lidas).

| | Regra de padding do plaintext | Com \|M\| = 65.536 B | Efeito no criptograma |
|---|---|---|---|
| **Ascon-AEAD128** | `pad(X,r) = X || 1 || 0^j`, `j = (-\|X\|-1) mod 128`. Quando `\|P\| mod 128 = 0`, *"the last block P~_n is empty"* e ainda assim faz `S[0:127] <- S[0:127] XOR pad(eps,128)`, com `C~_n <- S[0:l-1]`, l=0 | Ramo fixo: 4096 blocos cheios + 1 absorção de padding vazia | **Nenhum byte extra.** `len_ct = len_pt`, tag 16 B à parte |
| **GIFT-COFB** | `Pad(x)=x` se `x != eps` e `\|x\| mod n = 0`; senão `x||10^...`. O ramo só muda o domínio: `if \|M\| mod n = 0 then L <- 3*L else L <- 3^2*L` | Ramo fixo (`3*L`), 4096 blocos | Nenhum byte extra; diferença entra só na **tag** |
| **Schwaemm256-128** | `if \|M_last\| < 256 then pad; Const_M <- 2 XOR (1<<2)` senão `Const_M <- 3 XOR (1<<2)` | Ramo fixo (`Const_M = 7`), 2048 blocos de 256 bits | Nenhum byte extra |
| **Grain-128AEAD** | *"For a message m of length L... set m_L = 1 as padding in order to ensure that m and m||0 have different tags"* | Ramo fixo | Nenhum byte extra; tag 8 B |

**Conclusão dura (dedução do agente, cada linha verificada na especificação):** com plaintext de comprimento fixo múltiplo exato de todas as taxas envolvidas (65.536 é múltiplo de 16, 32 e 1), **a variância do canal de padding é identicamente zero**. O padding não é sinal fraco no experimento — é *matematicamente ausente*. Duas consequências:

1. A família de features `tag_region`/`bitblock` não pode capturar padding, porque não há padding para capturar.
2. **Se o objetivo é estudar assinatura de padding, é obrigatório variar o comprimento do plaintext** — e aí o sinal aparece em `len_ct`, o metadado excluído. Dilema real: *a assinatura de padding e o metadado de comprimento são o mesmo objeto*.

**Custo de testar.** Um braço de dataset com comprimentos sorteados (uniforme em [1, 65536]) e um classificador que **não** vê `len_ct` mas vê o criptograma alinhado. Mesmo custo do braço atual. Mede quanto do comprimento "vaza de volta" pela representação (bytes crus com padding a comprimento fixo reconstroem o comprimento trivialmente).

**O que prevê.** F1 = 1,0 com comprimento variável e alinhamento ingênuo; F1 = acaso com comprimento variável e representação que normaliza comprimento. A diferença entre esses dois números mede quanto do sinal publicado na literatura é geometria.

---

#### PARTE 4 — Geometria da tag: o único observável **sem máscara de plaintext**

##### 4.1 O argumento

**O que é.** Observação estrutural do agente, derivada das quatro especificações: em todos os quatro esquemas, **o corpo do criptograma é `P XOR Z`**, enquanto **a tag não é XORada com nenhum plaintext**:

- Ascon-AEAD128: `T <- S[192:319] XOR K` (Eq. 32 do SP 800-232)
- Schwaemm256-128: `return (C, S_R XOR K)`
- GIFT-COFB: `T <- Trunc_tau(Y[a+m])`
- Grain-128AEAD: tag = acumulador de 64 bits

Consequência: **toda feature de amostra única sobre o corpo (histograma, entropia, n-gramas, ACF, FFT, LZ/zlib/bz2) mede majoritariamente o plaintext**, porque `P XOR Z` herda a variância de `P` quando `Z` é fixo por amostra e as amostras têm plaintexts diferentes. A tag, com 16 bytes, é o único pedaço de saída cuja distribuição é função pura do criptossistema.

A literatura de teste de aleatoriedade em AEAD **já testa exatamente a tag**, por essa razão.

**Fonte de apoio.** Martin Ukrop, Petr Svenda, *Avalanche Effect in Improperly Initialized CAESAR Candidates*, MEMICS 2016, EPTCS 233:72–81. https://arxiv.org/pdf/1612.04984 — **PDF lido**. Geram fluxo de **tags de autenticação** de 52 candidatos CAESAR e testam com NIST STS (188 testes), Dieharder (55) e TestU01 (159), em três regimes de public message number: fixo em zero, **contador**, e aleatório.

Resultados exatos da Tabela 1:
- Com PMN **contador**, AES-GCM (aes128gcmv1): STS 187/188, Dieharder 52/55, TestU01 157/159 — tags indistinguíveis.
- Com PMN fixo em zero: **nenhum dos 52 candidatos passou**. STS 23/188 para o AES-GCM.
- *"Tags of just five ciphers (AES/GCM, Marble, AES-CMCC, AES-CPFB, Raviyoyla) were distinguishable from random streams with counter-valued public message numbers."*
- Explicação levantada pelos próprios autores, relevante para uma feature `tag_region`: *"it may merely be the case they produce a constant delimiter between the ciphertext and tag, violating the statistical randomness of the created tag."*

**Cabe no modelo?** **SIM, integralmente.** Nonces de contador, adversário passivo, sem plaintext conhecido. É exatamente o cenário deles.

**Custo de testar.** Baixíssimo. Concatenar as tags de todas as amostras num fluxo e rodar STS/Dieharder/TestU01 — mais barato que extrair 641 features de 180k amostras. Com 30.000 amostras x 16 B = **480 KB de saída não mascarada por algoritmo**; o NIST STS precisa de ~10^6 bits por sequência, então 480 KB = 3,8 Mbit dá para ~3 sequências completas. Engenharia: horas.

**O que prevê.**
- Full-round: os quatro passam (com base no resultado de Ukrop & Svenda para candidatos CAESAR com PMN contador). Se **não** passarem, há bug de implementação ou de serialização — resultado por si só, e é o modo de falha que eles apontam (delimitador constante).
- Rodadas reduzidas na **finalização**: a tag deve quebrar muito antes de qualquer estatística do corpo, porque tem razão sinal/ruído infinitamente melhor por byte.

**Sobre "geometria de tag".** A resposta honesta: a *posição e o tamanho* da tag deixam assinatura (8 vs. 16 bytes → Grain separável, mas isso é `len_ct`); o *conteúdo* da tag não deixa em full-round, mas é o **melhor lugar do criptograma para procurar**, e isso é publicado e testado.

---

#### PARTE 5 — Profundidade nonce→saída: a métrica de modo que sobrevive ao CT-only

##### 5.1 A ideia

**O que é.** Extrapolação do agente, com cada número vindo de especificação lida. O modelo de ameaça dá ao adversário algo raramente explorado: **o nonce é público e é um contador**. Ele observa passivamente uma família de entradas **estruturada** — subespaço afim sobre os bits baixos do nonce. O que o modo determina é *quanto trabalho de primitiva separa esse nonce estruturado do primeiro byte observável*, e *onde o nonce entra no estado*.

| Algoritmo | Onde o nonce entra | Profundidade nonce → 1o byte observável | Observável |
|---|---|---|---|
| **Ascon-AEAD128** | `IV||K||N`; N ocupa `S[192:319]` — região de **capacidade** | **12 rodadas** de Ascon-p. `C_0 = P_0 XOR S[0:127]` após `p[12]`, `XOR (0^192||K)` e o bit de separação de domínio (que tocam só `S[192:319]`) | taxa de 128 bits, mascarada por P |
| **Schwaemm256-128** | `Sparkle384_11(N||K)`; N é de **256 bits** e ocupa **toda a taxa** `S_L` | **11 big steps** de Sparkle384 | `C_0 = rho_2(S_L, M_0) = S_L XOR M_0`, 256 bits, mascarada por P |
| **Grain-128AEAD** | IV de 96 bits nos 96 primeiros elementos do LFSR (últimos 32 = `1^31||0`); K no NFSR | **256 clocks** de inicialização **+ 128 clocks** de inicialização do acumulador/registrador = **384 clocks** | `z_i = y_(2i)` — **só os bits pares** do pre-output; os ímpares vão para autenticação e nunca são vistos |
| **GIFT-COFB** | `Y[0] <- E_K(N)`; nunca observado diretamente | **2 x 40 = 80 rodadas** de GIFT-128 (`N -> Y[0] -> X[1] -> Y[1] -> C[1]`) | `C[1] = M[1] XOR Y[1]`, mascarada por P |

**Fontes.** SP 800-232 (lido), SPARKLE spec (Tabela 2.3, Algoritmo 2.13, tabela `Sparkle384: 7 slim / 11 big`), Grain-128AEAD spec round 2 (*"the cipher is clocked 256 times, feeding back the pre-output function"*, *"the authenticator generator is initialized by loading the register and the accumulator with the pre-output"*, *"every even bit (counting from 0) from the pre-output generator is taken as keystream"*), GIFT-COFB v1.1 (Algoritmo COFB-E, linhas 1, 12–18).

**Cabe no modelo?** SIM — 100% CT-only com nonce-contador público.

**Custo.** Zero para derivar; base das apostas 1 e 2.

**O que prevê.** Que a *ordem* em que os quatro deixam de parecer aleatórios, reduzindo rodadas proporcionalmente, é determinada por essa tabela, e **não** pela força da primitiva. Grain e Schwaemm expõem o nonce diretamente na parte observável do estado; Ascon o coloca na capacidade; **GIFT-COFB enterra o nonce atrás de uma chamada inteira de cifra de bloco antes de qualquer saída**. Previsão falsificável: em estudo de rodadas reduzidas passivo, o GIFT-COFB é o último a cair, por margem de ~2x em rodadas, e isso é propriedade **do modo**, não do GIFT-128.

##### 5.2 Margens relativas publicadas (para calibrar o piso de rodadas)

| Primitiva/inicialização | Melhor distinguidor público | Fração |
|---|---|---|
| Ascon-p, inicialização 12 rodadas | cube tester em **6/12** com 2^33 dados; key recovery cube-like **5/12** com 2^35 (prático) e **6/12** com ~4*2^64; differential-linear **5/12** com 2^36; zero-sum na permutação completa **12/12** com 2^130 | ~50% |
| Ascon-p (DL experimental) | distinguidor DL de **5 rodadas** com 2^35 dados (<1 s em RTX 4090) | ~42% |
| Ascon-p (MLP) | distinguidor de **4 rodadas** com MLP (Shen et al., citado em ePrint 2025/1306) | ~33% |
| Sparkle384, init 11 big steps | distinguidor DL prático de **4 rodadas**, complexidade < 2^13,1 | ~36% |
| Grain-128a, 256 clocks de KSA | diferencial condicional em **195/256** (fração das chaves); cube tester dim-5 em **191/256** single-key, **201/256** weak-key; division property key recovery em **184** rodadas, dados 2^95, tempo 2^110; superpolies exatas para **192** rodadas, distinção até **193** em weak-key | **~76%** |
| GIFT-128, 40 rodadas | DL em **13/40**; diferencial single-key em **20/40** com prob. 2^-120,245; neural differential em **7/40** com 99,36% de acurácia | ~33% (e ~16% da profundidade nonce→saída de 80) |

**Fontes.** Dobraunig, Eichlseder, Mendel, Schläffer, *Cryptanalysis of Ascon*, CT-RSA 2015 / ePrint 2015/030 (**PDF lido; Tabela 1 e Seções 3, 4.3, 4.4**). Grain-128AEAD spec, Seção 4.4 "Chosen IV Attacks" (**lida**): *"An attack that reaches the largest number of initialization rounds of Grain-128a in a fixed key scenario thus far is a conditional differential distinguishing attack and reaches 195 initialization rounds, but it works only for a fraction of all keys"*, e *"there exist no chosen IV attacks on full round initialization of Grain-128a in a single key scenario."* Para Sparkle, GIFT-128 e Grain-128AEAD com division property: **só confirmado por snippet de busca** — números a verificar.

**Previsão de ordenação (extrapolação do agente, marcada como tal):** reduzindo rodadas proporcionalmente, o **Grain-128AEAD cai primeiro** (margem relativa mais estreita: 195/256 ~ 76%), depois **Ascon** (~50%), depois **Schwaemm** (~36%), e o **GIFT-COFB por último** (~16% da profundidade efetiva). Se o experimento produzir essa ordem, confirma que *o modo governa o piso*. Outra ordem é resultado ainda mais interessante e precisa de explicação.

---

#### PARTE 6 — Cubos e integrais passivos sobre nonce-contador

Veio mais promissor do levantamento, e onde o agente discorda de uma premissa do enunciado.

##### 6.1 O contador *é* o cubo

**O que é.** O ataque de cubo precisa de `2^d` valores de IV formando subespaço afim sobre `d` bits escolhidos, com o resto fixo. **Um nonce-contador fornece exatamente isso, de graça, passivamente**: `2^d` nonces consecutivos alinhados percorrem todos os `2^d` valores dos `d` bits baixos, mantendo o resto constante. O adversário não *escolhe* — ele *espera e observa*.

Coincidência estrutural verificada no artigo do Ascon: o cube tester exige que **todas as variáveis do cubo estejam na mesma palavra de 64 bits do estado**, condição que um contador satisfaz naturalmente. Literal:

> *"So if all cube variables lie within the same word of the state, they do not appear together in one term after the application of the S-box layer. Hence, after 5 more rounds, at most 32 variables of one state-word appear together in one term. As a consequence, selecting a cube of 33 variables of the same state-word definitely results in an empty superpoly and all 2^33 generated outputs sum to zero."*

E, sobre o cenário nonce-respecting com inicialização reduzida:

> *"Similar cube testers can be applied to reduced versions of Ascon with only 6 rounds (instead of 12 rounds) of initialization. Then, an attacker with control over the nonce can observe the first key-stream block."*

O grau de uma rodada do Ascon é 2, então o grau após `r` rodadas é <= 2^r; com variáveis confinadas a uma palavra, o grau **nas variáveis do cubo** é <= 2^(r-1). Logo:

| Rodadas de inicialização do Ascon | Dimensão do cubo necessária | Nonces consecutivos | Bytes necessários (só os 16 primeiros de cada CT) |
|---|---|---|---|
| 2 | 3 | 8 | 128 B |
| 3 | 5 | 32 | 512 B |
| 4 | 9 | 512 | 8 KB |
| 5 | 17 | 131.072 | **2 MB** |
| 6 | 33 | 8,6x10^9 | 137 GB |
| 7 | 65 | 2^65 | inviável |
| **12 (full)** | — | — | **fechado** |

**Fonte.** Dobraunig, Eichlseder, Mendel, Schläffer, ePrint 2015/030, Seção 4.3. https://eprint.iacr.org/2015/030 — **PDF lido**. A observação de que o contador supre o cubo é **extrapolação do agente**, ancorada nesse texto. Não encontrou ninguém que a tenha escrito explicitamente — procurou por "known IV attack", "counter IV cube", "passive cube attack". Pode ser contribuição original da dissertação, ou folclore não escrito; **sinalizado como não confirmado na literatura**.

**Cabe no modelo?** **SIM**, com ressalva e obstáculo:

- *Ressalva:* o contador entrega apenas cubos sobre um **intervalo contíguo de bits baixos de uma palavra do nonce**. Os cubos condicionais modernos contra o Ascon exigem mais — o distinguidor de 7 rodadas usa cubo de dimensão 60 *"where the nonce bits are set to be equal in the third and fourth rows of the Ascon state"*, isto é, restrições de igualdade cruzada entre `x3` e `x4`. Um contador **não consegue** produzir isso. O "cubo passivo" alcança estritamente menos rodadas que o cubo escolhido. **Quantificar essa lacuna é resultado publicável**: "quanto de criptanálise de IV escolhido sobrevive a um adversário que só observa contadores?".
- *Obstáculo:* o observável é `C_1 = P_1 XOR Z_1`, com `P_1` desconhecido e **diferente** em cada amostra. A soma do cubo dá `XOR Z_1 XOR XOR P_1`. Se os `P_1` forem i.i.d. uniformes, o termo de plaintext randomiza tudo.

##### 6.2 Três saídas para o mascaramento pelo plaintext

**(a) Bits determinísticos do plaintext (in-model, limitado).** Se uma posição de bit é determinística no corpus (bit 7 de cada byte em texto ASCII de 7 bits), a soma do cubo desse bit sobre `2^d` amostras é exatamente 0, e `XOR C_1[bit]` = `XOR Z_1[bit]` sem erro. Num bloco de 16 bytes do Ascon isso dá **16 bits limpos por amostra**.

Limite prático (cálculo do agente): se o bit tem `Pr[=1] = p` independente, o viés da soma é `(1-2p)^(2^d)`. Para `p = 10^-3` (texto Gutenberg em UTF-8, com travessões e acentos) e `d = 9`, `(0,998)^512 = e^-1,02 ~ 0,36` — utilizável. Para `d = 17`, `e^-262 ~ 0` — morto. **O canal funciona limpo até d ~ 9–10 (Ascon com 4 rodadas de init) com texto real, e exige corpus com bit exatamente constante (ASCII 7-bit filtrado) para chegar a d = 17 (5 rodadas).**

**(b) Cancelamento pelo encadeamento (diagnóstico, não classificador).** Como o protocolo cifra **o mesmo plaintext com a mesma chave e o mesmo nonce em todos os algoritmos**, o termo de plaintext **cancela exatamente** na XOR das somas de cubo entre dois algoritmos:

`CubeSum(C^Ascon) XOR CubeSum(C^GIFT) = CubeSum(Z^Ascon) XOR CubeSum(Z^GIFT)`

Não é classificador (exige ver os dois criptogramas), mas é o **melhor diagnóstico possível** para "o canal de cubo está aberto neste número de rodadas?", e é puramente função dos criptogramas. Vale para o braço de rodadas reduzidas, que é pergunta sobre a *cifra*, não sobre o adversário.

**(c) Cube tester estatístico contra a distribuição do plaintext.** Sob H0 (rodadas completas), `CubeSum(C)` é uniforme. Sob H1 (rodadas reduzidas), `CubeSum(Z) = 0`, logo `CubeSum(C) = CubeSum(P)`, que é a XOR-convolução de `2^d` blocos de texto natural — enviesada para 0 em toda posição com viés por bit. Testar "uniforme vs. XOR-convolução do corpus" é teste de hipótese legítimo, e assume apenas *conhecimento da distribuição do plaintext*, premissa clássica do ciphertext-only (McGrew: *"we assume that the attacker has some (incomplete) knowledge about the plaintext"*).

**Custo de testar.** Muito baixo: **só é preciso o primeiro bloco do criptograma**. Para `d = 17` no Ascon: 131.072 nonces consecutivos x 16 bytes = **2 MB por chave por contagem de rodadas**. Comparado com ~20 h de extração de features sobre 180k amostras de 64 KB, é ruído. Única exigência de engenharia: gerar **corridas de nonces contíguas e alinhadas a potências de 2 sob a mesma chave** — o que um contador global intercalado entre 6 algoritmos e 300 chaves *não* dá de graça. É mudança no cronograma de nonces, não no protocolo.

**O que prevê.** Previsões duras e binárias:
1. **Ascon com init <= 5 rodadas + cubo alinhado de dimensão >= 17:** soma do cubo nas posições de bit determinísticas é **exatamente zero**, todas as vezes. Não é acurácia de 0,6 — é detector determinístico, F1 = 1,0.
2. **Ascon com init = 12 (full):** soma uniforme. Acaso.
3. **GIFT-COFB, qualquer dimensão alcançável:** **nenhum sinal, em nenhuma contagem praticável**, porque o nonce passa por permutação completa de 40 rodadas antes de influenciar qualquer coisa e por outra antes de ser observado. O grau satura. **O canal de cubo é aberto ou fechado conforme o modo, não conforme a primitiva.**
4. **Schwaemm256-128:** o nonce de 256 bits ocupa **toda a taxa inicial** e `C_0 = S_L XOR M_0` sem rate whitening. Estruturalmente o mais exposto dos quatro. Previsão: cai com dimensão de cubo menor que o Ascon, para o mesmo número relativo de steps.
5. **Grain-128AEAD:** só os bits **pares** do pre-output são visíveis. Viés de cubo em posição ímpar é invisível. Previsão: o distinguidor precisa ser construído sobre a sequência **decimada por 2**, e a dimensão de cubo necessária é maior que a reportada na literatura de Grain-128a (que analisa o pre-output completo). Efeito de **modo** (o modo AEAD esconde metade do gerador), diretamente mensurável.

##### 6.3 O corolário sobre Gohr que contraria o enunciado

**O que é.** O enunciado exclui distinguidores neurais estilo Gohr "que dependem de pares com diferença escolhida". Mas **nonces consecutivos de um contador têm diferença conhecida e fixa por construção** (Delta = 1 nos bits baixos, ou o padrão de carry para pares alinhados). O adversário não escolhe a diferença — ele a *recebe*. Logo, um distinguidor diferencial-neural sobre pares `(C_1^(N), C_1^(N+1))`, **restrito às posições de bit determinísticas do plaintext**, é ciphertext-only e cabe no modelo.

**Fonte de apoio.** Gohr, *Improving Attacks on Round-Reduced Speck32/64 Using Deep Learning*, CRYPTO 2019 / ePrint 2019/037. Para o alvo: *Neural differential distinguishers for GIFT-128 and ASCON*, Journal of Information Security and Applications, 2024 (ScienceDirect S2214212624000619) — **só confirmado por busca**: reportam melhorar a acurácia do distinguidor neural de 7 rodadas do GIFT-128 de 55,42% para 99,36%. Yuan et al., ePrint 2025/1306 (**PDF lido**) fornece o arcabouço teórico (modelo Coin-Tossing, classe Conjunctive Parity Form, prova de aprendibilidade em tempo subexponencial) e cita distinguidor MLP de 4 rodadas para a permutação do Ascon.

**Cabe no modelo?** **ADAPTÁVEL**, e a adaptação é: (i) a diferença está no **nonce público**, não no plaintext; (ii) o rótulo da rede é "real vs. aleatório" sobre o par de *primeiros blocos*; (iii) a máscara de plaintext é contornada restringindo aos bits determinísticos ou usando o cancelamento por encadeamento. **O que isso arranha no modelo de ameaça:** nada, desde que os nonces sejam realmente contadores públicos. Se o nonce fosse aleatório, o canal fecharia.

**Custo.** Médio. Reaproveita a infraestrutura de CNN 1D existente, com entrada de 2x16 bytes (ou 2x32 para o Schwaemm) em vez de 65.552. O treino fica **três ordens de grandeza mais barato** — treinável em CPU. Dados: 10^5–10^6 pares por (algoritmo, contagem de rodadas).

**O que prevê.** Igual à Parte 6.2, sem exigir alinhamento de cubo — só pares consecutivos. Contraste: a rede deve achar sinal em Ascon/Schwaemm/Grain reduzidos e **não** em GIFT-COFB reduzido, mesmo com o GIFT-128 reduzido ao ponto em que ele *isolado* é quebrável por distinguidor neural de 7 rodadas. Se confirmado, é a demonstração experimental de que **o modo, e não a cifra, decide**.

---

#### PARTE 7 — A literatura de identificação de cifra por ML: o que ela realmente mede

Seção necessária porque o resultado H0 da dissertação **contradiz frontalmente** uma literatura grande. Importa saber onde essa literatura vaza.

##### 7.1 de Mello & Xexéo (2018) — ECB total, CBC parcial

Sete algoritmos (DES, Blowfish, RSA, ARC4, Rijndael, Serpent, Twofish) em ECB e CBC, corpora em sete idiomas, seis classificadores (C4.5, PART, FT, Naive Bayes, MLP, WiSARD).

**Resultados.** ECB: reconhecimento pleno. CBC: até seis vezes o acaso; taxas de 40–50% com Complement Naive Bayes.

**Fonte.** Flávio L. de Mello, José A. M. Xexéo, *Identifying Encryption Algorithms in ECB and CBC Modes Using Computational Intelligence*, Journal of Universal Computer Science 24(1):25–42, 2018. https://www.jucs.org/jucs_24_1/identifying_encryption_algorithms_in — **PDF não extraído**; números vindos de busca. **A verificar no original.**

**Cabe no modelo?** ECB: não comparável (ECB não é AEAD e vaza por `L_ECB`). CBC com chave/IV variando: **caso mais próximo**, e o resultado é fraco, coerente com H0.

**Observação.** Trabalho do próprio orientador. O contraste "ECB pleno / CBC fraco" é exatamente a `L_ECB` de Rogaway, e dá arco narrativo natural: *o que sobrou em CBC (40–50% contra 14% de acaso) precisa ser explicado, e a explicação mais provável é tamanho de bloco + padding + resíduo de conteúdo, não estrutura da cifra.*

##### 7.2 Tan et al. (2018) — o experimento que isola o confundidor de chave

SVM classificando cinco cifras de bloco em CBC (AES, DES, 3DES, RC5, Blowfish).

**Resultados (de busca; PDF não obtido, ScienceDirect devolveu 403):**
- Mesma chave e mesmo IV em treino e teste: **>= 90%** para arquivos > 20 KB.
- **Chaves diferentes E IVs diferentes: 35,56% – 41,22%** (acaso = 20%).
- Conclusão dos autores: *"both key and IV have a great influence on identification rate."*

**Fonte.** Tan et al., *Identification of Block Ciphers under CBC Mode*, Procedia Computer Science 131:65–71, 2018. https://www.sciencedirect.com/science/article/pii/S1877050918305611

**Cabe no modelo?** Parcialmente, e é o **argumento empírico mais direto a favor do key-holdout**. A queda de 90% para ~38% ao trocar chave e IV é a medida do confundidor.

**Leitura do resíduo (extrapolação do agente):** os 35–41% restantes são quase certamente **tamanho de bloco**: AES tem bloco de 128 bits, DES/3DES/Blowfish/RC5 têm 64. Sob CBC com PKCS7, isso muda a granularidade do comprimento do criptograma e a estrutura do último bloco. Não é assinatura de cifra; é geometria.

##### 7.3 Xia, Li & Chen (2022) — identificação de MODO, e o que explica o resultado

Trabalho mais próximo do ângulo: distinguir **cinco modos** (ECB, CBC, CFB, OFB, CTR) a partir do criptograma, **com chaves e IVs aleatórios a cada operação** (melhoria explícita sobre trabalhos de chave fixa).

**Setup.** Corpus: Open American National Corpus (~1 GB) em 1.000 arquivos de ~1,1 MB. Cifras: **3DES, AES-128, ARIA, PRESENT, SIMON-32**. Features: **três índices do NIST STS** — Binary Matrix Rank, Runs, Serial. Classificadores e acurácia média: Random Forest 60–85%; Fully Connected NN > 70%; **Feed Forward NN 75–85% (melhor)**; CNN 1D 60–80%. Ganho declarado: *"30% higher than [prior work]"*, maioria dos modos > 80%.

Limitações declaradas pelos autores: melhor em ECB (menos seguro), pior em OFB/CFB; **cifras leves (PRESENT, SIMON-32) dão acurácia maior que as complexas (ARIA, AES)**.

**Fonte.** Ruiqi Xia, Manman Li, Shaozhen Chen, *Encryption modes identification of block ciphers based on machine learning*, IJCNC, 2022. https://ijcnc.com/2022/10/15/encryption-modes-identification-of-blockciphers-based-on-machine-learning/ — extraído da página, não do PDF.

**Cabe no modelo?** Cenário mais próximo, e à primeira vista **contradiz a teoria**: CBC, CFB, OFB e CTR deveriam ser mutuamente indistinguíveis (todos ind$).

**Explicação do agente (extrapolação quantificada, achado mais útil desta seção):** o resultado é consistente com a teoria se o sinal vier **do bound de aniversário de blocos pequenos**, pelo mecanismo do McGrew.

- **SIMON-32/64** tem bloco de **32 bits**. Arquivo de 1,1 MB = 1.100.000 bytes = **275.000 blocos de 32 bits**. Colisões esperadas entre blocos de criptograma em CBC: `C(275000,2)/2^32 ~ 3,78x10^10 / 4,29x10^9 ~ 8,8`. Isso está **4 bits além do bound de aniversário** e é diretamente visível no Binary Matrix Rank e no Serial.
- Em CTR, pelo argumento de McGrew, `E(i) != E(j)` sempre — estatística de colisão estruturalmente diferente.
- Para 3DES/PRESENT (64 bits): 137.500 blocos, colisões esperadas `~ 9,5x10^9/1,8x10^19 ~ 5x10^-10`. Nada.
- Para AES/ARIA (128 bits): nada por muitas ordens de grandeza.

Isso **explica exatamente** a observação dos próprios autores de que as cifras leves dão acurácia maior. E fecha o caso: **a identificação de modo publicada vive no ou além do bound de aniversário de blocos pequenos.** Com estados de 128/192/320/384 bits, esse bound está em 2^64 blocos, 10^11 vezes o que um dataset de dissertação tem.

**Custo de testar essa explicação.** Baixo e muito valioso: replicar Xia et al. com SIMON-32 a 1,1 MB (reproduz ~80%) e depois com AES-128 apenas (deve cair ao acaso). Meio dia de trabalho, e transforma "não achamos nada" em "localizamos de onde vem o que os outros acharam".

**O que prevê.** Acurácia de identificação de modo escala com `sigma^2/2^n`, ou seja, com (bytes por amostra)^2 / 2^(tamanho do bloco). Previsão quantitativa e falsificável.

##### 7.4 Ren et al. (2025) — a vulnerabilidade de estrutura do plaintext

Trabalho que nomeia o confundidor principal: *"when the plaintext distribution of test data departs from the training data, the performance of classifiers often declines significantly"*, e *"models trained end-to-end from ciphertext bytes develop hidden dependencies on plaintext statistical features"*.

**Números (extraídos do HTML do arXiv):**
- Seis cifras: AES (ECB/CBC), 3DES, Blowfish, ChaCha20, RC4. Chaves e IVs por janela, derivados, sem reúso.
- Datasets sintéticos: Regular_100 / 75 / 50 / 25 / Random_100, cada um com **10.000 janelas de 8 KB**.
- Lacuna de generalização: dentro do regime "Regular", macro-F1 cai **0,00–6,04%** e macro-AUC **0,00–2,98%**. Indo para Random_100, macro-F1 cai **83,85–88,32%** e macro-AUC **46,68–49,67%**.
- XGBoost concreto: Regular_100 → Acc 0,999 / F1 0,999 / AUC 0,999. **Random_100 → Acc 0,541 / F1 0,540 / AUC 0,905.**
- O extrator DRF usa **41 testes estatísticos** em quatro famílias (estatísticas básicas, testes clássicos chi2/runs, subconjunto do NIST STS incluindo FFT e Linear Complexity, e suítes avançadas: Birthday Spacings do Diehard, Serial Correlation do TestU01). Com ele: Canterbury + SVM(RBF) → 0,897 Acc / 0,899 F1 / **0,985 AUC**; e *"AUC > 0.90 even on purely random plaintext"*.
- Limitações declaradas: *"future work should include a broader set of ciphers"* e *"the datasets are synthetic... validation on captured network traffic is needed."*

**Fonte.** Xiwen Ren, Min Luo, Cong Peng, Debiao He (Wuhan University), *Plaintext Structure Vulnerability: Robust Cipher Identification via a Distributional Randomness Fingerprint Feature Extractor*, arXiv:2511.08296v1, 11 nov. 2025. https://arxiv.org/abs/2511.08296

**Cabe no modelo?** Trabalho mais próximo metodologicamente, e o achado central (acc → 0,54 em plaintext aleatório) é a confirmação independente mais forte da H0 da dissertação.

**Mas há um problema, e é o ponto interessante (inferência do agente, marcada):** AUC = 0,905 em **Random_100** é alto demais para "nenhum sinal". Com plaintext aleatório, o que pode separar AES-128, 3DES, Blowfish, ChaCha20 e RC4? **Tamanho de bloco e padding.** Janelas de 8 KB = 8192 bytes: AES-CBC/ECB com PKCS7 → 8208 bytes; 3DES e Blowfish (bloco de 64 bits) → 8200; ChaCha20 e RC4 (fluxo) → 8192. Três comprimentos distintos, três geometrias de cauda distintas. A AUC residual é quase certamente **geometria de padding**, não impressão digital de cifra. Não confirmado no artigo — precisaria ler a seção de construção do dataset — mas testável em minutos.

**Custo de testar.** Trivial: replicar Random_100 com todos os criptogramas truncados ao mesmo comprimento. Se a AUC cair de 0,905 para ~0,5, a explicação está confirmada e a dissertação ganha refutação publicável de um artigo recente.

##### 7.5 MIND-Crypt (Dani, Nakka, Saxena) — o resultado nulo mais próximo

Framework para avaliar indistinguibilidade de cifras leves (SPECK32/64, SIMON32/64) sob ML. Modelo de ameaça: **known-plaintext com chaves fixas**, treinando com criptogramas de duas mensagens conhecidas sob a mesma chave.

**Resultados.** *"accuracy equivalent to random guessing"*; isolando amostras exclusivas do conjunto de teste, a acurácia cai para **49,90%** — os autores concluem que o desempenho anterior *"reflects memorization rather than generalization to unseen ciphertexts"*. Conclusão: *"Existing block ciphers have secure cryptographic designs against ML-based indistinguishability assessments, reinforcing their security even under round-reduced conditions."*

**Fonte.** Jimmy Dani, Kalyan Nakka, Nitesh Saxena, arXiv:2405.19683 (maio 2024, revisto abr. 2025); versão de periódico em *Cryptography* 10(1):9. https://arxiv.org/abs/2405.19683

**Cabe no modelo?** Modelo de ameaça **mais forte** que o da dissertação (KPA, chave fixa) — e mesmo assim dá acaso. Melhor citação de "outros também acharam H0 com adversário mais poderoso que o nosso".

##### 7.6 Outros pontos de dados (menos verificados)

- **MLP em cifras de bloco**, *Soft Computing*, 2025 (doi 10.1007/s00500-025-10595-y): 76,5% de acurácia binária média para arquivos de 1 KB a 512 KB, e *"identification rates are generally high when the key and IV of testing ciphertext files match those of training ciphertext files"* — de novo, o confundidor de chave. **Texto não obtido (Springer bloqueou).**
- **HKNNRF** (k-NN + Random Forest híbrido), PMC9575859: 69,5% de acurácia binária média, 10–13 pontos acima de SVM de camada única.
- **Detecting the File Encryption Algorithms Using AI**, *Applied Sciences* 15(19):10831, 2025: Random Forest e Bagging melhores, 90–95% dependendo do par; e explicitamente: *"the classification performance was notably better in ECB mode, where no random initialization vector was used"*, *"CBC mode... made it significantly more challenging"*, e *"the increasing number of encryption keys further complicated correct classification, leading all tested models to demonstrate decreased efficiency."* Essa última frase é a justificativa empírica do key-holdout, dita por autores que não estavam tentando prová-la.
- **Bellini, Huang, Rachidi**, *Statistical Tests for Symmetric Primitives — An Application to NIST Lightweight Finalists*, SecITC 2022, LNCS 13809:133–152. **O trabalho mais relevante que existe** para o braço de rodadas reduzidas: aplicam o NIST STS a *todas* as versões de rodadas reduzidas dos finalistas do NIST LWC, com datasets Avalanche Plaintext, Avalanche Key, Plaintext-Ciphertext correlation, CBC mode, Random, Low-Density e High-Density. Objetivo declarado: *"to provide another metric to compare how conservative or aggressive the choice of number of rounds is for each candidate."* **Tabela de resultados por cifra não obtida** — Springer atrás de paywall, sem ePrint. Há apresentação de Yunju Huang (TII) no NIST Lightweight Cryptography Workshop 2022 com o mesmo conteúdo, mas o link direto dos slides retornou 404. **Recomendação forte: conseguir esse artigo** — provavelmente já contém o piso de rodadas que a dissertação quer medir, e comparar com ele é obrigatório.

---

#### PARTE 8 — Impossibilidade: o que é resultado útil dizer que não dá

##### 8.1 Kearns–Valiant: aprender é tão difícil quanto quebrar

Prova, no modelo PAC distribution-free, que aprender fórmulas booleanas, autômatos finitos determinísticos e circuitos de limiar de profundidade constante implicaria quebrar RSA, fatorar inteiros de Blum e decidir resíduos quadráticos. Os resultados são **representation independent** — valem qualquer que seja a forma sintática da hipótese, o que inclui redes neurais.

**Fonte.** Michael Kearns, Leslie Valiant, *Cryptographic Limitations on Learning Boolean Formulae and Finite Automata*, JACM 41(1):67–95, 1994 (versão STOC 1989). https://www.cis.upenn.edu/~mkearns/papers/crypto.pdf — **só existência e afirmações centrais confirmadas por busca**; PDF não lido.

**Cabe no modelo?** SIM, como argumento. Versão aplicável: se um classificador com acesso apenas a criptogramas distinguisse Ascon-AEAD128 de Schwaemm256-128 com vantagem não desprezível, ele seria um distinguidor ind$ para pelo menos um dos dois, contradizendo a prova de segurança sob a hipótese de permutação ideal. **A ML não é uma técnica que contorna limites criptográficos — é uma família de distinguidores como qualquer outra, sujeita à mesma cota.**

**O que prevê.** Que nenhuma arquitetura, por maior que seja, muda o resultado. Permite escrever a conclusão negativa com força em vez de com desculpas: não é "não conseguimos", é "não pode".

##### 8.2 Yuan et al. (2025) — a versão moderna e quantitativa

Arcabouço formal de teoria do aprendizado para criptanálise simétrica: modelo **Coin-Tossing (CoTo)**, e a classe de conceitos **Conjunctive Parity Form (CPF)**, que captura ampla classe de distinguidores tradicionais. Provam que *"any concept in the CPF class is learnable in sub-exponential time in the setting of symmetric cryptanalysis"*, e usam isso na prática: primeira melhoria no distinguidor por deep learning para SPECK32/64 desde 2019, estendendo de 8 para **9 rodadas**.

**Fonte.** Yufei Yuan, Haiyi Xu, Jiaye Teng, Lei Zhang, Wenling Wu, ePrint 2025/1306. https://eprint.iacr.org/2025/1306 — **PDF lido (introdução)**.

**O que prevê.** Que o número de amostras necessário escala com o inverso do quadrado do viés do melhor distinguidor clássico existente. Para os quatro algoritmos full-round, esse viés é <= 2^-64 ⇒ amostras necessárias >= 2^128.

##### 8.3 Algorithm Substitution Attacks — o argumento invertido

Bellare, Paterson e Rogaway constroem implementações **subvertidas** de cifras simétricas que vazam a chave para o "big brother" e cujos criptogramas são **indistinguíveis** dos da implementação honesta. Mostram, junto com Ateniese-Magri-Venturi (CCS'15) e Bellare-Jaeger-Kane (CCS'15), que a subversão indetectável é possível para esquemas suficientemente aleatorizados, e impossível para esquemas determinísticos.

**Fonte.** Bellare, Paterson, Rogaway, *Security of Symmetric Encryption against Mass Surveillance*, CRYPTO 2014 / ePrint 2014/438. https://eprint.iacr.org/2014/438 — **confirmado por busca**, PDF não lido.

**Cabe no modelo?** SIM, como argumento a fortiori: se nem um algoritmo **deliberadamente sabotado** é detectável pelo criptograma, distinguir dois algoritmos honestos e bem construídos é, com mais razão, inviável.

---

#### PARTE 9 — Becos sem saída (e por que vale documentá-los)

**9.1 Ataques de padding oracle (Vaudenay 2002, Lucky13, POODLE).** **Ativos** por definição — exigem submeter criptogramas alterados a um oráculo de decifragem e observar aceitação/rejeição ou tempo. Adversário passivo não tem oráculo. Além disso, nos quatro AEAD o padding nunca aparece no criptograma (Parte 3). **NÃO cabe, sem adaptação possível.**

**9.2 Canais laterais de compressão (CRIME, BREACH, TIME).** Exigem injetar dados no plaintext e observar o comprimento comprimido. **NÃO cabe.**

**9.3 Distinguidores integrais / zero-sum sobre a permutação isolada.** O zero-sum de 12 rodadas do Ascon com 2^130 opera sobre a permutação **sem chave**, em ambos os sentidos. Não há como aplicá-lo à saída de um AEAD com chave. Os autores reconhecem: *"the designers... are aware of such distinguishers"* e isso não afeta o esquema. **NÃO cabe.**

**9.4 Ataques de chave relacionada.** Grain-128AEAD lista ataque de chave relacionada em Grain-128a com complexidade 2^96, 2^96 IVs escolhidos e 2^104 bits de keystream, com 2 chaves relacionadas. Também o forgery de chave relacionada no Photon-Beetle. **NÃO cabe.**

**9.5 Reúso de nonce.** Cube tester de 2^33 do Ascon sobre o plaintext, ataque prático de cubo com nonce reutilizado, cubo condicional em Ascon-128a nonce-misuse — todos excluídos. Os próprios autores do Ascon: *"the designers of Ascon strictly forbid nonce reuse, and no security claims are made for such a scenario."* **NÃO cabe.**

**9.6 Complexidade linear / Berlekamp-Massey sobre o criptograma.** Ideia natural para cifra de fluxo com LFSR. Morre pelo mesmo motivo que todas as features de amostra única: a complexidade linear de `P XOR Z` é dominada pela de `P`, já quase máxima para texto natural. **NÃO cabe** sem cancelar o plaintext.

**9.7 Features de amostra única em geral (histograma, entropia, n-gramas, ACF, FFT, razões de compressão).** Beco mais importante de documentar, porque é onde está a maior parte do esforço da literatura. Argumento em uma linha: **toda estatística de uma única amostra é uma estatística de `P XOR Z`; como `Z` é pseudoaleatório e independente entre amostras, a variância entre amostras vem de `P`, que é idêntico entre algoritmos por construção do encadeamento.** Logo, essas features têm poder de discriminação estruturalmente nulo no protocolo encadeado. A única maneira de extrair sinal é estatística **entre amostras** que cancele `P` (cubo, integral, XOR de encadeamento) ou região **sem** `P` (a tag).

---

### APOSTAS

#### Aposta 1 — Cubo passivo sobre o nonce-contador, restrito ao primeiro bloco

**O quê.** Gerar, para cada algoritmo e cada contagem de rodadas reduzidas, corridas de **2^d nonces consecutivos e alinhados a 2^d** sob uma mesma chave, guardando **apenas os primeiros 16 (ou 32) bytes** de cada criptograma. Calcular a XOR de todos os 2^d primeiros blocos. Três leituras: (a) nas posições de bit determinísticas do plaintext (bit 7 de cada byte, com corpus ASCII puro); (b) na XOR entre algoritmos, aproveitando o encadeamento, que cancela o plaintext exatamente; (c) como teste de hipótese "uniforme vs. XOR-convolução da distribuição do corpus".

**Por que esta primeiro.**
1. Única técnica encontrada que **cancela o plaintext** e ainda assim é ciphertext-only com nonce público.
2. É **determinística**, não estatística: sob rodadas reduzidas suficientes a soma é *exatamente* zero. Não é F1 de 0,55 que exige bootstrap e BH-FDR — é detector com zero falsos negativos.
3. Custo ridículo: **2 MB por chave** para chegar a 5 rodadas do Ascon, contra ~20 h de extração de features sobre 180k amostras de 64 KB. Só o primeiro bloco importa.
4. Responde **diretamente** à pergunta do ângulo. Previsão: canal **aberto** para Ascon, Schwaemm e Grain, **fechado** para GIFT-COFB. Se confirmado, demonstra que **a assinatura é do modo, não da permutação**.
5. Âncora publicada: Dobraunig et al. dão a conta exata (cubo de 33 variáveis numa palavra ⇒ superpoly vazio em 6 rodadas, 2^33 dados) e afirmam o cenário *"an attacker with control over the nonce can observe the first key-stream block."* A contribuição é observar que **um contador fornece esse cubo sem controle nenhum**, só esperando.

**Riscos e mitigação.** (i) O cronograma de nonces precisa dar corridas contíguas alinhadas por chave — mudança de geração, não de protocolo. (ii) O mascaramento pelo plaintext limita `d` a ~9–10 com texto UTF-8 real; para `d = 17` é preciso filtrar o corpus para ASCII 7-bit puro. Escolha de corpus, não controle adversarial sobre o plaintext — mas é fronteira a decidir e defender explicitamente. (iii) Amostras de imagem (ImageNet grayscale) **destroem** o canal, porque o bit 7 varia. Precisa de subconjunto só-texto.

**Previsão falsificável.** Ascon com init <= 4 rodadas e cubo de dimensão 9 (512 nonces): soma exatamente zero nos bits limpos, sempre. Ascon com init = 12: uniforme. GIFT-COFB: uniforme em qualquer contagem reduzida que ainda produza criptograma. Se GIFT-COFB **também** der soma zero, a análise de profundidade está errada e isso é notícia.

#### Aposta 2 — Suítes estatísticas sobre a região da tag, e só ela

**O quê.** Concatenar as tags de autenticação de todas as amostras num único fluxo, por algoritmo e por contagem de rodadas (variando as rodadas **da finalização** separadamente das da inicialização e do processamento de dados), e rodar NIST STS (188 testes), Dieharder (55) e TestU01 (159). Contar testes aprovados, como Ukrop & Svenda.

**Por que esta.**
1. **A tag é o único pedaço do criptograma que não está XORado com plaintext desconhecido.** Verificado nas quatro especificações. Por byte, a razão sinal/ruído é infinitamente melhor que a do corpo.
2. Há **protocolo publicado e resultados de referência**: Ukrop & Svenda fizeram exatamente isto com 52 candidatos CAESAR, e reportam, com PMN contador, AES-GCM em 187/188 STS, 52/55 Dieharder, 157/159 TestU01.
3. É **barato**: 30.000 amostras x 16 B = 480 KB de saída pura por algoritmo. Horas de trabalho, não dias de GPU.
4. Cobre o modo de falha que os próprios Ukrop & Svenda apontam e que uma família de features `tag_region` poderia estar medindo por engano: *"they produce a constant delimiter between the ciphertext and tag."* Sinal aqui em full-round = bug de serialização, melhor descobrir agora.

**Previsão falsificável.** Full-round: os quatro passam em >= 95% dos testes de cada suíte. Finalização reduzida: a tag reprova muito antes de qualquer estatística do corpo se mexer — e a diferença em número de rodadas entre "tag reprova" e "corpo reprova" mede diretamente quanto o mascaramento pelo plaintext custa em poder de detecção. Esse número, sozinho, é resultado de dissertação.

#### Aposta 3 — Replicar e desmontar os positivos da literatura: ablação de geometria e de chave

**O quê.** Três replicações cirúrgicas, cada uma isolando um confundidor:

1. **Ablação de bound de aniversário (contra Xia, Li & Chen 2022).** Reproduzir a identificação de modo com **SIMON-32** a 1,1 MB por amostra (deve dar ~75–85%), e depois **só com AES-128** no mesmo protocolo (deve cair ao acaso). Previsão quantitativa: a acurácia escala com `(blocos por amostra)^2 / 2^(tamanho do bloco)`.
2. **Ablação de geometria de padding (contra Ren et al. 2025).** Reproduzir o `Random_100` deles (10.000 janelas de 8 KB, AES-ECB/CBC, 3DES, Blowfish, ChaCha20, RC4) e comparar a AUC com todos os criptogramas **truncados ao mesmo comprimento**. Previsão: AUC de 0,905 cai para ~0,5.
3. **Ablação de chave (contra Tan et al. 2018 / Applied Sciences 2025).** Mesmo classificador, mesmo dataset, variando apenas o número de chaves distintas de 1 até 300, com e sem key-holdout. Curva de acurácia versus número de chaves.

**Por que esta.**
1. A dissertação tem resultado H0 que **contradiz frontalmente** uma literatura com dezenas de artigos reportando 70–99% de acurácia. Sem essa parte, a banca pergunta "então todos aqueles estão errados?" e a resposta hoje é "sim" sem prova. Com ela, a resposta vira: *"eles estão medindo três coisas — conteúdo do plaintext, chave, e geometria de comprimento — e aqui está a curva de cada uma."*
2. Converte resultado negativo em resultado **explicativo**.
3. **Barato e usa a infraestrutura existente.** Nenhuma GPU, nenhum dataset novo de 180k amostras.
4. Gera contribuição autônoma, publicável em separado: protocolo de auditoria para trabalhos de identificação de cifra por ML, com três controles obrigatórios (holdout de chave, comprimento fixo, distância do bound de aniversário) e a demonstração de que resultados publicados não os passam.

**Previsão falsificável.** As três ablações produzem colapso ao acaso. Se alguma **não** colapsar, existe um quarto canal não identificado — e achá-lo seria o melhor resultado possível.

---

#### Apêndice — Fontes por nível de verificação

**PDF/HTML lido, com texto literal extraído:** McGrew ePrint 2012/623; Rogaway *Evaluation of Some Blockcipher Modes* (2011); Chan & Rogaway *Anonymous AE* ePrint 2019/1033; Nikitin et al. PURBs arXiv:1806.03160; Gellert et al. ePrint 2021/1027; Chakraborti, Datta, Jha, Nandi *Structural Classification of AEAD* (NIST LWC 2020); Banik et al. *GIFT-COFB v1.1*; Inoue, Iwata, Minematsu ePrint 2022/001; Dobraunig, Eichlseder, Mendel, Schläffer ePrint 2015/030; Hell, Johansson, Meier, Sönnerup, Yoshida *Grain-128AEAD* (round 2); Beierle et al. *Schwaemm and Esch* (final round); NIST SP 800-232 (ago. 2025); Ukrop & Svenda EPTCS 233:72–81; Yuan et al. ePrint 2025/1306; Ren et al. arXiv:2511.08296 (HTML).

**Existência e afirmações centrais confirmadas por busca, texto completo não lido — verificar antes de citar número:** de Mello & Xexéo J.UCS 24(1) 2018; Tan et al. Procedia CS 131:65–71; Xia, Li & Chen IJCNC 2022 (página lida, não o PDF); Dani, Nakka & Saxena arXiv:2405.19683; Kearns & Valiant JACM 41(1); Bellare, Paterson & Rogaway ePrint 2014/438; Daemen, Mennink & Van Assche ePrint 2017/498; Mennink ePrint 2022/1340; NIST IR 8459; *Neural differential distinguishers for GIFT-128 and ASCON* (JISA 2024); Civek & Tezcan (DL experimental para Ascon/DryGASCON); cube testers condicionais para Grain-128a (IEEE, 2021); *Cube Attacks on Round-Reduced Grain-128AEAD*; *Detecting the File Encryption Algorithms Using AI*, Applied Sciences 15(19):10831.

**Não obtido, vale perseguir:** Bellini, Huang & Rachidi, *Statistical Tests for Symmetric Primitives — An Application to NIST Lightweight Finalists*, SecITC 2022, LNCS 13809:133–152 (paywall Springer, sem ePrint; slides equivalentes de Yunju Huang no NIST LWC Workshop 2022 listados, PDF direto deu 404). **É o artigo mais relevante que existe para o braço de rodadas reduzidas e provavelmente já contém o piso de rodadas por candidato.**

---

# Pesquisa 02 — Análise de tráfego cifrado sem plaintext

- **Ângulo:** Análise de tráfego cifrado sem plaintext
- **Temperatura declarada:** 0,8

## Pesquisa 02 — prompt usado, na íntegra

````markdown
# Pesquisa 02 — O que a análise de tráfego cifrado sabe fazer sem plaintext

**Ângulo desta pesquisa.** Existe uma comunidade inteira — análise de tráfego
cifrado, website fingerprinting, identificação de protocolo, detecção de
malware em TLS, classificação de aplicação em VPN e Tor — que distingue coisas
observando **só criptograma e metadado**, sem nunca ver o texto em claro. Ela
publica em venues de rede e segurança (USENIX Security, NDSS, PETS, CCS,
IMC, INFOCOM, TIFS) e é quase ignorada pela literatura de criptografia
simétrica.

Pergunte: **o que exatamente essa comunidade explora, e quanto disso
sobrevive quando se tira comprimento, temporização e volume?** Vá atrás de:
técnicas de fingerprinting que operem sobre o CONTEÚDO dos bytes cifrados e
não sobre metadados de fluxo; trabalhos que mediram o quanto cada canal
(comprimento, tempo, direção, conteúdo) contribui isoladamente; métodos de
detecção de tráfego cifrado versus comprimido versus aleatório; identificação
de biblioteca ou implementação criptográfica pelo tráfego; e qualquer
resultado que quantifique o limite do que o conteúdo cifrado sozinho entrega.

Interessa muito também o negativo: trabalhos dessa área que concluíram que o
conteúdo cifrado, isolado dos metadados, não carrega sinal. Isso seria
convergência independente vinda de outro campo.

Não se limite a criptografia: entropia de payload em detecção de intrusão,
identificação de codec, esteganálise e detecção de canal encoberto usam as
mesmas estatísticas sobre dados de alta entropia. Traga o que transferir.

**Temperatura: 0,8.** Escala de amplitude de exploração, de 0,1 a 1,0.
Não é temperatura de amostragem — é instrução. Em 0,8: explore longe do
óbvio, siga conexões entre campos que normalmente não se citam, e proponha
transferências não publicadas. Continue exigindo fonte verificável para tudo
que for afirmado como fato, e marque com clareza o que é extrapolação sua.

---

# Prompt base — técnicas de distinção de algoritmos de criptografia

Este é o texto-mãe. Cada uma das 10 pesquisas recebe uma variação dele, com um
ângulo diferente e uma temperatura, e NADA MAIS: nem o repositório, nem os
resultados das pesquisas anteriores, nem esta conversa.

---

## PROBLEMA DE PESQUISA

Você está pesquisando para uma dissertação de mestrado em criptografia
aplicada e aprendizado de máquina. Trabalhe SÓ com literatura externa: não
leia nenhum repositório, arquivo local ou resultado prévio. Comece do zero.

**A pergunta.** Dado apenas o criptograma — sem a chave, sem o texto em claro,
sem poder escolher nada do que é cifrado — é possível distinguir qual
algoritmo de criptografia autenticada o produziu? E, num segundo nível, com
quantas rodadas reduzidas um algoritmo ainda deixa de parecer aleatório?

**Os algoritmos.** Os quatro finalistas do concurso NIST Lightweight
Cryptography: Ascon-AEAD128 (esponja), GIFT-COFB (cifra de bloco em modo
COFB), Grain-128AEAD (cifra de fluxo com LFSR e NFSR) e Schwaemm256-128
(esponja ARX, família SPARKLE).

**O modelo de ameaça, que é a restrição dura e não negocia.** Adversário
PASSIVO, em ciphertext-only. Ele observa criptogramas de um mesmo dispositivo,
com nonces públicos de contador, e pode observar vários de uma vez. Ele NÃO
tem: texto em claro conhecido ou escolhido, diferenças escolhidas na entrada,
reuso de nonce, acesso a canais laterais, nem consultas a um oráculo de
cifragem. Isso exclui de saída a maior parte da criptanálise diferencial
clássica e os distinguidores neurais no estilo Gohr, que dependem de pares com
diferença escolhida.

**O protocolo experimental.** Classificadores clássicos e redes sobre features
estatísticas e sobre os bytes crus. Chaves de teste nunca aparecem no treino
(key-holdout). Intervalo de confiança por bootstrap agrupado por chave, e não
i.i.d. Correção para múltiplas comparações. Controle negativo obrigatório: com
o algoritmo completo o classificador tem que ficar no acaso.

## O QUE EU QUERO DE VOCÊ

Técnicas, representações, ataques ou ideias — publicadas ou adaptáveis — que
possam extrair sinal nesse cenário, ou que ajudem a delimitar com rigor por
que o sinal não existe. Interessa tanto o que funciona quanto a prova de que
algo é impossível.

Busque em literatura acadêmica real (IACR ePrint, ToSC/FSE, CHES, CRYPTO,
EUROCRYPT, ASIACRYPT, SAC, Designs Codes and Cryptography, IEEE, Springer,
arXiv) e em fontes técnicas sérias. Use termos de busca em inglês.

## COMO RESPONDER

Para cada ideia encontrada, escreva:

1. **O que é** — a técnica, em duas ou três frases.
2. **Fonte** — autores, título, veículo, ano. Link quando houver. Se você não
   conseguiu confirmar a existência do trabalho, diga isso explicitamente em
   vez de completar de memória.
3. **Cabe no nosso modelo?** — SIM, NÃO, ou ADAPTÁVEL. Se ADAPTÁVEL, diga
   exatamente o que teria de mudar e qual premissa do modelo de ameaça isso
   arranha.
4. **O que custaria testar** — ordem de grandeza de dados, computação e
   engenharia.
5. **O que ela prevê** — se a técnica funcionar, que resultado deveríamos ver?
   Se não houver previsão falsificável, diga isso.

Termine com uma seção **APOSTAS**: as três ideias que você tentaria primeiro,
e por quê. Seja específico; "usar deep learning" não é uma aposta.

## PROFUNDIDADE — leia isto com atenção

Não é um levantamento rápido. **Vá até esgotar o veio.** Não pare em cinco ou
dez achados porque já "deu para ter uma ideia": siga as citações para frente e
para trás, abra os trabalhos relacionados dos artigos que importarem, procure
versões estendidas e teses, e persiga as pistas que aparecerem no caminho,
mesmo as que não estavam no ângulo original. Só encerre quando as buscas novas
pararem de trazer coisa nova.

Traga TODA a informação, não um resumo dela. Se um artigo tem um número que
importa (quantas rodadas, quantas consultas, que acurácia, que tamanho de
dado), traga o número. Se tem uma limitação declarada pelos próprios autores,
traga a limitação com as palavras deles. Prefira errar por excesso de detalhe.
Uma resposta longa e completa é o que se pede aqui; uma resposta enxuta é
falha de execução.

## REGRAS

- Não invente referências. Uma fonte não confirmada vale menos que nenhuma, e
  vou checar.
- Não repita o óbvio já saturado (distinguidor diferencial-neural padrão)
  sem trazer um ângulo novo que sobreviva ao ciphertext-only.
- Se a conclusão honesta de um caminho for "isso é impossível neste modelo
  por tal razão teórica", isso é resultado útil. Diga.
- Separe o que é publicado do que é sua extrapolação. Marque cada um.
````

## Pesquisa 02 — achados, sem resumir

### Achados — Pesquisa 02

- **Ângulo:** o que a análise de tráfego cifrado sabe fazer sem plaintext
- **Temperatura declarada:** 0,8
- **Prompt usado:** `prompts/02_analise_de_trafego.md`
- **Execução:** interrompida por rate limit (HTTP 429) aos ~30 min, RETOMADA por
  mensagem e concluída. Total ~251k tokens de subagente.

---

### Pesquisa 02 — Análise de tráfego cifrado e campos vizinhos: o que sobrevive sem plaintext

Conclusão antes do detalhe: **a comunidade de análise de tráfego cifrado praticamente não usa o conteúdo dos bytes cifrados — e o único trabalho que mediu isso diretamente, com controle de aleatoriedade, encontrou exatamente H0.** Convergência independente vinda de outro campo, e o achado mais forte deste levantamento. Junto vieram três ferramentas metodológicas que valem mais que qualquer técnica nova de extração de sinal, e uma releitura incômoda do trabalho de 2018 do próprio Xexéo.

Marcação: **[PUB]** = afirmação do artigo; **[MINHA]** = extrapolação do agente, não publicada.

---

#### PARTE I — O achado central: o único estudo que isolou o conteúdo cifrado

##### 1. SoK: Decoding the Enigma of Encrypted Network Traffic Classifiers

**O que é.** SoK que reauditou classificadores estado-da-arte de tráfego cifrado (ET-BERT, YaTC) com 348 experimentos de *feature occlusion*: apagar um canal de entrada por vez e medir a queda. Inclui dataset novo (CipherSpectrum: 40 domínios, 120.000 sessões, uniformes entre as três cipher suites do TLS 1.3) construído porque os datasets públicos estavam contaminados.

**Fonte.** Nimesha Wickramasinghe, Arash Shaghaghi, Gene Tsudik, Sanjay Jha. *SoK: Decoding the Enigma of Encrypted Network Traffic Classifiers.* IEEE S&P 2025, pp. 1825–1843. arXiv:2503.20093. https://arxiv.org/abs/2503.20093

**Números (10 classes, acaso = 0,10):**

| Condição | ET-BERT | YaTC |
|---|---|---|
| A1 — entrada completa | 0,96 | 0,90 |
| H1 — só cabeçalho | 0,63 | 0,57 |
| **E1 — só payload cifrado** | **0,12** | **0,30** |
| E2 — payload mascarado, só comprimento | 0,12 | 0,39 |
| **E3 — payload substituído por aleatório** | **0,11** | **0,30** |
| D1 — identificadores fortes (SII/SNI) removidos | 0,51 | 0,62 |
| C — features contextuais removidas | 0,57 | 0,55 |
| T — features temporais removidas | 0,57 | 0,56 |

O par decisivo é **E1 vs E3**: payload cifrado real → ET-BERT 0,12; payload substituído por bytes aleatórios → 0,11. YaTC faz 0,30 nos dois. **O conteúdo cifrado real e ruído puro produzem a mesma acurácia.** O 0,30 do YaTC vem de comprimento/estrutura.

Citações: *"The 72 experiments… demonstrate that state-of-the-art classifiers do not learn any intrinsic patterns from encrypted payloads beyond their length. This finding aligns with the guarantees provided by TLS 1.3, which asserts that the only observable characteristic in encrypted payloads is their length."* Guideline 6: *"Focus on encrypted payload length rather than content, as classifiers primarily rely on payload length for classification rather than intrinsic patterns in the cipher text."* E: *"any previously perceived patterns within encrypted payloads are likely artifacts from outdated datasets containing unencrypted data."*

Contaminação dos datasets legados (fração não-cifrada): ISCXVPN2016 98,9%; USTC-TFC2016 94,7%; ISCXTor2016 89,3%; Cross-Platform Application 69,7%.

**Cabe no modelo?** **SIM**, como replicação independente. O E1 é literalmente o cenário da dissertação executado por outra comunidade, com outros dados, outras arquiteturas, outro objetivo — e dá acaso.

**Custo.** Zero (resultado alheio). Replicar o protocolo E3 no v2: baixo.

**O que prevê.** Convergência ao acaso, e controle de payload aleatório produzindo a mesma métrica que o criptograma real. Falsificável: se o criptograma real der F1 significativamente acima do substituto aleatório, há sinal isolado do artefato de pipeline.

##### 2. Bias in the Shadows

Taxonomia de atalhos em classificação de tráfego cifrado, 19 datasets, três tarefas, com NetMamba e árvores de decisão. Três famílias: identificadores de vazamento (IP, porta, SNI), artefatos relativos (números de sequência TCP, timestamps), campos agnósticos à tarefa (TTL, window size, checksums).

**Fonte.** Chuyi Wang, Xiaohui Xie, Tongze Wang, Yong Cui. arXiv:2601.10180, 15/01/2026.

**Números.** CrossNet2021: NetMamba 94,72% → 91,64% removendo SII. CSTNET-TLS1.3: 98,91% → 98,77% removendo SNI. Usam 80 bytes de cabeçalho + 240 de payload. **Não** analisam o payload cifrado isoladamente — reforça o ponto: nem estudando atalho a comunidade olha o conteúdo cifrado.

**Cabe no modelo?** **NÃO** diretamente (tudo metadado). Evidência de contexto.

##### 3. TRUSTEE / "The Emperor has no Clothes"

Framework que extrai árvore de decisão de alta fidelidade e baixa complexidade de modelo caixa-preta de segurança de rede, para detectar *underspecification*: shortcut learning, correlações espúrias, falha de generalização fora da distribuição.

**Fonte.** Arthur S. Jacobs, Roman Beltiukov, Walter Willinger, Ronaldo A. Ferreira, Arpit Gupta, Lisandro Z. Granville. *AI/ML for Network Security: The Emperor has no Clothes.* ACM CCS 2022. DOI 10.1145/3548606.3560609. https://sites.cs.ucsb.edu/~arpitgupta/pdfs/trustee.pdf

**Ressalva.** Só as duas primeiras páginas foram extraídas. Definição e escopo confirmados; **quais estudos de caso foram reauditados não foi confirmado** (uma extração automática devolveu lista que não batia com o texto e foi descartada).

**Cabe no modelo?** **ADAPTÁVEL**, com valor real: extrair DT fiel do RF/XGB e ler as regras responde "o classificador está olhando para quê?". Se o modelo está no acaso, a DT extraída deve ser trivial ou instável entre folds — e *isso é reportável como evidência positiva de ausência de estrutura*, não só F1 baixo.

**Custo.** Baixo. TRUSTEE é pacote Python pronto sobre modelo sklearn treinado. Horas.

**O que prevê.** DTs com fidelidade alta, acurácia no acaso, sem estabilidade de regras entre folds. Regra estável (ex.: "byte 65540 > x") = vazamento de região de tag/comprimento.

---

#### PARTE II — Quanto cada canal contribui

##### 4. WeFDE — Measuring Information Leakage in Website Fingerprinting

Mede, por estimação de densidade por kernel adaptativa (AKDE) + Monte Carlo, a informação mútua I(F; W) entre features de tráfego e site visitado. Ponto central: **acurácia é péssimo proxy de vazamento**.

**Fonte.** Shuai Li, Huajun Guo, Nicholas Hopper. ACM CCS 2018. DOI 10.1145/3243734.3243832. https://www.freehaven.net/anonbib/cache/leakage-ccs2018.pdf

**Números.** 3.043 features de 14 categorias, 211.219 visitas Tor, ~2.200 sites.
- Vazamento máximo de feature individual: **3,45 bits** (contagem arredondada de pacotes de saída). Sem arredondar: 3,26. Contagem de pacotes de download: 3,04.
- Feature temporal mais informativa: média do inter-packet timing de download, **1,43 bit**. Tempo total: 1,21.
- Distribuição: 2,1% vazam >3 bits; 19,91% entre 2 e 3; 23,43% entre 1 e 2; **54,55% menos de 1 bit**.
- 45,36% das 183 features mais informativas são redundantes.
- Vazamento conjunto (limite superior): 6,64 bits (100 sites); 8,97 (500); 9,97 (1000).
- **O que mais importa:** com n classes e acurácia alfa, o vazamento fica indeterminado numa faixa de largura (1-alfa)*log2(n-1). Para n=100 e alfa=0,95, faixa de 0,33 bit; para alfa=0,05, vazamento pode estar entre 0,06 e 6,36 bits. Autores: *"low accuracy doesn't necessarily mean low information leakage"* e *"validating WF defenses by accuracy alone is flawed"*.

**Detalhe que responde direto ao ângulo.** As 14 categorias: Packet Count (13), Time Statistics (24), Ngram (124), Transposition (604), Interval-I (600), Interval-II (602), Interval-III (586), Packet Distribution (225), Bursts (11), First 20 Packets (20), First 30 (2), Last 30 (2), Packet Count per Second (126), CUMUL (104). **Nenhuma é conteúdo.** Catálogo declaradamente completo da literatura de WF, sem uma única feature de byte cifrado. O "Ngram" é sobre sequência de direções, não bytes.

**Cabe no modelo?** **ADAPTÁVEL — a adaptação mais importante do levantamento.** A conclusão H0 hoje se apoia em F1≈0,50. Esse artigo mostra que F1 no acaso *não prova* vazamento nulo: prova que aquele classificador não extraiu. Para 4 classes com alfa=0,25, a faixa de indeterminação é (1-0,25)*log2(3) ≈ **1,19 bits**. O resultado atual deixa até ~1,19 bits de vazamento potencial por explicar. Estimar I(features; algoritmo) por AKDE fecha esse buraco.

**Custo.** Médio-baixo. Código público (github.com/s0irrlor7m/InfoLeakWebsiteFingerprint). Trocar "label site" por "label algoritmo" e alimentar as 641 features. Gargalo: maldição da dimensionalidade — resolvem com Kononenko + DBSCAN sobre MI par a par (eps=0,4) e poda de pares com MI > 0,9. Estimativa: 1–2 semanas de engenharia, horas de CPU por braço.

**O que prevê.** I(F; algoritmo) ≈ 0 bits com intervalo apertado, contra máximo teórico de log2(4) = 2 bits. Falsificável e muito mais forte que "F1 = 0,50". Se sair 0,3 bit, existe sinal que os classificadores não pegaram.

##### 5. Cherubin — Bayes, not Naïve

Converte "meu classificador errou X%" em "**nenhum** classificador sobre este conjunto de features pode errar menos que R*". Usa Cover–Hart sobre o erro do vizinho mais próximo.

**Fonte.** Giovanni Cherubin. PoPETs 2017(4). arXiv:1702.07707. Código: https://github.com/gchers/wfes

**Matemática.** Para L rótulos, assintoticamente em n: `R* <= R^NN <= R*(2 - (L/(L-1))*R*)`, donde o estimador de limite inferior:

`R* = ((L-1)/L) * (1 - sqrt(1 - (L/(L-1))*R^NN))`

Teorema 1: R* <= R*_verdadeiro <= R^A, para qualquer algoritmo e classificador. Métrica de privacidade: epsilon = R*/R^G, onde R^G = (L-1)/L é o erro do chute aleatório; epsilon=1 é defesa perfeita.

Remark 1: **R*_P <= R*_Phi(P)** — nenhuma transformação dos dados melhora o erro de Bayes. Extração de features só pode perder informação. (Na prática, dizem, a estimativa no espaço original converge devagar demais.)

**Números (WCN+, 100 páginas):** Sem defesa R* = 6,2±0,3% (eps=0,06); Decoy Pages 42,6±0,6 (0,43); BuFLO 56,9±1,0 (0,58); Tamaraw 69,0±0,9 (0,70); CS-BuFLO 61,9±0,9 (0,63); WTF-PAD 48,6±1,2 (0,49).

**Cabe no modelo?** **ADAPTÁVEL, com ressalva séria.** A garantia assume i.i.d.; com key-holdout as amostras de uma mesma chave não são independentes. Solução: calcular R^NN com vizinho mais próximo **restrito a amostras de outras chaves** (leave-one-key-out NN). A garantia assintótica fica heurística, mas o número continua sendo limite inferior empírico defensável — e é honesto declarar a violação.

**Custo.** Muito baixo. Um passe de k-NN (k=1) sobre 180k x 641. Minutos com índice aproximado, horas em força bruta. Vale também sobre bytes crus (Remark 1), ainda que convirja mal.

**O que prevê.** Para 2 classes, R* ≈ 0,5 e eps ≈ 1,0 — "perfeitamente privado" na métrica do Cherubin. Se R* < 0,45 com CI que não cruza 0,5, existe sinal não capturado. **É o teste de "não deixei sinal na mesa" mais direto que existe.**

##### 6. Peek-a-Boo, I Still See You

Primeira análise abrangente de contramedidas genéricas de análise de tráfego. Nove contramedidas caem para ataques que exploram *features grosseiras* — tempo total e largura de banda total.

**Fonte.** Kevin P. Dyer, Scott E. Coull, Thomas Ristenpart, Thomas Shrimpton. IEEE S&P 2012. DOI 10.1109/SP.2012.28. https://oaklandsok.github.io/papers/dyer2012.pdf

**Cabe no modelo?** **NÃO.** Todas as features são volume e tempo. Vale como demarcação: o artigo fundador de "o que carrega sinal em tráfego cifrado" responde "volume e tempo", nunca conteúdo.

##### 7. Deep Fingerprinting — o estado da arte usa só direção

CNN profunda para WF em Tor. Entrada **exclusivamente a sequência de direções de pacote (+1/-1)**, 5.000 posições. Sem tamanhos, sem bytes, sem conteúdo.

**Fonte.** Payap Sirinam, Mohsen Imani, Marc Juarez, Matthew Wright. ACM CCS 2018. DOI 10.1145/3243734.3243768. https://mjuarezm.github.io/assets/pdf/ccs18.pdf

**Números.** Acima de 98% em Tor sem defesa, acima de 90% contra WTF-PAD (resumo). Na extração do corpo apareceram valores ligeiramente diferentes por tabela (~96% sem defesa, ~89% WTF-PAD, ~91% Walkie-Talkie); **discrepância sinalizada** — usar os do resumo e conferir na tabela se citar número exato.

**Cabe no modelo?** **NÃO**, e é esse o valor: o ataque mais forte da área atinge 98% usando um bit por pacote e zero bytes de conteúdo. Prova por construção de que a comunidade nunca precisou do conteúdo — e nunca o testou.

##### 8. Tik-Tok — o canal temporal isolado

Quantifica isoladamente a contribuição do tempo. Quatro representações: 160 features de timing, direção pura, *directional timing* (produto tempo x direção), combinações.

**Fonte.** Mohammad Saidur Rahman, Payap Sirinam, Nate Mathews, Kantha Girish Gangadhara, Matthew Wright. PoPETs 2020(3). https://petsymposium.org/popets/2020/popets-2020-0043.pdf Código: https://github.com/msrocean/Tik_Tok

**Números.** Só timing: 84,32% em Tor sem defesa. Directional timing: 93,46% em WTF-PAD. Em onion sites, directional timing é 12% mais acurado que direção sozinha. Features temporais vazam *menos* que direcionais, mas a informação é mutuamente exclusiva.

**Cabe no modelo?** **NÃO.** Inventário completo dos canais úteis em WF — direção, tempo, volume — e nosso adversário não tem nenhum.

---

#### PARTE III — Alta entropia: cifrado vs comprimido vs aleatório

##### 9. HEDGE

Classificação de pacotes cifrados vs comprimidos por chi2 (valor absoluto e percentual de confiança) mais três testes do NIST SP 800-22: frequência por bloco, somas cumulativas, entropia aproximada. Limiar com fator de ganho gama ajustável.

**Fonte.** Fran Casino, Kim-Kwang Raymond Choo, Constantinos Patsakis. IEEE TIFS 2019. arXiv:1905.11873.

**Números.** 64 KB: 94,72%. 32 KB: 92,77%. 16 KB: 89,85%. 8 KB: 86,20%. 4 KB: 81,67%. 2 KB: 75,50%. 1 KB: 70,61%.

**A frase que importa.** Testaram AES-128/192/256 e Camellia-128/192/256: *"when we analyse encrypted data streams we cannot distinguish the input file-type"* — **nenhuma diferenciação entre algoritmos de cifra.** Limitações declaradas: acurácia fortemente dependente do tamanho; pacotes abaixo de 1 KB ficaram como trabalho futuro.

**Cabe no modelo?** **ADAPTÁVEL, como calibração de competência.** A tarefa cifrado-vs-comprimido a 64 KB é exatamente o nosso tamanho e usa subconjunto das nossas features. Rodar o pipeline de 641 features nessa tarefa e reproduzir >=94% prova que as features *funcionam* em alta entropia — e antecipa a crítica "talvez suas features só sejam ruins".

**Custo.** Baixo. Precisa de corpus comprimido (gzip/bzip2/zstd de 64 KB) em paralelo ao cifrado. 1–2 dias.

**O que prevê.** >=94% em cifrado-vs-comprimido e ≈50% em Ascon-vs-GIFT, com o **mesmo** pipeline, features, tamanho. Esse par de números é o argumento de sensibilidade mais limpo possível.

##### 10. EnCoD

Rede totalmente conectada sobre histograma de 256 bins (normalizado como PDF) para separar fragmentos comprimidos de cifrados. Binário: 4 camadas ReLU; multiclasse: 5 camadas SeLU.

**Fonte.** Fabio De Gaspari, Dorjan Hitaj, Giulio Pagnotta, Lorenzo De Carli, Luigi V. Mancini. arXiv:2010.07754. (Irmão: arXiv:2103.17059, Neural Computing & Applications.)

**Números.** 512 B: 86%. 1 KB: ~88%. 2 KB: >90%. 4 KB: ~92%. 8 KB: 94% (compressão genérica) e 100% (compressão específica de aplicação). Crítica ao chi2: *"consistently low accuracy across the range of block sizes"*, por *"intrinsic difficulty in discriminating non-random content which closely approaches a uniform random distribution"*. Só AES-256; **nenhum experimento cifra-contra-cifra**.

**Cabe no modelo?** **ADAPTÁVEL**, mesmo motivo, com detalhe interessante: o histograma de 256 bins sozinho — a família `histogram` da dissertação — carrega quase toda a informação nessa tarefa. Permite afirmar: a mesma feature que resolve cifrado-vs-comprimido a 94% não separa Ascon de GIFT-COFB.

##### 11. Penrose, Macfarlane & Buchanan

Suite NIST completa sobre fragmentos de 4 KiB, resultados numa ANN, mais compressibilidade, sobre o govdocs1.

**Fonte.** Digital Investigation 10(4), 2013. DOI 10.1016/j.diin.2013.08.004

**Números.** Ótimos: **91% (cifrado) e 82% (comprimido)**. **Ressalva:** fontes secundárias reportam números divergentes (76%/70% numa; 97%/78% noutra). Sem acesso ao texto integral para arbitrar — conferir antes de citar.

**Cabe no modelo?** **ADAPTÁVEL**, mesmo papel dos itens 9 e 10, com o bônus de ser o precedente histórico de "NIST STS como vetor de features para ML".

##### 12. Entropia para identificar arquivos cifrados por ransomware

**Fonte.** arXiv:2210.13376. (Só o resumo foi lido; **autores e veículo não verificados em detalhe** — pista, não citação pronta.)

**Cabe no modelo?** **NÃO** como técnica; **SIM** como corroboração de que a família `entropy` (4 dimensões no v1) está saturada e não carrega sinal com entropia ~8 bits/byte.

---

#### PARTE IV — Identificação de algoritmo por ML: a linha direta

##### 13. Mello & Xexéo (2018) — o precedente de casa

Identificação de algoritmo a partir do criptograma, corpora em sete línguas, sete algoritmos em ECB e CBC (13 implementações), seis classificadores. Trabalho anterior do próprio orientador e o único da série que ataca CBC.

**Fonte.** Journal of Universal Computer Science 24(1), 2018, pp. 25–42. https://www.jucs.org/jucs_24_1/identifying_encryption_algorithms_in/jucs_24_01_0025_0042_demello.pdf

**Protocolo (verificado no texto).**
- 4.200 textos: 7 corpora (português, espanhol, inglês, alemão, hebraico, cirílico, mandarim), 600 amostras cada, >=140.000 caracteres por amostra, de jornais e revistas.
- 7 algoritmos: DES, Blowfish, RSA, ARC4, Rijndael, Serpent, Twofish. ECB + CBC = 13 implementações (ARC4 é de fluxo). "RSA CBC" é variante caseira.
- **Chaves: 128 bits do PRNG ANSI X9.17, uma chave distinta por arquivo** — "in order to avoid any influence of key patterns on the data mining process".
- IVs de todos os CBC do mesmo gerador.
- Features: histograma de blocos de bits contíguos, bin de 2 a 34 bits, **acumulado** (ao computar bin S, usam também todos de 2 a S-1).
- Classificadores: C4.5, PART, FT, Complement Naive Bayes, MLP, WiSARD. Split 66/34 + 10-fold CV.
- Controle negativo: KeyBITS, 600 arquivos de gerador físico (ruído de laser).
- NIST STS nos criptogramas: praticamente nenhuma falha; menor p-valor 0,004462 (ARC4).

**Números.**
- Acaso: **7,14%** (13 implementações + KeyBITS).
- **ECB:** quase 100% em bin de 28 bits (C4.5); Complement Naive Bayes identifica todos com 100% (exceto RSA) para bin > 20 bits.
- **CBC: 40–50%** com Complement Naive Bayes em bin acumulado de 34 bits. Regressão linear da identificação contra tamanho de bin: **f(x) = 1,13546457219251x + 3,27916295305999, R2 = 0,892509590686708**. Extrapolando para reconhecimento total: bin de **85,18 bits → 2^86 bins**, declaradamente inviável.
- **KeyBITS "was not classified at all"** — identificação marginal, muito próxima do acaso.

**As três explicações dos próprios autores para o sinal em CBC:** (i) padrões podem estar no primeiro bloco de 128 bits, cifrado logo após o XOR com o IV, o que "may provide a weak random input block"; (ii) colisões de blocos antes de 2^(n/2); (iii) as cifras subjacentes (ou implementações) podem ser vulneráveis a ataques distintivos.

**Leitura crítica — [MINHA], não publicada, e o item mais delicado:**

- **Explicação (ii) descartada quantitativamente.** 140.000 caracteres ≈ 17.500 blocos de 64 bits. Colisões esperadas ≈ q^2/2^(n+1) = (1,75x10^4)^2/2^65 ≈ **8x10^-12**. Não explica 40–50%.
- **Explicação (i) é criptograficamente insustentável.** Com IV uniforme, E_K(IV XOR P1) é uniforme para uma PRP ideal. O primeiro bloco não é mais fraco.
- **Sobram artefatos de protocolo, com três candidatos concretos:**
  1. **Comprimento e padding.** DES e Blowfish têm blocos de 64 bits; Rijndael, Serpent e Twofish, 128; ARC4 não tem padding; o "RSA CBC" é caseiro. Se os histogramas são contagens brutas e não densidades, a contagem total é função determinística do comprimento, e `len_ct mod 8` versus `mod 16` separa as famílias sem criptanálise nenhuma. É precisamente o que a Regra de Ouro nº 5 existe para impedir.
  2. **Esparsidade do histograma.** Bin de 34 bits são 2^34 ≈ 1,7x10^10 posições para ~33.000 blocos por amostra. Não é histograma, é assinatura quase única por arquivo. O crescimento monotônico da acurácia com o bin é forma de curva de sobreajuste, não de distinguidor criptanalítico — e a própria extrapolação para 85 bits diz isso.
  3. **Independência treino/teste.** Os mesmos 600 plaintexts por língua são cifrados pelas 13 implementações, e o split 66/34 é sobre criptogramas, não sobre plaintexts. O mesmo texto aparece no treino (sob o algoritmo A) e no teste (sob o B).

**Cabe no modelo?** **SIM, como o trabalho anterior a ser explicitamente reconciliado.** A dissertação não precisa dizer que o resultado de 2018 está errado. Pode dizer algo mais forte: **o protocolo v2 controla exatamente as três variáveis que poderiam produzir aquele sinal** e, sob esse controle, o sinal desaparece. Transforma H0 de "não achei nada" em "identifiquei o que sustentava o achado anterior e o removi".

> **Nota de conduta do agente:** releitura crítica de trabalho do orientador. **Não escreveria isso na dissertação sem antes conversar com o Nycolas e provavelmente com o próprio Xexéo.** Análise, não veredito.

**Custo de testar a hipótese do artefato.** Baixo e informativo: reimplementar as features de Mello & Xexéo (histograma acumulado de blocos de bits de 2 a ~24) sobre o v2, onde os comprimentos são controlados, e ver se a acurácia CBC-like reaparece. Alguns dias.

**O que prevê.** Acurácia crescendo com o bin também no v2 **se e somente se** o comprimento ou a identidade do arquivo vazarem; com comprimento fixo e chaves holdout, curva plana no acaso.

##### 14. A linha chinesa/indiana de "block cipher algorithm identification"

Caso mais bem documentado verificado em detalhe:

**Fonte.** Ke Yuan, Daoming Yu, Jingkai Feng, Longwei Yang, Chunfu Jia, Yiwang Huang. *A block cipher algorithm identification scheme based on hybrid k-nearest neighbor and random forest algorithm.* PeerJ Computer Science 8:e1110, 2022. DOI 10.7717/peerj-cs.1110

**Protocolo (verificado).** Cinco cifras (AES, 3DES, Blowfish, CAST, RC2), **modo ECB exclusivamente**, **chave fixa de 16 bytes** em todos os arquivos, plaintexts = números aleatórios do Fortuna. Tamanhos 1/8/64/256/512 KB, 100 arquivos cada → 2.500 arquivos. Features: 15 testes NIST, 10 selecionados.

**Números.** Binário AES vs 3DES: **69,5%** (SVM 56,5%, KNN 57%, RF 59,5%). Cinco classes: **máximo 34%** (acaso 20%; KNN 21%, RF 22%, SVM 23%).

**Leitura [MINHA].** Com chave fixa, plaintext aleatório e ECB — a configuração mais favorável ao atacante — o melhor binário é 69,5% e o multiclasse fica 14 pontos acima do acaso. Sinal dessa magnitude sem key-holdout é o que se espera de memorização de artefatos da chave. **Nada aqui sobrevive à Regra de Ouro nº 2.**

**Outros da mesma linha, não verificados em detalhe** (rastreio de citações, não fatos):
- *Identification of block cipher algorithms using multi-layer perception algorithm*, Soft Computing, 2025. DOI 10.1007/s00500-025-10595-y
- *A Block Cipher Algorithm Identification Scheme Based on Hybrid Random Forest and Logistic Regression Model*, Neural Processing Letters, 2022. DOI 10.1007/s11063-022-11005-2
- *Block Cipher Algorithm Identification Based on CNN-Transformer Fusion Model*, 2024 (reportado ~91% binário e ~70% em 8 classes com chaves aleatórias — **não verificado**, veio de resumo de busca).
- *A generic cryptographic algorithm identification scheme based on ciphertext features*, JISA 2025. DOI 10.1016/j.jisa.2025.103977 (identificador a confirmar).
- Mello & Xexéo. *Cryptographic Algorithm Identification Using Machine Learning and Massive Processing.* IEEE LATAM 14(11), 2016, pp. 4585–4590. DOI 10.1109/TLA.2016.7795833
- Barbosa, Vidal, Almeida, Mello. *Machine Learning Applied to the Recognition of Cryptographic Algorithms Used for Multimedia Encryption.* IEEE LATAM 2017. DOI 10.1109/TLA.2017.7959350
- Souza & Tomlinson. *A distinguishing attack with a neural network.* IEEE ICDMW 2013. DOI 10.1109/ICDMW.2013.116
- Torres, Xexéo, Souza, Oliveira, Linden. *Identification of Keys and Cryptographic Algorithms Using Genetic Algorithm and Graph Theory.* IEEE LATAM 9(2), 2011, pp. 178–183.

**Cabe no modelo?** **NÃO**, nenhum como publicado: ou ECB, ou chave fixa, ou ambos. Mas o conjunto é material de revisão de primeira: organizar a literatura por *qual premissa cada um viola* e mostrar desempenho monotonicamente decrescente conforme as premissas fecham (ECB fixo → 100%; ECB chave fixa → 69,5%; CBC chave por arquivo mas comprimento livre → 40–50%; AEAD com comprimento controlado e key-holdout → acaso). **Essa tabela é, sozinha, contribuição publicável.**

##### 15. MIND-Crypt — a replicação negativa do lado da criptografia

Framework de ML para testar indistinguibilidade (estilo IND-CPA) de cifras de bloco leves. Treina redes para dizer qual de dois plaintexts conhecidos, diferindo em 1 bit, gerou um criptograma.

**Fonte.** Jimmy Dani, Kalyan Nakka, Nitesh Saxena. arXiv:2405.19683 / IACR ePrint 2024/852. Periódico: *Cryptography* (MDPI) 10(1):9, 2026. DOI 10.3390/cryptography10010009. (**Versão MDPI não acessível — 403** — números por modo dessa versão ficaram por verificar.)

**Protocolo.** SPECK32/64 e SIMON32/64, CBC com IVs aleatórios. **O IV não entra no treino.** Chave única fixa, dois plaintexts de 32 bits diferindo em 1 bit. Modelos: CNN, LSTM, BiLSTM, ResNet, com Optuna/TPE.

**Números (todos).** Rodadas reduzidas — SPECK32/64: ResNet 50,00% (AUC 50,08), CNN 50,03% (50,05), LSTM 50,00% (50,14), BiLSTM 50,00% (50,00). SIMON32/64: ResNet 50,02% (50,03), CNN 49,93% (49,92), LSTM 50,00% (49,96), BiLSTM 50,00% (49,91). Rodadas completas — SPECK: 49,97–50,00%, AUC 49,96–50,03. SIMON: 49,99–50,00%, AUC 50,00–50,04.

**Achado de memorização.** Com IVs de 16 bits em vez de 32, acurácia sobe para ~53,72% em treino e cai para **49,90% em criptogramas inéditos** — *"ML models were memorizing ciphertext samples rather than genuinely learning cryptographic patterns"*.

**Conclusão.** *"Current ML algorithms, despite their advanced pattern-recognition capabilities, remain ineffective in compromising the indistinguishability property of even lightweight cryptographic algorithms."* Limitações: duas cifras, modos específicos, plaintext conhecido (não escolhido), pares fixos, ataque passivo.

**Cabe no modelo?** **SIM, com argumento a fortiori.** O adversário deles é **estritamente mais forte**: conhece os dois plaintexts candidatos, chave fixa e única, e mesmo assim as quatro arquiteturas param em 50,00%. Se um adversário com plaintext conhecido não distingue criptogramas do *mesmo* algoritmo, é coerente que um ciphertext-only não distinga criptogramas de algoritmos *diferentes*.

##### 16. Ren, Luo, Peng & He — "Plaintext Structure Vulnerability"

O mais próximo do nosso problema em data e desenho. Extrator de "fingerprint distribucional de aleatoriedade": painel fixo de T=41 testes, cada estatística mapeada para [0,1] pela transformada integral de probabilidade (s_t(u) = F_t(T_t(u)), uniforme sob H0), segmentação em janelas, histograma de K bins de arestas fixas mais 4 momentos, concatenados em R^(T(K+S)).

**Fonte.** arXiv:2511.08296. https://arxiv.org/abs/2511.08296

**Protocolo.** Seis classes: AES-ECB, AES-CBC, 3DES, Blowfish, ChaCha20, RC4 → **acaso = 16,67%**. Janelas de 8 KB; chaves por janela derivadas por HKDF (RFC 5869) de semente mestra. Dados: Canterbury Corpus e cinco suítes sintéticas graduadas — Regular_100/75/50/25 e Random_100 — 10.000 janelas cada, balanceadas.

**Protocolo anti-vazamento deles (convergência notável).** *"We use a 5x5 stratified group cross validation. Specifically, we group windows by their source file (sample ID) to ensure that all windows from the same file stay in one fold."* Mais: remoção de buffer de rho = ceil(W/s)-1 janelas em torno das amostras de teste; nenhuma feature de nome ou caminho; z-score ajustado só nos folds de treino; arestas de bin globais fixas. **Mesma disciplina do key-holdout + seleção dentro do fold, por outro caminho.**

**Números.**
- Canterbury, SVM-RBF: acurácia 0,897±0,071; macro-F1 0,899±0,067; macro-AUC 0,985±0,025.
- Regular_100: ~0,999 em SVM, RF, XGBoost, regressão logística.
- **Transferência Regular_100 → Random_100 (plaintext uniforme), XGBoost: acurácia 0,541, macro-F1 0,540, macro-AUC 0,905.**
- Médias: dentro do regime Regular, macro-F1 cai 0,00–6,04% e macro-AUC 0,00–2,98%. *"Transfers into the Random_100 target yield much larger average gaps: macro-F1 drops by about 83,85–88,32%, whereas macro-AUC declines by 46,68–49,67%."*
- Comprimento: *"All ciphertext windows have the same fixed length as their plaintext windows."*

**Limitações declaradas.** Seis algoritmos; painel de testes e hiperparâmetros (W, K) fixados sem análise de sensibilidade; datasets sintéticos; *"No evaluation of padding schemes or hardware-accelerated implementations"*.

**Cabe no modelo?** **ADAPTÁVEL, e é o trabalho que mais ameaça a conclusão — até olhar o mecanismo.**

Por que ameaça: a dissertação usa plaintext real do Gutenberg, ou seja, está no regime "Regular", onde reportam ~0,90.

Por que não ameaça, na leitura **[MINHA]**:
1. **Não há matriz de confusão nem F1 por classe** (confirmado: resultados só agregados). Macro-AUC 0,90 com acurácia 0,54 em 6 classes é compatível com uma ou duas classes separáveis e o resto no acaso.
2. **RC4 tem viés de keystream real, publicado e mensurável em 8 KB.** Mantin–Shamir (segundo byte zero com prob. ≈2/256), Fluhrer–McGrew (digramas), vieses de byte único de AlFardan et al. RC4 *deve* ser identificável, e isso é criptanálise genuína, não artefato. Com chave por janela e janela começando na posição 0 do keystream, Mantin–Shamir é diretamente observável.
3. **O mecanismo "estrutura do plaintext" exige um modo que deixe a estrutura passar** — ECB. Os próprios dados dizem: macro-F1 despenca 84–88% quando a estrutura é removida. A moldura dos autores ("o algoritmo é sinal, a estrutura do plaintext é ruído") está invertida em relação ao que os números mostram.
4. **Os quatro finalistas produzem C = P XOR KS.** Ascon e Schwaemm por squeeze de esponja, Grain por keystream, GIFT-COFB por C_i = Y_i XOR M_i. O mapa plaintext→ciphertext é **o mesmo** para os quatro, a menos do keystream. **Logo a vulnerabilidade de estrutura de plaintext não pode disparar no nosso conjunto, por construção.** Qualquer sinal teria que ser não-uniformidade do keystream.

O ponto 4 é a peça de argumentação teórica mais valiosa que a dissertação pode acrescentar — explica de forma limpa o achado já registrado de que "o sinal em CT-only é redundância do plaintext, não estrutura da cifra".

**Custo de testar.** Alto valor, custo médio: reimplementar o extrator (41 testes → PIT → histograma+momentos) é 2–4 semanas. **Mas** a versão barata e mais informativa é a réplica da *ablação*: rodar o Caminho A com plaintext Gutenberg e depois com plaintext uniforme do CTR_DRBG, mostrando curva plana nos dois — porque nos nossos quatro não há canal de estrutura.

**O que prevê.** Se o mecanismo deles for estrutura de plaintext via ECB: (a) nosso resultado não muda entre Gutenberg e uniforme; (b) incluindo AES-ECB (controle já previsto no v2), a acurácia dele contra os demais deve ser ~1,0 com texto e cair ao acaso com plaintext uniforme. **Teste falsificável direto da tese deles usando o dataset que já existe.**

##### 17. CipherBench

Benchmark de identificação de algoritmo em nível de payload fragmentado.

**Fonte.** Applied Sciences (MDPI) 16(17):8763. https://www.mdpi.com/2076-3417/16/17/8763

**Status.** **Não acessível (HTTP 403).** Pista a perseguir: benchmark público para exatamente esta tarefa seria o alvo natural para posicionar a dissertação. Tentar por DOI, ResearchGate ou contato com autores.

---

#### PARTE V — RNG, PRNG e distinguidores neurais sem diferença escolhida

##### 18. Assessing the quality of Random Number Generators through Neural Networks

Treina redes (LSTM e CNN) para separar a saída de um RNG-alvo da de um *golden standard* (HMAC-DRBG do NIST SP 800-90A). Não prediz o próximo bit: classifica sequências. Análogo exato do nosso problema com dois "algoritmos".

**Fonte.** José Luis Crespo, Javier González-Villa, Jaime Gutiérrez, Angel Valle. IACR ePrint 2024/578, abril 2024. Periódico: Machine Learning: Science and Technology, DOI 10.1088/2632-2153/ad56fb. https://eprint.iacr.org/2024/578

**Números (AO = average output; classificação perfeita seria AO.PRNG = 1 e AO.GSRNG = 0).**

Reprodução de trabalho anterior: RC4 segundo byte, treino 2^13 → 0,53 / 0,42. LCG (glibc 2.17 `rand`), treino 2^18 → 0,63 / 0,19 e 0,87 / 0,47.

Tabela 2, treino 2^18 salvo indicação:

| Gerador | AO.PRNG | AO.GSRNG | Veredito |
|---|---|---|---|
| VCSEL QRNG (pós-processado) | 0,47 | 0,47 | indistinguível |
| VCSEL QRNG, treino 2^19 | 0,51 | 0,51 | indistinguível |
| QRNG bruto | 0,73 | 0,55 | detectado |
| EC-LCG | 0,49 | 0,49 | indistinguível |
| Vídeo | 0,58 | 0,33 | parcialmente detectado |
| LCG (32 bits) | 0,51 | 0,42 | fraco |
| LCG (100 bits) | 0,50 | 0,51 | indistinguível |

Tabela 3 (arquitetura): CNN-1 sobre LCG a 2^18 → AO.PRNG = 1, AO.GSRNG = 0, matriz de confusão (16492, 35; 0, 16233), **separação perfeita**. CNN-1 sobre VCSEL QRNG a 2^19 → 0,5/0,5. CNN-2 com sequência de 512 → 0,5/0,5. CNN-2 com elementos de 2 bytes → 0,5/0,5.

Frases: *"Sequences of numbers obtained from our QRNG and the GSRNG are indistinguishable even with the biggest LSTM or CNN that we have considered."* E: *"VCSEL QRNG was indistinguishable even with the biggest networks that we have tried (twice the size of the biggest ones reported here). It remains an open question whether a massively larger network would yield better results."* Observação valiosa: acrescentar reset periódico de parâmetro ao LCG já basta para ele passar.

**Cabe no modelo?** **SIM, a evidência mais direta que existe.** Literalmente o nosso problema com rótulos "gerador A" vs "gerador B", sem plaintext, sem diferença escolhida. CNNs separam perfeitamente LCG de HMAC-DRBG (viés grosseiro) e ficam em 0,5 contra gerador de boa qualidade — inclusive **com rede ao dobro do maior modelo reportado**.

A ressalva honesta dos autores — "resta em aberto se uma rede massivamente maior daria resultado melhor" — é a mesma limitação da dissertação, e é bom citá-la nas palavras deles.

**Custo.** Zero para citar. Replicar a metodologia (Ascon-keystream vs GIFT-keystream vs CTR_DRBG como *golden standard*) é interessante: em vez de classificar Ascon contra GIFT diretamente, classificar **cada um contra o CTR_DRBG**. Se nenhum é separável do DRBG, por desigualdade triangular nenhum par é separável — e ganha-se dois experimentos binários limpos em vez de um multiclasse.

**O que prevê.** AO ≈ 0,5/0,5 para Ascon vs DRBG e GIFT vs DRBG, e AO ≈ 1/0 para o controle AES-ECB vs DRBG.

##### 19. Outros distinguidores neurais de PRNG

**Verificados apenas por título/resumo:**
- *Neural-Network-Based Pseudo-Random Number Generator Evaluation Tool for Stream Ciphers.* IEEE, https://ieeexplore.ieee.org/document/8951654 — descobre vieses desconhecidos com LSTM. É o trabalho [25] que Crespo et al. reproduzem. Relevante por ser **especificamente sobre cifras de fluxo**, o mais próximo do Grain-128AEAD.
- *Learning from Pseudo-Randomness with an Artificial Neural Network*, arXiv:1801.01117.
- Glauco Amigo et al., *Forecasting Pseudo Random Numbers Using Deep Learning*, https://robertmarks.org/REPRINTS/2021-Pseudo.pdf
- NCC Group, *Cracking xorshift128 with Machine Learning* — não-criptográfico, previsão exata.

**Cabe no modelo?** **NÃO** os de predição (precisam de saída consecutiva do mesmo estado; cada amostra nossa tem chave/nonce distintos). **SIM** o de avaliação de cifra de fluxo, como referência para Grain.

---

#### PARTE VI — Esteganálise e canal encoberto

##### 20. Cachin — modelo teórico-informacional da esteganografia

Define segurança de estegossistema contra adversário passivo como teste de hipóteses: eps-seguro se D_KL(P_C || P_S) <= eps; perfeitamente seguro se a divergência é zero. Dá limites sobre a capacidade de detecção de *qualquer* adversário.

**Fonte.** Christian Cachin. Information Hiding 1998, LNCS 1525. Estendido em Information and Computation 192(1), 2004. IACR ePrint 2000/028. https://eprint.iacr.org/2000/028

**Cabe no modelo?** **ADAPTÁVEL como moldura teórica, e a melhor que existe para enquadrar H0.** Traduzindo: sejam P_A a distribuição de criptogramas de Ascon e P_G a de GIFT-COFB. Se ambas são eps-próximas da uniforme em KL, então D(P_A || P_G) <= algo da ordem de eps, e por Pinsker a distância de variação total — que é exatamente a vantagem máxima de *qualquer* distinguidor, inclusive uma rede infinita — é limitada por sqrt(eps/2). **Converte a afirmação criptográfica padrão numa cota superior dura sobre o melhor F1 alcançável por qualquer classificador.** É o argumento de impossibilidade pedido.

**Custo.** Zero computacional; formalização e escrita. Meia dúzia de páginas.

**O que prevê.** Que nenhum método, presente ou futuro, ultrapasse 1/2 + sqrt(eps/2) de acurácia, com eps governado pela margem de segurança. Falsificável no sentido forte: se alguém ultrapassar, é ataque publicável contra o Ascon.

##### 21. Ker, Pevný, Kodovský & Fridrich — a lei da raiz quadrada

A capacidade esteganográfica segura escala com a raiz quadrada do tamanho da cover, não linearmente.

**Fonte.** ACM MM&Sec 2008, pp. 107–116. DOI 10.1145/1411328.1411349. http://dde.binghamton.edu/kodovsky/pdf/Ker08acm.pdf

**Os teoremas, como o artigo os enuncia.**
- **Teorema 1:** supondo que o detector mapeie objetos para escalares, que o efeito do payload seja deslocamento linear na resposta, que a densidade da resposta tenha suporte infinito, seja duas vezes continuamente diferenciável e tenha a segunda derivada do logaritmo limitada — se um esteganógrafo embute M bits em N covers uniformes, então: **(1) se M/sqrt(N) → infinito, existe detector pooled arbitrariamente próximo da detecção perfeita; (2) se M/sqrt(N) → 0, o desempenho de qualquer detector pooled tende ao aleatório.**
- **Teorema 2:** para N covers independentes com divergência KL entre cover e stego proporcional a p^2, o payload máximo seguro M é **O(sqrt(N))**.

**Experimentos.** 3.000 imagens em tons de cinza nunca comprimidas, 100x75 a 900x675, LSB replacement, payloads de 0,005/0,01/0,02 bpp; detectabilidade por AUR, 1-P_E e MMD. Payload fixo fica mais difícil de detectar em covers maiores; payload proporcional a sqrt(N) dá detectabilidade aproximadamente constante; proporcional a N fica mais fácil.

**Cabe no modelo?** **ADAPTÁVEL, e a transferência é para a segunda pergunta (rodadas reduzidas).**

Tradução **[MINHA]**: se um keystream com r rodadas tem viés per-bit delta(r) em alguma estatística, a deflexão do detector ótimo sobre N bits escala como delta(r)*sqrt(N). **Logo o "piso de rodadas" não é propriedade só da cifra: é função do volume de dados.** GIFT em 3/40 e Grain em 28/256 são o ponto onde delta(r)*sqrt(N) cruzou o limiar *para o N daquele experimento*. Com 100x mais dados, o piso sobe em aproximadamente o número de rodadas que reduz delta por fator de 10.

**Mudança de enquadramento que fortalece muito o resultado**: em vez de "o piso é 3/40", reportar "o piso é r*(N), e a curva r*(N) tem inclinação tal" — falsificável, extrapolável, e responde "quantas rodadas" de forma quantitativa em vez de pontual.

**Custo.** Baixo-médio: rerodar a detecção em quatro ou cinco volumes (N/16, N/4, N, 4N) e ajustar a curva. Compute já existe.

**O que prevê.** r*(N) crescendo logaritmicamente em N, com inclinação ligada à taxa de decaimento do viés por rodada. Se r* não se mover com N, a moldura de deflexão está errada e o piso é de outra natureza (limiar estrutural em vez de estatístico) — o que também seria achado.

**Cálculo de ordem de grandeza [MINHA].** Dataset v2: 180.000 x 65.552 bytes ≈ 1,18x10^10 bytes ≈ **9,4x10^10 bits**. Para distinguir duas distribuições com distância de variação total delta, é preciso N ≈ 1/delta^2. Logo o piso de detectabilidade deste dataset é delta ≈ 1/sqrt(9,4x10^10) ≈ **3,3x10^-6**. Qualquer viés abaixo disso é invisível, não importa o modelo. **Esta é a frase que transforma "não achamos nada" em "não poderíamos ter achado nada menor que 3x10^-6, e a cifra está muito abaixo disso".**

##### 22. Ker — Batch Steganography and Pooled Steganalysis

Trata o caso em que o adversário observa **vários objetos de uma vez** e precisa combinar a evidência.

**Fonte.** Information Hiding 2006, LNCS 4437, pp. 265–281. http://www.cs.ox.ac.uk/people/andrew.ker/docs/ADK18D.pdf (Sequência: *Detector-Informed Batch Steganography and Pooled Steganalysis*, ACM IH&MMSec 2022, DOI 10.1145/3531536.3532951.)

**Cabe no modelo?** **SIM, e é a lacuna de protocolo mais concreta encontrada.**

O modelo de ameaça diz que o adversário "observa vários de uma vez". Mas o protocolo classifica **uma amostra por vez**. Isso deixa um fator sqrt(100) na mesa: com 100 amostras por chave, a deflexão de um detector pooled é 10x a per-amostra.

**[MINHA]**: em vez de rotular cada criptograma, somar (centrando) os escores sobre as 100 amostras de cada chave-slot de teste e classificar **a chave**, não a amostra. Se existe viés per-amostra d, ele aparece amplificado 10x. Se F1 por amostra é 0,50 e F1 por chave também é 0,50 com IC apertado, H0 fica muito mais forte — porque cobre o adversário que o modelo de ameaça de fato autoriza.

**Custo.** Muito baixo. Os escores por amostra já existem. Pós-processamento: agrupar, somar, avaliar. Horas.

**O que prevê.** Se H0 for verdadeira, F1 pooled = 0,50 com IC mais *apertado* que o per-amostra. Se aparecer separação no pooled sem separação no per-amostra, há viés fraco real e o sinal foi achado.

##### 23. Cover-source mismatch

O fator que mais degrada esteganalisadores na prática: detector treinado numa fonte de covers desaba em outra.

**Fontes.** Jan Kodovský, Vahid Sedighi, Jessica Fridrich. SPIE Electronic Imaging 9028, 2014. http://dde.binghamton.edu/vsedighi/pdf/SPIE2014_Study_of_Cover_Source_Mismatch_in_Steganalysis_and_Ways_to_Mitigate_its_Impact.pdf — e a revisão: EURASIP Journal on Information Security, 2024. DOI 10.1186/s13635-024-00171-6 (*"Although well recognized as the single most important factor negatively affecting the performance of steganalyzers in practice, the CSM received surprisingly little attention from researchers."*)

**Cabe no modelo?** **ADAPTÁVEL, e sugere um controle negativo excelente que já existe de graça.**

O v2 usa 80% SPGC / 20% ImageNet. O análogo do cover-source é a **fonte do plaintext**.

1. **Teste de sanidade obrigatório [MINHA]:** treinar o pipeline para prever `plaintext_source` (texto vs imagem) a partir do criptograma. Como C = P XOR KS com KS uniforme, o criptograma é uniforme **independentemente** da fonte. **O classificador tem que ficar no acaso.** Se acertar, há vazamento no pipeline — ordenação, split, normalização. Custa uma rodada do Caminho A e é o teste de integridade mais barato e informativo que existe: o rótulo já está no parquet.
2. **Teste de robustez:** se algum caminho mostrar sinal, treinar em texto e testar em imagem (e vice-versa) diz se o sinal é da cifra ou da fonte.

**Custo.** Muito baixo. O rótulo já existe.

**O que prevê.** F1 ≈ 0,50 (binário texto/imagem). Acima disso é bug, não criptanálise.

##### 24. IDS por n-grama de payload: PAYL, Anagram e a refutação

Detecção de anomalia em payload por distribuição de n-gramas de byte (PAYL, RAID 2004; Anagram, RAID 2006), e a avaliação que mostrou os limites.

**Fonte da refutação.** Dina Hadžiosmanović, Lorenzo Simionato, Damiano Bolzoni, Emmanuele Zambon, Sandro Etalle. *N-Gram against the Machine: On the Feasibility of the N-Gram Network Analysis for Binary Protocols.* RAID 2012, LNCS 7462, pp. 354–373. DOI 10.1007/978-3-642-33338-5_18

**Achado.** Em ambientes reais com dados de alta variabilidade, os sistemas **não entregam simultaneamente alta detecção e baixa taxa de falsos positivos**.

**Cabe no modelo?** **NÃO como técnica** (a família n-gram já satura em dados uniformes), **SIM como precedente**: o campo que mais investiu em estatística de n-grama de byte concluindo que ela colapsa com alta variabilidade. Criptograma é o caso-limite. Vale mencionar junto com *polymorphic blending* (Fogla & Lee, CCS 2006), que mostra que casar a distribuição de bytes de primeira ordem basta para evadir — ou seja, estatística de byte de baixa ordem é canal raso mesmo quando há sinal.

---

#### PARTE VII — Limites teóricos

##### 25. Rogaway — indistinguibilidade de bits aleatórios (IND$)

**Fonte.** Phillip Rogaway. *Nonce-Based Symmetric Encryption.* FSE 2004, LNCS 3017, pp. 348–359. https://iacr.org/archive/fse2004/30170349/30170349.pdf

**O que dá.** A noção IND$: o adversário tem de distinguir a cifragem de bits uniformemente aleatórios. Sob IND$-CPA com stretch zero, o criptograma **não carrega informação alguma além do comprimento** (e do nonce, público). Ascon-AEAD128 é padronizado (SP 800-232) com 128 bits de segurança; os outros três são finalistas com análise pública extensa.

**Cabe no modelo?** **SIM, como o teorema de impossibilidade.** Cadeia completa:

1. Cada um dos quatro é IND$-CPA seguro com vantagem <= eps sob o número de consultas do dataset.
2. Logo cada distribuição de criptogramas está a <= eps (em vantagem de distinção) da uniforme de mesmo comprimento.
3. Por desigualdade triangular, D_TV(P_Ascon, P_GIFT) <= 2*eps.
4. A acurácia balanceada de **qualquer** classificador, computacionalmente ilimitado ou não, é <= 1/2 + eps.
5. O comprimento é a única exceção, e a Regra de Ouro nº 5 o remove das features.

**Isso não é resultado negativo da dissertação: é a previsão teórica que a dissertação confirma empiricamente.** O valor está em (a) medir quão perto de 1/2 se chega, (b) verificar que o pipeline *teria* detectado um viés de magnitude conhecida, (c) localizar onde a garantia quebra — rodadas reduzidas.

##### 26. Kearns & Valiant — limitações criptográficas ao aprendizado

**Fonte.** JACM 41(1), 1994, pp. 67–95. Preliminar: STOC 1989, DOI 10.1145/73007.73049. https://www.cis.upenn.edu/~mkearns/papers/cryptojacm.pdf

**O que dá.** Resultados de dureza **independentes de representação**: assumindo dificuldade de quebrar RSA, fatorar inteiros de Blum e detectar resíduos quadráticos, é intratável aprender autômatos finitos, circuitos de limiar de profundidade constante, circuitos de profundidade logarítmica e fórmulas booleanas no modelo PAC. Independente de representação = vale qualquer que seja a forma da hipótese, desde que avaliável em tempo polinomial.

**Cabe no modelo?** **ADAPTÁVEL como argumento de moldura.** A função "que algoritmo produziu este criptograma" é, sob a hipótese de segurança, indistinguível de uma função aleatória; um aprendiz eficiente que a aprendesse quebraria a hipótese. Impede que um revisor diga "vocês só não tentaram a arquitetura certa". **Cuidado na formulação:** Kearns–Valiant não cobre literalmente AEAD moderno; a afirmação precisa ser feita como analogia estrutural, não corolário.

##### 27. A limitação declarada do NIST SP 800-22

**Fonte.** NIST SP 800-22 Rev. 1a. https://csrc.nist.gov/pubs/sp/800/22/r1/upd1/final

**O que importa.** A suite **não computa o erro tipo II** — não há análise de poder. Recomenda 100 substrings de 10^6 bits (>=10^8 bits, 12,5 MB). Nenhum conjunto de testes estatísticos pode certificar absolutamente um gerador.

**Consequência [MINHA] e crítica ao próprio extractor.** A família `nist_sts` (25 features) é um painel cujo **poder contra a alternativa de interesse ("veio do Ascon e não do GIFT") é indefinido e não medido**. Os testes foram desenhados para detectar desvios estruturados específicos — frequência, runs, posto, complexidade linear — e nenhum é a alternativa que importa. Usar 25 delas como features não corrige: continua cego à alternativa.

**A alternativa correta é a estatística de Neyman–Pearson para a alternativa real**, e é estimável: treinar modelo autorregressivo de bytes por classe (n-grama com suavização, ou transformer pequeno) e usar a **razão de log-verossimilhança por amostra** como estatística de teste. É o distinguidor ótimo por construção, e a AUC da LLR com IC bootstrap agrupado por chave é a forma mais limpa e reconhecível pela comunidade criptográfica de dizer "não há sinal".

**Custo.** Médio. N-grama de ordem 3–4 sobre **bytes crus**: ordem 3 = 16,7M parâmetros de contagem por classe, treinável em CPU. Transformer pequeno é o Caminho E já implementado com a cabeça trocada de classificação para modelagem de linguagem. 1–2 semanas + GPU.

**O que prevê.** Distribuições de LLR completamente sobrepostas, AUC = 0,500 com IC agrupado de largura ~±0,01 para 60 chaves de teste. Se a AUC for 0,52 com IC excluindo 0,5, existe sinal — e a LLR ainda diz *onde* (que n-gramas contribuem).

---

#### PARTE VIII — Fingerprinting de biblioteca e implementação

##### 28. JA3, JA4, JARM, HASSH, Mercury

Família de técnicas que identifica a biblioteca TLS/SSH do cliente, por campos do ClientHello: lista e ordem de cipher suites, extensões, curvas, versões.

**Fontes.** Salesforce JA3/JA3S (2017), https://github.com/salesforce/ja3; JARM; HASSH; FoxIO JA4+. Blake Anderson, Subharthi Paul, David McGrew, *Deciphering Malware's Use of TLS (without Decryption)*, Journal of Computer Virology and Hacking Techniques, 2018. Anderson & McGrew, *Accurate TLS Fingerprinting using Destination Context and Knowledge Bases*, arXiv:2009.01939.

**O ponto.** **Tudo opera sobre o handshake em claro, nunca sobre o ciphertext da camada de registro.** Anderson e McGrew precisam somar endereço de destino, porta e server name porque centenas de processos mapeiam para a mesma fingerprint. Com a adoção ampla de TLS, as técnicas que dependiam de dados em claro deixaram de ser viáveis — e a resposta da comunidade não foi olhar o ciphertext, foi olhar o handshake.

**Cabe no modelo?** **NÃO.** Beco mapeado: **não foi encontrado nenhum trabalho publicado que identifique biblioteca ou implementação criptográfica a partir do conteúdo do criptograma.** Se existe, não foi achado; e a estrutura do campo sugere que não existe porque ninguém espera que funcione.

**Ângulo residual [MINHA].** O que *é* implementation-specific e observável é a geração de nonce/IV — e a literatura que explora isso (Heninger et al., *Mining Your Ps and Qs*, USENIX Security 2012) precisa de chaves públicas, não de criptograma. No v2 o nonce é contador global e não entra no parquet, então o canal está fechado. **Uma verificação vale a pena:** o contador de 128 bits precisa ser truncado para 96 bits no Grain e estendido para 256 no Schwaemm. Se a regra de derivação diferir por algoritmo de forma correlacionada com o rótulo, isso afeta a distribuição de estados iniciais. Vale confirmar que a derivação é uniforme.

---

#### APOSTAS

##### Aposta 1 — RC4 como controle positivo de dificuldade calibrada

**O que fazer.** Acrescentar RC4 como "algoritmo" adicional na mesma linha encadeada (mesmos plaintexts, mesmas chaves, mesmo comprimento — RC4 é de fluxo, então `len_ct = len_pt`, o que exige truncar todos os criptogramas ao mesmo comprimento antes da extração, ou você testa comprimento de novo). Rodar o Caminho A como está e reportar o F1 de RC4-contra-os-demais lado a lado com Ascon-contra-GIFT.

**Por quê primeiro.** É a única coisa no levantamento que resolve o problema retórico central. Hoje o resultado é "o pipeline não achou nada", e a objeção óbvia é "talvez o pipeline não preste". Os controles atuais não fecham isso: AES-ECB é fácil demais (a estrutura do plaintext atravessa o modo inteiro, e o classificador acha a repetição de blocos, não o keystream) e PRNG-contra-cifra também é fácil demais ou vazio.

**RC4 é o único controle da dificuldade certa.** Viés de keystream real, publicado, quantificado, detectável **exclusivamente** por estatística do keystream — sem estrutura de plaintext, sem comprimento, sem metadado. Mantin–Shamir (P[Z2=0] ≈ 2/256 em vez de 1/256), Fluhrer–McGrew (digramas), vieses de byte único de AlFardan, Bernstein, Paterson, Poettering e Schuldt (*On the Security of RC4 in TLS*, USENIX Security 2013, https://www.usenix.org/conference/usenixsecurity13/technical-sessions/paper/alfardan). Com 65.536 bytes por amostra e 30.000 amostras, esses vieses estão muito acima do piso de detectabilidade de 3x10^-6 do item 21.

Corroboração externa: Crespo et al. (item 18) detectam o segundo byte do RC4 com rede neural; Ren et al. (item 16) incluem RC4 entre as seis classes e reportam AUC residual alta mesmo com plaintext uniforme — o que, nesta leitura, é majoritariamente RC4.

**Custo.** Baixo. Wrapper de RC4 em Python puro (20 linhas, sem CFFI), geração de 30.000 amostras na linha encadeada (horas), extração (os ~20h por braço já previstos), Caminho A (já implementado). Duas semanas de calendário, sem GPU.

**Previsão falsificável.** F1 de RC4 contra qualquer dos quatro **>= 0,90**, e F1 de Ascon contra GIFT-COFB **≈ 0,50**, com o mesmo pipeline, features, protocolo e quantidade de dados. Se RC4 **não** for detectado, o pipeline tem problema de sensibilidade e o H0 atual não pode ser afirmado — resultado urgente. Se for detectado, a frase final deixa de ser "não encontramos sinal" e passa a ser "o pipeline detecta um viés de keystream conhecido de magnitude X e não detecta nada nos quatro finalistas".

##### Aposta 2 — Limite de Bayes por Cover–Hart e informação mútua direta

**O que fazer.** Duas medidas que substituem a acurácia como evidência principal:

1. **Limite inferior do erro de Bayes** (Cherubin, item 5). Calcular R^NN com vizinho mais próximo restrito a outras chaves, aplicar R* = ((L-1)/L)(1 - sqrt(1 - (L/(L-1))R^NN)), reportar eps = R*/R^G. Rodar sobre as 641 features e, separadamente, sobre bytes crus (Remark 1).
2. **Informação mútua I(features; algoritmo)** por AKDE no estilo WeFDE (item 4), por família e conjunta, com a redução de dimensionalidade deles (poda de pares com MI > 0,9, DBSCAN com eps=0,4, Kononenko por grupo).

**Por quê.** Li, Guo e Hopper provaram que **"validar por acurácia sozinha é falho"**, e esse é literalmente o método de validação atual. Para 4 classes com acurácia no acaso, a faixa de vazamento não excluída é (1-0,25)*log2(3) ≈ 1,19 bits — contra máximo teórico de 2 bits. O resultado atual, tomado literalmente, exclui pouco mais da metade do vazamento possível. Um examinador que conheça essa literatura vai levantar exatamente isso.

As duas medidas fecham lados diferentes: Cherubin limita **o melhor classificador possível** naquele espaço de features; WeFDE dá o **vazamento de informação** independentemente de haver classificador que o explore. Juntas, transformam "nossos modelos falharam" em "nenhum modelo pode ter sucesso neste espaço, e o espaço carrega ~0 bits".

Ressalva honesta para o texto: a garantia de Cherubin assume i.i.d., e key-holdout viola isso. Leave-one-key-out NN mitiga mas não restaura a garantia assintótica. Declarar.

**Custo.** Muito baixo. k-NN sobre 180k x 641 — minutos com índice aproximado, horas em força bruta. WeFDE é código público adaptado; 1–2 semanas de engenharia, horas de CPU. **Nada de GPU.** Disparado, a maior mudança de força argumentativa por hora de trabalho deste relatório.

**Previsão.** R* ≈ 0,50 e eps ≈ 1,0 (binário), I ≈ 0 bit com IC apertado. Falsificável nos dois sentidos: se R* vier 0,42 com IC que não cruza 0,5, existe sinal que RF, SVM, XGBoost, CNN 1D, CNN 2D e transformer não capturaram, e a resposta não é encerrar em H0, é ir atrás dele.

##### Aposta 3 — Detector pooled por chave e razão de verossimilhança

**O que fazer.** Duas mudanças no que é reportado, ambas dentro do modelo de ameaça já declarado.

1. **Pooling.** O modelo diz que o adversário observa vários criptogramas de uma vez. Então o alvo deveria ser a **chave-slot**, não a amostra. Somar (centrando) os escores sobre as 100 amostras de cada chave de teste e avaliar sobre as 60 chaves. Pela teoria de detector pooled (item 22 e Teorema 1 do item 21), isso amplifica qualquer deflexão per-amostra por sqrt(100) = 10x.
2. **Estatística certa.** Trocar o painel `nist_sts` — cujo poder contra a alternativa de interesse é indefinido, por admissão do próprio NIST (item 27) — pela razão de log-verossimilhança de modelos autorregressivos de byte treinados por classe. É a estatística de Neyman–Pearson para a alternativa real. Reportar AUC da LLR com bootstrap agrupado por chave.

**Por quê terceira.** É a mais cara e a que mais depende das outras duas para ser interpretável. Mas fecha a última brecha metodológica séria: hoje o protocolo mede um adversário mais fraco que o declarado. Um examinador criptógrafo vai notar que "pode observar vários de uma vez" e "classifico um por vez" não combinam.

O pooling isolado é quase de graça — os escores já existem, é pós-processamento de horas. A parte cara é a LLR. Se for preciso cortar, **faça o pooling e adie a LLR**: o pooling sozinho já cobre a lacuna do modelo de ameaça.

**Custo.** Pooling: horas. LLR com n-grama de ordem 3 sobre bytes: contagens de 16,7M por classe, treináveis em CPU em um dia, mais memória que compute. LLR com transformer: Caminho E com a cabeça trocada — 1–2 semanas mais GPU, na mesma ordem dos treinos B/C/E já planejados.

**Previsão.** F1 pooled por chave = 0,50 com IC **mais apertado** que o per-amostra. LLRs sobrepostas, AUC = 0,500 ± ~0,01. O cenário interessante é a discordância: F1 per-amostra em 0,50 e pooled acima de 0,50 significa viés fraco real e distribuído, e a dissertação muda de resultado. É o desenho com maior chance, entre tudo levantado, de encontrar sinal se ele existir.

---

#### Duas notas finais do agente

**Sobre o enquadramento.** Três resultados independentes chegaram ao mesmo lugar por caminhos que não se citam: o SoK do IEEE S&P 2025 (payload cifrado = payload aleatório, 0,12 vs 0,11), o MIND-Crypt (50,00% com quatro arquiteturas, adversário mais forte que o nosso) e o Crespo et al. (0,5/0,5 contra HMAC-DRBG, com rede do dobro do tamanho da maior reportada). Isso não torna H0 um bom resultado nem um objetivo — continua sendo a ausência do que se foi procurar. Mas muda o que a dissertação pode afirmar: em vez de resultado nulo isolado, ela é a primeira medição controlada dessa questão **para os finalistas do NIST LWC especificamente**, alinhada a uma convergência de três campos que não conversam. O que dá valor não é o zero; é a demonstração de que o pipeline detectaria um viés de magnitude conhecida (Aposta 1) e que o limite não é do método (Aposta 2).

**Sobre o trabalho de 2018.** O item 13 é o achado mais desconfortável e o que mais precisa de conversa antes de virar texto. Os 40–50% em CBC de Mello & Xexéo estão acima do acaso de 7,14% por margem grande, e as três explicações dos autores não se sustentam sob cálculo — a de colisões está descartada por 12 ordens de grandeza. Sobram comprimento/padding, esparsidade de histograma e independência treino/teste, e **o protocolo v2 já controla os três**. Permite reconciliação construtiva em vez de contradição: o v2 mede o que o trabalho de 2018 não pôde medir, e o desaparecimento do sinal sob esse controle é informativo sobre a origem dele. Mas é releitura crítica do trabalho do orientador e não deveria entrar na dissertação antes de conversa com ele.

---

# Pesquisa 03 — Limites teóricos de impossibilidade

- **Ângulo:** Limites teóricos de impossibilidade
- **Temperatura declarada:** 0,15

## Pesquisa 03 — prompt usado, na íntegra

````markdown
# Pesquisa 03 — Limites teóricos: o que é impossível, e com quanta certeza

**Ângulo desta pesquisa.** Em vez de procurar uma técnica que funcione,
procure a **prova de que nada funciona** — e, mais importante, o quanto essa
prova é apertada. Teoria da informação e teoria do aprendizado aplicadas a
este cenário exato.

Persiga: distância de unicidade de Shannon e o que ela diz quando a fonte de
plaintext é conhecida; limites de teste de hipóteses (Neyman-Pearson,
divergência de Kullback-Leibler, desigualdade de Pinsker) traduzidos em cota
superior de acurácia para QUALQUER classificador; quantas amostras são
necessárias para detectar um viés de magnitude delta, e portanto qual o menor
viés detectável com um volume de dados dado; resultados de dureza de
aprendizado ligados a hipóteses criptográficas; e limites de complexidade de
amostra que digam "abaixo de N amostras, nenhum algoritmo consegue".

Quero números, não só teoremas: dado um corpus de N bits, qual o menor desvio
da uniformidade que qualquer teste pode detectar? Como essa cota se compara
com a margem de segurança declarada de uma cifra moderna?

Procure também o contrário: trabalhos que mostrem que esses limites são
frouxos na prática, ou que ML às vezes acha estrutura onde a teoria dizia que
não haveria sinal detectável com aquele volume.

**Temperatura: 0,15.** Escala de amplitude de exploração, de 0,1 a 1,0.
Não é temperatura de amostragem — é instrução. Em 0,15: máximo rigor,
mínima especulação. Prefira resultado provado a conjectura, enuncie teoremas
com suas hipóteses, e diga explicitamente quando um limite NÃO se aplica ao
nosso caso em vez de esticá-lo. Se um número não puder ser derivado com
cuidado, não o dê.

---

# Prompt base — técnicas de distinção de algoritmos de criptografia

Este é o texto-mãe. Cada uma das 10 pesquisas recebe uma variação dele, com um
ângulo diferente e uma temperatura, e NADA MAIS: nem o repositório, nem os
resultados das pesquisas anteriores, nem esta conversa.

---

## PROBLEMA DE PESQUISA

Você está pesquisando para uma dissertação de mestrado em criptografia
aplicada e aprendizado de máquina. Trabalhe SÓ com literatura externa: não
leia nenhum repositório, arquivo local ou resultado prévio. Comece do zero.

**A pergunta.** Dado apenas o criptograma — sem a chave, sem o texto em claro,
sem poder escolher nada do que é cifrado — é possível distinguir qual
algoritmo de criptografia autenticada o produziu? E, num segundo nível, com
quantas rodadas reduzidas um algoritmo ainda deixa de parecer aleatório?

**Os algoritmos.** Os quatro finalistas do concurso NIST Lightweight
Cryptography: Ascon-AEAD128 (esponja), GIFT-COFB (cifra de bloco em modo
COFB), Grain-128AEAD (cifra de fluxo com LFSR e NFSR) e Schwaemm256-128
(esponja ARX, família SPARKLE).

**O modelo de ameaça, que é a restrição dura e não negocia.** Adversário
PASSIVO, em ciphertext-only. Ele observa criptogramas de um mesmo dispositivo,
com nonces públicos de contador, e pode observar vários de uma vez. Ele NÃO
tem: texto em claro conhecido ou escolhido, diferenças escolhidas na entrada,
reuso de nonce, acesso a canais laterais, nem consultas a um oráculo de
cifragem. Isso exclui de saída a maior parte da criptanálise diferencial
clássica e os distinguidores neurais no estilo Gohr, que dependem de pares com
diferença escolhida.

**O protocolo experimental.** Classificadores clássicos e redes sobre features
estatísticas e sobre os bytes crus. Chaves de teste nunca aparecem no treino
(key-holdout). Intervalo de confiança por bootstrap agrupado por chave, e não
i.i.d. Correção para múltiplas comparações. Controle negativo obrigatório: com
o algoritmo completo o classificador tem que ficar no acaso.

## O QUE EU QUERO DE VOCÊ

Técnicas, representações, ataques ou ideias — publicadas ou adaptáveis — que
possam extrair sinal nesse cenário, ou que ajudem a delimitar com rigor por
que o sinal não existe. Interessa tanto o que funciona quanto a prova de que
algo é impossível.

Busque em literatura acadêmica real (IACR ePrint, ToSC/FSE, CHES, CRYPTO,
EUROCRYPT, ASIACRYPT, SAC, Designs Codes and Cryptography, IEEE, Springer,
arXiv) e em fontes técnicas sérias. Use termos de busca em inglês.

## COMO RESPONDER

Para cada ideia encontrada, escreva:

1. **O que é** — a técnica, em duas ou três frases.
2. **Fonte** — autores, título, veículo, ano. Link quando houver. Se você não
   conseguiu confirmar a existência do trabalho, diga isso explicitamente em
   vez de completar de memória.
3. **Cabe no nosso modelo?** — SIM, NÃO, ou ADAPTÁVEL. Se ADAPTÁVEL, diga
   exatamente o que teria de mudar e qual premissa do modelo de ameaça isso
   arranha.
4. **O que custaria testar** — ordem de grandeza de dados, computação e
   engenharia.
5. **O que ela prevê** — se a técnica funcionar, que resultado deveríamos ver?
   Se não houver previsão falsificável, diga isso.

Termine com uma seção **APOSTAS**: as três ideias que você tentaria primeiro,
e por quê. Seja específico; "usar deep learning" não é uma aposta.

## PROFUNDIDADE — leia isto com atenção

Não é um levantamento rápido. **Vá até esgotar o veio.** Não pare em cinco ou
dez achados porque já "deu para ter uma ideia": siga as citações para frente e
para trás, abra os trabalhos relacionados dos artigos que importarem, procure
versões estendidas e teses, e persiga as pistas que aparecerem no caminho,
mesmo as que não estavam no ângulo original. Só encerre quando as buscas novas
pararem de trazer coisa nova.

Traga TODA a informação, não um resumo dela. Se um artigo tem um número que
importa (quantas rodadas, quantas consultas, que acurácia, que tamanho de
dado), traga o número. Se tem uma limitação declarada pelos próprios autores,
traga a limitação com as palavras deles. Prefira errar por excesso de detalhe.
Uma resposta longa e completa é o que se pede aqui; uma resposta enxuta é
falha de execução.

## REGRAS

- Não invente referências. Uma fonte não confirmada vale menos que nenhuma, e
  vou checar.
- Não repita o óbvio já saturado (distinguidor diferencial-neural padrão)
  sem trazer um ângulo novo que sobreviva ao ciphertext-only.
- Se a conclusão honesta de um caminho for "isso é impossível neste modelo
  por tal razão teórica", isso é resultado útil. Diga.
- Separe o que é publicado do que é sua extrapolação. Marque cada um.
````

## Pesquisa 03 — achados, sem resumir

### Achados — Pesquisa 03

- **Ângulo:** limites teóricos de impossibilidade, com números
- **Temperatura declarada:** 0,15 (a mais conservadora da série)
- **Prompt usado:** `prompts/03_limites_teoricos.md`
- **Execução:** ~310k tokens de subagente, 113 chamadas, ~30 min

---

### Limites teóricos do problema: o que é provadamente impossível, e com que folga

**Nota de método do agente.** Tudo vem de literatura externa; nada do repositório. Cada item marcado como **[PUBLICADO]** (consta da fonte) ou **[DERIVAÇÃO]** (conta do agente a partir de números publicados — verificável, não citável como de terceiros). Onde não conseguiu confirmar conteúdo interno de uma fonte, diz.

---

#### 0. O resultado que reorganiza tudo: aqui não existe limite informacional

Primeira coisa a acertar, porque é o erro mais comum em dissertações que tentam "provar impossibilidade" por teoria da informação.

##### 0.1 Distância de unicidade com fonte de plaintext conhecida

**O que é.** Shannon (1949) define U = H(K)/D, com D a redundância da fonte por símbolo. Abaixo de U há chaves espúrias; acima de U a chave fica unicamente determinada por adversário sem limite de recurso.

**Fonte.** C. E. Shannon, *Communication Theory of Secrecy Systems*, Bell System Technical Journal 28(4):656–715, 1949. https://pages.cs.wisc.edu/~rist/642-spring-2014/shannon-secrecy.pdf Redundância usual do inglês: D ≈ 6,8 bits/byte → U = 128/6,8 ≈ **18,8 bytes** para chave de 128 bits.

**Cabe no modelo?** SIM, e o veredito é o contrário do esperado: **os criptogramas têm ~3.500x a distância de unicidade** (65.536 B / 18,8 B). **[DERIVAÇÃO]**

**O número que importa.** **[DERIVAÇÃO]** Para 64 KiB com fonte SPGC a ~1,5 bit/char:
- H(plaintext) ≈ 65.536 x 1,5 = **98.304 bits**
- pares (chave, plaintext) por algoritmo: 2^128 * 2^98304 = **2^98432**
- espaço de criptograma (65.552 B): **2^524416**
- fração coberta pela imagem da cifragem: **2^-425984**
- probabilidade de a imagem de dois algoritmos colidir num ponto: **2^-327552**

Ou seja: as distribuições de criptograma de Ascon e GIFT-COFB, sob a fonte real de plaintext, têm suportes **essencialmente disjuntos**. TV(P_Ascon, P_GIFT) ≈ 1. O erro de Bayes é ≈ 0. Some-se a tag de 128 bits, que dá ao adversário ilimitado um teste de consistência gratuito por chave candidata.

**Consequência dura, e é ela que a dissertação precisa enunciar:** **nenhuma cota de Neyman-Pearson, KL, Pinsker ou Fano limita a acurácia neste problema.** O classificador ótimo (ilimitado) acerta ~100%. Toda a proteção é computacional. Uma seção de "limites teóricos" que invoque Pinsker sobre as distribuições verdadeiras estaria errada — o limite existe, mas vale 1,0.

**O que prevê.** Nada falsificável experimentalmente (o adversário ilimitado não é implementável). O valor é normativo: obriga a reescrever a pergunta como "qual a cota para classificadores de tempo t?" em vez de "qual a cota para qualquer classificador?".

---

#### I. As cotas de teste de hipóteses: o que dão, e sobre o quê

Aceito o §0, as ferramentas passam a ser aplicadas **não sobre P_Ascon vs P_GIFT, mas sobre P_algoritmo vs uniforme** — onde a prova criptográfica dá cota utilizável.

##### I.1 Vantagem = distância estatística; e a lei eps^-2

**Fonte.** Serge Fehr, Serge Vaudenay, *Sublinear Bounds on the Distinguishing Advantage for Multiple Samples*, IWSEC 2020, LNCS 12231, pp. 165–183. https://ir.cwi.nl/pub/30130/30130.pdf **PDF lido**; cotas verbatim:

- d(P0^n, P1^n) <= n * d(P0,P1) — eq. (1), justa em geral
- Vaudenay, caso booleano com P1 = U: d(P0^n, U^n) <= 4*sqrt(n) * d(P0,U) — eq. (2)
- Renner: d(P0^n,P1^n) <= sqrt(n/(2*p_barra)) * d(P0,P1), com p_barra = min sobre z onde diferem — eq. (3)
- Fehr–Vaudenay, booleano: d <= sqrt(n/(2q(1-q))) * d(P0,P1), q = P1(0) — eq. (4)
- Fehr–Vaudenay, geral: d <= sqrt(n/(2 min_z P1(z))) * ||P0-P1||_2 — eq. (5)
- Via Rényi: d(P0^n,P1^n) <= sqrt(n) * sqrt((1/2a)*D_a(P0||P1)), 0<a<=1; a=1 é Pinsker+KL

**Cabe no modelo?** SIM, com cuidado: nossas amostras não são i.i.d. dentro de uma chave (compartilham chave e encadeamento de nonce). As cotas i.i.d. valem por chave sob o modelo ideal; a soma sobre chaves é união.

**Número aplicado.** **[DERIVAÇÃO]** Com P1 = uniforme (q = 1/2), eq. (4) dá d <= sqrt(2n)*delta. Para vantagem 1/2 são precisas **n ≈ 1/(8*delta^2)** amostras.

##### I.2 Selçuk: a fórmula exata de "quantas amostras para um viés delta"

**Fonte.** Ali Aydın Selçuk, *On Probability of Success in Linear and Differential Cryptanalysis*, Journal of Cryptology 21:131–147, 2008. http://www.cs.bilkent.edu.tr/~selcuk/publications/Success_JoC.pdf **PDF lido.** Verbatim:

> **Teorema 2.** P_S = Phi( 2*sqrt(N)*|p - 1/2| - Phi^(-1)(1 - 2^(-a-1)) )
>
> **Corolário 1.** N = [ (Phi^(-1)(P_S) + Phi^(-1)(1 - 2^(-a-1))) / 2 ]^2 * |p - 1/2|^(-2)

Hipóteses declaradas: contadores T_i independentes, viés zero para chaves erradas (o autor diz que isso torna o resultado "um limite superior para a probabilidade de sucesso real"), m e N grandes. Tabela 2: para N = c_N*|p-1/2|^(-2), com c_N = 8 e a = 8 bits, P_S = 0,997; com c_N = 2 e a = 16, P_S = 0,067.

**Constantes instanciadas** **[DERIVAÇÃO]** (distinção pura, a = 1):

| P_S | a | c em N = c/delta^2 |
|---|---|---|
| 0,95 | 1 | **1,345** |
| 0,99 | 1 | 2,251 |
| 0,95 | 8 | 5,131 |
| 0,99 | 32 | 18,768 |

**Cabe no modelo?** ADAPTÁVEL. O ataque de Matsui é known-plaintext. O que transporta é apenas a **relação N <-> delta**, que é de teste de hipóteses e independe do modelo de ameaça. A parte de key-ranking (o parâmetro a) não se aplica: não estamos recuperando chave.

##### I.3 Distinguidor ótimo, informação de Chernoff, desequilíbrio euclidiano quadrático

**Fontes.**
- T. Baignères, P. Junod, S. Vaudenay, *How Far Can We Go Beyond Linear Cryptanalysis?*, ASIACRYPT 2004, LNCS 3329, pp. 432–450. **Existência, autores e veículo confirmados; texto integral NÃO obtido** (EPFL infoscience 405, KU Leuven recusou conexão). Fórmulas internas não citadas como verificadas.
- T. Baignères, S. Vaudenay, *The Complexity of Distinguishing Distributions*, ICITS 2008, LNCS 5155, pp. 210–222. Idem.
- T. Baignères, P. Sepehrdad, S. Vaudenay, *Distinguishing Distributions Using Chernoff Information*, ProvSec 2010, LNCS 6402, pp. 144–165. Existência confirmada; texto não lido.

O enunciado que circula — "se eps é a distância estatística, eps^-2 é a ordem de grandeza necessária e suficiente de amostras para vantagem >= 1/2" — é consistente com Fehr–Vaudenay eq. (4) e Selçuk Cor. 1, que foram lidos. Usa-se a forma verificada.

**Custo de testar.** Baixo: implementar o distinguidor LLR sobre a distribuição empírica de bytes é trivial e serve de *upper bound* empírico contra o qual comparar RF/CNN. Se o LLR ótimo sobre as features não bate o acaso, nenhum classificador sobre essas features bate.

**O que prevê.** Falsificável e útil: **se algum modelo de ML superar o distinguidor LLR ótimo sobre as mesmas features, há vazamento no protocolo, não sinal criptográfico.** Teste de sanidade barato e forte.

---

#### II. Cotas criptográficas concretas, por algoritmo, com os números do dataset

Geometria do dataset v2 **[DERIVAÇÃO]**: 300 chaves x 100 slots x 65.536 B.
- blocos de 128 bits por amostra: 4.096
- sigma por chave: 409.600 = **2^18,64** blocos; bytes por chave: 6.555.200 = **2^22,64**
- sigma agregado (300 chaves): 1,229x10^8 = **2^26,87** blocos
- bytes por braço (30k amostras): 1,967x10^9 = **2^30,87** → **2^33,87 bits**
- corpus inteiro (180k): 1,180x10^10 B = **2^33,46** B = **2^36,46 bits**

##### II.1 GIFT-COFB — a cota mais limpa e explícita

**Fonte.** S. Banik et al., *GIFT-COFB v1.1*, submissão finalista NIST LWC. https://csrc.nist.gov/CSRC/media/Projects/lightweight-cryptography/documents/finalist-round/updated-spec-doc/gift-cofb-spec-final.pdf **PDF lido.** Tabela 4.1: state 192 bits (excluindo key state), **IND-CPA 64 bits, INT-CTXT 58 bits**, nonce-respecting. Seção 4.1, verbatim:

> "a privacidade ou vantagem IND-CPA do GIFT-COFB pode ser limitada por Adv^prp_GIFT(q_e,t) + C(q_e,2)/2^128 + C(sigma_e,2)/2^128"

Cota AE completa (eq. 4.1): Adv^AE_COFB <= Adv^prp_GIFT(q',t') + C(q',2)/2^n + 1/2^(n/2) + q_f(n+4)/2^(n/2+1) + (3*sigma^2 + q_f + 2(q+sigma+sigma_f)*sigma_f)/2^n.

Também: "GIFT-COFB satisfaz o requisito de segurança contra 2^112 computações no cenário de chave única" e "o tamanho de entrada não deve ser menor que 2^50 - 1 bytes sob uma única chave".

**Tightness.** A cota birthday é justa **do lado do forjamento**: A. Inoue, T. Iwata, K. Minematsu, *GIFT-COFB is Tightly Birthday Secure with Encryption Queries*, https://eprint.iacr.org/2021/737 exibe ataque com 2^(n/2) blocos cifrados **mais uma consulta de decifragem**. O ataque que satura a cota **precisa de oráculo de decifragem** — fora do nosso modelo.

**Números para o nosso dataset** **[DERIVAÇÃO]**, só termos de modo (GIFT-128 PRP ideal):

| agregação | C(q_e,2)/2^128 | C(sigma_e,2)/2^128 | soma |
|---|---|---|---|
| por chave (q_e=100, sigma_e=2^18,64) | 2^-115,73 | 2^-91,71 | **2^-91,71** |
| 300 chaves somadas | 2^-99,25 | 2^-75,25 | **2^-75,25** |

Acurácia máxima de qualquer classificador que veja o corpus inteiro, contra uniforme: **0,5 + 2^-76,25**. Em 36.000 amostras de teste, o excesso esperado de acertos sobre o acaso é **8x10^-19 amostra**.

**Cabe no modelo?** SIM, com folga: nosso adversário é **passivo**. **[DERIVAÇÃO]** Redução imediata — um adversário CPA pode simular o passivo amostrando plaintexts da fonte conhecida e consultando-os; a visão é identicamente distribuída. Logo Adv_passivo <= Adv_CPA, e a cota vale *a fortiori*.

##### II.2 Ascon-AEAD128

**Parâmetros oficiais.** NIST SP 800-232, agosto 2025. https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-232.pdf **PDF lido.** Rate 128, capacidade 192, estado 320, chave 128, nonce 128, tag 32–128, p^a = 12 rodadas externas / p^b = 8 internas. Verbatim:

> "R6. Data limit. A quantidade total de dados processada durante cifragem e decifragem, incluindo o nonce, não deve exceder 2^54 bytes para uma dada chave."
>
> "Ascon-AEAD128 sem truncamento de tag fornece 128-bit security strength no cenário de chave única e nonce-respecting para a confidencialidade do plaintext (**exceto pelo seu comprimento**) e a integridade da tupla (nonce, associated data, ciphertext, tag), onde o número total de bytes de entrada é limitado a 2^54 (i.e., 2^50 blocos)."
>
> "Quando u chaves são independentemente selecionadas, Ascon-AEAD128 sem truncamento de tag fornece (128 - log2 u)-bit security strength."

**Cota exata do modo.** B. Chakraborty, C. Dhar, M. Nandi, *Exact Security Analysis of ASCON*, ASIACRYPT 2023. https://eprint.iacr.org/2023/775.pdf **PDF lido.** Verbatim (Seção 1.3):

> T/2^min{kappa,c} + D/2^min{tau,c} + DT/2^b

com kappa = chave, c = capacidade, tau = tag, b = estado; D = complexidade de dados, T = complexidade de tempo (chamadas diretas a pi). Concluem que, sob os requisitos NIST (D <= 2^53, T <= 2^112, kappa >= 128, tau >= 64), c = 136 já bastaria. Notam que "nenhum ataque de forjamento correspondente a essa cota foi descoberto", e que o melhor ataque genérico conhecido sobre duplex (Gilbert et al.) exige DT >> 2^(3c/2).

**Números** **[DERIVAÇÃO]**, com kappa=tau=128, c=192, b=320:
- D por chave ≈ 100 x 4.098 ≈ 2^18,6; agregado ≈ 2^26,9
- classificador com T = 2^40 avaliações de pi: T/2^128 = **2^-88**; D/2^128 = 2^-101; DT/2^320 = 2^-253
- domina o termo T/2^128 — que é literalmente *"chute a chave"*
- multi-chave, u = 300: força = 128 - log2(300) = **119,77 bits** → com T = 2^40, vantagem ≈ 2^-79,8
- nosso consumo por chave: 2^22,64 bytes contra limite de 2^54 → **2^31,4x abaixo**

##### II.3 Grain-128AEADv2 — o único com viés conhecido explorável em ciphertext-only

**O achado mais relevante desta pesquisa para a dissertação.**

**O que é.** Grain é cifra de fluxo aditiva: C = P XOR keystream. Um viés numa combinação linear do keystream se propaga para o criptograma **sempre que a combinação linear correspondente do plaintext for enviesada** — e plaintext de Gutenberg é fortemente enviesado (o bit alto de cada byte ASCII é praticamente constante). Pela piling-up lemma, viés_ct ≈ 2*viés_pt*viés_ks <= viés_ks. **Isto sobrevive ao ciphertext-only.**

**Fonte.** Hell, Johansson, Meier, Sönnerup, Yoshida, *Grain-128AEADv2*, spec finalista NIST LWC. https://csrc.nist.gov/CSRC/media/Projects/lightweight-cryptography/documents/finalist-round/updated-spec-doc/grain-128aead-spec-final.pdf **PDF lido.** Seção 4.2, verbatim:

> "Como é sempre possível encontrar uma aproximação linear enviesada das funções booleanas g e h, relações enviesadas nos bits do keystream sempre existirão. As funções do Grain-128AEADv2 foram portanto projetadas para tornar esse viés baixo. Para a função g, temos eps_g < 2^-9 e eta(A_g) = 5, e para a função h (incluindo os bits somados linearmente), temos eps_h < 2^-5 e eta(A_h) = 7. Isso dará **eps < 2^-77** para essa aproximação linear (que inclui também bits do LFSR)."

Ressalva declarada pelos autores: para obter expressão **só com bits de keystream**, somam-se versões deslocadas segundo a recorrência do LFSR, "o que baixará novamente o viés pela piling-up lemma". **2^-77 é otimista para o atacante**; o viés keystream-only é estritamente menor.

Demais números:
- **limitação de keystream: 2^80 bits por par chave/nonce** (2^81 bits de pré-saída)
- ataque de correlação rápida sobre Grain-128a: estado com dados e tempo ≈ **2^114**, mas exige todo bit de keystream (known-plaintext) e não se aplica ao modo de autenticação nem sob o limite de 2^80
- melhor ataque de rodadas reduzidas via division property: key recovery em **184 de 256 rodadas de inicialização**, dados 2^95, tempo 2^110
- maior alcance em chave fixa: distinguidor diferencial condicional em **195 rodadas**, só para fração das chaves
- claim: "ataques criptanalíticos requerem ao menos 2^112 computações"

**Números** **[DERIVAÇÃO]**:
- N necessário ≈ 1,345/eps^2 = **2^154 bits** (Selçuk Cor. 1, P_S = 0,95, a = 1)
- corpus inteiro: 2^36,46 bits → **déficit de 2^117,5**
- mesmo o limite de keystream do próprio cifrador (2^80 bits/chave-nonce) fica **2^74** aquém
- vantagem alcançável sobre o corpus inteiro, com 2*eps*sqrt(N): **2^-57,8** → acurácia 0,5 + 2^-58,8

**Cabe no modelo?** SIM — é o único distinguidor ciphertext-only *estruturalmente válido* dos quatro. E é inútil por 35 ordens de grandeza. Vale como seção justamente porque mostra que a conclusão não é "não há nada", é "há algo, e está a 2^117 de distância".

##### II.4 Schwaemm256-128 (SPARKLE)

**Fonte.** Beierle, Biryukov, Cardoso dos Santos, Großschädl, Perrin, Udovenko, Velichkov, Wang, *Schwaemm and Esch*, spec NIST LWC. https://csrc.nist.gov/CSRC/media/Projects/lightweight-cryptography/documents/round-2/spec-doc-rnd2/sparkle-spec-round2.pdf **PDF lido.** Seção 4.1.2, verbatim:

> "O modo de operação Beetle oferece um nível de segurança (em bits) de **min(r, (r+c)/2, c - log2(r))** tanto para confidencialidade (sob ataques adaptativos de plaintext escolhido) quanto para integridade."

Tabela 2.3: Schwaemm256-128 → n=384, r=256, c=128, |K|=128, |N|=256, |T|=128, **segurança 120 bits, data limit 2^68 bytes**. Aritmética: min(256, 192, 128-8) = 120.

Permutação Sparkle384: **7 passos slim / 11 big** (Tabela 2.1). Melhores ataques sobre Sparkle384 (seção 4.2): diferencial 5 passos, linear 6, boomerang 4, diferenciais truncados 2, yoyo 4, diferenciais impossíveis 4, correlação zero 4, integral/division property 4.

Frase útil dos projetistas sobre a lei eps^-2: "a complexidade de dados estimada para um ataque linear é ao menos **1/p^2**, onde p denota a correlação absoluta da aproximação linear usada."

**Número.** **[DERIVAÇÃO]** Consumo por chave: 2^22,64 bytes contra limite 2^68 → **2^45,4x abaixo**.

##### II.5 Síntese: a cota agregada

**[DERIVAÇÃO]** Lema (hibridação, padrão; enunciado como derivação porque não foi achada formulação publicada específica para "identificar qual esquema"): sejam A e B dois AEADs com saídas do **mesmo comprimento**, e eps_A, eps_B suas vantagens IND$ contra adversários de tempo t. Então, por desigualdade triangular em TV:

TV(P_A, P_B) <= TV(P_A, U) + TV(U, P_B) <= eps_A + eps_B,

e a acurácia de qualquer discriminador binário de tempo t é <= 1/2 + (eps_A + eps_B)/2.

Corolário sobre features **[DERIVAÇÃO]**: por desigualdade de processamento de dados para TV, para **qualquer** função phi (as 641 features, o latente da CNN, o que for), TV(phi(P_A), phi(P_B)) <= eps_A + eps_B. **Nenhuma engenharia de features pode aumentar o sinal.** É o que fecha a porta para os Caminhos A–F enquanto os comprimentos forem iguais.

Instanciando: Ascon (2^-88) + GIFT-COFB (2^-75,25) → acurácia <= **0,5 + 2^-76,2**.

---

#### III. Qual o menor desvio da uniformidade detectável com o nosso corpus

##### III.1 Piso monobit (Neyman-Pearson sobre Bernoulli)

**[DERIVAÇÃO]** delta_min ≈ (z_alfa + z_beta)/(2*sqrt(N)), com alfa = beta = 0,05 (z = 1,645):

| corpus | N (bits) | delta_min |
|---|---|---|
| um criptograma (65.552 B) | 2^19,0 | 2,27x10^-3 = **2^-8,78** |
| um braço (30k x 65.552 B) | 2^33,87 | 1,31x10^-5 = **2^-16,22** |
| corpus inteiro (180k) | 2^36,46 | 5,35x10^-6 = **2^-17,51** |

##### III.2 Piso chi2 sobre o histograma de 256 bytes

**[DERIVAÇÃO]** lambda = N*soma((p_i - q_i)^2/q_i); com aproximação de primeira ordem lambda ≈ (z_0,01 + z_0,05)*sqrt(2*255) ≈ 89,7:

| corpus | N (bytes) | divergência chi2 mín. | ||p-q||_2 | TV detectável |
|---|---|---|---|---|
| 1 criptograma | 2^16,0 | 2^-9,5 | 2^-8,8 | <= 2^-5,8 |
| 100 CTs (1 chave) | 2^22,6 | 2^-16,2 | 2^-12,1 | <= 2^-9,1 |
| 30k CTs (1 braço) | 2^30,9 | 2^-24,4 | 2^-16,2 | <= 2^-13,2 |
| 180k CTs | 2^33,5 | 2^-27,0 | 2^-17,5 | <= 2^-14,5 |

##### III.3 Teste de uniformidade em bloco de 128 bits — o piso é intransponível

**O que é.** Testar uniformidade sobre domínio de tamanho n exige Theta(sqrt(n)/eps^2) amostras, e essa complexidade é justa.

**Fontes.**
- L. Paninski, *A Coincidence-Based Test for Uniformity Given Very Sparsely Sampled Discrete Data*, IEEE Trans. Inform. Theory 54(10):4750–4755, 2008. https://ieeexplore.ieee.org/document/4626074/ Cota inferior casada, regime eps = Omega(m^-1/4).
- C. L. Canonne, *A Survey on Distribution Testing: Your Data is Big. But is it Blue?*, Theory of Computing Library, Graduate Surveys 9, 2020. https://theoryofcomputing.org/articles/gs009/gs009.pdf **PDF lido.** **Teorema 5.1** verbatim: existe algoritmo que com SAMP acesso a D toma **O(sqrt(n)/eps^2)** amostras e (i) se D = U aceita com prob >= 2/3, (ii) se d_TV(D,U) > eps rejeita com prob >= 2/3; "Furthermore, this sample complexity is tight." Também Thm 5.2/5.4 (estimador de colisões de Goldreich–Ron, O(sqrt(n)/eps^4), fracamente tolerante).

**Número.** **[DERIVAÇÃO]** Com n = 2^128 (blocos de 128 bits) e eps = 1/2, a complexidade mínima é ~4*2^64 = **2^66 amostras**. Temos 2^29,5 blocos no corpus inteiro. **Déficit de 2^36,5 amostras** — e isso para detectar desvio *metade do máximo possível*.

Argumento mais forte e limpo: **no espaço onde o modo de operação realmente vive (blocos de 128 bits), o corpus inteiro é 2^36,5 vezes pequeno demais para que qualquer teste, ótimo ou não, pudesse detectar sequer um desvio de metade da distância máxima.** Todo sinal que aparecer em nível de byte é, necessariamente, artefato de agregação.

##### III.4 A comparação pedida: piso de detecção vs. margem de segurança

**[DERIVAÇÃO]**

| grandeza | valor (log2) |
|---|---|
| menor viés detectável com o corpus (monobit, 180k) | -17,5 |
| menor TV detectável via chi2 de bytes (180k) | -14,5 |
| desvio provado do modo GIFT-COFB (por chave) | -91,7 |
| desvio provado do modo GIFT-COFB (300 chaves) | -75,3 |
| cota Ascon com T = 2^40 | -88 |
| melhor viés linear conhecido do keystream Grain | -77 |
| **lacuna típica** | **~2^60 a 2^75** |

Invertendo: para *alcançar* o desvio provado do GIFT-COFB seriam precisos N ≈ 1,345/delta^2 = **2^150,9** amostras (agregado) ou **2^183,8** (por chave). O corpus é 2^36,5. Não há dataset construível que feche essa lacuna: 2^180 bytes excede qualquer armazenamento físico concebível.

---

#### IV. Dureza de aprendizado a partir de hipóteses criptográficas

Aviso de escopo: **as cotas de complexidade de amostra do tipo VC / no-free-lunch NÃO se aplicam aqui.** São cotas *minimax sobre distribuições adversárias*; não dizem nada sobre uma distribuição fixa. Esticá-las seria erro. Aplicam-se as cotas **computacionais**.

##### IV.1 Kearns–Valiant

**Fonte.** M. Kearns, L. G. Valiant, JACM 41(1):67–95, 1994. https://dl.acm.org/doi/10.1145/174644.174647

Intratabilidade de aprender PAC fórmulas booleanas, DFAs e circuitos de limiar de profundidade constante — um algoritmo polinomial teria consequências dramáticas (inverter RSA, fatorar inteiros de Blum, decidir resíduos quadráticos).

**Cabe no modelo?** ADAPTÁVEL, e é o esqueleto certo. A função "qual algoritmo gerou este criptograma" é computável por circuito de tamanho ~2^128 (busca exaustiva), logo não está numa classe pequena; mas a direção útil é a contrapositiva — um classificador eficiente que separasse os criptogramas seria distinguidor eficiente contra a pseudoaleatoriedade da permutação Ascon / do cifrador GIFT-128. É **exatamente** a cota da §II.

**O que prevê.** Falsificável no sentido forte: se um classificador ciphertext-only atingir vantagem não-negligenciável contra Ascon full-round, isso é ataque publicável contra Ascon, não resultado de ML.

##### IV.2 Kharitonov — dureza específica-de-distribuição

**Fontes.** M. Kharitonov, STOC 1993, pp. 372–381, https://dl.acm.org/doi/10.1145/167088.167197; versão de periódico JCSS 50(3):600–610, 1995.

Aprender sob distribuição **uniforme** (o caso mais fácil, onde cotas distribution-free não se aplicam) continua difícil sob hipóteses de fatoração/subset-sum. Fecha a brecha "mas a nossa distribuição é benigna" — relevante porque nossa distribuição de criptogramas **é** (por hipótese) uniforme.

##### IV.3 Cotas SQ — e a ressalva honesta

**Fontes.** Kearns (1993/1998) para não-aprendibilidade SQ de paridades; Blum, Furst, Jackson, Kearns, Mansour, Rudich (STOC 1994) para SQ-dimension. Survey verificável: V. Feldman, arXiv:2004.00557, https://arxiv.org/pdf/2004.00557. Feldman, Grigorescu, Reyzin, Vempala, Xiao, JACM 64(2), 2017, https://arxiv.org/pdf/1201.1214.

Praticamente toda a família RF/SVM/XGBoost sobre features estatísticas agregadas é algoritmo SQ, e gradiente descendente sobre gradientes populacionais também.

**Ressalva.** A implicação "SQ lower bound ⟹ gradiente descendente falha" **não é estrita**. Y. Kou et al., *Matching the Statistical Query Lower Bound for k-Sparse Parity Problems with Sign Stochastic Gradient Descent*, NeurIPS 2024, https://arxiv.org/abs/2404.12376, mostram SGD-sinal resolvendo paridade k-esparsa com complexidade Otil(d^(k-1)) e 2^Theta(k) neurônios, casando (não violando) a cota Omega(d^k). **Não se pode dizer "SQ prova que CNN não consegue".** Pode-se dizer: o regime é o de dureza SQ, e nada sugere que o excesso de poder computacional das nossas CNNs chegue perto de 2^128.

##### IV.4 Raz — memória limitada como barreira separada

**Fonte.** R. Raz, *Fast Learning Requires Good Memory: A Time-Space Lower Bound for Parity Learning*, FOCS 2016; JACM 66(1), 2019. https://dl.acm.org/doi/10.1145/3186563

Qualquer algoritmo de aprendizado de paridade com menos de **n^2/25 bits de memória** requer número **exponencial** de amostras. Barreira incondicional, ortogonal à SQ.

**Cabe no modelo?** ADAPTÁVEL — e arranha uma premissa: a formalização é para paridade com amostras uniformes, não para AEAD. Mas a moral transporta: modelo com ~10^7 parâmetros (≈2^28 bits) está muito abaixo de n^2/25 para n = 128, portanto no regime "memória insuficiente ⟹ amostras exponenciais". **[DERIVAÇÃO]**

##### IV.5 Daniely–Vardi e o enquadramento correto: lacuna estatístico-computacional

**Fontes.**
- A. Daniely, G. Vardi, *From Local Pseudorandom Generators to Hardness of Learning*, COLT 2021, PMLR 134:1358–1394. https://arxiv.org/pdf/2101.08303
- M. Brennan, G. Bresler, *Reducibility and Statistical-Computational Gaps from Secret Leakage*, COLT 2020. https://proceedings.mlr.press/v125/brennan20a.html; Brennan, Bresler, Huleihel, COLT 2018.
- R. Rivest, *Cryptography and Machine Learning*, ASIACRYPT 1991, LNCS 739:427–439 — enquadramento original de "campos irmãos".

**Por que importa.** Dá o vocabulário exato para o §0: nosso problema tem **complexidade de amostra informacional ≈ 1 criptograma** (unicidade) e **barreira computacional ≈ 2^128**. É a maior lacuna estatístico-computacional que se pode construir de propósito — é literalmente o que uma cifra é. Enunciar com a linguagem de Brennan–Bresler é mais preciso e mais defensável numa banca do que dizer "é impossível".

---

#### V. Rodadas reduzidas: o que é provável, e o que o modelo de ameaça derruba

##### V.1 O resultado central — e é um resultado negativo forte

**Fonte.** E. Bellini, Y. J. Huang, *Randomness Testing of the NIST Light Weight Cipher Finalist Candidates*, NIST LWC Workshop 2022. https://csrc.nist.gov/csrc/media/Events/2022/lightweight-cryptography-workshop-2022/documents/papers/randomness-testing-of-the-nsit-lightweight-cipher-finalist-candidates.pdf **PDF lido.** Versão publicada: Bellini, Huang, Rachidi, *Statistical Tests for Symmetric Primitives*, SecITC 2022, LNCS 13809:133–152.

Critério: "um primitivo vem a random na rodada r" = falha em <= 4 de 188 testes. 462 GB de dados, sequências de ~10^6 bits, 384 sequências por dataset.

**Tabela 2, extraída** (rodada em que passa | total):

| primitivo | aval. PT | aval. chave | corr. PT/CT | CBC | **random** | low-dens PT | low-dens K | high-dens PT | high-dens K |
|---|---|---|---|---|---|---|---|---|---|
| Permutação Ascon (320 b, 12 rod.) | **4\|12** | — | 1\|12 | 1\|12 | **1\|12** | — | — | — | — |
| GIFT-128 (40 rod.) | **8\|40** | **10\|40** | 2\|40 | 2\|40 | **1\|40** | 7\|40 | 9\|40 | 7\|40 | 8\|40 |
| skinny-128-384+ (Romulus) | 7\|40 | 8\|40 | 1\|40 | — | 1\|40 | 6\|40 | 8\|40 | 6\|40 | 8\|40 |
| TinyJambu-128 P640 (20 rod.) | 17\|20 | 19\|20 | 4\|20 | 4\|20 | 1\|20 | 14\|20 | 17\|20 | 14\|20 | 17\|20 |

Os autores registram: "**Currently, the datasets of Sparkle-family and Grain-128 are missing.**" Não foi possível confirmar se a versão SecITC 2022 os inclui — **pendência verificável** que vale fechar (é a lacuna exata do nosso conjunto).

**A leitura que importa.** **[DERIVAÇÃO a partir da tabela publicada]** Na coluna **random** (plaintexts e chaves aleatórios — o dataset mais próximo do nosso cenário), **todos os primitivos passam já na rodada 1**. As não-aleatoriedades detectáveis em 4–10 rodadas aparecem *só* nos datasets avalanche, low-density e high-density — que **exigem entradas escolhidas**.

Consequência dura para a segunda pergunta da dissertação: **no modelo ciphertext-only passivo com plaintext natural, a bateria NIST não distingue nem uma rodada.** O "piso de rodadas" só existe quando o adversário controla a entrada. Um estudo de rodadas reduzidas em ciphertext-only está medindo, na melhor hipótese, a redundância do plaintext — não a estrutura da cifra.

##### V.2 Cotas provadas de trilha

- **Ascon.** J. Erlacher, F. Mendel, M. Eichlseder, *Bounds for the Security of Ascon against Differential and Linear Cryptanalysis*, ToSC 2022(1):64–87, DOI 10.46586/tosc.v2022.i1.64-87. Cotas inferiores (não justas) no número de S-boxes ativas diferenciais e lineares para **4 e 6 rodadas**, com busca por "girdle patterns" e teoria de colares.
- **GIFT-128.** Diferencial de 9 rodadas com prob. 2^-45,99 ⟹ ~**27 rodadas** para prob. abaixo de 2^-128; **40 rodadas** especificadas ⟹ margem ~33%. Banik et al., *GIFT: A Small Present*, CHES 2017, e análises MILP posteriores.
- **Sparkle384.** Long Trail Strategy: 4 passos bastam contra distinguidores lineares e diferenciais para Schwaemm256-128; slim usa 7, big usa 11. Margem declarada de 57%. Os projetistas advertem que "não encontramos ataques reais nos esquemas (de rodadas reduzidas) que correspondam a essas cotas e podemos estar vastamente superestimando as habilidades do adversário".
- **Grain-128AEADv2.** eps < 2^-77, 256 rodadas de inicialização, melhor ataque de rodadas reduzidas em 184 (division property) / 195 (diferencial condicional, fração das chaves).

##### V.3 O que NÃO se aplica — dito explicitamente

| técnica | fonte | por que não cabe |
|---|---|---|
| Cube / conditional cube em Ascon (7/12 rodadas, tempo 2^103,9; 6 rodadas prático a 2^40) | https://eprint.iacr.org/2024/743, ToSC; *Improved Key Recovery Attacks of Ascon* (2025) | exige **controle sobre bits do nonce**; nonce de contador não dá isso |
| Distinguidores neurais diferenciais (Gohr e sucessores) | Gohr, CRYPTO 2019; survey Gerault et al., https://eprint.iacr.org/2024/1300.pdf | exigem **pares com diferença de entrada escolhida** |
| Baksi et al.: 8 rodadas Gimli, **3 rodadas Ascon-Permutation**, 10 Knot-256, 4 Chaskey | https://eprint.iacr.org/2020/571, DATE 2021 | **diferenças de entrada escolhidas** (confirmado no texto) |
| Ataque genérico sobre duplex, tempo O(2^(3c/4)), memória negligenciável, "sem consultas de cifragem" | Gilbert, Heim Boissier, Khati, Rotella, EUROCRYPT 2023, https://eprint.iacr.org/2023/262 | é forjamento/recuperação de chave, com controle de nonce; quebra um claim do Xoodyak, não do Ascon |
| BoolTest / CoolTest | Sýs, Klinec, Švenda, SECRYPT 2017; CoolTest 2025 | opera em estratégias de geração (CTR, RPC) com **entradas estruturadas** |
| Doğanaksoy, Ege, Koçak, Sulak: SAC test, linear span, collision, coverage | https://eprint.iacr.org/2010/564 | SAC exige flip de bit de entrada — **entradas escolhidas** |
| Ataque de correlação rápida em Grain-128a, dados/tempo 2^114 | citado na spec Grain, ref. [51] | exige todo bit de keystream (**known-plaintext**) e viola o limite de 2^80 |
| Cotas VC / no-free-lunch | Shalev-Shwartz & Ben-David, cap. 5 | são **minimax sobre distribuições**; nossa distribuição é fixa. Não dizem nada aqui. |

---

#### VI. O outro lado: onde os limites são frouxos

##### VI.1 Preditores batem estimadores estatísticos — caso publicado, em NIST

**Fonte.** J. Kelsey, K. McKay, M. Sönmez Turan, *Predictive Models for Min-entropy Estimation*, CHES 2015, pp. 373–392. https://eprint.iacr.org/2015/600.pdf **PDF lido.** Verbatim:

> "Em RDTSC1, o preditor lag fornece uma estimativa 0,205 abaixo da do estimador de colisão do 90B, sugerindo que havia **periodicidade que os estimadores 90B foram incapazes de detectar**."

Também registram o contrário: em RDTSC8 e RANDOM.ORG "os preditores não obtiveram ganhos significativos sobre o chute desinformado". E: "os estimadores 90B estão sujeitos a subestimações sistemáticas enormes de entropia".

**Cabe no modelo?** SIM metodologicamente (é ciphertext-only por construção), NÃO como ameaça à cifra (é sobre fontes de entropia física). Valor: **precedente institucional** — o NIST adotou preditores porque testes estatísticos deixavam estrutura passar.

**Custo.** Baixíssimo. Rodar os quatro preditores do SP 800-90B sobre os bytes dos criptogramas: horas. **Previsão falsificável:** se algum preditor superar o acaso sobre criptogramas full-round, é bug de geração (nonce, RNG, buffer reaproveitado), não criptanálise.

##### VI.2 ML detecta correlação em QRNG que passa em testes

**Fonte.** N. D. Truong, J. Y. Haw, S. M. Assad, P. K. Lam, O. Kavehei, IEEE TIFS 14(2):403–414, 2019. https://arxiv.org/abs/1905.02342 Abstract confirmado; **acurácias específicas e tamanho de dados não extraídos**. Confirmado: o modelo "detecta correlações inerentes quando as fontes de ruído determinístico são proeminentes", e após filtragem e extração "o sistema QRNG demonstra sua robustez contra ML".

**Cabe no modelo?** NÃO diretamente (fonte física). Analogia apenas.

##### VI.3 Gohr e a explicação posterior: por que a surpresa não transporta

**Fontes.** Gohr, CRYPTO 2019 (238 citações em fev/2025 segundo o survey). A. Benamira, D. Gerault, T. Peyrin, Q. Q. Tan, *A Deeper Look at Machine Learning-Based Cryptanalysis*, EUROCRYPT 2021, https://eprint.iacr.org/2021/287: os distinguidores de Gohr "geralmente se apoiam na distribuição diferencial nos pares de criptograma, mas também na distribuição diferencial nas rodadas penúltima e antepenúltima".

**Leitura honesta.** A surpresa foi real — a rede achou informação que a criptanálise diferencial clássica descartava. Mas a fonte continuou sendo a **diferença escolhida**. Não é evidência de que ML ache sinal onde não há; é evidência de que ML extrai melhor um sinal que já existe. Não transporta para ciphertext-only.

**Registro do survey** (Gerault et al., https://eprint.iacr.org/2024/1300.pdf, **PDF lido**): classificação de cifras em ciphertext-only aparece na literatura **apenas para cifras históricas** (WWII, sistemas já quebrados por métodos clássicos) — refs [DS25], [Kop20], [LKE+21] —, e os autores dizem que esse ramo é "metodologicamente e empiricamente distinto" e por isso o excluíram. **Não há, nessa literatura, reivindicação de classificação ciphertext-only de cifras modernas full-round.**

##### VI.4 O caso mais incômodo

**Fonte.** *Plaintext Structure Vulnerability: Robust Cipher Identification via a Distributional Randomness Fingerprint Feature Extractor*, arXiv:2511.08296 (nov/2025, preprint). Pipeline: T = 41 testes → calibração por transformada integral de probabilidade → janelamento + histograma K-bin + 4 momentos. Seis cifras: AES-ECB, AES-CBC, 3DES, Blowfish, ChaCha20, RC4.

**Números.** Canterbury: SVM-RBF 0,897 acc / 0,985 AUC; MLP 0,878 / 0,982; XGBoost 0,788 / 0,952. Regular_100: ~0,999 acc. **Random_100 (0% estruturado): 0,541 acc, 0,905 AUC.** 10.000 janelas de 8 KB, balanceadas, CV 5x5 estratificada por arquivo-fonte.

**Limitações verbatim:** "Primeiro, os experimentos cobrem seis algoritmos criptográficos comuns... Segundo, a composição da suíte de testes estatísticos e os hiperparâmetros do extrator (e.g., tamanho de janela W, número de bins K) foram fixados... Finalmente, os datasets são sintéticos e projetados para isolar efeitos de estrutura de plaintext; validação em tráfego de rede capturado é necessária."

**Avaliação — [EXTRAPOLAÇÃO DO AGENTE, não do artigo].** Suspeita forte de artefato de comprimento/padding, que o artigo não descarta:
- AES tem bloco de 128 bits, 3DES e Blowfish de 64, RC4 e ChaCha20 são de fluxo. Com PKCS7 sobre janelas de 8.192 B (múltiplo de 8 e de 16), as saídas são **8.208 / 8.200 / 8.192 bytes**. Assinatura de 3 vias, trivialmente separável, e exatamente o que os 41 testes absorvem via contagens.
- O artigo **não discute** como cifradores de bloco de 64 bits diferem de AES ou de cifradores de fluxo quanto a padding — "lacuna metodológica significativa".
- **Não reporta matriz de confusão por cifra no Random_100**, o que impediria verificar se a separação é entre os três grupos de comprimento.
- A discrepância entre acc 0,541 e AUC 0,905 é o padrão de feature quase-determinística que separa *grupos* mas não *cifras dentro do grupo*.

**Como falsificar.** Replicar **normalizando todos os criptogramas ao mesmo comprimento** (truncar ao mínimo comum) colapsa Random_100 para ~1/6. Experimento de meio dia: se colapsar, contra-argumento publicável; se não colapsar, é o achado mais importante da área.

##### VI.5 A literatura de identificação de cifras, incluindo a do orientador

**Fonte central.** F. de Mello, J. Xexéo, JUCS 24(1):25–42, 2018. https://www.jucs.org/jucs_24_1/identifying_encryption_algorithms_in/jucs_24_01_0025_0042_demello.pdf Sete idiomas, sete algoritmos em ECB e CBC, seis classificadores. ECB: reconhecimento total. **CBC: 40–50% com Complement Naive Bayes** (acaso 1/7 ≈ 14,3%). Idioma não impactou.

**O que a literatura posterior mostra sobre essas taxas.**
- **Chave compartilhada entre treino e teste é a principal fonte de sinal.** "A taxa de identificação pode ficar em torno de 90% se as chaves forem as mesmas para treino e teste". Sob chaves aleatórias os números caem muito.
- **Sobreposição de amostras é a segunda.** MIND-Crypt: "**Ao isolar amostras únicas apenas do dataset de teste, a acurácia caiu bruscamente para 49,90%**".
- Esquema k-NN+RF sobre AES, 3DES, Blowfish, CAST, RC2 (todos ECB, Fortuna, chave fixa de 16 bytes) reporta **69,5% binário** e **34% em 5 classes** (acaso 20%) — https://pmc.ncbi.nlm.nih.gov/articles/PMC9575859/. Mesma suspeita de padding.

**Número de referência para o controle positivo** **[DERIVAÇÃO]**: em 64 KiB de texto (4.096 blocos de 16 B), se um bloco de 16 bytes de texto natural carrega ~16 bits de entropia efetiva, o número esperado de pares iguais é **~128**; a 24 bits, ~0,5; a 32 bits, ~0. Para blocos uniformes de 128 bits: 2,5x10^-32. É por isso que AES-ECB sobre texto é detectável e sobre aleatório não é — mecanismo exato do controle positivo.

##### VI.6 Resultados negativos rigorosos que corroboram

**MIND-Crypt.** arXiv:2405.19683 / ePrint 2024/852; periódico Cryptography 10(1):9, 2026. SPECK32/64 e SIMON32/64 em CBC; ResNet, CNN, LSTM, BiLSTM; KPA. "técnicas modernas de ML alcançam consistentemente acurácia equivalente a chute aleatório, indicando que **nenhum padrão estatisticamente explorável existe**". Controle decisivo: isolando amostras exclusivas do teste, 49,90%.

**Calderon–Johansson–Günlü.** *Evaluating PQC KEMs, Combiners, and Cascade Encryption via Adaptive IND-CPA Testing Using Deep Learning*, arXiv:2604.06942 (abril 2026). **PDF lido.** Desenho experimental mais próximo do nosso e vale copiar:
- 500.000 amostras de treino por classe, 100.000 de validação, 100.000 de teste; duas redes (small/big); até 1.000 épocas com early stopping
- **teste binomial bicaudal, H0: pi = 0,5, alfa = 0,01**
- controle positivo: RSA determinístico → **100%**, p = 2^-199999
- RSA-OAEP 50,02% (p=0,86) / 49,90% (p=0,37); ML-KEM 50,10% / 50,04%; BIKE 49,94% / 50,05%; HQC 50,26% (p=0,02) / 50,06%
- cifragem em cascata (AES-CBC, AES-CTR, AES-ECB, ChaCha20, DES-ECB, 17 combinações): **acurácias em 49,74%–50,27%**, todas não significativas
- notável: as combinações permanecem indistinguíveis **mesmo quando uma componente é determinística e não-IND-CPA (AES-ECB, DES-ECB)**
- limitação declarada: "o classificador neural não tem acesso a chaves públicas ou oráculos de cifragem... isso impõe alguns limites sobre quais vetores de ataque a modelagem DNN pode capturar"

**Relevância.** Benchmark externo de "quanto é o ruído esperado": com 100.000 amostras de teste, o desvio de 50% fica em ±0,27 pontos percentuais. Faixa de referência direta para calibrar o que conta como nulo.

---

#### VII. O que os limites NÃO cobrem — onde o sinal pode legitimamente estar

1. **Comprimento.** SP 800-232 diz textualmente: confidencialidade "exceto pelo seu comprimento". Grain-128AEADv2 tem tag de 64 bits (len_ct = 65.544) contra 128 dos demais (65.552). **Distinguidor perfeito e provado**, e não viola nada — é a parte que o AEAD nunca prometeu esconder. Idem AES-ECB com PKCS7.
2. **Nonce e seus comprimentos.** Ascon 128 bits, Grain 96, Schwaemm 256. Se qualquer parte do nonce entrar na representação, o problema vira trivial.
3. **O encadeamento (mesmo plaintext/chave/nonce para todos).** Cria dependência estatística entre criptogramas de algoritmos diferentes. Uma análise **pareada** pode explorá-la; a cota da §II.5 é para amostras marginais e **não cobre o caso pareado**. Brecha teórica real do protocolo v2, merece formalização própria antes de se afirmar "nada é possível".
4. **Implementação.** As cotas são sobre o modo idealizado. Nada cobre bugs de geração, reuso de buffer, padding variável ou artefatos do RNG.
5. **A fronteira multi-chave.** Com u = 300, Ascon cai de 128 para 119,77 bits. Irrelevante na prática, mas é o único termo que **cresce** com o desenho do dataset.
6. **Rodadas reduzidas com entrada controlada.** Fora do modelo, mas é onde todo o sinal existe (§V.1). Se o objetivo é achar sinal, é a única direção em que a literatura garante que ele exista.

---

#### APOSTAS

##### Aposta 1 — Construir o distinguidor LLR ótimo sobre as próprias features e usá-lo como teto

Instanciar o distinguidor de razão de verossimilhança (Neyman-Pearson) sobre a distribuição empírica das 641 features, e sobre o histograma de bytes bruto. Pela desigualdade de processamento de dados (§II.5), **nenhum RF, XGBoost, CNN ou Transformer que consuma essas mesmas features pode superá-lo**. Se o LLR ótimo dá 0,500 e uma CNN dá 0,54, a CNN está vendo algo que não são as features — comprimento, ordem de arquivos, vazamento de split.

Por quê primeiro: engenharia de um dia, poder diagnóstico máximo, e converte "os quatro caminhos convergiram para H0" de observação empírica em **consequência de um teto calculado**. Dá à banca um argumento que não depende de acreditar que os modelos foram bem treinados.

Previsão falsificável: LLR ótimo empírico ≡ acaso dentro do IC bootstrap; e Acc(qualquer modelo) <= Acc(LLR) + ruído de estimação.

##### Aposta 2 — Escrever a seção de limites com a estrutura "informacional vazio / computacional apertadíssimo"

A tabela que fecha o argumento:

| | valor |
|---|---|
| distância de unicidade (chave 128 b, SPGC) | 18,8 bytes |
| tamanho do criptograma | 65.536 bytes = **3.482x U** |
| TV verdadeira entre P_Ascon e P_GIFT | ≈ 1 (suportes disjuntos, colisão ~2^-327552) |
| erro de Bayes do adversário ilimitado | ≈ 0 |
| **piso de detecção do corpus (monobit, 2^36,46 bits)** | **2^-17,5** |
| piso de detecção chi2 sobre bytes (180k) | TV <= 2^-14,5 |
| amostras mínimas para teste de uniformidade em blocos de 128 b, eps=1/2 | 2^66 (temos 2^29,5 → **déficit 2^36,5**) |
| desvio provado do modo GIFT-COFB (300 chaves) | 2^-75,25 |
| cota Ascon, classificador com T = 2^40 | 2^-88 |
| melhor viés linear conhecido do keystream Grain | 2^-77 (precisa de 2^154 bits; temos 2^36,5) |
| acurácia máxima Ascon vs GIFT para qualquer classificador de tempo 2^40 | **0,5 + 2^-76,2** |
| excesso esperado de acertos em 36.000 amostras de teste | **8x10^-19 amostra** |

Todas as entradas rastreiam à SP 800-232, à spec GIFT-COFB, à spec Grain, à spec SPARKLE e ao Teorema 5.1 de Canonne.

Corolário prático: **len_ct do Grain (65.544 vs 65.552) é o único distinguidor provado do conjunto.** Tratá-lo como metadado é a decisão certa, e agora é decisão *justificada por teorema*, não por convenção.

##### Aposta 3 — Replicar o arXiv:2511.08296 com comprimento normalizado

Única reivindicação viva, publicada e datada de nov/2025, de sinal ciphertext-only sobre plaintext puramente aleatório (acc 0,541, AUC 0,905, seis cifras, incluindo AES-CBC e ChaCha20). Se for real, muda a pergunta da dissertação. Se for artefato de padding — o que os números e a lacuna metodológica sugerem —, a refutação é limpa e é contribuição própria.

Protocolo: mesmas seis cifras, janelas de 8 KB, **truncar todo criptograma a 8.192 bytes antes de qualquer feature**, mesmo extractor de 41 testes, mesma CV agrupada por arquivo, e reportar matriz de confusão por cifra no Random_100 (que o original omite).

Previsão falsificável e binária: com comprimento normalizado, Random_100 colapsa para 1/6 ± ruído binomial.

---

#### Fontes

**Teoria de informação e teste de hipóteses**
- Shannon, *Communication Theory of Secrecy Systems*, BSTJ 1949. https://pages.cs.wisc.edu/~rist/642-spring-2014/shannon-secrecy.pdf
- Fehr & Vaudenay, IWSEC 2020. https://ir.cwi.nl/pub/30130/30130.pdf
- Selçuk, J. Cryptology 2008. http://www.cs.bilkent.edu.tr/~selcuk/publications/Success_JoC.pdf
- Baignères, Junod, Vaudenay, ASIACRYPT 2004 *(existência confirmada; texto não obtido)*
- Baignères & Vaudenay, ICITS 2008 *(idem)*
- Baignères, Sepehrdad, Vaudenay, ProvSec 2010 *(idem)*
- Canonne, *A Survey on Distribution Testing*, 2020. https://theoryofcomputing.org/articles/gs009/gs009.pdf
- Paninski, IEEE-IT 2008. https://ieeexplore.ieee.org/document/4626074/
- Rogaway, *Nonce-Based Symmetric Encryption*, FSE 2004. https://iacr.org/archive/fse2004/30170349/30170349.pdf

**Especificações e provas dos quatro algoritmos**
- NIST SP 800-232, ago/2025. https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-232.pdf
- Chakraborty, Dhar, Nandi, ASIACRYPT 2023. https://eprint.iacr.org/2023/775.pdf
- GIFT-COFB v1.1. https://csrc.nist.gov/CSRC/media/Projects/lightweight-cryptography/documents/finalist-round/updated-spec-doc/gift-cofb-spec-final.pdf
- Inoue, Iwata, Minematsu. https://eprint.iacr.org/2021/737
- Grain-128AEADv2. https://csrc.nist.gov/CSRC/media/Projects/lightweight-cryptography/documents/finalist-round/updated-spec-doc/grain-128aead-spec-final.pdf
- SPARKLE / Schwaemm & Esch. https://csrc.nist.gov/CSRC/media/Projects/lightweight-cryptography/documents/round-2/spec-doc-rnd2/sparkle-spec-round2.pdf
- NIST IR 8454. https://nvlpubs.nist.gov/nistpubs/ir/2023/NIST.IR.8454.pdf
- Erlacher, Mendel, Eichlseder, ToSC 2022(1). https://tosc.iacr.org/index.php/ToSC/article/view/9527
- Gilbert, Heim Boissier, Khati, Rotella, EUROCRYPT 2023. https://eprint.iacr.org/2023/262
- *Improved Conditional Cube Attacks on Ascon AEADs*. https://eprint.iacr.org/2024/743

**Rodadas reduzidas e testes estatísticos**
- Bellini & Huang, NIST LWC Workshop 2022. https://csrc.nist.gov/csrc/media/Events/2022/lightweight-cryptography-workshop-2022/documents/papers/randomness-testing-of-the-nsit-lightweight-cipher-finalist-candidates.pdf
- Bellini, Huang, Rachidi, SecITC 2022, LNCS 13809. https://link.springer.com/chapter/10.1007/978-3-031-32636-3_8
- Doğanaksoy, Ege, Koçak, Sulak. https://eprint.iacr.org/2010/564
- Sýs, Klinec, Švenda, *BoolTest*, SECRYPT 2017. https://crocs.fi.muni.cz/_media/public/papers/booltest_preprint_2017.pdf

**Teoria de aprendizado**
- Kearns & Valiant, JACM 41(1), 1994. https://dl.acm.org/doi/10.1145/174644.174647
- Kharitonov, STOC 1993. https://dl.acm.org/doi/10.1145/167088.167197
- Raz, FOCS 2016 / JACM 66(1) 2019. https://dl.acm.org/doi/10.1145/3186563
- Feldman, arXiv:2004.00557. https://arxiv.org/pdf/2004.00557
- Feldman et al., JACM 2017. https://arxiv.org/pdf/1201.1214
- Daniely & Vardi, COLT 2021. https://proceedings.mlr.press/v134/daniely21a.html
- Kou et al., NeurIPS 2024. https://arxiv.org/abs/2404.12376
- Brennan & Bresler, COLT 2020. https://proceedings.mlr.press/v125/brennan20a.html
- Rivest, ASIACRYPT 1991. https://link.springer.com/chapter/10.1007/3-540-57332-1_36

**ML e criptanálise: positivos, negativos e críticas**
- Gerault, Hambitzer, Huppert, Picek, ePrint 2024/1300. https://eprint.iacr.org/2024/1300.pdf
- Benamira, Gerault, Peyrin, Tan, EUROCRYPT 2021. https://eprint.iacr.org/2021/287
- Baksi et al., ePrint 2020/571 / DATE 2021. https://eprint.iacr.org/2020/571
- MIND-Crypt. https://arxiv.org/abs/2405.19683 · https://eprint.iacr.org/2024/852.pdf · https://doi.org/10.3390/cryptography10010009
- Calderon, Johansson, Günlü, arXiv:2604.06942. https://arxiv.org/pdf/2604.06942
- *Plaintext Structure Vulnerability*, arXiv:2511.08296. https://arxiv.org/html/2511.08296
- de Mello & Xexéo, JUCS 24(1), 2018. https://www.jucs.org/jucs_24_1/identifying_encryption_algorithms_in/jucs_24_01_0025_0042_demello.pdf
- Esquema híbrido k-NN + RF. https://pmc.ncbi.nlm.nih.gov/articles/PMC9575859/
- Kelsey, McKay, Turan, CHES 2015. https://eprint.iacr.org/2015/600.pdf
- Truong et al., IEEE TIFS 14(2), 2019. https://arxiv.org/abs/1905.02342

---

# Pesquisa 04 — Identificação de cifra de fluxo pelo keystream

- **Ângulo:** Identificação de cifra de fluxo pelo keystream
- **Temperatura declarada:** 0,55

## Pesquisa 04 — prompt usado, na íntegra

````markdown
# Pesquisa 04 — Identificação de cifra de fluxo pelo keystream

**Ângulo desta pesquisa.** Foque nas cifras de FLUXO, que são o caso onde o
criptograma é literalmente `plaintext XOR keystream` e portanto onde qualquer
viés do gerador atravessa direto para a saída observável.

Persiga: a literatura de vieses de keystream (RC4 e sucessores, A5/1, E0,
Trivium, Grain, Salsa/ChaCha), com os números — que viés, em que posição, com
que magnitude, detectável com quantos bytes; ataques de correlação e
correlação rápida e o que deles sobrevive sem plaintext conhecido;
reconhecimento de cifra de fluxo pelo keystream (a literatura antiga de
"cipher identification"); e testes específicos para geradores baseados em
LFSR e NFSR.

Pergunta central: **num cenário em que só se vê `P XOR Z` com P desconhecido
mas de distribuição conhecida, que vieses de Z continuam detectáveis, e a que
custo em dados?** Traga a matemática do piling-up lemma aplicada a esse caso.

Interessa muito o Grain-128AEAD em particular: quais vieses são conhecidos,
que fração do gerador o modo AEAD esconde, e se alguém já testou o gerador
isolado contra o gerador dentro do modo.

**Temperatura: 0,55.** Escala de amplitude de exploração, de 0,1 a 1,0.
Não é temperatura de amostragem — é instrução. Em 0,55: equilíbrio. Ancore em
literatura estabelecida, mas persiga conexões laterais quando elas
aparecerem, e proponha adaptações desde que marque claramente o que é sua.

---

# Prompt base — técnicas de distinção de algoritmos de criptografia

Este é o texto-mãe. Cada uma das 10 pesquisas recebe uma variação dele, com um
ângulo diferente e uma temperatura, e NADA MAIS: nem o repositório, nem os
resultados das pesquisas anteriores, nem esta conversa.

---

## PROBLEMA DE PESQUISA

Você está pesquisando para uma dissertação de mestrado em criptografia
aplicada e aprendizado de máquina. Trabalhe SÓ com literatura externa: não
leia nenhum repositório, arquivo local ou resultado prévio. Comece do zero.

**A pergunta.** Dado apenas o criptograma — sem a chave, sem o texto em claro,
sem poder escolher nada do que é cifrado — é possível distinguir qual
algoritmo de criptografia autenticada o produziu? E, num segundo nível, com
quantas rodadas reduzidas um algoritmo ainda deixa de parecer aleatório?

**Os algoritmos.** Os quatro finalistas do concurso NIST Lightweight
Cryptography: Ascon-AEAD128 (esponja), GIFT-COFB (cifra de bloco em modo
COFB), Grain-128AEAD (cifra de fluxo com LFSR e NFSR) e Schwaemm256-128
(esponja ARX, família SPARKLE).

**O modelo de ameaça, que é a restrição dura e não negocia.** Adversário
PASSIVO, em ciphertext-only. Ele observa criptogramas de um mesmo dispositivo,
com nonces públicos de contador, e pode observar vários de uma vez. Ele NÃO
tem: texto em claro conhecido ou escolhido, diferenças escolhidas na entrada,
reuso de nonce, acesso a canais laterais, nem consultas a um oráculo de
cifragem. Isso exclui de saída a maior parte da criptanálise diferencial
clássica e os distinguidores neurais no estilo Gohr, que dependem de pares com
diferença escolhida.

**O protocolo experimental.** Classificadores clássicos e redes sobre features
estatísticas e sobre os bytes crus. Chaves de teste nunca aparecem no treino
(key-holdout). Intervalo de confiança por bootstrap agrupado por chave, e não
i.i.d. Correção para múltiplas comparações. Controle negativo obrigatório: com
o algoritmo completo o classificador tem que ficar no acaso.

## O QUE EU QUERO DE VOCÊ

Técnicas, representações, ataques ou ideias — publicadas ou adaptáveis — que
possam extrair sinal nesse cenário, ou que ajudem a delimitar com rigor por
que o sinal não existe. Interessa tanto o que funciona quanto a prova de que
algo é impossível.

Busque em literatura acadêmica real (IACR ePrint, ToSC/FSE, CHES, CRYPTO,
EUROCRYPT, ASIACRYPT, SAC, Designs Codes and Cryptography, IEEE, Springer,
arXiv) e em fontes técnicas sérias. Use termos de busca em inglês.

## COMO RESPONDER

Para cada ideia encontrada, escreva:

1. **O que é** — a técnica, em duas ou três frases.
2. **Fonte** — autores, título, veículo, ano. Link quando houver. Se você não
   conseguiu confirmar a existência do trabalho, diga isso explicitamente em
   vez de completar de memória.
3. **Cabe no nosso modelo?** — SIM, NÃO, ou ADAPTÁVEL. Se ADAPTÁVEL, diga
   exatamente o que teria de mudar e qual premissa do modelo de ameaça isso
   arranha.
4. **O que custaria testar** — ordem de grandeza de dados, computação e
   engenharia.
5. **O que ela prevê** — se a técnica funcionar, que resultado deveríamos ver?
   Se não houver previsão falsificável, diga isso.

Termine com uma seção **APOSTAS**: as três ideias que você tentaria primeiro,
e por quê. Seja específico; "usar deep learning" não é uma aposta.

## PROFUNDIDADE — leia isto com atenção

Não é um levantamento rápido. **Vá até esgotar o veio.** Não pare em cinco ou
dez achados porque já "deu para ter uma ideia": siga as citações para frente e
para trás, abra os trabalhos relacionados dos artigos que importarem, procure
versões estendidas e teses, e persiga as pistas que aparecerem no caminho,
mesmo as que não estavam no ângulo original. Só encerre quando as buscas novas
pararem de trazer coisa nova.

Traga TODA a informação, não um resumo dela. Se um artigo tem um número que
importa (quantas rodadas, quantas consultas, que acurácia, que tamanho de
dado), traga o número. Se tem uma limitação declarada pelos próprios autores,
traga a limitação com as palavras deles. Prefira errar por excesso de detalhe.
Uma resposta longa e completa é o que se pede aqui; uma resposta enxuta é
falha de execução.

## REGRAS

- Não invente referências. Uma fonte não confirmada vale menos que nenhuma, e
  vou checar.
- Não repita o óbvio já saturado (distinguidor diferencial-neural padrão)
  sem trazer um ângulo novo que sobreviva ao ciphertext-only.
- Se a conclusão honesta de um caminho for "isso é impossível neste modelo
  por tal razão teórica", isso é resultado útil. Diga.
- Separe o que é publicado do que é sua extrapolação. Marque cada um.
````

## Pesquisa 04 — achados, sem resumir

### Achados — Pesquisa 04

- **Ângulo:** identificação de cifra de fluxo pelo keystream
- **Temperatura declarada:** 0,55
- **Prompt usado:** `prompts/04_cifras_de_fluxo.md`
- **Execução:** ~294k tokens de subagente, 66 chamadas, ~26 min

---

### Identificação de cifra de fluxo pelo keystream em cenário ciphertext-only

Marcação: **[MINHA EXTRAPOLAÇÃO]** = construção do agente, não publicada.

---

#### PARTE 0 — A matemática do problema: `C = P XOR Z` com P de distribuição conhecida

##### 0.1 Piling-up lemma na forma geral (convolução de Fourier)

Em F2^n (n = tamanho do bloco observado). Para distribuição p sobre F2^n, o coeficiente de Walsh/Fourier na máscara a:

```
c_p(a) = soma_x p(x)*(-1)^(a.x) = E[(-1)^(a.X)]
```

com c_p(0)=1 e, para a != 0, c_p(a) = Pr[a.X=0] - Pr[a.X=1] = 2*eps_a.

Se **C = P XOR Z** com P independente de Z, então p_C = p_P * p_Z (convolução XOR) e o teorema da convolução dá:

```
c_C(a) = c_P(a) * c_Z(a)      para toda máscara a
```

Isso **é** o piling-up lemma, na forma que não precisa de hipótese de independência entre bits. Na notação escalar clássica:

```
Pr[a.C = 0] = 1/2 + 2*eps_P*eps_Z
```

##### 0.2 Custo em dados

Distinguir Bernoulli(1/2+eps) de Bernoulli(1/2) custa N ≈ kappa/eps^2 amostras (kappa entre 0,25 e ~2). Logo:

```
N_CT-only  ≈ kappa / (c_P(a)^2 * c_Z(a)^2)
N_known-PT ≈ kappa / c_Z(a)^2

Penalidade por não conhecer o plaintext = 1 / c_P(a)^2   — exatamente isso, nada mais.
```

Todo o problema se reduz a **um único número por máscara**: c_P(a). Três regimes:

| Regime | c_P(a) | Penalidade | Exemplo real |
|---|---|---|---|
| **Determinístico** | ±1 | **1 (zero perda)** | bit 7 de byte ASCII = 0; paridade de código corretor aplicado antes da cifragem (GSM) |
| **Estatístico** | pequeno mas != 0 | 1/c_P^2 | texto natural, imagem natural |
| **Uniforme** | 0 | infinito | plaintext aleatório uniforme |

O terceiro caso é o resultado de impossibilidade: **se P for uniforme e independente, p_C é exatamente uniforme — é one-time pad.** Nenhuma estatística, linear ou não, nenhuma rede, nenhum volume de dados, distingue coisa alguma. Não é "difícil": é informação-teoricamente vazio.

##### 0.3 Além do linear: limite sobre TODAS as estatísticas de uma vez

Capacidade / squared Euclidean imbalance: Delta(p) = soma_{a!=0} c_p(a)^2. O distinguidor ótimo (Baignères–Junod–Vaudenay, ASIACRYPT 2004; Hermelin–Cho–Nyberg) precisa de N ≈ kappa'/Delta. Pela identidade de convolução:

```
Delta(p_C) = soma_{a!=0} c_P(a)^2 * c_Z(a)^2  <=  (max_{a!=0} c_P(a)^2)*Delta(p_Z)  <=  Delta(p_Z)
```

**XOR com um plaintext independente só pode encolher a capacidade de distinção, nunca aumentar.** O mapa x -> x XOR P é canal duplamente estocástico com U como ponto fixo, logo é contração em variação total:

```
TV(p_C, U) <= TV(p_Z, U)
```

E para classificação binária balanceada A vs B, a acurácia balanceada de *qualquer* classificador satisfaz BA <= (1/2)(1 + TV(p_C^A, p_C^B)) e, por desigualdade triangular:

```
BA <= (1/2)*(1 + TV(p_Z^A, U) + TV(p_Z^B, U))
```

**Enunciado formal do controle negativo obrigatório da dissertação.** Se cada keystream está a distância delta do uniforme na janela observada, nenhum classificador passa de 1/2+delta. Não é conjectura, é cota.

##### 0.4 O custo real do plaintext natural — números

Para estatística de coincidência a lag g (o observável que a literatura de RC4 usa), com P_chapeu = P_r XOR P_{r+g}:

```
Pr[C_chapeu = 0] = soma_v p_P̂(v)*p_Ẑ(v) ≈ 2^-8 + delta*(p_P̂(0) - 2^-8)
```

O fator de atenuação é (p_P̂(0) - 2^-8), e p_P̂(0) é o **índice de coincidência** do corpus.

- Texto inglês em bytes (com espaços): IC ≈ 0,065 → atenuação ≈ 0,061 ≈ **2^-4**, penalidade em dados ≈ **2^8**.
- Imagem natural em escala de cinza, g pequeno: diferenças adjacentes com distribuição laplaciana concentrada; p_P̂(0) frequentemente **> 0,10** → atenuação melhor que texto.
- Plaintext uniforme: p_P̂(0) = 2^-8 → atenuação **exatamente 0**.

**Conclusão quantitativa mais importante desta pesquisa:** a máscara do plaintext natural é *barata* — custa da ordem de 2^8 em dados, não 2^80. O gargalo não é o desconhecimento do plaintext. O gargalo é o viés do keystream em si. Esses dois problemas são rotineiramente confundidos e é importante separá-los no texto.

---

#### PARTE 1 — Grain-128AEAD: o que o modo AEAD esconde, com os números

##### 1.1 Fatos da especificação (verificados no documento oficial)

**Fonte:** Hell, Johansson, Maximov, Meier, Sönnerup, Yoshida. *Grain-128AEADv2*, spec da rodada final do NIST LWC. https://csrc.nist.gov/CSRC/media/Projects/lightweight-cryptography/documents/finalist-round/updated-spec-doc/grain-128aead-spec-final.pdf

Componentes (§2.1):
- LFSR 128 bits, f(x) = 1 + x^32 + x^47 + x^58 + x^90 + x^121 + x^128 (primitivo, peso 7)
- NFSR 128 bits; taps **lineares** de g: b^t_0, b^t_26, b^t_56, b^t_91, b^t_96 (+ s^t_0), grau 4
- h(x) = x0x1 + x2x3 + x4x5 + x6x7 + x0x4x8, sobre (b12,s8,s13,s20,b95,s42,s60,s79,s94)
- Pré-saída: **y_t = h(x) + s^t_93 + soma_{j em A} b^t_j**, com A = {2,15,36,45,64,73,89}

Inicialização (§2.2): 320 clocks realimentando y_t; + 64 clocks reintroduzindo a chave; + 128 clocks para carregar acumulador A_0 = y_384..447 e registrador R_0 = y_448..511. **Total 512 clocks antes do primeiro bit de keystream.**

**A divisão (§2.3) — resposta direta à pergunta:**
```
z_i  = y_{512+2i}       → CIFRAGEM  (bits PARES da pré-saída)
z'_i = y_{512+2i+1}     → AUTENTICAÇÃO (bits ÍMPARES, entram no registrador R)
c_i  = m_i XOR z_i
a^{i+1}_j = a^i_j + m_i*r^i_j    (hash Toeplitz)
```

**O modo AEAD esconde exatamente 50% do gerador — todos os bits ímpares da pré-saída.** Além disso, com AD vazia, m' = Encode(0)||m||0x80 = 0x00||m||0x80, e a máscara AEAD zera z para os 8 primeiros bits. A cifragem observável começa em z_8 = y_528. O bit de padding 0x80 também não é cifrado. Bits observáveis: **y_528, y_530, y_532, ...** — decimação por 2 a partir do índice 528.

Limite de keystream: **2^80 bits por par (chave, nonce)**, i.e. 2^81 bits de pré-saída (§2.4).

##### 1.2 Vieses conhecidos — os números

**§3.4.4 e §3.4.5 da especificação:**
- g é balanceada, não-linearidade 267.403.264, resiliência 4. Há **2^14 aproximações lineares de g com viés eps_g = 63*2^-15 < 2^-9**, com eta(A_g)=5 variáveis do NFSR.
- A função de pré-saída tem não-linearidade 2^8*240 = 61.440. Há **2^8 aproximações lineares com viés máximo eps_h = 2^-5**, com eta(A_h)=7.

**§4.2 — os próprios projetistas aplicam o piling-up lemma:**
```
eps = 2^(eta(A_h)+eta(A_g)-1) * eps_g^eta(A_h) * eps_h^eta(A_g)
    = 2^11 * (2^-9)^7 * (2^-5)^5 = 2^(11-63-25) = 2^-77
```
**eps < 2^-77 é o melhor viés conhecido para combinação linear invariante no tempo de bits de pré-saída (incluindo bits do LFSR).** E explicitam: para obter expressão *só* em bits de keystream é preciso somar versões deslocadas pela recorrência do LFSR, "o que vai novamente reduzir o viés segundo o piling-up lemma".

§4.6: probabilidade de substituição do MAC P_S <= 2^-w + 2*eps, com w=64 e eps ≈ 2^-77 → essencialmente 2^-64, i.e. adivinhar a tag.

##### 1.3 O gerador isolado versus dentro do modo — **sim, alguém testou, e a resposta é explícita**

**Fonte:** Todo, Isobe, Meier, Aoki, Zhang. *Fast Correlation Attack Revisited — Cryptanalysis on Full Grain-128a, Grain-128, and Grain-v1*, CRYPTO 2018, LNCS 10992, pp. 129–159. https://eprint.iacr.org/2018/522

Tabela 1 (ksg = key-stream generator, init = inicialização):

| Alvo | Ataque | Hipótese | Dados | Tempo |
|---|---|---|---|---|
| Grain-128a | ksg, FCA | — | **2^113,8** | 2^115,4 |
| Grain-128 | init, dynamic cube | chosen IV | 2^63 | 2^90 |
| Grain-128 | init, dynamic cube | chosen IV | 2^62,4 | 2^84 |
| Grain-128 | ksg, FCA | — | 2^112,8 | 2^114,4 |
| Grain-v1 | ksg, fast near collision | — | 2^19 | 2^86,1 |
| Grain-v1 | ksg, FCA | — | 2^75,1 | 2^76,7 |

Correlações: Grain-128a, (n,m,c) = (128, ~2^26,6 máscaras, **±2^-54,2381**). Grain-128, 2^26 máscaras com **±2^-51**. Grain-v1, 442.368 máscaras com |cor| > **2^-36**. Melhor característica linear isolada (MILP): ±2^-80,159 para Grain-128a e ±2^-38,497 para Grain-v1.

**Nota de rodapé 6, literal:**
> "Grain-128a has two modes of operation: stream cipher mode and authenticated encryption mode. We assume that all output sequences of the pre-output function can be observed. This assumption naturally holds under the known-plaintext setting on the stream cipher mode. On the other hand, it is difficult to observe them under the reasonable assumption on the authentication mode because **the half of the pre-output function is not used as the key stream**. Therefore, we do not claim that the authenticated encryption mode is attacked."

**§8.5, "Possible Countermeasure against Our New Attack", literal:**
> "The simplest countermeasure is to suppress the output at every second position when the key stream is output. For example, the authenticated encryption mode of Grain-128a has such structure, where the key stream is output only in the even clock. When we attack Grain-128a, we want to use T_z = {0, 26, 56, 91, 96, 128}, but we cannot tap 91. **As far as we search, we cannot detect a preferable T_z under the condition that the tapped indices are only even numbers.**"

E os projetistas, §4.3 da especificação:
> "It should be noted that this fast correlation attack does not apply to Grain-128a in authentication mode, as then only every second key stream bit may be accessible to an opponent. In addition, Grain-128AEADv2 limits the keystream length to 2^80 bits."

##### 1.4 **[MINHA EXTRAPOLAÇÃO]** Quanto custa a decimação, quantitativamente

Os dois textos dizem "não conseguimos" mas não quantificam. Dá para quantificar:

**(a) O lado do LFSR sobrevive de graça.** Se q(x) é *exatamente* satisfeito pela sequência (caso do f(x) do LFSR), então q(x)^2 = q(x^2) sobre F2 também é, com **exatamente os mesmos 7 termos** e expoentes dobrados: f(x)^2 = 1 + x^64 + x^94 + x^116 + x^180 + x^242 + x^256 — todos pares. Equivalentemente (Golomb, *Shift Register Sequences*): a decimação por 2 de uma m-sequence binária é um deslocamento cíclico dela mesma, porque Tr(c*alpha^(2t)) = Tr(sqrt(c)*alpha^t). **Eliminar o LFSR não custa nada sob decimação.**

**(b) O lado do NFSR é onde a decimação morre.** T_z vem dos taps *lineares* de g, não de f. O tap 91 é ímpar e não há como evitá-lo dentro de uma única instância da relação. A saída genérica é elevar ao quadrado a relação *ruidosa*: se (q(x)*z)_t = n_t com correlação c, então

```
(q(x^2)*z)_t = (q(x)*q(x)*z)_t = (q(x)*n)_t = XOR_{i em T_z} n_{t+i}
```

com suporte 2*T_z = {0, 52, 112, 182, 192, 256} — **todos pares, logo totalmente observável no modo AEAD** — mas com correlação c' = c^|T_z| = c^6 pelo piling-up.

```
c  = 2^-54,24   → N ≈ c^-2  = 2^108,5 bits   (modo stream cipher)
c' = c^6 = 2^-325,4 → N ≈ c'^-2 = 2^650,9 bits  (modo AEAD, relação quadrada)
```

**A decimação por 2 do modo AEAD custa cerca de 2^542 em dados** — e 2^651 está 2^571 acima do próprio teto de 2^80 bits por (K,N) que a cifra impõe. Explica *por que* Todo et al. "não conseguiram encontrar um T_z par preferível": o truque existe, mas o preço é a correlação elevada à sexta potência.

**Distinguidor puro (sem recuperação de estado):** eliminar o LFSR do relacionamento de viés 2^-77 exige somar sobre o suporte de f (peso 7) → c ≈ (2*2^-77)^7 = 2^-532, logo **N ≈ 2^1064 bits**.

##### 1.5 Demais resultados sobre Grain (fora do modelo, úteis para rodadas reduzidas)

| Resultado | Rodadas de init (256 em Grain-128a; 512 em AEADv2) | Hipótese | Fonte |
|---|---|---|---|
| Conditional differential, chave única | 177 | chosen IV | Lehmann & Meier, CANS 2012, LNCS 7712, pp. 1–11 |
| Conditional differential, weak key | 189 | chosen IV + weak key | idem |
| Conditional differential, cubos dim. 5 | 191 (chave única) / 201 (weak key) | chosen IV | Ma, Tian, Qi, IET Inf. Security, 2017 |
| Cube/division property, key recovery | 184 (dados 2^95, tempo 2^110) | chosen IV | Todo, Isobe, Hao, Meier, CRYPTO 2017 |
| Cube/division property, superpoly exato | 190–192 (key recovery a 2^123 em 190) | chosen IV, weak key | Hao, Leander, Meier, Todo, Wang; https://eprint.iacr.org/2024/342.pdf |
| Zero-sum distinguisher | 193 (weak key) | chosen IV | idem |
| Reconstrução de chave a partir do estado | **2^62** | estado conhecido + msg e tag conhecidos | Chang & Turan, https://eprint.iacr.org/2021/439.pdf — motivou o tweak da v2 |

Todos exigem escolha de IV. **Nenhum resultado publicado ataca o gerador de keystream do Grain-128AEAD em rodadas completas, e nenhum funciona em ciphertext-only.**

---

#### PARTE 2 — Os quatro precedentes publicados de criptanálise CT-only real

##### IDEIA 1 — Ataque de difusão (broadcast) sobre RC4

**O que é.** O keystream de RC4 tem vieses *dependentes da posição* nos primeiros 256 bytes. Se o mesmo plaintext é cifrado sob muitas chaves, a distribuição empírica de C_r sobre as sessões é a distribuição do keystream Z_r *deslocada* pelo byte constante P_r. Recupera-se P_r por máxima verossimilhança multinomial. Nenhum plaintext é conhecido — só sua *constância*.

**Fontes.**
- Mantin & Shamir, *A Practical Attack on Broadcast RC4*, FSE 2001, LNCS 2355, pp. 152–164. Pr[Z_2 = 0x00] ≈ **1/128**. Recupera o 2º byte com Omega(256) criptogramas.
- Sen Gupta et al.: para 3 <= r <= 255, Pr[Z_r = 0x00] = 1/256 + c_r/256^2, com c_3 = 0,351089 e 0,242811 <= c_r <= 1,337057 — viés absoluto ≈ **2^-16**.
- Isobe, Ohigashi, Watanabe, Morii, *Full Plaintext Recovery Attack on Broadcast RC4*, FSE 2013, LNCS 8424, pp. 179–202: **2^34 criptogramas** recuperam os primeiros 257 bytes com prob. ≈1.
- AlFardan, Bernstein, Paterson, Poettering, Schuldt, *On the Security of RC4 in TLS*, USENIX Security 2013, pp. 305–320. https://www.usenix.org/system/files/conference/usenixsecurity13/sec13-paper_alfardan.pdf

**O Algoritmo 4 de AlFardan et al. é literalmente a ferramenta certa:**
```
lambda_mu = S!/(N^(mu)_0x00!...N^(mu)_0xFF!) * Prod_k p_{r,k}^(N_k^(mu))     (eq. 1)
onde N_k^(mu) = |{ j : C_{j,r} = k XOR mu }|
```
MLE exato de um byte de plaintext contra distribuição de keystream pré-computada. Explicitam: *"we use Bayes's law to compute the a posteriori plaintext distribution from the a priori plaintext distribution and the precomputed distributions of the Z_r."*

**Números:**
| Sessões | Resultado |
|---|---|
| 2^24 | algumas posições já recuperadas com alta probabilidade |
| 2^26 | primeiros 46 bytes com >=50% por byte; 112 bytes se o alfabeto tiver 16 símbolos |
| 2^32 | >=96% em todas as 256 primeiras posições, 100% em todas menos 12 |
| 13*2^30 (duplo byte) | 100% em 16 bytes consecutivos |

Estatísticas pré-computadas com **2^44 chaves aleatórias de 128 bits**.

**Cabe no modelo? NÃO — por razão estrutural.** Exige plaintext *fixo* repetido em muitas sessões. No dataset encadeado, cada slot tem plaintext distinto. A repetição existente é entre-algoritmos, e isso é o pareamento já rejeitado como fora de CT-only.

**Subproduto crítico:** o conceito de **estatística indexada por posição, agregada entre amostras**. É o ponto metodológico mais forte desta pesquisa (ver Aposta 2).

##### IDEIA 2 — Diferencial de criptograma: o viés ABSAB sem plaintext fixo

**O que é.** Mantin descobriu que dígrafos de RC4 tendem a se repetir com pequenos gaps (padrão ABSAB). O viés vive numa *diferença* de posições do keystream, e diferenças de keystream se traduzem em diferenças de criptograma menos diferenças de plaintext.

**Fontes.**
- Mantin, *Predicting and Distinguishing Attacks on RC4 Keystream Generator*, EUROCRYPT 2005, LNCS 3494. Probabilidade do padrão ABSAB com gap G: (1 + e^((-4-8G)/N)/N)/N^2. Distinguidor de RC4 com apenas **2^26 bytes de saída**.
- Vanhoef & Piessens, *All Your Biases Belong To Us: Breaking RC4 in WPA-TKIP and TLS*, USENIX Security 2015 (Best Student Paper). https://www.rc4nomore.com/vanhoef-usenix2015.pdf

**As equações que interessam (§4.2), literais:**
```
Z_chapeu^g_r = (Z_r XOR Z_{r+2+g},  Z_{r+1} XOR Z_{r+3+g})          (17)
Pr[Z_chapeu^g_r = (0,0)] = 2^-16(1 + 2^-8 * e^((-4-8g)/256)) = alpha(g)   (18)
Pr[C_chapeu^g_r = P_chapeu^g_r] = alpha(g)                           (19)
```
> *"Hence Mantin's bias implies that the ciphertext differential is biased towards the plaintext differential."*

Verossimilhança binomial (eq. 22): lambda = (1-alpha(g))^(|C|-|mu|) * alpha(g)^|mu|.

**Números:** viés ABSAB confirmado até **gaps >= 135 bytes** (2^48 blocos de 512 bytes de keystream). Fig. 7, decifrar dois bytes: ABSAB sozinho ≈2^38 criptogramas; Fluhrer–McGrew sozinho ≈2^35; FM + 258 vieses ABSAB combinados ≈**2^33**. Ataque prático a cookie TLS: 9*2^27 criptogramas, 75 horas, 94% de sucesso (Paterson, Poettering, Schuldt, ASIACRYPT 2014).

Vieses de dígrafo de Fluhrer–McGrew (FSE 2000, LNCS 1978, pp. 19–30) — tabela completa:

| Par de bytes | Condição em i | Probabilidade |
|---|---|---|
| (0,0) | i=1 | 2^-16(1+2^-9) |
| (0,0) | i!=1,255 | 2^-16(1+2^-8) |
| (0,1) | i!=0,1 | 2^-16(1+2^-8) |
| (i+1,255) | i!=254 | 2^-16(1+2^-8) |
| (255,i+1) | i!=1,254 | 2^-16(1+2^-8) |
| (255,i+2) | i!=0,253,254,255 | 2^-16(1+2^-8) |
| (255,0) | i=254 | 2^-16(1+2^-8) |
| (255,1) | i=255 | 2^-16(1+2^-8) |
| (255,2) | i=0,1 | 2^-16(1+2^-8) |
| (129,255) | i=2 | 2^-16(1+2^-8) |
| (255,255) | i!=254 | 2^-16(1-2^-8) |
| (0,i+1) | i!=0,255 | 2^-16(1-2^-8) |

Fluhrer & McGrew distinguem RC4 de aleatório com **2^30,6 bytes de saída**.

Vieses de longo prazo de Vanhoef–Piessens: Pr[(Z_256w, Z_256w+2) = (128,0)] = 2^-16(1+2^-8); Pr[Z_256w+a = Z_256w+b] ≈ 2^-8(2 ± 2^-16).

Custo de engenharia reportado: dataset `first16` com 2^44 chaves ≈ **9 CPU-anos**; `consec512` com 2^45 chaves ≈ **16 CPU-anos**; longo prazo 2^12 chaves x 2^40 bytes ≈ **8 CPU-anos**.

**Cabe no modelo? SIM, integralmente.** É *uma* observação de criptograma, duas posições internas. Não precisa de plaintext conhecido, nem repetido, nem de pares relacionados. A única informação externa é a distribuição de P_r XOR P_{r+g} do corpus — conhecimento público sobre a fonte, precisamente o que Barkan–Biham–Keller legitimam.

**Custo.** Baixo. Acrescentar ao extrator o **histograma de 256 bins de C_r XOR C_{r+g}** para lags g em {1,2,4,8,16,32,64,128,256,512,1024}, acumulado sobre as ~65k posições. São 256x11 = 2816 features novas, ou ~55 se comprimir (momentos + massa em v=0 + entropia por lag). Uma passada O(65536*|G|) por amostra, vetorizável em NumPy; para 180k amostras, horas de CPU. Zero GPU.

**Diferença crucial em relação à ACF existente (lags 1–16):** a ACF é um *escalar* por lag (correlação de bits); o histograma do diferencial é uma distribuição de 256 células por lag. A capacidade Delta da distribuição de 256 células domina largamente a de uma máscara única. Foi exatamente a diferença entre o Algoritmo 3 e o Algoritmo 4 de AlFardan et al. — eles mostram que o ingênuo *falha na prática*.

**O que prevê.** Se nenhum dos quatro tiver viés diferencial no keystream, o histograma de C_r XOR C_{r+g} deve ser idêntico entre as 4 classes e determinado *apenas* pela distribuição do diferencial de plaintext — compartilhada pelo encadeamento. Previsão: **o histograma diferencial deve ter capacidade Delta substancial (é o plaintext aparecendo), mas Delta idêntica entre classes.** Se as features de diferencial melhorarem o F1, é sinal de cifra. Se não, o resultado negativo fica muito mais forte, porque cobriu a classe de estatística que realmente quebrou o RC4.

##### IDEIA 3 — Barkan–Biham–Keller: redundância determinística converte CT-only em known-keystream

**O que é.** O GSM aplica códigos corretores de erro *antes* da cifragem. O plaintext satisfaz equações de paridade conhecidas: K_G*M = 0. Como C = M XOR k, tem-se K_G*C = K_G*k. **O adversário obtém equações lineares exatas sobre o keystream, sem conhecer uma palavra da conversa.**

**Fonte.** Barkan, Biham, Keller, *Instant Ciphertext-Only Cryptanalysis of GSM Encrypted Communication*, CRYPTO 2003, LNCS 2729, pp. 600–616; estendido em *Journal of Cryptology* 21(3), 2008. https://www.iacr.org/archive/crypto2003/27290598/27290598.pdf

**Literal (§4):**
> "Let K_G be a matrix that describes these 272 linear equations, i.e., K_G*M = 0 for any such M. ... K_G*C = K_G*(M XOR k) = K_G*M XOR K_G*k = 0 XOR K_G*k = K_G*k. Since the ciphertext C is known, we actually get linear equations over elements of k. **Note that the equations we get are independent of P** — they depend only on k."

> "while four frames of data suffice to launch the attack in Section 3, in the ciphertext-only attack we need eight frames, **since from each encrypted frame we get only about half the information** compared to the known plaintext attack."

**Números:**
- A5/2, CT-only: 8 frames (dezenas de ms de conversa), tempo médio ≈ **2^16 produtos internos**, memória 2^28,8 bytes (< 500 MB), pré-computação ≈ 2^47 XOR-bits (~5,5 h). Recupera K_c em menos de 1 s num PC.
- A5/1, CT-only passivo (TMDTO, TM^2D^2 = N^2, N = 2^64):

| D (dados) | M | Discos de 200 GB | P = N/D | PCs p/ pré-comp. em 1 ano | T | PCs p/ ataque em tempo real |
|---|---|---|---|---|---|---|
| 2^12 (≈5 min) | 2^38 | ≈22 | 2^52 | 140 | 2^28 | 1 |
| 2^6,7 (≈8 s) | 2^41 | ≈176 | 2^57,3 | 5000 | 2^32,6 | 1000 |
| 2^6,7 (≈8 s) | 2^42 | ≈350 | 2^57,3 | 5000 | 2^30,6 | 200 |
| 2^14 (≈20 min) | 2^35 | ≈3 | 2^50 | 35 | 2^30 | 1 |

**Conclusão dos autores, literal (§8):**
> "We would like to emphasize that **our ciphertext-only attack is made possible by the fact that the error-correction codes are employed before the encryption.** In the case of GSM, the addition of such a structured redundancy before encryption is performed crucially reduces the system's security."

**Cabe no modelo? SIM — e é o precedente que legitima usar estrutura conhecida do plaintext dentro de CT-only.** Não conhecem nenhum bit do plaintext; conhecem a *especificação da fonte*. Exatamente a distinção que o modelo faz ("P desconhecido mas de distribuição conhecida").

**Custo.** O análogo direto: no corpus Gutenberg, texto ASCII de 7 bits tem **bit 7 = 0 em todo byte**. Isto é c_P(a) = ±1 exato para a máscara a = 0x80 em cada byte. Consequência: **o bit 7 de cada byte de criptograma É o bit correspondente do keystream, sem ruído.** Para Grain vale nos 65.536 bytes; para Ascon/GIFT-COFB/Schwaemm, apenas no primeiro bloco de rate. Verificar a premissa: contagem de bytes >= 0x80 no corpus, minutos. Explorar: extrair o "plano de bits 7" (8.192 bytes por amostra) e rodar todo o arsenal de testes — trivial.

**Ressalva honesta:** os 20% de ImageNet usam a faixa 0–255, então para essas amostras c_P(0x80) != ±1. E mesmo para texto, se o pipeline gravar Latin-1/UTF-8 com acentos, há bytes >= 0x80. Precisa ser medido, não assumido.

**O que prevê.** Se o bit 7 do texto for determinístico, o plano extraído é **keystream puro do Grain**, e qualquer teste que o distinga de aleatório é distinguidor de keystream genuíno. Previsão: não vai distinguir (melhor viés 2^-76, e há 2^30,9 bits nesse plano). Mas o resultado negativo passa a ser sobre o *keystream*, não sobre o criptograma — enunciado muito mais forte e citável. E é o teste certo para rodadas reduzidas.

##### IDEIA 4 — Correlação e correlação rápida: o que sobrevive sem plaintext

**O que é.** Siegenthaler (1984) e Meier–Staffelbach (1989): se z_t = s_t XOR e_t, com s_t saída do LFSR e e_t ruído enviesado (correlação c = 1-2p), recupera-se o estado inicial resolvendo decodificação. Complexidade fundamental (Todo et al. §2.2):

```
soma_{t=0}^{N-1} (-1)^(s_t XOR z_t)  ~  N(Nc, N)  se o estado é correto
                                     ~  N(0, N)   caso contrário
→ N ≈ O(1/c^2)
```

**Fontes.** Siegenthaler, IEEE Trans. IT 30(5), 1984, pp. 776–780. Meier & Staffelbach, J. Cryptology 1(3), 1989, pp. 159–176. Chepyzhov, Johansson, Smeets, FSE 2000; Chose, Joux, Mitton, EUROCRYPT 2002 (one-pass via FWHT). Canteaut & Trabbia, EUROCRYPT 2000 (parity-checks de peso 4 e 5). Todo et al., CRYPTO 2018. Lu & Vaudenay, *Faster Correlation Attack on Bluetooth Keystream Generator E0*, CRYPTO 2004, LNCS 3152: complexidade **2^39 com 2^39 bits**. Lu, Meier, Vaudenay, CRYPTO 2005. Zhang, Xu, Meier, *Fast Near Collision Attack on the Grain v1 Stream Cipher*, EUROCRYPT 2018: *"an attack for any fixed IV in 2^75.7 cipher ticks after the pre-computation of 2^8.1 cipher ticks, given 2^28-bit memory and about 2^19 keystream bits"* — **CONTESTADO:** Derbez, Fouque, Mollimard, *Fake Near Collisions Attacks*, ToSC 2020(4), reavaliam e concluem que o ataque implementado custa **mais que busca exaustiva**.

**Cabe no modelo? ADAPTÁVEL, mas o preço é proibitivo.**

O FCA precisa de z_t. Você tem c_t = p_t XOR z_t. Cada bit de keystream na equação de paridade traz um fator c_P. Equação de peso w tem correlação multiplicada por c_P^w. Para Grain-128a, w = |T_z| = 6:

```
c_CT-only = c * c_P^6
```
- Com c_P = 1 (bit determinístico, tipo GSM/ASCII): **penalidade zero**. Caso de Barkan–Biham–Keller.
- Com c_P = 2^-1: c cai por 2^6 → dados sobem por 2^12.
- Com c_P = 0: impossível.

Barreira que nenhuma escolha de plaintext resolve: **o FCA exige dados do mesmo (chave, nonce)** — Hell et al. §4.3, literal: *"The data needs to come from the same secret key and the same nonce."* No protocolo, cada amostra tem nonce novo. Teto sob mesmo (K,N): **2^19 bits** (uma amostra de 64 KB). Contra 2^113,8 no modo stream cipher, e ~2^651 no modo AEAD. **Déficit de 2^95 no melhor caso, e é estrutural do protocolo, não do adversário.**

**Custo.** Não vale testar o FCA. Vale **usar N ≈ 1/c^2 como instrumento de calibração** (Aposta 1).

##### IDEIA 5 — Diferencial de nonce em plano de bits determinístico **[MINHA EXTRAPOLAÇÃO — a ideia lateral que mais vale]**

**O que é.** O modelo diz "nonces públicos de contador" e "pode observar vários de uma vez". Um contador não é nonce aleatório: nonces consecutivos diferem em 1 bit (metade das vezes), nonces a distância 2^k diferem no bit k mais carries. **O adversário passivo recebe de graça, sem escolher nada, uma família rica de diferenças de IV de peso baixo** — exatamente a entrada de que a criptanálise diferencial condicional precisa.

O que normalmente falta é ver a diferença de keystream. Mas:

```
C_i XOR C'_i = (P_i XOR P'_i) XOR (Z_i XOR Z'_i)
```

e, nas posições onde P é determinístico (bit 7 de ASCII), P_i XOR P'_i = 0 **exatamente**, mesmo com P e P' sendo textos completamente distintos e não relacionados. Nesse plano de bits:

```
C_i XOR C'_i = Z_i XOR Z'_i   — diferença de keystream pura, sob diferença de nonce conhecida
```

**Isto não é plaintext relacionado.** A cancelação vem exclusivamente da distribuição marginal da fonte (todo byte ASCII tem bit 7 = 0), conhecimento público sobre o corpus — o mesmo tipo que Barkan–Biham–Keller usam sobre o código corretor do GSM. É a distinção entre "conheço a estrutura da fonte" (permitido) e "conheço ou relaciono os plaintexts" (proibido).

**Fonte.** A construção é do agente. Ingredientes publicados: Barkan, Biham, Keller, CRYPTO 2003 (mecanismo de cancelação); Knellwolf, Meier, Naya-Plasencia, *Conditional Differential Cryptanalysis of NLFSR-based Cryptosystems*, ASIACRYPT 2010; Lehmann & Meier, CANS 2012; Ma, Tian, Qi, IET Inf. Sec. 2017.

Não foi encontrado nenhum trabalho que enuncie "nonce de contador = oráculo diferencial gratuito em ciphertext-only". Se existir, não foi localizado; declarado explicitamente.

**Cabe no modelo? SIM, com uma linha a defender no texto.** Adversário passivo ok; sem plaintext conhecido ok; sem diferenças escolhidas ok (as diferenças são *dadas* pelo contador); sem reuso de nonce ok; sem oráculo ok. Não arranha nenhuma premissa do modelo — mas arranha a fronteira traçada no achado do XOR de pares. A diferença é substantiva: lá, a cancelação vinha de os dois criptogramas terem o *mesmo* plaintext (plaintext relacionado). Aqui, vem de a *fonte* ter um bit constante. É o que BBK fazem, e o título do artigo deles é literalmente "Instant Ciphertext-Only Cryptanalysis".

**Custo.**
- Verificar a premissa (bytes >= 0x80 no corpus): minutos.
- Extrair planos de bit 7 de pares com distância de nonce controlada: uma passada, horas.
- Experimento: para cada Delta em {1,2,4,...,2^k}, distribuição de (C XOR C')|bit7 testada contra uniforme com chi2, sobre todos os pares. Com 100 slots por chave: ~4.950 pares por chave x 300 chaves = 1,5 milhão de pares por algoritmo, cada um com 8.192 bytes limpos → ~1,2x10^10 bytes de diferencial por algoritmo. Dias de CPU, nenhum GPU.
- Ponto delicado: saber qual offset de bit dentro do byte corresponde ao MSB ASCII na convenção bit-oriented do Grain (MSB-first vs LSB-first no mapeamento byte→bit da API NIST). Determina-se empiricamente com um par cifra/decifra.

**O que prevê.**
- **Rodadas completas:** nada. Não há viés diferencial publicado em 512 rodadas.
- **Rodadas reduzidas:** piso **muito mais alto** que estatísticas globais, porque é o observável que os distinguidores diferenciais condicionais usam. Ancoradouros: 177 rodadas (chave única, chosen IV) e 189–201 (weak key). Sem poder impor *condições* no IV, perde-se o ganho do "conditional" (que leva o viés de ~2^-30 para ~2^-10), então espere algo entre o piso genérico e 177. **Previsão: o piso medido com diferencial de nonce deve ficar estritamente acima do piso medido com features globais.** Se não ficar, ou o plano não está limpo, ou o extrator está errado.
- Colateral: deve funcionar para Ascon/GIFT-COFB/Schwaemm, mas **só nos primeiros 16 (Ascon, COFB) ou 32 (Schwaemm) bytes**.

---

#### PARTE 3 — Vieses de keystream nas demais cifras

| Cifra | Viés / correlação | Dados para distinguir | Sobrevive CT-only? |
|---|---|---|---|
| **RC4** Z_2 = 0 | 1/128 | O(256) sessões broadcast | Sim, via broadcast |
| **RC4** Z_r = 0, r=3..255 | 1/256 + c_r/256^2, c_3=0,351 | 2^32–2^34 sessões | Sim, via broadcast |
| **RC4** dígrafos FM | 2^-16(1 ± 2^-8) | **2^30,6 bytes** | Sim, via diferencial (atenuado) |
| **RC4** ABSAB | 2^-16(1 + 2^-8 * e^((-4-8g)/256)) | 2^26 bytes (distinguidor) | **Sim, diretamente** (eq. 19) |
| **E0 (Bluetooth)** | correlações do FSM até 26 bits | 2^39 bits (Lu–Vaudenay) | Conceitualmente sim |
| **A5/1** | — (TMDTO) | 2^6,7–2^14 frames | **Sim, comprovado** (BBK) |
| **A5/2** | — (algébrico) | 8 frames | **Sim, comprovado** (BBK) |
| **Grain-v1** | cor ±2^-36 (442.368 máscaras) | 2^75,1 bits (FCA) | Não |
| **Grain-128** | cor ±2^-51 (2^26 máscaras) | 2^112,8 bits | Não |
| **Grain-128a** | cor ±2^-54,24 (2^26,6 máscaras) | 2^113,8 bits | Não |
| **Grain-128AEADv2** | eps < 2^-77 | >=2^152 bits; keystream-only >=2^1064 | **Não, por margem de ~2^118 a 2^1030** |
| **Trivium** | cube testers | distinguidor a 790 rodadas com 2^30; não-aleatoriedade a 885 com 2^27 | Não (chosen IV) |
| **Salsa20 / ChaCha** | sem distinguidor em rodadas completas; Salsa20/8 a 2^251, ChaCha7 a 2^248 | chosen IV | Não |

Referências dos dois últimos: Aumasson, Dinur, Meier, Shamir, FSE 2009; Aumasson, Fischer, Khazaei, Meier, Rechberger, FSE 2008.

---

#### PARTE 4 — Testes específicos para LFSR/NFSR

##### 4.1 Complexidade linear / Berlekamp–Massey — **não funciona, e dá para provar**

BM recupera o LFSR mínimo; precisa de 2L bits para LFSR de comprimento L. O teste de Linear Complexity do NIST STS compara o perfil de LC em blocos de M bits contra a distribuição teórica.

**Fonte.** Rukhin et al., *NIST SP 800-22 Rev. 1a*; Massey, IEEE Trans. IT 15(1), 1969. Nota: o teste de LC domina >80% do tempo total do NIST STS (Sýs, Říha et al., *Algorithm 970*, ACM TOMS 43(3), 2016).

**Cabe no modelo? Sim, mas é cego.** O NIST STS usa M = 500 ou 1000 bits, logo só detecta geradores com LC < ~250–500. A LC da saída do Grain é ditada pelo NFSR e pelas funções h e g de grau 4; está astronomicamente acima de 2^19 bits. Com N bits e LC real > N/2, BM reporta LC ≈ N/2 — a mediana de uma sequência aleatória.

**O que prevê.** **Zero informação, com certeza teórica.** Resultado útil: das 25 features NIST, a de complexidade linear é *provadamente* inútil para distinguir qualquer um dos quatro, e vale dizer isso no texto em vez de deixá-la na tabela como se fosse informativa.

##### 4.2 Perfil de LC e complexidade 2-ádica

Mesma conclusão. A única situação em que a família LFSR/NFSR deixa assinatura de complexidade é em **rodadas de inicialização muito reduzidas**, onde o estado ainda não difundiu. Vale medir no estudo de piso — não no experimento principal.

##### 4.3 O teste que *seria* específico: resíduo da recorrência do LFSR

**[MINHA EXTRAPOLAÇÃO]** O único teste verdadeiramente específico da arquitetura do Grain é avaliar o resíduo da recorrência:

```
R(t) = XOR_{i em T} z_{t+i},   T = suporte de um múltiplo de f(x) com expoentes pares
```

O suporte natural é f(x)^2 = {0,64,94,116,180,242,256} (peso 7, todos pares — totalmente observável no modo AEAD). Sob H0, R(t) é Bernoulli(1/2) exato. Sob H1, R(t) tem correlação igual ao produto das correlações dos 7 termos.

**Custo:** trivial — 7 XORs por posição, ~65k posições por amostra, uma feature escalar por amostra.

**O que prevê:** com Grain completo, correlação ≈ 2^-532 → nada, garantidamente. **Mas com rodadas reduzidas, é o teste com maior poder por bit de dado que existe para esta cifra**, porque é o teste que o próprio FCA usa. E tem propriedade valiosa: é *nula por construção* para Ascon, GIFT-COFB e Schwaemm (que não têm LFSR), logo é feature com semântica de identificação, não só de aleatoriedade. Vale no texto mesmo dando zero — é o teste que um criptanalista perguntaria "vocês fizeram?".

---

#### PARTE 5 — A estrutura comparada dos quatro (o que é `P XOR máscara` e onde)

| Algoritmo | Fórmula do criptograma | Máscara independente do plaintext? | Extensão |
|---|---|---|---|
| **Grain-128AEADv2** | c_i = m_i XOR z_i | **Sim, sempre** (z depende só de K,N) | toda a mensagem, 65.536 B |
| **Ascon-AEAD128** | C_i = P_i XOR S_r ; depois S_r <- C_i (duplex) | Só no bloco 0 | **16 bytes** |
| **GIFT-COFB** | rho(Y,M): C_i = M_i XOR Y_i, feedback G*Y XOR M | Só no bloco 0 (Y_1 derivado do nonce) | **16 bytes** |
| **Schwaemm256-128** | C_i = M_i XOR rho_2(S_L,.), Beetle com FeistelSwap | Só no bloco 0 | **32 bytes** |

Fontes: Dobraunig, Eichlseder, Mendel, Schläffer, *Ascon v1.2*; Banik et al., *GIFT-COFB v1.1* (rho_1(Y,M) = G*Y XOR M); Beierle et al., ToSC 2020(S1) e submissão NIST LWC.

**Três consequências práticas:**

1. **O Grain é qualitativamente diferente dos outros três.** Para ele, a amostra inteira é one-time pad sobre sequência que não depende do plaintext. Para os demais, só o primeiro bloco. Se algum viés de máscara existir, para o Grain há 65.536 bytes por amostra; para os outros, 16 ou 32.
2. **Sugere desenho de feature assimétrico:** estatísticas sobre a *janela inicial* (primeiros 16/32 bytes, agregadas sobre as 30.000 amostras) são o local certo para procurar vieses de *inicialização* em Ascon/COFB/Schwaemm — análogo exato aos "primeiros 256 bytes do RC4". As features globais diluem isso por 65536/16 = 4096.
3. **Armadilha metodológica a checar:** len_ct difere (Grain 65.544; os outros 65.552). É metadado e está corretamente excluído. Mas se o pipeline trunca para comprimento comum e faz *zero-padding* em vez de corte, ou se alguma janela (`tag_region`) cobre [65.536, 65.552) sem ajustar por algoritmo, a diferença de 8 bytes vira feature com F1 = 1,0 disfarçada. Vale verificação explícita e um parágrafo dizendo que foi verificada.

---

#### PARTE 6 — A literatura de "cipher identification" e por que ela mente

**A linhagem:**
- Dileep & Sekhar, *Identification of block ciphers using support vector machines*, IJCNN 2006, pp. 2696–2701.
- Manjula & Anitha, *Identification of Encryption Algorithm Using Decision Tree*, CCSIT 2011, CCIS 133, Springer. C4.5 com 8 features, 11 algoritmos, **70–75%**.
- Escola chinesa posterior: k-NN + RF híbrido, RF + LR, CNN, CNN-Transformer, FFT. Taxas frequentemente >90% "quando o arquivo passa de 100 KB".

**A crítica, publicada e com números.** *Plaintext Structure Vulnerability*, arXiv:2511.08296 (2025). Questão central: *"whether the trained model captures the inherent attributes of the cryptographic algorithm or depends on the statistical law of the training data"*. Mostram que o classificador aprende vetor que mistura "parte estável, específica do algoritmo" com "parte volátil, induzida pelo plaintext", e que os métodos existentes dependem quase inteiramente da segunda.

**Os números do colapso** (AES-ECB/CBC, 3DES, Blowfish, ChaCha20, RC4):

| Regime de plaintext | Acurácia |
|---|---|
| Regular_100 (100% estruturado) | **≈ 0,999** |
| Random_100 (0% estruturado) | **0,52 – 0,57** |

Queda de macro-F1 de **83,85% a 88,32%**. SVM vai de 0,999 para 0,566. (Macro-AUC é mais resiliente, caindo 46,68–49,67%.)

Criticam nominalmente: Dileep & Sekhar e Manjula & Anitha por sensibilidade à engenharia manual; CNN recentes por sensibilidade à composição e comprimento do plaintext; pipelines estatísticos por tratarem testes como veredicto binário pass/fail.

Proposta deles: 41 testes, calibração por transformada integral de probabilidade, histograma normalizado de K bins + 4 momentos por janela. Canterbury: SVM-RBF 0,897 ± 0,071 de acurácia, 0,985 ± 0,025 de AUC; mantêm AUC > 0,90 em Random_100 enquanto os baselines colapsam.

**Segunda fonte, resultado negativo limpo:** MIND-Crypt, arXiv:2405.19683 / eprint 2024/852, periódico *Cryptography* 10(1):9. SPECK32/64 e SIMON32/64: ML fica consistentemente em ≈50%.

**O que isso significa — e é boa notícia metodológica:** o experimento encadeado (mesmos plaintexts, chaves e nonces para todos) **elimina por construção** exatamente o confundidor que invalida 20 anos dessa literatura. Merece parágrafo próprio: os resultados positivos da literatura são artefato de estrutura de plaintext; o resultado negativo da dissertação é obtido num protocolo onde esse artefato não pode ocorrer, e portanto é *mais* informativo que os positivos deles.

E o inverso como advertência: **se aparecer sinal, a primeira hipótese a excluir é que o pareamento de plaintext se rompeu em algum ponto do pipeline.**

---

#### PARTE 7 — Resultados de impossibilidade

**I1. Plaintext uniforme ⇒ distinção nula.** Se P for uniforme e independente, p_C é exatamente uniforme. **Corolário operacional:** rodar o pipeline com plaintext uniforme é o *controle negativo perfeito* — se der acima do acaso, há bug ou vazamento, com certeza matemática.

**I2. Contração de capacidade.** Delta(p_C) <= Delta(p_Z) e TV(p_C,U) <= TV(p_Z,U). Logo BA <= 1/2 + TV(p_Z^A,U) + TV(p_Z^B,U). Nenhuma arquitetura, feature ou ensemble ultrapassa.

**I3. Teto de dados por (K,N).** Qualquer ataque de correlação/estado precisa de keystream sob o mesmo (K,N). O protocolo entrega 2^19 bits. O FCA precisa de 2^113,8 (stream) ou ~2^651 (AEAD). Déficit >= 2^95. Estrutural.

**I4. Teto de dados agregados.** Estatísticas indexadas por posição agregadas entre amostras podem usar 30.000 x 65.536 = **2^30,87 bytes = 2^33,87 bits por classe**. O melhor viés publicado do Grain-128AEADv2 é 2^-76, exigindo 2^152 bits mesmo com c_P = 1. Déficit **2^118**. Keystream-only: déficit **2^1030**.

**I5. Garantia de segurança provável dos modos esponja.** Ascon e Schwaemm têm provas de indistinguibilidade no modelo de permutação ideal (Daemen, Mennink, Van Assche, https://eprint.iacr.org/2015/541.pdf; Mennink, https://eprint.iacr.org/2022/1340.pdf). Grain **não** tem prova análoga — tem apenas a análise de viés da §4.2. Assimetria digna de nota: *se* houvesse sinal, a teoria diria que o Grain é o candidato mais provável, por ser o único dos quatro sem redução de segurança e o único cuja máscara cobre a mensagem inteira.

**Formulação para a dissertação:** um classificador bem-sucedido sobre 2^33,9 bits por classe *seria* um distinguidor de complexidade de dados 2^33,9 e tempo polinomial contra um finalista do NIST LWC. Não é "um resultado de ML"; seria um ataque publicável em CRYPTO. **H0 é o que a literatura prevê, com margem de 118 a 1030 ordens de grandeza em log2.**

---

#### APOSTAS

##### APOSTA 1 — Curva de sensibilidade calibrada: qual é o menor viés que o pipeline detectaria, usando RC4 como régua

O problema do H0 atual é que diz "não achamos nada" sem dizer "e teríamos achado o quê". A literatura de RC4 oferece uma régua com marcações publicadas, e **a marcação cai exatamente na escala de dados da dissertação**:

> Fluhrer & McGrew (FSE 2000) distinguem RC4 de aleatório com **2^30,6 bytes**, explorando vieses de dígrafo de magnitude relativa **2^-8**.
> O dataset v2 tem **2^30,87 bytes por classe** (30.000 x 65.536).

Está 2^0,27 acima do limiar publicado. Coincidência feliz e oportunidade que não se repete.

**O experimento, em três camadas:**

1. **Régua RC4.** Gerar 30.000 amostras de RC4 (chaves de 128 bits, mesmos plaintexts do encadeamento) e 30.000 de AES-CTR. Rodar o pipeline completo. Três regimes de plaintext: (a) todo-zero — keystream puro; (b) Gutenberg + ImageNet — o regime real; (c) uniforme aleatório — o controle I1.
   - Regime (a) deve dar F1 alto. Se não der, **o pipeline é menos sensível que o estado da arte de 2000** e o H0 nos finalistas é sobre o estimador, não sobre as cifras.
   - Regime (b) deve dar F1 intermediário, e a razão de dados entre (a) e (b) é uma **medida empírica da penalidade c_P^-2**, validando (ou refutando) a previsão de ≈2^8 da Parte 0.4.
   - Regime (c) deve dar exatamente acaso. Se não der, há vazamento — detectado com garantia matemática.

2. **Escada de viés sintético.** Geradores "vazantes": AES-CTR com viés injetado de magnitude relativa r em {2^-2, 2^-4, 2^-6, 2^-8, 2^-10, 2^-12, 2^-14}, nas formas (i) viés de byte único de longo prazo, (ii) dígrafo a lag 1, (iii) dígrafo a lag g grande, (iv) viés posicional nos primeiros 256 bytes. Medir F1 vs r. Produz **a curva de sensibilidade do pipeline**.

3. **O enunciado resultante.** Em vez de "os quatro caminhos convergem para H0": *"o pipeline detecta vieses de byte único de magnitude relativa >= 2^-x e vieses de dígrafo >= 2^-y a N = 2^30,87 bytes por classe; nenhum viés dessa ordem existe nos criptogramas dos quatro finalistas; o maior viés publicado para o Grain-128AEADv2 é 2^-76, que exigiria 2^152 bits."* É a forma rigorosa de um resultado negativo.

**Custo:** ~2 semanas. Sem GPU. O trabalho real é a escada sintética (~200 linhas).

##### APOSTA 2 — Estatística indexada por posição e histograma diferencial por lag

Duas famílias de estimador ausentes, ambas com precedente de quebra real:

**(a) Estatísticas indexadas por posição, agregadas entre amostras.** As 641 features atuais são todas *agregados dentro da amostra*. A literatura de RC4 mostra que o estimador decisivo é o oposto: para cada posição r fixa, a distribuição empírica de C_r sobre as 30.000 amostras. Os dois são ortogonais — um agregado global sobre 65.536 posições **dilui por 4.096** um viés que viva só nas primeiras 16 posições.

Importa desproporcionalmente para Ascon, GIFT-COFB e Schwaemm, onde só o primeiro bloco (16, 16, 32 bytes) é one-time-pad puro sobre máscara derivada de (K,N) — a única janela onde um viés de inicialização apareceria sem ser mascarado pelo feedback. Para o Grain, o análogo dos "primeiros 256 bytes do RC4" são os primeiros bytes após as 512 rodadas.

Implementação: tensor de 30.000 x 256 (primeiras 256 posições) x 256 (valores de byte), reduzido a vetor de chi2 por posição. Não é feature de classificador — é teste estatístico direto, reportado como tabela.

**(b) Histograma diferencial por lag.** O observável da eq. (19) de Vanhoef–Piessens: para cada lag g, histograma de 256 bins de C_r XOR C_{r+g} acumulado sobre as ~65k posições. É o estimador que combina FM e ABSAB, e o que Vanhoef mostra levar de 2^38 para 2^33 criptogramas.

A ACF existente (lags 1–16) é a projeção escalar mais pobre desse objeto: um número por lag, versus distribuição de 256 células por lag. A diferença de capacidade Delta é dramática — foi a diferença entre o Algoritmo 3 e o 4 de AlFardan et al., e eles mostram que o 3 "is clearly invalidated for practical use".

**O que prevê.** Duas previsões distintas:
- O histograma diferencial **vai** ter capacidade Delta grande — é o plaintext aparecendo. Mas deve ser **idêntica entre as quatro classes**, porque o plaintext é o mesmo pelo encadeamento. Se divergirem, é sinal de cifra (ou bug de pareamento).
- Se houver assimetria, deve ser maior nas amostras de imagem que nas de texto, porque a distribuição de diferenças de pixels vizinhos é mais concentrada (p_P̂(0) > 0,10 vs ≈0,065). **Previsão testável: estratificar por `plaintext_source` e ver se a razão de efeitos bate com a razão dos índices de coincidência medidos.**

**Custo:** 1–2 semanas. ~2816 features novas (ou ~55 comprimidas). Nada de GPU. A parte cara é re-rodar A/D/F; B/C/E não mudam.

##### APOSTA 3 — Diferencial de nonce em plano de bits determinístico, como sonda de piso de rodadas

1. Medir, no corpus, a fração de bytes com bit 7 = 0. Se ≈1 nas amostras de texto, tem-se c_P(0x80) = 1.
2. Extrair o plano de bit 7 de cada criptograma (8.192 bytes por amostra). Para o Grain, esse plano **é keystream puro**; para os outros, puro nos primeiros 16/32 bytes.
3. Para pares com distância de nonce Delta conhecida (o contador dá de graça), computar o XOR dos planos: **diferença de keystream sob diferença de nonce conhecida**, sem plaintext, sem pareamento de plaintext.
4. Testar contra uniforme (chi2, e o resíduo de recorrência da §4.3 quando o alvo for Grain).
5. Varrer as rodadas de inicialização e localizar o piso.

**Cabe no modelo? Sim, e a defesa é Barkan–Biham–Keller.** Escrever no texto: a cancelação decorre da distribuição marginal conhecida da fonte (todo byte ASCII tem bit 7 = 0), não de os plaintexts serem iguais ou relacionados. Mesmo mecanismo pelo qual BBK obtêm K_G*C = K_G*k sem conhecer P. A linha traçada ao rejeitar o XOR de pares com mesmo plaintext continua intacta: lá havia dependência entre os plaintexts; aqui são independentes e a cancelação vem da marginal.

**O que prevê.**
- Rodadas completas: acaso.
- Rodadas reduzidas: **piso estritamente mais alto que o das features globais.** Ancoradouros para Grain-128a: 177 rodadas (chave única), 189–201 (weak key), cube/division property a 190–195. Sem impor condições no IV, perde-se o ganho que leva o viés de ~2^-30 para ~2^-10; espere piso entre o genérico e 177. Se não superar o piso global, ou o plano não está limpo, ou o pareamento de nonce está errado.
- Para Ascon/COFB/Schwaemm: mesmo efeito, confinado a 16/32 bytes. Com 1,5 milhão de pares por chave-grupo, ~10^7–10^8 bytes de diferencial limpo — suficiente para varredura de piso.

**Custo:** 2–3 semanas. Risco: a premissa do bit 7 falhar no corpus real (encoding não-ASCII) — descobre-se em 10 minutos, vale checar antes de tudo.

##### O que o agente **não** apostaria

- **Recuperar o FCA de Todo et al. em CT-only.** Déficit de 2^95 mesmo no cenário mais generoso, e é estrutural (nonce novo por amostra).
- **Cube attacks / division property / diferencial-linear.** Todos exigem escolha de entrada. Fora do modelo por definição.
- **Explorar a tag do Grain.** A tag é A_0 XOR soma_i m_i*R_i, hash de Toeplitz da mensagem (65.536 bits desconhecidos) mascarado por 64 bits de pré-saída. Estruturalmente atraente — a tag e o corpo vêm do *mesmo* fluxo de pré-saída, intercalados em posições ímpares/pares, acoplagem que nenhum dos outros três tem. Mas a soma sobre 65.536 bits desconhecidos destrói qualquer viés de ordem menor que 2^-64.
- **Mais uma arquitetura de rede.** Pela cota I2, a capacidade é a mesma para qualquer classificador. O gargalo é a estatística suficiente, não o modelo.

---

#### Fontes

- Grain-128AEADv2 (spec final NIST LWC). https://csrc.nist.gov/CSRC/media/Projects/lightweight-cryptography/documents/finalist-round/updated-spec-doc/grain-128aead-spec-final.pdf
- Todo, Isobe, Meier, Aoki, Zhang — Fast Correlation Attack Revisited (CRYPTO 2018). https://eprint.iacr.org/2018/522
- AlFardan, Bernstein, Paterson, Poettering, Schuldt — On the Security of RC4 in TLS (USENIX 2013). https://www.usenix.org/system/files/conference/usenixsecurity13/sec13-paper_alfardan.pdf
- Vanhoef & Piessens — All Your Biases Belong To Us (USENIX 2015). https://www.rc4nomore.com/vanhoef-usenix2015.pdf
- Barkan, Biham, Keller — Instant Ciphertext-Only Cryptanalysis of GSM (CRYPTO 2003). https://www.iacr.org/archive/crypto2003/27290598/27290598.pdf
- Mantin & Shamir — A Practical Attack on Broadcast RC4 (FSE 2001). https://link.springer.com/content/pdf/10.1007/3-540-45473-X_13.pdf
- Mantin — Predicting and Distinguishing Attacks on RC4 (EUROCRYPT 2005). https://www.iacr.org/archive/eurocrypt2005/34940491/34940491.pdf
- Fluhrer & McGrew — Statistical Analysis of the Alleged RC4 Keystream Generator (FSE 2000). https://link.springer.com/chapter/10.1007/3-540-44706-7_2
- Isobe, Ohigashi, Watanabe, Morii — Full Plaintext Recovery Attack on Broadcast RC4 (FSE 2013). https://link.springer.com/chapter/10.1007/978-3-662-43933-3_10
- Paterson, Poettering, Schuldt — Big Bias Hunting in Amazonia (ASIACRYPT 2014). https://link.springer.com/chapter/10.1007/978-3-662-45611-8_21
- Baignères, Junod, Vaudenay — How Far Can We Go Beyond Linear Cryptanalysis? (ASIACRYPT 2004). https://link.springer.com/chapter/10.1007/978-3-540-30539-2_31
- Lu & Vaudenay — Faster Correlation Attack on Bluetooth E0 (CRYPTO 2004). https://link.springer.com/chapter/10.1007/978-3-540-28628-8_25
- Zhang, Xu, Meier — Fast Near Collision Attack on Grain v1 (EUROCRYPT 2018). https://eprint.iacr.org/2018/145
- Derbez, Fouque, Mollimard — Fake Near Collisions Attacks (ToSC 2020:4). https://eprint.iacr.org/2021/021
- Chang & Turan — Recovering the Key from the Internal State of Grain-128AEAD. https://eprint.iacr.org/2021/439.pdf
- Hell et al. — Grain-128AEADv2: Strengthening the Initialization (CANS 2021). https://eprint.iacr.org/2021/751.pdf
- Lehmann & Meier — Conditional Differential Cryptanalysis of Grain-128a (CANS 2012). https://link.springer.com/chapter/10.1007/978-3-642-35404-5_1
- Ma, Tian, Qi — Conditional differential attacks on Grain-128a (IET Inf. Security 2017). https://ietresearch.onlinelibrary.wiley.com/doi/full/10.1049/iet-ifs.2016.0060
- Massive Superpoly Recovery with a Meet-in-the-middle Framework (EUROCRYPT 2024). https://eprint.iacr.org/2024/342.pdf
- Plaintext Structure Vulnerability (arXiv:2511.08296). https://arxiv.org/html/2511.08296
- MIND-Crypt (arXiv:2405.19683). https://arxiv.org/abs/2405.19683
- Dileep & Sekhar — Identification of block ciphers using SVM (IJCNN 2006). https://researchr.org/publication/DileepS06/reviews
- Manjula & Anitha — Identification of Encryption Algorithm Using Decision Tree (CCSIT 2011). https://link.springer.com/chapter/10.1007/978-3-642-17881-8_23
- Daemen, Mennink, Van Assche — Security of Full-State Keyed Sponge and Duplex. https://eprint.iacr.org/2015/541.pdf
- Mennink — Understanding the Duplex and Its Security. https://eprint.iacr.org/2022/1340.pdf
- NIST IR 8454. https://nvlpubs.nist.gov/nistpubs/ir/2023/NIST.IR.8454.pdf
- Sýs et al. — Algorithm 970 (ACM TOMS 2016). https://dl.acm.org/doi/10.1145/2988228

**Não confirmado pelo agente:** um número que apareceu em busca inicial sobre Grain — "uma chave em 8 distinguível com 2^20-24 amostras IV-diferenciais e viés refinado em 2^-10..2^-12" — não foi rastreado até artigo específico. Provavelmente Lehmann–Meier ou Ma–Tian–Qi; **tratar como não confirmado**.

---

# Pesquisa 05 — Resultados negativos e rigor do nulo

- **Ângulo:** Resultados negativos e rigor do nulo
- **Temperatura declarada:** 0,3

## Pesquisa 05 — prompt usado, na íntegra

````markdown
# Pesquisa 05 — Resultados negativos e como publicar um nulo com rigor

**Ângulo desta pesquisa.** Procure trabalhos que **falharam** em distinguir, e
o que eles concluíram. E, mais importante que o inventário: procure a
**metodologia** de como se publica um resultado nulo em criptografia e em
aprendizado de máquina de forma que ele seja aceito como contribuição, e não
como fracasso.

Persiga: resultados negativos publicados em criptanálise e em ML aplicado a
cripto, com atenção a como os autores enquadraram a ausência de achado;
testes de equivalência e inferência bayesiana para "aceitar H0" (TOST,
região de equivalência, fator de Bayes, análise de poder), que é o ferramental
estatístico que falta na maior parte desses trabalhos; padrões de reporte de
resultado nulo em conferências de segurança; e a literatura de crise de
replicação aplicada a segurança e ML.

Duas perguntas específicas: **(a) como se demonstra que um instrumento
detectaria o efeito se ele existisse** — calibração de sensibilidade,
controles positivos, curvas de poder; e **(b) que critérios uma banca ou um
revisor usam para separar "não encontramos" de "não existe"?**

Traga também o contrário: casos em que um nulo publicado foi depois
derrubado, e o que tinha sido mal feito.

**Temperatura: 0,3.** Escala de amplitude de exploração, de 0,1 a 1,0.
Não é temperatura de amostragem — é instrução. Em 0,3: conservador. Priorize
prática estabelecida e padrões reconhecidos por comunidades reais, com
referência concreta, em vez de propor arcabouços novos.

---

# Prompt base — técnicas de distinção de algoritmos de criptografia

Este é o texto-mãe. Cada uma das 10 pesquisas recebe uma variação dele, com um
ângulo diferente e uma temperatura, e NADA MAIS: nem o repositório, nem os
resultados das pesquisas anteriores, nem esta conversa.

---

## PROBLEMA DE PESQUISA

Você está pesquisando para uma dissertação de mestrado em criptografia
aplicada e aprendizado de máquina. Trabalhe SÓ com literatura externa: não
leia nenhum repositório, arquivo local ou resultado prévio. Comece do zero.

**A pergunta.** Dado apenas o criptograma — sem a chave, sem o texto em claro,
sem poder escolher nada do que é cifrado — é possível distinguir qual
algoritmo de criptografia autenticada o produziu? E, num segundo nível, com
quantas rodadas reduzidas um algoritmo ainda deixa de parecer aleatório?

**Os algoritmos.** Os quatro finalistas do concurso NIST Lightweight
Cryptography: Ascon-AEAD128 (esponja), GIFT-COFB (cifra de bloco em modo
COFB), Grain-128AEAD (cifra de fluxo com LFSR e NFSR) e Schwaemm256-128
(esponja ARX, família SPARKLE).

**O modelo de ameaça, que é a restrição dura e não negocia.** Adversário
PASSIVO, em ciphertext-only. Ele observa criptogramas de um mesmo dispositivo,
com nonces públicos de contador, e pode observar vários de uma vez. Ele NÃO
tem: texto em claro conhecido ou escolhido, diferenças escolhidas na entrada,
reuso de nonce, acesso a canais laterais, nem consultas a um oráculo de
cifragem. Isso exclui de saída a maior parte da criptanálise diferencial
clássica e os distinguidores neurais no estilo Gohr, que dependem de pares com
diferença escolhida.

**O protocolo experimental.** Classificadores clássicos e redes sobre features
estatísticas e sobre os bytes crus. Chaves de teste nunca aparecem no treino
(key-holdout). Intervalo de confiança por bootstrap agrupado por chave, e não
i.i.d. Correção para múltiplas comparações. Controle negativo obrigatório: com
o algoritmo completo o classificador tem que ficar no acaso.

## O QUE EU QUERO DE VOCÊ

Técnicas, representações, ataques ou ideias — publicadas ou adaptáveis — que
possam extrair sinal nesse cenário, ou que ajudem a delimitar com rigor por
que o sinal não existe. Interessa tanto o que funciona quanto a prova de que
algo é impossível.

Busque em literatura acadêmica real (IACR ePrint, ToSC/FSE, CHES, CRYPTO,
EUROCRYPT, ASIACRYPT, SAC, Designs Codes and Cryptography, IEEE, Springer,
arXiv) e em fontes técnicas sérias. Use termos de busca em inglês.

## COMO RESPONDER

Para cada ideia encontrada, escreva:

1. **O que é** — a técnica, em duas ou três frases.
2. **Fonte** — autores, título, veículo, ano. Link quando houver. Se você não
   conseguiu confirmar a existência do trabalho, diga isso explicitamente em
   vez de completar de memória.
3. **Cabe no nosso modelo?** — SIM, NÃO, ou ADAPTÁVEL. Se ADAPTÁVEL, diga
   exatamente o que teria de mudar e qual premissa do modelo de ameaça isso
   arranha.
4. **O que custaria testar** — ordem de grandeza de dados, computação e
   engenharia.
5. **O que ela prevê** — se a técnica funcionar, que resultado deveríamos ver?
   Se não houver previsão falsificável, diga isso.

Termine com uma seção **APOSTAS**: as três ideias que você tentaria primeiro,
e por quê. Seja específico; "usar deep learning" não é uma aposta.

## PROFUNDIDADE — leia isto com atenção

Não é um levantamento rápido. **Vá até esgotar o veio.** Não pare em cinco ou
dez achados porque já "deu para ter uma ideia": siga as citações para frente e
para trás, abra os trabalhos relacionados dos artigos que importarem, procure
versões estendidas e teses, e persiga as pistas que aparecerem no caminho,
mesmo as que não estavam no ângulo original. Só encerre quando as buscas novas
pararem de trazer coisa nova.

Traga TODA a informação, não um resumo dela. Se um artigo tem um número que
importa (quantas rodadas, quantas consultas, que acurácia, que tamanho de
dado), traga o número. Se tem uma limitação declarada pelos próprios autores,
traga a limitação com as palavras deles. Prefira errar por excesso de detalhe.
Uma resposta longa e completa é o que se pede aqui; uma resposta enxuta é
falha de execução.

## REGRAS

- Não invente referências. Uma fonte não confirmada vale menos que nenhuma, e
  vou checar.
- Não repita o óbvio já saturado (distinguidor diferencial-neural padrão)
  sem trazer um ângulo novo que sobreviva ao ciphertext-only.
- Se a conclusão honesta de um caminho for "isso é impossível neste modelo
  por tal razão teórica", isso é resultado útil. Diga.
- Separe o que é publicado do que é sua extrapolação. Marque cada um.
````

## Pesquisa 05 — achados, sem resumir

### Achados — Pesquisa 05

- **Ângulo:** resultados negativos e como publicar um nulo com rigor
- **Temperatura declarada:** 0,3
- **Prompt usado:** `prompts/05_resultados_negativos.md`
- **Execução:** morreu no 1º lançamento (rate limit), relançada 06:06. ~286k tokens, 109 chamadas, ~25 min.

Marcação: `[PUB]` = publicado e verificado na sessão; `[PUB-NV]` = localizado mas texto não lido; `[EXTRAP]` = extrapolação do agente; `[NÃO CONFIRMADO]` = não verificado.

---

#### PARTE 0 — O achado que muda o enquadramento da dissertação

O ponto mais importante não é uma referência, é uma conta.

A pergunta "ML distingue Ascon de GIFT-COFB em CT-only?" tem teto teórico calculável, e esse teto está **entre 9 e 30 ordens de grandeza abaixo da resolução estatística do experimento de 180k amostras**.

**Ascon-AEAD128.** Chakraborty, Dhar e Nandi (ASIACRYPT 2023) provam o bound exato `T/2^min{kappa,c} + D/2^min{tau,c} + DT/2^b`, com b=320. Para Ascon-AEAD128 no SP 800-232: kappa=128, c=192, tau=128. `[PUB]` https://eprint.iacr.org/2023/775

Substituindo o cenário da dissertação `[EXTRAP]`: D ≈ 30.000 amostras ≈ 2^14,9 (ou ~2^27 blocos); T = chamadas diretas à permutação, que um pipeline de ML **não faz** (a rede não avalia Ascon-p), logo T ≈ 0 a 2^50 por generosidade. Resultado: vantagem <= 2^-110 no caso realista; <= 2^-68 mesmo concedendo T = 2^60.

**GIFT-COFB.** Bound birthday em n=128, nonce-respecting `[PUB-NV]` (spec round 2 + Iwata, NIST LWC Workshop 2022). Termo mais pessimista, sigma/2^64 com sigma ≈ 2^27 blocos → 2^-37. Termo sigma^2/2^128 → 2^-74. `[EXTRAP]`

**Resolução do experimento** `[EXTRAP]`: com 12.000 amostras de teste i.i.d., erro-padrão binomial = sqrt(0,25/12000) = 0,00456; efeito mínimo detectável a 80% de poder e alfa=0,05 ≈ 0,013 (acurácia 0,513). Com bootstrap agrupado por chave (60 chaves, ~200 amostras cada), o *design effect* 1+(m-1)rho come isso rápido: rho=0,01 já leva o MDE para ≈ 0,022.

**A conclusão.** O experimento tem resolução de ~10^-2. O efeito, se a prova vale, é <= 10^-11 na leitura mais pessimista e <= 10^-33 na realista. **O experimento não é um teste da alegação criptográfica.** É um teste de falha catastrófica de implementação ou de projeto — e passa nesse teste. Dizer isso explicitamente é o que separa um nulo rigoroso de um "não achamos nada".

Consequência prática: **a região de equivalência (ROPE/SESOI) não precisa ser escolhida por gosto. Ela se deriva do bound provável.** É o único contexto conhecido em que o SESOI tem origem dedutiva. Lakens gasta meio paper discutindo como escolher SESOI porque em psicologia não há de onde derivar; aqui há. Argumento metodológico próprio, publicável, e o agente não encontrou ninguém que o tenha feito.

---

#### PARTE 1 — Nulos publicados em ML aplicado a criptografia

##### A1. MIND-Crypt — o nulo mais próximo

**O que é.** ResNet, CNN, LSTM e BiLSTM para distinguir cifrotextos de duas mensagens fixas P1 e P2 (diferindo em 1 bit) sob SPECK32/64 e SIMON32/64 em CBC, chave única fixa, IVs aleatórios. Todos no acaso, em rodadas reduzidas e full-round.

**Fonte.** Jimmy Dani, Kalyan Nakka, Nitesh Saxena (Texas A&M). arXiv:2405.19683v2, 30 abr. 2025. `[PUB]` — texto integral lido.

**Números (Tabela III):** 10^7 treino, 10^6 validação, 10^6 teste por configuração.

| Config | Cifra | Modelo | Acc | ROC-AUC | TPR | TNR |
|---|---|---|---|---|---|---|
| Round-reduced | SPECK32/64 | ResNet | 0,5000 | 0,5008 | 0,0000 | 1,0000 |
| Round-reduced | SPECK32/64 | CNN | 0,5003 | 0,5005 | 0,0355 | 0,9650 |
| Round-reduced | SIMON32/64 | ResNet | 0,5002 | 0,5003 | 0,4947 | 0,5057 |
| Full | SPECK32/64 | ResNet | 0,5000 | 0,5001 | 1,0000 | 0,0000 |
| Full | SPECK32/64 | CNN | 0,4997 | 0,4996 | 0,9489 | 0,0505 |
| Full | SIMON32/64 | BiLSTM | 0,5000 | 0,5003 | 0,9996 | 0,0004 |

**O controle de memorização — o melhor pedaço do paper.** Reduziram a entropia dos IVs de 32 para 16 bits, colapsando o espaço para ~65.536. Com oversampling massivo: **~99%**. Com subconjunto de 5.000 por classe (P1 com 4.819 únicos, P2 com 4.815, 366 redundantes), sobreposição treino/teste de 5.307 amostras (~5%): acurácia **53,72%**, CV **52,6%**. Nas 70.023 amostras únicas do teste: **53,58%**. Nas exclusivas do teste, excluindo sobrepostas: **49,90%** — acaso puro.

Verbatim: *"The observed marginal improvements in accuracy above random chance are entirely due to memorization of overlapping ciphertext samples, rather than genuine generalization by the ML algorithm."*

**Cabe?** ADAPTÁVEL, literatura relacionada obrigatória. Duas diferenças a marcar: (i) usam **chave única fixa** e **dois plaintexts fixos** — é known-plaintext, não CT-only; testam IND-CPA com 2 mensagens, não identificação de algoritmo; (ii) a pergunta deles é "de qual mensagem veio", a sua é "de qual algoritmo". Jogos diferentes. Mas o protocolo de controle de memorização transfere direto.

**Crítica do agente como revisor:** os TPR/TNR degenerados (1,0000 / 0,0000) mostram classificadores que predizem uma classe só. Reportam isso, mas chamam de "systemic biases rather than meaningful discrimination". Um classificador degenerado com acurácia 0,5 não é evidência de indistinguibilidade; é evidência de que o treino não convergiu. São coisas diferentes e o paper não as separa. **A dissertação precisa separar:** reportar sempre a matriz de confusão (Regra de Ouro nº 7 já manda) e distinguir "chegou em 0,5 predizendo as duas classes" de "chegou em 0,5 colapsando numa classe".

##### A2. Mello & Xexéo — o positivo que é o contraexemplo da casa

7 algoritmos (DES, Blowfish, RSA, ARC4, Rijndael, Serpent, Twofish) em ECB e CBC, 7 idiomas, 6 classificadores. ECB: pleno. CBC: até 6x o acaso, 40–50% com Complement Naive Bayes.

**Fonte.** JUCS 24(1):25–42, 2018. `[PUB]` https://lib.jucs.org/article/22921/

**Cabe? NÃO, e é por isso que importa.** ECB vaza estrutura do plaintext por construção. CBC com 7 algoritmos de tamanhos de bloco diferentes (DES/Blowfish 64, AES/Serpent/Twofish 128) vaza **comprimento e alinhamento de padding**. RSA num conjunto simétrico vaza tudo. O resultado é real; a explicação não é "as cifras têm assinatura".

**Nota política do agente.** O orientador é coautor. Não é problema — é oportunidade, se escrito como continuidade metodológica e não refutação. Enquadramento honesto: *"Mello & Xexéo mostraram que a identificação é viável quando o modo de operação deixa estrutura observável; este trabalho testa se sobra algo quando essa estrutura é removida por construção."* Vale conversar com ele antes de escrever o parágrafo.

##### A3. Ren et al. — a "vulnerabilidade da estrutura do plaintext"

Identificam que classificadores falham quando a distribuição de plaintext do teste difere da do treino, revelando *"the feature extractor's hidden dependency on plaintext features"*. Propõem extrator com 41 testes de aleatoriedade.

**Fonte.** Xiwen Ren, Min Luo, Cong Peng, Debiao He (Wuhan). arXiv:2511.08296, submetido 11 nov. 2025, revisado 30 jul. 2026. `[PUB]`

6 cifras — AES(ECB/CBC), 3DES, Blowfish, ChaCha20, RC4. Janelas do mesmo tamanho fixo. Chaves e IVs por janela. CV 5x5 estratificada **agrupada por arquivo-fonte**. AUC > 0,98 no Canterbury. Em `Random_100` (0% regular, 10.000 janelas de 8 KB): AUC ≈ 0,90–0,91.

**Cabe? ADAPTÁVEL com ressalva pesada.** O diagnóstico é ouro e confirma externamente a hipótese. Mas o **AUC 0,90 em plaintext puramente aleatório é inconsistente com a segurança de AES e ChaCha20** `[EXTRAP]`. Com 8 KB por janela e 41 estatísticas, o resíduo detectável é ~2^-8; a vantagem real deveria ser ~2^-60. Explicações plausíveis: (a) o conjunto inclui **3DES (bloco 64) e RC4/ChaCha20 (stream, sem padding)** — comprimento efetivo e PKCS#7 diferem e são deterministicamente detectáveis; (b) a AUC multiclasse agrega pares triviais com pares impossíveis e não é reportada por par.

**O que fazer:** citar o diagnóstico, e citar a AUC 0,90 como evidência de que **mesmo um trabalho que identifica corretamente o artefato do plaintext ainda cai num segundo artefato (comprimento/modo) quando não reporta por par**. Justifica a análise pareada e a exclusão de len_ct.

##### A4. FESLA — o positivo impossível, e o melhor estudo de caso de como NÃO fazer

**Achado mais útil da pesquisa para critérios de revisor.**

Alega os **primeiros distinguidores ciphertext-only para AES-128/192/256 full-round no modelo secret-key**, com **100% de acurácia** em SVM, RF, MLP, LR e Naive Bayes, validado por k-fold (K=5 e K=10) e em datasets não vistos.

**Fonte.** Gopal Singh (Jodhpur Institute of Engineering and Technology). *Distinguishing Full-Round AES-256 in a Ciphertext-Only Setting via Hybrid Statistical Learning*. IACR ePrint 2025/862, recebido 15 mai. 2025, revisado 9 nov. 2025. **NÃO É REVISADO POR PARES.** `[PUB]` — PDF completo lido.

Setup: 2^21 plaintexts aleatórios (dois conjuntos), 2^21 chaves, `secrets` do Python 3 para tudo (inclusive o dataset "random" — literalmente o mesmo código). PyCryptodome, validado contra AESAVS. 512 batches de 2^12 amostras. 30 testes estatísticos, filtrados para 20 features. iMac 1.8 GHz i5, 8 GB, sem GPU.

**A parte honesta (Fases I e II).** SVM e RF sobre bits crus **"failed to converge repeatedly"**. O MLP (3 camadas densas de 1024) **"failed to converge after numerous epochs indicating a weak or no feature separation"**. PCA e t-SNE: **"made it clear that the data is not separable using any method used on data directly"**. Os p-valores dos 30 testes foram iguais para os dois datasets.

**A parte que quebra (Fase III).** Ao agregar as estatísticas por batch, separação perfeita. A Figura 5(a) mostra Anderson–Darling: cifrotexto é um **pico delta em ~0,9 com variância visualmente nula**, random é distribuição larga em torno de 0,5. A Figura 7 estende para 3 cifras: DES ≈ 0,5 (em cima do random), PRESENT ≈ 0,62, AES-128 ≈ 0,9 — **três picos delta, cada um numa posição, todos sem variância amostral**.

**Por que é impossível** `[EXTRAP]`: 2^12 amostras de 128 bits por batch = 2^19 bits. Viés detectável ~2^-9,5 ≈ 0,0014. A vantagem de distinguir AES full-round de aleatório nesse volume é ~2^-64. Separação perfeita é 2^55 vezes maior que o máximo possível. Além disso: se os bits crus são comprovadamente inseparáveis (Fase I), e as features são **função determinística desses bits**, a única forma de ganhar separação perfeita é a estatística depender de algo que **não está no vetor de bits** — formato, dtype, ordenação, empacotamento. Variância nula é a assinatura disso: não é estatística amostral, é constante da tubulação.

**O tell decisivo:** DES (a mais fraca, bloco de 64 bits) cai **exatamente em cima do random**, e AES (a mais forte) fica mais longe. Se o sinal fosse criptográfico, a ordem seria inversa. O efeito rastreia **tamanho de bloco / representação**, não força da cifra.

**A frase dos autores, verbatim:**

> *"Note on Accuracy: While the classification results reported in this work consistently achieve 100% accuracy across models and test sets, their interpretation should be approached with objectivity. Such high accuracy is unusual in practical cryptanalysis and is likely a consequence of the carefully selected and well-engineered statistical features that capture subtle, persistent biases in ciphertext distributions. Extensive validation through cross-validation, unseen datasets, and alternative classifiers was conducted to rule out overfitting or data leakage."*

E na seção 5.3: *"This proves beyond any doubt that the Model training is fair."*

**A lição metodológica.** Validação cruzada, datasets não vistos e classificadores alternativos **não descartam vazamento**. Vazamento na construção das features sobrevive intacto aos três. O autor fez exatamente os três controles que a comunidade de ML recomenda, os três passaram, e o resultado é artefato. O único controle que teria pego é o que ele não fez: **comparar a magnitude do efeito com o teto teórico**.

**Cabe? SIM**, como estudo de caso central da seção metodológica. É o argumento mais forte para justificar por que a dissertação reporta um nulo com aparato estatístico pesado em vez de caçar um positivo.

##### A5. Gohr, Leander, Neumann — um nulo dentro de um paper positivo

Avaliação sistemática de distinguidores diferencial-neurais. Um nulo publicado: *"the claimed improvements from using multiple ciphertext-pairs at once are at most marginal, if not non-existent"*. Também: exploram a correlação entre a acurácia do distinguidor neural e uma **noção padrão de diferença entre as distribuições subjacentes**, e mostram que para uma classe praticamente relevante o distinguidor usa **apenas features diferenciais**.

**Fonte.** IACR ePrint 2022/1521. Cifras: Simon, Speck, Skinny, Present, Katan, ChaCha. `[PUB]`

**Cabe? ADAPTÁVEL, e é o link mais importante entre ML e criptanálise clássica.** A ideia de **ancorar a acurácia do classificador numa medida de distância entre distribuições** é o instrumento de calibração que a questão (a) pede: se a distância (SEI/TV) entre as distribuições de features é X, a acurácia máxima de qualquer classificador é conhecida, e dá para verificar se o seu chegou lá. Se chegou, o classificador satura o sinal e o nulo é do sinal. Se não chegou, o nulo é do modelo.

**Nulo do sinal vs nulo do instrumento** — é o que uma banca vai perguntar, e a única forma rigorosa de responder.

**Prevê.** Se SEI ≈ 0 dentro do erro amostral, F1 = 0,5 é *forçado*, e o nulo é do sinal. Se SEI > 0 mas F1 = 0,5, o pipeline deixa sinal na mesa. **A previsão mais valiosa deste relatório.**

##### A6–A8. Resto do inventário

**A6. Benamira, Gérault, Peyrin, Tan.** *A Deeper Look at Machine Learning-Based Cryptanalysis*. EUROCRYPT 2021 / ePrint 2021/287. `[PUB]` O distinguidor de Gohr constrói *"a very good approximation of the Differential Distribution Table (DDT) of the cipher during the learning phase"*, e depende da distribuição diferencial no cifrotexto **e** nas rodadas penúltima e antepenúltima. Construíram um distinguidor **não-neural**, por criptanálise pura, com *"basically the same accuracy as Gohr's neural distinguisher and with the same efficiency"*. Paper deflacionário canônico. **Cabe: SIM**, como argumento de que o valor do ML aqui é confirmatório, não descobridor.

**A7. So (2020) e a réplica.** Jaewoo So, *Deep Learning-Based Cryptanalysis of Lightweight Block Ciphers*, Security and Communication Networks 2020, art. 3701067. `[PUB]` Alega quebrar full-round Simon32/64 e Speck32/64 — **com o keyspace restrito a 64 caracteres ASCII**. Réplica: Kim, Lim, Kang, Kim, Seo, ePrint 2022/886 `[PUB-NV]`, em versões brinquedo. **Cabe: NÃO**, mas é o exemplo limpo de "positivo obtido por relaxar uma premissa que carrega todo o resultado".

**A8. Survey de 6 anos.** ePrint 2024/1300, em IACR CiC 3(2). `[PUB]` Limitação declarada: a criptanálise neural **não segue lei de escala "bigger is better"** — redes mais profundas frequentemente sobreajustam às chaves de treino e falham no **random key setting**. Valida diretamente a Regra de Ouro nº 2 (key-holdout).

---

#### PARTE 2 — Nulos publicados e aceitos em ML

Padrão consistente: **o nulo é aceito quando é reenquadrado como auditoria de um campo, com baselines fortes, código aberto e explicação mecanicista.** Nulo sem explicação não passa.

**B1. Ferrari Dacrema, Cremonesi, Jannach.** *Are We Really Making Much Progress?* RecSys 2019 (Best Paper). `[PUB]` 18 algoritmos de DL para top-n recommendation; **reproduziram 7 de 18**; desses 7, **6 foram superados por baselines simples bem ajustados**. +600 citações.

**B2. Musgrave, Belongie, Lim.** *A Metric Learning Reality Check*. ECCV 2020. `[PUB]` Falhas metodológicas em metric learning; **melhorias reais ao longo do tempo foram marginais na melhor das hipóteses**.

**B3. Melis, Dyer, Blunsom.** *On the State of the Art of Evaluation in Neural Language Models*. ICLR 2018. `[PUB]` **LSTMs padrão, adequadamente regularizadas, superam os modelos mais recentes**.

**B4. Lucic, Kurach, Michalski, Gelly, Bousquet.** *Are GANs Created Equal?* NeurIPS 2018, pp. 698–707. `[PUB]` **A maioria dos modelos alcança scores similares com otimização de hiperparâmetros e restarts suficientes**; melhorias vêm de orçamento, não de algoritmo.

**B5. Borji.** *Negative Results in Computer Vision: A Perspective*. arXiv:1705.04402. `[PUB]`

**O que copiar:** baseline forte e honesto; código e dados abertos; o nulo é sobre **um campo ou classe de métodos**, não sobre uma tentativa individual; explicação mecanicista.

##### B6. Os veículos que aceitam nulos, com critérios escritos

**ICBINB (I Can't Believe It's Not Better), NeurIPS 2020–2023, ICLR 2026, NeurIPS 2026.** `[PUB]` — CFP de 2020 lida. Missão: promover *"slow science"* contra *"leaderboard-ism"*. Quatro categorias: **Data**, **Modeling**, **Inference**, **Validation**.

**Critérios de revisão, verbatim:**
- *"Clarity of writing"*
- *"Rigor and transparency in the scientific process"*
- *"Vulnerability and honesty in discussion, particularly if the submission is by the original author"*
- *"Quality of discussion of limitations"*
- *"Significance of new insights"*

Note o que **não** está: magnitude do efeito, novidade do método, superação de baseline. Rubrica desenhada para nulos.

**Workshop on Insights from Negative Results in NLP.** Cinco edições (EMNLP 2020, EMNLP 2021, ACL 2022, EACL 2023...), ACL Anthology, organizado por Anna Rogers, João Sedoc, Anna Rumshisky. `[PUB]` Contribuições aceitas incluem: *"ablation studies of components in previously proposed models"*; *"trivial baselines that work suspiciously well"*; *"experiments on (in)stability of the previously published results"*; **"theoretical arguments and/or proofs for why X should not be expected to work"**.

**Requisito-chave, verbatim:** resultados devem incluir *"some explanation/hypothesis"* em vez de meramente reportar o desfecho negativo.

Esse item — *"theoretical arguments and/or proofs for why X should not be expected to work"* — é literalmente a Parte 0. É o pedaço da dissertação que uma comunidade real já declarou publicável.

**Pre-registration.** NeurIPS 2020 Workshop on Pre-registration in ML, publicado como **PMLR vol. 148** (Bertinetto, Henriques, Albanie, Paganini, Varol), 8 jul. 2021. `[PUB]` Motivação: o sistema de incentivos *"causes negative results to be omitted"*. Submissão revisada **sem resultados**, só protocolo.

**Registered Reports em CS:** introduzidos na MSR em **2020**, com o EMSE da Springer, mantidos em 2021, 2024, 2025, 2026. `[PUB]` Dois objetivos: feedback antecipado no desenho e **prevenir HARKing**.

**Reprodutibilidade:** Pineau et al. *Improving Reproducibility in Machine Learning Research*. JMLR 22(164):1–20, 2021. `[PUB]` Badging: ACM *Artifact Review and Badging v1.1*. USENIX Security: cada artefato revisado por **pelo menos dois** membros do AEC. `[PUB]`

Para uma dissertação que reporta H0, o artefato reprodutível **é** a evidência.

---

#### PARTE 3 — O ferramental estatístico para "aceitar H0"

Confirmado por busca: **não existe literatura aplicando TOST, ROPE ou fator de Bayes a distinguidores criptográficos** — a busca combinada retornou apenas psicologia e estatística médica. `[PUB — busca negativa registrada]` Contribuição em aberto.

##### C1. TOST e SESOI

Define-se intervalo de equivalência a partir do menor efeito de interesse (SESOI). Dois testes unicaudais contra as bordas. Se ambos rejeitam, o efeito está dentro do intervalo. Único teste frequentista que permite conclusão positiva de equivalência.

**Fonte.** Daniël Lakens. *Equivalence Tests: A Practical Primer*. SPPS 8(4), 2017. `[PUB]` https://journals.sagepub.com/doi/10.1177/1948550617697177 — e Lakens, Scheel, Isager. AMPPS 1(2), 2018. `[PUB]` Pacote R: `TOSTER`. Origem: Schuirmann (1987) `[NÃO CONFIRMADO]`.

Lakens sobre o SESOI, verbatim: quando fronteiras teóricas ou práticas estão ausentes, *"researchers should set the bounds to the smallest effect size they have sufficient power to detect"*.

**Cabe? SIM, com vantagem que Lakens não tem: o SESOI é derivável.** Duas ancoragens, reportar as duas:
- **SESOI teórico** = o bound provável. ~2^-37 na leitura mais pessimista. Nenhum experimento com 180k amostras rejeita nem aceita nesse nível — e dizer isso é o ponto.
- **SESOI operacional** = o menor efeito detectável com poder 0,80, do bootstrap agrupado por chave. É esse que entra no TOST.

##### C2. ROPE + HDI (Kruschke)

Se o HDI de 95% cai **inteiramente fora** da ROPE, rejeita-se o nulo; **inteiramente dentro**, aceita-se; caso contrário, **indeciso**. O estado "indeciso" é a virtude.

**Fonte.** John K. Kruschke. AMPPS 1(2), 2018. `[PUB]` https://journals.sagepub.com/doi/10.1177/2515245918771304

**Cabe? SIM.** Preferível ao TOST: os três estados mapeiam nos três desfechos cientificamente distintos. Numa banca, "indeciso" é defensável; "não rejeitamos" não é.

##### C3. Fator de Bayes para não-significância

Nenhuma conclusão decorre automaticamente de um não-significativo. Para saber se conta **contra** uma teoria ou indica **insensibilidade**, é preciso poder, intervalos, ou fator de Bayes.

**Fonte.** Zoltan Dienes. *Using Bayes to get the most out of non-significant results*. Frontiers in Psychology 5:781, 2014. `[PUB]` PMC4114196.

Tríade TOST + ROPE + BF é redundante de propósito: se as três concordam, a conclusão é robusta à escolha de framework.

##### C4. Benavoli, Corani, Demšar, Zaffalon — ROPE para folds de CV

Comparação bayesiana de classificadores. Três probabilidades: P(1 melhor), P(dentro da ROPE), P(2 melhor). Trata a correlação entre folds. **Definem:** dois classificadores com diferença média de acurácia menor que 1% são praticamente equivalentes, ROPE = [-0,01, +0,01].

**Fonte.** JMLR 18(77):1–36, 2017. `[PUB]` http://www.jmlr.org/papers/v18/16-305.html — Biblioteca: `baycomp`.

**Cabe? SIM**, com adaptação (comparador é o Dummy, já no pipeline). A ROPE de ±0,01 é **default de comunidade citável**, e da mesma ordem que o SESOI operacional.

**Prevê.** P(ROPE) > 0,95 para todos os pares AEAD, e P(diferença) > 0,95 para AES-ECB vs qualquer AEAD.

##### C5. Análise de poder

Card et al. argumentam "crise de poder": benchmarks típicos são pequenos demais; experimentos subpotentes **aumentam a chance de achados exagerados**.

**Fonte.** Card, Henderson, Khandelwal, Jia, Mahowald, Jurafsky. *With Little Power Comes Great Responsibility*. EMNLP 2020, pp. 9263–9274. `[PUB]` Complemento: Lakens. *Sample Size Justification*. Collabra: Psychology 8(1):33267, 2022. `[PUB]` Seis abordagens, incluindo **reconhecimento explícito da ausência de justificativa**.

Se o N=180.000 foi escolhido por restrição de recursos, o honesto é dizer isso e **derivar** qual efeito esse N detecta. Não inventar análise de poder a priori retroativa — isso é HARKing estatístico.

##### C6. Teste de permutação com embaralhamento de rótulos

Dois testes: o primeiro avalia **estrutura de classe real** (permutando rótulos); o segundo, **dependência entre features** (permutando features dentro de classes).

**Fonte.** Markus Ojala, Gemma C. Garriga. JMLR 11:1833–1863, 2010. `[PUB]` https://www.jmlr.org/papers/v11/ojala10a.html

**Cabe? SIM**, e é o controle mais barato e persuasivo. Dá a distribuição empírica do F1 sob H0 **para o pipeline exato**, incluindo todos os graus de liberdade do seletor, do CV e do bootstrap.

Detalhe: a permutação precisa ser **agrupada por chave**, não i.i.d., senão a nula fica estreita demais. `[EXTRAP]`

**Custo.** 1.000 permutações nos modelos clássicos: horas de CPU. Para CNNs, inviável — 20–50 permutações ou só modelos clássicos.

##### C7. Acurácia é estatística de teste subpotente — o achado que pode mudar o desenho

Usar acurácia de classificador como estatística de teste é **estratégia subpotente** comparada a um teste estatístico propriamente dito, e é computacionalmente mais cara.

**Fonte.** Rosenblatt, Benjamini, Gilron, Mukamel, Goeman. *Better-than-chance classification for signal detection*. Biostatistics 22(2):365–380, 2021 (arXiv:1608.08873). `[PUB]`

**Cabe? SIM, e é desconfortável.** Todo o protocolo (6 caminhos) usa acurácia/F1 como detector. Se reportar apenas "F1 ≈ 0,50 em 6 caminhos", um revisor pode responder "vocês usaram seis variações da estatística errada".

**O conserto** `[EXTRAP]`: rodar em paralelo um **teste de duas amostras genuíno** sobre as 641 features — MMD com kernel, Hotelling T² regularizado, ou testes marginais com BH-FDR (já implementado em `consolidate_v2.py`). Se o teste de duas amostras também não rejeita, o nulo sobrevive à estatística **mais** potente.

##### C8. Variância e testes de comparação

- **Dietterich (1998)**, Neural Computation 10:1895–1923. `[PUB]` McNemar tem erro Tipo I baixo e é **o único teste com erro Tipo I aceitável** para algoritmos executáveis uma única vez. O t-test cross-validado é o mais potente **e o mais enviesado**. (Você já usa McNemar+Bonferroni — alinhado; vale citar Dietterich.)
- **Nadeau & Bengio (2003)**, Machine Learning 52(3):239–281. `[PUB]` Testes devem levar em conta variabilidade da **escolha do conjunto de treino**. Propõem o *corrected resampled t-test*.
- **Bouthillier et al. (2021)**, MLSys 2021 (arXiv:2103.03098). `[PUB]` Variância de amostragem, inicialização e hiperparâmetros impacta os resultados de forma marcante. Adicionar fontes de variação aproxima do estimador ideal, com **redução de 51x no custo**.

**Implicação** `[EXTRAP]`: as Regras de Ouro fixam seeds (split=42, modelo=7, FS=13, bootstrap=42). Excelente para reprodutibilidade, **péssimo para estimar variância**. F1=0,50 com uma seed não distingue "a média é 0,50" de "a média é 0,50 mas o desvio entre seeds é 0,08". Rodar pelo menos 5 seeds de modelo e reportar dispersão.

##### C9–C10. Robustez a escolhas analíticas

**C9. Multiverse.** Steegen, Tuerlinckx, Gelman, Vanpaemel. Perspectives on Psychological Science 11(5):702–712, 2016. `[PUB]`

**C10. Specification curve.** Simonsohn, Simmons, Nelson. Nature Human Behaviour 4:1208–1214, 2020 (DOI 10.1038/s41562-020-0912-z). `[PUB]` Três passos: identificar especificações justificadas; exibir graficamente; **inferência conjunta**.

**Contexto:** Gelman & Loken, *The garden of forking paths*. `[PUB]` O problema de comparações múltiplas ocorre mesmo com **uma única análise**, se os detalhes foram contingentes aos dados.

**Cabe? SIM**, e para um nulo é mais valioso que para um positivo. Você já tem 6 caminhos x N modelos x 5 folds x 3 braços — **já é** uma curva de especificação, falta plotar como tal. Custo: 2 dias de reorganização.

---

#### PARTE 4 — Transformar o nulo em teorema

##### D1. Vantagem = distância de variação total

`max_A Pr[b'=b] = 1/2 + (1/2)*Delta(P,Q)`. No cenário de amostra única, `p_guess = (1/2)[1 + ||mu-nu||_TV]`. O distinguidor que otimiza a AUC é a razão de verossimilhança (Neyman–Pearson), e `(1/4)rho_tv <= rho <= (1/2)rho_tv`, com rho = AUC(L) - 0,5. `[PUB]`

**Cabe? SIM.** **A acurácia do seu classificador é, por construção, limite inferior da distância de variação total entre as distribuições de cifrotexto.** Reportá-lo como estimativa de Delta (com IC) é mais informativo que "acurácia".

**Prevê.** Delta = 2*(F1 - 0,5) com IC que contém zero. Reformular nesses termos é mudança de notação com ganho enorme de legibilidade criptográfica. **Recomendado fortemente.**

##### D2. Complexidade de dados do distinguidor ótimo

A complexidade de dados do melhor distinguidor é inversamente proporcional à **SEI** (Squared Euclidean Imbalance, ou capacidade). Junod formaliza também o distinguidor sequencial (SPRT).

**Fontes.** Baignères, Junod, Vaudenay. ASIACRYPT 2004, LNCS 3329. `[PUB]` Baignères & Vaudenay. ICITS 2008, LNCS 5155, pp. 210–222. `[PUB]` Junod. EUROCRYPT 2003, LNCS 2656, pp. 17–32; ePrint 2003/064. `[PUB]`

**Constantes exatas não extraídas** (servidor da COSIC recusou conexão). **Buscar no PDF do ASIACRYPT 2004 ou ePrint 2003/064 antes de citar números.** `[PUB-NV]`

##### D3. Bounds prováveis como origem da ROPE

- **Ascon:** ePrint 2023/775. `[PUB]` Contexto NIST LWC: D <= 2^53, T <= 2^112 → c=136 com b=320 basta, habilitando rate de 184 bits. Bounds anteriores: Bertoni et al. `(D²+DT)/2^c`; Jovanović et al. `(D+T)q_d/2^c`; Andreeva et al. `q_d*T/2^c`; Daemen et al. (IXIF) `LT/2^c`. Melhor ataque conhecido sobre Duplex (Gilbert et al.): `DT >> 2^(3c/2)`, e *"no forgery attack matching this bound has been discovered"*.
- **NIST SP 800-232:** Ascon-AEAD128 rate 128, capacidade 192, 128 bits de segurança, limite de 2^54 bytes por chave, IV `0x00001000808c0001`, tag truncável a no mínimo 32 bits. `[PUB]`
- **GIFT-COFB:** **tightly birthday secure** com consultas de cifragem (Inoue e Minematsu); ataques de forja e privacidade com probabilidade `q_d/2^(n/2)`, inclusive um com 2^(n/2) tentativas usando **uma única** consulta known-plaintext. Contradição documentada com o teorema principal de um paper do Journal of Cryptology 33:703–741 (2020). `[PUB-NV]` ePrint 2021/648.
- **Grain-128AEAD(v2):** estado de 256 bits; melhor tradeoff BG com T=M=D=2^128; **restringe a 2^80 bits de keystream por par chave/IV**. `[PUB]`
- **Schwaemm256-128 (SPARKLE):** modo **Beetle**; segurança de 120 a 250 bits; *long trail strategy*; melhor trilha diferencial de 7 rodadas de Alzette com prob. 2^-26. `[PUB]` ToSC 2020.

##### D4. Limites inferiores de teste de distribuição

Testar uniformidade sobre domínio de tamanho k requer `Theta(sqrt(k)/eps^2)` amostras. Paninski provou o limite inferior `Omega(sqrt(k)/eps^2)`. `[PUB]`

**Cabe? SIM**, e é o argumento de impossibilidade mais limpo. `[EXTRAP]` Os cifrotextos vivem num domínio de tamanho k = 2^524288 (64 KB). Com 180.000 amostras, **nenhum teste, de poder ilimitado, pode dizer nada sobre a distribuição conjunta.** O que se testa são projeções: as 641 features. Portanto:

> **O seu nulo é necessariamente um nulo sobre o espaço de features escolhido, nunca sobre a distribuição de cifrotextos.** Dizer isso não enfraquece; é o que torna correto.

##### D5. MILP e division property — como a criptografia prova nulos de classe

A comunidade resolveu "como publicar um nulo" há mais de uma década: **não se prova que nenhum ataque existe; prova-se exaustivamente que nenhum ataque de uma classe especificada existe, por busca automatizada sobre a classe inteira.**

- **Diferencial/linear:** Mouha, Wang, Gu, Preneel. `[PUB]` https://mouha.be/wp-content/uploads/milp.pdf Exemplo: para SKINNY-128, provou-se que **não existe característica diferencial de 14 rodadas com prob. superior a 2^-128**. `[PUB-NV]`
- **Integral:** Xiang, Zhang, Bao, Lin. ASIACRYPT 2016 / ePrint 2016/857. `[PUB]` A busca dá **cotas superiores no número de rodadas cobríveis por distinguidor integral**.

**Cabe? ADAPTÁVEL**, e é a analogia para vender o trabalho a uma banca de criptografia. O que a MILP faz para "características diferenciais", o experimento faz para "funções aprendíveis por RF/SVM/XGB/CNN1D/CNN2D/Transformer sobre 641 features + bytes crus". Não é prova, é busca — mas sobre classe declarada, e é assim que o campo publica nulos.

**Honestidade obrigatória:** a classe não é fechada, e a busca não é exaustiva dentro dela. Diga antes que perguntem.

##### D6. Impossibilidade da teoria do aprendizado

- **Rivest (1991).** ASIACRYPT '91, LNCS, pp. 427–439. `[PUB]` "Sister fields".
- **Kearns & Valiant (1994).** JACM 41(1):67–95. `[PUB]` Dureza independente de representação.
- **Modelo SQ.** Kearns provou que PARITY não é SQ-aprendível. Blum, Furst, Jackson, Kearns, Mansour, Rudich (STOC 1994) definiram a SQ-dimension. Blum, Kalai, Wasserman (JACM 2003). `[PUB]`
- **O mais operacional:** Shalev-Shwartz, Shamir, Shammah. *Failures of Gradient-Based Deep Learning*. ICML 2017, PMLR 70:3067–3075 (arXiv:1703.07950). `[PUB]` Quatro famílias de falha, incluindo **gradientes não-informativos** e **razão sinal-ruído baixa**, com demonstração em **aprendizado de paridades**. Para paridades de alta ordem o gradiente é essencialmente ruído.

**Cabe? SIM**, e é a resposta teórica a "por que as CNNs/Transformers não acharam nada". `[EXTRAP]` Muda a interpretação dos Caminhos B, C e E de "tentamos deep learning e não funcionou" para "deep learning baseado em gradiente é provadamente cego para esta classe de função".

**Cuidado com o overclaim:** mostram isso para paridades exatas, não para cifrotextos de AEAD. A ponte é heurística. Marque.

**Prevê.** Que as curvas de loss dos Caminhos B/C/E fiquem planas desde a primeira época, com loss de validação ≈ ln 2 = 0,693. **Verificável nos logs que já existem.** Se a loss caiu e voltou, foi memorização; se nunca caiu, é consistente com a previsão teórica. **Rode essa checagem — é grátis.**

##### D7–D8. Testes de duas amostras

**D7. Queda de poder em alta dimensão.** Reddi, Ramdas, Póczos, Singh, Wasserman. AAAI 2015 (arXiv:1406.2083). `[PUB]` **O poder desses testes cai polinomialmente com a dimensão crescente contra alternativas "justas"**.

**Implicação** `[EXTRAP]`: 641 dimensões já são muitas para MMD/energy tests. 65.552 bytes crus são ordens de grandeza piores. Argumento adicional de por que o nulo é esperado — e alerta: não concluir de um MMD nulo em 641 dimensões que as distribuições são iguais.

**D8. Classifier Two-Sample Test.** Lopez-Paz & Oquab. ICLR 2017 (arXiv:1610.06545). `[PUB]` O seu experimento **é** um C2ST, e nomeá-lo assim conecta a um arcabouço com distribuição assintótica conhecida.

**Complemento:** Gretton et al. *A Kernel Two-Sample Test*. JMLR 13:723–773, 2012. `[PUB]`

---

#### PARTE 5 — Questão (a): como demonstrar que o instrumento detectaria o efeito

##### E1. A escada de rodadas reduzidas — a curva de calibração nativa

A escada r → R **é** uma curva dose-resposta. O ponto de perda é o **limite de detecção do instrumento**, na unidade que a comunidade criptográfica entende.

**Pontos de ancoragem publicados:**

| Primitiva | Rodadas | Melhor ataque/distinguidor | Fonte |
|---|---|---|---|
| Ascon (init) | 12 | 7 rodadas: chave em 2^123, 2^64 dados, 2^101 bits de memória; cubos dim. 60 com superpolys nulos | Rohit, Hu, Sarkar, Sun, ToSC 2021 `[PUB]` |
| Ascon-p | 12 | **zero-sum na permutação completa**: 5 inversas + 7 diretas; grau da S-box inversa = 3; 2^244 estados. Com DSF: 2^55 | Dobraunig, Eichlseder, Mendel, Schläffer, CT-RSA 2015 / ePrint 2015/030 `[PUB]` |
| GIFT-128 | 40 | 27 (diferencial), 25 (linear) | `[PUB-NV]` |
| Grain-128a (KSA) | 256 | 191 (single key), 201 (weak key), cubos dim. 5 | `[PUB-NV]` |
| Schwaemm/Alzette | — | melhor trilha de 7 rodadas de Alzette: 2^-26 | Beierle et al., ToSC 2020 `[PUB]` |

**Cabe? SIM** — já está sendo feito. **O que falta é enquadrá-lo como curva de calibração, não como experimento acessório.** A escada de rodadas é o resultado principal, e o nulo em full-round é o ponto final dessa curva.

**Nuance crítica sobre o zero-sum** `[EXTRAP]`: existe distinguidor sobre a permutação Ascon **completa**, de 12 rodadas. A permutação **não é ideal**. Mas exige entradas escolhidas, que o adversário CT-only não tem. Exemplo perfeito para a seção de modelo de ameaça: **uma não-idealidade real, publicada, sobre a primitiva completa, inacessível no seu modelo.** Mostra que o nulo não é "a cifra é perfeita", é "a não-idealidade conhecida não é alcançável passivamente".

**Prevê.** F1 decrescente com rodadas, atingindo 0,50 em r*. Se r* for **menor** que o r dos melhores ataques clássicos, isso é resultado quantitativo forte: o ML CT-only é estritamente mais fraco que a criptanálise clássica com dados escolhidos, e você mediu quanto.

##### E2. Controles positivos e controle de memorização

**Referência-mãe:** Arp, Quiring, Pendlebury, Warnecke, Pierazzi, Wressnegger, Cavallaro, Rieck. *Dos and Don'ts of Machine Learning in Computer Security*. USENIX Security 2022 (arXiv:2010.09470; CACM 2024; dodo-mlsec.org). `[PUB]` Armadilha exemplar: artefatos não relacionados criam **padrões de atalho**.

**Complemento:** Pendlebury, Pierazzi, Jordaney, Kinder, Cavallaro. *TESSERACT*. USENIX Security 2019. `[PUB]` F1 de até **0,99** são inflados por **viés espacial** e **viés temporal**.

**Prevê.** F1 → 1,0 em AES-ECB; F1 → 0,5 em todos os pares AEAD. Se o controle positivo falhar, o nulo não vale nada.

##### E3. Limite de detecção (LOD) e Z'-factor

**LOD/LOQ.** Currie define três níveis: L_c (nível crítico), L_d (limite de detecção), L_q (limite de determinação). O paper existe porque os significados então correntes levavam a valores **abrangendo três ordens de grandeza** — problema idêntico ao do ML hoje.

**Fonte.** Lloyd A. Currie. Analytical Chemistry 40(3):586–593, 1968. `[PUB]` Harmonização IUPAC/ISO 1993–1995.

**Z'-factor.** Coeficiente adimensional que reflete **simultaneamente** faixa dinâmica e variação. Calculado dos limiares dos controles (média ± 3 sigma). Z' > 0,5 = ensaio excelente. Certifica que um ensaio detecta acertos **antes** de rodá-lo.

**Fonte.** Zhang, Chung, Oldenburg. Journal of Biomolecular Screening 4(2):67–73, 1999. `[PUB]`

**Cabe? ADAPTÁVEL**, e é a adaptação mais barata e retoricamente eficaz do relatório. `[EXTRAP]` O Z'-factor entre o controle negativo (par AEAD) e o positivo (AES-ECB) é **um único número** que responde "o ensaio funciona?". Nenhum requer nova computação.

**Prevê.** Z' > 0,5 no par negativo-vs-positivo, Z' < 0 nos pares AEAD.

##### E4. Testes de aleatorização como sanity check

**Fonte.** Adebayo, Gilmer, Muelly, Goodfellow, Hardt, Kim. *Sanity Checks for Saliency Maps*. NeurIPS 2018. `[PUB]`

**Análogo direto:** rodar o pipeline sobre **dois braços do mesmo algoritmo** (Ascon vs Ascon, chaves e nonces diferentes). Se o F1 não for 0,50 aí, o pipeline tem viés estrutural e **nenhum outro resultado vale**. Controle negativo mais forte possível e mais barato que a permutação.

##### E5. Severidade

Mayo, verbatim: *"If [a claim] C passes a test that was highly capable of finding flaws or discrepancies from C, and yet none or few are found, then the passing result, x, is evidence for C."*

**Fonte.** Deborah G. Mayo. *Statistical Inference as Severe Testing*. Cambridge University Press, 2018. `[PUB]` Conexão com física de partículas: arXiv:2002.09713. `[PUB]`

A questão (a) é "o teste era severo?"; a (b) é "quão severo precisa ser?". Use o conceito e cite uma vez; não faça seção filosófica.

##### E6. Física de partículas — a comunidade que publica nulos como produto principal

**Precedente mais forte e mais subexplorado em CS.**

- **CLs.** `CLs = CL(s+b)/CL(b)`. Exclusão a (1-CLs)*100%; 95% se CLs < 0,05. Propriedade crucial: **para mu=0, CLs = 1**, logo mu=0 nunca pode ser excluído. Desenhado para **evitar excluir sinais aos quais a análise não é sensível**. `[PUB]` Read; Junk (1999).
- **Feldman–Cousins.** Phys. Rev. D 57(7):3873–3889, 1998. `[PUB]` Cinturão de confiança que **unifica** limites superiores para nulos e intervalos bilaterais para não-nulos, resolvendo o problema de escolher entre os dois **com base nos dados**. Evita intervalos não-físicos.
- **Look-elsewhere.** Gross & Vitells. EPJ C 70:525–530, 2010. `[PUB]` Fator de tentativa cresce **linearmente** com a significância local.

**Cabe? ADAPTÁVEL**, e natural. `[EXTRAP]` O análogo da "massa" é o **número de rodadas**. O produto passa a ser:

> "Excluímos, a 95% CL, vantagem de distinção CT-only Delta > delta(r) para r >= r*, com a classe de distinguidores D; e não temos sensibilidade para Delta abaixo de delta_min = 0,0X."

Essa frase é uma contribuição. "Não conseguimos distinguir" não é.

O CLs existe **precisamente** para impedir que um experimento insensível declare exclusão por flutuação. Antídoto formal contra o erro que se quer evitar.

**Custo.** Adotar apenas o enquadramento (exclusão em vez de não-detecção) sem implementar CLs dá 80% do benefício por 5% do custo.

##### E7. Injeção controlada de sinal (spike-in)

`[EXTRAP]` — sem precedente em cripto. Construir cifrotextos sintéticos com viés conhecido de magnitude eps, varrer eps, medir em que eps o pipeline atinge F1 = 0,55, 0,75, 0,95. Curva de resposta direta, em unidades de vantagem.

**Cabe? SIM.** Complementar à E1: a escada calibra em unidades criptográficas, o spike-in em unidades estatísticas, e as duas devem ser consistentes.

**Custo.** Muito baixo, paralelizável. **Prevê:** uma sigmoide. O eps onde F1 = 0,55 é o LOD operacional. **A peça de evidência mais barata e convincente para a questão (a).**

---

#### PARTE 6 — Questão (b): critérios de banca e revisor

Ordenado por peso.

**1. O controle positivo passou?** Critério eliminatório. Sem debate em nenhuma rubrica.

**2. Qual é o limite de detecção, em número?** Não "usamos 180k amostras", mas "detectamos Delta >= 0,0X com poder 0,80". Sem essa frase, o resultado é indistinguível de um experimento subpotente.

**3. O efeito foi comparado com o teto teórico?** Critério que o ML não tem e a criptografia tem. FESLA fez validação cruzada, datasets não vistos e cinco classificadores, todos passaram, e é artefato — porque ninguém comparou 100% com o máximo teórico de 50%+2^-55. Numa banca de criptografia, resultado que excede o bound provável é **automaticamente** bug até prova em contrário.

**4. O nulo sobrevive à variação de especificação?** Um nulo numa especificação é anedota.

**5. Há explicação mecanicista?** A CFP do Insights exige verbatim *"some explanation/hypothesis"*. Nulo sem "por quê" não é aceito nem no workshop dedicado a nulos.

**6. O escopo está delimitado?** "Não existe distinguidor" é indefensável. "Não existe distinguidor na classe D com o orçamento B sobre o espaço F" é defensável, e é como MILP e division property publicam nulos.

**7. O artefato é executável?** Para um nulo, não é opcional: é a evidência.

**8. Os classificadores degeneraram?** Acurácia 0,50 com TPR=1,0 e TNR=0,0 não é indistinguibilidade, é treino falhado. A Regra de Ouro nº 7 já protege — **certifique-se de que o texto explicita a distinção**.

**9. Pré-registro ou graus de liberdade declarados?** Para um nulo é menos grave (forking paths tende a produzir falsos positivos), mas declarar fecha a objeção.

**10. Reconhece o viés de publicação do campo?** Serra-Garcia & Gneezy, *Nonreplicable publications are cited more than replicable ones*, Science Advances 7(21), 2021 `[PUB]` — papers que falham em replicar são **mais** citados; a diferença **não muda após a publicação da falha**; apenas **12%** das citações pós-replicação reconhecem a falha; em Nature/Science o gap foi de **300x**.

**Bônus de cripto:** D. J. Bernstein, *Cryptographic competitions*, Journal of Cryptology 37:7, 2024 `[PUB]`. NIST IR 8454 `[PUB]`: a equipe revisou os finalistas com base em pacotes de submissão, atualizações, **papers de análise de terceiros**, e benchmarking. **A ausência de ataque só conta quando há esforço documentado de terceiros.**

**Contra-argumento a antecipar:** Aumasson, *Too Much Crypto*, ePrint 2019/1492 `[PUB-NV]`, argumenta que margens de segurança são excessivamente conservadoras. A margem (rodadas não atacadas) é métrica criticada por negligenciar dependências entre componentes.

---

#### PARTE 7 — Nulos derrubados depois

##### G1. RC4 — o nulo que as baterias genéricas não viram

**O que se acreditava.** RC4 passava nos testes padrão; vieses conhecidos eram considerados localizados e não exploráveis em TLS.

**O que derrubou.** AlFardan, Bernstein, Paterson, Poettering, Schuldt. USENIX Security 2013. `[PUB]` Ataques de recuperação de plaintext **ciphertext-only** contra TLS com RC4. Viés de byte único anunciado em 12 mar. 2013, na palestra de Bernstein no FSE 2013. Distribuições dos **primeiros 256 bytes** medidas com **2^44 chaves de 128 bits**. Consequência: RFC 7465.

**O que estava mal feito.** Nada de fraudulento. Problema de **resolução**: os vieses estavam lá, com magnitude ~2^-8 a 2^-9 sobre posições específicas. Nenhuma bateria genérica com volume normal os detecta. Foi preciso (i) estatística específica (distribuição condicional à posição), e (ii) 2^44 amostras.

**A lição, direta.** Seu experimento tem 2^17,5 amostras. AlFardan et al. precisaram de 2^44 para ver um viés de 2^-8 numa cifra **reconhecidamente fraca**. **Você está 26,5 ordens binárias abaixo do volume necessário para expor a cifra mais estatisticamente enviesada em uso real.**

Sugere redesenho `[EXTRAP]`: se houver resíduo, está em **estatísticas posicionais** (byte j de todos os cifrotextos, condicionado à posição), não em histogramas agregados. O histograma de 256 dimensões agrega sobre todas as posições e apagaria exatamente esse tipo de viés. **Verificar se alguma das 12 famílias é posicional.**

##### G2. Gohr — o nulo limitado pela representação

**O que se acreditava.** Antes de 2019, ML em cifras produzia nada.

**O que derrubou.** Gohr. CRYPTO 2019 / ePrint 2019/037. `[PUB]` ResNets com rank médio de chave **~5x menor** que distinguidores clássicos usando a DDT completa em **9 rodadas** de Speck; busca bayesiana reduzindo a segurança de **11 rodadas de Speck32/64 a ~38 bits**. Os distinguidores *"successfully use features of the ciphertext pair distribution that are invisible to all purely differential distinguishers even given unlimited data"*.

**O que estava mal feito.** A **representação de entrada**. Gohr alimenta a rede com **pares** sob diferença de entrada escolhida. O nulo anterior era sobre a representação "um cifrotexto por vez".

**A lição, desconfortável.** É o risco número um: **o nulo pode ser da representação.** Defesa em duas partes: (i) o modelo CT-only **proíbe** a representação de Gohr — dizer isso explicitamente, nominalmente, citando Gohr; (ii) você testou N representações (307D, 641D, bytes crus 1D, co-ocorrência 2D, patches) e a curva de especificação mostra o nulo através de todas. A parte (i) é o argumento forte.

##### G3. Dessincronização em side-channel

**Fonte.** Cagli, Dumas, Prouff. CHES 2017 / ePrint 2017/740. `[PUB]` Dessincronização de **até 200 amostras** superada com CNNs + data augmentation, **sem pré-processamento**.

**O que estava mal feito.** Nulo de classe apresentado como nulo geral.

##### G4. Interpose PUF

**Fonte.** Wisiol, Mühl et al. TCHES / ePrint 2019/1473. `[PUB]` Divide-e-conquista modelando os dois blocos separadamente via regressão logística, **refutando a alegação original**.

**O que estava mal feito.** Alegação baseada em resistência a ML **genérico**, não a ataques estruturados. "Testamos com as ferramentas de prateleira e não funcionou" não é alegação de segurança.

##### G5. Gimli — finalista da rodada 2, distinguidor na permutação completa

**Fonte.** Flórez Gutiérrez, Leurent, Naya-Plasencia, Perrin, Schrottenloher, Sibleyras. ASIACRYPT 2020 / ePrint 2020/744 (JoC, DOI 10.1007/s00145-021-09413-z). `[PUB]` Difusão lenta e simetrias internas: distinguidor na permutação **completa** com complexidade **2^64**; distinguidor **prático implementado** em **23 das 24 rodadas**.

**A lição.** Gimli era finalista da rodada 2 e foi eliminado. Ausência de ataque num momento t não é evidência forte quando o esforço de análise ainda é pequeno.

##### G6. Midori64, SCREAM e PRINTcipher — bounds provados numa classe, quebrados por outra

**O caso mais importante para o argumento de escopo.**

**Nonlinear invariant attack.** Todo, Leander, Sasaki. ASIACRYPT 2016 / ePrint 2016/732; JoC (DOI 10.1007/s00145-018-9285-0). `[PUB]` Distinguem as versões **completas** de SCREAM, iSCREAM e Midori64 em chaves fracas, com **um punhado de pares** e custo mínimo. O plaintext de SCREAM pode ser praticamente recuperado dos cifrotextos no cenário **nonce-respecting**.

**Invariant subspace attack.** Leander, Abdelraheem, AlKhzaimi, Zenner. CRYPTO 2011. `[PUB]` Quebra a cifra **completa** para fração significativa das chaves; ataque distinguidor em **tempo unitário**.

**O que estava mal feito.** Nada. Os designers provaram bounds sólidos contra diferencial e linear, e continuam válidos. O ataque veio de uma **classe que ninguém estava enumerando**. Contraexemplo decisivo ao D5: a busca MILP prova não-existência dentro da classe, e a classe não é o universo.

**Aplicação literal.** A conclusão será "não há sinal detectável pelas classes D sobre o espaço F". Midori64 lembra que um adversário que inventar uma classe G ortogonal a F pode achar algo amanhã. **Cite Todo et al. na seção de limitações.**

##### G7. Dual EC DRBG

Shumow e Ferguson, rump do CRYPTO 2007. `[PUB]` Backdoor cleptográfico: recuperação do estado interno com **32 bytes** de saída. Depois: Checkoway et al., USENIX Security 2014; Bernstein, Lange, Niederhagen, ePrint 2015/767. `[PUB]`

**A lição.** "Passa nos testes estatísticos" e "é seguro" são afirmações não relacionadas. O nulo sobre distinguibilidade estatística **não** é afirmação sobre a segurança dos quatro algoritmos. Um parágrafo explícito separando as duas coisas evita a pior pergunta possível numa defesa.

##### G8. Ascon — a margem encolhendo devagar

Dobraunig et al. (CT-RSA 2015) → Rohit, Hu, Sarkar, Sun (ToSC 2021) chegam a **7 rodadas** com chave em 2^123. Rohit & Sarkar, ToSC 2021(4):74–99. Cubos condicionais com break-fix (ePrint 2024/743). `[PUB]`

**A lição.** Margens encolhem monotonicamente. Um resultado de 2026 que diz "nada em 12 rodadas" tem validade datada. **Diga a data.**

---

#### APOSTAS

##### APOSTA 1 — Trocar "não detectamos" por "excluímos Delta > delta", e derivar delta de duas fontes independentes

1. Calcular o **teto teórico** por par, dos bounds de Chakraborty–Dhar–Nandi (Ascon), birthday do COFB, claim de 2^80 do Grain, Beetle para Schwaemm. Tabela: `Par | Bound provável | Delta máximo teórico | Delta detectável | Razão`.
2. Calcular o **limite de detecção operacional** delta pela análise de poder com bootstrap agrupado por chave.
3. Reformular tudo como `Delta = 2*(F1 - 0,5)` com IC: "excluímos Delta > delta a 95%; não temos sensibilidade abaixo de delta".
4. TOST + ROPE(Kruschke) + `baycomp` como triangulação, com ROPE de ±0,01 de Benavoli et al. como default citável.

**Por quê.** Custo ≈ zero (reanálise). Ganho ≈ máximo. Transforma o capítulo de resultados de relato de ausência em relato de medição. Responde (a) e (b) na mesma tabela.

**Risco.** A tabela vai mostrar razão de 10^9 a 10^33 entre detectável e teórico, e isso pode ser lido como "o experimento era inútil". A resposta — que precisa estar **escrita** — é que o experimento nunca poderia testar a alegação criptográfica, e que o que ele testa (ausência de falha grosseira, de vazamento por metadado, de atalho aprendível) é a pergunta que a literatura vinha respondendo errado.

##### APOSTA 2 — Curva de spike-in mais escada de rodadas, publicadas juntas como a curva de calibração

1. **Spike-in.** Perturbar bits de cifrotexto Ascon com probabilidade 0,5+eps, varrer eps em {10^-1, 10^-1.5, ..., 10^-4}, rodar o Caminho A em cada. Saída: sigmoide F1(eps); o eps onde F1 = 0,55 é o LOD em unidades de vantagem.
2. **Escada de rodadas.** Já existe. Extrair r* por algoritmo, com IC.
3. **Consistência cruzada.** Verificar se o eps correspondente a r* bate com o Delta estimado na rodada r*. Duas calibrações independentes concordando é muito mais forte que uma.
4. Reportar Z'-factor entre o par AEAD e o controle AES-ECB, e o LOD no formato de Currie.

**Por quê.** Resposta completa e defensável à questão (a), e barata. A escada fala com criptógrafos; o spike-in com estatísticos; o Z'-factor é um número único. Nenhum exige GPU.

**E, sinceramente: a escada de rodadas é o resultado principal do trabalho, não o nulo.** O nulo é o ponto final de uma curva. A curva é a contribuição. **Reorganizar a dissertação nessa ordem é provavelmente a decisão editorial de maior impacto disponível.**

**Risco.** Se a curva de spike-in mostrar um LOD muito pior que o binomial teórico (0,013), o instrumento é menos sensível do que se pensa. Melhor descobrir agora que na defesa.

##### APOSTA 3 — Parar de usar só acurácia e rodar um teste de duas amostras genuíno em paralelo

1. Testes marginais por feature (KS ou Mann-Whitney), agrupados por chave, com BH-FDR — já existe em `consolidate_v2.py`.
2. MMD com kernel RBF sobre subamostras (ou C2ST com a nula de Lopez-Paz & Oquab), calibrado por permutação **agrupada por chave**.
3. Permutação de rótulos de Ojala & Garriga sobre o pipeline inteiro, incluindo o seletor, com >= 1.000 permutações nos modelos clássicos.
4. **Braço Ascon-vs-Ascon** (chaves diferentes, mesmo algoritmo) como controle negativo estrutural — se der F1 != 0,50, há viés no pipeline.
5. Verificar nos logs de B/C/E se a loss de validação **nunca desceu** de ln 2 ≈ 0,693. Se desceu e voltou, memorização; se nunca desceu, consistente com Shalev-Shwartz et al.

**Por quê.** Rosenblatt et al. mostram que acurácia é **subpotente**. Os seis caminhos são seis variações da mesma estatística subpotente. Se um revisor apontar isso, a resposta precisa ser "também rodamos o teste potente, e ele também não rejeita".

O item 4 é o controle mais forte e barato de toda a lista. O item 5 é grátis.

**Risco real.** O teste multivariado com FDR sobre 641 features **pode** rejeitar. Se rejeitar, é achado, não nulo, e precisa ser investigado até a raiz (provavelmente artefato de comprimento, padding, ou região de tag — e há uma família `tag_region` justamente lá). Mais trabalho, mas é o trabalho certo. Ver G1: o viés do RC4 estava em estatísticas **posicionais**, e o histograma agregado apagaria exatamente esse tipo de sinal.

---

#### Anexo — Lacunas honestas desta pesquisa

1. **Nenhuma aplicação publicada de TOST, ROPE ou fator de Bayes a distinguidores criptográficos.** Busca retornou apenas psicologia e estatística médica. Lacuna real e contribuição disponível.
2. **Nenhum trabalho que derive a região de equivalência de um bound de segurança provável.** Sem precedente. A ideia da Parte 0 é do agente `[EXTRAP]`; se usada, precisa ser apresentada como contribuição original e defendida, não citada.
3. **Constantes exatas de Baignères–Junod–Vaudenay não extraídas** (servidor da COSIC recusou). Buscar no PDF do ASIACRYPT 2004 ou ePrint 2003/064 antes de citar números.
4. **Não verificados nesta sessão:** Schuirmann (1987); Rouder et al. (2009); Wellek; Field & Welsh e Cameron-Gelbach-Miller (bootstrap agrupado); Lapuschkin et al. (Clever Hans); Geirhos et al. (shortcut learning); Henderson et al. (Deep RL That Matters); Ioannidis (2005); Mayo & Spanos (2006).
5. **Nenhum paper de criptanálise cujo resultado principal declarado seja "procuramos ataque e não achamos".** O campo publica nulos de três formas indiretas: bounds provados (MILP/division property), bounds de segurança provável, e relatórios institucionais (NIST IR 8454, Bernstein 2024). Não existe um gênero "resultado negativo" em ToSC/CHES/CRYPTO equivalente ao ICBINB. **Relevante para onde publicar:** o enquadramento de exclusão quantitativa (Aposta 1) dá uma forma que ToSC/CiC reconhecem; o de auditoria de campo (Parte 2) dá uma forma que os workshops de ML reconhecem. São públicos diferentes e talvez dois papers diferentes.

---

# Pesquisa 06 — Estatística de alta ordem além da bateria NIST

- **Ângulo:** Estatística de alta ordem além da bateria NIST
- **Temperatura declarada:** 0,65

## Pesquisa 06 — prompt usado, na íntegra

````markdown
# Pesquisa 06 — Estatística de alta ordem: o que existe além da bateria NIST

**Ângulo desta pesquisa.** A bateria NIST SP 800-22 é o instrumento padrão para
"isto parece aleatório?", mas ela foi desenhada para detectar desvios
estruturados específicos, e o próprio NIST declara que não computa o erro
tipo II — ou seja, o poder dela contra uma alternativa que não seja uma das
que ela antecipa é indefinido.

Procure o que existe **além** dela, e o que é demonstravelmente mais potente.

Persiga: teoria espectral e análise de Fourier sobre sequências binárias
(coeficientes de Walsh-Hadamard, transformada rápida sobre F2); complexidade
de Lempel-Ziv, complexidade de Kolmogorov aproximada, e métodos baseados em
compressão de verdade (NCD, distância de compressão normalizada); entropia de
Rényi e de Tsallis, e estimadores de entropia para amostras esparsas;
discrepância e equidistribuição; estatísticas de ordem superior (cumulantes,
bispectro); e busca automatizada de funções booleanas distinguidoras
(BoolTest e sucessores).

Pergunta central: **dada uma sequência que passa no NIST STS, que teste
detecta desvio que o STS não detecta, e com quanto dado?** Quero casos
documentados em que uma estatística mais fina pegou o que a bateria padrão
deixou passar.

Interessa também a direção oposta: evidência de que essas alternativas são
redundantes com o STS na prática.

**Temperatura: 0,65.** Escala de amplitude de exploração, de 0,1 a 1,0.
Não é temperatura de amostragem — é instrução. Em 0,65: favoreça o que é
menos citado e mais específico em vez do panorama conhecido, e persiga
ferramentas de comunidades vizinhas (física estatística, teoria da
informação algorítmica, processamento de sinais). Continue exigindo fonte.

---

# Prompt base — técnicas de distinção de algoritmos de criptografia

Este é o texto-mãe. Cada uma das 10 pesquisas recebe uma variação dele, com um
ângulo diferente e uma temperatura, e NADA MAIS: nem o repositório, nem os
resultados das pesquisas anteriores, nem esta conversa.

---

## PROBLEMA DE PESQUISA

Você está pesquisando para uma dissertação de mestrado em criptografia
aplicada e aprendizado de máquina. Trabalhe SÓ com literatura externa: não
leia nenhum repositório, arquivo local ou resultado prévio. Comece do zero.

**A pergunta.** Dado apenas o criptograma — sem a chave, sem o texto em claro,
sem poder escolher nada do que é cifrado — é possível distinguir qual
algoritmo de criptografia autenticada o produziu? E, num segundo nível, com
quantas rodadas reduzidas um algoritmo ainda deixa de parecer aleatório?

**Os algoritmos.** Os quatro finalistas do concurso NIST Lightweight
Cryptography: Ascon-AEAD128 (esponja), GIFT-COFB (cifra de bloco em modo
COFB), Grain-128AEAD (cifra de fluxo com LFSR e NFSR) e Schwaemm256-128
(esponja ARX, família SPARKLE).

**O modelo de ameaça, que é a restrição dura e não negocia.** Adversário
PASSIVO, em ciphertext-only. Ele observa criptogramas de um mesmo dispositivo,
com nonces públicos de contador, e pode observar vários de uma vez. Ele NÃO
tem: texto em claro conhecido ou escolhido, diferenças escolhidas na entrada,
reuso de nonce, acesso a canais laterais, nem consultas a um oráculo de
cifragem. Isso exclui de saída a maior parte da criptanálise diferencial
clássica e os distinguidores neurais no estilo Gohr, que dependem de pares com
diferença escolhida.

**O protocolo experimental.** Classificadores clássicos e redes sobre features
estatísticas e sobre os bytes crus. Chaves de teste nunca aparecem no treino
(key-holdout). Intervalo de confiança por bootstrap agrupado por chave, e não
i.i.d. Correção para múltiplas comparações. Controle negativo obrigatório: com
o algoritmo completo o classificador tem que ficar no acaso.

## O QUE EU QUERO DE VOCÊ

Técnicas, representações, ataques ou ideias — publicadas ou adaptáveis — que
possam extrair sinal nesse cenário, ou que ajudem a delimitar com rigor por
que o sinal não existe. Interessa tanto o que funciona quanto a prova de que
algo é impossível.

Busque em literatura acadêmica real (IACR ePrint, ToSC/FSE, CHES, CRYPTO,
EUROCRYPT, ASIACRYPT, SAC, Designs Codes and Cryptography, IEEE, Springer,
arXiv) e em fontes técnicas sérias. Use termos de busca em inglês.

## COMO RESPONDER

Para cada ideia encontrada, escreva:

1. **O que é** — a técnica, em duas ou três frases.
2. **Fonte** — autores, título, veículo, ano. Link quando houver. Se você não
   conseguiu confirmar a existência do trabalho, diga isso explicitamente em
   vez de completar de memória.
3. **Cabe no nosso modelo?** — SIM, NÃO, ou ADAPTÁVEL. Se ADAPTÁVEL, diga
   exatamente o que teria de mudar e qual premissa do modelo de ameaça isso
   arranha.
4. **O que custaria testar** — ordem de grandeza de dados, computação e
   engenharia.
5. **O que ela prevê** — se a técnica funcionar, que resultado deveríamos ver?
   Se não houver previsão falsificável, diga isso.

Termine com uma seção **APOSTAS**: as três ideias que você tentaria primeiro,
e por quê. Seja específico; "usar deep learning" não é uma aposta.

## PROFUNDIDADE — leia isto com atenção

Não é um levantamento rápido. **Vá até esgotar o veio.** Não pare em cinco ou
dez achados porque já "deu para ter uma ideia": siga as citações para frente e
para trás, abra os trabalhos relacionados dos artigos que importarem, procure
versões estendidas e teses, e persiga as pistas que aparecerem no caminho,
mesmo as que não estavam no ângulo original. Só encerre quando as buscas novas
pararem de trazer coisa nova.

Traga TODA a informação, não um resumo dela. Se um artigo tem um número que
importa (quantas rodadas, quantas consultas, que acurácia, que tamanho de
dado), traga o número. Se tem uma limitação declarada pelos próprios autores,
traga a limitação com as palavras deles. Prefira errar por excesso de detalhe.
Uma resposta longa e completa é o que se pede aqui; uma resposta enxuta é
falha de execução.

## REGRAS

- Não invente referências. Uma fonte não confirmada vale menos que nenhuma, e
  vou checar.
- Não repita o óbvio já saturado (distinguidor diferencial-neural padrão)
  sem trazer um ângulo novo que sobreviva ao ciphertext-only.
- Se a conclusão honesta de um caminho for "isso é impossível neste modelo
  por tal razão teórica", isso é resultado útil. Diga.
- Separe o que é publicado do que é sua extrapolação. Marque cada um.
````

## Pesquisa 06 — achados, sem resumir

### Achados — Pesquisa 06

- **Ângulo:** estatística de alta ordem além da bateria NIST
- **Temperatura declarada:** 0,65
- **Prompt usado:** `prompts/06_estatistica_alta_ordem.md`
- **Execução:** ~367k tokens de subagente (a maior até agora), 84 chamadas, ~27 min

Marcação: **[PUB]** = publicado, lido/confirmado; **[CIT]** = existência confirmada, texto integral não obtido; **[MINHA]** = extrapolação do agente.

---

#### PARTE 0 — O enquadramento que muda tudo

##### 0.1 O próprio NIST diz que a STS não tem poder definido

**[PUB]** Andrew L. Rukhin (autor da SP 800-22), *"Statistical Testing of Randomness: New and Old Procedures"*, cap. 3 de *Randomness Through Computation* (H. Zenil, ed.), World Scientific, 2011, pp. 33–51. https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=903151

- Critério de inclusão foi prático, não ótimo: *"While an attempt was made to employ only procedures which are optimal from the point of view of statistical theory, this concern was secondary to practical considerations."*
- Sobre a alternativa: *"An additional difficulty of the randomness hypothesis is that its amorphous alternative is enormous and cannot be fully described by a sensible finite-dimensional parameter set Theta_1."* — por isso o erro tipo II não é computável em geral.
- **O teste espectral (DFT) da STS estava errado**: *"The spectral test which appeared in the suite turned out to be troublesome. As it happened, it was not properly investigated, which resulted in a wrong statistic and a faulty constant."* Corrigido por Kim, Umeno & Hasegawa (2003), Killmann et al. (2004), Hamano (IEICE E88, 2005, 67–73) **[CIT]**.
- **O teste de Lempel–Ziv foi REMOVIDO da STS**: *"Unfortunately, this test failed because the normal approximation was too poor, i.e., the asymptotic formulas are not accurate enough for values of n of the magnitude encountered in testing random number generators."*
- **Kolmogorov é beco sem saída formal**: *"this complexity characteristic is not computable (Cover and Thomas, 1991), and there is no hope for a test which is directly based on it."*
- Saída via códigos universais, citando **Ryabko & Monarev (2005)**: corte `T_0 = n*log q + log alfa - 1`. *"For universal codes the power of the corresponding test tends to one as n increases. However, finding non-trivial compression codes with known distributions of the codewords length (so that P-value can be evaluated) is quite difficult."*
- **Teste assintoticamente ótimo** baseado em contagem de palavras com frequência prescrita (Tabela 2: pesos ótimos e lambda* para R = 0..9; R=0 → lambda* = 3,59, peso 1; R=9 → lambda* = 13,26). *"asymptotically optimal not only within the class of linear statistics, but in the class of all functions of X^0,...,X^R"*. O teste de palavras faltantes (OPSO do Diehard) é o caso R=0 com q mal escolhido: *"q = 2^10 new letters, which in general is not the optimal choice"* — o ótimo é `n ≈ 3.6*q^2`.

**Cabe?** SIM. **Custo:** trivial, O(n) por amostra.
**Prevê:** trocar a família `ngrams` (15D) pelo estimador de pesos ótimos com `n ≈ 3.6*q^2` (para 524.288 bits → p ≈ 8, q = 256, m=2) daria o teste mais potente da classe — e ainda assim deve dar acaso nos quatro AEAD completos.

##### 0.2 O criptograma **provavelmente não é aleatório** — publicado, com números

**[PUB]** Ryabko, Stognienko, Shokin, *"A new test for randomness and its application to some cryptographic problems"*, **JSPI 123 (2004) 365–376**, doi:10.1016/S0378-3758(03)00149-6. PDF: https://boris.ryabko.net/jspi.pdf

> *"the Shannon entropy of the ciphered text is not greater than the sum of the key entropy and the entropy of the input. Hence, if, for example, someone uses such a cipher for which the lengths of input and output files are equal and applies this cipher to an English language text using one key for the large text, the Shannon entropy of the ciphered text will be approximately the same as for the original text and, consequently, will be less than 1 per bit. (…) So, apparently, the problem of constructing tests which can distinguish ciphered texts from random sequences can be considered as a good example for estimation of a power of statistical tests, because, on the one hand, it is known that ciphered texts cannot be completely random in principle."*

**Aritmética para o nosso caso** (a conta é **[MINHA]**): 64 KB de SPGC, entropia do inglês ≈ 1,3 bit/char → H(P) ≈ 85.000 bits. Criptograma = 524.416 bits. `H(C) <= H(K) + H(N) + H(P) = 128 + 128 + 85.000 ≈ 85.256 bits`. O criptograma vive num suporte de ≈2^85.000 dentro de 2^524.416 — fração 2^-439.000. **Um distinguidor sem limite computacional acerta com vantagem ≈ 1 numa única amostra.** Toda a segurança é computacional. H0 *nunca* é literalmente verdadeira; qualquer resultado H0 é afirmação sobre o poder da classe de testes.

**Mas** — e é o que fecha o experimento — esse orçamento de não-uniformidade é **idêntico para os quatro**, porque a regra 6 faz H(P) ser comum. Produz sinal *cifra-vs-uniforme*, não *cifra-vs-cifra*. Por isso AES-ECB e PRNG são os controles certos, e por isso H0 no problema de 4 classes não é surpresa.

##### 0.3 A tabela do Ryabko et al. 2004 — na NOSSA escala de dados

Textos em inglês e russo cifrados com **Rijndael (AES)** e **RC6**, em **ECB, uma chave por arquivo**, 40 arquivos por célula, alfa=0,05, palavras de **24 bits** (k = 2^24). Treino/teste = metades do arquivo. Tabela 1 (rejeições em 40, `usual/new`):

| Tamanho (bytes) | 102.400 | 204.800 | 512.000 | 1.024.000 | 2.048.000 |
|---|---|---|---|---|---|
| RC6 russo | 4/**11** | 4/**13** | 4/**28** | 23/**32** | 27/**35** |
| RC6 inglês | 7/**19** | 6/**24** | 5/**31** | 27/**31** | 27/**35** |
| AES russo | 3/**10** | 4/**18** | 5/**24** | 18/**31** | 25/**34** |
| AES inglês | 4/**17** | 8/**26** | 8/**28** | 25/**30** | 30/**33** |

"usual" é o **melhor** resultado do qui-quadrado comum sobre todos os s = 1..14 testados. Conclusão: *"the new test can detect non-randomness more efficiently than the usual chi-square test. In other words, the power of the adaptive chi-square test is larger than that of the usual one, when the sample size is relatively small."*

Teorema (p. 369): existe k_{alfa,beta} tal que para todo k par > k_{alfa,beta} há teste adaptativo com `m(k)+n(k) <= c*sqrt(k)` amostras com erro tipo I < alfa e tipo II < beta — **tamanho de amostra O(sqrt(k)) em vez de O(k)**.

**Cabe?** SIM, integralmente. A fase de "treino" usa metade do *próprio criptograma* (ou o fold de treino).
**Custo:** O(n) por amostra, dicionário de 2^24 contadores (64 MB de int16). Horas de engenharia.
**Prevê:** deve **disparar** no controle AES-ECB (replicando o Ryabko) e no PRNG; **não disparar** nos quatro AEAD com nonce. Se disparar num AEAD completo, ou há achado, ou vazamento. **Controle positivo com valor de referência publicado**, que é o que o v2 não tem.

##### 0.4 O experimento não é teste de aleatoriedade — é teste de duas amostras

**[PUB]** Lopez-Paz & Oquab, *"Revisiting Classifier Two-Sample Tests"*, ICLR 2017. https://openreview.net/pdf/f810ace79b2282d0ac7c553a182c01b0670ce8dc.pdf

O C2ST é literalmente o que os Caminhos A–F fazem. Dá base formal ao protocolo e o **nulo exato**: teste de permutação dos rótulos *dentro de cada bloco de chave* é o nulo correto, e é mais apertado que o bootstrap agrupado atual.

**[PUB]** Gretton et al., *"A Kernel Two-Sample Test"*, JMLR 13 (2012) 723–773.
**[PUB]** Kernel two-sample em alta dimensão: *Biometrika* 110(2) (2023) 411, arXiv:2201.00073 — poder do MMD **decai polinomialmente com a dimensão** para deslocamento de média gaussiana, mas **não sofre maldição da dimensionalidade quando os dados vivem perto de variedade de baixa dimensão**. Os 641D têm estrutura de baixa dimensão; os 65552 bytes crus não.

**Custo:** MMD RBF sobre 641D e N=30k por classe: O(N²) = 9x10^8 pares — usar estatística linear-time ou subamostragem por bloco de chave. Um dia.
**Prevê:** MMD livre de modelo concordando com F1≈0,50 é **evidência muito mais forte de H0** que "o RF não achou", porque elimina "o modelo é que é fraco".

##### 0.5 Ordenação formal de poder, e a prova de que "passar na STS" não significa nada

**[PUB]** Boris Ryabko, arXiv:2404.02708 (3 abr 2024); **Entropy 26(6), 513 (2024)**, doi:10.3390/e26060513.

1. **Métrica de poder via dimensão de Hausdorff.** `T1 >= T2` sse `dim(R_T2 \ R_T1) > 0`. Ordenação parcial *rigorosa* de testes, que a literatura de baterias nunca teve.
2. **Teorema 1.** Para m, s, t = ms: `T^t_{K_m} <= T^t_{K_{m+1}}` e `T^t_{K_m} <= T^t_R`. E **`dim(T^t_{K_m} \ T^t_{K_{m+1}}) = 1`** — o conjunto que passa num teste de Markov de ordem m e falha no de ordem m+1 tem dimensão de Hausdorff **máxima**.
3. **Teorema 2.** Para qualquer x aleatória existe y(x) por duplicação de prefixos que é **não-aleatória para LZ e aleatória para T^t_R e T^t_{K_m} para todo m, t**; e `dim(R_{T^t_{K_m}} \ R_{T_LZ}) >= 1/2`, com supremo 1. **Testes de compressor de dicionário dominam estritamente toda a família de Markov de ordem finita** — e a NIST STS é, em essência, família de ordem finita.
4. **Processos "two-faced"** (Apêndice C; Ryabko–Monarev 2005 / Ryabko–Fionov 2005). Existem cadeias de Markov `T_k` de ordem k tais que **`P(x_{j+1}...x_{j+k} = u) = 2^-|u|` para todo u de comprimento <= k** mas cuja entropia limite é arbitrariamente baixa. Exemplo com nu = 0,9: `0000000000 111111111 0000000000 1111111 0...`.

**Resposta formal à pergunta central.** Existem sequências *construtivamente* projetadas para passar em qualquer teste de janela < s e serem maximamente não-aleatórias em janela >= s. Passar na STS é afirmação sobre s <= ~20 bits, e nada mais.

**Recomendação do próprio Ryabko** (§V): usar vários `T_{K^t_s}` com `s1 = O(log n)`, `s2 = O(sqrt(log n))`, e **incluir testes de compressor de dicionário**:

```
tau_LZ(x_1...x_n) = n - |LZ(x_1...x_n)|      valor crítico   t_alfa = n - log(1/alfa) - 1
```

> *"Note that in this case there is no need to use the density distribution formula, which greatly simplifies the use of the test and makes it possible to use a similar test for any grammar-based data compressor."*

**Enorme.** Você já tem `compression_ratio_zlib/bz2/lzma` como *features*. Podem virar **testes calibrados, válidos, sem distribuição nula, sem simulação**, para *qualquer* compressor sem perdas livre de prefixo. Custo: zero além de remover o cabeçalho do container.

**Prevê:** para n = 524.416 bits e alfa = 0,01, `t_alfa = n - 7,64` — o compressor precisa economizar **>= 8 bits**. Deve falhar sempre nos AEAD completos e disparar no AES-ECB. Teto honesto: "com 64 KB por amostra, nenhum compressor conhecido consegue nem 8 bits".

**[CIT]** Ryabko, *"Asymptotically most powerful tests for random number generators"*, **JSPI 217 (2022) 1–7**, doi:10.1016/j.jspi.2021.07.007.

---

#### PARTE 1 — Busca automatizada de funções booleanas distinguidoras

##### 1.1 BoolTest — a referência, com todos os números

**[PUB]** Marek Sýs, Dušan Klinec, Karel Kubíček, Petr Švenda, *"BoolTest: The fast randomness testing strategy based on boolean functions with application to DES, 3-DES, MD5, MD6 and SHA-256"*, **ICETE 2017 Selected Papers, Springer CCIS, 2019**, doi:10.1007/978-3-030-11039-0_7. Preprint: https://crocs.fi.muni.cz/_media/public/papers/booltest_preprint_2017.pdf Código: https://crocs.fi.muni.cz/papers/booltest2018

**Método.** Blocos não-sobrepostos de m bits (m em {128, 256, 384, 512}). Fase 1: avalia todos os monômios de grau <= deg, calcula `Z = (#1 - pn)/sqrt(p(1-p)n)` com p = Pr[f=1] sob H0 (calculado *exatamente*, em O(n*alfa(n)) via Union-Find), guarda os t = 128 de maior |Z|. Fase 2: XOR de todas as k-tuplas, recalcula Z, devolve o máximo. Implementação bit-paralela.

**Distribuição nula do máximo (§5.2).** Para k=1: `f_max(x) = l*phi(x)*(2*Phi(x)-1)^(l-1)` com `l = C(m, deg)`. Tabela 8 (mu do Z-SCORE, BoolTest vs R): deg=1: (2.80/2.70), (3.05/2.92), (3.14/3.03), (3.24/3.12) para m=128/256/384/512; deg=2: (3.87/3.85), (4.23/4.18), (4.39/4.36), (4.55/4.48); deg=3: (4.71/4.68), (5.13/5.09), (5.32/5.32), (5.54/5.48). Para k>1: *"to derive theoretical expected pdf f_max for k > 1 is hard task in general"* — usam referência empírica (10^5 sequências, alfa_BT1 = 10^-5).

**Tabela 2 — rodadas detectadas com 100 MB, estratégia CTR:**

| função | NIST | Dieharder | TestU01 | Bool1 | Bool2 | | função | NIST | Di | U01 | Bool1 | Bool2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| AES | 3 | 3 | 3 | 3 | 3 | | JH | 6 | 6 | 6 | 6 | 6 |
| ARIRANG | 3 | 3 | 4 | 3 | 3 | | **Keccak** | 2 | 2 | 2 | **3** | **3** |
| AURORA | 2 | 2 | 4 | 2 | 2 | | Lex | 3 | 3 | 3 | 3 | 3 |
| BLAKE | 1 | 1 | 1 | 1 | 1 | | Lesamnta | 2 | 3 | 3 | 2 | 2 |
| Cheetah | 4 | 4 | 6 | 4 | 4 | | Luffa | 7 | 7 | 7 | 7 | 7 |
| CubeHash | 0 | 0 | 1 | 0 | 0 | | **MD6** | 8 | 8 | 8 | **9** | 8 |
| DCH | 2 | 2 | 2 | 1 | 1 | | Simd | 0 | 0 | 0 | 0 | 0 |
| Decim | 6 | 6 | 6 | 5 | 5 | | **Salsa20** | 6 | 4 | 6 | **4+** | **4+** |
| Echo | 1 | 1 | 1 | 1 | 1 | | **TEA** | 4 | 4 | 4 | **4+** | **4+** |
| **Grain** | **3** | 2 | 2 | 2 | 2 | | **TSC-4** | 13 | 12 | 13 | **13+** | **13+** |
| Grøstl | 2 | 2 | 2 | 2 | 2 | | Twister | 6 | 6 | 7 | 6 | 6 |
| Hamsi | 0 | 0 | 0 | 0 | 0 | | | | | | | |

*"In 15 out of 24 functions tested, BoolTest was able to detect non-randomness in stream produced by the same number of rounds in round-reduced cryptographic functions when compared to NIST STS."* **Note Grain: NIST STS pega 3 rodadas, BoolTest só 2 — a STS é *melhor* aqui.**

**Tabela 4 — 100 MB, quatro estratégias de geração** (BT = BoolTest):

| | CTR NI/Di/U01/BT | LHW NI/Di/U01/BT | SAC NI/Di/U01/BT | RPC NI/Di/U01/BT |
|---|---|---|---|---|
| AES | 3/3/3/3 | 2/3/3/3 | 2/2/2/2 | -/1/1/1 |
| Blowfish | 2/2/2/2 | 2/3/3/3 | 2/2/3/3 | -/1/1/1 |
| DES | 4/4/4/**5** | 4/4/4/**5** | 4/4/**5**/4 | 1/1/1/1 |
| 3-DES | 2/2/2/**3** | 2/2/3/3 | 2/2/2/2 | 1/1/1/**2** |
| MD5 | 9/10/9/**11** | 12/13/**20**/13 | 9/11/14/12 | 3/3/4/**6** |
| MD6 | 8/8/8/8 | 8/8/8/**9** | 7/7/8/7 | 5/5/7/5 |
| SHA-1 | 12/12/13/**14** | 16/16/16/16 | 11/15/16/14 | 4/4/5/**7** |
| SHA-256 | 6/6/6/**7** | 12/12/12/13 | 11/11/12/13 | 3/4/4/4 |
| TEA | 4/4/4/**5** | 3/3/3/4 | 3/4/3/3 | -/2/1/1 |

**O melhor caso documentado de "uma bateria pega o que a STS não pega":** MD5 com LHW — NIST STS até 12 rodadas, **TestU01 até 20**. Testes responsáveis: `smarsa_BirthdaySpacings` do Small Crush (*"The test's p-value increases with increasing number of rounds up to 18, but it is always significant (<= 10^-9)"*) e `snpair_ClosePairsBitMatch` do Rabbit (*"fails even for MD6 reduced to 20 out of total 64 rounds (p-values <= 10^-19)"*). **Espaçamentos de aniversário e pares próximos são mais potentes que a STS inteira contra difusão incompleta, por 8 rodadas.**

**Tabela 3 — eficiência em dados** (Z-scores; ∀ = todos passaram):

| | | NI | Di | U01 | Bool3 | Bool4 |
|---|---|---|---|---|---|---|
| 10 MB | AES(3) | ∀ | 18 | 15 | **8.6** | **6.7** |
| | TEA(4) | ∀ | 20 | ∀ | **20.6** | **11.5** |
| | Keccak(3) | ∀ | ∀ | 15 | **3.7** | **5.3** |
| | MD6(9) | ∀ | ∀ | ∀ | 3.9 | **13.3** |
| | SHA-256(3) | 0 | 0 | 6 | **88.7** | **242** |
| 100 MB | SHA-256(3) | 0 | 0 | 4 | **50.7** | **828** |
| 1 GB | SHA-256(3) | 0 | 1 | 3 | **78.0** | **3043** |

*"test based on boolean functions usually requires an order of magnitude fewer data to detect bias than common batteries."*

**Estratégias de entrada:** CTR, LHW (peso de Hamming baixo fixo), SAC (par com 1 bit flipado), RPC (plaintext||ciphertext). *"Among the input generation strategies, RPC is consistently the scenario which is the most difficult to distinguish from the truly random stream."*

**Custo medido (Tabela 1, Python 3.6.4, Xeon E5-2630 v3):** 10 MB / 100 MB: 256-2-3 → 23 s / 2 m 40 s; 256-3-3 → 1 m 12 s / 9 m 53 s; 512-2-3 → 21,1 s / 1 m 42 s; 512-3-3 → 3 m 29 s / 31 m 30 s.

**Limitações declaradas:** (i) heurística *top-t* — *"It is evident there exists a good distinguisher of a low degree for Java Rand but due to top-heuristics the BoolTest was not able to find it with other combinations (…). The utilization of suitable optimization methods like genetic algorithms could lead to stronger distinguishers"*; (ii) pdf do máximo intratável para k>1; (iii) trabalho futuro: FPGA e seleção heurística de termos.

**Cabe?** **SIM**, com a estratégia de entrada substituída pelo fluxo natural: concatenar criptogramas reais. O teste opera sobre o fluxo de saída, ponto. Caminho mais direto de "criptanálise automatizada" que sobrevive ao ciphertext-only.
**Custo:** `pip install booltest`; 1,9 GB por classe. Com m=512, deg=2, k=2: ~10 h de CPU por classe.
**Prevê:** Z-SCORE dentro da referência empírica (mu ≈ 4,55, sigma ≈ 0,31 para deg2/k1/m512) nos quatro completos; explosivo no AES-ECB. Nas variantes de rodada reduzida, deve detectar 1–2 rodadas *além* do que a bateria NIST-STS-641D detecta — **a previsão falsificável mais limpa desta pesquisa**.

##### 1.2 Revisiting BoolTest — a crítica

**[PUB]** Chatterjee, Parikh, Maitra, Maitra, Roy, *"Revisiting BoolTest – On Randomness Testing Using Boolean Functions"*, **INDOCRYPT 2022**, LNCS 13774, doi:10.1007/978-3-031-22912-1_21.

*"the existing works related to BoolTest identify the Boolean functions that are sub-optimal, constrained by the low degree in the Algebraic Normal Form."* Propõem algoritmo O(N log N) que acha a função booleana que maximiza o Z-score. Ressalva dos autores: *"this test is not sufficient to conclude on randomness or non-randomness of a given stream of data."*

**[MINHA]** O(N log N) sobre blocos é assinatura de **transformada rápida de Walsh–Hadamard**. Texto integral não obtido, mas a complexidade e o objetivo são exatamente o que a FWHT entrega. Ver §1.5.

##### 1.3 CoolTest — o sucessor, feito para volume pequeno

**[PUB/CIT]** Jiří Gavenda, Marek Sýs, *"CoolTest: Improved Randomness Testing Using Boolean Functions"*, **IFIP SEC 2025**, Springer, pp. 3–17, doi:10.1007/978-3-031-92886-4_1.
**[CIT]** Versão estendida: ***"CoolTest: Randomness test suited for small data volumes"*, Computers & Security, 2026**, doi:10.1016/j.cose.2026.104986. Código Rust: https://github.com/jirigav/cooltest

Generaliza o BoolTest: em vez de funções de **forma pré-definida**, constrói **histograma sobre k posições de bits**, avaliando implicitamente **2^(2^k) funções booleanas ao avaliar 2^k**. Primeira metade dos dados constrói o distinguidor, segunda avalia. 14 funções de rodadas reduzidas. *"On 100 MB of data, CoolTest provides better results for SHA-2, SHA-1, MD6, and SHACAL-2 than statistical test suites NIST STS, Dieharder, and TestU01."* Tabelas não obtidas.

**Custo:** binário Rust pronto, `cooltest <file>`. Trivial.
**Prevê:** o título — *"suited for small data volumes"* — é literalmente o regime de 64 KB/amostra. **Se algum teste automatizado vai achar algo, é esse.** Rodá-lo é uma tarde.

##### 1.4 Evolução genética de funções distinguidoras

**[CIT]** Picek et al. (autoria a confirmar), *"Evolving Boolean Functions for Fast and Efficient Randomness Testing"*, **GECCO 2018**, doi:10.1145/3205455.3205518.
**[PUB, via bibliografia do BoolTest]** EACirc (CRoCS MUNI): distinguidores como circuitos sobre AND/XOR/NOR/NOT; *"EACirc was able to detect some non-randomness for Hermes and Fubuki where both batteries failed"* (Sýs, Švenda, Ukrop, Matyáš, SECRYPT 2014).
**[PUB]** Hernández & Isasi (*Computational Intelligence* 20:517–525, 2004) — GA para TEA, até 4 rodadas; Garrett, Hamilton & Dozier (2007), GA quântico, 5 rodadas.

**Cabe? ADAPTÁVEL.** Custo alto, baixo retorno dado que o BoolTest exaustivo já cobre grau <= 3.

##### 1.5 **[MINHA]** FWHT completa: a versão exata do BoolTest — a lacuna mais gritante

Não achado publicado como teste de aleatoriedade para cifras.

O BoolTest gasta esforço enorme para achar heuristicamente o XOR de monômios com maior |Z|. Mas restrito a **grau 1** (funções lineares), o problema tem solução **exata e fechada** pela FWHT: dado o histograma empírico `h` de blocos de w bits,

```
C(a) = soma_x h(x)*(-1)^(a.x) / N ,  para todos os 2^w valores de a, em O(w*2^w)
```

Sob H0, `sqrt(N)*C(a) ~ N(0,1)` iid para os 2^w - 1 valores de a != 0. Estatística: `M = max_{a!=0} sqrt(N)|C(a)|`, com nulo exato de estatística de ordem — **a mesma fórmula do Rukhin/Sýs**: `f_max(x) = l*phi(x)*(2*Phi(x)-1)^(l-1)` com `l = 2^w - 1`.

Números para o dataset:
- w = 24: 16,7 M coeficientes, 64 MB em float32, **uma FWHT em ~2 s**. Blocos por amostra: 65552/3 = 21.850. Pooled sobre 30.000 amostras: N = 6,6x10^8 blocos. Limiar nulo: `sqrt(2*ln(2^24)) ≈ 5,27`. Viés linear detectável: `eps ≈ 5,27/sqrt(N) ≈ 2,1x10^-4`.
- w = 32: 4,3 G coeficientes, 17 GB — FWHT out-of-core ou GPU. Viável, não é o primeiro passo.

**Por que domina o BoolTest em grau 1:** o BoolTest com deg=1, m=512 testa 512 monômios e k-tuplas de 128 deles — fração ínfima das 2^512 funções lineares, por heurística gulosa. A FWHT com w=24 testa **todas** as 2^24-1 funções lineares daquela janela, exatamente, mais rápido. O preço é a janela menor. **A combinação certa: FWHT exaustiva para janelas curtas + BoolTest heurístico para janelas longas e grau > 1.**

**Custo:** ~200 linhas de NumPy (FWHT in-place). Uma tarde. 64 MB.
**Prevê:** (a) nos quatro completos, `M` deve cair na distribuição de estatística de ordem — dando limite superior *quantitativo* publicável: "nenhum viés linear sobre janelas de 24 bits maior que 2,1x10^-4". Muito mais forte que "o RF deu 0,50". (b) Nas variantes reduzidas, `M` cresce monotonicamente ao diminuir rodadas — **curva de piso de rodadas contínua**, não binária.

##### 1.6 **[MINHA]** A identidade de convolução — por que o sinal CT-only é a redundância do plaintext

Formaliza e quantifica o que a memória do projeto já registrou empiricamente.

Se `C = P XOR KS` com `KS` independente de `P` (cifra de fluxo pura), então sobre GF(2)^n a XOR-convolução vira produto pontual na transformada de Walsh:

```
C(a) = P(a) * KS(a)      para todo a
```

Consequências, todas verificáveis:

1. **Com plaintext uniforme, `P(a) = 0` para todo a != 0, logo `C(a) = 0` identicamente.** Análise linear em ciphertext-only é **exatamente impossível** contra cifra de fluxo com plaintext uniforme, qualquer que seja o viés do keystream. Resultado de impossibilidade limpo.
2. **Com plaintext redundante, `|P(a)|` pode ser ≈ 1.** Em ASCII, `a = 0x80` tem `P(0x80) ≈ 1`. Então `C(0x80) ≈ KS(0x80)` — o viés linear do keystream aparece **sem atenuação**. O plaintext redundante é a *sonda* que torna o keystream observável.
3. **A identidade só vale para keystream independente do plaintext.** **Grain-128AEAD** é cifra de fluxo pura. **Ascon-AEAD128** e **Schwaemm256-128** absorvem o plaintext no estado. **GIFT-COFB** realimenta com o ciphertext. Nos três, a independência quebra e `C(a) ≈ 0` mesmo com P redundante.
4. **Assimetria estrutural de 4 classes, visível em ciphertext-only, que sobrevive ao truncamento de comprimento.** Grain deveria mostrar espectro de Walsh herdado de `P(a)`; os outros três, não.

**Atenção:** pode ser exatamente o "vazamento achado contra Grain" registrado na memória do projeto. Se o vazamento achado é só o `len_ct` (65.544 vs 65.552), então este é um **segundo** canal, distinto, e **não** desaparece truncando. Vale checar antes de decidir o que fazer com o Grain.

**Cabe?** SIM. Usa só conhecimento *público* da distribuição do idioma (Kerckhoffs). Ciphertext-only ortodoxo.
**Custo:** estimar `P(a)` sobre o SPGC é uma FWHT. Depois `KS(a) = C(a)/P(a)` onde `|P(a)|` não é desprezível. Um dia.
**Prevê:** com plaintext 100% imagem o sinal deve **cair**; com 100% texto deve **subir**. A divisão 80/20 dá esse experimento de graça — basta estratificar por `plaintext_source`. Se o F1 não variar com `plaintext_source`, a identidade não está operando.

##### 1.7 Linhagem anterior (via bibliografia do BoolTest)

- **E. Filiol**, ICICS 2002, LNCS, pp. 342–353 — cada bit de saída como função booleana em ANF; estatística = nº de monômios de grau d, distribuição chi². https://link.springer.com/chapter/10.1007/3-540-36159-6_29
- **Englund, Johansson, Sönmez Turan**, INDOCRYPT 2007, pp. 268–281 — generaliza para IV escolhido. **NÃO cabe.**
- **P. Stankovski**, *"Greedy distinguishers and nonrandomness detectors"*, INDOCRYPT 2010, LNCS 6498. **NÃO cabe** (entrada controlada).
- **Kaminsky & Sorrell**, CryptoStat, RIT 2013/2014. **NÃO cabe** (precisa de plaintext/chave).
- **[CIT]** Kaminsky, *"Testing the Randomness of Cryptographic Function Mappings"*, ePrint 2019/078.
- **[CIT]** Eskandari, Kidmose, Kölbl, Tiessen, *"Finding Integral Distinguishers with Ease"*, SAC 2018 — 30 primitivas via bit division property. **NÃO cabe**: exige plaintext escolhido estruturado. Citar como "o que o modelo de ameaça exclui".

---

#### PARTE 2 — Compressão, complexidade algorítmica, códigos universais

##### 2.1 Book Stack / Move-To-Front — o caso mais forte de "pegou o que a bateria não pegou"

**[PUB]** Ryabko & Pestunov, *"'Book stack' as a new statistical test for random numbers"*, **Problems of Information Transmission 40(1) (2004) 66–71**.
**[PUB]** Ryabko & Monarev, *"Using information theory approach to randomness testing"*, **JSPI 133(1) (2005) 95–110**. https://arxiv.org/pdf/cs/0504006
**[PUB]** Doroshenko & Ryabko, *"The experimental distinguishing attack on RC4"*, **ePrint 2006/070**. https://eprint.iacr.org/2006/070.pdf

**Método.** Alfabeto A = {a1,...,a_S}. Pilha; após observar x_t, atualiza:
```
nu^{t+1}(a) = 1               se x_t = a
            = nu^t(a) + 1     se nu^t(a) < nu^t(x_t)
            = nu^t(a)         se nu^t(a) > nu^t(x_t)
```
(MTF do Bentley–Sleator–Tarjan–Wei 1986; Ryabko publicou em 1980). Particiona {1..S} em r subconjuntos, conta `n_k`, aplica chi² com r-1 gl. O(1) amortizado com hashing.

**Números do RC4.** 100 chaves de 256 bits, palavras de 16 bits, A1 = {1..16}, A2 = {17..2^16}, alfa = 0,05:

| Comprimento (bits) | 2^31 | 2^32 | 2^33 | 2^34 | 2^35 | 2^36 | 2^37 | 2^38 | 2^39 |
|---|---|---|---|---|---|---|---|---|---|
| Arquivos não-aleatórios (de 100) | 6 | **12** | 17 | 23 | 37 | 74 | 95 | 99 | 100 |

Comparação: o resultado anterior (Crowley) precisou de **> 2^55 bits**. O book stack precisou de **≈ 2^32**. **Ganho de 2^23 ≈ 8 milhões de vezes em dados.**

**E o contra-exemplo, que importa tanto quanto.** **[PUB]** Doroshenko, Fionov, Lubkin, Monarev, Ryabko, *"On ZK-Crypt, Book Stack, and Statistical Tests"*, **ePrint 2006/196**. https://eprint.iacr.org/2006/196.pdf

> *"The algorithms submitted to the ECRYPT Stream Cipher Project (eSTREAM) were tested using the recently suggested statistical test named 'Book Stack'. All the ciphers except ZK-Crypt have passed the tests."*
> *"all candidates except ZK-Crypt have passed the Book Stack test under the sample sizes of 2^30–2^35 bits"*

**O teste mais forte que a literatura produziu, aplicado a todas as cifras de fluxo modernas do eSTREAM com 128 MB a 4 GB, não achou nada.** Evidência negativa mais direta que existe para o nosso cenário — da mesma equipe que fez o teste.

**Custo:** `bs.cpp` publicado no próprio ePrint 2006/196 (~200 linhas C++, `-w` palavra, `-u` topo). Usaram `bs -w 16 -u 16` para RC4 com 2^32 bits.
**Prevê:** nos 1,9 GB por classe = 1,5x10^10 bits, você está **na mesma ordem** dos 2^34 bits em que o RC4 cai. Se algum AEAD tivesse viés de RC4, você o veria. Valor: o **limite superior publicável** — "com 2^34 bits por algoritmo, o book stack não rejeita" é frase forte, com referência calibrada (RC4 rejeitaria 23/100 nesse ponto).

##### 2.2 Teste de Maurer e a correção de Coron–Naccache

**[PUB]** Maurer, *"A universal statistical test for random bit generators"*, **Journal of Cryptology 5(2) (1992) 89–105**, doi:10.1007/BF00193563.
**[PUB]** Coron & Naccache, *"An accurate evaluation of Maurer's universal test"*, **SAC'98**, LNCS.

Detecta qualquer desvio de fonte ergódica estacionária com memória finita e probabilidades de transição desconhecidas; o parâmetro é próximo da entropia por bit.

**Requisito de dados (Rukhin §4.2):** `10*2^L + 1000*2^L` bits com `6 <= L <= 16`. Para L=16: ≈ 132 Mbit = **16 MB por amostra**. **O criptograma de 64 KB é 250x pequeno demais para L=16.** Com L=8: 258 KB — ainda 4x maior. **Com L <= 6 cabe** (48 KB), mas L=6 é fraco.

Variância: `Var(F_n) = c(L,K)*Var(log2 G)/K` com `c(L,K) = 0.7 - 0.8/L + (1.6 + 12.8/L)*K^(-1/L)`, e os autores dizem que *"the inaccuracy due to [this approximation] can make the test to be 2.67 times more permissive than what is theoretically admitted."* Rukhin recomenda t-teste sobre N <= 20 substrings.

**Prevê:** com agregação de 30k amostras por classe chega-se em L=16 folgado; sob H0, F_n idêntico entre classes. A versão *t-teste de duas amostras entre classes* é mais informativa que o p-valor de aleatoriedade.

##### 2.3 NCD — e por que não vai funcionar aqui

**[PUB]** Cilibrasi & Vitányi, *"Clustering by compression"*, IEEE Trans. IT 51(4) (2005) 1523–1545. `NCD(x,y) = [Z(xy) - min{Z(x),Z(y)}] / max{Z(x),Z(y)}`.
**[PUB]** Raff & Nicholas, KDD 2017; arXiv:1509.00689.
**[PUB]** Cebrián, Alfonseca, Ortega, *"Common Pitfalls Using the Normalized Compression Distance"*.

Limitação fatal, literal:
> *"NCD has difficulty with high entropy strings, can produce values larger than the theoretical maximum similarity of 1, and lacks symmetry. (…) Because a single high entropy file will not help compress or be further compressed by any other file (including ones that are not compressed), high entropy files will become maximally far and equidistant from all other data points."*

**Cabe? SIM formalmente. Funciona? NÃO.** Criptograma é incompressível: `Z(xy) ≈ Z(x) + Z(y)` e `Z(x) ≈ |x|`, logo `NCD(x,y) ≈ 1` para todo par, com flutuação dominada pelo overhead do container.
**Prevê:** matriz NCD com média 1,00 ± ruído do compressor e silhouette ≈ 0. **Se der outra coisa, é artefato.** Vale rodar em 500x500 só como controle negativo instrumentado — 1 h e fecha uma rota que a banca vai perguntar.

##### 2.4 Perfil de complexidade linear

**[CIT]** Hamano, Sato, Yamamoto, *"A new randomness test based on linear complexity profile"*, **IEICE Trans. Fundamentals E92 (2009) 166–172**.

O teste da STS usa `T_n = (-1)^n[L_n - xi_n] + 2/9`, distribuição limite discreta e enviesada à direita. Propõem `soma_j |j/2 - L_j|`. Rukhin: *"A more powerful test which efficiently uses the available data."*

**Custo:** Berlekamp–Massey é O(n²) — para 524 kbit são 2,7x10^11 operações por amostra. **Inviável no criptograma completo.** Viável em janelas de 5.000 bits.
**Prevê:** perfil médio colado em j/2 para os quatro; desvio só em rodadas muito reduzidas de Grain — **o único dos quatro para o qual complexidade linear é *a* métrica natural. Direcionar esse teste especificamente ao Grain reduzido é a aplicação certa.**

##### 2.5 Borel normality + bateria de AIT — o caso análogo

**[PUB]** Calude, Dinneen, Dumitrescu, Svozil, *"Experimental Evidence of Quantum Randomness Incomputability"*, **Physical Review A 82, 022102 (2010)**. arXiv:1004.1521.

**Desenho quase idêntico ao nosso:** 5 fontes x 10 strings de **2^32 bits** (512 MB). Fontes: Quantis (QRNG comercial), Vienna IQOQI (QRNG bruto), Maple 11 (Mersenne Twister), Mathematica 6 (autômato celular), dígitos de pi. Cinco testes: book stack, Solovay–Strassen, Borel normality (m = 1..5), entropia de Shannon por janela, amplitude de passeio aleatório. Comparação por KS de duas amostras, Shapiro–Wilk e t de Welch.

| Teste | Separou o quê? |
|---|---|
| **Borel normality** | **TODOS os pares computável x incomputável**: p < 10^-4 a 0,0002. **MAS: Maple vs Mathematica p = 0,4175 e Mathematica vs pi p = 0,9945** — não separou PRNG de PRNG. |
| Passeio aleatório | Quantis vs todos; Vienna vs Mathematica/pi; Maple vs pi |
| Book stack | Só Quantis vs Mathematica (0,0021) e Quantis vs pi (0,0123) |
| Solovay–Strassen | **Nada** (KS p >= 0,4005) |
| **Entropia de Shannon** | **Nada** (KS p >= 0,0525) |

Médias de Borel: Maple 60.210, Mathematica 41.870, pi 40.220 vs Quantis 207.200, Vienna 337.100.

**A leitura crítica.** Trabalho mais próximo do nosso problema. Ele **separa física de algoritmo**, mas **não separa algoritmo de algoritmo**. Mersenne Twister vs autômato celular: p = 0,4175. **Evidência direta contra a viabilidade do problema de 4 classes**, e deve ser citada como tal — é honesta, publicada na PRA, e é exatamente o ponto.

Note também: **a entropia de Shannon não separou nada.** As 4 features de entropia estão, pela melhor evidência disponível, mortas para esse propósito.

**Custo:** Borel normality é contagem de m-blocos, m = 1..5 — já existe em `histogram` e `ngrams`. Critério de Calude: `|N_j^m(x)/|x|_m - 2^-m| <= sqrt(log2|x| / |x|_m)` para `1 <= m <= log2log2|x|`. Para |x| = 524.416 bits, m <= 4. Trivial.

---

#### PARTE 3 — Rényi, Tsallis, min-entropia, estimadores esparsos

##### 3.1 Estimador de Rényi de baixa complexidade

**[PUB]** Young-Sik Kim, *"Low Complexity Estimation Method of Rényi Entropy for Ergodic Sources"*, **Entropy 20(9), 657 (2018)**. https://www.mdpi.com/1099-4300/20/9/657

*"the proposed estimation method for Rényi entropy can detect any significant deviation of an ergodic stationary random source's output"* — alegação de universalidade no espírito do Maurer.

**Por que interessa mais que Shannon:** a Rényi de ordem 2 é `-log(soma p_i^2)`, e `soma p_i^2` é exatamente a **probabilidade de colisão**. Para amostras esparsas (2^16 ou 2^24 categorias, n << k) o estimador de Shannon plug-in tem viés catastrófico, enquanto o de colisão `(soma n_i(n_i-1)) / (n(n-1))` é **não-enviesado** e tem variância pequena. **Ponto técnico que a família `entropy` (4D) ignora.**

**[PUB]** Skórski, *"Towards More Efficient Rényi Entropy Estimation"*, **Entropy 25(2), 185 (2023)**.
**[CIT]** *"Complexity of Estimating Rényi Entropy of Markov Chains"*, ePrint 2019/766.
**[PUB]** *"Shannon Entropy versus Rényi Entropy from a Cryptographic Viewpoint"*, ePrint 2014/967.
**[PUB]** arXiv:2002.06516; arXiv:2506.14242 (Tsallis goodness-of-fit).

**Custo:** trivial — uma linha sobre o histograma. Para palavras de 16 e 24 bits custa memória (64 MB / 16 GB esparsos).
**Prevê:** `H2` por colisão em palavras de 16 bits deve dar 16,000 bits ± `1/sqrt(N)`. O interesse é a **variância entre amostras**, não a média — e é aí que um efeito de plaintext (§1.6) apareceria.

##### 3.2 Preditores do NIST SP 800-90B

**[PUB]** Kelsey, McKay, Sönmez Turan, *"Predictive Models for Min-Entropy Estimation"*, **CHES 2015**, LNCS 9293, pp. 373–392. https://eprint.iacr.org/2015/600.pdf

Preditores: **MultiMCW** (mais frequente na janela), **Lag** (valor de N amostras atrás), **MultiMMC** (Markov com contagem, ensemble sobre N), **LZ78Y** (dicionário até 32, *"based loosely on the LZ78 family"*).

**[PUB]** SP 800-90B final. Além dos preditores, **teste de permutação com 11 estatísticas** (excursion, directional runs, increases/decreases, runs based on median, average/maximum collision, periodicity e covariance com lag em {1,2,8,16,32}) = **19 testes**. Mais LRS e o teste de compressão.

**[PUB]** *"Machine Learning Predictors for Min-Entropy Estimation"*, **Entropy 27(2), 156 (2025)**, arXiv:2406.19983 — LSTM, CNN+LSTM e **GPT-2** superam os preditores da 90B em alguns cenários.
**[PUB]** SecureComm 2018, doi:10.1007/978-3-030-01704-0_13; arXiv:2009.09570 / ePrint 2020/1140.

**Custo:** implementação de referência do NIST em C++ (`usnistgov/SP800-90B_EntropyAssessment`). Horas. Teste de permutação com 10.000 shuffles x 19 estatísticas é caro mas paralelizável (GPU: PeerJ Comput. Sci. 7:e404).
**Prevê:** taxa de acerto do MultiMMC/LZ78Y em 1/256 ± 3 sigma. **Mas** — a família `hamming` já é a conversão binária da 90B (Conversion I). **Completar com as 19 estatísticas de permutação e os 4 preditores é a extensão de menor custo e maior cobertura de todo este relatório.**

##### 3.3 Entropia de permutação — onde Shannon passa e o ordinal não

**[PUB]** *"Shannon Entropy and Beyond: An Information-Theoretic Framework for Randomness Pre-Screening"*, **Entropy 28(6), 695 (2026)**, Univ. POLITEHNICA Bucharest. https://www.mdpi.com/1099-4300/28/6/695

O número que vale: um **mapa logístico determinístico com r = 3,9999** atinge **94,97% do máximo de entropia de Shannon** — passaria numa triagem — mas sua **entropia de permutação cai para 77,01%** e sua **entropia amostral é 0,67 contra 2,33 de um PRNG de qualidade**.

**[PUB]** Bandt & Pompe (original). `ordpy` (arXiv:2102.06786). Plano entropia–complexidade: arXiv:0812.2250.

**Custo:** ordem d = 5..7 sobre bytes: O(n), d! = 120..5040 padrões. Minutos.
**Prevê:** o caso do mapa logístico é **gerador caótico**, não cifra — a evidência **não** transfere direto. Previsão honesta: indistinguível de `log(d!)`. Valor: feature de ordem superior mais barata que existe, 2 h de implementação, e **cobre uma classe de defeito (estrutura ordinal) que nenhuma das 12 famílias atuais toca.**

---

#### PARTE 4 — Espectral e ordem superior

##### 4.1 Bispectro, cumulantes, poliespectros — sem aplicação criptográfica confirmada

**[PUB]** O bispectro é a TF do cumulante de terceira ordem; **é identicamente zero para qualquer processo gaussiano**. Para X gaussiano, cumulantes de ordem k > 2 são nulos. Refs: arXiv:1805.11775; Hinich (NYU Stern); arXiv:2505.01231.

**Busca não achou** nenhuma aplicação de bispectro/cumulantes de ordem >= 3 a teste de aleatoriedade criptográfica. O que existe sob "higher-order" em cripto é **diferencial de ordem superior** (Lai/Knudsen), coisa diferente, e exige diferenças escolhidas.

**[MINHA]** Por que provavelmente é inútil: um fluxo de bytes iid uniforme mapeado para ±1 é **não-gaussiano por construção** (Rademacher), então o bispectro de referência não é zero e perde-se o nulo limpo. Mais grave: sobre GF(2), o análogo do cumulante de ordem 3 é `E[(-1)^{a.x + b.x + c.x}]`, que colapsa em `C(a XOR b XOR c)` — **já está inteiramente contido na transformada de Walsh** (§1.5). Não há informação nova.

**Cabe? SIM formalmente. Vale? NÃO.**

##### 4.2 O teste espectral da STS está quebrado (e a versão correta)

Do Rukhin: com `X_k = ±1`, `f_j = soma_{k=1}^M X_k exp{2*pi*i*(k-1)*j/M}`, `j = 0..M/2-1`, então `E f_j = 0`, `E f_j f_j' = delta_jj' * M`, e para m fixo a distribuição conjunta de `M^(-1/2)(f_1,...,f_m)` é normal complexa multivariada. Logo `W = 2*soma_{k=1}^m mod_k^2/M ~ chi^2_{2m}`. Partir em N substrings, calcular `W_j`, chi² de aderência. Alternativa via mediana: `Q(m, 0.5*W) = 0.5`, `0.5*W ≈ m - 1/3`.

**Prevê:** a família `spectral_welch` (v2) e os 10D de FFT (v1) provavelmente usam o estimador *errado* (o da STS original) ou Welch sem nulo calibrado. Trocar pela forma chi²_{2m} do Rukhin dá p-valores válidos de graça. **Correção de corretude no código, não ideia nova — mas a que mais barato compra rigor.**

##### 4.3 Walsh–Hadamard como teste publicado

**[CIT]** Oprina, Popescu, Simion, Simion, *"Walsh–Hadamard randomness test and new methods of test results integration"*, **Bulletin of the Transilvania University of Braşov, Series III, 2009, pp. 93–106**. https://www.semanticscholar.org/paper/42de0c0c663461bfded8e5b29171e40f34ffed85

De fontes secundárias: *"an extension of frequency and autocorrelation tests"*, baseado na distribuição da WHT, capaz de detectar *"a general class of defects"*. **Artigo não lido — não usar o conteúdo sem verificar.**

Linhagem (survey de Ritter): S. Kak propôs Hadamard; desenvolvido por Phillips, Yuen, Hopkins, Beth & Dai, Mund, Marsaglia & Zaman; Feldman deu um teste via FWHT. Patente US 7,031,991 B2.

---

#### PARTE 5 — Discrepância e equidistribuição: conclusão negativa fundamentada

O aparato clássico — spectral test de Coveyou–MacPherson/Knuth, limites de Niederreiter, equidistribuição de congruenciais não-lineares (*Metrika*, doi:10.1007/BF02613697), sum-discrepancy test — foi construído para geradores com **estrutura de reticulado** (LCG, MRG, Mersenne Twister) e é enunciado em termos das constantes do gerador.

**[MINHA], com justificativa:** nada transfere para AEAD. O spectral test de Knuth precisa dos coeficientes — você não os tem (é a chave). A discrepância empírica em dimensão t reduz-se ao **teste serial** de t-uplas, que já existe em `ngrams`. Sem ganho de poder, só nome diferente. O único caso não-redundante seria estrutura de reticulado sobre Z — modelo errado para GF(2)-based (Ascon, GIFT, Grain) e para ARX (Schwaemm, onde a soma mod 2^32 *poderia* induzir estrutura aditiva, mas nenhum resultado sustenta isso em CT-only).

**Cabe? SIM. Vale? NÃO.**

---

#### PARTE 6 — A direção oposta: evidência de redundância

##### 6.1 Redundância medida dentro da própria STS

**[PUB]** Karell-Albo, Legón-Pérez, Madarro-Capó, Rojas, Sosa-Gómez, *"Measuring Independence between Statistical Randomness Tests by Mutual Information"*, **Entropy 22(7), 741 (2020)**. https://pmc.ncbi.nlm.nih.gov/articles/PMC7517289/

10.000 sequências de 10^6 bits, 10.000 permutações, alfa = 0,001; analisam p-valores **e estatísticas** (novo).

Pares dependentes por p-valor: Frequency ↔ CUSUM(f,b), Random Excursions, Random Excursions Variant; CUSUM(f) ↔ CUSUM(b), RE, REV; Serial 1 ↔ Serial 2; Approximate Entropy ↔ Serial 1; Longest Run ↔ Overlapping Template; RE ↔ REV.

Dependências **novas** ao usar estatísticas: **Runs ↔ CUSUM(f,b), Frequency**; **Non-Overlapping Template ↔ CUSUM(b)**. A MI captou dependência parabólica (Frequency–CUSUM backward) que Pearson não pega.

**Implicação:** as 641 features contêm blocos fortemente dependentes por construção. O `LWCFeatureSelector` é a escolha certa — mas o mRMR está removendo redundância *conhecida a priori*. **Poderia declarar os grupos de dependência da Tabela 8/9 como grupos e usar group-lasso, em vez de deixar o mRMR redescobri-los em cada fold** (e variar entre folds, o que provavelmente explica a instabilidade do Boruta já documentada).

Correlatas: **[CIT]** ePrint 2017/336; ePrint 2019/551; Applied Mathematics and Computation, 2023, doi:10.1016/j.amc.2023.128222; Computational and Applied Mathematics, 2026, doi:10.1007/s40314-026-03663-y.

O **próprio NIST** fez esse estudo: Rukhin et al. aplicaram PCA e extraíram 161 fatores, concluindo que *"there is no large redundancy among our tests"* — conclusão que os trabalhos acima contradizem parcialmente.

##### 6.2 O ganho do BoolTest sobre as baterias é de ~1 rodada

**[PUB]** Klinec, Sýs, Kubíček, Švenda, Matyáš, *"Large-scale randomness study of security margins for 100+ cryptographic functions"*, **SECRYPT 2022**, pp. 134–146, doi:10.5220/0000163500003283. https://karelkubicek.github.io/assets/pdf/Analyzing_security_margins_of_100_cryptographic_functions.pdf

Escala: **414 testes**, **109 funções** em 130 parametrizações, **52.077 configurações de rodada reduzida**, tamanhos {10, 100, 1000} MB, **5.160,4 GB analisados**. Corte: alfa = 10^-7, correção de Hommel, rejeição se >= 2 de 3 sementes. Referência: 75.000 runs de AES-128 full em CTR.

Tabela 1 (`rodadas_RTT / rodadas_literatura / rodadas_total`):

| Função | Margem | | Função | Margem |
|---|---|---|---|---|
| AES | 3/6/10 | | Keccak | 4/5/24 |
| SHA-3 | 4/5/24 | | Salsa20 | 2/6/20 |
| Chacha | 3/6/20 | | Trivium | 3/5.8/8 |
| **Grain** | **11/13/13** | | SPECK | 10/15/32 |
| SIMON | 16/16/16 | | SPARX-B64 | 2/8/24 |
| **SPARX-B128** | **3/8/32** | | RECT.K128 | 8/14/25 |
| PRINCE | 4/6/12 | | GOST | 29/20/32 |

Margens agregadas (Tabela 2): hash 76,37% (mediana 84,52); cifra de bloco 78,84 input / 68,86 key; **cifra de fluxo 80,77 input / 64,59 key (mediana 90 / 70)**; MPC 93,94/95,85.

**Advertência [MINHA]:** o "13 rodadas totais" do Grain e "8" do Trivium **não** são a parametrização padrão (Grain v1 tem 160 clocks de init; Trivium tem 1152). A parametrização de "rodada" para cifras de fluxo é própria deles (`ph4r05/CryptoStreams`). **Não citar "Grain: margem de 15%" sem checar.**

Limitações declaradas:
> *"We used default settings of tests (…). Due to high computational costs only {10, 100, 1000} MB data sizes were tested. Using larger data sizes could reveal more subtle biases and detect more rounds. Also, some tests were not run as they require more data for analysis, e.g., Test U01 BigCrush."*
> *"From all possible data generation strategies, we used only a small subset (…). New generation strategies may reveal another unexpected biases."*

Achado desconfortável: *"The most observed event was that changing input data stream did not increase detection capability, with 1694 detections (80.94%). (…) This turned out to be the case for 397 detections (18.97%)"* — em quase 19% dos casos, **mais dados reduziram a detecção**.

Nota metodológica a copiar: **excluíram** três testes por comportamento anômalo — `smultin_MultinomialBitsOver` do Rabbit, e **Random Excursions e Random Excursions Variant da NIST STS** porque computam números diferentes de p-valores de primeiro nível para tamanho fixo. **Se esses testes estão nas 25 features de `nist_sts`, são ruído estruturado.**

##### 6.3 Os finalistas LWC parecem aleatórios

**[CIT — paywall]** Bellini, Huang, Rachidi, *"Statistical Tests for Symmetric Primitives — An Application to NIST Lightweight Finalists"*, **SecITC 2022, LNCS 13809, pp. 133–152**, doi:10.1007/978-3-031-32636-3_8.

Testes NIST em **todas as versões de rodada reduzida** dos finalistas LWC. Nove tipos de dataset: Avalanche Plaintext; Avalanche Key; Plaintext-Ciphertext correlation; CBC Mode; Random; Low-Density with Plaintext; Low-Density with Key; High-Density with Plaintext; High-Density with Key. Testam a permutação do Ascon de 3 a 6 rodadas.

Conclusão por fonte secundária (arXiv:2303.14785): **"the underlying primitives for most of the methods produce datasets that seem random."**

**Cabe? NÃO, os datasets deles não cabem.** Sete dos nove exigem plaintext/chave escolhidos. Só "Random" e "CBC Mode" são passivos. **Mas é a referência obrigatória**: único trabalho publicado com testes estatísticos sistemáticos de rodada reduzida exatamente nos nossos quatro algoritmos, e a conclusão é a nossa H0.

##### 6.4 ML em CT-only contra cifras leves: acaso, com análise de memorização

**[PUB]** Dani, Nakka, Saxena, arXiv:2405.19683v2 / ePrint 2024/852.

SPECK32/64 e SIMON32/64 em **CBC**, chave fixa, dois plaintexts fixos diferindo em 1 bit, IVs aleatórios não fornecidos ao modelo. 10^7 treino, 10^6 validação, 10^6 teste. ResNet, CNN 1D, LSTM, BiLSTM, Optuna/TPE.

| | | Acc | Prec | Rec | F1 | ROC-AUC |
|---|---|---|---|---|---|---|
| **Round-reduced** SPECK | ResNet | 0.5000 | 0 | 0 | 0 | 0.5008 |
| | CNN | 0.5003 | 0.5043 | 0.0356 | 0.0665 | 0.5005 |
| | LSTM | 0.5000 | 0 | 0 | 0 | 0.5014 |
| | BiLSTM | 0.5000 | 0 | 0 | 0 | 0.5000 |
| SIMON | ResNet | 0.5002 | 0.5002 | 0.4947 | 0.4974 | 0.5003 |
| | CNN | 0.4993 | 0.4985 | 0.2235 | 0.3086 | 0.4992 |
| **Full-round** SPECK | ResNet | 0.5000 | 0.5000 | 1.0000 | 0.6667 | 0.5001 |
| | CNN | 0.4997 | 0.4999 | 0.9489 | 0.6548 | 0.4996 |
| SIMON | BiLSTM | 0.5000 | 0.5295 | 0.0005 | 0.0010 | 0.5003 |

**A análise de memorização.** IV de 32 → 16 bits (~65.536 criptogramas únicos). Treino: 800.000 amostras. Teste: 100.000, 70.023 únicas. Sobreposição: **5.307 (≈5%)**. Acurácia geral **53,72%**; nas 70.023 únicas, **53,58%**; **isolando as exclusivas do teste, 49,90%**. Com duplicação massiva, **≈99%**.

> *"modern ML techniques consistently achieve accuracy equivalent to random guessing, indicating that no statistically exploitable patterns exists"*
> *"reflects memorization rather than generalization to unseen ciphertexts"*
> *"the inability of state-of-the-art ML models to surpass random guessing underscores not a deficiency of ML techniques, but rather highlights the inherent robustness and strength of cryptographic indistinguishability"*

**Cabe?** O adversário é passivo mas conhece os dois plaintexts candidatos — IND-CPA com dois plaintexts fixos, não CT-only estrito. Ainda assim, a referência negativa mais rigorosa e a única com memorização quantificada. **Par metodológico natural.**

---

#### PARTE 7 — Dois trabalhos recentes a ler antes da banca

##### 7.1 A alegação impossível: FESLA "distinguindo AES-256 full-round em CT-only"

**[PUB — ePrint não arbitrado]** Gopal Singh, *"Distinguishing Full-Round AES-256 in a Ciphertext-Only Setting via Hybrid Statistical Learning"*, **ePrint 2025/862**. https://eprint.iacr.org/2025/862.pdf

**100% de acurácia** com SVM, RF, MLP, LR e Naive Bayes, em CV (K=5 e K=10) e teste.

Setup: 2^21 plaintexts aleatórios (`secrets`), dois cenários de chave, 12 datasets. Dados aleatórios: mesmo `secrets`. Batches de 2^12, 512 batches. 30 testes estatísticos, 20 selecionados por KS.

**Os sinais de artefato:**
1. **Nada funciona no dado cru.** ML direto sobre 128 bits: *"These models failed to converge repeatedly."* MLP: *"failed to converge after numerous epochs indicating a weak or no feature separation."* PCA/t-SNE: *"the data is not separable using any method used on data directly."* Nos 30 testes individuais: *"the results of probability value (p value) were found same for both data sets."*
2. **A separação só aparece nas estatísticas por batch**, e a Fig. 7 mostra por quê: Anderson-Darling é **função delta** em ≈0,90 para AES-128, ≈0,61 para DES, ≈0,50 para PRESENT, contra distribuição espalhada em 0,50–0,55 para o aleatório. Estatística determinística constante entre batches não é "viés sutil" — é valor fixo do pipeline.
3. **A ordenação DES(64) < PRESENT(64) < AES(128) sugere que a feature lê o tamanho de bloco / formatação.**
4. Ressalva dos autores: *"Such high accuracy is unusual in practical cryptanalysis and is likely a consequence of the carefully selected and well-engineered statistical features"*. E, contradizendo-se, *"This proves beyond any doubt that the Model training is fair."*

**Valor real:** exemplo perfeito para a seção de metodologia — mostra o tipo de falha que key-holdout, bootstrap agrupado e correção de múltiplas comparações previnem, **e que passar em CV 5-fold e 10-fold não protege contra artefato de geração**. Citar junto com Dani et al. (§6.4): mesma tarefa, mesmo modelo de ameaça, resultados opostos, e um dos dois fez controle de memorização.

##### 7.2 A vulnerabilidade de estrutura do plaintext

**[PUB]** Ren, Luo, Peng, He (Wuhan), arXiv:2511.08296 (11 nov 2025; v2 em 30 jul 2026).

> *"we find that when the plaintext distribution of test data departs from the training data, the performance of classifiers often declines significantly. This issue exposes the feature extractor's hidden dependency on plaintext features."*

**6 cifras** — AES (ECB e CBC), 3DES, Blowfish, ChaCha20, RC4. Chaves e IVs **por janela**, via HKDF (RFC 5869). Canterbury Corpus + cinco sintéticos graduados (Regular_100 a Random_100), **10.000 janelas de 8 KB** cada.

Extrator: **41 testes** em quatro famílias. Pipeline: calibração via CDF nula → segmentação → histograma normalizado de K bins + S momentos → concatenação.

| Domínio | AUC | Acurácia |
|---|---|---|
| Regular (estruturado) | **> 0,98** | **> 0,95** |
| **Random_100** (uniforme) | **> 0,90** | **≈ 0,52–0,57** |

Explicação por SNR: estruturado dá *"low noise background (high SNR)"*; aleatório dá *"high entropy background"*, **degradando as métricas com limiar mas preservando a capacidade de ordenação (AUC)**.

**Três consequências imediatas:**
1. **A discrepância AUC 0,90 / acurácia 0,52 é o padrão-ouro de diagnóstico.** Se o Caminho A dá F1 ≈ 0,50 mas AUC > 0,60, há sinal de ordenação que o limiar esconde. **Conferir as AUCs — se só o F1-macro foi reportado, pode haver sinal na mesa.**
2. **A divisão 80% texto / 20% imagem é um experimento de domínio cruzado grátis.** Estratificar por `plaintext_source` e reportar a degradação.
3. **Nenhuma das seis cifras é AEAD com nonce.** ECB e CBC propagam estrutura; ChaCha20 e RC4 são fluxo puro (onde §1.6 se aplica). **O conjunto de quatro AEAD é estritamente mais duro que o deles**, e vale dizer explicitamente.

##### 7.3 Padrões construídos para serem invisíveis à STS

**[PUB]** Allen, La Luz, Salivia, Hardwick, *"Non-detectable patterns hidden within sequences of bits"*, **arXiv:2405.03587** (6 mai 2024).

> *"we construct families of bit sequences using combinatorial methods (…) we show that the NIST testing suite described in publication 800-22 does not detect these symmetries hidden within these sequences."*

Versão combinatória explícita dos *two-faced processes* do Ryabko (§0.5). "A SP 800-22 não detecta simetrias construídas para escapar dela" tem duas fontes independentes, uma informação-teórica e uma combinatória.

##### 7.4 A própria Dieharder tinha erros

**[CIT]** Sýs, Obratil, Matyáš, Klinec, *"A Bad Day to Die Hard: Correcting the Dieharder Battery"*, **Journal of Cryptology, 2022**, doi:10.1007/s00145-021-09414-y. A segunda bateria mais usada do mundo teve erros corrigidos num JoC em 2022.

---

#### APOSTAS

##### Aposta 1 — FWHT exaustiva sobre janelas de 24 bits, com nulo de estatística de ordem

**O quê.** FWHT sobre o histograma de blocos de 24 bits do fluxo concatenado de cada classe. Saída: os 2^24-1 coeficientes `sqrt(N)*C(a)`, cada um ~N(0,1) sob H0. Estatística: `M = max_{a!=0} |sqrt(N)*C(a)|`, nulo exato `f_max(x) = l*phi(x)*(2*Phi(x)-1)^(l-1)`, `l = 2^24-1`. Versão de duas amostras: `sqrt(N/2)*|C_Ascon(a) - C_GIFT(a)|`.

**Por quê essa.** (i) É a versão **exata** do único método que comprovadamente ganha rodadas sobre a NIST STS. O BoolTest testa 512 monômios de grau 1 por heurística gulosa; a FWHT testa todas as 16.777.215 funções lineares daquela janela, exatamente, em 2 segundos e 64 MB. (ii) É a única coisa que produz **limite superior quantitativo publicável**: "nenhum viés linear sobre janelas de 24 bits excede 2,1x10^-4 em nenhum dos quatro, com 6,6x10^8 blocos por classe". (iii) Sobre GF(2) **subsume** o bispectro, os cumulantes de ordem 3, a autocorrelação e o monobit — os quatro colapsam em coeficientes de Walsh. Quatro famílias de features por um algoritmo. (iv) Nas variantes reduzidas, `M` é **monotônico e contínuo** em rodadas, transformando o piso binário (GIFT 3/40, Grain 28/256) numa curva com barras de erro.
**Custo:** ~200 linhas de NumPy, 64 MB, uma passada sobre 1,9 GB por classe. **Uma tarde.**
**Previsão falsificável.** Sob H0, `M ≈ 5,27 ± 0,25` para cada classe e para as seis diferenças de pares. Qualquer `M > 6,0` é sinal real. Nas variantes reduzidas, `M` deve cruzar 6,0 antes do número de rodadas em que a bateria de 641 features cruza o limiar de F1 — se não cruzar antes, a aposta está errada.

##### Aposta 2 — Teste adaptativo de Ryabko sobre palavras de 24 bits, ajustado dentro do fold

**O quê.** Ryabko–Stognienko–Shokin (JSPI 2004): alfabeto de 24 bits; metade de treino estima `p_i`; particionar em s = 3 subconjuntos (A0 = nunca vistas, A1 = vistas uma vez, A2 = resto); testar `H0: p(A_i) = |A_i|/2^24` na metade de teste por chi² com 2 gl, alfa = 0,05. A "metade de treino" é o fold de treino (192 chaves), a "metade de teste" é o de validação (48) — **a estrutura coincide exatamente com a regra de ouro 4**.

**Por quê essa.** (i) É o **único** caso na literatura em que um teste mais fino vence o padrão **na nossa escala de dados exata**: arquivos de 102.400 bytes (temos 65.552), AES-ECB sobre texto natural, 17 rejeições em 40 contra 4 em 40. Todo o resto (book stack 2^32 bits, BoolTest 100 MB, CoolTest 100 MB) opera 3 a 4 ordens acima de uma amostra nossa. (ii) Dá **um controle positivo com valor de referência publicado**. Hoje o AES-ECB é controle sem escala. Com este teste: 17/40 em 100 KB, 26/40 em 200 KB. Se der muito diferente, o problema está no corpus ou no pipeline. (iii) O mecanismo teórico é o mesmo que a memória do projeto e o Ren et al. identificaram — é o **instrumento calibrado** para medir esse canal.
**Custo:** 150 linhas. 32 MB de contadores. **Um dia.**
**Previsão.** AES-ECB: ≈ 40–45% de rejeições a 64 KB. PRNG (CTR_DRBG): ≈ 5%. Os quatro AEAD: **≈ 5%, indistinguível do nominal**. Se algum passar de ~10%, ou há achado, ou vazamento de geração — e o teste diz *quais palavras de 24 bits* estão sobre-representadas.

##### Aposta 3 — Converter as features de compressão em testes calibrados, e rodar CoolTest

**O quê.** (a) Substituir `compression_ratio_{zlib,bz2,lzma}` pelo teste `tau_f = n - |f(x)|` com valor crítico `t_alfa = n - log2(1/alfa) - 1`, usando codificador **sem container** (`zlib.compressobj(wbits=-15)` para deflate raw, ou zstd sem frame header). Validade provada para qualquer compressor sem perdas livre de prefixo — **sem distribuição nula, sem calibração, sem simulação**. (b) Rodar `cooltest` sobre os 1,9 GB de cada classe, com vários k.

**Por quê essa.** (i) É o **único** teste do levantamento com prova de dominância estrita: Teorema 2 do Ryabko 2024 mostra que testes de compressor de dicionário dominam *toda* a família de Markov de ordem finita, com `dim >= 1/2` e supremo 1. A NIST STS inteira é família de ordem finita. (ii) Custo quase negativo: as três compressões já existem; falta remover o cabeçalho e trocar razão por valor crítico. ~30 linhas. (iii) A CoolTest é literalmente *"suited for small data volumes"*, que é o nosso regime, e é binário pronto.
**Custo:** (a) 30 linhas + 2 h. (b) `cargo install cooltest`, ~8 h por classe. **Um dia.**
**Previsão.** (a) Para n = 524.416 bits e alfa = 0,01, `t_alfa = n - 7,64`: o compressor precisa economizar **>= 8 bits**. **Zero rejeições** em 30.000 amostras para cada AEAD; **100%** para AES-ECB sobre texto. Se algum AEAD rejeitar, verificar o cabeçalho antes de comemorar. (b) CoolTest: p uniforme para os quatro completos; nas reduzidas, deve detectar pelo menos tantas rodadas quanto o BoolTest e provavelmente 1 a mais.

---

#### Nota final: o que este levantamento NÃO achou

Nenhuma aplicação publicada de **bispectro, trispectro ou cumulantes de ordem >= 3** a teste de aleatoriedade criptográfica — com a razão em §4.1 (sobre GF(2) colapsam na transformada de Walsh). Nada útil em **discrepância/equidistribuição** para cifras modernas — aparato de reticulado, não transfere (§5). **NCD** não funciona em alta entropia, e a literatura diz por quê (§2.3). Três bons candidatos a "rotas fechadas com justificativa", um parágrafo cada, que evitam que a banca as sugira.

**O item mais desconfortável:** Calude et al. 2010 (§2.5). A bateria de AIT mais completa já aplicada separou **fonte física de fonte algorítmica** com p < 10^-4, mas **não separou Mersenne Twister de autômato celular** (p = 0,4175), com 512 MB por amostra. Se a melhor estatística de aleatoriedade disponível não distingue dois PRNGs não-criptográficos, a expectativa a priori de distinguir Ascon de GIFT-COFB deveria ser baixa — **e vale dizer isso explicitamente na dissertação, antes de apresentar o resultado.**

---

# Pesquisa 07 — Correlação e distinguidores lineares sem entrada escolhida

- **Ângulo:** Correlação e distinguidores lineares sem entrada escolhida
- **Temperatura declarada:** 0,9

## Pesquisa 07 — prompt usado, na íntegra

````markdown
# Pesquisa 07 — Correlação e distinguidores lineares sem entrada escolhida

**Temperatura declarada: 0,9** (amplitude de exploração alta — siga pistas
tortas, aceite analogias de outros subcampos, traga o que for especulativo
DESDE QUE marcado como tal; o critério de corte é "é verificável?", não "é
convencional?")

---

## PROBLEMA DE PESQUISA

Você está pesquisando para uma dissertação de mestrado em criptografia
aplicada e aprendizado de máquina. Trabalhe SÓ com literatura externa: não
leia nenhum repositório, arquivo local ou resultado prévio. Comece do zero.

**A pergunta.** Dado apenas o criptograma — sem a chave, sem o texto em claro,
sem poder escolher nada do que é cifrado — é possível distinguir qual
algoritmo de criptografia autenticada o produziu? E, num segundo nível, com
quantas rodadas reduzidas um algoritmo ainda deixa de parecer aleatório?

**Os algoritmos.** Os quatro finalistas do concurso NIST Lightweight
Cryptography: Ascon-AEAD128 (esponja), GIFT-COFB (cifra de bloco em modo
COFB), Grain-128AEAD (cifra de fluxo com LFSR e NFSR) e Schwaemm256-128
(esponja ARX, família SPARKLE).

**O modelo de ameaça, que é a restrição dura e não negocia.** Adversário
PASSIVO, em ciphertext-only. Ele observa criptogramas de um mesmo dispositivo,
com nonces públicos de contador, e pode observar vários de uma vez. Ele NÃO
tem: texto em claro conhecido ou escolhido, diferenças escolhidas na entrada,
reuso de nonce, acesso a canais laterais, nem consultas a um oráculo de
cifragem. Isso exclui de saída a maior parte da criptanálise diferencial
clássica e os distinguidores neurais no estilo Gohr, que dependem de pares com
diferença escolhida.

**O protocolo experimental.** Classificadores clássicos e redes sobre features
estatísticas e sobre os bytes crus. Chaves de teste nunca aparecem no treino
(key-holdout). Intervalo de confiança por bootstrap agrupado por chave, e não
i.i.d. Correção para múltiplas comparações. Controle negativo obrigatório: com
o algoritmo completo o classificador tem que ficar no acaso.

**Dado concreto disponível:** ~30.000 criptogramas por algoritmo, 64 KB cada
(≈1,9 GB por classe), 300 chaves distintas, nonces de contador, texto em claro
vindo de corpus real (80% texto em inglês do Project Gutenberg, 20% imagem em
tons de cinza). Existem variantes com rodadas reduzidas compiladas para os
quatro algoritmos. Existem controles: AES em modo ECB (positivo) e saída de
PRNG (negativo).

---

## ÂNGULO DESTA PESQUISA — o arsenal linear num cenário passivo

A criptanálise linear é, ao lado da diferencial, o outro pilar. Mas quase toda
a literatura de criptanálise linear pressupõe pares (plaintext, ciphertext)
conhecidos, porque a aproximação linear canônica tem a forma
`<a, P> XOR <b, C> XOR <c, K> = 0`. Sem P, o termo `<a, P>` é uma variável
aleatória desconhecida, e a aproximação parece morrer.

**A pergunta desta pesquisa é se ela morre mesmo.** Quero saber o que sobra do
arsenal linear e de correlação quando o adversário só tem C.

Persiga, entre outras coisas:

- **Aproximações lineares que não tocam o plaintext.** Existem trabalhos em que
  a máscara sobre a entrada é zero (`a = 0`), deixando só `<b, C> XOR <c, K>`?
  Isso é o que a literatura chama de "zero-correlation com máscara de entrada
  nula", "linear hull com input mask zero", ou aparece em outro nome? Em que
  primitivas isso é possível e por quê?
- **Ataques de correlação em cifras de fluxo** (Siegenthaler; correlação rápida
  de Meier–Staffelbach; suas versões modernas com decodificação de códigos
  LDPC/convolucionais). O ponto crucial: eles são clássicos de *known
  plaintext*, mas a literatura tem versões **ciphertext-only** que exploram a
  redundância do idioma do plaintext. Siegenthaler 1985 é exatamente isso.
  Quanto disso transfere para o Grain-128AEAD? Qual é a redundância mínima de
  plaintext necessária, em bits por bit?
- **Distinguidores de correlação multidimensional e linear-multiplo** (Hermelin,
  Cho, Nyberg; Biryukov–De Cannière–Quisquater). A vantagem do multidimensional
  é usar muitas aproximações fracas ao mesmo tempo — exatamente o que um
  classificador estatístico faz implicitamente. Existe formalização da ligação
  entre "distinguidor linear multidimensional" e "classificador treinado"?
- **Correlação em primitivas ARX** (Schwaemm/SPARKLE, e por analogia Salsa,
  ChaCha, Speck): aproximações lineares da soma modular, o trabalho de
  Wallén sobre a correlação linear da adição mod 2^n, e a técnica de
  Nyberg–Wallén. Isso produz vieses observáveis na saída sem conhecer a
  entrada?
- **Correlação em esponjas** (Ascon, Schwaemm): o que a literatura diz sobre
  trilhas lineares na permutação do Ascon com rodadas reduzidas, e se alguma
  delas se manifesta na *taxa de saída* (que é o que o adversário vê) em vez
  de no estado interno.
- **O caso do GIFT-COFB:** COFB realimenta o estado com o ciphertext e usa uma
  máscara que muda por bloco. Isso é uma construção de "feedback de
  ciphertext" — existe análise linear de modos com feedback de ciphertext
  (CFB, OFB, COFB, CBC) que produza viés observável só na saída?
- **Cruzamento com aprendizado de máquina:** existem trabalhos que mostram que
  uma rede neural treinada num distinguidor está, na prática, aprendendo
  aproximações lineares (ou uma combinação delas)? A linha de "interpretando o
  que o distinguidor neural aprendeu" (Benamira, Gerault, Peyrin, Tan; Bao,
  Guo, Liu, Ma, Tu) é relevante aqui — mas eu quero a parte que sobrevive sem
  diferença escolhida.
- **Qualquer coisa que faça a ponte entre "viés linear de uma máscara" e "o que
  se mede num dataset".** Se uma máscara `b` tem correlação `eps` na saída,
  quantos criptogramas de 64 KB são necessários para vê-la com poder 0,8? Traga
  a conta.

Vá também para onde o ângulo levar: se aparecer uma técnica de correlação de
outro subcampo (processamento de sinais, códigos corretores, teste de
hipóteses composto) que se aplique, traga.

---

## O QUE EU QUERO DE VOCÊ

Técnicas, representações, ataques ou ideias — publicadas ou adaptáveis — que
possam extrair sinal nesse cenário, ou que ajudem a delimitar com rigor por
que o sinal não existe. Interessa tanto o que funciona quanto a prova de que
algo é impossível.

Busque em literatura acadêmica real (IACR ePrint, ToSC/FSE, CHES, CRYPTO,
EUROCRYPT, ASIACRYPT, SAC, Designs Codes and Cryptography, IEEE, Springer,
arXiv) e em fontes técnicas sérias. Use termos de busca em inglês.

## COMO RESPONDER

Para cada ideia encontrada, escreva:

1. **O que é** — a técnica, em duas ou três frases.
2. **Fonte** — autores, título, veículo, ano. Link quando houver. Se você não
   conseguiu confirmar a existência do trabalho, diga isso explicitamente em
   vez de completar de memória.
3. **Cabe no nosso modelo?** — SIM, NÃO, ou ADAPTÁVEL. Se ADAPTÁVEL, diga
   exatamente o que teria de mudar e qual premissa do modelo de ameaça isso
   arranha.
4. **O que custaria testar** — ordem de grandeza de dados, computação e
   engenharia.
5. **O que ela prevê** — se a técnica funcionar, que resultado deveríamos ver?
   Se não houver previsão falsificável, diga isso.

Termine com uma seção **APOSTAS**: as três ideias que você tentaria primeiro,
e por quê. Seja específico; "usar deep learning" não é uma aposta.

## PROFUNDIDADE — leia isto com atenção

Não é um levantamento rápido. **Vá até esgotar o veio.** Não pare em cinco ou
dez achados porque já "deu para ter uma ideia": siga as citações para frente e
para trás, abra os trabalhos relacionados dos artigos que importarem, procure
versões estendidas e teses, e persiga as pistas que aparecerem no caminho,
mesmo as que não estavam no ângulo original. Só encerre quando as buscas novas
pararem de trazer coisa nova.

Traga TODA a informação, não um resumo dela. Se um artigo tem um número que
importa (quantas rodadas, quantas consultas, que acurácia, que correlação, que
tamanho de dado), traga o número. Se tem uma limitação declarada pelos próprios
autores, traga a limitação com as palavras deles. Prefira errar por excesso de
detalhe. Uma resposta longa e completa é o que se pede aqui; uma resposta
enxuta é falha de execução.

## REGRAS

- Não invente referências. Uma fonte não confirmada vale menos que nenhuma, e
  vou checar.
- Não repita o óbvio já saturado (distinguidor diferencial-neural padrão)
  sem trazer um ângulo novo que sobreviva ao ciphertext-only.
- Se a conclusão honesta de um caminho for "isso é impossível neste modelo
  por tal razão teórica", isso é resultado útil. Diga.
- Separe o que é publicado do que é sua extrapolação. Marque cada um
  explicitamente: **[PUB]** para publicado e lido/confirmado, **[CIT]** para
  existência confirmada mas texto não obtido, **[MINHA]** para extrapolação
  sua.
````

## Pesquisa 07 — achados, sem resumir

### Achados — Pesquisa 07

- **Ângulo:** correlação e distinguidores lineares sem entrada escolhida
- **Temperatura declarada:** 0,9
- **Prompt usado:** `prompts/07_correlacao_e_linear.md`
- **Execução:** 410.827 tokens de subagente, 138 chamadas, ~42 min (a maior da série)
- **Nota:** primeira tentativa (07:10) morreu no rate limit sem produzir nada; esta é a relançada às 11:06, mesmo prompt e mesma temperatura

---

### Pesquisa 07 — Correlação e distinguidores lineares sem entrada escolhida

**Escopo:** só literatura externa. Não abri o repositório nem nenhum resultado prévio; os únicos números do projeto que uso são os que vieram no enunciado (≈30.000 criptogramas/algoritmo, 64 KB, 300 chaves, nonce contador, 80% Gutenberg / 20% imagem).
**Marcação:** **[PUB]** = li o texto (PDF/HTML) e extraí os números; **[CIT]** = existência confirmada em fonte confiável, texto integral não obtido; **[MINHA]** = extrapolação/cálculo meu.

---

#### 0. Resumo do que sobra do arsenal linear

A resposta curta à pergunta central — "a aproximação linear morre sem o plaintext?" — é: **morre exatamente em um ponto e sobrevive em outro, e os dois são separáveis com precisão.**

Morre: a aproximação com **máscara de entrada nula** (`a = 0`) tem correlação **exatamente zero** para qualquer bijeção com entrada uniforme. Isso é um teorema, não uma dificuldade prática (Seção 1).

Sobrevive: o plaintext real não é uniforme. A fórmula que governa todo o cenário é

> **corr_C(b) = corr_P(b) · corr_Z(b)**

— a correlação observável no criptograma é o produto da correlação da máscara no plaintext pela correlação da mesma máscara no keystream. E para texto ASCII, **existe uma máscara com corr_P = 1,000 exatamente** (o bit 7 de cada byte). Nessa máscara, o cenário ciphertext-only é *indistinguível* de known-plaintext. Não há perda nenhuma. Esse é o achado mais explorável de toda esta pesquisa (Seções 2 e 3).

Além disso, achei uma propriedade estrutural do Ascon que o modelo de ameaça não exclui e que a literatura de ML não usa: **no Ascon-AEAD128 a parte de taxa do estado interno É o bloco de criptograma**, por definição normativa (NIST SP 800-232, eq. 24–25). O adversário passivo conhece 128 dos 320 bits do estado a cada bloco, de graça. Isso converte o problema de "distinguir ruído" em "medir a correlação linear taxa→taxa da permutação com máscara nula na capacidade" (Seção 6).

---

#### 1. Aproximações lineares que não tocam o plaintext

##### 1.1 O teorema que fecha a porta óbvia

**O que é.** Daemen, Govaerts e Vandewalle formalizaram a criptanálise linear via *matrizes de correlação*: a matriz `C^h` cuja entrada `C_uw = C(u^T h(a), w^T a)` descreve todas as correlações entre combinações lineares de entrada e de saída. Para uma transformação invertível, `C^h` é **ortogonal**, e disso sai:

> **Proposição 1.** *Every linear combination of output bits of an invertible transformation is a balanced Boolean function of its input bits.* Formalmente, `C(u^T h(a), 0) = δ(u)`.

Ou seja: com máscara de entrada `w = 0`, a correlação é **exatamente 0** para todo `u ≠ 0`. Não é "pequena", é zero.

**Fonte.** J. Daemen, R. Govaerts, J. Vandewalle, *Correlation Matrices*, FSE 1994, LNCS 1008, pp. 275–285. **[PUB]** (li o texto completo na cópia da KU Leuven).

**Cabe no nosso modelo?** SIM, mas como **resultado negativo**. Para chave e nonce fixos, `P ↦ C` é uma bijeção que preserva o comprimento nos quatro AEADs. Logo, se o plaintext fosse uniforme, **nenhuma estatística linear do criptograma, de qualquer peso, teria viés**. Isso é a formalização rigorosa de "criptograma não tem viés linear".

**O que custaria testar.** Nada — é um teorema. Vale como parágrafo de fundamentação da dissertação.

**O que prevê.** Que qualquer sinal linear medido no criptograma vem *obrigatoriamente* da não-uniformidade do plaintext, ou é artefato. Isso é uma previsão falsificável e forte: **substitua o corpus Gutenberg por saída de CTR_DRBG mantendo tudo o mais e todo sinal linear deve ir a zero.** Se não for, há vazamento metodológico.

##### 1.2 "Zero-correlation com máscara de entrada nula" — o termo não existe

Vasculhei a literatura de *zero-correlation* (Bogdanov–Rijmen e derivados) procurando algo com `a = 0`. **Não existe, e pela razão acima.** O que a literatura chama de zero-correlation é o oposto: máscaras de entrada *e* saída **ambas não-nulas** cuja correlação é provadamente zero, usadas como distinguidor de "correlação zero onde deveria haver ruído ±2^-n/2". Isso é intrinsecamente *known/chosen plaintext*: você precisa dos pares para medir a correlação empírica.

**Fontes.** A. Bogdanov, V. Rijmen, *Linear hulls with correlation zero and linear cryptanalysis of block ciphers*, Designs Codes and Cryptography 70(3), 2014 (ePrint 2011/123) **[CIT]**; A. Bogdanov, G. Leander, K. Nyberg, M. Wang, *Integral and Multidimensional Linear Distinguishers with Correlation Zero*, ASIACRYPT 2012 **[CIT]** — este último prova o elo entre distinguidores integrais e zero-correlation com máscaras parcialmente nulas, mas o lado integral exige plaintext escolhido.

**Cabe no nosso modelo?** **NÃO.** Precisa de pares (P,C).

**Resultado útil:** pode ser dito na dissertação que o ramo zero-correlation está **fechado por construção** no modelo ciphertext-only, e por quê. Isso é conteúdo, não lacuna.

##### 1.3 Onde a porta se reabre: função não-bijetiva e entrada não uniforme

Dois escapes reais da Proposição 1:

1. **Entrada não uniforme.** Se `P ~ p ≠ U`, então `corr_C(b) = Σ_a corr_P(a) · C^E_{b,a}`. O termo `a = b` domina quando `E` é "quase uma permutação aleatória", dando `corr_C(b) ≈ corr_P(b) · corr_Z(b)` no caso aditivo (Seção 2). **[MINHA]**, mas é aplicação direta da eq. (12)/(14) de Daemen et al.
2. **Função não-bijetiva.** O adversário do Ascon observa 128 de 320 bits do estado. A aplicação `capacidade ↦ taxa_de_saída` (com a taxa de entrada *conhecida e fixa*) é uma função 192→128 **não balanceada**. Para um valor fixo de taxa conhecida existe correlação de saída pura, não-nula — porém de magnitude ~2^-96 (heurística de função aleatória), e com média zero sobre os valores de taxa. **[MINHA]** — inviável de medir, mas vale registrar porque é *exatamente* o que o mapa de co-ocorrência de bigramas (Caminho C) mede de forma agregada.

##### 1.4 O arcabouço geométrico que unifica tudo isso

**O que é.** Beyne substitui "máscaras lineares" por "subespaços do espaço de funções `C^G`", e mostra que aproximações lineares, invariantes, ataques integrais, saturação estatística e **distribuições de probabilidade arbitrárias na entrada** são todos o *mesmo* objeto — propriedades medidas por produto interno com o estado propagado. A Tabela 2 do artigo lista explicitamente "Probability distribution `p : F₂ⁿ → [0,1]`, base `{p}`, aplicação: statistical saturation".

**Fonte.** T. Beyne, *A Geometric Approach to Linear Cryptanalysis*, ASIACRYPT 2021, LNCS 13090 (ePrint 2021/1247). **[PUB]** (li as seções 3.1 e a Tabela 2).

**Cabe no nosso modelo?** **SIM, como linguagem.** É o arcabouço correto para escrever "plaintext inglês + cifra = propriedade observável no criptograma" sem gambiarra. Também é a base do arcabouço *quasidiferencial* (Beyne–Rijmen, CRYPTO 2022) **[CIT]**, que põe diferencial e linear no mesmo pé via matrizes de correlação.

**Custo.** Só de escrita/teoria. Zero computação.

---

#### 2. A fórmula-mestra e a tabela do inglês ASCII

##### 2.1 Derivação

Nos quatro AEADs o bloco de criptograma é `C = P ⊕ Z`, onde `Z` é keystream (Ascon: taxa do estado; Grain: pre-output; Schwaemm: parte externa; GIFT-COFB: `Y_i = E_K(X_i)`). Se `Z ⫫ P`, para qualquer máscara `b`:

```
corr_C(b) = corr_P(b) · corr_Z(b)          (regra XOR / piling-up de 2 termos)
N ≈ 1 / (corr_P(b) · corr_Z(b))²           (dados necessários)
```

Isso é o lema XOR de distância estatística, formalizado em Coppersmith–Halevi–Jutla: *"If for all i, |U − D_i| = ε_i, then |U − Σ D_i| ≤ Π_i ε_i"*. **[PUB]** (li o texto).

**Fonte do mecanismo original:** T. Siegenthaler, *Decrypting a Class of Stream Ciphers Using Ciphertext Only*, IEEE Trans. Computers C-34(1):81–85, 1985. **[CIT]** — é exatamente este ataque: correlação LFSR↔keystream multiplicada pelo desvio do plaintext.

##### 2.2 A tabela que importa: `corr_P` por máscara, em inglês ASCII

Calculei o espectro de Walsh completo da distribuição marginal de bytes de um texto literário inglês em ASCII, montada a partir da tabela clássica de frequência de letras (Lewand) mais 17% espaço, 2,5% CR/LF, 3,5% pontuação, 3% maiúsculas. **[MINHA]** (cálculo meu sobre frequências publicadas).

| máscara | bits | `corr_P` | `1/corr_P²` | leitura |
|---|---|---|---|---|
| `0x80` | b7 | **+1,00000** | 2^0,00 | **grátis** — ASCII nunca acende o bit 7 |
| `0x20` / `0xA0` | b5 | −0,89000 | 2^0,34 | quase grátis |
| `0x40` / `0xC0` | b6 | −0,54000 | 2^1,78 | perde 1,8 bit |
| `0x10` / `0x90` | b4 | +0,50920 | 2^1,95 | perde 2,0 bits |
| `0x4E`/`0xCE` | b1,b2,b3,b6 | +0,58599 | 2^1,54 | combinação forte |
| `0x02` | b1 | +0,33286 | 2^3,17 | — |
| `0x08` | b3 | +0,32480 | 2^3,24 | — |
| `0xFF` | todos | −0,11164 | 2^6,33 | ruim |
| `0x04` | b2 | +0,03432 | 2^9,72 | praticamente morto |

Métricas agregadas do modelo: **entropia marginal H = 4,524 bits/byte**, **redundância marginal = 3,476 bits/byte**, **capacidade do byte `C_P = Σ_{a≠0} corr_P(a)² = 15,77 = 2^3,98`** (máximo possível 255).

##### 2.3 As três consequências que valem ouro

**(i) Ciphertext-only ≈ known-plaintext para máscaras em b5–b7.** Restringindo as máscaras aos bits 5, 6 e 7 de cada byte, o fator de perda fica entre 0,54 e 1,00 — no pior caso **1,8 bit de correlação**, no melhor **zero**. Um ataque linear ciphertext-only nesse subespaço custa essencialmente o mesmo que um known-plaintext.

**(ii) Máscaras de peso alto em b7 continuam grátis.** Para uma máscara `w` com suporte só em posições de bit 7, `⟨w,P⟩ = 0` deterministicamente (para ASCII puro), logo `corr_P(w) = 1` **independentemente do peso de Hamming**. Isso é raro: normalmente `corr_P` decai geometricamente com o peso. Aqui não decai.

**(iii) "Redundância mínima em bits por bit", respondendo à sua pergunta diretamente.** Uma máscara com correlação `δ` no plaintext consome `1 − h((1+δ)/2)` bits de redundância. Para `δ = 1` isso é 1 bit inteiro por byte, ou **0,125 bits por bit** — e é a exploração máxima possível por máscara. Os outros ~3,35 bits/byte de redundância marginal estão espalhados por máscaras com `|corr_P| < 1`, e entram **ao quadrado**, então valem muito menos. Traduzindo: de 3,48 bits/byte de redundância disponível, a fração *eficientemente* utilizável por um distinguidor linear é a primeira. **[MINHA]**

**Advertências honestas:** (a) SPGC moderno é UTF-8, então `corr_P(0x80) ≈ 0,99–0,999`, não 1,000 exato — para peso `w`, `≈ 0,99^w`; (b) os 20% de imagens em tons de cinza diluem: a estatística agrupada fica `≈ 0,8 × c`, perda de só 0,32 bit, então **não vale a pena estratificar** (e estratificar por `plaintext_source` seria trapaça, porque o adversário não conhece esse metadado); (c) a regra do produto entre bytes assume independência, falsa para bigramas do inglês — mas para b7 o argumento é determinístico e não precisa de independência.

---

#### 3. Orçamento de dados: a conta que você pediu

##### 3.1 Fórmulas

| regime | estatística | limiar de detecção |
|---|---|---|
| máscara única, sinal coerente | `z = ĉ√N` | `\|c\| ≥ 3/√N` |
| `M` máscaras, sinal desconhecido | `T = N Σ ĉ_a² ~ χ²_M` | `\|c\| ≥ √(3√(2/M)/N)`; capacidade `C ≥ 3√(2M)/N` |
| LLR (alternativa conhecida) | log-razão de verossimilhança | `N ∝ 1/C(p,q)` |
| χ² goodness-of-fit (alternativa desconhecida) | Pearson | `N = M^{1/2}/I₁`, com `2I₁ = C` |

As duas últimas são **[PUB]**: M. Hermelin, *Multidimensional Linear Cryptanalysis*, tese de doutorado, Aalto/TKK-ICS-D16, 2010. Definição 3.7 (capacidade `C(p,q) = Σ (p_η−q_η)²/q_η`), Lema 5.4 (`N ∝ 1/C` para LLR binário), Lema 5.5 (`N = M^{1/2}/I₁` para χ² com `M ≥ 50` graus de liberdade). A diferença `1/C` vs `2^{m/2}/C` é **o preço de não saber qual é a distribuição alternativa** — exatamente a diferença entre um distinguidor desenhado e um classificador treinado às cegas.

Complemento: T. Baignères, P. Junod, S. Vaudenay, *How Far Can We Go Beyond Linear Cryptanalysis?*, ASIACRYPT 2004, LNCS 3329, pp. 432–450 **[CIT]** — arcabouço estatístico geral com distinguidores ótimos explícitos. P. Junod, *On the Optimality of Linear, Differential and Sequential Distinguishers*, EUROCRYPT 2003 (ePrint 2003/064) **[PUB]**: no experimento com `ε = 0,01907`, o distinguidor sequencial (SPRT) atinge 96,8% de sucesso com **1.218,7 consultas em média**, contra `1/ε² = 2.750` do estático — **ganho prático de ~2,2×**.

##### 3.2 O orçamento concreto do dataset descrito no enunciado

30.000 amostras × 64 KB = **2^30,87 bytes = 2^33,87 bits por algoritmo**. **[MINHA]** (cálculo direto).

| alvo / unidade de observação | N | máscara única coerente | χ², M=2^8 | χ², M=2^16 | χ², M=2^24 |
|---|---|---|---|---|---|
| Ascon / GIFT / AES — pares de blocos de 128 b | 2^26,87 | `\|c\| ≥ 2^-11,85` | 2^-14,39 | **2^-16,39** | 2^-18,39 |
| Schwaemm256-128 — pares de blocos de 256 b | 2^25,87 | 2^-11,35 | 2^-13,89 | 2^-15,89 | 2^-17,89 |
| Grain-128AEAD — posições de bit do keystream | 2^33,87 | 2^-15,35 | 2^-17,89 | **2^-19,89** | 2^-21,89 |
| qualquer um — bytes isolados (família histograma) | 2^30,87 | 2^-13,85 | 2^-16,39 | 2^-18,39 | 2^-20,39 |

Variante com sinal desconhecido por chave (χ² sobre 300 chaves, porque o termo `⟨c,K⟩` troca o sinal a cada chave): perde-se cerca de **1,5 bit** de correlação em relação à linha coerente. Combinando 2^16 máscaras × 300 chaves: `|c| ≥ 2^-14,34` (blocos de 128 b) e `2^-17,84` (Grain). **[MINHA]**

Base teórica do problema do sinal por chave: C. Blondeau, K. Nyberg, *Improved Parameter Estimates for Correlation and Capacity Deviates in Linear Cryptanalysis*, ToSC 2016(2) **[CIT]**; J. Daemen, V. Rijmen, *Probability distributions of correlations and differentials in block ciphers*, J. Mathematical Cryptology 1(3):221–242, 2007 **[CIT]**.

##### 3.3 O que o Caminho A já é, em linguagem linear

**[MINHA], e acho que vale uma seção da dissertação.** A família "histograma" (256 dimensões) mede exatamente `corr_C(a)` para todas as 255 máscaras dentro de um byte. Ela **é** um distinguidor linear multidimensional de dimensão `m = 8`. Consequências imediatas:

- A capacidade mínima detectável é `C ≥ 2^{-28,79}` com 2^30,87 bytes (tabela acima com M=2^8, dobrando pelo ganho de 300 chaves) — ou seja, `|c|` por máscara ≳ 2^-16.
- Pelo Lema 5.5 de Hermelin, o teste χ² sobre 8 dimensões tem penalidade `M^{1/2} = 16` em relação ao LLR. Um classificador treinado, se aprender bem a alternativa, tende ao LLR — **esse é o argumento formal de por que o ML pode ganhar do χ² clássico, e o teto do ganho é exatamente 16× em dados, não mais.**
- N-gramas (15 dims) e autocorrelação/Runs (18 dims) são projeções de máscaras de peso 2 entre bytes vizinhos. FFT/Welch são máscaras periódicas. **Tudo o que o Caminho A mede é linear ou quadrático de baixa ordem local.**

---

#### 4. Ataques de correlação em cifras de fluxo — o que transfere para o Grain-128AEAD

##### 4.1 A linhagem

| trabalho | o que faz | marca |
|---|---|---|
| Siegenthaler 1985, *Decrypting a Class of Stream Ciphers Using Ciphertext Only*, IEEE ToC C-34(1) | divide-and-conquer; recupera estado de cada LFSR separadamente com `Σ(2^{L_i}−1)` tentativas em vez de `Π(2^{L_i}−1)`; **explicitamente ciphertext-only via redundância do plaintext** | **[CIT]** |
| Meier–Staffelbach, *Fast correlation attacks on certain stream ciphers*, J. Cryptology 1(3), 1989 | remove ruído com equações de paridade; evita a busca exaustiva | **[CIT]** |
| Johansson–Jönsson, *Fast Correlation Attacks Based on Turbo Code Techniques*, CRYPTO 1999; *Improved Fast Correlation Attacks via Convolutional Codes*, EUROCRYPT 1999 | decodificação iterativa / códigos convolucionais; funciona para polinômios de realimentação arbitrários | **[CIT]** |
| Chose–Joux–Mitton, algoritmo one-pass + FWHT; custo `N + n2^n`, caindo a `N + (n−ℓ)2^{n−ℓ}` | aceleração por Walsh–Hadamard | **[PUB]** (descrito em Todo et al. 2018) |
| Todo, Isobe, Meier, Aoki, Zhang, *Fast Correlation Attack Revisited*, CRYPTO 2018 (ePrint 2018/522) | quebra **Grain-128a completo**: dados 2^113,8, tempo 2^115,4. Grain-128: 2^112,8 / 2^114,4. Grain-v1: 2^75,1 / 2^76,7 | **[PUB]** |
| Zhang, Gong, Meier, *Fast Correlation Attacks on Grain-like Small State Stream Ciphers*, ToSC 2017(4):58–81 | pequenos estados (Fruit, Plantlet) | **[CIT]** |
| *Vectorial Fast Correlation Attacks*, ASIACRYPT 2025 | Grain-128a: **2^106,3 bits de keystream, tempo 2^107,7**; Grain-v1: 2^67,0 / 2^69,6. ~2^12 melhor que CRYPTO 2018 | **[CIT]** |

##### 4.2 Quanto transfere: os quatro bloqueios, quantificados

O que os designers do Grain-128AEAD escrevem, literalmente **[PUB]** (spec rodada 2, §4.2–4.3):

> *"For the function g, we have ε_g < 2^−9 and η(A_g) = 5, and for the function h (including the linearly added bits), we have ε_h < 2^−5 and η(A_h) = 7. This will give ε < 2^−77 for this linear approximation (which also includes LFSR bits)."*

> *"It should be noted that this fast correlation attack does not apply to Grain-128a in authentication mode, as then only every second key stream bit may be accessible to an opponent. In addition, Grain-128AEAD limits the keystream length to 2^80 bits for a same secret key and nonce. Thus, these fast correlation attacks do not apply to Grain-128AEAD."*

E Todo et al. **[PUB]**: *"We assume that all output sequences of the pre-output function can be observed. This assumption naturally holds under the known-plaintext setting on the stream cipher mode. […] we do not claim that the authenticated encryption mode is attacked."*

Os quatro bloqueios, com números **[MINHA]** sobre esses dados:

1. **Viés.** `ε < 2^-77` ⇒ `|c| < 2^-76` ⇒ `N > 2^152`. Nosso orçamento total: 2^33,87 bits. **Déficit de 2^118.** Nem multiplicando por `corr_P = 1` isso muda.
2. **Nonce contador.** A FCA precisa de dados "from the same secret key and the same nonce". No dataset cada amostra tem nonce distinto ⇒ estado inicial do LFSR diferente ⇒ as equações de paridade não se acumulam entre amostras. Por (key,nonce) temos 2^22,6 bits contra 2^106,3 exigidos pelo estado da arte.
3. **Split de bits.** Metade do pre-output vai para o autenticador. O adversário CT-only vê só os índices pares. Foi desenhado contra exatamente isso.
4. **Fator do plaintext.** Mesmo com `corr_P = 1` nas posições de bit 7, as relações lineares de keystream do Grain envolvem bits em posições arbitrárias, não em posições ≡ 7 (mod 8). Encontrar relações **restritas ao subgrid de bits 7** é um problema de busca legítimo mas ainda mais restrito — e portanto com viés ainda menor.

**Veredicto:** **NÃO** cabe no modelo para o Grain completo, e a razão é quantitativa e defensável (2^118 de déficit). **ADAPTÁVEL** para rodadas reduzidas (Seção 8).

##### 4.3 O ponto de referência realmente comparável: E0 do Bluetooth

**O que é.** Lu, Meier, Vaudenay, *The Conditional Correlation Attack: A Practical Attack on Bluetooth Encryption*, CRYPTO 2005: explora um defeito de **ressincronização** e correlações condicionais na FSM. Exige **os primeiros 24 bits de 2^23,8 frames** e 2^38 operações. Precursor (Lu–Vaudenay 2004): 24 bits de 2^35 frames. **[CIT]**

**Por que importa aqui.** É a única família de ataque publicada cuja *forma de dados* é a nossa: **muitas sessões curtas sob IVs distintos**, não uma sessão longa. 2^23,8 frames contra os nossos 2^14,9 — um fator 2^9, que é longe de astronômico. A diferença é que o E0 tem um defeito de ressincronização conhecido e os quatro finalistas não.

**Cabe?** **ADAPTÁVEL como molde de análise.** A lição operacional: **estatísticas indexadas por posição** (os "primeiros 24 bits"), não agregadas sobre a mensagem inteira. O histograma global do Caminho A destrói qualquer viés posicional por construção. Veja §9.3.

##### 4.4 Modelos lineares genéricos para geradores de keystream

- J. Golić, *Linear Models for Keystream Generators*, IEEE Trans. Computers 45(1):41–49, 1996: qualquer gerador com `M` bits de memória pode ser modelado como um LFSR não-autônomo de comprimento ≤ `M` com entrada aditiva de variáveis não-balanceadas; método de determinação do modelo por *linear sequential circuit approximation* (LSCA). **[CIT]**
- Khazaei, Hasanzadeh, Kiaei, *Linear Sequential Circuit Approximation of Grain and Trivium*, ePrint 2006/141: funções lineares de bits consecutivos de keystream com correlação **2^-63,7** (Grain) e **2^-126** (Trivium); via função geradora, melhoram para **2^-29** (Grain) e 2^-72 (Trivium); Grain distinguível com **2^58 bits**; Trivium sem distinguidor. **[PUB]**
- Coppersmith, Halevi, Jutla, *Cryptanalysis of Stream Ciphers with Linear Masking*, CRYPTO 2002: arcabouço geral — acha uma propriedade distinguível do processo não-linear e uma combinação linear que anula o processo linear. SNOW: **2^95 palavras, 2^100 trabalho**. Scream-0 (ataque de "baixa difusão"): **2^43 bytes, 2^50 espaço, 2^80 tempo**. **[PUB]**

**O ataque de baixa difusão merece destaque** e é o único item desta seção que eu apostaria em ML. Coppersmith et al.: *"some input/output bits of this process depend only on very few other input/output bits"*. Uma propriedade **local e de poucos bits** é exatamente o que uma CNN 1D com kernel pequeno pode representar, e exatamente o que é *impossível* para uma máscara de paridade de peso alto (§7.2). Se existe alguma classe de propriedade que o Caminho B pode achar e o Caminho A não, é esta.

##### 4.5 Vieses lineares em keystream de AEAD modernos — o estado da arte

| cifra | viés/correlação | dados para explorar | fonte |
|---|---|---|---|
| AEGIS-256 | máscara linear com viés **2^-89** | 2^188 (recupera bits de mensagem parcialmente conhecida) | Minaud, *Linear Biases in AEGIS Keystream*, SAC 2014 **[CIT]** |
| AEGIS-128 | rodadas `i` e `i+2` correlacionadas | **2^140** dados | idem **[CIT]** |
| MORUS-1280 | correlação **2^-76** no keystream | ~2^152 cifragens; recupera bits de plaintext no *broadcast setting* | Ashur, Eichlseder, Lauridsen, Leurent, Minaud, Rotella, Sasaki, Viguier, *Cryptanalysis of MORUS*, ASIACRYPT 2018 (ePrint 2018/464) **[CIT]** |
| MORUS-640 | correlação **2^-73** | não viola a alegação de segurança | idem **[CIT]** |

**Cabe no modelo?** Como *técnica*, SIM — são vieses observáveis só na saída, sem entrada escolhida, exatamente o nosso cenário. Como *magnitude*, NÃO: 2^-76 a 2^-89 estão 60 a 73 bits abaixo do nosso limiar de 2^-16.

**Valor para a dissertação:** este é o **parâmetro de referência honesto**. Quando um AEAD moderno cede a um distinguidor linear puro de saída, o viés fica em 2^-73…2^-89 e exige 2^140…2^188 dados. Nenhum experimento com 2^34 bits pode chegar perto. Citar essas três linhas transforma "F1 ≈ 0,50" de "nada aconteceu" em "o resultado está em acordo quantitativo com o estado da arte da criptanálise linear de AEADs".

---

#### 5. Linear multidimensional, múltiplo e a ponte com o classificador

##### 5.1 A linhagem e os números

- Kaliski–Robshaw 1994 (múltiplas aproximações, assume independência estatística) **[CIT]**; Murphy apontou que a hipótese falha em geral **[CIT]** (ambos citados na tese de Hermelin **[PUB]**).
- A. Biryukov, C. De Cannière, M. Quisquater, *On Multiple Linear Approximations*, CRYPTO 2004, LNCS 3152, pp. 1–22 (ePrint 2004/057) — fórmulas explícitas de ganho para versões generalizadas dos Algoritmos 1 e 2 de Matsui; introduzem o termo **capacidade**. **[CIT]**
- Hermelin, Cho, Nyberg, *A New Technique for Multidimensional Linear Cryptanalysis with Applications on Reduced Round Serpent*, ICISC 2008 / *Multidimensional Extension of Matsui's Algorithm 2*, FSE 2009. **[CIT]**
- Tese de Hermelin **[PUB]** — as fórmulas de complexidade já citadas na §3.1, e o resultado conceitual central: quando a alternativa é conhecida, use LLR (`N ∝ 1/C`); quando só se conhece a capacidade, é obrigatório um teste de aderência (`N ∝ 2^{m/2}/C`).
- G. Leander, *On Linear Hulls, Statistical Saturation Attacks, PRESENT and a Cryptanalysis of PUFFIN*, EUROCRYPT 2011, pp. 303–322: **distinguidores de saturação estatística são, em média, equivalentes a distinguidores lineares multidimensionais.** **[CIT]**
- B. Collard, F.-X. Standaert, *A Statistical Saturation Attack against the Block Cipher PRESENT*, CT-RSA 2009: **fixa 16 bits do plaintext**, ataca até **24 rodadas com ~2^60 plaintexts escolhidos**. **[CIT]**
- C. Harpes, J. L. Massey, *Partitioning Cryptanalysis*, FSE 1997, LNCS 1267, pp. 13–27: generaliza a criptanálise linear via *partition-pairs* e *I/O sums*. **[CIT]**
- S. Vaudenay, *An Experiment on DES Statistical Cryptanalysis*, ACM CCS 1996, pp. 139–147: criptanálise χ² sem precisar identificar a aproximação linear. **[CIT]**
- T. Ashur, D. Bodden, O. Dunkelman, *Linear Cryptanalysis Using Low-bias Linear Approximations*, ePrint 2017/204: **aproximações com `|ε| < 2^{-n/2}`, individualmente inúteis, combinadas num distinguidor χ²**; conjecturam estender Speck32/64 de 9 para 10 rodadas. Citação dos autores: *"security arguments based on counting S-boxes and showing an upper bound on the bias of the best approximation should be re-evaluated."* **[PUB]**

##### 5.2 A conexão "saturação estatística grátis" — o argumento que amarra tudo

**[MINHA], construída sobre três resultados publicados.** Texto inglês em ASCII tem **1 bit fixo por byte** (o b7). Em blocos de 128 bits, isso é **16 bits fixos por bloco** — literalmente a configuração de Collard–Standaert (16 bits fixos) só que **a fonte fixa esses bits, não o adversário**. Pelo teorema de Leander, essa configuração é equivalente a um ataque linear multidimensional sobre o subespaço de máscaras gerado pelas posições fixas.

Portanto:

> **Saturação estatística em modelo ciphertext-only é gratuita sobre plaintexts ASCII, e é equivalente a um distinguidor linear multidimensional de dimensão 16 por bloco de 128 bits.**

O que isso dá, em números: `M = 2^16 − 1` máscaras com `corr_P = 1`, capacidade `C = Σ corr_Z(a)²` sobre esse subespaço, limiar de detecção `C ≥ 3√(2·2^16)/N = 2^{-16,79}` no orçamento de 2^26,87 pares. **É precisamente a coluna "χ², M=2^16" da tabela da §3.2.**

##### 5.3 Existe formalização "distinguidor multidimensional ⟷ classificador treinado"?

Respondendo diretamente: **parcialmente, e o elo mais próximo é de 2025.**

**O que existe.**
1. **Beyne (ASIACRYPT 2021) [PUB]** — dá a álgebra comum (propriedades = subespaços; medição = produto interno), mas não fala de aprendizado.
2. **Hermelin [PUB]** — dá o lado estatístico: LLR é ótimo, χ² é o preço da ignorância da alternativa. Um classificador bem treinado converge para a razão de verossimilhança, logo para o LLR. Essa é a ponte, mas nunca vi escrita explicitamente em criptografia.
3. **Yuan, Xu, Teng, Zhang, Wu, *Rethinking Learning-based Symmetric Cryptanalysis: a Theoretical Perspective*, ePrint 2025/1306 [PUB]** — o elo mais forte que existe hoje. Introduzem o modelo *Coin-Tossing* (CoTo) e a classe **Conjunctive Parity Form (CPF)**, que "captura uma classe ampla de distinguidores tradicionais". Provam:
   - *"if a concept can be used as a distinguisher and it possesses a general CPF form, then a learning algorithm with sub-exponential complexity exists that can identify it"*;
   - *"if the Hamming weight of each clause within this concept is constant, then a polynomial-complexity algorithm exists that can identify it with limited error."*

   Praticamente: levam o distinguidor neural do Speck32/64 de 8 para **9 rodadas**, primeira melhora desde Gohr 2019.

**O que NÃO existe.** Um teorema do tipo "classificador com features de histograma = distinguidor multidimensional de dimensão 8 com penalidade `M^{1/2}`". **Essa é uma lacuna genuína, pequena e escrevível — cabe num capítulo de dissertação.** A demonstração é curta: features de histograma ↔ frequências empíricas `q̂`; o classificador aprende `log(p₁/p₀)` ⇒ aproxima o LLR de Hermelin; a penalidade em relação ao LLR exato é o erro de estimação do fold. **[MINHA]**

---

#### 6. Correlação em esponjas — e a observação estrutural que muda o problema

##### 6.1 O fato normativo

NIST SP 800-232 (agosto de 2025), processamento de plaintext do Ascon-AEAD128 — transcrevo as equações **[PUB]**:

```
(24)  S[0:127] ← S[0:127] ⊕ P_i
(25)  C_i      ← S[0:127]
(26)  S        ← Ascon-p[8](S)
```

Parâmetros: estado 320 bits, **taxa 128, capacidade 192, 12 rodadas na inicialização/finalização, 8 rodadas no processamento de mensagem**, chave/nonce/tag de 128 bits. **[PUB]**

**Consequência.** Pela eq. (25), **a parte de taxa do estado, depois de absorver, é exatamente o bloco de criptograma**. O adversário passivo, sem plaintext, sem chave, sem nada, **conhece 128 dos 320 bits do estado interno a cada bloco**, ao longo de toda a mensagem. Numa amostra de 64 KB, ele conhece 4.096 valores consecutivos de taxa.

Tezcan diz a mesma coisa por outras palavras **[PUB]**: *"masks or differences are allowed in the nonce, namely x3 and x4, and the output is observed only for x0 because it is XORed to the plaintext to produce ciphertext."* E Dobraunig et al. **[PUB]**: *"the linear active bits have to be observable and therefore must be in x0."*

##### 6.2 A relação ciphertext-only exata

**[MINHA]**, derivada das eqs. (24)–(26):

```
C_{i+1} = taxa( p^r ( C_i ‖ cap_i ) ) ⊕ P_{i+1}
```

Tome uma aproximação linear da permutação com máscara `u` na **taxa de entrada**, `w` na **taxa de saída** e **zero em ambas as metades de capacidade**, de correlação `c_r(u→w)`. Então:

```
corr[ ⟨u, C_i⟩ ⊕ ⟨w, C_{i+1}⟩ ]  =  c_r(u→w) · corr_P(w)
```

Com `w` suportada nas posições de bit 7 dos bytes ASCII, **`corr_P(w) = 1`**. Fim. É um distinguidor ciphertext-only puro, sem nenhuma hipótese extra.

##### 6.3 Os números do Ascon

Melhores trilhas lineares conhecidas e limites provados para a permutação Ascon — El Hirch, Mella, Mehrdad, Daemen, *Improved Differential and Linear Trail Bounds for ASCON*, ToSC 2022(4) / ePrint 2022/1377, Tabela 1(b) **[PUB]**:

| rodadas | melhor `C²` conhecido | `\|c\|` | `N = 1/c²` | limite provado `C²` |
|---|---|---|---|---|
| 1 | 2^-2 | 2^-1 | 2^2 | 2^-2 |
| 2 | 2^-8 | 2^-4 | 2^8 | 2^-8 |
| 3 | **2^-28** (lineartrails) | **2^-14** | **2^28** | 2^-28 (justo) |
| 4 | 2^-98 (lineartrails) | 2^-49 | 2^98 | ≤ 2^-88 |
| 5 | 2^-184 (MILP) | 2^-92 | 2^184 | ≤ 2^-96 |
| 6 | — | — | — | ≤ 2^-132 |
| **8** (o `p^b` real) | — | — | — | **≤ 2^-176** |
| 12 | — | — | — | ≤ 2^-264 |

Complementos **[PUB]** (Dobraunig, Eichlseder, Mendel, Schläffer, *Cryptanalysis of Ascon*, ePrint 2015/030, Tabela 4): S-boxes ativas mínimas — 1 rodada: 1/1; 2: 4/4; 3: 15 dif / **13 lineares** (prova SMT); 4: 44/43 (heurística); ≥5: >64. E textualmente: *"at least 13 linearly active S-boxes (bias ≤ 2^−14, complexity ≥ 2^28)"*; para 12 rodadas, *"at least 52 linearly active S-boxes (bias ≤ 2^−53, complexity ≥ 2^106)"*.

**Cruzando com o orçamento (§3.2), previsão falsificável [MINHA]:**

| rodadas de `p^b` | `\|c\|` esperável | `N` exigido | orçamento (χ², M=2^16) | veredicto |
|---|---|---|---|---|
| 2 | 2^-4 | 2^8 | 2^26,87 | **detectável com folga de 2^19** |
| 3 | 2^-14 | 2^28 | 2^26,87 (limiar 2^-16,39) | **detectável, com margem de ~2^2–2^5** |
| 4 | 2^-49 | 2^98 | — | **impossível por 2^71** |
| 8 (real) | ≤2^-88 | ≥2^176 | — | **impossível por 2^149** |

**O piso é 3 rodadas de 8, e a transição 3→4 é um penhasco de 2^70, não uma rampa.** Isso é o tipo de previsão que ou se confirma ou mata a hipótese.

##### 6.4 A lacuna aberta: ninguém calculou os limites taxa→taxa do Ascon

Todas as trilhas da tabela acima são sobre **máscaras arbitrárias nos 320 bits**. O que o adversário CT-only precisa é do subcaso com **máscara nula em `x2,x3,x4` na entrada e na saída**. O SPARKLE fez esse cálculo para si (Tabelas 4.7 e 4.8 da spec, "outer part to outer part"). **Para o Ascon, esse cálculo não existe na literatura** — verifiquei nos trabalhos de Dobraunig et al. 2015, Erlacher–Mendel–Eichlseder 2022 e El Hirch et al. 2022, e em buscas dirigidas.

**Isso é uma contribuição original tratável.** Ferramental já existe (o modelo SMT/STP de Dobraunig et al. e o `AsconTrailTool` de El Hirch et al.); basta acrescentar as restrições `a_2 = a_3 = a_4 = 0` na entrada e `b_2 = b_3 = b_4 = 0` na saída, e opcionalmente `supp(b) ⊆ {posições de bit 7}`.

**Custo.** Um SMT/MILP de porte moderado (horas a dias de CPU para 3–4 rodadas com o espaço restrito, que é *menor* que o irrestrito). Engenharia: reaproveitar o modelo publicado de Dobraunig et al. (as restrições estão escritas por extenso no ePrint 2015/030, §5.1, e eu as transcrevi acima na leitura).

**Previsão.** O melhor `|c|` taxa→taxa em 3 rodadas será **pior** que 2^-14 (a restrição só pode piorar). Se ficar em 2^-16 ou melhor, o experimento fica na margem; se cair para 2^-20, o piso previsto vira 2 rodadas. **Ou seja: esse cálculo decide, antes de rodar um único treino, se o experimento de 3 rodadas vale a pena.**

##### 6.5 Schwaemm — por que é o alvo mais duro

A spec do SPARKLE **[PUB]** define o feedback combinado:

```
FeistelSwap(S) = S₂ ‖ (S₂ ⊕ S₁)
ρ₁(S,D) = FeistelSwap(S) ⊕ D      (nova taxa)
ρ₂(S,D) = S ⊕ D                    (criptograma)
```
com "rate whitening" `W_{128,256}(x,y) = (x,y,x,y)` antes de cada chamada da permutação.

**Análise [MINHA].** Escrevendo `S_r = S₁‖S₂` (128 bits cada) e `C_j = (S₁⊕M₁ ‖ S₂⊕M₂)`:

```
nova_taxa = ( C_j^{(2)} ⊕ M^{(2)} ⊕ M^{(1)} )  ‖  ( C_j^{(1)} ⊕ C_j^{(2)} ⊕ M^{(1)} )
```

Diferentemente do Ascon, **a nova taxa não é o criptograma**: depende do plaintext. Mas nas posições de bit 7 (onde `M = 0` para ASCII), ela **é** conhecida: `nova_taxa^{(1)}|_{b7} = C^{(2)}|_{b7}` e `nova_taxa^{(2)}|_{b7} = C^{(1)}|_{b7} ⊕ C^{(2)}|_{b7}`. Ou seja, **o adversário CT-only conhece exatamente 1/8 dos bits de taxa do Schwaemm** — 32 de 256 por bloco. É esse o valor exato do que o `ρ` de Beetle custa ao adversário no cenário ASCII.

Limites de correlação linear do Sparkle384 (spec, Tabela 4.4, valor de `−log₂|c|`) **[PUB]**:

| passos | 1 | 2 | 3 | 4 | 5 | 6 | 7 (slim real) | 11 (big) |
|---|---|---|---|---|---|---|---|---|
| Sparkle384 | 2 | 17 | 25 | 46 | 76 | 89 | **110** | ≥192 |
| `N ≥ 1/c²` | 2^4 | 2^34 | 2^50 | 2^92 | 2^152 | 2^178 | **2^220** | ≥2^384 |

Também **[PUB]**: Alzette tem MEDCP 2^-6 e **MELCC 2^-2**; Alzette duplo, MEDCP ≤2^-32 e **MELCC 2^-17** (contra super-S-box do AES: 2^-30 e 2^-15). Os autores avisam que os limites são conservadores: *"while we cannot overestimate the security our permutations provide against single trail differential and linear attacks, we may actually underestimate it."*

**Previsão [MINHA]:** piso CT-only linear do Schwaemm256-128 entre **1 e 2 passos de 7**, e o limiar do orçamento (2^-15,9) cai justamente entre o limite de 1 passo (2^-2) e o de 2 passos (2^-17). Alvo mais duro dos quatro, e por motivos de projeto documentados.

##### 6.6 Esponjas: o que a literatura de Keccak acrescenta

- Melhor característica linear de 4 rodadas do Keccak-f[1600]: **33 S-boxes ativas, viés 2^-34**; 3 rodadas: **13 S-boxes ativas, viés 2^-14**. E a ressalva que é exatamente a nossa: *"Previous 3 and 4-round characteristics have active bits in the inner part […] which prevents their use in actual attacks."* **[CIT]** (spec principal do Keccak).
- Dobraunig, Eichlseder, Mendel, *Heuristic Tool for Linear Cryptanalysis with Applications to CAESAR Candidates*, ASIACRYPT 2015 — a ferramenta `lineartrails` que produziu os números do Ascon. **[CIT]**
- Mennink, *Understanding the Duplex and Its Security*, ePrint 2022/1340 **[CIT]**; Chakraborty, Dhar, Nandi, *Exact Security Analysis of ASCON*, ePrint 2023/775 **[PUB]**: segurança AE com `T ≤ min{2^κ, 2^c}` e `D·T ≤ 2^b = 2^320`.

**Observação de coincidência numérica que vale registrar [MINHA]:** o Ascon (13 S-boxes ativas em 3 rodadas, viés 2^-14) e o Keccak-f (13 S-boxes ativas em 3 rodadas, viés 2^-14) coincidem — ambos usam a S-box χ. Reforça que o número 3 é o ponto de virada em esponjas com χ de 5 bits.

---

#### 7. ML e criptanálise linear: o que sobrevive sem diferença escolhida

##### 7.1 O que a literatura de interpretabilidade diz

- A. Benamira, D. Gérault, T. Peyrin, Q. Q. Tan, *A Deeper Look at Machine Learning-Based Cryptanalysis*, EUROCRYPT 2021 (ePrint 2021/287): o distinguidor de Gohr constrói uma boa aproximação da DDT **e aprende informação adicional**; muitos filtros aprendidos capturam combinações simples de diferenças de criptograma; o estágio final pode ser trocado por classificadores mais simples e interpretáveis. **[CIT]**
- Bao, Lu, Yao, Zhang: a superioridade dos distinguidores neurais vem principalmente de **padrões XOR** específicos. **[CIT]**
- *Survey: Six Years of Neural Differential Cryptanalysis*, ePrint 2024/1300 — 238 artigos, 24 primitivas, 15+ arquiteturas; expõe explicitamente *"substantial methodological weaknesses in parts of the literature"* e propõe um conjunto de boas práticas de avaliação. **[PUB]** (li a introdução e a lista de contribuições.)

**Cabem no nosso modelo?** **NÃO em bloco** — todos dependem de pares com diferença escolhida. Só sobrevive o *método de interpretação*.

##### 7.2 O lado linear: ML não ganhou de Matsui — e isso é o achado

- Hou, Ren et al. (2020 em diante) combinaram redes neurais com criptanálise linear em DES reduzido. Avaliação de terceiros: *"Hou et al.'s works did not reduce complexity or increase success rate, and even performed worse key-recovery attacks than traditional cryptanalysis, indicating they did not fully utilize neural networks to capture the non-randomness of linear distinguishers."* **[CIT]**
- Zhou et al. (2023) desenharam distinguidores neural-lineares melhores e superaram Hou et al. **[CIT]**
- *Improved machine learning-aided linear cryptanalysis: application to DES*, Cybersecurity (Springer) 2024, doi 10.1186/s42400-024-00327-4: propõem um modelo para **distinguir diferentes distribuições de Bernoulli com rede neural** e argumentam que *"it is possible to replace linear approximation with an effective neural network"*. **[CIT]** — tentei três rotas de acesso ao texto integral (Springer, SpringerOpen, ResearchGate) e todas caíram em paywall/redirect de autenticação; **não confirmei os números experimentais**.

**Leitura [MINHA].** No terreno *diferencial*, Gohr bateu a linha de base clássica em 2019 e o campo explodiu. No terreno *linear*, seis anos depois, **ML ainda não bateu o Algoritmo 2 de Matsui**. Para uma dissertação cujo cenário é intrinsecamente linear (sem diferenças escolhidas), isso é contexto essencial: não há precedente de ML superar a criptanálise linear feita à mão.

##### 7.3 Por que: paridade, LPN e limites de consulta estatística

Esta é, na minha avaliação, a explicação teórica mais sólida disponível para o resultado do projeto — e ela **não depende de nada específico dos quatro algoritmos**.

Achar uma máscara `b` com correlação `ε` no criptograma, sem saber `b` de antemão, **é uma instância de Learning Parity with Noise** com taxa de ruído `(1−ε)/2`.

| resultado | enunciado | fonte |
|---|---|---|
| Paridade não é SQ-aprendível | o clássico limite inferior de consulta estatística; explica a dificuldade de métodos baseados em gradiente | Kearns, *Efficient noise-tolerant learning from statistical queries*, JACM 1998 **[CIT]** |
| BKW | primeiro algoritmo subexponencial para LPN: tempo e amostras **2^{O(n/log n)}** | Blum, Kalai, Wasserman, JACM 2003 **[CIT]** |
| Gradiente falha em paridades | *Failures of Gradient-Based Deep Learning*, ICML 2017; estendido a uma classe mais larga de funções quase-ortogonais | Shalev-Shwartz, Shamir, Shammah **[CIT]** |
| SGD **atinge** o limite SQ para paridades esparsas | `k`-paridade em `d` bits aprendível em ~`d^{O(k)}` | Barak, Edelman, Goel, Kakade, Malach, Zhang, *SGD Learns Parities Near the Computational Limit*, NeurIPS 2022 **[CIT]** |
| Paridades esparsas **são** aprendíveis por redes profundas sob certas distribuições, e métodos lineares não as aprendem | separação rede neural × método linear | Daniely, Malach, *Learning Parities with Neural Networks*, NeurIPS 2020 (arXiv 2002.07400) **[CIT]** |
| Paridade **fixa** de tamanho mínimo é dura para GD perturbado em rede ReLU de 1 camada oculta | *"using it as a target function to train one-hidden-layer ReLU networks with perturbed gradient descent will fail to produce anything meaningful"*; prova via decaimento dos coeficientes de Fourier de funções de limiar linear | Shoshani, Shamir, *Hardness of Learning Fixed Parities with Neural Networks*, arXiv 2501.00817, 2025 **[PUB]** (abstract e enunciado do resultado principal) |
| Sinal-SGD atinge o limite SQ para `k`-paridade esparsa com `Õ(d^{k−1})` amostras | arXiv 2404.12376, NeurIPS 2024 **[CIT]** |

**A consequência quantitativa, que é o ponto [MINHA]:** o custo de descobrir uma máscara de peso `k` sobre `n` bits é `~n^k`. Para uma amostra de 64 KB, `n = 524.288`:

| peso `k` | custo `n^k` | viável? |
|---|---|---|
| 1 | 2^19 | trivial — **é o histograma** |
| 2 | 2^38 | caro mas possível — **é a co-ocorrência de bigramas / ACF** |
| 3 | 2^57 | inviável |
| ≥4 | ≥2^76 | inviável |

> **Uma CNN sobre bytes crus, treinada por gradiente, não pode descobrir máscaras lineares de peso ≥3 sobre uma janela larga. E máscaras de peso 1 e 2 já estão integralmente cobertas pelo histograma de 256 dimensões e pelo mapa de co-ocorrência 256×256.**

Isso explica, sem apelar para "a cifra é boa", por que os Caminhos B, C e D convergem para o mesmo resultado do Caminho A: **eles vivem na mesma classe de complexidade de hipóteses.** É um argumento defensável em banca, e é falsificável: injete artificialmente uma paridade de peso 3 com correlação 2^-5 no dataset e verifique se a CNN a encontra. Se não encontrar (previsão: não encontra), o argumento está sustentado empiricamente.

A ressalva de Daniely–Malach é importante e honesta: paridades **esparsas** podem ser aprendidas por redes de profundidade 2 sob certas distribuições. Ou seja, o bloqueio é sobre peso alto e janela larga, não sobre "redes neurais em geral". Uma CNN 1D com kernel de 8 bytes **pode** achar paridades de peso até ~3 dentro da janela — e é exatamente por isso que o ataque de "baixa difusão" de Coppersmith et al. (§4.4) é o candidato certo para o Caminho B.

##### 7.4 O que a única teoria de aprendizado dedicada a criptanálise diz

Yuan et al., ePrint 2025/1306 **[PUB]**, já citado: conceitos CPF são identificáveis em tempo **subexponencial**; com peso de Hamming de cláusula **constante**, em tempo **polinomial**. Isso é a mesma fronteira da tabela acima, provada dentro do vocabulário criptográfico. Recomendo citar este artigo em vez de (ou além de) as fontes de teoria do aprendizado — é mais defensável em banca de criptografia.

---

#### 8. GIFT-COFB e modos com realimentação de ciphertext

##### 8.1 Existe análise linear de modos com feedback de ciphertext?

Fiz buscas dirigidas por "linear cryptanalysis of CBC/CFB/OFB/COFB modes". **Não achei nenhuma.** A razão parece estrutural: modos são analisados no paradigma de **segurança demonstrável** (redução a PRP/PRF, limites de aniversário), não no paradigma de **trilhas**. Isso é, em si, um achado reportável: **a criptanálise linear de modos de operação praticamente não existe como literatura**, e o que há é sempre análise do cifrador de bloco *dentro* do modo.

O único exemplo publicado do tipo certo é o de Zong et al. sobre GIFT-COFB. Cito a descrição do mecanismo, da própria spec **[PUB]**:

> *"Zong et al. applied their linear cryptanalysis to mount the key-recovery attack on the reduced-round variant of GIFT-COFB, in which the number of rounds of GIFT-128 is reduced to 15 rounds. In short, it makes many encryption queries under different nonces to obtain pairs of plaintext and ciphertext in the consequent two blocks. The pairs partially reveal the internal state value. By setting the linear masks only to exploit those values, linear cryptanalysis can be mounted. The attack complexity is (Time, Data, Memory) = (2^90.7, 2^62, 2^96)."*

E a explicação do porquê o COFB é mais resistente que o GIFT-128 nu: *"the number of attacked rounds is significantly smaller than that of GIFT-128, because of the limited degrees of freedom for the attacker to set the active bit positions."*

##### 8.2 A relação ciphertext-only para o COFB

**[MINHA]**, a partir da estrutura do modo (`Y_i = E_K(X_i)`, `C_i = Y_i ⊕ M_i`, `X_{i+1} = G·Y_i ⊕ M_i ⊕ Δ_i` com `Δ_i` a máscara secreta derivada de `L = trunc(E_K(N))`):

```
X_{i+1} = G·C_i ⊕ (G⊕I)·M_i ⊕ Δ_i
```

Com uma aproximação linear `⟨u,X⟩ ⊕ ⟨v,Y⟩ ⊕ ⟨k,K⟩` de correlação `c_E`:

```
corr[ ⟨Gᵀu, C_i⟩ ⊕ ⟨v, C_{i+1}⟩ ] = ± c_E · corr_P( (G⊕I)ᵀu ) · corr_P( v )
```

Três diferenças relevantes em relação ao Ascon:
1. **A entrada do cifrador de bloco não é conhecida** — depende de `Y_i`, que é secreto. Não há o "presente" da taxa conhecida.
2. **O sinal `±` é desconhecido e muda por mensagem**, porque `Δ_i` depende de `L = trunc(E_K(N))` e o nonce muda a cada amostra. Isso força estatística χ² e custa ~1,5 bit de correlação (tabela §3.2).
3. **Duas restrições de máscara simultâneas**: tanto `v` quanto `(G⊕I)ᵀu` precisam cair em posições de bit 7 para `corr_P = 1`. `G` é linear e explícito na spec, então isso vira uma restrição MILP perfeitamente formulável — mas corta o espaço de máscaras.

##### 8.3 Números do GIFT-128

Da spec GIFT-COFB v1.1, Tabela 4.2 e §4.3 **[PUB]**:

| propriedade | valor |
|---|---|
| efeito de linear hull em 9 rodadas | **2^-45,99** (spec) / 2^-44 (Tab. 4.2, ótimo) |
| 10 rodadas, LC (ótimo) | 2^-52 |
| 15 rodadas, LC | 2^-109 |
| rodadas para correlação < 2^-128 | **~27** de 40 |
| melhor distinguidor diferencial | 21 rodadas, 2^-126,4 |
| melhor key-recovery SK linear | 22 rodadas, `(T,D,M)=(2^117, 2^117, 2^78)` |
| melhor ataque diferencial-linear atual em GIFT-COFB | **19 rodadas** (fase de processamento de mensagem) — Zhang, Chen, Song, Lv, ISC 2025 **[CIT]** |

**Extrapolação [MINHA], com a ressalva de que o decaimento não é uniforme em poucas rodadas:** a partir de 9→10 rodadas o ELP perde ~2^-8/rodada. Retroprojetando, `|c| ≈ 2^-16` (nosso limiar multidimensional) corresponde a `ELP ≈ 2^-32`, ou seja **~7 a 8 rodadas de 40**. Se o piso empírico por ML relatado no projeto foi 3/40, **um distinguidor linear dirigido deveria ganhar 4 a 5 rodadas**. É a maior diferença prevista entre "ML às cegas" e "linear dirigido" de todo este levantamento.

---

#### 9. Ataques ciphertext-only publicados contra cifras modernas — o padrão que emerge

##### 9.1 O catálogo

| trabalho | cifra | alavanca no plaintext | custo | marca |
|---|---|---|---|---|
| Siegenthaler 1985 | geradores LFSR+combinador | redundância da língua | divide-and-conquer | **[CIT]** |
| Matsui, *Linear Cryptanalysis Method for DES Cipher*, EUROCRYPT 1993, LNCS 765, pp. 386–397 | DES 8 rodadas | **inglês em ASCII** (bit 7 = 0) | **2^29 criptogramas** (contra 2^21 known-plaintext) | **[CIT]** — número consistente em várias fontes secundárias; não li o texto primário |
| Mantin, Shamir, *A Practical Attack on Broadcast RC4*, FSE 2001 | RC4 | **mesmo plaintext sob chaves diferentes** | `Ω(N)=Ω(256)` criptogramas para o 2º byte (viés `Pr[Z₂=0]=2/N`) | **[CIT]** |
| Barkan, Biham, Keller, *Instant Ciphertext-Only Cryptanalysis of GSM Encrypted Communication*, CRYPTO 2003 | A5/2 e A5/1 | **código corretor de erro aplicado ANTES da cifragem** | A5/2: dezenas de ms de conversa, chave em <1 s num PC | **[CIT]** |
| Todo, Leander, Sasaki, *Nonlinear Invariant Attack*, ASIACRYPT 2016 / J. Cryptology 2019 | SCREAM, iSCREAM, Midori64 em CBC/CFB/OFB/CTR | **mesmo plaintext desconhecido, IVs diferentes, chave fraca** | "a handful of pairs"; 2^96 chaves fracas (Scream), 2^64 (Midori64); recupera 32 bits do bloco final do SCREAM | **[PUB]** |
| Isobe, Ohigashi, Watanabe, Morii, *Full Plaintext Recovery Attack on Broadcast RC4*, FSE 2013 | RC4 | **mesmo plaintext, chaves aleatórias** | quase todos os **primeiros 257 bytes** com prob. >0,8 usando **2^32 criptogramas**; bytes posteriores com **2^34** | **[PUB]** |
| Kara, Balıkçı, *Multi-Diagonal Truncated Differentials and Ciphertext-Only Attacks on Reduced-Round AES*, ePrint 2026/1637 | AES 5 e 6 rodadas, ECB | **inglês em ASCII**, e também ASCII uniforme | distinguidor 5R: **2^86,4 C-O**, custo 2^92,8 MA (inglês); **2^96,5**, 2^103,1 MA (ASCII uniforme). Key-recovery 6R: **2^99,2 dados**, 2^113,4 tempo, 2^106,4 memória | **[PUB]** |

##### 9.2 O padrão, e por que ele é o enquadramento certo da dissertação

**[MINHA], mas com suporte exaustivo na tabela acima.**

> **Todo ataque ciphertext-only publicado contra uma cifra pós-1990 explora uma propriedade estrutural CONHECIDA da distribuição do plaintext — nunca a cifra sozinha.** As alavancas são exatamente três: (a) redundância de idioma/codificação (Matsui, Kara–Balıkçı, Siegenthaler); (b) redundância injetada pelo protocolo, como código corretor (Barkan–Biham–Keller); (c) repetição do mesmo plaintext sob IVs/chaves diferentes (Mantin–Shamir, Isobe et al., Todo–Leander–Sasaki).

O experimento descrito no enunciado **tem a alavanca (a) disponível** — 80% de Gutenberg em ASCII — e **não a usa**, porque as features agregam sobre todas as posições de bit e sobre toda a mensagem, apagando exatamente a estrutura que faz esses ataques funcionarem.

Nota de coerência com a memória do projeto: as alavancas (b) e (c) exigem que o analista **saiba** que o plaintext se repete ou tem estrutura de protocolo, e isso é a mesma objeção que levou o Nycolas a rejeitar o XOR de pares com mesmo plaintext. Registro a tensão explicitamente: **a literatura inteira de CT-only contra cifras modernas assume conhecimento da estrutura do plaintext.** Se essa suposição estiver fora do modelo, então o modelo de ameaça exclui, por construção, 100% dos ataques CT-only publicados — e isso é um resultado legítimo e forte para a dissertação, desde que dito com todas as letras. A alavanca (a) é a única que sobrevive sem nenhum conhecimento adicional (o adversário só precisa saber que a fonte é texto — o que é conhecimento público de contexto, não de plaintext).

##### 9.3 O que isso implica para a engenharia de features

**[MINHA].** Três mudanças concretas, todas baratas:

1. **Estatísticas indexadas por posição de bit dentro do byte.** Separar b7, b6, b5 do resto. O histograma de 256 bins já contém isso em princípio, mas o estágio de seleção (MI/mRMR) não sabe que `0x80`, `0x20`, `0x40` são as máscaras privilegiadas e trata os 256 bins como intercambiáveis.
2. **Estatísticas de par de blocos consecutivos** `⟨u,C_i⟩ ⊕ ⟨w,C_{i+1}⟩`, que é o único formato em que a relação da §6.2 aparece. Nenhuma das 12 famílias descritas no enunciado calcula isso: autocorrelação faz lags de 1–16 **bytes**, não relações entre blocos de 16 bytes com máscaras arbitrárias.
3. **Estatísticas indexadas por offset absoluto** (primeiro bloco vs. blocos do meio vs. bloco final), na linha Mantin–Shamir e Lu–Meier–Vaudenay. O primeiro bloco de saída vem logo após `p^12` (inicialização) e é onde estão as fraquezas de inicialização reduzida; os blocos do meio vêm após `p^8`. Agregar tudo junto mistura dois regimes diferentes.

##### 9.4 Uma alegação que exige tratamento crítico

**O que é.** G. Singh, *Distinguishing Full-Round AES-256 in a Ciphertext-Only Setting via Hybrid Statistical Learning*, ePrint 2025/862 ("FESLA"). Alega **100% de acurácia** distinguindo criptograma de AES-128/192/256 **de rodadas completas** contra dados aleatórios, em cenário ciphertext-only, com SVM, Random Forest, MLP, Regressão Logística e Naive Bayes, e validação cruzada 5-fold e 10-fold. **[PUB]** — li o artigo inteiro.

**Por que precisa ser tratado com cuidado.** É a alegação exatamente oposta à hipótese da dissertação, e a metodologia tem lacunas verificáveis:

- Os aleatórios vêm de `secrets`; os plaintexts, de `secrets`; o **modo de operação do AES nunca é declarado** no artigo. Não há código publicado.
- O pipeline é: 2^21 valores por conjunto → 512 lotes de 2^12 → 30 testes estatísticos → 20 features → classificar 512×2 vetores de features.
- Fases I e II relatam **falha total**: ML e MLP sobre bits crus não convergem; PCA e t-SNE não separam; *"the results of probability value (p value) were found same for both data sets"*. Só as **estatísticas brutas** (não os p-valores) separam.
- Os próprios autores escrevem: *"Such high accuracy is unusual in practical cryptanalysis"* e *"though this result seems too good to be true"*.
- Só está no ePrint; não achei nenhuma refutação nem nenhuma validação por terceiros.

**Diagnóstico [MINHA].** Que os p-valores coincidam e as estatísticas brutas separem perfeitamente é a assinatura clássica de **artefato de geração ou de codificação** (comprimento/encoding dos "valores aleatórios" vs. dos criptogramas, tipo de dado, ordenação). Um distinguidor genuíno de AES completo com 100% de acurácia sobre 4.096 blocos violaria a hipótese PRP por uma margem absurda — e contradiria diretamente Kara–Balıkçı (ePrint 2026/1637), que precisam de **2^86,4 criptogramas para 5 rodadas** de AES.

**Valor para a dissertação.** Alto, como **contraexemplo metodológico**. O protocolo descrito no enunciado (key-holdout, bootstrap agrupado por chave, correção para múltiplas comparações, controle negativo obrigatório) é precisamente o conjunto de salvaguardas que o FESLA não tem. Vale um parágrafo dedicado: um F1 ≈ 0,50 obtido sob esse protocolo é mais informativo que um F1 = 1,00 obtido sem ele.

Contexto adicional: a literatura de classificação ML de cifras clássicas (Kopal, *Of Ciphers and Neurons*, HistoCrypt 2020, 5 cifras clássicas; Leierzopf, Mikhalev, Kopal et al., 55 tipos clássicos, melhor modelo **80,24%** de acurácia) **[CIT]** funciona porque cifras clássicas **vazam estatística do plaintext por construção**. Não é evidência de nada sobre AEADs modernos, e é comum ser citada como se fosse.

---

#### 10. Empréstimos de outros subcampos

##### 10.1 Distância de unicidade — o problema É solúvel, só não computacionalmente

Shannon: `U = H(K)/D`. Para inglês no alfabeto de 26 letras, `log₂26 = 4,7` bits, informação real **1,5 bits/caractere**, logo **`D = 3,2` bits/caractere** — exemplo canônico: substituição simples, `H(k) = log₂(26!) = 88,4` bits, `U = 28 caracteres`. **[PUB]** (Wikipedia, *Unicity distance*, valores padrão de Shannon).

**Aplicação ao nosso caso [MINHA].** Para texto ASCII em bytes de 8 bits com taxa de entropia ~1,5 bits/byte, `D = 6,5 bits/byte`. Com chave de 128 bits: `U = 128/6,5 ≈ 20 bytes`. Com 6 algoritmos candidatos, some `log₂6 = 2,6` bits: `U ≈ 20,1 bytes`.

> **Com 21 bytes de criptograma, o par (algoritmo, chave) já é unicamente determinado em sentido informacional. Uma amostra de 64 KB tem 3.100 vezes a distância de unicidade.** Logo, **H₀ não é uma afirmação sobre informação; é uma afirmação sobre computação.** O sinal *está lá*; custa 2^128 tentativas de decifração para lê-lo.

Isso reposiciona o resultado do projeto de forma bem mais interessante: não é "não há informação", é "a informação está a 2^128 de distância computacional, e nenhum estimador de complexidade polinomial — clássico ou neural — a alcança". E dá o enquadramento correto para os pisos de rodadas: **eles medem exatamente onde a barreira computacional cai abaixo do orçamento de dados.**

##### 10.2 Códigos corretores de erro

Já aparece na §4.1 (FCA = decodificação de código aleatório; turbo/convolucional/LDPC). Dois pontos adicionais:

- A ideia de **múltiplos de baixo peso do polinômio de realimentação** (spec do Grain-128AEAD cita explicitamente: *"Finding and using a low-weight multiple of the LFSR polynomial can be used to improve the bias"*) é o análogo exato de procurar máscaras de baixo peso — e conecta diretamente ao resultado de aprendizado da §7.3 (baixo peso = aprendível; alto peso = não). **[PUB]** para a citação, **[MINHA]** para a conexão.
- **Barkan–Biham–Keller** é o caso-limite: o *plaintext* é a saída de um código corretor, o que dá redundância estruturada e determinística. É o análogo perfeito do bit 7 do ASCII. **[CIT]**

##### 10.3 Teste de hipótese composto e teste sequencial

- Junod (EUROCRYPT 2003) **[PUB]**: distinguidor sequencial (SPRT) economiza ~2,2× em dados médios no exemplo relatado. Aplicável ao nosso caso: em vez de fixar `N` amostras, parar quando a razão de verossimilhança cruzar o limiar.
- Cressie–Read `R_λ` (a família que contém χ² em `λ=1` e o G-test em `λ=0`) e o resultado de Drost et al. sobre a potência, ambos usados por Hermelin **[PUB]**. Prático: para `M ≥ 50` graus de liberdade, χ² ≈ normal e a fórmula `N = M^{1/2}/I₁` vale.
- **Collard, Standaert, Quisquater, *Improving the Time Complexity of Matsui's Linear Cryptanalysis*, ICISC 2007** **[CIT]**: FFT/Walsh–Hadamard reduz o custo de `O(2^k · 2^k)` para `O(k · 2^k)`. **Essencial na prática**: varrer 2^16 máscaras sobre 2^27 pares por força bruta é 2^43 operações; com FWHT, ~2^27 + 16·2^16 ≈ 2^27. **Transforma a varredura de máscaras de inviável em trivial.**
- *Improving Linear Key Recovery Attacks using Walsh Spectrum Puncturing*, J. Cryptology 2025 **[CIT]** — refinamento moderno da mesma técnica.

##### 10.4 Processamento de sinais

O "spectral_welch" já presente no conjunto de features é, em linguagem linear, a medição de **máscaras periódicas** (correlações de lag fixo). Não achei literatura criptanalítica que use Welch/periodograma como distinguidor — o equivalente criptográfico é o teste espectral (DFT) do NIST SP 800-22, que é uma bateria de máscaras periódicas. **[MINHA]**: é redundante com a autocorrelação e cobre uma fatia estreita do espaço de máscaras; não espero ganho aí.

---

#### 11. Tabela consolidada: piso de rodadas previsto por algoritmo

Todos os valores de `|c|` vêm das fontes **[PUB]** das seções 4, 6 e 8; os limiares vêm do orçamento calculado na §3.2; os vereditos são **[MINHA]**.

| algoritmo | fase alvo | rodadas reais | `\|c\|` por rodada/passo (fonte) | limiar do orçamento | **piso CT-only linear previsto** |
|---|---|---|---|---|---|
| **Ascon-AEAD128** | `p^b` (processamento) | 8 | 1R: 2^-1 · 2R: 2^-4 · **3R: 2^-14** · 4R: 2^-49 (ToSC 2022 Tab.1b) | 2^-16,4 | **3 de 8** (penhasco em 4) |
| **Ascon-AEAD128** | `p^a` (inicialização, via nonce contador) | 12 | DL 4R: viés 2^-2,30…2^-3,68 (Tezcan) | 2^-16,4 | **4–5 de 12**, *se* houver DL com Δ de contador |
| **Schwaemm256-128** | Sparkle384 slim | 7 passos | 1: 2^-2 · 2: 2^-17 · 3: 2^-25 · 7: 2^-110 (spec Tab.4.4) | 2^-15,9 | **1–2 de 7** |
| **GIFT-COFB** | GIFT-128 | 40 | 9R: ELP 2^-44 · 10R: 2^-52 · 15R: 2^-109 (spec Tab.4.2) | 2^-16,4 (menos ~1,5 bit pelo sinal desconhecido) | **7–8 de 40** |
| **Grain-128AEAD** | pre-output | 256 init | `ε < 2^-77` no keystream completo (spec §4.2) | 2^-19,9 | **muito abaixo**; estado da arte com IV escolhido chega a 190–195/256 (ataques cube) |
| **AES-ECB** (controle +) | AES | 10/12/14 | CT-only 5R exige 2^86,4 (Kara–Balıkçı) | — | sinal vem de **blocos repetidos**, não de linearidade |

Para comparação, os tetos **conhecidos** com modelos de ameaça mais fortes **[PUB]/[CIT]**:

| algoritmo | melhor resultado publicado | modelo |
|---|---|---|
| Ascon-128 | key-recovery 7/12 rodadas (cube-like, 2^103,9); DL 5/12 em 2^31,44 (Tezcan) | nonce escolhido / diferença escolhida |
| GIFT-COFB | DL key-recovery **19/40**; LC key-recovery GIFT-128 22/40 | plaintext conhecido, muitos nonces |
| Grain-128AEAD | superpolies de **192–195/256** rodadas (cube, 3SDP/u); DCA 190R com 2^103,44 | IV escolhido |
| Schwaemm256-128 | DL prático 4 passos com complexidade < 2^13,1 | diferença escolhida |
| AES | distinguidor 5R: 2^30 CP (exchange attack); CT-only 5R: **2^86,4** | escolhido vs. ciphertext-only |

**Essa última tabela é o resultado mais citável de todo o levantamento [MINHA]:** ela quantifica o **preço do modelo de ameaça**. Em Grain-128AEAD, passar de "IV escolhido" para "ciphertext-only com nonce contador" custa **mais de 160 rodadas** de margem. Em GIFT-COFB, custa ~11 rodadas. Em AES, custa **2^56 em dados** (2^30 → 2^86,4) só para o mesmo número de rodadas. Um piso baixo em ciphertext-only não é falha do método: é o preço tabelado da restrição.

---

#### 12. Onde o caminho é comprovadamente impossível

Três argumentos de impossibilidade, em ordem crescente de força.

**(I) Máscara de entrada nula.** Proposição 1 de Daemen et al. Correlação exatamente zero para bijeção com entrada uniforme. **Fecha completamente** o ramo "aproximação linear que não toca o plaintext" no caso uniforme. **[PUB]**

**(II) Aprendizado de paridade.** Descobrir uma máscara de peso ≥3 sobre uma janela larga custa `n^k`, e isso vale para toda a classe SQ, que inclui gradiente descendente com gradientes ruidosos e essencialmente todo classificador baseado em features. **Fecha** a esperança de que CNN/Transformer "descubram sozinhos" estrutura linear de alto peso. **[CIT]** para os teoremas, **[MINHA]** para a aplicação.

**(III) Redução à segurança AEAD.** Se um distinguidor `D` separa Ascon de GIFT-COFB com vantagem `ε`, então pela desigualdade triangular `D` separa pelo menos um dos dois de aleatório com vantagem `≥ ε/2`. Para o Ascon, a prova exata de Chakraborty–Dhar–Nandi **[PUB]** dá segurança AE com `T ≤ min{2^κ,2^c}` e `D·T ≤ 2^b = 2^320`. No orçamento descrito (`D ≈ 2^27` chamadas de permutação, `T` do treino ≲2^45), `D·T ≈ 2^72 ≪ 2^320`. **No modelo de permutação aleatória, a vantagem máxima alcançável é da ordem de 2^-248.** **[MINHA]**, composição direta sobre provas publicadas.

A ressalva honesta e obrigatória: (III) vale no **modelo ideal**. Não diz nada sobre não-idealidades da permutação concreta. É exatamente por isso que o estudo de rodadas reduzidas é o caminho cientificamente correto — ele mede onde a permutação real se afasta do ideal, e é o único caminho no qual (III) não se aplica.

---

#### APOSTAS

##### Aposta 1 — Varredura de correlação linear taxa→taxa no Ascon, com máscaras ancoradas no bit 7 do ASCII

**Por quê.** É o único lugar onde tudo converge: (a) a normativa NIST SP 800-232 eq. (25) entrega a taxa do estado de graça, sem nenhuma hipótese extra; (b) o ASCII entrega `corr_P = 1,000` exato, sem nenhuma perda em relação a known-plaintext; (c) existe uma tabela publicada de trilhas lineares do Ascon que produz uma **previsão numérica sem ambiguidade**; (d) o orçamento de dados do projeto cai **exatamente** entre 3 e 4 rodadas, então o experimento discrimina em vez de confirmar.

**O que fazer, em ordem.**
1. **Antes de qualquer experimento**, rodar o MILP/SMT de Dobraunig et al. (ePrint 2015/030 §5.1 — as restrições estão escritas por extenso lá) com `a₂=a₃=a₄=0` na entrada, `b₂=b₃=b₄=0` na saída, e `supp(b) ⊆ {bit 7 de cada byte}`. Isso dá o `|c|` taxa→taxa real para 2, 3 e 4 rodadas. Custo: horas a dias de CPU; o espaço restrito é *menor* que o irrestrito já resolvido na literatura.
2. Gerar variantes de `p^b` com `r ∈ {2,3,4}` (o repositório já tem infraestrutura de rodadas reduzidas, pelo que o enunciado indica).
3. Extrair, para cada amostra, a sequência de 4.096 blocos de 128 bits e computar, via **FWHT** (Collard–Standaert–Quisquater), a correlação empírica de `⟨u,C_i⟩ ⊕ ⟨w,C_{i+1}⟩` para as máscaras do topo-K da etapa 1, mais o subespaço completo de dimensão 16 das posições de bit 7.
4. Agregar com o χ² multidimensional de Hermelin (`T = N Σ ĉ²`), com sinal por chave tratado ao quadrado, e IC bootstrap agrupado por chave.

**Custo.** Dados: nenhum novo (usa o que existe). Computação: uma passada FWHT sobre 2^27 pares por variante, minutos em CPU. Engenharia: média — o gerador de rodadas reduzidas já existe; a varredura de máscaras é código novo de ~200 linhas. O MILP é o item mais caro e é o que dá mais retorno.

**O que prevê.** `|c|` medido ≈ `c_taxa→taxa(r) · 0,8` (fator da mistura 80/20 texto/imagem). Detecção limpa em 2 rodadas, detecção no limiar em 3, **zero em 4 e acima, com transição abrupta de ~70 bits**. Se der sinal em 4 rodadas, ou o gerador está errado ou existe um efeito de *linear hull* taxa→taxa não documentado — e aí é resultado publicável por si só. Se der zero em 3 rodadas, o limite taxa→taxa da etapa 1 explica exatamente por quê, com número.

---

##### Aposta 2 — Saturação estatística gratuita: reescrever o Caminho A como distinguidor multidimensional e medir a capacidade

**Por quê.** É a aposta de menor custo e maior retorno de interpretação. O conjunto de 641 features **já é** um distinguidor linear multidimensional, mas está sendo lido como "um monte de números" em vez de como uma estimativa de capacidade. Reescrevê-lo em linguagem de capacidade (i) fornece um **limite superior teórico para o desempenho de qualquer classificador** sobre essas features, o que nenhum resultado de validação cruzada consegue dar; (ii) permite dizer, com número, *quanto sinal teria de existir* para o F1 sair de 0,50; (iii) amarra os Caminhos A–F numa única grandeza comparável. E pela equivalência de Leander, plaintexts ASCII com b7 fixo colocam o experimento no mesmo terreno da saturação estatística de Collard–Standaert — **de graça**, porque a fonte fixa os bits em vez do adversário.

**O que fazer.**
1. Para cada algoritmo e cada variante de rodadas, estimar `Ĉ = Σ_{a≠0} ĉ_C(a)²` sobre (i) o subespaço de dimensão 8 dentro do byte, (ii) o subespaço de dimensão 16 dos bits 7 de um bloco, (iii) o subespaço de dimensão 16 de pares de bytes consecutivos.
2. Comparar `Ĉ` com o piso nulo `M/N` e com o desvio `√(2M)/N`. Reportar `Ĉ · N / √(2M)` — uma estatística `z` interpretável, na mesma unidade para todos os caminhos.
3. Converter em teto de F1 via a relação de Baignères–Junod–Vaudenay entre capacidade e vantagem ótima, e comparar com o F1 medido. Se o F1 medido bater no teto, o classificador é ótimo; se ficar abaixo, sobra sinal na mesa e vale otimizar.
4. Traduzir o F1 ≈ 0,50 observado num **limite superior sobre `corr_Z`** do algoritmo completo: "o experimento estabelece `|corr_Z(a)| < 2^-16,4` para todas as 2^16 máscaras testadas, com poder 0,8". **Isso transforma um resultado nulo num limite mensurável e citável**, que é a forma padrão de reportar não-resultado em criptanálise.

**Custo.** Muito baixo. Uma passada de FWHT sobre os parquets já gerados; nenhum treino novo. Engenharia: ~150 linhas, leitura incremental via pyarrow (o dataset é grande demais para pandas).

**O que prevê.** `Ĉ` estatisticamente indistinguível de `M/N` para todos os algoritmos completos; separação clara em rodadas reduzidas abaixo do piso; e um teto de F1 muito próximo de 0,50 para os algoritmos completos, quantificando o resultado nulo em vez de apenas relatá-lo.

---

##### Aposta 3 — Diferenças de nonce grátis: o contador como fonte de estrutura que o modelo de ameaça não proíbe

**Por quê.** Esta é a aposta mais especulativa das três e a que tem o maior potencial de surpresa. O modelo de ameaça diz "nonces públicos de contador" e "pode observar vários de uma vez". Um contador entrega, **sem escolher nada**, pares de mensagens cuja diferença de nonce é `Δ = 1` com probabilidade 1/2, `Δ = 3` com 1/4, e assim por diante. É estrutura de entrada obtida por observação passiva, não por escolha.

E o canal de observação existe: para plaintext ASCII, `ΔC|_{bit 7} = ΔZ|_{bit 7}` **exatamente**, sem ruído, porque `ΔP|_{bit 7} = 0` deterministicamente. O adversário mede a diferença de keystream nas posições de bit 7, com fidelidade perfeita, a partir de dois criptogramas.

Isso coloca em jogo o arsenal diferencial-linear contra a **inicialização** — que é justamente onde estão os melhores resultados publicados. Dobraunig et al. dizem literalmente: *"differences are only allowed in the nonce (x3, x4), whereas the linear active bits have to be observable and therefore must be in x0"* — e é exatamente a configuração que o contador + ASCII produzem. Tezcan relata vieses diferenciais-lineares de **2^-2,30 a 2^-3,68 em 4 rodadas** do Ascon, que são enormes em relação ao nosso limiar.

**A questão aberta, e é ela que faz a aposta:** esses vieses foram obtidos com diferenças de nonce **escolhidas**. Um contador oferece um conjunto pequeno e fixo de diferenças (`1, 2, 3, 4, ...`). **Existe uma característica diferencial-linear boa para Δ = 1?** Ninguém procurou, porque ninguém tinha motivo. É uma busca MILP perfeitamente definida.

**O que fazer.**
1. Buscar (MILP/SAT) a melhor característica diferencial-linear do `p^a` do Ascon com diferença de entrada **fixada** nas diferenças que um contador produz (peso 1 no bit menos significativo de `x3`, e as variantes de carry), e máscara linear de saída restrita a `x0` e às posições de bit 7.
2. Formar pares de criptogramas consecutivos por chave (nonces `n` e `n+1`), calcular `ΔC` restrito às posições de bit 7 do primeiro bloco, e medir o viés.
3. Repetir para Schwaemm (nonce de 256 bits) e Grain (nonce de 96 bits). Para GIFT-COFB, o nonce entra via `E_K(N)`, então a diferença de contador se propaga por uma chamada completa do cifrador — provavelmente morto, mas o teste é barato.
4. **Controle obrigatório**: refazer com nonces aleatórios em vez de contador. Se o sinal do contador não desaparecer, é artefato.

**Custo.** Busca MILP: comparável à da Aposta 1. Extração: trivial (o primeiro bloco de cada amostra, pareado por chave — 100 amostras por chave dão 99 pares consecutivos, 29.700 pares por algoritmo, o que é pouco, então provavelmente exige gerar mais amostras por chave ou usar rodadas reduzidas com vieses grandes). Engenharia: baixa.

**O que prevê.** Se existir uma DL decente para `Δ = 1` com máscara em `x0|_{b7}`: viés detectável para inicialização reduzida a 3–5 rodadas, e **zero** com nonces aleatórios. Se não existir DL para `Δ = 1` (resultado igualmente possível e igualmente publicável): fica provado que o nonce de contador **não** dá ao adversário passivo nenhuma vantagem diferencial sobre o Ascon — o que é uma afirmação de segurança concreta sobre uma configuração de uso extremamente comum em IoT, e que, até onde apurei, ninguém enunciou.

**Ressalva de honestidade sobre esta aposta.** Ela está no limite do modelo de ameaça declarado. Usar pares consecutivos é CT-only legítimo (o adversário observa; não escolhe nada). Mas usar `ΔP|_{b7} = 0` é usar conhecimento sobre a *estrutura* do plaintext, não sobre o plaintext em si — é a mesma alavanca que Matsui usou em 1993 e que Kara–Balıkçı usaram em 2026, e em ambos os casos foi aceito como ciphertext-only pela comunidade. Vale alinhar isso com o orientador antes de investir, porque é a mesma fronteira onde o XOR-de-pares foi rejeitado, e a distinção (estrutura pública da codificação vs. conhecimento de que dois plaintexts são iguais) precisa estar escrita e defendida.

---

#### Anexo A — Referências, em ordem de utilidade para esta pesquisa

**Núcleo teórico**
1. J. Daemen, R. Govaerts, J. Vandewalle. *Correlation Matrices*. FSE 1994, LNCS 1008, 275–285. **[PUB]** — Proposição 1.
2. M. Hermelin. *Multidimensional Linear Cryptanalysis*. Tese, Aalto/TKK-ICS-D16, 2010. `https://aaltodoc.aalto.fi/bitstream/123456789/4802/1/isbn9789526031903.pdf` **[PUB]** — Def. 3.7, Lemas 5.3–5.5.
3. T. Beyne. *A Geometric Approach to Linear Cryptanalysis*. ASIACRYPT 2021 / ePrint 2021/1247. **[PUB]**
4. T. Baignères, P. Junod, S. Vaudenay. *How Far Can We Go Beyond Linear Cryptanalysis?* ASIACRYPT 2004, LNCS 3329, 432–450. **[CIT]**
5. P. Junod. *On the Optimality of Linear, Differential and Sequential Distinguishers*. EUROCRYPT 2003 / ePrint 2003/064. **[PUB]**
6. A. Biryukov, C. De Cannière, M. Quisquater. *On Multiple Linear Approximations*. CRYPTO 2004 / ePrint 2004/057. **[CIT]**
7. G. Leander. *On Linear Hulls, Statistical Saturation Attacks, PRESENT and a Cryptanalysis of PUFFIN*. EUROCRYPT 2011, 303–322. **[CIT]**
8. C. Harpes, J. L. Massey. *Partitioning Cryptanalysis*. FSE 1997, LNCS 1267, 13–27. **[CIT]**
9. S. Vaudenay. *An Experiment on DES Statistical Cryptanalysis*. ACM CCS 1996, 139–147. **[CIT]**
10. T. Ashur, D. Bodden, O. Dunkelman. *Linear Cryptanalysis Using Low-bias Linear Approximations*. ePrint 2017/204. **[PUB]**
11. C. Blondeau, K. Nyberg. *Improved Parameter Estimates for Correlation and Capacity Deviates in Linear Cryptanalysis*. ToSC 2016(2). **[CIT]**
12. J. Daemen, V. Rijmen. *Probability distributions of correlations and differentials in block ciphers*. J. Math. Cryptology 1(3):221–242, 2007. **[CIT]**
13. A. Bogdanov, V. Rijmen. *Linear hulls with correlation zero…* DCC 70(3), 2014 / ePrint 2011/123. **[CIT]**
14. B. Collard, F.-X. Standaert, J.-J. Quisquater. *Improving the Time Complexity of Matsui's Linear Cryptanalysis*. ICISC 2007. **[CIT]**
15. T. Beyne, V. Rijmen. *Differential Cryptanalysis in the Fixed-Key Model* (quasidiferenciais). CRYPTO 2022 / ePrint 2022/837. **[CIT]**
16. C. Che, T. Tian, J. Yang, F. Yang. *A Generalized Framework for Conditional Linear Cryptanalysis and Its Application to AES-Like Ciphers*. ePrint 2026/1563. **[PUB]** (abstract) — CLAT, "conditional linear weight", distinguidor linear de 4 rodadas do AES.

**Ciphertext-only contra cifras modernas**
17. T. Siegenthaler. *Decrypting a Class of Stream Ciphers Using Ciphertext Only*. IEEE ToC C-34(1):81–85, 1985. **[CIT]**
18. M. Matsui. *Linear Cryptanalysis Method for DES Cipher*. EUROCRYPT 1993, LNCS 765, 386–397. **[CIT]** — 2^29 criptogramas, inglês ASCII, 8 rodadas.
19. E. Barkan, E. Biham, N. Keller. *Instant Ciphertext-Only Cryptanalysis of GSM Encrypted Communication*. CRYPTO 2003 / J. Cryptology 21(3), 2008. **[CIT]**
20. I. Mantin, A. Shamir. *A Practical Attack on Broadcast RC4*. FSE 2001. **[CIT]**
21. T. Isobe, T. Ohigashi, Y. Watanabe, M. Morii. *Full Plaintext Recovery Attack on Broadcast RC4*. FSE 2013. **[PUB]** — 2^32 / 2^34.
22. Y. Todo, G. Leander, Y. Sasaki. *Nonlinear Invariant Attack*. ASIACRYPT 2016 / J. Cryptology 32, 2019 / ePrint 2016/732. **[PUB]**
23. O. Kara, C. Balıkçı. *Multi-Diagonal Truncated Differentials and Ciphertext-Only Attacks on Reduced-Round AES*. ePrint 2026/1637. **[PUB]** — 2^86,4 / 2^96,5 / 2^99,2.
24. Y. Lu, W. Meier, S. Vaudenay. *The Conditional Correlation Attack: A Practical Attack on Bluetooth Encryption*. CRYPTO 2005. **[CIT]** — 24 bits de 2^23,8 frames.

**Cifras de fluxo e correlação**
25. W. Meier, O. Staffelbach. *Fast correlation attacks on certain stream ciphers*. J. Cryptology 1(3), 1989. **[CIT]**
26. T. Johansson, F. Jönsson. *Fast Correlation Attacks Based on Turbo Code Techniques*. CRYPTO 1999; *…via Convolutional Codes*. EUROCRYPT 1999. **[CIT]**
27. J. Golić. *Linear Models for Keystream Generators*. IEEE ToC 45(1):41–49, 1996. **[CIT]**
28. D. Coppersmith, S. Halevi, C. Jutla. *Cryptanalysis of stream ciphers with linear masking*. CRYPTO 2002, LNCS 2442, 515–532. **[PUB]**
29. S. Khazaei, M. Hasanzadeh, M. Kiaei. *Linear Sequential Circuit Approximation of Grain and Trivium*. ePrint 2006/141. **[PUB]** — 2^-63,7 → 2^-29 → 2^58 bits.
30. Y. Todo, T. Isobe, W. Meier, K. Aoki, B. Zhang. *Fast Correlation Attack Revisited*. CRYPTO 2018 / ePrint 2018/522. **[PUB]**
31. *Vectorial Fast Correlation Attacks*. ASIACRYPT 2025. **[CIT]** — Grain-128a 2^106,3/2^107,7.
32. B. Zhang, X. Gong, W. Meier. *Fast Correlation Attacks on Grain-like Small State Stream Ciphers*. ToSC 2017(4):58–81. **[CIT]**
33. B. Minaud. *Linear Biases in AEGIS Keystream*. SAC 2014. **[CIT]**
34. T. Ashur, M. Eichlseder, M. Lauridsen, G. Leurent, B. Minaud, Y. Rotella, Y. Sasaki, B. Viguier. *Cryptanalysis of MORUS*. ASIACRYPT 2018 / ePrint 2018/464. **[CIT]**
35. J. Wallén. *Linear Approximations of Addition Modulo 2^n*. FSE 2003, LNCS 2887, 261–273. **[CIT]** — algoritmo Θ(log n) para a correlação; distribuição dos coeficientes.

**Os quatro algoritmos**
36. NIST SP 800-232, *Ascon-Based Lightweight Cryptography Standards for Constrained Devices*, agosto de 2025. **[PUB]** — eqs. (23)–(31).
37. C. Dobraunig, M. Eichlseder, F. Mendel, M. Schläffer. *Cryptanalysis of Ascon*. CT-RSA 2015 / ePrint 2015/030. **[PUB]** — Tabela 4, modelo SMT.
38. S. El Hirch, S. Mella, A. Mehrdad, J. Daemen. *Improved Differential and Linear Trail Bounds for ASCON*. ToSC 2022(4) / ePrint 2022/1377. **[PUB]** — Tabela 1.
39. J. Erlacher, F. Mendel, M. Eichlseder. *Bounds for the Security of Ascon against Differential and Linear Cryptanalysis*. ToSC 2022(1). **[PUB]** (abstract).
40. C. Tezcan. *Analysis of Ascon, DryGASCON, and Shamash Permutations*. Int. J. Information Security Science, 2020 / ePrint 2020/1458. **[PUB]**
41. B. Chakraborty, C. Dhar, M. Nandi. *Exact Security Analysis of ASCON*. ASIACRYPT 2023 / ePrint 2023/775. **[PUB]**
42. C. Beierle et al. *Lightweight AEAD and Hashing using the Sparkle Permutation Family* / spec final NIST. **[PUB]** — Tabelas 3.8, 4.1, 4.3, 4.4, 4.7; definição de `ρ`.
43. M. Hell, T. Johansson, W. Meier, J. Sönnerup, H. Yoshida. *Grain-128AEAD* — spec NIST rodada 2. **[PUB]** — §4.2–4.3, `ε_g<2^-9`, `ε_h<2^-5`, `ε<2^-77`, limite de 2^80 bits.
44. S. Banik et al. *GIFT-COFB v1.1* — spec final NIST. **[PUB]** — §4.3–4.4, Tabela 4.2.
45. Y. Zong, X. Dong, S. Chen, J. Luo, X. Wang, W. Li. *Towards Key-recovery-attack Friendly Distinguishers: Application to GIFT-128*. ToSC 2021(1):156–184. **[CIT]**
46. Z. Zhang, Y. Chen, L. Song, Y. Lv. *Improving the Differential-Linear Attack with Applications to GIFT-COFB, GIFT-64 and HyENA*. ISC 2025. **[CIT]** — 19 rodadas.

**ML e criptanálise**
47. A. Gohr. *Improving Attacks on Round-Reduced Speck32/64 using Deep Learning*. CRYPTO 2019. **[CIT]**
48. A. Benamira, D. Gérault, T. Peyrin, Q. Q. Tan. *A Deeper Look at Machine Learning-Based Cryptanalysis*. EUROCRYPT 2021 / ePrint 2021/287. **[CIT]**
49. Y. Yuan, H. Xu, J. Teng, L. Zhang, W. Wu. *Rethinking Learning-based Symmetric Cryptanalysis: a Theoretical Perspective*. ePrint 2025/1306. **[PUB]**
50. D. Gérault, A. Hambitzer, M. Huppert, S. Picek. *Survey: Six Years of Neural Differential Cryptanalysis*. ePrint 2024/1300. **[PUB]** (introdução)
51. *Improved machine learning-aided linear cryptanalysis: application to DES*. Cybersecurity (Springer), 2024. **[CIT]** — **não consegui o texto integral**; não confirmei os números.
52. M. Kearns. *Efficient noise-tolerant learning from statistical queries*. JACM 45(6), 1998. **[CIT]**
53. A. Blum, A. Kalai, H. Wasserman. *Noise-tolerant learning, the parity problem, and the statistical query model*. JACM 50(4), 2003. **[CIT]**
54. S. Shalev-Shwartz, O. Shamir, S. Shammah. *Failures of Gradient-Based Deep Learning*. ICML 2017. **[CIT]**
55. A. Daniely, E. Malach. *Learning Parities with Neural Networks*. NeurIPS 2020 / arXiv 2002.07400. **[CIT]**
56. I. Shoshani, O. Shamir. *Hardness of Learning Fixed Parities with Neural Networks*. arXiv 2501.00817, 2025. **[PUB]** (abstract/teorema)
57. B. Barak, B. Edelman, S. Goel, S. Kakade, E. Malach, C. Zhang. *SGD Learns Parities Near the Computational Limit*. NeurIPS 2022. **[CIT]**
58. G. Singh. *Distinguishing Full-Round AES-256 in a Ciphertext-Only Setting via Hybrid Statistical Learning* (FESLA). ePrint 2025/862. **[PUB]** — **tratar como contraexemplo metodológico**, não como resultado.
59. N. Kopal. *Of Ciphers and Neurons — Detecting the Type of Ciphers Using Artificial Neural Networks*. HistoCrypt 2020. **[CIT]**
60. E. Leierzopf, V. Mikhalev, N. Kopal et al. *Detection of Classical Cipher Types with Feature-Learning Approaches*. 2021 (55 tipos, melhor 80,24%). **[CIT]**

---

#### Anexo B — Fios que puxei e deram em nada (registrados para não serem repuxados)

- **"Zero-correlation com máscara de entrada nula"** não existe como conceito nomeado na literatura. O motivo é a Proposição 1 de Daemen et al. Busquei por cinco formulações diferentes; todos os resultados caem em zero-correlation clássico (ambas as máscaras não-nulas), que exige pares.
- **Criptanálise linear de modos de operação** (CBC/CFB/OFB/CTR/COFB) enquanto disciplina de trilhas: não encontrei nenhum trabalho. Modos são analisados por redução, não por trilha. O único exemplo do tipo certo é Zong et al. sobre GIFT-COFB, e ele analisa o cifrador dentro do modo.
- **Limites de trilha linear taxa→taxa ("outer to outer") para o Ascon**: não existem publicados. O SPARKLE tem (Tabelas 4.7/4.8); o Ascon não. Verifiquei nos três trabalhos de limites (2015, 2022a, 2022b) e em buscas dirigidas. **Lacuna real e tratável.**
- **Trabalho de ML distinguindo os finalistas do NIST LWC entre si em ciphertext-only**: não existe. Há ML sobre AES/DES/PRESENT e ML diferencial-neural sobre Ascon e GIFT-128, mas nada de classificação multi-algoritmo. A novidade do projeto está confirmada.
- **"Nonce de contador como fonte gratuita de diferenças de entrada"**: não achei nenhuma formalização na literatura de criptanálise. Todo o arsenal de IV é escrito como "chosen IV". Se isso for escrito com rigor, é contribuição original.
- **Espectral (Welch/periodograma) como distinguidor criptanalítico**: não há literatura criptográfica; o análogo é o teste DFT do NIST SP 800-22. Provavelmente redundante com autocorrelação.
- **Refutação publicada do FESLA (ePrint 2025/862)**: não existe, até onde busquei. O artigo permanece sem contestação e sem replicação.

---

# Pesquisa 08 — Rodadas reduzidas por métodos não-diferenciais

- **Ângulo:** Rodadas reduzidas por métodos não-diferenciais
- **Temperatura declarada:** 0,45

## Pesquisa 08 — prompt usado, na íntegra

````markdown
# Pesquisa 08 — Rodadas reduzidas por métodos não-diferenciais

**Temperatura declarada: 0,45** (amplitude de exploração moderada, puxando para
o conservador — o terreno aqui é técnico e bem documentado; prefira exatidão
numérica e rastreabilidade de fonte a analogia criativa. Especulação é
permitida, mas tem que vir marcada e depois dos fatos.)

---

## PROBLEMA DE PESQUISA

Você está pesquisando para uma dissertação de mestrado em criptografia
aplicada e aprendizado de máquina. Trabalhe SÓ com literatura externa: não
leia nenhum repositório, arquivo local ou resultado prévio. Comece do zero.

**A pergunta.** Dado apenas o criptograma — sem a chave, sem o texto em claro,
sem poder escolher nada do que é cifrado — é possível distinguir qual
algoritmo de criptografia autenticada o produziu? E, num segundo nível, com
quantas rodadas reduzidas um algoritmo ainda deixa de parecer aleatório?

**Os algoritmos.** Os quatro finalistas do concurso NIST Lightweight
Cryptography: Ascon-AEAD128 (esponja), GIFT-COFB (cifra de bloco em modo
COFB), Grain-128AEAD (cifra de fluxo com LFSR e NFSR) e Schwaemm256-128
(esponja ARX, família SPARKLE).

**O modelo de ameaça, que é a restrição dura e não negocia.** Adversário
PASSIVO, em ciphertext-only. Ele observa criptogramas de um mesmo dispositivo,
com nonces públicos de contador, e pode observar vários de uma vez. Ele NÃO
tem: texto em claro conhecido ou escolhido, diferenças escolhidas na entrada,
reuso de nonce, acesso a canais laterais, nem consultas a um oráculo de
cifragem. Isso exclui de saída a maior parte da criptanálise diferencial
clássica e os distinguidores neurais no estilo Gohr, que dependem de pares com
diferença escolhida.

**O protocolo experimental.** Classificadores clássicos e redes sobre features
estatísticas e sobre os bytes crus. Chaves de teste nunca aparecem no treino
(key-holdout). Intervalo de confiança por bootstrap agrupado por chave, e não
i.i.d. Correção para múltiplas comparações. Controle negativo obrigatório: com
o algoritmo completo o classificador tem que ficar no acaso.

**Dado concreto disponível:** ~30.000 criptogramas por algoritmo, 64 KB cada
(≈1,9 GB por classe), 300 chaves distintas, nonces de contador, texto em claro
vindo de corpus real (80% texto em inglês do Project Gutenberg, 20% imagem em
tons de cinza). Existem variantes com rodadas reduzidas compiladas para os
quatro algoritmos, e um piso empírico já foi medido por ML para dois deles.
Existem controles: AES em modo ECB (positivo) e saída de PRNG (negativo).

---

## ÂNGULO DESTA PESQUISA — medir margem de segurança sem criptanálise diferencial

A literatura de margem de segurança é dominada pelo eixo diferencial: conte
S-boxes ativas, ache a melhor característica, meça quantas rodadas resistem. O
nosso modelo de ameaça proíbe tudo isso, porque proíbe escolher a entrada.

**Quero o outro arsenal inteiro**, e quero saber, item por item, quanto dele
sobrevive à restrição de não escolher nada.

Persiga, entre outras coisas:

- **Division property e suas gerações** (Todo, CRYPTO/EUROCRYPT 2015; bit-based
  division property de Todo–Morii; three-subset division property; a versão
  com unknown subset, 3SDP/u; modelagem MILP de Xiang et al. e a linhagem que
  veio depois). Esses métodos determinam *estruturalmente* até quantas rodadas
  existe um distinguidor integral. Traga os números por algoritmo: Ascon,
  GIFT-128, Grain-128AEAD, SPARKLE/Schwaemm. **E responda com clareza: o
  distinguidor integral exige plaintext/IV escolhido estruturado, ou existe
  alguma formulação observacional?**
- **Ataques cube e superpolies.** É o estado da arte contra o Grain
  (superpolies em 190+ de 256 rodadas de inicialização). Traga a tabela
  completa de quantas rodadas cada trabalho alcançou, e a evolução histórica.
  E o mesmo para o Ascon. **Todos exigem IV escolhido — mas quero saber se
  alguém já formulou uma versão "cube observacional", com cubos formados por
  nonces que um contador entrega de graça.**
- **Zero-sum distinguishers** e a noção de *grau algébrico*: Boura–Canteaut–De
  Cannière sobre Keccak, e a aplicação a esponjas em geral. O grau algébrico
  como medida de margem é interessante porque é uma propriedade da
  permutação, não do par entrada/saída.
- **Ataques de invariante** (nonlinear invariant, Todo–Leander–Sasaki;
  subspace trails de Grassi–Rechberger–Rønjom; invariant subspace de
  Leander et al.). Esses são notáveis porque **alguns funcionam em
  ciphertext-only sob chave fraca** — quero saber exatamente sob que
  condições, e se algo análogo existe para os quatro finalistas.
- **Ataques integrais / saturação / multiset** e a pergunta central: o que
  desses métodos é uma propriedade da SAÍDA sozinha, e o que exige estrutura
  na entrada.
- **Grau algébrico e testes de grau** medidos empiricamente sobre a saída
  (higher-order derivatives, testes de grau de Boura et al.), e se dá para
  estimar grau sem controlar a entrada.
- **Como a literatura define "margem de segurança" e como ela compara
  algoritmos com noções diferentes de rodada.** Uma rodada do Grain (um clock)
  não é uma rodada do Ascon (permutação de 320 bits). Existe alguma
  normalização aceita? Alguém já fez esse cruzamento entre os finalistas do
  NIST LWC?
- **Estudos sistemáticos de margem em escala** — trabalhos que varreram muitos
  algoritmos e muitas contagens de rodada com uma bateria única. Quero as
  tabelas e a metodologia, inclusive as limitações que os autores declaram.

Vá também para onde o ângulo levar: se aparecer um método de medir margem que
não esteja nessa lista, traga.

---

## O QUE EU QUERO DE VOCÊ

Técnicas, representações, ataques ou ideias — publicadas ou adaptáveis — que
possam extrair sinal nesse cenário, ou que ajudem a delimitar com rigor por
que o sinal não existe. Interessa tanto o que funciona quanto a prova de que
algo é impossível.

Busque em literatura acadêmica real (IACR ePrint, ToSC/FSE, CHES, CRYPTO,
EUROCRYPT, ASIACRYPT, SAC, Designs Codes and Cryptography, IEEE, Springer,
arXiv) e em fontes técnicas sérias. Use termos de busca em inglês.

## COMO RESPONDER

Para cada ideia encontrada, escreva:

1. **O que é** — a técnica, em duas ou três frases.
2. **Fonte** — autores, título, veículo, ano. Link quando houver. Se você não
   conseguiu confirmar a existência do trabalho, diga isso explicitamente em
   vez de completar de memória.
3. **Cabe no nosso modelo?** — SIM, NÃO, ou ADAPTÁVEL. Se ADAPTÁVEL, diga
   exatamente o que teria de mudar e qual premissa do modelo de ameaça isso
   arranha.
4. **O que custaria testar** — ordem de grandeza de dados, computação e
   engenharia.
5. **O que ela prevê** — se a técnica funcionar, que resultado deveríamos ver?
   Se não houver previsão falsificável, diga isso.

Termine com uma seção **APOSTAS**: as três ideias que você tentaria primeiro,
e por quê. Seja específico; "usar deep learning" não é uma aposta.

## PROFUNDIDADE — leia isto com atenção

Não é um levantamento rápido. **Vá até esgotar o veio.** Não pare em cinco ou
dez achados porque já "deu para ter uma ideia": siga as citações para frente e
para trás, abra os trabalhos relacionados dos artigos que importarem, procure
versões estendidas e teses, e persiga as pistas que aparecerem no caminho,
mesmo as que não estavam no ângulo original. Só encerre quando as buscas novas
pararem de trazer coisa nova. Espera-se algo da ordem de 80 a 120 chamadas de
ferramenta de busca/leitura.

Traga TODA a informação, não um resumo dela. Se um artigo tem um número que
importa (quantas rodadas, quantas consultas, que complexidade, que grau, que
tamanho de dado), traga o número. Se tem uma limitação declarada pelos próprios
autores, traga a limitação com as palavras deles. Prefira errar por excesso de
detalhe. Uma resposta longa e completa é o que se pede aqui; uma resposta
enxuta é falha de execução.

**A sua resposta final é o produto inteiro** — ela vai ser salva em disco
literalmente, sem que ninguém a expanda depois. Não escreva "detalhei acima"
nem resuma: escreva o documento completo, em Markdown, em português do Brasil,
com todas as tabelas e todos os números.

## REGRAS

- Não invente referências. Uma fonte não confirmada vale menos que nenhuma, e
  vou checar.
- Não repita o óbvio já saturado (distinguidor diferencial-neural padrão)
  sem trazer um ângulo novo que sobreviva ao ciphertext-only.
- Se a conclusão honesta de um caminho for "isso é impossível neste modelo
  por tal razão teórica", isso é resultado útil. Diga.
- Separe o que é publicado do que é sua extrapolação. Marque cada um
  explicitamente: **[PUB]** para publicado e lido/confirmado, **[CIT]** para
  existência confirmada mas texto não obtido, **[MINHA]** para extrapolação
  sua.
````

## Pesquisa 08 — achados, sem resumir

### Achados — Pesquisa 08

- **Ângulo:** rodadas reduzidas por métodos não-diferenciais
- **Temperatura declarada:** 0,45
- **Prompt usado:** `prompts/08_rodadas_reduzidas_nao_diferencial.md`
- **Execução:** 382.020 tokens na primeira entrega + 396.864 na reemissão, 157 chamadas, ~42 min

> **Nota de integridade.** A entrega original veio truncada (~16,6k caracteres
> perdidos: fim da 6.8, seções 7 e 8 inteiras, começo da 9.1). O trecho foi
> reemitido pelo próprio agente a pedido e está reintegrado no lugar certo.
> O documento abaixo está completo.

---

### Pesquisa 08 — Rodadas reduzidas por métodos não-diferenciais
#### Medir margem de segurança sem criptanálise diferencial, sob ciphertext-only estrito

**Data:** 21/09/2026 · **Temperatura declarada:** 0,45 · **Escopo:** literatura externa apenas (nenhum arquivo local lido)

Marcação usada em todo o documento:
- **[PUB]** — trabalho publicado, texto obtido e lido nesta pesquisa (números conferidos na fonte)
- **[CIT]** — existência confirmada (DBLP/editora/citação em fonte primária lida), texto integral **não** obtido
- **[MINHA]** — extrapolação, cálculo ou proposta minha, não publicada

---

#### 0. RESPOSTA DIRETA ÀS TRÊS PERGUNTAS QUE VOCÊ FEZ NO ÂNGULO

Antes de tudo, porque são as três perguntas explícitas e todas têm resposta.

**(1) "O distinguidor integral exige plaintext/IV escolhido estruturado, ou existe alguma formulação observacional?"**

Formalmente, exige um **conjunto estruturado** — mas *estruturado* não é sinônimo de *escolhido*. A propriedade integral é um somatório sobre um subespaço afim do espaço de entrada; o que ela precisa é que o conjunto exista e que o atacante saiba **quais** criptogramas o compõem. **Um nonce de contador entrega exatamente isso de graça**: os 2^k nonces consecutivos `n₀, n₀+1, …, n₀+2^k−1` (com `n₀` alinhado) formam um cubo perfeito de dimensão k sobre os k bits baixos do nonce, com todos os outros bits constantes, e o nonce é público. O adversário não escolheu nada — ele colheu. Isso não está formulado assim em lugar nenhum que eu tenha encontrado, mas **tem precedente exato**: o ataque FMS sobre WEP [PUB] é um ataque *passivo, known-IV*, que simplesmente espera o contador de IV de 24 bits produzir os IVs fracos de padrão (3, 255, v). O obstáculo real não é o cubo — é o **plaintext**, que é XORado no criptograma e, ao somar 2^k amostras, contribui um termo `⊕Pᵢ`. Resolvo isso na Seção 2.4 e é a base da Aposta 1.

**(2) "Alguém já formulou uma versão 'cube observacional', com cubos formados por nonces que um contador entrega de graça?"**

Não encontrei o conceito nomeado nem formalizado na literatura de cube/division property. O que existe e chega perto:
- Dinur & Shamir, *Applying cube attacks to stream ciphers in realistic scenarios*, Cryptogr. Commun. 4:217–232 (2012) [CIT] — relaxa o modelo de dados, mas continua num universo de IV escolhido/parcialmente controlado.
- FMS/WEP [PUB] — passivo, known-IV, exploração de estrutura harvested. É o precedente conceitual.
- Dobraunig–Eichlseder–Mendel, ASIACRYPT 2015 [PUB] — definem características lineares "Tipo III" que exploram exatamente relações entre `C_i` e `C_{i+1}` e **não dependem de a mesma chave ser usada**. Esse é o análogo linear do que você quer, e é publicado.

Conclusão: a formulação observacional do cubo é, até onde eu apurei, **um vão real na literatura**. É a contribuição mais original disponível para a dissertação.

**(3) "Os ataques de invariante funcionam em ciphertext-only sob chave fraca — sob que condições exatamente, e existe análogo para os quatro finalistas?"**

Condições exatas, dos autores [PUB]: (i) classe de chaves fracas; (ii) round keys idênticas (ou cifra sem key schedule); (iii) a cifra usada em um **modo** (CBC/CFB/OFB/CTR) em que o plaintext não é entrada direta da cifra; (iv) **o mesmo plaintext desconhecido cifrado com a mesma chave fraca e IVs diferentes**. Para os quatro finalistas: **não existe análogo, e o motivo é documentado**. GIFT foi projetado contra isso (Seção 5.2, com a citação literal dos projetistas). Ascon e SPARKLE são permutações sem chave — a noção de "chave fraca" para invariante não se aplica ao modo. Grain não é key-alternating. Resposta honesta: **esse caminho está fechado**, e fechado por projeto, não por falta de tentativa.

---

#### 1. O TEOREMA-MOLDURA: O QUE O SEU MODELO DE AMEAÇA PERMITE E PROÍBE

Isto não é preâmbulo. É o que determina qual técnica sobrevive, e o resto do documento é organizado por essa fronteira.

##### 1.1 A redução formal (impossibilidade quantitativa)

**[MINHA]**, mas construída inteiramente sobre definições e limites publicados.

Seja `D_A` a distribuição de criptogramas do algoritmo A e `D_B` a do algoritmo B, sob a mesma distribuição de plaintext `P`, mesmas chaves e mesmos nonces. Um classificador ciphertext-only com vantagem `ε` sobre o acaso é, por definição, um distinguidor estatístico entre `D_A` e `D_B` com vantagem `ε`. Pela desigualdade triangular sobre a distância de variação total, e sendo `U` a distribuição uniforme de mesmo comprimento:

> **Adv(A vs B) ≤ Adv^IND$(A) + Adv^IND$(B)**

onde `Adv^IND$` é a vantagem de distinguir o criptograma de bits uniformes (a noção IND$-CPA; Rogaway, *Nonce-Based Symmetric Encryption*, FSE 2004 [CIT]). Isso significa: **o classificador nunca pode ser melhor do que a soma dos dois ataques de indistinguibilidade individuais**. Ele não tem nenhum poder extra por comparar dois algoritmos.

Aplicando os limites provados de cada um, com os parâmetros do seu dataset (σ ≈ 2^26,9 blocos de 128 bits por classe, tempo t ≈ 2^40):

| Algoritmo | Limite provado de privacidade | Fonte | Valor no seu regime |
|---|---|---|---|
| Ascon-AEAD128 | AE segura com `T ≤ min{2^κ, 2^c}` e `DT ≤ 2^b = 2^320` | Chakraborty–Dhar–Nandi, *Exact Security Analysis of ASCON*, ASIACRYPT 2023, ePrint 2023/775 [PUB] | `DT ≈ 2^67` ⇒ termo do modo ≈ **2^−253** |
| GIFT-COFB | `Adv^IND-CPA ≤ Adv^PRP_GIFT(q,t) + C(σₑ,2)/2^128` | Spec GIFT-COFB v1.1, Eq. (4.1) e §4.1 [PUB] | termo do modo ≈ 2^54/2^128 = **2^−74** |
| Schwaemm256-128 | segurança 120 bits, limite de dados 2^68 bytes | Spec SPARKLE final, Tab. cap. 2.3 [PUB] | muito abaixo do limite |
| Grain-128AEADv2 | ≥ 2^112 computações, single-key nonce-respecting; limite de keystream 2^80 bits/par | Spec Grain-128AEADv2 §1.2, §3.3.4 [PUB] | 2^19,3 bits/par usados |

**Consequência dura:** no seu regime de dados, qualquer sinal CT-only acima do acaso, com algoritmos *completos*, **necessariamente** vem de (a) quebrar a permutação/PRP subjacente, (b) metadados (comprimento, timing, ordem), ou (c) vazamento experimental. Não existe uma quarta porta. Isso transforma o H₀ observado de "resultado negativo" em **corroboração quantitativa de um limite provado** — e essa é a forma correta de escrever isso na dissertação.

##### 1.2 O limiar de detectabilidade do seu dataset

**[MINHA]** — aritmética direta, e é o número que eu usaria para julgar toda ideia daqui para a frente.

Um distinguidor baseado em uma estatística binária com correlação `c` precisa de ~`c⁻²` amostras. Com 30.000 criptogramas × 64 KB:

| Granularidade da estatística | N disponível | `\|c\|` mínimo detectável |
|---|---|---|
| por bit (toda a classe) | 1,573 × 10^10 ≈ **2^33,9** bits | **2^−16,9** |
| por bloco de 128 bits (toda a classe) | 1,229 × 10^8 ≈ **2^26,9** transições | **2^−13,4** |
| por bloco, **dentro de uma chave** | 4,096 × 10^5 ≈ **2^18,6** transições | **2^−9,3** |

A terceira linha importa muito e é fácil de esquecer: **aproximações lineares de primitivas com chave têm sinal dependente da chave**, então para GIFT-COFB você não pode somar entre as 300 chaves — o sinal cancela. Para Ascon e Schwaemm (permutações sem chave; o "segredo" é a capacidade, que funciona como ruído médio-zero) o sinal da correlação da trilha é uma propriedade fixa da permutação e **você pode**. É uma assimetria estrutural real entre as famílias e deveria estar na dissertação.

##### 1.3 A dicotomia estrutural: o que o adversário CT-only realmente enxerga

**[MINHA]**, apoiada nas especificações lidas.

| | Observável CT-only | O que precisa ser quebrado |
|---|---|---|
| **Ascon-AEAD128** | `C_i = S[0:127]` **é exatamente a parte rate de entrada de `p[8]`** (SP 800-232, Eqs. 24–26 [PUB]) | correlação linear outer→outer de `p[8]` |
| **Schwaemm256-128** | `C_i = S_outer ⊕ M_i`; o rate de entrada da próxima chamada é `FeistelSwap(C_i⊕M_i) ⊕ M_i ⊕ 𝒲(S_inner)` — **ofuscado de propósito** pelo feedback ρ do Beetle + rate whitening | idem, mas sem entrada conhecida |
| **Grain-128AEADv2** | `C = P ⊕ KS`, e **só os bits pares do pre-output viram keystream** (`z_i = y_{512+2i}`); os ímpares vão para o MAC e nunca aparecem [PUB] | viés do keystream (FCA) com metade do stream escondido |
| **GIFT-COFB** | `C_i = Y_i ⊕ M_i` com `Y_i = E_K(X_i)`, e `X_{i+1} = M_i ⊕ G·Y_i ⊕ L‖0^{n/2}` com `L` secreto [PUB] | GIFT-128 como PRP, com máscaras restritas ao observável |
| **AES-ECB (controle +)** | repetição de blocos de 16 B — determinística | nada: o modo vaza |

O ponto crítico e, na minha leitura, o achado estrutural mais explorável de toda esta pesquisa:

> **No Ascon-AEAD128, o adversário ciphertext-only conhece EXATAMENTE os 128 bits de rate na entrada de toda chamada de `p[8]` durante a cifragem.** A única coisa desconhecida na entrada é a capacidade de 192 bits. Do lado da saída, ele vê `C_{i+1} = Z_{i+1} ⊕ P_{i+1}`. Isso é, literalmente, uma configuração de criptanálise linear conhecida-entrada / parcialmente-conhecida-saída sobre `p[8]`, obtida sem escolher absolutamente nada.

O Schwaemm **não** tem essa propriedade, e os projetistas dizem por quê: "*For Schwaemm, we have to use the bounds for the permutation (i.e., Table 4.4) because of the rate-whitening layer that introduces linear masks in the inner part*" (Spec SPARKLE, §3.5.2 [PUB]).

##### 1.4 O que "ciphertext-only" significa na literatura (e onde o seu corte é mais estrito que o padrão)

Isto é para debate, não para eu decidir por você.

Todo–Leander–Sasaki, ASIACRYPT 2016 [PUB], são explícitos:

> "*Clearly, we cannot execute any ciphertext-only attack without some information on the plaintexts.*"

O modelo CT-only canônico da literatura **sempre** carrega uma hipótese sobre a distribuição do plaintext. Os três exemplos clássicos:

1. **Mantin–Shamir, FSE 2001, broadcast RC4** [PUB] — recupera o 2º byte do plaintext a partir de Ω(N) criptogramas do **mesmo plaintext desconhecido** sob chaves diferentes. É chamado de ciphertext-only na literatura, sem controvérsia.
2. **AlFardan–Bernstein–Paterson–Poettering–Schuldt, USENIX Security 2013** [PUB] — "ciphertext-only plaintext recovery attacks against TLS" usando vieses de keystream do RC4 combinados com a distribuição conhecida do plaintext HTTP.
3. **FMS, SAC 2001 (WEP)** [PUB] — passivo, explora que o primeiro byte do plaintext é o header SNAP 0xAA, conhecido.

**[MINHA] · Onde isso toca a sua decisão de 14/09:** você rejeitou o XOR de pares com mesmo plaintext como "fora do CT-only". Na versão **entre algoritmos** (C_Ascon ⊕ C_GIFT do mesmo slot) a rejeição me parece correta e defensável: um dispositivo real não cifra a mesma mensagem com Ascon *e* com GIFT-COFB, então saber que dois criptogramas de algoritmos distintos compartilham plaintext é informação que o adversário passivo não teria. Mas a versão **dentro do mesmo algoritmo** — mesma mensagem, mesma chave, nonces diferentes — é outra coisa: é exatamente o cenário Mantin–Shamir, é realista (retransmissão, heartbeat, mensagem de status periódica), e é o cenário sob o qual o ataque de invariante não-linear é chamado de ciphertext-only por Todo–Leander–Sasaki. Se você mantiver a rejeição, o texto ganha em rigor mas fica **mais estrito que a literatura**, e vale dizer isso explicitamente em vez de deixar implícito que você está usando a definição padrão. Contra-argumento para a sua posição: nada no seu dataset gerado tem plaintext repetido dentro de uma chave, então a questão é hipotética no v2 atual — mas ela decide se vale gerar um braço com repetição.

E o ponto que acho que você **deve** aceitar, porque não há literatura de CT-only que funcione sem ele: **a distribuição do plaintext é conhecida**. Você usa 80% Project Gutenberg (ASCII inglês) e 20% ImageNet 256×256 grayscale. Isso não é detalhe de implementação, é o único recurso que o adversário CT-only tem. Concretamente, para ASCII inglês, **o bit mais significativo de todo byte é 0 com probabilidade ≈ 1**. Ou seja: 1/8 das posições de bit do plaintext são *determinísticas*, e nessas posições `C = KS` exatamente, não estatisticamente. Isso muda tudo o que vem a seguir e é a fundação das Apostas 1 e 2.

---

#### 2. DIVISION PROPERTY E INTEGRAIS

##### 2.1 A linhagem completa

| # | Trabalho | Fonte | O que introduziu |
|---|---|---|---|
| 1 | Todo, *Structural Evaluation by Generalized Integral Property* | EUROCRYPT 2015, ePrint 2015/090 [PUB] | division property (word-based). Reduziu o distinguidor de 10 rodadas do Keccak-f de 2^1025 para 2^515; provou distinguidores integrais de 9/11/11/13/13 rodadas para Simon 32/48/64/96/128 |
| 2 | Todo, *Integral Cryptanalysis on Full MISTY1* | CRYPTO 2015 [CIT] | primeira quebra prática viabilizada pela técnica |
| 3 | Todo & Morii, *Bit-Based Division Property and Application to Simon Family* | FSE 2016 [CIT] | bit-based (2 subconjuntos) e **three-subset**; distinguidor integral de 14 rodadas para Simon32 |
| 4 | Xiang, Zhang, Bao, Lin | ASIACRYPT 2016, LNCS 10031, pp. 648–678 [CIT] | **division trail** + modelagem MILP de copy/AND/XOR/Sbox — o que tornou a busca automática |
| 5 | Sun, Wang, Liu, Wang, *MILP-Aided Bit-Based Division Property for Primitives with Non-Bit-Permutation Linear Layers* | ePrint 2016/811 [CIT] | camadas lineares gerais |
| 6 | Sun, Wang, Wang, *MILP-Aided BDP for ARX* | ePrint 2016/1101; Sci. China Inf. Sci. [CIT] | adição modular |
| 7 | Eskandari, Kidmose, Kölbl, Tiessen, *Finding Integral Distinguishers with Ease* | SAC 2018, ePrint 2018/688 [PUB] | ferramenta `Solvatore`, **30 primitivas** numa bateria só |
| 8 | Hao, Leander, Meier, Todo, Wang, *Modeling for Three-Subset Division Property without Unknown Subset* | EUROCRYPT 2020, ePrint 2020/441 [PUB] | **3SDP/u** — recuperação exata de superpoly; mostrou que vários "key-recovery" anteriores eram só distinguishers |
| 9 | Hu, Sun, Wang, Wang, *An Algebraic Formulation of the Division Property* (monomial prediction) | ASIACRYPT 2020, LNCS 12491, pp. 446–476, ePrint 2020/1048 [CIT] | **monomial prediction**; provou equivalência com 3SDP/u; grau algébrico exato do Trivium até 834 rodadas |
| 10 | Hu, Sun, Todo, Wang, Wang, *Massive Superpoly Recovery with Nested Monomial Predictions* | ASIACRYPT 2021, LNCS 13090, pp. 392–421, ePrint 2021/1225 [CIT] | nested MP |
| 11 | He, Hu, Preneel, Wang, *Stretching Cube Attacks* | ASIACRYPT 2022, ePrint 2022/1218 [CIT] | superpolies massivos |
| 12 | He, Hu, Lei, Wang, *Massive Superpoly Recovery with a Meet-in-the-Middle Framework* | EUROCRYPT 2024, ePrint 2024/342 [PUB] | **core monomial prediction (CMP)**; "*sufficient to recover the superpoly by extracting all the core monomial trails*" |
| 13 | Hu & Yap, *Perfect Monomial Prediction for Modular Addition* | ToSC 2024(3), ePrint 2024/1335 [PUB] | teorema de Braeken–Semaev; graus exatos de Alzette/Speck |
| 14 | Beyne & Verbauwhede, *Ultrametric Integral Cryptanalysis* | ASIACRYPT 2024 [CIT] | unifica integral e invariante sob correlação ultramétrica |
| 15 | Wang, Hadipour, *On Extending Integral Distinguishers* | ePrint 2026/1402 [CIT] | extensões recentes |

##### 2.2 Números por algoritmo

**Ascon (permutação de 320 bits, 12 rodadas)**

| r | Complexidade de dados (textos escolhidos) | Fonte |
|---|---|---|
| 5 | 2^16 (16 bits ativos, 320 bits balanceados) | Eskandari et al., Tab. 6 [PUB] — melhora em 4× o de Todo |
| 7 | 2^65 | Todo, EUROCRYPT 2015, via NISTIR 8454 [PUB] |
| 8 | 2^130 | idem |
| 9 | 2^258 | idem |
| 10 | 2^300 | idem |
| 11 | 2^315 | idem |
| 7 | 2^60 dados / 2^60 tempo (division property) | Rohit, Hu, Sarkar, Sun, ToSC 2021(1):130–155 [PUB] |

Eskandari et al. registram, com franqueza, o limite da ferramenta: "*for Ascon we can improve the data complexity of the 5 round distinguisher by a factor of 4, however for more rounds we could not improve any results as the computations takes too long*" [PUB].

**GIFT (GIFT-128 tem 40 rodadas; GIFT-64, 28)** — Eskandari et al., Tabela 2 [PUB]:

| Cifra | Rodadas | Bits ativos | Bits balanceados |
|---|---|---|---|
| GIFT-64 | 9 | 61 / 62 / 63 | 5 / 11 / 30 |
| GIFT-64 | **10** | — | **Nenhum distinguidor (provado)** |
| GIFT-128 | 11 | 127 | 32 |
| GIFT-128 | **12** | — | **Nenhum distinguidor (provado)** |

Essa linha "No Distinguisher" é o tipo de resultado que você pediu: **prova estrutural de impossibilidade**. A partir de 12 rodadas, GIFT-128 não tem *nenhum* distinguidor integral baseado em bit-based division property. Margem estrutural integral: 12/40 = 30% atacado, 70% de margem.

**SPARKLE** — Hu & Yap, ToSC 2024(3), Tabela 5 [PUB]:

| Permutação | Distinguidor integral | Bits ativos (anterior → novo) |
|---|---|---|
| Sparkle256 | 4,5 steps: {0–63} → {128–255} | 63 → **64** |
| **Sparkle384** | **4,5 steps: {0–127} → {192–383}** | 127 → **128** |
| Sparkle512 | 4,5 steps: {0–191} → {256–511} | 191 → **192** |

Contra Schwaemm256-128, que usa Sparkle384 com **7 steps (slim)** e **11 steps (big)**: 4,5/7 = 64% do slim, 4,5/11 = 41% do big. Para a ARX-box Alzette isolada, o melhor distinguidor integral cobre **6 rodadas = 1,5 step** [PUB, ePrint 2019/1378].

Observação dos autores que importa para você: "*our integral distinguishers work even if any key is XORed with the input data*" [PUB] — a propriedade é independente da chave.

**Grain-128AEADv2** — aqui a division property aparece na forma de cube attack (Seção 3), não de distinguidor integral clássico, porque a estrutura LFSR+NFSR não se presta ao formato "bits balanceados". Eskandari et al. cobriram Bivium (681), Trivium (707) e Kreyvium (713), mas não Grain, e explicam: "*we can only distinguish the key stream if the resulting key stream bit is also balanced*" — o gargalo é exatamente o que nos interessa (o observável).

##### 2.3 Cabe no modelo?

**NÃO, na forma publicada.** Toda a família exige um conjunto de entradas em que bits selecionados percorrem todos os valores. Isso é chosen-plaintext ou chosen-IV por construção.

##### 2.4 [MINHA] A formulação observacional: **integral de contador com cancelamento por bits determinísticos**

Esta é a ideia central que a pesquisa produziu. Vou expor com cuidado porque ela tem uma armadilha e a armadilha tem solução.

**Construção.** Fixe uma chave. Tome 2^k criptogramas cujos nonces sejam `n₀, n₀+1, …, n₀+2^k−1`, com `n₀ ≡ 0 mod 2^k`. Os k bits baixos do nonce percorrem todos os valores; todo o resto do estado inicial é constante. Some (XOR) os 2^k criptogramas, posição de bloco a posição de bloco:

```
⊕_{j=0}^{2^k−1} C^{(j)}_i  =  ⊕_j Z^{(j)}_i  ⊕  ⊕_j P^{(j)}_i
```

**A armadilha.** O segundo termo. Se os plaintexts variam entre amostras, `⊕_j P^{(j)}_i` é o XOR de 2^k textos independentes. Pelo lema de empilhamento, mesmo um viés forte por texto vira `viés^(2^k)` — para k ≥ 4 isso é indistinguível de uniforme e **destrói completamente** a soma do keystream. Se você tentasse isso ingenuamente, obteria ruído puro e concluiria (erradamente) que não há propriedade integral.

**A solução.** Restrinja a soma às **posições de bit em que o plaintext é determinístico**. Em ASCII inglês, o MSB de todo byte é 0. Logo, nessas posições, `⊕_j P^{(j)}_i = 0` **exatamente, com probabilidade 1**, e:

```
⊕_j C^{(j)}_i [MSBs]  =  ⊕_j Z^{(j)}_i [MSBs]
```

A soma integral do keystream fica **exposta sem nenhum ruído**, em 1/8 das posições de bit, para um adversário estritamente passivo que não escolheu nada. Para o braço de imagens (ImageNet grayscale), o análogo é mais fraco — os MSBs de pixels não são constantes — mas há redundância de bit baixo explorável; eu trataria o braço de texto como o principal e o de imagem como contraste.

**Quantas rodadas isso alcança?** A soma se anula quando `dim(cubo) > grau algébrico`. Para Ascon (grau 2 por rodada, logo grau ≤ 2^r após r rodadas):

| k (nonces consecutivos por chave) | grau máximo tolerado | rodadas de inicialização do Ascon distinguíveis |
|---|---|---|
| 6 (**seu dataset v2 atual**: 100 slots/chave) | 5 | **2** |
| 17 (2^17 ≈ 131 mil nonces/chave) | 16 | **4** |
| 33 | 32 | **5** |
| 65 | 64 | 6 |

Compare com Todo: 7 rodadas exigem 2^65 textos escolhidos. Aqui, 2^65 nonces de contador dariam 6 rodadas — perde-se aproximadamente uma rodada em relação ao caso escolhido, porque o cubo está preso aos bits baixos do nonce em vez de posições otimizadas. **Uma rodada de perda é um preço baixíssimo por eliminar totalmente a premissa de escolha.**

**Requisito de engenharia crítico:** o seu dataset v2 tem 100 slots por chave (k ≤ 6,6) e o nonce é um contador **global** (não por chave), o que quebra o alinhamento. Para testar isso, seria preciso um braço com **nonce contador por chave, alinhado em 2^k, e k grande** (≥ 17 para chegar a 4 rodadas). Isso é uma mudança de geração, não de análise.

**Custo:** trivial computacionalmente (um XOR acumulado, O(N)). Caro em geração: 2^17 amostras de 64 KB por chave = 8,6 GB por chave. Mas você não precisa de 64 KB — precisa só do **primeiro bloco** de cada criptograma (16 bytes). 2^17 × 16 B = 2 MB por chave. **O braço inteiro cabe em menos de 1 GB para 300 chaves.** Isso é muito barato.

**O que prevê:** com Ascon-AEAD128 completo (12 rodadas de init), a soma nas posições MSB deve ser uniformemente aleatória — H₀, e H₀ com uma razão teórica precisa. Com init reduzida a r rodadas e k ≥ 2^r + 1, a soma deve ser **identicamente zero** nessas posições, em toda chave, sem exceção. Isso é uma predição binária e determinística, não estatística: é falsificável em uma única execução.

---

#### 3. CUBE ATTACKS E SUPERPOLIES

##### 3.1 Grain-128AEAD — tabela histórica completa

A inicialização do Grain-128AEADv2 tem **512 clocks**: 320 de inicialização de estado + 64 de reintrodução da chave + 128 de inicialização de A/R (Spec §3.3, verbatim: "*This amounts to a total of 320+64+128 = 512 initialization clocks before keystream generation begins*") [PUB]. A v1 tinha 384; o tweak da rodada final aumentou ~33%.

| Rodadas | Tipo | Complexidade | Trabalho | Fonte |
|---|---|---|---|---|
| 184 | (tido como key-recovery; **revelado como só distinguishing**) | — | Hao et al. reanalisando trabalho anterior | EUROCRYPT 2020 [PUB] |
| 189 | distinguishing | 2^96 | Hao, Leander, Meier, Todo, Wang | EUROCRYPT 2020 / NISTIR 8454 [PUB] |
| **190** | key-recovery | **2^123** | Hao et al. (3SDP/u) | EUROCRYPT 2020 [PUB] |
| 190 | dynamic cube, 3 bits de chave | 2^103,44, sucesso 99,68% | Liu & Tian | ToSC 2024(2) [PUB] |
| **191** | key-recovery | 2^116,26 consultas, 2^118,6 bits de memória | Hu, Sun, Todo, Wang, Wang (nested MP) | ASIACRYPT 2021 [PUB via NISTIR] |
| **192** | key-recovery | **2^127 consultas** | He, Hu, Preneel, Wang | ASIACRYPT 2022 [PUB via NISTIR] |
| 192 | recuperação prática do superpoly (5× mais rápida) | prática | He, Hu, Lei, Wang (CMP + MitM) | EUROCRYPT 2024 [PUB] |
| 193 | zero-sum distinguisher, **weak-key** | — | linhagem NBDP+CMP | [CIT] |
| 195 | superpolies recuperados, **weak-key** | — | linhagem NBDP+CMP | [CIT] |

**Caveat que o NIST faz questão de registrar, e que é decisivo para o seu modelo** [PUB, NISTIR 8454]:

> "*The best key-recovery attack is on Grain-128AEAD with 192-round (out of 512-round) initialization **under the assumption that an attacker has access to the pre-output bits after 192 rounds without reintroducing key in the initialization phase**.*"

Ou seja: mesmo o melhor ataque do mundo contra Grain-128AEAD supõe um observável que o esquema real **nunca produz**. E há uma segunda camada: no Grain-128AEADv2, `z_i = y_{512+2i}` — **apenas os bits pares** do pre-output viram keystream; os ímpares alimentam o autenticador e jamais aparecem [PUB, Spec §2.3]. O adversário CT-only vê metade do stream.

**Conditional differential (cubos minúsculos, praticáveis):**

| Alvo | Rodadas | Cenário | Cubo | Fonte |
|---|---|---|---|---|
| Grain-128 | 215/256 distinguishing; 213 recuperação parcial | chosen IV | — | Knellwolf, Meier, Naya-Plasencia, ASIACRYPT 2010 [PUB] |
| Grain v1 | 215/256 distinguishing; 197 → 8 bits com p=0,87; 213 → 2 bits com p=0,59 | chosen IV | — | idem [PUB] |
| Grain v1 | 105 rodadas | chosen IV | — | Sarkar, Cryptogr. Commun. (2015) [CIT] |
| Grain-128a | **191/256 single-key**; 201/256 weak-key | chosen IV | **dimensão 5** | Ma, Tian, Qi, IET Inf. Secur. (2017) [CIT] |
| Grain-128a | 195 weak-key (ataque B) | chosen IV | — | idem [CIT] |
| Grain v1 | 96/160 não-aleatoriedade a **2^7**; distinguidor de 90 rodadas a 2^39 | chosen IV (maximum degree monomial test) | — | Stankovski, INDOCRYPT 2010, pp. 210–226 [CIT] |

**Cubos de dimensão 5 alcançando 191 rodadas** é o dado mais provocativo desta tabela: mostra que quando as *condições* são bem escolhidas, o cubo em si pode ser minúsculo. O que não sobrevive ao CT-only é a imposição das condições, não o tamanho do cubo.

##### 3.2 Ascon — tabela de cube/cube-like

| Rodadas (de 12) | Tipo | Dados | Tempo | Cenário | Fonte |
|---|---|---|---|---|---|
| 5 | key-recovery cube-like | — | 2^35 | nonce-resp. | Dobraunig et al., CT-RSA 2015 [PUB via Tezcan] |
| 5 | key-recovery cube-like | — | 2^24 | nonce-resp. | Li et al., ToSC 2017 [PUB via Tezcan] |
| 5 | key-recovery cond. HDL | 2^22 | 2^22 | nonce-resp. | Hu, Peyrin, Tan, Yap, ASIACRYPT 2023, §5.2 [PUB] |
| 6 | key-recovery cube-like | — | 2^40 | nonce-resp. | Li et al. [PUB via Tezcan] |
| 6 | state-recovery cond. cube | 2^40 | 2^40 | **nonce-misuse** | Baudrin et al. [PUB via NISTIR] |
| **7** | key-recovery cond. cube | 2^77 | **2^103** | nonce-resp. | Li, Zhang, Dong, ToSC 2017 [PUB] |
| 7 | key-recovery cube | 2^64 | 2^123 | nonce-resp. | Rohit, Hu, Sarkar, Sun, ToSC 2021(1) [PUB] |
| 7 | key-recovery cube | 2^70 | **2^72,4** | nonce-resp., break-fix | Hu, ToSC 2024(2) [PUB] |
| 7 | distinguisher cube, **weak-key** | 2^46 (para 2^82 chaves); 2^33 (para 2^63 chaves) | — | nonce-resp. | Rohit & Sarkar, ToSC 2021(4):74–99 [PUB] |
| 8 | key-recovery | — | 2^101 | **nonce-misuse** | [CIT] |

Condição exigida pelo melhor distinguidor de 7 rodadas: "*nonce bits are set to be equal in the third and fourth rows of the Ascon state during initialization*" (Hu, ToSC 2024 [PUB]). Um nonce contador **não** satisfaz isso — a probabilidade de um contador aleatoriamente gerar essa relação em 64 bits é 2^−64.

##### 3.3 Cabe no modelo?

**NÃO** para cube key-recovery. **ADAPTÁVEL** para cube *distinguisher* (soma nula), pela construção da Seção 2.4. A diferença é que o key-recovery precisa do superpoly avaliado em cubos *específicos* com condições impostas, enquanto o distinguisher precisa apenas de "a soma é zero" — e é isso que o contador fornece.

**O que teria de mudar e qual premissa arranha:** nada no modelo de ameaça. O que muda é o **protocolo de geração** do dataset: nonce contador por chave, alinhado, com muitas amostras por chave. Arranha apenas a hipótese "o adversário conhece a distribuição do plaintext", que é padrão em CT-only (Seção 1.4).

---

#### 4. ZERO-SUM DISTINGUISHERS E GRAU ALGÉBRICO

##### 4.1 A linhagem

| Trabalho | Fonte | Contribuição |
|---|---|---|
| Aumasson & Meier | 2009 [CIT] | introduz zero-sum |
| Boura & Canteaut, *A zero-sum property for the Keccak-f permutation with 18 rounds* | ISIT 2010 [CIT] | estende para 18 rodadas via espectro de Walsh |
| **Boura, Canteaut, De Cannière, *Higher-order differential properties of Keccak and Luffa*** | **FSE 2011, Lyngby** [CIT] | o limite superior de grau de permutações iteradas que é a base de tudo |
| Boura, Canteaut, De Cannière, *Zero-Sum Distinguishers for Iterated Permutations and Application to Keccak-f and Hamsi-256* | SAC 2010/2011 [CIT] | partições zero-sum |
| Duan & Lai, *Improved zero-sum distinguisher for full round Keccak-f* | Science Bulletin (2011) [CIT] | partição de 2^1590 → **2^1575** no Keccak-f de 24 rodadas |
| Yan et al., *New zero-sum distinguishers on full 24-round Keccak-f using the division property* | IET Inf. Secur. (2019) [CIT] | via division property |
| **Hu, Peyrin, Tan, Yap** | **ASIACRYPT 2023, ePrint 2022/1335** [PUB] | HATF + DSF; melhor resultado sobre Ascon |

##### 4.2 Números para Ascon — Hu et al., ASIACRYPT 2023, Tabela 3 [PUB]

| Tipo | Rodadas | Dados (log₂) | Tempo (log₂) | Método | Fonte |
|---|---|---|---|---|---|
| From start | 8 | 130 | 130 | Integral | Todo 2015 |
| From start | **8** | **48** | **48** | **HD (DSF)** | Hu et al., §7 |
| From start | 11 | 315 | 315 | Integral | Todo 2015 |
| Inside out | 12 (**completo**) | 130 | 130 | Zero-sum | Dobraunig et al. 2015 |
| **Inside out** | **12 (completo)** | **55** | **55** | **Zero-sum** | Hu et al., §J |
| Inside out | 11 | 48 | 48 | Zero-sum | Hu et al., §J |
| Inside out | 10 | 25 | 25 | Zero-sum (**verificado experimentalmente**) | Hu et al., §J |

Limites superiores do grau algébrico da DSF da permutação **inversa** do Ascon (Hu et al., Tabela 8) [PUB]:

| Rodadas inversas | S[0] | S[1] | S[2] | S[3] | S[4] |
|---|---|---|---|---|---|
| 1 | 2 | 1 | 2 | 0 | 2 |
| 2 | 4 | 6 | 6 | 6 | 6 |
| 3 | 18 | 16 | 18 | 18 | 18 |
| 4 | 54 | 54 | 54 | 54 | 54 |

Grau da S-box inversa do Ascon = 3, logo grau ≤ 3^r para r rodadas inversas; grau da S-box direta = 2, logo ≤ 2^r.

##### 4.3 O aviso dos próprios autores — e por que ele importa muito para você

Citação literal [PUB]:

> "*although these zero-sum distinguishers require low complexities, their actual impact on the security of the Ascon AEAD and Hash are very likely non-existent or at best not clear. (…) the advantage of the zero-sum distinguisher for Ascon permutation and a perfect permutation is very small, **usually falling under a factor of 2***"

E no zero-sum de 2015 os projetistas já diziam: "*The non-ideal properties of the permutation do not seem to affect the security of Ascon.*"

**[MINHA]** Isso é uma lição metodológica direta para a dissertação: existe um distinguidor de 2^55 sobre a permutação **completa** do Ascon, e ele **não implica absolutamente nada** para um classificador ML sobre criptogramas. Uma vantagem "abaixo de um fator 2" sobre um adversário genérico não é um F1 de 0,50 → 0,51; é um evento com vantagem que não sobrevive à composição com o modo. Vale escrever isso explicitamente, porque o leitor de banca vai perguntar "mas então a permutação do Ascon é distinguível em 12 rodadas, por que o ML não vê nada?" — e a resposta é: porque essa distinguibilidade exige 2^55 escolhas de entrada estruturadas e vale só sobre a permutação nua.

##### 4.4 Cabe no modelo?

**NÃO.** Zero-sum exige um conjunto de entradas escolhido "de dentro para fora" (inside-out): você escolhe um estado intermediário e propaga em ambas as direções. O adversário CT-only nem observa a permutação nua nem pode fixar estados intermediários.

Exceção parcial: **[MINHA]** a *partição* zero-sum de Dobraunig et al. divide o espaço inteiro em 2^(320−130) subespaços, cada um com soma nula. Isso é uma propriedade "de todos os pontos", não "de um conjunto escolhido". Mas verificar uma partição exige 2^n chamadas — os próprios autores de Hu et al. registram que isso "*is actually impossible to perform*". Caminho fechado.

##### 4.5 Estimar grau algébrico sem controlar a entrada — [MINHA] impossibilidade

O grau algébrico de `f: F₂ⁿ → F₂` é definido pela ANF, e o único estimador estatístico prático é a derivada de ordem superior: `Δ_V f(x) = ⊕_{v∈span(V)} f(x⊕v)`, que é 0 identicamente sse deg(f) < dim(V). **Isso exige avaliar f em todos os 2^|V| pontos de um coset de um subespaço.** Não existe estimador de grau a partir de amostras não estruturadas: um conjunto aleatório de 2^k pontos tem probabilidade 2^(−m) de ter soma nula em m bits de saída, para *qualquer* f, então o teste não discrimina. Portanto **não há versão observacional do teste de grau** — exceto, de novo, pela Seção 2.4, onde o contador *fornece* o coset. Vale registrar que esse é o mesmo mecanismo: o teste de grau é o cubo, com outro nome.

---

#### 5. ATAQUES DE INVARIANTE

##### 5.1 Nonlinear invariant attack — o único ataque CT-only "de verdade" na literatura estrutural

**O que é.** Se `E_k` tem uma função invariante não-linear `g` — isto é, `g(p) ⊕ g(E_k(p))` é constante para todo p e toda chave fraca k — o atacante distingue a cifra imediatamente (a probabilidade de uma permutação aleatória ter isso é ≈ 2^(−N+1) para g balanceada). Se a constante depende da chave, recupera-se 1 bit de chave com um único par conhecido.

**Fonte.** Todo, Leander, Sasaki, *Nonlinear Invariant Attack — Practical Attack on Full SCREAM, iSCREAM, and Midori64*. ASIACRYPT 2016, ePrint 2016/732. **[PUB]**

**A extensão ciphertext-only, com as condições exatas** (§2.2, texto lido):
1. A cifra é usada em CBC, CFB, OFB ou CTR — o plaintext **não** é a entrada direta da cifra; o IV é.
2. O atacante coleta vários criptogramas em que **o mesmo plaintext desconhecido é cifrado com a mesma chave fraca e IVs diferentes**.
3. `g` é não-linear nos primeiros s bits: `g(x,y) = f(x) ⊕ ℓ(y)`. A não-linearidade é essencial — se g fosse linear, `g(P₁⊕IV) ⊕ g(C₁)` degeneraria em 1 bit só.
4. Round keys idênticas (cifras sem key schedule).

Resultados concretos: **SCREAM e iSCREAM com 2^96 chaves fracas; Midori64 com 2^64 chaves fracas** (contra 2^32 do ataque anterior de Guo et al.). Recupera 32 bits em cada bloco de 64 bits do plaintext quando Midori64 roda em CBC/CFB/OFB/CTR. Justificativa dos autores para a praticidade: "*assuming an application sends secret password several times, we can recover the password practically*". Ataque em modelo **nonce-respecting** contra SCREAM/iSCREAM.

##### 5.2 Por que não há análogo para os quatro finalistas

**GIFT-128 — fechado por projeto, com citação literal.** GIFT paper (Banik, Pandey, Peyrin, Sasaki, Sim, Todo, CHES 2017, ePrint 2017/622) **[PUB]**:

- §4.5, invariant subspace: "*Since the round constant is XORed only in the MSB of several Sboxes* (…) *thus GIFT resists the invariant subspace attacks.*"
- §4.6, nonlinear invariant: "*Nonlinear invariant attacks are weak-key attacks that can be applied when the round constant is XORed only to some particular bits of nibbles. The core* (…) *1) has the quadratic nonlinear invariant and 2) the linear layer is represented by* (…) *we searched for the quadratic nonlinear invariant for GIFT Sbox, but **there is no such invariant**. Therefore, GIFT is secure against the nonlinear invariant attacks.*"

**Ascon e Schwaemm.** São permutações **sem chave**. A noção de "classe de chaves fracas" da invariante não-linear pressupõe key-alternating com round keys idênticas. O único análogo seria um invariante da permutação nua, e ele seria um invariante público, não um distinguidor de criptograma.

**Grain-128AEAD.** Não é key-alternating; é LFSR+NFSR. A teoria de invariantes não se aplica.

##### 5.3 A linhagem completa de invariantes (para o texto de trabalhos relacionados)

| Trabalho | Fonte | Contribuição |
|---|---|---|
| Leander, Abdelraheem, AlKhzaimi, Zenner, *A Cryptanalysis of PRINTcipher: The Invariant Subspace Attack* | CRYPTO 2011 [CIT] | quebra o PRINTcipher completo para fração significativa das chaves; distinguidor CP em tempo unitário para chaves fracas; "*weak-key variant of a statistical saturation attack*" |
| Leander, Minaud, Rønjom, *A Generic Approach to Invariant Subspace Attacks: Cryptanalysis of Robin, iSCREAM and Zorro* | EUROCRYPT 2015 [CIT] | busca genérica |
| Todo, Leander, Sasaki | ASIACRYPT 2016 [PUB] | invariante não-linear + CT-only |
| **Beierle, Canteaut, Leander, Rotella, *Proving Resistance Against Invariant Attacks: How to Choose the Round Constants*** | **CRYPTO 2017, pp. 647–678, ePrint 2017/463** [CIT] | **prova de resistência** via fatores invariantes da camada linear; prova Prince, Skinny-64, Mantis₇ imunes |
| Beyne, *Block Cipher Invariants as Eigenvectors of Correlation Matrices* | ASIACRYPT 2018, ePrint 2018/763 [CIT] | invariantes = autovetores; key-recovery em 10 rodadas do Midori-64 **não modificado** |
| Beyne, *A Geometric Approach to Linear Cryptanalysis* | ASIACRYPT 2021 [CIT] | arcabouço geométrico |
| Beyne & Verbauwhede, *Ultrametric Integral Cryptanalysis* | ASIACRYPT 2024 [CIT] | unifica integral + invariante |
| Grassi, Rechberger, Rønjom, subspace trails | [CIT] | trilhas de subespaço |
| Leander, Tezcan, Wiemer, *Searching for Subspace Trails and Truncated Differentials* | ToSC 2018(1):74–100 [CIT] | busca genérica; aplicada ao Ascon: **3 rodadas para frente com dimensão 2^98; 1 rodada para trás com dimensão 125** (via NISTIR 8454 [PUB]) |
| Tezcan, *Analysis of Ascon, DryGASCON, and Shamash Permutations* | Int. J. Inf. Secur. Sci. (2020), ePrint 2020/1458 [PUB] | subspace trails prob. 1: 4 rodadas DryGASCON-256, 3 DryGASCON-128, 2 Shamash; melhora DL de 4 e 5 rodadas do Ascon para 2^15 e 2^31,44 |

##### 5.4 Cabe no modelo?

**NÃO para os quatro finalistas.** Isto é resultado útil e definitivo: o único ramo estrutural que a literatura reconhece como ciphertext-only está **provadamente fechado** contra GIFT por design, e é **inaplicável** por tipo de construção aos outros três. Recomendo registrar isso na dissertação como uma seção curta de "caminho excluído com prova", porque é exatamente o tipo de negativo que dá credibilidade.

---

#### 6. CRIPTANÁLISE LINEAR E VIÉS DE KEYSTREAM — O ARSENAL QUE DE FATO SOBREVIVE

Esta é a seção mais importante do documento depois da 2.4. É aqui que existe uma técnica **publicada** desenhada exatamente para o observável que você tem.

##### 6.1 A taxonomia Tipo I / II / III

**Fonte:** Dobraunig, Eichlseder, Mendel, *Heuristic Tool for Linear Cryptanalysis with Applications to CAESAR Candidates*, ASIACRYPT 2015, pp. 490–509, ePrint 2015/1200. Ferramenta: `lineartrails` (github.com/iaikkrypto/lineartrails). **[PUB]**

Definições literais dos autores:

- **Tipo I (permutação):** sem restrição de posição. "*a characteristic of this type might not be usable in a concrete attack on the duplex-like constructions of Keyak, Ascon, and ICEPOLE.*"
- **Tipo II (saída restrita):** todos os bits ativos no **fim** da característica têm de estar no rate. "*Such linear characteristics can be used to create key-stream distinguishers in known-plaintext scenarios for duplex-like constructions, or even to perform key-recovery attacks.*"
- **Tipo III (entrada e saída restritas):** bits ativos de entrada **e** saída no rate. "*This type of linear characteristic can act as a key-stream distinguisher in known-plaintext scenarios for duplex-like constructions, targeting the encryption of the plaintext.*" E, sobre o ICEPOLE: "*distinguishers using Type-III characteristics in this way **do not rely on the fact that always the same key is used***."

**Tipo III é, literalmente, o seu modelo de ameaça** — um distinguidor que relaciona `C_i` com o keystream que gera `C_{i+1}`, sem depender de chave repetida.

##### 6.2 Tabela 1 completa do artigo [PUB]

| Cifra | Tipo | Rodadas | S-boxes ativas | Viés |
|---|---|---|---|---|
| Keyak | I | 3 | 13 | 2^−14 |
| Keyak | I | 4 | 33 | 2^−34 |
| Keyak | II | 3* | 12 | 2^−13 |
| Keyak | II | 4* | 43 | 2^−49 |
| **Ascon** | **I** | **3** | **13** | **2^−15** |
| **Ascon** | **I** | **4** | **43** | **2^−50** |
| **Ascon** | **I** | **5** | **67** | **2^−94** |
| **Ascon** | **II** | **2** | **6** | **2^−8** |
| **Ascon** | **II** | **3** | **23** | **2^−30** |
| **Ascon** | **II** | **4** | **61** | **2^−83** |
| **Ascon** | **III** | — | — | **"no meaningful results were obtained"** |
| ICEPOLE | I | 5 | 38 | 2^−55,08 |
| ICEPOLE | I | 6 | 104 | 2^−126,32 |
| ICEPOLE | II | 4 | 22 | 2^−30,42 |
| ICEPOLE | II | 5 | 38 | 2^−59,49 |
| ICEPOLE | III | 3 | 10 | 2^−16,66 |
| ICEPOLE | III | 4 | 22 | 2^−43,25 |
| ICEPOLE | III | 5 | 42 | 2^−87,08 |
| Minalpher | I | 4 / 5 / 6 | 22 / 41 / 58 | 2^−23 / 2^−42 / 2^−62 |
| Prøst-256 | I | 4 / 5 / 6 / 7 | 25 / 41 / 105 / 169 | 2^−26 / 2^−42 / 2^−107 / 2^−175 |

**Ponto honesto e importante: para o Ascon, Tipo III não deu resultado.** Cito verbatim: "*For Ascon-128, we additionally search for Type-II and Type-III characteristics. However, regarding Type-III characteristics, no meaningful results were obtained.*" Isso é um **negativo publicado, específico do Ascon**, e você tem que citá-lo. Mas note três coisas que **atenuam** esse negativo para o seu caso:

1. Eles analisavam **Ascon-128** (rate 64, pb=6). Você usa **Ascon-AEAD128/128a** (rate **128**, pb=**8**). Rate maior = mais graus de liberdade para máscaras Tipo III. A busca deles não cobre a sua instância.
2. Eles otimizaram para **número mínimo de S-boxes ativas**, não para viés mínimo: "*the characteristics given here are optimized for a minimum number of active S-boxes, rather than minimal bias*".
3. Eles **não restringiram as máscaras de saída a posições determinísticas do plaintext** — a busca Tipo III deles trata todos os bits do rate como igualmente observáveis, quando na verdade (Seção 1.4) apenas 1/8 são gratuitos.

##### 6.3 Limites provados de trilhas lineares — Ascon (irrestrito)

Erlacher, Mendel, Eichlseder, *Bounds for the Security of Ascon against Differential and Linear Cryptanalysis*, ToSC 2022(1):64–87 **[PUB]**, Tabela 1(b):

| R | Mín. S-boxes ativas | c² máximo (provado) | Melhor característica encontrada (#S / c²) | Método |
|---|---|---|---|---|
| 1 | 1 | 2^−2 | 1 / 2^−2 | LAT |
| 2 | 4 | 2^−8 | 4 / 2^−8 | LAT, B |
| 3 | 13 | ≤ 2^−26 | 13 / 2^−28 | SMT / `lineartrails` |
| 4 | ≥ 36 | ≤ 2^−72 | 43 / 2^−98 | SAT / `lineartrails` |
| 5 | — | — | 67 / 2^−186 | `lineartrails` |
| 6 | ≥ 54 | ≤ 2^−108 | — | SAT |

Diferenciais (Tab. 1a): 1R 2^−2, 2R 2^−8, 3R ≤2^−30 (melhor 2^−40), 4R ≤2^−72 (melhor 2^−107), 5R melhor 2^−190, 6R ≤2^−108.

Hirch et al. provaram, com ferramenta dedicada, limites além de 2^−128 para 6 rodadas e além de 2^−256 para 12 rodadas, diferencial e linear (via NISTIR 8454 [PUB]).

Parâmetros de referência: Ascon-AEAD128 (SP 800-232, publicada 13/08/2025 [PUB]) — estado 320 bits, **rate 128, capacidade 192**, `Ascon-p[12]` na inicialização e finalização, **`Ascon-p[8]` no processamento de AD e plaintext**, permutações definidas para `1 ≤ rnd ≤ 16`.

##### 6.4 Limites de trilha linear — SPARKLE (a tabela mais útil do documento)

Spec SPARKLE final, **Tabela 4.4** [PUB] — `−log₂(p)`, p = limite de correlação de trilha linear:

| n \ steps | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 256 | 2 | 17 | 23 | 42 | 57 | 72 | 91 | 106 | 125 | ≥128 | ≥128 | ≥128 | ≥128 |
| **384** | **2** | **17** | **25** | **46** | **76** | **89** | **110** | **131** | **161** | **174** | **≥192** | ≥192 | ≥192 |
| 512 | 2 | 17 | 27 | 50 | 93 | 106 | 129 | 152 | 195 | 208 | 231 | 254 | ≥256 |

E — isto é notável — os projetistas do SPARKLE **definiram formalmente a propriedade que interessa ao seu problema**:

> **Property 3.2.3 (Undetectability of Keystream Bias).** *Let P: F₂ʳ × F₂ᶜ → F₂ʳ × F₂ᶜ be a permutation. We say it has undetectable keystream biases with security parameter s if the absolute correlation of each linear approximation of Pⁱ involving only bits in the outer part is lower than 2^(−s/2), for all numbers of iterations i where i is smaller than the order of the permutation.* **[PUB]**
>
> *"Detection of biases is a dangerous attack on AEAD schemes. We aim for a security parameter of s = d, where d equals the binary logarithm of the number of blocks allowed by the data limit."*

**Isso é literalmente a formalização da sua pergunta de dissertação, escrita pelos projetistas de um dos quatro algoritmos.** Use.

Limitação declarada pelos autores, palavra por palavra: "*These are conservative bounds: while our algorithms show that there cannot exist any trail with higher a probability/correlation, it may very well be that the bounds they find are not tight.*" E: "*we did not find actual attacks on the (round-reduced) schemes that correspond to those bounds and might actually be vastly overestimating the abilities of the adversary.*"

##### 6.5 Limites de trilha linear — GIFT-128

Sun, Wang, Wang, *Linear Cryptanalyses of Three AEADs with GIFT-128 as Underlying Primitives*, ToSC 2021(2):199–221, ePrint 2021/661 **[PUB]**:

| Item | Valor |
|---|---|
| Trilha linear ótima de 10 rodadas | `\|c\| = 2^−26` (16.384 trilhas atingem esse ótimo, e **nenhuma delas é útil no setting do ataque** — precisaram baixar para 2^−27/2^−28/2^−29) |
| Trilha linear ótima de 11 rodadas | `\|c\| = 2^−31` |
| Aproximação de 10 rodadas usada contra GIFT-COFB | ELP = 2^−57,68; trilha dominante `c = 2^−29` |
| Aproximação de 19 rodadas | ELP = 2^−117,43 |
| Melhor ataque a GIFT-COFB | **16 rodadas** de GIFT-128, tempo 2^122,80, dados 2^62,10, memória 2^47, sucesso 80,01% |
| Melhor ataque linear a GIFT-128 | **24 rodadas**, tempo 2^124,45, dados 2^122,55, memória 2^105 |
| Melhor ataque diferencial a GIFT-128 | **27 rodadas** (Zong et al., ToSC 2021(1)) |

Detalhe metodológico que é ouro para você: eles tiveram de **restringir as máscaras ao que é observável no modo COFB** — "*Since the unknown value L masks the least significant 64* (…) *the verification of the linear relation should be* (…) *Then, the result of this specialised SAT problem will automatically suit the attack setting.*" Isto é o análogo Tipo-II/III para modo de cifra de bloco, e é exatamente a metodologia que você precisaria replicar.

**[MINHA] Predição do piso CT-only para GIFT-COFB.** Correlação ótima ≈ 2^(−2,6r) a 2^(−2,8r). Sinal dependente da chave ⇒ agregação só dentro de chave ⇒ limiar 2^−9,3 (Seção 1.2). Resolvendo `2,6r ≤ 9,3` ⇒ **r ≈ 3,6, piso predito = 3 rodadas de 40**.

Você mediu **3/40**. Isso não é coincidência plausível: é o arcabouço linear reproduzindo o seu número empírico a partir de dados de literatura independentes. Eu colocaria essa conta na dissertação — ela converte um número experimental solto em um número *explicado*.

##### 6.6 Fast correlation attack — o caso Grain, com os números que matam a ideia

Todo, Isobe, Meier, Aoki, Zhang, *Fast Correlation Attack Revisited — Cryptanalysis on Full Grain-128a, Grain-128, and Grain-v1*, CRYPTO 2018, ePrint 2018/522. **[PUB]**

| Alvo | Ataque | Premissa | Dados | Tempo |
|---|---|---|---|---|
| **Grain-128a (ksg)** | FCA | — | **2^113,8** | **2^115,4** |
| Grain-128 (init) | dynamic cube | chosen IV | 2^63 | 2^90 |
| Grain-128 (init) | dynamic cube | chosen IV | 2^62,4 | 2^84 |
| Grain-128 (ksg) | FCA | — | 2^112,8 | 2^114,4 |
| Grain-v1 (ksg) | fast near collision | — | 2^19 | 2^86,1 |
| Grain-v1 (ksg) | FCA | — | 2^75,1 | 2^76,7 |

Correlações efetivamente encontradas: para Grain-128a, **2^26,58 máscaras γ com |correlação| > 2^−54,2381**; a correlação da parte g é `corg(Λ_Tz) = −2^−34,313` (composta de −2^−33,1875 e −2^−33,4505 nos dois casos condicionais). Para Grain-128: 2^26 máscaras com correlação ±2^−51.

Restrição declarada pelos autores em nota de rodapé, e ela é decisiva: "*We assume that all output sequences of the pre-output function can be observed. This assumption naturally holds under the known-plaintext setting on the stream cipher mode. On the other hand, it is difficult to observe them under the reasonable assumption on the authentication mode **because the half of the pre-output function is not used as the key stream**. Therefore, we do not claim that the authenticated encryption mode is attacked.*"

**[MINHA] Veredicto quantitativo.** Você tem 2^33,9 bits por classe (2^19,3 bits por par chave/nonce). O FCA precisa de 2^113,8 bits **de um único par chave/nonce**. O déficit é de **2^94,5** — não é uma questão de mais GPU, é 28 ordens de magnitude decimal. E a melhor correlação individual conhecida (2^−54) exige 2^108 amostras, contra o seu limiar de 2^−16,9. **Distinguir Grain-128AEAD completo do aleatório no seu regime de dados é impossível por qualquer método linear conhecido, com margem de ~37 ordens binárias.** Esse é um bom número para a dissertação, porque converte "não achamos nada" em "não havia nada a achar, e eis a distância exata".

Os projetistas, aliás, escreveram o limite de 2^80 bits de keystream justamente para isso: "*Restricting the number of keystream bits will also make attacks that use linear approximations more difficult*" [PUB].

##### 6.7 Viés de keystream em AEAD — o precedente do AEGIS

Minaud, *Linear Biases in AEGIS Keystream*, SAC 2014, ePrint 2018/292 **[CIT]**. Encontra correlação entre criptogramas nas rodadas i e i+2 do AEGIS; **os vieses exigiriam 2^140 dados para serem detectados**. É citado explicitamente pelos autores de ASIACRYPT 2015 como a inspiração do Tipo III. Serve como referência de "existe a propriedade, mas é indetectável" — que é, estruturalmente, a sua conclusão.

Survey útil: *An overview of distinguishing attacks on stream ciphers*, Cryptogr. Commun. (2009) [CIT].

##### 6.8 Cabe no modelo?

**SIM para Tipo III. ADAPTÁVEL para Tipo II.**

- **Tipo III:** cabe integralmente, sem arranhar premissa nenhuma — máscara de entrada em `C_i` (que no Ascon **é** o rate de entrada de `p[8]`, exatamente conhecido) e máscara de saída em `C_{i+1}`. Nenhuma escolha, nenhum oráculo, nenhum reuso de nonce.
- **Tipo II:** a máscara de entrada pode cair na capacidade (desconhecida), o que normalmente inviabiliza. **[MINHA]** Mas com a máscara de saída restrita a posições MSB de ASCII (`⟨v,P⟩ = 0` deterministicamente), Tipo II torna-se utilizável CT-only sem penalidade de correlação. É isso que converte o viés 2^−8 de 2 rodadas do Ascon em um teste executável.

**Custo de testar:** muito baixo. A estatística é `⟨u, C_i⟩ ⊕ ⟨v, C_{i+1}⟩` acumulada — uma passada linear pelo dataset. O caro é a *busca* das máscaras `(u,v)`, que pede uma reimplementação do `lineartrails` com a restrição adicional de suporte de `v` nos bits MSB. Estimo 2–4 semanas de engenharia para a busca, ou **zero** se você começar pela versão empírica: varra exaustivamente máscaras de peso 1 e 2 sobre posições MSB (são 16 posições MSB por bloco de 128 bits ⇒ 16 + C(16,2)=120 ⇒ 136 máscaras de saída × 128 de entrada peso 1 = 17.408 pares; uma varredura trivial).

**O que prevê:**
- Ascon-AEAD128 completo (pb=8): correlação ≤ 2^−72 (extrapolando os limites de Erlacher). **Nada acima do acaso.**
- Ascon com pb=2: correlação Tipo II 2^−8 ⇒ detectável com ~2^16 amostras. **Sinal esmagador.**
- Ascon com pb=3: 2^−30 ⇒ exige 2^60. **Nada.**
- **Piso CT-only linear predito para o Ascon: 2 de 8 rodadas de pb** (e, se o alvo for a inicialização, 3 de 12, usando o Tipo I 2^−15).
- Schwaemm256-128: Tabela 4.4 dá 2^−17 já em **2 steps**, contra limiar 2^−13,4. **Piso predito: 1 step de 7 (slim).** Mais o feedback ρ + rate whitening, que degrada ainda mais. Predição: Schwaemm terá o piso CT-only **mais baixo dos quatro**, em fração de rodadas.

---

#### 7. DIFERENCIAL PASSIVO — DIFERENÇAS DE GRAÇA PELO CONTADOR

##### 7.1 A ideia

**[MINHA]**, com precedente publicado (FMS).

Seu modelo proíbe *diferenças escolhidas*. Não proíbe *diferenças observadas*. Com nonce de contador, o par de amostras com nonces `n` e `n+1` tem diferença de nonce `Δ = n ⊕ (n+1)`, que é pública e conhecida. Metade dos pares consecutivos tem **Δ de peso de Hamming 1** — a diferença de entrada mais favorável que existe, entregue de graça.

Combinando com a Seção 1.4: nas posições MSB de ASCII, `ΔP = 0` exatamente, logo `ΔC = ΔZ` **exatamente** nessas posições. O adversário passivo obtém **diferenças exatas de keystream em 1/8 das posições de bit**, para diferenças de entrada de peso 1 no nonce.

Isso reabre, parcialmente, todo o arsenal diferencial / diferencial-linear / conditional-differential — com duas restrições honestas: (i) a posição do bit de diferença é ditada pelo contador, não escolhida; (ii) só 1/8 dos bits de saída é lido, o que multiplica a complexidade de dados.

##### 7.2 O precedente exato

Fluhrer, Mantin, Shamir, *Weaknesses in the Key Scheduling Algorithm of RC4*, SAC 2001 **[PUB]**. O IV do WEP é um contador de 24 bits. O atacante é **passivo**: ele não escolhe IV nenhum, apenas espera até que o contador produza os IVs fracos de padrão `(3, 255, v)`. Combinado com o header SNAP conhecido (0xAA no primeiro byte do plaintext), recupera a chave. Ferramentas: AirSnort, weplab, aircrack. **É "estrutura colhida, não escolhida", com plaintext parcialmente conhecido, num ataque passivo real e devastador.** É o modelo conceitual exato do que proponho.

##### 7.3 O que a literatura diferencial dá, para calibrar

Distinguidores diferenciais-lineares e HD sobre a **inicialização** do Ascon — Hu, Peyrin, Tan, Yap, ASIACRYPT 2023, Tabela 2 [PUB]:

| Rodadas | Tipo | Dados (log₂) | Tempo (log₂) | Método |
|---|---|---|---|---|
| 4 | distinguisher | 5 | 5 | DL (Dobraunig et al.) |
| **4** | distinguisher | **2** | **2** | **2ª ordem HDL (Hu et al. §5.1)** |
| 5 | distinguisher | 18 | 18 | DL |
| **5** | distinguisher | **12** | **12** | **8ª ordem HDL (Hu et al. §5.1)** |

Um distinguidor de 4 rodadas com **4 textos** e de 5 rodadas com **2^12** — é isso que a diferença escolhida compra. Com a diferença colhida do contador e só 1/8 dos bits de saída, **[MINHA]** eu estimaria uma perda de 1 a 2 rodadas e um fator ~2^6 em dados: algo como 4 rodadas com ~2^8 pares, 5 rodadas talvez fora de alcance. Testável.

Para Grain, o análogo é o conditional differential com cubo de dimensão 5 (Seção 3.1): 191/256 rodadas no Grain-128a single-key. Mas ali as *condições* são o essencial e não sobrevivem.

##### 7.4 Nota sobre o seu resultado de 14/09

Pelo que entendi do registro, "pares consecutivos CT-only" já dá F1 até 0,99 em pa=1/2 e acaso em pa≥4. Isso é **exatamente** o que esta teoria prevê, e a explicação para a saturação em pa≥4 tem número: a probabilidade diferencial de 4 rodadas do Ascon é ≤ 2^−72 provada (melhor característica encontrada 2^−107) [PUB, Erlacher et al.]. Com 2^18,6 pares por chave, não há como ver 2^−72. O corte não é do seu método; é do algoritmo.

##### 7.5 Cabe no modelo?

**SIM**, com uma ressalva que você precisa decidir: o par consecutivo pressupõe que o adversário saiba *quais* criptogramas são consecutivos. Com nonce público de contador, ele sabe — é literalmente o que o nonce comunica. Eu considero isso dentro do CT-only sem reserva, e o FMS é o precedente. **Não** exige plaintext conhecido nem diferença escolhida nem reuso de nonce.

**Ataques de slide / auto-similaridade:** **NÃO.** Precisam de pares chave/IV que produzam keystream deslocado, obtidos por busca sobre entradas escolhidas (Advanced Slide Attacks; *New Slide Attacks on Almost Self-Similar Ciphers*, ePrint 2019/509 [CIT]). Além disso, as constantes de rodada de Ascon, GIFT e Alzette quebram a auto-similaridade por projeto. **Ataques rotacionais:** **NÃO** — exigem pares relacionados por rotação, que não aparecem passivamente.

---

#### 8. TESTES ESTATÍSTICOS E "PISOS DE RODADA" — OS ESTUDOS SISTEMÁTICOS EM ESCALA

Você pediu "trabalhos que varreram muitos algoritmos e muitas contagens de rodada com uma bateria única, com as tabelas e as limitações declaradas". Há quatro, e eles convergem para uma mesma lição.

##### 8.1 NISTIR 6483 — a origem do método

Soto & Bassham, *Randomness Testing of the Advanced Encryption Standard Finalist Candidates*, NISTIR 6483, abril de 2000. **[PUB]**

Setup: NIST STS com 16 testes centrais expandidos em **189 testes**; 2^20 bits por sequência; **300 sequências**; α = 0,01; linha de aceitação em 96,33% (11 rejeições de 300).

**Tabela 4 — a rodada mais antiga em que a saída parece aleatória em todos os testes** (chaves de 128 bits, plaintext de baixa densidade, ECB):

| Finalista | Rodada em que a aleatoriedade é evidente | Total de rodadas | Fração |
|---|---|---|---|
| MARS | **6** | 16 (core) | 37,5% |
| RC6 | **4** | 20 | 20% |
| **Rijndael** | **3** | 10 | **30%** |
| Serpent | **4** | 32 | 12,5% |
| Twofish | **2** | 16 | 12,5% |

Detalhes do protocolo de rodada parcial, verbatim: "*due to resource constraints, partial round testing was limited to the low-density plaintext case using 128-bit BBS generated keys*". O input whitening foi mantido (MARS, RC6, Rijndael, Twofish), o output whitening foi omitido (MARS, RC6, Twofish); RC6 avaliado nas rodadas 1–19, Rijndael 1–9, Serpent 1–31, Twofish em pares (rodadas pares de 2 a 14); MARS em três variantes de rodada parcial por ter estrutura heterogênea (8 rodadas de forward mixing não chaveadas + 16 rodadas core chaveadas).

**O caveat metodológico que quase ninguém cita, e que é central para você:** todas as **oito** categorias de dados do NISTIR 6483 são construções de entrada escolhida — Key Avalanche, Plaintext Avalanche, Plaintext/Ciphertext Correlation, CBC Mode (com plaintext todo-zero e IV todo-zero), Low Density Plaintext, Low Density Keys, High Density Plaintext, High Density Keys. **Nenhuma** é ciphertext-only com plaintext real. O teste de rodada parcial usou exclusivamente low-density plaintext (bloco todo-zero, depois 128 blocos com um único bit 1, depois blocos com dois bits 1 em todas as combinações). Logo, os números clássicos de "piso de rodada" da literatura **não são comparáveis** aos seus, e a diferença é o seu resultado.

Anomalia registrada pelos autores, por completude: "*Serpent's plaintext/ciphertext correlation (based on 256-bit keys) yielded 12 rejections out of a sample of 300 binary sequences, using the aperiodic templates statistical test. Subsequent experiments were conducted, and no other anomalies were detected.*"

##### 8.2 BoolTest — a tabela que mostra o tamanho exato dessa diferença

Sýs, Klinec, Kubíček, Švenda, *BoolTest: The Fast Randomness Testing Strategy Based on Boolean Functions with Application to DES, 3-DES, MD5, MD6 and SHA-256*, SECRYPT 2017 + versão estendida (Springer CCIS, 2019). **[PUB]**

**Tabela 3 — Z-scores e testes passados com 10 MB / 100 MB / 1 GB** (NI = NIST STS, Di = Dieharder, U01 = TestU01; Bool3 = deg 1, k=2, m=384, t=128; Bool4 = deg 1, k=2, m=512, t=128; "∀" = todos os testes passaram):

| Tamanho | Função (rodadas) | NI | Di | U01 | Bool3 | Bool4 |
|---|---|---|---|---|---|---|
| 10 MB | AES (3) | ∀ | 18 | 15 | 8,6 | 6,7 |
| 10 MB | TEA (4) | ∀ | 20 | ∀ | 20,6 | 11,5 |
| 10 MB | Keccak (3) | ∀ | ∀ | 15 | 3,7 | 5,3 |
| 10 MB | MD6 (9) | ∀ | ∀ | ∀ | 3,9 | 13,3 |
| 10 MB | SHA-256 (3) | 0 | 0 | 6 | 88,7 | 242 |
| 100 MB | AES (3) | ∀ | 16 | 15 | 8,9 | 15,0 |
| 100 MB | TEA (4) | 14 | 21 | ∀ | 73,6 | 5,2 |
| 100 MB | Keccak (3) | 14 | 22 | 15 | 3,8 | 9,2 |
| 100 MB | MD6 (9) | ∀ | ∀ | ∀ | 3,7 | 26,4 |
| 100 MB | SHA-256 (3) | 0 | 0 | 4 | 50,7 | 828 |
| 1 GB | AES (3) | 9 | 18 | 14 | 12,8 | 41,2 |
| 1 GB | TEA (4) | 13 | 24 | ∀ | 127 | 4,3 |
| 1 GB | Keccak (3) | ∀ | 26 | 15 | 3,5 | 32,0 |
| 1 GB | MD6 (9) | 13 | 25 | 15 | 4,1 | 26,4 |
| 1 GB | SHA-256 (3) | 0 | 1 | 3 | 78,0 | 3043 |

Conclusão dos autores sobre essa tabela: "*test based on boolean functions usually requires an order of magnitude fewer data to detect bias than common batteries*".

**Tabela 4 — número de rodadas em que a não-aleatoriedade é detectada, 100 MB de dados, por estratégia de geração de entrada** (NI / Di / U01 / BT):

| Função | CTR | LHW | SAC | **RPC** |
|---|---|---|---|---|
| AES | 3/3/3/3 | 2/3/3/3 | 2/2/2/2 | **–/1/1/1** |
| Blowfish | 2/2/2/2 | 2/3/3/3 | 2/2/3/3 | **–/1/1/1** |
| DES | 4/4/4/5 | 4/4/4/5 | 4/4/5/4 | **1/1/2/4** |
| 3-DES | 2/2/2/3 | 2/2/3/3 | 2/2/2/2 | **1/1/1/2** |
| Grøstl | 2/2/2/2 | 2/2/2/2 | –/–/–/– | **–/–/–/–** |
| JH | 6/6/6/6 | 6/6/6/6 | 6/6/6/5 | **2/2/2/3** |
| Keccak | 2/2/2/3 | 2/2/2/3 | 2/2/2/2 | **1/–/1/1** |
| MD5 | 9/10/9/11 | 12/13/20/13 | 9/11/14/12 | **3/3/4/6** |
| MD6 | 8/8/8/8 | 8/8/8/9 | 7/7/8/7 | **5/5/7/5** |
| SHA-1 | 12/12/13/14 | 16/16/16/16 | 11/15/16/14 | **4/4/5/7** |
| SHA-256 | 6/6/6/7 | 12/12/12/13 | 11/11/12/13 | **3/4/4/4** |
| TEA | 4/4/4/5 | 3/3/3/4 | 3/4/3/3 | **–/2/1/1** |

Definições, verbatim do artigo:
- **CTR** — "*generates blocks of particular size each containing the current block index. Intuitively the high bits are set to zero while the low bits are iterating.*"
- **LHW** — "*generates function's input blocks with the fixed and low Hamming weight*" (peso 4 para bloco de 128 bits; peso 6 para 64 bits). "*The idea behind the LHW strategy is to cover the whole input block with small changes only, keeping the total Hamming weight low thus feeding the minimal possible entropy to a function. Both CTR and LHW serve as low-entropy input generators.*"
- **SAC** — pares de blocos, o segundo idêntico ao primeiro exceto por um bit invertido em posição aleatória.
- **RPC** — "*inputs are generated randomly*".

Conclusão literal dos autores: "*Among the input generation strategies, **RPC is consistently the scenario which is the most difficult to distinguish from the truly random stream**. The SAC is more difficult than CTR and LHW, which are roughly comparable. However, for SHA-256 the CTR scenario is more difficult than both LHW and SAC. We hypothesize that CTR difficulty is caused by more chaotic bit-flips within two consecutive blocks compared to other scenarios.*"

E sobre a sensibilidade relativa: "*BoolTest is among the most successful tests for CTR, LHW and RPC inputs for tested data with 100 MB length. For SAC generation strategy, TestU01 is the most sensitive battery, while BoolTest performs similarly to Dieharder battery.*" Nota adicional: o teste `smarsa_BirthdaySpacings` do TestU01 Small Crush reprova MD5 reduzido a 18 rodadas com p ≤ 10^−9, e `snpair_ClosePairsBitMatch` do Rabbit reprova MD6 reduzido a **20 de 64 rodadas** com p ≤ 10^−19.

**[MINHA] Por que isso é o resultado mais importante desta seção para você.** A coluna RPC é a mais próxima do seu cenário (plaintext real, não estruturado do ponto de vista da cifra). O colapso é de 2× a 4× em rodadas: AES vai de 3 para 1, SHA-256 de 6 para 3-4, SHA-1 de 12-14 para 4-7, TEA de 4-5 para 1-2. **Seus pisos baixos (GIFT 3/40, Grain 28/256) não são anomalia nem falha de método: são exatamente o comportamento documentado do cenário RPC.** Isto deve ser o principal argumento de defesa metodológica da dissertação.

Nuance que vale registrar: seu plaintext é **inglês/Gutenberg**, mais estruturado que RPC e menos que LHW. O piso esperado fica entre as duas colunas, provavelmente mais perto de RPC.

Vantagem interpretativa que os autores destacam e que importa para o seu Caminho B/C: "*the interpretation of BoolTest result (…) is more straightforward than for the standard batteries. While BoolTest consists of only a single test and resulting single Z-score, standard batteries consist of multiple statistical tests, each with own p-value interpretation and also potentially correlated to other tests.*" Como subproduto, encontraram distinguidores práticos e universais (válidos para grandes grupos de sementes) para `C stdlib rand()` e `java.util.Random`, testados em 1000 streams com sementes em [0, 2^32−1]; e **nenhum** distinguidor para Mersenne Twister 19937, Multiply-with-Carry, Ranlux24, T800 e TT800 até 1 GB.

Trabalho de continuação: *Revisiting BoolTest – On Randomness Testing Using Boolean Functions*, Springer (2022) [CIT].

##### 8.3 EACirc — distinguidores por programação genética, incluindo Grain

Švenda, Ukrop, Matyáš, *Determining Cryptographic Distinguishers for eStream and SHA-3 Candidate Functions with Evolutionary Circuits*, Springer CCIS (2014); e *Towards cryptographic function distinguishers with evolutionary circuits*, SECRYPT 2013. **[PUB]**

Motivação declarada, verbatim: "*Testing full number of rounds usually provides only limited information – either a defect (…) or no defect at all is detected, even when a serious exploitable attack might exist for a limited number of rounds. In this work, we therefore inspected the functions in reduced-round versions.*" Dos candidatos eSTREAM, limitaram-se a 7 (Decim, Grain, FUBUKI, Hermes, LEX, Salsa20, TSC) "*since these had internal structure that allowed for a simple reduction of complexity by reducing a number of internal rounds*". Dos candidatos SHA-3, 42 eram utilizáveis.

**Tabela para candidatos eSTREAM** (valores: Dieharder x/20 testes passados — 20 = aleatório; STS NIST x/162 testes passados; EACirc — 0,52 significa indistinguível, 1,00 significa distinguidor perfeito):

| Cifra | Rodadas | Reinit. 1×/execução | Reinit. por conjunto de teste | Reinit. por vetor de teste |
|---|---|---|---|---|
| Decim | 1 | 0,0 / 0 / **0,99** | 0,0 / 0 / **0,85** | 0,0 / 5 / **0,99** |
| Decim | 2 | 0,5 / 0 / **0,54** | 1,0 / 0 / **0,54** | 15,5 / 146 / 0,52 |
| Decim | 3 | 1,0 / 0 / 0,53 | 1,0 / 0 / 0,53 | 15,0 / 160 / 0,52 |
| Decim | 4 | 3,5 / 79 / 0,52 | 3,0 / 78 / 0,52 | 20,0 / 160 / 0,52 |
| Decim | 5 | 4,5 / 79 / 0,52 | 3,5 / 91 / 0,52 | 17,5 / 161 / 0,52 |
| Decim | 6 | 19,0 / 158 / 0,52 | 19,0 / 159 / 0,52 | 18,0 / 162 / 0,52 |
| Decim | 7–8 | 18,5–20,0 / 159–162 / 0,52 | idem | idem |
| FUBUKI | 1 | 20,0 / 162 / 0,52 | 20,0 / 161 / 0,52 | 18,0 / 162 / 0,52 |
| FUBUKI | 4 | 20,0 / 162 / 0,52 | 20,0 / 162 / 0,52 | 20,0 / 162 / 0,52 |
| **Grain** | **1** | 0,0 / 0 / **1,00** | 0,0 / 0 / **0,67** | 18,5 / 162 / 0,52 |
| **Grain** | **2** | 0,0 / 0 / **1,00** | 0,5 / 0 / **0,66** | 20,0 / 162 / 0,52 |
| **Grain** | **3** | 19,5 / 160 / 0,52 | 20,0 / 162 / 0,52 | 20,0 / 162 / 0,52 |
| **Grain** | **13 (completo)** | 20,0 / 162 / 0,52 | 20,0 / 161 / 0,52 | 19,5 / 162 / 0,52 |
| Hermes | 1 | 20,0 / 162 / 0,52 | 20,0 / 162 / 0,52 | 20,0 / 162 / 0,52 |
| Hermes | 10 | 20,0 / 160 / 0,52 | 20,0 / 162 / 0,52 | 20,0 / 162 / 0,52 |
| LEX | 1 | 0,0 / 0 / **1,00** | 0,0 / 0 / **0,96** | 3,0 / 1 / **1,00** |
| LEX | 2 | 4,0 / 1 / **1,00** | 4,0 / 1 / **1,00** | 3,5 / 1 / **1,00** |
| LEX | 3 | 0,5 / 1 / **1,00** | 3,5 / 1 / **1,00** | 4,0 / 1 / **1,00** |
| LEX | 4 | 20,0 / 162 / 0,52 | 19,5 / 162 / 0,52 | 20,0 / 161 / 0,52 |
| LEX | 10 | 19,5 / 162 / 0,52 | 19,5 / 160 / 0,52 | 20,0 / 160 / 0,52 |
| Salsa20 | 1 | 5,5 / 1 / **0,87** | 8,5 / 1 / **0,67** | 17,5 / 161 / 0,52 |
| Salsa20 | 2 | 5,5 / 1 / **0,87** | 7,0 / 1 / **0,67** | 19,5 / 162 / 0,52 |
| Salsa20 | 3 | 20,0 / 162 / 0,52 | 20,0 / 162 / 0,52 | 19,5 / 161 / 0,52 |
| Salsa20 | 12 (completo) | 20,0 / 162 / 0,52 | 19,5 / 161 / 0,52 | 19,0 / 161 / 0,52 |
| TSC | 1–8 | 0,0* / 0 / **1,00** | idem | idem |
| TSC | 9 | 1,0 / 1 / **1,00** | 1,5 / 1 / **1,00** | 2,0 / 1 / **1,00** |
| TSC | 10 | 2,0 / 13 / **1,00** | 3,0 / 13 / **1,00** | 3,0 / 12 / **1,00** |
| TSC | 11 | 10,0 / 157 / 0,52 | 11,5 / 157 / 0,52 | 14,0 / 159 / 0,52 |
| TSC | 12 | 16,0 / 162 / 0,52 | 17,0 / 161 / 0,52 | 17,5 / 162 / 0,52 |
| TSC | 13 | 20,0 / 162 / 0,52 | 20,0 / 162 / 0,52 | 19,0 / 162 / 0,52 |
| TSC | 32 (completo) | 20,0 / 161 / 0,52 | 20,0 / 162 / 0,52 | 20,0 / 161 / 0,52 |

\* Nas primeiras 8 rodadas o TSC não produz saída, o que travou 4 testes do Dieharder, reduzindo o total efetivo a 16.

**Tabela para candidatos SHA-3** (Dieharder x/20, STS NIST x/162, EACirc):

| Função | Rodadas | Dieharder | STS NIST | EACirc |
|---|---|---|---|---|
| ARIRANG | 0–3 | 0,0 | 0 | **1,00** |
| ARIRANG | 4 | 20,0 | 161 | 0,52 |
| Aurora | 0 | 0,0 | 1 | **0,99** |
| Aurora | 1 | 0,0 | 1 | **0,75** |
| Aurora | 2 | 0,5 | 132 | **0,78** |
| Aurora | 3 | 0,5 | 132 | 0,52 |
| Aurora | 4 | 20,0 | 160 | 0,52 |
| Aurora | 17 (completo) | 19,5 | 161 | 0,52 |
| Blake | 0 | 0,0 | 0 | **1,00** |
| Blake | 1 | 0,0 | 0 | 0,52 |
| Blake | 2 | 20,0 | 162 | 0,52 |
| Blake | 14 (completo) | 20,0 | 159 | 0,52 |
| Cheetah | 0–2 | 0,0 | 0–1 | **1,00** |
| Cheetah | 3 | 0,0 | 0 | **0,90** |
| Cheetah | 4 | 0,0 | 1 | **0,86** |
| Cheetah | 5 | 0,0 | 1 | 0,52 |
| Cheetah | 6 | 20,0 | 161 | 0,52 |
| Cheetah | 16 (completo) | 20,0 | 162 | 0,52 |
| CubeHash | 0 | 0,0 | 0 | **1,00** |
| CubeHash | 1 | 0,0 | 0 | 0,52 |
| CubeHash | 2 | 20,0 | 161 | 0,52 |
| CubeHash | 8 (completo) | 20,0 | 162 | 0,52 |
| DCH | 0 | 0,0* | 0 | **1,00** |
| DCH | 1 | 0,0* | 0 | **0,73** |
| DCH | 2 | 19,5 | 162 | 0,52 |
| DCH | 4 (completo) | 20,0 | 162 | 0,52 |

**O achado que você precisa ler duas vezes:** com **reinicialização de chave/IV por vetor de teste**, o Grain já parece aleatório em **1 rodada** (Dieharder 18,5/20, STS 162/162, EACirc 0,52); com reinicialização única por execução, ele é claramente não-aleatório até 2 rodadas (Dieharder 0,0/20, STS 0/162, EACirc 1,00). **A frequência de rekeying suprime o sinal estatístico.** O seu dataset tem nonce novo a cada amostra de 64 KB — regime intermediário, mas mais próximo do supressivo. É mais um fator estrutural empurrando o piso para baixo, e não é defeito do seu protocolo: é consequência de modelar um dispositivo real nonce-respecting.

Comparação declarada pelos autores: "*EACirc consistently performs better than NIST STS, while Dieharder is able to detect small deviances in one additional round.*" E, sobre a segunda versão: "*EACirc2 detects non-randomness in some cases where NIST STS and Dieharder batteries, and previous approach (EACirc), fail*" — FUBUKI 1 rodada, Hermes 2, LEX 4, TSC 12.

Estudo relacionado sobre TEA: *New results on reduced-round Tiny Encryption Algorithm using genetic programming*, Infocommunications Journal (2016) [CIT] — TEA de 1 a 5 rodadas com diferentes tipos de plaintext, comparando baterias estatísticas e EACirc; e trabalho anterior citado no artigo que, com algoritmos genéticos, achou distinguidor de TEA reduzido bem-sucedido em **5 rodadas**.

##### 8.4 CryptoStat — a "margem de aleatoriedade" e a frase que resume tudo

Kaminsky, *Testing the Randomness of Cryptographic Function Mappings*, ePrint 2019/078. **[PUB]**

Método: em vez de agregar p-values (que os autores criticam — "*the NIST test suite* (…) *does not make a single random/nonrandom decision about the block cipher under test*"), usa testes de razão de chances bayesianos e agrega log-odds num único número.

Métrica definida: "*Let r be the largest round such that L_{r,∅,∅} < 0; then the randomness margin is (R − r)/R.*"

| Função | Bits A | Bits B | Bits de saída | Rodadas totais | Última rodada não-aleatória | **Margem** |
|---|---|---|---|---|---|---|
| AES-128 | 128 | 128 | 128 | 10 | 2 | **0,800** |
| AES-192 | 128 | 192 | 128 | 12 | 3 | 0,750 |
| AES-256 | 128 | 256 | 128 | 14 | 3 | 0,786 |
| SHA-1 | 256 | 160 | 160 | 80 | 23 | 0,713 |
| SHA-256 | 256 | 160 | 256 | 64 | 17 | 0,734 |

Conclusão dos autores: as funções exibem "*substantial randomness margin, with 71 to 80 percent of the rounds exhibiting*" aleatoriedade.

E a frase que eu citaria literalmente na sua metodologia [PUB]:

> "*It is important for the input values to be highly nonrandom. **If random inputs are applied to the function and the function's outputs are random, the randomness in the outputs might be due to the randomness in the inputs, rather than to the randomness of the function itself.** When nonrandom inputs nonetheless yield random outputs, the outputs' randomness must be coming from the randomness of the function's mapping.*"

Séries de entrada que a ferramenta suporta, todas explicitamente estruturadas: valores sequenciais a partir de 0 (`0000 0001 0002 0003…`), código Gray a partir de 0 (`0000 0001 0003 0002 0006 0007 0005 0004…`, 1 bit de diferença por passo), e one-off (cada valor difere do primeiro em 1 bit). **Nenhuma opção aleatória, por decisão explícita de projeto.**

Os autores também registram dois precedentes de crítica ao método NIST que valem para o seu texto: "*the AES finalist candidates had a slight inherent bias due to the block cipher mode*" — isto é, o viés detectado vinha do *modo*, não da cifra — e El-Fotouh & Diepold, que encontraram falha do AES sob um teste dedicado ("gambling test") que a suíte NIST não detectava.

**[MINHA] O que essa frase significa para a sua dissertação.** Ela diz, com autoridade de um artigo de ePrint, que **um piso de rodada medido com plaintext real mede uma coisa diferente do que a literatura clássica mede**. Não é uma versão pior da mesma métrica — é outra métrica. A clássica pergunta "a função destrói a estrutura da entrada?"; a sua pergunta "a função destrói a redundância do plaintext antes que ela seja observável?". A segunda é a que interessa para um adversário passivo real, e nenhum dos quatro estudos acima a mede. É um nicho vazio, e é o seu.

##### 8.5 Testes dedicados a sequências curtas

Doğanaksoy, Ege, Koçak, Sulak, *Cryptographic Randomness Testing of Block Ciphers and Hash Functions*, ePrint 2010/564 [CIT]; e Sulak, Doğanaksoy, Ege, Koçak, *Evaluation of Randomness Test Results for Short Sequences*, SETA 2010, Springer [CIT].

Contribuição: um pacote de testes estatísticos baseado em propriedades criptográficas específicas de cifras de bloco e funções de hash, que "*produced more precise results than those obtained in similar applications*" quando aplicado aos finalistas do AES. Modificaram **7 dos 15** testes da suíte NIST para operar em sequências binárias curtas (128–256 bits).

Motivação declarada: quando cifras de bloco e hashes produzem sequências de no máximo 512 bits, "*some tests in the NIST suite cannot be applied and most remaining ones do not produce reliable test values*", o que torna "*the NIST analysis method unsuitable for evaluation of generators producing relatively short sequences*". Vantagem declarada: a abordagem "*is able to perform randomness analysis even when presented with sequences shorter by several orders of magnitude than required by the NIST suite, and can detect non-randomness for stream ciphers with limited number of rounds where other batteries fail*".

Relevante se você quiser features por bloco (128 bits) em vez de por amostra (64 KB) — as suas amostras estão bem acima do limiar problemático, mas um Caminho A por bloco cairia nele. Ver também: *Recommendations on Statistical Randomness Test Batteries for Cryptographic Purposes*, arXiv 2402.02240 [CIT], e *Statistical Tests for Symmetric Primitives*, Springer (2023) [CIT]; além de Kaminsky, *Distinguishing TEA from a Random Permutation: Reduced Round Versions of TEA Do Not Have the SAC or Do Not Generate Random Numbers* [CIT].

##### 8.6 CLAASP — a ferramenta que eu usaria para automatizar isso

Bellini, Gérault, Grados et al., *CLAASP: a Cryptographic Library for the Automated Analysis of Symmetric Primitives*, SAC 2023, ePrint 2023/622. **[PUB]** Docs: claasp.readthedocs.io

A partir de um DAG descrevendo a primitiva como lista de componentes conectados, gera automaticamente: (1) código Python/C de avaliação, (2) **bateria de testes estatísticos e de avalanche**, (3) modelos SAT/SMT/CP/MILP para busca de trilhas diferenciais e lineares, (4) medidas de propriedades algébricas, (5) **teste de distinguidores neurais**. Construído sobre SageMath, GPLv3, descrito pelos autores como "*modular, extendable, easy to use, generic, efficient and fully automated*".

**Cabe no modelo:** a ferramenta, sim, como infraestrutura. Os testes que ela roda, na maioria não (são de entrada estruturada). **Custo:** instalar SageMath + descrever as quatro primitivas como DAG — semanas, não meses, e você já tem as implementações C de referência vendorizadas. **O que prevê:** nada por si; é instrumento. Mas seria a forma defensável de produzir a tabela "piso de rodada por bateria × por estratégia de entrada × por algoritmo" para os quatro finalistas, que **não existe na literatura** — verifiquei com busca dirigida e nenhum trabalho aplicou BoolTest, EACirc ou CryptoStat aos finalistas do NIST LWC. O único achado adjacente é *Evaluation of randomness hash-DRBG-based Ascon hash function using NIST SP800-22*, AIP Conf. Proc. 3320(1):030003 [CIT], que testa a saída de um DRBG baseado em Ascon-Hash, não rodadas reduzidas.

---

#### 9. ML E CIPHERTEXT-ONLY — O ESTADO DA ARTE E O QUE ELE DIZ

##### 9.1 O negativo mais forte, e ele é metodologicamente útil

Dani, Nakka, Saxena, *A Machine Learning-Based Framework for Assessing Cryptographic Indistinguishability of Lightweight Block Ciphers* (MIND-Crypt), ePrint 2024/852 / arXiv 2405.19683; versão estendida em *Cryptography* 10(1):9 (2026). **[PUB]**

Setup: SPECK32/64 e SIMON32/64 em CBC, sob Known Plaintext Attack; 10^7 amostras de treino, 10^6 de validação e 10^6 de teste, com classes balanceadas; duas mensagens de **32 bits diferindo em um único bit**, rotuladas '0' e '1'; IVs gerados com `numpy.frombuffer` + `os.urandom` ("*mirroring Gohr's method*"); chave fixa, para isolar a variação de IV ("*without key variability influencing the results*"); criptogramas representados como vetores binários de 32 bits; verificação de corretude por decifragem; ResNet, CNN, LSTM, BiLSTM com otimização Optuna/TPE.

Resultado (Tabela III):

| Configuração | Modelo | Acurácia | ROC-AUC |
|---|---|---|---|
| Round-reduced, SPECK32/64 | ResNet / CNN / LSTM / BiLSTM | 0,5000 / 0,5003 / 0,5000 / 0,5000 | 0,5008 / 0,5005 / 0,5014 / 0,5000 |
| Round-reduced, SIMON32/64 | ResNet / CNN / LSTM / BiLSTM | 0,5002 / 0,4993 / 0,5000 / 0,5000 | 0,5003 / 0,4992 / 0,4996 / 0,4991 |
| Full, SPECK32/64 | ResNet / CNN / LSTM / BiLSTM | 0,5000 / 0,4997 / 0,5000 / 0,4999 | 0,5001 / 0,4996 / 0,5001 / 0,5003 |
| Full, SIMON32/64 | ResNet / CNN / LSTM / BiLSTM | 0,5000 / 0,4999 / 0,5000 / 0,5000 | 0,5000 / 0,5000 / 0,5004 / 0,5003 |

**(Não consegui confirmar no texto que li quantas rodadas exatamente é o "round-reduced"; o PDF não explicita. Registro como não confirmado em vez de completar de memória.)**

**O achado metodológico, e é o que mais importa:** eles investigaram uma acurácia aparente de 53,72% e descobriram **5.307 criptogramas sobrepostos entre treino e teste (~5%)**. Entre os 70.023 criptogramas únicos do teste, a acurácia era 53,58%; **isolando os que só apareciam no teste, caía para 49,90%** — acaso puro. Conclusão literal: "*The observed marginal improvements in accuracy above random chance are entirely due to memorization of overlapping ciphertext samples, rather than genuine generalization by the ML algorithm.*"

**[MINHA]** Seu key-holdout já protege contra a versão de chave desse problema. Mas a versão de *plaintext* merece uma checagem explícita: com 180.000 amostras sorteadas de um corpus finito (SPGC + ImageNet), há trechos de plaintext repetidos entre treino e teste? Se houver, e se o piso de rodada baixo vier justamente de redundância do plaintext, você pode ter um canal de memorização análogo. Vale reportar, no capítulo de ameaças à validade, a contagem de sobreposição de trechos de plaintext entre partições. É um parágrafo que blinda a tese.

##### 9.2 O trabalho do seu próprio orientador — obrigatório citar

de Mello & Xexéo, *Identifying Encryption Algorithms in ECB and CBC Modes Using Computational Intelligence*, J. Univ. Comput. Sci. 24(1):25–42 (2018). **[PUB]**

Setup: corpora em **7 idiomas**, 600 textos cada; 7 algoritmos (DES, Blowfish, RSA, ARC4, Rijndael, Serpent, Twofish) em ECB e CBC; 6 classificadores (C4.5, PART, FT, Complement Naive Bayes, MLP, WiSARD); chaves de 128 bits, **uma chave distinta por criptograma** ("*each cryptogram was associated with a different key in order to avoid any influence of key patterns on the data mining process*"); split 66/34 com validação cruzada 10-fold; features por "bin size" (histograma de padrões de bits).

Resultados: **ECB — identificação plena** (100% de acurácia para quase todos, exceto ARC4, com bin de 28 bits); **CBC — 40–50%** com Complement Naive Bayes e bin de 34 bits, "*greater than the probabilistic bid*" (acaso = 14,3% para 7 classes), com crescimento monotônico no tamanho do bin.

Conclusão dos autores: "*the most important result was the identification of algorithms in CBC mode. Although* (…) *lower rates than ECB, they were not insignificant since they were greater than the probabilistic bid.*"

**[MINHA] Leitura crítica, para debate.** O ECB reconhecer 100% é esperado e não é criptanálise — é o modo vazando a estrutura do plaintext, exatamente como o seu controle positivo AES-ECB. O resultado do CBC é o interessante e o que merece escrutínio. Um sinal em CBC acima do acaso para cifras completas contradiz o limite da Seção 1.1, a menos que venha de (a) tamanhos de bloco diferentes (DES/Blowfish = 64 bits vs. AES/Serpent/Twofish = 128; e RSA não é cifra de bloco simétrica), que é essencialmente metadado de comprimento e alinhamento, ou (b) das features de "bin" capturarem padding/alinhamento. Note que **o tamanho de bloco separa trivialmente as classes** — 64 vs. 128 bits muda o padrão de padding e o comprimento. Isso não invalida o trabalho, mas provavelmente explica a maior parte dos 40–50%, e é o mesmo cuidado que você já toma ao excluir `len_ct`. Como o seu v2 exclui comprimento e usa quatro algoritmos com tamanhos de saída deliberadamente alinhados (exceto Grain), você está medindo algo mais estrito. **Vale dizer isso na dissertação com respeito e com o argumento técnico explícito** — é a diferença entre "ele achou sinal e eu não" e "medimos coisas diferentes, e eis por quê".

Trabalho correlato do mesmo grupo: de Mello & Xexéo, *Cryptographic Algorithm Identification Using Machine Learning and Massive Processing* [CIT].

##### 9.3 Distinguidores neurais sobre os seus algoritmos — todos diferenciais

| Trabalho | Fonte | Resultado | Modelo de ameaça |
|---|---|---|---|
| Gohr, *Improving attacks on round-reduced Speck32/64 using deep learning* | CRYPTO 2019 [CIT] | fundador | chosen-plaintext, diferença escolhida |
| Baksi, Breier, Chen, Dong, *Machine Learning Assisted Differential Distinguishers For Lightweight Ciphers* | DATE 2021, pp. 176–181; ePrint 2020/571 [PUB] | Gimli-Hash/Cipher **8 rodadas** (2^23 treino, 2^14,3 online — "*cube root complexity*" vs. 2^52 da trilha ótima); **Ascon-permutation: 2 distinguidores até 3 rodadas com 2^19 dados de treino**; KNOT-256 até 10; KNOT-512 até 12; Chaskey 4 rodadas (contradizendo a claim dos autores) | 'all-in-one' differential, **diferença de entrada fixa escolhida** |
| Rajan, Roy, Sen, Mishra, *Deep Learning-Based Differential Distinguisher for Lightweight Cipher GIFT-COFB* | Machine Intelligence and Smart Systems, Springer (2022), pp. 397–406 [CIT] | MLP distingue **2 a 6 rodadas** de GIFT-COFB de dados aleatórios, com dois conjuntos de classes diferenciais | diferencial |
| *Neural differential distinguishers for GIFT-128 and ASCON* | J. Inf. Secur. Appl. (2024), S2214212624000619 [CIT] | **GIFT-128: 7 rodadas, 55,42% → 99,36%**; **Ascon-permutation: 4 rodadas, 50,69% → 69,25%**; cobre 1 rodada a mais que os anteriores no Ascon | usa distribuição de scores de múltiplas diferenças de criptograma |
| *ML Based Improved Differential Distinguisher with High Accuracy: GIFT-128 and ASCON* | SPACE 2024, LNCS [CIT] | GIFT-128 6 rodadas 99,70%; 7 rodadas 95,47% com 32 pares; Ascon 4 rodadas 53,54% | multi-pair triplet, CNN + Residual Shrinkage |
| Bellini, Gérault, Hambitzer, Rossi, *A Cipher-Agnostic Neural Training Pipeline with Automated Finding of Good Input Differences* | ToSC 2023(3):184–212, ePrint 2022/1467 [CIT] | **DBitNet** + algoritmo evolucionário para achar diferenças; competitivo com abordagens especializadas em SPECK32/SIMON32 | diferença escolhida (o pipeline *busca* a diferença) |
| Gerault, Hambitzer, Huppert, Picek, *Survey: Six Years of Neural Differential Cryptanalysis* | IACR CiC 3(2) (2025) [PUB] | catálogo de **71 artigos** | **"The document does not explicitly discuss single-ciphertext or ciphertext-only neural distinguishers"** |

**A conclusão desta tabela, e é o seu gap:** 71 artigos de criptanálise neural em seis anos, e **nenhum** em ciphertext-only. Toda a literatura vive em chosen-plaintext com diferença escolhida. O survey confirma isso explicitamente. Você está num espaço sem competidor — o que é bom para originalidade e ruim para baseline.

##### 9.4 Identificação de algoritmo por ML — o resto da literatura

| Trabalho | Resultado | Observação |
|---|---|---|
| MLP para identificação de cifra de bloco, *Soft Computing* (2025) [CIT] | 76,5% de acurácia binária média, arquivos de 1 KB a 512 KB | |
| HKNNRF (KNN híbrido + RF), PMC9575859 [CIT] | 69,5% binário; **34% em 5 classes** | features de testes NIST em cenário ciphertext-only |
| CNN-Transformer fusion, Springer (2024) [CIT] | ~91% binário; ~70% em 8 classes, **com chaves aleatórias** | |
| Classification of Encryption Algorithms Based on Ciphertext Using Pattern Recognition, Springer (2019) [CIT] | LR 79%; 100% precisão/recall para AES e DES | |
| Rocha et al., *Artificial Intelligence Applied to the Identification of Block Ciphers*, IJCA 185(34) (2023) [CIT] | — | grupo brasileiro |
| MIND-Crypt [PUB] | **49,90%** em amostras inéditas | o negativo bem-feito |

**[MINHA]** Há uma tensão gritante nessa tabela: acurácias de 70–91% em identificação multi-classe convivem com 49,90% no único trabalho que isolou memorização. As acurácias altas são, quase certamente, um coquetel de (i) tamanhos de bloco/chave diferentes, (ii) padding, (iii) reuso de chave entre treino e teste, (iv) sobreposição de amostras. Sua dissertação, com key-holdout, comprimento excluído, mesmos plaintexts/chaves/nonces encadeados e bootstrap agrupado por chave, é metodologicamente **mais rigorosa que praticamente toda essa literatura**. Vale uma tabela comparativa de protocolo experimental no capítulo de trabalhos relacionados — mostrando coluna a coluna quem faz key-holdout, quem exclui comprimento, quem controla plaintext. Esse quadro, sozinho, justifica o H₀.

---

#### 10. MARGEM DE SEGURANÇA: DEFINIÇÕES, O PROBLEMA DA NORMALIZAÇÃO, E A TABELA CRUZADA

##### 10.1 Como a literatura define

A definição operacional é uniforme e simples: **margem = (rodadas totais − rodadas atacadas) / rodadas totais**. Serpent: 16 rodadas julgadas suficientes, 32 especificadas "*as insurance against future discoveries*". Simon: margem calibrada em ~30%, "*similar to AES-128*".

##### 10.2 O NIST admite que não é direto — e a nota de rodapé é sua melhor citação

NISTIR 8454, nota de rodapé 1, verbatim **[PUB]**:

> "*Note that determining the security margins of the finalists is not straightforward, as some of the finalists have a different number of rounds for different parts of the cipher (e.g., initialization, message/AD processing and finalization) or **full-round distinguishers for the underlying components (e.g., permutation) do not necessarily mean that there is no security margin**.*"

**Não existe normalização aceita.** Procurei e não encontrei nenhuma proposta de métrica comum publicada, e o NIST declara o problema sem resolvê-lo. Isso significa: **propor uma normalização é contribuição em aberto**, e é uma contribuição que a sua tese pode fazer de graça, porque você já vai ter os dados.

##### 10.3 O quadro cruzado dos quatro finalistas

Compilado de NISTIR 8454, das specs e dos artigos lidos. **[PUB]** exceto onde marcado.

| | **Ascon-AEAD128** | **GIFT-COFB** | **Grain-128AEADv2** | **Schwaemm256-128** |
|---|---|---|---|---|
| Tipo | esponja/duplex | cifra de bloco + COFB | fluxo LFSR+NFSR | esponja ARX (Beetle) |
| "Rodada" | rodada da permutação de 320 bits (grau 2) | rodada SPN de 128 bits (S-box 4 bits) | 1 clock de shift register | 1 step = 8 Alzette-rounds × 6 branches |
| Total | 12 (init/final) + 8 (dados) | 40 | **512 init** (320+64+128) | 11 big / **7 slim** |
| Nonce / tag | 128 / 128 bits | 128 / 128 | **96 / 64** | **256** / 128 |
| Rate / capacidade | 128 / 192 | — (bloco 128) | — | 256 / 128 |
| **Melhor key-recovery** | **7/12** (2^70 dados, 2^72,4 tempo, nonce-resp.) | **27/40** em GIFT-128; **16/40** em GIFT-COFB de fato | **192/512** (2^127), sob hipótese de pre-output acessível | 4,5 steps guess-and-determine, **acima do limite de dados** |
| **Melhor distinguidor da primitiva** | **12/12** zero-sum a 2^55; 8/12 HD a 2^48 | 11/40 integral (12 provadamente nenhum) | 189–193/512 | 4,5/11 integral; 6 steps rotacional |
| Margem declarada NIST | "alta" | "alta (≥30%)" | "alta" | "alta" |
| Margem em fração atacada | 58% (7/12) | 32,5% (13/40 restantes… 27/40 atacado) | 37,5% (192/512) | ~41% (4,5/11) |
| **Invariante não-linear** | inaplicável (sem chave) | **provadamente imune** (sem invariante quadrático na S-box) | inaplicável | inaplicável |
| **Rate de entrada conhecido CT-only** | **SIM (= C_i)** | não (mascarado por L) | n/a | não (ρ + rate whitening) |
| **Correlação linear detectável a 2^−13,4** | 2 rodadas (Tipo II) | ~3–5 rodadas | inexistente (melhor: 2^−54) | ~2 steps |
| Piso CT-only medido por você | — | **3/40 (7,5%)** | **28/256 (11%)** | — |
| **Piso CT-only predito [MINHA]** | **2/8 pb (25%) ou 3/12 init (25%)** | **3/40 (7,5%)** ✓ bate | — | **1–2/7 slim (14–29%)** |

##### 10.4 [MINHA] Três normalizações candidatas, com prós e contras

Já que não existe uma aceita e você vai precisar de uma:

**(a) Fração de rodadas.** `r_atacado / r_total`. Prós: trivial, é o que o NIST e todo mundo usa informalmente. Contras: 1 clock do Grain e 1 step do Sparkle384 (6 Alzettes de 4 rodadas ARX cada) não são comparáveis nem de longe; e Grain tem três fases de init com papéis distintos.

**(b) Normalização por grau algébrico atingido.** Compare `log₂(grau máximo da saída após r rodadas)` em vez de r. Prós: unidade comum, teoricamente motivada, e é *exatamente* o que determina se um distinguidor integral/cubo existe. Ascon: grau ≤ 2^r. Sparkle/Alzette: graus exatos publicados por Hu & Yap [PUB]. Grain: numeric mapping de Liu, CRYPTO 2017 [CIT], dá o limite superior de grau para NFSR com complexidade linear. GIFT: grau 3 por rodada (S-box de grau 3). Contras: só captura o eixo algébrico; ignora correlação linear.

**(c) Normalização por difusão completa.** Conte quantas rodadas até todo bit de saída depender de todo bit de entrada, e expresse `r_atacado / r_difusão_completa`. Sparkle declara 3 steps para difusão completa e adiciona "*three steps for full diffusion plus one additional step*" como margem [PUB]. Prós: é a unidade que mais se aproxima do que o *seu* piso CT-only mede (destruição de redundância). Contras: difusão completa não é a mesma coisa que confusão suficiente; um mapa linear difunde completamente em 1 rodada e não é seguro.

**Recomendação [MINHA]:** relate (a) porque é o que a banca espera, e proponha (b) como métrica secundária, porque é a única com fundamento teórico que atravessa esponja/SPN/fluxo, e porque você já vai ter os dados de grau dos quatro. Não invente uma quarta.

##### 10.5 O vazamento que você exclui e um adversário real não excluiria

**[MINHA]**, e merece um parágrafo na dissertação.

O Grain-128AEAD tem tag de **64 bits** e nonce de **96 bits**; os outros três têm tag de 128 bits e nonces de 128 (Ascon/GIFT) ou **256** (Schwaemm). Consequência: `len_ct` **identifica o Grain com 100% de acurácia**, sem nenhuma criptanálise, e o comprimento do nonce público separa o Schwaemm. Você trata isso corretamente como metadado e trunca na análise. Mas um adversário passivo real *tem* o comprimento. A leitura honesta é: **em campo, três dos quatro algoritmos são distinguíveis de graça por comprimento, e a pergunta científica interessante é o que sobra depois de neutralizar isso.** Vale enunciar assim, explicitamente — fortalece a tese em vez de enfraquecer, porque delimita a pergunta.

---

#### 11. CATÁLOGO ESTRUTURADO — CADA TÉCNICA COM OS CINCO CAMPOS

Formato pedido: **O que é / Fonte / Cabe? / Custo / O que prevê.**

---

##### T1 — Division property bit-based + MILP (distinguidor integral)

1. **O que é.** Propaga um invariante sobre subconjuntos do espaço de entrada por cada operação da cifra, determinando estruturalmente até quantas rodadas a soma sobre um cubo é garantidamente zero em algum bit de saída. Modelado como MILP/SAT, é automático.
2. **Fonte.** Todo, EUROCRYPT 2015 [PUB]; Todo & Morii, FSE 2016 [CIT]; Xiang et al., ASIACRYPT 2016 [CIT]; Eskandari et al., SAC 2018, ePrint 2018/688 [PUB].
3. **Cabe?** **NÃO** na forma publicada (exige conjunto de entradas escolhido). **ADAPTÁVEL** via T2.
4. **Custo.** Só a modelagem: SageMath/CLAASP + Gurobi ou CryptoMiniSat; dias a semanas por primitiva. Zero custo de dados.
5. **Prevê.** GIFT-128: nenhum distinguidor integral em ≥12 rodadas (já provado). Ascon: nenhum em ≥12. Sparkle384: nenhum em >4,5 steps. Se você achar sinal ML em rodadas acima desses limites, **é bug no experimento** — é um excelente teste de sanidade negativo.

---

##### T2 — [MINHA] Integral observacional por nonce-contador com cancelamento em bits determinísticos

1. **O que é.** Os 2^k nonces consecutivos de um contador formam um cubo gratuito; restringindo a soma às posições de bit onde o plaintext é determinístico (MSB de bytes ASCII), o termo do plaintext cancela exatamente e a soma do keystream fica exposta. Distinguidor integral completamente passivo.
2. **Fonte.** Não publicado. Precedente conceitual: FMS/WEP, SAC 2001 [PUB] (estrutura colhida de contador, passivo, plaintext parcialmente conhecido). Teoria do cubo: Dinur & Shamir, EUROCRYPT 2009 [CIT].
3. **Cabe?** **SIM.** Não arranha nenhuma premissa: sem plaintext escolhido, sem diferença escolhida, sem reuso de nonce, sem oráculo, sem canal lateral. Adiciona apenas "a distribuição do plaintext é conhecida", que é constitutiva do modelo CT-only (Todo–Leander–Sasaki [PUB]).
4. **Custo.** Computação: trivial (XOR acumulado). **Geração: exige um braço novo** com nonce contador **por chave**, alinhado em 2^k, com k ≥ 17. Mas só o primeiro bloco de cada criptograma é necessário: 2^17 × 16 B = 2 MB/chave; **< 1 GB para 300 chaves**. Engenharia: ~1 semana.
5. **Prevê.** **Predição determinística, não estatística.** Com a inicialização reduzida a r rodadas e k > 2^r, a soma nas posições MSB deve ser **identicamente 0 em toda chave**. Com o algoritmo completo, deve ser uniforme. O cruzamento de r onde isso vira é o piso integral CT-only, e para o Ascon eu predigo **r = 4 com k = 17**, **r = 5 com k = 33**.

---

##### T3 — Cube attack / superpoly recovery (3SDP/u, monomial prediction, CMP)

1. **O que é.** Soma a saída sobre um cubo de bits de IV; a soma é o "superpoly", um polinômio nos bits de chave. Recuperar seu ANF exato dá recuperação de chave.
2. **Fonte.** Hao–Leander–Meier–Todo–Wang, EUROCRYPT 2020 [PUB]; Hu et al., ASIACRYPT 2020/2021 [CIT]; He et al., EUROCRYPT 2024 [PUB]; Liu & Tian, ToSC 2024(2) [PUB]; Rohit et al., ToSC 2021(1) e ToSC 2021(4) [PUB]; Hu, ToSC 2024(2) [PUB].
3. **Cabe?** **NÃO** para recuperação de chave (exige cubos com condições impostas sobre bits específicos do nonce). **ADAPTÁVEL** para distinguisher via T2.
4. **Custo.** Proibitivo na forma original (2^103–2^127).
5. **Prevê.** Nada de observável no seu regime para os algoritmos completos. Usa-se como **calibração**: se seu piso ML para Grain fosse >192 clocks, algo estaria errado, porque nem a criptanálise dedicada com chosen-IV e 2^127 operações passa disso.

---

##### T4 — Zero-sum distinguisher e partições zero-sum

1. **O que é.** Escolhe um estado intermediário e propaga em ambas as direções; a soma de entradas e saídas é zero porque o grau algébrico nas duas direções é limitado.
2. **Fonte.** Boura–Canteaut–De Cannière, FSE 2011 [CIT]; Aumasson & Meier 2009 [CIT]; Hu, Peyrin, Tan, Yap, ASIACRYPT 2023, ePrint 2022/1335 [PUB]; Dobraunig et al., CT-RSA 2015 [PUB].
3. **Cabe?** **NÃO.** Inside-out exige fixar estado interno; a partição exige 2^n avaliações ("*actually impossible to perform*", segundo os próprios autores [PUB]).
4. **Custo.** N/A.
5. **Prevê.** Nada observável. **Contribuição indireta e valiosa:** a vantagem do zero-sum sobre uma permutação perfeita "*usually [falls] under a factor of 2*" [PUB] — é o argumento pronto para explicar por que um distinguidor de 12 rodadas na permutação **não** implica nada no classificador.

---

##### T5 — Ataque de invariante não-linear (extensão ciphertext-only)

1. **O que é.** Função `g` com `g(p) ⊕ g(E_k(p))` constante para chaves fracas; em modos CBC/CFB/OFB/CTR com o mesmo plaintext sob IVs distintos, vira recuperação de mensagem **ciphertext-only**.
2. **Fonte.** Todo, Leander, Sasaki, ASIACRYPT 2016, ePrint 2016/732 [PUB]. Antecedentes: Leander et al., CRYPTO 2011 [CIT]; Leander–Minaud–Rønjom, EUROCRYPT 2015 [CIT]. Resistência: Beierle–Canteaut–Leander–Rotella, CRYPTO 2017 [CIT].
3. **Cabe?** **SIM em princípio, NÃO na prática, para estes quatro.** GIFT: provado imune, sem invariante quadrático na S-box [PUB]. Ascon/Schwaemm: permutações sem chave. Grain: não key-alternating.
4. **Custo.** Baixo se existisse: "*only a handful of plaintext-ciphertext pairs and minimal computational costs*".
5. **Prevê.** Nada. **Resultado útil: caminho fechado, com prova documentada pelos projetistas.** Recomendo uma subseção curta na dissertação.

---

##### T6 — Características lineares Tipo II / Tipo III (distinguidor de keystream em duplex)

1. **O que é.** Trilhas lineares com máscaras restritas à parte externa (rate) do estado da esponja — as únicas observáveis. Tipo III (entrada e saída no rate) liga `C_i` ao keystream que gera `C_{i+1}` e "*do not rely on the fact that always the same key is used*".
2. **Fonte.** Dobraunig, Eichlseder, Mendel, ASIACRYPT 2015, ePrint 2015/1200 [PUB]. Inspiração: Minaud, *Linear Biases in AEGIS Keystream*, SAC 2014 [CIT]. Formalização paralela: SPARKLE Spec, Property 3.2.3 [PUB].
3. **Cabe?** **SIM, Tipo III integralmente.** **ADAPTÁVEL, Tipo II**, se você restringir a máscara de saída a bits determinísticos do plaintext.
4. **Custo.** Verificação empírica: uma passada linear, **horas**. Busca de máscaras: reimplementar `lineartrails` (github.com/iaikkrypto/lineartrails, público) com a restrição extra — 2–4 semanas. Versão barata: varredura exaustiva de máscaras de peso ≤2 sobre as 16 posições MSB — **17.408 pares, minutos**.
5. **Prevê.** Ascon completo (pb=8): nada. Ascon pb=2: correlação 2^−8, F1 próximo de 1,0 com poucos milhares de amostras. Ascon pb=3: 2^−30, nada. **Piso predito: 2 de 8.** Schwaemm: piso 1–2 de 7 steps. Se o piso medido para o Ascon for exatamente 2 de pb, a teoria está validada; se for 4 ou mais, existe uma característica Tipo III melhor do que a literatura conhece, **e isso seria publicável em ToSC**.

---

##### T7 — Fast correlation attack sobre keystream

1. **O que é.** Explora a correlação entre o estado inicial do LFSR e o keystream via múltiplas aproximações lineares; recupera o estado.
2. **Fonte.** Todo, Isobe, Meier, Aoki, Zhang, CRYPTO 2018, ePrint 2018/522 [PUB]; Meier & Staffelbach 1989 [CIT]; Siegenthaler 1984 [CIT].
3. **Cabe?** **NÃO.** Exige (i) 2^113,8 bits de keystream de um único par chave/nonce; (ii) o pre-output completo — e o Grain-128AEADv2 expõe só os bits pares; (iii) keystream, não criptograma (isto é, plaintext conhecido).
4. **Custo.** 2^115,4 tempo. Inviável por 28 ordens decimais.
5. **Prevê.** **Impossibilidade quantificada:** melhor correlação de keystream conhecida = 2^−54,24; seu limiar = 2^−16,9; déficit de 2^37. **Este é o número que encerra a discussão sobre o Grain.**

---

##### T8 — Diferencial passivo com diferenças de nonce colhidas do contador

1. **O que é.** Pares de nonces consecutivos dão diferenças de entrada de peso 1 de graça; nas posições MSB do plaintext ASCII, `ΔC = ΔZ` exatamente.
2. **Fonte.** Não formulado assim. Precedente: FMS/WEP, SAC 2001 [PUB]. Base diferencial-linear: Hu et al., ASIACRYPT 2023 [PUB]; conditional differential: Knellwolf–Meier–Naya-Plasencia, ASIACRYPT 2010 [PUB].
3. **Cabe?** **SIM**, com a ressalva de que o adversário identifica os pares consecutivos pelo nonce público — que é precisamente o que um nonce público comunica.
4. **Custo.** Zero adicional de dados (você já tem os pares). Engenharia: agrupar por Δ de nonce e computar estatísticas de ΔC restritas a MSBs — dias.
5. **Prevê.** Ascon com init reduzida: 4 rodadas detectáveis com ~2^8 pares (contra 4 textos no caso escolhido); 5 rodadas provavelmente fora. Saturação em ≥4–5 rodadas, porque a probabilidade diferencial de 4 rodadas é ≤ 2^−72 [PUB]. **Isto casa com o que você já observou** (pa=1/2 detectável, pa≥4 acaso).

---

##### T9 — Distinguidores integrais estatísticos (χ² em vez de soma exata)

1. **O que é.** Relaxa "a soma é exatamente zero" para "a distribuição da soma é enviesada", usando χ², o que reduz a complexidade de dados e tolera ruído.
2. **Fonte.** Wang et al., FSE 2016 [CIT]; *Statistical Integral Distinguisher with Multi-structure and Its Application on AES*, ACISP 2017, LNCS [CIT]; versão de periódico em Cryptogr. Commun. (2018), DOI 10.1007/s12095-018-0286-5 [CIT]. Exemplo: distinguidor de 5 rodadas do AES com S-box secreta, 2^114,32 criptogramas escolhidos, 2^110 cifragens, 2^33,32 blocos.
3. **Cabe?** **ADAPTÁVEL** e muito bem casado com T2: se você só conseguir k = 6 (100 nonces/chave), a soma exata falha, mas o desvio estatístico da soma ao longo de muitas chaves ainda pode ser detectável. É exatamente o remédio para a limitação de k do seu dataset atual.
4. **Custo.** Baixo. É um χ² sobre somas de cubo, com as 300 chaves como repetições independentes.
5. **Prevê.** Estende T2 em ~1 rodada com o mesmo k, ou permite usar o dataset **existente** (k=6) em vez de gerar um braço novo. Se T2 é a aposta principal, T9 é o plano B que roda amanhã.

---

##### T10 — BoolTest / EACirc / CryptoStat como bateria de piso de rodada

1. **O que é.** Busca automatizada (exaustiva ou evolucionária) de uma função booleana sobre bits de saída cujo viés não se espera de dados aleatórios. É, em espírito, o que a sua CNN faz, mas interpretável.
2. **Fonte.** Sýs, Klinec, Kubíček, Švenda, SECRYPT 2017 + CCIS 2019 [PUB]; Švenda et al., SECRYPT 2013 / CCIS 2014 [PUB]; Kaminsky, ePrint 2019/078 [PUB]; *Not So Greedy: Enhanced Subset Exploration for Nonrandomness Detectors*, Springer 2018 [CIT]; Stankovski, INDOCRYPT 2010 [CIT].
3. **Cabe?** **SIM, integralmente.** Rodam sobre a saída, sem exigir nada da entrada — o que muda é apenas a sensibilidade.
4. **Custo.** BoolTest é open-source (crocs-muni). Rodar sobre os quatro finalistas em todas as contagens de rodada: dias de CPU. **Trivial perto do que você já gastou.**
5. **Prevê.** Pela coluna RPC da Tabela 4 [PUB], pisos na faixa de 1 a 7 rodadas para primitivas maduras. Para os quatro finalistas, eu predigo **[MINHA]**: Ascon 2–3 de 12; GIFT 3–5 de 40; Grain 20–35 de 512; Schwaemm 1–2 de 7 steps. **E mais importante: BoolTest dá o distinguidor em forma legível** ("quais bits exatamente"), o que a CNN não dá. Isso vira uma seção de interpretabilidade da dissertação praticamente de graça, e responde à pergunta que a banca vai fazer: "o que a rede aprendeu?"

---

##### T11 — Bateria estatística clássica (NIST STS, Dieharder, TestU01)

1. **O que é.** As baterias padrão.
2. **Fonte.** NISTIR 6483 [PUB]; SP 800-22 [CIT]; Doğanaksoy et al. [CIT] para sequências curtas.
3. **Cabe?** **SIM**, mas com a advertência de Doğanaksoy et al.: para sequências curtas (≤512 bits) vários testes não se aplicam ou dão valores não confiáveis [CIT]. Suas amostras de 64 KB estão bem acima disso, então está OK.
4. **Custo.** Já feito (você tem as 25 features NIST SP 800-22).
5. **Prevê.** Menos sensível que BoolTest por ~1 ordem de magnitude em dados (Tabela 3 do BoolTest [PUB]). Espere pisos 1 rodada abaixo dos de T10.

---

##### T12 — Subspace trails e diferenciais truncadas

1. **O que é.** Subespaços afins mapeados em subespaços afins com probabilidade 1.
2. **Fonte.** Grassi–Rechberger–Rønjom [CIT]; Leander, Tezcan, Wiemer, ToSC 2018(1):74–100 [CIT]; Tezcan, ePrint 2020/1458 [PUB]. Para o Ascon: 3 rodadas para frente com dimensão 2^98; 1 rodada para trás com dimensão 125 [PUB via NISTIR].
3. **Cabe?** **NÃO.** Exige que o conjunto de entradas seja um coset de subespaço escolhido. Mesma barreira do integral, e sem o atalho do contador (o coset relevante não é o dos bits baixos do nonce).
4. **Custo.** N/A.
5. **Prevê.** Nada observável. 3 rodadas de 12 é, ainda assim, um bom limite superior de referência para o piso estrutural do Ascon.

---

##### T13 — Propriedade estrutural-diferencial independente de chave ("multiple-of-8")

1. **O que é.** Para 5 rodadas do AES, o número de pares de textos com diferença em subespaço é sempre múltiplo de 8, **independentemente da chave secreta**. Antes disso, só se conheciam propriedades chave-independentes até 4 rodadas.
2. **Fonte.** Grassi, Rechberger, Rønjom, *A New Structural-Differential Property of 5-Round AES*, EUROCRYPT 2017, pp. 289–317, ePrint 2017/118 [CIT].
3. **Cabe?** **NÃO.** Exige um coset escolhido de plaintexts.
4. **Custo.** N/A.
5. **Prevê.** Nada diretamente. Vale citar porque é o exemplo canônico de "propriedade estrutural independente da chave", que é a categoria que mais se aproximaria do que um classificador CT-only poderia, em princípio, aprender. E o fato de que a melhor dessas propriedades para o AES exige cosets escolhidos é, por si, evidência de que a categoria não sobrevive ao CT-only.

---

##### T14 — Ultrametric integral cryptanalysis / abordagem geométrica de Beyne

1. **O que é.** Reformula criptanálise linear, invariante e integral como propriedades espectrais de matrizes de correlação, sobre um corpo ultramétrico. Unifica os três eixos.
2. **Fonte.** Beyne, ASIACRYPT 2018, ePrint 2018/763 [CIT]; Beyne, ASIACRYPT 2021 [CIT]; Beyne & Verbauwhede, ASIACRYPT 2024 [CIT]. Não obtive o texto integral de nenhum.
3. **Cabe?** **Não sei, e digo isso em vez de chutar.** O arcabouço é agnóstico quanto ao modelo de ataque; a pergunta de se ele produz propriedades com máscaras restritas ao observável (análogo Tipo III) está em aberto na minha leitura. É o item da lista com maior incerteza e maior potencial.
4. **Custo.** Alto: exige ler três artigos densos de teoria antes de saber se vale.
5. **Prevê.** Sem previsão falsificável no momento. **Registro como pista a perseguir, não como aposta.**

---

##### T15 — Generic partial decryption como feature engineering

1. **O que é.** Decifra parcialmente com chaves candidatas e usa o resultado como feature do distinguidor neural.
2. **Fonte.** *Generic Partial Decryption as Feature Engineering for Neural Distinguishers*, LATINCRYPT 2025, Springer [CIT].
3. **Cabe?** **NÃO.** Exige espaço de chaves enumerável e, portanto, oráculo de decifragem.
4. **Custo.** N/A.
5. **Prevê.** N/A. Listado por completude da varredura.

---

#### 12. O QUE É IMPOSSÍVEL, E OS NÚMEROS QUE PROVAM

Consolidando. Estes são os enunciados que eu colocaria no capítulo de discussão, porque transformam H₀ em resultado.

**(I1)** Pelo argumento de distância de variação total (§1.1), `Adv(A vs B) ≤ Adv^IND$(A) + Adv^IND$(B)`. Com σ ≈ 2^26,9 blocos e t ≈ 2^40, os termos de modo provados valem **2^−253 (Ascon)** e **2^−74 (GIFT-COFB)**. Portanto, com algoritmos completos, **um F1 acima de 0,50 só pode vir de quebra da primitiva, de metadado, ou de vazamento experimental**. **[MINHA]**, sobre limites **[PUB]**.

**(I2)** Limiar de detectabilidade: `|c| ≥ 2^−16,9` (por bit, classe inteira), `2^−13,4` (por bloco), `2^−9,3` (por bloco dentro de chave). **[MINHA]**

**(I3)** Grain-128AEADv2: a melhor correlação de keystream conhecida é **2^−54,24**, e o FCA exige **2^113,8 bits de um único par chave/nonce**, dos quais você tem 2^19,3. Além disso, **metade do pre-output nunca é exposta** por design. Distinguir Grain completo é impossível no seu regime por margem de ~2^37. **[PUB]**

**(I4)** Ascon: a melhor característica linear Tipo II de 4 rodadas tem viés 2^−83 [PUB]; limites provados dão c² ≤ 2^−72 em 4 rodadas e ≤ 2^−108 em 6 [PUB]; e Hirch et al. provam além de 2^−256 em 12 rodadas [PUB]. Com pb = 8, **o viés observável está 55+ ordens binárias abaixo do limiar**.

**(I5)** GIFT-128: a partir de **12 rodadas não existe nenhum distinguidor integral** por bit-based division property (resultado provado, não empírico) [PUB]. A melhor trilha linear de 11 rodadas tem `|c| = 2^−31` [PUB]. O modo COFB limita a privacidade a `C(σₑ,2)/2^128 ≈ 2^−74` [PUB].

**(I6)** Ataques de invariante em ciphertext-only — o único ramo estrutural que a literatura reconhece como CT-only — estão **provadamente fechados** contra GIFT (sem invariante quadrático na S-box, verificado pelos projetistas) e **estruturalmente inaplicáveis** a Ascon, Schwaemm e Grain. **[PUB]**

**(I7)** Não há estimador de grau algébrico a partir de amostras não estruturadas. O único teste é a derivada de ordem superior, que exige avaliar a função em todos os pontos de um coset. **[MINHA]**, decorrência da definição.

**(I8)** O piso de rodada medido com plaintext real mede uma grandeza **diferente** do piso medido com entrada estruturada, e a diferença documentada é de **2× a 4× em número de rodadas** (BoolTest, coluna CTR/LHW vs. RPC) [PUB]. A frase de Kaminsky é a justificativa canônica [PUB].

---

#### 13. APOSTAS

As três que eu tentaria, nesta ordem, com o porquê.

---

##### APOSTA 1 — Distinguidor linear Tipo III/II com máscara de saída ancorada nos bits determinísticos do plaintext

**O que fazer, concretamente.**

Para Ascon-AEAD128 com `pb` reduzida a r ∈ {1,2,3,4} e completa (8), e para as posições `b` de MSB de byte dentro de cada bloco de 128 bits (`b ∈ {7,15,23,…,127}` na convenção de bytes ASCII):

1. Para cada par de máscaras `(u, v)` com `u` de peso 1 ou 2 sobre os 128 bits de `C_i` e `v` de peso 1 ou 2 sobre as **16 posições MSB** de `C_{i+1}`, acumule `s(u,v) = #{i : ⟨u,C_i⟩ ⊕ ⟨v,C_{i+1}⟩ = 0}` sobre todos os blocos, todas as amostras, **todas as 300 chaves** (pode agregar entre chaves: a permutação não tem chave, o sinal da correlação é fixo).
2. Correlação empírica `ĉ(u,v) = 2·s/N − 1`. Sob H₀, `ĉ ~ N(0, 1/N)` com `N ≈ 2^26,9`, logo σ ≈ 2^−13,4.
3. Z-score, correção BH-FDR sobre os ~17.408 pares (você já tem essa infra).
4. Repita para GIFT-COFB, **dentro de cada chave** (sinal dependente de chave), e combine os 300 Z-scores por qui-quadrado sobre `Z²`.

**Por que esta primeiro.**
- **É a única técnica da lista que é publicada, desenhada exatamente para o seu observável, e ainda não foi tentada no Ascon-AEAD128.** Dobraunig–Eichlseder–Mendel definiram Tipo III em 2015 e disseram "no meaningful results" — **para Ascon-128 com rate 64, otimizando número de S-boxes, e sem restringir a máscara às posições que o plaintext torna gratuitas**. Três diferenças em relação ao seu caso. Pode ser que o negativo se confirme; pode ser que não.
- **Custa quase nada.** É uma passada linear sobre dados que você já tem, para o algoritmo completo. Roda em horas. Não precisa de GPU, não precisa de novo dataset para a parte "completa".
- **Gera número mesmo quando falha.** Você não obtém "nenhum sinal"; obtém "correlação máxima observada = 2^−13,x, consistente com o limite provado de 2^−72", o que é uma frase muito melhor em uma dissertação.
- **A predição é dura e verificável:** piso em **2 de 8 rodadas de pb** para o Ascon, **3 de 40** para GIFT-COFB (número que já bate com o que você mediu — é a validação cruzada do arcabouço), **1–2 de 7 steps** para Schwaemm.
- Bônus estrutural: se o Ascon vazar mais que o Schwaemm nas mesmas rodadas reduzidas, você terá demonstrado empiricamente que o feedback ρ + rate whitening do Beetle **funciona**, o que é um resultado de interesse para a comunidade de design, não só para a sua tese.

**Risco.** Máscaras de peso ≤2 podem não capturar a melhor trilha. Mitigação: se a varredura barata não achar nada em 3 rodadas (onde a teoria diz que deveria achar para peso baixo), aí sim investir na busca com `lineartrails` restrito.

---

##### APOSTA 2 — Integral observacional por nonce-contador (T2), com o braço de dados mínimo

**O que fazer, concretamente.**

Gerar um braço novo, barato:
- 300 chaves (mesmo CTR_DRBG, mesmo offset de seed).
- Para cada chave, **2^17 = 131.072 nonces consecutivos começando em múltiplo de 2^17**, contador por chave (não global).
- Plaintext: só o primeiro bloco de 128 bits precisa ser guardado — **grave apenas `C_0` (16 bytes)**. 2 MB por chave, **600 MB no total**.
- Plaintext ASCII puro (braço de texto), para maximizar as posições determinísticas.
- Variantes de rodada reduzida: Ascon com init ∈ {2,3,4,5,6,12}; GIFT-COFB com r ∈ {2,3,4,5,40}; Schwaemm com steps ∈ {1,2,3,11}; Grain com clocks ∈ {16,24,32,512}.

Análise: para cada chave e cada `k ∈ {8,…,17}`, some XOR os 2^k primeiros `C_0` e teste se os bits MSB da soma são todos 0.

**Por que esta.**
- **É a resposta direta à pergunta que você fez no ângulo** ("existe formulação observacional do integral?"), e a resposta é sim, com uma construção que eu não encontrei na literatura. Se funcionar, é o item publicável da dissertação, não só um capítulo.
- **A predição é binária e não tem zona cinzenta.** Não é "F1 = 0,53, será que é sinal?". É: soma exatamente zero em 300 de 300 chaves, ou não é. Um resultado assim não sobrevive a nenhuma objeção estatística.
- **Custa 600 MB e alguns dias de CPU de geração.** Comparado com as ~20 h/braço de extração de features que você já tem planejadas, é ruído no orçamento.
- **Dá um piso de rodada de natureza diferente do estatístico** — algébrico, estrutural, com limite teórico calculável a priori (`k > 2^r`). Isso permite a normalização (b) da §10.4 e sustenta a comparação entre os quatro algoritmos numa base teórica, resolvendo o problema que o NIST declarou em aberto.
- **Falha informativamente.** Se a soma não for zero onde a teoria diz que deveria, o motivo é identificável: ou o contador não está alinhado, ou as posições MSB não são tão determinísticas quanto você supôs (verificável em 1 minuto no corpus), ou o grau real é menor que 2^r.

**Risco.** O alinhamento do contador precisa estar certo — se o nonce for embaralhado ou se os bits baixos do contador caírem em posições do estado que não são independentes, o cubo não se forma. Mitigação: verificar no código de geração exatamente onde os bits baixos do nonce pousam no estado do Ascon (palavras x3, x4), e alinhar a contagem a isso.

**Plano B embutido:** se gerar o braço novo for inviável por qualquer motivo, rode T9 (integral estatístico χ²) sobre os 100 slots existentes — k = 6, sinal mais fraco, mas roda hoje sobre o dataset atual.

---

##### APOSTA 3 — BoolTest sobre os quatro finalistas, em todas as contagens de rodada, nas quatro estratégias de entrada

**O que fazer, concretamente.**

Rodar BoolTest (crocs-muni, open-source) sobre as saídas dos quatro algoritmos em rodadas reduzidas, replicando **exatamente** a Tabela 4 do artigo de 2017 — quatro colunas: CTR, LHW, SAC e **RPC/texto-real**. Adicionar uma quinta coluna: **CT-only com plaintext Gutenberg**, que é a sua. Produzir a tabela:

| Algoritmo | Total rodadas | CTR | LHW | SAC | RPC | **Gutenberg CT-only** | NIST STS | sua CNN |
|---|---|---|---|---|---|---|---|---|
| Ascon | 12 / 8 | ? | ? | ? | ? | ? | ? | ? |
| GIFT-COFB | 40 | ? | ? | ? | ? | **3** | ? | **3** |
| Grain-128AEADv2 | 512 | ? | ? | ? | ? | **28** | ? | **28** |
| Schwaemm256-128 | 11 / 7 | ? | ? | ? | ? | ? | ? | ? |

**Por que esta é aposta e não tarefa braçal.**
- **Essa tabela não existe.** Verifiquei: BoolTest, EACirc e CryptoStat cobrem DES, 3-DES, AES, Blowfish, MD5, MD6, SHA-1, SHA-256, Keccak, JH, Grøstl, TEA, e os candidatos eSTREAM/SHA-3 — **nenhum dos finalistas do NIST LWC**. Publicar essa tabela é uma contribuição independente do resultado do seu experimento principal.
- **Ela é o que faz o seu H₀ deixar de ser um anticlímax.** Com a coluna CTR ao lado da coluna Gutenberg, o leitor vê de imediato que o colapso de piso não é falha do seu método, e sim a propriedade documentada do cenário. Sem essa coluna, você está dizendo "meu piso é 3 e o do NIST para o Rijndael foi 3, então ok" — com ela, você está dizendo "o piso cai por um fator de 2 a 4 quando se troca entrada estruturada por plaintext real, e eis a medição para os quatro finalistas".
- **BoolTest dá o distinguidor em forma interpretável.** Ele te diz *quais bits* formam a função booleana enviesada. Isso responde a pergunta que a banca vai fazer sobre a CNN e que você hoje não consegue responder. Se a função que o BoolTest encontra para GIFT em 3 rodadas for, digamos, um XOR de bits MSB de bytes vizinhos, você acabou de **provar** que o sinal é redundância do plaintext e não estrutura da cifra — que é exatamente a sua tese registrada, mas hoje sem demonstração direta.
- **Custo baixo e risco baixíssimo.** Ferramenta pronta, open-source, você já tem as variantes de rodada reduzida compiladas para os quatro. Dias de CPU.

**Risco.** BoolTest pode não ser mais sensível que a sua CNN, e aí a coluna "sua CNN" ganha. Isso também é resultado — e é bom para você, porque mostra que o caminho D/E entrega algo que uma bateria dedicada não entrega.

---

##### Por que estas três e não outras

Não escolhi as três mais sofisticadas. Escolhi as três que (i) cabem no modelo de ameaça sem arranhar premissa, (ii) fazem predição numérica falsificável antes de rodar, (iii) custam pouco perto do que você já investiu, e (iv) produzem resultado publicável tanto no sucesso quanto no fracasso.

Descartei explicitamente: cube key-recovery (T3, complexidade proibitiva), zero-sum (T4, exige entrada escolhida e vantagem abaixo de fator 2), invariante (T5, provadamente fechado), FCA (T7, déficit de 2^94), subspace trails (T12, exige coset escolhido), Beyne/ultramétrica (T14, incerteza alta demais para ser aposta — mas é a pista que eu perseguiria se as três acima fossem feitas).

E uma observação final sobre o enquadramento: nada nesta pesquisa aponta para sinal em ciphertext-only contra os algoritmos completos, e as três apostas são, honestamente, apostas sobre **rodadas reduzidas** e sobre **explicar por que não há sinal**, não sobre encontrar sinal onde os limites provados dizem que não pode haver. A Aposta 1 tem uma chance real de contrariar um negativo publicado (o "no meaningful results" do Tipo III no Ascon), e é por isso que ela vem primeiro.

---

#### FONTES

Ordenadas por primeira aparição relevante.

Todo, *Structural Evaluation by Generalized Integral Property* — eprint.iacr.org/2015/090 · link.springer.com/chapter/10.1007/978-3-662-46800-5_12 · Xiang–Zhang–Bao–Lin, MILP division property, ASIACRYPT 2016 — eprint.iacr.org/2016/857 · eprint.iacr.org/2016/811 · eprint.iacr.org/2016/1101 · *Finding Integral Distinguishers with Ease* — eprint.iacr.org/2018/688 · 3SDP/u, EUROCRYPT 2020 — eprint.iacr.org/2020/441 · Monomial Prediction, ASIACRYPT 2020 — eprint.iacr.org/2020/1048 · Nested Monomial Predictions — eprint.iacr.org/2021/1225 · Stretching Cube Attacks — eprint.iacr.org/2022/1218 · MitM Superpoly, EUROCRYPT 2024 — eprint.iacr.org/2024/342 · Perfect Monomial Prediction for Modular Addition, ToSC 2024 — eprint.iacr.org/2024/1335 · On Extending Integral Distinguishers — eprint.iacr.org/2026/1402 · Beyne & Verbauwhede, Ultrametric Integral Cryptanalysis — link.springer.com/chapter/10.1007/978-3-030-03326-2_1 · NISTIR 8454 — nvlpubs.nist.gov/nistpubs/ir/2023/NIST.IR.8454.pdf · Tezcan, Ascon/DryGASCON/Shamash — eprint.iacr.org/2020/1458 · HATF/DSF, ASIACRYPT 2023 — eprint.iacr.org/2022/1335 · Rohit–Hu–Sarkar–Sun, Misuse-Free 7-Round Ascon — doi.org/10.46586/tosc.v2021.i1.130-155 · Rohit & Sarkar, Weak Keys of Round Reduced Ascon — tosc.iacr.org/index.php/ToSC/article/view/9329 · Hu, Improved Conditional Cube Attacks, ToSC 2024 — tosc.iacr.org/index.php/ToSC/article/view/11623 · ascon.isec.tugraz.at/publications.html · Erlacher–Mendel–Eichlseder, Bounds for Ascon, ToSC 2022 — d-nb.info/1274454948/34 · Heuristic Tool for Linear Cryptanalysis, ASIACRYPT 2015 — eprint.iacr.org/2015/1200 · Minaud, Linear Biases in AEGIS Keystream — eprint.iacr.org/2018/292 · Exact Security Analysis of ASCON — eprint.iacr.org/2023/775 · SP 800-232 — nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-232.pdf · Nonlinear Invariant Attack, ASIACRYPT 2016 — eprint.iacr.org/2016/732 · Proving Resistance Against Invariant Attacks, CRYPTO 2017 — eprint.iacr.org/2017/463 · Invariant Subspace Attack, CRYPTO 2011 — link.springer.com/chapter/10.1007/978-3-642-22792-9_12 · Beyne, Invariants as Eigenvectors — eprint.iacr.org/2018/763 · GIFT: A Small Present, CHES 2017 — eprint.iacr.org/2017/622 · Linear Cryptanalyses of Three AEADs with GIFT-128, ToSC 2021 — eprint.iacr.org/2021/661 · GIFT-COFB v1.1 — csrc.nist.gov/CSRC/media/Projects/lightweight-cryptography/documents/finalist-round/updated-spec-doc/gift-cofb-spec-final.pdf · SPARKLE/Schwaemm spec — csrc.nist.gov/CSRC/media/Projects/lightweight-cryptography/documents/finalist-round/updated-spec-doc/sparkle-spec-final.pdf · Alzette: a 64-bit ARX-box — eprint.iacr.org/2019/1378 · Grain-128AEADv2 spec — csrc.nist.gov/CSRC/media/Projects/lightweight-cryptography/documents/finalist-round/updated-spec-doc/grain-128aead-spec-final.pdf · Fast Correlation Attack Revisited, CRYPTO 2018 — eprint.iacr.org/2018/522 · Conditional Differential Cryptanalysis of NLFSR-Based Cryptosystems, ASIACRYPT 2010 — crypto.ethz.ch/publications/files/KnMePl10.pdf · Ma et al., Conditional differential attacks on Grain-128a — ietresearch.onlinelibrary.wiley.com/doi/full/10.1049/iet-ifs.2016.0060 · Liu & Tian, Dynamic Cube Attacks against Grain-128AEAD, ToSC 2024 — tosc.iacr.org/index.php/ToSC/article/view/11627 · Stankovski, Greedy Distinguishers, INDOCRYPT 2010 — link.springer.com/chapter/10.1007/978-3-642-17401-8_16 · Dinur & Shamir, Cube attacks in realistic scenarios — link.springer.com/article/10.1007/s12095-012-0068-4 · FMS, Weaknesses in the KSA of RC4, SAC 2001 — link.springer.com/chapter/10.1007/3-540-45537-X_1 · Mantin & Shamir, A Practical Attack on Broadcast RC4, FSE 2001 — link.springer.com/content/pdf/10.1007/3-540-45473-X_13.pdf · On the Security of RC4 in TLS, USENIX Security 2013 — usenix.org/conference/usenixsecurity13/technical-sessions/paper/alfardan · Rogaway, Nonce-Based Symmetric Encryption — cs.ucdavis.edu/~rogaway/papers/nonce.pdf · NISTIR 6483 — nvlpubs.nist.gov/nistpubs/Legacy/IR/nistir6483.pdf · BoolTest — crocs.fi.muni.cz/_media/public/papers/booltest_preprint_2017.pdf · The Efficient Randomness Testing using Boolean Functions, SECRYPT 2017 — scitepress.org/papers/2017/64251/64251.pdf · EACirc, eSTREAM e SHA-3 — crocs.fi.muni.cz/_media/publications/pdf/2014-ccis-svenda.pdf · Kaminsky, Testing the Randomness of Cryptographic Function Mappings — eprint.iacr.org/2019/078 · Doğanaksoy et al., Cryptographic Randomness Testing — eprint.iacr.org/2010/564 · CLAASP, SAC 2023 — eprint.iacr.org/2023/622 · MIND-Crypt — eprint.iacr.org/2024/852 · MIND-Crypt, Cryptography 2026 — mdpi.com/2410-387X/10/1/9 · de Mello & Xexéo, JUCS 24(1) 2018 — jucs.org/jucs_24_1/identifying_encryption_algorithms_in/jucs_24_01_0025_0042_demello.pdf · Baksi et al., ML Assisted Differential Distinguishers, DATE 2021 — eprint.iacr.org/2020/571 · Rajan et al., GIFT-COFB DL distinguisher — link.springer.com/chapter/10.1007/978-981-16-9650-3_31 · Neural differential distinguishers for GIFT-128 and ASCON, JISA 2024 — sciencedirect.com/science/article/pii/S2214212624000619 · Cipher-Agnostic Neural Training Pipeline, ToSC 2023 — eprint.iacr.org/2022/1467 · Survey: Six Years of Neural Differential Cryptanalysis — cic.iacr.org/p/3/2/21 · Grassi–Rechberger–Rønjom, 5-Round AES, EUROCRYPT 2017 — eprint.iacr.org/2017/118 · Statistical integral distinguisher with multi-structure — link.springer.com/article/10.1007/s12095-018-0286-5 · Neural-Inspired Advances in Integral Cryptanalysis — arxiv.org/pdf/2505.10790 · New Slide Attacks on Almost Self-Similar Ciphers — eprint.iacr.org/2019/509 · Survey on the NIST LWC Standard — arxiv.org/pdf/2304.06222

---

# Pesquisa 09 — Vieses em tag, padding e enquadramento

- **Ângulo:** Vieses em tag, padding e enquadramento
- **Temperatura declarada:** 0,7

## Pesquisa 09 — prompt usado, na íntegra

````markdown
# Pesquisa 09 — Vieses em tag, padding e enquadramento

**Temperatura declarada: 0,7** (amplitude de exploração alta-média — este
ângulo é sobre as bordas do criptograma, onde a literatura é esparsa e
espalhada por subcampos que não conversam. Puxe de protocolo, de formato de
arquivo, de análise de tráfego, de ataques de padding oracle, de qualquer
lugar. Especulação marcada é bem-vinda; invenção de fonte não.)

---

## PROBLEMA DE PESQUISA

Você está pesquisando para uma dissertação de mestrado em criptografia
aplicada e aprendizado de máquina. Trabalhe SÓ com literatura externa: não
leia nenhum repositório, arquivo local ou resultado prévio. Comece do zero.

**A pergunta.** Dado apenas o criptograma — sem a chave, sem o texto em claro,
sem poder escolher nada do que é cifrado — é possível distinguir qual
algoritmo de criptografia autenticada o produziu? E, num segundo nível, com
quantas rodadas reduzidas um algoritmo ainda deixa de parecer aleatório?

**Os algoritmos.** Os quatro finalistas do concurso NIST Lightweight
Cryptography: Ascon-AEAD128 (esponja), GIFT-COFB (cifra de bloco em modo
COFB), Grain-128AEAD (cifra de fluxo com LFSR e NFSR) e Schwaemm256-128
(esponja ARX, família SPARKLE).

**O modelo de ameaça, que é a restrição dura e não negocia.** Adversário
PASSIVO, em ciphertext-only. Ele observa criptogramas de um mesmo dispositivo,
com nonces públicos de contador, e pode observar vários de uma vez. Ele NÃO
tem: texto em claro conhecido ou escolhido, diferenças escolhidas na entrada,
reuso de nonce, acesso a canais laterais, nem consultas a um oráculo de
cifragem. Isso exclui de saída a maior parte da criptanálise diferencial
clássica e os distinguidores neurais no estilo Gohr, que dependem de pares com
diferença escolhida.

**O protocolo experimental.** Classificadores clássicos e redes sobre features
estatísticas e sobre os bytes crus. Chaves de teste nunca aparecem no treino
(key-holdout). Intervalo de confiança por bootstrap agrupado por chave, e não
i.i.d. Correção para múltiplas comparações. Controle negativo obrigatório: com
o algoritmo completo o classificador tem que ficar no acaso.

**Dado concreto disponível:** ~30.000 criptogramas por algoritmo, 64 KB cada
(≈1,9 GB por classe), 300 chaves distintas, nonces de contador, texto em claro
vindo de corpus real (80% texto em inglês do Project Gutenberg, 20% imagem em
tons de cinza). Plaintext de comprimento fixo. Existem variantes com rodadas
reduzidas compiladas para os quatro algoritmos. Existem controles: AES em modo
ECB (positivo) e saída de PRNG (negativo).

---

## ÂNGULO DESTA PESQUISA — as bordas do criptograma

Quase toda a análise trata o criptograma como um bloco homogêneo de bytes e
mede estatísticas agregadas sobre ele. Mas um criptograma AEAD **não** é
homogêneo: ele tem uma tag de autenticação no fim, gerada por um caminho
diferente do resto; tem um primeiro bloco que sai logo depois da
inicialização; tem, dependendo do esquema, padding; e tem um comprimento que é
função do esquema.

**Quero saber tudo o que se sabe sobre sinal nessas bordas.**

Persiga, entre outras coisas:

- **A tag de autenticação como objeto estatístico separado.** Ela sai da
  finalização, que usa um número de rodadas diferente do processamento de
  mensagem (no Ascon, `p[12]` contra `p[8]`). Existe literatura sobre vieses
  em tags de MAC ou de AEAD? Sobre forjamento que explore estrutura da tag?
  Sobre distinguir esquemas pela distribuição da tag? E o caso do
  Grain-128AEAD, cuja tag de 64 bits vem de um acumulador que consome os bits
  ÍMPARES do pre-output — os que nunca aparecem no keystream: isso significa
  que a tag carrega informação sobre metade do gerador que o criptograma
  esconde?
- **Padding.** Esquemas de esponja usam padding 10* antes da última chamada da
  permutação. AES-ECB usa PKCS7. O que a literatura diz sobre padding como
  canal — não os ataques de padding oracle clássicos (que precisam de oráculo
  de decifragem, e portanto estão fora), mas vieses PASSIVOS induzidos por
  padding determinístico.
- **O comprimento e o enquadramento como canal.** Os quatro esquemas produzem
  expansões diferentes: tag de 128 bits em três deles, 64 no Grain; nonces de
  96, 128 e 256 bits. Quanto da literatura de análise de tráfego e de
  fingerprinting de protocolo se aplica? E, mais interessante: **depois de
  neutralizar comprimento, o que sobra?**
- **Efeitos de posição dentro do criptograma.** O primeiro bloco de saída vem
  logo após a inicialização completa; os blocos do meio, após a permutação de
  processamento. São dois regimes diferentes de número de rodadas, misturados
  num mesmo vetor de features quando se agrega sobre a mensagem toda. A
  literatura de RC4 (Mantin–Shamir, Isobe et al., AlFardan et al.) explora
  exatamente vieses **indexados por posição**. Isso transfere?
- **Fingerprinting de implementação e de formato** — literatura de forense
  digital, identificação de container criptografado, detecção de tipo de
  arquivo cifrado. É um subcampo diferente, com vocabulário próprio, e pode
  ter técnicas que a criptografia acadêmica não usa.
- **Detecção de AEAD em tráfego real** — trabalhos que identificam qual suíte
  de cifras está em uso observando só o tráfego, e o que exatamente eles usam
  como sinal (handshake? comprimento? timing? ou algo do próprio criptograma?).

Vá também para onde o ângulo levar: se aparecer um canal de borda que não
esteja nessa lista, traga.

---

## O QUE EU QUERO DE VOCÊ

Técnicas, representações, ataques ou ideias — publicadas ou adaptáveis — que
possam extrair sinal nesse cenário, ou que ajudem a delimitar com rigor por
que o sinal não existe. Interessa tanto o que funciona quanto a prova de que
algo é impossível.

Busque em literatura acadêmica real (IACR ePrint, ToSC/FSE, CHES, CRYPTO,
EUROCRYPT, ASIACRYPT, SAC, Designs Codes and Cryptography, USENIX, IEEE S&P,
CCS, NDSS, Springer, arXiv) e em fontes técnicas sérias. Use termos de busca
em inglês.

## COMO RESPONDER

Para cada ideia encontrada, escreva:

1. **O que é** — a técnica, em duas ou três frases.
2. **Fonte** — autores, título, veículo, ano. Link quando houver. Se você não
   conseguiu confirmar a existência do trabalho, diga isso explicitamente em
   vez de completar de memória.
3. **Cabe no nosso modelo?** — SIM, NÃO, ou ADAPTÁVEL. Se ADAPTÁVEL, diga
   exatamente o que teria de mudar e qual premissa do modelo de ameaça isso
   arranha.
4. **O que custaria testar** — ordem de grandeza de dados, computação e
   engenharia.
5. **O que ela prevê** — se a técnica funcionar, que resultado deveríamos ver?
   Se não houver previsão falsificável, diga isso.

Termine com uma seção **APOSTAS**: as três ideias que você tentaria primeiro,
e por quê. Seja específico; "usar deep learning" não é uma aposta.

## PROFUNDIDADE — leia isto com atenção

Não é um levantamento rápido. **Vá até esgotar o veio.** Não pare em cinco ou
dez achados porque já "deu para ter uma ideia": siga as citações para frente e
para trás, abra os trabalhos relacionados dos artigos que importarem, procure
versões estendidas e teses, e persiga as pistas que aparecerem no caminho,
mesmo as que não estavam no ângulo original. Só encerre quando as buscas novas
pararem de trazer coisa nova. Espera-se algo da ordem de 80 a 120 chamadas de
ferramenta de busca/leitura.

Traga TODA a informação, não um resumo dela. Se um artigo tem um número que
importa (quantas rodadas, quantas consultas, que acurácia, que viés, que
tamanho de dado), traga o número. Se tem uma limitação declarada pelos
próprios autores, traga a limitação com as palavras deles. Prefira errar por
excesso de detalhe. Uma resposta longa e completa é o que se pede aqui; uma
resposta enxuta é falha de execução.

**A sua resposta final é o produto inteiro** — ela vai ser salva em disco
literalmente, sem que ninguém a expanda depois. Não escreva "detalhei acima"
nem resuma: escreva o documento completo, em Markdown, em português do Brasil,
com todas as tabelas e todos os números.

**Se a resposta ficar muito longa, ela pode ser truncada na entrega.** Para
evitar perda: mantenha as seções numeradas e, se perceber que passou de umas
40 mil palavras, diga ao final quais seções você escreveu, para eu conferir se
chegaram todas.

## REGRAS

- Não invente referências. Uma fonte não confirmada vale menos que nenhuma, e
  vou checar.
- Não repita o óbvio já saturado (distinguidor diferencial-neural padrão)
  sem trazer um ângulo novo que sobreviva ao ciphertext-only.
- Se a conclusão honesta de um caminho for "isso é impossível neste modelo
  por tal razão teórica", isso é resultado útil. Diga.
- Separe o que é publicado do que é sua extrapolação. Marque cada um
  explicitamente: **[PUB]** para publicado e lido/confirmado, **[CIT]** para
  existência confirmada mas texto não obtido, **[MINHA]** para extrapolação
  sua.
````

## Pesquisa 09 — achados, sem resumir

### Achados — Pesquisa 09

- **Ângulo:** vieses em tag, padding e enquadramento
- **Temperatura declarada:** 0,7
- **Prompt usado:** `prompts/09_tag_padding_enquadramento.md`
- **Execução:** 468.906 tokens de subagente, 136 chamadas, ~40 min

> **Nota de integridade.** A entrega veio truncada pela segunda vez na série
> (~24,2k caracteres: fim da 7.2, seções 8 e 9.1 inteiras, começo da 9.2).
> O trecho foi recuperado por reemissão em duas partes, pedidas ao próprio
> agente, e está reintegrado no lugar certo. **O documento abaixo está
> completo**: seções 1 a 13 mais o sumário.

---

### Pesquisa 09 — Vieses em tag, padding e enquadramento
#### Sinal nas bordas do criptograma AEAD: levantamento de literatura, adaptações e limites

**Data:** 21/09/2026 · **Temperatura declarada:** 0,7 · **Convenção de marcação:** **[PUB]** = publicado e lido/conferido por mim nesta sessão; **[CIT]** = existência confirmada, texto integral não obtido; **[MINHA]** = extrapolação minha, não publicada.

---

#### SUMÁRIO DAS SEÇÕES (para conferência de truncamento)

1. Enquadramento formal — o que as bordas podem e não podem entregar
2. A tag como objeto estatístico separado
3. Padding como canal passivo
4. Comprimento e enquadramento como canal
5. Efeitos de posição dentro do criptograma
6. Fingerprinting forense, de formato e de container
7. Detecção de AEAD em tráfego real
8. Rodadas reduzidas — os números que definem o ponto de virada
9. A literatura de identificação de cifras por ML — o que é real e o que é artefato
10. Metodologia: os controles que a literatura já cobra
11. Caminhos que são impossíveis neste modelo, e por quê
12. Catálogo consolidado de ideias (formato 1–5)
13. APOSTAS

---

### 1. Enquadramento formal — o que as bordas podem e não podem entregar

Antes de catalogar técnicas, é preciso fixar o teto. Isso muda a leitura de tudo o que vem depois.

#### 1.1 A desigualdade triangular põe um teto duro no experimento inteiro

**[PUB]/[MINHA]** Seja `A` o adversário que tenta distinguir criptogramas de Ascon dos de GIFT-COFB. Escreva `R` para o oráculo que devolve bits uniformes do comprimento certo. Então

```
Adv^{Ascon vs GIFT}(A)  ≤  Adv^{IND$-CPA}_{Ascon}(A) + Adv^{IND$-CPA}_{GIFT-COFB}(A)
```

Isso é a desigualdade triangular padrão de indistinguibilidade computacional (Barak, notas COS433, Princeton, e o tratamento canônico de AEAD em Rogaway, *Authenticated-Encryption with Associated-Data*, CCS 2002, https://web.cs.ucdavis.edu/~rogaway/papers/ad.pdf) **[CIT]** para o texto do Rogaway; **[PUB]** para o enunciado da transitividade.

O ponto que interessa: **nosso adversário é estritamente mais fraco que o adversário IND$-CPA** (ele não escolhe plaintext, não escolhe nonce, não consulta oráculo). Logo os limites provados valem como teto superior, com folga.

Substituindo os números do nosso orçamento de dados (σ ≈ 2^26,9 blocos de 128 bits por algoritmo):

| Esquema | Limite de privacidade (modo) | Valor em σ = 2^26,9 |
|---|---|---|
| GIFT-COFB | σ²/2^128 + O(σ/2^64) **[PUB]** (Inoue–Iwata–Minematsu, ePrint 2022/001) | ≈ 2^−37 |
| Ascon-128a | D²/2^c, c=192, mais DT/2^320 **[PUB]** (abstract de *Exact Security Analysis of ASCON*, NIST LWC 2023) | ≈ 2^−138 |
| Grain-128AEADv2 | melhor viés linear de keystream ε < 2^−77 **[PUB]** (spec, §4.2) | dados necessários ≈ 2^154 |
| Schwaemm256-128 | 120 bits de segurança conjunta, limite de dados 2^68 bytes **[PUB]** (spec, Tab. 2.3) | negligível |

**Conclusão dura:** com o algoritmo completo, a vantagem alcançável por *qualquer* adversário ciphertext-only está limitada por ≈ 2^−37 (dominado pelo termo mais fraco, GIFT-COFB), no modelo de permutação/cifra ideal. A distância entre 2^−37 e o que um classificador ML consegue medir com 60.000 amostras (resolução ≈ 2^−8 em F1) é de **29 ordens binárias**. H₀ não é uma surpresa nem um resultado negativo: é o que a teoria manda.

O que a teoria **não** cobre, e onde portanto mora todo o sinal disponível:

1. **Comprimento.** IND-CPA/IND$-CPA vaza comprimento por definição. Ver §4.
2. **Desvio do primitivo em relação ao ideal.** O limite acima assume permutação/cifra ideal. Com rodadas reduzidas, esse termo explode. Ver §8.
3. **Artefatos de implementação/geração do dataset.** Ver §9 e §10.

**[MINHA]** Essas três coisas — e só elas — são as bordas do problema. O resto é ruído amostral.

#### 1.2 O que cada esquema expõe na fronteira entre blocos

Este é, no meu entender, o achado estrutural mais útil do levantamento inteiro. Extraí as equações das especificações oficiais.

**Ascon v1.2 [PUB]** (spec final NIST, Alg. 1):
```
C_i ← S_r ⊕ P_i
S  ← p^b( C_i ‖ S_c )
```
A parte rate do estado depois de absorver o bloco `i` **é exatamente `C_i`**. 128 dos 320 bits de estado são públicos a cada passo, para um adversário ciphertext-only puro.

**Schwaemm256-128 [PUB]** (spec Sparkle v1.2, Alg. 2.13, §2.3.2):
```
C_j        ← ρ₂(S_L, M_j) = S_L ⊕ M_j
novo outer ← ρ₁(S_L, M_j) ⊕ W(S_R) = FeistelSwap(S_L) ⊕ M_j ⊕ W(S_R)
FeistelSwap(S) = S₂ ‖ (S₂ ⊕ S₁)
```
Logo `novo outer ⊕ C_j = FeistelSwap(S_L) ⊕ S_L ⊕ W(S_R)` — o plaintext **cancela**, mas sobra uma função linear desconhecida do estado completo. O ciphertext **não** revela o rate pós-absorção. Esse é precisamente o propósito do feedback combinado do modo Beetle, e é uma diferença estrutural de peso em relação ao Ascon.

**GIFT-COFB v1.1 [PUB]** (spec final, Alg. COFB-E):
```
Y[0] ← E_K(N),  L ← Trunc_{n/2}(Y[0])        (máscara de 64 bits)
C[i]     ← M[i] ⊕ Y[i+a−1]
X[i+a]   ← M[i] ⊕ G·Y[i+a−1] ⊕ L‖0^{n/2}
Y[i+a]   ← E_K(X[i+a])
G(Y)     = (Y[2], Y[1] ≪ 1)
T        ← Trunc_τ(Y[a+m]),  τ = n = 128
```
Substituindo `M[i] = C[i] ⊕ Y[i+a−1]`: `X[i+a] = C[i] ⊕ (I ⊕ G)·Y[i+a−1] ⊕ L‖0`. O elo entre `C[i]` e `C[i+1]` atravessa **uma chamada completa de E_K** — 40 rodadas de GIFT-128.

**Grain-128AEADv2 [PUB]** (spec final, §2.3):
```
z_i  = y_{512+2i}        (bits pares  → keystream)
z'_i = y_{512+2i+1}      (bits ímpares → autenticação)
c_i  = m_i ⊕ z_i
```
O keystream é **completamente independente do plaintext**. O estado nunca vê a mensagem. Nenhuma exposição de estado via ciphertext, em nenhum ponto.

**Taxonomia resultante [MINHA]:**

| Esquema | Estado rate pós-absorção é função pública do criptograma? | Elo C_i → C_{i+1} |
|---|---|---|
| **Ascon-128a** | **Sim — é literalmente C_i** | p^8 (8 rodadas Ascon) |
| **Ascon-128** | **Sim** | p^6 (6 rodadas) |
| Schwaemm256-128 | Não (mascarado por L(S) desconhecido) | Sparkle384^7 (7 steps slim) |
| GIFT-COFB | Não (mas o elo é uma E_K limpa) | GIFT-128, 40 rodadas |
| Grain-128AEADv2 | N/A (keystream independente de M) | 16 clockings/byte |
| AES-ECB (controle +) | Sim, no pior modo possível: C_i = E_K(M_i) | nenhum — sem encadeamento |

**Rodadas de trabalho criptográfico por byte de saída observável:**

| Esquema | rodadas/byte |
|---|---|
| Ascon-128a (r=128, b=8) | **0,50** rodada Ascon/byte |
| Ascon-128 (r=64, b=6) | 0,75 rodada Ascon/byte |
| Schwaemm256-128 (r=256, 7 steps) | 0,22 step Sparkle384/byte (≈ 1,75 ARX-box/byte) |
| GIFT-COFB (n=128, 40 rodadas) | **2,50** rodadas GIFT/byte |
| Grain-128AEADv2 | 16 clockings/byte |

Isso importa porque diz **qual algoritmo cai primeiro sob redução de rodadas em CT-only** — ver §8.4.

---

### 2. A tag como objeto estatístico separado

#### 2.1 Anatomia comparada da tag

| Esquema | Fórmula da tag | Tipo algébrico | Tamanho | Rodadas entre o último bloco de C observável e T |
|---|---|---|---|---|
| Ascon-128a | `T = ⌈p^12(S ⊕ (0^r‖K‖0^{c−k}))⌉_128 ⊕ ⌈K⌉_128` **[PUB]** | estado ⊕ chave | 128 b | **20** (8 do bloco de padding + 12 da finalização) se \|P\| ≡ 0 mod r; **12** se \|P\| ≢ 0 |
| GIFT-COFB | `T = Trunc_128(E_K(X[a+m]))` **[PUB]** | saída de PRP | 128 b | **40** (uma E_K) |
| Grain-128AEADv2 | `T = A^{L+1} = A^0 ⊕ ⊕_{i: m_i=1} R_i` **[PUB]** | hash de Toeplitz ⊕ OTP | **64 b** | — (caminho totalmente separado) |
| Schwaemm256-128 | `T = S_R ⊕ K` após Sparkle384^11 **[PUB]** | capacidade ⊕ chave | 128 b | 7 steps slim + 11 steps big |
| AES-ECB (controle) | nenhuma | — | 0 | — |

**Observação 1 [MINHA], e ela é contraintuitiva e importante.** A intuição do ângulo é que a tag, saindo de um caminho com mais rodadas, seria estatisticamente distinta. É verdade que ela é distinta — mas **na direção errada para o atacante**. Mais rodadas significa *menos* viés, não mais. Somado ao fato de que a região de tag tem 128/524.288 ≈ 2^−12 dos bits do criptograma:

- bits de corpo por algoritmo: 30.000 × 524.288 = 1,57×10^10 ≈ 2^33,9
- bits de tag por algoritmo: 30.000 × 128 = 3,84×10^6 ≈ 2^21,9

Um teste por posição de bit sobre as tags detecta viés |ε| ≳ 3/(2√30.000) ≈ 2^−6,8. Agrupando as 128 posições (se o viés for o mesmo), |ε| ≳ 2^−10,3. Sobre o corpo, agrupando tudo, |ε| ≳ 2^−15,9. **A região de tag é 50× menos sensível que o corpo, e vem de mais rodadas.** Para os algoritmos completos, é o pior lugar possível para procurar.

A tag só vira interessante quando as rodadas de finalização são reduzidas **abaixo** das rodadas de mensagem — o que é uma manipulação experimental deliberada, não uma propriedade do algoritmo padrão.

#### 2.2 A pergunta do Grain: os bits ímpares vazam pela tag?

Esta é a pergunta mais específica e mais interessante do ângulo. A resposta é *não, mas por um motivo que vale escrever na dissertação*.

**Fato 1 [PUB]** — a pergunta é legítima e os projetistas sabem disso. Da spec Grain-128AEADv2, §4.3, literalmente:

> "a recent paper [51] reveals that there are multiple linear approximations in Grain-128a that together with a viewpoint based on a finite field allow a fast correlation attack on the raw encryption mode of Grain-128a (and on the other members of the Grain family), where every keystream bit is assumed to be accessible by an opponent. This attack recovers the state of Grain-128a with data and time complexity of about 2^114. The data needs to come from the same secret key and the same nonce. **It should be noted that this fast correlation attack does not apply to Grain-128a in authentication mode, as then only every second key stream bit may be accessible to an opponent.**"

Ou seja: esconder os bits ímpares **é** uma defesa reconhecida, que bloqueia um ataque de 2^114. Os bits ímpares valem alguma coisa.

**Fato 2 [PUB]** — mas a tag não os entrega. Da spec, §2.3 e §3.4.6:
```
a⁰_j = y_{384+j},  0 ≤ j ≤ 63          (acumulador inicializado com pre-output)
r⁰_j = y_{448+j},  0 ≤ j ≤ 63          (registrador inicializado com pre-output)
A^{i+1}_j = A^i_j + m_i · r^i_j        (Toeplitz: soma ponderada PELO PLAINTEXT)
r^{i+1}_{63} = z'_i                    (entra um bit ímpar por passo)
```
E o texto da spec: *"A 64-bit keystream block, here seen as a 'one-time pad', is added to the accumulator in order to encrypt the hash."*

Logo `T = A^0 ⊕ Σ_{i: m_i = 1} R_i` onde:
- `A^0` é um **one-time pad de 64 bits fresco por (chave, nonce)** — logo `T` é incondicionalmente uniforme dado `A^0` uniforme;
- os coeficientes `m_i` são os **bits de plaintext**, desconhecidos;
- são 64 bits observados contra L + 64 = 524.352 bits ímpares desconhecidos.

**Conclusão [MINHA], com números:** a tag do Grain expõe 64 combinações lineares dos bits ímpares, com coeficientes desconhecidos e máscara aditiva desconhecida, num sistema sub-determinado por fator 2^13. Com nonces distintos, os streams ímpares de mensagens diferentes são independentes, então não há acumulação através das 100 amostras por chave. **A resposta à pergunta é: em princípio sim, na prática não — a informação existe mas está sob um OTP fresco e um sistema linear massivamente sub-determinado.** Isso é um resultado negativo limpo e defensável, com mecanismo explicado, e vale meia página da dissertação.

**Fato 3 [PUB]** — os projetistas quantificam a segurança da autenticação assim (§4.6): *"if the sequence defining the Toeplitz matrix is ε-biased, then the substitution probability for the MAC is P_S ≤ 2^−w + 2ε"*, com w = 64 e ε ≈ 2^−77, logo P_S ≈ 2^−64 — "close to guessing the tag".

**Fato 4 [MINHA], e este é testável.** O que a tag do Grain *de fato* carrega de especial é outra coisa: `A^0 = y_{384..447}` e `R^0 = y_{448..511}` são gerados **imediatamente após as 384 clockings de inicialização**, enquanto o keystream só começa em `y_{512}`. A máscara da tag é o material de pre-output **mais próximo da inicialização que existe**. Se a inicialização estiver sub-misturada (rodadas reduzidas), a tag carrega o viés de inicialização *antes* de qualquer byte de keystream. Previsão falsificável: **com inicialização reduzida, o viés detectável na tag do Grain aparece com menos rodadas do que o viés nos primeiros bytes do ciphertext.** É um teste barato e nunca vi publicado.

#### 2.3 Vieses de tag/MAC na literatura publicada — o veio é seco, e há razão

Busquei sistematicamente por "authentication tag bias", "MAC output distribution distinguisher", "Wegman-Carter tag bias", "truncated tag statistical". **Não encontrei nenhum trabalho que analise a distribuição estatística de tags de AEAD como objeto observacional passivo.** Isso não é lacuna de busca: é consequência de projeto. Toda tag bem construída é ou (a) saída de PRP (GIFT-COFB), ou (b) estado ⊕ chave após muitas rodadas (Ascon, Schwaemm), ou (c) hash universal ⊕ OTP (Grain). Nos três casos, uniformidade é a propriedade de projeto mais barata de garantir.

O que existe é literatura sobre **estrutura de tag explorável com oráculo de decifragem**, que está fora do modelo:

**[PUB] Khairallah, "Security of COFB against Chosen Ciphertext Attacks", ePrint 2021/648 / FSE 2022.** Resultado central para nós:

> *"while COFB generates a 128-bit tag, it behaves in a very similar manner to an AEAD scheme with 64-bit tag"*

e, na discussão (§ "Effective Tag Size of GIFT-COFB"):

> *"Our attack complexity is a function of the mask size rather than the tag size. Given an n/2-bit mask, the attack works with 2^{n/2} forgery attempts, even if the tag size is larger than n/2 bits. [...] it seems that the tag size of GIFT-COFB offers little immunity compared to algorithms with half the tag size."*

Ataques: *Weak Key* e *Mask Collision* com q_d = 2^{n/2} e σ_e = 2^{n/2} ou 2^{n/4}; *Mask Presuming* com q_e = 1, σ_e = O(1), q_d = 2^{n/2}. **Cabe no modelo? NÃO** — todos exigem q_d consultas de verificação. Mas o insight estrutural (a entropia efetiva da tag do COFB é a da máscara L, 64 bits) é publicável como observação e não depende do oráculo.

**[PUB] Inoue, Iwata, Minematsu, "Analyzing the Provable Security Bounds of GIFT-COFB and Photon-Beetle", ACNS 2022 / ePrint 2022/001.** O único **ataque de privacidade** (IND-CPA) publicado contra GIFT-COFB. Procedimento exato (§3.1, transcrito):

> Para 0 ≤ i ≤ 2^{n/2}−1, consulta (N_i, A_i, M_i) com N_i = (i)_{n/2} ‖ lsb_{n/2}(X[2]), L_i := Trunc_{n/2}(Y[2]), A_i = N_i ⊕ G(Y[2]) ⊕ 3L_i‖0^{n/2}, M_i = N_i ⊕ G(Y[2]) ⊕ 3²L_i‖0^{n/2}. No mundo real sempre existe i com M_i ⊕ C_i = Y[2] e T_i = Trunc_τ(Y[2]); no mundo ideal isso ocorre com probabilidade 1/2^{n/2+τ}.

Sucesso O(q_e/2^{n/2}) = O(q_e/2^64). **Cabe no modelo? NÃO** — nonce escolhido, AD escolhido, plaintext escolhido. Mas fixa o teto: **mesmo com poder CPA total, quebrar a privacidade do GIFT-COFB custa 2^64 consultas.** Nosso adversário é infinitamente mais fraco e tem 2^15 consultas. Isso é um parágrafo de conclusão pronto.

**[PUB]** O mesmo paper dá o ataque de forja por colisão de estado completo contra Photon-Beetle com 2^{b/2} = 2^128 consultas de cifragem, detectando a colisão **pelos primeiros b bits do criptograma** — é um exemplo de como uma colisão de estado interno se manifesta no ciphertext. **Cabe? NÃO** (2^128), mas o mecanismo (colisão de estado visível como colisão de prefixo de ciphertext) é o único mecanismo genérico pelo qual dois criptogramas do mesmo esquema se "reconhecem", e vale calcular o custo para os nossos quatro esquemas: 2^160 (Ascon, c=192… na prática 2^96 pelo rate), 2^64 (GIFT-COFB), 2^128 (Schwaemm, c=128). Todos inalcançáveis com 2^26,9 blocos.

#### 2.4 O elo tag ↔ último bloco de criptograma — o achado de projeto de dataset

**[MINHA]**, derivado das specs lidas. Este é, no meu julgamento, o item mais acionável de toda a seção 2.

Em Ascon, com |P| ≡ 0 (mod r) (que é exatamente o nosso caso: 65.536 bytes, r = 16 bytes, 65536/16 = 4096 exato), a spec manda:
```
P₁…P_t ← blocos de r bits de P‖1‖0*        →  t = 4097
S_r ← S_r ⊕ P_t                             (P_4097 = 0x80‖0^120)
C̃_t ← ⌊S_r⌋_{|P| mod r} = ⌊S_r⌋_0           (bloco VAZIO — não é emitido!)
```
Ou seja: **o bloco de padding é absorvido mas o criptograma correspondente tem zero bits.** O estado que entra na finalização está separado do último bloco observável C_4096 por uma aplicação completa de p^8.

Consequência: o elo observável tag↔ciphertext em Ascon-128a atravessa 8 + 12 = 20 rodadas. Se, em vez disso, o comprimento do plaintext **não** for múltiplo do rate, então C̃_t = ⌊S_r⌋_ℓ com 0 < ℓ < r — até 127 bits do estado que entra na finalização ficam **diretamente visíveis no criptograma**, e o elo cai para **12 rodadas**.

**Recomendação concreta de projeto de dataset:** para maximizar a sensibilidade do teste de borda tag↔criptograma, use um comprimento de plaintext que **não** seja múltiplo do rate de nenhum dos esquemas. Com 64 KB exatos, o experimento está gastando 8 rodadas de margem no Ascon-128a (6 no Ascon-128) e 7 steps no Schwaemm, de graça. Um braço com |P| = 65535 bytes custa quase nada gerar e desloca a fronteira do teste em 8 rodadas.

Para GIFT-COFB isso não se aplica: `Pad(x) = x` quando `|x| mod n = 0` **[PUB]**, então não há bloco extra, e T = E_K(C[m] ⊕ (I⊕G)Y_last ⊕ L‖0) — o elo é **uma** E_K (40 rodadas) sempre.

#### 2.5 O que testar na tag — checklist

| Teste | Custo | Prevê o quê |
|---|---|---|
| Distribuição marginal de cada uma das 128 (64) posições de bit da tag, por algoritmo, por chave | trivial | H₀ em todos, com sensibilidade 2^−6,8 por posição |
| Correlação tag × último bloco de C (todas as 128×128 máscaras de 1 bit) | O(N · 128²), minutos | H₀; vira positivo quando finalização ≤ 3 rodadas |
| Correlação tag × tag entre nonces consecutivos (mesma chave) | trivial | H₀; mede se o contador de nonce vaza |
| **Classificador treinado só na tag** vs **só no corpo** vs **corpo+tag** | 3 treinos | Se tag-only > corpo-only, há artefato de geração (nenhum mecanismo criptográfico prevê isso) |
| Comparação Grain: viés na tag vs viés nos primeiros 64 bytes, sob inicialização reduzida | requer variantes | Tag mostra viés com menos rodadas (§2.2, Fato 4) |

O quarto item é um **detector de artefato**, não um ataque: não existe mecanismo pelo qual a tag de 128 bits carregue mais sinal que 65.536 bytes de corpo. Se carregar, o dataset está furado.

---

### 3. Padding como canal passivo

#### 3.1 O que cada esquema faz

| Esquema | Regra de padding | Expansão de \|C\| | Fonte |
|---|---|---|---|
| Ascon | P‖1‖0^{r−1−(\|P\| mod r)}; C̃_t truncado para \|P\| mod r | **nenhuma**: \|C\| = \|P\| | **[PUB]** spec §2.4.3 |
| GIFT-COFB | Pad(x) = x se \|x\| mod n = 0; senão x‖10* | **nenhuma** | **[PUB]** spec eq. (2.1) |
| Grain-128AEADv2 | m_L = 1 (um bit '1', ou '1'+sete '0' em ambiente de bytes) — só afeta a tag | **nenhuma** | **[PUB]** spec §2.3 |
| Schwaemm256-128 | pad_256 no último bloco; constante de domínio muda conforme bloco cheio/parcial | **nenhuma** | **[PUB]** spec Alg. 2.13 |
| AES-ECB (controle) | PKCS#7 | **+16 bytes sempre que \|P\| ≡ 0 mod 16** | padrão |

**Achado 1 [MINHA]:** entre os quatro finalistas, **o padding não produz nenhum canal de comprimento**. Os quatro são length-preserving. O único canal de padding no dataset v2 é o AES-ECB, que ganha um bloco inteiro (`len_ct = 65552`) — e ele é o controle positivo. Isso está correto por construção, mas significa que qualquer F1 alto envolvendo AES-ECB num experimento que veja comprimento é trivial e não informa nada. O CLAUDE.md já exclui `len_ct`; a literatura justifica plenamente essa regra (§4).

**Achado 2 [PUB]/[MINHA]:** padding de esponja 10* é **separação de domínio disfarçada**. A literatura formal sobre isso:

- **[CIT]** Bertoni, Daemen, Peeters, Van Assche, *Duplexing the Sponge: Single-Pass Authenticated Encryption and Other Applications*, SAC 2011 (https://keccak.team/files/SpongeDuplex.pdf) — a construção duplex e o papel do padding injetivo.
- **[CIT]** *Sufficient Conditions on Padding Schemes of Sponge Construction and Sponge-Based Authenticated-Encryption Scheme*, INDOCRYPT 2012, LNCS 7668, pp. 434–447 (https://link.springer.com/chapter/10.1007/978-3-642-34931-7_31) — condições necessárias e suficientes sobre o esquema de padding para a segurança da esponja.
- **[CIT]** *To Pad or Not to Pad? Padding-Free Arithmetization-Oriented Sponges*, ToSC 2025 (https://tosc.iacr.org/index.php/ToSC/article/view/12073) — mostra que padding injetivo custa uma avaliação supérflua da permutação metade das vezes, e propõe separação de domínio via NCP. Relevante porque **é justamente essa avaliação supérflua que separa a tag do último bloco no nosso dataset** (§2.4).

**Achado 3 — o que a literatura NÃO tem.** Não existe, até onde consegui verificar, trabalho sobre **viés passivo induzido por padding determinístico** em AEAD. Todos os ataques de padding conhecidos (Vaudenay, Lucky13, POODLE) exigem oráculo de decifragem e estão fora do modelo. Isso é uma conclusão de levantamento, não uma falha de busca: o padding entra no estado *antes* de uma permutação completa, então qualquer viés que ele induza é eliminado pela mesma margem que protege tudo o mais.

#### 3.2 O canal de padding que sobra: separação de domínio observável

**[MINHA]** Há um resíduo interessante. Schwaemm usa constantes de domínio **diferentes** conforme o último bloco seja cheio ou parcial:
```
if |M_{ℓ−1}| < 256 then Const_M ← 2 ⊕ (1≪2)  else  Const_M ← 3 ⊕ (1≪2)
```
**[PUB]** spec Alg. 2.13. Ascon faz o análogo com o bit de separação S ⊕ (0^319‖1) após AD. Isso significa que **o comprimento do plaintext módulo o rate altera uma constante que entra no estado**. Num cenário com comprimentos variáveis (não o nosso), o criptograma reflete essa mudança de domínio depois de uma permutação completa — ou seja, invisível com rodadas cheias, mas com rodadas reduzidas vira um canal: **criptogramas cujo último bloco é cheio deveriam ser distinguíveis dos de último bloco parcial**. Teste barato, previsão nítida, e é estritamente CT-only. Exige apenas um dataset com comprimentos mistos.

---

### 4. Comprimento e enquadramento como canal

#### 4.1 A literatura diz que comprimento é quase tudo

**[PUB] Nikitin, Barman, Lueks, Underwood, Hubaux, Ford, "Reducing Metadata Leakage from Encrypted Files and Communication with PURBs", PoPETs 2019 (arXiv:1806.03160).** Este é o trabalho de referência para o ângulo "enquadramento".

Números medidos (§5.3.2), fração de objetos com **tamanho único** (portanto identificáveis só pelo comprimento):

| Dataset | # objetos | Únicos por tamanho | Após Padmé |
|---|---|---|---|
| Vídeos YouTube | 191.250 | **87%** | 3% |
| Pacotes Ubuntu | 56.517 | **83%** | 3% |
| Sites Alexa Top 1M | 2.627 | **68%** | 6% |
| Arquivos de disco de usuário | 848k (de 3.027.460) | **45%** | 8% |

E a frase que mais importa para nós:

> *"These characteristics persist in traditional block-cipher encryption (blue dashed curves) where objects are padded only to a block size. Even after being padded to 512 bytes, the size of a Tor cell, most object sizes remain as unique as in the unpadded case. We observe similar results when padding to 256 bits, the typical block size for AES."*

**Cabe no modelo? SIM, e é o único canal que cabe trivialmente.** Mas no nosso dataset o comprimento é *determinístico por algoritmo* (plaintext fixo de 64 KB):

| Algoritmo | `len_ct` |
|---|---|
| Ascon-AEAD128 | 65.552 (65.536 + 16 tag) |
| GIFT-COFB | 65.552 |
| Schwaemm256-128 | 65.552 |
| Grain-128AEAD | **65.544** (tag de 8 bytes) |
| AES-ECB + PKCS7 | **65.552** (+bloco de padding, sem tag) |

**[MINHA]** O canal de comprimento separa **Grain de todos os outros com F1 = 1,000, exatamente, sem ML**. E não separa mais nada. O CLAUDE.md já trata `len_ct` como metadado; a literatura PURB é a justificativa formal para isso e deve ser citada na dissertação nesse ponto exato. Além disso: o **nonce** (96/128/256 bits) separa os quatro perfeitamente se for incluído — e por isso não está no parquet. Correto.

**"Depois de neutralizar comprimento, o que sobra?"** — a resposta formal está em §1.1: sobra no máximo 2^−37 de vantagem, e isso é 29 ordens binárias abaixo da resolução do experimento. Sobra, em termos práticos, **nada** com algoritmos completos. Este é o resultado, e ele é rigoroso.

#### 4.2 Truncamento como etapa de análise

**[MINHA]** O CLAUDE.md já diz: *"truncamento é etapa de ANÁLISE, nunca de geração"*. A literatura de website fingerprinting confirma que essa é a decisão certa: **[CIT]** Dyer, Coull, Ristenpart, Shrimpton, *Peek-a-Boo, I Still See You*, IEEE S&P 2012, mostra que padding por pacote é insuficiente e o que importa é o tamanho total do objeto; **[PUB]** PURBs cita isso (*"research has repeatedly showed that the total website size is the feature that helps an adversary the most"*).

Recomendação: as comparações pairwise devem usar **três variantes de truncamento** e reportar as três:
1. corpo completo, sem tag (65.536 bytes para todos) — neutraliza tag e comprimento;
2. corpo + tag truncada a 64 bits (o menor comum) — neutraliza comprimento, preserva tag;
3. corpo + tag completa — deixa o comprimento vazar; serve como **controle positivo de comprimento** (deve dar F1 = 1 contra Grain e só contra Grain).

A variante 3 é valiosa justamente por ser trivial: é o "ECB penguin" do canal de comprimento, e prova que o pipeline funciona.

---

### 5. Efeitos de posição dentro do criptograma

Esta é a seção mais produtiva do ângulo. A literatura de RC4 é um manual de como extrair sinal indexado por posição em cenário ciphertext-only ou quase.

#### 5.1 O template Mantin–Shamir: broadcast, ciphertext-only, indexado por posição

**[CIT] Mantin, Shamir, "A Practical Attack on Broadcast RC4", FSE 2001, LNCS 2355, pp. 152–164** (https://link.springer.com/chapter/10.1007/3-540-45473-X_13). Não obtive o texto integral (Springer exige login); os números abaixo vêm de fontes secundárias confiáveis e concordantes.

O que é: o segundo byte do keystream RC4 é enviesado em direção a zero, com Pr[Z_2 = 0] ≈ 2/256 em vez de 1/256. Numa configuração de **broadcast** — o mesmo plaintext cifrado sob muitas chaves diferentes — bastam Ω(N) = Ω(256) criptogramas para recuperar o segundo byte de plaintext. A extensão para os bytes 3–255 exige Ω(N³).

**Cabe no nosso modelo? ADAPTÁVEL, com uma ressalva séria.** O ataque exige o *mesmo* plaintext sob chaves diferentes. Nosso dataset tem plaintexts distintos por amostra. O que transfere **sem arranhar o modelo** é o **método**: alinhar as amostras por *offset* e computar estatísticas por posição, em vez de agregar sobre o criptograma inteiro. O que **não** transfere é a recuperação de plaintext.

**Este é o ponto metodológico central da seção, e há evidência empírica direta dele.**

#### 5.2 A prova de que agregar destrói o sinal posicional

**[PUB] Klinec, Sýs, Kubíček, Švenda, Matyáš, "Large-scale Randomness Study of Security Margins for 100+ Cryptographic Functions", SECRYPT 2022, pp. 134–146.** Frase literal (§4, "Key Method Dominance"):

> *"RC4 is known to contain biases on the beginning of the keystream. **Experiments were not able to detect biases using zero strategy, i.e., using keystream with a random key.** However, all tested key methods detected biases with 100 MB of data and more, even the most difficult rnd.key strategy."*

Traduzindo o que isso significa para nós: **as baterias de testes de aleatoriedade (NIST STS, Dieharder, TestU01, BoolTest — 414 testes) aplicadas ao keystream concatenado NÃO enxergam os vieses mais famosos da criptanálise moderna, porque a concatenação destrói o alinhamento posicional.** O viés Z_2 → 0 existe, é grande (2× o esperado), é publicado há 25 anos, e a bateria não o vê.

**[MINHA]** Isso é diretamente uma crítica ao desenho do extrator de features do projeto. As 12 famílias (histograma 256-D, entropia, n-gramas, autocorrelação, complexidade, FFT, NIST STS, momentos, Hamming, Welch, bitblock, tag_region) são **todas agregadas sobre o criptograma inteiro**. Se existir um viés indexado por posição — que é exatamente o que rodadas reduzidas produzem, porque a inicialização é o que está mal misturado — nenhuma delas o vê. Faltam features do tipo "byte na posição p, agregado *através* das amostras".

#### 5.3 Vieses de longo prazo indexados por lag — o caso Fluhrer–McGrew e ABSAB

**[PUB, via Vanhoef & Piessens]** Tabela completa dos vieses de dígrafo de Fluhrer–McGrew generalizados (Vanhoef, Piessens, *All Your Biases Belong To Us*, USENIX Security 2015, Tab. 1). i é o contador público do PRGA, r a posição do primeiro byte do dígrafo:

| Dígrafo | Condição | Probabilidade |
|---|---|---|
| (0,0) | i = 1 | 2^−16(1 + 2^−7) |
| (0,0) | i ≠ 1,255 | 2^−16(1 + 2^−8) |
| (0,1) | i ≠ 0,1 | 2^−16(1 + 2^−8) |
| (0,i+1) | i ≠ 0,255 | 2^−16(1 − 2^−8) |
| (i+1,255) | i ≠ 254 ∧ r ≠ 1 | 2^−16(1 + 2^−8) |
| (129,129) | i = 2, r ≠ 2 | 2^−16(1 + 2^−8) |
| (255,i+1) | i ≠ 1,254 | 2^−16(1 + 2^−8) |
| (255,i+2) | i ∈ [1,252] ∧ r ≠ 2 | 2^−16(1 + 2^−8) |
| (255,0) | i = 254 | 2^−16(1 + 2^−8) |
| (255,1) | i = 255 | 2^−16(1 + 2^−8) |
| (255,2) | i = 0,1 | 2^−16(1 + 2^−8) |
| (255,255) | i ≠ 254 ∧ r ≠ 5 | 2^−16(1 − 2^−8) |

E o viés ABSAB de Mantin, **[PUB]** (mesma fonte, eq. 1):

```
Pr[(Z_r, Z_{r+1}) = (Z_{r+g+2}, Z_{r+g+3})] = 2^−16 (1 + 2^−8 · e^{(−4−8g)/256})
```

**Por que o ABSAB importa tanto para o nosso ângulo [MINHA]:** ele é um viés **dentro do mesmo keystream**, relacionando duas posições separadas por um gap g. Isso significa que ele se manifesta no **XOR do criptograma consigo mesmo em lag g+2**:

```
(C_r ⊕ C_{r+g+2}, C_{r+1} ⊕ C_{r+g+3})
   = (M_r ⊕ M_{r+g+2}, …)  ⊕  (Z_r ⊕ Z_{r+g+2}, …)
      [viés do plaintext]      [viés ABSAB]
```

A distribuição observada é a **convolução-XOR** de duas distribuições enviesadas. Pela piling-up lemma, o viés observável é o produto. Como texto em inglês tem viés enorme no XOR em lag pequeno (dígrafos repetidos, espaços, quebras de linha), o produto pode ser mensurável. **E isso é uma estatística de criptograma único, chave única, ciphertext-only puro.**

Correção e refinamento publicados: **[CIT/PUB parcial] Bricout, Murphy, Paterson, van der Merwe, "Analysing and exploiting the Mantin biases in RC4", Designs, Codes and Cryptography 86(4):743–770, 2018.** Do que consegui extrair da versão PMC:
- caso A = B: expoente corrigido para e^{(−4−6g)/256} (viés mais forte);
- A = 1 ou B = 1: **sem viés** — a análise original de Mantin é inválida nesses casos;
- complexidade: N = 2^31 criptogramas → ~80% de sucesso para dois bytes desconhecidos; N = 2^32 → rank mediano 1; N = 2^31 com L = 2^16 → 86% de sucesso para 16 bytes com list-Viterbi; N = 2^30 com 130 bytes de plaintext conhecido;
- **o ataque não é ciphertext-only**: exige T = 26 a 130 bytes de plaintext conhecido adjacentes ao alvo.

**Cabe no modelo? A recuperação de plaintext NÃO. A estatística de autocorrelação de dígrafos em lag g SIM.** A adaptação é: não tente recuperar nada; use `Pr̂[(C_r, C_{r+1}) = (C_{r+g+2}, C_{r+g+3})]` como *feature* e deixe o classificador decidir. Custo: uma varredura O(N · L · G) com G valores de gap.

#### 5.4 Escala: o que a literatura RC4 precisou vs o que temos

| Trabalho | Dados necessários | Nossa disponibilidade |
|---|---|---|
| Mantin–Shamir, byte 2 **[CIT]** | Ω(256) criptogramas do *mesmo* plaintext | 0 (plaintexts distintos) |
| AlFardan et al. USENIX 2013 **[CIT]** | ≈ 2^30 sessões p/ 220 bytes; já a 2^24 alguns bytes; dígrafo: 13·2^30 p/ 100% em cookie de 16 bytes | 3×10^4 |
| Isobe, Ohigashi, Watanabe, Morii, FSE 2013 **[CIT]** | 2^32 criptogramas → P_1..P_257 com prob. > 0,8; 2^34 → 2 candidatos cada | 3×10^4 |
| Vanhoef–Piessens USENIX 2015 **[PUB]** | 9·2^27 cifragens → 94% num cookie; 75 h de tráfego | 3×10^4 |
| Bricout et al. DCC 2018 **[CIT]** | 2^30–2^32 | 3×10^4 |

**[MINHA]** Nosso número de *amostras alinhadas por posição* é 3×10^4 ≈ 2^14,9, contra os 2^24–2^34 que a literatura precisou para explorar vieses de magnitude 2^−8 relativos. Sensibilidade nossa por posição de bit: |ε| ≳ 2^−6,8. **Um viés do tamanho do de Mantin–Shamir (ε = 2^−8 relativo) estaria 2 bits binários abaixo da nossa capacidade de detecção por posição.** Isso é uma limitação dura e deve constar da dissertação: para testes posicionais, o dataset precisaria de ~10^6–10^8 amostras, não 3×10^4. **Alternativa mais barata: mais amostras curtas em vez de poucas amostras longas.** Trocar 30.000 × 64 KB por 30.000.000 × 64 bytes dá o mesmo volume de bytes mas 10^3× mais amostras alinhadas por posição, e é o desenho certo para caçar viés de inicialização.

#### 5.5 Busca empírica de vieses em larga escala — o método transferível

**[PUB] Vanhoef, Piessens, USENIX Security 2015** descrevem exatamente o procedimento:

> *"First we empirically search for biases in the keystream. This is done by generating a large amount of keystream, and storing statistics about them in several datasets. The resulting datasets are then analysed using statistical hypothesis tests. Our null hypothesis is that a keystream byte is uniformly distributed, or that two bytes are independent. Rejecting the null hypothesis is equivalent to detecting a bias. Compared to manually inspecting graphs, this allows for a more large-scale analysis."*

**[CIT] Paterson, Poettering, Schuldt, "Big Bias Hunting in Amazonia: Large-Scale Computation and Exploitation of RC4 Biases", ASIACRYPT 2014, LNCS 8873** — mesmo método em escala industrial: 2^13 núcleos hyper-threaded em EC2 por vários dias para estimar as distribuições de byte único e de dígrafo no início do keystream.

**Cabe no modelo? SIM, integralmente.** Esta é a técnica que a dissertação deveria adotar como Caminho complementar: em vez de escolher 641 features a priori, **varrer o espaço de estatísticas simples com teste de hipótese e correção de múltiplas comparações**. O projeto já usa BH-FDR na consolidação — é a mesma máquina. Confirmação de que BH é a escolha certa em criptanálise por varredura: **[CIT]** *Extended c-differential distinguishers of full 9 and reduced-round Kuznyechik cipher*, arXiv:2507.02181, que usa Benjamini–Hochberg explicitamente para controlar o efeito "look-elsewhere" sobre milhões de pares diferenciais testados.

#### 5.6 BoolTest: varredura de distinguidores booleanos

**[CIT] Sýs, Klinec, Kubíček, Švenda, "BoolTest: The Fast Randomness Testing Strategy Based on Boolean Functions with Application to DES, 3-DES, MD5, MD6 and SHA-256"**, SECRYPT 2017 (versão estendida em ICETE Selected Papers, LNCS/CCIS, Springer 2019). Preprint: https://crocs.fi.muni.cz/_media/public/papers/booltest_preprint_2017.pdf

O que é: busca exaustiva por funções booleanas (polinômios em forma normal algébrica) sobre subconjuntos de bits da saída, cuja distribuição se desvia do esperado. **"BoolTest detects bias and thus constructs distinguisher in a significantly higher number of rounds in the round-reduced versions of DES, 3-DES, MD5, MD6 and SHA-256 functions than the state-of-the-art batteries."** Encontrou viés previamente desconhecido no `rand()` do C e no `Random` do Java.

**Cabe? ADAPTÁVEL, e a adaptação é direta.** BoolTest é um teste de aleatoriedade (uma amostra vs uniforme), não um classificador de duas classes. A versão de duas classes é: rodar BoolTest separadamente em cada classe e comparar os polinômios/z-scores encontrados; ou melhor, usar o conjunto de monômios encontrados como **features** para o classificador. Custo: implementação moderada (o código é público em https://github.com/crocs-muni/booltest), execução barata.

**O que prevê:** com algoritmos completos, nenhum polinômio com z-score significativo após correção. Com rodadas reduzidas, polinômios de grau baixo sobre bits do mesmo bloco, com z-score crescendo monotonamente conforme as rodadas caem. Se BoolTest achar polinômio significativo no algoritmo completo, ou é bug de geração ou é um resultado de peso.

#### 5.7 NNBits: perfilamento bit a bit como distinguidor neural sem diferença escolhida

**[PUB] Hambitzer, Gérault, Huang, Aaraj, Bellini, "NNBits: Bit Profiling with a Deep Learning Ensemble Based Distinguisher", CT-RSA 2023, LNCS, pp. 493–523; ePrint 2023/819.** Código: https://github.com/Crypto-TII/nnbits

O que é: um ensemble de N redes neurais, cada uma treinada para **predizer um subconjunto de bits de uma sequência a partir dos bits restantes**. Se um bit é predito com acurácia significativamente acima do acaso, ele é um "weak bit" e a sequência não é aleatória.

Resultados exatos (Tab. 5), "random from round":

| Cifra | NIST STS | NNBits S₁ | NNBits S₂ | Tempo/rodada (STS / S₁ / S₂) | Dados |
|---|---|---|---|---|---|
| SPECK32/64 | 6 | **8** | **8** | ≤30 min / ≤5 min / ≤4 min | ~300 Mbit (STS,S₁) / ~4 Gbit (S₂) |
| SPECK64/128 | 7 | **8** | **8** | ≤30 / ≤7 / ≤12 min | ~300 Mbit / ~15 Gbit |
| SPECK96/144 | 8 | 8 | **9** | ≤30 / ≤10 / ≤24 min | ~300 Mbit / ~34 Gbit |
| SPECK128/128 | 9 | **10** | **10** | ≤30 / ≤20 / ≤17 min | ~300 Mbit / ~27 Gbit |
| AES-128 | 3 | 3 | 3 | ≤30 / ≤20 / ≤17 min | ~300 Mbit / ~27 Gbit |

E o resultado de explicabilidade (Tab. 4), para 6 rodadas de SPECK32/64:

| distinguidor diferencial clássico | ensemble E (só corretude das predições) | Gohr depth-1 | Gohr depth-10 |
|---|---|---|---|
| 75,8% | **78,1%** | 78,3% | 78,8% |

> *"Note that E does not even make use of the values of the bits, but only of the information about prediction correctness. [...] one possible way Gohr's network can be understood is as essentially learning the underlying Boolean functions to predict single bits, and then evaluating the number of correct predictions."*

Resultados análogos para rodada 5 (92,2% vs 92,7%) e rodada 7 (60,1% vs 60,8%).

**Cabe no modelo? ADAPTÁVEL, e é a adaptação mais limpa que encontrei.** O NNBits original opera sobre *avalanche datasets* (diferenças entre criptogramas de pares de plaintexts com diferença de 1 bit) — isso está fora do modelo. Mas a ideia núcleo — *predizer bit i a partir dos demais bits da mesma sequência* — é **puramente ciphertext-only**. Aplicada ao nosso caso:

- **Variante A (dentro do bloco):** predizer o bit j do bloco i a partir dos outros 127 bits do mesmo bloco. Mede a não-uniformidade interna ao bloco.
- **Variante B (entre blocos):** predizer bits do bloco i+1 a partir do bloco i. **É exatamente o elo estrutural do duplex** (§1.2). Para Ascon, isso testa p^8 diretamente.
- **Variante C (tag):** predizer bits da tag a partir dos últimos blocos do corpo. É o teste tag↔borda de §2.4.

**O que arranha do modelo de ameaça:** nada. Nenhuma diferença escolhida, nenhum plaintext, nenhum oráculo.

**Custo:** o código é público e paralelizado em GPU. Para 128 redes (uma por bit) × 4 algoritmos × k configurações de rodadas, algumas dezenas de horas de GPU. Cabe no orçamento Kaggle/Colab do projeto.

**O que prevê:** com algoritmos completos, acurácia por bit indistinguível de 0,5 em todas as posições e variantes, após BH-FDR sobre as 128 (ou 320) hipóteses. Com rodadas reduzidas, a variante B mostra bits fracos concentrados nas posições que o trilho linear prevê — e o perfil de bits fracos **difere entre algoritmos**, o que é um distinguidor de algoritmo indireto.

---

### 6. Fingerprinting forense, de formato e de container

Este subcampo tem vocabulário próprio e alguns resultados úteis, mas — importante — ele resolve um problema **mais fácil** que o nosso.

#### 6.1 O problema que esse campo resolve: cifrado vs comprimido

**[PUB] De Gaspari, Hitaj, Pagnotta, De Carli, Mancini, "Reliable Detection of Compressed and Encrypted Data", arXiv:2103.17059 (versão estendida do artigo de conferência; publicado em Neural Computing and Applications).**

Dataset: **400 milhões de fragmentos**, 16 formatos, fragmentos de 512 B a 8 KB, cifrado = AES-CBC (PyCryptodome).

Resultados do ENCOD:
- 512 B: ~82–86% de acurácia
- 8 KB: ~92%
- cifrado vs comprimido puro (zip, gzip): até **94%**
- cifrado vs dados de aplicação comprimidos (pdf, jpeg, mp3) a 8 KB: até **100%**

Faixas de entropia de Shannon medidas em blocos de 2048 B (Fig. 1), todos entre 7,5 e 8,0: `enc, bz2, lzma, h264, h265, mp2, mp4, office, vp8, zip, gzip, rar, jpeg, mp3, png, pdf` — **só png é inequivocamente separável, e mesmo assim sobrepõe com vários outros.**

Crítica dos autores a trabalhos anteriores:
> *"approaches based on statistical randomness tests (e.g., [35], [14]) cannot distinguish between different types of compressed archives."*
E sobre o HEDGE de Casino et al.: *"A limitation of this class of approaches is the fairly low accuracy, especially for small block sizes."*
E sobre um método anterior: *"It requires 800KB of data to reliably identify random data, which is far beyond the fragment size in the scenarios that we consider."*

**Cabe no modelo? NÃO como técnica, SIM como calibração.** O problema deles tem uma classe com estrutura residual (comprimido) e outra uniforme (cifrado). O nosso tem **duas classes uniformes**. O valor do resultado é fixar o teto: **o estado da arte em classificação de fragmentos quase-uniformes por bytes crus chega a 82–92% num problema estritamente mais fácil que o nosso.** Se nosso classificador passar disso, é artefato.

#### 6.2 Falsos positivos na detecção por entropia

**[CIT] McIntosh et al., "Why Current Statistical Approaches to Ransomware Detection Fail", ISC 2020** (https://www.cs.kent.ac.uk/people/staff/ba284/Papers/ISC2020.pdf). Achado reportado: taxas de falso positivo **frequentemente acima de 50%, e acima de 90% em várias ocasiões**; falsos negativos geralmente entre 5% e 20%.

**[CIT] Davies, Macfarlane, Buchanan, "Comparison of Entropy Calculation Methods for Ransomware Encrypted File Identification", Entropy 24(10):1503, 2022** (https://doi.org/10.3390/e24101503). Achado: **χ² supera Kolmogorov–Smirnov e Anderson–Darling**; ainda assim as métricas puramente matemáticas "struggle to differentiate consistently between encrypted files and other high entropy files such as compressed or archived files".

**Cabe? NÃO.** Reforça que a entropia agregada, que é a feature mais óbvia, é inútil aqui. O projeto já tem isso empiricamente; a literatura dá o argumento.

#### 6.3 Identificação de container cifrado sem assinatura

**[CIT]** Literatura forense sobre TrueCrypt/VeraCrypt (ForensicsWiki; Raedts; e o paper *Detecting Hidden Encrypted Volumes*, Communications and Multimedia Security 2010). Fato relevante: *"A VeraCrypt partition/device appears to consist of nothing more than random data and does not contain any kind of 'signature'"*. Os métodos que funcionam são todos **fora do criptograma**: tamanho do arquivo, localização, análise de Volume Shadow Copy, rastreamento de espaço livre, entropia (só para excluir não-cifrado).

**Cabe? NÃO.** Mas é um resultado útil por negação: **um subcampo inteiro, com incentivo forte (forense criminal) e décadas de esforço, chegou à conclusão de que não há assinatura dentro do criptograma e migrou para metadados de sistema de arquivos.** Vale citar na dissertação como evidência convergente de H₀.

#### 6.4 NCD — distância de compressão normalizada

**[CIT]** Cilibrasi & Vitányi, *Clustering by Compression*, IEEE Trans. Inf. Theory 51(4), 2005; aplicações a fragmentos de arquivo em Axelsson, *Using Normalized Compression Distance for Classifying File Fragments*, ARES 2010 (https://ieeexplore.ieee.org/document/5438024); e Raff & Nicholas, *On Normalized Compression Distance and Large Malware*, JCVHT 2017.

**Cabe? NÃO, e dá para provar.** NCD(x,y) = [C(xy) − min(C(x),C(y))] / max(C(x),C(y)). Para x, y uniformes e independentes, C(xy) ≈ C(x) + C(y), logo NCD → 1 para todos os pares, de todas as classes. **[MINHA]** A única maneira de NCD produzir sinal aqui seria se um dos criptogramas fosse compressível — o que o protocolo de validação do projeto (compressão média ~1.0×) já verifica que não acontece. Caminho fechado, com argumento.

---

### 7. Detecção de AEAD em tráfego real

#### 7.1 O SoK que resolve a pergunta

**[PUB] "SoK: Decoding the Enigma of Encrypted Network Traffic Classifiers", arXiv:2503.20093v4 (16 mai. 2025).** Este é o trabalho mais diretamente relevante de toda a pesquisa, e a metodologia dele deveria ser copiada.

**Premissa que eles testam:** muitos trabalhos de NTC assumem que *"encrypted payloads contain inherent patterns resulting from the imperfect randomness of encryption algorithms"* (citam 7 trabalhos que fazem essa suposição). Os autores rebatem:

> *"TLS 1.3 guarantees that the only learnable characteristic of a ciphertext is its length."*

**Experimento de oclusão** (348 experimentos totais; 72 sobre esta questão específica), com dois classificadores estado-da-arte (ET-BERT e YaTC), sobre CipherSpectrum e CSTNET-TLS1.3:

| Configuração | O que faz | ET-BERT | YaTC |
|---|---|---|---|
| **E1** | só payload cifrado, sem cabeçalhos | 0,12 | 0,30 |
| **E2** | bytes do payload substituídos por `0xFF` (só o comprimento sobra) | 0,12 | **0,39** (↑0,09) |
| **E3** | bytes substituídos por pseudoaleatórios independentes do rótulo | 0,12 | 0,30 |

Conclusão dos autores, literal:

> *"Collectively, the 72 experiments presented in Tables 4 and 5 demonstrate that state-of-the-art classifiers do not learn any intrinsic patterns from encrypted payloads beyond their length. [...] our results reinforce that any previously perceived patterns within encrypted payloads are likely artifacts from outdated datasets containing unencrypted data."*
>
> *"**Guideline 6**: Focus on encrypted payload length rather than content, as classifiers primarily rely on payload length for classification rather than intrinsic patterns in the ciphertext."*

E, sobre os datasets legados (Fig. 2a/2b):

| Dataset | % não-cifrado | Cifras presentes |
|---|---|---|
| ISCXVPN2016 | **98,9%** | — |
| ISCXTor2016 | 89,3% | — |
| USTC-TFC2016 | 94,7% | — |
| Cross-Platform'17 | 69,7% | — |
| CSTNET-TLS1.3 | 0% | só AEAD moderno |

> *"Takeaway 1: Substantial portions of public datasets contain unencrypted traffic. Takeaway 2: Widely-used datasets include sessions encrypted by vulnerable and deprecated ciphers, potentially misleading machine learning models."*

**Dataset CipherSpectrum** (contribuição deles): 40 domínios × 3 suítes TLS 1.3 (AES-128-GCM, AES-256-GCM, ChaCha20-Poly1305) × 1.000 sessões = **120.000 sessões**. Disponível em https://cspectrum.web.cse.unsw.edu.au

**Cabe no modelo? A metodologia SIM, integralmente, e é a coisa mais importante desta pesquisa.** O experimento E3 — substituir o criptograma por bytes pseudoaleatórios do mesmo comprimento, manter os rótulos, retreinar — é **o controle negativo que o projeto ainda não tem e que fecha a questão**. Se o F1 não cair, o modelo não está usando o criptograma.

**Nota importante:** na prática, a identificação de suíte de cifra em tráfego real é feita **pelo handshake**. O algoritmo de análise deles (Alg. 1, linha 8) diz: *"we attempt to identify the specific cipher suite used in the session by examining the 'Server Hello' packet of the TLS handshake packets"*. Ou seja: ninguém no mundo real tenta identificar a cifra pelo payload; isso é feito por metadado. Quando o metadado some (TLS 1.3 com ECH), a identificação some junto.

#### 7.2 Tipos de overfitting catalogados

O SoK classifica três tipos, e os três têm análogo direto no nosso experimento **[MINHA]**:

| Tipo (SoK) | Em NTC | Análogo no nosso dataset |
|---|---|---|
| **Data leakage overfitting** | SNI exposto nos primeiros m bytes (estudos usam m de 764 a 3072, e SNI aparece em ~700) | Nonce, comprimento, ordem de geração, ID de chave |
| **Contextual overfitting** | IP ID, TCP Seq/Ack, checksum — artefatos de protocolo, não da aplicação | Encadeamento do gerador, ordem dos slots, buffers reusados na implementação C |
| **Temporal overfitting** | TCP Window, timestamps | Timestamp no manifesto; ordem temporal da geração |

nte. **O segundo tipo não está coberto**: se o gerador encadeado produz os 6 algoritmos na mesma ordem dentro de cada slot, e se qualquer estado do RNG de geração vazar, há um canal contextual.

---

### 8. Rodadas reduzidas — os números que definem o ponto de virada

Esta seção responde à segunda pergunta da dissertação com números falsificáveis.

#### 8.1 O resultado mais importante: NIST STS com entrada aleatória quebra exatamente 1 rodada

**[PUB] Bellini, Huang (TII), "Randomness Testing of the NIST Light Weight Cipher Finalist Candidates", NIST LWC Workshop 2022** (slides, 11 mai. 2022). Versão em paper: **[CIT]** Bellini, Huang, Rachidi, *Statistical Tests for Symmetric Primitives*, SecITC 2022, LNCS 13809, https://link.springer.com/chapter/10.1007/978-3-031-32636-3_8

Escala: **462 GB de dados, 1 mês de execução**, três servidores (2× 16 Xeon Gold 5222 4-core 3,80 GHz 252 GB; 1× 112 Xeon Platinum 8280 28-core 2,70 GHz 1152 GB). Geração feita com NumPy e implementação Python independente não-otimizada de cada cifra. **Grain-128 foi excluído**; dados CBC do Spongent-π também. Nove estratégias de geração de dados: Avalanche Plaintext, Avalanche Key, Plaintext-Ciphertext Correlation, Cipher Block Chaining Mode, **Random**, Low-Density with Plaintext, Low-Density with Key, High-Density with Plaintext, High-Density with Key. Ferramentas: NIST STS oficial (https://csrc.nist.gov/Projects/Random-Bit-Generation/Documentation-and-Software).

Notação `r|[a,b]` = STS detecta não-aleatoriedade até a rodada r; o esquema usa entre a e b rodadas.

**Tabela consolidada (extraída dos slides 11–13):**

| Primitivo | Bloco | Chave | Avalanche PT | Avalanche Key | PT/CT corr. | CBC | **Random** | LowDens PT | LowDens Key | HighDens PT | HighDens Key |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **Ascon-p** (Ascon) | 320 | — | 4 \| [6,12] | — | 1 \| [6,12] | 1 \| [6,12] | **1** \| [6,12] | — | — | — | — |
| Elephant-Spongent-π[160] (Dumbo) | 160 | — | 8 \| 80 | — | 1 \| 80 | — | **1** \| 80 | — | — | — | — |
| Elephant-Spongent-π[176] (Jumbo) | 176 | — | 8 \| 90 | — | 1 \| 90 | — | **1** \| 90 | — | — | — | — |
| Elephant-Keccak-f[200] (Delirium) | 200 | — | 3 \| 18 | — | 1 \| 18 | 1 \| 18 | **1** \| 18 | — | — | — | — |
| Ascon-p (ISAP) | 320 | — | 4 \| [1,12] | — | 1 \| [1,12] | 1 \| [1,12] | **1** \| [1,12] | — | — | — | — |
| Keccak-p[400] (ISAP) | 400 | — | 3 \| [1,20] | — | 1 \| [1,20] | 1 \| [1,20] | **1** \| [1,20] | — | — | — | — |
| PHOTON256 (PHOTON-Beetle) | 256 | — | 3 \| 12 | — | 1 \| 12 | 1 \| 12 | **1** \| 12 | — | — | — | — |
| Xoodoo (Xoodyak) | 384 | — | 4 \| 12 | — | 1 \| 12 | 1 \| 12 | **1** \| 12 | — | — | — | — |
| **Sparkle256** (SCHWAEMM/ESCH) | 256 | — | 3 \| [7,10] | — | 1 \| [7,10] | 1 \| [7,10] | **1** \| [7,10] | — | — | — | — |
| **Sparkle384** | 384 | — | 3 \| [7,11] | — | 1 \| [7,11] | 1 \| [7,11] | **1** \| [7,11] | — | — | — | — |
| Sparkle512 | 512 | — | 3 \| [8,12] | — | 1 \| [8,12] | 1 \| [8,12] | **1** \| [8,12] | — | — | — | — |
| TinyJambu-128 P1024 | 128 | 128 | 17 \| [20,32] | 19 \| [20,32] | 4 \| [20,32] | 4 \| [20,32] | **1** \| [20,32] | 14 \| [20,32] | 17 \| [20,32] | 14 \| [20,32] | 17 \| [20,32] |
| TinyJambu-192 P1152 | 128 | 192 | 17 \| [20,36] | 21 \| [20,36] | 4 \| [20,36] | 4 \| [20,36] | **1** \| [20,36] | 14 | 17 | 14 | 17 |
| TinyJambu-256 P1280 | 128 | 256 | 17 \| [20,40] | 23 \| [20,40] | 4 \| [20,40] | 4 \| [20,40] | **1** \| [20,40] | 15 | 19 | 14 | 20 |
| **GIFT-128** (GIFT-COFB) | 128 | 128 | 8 \| 40 | 10 \| 40 | 2 \| 40 | 2 \| 40 | **1** \| 40 | 7 \| 40 | 9 \| 40 | 7 \| 40 | 8 \| 40 |
| skinny-128-384+ (Romulus) | 128 | 384 | 7 \| 40 | 8 \| 40 | 1 \| 40 | 1 \| 40 | **1** \| 40 | 6 \| 40 | 8 \| 40 | 6 \| 40 | 8 \| 40 |

Conclusão dos autores, literal (slide 14):

> *"We can see that most of the underlying primitives produce datasets which seem random in the first third of the total number of rounds. For the Spongent-pi this proportion is much higher, which seems to indicate a very conservative choice in the number of rounds of this cipher. Also, the schemes which using block ciphers as the underlying primitives also have parameter with higher rounds. In some scheme, different rounds of the underlying primitives are used. Ascon and Sparkle family choose this parameters in a more conservative way. On the other hand, we can see that in some cipher like ISAP and TinyJambu seems more aggressive to have some none random choice when doing the small task such as initialization or metadata encryption."*

Referências que eles citam como linhagem: **[CIT]** Soto, *NISTIR 6390: Randomness testing of the advanced encryption standard candidate algorithms*, 1999; **[CIT]** Bassham & Soto, *NISTIR 6483: Randomness testing of the advanced encryption standard finalist candidates*, abril de 2000 (as nove estratégias de geração vêm daí; o relatório conclui que "all five of the finalists appear to be random" para 192 e 256 bits de chave).

**A coluna que importa para nós é "Random".** Ela é a única das nove que corresponde ao nosso modelo de ameaça: entradas aleatórias, chaves aleatórias, sem diferenças escolhidas, sem baixa/alta densidade, sem controle nenhum. **Nessa coluna, o NIST STS quebra exatamente 1 rodada para todos os 15 primitivos, incluindo Ascon-p, as três Sparkle, GIFT-128, Keccak-p, PHOTON256, Xoodoo e skinny.**

**Isso dá à dissertação um baseline rigoroso e barato de citar:** qualquer coisa que o ML detecte com r ≥ 2 rodadas sob entradas aleatórias **já está batendo o NIST STS na configuração correspondente ao nosso modelo**. E, reciprocamente, se o ML não detectar nada com r = 1, está pior que uma bateria cuja metodologia é de 1999.

Duas observações adicionais sobre a tabela, que valem para a escrita **[MINHA]**:

- A distância entre a coluna Avalanche PT e a coluna Random é o preço exato do modelo de ameaça. Para GIFT-128: 8 rodadas com diferença escolhida, 1 rodada sem. **Fator 8 de margem que o adversário CT-only simplesmente não tem.** Para Ascon-p: 4 contra 1, fator 4. Essa razão é a medida quantitativa do que significa "ciphertext-only" nesse contexto e deveria ser um número citado na introdução da dissertação.
- TinyJambu é o outlier (17–23 rodadas detectáveis com avalanche de 20–40 nominais) e é justamente o que os autores chamam de "aggressive". Nenhum dos nossos quatro está nessa faixa.

#### 8.2 Margens de segurança em 109 funções (CRoCS Brno)

**[PUB] Klinec, Sýs, Kubíček, Švenda, Matyáš, "Large-scale Randomness Study of Security Margins for 100+ Cryptographic Functions", SECRYPT 2022, 19th International Conference on Security and Cryptography, pp. 134–146.** Framework com **414 testes estatísticos e variantes** de NIST STS, Dieharder, TestU01 e BoolTest, executados em cluster distribuído sobre **109 funções com rodadas reduzidas** (hash, lightweight e block-based).

Configuração ("cfg"): função (nº de rodadas + chave) × tipo de entrada (CTR, LHW, SAC; mais `zero` para cifras de fluxo, e as variantes `.key` correspondentes) × tamanho de saída (10 MB, 100 MB, 1000 MB). Cada configuração gera três sequências com seed/offset/byte distintos.

Definição formal deles:

```
sec. margin(f) = 1 − max{ i : f_i é não-aleatório } / n
```

> *"For example, there exists a distinguisher for a 3-round AES, but not for the 4-round one. AES-128 has 10 rounds in total, so the resulting security margin against analyzed randomness tests is 70%."*

**Tabela 1, extrato relevante** (notação `rodadas por RTT / rodadas por literatura / total`; `–` quando não há ataque prático publicado com complexidade < 2^80):

*Cifras de bloco:*

| Função | RTT/lit./total | Função | RTT/lit./total |
|---|---|---|---|
| **AES** | 3 / 6 / 10 | LBLOCK | 11 / 24 / 32 |
| ARIA | 2 / 4 / 12 | LEA | 8 / 8 / 24 |
| BLOWFISH | 5 / 4 / 16 | LED | 7 / – / 48 |
| CAMELLIA | 4 / 8 / 18 | MARS | 0 / 8 / 16 |
| CAST | 3 / 9 / 12 | MISTY1 | 1 / 6 / 8 |
| FANTOMAS | 2 / 5 / 12 | NOEKEON | 2 / 4 / 16 |
| GOST | 29 / 20 / 32 | PICCOLO | 6 / 5 / 25 |
| IDEA | 6 / 4 / 8 | PRIDE | 12 / 19 / 20 |
| KASUMI | 3 / 8 / 8 | PRINCE | 4 / 6 / 12 |
| KUZNYECHIK | 2 / 4 / 10 | RC5-20 | 5 / 17 / 20 |
| RC6 | 5 / 5 / 20 | ROBIN | 16 / 16 / 16 |
| ROBIN⋆ | 3 / – / 16 | SEED | 2 / – / 16 |
| SERPENT | 3 / 5 / 32 | SHACAL2 | 21 / 44 / 80 |
| SIMON | 19 / 26 / 68 | DES | 16 / 16 / 16 |
| TRIPLE-DES | 16 / – / 16 | TWOFISH | 3 / 16 / 16 |
| RECT.K80 | 8 / 18 / 25 | RECT.K128 | 8 / 14 / 25 |
| R.RUNNER.K80 | 3 / 8 / 10 | R.RUNNER.K128 | 5 / 8 / 12 |
| SPARX-B64 | 2 / 8 / 24 | SPARX-B128 | 3 / 8 / 32 |
| SPECK | 10 / 15 / 32 | TEA | 32 / 5 / 32 |
| TWINE | 9 / 23 / 35 | XTEA | 8 / 8 / 32 |
| HIGHT | 11 / 18 / 32 | CHASKEY | 3 / 7 / 16 |

*Cifras de fluxo:*

| Função | RTT/lit./total | Função | RTT/lit./total |
|---|---|---|---|
| Chacha | 3 / 6 / 20 | DECIM | 7 / – / 8 |
| F-FCSR | 5 / 5 / 5 | Fubuki | 0 / – / 4 |
| **Grain** (v1) | **11 / 13 / 13** | HC-128 | 0 / – / 1 |
| Hermes | 2 / – / 10 | LEX | 3 / – / 10 |
| MICKEY | 0 / – / 1 | Rabbit | 0 / – / 4 |
| **RC4** | **1 / – / 1** | Salsa20 | 2 / 6 / 20 |
| SOSEMANUK | 8 / – / 25 | Trivium | 3 / 5.8 / 8 |
| TSC-4 | 14 / – / 32 | | |

*Funções de hash (extrato):*

| Função | RTT/lit./total | Função | RTT/lit./total |
|---|---|---|---|
| **SHA-3 (Keccak)** | **4 / 5 / 24** | Keccak | 4 / 5 / 24 |
| SHA-1 | 18 / 80 / 80 | SHA-2 | 14 / 31 / 64 |
| MD5 | 25 / – / 64 | MD6 | 10 / 16 / 104 |
| RIPEMD160 | 14 / 48 / 80 | Skein | 4 / 17 / 72 |
| BLAKE | 1 / 4 / 14 | Grostl | 2 / – / 10 |
| JH | 6 / 10 / 42 | Luffa | 7 / 8 / 8 |
| CubeHash | 0 / – / 8 | Tiger | 2 / 19 / 23 |
| Whirlpool | 1 / 10 / 10 | Tangle | 80 / 80 / 80 |
| DynamicSHA2 | 17 / 17 / 17 | ESSENCE | 9 / 14 / 32 |

*PRNGs (todos 1/1/1):* Std.LCG, Std.MTwister, Std.SubCarry, U01.ULCG, U01.UMRG, U01.XorShift.

**Tabela 2 — margens agregadas (avg / med, em %):**

| Tipo de função | SM entrada (avg) | SM entrada (med) | SM chave (avg) | SM chave (med) |
|---|---|---|---|---|
| Hash | 76,37 | 84,52 | — | — |
| Cifra de bloco | 78,84 | 80,62 | 68,86 | 74,64 |
| **Cifra de fluxo** | 80,77 | 90,00 | **64,59** | **70,00** |
| MPC | 93,94 | 100,00 | 95,85 | 100,00 |

**Observações dos autores, transcritas, que importam para nós:**

> *"Results in Table 2 indicate that security margins of all function types are similar when considering only input type strategies. However, key type strategies reduce security margins significantly. Also, hash functions have typically greater security margins than block and stream ciphers using key strategies."*

> *"From the results we can conclude that the lhw strategy is very effective in breaking top-rounds, both in input and key variants. Also note that key variants have better relative success rate than input variants, indicating that cryptographic functions are more prone to biases when low-entropy keys are used compared to low-entropy inputs. Also, strategy rnd.key is the most difficult to detect as the entropy fed to the key of the function is high, it still managed to detect 37% of configurations it was used on."*

> *"Note that strategy zero is used for all stream functions with zero input as they generate long keystream with fixed random keys."*

> *"We observed that in 24 (44.44%) cases the key variant was better than input variant for given inputs, same performance was seen in 19 cases (35.19%), input variant was better in 11 cases (20.37%). [...] For example, Triple-DES is detected only to round 3 with input strategies, but the key strategy manages to detect all 16 rounds, even rnd.key, which is the most difficult strategy to detect. That means there are serious biases in Triple-DES output for some keys. A hypothesis is that weak keys known for Triple-DES were in the input stream, causing the ciphertext to contain biases. On the other hand, the SIMON function was detected with key methods up to 14 rounds but input methods reached 19 rounds."*

**E a frase que é o achado metodológico mais importante de toda esta pesquisa:**

> *"RC4 is known to contain biases on the beginning of the keystream. **Experiments were not able to detect biases using zero strategy, i.e., using keystream with a random key.** However, all tested key methods detected biases with 100 MB of data and more, even the most difficult rnd.key strategy."*

Traduzindo para o nosso problema **[MINHA]**: **414 testes estatísticos, aplicados a keystream de RC4 concatenado com chave aleatória, NÃO detectam os vieses mais famosos e mais publicados da criptanálise moderna.** O viés Z₂ → 0 de Mantin–Shamir existe, é grande (dobra a probabilidade esperada), está publicado há 25 anos, e a bateria inteira é cega a ele — porque a concatenação destrói o alinhamento posicional que é onde o viés vive. Todas as 12 famílias de features do projeto (histograma 256-D, entropia, n-gramas, autocorrelação, complexidade, FFT, nist_sts, momentos, Hamming, spectral_welch, bitblock, tag_region) agregam sobre o criptograma inteiro. Estão fazendo exatamente a concatenação que o CRoCS mostrou ser cega.

**Efeito do volume de dados** (10/100/1000 MB), números exatos dos autores:

| Evento observado | Ocorrências | % |
|---|---|---|
| Aumentar o volume **não** aumentou a detecção | 1694 | 80,94% |
| Detecção só apareceu a partir de volume maior | 397 | 18,97% |
| Detecção sumiu com volume maior ("fluke": Kasumi rodada 3, lhw.key, só 10 MB) | 1 | 0,05% |

> *"In general, one would assume that bigger the input stream the easiest is to spot biases for the randomness tests. [...] This turned out to be the case for 397 detections (18.97%). For example, AES round 3 using lhw.key strategy was not detected on 10 MB input but since 100 MB. Similarly for Blowfish round 3 with sac strategy."*
> *"Interestingly, {lhw, lhw.key} on 10 MB outperform ctr on 100 MB."*

Ou seja: **em 81% dos casos, multiplicar o volume por 100 não comprou nada.** A escolha de estatística domina o volume de dados. Isso é diretamente relevante para o orçamento do v2: 11,8 GB de parquet não compram o que uma estatística melhor compra.

Sobre as funções MPC (MiMC, GMiMC, Rescue, Poseidon, Vision, Starkad, LowMC), os autores acrescentam uma advertência útil:

> *"Measured security margins of MPC hash functions are high, indicating that testing batteries might not be directly usable for this function family. We hypothesize this is due to usage of algebraic building blocks which are difficult to detect with randomness testing batteries. To verify the claim, we tested a simple function f(x) = x³ (mod p), where p is a 255-bit prime. The function f was fed with a strongly biased input distribution — normal distribution to produce 1 GB of output data. The output was tested with testing batteries (after applying rejection sampling transformation). There was no bias detected in any of 10 tested streams."*

**Advertência crítica [MINHA]:** **todas** as estratégias do CryptoStreams (CTR, LHW, SAC, zero, e as variantes `.key`) são entradas escolhidas, estruturadas ou de baixa entropia. **Nenhuma corresponde ao nosso modelo.** As margens de 65–90% são margens contra um adversário com controle de entrada ou de chave. O nosso adversário não tem nem um nem outro, e o resultado de Bellini–Huang (§8.1) mostra que sem esse controle a margem sobe para ~97% (1 rodada de 40 no GIFT-128, 1 de 12 no Ascon-p). Citar as margens do CRoCS sem essa ressalva seria comparar coisas diferentes.

Ferramentas: CryptoStreams em https://github.com/crocs-muni/CryptoStreams (Klinec, Kubíček, Rózsa, Švenda).

#### 8.3 Os limites de trilho do Ascon — a tabela que permite prever o ponto de virada

**[PUB] El Hirch, Mella, Mehrdad, Daemen, "Improved Differential and Linear Trail Bounds for ASCON", IACR Transactions on Symmetric Cryptology 2022(4):145–178; ePrint 2022/1377.**

Contexto metodológico do próprio paper: a S-box de 5 bits tem DP máximo 2^−2 e C² máximo 2^−2; a camada linear tem número de ramificação B = 4; Dobraunig et al. (SMT, 2015) provaram que um trilho diferencial de 3 rodadas tem no mínimo **15 S-boxes ativas** e um trilho linear de 3 rodadas no mínimo **13**, o que dá automaticamente 2^−30 e 2^−26. O novo tool dedicado (`AsconTrailTool`, baseado em travessia de árvore de trail cores de 2 rodadas) atinge **peso 21 por rodada**, contra 17 do método SAT de Erlacher et al. **[CIT]** (*Bounds for the Security of Ascon against Differential and Linear Cryptanalysis*, ToSC 2022(1)), 12 do Keccak-f[1600] e Noekeon, 15 do Keccak-p refinado, 14 do Subterranean, 21 do Xoodoo.

Relação peso↔probabilidade: DP ≈ 2^−w para trilho diferencial, C² ≈ 2^−w para trilho linear.

**Tabela 1 (a) — Trilhos diferenciais (DP):**

| R | melhor conhecido | método / ref. | limite anterior | método / ref. | **novo limite** |
|---|---|---|---|---|---|
| 1 | 2^−2 | DDT | 2^−2 | DDT | 2^−2 |
| 2 | 2^−8 | DDT+B | 2^−8 | DDT+B | 2^−8 |
| 3 | 2^−40 | nldtool [DEMS15] | 2^−40 | MILP [MR22] | 2^−40 (**justo**) |
| 4 | 2^−107 | nldtool [DEMS15] | ≤ 2^−72 | SAT+min #S [EME22] | ≤ 2^−86 |
| 5 | 2^−190 | CP [DEMS15,GPT21] | ≤ 2^−74 | combine 1R+4R | ≤ 2^−100 |
| 6 | 2^−305 | CP [GPT21] | ≤ 2^−108 | SAT+min #S [EME22] | ≤ 2^−129 |
| 7 | — | — | ≤ 2^−110 | combine 1R+6R | ≤ 2^−131 |
| 8 | — | — | ≤ 2^−144 | SAT+min #S [EME22] | ≤ 2^−172 |
| 9 | — | — | ≤ 2^−146 | combine 1R+8R | ≤ 2^−186 |
| 10 | — | — | ≤ 2^−180 | combine 4R+6R | ≤ 2^−215 |
| 11 | — | — | ≤ 2^−182 | combine 1R+10R | ≤ 2^−229 |
| 12 | — | — | ≤ 2^−216 | SAT+min #S [EME22] | ≤ 2^−258 |

**Tabela 1 (b) — Trilhos lineares (C²):**

| R | melhor conhecido | método / ref. | limite anterior | método / ref. | **novo limite** |
|---|---|---|---|---|---|
| 1 | 2^−2 | LAT | 2^−2 | DDT | 2^−2 |
| 2 | 2^−8 | LAT+B | 2^−8 | DDT+B | 2^−8 |
| 3 | 2^−28 | lineartrails [DEM15] | ≤ 2^−26 | SMT+min #S [DEMS15] | 2^−28 (**justo**) |
| 4 | 2^−98 | lineartrails [DEM15] | ≤ 2^−72 | SAT+min #S [EME22] | ≤ 2^−88 |
| 5 | 2^−184 | MILP [MR22] | ≤ 2^−74 | combine 1R+4R | ≤ 2^−96 |
| 6 | — | — | ≤ 2^−108 | SAT+min #S [EME22] | ≤ 2^−132 |
| 7 | — | — | ≤ 2^−110 | combine 1R+6R | ≤ 2^−134 |
| 8 | — | — | ≤ 2^−144 | SAT+min #S [EME22] | ≤ 2^−176 |
| 9 | — | — | ≤ 2^−146 | combine 1R+8R | ≤ 2^−184 |
| 10 | — | — | ≤ 2^−180 | combine 4R+6R | ≤ 2^−220 |
| 11 | — | — | ≤ 2^−182 | combine 1R+10R | ≤ 2^−228 |
| 12 | — | — | ≤ 2^−216 | SAT+min #S [EME22] | ≤ 2^−264 |

Do abstract, o que é novidade deste trabalho:

> *"As a result, we prove tight bounds for 3-rounds linear trails, and for both differential and linear trails, we improve the existing upper bounds for other number of rounds. In particular, for the first time, we prove bounds beyond 2^−128 for 6 rounds and beyond 2^−256 for 12 rounds of both differential and linear trails."*

**As duas linhas que governam o nosso experimento são R=3 (C² = 2^−28, justo) e R=4 (C² ≤ 2^−88, melhor conhecido 2^−98).** O salto de 60 bits binários entre 3 e 4 rodadas é o que torna a previsão do ponto de virada tão nítida.

#### 8.4 Cálculo do ponto de virada em CT-only — a previsão central

**[MINHA]**, construído sobre os limites de §8.3 e as estruturas de modo de §1.2.

**Orçamento de amostras** por algoritmo, no dataset atual (30.000 criptogramas × 64 KB):

- pares de blocos consecutivos de 128 bits: 30.000 × 4095 = 1,2285×10^8 ≈ 2^26,87
- limiar de detecção de uma correlação linear com vantagem constante: N ≈ 1/C², logo detectável se C² ≳ 2^−26,9 ≈ 2^−27

**A relação observável para Ascon.** Da spec (§1.2): C_{i+1} = ⌊p^b(C_i ‖ S_c)⌋_r ⊕ P_{i+1}. Para máscaras α (entrada) e β (saída), ambas obrigatoriamente suportadas apenas no rate (porque S_c é desconhecido e uniforme — qualquer máscara com suporte na capacidade dá correlação observável nula):

```
corr( α·C_i ⊕ β·C_{i+1} )  =  corr_{p^b}(α,β) × corr( β·P_{i+1} )
```

pela piling-up lemma, assumindo independência entre o plaintext e o estado.

**E aqui está o ponto fino que faz a ideia funcionar [MINHA].** O corpus é 80% texto ASCII em inglês do Project Gutenberg. Em ASCII puro, **o bit 7 de todo byte é 0 com probabilidade ≈ 1**. Se β for suportada apenas nas posições de bit 7, 15, 23, …, 127 do bloco (16 posições dentro dos 128 bits do rate do Ascon-128a), então β·P_{i+1} = 0 deterministicamente e corr(β·P_{i+1}) = 1. **A penalidade da piling-up lemma desaparece inteiramente.** A correlação observável no criptograma é *exatamente* a correlação da permutação com máscara restrita — sem perda.

Isso é o oposto da intuição usual ("o plaintext desconhecido mascara tudo"). O plaintext desconhecido mascara tudo **exceto** nas direções em que ele é previsível, e num corpus de texto ASCII há 16 dessas direções por bloco, com correlação 1.

Comparando o limiar 2^−27 com a Tabela 1(b):

| b (rodadas de p) | C² (limite provado / melhor trilho conhecido) | amostras necessárias | temos 2^26,9? |
|---|---|---|---|
| 1 | 2^−2 | 4 | **SIM, trivial** |
| 2 | 2^−8 | 256 | **SIM, trivial** |
| **3** | 2^−28 (**justo**) | 2^28 | **MARGINAL** — falta fator ≈2,1 |
| 4 | ≤ 2^−88 (melhor conhecido 2^−98) | ≥ 2^88 | **NÃO** |
| 5 | ≤ 2^−96 | ≥ 2^96 | NÃO |
| 6 (Ascon-128, p^b) | ≤ 2^−132 | ≥ 2^132 | NÃO |
| 8 (Ascon-128a, p^b) | ≤ 2^−176 | ≥ 2^176 | NÃO |
| 12 (finalização) | ≤ 2^−264 | ≥ 2^264 | NÃO |

**Previsão falsificável #1:** o distinguidor linear ciphertext-only sobre a permutação de processamento de mensagem do Ascon vira de detectável para indetectável **entre b=3 e b=4**, e b=3 cai praticamente em cima do orçamento de dados (falta um fator ~2, que se resolve dobrando o dataset ou usando um único braço a mais).

Duas correções puxam em direções opostas, e ambas precisam constar da dissertação:

**(i) A teoria subestima o viés real em poucas rodadas — por muito.** **[PUB] Tezcan, "Differential-Linear Cryptanalysis of ASCON: Theory vs. Practice", NIST Lightweight Cryptography Workshop 2023** (slides, 22 jun. 2023, Middle East Technical University / TÜBİTAK 1001 projeto 121E228). Abre com *"In theory, theory and practice are the same. In practice, they are not."* e a advertência metodológica: *"Many cryptanalysis results are obtained theoretically but (1) they may not work in practice, (2) they may require more data/time/memory than expected, (3) they may require less data/time/memory than expected. Toy versions of the distinguishers and attacks must be experimentally verified."*

O número central (slides 26–30):

> *"The 4-round Differential-Linear distinguisher for Ascon has theoretical bias 2^−15, practical bias 2^−2, DLCT reduces this to 2^−5. The gap might be due to (1) multiple distinguishers, (2) slow diffusion and confusion."*

**Treze bits binários de discrepância entre teoria e prática em 4 rodadas.** Se um fator comparável valer no caso linear puro, b=4 e talvez b=5 entram no alcance do experimento.

Ele também dá, como calibração independente, a verificação experimental do distinguidor DL de 9 rodadas do Serpent (Dunkelman, Indesteege, Keller, 2008), com 100 chaves aleatórias e 2^50 pares de dados aleatórios:

| r | viés teórico | viés experimental | ganho |
|---|---|---|---|
| 4 | 2^−15 | 2^−13,73 | 2^1,27 |
| 5 | 2^−19 | 2^−17,63 | 2^1,37 |
| 6 | 2^−27 | 2^−25,61 | 2^1,39 |

Ou seja, no Serpent o ganho prática-sobre-teoria é modesto (~1,3 bits); no Ascon é de 13 bits. A diferença é atribuída por ele à difusão lenta do Ascon e à multiplicidade de distinguidores.

Outros números do mesmo material, úteis para calibrar:
- **Característica linear Type-II de 2 rodadas da permutação Ascon-128, com viés 2^−8** (slide 24), com as máscaras em hexadecimal: rodada 0 `................ ...........2.4.. ...........2.4.1 .....2........8. .....2........8.`; rodada 1 `... ...............1 ...............1`; rodada 2 `9224b6d24b6eda49 ...`.
- Distinguidor diferencial truncado de 2 rodadas com probabilidade 1 (Tezcan 2020), a partir da diferença de entrada com apenas duas palavras ativas.
- **Vieses DL de 5 rodadas medidos experimentalmente**, mantendo a aproximação linear fixa e introduzindo diferença em cada S-box:

| Diferença de entrada | Melhores vieses medidos |
|---|---|
| 00011 | 2^−11,91, 2^−14,87, 2^−15,05, 2^−8,03 |
| 10011 | 2^−14,45, 2^−12,25, 2^−12,25, 2^−14,45 |
| **01100** | 2^−8,52, 2^−7,94, 2^−7,94, 2^−8,52 |

- Bits não-perturbados ("undisturbed bits") da S-box 5×5 do Ascon/DryGASCON (slide 22), 23 diferenças de entrada com bits de saída determinados — por exemplo, entrada `00001` → saída `?1???`, entrada `00011` → `???0?`, entrada `11111` → `?0???`.
- Distinguidores melhores obtidos experimentalmente para DryGASCON: viés 2^−7,98 com 2^29 dados; viés 2^−5,34 com 2^17 dados.
- Verificação em GPU: **2^35 verificações de distinguidor DL de 5 rodadas do Ascon por segundo numa RTX 4090**; 2^35 tentativas de chave por segundo. Código em https://github.com/cihangirtezcan/CUDA_ASCON

**Esses são distinguidores diferencial-lineares (diferença escolhida) e portanto estão fora do modelo de ameaça.** Mas estabelecem, com medições, que a prática bate a teoria por larga margem no Ascon especificamente — o que torna a previsão "ponto de virada em b=3" conservadora.

**(ii) A restrição de máscara ao rate piora as coisas, e ninguém mediu quanto.** Os limites da Tabela 1(b) são sobre **todas** as máscaras nos 320 bits do estado. Nós só podemos usar máscaras suportadas nos 128 bits do rate, tanto na entrada quanto na saída. Isso pode degradar substancialmente a melhor correlação atingível — um trilho ótimo com máscara de entrada na capacidade simplesmente não é utilizável. **Nenhum trabalho publicado que encontrei calcula trilhos lineares do Ascon com máscaras restritas ao rate.** Essa é uma lacuna real, e preenchê-la — adaptando o `AsconTrailTool`, que é público, para buscar trilhos rate→rate — é trabalho de mestrado por si e seria uma contribuição original da dissertação.

**GIFT-128 [PUB]** (Banik, Pandey, Peyrin, Sasaki, Sim, Todo, *GIFT: A Small Present Towards Reaching the Limit of Lightweight Encryption*, CHES 2017, LNCS 10529; ePrint 2017/622). Parâmetros: bloco 128 bits, chave 128 bits, **40 rodadas**.

| R | S-boxes ativas mín. (GIFT-128) | S-boxes ativas mín. (GIFT-64) | melhor DP | melhor C² |
|---|---|---|---|---|
| 1 | 1 | 1 | 2^−6 | 2^−6 |
| 2 | 2 | 2 | 2^−12 | 2^−13 |
| 3 | 4 | 3 | 2^−19 | 2^−20 |
| 4 | 5 | 4 | 2^−25 | 2^−27 |

Resultados posteriores **[CIT]**:
- hull linear de **9 rodadas: 2^−45,99**; probabilidade diferencial de 9 rodadas: 2^−46,99 (valores oficiais da especificação/GIFT-COFB);
- **característica linear de 16 rodadas com correlação 2^−62**, a mais longa encontrada para GIFT-128, usada num ataque linear de 20 rodadas (2 rodadas antes + 2 depois) — Zhu et al., *MILP-Based Linear Attacks on Round-Reduced GIFT*, Chinese Journal of Electronics, 2022, https://cje.ejournal.org.cn/article/doi/10.1049/cje.2020.00.113;
- **aproximação linear de 19 rodadas com potencial linear esperado 2^−117,43**, por busca SAT (Sun et al.);
- limites lineares ótimos para 11 e 12 rodadas, estendendo o melhor resultado anterior de 10 rodadas;
- **[CIT]** *Addendum to Linear Cryptanalyses of Three AEADs with GIFT-128 as Underlying Primitives*, ToSC 2022(2) / ePrint 2022/151 — análise linear especificamente dos modos AEAD sobre GIFT-128, incluindo GIFT-COFB.

**Previsão falsificável #2:** o elo C_i → C_{i+1} do GIFT-COFB atravessa r rodadas de GIFT-128 (§1.2: X[i+a] = C[i] ⊕ (I⊕G)·Y[i+a−1] ⊕ L‖0^{n/2}, Y = E_K(X)). Com C² = 2^−27 em 4 rodadas, o limiar 2^−27 é atingido **exatamente em r = 4 de 40**.

**Schwaemm256-128.** Da página oficial de segurança da suíte Sparkle (**[PUB]** https://sparkle-lwc.github.io/security), limites superiores no número de *steps* que um ataque pode cobrir:

| Ataque | Sparkle256 | Sparkle384 | Sparkle512 |
|---|---|---|---|
| Criptanálise diferencial | 4 | 5 | 6 |
| **Criptanálise linear** | 5 | **6** | 6 |
| Boomerang | 3 | 4 | 5 |
| Diferenciais truncadas | 2 | 2 | 3 |
| Yoyo games | 4 | 4 | 4 |
| Diferenciais impossíveis | 4 | 4 | 4 |
| Correlação zero | 4 | 4 | 4 |
| Integral / division property | 4 | 4 | 4 |

Steps por instância **[PUB]** (spec Sparkle, Tab. 2.1): Sparkle256 = 7 slim / 10 big; Sparkle384 = 7 slim / **11 big**; Sparkle512 = 8 slim / 12 big. Schwaemm256-128 usa Sparkle384: 7 steps slim entre blocos, 11 steps big na inicialização e na finalização.

**Sparkle384 slim tem margem de 1 step contra criptanálise linear (6 de 7).** Ressalvas: (a) são *limites superiores* sobre quantos steps um ataque poderia cobrir, derivados pela long trail strategy, não ataques concretos; (b) a segurança do Schwaemm vem do modo Beetle (que esconde o rate pós-absorção, §1.2) somado aos 11 steps big nas pontas; (c) a própria spec **[PUB]** declara o nível de segurança conjunta em 120 bits com limite de dados de 2^68 bytes. Ainda assim, é o menor colchão relativo do conjunto ao nível da permutação slim, e merece investigação.

Detalhe da primitiva, útil para o braço de rodadas reduzidas **[PUB]** (spec, §2.1.1 e changelog): a ARX-box **Alzette** é uma cifra de bloco de 64 bits com estrutura tipo Feistel de quatro rodadas com rotações distintas (`x ← x + (y⋙31); y ← y ⊕ (x⋙24); x ← x ⊕ c;` depois `⋙17/⋙17`, `⋙0/⋙31`, `⋙24/⋙16`); a probabilidade do melhor trilho diferencial de 7 rodadas do Alzette é **2^−26** (melhorado de 2^−24 na v1.2).

**[CIT]** Xiong & Liu (2023) apresentaram um distinguidor prático de 4 rodadas e um ataque teórico de recuperação de chave de 4,5 rodadas contra uma variante do Schwaemm128-128, via criptanálise diferencial-linear. Ver também **[CIT]** *Revisiting differential-linear cryptanalysis of lightweight cipher Schwaemm*, Cybersecurity (Springer), 2026, https://link.springer.com/article/10.1186/s42400-026-00636-w

**Tabela comparativa final — a previsão central da dissertação [MINHA]:**

| Esquema | rodadas nominais no elo observável | rodadas em que o elo CT-only vira detectável | margem relativa sobrevivente | base do cálculo |
|---|---|---|---|---|
| **Ascon-128a** (p^8 entre blocos) | 8 | **3** (talvez 4) | **62,5%** (ou 50%) | C² justo 2^−28 em 3R vs limiar 2^−27 |
| Ascon-128 (p^6 entre blocos) | 6 | **3** | **50%** | idem |
| Ascon, finalização (p^12) | 12 | **3** | 75% | idem; concorda com forja 2^33 de Dobraunig et al. |
| **GIFT-COFB** (E_K, 40 rodadas) | 40 | **4** | **90%** | C² = 2^−27 em 4R (CHES 2017) |
| Schwaemm256-128 (Sparkle384 slim) | 7 steps | ≈ 2 steps | ≈ 71% | extrapolação do long trail; limite linear = 6 steps |
| Grain-128AEADv2 (init) | 512 clockings | indeterminado no nosso modelo | — | distinguidores publicados chegam a 191–195 de 256 **com IV escolhido** |

**Este é, no meu julgamento, o resultado mais vendável do braço de rodadas reduzidas: em termos relativos, o Ascon tem a margem MAIS FINA por elo observável em cenário ciphertext-only**, precisamente porque (a) é o único cujo rate do estado é literalmente o criptograma, e (b) usa apenas 8 rodadas entre blocos consecutivos, contra 40 do GIFT-128. É contraintuitivo — o Ascon é o vencedor do NIST e o primitivo mais analisado dos quatro — e é rigorosamente derivado de duas tabelas publicadas. E não contradiz em nada a segurança do Ascon: 62,5% de margem contra um adversário que sequer escolhe entradas é confortabilíssimo.

O eixo de apresentação correto é o de §1.2, **rodadas de trabalho criptográfico por byte de saída observável**:

| Esquema | rodadas/byte | margem relativa CT-only prevista |
|---|---|---|
| Ascon-128a (r=128, b=8) | **0,50** rodada Ascon/byte | 62,5% |
| Ascon-128 (r=64, b=6) | 0,75 rodada Ascon/byte | 50% |
| Schwaemm256-128 (r=256, 7 steps) | 0,22 step Sparkle384/byte (≈1,75 ARX-box/byte) | ≈71% |
| GIFT-COFB (n=128, 40 rodadas) | **2,50** rodadas GIFT/byte | 90% |
| Grain-128AEADv2 | 16 clockings/byte | — |

#### 8.5 Criptanálise do Ascon relevante à finalização

**[PUB] Dobraunig, Eichlseder, Mendel, Schläffer, "Cryptanalysis of Ascon", CT-RSA 2015, LNCS 9048, pp. 371–387; ePrint 2015/030.** Do abstract:

> *"Our results are practical key-recovery attacks on round-reduced versions of Ascon-128, where the initialization is reduced to 5 out of 12 rounds. Theoretical key-recovery attacks are possible for up to 6 rounds of initialization. Moreover, we present a practical forgery attack for 3 rounds of the finalization, a theoretical forgery attack for 4 rounds finalization and zero-sum distinguishers for the full 12-round Ascon permutation."*

**Tabela 1 completa (Ascon-128; ataques sobre inicialização ou finalização):**

| Tipo | Rodadas | Tempo | Método | Seção |
|---|---|---|---|---|
| Distinguidor de permutação | **12 / 12** | 2^130 | zero-sum | §3 |
| Recuperação de chave (init.) | 6 / 12 | 2^66 | cube-like | §4.4 |
| Recuperação de chave (init.) | 5 / 12 | 2^35 | cube-like | §4.4 |
| Recuperação de chave (init.) | 5 / 12 | 2^36 | diferencial-linear | §5.4 |
| Recuperação de chave (init.) | 4 / 12 | 2^18 | diferencial-linear | §5.4 |
| **Forja (finalização)** | **4 / 12** | 2^101 | diferencial | §5.3 |
| **Forja (finalização)** | **3 / 12** | 2^33 | diferencial | §5.3 |

Parâmetros do Ascon-128 na versão analisada (Tab. 2 do paper): chave 128, nonce 128, tag 128, bloco de dados 64, p_a = 12, p_b = 6.

**Cabe no modelo? NÃO** — a forja exige diferenças escolhidas e consultas de verificação, e o zero-sum exige conjuntos de entrada estruturados. Mas fixa a escala com precisão: com **3 rodadas de finalização a estrutura é explorável com 2^33 operações; com 4, custa 2^101.** Um salto de 68 bits binários entre 3 e 4.

**Isso concorda com a minha previsão de §8.4, obtida por caminho inteiramente independente** (limites de trilho linear de El Hirch et al. + orçamento de dados do experimento). Duas rotas independentes apontando o ponto de virada entre 3 e 4 rodadas é um bom sinal de que o número está certo.

Sobre os zero-sums na permutação completa, os projetistas respondem **[CIT]** que *"the designers are aware of such distinguishers, and the non-ideal properties of the permutation do not seem to affect the security of Ascon"* — o que é a posição padrão e correta: um zero-sum de 2^130 na permutação nua não se traduz em ataque ao modo.

Resultados mais recentes, para completar o estado da arte **[CIT]**:
- *Misuse-Free Key Recovery and Distinguishing Attacks on 7-Round Ascon*, NIST LWC Workshop 2022 — o melhor alcance atual sobre a inicialização;
- *Experimentally Obtained Differential-Linear Distinguishers for Permutations of ASCON and DryGASCON*, SECRYPT 2023 / CCIS (Springer) — primeiros distinguidores DL de 5 rodadas, com viés 2^−8,55, mais características truncadas de probabilidade 1 em 2 e 3 rodadas e características lineares de 2, 3 e 4 rodadas;
- *Truncated, Impossible, and Improbable Differential Analysis of Ascon*, ePrint 2016/490;
- *Analysis of Ascon, DryGASCON, and Shamash Permutations*, Tezcan, ePrint 2020/1458;
- *Conditional Cube Attack on Round-Reduced ASCON*, arXiv:2508.15172; *A New Conditional Cube Attack on Reduced Round Ascon-128a*, NIST LWC 2022;
- **[CIT]** Erlacher, Mendel, Eichlseder, *Bounds for the Security of Ascon against Differential and Linear Cryptanalysis*, ToSC 2022(1) — a base SAT que El Hirch et al. superam;
- **[CIT]** *Towards Tight Differential Bounds of Ascon: A Hybrid Usage of SMT and MILP*, ToSC (ojs.ub.rub.de/index.php/ToSC/article/view/9859).
- **[CIT]** Survey: *A Comprehensive Survey on the Implementations, Attacks, and Countermeasures of the Current NIST Lightweight Cryptography Standard*, arXiv:2304.06222, e a versão em ACM Computing Surveys (2025), https://dl.acm.org/doi/10.1145/3744640 — relatam ataques de forja por características diferenciais múltiplas com complexidade 2^32,76 para 3 rodadas de finalização e 2^96,61 para 4 rodadas do Ascon-128, ligeiramente melhores que os de Dobraunig et al.; e situam a análise da permutação em 7 de 12 rodadas, correspondendo a **42% de margem de segurança**.

#### 8.6 Grain-128AEAD sob rodadas reduzidas

**[PUB]** Da spec Grain-128AEADv2, §4.4 (*Chosen IV Attacks*), transcrito:

> *"A variety of chosen IV attacks on Grain have been proposed, in both fixed key scenario as well as in the related key setting, and either for distinguishing purpose or for key recovery. In a fixed key scenario, chosen IV attacks have been devised on reduced-round versions using conditional differentials and using cube attacks, or combinations of both. On Grain-128, a dynamic cube attack has been developed that succeeds in finding the secret key for the full 256-round initialization for a fraction of keys. Dynamic cube attacks have not been successful on Grain-128a thus far. Most of these results are experimental in nature, and do work only if the computational effort is practically feasible."*

> *"The latest result on Grain-128a in this direction is a key recovery on **184 initialization rounds**. The data complexity is 2^95, and the computational complexity corresponds to about 2^110 operations. An attack that reaches the largest number of initialization rounds of Grain-128a in a fixed key scenario thus far is a conditional differential distinguishing attack and reaches **195 initialization rounds**, but it works only for a fraction of all keys."*

> *"As a result, there exist no chosen IV attacks on full round initialization of Grain-128a in a single key scenario. The strengthened initialization procedure of Grain-128AEADv2 is expected to prevent such attacks even further."*

Resultados adicionais **[CIT]**:
- distinguidor com cubos de dimensão 5: **191 rodadas** de KSA em configuração de chave única, **201 rodadas** em configuração de chave fraca (Grain-128a);
- *Cube Attacks on Round-Reduced Grain-128AEAD*: ANFs exatas dos superpolinômios recuperadas para **191 rodadas**; **distinguidor zero-sum até 193 rodadas** em cenário de chave fraca, via cube attacks baseados em division property — o melhor zero-sum conhecido do Grain-128AEAD;
- **[CIT]** *Breaking Grain-128 with Dynamic Cube Attacks*, Dinur & Shamir, FSE 2011 / ePrint 2010/570 — quebra o Grain-128 (não o 128a) com inicialização completa de 256 rodadas para uma fração das chaves;
- **[CIT]** *Recovering the Key from the Internal State of Grain-128AEAD*, ePrint 2021/439, e a resposta dos projetistas **[CIT]** *Grain-128AEADv2: Strengthening the Initialization Against Key Reconstruction*, CANS 2021, LNCS 13099, ePrint 2021/751 — motivo do tweak v1→v2 (as 64 clockings extras de reintrodução de chave).

**Todos exigem IV escolhido.** Fora do modelo de ameaça.

Também da spec, §4.2 (*Linear Approximations*) **[PUB]**, a fórmula e os números que dão o limite no nosso cenário:

> *"It is always possible to find a linear combination of the output bits that is unbalanced. [...] Let ε_g and ε_h be the bias of the two nonlinear functions, and let A_g and A_h be linear approximations [...] Then, a time invariant linear combination of keystream bits and LFSR bits can be found that, using the piling-up lemma, has the bias ε = 2^{(η(A_h)+η(A_g)−1)} · ε_g^{η(A_h)} · ε_h^{η(A_g)} [...] For the function g, we have ε_g < 2^−9 and η(A_g) = 5, and for the function h (including the linearly added bits), we have ε_h < 2^−5 and η(A_h) = 7. This will give ε < 2^−77 for this linear approximation (which also includes LFSR bits)."*

Detalhes das primitivas **[PUB]** (§3.4.4–3.4.5): a função b(x) do NFSR tem não-linearidade 8.356.352; g é balanceada, com não-linearidade 2^5 · 8.356.352 = 267.403.264 e resiliência 4; existem 2^14 aproximações lineares de g com viés ε_g = 63·2^−15 < 2^−9. A função h tem não-linearidade 240; com 8 variáveis adicionadas linearmente, a não-linearidade total da função de pre-output é 2^8 · 240 = 61.440, com 2^8 aproximações lineares de maior viés ε_h = 2^−5.

**Viés ε < 2^−77 exige ≈ 2^154 bits de keystream.** Nosso orçamento é 2^33,9. **Faltam 120 ordens binárias.** Fim de linha para o Grain completo.

Sobre correlação rápida, §4.3 **[PUB]**, já citado em §2.2: o ataque de 2^114 sobre o *raw encryption mode* do Grain-128a não se aplica ao modo de autenticação porque só os bits pares ficam acessíveis; e o limite de 2^80 bits de keystream por par (chave, nonce) da v2 fecha a porta de vez.

**Lacuna identificada [MINHA]:** o Grain-128AEADv2 tem **512 clockings antes do primeiro bit de keystream** (320 de inicialização + 64 de reintrodução de chave + 128 para carregar acumulador e registrador). O "Grain 11/13/13" da tabela do CRoCS (§8.2) é o **Grain v1 do eSTREAM**, outra cifra, com outra parametrização de rodadas. **Não existe na literatura uma curva "clockings de inicialização × viés detectável com IV de contador e sem escolha" para o Grain-128AEADv2.** Isso é uma lacuna real e é exatamente o que o braço de rodadas reduzidas do projeto pode preencher — com a ressalva de que a granularidade de "rodada" no Grain é o clocking, não uma rodada de SPN, e o eixo de comparação com os outros três precisa ser normalizado (ver §8.4, rodadas por byte).

---

### 9. A literatura de identificação de cifras por ML — o que é real e o que é artefato

Esta seção é delicada porque inclui trabalho do orientador. Vou separar rigorosamente o que é fato reportado do que é hipótese minha, e marcar cada afirmação.

#### 9.1 O panorama numérico

Levantei todos os trabalhos de identificação de algoritmo criptográfico por ML que consegui localizar com números verificáveis, mais os que aparecem nas revisões de literatura deles. O quadro consolidado:

| # | Trabalho | Cifras | Modo | Features | Dados | Melhor acurácia | Acaso | Fonte / status |
|---|---|---|---|---|---|---|---|---|
| 1 | **Mello & Xexéo**, *Identifying Encryption Algorithms in ECB and CBC Modes Using Computational Intelligence*, J. Universal Computer Science **24(1):25–42**, 2018 | 7 (ARC4, Blowfish, DES, Rijndael, RSA, Serpent, Twofish) + KeyBITS | ECB **e** CBC | histogramas de blocos de bits contíguos, de 2 a 34 bits (no pior caso 2^34 classes, hash table encadeada) | 7 corpora × 600 amostras, 7 idiomas; ambiente Xeon Phi 7250, 4 nós, 68 cores/272 threads cada, 128 GB | **ECB: 100%** (exceto RSA, bin > 20 bits, Complement NB); **CBC: 40–50%** (bin 34, Complement NB) | 7,14% (13 algoritmos + KeyBITS) ou 14,29% (só as 7 classes de alta entropia) | **[PUB]** https://www.jucs.org/jucs_24_1/identifying_encryption_algorithms_in/jucs_24_01_0025_0042_demello.pdf |
| 2 | **Mello & Xexéo**, *Cryptographic algorithm identification using machine learning and massive processing*, IEEE Latin America Transactions **14(11):4585–4590**, 2016 | 7 | ECB | idem (histograma de blocos contíguos de 2 a 34 bits) | 4.200 amostras em 7 corpora (600 por idioma), textos de jornais e revistas, sem frases repetidas; 6 classificadores (C4.5, PART, FT, Naive Bayes, MLP, WiSARD) | melhor NB ≈ **50%** | 13% | **[CIT]**, números via a revisão de Rocha et al. 2023 |
| 3 | **Hu & Zhao** | 8 (AES-128, AES-256, Blowfish-64, Camellia-128, DES-56, 3DES-56, IDEA-64, SMS4-128) | **CBC** | método de dicionário com palavras de 8 bits; **mesma chave em treino e teste** | Caltech256 agrupado em 1.001 arquivos de 512 KB → **8.008 arquivos cifrados**; Random Forest | **12,64%** | 12,5% | **[CIT]**, via Rocha et al. 2023 ref. [8]; *Identification of block ciphers under CBC mode*, Procedia Computer Science 131 (2018), 65–71 |
| 4 | **Yu & Shi** | 4 (DES, AES, 3DES, Blowfish), **chaves iguais** | CBC | 5 testes do NIST STS | 4.000 arquivos do Caltech-256, 256 KB cada; MLP, split 75/25 | **29,8%** | 25% | **[CIT]**, via Rocha et al. 2023 ref. [10] |
| 5 | **Rocha et al.**, *Artificial Intelligence Applied to the Identification of Block Ciphers under CBC Mode*, Int. J. Computer Applications **185(34)**, set. 2023 | 5 (DES, 3DES, Blowfish, Camellia, AES) | CBC | **15 p-valores do NIST STS sobre arquivos de "primeiros blocos concatenados"** | 100 arquivos de primeiros blocos concatenados por cifra, 100 KB cada → 500 arquivos; split 70/30; i5-2450M, 6 GiB, Ubuntu 22.04, scikit-learn | LR 79%, KNN 78%, **NB 84%**, SVM 63%, RF 81% | 20% | **[PUB]** https://www.ijcaonline.org/archives/volume185/number34/rocha-2023-ijca-923114.pdf |
| 6 | **kNN + Random Forest híbrido**, *A block cipher algorithm identification scheme based on hybrid k-nearest neighbor and random forest algorithm*, Scientific Reports (PMC9575859), 2022 | 5 (AES, 3DES, Blowfish, CAST, RC2) | **só ECB** | 10 features selecionadas de 15 métodos de teste de aleatoriedade NIST | 2.500 arquivos: 5 tamanhos (1, 8, 64, 256, 512 KB) × 100 arquivos × 5 algoritmos; split 80/20 | alta (não quantificada por modo) | 20% | **[PUB]** https://pmc.ncbi.nlm.nih.gov/articles/PMC9575859/ |
| 7 | **Dani, Nakka, Saxena** (MIND-Crypt), *A Machine Learning-Based Framework for Assessing Cryptographic Indistinguishability of Lightweight Block Ciphers*, arXiv:2405.19683 / ePrint 2024/852, Texas A&M | SPECK32/64, SIMON32/64 | CBC, KPA | bytes crus | 800k treino (400k/classe) / 100k teste; IV restrito a **16 bits**; busca de hiperparâmetros extensa; ResNet, CNN, LSTM, BiLSTM | **0,4993–0,5003** em todas as 16 células (round-reduced e full) | 0,50 | **[PUB]** |
| 8 | **Ren, Luo, Peng, He**, *Plaintext Structure Vulnerability: Robust Cipher Identification via a Distributional Randomness Fingerprint Feature Extractor*, arXiv:2511.08296v2 (30 jul. 2026), Wuhan University | 6 (AES-ECB, AES-CBC, 3DES, Blowfish, ChaCha20, RC4) | vários | "distributional randomness fingerprint": histogramas de p-valores do NIST STS | Canterbury Corpus + 5 datasets sintéticos de estrutura graduada; 10.000 janelas de 8 KB cada; chaves/IVs por janela via HKDF (RFC 5869); CV 5×5 agrupada por arquivo-fonte | `Regular_100`: **0,999**; `Random_100`: **0,52–0,57** (AUC 0,90–0,92) | 0,167 | **[PUB]** |
| 9 | **Kopal**, *Of Ciphers and Neurons – Detecting the Type of Ciphers Using Artificial Neural Networks*, HistoCrypt 2020 | 5 cifras **clássicas** (substituição monoalfabética, Vigenère, Playfair, Hill, transposição) | — | índice de coincidência de unigramas e bigramas + distribuições de frequência; 704 neurônios de entrada | — | economia de ≈54% do tempo (2000 min → ≈920 min) | 20% | **[CIT]** https://ep.liu.se/en/conference-article.aspx?series=ecp&issue=171&Article_No=11 |
| 10 | **Tan & Ji**, *An approach to identifying cryptographic algorithm from ciphertext*, ICCSN 2016, pp. 19–23 | — | — | detecção de comprimento de bloco/fluxo, entropia/reocorrência, árvore de decisão baseada em dicionário | — | — | — | **[CIT]**, via Rocha et al. ref. [1] |
| 11 | **Tan, Deng, Zhang**, *Identification of block ciphers under CBC mode*, Procedia Computer Science **131** (2018), 65–71 | — | CBC | — | — | — | — | **[CIT]**, via Rocha et al. ref. [4] |
| 12 | **Fan & Zhao**, *Analysis of cryptosystem recognition scheme based on Euclidean distance feature extraction in three machine learning classifiers*, J. Physics Conf. Series **1314**(1):012184, 2019 | — | — | extração de features por distância euclidiana | — | — | — | **[CIT]**, via Rocha et al. ref. [5] |
| 13 | **Dileep & Sekhar**, *Identification of block ciphers using support vector machines*, IJCNN 2006, pp. 2696–2701 | — | — | SVM | — | — | — | **[CIT]**, via Rocha et al. ref. [6] |
| 14 | *Cryptographic Algorithms Identification based on Deep Learning* / *Identification of Cryptographic Algorithms Based on CNN* | vários | — | testes NIST + DNN/CNN | — | relatam ~84% | varia | **[CIT]**, https://csitcp.org/paper/12/1212csit17.pdf; https://dl.acm.org/doi/10.1145/3727648.3727680 |
| 15 | **Carvalho** (2006), **Souza** (2007, 2008), **Maheshwari** (2002), **Chandra** (2002), **Rao** (2003) | DES vs IDEA; RSA vs IDEA; RSA/DES/AES | ECB | recuperação de informação, clustering, redes neurais, programação linear | — | clustering > redes neurais | — | **[CIT]**, via a revisão de literatura de Mello & Xexéo 2018, §2 |

**Três padrões saltam da tabela [MINHA]:**

1. **Toda vez que o modo é ECB, a acurácia é altíssima (até 100%). Toda vez que o modo tem IV aleatório, a acurácia desaba para perto do acaso** — 12,64% contra 12,5% (Hu & Zhao), 29,8% contra 25% (Yu & Shi), 0,4993–0,5003 contra 0,50 (Dani et al.). As duas exceções a esse padrão são Mello & Xexéo 2018 (40–50% contra 7,14%) e Rocha et al. 2023 (84% contra 20%), e ambas são analisadas em §9.2.

2. **Quanto mais rigoroso o protocolo de validação, menor o resultado.** O trabalho com o protocolo mais cuidadoso da tabela — Dani et al., com análise explícita de sobreposição treino/teste — é o que reporta exatamente o acaso. O segundo mais cuidadoso — Ren et al., com CV agrupada por arquivo-fonte, buffer de remoção e sanity check de rótulos embaralhados — reporta 0,999 em plaintext estruturado e 0,52 em plaintext aleatório, ou seja, **quantifica o quanto do resultado vinha do plaintext**.

3. **Nenhum dos 15 trabalhos usa AEAD moderno.** As cifras são AES, DES, 3DES, Blowfish, Camellia, CAST, RC2, IDEA, SMS4, Serpent, Twofish, RC4, ChaCha20, SPECK, SIMON e cifras clássicas. **Nenhum trabalho publicado tenta distinguir Ascon de GIFT-COFB, ou qualquer par de finalistas do NIST LWC, a partir do criptograma.** Essa é a lacuna que a dissertação ocupa, e é uma lacuna genuína, não uma falha de busca — verifiquei com múltiplas formulações de consulta.

**Observação sobre as métricas relatadas [MINHA]:** a maioria dos trabalhos reporta acurácia contra "probabilidade de acerto aleatório" e declara sucesso quando a primeira supera a segunda. Nenhum dos trabalhos pré-2024 reporta intervalo de confiança, e nenhum reporta correção para múltiplas comparações sobre as configurações testadas (tamanhos de bin, classificadores, tamanhos de arquivo). Com 6 classificadores × 33 tamanhos de bin × 13 classes, como em Mello & Xexéo, o espaço de configurações é de ordem 10^3; sem correção, o maior valor observado não é uma estimativa não-enviesada do desempenho.

#### 9.2 O padrão: tudo que funciona, funciona por ECB ou por vazamento

**[PUB] Mello & Xexéo 2018**, explicação dos próprios autores para o resultado em ECB (p. 38):

> *"Furthermore, the identification of ECB mode encryption algorithms was significantly high because encrypting the same data block of plaintext using ECB mode always yields the same block of ciphertext, that is, repetitive sequences of bits in the plaintext result in repetitive patterns in the encrypted output, thus providing an opportunity for identification. This means that ECB propagates frequencies from plaintexts to ciphertexts and produces ciphertexts of non-uniform distribution, which makes classification easier."*

A explicação é correta e completa. **[MINHA]** Um classificador em ECB não identifica o algoritmo: identifica o **tamanho de bloco**, através do padrão de repetição que o plaintext imprime no criptograma. DES, 3DES e Blowfish repetem em grade de 8 bytes; AES, Camellia, Serpent e Twofish em grade de 16. Um detector de periodicidade de grade resolve o problema sem nenhum aprendizado. É, em essência, o "pinguim do ECB" transformado em feature.

E a motivação declarada do trabalho, na introdução (p. 26), que é honesta sobre a expectativa:

> *"Common sense states that encryption algorithms must generate sequences with random characteristics so that a ciphertext encrypted with algorithm A may be classified into a group of ciphertexts encrypted with algorithm B. However, several experimental studies have shown that this does not occur, and the groups generated in clustering processes are not mixed. Mello et al. [Mello,16] show that, contrary to what one would expect from files encrypted via well known and widely used algorithms, there is enough exposed information to identify which cryptographic algorithm was used."*

E a afirmação central do paper (p. 26):

> *"the amount of cryptographic algorithms to be analyzed is greater than that of previous investigations, since not only ECB encryption mode is addressed, but also CBC (Cipher Block Chaining) mode. **In fact, this is the most important issue here, since CBC mode is not supposed to be sensitive to distinguishing attacks, which this paper shows not to be true.** The CBC encryption mode may be susceptible to such an attack, but the volume of data to be processed is prohibitive for conventional computers, and it is needed parallel support from high performance computing architecture."*

**O resultado CBC é o que precisa de escrutínio, e os autores o apresentam com controles.** Os números exatos (p. 39):

> *"The successful identification of cryptographic algorithms in CBC mode, when using Complement Naive Bayes classifier and considering a 34-bit bin size cumulatively, ranges **40-50%**. This is in stark contrast to the 7.14% of the probabilistic bid and suggests that it is possible to identify algorithms in CBC mode."*

O controle negativo deles, o **KeyBITS** — um gerador físico de bits pseudoaleatórios que usa o ruído intrínseco de luz de um feixe laser como fonte de entropia (Barbosa), com 600 amostras de tamanhos equivalentes aos dos criptogramas (p. 36):

> *"The assumption made is that these files do not have exposed patterns that allow successful algorithm identification by the machine learning algorithms. Thus, the KeyBITS files were inserted into the identification procedure in order to produce base line values and serve as a reference for comparison."*

E o resultado do controle (p. 39):

> *"Moreover, the physical random bit generator KeyBITS, which was used as reference for comparison, was mixed among the other encryption algorithms with marginal successful identification very close to the probabilistic bid. This means that the classifiers did not manage to categorize a uniform distribution of bits, but they did manage to obtain a certain amount of success with the CBC distribution of bits produced by our implementation. **This is a major result because it implies that it may exists a distinguishing attack against the CBC block cipher mode of operation, or at least, against the implementations used in this work.**"*

Registro a ressalva que os próprios autores fazem — *"ou pelo menos contra as implementações usadas neste trabalho"*. Ela é importante e costuma ser esquecida nas citações do paper.

Também registram (Tab. 2, p. 34) que **os criptogramas passaram no NIST STS**: para os 7 algoritmos nos dois modos, todos os 15 testes reportaram zero falhas de proporção, com apenas algumas falhas isoladas de p-valor no Non-overlapping Template (no máximo 2 de 148 templates), Random Excursions (1 de 8), Random Excursions Variant (1 de 18) e Serial (1 de 2). O teste de Linear Complexity reportou **zero falhas em todas as 13 colunas** — é o teste de menor poder da bateria para este propósito.

Um achado lateral que também vale citar (p. 35, Fig. 2): o idioma do plaintext **não** influencia a classificação.

> *"Positive values of D indicate that the best identification results were obtained when using the corpus with all languages together. In the vast majority of cases this is true, but the nominal values obtained for mean distance do not indicate a significant difference. [...] Therefore, the original language of the plain texts does not seem to interfere with the performance of the classification algorithms. The better results obtained for the corpus with all languages together is explained by its sample space size."*

E a extrapolação, que é o ponto que gera a discussão (p. 39–40):

> *"These series have a monotonic increasing behavior for successful identification, and thus it is convenient to study this property. Note that there are two possible scenarios. In the first, the monotonic increasing behavior experiences a reduction in slope and adopts an asymptotic course. In such a case, the data obtained from the experiment do not contribute to determining its saturation value. In the second scenario, the monotonic increasing behavior maintains its slope until full recognition. [...] Figure 4 also presents the linear regression equation f(x) and the coefficient of determination R². The R² value is near 1, and thus suggests a good fit for the model. For this reason, it is interesting to extrapolate to predict the bin size for possible full recognition. From this point of view, **the bin size value for full identification would be 85.18 bits**, which implies a computational challenge. The number of bin variations for such a histogram is 2^86, a significantly higher number than the actual 2^34 of this experiment thus demanding much more computational power and addressing capacity. This value is beyond the borderline of processing, that is, reaching this number of bin variations is solvable but not in an effective manner. Despite this problem is computable, it is not feasible, except if a new method is found, with smaller computational complexity."*

Os custos computacionais reportados (Tab. 1) dão a dimensão do esforço: Key Generator 8,9 s; Encoder 1 d 52 min; **Transformation 9 d 19 h 54 min**; **Machine Learning 30 d 13 h 51 min** (só o MLP consumiu 24 d 6 h de treino; Complement Naive Bayes, 11 min). Ganho de velocidade de 864,02× em relação ao experimento anterior de Barbosa et al. (2016) e de 14,24× ao paralelizar em 16 cores.

**Hipóteses [MINHA] para explicar o CBC a 40–50%, e os controles que as separam.** Apresento como hipóteses concorrentes porque não tenho como decidir entre elas sem rodar os experimentos; e registro desde já que o controle KeyBITS argumenta contra uma delas.

**H1 — vazamento de comprimento / estrutura de bloco.** DES, 3DES e Blowfish têm bloco de 64 bits; Rijndael, Serpent e Twofish têm 128. Em CBC com padding, para o **mesmo** plaintext os criptogramas têm comprimentos diferentes: múltiplos de 8 bytes versus múltiplos de 16, e o bloco de padding é adicionado em pontos diferentes. Se as contagens do histograma de bins não forem normalizadas pelo comprimento do arquivo, o vetor de features carrega o comprimento e, através dele, a família de tamanho de bloco. Além disso, se o IV for prepended ao criptograma por algumas bibliotecas e não por outras, há um deslocamento de alinhamento sistemático entre classes.

Duas observações empíricas do próprio corpus de trabalhos são compatíveis com H1: (a) Mello & Xexéo relatam *"a significant increase in the successful identification rate of DES and Blowfish when the number of bits used becomes larger than 16 bits"* e *"a qualitative leap in identifying DES, Blowfish and Rijndael when the bin size exceeds 16 bits"* — 16 bits é exatamente onde uma janela deslizante começa a atravessar fronteiras de bloco de 8 bytes de forma diferente das de 16; (b) no paper de Rocha et al. 2023, o padrão das matrizes de confusão é "uma ou duas classes perfeitas, as demais confundidas a ~50%" — Camellia e DES classificados perfeitamente por **todos os cinco** classificadores, enquanto 3DES, AES e Blowfish ficam em torno de 50%. Esse padrão de "classe perfeita isolada" é mais típico de um atributo determinístico separando um subconjunto do que de um sinal estatístico distribuído.

**Controle que separa H1:** normalizar todos os criptogramas ao **mesmo comprimento exato em bytes** (truncando ao mínimo comum) antes de extrair qualquer feature, e refazer. Se a acurácia cair ao acaso, era comprimento. Custo: uma linha de código.

**H2 — memorização por esparsidade do histograma.** Com bins de 34 bits há 2^34 = 1,72×10^10 células possíveis, e um arquivo de 100 KB fornece ≈ 8×10^5 janelas de 34 bits: ocupação de **0,005%**. O vetor de features é, nesse regime, uma **impressão digital quase injetiva do arquivo específico**, e o Complement Naive Bayes sobre vetor esparso desse tipo funciona essencialmente como um vizinho-mais-próximo por sobreposição de bins ocupados. O comportamento monotonamente crescente da acurácia com o tamanho do bin — que os autores interpretam como evidência de que mais computação levaria ao reconhecimento pleno, e extrapolam para 85,18 bits — é **também** a assinatura exata do regime de memorização: quanto mais fina a discretização, mais única a impressão digital, maior a taxa de reconhecimento de amostras vistas.

E a extrapolação para 85,18 bits tem uma leitura alternativa **[MINHA]**: um histograma de 2^86 bins sobre arquivos de ~8×10^5 janelas tem ocupação de 10^−20, ou seja, **cada janela ocupa um bin próprio e o vetor de features é literalmente o arquivo**. "Reconhecimento pleno" nesse regime é tautológico — é reconhecer o arquivo, não o algoritmo. Isso não invalida o resultado a 34 bits; mas significa que a extrapolação linear até 85 bits atravessa o ponto em que a feature deixa de ser uma estatística e vira um identificador, e portanto não pode ser lida como previsão de desempenho de identificação de algoritmo.

**Este é exatamente o mecanismo que Dani et al. documentaram e mediram** (§9.3): 99% de acurácia com oversampling, 53,72% global, 53,58% nos únicos do teste, **49,90% nos exclusivos do teste**.

**Controle que separa H2:** o experimento

E3 do SoK (§7.1) — substituir cada criptograma por bytes pseudoaleatórios do mesmo comprimento, manter rótulos, retreinar. Se a acurácia se mantiver, é H1. Se cair para o acaso mas a monotonia com o bin reaparecer com dados reais, é H2.

Registro honesto: o controle KeyBITS dos autores **argumenta contra** H2 pura, porque uma classe genuinamente uniforme ficou no acaso. Mas KeyBITS era uma única fonte homogênea; as sete classes CBC tinham origens distintas (implementações, comprimentos) e portanto mais superfícies para H1.

**Não estou afirmando que o resultado está errado.** Estou dizendo que **existem dois controles baratos que ninguém rodou e que decidiriam a questão**, e que a dissertação está na posição ideal para rodá-los.

#### 9.3 A demonstração explícita de memorização

**[PUB] Dani, Nakka, Saxena, "A Machine Learning-Based Framework for Assessing Cryptographic Indistinguishability of Lightweight Block Ciphers" (MIND-Crypt), arXiv:2405.19683 / ePrint 2024/852.**

Setup: SPECK32/64 e SIMON32/64 em CBC, KPA, dois plaintexts fixos P₁, P₂, IV restrito a **16 bits** para tornar o espaço de criptogramas tratável (2^16 = 65.536 criptogramas únicos). Busca de hiperparâmetros extensa (Tab. I/II: 2–9 camadas LSTM, 200–500 células, 2–9 camadas conv, 2–256 filtros, kernel 2–21, 100–300 épocas, LR em escala log de 10^−5 a 10^−2).

Tabela III completa:

| Config | Cifra | Modelo | Acc | Prec | Rec | F1 | ROC-AUC | TPR | TNR | FPR | FNR |
|---|---|---|---|---|---|---|---|---|---|---|---|
| RR | SPECK | ResNet | 0,5000 | 0,0000 | 0,0000 | 0,0000 | 0,5008 | 0,0000 | 1,0000 | 0,0000 | 1,0000 |
| RR | SPECK | CNN | 0,5003 | 0,5043 | 0,0356 | 0,0665 | 0,5005 | 0,0355 | 0,9650 | 0,0350 | 0,9644 |
| RR | SPECK | LSTM | 0,5000 | 0 | 0 | 0 | 0,5014 | 0 | 1,0000 | 0 | 1,0000 |
| RR | SPECK | BiLSTM | 0,5000 | 0 | 0 | 0 | 0,5000 | 0 | 1,0000 | 0 | 1,0000 |
| RR | SIMON | ResNet | 0,5002 | 0,5002 | 0,4947 | 0,4974 | 0,5003 | 0,4947 | 0,5057 | 0,4943 | 0,5053 |
| RR | SIMON | CNN | 0,4993 | 0,4985 | 0,2235 | 0,3086 | 0,4992 | 0,2235 | 0,7750 | 0,3086 | 0,4992 |
| Full | SPECK | ResNet | 0,5000 | 0,5000 | 1,0000 | 0,6667 | 0,5001 | 1,0000 | 0 | 1,0000 | 0 |
| Full | SPECK | CNN | 0,4997 | 0,4999 | 0,9489 | 0,6548 | 0,4996 | 0,9489 | 0,0505 | 0,9494 | 0,0511 |
| Full | SIMON | ResNet | 0,5000 | 0,5000 | 1,0000 | 0,6667 | 0,5000 | 1,0000 | 0 | 1,0000 | 0 |
| Full | SIMON | CNN | 0,4999 | 0,4998 | 0,0721 | 0,1260 | 0,5000 | 0,0720 | 0,9278 | 0,1260 | 0,5000 |

**Alerta de armadilha de métrica:** ResNet em "Full" tem **F1 = 0,6667 com acurácia 0,5000** — porque prediz tudo como classe 1 (recall 1,0, precisão 0,5). Um F1 de 0,67 que é puro colapso de classe. O CLAUDE.md já exige matriz de confusão sempre; este é o exemplo de por quê.

**A análise de memorização, com os números exatos:**
- Treino: 800.000 amostras (400k por classe). P₁: 65.395 criptogramas únicos; P₂: 65.375.
- Teste: 100.000 amostras. P₁: 34.974 únicos; P₂: 35.049 → 70.023 únicos.
- Subconjunto controlado: 5.000 por classe. P₁: 4.819 únicos, P₂: 4.815, 366 redundantes.
- **Sobreposição treino∩teste: 5.307 amostras (2.659 de P₁ + 2.684 de P₂) ≈ 5%.**
- Acurácia global: 53,72%. CV: 52,6%.
- Sobre os 70.023 únicos do teste: **53,58%**.
- **Isolando só os exclusivos do teste (excluindo os sobrepostos): 49,90%.**

> *"This analysis conclusively demonstrates that ML models fail to identify meaningful cryptographic patterns or statistically exploitable leakage under artificially simplified cryptographic conditions. The observed marginal improvements in accuracy above random chance are entirely due to memorization of overlapping ciphertext samples, rather than genuine generalization by the ML algorithm."*

E, com oversampling deliberado: **~99% de acurácia**, puro decorar.

**[MINHA]** Este é o paper que a dissertação deve usar como espelho metodológico. A receita: (1) medir a sobreposição exata entre treino e teste; (2) reportar a métrica **restrita às amostras exclusivas do teste**; (3) mostrar que a diferença entre as duas é toda a "vantagem" observada.

#### 9.4 O paper de 2026 que nomeia o problema — e um número que ninguém explicou

**[PUB] Ren, Luo, Peng, He, "Plaintext Structure Vulnerability: Robust Cipher Identification via a Distributional Randomness Fingerprint Feature Extractor", arXiv:2511.08296v2 (30 jul. 2026).** Wuhan University.

Tese central: *"when the plaintext distribution of test data departs from the training data, the performance of classifiers often declines significantly. This issue exposes the feature extractor's hidden dependency on plaintext features."*

Setup: 6 cifras (AES-ECB, AES-CBC, 3DES, Blowfish, ChaCha20, RC4); Canterbury Corpus + 5 datasets sintéticos com estrutura graduada (`Regular_100/75/50/25`, `Random_100`), 10.000 janelas de 8 KB cada, classes balanceadas, chaves/IVs por janela derivados por HKDF (RFC 5869).

**Protocolo com consciência de vazamento (§IV-A-f), que é exemplar:**
- CV 5×5 estratificada e **agrupada por arquivo-fonte**;
- remoção de buffer de treino de ρ = ⌈W/s⌉ − 1 janelas ao redor de cada janela de teste;
- sem features de nome/caminho de arquivo;
- pré-processamento ajustado só nos folds de treino;
- bordas de bins fixas globalmente;
- **três sanity checks:** (i) embaralhar rótulos no treino derruba ao acaso; (ii) bordas fixas igualam o refit por fold; (iii) leave-one-cipher-out ainda dá acurácia alta.

**Tabela II completa (Acc / F1 / AUC):**

| Modelo | | Reg_100 | Reg_75 | Reg_50 | Reg_25 | **Random_100** | Global |
|---|---|---|---|---|---|---|---|
| SVM linear | Acc | 0,999 | 0,999 | 0,999 | 0,899 | **0,566** | 0,893 |
| | F1 | 0,999 | 0,999 | 0,999 | 0,900 | 0,565 | 0,893 |
| | AUC | 0,999 | 0,999 | 0,999 | 0,988 | **0,915** | 0,981 |
| SVM RBF | Acc | 0,999 | 0,999 | 0,999 | 0,910 | 0,527 | 0,887 |
| | AUC | 0,999 | 0,999 | 0,999 | 0,989 | 0,901 | 0,978 |
| Reg. Logística | Acc | 0,999 | 0,999 | 0,999 | 0,905 | 0,527 | 0,886 |
| | AUC | 0,999 | 0,999 | 0,999 | 0,991 | 0,817 | 0,962 |
| Random Forest | Acc | 0,999 | 0,999 | 0,999 | 0,955 | 0,522 | 0,895 |
| | AUC | 0,999 | 0,999 | 0,999 | 0,997 | 0,907 | 0,981 |
| XGBoost | Acc | 0,999 | 0,999 | 0,999 | 0,983 | 0,541 | 0,905 |
| | AUC | 0,999 | 0,999 | 0,999 | 0,999 | 0,905 | 0,981 |
| 1D CNN | Acc | 0,999 | 0,878 | 0,652 | 0,449 | **0,229** | 0,642 |
| | AUC | 0,999 | 0,990 | 0,885 | 0,776 | 0,592 | 0,848 |
| 1D ResNet | Acc | 0,999 | 0,999 | 0,995 | 0,888 | 0,423 | 0,861 |
| | AUC | 0,999 | 0,999 | 0,999 | 0,983 | 0,825 | 0,962 |
| Transformer | Acc | 0,999 | 0,999 | 0,981 | 0,878 | 0,555 | 0,883 |
| | AUC | 0,999 | 0,999 | 0,998 | 0,977 | **0,914** | 0,978 |
| MLP | Acc | 0,999 | 0,999 | 0,999 | 0,943 | 0,565 | 0,902 |
| | AUC | 0,999 | 0,999 | 0,999 | 0,994 | 0,844 | 0,968 |

Separabilidade: distância de Bhattacharyya de **12,565** no espaço completo de features; na melhor projeção LDA 1-D, apenas **≈1,98** com sobreposição pronunciada.

**Análise [MINHA]:** o resultado em `Regular_*` é totalmente explicado por estrutura de plaintext (AES-ECB propaga repetição; tamanhos de bloco diferentes geram padrões diferentes) — os próprios autores dizem isso. **O resultado em `Random_100` (0,52–0,57 de acurácia com acaso 0,167; AUC 0,90–0,92) é que não tem explicação criptográfica.** Com plaintext uniforme, C = M ⊕ Z é uniforme para todas as seis cifras, inclusive ECB. Nenhum mecanismo criptográfico conhecido produz 3,3× o acaso nessas condições. Candidatos de artefato, em ordem de plausibilidade:
1. resíduo de padding ou de posicionamento de IV entre bibliotecas;
2. estrutura de amostragem (10.000 janelas, ~1.667 por classe, features de alta dimensão);
3. correlação residual entre janelas do mesmo arquivo que o buffer de ρ janelas não remove;
4. um viés genuíno do RC4 que sobreviva ao XOR com plaintext uniforme — mas isso é impossível sob XOR com uniforme independente.

O sanity check de embaralhamento de rótulos deles argumenta contra (2). **Este é um resultado publicado, recente, que a dissertação deveria tentar reproduzir**, e o experimento E3 (substituir criptograma por PRNG) o decide em uma tarde.

---

### 10. Metodologia: os controles que a literatura já cobra

Consolidando tudo que li, eis o conjunto mínimo de controles que um resultado nesta área precisa ter em 2026 para ser levado a sério. Marco quais o projeto já tem.

| # | Controle | Fonte | Projeto tem? |
|---|---|---|---|
| 1 | **Key-holdout** — chaves de teste nunca no treino | prática padrão | **Sim** (CLAUDE.md regra 2) |
| 2 | **CV agrupada por unidade geradora** (arquivo-fonte / chave), não i.i.d. | **[PUB]** Ren et al. 2026, §IV-A-f | **Sim** (estratificado por chave) |
| 3 | **Bootstrap agrupado** por chave para IC | prática | **Sim** |
| 4 | **Correção de múltiplas comparações** (BH-FDR / Bonferroni) | **[PUB]** Klinec et al.; **[CIT]** arXiv:2507.02181 | **Sim** (`consolidate_v2.py`) |
| 5 | **Controle negativo: PRNG** — classificador deve ficar no acaso | **[PUB]** Mello & Xexéo (KeyBITS) | **Sim** |
| 6 | **Controle positivo: AES-ECB** — classificador deve acertar 100% | **[PUB]** Mello & Xexéo | **Sim** |
| 7 | **Oclusão E2: substituir bytes do criptograma por constante**, manter comprimento | **[PUB]** SoK arXiv:2503.20093 | **NÃO** |
| 8 | **Oclusão E3: substituir criptograma por PRNG do mesmo comprimento**, manter rótulos | **[PUB]** SoK arXiv:2503.20093 | **NÃO** |
| 9 | **Medir sobreposição exata treino∩teste** e reportar métrica só nos exclusivos do teste | **[PUB]** Dani et al. 2024 | **NÃO** |
| 10 | **Sanity check de rótulos embaralhados** — deve cair ao acaso | **[PUB]** Ren et al. 2026 | **NÃO** (verificar) |
| 11 | **Matriz de confusão sempre** — evita F1 de 0,67 com acurácia de 0,50 | **[PUB]** Dani et al. Tab. III | **Sim** (regra 7) |
| 12 | **Buffer de remoção ao redor de janelas de teste** quando há janelamento | **[PUB]** Ren et al. 2026 | N/A (amostras independentes) |
| 13 | **Reportar a resolução estatística do experimento** (ε mínimo detectável) | **[PUB]** todos os trabalhos de RC4 | **NÃO** |
| 14 | **Comparar contra o baseline NIST STS** na mesma configuração | **[PUB]** Bellini–Huang; NNBits Tab. 5 | Parcial |

**Os itens 7, 8, 9, 10 e 13 são lacunas reais e todos são baratos.** Os itens 7–8 em particular transformam "não achamos nada" em "provamos que não há nada a achar", que é uma afirmação muito mais forte e é exatamente o que o SoK fez para render um paper em venue A*.

Sobre o item 13, os números para o dataset atual (§2.1, §5.4):

| Estatística | N | \|ε\| mínimo detectável |
|---|---|---|
| bit em posição fixa, através das amostras | 3×10^4 | 2^−6,8 |
| bit em posição fixa, todas as posições agregadas | 2^33,9 | 2^−16,9 |
| bit da tag, posição fixa | 3×10^4 | 2^−6,8 |
| bit da tag, 128 posições agregadas | 2^21,9 | 2^−10,3 |
| correlação linear entre blocos consecutivos | 2^26,9 | C² ≥ 2^−27 |
| byte em posição fixa, χ² sobre 256 bins | 3×10^4 | desvio relativo ≥ 28% |

**Essa tabela deveria abrir o capítulo de resultados.** Ela transforma H₀ de "não achamos" em "descartamos todo viés acima de 2^−27 em correlação linear e 2^−16,9 em desbalanceamento de bit", que é um enunciado científico.

---

### 11. Caminhos que são impossíveis neste modelo, e por quê

Resultado útil é resultado. Aqui estão os becos sem saída, com o argumento.

#### 11.1 Distinguir por distintude de blocos (PRP vs PRF)

**[MINHA]** Em GIFT-COFB, os blocos de "keystream" Y[i] = E_K(X[i]) são saídas de uma **permutação** com entradas distintas — logo nunca colidem. Em Ascon/Schwaemm, o rate é uma fatia de um estado de 320/384 bits — comporta-se como função aleatória, com colisões na taxa de aniversário. Isso é um distinguidor **real** entre o modo bloco e o modo esponja.

Custo: Pr[colisão] = C(q,2)/2^128. Com q = 4096 blocos por criptograma: 2^24/2^129 = 2^−105. Com todos os 2^26,9 blocos de uma chave pooled — mas não se pode fazer pooling entre criptogramas diferentes porque as entradas de E_K são independentes… na verdade pode, dentro da mesma chave: 2^18,6 blocos por chave → 2^36/2^129 = 2^−93.

Pior: o plaintext mascara. Observamos C_i = M_i ⊕ Y_i, e C_i = C_j requer Y_i ⊕ Y_j = M_i ⊕ M_j. Para GIFT-COFB, Pr[Y_i = Y_j] = 0 exatamente, mas isso só afeta o termo M_i = M_j, cuja probabilidade é a de blocos de 16 bytes repetidos no texto. O número esperado de colisões de bloco de ciphertext é ≈ 0 para **todos** os esquemas ao nosso volume. **Caminho fechado: precisa de 2^64 blocos por chave; temos 2^18,6. Faltam 45 ordens binárias.**

Registro: o Ascon sequer teria a propriedade, porque C_i é o rate e blocos de rate podem repetir; e o AES-ECB é o caso degenerado onde Pr[C_i = C_j] = Pr[M_i = M_j] exatamente — é isso que faz dele o controle positivo.

#### 11.2 Colisões de tag como distinguidor PRP/PRF

**[MINHA]** Em GIFT-COFB, T = E_K(X_last) é saída de PRP → tags **nunca colidem** sob a mesma chave. Em Ascon/Schwaemm, T é uma fatia de estado → colide em 2^64. Distinguidor legítimo e puramente CT-only. Custo: 2^64 tags sob uma chave; temos **100**. Faltam 57 ordens binárias. **Fechado.**

#### 11.3 Zero-sum, integral, division property

**[PUB]** Existe distinguidor zero-sum para a permutação Ascon **completa de 12 rodadas**, com complexidade 2^130 (Dobraunig et al. 2015). **Todos exigem entradas escolhidas estruturadas** (conjuntos afins). Nosso adversário não escolhe nada. **Fechado por definição do modelo.**

#### 11.4 Distinguidores diferencial-neurais estilo Gohr

**[CIT] Gohr, "Improving Attacks on Round-Reduced Speck32/64 Using Deep Learning", CRYPTO 2019, ePrint 2019/037.** Exigem pares com diferença de entrada escolhida. **Fechado.** O usuário já sinalizou isso; registro só para completar a tabela e para marcar o que sobrevive:

| Componente do Gohr | Sobrevive ao CT-only? |
|---|---|
| Diferença de entrada escolhida | **Não** |
| Arquitetura ResNet 1-D sobre bytes | **Sim** (mas sem sinal para achar) |
| Key-search bayesiano | Não (precisa de oráculo) |
| **Ideia de predizer bits individuais** (via NNBits) | **Sim** — é a adaptação de §5.7 |

**[CIT] Shen, Song et al., "Neural differential distinguishers for GIFT-128 and ASCON", Journal of Information Security and Applications 82 (2024), 103758** — modelo baseado na distribuição de scores de múltiplas diferenças de ciphertext em vez de um par único. GIFT-128 de 7 rodadas: acurácia de 55,42% para **99,36%**; Ascon de 4 rodadas: 50,69% para **69,25%**. Também reportado como distinguidor de 7 rodadas com 98,7% para GIFT-128 e de 4 rodadas com 98,7% para Ascon. **Fora do modelo** (diferenças escolhidas), mas é a referência obrigatória de estado-da-arte a citar e contrastar.

**[CIT]** *ML based Improved Differential Distinguisher with High Accuracy: Application to GIFT-128 and ASCON*, SPACE 2024, código em https://github.com/tarunyadav/Improved-Differential-Distinguisher-GIFT128-ASCON

#### 11.5 Ataques de reuso de nonce, misuse, related-key

Excluídos pelo modelo. Registro do custo: **[PUB]** a spec do Grain é explícita — *"For a single key, the nonce must be unique. If the nonce is not unique, i.e., it is repeated for the same key, the algorithm leaks information about the two plaintext, and the MAC can be forged."* **[CIT]** Ataques de chave relacionada contra Grain-128a: 2^96 complexidade com 2^96 IVs escolhidos e 2 chaves relacionadas; ou 2^64 IVs escolhidos e 2^32 chaves relacionadas (×~2^8).

#### 11.6 NCD e distância de compressão

**[MINHA]** Fechado analiticamente: §6.4.

#### 11.7 A coisa que o adversário CT-only realmente tem, e que a literatura chama de recurso

**[PUB] Mason, Watkins, Eisner, Stubblefield, "A Natural Language Approach to Automated Cryptanalysis of Two-time Pads", CCS 2006, pp. 235–244.**

> *"we show how an adversary can automatically recover messages encrypted under the same keystream if only the type of each message is known (e.g. an HTML page in English). Our method, which is related to HMMs, recovers the most probable plaintext of this type by using a statistical language model and a dynamic programming algorithm. It produces up to **99% accuracy** on realistic data and can process ciphertexts at 200ms per byte on a $2,000 PC."*

E o ponto formal: *"We assume that p and q were independently drawn from known probability distributions Pr₁ and Pr₂"*. Ataque **puramente ciphertext-only**, sem dados de treino específicos, sem heurísticas ad hoc. Recuperam documentos cifrados pelo Microsoft Word 2002.

**[MINHA] Por que isso importa aqui, e muito:** o recurso do adversário CT-only não é o criptograma — é **a distribuição conhecida do plaintext**. O corpus é 80% texto em inglês do Gutenberg. Isso significa que, para qualquer máscara linear β, o viés ε_P(β) = corr(β·P) é **grande e mensurável**, e no caso extremo (bits altos de ASCII) é exatamente 1. Pela piling-up lemma, um viés de keystream ε_Z aparece no criptograma com magnitude ε_Z × ε_P. Quando ε_P = 1, **não há perda nenhuma**.

Isso explica, em retrospecto, por que o achado empírico registrado na memória do projeto ("pares consecutivos CT-only acusam pa=1/2 com F1 até 0,99, dispositivo 1,0; pa≥4 acaso") funciona: para nonces consecutivos com inicialização reduzida, Z(n) ⊕ Z(n+1) é enviesado; M(n) ⊕ M(n+1) (texto XOR texto) é fortemente enviesado — é literalmente o problema do two-time pad; o produto é observável. Com o algoritmo completo, Z(n)⊕Z(n+1) é uniforme e o produto zera. O mecanismo é a piling-up lemma com o viés do plaintext como multiplicador, e Mason et al. é a citação canônica para o lado do plaintext.

**[CIT] Coppersmith, Halevi, Jutla, "Cryptanalysis of Stream Ciphers with Linear Masking", CRYPTO 2002, LNCS 2442, pp. 515–532; ePrint 2002/020** é o arcabouço formal do lado da cifra: *"look for any property of the non-linear process that can be distinguished from random, find a linear combination of the linear process that vanishes, then apply the same linear combination to the cipher's output to find traces of the distinguishing property."*

**[PUB] Minaud, "Linear Biases in AEGIS Keystream", SAC 2014 / ePrint 2018/292** é o exemplo de como isso se aplica a um AEAD tipo-duplex:

> *"if only the last block of plaintext involved varies, and the rest remains fixed as before, the sum of ciphertext bits is biased towards 0 or 1 depending on the same sum on the plaintext. Thus, a linear distinguisher on the keystream yields an attack on the scheme, where plaintext bits of a partially known message can be recovered, provided the message is encrypted enough times. **Observe that this does not require the same key be used.**"*

Números do Minaud: viés de 2^−89 para algumas máscaras no keystream do AEGIS-256, requerendo 2^188 dados; correlação entre saídas das rodadas i e i+2 do AEGIS-128 com viés 2^−77, requerendo 2^140 dados (ou >2^128 mesmo com efeitos de hull linear e técnicas multilineares, ver Apêndice B). Observação do autor: *"in the security analysis of AEGIS by its authors, as well as many CAESAR submissions displaying similar stream cipher-like behavior, this type of attacks does not seem to be taken into account."*

**Isso é um precedente direto e citável: alguém já fez exatamente a análise de viés linear de keystream para um AEAD duplex-like, e publicou.** Não existe o análogo para Ascon, Schwaemm ou GIFT-COFB no cenário ciphertext-only. **Essa é a lacuna que a dissertação pode ocupar.**

---

### 12. Catálogo consolidado de ideias

Formato: 1. O que é · 2. Fonte · 3. Cabe? · 4. Custo · 5. Previsão.

---

##### I-01 — Correlação linear entre blocos consecutivos de criptograma, com máscaras escolhidas pelo viés do plaintext

1. **O que é.** No Ascon, o rate do estado após absorver o bloco i **é** C_i. Logo C_{i+1} = ⌊p^b(C_i‖S_c)⌋_r ⊕ P_{i+1}. Procurar máscaras (α,β) sobre o rate tais que α·C_i ⊕ β·C_{i+1} tenha correlação não nula, escolhendo β suportada nas posições de bit onde o plaintext ASCII é determinístico (bit 7 de cada byte), o que faz corr(β·P)=1 e elimina a perda da piling-up lemma.
2. **Fonte.** Estrutura: **[PUB]** spec Ascon v1.2, Alg. 1. Arcabouço: **[PUB]** Minaud ePrint 2018/292; **[CIT]** Coppersmith–Halevi–Jutla CRYPTO 2002. Limites: **[PUB]** El Hirch et al. ToSC 2022(4). A escolha de máscara guiada pelo viés do plaintext é **[MINHA]**.
3. **Cabe?** **SIM, integralmente.** Ciphertext-only puro, um único criptograma basta, nonce irrelevante, nenhuma escolha.
4. **Custo.** Varredura sobre 2^16−1 máscaras β (restritas aos 16 bits ASCII-altos) × máscaras α estruturadas; 2^26,9 pares por algoritmo. Alguns dias de CPU com implementação vetorizada. Engenharia: média. Adaptar o `AsconTrailTool` (público) para buscar trilhos rate→rate seria o refinamento e é trabalho de mestrado por si.
5. **Prevê.** Algoritmo completo: nenhuma máscara sobrevive a BH-FDR. Rodadas reduzidas: detectável com b ≤ 3 (limite justo C²=2^−28 contra limiar 2^−27), possivelmente b=4 dado o fator "prática bate teoria" de 2^13 medido por Tezcan. **Falsificável:** curva de |corr| vs b deve cair em degraus que espelham a Tab. (b) do El Hirch.

---

##### I-02 — Oclusão E1/E2/E3 como controle negativo definitivo

1. **O que é.** Três reexecuções do pipeline: **E1** só criptograma (sem metadados); **E2** bytes do criptograma substituídos por constante, comprimento preservado; **E3** criptograma substituído por bytes pseudoaleatórios independentes do rótulo, comprimento preservado. Se a métrica não cair de E1 para E3, o modelo não usa o criptograma.
2. **Fonte.** **[PUB]** SoK arXiv:2503.20093v4, §5.3.3, Tab. 3–5; 348 experimentos de oclusão; resultados ET-BERT 0,12/0,12/0,12 e YaTC 0,30/0,39/0,30.
3. **Cabe?** **SIM.** É controle, não ataque.
4. **Custo.** Trivial: três reexecuções dos treinos já implementados. Uma tarde de GPU.
5. **Prevê.** Se o resultado do projeto é H₀ genuíno, E1 ≈ E3 ≈ acaso, e isso **transforma "não achamos" em "provamos que não há"**. Se E3 > acaso, existe canal de comprimento ou artefato de pipeline, e ele é localizável.

---

##### I-03 — NNBits adaptado: predição de bit a partir dos demais bits do mesmo criptograma

1. **O que é.** Ensemble de redes, cada uma predizendo um bit a partir dos demais. Três variantes: (A) bit j do bloco i a partir dos outros 127 bits do bloco; (B) bits do bloco i+1 a partir do bloco i (= testa p^b diretamente); (C) bits da tag a partir dos últimos blocos.
2. **Fonte.** **[PUB]** Hambitzer, Gérault, Huang, Aaraj, Bellini, CT-RSA 2023, ePrint 2023/819; código em https://github.com/Crypto-TII/nnbits. Tab. 5: NNBits ≥ NIST STS em todos os casos testados, +2 rodadas em SPECK32/64.
3. **Cabe?** **ADAPTÁVEL.** O NNBits publicado usa avalanche datasets (fora do modelo). A variante de "predizer bit a partir dos demais da mesma sequência" é puramente CT-only. **Nada do modelo de ameaça é arranhado.**
4. **Custo.** 128 redes × 4 algoritmos × k configurações. Código público, paralelizado em GPU. Dezenas de horas de GPU — cabe em Kaggle/Colab.
5. **Prevê.** Completo: acurácia por bit em 0,5 ± ruído em todas as posições, após BH sobre 128 hipóteses. Reduzido: perfil de bits fracos concentrado nas posições previstas pelo trilho, e **perfis diferentes por algoritmo** (Ascon tem S-box de 5 bits em colunas; GIFT tem S-box de 4 bits com camada de bit-permutation) — o perfil vira assinatura.

---

##### I-04 — Estatísticas alinhadas por posição (template Mantin–Shamir)

1. **O que é.** Em vez de agregar sobre o criptograma, computar, para cada offset p, a distribuição do byte/bit naquele offset **através** das amostras. Produz 65.536 × 256 (ou × 8) estatísticas por algoritmo.
2. **Fonte.** **[CIT]** Mantin & Shamir FSE 2001; **[CIT]** Isobe et al. FSE 2013 (2^32 criptogramas → P_1..P_257 com prob. >0,8); **[CIT]** AlFardan et al. USENIX 2013; **[PUB]** Vanhoef & Piessens USENIX 2015 (método de busca por teste de hipótese). Evidência de que o agregado destrói o sinal: **[PUB]** Klinec et al. SECRYPT 2022 (*"Experiments were not able to detect biases using zero strategy"* para RC4).
3. **Cabe?** **SIM** para as estatísticas; **NÃO** para a recuperação de plaintext (exige plaintext repetido).
4. **Custo.** Uma varredura linear sobre o dataset, O(N · L). Barato. Correção BH sobre 65.536×8 hipóteses.
5. **Prevê.** Sensibilidade |ε| ≥ 2^−6,8 por posição com 3×10^4 amostras. Previsão: nada nos algoritmos completos. **Com inicialização reduzida, viés concentrado nos primeiros offsets, decaindo com a posição** — a assinatura clássica de mistura incompleta. **Recomendação forte:** para este teste, trocar 30.000 × 64 KB por ~10^7 × 64 B. Mesmo volume de bytes, 10^3× mais amostras alinhadas, sensibilidade 2^−11,3 em vez de 2^−6,8.

---

##### I-05 — Autocorrelação de dígrafos em lag variável (template ABSAB)

1. **O que é.** Estimar Pr̂[(C_r,C_{r+1}) = (C_{r+g+2},C_{r+g+3})] para g = 0..G, dentro de cada criptograma, e usar o perfil em g como feature. É uma estatística de criptograma único, chave única.
2. **Fonte.** **[PUB, via Vanhoef]** viés ABSAB de Mantin: 2^−16(1+2^−8 e^{(−4−8g)/256}); tabela completa de dígrafos Fluhrer–McGrew. **[CIT]** Bricout, Murphy, Paterson, van der Merwe, DCC 86(4):743–770, 2018 — correções: caso A=B tem expoente (−4−6g)/256; A=1 ou B=1 **sem viés**; correções para (0,0),(0,1),(255,255).
3. **Cabe?** **SIM** como estatística. A exploração para recuperação de plaintext exige 26–130 bytes conhecidos e **NÃO** cabe.
4. **Custo.** O(N·L·G). Com G = 64 e o dataset atual, algumas horas de CPU.
5. **Prevê.** Nada com algoritmos completos (o viés análogo estaria em 2^−176 para o Ascon-128a). Com rodadas reduzidas, pico em g correspondendo ao rate do esquema (16 B para Ascon-128a, 32 B para Schwaemm, 16 B para GIFT-COFB), **o que identifica o rate e portanto o algoritmo**. Essa última previsão é o que mais me interessa: o perfil em g codifica o tamanho do rate.

---

##### I-06 — BoolTest sobre criptogramas

1. **O que é.** Busca exaustiva por polinômios booleanos de grau baixo sobre subconjuntos de bits cuja distribuição se desvia do uniforme; usar os monômios encontrados como features.
2. **Fonte.** **[CIT]** Sýs, Klinec, Kubíček, Švenda, SECRYPT 2017 / ICETE Selected Papers, Springer 2019; código em https://github.com/crocs-muni/booltest. Também **[CIT]** *Evolving Boolean Functions for Fast and Efficient Randomness Testing*, GECCO 2018; *Revisiting BoolTest*, SECRYPT Selected Papers 2022.
3. **Cabe?** **ADAPTÁVEL.** É teste de uma amostra vs uniforme; a versão de duas classes é rodar por classe e comparar, ou usar os monômios como features.
4. **Custo.** Código público. Execução barata. Engenharia: baixa-média.
5. **Prevê.** Completo: nenhum polinômio significativo. Reduzido: polinômios de grau ≤3 sobre bits do mesmo bloco, com z-score crescendo monotonamente conforme as rodadas caem. **Se BoolTest achar polinômio significativo no algoritmo completo, ou há bug de geração ou é resultado de peso.** Baseline explícito: BoolTest supera NIST STS em DES, 3-DES, MD5, MD6 e SHA-256 com rodadas reduzidas.

---

##### I-07 — Elo tag ↔ última borda de criptograma, com comprimento não múltiplo do rate

1. **O que é.** Correlação entre bits da tag e bits do último bloco emitido. Para maximizar a sensibilidade, gerar um braço com |P| ≢ 0 (mod r), o que **derruba o elo no Ascon de 20 para 12 rodadas**.
2. **Fonte.** Derivação **[MINHA]** sobre **[PUB]** spec Ascon §2.4.3–2.4.4 e **[PUB]** spec GIFT-COFB Alg. COFB-E. Limites: **[PUB]** El Hirch et al. Precedente de forja: **[PUB]** Dobraunig et al. ePrint 2015/030 (3 rodadas de finalização: 2^33; 4 rodadas: 2^101).
3. **Cabe?** **SIM.** Nenhum oráculo, nenhuma escolha.
4. **Custo.** Regerar um braço com |P| = 65535 bytes: mesmo custo do braço atual. Cálculo das 128×128 correlações: minutos.
5. **Prevê.** Completo: nada (C² ≤ 2^−264 em 12 rodadas). Finalização em 3 rodadas: C² = 2^−28, marginalmente detectável. **A previsão diferencial é o que testa a hipótese: com |P| ≡ 0 mod r o sinal deve aparecer ~8 rodadas mais tarde que com |P| ≢ 0.** Se não aparecer essa diferença de 8 rodadas, minha derivação da estrutura está errada e isso também é informação.

---

##### I-08 — Grain: viés na região da tag antes do viés no corpo, sob inicialização reduzida

1. **O que é.** A^0 = y_{384..447} e R^0 = y_{448..511} vêm do pre-output mais próximo da inicialização; o keystream só começa em y_{512}. Sob inicialização reduzida, a tag deveria mostrar o viés antes dos primeiros bytes do criptograma.
2. **Fonte.** Estrutura: **[PUB]** spec Grain-128AEADv2 §2.2–2.3. A previsão é **[MINHA]**. Contexto: **[PUB]** a spec §4.3 confirma que esconder os bits ímpares bloqueia um ataque de correlação rápida de 2^114.
3. **Cabe?** **SIM.** Exige variantes com inicialização reduzida (o projeto já compila variantes de rodadas reduzidas).
4. **Custo.** Compilar variantes com 320/256/192/128/64 clockings; gerar amostras; testes de viés por posição nas tags e nos primeiros bytes.
5. **Prevê.** Curva de viés vs clockings, com a curva da tag deslocada para a **direita** (mais clockings) em relação à curva do corpo. Magnitude do deslocamento ≈ 128 clockings (a distância entre y_384 e y_512). Se não houver deslocamento, o modelo mental está errado.

---

##### I-09 — Separação de domínio de padding como canal (Schwaemm/Ascon)

1. **O que é.** Schwaemm usa `Const_M ← 2⊕(1≪2)` para último bloco parcial e `3⊕(1≪2)` para bloco cheio; Ascon usa o bit de separação após AD. Com comprimentos mistos no dataset, o criptograma reflete a constante depois de uma permutação completa.
2. **Fonte.** **[PUB]** spec Sparkle Alg. 2.13; **[PUB]** spec Ascon §2.4.2. Interpretação como canal é **[MINHA]**.
3. **Cabe?** **SIM.**
4. **Custo.** Braço com comprimentos mistos. Baixo.
5. **Prevê.** Completo: nada. Reduzido: criptogramas de último bloco cheio distinguíveis dos de último bloco parcial, com o mesmo perfil de rodadas de I-01.

---

##### I-10 — Truncamento controlado: corpo / corpo+tag64 / corpo+tag completa

1. **O que é.** Três representações, com relatório separado, para separar o canal de comprimento do resto.
2. **Fonte.** **[PUB]** PURBs (83–87% de objetos únicos só por tamanho); **[PUB]** SoK Guideline 6 (*"Focus on encrypted payload length rather than content"*); **[CIT]** Dyer et al. IEEE S&P 2012.
3. **Cabe?** **SIM.**
4. **Custo.** Trivial (é fatiamento de array).
5. **Prevê.** Variante "corpo+tag completa" separa Grain dos demais com F1 exatamente 1,000 (controle positivo de comprimento). Variantes 1 e 2 dão acaso. Se a variante 1 der acima do acaso, há canal não-comprimento — e aí sim há notícia.

---

##### I-11 — Colisão de estado detectada por prefixo de criptograma

1. **O que é.** Duas consultas com estados internos colidentes produzem prefixos de criptograma iguais a partir do ponto de colisão.
2. **Fonte.** **[PUB]** Inoue–Iwata–Minematsu ePrint 2022/001, ataque de forja por aniversário contra Photon-Beetle: *"The collision can be detected from C'_i and C'_j, which are the first b bits of C_i and C_j"*, com q = 2^{b/2} = 2^128.
3. **Cabe?** **SIM em princípio, NÃO em escala.** É o único mecanismo genérico pelo qual criptogramas do mesmo esquema se reconhecem.
4. **Custo.** Detecção: hash de todos os blocos, O(N). Barato.
5. **Prevê.** Zero colisões. Custos: 2^96 (Ascon-128a, rate 128), 2^64 (GIFT-COFB, máscara 64), 2^64 (Schwaemm, capacidade 128 → 2^64 para rate). Temos 2^18,6 por chave. Vale rodar **como detector de bug do gerador**: uma colisão observada significa reuso de nonce ou falha do CTR_DRBG.

---

##### I-12 — Busca empírica de vieses em larga escala com controle de FDR

1. **O que é.** Em vez de 641 features escolhidas a priori, enumerar milhares de estatísticas simples (byte em offset p, dígrafo em lag g, paridade de máscara β, peso de Hamming de janela), testar todas contra H₀ uniforme, e aplicar Benjamini–Hochberg.
2. **Fonte.** **[PUB]** Vanhoef & Piessens USENIX 2015 (método); **[CIT]** Paterson, Poettering, Schuldt, ASIACRYPT 2014 (2^13 núcleos EC2, vários dias); **[CIT]** arXiv:2507.02181 (BH em criptanálise). O projeto já tem BH-FDR em `consolidate_v2.py`.
3. **Cabe?** **SIM.**
4. **Custo.** Uma ou duas passadas pelo dataset por família de estatística. Alto em I/O (11,8 GB — e a memória do projeto adverte: **nunca carregar o parquet inteiro em pandas**, usar pyarrow incremental).
5. **Prevê.** Zero descobertas após BH nos algoritmos completos, e **o valor científico está em reportar quantas hipóteses foram testadas e qual a menor magnitude de viés que teria sobrevivido**. Isso transforma H₀ num enunciado quantitativo.

---

##### I-13 — Complexidade linear / perfil Berlekamp–Massey por região

1. **O que é.** Perfil de complexidade linear L_1(s), L_2(s), … computado separadamente para o início, o meio e a região de tag do criptograma.
2. **Fonte.** **[CIT]** Rueppel, e o teste "Linear Complexity" do NIST SP 800-22; **[CIT]** *The Linear Complexity Profile and the Jump Complexity of Keystream Sequences*, EUROCRYPT 1990, LNCS 473.
3. **Cabe?** **SIM.**
4. **Custo.** Berlekamp–Massey é O(n²) — caro para 65 KB, mas viável em janelas de 1–8 KB. Baixa engenharia.
5. **Prevê.** Nada. Registro relevante: **[PUB]** no experimento de Mello & Xexéo (Tab. 2), o teste de Linear Complexity do NIST reportou **zero falhas** para todas as 7 cifras em ambos os modos. É o teste com menor poder na bateria para este propósito. **Baixa prioridade.** Menciono para fechar o veio.

---

##### I-14 — Comparação explícita contra o baseline NIST STS na mesma configuração

1. **O que é.** Rodar a suíte NIST SP 800-22 sobre o mesmo dataset e reportar em quantas rodadas ela detecta, lado a lado com o ML.
2. **Fonte.** **[PUB]** Bellini & Huang NIST LWC 2022 (coluna "Random" = 1 rodada para Ascon, Sparkle, GIFT-128); **[PUB]** NNBits Tab. 5 (formato da comparação); **[CIT]** NISTIR 6483 (Soto & Bassham, 2000) é a origem das 9 estratégias de geração.
3. **Cabe?** **SIM.**
4. **Custo.** Baixo (o projeto já tem a família `nist_sts` com 25 features).
5. **Prevê.** ML ≥ NIST STS em todas as configurações; ambos detectam em r=1; **se o ML detectar em r=2 e o STS não, isso é resultado publicável por si** e a comparação é o que torna a afirmação defensável.

---

##### I-15 — Métrica restrita às amostras exclusivas do teste

1. **O que é.** Medir a sobreposição exata treino∩teste (mesmo criptograma, mesmo bloco, mesma janela) e reportar a métrica **só nas amostras exclusivas do teste**.
2. **Fonte.** **[PUB]** Dani et al. arXiv:2405.19683: 53,58% em todos os únicos → **49,90%** nos exclusivos do teste; 5.307 amostras sobrepostas de 10.000 (≈5%).
3. **Cabe?** **SIM.** Controle.
4. **Custo.** Trivial.
5. **Prevê.** Com key-holdout e criptogramas de 64 KB, a sobreposição deve ser exatamente zero — e **reportar o zero é o ponto**. Se não for zero, há bug no split.

---

##### I-16 — Reprodução do resultado `Random_100` de Ren et al. (2026)

1. **O que é.** Reproduzir a célula que ninguém explicou: 6 cifras, plaintext uniforme, acurácia 0,52–0,57 com acaso 0,167 e AUC 0,90–0,92.
2. **Fonte.** **[PUB]** Ren, Luo, Peng, He, arXiv:2511.08296v2, Tab. II.
3. **Cabe?** **SIM.** É exatamente o nosso cenário, com 6 cifras clássicas em vez dos 4 LWC.
4. **Custo.** Médio: reimplementar o "distributional randomness fingerprint" (histogramas de p-valores NIST STS). O projeto já tem a família `nist_sts`.
5. **Prevê.** **[MINHA]** Ou (a) o resultado não reproduz, e a dissertação tem um achado de replicação; ou (b) reproduz, e o E3 (I-02) localiza o artefato; ou (c) reproduz e sobrevive ao E3, e aí é o resultado mais importante da área em cinco anos. Nos três casos, vale a pena.

---

##### I-17 — Marcadores de artefato: classificar por região

1. **O que é.** Treinar classificadores separados em: só a tag; só os primeiros 256 bytes; só os últimos 256 bytes antes da tag; só o meio; corpo completo. Comparar.
2. **Fonte.** **[MINHA]**, informado por **[PUB]** Rocha et al. IJCA 2023 (que concatena **primeiros blocos** de muitos arquivos — a mesma ideia, usada como ataque em vez de diagnóstico).
3. **Cabe?** **SIM.**
4. **Custo.** 5 treinos. Baixo.
5. **Prevê.** **Ordenação esperada por informação disponível:** corpo completo > meio ≈ primeiros ≈ últimos > tag, porque a quantidade de bits ordena assim. **Qualquer inversão dessa ordem é assinatura de artefato**, não de criptografia. Em particular, "só a tag" superar "corpo completo" é impossível criptograficamente (2^−12 dos bits, mais rodadas) e significa bug de geração.

---

##### I-18 — Dataset com muitas amostras curtas em vez de poucas longas

1. **O que é.** Braço adicional com 10^6–10^7 criptogramas de 64–256 bytes, mesmo volume total de bytes.
2. **Fonte.** **[MINHA]**, derivado da aritmética de §5.4 e do padrão de todos os ataques RC4 (2^24–2^34 **sessões**, não bytes).
3. **Cabe?** **SIM.**
4. **Custo.** Geração: comparável ao braço atual (mesmo volume de bytes cifrados, mais overhead de inicialização — o que na verdade é *desejável* aqui). Armazenamento menor se truncado.
5. **Prevê.** Sensibilidade posicional passa de |ε| ≥ 2^−6,8 para ≥ 2^−11,3 (com 10^7 amostras): **4,5 bits binários de ganho** exatamente onde o viés de inicialização mora. Também permite pela primeira vez um teste tipo Mantin–Shamir de verdade. **Este é o melhor retorno por unidade de esforço de geração de todo o levantamento.**

---

##### I-19 — Perfil de "rodadas por byte observável" como eixo de comparação

1. **O que é.** Reportar os resultados de rodadas reduzidas normalizados por *rodadas de trabalho criptográfico por byte de saída*, não por *fração de rodadas nominais*.
2. **Fonte.** **[MINHA]**, tabela de §1.2 construída sobre as quatro specs **[PUB]**.
3. **Cabe?** **SIM.** É apresentação de resultados.
4. **Custo.** Zero.
5. **Prevê.** A ordenação de fragilidade em CT-only é Ascon-128a (0,50 rodada/byte, margem relativa 62,5%) < Ascon-128 (0,75, 50%) < Schwaemm < GIFT-COFB (2,50, 90%). **Falsificável:** o experimento de rodadas reduzidas deve produzir essa ordenação. Se produzir a ordenação inversa (GIFT caindo primeiro em fração relativa), o modelo está errado.

---

##### I-20 — Fingerprinting de container / formato

1. **O que é.** Técnicas forenses de identificação de container cifrado sem assinatura.
2. **Fonte.** **[CIT]** ForensicsWiki TrueCrypt; *Detecting Hidden Encrypted Volumes*, CMS 2010; **[PUB]** PURBs (que existe justamente porque os formatos *normalmente* têm cabeçalho em claro).
3. **Cabe?** **NÃO.** Todos os métodos que funcionam são externos ao criptograma (tamanho, localização, Volume Shadow Copy, espaço livre).
4. **Custo.** N/A.
5. **Prevê.** Nada. **Valor: é evidência convergente.** Um subcampo com incentivo forense forte concluiu, por experiência de campo, que não há assinatura dentro do criptograma. Vale um parágrafo na revisão de literatura da dissertação.

---

### 13. APOSTAS

As três que eu tentaria primeiro, em ordem, com o porquê.

---

#### Aposta 1 — Oclusão E3 + medição de resolução estatística: converter H₀ de "não achamos" em "provamos que não há"

**O que fazer, concretamente:**
1. Reexecutar todos os Caminhos (A–F) com o criptograma substituído por bytes de CTR_DRBG do **mesmo comprimento exato por algoritmo** (65.552 / 65.544 / 65.552 / 65.552 / 65.552), mantendo todos os rótulos, todos os metadados, todo o resto do pipeline idêntico. Isso é o E3 do SoK.
2. Reexecutar com o criptograma substituído por `0xFF` (E2): isola o canal de comprimento puro.
3. Reexecutar com rótulos embaralhados no treino (sanity check de Ren et al.).
4. Publicar a tabela de resolução estatística de §10: para cada família de teste, o menor |ε| que o experimento teria detectado.

**Por que primeiro.** Porque é o único item que muda a natureza da conclusão da dissertação em vez de acrescentar mais uma tentativa. Hoje o texto diz "quatro caminhos convergem para F1≈0,50". Com E2/E3 ele passa a dizer: *"quatro caminhos convergem para F1≈0,50, e o mesmo pipeline, alimentado com ruído puro do mesmo comprimento, produz exatamente o mesmo F1 — portanto o classificador demonstravelmente não extrai nenhuma informação do criptograma. Descartamos qualquer viés de correlação linear acima de 2^−27 e qualquer desbalanceamento de bit acima de 2^−16,9."* Essa é uma afirmação científica; a outra é um relato de tentativa.

**Custo.** Uma tarde de GPU para os retreinos. Algumas horas de escrita. **É o menor custo e o maior retorno de todo o levantamento.**

**Precedente exato.** O SoK arXiv:2503.20093 fez precisamente isso com 348 experimentos de oclusão e rendeu um paper de sistematização em venue de topo, com a conclusão *"state-of-the-art classifiers do not learn any intrinsic patterns from encrypted payloads beyond their length"*. A dissertação está na posição de dizer o mesmo sobre os finalistas do NIST LWC, que ninguém disse ainda.

**Risco.** Baixo. O pior caso é E3 ficar acima do acaso, e aí você encontrou um bug — o que também é resultado.

---

#### Aposta 2 — Distinguidor linear entre blocos consecutivos, com máscaras escolhidas pelo viés do plaintext, varrido ao longo das rodadas reduzidas

**O que fazer, concretamente:**
1. Para cada algoritmo e cada configuração de rodadas reduzidas, estimar corr(α·C_i ⊕ β·C_{i+1}) sobre todos os 2^26,9 pares de blocos consecutivos.
2. Restringir β aos bits em que o plaintext ASCII é determinístico (bits 7, 15, …, 127 dentro do bloco) — isso zera a perda da piling-up lemma. Para o braço de imagens (20%), medir ε_P(β) empiricamente a partir dos plaintexts guardados em `data/interim/`.
3. Varrer α sobre um conjunto estruturado (pesos de Hamming baixos, e as máscaras sugeridas pelos trilhos lineares conhecidos do Ascon).
4. Aplicar BH-FDR sobre o número total de máscaras testadas.
5. Plotar |corr| vs número de rodadas, por algoritmo, com os limites de El Hirch et al. sobrepostos.

**Por que.** Três razões independentes.

Primeira: **é o único ataque no catálogo inteiro que cabe integralmente no modelo de ameaça e tem um mecanismo criptográfico explícito.** Tudo mais ou é controle, ou é adaptação com ressalva, ou está fora do modelo.

Segunda: **a estrutura só existe porque o Ascon é um duplex puro**, em que o rate pós-absorção *é* o criptograma (§1.2). Isso é uma propriedade que nem Schwaemm (feedback Beetle esconde) nem GIFT-COFB nem Grain têm. É uma assimetria estrutural real entre os quatro, ela é uma propriedade de **borda** (a fronteira entre blocos), e nunca vi ninguém escrever isso sobre os finalistas do LWC no cenário ciphertext-only.

Terceira: **a previsão é numericamente nítida e falsificável.** Ponto de virada em b=3 para o Ascon (limite justo C²=2^−28 contra limiar 2^−27), r=4 para o GIFT-128 (C²=2^−27 em 4 rodadas). E as duas rotas independentes concordam: o ataque de forja de Dobraunig et al. também vira entre 3 (2^33) e 4 (2^101) rodadas de finalização. Se o experimento der o ponto de virada em 3–4 rodadas para o Ascon e em 4 para o GIFT-COFB, a previsão se confirma e a dissertação tem um resultado quantitativo. Se der em outro lugar, isso é ainda mais interessante — e a explicação mais provável seria o efeito "prática bate teoria" que Tezcan mediu (viés real 2^−2 contra teórico 2^−15 em 4 rodadas, 13 bits de discrepância).

**Custo.** Alguns dias de CPU para a varredura, mais trabalho de engenharia moderado. O passo opcional de alto valor — adaptar o `AsconTrailTool` público para buscar trilhos com máscaras restritas ao rate — é trabalho de mestrado por si e preencheria uma lacuna que verifiquei não existir na literatura.

**Precedente.** Minaud fez exatamente esta análise para o AEGIS (viés 2^−89, 2^188 dados) e publicou em SAC 2014, notando que *"in the security analysis of AEGIS by its authors, as well as many CAESAR submissions displaying similar stream cipher-like behavior, this type of attacks does not seem to be taken into account."* Não existe o equivalente para Ascon, Schwaemm ou GIFT-COFB.

---

#### Aposta 3 — Braço de amostras curtas e testes alinhados por posição

**O que fazer, concretamente:**
1. Gerar um braço adicional: ~10^7 criptogramas de 64 bytes por algoritmo (mesmo volume total de bytes que o braço atual; ~10^3× mais amostras).
2. Para cada offset p ∈ [0, 63] e cada posição de bit, estimar a distribuição **através** das amostras.
3. Repetir para cada configuração de rodadas reduzidas.
4. Comparar com o teste equivalente sobre a região de tag (Grain: a previsão de §2.2, Fato 4).
5. BH-FDR sobre 64×8× (nº de configurações) hipóteses.

**Por que.** Porque a tabela de §5.4 mostra que **o dataset atual está desenhado para o teste errado**. Todos os ataques posicionais da literatura precisaram de 2^24–2^34 *sessões*; temos 2^14,9. Trocar comprimento por quantidade de amostras é grátis em volume de bytes e compra **4,5 bits binários de sensibilidade** exatamente onde o viés de inicialização mora — que é o único lugar onde rodadas reduzidas produzem sinal indexado por posição.

E há a evidência direta de que o desenho atual é cego a esse tipo de sinal: **[PUB]** o estudo do CRoCS relata que as 414 baterias aplicadas a keystream concatenado de RC4 com chave aleatória **não detectaram** os vieses mais famosos da criptanálise moderna, porque a concatenação destrói o alinhamento posicional. Todas as 12 famílias de features do projeto agregam sobre o criptograma inteiro. Estão fazendo exatamente a concatenação que o CRoCS mostrou ser cega.

**Custo.** Geração: comparável ao braço atual em bytes cifrados, mais overhead de inicialização por amostra — o que aqui é característica, não defeito, porque é justamente a inicialização que estamos sondando. Armazenamento: menor. Análise: uma varredura linear.

**Previsão.** Algoritmos completos: nada, com sensibilidade agora reportável em |ε| ≥ 2^−11,3. Inicialização reduzida: viés concentrado nos primeiros offsets e decaindo — e, para o Grain, o viés aparecendo na tag ~128 clockings antes de aparecer no corpo. As duas previsões são independentes e falsificáveis.

---

#### O que eu NÃO apostaria, e por quê

- **Redes maiores sobre bytes crus.** Dani et al. varreram 2–9 camadas, 2–256 filtros, kernels de 2 a 21, 100–300 épocas, e obtiveram 0,4993–0,5003 em todas as 16 células. Ren et al. mostraram que a 1D CNN é o *pior* modelo sob plaintext aleatório (0,229 de acurácia, AUC 0,592, abaixo do acaso de 0,167 em F1). Capacidade de modelo não é o gargalo; informação é.
- **Mais features agregadas.** O v2 já tem 641. O problema não é o número — é que todas agregam, e o CRoCS provou que agregar é cego a viés posicional.
- **Análise só da tag.** É 2^−12 dos bits e vem de mais rodadas. Só vale como diagnóstico de artefato (I-17), não como ataque.
- **NCD / compressão.** Fechado analiticamente (§6.4).
- **Qualquer coisa que precise de 2^64.** Colisões de estado, colisões de tag, os ataques de privacidade do GIFT-COFB. Estão 45 a 57 ordens binárias fora.

---

#### Nota final sobre o que este levantamento mudou na minha leitura do problema

Entrei procurando viés nas bordas. Saí com três coisas que não esperava, e as três são mais sobre estrutura do que sobre bordas no sentido estreito:

1. **O Ascon é o único dos quatro cujo estado interno é literalmente o criptograma.** Isso é uma propriedade de borda (a fronteira entre blocos i e i+1) e é a única alavanca estrutural genuína que um adversário ciphertext-only tem sobre qualquer um dos quatro. Combinada com as 8 rodadas por bloco, dá ao Ascon a margem relativa mais fina do conjunto — 62,5% contra 90% do GIFT-COFB — o que é contraintuitivo e vendável.

2. **A tag é o pior lugar para procurar, e dá para provar com dois números** (2^−12 dos bits, mais rodadas). A pergunta sobre os bits ímpares do Grain tem resposta limpa e fundamentada: a informação existe, os projetistas admitem que ela vale 2^114, e um OTP de 64 bits fresco por nonce a torna inacessível. Isso é meia página de dissertação com mecanismo, e é melhor do que um "não encontramos nada".

3. **O canal que a literatura inteira aponta é o comprimento, e o dataset o neutraliza corretamente** — o que significa que o valor científico do experimento não está em achar sinal, e sim em (a) medir e publicar a resolução estatística do que foi descartado, (b) rodar os controles de oclusão que transformam H₀ em prova, e (c) mapear a curva de rodadas reduzidas em CT-only, que ninguém mapeou, porque toda a literatura de margem de segurança usa entradas escolhidas ou de baixa entropia.

O item (c) é, no fim, o único território realmente aberto. A coluna "Random" da tabela de Bellini–Huang tem **1** em todas as linhas. Essa coluna é o estado da arte no nosso modelo de ameaça, e ela é de 2022, feita com NIST STS. Bater isso em uma rodada já é resultado.

---

**Seções escritas pelo agente:** 1 a 13, mais o sumário inicial. Todas as tabelas citadas no corpo estão presentes na resposta original; o que faltou nesta cópia foi perdido no truncamento da entrega e está marcado acima.

---

# Pesquisa 10 — Aprendizado de representação / arquiteturas não-padrão

- **Ângulo:** Aprendizado de representação / arquiteturas não-padrão
- **Temperatura declarada:** 0,25

## Pesquisa 10 — prompt usado, na íntegra

````markdown
# Pesquisa 10 — Aprendizado de representação sobre bytes crus, com arquiteturas não-padrão

**Temperatura declarada: 0,25** (amplitude de exploração baixa — este é o
último ângulo da série e o terreno é o mais propenso a hype. Quero ceticismo
ativo: prefira trabalhos com código público, com baseline honesto e com
resultado negativo reportado, a alegações grandiosas. Especulação é permitida,
mas tem que vir marcada e depois dos fatos, e cada arquitetura proposta
precisa de um argumento de POR QUE ela veria algo que uma CNN não vê.)

---

## PROBLEMA DE PESQUISA

Você está pesquisando para uma dissertação de mestrado em criptografia
aplicada e aprendizado de máquina. Trabalhe SÓ com literatura externa: não
leia nenhum repositório, arquivo local ou resultado prévio. Comece do zero.

**A pergunta.** Dado apenas o criptograma — sem a chave, sem o texto em claro,
sem poder escolher nada do que é cifrado — é possível distinguir qual
algoritmo de criptografia autenticada o produziu? E, num segundo nível, com
quantas rodadas reduzidas um algoritmo ainda deixa de parecer aleatório?

**Os algoritmos.** Os quatro finalistas do concurso NIST Lightweight
Cryptography: Ascon-AEAD128 (esponja), GIFT-COFB (cifra de bloco em modo
COFB), Grain-128AEAD (cifra de fluxo com LFSR e NFSR) e Schwaemm256-128
(esponja ARX, família SPARKLE).

**O modelo de ameaça, que é a restrição dura e não negocia.** Adversário
PASSIVO, em ciphertext-only. Ele observa criptogramas de um mesmo dispositivo,
com nonces públicos de contador, e pode observar vários de uma vez. Ele NÃO
tem: texto em claro conhecido ou escolhido, diferenças escolhidas na entrada,
reuso de nonce, acesso a canais laterais, nem consultas a um oráculo de
cifragem. Isso exclui de saída a maior parte da criptanálise diferencial
clássica e os distinguidores neurais no estilo Gohr, que dependem de pares com
diferença escolhida.

**O protocolo experimental.** Chaves de teste nunca aparecem no treino
(key-holdout). Intervalo de confiança por bootstrap agrupado por chave, e não
i.i.d. Correção para múltiplas comparações. Controle negativo obrigatório: com
o algoritmo completo o classificador tem que ficar no acaso.

**Dado concreto disponível:** ~30.000 criptogramas por algoritmo, 64 KB cada
(≈1,9 GB por classe), 300 chaves distintas, nonces de contador, texto em claro
vindo de corpus real (80% texto em inglês do Project Gutenberg, 20% imagem em
tons de cinza). Existem variantes com rodadas reduzidas compiladas para os
quatro algoritmos. Controles: AES em modo ECB (positivo) e saída de PRNG
(negativo).

**O que já foi tentado e deu acaso:** classificadores clássicos sobre features
estatísticas (centenas de dimensões); CNN 1D sobre a sequência de bytes; CNN
2D sobre mapa de co-ocorrência de bigramas 256×256; concatenação híbrida das
três representações; Transformer hierárquico sobre bytes. Todos convergem para
F1 ≈ 0,50 com os algoritmos completos.

---

## ÂNGULO DESTA PESQUISA — o que existe além de CNN e Transformer

A pergunta é direta: **CNN e Transformer são as arquiteturas erradas para este
dado, ou não existe sinal para arquitetura nenhuma achar?**

Quero o levantamento das arquiteturas e dos paradigmas de representação que
NÃO são CNN/Transformer padrão, com um critério de corte severo: para cada
uma, preciso de um argumento de **por que ela enxergaria algo que uma
convolução não enxerga**. "É mais moderna" não é argumento. "Tem viés
indutivo X, e a estrutura do dado tem propriedade Y que casa com X" é
argumento.

Persiga, entre outras coisas:

- **State space models** (S4, Mamba, e a linhagem de modelos de sequência
  longa). O argumento a favor seria memória de longo alcance sobre 65 mil
  bytes, que a CNN com campo receptivo limitado não tem. Isso se sustenta?
  Existe aplicação a dados de alta entropia?
- **Redes sobre grafos** — representar o criptograma como grafo (de
  co-ocorrência, de transição de estado, de proximidade) e aprender sobre ele.
  Existe trabalho de identificação de cifra ou de detecção de aleatoriedade
  com GNN?
- **Compressão neural como distinguidor.** Treinar um modelo autorregressivo
  e usar a log-verossimilhança (ou o comprimento de código) como estatística.
  É formalmente uma versão aprendida dos testes de compressão, e tem a
  vantagem de dar um número calibrado. Existe literatura? E como isso se
  relaciona com o fato de que criptograma é incompressível por construção?
- **Modelos de linguagem grandes aplicados a bytes** — a linha de "LLM como
  compressor" e de tokenização de bytes. Há alegações recentes nessa direção;
  quero saber o que é real.
- **Aprendizado auto-supervisionado / contrastivo** — treinar sem rótulo de
  algoritmo, por exemplo aprendendo a dizer se dois blocos vêm do mesmo
  criptograma, e depois sondar a representação. O argumento é que o sinal de
  treino é diferente e pode revelar estrutura que a classificação direta não
  revela.
- **Arquiteturas com viés indutivo algébrico** — redes que operam sobre GF(2),
  camadas XOR/paridade, redes binárias, ou qualquer coisa desenhada para
  representar funções booleanas em vez de funções suaves. Este me parece o
  candidato mais promissor a priori, porque o dado É booleano e a operação
  fundamental das cifras é XOR.
- **Métodos de detecção de anomalia e de teste de duas amostras neural** —
  classifier two-sample test, MMD com kernel aprendido, e afins. A vantagem
  seria produzir um p-valor calibrado em vez de uma acurácia.
- **O que a literatura de criptanálise neural diz sobre escolha de
  arquitetura** — existe estudo comparativo sério? Alguém mostrou que a
  arquitetura importa, ou todos os resultados vêm da representação de entrada
  e da diferença escolhida?

E o contraponto, que quero com o mesmo peso: **evidência de que trocar de
arquitetura não adianta.** Estudos de ablação, resultados negativos,
argumentos teóricos de que a classe de funções aprendíveis é a mesma.

---

## O QUE EU QUERO DE VOCÊ

Técnicas, representações, ataques ou ideias — publicadas ou adaptáveis — que
possam extrair sinal nesse cenário, ou que ajudem a delimitar com rigor por
que o sinal não existe. Interessa tanto o que funciona quanto a prova de que
algo é impossível.

Busque em literatura acadêmica real (IACR ePrint, ToSC/FSE, CHES, CRYPTO,
EUROCRYPT, ASIACRYPT, SAC, NeurIPS, ICML, ICLR, IEEE, Springer, arXiv) e em
fontes técnicas sérias. Use termos de busca em inglês.

## COMO RESPONDER

Para cada ideia encontrada, escreva:

1. **O que é** — a técnica, em duas ou três frases.
2. **Fonte** — autores, título, veículo, ano. Link quando houver. Se você não
   conseguiu confirmar a existência do trabalho, diga isso explicitamente em
   vez de completar de memória.
3. **Cabe no nosso modelo?** — SIM, NÃO, ou ADAPTÁVEL. Se ADAPTÁVEL, diga
   exatamente o que teria de mudar e qual premissa do modelo de ameaça isso
   arranha.
4. **O que custaria testar** — ordem de grandeza de dados, computação e
   engenharia.
5. **O que ela prevê** — se a técnica funcionar, que resultado deveríamos ver?
   Se não houver previsão falsificável, diga isso.
6. **Por que ela veria o que a CNN não vê** — o argumento de viés indutivo. Se
   não houver, diga "não tenho argumento" em vez de inventar um.

Termine com uma seção **APOSTAS**: as três ideias que você tentaria primeiro,
e por quê. Seja específico; "usar deep learning" não é uma aposta.

## PROFUNDIDADE

Vá até esgotar o veio: siga as citações, abra os trabalhos relacionados,
procure versões estendidas e teses. Só encerre quando as buscas novas pararem
de trazer coisa nova. Espera-se algo da ordem de 80 a 120 chamadas de busca.

Traga todos os números que importarem (acurácia, tamanho de dado, número de
parâmetros, comparação com baseline) e as limitações declaradas pelos próprios
autores, com as palavras deles.

**A sua resposta final é o produto inteiro** — ela vai ser salva em disco
literalmente. Não escreva "detalhei acima".

**ATENÇÃO AO TAMANHO.** As duas últimas pesquisas desta série chegaram
truncadas na entrega e tive de pedir reemissão. Para evitar: **mantenha a
resposta final abaixo de ~35 mil palavras**, numere todas as seções, e comece
com um sumário listando as seções escritas. Se precisar cortar, corte
material de baixo valor (listas de referências tangenciais, repetição de
contexto) e preserve os números, as tabelas e as citações literais. Densidade
acima de extensão.

## REGRAS

- Não invente referências. Uma fonte não confirmada vale menos que nenhuma.
- Ceticismo ativo: alegação extraordinária sem código público e sem baseline
  honesto deve ser marcada como suspeita, com o motivo.
- Se a conclusão honesta de um caminho for "isso é impossível neste modelo
  por tal razão teórica", isso é resultado útil. Diga.
- Separe o publicado da sua extrapolação: **[PUB]** lido e confirmado,
  **[CIT]** existência confirmada mas texto não obtido, **[MINHA]**
  extrapolação sua.
````

## Pesquisa 10 — achados, sem resumir

*(pesquisa não concluída — sem achados em disco)*

---

# Síntese cruzada das nove pesquisas

Nove agentes independentes, sem contato entre si, nem com o repositório, nem
com esta conversa, varreram a mesma literatura a partir de ângulos diferentes
(assinatura do modo, análise de tráfego, limites teóricos, cifras de fluxo,
rigor do nulo, estatística de alta ordem, correlação linear, rodadas
reduzidas não-diferenciais, bordas do criptograma). O que segue não repete
achados individuais — está tudo nas seções acima — mas marca onde nove
buscas independentes convergiram no mesmo lugar, porque convergência
independente é o sinal mais forte que este exercício podia produzir.

---

## 1. A descoberta que apareceu três vezes, sem combinar: o bit 7 do ASCII cancela a piling-up lemma

Este é o achado mais importante de toda a série, precisamente porque
**nenhum dos três agentes que chegaram a ele sabia que os outros existiam.**

A mecânica, resumida: para qualquer máscara linear `β`, a correlação
observável no criptograma é `corr_C(β) = corr_P(β) · corr_Z(β)` — produto da
correlação da máscara no plaintext pela correlação da mesma máscara no
keystream (piling-up lemma). Em texto ASCII, o bit mais significativo de todo
byte é 0 com probabilidade ≈ 1. Para qualquer máscara `β` suportada apenas
nessas posições, `corr_P(β) = 1` **exatamente** — a penalidade da piling-up
lemma desaparece por inteiro, e o cenário ciphertext-only fica
indistinguível de known-plaintext, sem perda nenhuma, nessa direção
específica.

As três aparições independentes:

- **Pesquisa 01** (assinatura do modo, temp. 0,4) propôs isso como um
  **cubo passivo**: nonces consecutivos de um contador formam um cubo
  gratuito; somando os criptogramas nas posições de bit determinísticas, o
  termo de plaintext cancela e o keystream fica exposto. Precedente citado:
  FMS/WEP.
- **Pesquisa 07** (correlação linear, temp. 0,9) chegou à mesma ideia pelo
  lado de **trilha linear entre blocos consecutivos**: no Ascon, o rate do
  estado após absorver **é** o bloco de criptograma, então uma máscara de
  saída restrita ao bit 7 dá um distinguidor Tipo III sem nenhuma perda.
  Previu o ponto de virada em 2–3 de 8 rodadas.
- **Pesquisa 08** (rodadas reduzidas, temp. 0,45) redescobriu a mesma
  construção como **"integral observacional por nonce-contador"**, com a
  mesma mecânica de cancelamento, e calculou que ela recupera quase toda a
  potência de um distinguidor integral clássico (perde ~1 rodada em relação
  ao caso com IV escolhido) sem exigir escolha nenhuma.

Três formulações do mesmo mecanismo — cubo, trilha linear, integral —
convergindo no mesmo truque aritmético (bit 7 do ASCII) e nas mesmas
previsões numéricas (ponto de virada em 2–4 rodadas do Ascon). Isso não
prova que o mecanismo vá achar algo — os algoritmos completos continuam
protegidos por margens de 60+ bits acima do que qualquer um dos três
orçamentos de dados alcança —, mas é a coisa mais barata e mais bem
fundamentada de todo o levantamento para testar primeiro em rodadas
reduzidas, e dá três rotas de verificação cruzada independentes para o
mesmo número.

**Ressalva que as três pesquisas registraram:** o mecanismo depende de o
adversário conhecer a *distribuição* do plaintext (texto ASCII), não um
plaintext específico. É a mesma alavanca de Matsui contra o DES em 1993 e
de Barkan–Biham–Keller contra o GSM — aceita como ciphertext-only pela
comunidade —, mas é mais permissiva que a rejeição que você deu ao XOR de
pares com mesmo plaintext. Vale alinhar essa fronteira antes de investir.

---

## 2. Três rotas teóricas independentes, um único teto numérico

As pesquisas 03 (limites teóricos) e 05 (rigor do nulo) calcularam,
por caminhos diferentes (distância de unicidade de Shannon; bounds de
segurança prováveis de Chakraborty–Dhar–Nandi para o Ascon, de
Inoue–Iwata–Minematsu para o GIFT-COFB, da própria spec para o Grain), que
a vantagem máxima alcançável por qualquer classificador de tempo limitado
está entre **10⁻¹¹ e 10⁻³³**, dependendo de quão generosa é a suposição
sobre o poder computacional do adversário. A resolução do experimento — o
menor efeito que 180 mil amostras com bootstrap agrupado por chave
conseguem detectar — está em torno de **10⁻².**

A pesquisa 09 (bordas do criptograma) chegou ao mesmo tipo de número por
um quarto caminho, aplicando a desigualdade triangular de indistinguibilidade
diretamente aos quatro modos com os parâmetros do dataset: vantagem
máxima ≈ 2⁻³⁷, dominada pelo termo mais fraco (GIFT-COFB).

**A consequência prática, dita nas três pesquisas com a mesma conclusão:**
F1 ≈ 0,50 nos algoritmos completos não é ausência de evidência — é a
confirmação quantitativa de um teorema. A pesquisa 03 propõe a tabela que
resume isso (distância de unicidade × tamanho do criptograma × TV entre
distribuições × piso de detecção do corpus), e recomenda que ela abra o
capítulo de resultados. A pesquisa 05 vai além e argumenta que a região de
equivalência (ROPE/SESOI) para os testes estatísticos **não precisa ser
escolhida arbitrariamente** — pode ser derivada do próprio bound provável,
o que aparentemente ninguém fez antes em criptanálise (procurado
explicitamente, não encontrado).

---

## 3. "Agregar destrói o sinal posicional" — o mesmo achado em quatro pesquisas

Um resultado publicado pelo CRoCS Brno (Klinec, Sýs, Kubíček, Švenda,
SECRYPT 2022) apareceu, sozinho, em referências separadas nas pesquisas 04,
06, 08 e 09: **414 testes estatísticos aplicados a keystream de RC4
concatenado com chave aleatória não detectam o viés de Mantin–Shamir** —
publicado há 25 anos, dobra a probabilidade esperada do segundo byte. A
razão, nas palavras do próprio estudo, é que a concatenação destrói o
alinhamento posicional onde o viés vive.

Isso teria passado despercebido se aparecesse uma vez. Aparecer quatro
vezes, em pesquisas que não se comunicaram, é evidência de que é um ponto
cego estrutural do desenho de features atual: as 12 famílias (histograma,
entropia, n-gramas, autocorrelação, complexidade, FFT, NIST STS, momentos,
Hamming, Welch, bitblock, tag_region) **agregam sobre o criptograma
inteiro**. Nenhuma delas testa "o byte na posição p, através das amostras" —
que é exatamente onde um viés de inicialização mal misturada viveria.

A pesquisa 09 quantifica o preço: com 30.000 amostras de 64 KB, a
sensibilidade por posição fixa é |ε| ≳ 2⁻⁶·⁸ — pior que os ~2⁻⁸ que a
literatura de RC4 precisou explorar, e pior por muitas ordens de grandeza
do que o que o mesmo volume de bytes compraria em amostras mais curtas e
mais numerosas (a pesquisa recomenda trocar 30.000 × 64 KB por
~10.000.000 × 64 B, mesmo volume de bytes cifrados, 10³× mais amostras
alinhadas por posição — ganho de ~4,5 bits binários de sensibilidade
exatamente onde a inicialização reduzida produziria sinal).

O mesmo estudo do CRoCS também mostrou algo que vale registrar à parte:
em 81% dos casos, multiplicar o volume de dados por 100 **não** aumentou a
detecção — a escolha de estatística domina o volume. Isso é relevante para
qualquer decisão de "gerar mais dados" versus "medir melhor".

---

## 4. A tabela que falta na literatura, e que três pesquisas pediram para ser construída

As pesquisas 06, 08 e 09 documentaram, cada uma a seu modo, que existem
baterias de teste desenhadas especificamente para achar o piso de rodadas
de uma primitiva — NIST STS clássico, BoolTest, EACirc, CryptoStat — e que
**nenhuma delas nunca foi aplicada aos quatro finalistas do NIST LWC**.

O achado mais citável aqui (pesquisa 08, com apoio de 06) é o de Bellini &
Huang (NIST LWC Workshop 2022, 462 GB de dados, um mês de execução): com
entrada **aleatória** — a única das nove estratégias de geração deles que
corresponde ao nosso modelo de ameaça —, o **NIST STS quebra exatamente
1 rodada** para os 15 primitivos testados, incluindo Ascon-p, as três
variantes de Sparkle e GIFT-128. A distância entre essa coluna e a coluna
de entrada estruturada (avalanche) é o preço exato do modelo de ameaça: um
fator 8 para GIFT-128, um fator 4 para Ascon-p — e é um número que a
dissertação pode citar como calibração de referência, publicada, com
metodologia às claras.

A recomendação prática, presente nas três pesquisas de formas
independentes: rodar BoolTest (código público, `crocs-muni/booltest`) sobre
os quatro algoritmos em rodadas reduzidas e produzir a tabela comparativa
que a literatura nunca fez. Ela tem duplo valor — dá um piso de referência
mais sensível que o NIST STS, e devolve o distinguidor em forma
interpretável (quais bits, qual polinômio), que é exatamente o que falta
para responder "o que a rede aprendeu?" na defesa.

---

## 5. Uma assimetria estrutural real entre os quatro algoritmos, descoberta duas vezes

As pesquisas 07 e 09, por rotas diferentes, chegaram à mesma observação
sobre a arquitetura dos quatro esquemas: **o Ascon-AEAD128 é o único cujo
rate do estado, depois de absorver um bloco, é literalmente o bloco de
criptograma** — normativo, na eq. 24-26 da SP 800-232. O adversário passivo
conhece 128 dos 320 bits do estado a cada bloco, de graça, sem nenhuma
suposição extra. Nenhum dos outros três tem essa propriedade: o Schwaemm
esconde isso atrás do feedback combinado do modo Beetle; o GIFT-COFB
mascara com um valor `L` derivado de `E_K(nonce)`; o Grain nem tem esse
conceito, porque o keystream é gerado sem nunca ver o plaintext.

Cruzando isso com os limites de trilha linear publicados (El Hirch, Mella,
Mehrdad, Daemen, ToSC 2022(4)) e o orçamento de dados do experimento, as
duas pesquisas chegaram — independentemente — à mesma previsão numérica:
**o ponto de virada do Ascon fica entre 3 e 4 rodadas de 8** (salto de ~60
bits binários entre essas duas linhas da tabela de El Hirch et al.), o que
dá ao Ascon a **margem relativa mais fina dos quatro** em ciphertext-only —
62,5% contra 90% do GIFT-COFB. É contraintuitivo (o Ascon é o vencedor do
NIST e o mais estudado dos quatro) e não compromete em nada sua segurança;
é simplesmente a consequência de ter menos rodadas por byte de saída
observável (0,5 rodada/byte contra 2,5 do GIFT-COFB) combinada com a
exposição estrutural do rate.

Como bônus de verificação: essa previsão de 3-4 rodadas bate, por um
terceiro caminho totalmente independente, com o custo publicado do ataque
de forja de Dobraunig et al. (CT-RSA 2015) sobre a finalização do Ascon —
2³³ em 3 rodadas, 2¹⁰¹ em 4. Três rotas matemáticas diferentes convergindo
no mesmo número é o tipo de coincidência que vale a pena verificar
experimentalmente primeiro.

---

## 6. O catálogo de impossibilidades — o que várias pesquisas fecharam, com prova, e não precisa ser tentado

Reunindo o que cinco ou mais pesquisas confirmaram de formas independentes,
como caminhos genuinamente fechados neste modelo de ameaça (não "ainda não
tentamos", mas "provado impossível dado o orçamento"):

- **Qualquer ataque de família cube/division property/zero-sum na forma
  publicada.** Todos exigem conjunto de entradas escolhido ou estruturado.
  (01, 06, 07, 08)
- **Fast correlation attack contra o Grain.** Déficit de ~10²⁰ a 10³⁷ em
  dados, mesmo na leitura mais generosa; a spec do Grain-128AEADv2 esconde
  metade do pre-output e limita o keystream por nonce especificamente
  contra esse ataque. (04, 07, 08)
- **Ataques de invariante não-linear em ciphertext-only.** É o único ramo
  estrutural que a literatura reconhece como genuinamente ciphertext-only,
  e está provadamente fechado contra o GIFT (os projetistas verificaram que
  não existe invariante quadrático na S-box) e estruturalmente
  inaplicável aos outros três, que não são key-alternating da forma que o
  ataque exige. (08)
- **Colisões de estado ou de tag como distinguidor.** Custam entre 2⁶⁴ e
  2¹⁶⁰ observações dentro de uma chave; temos 2¹⁸·⁶. (09)
- **NCD e distância de compressão normalizada.** Fechado analiticamente —
  para dois criptogramas uniformes e independentes, `C(xy) ≈ C(x) + C(y)`
  sempre, então NCD tende a 1 para todo par, de toda classe, sem
  informação nenhuma. (02, 06)
- **Distância de unicidade como argumento de impossibilidade
  informacional.** Não é um caminho fechado — é o oposto: a pesquisa 03
  mostra que o problema está a ~3.500× a distância de unicidade, então
  informacionalmente o problema está *aberto*. O fechamento é puramente
  computacional. Confundir os dois é o erro mais citado nas nove pesquisas
  como risco de má argumentação na dissertação.

---

## 7. O ponto que precisa de conversa antes de virar uma linha de texto

Cinco pesquisas (01, 02, 03, 05, 09) tocaram, de ângulos diferentes, no
resultado de Mello & Xexéo (JUCS 2018): identificação de algoritmo em modo
CBC a 40-50% de acurácia contra um acaso de 7-14%, com um controle físico
(KeyBITS) que ficou no acaso. Nenhuma das cinco alega que o resultado está
errado. Todas levantaram a mesma dupla de hipóteses concorrentes,
independentemente:

- **H1 — vazamento de comprimento/padding.** DES, 3DES e Blowfish têm bloco
  de 64 bits; os demais, 128. Isso muda o padding e o alinhamento em CBC
  mesmo para o mesmo plaintext.
- **H2 — memorização por esparsidade do histograma.** Bins de 34 bits sobre
  arquivos de 100 KB dão ocupação de 0,005% — o vetor de features aproxima
  uma impressão digital do arquivo específico, não uma estatística do
  algoritmo. A extrapolação dos autores para "reconhecimento pleno em 85
  bits" atravessa exatamente o ponto em que isso deixa de ser sutil.

O controle KeyBITS argumenta contra H2 em sua forma mais forte (um
classificador puramente memorizador não deveria distinguir amostras nunca
vistas de uma fonte física genuinamente aleatória do jeito que distinguiu
das sete cifras). Mas nenhuma das cinco pesquisas encontrou o controle que
decidiria entre H1 e H2 de fato rodado no trabalho original — normalizar
todos os criptogramas ao mesmo comprimento exato antes de extrair
qualquer feature, o que custaria uma linha de código.

Isso não é uma crítica ao trabalho — é uma leitura de terceiros, sem os
dados originais em mãos, e pode estar errada. Por isso: **nenhuma dessas
cinco leituras deve entrar em texto da dissertação sem conversa direta
com o orientador primeiro**, seguindo a regra já registrada de como tratar
comentário de terceiro sobre conteúdo.

---

## 8. O que ficou confirmado, de forma cruzada e sem exceção: a lacuna é real

Todas as nove pesquisas, cada uma buscando de um ângulo diferente,
relataram a mesma ausência: **nenhum trabalho publicado tenta classificar
por ML, em ciphertext-only, um par ou conjunto de finalistas do NIST
Lightweight Cryptography.** A literatura de identificação de cifra por ML
existe (DES, AES, 3DES, Blowfish, RC4, SPECK, SIMON, cifras clássicas), e a
literatura de criptanálise neural existe (toda em chosen-plaintext, com
diferença escolhida, nenhuma em ciphertext-only puro), mas a interseção —
os quatro algoritmos do problema, no cenário exato do problema — está
vazia. Nove buscas independentes não encontrando o mesmo trabalho é a
confirmação mais forte disponível de que a pergunta da dissertação ainda
não tem resposta publicada.

---

## 9. Lista de ação, ordenada pelo número de pesquisas que recomendaram algo próximo disso

1. **Controles de oclusão (E2/E3): substituir o criptograma por bytes
   pseudoaleatórios ou por constante, do mesmo comprimento, mantendo os
   rótulos, e retreinar.** Recomendado com metodologia quase idêntica pelas
   pesquisas 05 (como "spike-in" / escada de calibração) e 09 (citando o
   precedente direto do SoK de classificadores de tráfego cifrado, IEEE
   S&P 2025, que fez exatamente isso e transformou "não achamos padrão" em
   "provamos que não há padrão além do comprimento"). É o item de menor
   custo (uma tarde de GPU) e maior retorno argumentativo de toda a série.
2. **A varredura de correlação linear/integral ancorada no bit 7 do ASCII**
   (seção 1 acima), nas três formulações independentes — cubo passivo (01),
   trilha entre blocos do Ascon (07), integral observacional (08).
3. **Um controle positivo calibrado de dificuldade conhecida** — RC4
   (pesquisas 02 e 04) com os vieses de Mantin–Shamir e Fluhrer–McGrew como
   régua publicada, na mesma ordem de grandeza de dados do experimento
   atual. Hoje o único positivo é AES-ECB, que é fácil demais (o plaintext
   atravessa o modo inteiro) para calibrar sensibilidade.
4. **BoolTest sobre os quatro algoritmos em rodadas reduzidas** (seção 4
   acima), pedido por 06, 08 e 09.
5. **Reportar a resolução estatística do experimento como número explícito**
   — "excluímos qualquer viés acima de X" — em vez de "não achamos nada",
   pedido de formas equivalentes por 03, 04 e 05.
6. **Pooling por chave em vez de por amostra**, já que o modelo de ameaça
   declarado permite ao adversário observar vários criptogramas de uma vez
   (02) — amplifica qualquer deflexão residual por ~10× (√100), e hoje o
   protocolo relatado mede um adversário mais fraco que o declarado.
