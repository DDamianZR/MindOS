import logging
import os
import sys
from typing import Any

import structlog

from mindos_common.context import get_correlation_id


def inject_correlation_id(_, __, event_dict: dict[str, Any]) -> dict[str, Any]:
    """
    Procesador para structlog que inyecta automáticamente el correlation_id
    del contexto actual en todos los registros de logs.
    """
    correlation_id = get_correlation_id()
    if correlation_id:
        event_dict["correlation_id"] = str(correlation_id)
    return event_dict

def configure_logging(service_name: str, log_level: str = "INFO") -> None:
    """
    Configura el logging estructurado del sistema utilizando structlog.
    Si la variable de entorno MINDOS_ENV es 'production', formatea en JSON.
    En desarrollo, utiliza un formateador legible por humanos con colores.
    """
    # Determinamos nivel de log numérico de stdlib logging
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        inject_correlation_id,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    is_production = os.getenv("MINDOS_ENV", "development").lower() == "production"

    if is_production:
        # Formateador JSON en producción para recolección de logs
        processor = structlog.processors.JSONRenderer()
    else:
        # Consola bonita y coloreada en desarrollo
        processor = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=shared_processors + [processor],
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        cache_logger_on_first_use=True,
    )

    # Redirigir logs estándar de Python stdlib a structlog
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=numeric_level,
    )

    # Inyectar el nombre del servicio como variable de contexto global
    structlog.contextvars.bind_contextvars(service=service_name)

def get_logger(name: str) -> Any:
    """
    Retorna una instancia de logger estructurado para el módulo dado.
    """
    return structlog.get_logger(name)
