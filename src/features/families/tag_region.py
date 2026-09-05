"""Família 12: separação tag vs. payload (comparação principal + exploratória).

Justificativa: a tag é gerada por mecanismo estruturalmente distinto em cada
algoritmo (squeeze da permutação / máscara COFB / acumulador dedicado /
finalização Schwaemm), enquanto o payload é desenhado para parecer uniforme
nos quatro — se há lugar provável para uma assinatura residual, é a tag
(ver docs/plano_experimento_v2/02_features_e_selecao.md).

**Janela comum de 8 bytes para a TAG (`tag8`):** usar o `ABYTES` real de
cada algoritmo (16 para Ascon/GIFT/Sparkle, 8 para Grain) introduziria um
viés de estimador de amostra pequena que separa o Grain por TAMANHO da
janela, não por conteúdo (entropia de n≪256 bytes uniformes tende a
log2(n), independente da fonte — ≈3,0 bits p/ 8 bytes vs. ≈4,0 bits p/ 16).
Corrigido: janela comum de 8 bytes (mínimo entre os algoritmos) para os
quatro na comparação principal. Esse argumento vale só para a TAG — ver
correção abaixo sobre por que ele NÃO se aplica a `payload_rest`.

**`payload_rest` — bug real de 2026-08-28, corrigido.** A primeira versão
definia `payload_rest = ct[:-8]`, reusando a MESMA janela de 8 bytes do
`tag8` por conveniência — sem perceber que isso serve a dois propósitos
opostos. Para o Grain (ABYTES=8), cortar os últimos 8 bytes remove a tag
inteira: `payload_rest` fica limpo. Para Ascon/GIFT-COFB/Schwaemm
(ABYTES=16), cortar só 8 bytes deixa a OUTRA METADE da tag (8 bytes reais
de tag) disfarçada de payload. Essa assimetria — não o conteúdo da tag —
levou o Caminho A a distinguir Grain de qualquer um dos outros três com
F1=0,9994 via XGBoost (RandomForest capturou parte, 0,69; modelos
lineares ficaram no acaso, 0,50 — a assinatura clássica de um viés fraco
e difuso que só boosting agrega bem). Os 3 pares SEM Grain (todos
ABYTES=16, logo sem essa assimetria) deram acaso mesmo com XGBoost,
isolando a causa. Confirmado por experimento (não só por inferência):
reconstruindo a fronteira com o `ABYTES` real de cada algoritmo — payload
puro (65.536 bytes, idêntico para os dois porque cifram o mesmo
plaintext) e a costura simétrica de 16 bytes ancorada na fronteira
verdadeira — os dois voltam a dar acaso puro, mesmo com XGBoost. Detalhe
completo: `docs/plano_experimento_v2/05_execucao_riscos_pendencias.md`
§5.14.

Diferente do argumento do `tag8`, aqui NÃO há viés de amostra pequena a
evitar — o payload tem dezenas de milhares de bytes não importa quantos
sejam excluídos, então não há razão para usar uma janela pequena e
comparável entre os algoritmos. A correção certa é o oposto: excluir
sempre o SUFICIENTE para garantir que nenhum byte de tag sobre para
NINGUÉM, com um comprimento FIXO e único (nunca calculado a partir do
algoritmo da amostra — a extração de features não deve consultar o
rótulo para decidir como processar os bytes). `_PAYLOAD_REST_LEN` abaixo
é esse valor: derivado uma única vez, do menor comprimento de ciphertext
cru entre as 6 classes do dataset (Grain, 65.544) menos o maior ABYTES
entre os algoritmos reais (16) — logo sempre dentro da região de payload
de qualquer um dos seis, com o MESMO comprimento para todos.

**Sempre sobre o CT cru** — nunca sobre o braço `controlado` (truncado),
que corta os últimos bytes do CT e destruiria/deslocaria a tag dos
algoritmos com ABYTES=16 (ver `01_algoritmos_e_dataset.md` §1.6).

**Tag completa por algoritmo:** análise exploratória separada
(`extract_tag_region_full`), com o viés de amostra pequena declarado —
não entra na comparação principal, e não é chamada por nenhum script de
produção hoje (função exploratória, não integrada ao pipeline).

Fronteira sempre via `abytes` explícito (parâmetro obrigatório) — nunca
offset fixo hardcoded.
"""
from __future__ import annotations

import numpy as np

_NAN = float("nan")
_COMMON_WINDOW = 8  # min(ABYTES) entre os 4 algoritmos — usado só por `tag8`, ver docstring

# Comprimento cru mínimo entre as 6 classes do dataset v2 (Grain-128AEAD,
# 65.536 payload + 8 tag) menos o maior ABYTES entre os algoritmos AEAD reais
# (16, em Ascon/GIFT-COFB/Schwaemm256-128). Constante fixa e única — nunca
# calculada a partir do algoritmo da amostra (ver docstring do módulo).
_MIN_RAW_LEN = 65544
_MAX_ABYTES = 16
_PAYLOAD_REST_LEN = _MIN_RAW_LEN - _MAX_ABYTES  # 65528


def _window_stats(window: bytes, prefix: str) -> dict[str, float]:
    """Histograma agregado + entropia + χ² para uma janela pequena de bytes."""
    n = len(window)
    if n == 0:
        return {
            f"{prefix}_entropy": _NAN,
            f"{prefix}_nunique": _NAN,
            f"{prefix}_max_freq": _NAN,
            f"{prefix}_chi2_statistic": _NAN,
        }

    arr = np.frombuffer(window, dtype=np.uint8)
    counts = np.bincount(arr, minlength=256).astype(float)
    probs = counts / n
    nz = probs[probs > 0]
    entropy = float(-np.sum(nz * np.log2(nz)))
    nunique = float(np.count_nonzero(counts))
    max_freq = float(probs.max())

    # χ² contra uniforme de 256 bins — só a estatística (não o p-value: dof
    # elevado com n pequeno deixa o p-value pouco informativo aqui).
    expected = np.full(256, n / 256.0)
    chi2_stat = float(np.sum(((counts - expected) ** 2) / expected))

    return {
        f"{prefix}_entropy": entropy,
        f"{prefix}_nunique": nunique,
        f"{prefix}_max_freq": max_freq,
        f"{prefix}_chi2_statistic": chi2_stat,
    }


def extract_tag_region(ct: bytes) -> dict[str, float]:
    """Comparação principal: janela comum de 8 bytes finais (tag) vs.
    payload livre de qualquer byte de tag — sempre sobre o CT cru, mesmo
    tratamento para as 6 classes do dataset.

    `tag8` e `payload_rest` usam comprimentos DIFERENTES de propósito (ver
    docstring do módulo): `tag8` precisa ser uma janela pequena e comum
    pra ser comparável entre tags de tamanhos diferentes; `payload_rest`
    precisa excluir o suficiente pra nunca sobrar byte de tag de ninguém,
    o que não tem relação com o tamanho da janela do `tag8`.

    Args:
        ct: ciphertext cru (CT || tag), como bytes. NUNCA passar a versão
            truncada do braço `controlado` aqui.

    Returns:
        tag8_*: estatísticas da janela de 8 bytes finais.
        payload_rest_*: estatísticas dos primeiros `_PAYLOAD_REST_LEN`
            bytes (payload puro, mesmo comprimento para as 6 classes).
        NaN se len(ct) for menor que o necessário para qualquer um dos
        dois recortes.
    """
    if len(ct) < _COMMON_WINDOW or len(ct) < _PAYLOAD_REST_LEN:
        keys = [
            f"{p}_{s}"
            for p in ("tag8", "payload_rest")
            for s in ("entropy", "nunique", "max_freq", "chi2_statistic")
        ]
        return dict.fromkeys(keys, _NAN)

    tag_window = ct[-_COMMON_WINDOW:]
    payload_rest = ct[:_PAYLOAD_REST_LEN]

    result = _window_stats(tag_window, "tag8")
    result.update(_window_stats(payload_rest, "payload_rest"))
    return result


def extract_tag_region_full(ct: bytes, abytes: int) -> dict[str, float]:
    """Exploratório: tag COMPLETA (ABYTES real do algoritmo) vs. payload.

    **Não entra na comparação principal** — viés de amostra pequena varia
    com `abytes` entre algoritmos (ver docstring do módulo). Só para
    análise exploratória declarada, sempre sobre o CT cru.

    Args:
        ct: ciphertext cru (CT || tag).
        abytes: tamanho da tag em bytes, do wrapper do algoritmo (nunca
            offset fixo — 16 para Ascon/GIFT/Sparkle, 8 para Grain).

    Returns:
        tag_full_*: estatísticas da tag completa (abytes bytes finais).
        payload_full_*: estatísticas do payload completo (ct[:-abytes]).
        NaN se len(ct) < abytes.
    """
    if abytes <= 0:
        raise ValueError(f"abytes deve ser positivo; recebeu {abytes}.")
    if len(ct) < abytes:
        keys = [
            f"{p}_{s}"
            for p in ("tag_full", "payload_full")
            for s in ("entropy", "nunique", "max_freq", "chi2_statistic")
        ]
        return dict.fromkeys(keys, _NAN)

    tag = ct[-abytes:]
    payload = ct[:-abytes]

    result = _window_stats(tag, "tag_full")
    result.update(_window_stats(payload, "payload_full"))
    return result
