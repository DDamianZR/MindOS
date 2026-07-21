
import httpx
from mindos_common.logging import get_logger

from agents.src.application.ports.llm import LlmPort

logger = get_logger("ollama_llm")

class OllamaLlm(LlmPort):
    """
    Adaptador concreto de LlmPort que se comunica con una instancia local de Ollama.
    """
    def __init__(self, model_name: str = "llama3:8b", base_url: str = "http://localhost:11434", timeout: float = 180.0):
        self.model_name = model_name
        self.base_url = base_url
        # 180s por defecto: modelos con modo "thinking" (ej. qwen3:8b) pueden tardar >60s en
        # generar una respuesta, medido empíricamente (F2-T5).
        self.client = httpx.AsyncClient(timeout=timeout)

    async def generate(
        self,
        prompt: str,
        system_instruction: str | None = None,
        json_mode: bool = False
    ) -> str:
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False
        }

        if system_instruction:
            payload["system"] = system_instruction

        if json_mode:
            payload["format"] = "json"

        try:
            logger.debug("Enviando petición a Ollama (/api/generate)", model=self.model_name, json_mode=json_mode)
            response = await self.client.post(url, json=payload)
            response.raise_for_status()

            data = response.json()
            return data.get("response", "")

        except Exception as e:
            logger.error("Fallo de comunicación con Ollama", error=str(e), url=url)
            raise RuntimeError(f"Error de inferencia local en Ollama: {str(e)}") from e

    async def chat(
        self,
        messages: list[dict[str, str]],
        json_mode: bool = False
    ) -> str:
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": False
        }

        if json_mode:
            payload["format"] = "json"

        try:
            logger.debug("Enviando petición a Ollama (/api/chat)", model=self.model_name, json_mode=json_mode)
            response = await self.client.post(url, json=payload)
            response.raise_for_status()

            data = response.json()
            message_data = data.get("message", {})
            return message_data.get("content", "")

        except Exception as e:
            logger.error("Fallo de comunicación con Ollama chat", error=str(e), url=url)
            raise RuntimeError(f"Error de inferencia conversacional en Ollama: {str(e)}") from e

    async def close(self) -> None:
        """Cierra el cliente HTTP."""
        await self.client.aclose()
