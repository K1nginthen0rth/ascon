"""
Experimento CNN — Ascon-AEAD128 vs GIFT-COFB (60k, 64KB CT)

Modos executados:
  cnn1d_direct      : CNN 1D end-to-end → F1
  cnn1d_latent_rf   : CNN 1D latent (512-D) → RandomForest → F1
  cnn1d_latent_lsvc : CNN 1D latent (512-D) → LinearSVC   → F1
  cnn2d_direct      : CNN 2D end-to-end (co-ocorrência 256×256) → F1
  cnn2d_latent_rf   : CNN 2D latent (128-D) → RandomForest → F1
  cnn2d_latent_lsvc : CNN 2D latent (128-D) → LinearSVC   → F1

Protocolo: 5-fold GroupKFold CV (key-holdout) + modelo final no test holdout.
Seeds: modelo=7, bootstrap=42.

CNN1D trunca em 4096 bytes. CNN2D usa mapa de co-ocorrência 256×256 (CT completo).
Checkpoints por época em reports/.../ckpts/ (retomável em spot instances).
MLflow opiconal (graceful fallback se não instalado).

Uso:
    python scripts/run_cnn_experiments_60k.py
    python scripts/run_cnn_experiments_60k.py --skip-cv   # reutiliza cache CV
"""
from __future__ import annotations

import argparse
import json
import math
import pickle
import sys
import time
from itertools import combinations
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src" / "crypto"))

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import balanced_accuracy_score, f1_score
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler
from sklearn.svm import LinearSVC
from torch.utils.data import DataLoader, Dataset

from src.eval.metrics import compute_metrics, mcnemar_test
from src.models.cnn1d import CiphertextCNN1D
from src.models.cnn2d import CiphertextCNN2D
from src.models.ciphertext_to_image import bytes_to_cooccurrence

try:
    import mlflow
    _MLFLOW = True
except ImportError:
    _MLFLOW = False

# ---------------------------------------------------------------------------
# Configuração — altere aqui para trocar parâmetros sem tocar no código
# ---------------------------------------------------------------------------

DATASET_ID   = "keyholdout_2class_60k_v1"
DATA_DIR     = REPO_ROOT / "data" / "processed"
RAW_PARQUET  = DATA_DIR / f"{DATASET_ID}.parquet"
REPORTS_DIR  = REPO_ROOT / "reports" / f"{DATASET_ID}_cnn"
CM_DIR       = REPORTS_DIR / "confusion_matrices"
CKPT_DIR     = REPORTS_DIR / "ckpts"

# Caminho B usa prefixo por viabilidade em CPU.
# Caminho D (run_hybrid_60k.py) usa MAX_LEN_D_CNN1D (CT completo) — não este script.
MAX_LEN_B        = 4096    # CNN1D Caminho B — prefixo; viável em CPU
MAX_LEN_D_CNN1D  = 65552   # CNN1D Caminho D — referência; NÃO usado neste script

CNN1D_MAX_LEN    = MAX_LEN_B   # Caminho B: prefixo
CNN2D_IMAGE_SIZE = 256

# Hiperparâmetros de treino CNN
BATCH_SIZE  = 64
N_EPOCHS    = 30
LR          = 1e-3
PATIENCE    = 5
SEED_MODEL  = 7
SEED_BOOT   = 42
N_BOOTSTRAP = 1000
N_FOLDS     = 5

# Hiperparâmetros dos classificadores clássicos sobre latents
RF_N_ESTIMATORS = 300
LSVC_C          = 1.0

REPORTS_DIR.mkdir(parents=True, exist_ok=True)
CM_DIR.mkdir(parents=True, exist_ok=True)
CKPT_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# DataLoader worker init
# ---------------------------------------------------------------------------

def _worker_init_fn(worker_id: int) -> None:
    np.random.seed(torch.initial_seed() % 2**32)


# ---------------------------------------------------------------------------
# Dataset lazy (converte bytes → tensor sob demanda; evita OOM com 64KB CT)
# ---------------------------------------------------------------------------

class _SeqDataset(Dataset):
    """CT bytes → int64 tensor (max_len,) — para CNN 1D."""

    def __init__(self, cts: list, labels: np.ndarray, max_len: int) -> None:
        self.cts     = cts
        self.labels  = torch.from_numpy(labels.astype(np.int64))
        self.max_len = max_len

    def __len__(self) -> int:
        return len(self.cts)

    def __getitem__(self, idx: int):
        arr = np.frombuffer(bytes(self.cts[idx]), dtype=np.uint8)
        if arr.size >= self.max_len:
            arr = arr[: self.max_len]
        else:
            pad = np.zeros(self.max_len - arr.size, dtype=np.uint8)
            arr = np.concatenate([arr, pad])
        return torch.from_numpy(arr.astype(np.int64)), self.labels[idx]


class _CoocDataset(Dataset):
    """CT bytes → co-ocorrência de bigramas (1, 256, 256) float32 — para CNN 2D.

    Usa o CT completo (sem truncamento) via bytes_to_cooccurrence().
    Representação metodologicamente defensável: adjacência real de bytes.
    """

    def __init__(self, cts: list, labels: np.ndarray) -> None:
        self.cts    = cts
        self.labels = torch.from_numpy(labels.astype(np.int64))

    def __len__(self) -> int:
        return len(self.cts)

    def __getitem__(self, idx: int):
        img = bytes_to_cooccurrence(bytes(self.cts[idx]))
        return torch.from_numpy(img[np.newaxis, :, :]), self.labels[idx]


# ---------------------------------------------------------------------------
# Funções de treino/avaliação CNN (loop reutilizável)
# ---------------------------------------------------------------------------

def _make_loader(ds: Dataset, shuffle: bool) -> DataLoader:
    return DataLoader(
        ds, batch_size=BATCH_SIZE, shuffle=shuffle,
        num_workers=4, persistent_workers=True,
        worker_init_fn=_worker_init_fn,
    )


def _train_cnn(
    model:       nn.Module,
    train_ds:    Dataset,
    val_ds:      Dataset,
    y_val:       np.ndarray,
    device:      str,
    fold_id:     int            = 0,
    model_name:  str            = "",
    ckpt_dir:    Optional[Path] = None,
    verbose:     bool           = False,
    seed:        int            = SEED_MODEL,
    resume:      bool           = True,
) -> tuple[nn.Module, int, dict]:
    """Treina model com early stopping no val_loss.

    Salva checkpoint após cada época (retomável em spot instances).
    Loga train_loss / val_loss / val_f1_macro por época no MLflow se disponível.
    resume=True carrega checkpoint existente; False ignora e começa do zero.
    Retorna (model_com_best_weights, best_epoch, history).
    """
    torch.manual_seed(seed)
    np.random.seed(seed)

    optim        = torch.optim.Adam(model.parameters(), lr=LR)
    crit         = nn.CrossEntropyLoss()
    train_loader = _make_loader(train_ds, shuffle=True)
    val_loader   = _make_loader(val_ds,   shuffle=False)

    history: dict = {"train_loss": [], "val_loss": [], "val_f1_macro": []}
    best_val, best_state, best_epoch, no_imp = float("inf"), None, 0, 0
    start_ep = 1

    ckpt_path = (ckpt_dir / f"{model_name}_fold{fold_id}.pt") if ckpt_dir else None

    if resume and ckpt_path and ckpt_path.exists():
        ckpt = torch.load(ckpt_path, map_location=device)
        model.load_state_dict(ckpt["model_state"])
        optim.load_state_dict(ckpt["optimizer_state"])
        best_val   = ckpt["best_val_loss"]
        best_epoch = ckpt["best_epoch"]
        no_imp     = ckpt.get("no_imp", 0)
        start_ep   = ckpt["epoch"] + 1
        torch.set_rng_state(ckpt["rng_state"])
        best_state = {k: v.clone().cpu() for k, v in model.state_dict().items()}
        history    = ckpt.get("history", history)
        if verbose:
            print(f"       Resumindo do fold {fold_id} epoch {ckpt['epoch']} "
                  f"(best_ep={best_epoch}  best_val={best_val:.4f})")
    elif verbose:
        print(f"       Iniciando do zero (fold {fold_id} {model_name})")

    for ep in range(start_ep, N_EPOCHS + 1):
        # Treino
        model.train()
        tot, n = 0.0, 0
        for xb, yb in train_loader:
            xb, yb = xb.to(device), yb.to(device)
            optim.zero_grad()
            loss = crit(model(xb), yb)
            loss.backward()
            optim.step()
            tot += loss.item() * xb.size(0)
            n   += xb.size(0)
        tloss = tot / n

        # Validação — loss + f1 em passo único
        model.eval()
        vl, n = 0.0, 0
        preds_chunks = []
        with torch.no_grad():
            for xb, yb in val_loader:
                xb, yb = xb.to(device), yb.to(device)
                logits = model(xb)
                vl += crit(logits, yb).item() * xb.size(0)
                n  += xb.size(0)
                preds_chunks.append(logits.argmax(dim=1).cpu().numpy())
        vloss     = vl / n
        val_preds = np.concatenate(preds_chunks)
        vf1 = float(f1_score(y_val, val_preds, average="macro", zero_division=0))

        history["train_loss"].append(tloss)
        history["val_loss"  ].append(vloss)
        history["val_f1_macro"].append(vf1)

        if _MLFLOW:
            pfx = f"{model_name}_fold{fold_id}_"
            mlflow.log_metric(f"{pfx}train_loss",   tloss, step=ep)
            mlflow.log_metric(f"{pfx}val_loss",     vloss, step=ep)
            mlflow.log_metric(f"{pfx}val_f1_macro", vf1,   step=ep)

        if verbose:
            print(f"       ep {ep:2d}  train={tloss:.4f}  val={vloss:.4f}"
                  f"  val_f1={vf1:.4f}")

        if vloss < best_val - 1e-4:
            best_val   = vloss
            best_state = {k: v.clone().cpu() for k, v in model.state_dict().items()}
            best_epoch = ep
            no_imp     = 0
        else:
            no_imp += 1
            if no_imp >= PATIENCE:
                if verbose:
                    print(f"       early stop @ ep {ep} (best {best_epoch})")
                break

        if ckpt_path:
            torch.save({
                "epoch":          ep,
                "fold":           fold_id,
                "model_state":    model.state_dict(),
                "optimizer_state": optim.state_dict(),
                "best_val_loss":  best_val,
                "best_epoch":     best_epoch,
                "no_imp":         no_imp,
                "rng_state":      torch.get_rng_state(),
                "history":        history,
            }, ckpt_path)

    if best_state is not None:
        model.load_state_dict(best_state)
    model.eval()
    return model, best_epoch, history


def _predict_cnn(model: nn.Module, ds: Dataset, device: str) -> tuple[np.ndarray, np.ndarray]:
    """Retorna (y_pred, y_proba) para todo o dataset."""
    loader = _make_loader(ds, shuffle=False)
    chunks = []
    model.eval()
    with torch.no_grad():
        for xb, _ in loader:
            logits = model(xb.to(device))
            chunks.append(torch.softmax(logits, dim=1).cpu().numpy())
    proba  = np.concatenate(chunks)
    y_pred = proba.argmax(axis=1)
    return y_pred, proba


def _extract_latents(model: nn.Module, ds: Dataset, device: str) -> np.ndarray:
    """Extrai vetor latente (antes do FC) para todo o dataset."""
    loader = _make_loader(ds, shuffle=False)
    chunks = []
    model.eval()
    with torch.no_grad():
        for xb, _ in loader:
            z = model.extract_latent(xb.to(device))
            chunks.append(z.cpu().numpy())
    return np.concatenate(chunks)


# ---------------------------------------------------------------------------
# Classificadores clássicos sobre features latentes
# ---------------------------------------------------------------------------

def _build_classifiers() -> dict:
    s = SEED_MODEL
    return {
        "RF":   RandomForestClassifier(
            n_estimators=RF_N_ESTIMATORS, max_depth=None,
            class_weight="balanced", random_state=s, n_jobs=-1,
        ),
        "LSVC": LinearSVC(
            C=LSVC_C, class_weight="balanced", random_state=s, max_iter=5000,
        ),
    }


def _fit_predict_on_latents(
    Z_train: np.ndarray,
    y_train: np.ndarray,
    Z_val:   np.ndarray,
    y_val:   np.ndarray,
) -> dict[str, dict]:
    """Treina RF e LSVC sobre latents e avalia. Retorna métricas por modelo."""
    scaler  = StandardScaler().fit(Z_train)
    Ztr     = scaler.transform(Z_train)
    Zva     = scaler.transform(Z_val)
    results = {}
    for name, clf in _build_classifiers().items():
        t0 = time.perf_counter()
        clf.fit(Ztr, y_train)
        t_tr   = time.perf_counter() - t0
        y_pred = clf.predict(Zva)
        f1     = float(f1_score(y_val, y_pred, average="macro", zero_division=0))
        bac    = float(balanced_accuracy_score(y_val, y_pred))
        results[name] = {"f1_macro": f1, "balanced_accuracy": bac,
                         "train_time_s": round(t_tr, 2), "_clf": clf, "_scaler": scaler}
    return results


# ---------------------------------------------------------------------------
# Carregar e preparar dados
# ---------------------------------------------------------------------------

def load_data() -> tuple[pd.DataFrame, pd.DataFrame, list[str], dict[str, int]]:
    """
    Carrega raw parquet e divide em trainval (240 chaves) / test (60 chaves).
    Mapeia split antigo (train/val → trainval, test → test).
    """
    print(f"  Carregando {RAW_PARQUET.name}  (memory_map=True)...")
    cols = ["sample_id", "algorithm", "key_id", "ciphertext", "split"]
    df   = pd.read_parquet(RAW_PARQUET, columns=cols, memory_map=True)

    if "split" not in df.columns:
        raise ValueError("Coluna 'split' não encontrada no parquet raw.")

    df["split"] = df["split"].map(
        {"train": "trainval", "val": "trainval", "test": "test"}
    ).fillna(df["split"])

    trainval = df[df["split"] == "trainval"].copy().reset_index(drop=True)
    test     = df[df["split"] == "test"].copy().reset_index(drop=True)

    tv_keys  = set(trainval["key_id"].unique())
    tst_keys = set(test["key_id"].unique())
    overlap  = tv_keys & tst_keys
    if overlap:
        raise ValueError(f"VAZAMENTO: {len(overlap)} chaves em trainval∩test!")

    classes   = sorted(df["algorithm"].unique().tolist())
    label_map = {c: i for i, c in enumerate(classes)}

    print(f"  TrainVal: {len(trainval):,} amostras | {len(tv_keys)} chaves")
    print(f"  Test    : {len(test):,} amostras | {len(tst_keys)} chaves")
    print(f"  Classes : {label_map}")
    return trainval, test, classes, label_map


def _encode(df: pd.DataFrame, label_map: dict) -> np.ndarray:
    return df["algorithm"].map(label_map).to_numpy()


def _make_ds_1d(df: pd.DataFrame, label_map: dict) -> _SeqDataset:
    return _SeqDataset(df["ciphertext"].tolist(), _encode(df, label_map), CNN1D_MAX_LEN)


def _make_ds_2d(df: pd.DataFrame, label_map: dict) -> _CoocDataset:
    return _CoocDataset(df["ciphertext"].tolist(), _encode(df, label_map))


# ---------------------------------------------------------------------------
# CV loop
# ---------------------------------------------------------------------------

def run_cv(
    trainval:  pd.DataFrame,
    classes:   list[str],
    label_map: dict[str, int],
    device:    str,
    mode:      str            = "both",
    resume:    bool           = True,
    ckpt_dir:  Optional[Path] = None,
) -> dict:
    """5-fold GroupKFold CV. Retorna métricas agregadas por modo.

    mode: 'cnn1d' | 'cnn2d' | 'both'
    resume: carrega checkpoints de epoch e folds anteriores se True.
    """
    ckpt_dir = ckpt_dir or CKPT_DIR
    run_1d   = mode in ("cnn1d", "both")
    run_2d   = mode in ("cnn2d", "both")
    modes    = (
        (["cnn1d_direct", "cnn1d_latent_rf", "cnn1d_latent_lsvc"] if run_1d else []) +
        (["cnn2d_direct", "cnn2d_latent_rf", "cnn2d_latent_lsvc"] if run_2d else [])
    )

    gkf    = GroupKFold(n_splits=N_FOLDS)
    groups = trainval["key_id"].to_numpy()
    y_all  = _encode(trainval, label_map)

    fold_results:   list[dict] = []
    best_epochs_1d: list[int]  = []
    best_epochs_2d: list[int]  = []

    # Progresso por fold: permite retomar folds já concluídos
    progress_file   = ckpt_dir / "_cv_progress.pkl"
    completed: dict[int, dict] = {}
    if resume and progress_file.exists():
        with progress_file.open("rb") as f:
            completed = pickle.load(f)
        if completed:
            print(f"  [--resume] {len(completed)}/{N_FOLDS} folds já concluídos")
    else:
        print("  Iniciando do zero" if not resume else "  Sem progresso salvo — iniciando do zero")

    for fold_idx, (tr_idx, val_idx) in enumerate(gkf.split(trainval, y_all, groups)):
        fold_num = fold_idx + 1
        tr_keys  = set(groups[tr_idx])
        val_keys = set(groups[val_idx])
        assert not (tr_keys & val_keys), f"Fold {fold_num}: vazamento de chave!"

        # Fold já concluído — pular treino
        if fold_idx in completed:
            fold_res = completed[fold_idx]
            print(f"\n  [Fold {fold_num}/{N_FOLDS}] Retomando resultados salvos — pulando treino")
            fold_results.append(fold_res)
            if run_1d:
                best_epochs_1d.append(fold_res.get("cnn1d_direct", {}).get("best_epoch", 0))
            if run_2d:
                best_epochs_2d.append(fold_res.get("cnn2d_direct", {}).get("best_epoch", 0))
            continue

        df_tr  = trainval.iloc[tr_idx]
        df_val = trainval.iloc[val_idx]
        y_tr   = y_all[tr_idx]
        y_val  = y_all[val_idx]

        print(f"\n  [Fold {fold_num}/{N_FOLDS}]  "
              f"treino={len(tr_keys)} chaves ({len(tr_idx):,})  "
              f"val={len(val_keys)} chaves ({len(val_idx):,})")

        fold_res: dict = {"fold": fold_num,
                          "n_train_keys": len(tr_keys),
                          "n_val_keys":   len(val_keys)}
        seed_fold = SEED_MODEL + fold_idx * 100

        # ── CNN 1D ──────────────────────────────────────────────────────────
        if run_1d:
            print(f"    [CNN1D]  max_len={CNN1D_MAX_LEN}")
            torch.manual_seed(seed_fold + 1)
            model1d = CiphertextCNN1D(
                n_classes=len(classes), max_len=CNN1D_MAX_LEN,
                n_filters=128, n_conv_blocks=3,
            ).to(device)

            ds_tr1d  = _make_ds_1d(df_tr,  label_map)
            ds_val1d = _make_ds_1d(df_val, label_map)

            t0 = time.perf_counter()
            model1d, best_ep1d, _ = _train_cnn(
                model1d, ds_tr1d, ds_val1d, y_val, device,
                fold_id=fold_idx, model_name="cnn1d",
                ckpt_dir=ckpt_dir, verbose=True,
                seed=seed_fold + 1, resume=resume,
            )
            t_cnn1d = time.perf_counter() - t0
            best_epochs_1d.append(best_ep1d)
            print(f"    CNN1D treinado: best_ep={best_ep1d}  t={t_cnn1d:.1f}s")

            if _MLFLOW:
                mlflow.log_metric(f"cnn1d_fold{fold_num}_best_epoch", best_ep1d)

            y_pred1d, _ = _predict_cnn(model1d, ds_val1d, device)
            f1_1d_dir   = float(f1_score(y_val, y_pred1d, average="macro", zero_division=0))
            bac_1d_dir  = float(balanced_accuracy_score(y_val, y_pred1d))
            print(f"    cnn1d_direct    F1={f1_1d_dir:.4f}  BalAcc={bac_1d_dir:.4f}")

            Z_tr1d    = _extract_latents(model1d, ds_tr1d,  device)
            Z_val1d   = _extract_latents(model1d, ds_val1d, device)
            lat_res1d = _fit_predict_on_latents(Z_tr1d, y_tr, Z_val1d, y_val)
            for name, r in lat_res1d.items():
                print(f"    cnn1d_latent_{name.lower():4s}  F1={r['f1_macro']:.4f}  "
                      f"BalAcc={r['balanced_accuracy']:.4f}  t_clf={r['train_time_s']:.1f}s")

            fold_res["cnn1d_direct"]      = {"f1_macro": f1_1d_dir, "balanced_accuracy": bac_1d_dir,
                                              "train_time_s": round(t_cnn1d, 2), "best_epoch": best_ep1d}
            fold_res["cnn1d_latent_rf"]   = {"f1_macro": lat_res1d["RF"]["f1_macro"],
                                              "balanced_accuracy": lat_res1d["RF"]["balanced_accuracy"]}
            fold_res["cnn1d_latent_lsvc"] = {"f1_macro": lat_res1d["LSVC"]["f1_macro"],
                                              "balanced_accuracy": lat_res1d["LSVC"]["balanced_accuracy"]}

        # ── CNN 2D ──────────────────────────────────────────────────────────
        if run_2d:
            print(f"    [CNN2D]  co-ocorrência 256×256 (CT completo)")
            torch.manual_seed(seed_fold + 2)
            model2d = CiphertextCNN2D(n_classes=len(classes)).to(device)

            ds_tr2d  = _make_ds_2d(df_tr,  label_map)
            ds_val2d = _make_ds_2d(df_val, label_map)

            t0 = time.perf_counter()
            model2d, best_ep2d, _ = _train_cnn(
                model2d, ds_tr2d, ds_val2d, y_val, device,
                fold_id=fold_idx, model_name="cnn2d",
                ckpt_dir=ckpt_dir, verbose=True,
                seed=seed_fold + 2, resume=resume,
            )
            t_cnn2d = time.perf_counter() - t0
            best_epochs_2d.append(best_ep2d)
            print(f"    CNN2D treinado: best_ep={best_ep2d}  t={t_cnn2d:.1f}s")

            if _MLFLOW:
                mlflow.log_metric(f"cnn2d_fold{fold_num}_best_epoch", best_ep2d)

            y_pred2d, _ = _predict_cnn(model2d, ds_val2d, device)
            f1_2d_dir   = float(f1_score(y_val, y_pred2d, average="macro", zero_division=0))
            bac_2d_dir  = float(balanced_accuracy_score(y_val, y_pred2d))
            print(f"    cnn2d_direct    F1={f1_2d_dir:.4f}  BalAcc={bac_2d_dir:.4f}")

            Z_tr2d    = _extract_latents(model2d, ds_tr2d,  device)
            Z_val2d   = _extract_latents(model2d, ds_val2d, device)
            lat_res2d = _fit_predict_on_latents(Z_tr2d, y_tr, Z_val2d, y_val)
            for name, r in lat_res2d.items():
                print(f"    cnn2d_latent_{name.lower():4s}  F1={r['f1_macro']:.4f}  "
                      f"BalAcc={r['balanced_accuracy']:.4f}  t_clf={r['train_time_s']:.1f}s")

            fold_res["cnn2d_direct"]      = {"f1_macro": f1_2d_dir, "balanced_accuracy": bac_2d_dir,
                                              "train_time_s": round(t_cnn2d, 2), "best_epoch": best_ep2d}
            fold_res["cnn2d_latent_rf"]   = {"f1_macro": lat_res2d["RF"]["f1_macro"],
                                              "balanced_accuracy": lat_res2d["RF"]["balanced_accuracy"]}
            fold_res["cnn2d_latent_lsvc"] = {"f1_macro": lat_res2d["LSVC"]["f1_macro"],
                                              "balanced_accuracy": lat_res2d["LSVC"]["balanced_accuracy"]}

        fold_results.append(fold_res)
        completed[fold_idx] = fold_res
        with progress_file.open("wb") as f:
            pickle.dump(completed, f)

    # Resumo CV
    cv_summary: dict = {}
    for m in modes:
        vals = [r[m]["f1_macro"] for r in fold_results]
        bacs = [r[m]["balanced_accuracy"] for r in fold_results]
        cv_summary[m] = {
            "f1_macro_mean": round(float(np.mean(vals)), 4),
            "f1_macro_std":  round(float(np.std(vals, ddof=1)), 4),
            "bal_acc_mean":  round(float(np.mean(bacs)), 4),
            "f1_per_fold":   [round(v, 4) for v in vals],
        }

    if _MLFLOW:
        for m, stats in cv_summary.items():
            mlflow.log_metric(f"cv_{m}_f1_mean", stats["f1_macro_mean"])
            mlflow.log_metric(f"cv_{m}_f1_std",  stats["f1_macro_std"])

    return {
        "n_folds":            N_FOLDS,
        "folds":              fold_results,
        "cv_summary":         cv_summary,
        "mean_best_epoch_1d": math.ceil(float(np.mean(best_epochs_1d))) if best_epochs_1d else 0,
        "mean_best_epoch_2d": math.ceil(float(np.mean(best_epochs_2d))) if best_epochs_2d else 0,
    }


# ---------------------------------------------------------------------------
# Modelo final (trainval → test holdout)
# ---------------------------------------------------------------------------

def _train_fixed_epochs(
    model:      nn.Module,
    train_ds:   Dataset,
    n_epochs:   int,
    model_name: str            = "",
    ckpt_dir:   Optional[Path] = None,
    seed:       int            = SEED_MODEL,
    resume:     bool           = True,
) -> nn.Module:
    """Treina por n_epochs exatos (sem early stopping). Checkpoint por época."""
    torch.manual_seed(seed)
    np.random.seed(seed)
    optim      = torch.optim.Adam(model.parameters(), lr=LR)
    crit       = nn.CrossEntropyLoss()
    loader     = _make_loader(train_ds, shuffle=True)
    start_ep   = 1
    ckpt_path  = (ckpt_dir / f"{model_name}_final.pt") if ckpt_dir else None

    if resume and ckpt_path and ckpt_path.exists():
        ckpt = torch.load(ckpt_path, map_location="cpu")
        model.load_state_dict(ckpt["model_state"])
        optim.load_state_dict(ckpt["optimizer_state"])
        start_ep = ckpt["epoch"] + 1
        torch.set_rng_state(ckpt["rng_state"])
        print(f"    Resumindo checkpoint final {model_name} epoch {ckpt['epoch']}")
    else:
        print(f"    Iniciando do zero (modelo final {model_name})")

    for ep in range(start_ep, n_epochs + 1):
        model.train()
        for xb, yb in loader:
            optim.zero_grad()
            crit(model(xb), yb).backward()
            optim.step()
        if ckpt_path:
            torch.save({
                "epoch":           ep,
                "model_state":     model.state_dict(),
                "optimizer_state": optim.state_dict(),
                "rng_state":       torch.get_rng_state(),
            }, ckpt_path)

    model.eval()
    return model


def run_final(
    trainval:   pd.DataFrame,
    test:       pd.DataFrame,
    classes:    list[str],
    label_map:  dict[str, int],
    mean_ep_1d: int,
    mean_ep_2d: int,
    device:     str,
    mode:       str            = "both",
    resume:     bool           = True,
    ckpt_dir:   Optional[Path] = None,
) -> dict:
    """
    Treina CNNs no trainval completo por mean_best_epoch épocas (sem early stopping),
    extrai latents, treina classifiers — avalia no test holdout com bootstrap.

    mode: 'cnn1d' | 'cnn2d' | 'both'
    """
    ckpt_dir = ckpt_dir or CKPT_DIR
    run_1d   = mode in ("cnn1d", "both")
    run_2d   = mode in ("cnn2d", "both")

    print(f"\n--- Modelo Final: trainval ({len(trainval):,}) → test ({len(test):,}) ---")
    print(f"  Épocas CNN1D={mean_ep_1d}  CNN2D={mean_ep_2d}  (ceil(média best_epoch CV))")

    y_tv   = _encode(trainval, label_map)
    y_tst  = _encode(test,     label_map)
    results: dict = {}

    # ── CNN 1D ──────────────────────────────────────────────────────────────
    if run_1d:
        print(f"\n  CNN1D — treinando {mean_ep_1d} épocas no trainval completo...")
        torch.manual_seed(SEED_MODEL + 1)
        model1d = CiphertextCNN1D(
            n_classes=len(classes), max_len=CNN1D_MAX_LEN,
            n_filters=128, n_conv_blocks=3,
        ).to(device)
        ds_tv1d  = _make_ds_1d(trainval, label_map)
        ds_tst1d = _make_ds_1d(test,     label_map)

        t0 = time.perf_counter()
        model1d = _train_fixed_epochs(model1d, ds_tv1d, mean_ep_1d,
                                      model_name="cnn1d", ckpt_dir=ckpt_dir,
                                      seed=SEED_MODEL + 1, resume=resume)
        t_1d = time.perf_counter() - t0
        print(f"  CNN1D treinado em {t_1d:.1f}s")

        y_pred, y_proba = _predict_cnn(model1d, ds_tst1d, device)
        rep = compute_metrics(y_tst, y_pred, y_proba=y_proba,
                              n_bootstrap=N_BOOTSTRAP, seed=SEED_BOOT)
        results["cnn1d_direct"] = {**rep.as_dict(), "train_time_s": round(t_1d, 2),
                                    "y_pred": y_pred.tolist()}
        ci = rep.f1_macro_ci
        print(f"  cnn1d_direct    F1={rep.f1_macro:.4f}  IC=[{ci[0]:.3f},{ci[1]:.3f}]  "
              f"BalAcc={rep.balanced_accuracy:.4f}")

        Z_tv1d   = _extract_latents(model1d, ds_tv1d,  device)
        Z_tst1d  = _extract_latents(model1d, ds_tst1d, device)
        scaler1d = StandardScaler().fit(Z_tv1d)
        Ztv_sc   = scaler1d.transform(Z_tv1d)
        Ztst_sc  = scaler1d.transform(Z_tst1d)
        for clf_name, clf in _build_classifiers().items():
            t0 = time.perf_counter()
            clf.fit(Ztv_sc, y_tv)
            t_clf       = time.perf_counter() - t0
            y_pred_clf  = clf.predict(Ztst_sc)
            y_proba_clf = clf.predict_proba(Ztst_sc) if hasattr(clf, "predict_proba") else None
            rep_clf = compute_metrics(y_tst, y_pred_clf, y_proba=y_proba_clf,
                                      n_bootstrap=N_BOOTSTRAP, seed=SEED_BOOT)
            mode_key = f"cnn1d_latent_{clf_name.lower()}"
            ci = rep_clf.f1_macro_ci
            print(f"  {mode_key:22s}  F1={rep_clf.f1_macro:.4f}  IC=[{ci[0]:.3f},{ci[1]:.3f}]  "
                  f"t_clf={t_clf:.1f}s")
            results[mode_key] = {**rep_clf.as_dict(),
                                 "train_time_s": round(t_1d + t_clf, 2),
                                 "y_pred": y_pred_clf.tolist()}

    # ── CNN 2D ──────────────────────────────────────────────────────────────
    if run_2d:
        print(f"\n  CNN2D — treinando {mean_ep_2d} épocas no trainval completo...")
        torch.manual_seed(SEED_MODEL + 2)
        model2d  = CiphertextCNN2D(n_classes=len(classes)).to(device)
        ds_tv2d  = _make_ds_2d(trainval, label_map)
        ds_tst2d = _make_ds_2d(test,     label_map)

        t0 = time.perf_counter()
        model2d = _train_fixed_epochs(model2d, ds_tv2d, mean_ep_2d,
                                      model_name="cnn2d", ckpt_dir=ckpt_dir,
                                      seed=SEED_MODEL + 2, resume=resume)
        t_2d = time.perf_counter() - t0
        print(f"  CNN2D treinado em {t_2d:.1f}s")

        y_pred, y_proba = _predict_cnn(model2d, ds_tst2d, device)
        rep = compute_metrics(y_tst, y_pred, y_proba=y_proba,
                              n_bootstrap=N_BOOTSTRAP, seed=SEED_BOOT)
        results["cnn2d_direct"] = {**rep.as_dict(), "train_time_s": round(t_2d, 2),
                                    "y_pred": y_pred.tolist()}
        ci = rep.f1_macro_ci
        print(f"  cnn2d_direct    F1={rep.f1_macro:.4f}  IC=[{ci[0]:.3f},{ci[1]:.3f}]  "
              f"BalAcc={rep.balanced_accuracy:.4f}")

        Z_tv2d   = _extract_latents(model2d, ds_tv2d,  device)
        Z_tst2d  = _extract_latents(model2d, ds_tst2d, device)
        scaler2d = StandardScaler().fit(Z_tv2d)
        Ztv_sc   = scaler2d.transform(Z_tv2d)
        Ztst_sc  = scaler2d.transform(Z_tst2d)
        for clf_name, clf in _build_classifiers().items():
            t0 = time.perf_counter()
            clf.fit(Ztv_sc, y_tv)
            t_clf       = time.perf_counter() - t0
            y_pred_clf  = clf.predict(Ztst_sc)
            y_proba_clf = clf.predict_proba(Ztst_sc) if hasattr(clf, "predict_proba") else None
            rep_clf = compute_metrics(y_tst, y_pred_clf, y_proba=y_proba_clf,
                                      n_bootstrap=N_BOOTSTRAP, seed=SEED_BOOT)
            mode_key = f"cnn2d_latent_{clf_name.lower()}"
            ci = rep_clf.f1_macro_ci
            print(f"  {mode_key:22s}  F1={rep_clf.f1_macro:.4f}  IC=[{ci[0]:.3f},{ci[1]:.3f}]  "
                  f"t_clf={t_clf:.1f}s")
            results[mode_key] = {**rep_clf.as_dict(),
                                 "train_time_s": round(t_2d + t_clf, 2),
                                 "y_pred": y_pred_clf.tolist()}

    return results


# ---------------------------------------------------------------------------
# McNemar entre todos os pares de modos
# ---------------------------------------------------------------------------

def _mcnemar_block(results: dict, y_true: np.ndarray) -> list[dict]:
    """McNemar pareado com correção de continuidade + Bonferroni entre todos os modos."""
    pairs   = list(combinations(results.keys(), 2))
    alpha_b = 0.05 / len(pairs) if pairs else 0.05
    out     = []
    for a, b in pairs:
        ya = np.array(results[a]["y_pred"]) if "y_pred" in results[a] else None
        yb = np.array(results[b]["y_pred"]) if "y_pred" in results[b] else None
        if ya is None or yb is None:
            continue
        res = mcnemar_test(y_true, ya, yb)
        out.append({"pair": f"{a} vs {b}", "bonferroni_alpha": alpha_b,
                    "significant": res["p_value"] < alpha_b, **res})
    return out


# ---------------------------------------------------------------------------
# Tabela Markdown
# ---------------------------------------------------------------------------

def _md_table(rows: list[list[str]], headers: list[str]) -> str:
    widths = [max(len(h), max((len(str(r[i])) for r in rows), default=0))
              for i, h in enumerate(headers)]
    sep  = "| " + " | ".join("-" * w for w in widths) + " |"
    hrow = "| " + " | ".join(h.ljust(w) for h, w in zip(headers, widths)) + " |"
    lines = [hrow, sep]
    for r in rows:
        lines.append("| " + " | ".join(str(c).ljust(w) for c, w in zip(r, widths)) + " |")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="CNN experiments — Ascon vs GIFT-COFB (60k)")
    ap.add_argument("--skip-cv",        action="store_true",
                    help="Reutiliza cache CV existente (ignora --resume para CV)")
    ap.add_argument("--resume",         action="store_true",
                    help="Retoma de checkpoint existente (fold + epoch)")
    ap.add_argument("--checkpoint-dir", type=Path, default=None, metavar="DIR",
                    help="Diretório de checkpoints (default: reports/.../ckpts/)")
    ap.add_argument("--mode",           choices=["cnn1d", "cnn2d", "both"], default="both",
                    help="Qual CNN treinar: cnn1d | cnn2d | both (default)")
    args = ap.parse_args()

    device   = "cuda" if torch.cuda.is_available() else "cpu"
    ckpt_dir = Path(args.checkpoint_dir) if args.checkpoint_dir else CKPT_DIR
    ckpt_dir.mkdir(parents=True, exist_ok=True)

    # Cache separado por modo para evitar conflitos entre runs parciais
    cv_cache    = REPORTS_DIR / f"_cv_cache_{args.mode}.pkl"
    final_cache = REPORTS_DIR / f"_final_cache_{args.mode}.pkl"

    print(f"\n{'='*70}")
    print(f"  Experimento CNN — Ascon vs GIFT-COFB (60k, 64KB CT)")
    print(f"  CNN1D max_len={CNN1D_MAX_LEN}  CNN2D co-ocorrência 256×256")
    print(f"  device={device}  mode={args.mode}  resume={args.resume}")
    print(f"  batch={BATCH_SIZE}  epochs≤{N_EPOCHS}  patience={PATIENCE}")
    print(f"  checkpoint_dir={ckpt_dir.relative_to(REPO_ROOT)}")
    print(f"  MLflow={'ativo' if _MLFLOW else 'nao instalado'}")
    print(f"{'='*70}\n")

    t_total = time.perf_counter()

    _run_ctx = mlflow.start_run(run_name=f"cnn_60k_{args.mode}") if _MLFLOW else _nullctx()
    with _run_ctx:
        if _MLFLOW:
            mlflow.log_params({
                "cnn1d_max_len":    CNN1D_MAX_LEN,
                "cnn2d_repr":       "cooccurrence_256x256",
                "batch_size":       BATCH_SIZE,
                "n_epochs_max":     N_EPOCHS,
                "patience":         PATIENCE,
                "lr":               LR,
                "seed_model":       SEED_MODEL,
                "n_folds":          N_FOLDS,
                "rf_n_estimators":  RF_N_ESTIMATORS,
                "mode":             args.mode,
                "resume":           args.resume,
            })

        trainval, test, classes, label_map = load_data()
        y_tst = _encode(test, label_map)

        # ── CV ──────────────────────────────────────────────────────────────
        if cv_cache.exists() and args.skip_cv:
            print(f"\n  [--skip-cv] Carregando cache CV de {cv_cache.name}")
            with cv_cache.open("rb") as f:
                cv_data = pickle.load(f)
        elif cv_cache.exists() and not args.resume:
            print(f"\n  Cache CV encontrado ({cv_cache.name}). Carregando.")
            with cv_cache.open("rb") as f:
                cv_data = pickle.load(f)
        else:
            print(f"\n--- {N_FOLDS}-fold GroupKFold CV ---")
            cv_data = run_cv(trainval, classes, label_map, device,
                             mode=args.mode, resume=args.resume, ckpt_dir=ckpt_dir)
            with cv_cache.open("wb") as f:
                pickle.dump(cv_data, f)
            print(f"\n  Cache CV salvo em: {cv_cache.name}")

        print(f"\n  CV Summary (mean ± std F1):")
        for m, stats in cv_data["cv_summary"].items():
            folds_str = "  ".join(f"f{i+1}={v:.4f}"
                                  for i, v in enumerate(stats["f1_per_fold"]))
            print(f"    {m:22s}  F1={stats['f1_macro_mean']:.4f}±{stats['f1_macro_std']:.4f}"
                  f"  [{folds_str}]")

        # ── Modelo Final ─────────────────────────────────────────────────────
        if final_cache.exists() and not args.resume:
            print(f"\n  Cache final encontrado ({final_cache.name}). Carregando.")
            with final_cache.open("rb") as f:
                final_results, y_tst_saved = pickle.load(f)
            y_tst = y_tst_saved
        else:
            final_results = run_final(
                trainval, test, classes, label_map,
                mean_ep_1d=cv_data["mean_best_epoch_1d"],
                mean_ep_2d=cv_data["mean_best_epoch_2d"],
                device=device,
                mode=args.mode, resume=args.resume, ckpt_dir=ckpt_dir,
            )
            with final_cache.open("wb") as f:
                pickle.dump((final_results, y_tst), f)
            print(f"  Cache final salvo: {final_cache.name}")

        if _MLFLOW:
            for mode, m in final_results.items():
                mlflow.log_metric(f"test_{mode}_f1",    m["f1_macro"])
                mlflow.log_metric(f"test_{mode}_balacc", m["balanced_accuracy"])

        # ── McNemar ──────────────────────────────────────────────────────────
        mcnemar_rows = _mcnemar_block(final_results, y_tst)

        # ── Tabela comparativa ───────────────────────────────────────────────
        baseline   = 1.0 / len(classes)
        modes_order = [
            "cnn1d_direct", "cnn1d_latent_rf", "cnn1d_latent_lsvc",
            "cnn2d_direct", "cnn2d_latent_rf", "cnn2d_latent_lsvc",
        ]
        tbl_rows: list[list[str]] = []
        for mode in modes_order:
            if mode not in final_results:
                continue
            m    = final_results[mode]
            cv_s = cv_data["cv_summary"].get(mode, {})
            cv_str = (f"{cv_s['f1_macro_mean']:.4f}±{cv_s['f1_macro_std']:.4f}"
                      if cv_s else "—")
            ci_lo = m.get("f1_macro_ci_lower", float("nan"))
            ci_hi = m.get("f1_macro_ci_upper", float("nan"))
            tbl_rows.append([
                mode, cv_str,
                f"{m['f1_macro']:.4f}",
                f"[{ci_lo:.3f},{ci_hi:.3f}]",
                f"{m['balanced_accuracy']:.4f}",
                f"{m.get('train_time_s', 0):.1f}s",
            ])

        headers = ["Modo", "F1 CV (mean±std)", "F1 test", "IC 95%", "BalAcc", "t treino"]
        md_tbl  = _md_table(tbl_rows, headers)

        mcn_rows = [[r["pair"], f"{r['statistic']:.3f}", f"{r['p_value']:.4g}",
                     "sim" if r["significant"] else "nao"]
                    for r in mcnemar_rows]
        alpha_b  = mcnemar_rows[0]["bonferroni_alpha"] if mcnemar_rows else 0.05
        mcn_md   = _md_table(mcn_rows,
                             [f"Comparação (α_bonf={alpha_b:.4f})", "estatística", "p-value", "Sig?"])

        elapsed = time.perf_counter() - t_total

        # ── Salvar outputs ───────────────────────────────────────────────────
        (REPORTS_DIR / "cv_results.json").write_text(
            json.dumps(cv_data, indent=2,
                       default=lambda x: x.tolist() if hasattr(x, "tolist") else str(x)),
            encoding="utf-8",
        )
        (REPORTS_DIR / "final_results.json").write_text(
            json.dumps(
                {**final_results, "y_true": y_tst.tolist(),
                 "mcnemar": mcnemar_rows, "elapsed_s": round(elapsed, 1)},
                indent=2,
                default=lambda x: x.tolist() if hasattr(x, "tolist") else str(x),
            ),
            encoding="utf-8",
        )
        (REPORTS_DIR / "comparison_table.md").write_text(
            f"# CNN — Ascon vs GIFT (60k, CNN1D max_len={CNN1D_MAX_LEN}, CNN2D cooc 256²)\n\n"
            f"Baseline acaso = {baseline:.4f}\n\n{md_tbl}\n",
            encoding="utf-8",
        )
        (REPORTS_DIR / "mcnemar_table.md").write_text(
            f"# McNemar (correção continuidade + Bonferroni)\n\n{mcn_md}\n",
            encoding="utf-8",
        )

        print(f"\n{'='*70}")
        print(f"  RESULTADOS FINAIS — test holdout ({len(y_tst):,} amostras)")
        print(f"  Baseline acaso = {baseline:.4f}")
        print(f"{'='*70}")
        print(md_tbl)
        print(f"\n{mcn_md}")
        print(f"\n  Tempo total: {elapsed:.1f}s")
        print(f"  Relatórios: {REPORTS_DIR.relative_to(REPO_ROOT)}/")


class _nullctx:
    """Context manager noop — usado quando MLflow não está disponível."""
    def __enter__(self):  return self
    def __exit__(self, *_): pass


if __name__ == "__main__":
    main()
