"""
Comando `mindos capture "..."` (F3-T3): captura texto desde la terminal. Pasa por el Gateway
como cualquier otro cliente externo (F3-T1, único punto de entrada seguro) llamando exactamente
al mismo `POST /api/v1/comms/inbound` que usa el adaptador REST — mismo endpoint, mismo formato,
mismo evento resultante, sin atajos.

Uso: python -m comms.src.cli capture "Idea: cachear las consultas frecuentes de reportes."
"""
import argparse
import asyncio
import sys

import httpx

from comms.src.config import settings


async def capture(
    text: str,
    client: httpx.AsyncClient,
    base_url: str,
    sender_id: str = "cli-local",
    recipient_id: str = "mindos",
    api_key: str | None = None,
) -> dict:
    headers = {"X-Api-Key": api_key} if api_key else {}
    response = await client.post(
        f"{base_url.rstrip('/')}/api/v1/comms/inbound",
        json={"provider": "cli", "sender_id": sender_id, "recipient_id": recipient_id, "text": text},
        headers=headers,
    )
    response.raise_for_status()
    return response.json()


def main():
    parser = argparse.ArgumentParser(prog="mindos", description="CLI de captura de MindOS")
    subparsers = parser.add_subparsers(dest="command", required=True)
    capture_parser = subparsers.add_parser("capture", help="Captura un mensaje de texto en MindOS")
    capture_parser.add_argument("text", help="El texto a capturar")

    args = parser.parse_args()

    async def _run():
        async with httpx.AsyncClient(timeout=10.0) as client:
            return await capture(
                args.text, client=client, base_url=settings.CLI_TARGET_URL,
                api_key=settings.MINDOS_API_KEY or None,
            )

    try:
        result = asyncio.run(_run())
    except httpx.HTTPError as e:
        print(f"Error al capturar: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Capturado (message_id={result['message_id']}).")


if __name__ == "__main__":
    main()
