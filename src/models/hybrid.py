"""
Caminho D — Modelo Híbrido.

Combina features clássicas (307D) com vetores latentes de CNN 1D e CNN 2D:
    [307D clássicas | latent CNN1D (512D) | latent CNN2D (128D)] → 947D

Representações:
  CNN1D : primeiros CNN1D_MAX_LEN bytes do CT como sequência de tokens
  CNN2D : mapa de co-ocorrência de bigramas 256×256 (CT completo, sem truncamento)

Infraestrutura:
  - Datasets lazy (bytes → tensor no __getitem__)
  - Checkpoint por epoch (resiliente a preempção em instâncias spot)
  - Resume automático a partir do último checkpoint
  - MLflow logging (train_loss, val_loss, val_f1_macro por epoch)
  - num_workers=4, persistent_workers=True, worker_init_fn para seed
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import f1_score
from torch.utils.data import DataLoader, Dataset

from src.models.ciphertext_to_image import bytes_to_cooccurrence
from src.models.cnn1d import CiphertextCNN1D
from src.models.cnn2d import CiphertextCNN2D

# ---------------------------------------------------------------------------
# MLflow opcional
# ---------------------------------------------------------------------------
try:
    import mlflow
    _MLFLOW_AVAILABLE = True
except ImportError:
    _MLFLOW_AVAILABLE = False


def _mlflow_log(key: str, value: float, step: Optional[int] = None) -> None:
    if not _MLFLOW_AVAILABLE:
        return
    try:
        if step is not None:
            mlflow.log_metric(key, value, step=step)
        else:
            mlflow.log_metric(key, value)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# DataLoader helpers
# ---------------------------------------------------------------------------

_NUM_WORKERS       = 4
_PERSISTENT        = True
_BATCH_SIZE        = 64


def _worker_init_fn(worker_id: int) -> None:
    np.random.seed(torch.initial_seed() % 2**32)


def _loader(ds: Dataset, shuffle: bool, batch_size: int = _BATCH_SIZE) -> DataLoader:
    return DataLoader(
        ds,
        batch_size          = batch_size,
        shuffle             = shuffle,
        num_workers         = _NUM_WORKERS,
        persistent_workers  = _PERSISTENT if _NUM_WORKERS > 0 else False,
        worker_init_fn      = _worker_init_fn,
    )


# ---------------------------------------------------------------------------
# Datasets lazy
# ---------------------------------------------------------------------------

class CiphertextSeqDataset(Dataset):
    """CT bytes → int64 tensor (max_len,). Conversão on-demand."""

    def __init__(self, cts: list, labels: np.ndarray, max_len: int) -> None:
        self.cts     = cts
        self.labels  = torch.from_numpy(np.asarray(labels, dtype=np.int64))
        self.max_len = max_len

    def __len__(self) -> int:
        return len(self.cts)

    def __getitem__(self, idx: int):
        arr = np.frombuffer(bytes(self.cts[idx]), dtype=np.uint8)
        if arr.size >= self.max_len:
            arr = arr[: self.max_len]
        else:
            arr = np.concatenate([arr, np.zeros(self.max_len - arr.size, dtype=np.uint8)])
        return torch.from_numpy(arr.astype(np.int64)), self.labels[idx]


class CiphertextCoocDataset(Dataset):
    """CT bytes → mapa de co-ocorrência float32 (1, 256, 256). CT completo."""

    def __init__(self, cts: list, labels: np.ndarray) -> None:
        self.cts    = cts
        self.labels = torch.from_numpy(np.asarray(labels, dtype=np.int64))

    def __len__(self) -> int:
        return len(self.cts)

    def __getitem__(self, idx: int):
        img = bytes_to_cooccurrence(bytes(self.cts[idx]))     # (256, 256) float32
        return torch.from_numpy(img[np.newaxis, :, :]), self.labels[idx]


# ---------------------------------------------------------------------------
# Checkpoint helpers
# ---------------------------------------------------------------------------

def _ckpt_path(ckpt_dir: Optional[Path], fold_id: int, cnn_id: str) -> Optional[Path]:
    if ckpt_dir is None:
        return None
    return ckpt_dir / f"ckpt_fold{fold_id:02d}_{cnn_id}_latest.pt"


def _save_ckpt(
    path:       Path,
    epoch:      int,
    fold_id:    int,
    model:      nn.Module,
    optimizer:  torch.optim.Optimizer,
    best_val:   float,
    best_epoch: int,
) -> None:
    torch.save({
        "epoch":          epoch,
        "fold":           fold_id,
        "model_state":    model.state_dict(),
        "optimizer_state": optimizer.state_dict(),
        "best_val_loss":  best_val,
        "best_epoch":     best_epoch,
        "rng_state":      torch.get_rng_state(),
    }, path)


def _load_ckpt(
    path:      Path,
    model:     nn.Module,
    optimizer: torch.optim.Optimizer,
    device:    str,
) -> tuple[int, float, int]:
    """Carrega checkpoint. Retorna (start_epoch, best_val, best_epoch)."""
    ckpt = torch.load(path, map_location=device)
    model.load_state_dict(ckpt["model_state"])
    optimizer.load_state_dict(ckpt["optimizer_state"])
    torch.set_rng_state(ckpt["rng_state"])
    return ckpt["epoch"] + 1, ckpt["best_val_loss"], ckpt["best_epoch"]


# ---------------------------------------------------------------------------
# Treino CNN
# ---------------------------------------------------------------------------

def train_cnn(
    model:      nn.Module,
    train_ds:   Dataset,
    val_ds:     Dataset,
    device:     str,
    lr:         float = 1e-3,
    n_epochs:   int   = 30,
    patience:   int   = 5,
    seed:       int   = 7,
    verbose:    bool  = False,
    fold_id:    int   = 0,
    cnn_id:     str   = "cnn",
    ckpt_dir:   Optional[Path] = None,
    mlflow_prefix: str = "",
    resume:     bool  = True,
    batch_size: int   = _BATCH_SIZE,
) -> tuple[nn.Module, int]:
    """
    Treina CNN com early stopping no val_loss.

    Checkpoint salvo após cada epoch em ckpt_dir (se fornecido).
    Resume a partir do checkpoint se resume=True e checkpoint existir.

    Returns:
        (model com melhor estado, best_epoch)
    """
    torch.manual_seed(seed)
    optim = torch.optim.Adam(model.parameters(), lr=lr)
    crit  = nn.CrossEntropyLoss()
    best_val, best_state, best_ep, no_imp = float("inf"), None, 0, 0
    start_ep = 1

    ckpt = _ckpt_path(ckpt_dir, fold_id, cnn_id)
    if resume and ckpt and ckpt.exists():
        start_ep, best_val, best_ep = _load_ckpt(ckpt, model, optim, device)
        no_imp = 0
        print(f"  Resumindo do fold {fold_id} {cnn_id} epoch {start_ep - 1}")
    elif verbose:
        print(f"  Iniciando do zero (fold {fold_id} {cnn_id})")

    train_loader = _loader(train_ds, shuffle=True,  batch_size=batch_size)
    val_loader   = _loader(val_ds,   shuffle=False, batch_size=batch_size)

    for ep in range(start_ep, n_epochs + 1):
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

        # Validação
        model.eval()
        vl, vn = 0.0, 0
        val_preds, val_targets = [], []
        with torch.no_grad():
            for xb, yb in val_loader:
                xb, yb = xb.to(device), yb.to(device)
                logits  = model(xb)
                vl     += crit(logits, yb).item() * xb.size(0)
                vn     += xb.size(0)
                val_preds.extend(logits.argmax(1).cpu().numpy())
                val_targets.extend(yb.cpu().numpy())
        vloss = vl / vn
        vf1   = float(f1_score(val_targets, val_preds, average="macro", zero_division=0))

        # MLflow
        prefix = f"{mlflow_prefix}_" if mlflow_prefix else ""
        _mlflow_log(f"{prefix}train_loss", tloss, step=ep)
        _mlflow_log(f"{prefix}val_loss",   vloss, step=ep)
        _mlflow_log(f"{prefix}val_f1_macro", vf1, step=ep)

        if verbose:
            print(f"    ep {ep:2d}  train={tloss:.4f}  val={vloss:.4f}  f1={vf1:.4f}")

        # Checkpoint por epoch
        if ckpt:
            ckpt_dir.mkdir(parents=True, exist_ok=True)
            _save_ckpt(ckpt, ep, fold_id, model, optim, best_val, best_ep)

        # Early stopping
        if vloss < best_val - 1e-4:
            best_val   = vloss
            best_state = {k: v.clone().cpu() for k, v in model.state_dict().items()}
            best_ep    = ep
            no_imp     = 0
        else:
            no_imp += 1
            if no_imp >= patience:
                if verbose:
                    print(f"    early stop @ ep {ep} (best {best_ep})")
                break

    if best_state is not None:
        model.load_state_dict(best_state)
    model.eval()

    # Remover checkpoint do fold ao concluir (fold completo)
    if ckpt and ckpt.exists():
        ckpt.unlink(missing_ok=True)

    return model, best_ep


def train_cnn_fixed(
    model:    nn.Module,
    train_ds: Dataset,
    n_epochs: int,
    device:   str,
    lr:       float = 1e-3,
    seed:     int   = 7,
    fold_id:  int   = 0,
    cnn_id:   str   = "final",
    ckpt_dir: Optional[Path] = None,
    mlflow_prefix: str = "",
    resume:   bool  = True,
    batch_size: int = _BATCH_SIZE,
) -> nn.Module:
    """Treina por n_epochs fixo sem early stopping (modelo final)."""
    torch.manual_seed(seed)
    optim  = torch.optim.Adam(model.parameters(), lr=lr)
    crit   = nn.CrossEntropyLoss()
    loader = _loader(train_ds, shuffle=True, batch_size=batch_size)
    ckpt   = _ckpt_path(ckpt_dir, fold_id, cnn_id)
    start_ep = 1

    if resume and ckpt and ckpt.exists():
        start_ep, _, _ = _load_ckpt(ckpt, model, optim, device)
        print(f"  Resumindo checkpoint final {cnn_id} epoch {start_ep - 1}")
    else:
        print(f"  Iniciando do zero (modelo final {cnn_id})")

    for ep in range(start_ep, n_epochs + 1):
        model.train()
        tot, n = 0.0, 0
        for xb, yb in loader:
            xb, yb = xb.to(device), yb.to(device)
            optim.zero_grad()
            loss = crit(model(xb), yb)
            loss.backward()
            optim.step()
            tot += loss.item() * xb.size(0)
            n   += xb.size(0)
        _mlflow_log(f"{mlflow_prefix}_train_loss" if mlflow_prefix else "train_loss",
                    tot / n, step=ep)
        if ckpt:
            ckpt_dir.mkdir(parents=True, exist_ok=True)
            _save_ckpt(ckpt, ep, fold_id, model, optim, float("inf"), 0)

    if ckpt and ckpt.exists():
        ckpt.unlink(missing_ok=True)

    model.eval()
    return model


# ---------------------------------------------------------------------------
# Extração de latents
# ---------------------------------------------------------------------------

def extract_latents(
    model:  nn.Module,
    cts:    list,
    max_len_or_size: int,
    mode:   str,
    device: str,
    batch_size: int = _BATCH_SIZE,
) -> np.ndarray:
    """
    Extrai vetores latentes (antes do FC) para uma lista de ciphertexts.

    Args:
        mode: '1d' → CiphertextSeqDataset com max_len
              '2d' → CiphertextCoocDataset (co-occurrence, CT completo)
              O parâmetro max_len_or_size é usado apenas no modo '1d'.
    Returns:
        (n, latent_dim) float32.
    """
    dummy = np.zeros(len(cts), dtype=np.int64)
    ds = (CiphertextSeqDataset(cts, dummy, max_len_or_size)
          if mode == "1d" else CiphertextCoocDataset(cts, dummy))

    chunks: list[np.ndarray] = []
    model.eval()
    with torch.no_grad():
        for xb, _ in _loader(ds, shuffle=False, batch_size=batch_size):
            chunks.append(model.extract_latent(xb.to(device)).cpu().numpy())
    return np.concatenate(chunks)


# ---------------------------------------------------------------------------
# Constantes de comprimento (exportadas para uso nos scripts)
# ---------------------------------------------------------------------------

# Caminho B usa prefixo por viabilidade em CPU.
# Caminho D usa CT completo para simetria com CNN2D e features clássicas.
# Assimetria INTENCIONAL — documentada na dissertação (Seção Metodologia).
MAX_LEN_B       = 4096   # CNN1D Caminho B — prefixo; viável em CPU
MAX_LEN_D_CNN1D = 65552  # CNN1D Caminho D — CT completo; requer GPU


# ---------------------------------------------------------------------------
# Configuração do Híbrido
# ---------------------------------------------------------------------------

@dataclass
class HybridConfig:
    """Parâmetros das CNNs e treino para o Caminho D."""
    max_len_1d:    int   = MAX_LEN_B   # scripts de produção sobrescrevem com MAX_LEN_D_CNN1D
    n_classes:     int   = 2
    n_filters_1d:  int   = 128     # latent_dim = 128 × 2² = 512 (3 blocos)
    n_conv_1d:     int   = 3
    lr:            float = 1e-3
    n_epochs:      int   = 30
    patience:      int   = 5
    seed_model:    int   = 7
    device:        Optional[str]  = None
    ckpt_dir:      Optional[Path] = None
    # Batch sizes separados por CNN. CNN1D sobre CT longo (>= 16384 bytes) precisa
    # de batch pequeno para caber na VRAM; CNN2D (co-ocorrência 256x256) e os
    # classificadores clássicos mantêm o batch padrão. None => derivado de max_len_1d.
    batch_size_1d: Optional[int]  = None
    batch_size_2d: int            = _BATCH_SIZE

    def __post_init__(self) -> None:
        if self.device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        if self.batch_size_1d is None:
            self.batch_size_1d = 8 if self.max_len_1d >= 16384 else _BATCH_SIZE


# ---------------------------------------------------------------------------
# HybridExtractor
# ---------------------------------------------------------------------------

class HybridExtractor:
    """
    Treina CNN 1D (sequência truncada) e CNN 2D (mapa de co-ocorrência)
    em dados de treino de um fold e combina os latents com features clássicas.

    CNN1D usa os primeiros max_len_1d bytes do CT.
    CNN2D usa o CT completo como mapa de co-ocorrência 256×256.

    Fluxo típico dentro de um fold de CV:
        ext = HybridExtractor(cfg)
        ext.fit(cts_train, y_train, cts_val, y_val, fold_id=fold_id)
        X_train = ext.transform(feat_train, cts_train)
        X_val   = ext.transform(feat_val,   cts_val)
    """

    def __init__(self, cfg: HybridConfig) -> None:
        self.cfg     = cfg
        self.model1d: Optional[CiphertextCNN1D] = None
        self.model2d: Optional[CiphertextCNN2D] = None
        self.best_epoch_1d: int = 0
        self.best_epoch_2d: int = 0

    def fit(
        self,
        cts_train: list,
        y_train:   np.ndarray,
        cts_val:   list,
        y_val:     np.ndarray,
        fold_id:   int            = 0,
        verbose:   bool           = False,
        resume:    bool           = True,
        ckpt_dir:  Optional[Path] = None,
    ) -> "HybridExtractor":
        """Treina CNN1D e CNN2D com early stopping.

        resume=True carrega checkpoint de ckpt_dir (ou cfg.ckpt_dir) se existir.
        ckpt_dir sobrescreve cfg.ckpt_dir quando fornecido.
        """
        cfg      = self.cfg
        dev      = cfg.device
        ckpt_dir = ckpt_dir if ckpt_dir is not None else cfg.ckpt_dir
        seed_fold = cfg.seed_model + fold_id * 100
        seed_1d   = seed_fold + 1
        seed_2d   = seed_fold + 2

        if verbose:
            print(f"    [CNN1D] max_len={cfg.max_len_1d}")
        torch.manual_seed(seed_1d)
        self.model1d = CiphertextCNN1D(
            n_classes     = cfg.n_classes,
            max_len       = cfg.max_len_1d,
            n_filters     = cfg.n_filters_1d,
            n_conv_blocks = cfg.n_conv_1d,
        ).to(dev)
        t0 = time.perf_counter()
        self.model1d, self.best_epoch_1d = train_cnn(
            model         = self.model1d,
            train_ds      = CiphertextSeqDataset(cts_train, y_train, cfg.max_len_1d),
            val_ds        = CiphertextSeqDataset(cts_val,   y_val,   cfg.max_len_1d),
            device        = dev,
            lr            = cfg.lr,
            n_epochs      = cfg.n_epochs,
            patience      = cfg.patience,
            seed          = seed_1d,
            verbose       = verbose,
            fold_id       = fold_id,
            cnn_id        = "1d",
            ckpt_dir      = ckpt_dir,
            mlflow_prefix = f"fold{fold_id:02d}_1d",
            resume        = resume,
            batch_size    = cfg.batch_size_1d,
        )
        if verbose:
            print(f"    CNN1D ok: best_ep={self.best_epoch_1d}  t={time.perf_counter()-t0:.1f}s")
        _mlflow_log(f"fold{fold_id:02d}_1d_best_epoch", self.best_epoch_1d)

        if verbose:
            print(f"    [CNN2D] co-occurrence 256×256 (CT completo)")
        torch.manual_seed(seed_2d)
        self.model2d = CiphertextCNN2D(n_classes=cfg.n_classes).to(dev)
        t0 = time.perf_counter()
        self.model2d, self.best_epoch_2d = train_cnn(
            model         = self.model2d,
            train_ds      = CiphertextCoocDataset(cts_train, y_train),
            val_ds        = CiphertextCoocDataset(cts_val,   y_val),
            device        = dev,
            lr            = cfg.lr,
            n_epochs      = cfg.n_epochs,
            patience      = cfg.patience,
            seed          = seed_2d,
            verbose       = verbose,
            fold_id       = fold_id,
            cnn_id        = "2d",
            ckpt_dir      = ckpt_dir,
            mlflow_prefix = f"fold{fold_id:02d}_2d",
            resume        = resume,
            batch_size    = cfg.batch_size_2d,
        )
        if verbose:
            print(f"    CNN2D ok: best_ep={self.best_epoch_2d}  t={time.perf_counter()-t0:.1f}s")
        _mlflow_log(f"fold{fold_id:02d}_2d_best_epoch", self.best_epoch_2d)

        return self

    def fit_fixed(
        self,
        cts_train:   list,
        y_train:     np.ndarray,
        n_epochs_1d: int,
        n_epochs_2d: int,
        verbose:     bool           = False,
        resume:      bool           = True,
        ckpt_dir:    Optional[Path] = None,
    ) -> "HybridExtractor":
        """Treina CNNs por épocas fixas (modelo final — sem early stopping).

        resume=True carrega checkpoint de ckpt_dir (ou cfg.ckpt_dir) se existir.
        """
        cfg      = self.cfg
        dev      = cfg.device
        ckpt_dir = ckpt_dir if ckpt_dir is not None else cfg.ckpt_dir
        seed_1d  = cfg.seed_model + 1
        seed_2d  = cfg.seed_model + 2

        torch.manual_seed(seed_1d)
        self.model1d = CiphertextCNN1D(
            n_classes     = cfg.n_classes,
            max_len       = cfg.max_len_1d,
            n_filters     = cfg.n_filters_1d,
            n_conv_blocks = cfg.n_conv_1d,
        ).to(dev)
        t0 = time.perf_counter()
        self.model1d = train_cnn_fixed(
            model         = self.model1d,
            train_ds      = CiphertextSeqDataset(cts_train, y_train, cfg.max_len_1d),
            n_epochs      = n_epochs_1d,
            device        = dev,
            lr            = cfg.lr,
            seed          = seed_1d,
            cnn_id        = "final_1d",
            ckpt_dir      = ckpt_dir,
            mlflow_prefix = "final_1d",
            resume        = resume,
            batch_size    = cfg.batch_size_1d,
        )
        if verbose:
            print(f"    CNN1D: {n_epochs_1d} épocas  t={time.perf_counter()-t0:.1f}s")

        torch.manual_seed(seed_2d)
        self.model2d = CiphertextCNN2D(n_classes=cfg.n_classes).to(dev)
        t0 = time.perf_counter()
        self.model2d = train_cnn_fixed(
            model         = self.model2d,
            train_ds      = CiphertextCoocDataset(cts_train, y_train),
            n_epochs      = n_epochs_2d,
            device        = dev,
            lr            = cfg.lr,
            seed          = seed_2d,
            cnn_id        = "final_2d",
            ckpt_dir      = ckpt_dir,
            mlflow_prefix = "final_2d",
            resume        = resume,
            batch_size    = cfg.batch_size_2d,
        )
        if verbose:
            print(f"    CNN2D: {n_epochs_2d} épocas  t={time.perf_counter()-t0:.1f}s")

        return self

    def transform(self, feat_matrix: np.ndarray, cts: list) -> np.ndarray:
        """
        Combina features clássicas com latents das CNNs.

        Args:
            feat_matrix: (n, 307) features clássicas pré-computadas.
            cts:         lista de ciphertexts (bytes).
        Returns:
            (n, 307 + latent1d_dim + latent2d_dim) float64.
        """
        if self.model1d is None or self.model2d is None:
            raise RuntimeError("Chame fit() ou fit_fixed() antes de transform().")
        cfg = self.cfg
        z1d = extract_latents(self.model1d, cts, cfg.max_len_1d, "1d", cfg.device,
                              batch_size=cfg.batch_size_1d)
        z2d = extract_latents(self.model2d, cts, 0,              "2d", cfg.device,
                              batch_size=cfg.batch_size_2d)
        return np.concatenate(
            [feat_matrix.astype(np.float64),
             z1d.astype(np.float64),
             z2d.astype(np.float64)],
            axis=1,
        )

    @property
    def combined_dim(self) -> int:
        d1 = self.model1d.latent_dim if self.model1d else 0
        d2 = self.model2d.latent_dim if self.model2d else 0
        return 307 + d1 + d2
