"""
Configuração global de pytest para o projeto lwc-ml.

Adiciona a raiz do repositório e src/crypto/ ao sys.path para que:
  - `from src.crypto.ascon_wrapper import ...` funcione sem instalação
  - `import _ascon_ref` (extensão cffi nativa) seja encontrado em src/crypto/
"""
import sys
from pathlib import Path

_ROOT = Path(__file__).parent
_CRYPTO_DIR = _ROOT / "src" / "crypto"

for _p in (_ROOT, _CRYPTO_DIR):
    s = str(_p)
    if s not in sys.path:
        sys.path.insert(0, s)
