"""Agentes Revisores: critican cada sección desde un aspecto distinto (formato, contexto y
calidad). Si encuentran problemas importantes, el Redactor corrige la sección y se vuelve a
revisar, hasta un máximo de rondas.

En la primera ronda cada revisor busca problemas. En las siguientes solo comprueba si se han
resuelto los que señaló (y puede añadir alguno nuevo, pero solo si es grave): si volviera a
revisar desde cero, un modelo pequeño encontraría siempre algo distinto y el bucle no acabaría.
"""

from collections.abc import Callable
from importlib.resources import files
from typing import Literal

from pydantic import BaseModel, Field

from articulos_ia.agents.base import Agent
from articulos_ia.agents.planificador import Esquema
from articulos_ia.agents.redactor import Borrador, Redactor, SeccionRedactada, encargo_seccion
from articulos_ia.spec import ArticleSpec

GRAVES = ("alta", "media")  # las de gravedad "baja" no obligan a corregir


class Problema(BaseModel):
    gravedad: Literal["alta", "media", "baja"]
    descripcion: str = Field(description="Qué falla, citando el fragmento afectado si es posible")
    sugerencia: str = Field(description="Cómo corregirlo, de forma concreta")


class Revision(BaseModel):
    problemas: list[Problema] = Field(description="Lista vacía si la sección es correcta")

    @property
    def aprobada(self) -> bool:
        return not any(p.gravedad in GRAVES for p in self.problemas)


class EstadoProblema(BaseModel):
    indice: int = Field(description="Número del problema en la lista de la ronda anterior")
    resuelto: bool


class Seguimiento(BaseModel):
    estados: list[EstadoProblema] = Field(description="Uno por cada problema de la ronda anterior")
    nuevos: list[Problema] = Field(
        description="Solo problemas nuevos de gravedad alta; normalmente, lista vacía"
    )


class Revisor(Agent):
    """Base de los revisores: cada uno tiene su propio system prompt y, si lo necesita,
    datos adicionales calculados por código (`_datos`)."""

    def run(
        self, spec: ArticleSpec, esquema: Esquema, i: int, texto: str, previa: str | None = None
    ) -> Revision:
        partes = self._partes(spec, esquema, i, texto, previa)
        return self.ask("\n\n".join(partes), Revision)

    def comprobar(
        self,
        spec: ArticleSpec,
        esquema: Esquema,
        i: int,
        texto: str,
        previa: str | None,
        anteriores: list[Problema],
    ) -> tuple[list[Problema], list[Problema]]:
        """Comprueba si la versión corregida resuelve los problemas `anteriores`.
        Devuelve (problemas que siguen abiertos, problemas resueltos)."""
        lista = "\n".join(
            f"{n}. ({p.gravedad}) {p.descripcion} Sugerencia: {p.sugerencia}"
            for n, p in enumerate(anteriores, 1)
        )
        partes = self._partes(spec, esquema, i, texto, previa)
        partes += [f"Problemas que señalaste en la ronda anterior:\n{lista or '(ninguno)'}"]
        partes += [_instrucciones_seguimiento()]
        seguimiento = self.ask("\n\n".join(partes), Seguimiento)

        # Si el modelo no dice nada de un problema, se considera que sigue abierto.
        resueltos_idx = {e.indice for e in seguimiento.estados if e.resuelto}
        abiertos = [p for n, p in enumerate(anteriores, 1) if n not in resueltos_idx]
        resueltos = [p for n, p in enumerate(anteriores, 1) if n in resueltos_idx]
        nuevos = [p for p in seguimiento.nuevos if p.gravedad == "alta"]
        return abiertos + nuevos, resueltos

    def _partes(
        self, spec: ArticleSpec, esquema: Esquema, i: int, texto: str, previa: str | None
    ) -> list[str]:
        return [
            encargo_seccion(spec, esquema, i),
            *self._datos(esquema, i, texto, previa),
            f"Texto de la sección a revisar:\n\n{texto}",
        ]

    def _datos(self, esquema: Esquema, i: int, texto: str, previa: str | None) -> list[str]:
        return []


def _instrucciones_seguimiento() -> str:
    return (
        files("articulos_ia.prompts").joinpath("revisor_seguimiento.md").read_text(encoding="utf-8")
    )


class RevisorFormato(Revisor):
    name = "revisor_formato"

    def _datos(self, esquema, i, texto, previa):
        # Un modelo pequeño no sabe contar palabras: se lo damos ya calculado.
        objetivo = esquema.secciones[i].palabras
        return [
            f"Datos medidos: la sección tiene {len(texto.split())} palabras "
            f"(objetivo: unas {objetivo}) y {texto.count('[CITA')} marcas [CITA: ...]."
        ]


class RevisorContexto(Revisor):
    name = "revisor_contexto"
    contexto_previo: int = 1500

    def _datos(self, esquema, i, texto, previa):
        if not previa:
            return []
        return [f"Final de la sección anterior:\n...{previa[-self.contexto_previo :]}"]


class RevisorCalidad(Revisor):
    name = "revisor_calidad"


class RegistroRevision(BaseModel):
    """Lo que dijo un revisor sobre una sección en una ronda (para analizar el proceso)."""

    seccion: str
    ronda: int
    revisor: str
    problemas: list[Problema]  # abiertos tras esta ronda
    resueltos: list[Problema] = []  # de la ronda anterior, ya resueltos (rondas > 0)


def revisar_borrador(
    spec: ArticleSpec,
    esquema: Esquema,
    borrador: Borrador,
    redactor: Redactor,
    revisores: list[Revisor],
    max_rondas: int = 2,
    on_event: Callable[[RegistroRevision], None] | None = None,
) -> tuple[Borrador, list[RegistroRevision]]:
    """Revisa cada sección con todos los revisores y la manda corregir mientras haya
    problemas graves. `max_rondas` es el número máximo de correcciones por sección."""
    secciones: list[SeccionRedactada] = []
    registro: list[RegistroRevision] = []
    for i, seccion in enumerate(borrador.secciones):
        texto = seccion.texto
        previa = secciones[-1].texto if secciones else None
        abiertos: dict[str, list[Problema]] = {}  # problemas graves de cada revisor
        for ronda in range(max_rondas + 1):
            a_corregir = []
            for revisor in revisores:
                if ronda == 0:
                    problemas = revisor.run(spec, esquema, i, texto, previa).problemas
                    resueltos = []
                else:
                    problemas, resueltos = revisor.comprobar(
                        spec, esquema, i, texto, previa, abiertos[revisor.name]
                    )
                abiertos[revisor.name] = [p for p in problemas if p.gravedad in GRAVES]
                entrada = RegistroRevision(
                    seccion=seccion.titulo,
                    ronda=ronda,
                    revisor=revisor.name,
                    problemas=problemas,
                    resueltos=resueltos,
                )
                registro.append(entrada)
                if on_event:
                    on_event(entrada)
                a_corregir += [
                    f"({revisor.name}, {p.gravedad}) {p.descripcion} Sugerencia: {p.sugerencia}"
                    for p in abiertos[revisor.name]
                ]
            if not a_corregir or ronda == max_rondas:
                break
            texto = redactor.corregir(spec, esquema, i, texto, a_corregir)
        secciones.append(SeccionRedactada(titulo=seccion.titulo, texto=texto))
    revisado = borrador.model_copy(update={"secciones": secciones})
    return revisado, registro
