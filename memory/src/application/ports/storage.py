from abc import ABC, abstractmethod


class StoragePort(ABC):
    """
    Puerto para la persistencia física de archivos binarios (storage/).
    """
    @abstractmethod
    async def save(self, file_path: str, content: bytes) -> str:
        """
        Guarda el archivo en el sistema de almacenamiento persistente y retorna su URI.
        """
        pass

    @abstractmethod
    async def get(self, uri: str) -> bytes:
        """
        Recupera los bytes de un archivo a partir de su URI.
        """
        pass

    @abstractmethod
    async def delete(self, uri: str) -> bool:
        """
        Elimina un archivo físico del almacenamiento.
        """
        pass
#
