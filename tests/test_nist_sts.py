"""
Testes pytest para src/features/families/nist_sts.py (suíte NIST SP 800-22).

Execução:
    pytest tests/test_nist_sts.py -v

Estratégia de validação: em vez de tentar recordar de memória os exemplos
numéricos oficiais do SP 800-22 (risco de citar mal um número "oficial" e
validar contra a própria memória errada), cada teste de maior risco é
cross-checado por uma REIMPLEMENTAÇÃO INDEPENDENTE da fórmula matemática
do padrão (não copiada do `nistrng`), ou por casos pequenos computáveis à
mão (LFSRs de complexidade linear conhecida, matrizes de posto conhecido).
Cobertura:
    - Monobit: fórmula erfc(|S_n|/sqrt(2n)) recomputada independentemente
    - Runs: contagem manual de runs cross-checada
    - Berlekamp-Massey (linear complexity): casos de LFSR conhecidos
    - Binary Matrix Rank: casos de matriz pequena + REGRESSÃO do bug de
      mutação in-place confirmado e corrigido nesta sessão
    - Determinismo: mesma entrada -> mesma saída (non-overlapping template,
      excursions variant, extract_nist_sts completo)
    - Elegibilidade/imputação: overlapping template sempre inválido em 64KB;
      linear complexity válido em 64KB; excursões inválidas com poucos ciclos
    - Forma/robustez: extract_nist_sts em CT curto, vazio, e no tamanho real
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from src.features.families.nist_sts import (
    _NEUTRAL_P,
    _count_cycles,
    _count_nonoverlapping_matches,
    _feature_keys,
    _non_overlapping_template_matching,
    _random_excursion_variant_fixed,
    _single_score,
    extract_nist_sts,
)


# ---------------------------------------------------------------------------
# Monobit — cross-check por fórmula independente
# ---------------------------------------------------------------------------
def test_monobit_matches_independent_formula():
    """P-value = erfc(|ones-zeros| / sqrt(2n)) — SP 800-22 §2.1, recomputado
    aqui do zero (não copiado do nistrng) para uma sequência arbitrária."""
    rng = np.random.default_rng(7)
    bits = rng.integers(0, 2, size=10_000).astype(np.int8)

    p_lib, elig = _single_score("monobit", bits)
    assert elig

    ones = int(np.count_nonzero(bits))
    zeros = bits.size - ones
    s_obs = abs(ones - zeros) / math.sqrt(bits.size)
    p_independent = math.erfc(s_obs / math.sqrt(2))

    assert p_lib == pytest.approx(p_independent, rel=1e-9)


def test_monobit_all_ones_gives_near_zero_pvalue():
    """Sequência totalmente enviesada (todos 1) deve reprovar (p muito baixo)."""
    bits = np.ones(1000, dtype=np.int8)
    p, elig = _single_score("monobit", bits)
    assert elig
    assert p < 1e-6


def test_monobit_perfectly_balanced_gives_pvalue_one():
    """ones == zeros -> S_obs=0 -> erfc(0)=1.0 exatamente."""
    bits = np.array(([0, 1] * 500), dtype=np.int8)
    p, elig = _single_score("monobit", bits)
    assert elig
    assert p == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Runs — contagem manual cross-checada
# ---------------------------------------------------------------------------
def test_runs_count_matches_manual_count():
    """O nº de runs (blocos de valores iguais consecutivos) usado pelo teste
    deve bater com uma contagem manual simples, independente da lib."""
    rng = np.random.default_rng(11)
    bits = rng.integers(0, 2, size=5000).astype(np.int8)

    manual_runs = 1 + int(np.sum(bits[1:] != bits[:-1]))

    # Reimplementação direta da fórmula do teste (SP 800-22 §2.3): se a
    # proporção de 1s foge muito de 0.5, o teste nem roda (pre-test da
    # Eq. 2.3); senão, p = erfc(|Vn - 2n*pi*(1-pi)| / (2*sqrt(2n)*pi*(1-pi))).
    n = bits.size
    pi = float(np.count_nonzero(bits)) / n
    tau = 2.0 / math.sqrt(n)
    if abs(pi - 0.5) >= tau:
        pytest.skip("pre-teste do runs falhou para esta amostra (esperado ocasionalmente)")
    v_n = manual_runs
    p_independent = math.erfc(
        abs(v_n - 2 * n * pi * (1 - pi)) / (2 * math.sqrt(2 * n) * pi * (1 - pi))
    )

    p_lib, elig = _single_score("runs", bits)
    assert elig
    assert p_lib == pytest.approx(p_independent, rel=1e-6)


# ---------------------------------------------------------------------------
# Berlekamp-Massey (linear complexity) — casos de LFSR conhecidos
# ---------------------------------------------------------------------------
def _berlekamp_massey_reference(bits: list[int]) -> int:
    """Reimplementação de referência do B-M, direta do algoritmo clássico
    (Massey 1969) — independente da versão usada por nistrng, para
    cross-check em sequências pequenas e conhecidas."""
    n = len(bits)
    c = [0] * n
    b = [0] * n
    c[0] = 1
    b[0] = 1
    l_ = 0
    m = -1
    for i in range(n):
        d = bits[i]
        for j in range(1, l_ + 1):
            d ^= c[j] & bits[i - j]
        if d == 1:
            t = c[:]
            for j in range(n - i + m):
                c[i - m + j] ^= b[j]
            if l_ <= i / 2:
                l_ = i + 1 - l_
                m = i
                b = t
    return l_


@pytest.mark.parametrize(
    "bits,expected_lc",
    [
        ([0] * 16, 0),                        # sequência nula: LC=0
        ([1] * 16, 1),                        # constante 1: LFSR de grau 1 (x_n = x_{n-1})
        ([1, 0] * 8, 2),                       # alternada: LFSR de grau 2
        ([1, 1, 0, 1, 0, 0, 1] * 3, 3),        # LFSR grau 3 (m-sequence, período 7 = 2^3-1)
    ],
)
def test_berlekamp_massey_known_lfsr_cases(bits, expected_lc):
    """Complexidade linear de sequências com LC conhecido por construção
    (todas puramente periódicas geradas por um LFSR do grau indicado —
    caso clássico onde a complexidade linear iguala o grau do LFSR)."""
    assert _berlekamp_massey_reference(bits) == expected_lc


def test_nistrng_berlekamp_massey_has_known_aliasing_bug():
    """
    REGRESSÃO/documentação: `LinearComplexityTest._berlekamp_massey` do
    nistrng faz `t = c[:]; b = t` — em NumPy, `array[:]` é uma VIEW, não
    cópia (ao contrário de lista Python), então escritas seguintes em `c`
    corrompem `b` retroativamente. Por isso NÃO é usada em produção neste
    módulo (ver `_berlekamp_massey_numba`, que usa `.copy()` de verdade).
    Este teste apenas documenta/trava o bug conhecido: se uma versão futura
    do pacote corrigir isso, o teste abaixo passará a falhar, sinalizando
    que `_berlekamp_massey_numba` pode voltar a ser cross-checada contra
    o pacote diretamente."""
    from nistrng.sp800_22r1a import LinearComplexityTest

    rng = np.random.default_rng(3)
    mismatches = 0
    for _ in range(20):
        bits_arr = rng.integers(0, 2, size=64)
        lib_lc = LinearComplexityTest._berlekamp_massey(bits_arr.astype(np.int8))
        ref_lc = _berlekamp_massey_reference(list(bits_arr))
        if lib_lc != ref_lc:
            mismatches += 1
    assert mismatches > 0, (
        "nistrng não divergiu mais da referência — bug de aliasing pode "
        "ter sido corrigido upstream; revisar se ainda é necessário usar "
        "_berlekamp_massey_numba em vez do pacote"
    )


def test_berlekamp_massey_numba_matches_independent_reference():
    """Cross-check: nossa versão numba (usada em produção) bate com a
    reimplementação de referência independente do algoritmo clássico de
    Massey — confiança de que a versão RÁPIDA usada no pipeline está
    correta (a versão do nistrng tem o bug de aliasing documentado acima e
    não é usada)."""
    from src.features.families.nist_sts import _berlekamp_massey_numba

    rng = np.random.default_rng(3)
    for _ in range(20):
        bits_arr = rng.integers(0, 2, size=64)
        numba_lc = int(_berlekamp_massey_numba(bits_arr.astype(np.int64)))
        ref_lc = _berlekamp_massey_reference(list(bits_arr))
        assert numba_lc == ref_lc


def test_ticket_to_bucket_matches_spec_boundaries():
    """Fronteiras exatas do SP 800-22 §2.10: limite superior incluído
    (<=), inferior não — cross-check contra `nistrng.int(max(-2.5,t)+2.5)`
    mostrando que elas DIVERGEM na maior parte do domínio (bug documentado
    no docstring do módulo), não coincidem por acaso em nenhum ponto
    interior às classes."""
    from src.features.families.nist_sts import _ticket_to_bucket

    # Pontos exatamente nas fronteiras: ambas as fórmulas devem concordar
    # (só o INTERIOR das classes diverge, porque nistrng trunca em vez de
    # respeitar o limite superior fechado).
    for boundary in (-2.5, -1.5, -0.5, 0.5, 1.5, 2.5):
        nistrng_style = min(6, int(max(-2.5, boundary) + 2.5))
        assert _ticket_to_bucket(boundary) == nistrng_style

    # Ponto central (ticket=0, o mais comum na prática): deve cair na
    # classe dominante C3 (índice 3, probabilidade 0.5), não C2.
    assert _ticket_to_bucket(0.0) == 3


def test_linear_complexity_chi_square_reasonable_on_random_data():
    """Antes da correção do bucketing, o χ² inflava para >1000 e o
    p-value colapsava para 0.0 sistematicamente em QUALQUER ciphertext,
    aleatório ou não — isso é a assinatura do bug, não de não-aleatoriedade.
    Numa amostra grande de dados genuinamente aleatórios, o p-value deve
    cair em uma faixa plausível a maior parte das vezes (não é um teste
    determinístico — usa uma margem generosa para não ser frágil)."""
    extreme_count = 0
    n_trials = 8
    for seed in range(n_trials):
        ct = bytes(np.random.default_rng(seed).integers(0, 256, size=65552, dtype=np.uint8))
        result = extract_nist_sts(ct)
        if result["nist_linear_complexity"] < 1e-6:
            extreme_count += 1
    # Sob H0 (dados realmente aleatórios), p<1e-6 deveria ser raríssimo;
    # toleramos até 1/8 para não tornar o teste frágil, mas o padrão do
    # bug (100% das amostras extremas) não deve mais aparecer.
    assert extreme_count <= 1, (
        f"{extreme_count}/{n_trials} amostras aleatórias deram p<1e-6 em "
        "linear_complexity — possível regressão do bug de bucketing"
    )


def test_linear_complexity_relaxed_eligibility_runs_at_64kb():
    """No CT real (524.416 bits), abaixo do mínimo recomendado pelo padrão
    (1e6 bits) mas com divisão exata em blocos de 512 — deve rodar (não
    ficar neutro/inválido), única exceção documentada de eligibilidade
    relaxada no módulo."""
    ct = bytes(np.random.default_rng(1).integers(0, 256, size=65552, dtype=np.uint8))
    result = extract_nist_sts(ct)
    assert result["nist_linear_complexity_valid"] == 1.0
    assert not math.isnan(result["nist_linear_complexity"])


# ---------------------------------------------------------------------------
# Binary Matrix Rank — casos pequenos + regressão do bug de mutação
# ---------------------------------------------------------------------------
def test_binary_matrix_rank_does_not_mutate_input():
    """REGRESSÃO: BinaryMatrix fazia eliminação gaussiana diretamente sobre
    a view do array de entrada, corrompendo `bits` para qualquer teste
    chamado depois (bug confirmado por inspeção nesta sessão — 7 outros
    testes retornavam p=0.0 de forma reprodutível após essa chamada).
    `_single_score` deve blindar contra isso passando sempre uma cópia."""
    rng = np.random.default_rng(5)
    bits = rng.integers(0, 2, size=524_416).astype(np.int8)
    bits_before = bits.copy()

    p, elig = _single_score("binary_matrix_rank", bits)
    assert elig

    assert np.array_equal(bits, bits_before), (
        "bits foi mutado por binary_matrix_rank — regressão do bug de "
        "corrupção in-place (BinaryMatrix._matrix = view, não cópia)"
    )


def test_extract_nist_sts_full_pipeline_does_not_corrupt_downstream_tests():
    """REGRESSÃO de ponta a ponta: roda a suíte completa e verifica que os
    testes que vêm DEPOIS do binary_matrix_rank na ordem de execução
    (dft, approximate_entropy, maurers_universal, serial, cumulative_sums,
    linear_complexity) não retornam o padrão de corrupção (p exatamente
    0.0 simultâneo, reprodutível, que caracterizava o bug)."""
    ct = bytes(np.random.default_rng(2).integers(0, 256, size=65552, dtype=np.uint8))
    r = extract_nist_sts(ct)
    suspect_keys = [
        "nist_dft", "nist_approximate_entropy", "nist_maurers_universal",
        "nist_serial_1", "nist_serial_2", "nist_cusum_forward", "nist_cusum_backward",
    ]
    # Não é impossível um p-value legítimo cair exatamente em 0.0 por
    # underflow isolado, mas TODOS os 7 simultaneamente em dados aleatórios
    # é a assinatura do bug corrigido nesta sessão — não deve mais ocorrer.
    n_zero = sum(1 for k in suspect_keys if r[k] == 0.0)
    assert n_zero < len(suspect_keys), (
        f"{n_zero}/{len(suspect_keys)} testes pós-binary_matrix_rank deram "
        "exatamente 0.0 simultaneamente — possível regressão do bug de mutação"
    )


def test_binary_matrix_rank_small_known_matrices():
    """Posto GF(2) de matrizes pequenas com posto conhecido à mão."""
    from nistrng.sp800_22r1a.test_binary_matrix_rank import BinaryMatrix

    # Matriz identidade 4x4 -> posto completo = 4
    identity = np.eye(4, dtype=int)
    rank = BinaryMatrix(identity.copy(), 4, 4).compute_rank()
    assert rank == 4

    # Matriz nula 4x4 -> posto 0
    zeros = np.zeros((4, 4), dtype=int)
    rank = BinaryMatrix(zeros.copy(), 4, 4).compute_rank()
    assert rank == 0

    # Duas linhas idênticas -> posto < nº de linhas (deficiente em pelo menos 1)
    dependent = np.array([[1, 0, 1, 0], [1, 0, 1, 0], [0, 1, 0, 1], [1, 1, 1, 1]])
    rank = BinaryMatrix(dependent.copy(), 4, 4).compute_rank()
    assert rank <= 3


# ---------------------------------------------------------------------------
# Non-overlapping template matching — determinismo + correção (ver também
# a verificação de 500 casos aleatórios feita interativamente nesta sessão)
# ---------------------------------------------------------------------------
def test_nonoverlapping_template_matching_deterministic():
    """Reimplementação própria deve ser 100% determinística (o bug original
    do nistrng usava random.choice sem seed) — mesma entrada, mesma saída,
    repetidas vezes."""
    rng = np.random.default_rng(9)
    bits = rng.integers(0, 2, size=8192).astype(np.int8)
    results = [_non_overlapping_template_matching(bits) for _ in range(5)]
    assert all(r == results[0] for r in results)


def test_count_nonoverlapping_matches_matches_naive_greedy():
    """Cross-check vetorizado vs. loop greedy posição-a-posição ingênuo
    (mesma lógica documentada no SP 800-22: casa -> pula m; senão avança 1)."""

    def naive(block, template):
        m = len(template)
        pos, count = 0, 0
        limit = len(block) - m + 1
        while pos < limit:
            if np.array_equal(block[pos:pos + m], template):
                pos += m
                count += 1
            else:
                pos += 1
        return count

    rng = np.random.default_rng(42)
    for _ in range(200):
        block_len = int(rng.integers(5, 300))
        m = int(rng.integers(2, 9))
        block = rng.integers(0, 2, size=block_len).astype(np.int8)
        template = rng.integers(0, 2, size=m).astype(np.uint8)
        assert _count_nonoverlapping_matches(block, template) == naive(block, template)


# ---------------------------------------------------------------------------
# Random excursion variant — erfc corrigido
# ---------------------------------------------------------------------------
def test_excursion_variant_scores_are_valid_pvalues():
    """Bug confirmado no nistrng: calcula o argumento de erfc mas não aplica
    erfc, então o "p-value" reportado era na verdade o próprio z-score (não
    limitado a [0,1]). A versão corrigida aqui deve sempre produzir valores
    em [0,1] (imagem de erfc para argumentos não-negativos é (0,2], mas
    como |arg|>=0 aqui, o resultado cai em (0,1])."""
    # Sequência artificial com caminhada longa o bastante pra gerar ciclos
    rng = np.random.default_rng(17)
    bits = rng.integers(0, 2, size=200_000).astype(np.int8)
    scores = _random_excursion_variant_fixed(bits)
    if len(scores) == 0:
        pytest.skip("nenhum ciclo suficiente nesta amostra (esperado ocasionalmente)")
    assert np.all(scores > 0.0)
    assert np.all(scores <= 1.0)


# ---------------------------------------------------------------------------
# Elegibilidade / imputação neutra
# ---------------------------------------------------------------------------
def test_overlapping_template_always_invalid_at_64kb():
    """Limitação estrutural documentada: precisa de >=1.028.016 bits;
    nosso CT de 64KB tem no máximo 524.416 — sempre inelegível."""
    ct = bytes(np.random.default_rng(4).integers(0, 256, size=65552, dtype=np.uint8))
    r = extract_nist_sts(ct)
    assert r["nist_overlapping_template_valid"] == 0.0
    assert r["nist_overlapping_template"] == _NEUTRAL_P


def test_excursions_invalid_when_few_cycles():
    """Sequência artificial monotônica (só 1s) não cruza o zero -> 0 ciclos
    -> deve ficar marcada inválida/neutra, nunca calcular um p-value real."""
    ct = bytes([0xFF] * 65552)  # todos 1s -> caminhada nunca retorna a 0
    r = extract_nist_sts(ct)
    assert r["nist_excursions_valid"] == 0.0
    assert r["nist_excursions_mean"] == _NEUTRAL_P
    assert r["nist_excursions_variant_valid"] == 0.0


def test_count_cycles_monotonic_sequence_only_counts_padding_closure():
    """Sequência que nunca retorna a zero naturalmente: a convenção do
    SP 800-22 (replicada de `nistrng`) fecha o passeio com um zero
    artificial ao final — sempre existe pelo menos esse "ciclo", mesmo
    sem nenhum cruzamento real. Por isso o critério de invalidação usa
    J < 500 (bem acima de 1), não J == 0."""
    bits = np.ones(10_000, dtype=np.int8)
    assert _count_cycles(bits) == 1


# ---------------------------------------------------------------------------
# Forma / robustez de extract_nist_sts
# ---------------------------------------------------------------------------
def test_extract_nist_sts_short_ct_returns_all_nan():
    result = extract_nist_sts(b"\x00" * 10)
    assert set(result.keys()) == set(_feature_keys())
    assert all(math.isnan(v) for v in result.values())


def test_extract_nist_sts_empty_ct_returns_all_nan():
    result = extract_nist_sts(b"")
    assert all(math.isnan(v) for v in result.values())


def test_extract_nist_sts_key_set_stable_across_sizes():
    """As mesmas chaves devem aparecer independente do tamanho do CT (a
    dimensão do vetor de features não pode variar por amostra)."""
    ct_small = bytes(range(256))
    ct_real = bytes(np.random.default_rng(6).integers(0, 256, size=65552, dtype=np.uint8))
    keys_small = set(extract_nist_sts(ct_small).keys())
    keys_real = set(extract_nist_sts(ct_real).keys())
    assert keys_small == keys_real == set(_feature_keys())


def test_extract_nist_sts_deterministic_full_pipeline():
    """Mesmo CT -> exatamente o mesmo dict de features, em chamadas repetidas."""
    ct = bytes(np.random.default_rng(8).integers(0, 256, size=65552, dtype=np.uint8))
    r1 = extract_nist_sts(ct)
    r2 = extract_nist_sts(ct)
    assert r1 == r2


def test_extract_nist_sts_grain_length_also_works():
    """CT do Grain-128AEAD (65.544 bytes, 8 a menos que os outros 3
    algoritmos) também deve produzir todas as chaves sem erro."""
    ct = bytes(np.random.default_rng(10).integers(0, 256, size=65544, dtype=np.uint8))
    r = extract_nist_sts(ct)
    assert set(r.keys()) == set(_feature_keys())
    assert r["nist_linear_complexity_valid"] == 1.0  # 524.352 / 512 = 1023.75 -> floor 1023 blocos, ainda roda
