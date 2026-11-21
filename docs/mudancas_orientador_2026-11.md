# Mudanças feitas a partir dos comentários do orientador

Organizado na ordem do documento do orientador (`Observacoes_Nycolas ORIENTADOR 1.docx`).
Cada item traz a crítica dele, citada uma vez e literalmente, e embaixo as mudanças que ela provocou.
Quando a mudança está numa seção que ele não comentou, o bloco diz **(consequência)**.
O Capítulo 6 não estava no arquivo que ele leu, então toda mudança no Capítulo 6 é consequência.
As mudanças que não vieram dele estão separadas no fim.

Os trechos alterados estão entre `#`. `...` indica texto que não mudou.

---

## Objetivo e questões de pesquisa (pedido posterior ao documento)

> Inclua objetivo e questões de pesquisa para que a verificação do seu texto novo seja consistente

**Situação:** feito. A introdução antiga (v1/v2) ficou como material, e entrou um Capítulo 1 novo (`introducao_piso.tex`) que, por enquanto, só tem a seção **Objetivo**. O resto da introdução vai ser reescrito.

Conteúdo da seção nova:

- **Objetivo geral:** medir, para o Ascon-AEAD128, o GIFT-COFB e o Schwaemm256-128, o maior número de rodadas em que as versões com rodadas reduzidas ainda podem ser separadas de dados aleatórios por um adversário passivo, que observa apenas criptogramas e nonces de contador (o piso de rodadas), com a ressalva de que o piso é uma cota inferior, e não uma prova de segurança acima dele.
- **Seis objetivos específicos**, cada um com a seção que o cumpre: construir e conferir as versões reduzidas (4.2); definir e calibrar o critério de detecção (4.6, 5.1); medir o piso com o criptograma isolado e com o par (5.2, 5.3); medir os dados necessários (5.3.3); verificar se o piso muda com o detector e o desenho (5.4); verificar se há sinal que os classificadores não aprendem (5.5).
- **Cinco questões de pesquisa:**
  - QP1. Um criptograma isolado, com rodadas reduzidas, pode ser separado de dados aleatórios, e até quantas rodadas? (5.2)
  - QP2. Observar duas mensagens do mesmo dispositivo aumenta o número de rodadas detectáveis, e qual é o piso de cada algoritmo? (5.3)
  - QP3. Quantos pares o adversário precisa observar, e quantos são necessários para treinar o classificador, para detectar a cifra no piso? (5.3.3)
  - QP4. O piso muda com o detector ou com as escolhas do experimento? (5.4)
  - QP5. Existe sinal acima do piso dos classificadores que eles, com os dados e os modelos avaliados, não conseguem aprender? (5.5)
- **Verificação:** cada QP é respondida por um número de rodadas, pelo critério da 4.6, com o F1 e o intervalo de confiança. Os dois primeiros objetivos não têm questão própria, porque constroem e calibram o instrumento.
- **Escopo:** fora ficam a recuperação de chave, a prova de segurança acima do piso e a distinção entre os algoritmos; as explicações do Capítulo 6 são hipóteses, e não respostas às QPs.

---

## 4.1 e 4.3.3. Pares de nonces

> Você não usa quaisquer dois nonces consecutivos. Usa os pares (0,1), (2,3), (4,5) etc. Nesses pares, muda sempre um único bit. Já de 7 para 8, por exemplo, mudam quatro bits. Isso precisa ficar explícito, porque o sinal que você procura depende dessa diferença.
> O adversário pode continuar sendo passivo e selecionar esses pares no tráfego. Mas descreva o resultado como obtido com essa seleção. Primeiro corrija a descrição; depois vemos se é necessário testar outras transições.

**Situação:** feito na 4.1, na 4.3.3, na 5.3 e no Capítulo 6. Além de corrigir a descrição, foi feito o teste de outras transições (pares a distância $k$), e o resultado entrou no Capítulo 5. A seleção ficou explícita: os pares usados são $2j$ e $2j+1$, que diferem em um único bit; o par não precisa ser consecutivo, basta que os nonces difiram em poucos bits.

### 4.1 Modelo de adversário

**Antes:**

... Neste trabalho, os #nonces de um par diferem em exatamente um bit, sempre na mesma posição (Seção~\ref{sec:met-dispositivos}), o caso mais favorável ao adversário.# ...

**Depois:**

... #No experimento principal, os pares são formados por mensagens consecutivas do mesmo dispositivo (Seção~\ref{sec:met-dispositivos}), mas o par não precisa ser consecutivo, basta que os dois nonces difiram em poucos bits. Pares de mensagens mais distantes, cujos nonces diferem em um único bit, e pares cujos nonces diferem em vários bits também foram testados. Outras configurações de nonce também foram testadas, com o contador começando de um valor sorteado e com o contador nos primeiros bytes do nonce, e em nenhuma delas o piso foi maior (Seção~\ref{sec:res-contador}).# ...

### 4.3.3 Dispositivos, chaves e nonces

**Antes:**

O nonce de cada dispositivo é um contador que começa do zero, e #o par $j$ de um dispositivo usa os nonces $2j$ e $2j+1$. Como $2j$ é par, os dois nonces de um par diferem em exatamente um bit, o menos significativo do contador, e a diferença de entrada é sempre a mesma. Pares de mensagens seguidas quaisquer, $n$ e $n+1$, podem diferir em mais bits, quando a soma propaga um transporte, e essa escolha é, portanto, o caso mais favorável ao adversário. A posição dessa diferença no nonce, no entanto, não favoreceu o piso medido, com# o contador nos primeiros bytes do nonce, a diferença #de um bit# entra em outra posição do estado, e o piso foi igual ou menor nos três algoritmos (Seção~\ref{sec:res-contador}). ...

**Depois:**

O nonce de cada dispositivo é um contador que começa do zero, e #cada par é formado por duas mensagens consecutivas de um dispositivo, com nonces $2j$ e $2j+1$, que diferem em um único bit.# Com o contador começando do zero, todos os dispositivos usam a mesma sequência de nonces, e só as chaves e os textos mudam de um dispositivo para outro. No estudo principal, o contador ocupa os últimos bytes do nonce. #As variações da Seção~\ref{sec:res-contador} mudam a posição do contador, que passa a ocupar os primeiros bytes, o seu valor inicial, que passa a ser sorteado por dispositivo, e a distância entre os nonces do par, que passa a ser de $k$ mensagens.#

O resultado ("o piso foi igual ou menor nos três algoritmos") saiu da metodologia; ele está no Capítulo 5.

### 5.4 Posição do contador no nonce (consequência, análise nova)

Teste novo: pares de nonces $c$ e $c+k$, com $k$ de 2 a 256, nos três algoritmos, com o mesmo desenho do estudo principal. Resultado: com um bit de diferença, o piso é igual ao das mensagens consecutivas, mesmo a 256 posições de distância; com vários bits ($k$ = 3, 7 e 15), o F1 cai, o GIFT-COFB perde uma rodada nos três casos e o Ascon-AEAD128 com $k$ = 7 e 15, e o Schwaemm256-128 não muda. Saídas em `build/reduced_rounds/floor_v2/contador_zero_dist{k}_corpus_en/`.

**Antes:**

(não existia)

**Depois:**

#O contador começando do zero corresponde a um dispositivo recém-ligado. Para o caso em que o contador de cada dispositivo está num ponto qualquer, o experimento foi repetido com o contador começando de um valor sorteado por dispositivo, com o corpus original, que inclui marcação HTML, e não com os livros em inglês do estudo principal. Com essa fonte, o contador começando do zero deu os mesmos pisos do estudo principal. Com o contador sorteado, o Ascon-AEAD128 e o Schwaemm256-128 mantiveram o piso, e o GIFT-COFB caiu uma rodada, para 2.#

#No estudo principal, o par é formado por duas mensagens consecutivas, com nonces $2j$ e $2j+1$, que diferem em um único bit. Para verificar se o par precisa ser consecutivo, o estudo foi repetido com pares de nonces $c$ e $c+k$, com $k$ entre 2 e 256 e $c$ múltiplo de $2k$, para que nenhum nonce se repita no mesmo dispositivo. [...] O piso depende, portanto, de quantos bits separam os dois nonces, e não da distância entre as mensagens, e, como os nonces são públicos, o adversário pode escolher no tráfego os pares que diferem em um único bit. No braço aleatório, nenhuma distância produziu piso, e 6 das 1\,620 células foram detectadas, todas com a tag incluída.# (mais a Tabela `tab:res-distancia`)

### 6.1, 6.2, 6.4 e 6.5 (consequência)

"um bit", "seguidas" → "consecutivas" / "entre os nonces":

- 6.1: nonces #que diferem em um bit# → nonces #consecutivos, que, nos pares usados, diferem em um único bit#; a diferença #de um bit no nonce# → a diferença #entre os nonces#; e frase nova ligando o mecanismo ao teste de distância: #O teste com nonces a distância $k$ é coerente com essa explicação, já que, quando os dois nonces diferem em vários bits, o F1 caiu e, no Ascon-AEAD128 e no GIFT-COFB, o piso perdeu uma rodada (Seção~\ref{sec:res-contador}).#
- 6.2: a diferença #de um bit entra no estado# → a diferença #entre os nonces entra no estado#
- 6.4: diferença de entrada conhecida e #pequena, de um bit, entre duas mensagens seguidas# → #pequena entre duas mensagens consecutivas#
- 6.4, Tabela `tab:disc-literatura`: "dois criptogramas #seguidos#" → "dois criptogramas #consecutivos#"
- 6.5: duas mensagens #seguidas# → duas mensagens #consecutivas#; nas condições de uso, entrou o resultado do teste de distância: #e pares cujos nonces diferem em vários bits deram um F1 menor e, no Ascon-AEAD128 e no GIFT-COFB, um piso uma rodada menor#
- 5.3, introdução do Capítulo 5 e legenda da tabela do XOR: "mensagens #seguidas#" → "mensagens #consecutivas#"

---

## 4.2.3. Vetores do Ascon

> Confira quais vetores foram usados no Ascon. Você diz que usa a versão padronizada e também os vetores da submissão à rodada final. Houve mudanças entre as versões. Pode ser só um problema de descrição. Registre o arquivo de vetores e a variante que ele verifica antes de pensar em refazer testes.

**Situação:** feito. Era só problema de descrição: os vetores vêm da implementação de referência dos autores, versão 1.3.0, que já segue o SP 800-232 (o nome do arquivo e o diretório ficaram fora do texto).

**Antes:**

... No Ascon-AEAD128, os vetores são os da implementação de referência dos #autores na versão 1.3~\cite{AsconC2024}, que segue o# NIST SP~800-232~\cite{nist_sp800232_2025}#, e não os do pacote da rodada final, cuja variante mais próxima, o Ascon-128a, tem outro valor inicial e outra ordem de bytes.# ...

**Depois:**

... No Ascon-AEAD128, os vetores são os da implementação de referência dos #autores, na versão 1.3.0~\cite{AsconC2024}, já atualizada para o Ascon-AEAD128 do# NIST SP~800-232~\cite{nist_sp800232_2025}#.# ...

---

## 4.3.2. Tag no controle aleatório

> Aqui há um ponto importante. Você reconhece que a tag pode ter estrutura com texto em claro aleatório. Então uma detecção nesse braço, com a tag incluída, não é necessariamente falso positivo. Não dá para reconhecer essa possibilidade e depois tratar toda detecção como erro do instrumento.
> Separe o controle sobre a parte cifrada do resultado com a tag incluída. Para conferir os falsos positivos do procedimento, considere também comparar dois conjuntos gerados pelo mesmo processo aleatório. Precisamos rever essa parte antes de aceitar a taxa de falsos positivos apresentada.

**Situação:** feito, com duas análises novas. (1) O braço aleatório do estudo principal foi refeito sem a tag, só com os 64 bytes de texto cifrado: com a tag, 0 de 180 células; sem a tag, 1 de 180 (GIFT-COFB r5, Random Forest, bolsa de 100), sem formar piso. (2) Teste A/A, CTR_DRBG contra CTR_DRBG pelo mesmo pipeline, 20 réplicas: 5 de 180 células com p < 0,05 (2,8%), nenhuma depois da correção BH. A interpretação no 5.1 está no item 5.1, abaixo.

**Antes:**

... A tag não tem essa garantia, já que ela é calculada na finalização, que também tem rodadas reduzidas, e pode carregar estrutura própria, de modo que uma detecção #vinda dela seria sinal da cifra, e não engano. Ela foi mantida no braço aleatório para que ele tivesse# exatamente o mesmo formato do braço de texto.

**Depois:**

... A tag não tem essa garantia, já que ela é calculada na finalização, que também tem rodadas reduzidas, e pode carregar estrutura própria, de modo que uma detecção #com a tag incluída não é necessariamente um falso positivo. Por isso, o braço aleatório foi analisado de duas formas. Com a tag incluída, ele tem# exatamente o mesmo formato do braço de texto#, e uma detecção pode vir da cifra. Sem a tag, só com os 64 bytes de texto cifrado, não há sinal possível, e qualquer detecção é falso positivo. Como esses dois controles ainda passam pela cifra, a taxa de falso positivo do próprio procedimento foi medida também por um teste A/A, em que dois conjuntos gerados pelo mesmo processo aleatório, o CTR\_DRBG, são comparados pelo mesmo pipeline, com os mesmos classificadores, bolsas e separação por chave, em 20 réplicas (Seção~\ref{sec:res-calibracao}).#

---

## 4.4.1. Sobreajuste e seleção de atributos

> Retire "não havia risco de sobreajuste". Ter 48 mil exemplos e 641 atributos não elimina esse risco. Também não diga que selecionar atributos só poderia retirar informação: pode reduzir ruído e melhorar o resultado. Basta explicar que você optou por manter todos os atributos.

**Situação:** feito.

**Antes:**

... #Os atributos foram usados sem seleção: com 48\,000 exemplos de treinamento para 641 atributos, não havia risco de sobreajuste por excesso de dimensões, e uma seleção só poderia remover informação.# ...

**Depois:**

... #Optou-se por manter todos os 641 atributos, sem etapa de seleção.# ...

---

## 4.5.2. Bolsas e log-odds

> As amostras da bolsa têm a mesma chave. Por isso, não apresente a soma de log-odds como se fossem necessariamente evidências independentes. Pode manter como uma regra de agregação e registrar essa ressalva.

**Situação:** feito.

### 4.5.2 Bolsas

**Antes:**

... #(frase nova)# ...

**Depois:**

... #As amostras de uma bolsa vêm do mesmo dispositivo e compartilham a chave, de modo que não são evidências independentes, e a média dos log-odds é usada aqui como uma regra de agregação, sem supor essa independência.# ...

### 5.1 Calibração do critério de detecção (consequência)

**Antes:**

... A média é feita nessa escala, e não sobre as probabilidades, porque nela a evidência de pares independentes se #soma de forma proporcional~\cite{Good1950}.# ...

**Depois:**

... A média é feita nessa escala, e não sobre as probabilidades, porque nela a evidência de pares independentes se #soma~\cite{Good1950}. Como os pares de uma bolsa compartilham a chave, a média é usada aqui como regra de agregação, sem supor essa independência.# ...

---

## 4.5.4. Parada antecipada

> A justificativa para não usar parada antecipada precisa mudar. É possível reservar chaves para validação sem misturá-las com as de treinamento. Você já usa separação por chave em outra parte. Não é uma exigência de refazer a rede; é uma correção da justificativa.

**Situação:** feito. A justificativa antiga (a validação sorteada por amostra misturaria chaves) foi retirada; a nova é a uniformidade do treinamento.

**Antes:**

... As duas foram treinadas com o otimizador Adam, taxa de aprendizado de $10^{-3}$, lotes de 256 amostras e 15 épocas, sem parada #antecipada, porque uma validação interna sorteada por amostra misturaria chaves de treinamento e de validação.#

**Depois:**

... As duas foram treinadas com o otimizador Adam, taxa de aprendizado de $10^{-3}$, lotes de 256 amostras e 15 épocas, sem parada #antecipada. O número de épocas foi fixado para que todas as rodadas e algoritmos recebessem o mesmo treinamento.#

---

## 4.6. F1 macro sem sinal

> Classes balanceadas não fazem o F1 macro ser sempre 0,50 quando não há sinal. Se o classificador responde sempre a mesma classe, ele fica em aproximadamente 0,333. Isso importa, inclusive, para a CNN que passou a responder quase sempre a mesma classe.

**Situação:** feito.

### 4.6 Critério de detecção e definição do piso

**Antes:**

... O desempenho de cada célula é medido pelo F1 macro, a média do F1 das duas classes~\cite{Sokolova2009}, e pela AUC, a área sob a curva ROC~\cite{fawcett2006}; #como as classes têm o mesmo tamanho, o acaso corresponde a 0,50 nas duas métricas.# ...

**Depois:**

... O desempenho de cada célula é medido pelo F1 macro, a média do F1 das duas classes~\cite{Sokolova2009}, e pela AUC, a área sob a curva ROC~\cite{fawcett2006}; #na AUC, o acaso corresponde a 0,50. No F1 macro, o valor sem sinal depende das decisões do classificador. Com classes do mesmo tamanho, um classificador sem sinal que divida as respostas entre as duas classes fica perto de 0,50, mas um que responda sempre a mesma classe fica em cerca de 0,33. Como o p-valor é calculado em relação a 0,50, um classificador que passe a responder sempre a mesma classe nunca é declarado detectado, de modo que esse comportamento pode esconder um sinal, mas não produzir uma detecção, e é assim que o caso da CNN 1D no GIFT-COFB com três rodadas é tratado (Seção~\ref{sec:res-modelos}).# ...

### 5.1 Calibração do critério de detecção (consequência)

**Antes:**

... #Nos números das próximas seções, o acaso corresponde a F1 e AUC de 0,50, já que as duas classes têm o mesmo tamanho.# ...

**Depois:**

... #Nos números das próximas seções, o acaso corresponde a AUC de 0,50. No F1 macro, um classificador sem sinal fica perto de 0,50 quando divide as respostas entre as duas classes e em cerca de 0,33 quando responde sempre a mesma classe.# ...

---

## 4.6. P-valor

> Precisamos conferir também o p-valor. Você usa a largura do intervalo bootstrap, divide por 1,96 e calcula um teste normal. Essa aproximação precisa ser justificada, principalmente nas bolsas maiores, com poucas decisões. A correção de múltiplos testes não resolve um p-valor mal calculado. Eu começaria conferindo as detecções mais fracas, que podem alterar o número de rodadas encontrado.

**Situação:** feito, com análise nova. Teste de permutação por chave (20 000 trocas de rótulo por chave inteira) nas 24 detecções com F1 abaixo de 0,9: todas se mantiveram, com p-valor de no máximo 0,005, nunca maior que o da aproximação normal. A 4.6 também foi reorganizada para separar os dois filtros: um parágrafo com os dois filtros e a correção de Benjamini-Hochberg (com a comparação com Bonferroni, que antes vinha depois da permutação), outro com o cálculo do p-valor e a justificativa da aproximação, e outro com o teto. A regra de considerar só o lado acima de 0,50 passou a vir antes da equação, e a explicação de que o p-valor é bicaudal, mas o teste é, na prática, unilateral, logo depois dela.

### 4.6 Critério de detecção e definição do piso

**Antes:**

... #(frases novas)# ...

**Depois:**

... #Como esse p-valor é bicaudal e só o lado acima de 0,50 é considerado, o teste é, na prática, unilateral, com nível de 2,5\%.# Essa conversão supõe que a distribuição bootstrap do F1 é aproximadamente normal, o que é menos seguro nas bolsas de 100 pares, que têm só 120 decisões. Por isso, as detecções com F1 abaixo de 0,9 foram conferidas também por um teste de permutação, em que, 20\,000 vezes, os rótulos das duas classes são trocados por chave inteira num subconjunto sorteado das chaves de teste, enquanto, acima de 0,9, o F1 fica tão longe de 0,50 que um erro da aproximação não muda a decisão. A troca por chave respeita a dependência entre as amostras de um mesmo dispositivo e não depende da aproximação normal. As 24 detecções desse tipo, nos estudos com o par e com o criptograma isolado, se mantiveram, com p-valor por permutação de no máximo 0,005, em nenhum caso maior que o da aproximação normal. No teste A/A, em que não há sinal, 2,8\% das células tiveram p-valor abaixo de 0,05, próximo dos 2,5\% esperados, e nenhuma passou pela correção (Seção~\ref{sec:res-calibracao}).# ...

### 6.6 Limitações reveladas pelos resultados (consequência)

**Antes:**

... essa célula deixa de passar, e o piso isolado do Schwaemm256-128 cai para um #passo.# ...

**Depois:**

... essa célula deixa de passar, e o piso isolado do Schwaemm256-128 cai para um #passo, embora o teste de permutação por chave a mantenha, com p-valor de 0,001.# ...

---

## 4.6. Teto da faixa de controle e monotonicidade

> O teto da faixa de controle e a exigência de detectar todas as rodadas anteriores são escolhas suas. Podem ser mantidas como critério do trabalho, mas não como uma fronteira natural da cifra. Metade das rodadas não garante ausência de sinal, e uma detecção isolada não é necessariamente ruído. Deixe claro que o resultado depende desse critério.

**Situação:** feito.

**Antes:**

... #A# ausência de sinal nessa faixa é uma #suposição, mas um erro nela vai na direção segura, um sinal real na faixa só aumentaria o teto e deixaria o critério# mais rigoroso. O teto e a regra de monotonicidade, descrita a seguir, #foram definidos neste trabalho.# O piso de uma célula é o maior número de rodadas em que ela é detectada, desde que todas as rodadas abaixo também sejam #detectadas, uma detecção que pula rodadas mais fracas é tratada como ruído de múltiplas comparações, e não como piso.# ...

**Depois:**

... #Metade das rodadas da especificação não garante ausência de sinal, e a# ausência de sinal nessa faixa é uma #suposição. Se ela estiver errada, o teto sobe e o critério fica# mais rigoroso. O teto e a regra de monotonicidade, descrita a seguir, #são escolhas deste trabalho, e não uma fronteira natural da cifra, e os pisos dependem delas. No estudo principal, nenhuma célula acima do piso passou pela correção de Benjamini-Hochberg, de modo que, nele, os pisos seriam os mesmos sem o teto e sem a regra de monotonicidade.# O piso de uma célula é o maior número de rodadas em que ela é detectada, desde que todas as rodadas abaixo também sejam #detectadas. Uma detecção isolada, acima de uma rodada não detectada, não entra no piso, por escolha do critério, embora não seja necessariamente ruído.# ...

Ainda na 4.6: "#muito acima da região em que o sinal aparece#" → "#acima da região em que o sinal apareceu nos experimentos#"; a frase redundante "O teto calibra o critério contra a oscilação real..." foi fundida com a anterior.

### 5.1 Calibração do critério de detecção (consequência)

"mas um erro nessa suposição vai na direção segura, já que um sinal real ali só aumentaria o teto e deixaria o critério mais rigoroso" → "#Se ela estiver errada, o teto sobe e o critério fica mais rigoroso.#", alinhado com a 4.6.

### 6.6 Limitações reveladas pelos resultados (consequência)

... Um critério menos rigoroso poderia apontar pisos maiores, #embora, no estudo principal, nenhuma célula acima do piso tenha passado pela correção de Benjamini-Hochberg, de modo que, ali, os pisos seriam os mesmos sem o teto e sem a regra de monotonicidade,# e a verificação descrita acima ...

---

## 4.7. Não detectar não demonstra segurança

> Está correta a ressalva de que não detectar não demonstra segurança. Mantenha isso nas conclusões, sem depois fazer afirmações que ultrapassem esse limite.

**Situação:** a 4.7 não precisou de mudança por essa crítica. O Capítulo 6 foi conferido para não ultrapassar esse limite.

### 6.2 De onde vem o piso (consequência)

**Antes:**

... Um adversário com mais dados, ou com um detector que saiba onde procurar, pode ir além, #mas# a queda de ordens de grandeza #a cada rodada indica# que cada rodada a mais #exige# ordens de grandeza a mais de #dados.# ...

**Depois:**

... Um adversário com mais dados, ou com um detector que saiba onde procurar, pode ir além, #e# a queda de ordens de grandeza #observada entre as rodadas medidas sugere# que cada rodada a mais #exija# ordens de grandeza a mais de #dados, embora isso não tenha sido medido além das rodadas da Tabela~\ref{tab:res-estatistico}.# ...

### 6.3 O piso e os detectores (consequência)

**Antes:**

... A busca de hiperparâmetros, as redes neurais e #cem vezes mais dados não subiram o piso de nenhum algoritmo# (Seção~\ref{sec:res-robustez}). #O piso medido não é, portanto, uma propriedade de um modelo específico, e sim da cifra vista por esse adversário, e o fato de um detector simples chegar ao mesmo ponto que os mais expressivos indica que a medida não depende da escolha do detector.#

**Depois:**

... A busca de hiperparâmetros, as redes neurais e #até cem vezes mais dados não subiram o piso de nenhum algoritmo com os detectores testados# (Seção~\ref{sec:res-robustez}). #Entre os detectores avaliados, portanto, o piso não dependeu de um modelo específico, e o fato de um detector simples chegar ao mesmo ponto que os mais expressivos indica que ele reflete a cifra vista por esse adversário, e não a escolha do detector.#

Também na 6.3: "No GIFT-COFB, #o sinal está em combinações de bits, como mostra o teste de contagem, em que# os maiores desvios aparecem em duplas" → "No GIFT-COFB, #o teste de contagem indica que o sinal está em combinações de bits, já que# os maiores desvios aparecem em duplas".

### 6.5 O que o piso significa na prática (consequência)

**Antes:**

... Como o viés cai em ordens de grandeza a cada rodada (Seção~\ref{sec:disc-origem}), cada rodada acima do piso #exige# um adversário passivo ordens de grandeza mais paciente ou com acesso a muito mais #dispositivos.#

**Depois:**

... Como o viés #observado# cai em ordens de grandeza a cada rodada (Seção~\ref{sec:disc-origem}), #é de se esperar que# cada rodada acima do piso #exija# um adversário passivo ordens de grandeza mais paciente ou com acesso a muito mais #dispositivos, embora isso não tenha sido medido.#

Também na 6.5: "As condições de uso mudam o piso #tanto quanto as rodadas#" → "As condições de uso #também# mudam o piso"; "dados comprimidos, #tende a dar# um piso menor, enquanto cabeçalhos fixos de protocolo #tendem a dar# um piso maior" → "#pode dar# ... #podem dar#".

### 6.6 Limitações reveladas pelos resultados (consequência)

"#Todas essas limitações só podem subestimar o piso estatístico.#" → "#As duas primeiras limitações só podem subestimar o piso estatístico, e a terceira é uma condição favorável ao adversário, que restringe a afirmação a dispositivos nessas condições.#" A terceira (pares de muitos dispositivos com os mesmos nonces) não subestima o piso, ela restringe a afirmação.

---

## 5.1. Interpretação do controle aleatório

> Reveja a interpretação do controle aleatório depois de acertar o item 4.3.2. Não podemos chamar as quatro detecções de falsos positivos sem descartar sinal na tag. Também não dá para dizer que vazamento apareceria em todas as rodadas. Retire essa justificativa geral.

**Situação:** feito, com uma pendência. As detecções do braço aleatório com a tag deixaram de ser chamadas de falsos positivos, e o parágrafo com a justificativa geral saiu. A taxa de falso positivo passou a vir do teste A/A. Com o teste de distância entre nonces, o total do braço aleatório passou de 2 184 para 3 804 células, e as detecções pelo critério completo, de quatro para dez (as seis novas vêm desse teste), todas com a tag e nenhuma formando piso. A Tabela 5.1 ganhou a coluna "sem a tag", e a abertura e o parágrafo depois da tabela passaram a separar os resultados com e sem a tag; "o critério não produz detecções onde não existe sinal" virou "não produz #piso# onde não existe sinal". **Pendente:** as dez detecções não foram reanalisadas sem a tag; o texto diz isso.

### 5.1 Controle negativo

**Antes:**

... Na parte cifrada, qualquer detecção nesse braço é, portanto, falso positivo por construção, a tag não tem essa garantia, #mas o braço, com a tag incluída, também não teve detecção. No estudo principal,# nenhuma das 180 células do braço aleatório teve p-valor abaixo de 0,05, nem antes da #correção,# e nenhum dos três algoritmos teve piso #nesse braço.#

**Depois:**

... Na parte cifrada, qualquer detecção nesse braço é, portanto, falso positivo por construção, #mas# a tag não tem essa garantia, #e uma detecção com a tag incluída pode ser sinal dela. Por isso, o controle foi feito com a tag e sem ela. Com a tag incluída, como no braço de texto,# nenhuma das 180 células do braço aleatório #do estudo principal# teve p-valor abaixo de 0,05, nem antes da #correção. Sem a tag, só com os 64 bytes de texto cifrado, uma das 180 células foi detectada, no GIFT-COFB com cinco rodadas, com o Random Forest e bolsas de 100 pares. Como, sem a tag, o braço aleatório não tem sinal possível, essa célula é um falso positivo do procedimento. Ela não formou piso, já que nenhuma rodada abaixo dela foi detectada nesse braço,# e nenhum dos três algoritmos teve piso #no braço aleatório, com a tag ou sem ela.#

### 5.1 Taxa de falso positivo

**Antes:**

#A taxa de falso positivo é a proporção de células declaradas detectadas quando não há sinal, e pode ser medida diretamente no braço aleatório, em que toda detecção é engano. Ela foi medida em todos os estudos de piso realizados com os três algoritmos, que somam 2\,184 células do braço aleatório e incluem as variações das Seções~\ref{sec:res-isolado}, \ref{sec:res-piso} e~\ref{sec:res-robustez}.# Antes de qualquer correção, 2,1\% ... #e o critério só declara piso quando todas as rodadas abaixo também são. Os indícios apontam para acaso, e não para defeito do classificador, da cifra ou vazamento de informação entre as classes. As quatro células estão espalhadas por algoritmos, rodadas, modelos e representações diferentes, sem padrão. Um vazamento entre as classes apareceria em todas as rodadas, e um defeito da cifra apareceria com mais força nas rodadas mais baixas, já que no braço aleatório só a tag poderia carregar alguma estrutura, e as rodadas mais baixas ficaram limpas. Além disso, em três das quatro configurações o teste de contagem da Seção~\ref{sec:res-estatistico} analisou o braço aleatório com pelo menos $10^9$ pares e não encontrou desvio em nenhum bit.#

**Depois:**

#Somando todos os estudos de piso realizados com os três algoritmos, inclusive as variações das Seções~\ref{sec:res-isolado}, \ref{sec:res-piso} e~\ref{sec:res-robustez}, o braço aleatório teve 3\,804 células, todas com a tag incluída.# Antes de qualquer correção, 1,9\% [...] restaram 0,37\%, e depois do critério completo 0,26\%, o que corresponde a dez células, [...] e seis no estudo com nonces a distância $k$ (Seção~\ref{sec:res-contador}). #Nenhuma delas formou piso, porque em nenhum dos dez casos a rodada 1 do mesmo braço foi detectada. Como essas células incluem a tag, que pode carregar estrutura da finalização reduzida, não é possível afirmar que sejam falsos positivos, e elas não foram reanalisadas sem a tag.#

#A taxa de falso positivo do procedimento foi medida, então, onde não há sinal possível, no teste A/A descrito na Seção~\ref{sec:met-braco-aleatorio}, em que as duas classes são amostras do mesmo processo aleatório. Nas 20 réplicas, com nove células cada, 5 das 180 células (2,8\%) tiveram p-valor abaixo de 0,05, próximo dos 2,5\% esperados, e nenhuma passou pela correção de Benjamini-Hochberg. O F1 sem sinal nenhum chegou a 0,510 com bolsas de um par, a 0,537 com bolsas de 10 e a 0,600 com bolsas de 100, o que mostra quanto as bolsas de 100 oscilam por acaso e por que o teto da faixa de controle é calculado separadamente para cada tamanho de bolsa.#

### 6.6 Limitações reveladas pelos resultados (consequência)

**Antes:**

(não existia)

**Depois:**

#O controle com texto aleatório também tem um limite. A tag é calculada na finalização, que também é reduzida, e pode ter estrutura mesmo com texto aleatório, de modo que as dez detecções no braço aleatório, todas com a tag incluída, não podem ser tratadas como falsos positivos sem uma nova análise sem a tag, que não foi feita para essas variações. No estudo principal, a análise sem a tag mostrou um falso positivo em 180 células, e o teste A/A, uma taxa de p-valores abaixo de 0,05 próxima da esperada, sem nenhuma detecção depois da correção (Seção~\ref{sec:res-calibracao}).#

---

## 5.2. Diluição do sinal

> A diluição do sinal é uma explicação possível, mas você mudou duas coisas ao mesmo tempo: tamanho da mensagem e representação. O experimento não separa os dois efeitos. Apresente como uma hipótese para o resultado, não como causa demonstrada. Não precisa acrescentar um experimento só para resolver isso agora.

**Situação:** feito.

### 5.2.1 Criptograma de 64 KB com atributos estatísticos

**Antes:**

... #A principal característica do desenho que explica a ausência de sinal# é a diluição: ... O Schwaemm256-128 com uma rodada #mostra esse efeito,# já que é separado dos dados aleatórios com F1 de 0,999 quando a mensagem tem 64 bytes e o classificador recebe os bits crus (Seção~\ref{sec:res-isolado-80b}), e fica no acaso quando o criptograma tem 64~KB e é descrito pelos atributos.

**Depois:**

... #Uma explicação possível# é a diluição: ... O Schwaemm256-128 com uma rodada #é compatível com essa hipótese,# já que é separado dos dados aleatórios com F1 de 0,999 quando a mensagem tem 64 bytes e o classificador recebe os bits crus (Seção~\ref{sec:res-isolado-80b}), e fica no acaso quando o criptograma tem 64~KB e é descrito pelos atributos. ##

Depois, a frase final que repetia a ressalva ("Como, de um experimento para o outro, mudaram ao mesmo tempo o tamanho da mensagem e a representação [...]") foi retirada da 5.2.1; a ideia de hipótese ficou em "Uma explicação possível" e "compatível com essa hipótese". Na 6.6, "são as explicações mais prováveis diante dos dados" virou "são #explicações possíveis#", e, na 6.4, "mostra que o desenho [...] não alcança o sinal que existe no início da mensagem" virou "#indica# que o desenho [...] #não alcançou o sinal, que, como hipótese, estaria no início da mensagem#".

### 6.1 Por que o par de mensagens revela a cifra (consequência)

**Antes:**

... #A# parte mal misturada fica no início da mensagem, ... O Schwaemm256-128 com um passo #mostra o efeito,# com F1 de 0,999 nos 80 bytes descritos pelos bits crus e no acaso nos 64~KB descritos pelos atributos. #A falha está, portanto, no que o classificador observa, e não na força da cifra, e foi essa a razão para# concentrar a análise nos primeiros bytes da mensagem, bit a bit.

**Depois:**

... #Uma explicação possível é que a# parte mal misturada fica no início da mensagem, ... O Schwaemm256-128 com um passo #é compatível com essa hipótese,# com F1 de 0,999 nos 80 bytes descritos pelos bits crus e no acaso nos 64~KB descritos pelos atributos. #Como, de um experimento para o outro, mudaram ao mesmo tempo o tamanho da mensagem e a representação, a diluição é uma hipótese, e não uma causa demonstrada, mas foi ela que motivou# concentrar a análise nos primeiros bytes da mensagem, bit a bit.

---

## 5.3. Seleção dos pares nos resultados

> Mantenha a seleção dos pares de nonces explícita ao apresentar os resultados. Evite passar de "foi detectado com esses pares e esse instrumento" para uma afirmação sobre qualquer sequência de mensagens.

**Situação:** feito. O teste de distância (item 4.1 e 4.3.3) mostra até onde o resultado vale para outros pares.

### 5.3 Piso de rodadas com pares de mensagens

**Antes:**

Observando duas mensagens #seguidas# do mesmo dispositivo, ... cifradas com a mesma chave e com nonces #consecutivos, $n$ e $n+1$.# ...

**Depois:**

Observando duas mensagens #consecutivas# do mesmo dispositivo, ... cifradas com a mesma chave e com nonces #consecutivos, $2j$ e $2j+1$, que diferem em um único bit quando o primeiro nonce é par (Seção~\ref{sec:met-dispositivos}). Os resultados desta seção foram obtidos com esses pares e com os detectores avaliados, e a Seção~\ref{sec:res-contador} mostra como o piso muda com pares de nonces mais distantes.# ...

### 5.6 Síntese (consequência)

**Antes:**

... Observando duas mensagens #seguidas# do mesmo dispositivo, o piso subiu para 3 das 12 rodadas no Ascon-AEAD128 ...

**Depois:**

... Observando duas mensagens #consecutivas# do mesmo dispositivo, o piso subiu para 3 das 12 rodadas no Ascon-AEAD128 ...

---

## 5.4.1. Inicialização e finalização

> Você conclui que o sinal vem inteiramente da inicialização. Mas, na descrição da redução, inicialização e finalização são reduzidas juntas. Como os classificadores recebem também a tag, essa comparação não separa os dois efeitos. Diga que o sinal persistiu quando a redução ficou restrita à inicialização e à finalização. Para atribuir tudo à inicialização, precisamos da evidência que a isole.

**Situação:** feito, com análise nova. Os estudos foram refeitos sem a tag, só com os 64 bytes de texto cifrado, que não passam pela finalização. Os pisos foram os mesmos (3, 3 e 2) e o F1 também (0,671, 0,595 e 0,998; com só a inicialização e a finalização reduzidas, 0,670 e 0,998). Essa é a evidência que isola a inicialização.

### 5.4.1 Diferenças entre inicialização e rodadas entre blocos

**Antes:**

... Com só a inicialização #reduzida,# o piso e a força do sinal foram praticamente iguais aos do experimento principal ... O #piso medido pelo adversário passivo é, portanto, inteiramente da inicialização.# ... (Tabela `tab:res-fase`: "inicialização")

**Depois:**

... Com só a inicialização #e a finalização reduzidas,# o piso e a força do sinal foram praticamente iguais aos do experimento principal ... O #sinal persistiu, portanto, quando a redução ficou restrita à inicialização e à finalização, e desapareceu quando ficou restrita às rodadas entre blocos. Como a finalização produz a tag, que também entra na amostra, essa comparação sozinha não separa a inicialização da finalização. Para separá-las, os dois estudos foram refeitos sem a tag, só com os 64 bytes de texto cifrado, que dependem da inicialização e das rodadas entre blocos, mas não da finalização, que só acontece depois do último bloco. Sem a tag, o piso e a força do sinal foram os mesmos. Com as duas fases reduzidas, o melhor F1 por par na rodada do piso foi de 0,671 no Ascon-AEAD128, 0,595 no GIFT-COFB e 0,998 no Schwaemm256-128, e, com só a inicialização e a finalização reduzidas, de 0,670 no Ascon-AEAD128 e 0,998 no Schwaemm256-128. Como o texto cifrado não passa pela finalização, a hipótese mais forte é que o sinal que define o piso venha da inicialização, mas ela não foi testada diretamente, já que nenhum estudo reduziu só a inicialização, com a finalização completa.# ... (Tabela `tab:res-fase`: "inicialização #e finalização#")

### 5.4 Robustez do piso, Tabela `tab:res-robustez` (consequência)

- "Só a inicialização #reduzida#" → "Só a inicialização #e a finalização reduzidas#"
- linha nova: #Sem a tag (só o texto cifrado) & 3 & 3 & 2#

### 5.6 Síntese (consequência)

**Antes:**

... e #vem inteiramente da inicialização, já que# reduzir só as rodadas entre blocos não produziu piso nenhum. ...

**Depois:**

... e #persistiu quando a redução ficou restrita à inicialização e à finalização, inclusive sem a tag, que é produzida pela finalização, enquanto# reduzir só as rodadas entre blocos não produziu piso nenhum. #A hipótese mais forte é, portanto, que o sinal que define o piso venha da inicialização.# ...

### 6.2 De onde vem o piso (consequência)

**Antes:**

... No Ascon-AEAD128 e no Schwaemm256-128, reduzir só a inicialização reproduziu o piso e a força do sinal do estudo principal, com F1 de 0,667 por par no Ascon-AEAD128 com três rodadas, contra 0,669, enquanto ...

**Depois:**

... No Ascon-AEAD128 e no Schwaemm256-128, reduzir só a inicialização #e a finalização# reproduziu o piso e a força do sinal do estudo principal, com F1 de 0,667 por par no Ascon-AEAD128 com três rodadas, contra 0,669, #e o mesmo aconteceu sem a tag, que é a única parte do criptograma produzida pela finalização,# enquanto ...

Também na 6.2, a frase que abre o parágrafo, "#O sinal vem inteiro da inicialização.#", virou "#A hipótese mais forte é que o sinal venha da inicialização.#", e "#A razão está no# que a Seção 6.1 mostrou" virou "#Essa hipótese é coerente com o# que a Seção 6.1 mostrou". No mesmo espírito, "#O que decide o piso, portanto, não é o número de rodadas de cada chamada, mas# quantas rodadas a diferença do nonce atravessa [...]. O GIFT-COFB #mostra isso de forma direta#" virou "#A hipótese, portanto, é que o piso dependa menos do número de rodadas de cada chamada que de# quantas rodadas a diferença do nonce atravessa [...]. O GIFT-COFB #ilustra essa hipótese#".

### 5.5.3 Dado associado no GIFT-COFB (consequência)

**Antes:**

... Nos três casos, o piso corresponde a #seis a oito rodadas da cifra de bloco antes do primeiro bloco de texto, e nenhuma configuração com nove ou mais foi detectada, o que é coerente com o resultado da Seção~\ref{sec:res-fase}: o que decide o piso é quanto o algoritmo mistura a diferença entre os nonces antes de o texto entrar.#

**Depois:**

... #Contando as rodadas da cifra de bloco antes do primeiro bloco de texto, o piso corresponde a oito rodadas sem dado associado e com um bloco, e a seis com dois blocos, e nenhuma configuração com nove ou mais rodadas antes do texto foi detectada. Isso é coerente com o resultado da Seção~\ref{sec:res-fase} e com a hipótese de que o piso depende de quanto o algoritmo mistura a diferença entre os nonces antes de o texto entrar.#

A mesma troca de "seis a oito" foi feita na 6.2. "Seis a oito" sugeria uma faixa medida, mas são dois valores (8 e 6), e o limite fica entre 8, detectado, e 9, não detectado.

### 6.6 Limitações reveladas pelos resultados (consequência)

Na lista de explicações inferidas, e não medidas, entrou: "#A origem do sinal na inicialização, já que nenhum estudo reduziu só a inicialização (Seção~\ref{sec:disc-origem}),#".

---

## 5.4.2. "Não decorre de falta de dados"

> Retire "não decorre de falta de dados". Você mostrou que aumentar os dados até os volumes testados não produziu detecção com aqueles modelos. É só isso que podemos concluir. O teste de contagem, aliás, encontrou sinal além dos classificadores.

**Situação:** feito.

### 5.4.2 Quantidade de dados

**Antes:**

... #A ausência de detecção acima do piso, portanto, não decorre de falta de dados para estes detectores. A Seção~\ref{sec:res-complexidade} mostra que, no GIFT-COFB com quatro rodadas, o sinal já estava presente nessa quantidade de pares, mas em combinações de bits que esses detectores não representam.#

**Depois:**

... #Até os volumes testados, portanto, mais dados não produziram detecção acima do piso com esses detectores. O teste de contagem da Seção~\ref{sec:res-estatistico} encontrou sinal além deles, no GIFT-COFB com quatro rodadas já com $10^{7}$ pares.#

### 5.6 Síntese (consequência)

**Antes:**

... #Mais dados de treinamento, até 3 milhões de pares,# hiperparâmetros ajustados e redes neurais não subiram o piso de nenhum algoritmo. ...

**Depois:**

... #Até os volumes e os modelos testados, mais dados de treinamento,# hiperparâmetros ajustados e redes neurais não subiram o piso de nenhum algoritmo. ...

### 6.3 O piso e os detectores (consequência)

"#cem vezes mais dados não subiram o piso de nenhum algoritmo#" → "#até cem vezes mais dados não subiram o piso de nenhum algoritmo com os detectores testados#" (o bloco completo está no item 4.7).

---

## 5.5. Cotas de viés e Šidák

> Precisamos conferir a conta das cotas de viés. Não passar do limiar não prova que o viés verdadeiro esteja abaixo de 0,0018% ou 0,0019%. Uma coisa é o viés observado; outra é um limite para o viés verdadeiro, com confiança declarada. Mostre como esses limites foram calculados e como entram as várias contagens e os pares que compartilham chave.
> Se essa conta ainda não estiver fundamentada, retire as cotas por enquanto. Basta informar que não houve detecção com a quantidade de dados usada. A correção de Šidák também precisa ser apresentada com as hipóteses do teste, e não como garantia automática para qualquer dependência entre as contagens.

**Situação:** feito. As cotas foram retiradas de todo o texto, e o Šidák passou a ser apresentado como aproximação, com o braço aleatório como controle empírico.

### 4.5.6 Teste de contagem

**Antes:**

... #Quando nenhuma contagem passa do limite, o teste fornece uma cota: o maior viés por bit que poderia existir sem ser detectado com aquela quantidade de pares.# O braço aleatório é contado da mesma forma, como #controle.# ...

**Depois:**

... #A correção de Šidák controla a chance de haver pelo menos um falso positivo numa família de testes quando as estatísticas são independentes. Aqui elas não são, já que duplas que compartilham um bit são correlacionadas e os 100 pares de um dispositivo compartilham a chave, e o limite é, portanto, uma aproximação.# O braço aleatório é contado da mesma forma, como #controle empírico desse limite. Quando nenhuma contagem passa do limite, o resultado é apenas que não houve detecção com aquela quantidade de pares.# ...

### 5.5 Piso estatístico (introdução)

**Antes:**

... O maior número de rodadas que ele detecta é o que aqui se chama de piso #estatístico, e, quando não detecta, ele fornece uma cota para o viés que ainda poderia existir.# ...

**Depois:**

... O maior número de rodadas que ele detecta é o que aqui se chama de piso #estatístico.# ...

### 5.5.1 O teste

**Antes:**

... acima do qual o desvio #não se explica por acaso. Quando nenhuma contagem passa do limite, o teste fornece uma cota: o maior viés por bit que poderia existir sem ser detectado com aquela quantidade de pares. O braço aleatório foi contado da mesma forma, como controle.#

**Depois:**

... acima do qual o desvio #é tratado como detecção. Como as contagens não são independentes, esse limite é uma aproximação, e o braço aleatório, contado da mesma forma, serve de controle empírico para ele (Seção~\ref{sec:met-teste-contagem}).#

### 5.5.2 Resultados

**Antes:**

Tabela `tab:res-estatistico`: GIFT-COFB r5 "não #detectado; viés por bit abaixo de 0,0018\%#"; Schwaemm256-128 r3 "não #detectado; viés por bit abaixo de 0,0019\%#". Texto: ... nenhuma contagem passou do limite com $10^{10}$ #pares. A cota indica que, se houver algum viés em bits isolados nessas rodadas, ele é menor que 0,002\%.# O Ascon-AEAD128 com cinco rodadas não foi medido nessa escala, e por isso #a linha dele não tem cota para a rodada seguinte ao piso estatístico.#

**Depois:**

Tabela: as duas linhas ficaram só "não #detectado#". Texto: ... nenhuma contagem passou do limite com $10^{10}$ #pares, ou seja, não houve detecção com essa quantidade de dados.# O Ascon-AEAD128 com cinco rodadas não foi medido nessa escala, e por isso #o seu piso estatístico é de quatro rodadas ou mais.# (Na Tabela `tab:res-sintese`, o Ascon-AEAD128 passou de "4" para "4 #ou mais#".)

### 6.2 De onde vem o piso (consequência)

**Antes:**

... No GIFT-COFB, passa de cerca de 0,09 com três rodadas para cerca de 0,002 com #quatro e fica abaixo de 0,00002 com cinco.# No Schwaemm256-128, ... com três, #o maior viés fica abaixo de 0,00002.# ... O teste de contagem, com cerca de 300 mil vezes mais pares, #alcança# vieses da ordem de milésimos a centésimos de milésimo, e por isso #vai# uma rodada além no Ascon-AEAD128 e no GIFT-COFB, mas #esbarra no salto seguinte.#

**Depois:**

... No GIFT-COFB, passa de cerca de 0,09 com três rodadas para cerca de 0,002 com #quatro, e, com cinco, nenhuma contagem passa do limite com $10^{10}$ pares.# No Schwaemm256-128, ... com três, #nenhuma contagem passa do limite com $10^{10}$ pares.# ... O teste de contagem, com #até# cerca de 300 mil vezes mais pares, #detectou# vieses da ordem de milésimos a centésimos de milésimo, e por isso #foi# uma rodada além no Ascon-AEAD128 e no GIFT-COFB, mas #não detectou a rodada seguinte.#

---

## 5.5. "Precisa de" 10 bilhões de pares

> No Ascon, você demonstrou detecção com cerca de 10 bilhões de pares. Não demonstrou que essa seja a quantidade mínima necessária para qualquer adversário. Troque "precisa de" por "foi detectado com". A réplica com novos pares é um cuidado importante; mantenha essa descrição.

**Situação:** feito. A réplica foi mantida. Uma ressalva que tinha sido acrescentada ("o que não mostra que essas sejam as quantidades mínimas para qualquer adversário") foi retirada depois, a pedido do Nycolas: a troca de "precisa de" por "foi detectado com" já atende à crítica. Na Tabela `tab:disc-literatura` (6.4), o piso estatístico do Ascon-AEAD128 passou de "4" para "#4 ou mais#".

### 5.5.2 Resultados

**Antes:**

... #A quantidade de dados que um adversário passivo precisa para detectar o Ascon-AEAD128 com quatro rodadas fica, portanto, na ordem de $10^{10}$ pares de mensagens, contra cerca de $10^{7}$ no GIFT-COFB.# ...

**Depois:**

... #O Ascon-AEAD128 com quatro rodadas foi detectado, portanto, com $10^{10}$ pares de mensagens, e o GIFT-COFB com quatro rodadas, já com $10^{7}$.# ...

### 6.4 Comparação com a literatura (consequência)

**Antes:**

... detectou o Ascon-AEAD128 com quatro rodadas, o mesmo número do distinguidor de Dobraunig et al., mas #precisou de# $10^{10}$ pares, ...

**Depois:**

... detectou o Ascon-AEAD128 com quatro rodadas, o mesmo número do distinguidor de Dobraunig et al., #com# $10^{10}$ pares, ...

### 6.5 O que o piso significa na prática (consequência)

**Antes:**

... O teste de contagem #precisou de $10^{7}$ pares no GIFT-COFB e de $10^{10}$ no Ascon-AEAD128 com quatro rodadas.# ...

**Depois:**

... O teste de contagem #detectou o GIFT-COFB com quatro rodadas com $10^{7}$ pares e o Ascon-AEAD128 com quatro rodadas com $10^{10}$.# ...

---

## 5.5.4. Ruído 13 vezes maior que o sinal

> De onde vem a estimativa de que o ruído é 13 vezes maior que o sinal e de que seriam necessários 100 milhões de exemplos? Se há uma derivação, apresente com suas hipóteses. Se não, trate como explicação possível. O fato de aqueles modelos não terem aprendido não demonstra, sozinho, a causa.

**Situação:** feito. A conta foi apresentada com a hipótese (ruído de estimação proporcional a pesos/exemplos) e como heurística.

### 5.5.4 Por que os classificadores não chegaram lá

**Antes:**

... #A explicação# é a quantidade de dados que um modelo precisa para aprender onde o sinal está. A regressão logística estima 8\,256 pesos com cerca de $8{,}5 \cdot 10^{6}$ #exemplos, e o ruído acumulado nessas estimativas é# cerca de 13 vezes maior que o sinal, #de modo# que aprender exigiria da ordem de $10^{8}$ exemplos ou mais. ... e #mostra que o piso dos classificadores é um limite do instrumento com aquela quantidade de dados, e não da cifra.#

**Depois:**

... #Uma explicação possível# é a quantidade de dados que um modelo precisa para aprender onde o sinal está. A regressão logística estima 8\,256 pesos com cerca de $8{,}5 \cdot 10^{6}$ #pares por classe no treinamento, os 85\% de $10^{7}$ reservados para isso, e uma estimativa aproximada, que trata o ruído de estimação dos pesos como proporcional ao número de pesos dividido pelo número de exemplos, dá um ruído# cerca de 13 vezes maior que o sinal, #o que sugere# que aprender exigiria da ordem de $10^{8}$ exemplos ou mais. #Essa estimativa é heurística, e o fato de esses modelos não terem aprendido não demonstra, sozinho, a causa.# ... e #é compatível com um piso dos classificadores que reflete o instrumento e a quantidade de dados usada.#

### 6.3 O piso e os detectores (consequência)

**Antes:**

O teste de contagem foi uma rodada além dos classificadores no Ascon-AEAD128 e no #GIFT-COFB porque# não precisa descobrir onde está o sinal. ... Um modelo treinado precisa estimar milhares de pesos, e o ruído acumulado nessas estimativas supera o #sinal,# ...

**Depois:**

O teste de contagem foi uma rodada além dos classificadores no Ascon-AEAD128 e no #GIFT-COFB, e uma explicação possível é que ele# não precisa descobrir onde está o sinal. ... Um modelo treinado precisa estimar milhares de pesos, e #uma estimativa aproximada indica que# o ruído acumulado nessas estimativas supera o #sinal (Seção~\ref{sec:res-complexidade}),# ...

---

## 5.6. Síntese

> A síntese deve acompanhar essas correções. Separe o que foi observado da explicação proposta. Preserve principalmente a ressalva de que o limite encontrado é do instrumento nas condições testadas, e não uma prova de segurança acima dele.

**Situação:** feito. As partes da síntese que acompanham outras críticas estão nos itens 5.3, 5.4.1, 5.4.2 e 5.5, acima.

### 5.6 Síntese

**Antes:**

... Em todos os casos, o piso é um limite do #instrumento, e não da cifra.# ... O Capítulo~\ref{cap:discussao} discute #o mecanismo por trás desses# resultados e os compara com a literatura.

**Depois:**

... #Esses são os resultados observados, e as explicações para eles ficam para o Capítulo~\ref{cap:discussao}.# Em todos os casos, o piso é um limite do #instrumento nas condições testadas, e não uma prova de segurança acima dele.# ... O Capítulo~\ref{cap:discussao} discute #as explicações propostas para esses# resultados e os compara com a literatura.

---

## Referências

> A referência 3 está com o número errado: o relatório da rodada final de criptografia leve é o IR 8454, não o IR 8459. As referências 3 e 14 parecem ser o mesmo relatório. Na referência 13 ficou "In: .". Confira também a autoria da especificação SPARKLE v1.2 na referência 40, que está incompleta.

**Situação:** feito.

- Referência 3: **IR 8459 → IR 8454** (número e DOI).
- Referências 3 e 14: as duas entradas do mesmo relatório (`nist_lwc_finalreport_2023` e `Turan2023NISTLWCFinal`) foram unificadas; o Capítulo 2 (`fundamentacao.tex`) passou a citar `Turan2023NISTLWCFinal`. Nenhum texto mudou, só a chave citada.
- Referência 13, *Cryptanalysis of Ascon* (Dobraunig et al.): o "In: ." vazio foi preenchido com *Topics in Cryptology (CT-RSA 2015)*, LNCS 9048, Springer, p. 371-387.
- Referência 40, especificação SPARKLE v1.2: autoria completada com **Amir Moradi** e **Aein Rezaei Shahmirzadi**, conferida na folha de rosto oficial.

---

## Para a próxima versão (orientação geral)

> Eu começaria por quatro pontos: descrever corretamente os pares de nonces; acertar o controle com texto aleatório; conferir o teste de detecção e as cotas; e reduzir as conclusões ao que foi medido. Não precisa refazer todos os experimentos por causa dessas observações. Primeiro precisamos saber o que é correção de texto e o que realmente exige nova análise.
> A separação por chave, o bootstrap por chave e a réplica do sinal fraco são cuidados que devem ser preservados. Vamos conferir os pontos acima para dar mais segurança à interpretação dos resultados.

| Ponto | Correção de texto | Análise nova |
|---|---|---|
| Pares de nonces | 4.1, 4.3.3 (pendente), 5.3, Cap. 6 | pares a distância $k$ ($k$ = 2 a 256) |
| Controle com texto aleatório | 4.3.2, 5.1, 6.6 | braço aleatório sem a tag; teste A/A |
| Teste de detecção e cotas | 4.5.6, 4.6, 5.5, 6.2 | permutação por chave nas 24 detecções fracas |
| Conclusões reduzidas ao medido | 5.2, 5.4.1, 5.4.2, 5.5.4, 5.6, Cap. 6 | retreino sem a tag (isola a inicialização) |

A separação por chave, o bootstrap por chave e a réplica do sinal fraco foram mantidos; as análises novas usam a mesma separação por chave.

---

## Mudanças que não vieram do orientador

Correções de coerência interna e uma referência, feitas na mesma rodada.

### 4.4.1 Criptograma de 64 KB com atributos estatísticos

**Motivo:** a frase falava de "um instrumento que não distinguia os algoritmos completos", referência à fase anterior da pesquisa, que não é apresentada nos Capítulos 4 a 6.

**Antes:** As doze famílias foram usadas para verificar se #um instrumento que não distinguia os algoritmos completos passaria a distinguir as versões enfraquecidas.# ...

**Depois:** As doze famílias foram usadas para verificar se #atributos calculados sobre o criptograma inteiro distinguiriam as versões enfraquecidas de dados aleatórios.# ...

### 4.5 Detectores e 4.5.1 Classificadores

**Motivo:** o texto dizia que os classificadores só recebem bits, mas no experimento de 64 KB eles recebem os 641 atributos.

- 4.5: ... em todos os #experimentos com bits crus.# → em todos os #experimentos, com bits crus ou com atributos.#
- 4.5.1: ... recebem cada bit da #amostra como uma variável.# → recebem cada bit da #amostra, ou cada atributo no experimento com criptogramas de 64~KB, como uma variável.#

### 4.7 Escopo e limitações do instrumento

**Motivo:** só o estudo principal usou 300 dispositivos; os estudos de quantidade de dados e de redes usaram mais.

... ou o XOR de duas, #e# foram treinados com os dados de 300 dispositivos. → ... ou o XOR de duas, #e, no estudo principal,# foram treinados com os dados de 300 dispositivos.

### 5.1 Calibração do critério de detecção

**Motivo:** a 5.1 falava em "dezenas de testes" e a 4.6 em "centenas"; cada algoritmo tem de 108 a 126 células.

"#dezenas de# testes" → "#mais de cem# testes" (duas ocorrências).

### 5.4.3 Modelos e hiperparâmetros

**Motivo:** a 5.4.3 dizia "configurações padrão", mas a 4.5.1 e a tabela de hiperparâmetros mostram valores fixados; e o termo "busca aninhada" já tinha sido trocado na metodologia.

**Antes:** Os classificadores do experimento principal usaram configurações #padrão.# Para verificar se um ajuste de hiperparâmetros mudaria o piso, foi feita uma busca #aninhada,# a configuração ...

**Depois:** Os classificadores do experimento principal usaram configurações #fixas, definidas antes dos experimentos.# Para verificar se um ajuste de hiperparâmetros mudaria o piso, foi feita uma busca #de hiperparâmetros com o teste separado, e# a configuração ...

### 5.6 Síntese

**Motivo:** levar para a síntese o resultado do piso de dados (Seção 5.3.3), escrito na mesma rodada.

... passou a ser detectada com F1 próximo de 1. #Na rodada do piso, um par observado já basta para que a distinção seja estatisticamente detectável, e cerca de 100 pares bastam para decidir sobre um dispositivo no Ascon-AEAD128 e no GIFT-COFB.#

### Capítulo 6 (abertura)

**Motivo:** a abertura ainda anunciava "o papel do aprendizado de máquina", mas a Seção 6.3 virou "O piso e os detectores".

- Comentário do topo do arquivo: "6.3 #papel do aprendizado de máquina#" → "6.3 #o piso e os detectores#".
- Texto: ... de onde vem o piso, #do papel do aprendizado de máquina,# da comparação ... → ... de onde vem o piso, #da relação entre o piso e os detectores,# da comparação ...

### 6.1 Por que o par de mensagens revela a cifra

**Motivo:** revisão de coerência da 6.1 contra os Capítulos 4 e 5, e pedidos do Nycolas.

- Referências na abertura: a equação $C = P \oplus M(K,n)$ passou a citar as especificações (#`nist_sp800232_2025`, `Banik2021`, `Beierle2021SparkleSub`#), a frase sobre cifra segura passou a citar #`Rogaway2004Nonce` e `KatzLindell2014IMC`#, e "o adversário passivo não a observa diretamente" ganhou a remissão #(Seção 4.1)#.
- Braço aleatório: "#e o par deixa de ser detectável com qualquer número de rodadas#" → "#na parte cifrada. Nesse braço houve detecções isoladas, mas a proporção de células com p-valor abaixo de 0,05 ficou dentro do esperado ao acaso, e nenhum dos três algoritmos teve piso em nenhum número de rodadas (Seção 5.1)#". A frase antiga contradizia a 5.1, que agora registra detecções no braço aleatório.
- Estrutura do texto em claro: "Dois trechos de texto #em inglês# [...] como #o bit mais significativo de cada byte, que é zero em texto ASCII# [...] e é #essa# estrutura" → "Dois trechos de texto [...] como #um bit mais significativo fixo em cada byte, que, em texto ASCII, por exemplo, é zero# [...] e é #esse tipo de# estrutura". Saiu "Nas posições em que o XOR dos textos é sempre zero, o XOR do par mostra diretamente a diferença entre as máscaras", que apresentava o mecanismo como certo. Entrou: "#O piso foi o mesmo com o corpus original, que inclui marcação HTML e livros em outros idiomas, e não diminuiu quando 20\% das mensagens foram trocadas por imagens, com uma única célula detectada no Ascon-AEAD128 com quatro rodadas, com F1 de 0,512 (Seção 5.4).#" (o braço misto foi medido só na rodada do piso, na seguinte e na da especificação). Para que a 6.1 tenha onde se apoiar, a 5.4 ganhou duas linhas na Tabela 5.6 (corpus original: 3, 3 e 2; 20% de imagens: 3 (4\*), 3 e 2), a abertura passou a citar "o nonce e a fonte do texto em claro" e "uma exceção marginal", e entrou um parágrafo com os F1: com as imagens, o F1 por par na rodada do piso caiu para 0,600, 0,547 e 0,959 (contra 0,669, 0,598 e 0,998), e com bolsas de 100 ficou em 0,882, 0,832 e 1,000.
- "#É por isso que# um classificador [...] reconhece o par" → "#Isso explicaria por que# um classificador [...] reconhece o par"; "Essa é #a explicação mais provável diante dos# resultados" → "Essa é #uma explicação possível para os# resultados".
- "#Um criptograma isolado não oferece essa comparação.#" → "#Com um criptograma isolado, não há uma segunda mensagem da mesma chave com que compará-lo, e a máscara não se cancela.#", para deixar claro a que "essa comparação" se referia.

### 6.3 O piso e os detectores

**Motivo:** a frase final afirmava que o teste de contagem "vai mais longe com os mesmos dados", mas, no geral, ele usou muito mais dados que os classificadores. Ficou: "#foi mais longe, no GIFT-COFB com quatro rodadas, com a mesma quantidade de pares com que a regressão logística e a MLP ficaram no acaso#", que é o caso em que os dados são de fato os mesmos.

### Referências

- *Lightweight AEAD and Hashing using the Sparkle Permutation Family* (2020): acento de "Léo" Perrin corrigido.
