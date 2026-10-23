"""Agente Planificador: convierte la especificación en el esquema del artículo."""

from pydantic import BaseModel, Field

from articulos_ia.agents.base import Agent
from articulos_ia.spec import ArticleSpec


class SeccionPlan(BaseModel):
    titulo: str
    objetivo: str = Field(description="Qué debe conseguir esta sección")
    puntos_clave: list[str] = Field(description="Ideas o argumentos que debe desarrollar")
    preguntas: list[int] = Field(
        description="Números (empezando en 1) de las preguntas de investigación que aborda"
    )
    palabras: int = Field(description="Extensión aproximada en palabras")


class Esquema(BaseModel):
    titulo: str
    resumen: str = Field(description="Borrador del abstract, 100-200 palabras")
    secciones: list[SeccionPlan] = Field(min_length=1)


class Planificador(Agent):
    name = "planificador"

    def run(self, spec: ArticleSpec) -> Esquema:
        return self.ask(f"Especificación del artículo:\n\n{spec.to_yaml()}", Esquema)
