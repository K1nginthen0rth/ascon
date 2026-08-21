"""
Ablação de seleção de features — Ascon-AEAD128 vs GIFT-COFB (dataset 60k).

MOTIVAÇÃO
---------
O experimento principal (`run_experiment_60k_cv.py`) reportou F1-macro ~0,50 com
UMA única feature sobrevivente (`ngram_2_chi2`) no modelo final. Isso abre uma
objeção legítima: a ausência de sinal poderia ser artefato do seletor, não
propriedade dos criptogramas. Duas etapas do pipeline são suspeitas:

  1. VarianceThreshold(1e-5) em unidades ABSOLUTAS elimina 278 das 307 features.
     O histograma de bytes (256 features) tem variância ~5,9e-8 porque é
     frequência relativa (média 1/256 = 0,0039). O corte é de ESCALA, não de
     informação.
  2. Boruta (na versão usada na época) filtrava o conjunto final e colapsou para
     1 feature em 2 dos 5 folds e no modelo final.

Esta ablação remove o seletor da equação e mede o teto de desempenho disponível.

BRAÇOS
------
  all307   : todas as 307 features, sem qualquer seleção
  vt29     : as 29 features que sobrevivem ao VarianceThreshold(1e-5)
  hist256  : apenas o histograma de bytes (a família descartada pelo VT)
  top1     : apenas `ngram_2_chi2` (o que foi de fato usado no relatório)

PROTOCOLO (idêntico ao experimento principal)
---------------------------------------------
  Split    : 240 chaves trainval / 60 chaves test (key-holdout estrito)
  CV       : 5-fold GroupKFold agrupado por key_id dentro do trainval
  Modelos  : LR, LinearSVC, RF(500), XGBoost(500)   [SVM-RBF omitido: ~1h/fold]
  Escala   : StandardScaler fitado SÓ no treino do fold (LR e LinearSVC)
  Métricas : F1-macro, balanced accuracy, ROC-AUC, IC 95% bootstrap (1000×, seed 42)

TESTE DE PERMUTAÇÃO
-------------------
Além dos braços, roda N_PERM permutações do rótulo no braço all307 (LR + XGBoost)
para estimar a distribuição nula EMPÍRICA de F1 sob H0. Isso permite afirmar
"não distinguível" contra um baseline medido, e não contra o valor teórico 0,50.

Seeds: modelos=7, bootstrap=42, permutação=101

Saídas em reports/ablation_fs_60k/:
  ablation_results.json
  ablation_table.md
  permutation_null.json

Uso:
    python scripts/run_ablation_fs_60k.py
    python scripts/run_ablation_fs_60k.py --arms all307,vt29
    python scripts/run_ablation_fs_60k.py --skip-perm
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src" / "crypto"))

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score, f1_score, roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler
from sklearn.svm import LinearSVC
from xgboost import XGBClassifier

DATASET_ID   = "keyholdout_2class_60k_v1"
DATA_DIR     = REPO_ROOT / "data" / "processed"
FEAT_PARQUET = DATA_DIR / f"{DATASET_ID}_features.parquet"
SPLITS_JSON  = DATA_DIR / f"{DATASET_ID}_splits.json"
REPORTS_DIR  = REPO_ROOT / "reports" / "ablation_fs_60k"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

N_FOLDS        = 5
N_BOOTSTRAP    = 1000
N_PERM         = 20
SEED_MODELS    = 7
SEED_BOOTSTRAP = 42
SEED_PERM      = 101
VT_THRESHOLD   = 1e-5

_NON_FEATURE_COLS = {
    "sample_id", "algorithm", "key_id", "nonce_id",
    "len_pt", "len_ad", "len_ct", "split", "split_orig",
    "mode", "impl", "plaintext_source", "seed", "version",
    "timestamp", "ciphertext",
}

_NEEDS_SCALING = {"LR", "LinearSVC"}


# ---------------------------------------------------------------------------
# Dados
# ---------------------------------------------------------------------------

def load_data() -> tuple[pd.DataFrame, pd.DataFrame, list[str], list[str]]:
    """Carrega features e aplica o split 80/20 por chave a partir do splits.json."""
    df = pd.read_parquet(FEAT_PARQUET)
    splits = json.loads(SPLITS_JSON.read_text(encoding="utf-8"))

    trainval_keys = set(splits["train_keys"]) | set(splits["val_keys"])
    test_keys     = set(splits["test_keys"])
    if trainval_keys & test_keys:
        raise ValueError("VAZAMENTO: chaves compartilhadas entre trainval e test.")

    tv = df[df["key_id"].isin(trainval_keys)].copy()
    te = df[df["key_id"].isin(test_keys)].copy()
    if len(tv) == 0 or len(te) == 0:
        raise ValueError("Bloco trainval ou test vazio — verifique o splits.json.")

    feat_cols = [c for c in df.columns
                 if c not in _NON_FEATURE_COLS and df[c].dtype.kind in ("f", "i", "u")]
    classes = sorted(df["algorithm"].unique().tolist())

    print(f"  TrainVal : {len(tv):,} amostras | {tv['key_id'].nunique()} chaves")
    print(f"  Test     : {len(te):,} amostras | {te['key_id'].nunique()} chaves")
    print(f"  Features : {len(feat_cols)}  |  Classes: {classes}")
    return tv, te, feat_cols, classes


def build_arms(X_tv: np.ndarray, feat_cols: list[str]) -> dict[str, list[int]]:
    """Define os índices de coluna de cada braço da ablação."""
    var = np.nanvar(X_tv, axis=0)
    vt_idx   = [i for i in range(len(feat_cols)) if var[i] > VT_THRESHOLD]
    hist_idx = [i for i, c in enumerate(feat_cols) if c.startswith("byte_hist_")]
    top1_idx = [i for i, c in enumerate(feat_cols) if c == "ngram_2_chi2"]

    arms = {
        "all307":  list(range(len(feat_cols))),
        "vt29":    vt_idx,
        "hist256": hist_idx,
        "top1":    top1_idx,
    }
    for name, idx in arms.items():
        print(f"  Braço {name:8s}: {len(idx)} features")
    return arms


# ---------------------------------------------------------------------------
# Modelos e métricas
# ---------------------------------------------------------------------------

def build_models() -> dict:
    s = SEED_MODELS
    return {
        "LR": LogisticRegression(
            C=1.0, class_weight="balanced", max_iter=2000,
            random_state=s, n_jobs=-1,
        ),
        "LinearSVC": LinearSVC(
            C=1.0, class_weight="balanced", random_state=s, max_iter=5000,
        ),
        "RF": RandomForestClassifier(
            n_estimators=500, max_depth=None, class_weight="balanced",
            random_state=s, n_jobs=-1,
        ),
        "XGBoost": XGBClassifier(
            n_estimators=500, max_depth=6, learning_rate=0.1,
            random_state=s, n_jobs=-1, eval_metric="logloss", tree_method="hist",
        ),
    }


def _scores(model, X: np.ndarray) -> np.ndarray | None:
    """Score contínuo da classe positiva, para ROC-AUC."""
    if hasattr(model, "predict_proba"):
        try:
            return model.predict_proba(X)[:, 1]
        except Exception:
            pass
    if hasattr(model, "decision_function"):
        d = model.decision_function(X)
        return d if d.ndim == 1 else d[:, 1]
    return None


def bootstrap_ci(y_true: np.ndarray, y_pred: np.ndarray,
                 n_boot: int = N_BOOTSTRAP, seed: int = SEED_BOOTSTRAP) -> tuple[float, float]:
    """IC 95% percentil do F1-macro por reamostragem com reposição."""
    rng  = np.random.default_rng(seed)
    n    = len(y_true)
    vals = np.empty(n_boot)
    for b in range(n_boot):
        idx = rng.integers(0, n, n)
        vals[b] = f1_score(y_true[idx], y_pred[idx], average="macro", zero_division=0)
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


# ---------------------------------------------------------------------------
# Execução de um braço
# ---------------------------------------------------------------------------

def run_arm(name: str, cols: list[int],
            X_tv: np.ndarray, y_tv: np.ndarray, groups: np.ndarray,
            X_te: np.ndarray, y_te: np.ndarray) -> dict:
    """CV 5-fold por chave + modelo final no holdout, para um braço."""
    print(f"\n{'='*70}\nBRAÇO: {name}  ({len(cols)} features)\n{'='*70}")
    Xtv = X_tv[:, cols]
    Xte = X_te[:, cols]

    # ---- CV ----
    gkf = GroupKFold(n_splits=N_FOLDS)
    cv_scores: dict[str, list[float]] = {m: [] for m in build_models()}

    for fold, (tr, va) in enumerate(gkf.split(Xtv, y_tv, groups), start=1):
        assert not (set(groups[tr]) & set(groups[va])), f"Fold {fold}: vazamento de chave!"
        scaler = StandardScaler().fit(Xtv[tr])
        Xtr_sc, Xva_sc = scaler.transform(Xtv[tr]), scaler.transform(Xtv[va])

        for mname, mdl in build_models().items():
            Xtr = Xtr_sc if mname in _NEEDS_SCALING else Xtv[tr]
            Xva = Xva_sc if mname in _NEEDS_SCALING else Xtv[va]
            mdl.fit(Xtr, y_tv[tr])
            f1 = float(f1_score(y_tv[va], mdl.predict(Xva), average="macro", zero_division=0))
            cv_scores[mname].append(f1)
            print(f"  [fold {fold}] {mname:10s} F1={f1:.4f}")

    # ---- Modelo final no holdout ----
    scaler = StandardScaler().fit(Xtv)
    Xtv_sc, Xte_sc = scaler.transform(Xtv), scaler.transform(Xte)

    final: dict[str, dict] = {}
    for mname, mdl in build_models().items():
        Xa = Xtv_sc if mname in _NEEDS_SCALING else Xtv
        Xb = Xte_sc if mname in _NEEDS_SCALING else Xte
        t0 = time.perf_counter()
        mdl.fit(Xa, y_tv)
        t_train = time.perf_counter() - t0

        y_pred = mdl.predict(Xb)
        sc     = _scores(mdl, Xb)
        lo, hi = bootstrap_ci(y_te, y_pred)
        cm     = np.zeros((2, 2), dtype=int)
        for t, p in zip(y_te, y_pred):
            cm[t, p] += 1

        final[mname] = {
            "f1_macro":          float(f1_score(y_te, y_pred, average="macro", zero_division=0)),
            "f1_ci_lower":       lo,
            "f1_ci_upper":       hi,
            "balanced_accuracy": float(balanced_accuracy_score(y_te, y_pred)),
            "roc_auc":           float(roc_auc_score(y_te, sc)) if sc is not None else None,
            "confusion_matrix":  cm.tolist(),
            "cv_f1_mean":        float(np.mean(cv_scores[mname])),
            "cv_f1_std":         float(np.std(cv_scores[mname])),
            "cv_f1_folds":       [round(v, 4) for v in cv_scores[mname]],
            "train_time_s":      round(t_train, 2),
        }
        print(f"  [final] {mname:10s} F1={final[mname]['f1_macro']:.4f} "
              f"IC[{lo:.4f},{hi:.4f}] AUC={final[mname]['roc_auc']} CM={cm.tolist()}")

    return {"n_features": len(cols), "models": final}


# ---------------------------------------------------------------------------
# Teste de permutação (distribuição nula empírica)
# ---------------------------------------------------------------------------

def _shuffle_by_key(rng, groups: np.ndarray, uniq_keys: np.ndarray) -> np.ndarray:
    """
    Rótulo aleatório constante dentro de cada chave (50/50 entre chaves).

    Neste dataset cada `key_id` gera 100 amostras de Ascon e 100 de GIFT-COFB.
    Sortear o rótulo por chave confunde deliberadamente rótulo e identidade de
    chave: o modelo pode decorar a chave no treino, mas isso não transfere para
    as 60 chaves inéditas do holdout. Mede, portanto, o F1 alcançável em chaves
    novas quando o rótulo de treino não carrega informação de algoritmo.
    """
    lab = rng.permutation(np.tile([0, 1], len(uniq_keys) // 2 + 1)[:len(uniq_keys)])
    key2lab = dict(zip(uniq_keys, lab))
    return np.array([key2lab[g] for g in groups])


def _shuffle_within_key(rng, groups: np.ndarray, y: np.ndarray) -> np.ndarray:
    """
    Permuta os rótulos DENTRO de cada chave, preservando o balanço 100/100.

    É o nulo mais estrito: destrói apenas a associação entre o criptograma e o
    algoritmo que o gerou, mantendo intactas a estrutura de grupos, a proporção
    de classes por chave e a distribuição marginal dos atributos.
    """
    y_shuf = y.copy()
    for k in np.unique(groups):
        m = groups == k
        y_shuf[m] = rng.permutation(y[m])
    return y_shuf


def run_permutation(X_tv: np.ndarray, y_tv: np.ndarray, groups: np.ndarray,
                    X_te: np.ndarray, y_te: np.ndarray, cols: list[int],
                    scheme: str = "by_key") -> dict:
    """
    Estima a distribuição nula EMPÍRICA do F1 embaralhando os rótulos de treino.

    scheme = "by_key"      -> rótulo constante por chave (ver _shuffle_by_key)
    scheme = "within_key"  -> permutação dentro da chave (ver _shuffle_within_key)

    Os dois esquemas respondem perguntas ligeiramente distintas e são reportados
    lado a lado: se ambos produzem a mesma banda nula, a conclusão não depende da
    escolha do esquema.
    """
    print(f"\n{'='*70}\nTESTE DE PERMUTAÇÃO — esquema '{scheme}' "
          f"({N_PERM} repetições, braço all307)\n{'='*70}")
    rng    = np.random.default_rng(SEED_PERM)
    Xtv    = X_tv[:, cols]
    Xte    = X_te[:, cols]
    scaler = StandardScaler().fit(Xtv)
    Xtv_sc = scaler.transform(Xtv)
    Xte_sc = scaler.transform(Xte)

    uniq_keys = np.unique(groups)
    null: dict[str, list[float]] = {"LR": [], "XGBoost": []}

    for rep in range(N_PERM):
        if scheme == "by_key":
            y_shuf = _shuffle_by_key(rng, groups, uniq_keys)
        elif scheme == "within_key":
            y_shuf = _shuffle_within_key(rng, groups, y_tv)
        else:
            raise ValueError(f"esquema desconhecido: {scheme}")

        lr = LogisticRegression(C=1.0, class_weight="balanced", max_iter=2000,
                                random_state=SEED_MODELS).fit(Xtv_sc, y_shuf)
        xg = XGBClassifier(n_estimators=500, max_depth=6, learning_rate=0.1,
                           random_state=SEED_MODELS, n_jobs=-1, eval_metric="logloss",
                           tree_method="hist").fit(Xtv, y_shuf)

        f_lr = float(f1_score(y_te, lr.predict(Xte_sc), average="macro", zero_division=0))
        f_xg = float(f1_score(y_te, xg.predict(Xte),   average="macro", zero_division=0))
        null["LR"].append(f_lr)
        null["XGBoost"].append(f_xg)
        print(f"  [perm {rep+1:02d}/{N_PERM}] LR={f_lr:.4f}  XGB={f_xg:.4f}")

    summary = {
        m: {
            "mean":  float(np.mean(v)),
            "std":   float(np.std(v)),
            "p2.5":  float(np.percentile(v, 2.5)),
            "p97.5": float(np.percentile(v, 97.5)),
            "max":   float(np.max(v)),
            "values": [round(x, 4) for x in v],
        }
        for m, v in null.items()
    }
    return {"n_perm": N_PERM, "seed": SEED_PERM, "shuffle_unit": scheme, "null": summary}


# ---------------------------------------------------------------------------
# Relatório
# ---------------------------------------------------------------------------

def write_report(results: dict, perms: dict[str, dict] | None, classes: list[str]) -> None:
    (REPORTS_DIR / "ablation_results.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    if perms:
        (REPORTS_DIR / "permutation_null.json").write_text(
            json.dumps(perms, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "# Ablação do seletor de features — Ascon-AEAD128 vs GIFT-COFB (60k)",
        "",
        f"Classes: `{classes[0]}` = 0, `{classes[1]}` = 1. Baseline do acaso = 0.5000.",
        "",
        "Protocolo: 240 chaves trainval / 60 chaves test (key-holdout estrito), "
        "5-fold GroupKFold por `key_id`, StandardScaler fitado só no treino do fold, "
        "IC 95% por bootstrap (1000×, seed 42).",
        "",
        "| Braço | Features | Modelo | F1 CV (média±dp) | F1 test | IC 95% | BalAcc | AUC | CM [[TN,FP],[FN,TP]] |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for arm, data in results.items():
        for mname, m in data["models"].items():
            auc = f"{m['roc_auc']:.4f}" if m["roc_auc"] is not None else "—"
            lines.append(
                f"| {arm} | {data['n_features']} | {mname} | "
                f"{m['cv_f1_mean']:.4f}±{m['cv_f1_std']:.4f} | {m['f1_macro']:.4f} | "
                f"[{m['f1_ci_lower']:.3f},{m['f1_ci_upper']:.3f}] | "
                f"{m['balanced_accuracy']:.4f} | {auc} | {m['confusion_matrix']} |"
            )

    if perms:
        # melhor F1 observado por modelo, sobre todos os braços
        best_obs = {}
        for data in results.values():
            for mname, m in data["models"].items():
                best_obs[mname] = max(best_obs.get(mname, 0.0), m["f1_macro"])

        lines += [
            "",
            "## Distribuição nula empírica (permutação de rótulo)",
            "",
            "`by_key`: rótulo sorteado constante por chave. "
            "`within_key`: permutação dentro da chave, preservando 100/100 por chave.",
            "",
            "| Esquema | Modelo | F1 médio sob H0 | dp | p2.5 | p97.5 | máx | "
            "Melhor F1 observado | p empírico |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for scheme, perm in perms.items():
            for m, s in perm["null"].items():
                obs = best_obs.get(m)
                if obs is None:
                    continue
                vals = np.asarray(s["values"])
                p_emp = float((vals >= obs).sum() + 1) / (len(vals) + 1)
                lines.append(
                    f"| {scheme} | {m} | {s['mean']:.4f} | {s['std']:.4f} | {s['p2.5']:.4f} | "
                    f"{s['p97.5']:.4f} | {s['max']:.4f} | {obs:.4f} | {p_emp:.3f} |"
                )
        lines += [
            "",
            "O p empírico usa a correção `(r+1)/(n+1)` de Phipson e Smyth (2010): "
            "com n permutações, o menor p atingível é 1/(n+1).",
        ]

    (REPORTS_DIR / "ablation_table.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nRelatórios escritos em {REPORTS_DIR}")


# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", default="all307,vt29,hist256,top1",
                    help="braços separados por vírgula")
    ap.add_argument("--skip-perm", action="store_true")
    ap.add_argument("--perm-schemes", default="by_key,within_key",
                    help="esquemas de permutação separados por vírgula")
    args = ap.parse_args()

    t_start = time.perf_counter()
    print("=" * 70)
    print("ABLAÇÃO DO SELETOR DE FEATURES — dataset 60k")
    print("=" * 70)

    tv, te, feat_cols, classes = load_data()
    lab = {c: i for i, c in enumerate(classes)}

    X_tv = np.nan_to_num(tv[feat_cols].to_numpy(dtype=np.float64), nan=0.0)
    X_te = np.nan_to_num(te[feat_cols].to_numpy(dtype=np.float64), nan=0.0)
    y_tv = tv["algorithm"].map(lab).to_numpy()
    y_te = te["algorithm"].map(lab).to_numpy()
    groups = tv["key_id"].to_numpy()

    arms_all = build_arms(X_tv, feat_cols)
    wanted   = [a.strip() for a in args.arms.split(",") if a.strip()]

    results = {}
    for arm in wanted:
        if arm not in arms_all:
            print(f"  (braço desconhecido ignorado: {arm})")
            continue
        results[arm] = run_arm(arm, arms_all[arm], X_tv, y_tv, groups, X_te, y_te)

    perms: dict[str, dict] = {}
    if not args.skip_perm:
        for scheme in [s.strip() for s in args.perm_schemes.split(",") if s.strip()]:
            perms[scheme] = run_permutation(X_tv, y_tv, groups, X_te, y_te,
                                            arms_all["all307"], scheme=scheme)

    write_report(results, perms, classes)
    print(f"\nTempo total: {(time.perf_counter() - t_start)/60:.1f} min")


if __name__ == "__main__":
    main()
