"""
Descrição dos quatro finalistas para o estudo de piso de rodadas.

O runner de piso é o mesmo para todos; o que muda de algoritmo para algoritmo
é (a) o tamanho de chave, nonce e tag, (b) qual parâmetro conta como "rodada"
e (c) como se constrói o cifrador daquela contagem. Este módulo isola essas
três coisas.

Sobre o eixo de rodadas, que não é óbvio e precisa estar declarado:

- **GIFT-COFB** — rodadas do cifrador de bloco, 1 a 40. Granularidade de uma
  rodada vem de `gift_pure_cipher.PureGiftCOFB` (o `.pyd` fixsliced só desce
  de 5 em 5).
- **Grain-128AEAD** — clocks da fase INIT, 1 a 256. É a mesma contagem que a
  literatura de ataques de cubo usa quando relata 190 ou 193, então o número
  é diretamente comparável. A fase ADDKEY fica intacta.
- **Schwaemm256-128** — passos da permutação SPARKLE. A especificação usa
  `slim=7` entre blocos de dados e `big=11` na inicialização e finalização.
- **Ascon-AEAD128** — rodadas da permutação. A especificação usa `pa=12`
  (inicialização e finalização) e `pb=8` (entre blocos de dados).

Para Schwaemm e Ascon há DOIS parâmetros, e a escolha de como reduzi-los muda
o que o piso significa. Duas políticas, ambas implementadas:

- `ambos` (padrão) — os dois parâmetros caem juntos para `r`, com o parâmetro
  de dados limitado ao seu valor de spec (`pb <= 8`, `slim <= 7`). Assim o
  ponto de controle `r` = máximo da spec reproduz a especificação EXATA
  (Ascon 12/8, Schwaemm slim=7/big=11), e não uma construção inventada — é o
  que torna o controle um controle. Responde "quantas rodadas de permutação
  bastam", tratando o algoritmo como uma peça só.
- `dados` — reduz só o parâmetro entre blocos de dados (`pb`, `slim`) e mantém
  o de inicialização na spec. É o que mais importa em ciphertext-only, porque
  é essa permutação que produz o fluxo que mascara cada bloco. Aqui o eixo
  termina no teto do parâmetro de dados (`pb <= 8`, `slim <= 7`), e pedir mais
  é erro, não saturação silenciosa: Ascon de 8 a 12 daria cinco vezes o mesmo
  cifrador com cinco rótulos diferentes.

A política tem que ser relatada junto do piso; sem ela o número não quer dizer
nada. Ver o campo `politica` no metadado de cada execução.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable, NamedTuple

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


class AlgoFloor(NamedTuple):
    nome: str                       # rótulo curto, usado em nomes de arquivo
    rotulo: str                     # nome por extenso, usado em gráficos e matrizes
    key_bytes: int
    nonce_bytes: int
    tag_bytes: int
    max_rounds: int                 # valor de spec do eixo de rodadas
    unidade: str                    # o que "uma rodada" é, neste algoritmo
    dois_parametros: bool           # se aceita --politica
    construtor: Callable[[int, str], object]
    # Teto do parâmetro de DADOS (pb do Ascon, slim do Schwaemm). Sob
    # `politica="dados"` o eixo de rodadas É esse parâmetro, então pedir mais
    # que isto produziria configurações repetidas com rótulos diferentes.
    max_rounds_dados: int = 0
    # Varredura padrão. Existe porque "todas as contagens" é impraticável no
    # Grain: 1..256 mandaria compilar 256 `.pyd`. A lista cobre a região onde
    # o piso cai (fina embaixo) mais uma faixa de controle acima de metade da
    # spec, que é onde `report_floor.py` calibra o ruído.
    rounds_padrao: tuple[int, ...] = ()
    # Só o GIFT difere: o piso é medido em Python puro (granularidade de uma
    # rodada) e o custo, nas variantes compiladas (granularidade de 5). Para os
    # outros três é o mesmo construtor.
    construtor_custo: Callable[[int, str], object] | None = None

    def _validar(self, rounds: int, politica: str) -> None:
        if not isinstance(rounds, int) or isinstance(rounds, bool):
            raise ValueError(f"{self.nome}: rodadas deve ser inteiro, recebeu {rounds!r}")
        if not 1 <= rounds <= self.max_rounds:
            raise ValueError(
                f"{self.nome}: rodadas deve estar em [1,{self.max_rounds}], recebeu {rounds}")
        if politica not in ("ambos", "dados"):
            raise ValueError(f"política desconhecida: {politica!r}")
        if not self.dois_parametros and politica != "ambos":
            raise ValueError(
                f"{self.nome} tem um parâmetro só; política '{politica}' não se aplica")
        # Sob `dados`, o parâmetro de inicialização fica na spec e só o de
        # dados varia — então o eixo termina no teto DELE. Sem esta checagem,
        # Ascon com rounds 8..12 devolvia cinco vezes o mesmo cifrador
        # (pa=12, pb=8) rotulado como cinco contagens diferentes, inflando a
        # contagem de testes do BH-FDR e tornando o "controle" idêntico a r=8.
        if politica == "dados" and rounds > self.max_rounds_dados:
            raise ValueError(
                f"{self.nome} com política 'dados': rodadas deve estar em "
                f"[1,{self.max_rounds_dados}] (o parâmetro de dados satura aí); "
                f"recebeu {rounds}")

    def cipher(self, rounds: int, politica: str = "ambos"):
        """Cifrador para MEDIR PISO (granularidade fina onde ela existe)."""
        self._validar(rounds, politica)
        return self.construtor(rounds, politica)

    def cipher_para_custo(self, rounds: int, politica: str = "ambos"):
        """Variante COMPILADA, para medir tempo.

        Medir custo com a implementação em Python puro do GIFT não diria nada
        sobre o dispositivo real — seriam três ordens de grandeza a mais, todas
        do interpretador. Este acessor existe para que o benchmark nunca pegue
        o cifrador errado por engano. As mesmas validações do `cipher()` valem
        aqui: um teto violado é erro nos dois caminhos, não só num.
        """
        self._validar(rounds, politica)
        return (self.construtor_custo or self.construtor)(rounds, politica)


def _build_gift(rounds: int, politica: str):
    from scripts.reduced_rounds.gift_pure_cipher import PureGiftCOFB

    # `validate=True` SEMPRE, e não só em 40 rodadas. A checagem compara o
    # Python puro com o binário de produção em 40 rodadas, independentemente
    # da contagem desta instância, e é cacheada por processo — custa uma
    # cifragem. Condicioná-la a `rounds == 40` fazia uma varredura de 1 a 12
    # nunca validar nada: o Python puro poderia divergir do `.pyd` em silêncio.
    return PureGiftCOFB(rounds)


def _build_gift_compilado(rounds: int, politica: str):
    """Variante fixsliced. Só múltiplos de 5 — é a granularidade do QUINTUPLE_ROUND."""
    from scripts.reduced_rounds.build_variant import build_gift
    from scripts.reduced_rounds.reduced_wrapper import ReducedRoundsCipher

    return ReducedRoundsCipher(build_gift(rounds), "gift")


def _build_grain(rounds: int, politica: str):
    from scripts.reduced_rounds.build_variant import build_grain
    from scripts.reduced_rounds.reduced_wrapper import ReducedRoundsCipher

    return ReducedRoundsCipher(build_grain(rounds), "grain")


def _build_ascon(rounds: int, politica: str):
    from scripts.reduced_rounds.build_variant import build_ascon
    from scripts.reduced_rounds.reduced_wrapper import ReducedRoundsCipher

    pa, pb = (rounds, min(rounds, 8)) if politica == "ambos" else (12, min(rounds, 8))
    return ReducedRoundsCipher(build_ascon(pa, pb), "ascon")


def _build_schwaemm(rounds: int, politica: str):
    from scripts.reduced_rounds.build_variant import build_schwaemm
    from scripts.reduced_rounds.reduced_wrapper import ReducedRoundsCipher

    big, slim = (rounds, min(rounds, 7)) if politica == "ambos" else (11, min(rounds, 7))
    return ReducedRoundsCipher(build_schwaemm(slim, big), "schwaemm")


ALGOS: dict[str, AlgoFloor] = {
    "gift": AlgoFloor(
        nome="gift", rotulo="GIFT-COFB", key_bytes=16, nonce_bytes=16, tag_bytes=16,
        max_rounds=40, unidade="rodadas do cifrador de bloco",
        dois_parametros=False, construtor=_build_gift,
        construtor_custo=_build_gift_compilado,
        rounds_padrao=tuple(range(1, 13)) + (20, 25, 30, 35, 40)),
    "grain": AlgoFloor(
        nome="grain", rotulo="Grain-128AEAD", key_bytes=16, nonce_bytes=12, tag_bytes=8,
        max_rounds=256, unidade="clocks da fase INIT",
        dois_parametros=False, construtor=_build_grain,
        rounds_padrao=tuple(range(1, 13)) + (16, 20, 24, 28, 32, 160, 192, 224, 256)),
    "ascon": AlgoFloor(
        nome="ascon", rotulo="Ascon-AEAD128", key_bytes=16, nonce_bytes=16, tag_bytes=16,
        max_rounds=12, unidade="rodadas da permutação (pa; pb limitado a 8)",
        dois_parametros=True, max_rounds_dados=8, construtor=_build_ascon,
        rounds_padrao=tuple(range(1, 13))),
    "schwaemm": AlgoFloor(
        nome="schwaemm", rotulo="Schwaemm256-128", key_bytes=16, nonce_bytes=32, tag_bytes=16,
        max_rounds=11, unidade="passos SPARKLE (big; slim limitado a 7)",
        dois_parametros=True, max_rounds_dados=7, construtor=_build_schwaemm,
        rounds_padrao=tuple(range(1, 12))),
}


def fracao_da_spec(algo: str, rounds: int) -> float:
    """Rodadas como fração da spec, para comparar algoritmos entre si.

    Um clock do Grain não é uma rodada do Ascon, então o número absoluto não
    é comparável. A fração é o menos ruim, e é o que converte o piso em "quanto
    mais leve dá para ficar". Está aqui para ser relatada SEMPRE junto do
    número absoluto, nunca no lugar dele.
    """
    return rounds / ALGOS[algo].max_rounds
