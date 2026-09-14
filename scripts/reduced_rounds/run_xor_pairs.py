"""
Diagnóstico do nulo: as MESMAS 641 features, aplicadas ao XOR de pares
relacionados em vez de a criptogramas isolados.

Motivação. As três configs de rodadas reduzidas em escala completa deram
F1 = 0,50 com IC apertado, inclusive no extremo (Ascon pb=1 vs GIFT-COFB
completo). Isso não prova que as features são ruins — prova que redução de
rodadas não mexe na distribuição MARGINAL do criptograma. GIFT-COFB com 5 de
40 rodadas ainda produz saída com histograma quase uniforme e entropia quase
máxima, porque cada bloco continua sendo uma bijeção key-dependent de um
estado que muda. O que a redução destrói é a relação entre entradas
relacionadas, que é exatamente onde a literatura de distinguisher
diferencial (Gohr 2019, Shen et al. 2024) vai buscar sinal, e exatamente o
que uma feature marginal não enxerga.

O experimento. Para cada (chave, plaintext), cifra DUAS vezes com o mesmo
algoritmo, com nonces diferindo em 1 bit (n e n^1), e extrai as features
sobre C1 XOR C2. Como o plaintext é o mesmo nos dois lados, ele cancela (no
Ascon, duplex/stream-like, cancela exatamente: C1^C2 = KS1^KS2; no
GIFT-COFB cancela parcialmente, porque o feedback depende do plaintext).
Sobra a estrutura do próprio cifrador.

A pergunta que isto responde. Se as mesmas features separarem Ascon de
GIFT sobre diferenças e não sobre amostras isoladas, o nulo do experimento
principal deixa de ser mudo: ele passa a ser propriedade do modelo de
acesso ciphertext-only de amostra única, não do conjunto de features ser
cego. Se não separarem nem aqui, o problema é mais fundo que o modelo de
acesso.

Duas configs, nesta ordem de prioridade:
  1. reduzido  — Ascon pb=1 vs GIFT-COFB 5 rodadas (onde o sinal DEVE estar)
  2. completo  — Ascon 12/8 vs GIFT-COFB 40 (contraste na especificação)

Uso:
    python scripts/reduced_rounds/run_xor_pairs.py --configs reduzido completo
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
import pandas as pd  # noqa: E402
from sklearn.ensemble import RandomForestClassifier  # noqa: E402
from sklearn.metrics import f1_score, confusion_matrix, balanced_accuracy_score  # noqa: E402
from sklearn.model_selection import GroupKFold  # noqa: E402

from scripts.reduced_rounds.build_variant import build_ascon, build_gift  # noqa: E402
from scripts.reduced_rounds.reduced_wrapper import ReducedRoundsCipher  # noqa: E402
from scripts.reduced_rounds.run_pilot import _TextPlaintextSampler, CORPORA_DIR  # noqa: E402
from src.crypto.ctr_drbg import CTRDRBG  # noqa: E402
from scripts.reduced_rounds.streaming_extract import extract_streaming  # noqa: E402
from src.features.extractor import _ALL_FAMILIES  # noqa: E402

N_KEYS = 300
SLOTS_PER_KEY = 100
N_TEST_KEYS = 60
N_CV_FOLDS = 5
SEED = 999001  # mesmo do estudo de amostra única — mesmas chaves, comparável

OUT_DIR = REPO_ROOT / "build" / "reduced_rounds" / "xor_pairs"
OUT_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_PATH = OUT_DIR / "results.jsonl"

CONFIGS = {
    "reduzido": dict(
        label="XOR de pares relacionados — Ascon pb=1 vs GIFT-COFB 5 rodadas",
        ascon_pa=12, ascon_pb=1, gift_rounds=5,
    ),
    "completo": dict(
        label="XOR de pares relacionados — Ascon 12/8 vs GIFT-COFB 40 (especificação)",
        ascon_pa=12, ascon_pb=8, gift_rounds=40,
    ),
    # Correção do desenho (2026-09-11): com pa=12, a diferença de 1 bit no
    # nonce é totalmente difundida pelas 12 rodadas de inicialização ANTES de
    # o laço de dados rodar, então o XOR dos dois criptogramas é só dois
    # keystreams independentes — uniforme por construção, e foi isso que a
    # config "reduzido" mediu (F1=0,4967). Com pa=1 a diferença sobrevive à
    # inicialização e a correlação entre os dois keystreams fica visível.
    "init_fraca": dict(
        label="XOR de pares relacionados — Ascon pa=1 vs GIFT-COFB 40",
        ascon_pa=1, ascon_pb=8, gift_rounds=40,
    ),
    # Mapeamento do limiar (2026-09-12). Com pa=1 o XOR separa a F1=0,9188 e
    # com pa=12 fica no acaso (0,4966) — o sinal morre em algum ponto entre os
    # dois. Varredura grossa primeiro (2, 4, 6) pra localizar a transição; se
    # cair entre dois pontos, refinar depois. Referência externa: Shen et al.
    # (2024) constroem distinguisher diferencial até 4 das 12 rodadas do Ascon,
    # então um limiar nessa vizinhança é comparável à literatura.
    "init_pa2": dict(
        label="XOR de pares relacionados — Ascon pa=2 vs GIFT-COFB 40",
        ascon_pa=2, ascon_pb=8, gift_rounds=40,
    ),
    "init_pa4": dict(
        label="XOR de pares relacionados — Ascon pa=4 vs GIFT-COFB 40",
        ascon_pa=4, ascon_pb=8, gift_rounds=40,
    ),
    "init_pa6": dict(
        label="XOR de pares relacionados — Ascon pa=6 vs GIFT-COFB 40",
        ascon_pa=6, ascon_pb=8, gift_rounds=40,
    ),
}


def _log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"[{ts}] {msg}", flush=True)


def _append_result(record: dict) -> None:
    with open(RESULTS_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _xor(a: bytes, b: bytes) -> bytes:
    n = min(len(a), len(b))
    return bytes(x ^ y for x, y in zip(a[:n], b[:n]))


def _generate_xor_pairs(ascon_pa: int, ascon_pb: int, gift_rounds: int) -> pd.DataFrame:
    ascon = ReducedRoundsCipher(build_ascon(ascon_pa, ascon_pb), "ascon")
    gift = ReducedRoundsCipher(build_gift(gift_rounds), "gift")

    key_drbg = CTRDRBG(seed=SEED, label="pilot-keys")
    pt_drbg = CTRDRBG(seed=SEED, label="pilot-plaintext")
    sampler = _TextPlaintextSampler(CORPORA_DIR, pt_drbg)

    rows = []
    for k in range(N_KEYS):
        key_id = f"pilot_k{k:04d}"
        key = key_drbg.random_key(16)
        for slot in range(SLOTS_PER_KEY):
            pt = sampler.sample()
            counter = k * SLOTS_PER_KEY + slot
            n1 = counter.to_bytes(16, "big")
            n2 = (counter ^ 1).to_bytes(16, "big")  # difere em 1 bit
            sid = f"{key_id}_s{slot:03d}"
            for name, cipher in (("ascon_reduced", ascon), ("gift_reduced", gift)):
                d = _xor(cipher.encrypt(key, n1, pt), cipher.encrypt(key, n2, pt))
                rows.append(dict(sample_id=f"{sid}_{name}", algorithm=name,
                                 key_id=key_id, len_pt=len(pt), len_ct=len(d),
                                 ciphertext=d))
    return pd.DataFrame(rows)


def _bootstrap_ci(y_true, y_pred, n_boot: int = 1000, seed: int = 42) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    y_true, y_pred = np.array(y_true), np.array(y_pred)
    n = len(y_true)
    scores = [f1_score(y_true[i], y_pred[i], average="macro", zero_division=0)
              for i in (rng.integers(0, n, n) for _ in range(n_boot))]
    return tuple(np.percentile(scores, [2.5, 97.5]))


def run_config(name: str) -> None:
    cfg = CONFIGS[name]
    t0 = time.time()
    _log(f"===== [{name}] {cfg['label']} =====")

    _log(f"Gerando {N_KEYS * SLOTS_PER_KEY * 2} amostras de XOR "
         f"({N_KEYS} chaves x {SLOTS_PER_KEY} slots x 2 classes, 2 cifragens cada)...")
    df = _generate_xor_pairs(cfg["ascon_pa"], cfg["ascon_pb"], cfg["gift_rounds"])
    ct_path = OUT_DIR / f"xor_{name}.parquet"
    df.to_parquet(ct_path, index=False)
    _log(f"Geração concluída em {time.time() - t0:.0f}s. Extraindo 641 features...")

    t1 = time.time()
    feat_path = OUT_DIR / f"features_xor_{name}.parquet"
    df_feat = extract_streaming(ct_path, list(_ALL_FAMILIES),
                                output_path=feat_path, log=_log)
    _log(f"Extração concluída em {time.time() - t1:.0f}s ({len(df_feat)} amostras) "
         f"-> {feat_path.name}")

    keys = sorted(df_feat["key_id"].unique().tolist())
    rng = np.random.default_rng(SEED)
    rng.shuffle(keys)
    test_keys, trainval_keys = set(keys[:N_TEST_KEYS]), set(keys[N_TEST_KEYS:])
    trainval = df_feat[df_feat["key_id"].isin(trainval_keys)].reset_index(drop=True)
    test = df_feat[df_feat["key_id"].isin(test_keys)].reset_index(drop=True)

    fcols = [c for c in df_feat.columns
             if c not in ("sample_id", "algorithm", "key_id", "len_pt", "len_ct")]
    X, y, groups = trainval[fcols].values, trainval["algorithm"].values, trainval["key_id"].values

    for fold_i, (tr, va) in enumerate(GroupKFold(n_splits=N_CV_FOLDS).split(X, y, groups)):
        clf = RandomForestClassifier(n_estimators=300, random_state=7, n_jobs=-1)
        clf.fit(X[tr], y[tr])
        pred = clf.predict(X[va])
        f1 = f1_score(y[va], pred, average="macro")
        ba = balanced_accuracy_score(y[va], pred)
        _append_result(dict(config=name, fold=fold_i, f1_macro=f1, balanced_accuracy=ba,
                            confusion_matrix=confusion_matrix(y[va], pred,
                                                              labels=sorted(set(y[va]))).tolist(),
                            n_train=len(tr), n_val=len(va),
                            timestamp=datetime.now(timezone.utc).isoformat()))
        _log(f"  fold {fold_i}: F1-macro={f1:.4f}  bal_acc={ba:.4f}")

    _log("Fold final: treinando em todo o trainval, avaliando no holdout de teste...")
    clf = RandomForestClassifier(n_estimators=300, random_state=7, n_jobs=-1)
    clf.fit(X, y)
    y_test = test["algorithm"].values
    pred = clf.predict(test[fcols].values)
    f1 = f1_score(y_test, pred, average="macro")
    ba = balanced_accuracy_score(y_test, pred)
    cm = confusion_matrix(y_test, pred, labels=sorted(set(y_test))).tolist()
    lo, hi = _bootstrap_ci(y_test, pred)
    _append_result(dict(config=name, fold="final", f1_macro=f1, balanced_accuracy=ba,
                        f1_macro_ci_lower=lo, f1_macro_ci_upper=hi, confusion_matrix=cm,
                        n_train=len(trainval), n_test=len(test),
                        timestamp=datetime.now(timezone.utc).isoformat()))
    _log(f"[{name}] FINAL: F1-macro={f1:.4f}  IC95%=[{lo:.4f}, {hi:.4f}]  bal_acc={ba:.4f}  "
         f"(tempo total: {(time.time() - t0) / 60:.1f} min)")
    _log(f"Matriz de confusão {sorted(set(y_test))}:\n{np.array(cm)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--configs", nargs="+", choices=list(CONFIGS),
                        default=["reduzido", "completo"])
    args = parser.parse_args()
    _log(f"Fila: {args.configs} | resultados em {RESULTS_PATH}")
    for name in args.configs:
        run_config(name)
    _log("Fila concluída.")
