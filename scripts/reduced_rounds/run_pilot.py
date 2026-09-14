"""
Fase 0 do estudo de sensibilidade a rodadas reduzidas: piloto go/no-go.

Gera um dataset PEQUENO (dezenas de chaves, não 300), só corpus de texto
(SPGC — a fração de imagem do protocolo v2 completo fica de fora aqui de
propósito, simplificação aceitável para um piloto de sensibilidade, não
para o experimento final), cifra os DOIS lados de um par sob a MESMA
chave/nonce/plaintext (encadeado, como no protocolo de produção), extrai as
641 features de produção e treina um classificador rápido com key-holdout.

Não usa `run_v2_caminho_a.py` nem o parquet de produção — é um caminho
enxuto e paralelo, cujo único objetivo é responder rápido "existe sinal
nesta configuração, sim ou não" antes de investir na Fase 3/4 (grade
completa, 5.000 amostras/config).

Uso:
    python scripts/reduced_rounds/run_pilot.py --config asimetrico
    python scripts/reduced_rounds/run_pilot.py --config simetrico
    python scripts/reduced_rounds/run_pilot.py --config todos
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src" / "crypto"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.ensemble import RandomForestClassifier  # noqa: E402
from sklearn.metrics import f1_score, confusion_matrix  # noqa: E402

from src.crypto.ctr_drbg import CTRDRBG  # noqa: E402
from src.features.extractor import CiphertextFeatureExtractor  # noqa: E402
from scripts.reduced_rounds.build_variant import build_ascon, build_gift  # noqa: E402
from scripts.reduced_rounds.reduced_wrapper import ReducedRoundsCipher  # noqa: E402

CORPORA_DIR = REPO_ROOT / "data" / "raw" / "corpora"
PLAINTEXT_BYTES = 65536
PILOT_OUT = REPO_ROOT / "build" / "reduced_rounds" / "pilot"
PILOT_OUT.mkdir(parents=True, exist_ok=True)

N_KEYS = 40
SLOTS_PER_KEY = 10
N_TEST_KEYS = 8  # 32 treino/val, 8 teste — mesma proporção ~80/20 do v2
PILOT_SEED = 999001  # deliberadamente fora do espaço de seeds de produção (6000+)


# ---------------------------------------------------------------------------
# Configurações do piloto (ver plano corrigido — reanálise de 2026-09-10)
# ---------------------------------------------------------------------------

CONFIGS = {
    "asimetrico": dict(
        label="Ascon pb=1 (extremo) vs GIFT-COFB completo (40) — controle de instrumento",
        ascon_pa=12, ascon_pb=1, gift_rounds=40,
    ),
    "simetrico": dict(
        label="Ascon pb=1 (extremo) vs GIFT-COFB 5 rodadas (extremo) — os dois enfraquecidos",
        ascon_pa=12, ascon_pb=1, gift_rounds=5,
    ),
    "asimetrico_inverso": dict(
        label="Ascon completo (12/8) vs GIFT-COFB 5 rodadas (piso do fixslicing) — "
              "controle de instrumento, outro lado da assimetria",
        ascon_pa=12, ascon_pb=8, gift_rounds=5,
    ),
    # --- init reduzida (correção de 2026-09-11) --------------------------
    # As 3 configs acima reduzem só o `pb` (permutação de dados) e deram acaso
    # nas três, em escala completa. O `pa` (inicialização, 12 rodadas) ficou
    # intacto, e é ele que mistura o estado ANTES do laço de dados: com pa=12,
    # o estado que entra na fase de dados já é de alta entropia, então mesmo
    # pb=1 produz saída de marginal limpa. Reduzir `pa` ataca a origem: estado
    # inicial mal misturado contamina o keystream inteiro, e aí a estrutura
    # deve aparecer até em feature marginal.
    "init_fraca": dict(
        label="Ascon pa=1 (inicialização quase nula) vs GIFT-COFB completo (40)",
        ascon_pa=1, ascon_pb=8, gift_rounds=40,
    ),
    "init_fraca_2": dict(
        label="Ascon pa=2 vs GIFT-COFB completo (40) — um passo acima, p/ o limiar",
        ascon_pa=2, ascon_pb=8, gift_rounds=40,
    ),
    "init_fraca_4": dict(
        label="Ascon pa=4 vs GIFT-COFB completo (40) — um passo acima, p/ o limiar",
        ascon_pa=4, ascon_pb=8, gift_rounds=40,
    ),
}


class _TextPlaintextSampler:
    """Reduzido de `generate_5class_v2.py::_TextPlaintextSampler` — só texto,
    mesma lógica de amostragem via CTR_DRBG."""

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
            raise ValueError(f"Nenhum corpus com >= {PLAINTEXT_BYTES} bytes em: {corpora_dir}")

    def sample(self) -> bytes:
        for _ in range(2000):
            idx = self._drbg.randint(0, len(self._corpora))
            data = self._corpora[idx]
            start = self._drbg.randint(0, len(data) - PLAINTEXT_BYTES + 1)
            chunk = data[start:start + PLAINTEXT_BYTES]
            try:
                chunk.decode("utf-8")
                return chunk
            except UnicodeDecodeError:
                continue
        raise RuntimeError("Falha ao amostrar trecho UTF-8 válido.")


def _generate_pairs(ascon_pa: int, ascon_pb: int, gift_rounds: int,
                     n_keys: int = N_KEYS, slots_per_key: int = SLOTS_PER_KEY,
                     seed: int = PILOT_SEED) -> pd.DataFrame:
    ascon_pyd = build_ascon(ascon_pa, ascon_pb)
    gift_pyd = build_gift(gift_rounds)
    ascon = ReducedRoundsCipher(ascon_pyd, "ascon")
    gift = ReducedRoundsCipher(gift_pyd, "gift")

    key_drbg = CTRDRBG(seed=seed, label="pilot-keys")
    pt_drbg = CTRDRBG(seed=seed, label="pilot-plaintext")
    sampler = _TextPlaintextSampler(CORPORA_DIR, pt_drbg)

    rows = []
    for k in range(n_keys):
        key_id = f"pilot_k{k:04d}"
        key = key_drbg.random_key(16)
        for slot in range(slots_per_key):
            pt = sampler.sample()
            counter = (k * slots_per_key + slot).to_bytes(16, "big")
            sample_id = f"{key_id}_s{slot:03d}"
            ct_ascon = ascon.encrypt(key, counter, pt)
            ct_gift = gift.encrypt(key, counter, pt)
            rows.append(dict(sample_id=f"{sample_id}_ascon", algorithm="ascon_reduced",
                              key_id=key_id, len_pt=len(pt), len_ct=len(ct_ascon),
                              ciphertext=ct_ascon))
            rows.append(dict(sample_id=f"{sample_id}_gift", algorithm="gift_reduced",
                              key_id=key_id, len_pt=len(pt), len_ct=len(ct_gift),
                              ciphertext=ct_gift))
    return pd.DataFrame(rows)


def _key_holdout_split(key_ids: list[str], n_test_keys: int = N_TEST_KEYS,
                        seed: int = PILOT_SEED) -> tuple[set[str], set[str]]:
    ordered = sorted(set(key_ids))
    rng = np.random.default_rng(seed)
    rng.shuffle(ordered)
    test_keys = set(ordered[:n_test_keys])
    train_keys = set(ordered[n_test_keys:])
    return train_keys, test_keys


def run_config(name: str, n_keys: int = N_KEYS, slots_per_key: int = SLOTS_PER_KEY,
               n_test_keys: int = N_TEST_KEYS, seed: int = PILOT_SEED,
               out_dir: Path = PILOT_OUT) -> dict:
    cfg = CONFIGS[name]
    print(f"\n{'=' * 70}\n[{name}] {cfg['label']}\n{'=' * 70}")

    print(f"Gerando {n_keys * slots_per_key * 2} criptogramas "
          f"({n_keys} chaves x {slots_per_key} slots x 2 classes)...")
    df_ct = _generate_pairs(cfg["ascon_pa"], cfg["ascon_pb"], cfg["gift_rounds"],
                             n_keys=n_keys, slots_per_key=slots_per_key, seed=seed)

    ct_path = out_dir / f"pilot_{name}_ciphertexts.parquet"
    df_ct.to_parquet(ct_path, index=False)

    print("Extraindo 641 features (12 famílias)...")
    extractor = CiphertextFeatureExtractor()
    df_feat = extractor.extract_dataset(ct_path, n_jobs=-1, show_progress=True)

    train_keys, test_keys = _key_holdout_split(
        df_feat["key_id"].unique().tolist(), n_test_keys=n_test_keys, seed=seed)
    train_df = df_feat[df_feat["key_id"].isin(train_keys)]
    test_df = df_feat[df_feat["key_id"].isin(test_keys)]

    feature_cols = [c for c in df_feat.columns
                    if c not in ("sample_id", "algorithm", "key_id", "len_pt", "len_ct")]
    X_train, y_train = train_df[feature_cols].values, train_df["algorithm"].values
    X_test, y_test = test_df[feature_cols].values, test_df["algorithm"].values

    clf = RandomForestClassifier(n_estimators=300, random_state=7, n_jobs=-1)
    clf.fit(X_train, y_train)
    y_pred = clf.predict(X_test)

    f1 = f1_score(y_test, y_pred, average="macro")
    cm = confusion_matrix(y_test, y_pred, labels=sorted(set(y_test)))

    # bootstrap CI simples sobre o F1, seed=42 (convenção do projeto)
    boot_rng = np.random.default_rng(42)
    n_test = len(y_test)
    boot_f1s = []
    for _ in range(1000):
        idx = boot_rng.integers(0, n_test, n_test)
        boot_f1s.append(f1_score(np.array(y_test)[idx], np.array(y_pred)[idx],
                                  average="macro", zero_division=0))
    ci_lo, ci_hi = np.percentile(boot_f1s, [2.5, 97.5])

    print(f"\nF1-macro = {f1:.4f}  IC95%=[{ci_lo:.4f}, {ci_hi:.4f}]  "
          f"(treino: {len(train_df)} amostras / {len(train_keys)} chaves, "
          f"teste: {len(test_df)} amostras / {len(test_keys)} chaves)")
    print(f"Matriz de confusão {sorted(set(y_test))}:\n{cm}")

    return dict(config=name, f1_macro=f1, ci_lo=ci_lo, ci_hi=ci_hi,
                n_train=len(train_df), n_test=len(test_df), confusion_matrix=cm.tolist())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", choices=list(CONFIGS) + ["todos"], default="todos")
    args = parser.parse_args()

    targets = list(CONFIGS) if args.config == "todos" else [args.config]
    results = [run_config(name) for name in targets]

    print(f"\n{'=' * 70}\nRESUMO\n{'=' * 70}")
    for r in results:
        print(f"  {r['config']:12s} F1-macro={r['f1_macro']:.4f} "
              f"IC95%=[{r['ci_lo']:.4f}, {r['ci_hi']:.4f}]")
