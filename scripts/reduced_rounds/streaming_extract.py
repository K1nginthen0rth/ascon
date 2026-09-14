"""Extração de features em lotes, para parquets grandes de ciphertext.

Por que existe. `CiphertextFeatureExtractor.extract_dataset()` faz
`pd.read_parquet()` do arquivo inteiro e depois materializa um dict por
amostra (`to_dict("records")`) antes de mandar pro joblib, que ainda pickla
tudo pros workers. Para os parquets deste estudo (60.000 amostras × 65 KB
= 3,9 GB) isso é 3,9 GB em pandas + ~3,9 GB em objetos Python + cópias por
worker. Sobreviveu em três rodadas e estourou com `MemoryError` na quarta.

A produção não sofre disso porque `extract_features_v2.py` fatia em 6
shards; os runners deste subsistema passavam o arquivo completo. Este
módulo é a correção do lado dos runners, sem tocar no extrator de produção
(que continua sendo o caminho validado do experimento principal).

Estratégia: pyarrow `iter_batches` + joblib por lote, mesmo padrão já
medido em `run_blockalign.py` (315 amostras/s com 18 features).
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

import pandas as pd
import pyarrow.parquet as pq
from joblib import Parallel, delayed

from src.features.extractor import _FAMILY_FUNCS

_META = ("sample_id", "algorithm", "key_id", "len_pt", "len_ct")
DEFAULT_BATCH_ROWS = 2000


def _extract_row(meta: dict, ct: bytes, families: list[str]) -> dict:
    out = dict(meta)
    for fname in families:
        out.update(_FAMILY_FUNCS[fname](bytes(ct)))
    return out


def extract_streaming(
    parquet_path: str | Path,
    families: list[str],
    output_path: Optional[str | Path] = None,
    batch_rows: int = DEFAULT_BATCH_ROWS,
    log=print,
) -> pd.DataFrame:
    """Extrai `families` de todas as amostras, lendo em lotes.

    Args:
        parquet_path: parquet com coluna `ciphertext` + metadados.
        families: nomes de famílias (chaves de `_FAMILY_FUNCS`).
        output_path: se dado, salva o resultado em parquet.
        batch_rows: linhas por lote (2000 ≈ 131 MB de ciphertext).
        log: função de log (recebe str).

    Returns:
        DataFrame com metadados + features, sem a coluna `ciphertext`.
    """
    parquet_path = Path(parquet_path)
    unknown = set(families) - set(_FAMILY_FUNCS)
    if unknown:
        raise ValueError(f"Familias desconhecidas: {sorted(unknown)}")

    pf = pq.ParquetFile(parquet_path)
    total = pf.metadata.num_rows
    present_meta = [c for c in _META if c in pf.schema_arrow.names]
    cols = present_meta + ["ciphertext"]

    frames: list[pd.DataFrame] = []
    done = 0
    t0 = time.time()
    with Parallel(n_jobs=-1, prefer="processes") as parallel:
        for batch in pf.iter_batches(batch_size=batch_rows, columns=cols):
            d = batch.to_pydict()
            cts = d.pop("ciphertext")
            metas = [{k: d[k][i] for k in present_meta} for i in range(len(cts))]
            results = parallel(
                delayed(_extract_row)(m, ct, families) for m, ct in zip(metas, cts)
            )
            frames.append(pd.DataFrame(results))
            done += len(results)
            elapsed = time.time() - t0
            rate = done / elapsed if elapsed > 0 else 0.0
            if rate > 0:
                log(f"    {done}/{total} ({rate:.1f}/s, ETA "
                    f"{(total - done) / rate / 60:.0f} min)")

    df = pd.concat(frames, ignore_index=True)
    if output_path is not None:
        df.to_parquet(output_path, index=False)
        log(f"    features salvas em {Path(output_path).name}")
    return df
