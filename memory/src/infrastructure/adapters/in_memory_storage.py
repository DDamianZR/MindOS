
from memory.src.application.ports.storage import StoragePort


class InMemoryStorage(StoragePort):
    """
    Implementación en memoria de StoragePort para simular persistencia de archivos.
    """
    def __init__(self):
        self._storage: dict[str, bytes] = {}

    async def save(self, file_path: str, content: bytes) -> str:
        uri = f"storage://{file_path}"
        self._storage[uri] = content
        return uri

    async def get(self, uri: str) -> bytes:
        if uri in self._storage:
            return self._storage[uri]
        raise FileNotFoundError(f"Archivo no encontrado en almacenamiento: {uri}")

    async def delete(self, uri: str) -> bool:
        if uri in self._storage:
            del self._storage[uri]
            return True
        return False
