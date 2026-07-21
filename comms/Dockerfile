# Imagen del Comms Service. Contexto de build = raíz del monorepo.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

WORKDIR /app

# 1. Paquetes locales del monorepo (editables) — capa cacheable
COPY schemas/ ./schemas/
COPY common/ ./common/
RUN pip install --no-cache-dir -e ./schemas -e ./common

# 2. Dependencias del servicio — capa cacheable
COPY comms/requirements.txt ./comms/requirements.txt
RUN pip install --no-cache-dir -r comms/requirements.txt uvicorn[standard]

# 3. Código del servicio
COPY comms/ ./comms/

RUN useradd -m appuser && chown -R appuser /app
USER appuser

EXPOSE 8003

HEALTHCHECK --interval=10s --timeout=4s --start-period=20s --retries=5 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8003/health').status==200 else 1)"

CMD ["uvicorn", "comms.src.main:app", "--host", "0.0.0.0", "--port", "8003"]
