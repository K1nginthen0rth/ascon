"""
Pares de mensagens consecutivas do MESMO dispositivo, em ciphertext-only.

Por que existe. O estudo `run_xor_pairs.py` (11-13/09) cifrava o MESMO
plaintext duas vezes. Saber que dois criptogramas cifram o mesmo texto é
conhecimento sobre o plaintext, e o desenho foi rejeitado pelo Nycolas em
13/09 como fora do modelo de ameaça. Aqui o adversário só tem o que teria
observando um dispositivo real:
  - criptogramas de uma mesma chave (mesmo dispositivo);
  - nonces públicos de contador — pareia mensagens consecutivas (2c, 2c+1),
    que diferem só no bit menos significativo;
  - plaintexts DIFERENTES e desconhecidos em cada mensagem (P1 != P2).

Pergunta: rodadas reduzidas na inicialização do Ascon (o "erro proposital")
continuam acusáveis sem relação conhecida entre os plaintexts?

Classes: Ascon-AEAD128 com `pa` reduzido (pb=8) vs GIFT-COFB 40 rodadas.
`pa=12` é o controle negativo (Ascon correto: deve dar acaso).
Braços de plaintext: `texto` (SPGC; texto xor texto zera o bit 7 de cada
byte, então é o melhor caso) e `imagem` (ImageNet 256x256 cinza; caso difícil).

Protocolo (Regras de Ouro): chaves e amostragem via CTR_DRBG; mesmas chaves,
nonces e plaintexts para os dois algoritmos; key-holdout 240/60 (seed 42);
GroupKFold 5 por chave dentro do trainval; modelos da produção (seed 7);
bootstrap por chave (seed 42); toda métrica via `report_eval` (console +
JSONL + PNG + parquet). len_pt/len_ct não entram.

Features: bits do XOR dos 4 primeiros blocos do payload (512) + bits do XOR
das tags (128) = 640 binárias. Sem seleção de features (simplificação já
aceita no estudo de rodadas reduzidas, ver `run_full.py`).

Nível dispositivo (vários criptogramas por vez): no teste, média do log-odds
das 100 pares de cada (chave, algoritmo) -> uma decisão por dispositivo.

SVM-RBF: só no fold final, subamostra de 10.000, C=1 e gamma=0.01 fixos
(gamma="scale" degenera sob subamostra — ver commit fd8bacf), sem
`probability` (probas via decision_function). Com CV custaria horas.

Uso:
    python scripts/reduced_rounds/run_pares_ct_only.py --smoke
    python scripts/reduced_rounds/run_pares_ct_only.py
    python scripts/reduced_rounds/run_pares_ct_only.py --arms texto --pa 1 12
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src" / "crypto"))

import numpy as np  # noqa: E402
from sklearn.model_selection import GroupKFold  # noqa: E402
from sklearn.pipeline import Pipeline  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402
from sklearn.svm import SVC  # noqa: E402

from scripts.generate_5class_v2 import (  # noqa: E402
    CORPORA_DIR, IMAGES_DIR, IMAGES_MANIFEST, PLAINTEXT_BYTES,
    _ImagePlaintextSampler, _TextPlaintextSampler,
)
from scripts.reduced_rounds.build_variant import build_ascon, build_gift  # noqa: E402
from scripts.reduced_rounds.reduced_wrapper import ReducedRoundsCipher  # noqa: E402
from scripts.run_v2_caminho_a import build_models, get_proba  # noqa: E402
from src.crypto.ascon_wrapper import AsconAEAD128  # noqa: E402
from src.crypto.ctr_drbg import CTRDRBG  # noqa: E402
from src.crypto.gift_cofb_wrapper import GiftCOFB  # noqa: E402
from src.eval.reporting import report_eval  # noqa: E402

SEED_GEN = 999002
SEED_SPLIT = 42
SEED_MODEL = 7
SEED_BOOT = 42
PAIRS_PER_KEY = 100
PA_VALUES = (1, 2, 4, 12)
HEAD = 64      # 4 blocos de 16 bytes do payload
ABYTES = 16    # tag de Ascon-AEAD128 e GIFT-COFB
SVM_SUBSAMPLE = 10_000
NEEDS_SCALING = {"LinearSVC", "LogisticRegression"}

OUT_DIR = REPO_ROOT / "build" / "reduced_rounds" / "pares_ct_only"


def _log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def _git_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT,
                              capture_output=True, text=True, check=True).stdout.strip()
    except Exception:  # noqa: BLE001
        return "desconhecido"


def _xor_head_tag(a: bytes, b: bytes) -> np.ndarray:
    return (np.frombuffer(a[:HEAD] + a[-ABYTES:], np.uint8)
            ^ np.frombuffer(b[:HEAD] + b[-ABYTES:], np.uint8))


def generate(arm: str, n_keys: int) -> dict:
    """XOR (4 blocos + tag) de pares consecutivos, para GIFT-40 e os 4 `pa`.

    Todos os `pa` saem do mesmo laço, com as mesmas chaves, nonces e
    plaintexts (regra 6). Só o XOR fica em disco — plaintexts e chaves não."""
    path = OUT_DIR / f"pares_{arm}_k{n_keys}.npz"
    if path.exists():
        _log(f"[{arm}] reaproveitando {path.name}")
        z = np.load(path)
        return {k: z[k] for k in z.files}

    ascon = {pa: ReducedRoundsCipher(build_ascon(pa, 8), "ascon") for pa in PA_VALUES}
    gift = ReducedRoundsCipher(build_gift(40), "gift")
    ref_ascon, ref_gift = AsconAEAD128(), GiftCOFB()

    key_drbg = CTRDRBG(seed=SEED_GEN, label="pares-ct-only-keys")
    pt_drbg = CTRDRBG(seed=SEED_GEN, label=f"pares-ct-only-pt-{arm}")
    if arm == "texto":
        text_sampler = _TextPlaintextSampler(CORPORA_DIR, pt_drbg)
        sample = text_sampler.sample
        image_sampler = None
    elif arm == "imagem":
        image_sampler = _ImagePlaintextSampler(IMAGES_DIR, IMAGES_MANIFEST, pt_drbg)
        sample = lambda: image_sampler.sample()[0]  # noqa: E731
    else:
        raise ValueError(f"braço desconhecido: {arm}")

    n = n_keys * PAIRS_PER_KEY
    out = {f"ascon_pa{pa}": np.zeros((n, HEAD + ABYTES), np.uint8) for pa in PA_VALUES}
    out["gift_r40"] = np.zeros((n, HEAD + ABYTES), np.uint8)
    out["key_idx"] = np.repeat(np.arange(n_keys), PAIRS_PER_KEY).astype(np.int32)
    n_resampled = 0
    t0 = time.time()
    for k in range(n_keys):
        key = key_drbg.random_key(16)
        for j in range(PAIRS_PER_KEY):
            p1, p2 = sample(), sample()
            while p2 == p1:  # par com plaintext igual reintroduziria o desenho rejeitado
                p2 = sample()
                n_resampled += 1
            assert len(p1) == len(p2) == PLAINTEXT_BYTES
            c = 2 * (k * PAIRS_PER_KEY + j)
            n1, n2 = c.to_bytes(16, "big"), (c + 1).to_bytes(16, "big")
            i = k * PAIRS_PER_KEY + j

            g1, g2 = gift.encrypt(key, n1, p1), gift.encrypt(key, n2, p2)
            out["gift_r40"][i] = _xor_head_tag(g1, g2)
            for pa in PA_VALUES:
                a1, a2 = ascon[pa].encrypt(key, n1, p1), ascon[pa].encrypt(key, n2, p2)
                out[f"ascon_pa{pa}"][i] = _xor_head_tag(a1, a2)
                if i == 0 and pa == 12:
                    assert a1 == ref_ascon.encrypt(key, n1, p1), "variante pa=12 != Ascon de produção"
            if i == 0:
                assert g1 == ref_gift.encrypt(key, n1, p1), "variante r40 != GIFT-COFB de produção"
        if (k + 1) % 25 == 0 or k + 1 == n_keys:
            _log(f"[{arm}] chaves {k + 1}/{n_keys} ({time.time() - t0:.0f}s)")

    np.savez(path, **out)
    meta = dict(arm=arm, n_keys=n_keys, pairs_per_key=PAIRS_PER_KEY, seed_gen=SEED_GEN,
                pa_values=list(PA_VALUES), head_bytes=HEAD, tag_bytes=ABYTES,
                nonce="contador big-endian 16 bytes, par (2c, 2c+1)",
                n_resampled_equal_plaintext=n_resampled,
                n_reused_images=(image_sampler.n_reused if image_sampler else None),
                git_commit=_git_commit(), generated_at=datetime.now(timezone.utc).isoformat())
    path.with_suffix(".json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    _log(f"[{arm}] geração concluída em {time.time() - t0:.0f}s -> {path.name} "
         f"(reamostrados por P1==P2: {n_resampled})")
    return out


def _device_level(proba: np.ndarray, y: np.ndarray, keys: np.ndarray):
    """Uma decisão por (chave, algoritmo): média do log-odds das pares."""
    logit = np.log(np.clip(proba[:, 1], 1e-12, 1)) - np.log(np.clip(proba[:, 0], 1e-12, 1))
    bag_y, bag_keys, bag_score = [], [], []
    for k in np.unique(keys):
        for lab in (0, 1):
            m = (keys == k) & (y == lab)
            if m.any():
                bag_y.append(lab)
                bag_keys.append(k)
                bag_score.append(logit[m].mean())
    p1 = 1.0 / (1.0 + np.exp(-np.clip(np.array(bag_score), -50, 50)))
    return np.array(bag_y), np.column_stack([1 - p1, p1]), np.array(bag_keys)


def run_config(arm: str, pa: int, data: dict, n_keys: int, n_test: int, n_cv: int,
               report_dir: Path, run_svm: bool) -> None:
    run_id = f"pares_ct_only_{arm}_pa{pa}"
    braco = f"pares_{arm}"
    class_names = ["GIFT-COFB 40", f"Ascon pa={pa}"]
    _log(f"===== {run_id}: Ascon pa={pa} vs GIFT-COFB 40, plaintext={arm} =====")

    n = n_keys * PAIRS_PER_KEY
    X = np.vstack([np.unpackbits(data[f"ascon_pa{pa}"], axis=1),
                   np.unpackbits(data["gift_r40"], axis=1)]).astype(np.float32)
    y = np.concatenate([np.ones(n, int), np.zeros(n, int)])
    kidx = np.concatenate([data["key_idx"], data["key_idx"]])
    key_ids = np.array([f"k{k:04d}" for k in kidx])
    sample_ids = np.array([f"{arm}_k{k:04d}_p{i % PAIRS_PER_KEY:03d}_{'ascon' if lab else 'gift'}"
                           for i, (k, lab) in enumerate(zip(kidx, y))])

    keys = np.arange(n_keys)
    np.random.default_rng(SEED_SPLIT).shuffle(keys)
    te = np.isin(kidx, keys[:n_test])
    tr = ~te

    # Diagnóstico sem modelo: viés por bit no bloco 1, só no treino.
    for lab, name in ((1, class_names[1]), (0, class_names[0])):
        sel = tr & (y == lab)
        p = X[sel, :128].mean(axis=0)
        z = (p - 0.5) / np.sqrt(0.25 / sel.sum())
        _log(f"  diagnóstico (treino) bloco 1, {name}: max|z|={np.abs(z).max():.1f}, "
             f"bits com |z|>6: {(np.abs(z) > 6).sum()}/128")

    extra_base = dict(pa=pa, arm=arm, n_features=X.shape[1], seed_gen=SEED_GEN,
                      access_model="mesma chave, nonces consecutivos (2c,2c+1), P1!=P2 desconhecidos")

    def fit_eval(name, model, idx_tr, idx_ev, fold):
        if name in NEEDS_SCALING:
            model = Pipeline([("scaler", StandardScaler()), ("clf", model)])
        t = time.time()
        model.fit(X[idx_tr], y[idx_tr])
        proba = get_proba(model, X[idx_ev])
        report_eval(run_id=run_id, caminho="A", modelo=name, braco=braco, fold=fold,
                    y_true=y[idx_ev], y_pred=proba.argmax(axis=1), y_proba=proba,
                    sample_ids=list(sample_ids[idx_ev]), key_ids=list(key_ids[idx_ev]),
                    class_names=class_names, labels=[0, 1], out_dir=report_dir,
                    seed=SEED_BOOT, extra={**extra_base, "fit_seconds": round(time.time() - t, 1),
                                           "n_train": int(len(idx_tr))})
        return proba

    idx_trval = np.where(tr)[0]
    idx_test = np.where(te)[0]
    for fold, (a, b) in enumerate(GroupKFold(n_splits=n_cv).split(idx_trval, groups=key_ids[idx_trval])):
        for name, model in build_models(seed=SEED_MODEL).items():
            fit_eval(name, model, idx_trval[a], idx_trval[b], fold)

    finals = {name: model for name, model in build_models(seed=SEED_MODEL).items()}
    if run_svm:
        finals["SVM-RBF"] = None
    for name, model in finals.items():
        idx_fit = idx_trval
        if name == "SVM-RBF":
            rng = np.random.default_rng(SEED_MODEL)
            idx_fit = rng.choice(idx_trval, size=min(SVM_SUBSAMPLE, len(idx_trval)), replace=False)
            model = SVC(C=1.0, gamma=0.01, kernel="rbf", random_state=SEED_MODEL)
        proba = fit_eval(name, model, idx_fit, idx_test, "final")
        by, bp, bk = _device_level(proba, y[idx_test], key_ids[idx_test])
        report_eval(run_id=run_id, caminho="A", modelo=f"{name}_dispositivo", braco=braco,
                    fold="final", y_true=by, y_pred=bp.argmax(axis=1), y_proba=bp,
                    sample_ids=[f"{k}_{'ascon' if lab else 'gift'}" for k, lab in zip(bk, by)],
                    key_ids=list(bk), class_names=class_names, labels=[0, 1],
                    out_dir=report_dir, seed=SEED_BOOT,
                    extra={**extra_base, "nivel": "dispositivo",
                           "pares_por_decisao": PAIRS_PER_KEY})


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--arms", nargs="+", default=["texto", "imagem"], choices=["texto", "imagem"])
    ap.add_argument("--pa", nargs="+", type=int, default=[1, 12, 2, 4], choices=list(PA_VALUES))
    ap.add_argument("--smoke", action="store_true", help="10 chaves, 3 folds, saída separada")
    ap.add_argument("--no-svm", action="store_true")
    args = ap.parse_args()

    n_keys, n_test, n_cv = (10, 2, 3) if args.smoke else (300, 60, 5)
    report_dir = OUT_DIR / ("smoke" if args.smoke else "reports")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    _log(f"braços={args.arms} pa={args.pa} chaves={n_keys} teste={n_test} folds={n_cv} "
         f"svm={not args.no_svm} -> {report_dir}")
    for arm in args.arms:
        data = generate(arm, n_keys)
        for pa in args.pa:
            run_config(arm, pa, data, n_keys, n_test, n_cv, report_dir, run_svm=not args.no_svm)
    _log("fila concluída")


if __name__ == "__main__":
    main()
