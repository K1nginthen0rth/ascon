"""Família opcional: estatísticas alinhadas ao bloco nativo do modo.

Motivação (2026-09-11). As 12 famílias do v2 são marginais ou agregadas
sobre a mensagem inteira: histograma, entropia, momentos, peso de Hamming,
NIST SP 800-22, Welch. Autocorrelação e n-gramas têm alguma estrutura
relacional, mas agregada sobre os 64 KB, o que dilui estrutura de bloco.

O estudo de rodadas reduzidas (build/reduced_rounds/full/) mostrou que
mesmo Ascon com 1 de 8 rodadas de dados, ou GIFT-COFB com 5 de 40, não é
separável por essas features: F1 = 0,50 com IC apertado nas três configs
em escala completa. Redução de rodadas não estraga a distribuição marginal
(cada bloco continua sendo bijeção key-dependent de um estado que muda), ela
estraga a RELAÇÃO entre blocos e entre entradas relacionadas. Esta família
olha exatamente aí, mantendo o cenário ciphertext-only de amostra única.

Duas granularidades, porque os modos operam em duas: 16 bytes (128 bits —
bloco do GIFT-COFB, taxa do Ascon-AEAD128) e 8 bytes (64 bits — metades do
G do COFB, taxa do Ascon-128 não-'a').

NÃO entra em `_ALL_FAMILIES` (o conjunto padrão de 641 dimensões): tem que
ser pedida explicitamente via `CiphertextFeatureExtractor(families=[...])`.
Isso é deliberado — registrar por padrão mudaria a dimensão do vetor e
quebraria a comparabilidade com os parquets de features já extraídos.
"""
from __future__ import annotations

import numpy as np

_NAN = float("nan")
_BLOCK_SIZES = (8, 16)

# LUT de popcount por byte — mais rápido que np.unpackbits para arrays grandes.
_POPCOUNT = np.array([bin(i).count("1") for i in range(256)], dtype=np.uint8)


def _feature_names(b: int) -> list[str]:
    return [
        f"blk{b}_offset_entropy_std",
        f"blk{b}_offset_entropy_range",
        f"blk{b}_offset_chi2_mean",
        f"blk{b}_offset_chi2_std",
        f"blk{b}_hamming_consec_mean",
        f"blk{b}_hamming_consec_std",
        f"blk{b}_diff_entropy",
        f"blk{b}_diff_chi2",
        f"blk{b}_repeat_rate",
    ]


def _byte_entropy_and_chi2(counts: np.ndarray, n: int) -> tuple[float, float]:
    probs = counts / n
    nz = probs[probs > 0]
    entropy = float(-np.sum(nz * np.log2(nz)))
    expected = n / 256.0
    chi2 = float(np.sum((counts - expected) ** 2) / expected)
    return entropy, chi2


def _stats_for_block_size(arr: np.ndarray, b: int) -> dict[str, float]:
    n_blocks = arr.size // b
    if n_blocks < 2:
        return dict.fromkeys(_feature_names(b), _NAN)

    blocks = arr[: n_blocks * b].reshape(n_blocks, b)

    # (1) Viés por posição dentro do bloco: entropia/χ² da coluna j, para cada
    # j em 0..b-1, resumidos por dispersão. Um modo que trate posições de
    # forma desigual (rotação, padding, metade alta/baixa) aparece aqui e não
    # no histograma global, que soma todas as posições.
    entropies = np.empty(b, dtype=float)
    chi2s = np.empty(b, dtype=float)
    for j in range(b):
        counts = np.bincount(blocks[:, j], minlength=256).astype(float)
        entropies[j], chi2s[j] = _byte_entropy_and_chi2(counts, n_blocks)

    # (2) Relação entre blocos consecutivos: XOR par a par.
    diffs = blocks[1:] ^ blocks[:-1]
    hamming = _POPCOUNT[diffs].sum(axis=1).astype(float)  # bits por par
    repeat_rate = float(np.count_nonzero(hamming == 0)) / diffs.shape[0]

    diff_counts = np.bincount(diffs.reshape(-1), minlength=256).astype(float)
    diff_entropy, diff_chi2 = _byte_entropy_and_chi2(diff_counts, diffs.size)

    return {
        f"blk{b}_offset_entropy_std": float(entropies.std()),
        f"blk{b}_offset_entropy_range": float(entropies.max() - entropies.min()),
        f"blk{b}_offset_chi2_mean": float(chi2s.mean()),
        f"blk{b}_offset_chi2_std": float(chi2s.std()),
        # normalizado pelo número de bits do bloco: 0,5 é o esperado ideal
        f"blk{b}_hamming_consec_mean": float(hamming.mean()) / (8.0 * b),
        f"blk{b}_hamming_consec_std": float(hamming.std()) / (8.0 * b),
        f"blk{b}_diff_entropy": diff_entropy,
        f"blk{b}_diff_chi2": diff_chi2,
        f"blk{b}_repeat_rate": repeat_rate,
    }


def extract_blockalign(ct: bytes) -> dict[str, float]:
    """Estatísticas nas granularidades de 8 e 16 bytes.

    Args:
        ct: ciphertext (ou diferença de ciphertexts) como bytes.

    Returns:
        18 features (9 por tamanho de bloco). NaN quando não há pelo menos
        2 blocos completos naquela granularidade.
    """
    if not ct:
        out: dict[str, float] = {}
        for b in _BLOCK_SIZES:
            out.update(dict.fromkeys(_feature_names(b), _NAN))
        return out

    arr = np.frombuffer(ct, dtype=np.uint8)
    result: dict[str, float] = {}
    for b in _BLOCK_SIZES:
        result.update(_stats_for_block_size(arr, b))
    return result
