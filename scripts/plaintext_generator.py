from __future__ import annotations

from importlib.resources import path
import random
from pathlib import Path


class PlaintextGenerator:
    def __init__(self, base_path: Path):
        self.corpora = {}

        txt_files = sorted(base_path.glob("*.txt"))
        if not txt_files:
            raise ValueError(f"Nenhum arquivo .txt encontrado em: {base_path}")

        for path in txt_files:
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                # Skip non-UTF-8 files to maintain data integrity
                continue                                
            # limpeza básica
            text = text.replace("\n", " ")
            text = " ".join(text.split())

            data = text.encode("utf-8")

            if len(data) < 1000:
                # pula arquivos muito pequenos
                continue

            source_name = path.stem
            self.corpora[source_name] = data

        if not self.corpora:
            raise ValueError("Nenhum corpus válido com pelo menos 1000 bytes foi carregado.")

        self.names = list(self.corpora.keys())

    def sample(self, length: int) -> tuple[bytes, str]:
        """
        Retorna:
        - pt (bytes) com tamanho exato em bytes
        - source (str)

        Garante que o trecho sorteado continua sendo UTF-8 válido.
        """
        for _ in range(1000):
            source = random.choice(self.names)
            data = self.corpora[source]

            if len(data) < length:
                continue

            start = random.randint(0, len(data) - length)
            chunk = data[start : start + length]

            try:
                chunk.decode("utf-8")
                return chunk, source
            except UnicodeDecodeError:
                continue

        raise RuntimeError(
            "Não foi possível amostrar um chunk UTF-8 válido no número de tentativas."
        )