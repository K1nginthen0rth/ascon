"""
Extração das 641 features do dataset v2 (180.000 amostras). Insumo
obrigatório do Caminho A (e do braço clássico do Caminho D). Ver
docs/plano_experimento_v2/06_implementacao_passo_a_passo.md Fase 2/6.

**Braços de truncamento** (`--branch`), ver `01_algoritmos_e_dataset.md` §1.6:
  - `cru`         : CT com o comprimento real de cada algoritmo (Grain
                    65.544; os demais 65.552).
  - `controlado`  : todos os CTs cortados para 65.544 bytes (remove os 8
                    bytes finais do CT bruto) — braço PRIMÁRIO da hipótese.
  - `shuffled`    : controle negativo — bytes de cada CT permutados
                    deterministicamente (CTR_DRBG com seed derivada do
                    `sample_id`), destrói estrutura sequencial e preserva
                    o histograma.

**Regra dura:** as features de tag (`tag_region`) são SEMPRE calculadas
sobre o CT **cru**, em qualquer braço — cortar os últimos bytes removeria
metade da tag dos algoritmos com ABYTES=16 e a extração passaria a contar
bytes de payload como tag, silenciosamente. Ver `02_features_e_selecao.md`.

**Memória (ver feedback de sessão):** o parquet de entrada tem 11,8GB; este
script NUNCA o carrega inteiro — lê row group por row group
(`pyarrow.parquet.ParquetFile.read_row_group`) e grava um parquet de saída
por chunk. Retomável: chunks já gravados são pulados, então uma queda de
sessão custa no máximo um chunk.

Uso (paralelismo = N processos independentes, ver `extract`):
    # 6 processos em paralelo sobre o mesmo braço
    for i in 0 1 2 3 4 5; do
        python scripts/extract_features_v2.py --branch controlado \
            --shard $i --n-shards 6 &
    done; wait

    # depois, juntar os chunks num parquet único
    python scripts/extract_features_v2.py --branch controlado --consolidate
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

from src.crypto.ctr_drbg import CTRDRBG  # noqa: E402
from src.features.extractor import _FAMILY_FUNCS  # noqa: E402

DATASET_ID = "keyholdout_5class_v2"
PQ_IN = REPO_ROOT / "data" / "processed" / f"{DATASET_ID}.parquet"

# Comprimento comum do braço `controlado`: o menor len_ct do conjunto
# (Grain-128AEAD, tag de 8 bytes). Todos os CTs são cortados para cá.
CONTROLLED_LEN = 65544

METADATA_COLUMNS = [
    "sample_id", "algorithm", "key_id", "nonce_id",
    "len_pt", "len_ct", "plaintext_source", "plaintext_sha256",
]
# Famílias calculadas sobre o CT do braço; `tag_region` fica de fora
# porque é sempre calculada sobre o CT cru (ver docstring do módulo).
_BRANCH_FAMILIES = [f for f in _FAMILY_FUNCS if f != "tag_region"]
_TAG_FAMILY = "tag_region"


def _shuffle_ct(ct: bytes, sample_id: str) -> bytes:
    """
    Permutação determinística dos bytes do CT (controle negativo
    `shuffled`): destrói a estrutura sequencial e preserva exatamente o
    histograma de bytes. Reprodutível e independente por amostra, via
    CTR_DRBG (Regra de Ouro 8 — sem NumPy RNG para material do dataset).

    Seed derivada do SHA-256 do `sample_id` INTEIRO, não de um prefixo:
    os `sample_id` começam pelo nome do algoritmo (`Ascon-AEAD128_...`),
    então qualquer derivação por prefixo daria a MESMA permutação para
    todas as amostras de um mesmo algoritmo — o controle negativo viraria
    uma transformação constante por classe, exatamente o tipo de artefato
    que ele deveria descartar.

    Permutação obtida por `argsort` de chaves uint32 geradas em UMA
    chamada batelada do DRBG (~0,17s), em vez de Fisher-Yates com uma
    chamada por posição (65.552 chamadas, ~3,3s/amostra — inviável).
    Empates de chave (~0,5 esperados em 65k elementos com chaves de 32
    bits) são desempatados pelo índice via ordenação estável: desvio
    desprezível da uniformidade para o propósito deste controle.
    """
    seed = int.from_bytes(hashlib.sha256(sample_id.encode("utf-8")).digest()[:4], "big")
    drbg = CTRDRBG(seed=seed, label="shuffle_bytes")
    arr = np.frombuffer(ct, dtype=np.uint8)
    keys = np.frombuffer(drbg.generate(arr.size * 4), dtype=np.uint32)
    perm = np.argsort(keys, kind="stable")
    return arr[perm].tobytes()


def _ct_for_branch(ct: bytes, branch: str, sample_id: str) -> bytes:
    if branch == "cru":
        return ct
    if branch == "controlado":
        return ct[:CONTROLLED_LEN]
    if branch == "shuffled":
        return _shuffle_ct(ct, sample_id)
    raise ValueError(f"braço desconhecido: {branch!r}")


def _extract_row(row: dict, branch: str) -> dict:
    """Extrai as 641 features de uma amostra. Função de nível de módulo
    (exigência do joblib com backend de processos)."""
    ct_raw = bytes(row["ciphertext"])
    ct_branch = _ct_for_branch(ct_raw, branch, row["sample_id"])

    out = {col: row[col] for col in METADATA_COLUMNS if col in row}
    out["branch"] = branch
    for family in _BRANCH_FAMILIES:
        out.update(_FAMILY_FUNCS[family](ct_branch))
    # Tag SEMPRE do CT cru, independentemente do braço (ver docstring).
    out.update(_FAMILY_FUNCS[_TAG_FAMILY](ct_raw))
    return out


def extract(
    branch: str, out_dir: Path, limit_chunks: int | None,
    sub_batch: int = 250, shard: int = 0, n_shards: int = 1,
) -> None:
    """
    Extrai as features de cada row group e grava um parquet por chunk.

    **Paralelismo por SHARD de processos independentes, não por joblib.**
    A primeira versão usava `joblib.Parallel` sobre as linhas; morria com
    `TerminatedWorkerError` de forma reprodutível neste ambiente (Windows +
    spawn + numba JIT em cada worker), mesmo com sub-lotes pequenos e
    memória livre de sobra — enquanto a mesma função rodava sem problema
    em processo único. Em vez de insistir, o paralelismo passou para o
    nível mais grosso e mais robusto possível: cada processo cuida de um
    subconjunto disjunto de row groups (`gi % n_shards == shard`), lê o
    próprio dado e não troca payload nenhum com os outros. Sem IPC, sem
    pickling de ciphertexts de 65KB, sem pool de workers para morrer.

    Rode N processos em paralelo pelo shell:
        for i in 0 1 2 3; do python scripts/extract_features_v2.py \
            --branch controlado --shard $i --n-shards 4 & done

    **Streaming dentro do row group (`sub_batch`):** um row group tem
    6.000 linhas x ~65KB = ~390MB de payload. `iter_batches(row_groups=[gi])`
    lê em lotes de `sub_batch` linhas, mantendo o pico em ~16MB por
    processo em vez de 390MB — importante porque N shards rodam ao mesmo
    tempo (ver a nota de segurança de memória do projeto).
    """
    pf = pq.ParquetFile(PQ_IN)
    n_groups = pf.num_row_groups
    if limit_chunks is not None:
        n_groups = min(n_groups, limit_chunks)
    out_dir.mkdir(parents=True, exist_ok=True)

    my_groups = [gi for gi in range(n_groups) if gi % n_shards == shard]
    tag = f"shard {shard + 1}/{n_shards}" if n_shards > 1 else "processo único"
    print(f"Extraindo braço={branch} ({tag}): {len(my_groups)} de {n_groups} "
          f"row groups, sub_batch={sub_batch}", flush=True)

    read_cols = METADATA_COLUMNS + ["ciphertext"]
    t_start = time.perf_counter()
    n_done_rows = 0

    for gi in my_groups:
        chunk_path = out_dir / f"chunk_{gi:04d}.parquet"
        if chunk_path.exists():
            print(f"  [rg {gi}] já existe, pulando", flush=True)
            continue

        t0 = time.perf_counter()
        results: list[dict] = []
        for batch in pf.iter_batches(batch_size=sub_batch, row_groups=[gi],
                                     columns=read_cols):
            for row in batch.to_pylist():
                results.append(_extract_row(row, branch))
            del batch

        df_out = pd.DataFrame(results)
        # float32 nas features: metade da memória/disco, precisão muito
        # acima do necessário para p-values e proporções (as colunas de
        # metadados, que são str/int, ficam intactas).
        float_cols = df_out.select_dtypes(include=["float64"]).columns
        df_out[float_cols] = df_out[float_cols].astype(np.float32)
        # Gravação atômica: escreve num temporário e renomeia, para que
        # um chunk interrompido no meio não fique parcial em disco e
        # seja "pulado" como se estivesse completo na retomada.
        tmp_path = chunk_path.with_suffix(f".parquet.tmp{shard}")
        df_out.to_parquet(tmp_path, index=False)
        tmp_path.replace(chunk_path)

        n_rows = len(results)
        n_done_rows += n_rows
        dt = time.perf_counter() - t0
        elapsed = time.perf_counter() - t_start
        print(f"  [rg {gi}] {n_rows} amostras em {dt:.0f}s "
              f"({dt / max(n_rows, 1) * 1000:.0f}ms/amostra) — "
              f"acumulado {n_done_rows:,} / {elapsed / 60:.1f}min", flush=True)
        del results, df_out

    print(f"\nShard concluído em {(time.perf_counter() - t_start) / 60:.1f}min. "
          f"Chunks em {out_dir}")


def consolidate(branch: str, out_dir: Path) -> None:
    """Junta os chunks num único parquet de features. O resultado
    (180k x ~650 colunas float32) tem ~460MB — cabe em memória, ao
    contrário do parquet de ciphertexts."""
    chunks = sorted(out_dir.glob("chunk_*.parquet"))
    if not chunks:
        raise FileNotFoundError(f"Nenhum chunk encontrado em {out_dir}")
    print(f"Consolidando {len(chunks)} chunks de {out_dir}...")
    df = pd.concat([pd.read_parquet(c) for c in chunks], ignore_index=True)
    out_path = REPO_ROOT / "data" / "processed" / f"{DATASET_ID}_features_{branch}.parquet"
    df.to_parquet(out_path, index=False)
    n_meta = len([c for c in METADATA_COLUMNS if c in df.columns]) + 1  # +branch
    print(f"Salvo: {out_path}")
    print(f"  {len(df):,} linhas x {len(df.columns)} colunas "
          f"({len(df.columns) - n_meta} features + {n_meta} metadados)")
    print(f"  amostras por algoritmo: {df['algorithm'].value_counts().to_dict()}")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser()
    parser.add_argument("--branch", choices=["cru", "controlado", "shuffled"],
                        default="controlado")
    parser.add_argument("--shard", type=int, default=0,
                        help="Índice deste processo (0..n_shards-1).")
    parser.add_argument("--n-shards", type=int, default=1,
                        help="Total de processos paralelos — cada um cuida "
                             "dos row groups com gi %% n_shards == shard.")
    parser.add_argument("--limit-chunks", type=int, default=None,
                        help="Processa só os N primeiros row groups (teste).")
    parser.add_argument("--sub-batch", type=int, default=250,
                        help="Linhas materializadas por vez dentro de um row "
                             "group (controla o pico de memória/IPC).")
    parser.add_argument("--consolidate", action="store_true",
                        help="Só junta os chunks já extraídos num parquet único.")
    args = parser.parse_args()

    out_dir = REPO_ROOT / "data" / "interim" / f"features_v2_{args.branch}"

    if args.consolidate:
        consolidate(args.branch, out_dir)
        return

    if not PQ_IN.exists():
        print(f"FAIL: dataset não encontrado em {PQ_IN}\n"
              "Rode antes: python scripts/generate_5class_v2.py")
        sys.exit(1)

    extract(args.branch, out_dir, args.limit_chunks, sub_batch=args.sub_batch,
            shard=args.shard, n_shards=args.n_shards)


if __name__ == "__main__":
    main()
