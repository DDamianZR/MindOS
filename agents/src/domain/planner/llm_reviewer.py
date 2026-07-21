import json

from mindos_schemas.api.v1.agent_dto import ReviewStepResponse

from agents.src.application.ports.llm import LlmPort
from agents.src.domain.planner.reviewer import Reviewer


class LlmReviewer(Reviewer):
    """
    Implementación concreta de Reviewer usando un LlmPort.
    Evalúa de forma analítica el resultado de una acción del executor comparándolo con la expectativa del plan.
    """
    def __init__(self, llm: LlmPort):
        self.llm = llm

    async def review_step(
        self,
        task: str,
        expected_output: str,
        actual_output: str
    ) -> ReviewStepResponse:

        prompt = (
            f"Actúa como el evaluador (Reviewer) de tareas de MindOS.\n"
            f"Tu rol es contrastar la salida real obtenida frente a la expectativa y determinar si el paso fue exitoso.\n\n"
            f"Tarea Planificada: {task}\n"
            f"Resultado Esperado: {expected_output}\n"
            f"Resultado Real Obtenido: {actual_output}\n\n"
            f"Responde OBLIGATORIAMENTE en formato JSON con la siguiente estructura:\n"
            f"{{\n"
            f"  \"approved\": true/false,\n"
            f"  \"feedback\": \"Retroalimentación detallada si fue desaprobado (approved=false) o nulo si fue aprobado\"\n"
            f"}}"
        )

        response_text = await self.llm.generate(prompt, json_mode=True)
        data = json.loads(response_text)
        return ReviewStepResponse(**data)
