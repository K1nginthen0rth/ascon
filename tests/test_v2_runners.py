"""
Testes de regressão dos runners v2 (`scripts/run_v2_*.py`,
`extract_features_v2.py`, `consolidate_v2.py`).

**Motivo de existir:** uma auditoria de aderência (2026-08-23) encontrou 2
bloqueadores de execução e vários problemas metodológicos, e TODOS viviam
exatamente nesta faixa de código — ~3.600 linhas que os 232 testes do
projeto não tocavam. Os testes abaixo travam cada bug corrigido; não são
testes de "o pipeline roda" (isso é caro e é feito por rodada real de
validação), são testes do PONTO ESPECÍFICO que quebrou.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import torch

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import scripts.consolidate_v2 as consolidate_v2  # noqa: E402
import scripts.extract_features_v2 as extract_v2  # noqa: E402
import scripts.run_v2_caminho_a as caminho_a  # noqa: E402
import scripts.run_v2_caminho_f as caminho_f  # noqa: E402
import scripts.run_v2_caminhos_bce as caminhos_bce  # noqa: E402
from src.models.hybrid import _ckpt_path, _load_ckpt, _save_ckpt  # noqa: E402


# ---------------------------------------------------------------------------
# BLOQUEADOR 1 — Caminho F abortava com as 3 seeds de B/C/E
# ---------------------------------------------------------------------------

def test_nenhuma_rodada_final_vaza_para_o_lado_out_of_fold():
    """
    `run_v2_caminhos_bce.py` grava `final_seed7/107/207` no braço
    controlado. A versão anterior do F usava um conjunto FIXO
    {"final","final_seed7"} para os dois lados do filtro, então 107 e 207
    caíam no lado out-of-fold — e são predições sobre chaves de TESTE. O
    assert de vazamento derrubava o script inteiro.
    """
    todas = [f"final_seed{s}" for s in caminhos_bce.FINAL_SEEDS] + ["final", "0", "1"]
    serie = pd.Series(todas)
    oof = [f for f, is_fin in zip(todas, caminho_f._is_final_fold(serie)) if not is_fin]
    assert not any(f.startswith("final") for f in oof), (
        f"rodada final vazou para o lado OOF: {oof}")
    assert set(oof) == {"0", "1"}


def test_apenas_a_seed_principal_alimenta_o_meta_modelo():
    """As seeds 107/207 são o robustez-check de B/C/E, não insumo do F —
    usá-las daria várias predições da mesma fonte para o mesmo sample_id."""
    assert "final_seed7" in caminho_f.FINAL_SOURCE_TAGS
    assert "final_seed107" not in caminho_f.FINAL_SOURCE_TAGS
    assert "final_seed207" not in caminho_f.FINAL_SOURCE_TAGS


# ---------------------------------------------------------------------------
# BLOQUEADOR 2 — checkpoint perdia o melhor estado ao retomar
# ---------------------------------------------------------------------------

def test_checkpoint_preserva_best_state(tmp_path):
    """
    `_save_ckpt` gravava `model_state` (época corrente), `best_val_loss` e
    `best_epoch`, mas NÃO os pesos da melhor época. Ao retomar,
    `best_state` voltava None e, se nenhuma época seguinte batesse o
    `best_val` herdado, o modelo devolvido era o da última época — com o
    `best_epoch` do JSON apontando outra. Kaggle/Colab dependem de
    retomada, então isso atingiria B, C e E.
    """
    model = torch.nn.Linear(4, 2)
    optim = torch.optim.Adam(model.parameters())
    best_state = {k: v.clone().cpu() for k, v in model.state_dict().items()}

    path = _ckpt_path(tmp_path, fold_id=0, cnn_id="t")
    _save_ckpt(path, epoch=3, fold_id=0, model=model, optimizer=optim,
               best_val=0.1234, best_epoch=2, best_state=best_state)

    model2 = torch.nn.Linear(4, 2)
    optim2 = torch.optim.Adam(model2.parameters())
    start_ep, best_val, best_ep, restored = _load_ckpt(path, model2, optim2, "cpu")

    assert (start_ep, best_val, best_ep) == (4, 0.1234, 2)
    assert restored is not None, "best_state não sobreviveu ao round-trip"
    for k in best_state:
        assert torch.allclose(restored[k], best_state[k])


def test_checkpoint_antigo_sem_best_state_nao_quebra(tmp_path):
    """Checkpoints gravados antes da correção não têm a chave — a
    retomada deve degradar (com aviso), nunca levantar KeyError."""
    model = torch.nn.Linear(4, 2)
    optim = torch.optim.Adam(model.parameters())
    path = _ckpt_path(tmp_path, fold_id=0, cnn_id="t")
    _save_ckpt(path, 3, 0, model, optim, 0.5, 2, best_state=None)
    payload = torch.load(path, map_location="cpu", weights_only=False)
    del payload["best_state"]            # simula o formato antigo
    torch.save(payload, path)

    _, _, _, restored = _load_ckpt(path, torch.nn.Linear(4, 2),
                                   torch.optim.Adam(torch.nn.Linear(4, 2).parameters()),
                                   "cpu")
    assert restored is None


# ---------------------------------------------------------------------------
# ITEM 4 — braço `shuffled` preservava a tag intacta
# ---------------------------------------------------------------------------

def _linha_sintetica(ct: bytes) -> dict:
    return {"sample_id": "Ascon-AEAD128_key_0001_slot000", "algorithm": "Ascon-AEAD128",
            "key_id": "key_0001", "nonce_id": 1, "len_pt": 65536, "len_ct": len(ct),
            "plaintext_source": "corpus", "plaintext_sha256": "0" * 64,
            "ciphertext": ct}


@pytest.fixture()
def ct_com_tag_marcada() -> bytes:
    """CT cujos 8 bytes finais (a janela de tag) são constantes e
    distintos do resto — assim dá para detectar se foram embaralhados."""
    corpo = bytes(np.random.default_rng(0).integers(0, 200, size=65544, dtype=np.uint8))
    return corpo[:-8] + b"\xff" * 8


def test_shuffled_embaralha_tambem_a_tag(ct_com_tag_marcada):
    """
    A regra "tag sempre do CT cru" existe por causa do TRUNCAMENTO no braço
    `controlado`. Aplicá-la ao `shuffled` deixava 8 das 641 features do
    controle negativo com a estrutura sequencial intacta — exatamente o que
    o controle existe para destruir.
    """
    row = _linha_sintetica(ct_com_tag_marcada)
    cru = extract_v2._extract_row(row, "cru")
    shuf = extract_v2._extract_row(row, "shuffled")

    # No cru a janela de tag é 0xFF puro: entropia zero, 1 valor único.
    assert cru["tag8_nunique"] == 1
    # No shuffled os 0xFF foram espalhados pelo CT inteiro, então a janela
    # final quase certamente tem mais de um valor distinto.
    assert shuf["tag8_nunique"] > 1, "a tag sobreviveu intacta ao embaralhamento"


def test_controlado_preserva_a_tag_do_ct_cru(ct_com_tag_marcada):
    """O contrário do teste acima: em `controlado` a tag TEM de vir do cru,
    senão o corte de 8 bytes faria a extração medir payload como tag."""
    row = _linha_sintetica(ct_com_tag_marcada)
    cru = extract_v2._extract_row(row, "cru")
    ctrl = extract_v2._extract_row(row, "controlado")
    assert ctrl["tag8_nunique"] == cru["tag8_nunique"] == 1


# ---------------------------------------------------------------------------
# ITEM 5 — braço de validação entrava na consolidação
# ---------------------------------------------------------------------------

def _escreve_metrica(dirpath: Path, run_id: str, braco: str, modelo: str) -> None:
    dirpath.mkdir(parents=True, exist_ok=True)
    rec = {"run_id": run_id, "caminho": "A", "modelo": modelo, "braco": braco,
           "fold": "final", "timestamp": "2026-08-23T00:00:00",
           "confusion_matrix": [[1, 0], [0, 1]], "n_samples": 2,
           "f1_macro": 0.9, "f1_macro_ci_lower": 0.8, "f1_macro_ci_upper": 0.95,
           "accuracy": 0.9, "balanced_accuracy": 0.9, "ece": 0.1}
    with open(dirpath / f"{run_id}_metrics.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")


def test_consolidacao_descarta_braco_sintetico(tmp_path, monkeypatch, capsys):
    """
    `sintetico` é o parquet de features ALEATÓRIAS usado para validar
    encanamento — por construção não tem sinal. Sem filtro, uma rodada de
    validação entrava na tabela exploratória E no denominador do BH-FDR
    (demonstrado na auditoria: um modelo saiu com p bruto de 0,0296 sobre
    ruído puro).
    """
    monkeypatch.setattr(consolidate_v2, "REPORTS", tmp_path)
    _escreve_metrica(tmp_path / "caminho_a" / "controlado", "run_ok", "controlado", "RF")
    _escreve_metrica(tmp_path / "caminho_a" / "sintetico", "run_val", "sintetico", "RF")
    _escreve_metrica(tmp_path / "caminho_a" / "sintetico", "run_val2",
                     "sintetico_sem_keyholdout", "RF")

    df = consolidate_v2.load_all_metrics()
    assert set(df["braco"]) == {"controlado"}
    assert "não-oficial" in capsys.readouterr().out

    # E o escape-hatch continua existindo para inspeção manual.
    df_todos = consolidate_v2.load_all_metrics(drop_non_official=False)
    assert len(df_todos) == 3


# ---------------------------------------------------------------------------
# Itens menores que também viviam sem cobertura
# ---------------------------------------------------------------------------

def test_hpsearch_aceita_a_variante_de_condicionamento():
    """`--cond` era ignorado no `--mode hpsearch`: a busca do Caminho C
    rodava sempre em `sum1` mesmo quando o smoke elegia outra variante, e
    a CV depois usava a vencedora com HPs escolhidos sob outra escala."""
    import inspect
    assert "cond" in inspect.signature(caminhos_bce.run_hpsearch).parameters


def test_models_subset_filtra_tambem_stacking_e_replicas():
    """`--models RandomForest` filtrava só `build_models()`; as 4 rodadas
    de `run_literature_replicas` rodavam mesmo assim."""
    import inspect
    assert "models_subset" in inspect.signature(caminho_a.run_literature_replicas).parameters
    assert set(caminho_a.REPLICA_MODEL_NAMES) == {
        "Stacking", "HKNNRF_replica",
        "XGB_LGBM_hamming_replica", "Transformer_E20_replica",
    }


def test_permutacao_recebe_keyholdout_em_vez_de_ignorar():
    """Os dois esquemas de permutação são definidos por `key_id`, então
    `--no-keyholdout` não se aplica — mas precisa AVISAR, não ignorar
    em silêncio."""
    import inspect
    assert "keyholdout" in inspect.signature(caminho_a.analysis_permutation).parameters


# ---------------------------------------------------------------------------
# ITEM 7 — fit final do SVM-RBF também subamostrado (decisão de 2026-09-02)
# ---------------------------------------------------------------------------

def _dataset_sintetico_svm(n_keys: int, samples_por_chave: int, seed: int = 0):
    rng = np.random.default_rng(seed)
    n = n_keys * samples_por_chave
    X = rng.normal(size=(n, 5))
    y = rng.integers(0, 2, size=n)
    groups = np.repeat([f"key_{i}" for i in range(n_keys)], samples_por_chave)
    return X, y, groups


def test_svm_subsample_respeita_o_tamanho_pedido():
    """`_svm_subsample` é o bloco que faltava: antes desta correção o fit
    final usava `X_train`/`y_train` inteiros, sem nenhum corte — daí o
    orçamento de 40-80h medido pela 6a auditoria (escala n^2,85)."""
    X, y, groups = _dataset_sintetico_svm(n_keys=50, samples_por_chave=200)  # 10.000
    Xs, ys, gs = caminho_a._svm_subsample(X, y, groups, size=1000, seed=7)
    assert len(ys) == 1000
    assert Xs.shape == (1000, X.shape[1])
    assert len(gs) == 1000


def test_svm_subsample_nao_corta_se_ja_menor_que_o_alvo():
    X, y, groups = _dataset_sintetico_svm(n_keys=5, samples_por_chave=10)  # 50
    Xs, ys, gs = caminho_a._svm_subsample(X, y, groups, size=1000, seed=7)
    assert len(ys) == 50  # devolve tudo, não estoura pedindo mais do que existe


def test_fit_svm_with_search_fit_final_usa_subamostra_nao_o_fold_inteiro():
    """Regressão do orçamento de 40-80h: o fit final tem que rodar em
    `SVM_FINAL_FIT_SUBSAMPLE` amostras, não nas 10.000 do fold completo —
    e isso precisa aparecer registrado no dict de metadados retornado,
    não só acontecer em silêncio."""
    X, y, groups = _dataset_sintetico_svm(n_keys=50, samples_por_chave=500)  # 25.000
    modelo, meta = caminho_a.fit_svm_with_search(X, y, groups, seed=7)
    assert meta["final_fit_subsample"] == caminho_a.SVM_FINAL_FIT_SUBSAMPLE
    assert meta["final_fit_subsample"] < len(y)
    # o SVM ajustado de fato viu poucas amostras de suporte, nao 10.000
    assert modelo.support_.shape[0] <= meta["final_fit_subsample"]


def test_fit_svm_with_search_grupos_insuficientes_tambem_subamostra():
    """O caminho de fallback (poucos grupos para CV interna) também
    precisa respeitar `SVM_FINAL_FIT_SUBSAMPLE` — não só o caminho
    principal da busca de hiperparâmetros."""
    X, y, groups = _dataset_sintetico_svm(n_keys=1, samples_por_chave=25000)
    _, meta = caminho_a.fit_svm_with_search(X, y, groups, seed=7)
    assert meta["search"] == "pulada (grupos insuficientes)"
    assert meta["final_fit_subsample"] == caminho_a.SVM_FINAL_FIT_SUBSAMPLE
    assert meta["final_fit_subsample"] < len(y)


def test_subsampled_svc_trunca_o_fit():
    """Achado ao vivo (2026-09-02): o SVM-RBF DENTRO do Stacking não
    passava por `fit_svm_with_search` — era um `SVC` cru, sem nenhuma
    subamostra, ajustado várias vezes por fold pela CV interna do
    `StackingClassifier`. Rodando o Caminho A completo pela primeira vez
    com dado real, isso sozinho travou um fold por horas."""
    X, y, groups = _dataset_sintetico_svm(n_keys=50, samples_por_chave=500)  # 25.000
    modelo = caminho_a.SubsampledSVC(C=1.0, gamma="scale", random_state=7)
    modelo.fit(X, y)
    assert modelo._svc.support_vectors_.shape[0] <= caminho_a.SVM_FINAL_FIT_SUBSAMPLE
    modelo.predict(X[:10])  # não levanta
    modelo.decision_function(X[:10])  # não levanta
    assert not hasattr(modelo, "predict_proba"), (
        "predict_proba não pode existir sem probability=True — "
        "senão o StackingClassifier tenta chamar e quebra em runtime, "
        "e probability=True adiciona sua PRÓPRIA CV interna (Platt scaling), "
        "reintroduzindo o mesmo tipo de custo que esta classe existe para evitar."
    )


def test_build_stacking_model_usa_svm_subamostrado():
    """Trava a troca do SVC cru pelo SubsampledSVC dentro do Stacking —
    sem isso, o teste anterior não garante nada sobre o pipeline real."""
    groups = np.repeat([f"key_{i}" for i in range(10)], 5)
    stack = caminho_a.build_stacking_model(seed=7, groups=groups)
    svm_estimator = dict(stack.estimators)["svm"]
    assert isinstance(svm_estimator, caminho_a.SubsampledSVC)


def test_build_stacking_model_nao_usa_gamma_scale():
    """Regressão do achado ao vivo de 2026-09-02: `gamma="scale"` (o
    default do sklearn, calculado a partir de 1/(n_features*X.var())) fez
    o SVM do Stacking prever UMA ÚNICA classe sempre em dado real, nos 3
    primeiros pares rodados (Ascon-vs-GIFT, Ascon-vs-Grain,
    Ascon-vs-Schwaemm) — os 20.000 pontos da subamostra viraram vetor de
    suporte inteiros (kernel achatado a ponto de virar quase constante).
    `gamma=0.01` (valor fixo, não depende da variância da amostra) não
    reproduz o problema. Não é sobre estabilidade sintética — é travar que
    ninguém troque de volta pro default sem repetir a verificação em dado
    real."""
    groups = np.repeat([f"key_{i}" for i in range(10)], 5)
    stack = caminho_a.build_stacking_model(seed=7, groups=groups)
    svm_estimator = dict(stack.estimators)["svm"]
    assert svm_estimator.gamma != "scale"
    assert svm_estimator.gamma == 0.01


# ---------------------------------------------------------------------------
# ITEM 6 — `--max-train-samples` colapsava a diversidade de chaves
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not caminhos_bce.PQ_IN.exists(),
                    reason="dataset v2 real não disponível neste ambiente")
def test_max_train_samples_preserva_todas_as_chaves():
    """
    O parquet está ordenado por chave, então a versão anterior (parar na
    N-ésima linha lida) treinava com ~50 das 192 chaves do fold —
    diversidade de chave é exatamente o que o key-holdout existe para
    medir. O teto agora é uma cota POR CHAVE.
    """
    folds = caminhos_bce.load_folds()
    tr_keys = set(folds["folds"][0]["train_keys"])
    _, y, _, kids = caminhos_bce.load_cts(
        tr_keys, caminhos_bce.REAL_ALGORITHMS, "controlado", max_samples=2000)

    assert set(kids) == tr_keys, (
        f"cota colapsou a diversidade: {len(set(kids))} de {len(tr_keys)} chaves")
    # E o balanceamento de classes sobrevive (cota é múltipla do nº de classes).
    counts = np.bincount(y, minlength=len(caminhos_bce.REAL_ALGORITHMS))
    assert counts.min() == counts.max(), f"classes desbalanceadas: {counts.tolist()}"


# ---------------------------------------------------------------------------
# mRMR — o pacote real, não uma reimplementação local que o sombreie
# ---------------------------------------------------------------------------

def test_mrmr_resolve_para_o_pacote_instalado():
    """
    Até 2026-08-23 havia um `mrmr.py` na RAIZ do repositório com uma
    reimplementação caseira. Como todo script de produção e o `conftest.py`
    fazem `sys.path.insert(0, REPO_ROOT)`, a raiz vinha antes do
    site-packages e o arquivo local sombreava o pacote **em toda execução
    dentro do projeto** — rodando de outro diretório, o pacote real era
    usado. Além de tornar o resultado dependente do diretório, a versão
    local usava `random_state=0` fixo (viola a seed canônica FS=13) e não
    era o algoritmo citado no docstring.
    """
    import mrmr
    origem = Path(mrmr.__file__).resolve()
    assert "site-packages" in origem.parts or "site-packages" in str(origem), (
        f"`mrmr` resolveu para {origem} — há um módulo local sombreando o "
        f"pacote instalado (era exatamente o bug de 2026-08-23)")
    assert not (REPO_ROOT / "mrmr.py").exists(), (
        "mrmr.py voltou para a raiz do repositório — vai sombrear o pacote")


# ---------------------------------------------------------------------------
# 4a auditoria (2026-08-23) — 2 bloqueadores
# ---------------------------------------------------------------------------

def test_shuffled_nao_vaza_comprimento(ct_com_tag_marcada):
    """
    **B2.** O braço `shuffled` só permutava, sem truncar — Grain ficava em
    65.544 e os demais em 65.552. Seis features são função EXATA do
    comprimento (compression_ratio_zlib/lzma, ngram_4_nunique/entropy/
    collision_rate, ngram_3_max_freq: AUC 1,0000 usando só bytes uniformes
    que diferem no comprimento), e embaralhar não apaga comprimento. O
    CONTROLE NEGATIVO ficava com um separador perfeito intacto.
    """
    grain = ct_com_tag_marcada[:65544]
    outro = ct_com_tag_marcada[:65544] + b"\x00" * 8      # 65.552
    assert len(grain) != len(outro)

    for br in ("controlado", "shuffled"):
        lg = len(extract_v2._ct_for_branch(grain, br, "s1"))
        lo = len(extract_v2._ct_for_branch(outro, br, "s2"))
        assert lg == lo, f"braço {br!r} deixa comprimentos diferentes ({lg} vs {lo})"

    # `cru` DEVE preservar a diferença — é o braço que existe para medi-la.
    assert len(extract_v2._ct_for_branch(grain, "cru", "s1")) != \
           len(extract_v2._ct_for_branch(outro, "cru", "s2"))


def test_caminho_f_filtra_por_braco(tmp_path, monkeypatch):
    """
    **B1.** A ablação `--no-keyholdout` grava no MESMO diretório com o
    MESMO `run_id`, mudando só o `braco`. Como o glob era por `run_id` e o
    filtro só por fold, essas linhas entravam na matriz OOF — e o split
    dessa ablação é aleatório POR AMOSTRA, então seus folds de CV contêm
    chaves do teste canônico. O assert de vazamento derrubava o script, na
    sequência que o próprio runbook manda rodar.
    """
    import numpy as np
    from src.eval.reporting import report_eval

    out = tmp_path / "caminho_a" / "controlado"
    ALG = ["A", "B"]
    y = np.array([0, 1, 0, 1])
    proba = np.eye(2)[y]
    for braco in ("controlado", "controlado_sem_keyholdout"):
        report_eval(run_id="run", caminho="A", modelo="RF", braco=braco, fold=0,
                    y_true=y, y_pred=y, y_proba=proba,
                    sample_ids=[f"{braco}_{i}" for i in range(4)],
                    key_ids=["k1", "k1", "k2", "k2"],
                    class_names=ALG, labels=[0, 1], out_dir=out, n_bootstrap=10)

    monkeypatch.setattr(caminho_f, "REPORTS", tmp_path)
    monkeypatch.setattr(caminho_f, "CAMINHO_DIRS", {"A": "caminho_a"})
    oof = caminho_f._collect("controlado", "run", want_final=False)
    assert set(oof["braco"]) == {"controlado"}, (
        f"braços vazados para a matriz OOF: {sorted(set(oof['braco']))}")


def test_selector_transform_imputa_nan():
    """**M2.** `fit` imputava NaN→0 e `transform` não — divergência que só
    não aparecia porque nenhuma feature devolve NaN hoje."""
    from src.features.selector import LWCFeatureSelector, SelectorConfig
    import numpy as np
    rng = np.random.default_rng(0)
    X = rng.standard_normal((80, 12))
    y = rng.integers(0, 2, 80)
    X[:, 0] += y * 3.0
    sel = LWCFeatureSelector(SelectorConfig(random_state=13, top_k_mi=8,
                                            n_features_mrmr=4, boruta_max_iter=5))
    sel.fit(X, y, feature_names=[f"f{i}" for i in range(12)])

    X_nan = X.copy()
    X_nan[0, :] = np.nan
    out = sel.transform(X_nan)
    assert np.isfinite(out).all(), "transform propagou NaN"


def test_train_cnn_fixed_retoma_de_checkpoint(tmp_path):
    """
    **B1 (bloqueador).** `train_cnn_fixed` desempacotava 3 valores de
    `_load_ckpt`, que devolve 4 desde a correção do `best_state` — toda
    RETOMADA levantava `ValueError: too many values to unpack`. É a função
    do modelo final de B/C/E, que grava checkpoint por época e roda em
    Kaggle/Colab, onde a sessão expira: a primeira execução passava e
    qualquer retomada quebrava. O teste existente cobria `train_cnn`, não
    esta — por isso passou pelas 253.
    """
    import os
    import torch
    from src.models.cnn2d import CiphertextCNN2D
    from src.models.hybrid import (
        CiphertextCoocDataset, _ckpt_path, _save_ckpt, train_cnn_fixed,
    )

    rng = np.random.default_rng(0)
    cts = [os.urandom(2000) for _ in range(16)]
    ds = CiphertextCoocDataset(cts, rng.integers(0, 4, 16))

    model = CiphertextCNN2D(n_classes=4)
    optim = torch.optim.Adam(model.parameters())
    _save_ckpt(_ckpt_path(tmp_path, 99, "x"), 1, 99, model, optim,
               best_val=0.5, best_epoch=1, best_state=None)

    # Não deve levantar — antes da correção, ValueError aqui.
    out = train_cnn_fixed(model, ds, n_epochs=2, device="cpu", seed=7,
                          fold_id=99, cnn_id="x", ckpt_dir=tmp_path, batch_size=8)
    assert out is not None
