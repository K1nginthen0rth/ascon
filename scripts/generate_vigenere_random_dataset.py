"""
Gera dataset 2-classes: Vigenere-XOR vs PRNG-Random (64 KB).

Reutiliza as linhas Vigenere-XOR do dataset control_vigenere_64k_v1 e
gera bytes puramente aleatorios (PRNG numpy) com o mesmo protocolo de
chaves e splits — nenhuma cifragem real ocorre.

Dataset ID: vigenere_vs_random_v1
  - 30.000 amostras Vigenere-XOR  (herdadas de control_vigenere_64k_v1)
  - 30.000 amostras PRNG-Random   (numpy RNG, seed determinista)
  - Split 60/20/20 -> 80/20 no treino (mesmo mapeamento de chaves)
  - PT 64 KB, 300 chaves, 100 amostras/chave

Saidas (data/processed/):
  vigenere_vs_random_v1.parquet
  vigenere_vs_random_v1_manifest.json
  vigenere_vs_random_v1_splits.json

Uso:
    python scripts/generate_vigenere_random_dataset.py
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

import numpy as np
import pandas as pd

DATASET_ID         = "vigenere_vs_random_v1"
SOURCE_ID          = "control_vigenere_64k_v1"
PT_SIZE            = 65536  # 64 KB
N_KEYS             = 300
SAMPLES_PER_KEY    = 100
SEED               = 42
RANDOM_SEED_OFFSET = 5000  # disjunto dos offsets 0/1000/2000/3000/4000

DATA_DIR    = _REPO / "data" / "processed"
INTERIM_DIR = _REPO / "data" / "interim"
SOURCE_PQ   = DATA_DIR / f"{SOURCE_ID}.parquet"
OUT_PQ      = DATA_DIR / f"{DATASET_ID}.parquet"


def _git_hash() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=_REPO, stderr=subprocess.DEVNULL, text=True,
        ).strip()
    except Exception:
        return "unknown"


def main() -> None:
    print(f"\n{'='*70}")
    print(f"  Gerando: {DATASET_ID}")
    print(f"  2 classes: Vigenere-XOR vs PRNG-Random (64 KB)")
    print(f"{'='*70}")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)

    if not SOURCE_PQ.exists():
        print(f"\n  ERRO: dataset fonte nao encontrado: {SOURCE_PQ}")
        print(f"  Execute primeiro: python scripts/generate_vigenere_64k.py")
        sys.exit(1)

    # --- 1. Carregar linhas Vigenere-XOR do dataset existente ---------------
    print(f"\n  Carregando Vigenere-XOR de {SOURCE_PQ.name} ...")
    t0  = time.perf_counter()
    src = pd.read_parquet(SOURCE_PQ)
    vig = src[src["algorithm"] == "Vigenere-XOR"].copy()
    print(f"    {len(vig):,} amostras Vigenere-XOR carregadas  ({time.perf_counter()-t0:.1f}s)")

    splits_path = DATA_DIR / f"{SOURCE_ID}_splits.json"
    splits_src  = json.loads(splits_path.read_text(encoding="utf-8"))
    key_to_split: dict[str, str] = {}
    for sname in ("train_keys", "val_keys", "test_keys"):
        for kid in splits_src[sname]:
            key_to_split[kid] = sname.replace("_keys", "")
    vig["split"] = vig["key_id"].map(key_to_split)

    # --- 2. Gerar linhas PRNG-Random com mesmo esquema de chaves ------------
    all_key_ids = (
        splits_src["train_keys"]
        + splits_src["val_keys"]
        + splits_src["test_keys"]
    )
    assert len(all_key_ids) == N_KEYS, f"Esperado {N_KEYS} chaves, encontrado {len(all_key_ids)}"

    print(f"\n  Gerando {N_KEYS * SAMPLES_PER_KEY:,} amostras PRNG-Random ...")
    t1        = time.perf_counter()
    timestamp = datetime.now(timezone.utc).isoformat()
    rng       = np.random.default_rng(SEED + RANDOM_SEED_OFFSET)

    # nonce_counter: offset 1_000_000 para nao colidir com Vigenere (max ~30k)
    nonce_counter = 1_000_000
    random_rows: list[dict] = []

    for key_id in all_key_ids:
        key_num = int(key_id.split("_")[1])
        for _ in range(SAMPLES_PER_KEY):
            nonce_id = f"nonce_{nonce_counter:07d}"
            nonce_counter += 1

            ct = bytes(rng.integers(0, 256, size=PT_SIZE, dtype=np.uint8).tolist())

            random_rows.append({
                "sample_id":        (
                    f"prng_random_numpy_k{key_num:04d}"
                    f"_n{nonce_counter-1:07d}_pt{PT_SIZE}"
                ),
                "algorithm":        "PRNG-Random",
                "mode":             "random",
                "impl":             "numpy",
                "key_id":           key_id,
                "nonce_id":         nonce_id,
                "len_pt":           PT_SIZE,
                "len_ad":           0,
                "len_ct":           PT_SIZE,
                "key_bytes_used":   0,
                "ciphertext":       ct,
                "plaintext_source": "N/A",
                "seed":             SEED,
                "version":          "v1",
                "timestamp":        timestamp,
            })

        if key_num % 60 == 0 or key_num == N_KEYS:
            elapsed = time.perf_counter() - t1
            print(f"    key {key_num:3d}/{N_KEYS}  ({elapsed:.1f}s)")

    random_df = pd.DataFrame(random_rows)
    random_df["split"] = random_df["key_id"].map(key_to_split)

    # --- 3. Combinar, embaralhar e salvar ------------------------------------
    df = pd.concat([vig, random_df], ignore_index=True)
    df = df.sample(frac=1, random_state=SEED).reset_index(drop=True)

    df.to_parquet(OUT_PQ, index=False)

    algo_counts  = df["algorithm"].value_counts().to_dict()
    split_counts = df["split"].value_counts().to_dict()

    (DATA_DIR / f"{DATASET_ID}_splits.json").write_text(
        json.dumps({
            "train_keys":  splits_src["train_keys"],
            "val_keys":    splits_src["val_keys"],
            "test_keys":   splits_src["test_keys"],
            "seed":        SEED,
            "split_ratio": "60/20/20",
            "note":        "train+val mergeados em trainval (80%) no script de treino",
        }, indent=2),
        encoding="utf-8",
    )

    manifest = {
        "dataset_id":         DATASET_ID,
        "purpose": (
            "Experimento 2-classes Vigenere-XOR vs PRNG-Random: verifica que o "
            "pipeline detecta a estrutura periodica do XOR (chave 25 bits efetivos) "
            "contra bytes puramente aleatorios — controle positivo extremo."
        ),
        "created_at":         datetime.now(timezone.utc).isoformat(),
        "generator_script":   "scripts/generate_vigenere_random_dataset.py",
        "generator_version":  _git_hash(),
        "source_vigenere":    SOURCE_ID,
        "algorithms": [
            {
                "name":              "Vigenere-XOR",
                "impl":              "python",
                "key_bytes_used":    4,
                "key_effective_bits": 25,
                "source":            f"herdado de {SOURCE_ID}",
            },
            {
                "name":           "PRNG-Random",
                "impl":           "numpy",
                "key_bytes_used": 0,
                "note": (
                    f"{PT_SIZE} bytes uniformemente aleatorios por amostra "
                    f"(np.random.default_rng({SEED + RANDOM_SEED_OFFSET}))"
                ),
            },
        ],
        "parameters": {
            "n_keys":             N_KEYS,
            "pt_size":            PT_SIZE,
            "samples_per_key":    SAMPLES_PER_KEY,
            "total_samples":      len(df),
            "seed":               SEED,
            "random_seed_offset": RANDOM_SEED_OFFSET,
            "version":            "v1",
        },
        "statistics": {
            "total_samples":         len(df),
            "samples_per_algorithm": {str(k): int(v) for k, v in algo_counts.items()},
            "split_counts":          {str(k): int(v) for k, v in split_counts.items()},
        },
    }
    (DATA_DIR / f"{DATASET_ID}_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    elapsed_total = time.perf_counter() - t0
    print(f"\n  OK: {len(df):,} amostras em {elapsed_total:.1f}s")
    for algo, cnt in algo_counts.items():
        print(f"    {algo:20s}  {cnt:,}")
    print(f"  splits: {split_counts}")
    print(f"  salvo: {OUT_PQ.relative_to(_REPO)}")


if __name__ == "__main__":
    main()
