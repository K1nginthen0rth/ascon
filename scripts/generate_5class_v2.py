"""
Gera o dataset v2 encadeado: 4 algoritmos LWC (Ascon-AEAD128, GIFT-COFB,
Grain-128AEAD, Schwaemm256-128) + AES-128-ECB (controle) + PRNG (controle
negativo), 300 chaves x 100 slots, 180.000 amostras (~11,8 GB). Ver
docs/plano_experimento_v2/01_algoritmos_e_dataset.md e
06_implementacao_passo_a_passo.md Fase 4.2.

Encadeamento: dentro de um slot (chave + plaintext + nonce), a MESMA tripla
é cifrada pelos 5 algoritmos — qualquer diferença estatística entre as
classes só pode vir do mecanismo criptográfico, nunca de dados diferentes.
O nonce de 128 bits (contador global) é mapeado para o tamanho de cada
algoritmo: Ascon/GIFT-COFB usam os 16 bytes diretos; Grain usa os 12 bytes
menos significativos (96 bits); Schwaemm256-128 usa os 16 bytes nos 128
bits MENOS significativos de um campo de 32 bytes, com os 128 bits mais
significativos zerados; AES-ECB ignora nonce.

Geração pseudoaleatória: CTR_DRBG (NIST SP 800-90A) para TODO material
determinístico do dataset (chaves, amostragem de posição no corpus de
texto, decisão texto/imagem por amostra, geração do PRNG-controle) — nunca
NumPy (Regra de Ouro 8). Cada uso tem seu próprio (seed, label) para não
correlacionar streams.

Uso:
    python scripts/generate_5class_v2.py [--n-keys 300] [--slots-per-key 100]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src" / "crypto"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.model_selection import GroupKFold  # noqa: E402

from src.crypto.aes_ecb_wrapper import AES128ECB  # noqa: E402
from src.crypto.ascon_wrapper import AsconAEAD128  # noqa: E402
from src.crypto.ctr_drbg import CTRDRBG  # noqa: E402
from src.crypto.gift_cofb_wrapper import GiftCOFB  # noqa: E402
from src.crypto.grain_wrapper import Grain128AEAD  # noqa: E402
from src.crypto.sparkle_wrapper import Schwaemm256_128  # noqa: E402

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

PLAINTEXT_BYTES = 65536
BASE_SEED = 42
KEY_SEED_OFFSET = 6000
IMAGE_SOURCE_PROBABILITY = 0.2  # 20% imagem, 80% texto (por amostra)

CORPORA_DIR = REPO_ROOT / "data" / "raw" / "corpora"
IMAGES_DIR = REPO_ROOT / "data" / "raw" / "imagens_v2"
IMAGES_MANIFEST = IMAGES_DIR / "manifest.json"

OUT_DIR = REPO_ROOT / "data" / "processed"
INTERIM_DIR = REPO_ROOT / "data" / "interim"


@dataclass
class V2Config:
    n_keys: int = 300
    slots_per_key: int = 100
    dataset_id: str = "keyholdout_5class_v2"
    version: str = "v2"
    seed: int = BASE_SEED
    key_seed_offset: int = KEY_SEED_OFFSET
    n_test_keys: int = 60  # 240 trainval / 60 test (80/20)
    n_folds: int = 5


# ---------------------------------------------------------------------------
# Amostragem de plaintext (texto, via CTR_DRBG)
# ---------------------------------------------------------------------------

class _TextPlaintextSampler:
    """Amostra trechos de PLAINTEXT_BYTES do corpus SPGC, via CTR_DRBG
    (nunca NumPy — ver docstring do módulo)."""

    def __init__(self, corpora_dir: Path, drbg: CTRDRBG) -> None:
        self._drbg = drbg
        self._corpora: list[bytes] = []

        for p in sorted(corpora_dir.glob("*.txt")):
            try:
                text = p.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            text = " ".join(text.replace("\n", " ").split())
            data = text.encode("utf-8")
            if len(data) >= PLAINTEXT_BYTES:
                self._corpora.append(data)

        if not self._corpora:
            raise ValueError(
                f"Nenhum corpus com >= {PLAINTEXT_BYTES} bytes UTF-8 em: {corpora_dir}"
            )

    def sample(self) -> bytes:
        for _ in range(2000):
            idx = self._drbg.randint(0, len(self._corpora))
            data = self._corpora[idx]
            if len(data) < PLAINTEXT_BYTES:
                continue
            start = self._drbg.randint(0, len(data) - PLAINTEXT_BYTES + 1)
            chunk = data[start:start + PLAINTEXT_BYTES]
            try:
                chunk.decode("utf-8")
                return chunk
            except UnicodeDecodeError:
                continue
        raise RuntimeError(
            "Não foi possível amostrar um trecho UTF-8 válido do corpus "
            "após 2000 tentativas."
        )


class _ImagePlaintextSampler:
    """Consome o pool de imagens pré-processadas (prepare_imagenet_subset.py)
    em ordem embaralhada (via CTR_DRBG), sem repetição até esgotar o pool;
    se esgotado (raro — variação binomial acima do esperado), reusa
    imagens já consumidas (log explícito, registrado no manifesto)."""

    def __init__(self, images_dir: Path, manifest_path: Path, drbg: CTRDRBG) -> None:
        if not manifest_path.exists():
            raise FileNotFoundError(
                f"Manifesto de imagens não encontrado: {manifest_path}\n"
                "Rode primeiro: python scripts/prepare_imagenet_subset.py"
            )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        image_ids = [e["image_id"] for e in manifest["images"]]

        # Embaralha deterministicamente via Fisher-Yates com CTR_DRBG.
        order = list(image_ids)
        for i in range(len(order) - 1, 0, -1):
            j = drbg.randint(0, i + 1)
            order[i], order[j] = order[j], order[i]

        self._images_dir = images_dir
        self._order = order
        self._cursor = 0
        self.n_reused = 0

    def sample(self) -> tuple[bytes, str]:
        """Retorna (bytes_da_imagem, image_id)."""
        if self._cursor >= len(self._order):
            # Pool esgotado (variação binomial acima do esperado) — reusa.
            self.n_reused += 1
            image_id = self._order[self._cursor % len(self._order)]
        else:
            image_id = self._order[self._cursor]
        self._cursor += 1
        data = (self._images_dir / f"{image_id}.bin").read_bytes()
        return data, image_id


# ---------------------------------------------------------------------------
# Mapeamento de nonce por algoritmo
# ---------------------------------------------------------------------------

def _nonce_for_algorithm(counter_bytes_16: bytes, npubbytes: int) -> bytes:
    """Deriva o nonce de cada algoritmo a partir do contador global de 128
    bits (16 bytes, big-endian) — ver docstring do módulo."""
    if npubbytes == 0:  # AES-128-ECB: sem nonce, wrapper ignora o argumento
        return b""
    if npubbytes == 16:
        return counter_bytes_16
    if npubbytes == 12:  # Grain-128AEAD: 12 bytes menos significativos
        return counter_bytes_16[-12:]
    if npubbytes == 32:  # Schwaemm256-128: zero-pad nos 128 bits MAIS significativos
        return b"\x00" * 16 + counter_bytes_16
    raise ValueError(f"NPUBBYTES não mapeado: {npubbytes}")


# ---------------------------------------------------------------------------
# Geração principal
# ---------------------------------------------------------------------------

def generate_and_write(
    cfg: V2Config, pq_path: Path, keys_per_batch: int = 20,
) -> tuple[dict, dict, dict]:
    """
    Gera o dataset e grava incrementalmente em `pq_path` via
    `pyarrow.parquet.ParquetWriter`, em lotes de `keys_per_batch` chaves.

    Motivo: manter as 180.000 linhas (com ciphertexts de ~64KB cada, soma
    ~11,8GB) inteiramente em memória antes de escrever esgotava a RAM
    disponível numa máquina de 16GB (confirmado empiricamente: processo
    chegou a ~1GB de working set após poucos minutos, projeção de esgotar
    a memória livre — 6,3GB no momento — bem antes de terminar,
    causando swapping severo ou crash). Escrever em lotes mantém o pico de
    memória em torno de `keys_per_batch * slots_per_key * 6` linhas, não
    o dataset inteiro.

    Returns:
        (keys_map, generation_stats, agg_stats) — agg_stats acumula
        estatísticas equivalentes às que antes vinham de `df` inteiro
        (total de amostras, bytes, contagem por algoritmo/fonte), sem
        precisar manter o DataFrame completo em memória.
    """
    ciphers = {
        "Ascon-AEAD128": AsconAEAD128(),
        "GIFT-COFB": GiftCOFB(),
        "Grain-128AEAD": Grain128AEAD(),
        "Schwaemm256-128": Schwaemm256_128(),
        "AES-128-ECB": AES128ECB(),
    }

    keys_drbg = CTRDRBG(seed=cfg.seed + cfg.key_seed_offset, label="keys")
    text_drbg = CTRDRBG(seed=cfg.seed + cfg.key_seed_offset, label="plaintext_text")
    source_drbg = CTRDRBG(seed=cfg.seed + cfg.key_seed_offset, label="plaintext_source_choice")
    image_shuffle_drbg = CTRDRBG(seed=cfg.seed + cfg.key_seed_offset, label="image_pool_shuffle")
    prng_drbg = CTRDRBG(seed=cfg.seed + cfg.key_seed_offset, label="prng_control")

    text_sampler = _TextPlaintextSampler(CORPORA_DIR, text_drbg)
    image_sampler = _ImagePlaintextSampler(IMAGES_DIR, IMAGES_MANIFEST, image_shuffle_drbg)

    keys_map: dict[str, str] = {}
    nonce_counter = 0
    timestamp = datetime.now(timezone.utc).isoformat()
    n_image_slots = 0
    n_text_slots = 0

    import pyarrow as pa
    import pyarrow.parquet as pq

    writer: pq.ParquetWriter | None = None
    total_samples = 0
    total_ct_bytes = 0
    samples_per_algorithm: dict[str, int] = {}
    t_batch_start = datetime.now(timezone.utc)

    def _flush(rows: list[dict]) -> None:
        nonlocal writer, total_samples, total_ct_bytes
        if not rows:
            return
        table = pa.Table.from_pylist(rows)
        if writer is None:
            writer = pq.ParquetWriter(str(pq_path), table.schema)
        writer.write_table(table)
        total_samples += len(rows)
        total_ct_bytes += sum(r["len_ct"] for r in rows)
        for r in rows:
            samples_per_algorithm[r["algorithm"]] = samples_per_algorithm.get(r["algorithm"], 0) + 1

    rows: list[dict] = []

    for key_idx in range(cfg.n_keys):
        key_id = f"key_{key_idx + 1:04d}"
        key_bytes = keys_drbg.random_key(16)
        keys_map[key_id] = key_bytes.hex()

        for slot_idx in range(cfg.slots_per_key):
            nonce_counter += 1
            counter_bytes = nonce_counter.to_bytes(16, "big")
            nonce_id = f"nonce_{nonce_counter:07d}"

            is_image = source_drbg.choice_bool(IMAGE_SOURCE_PROBABILITY)
            if is_image:
                plaintext, image_id = image_sampler.sample()
                pt_source = "imagem"
                n_image_slots += 1
            else:
                plaintext = text_sampler.sample()
                image_id = ""
                pt_source = "corpus"
                n_text_slots += 1

            if len(plaintext) != PLAINTEXT_BYTES:
                raise RuntimeError(
                    f"plaintext do slot {key_id}/{slot_idx} tem {len(plaintext)} "
                    f"bytes, esperado {PLAINTEXT_BYTES}."
                )
            plaintext_sha256 = hashlib.sha256(plaintext).hexdigest()

            for algo_name, cipher in ciphers.items():
                nonce_bytes = _nonce_for_algorithm(counter_bytes, cipher.NPUBBYTES)
                ciphertext = cipher.encrypt(key_bytes, nonce_bytes, plaintext, b"")
                sample_id = f"{algo_name}_{key_id}_{nonce_id}_slot{slot_idx:03d}"
                rows.append({
                    "sample_id": sample_id,
                    "algorithm": algo_name,
                    "mode": "AEAD" if algo_name != "AES-128-ECB" else "ECB",
                    "impl": "ref" if algo_name != "AES-128-ECB" else "python",
                    "key_id": key_id,
                    "nonce_id": nonce_id,
                    "len_pt": len(plaintext),
                    "len_ad": 0,
                    "len_ct": len(ciphertext),
                    "ciphertext": ciphertext,
                    "plaintext_source": pt_source,
                    "plaintext_sha256": plaintext_sha256,
                    "image_id": image_id,
                    "seed": cfg.seed,
                    "version": cfg.version,
                    "timestamp": timestamp,
                })

            # Linha 6: controle PRNG (bytes crus, mesmo comprimento dos
            # 4 algoritmos de tag 128 bits; independente de key/nonce/pt).
            prng_bytes = prng_drbg.generate(65552)
            rows.append({
                "sample_id": f"PRNG_{key_id}_{nonce_id}_slot{slot_idx:03d}",
                "algorithm": "PRNG",
                "mode": "n/a",
                "impl": "ctr_drbg",
                "key_id": key_id,  # grupo sintético (ver docstring do módulo)
                "nonce_id": "n/a",
                "len_pt": 0,
                "len_ad": 0,
                "len_ct": len(prng_bytes),
                "ciphertext": prng_bytes,
                "plaintext_source": "n/a",
                "plaintext_sha256": "n/a",
                "image_id": "",
                "seed": cfg.seed,
                "version": cfg.version,
                "timestamp": timestamp,
            })

        if (key_idx + 1) % keys_per_batch == 0 or (key_idx + 1) == cfg.n_keys:
            _flush(rows)
            rows = []
            elapsed = (datetime.now(timezone.utc) - t_batch_start).total_seconds()
            print(f"  chave {key_idx + 1}/{cfg.n_keys} — {total_samples:,} amostras, "
                  f"{total_ct_bytes / 1e9:.2f} GB — {elapsed:.0f}s decorridos",
                  flush=True)

    if writer is not None:
        writer.close()

    generation_stats = {
        "n_image_slots": n_image_slots,
        "n_text_slots": n_text_slots,
        "image_source_ratio_actual": n_image_slots / (n_image_slots + n_text_slots),
        "image_pool_reused": image_sampler.n_reused,
    }
    agg_stats = {
        "total_samples": total_samples,
        "total_ciphertext_bytes": total_ct_bytes,
        "samples_per_algorithm": samples_per_algorithm,
        "plaintext_source_ratio": {
            "imagem": round(n_image_slots / (n_image_slots + n_text_slots), 4),
            "corpus": round(n_text_slots / (n_image_slots + n_text_slots), 4),
        },
    }
    return keys_map, generation_stats, agg_stats


def build_folds(all_key_ids: list[str], cfg: V2Config) -> dict:
    """Partição única 240/60 (seed) + 5-fold GroupKFold sobre o trainval.
    Todos os Caminhos devem ler deste arquivo, nunca resplitar (ver
    docstring do módulo e 06_implementacao_passo_a_passo.md Fase 4.2)."""
    all_keys = sorted(all_key_ids)
    rng = np.random.default_rng(cfg.seed)
    shuffled = rng.permutation(all_keys).tolist()
    n_test = cfg.n_test_keys
    test_keys = sorted(shuffled[:n_test])
    trainval_keys = sorted(shuffled[n_test:])

    # Proxy 1-linha-por-chave: GroupKFold com groups=própria chave produz o
    # mesmo particionamento que rodar diretamente sobre as amostras (todas
    # as chaves têm o mesmo número de linhas — o balanceamento por
    # contagem do GroupKFold dá o mesmo resultado nos dois níveis).
    proxy_X = np.arange(len(trainval_keys))
    gkf = GroupKFold(n_splits=cfg.n_folds)
    folds = []
    for fold_idx, (tr_idx, val_idx) in enumerate(
        gkf.split(proxy_X, groups=np.array(trainval_keys))
    ):
        folds.append({
            "fold": fold_idx,
            "train_keys": sorted(trainval_keys[i] for i in tr_idx),
            "val_keys": sorted(trainval_keys[i] for i in val_idx),
        })

    return {
        "seed": cfg.seed,
        "n_test_keys": n_test,
        "n_trainval_keys": len(trainval_keys),
        "n_folds": cfg.n_folds,
        "test_keys": test_keys,
        "trainval_keys": trainval_keys,
        "folds": folds,
    }


def build_manifest(
    cfg: V2Config,
    agg_stats: dict,
    keys_map: dict[str, str],
    generation_stats: dict,
    t_start: datetime,
    t_end: datetime,
) -> dict:
    try:
        git_hash = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO_ROOT, stderr=subprocess.DEVNULL, text=True,
        ).strip()
    except Exception:
        git_hash = "unknown"

    ciphers_meta = {
        "Ascon-AEAD128": AsconAEAD128().metadata,
        "GIFT-COFB": GiftCOFB().metadata,
        "Grain-128AEAD": Grain128AEAD().metadata,
        "Schwaemm256-128": Schwaemm256_128().metadata,
        "AES-128-ECB": AES128ECB().metadata,
    }

    return {
        "dataset_id": cfg.dataset_id,
        "created_at": t_start.isoformat(),
        "generation_elapsed_s": round((t_end - t_start).total_seconds(), 2),
        "generator_script": "scripts/generate_5class_v2.py",
        "generator_version": git_hash,
        "crypto_wrappers": ciphers_meta,
        "rng": {
            "mechanism": "CTR_DRBG (NIST SP 800-90A, AES-128, sem função de derivação)",
            "validation": "240/240 vetores CAVP oficiais (DRBGVS [AES-128 no df])",
            "streams": ["keys", "plaintext_text", "plaintext_source_choice",
                        "image_pool_shuffle", "prng_control"],
        },
        "parameters": {
            "n_keys": cfg.n_keys,
            "slots_per_key": cfg.slots_per_key,
            "total_slots": cfg.n_keys * cfg.slots_per_key,
            "algorithms_per_slot": 5,
            "total_cipher_samples": cfg.n_keys * cfg.slots_per_key * 5,
            "total_prng_samples": cfg.n_keys * cfg.slots_per_key,
            "total_samples": agg_stats["total_samples"],
            "plaintext_bytes": PLAINTEXT_BYTES,
            "image_source_probability_target": IMAGE_SOURCE_PROBABILITY,
            "seed": cfg.seed,
            "key_seed_offset": cfg.key_seed_offset,
            "version": cfg.version,
            "nonce_policy": {
                "mechanism": "contador global de 128 bits, incrementado por slot",
                "ascon_gift_cofb": "16 bytes diretos",
                "grain": "12 bytes menos significativos (96 bits)",
                "schwaemm256_128": "zero-pad nos 128 bits mais significativos de um campo de 32 bytes",
                "aes_ecb": "ignorado (modo sem nonce)",
            },
        },
        "generation_stats": generation_stats,
        "statistics": agg_stats,
        "keys_stored_separately": "data/interim/keyholdout_5class_v2_keys.json (NUNCA no parquet público)",
        # Aponta para o arquivo real de validação, não um texto estático
        # "pending" que nunca é atualizado (achado na verificação de
        # aderência): o validador escreve seu próprio JSON separado, e
        # deixar este campo congelado em "pending" mesmo depois da
        # validação rodar (com veredicto PASS) é enganoso para quem lê só
        # o manifesto. O nome do arquivo é fixo e previsível
        # (`validate_5class_v2.py` usa `{dataset_id}_validation.json`).
        "sanity_checks": f"ver {cfg.dataset_id}_validation.json "
                         f"(gerado por scripts/validate_5class_v2.py)",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-keys", type=int, default=300)
    parser.add_argument("--slots-per-key", type=int, default=100)
    parser.add_argument("--dataset-id", type=str, default="keyholdout_5class_v2")
    parser.add_argument(
        "--n-test-keys", type=int, default=60,
        help="Chaves reservadas para teste (80/20 do total; default 60 = "
             "20%% de 300, ajustar para smoke tests com --n-keys pequeno).",
    )
    parser.add_argument(
        "--keys-per-batch", type=int, default=20,
        help="Chaves processadas por lote antes de gravar no parquet "
             "(controla o pico de memória — ver docstring de generate_and_write).",
    )
    args = parser.parse_args()

    cfg = V2Config(
        n_keys=args.n_keys,
        slots_per_key=args.slots_per_key,
        dataset_id=args.dataset_id,
        n_test_keys=args.n_test_keys,
    )

    print(f"Gerando dataset v2: {cfg.n_keys} chaves x {cfg.slots_per_key} slots "
          f"x 5 algoritmos + PRNG = {cfg.n_keys * cfg.slots_per_key * 6} amostras "
          f"(lotes de {args.keys_per_batch} chaves)...")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    pq_path = OUT_DIR / f"{cfg.dataset_id}.parquet"

    t_start = datetime.now(timezone.utc)
    keys_map, generation_stats, agg_stats = generate_and_write(
        cfg, pq_path, keys_per_batch=args.keys_per_batch
    )
    t_end = datetime.now(timezone.utc)

    print(f"Geração concluída em {(t_end - t_start).total_seconds():.1f}s: "
          f"{agg_stats['total_samples']:,} amostras, "
          f"{agg_stats['total_ciphertext_bytes'] / 1e9:.2f} GB de ciphertext.")
    print(f"  plaintext_source real: {generation_stats}")
    print(f"Parquet salvo: {pq_path}")

    keys_path = INTERIM_DIR / f"{cfg.dataset_id}_keys.json"
    keys_path.write_text(json.dumps(keys_map, indent=2), encoding="utf-8")
    print(f"Chaves (interim, NUNCA versionar): {keys_path}")

    manifest = build_manifest(cfg, agg_stats, keys_map, generation_stats, t_start, t_end)
    manifest_path = OUT_DIR / f"{cfg.dataset_id}_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    print(f"Manifesto: {manifest_path}")

    folds = build_folds(list(keys_map.keys()), cfg)
    folds_path = OUT_DIR / "v2_folds.json"
    folds_path.write_text(json.dumps(folds, indent=2), encoding="utf-8")
    print(f"Partição de folds (canônica p/ todos os Caminhos): {folds_path}")


if __name__ == "__main__":
    main()
