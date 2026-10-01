"""Ablação por região do XOR de pares consecutivos (ciphertext-only).

`run_pares_ct_only.py` usa 640 bits: bloco 1 (0-127), blocos 2-4 (128-511)
e tag (512-639). O patch de rodadas reduzidas encurta a permutação P12, que
o Ascon usa na inicialização E na finalização — então o sinal pode vir da
inicialização fraca (bloco 1) ou da finalização fraca (tag). Esta ablação
separa as duas fontes, com o mesmo split, os mesmos modelos e o mesmo relato
(`report_eval`) do runner principal. Reaproveita os .npz já gerados.

Uso:
    python scripts/reduced_rounds/ablacao_regiao_pares.py
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

import numpy as np  # noqa: E402
from sklearn.pipeline import Pipeline  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402

from scripts.reduced_rounds.run_pares_ct_only import (  # noqa: E402
    OUT_DIR, PAIRS_PER_KEY, SEED_BOOT, SEED_MODEL, SEED_SPLIT, _log,
)
from scripts.run_v2_caminho_a import build_models, get_proba  # noqa: E402
from src.eval.reporting import report_eval  # noqa: E402

N_KEYS, N_TEST = 300, 60
REGIOES = {"bloco1": (0, 128), "blocos2a4": (128, 512), "tag": (512, 640)}
MODELOS = ("XGBoost", "LogisticRegression")


def main() -> None:
    report_dir = OUT_DIR / "reports"
    for arm in ("texto", "imagem"):
        data = np.load(OUT_DIR / f"pares_{arm}_k{N_KEYS}.npz")
        n = N_KEYS * PAIRS_PER_KEY
        kidx = np.concatenate([data["key_idx"], data["key_idx"]])
        key_ids = np.array([f"k{k:04d}" for k in kidx])
        keys = np.arange(N_KEYS)
        np.random.default_rng(SEED_SPLIT).shuffle(keys)
        te = np.isin(kidx, keys[:N_TEST])
        tr = ~te
        for pa in (1, 2):
            X = np.vstack([np.unpackbits(data[f"ascon_pa{pa}"], axis=1),
                           np.unpackbits(data["gift_r40"], axis=1)]).astype(np.float32)
            y = np.concatenate([np.ones(n, int), np.zeros(n, int)])
            sample_ids = np.array([f"{arm}_k{k:04d}_p{i % PAIRS_PER_KEY:03d}_{'ascon' if lab else 'gift'}"
                                   for i, (k, lab) in enumerate(zip(kidx, y))])
            run_id = f"pares_ct_only_ablacao_{arm}_pa{pa}"
            _log(f"===== {run_id} =====")
            for reg, (a, b) in REGIOES.items():
                for name in MODELOS:
                    model = build_models(seed=SEED_MODEL)[name]
                    if name == "LogisticRegression":
                        model = Pipeline([("scaler", StandardScaler()), ("clf", model)])
                    model.fit(X[tr, a:b], y[tr])
                    proba = get_proba(model, X[te, a:b])
                    report_eval(run_id=run_id, caminho="A", modelo=f"{name}_{reg}",
                                braco=f"pares_{arm}", fold="final", y_true=y[te],
                                y_pred=proba.argmax(axis=1), y_proba=proba,
                                sample_ids=list(sample_ids[te]), key_ids=list(key_ids[te]),
                                class_names=["GIFT-COFB 40", f"Ascon pa={pa}"], labels=[0, 1],
                                out_dir=report_dir, seed=SEED_BOOT,
                                extra=dict(regiao=reg, bits=[a, b], pa=pa, arm=arm))
    _log("ablação concluída")


if __name__ == "__main__":
    main()
