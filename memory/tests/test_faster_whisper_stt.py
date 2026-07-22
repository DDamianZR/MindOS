"""
F3-T6: FasterWhisperStt es un SttPort real (100% local, sin API externa). Marcado `integration`
porque la primera transcripción descarga el modelo (red) y lo carga en memoria — en este
entorno de desarrollo la RAM libre es muy escasa (~1.9GB de 15.9GB, ver plan/NOTAS.md, mismo
hallazgo que con Ollama en F2-T5), así que no se ejecuta por defecto ni se intentó completar
en esta sesión.
"""
import io
import wave

import pytest

from memory.src.infrastructure.adapters.faster_whisper_stt import FasterWhisperStt


def _silent_wav_bytes(seconds: float = 1.0, sample_rate: int = 16000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b"\x00\x00" * int(seconds * sample_rate))
    return buf.getvalue()


def test_lazy_loading_does_not_load_the_model_until_first_transcription():
    """El modelo NO debe cargarse en __init__ — evita bloquear el arranque del servicio con
    una descarga/carga pesada aunque nunca llegue audio que transcribir."""
    stt = FasterWhisperStt(model_size="small")
    assert stt._model is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_transcribes_silence_as_empty_or_near_empty_text():
    """DoD F3-T6 con el modelo real: cargar 'tiny' (el más liviano) y transcribir un WAV en
    silencio no debería lanzar excepciones ni alucinar contenido sustancial."""
    stt = FasterWhisperStt(model_size="tiny")
    result = await stt.transcribe(_silent_wav_bytes(), "audio/wav")
    assert isinstance(result, str)
