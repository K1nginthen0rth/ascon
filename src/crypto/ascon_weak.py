"""Ascon-AEAD128 com o número de rodadas da permutação por bloco (`p^b`)
reduzido abaixo do padrão — gerador do experimento de "instância fraca".

Por que existe
--------------
O experimento principal (v2) compara os 4 algoritmos LWC usados CORRETAMENTE
e espera H0 (ciphertext-only não distingue implementações corretas de
algoritmos aprovados). Esse resultado é forte, mas não dá uma resposta
positiva demonstrável. Este módulo gera o outro lado da história: uma
instância deliberadamente enfraquecida do Ascon-AEAD128, variando só o número
de rodadas de `p^b` (a permutação aplicada a cada bloco de 16 bytes durante o
processamento de dados — 8 rodadas no padrão SP 800-232), mantendo tudo o
resto idêntico (mesma `p^a`=12 na inicialização/finalização, mesmo IV, mesma
carga little-endian, mesmo padding, mesma separação de domínio).

Reduzir `p^b` é a forma padrão de "instância fraca" usada em criptoanálise de
terceiros durante a avaliação do NIST LWC: ataques diferencial/linear contra a
permutação Ascon em contagem de rodadas reduzida já foram publicados. A
pergunta empírica deste experimento não é se existe um distinguidor em
princípio — é se o MESMO pipeline de ML construído para o experimento
principal (features de ciphertext-only, RandomForest com key-holdout) detecta
a mesma fraqueza na prática, e a partir de qual contagem de rodadas.

Proveniência
------------
A permutação em si é a MESMA reimplementada e auditada em
`tests/test_crypto_independente.py` (validada 1089/1089 contra o KAT oficial
do Ascon-AEAD128 com `p^b`=8). Este módulo generaliza `_ascon_perm` para
aceitar um `pb_rounds` diferente de 8 nas chamadas por bloco, mantendo `p^a`
fixo em 12. `test_ascon_weak.py` confere que `pb_rounds=8` (o valor oficial)
produz EXATAMENTE o mesmo ciphertext que `AsconAEAD128` (o wrapper C sob
teste em todo o resto do projeto) — ou seja, a única mudança de
comportamento possível é a intencional.

NÃO reaproveita `tests/test_crypto_independente.py` diretamente: aquele
arquivo é uma âncora de corretude (não deve ganhar parâmetros de
"enfraquecimento" nem virar dependência de um script de geração de dataset).
Este módulo é uma cópia derivada, com um parâmetro a mais, para um propósito
diferente — gerar dados, não validar o binário.
"""
from __future__ import annotations

_M64 = 0xFFFFFFFFFFFFFFFF
_ASCON_RC = [0xF0, 0xE1, 0xD2, 0xC3, 0xB4, 0xA5, 0x96, 0x87, 0x78, 0x69, 0x5A, 0x4B]

ASCON_AEAD128_IV = 0x00001000808C0001
PA_ROUNDS = 12          # inicialização/finalização — NUNCA reduzido aqui
PB_ROUNDS_OFICIAL = 8   # p^b padrão do Ascon-AEAD128 (SP 800-232)


def _ror(x: int, n: int) -> int:
    return ((x >> n) | (x << (64 - n))) & _M64


def _ascon_perm(s: list[int], rounds: int) -> list[int]:
    """Permutação Ascon-p com `rounds` rodadas (as ÚLTIMAS `rounds` constantes
    da sequência de 12 — é assim que P12/P8/P6 são definidas em
    `permutations.h` do ascon-c: cada uma é um prefixo comum na cauda)."""
    x0, x1, x2, x3, x4 = s
    for c in _ASCON_RC[12 - rounds:]:
        x2 ^= c
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
        x0 ^= _ror(x0, 19) ^ _ror(x0, 28)
        x1 ^= _ror(x1, 61) ^ _ror(x1, 39)
        x2 ^= _ror(x2, 1) ^ _ror(x2, 6)
        x3 ^= _ror(x3, 10) ^ _ror(x3, 17)
        x4 ^= _ror(x4, 7) ^ _ror(x4, 41)
    return [x0, x1, x2, x3, x4]


def _ld(b: bytes) -> int:
    return int.from_bytes(b, "little")


def _st(x: int) -> bytes:
    return x.to_bytes(8, "little")


def _absorve_parcial(s: list[int], blk: bytes, i0: int, i1: int) -> None:
    n = len(blk)
    s[i0] ^= _ld(blk[:8].ljust(8, b"\x00"))
    s[i1] ^= _ld(blk[8:].ljust(8, b"\x00"))
    if n < 8:
        s[i0] ^= 1 << (8 * n)
    else:
        s[i1] ^= 1 << (8 * (n - 8))


def ascon_weak_encrypt(
    key: bytes, nonce: bytes, pt: bytes, ad: bytes = b"", pb_rounds: int = PB_ROUNDS_OFICIAL,
) -> bytes:
    """Ascon-AEAD128 com `p^b` = `pb_rounds` (padrão: 8, o valor oficial).

    `pb_rounds=8` reproduz EXATAMENTE o Ascon-AEAD128 padrão — ver
    `test_ascon_weak.py::test_pb_rounds_oficial_bate_com_wrapper_c`.

    `pb_rounds=0` é um caso limite qualitativamente diferente de "poucas
    rodadas": a permutação vira identidade, então não há NENHUMA mistura
    não-linear entre blocos — o "keystream" de cada bloco passa a ser o XOR
    acumulado dos blocos de plaintext anteriores. Isso tende a vazar
    estrutura do PRÓPRIO PLAINTEXT (detectável por estatística global —
    histograma, entropia, n-gramas), diferente de 1–6 rodadas, onde a saída
    já tem boa aparência estatística local mesmo sem margem de segurança
    algébrica (ver `docs/plano_experimento_v2/05_execucao_riscos_pendencias.md`
    §5.14 para a discussão completa desse resultado).
    """
    if not 0 <= pb_rounds <= 12:
        raise ValueError(f"pb_rounds={pb_rounds} fora de [0, 12]")

    k0, k1 = _ld(key[:8]), _ld(key[8:])
    s = [ASCON_AEAD128_IV, k0, k1, _ld(nonce[:8]), _ld(nonce[8:])]
    s = _ascon_perm(s, PA_ROUNDS)
    s[3] ^= k0
    s[4] ^= k1

    if ad:
        corte = len(ad) - len(ad) % 16
        for i in range(0, corte, 16):
            s[0] ^= _ld(ad[i:i + 8])
            s[1] ^= _ld(ad[i + 8:i + 16])
            s = _ascon_perm(s, pb_rounds)
        _absorve_parcial(s, ad[corte:], 0, 1)
        s = _ascon_perm(s, pb_rounds)

    s[4] ^= 0x80 << 56

    ct = b""
    corte = len(pt) - len(pt) % 16
    for i in range(0, corte, 16):
        s[0] ^= _ld(pt[i:i + 8])
        s[1] ^= _ld(pt[i + 8:i + 16])
        ct += _st(s[0]) + _st(s[1])
        s = _ascon_perm(s, pb_rounds)
    cauda = pt[corte:]
    _absorve_parcial(s, cauda, 0, 1)
    ct += (_st(s[0]) + _st(s[1]))[:len(cauda)]

    s[2] ^= k0
    s[3] ^= k1
    s = _ascon_perm(s, PA_ROUNDS)
    return ct + _st(s[3] ^ k0) + _st(s[4] ^ k1)
