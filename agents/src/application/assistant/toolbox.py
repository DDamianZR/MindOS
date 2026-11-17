"""
Herramientas del asistente personal (F7-T2): definición (lo que ve el modelo), validación de
entradas y ejecución contra el Memory Service a través de `MemoryGatewayPort`.

La lista es **fija y de orden estable**: forma parte del prefijo cacheado de cada petición, y el
proveedor exige que no cambie a mitad de una conversación. Por eso no se deriva del
`CapabilityRegistry` dinámico (F1-T8), que puede variar mientras el servicio corre.
"""
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from mindos_common.logging import get_logger
from mindos_schemas.domain import ObjectType
from pydantic import BaseModel, Field, ValidationError

from agents.src.application.ports.memory_gateway import MemoryGatewayError, MemoryGatewayPort

logger = get_logger("assistant_toolbox")

# Tipos que el asistente puede asignar al guardar. Subconjunto de `ObjectType`: se dejan fuera
# los que produce la propia maquinaria (outcome, evidence, investigation, conversation...).
SAVEABLE_TYPES = [
    ObjectType.NOTE, ObjectType.IDEA, ObjectType.DECISION, ObjectType.LEARNING,
    ObjectType.FACT, ObjectType.TASK, ObjectType.QUESTION, ObjectType.HYPOTHESIS,
    ObjectType.OBSERVATION, ObjectType.EXPERIENCE, ObjectType.PERSON, ObjectType.PROJECT,
    ObjectType.EVENT, ObjectType.RESOURCE, ObjectType.CONCEPT,
]


class SearchMemoryInput(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=5, ge=1, le=15)


class SaveMemoryInput(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1)
    object_type: ObjectType = ObjectType.NOTE
    importance: float = Field(default=0.5, ge=0.0, le=1.0)


class TopicInput(BaseModel):
    topic: str = Field(min_length=1)
    limit: int = Field(default=5, ge=1, le=20)


class PastThinkingInput(BaseModel):
    topic: str = Field(min_length=1)
    at: datetime
    limit: int = Field(default=5, ge=1, le=20)


class NodeInput(BaseModel):
    node_id: UUID


@dataclass(frozen=True)
class ToolSpec:
    name: str
    label: str  # lo que la interfaz muestra mientras corre ("Buscando en tu memoria")
    description: str
    input_schema: dict[str, Any]
    input_model: type[BaseModel]


@dataclass
class ToolOutcome:
    content: str  # lo que recibe el modelo como resultado
    is_error: bool = False
    summary: str = ""  # una línea para la interfaz
    sources: list[dict[str, Any]] = field(default_factory=list)  # nodos consultados, para citarlos


_NODE_ID_PROPERTY = {
    "type": "string",
    "description": "Identificador (UUID) del nodo, tal como lo devolvió una herramienta anterior.",
}

TOOL_SPECS: list[ToolSpec] = [
    ToolSpec(
        name="search_memory",
        label="Buscando en tu memoria",
        description=(
            "Busca en la memoria de largo plazo de la persona (notas, ideas, decisiones, "
            "documentos, conversaciones capturadas). Combina similitud semántica con expansión "
            "por el grafo de conocimiento y devuelve fragmentos citables ordenados por relevancia, "
            "las relaciones entre ellos y una línea temporal corta. Es la herramienta principal: "
            "úsala antes de responder cualquier cosa que dependa de lo que la persona sabe, hizo, "
            "decidió o guardó. La consulta funciona mejor como una frase descriptiva del tema que "
            "como palabras sueltas. Cada fragmento trae su `node_id`, que sirve de entrada para "
            "`explain_knowledge` y `get_history`."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Qué buscar, en lenguaje natural."},
                "limit": {
                    "type": "integer", "minimum": 1, "maximum": 15,
                    "description": "Cuántos fragmentos devolver. Por defecto 5; sube a 10-15 para un repaso amplio de un tema.",
                },
            },
            "required": ["query"],
        },
        input_model=SearchMemoryInput,
    ),
    ToolSpec(
        name="save_memory",
        label="Guardando en tu memoria",
        description=(
            "Guarda un conocimiento nuevo en la memoria de la persona. Úsala cuando pida anotar o "
            "recordar algo, o cuando acepte tu propuesta de guardarlo; no la uses por iniciativa "
            "propia. Escribe el contenido completo y autocontenido: debe entenderse sin esta "
            "conversación. Si ya existe algo casi idéntico, MindOS enlaza ambos en vez de "
            "duplicar, y el resultado lo indica. Guardar nunca sobrescribe ni borra nada."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Título específico y reconocible (máx. 255 caracteres)."},
                "content": {"type": "string", "description": "El conocimiento completo, con el contexto necesario para entenderlo por sí solo."},
                "object_type": {
                    "type": "string",
                    "enum": [t.value for t in SAVEABLE_TYPES],
                    "description": (
                        "Tipo de objeto: 'decision' para una decisión tomada (incluye el porqué en el "
                        "contenido), 'learning' para una lección aprendida, 'idea' para algo por explorar, "
                        "'task' para un pendiente, 'fact' para un dato comprobado, 'note' si ninguno encaja."
                    ),
                },
                "importance": {
                    "type": "number", "minimum": 0, "maximum": 1,
                    "description": "Importancia para la persona, de 0 a 1. Por defecto 0.5; usa 0.8 o más solo si lo marcó como importante.",
                },
            },
            "required": ["title", "content", "object_type"],
        },
        input_model=SaveMemoryInput,
    ),
    ToolSpec(
        name="list_decisions",
        label="Revisando tus decisiones",
        description=(
            "Devuelve las decisiones que la persona registró sobre un tema, cada una con su "
            "justificación y la evidencia que la respaldaba. Úsala para preguntas del tipo "
            "«¿qué decidí sobre X y por qué?». Para explorar un tema en general, usa `search_memory`."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "Tema de las decisiones."},
                "limit": {"type": "integer", "minimum": 1, "maximum": 20, "description": "Máximo de decisiones. Por defecto 5."},
            },
            "required": ["topic"],
        },
        input_model=TopicInput,
    ),
    ToolSpec(
        name="find_contradictions",
        label="Buscando contradicciones",
        description=(
            "Devuelve pares de afirmaciones de la memoria que se contradicen entre sí sobre un "
            "tema. Úsala cuando la persona pregunte si se contradice, o antes de dar por cierta "
            "una conclusión importante que se apoye en varias notas."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "Tema en el que buscar contradicciones."},
                "limit": {"type": "integer", "minimum": 1, "maximum": 20, "description": "Máximo de pares. Por defecto 5."},
            },
            "required": ["topic"],
        },
        input_model=TopicInput,
    ),
    ToolSpec(
        name="recall_past_thinking",
        label="Reconstruyendo lo que pensabas",
        description=(
            "Reconstruye lo que la persona pensaba sobre un tema en un momento pasado, usando las "
            "versiones del conocimiento vigentes en esa fecha (no las actuales). Úsala para "
            "«¿qué pensaba en marzo sobre X?» o para comparar cómo cambió una postura."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "Tema a reconstruir."},
                "at": {"type": "string", "description": "Instante de referencia en formato ISO 8601, por ejemplo 2026-03-15T00:00:00Z."},
                "limit": {"type": "integer", "minimum": 1, "maximum": 20, "description": "Máximo de resultados. Por defecto 5."},
            },
            "required": ["topic", "at"],
        },
        input_model=PastThinkingInput,
    ),
    ToolSpec(
        name="explain_knowledge",
        label="Trazando el razonamiento",
        description=(
            "Explica de dónde sale un nodo de la memoria: la cadena de evidencias que lo "
            "sustenta, sus fuentes de origen y, si lo produjo un agente, el episodio de "
            "razonamiento que lo generó. Úsala para «¿por qué creo esto?» o «¿en qué se basa "
            "esta decisión?». Necesita el `node_id` devuelto por otra herramienta."
        ),
        input_schema={
            "type": "object",
            "properties": {"node_id": _NODE_ID_PROPERTY},
            "required": ["node_id"],
        },
        input_model=NodeInput,
    ),
    ToolSpec(
        name="get_history",
        label="Revisando el historial",
        description=(
            "Devuelve todas las versiones de un nodo en orden cronológico, con autor y fecha de "
            "cada cambio. Úsala para ver cómo evolucionó una nota o una idea. Necesita el "
            "`node_id` devuelto por otra herramienta."
        ),
        input_schema={
            "type": "object",
            "properties": {"node_id": _NODE_ID_PROPERTY},
            "required": ["node_id"],
        },
        input_model=NodeInput,
    ),
]

_SPECS_BY_NAME = {spec.name: spec for spec in TOOL_SPECS}


def _dump(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, default=str)


def _collect_sources(data: Any, limit: int = 12) -> list[dict[str, Any]]:
    """Recorre una respuesta del Memory Service y extrae los nodos citables (`node_id` + `title`)."""
    found: dict[str, dict[str, Any]] = {}

    def walk(obj: Any) -> None:
        if len(found) >= limit:
            return
        if isinstance(obj, dict):
            node_id, title = obj.get("node_id"), obj.get("title")
            if node_id and title and str(node_id) not in found:
                found[str(node_id)] = {
                    "node_id": str(node_id),
                    "title": str(title),
                    "object_type": obj.get("object_type"),
                    "score": obj.get("score"),
                }
            for value in obj.values():
                walk(value)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(data)
    return list(found.values())


def _plural(count: int, singular: str, plural: str) -> str:
    return f"{count} {singular if count == 1 else plural}"


class AssistantToolbox:
    """Ejecuta las herramientas del asistente. Nunca lanza: un fallo vuelve como resultado de
    error para que el modelo pueda reaccionar (reintentar con otros parámetros o avisar)."""

    def __init__(self, memory: MemoryGatewayPort, author: str = "usuario"):
        self._memory = memory
        self._author = author or "usuario"

    @property
    def specs(self) -> list[ToolSpec]:
        return TOOL_SPECS

    def resolve(self, name: str) -> ToolSpec | None:
        """Acepta el nombre exacto o uno que solo difiera en mayúsculas (el modelo a veces lo hace)."""
        if name in _SPECS_BY_NAME:
            return _SPECS_BY_NAME[name]
        matches = [spec for spec in TOOL_SPECS if spec.name.lower() == name.lower()]
        return matches[0] if len(matches) == 1 else None

    async def execute(self, name: str, raw_input: Any) -> ToolOutcome:
        spec = self.resolve(name)
        if not spec:
            valid = ", ".join(s.name for s in TOOL_SPECS)
            return ToolOutcome(
                content=f"La herramienta '{name}' no existe. Herramientas disponibles: {valid}.",
                is_error=True, summary="Herramienta desconocida",
            )

        # Con streaming anticipado de entradas el servidor ya no valida el JSON del modelo: una
        # entrada truncada o mal tipada puede llegar aquí con forma de objeto válido.
        try:
            args = spec.input_model.model_validate(raw_input)
        except ValidationError as e:
            problems = "; ".join(f"{'.'.join(map(str, err['loc']))}: {err['msg']}" for err in e.errors())
            return ToolOutcome(
                content=_dump({"INVALID_INPUT": problems, "received": raw_input}),
                is_error=True, summary="Parámetros inválidos",
            )

        try:
            return await getattr(self, f"_{spec.name}")(args)
        except MemoryGatewayError as e:
            logger.warning("Fallo ejecutando herramienta del asistente", tool=spec.name, error=str(e))
            return ToolOutcome(
                content=f"No se pudo completar '{spec.name}': {e}",
                is_error=True, summary="La memoria no respondió",
            )

    async def _search_memory(self, args: SearchMemoryInput) -> ToolOutcome:
        bundle = await self._memory.search_context(args.query, limit=args.limit, depth=1)
        fragments = bundle.get("fragments", [])
        result = {
            "fragments": [
                {
                    "node_id": f.get("node_id"), "title": f.get("title"),
                    "object_type": f.get("object_type"), "content": f.get("content"),
                    "confidence": f.get("confidence"), "importance": f.get("importance"),
                    "found_via_graph": f.get("via_graph", False),
                }
                for f in fragments
            ],
            "relations": bundle.get("relations_summary", []),
            "timeline": bundle.get("timeline", []),
        }
        if not fragments:
            return ToolOutcome(
                content=_dump({**result, "note": "Sin resultados para esta consulta."}),
                summary="Sin resultados",
            )
        return ToolOutcome(
            content=_dump(result),
            summary=_plural(len(fragments), "fragmento encontrado", "fragmentos encontrados"),
            sources=_collect_sources(fragments),
        )

    async def _save_memory(self, args: SaveMemoryInput) -> ToolOutcome:
        saved = await self._memory.ingest({
            "object_type": args.object_type.value, "title": args.title, "content": args.content,
            "author": self._author, "importance": args.importance,
            "source": {"kind": "agent", "metadata": {"captured_via": "assistant"}},
        })
        result = {
            "saved": True, "node_id": saved.get("node_id"), "version": saved.get("version"),
            "object_type": saved.get("object_type"), "duplicate_of": saved.get("duplicate_of"),
        }
        summary = f"Guardado: {args.title}"
        if saved.get("duplicate_of"):
            summary += " (enlazado a uno casi idéntico)"
        return ToolOutcome(
            content=_dump(result), summary=summary,
            sources=[{
                "node_id": str(saved.get("node_id")), "title": args.title,
                "object_type": args.object_type.value, "score": None,
            }],
        )

    async def _list_decisions(self, args: TopicInput) -> ToolOutcome:
        data = await self._memory.decisions(args.topic, limit=args.limit)
        return self._passthrough(data, "decisión", "decisiones")

    async def _find_contradictions(self, args: TopicInput) -> ToolOutcome:
        data = await self._memory.contradictions(args.topic, limit=args.limit)
        return self._passthrough(data, "contradicción", "contradicciones")

    async def _recall_past_thinking(self, args: PastThinkingInput) -> ToolOutcome:
        data = await self._memory.past_thinking(args.topic, at=args.at.isoformat(), limit=args.limit)
        return self._passthrough(data, "resultado", "resultados")

    async def _explain_knowledge(self, args: NodeInput) -> ToolOutcome:
        data = await self._memory.explain(str(args.node_id), max_depth=3)
        sources = _collect_sources(data)
        return ToolOutcome(content=_dump(data), summary="Razonamiento reconstruido", sources=sources)

    async def _get_history(self, args: NodeInput) -> ToolOutcome:
        data = await self._memory.history(str(args.node_id))
        versions = data.get("versions", [])
        return ToolOutcome(
            content=_dump(data), summary=_plural(len(versions), "versión", "versiones"),
        )

    @staticmethod
    def _passthrough(data: dict[str, Any], singular: str, plural: str) -> ToolOutcome:
        """Para respuestas de la Cognitive Query API: se entregan íntegras al modelo y se resume
        por la lista más larga que traigan (cada endpoint nombra la suya distinto)."""
        lists = [v for v in data.values() if isinstance(v, list)]
        count = max((len(v) for v in lists), default=0)
        summary = _plural(count, singular, plural) if count else f"Sin {plural}"
        return ToolOutcome(content=_dump(data), summary=summary, sources=_collect_sources(data))
