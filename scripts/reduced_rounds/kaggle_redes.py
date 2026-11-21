"""
Dispara no Kaggle (GPU T4) o metodo_redes.py: um notebook por modo, com a
saída linha a linha no log (as linhas RESULTADO são coletadas ao vivo por
`kaggle_publicar.py coletar redes-piso|redes-gift4`).

Uso:
    python scripts/reduced_rounds/kaggle_redes.py piso
    python scripts/reduced_rounds/kaggle_redes.py gift4
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
STAGE = REPO_ROOT / "build" / "kaggle_stage"
USUARIO, DATASET = "nycolaswenderson", "piso-rodadas-dados"
KAGGLE = str(Path(sys.executable).parent / "kaggle")

CMD = {
    "piso": "['piso', '--dados', os.path.join(DADOS, 'piso'), '--saida', '/kaggle/working/metodo_redes']",
    "gift4": "['gift4', '--brutos', os.path.join(DADOS, 'brutos')]",
    "plantado": "['plantado']",
}


def main() -> None:
    modo = sys.argv[1]
    slug = f"piso-redes-{modo}"
    modos = ["gift4", "plantado"] if modo == "gift4" else [modo]
    fonte = """
import glob, os, subprocess, sys
codigo = os.path.dirname(glob.glob('/kaggle/input/**/codigo/scripts', recursive=True)[0])
DADOS = os.path.dirname(glob.glob('/kaggle/input/**/dados_metodo/piso', recursive=True)[0])
import torch
assert torch.cuda.is_available(), 'sem GPU'
gpu = torch.cuda.get_device_name(0)
assert 'P100' not in gpu, gpu
print('GPU:', gpu, flush=True)
script = os.path.join(codigo, 'scripts', 'reduced_rounds', 'metodo_redes.py')
"""
    for m in modos:
        fonte += f"""
proc = subprocess.Popen([sys.executable, '-u', script] + {CMD[m]},
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
for linha in proc.stdout:
    print(linha, end='', flush=True)
print('terminou com código', proc.wait(), flush=True)
"""
    nb = {"cells": [{"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [],
                     "source": fonte.strip("\n").splitlines(keepends=True)}],
          "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                       "language_info": {"name": "python"}}, "nbformat": 4, "nbformat_minor": 5}
    alvo = STAGE / slug
    alvo.mkdir(parents=True, exist_ok=True)
    (alvo / "redes.ipynb").write_text(json.dumps(nb, indent=1, ensure_ascii=False), encoding="utf-8")
    (alvo / "kernel-metadata.json").write_text(json.dumps({
        "id": f"{USUARIO}/{slug}", "title": slug, "code_file": "redes.ipynb", "language": "python",
        "kernel_type": "notebook", "is_private": True, "enable_gpu": True, "enable_internet": False,
        "machine_shape": "NvidiaTeslaT4", "dataset_sources": [f"{USUARIO}/{DATASET}"],
        "kernel_sources": [], "competition_sources": []}, indent=2), encoding="utf-8")
    sys.exit(subprocess.run([KAGGLE, "kernels", "push", "-p", str(alvo), "--accelerator", "NvidiaTeslaT4"]).returncode)


if __name__ == "__main__":
    main()
