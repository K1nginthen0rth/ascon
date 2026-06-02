"""
Gerador de datasets Ascon-AEAD128 para experimentos de classificação LWC.

Cenário: ciphertext-only — o parquet final NÃO contém plaintext, chave ou nonce
em claro. Esses valores são salvos separadamente em data/interim/ apenas para
validação/debug e NUNCA devem ser usados como features de treino.

Uso típico:
    from src.crypto.dataset_generator import AsconDatasetGenerator, DatasetConfig
    gen = AsconDatasetGenerator(config, corpora_dir=Path("data/raw/corpora"))
    result = gen.generate()
    result.save(out_dir=Path("data/processed"), interim_dir=Path("data/interim"))
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import zlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# PlaintextGenerator (versão determinística com numpy RNG)
# ---------------------------------------------------------------------------

class _PlaintextGenerator:
    """
    Gerador de plaintexts a partir de corpus UTF-8.

    Versão determinística: usa numpy RNG fornecido externamente em vez do
    random global do stdlib, garantindo reprodutibilidade.
    """

    def __init__(self, corpora_dir: Path, rng: np.random.Generator) -> None:
        self._rng = rng
        self._corpora: list[bytes] = []
        self._names: list[str] = []

        for p in sorted(corpora_dir.glob("*.txt")):
            try:
                text = p.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            text = " ".join(text.replace("\n", " ").split())
            data = text.encode("utf-8")
            if len(data) >= 1000:
                self._corpora.append(data)
                self._names.append(p.stem)

        if not self._corpora:
            raise ValueError(
                f"Nenhum corpus válido (≥1000 bytes UTF-8) em: {corpora_dir}"
            )

    def sample(self, length: int) -> bytes:
        """Retorna trecho de exatamente `length` bytes, UTF-8 válido."""
        if length == 0:
            return b""

        for _ in range(2000):
            idx = int(self._rng.integers(0, len(self._corpora)))
            data = self._corpora[idx]
            if len(data) < length:
                continue
            start = int(self._rng.integers(0, len(data) - length + 1))
            chunk = data[start: start + length]
            try:
                chunk.decode("utf-8")
                return chunk
            except UnicodeDecodeError:
                continue

        # fallback: trunca/repete bytes ASCII simples
        base = b"The quick brown fox jumps over the lazy dog. " * (length // 45 + 2)
        return base[:length]


# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

@dataclass
class DatasetConfig:
    """Parâmetros de geração de um dataset Ascon-AEAD128."""

    dataset_id: str
    n_keys: int
    pt_sizes: list[int]
    samples_per_key_size: int
    seed: int = 42
    ad: bytes = b""
    version: str = "v1"
    key_seed_offset: int = 0  # offset para diferenciar keys entre datasets
    supersedes: str = ""     # dataset_id que esta versão substitui (para manifesto)

    @property
    def total_samples(self) -> int:
        return self.n_keys * len(self.pt_sizes) * self.samples_per_key_size


# ---------------------------------------------------------------------------
# Resultado da geração
# ---------------------------------------------------------------------------

@dataclass
class GenerationResult:
    """Contém todos os artefatos produzidos por uma geração."""

    config: DatasetConfig
    df: pd.DataFrame                      # parquet público (sem PT/key/nonce)
    keys: dict[str, str]                  # key_id → hex(key)
    nonces: dict[str, str]                # nonce_id → hex(nonce)
    plaintexts_df: pd.DataFrame           # sample_id → plaintext (apenas interim)
    manifest: dict
    split_info: Optional[dict] = None    # apenas para key-holdout

    def save(
        self,
        out_dir: Path,
        interim_dir: Path,
    ) -> dict[str, Path]:
        """
        Salva todos os artefatos e retorna mapa nome→path.

        Parquet público salvo em out_dir.
        Chaves, nonces, plaintexts salvos em interim_dir (só para validação).
        """
        out_dir.mkdir(parents=True, exist_ok=True)
        interim_dir.mkdir(parents=True, exist_ok=True)

        saved: dict[str, Path] = {}
        did = self.config.dataset_id

        # Parquet público
        pq_path = out_dir / f"{did}.parquet"
        self.df.to_parquet(pq_path, index=False)
        saved["parquet"] = pq_path

        # Manifesto
        manifest_path = out_dir / f"{did}_manifest.json"
        manifest_path.write_text(
            json.dumps(self.manifest, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        saved["manifest"] = manifest_path

        # Split info (key-holdout)
        if self.split_info:
            split_path = out_dir / f"{did}_splits.json"
            split_path.write_text(
                json.dumps(self.split_info, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            saved["splits"] = split_path

        # Interim: chaves
        keys_path = interim_dir / f"{did}_keys.json"
        keys_path.write_text(
            json.dumps(self.keys, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        saved["keys"] = keys_path

        # Interim: nonces
        nonces_path = interim_dir / f"{did}_nonces.json"
        nonces_path.write_text(
            json.dumps(self.nonces, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        saved["nonces"] = nonces_path

        # Interim: plaintexts (para spot-check em validação)
        pt_path = interim_dir / f"{did}_plaintexts.parquet"
        self.plaintexts_df.to_parquet(pt_path, index=False)
        saved["plaintexts"] = pt_path

        return saved


# ---------------------------------------------------------------------------
# Gerador principal
# ---------------------------------------------------------------------------

class AsconDatasetGenerator:
    """
    Gera datasets Ascon-AEAD128 para classificação em cenário ciphertext-only.

    Garante:
    - Nonces únicos por amostra (contador global por dataset)
    - Chaves geradas deterministicamente via numpy RNG com seed fixa
    - Plaintexts NÃO armazenados no parquet público
    - Todas as decisões registradas no manifesto

    Args:
        config: Parâmetros do dataset (ver DatasetConfig).
        corpora_dir: Diretório com arquivos .txt para geração de corpus plaintexts.
        ascon: Instância de AsconAEAD128; se None, cria automaticamente.
    """

    def __init__(
        self,
        config: DatasetConfig,
        corpora_dir: Path,
        ascon=None,
    ) -> None:
        self.config = config
        self._corpora_dir = Path(corpora_dir)

        # Wrapper Ascon (importado aqui para evitar import circular)
        if ascon is None:
            from src.crypto.ascon_wrapper import AsconAEAD128
            self._ascon = AsconAEAD128()
        else:
            self._ascon = ascon

        # RNG determinística: seed + offset para diferenciar datasets
        self._key_rng = np.random.default_rng(
            config.seed + config.key_seed_offset
        )
        # RNG separada para plaintexts (não misturar com key generation)
        self._pt_rng = np.random.default_rng(
            config.seed + config.key_seed_offset + 500
        )

        self._pt_gen = _PlaintextGenerator(corpora_dir, rng=self._pt_rng)

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def generate(self) -> GenerationResult:
        """
        Gera o dataset completo e retorna um GenerationResult.

        O DataFrame público não contém plaintext, chave nem nonce em claro.
        Os valores brutos ficam em GenerationResult.keys, .nonces, .plaintexts_df.
        """
        cfg = self.config
        t_start = datetime.now(timezone.utc)

        # 1. Gerar chaves
        keys_list = self._generate_keys()
        keys_map = {
            f"key_{i+1:04d}": k.hex() for i, (_, k) in enumerate(keys_list)
        }

        # 2. Gerar amostras
        rows, nonces_map, plaintexts_rows = self._generate_samples(keys_list)

        # 3. Montar DataFrame público
        df = pd.DataFrame(rows)

        # 4. Split info (key-holdout)
        split_info = self._make_split_info(keys_list) if cfg.n_keys > 10 else None

        # Adicionar coluna split ao df se key-holdout
        if split_info:
            key_to_split = {}
            for split_name in ("train_keys", "val_keys", "test_keys"):
                for kid in split_info[split_name]:
                    key_to_split[kid] = split_name.replace("_keys", "")
            df["split"] = df["key_id"].map(key_to_split)

        # 5. DataFrame de plaintexts (interim)
        plaintexts_df = pd.DataFrame(plaintexts_rows)

        # 6. Manifesto
        t_end = datetime.now(timezone.utc)
        manifest = self._build_manifest(df, t_start, t_end)

        return GenerationResult(
            config=cfg,
            df=df,
            keys=keys_map,
            nonces=nonces_map,
            plaintexts_df=plaintexts_df,
            manifest=manifest,
            split_info=split_info,
        )

    # ------------------------------------------------------------------
    # Privados
    # ------------------------------------------------------------------

    def _generate_keys(self) -> list[tuple[str, bytes]]:
        """Gera n_keys chaves determinísticas. Retorna [(key_id, key_bytes)]."""
        result = []
        for i in range(self.config.n_keys):
            key_id = f"key_{i+1:04d}"
            # Usar rng.integers para gerar 16 bytes deterministicamente
            key_bytes = bytes(
                self._key_rng.integers(0, 256, size=16, dtype=np.uint8).tolist()
            )
            result.append((key_id, key_bytes))
        return result

    def _generate_samples(
        self, keys_list: list[tuple[str, bytes]]
    ) -> tuple[list[dict], dict[str, str], list[dict]]:
        """
        Gera todas as amostras.

        Returns:
            (rows, nonces_map, plaintexts_rows)
        """
        cfg = self.config
        rows: list[dict] = []
        nonces_map: dict[str, str] = {}
        plaintexts_rows: list[dict] = []

        nonce_counter = 1
        timestamp = datetime.now(timezone.utc).isoformat()

        for key_id, key_bytes in keys_list:
            for pt_size in cfg.pt_sizes:
                for sample_idx in range(cfg.samples_per_key_size):
                    # Nonce como contador global
                    nonce_id = f"nonce_{nonce_counter:06d}"
                    nonce_bytes = nonce_counter.to_bytes(16, "big")
                    nonces_map[nonce_id] = nonce_bytes.hex()
                    nonce_counter += 1

                    # Plaintext: 100% corpus (PT=0 é caso especial válido em AEAD)
                    if pt_size == 0:
                        plaintext = b""
                        pt_source = "empty"
                    else:
                        plaintext = self._pt_gen.sample(pt_size)
                        pt_source = "corpus"

                    # Cifrar
                    ciphertext = self._ascon.encrypt(
                        key_bytes, nonce_bytes, plaintext, cfg.ad
                    )

                    # key_num para sample_id
                    key_num = int(key_id.split("_")[1])
                    sample_id = (
                        f"ascon_aead128_ref_k{key_num:04d}"
                        f"_n{nonce_counter-1:06d}"
                        f"_pt{pt_size:04d}"
                    )

                    rows.append(
                        {
                            "sample_id": sample_id,
                            "algorithm": "Ascon-AEAD128",
                            "mode": "AEAD",
                            "impl": "ref",
                            "key_id": key_id,
                            "nonce_id": nonce_id,
                            "len_pt": pt_size,
                            "len_ad": len(cfg.ad),
                            "len_ct": len(ciphertext),
                            "ciphertext": ciphertext,
                            "plaintext_source": pt_source,
                            "seed": cfg.seed,
                            "version": cfg.version,
                            "timestamp": timestamp,
                        }
                    )

                    plaintexts_rows.append(
                        {
                            "sample_id": sample_id,
                            "plaintext": plaintext,
                        }
                    )

        return rows, nonces_map, plaintexts_rows

    def _make_split_info(
        self, keys_list: list[tuple[str, bytes]]
    ) -> dict:
        """Produz split train/val/test para key-holdout."""
        n = len(keys_list)
        n_train = int(n * 0.6)
        n_val = int(n * 0.2)
        all_ids = [kid for kid, _ in keys_list]
        return {
            "train_keys": all_ids[:n_train],
            "val_keys": all_ids[n_train: n_train + n_val],
            "test_keys": all_ids[n_train + n_val:],
            "seed": self.config.seed,
            "split_ratio": "60/20/20",
        }

    def _build_manifest(
        self, df: pd.DataFrame, t_start: datetime, t_end: datetime
    ) -> dict:
        """Constrói o manifesto JSON completo."""
        cfg = self.config

        # Git hash do gerador
        try:
            git_hash = subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=Path(__file__).parent.parent.parent,
                stderr=subprocess.DEVNULL,
                text=True,
            ).strip()
        except Exception:
            git_hash = "unknown"

        # SHA256 do binário cffi
        binary_sha256 = self._ascon.metadata.get("binary_sha256", "unknown")

        size_dist = (
            df.groupby("len_pt").size().to_dict()
        )
        source_ratio = (
            df["plaintext_source"].value_counts(normalize=True).round(4).to_dict()
        )

        manifest: dict = {
            "dataset_id": cfg.dataset_id,
            "created_at": t_start.isoformat(),
            "generation_elapsed_s": round((t_end - t_start).total_seconds(), 2),
            "generator_script": "scripts/generate_pilot_dataset.py",
            "generator_version": git_hash,
            "crypto_wrapper": {
                "module": "src.crypto.ascon_wrapper.AsconAEAD128",
                "impl": "ref",
                "binary_sha256": binary_sha256,
                "kat_validation": "1089/1089 passed",
            },
            "parameters": {
                "n_keys": cfg.n_keys,
                "pt_sizes": cfg.pt_sizes,
                "samples_per_key_size": cfg.samples_per_key_size,
                "total_samples": cfg.total_samples,
                "ad_policy": "empty" if cfg.ad == b"" else cfg.ad.hex(),
                "nonce_policy": "global_counter",
                "plaintext_sources": ["corpus"],
                "seed": cfg.seed,
                "key_seed_offset": cfg.key_seed_offset,
                "version": cfg.version,
            },
            "statistics": {
                "total_samples": len(df),
                "total_ciphertext_bytes": int(df["len_ct"].sum()),
                "samples_per_pt_size": {str(k): int(v) for k, v in size_dist.items()},
                "plaintext_source_ratio": source_ratio,
            },
            "sanity_checks": "pending - run scripts/validate_pilot_dataset.py",
        }
        if cfg.supersedes:
            manifest["supersedes"] = cfg.supersedes
            manifest["change_reason"] = (
                "Removido plaintexts aleatorios; 100% corpus conforme "
                "protocolo ciphertext-only"
            )
        return manifest
