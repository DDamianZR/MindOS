from enum import Enum


class RelationType(str, Enum):
    """
    Catálogo tipado de relaciones del Knowledge Graph / Thinking Graph de MindOS.

    Se almacena como `String` (no ENUM nativo) por el mismo motivo que `ObjectType`: extender
    el catálogo no debe requerir una migración de esquema. `save_relation` valida pertenencia
    a este catálogo (o acepta `CUSTOM` explícito) — ver F1-T6.
    """
    PART_OF = "PART_OF"
    RELATED_TO = "RELATED_TO"
    DERIVED_FROM = "DERIVED_FROM"
    SUPPORTS = "SUPPORTS"
    CONTRADICTS = "CONTRADICTS"
    CAUSED_BY = "CAUSED_BY"
    DUPLICATE_OF = "DUPLICATE_OF"
    MENTIONS = "MENTIONS"
    ANSWERS = "ANSWERS"
    EVIDENCES = "EVIDENCES"
    DECIDES = "DECIDES"
    LEADS_TO = "LEADS_TO"
    CUSTOM = "CUSTOM"
