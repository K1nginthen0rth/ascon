"""
Loop de treinamento + avaliação para CiphertextCNN1D.

Padrões:
  - Optimizer: Adam (lr=1e-3 default)
  - Loss: CrossEntropyLoss
  - Early stopping no val_loss com patience configurável
  - Pad com 0 (ou truncate) para max_len fixo
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

from src.eval.metrics import compute_metrics, MetricsReport
from src.models.cnn1d import CiphertextCNN1D


@dataclass
class CNN1DResult:
    metrics:        MetricsReport
    train_time_s:   float
    predict_time_s: float
    y_pred:         np.ndarray
    y_proba:        np.ndarray
    best_epoch:     int
    history:        dict


def _bytes_to_tensor(ct: bytes, max_len: int) -> np.ndarray:
    """Converte bytes para array (max_len,) com pad-zero ou truncate."""
    arr = np.frombuffer(ct, dtype=np.uint8)
    if len(arr) >= max_len:
        return arr[:max_len].astype(np.int64)
    out = np.zeros(max_len, dtype=np.int64)
    out[: len(arr)] = arr
    return out


class CNN1DTrainer:
    """
    Treina CiphertextCNN1D no dataset key-holdout 2-classes.

    Args:
        max_len:    comprimento fixo da sequência (default 1040 = 1024 + 16).
        batch_size: tamanho do batch (default 32).
        n_epochs:   máximo de épocas (default 30).
        lr:         learning rate Adam (default 1e-3).
        patience:   early stopping no val_loss (default 5).
        device:     'cpu' ou 'cuda'. Default: detecta automaticamente.
        seed:       semente para reprodutibilidade.
    """

    def __init__(
        self,
        max_len:     int   = 1040,
        batch_size:  int   = 32,
        n_epochs:    int   = 30,
        lr:          float = 1e-3,
        patience:    int   = 5,
        device:      Optional[str] = None,
        seed:        int   = 7,
        n_bootstrap: int   = 1000,
        seed_bootstrap: int = 42,
    ) -> None:
        self.max_len     = max_len
        self.batch_size  = batch_size
        self.n_epochs    = n_epochs
        self.lr          = lr
        self.patience    = patience
        self.device      = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.seed        = seed
        self.n_bootstrap = n_bootstrap
        self.seed_bootstrap = seed_bootstrap

    # ------------------------------------------------------------------

    def prepare_split(
        self,
        raw_df: pd.DataFrame,
        split:  str,
    ) -> tuple[torch.Tensor, torch.Tensor, dict]:
        """
        Prepara X (int), y (int) para um split específico.

        Args:
            raw_df: DataFrame com colunas 'split', 'algorithm', 'ciphertext'.
            split:  um de {'train', 'val', 'test'}.
        """
        sub = raw_df[raw_df["split"] == split]
        if len(sub) == 0:
            raise ValueError(f"Split '{split}' vazio.")

        classes   = sorted(raw_df["algorithm"].unique().tolist())
        label_map = {c: i for i, c in enumerate(classes)}

        X_arr = np.stack([
            _bytes_to_tensor(bytes(ct), self.max_len)
            for ct in sub["ciphertext"]
        ])
        y_arr = sub["algorithm"].map(label_map).to_numpy()

        return (
            torch.from_numpy(X_arr),
            torch.from_numpy(y_arr).long(),
            label_map,
        )

    def train(
        self,
        raw_df:  pd.DataFrame,
        verbose: bool = True,
    ) -> CNN1DResult:
        """Treina e avalia o CNN no split key-holdout."""
        torch.manual_seed(self.seed)
        np.random.seed(self.seed)

        X_train, y_train, label_map = self.prepare_split(raw_df, "train")
        X_val,   y_val,   _         = self.prepare_split(raw_df, "val")
        X_test,  y_test,  _         = self.prepare_split(raw_df, "test")
        if verbose:
            print(f"  CNN device:  {self.device}")
            print(f"  Train: {X_train.shape}, Val: {X_val.shape}, Test: {X_test.shape}")
            print(f"  Classes: {label_map}")

        n_classes = len(label_map)
        model = CiphertextCNN1D(n_classes=n_classes, max_len=self.max_len).to(self.device)
        optim = torch.optim.Adam(model.parameters(), lr=self.lr)
        crit  = nn.CrossEntropyLoss()

        train_loader = DataLoader(TensorDataset(X_train, y_train),
                                  batch_size=self.batch_size, shuffle=True)
        val_loader   = DataLoader(TensorDataset(X_val,   y_val),
                                  batch_size=self.batch_size, shuffle=False)

        history = {"train_loss": [], "val_loss": [], "val_acc": []}
        best_val      = float("inf")
        best_state    = None
        best_epoch    = 0
        epochs_no_imp = 0

        t0 = time.perf_counter()
        for ep in range(1, self.n_epochs + 1):
            # --- treino ---
            model.train()
            tot_loss, n_seen = 0.0, 0
            for xb, yb in train_loader:
                xb, yb = xb.to(self.device), yb.to(self.device)
                optim.zero_grad()
                logits = model(xb)
                loss   = crit(logits, yb)
                loss.backward()
                optim.step()
                tot_loss += loss.item() * xb.size(0)
                n_seen   += xb.size(0)
            train_loss = tot_loss / n_seen

            # --- validação ---
            model.eval()
            val_loss, val_correct, val_n = 0.0, 0, 0
            with torch.no_grad():
                for xb, yb in val_loader:
                    xb, yb = xb.to(self.device), yb.to(self.device)
                    logits = model(xb)
                    val_loss += crit(logits, yb).item() * xb.size(0)
                    val_correct += (logits.argmax(1) == yb).sum().item()
                    val_n += xb.size(0)
            val_loss /= val_n
            val_acc   = val_correct / val_n
            history["train_loss"].append(train_loss)
            history["val_loss"  ].append(val_loss)
            history["val_acc"   ].append(val_acc)
            if verbose:
                print(f"     ep {ep:2d}  train_loss={train_loss:.4f}  "
                      f"val_loss={val_loss:.4f}  val_acc={val_acc:.4f}")

            if val_loss < best_val - 1e-4:
                best_val      = val_loss
                best_state    = {k: v.clone().cpu() for k, v in model.state_dict().items()}
                best_epoch    = ep
                epochs_no_imp = 0
            else:
                epochs_no_imp += 1
                if epochs_no_imp >= self.patience:
                    if verbose:
                        print(f"     Early stop @ ep {ep} (best ep {best_epoch})")
                    break

        train_time = time.perf_counter() - t0

        # --- restaura melhor modelo e prediz no test ---
        if best_state is not None:
            model.load_state_dict(best_state)
        model.eval()

        t1 = time.perf_counter()
        proba_chunks = []
        with torch.no_grad():
            for start in range(0, len(X_test), self.batch_size):
                xb = X_test[start : start + self.batch_size].to(self.device)
                logits = model(xb)
                proba_chunks.append(torch.softmax(logits, dim=1).cpu().numpy())
        proba  = np.concatenate(proba_chunks, axis=0)
        y_pred = proba.argmax(axis=1)
        predict_time = time.perf_counter() - t1

        rep = compute_metrics(
            y_test.numpy(), y_pred, y_proba=proba,
            n_bootstrap=self.n_bootstrap, seed=self.seed_bootstrap,
        )
        return CNN1DResult(
            metrics=rep,
            train_time_s=train_time,
            predict_time_s=predict_time,
            y_pred=y_pred,
            y_proba=proba,
            best_epoch=best_epoch,
            history=history,
        )
