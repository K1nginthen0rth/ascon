"""Testes do carimbo de parâmetros do cache de geração (`conferir_cache`).

Os runners de piso guardam as amostras num `.npz` e reaproveitam entre
execuções. O nome do arquivo só carrega algoritmo, braço e número de chaves —
então, sem carimbo, um cache gerado com outro `MSG_BYTES`, outra largura de
tag ou outra seed voltava em silêncio e contaminava o resultado. O risco não é
hipotético neste estudo: `MSG_BYTES` passou de 65536 para 64 no meio dele.

Pior ainda era o caminho de CACHE CHEIO, que retornava antes de qualquer
checagem: pedir 10 chaves num arquivo de 300 devolvia as 300 sem reclamar, e o
erro só aparecia depois, como desalinhamento de shape no numpy.

Caches anteriores ao carimbo continuam válidos (os dados reais do estudo são
desses), com a checagem de forma que ainda pega o erro mais comum.
"""
from __future__ import annotations

import json

import numpy as np
import pytest

from scripts.reduced_rounds.run_gift_floor import (
    _FP, PAIRS_PER_KEY, conferir_cache, impressao_digital,
)


def _store(n_keys: int, fp: np.ndarray | None) -> dict:
    s = {"key_idx": np.repeat(np.arange(n_keys), PAIRS_PER_KEY).astype(np.int32)}
    if fp is not None:
        s[_FP] = fp
    return s


def _fp(**over) -> np.ndarray:
    base = dict(algo="grain", arm="texto", n_keys=10, pairs_per_key=PAIRS_PER_KEY,
                msg_bytes=64, tag_bytes=8, seed_gen=999004)
    base.update(over)
    return impressao_digital(**base)


def test_carimbo_igual_passa(tmp_path) -> None:
    conferir_cache(_store(10, _fp()), _fp(), tmp_path / "c.npz")


@pytest.mark.parametrize("campo,valor", [
    ("msg_bytes", 128),      # a mudança que de fato aconteceu no estudo
    ("tag_bytes", 16),
    ("seed_gen", 999003),
    ("arm", "aleatorio"),
    ("algo", "gift"),
    ("pairs_per_key", 50),
])
def test_qualquer_parametro_diferente_recusa(campo: str, valor, tmp_path) -> None:
    with pytest.raises(ValueError, match="outros parâmetros"):
        conferir_cache(_store(10, _fp()), _fp(**{campo: valor}), tmp_path / "c.npz")


def test_numero_de_chaves_diferente_recusa_no_caminho_de_cache_cheio(tmp_path) -> None:
    """O bug original: pedir 10 chaves num arquivo de 300 era aceito."""
    with pytest.raises(ValueError, match="linhas"):
        conferir_cache(_store(300, None), _fp(n_keys=10), tmp_path / "c.npz")


def test_cache_legado_sem_carimbo_passa_com_aviso(tmp_path, capsys) -> None:
    """Os dados reais do estudo são anteriores ao carimbo e não podem quebrar."""
    conferir_cache(_store(10, None), _fp(), tmp_path / "legado.npz")
    assert "anterior ao carimbo" in capsys.readouterr().out


def test_carimbo_correto_mas_arquivo_truncado_recusa(tmp_path) -> None:
    s = _store(10, _fp())
    s["key_idx"] = s["key_idx"][:-1]      # corrompido
    with pytest.raises(ValueError, match="corrompido"):
        conferir_cache(s, _fp(), tmp_path / "c.npz")


def test_carimbo_independe_da_ordem_das_chaves() -> None:
    """`sort_keys=True`: a mesma configuração dá sempre o mesmo carimbo."""
    a = impressao_digital(b=2, a=1)
    b = impressao_digital(a=1, b=2)
    assert str(a) == str(b)
    assert json.loads(str(a)) == {"a": 1, "b": 2}
