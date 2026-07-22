"""
Punto de entrada del servidor MCP de MindOS (F4-T2).

Uso:
  python -m mindos_mcp.main --transport stdio             # clientes locales (Claude Desktop/Code)
  python -m mindos_mcp.main --transport streamable-http    # remoto, detrás del Gateway
"""
import argparse

import uvicorn

from mindos_mcp.auth_middleware import ApiKeyAuthMiddleware
from mindos_mcp.config import settings
from mindos_mcp.server import mcp


def main() -> None:
    parser = argparse.ArgumentParser(description="Servidor MCP de MindOS")
    parser.add_argument(
        "--transport", choices=["stdio", "streamable-http"], default="stdio",
        help="'stdio' para clientes locales (Claude Desktop/Code); "
             "'streamable-http' para acceso remoto detrás del Gateway",
    )
    args = parser.parse_args()

    if args.transport == "stdio":
        mcp.run(transport="stdio")
    else:
        app = ApiKeyAuthMiddleware(mcp.streamable_http_app(), settings.MCP_API_KEY)
        uvicorn.run(app, host="0.0.0.0", port=settings.MCP_HTTP_PORT)


if __name__ == "__main__":
    main()
