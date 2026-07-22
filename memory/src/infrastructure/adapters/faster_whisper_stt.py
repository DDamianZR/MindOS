import asyncio
import tempfile

from faster_whisper import WhisperModel

from memory.src.application.ports.stt import SttPort

# WhatsApp entrega notas de voz como Opus dentro de un contenedor Ogg por defecto.
_SUFFIX_BY_MIME = {
    "audio/ogg": ".ogg", "audio/opus": ".ogg", "audio/mpeg": ".mp3", "audio/mp3": ".mp3",
    "audio/mp4": ".m4a", "audio/wav": ".wav", "audio/x-wav": ".wav", "audio/webm": ".webm",
}


class FasterWhisperStt(SttPort):
    """
    Implementación real de SttPort (F3-T6) vía `faster-whisper` (CTranslate2), 100% local —
    sin llamadas a APIs externas de transcripción. El modelo se carga perezosamente en el
    primer uso (no en `__init__`): cargarlo de entrada bloquearía el arranque del servicio con
    una descarga/carga pesada aunque nunca llegue audio que transcribir.
    """
    def __init__(self, model_size: str = "small", device: str = "cpu", compute_type: str = "int8"):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self._model: WhisperModel | None = None

    def _get_model(self) -> WhisperModel:
        if self._model is None:
            self._model = WhisperModel(self.model_size, device=self.device, compute_type=self.compute_type)
        return self._model

    async def transcribe(self, file_bytes: bytes, mime_type: str) -> str:
        return await asyncio.to_thread(self._transcribe_sync, file_bytes, mime_type)

    def _transcribe_sync(self, file_bytes: bytes, mime_type: str) -> str:
        model = self._get_model()
        suffix = _SUFFIX_BY_MIME.get(mime_type, ".ogg")
        with tempfile.NamedTemporaryFile(suffix=suffix) as tmp:
            tmp.write(file_bytes)
            tmp.flush()
            segments, _info = model.transcribe(tmp.name, language=None)  # autodetección de idioma
            return " ".join(segment.text.strip() for segment in segments).strip()
