from __future__ import annotations

import json
import secrets
import subprocess
from pathlib import Path

import pandas as pd

from plaintext_generator import PlaintextGenerator


ROOT = Path(r"C:\Users\nycol\Documents\Mestrado\ascon")
WRAPPER_EXE = ROOT / "scripts" / "ascon_cli_ref.exe"
CORPORA_DIR = ROOT / "data" / "raw" / "corpora"
OUT_PATH = ROOT / "data" / "processed" / "ascon_aead128_base_v1.parquet"

CRYPTO_KEYBYTES = 16
CRYPTO_NPUBBYTES = 16
CRYPTO_ABYTES = 16

N_SAMPLES = 10000

# FIXOS DO DATASET
LEN_PT = 128
LEN_AD = 64

ALGO_ID = "Ascon-AEAD128_SP800-232"
ASCON_COMMIT = "b7ca60b"
ASCON_TAG = "v1.3.0"
ASCON_CRYPTO_VERSION = "1.3.0"
IMPL = "ref"
TAG_LEN = 128
SEED = "session_key_text_only_v1"

PROFILE_PATH = ROOT / "data" / "processed" / "ascon_aead128_base_v1_profile.json"
MANIFEST_PATH = ROOT / "data" / "processed" / "ascon_aead128_base_v1_manifest.json"


def rand_bytes(n: int) -> bytes:
    return secrets.token_bytes(n)


def encrypt_with_wrapper(key: bytes, nonce: bytes, ad: bytes, pt: bytes) -> tuple[bytes, bytes]:
    cmd = [
        str(WRAPPER_EXE),
        key.hex(),
        nonce.hex(),
        ad.hex(),
        pt.hex(),
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )
        ct_full = bytes.fromhex(result.stdout.strip())
    except (subprocess.CalledProcessError, ValueError) as e:
        raise RuntimeError(
            f"Encryption wrapper failed: {e}. "
            f"stdout={result.stdout[:200] if 'result' in locals() else 'N/A'}"
        ) from e

    ct = ct_full[: len(pt)]
    tag = ct_full[len(pt) : len(pt) + CRYPTO_ABYTES]
    return ct, tag


def main() -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    generator = PlaintextGenerator(CORPORA_DIR)
    key = rand_bytes(CRYPTO_KEYBYTES)
    seen_nonces: set[bytes] = set()

    rows = []

    for sample_id in range(N_SAMPLES):
        nonce = rand_bytes(CRYPTO_NPUBBYTES)
        while nonce in seen_nonces:
            nonce = rand_bytes(CRYPTO_NPUBBYTES)
        seen_nonces.add(nonce)

        pt, pt_source = generator.sample(LEN_PT)
        ad = rand_bytes(LEN_AD)

        ct, tag = encrypt_with_wrapper(key, nonce, ad, pt)

        assert len(pt) == LEN_PT
        assert len(ad) == LEN_AD
        assert len(ct) == len(pt)
        assert len(tag) == CRYPTO_ABYTES

        rows.append(
            {
                "sample_id": sample_id,
                "key": key,
                "nonce": nonce,
                "pt": pt,
                "pt_source": pt_source,
                "ad": ad,
                "ct": ct,
                "tag": tag,
                "len_pt": len(pt),
                "len_ad": len(ad),
                "algo_id": ALGO_ID,
                "ascon_commit": ASCON_COMMIT,
                "seed": SEED,
                "ascon_tag": ASCON_TAG,
                "ascon_crypto_version": ASCON_CRYPTO_VERSION,
                "impl": IMPL,
                "tag_len": TAG_LEN,
            }
        )

    df = pd.DataFrame(rows)
    df.to_parquet(OUT_PATH, index=False)

    print(f"Parquet salvo em: {OUT_PATH}")
    print(f"Total de amostras: {len(df)}")
    print(f"Nonces únicos: {df['nonce'].nunique()}")

    profile = {
        "dataset_id": "ascon_aead128_base_v1",
        "storage_format": "parquet",
        "algorithm": ALGO_ID,
        "implementation": IMPL,
        "ascon_tag": ASCON_TAG,
        "ascon_commit": ASCON_COMMIT,
        "ascon_crypto_version": ASCON_CRYPTO_VERSION,
        "tag_len_bits": TAG_LEN,
        "key_regime": "session_key",
        "nonce_policy": "unique_per_key",
        "plaintext_policy": {
            "source": "natural_text_only",
            "corpora": "all_txt_files_in_data_raw_corpora",
            "encoding": "utf-8",
            "len_pt_range_bytes": [LEN_PT, LEN_PT],
        },
        "ad_policy": {
            "source": "random_bytes",
            "len_ad_range_bytes": [LEN_AD, LEN_AD],
        },
        "schema_fields": list(df.columns),
    }

    manifest = {
        "dataset_id": "ascon_aead128_base_v1",
        "output_file": OUT_PATH.name,
        "n_samples": len(df),
        "ascon_tag": ASCON_TAG,
        "ascon_commit": ASCON_COMMIT,
        "implementation": IMPL,
        "seed": SEED,
        "key_regime": "session_key",
        "nonce_policy": "unique_per_key",
        "len_pt_min": int(df["len_pt"].min()),
        "len_pt_max": int(df["len_pt"].max()),
        "len_ad_min": int(df["len_ad"].min()),
        "len_ad_max": int(df["len_ad"].max()),
        "pt_sources_present": sorted(df["pt_source"].unique().tolist()),
    }

    PROFILE_PATH.write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8")
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Profile salvo em: {PROFILE_PATH}")
    print(f"Manifest salvo em: {MANIFEST_PATH}")


if __name__ == "__main__":
    main()