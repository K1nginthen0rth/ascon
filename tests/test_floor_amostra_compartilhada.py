"""A amostra do estudo de piso tem que ser a mesma para todos os algoritmos.

Na v1 os rótulos do DRBG levavam o nome do algoritmo (chaves e textos
diferentes por algoritmo) e o nonce era um contador global amarrado à chave.
Estes testes travam a v2: mesma chave, mesmo texto e mesmo offset de nonce na
mesma posição da amostra, e o par (n, n+1) diferindo em exatamente 1 bit.
Usam um cifrador falso que só registra o que recebeu, sem compilar nada.
"""
from __future__ import annotations

from typing import NamedTuple

import scripts.reduced_rounds.run_floor as rf


class _Gravador:
    def __init__(self, tag_bytes: int, log: list) -> None:
        self.tag_bytes, self.log = tag_bytes, log

    def encrypt(self, key: bytes, nonce: bytes, pt: bytes) -> bytes:
        self.log.append((key, nonce, pt))
        return bytes(len(pt) + self.tag_bytes)


class _SpecFalsa(NamedTuple):
    key_bytes: int
    nonce_bytes: int
    tag_bytes: int
    log: list
    rotulo: str = "falso"
    unidade: str = "rodadas"
    max_rounds: int = 12

    def cipher(self, rounds: int, politica: str = "ambos"):
        return _Gravador(self.tag_bytes, self.log)


def _gera(monkeypatch, tmp_path, nome: str, nonce_bytes: int, tag_bytes: int) -> list:
    log: list = []
    monkeypatch.setitem(rf.ALGOS, nome, _SpecFalsa(16, nonce_bytes, tag_bytes, log))
    rf.generate(nome, "aleatorio", 2, [1], tmp_path / f"{nome}.npz", "ambos")
    return log


def test_chaves_textos_e_nonces_sao_os_mesmos_entre_algoritmos(monkeypatch, tmp_path) -> None:
    a = _gera(monkeypatch, tmp_path, "falso_n16", 16, 16)   # como Ascon/GIFT
    b = _gera(monkeypatch, tmp_path, "falso_n12", 12, 8)    # como Grain
    assert len(a) == len(b) > 0
    for (ka, na, pa), (kb, nb, pb) in zip(a, b):
        assert ka == kb
        assert pa == pb
        # o nonce menor são os bytes baixos do mesmo sorteio
        assert int.from_bytes(na, "big") % (1 << 96) == int.from_bytes(nb, "big")


def test_par_difere_em_um_bit_e_o_offset_nao_e_o_contador_global(monkeypatch, tmp_path) -> None:
    log = _gera(monkeypatch, tmp_path, "falso_n16b", 16, 16)
    n1s = []
    for i in range(0, len(log), 2):
        n1 = int.from_bytes(log[i][1], "big")
        n2 = int.from_bytes(log[i + 1][1], "big")
        assert n1 % 2 == 0 and n2 == n1 + 1
        assert bin(n1 ^ n2).count("1") == 1
        n1s.append(n1)
    # v1 dava 0, 2, 4, ... amarrado ao índice da chave; a v2 parte de um offset
    # sorteado por dispositivo, então a primeira chave não começa em zero.
    assert n1s[0] != 0
    por_chave = len(n1s) // 2
    assert n1s[por_chave] != n1s[por_chave - 1] + 2, "segunda chave continuou o contador da primeira"


def test_contador_zero_comeca_do_zero_em_todo_dispositivo(monkeypatch, tmp_path) -> None:
    log: list = []
    monkeypatch.setitem(rf.ALGOS, "falso_zero", _SpecFalsa(16, 16, 16, log))
    rf.generate("falso_zero", "aleatorio", 2, [1], tmp_path / "z.npz", "ambos", contador="zero")
    n1s = [int.from_bytes(log[i][1], "big") for i in range(0, len(log), 2)]
    por_chave = len(n1s) // 2
    assert n1s[:por_chave] == n1s[por_chave:] == list(range(0, 2 * por_chave, 2))



class _Eco:
    """Cifrador falso que devolve o último byte do nonce repetido: deixa ver
    exatamente o que foi guardado em cada lado da amostra."""

    def __init__(self, tag_bytes: int) -> None:
        self.tag_bytes = tag_bytes

    def encrypt(self, key: bytes, nonce: bytes, pt: bytes) -> bytes:
        return bytes([nonce[-1]]) * (len(pt) + self.tag_bytes)


class _SpecEco(_SpecFalsa):
    def cipher(self, rounds: int, politica: str = "ambos"):
        return _Eco(self.tag_bytes)


def test_representacao_par_guarda_os_dois_criptogramas_lado_a_lado(monkeypatch, tmp_path) -> None:
    monkeypatch.setitem(rf.ALGOS, "eco", _SpecEco(16, 16, 16, []))
    par = rf.generate("eco", "aleatorio", 2, [1], tmp_path / "p.npz", "ambos",
                      contador="zero", representacao="par")
    xor = rf.generate("eco", "aleatorio", 2, [1], tmp_path / "x.npz", "ambos",
                      contador="zero", representacao="xor")
    largura = 64 + 16
    assert par["r1"].shape[1] == 2 * largura and par["random"].shape[1] == 2 * largura
    assert xor["r1"].shape[1] == largura
    # contador zero: o par j tem nonces 2j e 2j+1
    for j in (0, 3):
        assert set(par["r1"][j, :largura]) == {2 * j}
        assert set(par["r1"][j, largura:]) == {2 * j + 1}
        assert set(xor["r1"][j]) == {1}



def test_par_mais_xor_e_classe_aleatoria_montada_do_mesmo_jeito(monkeypatch, tmp_path) -> None:
    """Na classe aleatória o 3º bloco também tem que ser o XOR dos dois
    primeiros; senão o classificador separa as classes só por essa checagem."""
    import numpy as np
    monkeypatch.setitem(rf.ALGOS, "eco2", _SpecEco(16, 16, 16, []))
    d = rf.generate("eco2", "aleatorio", 2, [1], tmp_path / "px.npz", "ambos",
                    contador="zero", representacao="par+xor")
    L = 64 + 16
    for nome in ("r1", "random"):
        a, b, c = d[nome][:, :L], d[nome][:, L:2 * L], d[nome][:, 2 * L:]
        assert d[nome].shape[1] == 3 * L
        assert np.array_equal(c, a ^ b), nome
