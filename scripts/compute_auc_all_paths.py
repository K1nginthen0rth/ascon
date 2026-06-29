"""
Calcula AUC-ROC para os modelos de cada um dos 4 caminhos experimentais
e consolida os resultados em uma tabela markdown.

Estrutura real dos arquivos `_final_cache*.pkl` (inspecionada antes de
escrever este script): cada arquivo contem uma tupla
(predictions, final_data), onde:
  - predictions[model_name] = {"y_pred", "y_proba", "confusion_matrix"}
  - final_data["y_true"], final_data["label_map"], final_data["model_metrics"]

`model_metrics[model_name]` ja contem o dict as_dict() de MetricsReport
(f1_macro etc.), usado aqui apenas para contexto na tabela final.

Caminhos esperados (conforme run_experiment_60k_cv.py):
  A: reports/keyholdout_2class_60k_v1_cv/_final_cache.pkl
  B: reports/keyholdout_2class_60k_v1_cnn/_final_cache_cnn1d.pkl
  C: reports/keyholdout_2class_60k_v1_cnn/_final_cache_cnn2d.pkl
  D: reports/keyholdout_2class_60k_v1_hybrid/_final_cache.pkl

Se um arquivo nao existir no caminho esperado, o script tenta localizar
pelo nome real (busca por "_final_cache*.pkl" em reports/) e documenta
no relatorio final qual caminho foi de fato usado ou se o caminho
permanece pendente (sem cache disponivel).
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

from src.eval.metrics import compute_auc_roc

PATHS_ESPERADOS = {
    "A (Classico 307D)":  _REPO / "reports" / "keyholdout_2class_60k_v1_cv"     / "_final_cache.pkl",
    "B (CNN1D latente)":  _REPO / "reports" / "keyholdout_2class_60k_v1_cnn"    / "_final_cache_cnn1d.pkl",
    "C (CNN2D latente)":  _REPO / "reports" / "keyholdout_2class_60k_v1_cnn"    / "_final_cache_cnn2d.pkl",
    "D (Hibrido)":        _REPO / "reports" / "keyholdout_2class_60k_v1_hybrid" / "_final_cache.pkl",
}

OUT_MD = _REPO / "reports" / "AUC_ROC_consolidado.md"


def _localizar_caches_reais() -> dict:
    """Busca todos os _final_cache*.pkl existentes em reports/ (fallback)."""
    return {p.relative_to(_REPO).as_posix(): p for p in (_REPO / "reports").rglob("_final_cache*.pkl")}


def _processar_cache(caminho_nome: str, pkl_path: Path) -> list[dict]:
    """Extrai AUC + F1 de cada modelo dentro de um cache de caminho experimental."""
    with open(pkl_path, "rb") as f:
        obj = pickle.load(f)

    # Formato observado: tupla (predictions, final_data)
    predictions, final_data = obj
    y_true        = final_data["y_true"]
    model_metrics = final_data.get("model_metrics", {})

    linhas = []
    for model_name, pred in predictions.items():
        y_proba = pred.get("y_proba")
        auc_info = compute_auc_roc(y_true, y_proba)
        auc = auc_info["auc"] if auc_info is not None else None
        f1  = model_metrics.get(model_name, {}).get("f1_macro")
        linhas.append({
            "caminho": caminho_nome,
            "modelo":  model_name,
            "auc":     auc,
            "f1":      f1,
        })
    return linhas


def main() -> None:
    print(f"\n{'='*60}\n  AUC-ROC consolidado - 4 caminhos experimentais\n{'='*60}")

    caches_reais = _localizar_caches_reais()
    print(f"  Caches encontrados em reports/: {list(caches_reais.keys())}")

    todas_linhas: list[dict] = []
    notas: list[str] = []

    for caminho_nome, path_esperado in PATHS_ESPERADOS.items():
        if path_esperado.exists():
            usado = path_esperado
            nota = None
        else:
            # fallback: busca _final_cache*.pkl APENAS dentro do mesmo
            # diretorio do caminho esperado (evita casar com caches de
            # outros datasets, ex.: control_vigenere, que tambem se
            # chamam "_final_cache.pkl" mas pertencem a outro experimento)
            candidatos = [
                p for nome, p in caches_reais.items()
                if p.parent == path_esperado.parent
            ]
            if candidatos:
                usado = candidatos[0]
                nota = (f"{caminho_nome}: arquivo esperado nao encontrado em "
                        f"{path_esperado.relative_to(_REPO)}; usando {usado.relative_to(_REPO)} encontrado por busca.")
            else:
                usado = None
                nota = (f"{caminho_nome}: PENDENTE - nenhum _final_cache*.pkl encontrado "
                        f"(esperado em {path_esperado.relative_to(_REPO)}). "
                        f"Modelo provavelmente ainda nao foi treinado.")
        if nota:
            print(f"  ! {nota}")
            notas.append(nota)
        if usado is None:
            continue
        print(f"  Processando {caminho_nome}: {usado.relative_to(_REPO)}")
        linhas = _processar_cache(caminho_nome, usado)
        todas_linhas.extend(linhas)

    # --- tabela markdown ---
    header = "| Caminho | Modelo | AUC | F1 |\n|---|---|---|---|\n"
    rows = ""
    for r in todas_linhas:
        auc_str = f"{r['auc']:.4f}" if r["auc"] is not None else "N/A"
        f1_str  = f"{r['f1']:.4f}"  if r["f1"]  is not None else "N/A"
        rows += f"| {r['caminho']} | {r['modelo']} | {auc_str} | {f1_str} |\n"

    notas_md = ""
    if notas:
        notas_md = "\n## Notas\n\n" + "\n".join(f"- {n}" for n in notas) + "\n"

    conteudo = (
        "# AUC-ROC consolidado - 4 caminhos experimentais\n\n"
        f"{header}{rows}"
        f"{notas_md}"
    )
    OUT_MD.write_text(conteudo, encoding="utf-8")

    print(f"\n{'='*60}\n  TABELA FINAL\n{'='*60}")
    print(header + rows)
    if notas:
        print("Notas:")
        for n in notas:
            print(f"  - {n}")
    print(f"\n  Relatorio salvo em: {OUT_MD.relative_to(_REPO)}")


if __name__ == "__main__":
    main()
