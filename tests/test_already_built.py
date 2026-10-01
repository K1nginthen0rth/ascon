"""Testes do cache de artefatos compilados (`build_variant._already_built`).

O objetivo da função é pular o link quando o `.pyd` já existe — o link.exe do
MSVC falha com LNK1104 se qualquer processo ainda tiver o arquivo carregado, e
isso já derrubou uma execução longa no meio.

O problema: ela casava por glob no NOME DO MÓDULO, sem olhar a ABI. Um `.pyd`
compilado por outra versão de Python (`cp311` num ambiente `cp314`) contava
como "já pronto", a recompilação era pulada, e o erro só aparecia depois, no
import, como `DLL load failed` — sem nada indicando que a causa era artefato
velho. Como estes artefatos ficam em cache indefinidamente, bastava subir o
interpretador para o estudo inteiro parar de funcionar com um erro opaco.
"""
from __future__ import annotations

import sysconfig

import pytest

import scripts.reduced_rounds.build_variant as bv

SUFIXO = sysconfig.get_config_var("EXT_SUFFIX") or ".pyd"


@pytest.fixture()
def raiz(tmp_path, monkeypatch):
    monkeypatch.setattr(bv, "OUT_ROOT", tmp_path)
    return tmp_path


def _criar(raiz, modulo: str, nome_arquivo: str):
    d = raiz / modulo
    d.mkdir(parents=True, exist_ok=True)
    (d / nome_arquivo).write_bytes(b"conteudo irrelevante")


def test_encontra_o_artefato_da_abi_atual(raiz) -> None:
    _criar(raiz, "_m", f"_m{SUFIXO}")
    achado = bv._already_built("_m")
    assert achado is not None and achado.name == f"_m{SUFIXO}"


def test_ignora_artefato_de_outra_abi(raiz, capsys) -> None:
    _criar(raiz, "_m", "_m.cp311-win_amd64.pyd")
    assert bv._already_built("_m") is None
    assert "outra ABI" in capsys.readouterr().out


def test_prefere_a_abi_atual_quando_convivem(raiz) -> None:
    _criar(raiz, "_m", "_m.cp311-win_amd64.pyd")
    _criar(raiz, "_m", f"_m{SUFIXO}")
    achado = bv._already_built("_m")
    assert achado is not None and achado.name == f"_m{SUFIXO}"


def test_diretorio_ausente_nao_quebra(raiz) -> None:
    assert bv._already_built("_nunca_compilado") is None


def test_nao_confunde_modulos_de_prefixo_parecido(raiz) -> None:
    """`_grain_ref_init2` não pode casar com o diretório de `_grain_ref_init256`."""
    _criar(raiz, "_grain_ref_init256", f"_grain_ref_init256{SUFIXO}")
    assert bv._already_built("_grain_ref_init2") is None
    assert bv._already_built("_grain_ref_init256") is not None


def test_as_variantes_reais_continuam_sendo_reconhecidas() -> None:
    """Sem `raiz`: usa o OUT_ROOT de verdade. Se isto falhar, a correção da
    ABI passou a rejeitar os artefatos que já estão no disco."""
    for modulo in ("_grain_ref_init256", "_gift_cofb_ref_r40",
                   "_ascon_ref_pa12_pb8", "_sparkle_ref_slim7_big11"):
        if not (bv.OUT_ROOT / modulo).is_dir():
            pytest.skip(f"{modulo} não compilado neste ambiente")
        assert bv._already_built(modulo) is not None, modulo
