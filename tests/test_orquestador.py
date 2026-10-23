"""Tests del agente Orquestador (con LLM falsos para él y para cada agente)."""

import json

from articulos_ia.agents import Estado, Orquestador, Planificador, Redactor, RevisorCalidad
from articulos_ia.agents.orquestador import comprobar_con_codigo, medir

from .conftest import FakeLLM

ESQUEMA = json.dumps(
    {
        "titulo": "T",
        "resumen": "R",
        "secciones": [
            {
                "titulo": "Intro",
                "objetivo": "O",
                "puntos_clave": ["p"],
                "preguntas": [1],
                "palabras": 4,
            },
            {
                "titulo": "Fin",
                "objetivo": "O",
                "puntos_clave": ["p"],
                "preguntas": [2],
                "palabras": 4,
            },
        ],
    }
)
SIN_PROBLEMAS = json.dumps({"problemas": []})
GRAVE = json.dumps(
    {"problemas": [{"gravedad": "media", "descripcion": "flojo", "sugerencia": "mejorar"}]}
)
RESUELTO = json.dumps({"estados": [{"indice": 1, "resuelto": True}], "nuevos": []})


def decision(accion: str, seccion: int | None = None) -> str:
    return json.dumps({"razonamiento": "porque sí", "accion": accion, "seccion": seccion})


def orquestador(decisiones, redactor=(), revisor=(), max_pasos=40):
    return Orquestador(
        FakeLLM(*decisiones),
        planificador=Planificador(FakeLLM(ESQUEMA)),
        redactor=Redactor(FakeLLM(*redactor)),
        revisores=[RevisorCalidad(FakeLLM(*revisor))],
        max_pasos=max_pasos,
    )


def test_ciclo_completo_con_correccion(spec):
    orq = orquestador(
        [
            decision("planificar"),
            decision("redactar"),
            decision("revisar_seccion", 1),
            decision("corregir_seccion", 1),
            decision("revisar_seccion", 1),
            decision("revisar_seccion", 2),
            decision("terminar"),
        ],
        redactor=["uno dos tres cuatro", "cinco seis siete ocho", "uno dos tres nuevo"],
        revisor=[GRAVE, RESUELTO, SIN_PROBLEMAS],
    )
    guardados = []
    estado = orq.run(Estado(spec=spec), guardar=lambda e: guardados.append(len(e.historial)))

    assert estado.terminado and estado.motivo_fin == "porque sí"
    assert [p.accion for p in estado.historial][:2] == ["planificar", "redactar"]
    assert not any(p.rechazada for p in estado.historial)
    assert estado.borrador.secciones[0].texto == "uno dos tres nuevo"
    assert estado.secciones[0].correcciones == 1
    assert "1 resueltos" in estado.historial[4].resultado  # ronda de seguimiento
    assert guardados[:7] == [1, 2, 3, 4, 5, 6, 7]  # se guarda tras cada paso


def test_lo_que_ve_el_orquestador(spec):
    llm = FakeLLM(decision("planificar"), decision("redactar"), decision("terminar"))
    orq = Orquestador(
        llm,
        planificador=Planificador(FakeLLM(ESQUEMA)),
        redactor=Redactor(FakeLLM("uno dos tres cuatro", "texto [1] con cita inventada")),
        revisores=[],
    )
    orq.run(Estado(spec=spec))

    primero = llm.calls[0][1]["content"]
    assert "Pasos usados: 0 de 40" in primero and "Esquema: todavía no hay" in primero
    tercero = llm.calls[2][1]["content"]
    assert "1. Intro: 4 palabras (objetivo 4), 0 marcas [CITA]; sin revisar" in tercero
    assert "CONTIENE REFERENCIAS INVENTADAS" in tercero
    assert "Paso 2: redactar → borrador de 9 palabras" in tercero


def test_rechaza_acciones_sin_sentido(spec):
    orq = orquestador(
        [
            decision("redactar"),  # sin esquema
            decision("terminar"),  # sin borrador
            decision("planificar"),
            decision("redactar"),
            decision("corregir_seccion", 1),  # sin revisar
            decision("revisar_seccion", 7),  # no existe
            decision("revisar_seccion", 1),
            decision("revisar_seccion", 1),  # no ha cambiado
            decision("corregir_seccion", 1),  # sin problemas graves
            decision("terminar"),
        ],
        redactor=["uno dos tres cuatro", "cinco seis siete ocho"],
        revisor=[SIN_PROBLEMAS],
    )
    estado = orq.run(Estado(spec=spec))

    rechazos = [p.resultado for p in estado.historial if p.rechazada]
    assert rechazos == [
        "RECHAZADA: no hay esquema; primero hay que planificar",
        "RECHAZADA: todavía no hay borrador",
        "RECHAZADA: hay que revisarla antes de corregirla",
        "RECHAZADA: indica una sección entre 1 y 2",
        "RECHAZADA: ya está revisada y no ha cambiado desde entonces",
        "RECHAZADA: no tiene problemas graves abiertos",
    ]
    assert estado.terminado


def test_limite_de_pasos(spec):
    orq = orquestador([decision("planificar")] * 3, max_pasos=3)
    orq.planificador = Planificador(FakeLLM(ESQUEMA, ESQUEMA, ESQUEMA))
    estado = orq.run(Estado(spec=spec))
    assert len(estado.historial) == 3
    assert estado.motivo_fin == "Se alcanzó el límite de 3 pasos"


def test_reanuda_desde_un_estado_guardado(spec):
    primero = orquestador([decision("planificar")], max_pasos=1)
    guardado = primero.run(Estado(spec=spec)).model_dump_json()

    # Simula un corte: se carga el estado guardado y se continúa con un límite mayor
    estado = Estado.model_validate_json(guardado)
    estado.terminado, estado.motivo_fin = False, None
    segundo = orquestador(
        [decision("redactar"), decision("terminar")], redactor=["uno dos tres cuatro", "a b c d"]
    )
    estado = segundo.run(estado)
    assert [p.accion for p in estado.historial] == ["planificar", "redactar", "terminar"]


def test_medir_detecta_referencias_inventadas():
    assert not medir("Texto con [CITA: algo] normal (en 2023).").referencias_inventadas
    assert medir("Según estudios [3], esto es así.").referencias_inventadas
    assert medir("Como dice (García, 2021) en su trabajo.").referencias_inventadas
    assert medir("Texto.\n\n### Referencias\n1. Li (2023)").referencias_inventadas


def test_comprobaciones_con_codigo():
    assert comprobar_con_codigo("uno dos tres cuatro", 4) == []
    [extension] = comprobar_con_codigo("palabra " * 10, 4)
    assert extension.gravedad == "media" and "+150%" in extension.descripcion
    problemas = comprobar_con_codigo("uno dos tres [1]", 4)
    assert [p.gravedad for p in problemas] == ["alta"]


def test_revisar_incluye_las_comprobaciones_del_codigo(spec):
    orq = orquestador(
        [
            decision("planificar"),
            decision("redactar"),
            decision("revisar_seccion", 1),
            decision("corregir_seccion", 1),
            decision("terminar"),
        ],
        redactor=["muchas " * 20, "uno dos tres cuatro", "corto ya del todo"],
        revisor=[SIN_PROBLEMAS],
    )
    estado = orq.run(Estado(spec=spec))
    # El revisor (LLM) no vio problemas, pero el código sí (extensión): se puede corregir
    assert "codigo 1" in estado.historial[2].resultado
    assert not estado.historial[3].rechazada
    corregir = orq.redactor.llm.calls[2][1]["content"]
    assert "(codigo, media)" in corregir and "Acórtala" in corregir
