"""
Redes no protocolo pré-registrado (plano v3, "Pré-registro do método de ML").

Treino comum: Adam, taxa 10⁻³ com agenda cosseno, weight decay 10⁻⁵, parada
antecipada pela AUC numa validação separada POR CHAVE/DISPOSITIVO (paciência 5),
o melhor estado é o usado no teste, e o teste é avaliado uma vez.

Modos:
  piso      Para cada algoritmo: seleção da ResNet (profundidade {3,6,10} x
            canais {32,64}) pela AUC de validação na célula piso+1 / texto-en;
            a escolhida, e uma MLP fixa, são avaliadas nas 6 células (piso,
            piso+1, especificação; texto-en e aleatório) com o split do
            run_floor (240 chaves de treino, das quais 40 de validação; 60 de
            teste), e relatadas por report_eval (bolsas 1, 10, 100) para o
            report_floor.py decidir o piso.
  gift4     GIFT-COFB rodada 4 com 10⁷ pares por classe: classe 1 = XOR do
            braço texto-en, classe 0 = XOR do braço aleatório (uniforme por
            construção, mesmos dispositivos e mesma cifra). Controle: aleatório
            (metade A) contra aleatório (metade B). Modelos: ResNet profundidade
            10 x 32 canais (perto do Gohr), MLP, e regressão logística sobre os
            128 bits do bloco e as 8 128 paridades de dois bits.
  plantado  Teste de capacidade: bits uniformes; na classe 1 a paridade dos
            bits 16 e 64 vale 0 com probabilidade 0,502 (viés de 0,2%, como o
            GIFT r4). Treino com 10⁶, 3·10⁶ e 10⁷ por classe.

Toda métrica sai numa linha "RESULTADO {json}" assim que calculada (o Kaggle
nem sempre salva a saída).

Uso:
    python metodo_redes.py piso --algo gift --dados <pasta com <algo>_floor/>
    python metodo_redes.py gift4 --brutos <pasta com gift_r4_*_10M.npz>
    python metodo_redes.py plantado
    (--smoke reduz tudo para testar localmente em CPU)
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src" / "crypto"))

import numpy as np  # noqa: E402
import torch  # noqa: E402
from torch import nn  # noqa: E402

DISP = "cuda" if torch.cuda.is_available() else "cpu"
SEED = 7
CELULAS = {"ascon": (3, 4, 12), "gift": (3, 4, 40), "grain": (28, 29, 256), "schwaemm": (2, 3, 11)}


def _log(m: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def resultado(**d) -> None:
    print("RESULTADO " + json.dumps(d, default=float), flush=True)


# ------------------------------------------------------------------ modelos

class Bloco(nn.Module):
    def __init__(self, c: int) -> None:
        super().__init__()
        self.f = nn.Sequential(nn.Conv1d(c, c, 3, padding=1), nn.BatchNorm1d(c), nn.ReLU(),
                               nn.Conv1d(c, c, 3, padding=1), nn.BatchNorm1d(c), nn.ReLU())

    def forward(self, x):
        return x + self.f(x)


class ResNet(nn.Module):
    """Bits como 8 canais (bit do byte) x posições (byte), como no Gohr."""

    def __init__(self, n_bytes: int, prof: int, canais: int) -> None:
        super().__init__()
        self.n = n_bytes
        self.ent = nn.Sequential(nn.Conv1d(8, canais, 1), nn.BatchNorm1d(canais), nn.ReLU())
        self.blocos = nn.Sequential(*[Bloco(canais) for _ in range(prof)])
        self.cab = nn.Sequential(nn.Flatten(), nn.Linear(canais * n_bytes, 64), nn.BatchNorm1d(64), nn.ReLU(),
                                 nn.Linear(64, 64), nn.BatchNorm1d(64), nn.ReLU(), nn.Linear(64, 2))

    def forward(self, bits):                      # bits: (B, 8*n) em float
        x = bits.view(-1, self.n, 8).transpose(1, 2)
        return self.cab(self.blocos(self.ent(x)))


class MLP(nn.Module):
    def __init__(self, n_bits: int) -> None:
        super().__init__()
        self.f = nn.Sequential(nn.Linear(n_bits, 512), nn.BatchNorm1d(512), nn.ReLU(), nn.Dropout(0.2),
                               nn.Linear(512, 256), nn.BatchNorm1d(256), nn.ReLU(), nn.Linear(256, 2))

    def forward(self, bits):
        return self.f(bits)


class LogParidades(nn.Module):
    """Regressão logística sobre os 128 bits do bloco e as 8 128 paridades."""

    def __init__(self) -> None:
        super().__init__()
        i, j = torch.triu_indices(128, 128, 1)
        self.register_buffer("i", i)
        self.register_buffer("j", j)
        self.lin = nn.Linear(128 + len(i), 2)

    def forward(self, bits):
        b = bits[:, :128]
        par = (b[:, self.i] + b[:, self.j]) % 2
        return self.lin(torch.cat([b, par], 1) * 2 - 1)


def construir(nome: str, n_bytes: int):
    if nome.startswith("ResNet"):
        _, p, c = nome.split("_")                 # ResNet_p<prof>_c<canais>
        return ResNet(n_bytes, int(p[1:]), int(c[1:]))
    if nome == "MLP":
        return MLP(8 * n_bytes)
    return LogParidades()


# ------------------------------------------------------------------ treino

def _bits(x_u8: np.ndarray) -> torch.Tensor:
    return torch.from_numpy(np.unpackbits(x_u8, axis=1).astype(np.float32))


@torch.no_grad()
def escores(rede, X: np.ndarray, lote: int = 8192) -> np.ndarray:
    rede.eval()
    out = []
    for i in range(0, len(X), lote):
        z = rede(_bits(X[i:i + lote]).to(DISP))
        out.append((z[:, 1] - z[:, 0]).float().cpu().numpy())
    return np.concatenate(out)


def auc(s1: np.ndarray, s0: np.ndarray) -> tuple[float, float]:
    """AUC (Mann-Whitney) e z sob H0 (AUC = 1/2)."""
    from scipy.stats import rankdata
    r = rankdata(np.concatenate([s0, s1]))
    n0, n1 = len(s0), len(s1)
    a = (r[n0:].sum() - n1 * (n1 + 1) / 2) / (n0 * n1)
    return float(a), float((a - 0.5) / math.sqrt((n0 + n1 + 1) / (12 * n0 * n1)))


def treinar(nome: str, n_bytes: int, X1, X0, V1, V0, epocas: int, lote: int, tag: str):
    """X1/X0: classe 1 e 0 de treino (uint8); V1/V0: validação. Devolve a rede
    no melhor estado (AUC de validação) e o histórico."""
    torch.manual_seed(SEED)
    rede = construir(nome, n_bytes).to(DISP)
    otim = torch.optim.Adam(rede.parameters(), lr=1e-3, weight_decay=1e-5)
    passos = epocas * math.ceil((len(X1) + len(X0)) / lote)
    agenda = torch.optim.lr_scheduler.CosineAnnealingLR(otim, T_max=passos)
    perda = nn.CrossEntropyLoss()
    X = np.concatenate([X1, X0])
    y = torch.from_numpy(np.r_[np.ones(len(X1)), np.zeros(len(X0))].astype(np.int64))
    g = torch.Generator().manual_seed(SEED)
    melhor, estado, sem_melhora, hist = -1.0, None, 0, []
    for ep in range(epocas):
        rede.train()
        ordem = torch.randperm(len(y), generator=g).numpy()
        soma, n, t0 = 0.0, 0, time.time()
        for k in range(0, len(ordem), lote):
            sel = ordem[k:k + lote]
            if len(sel) < 2:
                continue
            xb = _bits(X[sel]).to(DISP, non_blocking=True)
            otim.zero_grad()
            l = perda(rede(xb), y[sel].to(DISP))
            l.backward()
            otim.step()
            agenda.step()
            soma += float(l) * len(sel)
            n += len(sel)
        a, z = auc(escores(rede, V1), escores(rede, V0))
        hist.append(dict(epoca=ep + 1, perda=soma / n, auc_val=a, z_val=z))
        _log(f"  {tag} {nome} época {ep + 1}: perda {soma / n:.5f} AUC val {a:.4f} (z {z:.1f}) {time.time() - t0:.0f}s")
        if a > melhor:
            melhor, sem_melhora = a, 0
            estado = {k: v.detach().clone() for k, v in rede.state_dict().items()}
        else:
            sem_melhora += 1
            if sem_melhora >= 5:
                break
    rede.load_state_dict(estado)
    return rede, melhor, hist


# ------------------------------------------------------------------ modo piso

def _celula(dados: Path, algo: str, arm: str, r: int):
    z = np.load(dados / f"{algo}_floor" / f"{algo}_{arm}_k300.npz")
    pos, neg, kidx = z[f"r{r}"], z["random"], z["key_idx"]
    keys = np.arange(300)
    np.random.default_rng(42).shuffle(keys)           # SEED_SPLIT do run_floor
    teste, val = keys[:60], keys[60:100]
    te, va = np.isin(kidx, teste), np.isin(kidx, val)
    tr = ~te & ~va
    return pos, neg, kidx, tr, va, te


def modo_piso(algo: str, dados: Path, saida: Path, smoke: bool) -> None:
    # No Kaggle não há os .pyd das cifras nem o nistrng, que o run_gift_floor
    # importa no carregamento: os mesmos substitutos do kaggle_piso.py.
    from scripts.reduced_rounds.kaggle_piso import preparar_ambiente
    preparar_ambiente(False)
    from scripts.reduced_rounds.floor_algos import ALGOS
    from scripts.reduced_rounds.run_gift_floor import _bags
    from src.eval.reporting import report_eval

    spec = ALGOS[algo]
    epocas, lote = (2, 512) if smoke else (50, 256)
    grade = ["ResNet_p3_c32"] if smoke else [f"ResNet_p{p}_c{c}" for p in (3, 6, 10) for c in (32, 64)]
    pos, neg, kidx, tr, va, te = _celula(dados, algo, "texto-en", CELULAS[algo][1])
    n_bytes = pos.shape[1]
    sel = {}
    for nome in grade:
        _, a, hist = treinar(nome, n_bytes, pos[tr], neg[tr], pos[va], neg[va], epocas, lote, f"{algo} seleção")
        sel[nome] = a
        resultado(modo="piso-selecao", algo=algo, modelo=nome, auc_val=a, epocas=len(hist))
    escolhida = max(sel, key=sel.get)
    _log(f"{algo}: ResNet escolhida {escolhida} (AUC val {sel[escolhida]:.4f}; faixa {min(sel.values()):.4f} a {max(sel.values()):.4f})")
    rep = saida / f"{algo}_floor" / "reports"
    rep.mkdir(parents=True, exist_ok=True)
    for nome in (escolhida, "MLP"):
        for arm in ("texto-en", "aleatorio"):
            for r in CELULAS[algo]:
                pos, neg, kidx, tr, va, te = _celula(dados, algo, arm, r)
                rede, a_val, hist = treinar(nome, n_bytes, pos[tr], neg[tr], pos[va], neg[va], epocas, lote,
                                            f"{algo} {arm} r{r}")
                s1, s0 = escores(rede, pos[te]), escores(rede, neg[te])
                p1 = 1 / (1 + np.exp(-np.r_[s0, s1]))
                proba = np.column_stack([1 - p1, p1])
                y = np.r_[np.zeros(len(s0), int), np.ones(len(s1), int)]
                k = np.r_[kidx[te], kidx[te]]
                kid = np.array([f"k{x:04d}" for x in k])
                classes = ["aleatório uniforme", f"{spec.rotulo} {r}"]
                rotulo = "ResNet_ajustada" if nome.startswith("ResNet") else "MLP_ajustada"
                extra = dict(algo=algo, rounds=r, rounds_spec=spec.max_rounds, unidade=spec.unidade,
                             politica="ambos", arm=arm, runner="metodo_redes", seed_gen_runner=999004,
                             contador="zero", representacao="xor", config=nome, epocas=len(hist),
                             auc_val=a_val)
                for bag in (1, 10, 100):
                    by, bp, bk = _bags(proba, y, kid, bag) if bag > 1 else (y, proba, kid)
                    m = report_eval(run_id=f"floor_{algo}_{arm}_r{r}", caminho="A",
                                    modelo=f"{rotulo}_bag{bag}" if bag > 1 else rotulo,
                                    braco=f"floor_{algo}_{arm}", fold="final", y_true=by,
                                    y_pred=bp.argmax(1), y_proba=bp,
                                    sample_ids=[f"{a}_{b}_{i}" for i, (a, b) in enumerate(zip(bk, by))],
                                    key_ids=list(bk), class_names=classes, labels=[0, 1], out_dir=rep,
                                    seed=42, extra={**extra, "pares_por_decisao": bag})
                    d = m.as_dict()
                    resultado(modo="piso", algo=algo, arm=arm, rodadas=r, modelo=rotulo, config=nome, bolsa=bag,
                              f1=d.get("f1_macro"), f1_lo=d.get("f1_macro_ci_lower"),
                              f1_hi=d.get("f1_macro_ci_upper"))


# ------------------------------------------------------------------ gift4 e plantado

def _split_disp(disp: np.ndarray, frac_te=0.1, frac_va=0.05):
    u = np.unique(disp)
    rng = np.random.default_rng(42)
    rng.shuffle(u)
    nte, nva = int(len(u) * frac_te), int(len(u) * frac_va)
    return np.isin(disp, u[:nte]), np.isin(disp, u[nte:nte + nva])


def _avaliar_par(tag, nome, n_bytes, A1, A0, epocas, lote, disp1, disp0, frac_te=0.1, frac_va=0.05):
    te1, va1 = _split_disp(disp1, frac_te, frac_va)
    te0, va0 = _split_disp(disp0, frac_te, frac_va)
    tr1, tr0 = ~te1 & ~va1, ~te0 & ~va0
    rede, a_val, hist = treinar(nome, n_bytes, A1[tr1], A0[tr0], A1[va1], A0[va0], epocas, lote, tag)
    s1, s0 = escores(rede, A1[te1]), escores(rede, A0[te0])
    a, z = auc(s1, s0)
    # decisão por dispositivo: média do escore dos pares do dispositivo
    def por_disp(s, d):
        u, inv = np.unique(d, return_inverse=True)
        return np.bincount(inv, weights=s) / np.bincount(inv)
    ad, zd = auc(por_disp(s1, disp1[te1]), por_disp(s0, disp0[te0]))
    resultado(modo=tag, modelo=nome, n_treino=int(tr1.sum()), n_teste=int(te1.sum()), auc=a, z=z,
              auc_disp=ad, z_disp=zd, auc_val=a_val, epocas=len(hist))
    _log(f"{tag} {nome}: AUC teste {a:.4f} (z {z:.1f}); por dispositivo {ad:.4f} (z {zd:.1f})")


def modo_gift4(brutos: Path, smoke: bool) -> None:
    t = np.load(brutos / "gift_r4_texto-en_10M.npz")
    a = np.load(brutos / "gift_r4_aleatorio_10M.npz")
    X1, d1, X0, d0 = t["x"], t["disp"], a["x"], a["disp"]
    if smoke:
        X1, d1, X0, d0 = X1[:200_000], d1[:200_000], X0[:200_000], d0[:200_000]
    ep, lote = (2, 2048) if smoke else (10, 2048)
    meio = len(X0) // 2
    for nome in ("LogParidades", "MLP", "ResNet_p10_c32"):
        _avaliar_par("gift4", nome, 80, X1, X0, ep, lote, d1, d0)
        # controle: aleatório contra aleatório (metades com dispositivos distintos)
        _avaliar_par("gift4-controle", nome, 80, X0[:meio], X0[meio:], ep, lote, d0[:meio], d0[meio:] + 10**7)


def modo_plantado(smoke: bool) -> None:
    rng = np.random.default_rng(2026)
    tamanhos = (20_000,) if smoke else (1_000_000, 3_000_000, 10_000_000)
    n_te = 20_000 if smoke else 2_000_000
    for n in tamanhos:
        tot = n + n_te + n // 20
        X0 = rng.integers(0, 256, (tot, 80), dtype=np.uint8)
        X1 = rng.integers(0, 256, (tot, 80), dtype=np.uint8)
        # bits 16 (byte 2, MSB) e 64 (byte 8, MSB): paridade 0 com prob. 0,502
        b16 = (X1[:, 2] >> 7) & 1
        alvo = np.where(rng.random(tot) < 0.502, b16, 1 - b16).astype(np.uint8)
        X1[:, 8] = (X1[:, 8] & 0x7F) | (alvo << 7)
        disp = np.arange(tot) // 100                  # dispositivos de 100 pares
        for nome in ("LogParidades", "ResNet_p10_c32"):
            _avaliar_par(f"plantado-{n}", nome, 80, X1, X0, 2 if smoke else 10, 2048, disp, disp + 10**8,
                         frac_te=n_te / tot, frac_va=(n // 20) / tot)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("modo", choices=["piso", "gift4", "plantado"])
    ap.add_argument("--algo", choices=sorted(CELULAS))
    ap.add_argument("--dados", type=Path)
    ap.add_argument("--brutos", type=Path)
    ap.add_argument("--saida", type=Path, default=REPO_ROOT / "build" / "reduced_rounds" / "floor_v2" / "metodo_redes")
    ap.add_argument("--smoke", action="store_true")
    a = ap.parse_args()
    _log(f"dispositivo {DISP}" + (f" ({torch.cuda.get_device_name(0)})" if DISP == "cuda" else ""))
    if a.modo == "piso":
        for algo in ([a.algo] if a.algo else list(CELULAS)):
            modo_piso(algo, a.dados, a.saida, a.smoke)
    elif a.modo == "gift4":
        modo_gift4(a.brutos, a.smoke)
    else:
        modo_plantado(a.smoke)
    _log("fim")


if __name__ == "__main__":
    main()
