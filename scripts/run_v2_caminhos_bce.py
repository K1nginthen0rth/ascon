"""
Caminhos B (CNN1D), C (CNN2D) e E (Transformer hierárquico) do experimento
v2 — os caminhos profundos, que rodam em GPU. Ver
docs/plano_experimento_v2/06_implementacao_passo_a_passo.md Fases 7 e 8.

Protocolo comum aos três (decidido no planejamento):
  1. **Smoke test primeiro** (`--mode smoke`): amostra reduzida, 2 folds,
     poucas épocas — mede tempo/VRAM por arquitetura ANTES de comprometer
     sessões longas de GPU. É gate: sem smoke verde, não roda CV.
  2. **HP search** (`--mode hpsearch`): 8-12 configs aleatórias x **1 fold**
     por arquitetura. Registra tudo; config vencedora vai para a CV.
  3. **CV completa** (`--mode cv`): 5 folds da partição canônica
     `v2_folds.json`, seed 7.
  4. **Modelo final** (`--mode final`): trainval completo -> teste. No
     braço `controlado` (primário) roda com 3 seeds {7, 107, 207}; no
     braço `cru`, só seed 7 (decidido 2026-08-21).
  5. Latentes persistidos + diagnóstico de posto efetivo (SVD, variância
     explicada 95%) e contagem de parâmetros no relatório.

Memória: o parquet de CTs tem 11,8GB — este script NUNCA o carrega
inteiro. Lê só as linhas das chaves necessárias, por row group.

Uso:
    python scripts/run_v2_caminhos_bce.py --mode smoke  --path B
    python scripts/run_v2_caminhos_bce.py --mode cv     --path C --branch controlado
    python scripts/run_v2_caminhos_bce.py --mode final  --path E --branch controlado
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import numpy as np  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402
import torch  # noqa: E402

from src.eval.reporting import report_eval  # noqa: E402
from src.models.cnn1d import CiphertextCNN1D  # noqa: E402
from src.models.cnn2d import CiphertextCNN2D  # noqa: E402
from src.models.hybrid import (  # noqa: E402
    CiphertextCoocDataset, CiphertextSeqDataset, extract_latents, train_cnn,
)
from src.models.transformer1d import HierarchicalByteTransformer  # noqa: E402

DATASET_ID = "keyholdout_5class_v2"
PROCESSED = REPO_ROOT / "data" / "processed"
PQ_IN = PROCESSED / f"{DATASET_ID}.parquet"
FOLDS_JSON = PROCESSED / "v2_folds.json"
OUT_ROOT = REPO_ROOT / "reports" / "v2"

REAL_ALGORITHMS = ["Ascon-AEAD128", "GIFT-COFB", "Grain-128AEAD", "Schwaemm256-128"]
CONTROLLED_LEN = 65544
MAX_LEN_FULL = 65552

SEED_MODEL = 7
FINAL_SEEDS = [7, 107, 207]


# ---------------------------------------------------------------------------
# Carregamento (streaming, sem carregar os 11,8GB)
# ---------------------------------------------------------------------------

def load_cts(keys: set[str], classes: list[str], branch: str,
             max_samples: int | None = None) -> tuple[list[bytes], np.ndarray, list[str], list[str]]:
    """
    Carrega ciphertexts das chaves/classes pedidas, lendo o parquet por
    row group (nunca inteiro). Aplica o corte do braço `controlado`.

    Returns:
        (cts, y, sample_ids, key_ids)
    """
    label_map = {c: i for i, c in enumerate(classes)}
    pf = pq.ParquetFile(PQ_IN)
    cols = ["sample_id", "algorithm", "key_id", "ciphertext"]
    cts: list[bytes] = []
    ys: list[int] = []
    sids: list[str] = []
    kids: list[str] = []

    for gi in range(pf.num_row_groups):
        for batch in pf.iter_batches(batch_size=500, row_groups=[gi], columns=cols):
            for row in batch.to_pylist():
                if row["key_id"] not in keys or row["algorithm"] not in label_map:
                    continue
                ct = bytes(row["ciphertext"])
                if branch == "controlado":
                    ct = ct[:CONTROLLED_LEN]
                cts.append(ct)
                ys.append(label_map[row["algorithm"]])
                sids.append(row["sample_id"])
                kids.append(row["key_id"])
                if max_samples is not None and len(cts) >= max_samples:
                    return cts, np.asarray(ys), sids, kids
    return cts, np.asarray(ys), sids, kids


def load_folds() -> dict:
    return json.loads(FOLDS_JSON.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Arquiteturas
# ---------------------------------------------------------------------------

def build_model(path: str, n_classes: int, branch: str, hp: dict | None = None) -> torch.nn.Module:
    hp = hp or {}
    max_len = CONTROLLED_LEN if branch == "controlado" else MAX_LEN_FULL
    if path == "B":
        return CiphertextCNN1D(
            n_classes=n_classes, max_len=max_len,
            embed_dim=hp.get("embed_dim", 32),
            n_filters=hp.get("n_filters", 128),
            n_conv_blocks=hp.get("n_conv_blocks", 3),
            dropout=hp.get("dropout", 0.3),
        )
    if path == "C":
        return CiphertextCNN2D(n_classes=n_classes, dropout=hp.get("dropout", 0.3))
    if path == "E":
        return HierarchicalByteTransformer(
            n_classes=n_classes,
            max_len=hp.get("max_len", 65536),
            window=hp.get("window", 1024),
            patch=hp.get("patch", 16),
            d_model=hp.get("d_model", 64),
            n_heads=hp.get("n_heads", 4),
            n_local=hp.get("n_local", 2),
            n_global=hp.get("n_global", 2),
            dropout=hp.get("dropout", 0.1),
        )
    raise ValueError(f"caminho desconhecido: {path}")


def make_dataset(path: str, cts: list[bytes], y: np.ndarray, branch: str):
    """Caminho C usa co-ocorrência 256x256 (representação canônica);
    B e E consomem a sequência de bytes."""
    if path == "C":
        return CiphertextCoocDataset(cts, y)
    max_len = CONTROLLED_LEN if branch == "controlado" else MAX_LEN_FULL
    return CiphertextSeqDataset(cts, y, max_len)


def latent_mode(path: str) -> str:
    return "2d" if path == "C" else "1d"


def effective_rank(latents: np.ndarray, var_threshold: float = 0.95) -> int:
    """Posto efetivo do latente: nº de componentes que explicam 95% da
    variância (diagnóstico de colapso — um latente que colapsa para 1-2
    direções não carrega informação de classe, mesmo com loss baixa)."""
    if latents.ndim != 2 or latents.shape[0] < 2:
        return 0
    centered = latents - latents.mean(axis=0, keepdims=True)
    sv = np.linalg.svd(centered, compute_uv=False)
    energy = sv ** 2
    total = energy.sum()
    if total <= 0:
        return 0
    return int(np.searchsorted(np.cumsum(energy) / total, var_threshold) + 1)


def _save_latents(out_dir: Path, path: str, branch: str, tag: str,
                  lat: np.ndarray, sample_ids: list[str], key_ids: list[str],
                  y: np.ndarray) -> None:
    """
    Persiste o latente JUNTO com `sample_id`/`key_id`/rótulo.

    Salvar só a matriz `.npy` (como na primeira versão) obrigaria o
    Caminho D a confiar que a ordem das linhas é idêntica à da leitura do
    parquet — um acoplamento implícito que quebra em silêncio se a ordem
    de leitura mudar. Com o parquet companheiro, o Caminho D faz `merge`
    por `sample_id` e qualquer desalinhamento vira erro, não resultado
    errado.
    """
    import pandas as pd
    np.save(out_dir / f"latents_{path}_{branch}_{tag}.npy", lat)
    pd.DataFrame({
        "sample_id": sample_ids, "key_id": key_ids, "y": np.asarray(y),
        "row": np.arange(len(sample_ids)),
    }).to_parquet(out_dir / f"latents_{path}_{branch}_{tag}_index.parquet", index=False)


def predict_logits(model: torch.nn.Module, ds, device: str, batch_size: int) -> np.ndarray:
    from torch.utils.data import DataLoader
    loader = DataLoader(ds, batch_size=batch_size, shuffle=False, num_workers=0)
    model.eval()
    outs = []
    with torch.no_grad():
        for xb, _ in loader:
            outs.append(model(xb.to(device)).cpu().numpy())
    return np.concatenate(outs)


def softmax(z: np.ndarray) -> np.ndarray:
    e = np.exp(z - z.max(axis=1, keepdims=True))
    return e / e.sum(axis=1, keepdims=True)


# ---------------------------------------------------------------------------
# Modos
# ---------------------------------------------------------------------------

def run_smoke(path: str, branch: str, device: str, out_dir: Path,
              n_samples: int, epochs: int, batch_size: int) -> None:
    """Gate: mede tempo/VRAM/param antes de comprometer GPU em CV longa."""
    folds = load_folds()
    keys = set(folds["folds"][0]["train_keys"][:6]) | set(folds["folds"][0]["val_keys"][:3])
    print(f"[smoke {path}] carregando até {n_samples} amostras de {len(keys)} chaves...")
    cts, y, sids, kids = load_cts(keys, REAL_ALGORITHMS, branch, max_samples=n_samples)
    print(f"[smoke {path}] {len(cts)} amostras, classes={np.bincount(y).tolist()}")

    n_val = max(1, len(cts) // 5)
    tr_ds = make_dataset(path, cts[n_val:], y[n_val:], branch)
    va_ds = make_dataset(path, cts[:n_val], y[:n_val], branch)

    model = build_model(path, len(REAL_ALGORITHMS), branch).to(device)
    n_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"[smoke {path}] parâmetros treináveis: {n_params:,}")

    t0 = time.perf_counter()
    model, best_ep = train_cnn(
        model, tr_ds, va_ds, device=device, n_epochs=epochs, patience=epochs,
        seed=SEED_MODEL, verbose=True, cnn_id=f"smoke_{path}",
        batch_size=batch_size, resume=False,
    )
    dt = time.perf_counter() - t0
    per_epoch = dt / max(epochs, 1)
    print(f"[smoke {path}] {epochs} épocas em {dt:.0f}s ({per_epoch:.0f}s/época "
          f"para {len(tr_ds)} amostras)")

    # Extrapolação honesta para a CV completa (96.000 trainval, 5 folds).
    scale = 96_000 / max(len(tr_ds), 1)
    est_cv_h = per_epoch * scale * 30 * 5 / 3600  # 30 épocas x 5 folds
    print(f"[smoke {path}] ESTIMATIVA CV completa (30 épocas x 5 folds): {est_cv_h:.1f}h")
    if device == "cuda":
        print(f"[smoke {path}] VRAM pico: "
              f"{torch.cuda.max_memory_allocated() / 1e9:.2f} GB")

    logits = predict_logits(model, va_ds, device, batch_size)
    report_eval(
        run_id=f"{DATASET_ID}_smoke", caminho=path, modelo=f"smoke_{path}",
        braco=branch, fold="smoke",
        y_true=y[:n_val], y_pred=logits.argmax(1), y_proba=softmax(logits),
        sample_ids=sids[:n_val], key_ids=kids[:n_val],
        class_names=REAL_ALGORITHMS, labels=list(range(len(REAL_ALGORITHMS))),
        out_dir=out_dir, n_bootstrap=200,
        extra={"n_params": n_params, "s_per_epoch": round(per_epoch, 1),
               "est_cv_hours": round(est_cv_h, 2), "best_epoch": best_ep,
               "n_train": len(tr_ds), "device": device},
    )


def run_cv(path: str, branch: str, device: str, out_dir: Path,
           epochs: int, batch_size: int, hp: dict | None = None) -> None:
    folds = load_folds()
    for fold_spec in folds["folds"]:
        fi = fold_spec["fold"]
        tr_keys, va_keys = set(fold_spec["train_keys"]), set(fold_spec["val_keys"])
        print(f"\n[{path} fold {fi}] carregando {len(tr_keys)} chaves treino / "
              f"{len(va_keys)} val...")
        cts_tr, y_tr, _, _ = load_cts(tr_keys, REAL_ALGORITHMS, branch)
        cts_va, y_va, sid_va, kid_va = load_cts(va_keys, REAL_ALGORITHMS, branch)

        tr_ds = make_dataset(path, cts_tr, y_tr, branch)
        va_ds = make_dataset(path, cts_va, y_va, branch)
        model = build_model(path, len(REAL_ALGORITHMS), branch, hp).to(device)
        n_params = sum(p.numel() for p in model.parameters() if p.requires_grad)

        t0 = time.perf_counter()
        model, best_ep = train_cnn(
            model, tr_ds, va_ds, device=device, n_epochs=epochs, patience=5,
            seed=SEED_MODEL, fold_id=fi, cnn_id=f"{path}_{branch}",
            ckpt_dir=out_dir / "ckpts", batch_size=batch_size, verbose=True,
        )
        logits = predict_logits(model, va_ds, device, batch_size)
        lat = extract_latents(model, cts_va, CONTROLLED_LEN if branch == "controlado"
                              else MAX_LEN_FULL, latent_mode(path), device, batch_size)

        report_eval(
            run_id=f"{DATASET_ID}_4class", caminho=path, modelo=f"CNN{path}" if path != "E" else "Transformer",
            braco=branch, fold=fi,
            y_true=y_va, y_pred=logits.argmax(1), y_proba=softmax(logits),
            sample_ids=sid_va, key_ids=kid_va,
            class_names=REAL_ALGORITHMS, labels=list(range(len(REAL_ALGORITHMS))),
            out_dir=out_dir, extra={
                "n_params": n_params, "best_epoch": best_ep,
                "train_time_s": round(time.perf_counter() - t0, 1),
                "latent_effective_rank_95": effective_rank(lat),
                "latent_dim": int(lat.shape[1]), "hp": hp or {},
            },
        )
        _save_latents(out_dir, path, branch, f"fold{fi}", lat, sid_va, kid_va, y_va)


def run_final(path: str, branch: str, device: str, out_dir: Path,
              epochs: int, batch_size: int, hp: dict | None = None) -> None:
    """Modelo final: trainval completo -> teste. 3 seeds só no braço
    controlado (primário); no cru, seed 7 apenas."""
    folds = load_folds()
    tv_keys, te_keys = set(folds["trainval_keys"]), set(folds["test_keys"])
    cts_tv, y_tv, _, _ = load_cts(tv_keys, REAL_ALGORITHMS, branch)
    cts_te, y_te, sid_te, kid_te = load_cts(te_keys, REAL_ALGORITHMS, branch)
    tr_ds = make_dataset(path, cts_tv, y_tv, branch)
    te_ds = make_dataset(path, cts_te, y_te, branch)

    seeds = FINAL_SEEDS if branch == "controlado" else [SEED_MODEL]
    for seed in seeds:
        model = build_model(path, len(REAL_ALGORITHMS), branch, hp).to(device)
        n_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
        t0 = time.perf_counter()
        model, best_ep = train_cnn(
            model, tr_ds, te_ds, device=device, n_epochs=epochs, patience=5,
            seed=seed, fold_id=99, cnn_id=f"{path}_{branch}_final_s{seed}",
            ckpt_dir=out_dir / "ckpts", batch_size=batch_size, verbose=True,
        )
        logits = predict_logits(model, te_ds, device, batch_size)
        lat = extract_latents(model, cts_te, CONTROLLED_LEN if branch == "controlado"
                              else MAX_LEN_FULL, latent_mode(path), device, batch_size)
        report_eval(
            run_id=f"{DATASET_ID}_4class", caminho=path,
            modelo=f"CNN{path}" if path != "E" else "Transformer",
            braco=branch, fold=f"final_seed{seed}",
            y_true=y_te, y_pred=logits.argmax(1), y_proba=softmax(logits),
            sample_ids=sid_te, key_ids=kid_te,
            class_names=REAL_ALGORITHMS, labels=list(range(len(REAL_ALGORITHMS))),
            out_dir=out_dir, extra={
                "n_params": n_params, "seed": seed, "best_epoch": best_ep,
                "train_time_s": round(time.perf_counter() - t0, 1),
                "latent_effective_rank_95": effective_rank(lat),
                "latent_dim": int(lat.shape[1]), "hp": hp or {},
            },
        )
        _save_latents(out_dir, path, branch, f"final_s{seed}", lat, sid_te, kid_te, y_te)


def run_hpsearch(path: str, branch: str, device: str, out_dir: Path,
                 epochs: int, batch_size: int, n_configs: int) -> None:
    """8-12 configs aleatórias x 1 fold (decisão C3 do planejamento).
    Registra todas; a vencedora por F1 de validação vai para a CV."""
    rng = np.random.default_rng(SEED_MODEL)
    folds = load_folds()
    fold_spec = folds["folds"][0]
    cts_tr, y_tr, _, _ = load_cts(set(fold_spec["train_keys"]), REAL_ALGORITHMS, branch)
    cts_va, y_va, sid_va, kid_va = load_cts(set(fold_spec["val_keys"]), REAL_ALGORITHMS, branch)
    tr_ds = make_dataset(path, cts_tr, y_tr, branch)
    va_ds = make_dataset(path, cts_va, y_va, branch)

    for ci in range(n_configs):
        if path == "B":
            hp = {"n_filters": int(rng.choice([64, 128, 256])),
                  "n_conv_blocks": int(rng.choice([2, 3, 4])),
                  "dropout": float(rng.choice([0.1, 0.3, 0.5])),
                  "embed_dim": int(rng.choice([16, 32, 64]))}
        elif path == "C":
            hp = {"dropout": float(rng.choice([0.1, 0.3, 0.5]))}
        else:
            hp = {"d_model": int(rng.choice([64, 128])),
                  "n_heads": int(rng.choice([4, 8])),
                  "n_local": int(rng.choice([1, 2, 3])),
                  "n_global": int(rng.choice([1, 2])),
                  "patch": int(rng.choice([8, 16, 32])),
                  "dropout": float(rng.choice([0.1, 0.3]))}
        lr = float(rng.choice([1e-3, 5e-4, 1e-4]))
        print(f"\n[hpsearch {path} cfg {ci}] {hp} lr={lr}")

        model = build_model(path, len(REAL_ALGORITHMS), branch, hp).to(device)
        model, best_ep = train_cnn(
            model, tr_ds, va_ds, device=device, lr=lr, n_epochs=epochs, patience=3,
            seed=SEED_MODEL, cnn_id=f"hp_{path}_{ci}", batch_size=batch_size,
            resume=False, verbose=True,
        )
        logits = predict_logits(model, va_ds, device, batch_size)
        report_eval(
            run_id=f"{DATASET_ID}_hpsearch", caminho=path,
            modelo=f"{path}_cfg{ci}", braco=branch, fold=0,
            y_true=y_va, y_pred=logits.argmax(1), y_proba=softmax(logits),
            sample_ids=sid_va, key_ids=kid_va,
            class_names=REAL_ALGORITHMS, labels=list(range(len(REAL_ALGORITHMS))),
            out_dir=out_dir, n_bootstrap=200,
            extra={"hp": hp, "lr": lr, "best_epoch": best_ep,
                   "n_params": sum(p.numel() for p in model.parameters())},
        )


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    p = argparse.ArgumentParser()
    p.add_argument("--path", required=True, choices=["B", "C", "E"])
    p.add_argument("--mode", required=True, choices=["smoke", "hpsearch", "cv", "final"])
    p.add_argument("--branch", default="controlado", choices=["cru", "controlado"])
    p.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    p.add_argument("--epochs", type=int, default=None)
    p.add_argument("--batch-size", type=int, default=8)
    p.add_argument("--smoke-samples", type=int, default=500)
    p.add_argument("--n-configs", type=int, default=10)
    p.add_argument("--hp-json", default=None,
                   help="JSON com a config vencedora do hpsearch (modo cv/final).")
    args = p.parse_args()

    epochs = args.epochs if args.epochs is not None else (3 if args.mode == "smoke" else 30)
    out_dir = OUT_ROOT / f"caminho_{args.path.lower()}" / args.branch
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "ckpts").mkdir(exist_ok=True)
    hp = json.loads(Path(args.hp_json).read_text()) if args.hp_json else None

    print(f"Caminho {args.path} | modo={args.mode} | braço={args.branch} | "
          f"device={args.device} | épocas={epochs} | batch={args.batch_size}")
    if args.device == "cpu":
        print("[AVISO] rodando em CPU — os caminhos profundos foram planejados "
              "para GPU (Kaggle T4 / Colab). Use só para smoke.")

    t0 = time.perf_counter()
    if args.mode == "smoke":
        run_smoke(args.path, args.branch, args.device, out_dir,
                  args.smoke_samples, epochs, args.batch_size)
    elif args.mode == "hpsearch":
        run_hpsearch(args.path, args.branch, args.device, out_dir,
                     epochs, args.batch_size, args.n_configs)
    elif args.mode == "cv":
        run_cv(args.path, args.branch, args.device, out_dir, epochs,
               args.batch_size, hp)
    else:
        run_final(args.path, args.branch, args.device, out_dir, epochs,
                  args.batch_size, hp)
    print(f"\nConcluído em {(time.perf_counter() - t0) / 60:.1f}min — {out_dir}")


if __name__ == "__main__":
    main()
