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
from src.features.families.complexity import extract_complexity
from src.features.families.entropy import extract_entropy_stats
from src.features.families.frequency import extract_frequency
from src.features.families.histogram import extract_histogram
from src.features.families.ngrams import extract_ngrams

_ALL_FAMILIES = ("histogram", "entropy", "ngrams", "autocorrelation", "complexity", "frequency")

_FAMILY_FUNCS = {
    "histogram": extract_histogram,
    "entropy": extract_entropy_stats,
    "ngrams": extract_ngrams,
    "autocorrelation": extract_autocorrelation,
    "complexity": extract_complexity,
    "frequency": extract_frequency,
}

_METADATA_COLS = ("sample_id", "algorithm", "key_id", "len_pt", "len_ct")


class CiphertextFeatureExtractor:
    """Extrai vetores de features numéricas de ciphertexts para modelos ML.

    Combina 6 famílias de features (~307 dimensões no total):
      - histogram (256): distribuição empírica de bytes
      - entropy (4): Shannon + chi² contra uniforme
      - ngrams (15): estatísticas de bigramas, trigramas e 4-gramas
      - autocorrelation (18): ACF lags 1–16 + Wald-Wolfowitz runs test
      - complexity (4): LZ76 + razões de compressão zlib/bz2
      - frequency (10): energia FFT por banda + entropia espectral

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
