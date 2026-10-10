"""
Dia 1 do v3: a cota de sinal em escala (ver o plano em docs/).

Contagem por bit e por par de bits do XOR de pares consecutivos, com o laço de
cifragem inteiro em C (`contador_escala.c`, compilado junto do .c de cada
algoritmo com as macros de rodadas das variantes). Contador zero, 100 pares por
dispositivo (nonces 2j e 2j+1, a vizinhança do v2), AD vazio, mensagens de 64
bytes.

Fontes de aleatoriedade (Regra de Ouro 8): chaves e índices de cada shard vêm de
um AES-128-CTR cuja chave é sorteada pelo CTR_DRBG (`label` próprio por shard),
o mesmo mecanismo do CTR_DRBG sem a atualização por pedido, que em Python puro
seria lento demais para 10⁹ pares. O conjunto de trechos é sorteado pelo
`_TextPlaintextSampler` com CTR_DRBG, como no `run_floor.py`. As chaves e os
claros de cada shard são os mesmos para todos os algoritmos e rodadas (Regra 6).

Braços: `texto-en` (fonte principal desde 08/10) e `aleatorio` (trechos
uniformes). Um trecho repete em vários pares; sob H0 (diferença de keystream
uniforme e independente entre pares) o XOR continua uniforme e independente,
então isso só custa poder, não validade.

Uso (dentro do ambiente MSVC; ver escala.bat):
    python escala.py build --algo ascon --rounds 4
    python escala.py rodar --algo ascon --rounds 3 4 --pares 1e9 --workers 11
    python escala.py stats --algo ascon --rounds 3 4
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "reduced_rounds"))

import build_variant as bv  # noqa: E402

AQUI = Path(__file__).resolve().parent
OUT = REPO_ROOT / "build" / "reduced_rounds" / "floor_v2" / "escala"
SEED = 999007
N_TRECHOS = 1_000_000
PARES_POR_DISP = 100
DISP_POR_SHARD = 10_000          # 10⁶ pares por shard
MSG = 64

CDEF = """
int acumula(const unsigned char *keys, int ndev, int pares_por_disp,
            const unsigned char *buf, const uint32_t *idx,
            int nonce_bytes, int tag_bytes,
            uint64_t *cnt_bits, uint64_t *cnt_pares, uint64_t *M);
int acumula2(const unsigned char *keys, int ndev, int pares_por_disp,
             const unsigned char *buf, const uint32_t *idx,
             int nonce_bytes, int tag_bytes, int layout,
             const unsigned char *cabecalhos, int cab_bytes,
             const unsigned char *ads, int ad_bytes,
             uint64_t *cnt_bits, uint64_t *cnt_pares, uint64_t *M);
int cubos(const unsigned char *keys, int ndev, int D, int nonce_bytes, int layout,
          const unsigned char *cabs, int cab_por_msg,
          uint64_t *cnt_um, uint64_t *n_cubos);
"""
ALGO = {   # nonce, tag, largura do primeiro bloco de taxa em bytes
    "ascon": (16, 16, 16), "schwaemm": (32, 16, 32), "grain": (12, 8, 16), "gift": (16, 16, 16),
}


def _log(m: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def _nome(algo: str, r: int) -> str:
    # _escala3_: harness com os eixos do Dia 2 e os cubos do Dia 3
    return f"_escala3_{algo}_r{r}"


def build(algo: str, r: int) -> Path:
    import cffi
    nome = _nome(algo, r)
    pronto = bv._already_built(nome)
    if pronto:
        return pronto
    ffi = cffi.FFI()
    ffi.cdef(CDEF)
    harness = str(AQUI / "contador_escala.c")
    if algo == "ascon":
        kw = dict(sources=[str(bv.ASCON_REF_DIR / "aead.c"), harness],
                  include_dirs=[str(bv.ASCON_REF_DIR), str(bv.ASCON_TESTS_DIR)],
                  define_macros=[("ASCON_PA_ROUNDS_OVERRIDE", str(r)),
                                 ("ASCON_PB_ROUNDS_OVERRIDE", str(min(r, 8)))])
    elif algo == "schwaemm":
        kw = dict(sources=[str(bv.SPARKLE_REF_DIR / "encrypt.c"), str(bv.SPARKLE_REF_DIR / "sparkle_ref.c"), harness],
                  include_dirs=[str(bv.SPARKLE_REF_DIR)],
                  define_macros=[("SPARKLE_STEPS_SLIM", str(min(r, 7))), ("SPARKLE_STEPS_BIG", str(r))])
    elif algo == "grain":
        kw = dict(sources=[str(bv.GRAIN_REF_DIR / "grain128aead.c"), harness],
                  include_dirs=[str(bv.GRAIN_REF_DIR)],
                  define_macros=[("GRAIN_INIT_ROUNDS_OVERRIDE", str(r))])
    else:
        kw = dict(sources=[str(AQUI / "gift_cofb_rodada.c"), harness],
                  include_dirs=[str(AQUI)], define_macros=[("GIFT_RODADAS", str(r))])
    ffi.set_source(nome, "#include <stdint.h>\n" + CDEF, **kw)
    return Path(ffi.compile(tmpdir=str(bv._out_dir(nome)), verbose=False))


def _importar(algo: str, r: int):
    import importlib
    d = str(bv.OUT_ROOT / _nome(algo, r))
    if d not in sys.path:
        sys.path.insert(0, d)
    return importlib.import_module(_nome(algo, r))


# ---------------------------------------------------------------- dados

def _aes_ctr(chave: bytes, n: int) -> np.ndarray:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    enc = Cipher(algorithms.AES(chave), modes.CTR(b"\x00" * 16)).encryptor()
    return np.frombuffer(enc.update(b"\x00" * n) + enc.finalize(), np.uint8)


def trechos(braco: str) -> np.ndarray:
    """N_TRECHOS × 64 bytes, em cache (o sorteio do texto é lento)."""
    cache = OUT / f"trechos_{braco}.npy"
    if cache.exists():
        return np.load(cache)
    from src.crypto.ctr_drbg import CTRDRBG
    OUT.mkdir(parents=True, exist_ok=True)
    drbg = CTRDRBG(seed=SEED, label=f"v3-escala-pt-{braco}")
    if braco == "aleatorio":
        buf = _aes_ctr(drbg.generate(16), N_TRECHOS * MSG).reshape(N_TRECHOS, MSG)
    else:
        from scripts.generate_5class_v2 import _TextPlaintextSampler
        corp = REPO_ROOT / "data" / "raw" / ("corpora_en" if braco == "texto-en" else "corpora")
        s = _TextPlaintextSampler(corp, drbg)
        buf = np.zeros((N_TRECHOS, MSG), np.uint8)
        t0 = time.time()
        for i in range(N_TRECHOS):
            buf[i] = np.frombuffer(s.sample()[:MSG], np.uint8)
            if (i + 1) % 100_000 == 0:
                _log(f"trechos {braco}: {i + 1}/{N_TRECHOS} ({time.time() - t0:.0f}s)")
    np.save(cache, buf)
    return buf


def cfg_tag(layout: int, cab: int, ad: int) -> str:
    """Sufixo da pasta de saída; vazio no desenho do Dia 1."""
    s = (f"_lay{layout}" if layout else "") + (f"_cab{cab}" if cab else "") + (f"_ad{ad}" if ad else "")
    return s


def material_dia2(shard: int, cab: int, ad: int):
    """Cabeçalho (16 bytes, usa os `cab` primeiros) e AD constantes por
    dispositivo, de um fluxo próprio, iguais para todos os algoritmos."""
    from src.crypto.ctr_drbg import CTRDRBG
    semente = CTRDRBG(seed=SEED, label=f"v3-dia2-shard-{shard}").generate(16)
    fluxo = _aes_ctr(semente, DISP_POR_SHARD * (16 + 32))
    cabs = fluxo[:DISP_POR_SHARD * 16].copy()
    ads = fluxo[DISP_POR_SHARD * 16:DISP_POR_SHARD * (16 + ad)].copy() if ad else np.zeros(1, np.uint8)
    return cabs, ads


def material_shard(shard: int):
    """Chaves e índices do shard, iguais para todos os algoritmos e rodadas."""
    from src.crypto.ctr_drbg import CTRDRBG
    semente = CTRDRBG(seed=SEED, label=f"v3-escala-shard-{shard}").generate(16)
    n_pares = DISP_POR_SHARD * PARES_POR_DISP
    fluxo = _aes_ctr(semente, DISP_POR_SHARD * 16 + 2 * n_pares * 4 + 4 * 65536)
    keys = fluxo[:DISP_POR_SHARD * 16].copy()
    raw = fluxo[DISP_POR_SHARD * 16:].view(np.uint32)
    idx = (raw[:2 * n_pares] % N_TRECHOS).astype(np.uint32)
    extra = raw[2 * n_pares:] % N_TRECHOS
    iguais = np.flatnonzero(idx[0::2] == idx[1::2])    # P1 = P2: reamostrar o segundo
    for n, p in enumerate(iguais):
        cand = extra[n]
        while cand == idx[2 * p]:
            cand = (cand + 1) % N_TRECHOS
        idx[2 * p + 1] = cand
    return keys, idx, len(iguais)


def _tarefa(args):
    algo, r, braco, shard, layout, cab, ad = args
    destino = OUT / f"{algo}_{braco}_r{r}{cfg_tag(layout, cab, ad)}" / f"shard_{shard:05d}.npz"
    if destino.exists():
        return shard, 0.0
    mod = _importar(algo, r)
    ffi, lib = mod.ffi, mod.lib
    nb, tb, _ = ALGO[algo]
    buf = trechos(braco)
    keys, idx, n_reamostra = material_shard(shard)
    nbits = (MSG + tb) * 8
    cb = np.zeros(nbits, np.uint64)
    cp = np.zeros(128 * 128, np.uint64)
    M = np.zeros(1, np.uint64)
    t = time.time()
    cabs, ads = material_dia2(shard, cab, ad)
    rc = lib.acumula2(ffi.from_buffer("unsigned char[]", keys), DISP_POR_SHARD, PARES_POR_DISP,
                      ffi.from_buffer("unsigned char[]", buf), ffi.from_buffer("uint32_t[]", idx),
                      nb, tb, layout, ffi.from_buffer("unsigned char[]", cabs), cab,
                      ffi.from_buffer("unsigned char[]", ads), ad,
                      ffi.from_buffer("uint64_t[]", cb), ffi.from_buffer("uint64_t[]", cp),
                      ffi.from_buffer("uint64_t[]", M))
    if rc:
        raise RuntimeError(f"acumula devolveu {rc}")
    dt = time.time() - t
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_suffix(".tmp.npz")
    np.savez(tmp, cnt_bits=cb, cnt_pares=cp, M=M, reamostrados=n_reamostra, segundos=dt)
    tmp.replace(destino)
    return shard, dt


def rodar(algo: str, rodadas: list[int], bracos: list[str], pares: float, workers: int,
          layout: int = 0, cab: int = 0, ad: int = 0) -> None:
    for b in bracos:
        trechos(b)                       # gera o cache uma vez, antes dos workers
    n_shards = int(math.ceil(pares / (DISP_POR_SHARD * PARES_POR_DISP)))
    tarefas = [(algo, r, b, s, layout, cab, ad) for s in range(n_shards) for r in rodadas for b in bracos]
    _log(f"{algo} rodadas {rodadas} braços {bracos}: {n_shards} shards de 10⁶ pares, "
         f"{len(tarefas)} tarefas, {workers} processos")
    t0 = time.time()
    with Pool(workers) as pool:
        for n, (shard, dt) in enumerate(pool.imap_unordered(_tarefa, tarefas), 1):
            if n % 20 == 0 or n == len(tarefas):
                _log(f"  {n}/{len(tarefas)} tarefas ({time.time() - t0:.0f}s; último shard {dt:.1f}s)")


# ---------------------------------------------------------------- estatística

def _sidak(z2max: float, n: int) -> float:
    from scipy.stats import chi2
    p1 = chi2.sf(z2max, 1)
    return float(-np.expm1(n * np.log1p(-p1))) if p1 < 1 else 1.0


def stats(algo: str, rodadas: list[int], bracos: list[str], layout: int = 0, cab: int = 0,
          ad: int = 0) -> list[dict]:
    from scipy.stats import chi2
    _, tb, taxa = ALGO[algo]
    linhas = []
    for r in rodadas:
        for b in bracos:
            arqs = sorted((OUT / f"{algo}_{b}_r{r}{cfg_tag(layout, cab, ad)}").glob("shard_*.npz"))
            if not arqs:
                continue
            cb = sum(np.load(a)["cnt_bits"].astype(np.float64) for a in arqs)
            cp = sum(np.load(a)["cnt_pares"].astype(np.float64) for a in arqs)
            M = float(sum(int(np.load(a)["M"][0]) for a in arqs))
            z = (cb - M / 2) / math.sqrt(M / 4)
            nt = taxa * 8
            zt = z[:nt]
            # paridade (i, l): x_i XOR x_l = 1  <=>  c_i + c_l - 2 n_il
            i, l = np.triu_indices(128, 1)
            par = cb[i] + cb[l] - 2 * cp[i * 128 + l]
            zp = (par - M / 2) / math.sqrt(M / 4)
            # Cota: com M pares, o maior viés |p - 1/2| que o teste do máximo
            # deixaria passar a 5% (Šidák), por bit.
            from scipy.stats import norm
            zc = norm.isf((1 - (0.95) ** (1 / nt)) / 2)
            linhas.append(dict(
                algo=algo, rodadas=r, braco=b, M=int(M), shards=len(arqs),
                layout=layout, cab=cab, ad=ad,
                primario_max_z=float(np.abs(zt).max()), primario_bit=int(np.abs(zt).argmax()),
                primario_p=_sidak(float((zt ** 2).max()), nt), n_bits_taxa=nt,
                paridades_max_z=float(np.abs(zp).max()), paridades_p=_sidak(float((zp ** 2).max()), len(zp)),
                sei_qui2=float((z ** 2).sum()), sei_gl=len(z), sei_p=float(chi2.sf((z ** 2).sum(), len(z))),
                cota_vies_por_bit=float(zc / (2 * math.sqrt(M))),
            ))
            d = linhas[-1]
            _log(f"{algo} r{r} {b}{cfg_tag(layout, cab, ad)}: M={M:.3g} | primário max|z|={d['primario_max_z']:.2f} (bit {d['primario_bit']}) "
                 f"p={d['primario_p']:.3g} | paridades max|z|={d['paridades_max_z']:.2f} p={d['paridades_p']:.3g} "
                 f"| SEI p={d['sei_p']:.3g} | cota de viés {100 * d['cota_vies_por_bit']:.4f}%")
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "escala_stats.jsonl").open("a", encoding="utf-8") as f:
        for d in linhas:
            f.write(json.dumps(d) + "\n")
    return linhas


# ---------------------------------------------------------------- Dia 3: cubos

D_CUBO = 10
DISP_CUBO = 1000


def _tarefa_cubo(args):
    algo, r, controle, shard = args
    destino = OUT / f"cubo_{algo}_r{r}{'_controle' if controle else ''}" / f"shard_{shard:05d}.npz"
    if destino.exists():
        return shard, 0.0
    from src.crypto.ctr_drbg import CTRDRBG
    mod = _importar(algo, r)
    ffi, lib = mod.ffi, mod.lib
    nb = ALGO[algo][0]
    semente = CTRDRBG(seed=SEED, label=f"v3-cubo-shard-{shard}").generate(16)
    N = 1 << D_CUBO
    n_cab = DISP_CUBO * (N if controle else 1)
    fluxo = _aes_ctr(semente, DISP_CUBO * 16 + n_cab * 16)
    keys = fluxo[:DISP_CUBO * 16].copy()
    cabs = fluxo[DISP_CUBO * 16:].copy()
    cnt = np.zeros((D_CUBO + 1) * 128, np.uint64)
    ncub = np.zeros(D_CUBO + 1, np.uint64)
    t = time.time()
    rc = lib.cubos(ffi.from_buffer("unsigned char[]", keys), DISP_CUBO, D_CUBO, nb, 0,
                   ffi.from_buffer("unsigned char[]", cabs), int(controle),
                   ffi.from_buffer("uint64_t[]", cnt), ffi.from_buffer("uint64_t[]", ncub))
    if rc:
        raise RuntimeError(f"cubos devolveu {rc}")
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_suffix(".tmp.npz")
    np.savez(tmp, cnt_um=cnt, n_cubos=ncub, segundos=time.time() - t)
    tmp.replace(destino)
    return shard, time.time() - t


def rodar_cubos(algo: str, rodadas: list[int], shards: int, workers: int) -> None:
    tarefas = [(algo, r, c, s) for s in range(shards) for r in rodadas for c in (False, True)]
    _log(f"cubos {algo} {rodadas}: {shards} shards de {DISP_CUBO} dispositivos x 2^{D_CUBO} mensagens")
    t0 = time.time()
    with Pool(workers) as pool:
        for n, (s, dt) in enumerate(pool.imap_unordered(_tarefa_cubo, tarefas), 1):
            if n % 10 == 0 or n == len(tarefas):
                _log(f"  {n}/{len(tarefas)} ({time.time() - t0:.0f}s; último {dt:.1f}s)")


def stats_cubos(algo: str, rodadas: list[int]) -> None:
    from scipy.stats import norm
    for r in rodadas:
        for controle in (False, True):
            arqs = sorted((OUT / f"cubo_{algo}_r{r}{'_controle' if controle else ''}").glob("shard_*.npz"))
            if not arqs:
                continue
            cnt = sum(np.load(a)["cnt_um"].astype(np.float64) for a in arqs).reshape(D_CUBO + 1, 128)
            nc = sum(np.load(a)["n_cubos"].astype(np.float64) for a in arqs)
            partes = []
            for d in range(1, D_CUBO + 1):
                n = nc[d]
                z = (cnt[d] - n / 2) / math.sqrt(n / 4)
                zmax = float(np.abs(z).max())
                p = min(1.0, 128 * 2 * norm.sf(zmax))
                zero = int((cnt[d] == 0).sum())
                partes.append(f"d{d}: z={zmax:.1f} p={p:.2g} zero-sum={zero}")
            _log(f"cubos {algo} r{r} {'controle' if controle else 'cabecalho'}: " + " | ".join(partes))
            with (OUT / "cubos_stats.jsonl").open("a", encoding="utf-8") as f:
                for d in range(1, D_CUBO + 1):
                    n = nc[d]; z = (cnt[d] - n / 2) / math.sqrt(n / 4)
                    f.write(json.dumps(dict(algo=algo, rodadas=r, controle=controle, d=d, n_cubos=int(n),
                                            max_z=float(np.abs(z).max()), bit=int(np.abs(z).argmax()),
                                            zero_sum=int((cnt[d] == 0).sum()))) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("acao", choices=["build", "rodar", "stats", "cubos", "stats-cubos"])
    ap.add_argument("--shards", type=int, default=3)
    ap.add_argument("--algo", required=True, choices=sorted(ALGO))
    ap.add_argument("--rounds", nargs="+", type=int, required=True)
    ap.add_argument("--bracos", nargs="+", default=["texto-en", "aleatorio"])
    ap.add_argument("--pares", type=float, default=1e7)
    ap.add_argument("--workers", type=int, default=11)
    ap.add_argument("--layout", type=int, default=0, help="0 BE no fim (v2), 1 LE no início, 2 BE até o byte 7")
    ap.add_argument("--cab", type=int, default=0, help="bytes de cabeçalho constante (0, 8, 16)")
    ap.add_argument("--ad", type=int, default=0, help="bytes de AD constante (0, 16, 32)")
    a = ap.parse_args()
    if a.acao == "build":
        for r in a.rounds:
            print(build(a.algo, r))
    elif a.acao == "rodar":
        for r in a.rounds:
            build(a.algo, r)
        rodar(a.algo, a.rounds, a.bracos, a.pares, a.workers, a.layout, a.cab, a.ad)
    elif a.acao == "cubos":
        for r in a.rounds:
            build(a.algo, r)
        rodar_cubos(a.algo, a.rounds, a.shards, a.workers)
    elif a.acao == "stats-cubos":
        stats_cubos(a.algo, a.rounds)
    else:
        stats(a.algo, a.rounds, a.bracos, a.layout, a.cab, a.ad)


if __name__ == "__main__":
    main()
