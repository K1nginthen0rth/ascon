"""Experimento de instância fraca: Ascon-AEAD128 com p^b (rodadas por bloco)
reduzido abaixo do padrão.

Por que existe
---------------
O experimento principal (v2) compara os 4 algoritmos LWC usados
CORRETAMENTE e espera H0 — ciphertext-only não deveria distinguir
implementações corretas de algoritmos aprovados pelo NIST. Isso é um
resultado forte, mas puramente negativo. Este experimento busca a outra
metade da história: existe algum cenário DEMONSTRÁVEL em que
ciphertext-only ML consegue distinguir? A resposta não deveria estar entre
os 4 algoritmos corretos — deveria estar na fronteira onde alguém usa uma
instância enfraquecida.

Aqui a instância fraca é o Ascon-AEAD128 com `p^b` (a permutação aplicada a
cada bloco de 16 bytes durante o processamento de dados — 8 rodadas no
padrão SP 800-232) reduzido para 1–6 rodadas, mantendo tudo o resto idêntico
(`p^a`=12 na inicialização/finalização, mesmo IV, mesma carga
little-endian, mesmo padding). Reduzir `p^b` é a forma padrão de "instância
fraca" usada em criptoanálise de terceiros durante a avaliação do NIST LWC
— ataques diferencial/linear contra a permutação Ascon em contagem de
rodadas reduzida já foram publicados. A pergunta empírica não é se existe
um distinguidor em princípio — é se o MESMO pipeline de ML construído para
o experimento principal (features de ciphertext-only, RandomForest com
key-holdout) detecta a mesma fraqueza na prática, e a partir de qual
contagem de rodadas.

Duas comparações, para cada nível de `p^b` em {1, 2, 3, 4, 6}:
  1. Ascon-pb{R} vs. PRNG (AES-CTR/CTR_DRBG) — testa a definição de
     segurança real (ciphertext indistinguível de aleatório).
  2. Ascon-pb{R} vs. Ascon-pb8 (oficial) — testa se dá pra saber que o
     ciphertext NÃO veio da implementação recomendada.
`Ascon-pb8` entra nas duas comparações como âncora "deveria ser H0".

Protocolo (PILOTO — mais simples que a família primária pré-registrada,
propositalmente): 100 chaves (80 trainval / 20 teste, 80/20 — mesma
proporção do resto do projeto), 12 slots/chave, split ÚNICO por chave (sem
5-fold — se algum nível cruzar o limiar de detecção, o próximo passo é
rodar a família completa com CV, não este script). RandomForest oficial
(n_estimators=500, random_state=7 — Regra de Ouro 2), bootstrap por
CLUSTER de chave (Regra herdada da 6a auditoria do v2).

Uso
---
    python scripts/run_ascon_weak_rounds_experiment.py generate
    python scripts/run_ascon_weak_rounds_experiment.py extract --shard 0 --n-shards 8
    ... (repetir para shard 1..7, em paralelo)
    python scripts/run_ascon_weak_rounds_experiment.py consolidate
    python scripts/run_ascon_weak_rounds_experiment.py train
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from sklearn.ensemble import RandomForestClassifier

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src" / "crypto"))

from src.crypto.ascon_weak import ascon_weak_encrypt  # noqa: E402
from src.crypto.ctr_drbg import CTRDRBG  # noqa: E402
from src.eval.reporting import report_eval  # noqa: E402
from src.features.extractor import CiphertextFeatureExtractor  # noqa: E402
from scripts.generate_5class_v2 import _TextPlaintextSampler  # noqa: E402

OUT_DIR = REPO_ROOT / "data" / "interim" / "ascon_weak_rounds"
FEATURES_DIR = OUT_DIR / "features"
RAW_PARQUET = OUT_DIR / "raw_ciphertexts.parquet"
FEATURES_PARQUET = OUT_DIR / "features.parquet"
REPORTS_DIR = REPO_ROOT / "reports" / "v2" / "ascon_weak_rounds"

PB_LEVELS = (1, 2, 3, 4, 6, 8)  # 8 = oficial (âncora "deveria ser H0")
PB0_ALGO = "Ascon-pb0"  # caso extremo, gerado à parte (ver cmd_generate_pb0)
RAW_PARQUET_PB0 = OUT_DIR / "raw_ciphertexts_pb0.parquet"
N_KEYS = 100
N_TEST_KEYS = 20  # 80/20, mesma proporção do resto do projeto
N_SLOTS = 12
PLAINTEXT_BYTES = 65536
SEED = 42          # Regra de Ouro 1 (split)
MODEL_SEED = 7     # Regra de Ouro 1 (modelo)
KEY_SEED_OFFSET = 9000  # fora dos ranges já usados pelo v1 (2000) e v2 (6000)


# ---------------------------------------------------------------------------
# generate
# ---------------------------------------------------------------------------

def cmd_generate() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    key_drbg = CTRDRBG(seed=SEED + KEY_SEED_OFFSET, label="ascon_weak_rounds_keys")
    pt_drbg = CTRDRBG(seed=SEED + KEY_SEED_OFFSET + 1, label="ascon_weak_rounds_pt")
    prng_drbg = CTRDRBG(seed=SEED + KEY_SEED_OFFSET + 2, label="ascon_weak_rounds_prng")
    text_sampler = _TextPlaintextSampler(REPO_ROOT / "data" / "raw" / "corpora", pt_drbg)

    rf = np.random.RandomState(SEED)  # só para o split train/test de key_id (não material criptográfico)
    key_indices = np.arange(N_KEYS)
    rf.shuffle(key_indices)
    test_key_set = set(key_indices[:N_TEST_KEYS].tolist())

    schema = pa.schema([
        ("sample_id", pa.string()), ("algorithm", pa.string()), ("key_id", pa.string()),
        ("split", pa.string()), ("len_pt", pa.int64()), ("len_ct", pa.int64()),
        ("ciphertext", pa.binary()), ("plaintext_sha256", pa.string()),
    ])
    writer = pq.ParquetWriter(str(RAW_PARQUET), schema)
    t0 = time.time()
    n_written = 0

    for k in range(N_KEYS):
        key_id = f"awr_key_{k:04d}"
        key = key_drbg.random_key(16)
        split = "test" if k in test_key_set else "trainval"

        for slot in range(N_SLOTS):
            nonce = ((k * N_SLOTS + slot) + 1).to_bytes(16, "big")
            pt = text_sampler.sample()
            pt_hash = hashlib.sha256(pt).hexdigest()
            rows = []

            for pb in PB_LEVELS:
                ct = ascon_weak_encrypt(key, nonce, pt, b"", pb_rounds=pb)
                rows.append({
                    "sample_id": f"AsconPB{pb}_{key_id}_slot{slot:03d}",
                    "algorithm": f"Ascon-pb{pb}",
                    "key_id": key_id, "split": split,
                    "len_pt": len(pt), "len_ct": len(ct),
                    "ciphertext": ct, "plaintext_sha256": pt_hash,
                })

            prng_ct = prng_drbg.generate(len(pt) + 16)  # +16 = ABYTES, mesmo len_ct do Ascon
            rows.append({
                "sample_id": f"PRNG_{key_id}_slot{slot:03d}", "algorithm": "PRNG",
                "key_id": key_id, "split": split,
                "len_pt": 0, "len_ct": len(prng_ct),
                "ciphertext": prng_ct, "plaintext_sha256": "n/a",
            })

            writer.write_table(pa.Table.from_pylist(rows, schema=schema))
            n_written += len(rows)

        if (k + 1) % 10 == 0:
            print(f"  {k+1}/{N_KEYS} chaves ({n_written} amostras, "
                  f"{time.time()-t0:.0f}s)", flush=True)

    writer.close()
    print(f"OK: {n_written} amostras em {RAW_PARQUET} ({time.time()-t0:.0f}s)")
    print(f"  algoritmos: {[f'Ascon-pb{p}' for p in PB_LEVELS]} + PRNG")
    print(f"  chaves: {N_KEYS - N_TEST_KEYS} trainval / {N_TEST_KEYS} teste")


def cmd_generate_pb0() -> None:
    """Gera SÓ o caso extremo pb_rounds=0 (permutação = identidade).

    Qualitativamente diferente de reduzir rodadas: sem NENHUMA mistura
    entre blocos, o "keystream" de cada bloco é o XOR acumulado dos blocos
    de plaintext anteriores — tende a vazar estrutura do PRÓPRIO PLAINTEXT
    (detectável por estatística global), ao contrário de 1-6 rodadas, onde
    a saída já parece estatisticamente boa mesmo sem margem de segurança
    algébrica (ver `ascon_weak_encrypt.__doc__` e §5.14 do plano v2).

    Replica EXATAMENTE a mesma sequência de chamadas ao CTR_DRBG que
    `cmd_generate()` (mesmas seeds, mesma ordem: chave por `k`, plaintext
    por slot) para reusar as MESMAS chaves/nonces/plaintexts já gerados —
    sem isso, o split trainval/teste por chave não seria comparável entre
    os dois arquivos.
    """
    key_drbg = CTRDRBG(seed=SEED + KEY_SEED_OFFSET, label="ascon_weak_rounds_keys")
    pt_drbg = CTRDRBG(seed=SEED + KEY_SEED_OFFSET + 1, label="ascon_weak_rounds_pt")
    text_sampler = _TextPlaintextSampler(REPO_ROOT / "data" / "raw" / "corpora", pt_drbg)

    rf = np.random.RandomState(SEED)
    key_indices = np.arange(N_KEYS)
    rf.shuffle(key_indices)
    test_key_set = set(key_indices[:N_TEST_KEYS].tolist())

    schema = pa.schema([
        ("sample_id", pa.string()), ("algorithm", pa.string()), ("key_id", pa.string()),
        ("split", pa.string()), ("len_pt", pa.int64()), ("len_ct", pa.int64()),
        ("ciphertext", pa.binary()), ("plaintext_sha256", pa.string()),
    ])
    writer = pq.ParquetWriter(str(RAW_PARQUET_PB0), schema)
    t0 = time.time()
    n_written = 0

    for k in range(N_KEYS):
        key_id = f"awr_key_{k:04d}"
        key = key_drbg.random_key(16)
        split = "test" if k in test_key_set else "trainval"

        for slot in range(N_SLOTS):
            nonce = ((k * N_SLOTS + slot) + 1).to_bytes(16, "big")
            pt = text_sampler.sample()  # MESMA chamada, MESMA posição na sequência
            pt_hash = hashlib.sha256(pt).hexdigest()

            ct = ascon_weak_encrypt(key, nonce, pt, b"", pb_rounds=0)
            row = {
                "sample_id": f"AsconPB0_{key_id}_slot{slot:03d}", "algorithm": PB0_ALGO,
                "key_id": key_id, "split": split,
                "len_pt": len(pt), "len_ct": len(ct),
                "ciphertext": ct, "plaintext_sha256": pt_hash,
            }
            writer.write_table(pa.Table.from_pylist([row], schema=schema))
            n_written += 1

        if (k + 1) % 20 == 0:
            print(f"  {k+1}/{N_KEYS} chaves ({n_written} amostras, "
                  f"{time.time()-t0:.0f}s)", flush=True)

    writer.close()
    print(f"OK: {n_written} amostras em {RAW_PARQUET_PB0} ({time.time()-t0:.0f}s)")

    # Sanity: os plaintexts têm que ser EXATAMENTE os mesmos do dataset
    # principal por (key_id, slot) — senão os dois datasets não são
    # comparáveis (chave "vazando" um plaintext diferente do que os outros
    # níveis de pb_rounds usaram no mesmo slot).
    principal = pq.read_table(
        str(RAW_PARQUET), columns=["sample_id", "algorithm", "key_id", "split",
                                   "plaintext_sha256"]
    ).to_pandas()
    ref = principal[principal["algorithm"] == "Ascon-pb8"].copy()
    ref["slot"] = ref["sample_id"].str.extract(r"_slot(\d+)$").astype(int)
    ref = ref.set_index(["key_id", "slot"])[["split", "plaintext_sha256"]]

    novo = pq.read_table(
        str(RAW_PARQUET_PB0), columns=["sample_id", "key_id", "split", "plaintext_sha256"]
    ).to_pandas()
    novo["slot"] = novo["sample_id"].str.extract(r"_slot(\d+)$").astype(int)
    novo = novo.set_index(["key_id", "slot"])[["split", "plaintext_sha256"]]

    assert ref.index.equals(novo.index), "conjunto de (key_id, slot) diverge do principal"
    diverge = (ref["plaintext_sha256"] != novo["plaintext_sha256"]).sum()
    diverge_split = (ref["split"] != novo["split"]).sum()
    assert diverge == 0, f"{diverge} slots com plaintext_sha256 diferente do principal"
    assert diverge_split == 0, f"{diverge_split} slots com split (trainval/teste) diferente"
    print("  sanity OK: plaintexts e split idênticos ao dataset principal, slot a slot")


# ---------------------------------------------------------------------------
# extract
# ---------------------------------------------------------------------------

def cmd_extract(shard: int, n_shards: int, source: str = "main") -> None:
    FEATURES_DIR.mkdir(parents=True, exist_ok=True)
    raw_path = RAW_PARQUET if source == "main" else RAW_PARQUET_PB0
    df = pq.read_table(str(raw_path)).to_pandas()
    df = df.iloc[shard::n_shards].reset_index(drop=True)
    extractor = CiphertextFeatureExtractor()

    t0 = time.time()
    rows = []
    for i, row in df.iterrows():
        feats = extractor.extract(row["ciphertext"])
        feats.update({
            "sample_id": row["sample_id"], "algorithm": row["algorithm"],
            "key_id": row["key_id"], "split": row["split"],
        })
        rows.append(feats)
        if (i + 1) % 100 == 0:
            dt = time.time() - t0
            print(f"  [shard {shard}/{source}] {i+1}/{len(df)}  ({dt:.0f}s, "
                  f"{dt/(i+1):.2f}s/amostra)", flush=True)

    out = FEATURES_DIR / f"{source}_shard_{shard:02d}_of_{n_shards:02d}.parquet"
    pd.DataFrame(rows).to_parquet(out, index=False)
    print(f"OK: shard {shard}/{source} -> {out} ({len(rows)} amostras, {time.time()-t0:.0f}s)")


# ---------------------------------------------------------------------------
# consolidate
# ---------------------------------------------------------------------------

def cmd_consolidate() -> None:
    partes = sorted(FEATURES_DIR.glob("*_shard_*.parquet"))
    if not partes:
        raise SystemExit(f"Nenhum shard encontrado em {FEATURES_DIR}")
    dfs = [pd.read_parquet(p) for p in partes]
    full = pd.concat(dfs, ignore_index=True)

    n_esperado = len(pq.read_table(str(RAW_PARQUET), columns=["sample_id"]))
    if RAW_PARQUET_PB0.exists():
        n_esperado += len(pq.read_table(str(RAW_PARQUET_PB0), columns=["sample_id"]))
    print(f"Consolidado: {len(full)} amostras de {len(partes)} shards "
          f"(esperado: {n_esperado})")
    if len(full) != n_esperado:
        print("  AVISO: contagem não bate — confira se todos os shards rodaram.")
    if full["sample_id"].duplicated().any():
        raise SystemExit("sample_id duplicado entre shards — shards se sobrepuseram.")

    full.to_parquet(FEATURES_PARQUET, index=False)
    print(f"OK: {FEATURES_PARQUET}")
    print(full["algorithm"].value_counts().to_string())


# ---------------------------------------------------------------------------
# train
# ---------------------------------------------------------------------------

_NON_FEATURE_COLS = {"sample_id", "algorithm", "key_id", "split", "y"}


def _feature_columns(df: pd.DataFrame) -> list[str]:
    cols = [c for c in df.columns if c not in _NON_FEATURE_COLS]
    assert "y" not in cols and "algorithm" not in cols, "vazamento de rótulo em feature_columns"
    return cols


def _run_binary(df: pd.DataFrame, classe_positiva: str, classe_negativa: str,
                run_id: str) -> dict:
    sub = df[df["algorithm"].isin([classe_positiva, classe_negativa])].copy()
    sub["y"] = (sub["algorithm"] == classe_positiva).astype(int)
    feat_cols = _feature_columns(sub)

    tr = sub[sub["split"] == "trainval"]
    te = sub[sub["split"] == "test"]

    X_tr = tr[feat_cols].to_numpy(dtype=np.float64)
    X_te = te[feat_cols].to_numpy(dtype=np.float64)
    X_tr = np.nan_to_num(X_tr, nan=0.0, posinf=0.0, neginf=0.0)
    X_te = np.nan_to_num(X_te, nan=0.0, posinf=0.0, neginf=0.0)

    clf = RandomForestClassifier(
        n_estimators=500, max_depth=None, class_weight="balanced",
        random_state=MODEL_SEED, n_jobs=-1,
    )
    clf.fit(X_tr, tr["y"].to_numpy())
    y_pred = clf.predict(X_te)
    y_proba = clf.predict_proba(X_te)

    report = report_eval(
        run_id=run_id, caminho="piloto", modelo="RandomForest",
        braco="ascon_weak_rounds", fold="test",
        y_true=te["y"].to_numpy(), y_pred=y_pred, y_proba=y_proba,
        sample_ids=te["sample_id"].tolist(), key_ids=te["key_id"].tolist(),
        class_names=[classe_negativa, classe_positiva], labels=[0, 1],
        out_dir=REPORTS_DIR,
    )
    return {
        "comparacao": run_id, "positiva": classe_positiva, "negativa": classe_negativa,
        "n_test": len(te), "f1_macro": report.f1_macro,
        "f1_macro_ci_low": report.f1_macro_ci[0], "f1_macro_ci_high": report.f1_macro_ci[1],
        "balanced_accuracy": report.balanced_accuracy,
    }


def cmd_train() -> None:
    df = pd.read_parquet(FEATURES_PARQUET)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    resultados = []

    niveis = list(PB_LEVELS)
    tem_pb0 = PB0_ALGO in df["algorithm"].unique()
    if tem_pb0:
        niveis = [0] + niveis

    def _nome(pb: int) -> str:
        return PB0_ALGO if pb == 0 else f"Ascon-pb{pb}"

    print("\n=== Ascon-pb{R} vs. PRNG (indistinguível de aleatório?) ===")
    for pb in niveis:
        r = _run_binary(df, _nome(pb), "PRNG", run_id=f"ascon_pb{pb}_vs_prng")
        resultados.append({**r, "pb_rounds": pb, "eixo": "vs_PRNG"})
        print(f"  pb={pb:2d}  F1-macro={r['f1_macro']:.4f}  "
              f"IC95%=[{r['f1_macro_ci_low']:.4f}, {r['f1_macro_ci_high']:.4f}]")

    print("\n=== Ascon-pb{R} vs. Ascon-pb8 (oficial) — dá pra saber que não é o recomendado? ===")
    for pb in niveis:
        if pb == 8:
            continue
        r = _run_binary(df, _nome(pb), "Ascon-pb8", run_id=f"ascon_pb{pb}_vs_oficial")
        resultados.append({**r, "pb_rounds": pb, "eixo": "vs_oficial"})
        print(f"  pb={pb:2d}  F1-macro={r['f1_macro']:.4f}  "
              f"IC95%=[{r['f1_macro_ci_low']:.4f}, {r['f1_macro_ci_high']:.4f}]")

    out = pd.DataFrame(resultados)
    out_path = REPORTS_DIR / "resumo_pb_rounds.csv"
    out.to_csv(out_path, index=False)
    print(f"\nOK: {out_path}")

    print("\n=== Leitura ===")
    limiar_prng = out[(out["eixo"] == "vs_PRNG") & (out["f1_macro_ci_low"] > 0.55)]
    limiar_of = out[(out["eixo"] == "vs_oficial") & (out["f1_macro_ci_low"] > 0.55)]
    if len(limiar_prng):
        pior_pb = limiar_prng["pb_rounds"].max()
        print(f"  Menor rodada ainda indistinguível de PRNG (IC95% exclui F1>0,55): "
              f"pb > {pior_pb}")
    else:
        print("  Nenhum nível de pb_rounds testado ficou acima do acaso vs. PRNG "
              "(IC95% inclui F1<=0,55 em todos) — reduzir mais as rodadas ou "
              "aumentar a amostra.")
    if len(limiar_of):
        pior_pb = limiar_of["pb_rounds"].max()
        print(f"  Menor rodada ainda indistinguível do oficial (pb=8): pb > {pior_pb}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("generate")
    sub.add_parser("generate-pb0")
    p_ext = sub.add_parser("extract")
    p_ext.add_argument("--shard", type=int, default=0)
    p_ext.add_argument("--n-shards", type=int, default=1)
    p_ext.add_argument("--source", choices=["main", "pb0"], default="main")
    sub.add_parser("consolidate")
    sub.add_parser("train")
    args = ap.parse_args()

    if args.cmd == "generate":
        cmd_generate()
    elif args.cmd == "generate-pb0":
        cmd_generate_pb0()
    elif args.cmd == "extract":
        cmd_extract(args.shard, args.n_shards, args.source)
    elif args.cmd == "consolidate":
        cmd_consolidate()
    elif args.cmd == "train":
        cmd_train()


if __name__ == "__main__":
    main()
