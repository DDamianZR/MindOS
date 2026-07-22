"""
F3-T6: TesseractOcr es un OcrPort real (pytesseract + el binario `tesseract-ocr`). No
verificable en este entorno de desarrollo (el binario no está instalado en este host — sí lo
estará en la imagen Docker, que instala `tesseract-ocr`/`tesseract-ocr-spa` vía apt) — se salta
en tiempo de ejecución si el binario no está disponible, en vez de fallar el suite completo.
"""
import io
import shutil

import pytest

pytestmark = pytest.mark.integration

if not shutil.which("tesseract"):
    pytest.skip("El binario 'tesseract' no está instalado en este entorno.", allow_module_level=True)

from PIL import Image, ImageDraw  # noqa: E402

from memory.src.infrastructure.adapters.tesseract_ocr import TesseractOcr  # noqa: E402


def _text_image_bytes(text: str) -> bytes:
    image = Image.new("RGB", (400, 100), color="white")
    draw = ImageDraw.Draw(image)
    draw.text((10, 30), text, fill="black")
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


@pytest.mark.asyncio
async def test_extracts_text_from_a_simple_image():
    ocr = TesseractOcr()
    result = await ocr.extract_text(_text_image_bytes("MindOS"), "image/png")
    assert "mindos" in result.lower()


@pytest.mark.asyncio
async def test_extracts_native_text_layer_from_a_text_pdf_without_ocr():
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)

    ocr = TesseractOcr()
    # Un PDF en blanco no tiene capa de texto ni contenido visible: cae al fallback de OCR
    # sobre la página rasterizada, y debe devolver una cadena vacía sin lanzar excepciones.
    result = await ocr.extract_text(buf.getvalue(), "application/pdf")
    assert result == ""
