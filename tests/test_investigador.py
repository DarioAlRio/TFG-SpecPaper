"""Tests del Investigador y de la búsqueda de fuentes (sin red ni LLM real)."""

import json
import urllib.error

from articulos_ia.agents import Investigador
from articulos_ia.fuentes import Articulo, buscar, parse_arxiv, parse_semantic_scholar

from .conftest import FakeLLM

ARXIV_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2508.08322v1</id>
    <published>2025-08-09T14:45:53Z</published>
    <title>Context Engineering for
      Multi-Agent LLM Code Assistants</title>
    <summary>  Large Language Models have shown promise.  </summary>
    <author><name>Ana Perez</name></author>
    <author><name>Bo Li</name></author>
    <arxiv:doi>10.1000/xyz</arxiv:doi>
  </entry>
</feed>"""


def articulo(n: int, titulo: str | None = None) -> Articulo:
    return Articulo(
        id=f"arxiv:{n}",
        titulo=titulo or f"Paper {n}",
        autores=["A"],
        anio=2024,
        resumen=f"Abstract {n}",
        url=f"https://arxiv.org/abs/{n}",
        fuente="arxiv",
    )


def test_parse_arxiv():
    [a] = parse_arxiv(ARXIV_XML)
    assert a.id == "arxiv:2508.08322"  # sin la versión
    assert a.titulo == "Context Engineering for Multi-Agent LLM Code Assistants"
    assert a.autores == ["Ana Perez", "Bo Li"]
    assert a.anio == 2025
    assert a.resumen == "Large Language Models have shown promise."
    assert a.doi == "10.1000/xyz"


def test_parse_semantic_scholar_descarta_los_que_no_tienen_resumen():
    data = {
        "data": [
            {
                "paperId": "abc",
                "title": "T",
                "authors": [{"name": "X"}],
                "year": 2023,
                "abstract": "Algo",
                "url": None,
                "externalIds": {"DOI": "10.1/2"},
            },
            {"paperId": "def", "title": "Sin resumen", "abstract": None},
        ]
    }
    [a] = parse_semantic_scholar(json.dumps(data).encode())
    assert a.id == "s2:abc" and a.doi == "10.1/2"
    assert a.url.endswith("/paper/abc")


def test_buscar_quita_duplicados_y_sigue_si_un_buscador_falla():
    def falla(consulta, n):
        raise urllib.error.URLError("sin red")

    def bueno(consulta, n):
        return [articulo(1, "Same Title"), articulo(2, "same title!"), articulo(3)]

    resultado = buscar(["q1", "q2"], [falla, bueno])
    assert [a.id for a in resultado] == ["arxiv:1", "arxiv:3"]


def test_investigador_selecciona_las_relevantes(spec):
    encontrados = [articulo(n) for n in range(1, 8)]  # 7 artículos: 2 lotes (5 + 2)
    llm = FakeLLM(
        json.dumps({"consultas": ["multi-agent LLM", "code verification"]}),
        json.dumps(
            {
                "valoraciones": [
                    {"indice": 1, "puntuacion": 2, "motivo": "útil", "preguntas": [1]},
                    {"indice": 2, "puntuacion": 0, "motivo": "no", "preguntas": []},
                    {"indice": 3, "puntuacion": 3, "motivo": "clave", "preguntas": [2]},
                    {"indice": 3, "puntuacion": 3, "motivo": "repetido", "preguntas": [2]},
                    {"indice": 99, "puntuacion": 3, "motivo": "no existe", "preguntas": []},
                ]
            }
        ),
        json.dumps(
            {
                "valoraciones": [
                    {"indice": 2, "puntuacion": 3, "motivo": "clave", "preguntas": [3]},
                ]
            }
        ),
    )
    consultas_recibidas = []

    def buscador(consulta, n):
        consultas_recibidas.append(consulta)
        return encontrados if consulta == "multi-agent LLM" else []

    investigacion = Investigador(llm, [buscador], max_fuentes=10).run(spec)

    assert consultas_recibidas == ["multi-agent LLM", "code verification"]
    assert investigacion.encontrados == 7
    # Ordenadas por puntuación, sin repetidas, sin las de puntuación < 2 ni índices inválidos
    assert [f.articulo.id for f in investigacion.fuentes] == ["arxiv:3", "arxiv:7", "arxiv:1"]
    assert "Abstract 6" in llm.calls[2][1]["content"]  # el segundo lote empieza en el 6
    assert "Paper 7" in investigacion.to_markdown()


def test_investigador_respeta_max_fuentes(spec):
    llm = FakeLLM(
        json.dumps({"consultas": ["q"]}),
        json.dumps(
            {
                "valoraciones": [
                    {"indice": i, "puntuacion": 3, "motivo": "m", "preguntas": [1]}
                    for i in range(1, 4)
                ]
            }
        ),
    )
    investigacion = Investigador(
        llm, [lambda c, n: [articulo(i) for i in range(1, 4)]], max_fuentes=2
    ).run(spec)
    assert len(investigacion.fuentes) == 2
