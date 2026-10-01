# O que a literatura fez, o que eu vou fazer, e onde está a diferença

**26/09/2026.** Texto sobre os dois trabalhos mais próximos do meu experimento, o que cada um mediu de fato, e por que o que eu proponho responde uma pergunta diferente.

---

## 1. Shen et al. (2024)

*Neural differential distinguishers for GIFT-128 and ASCON*, Journal of Information Security and Applications 82, artigo 103758. Autores da Universidade de Xiangtan, do Instituto de Software da Academia Chinesa de Ciências e da Universidade de Jinan. Código em `github.com/yijSong/ND-GIFT-ASCON`.

### O que é um distinguidor diferencial neural

A ideia vem do Gohr (CRYPTO 2019). O atacante escolhe uma diferença fixa δ, monta pares de textos que diferem exatamente por δ, cifra os dois com a mesma chave, e treina uma rede para reconhecer se o par de criptogramas veio de textos relacionados por δ ou de textos sem relação nenhuma. Se a rede acerta acima de 50%, o algoritmo ainda não apagou o rastro de δ naquele número de rodadas.

O modelo do Shen muda duas coisas em relação ao Gohr. Primeiro, a rede recebe só a diferença entre os dois criptogramas (C ⊕ C'), não o par (C, C'). Segundo, e é a contribuição principal deles, a classificação não é feita uma diferença por vez: eles pegam um conjunto de s diferenças, passam cada uma pela primeira rede para obter um score entre 0 e 1, ordenam esses s scores, e alimentam esse vetor ordenado numa segunda rede, que classifica o conjunto inteiro. O motivo é que mesmo quando a primeira rede mal supera o acaso numa diferença isolada, a **distribuição** dos scores sobre um conjunto grande já é visivelmente distinta entre os dois casos. Eles também testaram fazer esse segundo estágio com o teste estatístico de Kolmogorov-Smirnov, e a rede se mostrou mais econômica em dados.

### O que ele separa, exatamente

Este ponto é o que mais importa para comparar com o meu trabalho. No algoritmo de geração de dados do artigo, sorteia-se P0 e P1 independentes, e define-se P2 = P1 ⊕ δ. Cifra-se os três com a mesma chave. As duas classes são:

- classe 1: C1 ⊕ C2, a diferença entre criptogramas de textos que diferem por δ;
- classe 0: C0 ⊕ C1, a diferença entre criptogramas de dois textos independentes.

**As duas classes são saída real do algoritmo.** Não há ruído uniforme em nenhum momento do treino. O que o distinguidor dele decide é se um par de criptogramas veio de textos relacionados pelo δ que ele mesmo escolheu, não se aquilo é cifra ou é aleatório.

### Sobre o que ele testou

Nos dois casos, a peça isolada, não o esquema completo.

**Ascon-permutation** é só o motor criptográfico: uma função que embaralha um estado de 320 bits, aplicando por r vezes três passos (soma de constante, camada de substituição com S-box de 5 bits, camada de difusão linear). Não tem chave, não tem nonce, não tem mensagem. O Ascon-AEAD128 é o esquema de criptografia autenticada construído em cima dessa função: carrega chave e nonce no estado, roda a permutação 12 vezes na inicialização, depois para cada bloco de mensagem absorve o bloco, emite o criptograma e roda a permutação 8 vezes, e no final roda 12 vezes de novo para produzir a tag. O artigo diz explicitamente que testa só a permutação: *"Because the ASCON-PERMUTATION does not require a key for computation, we only need to generate uniformly distributed 320-bit states."* Ou seja, ele aplica a função sobre estados de 320 bits sorteados, sem chave nenhuma envolvida.

**GIFT-128** é a cifra de bloco pura: 128 bits de entrada, 128 bits de chave, 40 rodadas, cada rodada com S-box de 4 bits, permutação de bits e soma de subchave. O GIFT-COFB é o modo AEAD que usa o GIFT-128 como peça: cifra o nonce para derivar uma máscara secreta L, encadeia os blocos aplicando uma função linear G sobre a saída anterior somada à máscara, e gera a tag numa última chamada. O artigo também é explícito: *"We assume that there is only one plaintext block for the data collection."* Um bloco só, ou seja, uma chamada isolada da cifra, sem nonce, sem encadeamento, sem tag.

### A diferença de entrada que ele usou

Para o GIFT-128, uma diferença de 1 bit no 7º byte do texto. Para a permutação do Ascon, o valor `0x01` somado por XOR no último byte do registrador x0. As duas têm peso de Hamming 1, um único bit alterado.

Eles testaram isso de propósito: treinaram distinguidores com diferenças de peso 1 a 5 no GIFT-128 de 6 rodadas, 128 diferenças por peso. Com peso 1, nenhuma das 128 ficou abaixo de 65% de acurácia e a maioria ficou entre 70% e 75%. Com peso 5, as 128 ficaram todas abaixo de 55%, praticamente inúteis. E quando tentaram usar a diferença de uma característica diferencial publicada, tida como ótima pela criptanálise clássica, obtiveram só 50,77% em 6 rodadas, pior que a escolha simples de peso 1.

### Por que isso é ataque de texto escolhido

O próprio artigo classifica assim, citando Biham e Shamir: criptanálise diferencial é um ataque de texto escolhido. Para montar o experimento, o atacante precisa escolher δ, construir os pares, e obter as três cifragens sob a mesma chave. Nada disso está disponível para quem só observa tráfego.

### O que o resultado dele mede

Por construção, o número de rodadas que ele alcança diz **quantas rodadas o algoritmo leva para apagar o rastro de uma perturbação injetada de fora**. É uma medida de difusão: o quanto uma alteração de um bit na entrada continua visível na saída. Não é uma medida de quão aleatória a saída parece para quem observa passivamente.

### Resultados

| Alvo | Rodadas testadas | Total do algoritmo | Acurácia com 1 diferença | Com conjunto de diferenças |
|---|---|---|---|---|
| GIFT-128 | 5 | 40 | 96,43% | não aplicado |
| GIFT-128 | 6 | 40 | 77,06% | 98,59% (s = 8) |
| GIFT-128 | 7 | 40 | 55,42% | 99,36% (s = 512) |
| Ascon-permutation | 1 a 3 | 12 | 100% / 100% / 99,99% | não aplicado |
| Ascon-permutation | 4 | 12 | 50,69% | 69,25% (s = 2048) |

Vale registrar como ler esses números. Em 7 rodadas de GIFT-128, a rede sozinha acerta 55,42%, quase acaso; os 99,36% só aparecem quando ela decide sobre um conjunto de 512 diferenças de uma vez. Em 4 rodadas do Ascon, a rede sozinha fica em 50,69%, e mesmo agrupando 2.048 diferenças chega a 69,25%. Eles conseguem 99,47% nesse caso, mas usando o teste de Kolmogorov-Smirnov sobre conjuntos de 65.536 diferenças. O sinal em 4 rodadas é fraco, e os próprios autores dizem isso.

Em relação ao estado da arte anterior, eles cobrem uma rodada a mais que o Baksi et al. no Ascon (que tinha chegado a 3 rodadas) e constroem o primeiro distinguidor neural de 7 rodadas para o GIFT-128.

---

## 2. Bellini e Huang (2022)

*Randomness Testing of the NIST Light Weight Cipher Finalist Candidates*, apresentado no NIST Lightweight Cryptography Workshop 2022, com versão em artigo na SecITC 2022 (LNCS 13809).

### O que é a bateria NIST STS

É o conjunto de testes estatísticos padrão do NIST para avaliar geradores de números aleatórios, definido na publicação SP 800-22. São 15 testes, expandidos em quase 200 variações, cada um procurando um tipo específico de regularidade: frequência de bits, tamanho de sequências repetidas, padrões periódicos, complexidade linear, entre outros. Cada teste devolve um p-valor, e a sequência é considerada não aleatória se rejeitar em proporção maior que a esperada. É uma bateria fixa: os testes são definidos de antemão e não aprendem nada dos dados.

### O que eles fizeram

Aplicaram essa bateria às versões com rodadas reduzidas de todos os finalistas do concurso LWC do NIST, sob nove estratégias diferentes de geração de dados. Oito dessas estratégias usam entrada estruturada ou escolhida (avalanche de texto, avalanche de chave, correlação texto-criptograma, modo CBC, baixa e alta densidade de bits no texto e na chave). Só uma, chamada Random, usa chave e entrada aleatórias, sem controle nenhum do analista. É a única que corresponde ao meu cenário.

### Resultado

Na coluna Random, a bateria detecta não aleatoriedade até a **primeira rodada** e nada além disso, para praticamente todos os primitivos testados: Ascon-p, as três variantes do Sparkle (a família do Schwaemm), GIFT-128, Keccak-p, PHOTON256, Xoodoo e skinny. Nas colunas de entrada escolhida os números são bem maiores, por exemplo 8 rodadas para o GIFT-128 com avalanche de texto contra 1 rodada com entrada aleatória. Essa razão é a medida direta do que se perde ao abrir mão do controle da entrada.

### Custo e limitações

O estudo consumiu 462 GB de dados gerados e cerca de um mês de execução em três servidores dedicados, o maior deles com 1.152 GB de memória. É um esforço que não se repete com facilidade.

Três pontos limitam o que dá para concluir dali para o meu caso. Primeiro, é estatística clássica, com testes fixos: a bateria só encontra os padrões que ela foi programada para procurar. Segundo, testam o primitivo isolado, como o Shen, e não o esquema AEAD completo. Terceiro, o Grain-128 foi excluído do estudo, então não existe número de comparação para ele.

---

## 3. Um terceiro trabalho, mais próximo no objeto

Rajan et al. (2022) treinaram distinguidores diferenciais sobre 6 rodadas do **GIFT-COFB**, o modo completo, não a cifra isolada. É o trabalho que chega mais perto do meu objeto de estudo. Mas continua sendo distinguidor diferencial com diferença de entrada escolhida (usam as diferenças do Wang), então o modelo de ameaça é o mesmo do Shen e não o meu.

---

## 4. O que eu vou fazer

Medir o piso de rodadas reduzidas dos quatro finalistas (Ascon-AEAD128, GIFT-COFB, Grain-128AEAD, Schwaemm256-128), nos **esquemas AEAD completos**, sob adversário passivo em ciphertext-only. Reduzo as rodadas internas, gero o criptograma a partir de texto real (corpus Gutenberg e imagens), com 300 chaves distintas e nonces de contador, e mede-se até que rodada um classificador ainda separa esse criptograma de bytes uniformemente aleatórios do mesmo tamanho. O protocolo mantém as chaves de teste fora do treino, usa validação cruzada agrupada por chave e correção para múltiplas comparações.

GIFT-COFB e Grain-128AEAD já estão medidos: piso em 3 de 40 rodadas e em 28 de 256 clocks de inicialização, respectivamente. Ascon e Schwaemm são os próximos.

### Diferença para o Shen

**O que é separado.** Ele separa pares relacionados por δ de pares não relacionados, e as duas classes são saída real do algoritmo. Eu separo saída real do algoritmo de bytes uniformemente aleatórios. São perguntas diferentes.

**O modelo de ameaça.** Ele precisa escolher a diferença e obter as cifragens correspondentes sob a mesma chave. Eu só observo, não escolho nada, e o nonce que vejo é público porque é um contador.

**O objeto.** Ele testa a permutação do Ascon sem chave e um bloco isolado do GIFT-128. Eu testo o Ascon-AEAD128 e o GIFT-COFB inteiros, com inicialização, encadeamento de blocos, nonce e tag, que é o que um dispositivo real implementa e o que um observador de fato vê passar.

**O que se mede.** O número dele diz quantas rodadas o algoritmo leva para apagar o rastro de uma perturbação injetada. O meu diz quantas rodadas o algoritmo leva para que a saída deixe de ser distinguível de aleatório por quem só observa. A primeira é medida de difusão, a segunda é medida do que sobra para um adversário realista.

**O texto original.** Ele usa textos sorteados uniformemente. Eu uso corpus real, porque a redundância do texto natural é o único recurso que um adversário ciphertext-only tem, e ignorá-la mudaria o resultado.

### Diferença para o Bellini e Huang

**O método.** Bateria fixa contra classificador que aprende as features dos dados. A diferença já apareceu no meu resultado: no GIFT-128 eles param na rodada 1 sob entrada aleatória, e o meu experimento com ML chegou a 3 rodadas no GIFT-COFB.

**O objeto.** Primitivo isolado contra esquema AEAD completo, mesma distinção do Shen.

**A cobertura.** O Grain ficou de fora do estudo deles. Eu meço os quatro.

### Quadro comparativo

| | Shen et al. (2024) | Rajan et al. (2022) | Bellini e Huang (2022) | Este trabalho |
|---|---|---|---|---|
| Objeto | Ascon-permutation, GIFT-128 | GIFT-COFB | primitivos isolados dos finalistas | os quatro esquemas AEAD completos |
| Modelo de ameaça | texto escolhido, diferença escolhida | texto escolhido, diferença escolhida | entrada aleatória | ciphertext-only passivo |
| Método | rede neural sobre diferenças | rede neural sobre diferenças | NIST STS | classificadores clássicos e redes |
| Separa o quê | par com δ contra par sem δ | par com δ contra par sem δ | saída contra aleatório | saída contra aleatório |
| Texto original | uniforme | uniforme | uniforme | corpus real (texto e imagem) |
| Grain-128AEAD | não | não | excluído | sim |
| Mede | difusão de perturbação injetada | difusão de perturbação injetada | aleatoriedade estatística | piso sob adversário realista |

### Por que é relevante

Primeiro, porque nenhum trabalho publicado mede o piso de rodadas dos esquemas AEAD completos sob adversário passivo. O que existe ou usa entrada escolhida ou testa o primitivo isolado.

Segundo, porque é o cenário realista. Um atacante que observa tráfego de um dispositivo não escolhe diferença nem obtém cifragens sob demanda. Medir com poder que o atacante real não tem superestima o que ele consegue.

Terceiro, porque o número que sai é diretamente utilizável para a pergunta que motiva o concurso LWC: quanto dá para aliviar um algoritmo antes de perder segurança. Um piso medido sobre o esquema completo, sob o adversário mais fraco possível, é o limite inferior honesto dessa conta.

### Próximos passos

Medir o piso do Ascon-AEAD128 variando as rodadas de processamento de mensagem, e depois o Schwaemm256-128. Em paralelo, um teste estatístico direto e barato de correlação linear entre blocos consecutivos de criptograma, que serve de verificação cruzada do resultado obtido por aprendizado de máquina. O plano detalhado está em `docs/piso_rodadas.md`.
