"""Consolida o estudo principal repetido com 5 sementes (dados, separação e
modelos) e validação cruzada de 5 dobras por chave.

Para cada semente e algoritmo: o piso pelo critério de sempre (report_floor.py,
que usa só o teste final), e, a partir das linhas de dobra dos _metrics.jsonl,
a média e o desvio do F1 e da AUC por par nas 5 dobras, na rodada do piso e na
seguinte. No fim, o resumo entre sementes.

    python scripts/reduced_rounds/consolidar_sementes.py
"""
from __future__ import annotations

import csv
import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parents[2]
B = RAIZ / "build" / "reduced_rounds" / "floor_v2"
SEMENTES = range(5)
PISO_PRINCIPAL = {"ascon": 3, "gift": 3, "schwaemm": 2}


def _piso_csv(pasta: Path) -> list[dict]:
    saida = pasta / "piso.csv"
    subprocess.run([sys.executable, str(RAIZ / "scripts" / "reduced_rounds" / "report_floor.py"),
                    "--dir", str(pasta / "reports"), "--csv", str(saida)], capture_output=True, check=False)
    return list(csv.DictReader(open(saida, encoding="utf-8"))) if saida.exists() else []


def _piso(rows: list[dict], arm: str) -> int:
    det = defaultdict(bool)
    for r in rows:
        if r["arm"] == arm:
            det[int(r["rounds"])] |= r["detectado"] == "True"
    piso = 0
    for rr in sorted(det):
        if rr == piso + 1 and det[rr]:
            piso = rr
        elif rr > piso:
            break
    return piso


def _dobras(pasta: Path, arm: str, rodada: int) -> dict:
    """F1 e AUC por par (sem bolsa) em cada dobra, por modelo."""
    f = pasta / "reports" / f"floor_{pasta.name.split('_')[0]}_{arm}_r{rodada}_metrics.jsonl"
    out = defaultdict(lambda: {"f1": [], "auc": []})
    if not f.exists():
        return out
    for linha in open(f, encoding="utf-8"):
        d = json.loads(linha)
        if str(d.get("fold")) == "final" or (d.get("extra") or {}).get("nivel") == "bolsa":
            continue
        if re.search(r"_bag\d+$", d.get("modelo", "")):
            continue
        auc = d.get("auc_roc")
        out[d["modelo"]]["f1"].append(d["f1_macro"])
        out[d["modelo"]]["auc"].append(auc.get("auc") if isinstance(auc, dict) else auc)
    return out


def main() -> None:
    linhas, pisos = [], defaultdict(list)
    for s in SEMENTES:
        for algo, p0 in PISO_PRINCIPAL.items():
            pasta = B / f"contador_zero_corpus_en_s{s}" / f"{algo}_floor"
            if not (pasta / "reports").exists():
                linhas.append(f"s{s} {algo}: pendente")
                continue
            rows = _piso_csv(pasta)
            pt, pa = _piso(rows, "texto-en"), _piso(rows, "aleatorio")
            pisos[algo].append(pt)
            txt = [f"s{s} {algo}: piso texto {pt}, aleatório {pa}"]
            for rr in (p0, p0 + 1):
                for mod, v in sorted(_dobras(pasta, "texto-en", rr).items()):
                    if v["f1"]:
                        txt.append(f"    r{rr} {mod:18s} dobras={len(v['f1'])} "
                                   f"F1 {np.mean(v['f1']):.3f} ± {np.std(v['f1'], ddof=1) if len(v['f1']) > 1 else 0:.3f} | "
                                   f"AUC {np.mean(v['auc']):.3f} ± {np.std(v['auc'], ddof=1) if len(v['auc']) > 1 else 0:.3f}")
            linhas.extend(txt)
    linhas.append("== entre sementes (piso no braço de texto)")
    for algo, v in pisos.items():
        linhas.append(f"  {algo}: {v} (mín {min(v)}, máx {max(v)})")
    texto = "\n".join(linhas)
    (B / "sementes_resumo.txt").write_text(texto + "\n", encoding="utf-8")
    print(texto)


if __name__ == "__main__":
    main()
