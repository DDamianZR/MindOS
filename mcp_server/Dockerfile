# Imagen del servidor MCP (F4-T2). Contexto de build = raíz del monorepo. El directorio se
# llama mcp_server/ (no mcp/) para no colisionar con el paquete del SDK oficial `mcp` — ver
# plan/NOTAS.md.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Paquetes locales del monorepo (editables) — capa cacheable
COPY schemas/ ./schemas/
COPY common/ ./common/
RUN pip install --no-cache-dir -e ./schemas -e ./common

# El servidor MCP en sí, instalado como paquete editable propio (mindos_mcp) — mismo motivo
# que arriba: mantiene su propio pyproject.toml en vez de un requirements.txt suelto porque
# necesita declararse como paquete instalable para no depender de PYTHONPATH=/app (que
# resolvería "mcp" al directorio en vez de al SDK si algo lo importara así por error).
COPY mcp_server/ ./mcp_server/
RUN pip install --no-cache-dir -e ./mcp_server

RUN useradd -m appuser && chown -R appuser /app
USER appuser

EXPOSE 8005

HEALTHCHECK --interval=10s --timeout=4s --start-period=20s --retries=5 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8005/health').status==200 else 1)"

CMD ["python", "-m", "mindos_mcp.main", "--transport", "streamable-http"]
