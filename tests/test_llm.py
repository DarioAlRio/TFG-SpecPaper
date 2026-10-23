"""Tests de los clientes de LLM sin llamar a Ollama ni a la API (clientes falsos)."""

import json
from types import SimpleNamespace

import pytest
from ollama import ResponseError

from articulos_ia.agents import Esquema
from articulos_ia.config import LLMConfig
from articulos_ia.llm import AnthropicClient, ClaudeCodeClient, OllamaClient, _strict


class FakeMessages:
    def __init__(self):
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(
            stop_reason="end_turn",
            content=[SimpleNamespace(type="thinking"), SimpleNamespace(type="text", text="hola")],
        )


def cliente_falso(**config) -> tuple[AnthropicClient, FakeMessages]:
    llm = AnthropicClient.__new__(AnthropicClient)  # sin crear el cliente real
    llm.config = LLMConfig(provider="anthropic", model="claude-opus-5-5", **config)
    messages = FakeMessages()
    llm._client = SimpleNamespace(beta=SimpleNamespace(messages=messages))
    return llm, messages


def test_anthropic_separa_el_system_prompt():
    llm, api = cliente_falso(effort="low")
    texto = llm.chat([{"role": "system", "content": "S"}, {"role": "user", "content": "U"}])

    assert texto == "hola"
    assert api.kwargs["system"] == "S"
    assert api.kwargs["messages"] == [{"role": "user", "content": "U"}]
    assert api.kwargs["output_config"] == {"effort": "low"}
    assert "temperature" not in api.kwargs


def test_anthropic_pide_json_con_esquema():
    llm, api = cliente_falso()
    llm.chat([{"role": "user", "content": "U"}], schema=Esquema.model_json_schema())
    formato = api.kwargs["output_config"]["format"]
    assert formato["type"] == "json_schema"
    assert formato["schema"]["additionalProperties"] is False


def test_strict_marca_todos_los_objetos():
    schema = _strict(Esquema.model_json_schema())
    assert schema["$defs"]["SeccionPlan"]["additionalProperties"] is False


class FalloOllama:
    """Cliente de Ollama falso: falla con los errores dados y luego responde."""

    def __init__(self, *errores: ResponseError):
        self.errores = list(errores)
        self.llamadas = 0

    def chat(self, **kwargs):
        self.llamadas += 1
        if self.errores:
            raise self.errores.pop(0)
        return SimpleNamespace(message=SimpleNamespace(content="ok"))


def ollama_falso(*errores) -> tuple[OllamaClient, FalloOllama]:
    llm = OllamaClient.__new__(OllamaClient)
    llm.config = LLMConfig()
    llm.espera = 0
    llm._client = FalloOllama(*errores)
    return llm, llm._client


def test_ollama_reintenta_si_el_modelo_se_cae():
    caida = ResponseError("model runner has unexpectedly stopped", 500)
    llm, cliente = ollama_falso(caida, caida)
    assert llm.chat([{"role": "user", "content": "U"}]) == "ok"
    assert cliente.llamadas == 3


def test_ollama_no_reintenta_otros_errores_ni_indefinidamente():
    llm, cliente = ollama_falso(ResponseError("model not found", 404))
    with pytest.raises(ResponseError):
        llm.chat([])
    assert cliente.llamadas == 1

    caida = ResponseError("caído", 500)
    llm, cliente = ollama_falso(*[caida] * 10)
    with pytest.raises(ResponseError):
        llm.chat([])
    assert cliente.llamadas == 4  # 1 + 3 reintentos


def claude_code_falso(monkeypatch, respuesta: dict):
    llamadas = []

    def run(args, **kwargs):
        llamadas.append((args, kwargs))
        return SimpleNamespace(stdout=json.dumps(respuesta), stderr="", returncode=0)

    monkeypatch.setattr("articulos_ia.llm.subprocess.run", run)
    llm = ClaudeCodeClient.__new__(ClaudeCodeClient)
    llm.config = LLMConfig(provider="claude_code", model="sonnet")
    llm.ejecutable = "claude"
    return llm, llamadas


def test_claude_code_texto_libre(monkeypatch):
    llm, llamadas = claude_code_falso(monkeypatch, {"is_error": False, "result": "Hola"})
    texto = llm.chat([{"role": "system", "content": "S"}, {"role": "user", "content": "U"}])

    assert texto == "Hola"
    args, kwargs = llamadas[0]
    assert args[:2] == ["claude", "-p"]
    assert args[args.index("--system-prompt") + 1] == "S"
    assert args[args.index("--model") + 1] == "sonnet"
    assert args[args.index("--tools") + 1] == ""  # sin herramientas
    assert "--json-schema" not in args
    assert kwargs["input"] == "U"  # el mensaje va por la entrada estándar


def test_claude_code_json_con_esquema_y_reintento(monkeypatch):
    llm, llamadas = claude_code_falso(
        monkeypatch, {"is_error": False, "result": "...", "structured_output": {"a": "ñ"}}
    )
    mensajes = [
        {"role": "system", "content": "S"},
        {"role": "user", "content": "pregunta"},
        {"role": "assistant", "content": "mal"},
        {"role": "user", "content": "corrígela"},
    ]
    assert json.loads(llm.chat(mensajes, schema={"type": "object"})) == {"a": "ñ"}
    args, kwargs = llamadas[0]
    assert json.loads(args[args.index("--json-schema") + 1]) == {"type": "object"}
    assert kwargs["input"] == (
        "[Usuario]\npregunta\n\n[Tu respuesta anterior]\nmal\n\n[Usuario]\ncorrígela"
    )


def test_claude_code_error(monkeypatch):
    llm, _ = claude_code_falso(monkeypatch, {"is_error": True, "result": "usage limit"})
    with pytest.raises(RuntimeError, match="usage limit"):
        llm.chat([{"role": "user", "content": "U"}])
