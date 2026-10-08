# Os dados foram suficientes? (piso de rodadas)

Pergunta que a banca pode fazer: "o piso não subiu porque faltou dado?". Este
documento responde com a teoria de distinguidores e com uma medida feita nos
próprios dados. Números de 03/10/2026. Script: `scripts/reduced_rounds/sei_dados.py`;
saída em `build/reduced_rounds/floor_v2/sei_dados.json`.

## Resposta curta

Não faltou dado. Na rodada seguinte ao piso, o desvio da distribuição em
relação à uniforme é indistinguível de zero com 3,1 milhões de pares por
classe, nos quatro algoritmos. Pela teoria do distinguidor ótimo, um desvio
pequeno o bastante para passar por essa medida exigiria pelo menos 360 mil
pares do mesmo dispositivo para uma única decisão com 5% de erro, e da ordem
de um bilhão de pares só para aprender quais bits estão enviesados. Isso é
mais de 300 vezes o maior orçamento testado, e a mesma ordem de grandeza em
que o Gohr, com rede e treino em estágios, chegou a 51,4% de acerto na rodada
seguinte à fronteira dele.

## 1. A régua da literatura

**Baignères, Junod e Vaudenay (ASIACRYPT 2004), Teorema 6.** O distinguidor
ótimo entre uma distribuição D0 e a uniforme, com n amostras independentes,
erra com probabilidade Pe ≈ Φ(−√d / 2), em que d = n · SEI(D0). O SEI
(*squared Euclidean imbalance*) é |Z| · Σ (Pr[z] − 1/|Z|)². Em palavras: o
número de amostras necessário é inversamente proporcional ao SEI, n = d / SEI,
e para errar 5% é preciso d ≈ 10,8. Os autores lembram que um teste χ² precisa
de O(1/SEI) consultas, o que não é pior que o distinguidor ótimo a menos de uma
constante. O artigo recebeu o prêmio Test of Time da IACR em 2019.

**Matsui (EUROCRYPT 1993).** Na criptoanálise linear, o número de textos
necessário cresce com o inverso do quadrado do viés, e pelo *piling-up lemma*
o viés de uma aproximação de várias rodadas é o produto dos vieses de cada
rodada. É a razão de o custo em dados crescer exponencialmente a cada rodada.
Selçuk (Journal of Cryptology, 2008) formaliza a probabilidade de sucesso e o
requisito de dados de ataques lineares e diferenciais nessa mesma escala.

**Gohr, Leander e Neumann (ePrint 2022/1521).** Mostram correlação entre a
acurácia de distinguidores neurais e uma medida padrão de distância entre as
duas distribuições. É o que justifica usar o SEI como variável explicativa
também para as redes.

## 2. O SEI medido, e a validação da régua

O SEI do XOR dos pares foi estimado em três granularidades: por bit (640
distribuições de 2 valores, o que a contagem de bits e a regressão logística
enxergam), por byte (80 distribuições de 256 valores, que pegam estrutura
conjunta dentro do byte, como a S-box de 4 bits do GIFT) e por par de bytes
vizinhos (79 distribuições de 65.536 valores). O estimador desconta o valor
esperado sob a uniforme, (|Z| − 1)/N, e o braço aleatório, nulo provado, foi
medido junto como verificação do ruído (deu zero dentro do erro em todos os
casos).

Antes de usar a fórmula na rodada seguinte, ela foi conferida no piso, onde há
sinal. Prevendo o acerto por par a partir do SEI por bit:

| algoritmo (piso) | SEI por bit | acerto previsto por par | acerto medido (contagem de bits, 100x) |
|---|---|---|---|
| Ascon (3) | 0,643 | 65,6% | 66,5% |
| GIFT (3) | 0,035 | 53,7% | 53,5% |
| Grain (28) | 0,024 | 53,1% | 53,1% |
| Schwaemm (2) | 13,7 | 96,8% | 94,3% |

No Schwaemm, o SEI por byte (28,8) prevê 99,6%, e a melhor rede chegou a
99,4%: a parte do sinal que está dentro do byte é justamente a que a contagem
de bits não vê e a rede vê. A régua prevê os resultados com erro de cerca de um
ponto percentual, então serve para dizer o que aconteceria com mais dados.

## 3. A rodada seguinte ao piso

Limite superior do SEI (estimativa mais dois desvios padrão, com 3,1 milhões de
pares por classe):

| algoritmo (piso + 1) | SEI por bit ≤ | por byte ≤ | por par de bytes ≤ | queda em relação ao piso |
|---|---|---|---|---|
| Ascon (4) | 2,3 · 10⁻⁵ | 1,3 · 10⁻⁴ | 3,8 · 10⁻³ | ≥ 28.000 vezes |
| GIFT (4) | 2,3 · 10⁻⁵ | 1,3 · 10⁻⁴ | 2,7 · 10⁻³ | ≥ 1.500 vezes |
| Grain (29) | 2,2 · 10⁻⁵ | 1,7 · 10⁻⁴ | 2,0 · 10⁻³ | ≥ 1.100 vezes |
| Schwaemm (3) | 3,0 · 10⁻⁵ | 1,3 · 10⁻⁴ | 3,1 · 10⁻³ | ≥ 460.000 vezes |

O que isso implica, pela fórmula do Baignères:

- **Por decisão.** Com SEI ≤ 2,3 · 10⁻⁵, uma decisão com 5% de erro precisa de
  pelo menos 360 a 490 mil pares do mesmo dispositivo. Com os 100 pares por
  dispositivo do protocolo, o acerto máximo possível é cerca de 51%.
- **Para aprender.** Distribuído pelos 640 bits, esse SEI corresponde a um viés
  médio de cerca de 10⁻⁴ por bit. Estimar o sinal de um viés desse tamanho com
  três desvios padrão exige da ordem de 10⁹ pares, mais de 300 vezes o maior
  orçamento de treino testado (3 milhões de pares por classe).
- **Por rodada.** Uma rodada a mais derruba o SEI por um fator de pelo menos mil
  a quase meio milhão. Mais dados no orçamento atual (10x, 100x) movem o
  resultado em uma ou duas ordens de grandeza; a rodada seguinte pede três ou
  mais. É o comportamento previsto pelo *piling-up lemma*: o custo em dados é
  multiplicativo por rodada, não aditivo.

## 4. Os orçamentos da literatura

| trabalho | dados de treino | o que aconteceu na fronteira |
|---|---|---|
| Gohr (CRYPTO 2019), Speck32/64 | 10⁷ amostras (7 rodadas) | 7 rodadas: 61,6%. 8 rodadas: o treino normal "falha" (o modelo não aprende nada); com pré-treino em estágios e 2 · 10⁹ exemplos novos, 51,4% |
| Shen et al. (JISA 2024), GIFT-128 e Ascon | 2^23,2 ≈ 10⁷ amostras | distinguidores com diferença de entrada escolhida e estado inteiro observado |
| este trabalho, redes | 6 · 10⁵ (10x) e 6 · 10⁶ (100x, GIFT) amostras | rodada seguinte ao piso no acaso; no GIFT com 100x, perda de treino igual a ln 2, como no braço nulo |
| este trabalho, contagem de bits | até 6 · 10⁶ amostras (100x) | rodada seguinte ao piso no acaso nos quatro algoritmos |

O orçamento das redes está na mesma ordem que o do Gohr e do Shen. E o caso do
Gohr na 8ª rodada mostra o que acontece logo depois da fronteira: mesmo com 200
vezes mais exemplos e um treino feito para isso, o ganho é de 1,4 ponto
percentual. A fronteira é abrupta em dados, como a régua da seção 1 prevê.

O setting deste trabalho é mais difícil que o do Gohr e o do Shen, não mais
fácil: lá o atacante escolhe a diferença de entrada e vê a saída inteira;
aqui a diferença é a do nonce consecutivo, e o que se vê é só a parte de taxa,
misturada com a diferença de dois textos desconhecidos. Mais dados ajudariam
menos aqui do que lá, não mais.

Para o Ascon há ainda o limite estrutural: com 4 rodadas da permutação, toda
trilha diferencial ou linear tem pelo menos 36 S-boxes ativas, o que dá
probabilidade diferencial ou correlação ao quadrado de no máximo 2⁻⁷²
(Erlacher, Mendel e Eichlseder, ToSC 2022). Isso não é o mesmo ataque, mas
mostra a escala de dados de que se fala uma rodada depois do piso.

## 5. As evidências internas, que apontam para o mesmo lado

- **Curva de orçamento** (`piso_rodadas.md` §5.1.1): de 1x para 100x os dados, a
  rodada seguinte ao piso continua no acaso nos quatro algoritmos, com
  intervalo de confiança estreito, e no piso a contagem de bits satura já em
  10x.
- **Redes com 100x no GIFT** (`piso_rodadas.md` §5.1): na rodada 3 a ResNet
  continua melhorando com dados (56% para 62% por par), então ela não estava
  limitada pela arquitetura; na rodada 4, com 6 milhões de exemplos, a perda
  de treino fica em ln 2 da segunda época em diante, igual ao braço nulo. Nem
  dentro do conjunto de treino há o que aprender.

## 6. Limites desta resposta

- O SEI medido cobre estrutura dentro de bits, de bytes e de pares de bytes
  vizinhos. Um desvio espalhado por bits distantes, de ordem alta, não aparece
  nessas três medidas. Para esse caso a evidência é a das redes, que olham o
  vetor inteiro, e não uma prova. Por isso a afirmação continua sendo do
  instrumento: "este atacante, com até 3 milhões de pares, não separa a rodada
  seguinte", e nunca "a rodada seguinte é segura".
- A fórmula supõe amostras independentes. Os 100 pares de um dispositivo
  compartilham a chave, então a previsão para bolsas de 100 pares é otimista
  (prevê perto de 100% no piso do Ascon, onde se mediu 91%). Isso não afeta o
  argumento, porque na rodada seguinte o limite já é de 51% com a hipótese
  otimista.
- O limite superior usa dois desvios padrão sobre uma estimativa que pode ser
  negativa por ruído; com isso ele é conservador.

## Frase para a dissertação

> Na rodada seguinte ao piso, o desequilíbrio quadrático da distribuição dos
> pares em relação à uniforme ficou abaixo de 3 · 10⁻⁵ nos quatro algoritmos,
> medido com 3,1 milhões de pares por classe. Pelo resultado de Baignères,
> Junod e Vaudenay (2004), o distinguidor ótimo precisaria de mais de 3,6 · 10⁵
> pares de um mesmo dispositivo para decidir com 5% de erro, e da ordem de 10⁹
> pares para aprender os vieses, ordem de grandeza em que o distinguidor neural
> de Gohr (2019) já não supera o acaso de forma útil na rodada seguinte à sua
> fronteira. A mesma medida prevê, com erro de cerca de um ponto percentual, a
> acurácia observada no piso.

## Referências

- T. Baignères, P. Junod, S. Vaudenay. *How Far Can We Go Beyond Linear
  Cryptanalysis?* ASIACRYPT 2004, LNCS 3329.
  https://www.iacr.org/archive/asiacrypt2004/33290427/33290427.pdf
- M. Matsui. *Linear Cryptanalysis Method for DES Cipher.* EUROCRYPT 1993,
  LNCS 765.
- A. A. Selçuk. *On Probability of Success in Linear and Differential
  Cryptanalysis.* Journal of Cryptology 21(1), 2008.
  https://doi.org/10.1007/s00145-007-9013-7
- A. Gohr. *Improving Attacks on Round-Reduced Speck32/64 Using Deep
  Learning.* CRYPTO 2019. https://eprint.iacr.org/2019/037
- A. Gohr, G. Leander, P. Neumann. *An Assessment of Differential-Neural
  Distinguishers.* Cryptology ePrint Archive 2022/1521.
  https://eprint.iacr.org/2022/1521
- D. Shen et al. *Neural differential distinguishers for GIFT-128 and ASCON.*
  Journal of Information Security and Applications, 2024.
  https://www.sciencedirect.com/science/article/abs/pii/S2214212624000619
- J. Erlacher, F. Mendel, M. Eichlseder. *Bounds for the Security of Ascon
  against Differential and Linear Cryptanalysis.* IACR ToSC 2022(1).
  https://tosc.iacr.org/index.php/ToSC/article/view/9527
