from abc import ABC, abstractmethod


class OcrPort(ABC):
    """
    Puerto para la extracción de texto a partir de archivos binarios (imágenes, PDFs).
    """
    @abstractmethod
    async def extract_text(self, file_bytes: bytes, mime_type: str) -> str:
        """
        Analiza los bytes del archivo y retorna el texto extraído.
        """
        pass
#
