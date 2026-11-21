# Criptograma isolado de 64 KB contra aleatório, com uma rodada

Rodado em 02/11/2026 (00h18 às ~7h50). Refaz o experimento da Seção 5.2.1, que
era Ascon contra GIFT, no desenho do resto do trabalho: cada algoritmo contra
a classe aleatória.

## Protocolo

- Algoritmos com uma rodada: Ascon-AEAD128 (pa = pb = 1), GIFT-COFB (1 rodada
  em todas as chamadas da cifra de bloco) e Schwaemm256-128 (big = slim = 1).
- GIFT-COFB pela implementação de referência oficial do NIST, com o número de
  rodadas exposto (`scripts/reduced_rounds/gift_oficial/`). Conferida antes da
  geração: 40 rodadas = binário de produção, 1 rodada = implementação em Python.
- Amostra igual à do piso: 300 dispositivos com 100 mensagens cada, fonte
  `texto-en`, contador de nonce começando do zero em cada dispositivo, as
  mesmas chaves e os mesmos textos para os três algoritmos. Classe aleatória
  do CTR_DRBG com o tamanho do criptograma (65 552 bytes).
- Cada amostra é um criptograma inteiro de 64 KB (texto cifrado + tag),
  descrito pelos 641 atributos estatísticos.
- Regressão logística, Random Forest e XGBoost (configurações da Seção 4.5.1),
  treino em 240 dispositivos e teste em 60 (6 000 mensagens por classe), bolsas
  de 1, 10 e 100 mensagens, BH (q = 0,05) por algoritmo, sobre as nove células de cada um, como no estudo principal.
- Faixa de controle e braço aleatório: não foram rodados, porque nenhuma célula passou no BH e não havia detecção a conferir.

## Resultado

**Nenhuma célula foi detectada em nenhum dos três algoritmos.** Os menores p-valores foram 0,439 (Ascon), 0,478 (GIFT) e 0,194 (Schwaemm).

| Algoritmo | Classificador | F1 bolsa 1 [IC 95%] | AUC bolsa 1 | F1 bolsa 10 | F1 bolsa 100 |
|---|---|---|---|---|---|
| Ascon r1 | RF | 0,504 [0,494; 0,514] | 0,502 | 0,494 | 0,533 |
| | XGBoost | 0,499 [0,490; 0,508] | 0,495 | 0,492 | 0,474 |
| | Reg. log. | 0,500 [0,490; 0,509] | 0,498 | 0,494 | 0,500 |
| GIFT r1 | RF | 0,502 [0,494; 0,511] | 0,498 | 0,490 | 0,423 |
| | XGBoost | 0,495 [0,487; 0,503] | 0,495 | 0,495 | 0,490 |
| | Reg. log. | 0,503 [0,493; 0,512] | 0,500 | 0,511 | 0,480 |
| Schwaemm r1 | RF | 0,498 [0,490; 0,506] | 0,494 | 0,482 | 0,418 |
| | XGBoost | 0,506 [0,497; 0,514] | 0,500 | 0,498 | 0,497 |
| | Reg. log. | 0,499 [0,490; 0,509] | 0,498 | 0,496 | 0,500 |

Matrizes de confusão do melhor F1 por mensagem (linhas: aleatório, cifra;
colunas: previsto aleatório, previsto cifra):

| Algoritmo | Modelo | Matriz |
|---|---|---|
| Ascon r1 | RF | [[3 124, 2 876], [3 075, 2 925]] |
| GIFT r1 | Reg. log. | [[3 068, 2 932], [3 029, 2 971]] |
| Schwaemm r1 | XGBoost | [[2 967, 3 033], [2 899, 3 101]] |

## Leitura

- Com uma rodada, nenhum dos três algoritmos se separa do aleatório quando o
  classificador vê o criptograma de 64 KB pelos atributos estatísticos. Isso
  inclui o Schwaemm256-128, que, no experimento de 80 bytes com bits crus,
  é separado com F1 de 0,999 com uma rodada.
- O contraste com os 80 bytes reforça a explicação da diluição da Seção 5.2.1:
  a parte mal misturada fica no início da mensagem, e os atributos, calculados
  sobre 65 552 bytes, não isolam essa região. A família da região da tag
  também não acusou nada.
- O F1 com bolsa de 100 oscila mais (de 0,418 a 0,533) porque o teste tem só
  60 decisões por classe nesse tamanho; nenhuma dessas células passa perto do
  BH.

## Integridade

- Atributos completos: 30 000 × 641 por classe; 1 ou 2 linhas com NaN por
  classe (zeradas antes do treino) e as mesmas 6 colunas constantes nas quatro
  classes.

## Arquivos

- `scripts/reduced_rounds/run_isolado_64k.py` (geração com checkpoint,
  extração, avaliação; `--smoke` para o teste rápido).
- `scripts/reduced_rounds/gift_oficial/build_rodadas.bat` (compila a GIFT
  oficial com `gift_rounds`; fontes e `.pyd` em
  `build/reduced_rounds/_gift_oficial_rodadas/`).
- Saídas em `build/reduced_rounds/floor_v2/isolado_64k/`:
  `isolado_64k_r1.csv`, `atributos_k300_m100.npz`, relatórios por célula em
  `reports/`, log em `run.log`.

Reproduzir: `python scripts/reduced_rounds/run_isolado_64k.py` (~7,5 h).
