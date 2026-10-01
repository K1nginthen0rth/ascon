"""Testes do eixo de custo (`bench_custo.py`).

É o script que converte "menos rodadas" em "% mais leve", então o que importa
é que ele não afirme mais do que mediu e não se contradiga.

Casos que já deram errado de verdade:
 - o relatório imprimia a MESMA medição como 1.58 no laço e 1.57 na tabela,
   por arredondamento duplo (o laço formatava o valor bruto, a tabela o valor
   já arredondado para 3 casas);
 - com 3 pontos o R² dava ~1 sozinho e o script afirmava linearidade sem
   evidência nenhuma;
 - uma varredura com outro processo pesado na máquina produziu um salto de
   70% no meio da curva que não existe na cifra — daí a âncora de deriva.
"""
from __future__ import annotations

import numpy as np
import pytest

from scripts.reduced_rounds.bench_custo import (
    CASAS, MIN_PONTOS_LINEARIDADE, _r2_linear, imprimir,
)


# --- R²: comparado contra referência independente --------------------------

@pytest.mark.parametrize("xs,ys", [
    ([1, 2, 3, 4, 5], [2.0, 4.0, 6.0, 8.0, 10.0]),
    ([1, 2, 3, 4, 5, 6], [2.1, 3.9, 6.2, 7.8, 10.1, 12.0]),
    ([1, 2, 3, 4, 5, 6], [1.0, 4.0, 9.0, 16.0, 25.0, 36.0]),
])
def test_r2_bate_com_numpy(xs: list[int], ys: list[float]) -> None:
    b, a = np.polyfit(xs, ys, 1)
    pred = a + b * np.array(xs)
    ss_res = ((np.array(ys) - pred) ** 2).sum()
    ss_tot = ((np.array(ys) - np.mean(ys)) ** 2).sum()
    assert _r2_linear(xs, ys) == pytest.approx(1 - ss_res / ss_tot, abs=1e-9)


def test_r2_exige_pontos_suficientes() -> None:
    """Com 3 pontos um ajuste de 2 parâmetros quase sempre dá R² ~ 1."""
    assert MIN_PONTOS_LINEARIDADE >= 5
    poucos = list(range(1, MIN_PONTOS_LINEARIDADE))
    assert _r2_linear(poucos, [float(x) for x in poucos]) is None


def test_r2_indefinido_quando_nao_ha_variacao() -> None:
    n = MIN_PONTOS_LINEARIDADE
    assert _r2_linear(list(range(n)), [7.0] * n) is None      # y constante
    assert _r2_linear([3] * n, [float(i) for i in range(n)]) is None  # x constante


# --- relatório: não pode se contradizer ------------------------------------

def _resultado(**over) -> dict:
    base = dict(algo="x", rotulo="Cifra X", unidade="rodadas", rounds_spec=40,
                msg_bytes=64, repeticoes=5, n_por_bloco=2000,
                us_por_msg={"5": 1.575, "40": 3.15},
                us_na_spec=3.15,
                economia_pct_vs_spec={"5": 50.0, "40": 0.0},
                deriva_pct=0.2, r2_ajuste_linear=None)
    base.update(over)
    return base


def test_valor_guardado_e_o_mesmo_que_o_laco_imprime() -> None:
    """Contrato do arredondamento: medida e relato usam a MESMA precisão."""
    assert CASAS == 3
    us = round(1.5751, CASAS)
    assert f"{us:.2f}" == f"{round(us, CASAS):.2f}"


def test_economia_e_encontrada_apesar_da_ida_ao_json(capsys) -> None:
    """As chaves viram str no JSON; com int o `.get()` devolvia None na volta."""
    imprimir(_resultado())
    saida = capsys.readouterr().out
    assert "+50.0%" in saida
    assert "-" not in saida.split("economia vs spec")[1].split("\n")[1]


def test_deriva_alta_invalida_a_medicao(capsys) -> None:
    imprimir(_resultado(deriva_pct=9.0, r2_ajuste_linear=0.999))
    saida = capsys.readouterr().out
    assert "MEDIÇÃO INVÁLIDA" in saida
    # com a medição invalidada, não faz sentido afirmar linearidade
    assert "linear" not in saida.split("MEDIÇÃO INVÁLIDA")[1]


def test_linearidade_so_e_afirmada_com_r2_alto(capsys) -> None:
    imprimir(_resultado(r2_ajuste_linear=0.9986))
    assert "interpolar entre pontos medidos é defensável" in capsys.readouterr().out
    imprimir(_resultado(r2_ajuste_linear=0.75))
    assert "NÃO é linear" in capsys.readouterr().out


def test_sem_pontos_suficientes_nao_afirma_nada(capsys) -> None:
    imprimir(_resultado(r2_ajuste_linear=None))
    saida = capsys.readouterr().out
    assert "linearidade não avaliada" in saida
    assert "defensável" not in saida


def test_variante_ausente_nao_derruba_o_relatorio(capsys) -> None:
    """Sem a variante da spec não há base de comparação, e isso tem que
    aparecer como '-' em vez de porcentagem inventada."""
    imprimir(_resultado(us_por_msg={"5": 1.5}, us_na_spec=None,
                        economia_pct_vs_spec={}))
    linha = [x for x in capsys.readouterr().out.splitlines() if x.strip().startswith("5")]
    assert linha and linha[0].strip().endswith("-")
