"""
Valida uma variante compilada por `build_variant.py` contra os vetores de
teste oficiais (defaults) ou contra o oráculo Python independente (rodadas
reduzidas — só Ascon e GIFT têm oráculo hoje).

Uso:
    python scripts/reduced_rounds/validate_variant.py --all-baseline
        # os 3 .pyd na spec, contra os 1.089 KATs oficiais de cada um

    python scripts/reduced_rounds/validate_variant.py --algo ascon --pa 12 --pb 4 --n-random 500
        # variante reduzida, contra o oráculo Python (amostragem aleatória)
"""
from __future__ import annotations

import argparse
import os
import random
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tests"))

from src.crypto.kat_parser import parse_kat_file  # noqa: E402
from scripts.reduced_rounds.reduced_wrapper import ReducedRoundsCipher  # noqa: E402
from scripts.reduced_rounds.build_variant import (  # noqa: E402
    build_ascon, build_gift, build_schwaemm,
)

_KAT_ASCON = REPO_ROOT / "data" / "kat" / "LWC_AEAD_KAT_ASCON128AV13.txt"
_KAT_GIFT = REPO_ROOT / "data" / "kat" / "LWC_AEAD_KAT_GIFTCOFB128_128.txt"
_KAT_SCHWAEMM = REPO_ROOT / "data" / "kat" / "LWC_AEAD_KAT_SCHWAEMM256_128.txt"


def validate_against_kat(pyd_path: Path, algo: str, kat_path: Path) -> None:
    cipher = ReducedRoundsCipher(pyd_path, algo)
    vetores = parse_kat_file(kat_path)
    ruins = []
    for v in vetores:
        try:
            ct = cipher.encrypt(v.key, v.nonce, v.pt, v.ad)
        except Exception as e:  # noqa: BLE001
            ruins.append((v.count, f"exceção: {e}"))
            continue
        if ct != v.ct:
            ruins.append((v.count, "CT divergente"))
    total = len(vetores)
    ok = total - len(ruins)
    status = "PASS" if not ruins else "FAIL"
    print(f"[{algo}] {pyd_path.name}: {ok}/{total} KATs — {status}")
    if ruins:
        print(f"  primeiros divergentes: {ruins[:10]}")
        raise SystemExit(1)


def validate_against_oracle_ascon(pyd_path: Path, pa: int, pb: int, n_random: int) -> None:
    from tests.test_crypto_independente import ascon_aead128_encrypt  # noqa: E402

    cipher = ReducedRoundsCipher(pyd_path, "ascon")
    rng = random.Random(20260910)
    ruins = []
    for i in range(n_random):
        key = bytes(rng.getrandbits(8) for _ in range(16))
        nonce = bytes(rng.getrandbits(8) for _ in range(16))
        pt_len = rng.choice([0, 1, 15, 16, 17, 63, 64, 65, 300])
        ad_len = rng.choice([0, 1, 20, 64])
        pt = bytes(rng.getrandbits(8) for _ in range(pt_len))
        ad = bytes(rng.getrandbits(8) for _ in range(ad_len))
        esperado = ascon_aead128_encrypt(key, nonce, pt, ad, pa=pa, pb=pb)
        obtido = cipher.encrypt(key, nonce, pt, ad)
        if obtido != esperado:
            ruins.append(i)
    status = "PASS" if not ruins else "FAIL"
    print(f"[ascon pa={pa} pb={pb}] {pyd_path.name}: "
          f"{n_random - len(ruins)}/{n_random} vs. oráculo Python — {status}")
    if ruins:
        raise SystemExit(1)


def validate_against_oracle_gift(pyd_path: Path, rounds: int, n_random: int) -> None:
    from tests.test_crypto_independente import gift_cofb_encrypt  # noqa: E402

    cipher = ReducedRoundsCipher(pyd_path, "gift")
    rng = random.Random(20260910)
    ruins = []
    for i in range(n_random):
        key = bytes(rng.getrandbits(8) for _ in range(16))
        nonce = bytes(rng.getrandbits(8) for _ in range(16))
        pt_len = rng.choice([0, 1, 15, 16, 17, 63, 64, 65, 300])
        ad_len = rng.choice([0, 1, 20, 64])
        pt = bytes(rng.getrandbits(8) for _ in range(pt_len))
        ad = bytes(rng.getrandbits(8) for _ in range(ad_len))
        esperado = gift_cofb_encrypt(key, nonce, pt, ad, rounds=rounds)
        obtido = cipher.encrypt(key, nonce, pt, ad)
        if obtido != esperado:
            ruins.append(i)
    status = "PASS" if not ruins else "FAIL"
    print(f"[gift rounds={rounds}] {pyd_path.name}: "
          f"{n_random - len(ruins)}/{n_random} vs. oráculo Python — {status}")
    if ruins:
        raise SystemExit(1)


def validate_roundtrip_only(pyd_path: Path, algo: str, n_random: int) -> None:
    """Sem oráculo (Schwaemm): valida só que encrypt/decrypt fecham o ciclo
    e que o comprimento do CT é o esperado — não prova corretude criptográfica
    da redução, só ausência de erro grosseiro (buffer, off-by-one)."""
    cipher = ReducedRoundsCipher(pyd_path, algo)
    spec = cipher.spec
    rng = random.Random(20260910)
    ruins = []
    for i in range(n_random):
        key = bytes(rng.getrandbits(8) for _ in range(spec.key_bytes))
        nonce = bytes(rng.getrandbits(8) for _ in range(spec.nonce_bytes))
        pt_len = rng.choice([0, 1, 15, 16, 17, 63, 64, 65, 300])
        pt = bytes(rng.getrandbits(8) for _ in range(pt_len))
        ct = cipher.encrypt(key, nonce, pt)
        if len(ct) != pt_len + spec.tag_bytes:
            ruins.append((i, "comprimento errado"))
            continue
        rt = cipher.decrypt(key, nonce, ct)
        if rt != pt:
            ruins.append((i, "roundtrip falhou"))
    status = "PASS" if not ruins else "FAIL"
    print(f"[{algo}] {pyd_path.name}: {n_random - len(ruins)}/{n_random} roundtrip — {status}"
          " (sem oráculo — não prova corretude, só ausência de erro grosseiro)")
    if ruins:
        print(f"  falhas: {ruins[:10]}")
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all-baseline", action="store_true")
    parser.add_argument("--algo", choices=["ascon", "gift", "schwaemm"])
    parser.add_argument("--pa", type=int, default=12)
    parser.add_argument("--pb", type=int, default=8)
    parser.add_argument("--rounds", type=int, default=40)
    parser.add_argument("--slim", type=int, default=7)
    parser.add_argument("--big", type=int, default=11)
    parser.add_argument("--n-random", type=int, default=500)
    args = parser.parse_args()

    if args.all_baseline:
        validate_against_kat(build_ascon(12, 8), "ascon", _KAT_ASCON)
        validate_against_kat(build_gift(40), "gift", _KAT_GIFT)
        validate_against_kat(build_schwaemm(7, 11), "schwaemm", _KAT_SCHWAEMM)
        sys.exit(0)

    if args.algo == "ascon":
        pyd = build_ascon(args.pa, args.pb)
        if args.pa == 12 and args.pb == 8:
            validate_against_kat(pyd, "ascon", _KAT_ASCON)
        else:
            validate_against_oracle_ascon(pyd, args.pa, args.pb, args.n_random)
    elif args.algo == "gift":
        pyd = build_gift(args.rounds)
        if args.rounds == 40:
            validate_against_kat(pyd, "gift", _KAT_GIFT)
        else:
            validate_against_oracle_gift(pyd, args.rounds, args.n_random)
    elif args.algo == "schwaemm":
        pyd = build_schwaemm(args.slim, args.big)
        if args.slim == 7 and args.big == 11:
            validate_against_kat(pyd, "schwaemm", _KAT_SCHWAEMM)
        else:
            validate_roundtrip_only(pyd, "schwaemm", args.n_random)
