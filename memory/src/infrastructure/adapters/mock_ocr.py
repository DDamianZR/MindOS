from memory.src.application.ports.ocr import OcrPort


class MockOcr(OcrPort):
    """
    Mock de OcrPort para simular extracción de texto de imágenes o PDFs.
    """
    async def extract_text(self, file_bytes: bytes, mime_type: str) -> str:
        # Retornar una simulación de texto basada en el tamaño de los bytes
        return f"[Simulación OCR para archivo {mime_type} de {len(file_bytes)} bytes]\nTexto extraído del documento."
