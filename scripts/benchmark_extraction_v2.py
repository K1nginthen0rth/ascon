"""
Benchmark de extração de features v2 — GATE da Fase 4 (geração do dataset).

Mede o custo por amostra de cada família de features (as 6 do v1 + as 6
novas do v2) sobre uma amostra de ciphertexts reais, e extrapola o custo
total projetado para as 180.000 amostras do dataset v2. Ver
docs/plano_experimento_v2/06_implementacao_passo_a_passo.md Fase 2.4.

Uso:
    python scripts/benchmark_extraction_v2.py [--n-samples 500]

Critério de aceite: custo total projetado conhecido e registrado em
reports/v2/benchmark_extracao.md — decisão de otimizar (numba/vetorização)
antes de prosseguir para a Fase 4 fica para o Nycolas, não é automática.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.features.extractor import _ALL_FAMILIES, _FAMILY_FUNCS  # noqa: E402

DEFAULT_SOURCE = REPO_ROOT / "data" / "processed" / "keyholdout_2class_60k_v1.parquet"
OUT_DIR = REPO_ROOT / "reports" / "v2"
N_TOTAL_V2 = 180_000


def benchmark(n_samples: int, source_path: Path) -> pd.DataFrame:
    full_df = pd.read_parquet(source_path, columns=["ciphertext"])
    df = full_df.sample(n=min(n_samples, len(full_df)), random_state=42)
    cts = [bytes(c) for c in df["ciphertext"]]
    n = len(cts)
    print(f"Benchmarking {n} amostras reais de {source_path.name} "
          f"(len_ct médio: {sum(len(c) for c in cts) / n:.0f} bytes)\n")

    rows = []
    for fname in _ALL_FAMILIES:
        func = _FAMILY_FUNCS[fname]
        t0 = time.perf_counter()
        n_features = None
        for ct in cts:
            feats = func(ct)
            if n_features is None:
                n_features = len(feats)
        elapsed = time.perf_counter() - t0
        per_sample_ms = (elapsed / n) * 1000.0
        projected_hours = (per_sample_ms / 1000.0) * N_TOTAL_V2 / 3600.0
        rows.append({
            "family": fname,
            "n_features": n_features,
            "ms_per_sample": per_sample_ms,
            "projected_hours_180k_serial": projected_hours,
        })
        print(f"  {fname:20s} {n_features:4d} feats  {per_sample_ms:8.3f} ms/amostra  "
              f"~{projected_hours:7.2f}h projetadas (serial, 180k)")

    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-samples", type=int, default=500)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    args = parser.parse_args()

    if not args.source.exists():
        raise FileNotFoundError(
            f"Dataset fonte não encontrado: {args.source}\n"
            "Ajuste --source para um parquet com coluna 'ciphertext' disponível "
            "(o dataset v2 ainda não existe — usamos o v1 como proxy de "
            "tamanho/característica de CT para o benchmark)."
        )

    result = benchmark(args.n_samples, args.source)

    total_serial_h = result["projected_hours_180k_serial"].sum()
    print(f"\nTOTAL projetado (serial, 1 processo): {total_serial_h:.1f}h")
    print("Nota: extração real usa joblib.Parallel (n_jobs=-1) — dividir "
          "aproximadamente pelo nº de cores disponíveis para uma estimativa "
          "de wall-clock real.")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / "benchmark_extracao.md"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("# Benchmark de extração de features — v2\n\n")
        f.write(f"Amostras: {args.n_samples} (fonte: `{args.source.name}`)\n\n")
        f.write("| Família | Nº features | ms/amostra | Horas projetadas (180k, serial) |\n")
        f.write("|---|---|---|---|\n")
        for _, row in result.iterrows():
            f.write(
                f"| {row['family']} | {row['n_features']} | "
                f"{row['ms_per_sample']:.3f} | {row['projected_hours_180k_serial']:.2f} |\n"
            )
        f.write(f"\n**Total projetado (serial): {total_serial_h:.1f}h.** "
                f"Dividir pelo nº de cores em uso via `joblib.Parallel` para "
                f"estimativa de wall-clock real.\n")
    print(f"\nRelatório salvo em {out_path}")


if __name__ == "__main__":
    main()
