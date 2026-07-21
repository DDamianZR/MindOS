import json

from mindos_schemas.api.v1.agent_dto import GeneratePlanResponse
from mindos_schemas.capabilities import Capability

from agents.src.application.ports.llm import LlmPort
from agents.src.domain.planner.planner import Planner


class LlmPlanner(Planner):
    """
    Implementación concreta de Planner usando un LlmPort.
    Formula prompts estruturados indicando la meta, el contexto unificado y las herramientas disponibles.
    """
    def __init__(self, llm: LlmPort):
        self.llm = llm

    async def plan(
        self,
        goal: str,
        context: str,
        available_capabilities: list[Capability]
    ) -> GeneratePlanResponse:

        # Mapear capacidades a texto explicativo
        caps_desc = "\n".join([
            f"- Nombre: {c.name}\n  Descripción: {c.description}\n  Parámetros: {c.parameters_schema}"
            for c in available_capabilities
        ])

        prompt = (
            f"Actúa como el agente Planificador (Planner) de MindOS.\n"
            f"Tu meta es descomponer el objetivo del usuario en una serie ordenada de pasos lógicos.\n"
            f"Para cada paso, debes seleccionar la capacidad más adecuada de la lista provista.\n\n"
            f"Objetivo del Usuario: {goal}\n\n"
            f"Contexto disponible:\n{context}\n\n"
            f"Capacidades Registradas:\n{caps_desc}\n\n"
            f"Responde OBLIGATORIAMENTE en formato JSON con la siguiente estructura:\n"
            f"{{\n"
            f"  \"plan_id\": \"UUIDv7 generado\",\n"
            f"  \"goal\": \"Objetivo del usuario\",\n"
            f"  \"steps\": [\n"
            f"    {{\n"
            f"      \"step_id\": 1,\n"
            f"      \"task\": \"Descripción de la tarea a realizar\",\n"
            f"      \"capability_name\": \"Nombre de la capacidad\",\n"
            f"      \"expected_output\": \"Resultado esperado para aprobar el paso\",\n"
            f"      \"status\": \"pending\"\n"
            f"    }}\n"
            f"  ]\n"
            f"}}"
        )

        response_text = await self.llm.generate(prompt, json_mode=True)
        data = json.loads(response_text)

        return GeneratePlanResponse(**data)
