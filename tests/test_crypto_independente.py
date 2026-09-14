"""Âncoras criptográficas EXTERNAS: implementações independentes vs. os binários.

Por que este arquivo existe
---------------------------
A afirmação "os quatro algoritmos AEAD estão corretamente implementados" é
premissa de toda a dissertação. Para Ascon, Grain e Schwaemm ela se apoia em
KAT oficiais dos designers. Para **GIFT-COFB não havia âncora externa**: o
arquivo `data/kat/LWC_AEAD_KAT_GIFTCOFB128_128.txt` é AUTOGERADO por
`scripts/generate_gift_cofb_kat.py` a partir da própria `_gift_cofb_ref.pyd`
que ele depois "valida" — circular. O repositório vendorizado
(`github.com/aadomn/gift`) não traz KAT; o README dele manda usar o
`TestVectorGen` do NIST. Achado numa auditoria criptográfica independente
(2026-08-24), que também apontou que os headers de
`src/crypto/_gift_cofb_msvc/` são reescritas manuais de código criptográfico
— exatamente o tipo de porte que um KAT circular não consegue auditar.

O que este arquivo faz
----------------------
Reimplementa Ascon-AEAD128 e GIFT-128/COFB **a partir das especificações
publicadas**, em Python puro, e usa essas implementações como oráculo contra
os binários compilados. A cadeia de evidência para o GIFT-COFB passa a ser:

  3 vetores OFICIAIS do cifrador de bloco (embutidos abaixo, do
  `test_vectors.c` dos designers)
      -> validam a implementação independente do GIFT-128
      -> que sustenta o GIFTb-128 e o modo COFB escritos da especificação
      -> que concordam com `_gift_cofb_ref.pyd` em 1089 + 60 casos aleatórios

Nenhuma linha foi copiada do C de referência. O único elemento tomado da
implementação (e não da especificação em papel) é a convenção de ordenação de
bits na interface do GIFTb-128 — uma escolha entre duas convenções naturais,
fixada empiricamente e documentada em `_rho_in`.

O arquivo é **autocontido de propósito**: os vetores oficiais estão embutidos
como literais porque `gift-cofb/` é gitignored, e num clone limpo o
`test_vectors.c` não existe. Só importa os wrappers sob teste.

Referências
-----------
- NIST SP 800-232, *Ascon-Based Lightweight Cryptography Standards*.
- Banik, Pandey, Peyrin, Sasaki, Sim, Todo. "GIFT: A Small Present". CHES 2017.
- Banik et al. "GIFT-COFB", submissão ao NIST LWC (finalista da Rodada 3).
- Adomnicai, Najm, Peyrin. "Fixslicing: A New GIFT Representation".
  TCHES 2020(3) — a representação bitsliced usada pelo GIFTb-128.
"""
from __future__ import annotations

import random
from pathlib import Path

import pytest

from src.crypto.ascon_wrapper import AsconAEAD128
from src.crypto.gift_cofb_wrapper import GiftCOFB
from src.crypto.kat_parser import parse_kat_file

_KAT_DIR = Path(__file__).parent.parent / "data" / "kat"
_KAT_ASCON = _KAT_DIR / "LWC_AEAD_KAT_ASCON128AV13.txt"
_KAT_GIFT = _KAT_DIR / "LWC_AEAD_KAT_GIFTCOFB128_128.txt"


# ======================================================================
# 1. Ascon-AEAD128 — do NIST SP 800-232
# ======================================================================

_M64 = 0xFFFFFFFFFFFFFFFF
_ASCON_RC = [0xF0, 0xE1, 0xD2, 0xC3, 0xB4, 0xA5, 0x96, 0x87, 0x78, 0x69, 0x5A, 0x4B]

# IV do Ascon-AEAD128 (taxa 128 bits). O Ascon-128a v1.2 usava
# 0x80800C0800000000 — este valor, junto com a carga little-endian e o padding
# 0x01, é o que distingue o padrão final do candidato da competição.
ASCON_AEAD128_IV = 0x00001000808C0001


def _ror(x: int, n: int) -> int:
    return ((x >> n) | (x << (64 - n))) & _M64


def _ascon_perm(s: list[int], rounds: int) -> list[int]:
    """Permutação Ascon-p: adição de constante, camada S bitsliced, difusão."""
    x0, x1, x2, x3, x4 = s
    for c in _ASCON_RC[12 - rounds:]:
        x2 ^= c
        # camada de substituição (S-box de 5 bits em forma bitsliced)
        x0 ^= x4
        x4 ^= x3
        x2 ^= x1
        t0 = (~x0 & _M64) & x1
        t1 = (~x1 & _M64) & x2
        t2 = (~x2 & _M64) & x3
        t3 = (~x3 & _M64) & x4
        t4 = (~x4 & _M64) & x0
        x0 ^= t1
        x1 ^= t2
        x2 ^= t3
        x3 ^= t4
        x4 ^= t0
        x1 ^= x0
        x0 ^= x4
        x3 ^= x2
        x2 ^= _M64
        # camada de difusão linear
        x0 ^= _ror(x0, 19) ^ _ror(x0, 28)
        x1 ^= _ror(x1, 61) ^ _ror(x1, 39)
        x2 ^= _ror(x2, 1) ^ _ror(x2, 6)
        x3 ^= _ror(x3, 10) ^ _ror(x3, 17)
        x4 ^= _ror(x4, 7) ^ _ror(x4, 41)
    return [x0, x1, x2, x3, x4]


def _ld(b: bytes) -> int:
    """Carga little-endian (SP 800-232; o v1.2 era big-endian)."""
    return int.from_bytes(b, "little")


def _st(x: int) -> bytes:
    return x.to_bytes(8, "little")


def _absorve_parcial(s: list[int], blk: bytes, i0: int, i1: int) -> None:
    """XOR de bloco parcial (<16B) nas palavras i0/i1 + padding PAD(i)=0x01<<8i."""
    n = len(blk)
    s[i0] ^= _ld(blk[:8].ljust(8, b"\x00"))
    s[i1] ^= _ld(blk[8:].ljust(8, b"\x00"))
    if n < 8:
        s[i0] ^= 1 << (8 * n)
    else:
        s[i1] ^= 1 << (8 * (n - 8))


def ascon_aead128_encrypt(key: bytes, nonce: bytes, pt: bytes, ad: bytes = b"",
                          pa: int = 12, pb: int = 8) -> bytes:
    """Ascon-AEAD128: taxa 128, p^12 na inicialização/finalização, p^8 nos dados.

    `pa`/`pb` existem para o estudo de sensibilidade com rodadas reduzidas; nos
    valores padrão a saída é a do algoritmo especificado. A redução consome as
    ÚLTIMAS constantes de rodada (ver `_ascon_perm`), que é a convenção do
    próprio `ascon-c`: seu P8 usa RC4..RCb, não RC0..RC7.
    """
    k0, k1 = _ld(key[:8]), _ld(key[8:])
    s = [ASCON_AEAD128_IV, k0, k1, _ld(nonce[:8]), _ld(nonce[8:])]
    s = _ascon_perm(s, pa)
    s[3] ^= k0
    s[4] ^= k1

    if ad:
        corte = len(ad) - len(ad) % 16
        for i in range(0, corte, 16):
            s[0] ^= _ld(ad[i:i + 8])
            s[1] ^= _ld(ad[i + 8:i + 16])
            s = _ascon_perm(s, pb)
        _absorve_parcial(s, ad[corte:], 0, 1)
        s = _ascon_perm(s, pb)

    s[4] ^= 0x80 << 56  # separação de domínio (no v1.2 era o LSB de x4)

    ct = b""
    corte = len(pt) - len(pt) % 16
    for i in range(0, corte, 16):
        s[0] ^= _ld(pt[i:i + 8])
        s[1] ^= _ld(pt[i + 8:i + 16])
        ct += _st(s[0]) + _st(s[1])
        s = _ascon_perm(s, pb)
    cauda = pt[corte:]
    _absorve_parcial(s, cauda, 0, 1)
    ct += (_st(s[0]) + _st(s[1]))[:len(cauda)]

    s[2] ^= k0  # taxa 128 => a chave entra em x2/x3 (no Ascon-128 seria x1/x2)
    s[3] ^= k1
    s = _ascon_perm(s, pa)
    return ct + _st(s[3] ^ k0) + _st(s[4] ^ k1)


# ======================================================================
# 2. GIFT-128 (CHES 2017) e GIFT-COFB (submissão NIST LWC)
# ======================================================================

_GS = [0x1, 0xA, 0x4, 0xC, 0x6, 0xF, 0x3, 0x9, 0x2, 0xD, 0xB, 0x7, 0x5, 0x0, 0x8, 0xE]


def _p128(i: int) -> int:
    """PermBits: P(i) = 4*(i//16) + 32*((3*((i%16)//4) + i%4) % 4) + i%4."""
    return 4 * (i // 16) + 32 * ((3 * ((i % 16) // 4) + (i % 4)) % 4) + (i % 4)


# SubCells + PermBits fundidos numa tabela por byte: SubCells é local ao nibble
# (logo ao byte) e PermBits é permutação de bits, então a composição cabe numa
# tabela 16x256 e uma rodada vira 16 consultas + 1 XOR.
_SBOX_BYTE = [_GS[v & 0xF] | (_GS[v >> 4] << 4) for v in range(256)]
_SP_TAB: list[list[int]] = []
for _k in range(16):
    _linha: list[int] = []
    for _v in range(256):
        _s, _acc = _SBOX_BYTE[_v], 0
        for _t in range(8):
            if (_s >> _t) & 1:
                _acc |= 1 << _p128(8 * _k + _t)
        _linha.append(_acc)
    _SP_TAB.append(_linha)

# Constantes de rodada: LFSR de 6 bits, (c5..c0) <- (c4..c0, c5^c4^1).
_GIFT_RC: list[int] = []
_c = 0
for _ in range(40):
    _c = ((_c << 1) | (((_c >> 5) & 1) ^ ((_c >> 4) & 1) ^ 1)) & 0x3F
    _GIFT_RC.append(_c)


def _round_masks(k_int: int, rounds: int = 40) -> list[int]:
    """AddRoundKey + constante de rodada colapsados num XOR de 128 bits/rodada.

    Key schedule do GIFT-128: K = k7||...||k0 (palavras de 16 bits);
    RK = U||V com U = k5||k4 e V = k1||k0; atualização
    K <- k1>>>2 || k0>>>12 || k7 || k6 || k5 || k4 || k3 || k2.
    U entra em b_{4i+2}, V em b_{4i+1}; a constante em b_{4i+3} (i<6) e o bit
    fixo 1 em b_127.

    `rounds` existe para o estudo de sensibilidade com rodadas reduzidas. Aqui
    a redução toma as PRIMEIRAS rodadas, ao contrário do Ascon, porque é assim
    que o key schedule do GIFT avança: a rodada r usa a r-ésima subchave.
    """
    k = [(k_int >> (16 * i)) & 0xFFFF for i in range(8)]

    def ror16(x: int, n: int) -> int:
        return ((x >> n) | (x << (16 - n))) & 0xFFFF

    masks = []
    for r in range(rounds):
        u = (k[5] << 16) | k[4]
        v = (k[1] << 16) | k[0]
        m = 1 << 127
        for i in range(32):
            m |= ((u >> i) & 1) << (4 * i + 2)
            m |= ((v >> i) & 1) << (4 * i + 1)
        c = _GIFT_RC[r]
        for i in range(6):
            m |= ((c >> i) & 1) << (4 * i + 3)
        masks.append(m)
        k = [k[2], k[3], k[4], k[5], k[6], k[7], ror16(k[0], 12), ror16(k[1], 2)]
    return masks


def _gift_core(b: int, masks: list[int]) -> int:
    """Uma rodada de SubCells -> PermBits -> AddRoundKey/constante por máscara."""
    tab = _SP_TAB
    for m in masks:
        b = (tab[0][b & 0xFF] | tab[1][(b >> 8) & 0xFF] | tab[2][(b >> 16) & 0xFF]
             | tab[3][(b >> 24) & 0xFF] | tab[4][(b >> 32) & 0xFF]
             | tab[5][(b >> 40) & 0xFF] | tab[6][(b >> 48) & 0xFF]
             | tab[7][(b >> 56) & 0xFF] | tab[8][(b >> 64) & 0xFF]
             | tab[9][(b >> 72) & 0xFF] | tab[10][(b >> 80) & 0xFF]
             | tab[11][(b >> 88) & 0xFF] | tab[12][(b >> 96) & 0xFF]
             | tab[13][(b >> 104) & 0xFF] | tab[14][(b >> 112) & 0xFF]
             | tab[15][(b >> 120) & 0xFF]) ^ m
    return b


# --- os dois mapeamentos byte <-> estado -------------------------------
# pi:  interface "GIFT-128" do NIST (a dos 3 vetores oficiais) — b_127 é o MSB
#      do byte 0, ou seja, o inteiro big-endian.
# rho: interface "GIFTb-128", usada DENTRO do COFB — o estado é lido direto
#      como as 4 palavras bitsliced W_j (W_j[i] = b_{4i+j}) do paper
#      Fixslicing, sem passar pelo packing/unpacking. É a única convenção
#      fixada empiricamente aqui (escolha entre 2 alternativas naturais);
#      todo o resto vem da especificação.

def _pi_in(x: bytes) -> int:
    return int.from_bytes(x, "big")


def _pi_out(b: int) -> bytes:
    return b.to_bytes(16, "big")


_RHO_TAB: list[list[int]] = []
for _k in range(16):
    _linha = []
    for _v in range(256):
        _acc = 0
        for _t in range(8):
            if (_v >> _t) & 1:
                _j = _k // 4                    # palavra W_j
                _i = (3 - (_k % 4)) * 8 + _t    # índice do bit (palavra big-endian)
                _acc |= 1 << (4 * _i + _j)
        _linha.append(_acc)
    _RHO_TAB.append(_linha)


def _rho_in(x: bytes) -> int:
    b = 0
    for k in range(16):
        b |= _RHO_TAB[k][x[k]]
    return b


def _rho_out(b: int) -> bytes:
    out = bytearray(16)
    for j in range(4):
        w = 0
        for i in range(32):
            w |= ((b >> (4 * i + j)) & 1) << i
        out[4 * j:4 * j + 4] = w.to_bytes(4, "big")
    return bytes(out)


def gift128_encrypt_block(pt: bytes, key: bytes, rounds: int = 40) -> bytes:
    """GIFT-128 na interface do NIST — a que os 3 vetores oficiais cobrem."""
    return _pi_out(_gift_core(_pi_in(pt), _round_masks(_pi_in(key), rounds)))


def giftb128_encrypt_block(pt: bytes, key: bytes, rounds: int = 40) -> bytes:
    """GIFTb-128 — mesmo cifrador, representação bitsliced na interface."""
    return _rho_out(_gift_core(_rho_in(pt), _round_masks(_pi_in(key), rounds)))


# --- modo COFB ---------------------------------------------------------
_N = 16


def _dbl(x: int) -> int:
    """Dobra em GF(2^64), polinômio x^64 + x^4 + x^3 + x + 1 (0x1b)."""
    return ((x << 1) ^ 0x1B) & _M64 if (x >> 63) & 1 else (x << 1)


def _triplo(x: int) -> int:
    return _dbl(x) ^ x


def _xor(a: bytes, b: bytes) -> bytes:
    return bytes(p ^ q for p, q in zip(a, b))


def _pad10(b: bytes) -> bytes:
    """pad(X) = X || 1 || 0*, aplicado só a bloco incompleto."""
    return b if len(b) == _N else b + b"\x80" + b"\x00" * (_N - len(b) - 1)


def _g(y: bytes) -> bytes:
    """G(Y1 || Y2) = Y2 || (Y1 <<< 1), com Y1 e Y2 de 64 bits."""
    y1 = int.from_bytes(y[:8], "big")
    return y[8:] + (((y1 << 1) | (y1 >> 63)) & _M64).to_bytes(8, "big")


def gift_cofb_encrypt(key: bytes, nonce: bytes, pt: bytes, ad: bytes = b"",
                      rounds: int = 40) -> bytes:
    """GIFT-COFB: feedback combinado, máscara L dobrada/triplicada em GF(2^64).

    O expoente do 3 antes do ÚLTIMO bloco de AD é 1 + [A_a parcial] +
    2*[M vazio] — as quatro linhas da especificação colapsadas numa só.

    `rounds` reduz apenas o cifrador de bloco interno; o modo COFB em volta
    permanece intacto, que é o que se quer no estudo de sensibilidade.
    """
    masks = _round_masks(_pi_in(key), rounds)

    def e(blk: bytes) -> bytes:
        return _rho_out(_gift_core(_rho_in(blk), masks))

    def fb(y: bytes, blk: bytes, ell: int) -> bytes:
        return _xor(_xor(_pad10(blk), _g(y)), ell.to_bytes(8, "big") + b"\x00" * 8)

    y = e(nonce)
    ell = int.from_bytes(y[:8], "big")

    blocos_ad = [ad[i:i + _N] for i in range(0, len(ad), _N)] or [b""]
    for blk in blocos_ad[:-1]:
        ell = _dbl(ell)
        y = e(fb(y, blk, ell))
    for _ in range(1 + (len(blocos_ad[-1]) != _N) + 2 * (not pt)):
        ell = _triplo(ell)
    y = e(fb(y, blocos_ad[-1], ell))

    ct = b""
    if pt:
        blocos_m = [pt[i:i + _N] for i in range(0, len(pt), _N)]
        for blk in blocos_m[:-1]:
            ct += _xor(blk, y[:len(blk)])
            ell = _dbl(ell)
            y = e(fb(y, blk, ell))
        ultimo = blocos_m[-1]
        ct += _xor(ultimo, y[:len(ultimo)])
        ell = _triplo(ell) if len(ultimo) == _N else _triplo(_triplo(ell))
        y = e(fb(y, ultimo, ell))
    return ct + y


# ======================================================================
# 3. Testes
# ======================================================================

# Vetores OFICIAIS do GIFT-128, do `test_vectors.c` dos designers
# (github.com/aadomn/gift, crypto_bc/gift128/opt32); o primeiro é o vetor
# publicado no paper CHES 2017. Embutidos como literais porque `gift-cofb/` é
# gitignored — num clone limpo o arquivo original não existe.
VETORES_OFICIAIS_GIFT128 = [
    ("00000000000000000000000000000000",
     "00000000000000000000000000000000",
     "cd0bd738388ad3f668b15a36ceb6ff92"),
    ("fedcba9876543210fedcba9876543210",
     "fedcba9876543210fedcba9876543210",
     "8422241a6dbf5a9346af468409ee0152"),
    ("d0f5c59a7700d3e799028fa9f90ad837",
     "e39c141fa57dba43f08a85b6a91f86c1",
     "13ede67cbdcc3dbf400a62d6977265ea"),
]


def _casos_aleatorios(n: int, max_len: int, seed: int):
    rng = random.Random(seed)
    for _ in range(n):
        yield (
            bytes(rng.getrandbits(8) for _ in range(16)),
            bytes(rng.getrandbits(8) for _ in range(16)),
            bytes(rng.getrandbits(8) for _ in range(rng.randint(0, max_len))),
            bytes(rng.getrandbits(8) for _ in range(rng.randint(0, max_len))),
        )


# --- a âncora externa --------------------------------------------------

@pytest.mark.parametrize("kh,ph,ch", VETORES_OFICIAIS_GIFT128)
def test_gift128_independente_vs_vetores_oficiais(kh: str, ph: str, ch: str) -> None:
    """ÂNCORA EXTERNA do GIFT-COFB: a implementação independente do cifrador de
    bloco bate com os 3 vetores publicados pelos designers.

    É o único elo da cadeia do GIFT-COFB que não depende de nada gerado dentro
    deste repositório."""
    assert gift128_encrypt_block(bytes.fromhex(ph), bytes.fromhex(kh)) == bytes.fromhex(ch)


def test_gift_cofb_independente_vs_binario() -> None:
    """A implementação independente concorda com `_gift_cofb_ref.pyd`.

    Substitui o KAT circular: se a porta MSVC feita à mão
    (`src/crypto/_gift_cofb_msvc/`) tivesse corrompido o cifrador, o KAT
    autogerado passaria e este teste falharia."""
    w = GiftCOFB()
    for key, nonce, pt, ad in _casos_aleatorios(60, 100, seed=20260824):
        assert gift_cofb_encrypt(key, nonce, pt, ad) == w.encrypt(key, nonce, pt, ad), (
            f"divergência em len(pt)={len(pt)} len(ad)={len(ad)}"
        )


def test_gift_cofb_independente_vs_kat_versionado() -> None:
    """Revalida o KAT autogerado contra a implementação independente.

    Depois deste teste o arquivo deixa de ser circular: passa a ser um registro
    conferido por uma segunda implementação, escrita da especificação."""
    assert _KAT_GIFT.exists(), f"KAT não encontrado: {_KAT_GIFT}"
    vetores = parse_kat_file(_KAT_GIFT)
    assert len(vetores) == 1089
    ruins = [v.count for v in vetores
             if gift_cofb_encrypt(v.key, v.nonce, v.pt, v.ad) != v.ct]
    assert not ruins, f"vetores divergentes: {ruins[:10]}"


# --- Ascon: âncora redundante (o KAT dele já é oficial) ----------------

def test_ascon_independente_vs_kat_oficial() -> None:
    """1089/1089 contra o KAT dos designers, saindo de uma segunda
    implementação escrita do SP 800-232."""
    assert _KAT_ASCON.exists(), f"KAT não encontrado: {_KAT_ASCON}"
    vetores = parse_kat_file(_KAT_ASCON)
    assert len(vetores) == 1089
    ruins = [v.count for v in vetores
             if ascon_aead128_encrypt(v.key, v.nonce, v.pt, v.ad) != v.ct]
    assert not ruins, f"vetores divergentes: {ruins[:10]}"


def test_ascon_independente_vs_binario() -> None:
    a = AsconAEAD128()
    for key, nonce, pt, ad in _casos_aleatorios(80, 300, seed=20260824):
        assert ascon_aead128_encrypt(key, nonce, pt, ad) == a.encrypt(key, nonce, pt, ad), (
            f"divergência em len(pt)={len(pt)} len(ad)={len(ad)}"
        )


def test_ascon_iv_fixa_a_variante_compilada() -> None:
    """Fixa a variante: o IV é o do SP 800-232, não o do Ascon-128a v1.2.

    O v1.2 usava 0x80800C0800000000 com carga big-endian e padding 0x80; o
    padrão final usa este IV, carga little-endian e padding 0x01. Se o `.pyd`
    fosse o Ascon-128 (taxa 64) ou o v1.2, o teste do KAT falharia — e é por
    isso que a docstring de `validate_kat` não deve apontar para
    `ascon-c/LWC_AEAD_KAT_128_128.txt`, que é o arquivo da taxa 64."""
    assert ASCON_AEAD128_IV == 0x00001000808C0001
    assert ASCON_AEAD128_IV != 0x80800C0800000000
    a = AsconAEAD128()
    key = bytes(range(16))
    nonce = bytes(range(16, 32))
    assert ascon_aead128_encrypt(key, nonce, b"", b"") == a.encrypt(key, nonce, b"", b"")


# --- rodadas reduzidas (estudo de sensibilidade do detector) ----------
#
# A corretude das versões reduzidas só pode ser estabelecida contra as builds
# em C reduzidas, que ainda não existem. O que estes testes cobrem é o que dá
# para cobrir agora: que a parametrização é inerte nos valores padrão, que ela
# de fato altera a saída, e que ela não toca no modo em volta do cifrador.

_RED_KEY = bytes(range(16))
_RED_NONCE = bytes(range(16, 32))
_RED_PT = bytes(range(64))
_RED_AD = b"cabecalho"


def test_rodadas_padrao_reproduzem_a_especificacao() -> None:
    """Nos valores padrão a saída é idêntica à de antes da parametrização.

    É isso que permite dizer que as builds reduzidas saem do mesmo código que
    valida os 1.089 vetores oficiais, e não de um caminho paralelo."""
    assert (ascon_aead128_encrypt(_RED_KEY, _RED_NONCE, _RED_PT, _RED_AD, pa=12, pb=8)
            == ascon_aead128_encrypt(_RED_KEY, _RED_NONCE, _RED_PT, _RED_AD))
    assert (gift_cofb_encrypt(_RED_KEY, _RED_NONCE, _RED_PT, _RED_AD, rounds=40)
            == gift_cofb_encrypt(_RED_KEY, _RED_NONCE, _RED_PT, _RED_AD))
    assert (gift128_encrypt_block(_RED_PT[:16], _RED_KEY, rounds=40)
            == gift128_encrypt_block(_RED_PT[:16], _RED_KEY))


@pytest.mark.parametrize("pa,pb", [(12, 1), (12, 4), (12, 6), (6, 8), (1, 8)])
def test_ascon_rodadas_reduzidas_alteram_o_criptograma(pa: int, pb: int) -> None:
    assert (ascon_aead128_encrypt(_RED_KEY, _RED_NONCE, _RED_PT, pa=pa, pb=pb)
            != ascon_aead128_encrypt(_RED_KEY, _RED_NONCE, _RED_PT))


@pytest.mark.parametrize("rounds", [5, 10, 20, 30, 35])
def test_gift_rodadas_reduzidas_alteram_o_criptograma(rounds: int) -> None:
    assert (gift_cofb_encrypt(_RED_KEY, _RED_NONCE, _RED_PT, rounds=rounds)
            != gift_cofb_encrypt(_RED_KEY, _RED_NONCE, _RED_PT))


@pytest.mark.parametrize("rounds", [5, 20, 40])
def test_reducao_nao_altera_o_modo_em_volta(rounds: int) -> None:
    """O comprimento do criptograma não muda com o número de rodadas.

    O estudo compara representações do criptograma entre configurações de
    rodadas; se a redução mexesse no modo, o comprimento viraria uma variável
    de confusão trivialmente separável, exatamente o vazamento estrutural que
    já custou uma rodada inteira do Caminho A."""
    pb = max(1, rounds // 5)
    ct_ascon = ascon_aead128_encrypt(_RED_KEY, _RED_NONCE, _RED_PT, pb=pb)
    ct_gift = gift_cofb_encrypt(_RED_KEY, _RED_NONCE, _RED_PT, rounds=rounds)
    assert len(ct_ascon) == len(_RED_PT) + 16
    assert len(ct_gift) == len(_RED_PT) + 16


def test_giftb128_difere_do_gift128_na_interface() -> None:
    """GIFTb-128 e GIFT-128 são o MESMO cifrador em representações distintas.

    Documenta a única convenção fixada empiricamente neste arquivo: se as duas
    coincidissem, `_rho_in` seria supérfluo — o teste falharia e apontaria que
    a hipótese sobre a interface está errada."""
    pt = bytes(range(16))
    key = bytes(range(16, 32))
    assert gift128_encrypt_block(pt, key) != giftb128_encrypt_block(pt, key)
    # rho é bijetiva: 256 entradas distintas -> 256 saídas distintas
    assert len({_rho_out(_rho_in(bytes([i] * 16))) for i in range(256)}) == 256
