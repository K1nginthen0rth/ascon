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
