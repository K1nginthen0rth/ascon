"""
Gera dataset 3-classes para CONTROLE POSITIVO do pipeline ML.

Classes: Ascon-AEAD128, GIFT-COFB, AES-128-ECB.
ECB e' inseguro mas estruturalmente diferente das AEADs (sem nonce, sem tag,
preserva padroes de bloco). Pipeline DEVE distingui-lo das AEADs.

Esquema:
  - 30 chaves (mesmas para os 3 algoritmos), seed=42 + offset=3000
  - 3 tamanhos de PT: 64, 256, 1024
  - 167 amostras por (chave x tamanho)
  - Mesmos plaintexts amostrados para os 3 algoritmos
  - Nonces gerados sequencialmente; ECB ignora mas mantem para compat
  - 30 * 3 * 167 * 3 = 45.030 amostras totais (15.010 por classe)

Splits:
  - 18 train / 6 val / 6 test (60/20/20)
  - Mesmas chaves para os 3 algoritmos -> chaves disjuntas entre splits

Saidas (data/processed/):
  control_3class_v1.parquet
  control_3class_v1_manifest.json
  control_3class_v1_splits.json
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(_REPO / "src" / "crypto"))

import numpy as np
import pandas as pd

from src.crypto.aes_ecb_wrapper   import AES128ECB
from src.crypto.ascon_wrapper      import AsconAEAD128
from src.crypto.dataset_generator  import _PlaintextGenerator
from src.crypto.gift_cofb_wrapper  import GiftCOFB

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DATASET_ID = "control_3class_v1"
N_KEYS               = 30
PT_SIZES             = [64, 256, 1024]
SAMPLES_PER_KEY_SIZE = 167   # 30 * 3 * 167 = 15.030 por algoritmo
SEED                 = 42
KEY_SEED_OFFSET      = 3000

CORPORA_DIR = _REPO / "data" / "raw" / "corpora"
OUT_DIR     = _REPO / "data" / "processed"
INTERIM_DIR = _REPO / "data" / "interim"

CIPHERS = [
    ("Ascon-AEAD128", "ref",    AsconAEAD128()),
    ("GIFT-COFB",     "opt32",  GiftCOFB()),
    ("AES-128-ECB",   "python", AES128ECB()),
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
    print(f"\n{'='*70}\n  Gerando: {DATASET_ID} (CONTROLE POSITIVO)\n{'='*70}")
    print(f"  N keys:                 {N_KEYS}")
    print(f"  PT sizes:               {PT_SIZES}")
    print(f"  samples / (key x size): {SAMPLES_PER_KEY_SIZE}")
    total_per_algo = N_KEYS * len(PT_SIZES) * SAMPLES_PER_KEY_SIZE
    total          = total_per_algo * len(CIPHERS)
    print(f"  por algoritmo:          {total_per_algo:,}")
    print(f"  total esperado:         {total:,}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)

    # Chaves (mesmas para os 3 algoritmos)
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
            for sample_idx in range(SAMPLES_PER_KEY_SIZE):
                # Nonce compartilhado pelas 3 amostras do triplet
                nonce_id    = f"nonce_{nonce_counter:06d}"
                nonce_bytes = nonce_counter.to_bytes(16, "big")
                nonces_map[nonce_id] = nonce_bytes.hex()
                nonce_counter += 1

                plaintext = pt_gen.sample(pt_size)

                key_num = int(key_id.split("_")[1])

                for algo_name, impl_name, cipher in CIPHERS:
                    ct = cipher.encrypt(key_bytes, nonce_bytes, plaintext, b"")
                    algo_tag = (algo_name.lower()
                                .replace("-", "_")
                                .replace("aead128", "aead128"))
                    sample_id = (
                        f"{algo_tag}_{impl_name}"
                        f"_k{key_num:04d}_n{nonce_counter-1:06d}"
                        f"_pt{pt_size:04d}"
                    )
                    rows.append({
                        "sample_id":        sample_id,
                        "algorithm":        algo_name,
                        "mode":             "ECB" if algo_name == "AES-128-ECB" else "AEAD",
                        "impl":             impl_name,
                        "key_id":           key_id,
                        "nonce_id":         nonce_id,
                        "len_pt":           pt_size,
                        "len_ad":           0,
                        "len_ct":           len(ct),
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
        "purpose":          "POSITIVE CONTROL - validate that pipeline can detect a known structural signal (ECB).",
        "created_at":       datetime.now(timezone.utc).isoformat(),
        "generation_elapsed_s": round(elapsed, 2),
        "generator_script": "scripts/generate_3class_control.py",
        "generator_version": _git_hash(),
        "algorithms": [
            {"name": "Ascon-AEAD128",
             "module": "src.crypto.ascon_wrapper.AsconAEAD128",
             "impl": "ref"},
            {"name": "GIFT-COFB",
             "module": "src.crypto.gift_cofb_wrapper.GiftCOFB",
             "impl": "opt32"},
            {"name": "AES-128-ECB",
             "module": "src.crypto.aes_ecb_wrapper.AES128ECB",
             "impl": "python",
             "note": "INSECURE - control class only, NOT a thesis target."},
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
            "note":                  "same key+nonce+plaintext across the 3 algorithms in each triplet",
        },
        "statistics": {
            "total_samples":         len(df),
            "samples_per_algorithm": {str(k): int(v) for k, v in algo_counts.items()},
            "samples_per_pt_size":   {str(k): int(v) for k, v in size_dist.items()},
            "ct_length_per_algorithm": {
                algo: {str(pt): int(df[(df["algorithm"] == algo) & (df["len_pt"] == pt)]["len_ct"].iloc[0])
                       for pt in PT_SIZES}
                for algo in df["algorithm"].unique()
            },
        },
        "splits": {
            "train_keys":  len(split_info["train_keys"]),
            "val_keys":    len(split_info["val_keys"]),
            "test_keys":   len(split_info["test_keys"]),
            "split_ratio": split_info["split_ratio"],
        },
        "sanity_checks": "pending - run scripts/validate_3class_control.py",
    }
    (OUT_DIR / f"{DATASET_ID}_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"\n  OK {len(df):,} amostras em {elapsed:.1f}s")
    for algo, cnt in algo_counts.items():
        # CT length distinto por algoritmo: aleatorio para 1024B
        ct_len = int(df[df["algorithm"] == algo]["len_ct"].iloc[0])
        ct_lens = sorted(df[df["algorithm"] == algo]["len_ct"].unique().tolist())
        print(f"     {algo:18s} {cnt:,}  CT_lens={ct_lens}")
    print(f"  splits: {df['split'].value_counts().to_dict()}")
    print(f"  arquivos:")
    for p in [pq_path, pt_df_path, OUT_DIR / f"{DATASET_ID}_manifest.json",
              OUT_DIR / f"{DATASET_ID}_splits.json"]:
        print(f"     {p.relative_to(_REPO)}  ({p.stat().st_size/1024:.0f} KB)")


if __name__ == "__main__":
    main()
