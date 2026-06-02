"""Validacao do dataset 3-classes de controle positivo."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(_REPO / "src" / "crypto"))

from src.crypto.aes_ecb_wrapper    import AES128ECB
from src.crypto.ascon_wrapper       import AsconAEAD128
from src.crypto.gift_cofb_wrapper   import GiftCOFB

DATASET_ID  = "control_3class_v1"
OUT_DIR     = _REPO / "data" / "processed"
INTERIM_DIR = _REPO / "data" / "interim"


def main() -> None:
    pq = OUT_DIR / f"{DATASET_ID}.parquet"
    df = pd.read_parquet(pq)
    print(f"\n  Validacao: {DATASET_ID}")
    print(f"  Total: {len(df):,}, colunas: {len(df.columns)}")

    # Totais por algoritmo
    counts = df["algorithm"].value_counts().to_dict()
    print(f"  Algoritmos: {counts}")
    expected = 15030
    total_ok = all(counts[a] == expected for a in
                   ["Ascon-AEAD128", "GIFT-COFB", "AES-128-ECB"])
    print(f"  Totais (15030 cada): {'OK' if total_ok else 'FAIL'}")

    # Splits disjuntos
    train_keys = set(df.loc[df["split"] == "train", "key_id"].unique())
    val_keys   = set(df.loc[df["split"] == "val",   "key_id"].unique())
    test_keys  = set(df.loc[df["split"] == "test",  "key_id"].unique())
    splits_ok  = not (train_keys & test_keys or train_keys & val_keys or val_keys & test_keys)
    print(f"  Chaves disjuntas: train={len(train_keys)}, val={len(val_keys)}, "
          f"test={len(test_keys)}  {'OK' if splits_ok else 'FAIL'}")

    # CT lengths por algoritmo
    print(f"  CT lengths por algoritmo:")
    for algo in df["algorithm"].unique():
        lens = sorted(df[df["algorithm"] == algo]["len_ct"].unique().tolist())
        print(f"    {algo:18s} {lens}")

    # Decrypt spot check
    print(f"  Decrypt spot check (10/algo):")
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
            expected = bytes(pt_lookup[(row["key_id"], row["nonce_id"], int(row["len_pt"]))])
            if rec != expected:
                print(f"    {algo}/{row['sample_id']}: PT diverge")
                spot_ok = False
                continue
            passed += 1
        print(f"    {algo:18s} {passed}/10")

    # Verificacao adicional: ECB determinismo
    # Para cada (key, len_pt) no ECB, encripto duas vezes e checo igualdade
    print(f"  ECB determinismo (sanity):")
    ecb = ciphers["AES-128-ECB"]
    ecb_sub = df[df["algorithm"] == "AES-128-ECB"]
    sample_a = ecb_sub.iloc[0]
    sample_b = ecb_sub[(ecb_sub["key_id"] == sample_a["key_id"]) &
                       (ecb_sub["len_pt"] == sample_a["len_pt"])].iloc[1]
    pt_a = pt_lookup[(sample_a["key_id"], sample_a["nonce_id"], int(sample_a["len_pt"]))]
    ct_a = ecb.encrypt(bytes.fromhex(keys_map[sample_a["key_id"]]),
                       bytes(16), bytes(pt_a), b"")
    ct_a2 = ecb.encrypt(bytes.fromhex(keys_map[sample_a["key_id"]]),
                        b"\xff" * 16, bytes(pt_a), b"")
    print(f"    nonce diferente -> mesmo CT: {'OK' if ct_a == ct_a2 else 'FAIL'}")

    verdict = "PASS" if (total_ok and splits_ok and spot_ok) else "FAIL"
    print(f"\n  VEREDICTO: {verdict}")


if __name__ == "__main__":
    main()
