"""
Validação dos datasets piloto Ascon-AEAD128.

Sanity checks:
  1. Estrutura do parquet (colunas, tipos, nulos)
  2. Completude (contagens por chave × tamanho, nonces únicos)
  3. χ² de uniformidade de bytes (por ciphertext ≥ 64 bytes)
  4. Compressibilidade (zlib, razão ≈ 1.0 para CT ≥ 64 bytes)
  5. Decrypt spot check (100 amostras aleatórias)
  6. Relatório JSON final

Uso:
    python scripts/validate_pilot_dataset.py

Saída: data/processed/<dataset_id>_validation.json
"""
from __future__ import annotations

import json
import os
import sys
import zlib
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import chisquare

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_REPO_ROOT / "src" / "crypto"))

from src.crypto.ascon_wrapper import AsconAEAD128, AuthenticationError

# ---------------------------------------------------------------------------
# Configuração de datasets a validar
# ---------------------------------------------------------------------------
_DATASETS = [
    {
        "dataset_id": "ascon_aead128_pilot_v2",
        "n_keys": 10,
        "pt_sizes": [0, 1, 8, 16, 32, 64, 128, 256, 512, 1024, 2048],
        "samples_per_key_size": 100,
    },
    {
        "dataset_id": "ascon_aead128_keyholdout_v2",
        "n_keys": 50,
        "pt_sizes": [64, 256, 1024],
        "samples_per_key_size": 50,
    },
]

_REQUIRED_COLUMNS = {
    "sample_id", "algorithm", "mode", "impl",
    "key_id", "nonce_id", "len_pt", "len_ad", "len_ct",
    "ciphertext", "plaintext_source", "seed", "version", "timestamp",
}

OUT_DIR     = _REPO_ROOT / "data" / "processed"
INTERIM_DIR = _REPO_ROOT / "data" / "interim"


# ---------------------------------------------------------------------------
# Checks individuais
# ---------------------------------------------------------------------------

def check_structure(df: pd.DataFrame, dataset_id: str) -> tuple[bool, list[str]]:
    """Verifica colunas obrigatórias, tipos e ausência de nulos."""
    errors: list[str] = []

    missing = _REQUIRED_COLUMNS - set(df.columns)
    if missing:
        errors.append(f"Colunas faltando: {missing}")

    null_counts = df.isnull().sum()
    nulls = null_counts[null_counts > 0]
    if not nulls.empty:
        errors.append(f"Nulos encontrados: {nulls.to_dict()}")

    if "len_ct" in df.columns and "len_pt" in df.columns:
        mismatch = df[df["len_ct"] != df["len_pt"] + 16]
        if not mismatch.empty:
            errors.append(
                f"{len(mismatch)} linhas com len_ct != len_pt + 16"
            )

    return len(errors) == 0, errors


def check_completeness(
    df: pd.DataFrame,
    n_keys: int,
    pt_sizes: list[int],
    samples_per_key_size: int,
) -> tuple[bool, list[str], bool]:
    """Verifica contagens e unicidade de nonces."""
    errors: list[str] = []

    expected_total = n_keys * len(pt_sizes) * samples_per_key_size
    if len(df) != expected_total:
        errors.append(
            f"Total esperado {expected_total}, obtido {len(df)}"
        )

    for kid in df["key_id"].unique():
        sub = df[df["key_id"] == kid]
        for sz in pt_sizes:
            cnt = len(sub[sub["len_pt"] == sz])
            if cnt != samples_per_key_size:
                errors.append(
                    f"{kid}/len_pt={sz}: esperado {samples_per_key_size}, "
                    f"obtido {cnt}"
                )

    # Unicidade de nonces por chave
    nonce_ok = True
    for kid in df["key_id"].unique():
        nids = df[df["key_id"] == kid]["nonce_id"]
        if nids.nunique() != len(nids):
            errors.append(f"Nonces repetidos em {kid}")
            nonce_ok = False

    return len(errors) == 0, errors, nonce_ok


def check_chi2_uniformity(
    df: pd.DataFrame,
    min_ct_len: int = 64,
    alpha: float = 0.05,
) -> dict:
    """
    Teste χ² de uniformidade de bytes para ciphertexts ≥ min_ct_len bytes.

    Hipótese nula: distribuição uniforme de bytes (256 bins).
    Esperado para ciphertexts bons: baixo percentual de rejeição.
    """
    sub = df[df["len_ct"] >= min_ct_len].copy()
    if sub.empty:
        return {"tested": 0, "mean": None, "std": None, "reject_pct_alpha05": None}

    chi2_vals: list[float] = []
    p_vals: list[float] = []

    for ct in sub["ciphertext"]:
        if not isinstance(ct, (bytes, bytearray)):
            continue
        arr = np.frombuffer(ct, dtype=np.uint8)
        counts = np.bincount(arr, minlength=256).astype(float)
        expected = np.full(256, len(arr) / 256.0)
        # Evitar bins com expected < 1 (invalida o χ²)
        if (expected < 1).any():
            continue
        stat, p = chisquare(counts, f_exp=expected)
        chi2_vals.append(float(stat))
        p_vals.append(float(p))

    if not chi2_vals:
        return {"tested": 0, "mean": None, "std": None, "reject_pct_alpha05": None}

    reject = sum(1 for p in p_vals if p < alpha)
    return {
        "tested": len(chi2_vals),
        "mean": round(float(np.mean(chi2_vals)), 2),
        "std": round(float(np.std(chi2_vals)), 2),
        "reject_pct_alpha05": round(reject / len(chi2_vals), 4),
        "min_ct_len_filter": min_ct_len,
    }


def check_compressibility(
    df: pd.DataFrame,
    min_ct_len: int = 64,
) -> dict:
    """
    Teste de compressibilidade com zlib.

    Razão = len(compressed) / len(original).
    Ciphertexts bons não devem comprimir (razão ≈ 1.0 ou > 1.0).
    """
    sub = df[df["len_ct"] >= min_ct_len].copy()
    if sub.empty:
        return {"tested": 0, "mean_ratio": None, "max_ratio": None}

    ratios: list[float] = []
    for ct in sub["ciphertext"]:
        if not isinstance(ct, (bytes, bytearray)):
            continue
        compressed = zlib.compress(bytes(ct), level=9)
        ratios.append(len(compressed) / len(ct))

    if not ratios:
        return {"tested": 0, "mean_ratio": None, "max_ratio": None}

    return {
        "tested": len(ratios),
        "mean_ratio": round(float(np.mean(ratios)), 4),
        "std_ratio": round(float(np.std(ratios)), 4),
        "max_ratio": round(float(np.max(ratios)), 4),
        "min_ratio": round(float(np.min(ratios)), 4),
        "min_ct_len_filter": min_ct_len,
    }


def check_decrypt_spot(
    df: pd.DataFrame,
    keys_path: Path,
    nonces_path: Path,
    plaintexts_path: Path,
    ascon: AsconAEAD128,
    n_samples: int = 100,
    seed: int = 42,
) -> dict:
    """
    Decrypt de n_samples amostras aleatórias e comparação com plaintext original.

    Carrega chaves/nonces de data/interim/, decifra, verifica conteúdo.
    """
    keys_map: dict[str, str] = json.loads(keys_path.read_text(encoding="utf-8"))
    nonces_map: dict[str, str] = json.loads(nonces_path.read_text(encoding="utf-8"))
    pt_df = pd.read_parquet(plaintexts_path)
    pt_lookup = dict(zip(pt_df["sample_id"], pt_df["plaintext"]))

    rng = np.random.default_rng(seed + 99)
    sample_idx = rng.choice(len(df), size=min(n_samples, len(df)), replace=False)
    sample_rows = df.iloc[sample_idx]

    passed = 0
    failed = 0
    errors: list[str] = []

    for _, row in sample_rows.iterrows():
        key_hex = keys_map.get(row["key_id"])
        nonce_hex = nonces_map.get(row["nonce_id"])
        expected_pt = pt_lookup.get(row["sample_id"])

        if key_hex is None or nonce_hex is None:
            errors.append(f"Chave/nonce não encontrado: {row['sample_id']}")
            failed += 1
            continue

        key = bytes.fromhex(key_hex)
        nonce = bytes.fromhex(nonce_hex)
        ct = bytes(row["ciphertext"]) if not isinstance(row["ciphertext"], bytes) \
             else row["ciphertext"]

        try:
            recovered = ascon.decrypt(key, nonce, ct, b"")
        except AuthenticationError as e:
            errors.append(f"AuthError em {row['sample_id']}: {e}")
            failed += 1
            continue
        except Exception as e:
            errors.append(f"Erro em {row['sample_id']}: {e}")
            failed += 1
            continue

        # Verificar conteúdo se plaintext disponível
        if expected_pt is not None:
            expected_bytes = bytes(expected_pt) if not isinstance(expected_pt, bytes) \
                             else expected_pt
            if recovered != expected_bytes:
                errors.append(
                    f"Conteúdo diverge em {row['sample_id']}: "
                    f"esperado {len(expected_bytes)}B, obtido {len(recovered)}B"
                )
                failed += 1
                continue

        # Verificar tamanho
        if len(recovered) != row["len_pt"]:
            errors.append(
                f"Tamanho diverge em {row['sample_id']}: "
                f"len_pt={row['len_pt']}, recovered={len(recovered)}"
            )
            failed += 1
            continue

        passed += 1

    return {
        "tested": passed + failed,
        "passed": passed,
        "failed": failed,
        "errors": errors[:5] if errors else [],
    }


# ---------------------------------------------------------------------------
# Função principal de validação
# ---------------------------------------------------------------------------

def validate_dataset(meta: dict, ascon: AsconAEAD128) -> dict:
    dataset_id = meta["dataset_id"]
    print(f"\n  Validando: {dataset_id}")

    # Caminhos
    pq_path  = OUT_DIR / f"{dataset_id}.parquet"
    keys_path     = INTERIM_DIR / f"{dataset_id}_keys.json"
    nonces_path   = INTERIM_DIR / f"{dataset_id}_nonces.json"
    pt_path       = INTERIM_DIR / f"{dataset_id}_plaintexts.parquet"
    manifest_path = OUT_DIR / f"{dataset_id}_manifest.json"

    if not pq_path.exists():
        return {"dataset_id": dataset_id, "verdict": "ERROR", "detail": "Parquet não encontrado"}

    df = pd.read_parquet(pq_path)
    print(f"    Carregado: {len(df):,} linhas, {len(df.columns)} colunas")

    # 1. Estrutura
    struct_ok, struct_errors = check_structure(df, dataset_id)
    print(f"    Estrutura: {'OK' if struct_ok else 'FALHOU'}")
    if not struct_ok:
        print(f"      {struct_errors}")

    # 2. Completude
    complete_ok, complete_errors, nonce_ok = check_completeness(
        df,
        n_keys=meta["n_keys"],
        pt_sizes=meta["pt_sizes"],
        samples_per_key_size=meta["samples_per_key_size"],
    )
    print(f"    Completude: {'OK' if complete_ok else 'FALHOU'}")
    print(f"    Nonces únicos: {'OK' if nonce_ok else 'FALHOU'}")
    if not complete_ok:
        print(f"      {complete_errors[:3]}")

    # 3. χ²
    chi2_result = check_chi2_uniformity(df)
    if chi2_result["tested"] > 0:
        print(
            f"    chi2 ({chi2_result['tested']} amostras >=64B): "
            f"mean={chi2_result['mean']}, "
            f"reject@a=0.05: {chi2_result['reject_pct_alpha05']*100:.1f}%"
        )
    else:
        print("    chi2: sem amostras elegiveis")

    # 4. Compressibilidade
    comp_result = check_compressibility(df)
    if comp_result["tested"] > 0:
        print(
            f"    Compressão ({comp_result['tested']} amostras): "
            f"mean_ratio={comp_result['mean_ratio']}"
        )
    else:
        print("    Compressao: sem amostras elegiveis")

    # 5. Decrypt spot check
    if keys_path.exists() and nonces_path.exists() and pt_path.exists():
        spot_result = check_decrypt_spot(df, keys_path, nonces_path, pt_path, ascon)
        print(
            f"    Decrypt spot ({spot_result['tested']}): "
            f"{spot_result['passed']}/{spot_result['tested']} OK"
        )
        if spot_result["errors"]:
            for e in spot_result["errors"]:
                print(f"      ! {e}")
    else:
        spot_result = {"tested": 0, "passed": 0, "failed": 0, "errors": ["arquivos interim não encontrados"]}
        print("    Decrypt spot: arquivos interim nao encontrados")

    # Veredicto
    chi2_ok = (
        chi2_result.get("reject_pct_alpha05") is None
        or chi2_result["reject_pct_alpha05"] < 0.10
    )
    comp_ok = (
        comp_result.get("mean_ratio") is None
        or comp_result["mean_ratio"] > 0.99
    )
    spot_ok = spot_result["passed"] == spot_result["tested"] and spot_result["tested"] > 0

    all_ok = struct_ok and complete_ok and nonce_ok and chi2_ok and comp_ok and spot_ok
    verdict = "PASS" if all_ok else "FAIL"
    print(f"    Veredicto: {verdict}")

    report = {
        "validation_date": datetime.now(timezone.utc).isoformat(),
        "dataset_id": dataset_id,
        "structure_ok": struct_ok,
        "structure_errors": struct_errors,
        "completeness_ok": complete_ok,
        "completeness_errors": complete_errors[:10],
        "nonce_uniqueness_ok": nonce_ok,
        "chi2_uniformity": chi2_result,
        "compressibility": comp_result,
        "decrypt_spot_check": spot_result,
        "verdict": verdict,
    }

    # Salvar relatório
    report_path = OUT_DIR / f"{dataset_id}_validation.json"
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"    Relatório: {report_path.name}")

    # Atualizar manifesto com sanity checks
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest is not None:
            manifest["sanity_checks"] = {
                "verdict": verdict,
                "chi2_uniformity": chi2_result,
                "compressibility": comp_result,
                "decrypt_spot_check": {
                    k: v for k, v in spot_result.items() if k != "errors"
                },
            }
            manifest_path.write_text(
                json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        else:
            print("    Aviso: manifest nulo no disco - execute generate_pilot_dataset.py para regenerar")

    return report


def main() -> None:
    print("Validacao de datasets piloto Ascon-AEAD128")
    print(f"{'='*60}")

    ascon = AsconAEAD128()
    reports = []

    for meta in _DATASETS:
        report = validate_dataset(meta, ascon)
        reports.append(report)

    print(f"\n{'='*60}")
    print("  SUMÁRIO")
    for r in reports:
        print(f"  {r['dataset_id']}: {r.get('verdict', 'ERROR')}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
