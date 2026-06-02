"""
Validacao do dataset 2-classes 50k (Ascon + GIFT-COFB).

Sanity checks:
  1. Totais por algoritmo (50.100 cada, 100.200 total)
  2. Nonces unicos por chave
  3. chi2 de uniformidade (reject_pct < 10% a alpha=0.05)
  4. Compressibilidade zlib (mean_ratio > 0.99)
  5. Decrypt spot check 100 amostras (50 Ascon + 50 GIFT-COFB)
  6. Splits disjuntos (train/val/test)
"""
from __future__ import annotations

import json
import sys
import zlib
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import chisquare

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(_REPO / "src" / "crypto"))

from src.crypto.ascon_wrapper    import AsconAEAD128, AuthenticationError
from src.crypto.gift_cofb_wrapper import GiftCOFB

DATASET_ID  = "keyholdout_2class_50k_v1"
OUT_DIR     = _REPO / "data" / "processed"
INTERIM_DIR = _REPO / "data" / "interim"

PQ          = OUT_DIR     / f"{DATASET_ID}.parquet"
KEYS_JSON   = INTERIM_DIR / f"{DATASET_ID}_keys.json"
NONCES_JSON = INTERIM_DIR / f"{DATASET_ID}_nonces.json"
PT_PARQUET  = INTERIM_DIR / f"{DATASET_ID}_plaintexts.parquet"
SPLITS_JSON = OUT_DIR     / f"{DATASET_ID}_splits.json"


def _chi2(df: pd.DataFrame, sample_n: int = 1000) -> dict:
    """chi2 sobre amostra aleatoria de ciphertexts >= 64 bytes."""
    sub = df[df["len_ct"] >= 64].sample(min(sample_n, len(df)), random_state=42)
    chi2_vals, p_vals = [], []
    for ct in sub["ciphertext"]:
        arr = np.frombuffer(bytes(ct), dtype=np.uint8)
        counts = np.bincount(arr, minlength=256).astype(float)
        expected = np.full(256, len(arr) / 256.0)
        if (expected < 1).any():
            continue
        stat, p = chisquare(counts, f_exp=expected)
        chi2_vals.append(float(stat))
        p_vals.append(float(p))
    if not chi2_vals:
        return {"tested": 0}
    reject = sum(1 for p in p_vals if p < 0.05)
    return {
        "tested": len(chi2_vals),
        "mean":   round(float(np.mean(chi2_vals)), 2),
        "std":    round(float(np.std(chi2_vals)),  2),
        "reject_pct_alpha05": round(reject / len(chi2_vals), 4),
    }


def _comp(df: pd.DataFrame, sample_n: int = 1000) -> dict:
    sub = df[df["len_ct"] >= 64].sample(min(sample_n, len(df)), random_state=42)
    ratios = [len(zlib.compress(bytes(ct), level=9)) / len(ct) for ct in sub["ciphertext"]]
    return {
        "tested":     len(ratios),
        "mean_ratio": round(float(np.mean(ratios)), 4),
        "max_ratio":  round(float(np.max(ratios)),  4),
        "min_ratio":  round(float(np.min(ratios)),  4),
    }


def _decrypt_spot(df: pd.DataFrame, keys_map, nonces_map, pt_lookup,
                  ascon: AsconAEAD128, gift: GiftCOFB,
                  n_per_algo: int = 50, seed: int = 42) -> dict:
    rng = np.random.default_rng(seed)
    passed, failed, errors = 0, 0, []
    for algo, cipher in [("Ascon-AEAD128", ascon), ("GIFT-COFB", gift)]:
        sub = df[df["algorithm"] == algo]
        idx = rng.choice(len(sub), size=min(n_per_algo, len(sub)), replace=False)
        for _, row in sub.iloc[idx].iterrows():
            key   = bytes.fromhex(keys_map[row["key_id"]])
            nonce = bytes.fromhex(nonces_map[row["nonce_id"]])
            ct    = bytes(row["ciphertext"])
            try:
                rec = cipher.decrypt(key, nonce, ct, b"")
            except AuthenticationError as e:
                errors.append(f"{algo}/{row['sample_id']}: AuthError {e}")
                failed += 1
                continue
            # plaintext lookup pela tupla (key_id, nonce_id, len_pt)
            pt_key = (row["key_id"], row["nonce_id"], int(row["len_pt"]))
            expected = pt_lookup.get(pt_key)
            if expected is None:
                errors.append(f"{algo}/{row['sample_id']}: PT nao encontrado")
                failed += 1
                continue
            if rec != bytes(expected):
                errors.append(f"{algo}/{row['sample_id']}: PT diverge")
                failed += 1
                continue
            passed += 1
    return {
        "tested": passed + failed,
        "passed": passed,
        "failed": failed,
        "errors": errors[:5],
    }


def main() -> None:
    print(f"\n{'='*60}\n  Validacao: {DATASET_ID}\n{'='*60}")

    if not PQ.exists():
        print(f"FAIL: parquet nao encontrado em {PQ}")
        sys.exit(1)

    df = pd.read_parquet(PQ)
    print(f"  Carregado: {len(df):,} linhas, {len(df.columns)} colunas")

    # --- Totais por algoritmo ---
    counts = df["algorithm"].value_counts().to_dict()
    print(f"  Algoritmos: {counts}")
    total_ok = (counts.get("Ascon-AEAD128") == 50100
                and counts.get("GIFT-COFB")  == 50100
                and len(df) == 100200)
    print(f"  Totais: {'OK' if total_ok else 'FAIL'}")

    # --- Nonces por chave (devem ser unicos por algoritmo) ---
    nonce_ok = True
    for kid in df["key_id"].unique():
        for algo in df["algorithm"].unique():
            sub = df[(df["key_id"] == kid) & (df["algorithm"] == algo)]
            if sub["nonce_id"].nunique() != len(sub):
                nonce_ok = False
                break
    print(f"  Nonces unicos por (chave,algo): {'OK' if nonce_ok else 'FAIL'}")

    # --- Splits disjuntos ---
    split_counts = df["split"].value_counts().to_dict()
    print(f"  Splits: {split_counts}")
    train_keys = set(df.loc[df["split"] == "train", "key_id"].unique())
    val_keys   = set(df.loc[df["split"] == "val",   "key_id"].unique())
    test_keys  = set(df.loc[df["split"] == "test",  "key_id"].unique())
    splits_ok = not (train_keys & test_keys or train_keys & val_keys or val_keys & test_keys)
    print(f"  Chaves disjuntas: train={len(train_keys)}, val={len(val_keys)}, "
          f"test={len(test_keys)}  {'OK' if splits_ok else 'FAIL'}")

    # --- chi2 ---
    chi2 = _chi2(df, sample_n=1000)
    print(f"  chi2 (n={chi2['tested']}): mean={chi2.get('mean')}, "
          f"reject@a=0.05: {chi2.get('reject_pct_alpha05', 0)*100:.1f}%")
    chi2_ok = chi2.get("reject_pct_alpha05", 0) < 0.10

    # --- compressibilidade ---
    comp = _comp(df, sample_n=1000)
    print(f"  compressao (n={comp['tested']}): mean_ratio={comp['mean_ratio']}")
    comp_ok = comp["mean_ratio"] > 0.99

    # --- decrypt spot check ---
    keys_map   = json.loads(KEYS_JSON.read_text(encoding="utf-8"))
    nonces_map = json.loads(NONCES_JSON.read_text(encoding="utf-8"))
    pt_df      = pd.read_parquet(PT_PARQUET)
    # plaintexts identificados por (key_id, nonce_id, len_pt)
    pt_lookup = {
        (row["key_id"], row["nonce_id"], int(row["len_pt"])): row["plaintext"]
        for _, row in pt_df.iterrows()
    }
    ascon = AsconAEAD128()
    gift  = GiftCOFB()
    spot  = _decrypt_spot(df, keys_map, nonces_map, pt_lookup, ascon, gift,
                          n_per_algo=50)
    print(f"  decrypt spot ({spot['tested']}): "
          f"{spot['passed']}/{spot['tested']} OK")
    if spot["errors"]:
        for e in spot["errors"]:
            print(f"     ! {e}")
    spot_ok = spot["failed"] == 0 and spot["passed"] > 0

    verdict = "PASS" if (total_ok and nonce_ok and splits_ok and chi2_ok and
                         comp_ok and spot_ok) else "FAIL"
    print(f"\n  VEREDICTO: {verdict}")

    report = {
        "validation_date":  datetime.now(timezone.utc).isoformat(),
        "dataset_id":       DATASET_ID,
        "totals":           counts,
        "totals_ok":        total_ok,
        "nonce_uniqueness_ok": nonce_ok,
        "splits":           split_counts,
        "splits_disjoint_ok": splits_ok,
        "chi2_uniformity":  chi2,
        "compressibility":  comp,
        "decrypt_spot_check": spot,
        "verdict":          verdict,
    }
    rp = OUT_DIR / f"{DATASET_ID}_validation.json"
    rp.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  Relatorio: {rp.name}")


if __name__ == "__main__":
    main()
