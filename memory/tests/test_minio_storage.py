"""
F3-T6: MinioStorage es un StoragePort real sobre MinIO/S3. Necesita un servidor MinIO real
(solo disponible vía Docker, no en este entorno de desarrollo) — se salta en tiempo de
ejecución si no hay uno alcanzable, igual que los tests de integración con Postgres/Ollama
reales de fases anteriores.
"""
import httpx
import pytest

pytestmark = pytest.mark.integration

_MINIO_ENDPOINT = "localhost:9000"

try:
    httpx.get(f"http://{_MINIO_ENDPOINT}/minio/health/live", timeout=2.0)
except Exception:
    pytest.skip(f"No hay un servidor MinIO alcanzable en {_MINIO_ENDPOINT}.", allow_module_level=True)

from memory.src.infrastructure.adapters.minio_storage import MinioStorage  # noqa: E402


@pytest.fixture
def storage():
    return MinioStorage(
        endpoint=_MINIO_ENDPOINT, access_key="minioadmin", secret_key="minioadmin",
        bucket="mindos-test", secure=False,
    )


@pytest.mark.asyncio
async def test_save_then_get_roundtrips_the_same_bytes(storage):
    uri = await storage.save("documento.pdf", b"contenido binario de prueba")
    assert uri.startswith("minio://mindos-test/")
    assert await storage.get(uri) == b"contenido binario de prueba"


@pytest.mark.asyncio
async def test_delete_removes_the_object(storage):
    uri = await storage.save("temporal.txt", b"borrame")
    assert await storage.delete(uri) is True
