"""
Detecção de REUSO DE NONCE (erro de USO, não de implementação), em
ciphertext-only, com os 4 algoritmos em RODADAS COMPLETAS (wrappers de
produção, validados por KAT).

Erro real e documentado: contador de nonce que zera no reboot (RIOT-OS
#16844) ou servidores repetindo nonce em GCM/TLS (Böck et al. 2016). Sob
reuso, duas mensagens da mesma (chave, nonce) vazam: C1 xor C2 no primeiro
bloco de taxa é exatamente P1 xor P2 (o keystream inicial, idêntico, se
cancela). Em texto, P1 xor P2 tem o bit 7 de cada byte zerado; um keystream
independente (nonce distinto) não tem. O adversário não conhece P1 nem P2 —
só explora que criptograma correto (nonce distinto) é uniforme e o com reuso
não é.

Duas tarefas:
  deteccao  — binário POR algoritmo: reuso vs respeito (nonce distinto). É a
              "acusação da falha".
  algoritmo — 4-classes SÓ nas amostras com reuso: quanto de P1 xor P2 vaza
              denuncia o algoritmo (taxa/bloco). Ascon/GIFT vazam 16 B,
              Schwaemm 32 B, Grain (cifra de fluxo) a mensagem inteira. É o
              efeito de tamanho de bloco da RSL (Tan e Ji 2016).

Modelo de acesso ciphertext-only: o adversário vê só C1 xor C2 dos primeiros
HEAD bytes; nada do plaintext. Protocolo (Regras de Ouro): CTR_DRBG; mesmas
chaves/nonces/plaintexts entre algoritmos; key-holdout 240/60; GroupKFold 5;
modelos da produção; bootstrap por chave; relato via `report_eval`.

Uso:
    python scripts/reduced_rounds/run_nonce_reuse_ct_only.py --smoke
    python scripts/reduced_rounds/run_nonce_reuse_ct_only.py
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
    _ImagePlaintextSampler, _TextPlaintextSampler, _nonce_for_algorithm,
)
from scripts.run_v2_caminho_a import build_models, get_proba  # noqa: E402
from src.crypto.ascon_wrapper import AsconAEAD128  # noqa: E402
from src.crypto.gift_cofb_wrapper import GiftCOFB  # noqa: E402
from src.crypto.grain_wrapper import Grain128AEAD  # noqa: E402
from src.crypto.sparkle_wrapper import Schwaemm256_128  # noqa: E402
from src.crypto.ctr_drbg import CTRDRBG  # noqa: E402
from src.eval.reporting import report_eval  # noqa: E402

SEED_GEN = 999004
SEED_SPLIT, SEED_MODEL, SEED_BOOT = 42, 7, 42
PAIRS_PER_KEY = 100
HEAD = 128          # cobre 1o bloco de Ascon/GIFT (16), Schwaemm (32) e um pedaço do Grain
SVM_SUBSAMPLE = 10_000
NEEDS_SCALING = {"LinearSVC", "LogisticRegression"}
ALGOS = [("Ascon", AsconAEAD128), ("GIFT", GiftCOFB),
         ("Grain", Grain128AEAD), ("Schwaemm", Schwaemm256_128)]
OUT_DIR = REPO_ROOT / "build" / "reduced_rounds" / "nonce_reuse_ct_only"


def _log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def _git_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT,
                              capture_output=True, text=True, check=True).stdout.strip()
    except Exception:  # noqa: BLE001
        return "desconhecido"


def generate(arm: str, n_keys: int) -> dict:
    """Para cada (chave, par) e cada algoritmo, XOR dos primeiros HEAD bytes
    em dois cenários: reuso (mesmo nonce) e respeito (nonces distintos)."""
    path = OUT_DIR / f"reuse_{arm}_k{n_keys}.npz"
    if path.exists():
        _log(f"[{arm}] reaproveitando {path.name}")
        z = np.load(path)
        return {k: z[k] for k in z.files}

    ciphers = {name: cls() for name, cls in ALGOS}
    key_drbg = CTRDRBG(seed=SEED_GEN, label="reuse-keys")
    nonce_drbg = CTRDRBG(seed=SEED_GEN, label="reuse-nonces")
    pt_drbg = CTRDRBG(seed=SEED_GEN, label=f"reuse-pt-{arm}")
    if arm == "texto":
        sampler = _TextPlaintextSampler(CORPORA_DIR, pt_drbg)
        sample, image_sampler = sampler.sample, None
    else:
        image_sampler = _ImagePlaintextSampler(IMAGES_DIR, IMAGES_MANIFEST, pt_drbg)
        sample = lambda: image_sampler.sample()[0]  # noqa: E731

    n = n_keys * PAIRS_PER_KEY
    out = {}
    for name, _ in ALGOS:
        out[f"{name}_reuse"] = np.zeros((n, HEAD), np.uint8)
        out[f"{name}_respect"] = np.zeros((n, HEAD), np.uint8)
    out["key_idx"] = np.repeat(np.arange(n_keys), PAIRS_PER_KEY).astype(np.int32)
    n_resampled = 0
    t0 = time.time()
    for k in range(n_keys):
        key = key_drbg.random_key(16)
        for j in range(PAIRS_PER_KEY):
            p1, p2 = sample(), sample()
            while p2 == p1:
                p2 = sample(); n_resampled += 1
            base_a = nonce_drbg.generate(16)   # nonce compartilhado (reuso)
            base_b = nonce_drbg.generate(16)   # nonce distinto (respeito)
            i = k * PAIRS_PER_KEY + j
            for name, _ in ALGOS:
                c = ciphers[name]
                na = _nonce_for_algorithm(base_a, c.NPUBBYTES)
                nb = _nonce_for_algorithm(base_b, c.NPUBBYTES)
                r1 = np.frombuffer(c.encrypt(key, na, p1)[:HEAD], np.uint8)
                r2 = np.frombuffer(c.encrypt(key, na, p2)[:HEAD], np.uint8)  # MESMO nonce
                s2 = np.frombuffer(c.encrypt(key, nb, p2)[:HEAD], np.uint8)  # nonce distinto
                out[f"{name}_reuse"][i] = r1 ^ r2
                out[f"{name}_respect"][i] = r1 ^ s2
        if (k + 1) % 50 == 0 or k + 1 == n_keys:
            _log(f"[{arm}] chaves {k+1}/{n_keys} ({time.time()-t0:.0f}s)")

    np.savez(path, **out)
    path.with_suffix(".json").write_text(json.dumps(dict(
        arm=arm, n_keys=n_keys, pairs_per_key=PAIRS_PER_KEY, seed_gen=SEED_GEN,
        head_bytes=HEAD, algos=[a for a, _ in ALGOS],
        n_resampled_equal_plaintext=n_resampled,
        n_reused_images=(image_sampler.n_reused if image_sampler else None),
        git_commit=_git_commit(), generated_at=datetime.now(timezone.utc).isoformat(),
    ), indent=2), encoding="utf-8")
    _log(f"[{arm}] gerado em {time.time()-t0:.0f}s -> {path.name}")
    return out


def _fit_eval(run_id, braco, X, y, key_ids, sample_ids, itr, iev, name, model,
              class_names, labels, report_dir, extra):
    if name.split("_")[0] in NEEDS_SCALING:
        model = Pipeline([("scaler", StandardScaler()), ("clf", model)])
    model.fit(X[itr], y[itr])
    proba = get_proba(model, X[iev])
    report_eval(run_id=run_id, caminho="A", modelo=name, braco=braco, fold="final",
                y_true=y[iev], y_pred=proba.argmax(axis=1), y_proba=proba,
                sample_ids=list(sample_ids[iev]), key_ids=list(key_ids[iev]),
                class_names=class_names, labels=labels, out_dir=report_dir,
                seed=SEED_BOOT, extra=extra)
    return proba


def _split(kidx, n_keys, n_test):
    keys = np.arange(n_keys)
    np.random.default_rng(SEED_SPLIT).shuffle(keys)
    te = np.isin(kidx, keys[:n_test])
    return np.where(~te)[0], np.where(te)[0]


def run_detection(arm, data, n_keys, n_test, n_cv, report_dir, run_svm):
    """Binário por algoritmo: reuso vs respeito."""
    n = n_keys * PAIRS_PER_KEY
    for name, _ in ALGOS:
        run_id = f"nonce_reuse_deteccao_{arm}_{name}"
        _log(f"===== {run_id}: reuso vs respeito, {name}, plaintext={arm} =====")
        X = np.vstack([np.unpackbits(data[f"{name}_reuse"], axis=1),
                       np.unpackbits(data[f"{name}_respect"], axis=1)]).astype(np.float32)
        y = np.concatenate([np.ones(n, int), np.zeros(n, int)])
        kidx = np.concatenate([data["key_idx"], data["key_idx"]])
        key_ids = np.array([f"k{v:04d}" for v in kidx])
        sample_ids = np.array([f"{run_id}_k{v:04d}_{'reuse' if lab else 'ok'}_{i}"
                               for i, (v, lab) in enumerate(zip(kidx, y))])
        itr, iev = _split(kidx, n_keys, n_test)
        cn = ["nonce distinto (ok)", "reuso de nonce"]
        extra = dict(task="deteccao", algo=name, arm=arm)
        for fold, (a, b) in enumerate(GroupKFold(n_splits=n_cv).split(itr, groups=key_ids[itr])):
            for mn, mdl in build_models(seed=SEED_MODEL).items():
                _fe_fold(run_id, f"reuse_{arm}", X, y, key_ids, sample_ids, itr[a], itr[b],
                         mn, mdl, cn, [0, 1], report_dir, {**extra, "fold": fold}, fold)
        finals = dict(build_models(seed=SEED_MODEL))
        if run_svm:
            finals["SVM-RBF"] = SVC(C=1.0, gamma=0.01, kernel="rbf", random_state=SEED_MODEL)
        for mn, mdl in finals.items():
            f_itr = itr
            if mn == "SVM-RBF":
                f_itr = np.random.default_rng(SEED_MODEL).choice(
                    itr, size=min(SVM_SUBSAMPLE, len(itr)), replace=False)
            _fit_eval(run_id, f"reuse_{arm}", X, y, key_ids, sample_ids, f_itr, iev,
                      mn, mdl, cn, [0, 1], report_dir, extra)


def _fe_fold(run_id, braco, X, y, key_ids, sample_ids, itr, iev, name, model,
             class_names, labels, report_dir, extra, fold):
    if name in NEEDS_SCALING:
        model = Pipeline([("scaler", StandardScaler()), ("clf", model)])
    model.fit(X[itr], y[itr])
    proba = get_proba(model, X[iev])
    report_eval(run_id=run_id, caminho="A", modelo=name, braco=braco, fold=fold,
                y_true=y[iev], y_pred=proba.argmax(axis=1), y_proba=proba,
                sample_ids=list(sample_ids[iev]), key_ids=list(key_ids[iev]),
                class_names=class_names, labels=labels, out_dir=report_dir,
                seed=SEED_BOOT, extra=extra)


def run_algo_id(arm, data, n_keys, n_test, n_cv, report_dir):
    """4-classes só nas amostras com reuso: qual algoritmo (tamanho do vazamento)."""
    run_id = f"nonce_reuse_algoritmo_{arm}"
    _log(f"===== {run_id}: identificar algoritmo sob reuso (4 classes), plaintext={arm} =====")
    n = n_keys * PAIRS_PER_KEY
    blocks = [np.unpackbits(data[f"{name}_reuse"], axis=1) for name, _ in ALGOS]
    X = np.vstack(blocks).astype(np.float32)
    y = np.concatenate([np.full(n, i) for i in range(len(ALGOS))])
    kidx = np.concatenate([data["key_idx"]] * len(ALGOS))
    key_ids = np.array([f"k{v:04d}" for v in kidx])
    sample_ids = np.array([f"{run_id}_{ALGOS[lab][0]}_k{v:04d}_{i}"
                           for i, (v, lab) in enumerate(zip(kidx, y))])
    itr, iev = _split(kidx, n_keys, n_test)
    cn = [a for a, _ in ALGOS]
    labels = list(range(len(ALGOS)))
    extra = dict(task="algoritmo_sob_reuso", arm=arm)
    for fold, (a, b) in enumerate(GroupKFold(n_splits=n_cv).split(itr, groups=key_ids[itr])):
        for mn, mdl in build_models(seed=SEED_MODEL).items():
            _fe_fold(run_id, f"reuse_{arm}", X, y, key_ids, sample_ids, itr[a], itr[b],
                     mn, mdl, cn, labels, report_dir, {**extra, "fold": fold}, fold)
    for mn, mdl in build_models(seed=SEED_MODEL).items():
        _fit_eval(run_id, f"reuse_{arm}", X, y, key_ids, sample_ids, itr, iev,
                  mn, mdl, cn, labels, report_dir, extra)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--arms", nargs="+", default=["texto", "imagem"], choices=["texto", "imagem"])
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--no-svm", action="store_true")
    args = ap.parse_args()
    n_keys, n_test, n_cv = (10, 2, 3) if args.smoke else (300, 60, 5)
    report_dir = OUT_DIR / ("smoke" if args.smoke else "reports")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    _log(f"braços={args.arms} chaves={n_keys} svm={not args.no_svm} -> {report_dir}")
    for arm in args.arms:
        data = generate(arm, n_keys)
        run_detection(arm, data, n_keys, n_test, n_cv, report_dir, run_svm=not args.no_svm)
        run_algo_id(arm, data, n_keys, n_test, n_cv, report_dir)
    _log("fila concluída")


if __name__ == "__main__":
    main()
