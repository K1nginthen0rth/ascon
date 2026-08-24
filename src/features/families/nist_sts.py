"""
Família 7: suíte estatística NIST SP 800-22 Rev.1a (15 testes, nível de bit).

Backend: pacote `nistrng` (implementação independente, licença BSD-3, usada
como base para reduzir o risco de reimplementar do zero 15 testes
estatísticos intrincados — ver docs/plano_experimento_v2/02_features_e_selecao.md).
A implementação foi auditada linha a linha contra o texto normativo antes de
ser usada aqui, e **sete desvios foram corrigidos ou contornados** nesta
camada (não no pacote vendorizado) — três deles ([CRÍTICO], abaixo)
produziam resultados sistematicamente errados, não apenas ausência de sinal:

-1. **[CRÍTICO] Binary Matrix Rank corrompe o array de bits compartilhado.**
    `BinaryMatrix.__init__` (test_binary_matrix_rank.py) faz
    `self._matrix = block`, onde `block` é uma VIEW de `bits` (slice +
    reshape, sem cópia) — a eliminação gaussiana então escreve em
    `self._matrix[j, :] = ...` **diretamente no array original**. Confirmado
    por inspeção: rodar `binary_matrix_rank` seguido de qualquer outro teste
    no MESMO array corrompia silenciosamente os resultados de TODOS os
    testes seguintes (dft, approximate_entropy, maurers_universal, serial,
    cumulative_sums, linear_complexity, excursões — 7 testes, todos com
    p-value exatamente 0.0 de forma reprodutível, não aleatória, em 4
    tentativas independentes). Sem esta correção, ~metade da suíte teria
    saído de dados corrompidos, não do ciphertext real. Corrigido: toda
    chamada a um teste do `nistrng` (via `_single_score`/`_multi_score`/os
    dois bypasses de `is_eligible`) passa `bits.copy()`, nunca a referência
    compartilhada — defesa contra este bug e qualquer outro igual ainda não
    identificado nas 15 implementações.
0. **Cumulative Sums**: acumula `forward_sum`/`backward_sum` num loop Python
   manual (não usa `numpy.cumsum`, que faria upcast automático) — herda o
   dtype `int8` do array de bits de entrada e **estoura silenciosamente**
   (confirmado: `RuntimeWarning: overflow encountered in scalar add`) para
   qualquer sequência com caminhada acumulada fora de [-128, 127], o que é
   praticamente garantido nos nossos CTs de centenas de milhares de bits.
   Contornado aqui alimentando esse teste especificamente com bits em
   `int32` (só ele — os demais testes usam a convenção `int8` do pacote,
   segura para eles porque usam `numpy.cumsum`/`count_nonzero`, que fazem
   upcast ou não acumulam).
1. **Non-overlapping Template Matching**: a implementação do `nistrng`
   escolhe UM template aleatoriamente a cada chamada (`random.choice`, sem
   seed) — não-determinístico entre execuções (viola Regra de Ouro 1 —
   seeds fixas) e não é o desenho oficial (NIST usa múltiplos templates
   agregados, não um só sorteado). Corrigido aqui: iteramos
   deterministicamente sobre TODOS os templates de comprimento 2–8 já
   catalogados no pacote (a tabela em si — quais bytes são templates
   aperiódicos — vem do pacote; a agregação determinística é nossa) e
   reportamos estatísticas agregadas (média/mín) em vez de escolher um.
2. **Random Excursion Variant**: a implementação do `nistrng` calcula o
   argumento da função `erfc` mas **esquece de aplicar `erfc`** antes de
   devolver o "p-value" — bug confirmado por leitura do código-fonte
   (compare com `test_random_excursion.py`, que usa `gammaincc`
   corretamente). Recalculado aqui a partir da mesma lógica de ciclos do
   pacote, com `math.erfc` aplicado como o padrão exige.
3a. **Approximate Entropy e Serial: reimplementados vetorizados.** As
   versões do `nistrng` contam frequências de padrões sobrepostos em loops
   Python triplo-aninhados (chamando `_pattern_to_int` posição a posição) —
   6-10s por amostra de 64KB cada, inviável em 180k amostras. Reimplementado
   aqui com `sliding_window_view` + produto escalar de pesos binários +
   `np.bincount` (mesma técnica de `bitblock.py`) — validado bit-a-bit
   idêntico ao `nistrng` original em 10 sequências aleatórias (5 cada,
   tamanhos variados) antes da troca.
4. **Linear Complexity**: o `nistrng` marca o teste como inelegível para
   sequências < 1.000.000 bits (recomendação do padrão). Nosso CT de 64KB
   tem 524.416 bits (524.352 para Grain) — abaixo do recomendado, mas
   524.416 / 512 = 1024 blocos EXATOS (divisão limpa, sem bloco parcial) —
   diferente de Overlapping Template Matching (ver abaixo), aqui a conta
   permanece matematicamente válida, só com menos blocos que o recomendado
   (potência estatística reduzida, não resultado espúrio). Reabilitado
   aqui com a eligibilidade recalculada dinamicamente por amostra
   (`bits.size // 512 >= 1`), e sinalizado via `nist_linear_complexity_valid`.
4b. **[CRÍTICO] `_berlekamp_massey` do nistrng aliasa `b` e `c` — resultado
   errado em boa parte das amostras.** `t = c[:]` seguido de `b = t`: em
   NumPy, `array[:]` é uma VIEW, não uma cópia (ao contrário de uma lista
   Python, onde `lista[:]` copia de fato) — depois que `b` recebe essa view,
   as escritas seguintes em `c[...] = ...` mutam o MESMO buffer, corrompendo
   retroativamente o "snapshot" que `b` deveria preservar. Confirmado
   rastreando as duas implementações passo a passo no mesmo CT: os arrays
   `c` divergem a partir do primeiro evento em que haveria a troca de `b`
   (n=5 num caso de teste de 64 bits), e o resultado final diverge em ~65%
   das sequências testadas (13/20 aleatórias). Nossa reimplementação usa
   `c.copy()` explicitamente (`_berlekamp_massey_numba`, abaixo) — cross-
   validada idêntica a uma reimplementação de referência independente do
   algoritmo clássico de Massey em 50 sequências aleatórias antes da troca
   (a versão nistrng NÃO bate com nenhuma das duas — não é usada em
   produção neste módulo).
5. **[CRÍTICO] Linear Complexity classifica ~60% dos tickets no bucket
   errado.** A fórmula do `nistrng` para mapear a estatística por bloco
   ("ticket") numa das 7 classes C0..C6 é `int(max(-2.5, ticket) + 2.5)` —
   trunca em vez de respeitar as fronteiras semi-abertas do padrão
   (limite superior incluído). Isso desloca toda a massa central da
   distribuição (onde a maioria dos tickets cai) da classe C3 (dominante,
   probabilidade 0,5) para C2 — confirmado comparando as duas fórmulas em
   100 mil pontos aleatórios (59.679 discordâncias) e por inspeção direta
   num CT real (frequência observada de 512 exatamente na classe 2 em vez
   da 3, onde a esperada também é ≈512). Sem correção, χ² inflava para
   ~1700+ e o p-value colapsava para 0,0 sistematicamente em qualquer
   ciphertext, real ou aleatório — não é sinal, é o bug. Corrigido com
   `_ticket_to_bucket` (fronteiras explícitas, sem truncamento), reusando
   `_berlekamp_massey` do `nistrng` (esse componente foi cross-validado
   correto independentemente).

**Limitação estrutural conhecida — Overlapping Template Matching:**
requer ≥ 1.028.016 bits (968 blocos × 1062 bits); nosso CT de 64KB tem, no
máximo, 524.416 bits — **este teste é estruturalmente inaplicável em
qualquer amostra do dataset v2** (não uma falha ocasional: sempre
inelegível, para todo algoritmo e toda amostra). Diferente do Linear
Complexity, aqui os blocos ficariam parciais/vazios perto do fim — rodar
mesmo assim produziria lixo, não sinal fraco. Mantido no vetor de features
por consistência de dimensão, sempre com `nist_overlapping_template_valid=0`
e p-value imputado em 0,5 (neutro) — nunca contribui variância real.

**Excursões (Random Excursion / Variant) — o corte J≥500 elimina METADE
das amostras, não uma minoria.** O padrão recomenda só interpretar o teste
com J (nº de ciclos/cruzamentos por zero) ≥ 500; `nistrng` sempre calcula
um p-value independente disso. Aqui calculamos J nós mesmos e, se J < 500,
marcamos `nist_excursions_valid`/`nist_excursions_variant_valid = 0` e
imputamos p-value 0,5 (neutro) — nunca 0 (zero seria "falha", não "não
aplicável").

**Medido em ciphertexts reais do v2 (2026-08-24):** J tem mediana ~450-490
contra o valor teórico sqrt(2n/π)=578, e a **taxa de validade fica em
~46-48%** — equilibrada entre os 6 algoritmos (40% a 50%), então não é
vazamento, mas significa que os dois testes de excursão são avaliados em
**pouco menos da metade do dataset**, e 4 das 641 features ficam
constantes em 0,5 nas demais. O corte cai praticamente sobre a mediana da
distribuição real de J.

**Consequência para o texto:** "rodamos a suíte NIST SP 800-22 completa"
precisa da ressalva de que 2 dos 15 testes valem em ~metade das amostras,
e 1 (Overlapping Template) em nenhuma. **Features informativas reais: 638 de 641** — três são constantes por
construção em 64KB: `nist_overlapping_template` (sempre 0,5, teste
estruturalmente inelegível), `nist_overlapping_template_valid` (sempre 0)
e `nist_linear_complexity_valid` (sempre 1, pois 524.416/512 = 1024
blocos exatos em qualquer amostra). O VT as descarta, então o efeito
prático é nulo — mas **638** é o número que vai para o texto.

**Templates: estatísticas agregadas, não 158 colunas** — média, desvio
padrão e mínimo do p-value entre templates, como decidido em
`02_features_e_selecao.md`.

**Performance — Berlekamp-Massey via numba:** a versão pura-Python do
`nistrng` (chamada 1024x por amostra, uma por bloco de 512 bits) levava
~44s/amostra sozinha — inviável em 180k amostras. Reimplementado com
`@numba.njit` (mesmo algoritmo, cross-validado idêntico à referência em 50
sequências aleatórias antes da troca): ~400x mais rápido após o
aquecimento do JIT (que ocorre uma vez por processo, não por amostra).

REGRA CRÍTICA: nenhum teste desta família usa plaintext, chave ou nonce —
opera inteiramente sobre os bits do ciphertext.
"""
from __future__ import annotations

import collections
import math

import numba
import numpy as np
import scipy.special
from nistrng import SP800_22R1A_BATTERY
from nistrng.sp800_22r1a import NonOverlappingTemplateMatchingTest as _NOTMTest

_NAN = float("nan")
_NEUTRAL_P = 0.5  # imputação p/ teste inaplicável — nunca 0.0 (seria "reprovou")
_MIN_CYCLES_FOR_EXCURSIONS = 500
# Comprimento de bloco do Approximate Entropy. Literal de propósito — a
# expressão do nistrng que "calculava" isto era malformada e devolvia 2
# sempre (ver `_approximate_entropy_vectorized`).
_APEN_BLOCK_LEN = 2  # recomendação do próprio SP 800-22

_battery = SP800_22R1A_BATTERY  # instâncias reaproveitadas entre chamadas (stateless o bastante)

# Templates de comprimento 2..8 já catalogados pelo nistrng (tabela reaproveitada;
# a agregação determinística abaixo é nossa — ver ponto 1 do docstring do módulo).
_NOTM_TEMPLATES: list[np.ndarray] = [
    np.array(t, dtype=np.uint8)
    for group in _NOTMTest()._templates
    for t in group
]


def _template_to_int(template: np.ndarray) -> int:
    """Valor inteiro do padrão de bits (MSB primeiro), para comparação
    direta contra janelas pré-computadas — ver `_rolling_window_values`."""
    value = 0
    for bit in template:
        value = (value << 1) | int(bit)
    return value


# Templates agrupados por comprimento: {m: [valor_inteiro, ...]}. Permite
# calcular o valor de cada janela deslizante UMA VEZ por comprimento m
# (7 comprimentos) em vez de uma varredura de comparação por template
# (158 templates) — ver `_non_overlapping_template_matching`.
_NOTM_TEMPLATES_BY_LEN: dict[int, list[int]] = {}
for _t in _NOTM_TEMPLATES:
    _NOTM_TEMPLATES_BY_LEN.setdefault(int(_t.size), []).append(_template_to_int(_t))


def _bits_from_ct(ct: bytes) -> np.ndarray:
    """Converte bytes em array 0/1 (MSB primeiro por byte), formato do nistrng.

    dtype int8 (não uint8): vários testes fazem `bits[bits == 0] = -1`
    in-place (conversão para passeio aleatório ±1) — precisa de sinal.
    Mesma convenção usada internamente por `nistrng.pack_sequence`.
    """
    return np.unpackbits(np.frombuffer(ct, dtype=np.uint8)).astype(np.int8)


def _single_score(name: str, bits: np.ndarray) -> tuple[float, bool]:
    """Roda um teste de score único do battery; retorna (p_value, elegivel).

    Passa sempre uma CÓPIA de `bits` — `binary_matrix_rank` (ver `BinaryMatrix`
    em test_binary_matrix_rank.py) faz eliminação gaussiana diretamente sobre
    a view recebida, mutando `bits` in-place e corrompendo silenciosamente
    todo teste chamado depois dele com o mesmo array (bug confirmado por
    inspeção: `bits.sum()` muda de ~n/2 para um valor muito menor após essa
    chamada). Cópia aqui é a defesa central contra esse bug e qualquer outro
    igual ainda não identificado nas 15 implementações.
    """
    test = _battery[name]
    if not test.is_eligible(bits):
        return _NAN, False
    result, _ = test.run(bits.copy())
    return float(result.score), True


def _multi_score(name: str, bits: np.ndarray) -> tuple[np.ndarray, bool]:
    """Roda um teste multi-score (serial, cumsum, excursões); retorna (scores[], elegivel).

    Sempre passa uma CÓPIA de `bits` ao teste — ver nota de mutação em
    `_single_score`.
    """
    test = _battery[name]
    if name == "cumulative sums":
        # int32: evita o overflow silencioso do acumulador Python manual
        # do teste (ver ponto 0 do docstring do módulo) — os demais testes
        # multi-score usam a convenção int8 normal do pacote. astype() já
        # produz uma cópia nova.
        bits = bits.astype(np.int32)
    if not test.is_eligible(bits):
        return np.array([]), False
    result, _ = test.run(bits.copy())
    # nistrng não expõe os p-values individuais publicamente — só a média
    # (Result.score) e o passed geral. Acessamos o atributo interno
    # documentado em test.py (_score_list) deliberadamente.
    return np.asarray(result._score_list, dtype=float).ravel(), True  # noqa: SLF001


@numba.njit
def _gf2_rank_numba(mat: np.ndarray) -> int:
    """Posto de uma matriz binária sobre GF(2) por eliminação gaussiana.
    Compilado com numba — substitui a versão pura-Python do `nistrng`
    (`BinaryMatrix.compute_rank`), que custava ~0,77s por amostra de 64KB
    (64 matrizes 32x32 por amostra). Validado idêntico ao `nistrng` em 300
    matrizes 32x32 aleatórias antes da troca. Muta `mat` in-place — passe
    sempre uma cópia."""
    rows, cols = mat.shape
    rank = 0
    row = 0
    for col in range(cols):
        pivot = -1
        for r in range(row, rows):
            if mat[r, col] == 1:
                pivot = r
                break
        if pivot == -1:
            continue
        if pivot != row:
            for c in range(cols):
                tmp = mat[row, c]
                mat[row, c] = mat[pivot, c]
                mat[pivot, c] = tmp
        for r in range(rows):
            if r != row and mat[r, col] == 1:
                for c in range(cols):
                    mat[r, c] ^= mat[row, c]
        row += 1
        rank += 1
        if row == rows:
            break
    return rank


def _binary_matrix_rank_fast(bits: np.ndarray) -> tuple[float, bool]:
    """
    Binary Matrix Rank acelerado (ver `_gf2_rank_numba`). Reaproveita as
    CONSTANTES de probabilidade já calculadas pela instância do `nistrng`
    (`_full_rank_probability` etc.), então a estatística χ² e o p-value
    saem da mesma fórmula do pacote — só a eliminação gaussiana foi
    substituída. Também elimina o bug de mutação in-place na origem
    (opera sempre sobre cópias por bloco).

    Returns:
        (p_value, elegivel)
    """
    test = _battery["binary_matrix_rank"]
    n_rows = test._rows_number  # noqa: SLF001
    n_cols = test._cols_number  # noqa: SLF001
    block_size = n_rows * n_cols
    n_blocks = bits.size // block_size
    if n_blocks < test._block_size_min:  # noqa: SLF001
        return _NAN, False

    full_rank = 0
    minus_rank = 0
    remainder = 0
    for b in range(n_blocks):
        block = bits[b * block_size:(b + 1) * block_size]
        mat = block.reshape(n_rows, n_cols).astype(np.int64)  # astype já copia
        rank = _gf2_rank_numba(mat)
        if rank == n_rows:
            full_rank += 1
        elif rank == n_rows - 1:
            minus_rank += 1
        else:
            remainder += 1

    p_full = test._full_rank_probability      # noqa: SLF001
    p_minus = test._minus_rank_probability    # noqa: SLF001
    p_rem = test._remained_rank_probability   # noqa: SLF001
    chi_square = (
        ((full_rank - (p_full * n_blocks)) ** 2) / (p_full * n_blocks)
        + ((minus_rank - (p_minus * n_blocks)) ** 2) / (p_minus * n_blocks)
        + ((remainder - (p_rem * n_blocks)) ** 2) / (p_rem * n_blocks)
    )
    return float(math.e ** (-chi_square / 2.0)), True


def _rolling_window_values(block: np.ndarray, m: int) -> np.ndarray:
    """
    Valor inteiro (MSB primeiro) de cada janela deslizante de `m` bits em
    `block`. Calculado por `m` operações vetoriais de shift/or — sem
    materializar a matriz `n x m` de janelas. Permite comparar TODOS os
    templates de comprimento `m` contra uma única varredura, em vez de uma
    varredura por template (ver `_non_overlapping_template_matching`).
    """
    n_windows = block.size - m + 1
    if n_windows <= 0:
        return np.empty(0, dtype=np.int64)
    values = np.zeros(n_windows, dtype=np.int64)
    for j in range(m):
        values = (values << 1) | block[j:j + n_windows].astype(np.int64)
    return values


@numba.njit
def _greedy_nonoverlapping_count(candidates: np.ndarray, m: int) -> int:
    """Percorre as posições candidatas (onde a janela casa com o template)
    aplicando a regra greedy do teste oficial: ao casar, pula `m` posições."""
    count = 0
    next_allowed = 0
    for idx in range(candidates.size):
        pos = candidates[idx]
        if pos >= next_allowed:
            count += 1
            next_allowed = pos + m
    return count


def _overlapping_pattern_counts(
    padded_bits: np.ndarray, block_size: int, n_positions: int
) -> np.ndarray:
    """
    Conta ocorrências de cada valor de padrão de `block_size` bits nas
    primeiras `n_positions` posições de sobreposição de `padded_bits` (que
    já deve ter padding suficiente para as janelas não estourarem o array).
    Vetorizado via `sliding_window_view` + produto escalar de pesos binários
    + `np.bincount` — mesma técnica de `bitblock.py`. Usado por Approximate
    Entropy e Serial (ver ponto 3a do docstring do módulo).
    """
    windows = np.lib.stride_tricks.sliding_window_view(padded_bits, block_size)[:n_positions]
    weights = (1 << np.arange(block_size - 1, -1, -1)).astype(np.int64)
    values = windows.astype(np.int64) @ weights
    return np.bincount(values, minlength=2 ** block_size)


def _approximate_entropy_vectorized(bits: np.ndarray) -> float:
    """
    Reimplementação vetorizada de Approximate Entropy (ver ponto 3a do
    docstring do módulo) — validada bit-a-bit idêntica ao `nistrng`
    original antes da troca.

    **m = 2, SEMPRE — e não por escolha do n.** A expressão do `nistrng`,
    `min(2, max(3, floor(log2(n)) − 6))`, é malformada: `max(3, ·)` nunca
    é menor que 3, então `min(2, ·)` devolve 2 para QUALQUER entrada. Não
    é "na prática sempre 2 para n realista" (como esta nota dizia antes da
    auditoria de 2026-08-24) — é estruturalmente impossível dar outra
    coisa. A SP 800-22 §2.12 permitiria m até ~13 para n≈524k
    (recomendação: m < log2(n) − 5), então m=2 custa sensibilidade.

    **Decisão: manter m=2** — é o que o `nistrng` computa, é o que já foi
    validado bit-a-bit, e mudar agora tornaria a feature incomparável com
    qualquer resultado anterior. Mas fica registrado como escolha
    consciente, não como consequência de uma fórmula que ninguém leu:
    `_APEN_BLOCK_LEN` abaixo é literal, sem a aritmética enganosa. Se o
    Nycolas quiser mais sensibilidade, é só subir a constante — o resto do
    código já é paramétrico nela.
    """
    n = bits.size
    blocks_length = _APEN_BLOCK_LEN
    phi_m = []
    for iteration in (blocks_length, blocks_length + 1):
        padded = np.concatenate((bits, bits[0:iteration - 1]))
        counts = _overlapping_pattern_counts(padded, iteration, n)
        c_i = counts / float(n)
        nz = c_i[c_i > 0]
        phi_m.append(float(np.sum(nz * np.log(nz))))
    chi_square = 2 * n * (math.log(2) - (phi_m[0] - phi_m[1]))
    dof = 2 ** (blocks_length - 1)
    return float(scipy.special.gammaincc(dof, chi_square / 2.0))


def _serial_vectorized(bits: np.ndarray) -> tuple[float, float] | None:
    """
    Reimplementação vetorizada de Serial (ver ponto 3a do docstring do
    módulo) — validada bit-a-bit idêntica ao `nistrng` original antes da
    troca. `pattern_length=4` é o default fixo do pacote. Retorna None se
    inelegível (mesma checagem de `SerialTest.is_eligible`).
    """
    n = bits.size
    pattern_length = 4
    if int(math.floor(math.log(n, 2))) - 2 < 4:
        return None
    padded = np.concatenate((bits, bits[0:pattern_length - 1]))

    def psi_sq(block_size: int) -> float:
        counts = _overlapping_pattern_counts(padded, block_size, n)
        return float(np.sum(counts.astype(float) ** 2)) * (2.0 ** block_size) / n - n

    psi_m0 = psi_sq(pattern_length)
    psi_m1 = psi_sq(pattern_length - 1)
    psi_m2 = psi_sq(pattern_length - 2)
    delta_1 = psi_m0 - psi_m1
    delta_2 = psi_m0 - (2 * psi_m1) + psi_m2
    score_1 = float(scipy.special.gammaincc(2 ** (pattern_length - 2), delta_1 / 2.0))
    score_2 = float(scipy.special.gammaincc(2 ** (pattern_length - 3), delta_2 / 2.0))
    return score_1, score_2


def _ticket_to_bucket(ticket: float) -> int:
    """
    Classifica um "ticket" (estatística por bloco) do teste de Complexidade
    Linear em uma das 7 classes C0..C6, pelas fronteiras exatas do SP
    800-22 §2.10 (intervalos semi-abertos: limite superior incluído,
    inferior não). Ver ponto 5 do docstring do módulo — `nistrng` usa
    `int(max(-2.5, ticket) + 2.5)`, que trunca em vez de respeitar essas
    fronteiras e classifica ~60% dos valores na classe errada (confirmado
    por comparação em 100k pontos aleatórios).
    """
    if ticket <= -2.5:
        return 0
    if ticket <= -1.5:
        return 1
    if ticket <= -0.5:
        return 2
    if ticket <= 0.5:
        return 3
    if ticket <= 1.5:
        return 4
    if ticket <= 2.5:
        return 5
    return 6


@numba.njit
def _berlekamp_massey_numba(sequence: np.ndarray) -> int:
    """
    Complexidade linear via Berlekamp-Massey, compilado com numba —
    mesmo algoritmo de `LinearComplexityTest._berlekamp_massey` do
    `nistrng` (que é lento, ~44s/amostra para os 1024 blocos de uma
    amostra de 64KB — inviável em 180k amostras), cross-validado idêntico
    em 50 sequências aleatórias contra uma reimplementação de referência
    antes da troca (ver `tests/test_nist_sts.py`). ~400x mais rápido após
    o aquecimento do JIT.
    """
    n = sequence.size
    b = np.zeros(n, dtype=np.int64)
    c = np.zeros(n, dtype=np.int64)
    b[0] = 1
    c[0] = 1
    generator_length = 0
    m = -1
    nn = 0
    while nn < n:
        discrepancy = sequence[nn]
        for j in range(1, generator_length + 1):
            discrepancy = discrepancy ^ (c[j] & sequence[nn - j])
        if discrepancy != 0:
            t = c.copy()
            for j in range(0, n - nn + m):
                c[nn - m + j] = c[nn - m + j] ^ b[j]
            if generator_length <= nn / 2:
                generator_length = nn + 1 - generator_length
                m = nn
                b = t
        nn += 1
    return generator_length


def _linear_complexity_vectorized(bits: np.ndarray) -> float:
    """
    Reimplementação de Complexidade Linear com o bucketing corrigido (ver
    `_ticket_to_bucket` e ponto 5 do docstring do módulo) e Berlekamp-Massey
    acelerado por numba (ver `_berlekamp_massey_numba`).
    """
    pattern_length = 512
    freedom_degrees = 6
    probabilities = np.array([0.010417, 0.03125, 0.125, 0.5, 0.25, 0.0625, 0.020833])
    mu = (
        (pattern_length / 2.0)
        + (((-1) ** (pattern_length + 1)) + 9.0) / 36.0
        - ((pattern_length / 3.0) + (2.0 / 9.0)) / (2 ** pattern_length)
    )

    n_blocks = bits.size // pattern_length
    lc = np.zeros(n_blocks, dtype=int)
    for i in range(n_blocks):
        block = bits[i * pattern_length:(i + 1) * pattern_length].astype(np.int64)
        lc[i] = _berlekamp_massey_numba(block)

    tickets = ((-1.0) ** pattern_length) * (lc - mu) + (2.0 / 9.0)
    frequencies = np.zeros(freedom_degrees + 1, dtype=int)
    for t in tickets:
        frequencies[_ticket_to_bucket(float(t))] += 1

    chi_square = float(
        np.sum(((frequencies - (n_blocks * probabilities)) ** 2) / (n_blocks * probabilities))
    )
    return float(scipy.special.gammaincc(freedom_degrees / 2.0, chi_square / 2.0))


def _count_cycles(bits: np.ndarray) -> int:
    """Nº de ciclos (cruzamentos por zero) do passeio aleatório acumulado — mesma
    lógica de random_excursion(_variant), duplicada aqui só para o critério de
    elegibilidade J>=500 (o pacote não implementa esse corte)."""
    signed = np.where(bits == 0, -1, 1)
    sum_prime = np.concatenate(([0], np.cumsum(signed), [0]))
    return int(np.count_nonzero(sum_prime[1:] == 0))


def _count_nonoverlapping_matches(block: np.ndarray, template: np.ndarray) -> int:
    """
    Conta ocorrências não-sobrepostas de `template` em `block` (mesma
    semântica greedy do teste oficial: ao casar, pula `m` posições; senão
    avança 1). Vetorizado: a varredura "casa em cada posição" usa
    `sliding_window_view` (numpy, sem loop Python); só o passo greedy final
    itera — e apenas sobre as posições CANDIDATAS (onde há match), não
    sobre todas as `len(block)-m+1` posições. Como casamentos são raros em
    dados pseudo-aleatórios (~1/2^m das posições), isso é ordens de
    magnitude mais rápido que o loop posição-a-posição original do
    nistrng, sem mudar o resultado.
    """
    m = template.size
    if block.size < m:
        return 0
    values = _rolling_window_values(block, m)
    candidates = np.flatnonzero(values == _template_to_int(template))
    return _greedy_nonoverlapping_count(candidates, m)


def _non_overlapping_template_matching(bits: np.ndarray) -> tuple[float, float, float]:
    """
    Reimplementação determinística e vetorizada: agrega TODOS os templates
    de comprimento 2-8 do nistrng (158 no total: 2+4+6+12+20+40+74 por
    comprimento — contado do inventário real, não do número redondo que
    a literatura costuma citar), em vez de sortear 1 (ver
    ponto 1 do docstring do módulo). Mesma lógica de blocos/chi² do teste
    original.

    **Otimização (2026-08-22):** o valor inteiro de cada janela deslizante
    é calculado UMA VEZ por (comprimento m, bloco) — 7 comprimentos x 8
    blocos = 56 varreduras — e reaproveitado por todos os templates
    daquele comprimento, em vez de uma varredura de comparação por
    template (158 varreduras, cada uma materializando uma matriz booleana
    `n x m`). Reduziu esta função de ~2,13s para uma fração disso por
    amostra de 64KB, sem mudar o resultado (validado contra a versão
    anterior). Era o maior custo isolado da suíte NIST.

    Returns:
        (p_mean, p_std, p_min) sobre os 158 templates.
    """
    blocks_number = 8
    substring_len = bits.size // blocks_number
    if substring_len < 2:
        return _NAN, _NAN, _NAN

    blocks = [
        bits[i * substring_len:(i + 1) * substring_len] for i in range(blocks_number)
    ]

    p_values: list[float] = []
    for m in sorted(_NOTM_TEMPLATES_BY_LEN):
        if substring_len <= m:
            continue
        mu = (substring_len - m + 1) / (2.0 ** m)
        sigma = substring_len * ((1.0 / (2.0 ** m)) - ((2.0 * m - 1) / (2.0 ** (2 * m))))
        if sigma <= 0:
            continue
        values_per_block = [_rolling_window_values(block, m) for block in blocks]
        for template_int in _NOTM_TEMPLATES_BY_LEN[m]:
            matches = np.zeros(blocks_number, dtype=np.int64)
            for i, values in enumerate(values_per_block):
                candidates = np.flatnonzero(values == template_int)
                matches[i] = _greedy_nonoverlapping_count(candidates, m)
            chi_square = float(np.sum(((matches - mu) ** 2) / sigma))
            p_values.append(
                float(scipy.special.gammaincc(blocks_number / 2.0, chi_square / 2.0))
            )

    if not p_values:
        return _NAN, _NAN, _NAN
    arr = np.array(p_values)
    return float(arr.mean()), float(arr.std()), float(arr.min())


def _cycles_from_bits(bits: np.ndarray) -> tuple[list[np.ndarray], int]:
    """Ciclos da caminhada aleatória (S' com zeros nas pontas). Compartilhado
    por Random Excursion e sua Variant."""
    signed = np.where(bits == 0, -1, 1)
    s_linha = np.concatenate(([0], np.cumsum(signed), [0]))
    zeros = np.flatnonzero(s_linha == 0)
    cycles = [s_linha[zeros[i]:zeros[i + 1] + 1] for i in range(len(zeros) - 1)]
    return cycles, len(cycles)


def _excursion_pi(x: int) -> list[float]:
    """
    Probabilidades π_k(x), k=0..5, da SP 800-22 §2.14 — calculadas pela
    fórmula fechada em vez de tabeladas:

        π_0 = 1 − 1/(2|x|)
        π_k = (1/(4x²))·(1 − 1/(2|x|))^(k−1)   , k = 1..4
        π_5 = (1/(2|x|))·(1 − 1/(2|x|))^4
    """
    a = abs(x)
    p0 = 1.0 - 1.0 / (2.0 * a)
    pis = [p0]
    pis += [(1.0 / (4.0 * a * a)) * (p0 ** (k - 1)) for k in range(1, 5)]
    pis.append((1.0 / (2.0 * a)) * (p0 ** 4))
    return pis


def _random_excursion_fixed(bits: np.ndarray) -> np.ndarray:
    """
    Random Excursion (NÃO a Variant) reimplementado — SP 800-22 §2.14.

    **[CRÍTICO] Bug do nistrng (achado em 2026-08-23):** a contagem de
    buckets do pacote é

        if 5 > k == occurrences: count += 1
        elif occurrences >= 5:   count += 1

    O `elif` dispara para TODO k de 0 a 5, então **todo ciclo com ≥5
    visitas ao estado é contado nos seis buckets ao mesmo tempo**. O χ²
    explode e o p-value colapsa para 0,0 exato em qualquer sequência —
    inclusive uniforme. Confirmado: numa sequência aleatória de 524.416
    bits com J=1932 ciclos, o pacote devolve `[0,0,0,0,0,0,0,0]` enquanto
    a especificação devolve p-values sensatos (0,017 a 0,913).

    Sem esta correção, as duas features do teste (`nist_excursions_mean`
    e `_min`) eram função determinística da flag `nist_excursions_valid`
    — 3 features carregando 1 bit, e esse bit é "J≥500", não o resultado
    do teste. Na dissertação viraria "o teste Random Excursion rejeita
    aleatoriedade em TODO criptograma", que é o bug, não o achado.

    Returns:
        p-values dos 8 estados x ∈ {−4..−1, 1..4}; vazio se não há ciclos.
    """
    cycles, j = _cycles_from_bits(bits)
    if j == 0:
        return np.array([])
    scores = []
    for x in (-4, -3, -2, -1, 1, 2, 3, 4):
        v_k = [0] * 6
        for cycle in cycles:
            k = int(np.count_nonzero(cycle == x))
            v_k[min(k, 5)] += 1            # cada ciclo conta em UM bucket só
        pi = _excursion_pi(x)
        chi_square = sum(
            ((v_k[k] - j * pi[k]) ** 2) / (j * pi[k]) for k in range(6)
        )
        scores.append(float(scipy.special.gammaincc(2.5, chi_square / 2.0)))
    return np.array(scores)


def _maurers_universal_fixed(bits: np.ndarray) -> tuple[float, bool]:
    """
    Maurer's Universal Statistical Test reimplementado — SP 800-22 §2.9.

    **[CRÍTICO] Bug do nistrng (achado em 2026-08-23):** o desvio padrão
    usado no denominador é `sqrt(variance(L))`, quando a especificação
    (§2.9.4 passo 5) manda

        σ = c · sqrt( variance(L) / K )
        c = 0,7 − 0,8/L + (4 + 32/L)·K^(−3/L)/15

    Faltam o fator de correção `c` E a divisão por √K — o denominador sai
    ~518x maior que o correto e o p-value é empurrado para perto de 1 em
    qualquer entrada. Medido num CT de 64KB (524.416 bits), com o L que a
    §2.9.5 manda para essa faixa de n — **L=6**, K=86.762, c=0,5688:
    denominador 2,500 contra 0,00483 (razão 517,9x); p-value 0,99951
    (pacote) contra 0,75268 (especificação).

    **Cuidado com o L:** a primeira versão desta nota citava c=0,5904,
    K=73.636 e "~460x" — são os valores de **L=7**, que é a faixa a
    partir de 904.960 bits, não a nossa. O CÓDIGO sempre escolheu L=6
    corretamente; era só a documentação que estava no L errado (e uma
    verificação escrita com L=7 chega a acusar divergência falsa).

    Como é transformação monótona de |fn − EV|, RF/XGBoost são
    invariantes — mas LinearSVC/SVM/LR sofrem, e a AFIRMAÇÃO quebra: a
    feature não é o p-value do teste Universal de Maurer. Mesma classe do
    erro de √2 do Random Excursions Variant, com fator ~460 em vez de
    1,41.

    Returns:
        (p_value, elegivel)
    """
    n = int(bits.size)
    # Tabela da §2.9.5: L em função de n. Só as faixas alcançáveis aqui.
    if n < 387_840:
        return _NAN, False
    if n < 904_960:
        block_len = 6
    elif n < 2_068_480:
        block_len = 7
    else:
        block_len = 8

    q = 10 * (2 ** block_len)
    k = n // block_len - q
    if k <= 0:
        return _NAN, False

    expected = {6: 5.2177052, 7: 6.1962507, 8: 7.1836656}[block_len]
    variance = {6: 2.954, 7: 3.125, 8: 3.238}[block_len]

    # Valores inteiros de cada bloco de L bits (vetorizado).
    usable = (q + k) * block_len
    blocks = bits[:usable].reshape(-1, block_len).astype(np.int64)
    weights = (1 << np.arange(block_len - 1, -1, -1)).astype(np.int64)
    values = blocks @ weights

    # Inicialização em laço explícito: `table[values[:q]] = arange(...)` é
    # atribuição com índices REPETIDOS, e o numpy não garante qual vence
    # nesse caso (a especificação exige o ÚLTIMO). Q é 1.280 para L=7 —
    # o laço custa nada e é determinístico.
    table = np.zeros(2 ** block_len, dtype=np.int64)
    for i in range(q):
        table[int(values[i])] = i + 1
    total = 0.0
    for i in range(q, q + k):
        v = int(values[i])
        total += math.log2((i + 1) - table[v])
        table[v] = i + 1
    fn = total / k

    c = 0.7 - 0.8 / block_len + (4.0 + 32.0 / block_len) * (k ** (-3.0 / block_len)) / 15.0
    sigma = c * math.sqrt(variance / k)
    p_value = math.erfc(abs(fn - expected) / (math.sqrt(2.0) * sigma))
    return float(p_value), True


def _random_excursion_variant_fixed(bits: np.ndarray) -> np.ndarray:
    """
    Reimplementação com o `erfc` que falta no nistrng (ver ponto 2 do
    docstring do módulo). Mesma lógica de ciclos/estados do original.

    **Fórmula (SP 800-22 Rev 1a §2.15.4, passo 6):**

        P-value = erfc( |ξ − J| / sqrt(2·J·(4·|x| − 2)) )

    **Correção de 2026-08-23:** esta função aplicava `erfc(z / sqrt(2))`
    com `z` JÁ dividido pelo denominador da especificação — ou seja,
    inseria o fator √2 uma segunda vez. Confirmado em CT real do v2:
    recuperando o argumento do erfc por inversão, a razão entre a versão
    antiga e a especificação era exatamente 0,707107 = 1/√2 nos 18
    estados. Efeito prático era contido (transformação monótona aplicada
    igualmente a todas as amostras — RF/XGBoost são invariantes), mas
    quebrava a AFIRMAÇÃO: duas das 641 features seriam reportadas como
    p-values do Random Excursions Variant da SP 800-22 sem o serem, e
    modelos sensíveis a escala (LinearSVC/SVM/LR) sofriam efeito real.

    Ironia registrada: a função existe para corrigir um `erfc` faltante
    no `nistrng`, e a correção passou do ponto. É exatamente o tipo de
    erro que o teste antigo (`0 < p <= 1`) não podia pegar — daí o teste
    de recomputação independente em `test_nist_sts.py`.
    """
    signed = np.where(bits == 0, -1, 1)
    sum_prime = np.concatenate(([0], np.cumsum(signed), [0])).astype(int)
    cycles_size = int(np.count_nonzero(sum_prime[1:] == 0))
    if cycles_size == 0:
        return np.array([])
    # Os 18 estados x ∈ {−9..−1, 1..9} são FIXOS pela especificação. Iterar
    # sobre `np.unique(...)` — como a versão anterior fazia — omitia um
    # estado nunca visitado em vez de deixá-lo contribuir com ξ=0, o que
    # mudaria o nº de p-values devolvidos e, portanto, a média/mínimo
    # agregados. Latente com J≥500 (todos os estados costumam ser
    # visitados), mas é desvio da especificação; corrigido em 2026-08-24.
    restricted = sum_prime[np.abs(sum_prime) < 10]
    counts_by_state = collections.Counter(int(v) for v in restricted)
    scores = []
    for state in (*range(-9, 0), *range(1, 10)):
        xi = counts_by_state.get(state, 0)          # 0 se nunca visitado
        # `denom` JÁ é o sqrt(2·J·(4|x|−2)) da especificação — o erfc recebe
        # o quociente direto, sem nenhuma divisão adicional por sqrt(2).
        denom = math.sqrt(2.0 * cycles_size * ((4.0 * abs(state)) - 2.0))
        scores.append(math.erfc(abs(xi - cycles_size) / denom))
    return np.array(scores)


def extract_nist_sts(ct: bytes) -> dict[str, float]:
    """Extrai as 15 estatísticas da suíte NIST SP 800-22 Rev.1a.

    Args:
        ct: ciphertext como bytes.

    Returns:
        dict com prefixo `nist_` — um p-value (ou estatística agregada) por
        teste, mais flags `_valid` (0/1) para os três testes que podem ser
        estruturalmente inaplicáveis nesta escala de CT (linear complexity,
        overlapping template, excursões — ver docstring do módulo).
    """
    if len(ct) < 32:
        # Sequência curta demais para qualquer teste ter sentido — todos NaN.
        keys = _feature_keys()
        return dict.fromkeys(keys, _NAN)

    bits = _bits_from_ct(ct)
    out: dict[str, float] = {}

    # --- testes de score único, direto do battery -------------------------
    for feat_name, battery_name in (
        ("nist_monobit", "monobit"),
        ("nist_frequency_within_block", "frequency_within_block"),
        ("nist_runs", "runs"),
        ("nist_longest_run_ones", "longest_run_ones_in_a_block"),
        ("nist_dft", "dft"),
    ):
        p, _ = _single_score(battery_name, bits)
        out[feat_name] = p

    # --- maurers universal (reimplementado — ver `_maurers_universal_fixed`)
    maurer_p, _ = _maurers_universal_fixed(bits)
    out["nist_maurers_universal"] = maurer_p

    # --- binary matrix rank (numba — ver `_binary_matrix_rank_fast`) -------
    rank_p, _ = _binary_matrix_rank_fast(bits)
    out["nist_binary_matrix_rank"] = rank_p

    # --- approximate entropy (reimplementado, vetorizado — ver ponto 3a) ---
    out["nist_approximate_entropy"] = _approximate_entropy_vectorized(bits)

    # --- serial (2 p-values; reimplementado, vetorizado — ver ponto 3a) ----
    serial_result = _serial_vectorized(bits)
    if serial_result is not None:
        out["nist_serial_1"], out["nist_serial_2"] = serial_result
    else:
        out["nist_serial_1"] = _NAN
        out["nist_serial_2"] = _NAN

    # --- cumulative sums (forward/backward) --------------------------------
    scores, elig = _multi_score("cumulative sums", bits)
    out["nist_cusum_forward"] = float(scores[0]) if elig and len(scores) > 0 else _NAN
    out["nist_cusum_backward"] = float(scores[1]) if elig and len(scores) > 1 else _NAN

    # --- non-overlapping template matching (reimplementado, determinístico) --
    p_mean, p_std, p_min = _non_overlapping_template_matching(bits)
    out["nist_nonoverlapping_template_mean"] = p_mean
    out["nist_nonoverlapping_template_std"] = p_std
    out["nist_nonoverlapping_template_min"] = p_min

    # --- overlapping template matching (estruturalmente inelegível em 64KB) --
    test = _battery["overlapping_template_matching"]
    if test.is_eligible(bits):
        result, _ = test.run(bits.copy())  # copy: ver nota de mutação em _single_score
        out["nist_overlapping_template"] = float(result.score)
        out["nist_overlapping_template_valid"] = 1.0
    else:
        out["nist_overlapping_template"] = _NEUTRAL_P
        out["nist_overlapping_template_valid"] = 0.0

    # --- linear complexity (eligibilidade relaxada — ver ponto 4; bucketing
    # corrigido — ver ponto 5) -----------------------------------------------
    n_blocks = bits.size // 512
    if n_blocks >= 1:
        out["nist_linear_complexity"] = _linear_complexity_vectorized(bits)
        out["nist_linear_complexity_valid"] = 1.0
    else:
        out["nist_linear_complexity"] = _NEUTRAL_P
        out["nist_linear_complexity_valid"] = 0.0

    # --- random excursion (8 estados) --------------------------------------
    n_cycles = _count_cycles(bits)
    if n_cycles >= _MIN_CYCLES_FOR_EXCURSIONS:
        scores = _random_excursion_fixed(bits)
        elig = len(scores) > 0
        if elig and len(scores) > 0:
            out["nist_excursions_mean"] = float(np.mean(scores))
            out["nist_excursions_min"] = float(np.min(scores))
            out["nist_excursions_valid"] = 1.0
        else:
            out["nist_excursions_mean"] = _NEUTRAL_P
            out["nist_excursions_min"] = _NEUTRAL_P
            out["nist_excursions_valid"] = 0.0
    else:
        out["nist_excursions_mean"] = _NEUTRAL_P
        out["nist_excursions_min"] = _NEUTRAL_P
        out["nist_excursions_valid"] = 0.0

    # --- random excursion variant (reimplementado com erfc corrigido) ------
    if n_cycles >= _MIN_CYCLES_FOR_EXCURSIONS:
        scores = _random_excursion_variant_fixed(bits)
        if len(scores) > 0:
            out["nist_excursions_variant_mean"] = float(np.mean(scores))
            out["nist_excursions_variant_min"] = float(np.min(scores))
            out["nist_excursions_variant_valid"] = 1.0
        else:
            out["nist_excursions_variant_mean"] = _NEUTRAL_P
            out["nist_excursions_variant_min"] = _NEUTRAL_P
            out["nist_excursions_variant_valid"] = 0.0
    else:
        out["nist_excursions_variant_mean"] = _NEUTRAL_P
        out["nist_excursions_variant_min"] = _NEUTRAL_P
        out["nist_excursions_variant_valid"] = 0.0

    return out


def _feature_keys() -> list[str]:
    """Lista fixa de chaves produzidas (para o caso de CT curto demais)."""
    return [
        "nist_monobit", "nist_frequency_within_block", "nist_runs",
        "nist_longest_run_ones", "nist_binary_matrix_rank", "nist_dft",
        "nist_maurers_universal", "nist_approximate_entropy",
        "nist_serial_1", "nist_serial_2",
        "nist_cusum_forward", "nist_cusum_backward",
        "nist_nonoverlapping_template_mean", "nist_nonoverlapping_template_std",
        "nist_nonoverlapping_template_min",
        "nist_overlapping_template", "nist_overlapping_template_valid",
        "nist_linear_complexity", "nist_linear_complexity_valid",
        "nist_excursions_mean", "nist_excursions_min", "nist_excursions_valid",
        "nist_excursions_variant_mean", "nist_excursions_variant_min",
        "nist_excursions_variant_valid",
    ]
