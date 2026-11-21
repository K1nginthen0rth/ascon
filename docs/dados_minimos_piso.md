# Dados mínimos para detectar o piso

Rodado em 28–29/10/2026. Pergunta: na rodada do piso, quantos pares o atacante
precisa observar por decisão, e com quanto treino cada classificador detecta.

## Protocolo

- Rodadas do piso: Ascon-AEAD128 r3, GIFT-COFB r3, Schwaemm256-128 r2. Controles:
  rodada da especificação (r12, r40, r11) e braço aleatório (texto em claro uniforme).
- Amostragem igual à do estudo principal: contador perto do zero, XOR de pares
  consecutivos, fonte `texto-en`, classe concorrente gerada por CTR_DRBG.
- Teste fixo: 1 000 dispositivos (100 000 pares por classe), separados por chave.
- Treino: n pares da cifra + n amostras aleatórias, tirados de uma permutação fixa
  dos 30 000 pares dos 300 dispositivos de treino (conjuntos aninhados).
- Pares observados por decisão (bolsa): 1, 10 e 100 pares do mesmo dispositivo,
  decisão pelo sinal da média dos log-odds.
- Critério: BH (q = 0,05) sobre todas as células do algoritmo. Teto por
  (classificador, treino, bolsa): maior F1 entre a rodada da especificação no texto
  e as duas rodadas do braço aleatório. O braço aleatório é medido só contra a
  rodada da especificação.
- Mínimo: menor treino a partir do qual todos os níveis maiores da grade também
  são detectados.

## Resultado 1: pares observados por decisão

**Um par basta, nos três algoritmos e nos três classificadores, desde que o
treino seja suficiente.** A grade anterior (`dados_minimos_*.csv`, 3 a 300
dispositivos) já mostrava isso: com 300 dispositivos de treino, todas as células
de bolsa 1 na rodada do piso foram detectadas. Bolsas maiores só aumentam o F1.
Por exemplo, no Ascon r3 com 30 000 pares de treino, o F1 vai de 0,68 com 1 par
a 0,94 com 100 pares.

## Resultado 2: menor treino por classificador (pares por classe)

| Algoritmo | Classificador | bolsa 1 | bolsa 10 | bolsa 100 |
|---|---|---|---|---|
| Ascon r3 | Regressão logística | 1 | 5 | 100 |
| | Random Forest | 10 | 20 | 50 |
| | XGBoost | 50 | 50 | 50 |
| GIFT r3 | Regressão logística | 1 000 | 1 000 | 2 000 |
| | Random Forest | 2 000 | 2 000 | 2 000 |
| | XGBoost | 700 | 700 | 800 |
| Schwaemm r2 | Regressão logística | 1 | 1 | 1 |
| | Random Forest | 1 | 1 | 2 |
| | XGBoost | 10 | 5 | 10 |

Grades: Ascon e Schwaemm 1, 2, 5, 10, 20, 50, 100, 200, 300; GIFT 300, 400,
500, 600, 700, 800, 1 000, 2 000, 3 000, 5 000. Valores em 1 par são o mínimo
absoluto.

Braço aleatório: 0 de 504 células detectadas (F1 máximo 0,523).

## Ressalvas

- **Ascon, regressão logística com 1 ou 2 pares:** é detectado (F1 de 0,507 e
  0,503, com p de 0,004 em 2 pares e acima de todas as 16 células de controle,
  cujo máximo é 0,5008), mas o sinal é marginal. Esse mínimo só é estável com
  bolsa de 1. Com bolsas de 10 e 100 e pouco treino, o F1 oscila e chega a ficar
  abaixo de 0,50 (0,419 com 2 pares e bolsa de 100), provavelmente porque a média
  dos log-odds amplifica um deslocamento de calibração do modelo. Com bolsa de 1,
  a afirmação segura para o Ascon é que, a partir de 50 pares de treino, os três
  classificadores detectam.
- **XGBoost com 1 ou 2 pares:** F1 = 0,333, ou seja, o modelo prevê uma classe
  só. Isso é um modelo degenerado, e não uma medida de sinal.
- **GIFT:** abaixo do mínimo, há detecções isoladas (RF com 300 e 700 pares), que
  não contam porque não se mantêm nos níveis seguintes. Na grade antiga, com 300
  pares (3 dispositivos), nenhum classificador detectava; com 3 000 pares, os três
  detectavam em todas as bolsas.
- O treino é contado em pares por classe; o conjunto de treino tem o dobro de
  exemplos (cifra + aleatório).
- A grade antiga (por dispositivo, teto de uma célula só) teve 7 falsos positivos
  em 630 células, todos na rodada da especificação. Na grade fina, com o teto
  ampliado, foram 0 de 504.

## Arquivos

- `scripts/reduced_rounds/run_dados_minimos.py`: grade por dispositivo.
- `scripts/reduced_rounds/run_dados_minimos_fino.py`: grade fina por pares
  (`--pares` para estender).
- `scripts/reduced_rounds/consolidar_dados_minimos.py`: junta a grade fina e a
  extensão e reaplica o critério.
- Saídas: `build/reduced_rounds/floor_v2/dados_minimos/` (`dados_minimos_fino_consolidado*.csv`,
  relatórios por célula em `reports_fino/`).

Reproduzir:
```bash
python scripts/reduced_rounds/run_dados_minimos_fino.py --algos ascon
python scripts/reduced_rounds/run_dados_minimos_fino.py --algos ascon --pares 1
python scripts/reduced_rounds/consolidar_dados_minimos.py
```
