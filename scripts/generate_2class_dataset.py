"""
Geração de datasets 2 classes: Ascon-AEAD128 vs GIFT-COFB.

Cada par (key_id, nonce_id, pt_size, sample_idx) é cifrado por AMBOS os
algoritmos com os mesmos inputs (mesma chave, mesmo nonce, mesmo plaintext).
Isso garante que qualquer diferença entre ciphertexts é puramente algorítmica,
eliminando artifacts de key-set ou plaintext-set.

Datasets gerados:
  1. pilot_2class_v1     — 10 chaves × 11 tamanhos × 100 × 2 = 22.000 amostras
  2. keyholdout_2class_v1 — 50 chaves × 3 tamanhos × 50 × 2 = 15.000 amostras

Uso:
    python scripts/generate_2class_dataset.py

Saídas (data/processed/):
    pilot_2class_v1.parquet
    pilot_2class_v1_manifest.json
    keyholdout_2class_v1.parquet
    keyholdout_2class_v1_manifest.json
    keyholdout_2class_v1_splits.json

Saídas (data/interim/):
    pilot_2class_v1_keys.json
    pilot_2class_v1_nonces.json
    pilot_2class_v1_plaintexts.parquet
    keyholdout_2class_v1_keys.json
    ...
"""
from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import sys

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_REPO_ROOT / "src" / "crypto"))

import numpy as np
import pandas as pd

from src.crypto.ascon_wrapper import AsconAEAD128
from src.crypto.gift_cofb_wrapper import GiftCOFB
from src.crypto.dataset_generator import _PlaintextGenerator

# ---------------------------------------------------------------------------
# Constantes e caminhos
# ---------------------------------------------------------------------------
CORPORA_DIR = _REPO_ROOT / "data" / "raw" / "corpora"
OUT_DIR     = _REPO_ROOT / "data" / "processed"
INTERIM_DIR = _REPO_ROOT / "data" / "interim"

# Configurações espelhadas do dataset single-class para compatibilidade de keys
PILOT_N_KEYS             = 10
PILOT_PT_SIZES           = [0, 1, 8, 16, 32, 64, 128, 256, 512, 1024, 2048]
PILOT_SAMPLES_PER_KS     = 100
PILOT_SEED               = 42
PILOT_KEY_SEED_OFFSET    = 0

KEYHOLDOUT_N_KEYS        = 50
KEYHOLDOUT_PT_SIZES      = [64, 256, 1024]
KEYHOLDOUT_SAMPLES_PER_KS = 50
KEYHOLDOUT_SEED          = 42
KEYHOLDOUT_KEY_SEED_OFFSET = 1000


# ---------------------------------------------------------------------------
# Gerador 2-classes
# ---------------------------------------------------------------------------

@dataclass
class TwoClassConfig:
    dataset_id: str
    n_keys: int
    pt_sizes: list[int]
    samples_per_key_size: int
    seed: int = 42
    key_seed_offset: int = 0
    ad: bytes = b""
    version: str = "v1"

    @property
    def total_samples(self) -> int:
        return self.n_keys * len(self.pt_sizes) * self.samples_per_key_size * 2


def _git_hash(repo_root: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo_root, stderr=subprocess.DEVNULL, text=True,
        ).strip()
    except Exception:
        return "unknown"


def generate_2class(config: TwoClassConfig) -> dict[str, Path]:
    """
    Gera dataset 2-classes e salva os artefatos.

    Para cada (key, pt_size, sample_idx):
      - Cifra com Ascon-AEAD128  → 1 linha com algorithm="Ascon-AEAD128"
      - Cifra com GIFT-COFB      → 1 linha com algorithm="GIFT-COFB"

    Mesmo key_bytes, nonce_bytes e plaintext para ambas as linhas do par.
    """
    print(f"\n{'='*60}")
    print(f"  Gerando: {config.dataset_id}")
    print(f"  {config.total_samples:,} amostras esperadas")
    print(f"{'='*60}")
    t0 = time.perf_counter()

    ascon  = AsconAEAD128()
    gift   = GiftCOFB()
    ciphers = [
        ("Ascon-AEAD128", "ref",   ascon),
        ("GIFT-COFB",     "opt32", gift),
    ]

    key_rng = np.random.default_rng(config.seed + config.key_seed_offset)
    pt_rng  = np.random.default_rng(config.seed + config.key_seed_offset + 500)
    pt_gen  = _PlaintextGenerator(CORPORA_DIR, rng=pt_rng)

    # Gerar chaves (idênticas para ambos os algoritmos)
    keys: list[tuple[str, bytes]] = []
    for i in range(config.n_keys):
        kid = f"key_{i+1:04d}"
        kb  = bytes(key_rng.integers(0, 256, size=16, dtype=np.uint8).tolist())
        keys.append((kid, kb))

    keys_map   : dict[str, str] = {kid: kb.hex() for kid, kb in keys}
    nonces_map : dict[str, str] = {}
    rows       : list[dict]     = []
    pt_rows    : list[dict]     = []

    nonce_counter = 1
    timestamp = datetime.now(timezone.utc).isoformat()

    for key_id, key_bytes in keys:
        for pt_size in config.pt_sizes:
            for sample_idx in range(config.samples_per_key_size):
                # Nonce shared between the two algorithm variants of this sample
                nonce_id    = f"nonce_{nonce_counter:06d}"
                nonce_bytes = nonce_counter.to_bytes(16, "big")
                nonces_map[nonce_id] = nonce_bytes.hex()
                nonce_counter += 1

                if pt_size == 0:
                    plaintext  = b""
                    pt_source  = "empty"
                else:
                    plaintext  = pt_gen.sample(pt_size)
                    pt_source  = "corpus"

                key_num = int(key_id.split("_")[1])

                for algo_name, impl_name, cipher in ciphers:
                    ct = cipher.encrypt(key_bytes, nonce_bytes, plaintext, config.ad)

                    algo_tag = algo_name.lower().replace("-", "_")
                    sample_id = (
                        f"{algo_tag}_{impl_name}"
                        f"_k{key_num:04d}"
                        f"_n{nonce_counter-1:06d}"
                        f"_pt{pt_size:04d}"
                    )

                    rows.append({
                        "sample_id":        sample_id,
                        "algorithm":        algo_name,
                        "mode":             "AEAD",
                        "impl":             impl_name,
                        "key_id":           key_id,
                        "nonce_id":         nonce_id,
                        "len_pt":           pt_size,
                        "len_ad":           len(config.ad),
                        "len_ct":           len(ct),
                        "ciphertext":       ct,
                        "plaintext_source": pt_source,
                        "seed":             config.seed,
                        "version":          config.version,
                        "timestamp":        timestamp,
                    })

                pt_rows.append({
                    "key_id":   key_id,
                    "nonce_id": nonce_id,
                    "len_pt":   pt_size,
                    "plaintext": plaintext,
                })

    df = pd.DataFrame(rows)

    # Split info (key-holdout datasets)
    split_info = None
    if config.n_keys > 10:
        n = len(keys)
        n_train = int(n * 0.6)
        n_val   = int(n * 0.2)
        all_ids = [kid for kid, _ in keys]
        split_info = {
            "train_keys": all_ids[:n_train],
            "val_keys":   all_ids[n_train: n_train + n_val],
            "test_keys":  all_ids[n_train + n_val:],
            "seed":       config.seed,
            "split_ratio": "60/20/20",
        }
        key_to_split = {}
        for sname in ("train_keys", "val_keys", "test_keys"):
            for kid in split_info[sname]:
                key_to_split[kid] = sname.replace("_keys", "")
        df["split"] = df["key_id"].map(key_to_split)

    elapsed = time.perf_counter() - t0

    # ---------------------------------------------------------------------------
    # Salvar
    # ---------------------------------------------------------------------------
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)

    did = config.dataset_id

    pq_path = OUT_DIR / f"{did}.parquet"
    df.to_parquet(pq_path, index=False)

    pt_df_path = INTERIM_DIR / f"{did}_plaintexts.parquet"
    pd.DataFrame(pt_rows).to_parquet(pt_df_path, index=False)

    (INTERIM_DIR / f"{did}_keys.json").write_text(
        json.dumps(keys_map, indent=2), encoding="utf-8"
    )
    (INTERIM_DIR / f"{did}_nonces.json").write_text(
        json.dumps(nonces_map, indent=2), encoding="utf-8"
    )

    # Manifesto
    size_dist   = df.groupby("len_pt").size().to_dict()
    algo_counts = df["algorithm"].value_counts().to_dict()
    src_ratio   = df["plaintext_source"].value_counts(normalize=True).round(4).to_dict()

    manifest = {
        "dataset_id":    config.dataset_id,
        "created_at":    datetime.now(timezone.utc).isoformat(),
        "generation_elapsed_s": round(elapsed, 2),
        "generator_script": "scripts/generate_2class_dataset.py",
        "generator_version": _git_hash(_REPO_ROOT),
        "algorithms": [
            {
                "name": "Ascon-AEAD128",
                "module": "src.crypto.ascon_wrapper.AsconAEAD128",
                "impl": "ref",
                "binary_sha256": ascon.metadata["binary_sha256"],
            },
            {
                "name": "GIFT-COFB",
                "module": "src.crypto.gift_cofb_wrapper.GiftCOFB",
                "impl": "opt32",
                "binary_sha256": gift.metadata["binary_sha256"],
            },
        ],
        "parameters": {
            "n_keys":                config.n_keys,
            "pt_sizes":              config.pt_sizes,
            "samples_per_key_size":  config.samples_per_key_size,
            "total_samples":         config.total_samples,
            "ad_policy":             "empty",
            "nonce_policy":          "global_counter_shared_per_pair",
            "plaintext_sources":     ["corpus"],
            "seed":                  config.seed,
            "key_seed_offset":       config.key_seed_offset,
            "version":               config.version,
            "note":                  "same key+nonce+plaintext for both algorithms in each pair",
        },
        "statistics": {
            "total_samples":         len(df),
            "samples_per_algorithm": {str(k): int(v) for k, v in algo_counts.items()},
            "total_ciphertext_bytes": int(df["len_ct"].sum()),
            "samples_per_pt_size":   {str(k): int(v) for k, v in size_dist.items()},
            "plaintext_source_ratio": src_ratio,
        },
        "sanity_checks": "pending - run scripts/validate_all_datasets.py",
    }

    manifest_path = OUT_DIR / f"{did}_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    saved: dict[str, Path] = {
        "parquet":    pq_path,
        "manifest":   manifest_path,
        "keys":       INTERIM_DIR / f"{did}_keys.json",
        "nonces":     INTERIM_DIR / f"{did}_nonces.json",
        "plaintexts": pt_df_path,
    }

    if split_info:
        sp = OUT_DIR / f"{did}_splits.json"
        sp.write_text(json.dumps(split_info, indent=2), encoding="utf-8")
        saved["splits"] = sp

    # Quick sanity checks
    assert len(df) == config.total_samples, (
        f"Total esperado: {config.total_samples}, obtido: {len(df)}"
    )
    for algo_name in ("Ascon-AEAD128", "GIFT-COFB"):
        n = (df["algorithm"] == algo_name).sum()
        expected = config.total_samples // 2
        assert n == expected, f"{algo_name}: esperava {expected} amostras, obteve {n}"

    print(f"  OK {len(df):,} amostras em {elapsed:.1f}s")
    print(f"  OK Ascon-AEAD128: {algo_counts.get('Ascon-AEAD128', 0):,}")
    print(f"  OK GIFT-COFB:     {algo_counts.get('GIFT-COFB', 0):,}")
    for name, path in saved.items():
        size_kb = path.stat().st_size / 1024
        print(f"     {name}: {path.name}  ({size_kb:.0f} KB)")

    return saved


def main() -> None:
    print("Gerador de datasets 2-classes: Ascon-AEAD128 vs GIFT-COFB")
    print(f"Repositorio: {_REPO_ROOT}")

    # Dataset piloto
    pilot_cfg = TwoClassConfig(
        dataset_id="pilot_2class_v1",
        n_keys=PILOT_N_KEYS,
        pt_sizes=PILOT_PT_SIZES,
        samples_per_key_size=PILOT_SAMPLES_PER_KS,
        seed=PILOT_SEED,
        key_seed_offset=PILOT_KEY_SEED_OFFSET,
    )
    generate_2class(pilot_cfg)

    # Dataset key-holdout
    kh_cfg = TwoClassConfig(
        dataset_id="keyholdout_2class_v1",
        n_keys=KEYHOLDOUT_N_KEYS,
        pt_sizes=KEYHOLDOUT_PT_SIZES,
        samples_per_key_size=KEYHOLDOUT_SAMPLES_PER_KS,
        seed=KEYHOLDOUT_SEED,
        key_seed_offset=KEYHOLDOUT_KEY_SEED_OFFSET,
    )
    generate_2class(kh_cfg)

    print(f"\n{'='*60}")
    print("  CONCLUIDO")
    print("  Para validar: python scripts/validate_all_datasets.py")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
