"""Base común de todos los agentes."""

from importlib.resources import files

from pydantic import BaseModel, ValidationError

from articulos_ia.llm import LLMClient


class AgentError(Exception):
    pass


class Agent:
    """Un agente = un rol (system prompt) + un LLM + una salida estructurada y validada."""

    name: str
    max_attempts: int = 3

    def __init__(self, llm: LLMClient):
        self.llm = llm
        self.system_prompt = (
            files("articulos_ia.prompts").joinpath(f"{self.name}.md").read_text(encoding="utf-8")
        )

    def _messages(self, user_message: str) -> list[dict]:
        return [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_message},
        ]

    def write(self, user_message: str) -> str:
        """Pide al LLM texto libre (sin JSON); reintenta si la respuesta llega vacía."""
        for _ in range(self.max_attempts):
            text = self.llm.chat(self._messages(user_message)).strip()
            if text:
                return text
        raise AgentError(f"{self.name}: respuesta vacía tras {self.max_attempts} intentos")

    def ask[T: BaseModel](self, user_message: str, output: type[T]) -> T:
        """Pide al LLM una respuesta con el formato `output`; si no es válida, reintenta
        indicándole el error para que lo corrija."""
        messages = self._messages(user_message)
        schema = output.model_json_schema()
        for _ in range(self.max_attempts):
            raw = self.llm.chat(messages, schema=schema)
            try:
                return output.model_validate_json(raw)
            except ValidationError as e:
                messages += [
                    {"role": "assistant", "content": raw},
                    {"role": "user", "content": f"La respuesta no es válida:\n{e}\nCorrígela."},
                ]
        raise AgentError(f"{self.name}: sin respuesta válida tras {self.max_attempts} intentos")
