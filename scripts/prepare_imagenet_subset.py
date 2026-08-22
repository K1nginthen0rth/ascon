"""
Prepara o subconjunto de imagens do dataset v2 (20% do plaintext — ver
docs/plano_experimento_v2/01_algoritmos_e_dataset.md §1.5).

Fonte: benjamin-paine/imagenet-1k-256x256 (Hugging Face), split de
validação (50.000 imagens em 2 shards parquet — só o shard 0, com 25.000,
é baixado; suficiente para as 6.000 necessárias, evita baixar o shard 1
à toa). Licença: ImageNet Terms of Access (uso não-comercial de pesquisa/
educacional — licenças já confirmadas pelo Nycolas em sessão de
planejamento).

Cada imagem selecionada é convertida para tons de cinza (`PIL .convert("L")`)
e salva como bytes brutos de exatamente 65.536 bytes (256×256×1) em
data/raw/imagens_v2/<image_id>.bin — junto com um manifesto (ids, índice de
origem no shard, sha256, licença, seed de seleção).

Seleção determinística via CTR_DRBG (nunca NumPy — mesmo mecanismo do
restante do material criptográfico do dataset v2), reaproveitando a seed
canônica do projeto (42) com label distinto para não colidir com nenhum
outro uso dessa seed.

Uso:
    python scripts/prepare_imagenet_subset.py [--n-images 6000]
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import pandas as pd  # noqa: E402
from huggingface_hub import hf_hub_download  # noqa: E402
from PIL import Image  # noqa: E402

from src.crypto.ctr_drbg import CTRDRBG  # noqa: E402

REPO_ID = "benjamin-paine/imagenet-1k-256x256"
SHARD_FILENAME = "data/validation-00000-of-00002.parquet"
N_IMAGES_DEFAULT = 6000
SEED = 42  # seed canônica do projeto (split=42) — label abaixo evita colisão
LABEL = "imagens_v2_selecao"
IMG_BYTES = 65536  # 256 * 256 * 1 (grayscale)

OUT_DIR = REPO_ROOT / "data" / "raw" / "imagens_v2"

LICENSE_TEXT = (
    "ImageNet Terms of Access (via Hugging Face, license: other / "
    "license_details: imagenet-agreement) — uso restrito a pesquisa e "
    "fins educacionais não-comerciais. Licenças confirmadas pelo Nycolas "
    "em sessão de planejamento do experimento v2 (2026-08-21)."
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-images", type=int, default=N_IMAGES_DEFAULT)
    args = parser.parse_args()
    n_images = args.n_images

    print(f"Baixando {SHARD_FILENAME} de {REPO_ID} (split de validação)...")
    shard_path = hf_hub_download(
        repo_id=REPO_ID, filename=SHARD_FILENAME, repo_type="dataset"
    )
    df = pd.read_parquet(shard_path)
    n_available = len(df)
    print(f"Shard carregado: {n_available} imagens disponíveis.")

    if n_images > n_available:
        raise ValueError(
            f"--n-images={n_images} > {n_available} disponíveis no shard 0. "
            "Baixe também o shard 1 (validation-00001-of-00002) se precisar de mais."
        )

    # Seleção sem reposição via CTR_DRBG (determinística, reprodutível).
    drbg = CTRDRBG(seed=SEED, label=LABEL)
    selected_indices: list[int] = []
    seen: set[int] = set()
    while len(selected_indices) < n_images:
        idx = drbg.randint(0, n_available)
        if idx not in seen:
            seen.add(idx)
            selected_indices.append(idx)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest_entries = []
    t_start = datetime.now(timezone.utc)

    for i, idx in enumerate(selected_indices):
        row = df.iloc[idx]
        jpeg_bytes = row["image"]["bytes"]
        img = Image.open(io.BytesIO(jpeg_bytes)).convert("L")
        if img.size != (256, 256):
            img = img.resize((256, 256))
        raw = img.tobytes()
        if len(raw) != IMG_BYTES:
            raise RuntimeError(
                f"Imagem índice {idx}: {len(raw)} bytes após conversão, "
                f"esperado {IMG_BYTES}."
            )

        image_id = f"img_v2_{i:05d}"
        out_path = OUT_DIR / f"{image_id}.bin"
        out_path.write_bytes(raw)

        manifest_entries.append({
            "image_id": image_id,
            "source_shard": SHARD_FILENAME,
            "source_index_in_shard": int(idx),
            "source_label": int(row["label"]),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "size_bytes": len(raw),
        })

        if (i + 1) % 1000 == 0:
            print(f"  {i + 1}/{n_images} processadas...")

    t_end = datetime.now(timezone.utc)

    manifest = {
        "dataset_source": REPO_ID,
        "shard_used": SHARD_FILENAME,
        "n_images_available_in_shard": n_available,
        "license": LICENSE_TEXT,
        "n_images": n_images,
        "selection_seed": SEED,
        "selection_label": LABEL,
        "selection_method": "CTRDRBG.randint sem reposição (ver src/crypto/ctr_drbg.py)",
        "conversion": "PIL .convert('L'), 256x256 -> 65536 bytes crus",
        "generated_at": t_start.isoformat(),
        "elapsed_s": round((t_end - t_start).total_seconds(), 2),
        "images": manifest_entries,
    }
    manifest_path = OUT_DIR / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nSalvo: {n_images} imagens em {OUT_DIR}")
    print(f"Manifesto: {manifest_path}")


if __name__ == "__main__":
    main()
