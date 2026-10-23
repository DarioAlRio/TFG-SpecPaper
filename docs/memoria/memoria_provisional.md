# Memoria provisional del TFG

> Documento de trabajo. Recoge, en orden, las decisiones, el trabajo realizado y su justificación,
> para pasarlo después a la memoria final (LaTeX/Overleaf). No es el texto definitivo.

- **Autor:** Darío Domínguez
- **Tutor:** Joaquín Gayoso Cabada
- **Línea:** *SpecFlow AI: plataforma SDD (Spec-Driven Development) para convertir requisitos de
  negocio en software verificable con IA*
- **Tema concreto:** equipo de agentes de IA para redactar artículos científicos

---

## 1. Contexto y origen del proyecto

La línea de TFG propone aplicar ingeniería del software, arquitectura, IA generativa, calidad,
seguridad y DevOps al diseño de un **equipo de agentes de IA**. La idea central es usar la IA
"no como una calculadora que escupe código, sino como un colaborador con criterio al que sabes
guiar, revisar y corregir".

En la reunión con el tutor (22/10/2026) se concretó el tema: **un equipo de agentes que redacte
artículos científicos**.

### 1.1 Relación con Spec-Driven Development (SDD)

En SDD, antes de generar nada se escribe una **especificación** (requisitos, restricciones,
criterios de aceptación) y el resultado se verifica contra ella. Se traslada esta idea a los
artículos:

- La "spec" es la **especificación del artículo**: título, objetivo, preguntas de investigación,
  tipo, extensión, estructura y criterios de aceptación.
- Los agentes producen el artículo a partir de ella.
- El resultado es **verificable**: se puede comprobar si cubre las preguntas, si las citas existen,
  si cumple la extensión, etc.

## 2. Acuerdos con el tutor (reunión 22/10/2026)

| Tema | Acuerdo |
|---|---|
| Enfoque | Equipo de agentes para redactar artículos científicos |
| Modelos | Recomendado **Ollama** (modelos locales) |
| APIs comerciales | Permitidas **solo para pruebas**, no durante el desarrollo |
| Plazo | Sistema listo para depurar el **15/02/2027** |
| Próxima reunión | Sin fijar (propuesta: mediados de noviembre, con el diseño) |

### 2.1 Mensaje del tutor (23/10/2026)

> "Hoy hemos hablado de la creación/exploración de frameworks similares a OpenSpec basados en
> agentes para la creación de artículos científicos/TFG basados en agentes."

Interpretación y consecuencias:

- **Referente explícito: OpenSpec** (Fission-AI, código abierto, licencia MIT). Es un framework
  de SDD para asistentes de programación con IA (Claude Code, Cursor, Copilot…). Los requisitos
  viven en ficheros y no en el historial del chat. Cada cambio tiene su carpeta con propuesta,
  diseño, tareas y diferencias en las specs, y el flujo es proponer → aplicar → archivar
  (`/opsx:propose`, `/opsx:apply`, `/opsx:archive`). Se presenta como acciones flexibles, no
  como fases rígidas (a diferencia de GitHub Spec Kit).
- **El producto es un framework, no solo un generador.** La tubería de agentes actual es el
  motor. Hay que añadir un flujo de trabajo guiado por specs: artefactos en ficheros que la
  persona revisa y edita entre fases, cambios incrementales y un histórico.
- **Ámbito: artículos científicos y también TFG.** Un TFG es más largo y se organiza por
  capítulos, así que la spec y el troceado deben generalizarse.
- **"Exploración":** el estado del arte debe incluir los frameworks de SDD (OpenSpec,
  GitHub Spec Kit, Kiro…) además de los sistemas de agentes que escriben textos científicos.

## 3. Planificación

| Fechas | Fase | Entregable |
|---|---|---|
| 22/10 – 02/11 | Estado del arte y entorno | Entorno funcionando, resumen del estado del arte |
| 03/11 – 16/11 | Diseño | Documento de arquitectura, formato de la spec |
| 17/11 – 14/12 | MVP: Planificador → Redactor → Revisor | Borrador de artículo desde una spec |
| 15/12 – 11/01 | Investigador + Verificador de citas | Referencias reales comprobadas |
| 12/01 – 01/02 | Bucle de revisión, Editor LaTeX/PDF, interfaz | Sistema completo |
| 02/02 – 15/02 | Integración y pruebas con API | Versión lista para depurar |

**Estado a 22/10/2026:** se va por delante de la planificación. Ya hay una primera versión del
Planificador, el Redactor, los tres Revisores con su bucle de corrección y el Investigador
(fases previstas para noviembre–enero). Queda pendiente el estado del arte, que estaba previsto
para esta primera fase.

## 4. Entorno de desarrollo

### 4.1 Hardware

Portátil **MSI GF75 Thin 10UE**:

| Componente | Valor |
|---|---|
| CPU | Intel Core i7-10750H (6 núcleos, 2,6 GHz) |
| RAM | 16 GB |
| GPU | NVIDIA GeForce RTX 3060 Laptop, **6 GB de VRAM** |

La VRAM es el factor limitante para ejecutar modelos en local: un modelo debe caber entero en la
GPU para ir rápido; si no cabe, parte se ejecuta en CPU y la velocidad cae mucho.

### 4.2 Elección de modelos (Ollama)

| Tamaño | Viabilidad con 6 GB de VRAM |
|---|---|
| 3–4B parámetros | Cabe entero, rápido |
| 7–8B | Cabe justo (cuantizado a 4 bits). Mejor equilibrio calidad/velocidad |
| 12–14B | No cabe entero, lento |
| ≥30B | No viable |

Decisión:
- **`qwen3.5:4b`** como único modelo local. Inicialmente se pensó en usar también `qwen3:8b`
  para evaluar la calidad, pero se decidió **no descargar más modelos** por falta de espacio en
  disco y de memoria (ver 4.5). La comparación de calidad se hará contra una API comercial.
- Motivos para la familia Qwen: buen nivel en español e inglés, buen seguimiento de instrucciones
  y salida JSON fiable (necesaria para que los agentes intercambien datos estructurados).

**Prueba inicial (`qwen3.5:4b`):** se ejecuta 100 % en GPU, carga en frío ≈ 10 s,
generación ≈ **65 tokens/s**. Se observó que el modelo tiene activado el **modo "thinking"**
(razona antes de responder): para responder "hola" generó 675 tokens. Conclusión: desactivarlo en
los agentes donde no aporte, porque multiplica el tiempo de respuesta. El contexto por defecto de
Ollama es de 4096 tokens; se sube a 8192.

**El contexto (`num_ctx`) debe ser el mismo en todos los agentes:** si cambia entre llamadas,
Ollama recarga el modelo, y en 6 GB de VRAM no caben dos copias.

Recomendaciones de uso: portátil enchufado y en modo de alto rendimiento (con batería la GPU
rinde menos) y un solo modelo cargado a la vez (en 6 GB no caben dos).

### 4.3 Software

| Herramienta | Versión | Uso |
|---|---|---|
| Python | 3.12.10 | Lenguaje del proyecto (estándar en IA, librería oficial de Ollama) |
| Git | 2.45.1 | Control de versiones |
| VS Code | 1.142 | Editor. Extensiones: Python, Pylance, Ruff, LaTeX Workshop, Claude Code |
| Ollama | 0.40.7 | Ejecución local de modelos |
| SDK `anthropic` | 2.1.0 | Cliente de la API de Claude (solo para pruebas, dependencia opcional) |
| MiKTeX | 25.12 | Compilador de LaTeX (instalación incompleta: falta `pdflatex`) |

### 4.4 LaTeX y generación de PDF

Los artículos científicos se escriben casi siempre en **LaTeX**: se escribe texto con etiquetas
(`\section{}`, `\cite{}`, ecuaciones…) y un **compilador** genera el PDF con formato profesional.
Las citas se gestionan desde un fichero `.bib`.

Distinción importante para el diseño: **el agente escribe el `.tex`, pero el PDF lo genera un
compilador**. Un modelo de lenguaje no produce el PDF directamente; lo hace invocando una
herramienta (igual que la IA escribe código Python pero hace falta el intérprete para ejecutarlo).
Esto permite un bucle interesante: el agente Editor compila, y si hay errores, los lee y corrige
el `.tex` (genera → verifica → corrige).

Alternativas valoradas:

| Opción | Ventajas | Inconvenientes |
|---|---|---|
| MiKTeX | Cómodo en Windows, instala paquetes bajo demanda, integra con LaTeX Workshop | `latexmk` requiere Perl |
| TeX Live | Completo | ~8 GB |
| Tectonic | Un único ejecutable, ideal para llamarlo desde código | Requiere configurar LaTeX Workshop |
| Typst | Moderno y sencillo (`pip install typst`) | Menos aceptado por revistas |

Decisión: **MiKTeX** como distribución local. La extensión LaTeX Workshop por sí sola no
compila; necesita una distribución instalada.

### 4.5 Limitaciones de recursos observadas

Problemas reales encontrados al ejecutar los agentes con Ollama, útiles para justificar
decisiones y para la discusión de la memoria:

| Fecha | Síntoma | Causa probable |
|---|---|---|
| 22/10/2026 | Ollama falla por falta de memoria con contextos de 6144 y 8192, con la GPU libre | Disco C: casi lleno (≈ 0,25 GB libres): Windows no puede ampliar la memoria virtual |
| 22/10/2026 | En mitad de la revisión: *"model runner has unexpectedly stopped"* | Falta de memoria |
| 22/10/2026 | Ollama no puede cargar el modelo: `std::bad_alloc` al cargar el codificador de visión (CLIP) de `qwen3.5:4b` | Solo 1,6 GB de RAM libre; el proceso "ollama app" ocupaba 3,8 GB |

Lecciones:
- `qwen3.5:4b` es multimodal: además del modelo de texto carga un codificador de imágenes que
  el proyecto no usa pero que también consume memoria.
- Una ejecución larga (decenas de llamadas seguidas) puede caerse a mitad. Conviene que el
  sistema **guarde el progreso** para poder reanudar sin repetir lo ya hecho (pendiente).

## 5. Arquitectura del sistema

```
                         ┌──────────── Orquestador (LLM) ────────────┐
                         │ decide en cada paso qué agente actúa      │
                         ▼             ▼              ▼              ▼
Spec → Investigador   Planificador   Redactor   Revisores (formato · contexto · calidad + código)
     → Verificador de citas → Editor (LaTeX/PDF)
```

| Agente | Función | Estado |
|---|---|---|
| Orquestador | Decide paso a paso qué agente actúa (planificar, redactar, revisar o corregir una sección, terminar), dentro de los límites que pone el código | ✅ v1 |
| Investigador | Busca bibliografía real (arXiv; Semantic Scholar opcional) y valora su relevancia | ✅ v1 |
| Planificador | Genera el esquema: título, resumen y secciones con sus puntos clave | ✅ v1 |
| Redactor | Escribe sección a sección; corrige las secciones según los revisores | ✅ v1 |
| Revisor de formato | Extensión, idioma, Markdown, forma de las marcas de cita | ✅ v1 |
| Revisor de contexto | Encaje en el artículo: objetivo, puntos clave, preguntas, coherencia | ✅ v1 |
| Revisor de calidad | Rigor, argumentación, claridad, criterios de aceptación | ✅ v1 |
| Verificador de citas | Comprueba que las referencias existen y respaldan lo que se afirma | ⏳ |
| Editor | Da formato LaTeX y compila el PDF | ⏳ |

### 5.1 Decisiones de diseño

- **Independencia del proveedor de LLM.** Los agentes solo conocen una interfaz `LLMClient`.
  Cambiar de Ollama a una API (para las pruebas) es cambiar `config.yaml`, no el código. Esto
  permite además comparar modelo local frente a API en la evaluación. Ya hay dos
  implementaciones: Ollama y Claude (ver 6.8).
- **Configuración por agente.** Cada agente puede usar otro modelo, temperatura o modo thinking.
- **Salida estructurada y validada.** Los agentes que intercambian datos devuelven JSON con un
  esquema definido (Pydantic). Ollama recibe ese esquema y restringe la salida del modelo a él.
- **Texto libre para redactar.** El Redactor es la excepción: devuelve Markdown, no JSON. Escribir
  prosa larga dentro de un campo JSON (escapando comillas y saltos de línea) es difícil para un
  modelo de 4B y empeora el texto. La clase base `Agent` ofrece por eso dos métodos: `ask`
  (JSON validado) y `write` (texto libre, reintenta si llega vacío).
- **Autocorrección.** Si la respuesta no cumple el esquema, se reenvía al modelo junto con el
  error de validación para que la corrija (hasta 3 intentos). Es el mismo principio de
  "genera → verifica → corrige" aplicado a cada agente.
- **Prompts separados del código.** Las instrucciones de cada agente están en ficheros `.md`, para
  poder ajustarlas y versionarlas sin tocar Python.
- **Orquestación propia (sin framework por ahora).** Se empieza sin LangGraph/CrewAI para entender
  y controlar cada paso; se valorará un framework cuando haya varios agentes.
- **Orquestador con LLM, pero con límites puestos por el código** (decidido el 23/10/2026). Se
  valoraron tres opciones: un orquestador en código (flujo fijo), un agente orquestador (un LLM
  decide el flujo) y un híbrido. Se eligió el **agente orquestador**: es el enfoque más
  propio de un sistema multiagente y permite que el flujo se adapte. Por ejemplo, corregir
  solo las secciones con problemas o terminar cuando ya no compensa seguir. Como el modelo
  de 4B no es fiable por sí solo (ver 7.3), el código lo encierra en unos límites:
  - solo puede elegir entre 5 acciones cerradas;
  - el código valida cada decisión (por ejemplo, no se puede redactar sin esquema ni corregir
    una sección sin revisarla). Si no tiene sentido, la rechaza y en el paso siguiente le
    muestra el motivo, como en la autocorrección de los demás agentes;
  - hay un máximo de pasos (40) y de correcciones por sección (3);
  - recibe ya medidas por código las palabras, las marcas `[CITA]` y las referencias
    inventadas de cada sección;
  - el estado completo se guarda tras cada paso (`estado.json`) para poder **reanudar** si
    Ollama se cae.
- **Comprobaciones con código dentro de la revisión.** Tras la prueba de 7.3, la extensión
  (±25 % del objetivo) y las referencias inventadas (citas numéricas, «(Autor, año)» o una
  lista de referencias) las comprueba el código y se añaden como problemas de un revisor más,
  `codigo`. Como se recalculan en cada revisión, el modelo no puede darlas por resueltas si
  no lo están.
- **Trabajo sección a sección.** Con 8192 tokens de contexto no cabe el artículo entero junto con
  la spec y las instrucciones. Redactor y Revisores trabajan sobre una sección cada vez y reciben
  el final de la sección anterior (1500 caracteres) para mantener la continuidad.
- **El mismo "encargo" para quien escribe y quien revisa.** La descripción de lo que se espera de
  una sección (spec, índice del esquema, objetivo, puntos clave, preguntas y extensión) se genera
  en una sola función (`encargo_seccion`), que usan el Redactor y los tres Revisores. Así juzgan
  el texto con exactamente la misma información con la que se escribió.
- **Citas como marcas pendientes.** El Redactor no escribe referencias: donde hace falta una cita
  pone `[CITA: qué debe respaldar]`. Así no inventa autores ni años (alucinación típica de los
  LLMs), y deja localizado qué afirmaciones necesitan fuente para el Investigador y el
  Verificador de citas.
- **Tres revisores especializados en lugar de uno.** Un único revisor con un prompt largo tiende
  a centrarse en unos aspectos y olvidar otros, sobre todo con un modelo pequeño. Se divide en
  formato, contexto y calidad, cada uno con su prompt y criterios de gravedad propios.
- **El código mide; el modelo opina.** Los modelos pequeños no saben contar palabras. El número
  de palabras y de marcas `[CITA]` se calcula en Python y se le da al Revisor de formato.
- **Gravedad de los problemas.** Cada problema es de gravedad alta, media o baja. Solo los de
  gravedad alta o media obligan a corregir; los de baja se registran pero no reabren la sección.
- **Rondas de seguimiento en lugar de revisar desde cero** (decidido el 23/10/2026). En la primera
  prueba real el bucle no convergía: en cada ronda el revisor volvía a criticar la sección
  entera y encontraba problemas distintos (ver 7.2). Ahora, desde la segunda ronda, cada
  revisor recibe la lista numerada de sus problemas graves anteriores y solo dice cuáles se
  han resuelto. Puede añadir problemas nuevos, pero solo de gravedad alta, porque son los
  que la corrección puede haber introducido. Es lo que hace una persona al revisar una
  segunda versión: comprobar los cambios que pidió. Se descartó la alternativa de obligar a
  corregir solo los problemas de gravedad alta, porque dejaría sin tratar los de gravedad
  media (faltan puntos clave, faltan citas…). Además, así se puede medir cuántos problemas
  se resuelven en cada ronda.
- **La búsqueda bibliográfica no usa IA.** El LLM propone las consultas y valora la relevancia,
  pero la búsqueda la hace el código contra APIs reales. Así las fuentes existen seguro.

## 6. Implementación

### 6.1 Estructura del proyecto

| Ruta | Contenido |
|---|---|
| `config.yaml` | Modelo y proveedor (global y por agente), rondas de revisión, búsqueda |
| `specs/` | Especificaciones de artículos (entrada del sistema) |
| `src/articulos_ia/spec.py` | Modelo de la especificación (`ArticleSpec`) |
| `src/articulos_ia/config.py` | Carga de la configuración |
| `src/articulos_ia/llm.py` | Interfaz `LLMClient` y clientes de Ollama y Claude |
| `src/articulos_ia/fuentes.py` | Búsqueda en arXiv y Semantic Scholar (sin IA) |
| `src/articulos_ia/agents/` | Clase base `Agent` y un fichero por agente |
| `src/articulos_ia/prompts/` | System prompt de cada agente |
| `tests/` | Tests automáticos |
| `outputs/` | Resultados generados (excluidos de Git) |

Dependencias: `ollama`, `pydantic`, `pyyaml`; opcional `anthropic`; en desarrollo, `pytest` y
`ruff`. La búsqueda bibliográfica usa solo la biblioteca estándar (`urllib`, `xml`).

Órdenes disponibles:

```
python -m articulos_ia generar    specs/ejemplo.yaml   → estado.json, articulo.md (Orquestador)
python -m articulos_ia investigar specs/ejemplo.yaml   → fuentes.json, fuentes.md
python -m articulos_ia plan       specs/ejemplo.yaml   → esquema.json
python -m articulos_ia redactar   specs/ejemplo.yaml   → borrador.json, borrador.md
python -m articulos_ia revisar    specs/ejemplo.yaml   → revisado.md, revision.json
```

Cada orden reutiliza lo que ya existe en `outputs/<titulo>/` y genera lo que falte (por ejemplo,
`revisar` redacta antes el borrador si no lo hay). `generar` es independiente de las demás:
lo dirige el Orquestador y, si existe `estado.json`, continúa desde ahí (`--nuevo` empieza
de cero). El flujo fijo de `revisar` (6.5) se mantiene para poder comparar sus resultados
con los del Orquestador.

### 6.2 Especificación del artículo

Fichero YAML con: `titulo`, `idioma`, `tipo` (revisión, experimental, posición),
`extension_palabras`, `objetivo`, `preguntas_investigacion`, `palabras_clave`, `secciones`
(opcional) y `criterios_aceptacion`. Se valida al cargarla (por ejemplo, debe haber al menos
una pregunta de investigación). Ejemplo en `specs/ejemplo.yaml`.

### 6.3 Agente Planificador

Entrada: la spec. Salida (`Esquema`): título, borrador del resumen y lista de secciones, cada una
con objetivo, puntos clave, preguntas de investigación que cubre y extensión aproximada.

Reglas principales del prompt: respetar las secciones de la spec si las hay, cubrir todas las
preguntas de investigación, repartir la extensión y **no inventar datos ni referencias** (eso
corresponde a agentes con fuentes reales). Modo thinking desactivado.

### 6.4 Agente Redactor

Entrada: la spec y el esquema. Salida (`Borrador`): título, resumen y la lista de secciones
redactadas; se exporta también a Markdown.

Para cada sección recibe el encargo de la sección y el final de la anterior. Reglas del prompt:
registro académico e impersonal, desarrollar todos los puntos clave, ajustarse a la extensión,
no repetir el título de la sección (si lo pone, el código lo quita) y marcar las citas con
`[CITA: ...]`. Tiene un segundo método, `corregir`, que recibe la versión actual de la sección y
la lista de problemas de los revisores y la reescribe entera.

Ajuste tras la primera prueba: el modelo copiaba literalmente el ejemplo del prompt
(`[CITA: descripción breve sobre…]`); se cambió por un ejemplo concreto
(`[CITA: tasa de errores del código generado por LLMs]`).

### 6.5 Agentes Revisores y bucle de revisión

Los tres revisores heredan de una clase `Revisor` y comparten la salida (`Revision`): una lista
de problemas, cada uno con gravedad, descripción y sugerencia. Lista vacía = sección correcta.

| Revisor | Comprueba | Datos extra que recibe |
|---|---|---|
| Formato | Extensión (±25 %), idioma, Markdown, forma de las marcas de cita, frases dirigidas al lector | Palabras y marcas `[CITA]` contadas por código |
| Contexto | Objetivo y puntos clave, preguntas asignadas, coherencia con la spec, que no invada otras secciones | Final de la sección anterior |
| Calidad | Afirmaciones con cita, datos inventados, argumentación, claridad, criterios de aceptación | — |

Bucle (`revisar_borrador`), para cada sección:

1. Ronda 0: los tres revisores la revisan completa (`Revisor.run`).
2. Si hay problemas de gravedad alta o media, el Redactor la corrige con esa lista.
3. Rondas de seguimiento (`Revisor.comprobar`): cada revisor recibe la versión corregida y la
   lista numerada de sus problemas graves de la ronda anterior. Devuelve, para cada número, si
   se ha resuelto, y solo puede añadir problemas nuevos de gravedad alta. Las instrucciones
   comunes de esta ronda están en `prompts/revisor_seguimiento.md`.
4. El código decide qué sigue abierto: los problemas no resueltos (también aquellos sobre los
   que el modelo no dice nada, por prudencia) más los nuevos de gravedad alta. Los nuevos de
   gravedad menor se descartan aunque el modelo los devuelva.
5. Se repite hasta que no quede nada abierto o hasta `max_rondas_revision` correcciones
   (2 por defecto, en `config.yaml`).

Todo lo que dice cada revisor en cada ronda se guarda en `revision.json`: los problemas abiertos
y, en las rondas de seguimiento, los resueltos. Así se puede medir cuántos problemas se
resuelven en cada ronda.

### 6.6 Agente Investigador

Funciona en tres pasos:

1. El LLM propone de 4 a 6 consultas en inglés (la mayoría de la literatura está en inglés)
   que entre todas cubran las preguntas de investigación.
2. El código lanza cada consulta contra los buscadores y elimina duplicados (mismo título
   normalizado). Si un buscador falla, lo avisa y sigue con los demás.
3. El LLM valora la relevancia de cada artículo de 0 a 3 a partir de su título y su resumen, en
   **lotes de 5** para no desbordar el contexto. Se quedan los de puntuación ≥ 2, ordenados de
   mayor a menor, hasta un máximo de 15. Para cada uno se guarda el motivo y las preguntas de
   investigación a las que ayuda.

Fuentes de datos:

| API | Clave | Observaciones |
|---|---|---|
| arXiv | No | Pide no hacer más de una petición cada 3 s; el código lo respeta. Responde en XML (Atom) |
| Semantic Scholar | Opcional | Sin clave comparte un cupo con todos los usuarios y responde casi siempre **429** (demasiadas peticiones). Desactivado por defecto |

Las fuentes seleccionadas todavía no se usan en el Planificador ni en el Redactor (pendiente).

### 6.7 Agente Orquestador

Bucle (`Orquestador.run`):

1. Se construye un resumen del estado: pasos usados, si hay esquema y borrador y, por cada
   sección, sus palabras frente al objetivo, sus marcas `[CITA]`, si tiene referencias
   inventadas, su estado de revisión (sin revisar, problemas graves abiertos por revisor,
   corregida y pendiente de revisar) y sus correcciones. Se añaden también los últimos 6
   pasos con su resultado.
2. El LLM devuelve una `Decision` (JSON): `razonamiento`, `accion` y, si hace falta,
   `seccion`. El razonamiento va primero para que el modelo lo escriba antes de elegir.
3. El código valida la decisión. Si es válida, la ejecuta con el agente que toca. Si no, la
   registra como «RECHAZADA: motivo».
4. Se añade el paso al historial y se guarda el estado.
5. Se repite hasta que el modelo elige `terminar` o se agotan los pasos.

| Acción | Qué hace | Condiciones que exige el código |
|---|---|---|
| `planificar` | Planificador → esquema (descarta el borrador) | — |
| `redactar` | Redactor → borrador completo | Que haya esquema |
| `revisar_seccion` | Los 3 revisores + las comprobaciones del código. Si la sección se había corregido, hace ronda de seguimiento | Que haya borrador; sección válida; que haya cambiado desde la última revisión |
| `corregir_seccion` | Redactor.corregir con los problemas graves abiertos | Revisada; con problemas graves; sin una corrección pendiente de revisar; menos de 3 correcciones |
| `terminar` | Fin | Que haya borrador |

Ajustes de los prompts tras la prueba 7.3:
- Al Redactor, cuando corrige, se le recuerda la extensión objetivo y que las citas se marcan
  con `[CITA: ...]`, nunca con autores, años ni una lista de referencias.
- Al Revisor de calidad se le indica que, si faltan citas, la sugerencia debe ser añadir
  marcas, no referencias concretas.

### 6.8 Cliente de Claude (API de Anthropic)

Segunda implementación de `LLMClient`, para las pruebas con API acordadas con el tutor. Se activa
con `provider: anthropic` en `config.yaml` y la variable de entorno `ANTHROPIC_API_KEY`.

Diferencias con Ollama que resuelve el cliente:
- La API recibe el system prompt aparte, no como un mensaje más.
- La salida estructurada se pide con `output_config.format` (JSON Schema), y exige
  `additionalProperties: false` en todos los objetos; el cliente se lo añade al esquema que
  genera Pydantic.
- No admite `temperature` ni desactivar el razonamiento; en su lugar se ajusta el `effort`
  (low / medium / high).
- Si el modelo rechaza una petición, la API la repite automáticamente con un modelo de respaldo.

Modelo configurado: `claude-opus-5-5`. **Sin probar contra la API real** (no hay clave
configurada); está cubierto por tests con un cliente falso.

## 7. Pruebas

### 7.1 Tests automáticos

Los tests usan un **LLM falso** que devuelve respuestas fijas, de modo que no necesitan Ollama,
son rápidos y deterministas. Tampoco acceden a internet: las búsquedas se sustituyen por
funciones falsas y las respuestas de arXiv y Semantic Scholar por ejemplos fijos.

| Fichero | Comprueba |
|---|---|
| `test_planificador.py` (5) | Carga de la spec, esquema válido, reintento con el error, fallo tras agotar intentos, ajustes por agente |
| `test_redactor.py` (7) | Una llamada por sección, contexto correcto (preguntas, sección anterior), progreso, reintento si llega vacío, Markdown, eliminación del título repetido |
| `test_revisor.py` (8) | Aprobación según gravedad, datos medidos, sección anterior, un prompt distinto por revisor, bucle sin correcciones, corrección con ronda de seguimiento, en el seguimiento solo se admiten nuevos problemas graves y los no mencionados siguen abiertos, máximo de rondas |
| `test_investigador.py` (5) | Lectura de arXiv y Semantic Scholar, duplicados, buscador que falla, selección y orden por relevancia, lotes, máximo de fuentes |
| `test_llm.py` (3) | Cliente de Claude: system prompt aparte, sin `temperature`, esquema JSON estricto |
| `test_orquestador.py` (8) | Ciclo completo con corrección y seguimiento, guardado tras cada paso, resumen que ve el orquestador, rechazo de 6 tipos de acciones sin sentido, límite de pasos, reanudar desde un estado guardado, detección de referencias inventadas, comprobaciones del código dentro de la revisión |

Resultado: **36/36 tests superados**. Ruff (estilo y errores): sin incidencias.

### 7.2 Ejecuciones reales con Ollama (`qwen3.5:4b`)

Spec de ejemplo: revisión de 3000 palabras sobre agentes LLM para generar software.

| Fecha | Orden | Resultado |
|---|---|---|
| 22/10/2026 | `plan` | Esquema de 6 secciones válido a la primera |
| 22/10/2026 | `redactar` | 6 secciones en **128 s**. **4909 palabras** (objetivo: 3000, +64 %); cada sección superó su objetivo. 45 marcas `[CITA]` |
| 22/10/2026 | `revisar` | Se cortó en la 3.ª sección de 6 por falta de memoria (ver 4.5). Hasta ahí, **ninguna sección quedó aprobada**: todas agotaron las 2 rondas con problemas pendientes |
| 22/10/2026 | `investigar` | No llegó a ejecutarse: Ollama no pudo cargar el modelo (falta de memoria) |

Detalle de la revisión (problemas que obligan a corregir, por ronda):

| Sección | Ronda 0 (F / Cx / Ca) | Ronda 1 | Ronda 2 |
|---|---|---|---|
| Introducción | 1 / 3 / 2 | 1 / 2 / 4 | 0 / 1 / 3 |
| Trabajos relacionados | 1 / 2 / 2 | 2 / 1 / 1 | 0 / 1 / 4 |
| Arquitecturas multiagente | 1 / 12 / 2 | 1 / 1 / 1 | 1 / 2 / — (corte) |

F = formato, Cx = contexto, Ca = calidad.

Observaciones:
- El Revisor de formato detecta el exceso de extensión y, tras corregir, sus problemas bajan a 0
  en dos de las tres secciones.
- El Revisor de calidad no baja: en cada ronda encuentra problemas **nuevos**. Un modelo pequeño
  al que se le pide criticar siempre encuentra algo, así que el bucle no converge.
- Solución adoptada el 23/10/2026: rondas de seguimiento (ver 5.1 y 6.5). Probada en 7.3.

### 7.3 Segunda prueba de la revisión, con rondas de seguimiento (23/10/2026)

Mismo borrador que en la primera prueba. Terminó sin cortes en **461 s** (6 secciones,
3 revisores, hasta 2 correcciones por sección).

| Sección | Graves ronda 0 (F / Cx / Ca) | Correcciones | Resultado |
|---|---|---|---|
| Introducción | 1 / 0 / 3 | 1 | Aprobada |
| Trabajos relacionados | 1 / 3 / 2 | 2 | **No aprobada**: quedan 2 de calidad |
| Arquitecturas multiagente | 1 / 1 / 3 | 2 | Aprobada |
| Verificación y calidad | 1 / 1 / 2 | 1 | Aprobada |
| Discusión | 1 / 2 / 2 | 2 | Aprobada |
| Conclusiones | 1 / 1 / 2 | 1 | Aprobada |

En apariencia, el bucle ya converge: 5 de 6 secciones aprobadas y 26 de los 28 problemas graves
marcados como resueltos. Ningún revisor añadió problemas nuevos en las rondas de seguimiento.

**Pero al comprobar el texto final, varias "resoluciones" son falsas:**

| Sección | Objetivo | Palabras antes | Palabras después | `[CITA]` antes → después |
|---|---|---|---|---|
| Introducción | 500 | 612 | 648 | 4 → 10 |
| Trabajos relacionados | 600 | 835 | 830 | 10 → 13 |
| Arquitecturas multiagente | 700 | 1126 | 1306 | 13 → **0** |
| Verificación y calidad | 600 | 914 | 951 | 10 → 12 |
| Discusión | 600 | 757 | 729 | 6 → 11 |
| Conclusiones | 400 | 530 | 633 | 2 → 7 |
| **Total** | 3400 | 4774 | **5097** | |

1. **Extensión.** El Revisor de formato marcó como resuelto el exceso de extensión en todas las
   secciones, pero ninguna se acortó; tres incluso crecieron. El total pasó de 4774 a 5097
   palabras. Además se contradijo: en la Introducción calculó un exceso del 22 % (por debajo de
   su propio umbral del 25 %) y aun así le puso gravedad media.
2. **Referencias inventadas.** El Revisor de calidad pidió más citas en "Arquitecturas
   multiagente". Al corregir, el Redactor quitó todas las marcas `[CITA]`, puso citas
   numéricas `[1]`–`[10]` y añadió una sección "Referencias" con autores, revistas y páginas
   **inventados** (por ejemplo, "Li, X., et al. (2023). Multi-Agent Systems for Software
   Engineering: A Survey. *Journal of Software Evolution and Process*, 35(4)"). El Revisor de
   calidad lo dio por resuelto. Es justo la alucinación de citas que el diseño quería evitar.

Conclusiones:
- Un LLM pequeño no es fiable para **comprobar** si algo se ha corregido: tiende a aceptar la
  nueva versión. Ocurre igual que con contar palabras (ver 5.1, "el código mide").
- Las comprobaciones que se pueden hacer con código (extensión, presencia de marcas
  `[CITA]`, ausencia de referencias inventadas, encabezados) deben hacerse con código. El
  modelo no debe poder darlas por resueltas.
- La petición "faltan citas" empuja al Redactor a inventarlas. Hay que decir explícitamente,
  tanto al Revisor de calidad como al Redactor al corregir, que la forma correcta de citar es
  añadir marcas `[CITA: ...]`.
- La primera prueba (7.2) también apuntaba a falsas resoluciones del Revisor de formato.

### 7.4 Primera ejecución del Orquestador (23/10/2026)

`generar --nuevo` con la spec de ejemplo, desde cero. Primeros pasos:

| Paso | Decisión del Orquestador | Tiempo | Resultado |
|---|---|---|---|
| 1 | planificar | 33 s | Esquema con 6 secciones |
| 2 | redactar | 120 s | Borrador de 4725 palabras |
| 3 | revisar_seccion 1 | 26 s | 5 problemas graves (todos de calidad) |
| 4 | corregir_seccion 1 | 16 s | Corregida; queda en 386 palabras |
| 5 | revisar_seccion 1 | 16 s | 0 problemas graves; 5 resueltos |
| 6 | revisar_seccion 2 | 19 s | 2 problemas graves (formato 1, calidad 1) |
| 7 | corregir_seccion 2 | 25 s | Corregida; queda en 738 palabras |
| 8 | — | — | **Ollama se cae** (*model runner has unexpectedly stopped*) |

Observaciones:
- Las 7 decisiones fueron válidas; ninguna se rechazó. El orden es el de la estrategia del
  prompt: planificar, redactar y luego revisar → corregir → volver a revisar, sección a
  sección. Los razonamientos citan datos del resumen (por ejemplo, «todas las secciones
  superan su extensión objetivo»).
- En el paso 4 el razonamiento dice que la sección 1 «contiene referencias inventadas», pero
  la comprobación del código no detectó ninguna: es una **afirmación inventada en el propio
  razonamiento**. No tuvo consecuencias, porque la acción elegida era correcta igualmente.
- La corrección pasa ahora de un extremo al otro: la Introducción quedó en 386 palabras para
  un objetivo de unas 500, justo en el límite de la tolerancia (−23 %).
- Tras la caída se vuelve a ejecutar `generar` para que continúe desde el estado guardado del
  paso 7 (resultado pendiente).

## 8. Diario de trabajo

| Fecha | Trabajo |
|---|---|
| 21/10/2026 | Preparación de la reunión con el tutor |
| 22/10/2026 | Reunión: se fija el tema, Ollama y el plazo del 15/02 |
| 22/10/2026 | Análisis del hardware y elección de modelos; prueba de Ollama |
| 22/10/2026 | Preparación del entorno (VS Code, extensiones, MiKTeX) |
| 22/10/2026 | Estructura del proyecto, agente Planificador y tests |
| 22/10/2026 | Decisión: un único modelo local (`qwen3.5:4b`), no se descargan más |
| 22/10/2026 | Agente Redactor (texto libre, sección a sección, marcas `[CITA]`) y orden `redactar` |
| 22/10/2026 | Cliente de Claude como segunda implementación de `LLMClient` |
| 22/10/2026 | Primera ejecución real del Redactor: 128 s, 4909 palabras (+64 % sobre el objetivo) |
| 22/10/2026 | Ajuste del prompt del Redactor: el modelo copiaba literalmente el ejemplo de cita |
| 22/10/2026 | Tres Revisores (formato, contexto, calidad), bucle de corrección y orden `revisar` |
| 22/10/2026 | Primera ejecución real de la revisión: no converge; se corta por falta de memoria |
| 22/10/2026 | Agente Investigador (arXiv, Semantic Scholar opcional) y orden `investigar` |
| 22/10/2026 | Ollama no puede cargar el modelo por falta de RAM (`std::bad_alloc`) |
| 23/10/2026 | Mensaje del tutor: el referente es OpenSpec; el objetivo es un framework para artículos y TFG (ver 2.1) |
| 23/10/2026 | Bucle de revisión con rondas de seguimiento para que converja; 28/28 tests |
| 23/10/2026 | Reinicio de Ollama (vuelve a cargar el modelo al 100 % en GPU) |
| 23/10/2026 | Segunda prueba de la revisión: 5/6 secciones aprobadas en 461 s, pero con resoluciones falsas y referencias inventadas (ver 7.3) |
| 23/10/2026 | Agente Orquestador (LLM con límites del código, reanudable) y orden `generar`; comprobaciones con código en la revisión; ajustes de prompts; 36/36 tests |
| 23/10/2026 | Primera ejecución del Orquestador: 7 decisiones válidas; Ollama se cae en el paso 8; se relanza para reanudar desde el estado guardado (ver 7.4) |
| 23/10/2026 | `config_claude.yaml`: configuración aparte para probar con Claude (`--config`), con resultados en `outputs_claude/` para comparar con Ollama |
| 23/10/2026 | Tercer proveedor de LLM, `claude_code`: llama a Claude Code en modo no interactivo (`claude -p`, salida JSON con `--json-schema`, sin herramientas) con la sesión de la suscripción Pro, sin API key. 41/41 tests. Primera ejecución completa con Claude Sonnet lanzada |

## 9. Pendiente / ideas para la memoria

- Estudiar OpenSpec (y GitHub Spec Kit, Kiro) y decidir qué se adopta de su flujo: artefactos
  editables, aprobación humana entre fases, propuestas de cambio sobre un artículo ya escrito
  e histórico (ver 2.1).
- Generalizar la spec para que admita TFG (capítulos, mayor extensión), además de artículos.
- Aclarar con el tutor si el framework debe tener sus propios agentes (lo actual) o funcionar
  sobre asistentes existentes como Claude Code, como hace OpenSpec, o las dos cosas.

- Añadir al Orquestador la acción `investigar` cuando las fuentes se usen en el Planificador y
  el Redactor.
- Comparar el Orquestador (LLM) con el flujo fijo de `revisar`: pasos, tiempo, secciones
  aprobadas, problemas resueltos y decisiones rechazadas.
- Comprobación con código de encabezados `#`/`##` dentro de las secciones (aún no está).
- Volver a ejecutar `revisar` e `investigar` cuando Ollama tenga memoria suficiente
  (reiniciar Ollama, liberar disco).
- Guardar el progreso de las ejecuciones largas para poder reanudarlas tras un fallo.
- Usar las fuentes del Investigador en el Planificador y el Redactor, y relacionarlas con las
  marcas `[CITA]` (Verificador de citas).
- Ajustar la extensión: el Redactor se pasa sistemáticamente del objetivo.
- Probar el cliente de Claude contra la API real.
- Reinstalar MiKTeX y comprobar `pdflatex --version`.
- Escribir el estado del arte: SDD, sistemas multiagente con LLMs, generación automática de texto
  científico, alucinaciones en citas.
- Evaluación: comparar `qwen3.5:4b` con una API comercial usando la misma spec.
- Métricas posibles: cobertura de las preguntas de investigación, % de citas verificables,
  cumplimiento de la extensión, tiempo de generación, problemas resueltos por ronda de revisión.
