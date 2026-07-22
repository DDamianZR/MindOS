"""F3-T6: LocalFsStorage es un StoragePort real y completamente verificable sin Docker
(a diferencia de MinioStorage, que necesita un servidor MinIO real)."""
import pytest

from memory.src.infrastructure.adapters.local_fs_storage import LocalFsStorage


@pytest.mark.asyncio
async def test_save_then_get_roundtrips_the_same_bytes(tmp_path):
    storage = LocalFsStorage(str(tmp_path))
    uri = await storage.save("documento.pdf", b"contenido binario de prueba")
    assert uri.startswith("file://")

    retrieved = await storage.get(uri)
    assert retrieved == b"contenido binario de prueba"


@pytest.mark.asyncio
async def test_save_avoids_collisions_between_files_with_the_same_name(tmp_path):
    storage = LocalFsStorage(str(tmp_path))
    uri_a = await storage.save("nota.txt", b"primera version")
    uri_b = await storage.save("nota.txt", b"segunda version")

    assert uri_a != uri_b
    assert await storage.get(uri_a) == b"primera version"
    assert await storage.get(uri_b) == b"segunda version"


@pytest.mark.asyncio
async def test_save_neutralizes_path_traversal_in_the_filename(tmp_path):
    storage = LocalFsStorage(str(tmp_path))
    uri = await storage.save("../../etc/passwd", b"contenido")
    # El archivo debe quedar DENTRO de tmp_path, nunca escapar vía "../".
    assert str(tmp_path) in uri
    assert await storage.get(uri) == b"contenido"


@pytest.mark.asyncio
async def test_delete_removes_the_file_and_reports_success(tmp_path):
    storage = LocalFsStorage(str(tmp_path))
    uri = await storage.save("temporal.txt", b"borrame")
    assert await storage.delete(uri) is True

    with pytest.raises(FileNotFoundError):
        await storage.get(uri)


@pytest.mark.asyncio
async def test_delete_on_a_missing_file_reports_false_not_an_exception(tmp_path):
    storage = LocalFsStorage(str(tmp_path))
    assert await storage.delete("file:///no/existe/nunca.txt") is False


@pytest.mark.asyncio
async def test_get_rejects_a_uri_from_a_different_scheme(tmp_path):
    storage = LocalFsStorage(str(tmp_path))
    with pytest.raises(ValueError):
        await storage.get("minio://otro-bucket/archivo.txt")
