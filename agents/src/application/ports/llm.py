from abc import ABC, abstractmethod


class LlmPort(ABC):
    """
    Puerto para ejecutar consultas LLM dentro del servicio de Agentes.
    """
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_instruction: str | None = None,
        json_mode: bool = False
    ) -> str:
        pass

    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, str]],
        json_mode: bool = False
    ) -> str:
        pass
