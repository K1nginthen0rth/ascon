"""Testes da variante de inicialização reduzida do Grain-128AEAD.

O Grain era a maior lacuna do estudo de fronteira: não existe distinguidor
neural publicado para ele, e nenhuma variante reduzida existia neste repo.

Três coisas precisam valer para a variante servir como instrumento:

 1. **O patch é inerte.** Com `GRAIN_INIT_ROUNDS_OVERRIDE=256` (o default da
    especificação) a variante tem que reproduzir os 1.089 KATs oficiais. É o
    mesmo critério de aceite usado nos patches de Ascon, GIFT e Schwaemm.
 2. **A redução muda o que tem que mudar.** Cada contagem de clocks produz um
    criptograma distinto, e nenhuma delas coincide com a de 256.
 3. **O modo continua intacto.** A fase ADDKEY (128 clocks que constroem a
    tag) não é parametrizada de propósito, então o criptograma continua sendo
    payload + 8 bytes de tag e o decrypt continua fechando o ciclo. Se isso
    quebrasse, a comparação deixaria de ser "mesmo AEAD com menos rodadas".

Os `.pyd` são compilados sob demanda; num ambiente sem MSVC os testes são
pulados em vez de falharem.
"""
from __future__ import annotations

import random

import pytest

from scripts.reduced_rounds.reduced_wrapper import ALGO_SPECS, ReducedRoundsCipher

KEY = bytes(range(16))
NONCE = bytes(range(16, 28))  # Grain usa nonce de 12 bytes
PT = bytes(range(64))
SPEC_INIT_ROUNDS = 256


def _cipher(init_rounds: int) -> ReducedRoundsCipher:
    """Compila (ou reaproveita) a variante e devolve o cifrador."""
    from scripts.reduced_rounds.build_variant import build_grain

    try:
        pyd = build_grain(init_rounds)
    except Exception as e:  # noqa: BLE001 - ambiente sem compilador
        pytest.skip(f"variante init={init_rounds} indisponível: {e}")
    return ReducedRoundsCipher(pyd, "grain")


def test_spec_do_grain_tem_nonce_e_tag_menores() -> None:
    """Grain foge do padrão dos outros três: nonce 96 bits, tag 64 bits."""
    assert ALGO_SPECS["grain"] == (16, 12, 8)


def test_baseline_reproduz_os_kats_oficiais() -> None:
    """Critério de aceite do patch: sem override, saída idêntica à de produção."""
    from pathlib import Path

    from src.crypto.kat_parser import parse_kat_file

    repo_root = Path(__file__).resolve().parent.parent
    kat = repo_root / "data" / "kat" / "LWC_AEAD_KAT_GRAIN128AEAD.txt"
    cipher = _cipher(SPEC_INIT_ROUNDS)
    vetores = parse_kat_file(kat)
    assert len(vetores) == 1089
    ruins = [v.count for v in vetores
             if cipher.encrypt(v.key, v.nonce, v.pt, v.ad) != v.ct]
    assert not ruins, f"KATs divergentes: {ruins[:10]}"


def test_baseline_bate_com_o_wrapper_de_producao() -> None:
    """Segunda âncora: mesmo byte que o `.pyd` de produção, fora dos KATs."""
    from src.crypto.grain_wrapper import Grain128AEAD

    cipher = _cipher(SPEC_INIT_ROUNDS)
    rng = random.Random(20260919)
    producao = Grain128AEAD()
    for _ in range(50):
        key = bytes(rng.getrandbits(8) for _ in range(16))
        nonce = bytes(rng.getrandbits(8) for _ in range(12))
        pt = bytes(rng.getrandbits(8) for _ in range(rng.choice([0, 1, 15, 17, 64, 300])))
        ad = bytes(rng.getrandbits(8) for _ in range(rng.choice([0, 1, 20])))
        assert cipher.encrypt(key, nonce, pt, ad) == producao.encrypt(key, nonce, pt, ad)


@pytest.mark.parametrize("init_rounds", [32, 64, 96, 128, 160, 192, 224, 240])
def test_inicializacao_reduzida_muda_o_criptograma(init_rounds: int) -> None:
    assert (_cipher(init_rounds).encrypt(KEY, NONCE, PT)
            != _cipher(SPEC_INIT_ROUNDS).encrypt(KEY, NONCE, PT))


def test_cada_contagem_de_clocks_da_um_criptograma_distinto() -> None:
    contagens = [32, 64, 96, 112, 128, 144, 160, 176, 192, 208, 224, 240, 256]
    saidas = {r: _cipher(r).encrypt(KEY, NONCE, PT) for r in contagens}
    assert len(set(saidas.values())) == len(saidas)


@pytest.mark.parametrize("init_rounds", [32, 128, 240])
def test_modo_aead_continua_intacto_na_variante_reduzida(init_rounds: int) -> None:
    """A fase ADDKEY não foi tocada: tag de 8 bytes e roundtrip fechando."""
    cipher = _cipher(init_rounds)
    rng = random.Random(init_rounds)
    for n_pt in (0, 1, 15, 16, 17, 64, 300):
        pt = bytes(rng.getrandbits(8) for _ in range(n_pt))
        ct = cipher.encrypt(KEY, NONCE, pt)
        assert len(ct) == n_pt + 8
        assert cipher.decrypt(KEY, NONCE, ct) == pt


def test_tag_rejeita_criptograma_adulterado() -> None:
    """Autenticação viva mesmo com 32 clocks — confirma que o modo sobreviveu."""
    cipher = _cipher(32)
    ct = bytearray(cipher.encrypt(KEY, NONCE, PT))
    ct[0] ^= 0x01
    with pytest.raises(RuntimeError):
        cipher.decrypt(KEY, NONCE, bytes(ct))


def test_rejeita_contagem_de_clocks_invalida() -> None:
    from scripts.reduced_rounds.build_variant import build_grain

    for r in (0, -1, 257, 1000):
        with pytest.raises(ValueError):
            build_grain(r)
