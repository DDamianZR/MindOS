import os
import threading
import time
import uuid


def new_id() -> uuid.UUID:
    """
    Genera un UUIDv7: identificador único ordenable temporalmente.

    A diferencia de UUIDv4, UUIDv7 incorpora un timestamp en sus bits altos, lo que lo
    hace ordenable por creación y mucho más eficiente como clave primaria/índice.

    Reemplaza cualquier generación de IDs basada en `hash()`, que era irreproducible
    (PYTHONHASHSEED cambia por proceso) y propensa a colisiones.

    `uuid.uuid7` llegó a la stdlib en Python 3.14; los servicios corren en 3.12 (imágenes
    `python:3.12-slim` y CI), así que ahí se usa la implementación propia de abajo.
    """
    return _stdlib_uuid7() if _stdlib_uuid7 else _uuid7()


_stdlib_uuid7 = getattr(uuid, "uuid7", None)

# Estado del generador propio: mismo esquema que CPython 3.14 (RFC 9562, método 1 de la §6.2):
# un contador de 42 bits que arranca en un valor aleatorio en cada milisegundo nuevo y se
# incrementa dentro del mismo milisegundo, para que los IDs de un proceso salgan ordenados.
_lock = threading.Lock()
_last_ms = 0
_counter = 0
_COUNTER_BITS = 42
_COUNTER_MAX = (1 << _COUNTER_BITS) - 1


def _new_counter() -> int:
    # El bit más alto empieza en 0 para dejar margen de incrementos antes de desbordar.
    return int.from_bytes(os.urandom(6), "big") & (_COUNTER_MAX >> 1)


def _uuid7() -> uuid.UUID:
    global _last_ms, _counter
    with _lock:
        now_ms = time.time_ns() // 1_000_000
        if now_ms > _last_ms:
            _last_ms = now_ms
            _counter = _new_counter()
        else:
            # Mismo milisegundo (o reloj que retrocede): se sigue contando sobre el último.
            _counter += 1
            if _counter > _COUNTER_MAX:
                _last_ms += 1
                _counter = _new_counter()
        timestamp_ms, counter = _last_ms, _counter

    tail = int.from_bytes(os.urandom(4), "big")  # 32 bits aleatorios al final
    counter_hi = (counter >> 30) & 0xFFF          # 12 bits -> rand_a
    counter_lo = counter & 0x3FFF_FFFF            # 30 bits -> parte alta de rand_b

    value = (timestamp_ms & 0xFFFF_FFFF_FFFF) << 80
    value |= 0x7 << 76            # versión 7
    value |= counter_hi << 64
    value |= 0b10 << 62           # variante RFC 9562
    value |= counter_lo << 32
    value |= tail
    return uuid.UUID(int=value)
