from enum import Enum


class ObjectType(str, Enum):
    """
    Tipo de un Objeto Cognitivo en el Knowledge Graph de MindOS.

    Cubre tanto entidades de conocimiento "pasivas" (nota, documento, concepto, persona...) como
    los nodos del Thinking Graph (pregunta, hipótesis, investigación, evidencia, decisión,
    resultado, aprendizaje — ver Fase 2), para no requerir una migración de esquema al llegar ahí.

    Se almacena como `String`, no como ENUM nativo de Postgres: añadir un tipo nuevo no debe
    requerir un `ALTER TYPE`. La validación de pertenencia al catálogo ocurre en esta capa (Pydantic).
    """
    NOTE = "note"
    IDEA = "idea"
    DOCUMENT = "document"
    CONVERSATION = "conversation"
    CONCEPT = "concept"
    PERSON = "person"
    PROJECT = "project"
    TASK = "task"
    RESOURCE = "resource"
    TECHNOLOGY = "technology"
    EVENT = "event"
    OBSERVATION = "observation"
    EXPERIENCE = "experience"

    # Thinking Graph (Fase 2) — declarados ya para evitar una migración de enum a futuro.
    QUESTION = "question"
    HYPOTHESIS = "hypothesis"
    INVESTIGATION = "investigation"
    EVIDENCE = "evidence"
    DECISION = "decision"
    OUTCOME = "outcome"
    LEARNING = "learning"
    FACT = "fact"
    INSIGHT = "insight"


class ObjectStatus(str, Enum):
    """
    Estado de ciclo de vida de una versión de Objeto Cognitivo.

    Independiente de `ObjectType`: p.ej. un objeto `HYPOTHESIS` puede estar `active` y, tras
    acumular evidencia suficiente, promoverse a `status=fact` (ver Fase 5, lifecycle F5-T4)
    sin necesariamente cambiar su `object_type`.
    """
    DRAFT = "draft"
    ACTIVE = "active"
    HYPOTHESIS = "hypothesis"
    FACT = "fact"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"
