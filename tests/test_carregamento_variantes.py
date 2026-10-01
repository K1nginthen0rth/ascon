"""Testes de isolamento entre variantes compiladas e da validação do GIFT puro.

Duas coisas que, se estiverem erradas, trocam a cifra por baixo sem que nada
acuse — e o piso medido passaria a ser de outro algoritmo.

**1. Isolamento entre `.pyd`.** A varredura do Grain carrega 21 variantes no
MESMO processo (`ciphers = {r: spec.cipher(r) for r in faltando}`). O código C
de referência do Grain tem estado global (`grain_round`), e `_load_module`
escreve em `sys.modules`. Se houvesse contaminação entre variantes, a rodada R
estaria medindo a cifra de outra contagem.

**2. Validação do GIFT em Python puro.** `PureGiftCOFB` só é confiável porque
é conferido contra o binário de produção em 40 rodadas. A checagem é cacheada
num global por processo. Havia um bug real aqui: `_build_gift` passava
`validate=(rounds == 40)`, então uma varredura de 1 a 12 nunca validava nada.
"""
from __future__ import annotations

import pytest

from scripts.reduced_rounds.floor_algos import ALGOS

KEY = bytes(range(16))
NONCE_GRAIN = bytes(range(16, 28))
PT = bytes(range(64))


def _grain(r: int):
    try:
        return ALGOS["grain"].cipher(r)
    except Exception as e:  # noqa: BLE001 - ambiente sem a variante compilada
        pytest.skip(f"variante grain init={r} indisponível: {e}")


# --- isolamento entre variantes -------------------------------------------

def test_variantes_carregadas_juntas_nao_se_contaminam() -> None:
    """Carregar N variantes no mesmo processo dá N criptogramas distintos."""
    contagens = [1, 2, 4, 8, 16, 32, 64, 128, 256]
    cifras = {r: _grain(r) for r in contagens}          # todas antes de cifrar
    saidas = {r: c.encrypt(KEY, NONCE_GRAIN, PT) for r, c in cifras.items()}
    assert len(set(saidas.values())) == len(contagens)


def test_carregar_outra_variante_nao_altera_a_anterior() -> None:
    a = _grain(32)
    antes = a.encrypt(KEY, NONCE_GRAIN, PT)
    _grain(64)                                           # carrega outra no meio
    assert a.encrypt(KEY, NONCE_GRAIN, PT) == antes


def test_recarregar_a_mesma_variante_da_o_mesmo_resultado() -> None:
    """`bench_custo` carrega a configuração da spec duas vezes (âncora)."""
    a, b = _grain(32), _grain(32)
    assert a.encrypt(KEY, NONCE_GRAIN, PT) == b.encrypt(KEY, NONCE_GRAIN, PT)


def test_a_ordem_de_carregamento_nao_muda_o_resultado() -> None:
    crescente = [_grain(r).encrypt(KEY, NONCE_GRAIN, PT) for r in (8, 16, 32)]
    decrescente = [_grain(r).encrypt(KEY, NONCE_GRAIN, PT) for r in (32, 16, 8)]
    assert crescente == decrescente[::-1]


# --- validação do GIFT puro contra o binário -------------------------------

def test_construir_gift_por_qualquer_contagem_dispara_a_validacao() -> None:
    """O bug: `validate=(rounds == 40)` fazia a varredura de 1 a 12 não validar.

    A checagem compara o Python puro com o `.pyd` em 40 rodadas, independente
    da contagem da instância, e é cacheada por processo — então condicioná-la
    ao número de rodadas só servia para pulá-la.
    """
    import scripts.reduced_rounds.gift_pure_cipher as gp

    anterior = gp._checked
    try:
        gp._checked = False
        ALGOS["gift"].cipher(3)          # contagem longe de 40
        assert gp._checked, "a validação contra o binário de produção não rodou"
    finally:
        gp._checked = anterior


def test_validacao_roda_uma_vez_so_por_processo() -> None:
    """Se rodasse a cada instância, a geração pagaria uma cifragem extra por
    rodada — e o cache é o que torna `validate=True` gratuito."""
    import scripts.reduced_rounds.gift_pure_cipher as gp

    anterior = gp._checked
    chamadas = []
    original = gp._check_against_production
    try:
        gp._checked = False

        def espiao():
            chamadas.append(1)
            original()

        gp._check_against_production = espiao
        for r in (1, 2, 3, 4):
            gp.PureGiftCOFB(r)
        # o espião é chamado sempre; quem corta é o `if _checked: return`
        assert len(chamadas) == 4
        assert gp._checked
    finally:
        gp._check_against_production = original
        gp._checked = anterior


# --- GIFT: Python puro x fixsliced compilado -------------------------------

def test_gift_puro_e_compilado_dao_o_mesmo_criptograma() -> None:
    """O elo entre as duas metades do estudo.

    O PISO do GIFT é medido com `PureGiftCOFB` (Python puro, granularidade de
    uma rodada) e o CUSTO com a variante fixsliced compilada (granularidade de
    5). As duas só descrevem o mesmo objeto se produzirem o mesmo criptograma
    nas contagens em que ambas existem. Sem este teste, piso e custo poderiam
    estar falando de cifras diferentes sem ninguém notar.
    """
    import random

    from scripts.reduced_rounds.gift_pure_cipher import PureGiftCOFB

    try:
        from scripts.reduced_rounds.build_variant import build_gift
        from scripts.reduced_rounds.reduced_wrapper import ReducedRoundsCipher
        compilados = {r: ReducedRoundsCipher(build_gift(r), "gift")
                      for r in (5, 20, 40)}
    except Exception as e:  # noqa: BLE001 - variantes não compiladas
        pytest.skip(f"variantes compiladas do GIFT indisponíveis: {e}")

    rng = random.Random(20260920)
    for r, comp in compilados.items():
        puro = PureGiftCOFB(r)
        for _ in range(25):
            k = bytes(rng.getrandbits(8) for _ in range(16))
            n = bytes(rng.getrandbits(8) for _ in range(16))
            pt = bytes(rng.getrandbits(8)
                       for _ in range(rng.choice([0, 1, 15, 16, 17, 64, 300])))
            ad = bytes(rng.getrandbits(8) for _ in range(rng.choice([0, 1, 20])))
            assert puro.encrypt(k, n, pt, ad) == comp.encrypt(k, n, pt, ad), r
