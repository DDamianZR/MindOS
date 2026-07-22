import asyncio
import os
import uuid

from memory.src.application.ports.storage import StoragePort


class LocalFsStorage(StoragePort):
    """
    Implementación real de StoragePort (F3-T6) sobre el sistema de archivos local, con URIs
    estables `file://<base_dir>/<archivo>`. Adecuada para un solo host — para múltiples
    réplicas o almacenamiento desacoplado del host, usar `MinioStorage`.
    """
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)

    async def save(self, file_path: str, content: bytes) -> str:
        return await asyncio.to_thread(self._save_sync, file_path, content)

    def _save_sync(self, file_path: str, content: bytes) -> str:
        # Nombre plano prefijado con un uuid: evita colisiones y neutraliza path traversal
        # (basename() descarta cualquier "../" que traiga el nombre original).
        safe_name = f"{uuid.uuid4().hex}_{os.path.basename(file_path)}"
        full_path = os.path.join(self.base_dir, safe_name)
        with open(full_path, "wb") as f:
            f.write(content)
        return f"file://{full_path}"

    async def get(self, uri: str) -> bytes:
        return await asyncio.to_thread(self._get_sync, uri)

    def _get_sync(self, uri: str) -> bytes:
        with open(self._uri_to_path(uri), "rb") as f:
            return f.read()

    async def delete(self, uri: str) -> bool:
        return await asyncio.to_thread(self._delete_sync, uri)

    def _delete_sync(self, uri: str) -> bool:
        path = self._uri_to_path(uri)
        if os.path.exists(path):
            os.remove(path)
            return True
        return False

    def _uri_to_path(self, uri: str) -> str:
        if not uri.startswith("file://"):
            raise ValueError(f"URI no reconocida por LocalFsStorage: {uri}")
        return uri[len("file://"):]
