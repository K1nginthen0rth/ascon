"""
Poder estatístico a priori do experimento v2 — Fase 5.2 (rodar ANTES de
qualquer treino real). Ver docs/plano_experimento_v2/06_implementacao_passo_a_passo.md
Fase 5.2 e 04_protocolo_metricas_validacao.md §4.6 item 3.

Pergunta respondida: com os tamanhos de teste do experimento v2 (n=24.000
para o teste 4-classes; n=12.000 para cada par binário), qual é o MENOR
efeito verdadeiro acima do acaso que temos 80% de chance de detectar a
α=0,05 (bicaudal)? Transforma o nulo de "ausência de evidência" em "tínhamos
poder para detectar X e não detectamos" — cita-se diretamente no texto.

Método: simulação de Monte Carlo (não fórmula fechada — F1-macro não tem
variância analítica simples como uma proporção binomial). Sob H0 (classi-
ficador exatamente no acaso), gera-se M datasets independentes de tamanho n
e mede-se a distribuição amostral empírica de F1-macro — isso estima o erro
padrão (SE) de F1 nesse tamanho de amostra sem precisar de bootstrap
aninhado (bootstrap-dentro-de-Monte-Carlo seria caro demais para varrer
vários tamanhos de efeito). Com o SE estimado, o menor efeito detectável
(MDE) com poder 1-β a nível α é a fórmula padrão de poder para diferença
de médias:

    MDE = (z_{α/2} + z_β) * SE

Concluído com uma verificação de poder EMPÍRICA (não só analítica): para o
MDE encontrado, simula-se diretamente sob H1 (classificador com esse
desempenho verdadeiro) e mede-se a fração de repetições em que o IC
bootstrap de 95% exclui o nível de acaso — deve bater ~80%.

Uso:
    python scripts/power_analysis_v2.py
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import numpy as np  # noqa: E402
from scipy.stats import norm  # noqa: E402
from sklearn.metrics import f1_score  # noqa: E402

from src.eval.metrics import compute_metrics  # noqa: E402

OUT_PATH = REPO_ROOT / "reports" / "v2" / "power_analysis.md"

ALPHA = 0.05
POWER_TARGET = 0.80
Z_ALPHA_2 = norm.ppf(1 - ALPHA / 2)
Z_BETA = norm.ppf(POWER_TARGET)

SCENARIOS = [
    {"name": "4 classes (teste principal)", "n": 24_000, "n_classes": 4},
    {"name": "par binário (comparação par-a-par)", "n": 12_000, "n_classes": 2},
]

M_NULL_SIMULATIONS = 2000       # repetições para estimar o SE de F1 sob H0
# Verificação empírica de poder: nº de repetições x bootstrap por repetição
# é o termo dominante de custo (cada repetição roda compute_metrics, que já
# faz seu próprio bootstrap). 150x150=22.500 chamadas de F1/bal_acc por
# cenário é suficiente para confirmar a ordem de grandeza do poder (SE de
# uma proporção com n=150 e p~0,8 é ~4%) sem o custo de 500x300 (~7-9min/
# cenário, que estourou o timeout mesmo sem concorrência de CPU).
M_POWER_VERIFICATION = 150
# Pontos da grade de conversão F1->acurácia. Discreta, e `searchsorted`
# arredonda para cima — ver a nota de premissas no relatório gerado.
_GRID_POINTS = 60
BOOTSTRAP_FOR_VERIFICATION = 150


def _simulate_classifier(
    rng: np.random.Generator, n: int, n_classes: int, true_accuracy: float,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Simula y_true/y_pred de um classificador com acurácia verdadeira
    `true_accuracy` sobre `n_classes` balanceadas: com probabilidade
    `true_accuracy` acerta a classe verdadeira, senão erra uniformemente
    entre as classes restantes. Acaso puro = true_accuracy = 1/n_classes.
    """
    y_true = rng.integers(0, n_classes, size=n)
    hits = rng.random(n) < true_accuracy
    y_pred = np.empty(n, dtype=int)
    y_pred[hits] = y_true[hits]
    n_miss = int((~hits).sum())
    if n_miss > 0:
        # erro uniforme entre as (n_classes - 1) classes restantes
        offset = rng.integers(1, n_classes, size=n_miss)
        y_pred[~hits] = (y_true[~hits] + offset) % n_classes
    return y_true, y_pred


def _null_f1_distribution(
    rng: np.random.Generator, n: int, n_classes: int, m: int,
) -> tuple[float, float]:
    """Retorna (média, desvio padrão) de F1-macro sob H0 (acaso puro),
    estimados por m simulações independentes de tamanho n."""
    chance = 1.0 / n_classes
    f1_vals = np.empty(m)
    for i in range(m):
        y_true, y_pred = _simulate_classifier(rng, n, n_classes, chance)
        f1_vals[i] = f1_score(y_true, y_pred, average="macro")
    return float(f1_vals.mean()), float(f1_vals.std(ddof=1))


def _verify_power_empirically(
    rng: np.random.Generator, n: int, n_classes: int, true_accuracy: float,
    chance_f1: float, m: int, n_bootstrap: int,
) -> float:
    """Simula m datasets sob a acurácia verdadeira dada e mede a fração em
    que o IC bootstrap de 95% de F1-macro exclui `chance_f1` — poder
    empírico do procedimento de detecção realmente usado no projeto."""
    detections = 0
    for _ in range(m):
        y_true, y_pred = _simulate_classifier(rng, n, n_classes, true_accuracy)
        report = compute_metrics(y_true, y_pred, n_bootstrap=n_bootstrap, seed=int(rng.integers(0, 2**31)))
        if report.f1_macro_ci[0] > chance_f1:
            detections += 1
    return detections / m


def analyze_scenario(scenario: dict, seed: int) -> dict:
    rng = np.random.default_rng(seed)
    n, n_classes, name = scenario["n"], scenario["n_classes"], scenario["name"]
    chance_acc = 1.0 / n_classes

    chance_f1_mean, se_f1 = _null_f1_distribution(rng, n, n_classes, M_NULL_SIMULATIONS)
    mde_f1 = (Z_ALPHA_2 + Z_BETA) * se_f1

    # Efeito em termos de ACURÁCIA equivalente (mais interpretável no texto):
    # calibra empiricamente por busca em pequena grade em vez de assumir
    # relação linear F1<->acurácia (que só vale aproximadamente perto do
    # acaso). `np.searchsorted` exige um array ORDENADO/monótono — uma
    # única simulação por ponto da grade é ruidosa o bastante (SE~0.003)
    # para não ser monótona por acaso, o que quebraria a busca
    # silenciosamente. Corrigido: várias repetições por ponto (reduz o
    # ruído) + `np.maximum.accumulate` força monotonicidade (isotônica)
    # antes da busca — sem isso, um mde_true_accuracy visivelmente errado
    # (bem abaixo do esperado) passava sem nenhum erro ou aviso.
    target_f1 = chance_f1_mean + mde_f1
    acc_grid = np.linspace(chance_acc, min(chance_acc + 0.15, 0.99), _GRID_POINTS)
    n_reps_per_point = 20
    f1_at_acc = np.array([
        np.mean([
            f1_score(*_simulate_classifier(rng, n, n_classes, acc), average="macro")
            for _ in range(n_reps_per_point)
        ])
        for acc in acc_grid
    ])
    f1_at_acc_monotonic = np.maximum.accumulate(f1_at_acc)
    mde_acc_idx = int(np.searchsorted(f1_at_acc_monotonic, target_f1))
    mde_acc_idx = min(mde_acc_idx, len(acc_grid) - 1)
    mde_true_accuracy = float(acc_grid[mde_acc_idx])
    mde_pp = (mde_true_accuracy - chance_acc) * 100

    empirical_power = _verify_power_empirically(
        rng, n, n_classes, mde_true_accuracy, chance_f1_mean,
        M_POWER_VERIFICATION, BOOTSTRAP_FOR_VERIFICATION,
    )

    return {
        "name": name,
        "n": n,
        "n_classes": n_classes,
        "chance_accuracy": chance_acc,
        "chance_f1_macro": chance_f1_mean,
        "se_f1_macro": se_f1,
        "mde_f1_macro": mde_f1,
        "mde_true_accuracy": mde_true_accuracy,
        "mde_percentage_points_above_chance": mde_pp,
        "empirical_power_at_mde": empirical_power,
    }


def main() -> None:
    # Windows: stdout redirecionado (arquivo/pipe) usa cp1252 por padrão,
    # que não cobre caracteres gregos (α/β usados nos prints abaixo) —
    # força UTF-8 para funcionar tanto no console quanto redirecionado.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    print(f"Poder estatístico a priori — α={ALPHA}, poder alvo={POWER_TARGET}")
    print(f"z_alpha/2={Z_ALPHA_2:.4f}  z_beta={Z_BETA:.4f}\n")

    results = []
    for i, scenario in enumerate(SCENARIOS):
        print(f"Cenário: {scenario['name']} (n={scenario['n']}, "
              f"{scenario['n_classes']} classes)...", flush=True)
        r = analyze_scenario(scenario, seed=42 + i)
        results.append(r)
        print(f"  F1-macro sob acaso: {r['chance_f1_macro']:.4f} "
              f"(SE={r['se_f1_macro']:.5f})")
        print(f"  Menor efeito detectável (MDE): F1-macro +{r['mde_f1_macro']:.4f} "
              f"<=> acurácia verdadeira {r['mde_true_accuracy']:.4f} "
              f"(+{r['mde_percentage_points_above_chance']:.2f} p.p. acima do acaso)")
        print(f"  Verificação empírica de poder no MDE: {r['empirical_power_at_mde']*100:.1f}% "
              f"(alvo: {POWER_TARGET*100:.0f}%)\n", flush=True)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write("# Poder estatístico a priori — experimento v2\n\n")
        f.write(f"α={ALPHA}, poder alvo={POWER_TARGET*100:.0f}%. Método: simulação de "
                f"Monte Carlo (ver docstring de `scripts/power_analysis_v2.py`) — "
                f"F1-macro não tem fórmula analítica simples de variância como uma "
                f"proporção binomial, então o erro padrão foi estimado empiricamente "
                f"por {M_NULL_SIMULATIONS} simulações independentes sob H0 por cenário.\n\n")
        f.write("| Cenário | n (teste) | F1 sob acaso | MDE (F1) | Acurácia verdadeira no MDE "
                "| Efeito (p.p. acima do acaso) | Poder empírico no MDE |\n")
        f.write("|---|---|---|---|---|---|---|\n")
        for r in results:
            f.write(
                f"| {r['name']} | {r['n']:,} | {r['chance_f1_macro']:.4f} | "
                f"+{r['mde_f1_macro']:.4f} | {r['mde_true_accuracy']:.4f} | "
                f"+{r['mde_percentage_points_above_chance']:.2f} p.p. | "
                f"{r['empirical_power_at_mde']*100:.1f}% |\n"
            )
        f.write(
            "\n**Interpretação:** com os tamanhos de teste do experimento v2, um "
            "resultado nulo (F1-macro dentro do IC do acaso) não significa "
            "\"ausência de evidência\" — significa que um efeito verdadeiro do "
            "tamanho do MDE reportado acima teria sido detectado com a "
            "probabilidade da coluna **Poder empírico no MDE**: "
            + "; ".join(f"{r['name']} = {r['empirical_power_at_mde']*100:.0f}%"
                        for r in results)
            + ". Efeitos menores que o MDE podem existir sem serem detectáveis "
            "nesta escala de amostra; essa é uma limitação declarada do desenho, "
            "não uma alegação de \"prova de ausência de diferença\".\n"
        )
        f.write(
            f"\n> **Por que o poder empírico não é exatamente {POWER_TARGET*100:.0f}%.** "
            f"{POWER_TARGET*100:.0f}% é o ALVO usado para derivar o MDE pela "
            "fórmula `(z_α/2 + z_β)·SE`, não um valor medido. A verificação "
            "empírica roda o procedimento e mede o que de fato acontece; as duas "
            "coisas divergem por três motivos, todos declarados aqui:\n"
            "> \n"
            "> 1. **O SE é estimado só sob H₀.** A fórmula supõe que o erro "
            "padrão de F1 é o mesmo sob H₀ e sob a alternativa, o que não é "
            "exato.\n"
            "> 2. **A conversão F1→acurácia usa uma grade discreta** "
            f"({_GRID_POINTS} pontos) com `searchsorted`, que arredonda para "
            "cima — o MDE efetivo fica ligeiramente acima do alvo, e o poder "
            "medido, acima de 80% (é o caso do cenário de 4 classes).\n"
            f"> 3. **A verificação usa `n_bootstrap={BOOTSTRAP_FOR_VERIFICATION}` "
            f"e {M_POWER_VERIFICATION} repetições**, contra 1000 na produção. "
            f"Com {M_POWER_VERIFICATION} repetições, um poder medido de ~80% tem "
            f"incerteza de ±{1.96 * (0.8 * 0.2 / M_POWER_VERIFICATION) ** 0.5 * 100:.1f} "
            "p.p. (IC 95%) — ou seja, o valor do par binário não é distinguível "
            "de 80%.\n"
            "> \n"
            "> 4. **O MDE é calculado sob amostras i.i.d., e o desenho é "
            "AGRUPADO.** Esta simulação sorteia amostras independentes; o "
            "dado real tem 100 slots por chave. O bootstrap de produção "
            "passou a ser por cluster de chave (`compute_metrics(groups=...)`, "
            "2026-08-24), e sob efeito de chave o IC fica até **2,3x mais "
            "largo** que o i.i.d. — logo o MDE efetivo é proporcionalmente "
            "MAIOR que o reportado aqui. Tornar esta simulação cluster-aware "
            "exigiria fixar um ICC (quanto da variância é entre chaves), que "
            "é uma suposição de modelagem e não uma medição — só será "
            "estimável depois da rodada real. **Trate os valores desta "
            "tabela como LIMITE INFERIOR do MDE**, não como o número final.\n"
            "> \n"
            "> **Premissa adicional, também declarada:** o classificador simulado "
            "erra UNIFORMEMENTE entre as classes restantes, o que maximiza o "
            "F1-macro para uma dada acurácia. Um classificador fraco real erra de "
            "forma estruturada (confunde pares específicos), então o MDE em "
            "pontos percentuais aqui é **otimista** — o efeito real necessário "
            "para detecção tende a ser um pouco maior.\n"
        )
    print(f"Relatório salvo em {OUT_PATH}")


if __name__ == "__main__":
    main()
