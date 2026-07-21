from abc import ABC, abstractmethod


class EmbeddingPort(ABC):
    """
    Puerto para la generación de vectores de características (embeddings).
    """
    @abstractmethod
    async def embed_query(self, text: str) -> list[float]:
        """
        Genera el vector numérico para una consulta corta de búsqueda.
        """
        pass

    @abstractmethod
    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """
        Genera vectores numéricos para bloques de texto/documentos de forma optimizada.
        """
        pass
