"""Tests de los Revisores y del bucle de revisión (con el LLM falso de conftest.py)."""

import json

import pytest

from articulos_ia.agents import (
    Borrador,
    Esquema,
    Redactor,
    RevisorCalidad,
    RevisorContexto,
    RevisorFormato,
    revisar_borrador,
)
from articulos_ia.agents.planificador import SeccionPlan
from articulos_ia.agents.redactor import SeccionRedactada
from articulos_ia.agents.revisor import Revision

from .conftest import FakeLLM

SIN_PROBLEMAS = json.dumps({"problemas": []})
SOLO_LEVE = json.dumps(
    {"problemas": [{"gravedad": "baja", "descripcion": "estilo", "sugerencia": "pulir"}]}
)
GRAVE = json.dumps(
    {"problemas": [{"gravedad": "alta", "descripcion": "fuera de tema", "sugerencia": "centrar"}]}
)


@pytest.fixture
def esquema() -> Esquema:
    plan = SeccionPlan(titulo="Intro", objetivo="O", puntos_clave=["p"], preguntas=[1], palabras=4)
    return Esquema(
        titulo="T", resumen="R", secciones=[plan, plan.model_copy(update={"titulo": "Fin"})]
    )


@pytest.fixture
def borrador() -> Borrador:
    return Borrador(
        titulo="T",
        resumen="R",
        secciones=[
            SeccionRedactada(titulo="Intro", texto="uno dos [CITA: x]"),
            SeccionRedactada(titulo="Fin", texto="final"),
        ],
    )


def test_revision_aprobada_ignora_problemas_leves():
    assert Revision.model_validate_json(SOLO_LEVE).aprobada
    assert not Revision.model_validate_json(GRAVE).aprobada


def test_revisor_formato_recibe_datos_medidos(spec, esquema):
    llm = FakeLLM(SIN_PROBLEMAS)
    RevisorFormato(llm).run(spec, esquema, 0, "uno dos [CITA: x]")
    mensaje = llm.calls[0][1]["content"]
    assert "tiene 4 palabras (objetivo: unas 4)" in mensaje
    assert "1 marcas [CITA" in mensaje


def test_revisor_contexto_recibe_seccion_anterior(spec, esquema):
    llm = FakeLLM(SIN_PROBLEMAS)
    RevisorContexto(llm).run(spec, esquema, 1, "final", previa="texto previo")
    assert "texto previo" in llm.calls[0][1]["content"]


def test_cada_revisor_usa_su_prompt(spec, esquema):
    prompts = set()
    for cls in (RevisorFormato, RevisorContexto, RevisorCalidad):
        llm = FakeLLM(SIN_PROBLEMAS)
        cls(llm).run(spec, esquema, 0, "texto")
        prompts.add(llm.calls[0][0]["content"])
    assert len(prompts) == 3


def test_bucle_no_corrige_si_todo_esta_bien(spec, esquema, borrador):
    redactor_llm = FakeLLM()
    revisores = [
        RevisorFormato(FakeLLM(SIN_PROBLEMAS, SOLO_LEVE)),
        RevisorCalidad(FakeLLM(SIN_PROBLEMAS, SIN_PROBLEMAS)),
    ]

    revisado, registro = revisar_borrador(
        spec, esquema, borrador, Redactor(redactor_llm), revisores
    )

    assert revisado == borrador
    assert redactor_llm.calls == []
    assert len(registro) == 4  # 2 secciones x 2 revisores x 1 ronda


def seguimiento(*resueltos: bool, nuevos: list | None = None) -> str:
    estados = [{"indice": n, "resuelto": r} for n, r in enumerate(resueltos, 1)]
    return json.dumps({"estados": estados, "nuevos": nuevos or []})


def test_bucle_corrige_y_comprueba_los_problemas_anteriores(spec, esquema, borrador):
    redactor_llm = FakeLLM("Intro corregida.")
    # Sección 1: grave en la ronda 0, resuelto en la 1. Sección 2: bien a la primera.
    revisor_llm = FakeLLM(GRAVE, seguimiento(True), SIN_PROBLEMAS)
    revisor = RevisorContexto(revisor_llm)

    revisado, registro = revisar_borrador(
        spec, esquema, borrador, Redactor(redactor_llm), [revisor]
    )

    assert revisado.secciones[0].texto == "Intro corregida."
    assert revisado.secciones[1].texto == "final"
    assert [(r.seccion, r.ronda) for r in registro] == [("Intro", 0), ("Intro", 1), ("Fin", 0)]
    assert registro[1].problemas == [] and len(registro[1].resueltos) == 1
    correccion = redactor_llm.calls[0][1]["content"]
    assert "fuera de tema" in correccion and "uno dos [CITA: x]" in correccion
    # En la ronda de seguimiento el revisor recibe su problema anterior y la versión corregida
    comprobacion = revisor_llm.calls[1][1]["content"]
    assert "1. (alta) fuera de tema" in comprobacion and "Intro corregida." in comprobacion
    assert "ronda de seguimiento" in comprobacion


def test_seguimiento_solo_admite_nuevos_problemas_graves(spec, esquema):
    from articulos_ia.agents.revisor import Problema

    anteriores = [
        Problema(gravedad="media", descripcion="a", sugerencia="x"),
        Problema(gravedad="alta", descripcion="b", sugerencia="y"),
        Problema(gravedad="media", descripcion="c", sugerencia="z"),
    ]
    nuevos = [
        {"gravedad": "alta", "descripcion": "rompe algo", "sugerencia": "s"},
        {"gravedad": "media", "descripcion": "otra crítica", "sugerencia": "s"},
    ]
    # Resuelve el 1; dice que el 2 no; no dice nada del 3 (se considera abierto)
    llm = FakeLLM(
        json.dumps(
            {
                "estados": [{"indice": 1, "resuelto": True}, {"indice": 2, "resuelto": False}],
                "nuevos": nuevos,
            }
        )
    )
    abiertos, resueltos = RevisorCalidad(llm).comprobar(spec, esquema, 0, "t", None, anteriores)

    assert [p.descripcion for p in resueltos] == ["a"]
    assert [p.descripcion for p in abiertos] == ["b", "c", "rompe algo"]


def test_bucle_respeta_el_maximo_de_rondas(spec, esquema, borrador):
    redactor_llm = FakeLLM("v1", "v2")
    revisor = RevisorCalidad(FakeLLM(GRAVE, seguimiento(False), seguimiento(False), SIN_PROBLEMAS))

    revisado, registro = revisar_borrador(
        spec, esquema, borrador, Redactor(redactor_llm), [revisor], max_rondas=2
    )

    assert len(redactor_llm.calls) == 2  # 2 correcciones y no más
    assert revisado.secciones[0].texto == "v2"
    assert [r.ronda for r in registro if r.seccion == "Intro"] == [0, 1, 2]
