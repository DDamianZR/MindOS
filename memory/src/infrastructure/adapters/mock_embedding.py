import hashlib
import math

from memory.src.application.ports.embedding import EmbeddingPort


class MockEmbedding(EmbeddingPort):
    """
    Mock de EmbeddingPort que retorna vectores de 384 dimensiones de forma semi-determinista.
    Utiliza el hash MD5 del texto para rellenar los valores del vector, permitiendo
    que la similitud coseno funcione de forma predecible para pruebas de RAG.
    """
    def __init__(self, dimension: int = 384):
        self.dimension = dimension

    async def embed_query(self, text: str) -> list[float]:
        return self._generate_vector(text)

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._generate_vector(t) for t in texts]

    def _generate_vector(self, text: str) -> list[float]:
        # Generar un hash determinista a partir del texto
        hash_val = hashlib.md5(text.encode("utf-8")).digest()

        vector = []
        # Rellenar las dimensiones repitiendo el hash MD5
        for i in range(self.dimension):
            # Obtener un valor pseudo-aleatorio determinista entre -1.0 y 1.0
            byte_idx = (i * 7) % len(hash_val)
            val = (hash_val[byte_idx] / 127.5) - 1.0
            vector.append(val)

        # Normalizar el vector para que tenga longitud unitaria
        magnitude = math.sqrt(sum(x * x for x in vector))
        if magnitude > 0:
            vector = [x / magnitude for x in vector]

        return vector

# Fin del módulo mock_embedding
