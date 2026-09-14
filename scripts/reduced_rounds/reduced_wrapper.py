"""
Wrapper genérico para os módulos `.pyd` compilados por `build_variant.py`.

Os três algoritmos usam a mesma API SUPERCOP/eBACS (`crypto_aead_encrypt` /
`crypto_aead_decrypt`), então um único wrapper serve para os três — só varia
KEYBYTES/NPUBBYTES/ABYTES, que são propriedades do algoritmo, não da
implementação. Isso é deliberadamente uma classe PARALELA a
`AsconAEAD128`/`GiftCOFB`/`Schwaemm256_128` (não uma subclasse nem substituto):
carrega o `.pyd` de um caminho explícito, não pelo nome fixo que os wrappers
de produção esperam em `src/crypto/`.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import NamedTuple


class AlgoSpec(NamedTuple):
    key_bytes: int
    nonce_bytes: int
    tag_bytes: int


ALGO_SPECS = {
    "ascon": AlgoSpec(16, 16, 16),
    "gift": AlgoSpec(16, 16, 16),
    "schwaemm": AlgoSpec(16, 32, 16),
}


def _load_module(pyd_path: Path):
    pyd_path = Path(pyd_path)
    module_name = pyd_path.stem.split(".")[0]  # remove sufixo cpXXX-win_amd64
    spec = importlib.util.spec_from_file_location(module_name, pyd_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"não foi possível carregar {pyd_path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


class ReducedRoundsCipher:
    """Cifrador AEAD genérico sobre um `.pyd` variante, por caminho explícito."""

    def __init__(self, pyd_path: str | Path, algo: str) -> None:
        if algo not in ALGO_SPECS:
            raise ValueError(f"algo={algo!r} desconhecido. Opções: {list(ALGO_SPECS)}")
        self.algo = algo
        self.spec = ALGO_SPECS[algo]
        self._mod = _load_module(pyd_path)
        self._ffi = self._mod.ffi
        self._lib = self._mod.lib

    def encrypt(self, key: bytes, nonce: bytes, plaintext: bytes,
                associated_data: bytes = b"") -> bytes:
        if len(key) != self.spec.key_bytes:
            raise ValueError(f"key deve ter {self.spec.key_bytes} bytes, recebeu {len(key)}")
        if len(nonce) != self.spec.nonce_bytes:
            raise ValueError(f"nonce deve ter {self.spec.nonce_bytes} bytes, recebeu {len(nonce)}")
        ffi, lib = self._ffi, self._lib
        ct_len = len(plaintext) + self.spec.tag_bytes
        c_buf = ffi.new(f"unsigned char[{max(ct_len, 1)}]")
        clen_out = ffi.new("unsigned long long *", ct_len)
        rc = lib.crypto_aead_encrypt(
            c_buf, clen_out,
            plaintext, len(plaintext),
            associated_data, len(associated_data),
            ffi.NULL, nonce, key,
        )
        if rc != 0:
            raise RuntimeError(f"crypto_aead_encrypt retornou {rc}")
        return bytes(ffi.buffer(c_buf, int(clen_out[0])))

    def decrypt(self, key: bytes, nonce: bytes, ciphertext: bytes,
                associated_data: bytes = b"") -> bytes:
        if len(ciphertext) < self.spec.tag_bytes:
            raise ValueError("ciphertext menor que o tamanho da tag")
        ffi, lib = self._ffi, self._lib
        pt_len = len(ciphertext) - self.spec.tag_bytes
        m_buf = ffi.new(f"unsigned char[{max(pt_len, 1)}]")
        mlen_out = ffi.new("unsigned long long *", pt_len)
        rc = lib.crypto_aead_decrypt(
            m_buf, mlen_out, ffi.NULL,
            ciphertext, len(ciphertext),
            associated_data, len(associated_data),
            nonce, key,
        )
        if rc != 0:
            raise RuntimeError(f"crypto_aead_decrypt retornou {rc} (autenticação falhou)")
        return bytes(ffi.buffer(m_buf, int(mlen_out[0])))
