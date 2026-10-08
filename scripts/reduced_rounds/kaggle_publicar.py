"""
Opera o Kaggle pela API para o piso com 10x os dados (caminhos B, C, D, F).

Subcomandos:
    dataset          sobe build/kaggle_piso/{codigo,dados} como dataset privado
                     (--versao para subir uma nova versão do código)
    notebook ALGO    gera o notebook de ALGO e o publica com GPU T4 (roda sozinho,
                     como "Save & Run All"); --retomar usa a saída da versão anterior
    status ALGO      estado da execução
    baixar ALGO      baixa a saída para build/reduced_rounds/floor_v2/kaggle/

Também regrava `kaggle_piso.ipynb` (a versão para uso manual).
Credencial: ~/.kaggle/access_token.

Uso:
    python scripts/reduced_rounds/kaggle_publicar.py dataset
    python scripts/reduced_rounds/kaggle_publicar.py notebook ascon
    python scripts/reduced_rounds/kaggle_publicar.py status ascon
    python scripts/reduced_rounds/kaggle_publicar.py baixar ascon
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BUNDLE = REPO_ROOT / "build" / "kaggle_piso"
STAGE = REPO_ROOT / "build" / "kaggle_stage"
USUARIO = "nycolaswenderson"
DATASET = "piso-rodadas-dados"
KAGGLE = str(Path(sys.executable).parent / "kaggle")


def _celulas(algos: list[str], retomar: bool, sem_meta: bool) -> list[dict]:
    def code(src: str) -> dict:
        return {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [],
                "source": src.strip("\n").splitlines(keepends=True)}

    md = {"cell_type": "markdown", "metadata": {}, "source": [
        "# Piso de rodadas: caminhos B, C, D e F com 10x os dados\n",
        "\n",
        "Gerado por `scripts/reduced_rounds/kaggle_publicar.py`. Para uso manual: suba\n",
        "`build/kaggle_piso` como Dataset, acelerador **GPU T4** (não P100), e rode com\n",
        "*Save & Run All*. Para retomar, adicione a saída da versão anterior como Input.\n"]}
    return [md, code(f"""
ALGOS = {algos!r}
LIMITE_HORAS = 11.0
EXTRA = {(['--sem-meta'] if sem_meta else [])!r}   # ['--sem-meta'] deixa o Meta_F de fora

import glob, os, shutil, subprocess, sys, time
T0 = time.time()
codigo = os.path.dirname(glob.glob('/kaggle/input/**/codigo/scripts', recursive=True)[0])
DADOS = os.path.dirname(glob.glob('/kaggle/input/**/ascon_texto_k3000.npz', recursive=True)[0])
print('código em', codigo, '| dados em', DADOS)
print(sorted(os.listdir(DADOS)))
subprocess.run(['nvidia-smi'])
import torch
assert torch.cuda.is_available(), 'sem GPU: ligar o acelerador T4'
gpu = torch.cuda.get_device_name(0)
assert 'P100' not in gpu, f'{{gpu}}: o PyTorch atual não roda na P100, trocar para T4'
print('GPU:', gpu, '| torch', torch.__version__)
"""), code("""
SAIDA = '/kaggle/working/piso'
for algo in ALGOS:
    ant = [p for p in glob.glob(f'/kaggle/input/**/{algo}_floor/feitos.txt', recursive=True)
           if not p.startswith(os.path.dirname(codigo))]
    if ant:
        origem = os.path.dirname(ant[0])
        shutil.copytree(origem, os.path.join(SAIDA, f'{algo}_floor'), dirs_exist_ok=True)
        print('retomando', algo, 'de', origem)
"""), code("""
runner = os.path.join(codigo, 'scripts', 'reduced_rounds', 'kaggle_piso.py')
for algo in ALGOS:
    resta = LIMITE_HORAS - (time.time() - T0) / 3600
    if resta < 0.5:
        print('sem tempo para', algo); continue
    # A saída do runner passa linha a linha pelo print do notebook: cada
    # RESULTADO fica no log no instante em que é calculado.
    proc = subprocess.Popen([sys.executable, '-u', runner, '--algo', algo, '--dados', DADOS,
                             '--saida', SAIDA, '--limite-horas', f'{resta:.2f}', *EXTRA],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    for linha in proc.stdout:
        print(linha, end='', flush=True)
    print('runner terminou com código', proc.wait(), flush=True)
"""), code("""
for algo in ALGOS:
    for nome in ('piso.csv', 'feitos.txt'):
        p = os.path.join(SAIDA, f'{algo}_floor', nome)
        if os.path.exists(p):
            print(f'==== {algo} {nome}'); print(open(p, encoding='utf-8').read())
""")]


def _notebook(algos: list[str], retomar: bool = False, sem_meta: bool = False) -> dict:
    return {"cells": _celulas(algos, retomar, sem_meta),
            "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python",
                                        "name": "python3"},
                         "language_info": {"name": "python"}},
            "nbformat": 4, "nbformat_minor": 5}


def _kaggle(*args: str) -> int:
    print("$ kaggle", " ".join(args), flush=True)
    return subprocess.run([KAGGLE, *args]).returncode


def _slug(algo: str) -> str:
    return f"piso-rodadas-{algo}"


def cmd_dataset(versao: bool) -> None:
    alvo = STAGE / "dataset"
    if alvo.exists():
        shutil.rmtree(alvo)
    alvo.mkdir(parents=True)
    # dados_x100: caches da curva para o kaggle_100x.py (criar um dataset
    # próprio para eles falhou duas vezes com erro 500 do Kaggle)
    for sub in ("codigo", "dados", "dados_x100"):
        if (BUNDLE / sub).exists():
            shutil.copytree(BUNDLE / sub, alvo / sub, ignore=shutil.ignore_patterns("__pycache__"))
    (alvo / "dataset-metadata.json").write_text(json.dumps({
        "title": "piso-rodadas-dados", "id": f"{USUARIO}/{DATASET}",
        "licenses": [{"name": "CC0-1.0"}]}, indent=2), encoding="utf-8")
    if versao:
        rc = _kaggle("datasets", "version", "-p", str(alvo), "-m", "código atualizado",
                     "--dir-mode", "zip")
    else:
        rc = _kaggle("datasets", "create", "-p", str(alvo), "--dir-mode", "zip")
    sys.exit(rc)


def cmd_notebook(algo: str, retomar: bool, sem_meta: bool) -> None:
    alvo = STAGE / _slug(algo)
    if alvo.exists():
        shutil.rmtree(alvo)
    alvo.mkdir(parents=True)
    (alvo / "piso.ipynb").write_text(json.dumps(_notebook([algo], retomar, sem_meta), indent=1,
                                                ensure_ascii=False), encoding="utf-8")
    fontes = [f"{USUARIO}/{_slug(algo)}"] if retomar else []
    (alvo / "kernel-metadata.json").write_text(json.dumps({
        "id": f"{USUARIO}/{_slug(algo)}", "title": _slug(algo), "code_file": "piso.ipynb",
        "language": "python", "kernel_type": "notebook", "is_private": True,
        "enable_gpu": True, "enable_internet": False, "machine_shape": "NvidiaTeslaT4",
        "dataset_sources": [f"{USUARIO}/{DATASET}"], "kernel_sources": fontes,
        "competition_sources": []}, indent=2), encoding="utf-8")
    sys.exit(_kaggle("kernels", "push", "-p", str(alvo), "--accelerator", "NvidiaTeslaT4"))


def cmd_coletar(algo: str) -> None:
    """Lê o log AO VIVO (funciona com a execução em andamento) e guarda aqui as
    linhas RESULTADO e FEITO, sem depender da saída salva pelo Kaggle. Pode
    rodar quantas vezes quiser: o log bruto vai com carimbo de hora e o
    resultados.jsonl é deduplicado."""
    import time

    destino = REPO_ROOT / "build" / "reduced_rounds" / "floor_v2" / "kaggle" / "coleta"
    destino.mkdir(parents=True, exist_ok=True)
    # Sem -f a API só devolve o log de sessões encerradas; com -f ela manda o
    # histórico inteiro da sessão em andamento e fica seguindo. Corta-se a
    # transmissão depois de alguns segundos e fica-se com o que chegou.
    try:
        r = subprocess.run([KAGGLE, "kernels", "logs", "-f", f"{USUARIO}/{_slug(algo)}"],
                           capture_output=True, text=True, encoding="utf-8", timeout=60)
        bruto = r.stdout
    except subprocess.TimeoutExpired as e:
        bruto = e.stdout.decode("utf-8", "replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
    if not bruto.strip():
        r = subprocess.run([KAGGLE, "kernels", "logs", f"{USUARIO}/{_slug(algo)}"],
                           capture_output=True, text=True, encoding="utf-8")
        bruto = r.stdout
    (destino / f"{algo}_log_{time.strftime('%Y%m%d_%H%M%S')}.txt").write_text(bruto, encoding="utf-8")
    try:
        texto = "".join(e.get("data", "") for e in json.loads(bruto))
    except json.JSONDecodeError:
        texto = bruto
    linhas = texto.splitlines()
    res = [ln[len("RESULTADO "):] for ln in linhas if ln.startswith("RESULTADO ")]
    feitos = [ln for ln in linhas if ln.startswith("FEITO ")]
    jl = destino / f"{algo}_resultados.jsonl"
    antigos = set(jl.read_text(encoding="utf-8").splitlines()) if jl.exists() else set()
    novos = [x for x in res if x not in antigos]
    with jl.open("a", encoding="utf-8") as f:
        for x in novos:
            f.write(x + "\n")
    fp = destino / f"{algo}_feitos.txt"
    antigos_f = set(fp.read_text(encoding="utf-8").splitlines()) if fp.exists() else set()
    with fp.open("a", encoding="utf-8") as f:
        for x in feitos:
            if x not in antigos_f:
                f.write(x + "\n")
                antigos_f.add(x)
    erros = [ln for ln in linhas if "Traceback" in ln or "Error" in ln]
    print(f"{algo}: {len(res)} RESULTADO no log ({len(novos)} novos), {len(feitos)} células feitas"
          + (f", {len(erros)} linha(s) de erro" if erros else ""))
    for ln in feitos[-3:]:
        print("  ", ln)
    for ln in erros[-3:]:
        print("  ERRO:", ln[:200])


def cmd_x100(algo: str, rounds: list[int], so_notebook: bool) -> None:
    """Redes com 100x os dados (kaggle_100x.py): sobe os caches da curva de
    orçamento como dataset próprio e dispara o notebook."""
    ds = f"piso-rodadas-x100-{algo}"
    slug = f"piso-rodadas-x100-{algo}"
    if not so_notebook:
        alvo = STAGE / ds
        if alvo.exists():
            shutil.rmtree(alvo)
        (alvo / "dados").mkdir(parents=True)
        shutil.copytree(BUNDLE / "codigo", alvo / "codigo", ignore=shutil.ignore_patterns("__pycache__"))
        curva = REPO_ROOT / "build" / "reduced_rounds" / "floor_v2" / "curva_orcamento"
        for arm in ("texto", "aleatorio"):
            shutil.copy2(curva / f"{algo}_{arm}_dev31000.npz", alvo / "dados")
        (alvo / "dataset-metadata.json").write_text(json.dumps({
            "title": ds, "id": f"{USUARIO}/{ds}", "licenses": [{"name": "CC0-1.0"}]}, indent=2),
            encoding="utf-8")
        rc = _kaggle("datasets", "create", "-p", str(alvo), "--dir-mode", "zip")
        if rc:
            sys.exit(rc)
        print("dataset enviado; rode de novo com --so-notebook quando o Kaggle terminar de processar")
        return
    def code(src):
        return {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [],
                "source": src.strip("\n").splitlines(keepends=True)}
    nb ={"cells": [code(f"""
import glob, os, subprocess, sys
codigo = os.path.dirname(glob.glob('/kaggle/input/**/codigo/scripts', recursive=True)[0])
DADOS = os.path.dirname(glob.glob('/kaggle/input/**/{algo}_texto_dev31000.npz', recursive=True)[0])
print('código em', codigo, '| dados em', DADOS)
import torch
assert torch.cuda.is_available(), 'sem GPU'
gpu = torch.cuda.get_device_name(0)
assert 'P100' not in gpu, gpu
print('GPU:', gpu)
script = os.path.join(codigo, 'scripts', 'reduced_rounds', 'kaggle_100x.py')
proc = subprocess.Popen([sys.executable, '-u', script, '--algo', '{algo}', '--rounds',
                         {", ".join(repr(str(r)) for r in rounds)}, '--dados', DADOS,
                         '--saida', '/kaggle/working/x100'],
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
for linha in proc.stdout:
    print(linha, end='', flush=True)
print('terminou com código', proc.wait(), flush=True)
""")], "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                     "language_info": {"name": "python"}}, "nbformat": 4, "nbformat_minor": 5}
    alvo = STAGE / slug
    if alvo.exists():
        shutil.rmtree(alvo)
    alvo.mkdir(parents=True)
    (alvo / "x100.ipynb").write_text(json.dumps(nb, indent=1, ensure_ascii=False), encoding="utf-8")
    (alvo / "kernel-metadata.json").write_text(json.dumps({
        "id": f"{USUARIO}/{slug}", "title": slug, "code_file": "x100.ipynb",
        "language": "python", "kernel_type": "notebook", "is_private": True,
        "enable_gpu": True, "enable_internet": False, "machine_shape": "NvidiaTeslaT4",
        "dataset_sources": [f"{USUARIO}/{DATASET}"], "kernel_sources": [],
        "competition_sources": []}, indent=2), encoding="utf-8")
    sys.exit(_kaggle("kernels", "push", "-p", str(alvo), "--accelerator", "NvidiaTeslaT4"))


def cmd_piso(algo: str) -> None:
    """Piso a partir das linhas RESULTADO coletadas do log, sem depender da
    saída salva pelo Kaggle (que já veio incompleta). Remonta o
    `*_metrics.jsonl` que o `report_floor.py` lê e roda o relatório."""
    sys.path.insert(0, str(REPO_ROOT))
    from scripts.reduced_rounds.floor_algos import ALGOS

    spec = ALGOS[algo]
    coleta = REPO_ROOT / "build" / "reduced_rounds" / "floor_v2" / "kaggle" / "coleta"
    rep = coleta / f"{algo}_reports"
    rep.mkdir(parents=True, exist_ok=True)
    n = 0
    with (rep / f"{algo}_metrics.jsonl").open("w", encoding="utf-8") as f:
        for linha in (coleta / f"{algo}_resultados.jsonl").read_text(encoding="utf-8").splitlines():
            d = json.loads(linha)
            if d["fold"] != "final":
                continue
            f.write(json.dumps(dict(
                fold="final", modelo=d["modelo"], f1_macro=d["f1"], f1_macro_ci_lower=d["f1_lo"],
                f1_macro_ci_upper=d["f1_hi"], auc_roc=d["auc"], n_samples=d["n"],
                extra=dict(arm=d["arm"], rounds=d["rounds"], politica="ambos", algo=algo,
                           rounds_spec=spec.max_rounds, unidade=spec.unidade, runner="run_floor",
                           seed_gen_runner=999004, pares_por_decisao=d["bolsa"])),
                ensure_ascii=False) + "\n")
            n += 1
    print(f"{algo}: {n} métricas remontadas do log -> {rep}")
    sys.exit(subprocess.run([sys.executable, str(REPO_ROOT / "scripts" / "reduced_rounds" / "report_floor.py"),
                             "--dir", str(rep), "--csv", str(coleta / f"{algo}_piso.csv")]).returncode)


def _status(algo: str) -> str:
    r = subprocess.run([KAGGLE, "kernels", "status", f"{USUARIO}/{_slug(algo)}"],
                       capture_output=True, text=True, encoding="utf-8")
    s = (r.stdout + r.stderr).strip().splitlines()
    return s[-1] if s else "?"


def cmd_vigiar(ativos: list[str], fila: list[str], intervalo_min: float, sem_meta: bool) -> None:
    """Coleta os logs a cada `intervalo_min`; quando uma sessão termina, coleta
    o log final, baixa a saída e dispara o próximo algoritmo da fila."""
    import time

    ativos, fila = list(ativos), list(fila)
    while ativos:
        for algo in list(ativos):
            try:
                cmd_coletar(algo)
            except Exception as e:  # coleta falhar não pode derrubar o vigia
                print(f"{algo}: coleta falhou: {e}", flush=True)
            st = _status(algo)
            print(f"[{time.strftime('%H:%M')}] {algo}: {st}", flush=True)
            if "RUNNING" in st or "QUEUED" in st:
                continue
            ativos.remove(algo)
            try:
                cmd_coletar(algo)
                destino = REPO_ROOT / "build" / "reduced_rounds" / "floor_v2" / "kaggle" / algo
                destino.mkdir(parents=True, exist_ok=True)
                _kaggle("kernels", "output", f"{USUARIO}/{_slug(algo)}", "-p", str(destino), "-o")
            except Exception as e:
                print(f"{algo}: baixar saída falhou: {e}", flush=True)
            if fila:
                prox = fila.pop(0)
                try:
                    cmd_notebook(prox, False, sem_meta)
                except SystemExit:
                    pass
                ativos.append(prox)
                print(f"disparado {prox}", flush=True)
        if ativos:
            time.sleep(intervalo_min * 60)
    print("vigia: nada mais rodando", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("acao", choices=["dataset", "notebook", "status", "baixar", "coletar", "vigiar", "piso", "x100"])
    ap.add_argument("algo", nargs="?")
    ap.add_argument("--versao", action="store_true")
    ap.add_argument("--retomar", action="store_true")
    ap.add_argument("--sem-meta", action="store_true", help="deixa o Meta_F (caminho F) de fora")
    ap.add_argument("--ativos", nargs="*", default=[], help="vigiar: sessões já rodando")
    ap.add_argument("--fila", nargs="*", default=[], help="vigiar: algoritmos a disparar em seguida")
    ap.add_argument("--intervalo", type=float, default=20.0, help="vigiar: minutos entre coletas")
    ap.add_argument("--rounds", nargs="+", type=int, default=[3, 4], help="x100: rodadas")
    ap.add_argument("--so-notebook", action="store_true", help="x100: só dispara o notebook")
    a = ap.parse_args()

    (REPO_ROOT / "scripts" / "reduced_rounds" / "kaggle_piso.ipynb").write_text(
        json.dumps(_notebook(["ascon"]), indent=1, ensure_ascii=False), encoding="utf-8")

    if a.acao == "dataset":
        cmd_dataset(a.versao)
    if a.acao == "vigiar":
        cmd_vigiar(a.ativos, a.fila, a.intervalo, a.sem_meta)
        return
    if not a.algo:
        ap.error("informe o algoritmo")
    if a.acao == "notebook":
        cmd_notebook(a.algo, a.retomar, a.sem_meta)
    elif a.acao == "x100":
        cmd_x100(a.algo, a.rounds, a.so_notebook)
    elif a.acao == "piso":
        cmd_piso(a.algo)
    elif a.acao == "coletar":
        cmd_coletar(a.algo)
    elif a.acao == "status":
        sys.exit(_kaggle("kernels", "status", f"{USUARIO}/{_slug(a.algo)}"))
    else:
        destino = REPO_ROOT / "build" / "reduced_rounds" / "floor_v2" / "kaggle" / a.algo
        destino.mkdir(parents=True, exist_ok=True)
        sys.exit(_kaggle("kernels", "output", f"{USUARIO}/{_slug(a.algo)}", "-p", str(destino), "-o"))


if __name__ == "__main__":
    main()
