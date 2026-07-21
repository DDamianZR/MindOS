import uuid


def new_id() -> uuid.UUID:
    """
    Genera un UUIDv7: identificador único ordenable temporalmente.

    A diferencia de UUIDv4, UUIDv7 incorpora un timestamp en sus bits altos, lo que lo
    hace ordenable por creación y mucho más eficiente como clave primaria/índice.

    Reemplaza cualquier generación de IDs basada en `hash()`, que era irreproducible
    (PYTHONHASHSEED cambia por proceso) y propensa a colisiones.

    Requiere Python 3.12+ (donde `uuid.uuid7` está disponible en la stdlib).
    """
    return uuid.uuid7()
