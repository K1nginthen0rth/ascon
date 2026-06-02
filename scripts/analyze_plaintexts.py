"""
Entry point so para a Analise 1 (caracterizacao de plaintexts) dos controles.

Reusa as funcoes de scripts/run_control_analysis.py. Saida: stdout +
reports/control_analysis/plaintext_characterization.json.

Como rodar:
  python scripts/analyze_plaintexts.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "scripts"))

from run_control_analysis import OUT_DIR, analyse_plaintexts


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pt_stats = analyse_plaintexts()
    out = OUT_DIR / "plaintext_characterization.json"
    out.write_text(json.dumps(pt_stats, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSalvo: {out.relative_to(_REPO)}")


if __name__ == "__main__":
    main()
