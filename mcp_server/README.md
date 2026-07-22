# MindOS MCP Server (F4-T2)

Expone MindOS como herramientas [MCP](https://modelcontextprotocol.io) para asistentes externos
(Claude Desktop, Claude Code, y cualquier otro cliente MCP): la memoria de largo plazo de
MindOS queda disponible para que un asistente busque, capture, y explique su razonamiento.

El paquete Python se llama `mindos_mcp` (no `mcp`, que colisionaría con el
[SDK oficial](https://pypi.org/project/mcp/), del que este servidor depende) — ver
`plan/NOTAS.md`, entrada F4-T2.

## Tools expuestas

| Tool | Qué hace |
|---|---|
| `mindos_search(query, limit=5)` | Búsqueda semántica en la memoria de conocimiento, con citas. |
| `mindos_ingest(title, content, object_type="note", source=None)` | Captura una nueva pieza de conocimiento. |
| `mindos_context(query, limit=5, depth=1)` | Bundle de contexto GraphRAG (similitud + expansión de grafo + citas). |
| `mindos_ask_cognitive(question_type, params)` | Las 7 preguntas insignia (menos "cómo llegué a esto", ver abajo). |
| `mindos_explain(node_id, max_depth=3)` | "¿Cómo llegué a esta conclusión?" — evidencias, decisiones, episodios. |

El servidor habla **siempre** con MindOS a través del Gateway (`GATEWAY_URL` + `MINDOS_API_KEY`,
igual que cualquier otro cliente externo) — nunca se salta el único punto de entrada seguro
(F3-T1), aunque corra dentro del mismo stack Docker.

## Transportes

- **stdio**: para clientes locales (Claude Desktop, Claude Code) que arrancan el servidor como
  subproceso. Sin autenticación propia — la seguridad la da quien controla el proceso local.
- **streamable-http**: para acceso remoto, detrás del Gateway (`GATEWAY_URL/api/v1/mcp/mcp`).
  Además de la autenticación del Gateway, el propio transporte HTTP exige un header
  `X-Api-Key` (`MCP_API_KEY`) como defensa en profundidad — ver `mindos_mcp/auth_middleware.py`.

## Configuración (`.env` o variables de entorno)

```bash
GATEWAY_URL=http://localhost:8000       # o https://tu-dominio en producción
MINDOS_API_KEY=tu-api-key-de-gateway    # la misma que usa cualquier cliente del Gateway
MCP_HTTP_PORT=8005                      # solo para el transporte streamable-http
MCP_API_KEY=una-api-key-distinta        # defensa en profundidad del transporte HTTP
```

## Ejemplo de `mcp.json`

### Local (stdio) — Claude Desktop / Claude Code contra un MindOS en la misma máquina o accesible por red

```json
{
  "mcpServers": {
    "mindos": {
      "command": "python",
      "args": ["-m", "mindos_mcp.main", "--transport", "stdio"],
      "cwd": "/ruta/a/MindOS/mcp_server",
      "env": {
        "GATEWAY_URL": "http://localhost:8000",
        "MINDOS_API_KEY": "tu-api-key-de-gateway"
      }
    }
  }
}
```

### Remoto (streamable-http) — un MindOS ya desplegado, detrás de su Gateway público

```json
{
  "mcpServers": {
    "mindos": {
      "url": "https://tu-dominio.example.com/api/v1/mcp/mcp",
      "headers": {
        "X-Api-Key": "una-api-key-distinta"
      }
    }
  }
}
```

## Desarrollo

```bash
pip install -e ./schemas -e ./common -e ./mcp_server
python -m mindos_mcp.main --transport stdio            # o --transport streamable-http
pytest mcp_server/tests
```
