import json

from agents.src.application.ports.llm import LlmPort


class MockLlm(LlmPort):
    """
    Mock de LlmPort para simular razonamiento e inferencia en el servicio de agentes.
    """
    async def generate(
        self,
        prompt: str,
        system_instruction: str | None = None,
        json_mode: bool = False
    ) -> str:
        if json_mode:
            # Buscar coincidencia exacta para planner (evitando 'planificada')
            if "planner" in prompt.lower() or "generar un plan" in prompt.lower() or "plan_id" in prompt.lower() and "approved" not in prompt.lower():
                return json.dumps({
                    "plan_id": "018b10f8-e1a5-7b18-b2a6-382a93414902",
                    "goal": "Revisar configuración de Traefik",
                    "steps": [
                        {
                            "step_id": 1,
                            "task": "Buscar en memoria el archivo de configuración de Traefik",
                            "capability_name": "search_knowledge",
                            "expected_output": "Encontrar la nota 'Configuración Traefik' con su puerto.",
                            "status": "pending"
                        },
                        {
                            "step_id": 2,
                            "task": "Enviar mensaje informando del puerto al usuario",
                            "capability_name": "send_chat_message",
                            "expected_output": "Mensaje enviado con éxito.",
                            "status": "pending"
                        }
                    ]
                })
            elif "reviewer" in prompt.lower() or "evaluador" in prompt.lower() or "approved" in prompt.lower():
                return json.dumps({
                    "approved": True,
                    "feedback": "La ejecución cumple plenamente con los objetivos del paso."
                })
            return json.dumps({"response": "Mocked JSON"})
        return "Mocked text"

    async def chat(
        self,
        messages: list[dict[str, str]],
        json_mode: bool = False
    ) -> str:
        last_text = messages[-1]["content"] if messages else ""
        return await self.generate(last_text, json_mode=json_mode)
