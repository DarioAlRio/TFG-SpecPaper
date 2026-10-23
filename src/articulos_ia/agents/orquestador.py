"""Agente Orquestador: un LLM decide, paso a paso, qué agente actúa a continuación.

En cada paso el Orquestador recibe un resumen del estado del artículo y elige una acción de
una lista cerrada. El código no decide el flujo, pero sí pone los límites:
- comprueba que la acción tenga sentido (por ejemplo, no se puede redactar sin esquema) y,
  si no lo tiene, la rechaza y se lo dice en el siguiente paso;
- limita el número de pasos y de correcciones por sección;
- mide lo que se puede medir (palabras, marcas [CITA], referencias inventadas) y se lo da
  ya calculado;
- guarda el estado tras cada paso, para poder reanudar si algo falla.
"""

import re
import time
from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel, Field

from articulos_ia.agents.base import Agent
from articulos_ia.agents.planificador import Esquema, Planificador
from articulos_ia.agents.redactor import Borrador, Redactor, SeccionRedactada
from articulos_ia.agents.revisor import GRAVES, Problema, RegistroRevision, Revisor
from articulos_ia.spec import ArticleSpec

Accion = Literal["planificar", "redactar", "revisar_seccion", "corregir_seccion", "terminar"]


class Decision(BaseModel):
    razonamiento: str = Field(description="Por qué esta acción ahora, en una o dos frases")
    accion: Accion
    seccion: int | None = Field(
        default=None,
        description="Número de la sección (empezando en 1); solo para revisar_seccion "
        "y corregir_seccion",
    )


class EstadoSeccion(BaseModel):
    revisada: bool = False
    corregida_tras_revision: bool = False  # ha cambiado desde la última revisión
    correcciones: int = 0
    abiertos: dict[str, list[Problema]] = {}  # problemas graves abiertos, por revisor


class Paso(BaseModel):
    numero: int
    accion: Accion
    seccion: int | None
    razonamiento: str
    resultado: str
    rechazada: bool
    segundos: float


class Estado(BaseModel):
    """Todo lo necesario para continuar el trabajo: se guarda tras cada paso."""

    spec: ArticleSpec
    esquema: Esquema | None = None
    borrador: Borrador | None = None
    secciones: list[EstadoSeccion] = []
    historial: list[Paso] = []
    registro_revision: list[RegistroRevision] = []
    terminado: bool = False
    motivo_fin: str | None = None


class Medida(BaseModel):
    palabras: int
    citas: int
    referencias_inventadas: bool


_REFERENCIAS = re.compile(
    r"^#{1,6}\s*(?i:referencias|bibliograf[ií]a|references)"  # una sección de referencias
    r"|\[\d+(?:\s*[,–-]\s*\d+)*\]"  # citas numéricas [1], [2-4]
    r"|\([A-ZÁÉÍÓÚ][\w-]+(?: et al\.)?, (?:19|20)\d{2}\)",  # (Autor, 2023)
    re.MULTILINE,
)
TOLERANCIA_EXTENSION = 0.25


def medir(texto: str) -> Medida:
    """Lo que el código puede comprobar sin preguntar al modelo."""
    return Medida(
        palabras=len(texto.split()),
        citas=texto.count("[CITA"),
        referencias_inventadas=bool(_REFERENCIAS.search(texto)),
    )


def comprobar_con_codigo(texto: str, objetivo: int) -> list[Problema]:
    """Problemas que detecta el código. Se recalculan en cada revisión, así que el modelo no
    puede darlos por resueltos si no lo están."""
    m = medir(texto)
    problemas = []
    if m.referencias_inventadas:
        problemas.append(
            Problema(
                gravedad="alta",
                descripcion="La sección contiene referencias bibliográficas escritas por el "
                "modelo (citas numéricas, (Autor, año) o una lista de referencias). No están "
                "verificadas y probablemente son inventadas.",
                sugerencia="Elimina la lista de referencias y sustituye cada cita por una "
                "marca [CITA: qué debe respaldar la fuente].",
            )
        )
    desviacion = (m.palabras - objetivo) / objetivo
    if abs(desviacion) > TOLERANCIA_EXTENSION:
        accion = "Acórtala" if desviacion > 0 else "Amplíala"
        problemas.append(
            Problema(
                gravedad="media",
                descripcion=f"La sección tiene {m.palabras} palabras y el objetivo es "
                f"{objetivo} ({desviacion:+.0%}).",
                sugerencia=f"{accion} hasta unas {objetivo} palabras.",
            )
        )
    return problemas


class Orquestador(Agent):
    name = "orquestador"
    max_correcciones: int = 3  # por sección
    pasos_en_resumen: int = 6  # pasos recientes que se le muestran

    def __init__(
        self,
        llm,
        planificador: Planificador,
        redactor: Redactor,
        revisores: list[Revisor],
        max_pasos: int = 40,
    ):
        super().__init__(llm)
        self.planificador = planificador
        self.redactor = redactor
        self.revisores = revisores
        self.max_pasos = max_pasos

    def run(
        self,
        estado: Estado,
        guardar: Callable[[Estado], None] | None = None,
        on_paso: Callable[[Paso], None] | None = None,
    ) -> Estado:
        while not estado.terminado:
            if len(estado.historial) >= self.max_pasos:
                estado.terminado = True
                estado.motivo_fin = f"Se alcanzó el límite de {self.max_pasos} pasos"
                break
            inicio = time.perf_counter()
            decision = self.ask(self.resumen(estado), Decision)
            error = self._validar(estado, decision)
            resultado = f"RECHAZADA: {error}" if error else self._ejecutar(estado, decision)
            paso = Paso(
                numero=len(estado.historial) + 1,
                accion=decision.accion,
                seccion=decision.seccion,
                razonamiento=decision.razonamiento,
                resultado=resultado,
                rechazada=error is not None,
                segundos=round(time.perf_counter() - inicio, 1),
            )
            estado.historial.append(paso)
            if guardar:
                guardar(estado)
            if on_paso:
                on_paso(paso)
        if guardar:
            guardar(estado)
        return estado

    # --- Lo que ve el Orquestador ---------------------------------------------------------

    def resumen(self, estado: Estado) -> str:
        spec = estado.spec
        lineas = [
            f"Pasos usados: {len(estado.historial)} de {self.max_pasos}.",
            f'Artículo: "{spec.titulo}" (unas {spec.extension_palabras} palabras).',
        ]
        if not estado.esquema:
            lineas.append("Esquema: todavía no hay.")
        else:
            lineas.append(f"Esquema: {len(estado.esquema.secciones)} secciones.")
        if not estado.borrador:
            lineas.append("Borrador: todavía no hay.")
        else:
            lineas.append("Secciones del borrador:")
            for n, (plan, seccion, es) in enumerate(
                zip(
                    estado.esquema.secciones,
                    estado.borrador.secciones,
                    estado.secciones,
                    strict=True,
                ),
                1,
            ):
                m = medir(seccion.texto)
                linea = (
                    f"{n}. {plan.titulo}: {m.palabras} palabras (objetivo {plan.palabras}), "
                    f"{m.citas} marcas [CITA]"
                )
                if m.referencias_inventadas:
                    linea += ", CONTIENE REFERENCIAS INVENTADAS (no permitidas)"
                linea += f"; {_estado_revision(es)}; correcciones {es.correcciones}"
                linea += f"/{self.max_correcciones}."
                lineas.append(linea)
        recientes = estado.historial[-self.pasos_en_resumen :]
        if recientes:
            lineas.append("Últimos pasos:")
            for p in recientes:
                seccion = f" {p.seccion}" if p.seccion else ""
                lineas.append(f"- Paso {p.numero}: {p.accion}{seccion} → {p.resultado}")
        lineas.append("Decide la siguiente acción.")
        return "\n".join(lineas)

    # --- Límites que pone el código --------------------------------------------------------

    def _validar(self, estado: Estado, d: Decision) -> str | None:
        if d.accion == "redactar" and not estado.esquema:
            return "no hay esquema; primero hay que planificar"
        if d.accion == "terminar" and not estado.borrador:
            return "todavía no hay borrador"
        if d.accion in ("revisar_seccion", "corregir_seccion"):
            if not estado.borrador:
                return "todavía no hay borrador"
            if d.seccion is None or not 1 <= d.seccion <= len(estado.secciones):
                return f"indica una sección entre 1 y {len(estado.secciones)}"
            es = estado.secciones[d.seccion - 1]
            if d.accion == "revisar_seccion" and es.revisada and not es.corregida_tras_revision:
                return "ya está revisada y no ha cambiado desde entonces"
            if d.accion == "corregir_seccion":
                if not es.revisada:
                    return "hay que revisarla antes de corregirla"
                if es.corregida_tras_revision:
                    return "ya se corrigió; hay que revisarla antes de volver a corregirla"
                if not any(es.abiertos.values()):
                    return "no tiene problemas graves abiertos"
                if es.correcciones >= self.max_correcciones:
                    return f"ya se ha corregido {self.max_correcciones} veces (máximo)"
        return None

    # --- Ejecución de cada acción ----------------------------------------------------------

    def _ejecutar(self, estado: Estado, d: Decision) -> str:
        match d.accion:
            case "planificar":
                estado.esquema = self.planificador.run(estado.spec)
                estado.borrador, estado.secciones = None, []
                return f"esquema con {len(estado.esquema.secciones)} secciones"
            case "redactar":
                estado.borrador = self.redactor.run(estado.spec, estado.esquema)
                estado.secciones = [EstadoSeccion() for _ in estado.borrador.secciones]
                palabras = sum(medir(s.texto).palabras for s in estado.borrador.secciones)
                return f"borrador de {palabras} palabras"
            case "revisar_seccion":
                return self._revisar(estado, d.seccion - 1)
            case "corregir_seccion":
                return self._corregir(estado, d.seccion - 1)
            case "terminar":
                estado.terminado = True
                estado.motivo_fin = d.razonamiento
                return "fin"

    def _revisar(self, estado: Estado, i: int) -> str:
        es = estado.secciones[i]
        seccion = estado.borrador.secciones[i]
        previa = estado.borrador.secciones[i - 1].texto if i > 0 else None
        seguimiento = es.revisada and es.corregida_tras_revision
        resueltos_total = 0
        for revisor in self.revisores:
            if seguimiento:
                problemas, resueltos = revisor.comprobar(
                    estado.spec,
                    estado.esquema,
                    i,
                    seccion.texto,
                    previa,
                    es.abiertos.get(revisor.name, []),
                )
            else:
                revision = revisor.run(estado.spec, estado.esquema, i, seccion.texto, previa)
                problemas, resueltos = revision.problemas, []
            es.abiertos[revisor.name] = [p for p in problemas if p.gravedad in GRAVES]
            resueltos_total += len(resueltos)
            estado.registro_revision.append(
                RegistroRevision(
                    seccion=seccion.titulo,
                    ronda=es.correcciones,
                    revisor=revisor.name,
                    problemas=problemas,
                    resueltos=resueltos,
                )
            )
        objetivo = estado.esquema.secciones[i].palabras
        es.abiertos["codigo"] = comprobar_con_codigo(seccion.texto, objetivo)
        estado.registro_revision.append(
            RegistroRevision(
                seccion=seccion.titulo,
                ronda=es.correcciones,
                revisor="codigo",
                problemas=es.abiertos["codigo"],
            )
        )
        es.revisada, es.corregida_tras_revision = True, False
        detalle = ", ".join(
            f"{nombre.removeprefix('revisor_')} {len(ps)}" for nombre, ps in es.abiertos.items()
        )
        abiertos = sum(len(ps) for ps in es.abiertos.values())
        texto = f"{abiertos} problemas graves abiertos ({detalle})"
        return texto + (f"; {resueltos_total} resueltos" if seguimiento else "")

    def _corregir(self, estado: Estado, i: int) -> str:
        es = estado.secciones[i]
        seccion = estado.borrador.secciones[i]
        problemas = [
            f"({nombre}, {p.gravedad}) {p.descripcion} Sugerencia: {p.sugerencia}"
            for nombre, ps in es.abiertos.items()
            for p in ps
        ]
        texto = self.redactor.corregir(estado.spec, estado.esquema, i, seccion.texto, problemas)
        estado.borrador.secciones[i] = SeccionRedactada(titulo=seccion.titulo, texto=texto)
        es.correcciones += 1
        es.corregida_tras_revision = True
        return f"corregida ({len(problemas)} problemas); ahora {medir(texto).palabras} palabras"


def _estado_revision(es: EstadoSeccion) -> str:
    if not es.revisada:
        return "sin revisar"
    if es.corregida_tras_revision:
        return "corregida, pendiente de volver a revisar"
    abiertos = {n.removeprefix("revisor_"): len(ps) for n, ps in es.abiertos.items() if ps}
    if not abiertos:
        return "revisada, sin problemas graves"
    detalle = ", ".join(f"{n} {k}" for n, k in abiertos.items())
    return f"revisada, {sum(abiertos.values())} problemas graves abiertos ({detalle})"
