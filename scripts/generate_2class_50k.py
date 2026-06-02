"""
Replicacao Fase 4B-Extended: dataset key-holdout com 50k amostras por classe.

Reusa a infraestrutura de scripts/generate_2class_dataset.py (TwoClassConfig +
generate_2class). Diferenca: 100 chaves, 167 amostras/(chave x tamanho),
totalizando 100.200 amostras (50.100 por algoritmo).

Saida:
    data/processed/keyholdout_2class_50k_v1.parquet     (~100k amostras)
    data/processed/keyholdout_2class_50k_v1_manifest.json
    data/processed/keyholdout_2class_50k_v1_splits.json (60/20/20)
    data/interim/keyholdout_2class_50k_v1_keys.json
    data/interim/keyholdout_2class_50k_v1_nonces.json
    data/interim/keyholdout_2class_50k_v1_plaintexts.parquet
"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(_REPO / "scripts"))
sys.path.insert(0, str(_REPO / "src" / "crypto"))

from scripts.generate_2class_dataset import TwoClassConfig, generate_2class

CONFIG_50K = TwoClassConfig(
    dataset_id="keyholdout_2class_60k_v1",
    n_keys=300,
    pt_sizes=[65536],  # 64 KB fixo
    samples_per_key_size=100,   # 300 * 1 * 100 = 30.000 por algoritmo → 60k total
    seed=42,
    key_seed_offset=2000,        # disjunto dos offsets 0 e 1000 ja usados
    version="v1",
)


def main() -> None:
    print("Replicacao 60k - Tamanho fixo 64 KB, 300 chaves, plaintexts diferentes/chave")
    print(f"  n_keys:                 {CONFIG_50K.n_keys}")
    print(f"  pt_size (fixo):         64 KB")
    print(f"  samples/chave:          {CONFIG_50K.samples_per_key_size}")
    print(f"  por algoritmo:          {CONFIG_50K.n_keys * CONFIG_50K.samples_per_key_size:,}")
    print(f"  total (2 classes):      {CONFIG_50K.total_samples:,}")
    generate_2class(CONFIG_50K)


if __name__ == "__main__":
    main()
