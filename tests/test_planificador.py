"""Tests del Planificador (con el LLM falso de conftest.py)."""

import json

import pytest

from articulos_ia.agents import Esquema, Planificador
from articulos_ia.agents.base import AgentError
from articulos_ia.config import load_settings

from .conftest import ROOT, FakeLLM

ESQUEMA_VALIDO = json.dumps(
    {
        "titulo": "T",
        "resumen": "R",
        "secciones": [
            {
                "titulo": "Introducción",
                "objetivo": "Presentar el tema",
                "puntos_clave": ["a", "b"],
                "preguntas": [1],
                "palabras": 500,
            }
        ],
    }
)


def test_carga_spec_de_ejemplo(spec):
    assert len(spec.preguntas_investigacion) == 3
    assert spec.secciones[0] == "Introducción"


def test_planificador_devuelve_esquema(spec):
    llm = FakeLLM(ESQUEMA_VALIDO)
    esquema = Planificador(llm).run(spec)
    assert isinstance(esquema, Esquema)
    assert esquema.secciones[0].titulo == "Introducción"
    assert spec.titulo in llm.calls[0][1]["content"]


def test_planificador_reintenta_si_la_respuesta_no_es_valida(spec):
    llm = FakeLLM('{"titulo": "incompleto"}', ESQUEMA_VALIDO)
    Planificador(llm).run(spec)
    assert len(llm.calls) == 2
    assert "no es válida" in llm.calls[1][-1]["content"]


def test_planificador_falla_tras_agotar_intentos(spec):
    llm = FakeLLM("no es json", "tampoco", "nada")
    with pytest.raises(AgentError):
        Planificador(llm).run(spec)


def test_config_aplica_ajustes_por_agente():
    settings = load_settings(ROOT / "config.yaml")
    assert settings.llm_for("planificador").think is False
    assert settings.llm_for("otro").think is None
