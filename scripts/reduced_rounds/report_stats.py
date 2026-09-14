"""Estatística completa do estudo de rodadas reduzidas, sobre features já salvas.

Por que este script existe. Os runners (`run_full.py`, `run_xor_pairs.py`)
reportaram um subconjunto pobre: só F1-macro, balanced accuracy, matriz de
confusão e um IC bootstrap feito à mão. Faltava tudo o que a produção
(`run_v2_caminho_a.py`) reporta — accuracy, AUC-ROC, ECE, métricas por
classe, top-k, IC da balanced accuracy — e, pior, o bootstrap era **i.i.d.**,
reamostrando amostras individuais quando 100 amostras compartilham cada
chave. Isso estreita o IC artificialmente. `src/eval/metrics.py` já tem
bootstrap por CLUSTER (`groups=key_ids`) exatamente por isso; este script
usa a função da produção em vez de reimplementar, garantindo que os números
sejam comparáveis aos do experimento principal.

Como é barato rodar: as features já estão em parquet (a extração, que custa
~3,8h por config, não precisa ser repetida). Reclassificar 60k x 641 é
questão de minutos, então toda a estatística pode ser refeita quantas vezes
for preciso.

O que salva, por config:
  - `<config>_metrics.jsonl`  — um registro por fold + "final", com o mesmo
    conjunto de campos do experimento principal
  - `<config>_predictions.parquet` — predição por amostra (sample_id, key_id,
    y_true, y_pred, y_proba), o que permite McNemar entre configs depois
  - `<config>_importances.parquet` — importância das 641 features
  - `<config>_manifest.json` — parâmetros, seeds, commit, caminhos

Uso:
    python scripts/reduced_rounds/report_stats.py --all
    python scripts/reduced_rounds/report_stats.py --features build/.../features_xor_init_fraca.parquet
    python scripts/reduced_rounds/report_stats.py --mcnemar xor_init_fraca xor_completo
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

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.model_selection import GroupKFold  # noqa: E402
from sklearn.pipeline import Pipeline  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402
from sklearn.svm import SVC  # noqa: E402

from src.eval.metrics import (  # noqa: E402
    compute_auc_roc, compute_metrics, expected_calibration_error, mcnemar_test,
)
# Reusa os modelos e hiperparâmetros exatos da produção, em vez de
# reimplementar — RF/LinearSVC/XGBoost/LR com os mesmos parâmetros do
# Caminho A oficial, e `get_proba` (decision_function -> softmax para
# modelos sem predict_proba).
from scripts.run_v2_caminho_a import build_models, get_proba  # noqa: E402

# LinearSVC e LogisticRegression precisam de features escalonadas (a
# produção também faz isso, ver `build_stacking_model`) — RF/XGBoost/SVM-RBF
# não.
_NEEDS_SCALING = {"LinearSVC", "LogisticRegression"}

# SVM-RBF fica fora de `build_models()` porque a produção faz busca de
# hiperparâmetros cara (SVM_SEARCH_SUBSAMPLE); aqui é fixo, deliberadamente
# mais simples, mas com o cuidado que já é conhecido: gamma="scale" degenera
# sob subamostra (achado real do Caminho A, ver
# fix(v2): vazamento payload_rest... commit fd8bacf), então gamma é FIXO.
SVM_SUBSAMPLE = 20000
SVM_PARAMS = dict(C=1.0, gamma=0.01, kernel="rbf", probability=True)


def _svm_subsample(X, y, groups, size, seed):
    n = len(y)
    if n <= size:
        return X, y, groups
    rng = np.random.default_rng(seed)
    idx = rng.choice(n, size=size, replace=False)
    return X[idx], y[idx], groups[idx]


def build_classifier_suite(seed: int = 7) -> dict:
    """RF/LinearSVC/XGBoost/LR da produção + SVM-RBF simplificado (subamostrado,
    sem busca de hiperparâmetros — este é um estudo de sensibilidade, não o
    experimento oficial)."""
    models = build_models(seed=seed)
    models["SVM-RBF"] = SVC(random_state=seed, **SVM_PARAMS)
    return models

BASE = REPO_ROOT / "build" / "reduced_rounds"
OUT_DIR = BASE / "stats"
OUT_DIR.mkdir(parents=True, exist_ok=True)

N_TEST_KEYS = 60
N_CV_FOLDS = 5
SEED = 999001
N_BOOTSTRAP = 1000
META_COLS = ("sample_id", "algorithm", "key_id", "len_pt", "len_ct")


def _log(msg: str) -> None:
    print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {msg}", flush=True)


def _git_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT,
                              capture_output=True, text=True, check=True).stdout.strip()
    except Exception:  # noqa: BLE001
        return "desconhecido"


def _split(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    keys = sorted(df["key_id"].unique().tolist())
    rng = np.random.default_rng(SEED)
    rng.shuffle(keys)
    test = set(keys[:N_TEST_KEYS])
    return (df[~df["key_id"].isin(test)].reset_index(drop=True),
            df[df["key_id"].isin(test)].reset_index(drop=True))


def _record(name: str, fold, y_true, y_pred, y_proba, groups, labels) -> dict:
    # `expected_calibration_error` da produção exige rótulo inteiro (faz
    # `y_true.astype(np.int64)`), então codifica-se para índice de classe na
    # ordem de `labels`; os nomes ficam registrados no manifesto e em
    # `label_names` abaixo.
    code = {lab: i for i, lab in enumerate(labels)}
    yt = np.array([code[v] for v in y_true], dtype=np.int64)
    yp = np.array([code[v] for v in y_pred], dtype=np.int64)
    label_ids = list(range(len(labels)))
    rep = compute_metrics(yt, yp, y_proba=y_proba, labels=label_ids,
                          n_bootstrap=N_BOOTSTRAP, seed=42, groups=groups)
    d = rep.as_dict() if hasattr(rep, "as_dict") else dict(rep)
    auc = compute_auc_roc(yt, y_proba, labels=label_ids)
    d.update(
        config=name, fold=fold, label_names=list(labels),
        n_samples=int(len(yt)), n_bootstrap=N_BOOTSTRAP,
        bootstrap_por_chave=True, n_chaves=int(len(np.unique(groups))),
        auc_roc=(auc.get("auc") if isinstance(auc, dict) else auc),
        ece=(float(expected_calibration_error(yt, y_proba))
             if y_proba is not None else None),
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    # curva ROC não entra no jsonl (volume); fica para plot sob demanda
    d.pop("roc", None)
    return d


def _make_model(name: str, base_model):
    """Envolve LinearSVC/LR em Pipeline(StandardScaler, modelo), igual à
    produção (`build_stacking_model`) — RF/XGBoost/SVM-RBF ficam como estão."""
    if name in _NEEDS_SCALING:
        return Pipeline([("scaler", StandardScaler()), ("clf", base_model)])
    return base_model


def _fit_predict(model_name: str, base_model, X_tr, y_tr, X_ev, seed: int, label_order: list):
    """`label_order` fixa a codificação inteira usada só pelo XGBoost (não
    aceita rótulo string, diferente do resto do sklearn) — mesma ordem em
    treino e predição, senão as classes trocam de posição entre folds."""
    clf = _make_model(model_name, base_model)
    if model_name == "XGBoost":
        code = {lab: i for i, lab in enumerate(label_order)}
        y_tr_fit = np.array([code[v] for v in y_tr])
        clf.fit(X_tr, y_tr_fit)
        proba = get_proba(clf, X_ev)
        classes = np.array(label_order)[clf.classes_] if proba is not None else None
        pred = classes[proba.argmax(axis=1)] if proba is not None else \
            np.array(label_order)[clf.predict(X_ev)]
        return clf, pred, proba
    clf.fit(X_tr, y_tr)
    proba = get_proba(clf, X_ev)
    classes = clf.named_steps["clf"].classes_ if hasattr(clf, "named_steps") else clf.classes_
    pred = classes[proba.argmax(axis=1)] if proba is not None else clf.predict(X_ev)
    return clf, pred, proba


def run_for_features(features_path: Path, config_name: str | None = None,
                      models: dict | None = None) -> None:
    features_path = Path(features_path)
    name = config_name or features_path.stem.replace("features_", "")
    t0 = time.time()
    _log(f"===== [{name}] {features_path.name} =====")

    df = pd.read_parquet(features_path)  # ~61 MB, seguro carregar inteiro
    fcols = [c for c in df.columns if c not in META_COLS]
    labels = sorted(df["algorithm"].unique().tolist())
    trainval, test = _split(df)
    _log(f"  {len(df)} amostras, {len(fcols)} features, "
         f"{trainval['key_id'].nunique()} chaves treino / {test['key_id'].nunique()} teste")

    X = np.nan_to_num(trainval[fcols].to_numpy(dtype=np.float64), nan=0.0)
    y = trainval["algorithm"].to_numpy()
    g = trainval["key_id"].to_numpy()
    X_test = np.nan_to_num(test[fcols].to_numpy(dtype=np.float64), nan=0.0)
    y_test = test["algorithm"].to_numpy()
    g_test = test["key_id"].to_numpy()

    model_suite = models if models is not None else {"RandomForest": build_classifier_suite()["RandomForest"]}

    metrics_path = OUT_DIR / f"{name}_metrics.jsonl"
    metrics_path.unlink(missing_ok=True)
    records = []
    final_predictions = {}  # model_name -> (pred, proba, classes) para salvar depois

    for model_name, base_model in model_suite.items():
        X_svm, y_svm, g_svm = (
            _svm_subsample(X, y, g, SVM_SUBSAMPLE, SEED) if model_name == "SVM-RBF"
            else (X, y, g)
        )
        for fold_i, (tr, va) in enumerate(GroupKFold(n_splits=N_CV_FOLDS).split(X_svm, y_svm, g_svm)):
            _, pred, proba = _fit_predict(model_name, base_model, X_svm[tr], y_svm[tr], X_svm[va], SEED, labels)
            rec = _record(name, fold_i, y_svm[va], pred, proba, g_svm[va], labels)
            rec["model"] = model_name
            records.append(rec)
            _log(f"  [{model_name}] fold {fold_i}: F1={rec['f1_macro']:.4f} "
                 f"IC=[{rec['f1_macro_ci_lower']:.4f}, {rec['f1_macro_ci_upper']:.4f}] "
                 f"AUC={rec.get('auc_roc')}")

        X_final, y_final = (X_svm, y_svm) if model_name == "SVM-RBF" else (X, y)
        clf, pred, proba = _fit_predict(model_name, base_model, X_final, y_final, X_test, SEED, labels)
        rec = _record(name, "final", y_test, pred, proba, g_test, labels)
        rec["model"] = model_name
        records.append(rec)
        final_predictions[model_name] = (pred, proba, clf)
        _log(f"  [{model_name}] FINAL: F1={rec['f1_macro']:.4f} "
             f"IC=[{rec['f1_macro_ci_lower']:.4f}, {rec['f1_macro_ci_upper']:.4f}] (por chave)  "
             f"bal_acc={rec['balanced_accuracy']:.4f}  AUC={rec.get('auc_roc')}  ECE={rec.get('ece')}")

    with open(metrics_path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")

    pred_cols = {"sample_id": test["sample_id"].to_numpy(), "key_id": g_test, "y_true": y_test}
    for model_name, (pred, proba, clf) in final_predictions.items():
        pred_cols[f"y_pred_{model_name}"] = pred
        if proba is not None:
            # `labels` (não `clf.classes_`) porque XGBoost fita em código
            # inteiro — `proba` já foi reordenada para `labels` em `_fit_predict`.
            for i, c in enumerate(labels):
                pred_cols[f"proba_{model_name}_{c}"] = proba[:, i]
    pd.DataFrame(pred_cols).to_parquet(OUT_DIR / f"{name}_predictions.parquet", index=False)

    if "RandomForest" in final_predictions:
        rf_clf = final_predictions["RandomForest"][2]
        imp = pd.DataFrame({"feature": fcols, "importance": rf_clf.feature_importances_}) \
            .sort_values("importance", ascending=False)
        imp.to_parquet(OUT_DIR / f"{name}_importances.parquet", index=False)
        _log(f"  top-5 features (RandomForest): {', '.join(imp['feature'].head(5).tolist())}")

    (OUT_DIR / f"{name}_manifest.json").write_text(json.dumps(dict(
        config=name, features_path=str(features_path), n_samples=len(df),
        n_features=len(fcols), labels=labels, seed=SEED, model_seed=7,
        models=list(model_suite), svm_subsample=SVM_SUBSAMPLE, svm_params=SVM_PARAMS,
        n_cv_folds=N_CV_FOLDS, n_test_keys=N_TEST_KEYS, n_bootstrap=N_BOOTSTRAP,
        bootstrap="cluster por key_id (src/eval/metrics.py)",
        git_commit=_git_commit(),
        generated_at=datetime.now(timezone.utc).isoformat(),
    ), indent=2, ensure_ascii=False), encoding="utf-8")
    _log(f"  salvo em stats/ ({time.time() - t0:.0f}s)")
    _log(f"  salvo em {OUT_DIR.name}/ ({time.time() - t0:.0f}s)")


def run_mcnemar(name_a: str, name_b: str, model_name: str = "RandomForest") -> None:
    pa = OUT_DIR / f"{name_a}_predictions.parquet"
    pb = OUT_DIR / f"{name_b}_predictions.parquet"
    for p in (pa, pb):
        if not p.exists():
            _log(f"AVISO: faltam predições ({p.name}); rode as configs primeiro.")
            return
    a, b = pd.read_parquet(pa), pd.read_parquet(pb)
    col = f"y_pred_{model_name}"
    if col not in a.columns or col not in b.columns:
        _log(f"AVISO: modelo {model_name!r} não encontrado nas predições salvas "
             f"(colunas disponíveis: {[c for c in a.columns if c.startswith('y_pred_')]})")
        return
    # mesmo split determinístico -> mesmas chaves de teste; alinhar por posição
    # dentro de cada key_id não é seguro entre datasets diferentes, então
    # compara-se o acerto por amostra na ordem de sample_id ordenada.
    a = a.sort_values("sample_id").reset_index(drop=True)
    b = b.sort_values("sample_id").reset_index(drop=True)
    n = min(len(a), len(b))
    res = mcnemar_test(np.ones(n), (a["y_true"][:n] == a[col][:n]).to_numpy().astype(int),
                       (b["y_true"][:n] == b[col][:n]).to_numpy().astype(int))
    out = OUT_DIR / f"mcnemar_{name_a}_vs_{name_b}.json"
    out.write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")
    _log(f"McNemar {name_a} vs {name_b}: {res}")
    _log(f"  salvo em {out.name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--features", nargs="+", default=None)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--mcnemar", nargs=2, metavar=("A", "B"), default=None)
    parser.add_argument("--models", choices=["rf", "all"], default="rf",
                        help="'rf' = só RandomForest (default, compatível com rodadas "
                             "anteriores); 'all' = RF+LinearSVC+XGBoost+LR+SVM-RBF, "
                             "o mesmo conjunto do Caminho A de produção")
    args = parser.parse_args()

    if args.mcnemar:
        run_mcnemar(*args.mcnemar)
        sys.exit(0)

    if args.all or not args.features:
        targets = sorted(BASE.glob("*/features_*.parquet"))
        if not targets:
            _log("Nenhum parquet de features encontrado.")
            sys.exit(1)
    else:
        targets = [Path(p) for p in args.features]

    model_suite = build_classifier_suite() if args.models == "all" else None
    _log(f"Alvos: {[p.name for p in targets]} | modelos: "
         f"{list(model_suite) if model_suite else ['RandomForest']}")
    for p in targets:
        run_for_features(p, models=model_suite)
    _log("Concluído.")
