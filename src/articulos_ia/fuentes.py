"""Búsqueda de artículos científicos en APIs gratuitas (sin IA).

- arXiv: sin clave; pide no hacer más de una petición cada 3 segundos.
- Semantic Scholar: sin clave comparte un cupo con todos los usuarios y suele responder
  429 (demasiadas peticiones). Con la variable de entorno SEMANTIC_SCHOLAR_API_KEY va bien.
"""

import json
import logging
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel

log = logging.getLogger(__name__)

USER_AGENT = "articulos-ia/0.1 (TFG)"


class Articulo(BaseModel):
    id: str  # "arxiv:2508.08322" o "s2:<paperId>"
    titulo: str
    autores: list[str]
    anio: int | None
    resumen: str
    url: str
    fuente: Literal["arxiv", "semantic_scholar"]
    doi: str | None = None


Buscador = Callable[[str, int], list[Articulo]]


def _get(url: str, headers: dict | None = None) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


_ultima_peticion_arxiv = 0.0


def buscar_arxiv(consulta: str, n: int = 10) -> list[Articulo]:
    global _ultima_peticion_arxiv
    espera = 3 - (time.monotonic() - _ultima_peticion_arxiv)
    if espera > 0:
        time.sleep(espera)
    _ultima_peticion_arxiv = time.monotonic()

    # Todas las palabras deben aparecer (AND); arXiv ordena por relevancia.
    palabras = re.findall(r"[\w-]+", consulta)
    query = " AND ".join(f"all:{p}" for p in palabras)
    params = urllib.parse.urlencode(
        {"search_query": query, "max_results": n, "sortBy": "relevance"}
    )
    xml = _get(f"https://export.arxiv.org/api/query?{params}")
    return parse_arxiv(xml)


def parse_arxiv(xml: bytes) -> list[Articulo]:
    ns = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
    articulos = []
    for entry in ET.fromstring(xml).findall("a:entry", ns):
        url = entry.findtext("a:id", "", ns).strip()
        arxiv_id = re.sub(r"v\d+$", "", url.rsplit("/abs/", 1)[-1])
        publicado = entry.findtext("a:published", "", ns)
        articulos.append(
            Articulo(
                id=f"arxiv:{arxiv_id}",
                titulo=" ".join(entry.findtext("a:title", "", ns).split()),
                autores=[a.findtext("a:name", "", ns) for a in entry.findall("a:author", ns)],
                anio=int(publicado[:4]) if publicado[:4].isdigit() else None,
                resumen=" ".join(entry.findtext("a:summary", "", ns).split()),
                url=f"https://arxiv.org/abs/{arxiv_id}",
                fuente="arxiv",
                doi=entry.findtext("arxiv:doi", None, ns),
            )
        )
    return articulos


def buscar_semantic_scholar(consulta: str, n: int = 10, reintentos: int = 2) -> list[Articulo]:
    params = urllib.parse.urlencode(
        {"query": consulta, "limit": n, "fields": "title,authors,year,abstract,url,externalIds"}
    )
    url = f"https://api.semanticscholar.org/graph/v1/paper/search?{params}"
    headers = {}
    if key := os.environ.get("SEMANTIC_SCHOLAR_API_KEY"):
        headers["x-api-key"] = key
    for intento in range(reintentos + 1):
        try:
            return parse_semantic_scholar(_get(url, headers))
        except urllib.error.HTTPError as e:
            if e.code != 429 or intento == reintentos:
                raise
            time.sleep(2 ** (intento + 1))
    return []


def parse_semantic_scholar(data: bytes) -> list[Articulo]:
    articulos = []
    for p in json.loads(data).get("data", []):
        if not p.get("abstract"):
            continue  # sin resumen no se puede valorar su relevancia
        articulos.append(
            Articulo(
                id=f"s2:{p['paperId']}",
                titulo=p["title"],
                autores=[a["name"] for a in p.get("authors", [])],
                anio=p.get("year"),
                resumen=p["abstract"],
                url=p.get("url") or f"https://www.semanticscholar.org/paper/{p['paperId']}",
                fuente="semantic_scholar",
                doi=(p.get("externalIds") or {}).get("DOI"),
            )
        )
    return articulos


BUSCADORES: dict[str, Buscador] = {
    "arxiv": buscar_arxiv,
    "semantic_scholar": buscar_semantic_scholar,
}


def buscar(consultas: list[str], buscadores: list[Buscador], n: int = 10) -> list[Articulo]:
    """Lanza cada consulta en cada buscador y quita duplicados (mismo título).
    Si un buscador falla, lo avisa y sigue con los demás."""
    vistos: dict[str, Articulo] = {}
    for consulta in consultas:
        for buscador in buscadores:
            try:
                resultados = buscador(consulta, n)
            except (urllib.error.URLError, TimeoutError, ET.ParseError, ValueError) as e:
                log.warning("Fallo al buscar %r en %s: %s", consulta, buscador.__name__, e)
                continue
            for articulo in resultados:
                vistos.setdefault(_clave(articulo.titulo), articulo)
    return list(vistos.values())


def _clave(titulo: str) -> str:
    return re.sub(r"[^a-z0-9]", "", titulo.lower())
