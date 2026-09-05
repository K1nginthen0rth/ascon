"""Testes de `src/features/families/tag_region.py` — não existiam antes
da 8a auditoria (2026-08-28), que achou o bug de `payload_rest` justamente
por FALTA de um teste que verificasse "nenhum byte de tag sobra no
payload_rest" para um algoritmo com ABYTES=16.
"""
from __future__ import annotations

from src.features.families.tag_region import (
    _MAX_ABYTES,
    _MIN_RAW_LEN,
    _PAYLOAD_REST_LEN,
    extract_tag_region,
    extract_tag_region_full,
)

_PAYLOAD_BYTE = 0x00
_TAG_BYTE = 0xFF


def _ct_sintetico(payload_len: int, abytes: int) -> bytes:
    """CT sintético com payload e tag claramente distinguíveis por byte,
    para poder afirmar 'nenhum byte de tag vazou' de forma direta."""
    return bytes([_PAYLOAD_BYTE]) * payload_len + bytes([_TAG_BYTE]) * abytes


def test_payload_rest_len_e_fixo_e_documentado() -> None:
    assert _PAYLOAD_REST_LEN == _MIN_RAW_LEN - _MAX_ABYTES
    assert _PAYLOAD_REST_LEN == 65528


def test_payload_rest_nao_vaza_tag_abytes_16() -> None:
    """Regressão do bug de 2026-08-28: com `payload_rest = ct[:-8]`, um
    algoritmo com ABYTES=16 (Ascon/GIFT-COFB/Schwaemm) sobrava com 8 bytes
    REAIS de tag disfarçados de payload. Com o comprimento fixo
    `_PAYLOAD_REST_LEN`, nenhum byte de tag deve aparecer."""
    ct = _ct_sintetico(payload_len=65536, abytes=16)  # total 65552, como Ascon
    resultado = extract_tag_region(ct)
    assert resultado["payload_rest_nunique"] == 1  # só um valor de byte: o payload
    assert resultado["payload_rest_max_freq"] == 1.0  # 100% do mesmo byte


def test_payload_rest_nao_vaza_tag_abytes_8() -> None:
    """Mesmo teste para ABYTES=8 (Grain) — já funcionava antes, continua
    funcionando depois (não é regressão, é conferência)."""
    ct = _ct_sintetico(payload_len=65536, abytes=8)  # total 65544, como Grain
    resultado = extract_tag_region(ct)
    assert resultado["payload_rest_nunique"] == 1
    assert resultado["payload_rest_max_freq"] == 1.0


def test_payload_rest_mesmo_comprimento_para_abytes_8_e_16() -> None:
    """O comprimento do payload_rest não pode depender de ABYTES — senão
    reintroduz o próprio comprimento como discriminador (Regra de Ouro 5),
    só que escondido dentro de uma feature em vez de aparecer como
    `len_ct`."""
    ct_8 = _ct_sintetico(payload_len=65536, abytes=8)
    ct_16 = _ct_sintetico(payload_len=65536, abytes=16)
    # ambos tem que produzir o MESMO numero de bytes de payload_rest —
    # aqui verificado indiretamente via chi2 (que so depende do
    # comprimento da janela quando o conteudo e uniforme por construcao)
    r8 = extract_tag_region(ct_8)
    r16 = extract_tag_region(ct_16)
    assert r8["payload_rest_entropy"] == r16["payload_rest_entropy"] == 0.0
    assert r8["payload_rest_chi2_statistic"] == r16["payload_rest_chi2_statistic"]


def test_tag8_continua_pegando_a_janela_comum_de_8_bytes() -> None:
    """`tag8` não muda com esta correção — continua sendo os últimos 8
    bytes do CT cru, igual para os dois ABYTES."""
    ct_16 = _ct_sintetico(payload_len=65536, abytes=16)
    resultado = extract_tag_region(ct_16)
    assert resultado["tag8_nunique"] == 1
    assert resultado["tag8_max_freq"] == 1.0


def test_ct_curto_demais_retorna_nan() -> None:
    resultado = extract_tag_region(b"\x00" * 10)  # menor que _PAYLOAD_REST_LEN
    assert all(v != v for v in resultado.values())  # NaN != NaN


def test_extract_tag_region_full_usa_abytes_explicito() -> None:
    """Função exploratória (não chamada por nenhum script de produção
    hoje) — continua correta, usando o abytes real, sem janela fixa."""
    ct = _ct_sintetico(payload_len=100, abytes=16)
    resultado = extract_tag_region_full(ct, abytes=16)
    assert resultado["tag_full_nunique"] == 1
    assert resultado["payload_full_nunique"] == 1


def test_extract_tag_region_full_rejeita_abytes_invalido() -> None:
    try:
        extract_tag_region_full(b"\x00" * 100, abytes=0)
        assert False, "deveria ter levantado ValueError"
    except ValueError:
        pass
