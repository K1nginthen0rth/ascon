"""
Lê as métricas do estudo de piso e determina a fronteira de rodadas.

O critério precisa ser explícito, porque é dele que sai a afirmação da tese.
A primeira versão deste script usava só "limite inferior do IC acima de 0,50",
e o próprio smoke mostrou o problema: com 40 rodadas (cifra completa) o
RandomForest apareceu como detectado. Numa varredura de 40 rodadas x 3 modelos
x 3 tamanhos de bolsa são 360 testes, e a 95% de confiança cerca de 18 passam
por acaso. Critério atual, com duas barreiras:

 1. **BH-FDR (q=0,05)** sobre TODAS as configurações da varredura, usando o
    mesmo cálculo de p-valor do `consolidate_v2.py` (meia-largura do IC
    bootstrap por chave dividida por 1,96 vira erro padrão, daí o z contra o
    acaso de 0,50). A função de correção é importada de lá, não reimplementada.

 2. **Faixa de controle empírica:** as rodadas altas são, por construção, a
    cifra essencialmente completa. A detecção só vale se o F1 também superar
    o MÁXIMO observado nessa faixa, para o mesmo modelo e tamanho de bolsa.
    Isso calibra contra o ruído real do pipeline em vez de contra o 0,50
    teórico. Onde a faixa começa é POR ALGORITMO, metade da spec por padrão:
    um limiar fixo de 20 rodadas é controle para o GIFT (spec 40) e é região
    de sinal para o Grain (spec 256), e chegou a fazer o Grain reportar
    "nenhum piso" tendo piso 28.

 3. **Monotonicidade:** só entra na manchete a célula (modelo x bolsa) que
    detecta em R e também em tudo abaixo de R. Detecção que pula as rodadas
    mais fracas é ruído de múltiplas comparações, não fronteira.

O piso de um par (modelo, bolsa) é o MAIOR R detectado. Rodadas não detectadas
abaixo do piso são reportadas como não monotonicidade, não escondidas.

A leitura honesta é "abaixo de X, até este atacante genérico quebra", nunca
"acima de X é seguro".

Uso:
    python scripts/reduced_rounds/report_floor.py
    python scripts/reduced_rounds/report_floor.py --dir build/reduced_rounds/gift_floor/smoke
    python scripts/reduced_rounds/report_floor.py --dir build/reduced_rounds/grain_floor/reports
    python scripts/reduced_rounds/report_floor.py --null-min 30 --csv piso.csv
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from scripts.consolidate_v2 import apply_bh_fdr  # noqa: E402
from scripts.reduced_rounds.floor_algos import ALGOS  # noqa: E402

DEFAULT_DIR = REPO_ROOT / "build" / "reduced_rounds" / "gift_floor" / "reports"
CHANCE = 0.50
Q_PADRAO = 0.05


def carregar(report_dir: Path) -> pd.DataFrame:
    linhas = []
    for p in sorted(report_dir.glob("*_metrics.jsonl")):
        for linha in p.read_text(encoding="utf-8").splitlines():
            if not linha.strip():
                continue
            r = json.loads(linha)
            if str(r.get("fold")) != "final":
                continue
            extra = r.get("extra") or {}
            if "rounds" not in extra:
                continue
            auc = r.get("auc_roc")
            auc = auc.get("auc") if isinstance(auc, dict) else auc
            linhas.append(dict(
                arm=extra.get("arm"), rounds=int(extra["rounds"]),
                politica=extra.get("politica", "ambos"),
                algo=extra.get("algo", "gift"), rounds_spec=extra.get("rounds_spec"),
                unidade=extra.get("unidade", "rodadas"),
                runner=extra.get("runner", "desconhecido"),
                seed_gen=extra.get("seed_gen_runner", extra.get("seed_gen")),
                modelo=r["modelo"].split("_bag")[0],
                bolsa=int(extra.get("pares_por_decisao", 1)),
                f1_macro=r["f1_macro"], f1_ci_lo=r.get("f1_macro_ci_lower"),
                f1_ci_hi=r.get("f1_macro_ci_upper"), auc=auc, n_samples=r.get("n_samples"),
                timestamp=r.get("timestamp", ""),
            ))
    if not linhas:
        return pd.DataFrame()
    df = pd.DataFrame(linhas).sort_values("timestamp")
    # `run_gift_floor.py` (anterior ao catálogo) não grava rounds_spec/unidade;
    # completar do catálogo mantém o relatório uniforme entre os dois runners.
    falta = df["rounds_spec"].isna()
    if falta.any():
        df["rounds_spec"] = df["rounds_spec"].astype("object")
        df.loc[falta, "rounds_spec"] = df.loc[falta, "algo"].map(
            lambda a: ALGOS[a].max_rounds if a in ALGOS else None)
    # Sob `politica="dados"` o eixo de rodadas E o parametro de dados (pb do
    # Ascon, slim do Schwaemm), que satura antes da spec: pedir 12 ali devolve
    # o mesmo cifrador de 8. O runner grava `rounds_spec` como a spec da
    # permutacao nos dois casos, o que faria a faixa de controle comecar no
    # lugar errado e a fracao da spec sair menor que 1,0 no ponto que E a spec.
    sob_dados = df["politica"] == "dados"
    if sob_dados.any():
        df["rounds_spec"] = df["rounds_spec"].astype("object")
        df.loc[sob_dados, "rounds_spec"] = df.loc[sob_dados, "algo"].map(
            lambda a: ALGOS[a].max_rounds_dados if a in ALGOS else None)
    sem_unidade = df["unidade"].isna()
    if sem_unidade.any():
        df.loc[sem_unidade, "unidade"] = df.loc[sem_unidade, "algo"].map(
            lambda a: ALGOS[a].unidade if a in ALGOS else "rodadas")
    # `run_gift_floor.py` e `run_floor.py` escrevem no MESMO diretório para o
    # GIFT e usam seeds de geração diferentes (999003 e 999004). Sem este
    # aviso, linhas das duas execuções cairiam na mesma chave e o
    # drop_duplicates escolheria uma delas em silêncio — o relatório sairia
    # com metade dos dados de cada, sem nada indicando isso.
    for (algo, arm, pol), g in df.groupby(["algo", "arm", "politica"]):
        proc = sorted(set(g["runner"].dropna()) | {str(s) for s in g["seed_gen"].dropna()})
        if len(set(g["runner"].dropna())) > 1 or len(set(g["seed_gen"].dropna())) > 1:
            print(f"AVISO: {algo}/{arm}/{pol} mistura execuções distintas ({proc}). "
                  "São dados de geração diferente na mesma pasta; separe antes de "
                  "acreditar no piso.")
    # Arquivos são append-only: fica a execução mais recente de cada configuração.
    # `politica` entra na chave porque Ascon e Schwaemm tem DOIS parametros de
    # rodada, e os dois eixos usam a mesma numeracao: r=4 sob `ambos` e r=4 sob
    # `dados` sao cifradores diferentes. Sem isto, o dedup guardava so o que
    # rodou por ultimo e o relatorio saia com metade das linhas de cada eixo,
    # numerado como se fosse um sweep so.
    return df.drop_duplicates(
        subset=["algo", "arm", "politica", "rounds", "modelo", "bolsa"], keep="last")


def _com_politica(df: pd.DataFrame) -> pd.DataFrame:
    """Garante a coluna `politica`, defaultando para "ambos".

    `carregar()` sempre preenche, mas `marcar()`/`null_min_por_algo()` tambem
    sao chamadas direto pelos testes e por quem inspeciona um quadro a mao, e
    `run_gift_floor.py` (anterior as duas politicas) nao grava o campo. Sem
    este default, um quadro legitimo sem a coluna morria em KeyError em vez de
    ser lido como o unico eixo que aqueles dados tem.
    """
    if "politica" not in df.columns:
        df = df.copy()
        df["politica"] = "ambos"
    return df


def null_min_por_algo(df: pd.DataFrame, null_min: int | None) -> dict[tuple[str, str], int]:
    """Onde começa a faixa de controle, por algoritmo.

    Um valor único para todos não serve: 20 rodadas é "cifra praticamente
    completa" para o GIFT (spec 40) e é plena região de sinal para o Grain
    (spec 256). Com o padrão antigo, fixo em 20, o Grain reportava NENHUM piso
    quando o piso real é 28 — a faixa de controle engolia justamente as
    contagens com sinal. O padrão agora é METADE da spec de cada algoritmo, e
    `--null-min` só sobrepõe quando dado explicitamente.
    """
    df = _com_politica(df)
    chaves = df[["algo", "politica"]].dropna(subset=["algo"]).drop_duplicates()
    if null_min is not None:
        return {(a, pol): null_min for a, pol in chaves.itertuples(index=False)}
    fora = {}
    for (a, pol), g in df.groupby(["algo", "politica"]):
        spec = g["rounds_spec"].dropna()
        base = int(spec.iloc[0]) if not spec.empty else int(g["rounds"].max())
        fora[(a, pol)] = max(1, math.ceil(base / 2))
    return fora


def marcar(df: pd.DataFrame, null_min: int | None, q: float) -> pd.DataFrame:
    """p-valor a partir do IC (igual ao consolidate_v2), BH-FDR e faixa de controle."""
    df = _com_politica(df).copy()
    if df.empty:
        # `main()` já barra antes de chegar aqui, mas a função é reusada por
        # testes e por quem inspeciona à mão; sem isto, quadro vazio saía como
        # KeyError: 'algo'.
        return df
    nm = null_min_por_algo(df, null_min)
    df["null_min"] = [nm.get((a, pol)) for a, pol in zip(df["algo"], df["politica"])]

    half = (df["f1_ci_hi"] - df["f1_ci_lo"]) / 2.0
    # IC AUSENTE e IC de largura ZERO são coisas diferentes, e confundi-las
    # fabrica detecção: sem esta separação, uma linha sem IC no jsonl virava
    # `se = NaN`, caía no ramo "separação perfeita" e recebia p=0.
    sem_ic = df["f1_ci_lo"].isna() | df["f1_ci_hi"].isna() | df["f1_macro"].isna()
    degenerado = (~sem_ic) & (half == 0)

    se = (half / 1.96).replace(0, np.nan)
    z = (df["f1_macro"] - CHANCE) / se
    from scipy.stats import norm
    df["p_value"] = 2.0 * (1.0 - norm.cdf(z.abs()))
    # IC de largura zero (separação perfeita, F1=1,000) zera o erro padrão e
    # deixaria o p-valor indefinido. Tratar como "sem evidência" faria o piso
    # ser subestimado justamente nas rodadas mais fracas, que são as que mais
    # separam. Separação perfeita acima do acaso é a evidência máxima, então
    # recebe p=0; abaixo do acaso, p=1.
    df.loc[degenerado & (df["f1_macro"] > CHANCE), "p_value"] = 0.0
    df.loc[degenerado & (df["f1_macro"] <= CHANCE), "p_value"] = 1.0
    # unilateral: só interessa desempenho ACIMA do acaso
    df.loc[(~sem_ic) & (df["f1_macro"] <= CHANCE), "p_value"] = 1.0
    # sem IC não é evidência de nada: p=NaN sai do BH-FDR e nunca é detectado
    df.loc[sem_ic, "p_value"] = np.nan
    if sem_ic.any():
        print(f"AVISO: {int(sem_ic.sum())} linha(s) sem IC bootstrap; "
              "excluídas do teste (não contam como detecção nem como controle).")
    df = apply_bh_fdr(df, q=q)

    df["teto_controle"] = np.nan
    for _chave, g in df.groupby(["algo", "arm", "politica", "modelo", "bolsa"]):
        faixa = g[g["rounds"] >= g["null_min"]]
        if not faixa.empty:
            df.loc[g.index, "teto_controle"] = faixa["f1_macro"].max()
    acima_do_controle = (df["teto_controle"].isna()
                         | (df["f1_macro"] > df["teto_controle"]))
    df["detectado"] = df["significativo_fdr"] & acima_do_controle
    return df


def tabela(df: pd.DataFrame) -> None:
    for algo in sorted(df["algo"].dropna().unique()):
      for arm in sorted(df["arm"].dropna().unique()):
        for bolsa in sorted(df["bolsa"].unique()):
            sel = df[(df["algo"] == algo) & (df["arm"] == arm) & (df["bolsa"] == bolsa)]
            if sel.empty:
                continue
            modelos = sorted(sel["modelo"].unique())
            print(f"\n=== {algo} | braço={arm} | bolsa={bolsa} par(es) por decisão ===")
            print("rod | " + " | ".join(f"{m[:20]:^22}" for m in modelos))
            for r in sorted(sel["rounds"].unique()):
                celulas = []
                for m in modelos:
                    linha = sel[(sel["rounds"] == r) & (sel["modelo"] == m)]
                    if linha.empty:
                        celulas.append(f"{'-':^22}")
                        continue
                    x = linha.iloc[0]
                    marca = "*" if x["detectado"] else " "
                    celulas.append(f"{x['f1_macro']:.3f} [{x['f1_ci_lo']:.3f}] {marca}".center(22))
                print(f"{r:3d} | " + " | ".join(celulas))
            print("  (* = significativo sob BH-FDR E acima do teto da faixa de controle)")


def pisos(df: pd.DataFrame) -> None:
    print("\n=== PISO (maior nº de rodadas ainda detectado) ===")
    print(f"{'algo/braço':<16} {'modelo':<20} {'bolsa':>6} {'piso':>5}  observação")
    global_piso: dict[tuple[str, str, str], int] = {}
    n_celulas: dict[tuple[str, str, str], int] = {}
    descartadas: dict[tuple[str, str, str], int] = {}
    # Total real de células (modelo x bolsa) por braço. Estava fixo em 9, o que
    # mentiria em qualquer varredura com outro número de modelos ou bolsas.
    total_celulas = (df.groupby(["algo", "arm", "politica"])[["modelo", "bolsa"]]
                     .apply(lambda g: len(g.drop_duplicates())).to_dict())
    for (algo, arm, pol, modelo, bolsa), g in df.groupby(
            ["algo", "arm", "politica", "modelo", "bolsa"]):
        g = g.sort_values("rounds")
        det = g[g["detectado"]]["rounds"].tolist()
        rotulo = f"{algo}/{arm}/{pol}"
        if not det:
            print(f"{rotulo:<16} {modelo:<20} {bolsa:>6} {'-':>5}  nenhuma rodada detectada")
            continue
        piso = max(det)
        buracos = g[(g["rounds"] < piso) & (~g["detectado"])]["rounds"].tolist()
        obs = f"NÃO MONOTÔNICO: falhou em {buracos}" if buracos else ""
        print(f"{rotulo:<16} {modelo:<20} {bolsa:>6} {piso:>5}  {obs}")
        # Só célula monotônica entra na manchete. Um piso real não pode pular as
        # rodadas MAIS fracas: se a detecção aparece em R mas some em R-1, é
        # ruído de múltiplas comparações, não fronteira. Sem esta regra, uma
        # única célula espúria definia o número da tese — foi o que aconteceu
        # no braço de plaintext uniforme, onde 3 de 9 células "detectaram" algo
        # e as 3 tinham buraco embaixo.
        if buracos:
            descartadas[(algo, arm, pol)] = descartadas.get((algo, arm, pol), 0) + 1
            continue
        global_piso[(algo, arm, pol)] = max(global_piso.get((algo, arm, pol), 0), piso)
        n_celulas[(algo, arm, pol)] = n_celulas.get((algo, arm, pol), 0) + 1

    # Diagnóstico da faixa de controle POR ALGORITMO: o limiar é por algoritmo,
    # então somar os quatro numa estatística só esconde qual deles está sujo.
    for (algo, pol), g in df.groupby(["algo", "politica"]):
        nm = int(g["null_min"].iloc[0])
        controle = g[g["rounds"] >= nm]
        if controle.empty:
            print(f"\nAVISO [{algo}/{pol}]: nenhuma rodada >= {nm} nos dados. Sem faixa de "
                  "controle, a detecção depende só do BH-FDR contra o acaso teórico.")
            continue
        fp = int(controle["significativo_fdr"].sum())
        frac = fp / len(controle)
        print(f"\nfaixa de controle [{algo}/{pol}] (rodadas >= {nm}): {len(controle)} "
              f"configurações, {fp} significativa(s) antes do teto de controle "
              f"({frac:.0%})")
        # Acima de 2x o q do BH a faixa não é mais nula: ela contém sinal, e um
        # teto calculado ali mascara o piso de verdade em vez de calibrar ruído.
        if frac > 2 * Q_PADRAO:
            print(f"  ATENÇÃO: {frac:.0%} é alto demais para uma faixa nula "
                  f"(esperado <= {Q_PADRAO:.0%}). A faixa provavelmente contém "
                  "sinal real — subir --null-min antes de acreditar no piso.")

    for (algo, arm, pol) in sorted(set(df.groupby(["algo", "arm", "politica"]).groups)):
        chave = (algo, arm, pol)
        fora = descartadas.get(chave, 0)
        if chave not in global_piso:
            extra = (f" ({fora} célula(s) marcaram algo, todas com buraco abaixo "
                     "— ruído, não fronteira)") if fora else ""
            print(f"\n>> {algo} / braço {arm} / politica {pol}: NENHUM piso monotônico{extra}. "
                  "Nenhuma redução testada foi separável do aleatório.")
            continue
        piso = global_piso[chave]
        meta = df[(df["algo"] == algo) & (df["arm"] == arm)
                  & (df["politica"] == pol)].iloc[0]
        spec, unidade = meta["rounds_spec"], meta["unidade"]
        frac = f" = {piso / spec:.1%} da spec" if spec else ""
        print(f"\n>> {algo} / braço {arm} / politica {pol}: com até {piso} {unidade}"
              f" ({piso}/{int(spec) if spec else '?'}{frac}) o algoritmo é separável do "
              f"aleatório por pelo menos um detector genérico em ciphertext-only.")
        print(f"   Apoio: {n_celulas.get(chave, 0)} de "
              f"{total_celulas.get(chave, 0)} células (modelo x bolsa) "
              f"monotônicas; {fora} descartada(s) por não monotonicidade.")
        print("   Leitura: ABAIXO desse ponto a versão reduzida é comprovadamente insegura; "
              "ACIMA dele este instrumento não separa, o que NÃO é certificado de segurança.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", type=Path, default=DEFAULT_DIR)
    ap.add_argument("--null-min", type=int, default=None,
                    help="rodadas a partir das quais a cifra é tratada como controle; "
                         "padrão = metade da spec de cada algoritmo")
    ap.add_argument("--q", type=float, default=0.05)
    ap.add_argument("--csv", type=Path, default=None)
    args = ap.parse_args()

    df = carregar(args.dir)
    if df.empty:
        print(f"nenhuma métrica encontrada em {args.dir}")
        return
    df = marcar(df, null_min=args.null_min, q=args.q)
    tabela(df)
    pisos(df)

    if args.csv:
        df.sort_values(["algo", "arm", "politica", "bolsa", "modelo", "rounds"]).to_csv(args.csv, index=False)
        print(f"\ncsv escrito em {args.csv}")


if __name__ == "__main__":
    main()
