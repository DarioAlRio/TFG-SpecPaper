"""Línea de comandos.

Uso:
    python -m articulos_ia generar specs/ejemplo.yaml      (todo, con el agente Orquestador)
    python -m articulos_ia investigar specs/ejemplo.yaml
    python -m articulos_ia plan specs/ejemplo.yaml
    python -m articulos_ia redactar specs/ejemplo.yaml
    python -m articulos_ia revisar specs/ejemplo.yaml
"""

import argparse
import json
import re
import sys
import time

from articulos_ia.agents import (
    Borrador,
    Esquema,
    Estado,
    Investigador,
    Orquestador,
    Planificador,
    Redactor,
    RevisorCalidad,
    RevisorContexto,
    RevisorFormato,
    revisar_borrador,
)
from articulos_ia.config import Settings, load_settings
from articulos_ia.fuentes import BUSCADORES
from articulos_ia.llm import create_llm
from articulos_ia.spec import ArticleSpec


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60]


def crear_agente(settings: Settings, cls):
    return cls(create_llm(settings.llm_for(cls.name)))


def cmd_generar(args: argparse.Namespace) -> None:
    settings = load_settings(args.config)
    spec = ArticleSpec.from_yaml(args.spec)
    out_dir = settings.output_dir / slug(spec.titulo)
    out_dir.mkdir(parents=True, exist_ok=True)
    estado_file = out_dir / "estado.json"

    if estado_file.exists() and not args.nuevo:
        estado = Estado.model_validate_json(estado_file.read_text(encoding="utf-8"))
        print(f"Reanudando desde el paso {len(estado.historial)}...", file=sys.stderr)
    else:
        estado = Estado(spec=spec)

    orquestador = Orquestador(
        create_llm(settings.llm_for("orquestador")),
        planificador=crear_agente(settings, Planificador),
        redactor=crear_agente(settings, Redactor),
        revisores=[
            crear_agente(settings, c) for c in (RevisorFormato, RevisorContexto, RevisorCalidad)
        ],
        max_pasos=settings.max_pasos_orquestador,
    )

    def guardar(e: Estado) -> None:
        estado_file.write_text(e.model_dump_json(indent=2), encoding="utf-8")

    def progreso(p) -> None:
        seccion = f" {p.seccion}" if p.seccion else ""
        print(
            f"  {p.numero}. {p.accion}{seccion} ({p.segundos:.0f} s): {p.razonamiento}",
            file=sys.stderr,
        )
        print(f"     → {p.resultado}", file=sys.stderr)

    start = time.perf_counter()
    estado = orquestador.run(estado, guardar=guardar, on_paso=progreso)
    elapsed = time.perf_counter() - start

    rechazadas = sum(p.rechazada for p in estado.historial)
    print(
        f"\nFin: {estado.motivo_fin}\n{len(estado.historial)} pasos ({rechazadas} rechazados), "
        f"{elapsed:.1f} s. Estado en {estado_file}",
        file=sys.stderr,
    )
    if estado.borrador:
        out_file = out_dir / "articulo.md"
        out_file.write_text(estado.borrador.to_markdown(), encoding="utf-8")
        print(f"Artículo en {out_file}", file=sys.stderr)


def cmd_investigar(args: argparse.Namespace) -> None:
    settings = load_settings(args.config)
    spec = ArticleSpec.from_yaml(args.spec)
    conf = settings.investigacion
    llm_config = settings.llm_for("investigador")
    print(f"Investigando con {llm_config.model} en {conf.buscadores}...", file=sys.stderr)

    investigador = Investigador(
        create_llm(llm_config),
        buscadores=[BUSCADORES[b] for b in conf.buscadores],
        resultados_por_consulta=conf.resultados_por_consulta,
        max_fuentes=conf.max_fuentes,
    )
    start = time.perf_counter()
    investigacion = investigador.run(spec, on_progress=lambda m: print(f"  {m}", file=sys.stderr))
    elapsed = time.perf_counter() - start

    out_dir = settings.output_dir / slug(spec.titulo)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "fuentes.json").write_text(investigacion.model_dump_json(indent=2), encoding="utf-8")
    out_file = out_dir / "fuentes.md"
    out_file.write_text(investigacion.to_markdown(), encoding="utf-8")
    print(investigacion.to_markdown())
    print(
        f"{len(investigacion.fuentes)} de {investigacion.encontrados} artículos seleccionados. "
        f"Guardado en {out_file} ({elapsed:.1f} s)",
        file=sys.stderr,
    )


def cmd_plan(args: argparse.Namespace) -> None:
    settings = load_settings(args.config)
    spec = ArticleSpec.from_yaml(args.spec)
    llm_config = settings.llm_for("planificador")
    print(f"Planificando con {llm_config.model}...", file=sys.stderr)

    start = time.perf_counter()
    esquema = Planificador(create_llm(llm_config)).run(spec)
    elapsed = time.perf_counter() - start

    out_dir = settings.output_dir / slug(spec.titulo)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "esquema.json"
    out_file.write_text(esquema.model_dump_json(indent=2), encoding="utf-8")

    print(f"\n# {esquema.titulo}\n\n{esquema.resumen}\n")
    for i, s in enumerate(esquema.secciones, 1):
        print(f"{i}. {s.titulo} (~{s.palabras} palabras, preguntas {s.preguntas})")
        for p in s.puntos_clave:
            print(f"   - {p}")
    print(f"\nGuardado en {out_file} ({elapsed:.1f} s)", file=sys.stderr)


def cmd_redactar(args: argparse.Namespace) -> None:
    settings = load_settings(args.config)
    spec = ArticleSpec.from_yaml(args.spec)
    out_dir = settings.output_dir / slug(spec.titulo)
    esquema_file = out_dir / "esquema.json"
    if not esquema_file.exists():
        cmd_plan(args)
    esquema = Esquema.model_validate_json(esquema_file.read_text(encoding="utf-8"))

    llm_config = settings.llm_for("redactor")
    print(
        f"Redactando {len(esquema.secciones)} secciones con {llm_config.model}...", file=sys.stderr
    )

    def progreso(i: int, seccion) -> None:
        palabras = len(seccion.texto.split())
        print(f"  {i + 1}. {seccion.titulo} ({palabras} palabras)", file=sys.stderr)

    start = time.perf_counter()
    borrador = Redactor(create_llm(llm_config)).run(spec, esquema, on_section=progreso)
    elapsed = time.perf_counter() - start

    (out_dir / "borrador.json").write_text(borrador.model_dump_json(indent=2), encoding="utf-8")
    out_file = out_dir / "borrador.md"
    out_file.write_text(borrador.to_markdown(), encoding="utf-8")
    print(f"\nGuardado en {out_file} ({elapsed:.1f} s)", file=sys.stderr)


def cmd_revisar(args: argparse.Namespace) -> None:
    settings = load_settings(args.config)
    spec = ArticleSpec.from_yaml(args.spec)
    out_dir = settings.output_dir / slug(spec.titulo)
    borrador_file = out_dir / "borrador.json"
    if not borrador_file.exists():
        cmd_redactar(args)
    esquema = Esquema.model_validate_json((out_dir / "esquema.json").read_text(encoding="utf-8"))
    borrador = Borrador.model_validate_json(borrador_file.read_text(encoding="utf-8"))

    def agente(cls):
        return crear_agente(settings, cls)

    revisores = [agente(RevisorFormato), agente(RevisorContexto), agente(RevisorCalidad)]
    print(f"Revisando {len(borrador.secciones)} secciones...", file=sys.stderr)

    def progreso(r) -> None:
        graves = sum(p.gravedad != "baja" for p in r.problemas)
        resueltos = f", {len(r.resueltos)} resueltos" if r.ronda else ""
        print(
            f"  {r.seccion} · ronda {r.ronda} · {r.revisor}: {graves} a corregir{resueltos}",
            file=sys.stderr,
        )

    start = time.perf_counter()
    revisado, registro = revisar_borrador(
        spec,
        esquema,
        borrador,
        agente(Redactor),
        revisores,
        max_rondas=settings.max_rondas_revision,
        on_event=progreso,
    )
    elapsed = time.perf_counter() - start

    (out_dir / "revision.json").write_text(
        json.dumps([r.model_dump() for r in registro], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    out_file = out_dir / "revisado.md"
    out_file.write_text(revisado.to_markdown(), encoding="utf-8")
    print(f"\nGuardado en {out_file} ({elapsed:.1f} s)", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(prog="articulos_ia")
    parser.add_argument("--config", default="config.yaml")
    sub = parser.add_subparsers(required=True)

    generar = sub.add_parser(
        "generar", help="El agente Orquestador genera el artículo completo (reanuda si se cortó)"
    )
    generar.add_argument("spec")
    generar.add_argument("--nuevo", action="store_true", help="Empieza de cero")
    generar.set_defaults(func=cmd_generar)

    investigar = sub.add_parser("investigar", help="Busca artículos reales sobre el tema")
    investigar.add_argument("spec")
    investigar.set_defaults(func=cmd_investigar)

    plan = sub.add_parser("plan", help="Genera el esquema de un artículo a partir de su spec")
    plan.add_argument("spec")
    plan.set_defaults(func=cmd_plan)

    redactar = sub.add_parser(
        "redactar", help="Redacta el borrador (si no hay esquema, lo genera antes)"
    )
    redactar.add_argument("spec")
    redactar.set_defaults(func=cmd_redactar)

    revisar = sub.add_parser(
        "revisar", help="Revisa y corrige el borrador (si no hay borrador, lo genera antes)"
    )
    revisar.add_argument("spec")
    revisar.set_defaults(func=cmd_revisar)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
