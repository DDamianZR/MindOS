from abc import ABC, abstractmethod


class SttPort(ABC):
    """
    Puerto para transcripción de audio a texto (F3-T6): notas de voz de WhatsApp u otros
    adjuntos de audio capturados por el pipeline de ingestión (F3-T5).
    """
    @abstractmethod
    async def transcribe(self, file_bytes: bytes, mime_type: str) -> str:
        """Transcribe el audio a texto. Retorna cadena vacía si no se detecta habla."""
        pass
