# Equipo de agentes de IA para redactar artículos científicos

TFG — línea *SpecFlow AI: plataforma SDD (Spec-Driven Development)*. Tutor: Joaquín Gayoso Cabada.

A partir de una **especificación** del artículo (`specs/*.yaml`), un equipo de agentes
de IA genera un artículo científico que se puede verificar contra esa especificación.

```
Spec → Investigador → [Orquestador: Planificador · Redactor · Revisores (formato · contexto · calidad) ⟲] → Verificador de citas → Editor (LaTeX/PDF)
```

Estado: ✅ Orquestador · ✅ Investigador · ✅ Planificador · ✅ Redactor · ✅ Revisores (formato, contexto y calidad) · ⏳ el resto

## Puesta en marcha

Requisitos: Python 3.12+, [Ollama](https://ollama.com) con el modelo de `config.yaml` descargado.

```bash
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
```

## Usar Claude en lugar de Ollama

```bash
pip install -e ".[anthropic]"
set ANTHROPIC_API_KEY=sk-ant-...      # PowerShell: $env:ANTHROPIC_API_KEY="sk-ant-..."
```

Y en `config.yaml`, cambia el bloque `llm` por el que aparece comentado (`provider: anthropic`).
No hay que tocar código: los agentes solo conocen la interfaz `LLMClient` de `llm.py`.

## Uso

```bash
python -m articulos_ia generar specs/ejemplo.yaml    # todo, dirigido por el agente Orquestador (reanudable)
python -m articulos_ia investigar specs/ejemplo.yaml # genera fuentes.md
python -m articulos_ia plan specs/ejemplo.yaml       # genera outputs/<titulo>/esquema.json
python -m articulos_ia redactar specs/ejemplo.yaml   # genera outputs/<titulo>/borrador.md
python -m articulos_ia revisar specs/ejemplo.yaml    # genera revisado.md y revision.json
pytest                                               # tests (no necesitan Ollama)
```

## Estructura

| Ruta | Contenido |
|---|---|
| `config.yaml` | Modelo y proveedor de LLM (global y por agente) |
| `specs/` | Especificaciones de artículos (entrada del sistema) |
| `src/articulos_ia/spec.py` | Modelo de la especificación |
| `src/articulos_ia/llm.py` | Acceso al LLM (Ollama; ampliable a APIs) |
| `src/articulos_ia/agents/` | Un fichero por agente |
| `src/articulos_ia/prompts/` | Instrucciones (system prompt) de cada agente |
| `tests/` | Tests con un LLM falso |
| `outputs/` | Resultados generados (no se suben a Git) |
