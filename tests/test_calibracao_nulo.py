"""Calibração da cadeia inteira sob um nulo verdadeiro.

Com as DUAS classes aleatórias não existe nada a achar. Se o pipeline
(ajuste → bolsas → p-valor do IC → BH-FDR → faixa de controle →
monotonicidade) apontar qualquer piso aqui, ele fabrica sinal, e todo piso
medido fica sob suspeita.

A versão de verdade desta checagem rodou em escala real (300 chaves, 6
contagens, 3 modelos, 3 bolsas = 54 testes, vetor de 640 bits) e deu zero
detecções. Aqui fica uma versão enxuta — vetor estreito e poucas contagens —
só para o nulo continuar sendo verificado a cada suíte.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from scripts.reduced_rounds.report_floor import carregar, marcar, pisos
from scripts.reduced_rounds.run_gift_floor import PAIRS_PER_KEY, run_config

LARGURA = 20        # bytes por amostra; 160 bits bastam para o nulo


def test_duas_classes_aleatorias_nao_produzem_piso(tmp_path, capsys) -> None:
    n_keys, n_test = 12, 10        # >= 10 clusters: abaixo disso o IC não
    rodadas = [1, 2]               # significa nada e o nulo dá falso positivo
    n = n_keys * PAIRS_PER_KEY
    rng = np.random.default_rng(31337)

    dados = {"key_idx": np.repeat(np.arange(n_keys), PAIRS_PER_KEY).astype(np.int32),
             "random": rng.integers(0, 256, (n, LARGURA), dtype=np.uint8)}
    for r in rodadas:               # cada "rodada" também é ruído puro
        dados[f"r{r}"] = rng.integers(0, 256, (n, LARGURA), dtype=np.uint8)

    saida = Path(tmp_path)
    for r in rodadas:
        run_config("texto", r, dados, n_keys, n_test, 2, saida, "sweep",
                   ["RandomForest"])
    capsys.readouterr()             # descarta o log da geração

    df = marcar(carregar(saida), null_min=2, q=0.05)
    assert not df.empty
    assert not df["detectado"].any(), \
        df[df["detectado"]][["rounds", "modelo", "bolsa", "f1_macro"]].to_dict("records")

    pisos(df)
    assert "NENHUM piso monotônico" in capsys.readouterr().out


def test_o_teste_acima_detectaria_sinal_se_houvesse(tmp_path, capsys) -> None:
    """Contraprova: sem isto, um pipeline que nunca detecta nada passaria."""
    n_keys, n_test = 12, 10
    n = n_keys * PAIRS_PER_KEY
    rng = np.random.default_rng(31337)
    dados = {"key_idx": np.repeat(np.arange(n_keys), PAIRS_PER_KEY).astype(np.int32),
             "random": rng.integers(0, 256, (n, LARGURA), dtype=np.uint8),
             "r1": rng.integers(0, 256, (n, LARGURA), dtype=np.uint8),
             "r4": rng.integers(0, 256, (n, LARGURA), dtype=np.uint8)}
    dados["r1"][:, :4] = 0          # sinal grosseiro só na contagem baixa

    saida = Path(tmp_path)
    for r in (1, 4):
        run_config("texto", r, dados, n_keys, n_test, 2, saida, "sweep",
                   ["RandomForest"])
    capsys.readouterr()

    df = marcar(carregar(saida), null_min=4, q=0.05)
    assert bool(df[df["rounds"] == 1]["detectado"].any())
    assert not bool(df[df["rounds"] == 4]["detectado"].any())
