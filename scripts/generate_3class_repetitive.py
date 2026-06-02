"""
CONTROLE POSITIVO B: dataset 3-classes com PLAINTEXTS REPETITIVOS.

Diferenca vs control_3class_v1: PTs sao 4 padroes deterministicos repetitivos,
nao texto natural. ECB com PT repetitivo PRESERVA a repeticao no CT (vazamento
classico do ECB), enquanto Ascon e GIFT mascaram completamente.

Esperado: classificadores classicos atingem F1 >> 0.50, provando que o pipeline
e' capaz de detectar sinal estrutural quando ele esta presente.

Padroes (ciclados por sample_idx):
    pid 0: bytes(size)                       # zeros
    pid 1: b'\xff' * size                    # uns
    pid 2: (b'ABCDEFGHIJKLMNOP' * N)[:size]  # bloco de 16 ASCII repetido
    pid 3: (b'\\x00\\x01\\x02\\x03' * N)[:size] # contador curto repetido

Saidas (data/processed/):
  control_repetitive_3class_v1.parquet
  control_repetitive_3class_v1_manifest.json
  control_repetitive_3class_v1_splits.json
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

from src.crypto.aes_ecb_wrapper   import AES128ECB
from src.crypto.ascon_wrapper      import AsconAEAD128
from src.crypto.gift_cofb_wrapper  import GiftCOFB

DATASET_ID           = "control_repetitive_3class_v1"
N_KEYS               = 30
PT_SIZES             = [64, 256, 1024]
SAMPLES_PER_KEY_SIZE = 167
SEED                 = 42
KEY_SEED_OFFSET      = 4000   # disjunto de 0/1000/2000/3000

OUT_DIR     = _REPO / "data" / "processed"
INTERIM_DIR = _REPO / "data" / "interim"

CIPHERS = [
    ("Ascon-AEAD128", "ref",    AsconAEAD128()),
    ("GIFT-COFB",     "opt32",  GiftCOFB()),
    ("AES-128-ECB",   "python", AES128ECB()),
]

_PATTERNS = [
    ("zeros",       lambda n: b"\x00" * n),
    ("ones",        lambda n: b"\xff" * n),
    ("ascii_block", lambda n: (b"ABCDEFGHIJKLMNOP" * (n // 16 + 1))[:n]),
    ("counter_4",   lambda n: (b"\x00\x01\x02\x03" * (n // 4 + 1))[:n]),
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
    print(f"\n{'='*70}\n  Gerando: {DATASET_ID} (CONTROLE POSITIVO B)\n{'='*70}")
    total_per_algo = N_KEYS * len(PT_SIZES) * SAMPLES_PER_KEY_SIZE
    total          = total_per_algo * len(CIPHERS)
    print(f"  N keys:                 {N_KEYS}")
    print(f"  PT sizes:               {PT_SIZES}")
    print(f"  samples / (key x size): {SAMPLES_PER_KEY_SIZE}")
    print(f"  por algoritmo:          {total_per_algo:,}")
    print(f"  total esperado:         {total:,}")
    print(f"  patterns:               {[p[0] for p in _PATTERNS]}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)

    key_rng = np.random.default_rng(SEED + KEY_SEED_OFFSET)

    keys: list[tuple[str, bytes]] = []
    for i in range(N_KEYS):
        kid = f"key_{i+1:04d}"
        kb  = bytes(key_rng.integers(0, 256, size=16, dtype=np.uint8).tolist())
        keys.append((kid, kb))
    keys_map = {kid: kb.hex() for kid, kb in keys}

    nonces_map: dict[str, str] = {}
    rows: list[dict] = []
    pt_rows: list[dict] = []

    nonce_counter = 1
    timestamp = datetime.now(timezone.utc).isoformat()
    t0 = time.perf_counter()

    for kn, (key_id, key_bytes) in enumerate(keys, start=1):
        for pt_size in PT_SIZES:
            for sample_idx in range(SAMPLES_PER_KEY_SIZE):
                nonce_id    = f"nonce_{nonce_counter:06d}"
                nonce_bytes = nonce_counter.to_bytes(16, "big")
                nonces_map[nonce_id] = nonce_bytes.hex()
                nonce_counter += 1

                pid       = sample_idx % len(_PATTERNS)
                pname, pf = _PATTERNS[pid]
                plaintext = pf(pt_size)

                key_num = int(key_id.split("_")[1])

                for algo_name, impl_name, cipher in CIPHERS:
                    ct = cipher.encrypt(key_bytes, nonce_bytes, plaintext, b"")
                    algo_tag = algo_name.lower().replace("-", "_")
                    sample_id = (
                        f"{algo_tag}_{impl_name}"
                        f"_k{key_num:04d}_n{nonce_counter-1:06d}"
                        f"_pt{pt_size:04d}_p{pid}"
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
                        "plaintext_source": f"repetitive_{pname}",
                        "seed":             SEED,
                        "version":          "v1",
                        "timestamp":        timestamp,
                    })

                pt_rows.append({
                    "key_id":   key_id,
                    "nonce_id": nonce_id,
                    "len_pt":   pt_size,
                    "pattern":  pname,
                    "plaintext": plaintext,
                })

        if kn % 5 == 0 or kn == N_KEYS:
            print(f"     processadas {kn}/{N_KEYS} chaves "
                  f"(elapsed {time.perf_counter() - t0:.0f}s)")

    df = pd.DataFrame(rows)

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

    pq_path = OUT_DIR / f"{DATASET_ID}.parquet"
    df.to_parquet(pq_path, index=False)
    pt_path = INTERIM_DIR / f"{DATASET_ID}_plaintexts.parquet"
    pd.DataFrame(pt_rows).to_parquet(pt_path, index=False)
    (INTERIM_DIR / f"{DATASET_ID}_keys.json").write_text(
        json.dumps(keys_map, indent=2), encoding="utf-8"
    )
    (INTERIM_DIR / f"{DATASET_ID}_nonces.json").write_text(
        json.dumps(nonces_map, indent=2), encoding="utf-8"
    )
    (OUT_DIR / f"{DATASET_ID}_splits.json").write_text(
        json.dumps(split_info, indent=2), encoding="utf-8"
    )

    algo_counts    = df["algorithm"].value_counts().to_dict()
    pattern_counts = df["plaintext_source"].value_counts().to_dict()
    manifest = {
        "dataset_id": DATASET_ID,
        "purpose":    "POSITIVE CONTROL B - validate pipeline detects strong ECB signal "
                      "with deliberately repetitive plaintexts.",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "generation_elapsed_s": round(elapsed, 2),
        "generator_script":  "scripts/generate_3class_repetitive.py",
        "generator_version": _git_hash(),
        "algorithms": [
            {"name": "Ascon-AEAD128", "impl": "ref"},
            {"name": "GIFT-COFB",     "impl": "opt32"},
            {"name": "AES-128-ECB",   "impl": "python",
             "note": "INSECURE - control class only"},
        ],
        "parameters": {
            "n_keys": N_KEYS,
            "pt_sizes": PT_SIZES,
            "samples_per_key_size": SAMPLES_PER_KEY_SIZE,
            "total_samples": total,
            "ad_policy": "empty",
            "nonce_policy": "global_counter_shared_per_triplet",
            "plaintext_policy": "deterministic_repetitive_4_patterns",
            "patterns": [p[0] for p in _PATTERNS],
            "seed": SEED,
            "key_seed_offset": KEY_SEED_OFFSET,
            "version": "v1",
            "note": "ECB will leak block repetition; AEADs will mask it.",
        },
        "statistics": {
            "total_samples":         len(df),
            "samples_per_algorithm": {str(k): int(v) for k, v in algo_counts.items()},
            "samples_per_pattern":   {str(k): int(v) for k, v in pattern_counts.items()},
        },
        "splits": {
            "train_keys":  len(split_info["train_keys"]),
            "val_keys":    len(split_info["val_keys"]),
            "test_keys":   len(split_info["test_keys"]),
            "split_ratio": split_info["split_ratio"],
        },
    }
    (OUT_DIR / f"{DATASET_ID}_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"\n  OK {len(df):,} amostras em {elapsed:.1f}s")
    for algo, cnt in algo_counts.items():
        ct_lens = sorted(df[df["algorithm"] == algo]["len_ct"].unique().tolist())
        print(f"     {algo:18s} {cnt:,}  CT_lens={ct_lens}")
    print(f"  patterns: {pattern_counts}")
    print(f"  splits:   {df['split'].value_counts().to_dict()}")


if __name__ == "__main__":
    main()
