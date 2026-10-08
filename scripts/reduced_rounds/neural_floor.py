"""
Caminhos B, C, D e F, e as redes da literatura, para o estudo de piso.

Os modelos clássicos do Caminho A sobre bits crus não aprendem relações entre
os dois criptogramas de um par (uma regressão logística não representa um XOR,
e árvores precisariam achar a interação entre o bit i de um e o bit i do outro
no meio de centenas de bits). As redes desta família aprendem. Com elas, a
pergunta "com um modelo mais forte o piso subiria?" passa a ter resposta
medida, e não só argumento.

Tudo aqui tem interface do scikit-learn (`fit`, `predict_proba`), então entra no
`run_floor.py` pelo `--models` sem nada de especial: herda a mesma amostra, o
mesmo split por chave, a mesma CV, o relato por `report_eval` e o critério do
`report_floor.py`.

Modelos:

- `MLP_Shen`: rede densa sobre os bits. É o modelo do Shen et al. (JISA 2024),
  que alimenta uma MLP com a diferença C ⊕ C'.
- `ResNet_Gohr`: rede residual 1D no estilo de Gohr (CRYPTO 2019). A entrada é
  organizada por POSIÇÃO de byte: cada posição é um passo da sequência, e os
  canais são os 8 bits daquele byte em cada bloco do par. Com a representação
  `par`, o bit b do C1 e o bit b do C2 caem no mesmo passo, em canais
  vizinhos, e uma convolução de núcleo 1 consegue aprender o XOR dos dois.
- `CNN1D_bytes` (Caminho B): o `CiphertextCNN1D` do projeto, fiel ao original
  (embedding de byte e média global no fim), reduzido para sequências curtas.
  A média global descarta a posição, que é onde o sinal está; o resultado dele
  serve de contraste com as arquiteturas que preservam posição.
- `CNN2D_bits` (Caminho C, adaptado): a co-ocorrência 256 × 256 do Caminho C
  original fica vazia com 80 bytes (79 pares num mapa de 65.536 células). A
  adaptação usa a imagem de bits: linhas = os 8 bits de cada byte, um conjunto
  de linhas por bloco do par; colunas = posição de byte. Termina numa camada
  densa sobre o mapa achatado, e não em média global, para preservar posição.
  A "imagem" é artificial (a posição do bit no byte não é dimensão espacial), e
  isso precisa ser dito junto do resultado.
- `Hibrido_D` (Caminho D): os bits crus mais os vetores latentes da ResNet e da
  CNN 2D, numa regressão logística. Mesma ressalva do Caminho D do v1: os
  latentes do treino vêm de redes treinadas nesse mesmo treino.
- `Meta_F` (Caminho F): empilhamento. Regressão logística sobre as
  probabilidades fora do fold (CV interna de 3) de LR, XGBoost, RandomForest,
  MLP, ResNet e CNN 2D. A CV interna sorteia por amostra, sem saber a chave;
  as chaves de teste seguem fora, então isso não vaza para a avaliação.

O Caminho E (Transformer) foi decidido fora do estudo de piso em 02/10/2026.

Treino das redes: Adam, número fixo de épocas, sem early stopping. O `fit` do
scikit-learn não recebe a chave de cada amostra, então qualquer validação
interna seria sorteada por amostra e misturaria chaves; épocas fixas evitam
isso e mantêm o treino determinístico com a seed do modelo.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import torch
from sklearn.base import BaseEstimator, ClassifierMixin
from torch import nn

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.models.cnn1d import CiphertextCNN1D  # noqa: E402

ARQUITETURAS = ("MLP_Shen", "ResNet_Gohr", "CNN1D_bytes", "CNN2D_bits")
# GPU quando houver (Kaggle/Colab); em CPU nada muda. Os dados ficam na CPU e
# só cada lote vai para o dispositivo, para caber em memória de GPU pequena.
DISPOSITIVO = "cuda" if torch.cuda.is_available() else "cpu"
COMPOSTOS = ("Hibrido_D", "Meta_F")


class _MLP(nn.Module):
    def __init__(self, n_bits: int) -> None:
        super().__init__()
        self.corpo = nn.Sequential(
            nn.Linear(n_bits, 512), nn.BatchNorm1d(512), nn.ReLU(), nn.Dropout(0.2),
            nn.Linear(512, 256), nn.BatchNorm1d(256), nn.ReLU())
        self.saida = nn.Linear(256, 2)

    def latente(self, x: torch.Tensor) -> torch.Tensor:
        return self.corpo(x)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.saida(self.corpo(x))


class _BlocoResidual(nn.Module):
    def __init__(self, canais: int) -> None:
        super().__init__()
        self.c1 = nn.Conv1d(canais, canais, 3, padding=1)
        self.b1 = nn.BatchNorm1d(canais)
        self.c2 = nn.Conv1d(canais, canais, 3, padding=1)
        self.b2 = nn.BatchNorm1d(canais)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h = torch.relu(self.b1(self.c1(x)))
        h = torch.relu(self.b2(self.c2(h)))
        return x + h


class _ResNetGohr(nn.Module):
    """Entrada (batch, 8*blocos, posições). Núcleo 1 primeiro, como no Gohr:
    mistura os bits de mesma posição dos blocos antes de olhar vizinhança."""

    def __init__(self, canais_entrada: int, posicoes: int, canais: int = 32,
                 profundidade: int = 3) -> None:
        super().__init__()
        self.entrada = nn.Sequential(nn.Conv1d(canais_entrada, canais, 1),
                                     nn.BatchNorm1d(canais), nn.ReLU())
        self.blocos = nn.Sequential(*[_BlocoResidual(canais) for _ in range(profundidade)])
        self.corpo = nn.Sequential(
            nn.Flatten(), nn.Linear(canais * posicoes, 64), nn.BatchNorm1d(64), nn.ReLU(),
            nn.Linear(64, 64), nn.BatchNorm1d(64), nn.ReLU())
        self.saida = nn.Linear(64, 2)

    def latente(self, x: torch.Tensor) -> torch.Tensor:
        return self.corpo(self.blocos(self.entrada(x)))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.saida(self.latente(x))


class _CNN2DBits(nn.Module):
    """Entrada (batch, 1, 8*blocos, posições). Duas camadas convolucionais 3×3 e
    cabeça densa sobre o mapa achatado (preserva posição)."""

    def __init__(self, linhas: int, posicoes: int, canais: int = 16) -> None:
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(1, canais, 3, padding=1), nn.BatchNorm2d(canais), nn.ReLU(),
            nn.Conv2d(canais, canais, 3, padding=1), nn.BatchNorm2d(canais), nn.ReLU())
        self.corpo = nn.Sequential(
            nn.Flatten(), nn.Linear(canais * linhas * posicoes, 64), nn.BatchNorm1d(64), nn.ReLU())
        self.saida = nn.Linear(64, 2)

    def latente(self, x: torch.Tensor) -> torch.Tensor:
        return self.corpo(self.conv(x))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.saida(self.latente(x))


def _por_posicao(bits: np.ndarray, blocos: int) -> np.ndarray:
    """(n, blocos*L*8) bits → (n, 8*blocos, L): canais = bits de cada bloco
    naquela posição de byte. Os blocos ficam em sequência na amostra
    (C1, depois C2, depois o XOR, conforme a representação)."""
    n, nbits = bits.shape
    L = nbits // (8 * blocos)
    assert L * 8 * blocos == nbits, f"{nbits} bits não divide em {blocos} blocos de bytes"
    x = bits.reshape(n, blocos, L, 8)            # bloco, posição, bit
    return np.ascontiguousarray(x.transpose(0, 1, 3, 2).reshape(n, blocos * 8, L))


class NeuralBitClassifier(BaseEstimator, ClassifierMixin):
    """Classificador neural binário sobre bits, com interface do scikit-learn.

    Args:
        arquitetura: uma de `ARQUITETURAS`.
        blocos: quantos blocos de criptograma a amostra carrega (1 em `xor`,
            2 em `par`, 3 em `par+xor`). Define o alinhamento por posição.
        epocas, lote, lr: treino com Adam, épocas fixas.
        seed: semente do torch e do numpy (Regra de Ouro 1: modelo = 7).
    """

    def __init__(self, arquitetura: str = "MLP_Shen", blocos: int = 1, epocas: int = 15,
                 lote: int = 256, lr: float = 1e-3, seed: int = 7) -> None:
        self.arquitetura = arquitetura
        self.blocos = blocos
        self.epocas = epocas
        self.lote = lote
        self.lr = lr
        self.seed = seed

    def _entrada(self, X: np.ndarray) -> torch.Tensor:
        X = np.asarray(X)
        if self.arquitetura == "MLP_Shen":
            return torch.from_numpy(X.astype(np.float32))
        if self.arquitetura == "CNN1D_bytes":
            return torch.from_numpy(np.packbits(X.astype(np.uint8), axis=1).astype(np.int64))
        x = torch.from_numpy(_por_posicao(X.astype(np.float32), self.blocos))
        return x.unsqueeze(1) if self.arquitetura == "CNN2D_bits" else x

    def _construir(self, X: np.ndarray) -> nn.Module:
        nbits = X.shape[1]
        L = nbits // (8 * self.blocos)
        if self.arquitetura == "MLP_Shen":
            return _MLP(nbits)
        if self.arquitetura == "ResNet_Gohr":
            return _ResNetGohr(8 * self.blocos, L)
        if self.arquitetura == "CNN1D_bytes":
            return CiphertextCNN1D(n_classes=2, embed_dim=32, max_len=nbits // 8,
                                   n_filters=64, n_conv_blocks=3, dropout=0.3)
        if self.arquitetura == "CNN2D_bits":
            return _CNN2DBits(8 * self.blocos, L)
        raise ValueError(f"arquitetura desconhecida: {self.arquitetura!r}")

    def fit(self, X, y):
        torch.manual_seed(self.seed)
        np.random.seed(self.seed)
        self.classes_ = np.array([0, 1])
        self.rede_ = self._construir(np.asarray(X)).to(DISPOSITIVO)
        xt = self._entrada(X)
        yt = torch.from_numpy(np.asarray(y).astype(np.int64))
        otim = torch.optim.Adam(self.rede_.parameters(), lr=self.lr, weight_decay=1e-5)
        perda = nn.CrossEntropyLoss()
        gerador = torch.Generator().manual_seed(self.seed)
        self.rede_.train()
        for _ in range(self.epocas):
            ordem = torch.randperm(len(yt), generator=gerador)
            for i in range(0, len(yt), self.lote):
                idx = ordem[i:i + self.lote]
                if len(idx) < 2:          # BatchNorm não aceita lote de 1
                    continue
                otim.zero_grad()
                perda(self.rede_(xt[idx].to(DISPOSITIVO)), yt[idx].to(DISPOSITIVO)).backward()
                otim.step()
        return self

    @torch.no_grad()
    def predict_proba(self, X) -> np.ndarray:
        self.rede_.eval()
        xt = self._entrada(X)
        saidas = [torch.softmax(self.rede_(xt[i:i + 2048].to(DISPOSITIVO)), dim=1).cpu()
                  for i in range(0, len(xt), 2048)]
        return torch.cat(saidas).numpy()

    @torch.no_grad()
    def latente(self, X) -> np.ndarray:
        """Vetor antes da camada de saída (Caminho D). Só MLP, ResNet e CNN 2D."""
        if not hasattr(self.rede_, "latente"):
            raise ValueError(f"{self.arquitetura} não expõe latente")
        self.rede_.eval()
        xt = self._entrada(X)
        return torch.cat([self.rede_.latente(xt[i:i + 2048].to(DISPOSITIVO)).cpu()
                          for i in range(0, len(xt), 2048)]).numpy()

    def predict(self, X) -> np.ndarray:
        return self.predict_proba(X).argmax(axis=1)


class HibridoD(BaseEstimator, ClassifierMixin):
    """Caminho D: bits crus + latente da ResNet + latente da CNN 2D → LR."""

    def __init__(self, blocos: int = 1, epocas: int = 15, seed: int = 7) -> None:
        self.blocos = blocos
        self.epocas = epocas
        self.seed = seed

    def _z(self, X) -> np.ndarray:
        X = np.asarray(X, dtype=np.float32)
        return np.hstack([X, self.resnet_.latente(X), self.cnn2d_.latente(X)])

    def fit(self, X, y):
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import StandardScaler

        self.classes_ = np.array([0, 1])
        self.resnet_ = NeuralBitClassifier("ResNet_Gohr", self.blocos, self.epocas, seed=self.seed).fit(X, y)
        self.cnn2d_ = NeuralBitClassifier("CNN2D_bits", self.blocos, self.epocas, seed=self.seed).fit(X, y)
        self.lr_ = Pipeline([("s", StandardScaler()),
                             ("c", LogisticRegression(max_iter=2000, random_state=self.seed))])
        self.lr_.fit(self._z(X), y)
        return self

    def predict_proba(self, X) -> np.ndarray:
        return self.lr_.predict_proba(self._z(X))

    def predict(self, X) -> np.ndarray:
        return self.predict_proba(X).argmax(axis=1)


def _meta_f(seed: int, blocos: int, epocas: int):
    """Caminho F: empilhamento sobre probabilidades fora do fold."""
    from sklearn.ensemble import StackingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    from scripts.run_v2_caminho_a import build_models

    cls = build_models(seed=seed)
    base = [
        ("lr", Pipeline([("s", StandardScaler()), ("c", cls["LogisticRegression"])])),
        ("xgb", cls["XGBoost"]),
        ("rf", cls["RandomForest"]),
        ("mlp", NeuralBitClassifier("MLP_Shen", blocos, epocas, seed=seed)),
        ("resnet", NeuralBitClassifier("ResNet_Gohr", blocos, epocas, seed=seed)),
        ("cnn2d", NeuralBitClassifier("CNN2D_bits", blocos, epocas, seed=seed)),
    ]
    return StackingClassifier(estimators=base,
                              final_estimator=LogisticRegression(max_iter=2000, random_state=seed),
                              cv=3, stack_method="predict_proba", n_jobs=1)


def build_neural_models(seed: int, blocos: int, epocas: int = 15) -> dict:
    """Redes e caminhos compostos, prontos para entrar no `run_floor.py`."""
    modelos = {nome: NeuralBitClassifier(arquitetura=nome, blocos=blocos, epocas=epocas, seed=seed)
               for nome in ARQUITETURAS}
    modelos["Hibrido_D"] = HibridoD(blocos=blocos, epocas=epocas, seed=seed)
    modelos["Meta_F"] = _meta_f(seed, blocos, epocas)
    return modelos
