"""Roda a família `blockalign` sobre datasets de criptogramas JÁ gerados.

Reaproveita os parquets de `build/reduced_rounds/` (3,9 GB cada) em vez de
regerar 60.000 criptogramas por config. Extrai só as 18 features alinhadas
ao bloco — não as 641 — o que torna a rodada barata (operações vetorizadas,
sem NIST STS nem compressão, que é o que domina o custo das 641).

A pergunta: as três configs de rodadas reduzidas deram F1=0,50 com as 641
features marginais/agregadas. Estrutura de bloco (viés por posição, relação
entre blocos consecutivos, taxa de repetição) é invisível para elas por
construção. Se `blockalign` separar onde as 641 não separaram, o problema
era onde se olhava, não a ausência de sinal.

Leitura em lotes via pyarrow — nunca `pd.read_parquet` do arquivo inteiro
(regra de segurança de memória do projeto; estes arquivos têm 3,9 GB de
ciphertext bruto).

Uso:
    python scripts/reduced_rounds/run_blockalign.py --datasets full/full_asimetrico_ciphertexts.parquet ...
    python scripts/reduced_rounds/run_blockalign.py --all
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402
from joblib import Parallel, delayed  # noqa: E402
from sklearn.ensemble import RandomForestClassifier  # noqa: E402
from sklearn.metrics import f1_score, confusion_matrix, balanced_accuracy_score  # noqa: E402
from sklearn.model_selection import GroupKFold  # noqa: E402

from src.features.families.blockalign import extract_blockalign  # noqa: E402

BASE = REPO_ROOT / "build" / "reduced_rounds"
OUT_DIR = BASE / "blockalign"
OUT_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_PATH = OUT_DIR / "results.jsonl"

N_TEST_KEYS = 60
N_CV_FOLDS = 5
SEED = 999001
BATCH_ROWS = 2000  # ~131 MB de ciphertext por lote, amortiza o overhead do joblib

ALL_DATASETS = [
    "full/full_asimetrico_inverso_ciphertexts.parquet",
    "full/full_asimetrico_ciphertexts.parquet",
    "full/full_simetrico_ciphertexts.parquet",
    "xor_pairs/xor_reduzido.parquet",
]


def _log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"[{ts}] {msg}", flush=True)


def _extract_one(sid: str, algo: str, kid: str, ct: bytes) -> dict:
    feats = extract_blockalign(bytes(ct))
    feats.update(sample_id=sid, algorithm=algo, key_id=kid)
    return feats


def _extract_streaming(parquet_path: Path) -> pd.DataFrame:
    """Percorre o parquet em lotes, extraindo blockalign em paralelo.

    Lote a lote (e não o arquivo inteiro) por causa dos 3,9 GB de ciphertext
    bruto; paralelo dentro do lote porque serial dá ~6 amostras/s, o que
    seriam ~2,6h por dataset.
    """
    pf = pq.ParquetFile(parquet_path)
    frames = []
    n = 0
    t0 = time.time()
    with Parallel(n_jobs=-1, prefer="processes") as parallel:
        for batch in pf.iter_batches(batch_size=BATCH_ROWS,
                                     columns=["sample_id", "algorithm", "key_id", "ciphertext"]):
            d = batch.to_pydict()
            results = parallel(
                delayed(_extract_one)(sid, algo, kid, ct)
                for sid, algo, kid, ct in zip(d["sample_id"], d["algorithm"],
                                              d["key_id"], d["ciphertext"])
            )
            frames.append(pd.DataFrame(results))
            n += len(results)
            if n % 10000 == 0:
                rate = n / (time.time() - t0)
                _log(f"    {n} amostras ({rate:.0f}/s, ETA "
                     f"{(pf.metadata.num_rows - n) / rate / 60:.0f} min)")
    return pd.concat(frames, ignore_index=True)


def run_dataset(rel_path: str) -> None:
    path = BASE / rel_path
    if not path.exists():
        _log(f"AVISO: não encontrado, pulando: {path}")
        return

    name = path.stem
    t0 = time.time()
    _log(f"===== [{name}] =====")
    _log(f"Extraindo blockalign (18 features) de {path.name} em lotes...")
    df = _extract_streaming(path)
    feat_path = OUT_DIR / f"blockalign_{name}.parquet"
    df.to_parquet(feat_path, index=False)
    _log(f"Extração concluída em {time.time() - t0:.0f}s ({len(df)} amostras) "
         f"-> {feat_path.name}")

    keys = sorted(df["key_id"].unique().tolist())
    rng = np.random.default_rng(SEED)
    rng.shuffle(keys)
    test_keys, trainval_keys = set(keys[:N_TEST_KEYS]), set(keys[N_TEST_KEYS:])
    trainval = df[df["key_id"].isin(trainval_keys)].reset_index(drop=True)
    test = df[df["key_id"].isin(test_keys)].reset_index(drop=True)

    fcols = [c for c in df.columns if c.startswith(("blk8_", "blk16_"))]
    X = np.nan_to_num(trainval[fcols].values, nan=0.0)
    y, groups = trainval["algorithm"].values, trainval["key_id"].values

    for fold_i, (tr, va) in enumerate(GroupKFold(n_splits=N_CV_FOLDS).split(X, y, groups)):
        clf = RandomForestClassifier(n_estimators=300, random_state=7, n_jobs=-1)
        clf.fit(X[tr], y[tr])
        pred = clf.predict(X[va])
        f1 = f1_score(y[va], pred, average="macro")
        ba = balanced_accuracy_score(y[va], pred)
        with open(RESULTS_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(dict(dataset=name, family="blockalign", fold=fold_i,
                                    f1_macro=f1, balanced_accuracy=ba,
                                    timestamp=datetime.now(timezone.utc).isoformat())) + "\n")
        _log(f"  fold {fold_i}: F1-macro={f1:.4f}  bal_acc={ba:.4f}")

    clf = RandomForestClassifier(n_estimators=300, random_state=7, n_jobs=-1)
    clf.fit(X, y)
    y_test = test["algorithm"].values
    pred = clf.predict(np.nan_to_num(test[fcols].values, nan=0.0))
    f1 = f1_score(y_test, pred, average="macro")
    ba = balanced_accuracy_score(y_test, pred)
    cm = confusion_matrix(y_test, pred, labels=sorted(set(y_test))).tolist()

    boot = np.random.default_rng(42)
    yt, yp = np.array(y_test), np.array(pred)
    scores = [f1_score(yt[i], yp[i], average="macro", zero_division=0)
              for i in (boot.integers(0, len(yt), len(yt)) for _ in range(1000))]
    lo, hi = np.percentile(scores, [2.5, 97.5])

    with open(RESULTS_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(dict(dataset=name, family="blockalign", fold="final",
                                f1_macro=f1, balanced_accuracy=ba,
                                f1_macro_ci_lower=lo, f1_macro_ci_upper=hi,
                                confusion_matrix=cm, n_train=len(trainval), n_test=len(test),
                                timestamp=datetime.now(timezone.utc).isoformat())) + "\n")
    _log(f"[{name}] FINAL blockalign: F1-macro={f1:.4f}  IC95%=[{lo:.4f}, {hi:.4f}]  "
         f"bal_acc={ba:.4f}  (total {(time.time() - t0) / 60:.1f} min)")
    _log(f"Matriz {sorted(set(y_test))}:\n{np.array(cm)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--datasets", nargs="+", default=None)
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()

    targets = ALL_DATASETS if (args.all or not args.datasets) else args.datasets
    _log(f"Fila: {targets} | resultados em {RESULTS_PATH}")
    for rel in targets:
        run_dataset(rel)
    _log("Fila concluída.")
