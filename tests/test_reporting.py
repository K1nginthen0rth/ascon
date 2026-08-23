"""Testes para src/eval/reporting.py (função única de relato — regra de
ouro 7)."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from src.eval.reporting import load_predictions, report_eval


@pytest.fixture()
def sample_data():
    rng = np.random.default_rng(0)
    n = 60
    y_true = rng.integers(0, 3, n)
    y_pred = y_true.copy()
    flip = rng.choice(n, size=10, replace=False)
    y_pred[flip] = (y_pred[flip] + 1) % 3
    proba = rng.dirichlet(alpha=[1, 1, 1], size=n)
    sample_ids = [f"sample_{i:03d}" for i in range(n)]
    key_ids = [f"key_{i % 5:02d}" for i in range(n)]
    return y_true, y_pred, proba, sample_ids, key_ids


def test_report_eval_returns_metrics_report(tmp_path, sample_data, capsys):
    y_true, y_pred, proba, sample_ids, key_ids = sample_data
    report = report_eval(
        run_id="test_run", caminho="A", modelo="RF", braco="controlado", fold=0,
        y_true=y_true, y_pred=y_pred, y_proba=proba,
        sample_ids=sample_ids, key_ids=key_ids,
        class_names=["Ascon", "GIFT", "Grain"],
        out_dir=tmp_path, n_bootstrap=50,
    )
    assert 0.0 <= report.f1_macro <= 1.0
    assert report.per_class is not None


def test_report_eval_prints_immediately(tmp_path, sample_data, capsys):
    """Regra de ouro 7: métricas devem ser impressas na hora, não só salvas."""
    y_true, y_pred, proba, sample_ids, key_ids = sample_data
    report_eval(
        run_id="test_run", caminho="A", modelo="RF", braco="controlado", fold=0,
        y_true=y_true, y_pred=y_pred, y_proba=proba,
        sample_ids=sample_ids, key_ids=key_ids,
        out_dir=tmp_path, n_bootstrap=50,
    )
    out = capsys.readouterr().out
    assert "F1-macro" in out
    assert "Acurácia" in out
    assert "Matriz de confusão" in out
    assert "Por classe" in out


def test_report_eval_writes_incremental_jsonl(tmp_path, sample_data):
    """Duas chamadas consecutivas devem ACRESCENTAR ao mesmo .jsonl, nunca
    sobrescrever o que já foi calculado (proteção contra queda de sessão)."""
    y_true, y_pred, proba, sample_ids, key_ids = sample_data
    for fold in (0, 1):
        report_eval(
            run_id="test_run", caminho="A", modelo="RF", braco="controlado", fold=fold,
            y_true=y_true, y_pred=y_pred, y_proba=proba,
            sample_ids=sample_ids, key_ids=key_ids,
            out_dir=tmp_path, n_bootstrap=50,
        )
    jsonl_path = tmp_path / "test_run_metrics.jsonl"
    assert jsonl_path.exists()
    lines = jsonl_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    records = [json.loads(line) for line in lines]
    assert records[0]["fold"] == 0
    assert records[1]["fold"] == 1
    assert all("f1_macro" in r for r in records)


def test_report_eval_saves_confusion_matrix_png(tmp_path, sample_data):
    y_true, y_pred, proba, sample_ids, key_ids = sample_data
    report_eval(
        run_id="test_run", caminho="A", modelo="RF", braco="controlado", fold=0,
        y_true=y_true, y_pred=y_pred, y_proba=proba,
        sample_ids=sample_ids, key_ids=key_ids,
        out_dir=tmp_path, n_bootstrap=50,
    )
    pngs = list((tmp_path / "confusion_matrices").glob("*.png"))
    assert len(pngs) == 1


def test_report_eval_persists_per_sample_predictions(tmp_path, sample_data):
    """Pré-requisito duro do Caminho F: predição/probabilidade por amostra,
    com sample_id e key_id reais."""
    y_true, y_pred, proba, sample_ids, key_ids = sample_data
    report_eval(
        run_id="test_run", caminho="A", modelo="RF", braco="controlado", fold=0,
        y_true=y_true, y_pred=y_pred, y_proba=proba,
        sample_ids=sample_ids, key_ids=key_ids,
        out_dir=tmp_path, n_bootstrap=50,
    )
    parquets = list((tmp_path / "predictions").glob("*.parquet"))
    assert len(parquets) == 1
    df = pd.read_parquet(parquets[0])
    assert len(df) == len(y_true)
    assert list(df["sample_id"]) == sample_ids
    assert list(df["key_id"]) == key_ids
    assert "y_proba" in df.columns
    assert len(df["y_proba"].iloc[0]) == 3  # 3 classes


def test_report_eval_without_sample_ids_uses_fallback(tmp_path, sample_data):
    """Sem sample_ids/key_ids explícitos, ainda deve funcionar (uso em
    testes rápidos), gerando IDs sintéticos."""
    y_true, y_pred, proba, _, _ = sample_data
    report_eval(
        run_id="test_run2", caminho="A", modelo="RF", braco="controlado", fold=0,
        y_true=y_true, y_pred=y_pred, y_proba=proba,
        out_dir=tmp_path, n_bootstrap=50,
    )
    parquets = list((tmp_path / "predictions").glob("test_run2_*.parquet"))
    df = pd.read_parquet(parquets[0])
    assert df["sample_id"].iloc[0] == "sample_0"
    assert df["key_id"].isna().all()


def test_load_predictions_concatenates_all_folds(tmp_path, sample_data):
    y_true, y_pred, proba, sample_ids, key_ids = sample_data
    for fold in range(3):
        report_eval(
            run_id="multi_fold_run", caminho="A", modelo="RF", braco="controlado", fold=fold,
            y_true=y_true, y_pred=y_pred, y_proba=proba,
            sample_ids=sample_ids, key_ids=key_ids,
            out_dir=tmp_path, n_bootstrap=50,
        )
    all_preds = load_predictions(tmp_path, run_id="multi_fold_run", caminho="A")
    assert len(all_preds) == len(y_true) * 3
    assert set(all_preds["fold"].unique()) == {"0", "1", "2"}


def test_load_predictions_raises_when_nothing_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_predictions(tmp_path, run_id="nao_existe")


def test_report_eval_different_folds_do_not_collide(tmp_path, sample_data):
    """Cada chamada grava seu próprio parquet — sem race/overwrite entre
    folds diferentes."""
    y_true, y_pred, proba, sample_ids, key_ids = sample_data
    for fold in range(5):
        report_eval(
            run_id="race_test", caminho="B", modelo="CNN1D", braco="controlado", fold=fold,
            y_true=y_true, y_pred=y_pred, y_proba=proba,
            sample_ids=sample_ids, key_ids=key_ids,
            out_dir=tmp_path, n_bootstrap=20,
        )
    parquets = list((tmp_path / "predictions").glob("race_test_*.parquet"))
    assert len(parquets) == 5


def test_report_eval_extra_metadata_included_in_jsonl(tmp_path, sample_data):
    y_true, y_pred, proba, sample_ids, key_ids = sample_data
    report_eval(
        run_id="extra_test", caminho="A", modelo="SVM", braco="controlado", fold="final",
        y_true=y_true, y_pred=y_pred, y_proba=proba,
        sample_ids=sample_ids, key_ids=key_ids,
        out_dir=tmp_path, n_bootstrap=50,
        extra={"best_params": {"C": 1.0, "gamma": "scale"}, "train_time_s": 12.3},
    )
    jsonl_path = tmp_path / "extra_test_metrics.jsonl"
    record = json.loads(jsonl_path.read_text(encoding="utf-8").strip())
    assert record["extra"]["best_params"]["C"] == 1.0
    assert record["fold"] == "final"


# ---------------------------------------------------------------------------
# Robustez: report_eval NUNCA pode perder um fold inteiro por causa de uma
# métrica opcional. Todos estes casos já quebraram em desenvolvimento.
# ---------------------------------------------------------------------------
def test_report_eval_survives_invalid_proba(tmp_path, capsys):
    """`y_proba` que não soma 1 fazia `roc_auc_score` levantar e derrubar a
    chamada inteira, perdendo TODAS as métricas do fold. Agora a AUC vira
    None e o resto do relato segue."""
    y_true = np.array([0, 0, 1, 1, 2, 2])
    y_pred = np.array([0, 1, 1, 1, 2, 0])
    bad_proba = np.eye(4)[y_pred] * 0.7 + 0.1  # não soma 1
    report = report_eval(
        run_id="edge", caminho="A", modelo="M", braco="b", fold=0,
        y_true=y_true, y_pred=y_pred, y_proba=bad_proba,
        class_names=["A", "B", "C", "D"], labels=[0, 1, 2, 3],
        out_dir=tmp_path, n_bootstrap=20,
    )
    assert report.auc_roc is None
    assert 0.0 <= report.f1_macro <= 1.0
    assert (tmp_path / "edge_metrics.jsonl").exists()
    assert len(list((tmp_path / "predictions").glob("*.parquet"))) == 1


def test_report_eval_handles_class_absent_from_fold(tmp_path):
    """Classe declarada em `labels` mas ausente do fold não pode quebrar
    a matriz de confusão nem os nomes das classes."""
    y_true = np.array([0, 0, 1, 1, 2, 2])       # classe 3 ausente
    y_pred = np.array([0, 1, 1, 1, 2, 0])
    report = report_eval(
        run_id="edge2", caminho="A", modelo="M", braco="b", fold=0,
        y_true=y_true, y_pred=y_pred, y_proba=np.eye(4)[y_pred],
        class_names=["A", "B", "C", "D"], labels=[0, 1, 2, 3],
        out_dir=tmp_path, n_bootstrap=20,
    )
    assert report.confusion_matrix.shape == (4, 4)
    assert report.per_class["3"]["support"] == 0


def test_report_eval_handles_single_class(tmp_path):
    y = np.zeros(5, dtype=int)
    report = report_eval(
        run_id="edge3", caminho="A", modelo="M", braco="b", fold=0,
        y_true=y, y_pred=y, y_proba=np.eye(4)[y],
        class_names=["A", "B", "C", "D"], labels=[0, 1, 2, 3],
        out_dir=tmp_path, n_bootstrap=20,
    )
    assert report.accuracy == 1.0
    assert len(list((tmp_path / "confusion_matrices").glob("*.png"))) == 1
