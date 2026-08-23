"""
Transformer hierárquico sobre bytes crus — Caminho E do experimento v2.

**Contribuição própria, NÃO réplica do E20** (enquadramento corrigido na
revisão crítica do plano; ver docs/plano_experimento_v2/03_classificadores.md
§3.5): o E20 (Yuan et al., 2026) aplica um Transformer sobre ~8 features NIST
pré-filtradas, com hierarquia de RÓTULOS (classifica a família construtiva e
depois o algoritmo). Aqui a hierarquia é de ATENÇÃO, e a entrada são os bytes
crus — nenhum estudo da RSL testa atenção direto sobre bytes de criptograma.
A réplica fiel do E20 vive no Caminho A, separada.

Arquitetura:
    bytes (N,)                            # N = 65.536 efetivos
      -> Embedding(256, d_model)
      -> patch embedding: Conv1d(k=P, stride=P)    -> (N/P, d_model)
      -> reshape em J janelas de T tokens          # T = window/P, J = N/window
      -> + posicional dentro da janela
      -> encoder LOCAL (n_local camadas) por janela
      -> pooling por janela                        -> (J, d_model)
      -> + posicional de janela
      -> encoder GLOBAL (n_global camadas) sobre J tokens
      -> pooling global -> `extract_latent()`      -> (d_model,)
      -> cabeça linear -> n_classes

**Por que patch embedding (decisão de projeto, não detalhe):** o plano
descrevia "janelas de ~1024 bytes + atenção global". Atenção com UM TOKEN
POR BYTE é inviável nessa escala — medido: com janela de 1024 bytes e
batch 2, a matriz de atenção sozinha pede 2,1 GB em CPU
(`B*J x heads x W² x 4B`), e em GPU com batch 8 passaria de 8 GB, antes de
qualquer gradiente. O patch embedding (padrão em ViT/áudio) agrega P bytes
por token via convolução aprendida: com P=16 e janela de 1024, cada janela
vira 64 tokens em vez de 1024, e a atenção cai por um fator de P²=256.
A hierarquia (local dentro da janela, global entre janelas) — que é a
contribuição de fato — fica intacta.

Hipótese que o desenho testa: uma assinatura de algoritmo, se existir,
aparece OU dentro de uma janela curta (padrão local da permutação/rodada)
OU na relação entre janelas (deriva posicional). Os dois níveis ficam
cobertos.

`extract_latent()` é obrigatório: o Caminho D concatena esse latente com as
representações dos Caminhos A/B/C.
"""
from __future__ import annotations

import torch
import torch.nn as nn


class HierarchicalByteTransformer(nn.Module):
    """
    Transformer hierárquico (janela local + global) sobre bytes de CT.

    Args:
        n_classes:  número de classes de saída.
        max_len:    comprimento da sequência de bytes consumida (pad/truncate).
                    Default 65.536 (o payload; ver nota sobre a tag abaixo).
        window:     bytes por janela local (default 1.024).
        patch:      bytes agregados por token (default 16) — ver docstring
                    do módulo para o motivo.
        d_model:    dimensão do modelo.
        n_heads:    cabeças de atenção.
        n_local:    camadas do encoder local (dentro da janela).
        n_global:   camadas do encoder global (entre janelas).
        dim_ff:     dimensão da feed-forward dos encoders.
        dropout:    dropout dos encoders e da cabeça.

    Notes:
        `max_len` é truncado para o múltiplo inferior de `window`, e
        `window` para o múltiplo inferior de `patch`. Com os defaults,
        65.536 = 64 janelas x 1.024 bytes = 64 janelas x 64 tokens.
        Os bytes finais de tag (8 no braço controlado) ficam FORA deste
        caminho por não completarem uma janela — a informação de tag é
        coberta pelas features `tag_region` do Caminho A, não aqui.
        Registrado em `self.effective_len` e reportado no manifesto do
        experimento para não virar diferença silenciosa entre caminhos.
    """

    def __init__(
        self,
        n_classes: int = 4,
        max_len: int = 65536,
        window: int = 1024,
        patch: int = 16,
        d_model: int = 64,
        n_heads: int = 4,
        n_local: int = 2,
        n_global: int = 2,
        dim_ff: int = 128,
        dropout: float = 0.1,
    ) -> None:
        super().__init__()
        if d_model % n_heads != 0:
            raise ValueError(f"d_model ({d_model}) deve ser divisível por n_heads ({n_heads})")
        if window % patch != 0:
            raise ValueError(f"window ({window}) deve ser divisível por patch ({patch})")
        if max_len < window:
            raise ValueError(f"max_len ({max_len}) menor que window ({window})")

        self.max_len = max_len
        self.window = window
        self.patch = patch
        self.n_windows = max_len // window
        self.effective_len = self.n_windows * window
        self.tokens_per_window = window // patch
        self.d_model = d_model

        self.embedding = nn.Embedding(num_embeddings=256, embedding_dim=d_model)
        # Patch embedding: agrega `patch` bytes num token (conv aprendida,
        # stride = kernel, sem sobreposição).
        self.patch_embed = nn.Conv1d(
            in_channels=d_model, out_channels=d_model,
            kernel_size=patch, stride=patch,
        )

        # Posicional aprendido DENTRO da janela (compartilhado entre janelas —
        # o que importa localmente é a posição relativa) e ENTRE janelas
        # (posição absoluta grosseira no criptograma).
        self.pos_local = nn.Parameter(torch.zeros(1, self.tokens_per_window, d_model))
        self.pos_global = nn.Parameter(torch.zeros(1, self.n_windows, d_model))
        nn.init.trunc_normal_(self.pos_local, std=0.02)
        nn.init.trunc_normal_(self.pos_global, std=0.02)

        local_layer = nn.TransformerEncoderLayer(
            d_model=d_model, nhead=n_heads, dim_feedforward=dim_ff,
            dropout=dropout, batch_first=True, norm_first=True,
        )
        self.local_encoder = nn.TransformerEncoder(local_layer, num_layers=n_local)

        global_layer = nn.TransformerEncoderLayer(
            d_model=d_model, nhead=n_heads, dim_feedforward=dim_ff,
            dropout=dropout, batch_first=True, norm_first=True,
        )
        self.global_encoder = nn.TransformerEncoder(global_layer, num_layers=n_global)

        self.norm = nn.LayerNorm(d_model)
        self.dropout = nn.Dropout(dropout)
        self.fc = nn.Linear(d_model, n_classes)

    # ------------------------------------------------------------------

    def _prepare(self, x: torch.Tensor) -> torch.Tensor:
        """Trunca/pad para `effective_len` e garante dtype long."""
        if x.dtype != torch.long:
            x = x.long()
        n = x.shape[1]
        if n > self.effective_len:
            x = x[:, : self.effective_len]
        elif n < self.effective_len:
            x = torch.nn.functional.pad(x, (0, self.effective_len - n), value=0)
        return x

    def extract_latent(self, x: torch.Tensor) -> torch.Tensor:
        """
        Vetor latente (antes da cabeça de classificação), dimensão
        `d_model`. Obrigatório para o Caminho D (híbrido).

        Args:
            x: (batch, seq_len) de inteiros 0-255.

        Returns:
            (batch, d_model)
        """
        x = self._prepare(x)
        batch = x.shape[0]

        emb = self.embedding(x)                       # (B, N, d)
        emb = self.patch_embed(emb.transpose(1, 2))   # (B, d, N/P)
        tokens = emb.transpose(1, 2)                  # (B, N/P, d)

        # (B, J*T, d) -> (B*J, T, d): cada janela vira um item do batch, então
        # a atenção local NUNCA cruza janelas.
        tokens = tokens.reshape(batch * self.n_windows, self.tokens_per_window, self.d_model)
        tokens = tokens + self.pos_local

        local_out = self.local_encoder(tokens)                    # (B*J, T, d)
        window_repr = local_out.mean(dim=1)                       # (B*J, d)
        window_repr = window_repr.view(batch, self.n_windows, self.d_model)

        window_repr = window_repr + self.pos_global
        global_out = self.global_encoder(window_repr)             # (B, J, d)
        latent = global_out.mean(dim=1)                           # (B, d)
        return self.norm(latent)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        latent = self.extract_latent(x)
        return self.fc(self.dropout(latent))

    # ------------------------------------------------------------------

    def count_parameters(self, trainable_only: bool = True) -> int:
        """Contagem de parâmetros — exigida no relatório de cada
        arquitetura (Fases 7/8 do plano)."""
        params = self.parameters()
        if trainable_only:
            params = (p for p in params if p.requires_grad)
        return sum(p.numel() for p in params)
