# Guia de escrita da dissertação de mestrado

Como montar uma dissertação de mestrado: a estrutura geral, o que vai em cada
capítulo, e em detalhe o resumo e a introdução. Normas de referência: ABNT
NBR 14724 (estrutura), NBR 6028 (resumo), NBR 6023 (referências), NBR 6024
(numeração), NBR 6027 (sumário) e NBR 10520 (citações), mais o modelo
`abntex2ime` do IME.

---

## 1. Estrutura geral

A dissertação tem três blocos: o que vem antes do texto, o texto e o que vem
depois. A ordem dos elementos é fixa. Os capítulos do meio têm uma forma
consagrada, mas podem se fundir ou se desdobrar.

### 1.1 Pré-textuais (antes do texto)

Na ordem do modelo do IME:

| elemento | obrigatório? | observação |
|---|---|---|
| Capa | sim | |
| Folha de rosto | sim | diz que é dissertação ao programa, para o grau de mestre |
| Ficha catalográfica | sim | no verso da folha de rosto |
| Folha de aprovação | sim | banca e data de defesa |
| Dedicatória | não | |
| Agradecimentos | não | se houve bolsa, citar a agência é obrigatório |
| Epígrafe | não | |
| Resumo e palavras-chave | sim | ver a seção 2 |
| Abstract e keywords | sim | tradução fiel do resumo |
| Listas de figuras e de tabelas | sim, se houver | geradas automaticamente |
| Lista de quadros | não | só em português |
| Lista de siglas e de símbolos | não | opcional pela norma, mas praticamente necessária quando muitas siglas aparecem desde a introdução |
| Sumário | sim | último elemento pré-textual |

### 1.2 Textuais (o corpo)

O padrão de dissertação empírica de Computação:

| capítulo | função | pergunta que responde |
|---|---|---|
| **1. Introdução** | contexto, problema, justificativa, objetivos, contribuições, organização | o que, por que e o que foi feito? |
| **2. Fundamentação teórica** | só os conceitos que o leitor precisa para entender o resto | o que eu preciso saber para acompanhar? |
| **3. Trabalhos relacionados** | o que os outros fizeram, comparado criticamente, até chegar à lacuna | por que isso ainda não está resolvido? |
| **4. Metodologia** | dados, protocolo, decisões de projeto, com detalhe suficiente para reproduzir | como foi feito? |
| **5. Resultados e discussão** | o que foi medido, com números e incerteza, e o que significa; ameaças à validade | o que saiu, e o que isso quer dizer? |
| **6. Conclusão** | síntese, contribuições retomadas, limitações, trabalhos futuros | o que fica? |

O princípio por trás da ordem: **cada capítulo responde a uma pergunta que a
banca faz, na ordem em que ela faz.** Uma seção que não responde a nenhuma
pergunta da banca, nem abriga algum resultado, não precisa existir.

Uma variação comum é separar **Resultados** de **Discussão** em dois capítulos
(sete no total): os resultados dizem o que saiu; a discussão diz o que significa
e onde o trabalho pode estar errado. A separação evita o defeito de misturar
número com interpretação e deixa a conclusão livre para responder à pergunta da
introdução, em vez de repetir o resumo.

Três regras não mudam:

- **A introdução vem primeiro e a conclusão por último.**
- **Cada capítulo do meio abre anunciando o que vem nele** ("Este capítulo
  apresenta... A Seção 4.1...").
- **O que a introdução promete, o resto entrega.** Cada objetivo específico vira
  um pedaço da metodologia e um resultado.

### 1.3 Pós-textuais (depois do texto)

| elemento | obrigatório? | observação |
|---|---|---|
| Referências | sim | todas as obras citadas, e só elas |
| Apêndices | não | material **próprio**: tabelas longas, código, provas |
| Anexos | não | material **de terceiros**: especificações, normas |
| Índice remissivo | não | |

### 1.4 Onde vai cada coisa

| elemento | vai em |
|---|---|
| objetivo geral e específicos | introdução |
| problema de pesquisa | introdução |
| justificativa | introdução |
| hipótese | introdução, retomada nos resultados |
| contribuições | introdução, retomadas na conclusão |
| conceitos e definições | fundamentação |
| o que os outros fizeram | trabalhos relacionados |
| dados, particionamento, protocolo | metodologia |
| métricas, números, testes estatísticos | resultados |
| ameaças à validade | resultados (ou discussão, se for capítulo separado) |
| limitações e trabalhos futuros | conclusão |

Três coisas parecidas, com lugares diferentes. Misturar as três é comum e faz o
texto se repetir:

| o quê | onde | responde |
|---|---|---|
| **Escopo** | introdução | o que o trabalho decidiu não fazer |
| **Limitações do instrumento** | metodologia | o que o método não consegue medir |
| **Ameaças à validade** | resultados ou discussão | o que pode tornar as conclusões erradas, e o que foi feito para mitigar |

Na conclusão, as limitações aparecem num parágrafo que remete a essas três
seções, sem repeti-las.

---

## 2. Resumo

### 2.1 O que a norma exige (NBR 6028)

- **Parágrafo único**, sem listas nem tópicos.
- **Quatro partes, nesta ordem:** objetivo, método, resultados e conclusão.
- **Terceira pessoa** ("esta dissertação mede", "os resultados mostram").
- **Sem citações, sem fórmulas** e sem siglas que não sejam explicadas.
- **De 150 a 500 palavras.** Na prática, os bons ficam entre 200 e 300.
- **Autossuficiente:** quem lê só o resumo entende o trabalho.
- Logo abaixo, as **palavras-chave**, de 3 a 5.

### 2.2 O que faz um resumo ser bom

**1. Uma frase por movimento.** Os resumos ruins gastam três frases no contexto
e uma nos resultados. O peso deve ser o contrário.

| movimento | tamanho | pergunta que responde |
|---|---|---|
| contexto | 1 frase | por que isso importa? |
| lacuna | 1 frase | o que falta na literatura? |
| objetivo | 1 frase | o que este trabalho faz? |
| método | 1 a 2 frases | como? |
| resultados | 2 frases | o que saiu, com números |
| conclusão | 1 frase | o que isso significa, e até onde vale |

**2. O objetivo aparece cedo e numa frase só.** O leitor deveria saber o que o
trabalho faz até a terceira frase.

**3. O método fica no nível da ideia, não da configuração.** O que é
diferencial do protocolo entra; tamanhos de partição e parâmetros ficam para a
metodologia.

**4. Os resultados vêm com o número principal.** Detalhes secundários (controles,
variações) aparecem no máximo em meia frase.

**5. A conclusão diz o que o resultado permite afirmar**, e não só repete os números.

### 2.3 Erros comuns no resumo

- Contexto longo antes de chegar ao assunto.
- Método detalhado demais.
- Experimentos secundários ocupando frases inteiras.
- Resultados demais disputando atenção, sem um principal.
- Fórmulas e siglas sem explicação.

### 2.4 Abstract

Tradução fiel do resumo, com o mesmo conteúdo e a mesma ordem. Nem mais técnico
nem mais acadêmico que o original.

---

## 3. Introdução

Um bom capítulo de introdução faz uma única coisa: **convencer o leitor de que
existe um problema que vale resolver, e mostrar como o trabalho o resolve**.
Tudo o que entra nele serve a isso.

### 3.1 A estrutura

A ordem segue o formato de **funil**: começa largo (a área) e afunila até o
ponto exato que o trabalho ataca.

**1. Abertura, ou contextualização (sem título de seção)**
- Apresenta a área e por que ela importa hoje.
- Vai do geral ao específico em poucos parágrafos.
- Termina numa **tensão**: algo que não está resolvido. É ela que leva ao problema.

**2. Problema**
- A pergunta concreta que está em aberto.
- Precisa ser **delimitada**: não "a segurança de X é importante", e sim
  "não se sabe Y, nas condições Z".
- Costuma vir acompanhada da **lacuna**: o que a literatura já fez e o que
  falta, em poucas frases, sem virar revisão.

**3. Motivação ou justificativa**
- Por que resolver esse problema importa: impacto científico, técnico ou prático.
- Sustentada por evidência ou literatura, não por opinião.
- Pode ser uma seção própria ou um parágrafo dentro do problema.

**4. Hipótese (quando o trabalho testa uma)**
- A afirmação que será testada, em prosa.
- É retomada nos resultados.

**5. Objetivos**
- **Geral:** uma frase, com verbo no infinitivo, dizendo o que o trabalho
  entrega. "Avaliar", "determinar", "propor", "medir". Evite "estudar" ou
  "analisar" soltos, que não dizem o que sai no fim.
- **Específicos:** passos verificáveis que, somados, cumprem o geral. Cada um
  precisa corresponder a algo concreto mais à frente: um experimento, uma seção
  da metodologia, um resultado.

**6. Escopo (opcional)**
- O que o trabalho **não** faz. Evita que a banca cobre algo que nunca foi prometido.

**7. Contribuições**
- O que o trabalho entrega de novo, escrito como resultado ("evidência de
  que...", "um método para...", "um conjunto de dados...").
- Espelha os objetivos específicos e é retomada na conclusão.

**8. Organização do trabalho**
- Um parágrafo: "O Capítulo 2 apresenta... O Capítulo 3...".

### 3.2 Seções típicas

| seção | o que vai nela | tamanho típico |
|---|---|---|
| (abertura, sem título) | contexto, terminando na tensão que vira o problema | 2 a 4 parágrafos |
| Problema (ou Caracterização do problema, ou Motivação) | a pergunta em aberto e por que vale resolver; a hipótese, se houver | 2 a 4 parágrafos |
| Escopo (opcional) | o que o trabalho não faz | 1 parágrafo |
| Objetivos | o geral numa frase e os específicos em lista | 1 frase + 3 a 5 itens |
| Contribuições | o que a dissertação entrega de novo | 3 a 5 itens |
| Organização da dissertação | o que cada capítulo traz | 1 parágrafo |

### 3.3 O que torna uma introdução boa

- **O problema é específico.** O leitor consegue dizer em uma frase qual é a pergunta.
- **A lacuna é real e mostrada.** Fica claro por que os trabalhos existentes não
  respondem a pergunta.
- **Objetivos, método e resultados se encaixam.** Nada é prometido sem ser
  entregue, nada é entregue sem ter sido prometido.
- **É autossuficiente.** Quem lê só a introdução entende o que o trabalho fez,
  por que e qual é a contribuição.
- **Tem tamanho proporcional.** Em dissertação de mestrado, algo como 5 a 10
  páginas é comum, mais ou menos 5% a 10% do texto.

### 3.4 Os erros mais comuns

- **Virar revisão de literatura.** Citar estudo por estudo é trabalho do
  capítulo de trabalhos relacionados.
- **Virar fundamentação.** Definir conceitos técnicos a fundo é trabalho do
  capítulo 2. Na introdução, basta o necessário para entender o problema.
- **Repetir o mesmo conteúdo em duas seções** (por exemplo, a mesma teoria na
  abertura e no problema).
- **Contexto longo demais.** Três páginas sobre a importância da área antes de
  chegar à pergunta.
- **Afirmação sem fonte**, como projeções numéricas sem citação.
- **Citação que não sustenta a frase.** Conferir se cada obra citada diz de fato
  o que a frase atribui a ela, e não usar a mesma obra como prova de que algo
  "já foi feito" e de que "falta".
- **Objetivo vago.** "Estudar o comportamento de X" não diz o que o trabalho entrega.
- **Objetivos específicos que são entregáveis** ("construir um dataset") em vez
  de passos verificáveis ligados a experimentos.
- **Prometer mais do que se entrega.** É o erro mais cobrado pela banca.
- **Contar a história do projeto** ("primeiro tentei isto, depois aquilo"). A
  introdução apresenta o problema e a solução, não a cronologia de como se
  chegou nela.
- **Justificar dos dois lados.** "Se der positivo é bom, se der negativo
  também" enfraquece o problema: parece que qualquer resultado serve.

### 3.5 Uma dica de processo

**A introdução é o último capítulo a ser finalizado.** Dá para rascunhar no
começo, para fixar o problema e os objetivos. Mas a versão final só sai depois
que os resultados e a conclusão estão prontos, porque só então se sabe
exatamente o que foi entregue, e a introdução precisa prometer isso, nem mais
nem menos.

---

## 4. Os demais capítulos

### 4.1 Fundamentação teórica

- **Regra:** só entra o que algum resultado usa. Se um conceito não aparece na
  metodologia nem nos resultados, ele sai.
- Uma seção por bloco de conceitos, na ordem em que o leitor vai precisar deles.
- Explicar aqui o que a banca provavelmente não conhece (por exemplo, correções
  estatísticas para muitos testes) evita discutir o critério no meio dos resultados.

### 4.2 Trabalhos relacionados

- **Regra:** trazer os números que a banca vai comparar com os seus.
- Uma revisão sistemática (protocolo, bases, critérios, trabalhos selecionados e
  uma tabela de estado da arte) dá rigor ao capítulo.
- **Declarar o parentesco do método.** Se há técnicas antigas parecidas com a
  sua, citá-las antes que a banca as encontre transforma uma possível crítica em
  posicionamento.
- **Comparação com a literatura exige condições equivalentes declaradas.** Antes
  de dizer que o resultado é melhor ou pior que o de outro trabalho, conferir no
  artigo o experimento exato, o modelo de acesso e o custo, e listar as diferenças.
- **A lacuna se sustenta pela revisão, não por afirmação de ineditismo.** "Na
  revisão não foi encontrado trabalho que..." é defensável; "este é o primeiro
  trabalho a..." não é.

### 4.3 Metodologia

É o capítulo da contribuição metodológica, e costuma ser o mais longo. Em
trabalho empírico, ele costuma ter:

- **O modelo de ameaça ou de acesso** (em trabalhos de segurança): o que o
  adversário observa, o que só o experimento controla, e qual é a unidade de
  independência estatística. Qualquer relaxamento declarado aqui é defesa;
  escondido, é falha.
- **A definição operacional do que se mede**, com as regras que impedem leituras
  erradas (por exemplo: o que conta como detecção, o que não conta, e que
  ausência de detecção não é prova do contrário).
- **Os dados e a geração dos dados**, com cada escolha justificada em uma linha.
- **O instrumento e a sua validação**: como se sabe que a ferramenta mede o que
  diz medir.
- **O critério de decisão e os controles**: correção para múltiplos testes,
  controles negativos e positivos, separação de treino e teste.
- **Reprodutibilidade**: repositório, sementes, ambiente, comandos.
- **Limitações do instrumento**: o que o método não mede.

Se o instrumento ou um erro dos dados foi corrigido ao longo do trabalho, contar
isso aqui, antes que alguém descubra, transforma o erro em medida de robustez.

### 4.4 Resultados

- **Começar pela calibração do detector nos dados do experimento** (controles
  negativos e positivos, taxa real de falso positivo). A banca precisa acreditar
  na régua antes de olhar as medidas. A correção das ferramentas em si (testes
  que só passam ou não passam, feitos antes do experimento) fica na metodologia;
  nos resultados entra o que é medido nos dados.
- **Uma seção por objetivo específico, na ordem da introdução.** Se os resultados
  respondem a perguntas que a introdução não fez, um dos dois está errado.
- **Cada seção abre com o resultado em uma frase e um número.**
- **Nenhuma célula de tabela sem o tamanho da amostra (N).**
- **Nenhum mecanismo afirmado sem derivação.** Se a explicação não fecha, o
  achado fica como observação.
- **Nada não replicado apresentado como estabelecido.** O que é exploratório é
  marcado como exploratório.
- **Uma tabela-síntese que possa ser lida sozinha**, porque é a primeira coisa que
  a banca folheia.
- **Hipóteses "declaradas antes"** só valem para o que foi de fato escrito antes da
  análise correspondente, com data. Usar o rótulo além disso é o primeiro ataque
  da banca.

### 4.5 Discussão (quando separada dos resultados)

- O que os resultados significam, apresentado como interpretação avaliada contra
  os números, incluindo os casos que a contradizem.
- A comparação com a literatura, nas condições equivalentes declaradas.
- Implicações práticas, para quem usa o resultado fora da academia.
- Ameaças à validade: cada uma com o que foi feito para mitigar e o que ficou.

### 4.6 Conclusão

- **Resposta à pergunta da introdução, com as palavras dela e com os números.** A
  banca confere se as duas batem.
- **Contribuições**, as mesmas da introdução, agora com a evidência.
- **Limitações**, num parágrafo que remete ao escopo, à metodologia e às ameaças,
  sem repetir.
- **Trabalhos futuros.** Tudo o que foi cortado por falta de tempo vira uma linha aqui.

### 4.7 Apêndices úteis em trabalho empírico

- **Diário de decisões:** cada decisão tomada durante o trabalho que mudou o
  experimento (correções, escolhas feitas depois de ver resultados), com data e
  consequência. É a melhor resposta à pergunta "isso foi decidido antes ou depois
  de olhar os dados?".
- **Reprodutibilidade:** repositório, sementes, comandos.
- **Tabelas completas** por configuração, que não cabem no corpo.

---

## 5. Ordem de escrita

Escrever **do meio para fora**:

1. **Metodologia** primeiro: é o que mais tem material pronto e fixa o vocabulário
   dos outros capítulos.
2. **Resultados**, com as regras da seção 4.4 aplicadas desde a primeira tabela.
3. **Discussão**, só depois dos resultados, para não interpretar antes de ter os
   números na página.
4. **Introdução e conclusão juntas, por último** entre os capítulos textuais. Os
   objetivos e a resposta são escritos no mesmo dia, para baterem.
5. **Fundamentação e trabalhos relacionados** em paralelo com tudo, porque não
   dependem de decisão nenhuma.
6. **Apêndices** ao longo da escrita, à medida que cada decisão é citada.

**Cuidado com a ambição da estrutura.** Cada seção prometida no sumário é uma
obrigação de entrega. Antes de adotar uma estrutura, conferir se cada seção tem
material pronto; o que não tiver vira trabalho a fazer ou sai.
