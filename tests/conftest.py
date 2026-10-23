"""Utilidades comunes de los tests: no usan ningún LLM real."""

from pathlib import Path

import pytest

from articulos_ia.spec import ArticleSpec

ROOT = Path(__file__).parent.parent


class FakeLLM:
    """LLM falso: devuelve respuestas fijas, en orden, y guarda los mensajes recibidos."""

    def __init__(self, *responses: str):
        self.responses = list(responses)
        self.calls: list[list[dict]] = []

    def chat(self, messages, schema=None):
        self.calls.append(list(messages))
        return self.responses.pop(0)


@pytest.fixture
def spec() -> ArticleSpec:
    return ArticleSpec.from_yaml(ROOT / "specs" / "ejemplo.yaml")
