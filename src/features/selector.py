"""
Pipeline de seleção de features para classificação LWC ciphertext-only.

Pipeline v2, em 5 estágios (ver docs/plano_experimento_v2/02_features_e_selecao.md
§2.2; substitui o pipeline v1 de 3 estágios documentado em docs/contexto_inicial.md §2):
  0. Padronização z-score (fit no treino) — só para alimentar o VT do estágio 1;
     as demais etapas e a saída final continuam em escala original.
  1. VarianceThreshold sobre features PADRONIZADAS — na prática, descarta só
     constantes verdadeiras (ver correção abaixo).
  2. Mutual Information — corte de CONVENIÊNCIA (top-k), explicitamente SEM
     alegação estatística (ver nota abaixo).
  3. mRMR — define o conjunto final (relevância − redundância). Implementação:
     pacote `mrmr-selection` 0.2.8 (variante FCQ: relevância por estatística F,
     redundância por correlação de Pearson média), NÃO uma reimplementação
     local — ver a nota "qual mRMR" abaixo.
  4. Boruta [Kursa & Rudnicki 2010] — diagnóstico de estabilidade; reporta quantas
     features do mRMR também se confirmam contra shadow features, mas NÃO
     filtra o conjunto usado pelo classificador (apenas informativo/relatório).

**Correção do VT (motivada pela ablação v1, `scripts/run_ablation_fs_60k.py`):**
o corte bruto de VarianceThreshold(1e-5) em escala ABSOLUTA descartava 278/307
features do v1 (todo o histograma de bytes) por ESCALA, não por falta de
informação — frequências relativas têm variância ~5,9e-8 simplesmente por
serem números pequenos (média 1/256), não por serem constantes. Padronizando
antes, "baixa variância" volta a significar "genuinamente constante": uma
feature padronizada não-constante sempre tem variância ≈1; só as verdadeiras
constantes ficam com variância ≈0. O mesmo threshold (1e-5) agora filtra a
coisa certa.

**MI como corte de conveniência (não estatístico):** um limiar de MI com
pretensão de significância seria tão arbitrário quanto o antigo top-k cego —
o estimador de MI dá valores positivos pequenos até para ruído puro (viés
conhecido do estimador k-NN), então qualquer limiar "acima da média dos ≠0"
deixaria uma fração substancial de ruído passar. Por isso o MI aqui SÓ reduz
volume para o mRMR processar; a validação real de sinal-vs-ruído acontece no
RESULTADO FINAL do pipeline completo, por teste de permutação (mesma
metodologia já validada na ablação v1) — não em nenhum estágio intermediário.

**Sem RFE** neste seletor (decisão deliberada): RFE amarraria a seleção à
importância de um classificador específico e quebraria a comparação justa do
Caminho A, onde todos os modelos recebem o mesmo conjunto de features. A
réplica fiel do E20 (Yuan et al. 2026, Caminho A) usa RFE internamente como
parte do desenho original do estudo replicado — exceção deliberada e isolada
dentro do braço da réplica, que não usa este `LWCFeatureSelector` e não
contamina o pipeline padrão do projeto.

REGRA CRÍTICA: o `fit` deve ser chamado APENAS no X_train, dentro de cada fold
de CV. Selecionar no dataset completo é o vazamento documentado em
[Ambroise & McLachlan, PNAS 2002].

**Qual mRMR (correção de 2026-08-23):** até esta data existia um `mrmr.py`
na RAIZ do repositório com uma reimplementação caseira (relevância por
informação mútua com `random_state=0` fixo, redundância por correlação de
Pearson média, esquema de diferença). Como todo script de produção e o
`conftest.py` fazem `sys.path.insert(0, REPO_ROOT)`, a raiz vinha antes do
site-packages e esse arquivo **sombreava o pacote instalado em toda
execução dentro do projeto** — rodando de outro diretório, o pacote real
era usado. Quatro problemas: (a) o docstring e o plano citavam Peng et al.
2005 para um algoritmo que não era o deles, e isso viraria afirmação de
método na dissertação; (b) o `random_state=0` fixo violava a seed canônica
FS=13 (Regra de Ouro 1) e diferia da seed do estágio 1 do mesmo seletor;
(c) o resultado dependia do diretório de onde se rodava; (d) o laço fazia
~2,8 milhões de chamadas a `np.corrcoef` para p=350/K=150, ~0,4h por fold
(~10h no total) que nenhum documento de orçamento contabilizava.

O arquivo foi removido. Medido antes de remover, num cenário de sinal
fraco com ruído correlacionado: as duas implementações recuperam os 5
sinais plantados no top-20, mas as seleções COMPLETAS de 20 features
coincidem em apenas 5/20 — ou seja, o conjunto que alimenta o
classificador era substancialmente diferente. Usar o pacote é o que
sustenta a citação.

Referências:
  - Peng, H., Long, F., & Ding, C. (2005). IEEE TPAMI 27(8) — base
    conceitual do mRMR; a implementação usada é a do pacote
    `mrmr-selection`, cuja variante default (FCQ) difere do MID original.
  - Kursa, M. B., & Rudnicki, W. R. (2010). JSS 36(11).
  - Saeys, Y., Inza, I., & Larrañaga, P. (2007). Bioinformatics 23(19).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_selection import VarianceThreshold, mutual_info_classif


@dataclass
class SelectorConfig:
    """Hiperparâmetros do pipeline LWCFeatureSelector.

    Defaults recalibrados para o total de features do v2 (~641, 12 famílias
    — era ~307/6 famílias no v1): `top_k_mi` e `n_features_mrmr` maiores
    para manter proporção semelhante de corte em cada estágio.
    """

    variance_threshold: float = 1e-5  # aplicado sobre features PADRONIZADAS (estágio 0+1)
    top_k_mi:           int   = 350   # corte de CONVENIÊNCIA, não estatístico — ver docstring do módulo
    n_features_mrmr:    int   = 150
    boruta_max_iter:    int   = 100
    boruta_n_estimators: int | str = "auto"
    random_state:       int   = 13
    verbose:            int   = 0


class LWCFeatureSelector:
    """
    Seletor de features em 5 estágios (numeração do plano; internamente as
    chaves de `_stage_report` mantêm os nomes `stage1/2/3` do pipeline v1
    por compatibilidade com os consumidores existentes — ver nota no fit()).

    Estágio 0+1 (univariado, O(p)):
        - Padronização z-score (fit no treino) alimenta SÓ o VarianceThreshold
          — corrige o viés de escala absoluta do v1 (ver docstring do módulo)
        - Mutual Information classif → top-k (corte de conveniência, não
          estatístico — ver docstring do módulo)

    Estágio 2 (redundância):
        - mRMR seleciona n_features_mrmr maximizando relevância e minimizando
          redundância entre features (pacote `mrmr-selection`, variante FCQ)

    Estágio 3 (estabilidade, diagnóstico apenas):
        - Boruta reporta quais features do mRMR carregam sinal vs. baseline
          de "shadow features" embaralhadas [Kursa & Rudnicki 2010], mas o
          resultado NÃO altera o conjunto final (self._final_mask == mRMR)

    Sem RFE (ver docstring do módulo). Saída final sempre em escala
    ORIGINAL das features (a padronização do estágio 0 é interna ao VT,
    não se propaga ao `transform()`).

    Uso correto (dentro do fold):
        sel = LWCFeatureSelector()
        sel.fit(X_train, y_train, feature_names=cols)
        X_train_sel = sel.transform(X_train)
        X_val_sel   = sel.transform(X_val)
        X_test_sel  = sel.transform(X_test)

    Args:
        config: SelectorConfig com hiperparâmetros (defaults recalibrados
                para ~641 features/12 famílias do v2).
    """

    def __init__(self, config: Optional[SelectorConfig] = None) -> None:
        self.config = config or SelectorConfig()

        # Resultados de cada estágio
        self._feature_names_in : Optional[np.ndarray] = None
        self._stage1_mask      : Optional[np.ndarray] = None  # bool array após VT+MI
        self._stage2_mask      : Optional[np.ndarray] = None  # bool array após mRMR
        self._stage3_mask      : Optional[np.ndarray] = None  # bool array após Boruta
        self._final_mask       : Optional[np.ndarray] = None
        self._final_indices    : Optional[np.ndarray] = None
        self._stage_report     : dict = {}
        self._fitted           : bool = False

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def fit(
        self,
        X_train: np.ndarray | pd.DataFrame,
        y_train: np.ndarray | pd.Series,
        feature_names: Optional[list[str]] = None,
    ) -> "LWCFeatureSelector":
        """
        Ajusta o pipeline (5 estágios, ver docstring da classe/módulo) usando
        APENAS dados de treino.

        Args:
            X_train: matriz (n_samples, n_features). Aceita DataFrame ou ndarray.
            y_train: rótulos (n_samples,). Aceita Series, array ou lista.
            feature_names: nomes opcionais. Se X_train for DataFrame, são
                inferidos das colunas.
        """
        X, y, names = self._prepare(X_train, y_train, feature_names)
        cfg         = self.config
        n_in        = X.shape[1]

        # ---- Estágio 0: padronização z-score (só para alimentar o VT) ----
        # dp=0 (feature constante no treino) -> descarte direto, sem dividir
        # por zero: usamos um dp "seguro" de 1.0 só para a divisão não gerar
        # NaN/inf; como (x-mean)=0 para toda a coluna, o z-score fica
        # identicamente 0 (variância 0), então o VT abaixo já descarta essa
        # feature de qualquer forma — o valor do dp seguro nunca influencia
        # QUAIS features sobrevivem.
        train_mean   = X.mean(axis=0)
        train_std    = X.std(axis=0)
        zero_std_mask = train_std == 0.0
        n_zero_variance = int(zero_std_mask.sum())
        std_safe     = np.where(zero_std_mask, 1.0, train_std)
        X_standardized = (X - train_mean) / std_safe

        # ---- Estágio 1a: Variance Threshold sobre features PADRONIZADAS ----
        # Corrige o viés de escala absoluta do v1 (ver docstring do módulo):
        # numa feature padronizada não-constante, variância ≈ 1 sempre; só
        # constantes verdadeiras ficam ≈0. O mesmo threshold (1e-5) agora
        # filtra "genuinamente constante", não "pequena em escala absoluta".
        vt        = VarianceThreshold(threshold=cfg.variance_threshold)
        vt.fit(X_standardized)
        vt_mask   = vt.get_support()  # shape (n_in,)
        n_after_vt = int(vt_mask.sum())

        # ---- Estágio 1b: Mutual Information top-k (sobre os sobreviventes do VT) ----
        # Sobre a escala ORIGINAL (não padronizada) — a padronização do
        # estágio 0 existe só para corrigir o VT; MI/mRMR/Boruta e a saída
        # final operam nos valores originais das features.
        X_vt      = X[:, vt_mask]
        k         = min(cfg.top_k_mi, X_vt.shape[1])
        mi_scores = mutual_info_classif(
            X_vt, y, random_state=cfg.random_state
        )
        # Indices dos top-k em X_vt
        topk_idx_in_vt = np.argsort(mi_scores)[::-1][:k]
        # Reconstruir máscara em X original
        stage1_mask = np.zeros(n_in, dtype=bool)
        vt_indices  = np.where(vt_mask)[0]
        stage1_mask[vt_indices[topk_idx_in_vt]] = True

        # ---- Estágio 2: mRMR ----
        X_s1            = X[:, stage1_mask]
        names_s1        = names[stage1_mask]
        n_mrmr          = min(cfg.n_features_mrmr, X_s1.shape[1])
        selected_names_mrmr = self._run_mrmr(X_s1, y, names_s1, n_mrmr)
        stage2_mask     = np.array(
            [n in set(selected_names_mrmr) for n in names], dtype=bool
        )

        # ---- Estágio 3: Boruta (diagnóstico de estabilidade, NÃO filtra o output) ----
        # Boruta aqui serve apenas para reportar quantas/quais features do mRMR
        # também se confirmam contra shadow features. O conjunto final usado
        # pelo classificador é sempre a saída do mRMR (stage2_mask); o Boruta
        # não remove nem adiciona features ao resultado.
        X_s2            = X[:, stage2_mask]
        names_s2        = names[stage2_mask]
        boruta_support  = self._run_boruta(X_s2, y)
        stage3_mask     = np.zeros(n_in, dtype=bool)
        s2_indices      = np.where(stage2_mask)[0]
        stage3_mask[s2_indices[boruta_support]] = True

        # Salvar
        self._feature_names_in = names
        self._stage1_mask      = stage1_mask
        self._stage2_mask      = stage2_mask
        self._stage3_mask      = stage3_mask
        self._final_mask       = stage2_mask
        self._final_indices    = np.where(stage2_mask)[0]

        n_mrmr_out = int(stage2_mask.sum())
        n_boruta_confirmed = int(stage3_mask.sum())
        self._stage_report.update({
            "stage1_input":   n_in,
            "stage0_zero_variance": n_zero_variance,
            "stage1_after_variance": n_after_vt,
            "stage1_output":  int(stage1_mask.sum()),
            "stage2_output":  n_mrmr_out,
            "stage3_boruta_confirmed": n_boruta_confirmed,
            "stage3_stability_ratio": (
                n_boruta_confirmed / n_mrmr_out if n_mrmr_out > 0 else 0.0
            ),
            "final_output":   int(self._final_mask.sum()),
            "stage1_top_k_mi": k,
            "stage2_n_mrmr":   n_mrmr,
        })

        self._fitted = True
        return self

    def transform(self, X: np.ndarray | pd.DataFrame) -> np.ndarray:
        """
        Aplica a máscara final (saída do mRMR, Estágio 2) ao X fornecido.

        Imputa NaN→0 como o `_prepare` do `fit` faz — sem isso, `fit` e
        `transform` tratavam NaN de forma diferente (achado na auditoria de
        2026-08-23). Hoje é latente (nenhuma das 641 features devolve NaN
        em CT real dos 6 algoritmos), mas as famílias NIST imputam p-value
        neutro por convenção e não por garantia: se alguma voltar a
        devolver NaN, o `StandardScaler` propaga e LinearSVC/LR/SVM
        levantam, derrubando metade do Caminho A no meio de uma rodada de
        horas.
        """
        self._check_fitted()
        Xa = X.values if isinstance(X, pd.DataFrame) else np.asarray(X)
        Xa = np.nan_to_num(np.asarray(Xa, dtype=np.float64),
                           nan=0.0, posinf=0.0, neginf=0.0)
        return Xa[:, self._final_mask]

    def fit_transform(
        self,
        X_train: np.ndarray | pd.DataFrame,
        y_train: np.ndarray | pd.Series,
        feature_names: Optional[list[str]] = None,
    ) -> np.ndarray:
        return self.fit(X_train, y_train, feature_names).transform(X_train)

    def get_selected_names(self) -> list[str]:
        """Nomes das features selecionadas após o pipeline."""
        self._check_fitted()
        return self._feature_names_in[self._final_mask].tolist()

    def get_stage_report(self) -> dict:
        """Resumo de quantas features sobreviveram a cada estágio."""
        self._check_fitted()
        return dict(self._stage_report)

    # ------------------------------------------------------------------
    # Privados
    # ------------------------------------------------------------------

    @staticmethod
    def _prepare(
        X: np.ndarray | pd.DataFrame,
        y: np.ndarray | pd.Series,
        feature_names: Optional[list[str]],
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        if isinstance(X, pd.DataFrame):
            names = np.asarray(list(X.columns))
            Xa = X.values
        else:
            Xa = np.asarray(X)
            if feature_names is not None:
                names = np.asarray(feature_names)
            else:
                names = np.asarray([f"f{i}" for i in range(Xa.shape[1])])

        if Xa.shape[1] != len(names):
            raise ValueError(
                f"X tem {Xa.shape[1]} colunas mas feature_names tem {len(names)}."
            )

        ya = np.asarray(y).ravel()
        if ya.shape[0] != Xa.shape[0]:
            raise ValueError(
                f"X.shape[0]={Xa.shape[0]} != y.shape[0]={ya.shape[0]}"
            )

        # NaN e ±inf -> 0 (features de autocorrelacao com CT curto retornam
        # NaN; tratar como "sem informacao"). Imputacao mais sofisticada e'
        # overkill aqui.
        #
        # **±inf incluído em 2026-08-24:** o `fit` imputava só NaN e o
        # `transform` já sanitizava NaN E inf — divergência da mesma classe
        # que a de NaN já corrigida antes. Com um inf na matriz, o `fit`
        # emitia RuntimeWarning e a feature era silenciosamente descartada
        # pelo VT, enquanto o `transform` a teria imputado como 0. Latente
        # hoje (0 inf medido em CT real), mas as duas metades precisam
        # concordar.
        Xa = np.nan_to_num(Xa.astype(np.float64), nan=0.0, posinf=0.0, neginf=0.0)

        return Xa, ya, names

    def _run_mrmr(
        self,
        X: np.ndarray,
        y: np.ndarray,
        names: np.ndarray,
        K: int,
    ) -> list[str]:
        from mrmr import mrmr_classif
        X_df = pd.DataFrame(X, columns=names.tolist())
        y_s  = pd.Series(y)
        return mrmr_classif(X=X_df, y=y_s, K=K, show_progress=False)

    def _run_boruta(self, X: np.ndarray, y: np.ndarray) -> np.ndarray:
        from boruta import BorutaPy
        cfg = self.config

        rf = RandomForestClassifier(
            n_jobs=-1,
            class_weight="balanced",
            max_depth=5,
            random_state=cfg.random_state,
        )
        bp = BorutaPy(
            rf,
            n_estimators=cfg.boruta_n_estimators,
            max_iter=cfg.boruta_max_iter,
            random_state=cfg.random_state,
            verbose=cfg.verbose,
        )
        # Boruta legacy chama np.random.RandomState.randint usando np.int — em
        # numpy 2.x essa chamada já foi corrigida na 0.4.x via shim. Caso falhe,
        # captura e retorna apenas suporte forte.
        bp.fit(X.astype(np.float32), y)
        return np.asarray(bp.support_, dtype=bool)

    def _check_fitted(self) -> None:
        if not self._fitted:
            raise RuntimeError("LWCFeatureSelector ainda nao foi ajustado (fit).")
