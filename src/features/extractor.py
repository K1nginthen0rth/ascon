"""Orquestrador de extração de features para classificação LWC ciphertext-only."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from tqdm import tqdm

from src.features.families.autocorrelation import extract_autocorrelation
from src.features.families.bitblock import extract_bitblock
from src.features.families.complexity import extract_complexity
from src.features.families.entropy import extract_entropy_stats
from src.features.families.frequency import extract_frequency
from src.features.families.hamming import extract_hamming
from src.features.families.histogram import extract_histogram
from src.features.families.moments import extract_moments
from src.features.families.ngrams import extract_ngrams
from src.features.families.nist_sts import extract_nist_sts
from src.features.families.spectral_welch import extract_spectral_welch
from src.features.families.tag_region import extract_tag_region

_ALL_FAMILIES = (
    "histogram", "entropy", "ngrams", "autocorrelation", "complexity",
    "frequency", "nist_sts", "moments", "hamming", "spectral_welch",
    "bitblock", "tag_region",
)

_FAMILY_FUNCS = {
    "histogram": extract_histogram,
    "entropy": extract_entropy_stats,
    "ngrams": extract_ngrams,
    "autocorrelation": extract_autocorrelation,
    "complexity": extract_complexity,
    "frequency": extract_frequency,
    "nist_sts": extract_nist_sts,
    "moments": extract_moments,
    "hamming": extract_hamming,
    "spectral_welch": extract_spectral_welch,
    "bitblock": extract_bitblock,
    "tag_region": extract_tag_region,
}

_METADATA_COLS = ("sample_id", "algorithm", "key_id", "len_pt", "len_ct")


class CiphertextFeatureExtractor:
    """Extrai vetores de features numéricas de ciphertexts para modelos ML.

    Combina 12 famílias de features (v2 — 641 dimensões no total, medido;
    a estimativa inicial de projeto era ~380-420, revisada para cima ao
    fechar `bitblock`/`nist_sts`; v1 tinha 6 famílias/307D):
      - histogram (256): distribuição empírica de bytes
      - entropy (4): Shannon + chi² contra uniforme
      - ngrams (15): estatísticas de bigramas, trigramas e 4-gramas
      - autocorrelation (18): ACF lags 1–16 + Wald-Wolfowitz runs test
      - complexity (5): LZ76 + razões de compressão zlib/bz2/lzma
      - frequency (10): energia FFT (byte) por banda + entropia espectral
      - nist_sts (25): suíte NIST SP 800-22 completa, nível de bit
      - moments (2): skewness + kurtosis da distribuição de bytes
      - hamming (11): distribuição de peso de Hamming por byte
      - spectral_welch (5): PSD de Welch (bit) + descritores espectrais
      - bitblock (~300): histograma de blocos de bits (bruto 2/4/8, agregado 12/16)
      - tag_region (8): estatísticas tag (janela comum 8B) vs. payload

    Cenário ciphertext-only: nenhuma família usa plaintext, chave ou nonce.
    len_pt/len_ct NÃO são incluídas nas features — ficam como metadados.

    Args:
        families: subconjunto de famílias a ativar. Default = todas.

    Example:
        extractor = CiphertextFeatureExtractor()
        feats = extractor.extract(ciphertext_bytes)
        df = extractor.extract_dataset("data/processed/pilot.parquet",
                                       output_path="data/processed/features.parquet")
    """

    def __init__(self, families: Optional[list[str]] = None) -> None:
        if families is None:
            families = list(_ALL_FAMILIES)
        unknown = set(families) - set(_FAMILY_FUNCS)
        if unknown:
            raise ValueError(f"Familias desconhecidas: {sorted(unknown)}")
        self._families = [f for f in _ALL_FAMILIES if f in set(families)]

    def extract(self, ct: bytes) -> dict[str, float]:
        """Extrai todas as features ativas de um único ciphertext."""
        result: dict[str, float] = {}
        for fname in self._families:
            result.update(_FAMILY_FUNCS[fname](ct))
        return result

    def feature_names(self) -> list[str]:
        """Retorna lista ordenada de nomes de features (baseada em CT de 64 bytes)."""
        return list(self.extract(bytes(range(64))))

    def n_features(self) -> int:
        return len(self.feature_names())

    def extract_dataset(
        self,
        parquet_path: str | Path,
        output_path: Optional[str | Path] = None,
        n_jobs: int = -1,
        show_progress: bool = True,
    ) -> pd.DataFrame:
        """Extrai features de todas as amostras de um dataset Parquet.

        Metadados preservados: sample_id, algorithm, key_id, len_pt, len_ct.
        Coluna 'ciphertext' NÃO é incluída no output.

        Args:
            parquet_path: path do parquet de ciphertexts.
            output_path: se fornecido, salva resultado em parquet.
            n_jobs: paralelismo joblib (-1 = todos os threads).
            show_progress: exibir barra de progresso tqdm.

        Returns:
            DataFrame com metadados + features numéricas (sem ciphertext bruto).
        """
        df = pd.read_parquet(parquet_path)
        families = self._families
        meta_cols = [c for c in _METADATA_COLS if c in df.columns]

        rows = df[meta_cols + ["ciphertext"]].to_dict("records")
        t0 = time.perf_counter()

        iterator = tqdm(rows, desc="Extracting features", disable=not show_progress)
        results = Parallel(n_jobs=n_jobs, prefer="processes")(
            delayed(_extract_row)(r, families, meta_cols) for r in iterator
        )

        elapsed = time.perf_counter() - t0
        n = len(results)
        print(
            f"Extraido: {n:,} amostras em {elapsed:.1f}s "
            f"({elapsed / n * 1000:.2f}ms/amostra)"
        )

        out_df = pd.DataFrame(results)

        if output_path is not None:
            out_df.to_parquet(output_path, index=False)
            print(f"Salvo: {output_path}")

        return out_df


def _extract_row(
    row: dict,
    families: list[str],
    meta_cols: list[str],
) -> dict:
    """Processa uma linha do dataset — função de nível de módulo para joblib."""
    ct = bytes(row["ciphertext"])
    result = {col: row[col] for col in meta_cols}
    for fname in families:
        result.update(_FAMILY_FUNCS[fname](ct))
    return result
