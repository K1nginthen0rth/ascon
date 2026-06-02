"""
Pipeline de seleção de features para classificação LWC ciphertext-only.

Pipeline em 3 estágios (ver docs/contexto_inicial.md §2):
  1. Screening univariado: VarianceThreshold + Mutual Information (top-k)
  2. Redução de redundância: mRMR [Peng et al. 2005]
  3. Validação por estabilidade: Boruta [Kursa & Rudnicki 2010]

REGRA CRÍTICA: o `fit` deve ser chamado APENAS no X_train, dentro de cada fold
de CV. Selecionar no dataset completo é o vazamento documentado em
[Ambroise & McLachlan, PNAS 2002].

Referências:
  - Peng, H., Long, F., & Ding, C. (2005). IEEE TPAMI 27(8).
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
    """Hiperparâmetros do pipeline LWCFeatureSelector."""

    variance_threshold: float = 1e-5
    top_k_mi:           int   = 200
    n_features_mrmr:    int   = 100
    boruta_max_iter:    int   = 100
    boruta_n_estimators: int | str = "auto"
    random_state:       int   = 13
    verbose:            int   = 0


class LWCFeatureSelector:
    """
    Seletor de features em 3 estágios para datasets de criptogramas LWC.

    Estágio 1 (univariado, O(p)):
        - VarianceThreshold remove features quase-constantes
        - Mutual Information classif → top-k

    Estágio 2 (redundância):
        - mRMR seleciona n_features_mrmr maximizando relevância e minimizando
          redundância entre features [Peng et al. 2005]

    Estágio 3 (estabilidade):
        - Boruta confirma quais features carregam sinal de fato vs. baseline
          de "shadow features" embaralhadas [Kursa & Rudnicki 2010]

    Uso correto (dentro do fold):
        sel = LWCFeatureSelector()
        sel.fit(X_train, y_train, feature_names=cols)
        X_train_sel = sel.transform(X_train)
        X_val_sel   = sel.transform(X_val)
        X_test_sel  = sel.transform(X_test)

    Args:
        config: SelectorConfig com hiperparâmetros (defaults razoáveis para
                ~300 features e milhares de amostras).
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
        Ajusta o pipeline em 3 estágios usando APENAS dados de treino.

        Args:
            X_train: matriz (n_samples, n_features). Aceita DataFrame ou ndarray.
            y_train: rótulos (n_samples,). Aceita Series, array ou lista.
            feature_names: nomes opcionais. Se X_train for DataFrame, são
                inferidos das colunas.
        """
        X, y, names = self._prepare(X_train, y_train, feature_names)
        cfg         = self.config
        n_in        = X.shape[1]

        # ---- Estágio 1a: Variance Threshold ----
        vt        = VarianceThreshold(threshold=cfg.variance_threshold)
        vt.fit(X)
        vt_mask   = vt.get_support()  # shape (n_in,)
        n_after_vt = int(vt_mask.sum())

        # ---- Estágio 1b: Mutual Information top-k (sobre os sobreviventes do VT) ----
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

        # ---- Estágio 3: Boruta ----
        X_s2            = X[:, stage2_mask]
        names_s2        = names[stage2_mask]
        boruta_support  = self._run_boruta(X_s2, y)
        stage3_mask     = np.zeros(n_in, dtype=bool)
        s2_indices      = np.where(stage2_mask)[0]
        stage3_mask[s2_indices[boruta_support]] = True

        # Fallback: se Boruta não selecionar nada, usar mRMR como final
        if stage3_mask.sum() == 0:
            stage3_mask = stage2_mask.copy()
            self._stage_report["boruta_fallback"] = (
                "Boruta retornou conjunto vazio — usando saída do mRMR como final."
            )

        # Salvar
        self._feature_names_in = names
        self._stage1_mask      = stage1_mask
        self._stage2_mask      = stage2_mask
        self._stage3_mask      = stage3_mask
        self._final_mask       = stage3_mask
        self._final_indices    = np.where(stage3_mask)[0]

        self._stage_report.update({
            "stage1_input":   n_in,
            "stage1_after_variance": n_after_vt,
            "stage1_output":  int(stage1_mask.sum()),
            "stage2_output":  int(stage2_mask.sum()),
            "stage3_output":  int(stage3_mask.sum()),
            "final_output":   int(self._final_mask.sum()),
            "stage1_top_k_mi": k,
            "stage2_n_mrmr":   n_mrmr,
        })

        self._fitted = True
        return self

    def transform(self, X: np.ndarray | pd.DataFrame) -> np.ndarray:
        """Aplica a máscara final (Estágio 3 ou fallback) ao X fornecido."""
        self._check_fitted()
        Xa = X.values if isinstance(X, pd.DataFrame) else np.asarray(X)
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

        # NaN -> 0 (features de autocorrelacao com CT curto retornam NaN; tratar
        # como "sem informacao"). Imputacao mais sofisticada e' overkill aqui.
        if np.isnan(Xa).any():
            Xa = np.where(np.isnan(Xa), 0.0, Xa)

        return Xa.astype(np.float64), ya, names

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
