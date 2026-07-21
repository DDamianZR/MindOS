import httpx
from mindos_common.logging import get_logger

from memory.src.application.ports.embedding import EmbeddingPort

logger = get_logger("ollama_embedding")


class OllamaEmbedding(EmbeddingPort):
    """
    Adaptador concreto de EmbeddingPort que genera embeddings reales vía Ollama.

    Modelo por defecto: `nomic-embed-text` (768 dimensiones). El endpoint `/api/embeddings`
    acepta un `prompt` y devuelve `{"embedding": [...]}`.
    """
    def __init__(self, base_url: str, model: str = "nomic-embed-text"):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.client = httpx.AsyncClient(timeout=60.0)

    async def embed_query(self, text: str) -> list[float]:
        url = f"{self.base_url}/api/embeddings"
        try:
            response = await self.client.post(url, json={"model": self.model, "prompt": text})
            response.raise_for_status()
            embedding = response.json().get("embedding")
            if not embedding:
                raise RuntimeError("Ollama devolvió un embedding vacío")
            return embedding
        except Exception as e:
            logger.error("Fallo generando embedding en Ollama", error=str(e), url=url, model=self.model)
            raise RuntimeError(f"Error de embedding en Ollama: {str(e)}") from e

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        # Batch secuencial simple; la optimización por lotes (/api/embed) llega en el pipeline (Fase 3).
        return [await self.embed_query(t) for t in texts]

    async def close(self) -> None:
        await self.client.aclose()
