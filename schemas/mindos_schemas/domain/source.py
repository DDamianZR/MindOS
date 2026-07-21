from enum import Enum


class SourceKind(str, Enum):
    """
    Tipo de origen de una captura (provenance) — F1-T2. Permite responder
    "¿de dónde vino este conocimiento?" y es obligatorio para todo evento de comunicación (Fase 3).
    """
    WHATSAPP = "whatsapp"
    PDF = "pdf"
    IMAGE = "image"
    AUDIO = "audio"
    WEB = "web"
    CLI = "cli"
    API = "api"
    AGENT = "agent"
