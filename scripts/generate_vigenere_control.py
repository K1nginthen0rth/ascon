"""
Gera dataset 3-classes para CONTROLE POSITIVO via cifra de Vigenere.

Classes: Ascon-AEAD128, GIFT-COFB, Vigenere-XOR (chave de 25 bits codificada em 4 bytes).
Vigenere e' cifra classica fraca, NAO algoritmo LWC — incluida apenas para
verificar que o pipeline detecta um sinal estrutural evidente (periodicidade).

Esquema:
  - 30 chaves (seed=42, key_seed_offset=3000 para evitar colisao)
  - 3 tamanhos de PT: 64, 256, 1024 bytes
  - 55 amostras por (chave x tamanho)
  - 30 * 3 * 55 = 4.950 amostras por algoritmo
  - Total: 4950 * 3 = 14.850 amostras
  - Mesmos plaintexts amostrados para os 3 algoritmos
  - Plaintexts 100% corpus natural (SPGC + Enron via _PlaintextGenerator)
  - Splits: 18 train / 6 val / 6 test (60/20/20) sobre as chaves

Chaves:
  - 16 bytes geradas normalmente
  - Ascon e GIFT-COFB usam os 16 bytes completos
  - Vigenere usa os 25 bits menos significativos dos 4 primeiros bytes
  - Registrado em key_bytes_used no manifesto

Saidas (data/processed/):
  control_vigenere_v1.parquet
  control_vigenere_v1_manifest.json
  control_vigenere_v1_splits.json
Interim:
  control_vigenere_v1_keys.json
  control_vigenere_v1_nonces.json
  control_vigenere_v1_plaintexts.parquet
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

from src.crypto.ascon_wrapper      import AsconAEAD128
from src.crypto.dataset_generator  import _PlaintextGenerator
from src.crypto.gift_cofb_wrapper  import GiftCOFB
from src.crypto.vigenere_wrapper   import VigenereWrapper

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DATASET_ID           = "control_vigenere_v1"
N_KEYS               = 30
PT_SIZES             = [64, 256, 1024]
SAMPLES_PER_KEY_SIZE = 55      # 30 * 3 * 55 = 4.950 por algoritmo
SEED                 = 42
KEY_SEED_OFFSET      = 3000

CORPORA_DIR = _REPO / "data" / "raw" / "corpora"
OUT_DIR     = _REPO / "data" / "processed"
INTERIM_DIR = _REPO / "data" / "interim"

CIPHERS = [
    ("Ascon-AEAD128", "ref",    AsconAEAD128(),    16),  # key_bytes_used
    ("GIFT-COFB",     "opt32",  GiftCOFB(),        16),
    ("Vigenere-XOR",  "python", VigenereWrapper(),  4),
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
    print(f"\n{'='*70}\n  Gerando: {DATASET_ID} (CONTROLE POSITIVO - VIGENERE)\n{'='*70}")
    print(f"  N keys:                 {N_KEYS}")
    print(f"  PT sizes:               {PT_SIZES}")
    print(f"  samples / (key x size): {SAMPLES_PER_KEY_SIZE}")
    total_per_algo = N_KEYS * len(PT_SIZES) * SAMPLES_PER_KEY_SIZE
    total          = total_per_algo * len(CIPHERS)
    print(f"  por algoritmo:          {total_per_algo:,}")
    print(f"  total esperado:         {total:,}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)

    # Chaves (mesmas para os 3 algoritmos; Vigenere usa apenas key[:3])
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
                key_num = int(key_id.split("_")[1])

                for algo_name, impl_name, cipher, key_bytes_used in CIPHERS:
                    ct = cipher.encrypt(key_bytes, nonce_bytes, plaintext, b"")
                    algo_tag = (algo_name.lower()
                                .replace("-", "_"))
                    sample_id = (
                        f"{algo_tag}_{impl_name}"
                        f"_k{key_num:04d}_n{nonce_counter-1:06d}"
                        f"_pt{pt_size:04d}"
                    )
                    rows.append({
                        "sample_id":        sample_id,
                        "algorithm":        algo_name,
                        "mode":             ("classical" if algo_name == "Vigenere-XOR"
                                             else "AEAD"),
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
                    "key_id":   key_id,
                    "nonce_id": nonce_id,
                    "len_pt":   pt_size,
                    "plaintext": plaintext,
                })

        if kn % 5 == 0 or kn == N_KEYS:
            print(f"     processadas {kn}/{N_KEYS} chaves "
                  f"(elapsed {time.perf_counter() - t0:.0f}s)")

    df = pd.DataFrame(rows)

    # Splits 60/20/20 sobre as chaves
    n_train = int(N_KEYS * 0.6)
    n_val   = int(N_KEYS * 0.2)
    all_ids = [kid for kid, _ in keys]
    split_info = {
        "train_keys": all_ids[:n_train],
        "val_keys":   all_ids[n_train: n_train + n_val],
        "test_keys":  all_ids[n_train + n_val:],
        "seed":        SEED,
        "split_ratio": "60/20/20",
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
    pt_df_path = INTERIM_DIR / f"{DATASET_ID}_plaintexts.parquet"
    pd.DataFrame(pt_rows).to_parquet(pt_df_path, index=False)
    (INTERIM_DIR / f"{DATASET_ID}_keys.json").write_text(
        json.dumps(keys_map, indent=2), encoding="utf-8"
    )
    (INTERIM_DIR / f"{DATASET_ID}_nonces.json").write_text(
        json.dumps(nonces_map, indent=2), encoding="utf-8"
    )
    (OUT_DIR / f"{DATASET_ID}_splits.json").write_text(
        json.dumps(split_info, indent=2), encoding="utf-8"
    )

    # Manifesto
    algo_counts = df["algorithm"].value_counts().to_dict()
    size_dist   = df.groupby("len_pt").size().to_dict()
    manifest = {
        "dataset_id":       DATASET_ID,
        "purpose": (
            "POSITIVE CONTROL via Vigenere XOR cipher (3-byte key). "
            "Validates that the ML pipeline can detect a known structural "
            "signal (cyclic periodicity) when present."
        ),
        "created_at":       datetime.now(timezone.utc).isoformat(),
        "generation_elapsed_s": round(elapsed, 2),
        "generator_script": "scripts/generate_vigenere_control.py",
        "generator_version": _git_hash(),
        "algorithms": [
            {"name": "Ascon-AEAD128",
             "module": "src.crypto.ascon_wrapper.AsconAEAD128",
             "impl": "ref", "key_bytes_used": 16},
            {"name": "GIFT-COFB",
             "module": "src.crypto.gift_cofb_wrapper.GiftCOFB",
             "impl": "opt32", "key_bytes_used": 16},
            {"name": "Vigenere-XOR",
             "module": "src.crypto.vigenere_wrapper.VigenereWrapper",
             "impl": "python", "key_bytes_used": 3,
             "note": "Classical cipher with 3-byte repeating XOR key. "
                     "INSECURE - control class only, NOT a thesis target."},
        ],
        "parameters": {
            "n_keys":                N_KEYS,
            "pt_sizes":              PT_SIZES,
            "samples_per_key_size":  SAMPLES_PER_KEY_SIZE,
            "total_samples":         total,
            "ad_policy":             "empty",
            "nonce_policy":          "global_counter_shared_per_triplet",
            "plaintext_sources":     ["corpus"],
            "seed":                  SEED,
            "key_seed_offset":       KEY_SEED_OFFSET,
            "version":               "v1",
            "note":                  "same key+nonce+plaintext across the 3 algorithms; "
                                     "Vigenere uses only key[:3].",
        },
        "statistics": {
            "total_samples":         len(df),
            "samples_per_algorithm": {str(k): int(v) for k, v in algo_counts.items()},
            "samples_per_pt_size":   {str(k): int(v) for k, v in size_dist.items()},
            "ct_length_per_algorithm": {
                algo: sorted(df[df["algorithm"] == algo]["len_ct"].unique().tolist())
                for algo in df["algorithm"].unique()
            },
        },
        "splits": {
            "train_keys":  len(split_info["train_keys"]),
            "val_keys":    len(split_info["val_keys"]),
            "test_keys":   len(split_info["test_keys"]),
            "split_ratio": split_info["split_ratio"],
        },
        "sanity_checks": "pending - run scripts/analyze_vigenere_control.py",
    }
    (OUT_DIR / f"{DATASET_ID}_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"\n  OK {len(df):,} amostras em {elapsed:.1f}s")
    for algo, cnt in algo_counts.items():
        ct_lens = sorted(df[df["algorithm"] == algo]["len_ct"].unique().tolist())
        print(f"     {algo:18s} {cnt:,}  CT_lens={ct_lens}")
    print(f"  splits: {df['split'].value_counts().to_dict()}")
    print(f"  arquivos:")
    for p in [pq_path, pt_df_path,
              OUT_DIR / f"{DATASET_ID}_manifest.json",
              OUT_DIR / f"{DATASET_ID}_splits.json"]:
        print(f"     {p.relative_to(_REPO)}  ({p.stat().st_size/1024:.0f} KB)")


if __name__ == "__main__":
    main()
