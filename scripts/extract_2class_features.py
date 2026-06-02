"""
Extrai features dos datasets 2-classes.

Uso:
    python scripts/extract_2class_features.py [dataset_id ...]

Sem argumentos, processa pilot_2class_v1 e keyholdout_2class_v1.
"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(_REPO / "src" / "crypto"))

from src.features.extractor import CiphertextFeatureExtractor

ex = CiphertextFeatureExtractor()
processed = _REPO / "data" / "processed"

datasets = sys.argv[1:] or ["pilot_2class_v1", "keyholdout_2class_v1"]

for dataset_id in datasets:
    src = processed / f"{dataset_id}.parquet"
    dst = processed / f"{dataset_id}_features.parquet"
    print(f"\n=== {dataset_id} ===")
    df = ex.extract_dataset(src, output_path=dst, n_jobs=-1, show_progress=True)
    algos = df["algorithm"].value_counts().to_dict()
    nan_total = int(df.isna().sum().sum())
    size_mb = dst.stat().st_size / 1024 / 1024
    print(f"Shape:      {df.shape}")
    print(f"Algoritmos: {algos}")
    print(f"NaN total:  {nan_total}")
    print(f"Arquivo:    {dst.name}  ({size_mb:.1f} MB)")
