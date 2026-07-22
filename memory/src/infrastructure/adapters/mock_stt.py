from memory.src.application.ports.stt import SttPort


class MockStt(SttPort):
    """Mock de SttPort para simular transcripción de audio en tests/dev sin cargar un modelo real."""
    async def transcribe(self, file_bytes: bytes, mime_type: str) -> str:
        return f"[Simulación STT para audio {mime_type} de {len(file_bytes)} bytes] Transcripción de la nota de voz."
