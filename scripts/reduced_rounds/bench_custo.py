"""
Custo por mensagem curta, em função do número de rodadas.

Sem isto, "mais leve" não tem número. O piso diz quantas rodadas são
insuficientes; este script diz quanto se economiza por rodada cortada, e é a
multiplicação dos dois que responde "quão mais leve o algoritmo pode ficar".

O que é medido: tempo de UMA cifragem completa de mensagem curta (64 bytes),
incluindo o que o modo AEAD cobra em volta (key schedule, absorção do nonce,
finalização, tag). É de propósito o custo de ponta a ponta, e não só o da
permutação: um dispositivo IoT paga o pacote inteiro. Para mensagens curtas o
custo fixo pesa, e é justamente isso que limita o ganho de cortar rodadas — daí
`--msg-bytes` aceitar vários tamanhos: a economia por rodada cortada é uma
função do tamanho do pacote, não uma constante do algoritmo.

Só variantes COMPILADAS entram. O `PureGiftCOFB` em Python puro serve para
medir o piso do GIFT com granularidade de uma rodada, mas o tempo dele não diz
nada sobre custo real, então o GIFT é medido aqui pelas variantes fixsliced
(granularidade de 5) e o resto é interpolado — ver a nota sobre linearidade.

Sobre interpolar: o Grain tem variante compilada para QUALQUER contagem de
clocks, então dá para medir a linearidade em vez de supor. O relatório imprime
o R² do ajuste linear do Grain; se ele for alto, a mesma suposição para os
outros (cujas variantes têm granularidade grossa) está apoiada em medição, e
não em fé. Se for baixo, a interpolação não se sustenta e o relatório avisa.

As variantes precisam estar compiladas antes (o build exige ambiente MSVC):
    build_reduced_variant.bat --algo grain --init-rounds 64

Uso:
    python scripts/reduced_rounds/bench_custo.py --algo grain
    python scripts/reduced_rounds/bench_custo.py --algo grain --rounds 32 64 128 256
    python scripts/reduced_rounds/bench_custo.py --algo grain --msg-bytes 8 64 1024
    python scripts/reduced_rounds/bench_custo.py --todos --json build/custo.json
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.reduced_rounds.floor_algos import ALGOS  # noqa: E402

CASAS = 3               # precisão guardada; o laço imprime o MESMO valor que
                        # vai para o JSON, senão o arredondamento duplo faz o
                        # relatório se contradizer (1,5751 vira 1.58 no laço e
                        # 1.57 na tabela, para a mesma medição)
MSG_BYTES = 64          # mesma mensagem do estudo de piso
REPETICOES = 5          # blocos independentes, para pegar a mediana
N_POR_BLOCO = 2000      # cifragens por bloco
AQUECIMENTO = 200

# Contagens medidas por algoritmo. Onde a variante compilada tem granularidade
# grossa, o ponto medido é o que existe; o resto se interpola.
PADRAO = {
    "grain": [1, 8, 16, 32, 64, 96, 128, 160, 192, 224, 256],
    "ascon": [1, 2, 3, 4, 5, 6, 8, 10, 12],
    "schwaemm": [1, 2, 3, 4, 5, 7, 9, 11],
    "gift": [5, 10, 15, 20, 25, 30, 35, 40],
}


def _medir(cipher, key: bytes, nonce: bytes, pt: bytes) -> float:
    """Mediana de `REPETICOES` blocos, em microssegundos por mensagem.

    Mediana e não média: num desktop qualquer bloco pode ser interrompido pelo
    escalonador, e a média puxa para cima com essas caudas.
    """
    for _ in range(AQUECIMENTO):
        cipher.encrypt(key, nonce, pt)
    tempos = []
    for _ in range(REPETICOES):
        t0 = time.perf_counter()
        for _ in range(N_POR_BLOCO):
            cipher.encrypt(key, nonce, pt)
        tempos.append((time.perf_counter() - t0) / N_POR_BLOCO * 1e6)
    return statistics.median(tempos)


# Abaixo disto o R² não diz nada: com 3 pontos um ajuste de 2 parâmetros quase
# sempre dá R² ~ 1, e o script sairia afirmando linearidade sem evidência.
MIN_PONTOS_LINEARIDADE = 5


def _r2_linear(xs: list[int], ys: list[float]) -> float | None:
    """R² do ajuste `custo = a + b*rodadas`. None se não der para ajustar."""
    n = len(xs)
    if n < MIN_PONTOS_LINEARIDADE:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return None
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    a = my - b * mx
    ss_res = sum((y - (a + b * x)) ** 2 for x, y in zip(xs, ys))
    ss_tot = sum((y - my) ** 2 for y in ys)
    return None if ss_tot == 0 else 1.0 - ss_res / ss_tot


def bench_algo(algo: str, rounds: list[int], msg_bytes: int = MSG_BYTES) -> dict:
    spec = ALGOS[algo]
    key = bytes(range(spec.key_bytes))
    nonce = bytes((i * 7 + 1) & 0xFF for i in range(spec.nonce_bytes))
    pt = bytes((i * 13 + 5) & 0xFF for i in range(msg_bytes))

    # Âncora de deriva: a MESMA configuração é medida no começo e no fim. Se
    # as duas medidas discordarem, a máquina não estava livre durante a
    # varredura e os números não valem. Isso não é hipotético — uma primeira
    # rodada deste script, com uma varredura de ML em segundo plano, produziu
    # um salto de 70% no meio da curva que não existe na cifra.
    def _ancora() -> float | None:
        try:
            return _medir(spec.cipher_para_custo(spec.max_rounds), key, nonce, pt)
        except Exception:  # noqa: BLE001 - variante de spec não compilada
            return None

    ancora_antes = _ancora()

    medidas: dict[int, float] = {}
    for r in rounds:
        try:
            cipher = spec.cipher_para_custo(r)
        except Exception as e:  # noqa: BLE001 - variante não compilada
            print(f"  r={r:4d}  PULADO ({type(e).__name__}: {e})", flush=True)
            continue
        us = round(_medir(cipher, key, nonce, pt), CASAS)
        medidas[r] = us
        print(f"  r={r:4d}  {us:8.2f} us/msg", flush=True)

    if not medidas:
        return dict(algo=algo, erro="nenhuma variante compilada disponível")

    ancora_depois = _ancora()
    deriva = None
    if ancora_antes and ancora_depois:
        deriva = 100.0 * abs(ancora_depois - ancora_antes) / ancora_antes

    xs = sorted(medidas)
    ys = [medidas[x] for x in xs]
    custo_spec = medidas.get(spec.max_rounds)
    r2 = _r2_linear(xs, ys)

    # Chaves em str, iguais às de `us_por_msg`: com int elas viravam str na
    # ida para JSON e o `.get(int)` da impressão devolvia None na volta.
    economia = {}
    if custo_spec:
        for r in xs:
            economia[str(r)] = round(100.0 * (1.0 - medidas[r] / custo_spec), 1)

    return dict(algo=algo, rotulo=spec.rotulo, unidade=spec.unidade,
                rounds_spec=spec.max_rounds, msg_bytes=msg_bytes,
                repeticoes=REPETICOES, n_por_bloco=N_POR_BLOCO,
                us_por_msg={str(k): v for k, v in medidas.items()},
                us_na_spec=custo_spec,
                economia_pct_vs_spec=economia,
                deriva_pct=round(deriva, 2) if deriva is not None else None,
                r2_ajuste_linear=round(r2, 4) if r2 is not None else None)


def imprimir(res: dict) -> None:
    if "erro" in res:
        print(f"\n{res['algo']}: {res['erro']}")
        return
    print(f"\n=== {res['rotulo']} — custo por mensagem de {res['msg_bytes']} bytes ===")
    print(f"{'rodadas':>8} {'us/msg':>10} {'economia vs spec':>18}")
    for r in sorted(map(int, res["us_por_msg"])):
        eco = res["economia_pct_vs_spec"].get(str(r))
        eco_txt = f"{eco:+.1f}%" if eco is not None else "-"
        print(f"{r:>8} {res['us_por_msg'][str(r)]:>10.2f} {eco_txt:>18}")
    deriva = res.get("deriva_pct")
    if deriva is None:
        print("  (sem âncora de deriva: variante de spec não compilada)")
    elif deriva > 5.0:
        print(f"  MEDIÇÃO INVÁLIDA: a configuração de spec mudou {deriva:.1f}% entre o "
              "início e o fim. A máquina não estava livre; repetir sem nada rodando.")
        return
    else:
        print(f"  (deriva da âncora: {deriva:.1f}% — máquina estável durante a medição)")
    r2 = res["r2_ajuste_linear"]
    if r2 is None:
        print(f"  (menos de {MIN_PONTOS_LINEARIDADE} pontos: linearidade não avaliada)")
    elif r2 >= 0.99:
        print(f"  ajuste linear R²={r2:.4f}: o custo é linear nas rodadas, "
              "interpolar entre pontos medidos é defensável")
    else:
        print(f"  ATENÇÃO: ajuste linear R²={r2:.4f}. O custo NÃO é linear nas "
              "rodadas; não interpolar entre pontos medidos.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--algo", choices=sorted(ALGOS))
    ap.add_argument("--todos", action="store_true")
    ap.add_argument("--rounds", nargs="+", type=int, default=None)
    ap.add_argument("--msg-bytes", nargs="+", type=int, default=[MSG_BYTES],
                    help="tamanhos de mensagem; a economia por rodada cortada "
                         "depende muito disto, porque a inicialização é custo fixo")
    ap.add_argument("--json", type=Path, default=None)
    args = ap.parse_args()

    if not args.algo and not args.todos:
        ap.error("informe --algo ou --todos")
    algos = sorted(ALGOS) if args.todos else [args.algo]

    resultados = []
    for algo in algos:
        rounds = args.rounds if args.rounds else PADRAO[algo]
        rounds = [r for r in sorted(set(rounds)) if 1 <= r <= ALGOS[algo].max_rounds]
        for nb in args.msg_bytes:
            print(f"\nmedindo {algo} em {rounds}, mensagem de {nb} bytes", flush=True)
            res = bench_algo(algo, rounds, msg_bytes=nb)
            imprimir(res)
            resultados.append(res)

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(resultados, indent=2, ensure_ascii=False),
                             encoding="utf-8")
        print(f"\njson escrito em {args.json}")


if __name__ == "__main__":
    main()
