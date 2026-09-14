"""
Versão em escala de produção do estudo de sensibilidade a rodadas reduzidas
(Ascon vs GIFT-COFB): 300 chaves x 100 slots = 60.000 criptogramas por
config (mesma escala do dataset v1 original), com key-holdout 240/60 e
5-fold CV estratificado por chave dentro do treino, igual à Regra de Ouro
2/3 da produção.

Diferença deliberada em relação ao Caminho A de produção: SEM seleção de
características (as 641 features vão direto pro classificador). Resolve o
regime p≈n que o piloto tinha (48.000 amostras de treino contra 641
features já é folgado o bastante), mas não replica o pipeline de seleção
em 5 estágios — isso é uma simplificação aceita para este estudo de
sensibilidade, registrada aqui, não um descuido.

Escreve resultado incremental em JSONL (um registro por fold + um "final"),
pra poder acompanhar progresso e não perder nada se o processo for
interrompido no meio.

Uso:
    python scripts/reduced_rounds/run_full.py --configs asimetrico_inverso asimetrico simetrico
    python scripts/reduced_rounds/run_full.py --configs asimetrico_inverso   # só um
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
sys.path.insert(0, str(REPO_ROOT / "src" / "crypto"))

import numpy as np  # noqa: E402
from sklearn.ensemble import RandomForestClassifier  # noqa: E402
from sklearn.metrics import f1_score, confusion_matrix, balanced_accuracy_score  # noqa: E402
from sklearn.model_selection import GroupKFold  # noqa: E402

from scripts.reduced_rounds.run_pilot import (  # noqa: E402
    CONFIGS, _generate_pairs, _key_holdout_split,
)
from scripts.reduced_rounds.streaming_extract import extract_streaming  # noqa: E402
from src.features.extractor import _ALL_FAMILIES  # noqa: E402

N_KEYS = 300
SLOTS_PER_KEY = 100
N_TEST_KEYS = 60  # 240 trainval / 60 teste — mesma proporção 80/20 da produção
N_CV_FOLDS = 5
FULL_SEED = 999001  # mesmo seed do piloto — mesmas chaves/plaintexts, comparável

OUT_DIR = REPO_ROOT / "build" / "reduced_rounds" / "full"
OUT_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_PATH = OUT_DIR / "results.jsonl"


def _log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"[{ts}] {msg}", flush=True)


def _append_result(record: dict) -> None:
    with open(RESULTS_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _bootstrap_ci(y_true, y_pred, n_boot: int = 1000, seed: int = 42) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    y_true, y_pred = np.array(y_true), np.array(y_pred)
    n = len(y_true)
    scores = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        scores.append(f1_score(y_true[idx], y_pred[idx], average="macro", zero_division=0))
    return tuple(np.percentile(scores, [2.5, 97.5]))


def run_config_full(name: str) -> None:
    cfg = CONFIGS[name]
    t0 = time.time()
    _log(f"===== [{name}] {cfg['label']} =====")

    _log(f"Gerando {N_KEYS * SLOTS_PER_KEY * 2} criptogramas "
         f"({N_KEYS} chaves x {SLOTS_PER_KEY} slots x 2 classes)...")
    df_ct = _generate_pairs(cfg["ascon_pa"], cfg["ascon_pb"], cfg["gift_rounds"],
                             n_keys=N_KEYS, slots_per_key=SLOTS_PER_KEY, seed=FULL_SEED)
    ct_path = OUT_DIR / f"full_{name}_ciphertexts.parquet"
    df_ct.to_parquet(ct_path, index=False)
    _log(f"Geração concluída em {time.time() - t0:.0f}s. Extraindo 641 features...")

    t1 = time.time()
    # Extração em lotes (não `extract_dataset`, que carrega o parquet inteiro
    # e estourou com MemoryError nos 3,9 GB deste dataset), e salvando em
    # disco — as 3 primeiras rodadas descartaram ~10,5h de CPU de features.
    feat_path = OUT_DIR / f"features_{name}.parquet"
    df_feat = extract_streaming(ct_path, list(_ALL_FAMILIES),
                                output_path=feat_path, log=_log)
    _log(f"Extração concluída em {time.time() - t1:.0f}s ({len(df_feat)} amostras) "
         f"-> {feat_path.name}")

    trainval_keys, test_keys = _key_holdout_split(
        df_feat["key_id"].unique().tolist(), n_test_keys=N_TEST_KEYS, seed=FULL_SEED)
    trainval_df = df_feat[df_feat["key_id"].isin(trainval_keys)].reset_index(drop=True)
    test_df = df_feat[df_feat["key_id"].isin(test_keys)].reset_index(drop=True)

    feature_cols = [c for c in df_feat.columns
                    if c not in ("sample_id", "algorithm", "key_id", "len_pt", "len_ct")]

    X_trainval = trainval_df[feature_cols].values
    y_trainval = trainval_df["algorithm"].values
    groups = trainval_df["key_id"].values

    # --- 5-fold CV estratificado por chave, dentro do trainval (Regra de Ouro 3) ---
    gkf = GroupKFold(n_splits=N_CV_FOLDS)
    for fold_i, (tr_idx, va_idx) in enumerate(gkf.split(X_trainval, y_trainval, groups)):
        clf = RandomForestClassifier(n_estimators=300, random_state=7, n_jobs=-1)
        clf.fit(X_trainval[tr_idx], y_trainval[tr_idx])
        y_pred = clf.predict(X_trainval[va_idx])
        y_true = y_trainval[va_idx]

        f1 = f1_score(y_true, y_pred, average="macro")
        bal_acc = balanced_accuracy_score(y_true, y_pred)
        cm = confusion_matrix(y_true, y_pred, labels=sorted(set(y_true))).tolist()

        record = dict(config=name, fold=fold_i, f1_macro=f1, balanced_accuracy=bal_acc,
                       confusion_matrix=cm, n_train=len(tr_idx), n_val=len(va_idx),
                       timestamp=datetime.now(timezone.utc).isoformat())
        _append_result(record)
        _log(f"  fold {fold_i}: F1-macro={f1:.4f}  bal_acc={bal_acc:.4f} "
             f"(treino={len(tr_idx)}, val={len(va_idx)})")

    # --- fit final: todas as 240 chaves trainval -> avalia nas 60 chaves de teste ---
    _log("Fold final: treinando em todo o trainval, avaliando no holdout de teste...")
    clf = RandomForestClassifier(n_estimators=300, random_state=7, n_jobs=-1)
    clf.fit(X_trainval, y_trainval)
    X_test = test_df[feature_cols].values
    y_test = test_df["algorithm"].values
    y_pred = clf.predict(X_test)

    f1 = f1_score(y_test, y_pred, average="macro")
    bal_acc = balanced_accuracy_score(y_test, y_pred)
    cm = confusion_matrix(y_test, y_pred, labels=sorted(set(y_test))).tolist()
    ci_lo, ci_hi = _bootstrap_ci(y_test, y_pred)

    record = dict(config=name, fold="final", f1_macro=f1, balanced_accuracy=bal_acc,
                  f1_macro_ci_lower=ci_lo, f1_macro_ci_upper=ci_hi,
                  confusion_matrix=cm, n_train=len(trainval_df), n_test=len(test_df),
                  timestamp=datetime.now(timezone.utc).isoformat())
    _append_result(record)

    elapsed = time.time() - t0
    _log(f"[{name}] FINAL: F1-macro={f1:.4f}  IC95%=[{ci_lo:.4f}, {ci_hi:.4f}]  "
         f"bal_acc={bal_acc:.4f}  (tempo total: {elapsed / 60:.1f} min)")
    _log(f"Matriz de confusão {sorted(set(y_test))}:\n{np.array(cm)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--configs", nargs="+", choices=list(CONFIGS),
                        default=["asimetrico_inverso", "asimetrico", "simetrico"])
    args = parser.parse_args()

    _log(f"Fila de execução: {args.configs}")
    _log(f"Resultados incrementais em: {RESULTS_PATH}")
    for name in args.configs:
        run_config_full(name)
    _log("Todas as configs da fila concluídas.")
