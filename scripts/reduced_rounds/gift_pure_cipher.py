"""
GIFT-COFB com granularidade de UMA rodada, para o estudo de fronteira de rodadas.

Por que existe. O wrapper de produção e as variantes compiladas por
`build_variant.py` usam a implementação `opt32` fixsliced, cujo laço é o
`QUINTUPLE_ROUND`: só dá para reduzir de 5 em 5 (5, 10, ..., 40). Como a
difusão completa do GIFT-128 acontece em poucas rodadas, o piso provavelmente
cai ABAIXO de 5, e o salto de 5 esconderia justamente a região de interesse.

De onde vem a implementação. Não há reimplementação nova aqui: este módulo
importa `gift_cofb_encrypt` de `tests/test_crypto_independente.py`, que é a
reimplementação independente em Python puro já usada como âncora externa de
corretude do GIFT-COFB (o KAT em `data/kat/` é autogerado a partir do próprio
`.pyd`, então quem sustenta a corretude é esta reimplementação — ver
`CLAUDE.md` e `data/kat/README.md`). Importar em vez de duplicar mantém uma
única fonte da verdade: se a âncora mudar, este cifrador muda junto, e os
testes pegam divergência.

Custo medido (payload de 64 bytes, que é o que o experimento de pares usa):
~1,1 ms por mensagem com 40 rodadas, e menos com rodadas reduzidas. Para
300 chaves x 100 pares x 2 cifragens dá pouco mais de 1 minuto por configuração.
Não serve para os 64 KB do dataset v2; serve para os primeiros blocos, que é o
que as features de par consomem.

A interface é a mesma de `ReducedRoundsCipher` (`encrypt(key, nonce, pt, ad)`),
de propósito, para que os runners aceitem os dois sem ramificação.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests.test_crypto_independente import gift_cofb_encrypt  # noqa: E402

MAX_ROUNDS = 40
KEY_BYTES = 16
NONCE_BYTES = 16
TAG_BYTES = 16

# Vetor fixo para a checagem de sanidade contra o binário de produção. Roda uma
# vez por processo, na primeira instanciação.
_CHECK_KEY = bytes(range(16))
_CHECK_NONCE = bytes(range(16, 32))
_CHECK_PT = bytes(range(64))
_checked = False


def _check_against_production() -> None:
    """Confere que a implementação em Python reproduz o binário em 40 rodadas.

    Não valida a variante reduzida (não há binário com que comparar); valida o
    cifrador e o modo COFB em volta, que é o que a redução NÃO deve alterar.
    """
    global _checked
    if _checked:
        return
    from src.crypto.gift_cofb_wrapper import GiftCOFB

    esperado = GiftCOFB().encrypt(_CHECK_KEY, _CHECK_NONCE, _CHECK_PT)
    obtido = gift_cofb_encrypt(_CHECK_KEY, _CHECK_NONCE, _CHECK_PT, b"", rounds=MAX_ROUNDS)
    if obtido != esperado:
        raise RuntimeError(
            "GIFT-COFB em Python divergiu do binário de produção em 40 rodadas; "
            "a granularidade fina não pode ser usada até isso ser resolvido"
        )
    _checked = True


class PureGiftCOFB:
    """GIFT-COFB com número de rodadas arbitrário entre 1 e 40.

    Args:
        rounds: rodadas do cifrador de bloco interno. A redução toma as
            PRIMEIRAS rodadas, porque o key schedule do GIFT avança por rodada
            (a rodada r usa a r-ésima subchave). O modo COFB em volta fica
            intacto, então a tag continua de 16 bytes.
        validate: confere uma vez por processo que a implementação bate com o
            binário de produção em 40 rodadas.
    """

    def __init__(self, rounds: int = MAX_ROUNDS, validate: bool = True) -> None:
        if not isinstance(rounds, int) or not 1 <= rounds <= MAX_ROUNDS:
            raise ValueError(f"rounds deve ser inteiro entre 1 e {MAX_ROUNDS}, recebeu {rounds!r}")
        self.rounds = rounds
        self.algo = "gift"
        if validate:
            _check_against_production()

    def encrypt(self, key: bytes, nonce: bytes, plaintext: bytes,
                associated_data: bytes = b"") -> bytes:
        if len(key) != KEY_BYTES:
            raise ValueError(f"key deve ter {KEY_BYTES} bytes, recebeu {len(key)}")
        if len(nonce) != NONCE_BYTES:
            raise ValueError(f"nonce deve ter {NONCE_BYTES} bytes, recebeu {len(nonce)}")
        return gift_cofb_encrypt(key, nonce, plaintext, associated_data, rounds=self.rounds)

    def __repr__(self) -> str:  # pragma: no cover - conveniência de log
        return f"PureGiftCOFB(rounds={self.rounds})"
