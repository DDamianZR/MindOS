import contextvars
from uuid import UUID

# Variable de contexto local para almacenar el correlation_id de forma segura en tareas concurrentes/asíncronas
_correlation_id_ctx = contextvars.ContextVar("correlation_id", default=None)

def set_correlation_id(correlation_id: UUID) -> contextvars.Token:
    """
    Establece el ID de correlación activo en el contexto actual.
    Retorna un token necesario para restaurar el contexto previo más adelante si es necesario.
    """
    return _correlation_id_ctx.set(correlation_id)

def get_correlation_id() -> UUID | None:
    """
    Recupera el ID de correlación activo del contexto actual.
    Retorna None si no ha sido configurado.
    """
    return _correlation_id_ctx.get()

def clear_correlation_id(token: contextvars.Token) -> None:
    """
    Restaura el ID de correlación al valor anterior usando el token provisto.
    """
    _correlation_id_ctx.reset(token)
