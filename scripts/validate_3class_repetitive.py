"""
Validacao do dataset 3-classes repetitivo (controle B).

NOTA esperada: chi2 do ECB tera reject_pct ALTO (PTs repetitivos -> CTs com
blocos repetidos). Para Ascon e GIFT, chi2 deve permanecer baixo.
"""
from __future__ import annotations

import json
import sys
import zlib
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import chisquare

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(_REPO / "src" / "crypto"))

from src.crypto.aes_ecb_wrapper    import AES128ECB
from src.crypto.ascon_wrapper       import AsconAEAD128
from src.crypto.gift_cofb_wrapper   import GiftCOFB

DATASET_ID  = "control_repetitive_3class_v1"
OUT_DIR     = _REPO / "data" / "processed"
INTERIM_DIR = _REPO / "data" / "interim"


def _chi2_per_algo(df: pd.DataFrame, sample_n: int = 500) -> dict:
    """chi2 por algoritmo, sampleado de CTs >= 64 bytes."""
    out = {}
    for algo in df["algorithm"].unique():
        sub = df[(df["algorithm"] == algo) & (df["len_ct"] >= 64)].sample(
            min(sample_n, len(df[df["algorithm"] == algo])), random_state=42)
        rejects = 0; n = 0
        chi2_vals = []
        for ct in sub["ciphertext"]:
            arr = np.frombuffer(bytes(ct), dtype=np.uint8)
            counts = np.bincount(arr, minlength=256).astype(float)
            expected = np.full(256, len(arr) / 256.0)
            if (expected < 1).any():
                continue
            stat, p = chisquare(counts, f_exp=expected)
            chi2_vals.append(float(stat))
            if p < 0.05:
                rejects += 1
            n += 1
        out[algo] = {
            "tested": n,
            "mean":   round(float(np.mean(chi2_vals)), 2) if chi2_vals else None,
            "reject_pct_alpha05": round(rejects / n, 4) if n else None,
        }
    return out


def main() -> None:
    pq = OUT_DIR / f"{DATASET_ID}.parquet"
    df = pd.read_parquet(pq)
    print(f"\n  Validacao: {DATASET_ID}")
    print(f"  Total: {len(df):,}, colunas: {len(df.columns)}")

    counts = df["algorithm"].value_counts().to_dict()
    print(f"  Algoritmos: {counts}")
    expected = 15030
    total_ok = all(counts[a] == expected for a in
                   ["Ascon-AEAD128", "GIFT-COFB", "AES-128-ECB"])
    print(f"  Totais (15030 cada): {'OK' if total_ok else 'FAIL'}")

    train = set(df.loc[df["split"] == "train", "key_id"].unique())
    val   = set(df.loc[df["split"] == "val",   "key_id"].unique())
    test  = set(df.loc[df["split"] == "test",  "key_id"].unique())
    splits_ok = not (train & test or train & val or val & test)
    print(f"  Chaves disjuntas: train={len(train)}, val={len(val)}, "
          f"test={len(test)}  {'OK' if splits_ok else 'FAIL'}")

    # chi2 por algoritmo - ECB esperado ALTO, AEADs esperados baixos
    print(f"\n  chi2 por algoritmo (esperado: ECB alto, AEAD baixo):")
    chi2 = _chi2_per_algo(df, sample_n=500)
    for algo, d in chi2.items():
        print(f"    {algo:18s} mean={d['mean']:>8.1f}  "
              f"reject@a=0.05: {d['reject_pct_alpha05']*100:>5.1f}%  "
              f"(n={d['tested']})")

    # Compressibilidade tambem deve diferir
    print(f"\n  compressao zlib por algoritmo (esperado: ECB comprime):")
    for algo in df["algorithm"].unique():
        sub = df[df["algorithm"] == algo].sample(500, random_state=42)
        ratios = [len(zlib.compress(bytes(ct), level=9)) / len(ct)
                  for ct in sub["ciphertext"]]
        print(f"    {algo:18s} mean_ratio={np.mean(ratios):.4f}  "
              f"min={np.min(ratios):.4f}  max={np.max(ratios):.4f}")

    # Decrypt spot check
    print(f"\n  Decrypt spot check (10/algo):")
    keys_map   = json.loads((INTERIM_DIR / f"{DATASET_ID}_keys.json").read_text())
    nonces_map = json.loads((INTERIM_DIR / f"{DATASET_ID}_nonces.json").read_text())
    pt_df      = pd.read_parquet(INTERIM_DIR / f"{DATASET_ID}_plaintexts.parquet")
    pt_lookup  = {(r["key_id"], r["nonce_id"], int(r["len_pt"])): r["plaintext"]
                  for _, r in pt_df.iterrows()}

    ciphers = {
        "Ascon-AEAD128": AsconAEAD128(),
        "GIFT-COFB":     GiftCOFB(),
        "AES-128-ECB":   AES128ECB(),
    }
    rng = np.random.default_rng(42)
    spot_ok = True
    for algo, cipher in ciphers.items():
        sub = df[df["algorithm"] == algo]
        idx = rng.choice(len(sub), 10, replace=False)
        passed = 0
        for _, row in sub.iloc[idx].iterrows():
            key   = bytes.fromhex(keys_map[row["key_id"]])
            nonce = bytes.fromhex(nonces_map[row["nonce_id"]])
            ct    = bytes(row["ciphertext"])
            try:
                rec = cipher.decrypt(key, nonce, ct, b"")
            except Exception as e:
                print(f"    {algo}/{row['sample_id']}: ERRO {e}")
                spot_ok = False
                continue
            expected = bytes(pt_lookup[(row["key_id"], row["nonce_id"],
                                         int(row["len_pt"]))])
            if rec != expected:
                spot_ok = False
                continue
            passed += 1
        print(f"    {algo:18s} {passed}/10")

    verdict = "PASS" if (total_ok and splits_ok and spot_ok) else "FAIL"
    print(f"\n  VEREDICTO: {verdict}")
    print(f"  (chi2 alto no ECB e' ESPERADO - vazamento de bloco do modo)")


if __name__ == "__main__":
    main()
