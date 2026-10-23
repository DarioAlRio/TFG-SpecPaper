"""Carga de la configuración (config.yaml)."""

from pathlib import Path

import yaml
from pydantic import BaseModel


class LLMConfig(BaseModel):
    provider: str = "ollama"
    model: str = "qwen3.5:4b"
    host: str = "http://localhost:11434"
    num_ctx: int = 8192
    temperature: float = 0.4
    think: bool | None = None
    # Solo para APIs (Anthropic): esfuerzo de razonamiento y longitud máxima de la respuesta
    effort: str | None = None
    max_tokens: int = 16000


class InvestigacionConfig(BaseModel):
    buscadores: list[str] = ["arxiv"]  # arxiv, semantic_scholar
    resultados_por_consulta: int = 10
    max_fuentes: int = 15


class Settings(BaseModel):
    llm: LLMConfig = LLMConfig()
    agents: dict[str, dict] = {}
    output_dir: Path = Path("outputs")
    max_rondas_revision: int = 2
    max_pasos_orquestador: int = 40
    investigacion: InvestigacionConfig = InvestigacionConfig()

    def llm_for(self, agent: str) -> LLMConfig:
        """Configuración del LLM para un agente, aplicando sus ajustes propios."""
        return self.llm.model_copy(update=self.agents.get(agent, {}))


def load_settings(path: str | Path = "config.yaml") -> Settings:
    path = Path(path)
    if not path.exists():
        return Settings()
    with open(path, encoding="utf-8") as f:
        return Settings.model_validate(yaml.safe_load(f) or {})
