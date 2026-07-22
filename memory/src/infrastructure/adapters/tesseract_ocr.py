import asyncio
import io

import pypdfium2 as pdfium
import pytesseract
from PIL import Image
from pypdf import PdfReader

from memory.src.application.ports.ocr import OcrPort


class TesseractOcr(OcrPort):
    """
    Implementación real de OcrPort (F3-T6) vía Tesseract (`pytesseract`, requiere el binario
    `tesseract-ocr` en el PATH del sistema/imagen). Para PDFs, primero intenta extraer la capa
    de texto nativa (rápido, sin OCR); si el PDF es un escaneo sin texto, rasteriza cada página
    (`pypdfium2`, sin depender de poppler) y aplica OCR sobre la imagen resultante.
    """
    def __init__(self, languages: str = "spa+eng"):
        self.languages = languages

    async def extract_text(self, file_bytes: bytes, mime_type: str) -> str:
        if mime_type == "application/pdf":
            return await asyncio.to_thread(self._extract_from_pdf, file_bytes)
        return await asyncio.to_thread(self._extract_from_image, file_bytes)

    def _extract_from_image(self, file_bytes: bytes) -> str:
        image = Image.open(io.BytesIO(file_bytes))
        return pytesseract.image_to_string(image, lang=self.languages).strip()

    def _extract_from_pdf(self, file_bytes: bytes) -> str:
        reader = PdfReader(io.BytesIO(file_bytes))
        native_text = "\n".join(page.extract_text() or "" for page in reader.pages).strip()
        if native_text:
            return native_text
        return self._ocr_scanned_pdf(file_bytes)

    def _ocr_scanned_pdf(self, file_bytes: bytes) -> str:
        pdf = pdfium.PdfDocument(file_bytes)
        pages_text = []
        for page in pdf:
            bitmap = page.render(scale=2.0)
            image = bitmap.to_pil()
            pages_text.append(pytesseract.image_to_string(image, lang=self.languages))
        return "\n".join(pages_text).strip()
