"""
Junta a grade fina de dados mínimos com a extensão (`_ext`) e reaplica o
critério sobre o conjunto inteiro, para que o BH conte todas as células.

Uso:
    python scripts/reduced_rounds/consolidar_dados_minimos.py
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

import pandas as pd  # noqa: E402

from scripts.reduced_rounds.run_dados_minimos import OUT, PISOS  # noqa: E402
from scripts.reduced_rounds.run_dados_minimos_fino import criterio, minimos  # noqa: E402

BASE = ["algo", "arm", "rodadas", "modelo", "pares_treino", "bolsa", "f1", "f1_lo", "f1_hi", "auc"]


def main() -> None:
    partes = []
    for algo in ["ascon", "gift", "schwaemm"]:
        for suf in ["", "_ext"]:
            f = OUT / f"dados_minimos_fino_{algo}{suf}.csv"
            if f.exists():
                partes.append(pd.read_csv(f)[BASE])
    df = criterio(pd.concat(partes, ignore_index=True))
    df.to_csv(OUT / "dados_minimos_fino_consolidado.csv", index=False)
    mn = minimos(df)
    mn.to_csv(OUT / "dados_minimos_fino_consolidado_minimos.csv", index=False)

    piso = df[(df["arm"] != "aleatorio") & (df["rodadas"] == df["algo"].map(PISOS))]
    print("F1 na rodada do piso (braço de texto):")
    print(piso.pivot_table(index=["algo", "modelo", "pares_treino"], columns="bolsa",
                           values="f1").round(3).to_string())
    print("\ndetectada (1) na rodada do piso:")
    print(piso.pivot_table(index=["algo", "modelo", "pares_treino"], columns="bolsa",
                           values="detectada").astype(int).to_string())
    print("\nmenor treino (pares) com detecção estável:")
    print(mn.pivot_table(index=["algo", "modelo"], columns="bolsa",
                         values="pares_treino_min").to_string())
    print("\nabaixo da grade:\n", mn[mn["abaixo_da_grade"]].to_string())
    alea = df[df["arm"] == "aleatorio"]
    print(f"\nbraço aleatório: {int(alea['detectada'].sum())} de {len(alea)} células detectadas; "
          f"F1 máximo {alea['f1'].max():.3f}")


if __name__ == "__main__":
    main()
