"""
Caracterizacao estatistica dos ciphertexts do dataset control_vigenere_v1.

Para cada algoritmo (Ascon, GIFT-COFB, Vigenere-XOR), calcula:
  1. Entropia de Shannon (bits/byte)
  2. Chi-quadrado vs uniforme (256 categorias)
  3. Indice de coincidencia (IC)
        IC = sum(n_i * (n_i - 1)) / (N * (N - 1))
        uniforme ~ 1/256 ~ 0.00391
        texto natural em ingles ~ 0.067 (no nivel de letras);
        em bytes ASCII ~ 0.04-0.06
  4. % de blocos de 16 bytes repetidos no CT
  5. Autocorrelacao no lag 3 (assinatura do Vigenere com chave de 3 bytes)

Saidas:
  reports/control_vigenere_v1/characterization.md
  reports/control_vigenere_v1/characterization.json
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

DATASET_ID = "control_vigenere_v1"
PARQUET    = _REPO / "data" / "processed" / f"{DATASET_ID}.parquet"
REPORTS    = _REPO / "reports" / DATASET_ID
REPORTS.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Estatisticas por amostra
# ---------------------------------------------------------------------------
def shannon_entropy(byts: np.ndarray) -> float:
    counts = np.bincount(byts, minlength=256).astype(np.float64)
    p = counts / counts.sum()
    p = p[p > 0]
    return float(-(p * np.log2(p)).sum())


def chi_square_uniform(byts: np.ndarray) -> float:
    counts = np.bincount(byts, minlength=256).astype(np.float64)
    n = counts.sum()
    expected = n / 256.0
    return float(((counts - expected) ** 2 / expected).sum())


def index_of_coincidence(byts: np.ndarray) -> float:
    n = len(byts)
    if n < 2:
        return 0.0
    counts = np.bincount(byts, minlength=256).astype(np.float64)
    return float((counts * (counts - 1)).sum() / (n * (n - 1)))


def block_repetition_pct(byts: np.ndarray, block: int = 16) -> float:
    n = len(byts)
    if n < 2 * block:
        return 0.0
    n_blocks = n // block
    blocks = byts[: n_blocks * block].reshape(n_blocks, block)
    # blocks como bytes (hashable)
    seen: dict[bytes, int] = {}
    for row in blocks:
        b = row.tobytes()
        seen[b] = seen.get(b, 0) + 1
    repeated = sum(c for c in seen.values() if c > 1)
    return 100.0 * repeated / n_blocks


def autocorrelation_lag(byts: np.ndarray, lag: int) -> float:
    n = len(byts)
    if n <= lag + 1:
        return 0.0
    x = byts.astype(np.float64)
    x -= x.mean()
    denom = (x * x).sum()
    if denom == 0:
        return 0.0
    num = (x[: n - lag] * x[lag:]).sum()
    return float(num / denom)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    print(f"\n{'='*70}\n  Caracterizacao: {DATASET_ID}\n{'='*70}")
    df = pd.read_parquet(PARQUET)
    print(f"  Total amostras: {len(df):,}  ({df['algorithm'].nunique()} classes)")

    algos = sorted(df["algorithm"].unique().tolist())

    results: dict[str, dict] = {}
    t0 = time.perf_counter()

    for algo in algos:
        sub = df[df["algorithm"] == algo]
        H_list, chi_list, ic_list, blk_list, ac3_list = [], [], [], [], []

        for ct in sub["ciphertext"]:
            arr = np.frombuffer(bytes(ct), dtype=np.uint8)
            H_list.append(shannon_entropy(arr))
            chi_list.append(chi_square_uniform(arr))
            ic_list.append(index_of_coincidence(arr))
            blk_list.append(block_repetition_pct(arr, 16))
            ac3_list.append(autocorrelation_lag(arr, 3))

        results[algo] = {
            "n_samples":  len(sub),
            "ct_lens":    sorted(sub["len_ct"].unique().tolist()),
            "entropy":    {"mean": float(np.mean(H_list)),
                           "std":  float(np.std(H_list))},
            "chi2":       {"mean": float(np.mean(chi_list)),
                           "std":  float(np.std(chi_list))},
            "ic":         {"mean": float(np.mean(ic_list)),
                           "std":  float(np.std(ic_list))},
            "block_rep_pct": {"mean": float(np.mean(blk_list)),
                              "std":  float(np.std(blk_list))},
            "autocorr_lag3": {"mean": float(np.mean(ac3_list)),
                              "std":  float(np.std(ac3_list)),
                              "abs_mean": float(np.mean(np.abs(ac3_list)))},
        }
        print(f"    OK {algo:18s} N={len(sub):4d}  "
              f"H={results[algo]['entropy']['mean']:.4f}  "
              f"IC={results[algo]['ic']['mean']:.5f}  "
              f"AC3={results[algo]['autocorr_lag3']['mean']:+.4f}")

    elapsed = time.perf_counter() - t0
    print(f"  Tempo: {elapsed:.1f}s")

    # ----- Tabela markdown -----
    rows = [
        "| Algoritmo | H_CT | chi2_CT | IC_CT | %Blk Rep | AutoCorr lag3 |",
        "|-----------|------|---------|-------|----------|----------------|",
    ]
    for algo in algos:
        r = results[algo]
        rows.append(
            f"| {algo} "
            f"| {r['entropy']['mean']:.4f} ± {r['entropy']['std']:.4f} "
            f"| {r['chi2']['mean']:.1f} ± {r['chi2']['std']:.1f} "
            f"| {r['ic']['mean']:.5f} ± {r['ic']['std']:.5f} "
            f"| {r['block_rep_pct']['mean']:.3f}% "
            f"| {r['autocorr_lag3']['mean']:+.4f} ± {r['autocorr_lag3']['std']:.4f} |"
        )

    md = (
        f"# Caracterizacao estatistica - {DATASET_ID}\n\n"
        f"- Total amostras: {len(df):,} ({len(algos)} classes, "
        f"{df.groupby('algorithm').size().to_dict()})\n"
        f"- CT comprimentos por algoritmo (bytes): "
        f"{{algo: lens}} = {{ "
        + ", ".join(f"'{a}': {results[a]['ct_lens']}" for a in algos)
        + " }\n"
        f"- Tempo de analise: {elapsed:.1f}s\n\n"
        + "\n".join(rows)
        + "\n\n"
        f"## Interpretacao esperada\n\n"
        f"- **Entropia (H)**: AEADs proximos do maximo (~8 bits/byte); "
        f"Vigenere herda do texto natural (~4-5 bits/byte) - **assinatura clara**.\n"
        f"- **Chi2**: AEADs ~ 255 (gl=255, esperado para uniforme); "
        f"Vigenere muito > 255 (desvio da uniformidade).\n"
        f"- **Indice de Coincidencia**: uniforme ~ 0.00391; "
        f"texto natural ~ 0.04-0.07; Vigenere preserva esse valor "
        f"(XOR com chave fixa nao altera frequencia relativa dentro de cada classe mod 3).\n"
        f"- **%Blocos repetidos**: AEADs ~ 0%; Vigenere pode mostrar repeticoes "
        f"se o PT tiver tambem padroes de 16 bytes alinhados ao ciclo de 3 (raro).\n"
        f"- **Autocorrelacao lag 3**: para Vigenere com chave de 3 bytes, "
        f"byte[i] e byte[i+3] sao XOR do mesmo byte de chave - "
        f"se PT tem autocorr_lag3 alto (texto natural tem), CT herda. **Prova definitiva**.\n"
    )

    (REPORTS / "characterization.md").write_text(md, encoding="utf-8")
    (REPORTS / "characterization.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"\n  Artefatos:")
    print(f"    {(REPORTS / 'characterization.md').relative_to(_REPO)}")
    print(f"    {(REPORTS / 'characterization.json').relative_to(_REPO)}")


if __name__ == "__main__":
    main()
