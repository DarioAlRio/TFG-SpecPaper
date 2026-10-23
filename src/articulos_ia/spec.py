"""Especificación de un artículo: la entrada de todo el sistema."""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field


class ArticleSpec(BaseModel):
    titulo: str
    idioma: Literal["es", "en"] = "es"
    tipo: Literal["revision", "experimental", "posicion"] = "revision"
    extension_palabras: int = Field(default=3000, gt=0)
    objetivo: str
    preguntas_investigacion: list[str] = Field(min_length=1)
    palabras_clave: list[str] = []
    secciones: list[str] | None = None
    criterios_aceptacion: list[str] = []

    @classmethod
    def from_yaml(cls, path: str | Path) -> "ArticleSpec":
        with open(path, encoding="utf-8") as f:
            return cls.model_validate(yaml.safe_load(f))

    def to_yaml(self) -> str:
        return yaml.safe_dump(
            self.model_dump(exclude_none=True), allow_unicode=True, sort_keys=False
        )
