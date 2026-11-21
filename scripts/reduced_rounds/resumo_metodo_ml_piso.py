"""Compara, na rodada do piso, o F1 e a AUC da configuração padrão com os da
configuração escolhida pela busca de hiperparâmetros feita na própria rodada do
piso (metodo_ml.py --celula-selecao piso).

    python scripts/reduced_rounds/resumo_metodo_ml_piso.py
"""
from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
B = RAIZ / "build" / "reduced_rounds" / "floor_v2"
PISO = {"ascon": 3, "gift": 3, "schwaemm": 2}
PAR = {"LogisticRegression": "LogReg_ajustada", "RandomForest": "RandomForest_ajustada",
       "XGBoost": "XGBoost_ajustado", None: "SVM_RBF_ajustado"}


def _csv(pasta: Path) -> list[dict]:
    saida = pasta / "piso.csv"
    if not saida.exists():
        subprocess.run([sys.executable, str(RAIZ / "scripts" / "reduced_rounds" / "report_floor.py"),
                        "--dir", str(pasta / "reports"), "--csv", str(saida)],
                       capture_output=True, check=False)
    return list(csv.DictReader(open(saida, encoding="utf-8"))) if saida.exists() else []


def _celula(rows, modelo, r, bolsa):
    for x in rows:
        if x["arm"] == "texto-en" and x["modelo"] == modelo and x["rounds"] == str(r) and x["bolsa"] == bolsa:
            return x
    return None


def main() -> None:
    linhas = []
    for algo, r in PISO.items():
        padrao = _csv(B / "contador_zero_corpus_en" / f"{algo}_floor")
        ajust = _csv(B / "metodo_ml_piso" / f"{algo}_floor")
        linhas.append(f"== {algo} (rodada do piso: {r})")
        for orig, novo in PAR.items():
            for bolsa in ("1", "100"):
                p = _celula(padrao, orig, r, bolsa) if orig else None
                a = _celula(ajust, novo, r, bolsa)
                fp = f"{float(p['f1_macro']):.3f} / AUC {float(p['auc']):.3f}" if p else "-"
                fa = (f"{float(a['f1_macro']):.3f} / AUC {float(a['auc']):.3f} "
                      f"(detectado={a['detectado']})") if a else "pendente"
                linhas.append(f"  {novo:24s} bolsa {bolsa:>3}: padrão {fp:22s} | ajustado {fa}")
        # a rodada seguinte, para confirmar que o ajuste no piso não cria detecção acima
        for novo in PAR.values():
            a = _celula(ajust, novo, r + 1, "1")
            if a:
                linhas.append(f"  {novo:24s} rodada {r + 1}, bolsa 1: F1 {float(a['f1_macro']):.3f} "
                              f"/ AUC {float(a['auc']):.3f} (detectado={a['detectado']})")
    texto = "\n".join(linhas)
    (B / "metodo_ml_piso_resumo.txt").write_text(texto + "\n", encoding="utf-8")
    print(texto)


if __name__ == "__main__":
    main()
