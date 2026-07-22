from typing import Any

import httpx

from comms.src.application.ports.communication import CommunicationOutboundPort


class WhatsAppOutboundAdapter(CommunicationOutboundPort):
    """Entrega real de mensajes salientes por WhatsApp (F3-T7): llama al `POST /send` del
    adaptador Node (F3-T4), que ya sabe traducir un `recipient_id` a JID y usar el socket activo."""
    def __init__(self, http_client: httpx.AsyncClient, base_url: str):
        self.http_client = http_client
        self.base_url = base_url.rstrip("/")

    async def send(self, recipient_id: str, text: str) -> dict[str, Any]:
        response = await self.http_client.post(
            f"{self.base_url}/send", json={"recipient_id": recipient_id, "text": text},
        )
        response.raise_for_status()
        return response.json()
