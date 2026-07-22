# Imagen del Memory Service. Contexto de build = raíz del monorepo.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

WORKDIR /app

# F3-T6: binario de Tesseract (pytesseract es solo un wrapper, no funciona sin esto) + paquete
# de idioma español, ya que MindOS captura contenido mayormente en español.
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr tesseract-ocr-spa \
    && rm -rf /var/lib/apt/lists/*

# 1. Paquetes locales del monorepo (editables) — capa cacheable
COPY schemas/ ./schemas/
COPY common/ ./common/
RUN pip install --no-cache-dir -e ./schemas -e ./common

# 2. Dependencias del servicio — capa cacheable
COPY memory/requirements.txt ./memory/requirements.txt
RUN pip install --no-cache-dir -r memory/requirements.txt uvicorn[standard]

# 3. Código del servicio
COPY memory/ ./memory/

# Usuario no-root
RUN useradd -m appuser && chown -R appuser /app
USER appuser

EXPOSE 8001

HEALTHCHECK --interval=10s --timeout=4s --start-period=20s --retries=5 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8001/health').status==200 else 1)"

CMD ["uvicorn", "memory.src.main:app", "--host", "0.0.0.0", "--port", "8001"]
