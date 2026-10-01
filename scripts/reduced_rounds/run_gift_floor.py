"""
Piso de rodadas do GIFT-COFB, em ciphertext-only, contra aleatório uniforme.

Pergunta: a partir de quantas rodadas o criptograma do GIFT-COFB deixa de ser
separável de uma sequência uniforme, observando só o que um adversário passivo
vê? A resposta é o piso: abaixo dele, a versão reduzida é comprovadamente
insegura, porque um classificador genérico a distingue do aleatório.

Modelo de acesso (idêntico ao de `run_pares_ct_only.py`, sem relaxamento):
mesma chave (mesmo dispositivo), nonces públicos de contador consecutivos
(2c, 2c+1), plaintexts DIFERENTES e DESCONHECIDOS. O adversário observa o XOR
do payload mais o XOR das tags: 640 bits. Nada de plaintext escolhido,
diferença escolhida ou reuso de nonce.

Mensagem de 64 bytes (4 blocos), e não os 64 KB do dataset v2. Dois motivos:
pacote curto é o caso típico de IoT, e as features de par já só consumiam os
primeiros blocos mais a tag, então os 64 KB só custariam tempo. Em Python puro
a diferença é entre ~1 ms e ~700 ms por mensagem.

Classe negativa: ALEATÓRIO UNIFORME, que é a definição padrão de distinguidor
e o que a literatura usa (decidido em 19/09). Para um AEAD ideal, C1 xor C2 é
uniforme mesmo com plaintexts estruturados, porque os keystreams são uniformes
e independentes; então qualquer desvio da uniformidade é falha da cifra. As
amostras aleatórias recebem o mesmo `key_idx` das reais para que o key-holdout
e a decisão por dispositivo continuem definidos: a "chave" aleatória
representa o dispositivo ideal de referência.

Braços de plaintext: `texto`, `imagem` e `aleatorio`. O braço `aleatorio` é o
mais informativo dos três, e não pelo motivo que parecia à primeira vista.

Com rodadas reduzidas, C1 xor C2 = (Y1 xor Y2) xor (P1 xor P2). A intenção
original do braço era isolar a estrutura da cifra zerando o termo do
plaintext. Ele não faz isso, e não tem como: se P1 e P2 são uniformes e
independentes da chave, P1 xor P2 é uniforme e independente de Y1 xor Y2,
logo o XOR inteiro é EXATAMENTE uniforme, por mais fraca que a cifra seja.
Nenhum detector pode superar o acaso ali. O mesmo argumento vale para os
criptogramas observados separadamente, então não é limitação da representação
por pares.

O que o braço mede, então, é o teto do próprio modelo de ameaça: em
ciphertext-only, a única coisa explorável é a redundância do plaintext. Um
piso medido aqui é sempre uma afirmação conjunta sobre a cifra E sobre a
fonte, nunca sobre a cifra sozinha. Medido: com plaintext uniforme os quatro
ficam no acaso em TODAS as contagens de rodada, inclusive a mínima.

Granularidade: usa `PureGiftCOFB`, que varre de 1 a 40 rodadas uma a uma. O
wrapper compilado (fixsliced) só desce de 5 em 5 e esconderia o piso, que deve
cair abaixo de 5. Ver `gift_pure_cipher.py`.

Dois modos:
  sweep (padrão) — só o ajuste final (treino nas chaves de treino, avaliação
    nas de teste). Barato, serve para localizar o piso ao longo das 40 rodadas.
  full — validação cruzada de 5 folds mais o ajuste final, o protocolo
    completo. Para a região de fronteira, depois que o sweep mostrar onde ela
    está.

Curva de orçamento: além da decisão por amostra, agrega por dispositivo em
bolsas de 1, 10 e 100 pares (média do log-odds), respondendo "com quantas
mensagens observadas o piso aparece". A agregação é a combinação de escores
independentes, e não um modelo multi-par, justamente porque Gohr, Leander e
Neumann (ePrint 2022/1521) mostraram que ganhos alegados de modelos multi-par
costumam sumir quando comparados dessa forma.

Uso:
    python scripts/reduced_rounds/run_gift_floor.py --smoke
    python scripts/reduced_rounds/run_gift_floor.py --rounds 1 2 3 4 5 6 7 8 40
    python scripts/reduced_rounds/run_gift_floor.py                 # 1..40
    python scripts/reduced_rounds/run_gift_floor.py --rounds 3 4 5 --mode full
    python scripts/reduced_rounds/run_gift_floor.py --arms texto aleatorio --rounds 1 2 3 4 5 6
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src" / "crypto"))

import numpy as np  # noqa: E402
from sklearn.model_selection import GroupKFold  # noqa: E402
from sklearn.pipeline import Pipeline  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402

from scripts.generate_5class_v2 import (  # noqa: E402
    CORPORA_DIR, IMAGES_DIR, IMAGES_MANIFEST, PLAINTEXT_BYTES,
    _ImagePlaintextSampler, _TextPlaintextSampler,
)
from scripts.reduced_rounds.gift_pure_cipher import MAX_ROUNDS, PureGiftCOFB  # noqa: E402
from scripts.run_v2_caminho_a import build_models, get_proba  # noqa: E402
from src.crypto.ctr_drbg import CTRDRBG  # noqa: E402
from src.eval.reporting import report_eval  # noqa: E402

SEED_GEN = 999003      # distinto do runner de pares: outro conjunto de amostras
SEED_SPLIT = 42
SEED_MODEL = 7
SEED_BOOT = 42
PAIRS_PER_KEY = 100
MSG_BYTES = 64         # mensagem curta: 4 blocos de 16 bytes
HEAD = 64              # payload observado (aqui, a mensagem inteira)
ABYTES = 16            # tag do GIFT-COFB
BAG_SIZES = (1, 10, 100)
NEEDS_SCALING = {"LinearSVC", "LogisticRegression"}
DEFAULT_MODELS = ("RandomForest", "XGBoost", "LogisticRegression")

OUT_DIR = REPO_ROOT / "build" / "reduced_rounds" / "gift_floor"


def _log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def _git_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT,
                              capture_output=True, text=True, check=True).stdout.strip()
    except Exception:  # noqa: BLE001
        return "desconhecido"


def _xor_head_tag(a: bytes, b: bytes) -> np.ndarray:
    return (np.frombuffer(a[:HEAD] + a[-ABYTES:], np.uint8)
            ^ np.frombuffer(b[:HEAD] + b[-ABYTES:], np.uint8))


def _e_chave_de_rodada(k: str) -> bool:
    """`r7` é rodada; `random` e `key_idx` não são (o prefixo 'r' sozinho engana)."""
    return len(k) > 1 and k[0] == "r" and k[1:].isdigit()


_FP = "_fingerprint"


def impressao_digital(**params) -> np.ndarray:
    """Parâmetros que DEFINEM os dados de um cache, para gravar dentro dele."""
    return np.array(json.dumps(params, sort_keys=True))


def conferir_cache(store: dict, esperada: np.ndarray, cache: Path) -> None:
    """Recusa um cache gerado com outros parâmetros.

    Sem isto o reuso é cego: o nome do arquivo só carrega o algoritmo, o braço
    e o número de chaves, então um `.npz` gerado com outro `MSG_BYTES`, outra
    largura de tag ou outra seed voltaria em silêncio. Aconteceu de verdade o
    risco quando `MSG_BYTES` passou de 65536 para 64 no meio do estudo.

    Caches anteriores ao carimbo não têm o campo; nesse caso sobra a checagem
    de forma, que ainda pega o erro mais comum (número de chaves diferente).
    """
    n_esperado = json.loads(str(esperada))["n_keys"] * PAIRS_PER_KEY
    if _FP not in store:
        linhas = len(store.get("key_idx", ()))
        if linhas != n_esperado:
            raise ValueError(
                f"{cache.name}: cache tem {linhas} linhas, esperado {n_esperado}. "
                "Apague o arquivo e gere de novo.")
        _log(f"  aviso: {cache.name} é anterior ao carimbo de parâmetros; "
             "só a forma foi conferida")
        return
    if str(store[_FP]) != str(esperada):
        raise ValueError(
            f"{cache.name} foi gerado com outros parâmetros.\n"
            f"  no arquivo: {store[_FP]}\n"
            f"  pedido    : {esperada}\n"
            "Apague o arquivo e gere de novo.")
    linhas = len(store.get("key_idx", ()))
    if linhas != n_esperado:
        raise ValueError(
            f"{cache.name}: carimbo bate mas tem {linhas} linhas, esperado "
            f"{n_esperado}. Arquivo corrompido; apague e gere de novo.")


def generate(arm: str, n_keys: int, rounds: list[int], cache: Path) -> dict:
    """XOR (4 blocos + tag) de pares consecutivos, por número de rodadas.

    Incremental: se o cache já tem parte das rodadas pedidas, só gera as que
    faltam. As chaves, nonces e plaintexts são reproduzidos pelo mesmo DRBG
    com a mesma seed, então rodadas geradas em passadas diferentes continuam
    comparáveis entre si (Regra de Ouro 6).
    """
    fp = impressao_digital(algo="gift", arm=arm, n_keys=n_keys,
                           pairs_per_key=PAIRS_PER_KEY, msg_bytes=MSG_BYTES,
                           head=HEAD, tag_bytes=ABYTES, seed_gen=SEED_GEN)

    store: dict[str, np.ndarray] = {}
    if cache.exists():
        z = np.load(cache, allow_pickle=False)
        store = {k: z[k] for k in z.files}
        conferir_cache(store, fp, cache)

    faltando = [r for r in rounds if f"r{r}" not in store]
    if not faltando:
        _log(f"[{arm}] cache completo em {cache.name} (rodadas {rounds})")
        return store

    _log(f"[{arm}] gerando rodadas {faltando} ({n_keys} chaves x {PAIRS_PER_KEY} pares)")
    # `validate` fica no padrão (True): a checagem contra o binário de produção
    # é cacheada por processo, então roda uma vez e vale para todas as
    # contagens. Antes era condicionada a `r == MAX_ROUNDS` mais uma linha
    # extra de rede; a linha extra existia só para consertar a condição.
    ciphers = {r: PureGiftCOFB(r) for r in faltando}

    key_drbg = CTRDRBG(seed=SEED_GEN, label="gift-floor-keys")
    pt_drbg = CTRDRBG(seed=SEED_GEN, label=f"gift-floor-pt-{arm}")
    rnd_drbg = CTRDRBG(seed=SEED_GEN, label=f"gift-floor-random-{arm}")

    if arm == "texto":
        sample = _TextPlaintextSampler(CORPORA_DIR, pt_drbg).sample
        image_sampler = None
    elif arm == "imagem":
        image_sampler = _ImagePlaintextSampler(IMAGES_DIR, IMAGES_MANIFEST, pt_drbg)
        sample = lambda: image_sampler.sample()[0]  # noqa: E731
    elif arm == "aleatorio":
        # Braço de desambiguação: plaintext uniforme faz P1 xor P2 ser uniforme,
        # então o que sobra no C1 xor C2 é só a estrutura da própria cifra.
        # Comparado com o braço "texto", separa "a cifra é fraca" de "a cifra
        # fraca deixa vazar a redundância do texto".
        sample = lambda: pt_drbg.generate(MSG_BYTES)  # noqa: E731
        image_sampler = None
    else:
        raise ValueError(f"braço desconhecido: {arm}")

    n = n_keys * PAIRS_PER_KEY
    novo = {f"r{r}": np.zeros((n, HEAD + ABYTES), np.uint8) for r in faltando}
    precisa_random = "random" not in store
    if precisa_random:
        novo["random"] = np.zeros((n, HEAD + ABYTES), np.uint8)
    key_idx = np.repeat(np.arange(n_keys), PAIRS_PER_KEY).astype(np.int32)

    n_resampled = 0
    t0 = time.time()
    for k in range(n_keys):
        key = key_drbg.random_key(16)
        for j in range(PAIRS_PER_KEY):
            p1, p2 = sample()[:MSG_BYTES], sample()[:MSG_BYTES]
            while p2 == p1:  # par com plaintext igual sairia do modelo de acesso
                p2 = sample()[:MSG_BYTES]
                n_resampled += 1
            assert len(p1) == len(p2) == MSG_BYTES
            c = 2 * (k * PAIRS_PER_KEY + j)
            n1, n2 = c.to_bytes(16, "big"), (c + 1).to_bytes(16, "big")
            i = k * PAIRS_PER_KEY + j
            for r, cipher in ciphers.items():
                novo[f"r{r}"][i] = _xor_head_tag(cipher.encrypt(key, n1, p1),
                                                 cipher.encrypt(key, n2, p2))
            if precisa_random:
                novo["random"][i] = np.frombuffer(rnd_drbg.generate(HEAD + ABYTES), np.uint8)
        if (k + 1) % 25 == 0 or k + 1 == n_keys:
            _log(f"[{arm}] chaves {k + 1}/{n_keys} ({time.time() - t0:.0f}s)")

    if "key_idx" in store:
        assert np.array_equal(store["key_idx"], key_idx), "cache com nº de chaves diferente"
    store.update(novo)
    store["key_idx"] = key_idx
    store[_FP] = fp
    np.savez(cache, **store)

    meta_path = cache.with_suffix(".json")
    meta = dict(arm=arm, n_keys=n_keys, pairs_per_key=PAIRS_PER_KEY, seed_gen=SEED_GEN,
                rounds_presentes=sorted(int(k[1:]) for k in store if _e_chave_de_rodada(k)),
                msg_bytes=MSG_BYTES,
                head_bytes=HEAD, tag_bytes=ABYTES, classe_negativa="aleatório uniforme (CTR_DRBG)",
                nonce="contador big-endian 16 bytes, par (2c, 2c+1)",
                plaintexts="P1 != P2, desconhecidos, mesmos para todas as rodadas",
                n_resampled_equal_plaintext=n_resampled,
                n_reused_images=(image_sampler.n_reused if image_sampler else None),
                git_commit=_git_commit(), generated_at=datetime.now(timezone.utc).isoformat())
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    _log(f"[{arm}] geração de {faltando} concluída em {time.time() - t0:.0f}s -> {cache.name}")
    return store


def _bags(proba: np.ndarray, y: np.ndarray, keys: np.ndarray, bag: int):
    """Agrega o log-odds em bolsas de `bag` pares dentro de cada (chave, classe).

    Levanta se a bolsa não couber, em vez de devolver arrays vazios: sem isso o
    erro só aparecia lá dentro do `report_eval`, como "empty input array" do
    sklearn, sem dizer que a causa era o tamanho da bolsa.
    """
    if not isinstance(bag, int) or bag < 1:
        raise ValueError(f"bolsa deve ser inteiro >= 1, recebeu {bag!r}")
    logit = np.log(np.clip(proba[:, 1], 1e-12, 1)) - np.log(np.clip(proba[:, 0], 1e-12, 1))
    by, bk, bs = [], [], []
    sobras, maior = 0, 0
    for k in np.unique(keys):
        for lab in (0, 1):
            idx = np.where((keys == k) & (y == lab))[0]
            maior = max(maior, len(idx))
            n_bolsas = len(idx) // bag
            sobras += len(idx) - n_bolsas * bag
            for b in range(n_bolsas):
                by.append(lab)
                bk.append(k)
                bs.append(logit[idx[b * bag:(b + 1) * bag]].mean())
    if not by:
        raise ValueError(
            f"bolsa de {bag} não cabe: nenhum par (chave, classe) tem {bag} "
            f"amostras (máximo disponível: {maior})")
    if sobras:
        # Resto descartado não é erro, mas precisa aparecer: uma bolsa que não
        # divide o número de amostras joga fora parte do conjunto de teste.
        _log(f"  aviso: bolsa {bag} descartou {sobras} amostra(s) de resto")
    p1 = 1.0 / (1.0 + np.exp(-np.clip(np.array(bs), -50, 50)))
    return np.array(by), np.column_stack([1 - p1, p1]), np.array(bk)


def run_config(arm: str, rounds: int, data: dict, n_keys: int, n_test: int,
               n_cv: int, report_dir: Path, mode: str, model_names: list[str]) -> None:
    run_id = f"gift_floor_{arm}_r{rounds}"
    braco = f"gift_floor_{arm}"
    class_names = ["aleatório uniforme", f"GIFT-COFB {rounds} rodadas"]
    _log(f"===== {run_id}: GIFT-COFB {rounds} rodadas vs aleatório, plaintext={arm} =====")

    n = n_keys * PAIRS_PER_KEY
    X = np.vstack([np.unpackbits(data["random"], axis=1),
                   np.unpackbits(data[f"r{rounds}"], axis=1)]).astype(np.float32)
    y = np.concatenate([np.zeros(n, int), np.ones(n, int)])
    kidx = np.concatenate([data["key_idx"], data["key_idx"]])
    key_ids = np.array([f"k{k:04d}" for k in kidx])
    sample_ids = np.array([f"{arm}_r{rounds}_k{k:04d}_p{i % PAIRS_PER_KEY:03d}"
                           f"_{'gift' if lab else 'rand'}"
                           for i, (k, lab) in enumerate(zip(kidx, y))])

    keys = np.arange(n_keys)
    np.random.default_rng(SEED_SPLIT).shuffle(keys)
    te = np.isin(kidx, keys[:n_test])
    tr = ~te

    # Diagnóstico sem modelo: viés por bit no primeiro bloco, só no treino.
    sel = tr & (y == 1)
    p = X[sel, :128].mean(axis=0)
    z = (p - 0.5) / np.sqrt(0.25 / sel.sum())
    _log(f"  diagnóstico (treino) bloco 1: max|z|={np.abs(z).max():.1f}, "
         f"bits com |z|>6: {(np.abs(z) > 6).sum()}/128")

    extra_base = dict(rounds=rounds, arm=arm, n_features=X.shape[1], seed_gen=SEED_GEN,
                      runner="run_gift_floor", seed_gen_runner=SEED_GEN,
                      classe_negativa="aleatório uniforme",
                      access_model="mesma chave, nonces consecutivos (2c,2c+1), P1!=P2 desconhecidos",
                      diag_bloco1_max_abs_z=round(float(np.abs(z).max()), 2))

    def fit_eval(name, model, idx_tr, idx_ev, fold):
        if name in NEEDS_SCALING:
            model = Pipeline([("scaler", StandardScaler()), ("clf", model)])
        t = time.time()
        model.fit(X[idx_tr], y[idx_tr])
        proba = get_proba(model, X[idx_ev])
        report_eval(run_id=run_id, caminho="A", modelo=name, braco=braco, fold=fold,
                    y_true=y[idx_ev], y_pred=proba.argmax(axis=1), y_proba=proba,
                    sample_ids=list(sample_ids[idx_ev]), key_ids=list(key_ids[idx_ev]),
                    class_names=class_names, labels=[0, 1], out_dir=report_dir,
                    seed=SEED_BOOT, extra={**extra_base, "fit_seconds": round(time.time() - t, 1),
                                           "n_train": int(len(idx_tr))})
        return proba

    idx_trval = np.where(tr)[0]
    idx_test = np.where(te)[0]
    # O IC vem de bootstrap por CLUSTER (chave). Com poucos clusters no teste
    # ele perde o sentido — e, como o p-valor do `report_floor` sai da largura
    # do IC, um teste minúsculo fabrica detecção. Visto na prática: com 2
    # chaves de teste, dado puramente aleatório apareceu como significativo.
    n_clusters = len(np.unique(key_ids[idx_test]))
    if n_clusters < 10:
        _log(f"  AVISO: só {n_clusters} chave(s) no teste. O IC bootstrap por "
             "chave não é confiável abaixo de ~10 clusters; trate como "
             "direcional, não como evidência.")

    def modelos():
        todos = build_models(seed=SEED_MODEL)
        faltantes = [m for m in model_names if m not in todos]
        if faltantes:
            raise ValueError(f"modelos desconhecidos: {faltantes}. Disponíveis: {list(todos)}")
        return {m: todos[m] for m in model_names}

    if mode == "full":
        for fold, (a, b) in enumerate(
                GroupKFold(n_splits=n_cv).split(idx_trval, groups=key_ids[idx_trval])):
            for name, model in modelos().items():
                fit_eval(name, model, idx_trval[a], idx_trval[b], fold)

    for name, model in modelos().items():
        proba = fit_eval(name, model, idx_trval, idx_test, "final")
        # Quantas amostras cada (chave, classe) tem DE FATO no teste. O guard
        # antigo comparava com PAIRS_PER_KEY, que só funciona porque toda chave
        # recebe exatamente esse número — proxy que quebra em silêncio se o
        # conjunto de teste ficar desbalanceado.
        kt, yt = key_ids[idx_test], y[idx_test]
        disponivel = min(int(((kt == k) & (yt == lab)).sum())
                         for k in np.unique(kt) for lab in (0, 1))
        for bag in BAG_SIZES:
            if bag > disponivel:
                _log(f"  bolsa {bag} pulada: só {disponivel} amostra(s) por "
                     f"(chave, classe) no teste")
                continue
            by, bp, bk = _bags(proba, y[idx_test], key_ids[idx_test], bag)
            report_eval(run_id=run_id, caminho="A", modelo=f"{name}_bag{bag}", braco=braco,
                        fold="final", y_true=by, y_pred=bp.argmax(axis=1), y_proba=bp,
                        sample_ids=[f"{k}_{'gift' if lab else 'rand'}_{i}"
                                    for i, (k, lab) in enumerate(zip(bk, by))],
                        key_ids=list(bk), class_names=class_names, labels=[0, 1],
                        out_dir=report_dir, seed=SEED_BOOT,
                        extra={**extra_base, "nivel": "bolsa", "pares_por_decisao": bag})


def _parse_rounds(valores: list[int]) -> list[int]:
    fora = [r for r in valores if not 1 <= r <= MAX_ROUNDS]
    if fora:
        raise ValueError(f"rodadas fora de 1..{MAX_ROUNDS}: {fora}")
    return sorted(set(valores))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--arms", nargs="+", default=["texto"],
                    choices=["texto", "imagem", "aleatorio"])
    ap.add_argument("--rounds", nargs="+", type=int, default=list(range(1, MAX_ROUNDS + 1)))
    ap.add_argument("--mode", choices=["sweep", "full"], default="sweep")
    ap.add_argument("--models", nargs="+", default=list(DEFAULT_MODELS))
    ap.add_argument("--smoke", action="store_true", help="10 chaves, poucas rodadas, saída separada")
    args = ap.parse_args()

    rounds = _parse_rounds(args.rounds)
    n_keys, n_test, n_cv = (10, 2, 3) if args.smoke else (300, 60, 5)
    report_dir = OUT_DIR / ("smoke" if args.smoke else "reports")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    _log(f"braços={args.arms} rodadas={rounds} modo={args.mode} modelos={args.models} "
         f"chaves={n_keys} teste={n_test} -> {report_dir}")

    for arm in args.arms:
        cache = OUT_DIR / f"gift_{arm}_k{n_keys}.npz"
        data = generate(arm, n_keys, rounds, cache)
        for r in rounds:
            run_config(arm, r, data, n_keys, n_test, n_cv, report_dir, args.mode, args.models)
    _log("fila concluída")


if __name__ == "__main__":
    main()
