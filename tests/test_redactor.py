"""Tests del Redactor (con el LLM falso de conftest.py)."""

import pytest

from articulos_ia.agents import Borrador, Esquema, Redactor
from articulos_ia.agents.base import AgentError
from articulos_ia.agents.planificador import SeccionPlan
from articulos_ia.agents.redactor import quitar_titulo

from .conftest import FakeLLM


@pytest.fixture
def esquema() -> Esquema:
    return Esquema(
        titulo="T",
        resumen="R",
        secciones=[
            SeccionPlan(
                titulo="Introducción",
                objetivo="Presentar el tema",
                puntos_clave=["contexto"],
                preguntas=[1, 99],  # 99 no existe: debe ignorarse
                palabras=300,
            ),
            SeccionPlan(
                titulo="Conclusiones",
                objetivo="Cerrar",
                puntos_clave=["resumen"],
                preguntas=[3],
                palabras=200,
            ),
        ],
    )


def test_redactor_escribe_cada_seccion(spec, esquema):
    llm = FakeLLM("Texto de la introducción.", "## Conclusiones\n\nTexto final.")
    borrador = Redactor(llm).run(spec, esquema)

    assert isinstance(borrador, Borrador)
    assert [s.titulo for s in borrador.secciones] == ["Introducción", "Conclusiones"]
    assert borrador.secciones[1].texto == "Texto final."  # sin el título repetido
    assert len(llm.calls) == 2


def test_redactor_pasa_contexto_de_la_seccion(spec, esquema):
    llm = FakeLLM("Texto de la introducción.", "Texto final.")
    Redactor(llm).run(spec, esquema)

    primera = llm.calls[0][1]["content"]
    assert "Sección: 1. Introducción" in primera
    assert spec.preguntas_investigacion[0] in primera
    assert "sección anterior" not in primera

    segunda = llm.calls[1][1]["content"]
    assert "Texto de la introducción." in segunda  # continuidad con la anterior
    assert spec.preguntas_investigacion[2] in segunda


def test_redactor_avisa_del_progreso(spec, esquema):
    vistas = []
    Redactor(FakeLLM("a", "b")).run(spec, esquema, on_section=lambda i, s: vistas.append(i))
    assert vistas == [0, 1]


def test_redactor_reintenta_si_la_respuesta_esta_vacia(spec, esquema):
    llm = FakeLLM("  ", "Texto.", "Final.")
    borrador = Redactor(llm).run(spec, esquema)
    assert borrador.secciones[0].texto == "Texto."
    assert len(llm.calls) == 3


def test_redactor_falla_si_siempre_esta_vacia(spec, esquema):
    with pytest.raises(AgentError):
        Redactor(FakeLLM("", "", "")).run(spec, esquema)


def test_borrador_a_markdown(spec, esquema):
    md = Redactor(FakeLLM("Uno.", "Dos.")).run(spec, esquema).to_markdown()
    assert md.startswith("# T\n")
    assert "## Introducción\n\nUno." in md
    assert "## Conclusiones\n\nDos." in md


def test_quitar_titulo_solo_quita_el_encabezado_inicial():
    assert quitar_titulo("Texto\n\n### Sub\n\nMás") == "Texto\n\n### Sub\n\nMás"
    assert quitar_titulo("# Intro\nTexto") == "Texto"
