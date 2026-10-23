"""Agente Investigador: busca artículos reales sobre el tema de la especificación.

1. El LLM propone consultas de búsqueda a partir de la spec.
2. El código las lanza contra arXiv / Semantic Scholar (sin IA).
3. El LLM valora la relevancia de cada artículo a partir de su resumen, por lotes
   pequeños para no desbordar el contexto del modelo.
"""

from collections.abc import Callable

from pydantic import BaseModel, Field

from articulos_ia.agents.base import Agent
from articulos_ia.fuentes import Articulo, Buscador, buscar
from articulos_ia.spec import ArticleSpec


class Consultas(BaseModel):
    consultas: list[str] = Field(
        min_length=1, description="Consultas de búsqueda en inglés, de 2 a 5 palabras cada una"
    )


class Valoracion(BaseModel):
    indice: int = Field(description="Número del artículo en la lista recibida")
    puntuacion: int = Field(
        ge=0, le=3, description="0 nada relevante, 1 poco, 2 relevante, 3 muy relevante"
    )
    motivo: str = Field(description="Por qué es (o no es) útil para el artículo, en una frase")
    preguntas: list[int] = Field(
        description="Números (empezando en 1) de las preguntas que ayuda a responder"
    )


class Valoraciones(BaseModel):
    valoraciones: list[Valoracion]


class FuenteSeleccionada(BaseModel):
    articulo: Articulo
    puntuacion: int
    motivo: str
    preguntas: list[int]


class Investigacion(BaseModel):
    consultas: list[str]
    encontrados: int
    fuentes: list[FuenteSeleccionada]

    def to_markdown(self) -> str:
        lineas = ["# Fuentes seleccionadas", "", f"Consultas: {', '.join(self.consultas)}", ""]
        for n, f in enumerate(self.fuentes, 1):
            a = f.articulo
            autores = ", ".join(a.autores[:3]) + (" et al." if len(a.autores) > 3 else "")
            lineas.append(f"{n}. **{a.titulo}** — {autores} ({a.anio}). <{a.url}>")
            lineas.append(f"   - Relevancia {f.puntuacion}/3, preguntas {f.preguntas}: {f.motivo}")
        return "\n".join(lineas) + "\n"


class Investigador(Agent):
    name = "investigador"
    lote: int = 5  # artículos por llamada al LLM al valorar
    max_resumen: int = 1200  # caracteres del resumen que se le pasan
    min_puntuacion: int = 2

    def __init__(
        self,
        llm,
        buscadores: list[Buscador],
        resultados_por_consulta: int = 10,
        max_fuentes: int = 15,
    ):
        super().__init__(llm)
        self.buscadores = buscadores
        self.resultados_por_consulta = resultados_por_consulta
        self.max_fuentes = max_fuentes

    def run(
        self, spec: ArticleSpec, on_progress: Callable[[str], None] | None = None
    ) -> Investigacion:
        avisar = on_progress or (lambda _: None)
        consultas = self.ask(
            f"Especificación del artículo:\n\n{spec.to_yaml()}\n\n"
            "Propón las consultas de búsqueda de artículos científicos.",
            Consultas,
        ).consultas
        avisar(f"Consultas: {consultas}")

        articulos = buscar(consultas, self.buscadores, self.resultados_por_consulta)
        avisar(f"{len(articulos)} artículos encontrados; valorando su relevancia...")

        seleccion = []
        for inicio in range(0, len(articulos), self.lote):
            lote = articulos[inicio : inicio + self.lote]
            for v in self._valorar(spec, lote):
                if 1 <= v.indice <= len(lote) and v.puntuacion >= self.min_puntuacion:
                    seleccion.append(
                        FuenteSeleccionada(
                            articulo=lote[v.indice - 1],
                            puntuacion=v.puntuacion,
                            motivo=v.motivo,
                            preguntas=v.preguntas,
                        )
                    )
        seleccion.sort(key=lambda f: f.puntuacion, reverse=True)  # estable: mantiene el orden
        return Investigacion(
            consultas=consultas,
            encontrados=len(articulos),
            fuentes=_sin_repetir(seleccion)[: self.max_fuentes],
        )

    def _valorar(self, spec: ArticleSpec, lote: list[Articulo]) -> list[Valoracion]:
        preguntas = "\n".join(f"{n}. {p}" for n, p in enumerate(spec.preguntas_investigacion, 1))
        lista = "\n\n".join(
            f"[{n}] {a.titulo} ({a.anio})\n{a.resumen[: self.max_resumen]}"
            for n, a in enumerate(lote, 1)
        )
        mensaje = (
            f"Tema del artículo: {spec.titulo}\nObjetivo: {spec.objetivo}\n\n"
            f"Preguntas de investigación:\n{preguntas}\n\n"
            f"Valora la relevancia de cada uno de estos artículos:\n\n{lista}"
        )
        return self.ask(mensaje, Valoraciones).valoraciones


def _sin_repetir(fuentes: list[FuenteSeleccionada]) -> list[FuenteSeleccionada]:
    """El LLM puede valorar dos veces el mismo índice: nos quedamos con la primera."""
    unicas: dict[str, FuenteSeleccionada] = {}
    for f in fuentes:
        unicas.setdefault(f.articulo.id, f)
    return list(unicas.values())
