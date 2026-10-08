"""
Runner do piso no Kaggle: os caminhos B, C, D e F (mais ResNet e MLP) com 10x
os dados das rodadas anteriores.

Pergunta: com modelos que combinam bits (CNN 2D, híbrido, empilhamento) e 10x
mais criptogramas, a rodada seguinte ao piso aparece? A curva de orçamento já
mostrou que, para detectores de bits independentes, nem 100x faz aparecer.

Desenho (o mesmo do `run_floor.py`, que é quem roda cada célula):
- contador zero, representação XOR, 3.000 dispositivos x 100 pares,
  key-holdout 2.400 / 600 (80/20), bolsas de 1, 10 e 100 pares;
- rodadas: o piso + 1 (a pergunta), o piso (tem que detectar), a rodada 1 e a
  especificação completa (controles da regra de monotonicidade e da faixa de
  controle); braços texto e aleatório (o aleatório é nulo provado);
- os dados vêm prontos (`exportar_kaggle.py`): nenhuma cifra roda aqui.

Ordem de prioridade: primeiro as redes e o híbrido em todas as células, com a
rodada seguinte ao piso na frente; o Meta_F (o mais caro: treina seis modelos
quatro vezes) fica por último. Cada célula concluída vai para `feitos.txt`:
rodar de novo com a mesma pasta de saída retoma de onde parou. Antes de cada
célula, se o tempo gasto mais a duração da última célula do mesmo modelo
passar do limite, o runner para e deixa o resto para a próxima sessão.

Uso no Kaggle (ver notebook `kaggle_piso.ipynb`):
    python codigo/scripts/reduced_rounds/kaggle_piso.py --algo ascon \\
        --dados /kaggle/input/<dataset>/dados --saida /kaggle/working/piso
Local, simulando o Kaggle (sem binários de cifra, 20 chaves):
    python scripts/reduced_rounds/kaggle_piso.py --algo ascon --smoke --sem-binarios
"""
from __future__ import annotations

import argparse
import importlib
import os
import subprocess
import sys
import time
import types
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src" / "crypto"))

PISOS = {"ascon": 3, "gift": 3, "grain": 28, "schwaemm": 2}
MODELOS = ["ResNet_Gohr", "MLP_Shen", "CNN1D_bytes", "CNN2D_bits", "Hibrido_D"]
MODELO_CARO = "Meta_F"
BRACOS = ("texto", "aleatorio")
N_KEYS, N_TEST = 3_000, 600


class _Ausente:
    """Lugar de um objeto que só existe com os binários de cifra."""

    def __init__(self, nome: str) -> None:
        self._nome = nome

    def __call__(self, *a, **k):
        raise RuntimeError(f"{self._nome} não existe neste ambiente (sem binários de cifra). "
                           "O cache deveria trazer todas as rodadas pedidas.")

    def __getattr__(self, attr: str):
        if attr.startswith("__"):
            raise AttributeError(attr)
        return _Ausente(f"{self._nome}.{attr}")


def _substituir(nome: str) -> None:
    m = types.ModuleType(nome)

    def __getattr__(attr: str):  # PEP 562
        # Atributos internos (__file__, __path__...) têm que faltar de verdade:
        # o torch e o inspect sondam todos os módulos carregados.
        if attr.startswith("__"):
            raise AttributeError(attr)
        return _Ausente(f"{nome}.{attr}")

    m.__getattr__ = __getattr__
    sys.modules[nome] = m


def preparar_ambiente(forcar: bool) -> list[str]:
    """No Linux do Kaggle não há os .pyd das cifras nem o `nistrng`, que só
    servem para gerar dados e extrair features. Os módulos que os importam no
    carregamento são trocados por substitutos que falham se forem USADOS."""
    trocados = []
    for w in ("ascon_wrapper", "gift_cofb_wrapper", "grain_wrapper", "sparkle_wrapper",
              "aes_ecb_wrapper"):
        nome = f"src.crypto.{w}"
        try:
            if forcar:
                raise ImportError
            importlib.import_module(nome)
        except Exception:
            _substituir(nome)
            trocados.append(nome)
    try:
        if forcar:
            raise ImportError
        importlib.import_module("nistrng")
    except Exception:
        _substituir("src.features.families.nist_sts")
        trocados.append("src.features.families.nist_sts")
    return trocados


def tarefas(algo: str, spec_rounds: int) -> list[tuple[int, str, str]]:
    piso = PISOS[algo]
    rodadas = [piso + 1, piso, 1, spec_rounds]
    jobs = [(r, arm, m) for r in rodadas for arm in BRACOS for m in MODELOS]
    jobs += [(r, arm, MODELO_CARO) for r in rodadas for arm in BRACOS]
    return jobs


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--algo", required=True, choices=sorted(PISOS))
    ap.add_argument("--dados", type=Path, default=REPO_ROOT / "build" / "kaggle_piso" / "dados")
    ap.add_argument("--saida", type=Path, default=None)
    ap.add_argument("--limite-horas", type=float, default=11.0,
                    help="não começa uma célula que provavelmente passaria disto (Kaggle: 12 h)")
    ap.add_argument("--sem-meta", action="store_true", help="pula o Meta_F")
    ap.add_argument("--sem-binarios", action="store_true",
                    help="força os substitutos, para testar localmente o caminho do Kaggle")
    ap.add_argument("--smoke", action="store_true", help="20 chaves (4 de teste), saída separada")
    a = ap.parse_args()

    saida = a.saida or (REPO_ROOT / "build" / "reduced_rounds" / "floor_v2" / "kaggle"
                        / ("smoke" if a.smoke else ""))
    os.environ["PISO_OUT_ROOT"] = str(saida)
    trocados = preparar_ambiente(a.sem_binarios)

    import numpy as np
    import torch

    from scripts.reduced_rounds import run_floor as rf
    from scripts.reduced_rounds.floor_algos import ALGOS
    from scripts.reduced_rounds.neural_floor import DISPOSITIVO

    # Cada métrica sai numa linha RESULTADO no instante em que é calculada: no
    # Kaggle a pasta de saída nem sempre é salva, e o log é lido ao vivo
    # (`kaggle kernels logs`). Não depender do disco para não perder resultado.
    import json as _json
    _report_eval = rf.report_eval

    def _report_eval_com_print(**kw):
        rep = _report_eval(**kw)
        d = rep.as_dict()
        auc = d.get("auc_roc")
        extra = kw.get("extra") or {}
        print("RESULTADO " + _json.dumps(dict(
            algo=a.algo, run_id=kw["run_id"], modelo=kw["modelo"], fold=kw["fold"],
            arm=extra.get("arm"), rounds=extra.get("rounds"),
            bolsa=extra.get("pares_por_decisao", 1), n=len(kw["y_true"]),
            f1=d.get("f1_macro"), f1_lo=d.get("f1_macro_ci_lower"), f1_hi=d.get("f1_macro_ci_upper"),
            auc=auc.get("auc") if isinstance(auc, dict) else auc,
            fit_s=extra.get("fit_seconds")), ensure_ascii=False, default=float), flush=True)
        return rep

    rf.report_eval = _report_eval_com_print

    rf._log(f"python {sys.version.split()[0]} | torch {torch.__version__} | dispositivo {DISPOSITIVO}"
            + (f" ({torch.cuda.get_device_name(0)})" if DISPOSITIVO == "cuda" else ""))
    if trocados:
        rf._log(f"substitutos (sem binários): {trocados}")

    spec = ALGOS[a.algo]
    jobs = tarefas(a.algo, spec.max_rounds)
    if a.sem_meta:
        jobs = [j for j in jobs if j[2] != MODELO_CARO]
    rodadas = sorted({r for r, _, _ in jobs})
    n_keys, n_test = (20, 4) if a.smoke else (N_KEYS, N_TEST)

    base = saida / f"{a.algo}_floor"
    report_dir = base / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    feitos_path = base / "feitos.txt"
    feitos = set()
    if feitos_path.exists():
        feitos = {ln.split("\t")[0] for ln in feitos_path.read_text(encoding="utf-8").splitlines() if ln}

    data = {}
    for arm in BRACOS:
        d = rf.generate(a.algo, arm, N_KEYS, rodadas, a.dados / f"{a.algo}_{arm}_k{N_KEYS}.npz",
                        "ambos", contador="zero")
        if a.smoke:
            n = n_keys * rf.PAIRS_PER_KEY
            d = {k: (v[:n] if isinstance(v, np.ndarray) and v.ndim and len(v) == N_KEYS * rf.PAIRS_PER_KEY
                     else v) for k, v in d.items()}
        data[arm] = d

    rf._log(f"{a.algo}: {len(jobs)} células, {len(feitos)} já feitas, limite {a.limite_horas} h "
            f"-> {base}")
    t0 = time.time()
    # Estimativa antes da primeira medição: uma célula do Meta_F morta pelo
    # limite do Kaggle perde horas, então a estimativa inicial é pessimista.
    duracao: dict[str, float] = {m: 1800.0 for m in MODELOS} | {MODELO_CARO: 3 * 3600.0}
    pendentes = 0
    for r, arm, modelo in jobs:
        chave = f"{arm} r{r} {modelo}"
        if chave in feitos:
            continue
        gasto = time.time() - t0
        if gasto + duracao.get(modelo, 0.0) > a.limite_horas * 3600:
            pendentes += 1
            continue
        rf._log(f"######## {a.algo} {chave} (decorrido {gasto / 3600:.2f} h)")
        t = time.time()
        rf.run_config(a.algo, arm, r, data[arm], n_keys, n_test, 5, report_dir, "sweep",
                      [modelo], "ambos", "zero", "xor")
        duracao[modelo] = time.time() - t
        with feitos_path.open("a", encoding="utf-8") as f:
            f.write(f"{chave}\t{duracao[modelo]:.0f}s\n")
        print(f"FEITO {a.algo}\t{chave}\t{duracao[modelo]:.0f}s", flush=True)
        if DISPOSITIVO == "cuda":
            torch.cuda.empty_cache()

    if pendentes:
        rf._log(f"PARADO PELO LIMITE: {pendentes} célula(s) pendentes. Rode de novo com a mesma "
                "pasta de saída (feitos.txt) para continuar.")
    else:
        rf._log("todas as células concluídas")
    subprocess.run([sys.executable, str(REPO_ROOT / "scripts" / "reduced_rounds" / "report_floor.py"),
                    "--dir", str(report_dir), "--csv", str(base / "piso.csv")], check=False)
    rf._log("fim")


if __name__ == "__main__":
    main()
