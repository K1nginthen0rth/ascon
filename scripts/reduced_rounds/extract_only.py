"""Extrai as 641 features de parquets de criptograma JÁ gerados, sem regerar
e sem classificar.

Existe para as três primeiras configs do estudo (asimetrico,
asimetrico_inverso, simetrico), cujos runners descartaram as features antes
da correção. Os criptogramas continuam em disco; só falta a extração. A
classificação e toda a estatística (bootstrap por chave, AUC, ECE,
predições, importâncias) ficam com `report_stats.py`, que lê o parquet de
features gerado aqui.

Pula arquivos cujo parquet de features já existe — relançar é seguro.

Uso:
    python scripts/reduced_rounds/extract_only.py full/full_asimetrico_ciphertexts.parquet ...
"""
from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.reduced_rounds.streaming_extract import extract_streaming  # noqa: E402
from src.features.extractor import _ALL_FAMILIES  # noqa: E402

BASE = REPO_ROOT / "build" / "reduced_rounds"


def _log(msg: str) -> None:
    print(f"[{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}] {msg}", flush=True)


def features_path_for(ct_path: Path) -> Path:
    name = ct_path.stem.replace("full_", "").replace("_ciphertexts", "")
    return ct_path.parent / f"features_{name}.parquet"


if __name__ == "__main__":
    targets = [BASE / a for a in sys.argv[1:]]
    if not targets:
        sys.exit("uso: extract_only.py <caminho relativo a build/reduced_rounds> ...")
    for ct in targets:
        out = features_path_for(ct)
        if out.exists():
            _log(f"já existe, pulando: {out.name}")
            continue
        if not ct.exists():
            _log(f"AVISO: criptogramas não encontrados: {ct}")
            continue
        t0 = time.time()
        _log(f"===== extraindo {ct.name} -> {out.name} =====")
        extract_streaming(ct, list(_ALL_FAMILIES), output_path=out, log=_log)
        _log(f"concluído em {(time.time() - t0) / 60:.0f} min")
    _log("Fila concluída.")
