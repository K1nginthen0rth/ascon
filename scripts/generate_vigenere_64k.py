"""
Gera dataset 3-classes CONTROLE POSITIVO com configuracao identica ao experimento 60k.

Configuracao identica a keyholdout_2class_60k_v1:
  - 300 chaves, plaintexts de 64 KB, 100 amostras/chave
  - 30.000 amostras por algoritmo -> 90.000 total
  - Split 60/20/20 (180 train / 60 val / 60 test) -> mergeado em 80/20 no script de treino

Classes: Ascon-AEAD128, GIFT-COFB, Vigenere-XOR (chave efetiva 25 bits, 4 bytes)

Saidas (data/processed/):
  control_vigenere_64k_v1.parquet
  control_vigenere_64k_v1_manifest.json
  control_vigenere_64k_v1_splits.json
Interim:
  control_vigenere_64k_v1_keys.json
  control_vigenere_64k_v1_nonces.json
  control_vigenere_64k_v1_plaintexts.parquet

Uso:
    python scripts/generate_vigenere_64k.py
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(_REPO / "src" / "crypto"))

import numpy as np
import pandas as pd

from src.crypto.ascon_wrapper     import AsconAEAD128
from src.crypto.dataset_generator import _PlaintextGenerator
from src.crypto.gift_cofb_wrapper import GiftCOFB
from src.crypto.vigenere_wrapper  import VigenereWrapper

DATASET_ID           = "control_vigenere_64k_v1"
N_KEYS               = 300
PT_SIZES             = [65536]   # 64 KB — mesmo que o experimento principal
SAMPLES_PER_KEY_SIZE = 100       # 300 * 1 * 100 = 30.000 por algoritmo -> 90k total
SEED                 = 42
KEY_SEED_OFFSET      = 4000      # disjunto dos offsets 0/1000/2000/3000

CORPORA_DIR = _REPO / "data" / "raw" / "corpora"
OUT_DIR     = _REPO / "data" / "processed"
INTERIM_DIR = _REPO / "data" / "interim"

CIPHERS = [
    ("Ascon-AEAD128", "ref",    AsconAEAD128(),    16),
    ("GIFT-COFB",     "opt32",  GiftCOFB(),        16),
    ("Vigenere-XOR",  "python", VigenereWrapper(),   4),
]


def _git_hash() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=_REPO, stderr=subprocess.DEVNULL, text=True,
        ).strip()
    except Exception:
        return "unknown"


def main() -> None:
    print(f"\n{'='*70}\n  Gerando: {DATASET_ID} (CONTROLE POSITIVO 3 classes, 64KB)\n{'='*70}")
    total_per_algo = N_KEYS * len(PT_SIZES) * SAMPLES_PER_KEY_SIZE
    total          = total_per_algo * len(CIPHERS)
    print(f"  N keys:                {N_KEYS}")
    print(f"  PT size:               {PT_SIZES[0]:,} bytes (64 KB)")
    print(f"  amostras/chave:        {SAMPLES_PER_KEY_SIZE}")
    print(f"  por algoritmo:         {total_per_algo:,}")
    print(f"  total esperado:        {total:,}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)

    key_rng = np.random.default_rng(SEED + KEY_SEED_OFFSET)
    pt_rng  = np.random.default_rng(SEED + KEY_SEED_OFFSET + 500)
    pt_gen  = _PlaintextGenerator(CORPORA_DIR, rng=pt_rng)

    keys: list[tuple[str, bytes]] = []
    for i in range(N_KEYS):
        kid = f"key_{i+1:04d}"
        kb  = bytes(key_rng.integers(0, 256, size=16, dtype=np.uint8).tolist())
        keys.append((kid, kb))

    keys_map: dict[str, str] = {kid: kb.hex() for kid, kb in keys}
    nonces_map: dict[str, str] = {}
    rows: list[dict] = []
    pt_rows: list[dict] = []
    nonce_counter = 1
    timestamp = datetime.now(timezone.utc).isoformat()
    t0 = time.perf_counter()

    for kn, (key_id, key_bytes) in enumerate(keys, start=1):
        for pt_size in PT_SIZES:
            for _ in range(SAMPLES_PER_KEY_SIZE):
                nonce_id    = f"nonce_{nonce_counter:06d}"
                nonce_bytes = nonce_counter.to_bytes(16, "big")
                nonces_map[nonce_id] = nonce_bytes.hex()
                nonce_counter += 1

                plaintext = pt_gen.sample(pt_size)
                key_num   = int(key_id.split("_")[1])

                for algo_name, impl_name, cipher, key_bytes_used in CIPHERS:
                    ct = cipher.encrypt(key_bytes, nonce_bytes, plaintext, b"")
                    algo_tag  = algo_name.lower().replace("-", "_")
                    sample_id = (
                        f"{algo_tag}_{impl_name}"
                        f"_k{key_num:04d}_n{nonce_counter-1:06d}"
                        f"_pt{pt_size}"
                    )
                    rows.append({
                        "sample_id":        sample_id,
                        "algorithm":        algo_name,
                        "mode":             "classical" if algo_name == "Vigenere-XOR" else "AEAD",
                        "impl":             impl_name,
                        "key_id":           key_id,
                        "nonce_id":         nonce_id,
                        "len_pt":           pt_size,
                        "len_ad":           0,
                        "len_ct":           len(ct),
                        "key_bytes_used":   key_bytes_used,
                        "ciphertext":       ct,
                        "plaintext_source": "corpus",
                        "seed":             SEED,
                        "version":          "v1",
                        "timestamp":        timestamp,
                    })

                pt_rows.append({
                    "key_id":    key_id,
                    "nonce_id":  nonce_id,
                    "len_pt":    pt_size,
                    "plaintext": plaintext,
                })

        if kn % 30 == 0 or kn == N_KEYS:
            elapsed = time.perf_counter() - t0
            print(f"     {kn}/{N_KEYS} chaves  ({elapsed:.0f}s)")

    df = pd.DataFrame(rows)

    # Split 60/20/20 sobre as chaves (mesmo protocolo do experimento 60k)
    n_train = int(N_KEYS * 0.6)   # 180
    n_val   = int(N_KEYS * 0.2)   # 60
    all_ids = [kid for kid, _ in keys]
    split_info = {
        "train_keys": all_ids[:n_train],
        "val_keys":   all_ids[n_train: n_train + n_val],
        "test_keys":  all_ids[n_train + n_val:],
        "seed":        SEED,
        "split_ratio": "60/20/20",
        "note": "train+val sao mergeados em trainval (80%) no script de treino",
    }
    key_to_split = {}
    for sname in ("train_keys", "val_keys", "test_keys"):
        for kid in split_info[sname]:
            key_to_split[kid] = sname.replace("_keys", "")
    df["split"] = df["key_id"].map(key_to_split)

    elapsed = time.perf_counter() - t0

    # Salvar
    pq_path = OUT_DIR / f"{DATASET_ID}.parquet"
    df.to_parquet(pq_path, index=False)
    pd.DataFrame(pt_rows).to_parquet(
        INTERIM_DIR / f"{DATASET_ID}_plaintexts.parquet", index=False
    )
    (INTERIM_DIR / f"{DATASET_ID}_keys.json").write_text(
        json.dumps(keys_map, indent=2), encoding="utf-8"
    )
    (INTERIM_DIR / f"{DATASET_ID}_nonces.json").write_text(
        json.dumps(nonces_map, indent=2), encoding="utf-8"
    )
    (OUT_DIR / f"{DATASET_ID}_splits.json").write_text(
        json.dumps(split_info, indent=2), encoding="utf-8"
    )

    algo_counts = df["algorithm"].value_counts().to_dict()
    manifest = {
        "dataset_id":           DATASET_ID,
        "purpose": (
            "POSITIVE CONTROL via Vigenere-XOR (25-bit key). "
            "Configuracao identica ao experimento principal (64KB, 300 chaves, 100 amostras/chave). "
            "Valida que o pipeline detecta sinal estrutural (periodicidade ciclica) em CTs grandes."
        ),
        "created_at":           datetime.now(timezone.utc).isoformat(),
        "generation_elapsed_s": round(elapsed, 2),
        "generator_script":     "scripts/generate_vigenere_64k.py",
        "generator_version":    _git_hash(),
        "algorithms": [
            {"name": "Ascon-AEAD128", "impl": "ref",    "key_bytes_used": 16},
            {"name": "GIFT-COFB",     "impl": "opt32",  "key_bytes_used": 16},
            {"name": "Vigenere-XOR",  "impl": "python", "key_bytes_used": 4,
             "key_effective_bits": 25,
             "note": "Classical cipher with 4-byte repeating XOR key (25 effective bits). "
                     "INSECURE - positive control only, NOT a thesis target."},
        ],
        "parameters": {
            "n_keys":               N_KEYS,
            "pt_sizes":             PT_SIZES,
            "samples_per_key_size": SAMPLES_PER_KEY_SIZE,
            "total_samples":        total,
            "ad_policy":            "empty",
            "nonce_policy":         "global_counter_shared_per_triplet",
            "plaintext_sources":    ["corpus"],
            "seed":                 SEED,
            "key_seed_offset":      KEY_SEED_OFFSET,
            "version":              "v1",
        },
        "statistics": {
            "total_samples":         len(df),
            "samples_per_algorithm": {str(k): int(v) for k, v in algo_counts.items()},
            "split_counts":          df["split"].value_counts().to_dict(),
        },
        "splits": {
            "train_keys": len(split_info["train_keys"]),
            "val_keys":   len(split_info["val_keys"]),
            "test_keys":  len(split_info["test_keys"]),
            "split_ratio": "60/20/20 -> mergeado em 80/20 no treino",
        },
    }
    (OUT_DIR / f"{DATASET_ID}_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"\n  OK: {len(df):,} amostras em {elapsed:.1f}s")
    for algo, cnt in algo_counts.items():
        print(f"     {algo:18s}  {cnt:,}")
    print(f"  splits: {df['split'].value_counts().to_dict()}")
    print(f"  salvo: {pq_path.relative_to(_REPO)}")


if __name__ == "__main__":
    main()
