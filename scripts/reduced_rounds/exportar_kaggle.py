"""
Monta o pacote do Kaggle para os caminhos B, C, D e F do piso, com 10x os dados.

Os dados saem da curva de orçamento (`run_curva_orcamento.py`), que já sorteou e
cifrou 31.000 dispositivos com a mesma amostragem do `run_floor.py`: os
primeiros 3.000 dispositivos dela são, byte a byte, os de um `run_floor` com
3.000 chaves. A curva só guardou o piso e a rodada seguinte; este script cifra a
rodada 1 e a especificação completa para os mesmos 3.000 dispositivos e grava
tudo no formato de cache do `run_floor` (com a impressão digital), de modo que
no Kaggle nenhuma cifra precisa rodar.

Conferências:
- a classe aleatória sorteada de novo tem que bater com a da curva;
- o piso recifrado para os primeiros dispositivos tem que bater com o da curva;
- o próprio `run_floor.generate` tem que aceitar o cache sem regerar nada.

Saída: build/kaggle_piso/ com `dados/<algo>_<braço>_k3000.npz` e o código
necessário, mais um .zip para subir como dataset do Kaggle.

Uso:
    python scripts/reduced_rounds/exportar_kaggle.py
    python scripts/reduced_rounds/exportar_kaggle.py --so-codigo   (refaz só o zip do código)
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
import zipfile
from multiprocessing import Pool
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src" / "crypto"))

import numpy as np  # noqa: E402

from scripts.reduced_rounds.run_curva_orcamento import (  # noqa: E402
    OUT as CURVA, PARES, PISOS, _cifrar_bloco, sortear,
)

N_KEYS = 3_000
BUNDLE = REPO_ROOT / "build" / "kaggle_piso"

# Código que o runner do Kaggle importa. O resto do repositório fica de fora.
CODIGO = [
    "scripts/reduced_rounds/kaggle_piso.py",
    "scripts/reduced_rounds/kaggle_100x.py",
    "scripts/reduced_rounds/run_floor.py",
    "scripts/reduced_rounds/run_gift_floor.py",
    "scripts/reduced_rounds/floor_algos.py",
    "scripts/reduced_rounds/gift_pure_cipher.py",
    "scripts/reduced_rounds/neural_floor.py",
    "scripts/reduced_rounds/report_floor.py",
    "scripts/run_v2_caminho_a.py",
    "scripts/generate_5class_v2.py",
    "scripts/consolidate_v2.py",          # report_floor usa o BH-FDR de lá
    # gift_pure_cipher importa a reimplementação independente do GIFT-COFB
    "tests/__init__.py",
    "tests/test_crypto_independente.py",
]
PASTAS_CODIGO = ["src/eval", "src/models", "src/features", "src/crypto"]


def exportar(algo: str, arm: str, workers: int) -> Path:
    from scripts.reduced_rounds import run_floor as rf
    from scripts.reduced_rounds.floor_algos import ALGOS

    spec = ALGOS[algo]
    piso = PISOS[algo]
    n = N_KEYS * PARES
    destino = BUNDLE / "dados" / f"{algo}_{arm}_k{N_KEYS}.npz"
    if destino.exists():
        rf._log(f"[{algo}/{arm}] já exportado: {destino.name}")
        return destino

    z = np.load(CURVA / f"{algo}_{arm}_dev31000.npz")
    assert np.array_equal(z["dev"][:n], np.repeat(np.arange(N_KEYS), PARES)), "ordem da curva mudou"
    store = {f"r{r}": z[f"r{r}"][:n].copy() for r in (piso, piso + 1)}
    store["random"] = z["random"][:n].copy()
    del z

    t0 = time.time()
    chaves, p1, p2, rnd = sortear(algo, arm, N_KEYS)
    assert np.array_equal(rnd, store["random"]), "classe aleatória não bate com a curva"
    _, conf = _cifrar_bloco((algo, [piso], 0, chaves[:20], p1[:20 * PARES], p2[:20 * PARES]))
    assert np.array_equal(conf[piso], store[f"r{piso}"][:20 * PARES]), "piso recifrado não bate"
    rf._log(f"[{algo}/{arm}] sorteio conferido com a curva ({time.time() - t0:.0f}s)")

    novas = sorted(r for r in {1, spec.max_rounds} if f"r{r}" not in store)
    passo = 100
    tarefas = [(algo, novas, k0, chaves[k0:k0 + passo],
                p1[k0 * PARES:(k0 + passo) * PARES], p2[k0 * PARES:(k0 + passo) * PARES])
               for k0 in range(0, N_KEYS, passo)]
    for r in novas:
        store[f"r{r}"] = np.zeros_like(store["random"])
    with Pool(workers) as pool:
        for k0, out in pool.imap_unordered(_cifrar_bloco, tarefas):
            for r, arr in out.items():
                store[f"r{r}"][k0 * PARES:k0 * PARES + len(arr)] = arr
    rf._log(f"[{algo}/{arm}] rodadas {novas} cifradas ({time.time() - t0:.0f}s)")

    # Mesma impressão digital que o run_floor.generate grava (contador zero, xor).
    store["key_idx"] = np.repeat(np.arange(N_KEYS), PARES).astype(np.int32)
    store[rf._FP] = rf.impressao_digital(
        algo=algo, arm=arm, politica="ambos", n_keys=N_KEYS, pairs_per_key=PARES,
        msg_bytes=rf.MSG_BYTES, tag_bytes=spec.tag_bytes, nonce_bytes=spec.nonce_bytes,
        seed_gen=rf.SEED_GEN, esquema=rf.ESQUEMA_AMOSTRA, contador="zero")
    destino.parent.mkdir(parents=True, exist_ok=True)
    np.savez(destino, **store)

    rodadas = sorted(int(k[1:]) for k in store if k.startswith("r") and k[1:].isdigit())
    # O próprio run_floor tem que aceitar o cache: a impressão digital é
    # conferida, e com todas as rodadas presentes ele não cifra nada.
    volta = rf.generate(algo, arm, N_KEYS, rodadas, destino, "ambos", contador="zero")
    assert all(np.array_equal(volta[f"r{r}"], store[f"r{r}"]) for r in rodadas)
    meta = dict(algo=algo, arm=arm, n_keys=N_KEYS, pairs_per_key=PARES, rodadas=rodadas,
                origem=f"curva_orcamento/{algo}_{arm}_dev31000.npz (primeiros {N_KEYS} "
                       f"dispositivos) + rodadas {novas} cifradas aqui",
                contador="zero", representacao="xor")
    destino.with_suffix(".json").write_text(json.dumps(meta, indent=2, ensure_ascii=False),
                                            encoding="utf-8")
    rf._log(f"[{algo}/{arm}] -> {destino.name} ({destino.stat().st_size / 2**20:.0f} MB)")
    return destino


def empacotar_codigo() -> Path:
    alvo = BUNDLE / "codigo"
    if alvo.exists():
        shutil.rmtree(alvo)
    arquivos = [Path(a) for a in CODIGO]
    for pasta in PASTAS_CODIGO:
        arquivos += [p.relative_to(REPO_ROOT) for p in (REPO_ROOT / pasta).rglob("*.py")]
    for rel in arquivos:
        (alvo / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO_ROOT / rel, alvo / rel)
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT,
                            capture_output=True, text=True).stdout.strip()
    (alvo / "VERSAO.txt").write_text(f"commit base: {commit}\n(com alterações locais não commitadas)\n",
                                     encoding="utf-8")
    # O notebook sobe à parte (File → Import Notebook no Kaggle).
    shutil.copy2(REPO_ROOT / "scripts" / "reduced_rounds" / "kaggle_piso.ipynb", BUNDLE)
    return alvo


def zipar() -> Path:
    zp = BUNDLE / "piso_kaggle.zip"
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_STORED) as z:
        for sub in ("codigo", "dados"):
            for p in sorted((BUNDLE / sub).rglob("*")):
                if p.is_file() and "__pycache__" not in p.parts:
                    z.write(p, p.relative_to(BUNDLE))
    return zp


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--algos", nargs="+", default=["ascon", "schwaemm", "grain", "gift"])
    ap.add_argument("--arms", nargs="+", default=["texto", "aleatorio"])
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--so-codigo", action="store_true")
    a = ap.parse_args()
    if not a.so_codigo:
        for algo in a.algos:
            for arm in a.arms:
                exportar(algo, arm, a.workers)
    empacotar_codigo()
    zp = zipar()
    print(f"pacote: {zp} ({zp.stat().st_size / 2**20:.0f} MB)")


if __name__ == "__main__":
    main()
