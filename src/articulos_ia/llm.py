"""Acceso a los modelos de lenguaje.

Los agentes solo conocen la interfaz `LLMClient`, así que cambiar de Ollama a una API
(Anthropic, OpenAI...) consiste en añadir otra clase aquí y cambiar config.yaml.

Proveedores: `ollama` (local), `anthropic` (API, con clave) y `claude_code` (Claude Code
con la sesión de una suscripción Pro/Max, sin clave).
"""

import json
import logging
import shutil
import subprocess
import time
from typing import Protocol

from articulos_ia.config import LLMConfig

log = logging.getLogger(__name__)


class LLMClient(Protocol):
    def chat(self, messages: list[dict], schema: dict | None = None) -> str:
        """Devuelve el texto de la respuesta. Con `schema`, la respuesta es JSON que lo cumple."""
        ...


class OllamaClient:
    # En el portátil de desarrollo el proceso del modelo se cae cada pocas decenas de llamadas
    # (error 500, "model runner has unexpectedly stopped"). Ollama lo vuelve a cargar en la
    # siguiente petición, así que basta con esperar un poco y reintentar.
    reintentos: int = 3
    espera: float = 10.0  # segundos antes del primer reintento; se duplica en cada uno

    def __init__(self, config: LLMConfig):
        from ollama import Client

        self.config = config
        self._client = Client(host=config.host)

    def chat(self, messages: list[dict], schema: dict | None = None) -> str:
        from ollama import ResponseError

        for intento in range(self.reintentos + 1):
            try:
                response = self._client.chat(
                    model=self.config.model,
                    messages=messages,
                    format=schema,
                    think=self.config.think,
                    options={
                        "num_ctx": self.config.num_ctx,
                        "temperature": self.config.temperature,
                    },
                )
                return response.message.content
            except ResponseError as e:
                if e.status_code != 500 or intento == self.reintentos:
                    raise
                espera = self.espera * 2**intento
                log.warning("Ollama ha fallado (%s); reintento en %.0f s", e.error, espera)
                time.sleep(espera)
        raise AssertionError("inalcanzable")


class AnthropicClient:
    """Claude (API de Anthropic). Lee la clave de la variable de entorno ANTHROPIC_API_KEY."""

    def __init__(self, config: LLMConfig):
        from anthropic import Anthropic

        self.config = config
        self._client = Anthropic()

    def chat(self, messages: list[dict], schema: dict | None = None) -> str:
        # La API recibe el system prompt aparte, no como un mensaje más.
        system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
        output_config = {}
        if self.config.effort:
            output_config["effort"] = self.config.effort
        if schema:
            output_config["format"] = {"type": "json_schema", "schema": _strict(schema)}

        response = self._client.beta.messages.create(
            model=self.config.model,
            max_tokens=self.config.max_tokens,
            system=system,
            messages=[m for m in messages if m["role"] != "system"],
            output_config=output_config,
            # Si el modelo rechaza la petición, la API la repite con otro modelo de respaldo.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        if response.stop_reason == "refusal":
            raise RuntimeError(f"El modelo ha rechazado la petición: {response.stop_details}")
        return "".join(b.text for b in response.content if b.type == "text")


def _strict(schema: dict) -> dict:
    """La salida estructurada de Claude exige `additionalProperties: false` en cada objeto."""
    if isinstance(schema, dict):
        schema = {k: _strict(v) for k, v in schema.items()}
        if schema.get("type") == "object":
            schema["additionalProperties"] = False
    elif isinstance(schema, list):
        schema = [_strict(v) for v in schema]
    return schema


class ClaudeCodeClient:
    """Claude a través de Claude Code en modo no interactivo (`claude -p`).

    Usa la sesión iniciada en Claude Code (suscripción Pro/Max), así que no necesita API key;
    el consumo se descuenta de los límites de uso de la suscripción. Se desactivan las
    herramientas, la configuración local y los servidores MCP para que Claude Code se
    comporte como un modelo de lenguaje sin más.
    """

    timeout: float = 600.0

    def __init__(self, config: LLMConfig):
        ejecutable = shutil.which("claude")
        if not ejecutable:
            raise RuntimeError("No se encuentra Claude Code (`claude`) en el PATH")
        self.config = config
        self.ejecutable = ejecutable

    def chat(self, messages: list[dict], schema: dict | None = None) -> str:
        system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
        args = [
            self.ejecutable,
            "-p",
            "--output-format", "json",
            "--model", self.config.model,
            "--tools", "",
            "--no-session-persistence",
            "--strict-mcp-config",
            "--setting-sources", "",
        ]  # fmt: skip
        if system:
            args += ["--system-prompt", system]
        if schema:
            args += ["--json-schema", json.dumps(schema, ensure_ascii=False)]

        # El mensaje va por la entrada estándar: en Windows la línea de órdenes tiene un límite
        # de 32 767 caracteres y un encargo con la sección completa puede superarlo.
        proceso = subprocess.run(
            args,
            input=_conversacion(messages),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=self.timeout,
        )
        try:
            data = json.loads(proceso.stdout)
        except json.JSONDecodeError:
            raise RuntimeError(
                f"Claude Code no devolvió JSON (código {proceso.returncode}): "
                f"{(proceso.stderr or proceso.stdout)[:500]}"
            ) from None
        if data.get("is_error"):
            raise RuntimeError(f"Claude Code devolvió un error: {data.get('result')}")
        if schema and data.get("structured_output") is not None:
            return json.dumps(data["structured_output"], ensure_ascii=False)
        return data.get("result", "")


def _conversacion(messages: list[dict]) -> str:
    """`claude -p` recibe un único mensaje. Si hay varios (por ejemplo, el reintento con el
    error de validación), se le pasan todos en orden, indicando quién dijo cada cosa."""
    turnos = [m for m in messages if m["role"] != "system"]
    if len(turnos) == 1:
        return turnos[0]["content"]
    etiquetas = {"user": "Usuario", "assistant": "Tu respuesta anterior"}
    return "\n\n".join(f"[{etiquetas[m['role']]}]\n{m['content']}" for m in turnos)


def create_llm(config: LLMConfig) -> LLMClient:
    if config.provider == "ollama":
        return OllamaClient(config)
    if config.provider == "anthropic":
        return AnthropicClient(config)
    if config.provider == "claude_code":
        return ClaudeCodeClient(config)
    raise ValueError(f"Proveedor de LLM no soportado todavía: {config.provider}")
