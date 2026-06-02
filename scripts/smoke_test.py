"""
smoke_test.py — Valida Caminhos B, C e D em modo reduzido.

500 amostras · 2 folds · 3 épocas · target < 10 min em CPU.
num_workers=0 evita overhead de spawn de processos no Windows.
Usa o parquet canônico keyholdout_2class_60k_v1 com subsample.

Uso:
    python scripts/smoke_test.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src" / "crypto"))

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import f1_score
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler
from torch.utils.data import DataLoader, Dataset

from src.models.cnn1d import CiphertextCNN1D
from src.models.cnn2d import CiphertextCNN2D
from src.models.ciphertext_to_image import bytes_to_cooccurrence
from src.features.selector import LWCFeatureSelector, SelectorConfig

try:
    import mlflow
    _MLFLOW = True
except ImportError:
    _MLFLOW = False

try:
    import psutil
    _PSUTIL = True
except ImportError:
    _PSUTIL = False

# ─── Parâmetros smoke ────────────────────────────────────────────────────────
N_PER_CLASS  = 250          # 500 amostras total
N_FOLDS      = 2
N_EPOCHS     = 3
# Caminho B usa prefixo por viabilidade em CPU.
# Caminho D usa CT completo em produção (GPU). Smoke test força MAX_LEN_B.
# Assimetria INTENCIONAL — documentada na dissertação (Seção Metodologia).
MAX_LEN_B       = 4096    # CNN1D Caminho B — prefixo; smoke test SEMPRE usa isto
MAX_LEN_D_CNN1D = 65552   # CNN1D Caminho D — CT completo; smoke test NUNCA usa
CNN1D_NFILT  = 64           # filtros reduzidos para CPU
CNN1D_NCONV  = 2            # blocos conv reduzidos
BATCH        = 32
SEED         = 42
SEED_MODEL   = 7

DATASET_ID   = "keyholdout_2class_60k_v1"
DATA_DIR     = REPO_ROOT / "data" / "processed"
RAW_PQ       = DATA_DIR / f"{DATASET_ID}.parquet"
FEAT_PQ      = DATA_DIR / f"{DATASET_ID}_features.parquet"
OUT_DIR      = REPO_ROOT / "reports" / "smoke_test"
CKPT_DIR     = OUT_DIR / "ckpts"
OUT_DIR.mkdir(parents=True, exist_ok=True)
CKPT_DIR.mkdir(parents=True, exist_ok=True)

_NON_FEAT = {
    "sample_id", "algorithm", "key_id", "nonce_id", "split",
    "len_pt", "len_ad", "len_ct", "mode", "impl", "plaintext_source",
    "seed", "version", "timestamp", "ciphertext",
}

SELECTOR_CFG = SelectorConfig(
    variance_threshold  = 1e-5,
    top_k_mi            = 50,
    n_features_mrmr     = 30,
    boruta_max_iter     = 10,   # reduzido para smoke test
    random_state        = 13,
    verbose             = 0,
)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _ram_mb() -> float:
    return psutil.Process().memory_info().rss / 1024 ** 2 if _PSUTIL else 0.0


def _feat_cols(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns
            if c not in _NON_FEAT and df[c].dtype.kind in ("f", "i", "u")]


# ─── Datasets lazy (num_workers=0 — sem spawn de processo) ───────────────────

class _SeqDS(Dataset):
    """CT bytes → int64 tensor truncado a MAX_LEN_B."""

    def __init__(self, cts: list, labels: np.ndarray) -> None:
        self.cts = cts
        self.y   = torch.from_numpy(np.asarray(labels, np.int64))

    def __len__(self) -> int:
        return len(self.cts)

    def __getitem__(self, i: int):
        a = np.frombuffer(bytes(self.cts[i]), dtype=np.uint8)
        if a.size >= MAX_LEN_B:
            a = a[:MAX_LEN_B]
        else:
            a = np.concatenate([a, np.zeros(MAX_LEN_B - a.size, np.uint8)])
        return torch.from_numpy(a.astype(np.int64)), self.y[i]


class _CoocDS(Dataset):
    """CT bytes → mapa de co-ocorrência (1, 256, 256) float32 — CT completo."""

    def __init__(self, cts: list, labels: np.ndarray) -> None:
        self.cts = cts
        self.y   = torch.from_numpy(np.asarray(labels, np.int64))

    def __len__(self) -> int:
        return len(self.cts)

    def __getitem__(self, i: int):
        m = bytes_to_cooccurrence(bytes(self.cts[i]))
        return torch.from_numpy(m[np.newaxis]), self.y[i]


def _loader(ds: Dataset, shuffle: bool) -> DataLoader:
    return DataLoader(ds, batch_size=BATCH, shuffle=shuffle, num_workers=0)


# ─── Treino CNN com checkpoint por época ─────────────────────────────────────

def _train(
    model:  nn.Module,
    ds_tr:  Dataset,
    ds_vl:  Dataset,
    y_vl:   np.ndarray,
    device: str,
    name:   str,
    fold:   int,
    seed:   int = SEED_MODEL,
) -> nn.Module:
    """3 épocas fixas, checkpoint após cada época, retoma se checkpoint existe."""
    torch.manual_seed(seed)
    np.random.seed(seed)
    opt  = torch.optim.Adam(model.parameters(), lr=1e-3)
    crit = nn.CrossEntropyLoss()
    ckpt = CKPT_DIR / f"{name}_f{fold}.pt"
    start = 1

    if ckpt.exists():
        st = torch.load(ckpt, map_location=device)
        model.load_state_dict(st["model"])
        opt.load_state_dict(st["opt"])
        torch.set_rng_state(st["rng"])
        start = st["epoch"] + 1
        print(f"      [resume] {name} fold{fold} a partir da época {st['epoch']}")

    for ep in range(start, N_EPOCHS + 1):
        model.train()
        for xb, yb in _loader(ds_tr, shuffle=True):
            xb, yb = xb.to(device), yb.to(device)
            opt.zero_grad()
            crit(model(xb), yb).backward()
            opt.step()

        model.eval()
        vl, n, preds = 0.0, 0, []
        with torch.no_grad():
            for xb, yb in _loader(ds_vl, shuffle=False):
                xb, yb = xb.to(device), yb.to(device)
                lg      = model(xb)
                vl     += crit(lg, yb).item() * xb.size(0)
                n      += xb.size(0)
                preds.extend(lg.argmax(1).cpu().numpy())
        vloss = vl / n
        vf1   = float(f1_score(y_vl, preds, average="macro", zero_division=0))
        print(f"      ep{ep}  val_loss={vloss:.4f}  val_f1={vf1:.4f}")

        if _MLFLOW:
            mlflow.log_metric(f"{name}_f{fold}_val_loss", vloss, step=ep)
            mlflow.log_metric(f"{name}_f{fold}_val_f1",   vf1,   step=ep)

        torch.save({
            "epoch": ep,
            "model": model.state_dict(),
            "opt":   opt.state_dict(),
            "rng":   torch.get_rng_state(),
        }, ckpt)

    model.eval()
    return model


def _infer(model: nn.Module, ds: Dataset, device: str) -> np.ndarray:
    """Retorna y_pred para todo ds."""
    model.eval()
    preds = []
    with torch.no_grad():
        for xb, _ in _loader(ds, shuffle=False):
            preds.extend(model(xb.to(device)).argmax(1).cpu().numpy())
    return np.array(preds)


def _latents(model: nn.Module, ds: Dataset, device: str) -> np.ndarray:
    """Extrai vetor latente via extract_latent()."""
    model.eval()
    chunks = []
    with torch.no_grad():
        for xb, _ in _loader(ds, shuffle=False):
            chunks.append(model.extract_latent(xb.to(device)).cpu().numpy())
    return np.concatenate(chunks)


# ─── Carga e subsample ───────────────────────────────────────────────────────

def load_data() -> tuple[pd.DataFrame, list[str], list[str], dict[str, int]]:
    print("  Carregando raw parquet  (memory_map=True)...")
    raw = pd.read_parquet(
        RAW_PQ,
        columns=["sample_id", "algorithm", "key_id", "split", "ciphertext"],
        memory_map=True,
    )
    raw = raw[raw["split"].isin(["train", "val"])].copy()

    rng   = np.random.default_rng(SEED)
    parts = []
    for algo, grp in raw.groupby("algorithm"):
        n = min(N_PER_CLASS, len(grp))
        parts.append(grp.sample(n=n, random_state=int(rng.integers(0, 2**31))))
    df = pd.concat(parts).reset_index(drop=True)

    print("  Carregando features parquet  (memory_map=True)...")
    feat  = pd.read_parquet(FEAT_PQ, memory_map=True)
    fcols = _feat_cols(feat)
    df    = df.merge(feat[["sample_id"] + fcols], on="sample_id", how="left")

    classes   = sorted(df["algorithm"].unique().tolist())
    label_map = {c: i for i, c in enumerate(classes)}

    print(f"  {len(df)} amostras | {df['key_id'].nunique()} chaves únicas | "
          f"{len(fcols)} features clássicas")
    if len(fcols) != 307:
        print(f"  [warn] esperava 307 features, obteve {len(fcols)}")
    return df, fcols, classes, label_map


# ─── Caminhos B e C ──────────────────────────────────────────────────────────

def run_bc(
    df:        pd.DataFrame,
    classes:   list[str],
    label_map: dict[str, int],
    device:    str,
) -> dict[str, dict]:
    print("\n" + "─" * 55)
    print("  Caminhos B (CNN1D) e C (CNN2D)")

    gkf = GroupKFold(N_FOLDS)
    y   = df["algorithm"].map(label_map).to_numpy()
    cts = df["ciphertext"].tolist()
    grp = df["key_id"].to_numpy()

    acc: dict[str, list[float]] = {
        "B_cnn1d_direct": [], "B_cnn1d_latent_rf": [],
        "C_cnn2d_direct": [], "C_cnn2d_latent_rf": [],
    }

    for fi, (tri, vli) in enumerate(gkf.split(df, y, grp)):
        y_tr, y_vl = y[tri], y[vli]
        cts_tr = [cts[i] for i in tri]
        cts_vl = [cts[i] for i in vli]
        print(f"\n  [Fold {fi+1}/{N_FOLDS}]  treino={len(tri)}  val={len(vli)}")

        # ── CNN1D ─────────────────────────────────────────────────────────
        seed_fold = SEED_MODEL + fi * 100
        print(f"    [CNN1D] n_filters={CNN1D_NFILT}  n_conv={CNN1D_NCONV}  max_len={MAX_LEN_B}")
        torch.manual_seed(seed_fold + 1)
        m1   = CiphertextCNN1D(
            n_classes=len(classes), max_len=MAX_LEN_B,
            n_filters=CNN1D_NFILT, n_conv_blocks=CNN1D_NCONV,
        ).to(device)
        dtr1 = _SeqDS(cts_tr, y_tr)
        dvl1 = _SeqDS(cts_vl, y_vl)

        t0 = time.perf_counter()
        m1  = _train(m1, dtr1, dvl1, y_vl, device, "cnn1d", fi, seed=seed_fold + 1)
        print(f"    CNN1D  t={time.perf_counter()-t0:.1f}s  "
              f"latent_dim={m1.latent_dim}")

        p1 = _infer(m1, dvl1, device)
        f1_dir = float(f1_score(y_vl, p1, average="macro", zero_division=0))
        acc["B_cnn1d_direct"].append(f1_dir)

        Z_tr1  = _latents(m1, dtr1, device)
        Z_vl1  = _latents(m1, dvl1, device)
        sc1    = StandardScaler().fit(Z_tr1)
        rf1    = RandomForestClassifier(100, random_state=SEED_MODEL, n_jobs=-1)
        rf1.fit(sc1.transform(Z_tr1), y_tr)
        f1_lat = float(f1_score(
            y_vl, rf1.predict(sc1.transform(Z_vl1)), average="macro", zero_division=0,
        ))
        acc["B_cnn1d_latent_rf"].append(f1_lat)
        print(f"    CNN1D  direct={f1_dir:.4f}  latent_rf={f1_lat:.4f}")

        # ── CNN2D ─────────────────────────────────────────────────────────
        print("    [CNN2D] co-ocorrência 256×256 (CT completo)")
        torch.manual_seed(seed_fold + 2)
        m2   = CiphertextCNN2D(n_classes=len(classes)).to(device)
        dtr2 = _CoocDS(cts_tr, y_tr)
        dvl2 = _CoocDS(cts_vl, y_vl)

        t0 = time.perf_counter()
        m2  = _train(m2, dtr2, dvl2, y_vl, device, "cnn2d", fi, seed=seed_fold + 2)
        print(f"    CNN2D  t={time.perf_counter()-t0:.1f}s  "
              f"latent_dim={m2.latent_dim}")

        p2 = _infer(m2, dvl2, device)
        f2_dir = float(f1_score(y_vl, p2, average="macro", zero_division=0))
        acc["C_cnn2d_direct"].append(f2_dir)

        Z_tr2  = _latents(m2, dtr2, device)
        Z_vl2  = _latents(m2, dvl2, device)
        sc2    = StandardScaler().fit(Z_tr2)
        rf2    = RandomForestClassifier(100, random_state=SEED_MODEL, n_jobs=-1)
        rf2.fit(sc2.transform(Z_tr2), y_tr)
        f2_lat = float(f1_score(
            y_vl, rf2.predict(sc2.transform(Z_vl2)), average="macro", zero_division=0,
        ))
        acc["C_cnn2d_latent_rf"].append(f2_lat)
        print(f"    CNN2D  direct={f2_dir:.4f}  latent_rf={f2_lat:.4f}")

    summary = {k: {"folds": v, "mean": round(float(np.mean(v)), 4)}
               for k, v in acc.items()}
    if _MLFLOW:
        for k, v in summary.items():
            mlflow.log_metric(f"bc_{k}_f1_mean", v["mean"])
    return summary


# ─── Caminho D ───────────────────────────────────────────────────────────────

def run_d(
    df:        pd.DataFrame,
    feat_cols: list[str],
    classes:   list[str],
    label_map: dict[str, int],
    device:    str,
) -> dict:
    print("\n" + "─" * 55)
    print("  Caminho D  [307D clássicas | latent CNN1D | latent CNN2D] → RF")

    gkf = GroupKFold(N_FOLDS)
    y   = df["algorithm"].map(label_map).to_numpy()
    cts = df["ciphertext"].tolist()
    grp = df["key_id"].to_numpy()
    f1s: list[float] = []

    for fi, (tri, vli) in enumerate(gkf.split(df, y, grp)):
        y_tr, y_vl = y[tri], y[vli]
        cts_tr = [cts[i] for i in tri]
        cts_vl = [cts[i] for i in vli]
        print(f"\n  [Híbrido Fold {fi+1}/{N_FOLDS}]  treino={len(tri)}  val={len(vli)}")

        # Treinar CNN1D e CNN2D no fold
        seed_fold = SEED_MODEL + fi * 100
        torch.manual_seed(seed_fold + 1)
        m1   = CiphertextCNN1D(
            n_classes=len(classes), max_len=MAX_LEN_B,
            n_filters=CNN1D_NFILT, n_conv_blocks=CNN1D_NCONV,
        ).to(device)
        dtr1 = _SeqDS(cts_tr, y_tr)
        dvl1 = _SeqDS(cts_vl, y_vl)
        m1   = _train(m1, dtr1, dvl1, y_vl, device, "hyb_1d", fi, seed=seed_fold + 1)

        torch.manual_seed(seed_fold + 2)
        m2   = CiphertextCNN2D(n_classes=len(classes)).to(device)
        dtr2 = _CoocDS(cts_tr, y_tr)
        dvl2 = _CoocDS(cts_vl, y_vl)
        m2   = _train(m2, dtr2, dvl2, y_vl, device, "hyb_2d", fi, seed=seed_fold + 2)

        # Construir vetor híbrido (307 + latent1D + latent2D)
        # nan_to_num sem copy=False — iloc pode retornar array read-only
        F_tr = np.nan_to_num(df.iloc[tri][feat_cols].to_numpy(dtype=np.float64))
        F_vl = np.nan_to_num(df.iloc[vli][feat_cols].to_numpy(dtype=np.float64))

        Z1_tr = _latents(m1, dtr1, device)
        Z1_vl = _latents(m1, dvl1, device)
        Z2_tr = _latents(m2, dtr2, device)
        Z2_vl = _latents(m2, dvl2, device)

        X_tr = np.concatenate([F_tr, Z1_tr.astype(np.float64), Z2_tr.astype(np.float64)], axis=1)
        X_vl = np.concatenate([F_vl, Z1_vl.astype(np.float64), Z2_vl.astype(np.float64)], axis=1)
        dim  = X_tr.shape[1]
        print(f"    Vetor híbrido: {dim}D  "
              f"(307 + {m1.latent_dim} CNN1D + {m2.latent_dim} CNN2D)")

        # Feature selection (com fallback se falhar)
        fn = (feat_cols
              + [f"l1d_{i}" for i in range(m1.latent_dim)]
              + [f"l2d_{i}" for i in range(m2.latent_dim)])
        try:
            sel = LWCFeatureSelector(SELECTOR_CFG)
            sel.fit(X_tr, y_tr, feature_names=fn)
            X_tr_s = sel.transform(X_tr)
            X_vl_s = sel.transform(X_vl)
            print(f"    FS: {dim} → {X_tr_s.shape[1]} features selecionadas")
        except Exception as exc:
            print(f"    [warn] FS falhou ({exc}) — usando todas as {dim} features")
            X_tr_s, X_vl_s = X_tr, X_vl

        # RF
        sc    = StandardScaler().fit(X_tr_s)
        rf    = RandomForestClassifier(100, random_state=SEED_MODEL, n_jobs=-1)
        rf.fit(sc.transform(X_tr_s), y_tr)
        f1    = float(f1_score(
            y_vl, rf.predict(sc.transform(X_vl_s)), average="macro", zero_division=0,
        ))
        f1s.append(f1)
        print(f"    RF  F1={f1:.4f}")

        if _MLFLOW:
            mlflow.log_metric(f"d_rf_fold{fi+1}_f1", f1)

    mean_f1 = float(np.mean(f1s))
    if _MLFLOW:
        mlflow.log_metric("d_rf_f1_mean", mean_f1)
    return {"folds": f1s, "mean": round(mean_f1, 4)}


# ─── Main ────────────────────────────────────────────────────────────────────

def main() -> None:
    t0     = time.perf_counter()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    ram0   = _ram_mb()

    print(f"\n{'='*60}")
    print(f"  SMOKE TEST — Caminhos B, C, D")
    print(f"  {N_PER_CLASS*2} amostras · {N_FOLDS} folds · {N_EPOCHS} épocas")
    print(f"  device={device}  MLflow={'ativo' if _MLFLOW else 'nao instalado'}")
    print(f"  psutil={'sim' if _PSUTIL else 'nao instalado'}")
    print(f"{'='*60}\n")

    _ctx = mlflow.start_run(run_name="smoke_test") if _MLFLOW else _NullCtx()
    with _ctx:
        if _MLFLOW:
            mlflow.log_params({
                "n_samples":               N_PER_CLASS * 2,
                "n_folds":                 N_FOLDS,
                "n_epochs":                N_EPOCHS,
                "cnn1d_max_len_caminhoB":  MAX_LEN_B,
                "cnn1d_max_len_caminhoD":  MAX_LEN_B,   # smoke test: força prefixo mesmo no D
                "caminho_d_ct_completo":   False,        # smoke test: sempre False
                "cnn1d_nfilt":             CNN1D_NFILT,
                "cnn1d_nconv":             CNN1D_NCONV,
                "device":                  device,
                "seed":                    SEED,
            })

        df, feat_cols, classes, label_map = load_data()

        bc = run_bc(df, classes, label_map, device)
        d  = run_d(df, feat_cols, classes, label_map, device)

        elapsed = time.perf_counter() - t0
        ram1    = _ram_mb()

        if _MLFLOW:
            mlflow.log_metric("total_time_s", round(elapsed, 1))
            mlflow.log_metric("peak_ram_mb",  round(ram1, 0))

        gpu_str = (
            f"sim  —  {torch.cuda.get_device_name(0)}"
            if torch.cuda.is_available() else "nao  (CPU only)"
        )

        print(f"\n{'='*60}")
        print(f"  SMOKE TEST CONCLUÍDO  {'✓ OK' if elapsed < 600 else '✗ EXCEDEU 10min'}")
        print(f"{'='*60}")
        print(f"  Tempo total  : {elapsed:.1f}s")
        print(f"  RAM usada    : {ram1:.0f} MB  (Δ +{ram1-ram0:.0f} MB)")
        print(f"  GPU detectada: {gpu_str}")
        print()
        print(f"  {'Modo':<24}  {'fold1':>6}  {'fold2':>6}  {'média':>6}")
        print(f"  {'-'*46}")
        for k, v in bc.items():
            f = v["folds"]
            print(f"  {k:<24}  {f[0]:>6.4f}  {f[1]:>6.4f}  {v['mean']:>6.4f}")
        f = d["folds"]
        print(f"  {'D_hybrid_RF':<24}  {f[0]:>6.4f}  {f[1]:>6.4f}  {d['mean']:>6.4f}")
        print()
        print(f"  Checkpoints em: {CKPT_DIR.relative_to(REPO_ROOT)}/")
        print()
        print(f"  AVISO: Caminho D no smoke test usa prefixo {MAX_LEN_B} bytes (CPU).")
        print( "         Execucao de producao requer GPU para CT completo "
              f"({MAX_LEN_D_CNN1D} bytes).")
        print()
        print(f"  PASS — pipeline executou sem erros")
        print(f"{'='*60}")


class _NullCtx:
    def __enter__(self):  return self
    def __exit__(self, *_): pass


if __name__ == "__main__":
    main()
