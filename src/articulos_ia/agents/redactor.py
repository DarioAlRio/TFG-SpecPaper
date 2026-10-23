"""Agente Redactor: escribe el artículo sección a sección siguiendo el esquema."""

import re
from collections.abc import Callable

from pydantic import BaseModel

from articulos_ia.agents.base import Agent
from articulos_ia.agents.planificador import Esquema
from articulos_ia.spec import ArticleSpec


class SeccionRedactada(BaseModel):
    titulo: str
    texto: str


class Borrador(BaseModel):
    titulo: str
    resumen: str
    secciones: list[SeccionRedactada]

    def to_markdown(self) -> str:
        partes = [f"# {self.titulo}", f"**Resumen.** {self.resumen}"]
        partes += [f"## {s.titulo}\n\n{s.texto}" for s in self.secciones]
        return "\n\n".join(partes) + "\n"


class Redactor(Agent):
    name = "redactor"
    contexto_previo: int = 1500  # caracteres del final de la sección anterior que se le pasan

    def run(
        self,
        spec: ArticleSpec,
        esquema: Esquema,
        on_section: Callable[[int, SeccionRedactada], None] | None = None,
    ) -> Borrador:
        secciones: list[SeccionRedactada] = []
        for i, plan in enumerate(esquema.secciones):
            previa = secciones[-1].texto if secciones else None
            texto = self.write(self._mensaje(spec, esquema, i, previa))
            seccion = SeccionRedactada(titulo=plan.titulo, texto=quitar_titulo(texto))
            secciones.append(seccion)
            if on_section:
                on_section(i, seccion)
        return Borrador(titulo=esquema.titulo, resumen=esquema.resumen, secciones=secciones)

    def corregir(
        self, spec: ArticleSpec, esquema: Esquema, i: int, texto: str, problemas: list[str]
    ) -> str:
        """Reescribe la sección `i` resolviendo los problemas señalados por los revisores."""
        mensaje = "\n\n".join(
            [
                encargo_seccion(spec, esquema, i),
                f"Versión actual de la sección:\n\n{texto}",
                "Problemas señalados por los revisores:\n" + "\n".join(f"- {p}" for p in problemas),
                "Reescribe la sección completa corrigiendo estos problemas y conservando "
                "lo que ya estaba bien.",
                # En la prueba del 23/10, al pedirle "más citas" inventó una lista de
                # referencias, y al corregir nunca acortaba la sección.
                f"Recuerda: unas {esquema.secciones[i].palabras} palabras. Si faltan citas, "
                "añade marcas [CITA: ...]; nunca escribas autores, años ni una lista de "
                "referencias.",
            ]
        )
        return quitar_titulo(self.write(mensaje))

    def _mensaje(self, spec: ArticleSpec, esquema: Esquema, i: int, previa: str | None) -> str:
        partes = [encargo_seccion(spec, esquema, i), "Redacta ahora esta sección."]
        if previa:
            partes.append(
                "Final de la sección anterior (continúa a partir de aquí, sin repetirlo):\n"
                f"...{previa[-self.contexto_previo :]}"
            )
        return "\n\n".join(partes)


def encargo_seccion(spec: ArticleSpec, esquema: Esquema, i: int) -> str:
    """Lo que se espera de la sección `i`: la usan el Redactor y los Revisores."""
    plan = esquema.secciones[i]
    indice = "\n".join(f"{n}. {s.titulo}: {s.objetivo}" for n, s in enumerate(esquema.secciones, 1))
    preguntas = [
        spec.preguntas_investigacion[p - 1]
        for p in plan.preguntas
        if 1 <= p <= len(spec.preguntas_investigacion)
    ]
    partes = [
        f"Especificación del artículo:\n\n{spec.to_yaml()}",
        f"Esquema completo:\n{indice}",
        f"Sección: {i + 1}. {plan.titulo}",
        f"Objetivo: {plan.objetivo}",
        "Puntos clave:\n" + "\n".join(f"- {p}" for p in plan.puntos_clave),
    ]
    if preguntas:
        partes.append(
            "Preguntas de investigación que aborda:\n" + "\n".join(f"- {p}" for p in preguntas)
        )
    partes.append(f"Extensión: unas {plan.palabras} palabras.")
    return "\n\n".join(partes)


def quitar_titulo(texto: str) -> str:
    """Quita el encabezado Markdown inicial si el modelo lo ha añadido (lo pone el Borrador)."""
    return re.sub(r"\A\s*#{1,6} [^\n]*\n+", "", texto).strip()
