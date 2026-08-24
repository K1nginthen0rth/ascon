"""
Validação do dataset v2 (5 classes: Ascon, GIFT-COFB, Grain-128AEAD,
Schwaemm256-128, AES-128-ECB + controle PRNG). Ver
docs/plano_experimento_v2/06_implementacao_passo_a_passo.md Fase 4.3.

Sanity checks:
  1. Totais por algoritmo (30.000 cada dos 5 reais + 30.000 PRNG = 180.000)
  2. Unicidade dos BYTES de nonce derivados (não do rótulo `nonce_id`, que é
     único por construção): reconstrói o nonce de cada algoritmo a partir do
     contador e mede colisões globais e reuso dentro de uma mesma chave. É no
     Grain-128AEAD que isso tem conteúdo — o contador de 128 bits vira 12
     bytes por truncamento. AES-ECB e PRNG não usam nonce
  3. χ² de uniformidade + compressibilidade — desvio ESPERADO no AES-ECB
     (reportado, não faz a validação falhar — é o controle positivo)
  4. Decrypt spot-check (100 amostras/algoritmo real; PRNG pulado — não
     tem operação de decrypt)
  5. Proporção texto/imagem (~80/20) global e por split (train/test)
  6. Encadeamento: mesma chave+nonce -> mesmo plaintext_sha256 nas 5
     linhas de cifra reais de cada slot
  7. Overlap de plaintext_sha256 entre trainval e test (medido e
     reportado, não é critério de falha — ver 04_protocolo_metricas_validacao.md §4.6 item 6)
"""
from __future__ import annotations

import json
import sys
import zlib
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from scipy.stats import chisquare

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src" / "crypto"))

from src.crypto.aes_ecb_wrapper import AES128ECB  # noqa: E402
from src.crypto.ascon_wrapper import AsconAEAD128, AuthenticationError  # noqa: E402
from src.crypto.gift_cofb_wrapper import GiftCOFB  # noqa: E402
from src.crypto.grain_wrapper import Grain128AEAD  # noqa: E402
from src.crypto.sparkle_wrapper import Schwaemm256_128  # noqa: E402
from scripts.generate_5class_v2 import _nonce_for_algorithm  # noqa: E402

DATASET_ID = "keyholdout_5class_v2"
OUT_DIR = REPO_ROOT / "data" / "processed"
INTERIM_DIR = REPO_ROOT / "data" / "interim"

PQ = OUT_DIR / f"{DATASET_ID}.parquet"
KEYS_JSON = INTERIM_DIR / f"{DATASET_ID}_keys.json"
FOLDS_JSON = OUT_DIR / "v2_folds.json"

REAL_ALGORITHMS = (
    "Ascon-AEAD128", "GIFT-COFB", "Grain-128AEAD", "Schwaemm256-128", "AES-128-ECB",
)
EXPECTED_PER_ALGO = 30_000


def _chi2(df: pd.DataFrame, algo: str, sample_n: int = 300) -> dict:
    sub = df[(df["algorithm"] == algo) & (df["len_ct"] >= 64)]
    sub = sub.sample(min(sample_n, len(sub)), random_state=42)
    chi2_vals, p_vals = [], []
    for ct in sub["ciphertext"]:
        arr = np.frombuffer(bytes(ct), dtype=np.uint8)
        counts = np.bincount(arr, minlength=256).astype(float)
        expected = np.full(256, len(arr) / 256.0)
        stat, p = chisquare(counts, f_exp=expected)
        chi2_vals.append(float(stat))
        p_vals.append(float(p))
    if not chi2_vals:
        return {"tested": 0}
    reject = sum(1 for p in p_vals if p < 0.05)
    return {
        "tested": len(chi2_vals),
        "mean": round(float(np.mean(chi2_vals)), 2),
        "reject_pct_alpha05": round(reject / len(chi2_vals), 4),
    }


def _comp(df: pd.DataFrame, algo: str, sample_n: int = 300) -> dict:
    sub = df[(df["algorithm"] == algo) & (df["len_ct"] >= 64)]
    sub = sub.sample(min(sample_n, len(sub)), random_state=42)
    ratios = [len(zlib.compress(bytes(ct), level=9)) / len(ct) for ct in sub["ciphertext"]]
    return {
        "tested": len(ratios),
        "mean_ratio": round(float(np.mean(ratios)), 4),
    }


def _decrypt_spot_check(
    df: pd.DataFrame, keys_map: dict, ciphers: dict, n_per_algo: int = 20,
) -> dict:
    """100 amostras total (n_per_algo x 5 algoritmos reais); PRNG pulado
    (não tem operação de decrypt)."""
    rng = np.random.default_rng(42)
    passed, failed, errors = 0, 0, []
    for algo, cipher in ciphers.items():
        sub = df[df["algorithm"] == algo]
        idx = rng.choice(len(sub), size=min(n_per_algo, len(sub)), replace=False)
        for _, row in sub.iloc[idx].iterrows():
            key = bytes.fromhex(keys_map[row["key_id"]])
            nonce_num = int(row["nonce_id"].split("_")[1])
            counter_bytes = nonce_num.to_bytes(16, "big")
            nonce = _nonce_for_algorithm(counter_bytes, cipher.NPUBBYTES)
            ct = bytes(row["ciphertext"])
            try:
                pt = cipher.decrypt(key, nonce, ct, b"")
            except AuthenticationError as e:
                errors.append(f"{algo}/{row['sample_id']}: AuthError {e}")
                failed += 1
                continue
            if hashlib_sha256(pt) != row["plaintext_sha256"]:
                errors.append(f"{algo}/{row['sample_id']}: sha256 diverge")
                failed += 1
                continue
            passed += 1
    return {"tested": passed + failed, "passed": passed, "failed": failed, "errors": errors[:10]}


def hashlib_sha256(data: bytes) -> str:
    import hashlib
    return hashlib.sha256(data).hexdigest()


_METADATA_COLUMNS = [
    "sample_id", "algorithm", "mode", "key_id", "nonce_id", "len_pt",
    "len_ct", "plaintext_source", "plaintext_sha256", "image_id",
]


def _load_metadata_only(pq_path: Path) -> pd.DataFrame:
    """Lê todas as 180k linhas mas SEM a coluna `ciphertext` (~65KB/linha,
    ~11,8GB no total) — só os campos leves, usados pela maioria dos
    checks (totais, nonces, encadeamento, proporção, overlap). Carregar
    o parquet inteiro (com ciphertext) esgotou a RAM disponível numa
    tentativa anterior (confirmado: sistema caiu para 0,13GB livres e o
    processo precisou ser morto) — nenhum desses checks precisa do
    ciphertext bruto."""
    return pd.read_parquet(pq_path, columns=_METADATA_COLUMNS)


def _sample_with_ciphertext(
    pq_path: Path, n_row_groups: int = 4, seed: int = 42,
) -> pd.DataFrame:
    """Lê só um punhado de ROW GROUPS completos (não o arquivo inteiro)
    para os checks que precisam do ciphertext de verdade (χ²,
    compressão, decrypt spot-check). Cada row group tem ~6.000 linhas
    (10 chaves x 100 slots x 6 linhas) — 4 row groups ≈ 24.000 linhas
    (~1,6GB), suficiente para amostras de até algumas centenas por
    algoritmo sem se aproximar do limite de memória."""
    pf = pq.ParquetFile(pq_path)
    rng = np.random.default_rng(seed)
    chosen = rng.choice(pf.num_row_groups, size=min(n_row_groups, pf.num_row_groups), replace=False)
    tables = [pf.read_row_group(int(i)) for i in chosen]
    return pa.concat_tables(tables).to_pandas()


def _check_encadeamento(df: pd.DataFrame) -> dict:
    real = df[df["algorithm"] != "PRNG"]
    grouped = real.groupby(["key_id", "nonce_id"])["plaintext_sha256"].nunique()
    n_inconsistent = int((grouped > 1).sum())
    sizes = real.groupby(["key_id", "nonce_id"]).size()
    n_wrong_size = int((sizes != len(REAL_ALGORITHMS)).sum())
    return {
        "n_slots_checked": len(grouped),
        "n_slots_inconsistent_plaintext": n_inconsistent,
        "n_slots_wrong_algorithm_count": n_wrong_size,
        "ok": n_inconsistent == 0 and n_wrong_size == 0,
    }


_NPUB_POR_ALGORITMO = {
    "Ascon-AEAD128": AsconAEAD128.NPUBBYTES,
    "GIFT-COFB": GiftCOFB.NPUBBYTES,
    "Grain-128AEAD": Grain128AEAD.NPUBBYTES,
    "Schwaemm256-128": Schwaemm256_128.NPUBBYTES,
}


def _check_nonce_uniqueness(df: pd.DataFrame) -> dict:
    """Unicidade dos BYTES de nonce derivados, não do rótulo `nonce_id`.

    A versão anterior contava duplicatas de (key_id, nonce_id). `nonce_id` é a
    string do contador global, então era única POR CONSTRUÇÃO e a checagem
    passava sem olhar o que de fato entrou na cifra. O que importa é se os
    bytes colidem — em particular no Grain-128AEAD, onde o contador de 128 bits
    vira 12 bytes por truncamento. Achado na auditoria criptográfica de
    2026-08-24.

    AES-128-ECB e PRNG não usam nonce e ficam de fora.
    """
    ok = True
    detalhes: dict[str, dict] = {}

    for algo, npub in _NPUB_POR_ALGORITMO.items():
        sub_idx = df.index[df["algorithm"] == algo]
        if len(sub_idx) == 0:
            continue
        # int() do Python, não int64: o contador é um rótulo e não deve estourar
        # em silêncio. Só as linhas deste algoritmo — o PRNG grava nonce_id="n/a".
        derivados = [
            _nonce_for_algorithm(int(str(s).removeprefix("nonce_")).to_bytes(16, "big"), npub)
            for s in df.loc[sub_idx, "nonce_id"]
        ]
        n_total = len(derivados)
        n_distintos = len(set(derivados))
        comprimentos = {len(b) for b in derivados}
        # reuso DENTRO de uma mesma chave é o caso fatal para AEAD
        por_chave = pd.DataFrame({"key_id": df.loc[sub_idx, "key_id"].to_numpy(),
                                  "nonce": derivados})
        chaves_com_reuso = int(
            por_chave.groupby("key_id")["nonce"].apply(lambda s: s.duplicated().any()).sum()
        )
        detalhes[algo] = {
            "npub_bytes": sorted(comprimentos),
            "nonces_derivados": n_total,
            "distintos": n_distintos,
            "colisoes_globais": n_total - n_distintos,
            "chaves_com_reuso": chaves_com_reuso,
        }
        if n_distintos != n_total or chaves_com_reuso > 0 or comprimentos != {npub}:
            ok = False

    return {"ok": ok, "por_algoritmo": detalhes}


def _check_plaintext_source_ratio(df: pd.DataFrame, folds: dict | None) -> dict:
    real = df[df["plaintext_source"] != "n/a"]
    # Uma linha por SLOT (não por algoritmo) para não pesar a proporção 5x.
    per_slot = real.drop_duplicates(subset=["key_id", "nonce_id"])
    global_ratio = per_slot["plaintext_source"].value_counts(normalize=True).round(4).to_dict()

    by_split = {}
    if folds is not None:
        test_keys = set(folds["test_keys"])
        trainval_keys = set(folds["trainval_keys"])
        for split_name, keys in (("test", test_keys), ("trainval", trainval_keys)):
            sub = per_slot[per_slot["key_id"].isin(keys)]
            by_split[split_name] = (
                sub["plaintext_source"].value_counts(normalize=True).round(4).to_dict()
            )
    return {"global": global_ratio, "by_split": by_split}


def _check_plaintext_overlap(df: pd.DataFrame, folds: dict | None) -> dict:
    """Mede (não bloqueia) overlap de plaintext_sha256 entre trainval e
    test — ver 04_protocolo_metricas_validacao.md §4.6 item 6."""
    if folds is None:
        return {"skipped": "v2_folds.json não encontrado"}
    real = df[df["plaintext_source"] != "n/a"]
    test_keys = set(folds["test_keys"])
    trainval_keys = set(folds["trainval_keys"])
    test_hashes = set(real.loc[real["key_id"].isin(test_keys), "plaintext_sha256"])
    trainval_hashes = set(real.loc[real["key_id"].isin(trainval_keys), "plaintext_sha256"])
    overlap = test_hashes & trainval_hashes
    return {
        "n_unique_test_plaintexts": len(test_hashes),
        "n_unique_trainval_plaintexts": len(trainval_hashes),
        "n_overlapping": len(overlap),
        "overlap_pct_of_test": round(len(overlap) / max(len(test_hashes), 1), 4),
    }


def main() -> None:
    # Windows: stdout redirecionado (arquivo/pipe) usa cp1252 por padrão,
    # que não cobre χ (usado nos prints abaixo) — força UTF-8.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    print(f"\n{'=' * 60}\n  Validação: {DATASET_ID}\n{'=' * 60}")

    if not PQ.exists():
        print(f"FAIL: parquet não encontrado em {PQ}")
        sys.exit(1)

    df = _load_metadata_only(PQ)
    print(f"  Carregado (metadados, sem ciphertext): {len(df):,} linhas, "
          f"{len(df.columns)} colunas")
    df_sample = _sample_with_ciphertext(PQ, n_row_groups=4, seed=42)
    print(f"  Amostra com ciphertext (χ²/compressão/decrypt): "
          f"{len(df_sample):,} linhas de {pq.ParquetFile(PQ).num_row_groups} row groups")

    # --- Totais ---
    counts = df["algorithm"].value_counts().to_dict()
    print(f"  Algoritmos: {counts}")
    total_ok = (
        all(counts.get(a) == EXPECTED_PER_ALGO for a in REAL_ALGORITHMS)
        and counts.get("PRNG") == EXPECTED_PER_ALGO
        and len(df) == EXPECTED_PER_ALGO * 6
    )
    print(f"  Totais (5x{EXPECTED_PER_ALGO} reais + {EXPECTED_PER_ALGO} PRNG): "
          f"{'OK' if total_ok else 'FAIL'}")

    # --- Nonces ---
    nonce_check = _check_nonce_uniqueness(df)
    print(f"  Bytes de nonce derivados, únicos por algoritmo e sem reuso por chave: "
          f"{'OK' if nonce_check['ok'] else 'FAIL'}")
    for _algo, _d in nonce_check["por_algoritmo"].items():
        print(f"    {_algo:18s} npub={_d['npub_bytes']} distintos="
              f"{_d['distintos']}/{_d['nonces_derivados']} "
              f"chaves_com_reuso={_d['chaves_com_reuso']}")

    # --- Encadeamento ---
    chain_check = _check_encadeamento(df)
    print(f"  Encadeamento (mesma chave+nonce -> mesmo plaintext_sha256 "
          f"nas {len(REAL_ALGORITHMS)} linhas reais): "
          f"{'OK' if chain_check['ok'] else 'FAIL'} — {chain_check}")

    # --- χ² / compressão por algoritmo (ECB: desvio esperado, não falha) ---
    chi2_by_algo, comp_by_algo = {}, {}
    chi2_ok = True
    for algo in REAL_ALGORITHMS:
        chi2_by_algo[algo] = _chi2(df_sample, algo)
        comp_by_algo[algo] = _comp(df_sample, algo)
        reject = chi2_by_algo[algo].get("reject_pct_alpha05", 0)
        print(f"  χ²[{algo}] reject@0.05={reject * 100:.1f}%  "
              f"compressão={comp_by_algo[algo].get('mean_ratio')}"
              + ("  (desvio esperado — controle ECB)" if algo == "AES-128-ECB" else ""))
        if algo != "AES-128-ECB" and reject >= 0.10:
            chi2_ok = False

    # --- Proporção texto/imagem ---
    folds = json.loads(FOLDS_JSON.read_text(encoding="utf-8")) if FOLDS_JSON.exists() else None
    ratio_check = _check_plaintext_source_ratio(df, folds)
    print(f"  Proporção texto/imagem global: {ratio_check['global']}")
    for split_name, ratio in ratio_check["by_split"].items():
        print(f"    por split [{split_name}]: {ratio}")
    ratio_ok = abs(ratio_check["global"].get("imagem", 0) - 0.20) < 0.03

    # --- Overlap de plaintext entre splits (medido, não bloqueia) ---
    overlap_check = _check_plaintext_overlap(df, folds)
    print(f"  Overlap de plaintext trainval/test: {overlap_check}")

    # --- Decrypt spot-check ---
    spot_ok = True
    spot = {"skipped": True}
    if KEYS_JSON.exists():
        keys_map = json.loads(KEYS_JSON.read_text(encoding="utf-8"))
        ciphers = {
            "Ascon-AEAD128": AsconAEAD128(),
            "GIFT-COFB": GiftCOFB(),
            "Grain-128AEAD": Grain128AEAD(),
            "Schwaemm256-128": Schwaemm256_128(),
            "AES-128-ECB": AES128ECB(),
        }
        spot = _decrypt_spot_check(df_sample, keys_map, ciphers, n_per_algo=20)
        print(f"  Decrypt spot-check ({spot['tested']}): {spot['passed']}/{spot['tested']} OK")
        for e in spot["errors"]:
            print(f"     ! {e}")
        spot_ok = spot["failed"] == 0 and spot["passed"] > 0
    else:
        print(f"  Decrypt spot-check: PULADO (chaves não encontradas em {KEYS_JSON})")

    verdict = "PASS" if (
        total_ok and nonce_check["ok"] and chain_check["ok"] and chi2_ok
        and ratio_ok and spot_ok
    ) else "FAIL"
    print(f"\n  VEREDICTO: {verdict}")

    report = {
        "validation_date": datetime.now(timezone.utc).isoformat(),
        "dataset_id": DATASET_ID,
        "totals": counts,
        "totals_ok": total_ok,
        "nonce_uniqueness": nonce_check,
        "encadeamento": chain_check,
        "chi2_by_algorithm": chi2_by_algo,
        "compressibility_by_algorithm": comp_by_algo,
        "plaintext_source_ratio": ratio_check,
        "plaintext_overlap_trainval_test": overlap_check,
        "decrypt_spot_check": spot,
        "verdict": verdict,
    }
    rp = OUT_DIR / f"{DATASET_ID}_validation.json"
    rp.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"  Relatório: {rp.name}")


if __name__ == "__main__":
    main()
