from uuid import UUID

from pydantic import BaseModel, Field


class PlanStep(BaseModel):
    """
    Representación de un paso individual en un plan de ejecución de agente
    """
    step_id: int = Field(..., description="ID secuencial del paso")
    task: str = Field(..., description="Descripción detallada de la tarea a realizar")
    capability_name: str | None = Field(
        default=None,
        description="Nombre de la capacidad registrada recomendada para resolver el paso"
    )
    expected_output: str = Field(..., description="Resultado esperado del paso para que sea considerado válido")
    status: str = Field(default="pending", description="Estado del paso (pending, running, completed, failed)")
    actual_output: str | None = Field(default=None, description="Resultado real obtenido en la ejecución")


class GeneratePlanRequest(BaseModel):
    """
    DTO para solicitar la generación de un plan al agente Planner
    """
    goal: str = Field(..., description="Meta u objetivo final del usuario (ej: 'Revisar la configuración de Traefik')")
    context: str = Field(..., description="Contexto unificado provisto por el ContextBuilder")


class GeneratePlanResponse(BaseModel):
    """
    DTO que contiene el plan estructurado retornado por el Planner
    """
    plan_id: UUID = Field(..., description="ID único (UUIDv7) asignado al plan de ejecución")
    goal: str = Field(..., description="Meta original")
    steps: list[PlanStep] = Field(..., description="Lista ordenada de pasos necesarios para lograr la meta")


class ReviewStepRequest(BaseModel):
    """
    DTO enviado al Reviewer para evaluar el resultado de un paso ejecutado
    """
    plan_id: UUID = Field(..., description="ID del plan actual")
    step_id: int = Field(..., description="ID del paso evaluado")
    task: str = Field(..., description="La tarea planificada")
    expected_output: str = Field(..., description="El resultado que se esperaba")
    actual_output: str = Field(..., description="El resultado real provisto por el Executor")


class ReviewStepResponse(BaseModel):
    """
    DTO de respuesta del Reviewer indicando si el paso fue superado o si requiere corrección
    """
    approved: bool = Field(..., description="Indica si la ejecución cumple con la expectativa del plan")
    feedback: str | None = Field(
        default=None,
        description="Retroalimentación o correcciones si la aprobación fue rechazada (approved=False)"
    )
