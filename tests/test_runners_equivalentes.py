"""Os dois runners de piso precisam ser intercambiáveis.

`run_gift_floor.py` mede o GIFT (Python puro, granularidade de uma rodada) e
`run_floor.py` mede os quatro (variantes compiladas). Os números dos dois
aparecem lado a lado na dissertação — se as funções divergirem em split,
diagnóstico, ajuste ou agregação, os pisos deixam de ser comparáveis entre
algoritmos sem que nada acuse.

Só o que é metadado pode diferir: `run_id`, `braco`, nomes de classe,
prefixo dos `sample_ids` e os campos de `extra`.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

import scripts.reduced_rounds.run_floor as novo
import scripts.reduced_rounds.run_gift_floor as antigo


def _dados(n_keys: int = 6):
    ppk = antigo.PAIRS_PER_KEY
    n = n_keys * ppk
    rng = np.random.default_rng(7)
    d = {
        "key_idx": np.repeat(np.arange(n_keys), ppk).astype(np.int32),
        "random": rng.integers(0, 256, (n, 80), dtype=np.uint8),
        "r3": rng.integers(0, 256, (n, 80), dtype=np.uint8),
    }
    d["r3"][:, 0] &= 0xF0     # viés proposital: sem sinal o teste não discrimina
    return d, n_keys


def _f1_por_modelo(d: Path) -> dict:
    out = {}
    for f in d.glob("*_metrics.jsonl"):
        for linha in f.read_text(encoding="utf-8").splitlines():
            if linha.strip():
                r = json.loads(linha)
                out[(r["modelo"], str(r["fold"]))] = round(r["f1_macro"], 10)
    return out


def test_os_dois_runners_dao_o_mesmo_f1_para_os_mesmos_dados(tmp_path) -> None:
    dados, n_keys = _dados()
    modelos = ["RandomForest"]
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()

    antigo.run_config("texto", 3, dados, n_keys, 2, 3, a, "sweep", modelos)
    novo.run_config("gift", "texto", 3, dados, n_keys, 2, 3, b, "sweep",
                    modelos, "ambos")

    ma, mb = _f1_por_modelo(a), _f1_por_modelo(b)
    assert ma and set(ma) == set(mb)
    assert ma == mb, {k: (ma[k], mb[k]) for k in ma if ma[k] != mb[k]}
