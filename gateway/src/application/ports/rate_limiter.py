from abc import ABC, abstractmethod


class RateLimiterPort(ABC):
    """
    Puerto de rate-limit (F3-T1): ventana fija por clave (IP del cliente). `hit` registra una
    petición y devuelve si el llamador sigue DENTRO del límite.
    """
    @abstractmethod
    async def hit(self, key: str, limit: int, window_seconds: int) -> bool:
        """Registra una petición para `key` y retorna True si aún está dentro del límite."""
        pass
