"""
Função única de relato — regra de ouro 7 (pedido do orientador, inviolável).

Toda métrica de todo Caminho/modelo/braço/fold deste projeto DEVE passar por
`report_eval()`. Proibido print/save de métrica fora dela — uniformidade
estrutural em vez de disciplina manual por script (motivo: no v1, métricas
eram impressas ad-hoc e só salvas no relatório final; resultados de sessões
que caíram no meio foram perdidos). Ver
docs/plano_experimento_v2/06_implementacao_passo_a_passo.md Fase 5.1 e
04_protocolo_metricas_validacao.md §4.4.

A cada chamada, `report_eval()` garante:
  1. impressão IMEDIATA de todas as métricas no console (nunca "só no
     relatório final");
  2. matriz de confusão como tabela legível no console, SEMPRE;
  3. JSON incremental — um arquivo `.jsonl` por `run_id`, uma linha
     (append) por chamada; nunca reescreve o arquivo inteiro, então uma
     queda de sessão não perde o que já foi calculado;
  4. PNG da matriz de confusão, SEMPRE (não só quando "interessante");
  5. persistência por amostra (`sample_id, key_id, fold, braço, y_true,
     y_pred, y_proba`) em parquet — pré-requisito duro do Caminho F
     (probabilidades out-of-fold para o meta-classificador), do McNemar
     pareado e da calibração. Cada chamada grava seu PRÓPRIO arquivo
     parquet (nome inclui run_id/caminho/modelo/braço/fold) — sem
     read-modify-write do mesmo arquivo, sem risco de corromper um
     resultado já salvo se o processo cair no meio da próxima chamada.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from src.eval.metrics import MetricsReport, compute_metrics


def _json_default(obj):
    """Mesma convenção já usada nos scripts de produção do v1 (ver
    scripts/run_experiment_60k_cv.py) — serializa qualquer objeto com
    `.tolist()` (arrays numpy) e cai para `str()` no restante."""
    if hasattr(obj, "tolist"):
        return obj.tolist()
    return str(obj)


def _safe_tag(value: object) -> str:
    return str(value).replace("/", "_").replace(" ", "_").replace("\\", "_")


def _print_confusion_matrix(cm: np.ndarray, names: list[str]) -> None:
    """Tabela legível no console — linhas=verdadeiro, colunas=predito."""
    short_names = [n[:10] for n in names]
    col_w = max(6, max(len(n) for n in short_names) + 1)
    header = " " * 12 + "".join(f"{n:>{col_w}s}" for n in short_names)
    print("  Matriz de confusão (linha=verdadeiro, coluna=predito):")
    print(header)
    for i, row in enumerate(cm):
        row_str = "".join(f"{int(v):>{col_w}d}" for v in row)
        print(f"    {short_names[i]:<8s}{row_str}")


def _plot_confusion_matrix(
    cm: np.ndarray, names: list[str], title: str, out_path: Path,
) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print(f"  [aviso] matplotlib indisponível — PNG da matriz não salvo ({out_path.name}).")
        return

    fig, ax = plt.subplots(figsize=(max(4, len(names) * 0.7), max(4, len(names) * 0.7)))
    im = ax.imshow(cm, cmap="Blues")
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            ax.text(j, i, str(int(cm[i, j])), ha="center", va="center", fontsize=10)
    ax.set_xticks(range(len(names)))
    ax.set_yticks(range(len(names)))
    ax.set_xticklabels(names, rotation=45, ha="right")
    ax.set_yticklabels(names)
    ax.set_xlabel("Predito")
    ax.set_ylabel("Verdadeiro")
    ax.set_title(title)
    plt.colorbar(im, ax=ax)
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def report_eval(
    run_id: str,
    caminho: str,
    modelo: str,
    braco: str,
    fold: int | str,
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_proba: Optional[np.ndarray] = None,
    sample_ids: Optional[list[str]] = None,
    key_ids: Optional[list[str]] = None,
    class_names: Optional[list[str]] = None,
    labels: Optional[list] = None,
    out_dir: Path | str = "reports/v2",
    n_bootstrap: int = 1000,
    seed: int = 42,
    extra: Optional[dict] = None,
) -> MetricsReport:
    """
    Função ÚNICA de relato de métricas — ver docstring do módulo.

    Args:
        run_id: identificador do experimento/dataset (ex.: "keyholdout_5class_v2").
        caminho: "A", "B", "C", "D", "E" ou "F".
        modelo: nome do classificador (ex.: "RandomForest", "SVM-RBF").
        braco: braço do experimento (ex.: "controlado", "cru", "sem_keyholdout").
        fold: índice do fold de CV (int) ou "final"/"test" para o holdout final.
        y_true, y_pred: rótulos verdadeiros e preditos (n_samples,).
        y_proba: probabilidades por classe (n_samples, n_classes), opcional
            mas OBRIGATÓRIO para folds cujo output alimenta o Caminho F.
        sample_ids, key_ids: identificadores por amostra — usados na
            persistência do parquet; se ausentes, gera-se `sample_{i}` e
            `None` respectivamente (aceito para testes rápidos, mas
            **obrigatório em produção** para o Caminho F conseguir juntar
            predições out-of-fold por amostra real).
        class_names: nomes legíveis das classes (para os prints/PNG); se
            ausente, usa `str(label)`.
        labels: ordem/conjunto de labels a considerar; default =
            union(y_true, y_pred) ordenado.
        out_dir: diretório raiz de saída (default reports/v2/).
        extra: dict opcional de metadados adicionais (ex.: hiperparâmetros
            do modelo, tempo de treino) — anexado ao JSON, não ao parquet.

    Returns:
        MetricsReport (mesmo objeto retornado por `compute_metrics`).
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    n = len(y_true)

    if labels is None:
        labels = sorted(np.unique(np.concatenate([y_true, y_pred])).tolist())
    display_names = (
        [str(c) for c in class_names] if class_names is not None
        else [str(lbl) for lbl in labels]
    )
    label_to_name = {str(lbl): name for lbl, name in zip(labels, display_names)}

    # `key_ids` alimenta o bootstrap por CLUSTER (ver `compute_metrics`): o
    # desenho é agrupado (100 slots por chave) e reamostrar amostras
    # individuais produz IC estreito demais sob sinal correlacionado à
    # chave. Como o veredicto primário do projeto é "o IC 95% exclui o
    # acaso", isso empurraria na direção de falso positivo. Passar aqui faz
    # TODO caminho herdar a correção sem mudar nenhum runner.
    report = compute_metrics(
        y_true, y_pred, y_proba=y_proba, labels=labels,
        n_bootstrap=n_bootstrap, seed=seed,
        groups=(np.asarray(key_ids) if key_ids is not None else None),
    )

    tag = f"[{run_id} | Caminho {caminho} | {modelo} | braço={braco} | fold={fold}]"

    # ------------------------------------------------------------------
    # 1+2. Impressão imediata (métricas agregadas + por classe + matriz)
    # ------------------------------------------------------------------
    print(f"\n{tag}")
    print(f"  n={report.n_samples}  F1-macro={report.f1_macro:.4f} "
          f"IC95%=[{report.f1_macro_ci[0]:.4f},{report.f1_macro_ci[1]:.4f}]")
    print(f"  Acurácia={report.accuracy:.4f}  "
          f"BalAcc={report.balanced_accuracy:.4f} "
          f"IC95%=[{report.balanced_accuracy_ci[0]:.4f},{report.balanced_accuracy_ci[1]:.4f}]")
    if report.ece is not None:
        print(f"  ECE={report.ece:.4f}")
    if report.auc_roc is not None:
        line = f"  AUC-ROC (OVR agregado)={report.auc_roc['auc']:.4f}"
        per_class_auc = report.auc_roc.get("auc_per_class")
        if per_class_auc:
            parts = [
                f"{label_to_name.get(k, k)}={v:.3f}" if v is not None else f"{label_to_name.get(k, k)}=n/a"
                for k, v in per_class_auc.items()
            ]
            line += "  |  por classe: " + ", ".join(parts)
        print(line)
    if report.per_class:
        print("  Por classe (precisão / recall / F1 / suporte):")
        for lbl_str, name in label_to_name.items():
            pc = report.per_class.get(lbl_str)
            if pc is None:
                continue
            print(f"    {name:<20s} P={pc['precision']:.3f}  R={pc['recall']:.3f}  "
                  f"F1={pc['f1']:.3f}  n={pc['support']}")
    _print_confusion_matrix(report.confusion_matrix, display_names)

    # ------------------------------------------------------------------
    # 3. JSON incremental (append-only, JSONL — nunca reescreve o arquivo)
    # ------------------------------------------------------------------
    metrics_path = out_dir / f"{_safe_tag(run_id)}_metrics.jsonl"
    record = {
        "run_id": run_id,
        "caminho": caminho,
        "modelo": modelo,
        "braco": braco,
        "fold": fold,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **report.as_dict(),
    }
    if extra:
        record["extra"] = extra
    with open(metrics_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, default=_json_default) + "\n")

    # ------------------------------------------------------------------
    # 4. PNG da matriz de confusão (sempre)
    # ------------------------------------------------------------------
    cm_name = (
        f"{_safe_tag(run_id)}_{_safe_tag(caminho)}_{_safe_tag(modelo)}_"
        f"{_safe_tag(braco)}_fold{_safe_tag(fold)}.png"
    )
    _plot_confusion_matrix(
        report.confusion_matrix, display_names,
        title=f"{caminho}/{modelo}/{braco}/fold={fold}  F1={report.f1_macro:.4f}",
        out_path=out_dir / "confusion_matrices" / cm_name,
    )

    # ------------------------------------------------------------------
    # 5. Persistência por amostra (parquet próprio por chamada)
    # ------------------------------------------------------------------
    pred_dir = out_dir / "predictions"
    pred_dir.mkdir(parents=True, exist_ok=True)
    data: dict[str, object] = {
        "sample_id": sample_ids if sample_ids is not None else [f"sample_{i}" for i in range(n)],
        "key_id": key_ids if key_ids is not None else [None] * n,
        "run_id": [run_id] * n,
        "caminho": [caminho] * n,
        "modelo": [modelo] * n,
        "braco": [braco] * n,
        "fold": [str(fold)] * n,
        "y_true": y_true.tolist(),
        "y_pred": y_pred.tolist(),
    }
    if y_proba is not None:
        data["y_proba"] = [row.tolist() for row in np.asarray(y_proba)]
    pred_df = pd.DataFrame(data)
    pred_path = pred_dir / (
        f"{_safe_tag(run_id)}_{_safe_tag(caminho)}_{_safe_tag(modelo)}_"
        f"{_safe_tag(braco)}_fold{_safe_tag(fold)}.parquet"
    )
    pred_df.to_parquet(pred_path, index=False)

    return report


def load_predictions(
    out_dir: Path | str, run_id: str, caminho: Optional[str] = None,
) -> pd.DataFrame:
    """
    Carrega e concatena todos os parquets de predição por amostra salvos
    por `report_eval()` para um `run_id` (opcionalmente filtrando por
    `caminho`) — uso típico: montar a matriz out-of-fold para o Caminho F.
    """
    out_dir = Path(out_dir)
    pred_dir = out_dir / "predictions"
    pattern = f"{_safe_tag(run_id)}_{_safe_tag(caminho)}_*.parquet" if caminho else f"{_safe_tag(run_id)}_*.parquet"
    paths = sorted(pred_dir.glob(pattern))
    if not paths:
        raise FileNotFoundError(
            f"Nenhum parquet de predição encontrado em {pred_dir} para "
            f"run_id={run_id!r} caminho={caminho!r}."
        )
    return pd.concat([pd.read_parquet(p) for p in paths], ignore_index=True)
