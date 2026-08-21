"""Família 12: separação tag vs. payload (comparação principal + exploratória).

Justificativa: a tag é gerada por mecanismo estruturalmente distinto em cada
algoritmo (squeeze da permutação / máscara COFB / acumulador dedicado /
finalização Schwaemm), enquanto o payload é desenhado para parecer uniforme
nos quatro — se há lugar provável para uma assinatura residual, é a tag
(ver docs/plano_experimento_v2/02_features_e_selecao.md).

**Janela comum de 8 bytes (comparação principal):** usar o `ABYTES` real de
cada algoritmo (16 para Ascon/GIFT/Sparkle, 8 para Grain) introduziria um
viés de estimador de amostra pequena que separa o Grain por TAMANHO da
janela, não por conteúdo (entropia de n≪256 bytes uniformes tende a
log2(n), independente da fonte — ≈3,0 bits p/ 8 bytes vs. ≈4,0 bits p/ 16).
Isso reintroduziria `len_ct` como feature pela porta dos fundos (violação
da Regra de Ouro 5). Corrigido: janela comum de 8 bytes (mínimo entre os
algoritmos) para todos os quatro na comparação principal.

**Sempre sobre o CT cru** — nunca sobre o braço `controlado` (truncado),
que corta os últimos bytes do CT e destruiria/deslocaria a tag dos
algoritmos com ABYTES=16 (ver `01_algoritmos_e_dataset.md` §1.6).

**Tag completa por algoritmo:** análise exploratória separada
(`extract_tag_region_full`), com o viés de amostra pequena declarado —
não entra na comparação principal.

Fronteira sempre via `abytes` explícito (parâmetro obrigatório) — nunca
offset fixo hardcoded.
"""
from __future__ import annotations

import numpy as np

_NAN = float("nan")
_COMMON_WINDOW = 8  # min(ABYTES) entre os 4 algoritmos — ver docstring


def _window_stats(window: bytes, prefix: str) -> dict[str, float]:
    """Histograma agregado + entropia + χ² para uma janela pequena de bytes."""
    n = len(window)
    if n == 0:
        return {
            f"{prefix}_entropy": _NAN,
            f"{prefix}_nunique": _NAN,
            f"{prefix}_max_freq": _NAN,
            f"{prefix}_chi2_statistic": _NAN,
        }

    arr = np.frombuffer(window, dtype=np.uint8)
    counts = np.bincount(arr, minlength=256).astype(float)
    probs = counts / n
    nz = probs[probs > 0]
    entropy = float(-np.sum(nz * np.log2(nz)))
    nunique = float(np.count_nonzero(counts))
    max_freq = float(probs.max())

    # χ² contra uniforme de 256 bins — só a estatística (não o p-value: dof
    # elevado com n pequeno deixa o p-value pouco informativo aqui).
    expected = np.full(256, n / 256.0)
    chi2_stat = float(np.sum(((counts - expected) ** 2) / expected))

    return {
        f"{prefix}_entropy": entropy,
        f"{prefix}_nunique": nunique,
        f"{prefix}_max_freq": max_freq,
        f"{prefix}_chi2_statistic": chi2_stat,
    }


def extract_tag_region(ct: bytes) -> dict[str, float]:
    """Comparação principal: janela comum de 8 bytes finais (tag) vs. resto
    (payload) — sempre sobre o CT cru, mesma janela para os 4 algoritmos.

    Args:
        ct: ciphertext cru (CT || tag), como bytes. NUNCA passar a versão
            truncada do braço `controlado` aqui.

    Returns:
        tag8_*: estatísticas da janela de 8 bytes finais.
        payload_rest_*: estatísticas de todo o restante (ct[:-8]).
        NaN se len(ct) < 8.
    """
    if len(ct) < _COMMON_WINDOW:
        keys = [
            f"{p}_{s}"
            for p in ("tag8", "payload_rest")
            for s in ("entropy", "nunique", "max_freq", "chi2_statistic")
        ]
        return dict.fromkeys(keys, _NAN)

    tag_window = ct[-_COMMON_WINDOW:]
    payload_rest = ct[:-_COMMON_WINDOW]

    result = _window_stats(tag_window, "tag8")
    result.update(_window_stats(payload_rest, "payload_rest"))
    return result


def extract_tag_region_full(ct: bytes, abytes: int) -> dict[str, float]:
    """Exploratório: tag COMPLETA (ABYTES real do algoritmo) vs. payload.

    **Não entra na comparação principal** — viés de amostra pequena varia
    com `abytes` entre algoritmos (ver docstring do módulo). Só para
    análise exploratória declarada, sempre sobre o CT cru.

    Args:
        ct: ciphertext cru (CT || tag).
        abytes: tamanho da tag em bytes, do wrapper do algoritmo (nunca
            offset fixo — 16 para Ascon/GIFT/Sparkle, 8 para Grain).

    Returns:
        tag_full_*: estatísticas da tag completa (abytes bytes finais).
        payload_full_*: estatísticas do payload completo (ct[:-abytes]).
        NaN se len(ct) < abytes.
    """
    if abytes <= 0:
        raise ValueError(f"abytes deve ser positivo; recebeu {abytes}.")
    if len(ct) < abytes:
        keys = [
            f"{p}_{s}"
            for p in ("tag_full", "payload_full")
            for s in ("entropy", "nunique", "max_freq", "chi2_statistic")
        ]
        return dict.fromkeys(keys, _NAN)

    tag = ct[-abytes:]
    payload = ct[:-abytes]

    result = _window_stats(tag, "tag_full")
    result.update(_window_stats(payload, "payload_full"))
    return result
