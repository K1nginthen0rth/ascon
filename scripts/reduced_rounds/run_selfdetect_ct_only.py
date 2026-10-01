"""
Auto-detecção de erro de implementação, em ciphertext-only.

Diferença para `run_pares_ct_only.py`: lá a classe negativa era GIFT-COFB
correto (outro algoritmo). Aqui as DUAS classes são o MESMO algoritmo — a
positiva com rodadas de inicialização reduzidas (o "erro proposital"), a
negativa com o algoritmo CORRETO. Qualquer separação vem então da fraqueza
introduzida, nunca da identidade do algoritmo. É o enquadramento limpo de
"o detector acusa a implementação errada".

Modelo de acesso (o mesmo aprovado em 14/09): mesma chave (mesmo
dispositivo), nonces de contador consecutivos (c, c+1 — diferem em 1 bit),
plaintexts DIFERENTES e desconhecidos. O adversário só vê C1 xor C2 do
primeiro bloco de taxa + tag; nada do plaintext.

Famílias:
  ascon    — Ascon-AEAD128, taxa 16 B. pa reduzido (1..4) vs pa=12 (correto).
  schwaemm — Schwaemm256-128, taxa 32 B. big reduzido (1,4) vs big=11 (correto).

Fecha duas pendências: (1) classe negativa = algoritmo correto, não GIFT;
(2) pa=3 preenche a fronteira entre pa=2 (detectável) e pa=4 (acaso). E
testa robustez do nonce (contador big-endian vs little-endian).

Protocolo idêntico ao runner de pares (Regras de Ouro): CTR_DRBG; mesmas
chaves/nonces/plaintexts entre as classes; key-holdout 240/60 (seed 42);
GroupKFold 5; modelos da produção (seed 7); bootstrap por chave; relato via
`report_eval`. Ablação por região (1o bloco de taxa / resto do payload / tag)
para localizar o vazamento.

Uso:
    python scripts/reduced_rounds/run_selfdetect_ct_only.py --smoke
    python scripts/reduced_rounds/run_selfdetect_ct_only.py --family ascon
    python scripts/reduced_rounds/run_selfdetect_ct_only.py --family schwaemm
    python scripts/reduced_rounds/run_selfdetect_ct_only.py --family ascon --nonce-endian little --pa 1 2
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
from scripts.reduced_rounds.build_variant import build_ascon, build_schwaemm  # noqa: E402
from scripts.reduced_rounds.reduced_wrapper import ReducedRoundsCipher  # noqa: E402
from scripts.run_v2_caminho_a import build_models, get_proba  # noqa: E402
from src.crypto.ascon_wrapper import AsconAEAD128  # noqa: E402
from src.crypto.sparkle_wrapper import Schwaemm256_128  # noqa: E402
from src.crypto.ctr_drbg import CTRDRBG  # noqa: E402
from src.eval.reporting import report_eval  # noqa: E402

SEED_GEN = 999003
SEED_SPLIT, SEED_MODEL, SEED_BOOT = 42, 7, 42
PAIRS_PER_KEY = 100
HEAD = 64
SVM_SUBSAMPLE = 10_000
NEEDS_SCALING = {"LinearSVC", "LogisticRegression"}

# family -> (nonce_bytes, rate_bytes, tag_bytes, reduced_values, correct_value,
#            builder, production_wrapper, algo_tag_no_reduced_wrapper)
FAMILIES = {
    "ascon": dict(nonce=16, rate=16, tag=16, reduced=(1, 2, 3, 4), correct=12,
                  build=lambda v: build_ascon(v, 8), algo="ascon",
                  prod=AsconAEAD128, label="Ascon-AEAD128", param="pa"),
    "schwaemm": dict(nonce=32, rate=32, tag=16, reduced=(1, 4), correct=11,
                     build=lambda v: build_schwaemm(7, v), algo="schwaemm",
                     prod=Schwaemm256_128, label="Schwaemm256-128", param="big"),
}
OUT_DIR = REPO_ROOT / "build" / "reduced_rounds" / "selfdetect_ct_only"


def _log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def _git_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT,
                              capture_output=True, text=True, check=True).stdout.strip()
    except Exception:  # noqa: BLE001
        return "desconhecido"


def _nonce(counter: int, nbytes: int, endian: str) -> bytes:
    """Contador de 16 bytes na endianness pedida, zero-pad à esquerda até nbytes
    (Schwaemm usa 32; os 16 MSB ficam zero, como no gerador v2)."""
    c16 = counter.to_bytes(16, endian)
    return c16 if nbytes == 16 else b"\x00" * (nbytes - 16) + c16


def _xor_region(a: bytes, b: bytes, rate: int, tag: int) -> np.ndarray:
    head = np.frombuffer(a[:HEAD], np.uint8) ^ np.frombuffer(b[:HEAD], np.uint8)
    tg = np.frombuffer(a[-tag:], np.uint8) ^ np.frombuffer(b[-tag:], np.uint8)
    return np.concatenate([head, tg])  # HEAD + tag bytes


def generate(family: str, arm: str, endian: str, n_keys: int) -> dict:
    F = FAMILIES[family]
    path = OUT_DIR / f"{family}_{arm}_{endian}_k{n_keys}.npz"
    if path.exists():
        _log(f"[{family}/{arm}/{endian}] reaproveitando {path.name}")
        z = np.load(path)
        return {k: z[k] for k in z.files}

    variants = {v: ReducedRoundsCipher(F["build"](v), F["algo"])
                for v in (*F["reduced"], F["correct"])}
    prod = F["prod"]()

    key_drbg = CTRDRBG(seed=SEED_GEN, label=f"selfdetect-keys-{family}")
    pt_drbg = CTRDRBG(seed=SEED_GEN, label=f"selfdetect-pt-{family}-{arm}")
    if arm == "texto":
        sampler = _TextPlaintextSampler(CORPORA_DIR, pt_drbg)
        sample, image_sampler = sampler.sample, None
    else:
        image_sampler = _ImagePlaintextSampler(IMAGES_DIR, IMAGES_MANIFEST, pt_drbg)
        sample = lambda: image_sampler.sample()[0]  # noqa: E731

    n = n_keys * PAIRS_PER_KEY
    width = HEAD + F["tag"]
    out = {f"v{v}": np.zeros((n, width), np.uint8) for v in variants}
    out["key_idx"] = np.repeat(np.arange(n_keys), PAIRS_PER_KEY).astype(np.int32)
    n_resampled = 0
    t0 = time.time()
    for k in range(n_keys):
        key = key_drbg.random_key(16)
        for j in range(PAIRS_PER_KEY):
            p1, p2 = sample(), sample()
            while p2 == p1:
                p2 = sample(); n_resampled += 1
            assert len(p1) == len(p2) == PLAINTEXT_BYTES
            c = 2 * (k * PAIRS_PER_KEY + j)
            n1, n2 = _nonce(c, F["nonce"], endian), _nonce(c + 1, F["nonce"], endian)
            i = k * PAIRS_PER_KEY + j
            for v, ciph in variants.items():
                out[f"v{v}"][i] = _xor_region(ciph.encrypt(key, n1, p1),
                                              ciph.encrypt(key, n2, p2),
                                              F["rate"], F["tag"])
            if i == 0:  # a variante correta tem que bater byte a byte com produção
                ref = prod.encrypt(key, n1, p1)
                got = variants[F["correct"]].encrypt(key, n1, p1)
                assert got == ref, f"{family} variante correta != produção"
        if (k + 1) % 50 == 0 or k + 1 == n_keys:
            _log(f"[{family}/{arm}/{endian}] chaves {k+1}/{n_keys} ({time.time()-t0:.0f}s)")

    np.savez(path, **out)
    path.with_suffix(".json").write_text(json.dumps(dict(
        family=family, arm=arm, nonce_endian=endian, n_keys=n_keys,
        pairs_per_key=PAIRS_PER_KEY, seed_gen=SEED_GEN, reduced=list(F["reduced"]),
        correct=F["correct"], rate_bytes=F["rate"], tag_bytes=F["tag"],
        n_resampled_equal_plaintext=n_resampled,
        n_reused_images=(image_sampler.n_reused if image_sampler else None),
        git_commit=_git_commit(), generated_at=datetime.now(timezone.utc).isoformat(),
    ), indent=2), encoding="utf-8")
    _log(f"[{family}/{arm}/{endian}] gerado em {time.time()-t0:.0f}s -> {path.name} "
         f"(reamostrados P1==P2: {n_resampled})")
    return out


def _device_level(proba, y, keys):
    logit = np.log(np.clip(proba[:, 1], 1e-12, 1)) - np.log(np.clip(proba[:, 0], 1e-12, 1))
    by, bk, bs = [], [], []
    for k in np.unique(keys):
        for lab in (0, 1):
            m = (keys == k) & (y == lab)
            if m.any():
                by.append(lab); bk.append(k); bs.append(logit[m].mean())
    p1 = 1.0 / (1.0 + np.exp(-np.clip(np.array(bs), -50, 50)))
    return np.array(by), np.column_stack([1 - p1, p1]), np.array(bk)


def run_config(family, arm, endian, red, data, n_keys, n_test, n_cv, report_dir,
               run_svm, ablation):
    F = FAMILIES[family]
    tag_e = "" if endian == "big" else f"_{endian}"
    run_id = f"selfdetect_{family}_{arm}{tag_e}_{F['param']}{red}"
    braco = f"{family}_{arm}{tag_e}"
    class_names = [f"{F['label']} correto ({F['param']}={F['correct']})",
                   f"{F['label']} erro ({F['param']}={red})"]
    _log(f"===== {run_id}: {class_names[1]} vs {class_names[0]}, plaintext={arm} =====")

    n = n_keys * PAIRS_PER_KEY
    X = np.vstack([np.unpackbits(data[f"v{red}"], axis=1),
                   np.unpackbits(data[f"v{F['correct']}"], axis=1)]).astype(np.float32)
    y = np.concatenate([np.ones(n, int), np.zeros(n, int)])
    kidx = np.concatenate([data["key_idx"], data["key_idx"]])
    key_ids = np.array([f"k{k:04d}" for k in kidx])
    sample_ids = np.array([f"{run_id}_k{k:04d}_p{i % PAIRS_PER_KEY:03d}_{'err' if lab else 'ok'}"
                           for i, (k, lab) in enumerate(zip(kidx, y))])

    keys = np.arange(n_keys)
    np.random.default_rng(SEED_SPLIT).shuffle(keys)
    te = np.isin(kidx, keys[:n_test])
    idx_trval, idx_test = np.where(~te)[0], np.where(te)[0]

    rate_bits = F["rate"] * 8
    for lab, name in ((1, "erro"), (0, "correto")):
        sel = (~te) & (y == lab)
        p = X[sel, :rate_bits].mean(axis=0)
        z = (p - 0.5) / np.sqrt(0.25 / sel.sum())
        _log(f"  diagnóstico (treino) 1o bloco de taxa, {name}: max|z|={np.abs(z).max():.1f}, "
             f"bits |z|>6: {(np.abs(z) > 6).sum()}/{rate_bits}")

    extra_base = dict(family=family, arm=arm, nonce_endian=endian, reduced=red,
                      correct=F["correct"], n_features=X.shape[1],
                      access_model="mesma chave, nonces consecutivos, P1!=P2 desconhecidos")

    def fit_eval(name, model, itr, iev, fold, region=None):
        Xtr, Xev = (X[itr], X[iev]) if region is None else (X[itr, region[0]:region[1]], X[iev, region[0]:region[1]])
        if name.split("_")[0] in NEEDS_SCALING:
            model = Pipeline([("scaler", StandardScaler()), ("clf", model)])
        model.fit(Xtr, y[itr])
        proba = get_proba(model, Xev)
        report_eval(run_id=run_id, caminho="A", modelo=name, braco=braco, fold=fold,
                    y_true=y[iev], y_pred=proba.argmax(axis=1), y_proba=proba,
                    sample_ids=list(sample_ids[iev]), key_ids=list(key_ids[iev]),
                    class_names=class_names, labels=[0, 1], out_dir=report_dir,
                    seed=SEED_BOOT, extra={**extra_base, "region": region})
        return proba

    for fold, (a, b) in enumerate(GroupKFold(n_splits=n_cv).split(idx_trval, groups=key_ids[idx_trval])):
        for name, model in build_models(seed=SEED_MODEL).items():
            fit_eval(name, model, idx_trval[a], idx_trval[b], fold)

    finals = dict(build_models(seed=SEED_MODEL))
    if run_svm:
        finals["SVM-RBF"] = None
    for name, model in finals.items():
        itr = idx_trval
        if name == "SVM-RBF":
            rng = np.random.default_rng(SEED_MODEL)
            itr = rng.choice(idx_trval, size=min(SVM_SUBSAMPLE, len(idx_trval)), replace=False)
            model = SVC(C=1.0, gamma=0.01, kernel="rbf", random_state=SEED_MODEL)
        proba = fit_eval(name, model, itr, idx_test, "final")
        by, bp, bk = _device_level(proba, y[idx_test], key_ids[idx_test])
        report_eval(run_id=run_id, caminho="A", modelo=f"{name}_dispositivo", braco=braco,
                    fold="final", y_true=by, y_pred=bp.argmax(axis=1), y_proba=bp,
                    sample_ids=[f"{k}_{'err' if lab else 'ok'}" for k, lab in zip(bk, by)],
                    key_ids=list(bk), class_names=class_names, labels=[0, 1],
                    out_dir=report_dir, seed=SEED_BOOT,
                    extra={**extra_base, "nivel": "dispositivo"})

    if ablation:
        regions = {"bloco1_taxa": (0, rate_bits), "resto_payload": (rate_bits, HEAD * 8),
                   "tag": (HEAD * 8, (HEAD + F["tag"]) * 8)}
        for reg, span in regions.items():
            for name in ("XGBoost", "LogisticRegression"):
                fit_eval(f"{name}_{reg}", build_models(seed=SEED_MODEL)[name],
                         idx_trval, idx_test, "final", region=span)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--family", nargs="+", default=["ascon", "schwaemm"], choices=list(FAMILIES))
    ap.add_argument("--arms", nargs="+", default=["texto", "imagem"], choices=["texto", "imagem"])
    ap.add_argument("--nonce-endian", nargs="+", default=["big"], choices=["big", "little"])
    ap.add_argument("--pa", nargs="+", type=int, default=None,
                    help="valores reduzidos a testar (default = todos da família)")
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--no-svm", action="store_true")
    ap.add_argument("--no-ablation", action="store_true")
    args = ap.parse_args()

    n_keys, n_test, n_cv = (10, 2, 3) if args.smoke else (300, 60, 5)
    report_dir = OUT_DIR / ("smoke" if args.smoke else "reports")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    _log(f"famílias={args.family} braços={args.arms} endian={args.nonce_endian} "
         f"chaves={n_keys} svm={not args.no_svm} -> {report_dir}")
    for family in args.family:
        reduced = args.pa if args.pa else FAMILIES[family]["reduced"]
        for endian in args.nonce_endian:
            for arm in args.arms:
                data = generate(family, arm, endian, n_keys)
                for red in [r for r in reduced if f"v{r}" in data]:
                    run_config(family, arm, endian, red, data, n_keys, n_test, n_cv,
                               report_dir, run_svm=not args.no_svm,
                               ablation=not args.no_ablation)
    _log("fila concluída")


if __name__ == "__main__":
    main()
