"""Testes do critério de piso (`scripts/reduced_rounds/report_floor.py`).

Este é o script de onde sai o número que vai para a dissertação, então o que
importa testar não é formatação: é que ele não invente detecção onde não há, e
não perca detecção onde há. Os dois modos de errar já aconteceram de verdade
durante o desenvolvimento e estão cobertos aqui:

 1. **Falso positivo por múltiplas comparações.** Com o critério ingênuo (IC
    inferior acima de 0,50), a cifra COMPLETA aparecia como detectada. Numa
    varredura são centenas de testes e alguns passam por acaso.
 2. **Separação perfeita virando "sem evidência".** Com F1 = 1,000 o IC tem
    largura zero, o erro padrão vira zero e o p-valor fica indefinido. Se isso
    conta como não detectado, o piso é subestimado exatamente nas rodadas mais
    fracas, que são as que mais separam.

O `marcar()` é testado direto sobre DataFrames montados à mão, sem depender de
nenhuma execução real.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scripts.reduced_rounds.report_floor import CHANCE, marcar


def _linha(rounds: int, f1: float, meia_largura: float = 0.02, *,
           modelo: str = "RandomForest", bolsa: int = 1, algo: str = "gift",
           arm: str = "texto", politica: str = "ambos") -> dict:
    return dict(algo=algo, arm=arm, politica=politica, rounds=rounds,
                modelo=modelo, bolsa=bolsa,
                f1_macro=f1, f1_ci_lo=f1 - meia_largura, f1_ci_hi=f1 + meia_largura,
                rounds_spec=40, unidade="rodadas")


def _df(linhas: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(linhas)


def test_cifra_completa_no_acaso_nao_e_detectada() -> None:
    """O controle negativo. Se isto falhar, todo piso medido é suspeito."""
    df = marcar(_df([_linha(r, 0.501) for r in (1, 20, 25, 30, 35, 40)]),
                null_min=20, q=0.05)
    assert not df["detectado"].any()


def test_separacao_perfeita_conta_como_detectada() -> None:
    """IC de largura zero acima do acaso é a evidência máxima, não a ausência."""
    linhas = [_linha(1, 1.0, meia_largura=0.0)]
    linhas += [_linha(r, 0.502) for r in (20, 30, 40)]
    df = marcar(_df(linhas), null_min=20, q=0.05)
    assert bool(df[df["rounds"] == 1]["detectado"].iloc[0])
    assert df[df["rounds"] >= 20]["detectado"].sum() == 0


def test_separacao_perfeita_abaixo_do_acaso_nao_e_detectada() -> None:
    """F1 = 0 também tem IC degenerado, e não é evidência de nada."""
    linhas = [_linha(1, 0.0, meia_largura=0.0)]
    linhas += [_linha(r, 0.50) for r in (20, 40)]
    df = marcar(_df(linhas), null_min=20, q=0.05)
    assert not df["detectado"].any()


def test_desempenho_abaixo_do_acaso_nunca_e_detectado() -> None:
    """Critério unilateral: só interessa acima de 0,50."""
    linhas = [_linha(1, 0.40, meia_largura=0.01)]
    linhas += [_linha(r, 0.50) for r in (20, 40)]
    df = marcar(_df(linhas), null_min=20, q=0.05)
    assert not df["detectado"].any()
    assert df[df["rounds"] == 1]["p_value"].iloc[0] == 1.0


def test_faixa_de_controle_barra_ruido_que_passa_pelo_fdr() -> None:
    """A segunda barreira: não basta ser significativo contra o 0,50 teórico.

    Uma rodada baixa com F1 ligeiramente acima do acaso, mas ABAIXO do que o
    próprio pipeline produz na cifra completa, não é sinal — é ruído do
    pipeline, e a faixa de controle é quem sabe disso.
    """
    linhas = [_linha(5, 0.56, meia_largura=0.005)]           # "significativo"
    linhas += [_linha(r, 0.58, meia_largura=0.005) for r in (20, 30, 40)]  # controle mais alto
    df = marcar(_df(linhas), null_min=20, q=0.05)
    r5 = df[df["rounds"] == 5].iloc[0]
    assert bool(r5["significativo_fdr"]), "deveria passar no FDR isoladamente"
    assert not bool(r5["detectado"]), "mas a faixa de controle tem que barrar"


def test_sem_faixa_de_controle_a_deteccao_cai_so_no_fdr() -> None:
    """Sem rodadas altas nos dados, o teto é NaN e não deve zerar tudo."""
    df = marcar(_df([_linha(1, 0.95, meia_largura=0.01),
                     _linha(2, 0.501, meia_largura=0.02)]), null_min=20, q=0.05)
    assert df["teto_controle"].isna().all()
    assert bool(df[df["rounds"] == 1]["detectado"].iloc[0])
    assert not bool(df[df["rounds"] == 2]["detectado"].iloc[0])


def test_teto_de_controle_e_por_modelo_e_por_bolsa() -> None:
    """Modelos e tamanhos de bolsa têm níveis de ruído diferentes."""
    linhas = []
    for modelo, teto in (("RandomForest", 0.58), ("XGBoost", 0.52)):
        linhas.append(_linha(5, 0.55, meia_largura=0.005, modelo=modelo))
        linhas += [_linha(r, teto, meia_largura=0.005, modelo=modelo) for r in (20, 40)]
    df = marcar(_df(linhas), null_min=20, q=0.05)
    r5 = df[df["rounds"] == 5].set_index("modelo")
    assert not bool(r5.loc["RandomForest", "detectado"])  # teto 0,58 > 0,55
    assert bool(r5.loc["XGBoost", "detectado"])           # teto 0,52 < 0,55


def test_fdr_e_mais_severo_que_o_teste_isolado() -> None:
    """Muitas configurações no acaso empurram o limiar do BH para baixo."""
    marginal = _linha(1, 0.5101, meia_largura=0.01)
    sozinho = marcar(_df([marginal]), null_min=99, q=0.05)
    acompanhado = marcar(_df([marginal] + [_linha(r, 0.5001, meia_largura=0.01)
                                           for r in range(2, 40)]),
                         null_min=99, q=0.05)
    assert bool(sozinho["significativo_fdr"].iloc[0])
    assert not bool(acompanhado[acompanhado["rounds"] == 1]["significativo_fdr"].iloc[0])


@pytest.mark.parametrize("f1,esperado_significativo", [
    (0.500, False),
    (0.505, False),
    (0.700, True),
    (0.990, True),
])
def test_p_valor_acompanha_a_distancia_do_acaso(f1: float, esperado_significativo: bool) -> None:
    df = marcar(_df([_linha(1, f1, meia_largura=0.02)]), null_min=99, q=0.05)
    assert bool(df["significativo_fdr"].iloc[0]) is esperado_significativo
    assert 0.0 <= df["p_value"].iloc[0] <= 1.0
    assert not np.isnan(df["p_value"].iloc[0])


def test_chance_e_meio() -> None:
    """Duas classes balanceadas; se isto mudar, todo o critério muda."""
    assert CHANCE == 0.50


# --- regra de monotonicidade na manchete -----------------------------------
# Um piso real não pode pular as rodadas MAIS fracas. Se a detecção aparece em
# R mas some em R-1, é ruído de múltiplas comparações. Sem esta regra, uma
# única célula espúria definia o número da tese: no braço de plaintext
# uniforme do Grain, 3 de 9 células marcaram algo e as 3 tinham buraco embaixo.

def _relatorio(linhas: list[dict], null_min: int, capsys) -> str:
    from scripts.reduced_rounds.report_floor import pisos

    df = marcar(_df(linhas), null_min=null_min, q=0.05)
    pisos(df)
    return capsys.readouterr().out


def test_deteccao_com_buraco_abaixo_nao_vira_manchete(capsys) -> None:
    linhas = [_linha(r, 0.501) for r in (1, 2, 3, 4)]        # nada aqui
    linhas.append(_linha(5, 0.62, meia_largura=0.01))         # só aqui: suspeito
    linhas += [_linha(r, 0.502) for r in (20, 30, 40)]
    saida = _relatorio(linhas, null_min=20, capsys=capsys)
    assert "NENHUM piso monotônico" in saida
    assert "buraco abaixo" in saida


def test_deteccao_monotonica_vira_manchete_com_contagem_de_apoio(capsys) -> None:
    linhas = [_linha(r, f1, meia_largura=0.01) for r, f1 in ((1, 0.95), (2, 0.80), (3, 0.62))]
    linhas += [_linha(r, 0.501) for r in (4, 5, 6)]
    linhas += [_linha(r, 0.502) for r in (20, 30, 40)]
    saida = _relatorio(linhas, null_min=20, capsys=capsys)
    assert "com até 3 rodadas" in saida
    assert "1 de 1 células" in saida       # só um (modelo, bolsa) neste cenário
    assert "0 descartada" in saida


def test_arm_sem_nenhuma_deteccao_diz_isso_explicitamente(capsys) -> None:
    linhas = [_linha(r, 0.501) for r in (1, 2, 3, 20, 40)]
    saida = _relatorio(linhas, null_min=20, capsys=capsys)
    assert "NENHUM piso monotônico" in saida
    assert "buraco abaixo" not in saida    # não houve célula espúria a descartar


# --- bugs achados na revisão de 20/09 --------------------------------------

def test_ic_ausente_nao_vira_deteccao() -> None:
    """IC ausente != IC de largura zero.

    Confundir os dois fabricava detecção: sem IC, `se` virava NaN, caía no
    ramo "separação perfeita" e recebia p=0. Uma linha de jsonl sem IC
    bastava para inventar um piso.
    """
    linha = _linha(1, 0.95)
    linha["f1_ci_lo"] = None
    linha["f1_ci_hi"] = None
    df = marcar(_df([linha] + [_linha(r, 0.501) for r in (20, 40)]), null_min=20, q=0.05)
    r1 = df[df["rounds"] == 1].iloc[0]
    assert np.isnan(r1["p_value"])
    assert not bool(r1["detectado"])


def test_null_min_padrao_e_metade_da_spec_de_cada_algoritmo() -> None:
    """Limiar fixo quebrava o Grain: 20 é controle no GIFT (spec 40) e região
    de sinal no Grain (spec 256)."""
    from scripts.reduced_rounds.report_floor import null_min_por_algo

    linhas = [_linha(1, 0.6, algo="gift")]
    linhas += [dict(_linha(1, 0.6, algo="grain"), rounds_spec=256)]
    nm = null_min_por_algo(_df(linhas), None)
    assert nm == {("gift", "ambos"): 20, ("grain", "ambos"): 128}
    assert null_min_por_algo(_df(linhas), 33) == {("gift", "ambos"): 33,
                                                 ("grain", "ambos"): 33}


def test_os_dois_eixos_do_ascon_nao_se_misturam() -> None:
    """Ascon tem dois parametros de rodada e os dois eixos usam a MESMA
    numeracao: r=4 com `pa=4,pb=4` e r=4 com `pa=12,pb=4` sao cifradores
    diferentes. Se `politica` nao entrar na chave, o teto de controle de um
    eixo calibra o outro e o piso sai errado.
    """
    from scripts.reduced_rounds.report_floor import null_min_por_algo

    linhas = [dict(_linha(r, 0.502, algo="ascon"), rounds_spec=12) for r in (1, 6, 12)]
    linhas += [dict(_linha(r, 0.502, algo="ascon", politica="dados"), rounds_spec=8)
               for r in (1, 4, 8)]
    nm = null_min_por_algo(_df(linhas), None)
    assert nm == {("ascon", "ambos"): 6, ("ascon", "dados"): 4}

    df = marcar(_df(linhas), null_min=None, q=0.05)
    assert set(df[df["politica"] == "ambos"]["null_min"]) == {6}
    assert set(df[df["politica"] == "dados"]["null_min"]) == {4}


def test_quadro_sem_coluna_politica_continua_lido() -> None:
    """`run_gift_floor.py` e anterior as duas politicas e nao grava o campo.
    Um quadro sem a coluna tem que ser lido como o unico eixo que ele tem, nao
    morrer em KeyError."""
    linhas = [_linha(r, 0.502) for r in (1, 20, 40)]
    for l in linhas:
        del l["politica"]
    df = marcar(_df(linhas), null_min=20, q=0.05)
    assert set(df["politica"]) == {"ambos"}
    assert not df["detectado"].any()


def test_faixa_de_controle_e_por_algoritmo_e_nao_global() -> None:
    """Com dois algoritmos na mesma pasta, um limiar só produziria teto errado."""
    linhas = [_linha(r, 0.502, algo="gift") for r in (1, 20, 40)]
    linhas += [dict(_linha(r, 0.502, algo="grain"), rounds_spec=256)
               for r in (1, 128, 256)]
    df = marcar(_df(linhas), null_min=None, q=0.05)
    assert set(df[df["algo"] == "gift"]["null_min"]) == {20}
    assert set(df[df["algo"] == "grain"]["null_min"]) == {128}
    # a rodada 20 do grain NÃO pode entrar na faixa de controle dele
    grain_r1 = df[(df["algo"] == "grain") & (df["rounds"] == 1)].iloc[0]
    assert grain_r1["rounds"] < grain_r1["null_min"]


def test_contagem_de_apoio_usa_o_numero_real_de_celulas(capsys) -> None:
    """Estava fixo em 9; qualquer varredura com outro nº de modelos mentiria."""
    linhas = []
    for modelo in ("RandomForest", "XGBoost"):
        linhas.append(_linha(1, 0.95, meia_largura=0.01, modelo=modelo))
        linhas += [_linha(r, 0.501, modelo=modelo) for r in (20, 40)]
    saida = _relatorio(linhas, null_min=20, capsys=capsys)
    assert "2 de 2 células" in saida


def test_avisa_quando_a_pasta_mistura_execucoes(tmp_path, capsys) -> None:
    """`run_gift_floor` e `run_floor` gravam no MESMO diretório para o GIFT,
    com seeds de geração diferentes. Sem aviso, o drop_duplicates escolheria
    uma das duas em silêncio e o piso sairia de dados misturados."""
    import json

    from scripts.reduced_rounds.report_floor import carregar

    linhas = []
    for runner, seed in (("run_gift_floor", 999003), ("run_floor", 999004)):
        linhas.append(dict(
            run_id=f"x_{runner}", modelo="RandomForest", fold="final",
            f1_macro=0.6, f1_macro_ci_lower=0.58, f1_macro_ci_upper=0.62,
            timestamp=f"2026-09-20T00:00:0{seed % 10}",
            extra=dict(rounds=3, arm="texto", algo="gift", rounds_spec=40,
                       runner=runner, seed_gen_runner=seed)))
    (tmp_path / "x_metrics.jsonl").write_text(
        "\n".join(json.dumps(x) for x in linhas), encoding="utf-8")

    df = carregar(tmp_path)
    saida = capsys.readouterr().out
    assert "mistura execuções distintas" in saida
    assert len(df) == 1   # o drop_duplicates continua colapsando — daí o aviso


def test_marcar_aceita_quadro_vazio() -> None:
    """`main()` barra antes, mas a função é reusada; antes saía KeyError."""
    assert marcar(pd.DataFrame(), null_min=None, q=0.05).empty
