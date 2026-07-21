from mindos_common.ids import new_id

from memory.src.infrastructure.adapters.in_memory_database import InMemoryDatabase


async def test_version_lineage_points_to_previous_version():
    """
    F0-T3: al versionar un nodo, `parent_version_id` de v2 debe apuntar al `version_id` de v1
    (la versión previa), NO al node_id. Verifica que el lineaje histórico es reconstruible.
    """
    db = InMemoryDatabase()
    node_id = new_id()
    await db.save_node(node_id, "note")

    # v1
    version_id_1 = new_id()
    await db.save_node_version(
        node_id=node_id, version_id=version_id_1, version=1,
        title="v1", content="contenido inicial", author="damian", metadata={},
        parent_version_id=None,
    )

    latest = await db.get_latest_node_version(node_id)
    assert latest["version"] == 1
    assert latest["version_id"] == version_id_1
    assert latest["parent_version_id"] is None

    # v2 (encadena al version_id de v1)
    version_id_2 = new_id()
    await db.save_node_version(
        node_id=node_id, version_id=version_id_2, version=2,
        title="v2", content="contenido corregido", author="damian", metadata={},
        parent_version_id=latest["version_id"],
    )

    versions = await db.get_node_versions(node_id)
    assert len(versions) == 2

    v1, v2 = versions[0], versions[1]
    assert v2["version"] == 2
    assert v2["parent_version_id"] == version_id_1, "v2 debe apuntar al version_id de v1"
    assert v2["parent_version_id"] != node_id, "el padre nunca debe ser el node_id"
    assert v1["version_id"] != v2["version_id"], "cada versión tiene su propio id único"


async def test_uuid7_is_time_ordered():
    """F0-T2: dos ids consecutivos deben ser ordenables temporalmente (v7)."""
    a, b = new_id(), new_id()
    assert a.version == 7
    assert b.version == 7
    assert a < b or a == b  # v7 es monotónicamente creciente por timestamp
