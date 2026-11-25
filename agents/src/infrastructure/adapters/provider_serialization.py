"""Serialización del historial del proveedor para guardarlo sin alterar lo que se reenvía."""

from typing import Any


def to_jsonable(value: Any) -> Any:
    """Convierte objetos del SDK a JSON y recorre listas y dicts; el resto queda igual.

    `to_dict(mode="json")` es lo que el SDK escribe en el cuerpo de la petición cuando
    recibe el objeto: conserva la firma del razonamiento y omite los campos que la API
    no envió. `model_dump` sin ese criterio, o `exclude_none`, cambiaría el historial
    que se reenvía y el proveedor puede descartar el razonamiento previo.
    """
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return to_jsonable(to_dict(mode="json"))
    if isinstance(value, dict):
        return {key: to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    return value
