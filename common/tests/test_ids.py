"""
`new_id()` debe dar UUIDv7 válidos y ordenados por creación también en Python 3.12, donde
`uuid.uuid7` no existe (llegó en 3.14). Se prueba la implementación propia directamente.
"""
import time
import uuid

from mindos_common import ids


def test_fallback_produces_valid_uuid7():
    value = ids._uuid7()
    assert isinstance(value, uuid.UUID)
    assert value.version == 7
    assert value.variant == uuid.RFC_4122


def test_fallback_timestamp_matches_now():
    before = time.time_ns() // 1_000_000
    value = ids._uuid7()
    after = time.time_ns() // 1_000_000
    assert before <= value.int >> 80 <= after + 1


def test_fallback_ids_are_unique_and_sorted_by_creation():
    generated = [ids._uuid7() for _ in range(20_000)]  # muchos caen en el mismo milisegundo
    assert len(set(generated)) == len(generated)
    assert generated == sorted(generated)


def test_new_id_uses_stdlib_when_present_and_fallback_otherwise(monkeypatch):
    monkeypatch.setattr(ids, "_stdlib_uuid7", None)
    assert ids.new_id().version == 7
