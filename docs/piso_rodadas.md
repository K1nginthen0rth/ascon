# Piso de rodadas dos finalistas do NIST LWC

Linha de trabalho corrente, aberta em setembro de 2026 depois da banca de
acompanhamento. Absorve o antigo `plano_piso_ascon.md`.

A pergunta mudou de lugar. O v1 e o v2 perguntam se dois algoritmos são
separáveis um do outro. Aqui a pergunta é por algoritmo: **com quantas rodadas
internas a saída ainda é separável de uma sequência uniforme do mesmo tamanho,
para quem só observa criptograma?** O maior R ainda detectado é o piso.

A leitura honesta do número é "abaixo de R, até este atacante genérico quebra".
Nunca "acima de R é seguro": o piso é do instrumento, e um modelo mais forte o
empurra para cima.

---

## 1. Estado

Medido em 30/09 e 01/10 com o gerador corrigido (seção 1.1): mesma amostra de
chaves, textos e nonces para os quatro algoritmos, e CV de 5 folds.

| Algoritmo | Unidade de rodada | Spec | Contador sorteado | Contador zero | Primeiro par | **Piso** | Fração |
|---|---|---|---|---|---|---|---|
| Ascon-AEAD128 | rodadas da permutação, eixo `ambos` | 12 | 3 | 3 | 3 | **3** | 25,0% |
| GIFT-COFB | rodadas do cifrador de bloco | 40 | 2 | 3 | 3 | **3** | 7,5% |
| Grain-128AEAD | clocks da fase INIT | 256 | 24 | 28 | 28 | **28** | 10,9% |
| Schwaemm256-128 | passos SPARKLE, eixo `ambos` | 11 | 2 | 2 | 2 | **2** | 18,2% |

No eixo `dados` (só o parâmetro entre blocos, com a inicialização completa), nem
Ascon nem Schwaemm têm piso, nem com 1 rodada. Nos braços de controle (texto
uniforme), nenhuma detecção em nenhum dos três cenários.

O piso da tese é o maior dos três cenários, e a frase que ele sustenta é:
abaixo de X rodadas, um atacante passivo distingue o criptograma de aleatório
pelo menos quando o contador do dispositivo está perto do zero. "Contador zero"
e "primeiro par" são os piores casos **testados**, não os piores possíveis.

"Célula" é um par (modelo, tamanho de bolsa); são 3 modelos × 3 bolsas = 9.
Todos os pisos dos cenários sorteado e contador zero têm 9 de 9 células
monotônicas, exceto o GIFT (8 de 9: uma célula com detecção espúria na rodada
8, descartada pela regra de monotonicidade). No primeiro par cada dispositivo
tem um par só, então não há bolsa: são 3 células, 3 de 3 em todos.

### 1.1 A correção do gerador e o estado do contador

A primeira rodada de medições (até 29/09) tinha dois problemas no gerador:

- **Contador de nonce global**, `2 × (chave × 100 + j)`. Todo nonce era um
  número menor que 60 mil, então 14 dos 16 bytes eram sempre zero, e a faixa de
  nonce identificava o dispositivo: as 60 chaves de teste traziam faixas que o
  treino nunca viu.
- **Amostra por algoritmo**: os rótulos do sorteio incluíam o nome do
  algoritmo, então cada um foi medido com chaves e textos próprios, e o GIFT
  ainda com outro runner e outra seed.

A correção (`ESQUEMA_AMOSTRA` em `run_floor.py`, com testes em
`tests/test_floor_amostra_compartilhada.py`): cada dispositivo tem o próprio
contador a partir de um offset sorteado, o par continua diferindo em exatamente
1 bit, e os quatro algoritmos recebem a mesma chave, o mesmo texto e o mesmo
nonce na mesma posição da amostra.

Com o gerador corrigido, o GIFT caiu de 3 para 2 e o Grain de 28 para 24. A
causa foi medida isolando o keystream (plaintext zero): no GIFT com 3 rodadas,
o par de nonces vizinhos tem 21 bits enviesados quando o resto do nonce é zero,
e nenhum quando o resto é aleatório. A diferença de 1 bit atravessa as S-boxes
de um jeito que depende dos bits vizinhos; com vizinhos sempre zero, ela se
espalha sempre igual e os mesmos bits cancelam em todo par. No GIFT-COFB o
nonce passa inteiro pelo GIFT-128 para gerar a máscara, então isso pesa. No
Ascon a diferença já sai determinística em 3 rodadas, com qualquer contexto.

Por isso o caso "contador perto do zero", que é real (dispositivo recém-ligado),
virou dois braços declarados, sem o artefato da faixa amarrada à chave:
`--contador zero` (todo dispositivo começa em 0 e usa os mesmos nonces) e
`--contador zero --pares-por-chave 1` (o "primeiro par": só os nonces 0 e 1, em
30.000 dispositivos). O contador zero devolve o 3 do GIFT e o 28 do Grain. O
primeiro par, que é o contexto mais fixo possível, fortalece o sinal no piso
(Schwaemm com 2 passos vai a F1 de 0,99 por par), mas **não sobe nenhum piso**,
inclusive no Grain, onde 29, 30 e 31 clocks foram compilados só para isso e
ficaram no acaso.

Uma triagem de outros contextos, com a mesma medida isolada do keystream,
mostrou que o zero é especial e não "qualquer constante": com um prefixo fixo
diferente de zero no nonce, ou com o contador gravado em little-endian, GIFT e
Grain perdem a rodada extra. Na prática, a construção recomendada (campo fixo do
dispositivo mais contador) fecha essa rodada.

Em rodadas absolutas GIFT e Ascon coincidem em 3, mas isso é coincidência de
escala: como fração da própria especificação, o Ascon precisa de 25% das rodadas
e o GIFT de 7,5%. A fração é o que permite comparar, e tem que ser relatada
junto do número absoluto.

## 2. Protocolo

Idêntico para os quatro algoritmos, porque é esse o ponto: Gerault et al.
(CiC 2025) listam a falta de comparabilidade entre distinguidores como problema
aberto do campo, e não existe na literatura um instrumento único aplicado aos
quatro finalistas.

**Modelo de acesso.** Adversário passivo, ciphertext-only. Mesma chave (mesmo
dispositivo), nonces públicos de contador consecutivos (n e n+1), plaintexts
diferentes e desconhecidos. Sem plaintext escolhido, sem diferença escolhida,
sem reuso de nonce.

**Representação.** XOR do payload mais XOR das tags de um par consecutivo.
Mensagem de 64 bytes, que são 4 blocos de 16 para o Ascon. Amostra única já foi
medida antes e dá acaso até na redução mínima, então o par é o mínimo que produz
sinal.

**Dados.** 300 chaves × 100 pares por chave (no primeiro par, 30.000 chaves ×
1 par). Classe negativa: bytes uniformes do CTR_DRBG, mesmo tamanho. Chaves,
textos e offsets de nonce são os mesmos para os quatro algoritmos (seção 1.1), e
contagens de rodada geradas em passadas diferentes continuam comparáveis.

**Split.** 240 chaves para treino, 60 para teste, sorteio com seed 42. IC 95%
por bootstrap de cluster (chave), não i.i.d.

**Validação cruzada.** As medições da seção 1 usam `--mode full`: `GroupKFold`
de 5 folds por chave dentro das 240 de treino, mais o holdout final, como pede a
Regra de Ouro 3. A primeira rodada (até 29/09) tinha usado `--mode sweep`, só o
holdout, e por isso também foi refeita.

**Modelos.** RandomForest, XGBoost e LogisticRegression, sobre os bits crus.
Tudo é Caminho A: nenhuma CNN, nenhum Transformer, nenhum híbrido. Os Caminhos
B a F do v2 não foram usados no estudo de piso.

**Curva de orçamento.** Além da decisão por amostra, agrega por dispositivo em
bolsas de 1, 10 e 100 pares, por média de log-odds. É combinação de escores
independentes, não um modelo multi-par, porque Gohr, Leander e Neumann
(ePrint 2022/1521) mostraram que os ganhos alegados por modelos multi-par
costumam desaparecer quando comparados dessa forma.

### Critério de detecção

Três barreiras, em `scripts/reduced_rounds/report_floor.py`. As três existem
porque as duas primeiras versões do critério produziram detecção na cifra
completa:

1. **BH-FDR com q = 0,05** sobre todas as configurações da varredura. Numa
   varredura de 12 rodadas × 3 modelos × 3 bolsas × 2 braços são 216 testes, e a
   95% de confiança cerca de 11 passam por acaso.
2. **Faixa de controle empírica.** A detecção só vale se o F1 superar o máximo
   observado nas rodadas altas, para o mesmo modelo e a mesma bolsa. Isso
   calibra contra o ruído real do pipeline em vez do 0,50 teórico. A faixa
   começa na metade do teto do eixo em uso, por algoritmo: um limiar fixo de 20
   é controle para o GIFT (spec 40) e região de sinal para o Grain (spec 256).
3. **Monotonicidade.** Só entra na manchete a célula que detecta em R e também
   em tudo abaixo de R. Detecção que pula as rodadas mais fracas é ruído de
   múltiplas comparações, não fronteira.

### O braço de controle, e por que ele é forte

Três braços de plaintext: `texto` (corpus Gutenberg), `imagem` e `aleatorio`.
O `aleatorio` é o mais informativo, e não pelo motivo óbvio.

Com rodadas reduzidas, `C1 xor C2 = (Y1 xor Y2) xor (P1 xor P2)`. A intenção
original era isolar a estrutura da cifra zerando o termo do plaintext. Não faz
isso, e não tem como: se P1 e P2 são uniformes e independentes da chave, então
`P1 xor P2` é uniforme e independente de `Y1 xor Y2`, logo o XOR inteiro é
exatamente uniforme, por mais fraca que a cifra seja. Nenhum detector pode
superar o acaso ali.

Então o braço tem verdade-terra provada em 0,50, e qualquer detecção nele é
falso positivo por construção. É assim que o instrumento se calibra. Medido:
nos três algoritmos, nenhum piso monotônico no braço `aleatorio`.

O que isso implica para a leitura dos números: em ciphertext-only a única coisa
explorável é a redundância do plaintext. **Um piso medido aqui é sempre uma
afirmação conjunta sobre a cifra E sobre a fonte, nunca sobre a cifra sozinha.**

## 3. Ascon: os dois eixos, e por que só um deu piso

O Ascon tem dois parâmetros de rodada, e a escolha de como reduzi-los muda o que
o piso significa:

- `ambos`: os dois caem juntos para r, com o de dados limitado à spec
  (`pa = r`, `pb = min(r, 8)`). Em r = 12 reproduz a especificação exata, o que
  é o que torna o ponto de controle um controle. Verificado: pa=12/pb=8 bate com
  o binário de produção em 50 de 50 cifragens.
- `dados`: reduz só o parâmetro entre blocos (`pa = 12`, `pb = r`). O eixo
  termina em 8, porque é ali que `pb` satura.

Resultado, braço `texto`, F1-macro com bolsa 1:

| r | eixo `ambos` (LR / RF / XGB) | eixo `dados` (LR / RF / XGB) |
|---|---|---|
| 1 | 0,977 / 0,982 / 0,996 | 0,493 / 0,496 / 0,499 |
| 2 | 0,970 / 0,974 / 0,988 | 0,496 / 0,493 / 0,498 |
| 3 | 0,649 / 0,646 / 0,649 | 0,489 / 0,500 / 0,497 |
| 4 | 0,502 / 0,500 / 0,499 | 0,499 / 0,493 / 0,492 |
| 8 | 0,493 / 0,502 / 0,504 | 0,501 / 0,501 / 0,502 |
| 12 | 0,501 / 0,501 / 0,502 | (fora do eixo) |

No eixo `ambos` o corte é abrupto: 0,98 em r = 1 e 2, cai para 0,65 em r = 3, e
de r = 4 em diante todas as 9 células ficam com IC cobrindo 0,50. Com bolsa 100
o r = 3 sobe para 0,890, e r = 4 não sobe.

No eixo `dados` não há piso nenhum, nem com `pb = 1`. Isso tem explicação
estrutural, e ela importa para o desenho: com `pa = 12` intacto, os dois estados
iniciais do par (nonces 2c e 2c+1, que diferem em 1 bit) passam pela
inicialização completa e ficam independentes. O que o par XOR enxerga, então, é
a inicialização, não a permutação de processamento de mensagem. **O sinal do
eixo `ambos` vem de a inicialização estar enfraquecida, não de `pb`.**

### Uma previsão que não se confirmou, e por quê

O plano anterior previa piso entre a 3ª e a 4ª rodada de 8 no eixo `pb`, por três
rotas de cálculo cruzando limites de correlação linear publicados (El Hirch,
Mella, Mehrdad, Daemen, ToSC 2022) com o volume de dados, e por uma quarta rota
independente vinda dos custos de forja de Dobraunig et al. (CT-RSA 2015).

A medição não confirma. Mas a previsão não estava errada sobre a cifra: ela é
sobre **correlação linear entre blocos consecutivos dentro da mesma mensagem**,
que é onde `pb` atua, e a representação por par XOR de duas mensagens distintas
não mede isso. A previsão segue testável; o que falta é o instrumento certo,
que é o teste linear direto da seção 5.

## 4. Ressalvas que precisam ser ditas junto dos números

**O piso 28 do Grain é o mais fraco.** Com contador zero, em 28 clocks o F1 por
par fica entre 0,507 e 0,517 e só passa com folga com bolsa (0,59 a 0,66); no
primeiro par, 0,51 a 0,52. É detecção, com controle limpo, mas o número vem com
a margem declarada. No caso geral (contador sorteado) o Grain para em 24.

**O piso depende do estado do contador.** GIFT e Grain ganham uma rodada com o
contador perto do zero; Ascon e Schwaemm não mudam. Sem declarar o cenário, o
número do GIFT e do Grain não tem leitura.

**Uma rodada de um não é uma rodada do outro.** Um clock do Grain não é uma
rodada da permutação do Ascon. Normalizar por fração da spec é o menos ruim, e
está implementado em `floor_algos.py::fracao_da_spec`, mas é uma escolha e tem
que estar declarada.

**O piso é do instrumento.** Os três modelos são clássicos sobre bits crus.
Nenhuma CNN, nenhum Transformer, nenhum distinguidor diferencial. Um modelo mais
forte empurra o piso para cima, e a afirmação que o trabalho sustenta é o limite
inferior, não o superior.

## 5. O que falta

1. **Par inteiro no lugar do XOR.** O Shen mostra que, com um par só, a entrada
   (C, C') acerta mais que a diferença C ⊕ C'. É a primeira pergunta que o
   desenho atual deixa aberta.
2. **Teste linear direto**, para fechar a previsão da seção 3. Correlação linear
   entre blocos consecutivos de criptograma, restrita às posições de bit em que o
   texto ASCII é previsível (o bit mais significativo de cada byte é zero em
   texto inglês, o que dá `corr_P = 1` exato). Roda em CPU, sem treino de
   modelo, e mede exatamente o que a representação por pares não mede.
3. **Braço `imagem`.** Os três pisos vieram só de `texto` e `aleatorio`. Como o
   piso é afirmação conjunta sobre cifra e fonte (seção 2), medir com uma fonte
   de redundância diferente é o teste direto de quanto do número depende da
   fonte.
4. **Eixo de custo.** Tempo por mensagem curta em cada variante reduzida, para
   converter "uma rodada a menos" em "tantos por cento mais leve". Sem isso a
   palavra "leve" fica sem número. Há `bench_custo.py` para isso.
5. **Outras fontes de texto.** O XOR de dois textos é enviesado também em
   português e em chinês UTF-8 (desvio máximo de 0,40 e 0,37, contra 0,47 do
   inglês), mas com força menor; no piso, onde o sinal já é fraco, isso pode
   mover o número.

## 6. Como reproduzir

```bash
# 1. compilar as variantes (exige ambiente MSVC; o .bat chama vcvarsall)
build_reduced_variant.bat --algo ascon --pa 3 --pb 3

# 2. medir (smoke primeiro, 10 chaves, valida o caminho inteiro)
python scripts/reduced_rounds/run_floor.py --algo ascon --smoke
# caso geral (contador sorteado)
python scripts/reduced_rounds/run_floor.py --algo ascon --arms texto aleatorio --mode full
python scripts/reduced_rounds/run_floor.py --algo ascon --politica dados --arms texto aleatorio --rounds 1 2 3 4 5 6 7 8 --mode full
# contador zero e primeiro par
python scripts/reduced_rounds/run_floor.py --algo ascon --contador zero --arms texto aleatorio --mode full
python scripts/reduced_rounds/run_floor.py --algo ascon --contador zero --pares-por-chave 1 --n-keys 30000 --n-test 6000 --arms texto aleatorio --mode full --rounds 2 3 4 12

# 3. determinar o piso (um diretório por cenário)
python scripts/reduced_rounds/report_floor.py --dir build/reduced_rounds/floor_v2/ascon_floor/reports --csv build/reduced_rounds/floor_v2/ascon_floor/piso.csv
```

Saídas em `build/reduced_rounds/floor_v2/` (gitignored): `<algo>_floor/` para o
contador sorteado, `contador_zero/<algo>_floor/` e
`contador_zero_ppk1/<algo>_floor/` para os outros dois. A primeira rodada, com o
gerador antigo, ficou em `build/reduced_rounds/<algo>_floor/` como registro.
Cada um tem `piso.csv` com uma linha por configuração, `reports/*_metrics.jsonl` append-only com o relato
completo, `reports/confusion_matrices/` e `sweep_full.log`.

Detalhe importante do `.jsonl`: o `run_id` não inclui a política, então os dois
eixos do Ascon escrevem no mesmo arquivo. Nada se perde, porque o arquivo é
append e cada linha carrega `extra.politica`, e o `report_floor.py` separa por
esse campo. As imagens de matriz de confusão, essas sim, são sobrescritas pelo
eixo que rodou por último.

## 7. Onde isso encosta na literatura

O texto completo, escrito para o orientador, está em
`relatorio_orientador_piso_rodadas.md`. O levantamento que o embasa, nove buscas
independentes, em `pesquisa_distinguishers/RELATORIO.md`. Em resumo:

- **Bellini & Huang (NIST LWC Workshop 2022)** aplicaram a bateria NIST STS às
  versões reduzidas dos finalistas. Sob entrada aleatória, a única das nove
  estratégias deles que corresponde a este cenário, acharam piso de 1 rodada
  para quase tudo, Ascon e GIFT incluídos. Aqui, com ML, o GIFT dá 3 e o Ascon
  dá 3. A diferença de 1 para 3 nos dois algoritmos é o resultado mais direto
  que este estudo produz contra a referência publicada. Diferenças: eles usam
  estatística fixa e não ML, e testam o primitivo isolado, não o esquema AEAD.
- **Shen et al. (JISA 2024)** treinam distinguidor diferencial neural e chegam a
  4 rodadas na permutação do Ascon e 7 de 40 no GIFT-128. Modelo de ameaça
  diferente: precisam escolher a diferença de entrada e obter as cifragens sob a
  mesma chave, o que não está disponível para quem só observa tráfego. E testam a
  peça isolada, não o AEAD.
- **Rajan et al. (2022)** treinam distinguidor diferencial sobre 6 rodadas do
  GIFT-COFB, o modo completo. Continua sendo diferença escolhida.

Nenhum trabalho publicado mede o piso dos esquemas AEAD completos sob adversário
passivo. Confirmado em duas buscas independentes, com formulações diferentes.
