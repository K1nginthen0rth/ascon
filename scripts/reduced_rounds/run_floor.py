"""
Piso de rodadas dos finalistas do NIST LWC, em ciphertext-only, contra
aleatório uniforme. Generalização de `run_gift_floor.py` para os quatro.

Pergunta: a partir de quantas rodadas o criptograma deixa de ser separável de
uma sequência uniforme, observando só o que um adversário passivo vê? Abaixo
do piso, a versão reduzida é comprovadamente insegura. Acima dele, este
instrumento não separa — o que NÃO é certificado de segurança, só o limite
deste atacante.

Modelo de acesso (o mesmo do v2, sem relaxamento): mesma chave (mesmo
dispositivo), nonces públicos de contador consecutivos (n, n+1), plaintexts
DIFERENTES e DESCONHECIDOS. O adversário observa o XOR do payload mais o XOR
das tags. Nada de plaintext escolhido, diferença escolhida ou reuso de nonce.

O que muda por algoritmo — tamanho de nonce e tag, o que conta como rodada e
como construir a variante — está em `floor_algos.py`, junto da justificativa
de cada eixo. Os quatro rodam pelo mesmo caminho a partir daqui, que é o ponto:
a literatura não tem um instrumento único aplicado aos quatro (Gerault et al.,
CiC 2025, lista a falta de comparabilidade como problema em aberto).

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

Curva de orçamento: além da decisão por amostra, agrega por dispositivo em
bolsas de 1, 10 e 100 pares (média do log-odds). A agregação é combinação de
escores independentes, e não um modelo multi-par, porque Gohr, Leander e
Neumann (ePrint 2022/1521) mostraram que ganhos alegados de modelos multi-par
costumam sumir quando comparados dessa forma.

Uso:
    python scripts/reduced_rounds/run_floor.py --algo grain --smoke
    python scripts/reduced_rounds/run_floor.py --algo grain --rounds 32 64 96 128 160 192 224 256
    python scripts/reduced_rounds/run_floor.py --algo ascon --rounds 1 2 3 4 5 6 12
    python scripts/reduced_rounds/run_floor.py --algo schwaemm --rounds 1 2 3 4 5 11
    python scripts/reduced_rounds/run_floor.py --algo ascon --politica dados --rounds 1 2 3 4 8
"""
from __future__ import annotations

import argparse
import json
import os
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
    CORPORA_DIR, IMAGES_DIR, IMAGES_MANIFEST,
    _ImagePlaintextSampler, _TextPlaintextSampler,
)
from scripts.reduced_rounds.floor_algos import ALGOS, fracao_da_spec  # noqa: E402
# Reaproveitados de `run_gift_floor.py` de propósito: a agregação por bolsa é a
# parte estatisticamente delicada, e duplicá-la criaria duas versões para
# divergirem. Aquele script continua sendo o caminho do GIFT com granularidade
# de uma rodada (via Python puro); este cobre os quatro via variantes compiladas.
from scripts.reduced_rounds.run_gift_floor import (  # noqa: E402
    BAG_SIZES, DEFAULT_MODELS, MSG_BYTES, NEEDS_SCALING, PAIRS_PER_KEY,
    SEED_BOOT, SEED_MODEL, SEED_SPLIT, _FP, _bags, _e_chave_de_rodada, _git_commit,
    _log, conferir_cache, impressao_digital,
)
from scripts.run_v2_caminho_a import build_models, get_proba  # noqa: E402
from scripts.reduced_rounds.neural_floor import build_neural_models  # noqa: E402
from src.crypto.ctr_drbg import CTRDRBG  # noqa: E402
from src.eval.reporting import report_eval  # noqa: E402

SEED_GEN = 999004
# Esquema da amostra. Na v1 (até 2026-09-29) os rótulos do DRBG levavam o nome
# do algoritmo, então cada algoritmo era medido com chaves e textos próprios, e
# o nonce era um contador GLOBAL, 2*(k*100+j): a faixa de nonce ficava amarrada
# à chave, e o split por chave virava mudança de distribuição de nonce. Com
# poucas rodadas, bits do criptograma se correlacionam com bits do nonce, e as
# chaves de teste traziam faixas que o treino nunca viu. Na v2 os quatro
# algoritmos compartilham chaves, textos e offsets de nonce (Regra de Ouro 6),
# e cada dispositivo tem o próprio contador, a partir de um offset sorteado.
ESQUEMA_AMOSTRA = "v2-compartilhada-offset-por-chave"
# PISO_OUT_ROOT: no Kaggle o repositório fica numa entrada só de leitura.
OUT_ROOT = Path(os.environ.get("PISO_OUT_ROOT",
                               REPO_ROOT / "build" / "reduced_rounds" / "floor_v2"))


def _sampler(arm: str, pt_drbg: CTRDRBG):
    """Fonte de plaintext do braço. Devolve (função, amostrador de imagem)."""
    if arm == "texto":
        return _TextPlaintextSampler(CORPORA_DIR, pt_drbg).sample, None
    if arm == "imagem":
        s = _ImagePlaintextSampler(IMAGES_DIR, IMAGES_MANIFEST, pt_drbg)
        return (lambda: s.sample()[0]), s
    if arm == "aleatorio":
        return (lambda: pt_drbg.generate(MSG_BYTES)), None
    raise ValueError(f"braço desconhecido: {arm}")


def _montar(ca: np.ndarray, cb: np.ndarray, representacao: str) -> np.ndarray:
    """Amostra a partir dos dois lados do par, na representação pedida."""
    if representacao == "xor":
        return ca ^ cb
    if representacao == "par":
        return np.concatenate([ca, cb])
    return np.concatenate([ca, cb, ca ^ cb])


def generate(algo: str, arm: str, n_keys: int, rounds: list[int], cache: Path,
             politica: str, contador: str = "sorteado",
             representacao: str = "xor") -> dict:
    """XOR (payload + tag) de pares consecutivos, por contagem de rodadas.

    Incremental: só gera as contagens que faltam no cache. Chaves, nonces e
    plaintexts vêm do mesmo DRBG com a mesma seed, então contagens geradas em
    passadas diferentes continuam comparáveis (Regra de Ouro 6).
    """
    spec = ALGOS[algo]
    largura = MSG_BYTES + spec.tag_bytes
    # `xor`: o XOR dos dois criptogramas do par (Baksi; Shen). `par`: os dois
    # criptogramas inteiros lado a lado, como a entrada do Gohr. O Shen mostra
    # que, com um par só, a entrada completa acerta mais que a diferença.
    # `par+xor`: os dois criptogramas e o XOR deles. Testa se o XOR descarta
    # informação útil: se esta forma subir o piso, descartava.
    if representacao not in ("xor", "par", "par+xor"):
        raise ValueError(f"representação desconhecida: {representacao!r}")
    largura_amostra = {"xor": 1, "par": 2, "par+xor": 3}[representacao] * largura

    fp = impressao_digital(algo=algo, arm=arm, politica=politica, n_keys=n_keys,
                           pairs_per_key=PAIRS_PER_KEY, msg_bytes=MSG_BYTES,
                           tag_bytes=spec.tag_bytes, nonce_bytes=spec.nonce_bytes,
                           seed_gen=SEED_GEN, esquema=ESQUEMA_AMOSTRA,
                           # só entra quando difere do padrão, para não invalidar
                           # os caches já gerados com contador sorteado
                           **({} if contador == "sorteado" else {"contador": contador}),
                           **({} if representacao == "xor" else {"representacao": representacao}))

    store: dict[str, np.ndarray] = {}
    if cache.exists():
        z = np.load(cache, allow_pickle=False)
        store = {k: z[k] for k in z.files}
        conferir_cache(store, fp, cache)

    faltando = [r for r in rounds if f"r{r}" not in store]
    if not faltando:
        _log(f"[{algo}/{arm}] cache completo em {cache.name} ({rounds})")
        return store

    _log(f"[{algo}/{arm}] construindo variantes {faltando} (política={politica})")
    ciphers = {r: spec.cipher(r, politica) for r in faltando}
    _log(f"[{algo}/{arm}] gerando {faltando} ({n_keys} chaves x {PAIRS_PER_KEY} pares)")

    # Rótulos SEM o nome do algoritmo: a mesma chave, o mesmo texto e o mesmo
    # offset de nonce para os quatro, na mesma posição da amostra.
    key_drbg = CTRDRBG(seed=SEED_GEN, label="floor-keys")
    pt_drbg = CTRDRBG(seed=SEED_GEN, label=f"floor-pt-{arm}")
    rnd_drbg = CTRDRBG(seed=SEED_GEN, label=f"floor-random-{arm}")
    nonce_drbg = CTRDRBG(seed=SEED_GEN, label="floor-nonceoffset")
    mod_nonce = 1 << (8 * spec.nonce_bytes)
    sample, image_sampler = _sampler(arm, pt_drbg)

    n = n_keys * PAIRS_PER_KEY
    novo = {f"r{r}": np.zeros((n, largura_amostra), np.uint8) for r in faltando}
    precisa_random = "random" not in store
    if precisa_random:
        novo["random"] = np.zeros((n, largura_amostra), np.uint8)
    key_idx = np.repeat(np.arange(n_keys), PAIRS_PER_KEY).astype(np.int32)

    n_resampled = 0
    t0 = time.time()
    for k in range(n_keys):
        key = key_drbg.random_key(spec.key_bytes)
        # 32 bytes cobrem o maior nonce (Schwaemm); os de nonce menor usam os
        # bytes baixos do MESMO sorteio, então a amostra segue compartilhada.
        # LSB zerado: o par (n, n+1) difere em exatamente 1 bit, como na v1,
        # para os pisos continuarem comparáveis.
        off = (int.from_bytes(nonce_drbg.generate(32), "big") % mod_nonce) & ~1
        if contador == "zero":
            # Dispositivo recém-ligado: todo contador começa do zero, então os
            # nonces são quase todos bytes nulos e só os bits de baixo variam.
            # É o pior caso realista para o atacante passivo (a diferença de 1
            # bit atravessa as rodadas sempre com os mesmos vizinhos). Todos
            # os dispositivos usam os MESMOS nonces, então a faixa de nonce não
            # fica amarrada à chave, ao contrário do contador global da v1.
            off = 0
        for j in range(PAIRS_PER_KEY):
            p1, p2 = sample()[:MSG_BYTES], sample()[:MSG_BYTES]
            while p2 == p1:  # par com plaintext igual sairia do modelo de acesso
                p2 = sample()[:MSG_BYTES]
                n_resampled += 1
            # Um amostrador que devolva menos que MSG_BYTES quebraria a
            # largura das linhas de forma silenciosa em algumas combinações.
            assert len(p1) == len(p2) == MSG_BYTES, "amostrador devolveu tamanho errado"
            c = (off + 2 * j) % mod_nonce
            n1 = c.to_bytes(spec.nonce_bytes, "big")
            n2 = (c + 1).to_bytes(spec.nonce_bytes, "big")
            i = k * PAIRS_PER_KEY + j
            for r, cipher in ciphers.items():
                a = cipher.encrypt(key, n1, p1)
                b = cipher.encrypt(key, n2, p2)
                ca = np.frombuffer(a[:MSG_BYTES] + a[-spec.tag_bytes:], np.uint8)
                cb = np.frombuffer(b[:MSG_BYTES] + b[-spec.tag_bytes:], np.uint8)
                novo[f"r{r}"][i] = _montar(ca, cb, representacao)
            if precisa_random:
                # A classe aleatória é montada do MESMO jeito que a da cifra:
                # dois blocos uniformes e independentes, combinados pela mesma
                # regra. Em `par+xor`, 240 bytes uniformes puros vazariam o
                # rótulo (bastaria checar se o 3º bloco é o XOR dos dois).
                ra = np.frombuffer(rnd_drbg.generate(largura), np.uint8)
                if representacao == "xor":
                    novo["random"][i] = ra
                else:
                    rb = np.frombuffer(rnd_drbg.generate(largura), np.uint8)
                    novo["random"][i] = _montar(ra, rb, representacao)
        if (k + 1) % 25 == 0 or k + 1 == n_keys:
            _log(f"[{algo}/{arm}] chaves {k + 1}/{n_keys} ({time.time() - t0:.0f}s)")

    if "key_idx" in store:
        assert np.array_equal(store["key_idx"], key_idx), "cache com nº de chaves diferente"
    store.update(novo)
    store["key_idx"] = key_idx
    store[_FP] = fp
    np.savez(cache, **store)

    meta = dict(algo=algo, rotulo=spec.rotulo, unidade=spec.unidade, politica=politica,
                arm=arm, n_keys=n_keys, pairs_per_key=PAIRS_PER_KEY, seed_gen=SEED_GEN,
                rounds_presentes=sorted(int(k[1:]) for k in store if _e_chave_de_rodada(k)),
                rounds_spec=spec.max_rounds, msg_bytes=MSG_BYTES, tag_bytes=spec.tag_bytes,
                classe_negativa="aleatório uniforme (CTR_DRBG)",
                nonce=(("contador por dispositivo começando do zero" if contador == "zero"
                        else "contador por dispositivo a partir de offset sorteado (LSB 0)")
                       + f", big-endian {spec.nonce_bytes} bytes, par (n, n+1)"),
                contador=contador, representacao=representacao,
                esquema=ESQUEMA_AMOSTRA,
                plaintexts="P1 != P2, desconhecidos, mesmos para todas as contagens",
                n_resampled_equal_plaintext=n_resampled,
                n_reused_images=(image_sampler.n_reused if image_sampler else None),
                git_commit=_git_commit(), generated_at=datetime.now(timezone.utc).isoformat())
    cache.with_suffix(".json").write_text(json.dumps(meta, indent=2, ensure_ascii=False),
                                          encoding="utf-8")
    _log(f"[{algo}/{arm}] geração de {faltando} em {time.time() - t0:.0f}s -> {cache.name}")
    return store


def run_config(algo: str, arm: str, rounds: int, data: dict, n_keys: int, n_test: int,
               n_cv: int, report_dir: Path, mode: str, model_names: list[str],
               politica: str, contador: str = "sorteado",
               representacao: str = "xor") -> None:
    spec = ALGOS[algo]
    run_id = f"floor_{algo}_{arm}_r{rounds}"
    braco = f"floor_{algo}_{arm}"
    class_names = ["aleatório uniforme", f"{spec.rotulo} {rounds}"]
    _log(f"===== {run_id}: {spec.rotulo} {rounds} {spec.unidade} vs aleatório, "
         f"plaintext={arm} =====")

    n = n_keys * PAIRS_PER_KEY
    X = np.vstack([np.unpackbits(data["random"], axis=1),
                   np.unpackbits(data[f"r{rounds}"], axis=1)]).astype(np.float32)
    y = np.concatenate([np.zeros(n, int), np.ones(n, int)])
    kidx = np.concatenate([data["key_idx"], data["key_idx"]])
    key_ids = np.array([f"k{k:04d}" for k in kidx])
    sample_ids = np.array([f"{algo}_{arm}_r{rounds}_k{k:04d}_p{i % PAIRS_PER_KEY:03d}"
                           f"_{'cif' if lab else 'rand'}"
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

    extra_base = dict(
        algo=algo, rounds=rounds, rounds_spec=spec.max_rounds,
        runner="run_floor", seed_gen_runner=SEED_GEN,
        fracao_da_spec=round(fracao_da_spec(algo, rounds), 4),
        unidade=spec.unidade, politica=politica, arm=arm,
        n_features=X.shape[1], seed_gen=SEED_GEN, classe_negativa="aleatório uniforme",
        access_model="mesma chave, nonces consecutivos (n,n+1) por dispositivo, P1!=P2 desconhecidos",
        esquema=ESQUEMA_AMOSTRA, contador=contador, representacao=representacao,
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
        # Clássicos do Caminho A e as redes de `neural_floor.py`. As redes
        # precisam saber quantos blocos de criptograma a amostra carrega, para
        # alinhar os bits por posição de byte.
        blocos = {"xor": 1, "par": 2, "par+xor": 3}[representacao]
        todos = {**build_models(seed=SEED_MODEL),
                 **build_neural_models(seed=SEED_MODEL, blocos=blocos)}
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
                        sample_ids=[f"{k}_{'cif' if lab else 'rand'}_{i}"
                                    for i, (k, lab) in enumerate(zip(bk, by))],
                        key_ids=list(bk), class_names=class_names, labels=[0, 1],
                        out_dir=report_dir, seed=SEED_BOOT,
                        extra={**extra_base, "nivel": "bolsa", "pares_por_decisao": bag})


def main() -> None:
    global PAIRS_PER_KEY
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--algo", required=True, choices=sorted(ALGOS))
    ap.add_argument("--arms", nargs="+", default=["texto"],
                    choices=["texto", "imagem", "aleatorio"])
    ap.add_argument("--rounds", nargs="+", type=int, default=None,
                    help="contagens a varrer; padrão = a varredura do catálogo "
                         "(região do piso + faixa de controle)")
    ap.add_argument("--politica", choices=["ambos", "dados"], default="ambos",
                    help="só para Ascon e Schwaemm; ver floor_algos.py")
    ap.add_argument("--mode", choices=["sweep", "full"], default="sweep")
    ap.add_argument("--models", nargs="+", default=list(DEFAULT_MODELS))
    ap.add_argument("--n-keys", type=int, default=300)
    ap.add_argument("--n-test", type=int, default=60)
    ap.add_argument("--n-cv", type=int, default=5)
    ap.add_argument("--contador", choices=["sorteado", "zero"], default="sorteado",
                    help="estado do contador de nonce de cada dispositivo: 'sorteado' "
                         "(ponto qualquer, caso geral) ou 'zero' (recém-ligado, pior caso)")
    ap.add_argument("--representacao", choices=["xor", "par", "par+xor"], default="xor",
                    help="o que o classificador recebe: o XOR dos dois criptogramas "
                         "do par, os dois inteiros lado a lado, ou os dois mais o XOR")
    ap.add_argument("--tag", default=None,
                    help="sufixo do diretório de saída, para separar uma família de "
                         "modelos (ex.: 'neural') dos relatórios dos clássicos; os "
                         "dados são regerados idênticos pelo mesmo DRBG")
    ap.add_argument("--pares-por-chave", type=int, default=PAIRS_PER_KEY,
                    help="pares por dispositivo. Com --contador zero e 1 par, cada "
                         "dispositivo contribui só os nonces 0 e 1 (o 'primeiro par')")
    ap.add_argument("--smoke", action="store_true",
                    help="10 chaves, poucas contagens, saída separada")
    args = ap.parse_args()
    # Sobrescreve o padrão do módulo: generate() e run_config() leem o global.
    PAIRS_PER_KEY = args.pares_por_chave

    spec = ALGOS[args.algo]
    if args.politica == "dados" and not spec.dois_parametros:
        raise SystemExit(f"{args.algo} tem um parâmetro de rodadas só; a política "
                         "'dados' existe para Ascon e Schwaemm, que têm dois.")
    # Sem --rounds, usa a varredura do catálogo. NÃO usar 1..spec: no Grain
    # isso mandaria compilar 256 variantes.
    rounds = list(args.rounds) if args.rounds else list(spec.rounds_padrao)
    if not rounds:
        rounds = list(range(1, spec.max_rounds + 1))
    # Sob `dados` o eixo é o parâmetro de dados, que satura antes da spec.
    teto = spec.max_rounds_dados if args.politica == "dados" else spec.max_rounds
    fora = [r for r in rounds if not 1 <= r <= teto]
    if fora and args.rounds:
        # Pedido explícito fora do intervalo é erro, não filtro silencioso.
        raise SystemExit(f"{args.algo} (política {args.politica}): rodadas fora "
                         f"de 1..{teto}: {fora}")
    rounds = sorted({r for r in rounds if 1 <= r <= teto})
    if not rounds:
        raise SystemExit(f"{args.algo} com política '{args.politica}' não tem "
                         f"contagens válidas (teto = {teto})")

    n_keys, n_test = args.n_keys, args.n_test
    base = (OUT_ROOT if args.contador == "sorteado"
            else OUT_ROOT / f"contador_{args.contador}")
    if PAIRS_PER_KEY != 100:
        # outro desenho de amostra: diretório próprio, para não misturar relatórios
        base = base.parent / f"{base.name}_ppk{PAIRS_PER_KEY}"
    if args.representacao != "xor":
        base = base.parent / f"{base.name}_{args.representacao.replace('+', '_')}"
    if args.tag:
        base = base.parent / f"{base.name}_{args.tag}"
    base = base / f"{args.algo}_floor"
    if args.smoke:
        n_keys, n_test = 10, 3
        # O ponto de controle do smoke é o TETO do eixo em uso, não a spec:
        # sob `dados` a spec está fora do intervalo e voltaria pela janela.
        rounds = sorted(set(rounds[:3] + [teto]))
        base = base / "smoke"
    report_dir = base / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)

    _log(f"algo={args.algo} ({spec.rotulo}) braços={args.arms} rodadas={rounds} "
         f"política={args.politica} modo={args.mode} modelos={args.models} "
         f"chaves={n_keys} teste={n_test} -> {report_dir}")

    for arm in args.arms:
        sufixo = "" if args.politica == "ambos" else f"_{args.politica}"
        cache = base / f"{args.algo}_{arm}{sufixo}_k{n_keys}.npz"
        data = generate(args.algo, arm, n_keys, rounds, cache, args.politica, args.contador,
                        args.representacao)
        for r in rounds:
            run_config(args.algo, arm, r, data, n_keys, n_test, args.n_cv,
                       report_dir, args.mode, args.models, args.politica, args.contador,
                       args.representacao)

    _log("fim")


if __name__ == "__main__":
    main()
