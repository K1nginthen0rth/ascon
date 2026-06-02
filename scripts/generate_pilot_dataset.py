"""
Geração do dataset piloto Ascon-AEAD128 (Fase 2).

Gera dois datasets:
  1. ascon_aead128_pilot_v1    — 10 chaves × 11 tamanhos × 100 = 11.000 amostras
  2. ascon_aead128_keyholdout_v1 — 50 chaves × 3 tamanhos × 50 = 7.500 amostras

Uso:
    python scripts/generate_pilot_dataset.py

Saídas (data/processed/):
    ascon_aead128_pilot_v1.parquet
    ascon_aead128_pilot_v1_manifest.json
    ascon_aead128_keyholdout_v1.parquet
    ascon_aead128_keyholdout_v1_manifest.json
    ascon_aead128_keyholdout_v1_splits.json

Saídas (data/interim/):
    ascon_aead128_pilot_v1_keys.json
    ascon_aead128_pilot_v1_nonces.json
    ascon_aead128_pilot_v1_plaintexts.parquet
    ascon_aead128_keyholdout_v1_keys.json
    ascon_aead128_keyholdout_v1_nonces.json
    ascon_aead128_keyholdout_v1_plaintexts.parquet
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Setup de paths (repositório pode ser chamado de qualquer diretório)
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_REPO_ROOT / "src" / "crypto"))  # para _ascon_ref

from src.crypto.dataset_generator import AsconDatasetGenerator, DatasetConfig

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
CORPORA_DIR = _REPO_ROOT / "data" / "raw" / "corpora"
OUT_DIR     = _REPO_ROOT / "data" / "processed"
INTERIM_DIR = _REPO_ROOT / "data" / "interim"

PILOT_CONFIG = DatasetConfig(
    dataset_id="ascon_aead128_pilot_v2",
    n_keys=10,
    pt_sizes=[0, 1, 8, 16, 32, 64, 128, 256, 512, 1024, 2048],
    samples_per_key_size=100,
    seed=42,
    ad=b"",
    version="v2",
    key_seed_offset=0,
    supersedes="ascon_aead128_pilot_v1",
)

KEYHOLDOUT_CONFIG = DatasetConfig(
    dataset_id="ascon_aead128_keyholdout_v2",
    n_keys=50,
    pt_sizes=[64, 256, 1024],
    samples_per_key_size=50,
    seed=42,
    ad=b"",
    version="v2",
    key_seed_offset=1000,
    supersedes="ascon_aead128_keyholdout_v1",
)


def _fmt(n: int) -> str:
    return f"{n:,}"


def generate_dataset(config: DatasetConfig, label: str) -> dict:
    print(f"\n{'='*60}")
    print(f"  Gerando: {config.dataset_id}")
    print(f"  {_fmt(config.total_samples)} amostras esperadas")
    print(f"{'='*60}")

    t0 = time.perf_counter()
    gen = AsconDatasetGenerator(config, corpora_dir=CORPORA_DIR)
    result = gen.generate()
    elapsed = time.perf_counter() - t0

    saved = result.save(out_dir=OUT_DIR, interim_dir=INTERIM_DIR)

    # Verificações rápidas
    df = result.df
    assert len(df) == config.total_samples, (
        f"Total esperado: {config.total_samples}, obtido: {len(df)}"
    )
    # Unicidade de nonces por chave
    for kid in df["key_id"].unique():
        nids = df[df["key_id"] == kid]["nonce_id"]
        assert nids.nunique() == len(nids), f"Nonces repetidos em {kid}!"

    print(f"  OK {_fmt(len(df))} amostras geradas em {elapsed:.1f}s")
    print(f"  OK Nonces unicos por chave")
    print(f"  OK Arquivos salvos:")
    for name, path in saved.items():
        size_kb = path.stat().st_size / 1024
        print(f"      {name}: {path.name}  ({size_kb:.0f} KB)")

    return {
        "dataset_id": config.dataset_id,
        "total_samples": len(df),
        "elapsed_s": round(elapsed, 2),
        "paths": {k: str(v) for k, v in saved.items()},
    }


def main() -> None:
    print("Gerador de dataset piloto Ascon-AEAD128 - Fase 2")
    print(f"Repositório: {_REPO_ROOT}")
    print(f"Corpus: {CORPORA_DIR}")

    results = []

    # Parte A: Dataset Piloto
    results.append(generate_dataset(PILOT_CONFIG, "piloto"))

    # Parte B: Dataset Key-Holdout
    results.append(generate_dataset(KEYHOLDOUT_CONFIG, "key-holdout"))

    # Sumário final
    total = sum(r["total_samples"] for r in results)
    total_time = sum(r["elapsed_s"] for r in results)
    print(f"\n{'='*60}")
    print(f"  CONCLUIDO")
    print(f"  Total de amostras: {_fmt(total)}")
    print(f"  Tempo total: {total_time:.1f}s")
    print(f"  Para validar: python scripts/validate_pilot_dataset.py")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
