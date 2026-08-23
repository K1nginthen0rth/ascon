"""
Conversão de ciphertext em representações 2D para CNN 2D.

Representação canônica: mapa de co-ocorrência de bigramas 256×256.
  - pixel[i,j] = freq(byte i seguido de byte j) / total_pares
  - Usa o CT completo sem truncamento
  - Adjacência real: apenas bytes consecutivos são relacionados
  - Invariante a permutações que preservem pares consecutivos

Representação alternativa (legada): reshape linear 32×32.
  Mantida para compatibilidade com experimentos anteriores (protocolo antigo).
"""
from __future__ import annotations

import numpy as np


def bytes_to_cooccurrence(ct: bytes) -> np.ndarray:
    """
    Converte ciphertext em mapa de co-ocorrência de bigramas 256×256.

    Usa o CT completo (sem truncamento). O pixel [i, j] representa a
    frequência relativa do par de bytes consecutivos (i, j) no ciphertext.

    Implementação via np.bincount — O(n) sem loop Python.

    Args:
        ct: ciphertext como bytes.

    Returns:
        (256, 256) float32, soma = 1.0 (ou zeros se CT < 2 bytes).
    """
    arr = np.frombuffer(ct, dtype=np.uint8)
    if arr.size < 2:
        return np.zeros((256, 256), dtype=np.float32)
    indices = arr[:-1].astype(np.int32) * 256 + arr[1:].astype(np.int32)
    counts  = np.bincount(indices, minlength=256 * 256)
    matrix  = counts.reshape(256, 256).astype(np.float32)
    total   = matrix.sum()
    if total > 0:
        matrix /= total
    return matrix


def batch_ciphertexts_to_cooccurrence(cts) -> np.ndarray:
    """Versão em lote — retorna (N, 1, 256, 256) float32."""
    out = np.empty((len(cts), 1, 256, 256), dtype=np.float32)
    for i, ct in enumerate(cts):
        out[i, 0] = bytes_to_cooccurrence(bytes(ct))
    return out


# ---------------------------------------------------------------------------
# Variantes de condicionamento (06 Fase 7) — testadas no smoke/1-fold do
# Caminho C; a vencedora por val_loss congela e só ela vai à CV completa.
#
# Motivo de existir: `bytes_to_cooccurrence` normaliza para soma=1, o que
# deixa cada célula na casa de ~1,5e-5 (1/65.536) — o dado que a primeira
# camada convolucional recebe é uniformemente minúsculo, o que pode
# achatar gradientes cedo no treino. As 3 variantes testam correções
# diferentes para essa escala, sem mudar a informação carregada (todas são
# funções determinísticas e invertíveis-ou-quase da mesma contagem bruta):
#   - `raw`: contagem bruta (SEM dividir pelo total) — "×65536" no plano,
#     porque desnormalizar a versão soma=1 por ~65536 (o total de pares)
#     recupera aproximadamente a contagem original.
#   - `log1p`: log(1+contagem) — comprime a cauda longa (poucas células
#     muito frequentes, muitas quase nulas) mantendo tudo não-negativo.
#   - `standardized`: z-score com média/desvio GLOBAIS (escalares, não por
#     pixel — 200 amostras de treino não bastam para estimar 65.536
#     médias/desvios individuais sem overfitting), fitados numa
#     subamostra do treino e reaproveitados no resto (nunca refitados em
#     val/teste).
# ---------------------------------------------------------------------------

COND_VARIANTS = ("sum1", "raw", "log1p", "standardized")


def _raw_cooccurrence_counts(ct: bytes) -> np.ndarray:
    """Como `bytes_to_cooccurrence`, mas sem normalizar (contagem bruta)."""
    arr = np.frombuffer(ct, dtype=np.uint8)
    if arr.size < 2:
        return np.zeros((256, 256), dtype=np.float32)
    indices = arr[:-1].astype(np.int32) * 256 + arr[1:].astype(np.int32)
    counts = np.bincount(indices, minlength=256 * 256)
    return counts.reshape(256, 256).astype(np.float32)


def fit_standardization_stats(cts_sample, n_sample: int = 200) -> tuple[float, float]:
    """
    Média/desvio GLOBAIS (escalares) da contagem bruta, estimados numa
    subamostra do TREINO. Chamar uma vez por fold/execução e reaproveitar
    — nunca refitar em validação/teste (mesma disciplina do resto do
    projeto: estatística de normalização é "parâmetro do modelo").
    """
    rng = np.random.default_rng(7)
    idx = rng.choice(len(cts_sample), size=min(n_sample, len(cts_sample)), replace=False)
    values = np.concatenate([
        _raw_cooccurrence_counts(bytes(cts_sample[i])).ravel() for i in idx
    ])
    return float(values.mean()), float(values.std() + 1e-8)


def bytes_to_cooccurrence_conditioned(
    ct: bytes, variant: str = "sum1", mean: float = 0.0, std: float = 1.0,
) -> np.ndarray:
    """
    Mapa de co-ocorrência sob a variante de condicionamento pedida.

    Args:
        variant: um de `COND_VARIANTS`.
        mean, std: só usados por `variant="standardized"` — vêm de
            `fit_standardization_stats` no TREINO do fold.
    """
    if variant == "sum1":
        return bytes_to_cooccurrence(ct)
    raw = _raw_cooccurrence_counts(ct)
    if variant == "raw":
        return raw
    if variant == "log1p":
        return np.log1p(raw)
    if variant == "standardized":
        return (raw - mean) / std
    raise ValueError(f"variante de condicionamento desconhecida: {variant!r} "
                     f"(válidas: {COND_VARIANTS})")


# ---------------------------------------------------------------------------
# Representação legada (reshape linear) — mantida para experimentos antigos
# ---------------------------------------------------------------------------

def ciphertext_to_image(ct: bytes, image_size: int = 32) -> np.ndarray:
    """Reshape linear de bytes em imagem quadrada (representação legada).

    LIMITAÇÃO: impõe adjacência espacial artificial entre bytes que não são
    vizinhos no CT. Use bytes_to_cooccurrence() para experimentos novos.
    """
    if image_size <= 0:
        raise ValueError("image_size deve ser positivo.")
    target = image_size * image_size
    arr    = np.frombuffer(ct, dtype=np.uint8)
    if arr.size >= target:
        arr = arr[:target]
    else:
        arr = np.concatenate([arr, np.zeros(target - arr.size, dtype=np.uint8)])
    return arr.reshape(image_size, image_size).astype(np.float32) / 255.0


def batch_ciphertexts_to_images(cts, image_size: int = 32) -> np.ndarray:
    """Versão em lote do reshape linear — retorna (N, 1, H, W) float32."""
    out = np.empty((len(cts), 1, image_size, image_size), dtype=np.float32)
    for i, ct in enumerate(cts):
        out[i, 0] = ciphertext_to_image(bytes(ct), image_size=image_size)
    return out
