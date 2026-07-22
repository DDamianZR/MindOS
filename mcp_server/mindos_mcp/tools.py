"""
Lógica de las 5 tools MCP (F4-T2), separada del registro en `server.py` para poder probarla
directamente (con un `MindOSClient` de prueba) sin pasar por la maquinaria de FastMCP.
"""
from typing import Any

from mindos_mcp.mindos_client import MindOSClient


async def search(client: MindOSClient, query: str, limit: int = 5) -> dict[str, Any]:
    """Busca en la memoria de conocimiento de MindOS por similitud semántica.

    Devuelve resultados con su `node_id`, contenido y `score` — cita el `node_id` de cada
    resultado que uses para responder, así la respuesta queda trazable a su fuente.
    """
    return await client.search(query, limit=limit)


async def ingest(
    client: MindOSClient, title: str, content: str, object_type: str = "note", source: str | None = None,
) -> dict[str, Any]:
    """Captura una nueva pieza de conocimiento en MindOS (nota, idea, hecho, decisión...).

    `object_type` es uno de: note, idea, fact, hypothesis, decision, document, concept. `source`
    es una referencia libre de dónde salió esta información dentro de la conversación actual
    (ej: "conversación sobre el despliegue de X") — opcional, pero recomendado para trazabilidad.
    """
    return await client.ingest(title=title, content=content, object_type=object_type, source=source)


async def context(client: MindOSClient, query: str, limit: int = 5, depth: int = 1) -> dict[str, Any]:
    """Recupera un bundle de contexto GraphRAG (similitud vectorial + expansión de grafo +
    reranking por importancia/recencia/confianza) para responder preguntas fundamentadas en el
    conocimiento de MindOS, con fragmentos citables por `node_id`/fuente.
    """
    return await client.context(query, limit=limit, depth=depth)


async def ask_cognitive(client: MindOSClient, question_type: str, params: dict[str, Any]) -> dict[str, Any]:
    """Responde una de las preguntas insignia de MindOS sobre su propio historial de pensamiento.

    `question_type` y los `params` que espera cada una:
    - "past_thinking": {"topic": str, "at": str ISO8601} — ¿qué pensaba en esa fecha sobre X?
    - "similar": {"node_id": str} — ¿qué ideas similares tuve antes?
    - "decisions": {"topic": str} — ¿qué decisiones tomé y por qué?
    - "support": {"node_id": str} — ¿qué respalda esta recomendación?
    - "contradictions": {"topic": str} — ¿qué contradicciones existen?
    - "patterns": {} — ¿qué patrones aparecen en mi forma de pensar?

    Para "¿cómo llegué a esta conclusión?" usa la tool `mindos_explain`, no esta.
    """
    return await client.ask_cognitive(question_type, params)


async def explain(client: MindOSClient, node_id: str, max_depth: int = 3) -> dict[str, Any]:
    """Explica cómo se llegó a una conclusión: recorre hacia atrás las evidencias, decisiones e
    hipótesis que sustentan el nodo dado, y los episodios de razonamiento de agentes que lo
    produjeron o citaron — la traza completa de "¿cómo llegué a esto?".
    """
    return await client.explain(node_id, max_depth=max_depth)
