"""
Testes pytest para src/crypto/ctr_drbg.py.

Execução:
    pytest tests/test_ctr_drbg.py -v

Cobertura:
    - Determinismo: mesma seed -> mesma sequência
    - Seeds diferentes -> sequências diferentes
    - Tamanhos de saída corretos (generate/random_key)
    - Fatiamento automático acima do limite de 65.536 bytes/request
    - randint: limites respeitados + sem viés grosseiro (checagem estatística)
    - choice_bool: proporção aproximada da probabilidade pedida
    - Validação CAVP (NIST SP 800-90A DRBGVS, AES-128 no df): ver
      test_cavp_vectors, marcado xfail/skip até os vetores oficiais serem
      adicionados em tests/vectors/ (pendência registrada em
      docs/plano_experimento_v2/06_implementacao_passo_a_passo.md Fase 1.2).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.crypto.ctr_drbg import (
    BLOCKLEN,
    KEYLEN,
    MAX_BYTES_PER_REQUEST,
    SEEDLEN,
    CTRDRBG,
    CTRDRBGCore,
    CTRDRBGError,
    _ctr_drbg_update,
    _increment_counter,
)

_CAVP_VECTORS_PATH = Path(__file__).parent / "vectors" / "ctr_drbg_aes128_nodf.json"


# ---------------------------------------------------------------------------
# Determinismo e independência de seed
# ---------------------------------------------------------------------------
def test_same_seed_same_sequence():
    a = CTRDRBG(seed=42)
    b = CTRDRBG(seed=42)
    assert a.generate(64) == b.generate(64)


def test_different_seed_different_sequence():
    a = CTRDRBG(seed=42)
    b = CTRDRBG(seed=43)
    assert a.generate(64) != b.generate(64)


def test_different_label_different_sequence():
    a = CTRDRBG(seed=42, label="chaves")
    b = CTRDRBG(seed=42, label="plaintext")
    assert a.generate(64) != b.generate(64)


def test_successive_generate_calls_differ():
    drbg = CTRDRBG(seed=42)
    first = drbg.generate(32)
    second = drbg.generate(32)
    assert first != second


# ---------------------------------------------------------------------------
# Tamanhos de saída
# ---------------------------------------------------------------------------
def test_generate_output_length():
    drbg = CTRDRBG(seed=1)
    assert len(drbg.generate(1)) == 1
    assert len(drbg.generate(16)) == 16
    assert len(drbg.generate(1000)) == 1000


def test_random_key_default_length():
    drbg = CTRDRBG(seed=1)
    assert len(drbg.random_key()) == 16
    assert len(drbg.random_key(32)) == 32


def test_generate_rejects_non_positive():
    drbg = CTRDRBG(seed=1)
    with pytest.raises(CTRDRBGError):
        drbg.generate(0)
    with pytest.raises(CTRDRBGError):
        drbg.generate(-1)


# ---------------------------------------------------------------------------
# Fatiamento acima do limite por request (65.536 bytes)
# ---------------------------------------------------------------------------
def test_generate_above_max_per_request_matches_manual_chunks():
    """
    generate(N) para N > MAX_BYTES_PER_REQUEST deve ser byte-a-byte igual a
    chamar o núcleo (CTRDRBGCore) manualmente em fatias de
    MAX_BYTES_PER_REQUEST, na mesma ordem — prova que o fatiamento automático
    da camada de alto nível não reordena nem perde bytes.
    """
    n = MAX_BYTES_PER_REQUEST + 1000
    drbg = CTRDRBG(seed=7)
    combined = drbg.generate(n)
    assert len(combined) == n

    # Reconstrução manual com uma instância separada e mesma seed/label.
    drbg2 = CTRDRBG(seed=7)
    manual = drbg2._core.generate(MAX_BYTES_PER_REQUEST) + drbg2._core.generate(1000)
    assert combined == manual


def test_core_generate_rejects_above_max_per_request():
    core = CTRDRBGCore(entropy_input=b"\x00" * SEEDLEN)
    with pytest.raises(CTRDRBGError):
        core.generate(MAX_BYTES_PER_REQUEST + 1)


# ---------------------------------------------------------------------------
# randint
# ---------------------------------------------------------------------------
def test_randint_respects_bounds():
    drbg = CTRDRBG(seed=5)
    for _ in range(500):
        v = drbg.randint(10, 20)
        assert 10 <= v < 20


def test_randint_single_value_range():
    drbg = CTRDRBG(seed=5)
    assert drbg.randint(3, 4) == 3


def test_randint_rejects_invalid_range():
    drbg = CTRDRBG(seed=5)
    with pytest.raises(CTRDRBGError):
        drbg.randint(5, 5)
    with pytest.raises(CTRDRBGError):
        drbg.randint(5, 4)


def test_randint_roughly_uniform_no_gross_bias():
    """Checagem grosseira (não estatisticamente rigorosa): sobre um range
    pequeno e muitas amostras, cada valor deve aparecer com frequência
    plausível — detecta bugs óbvios de viés/off-by-one, não substitui os
    testes NIST SP 800-22 (esses validam os wrappers AEAD, não este PRNG)."""
    drbg = CTRDRBG(seed=99)
    counts = [0] * 7
    n = 7000
    for _ in range(n):
        counts[drbg.randint(0, 7)] += 1
    expected = n / 7
    for c in counts:
        assert 0.5 * expected < c < 1.5 * expected


# ---------------------------------------------------------------------------
# choice_bool
# ---------------------------------------------------------------------------
def test_choice_bool_extremes():
    drbg = CTRDRBG(seed=3)
    assert all(drbg.choice_bool(1.0) for _ in range(100))
    drbg2 = CTRDRBG(seed=3)
    assert not any(drbg2.choice_bool(0.0) for _ in range(100))


def test_choice_bool_approximate_proportion():
    drbg = CTRDRBG(seed=11)
    n = 5000
    true_count = sum(drbg.choice_bool(0.2) for _ in range(n))
    proportion = true_count / n
    assert 0.15 < proportion < 0.25


# ---------------------------------------------------------------------------
# Núcleo (CTRDRBGCore) — validação de forma/erros de entrada
# ---------------------------------------------------------------------------
def test_core_requires_exact_seedlen_entropy():
    with pytest.raises(CTRDRBGError):
        CTRDRBGCore(entropy_input=b"\x00" * (SEEDLEN - 1))
    with pytest.raises(CTRDRBGError):
        CTRDRBGCore(entropy_input=b"\x00" * (SEEDLEN + 1))


def test_core_deterministic_from_same_entropy():
    entropy = b"\x01" * SEEDLEN
    a = CTRDRBGCore(entropy_input=entropy)
    b = CTRDRBGCore(entropy_input=entropy)
    assert a.generate(48) == b.generate(48)


def test_increment_counter_wraps_at_max():
    max_v = b"\xff" * BLOCKLEN
    assert _increment_counter(max_v) == b"\x00" * BLOCKLEN


def test_update_requires_exact_seedlen_provided_data():
    key = b"\x00" * KEYLEN
    v = b"\x00" * BLOCKLEN
    with pytest.raises(CTRDRBGError):
        _ctr_drbg_update(key, v, b"\x00" * (SEEDLEN - 1))


# ---------------------------------------------------------------------------
# Validação CAVP (NIST SP 800-90A DRBGVS) — pendente de vetores oficiais
# ---------------------------------------------------------------------------
@pytest.mark.skipif(
    not _CAVP_VECTORS_PATH.exists(),
    reason=(
        "Vetores CAVP DRBGVS (AES-128 CTR_DRBG, no df) ainda não adicionados "
        f"em {_CAVP_VECTORS_PATH}. Pendência registrada na Fase 1.2 do plano "
        "de implementação — bloqueia a geração real do dataset v2 até ser "
        "resolvida."
    ),
)
def test_cavp_vectors():
    """
    Valida CTRDRBGCore byte-a-byte contra os vetores oficiais NIST CAVP
    (DRBGVS) para CTR_DRBG AES-128 sem função de derivação, sem resistência
    a predição. Formato esperado do JSON (uma lista de casos):
        {
          "entropy_input": "<hex, 32 bytes>",
          "personalization_string": "<hex, 0..32 bytes>",
          "entropy_input_reseed": "<hex, 32 bytes ou null>",
          "additional_input_reseed": "<hex ou null>",
          "additional_input_1": "<hex ou null>",
          "additional_input_2": "<hex ou null>",
          "returned_bits": "<hex>"
        }
    Cada caso: Instantiate -> [Reseed opcional] -> Generate (descartado) ->
    Generate (comparado com returned_bits), conforme layout padrão do CAVP.
    """
    cases = json.loads(_CAVP_VECTORS_PATH.read_text())
    assert cases, "arquivo de vetores está vazio"

    for i, case in enumerate(cases):
        core = CTRDRBGCore(
            entropy_input=bytes.fromhex(case["entropy_input"]),
            personalization_string=bytes.fromhex(
                case.get("personalization_string") or ""
            ),
        )
        if case.get("entropy_input_reseed"):
            core.reseed(
                entropy_input=bytes.fromhex(case["entropy_input_reseed"]),
                additional_input=bytes.fromhex(
                    case.get("additional_input_reseed") or ""
                ),
            )
        n_bytes = len(case["returned_bits"]) // 2
        core.generate(
            n_bytes, additional_input=bytes.fromhex(case.get("additional_input_1") or "")
        )
        result = core.generate(
            n_bytes, additional_input=bytes.fromhex(case.get("additional_input_2") or "")
        )
        expected = bytes.fromhex(case["returned_bits"])
        assert result == expected, f"vetor CAVP #{i} não bateu"
