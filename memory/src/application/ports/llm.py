from abc import ABC, abstractmethod


class LlmPort(ABC):
    """
    Puerto para la ejecución de modelos de lenguaje (LLM).
    Abstrae proveedores locales (Ollama, llama.cpp) y remotos (Anthropic, OpenAI).
    """
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_instruction: str | None = None,
        json_mode: bool = False
    ) -> str:
        """
        Ejecuta una petición de generación de texto simple.
        """
        pass

    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, str]],
        json_mode: bool = False
    ) -> str:
        """
        Ejecuta una petición conversacional con historial estructurado de roles.
        """
        pass
