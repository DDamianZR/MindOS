from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from mindos_mcp import tools
from mindos_mcp.config import settings
from mindos_mcp.mindos_client import MindOSClient

client = MindOSClient(settings.GATEWAY_URL, settings.MINDOS_API_KEY)

mcp = FastMCP(
    "MindOS",
    instructions=(
        "MindOS es un sistema operativo de conocimiento personal: memoria de largo plazo con "
        "explicabilidad ('¿cómo llegué a esto?') y detección de contradicciones. Usa "
        "mindos_search/mindos_context para fundamentar respuestas en lo que el usuario ya sabe, "
        "mindos_ingest para capturar información nueva, y mindos_ask_cognitive/mindos_explain "
        "para consultar su historial de pensamiento."
    ),
    host="0.0.0.0",
    port=settings.MCP_HTTP_PORT,
    # El Gateway (F3-T1) proxya /api/v1/{servicio}/... reconstruyendo el path completo hacia
    # el downstream (ver SERVICE_ROUTES) — para que un cliente remoto llegue a este server vía
    # GATEWAY_URL/api/v1/mcp/mcp, el endpoint real tiene que vivir exactamente ahí, no en el
    # "/mcp" por defecto del SDK.
    streamable_http_path="/api/v1/mcp/mcp",
)


@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "service": "mcp"})


@mcp.tool(name="mindos_search")
async def mindos_search(query: str, limit: int = 5) -> dict:
    """Busca en la memoria de conocimiento de MindOS por similitud semántica. Devuelve
    resultados con su node_id, contenido y score — cita el node_id de lo que uses."""
    return await tools.search(client, query, limit=limit)


@mcp.tool(name="mindos_ingest")
async def mindos_ingest(title: str, content: str, object_type: str = "note", source: str | None = None) -> dict:
    """Captura una nueva pieza de conocimiento en MindOS (nota, idea, hecho, decisión...).
    object_type: note, idea, fact, hypothesis, decision, document o concept. source (opcional):
    de dónde salió esta información en la conversación actual."""
    return await tools.ingest(client, title=title, content=content, object_type=object_type, source=source)


@mcp.tool(name="mindos_context")
async def mindos_context(query: str, limit: int = 5, depth: int = 1) -> dict:
    """Recupera un bundle de contexto GraphRAG (similitud + expansión de grafo + citas) para
    fundamentar una respuesta en el conocimiento existente de MindOS."""
    return await tools.context(client, query, limit=limit, depth=depth)


@mcp.tool(name="mindos_ask_cognitive")
async def mindos_ask_cognitive(question_type: str, params: dict) -> dict:
    """Responde una de las preguntas insignia de MindOS: past_thinking (topic, at),
    similar (node_id), decisions (topic), support (node_id), contradictions (topic),
    patterns (sin params). Para "¿cómo llegué a esto?" usa mindos_explain, no esta."""
    return await tools.ask_cognitive(client, question_type, params)


@mcp.tool(name="mindos_explain")
async def mindos_explain(node_id: str, max_depth: int = 3) -> dict:
    """Explica cómo se llegó a una conclusión: evidencias, decisiones y episodios de
    razonamiento de agentes que sustentan el nodo dado."""
    return await tools.explain(client, node_id, max_depth=max_depth)
