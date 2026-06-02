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
OUT_PATH = ROOT / "data" / "processed" / "ascon_aead128_variable_sizes_v1.parquet"

CRYPTO_KEYBYTES = 16
CRYPTO_NPUBBYTES = 16
CRYPTO_ABYTES = 16

# Tamanhos de plaintext para testar
PT_SIZES = [0, 1, 8, 16, 32, 64, 128, 256, 512, 1024, 2048]
SAMPLES_PER_SIZE = 1000  # 1000 amostras por tamanho = 11.000 total

LEN_AD = 64  # AD fixo

ALGO_ID = "Ascon-AEAD128_SP800-232"
ASCON_COMMIT = "b7ca60b"
ASCON_TAG = "v1.3.0"
ASCON_CRYPTO_VERSION = "1.3.0"
IMPL = "ref"
TAG_LEN = 128
SEED = "variable_sizes_v1"

PROFILE_PATH = ROOT / "data" / "processed" / "ascon_aead128_variable_sizes_v1_profile.json"
MANIFEST_PATH = ROOT / "data" / "processed" / "ascon_aead128_variable_sizes_v1_manifest.json"


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
    total_samples = 0

    # Para cada tamanho de plaintext
    for len_pt in PT_SIZES:
        print(f"Gerando {SAMPLES_PER_SIZE} amostras com plaintext size = {len_pt} bytes...")
        
        for sample_idx in range(SAMPLES_PER_SIZE):
            nonce = rand_bytes(CRYPTO_NPUBBYTES)
            while nonce in seen_nonces:
                nonce = rand_bytes(CRYPTO_NPUBBYTES)
            seen_nonces.add(nonce)

            # Se len_pt é 0, gerar plaintext vazio
            if len_pt == 0:
                pt = b""
                pt_source = "empty"
            else:
                pt, pt_source = generator.sample(len_pt)

            ad = rand_bytes(LEN_AD)

            ct, tag = encrypt_with_wrapper(key, nonce, ad, pt)

            assert len(pt) == len_pt, f"Tamanho PT mismatch: esperado {len_pt}, obtido {len(pt)}"
            assert len(ad) == LEN_AD
            assert len(ct) == len(pt)
            assert len(tag) == CRYPTO_ABYTES

            rows.append(
                {
                    "sample_id": total_samples,
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

            total_samples += 1
            
            if (sample_idx + 1) % 100 == 0:
                print(f"  ... {sample_idx + 1}/{SAMPLES_PER_SIZE} amostras geradas")

    df = pd.DataFrame(rows)
    df.to_parquet(OUT_PATH, index=False)

    print(f"\n✅ Parquet salvo em: {OUT_PATH}")
    print(f"Total de amostras: {len(df)}")
    print(f"Nonces únicos: {df['nonce'].nunique()}")
    print(f"Tamanhos de plaintext presentes: {sorted(df['len_pt'].unique().tolist())}")
    print(f"Distribuição por tamanho:")
    for size in PT_SIZES:
        count = len(df[df['len_pt'] == size])
        print(f"  - {size:4d} bytes: {count:,} amostras")

    profile = {
        "dataset_id": "ascon_aead128_variable_sizes_v1",
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
            "source": "natural_text_only (except size 0)",
            "corpora": "all_txt_files_in_data_raw_corpora",
            "encoding": "utf-8",
            "len_pt_values_bytes": PT_SIZES,
            "samples_per_size": SAMPLES_PER_SIZE,
        },
        "ad_policy": {
            "source": "random_bytes",
            "len_ad_range_bytes": [LEN_AD, LEN_AD],
        },
        "schema_fields": list(df.columns),
        "purpose": "Test model behavior across different plaintext lengths",
    }

    manifest = {
        "dataset_id": "ascon_aead128_variable_sizes_v1",
        "output_file": OUT_PATH.name,
        "n_samples": len(df),
        "ascon_tag": ASCON_TAG,
        "ascon_commit": ASCON_COMMIT,
        "implementation": IMPL,
        "seed": SEED,
        "key_regime": "session_key",
        "nonce_policy": "unique_per_key",
        "plaintext_sizes": PT_SIZES,
        "samples_per_size": SAMPLES_PER_SIZE,
        "len_pt_min": int(df["len_pt"].min()),
        "len_pt_max": int(df["len_pt"].max()),
        "len_pt_distribution": {str(size): int(count) for size, count in df["len_pt"].value_counts().items()},
        "len_ad_min": int(df["len_ad"].min()),
        "len_ad_max": int(df["len_ad"].max()),
        "pt_sources_present": sorted(df["pt_source"].unique().tolist()),
    }

    PROFILE_PATH.write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8")
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n✅ Profile salvo em: {PROFILE_PATH}")
    print(f"✅ Manifest salvo em: {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
