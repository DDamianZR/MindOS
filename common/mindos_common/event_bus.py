import asyncio
import json
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from pydantic import BaseModel
from redis.asyncio import ConnectionPool, Redis

from mindos_common.context import set_correlation_id
from mindos_common.ids import new_id
from mindos_common.logging import get_logger

logger = get_logger("event_bus")

class RedisEventBus:
    """
    Bus de eventos asíncronos basado en Redis Streams.
    Soporta publicación estructurada y suscripción distribuida mediante Grupos de Consumo (Consumer Groups).
    Propaga automáticamente el correlation_id a través de los eventos.
    """
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.pool = ConnectionPool.from_url(redis_url)
        self.client = Redis(connection_pool=self.pool)

    async def close(self) -> None:
        """Cierra el pool de conexiones de Redis."""
        await self.pool.disconnect()

    async def publish(self, stream_name: str, event_type: str, event_data: BaseModel, correlation_id: UUID) -> str:
        """
        Publica un evento estructurado en un Stream de Redis.
        """
        # Estructura compatible con CloudEvents v1.0
        event_payload = {
            "specversion": "1.0",
            "id": str(new_id()),  # UUIDv7 único por evento (antes: hash() colisionaba)
            "type": event_type,
            "time": datetime.now(timezone.utc).isoformat(),
            "datacontenttype": "application/json",
            "correlation_id": str(correlation_id),
            "data": event_data.model_dump_json()
        }

        # Serializar y subir al stream (xadd)
        message_id = await self.client.xadd(
            name=stream_name,
            fields={"payload": json.dumps(event_payload)}
        )
        logger.debug(
            "Evento publicado con éxito",
            stream=stream_name,
            type=event_type,
            message_id=message_id,
            correlation_id=str(correlation_id)
        )
        return message_id

    async def subscribe(
        self,
        stream_name: str,
        group_name: str,
        consumer_name: str,
        callback: Callable[[dict[str, Any]], Awaitable[None]]
    ) -> None:
        """
        Registra un consumidor en un grupo de consumo y comienza a procesar eventos en segundo plano.
        """
        # Asegurar que el grupo de consumo existe (crearlo desde el inicio del stream '$' si no existe)
        try:
            await self.client.xgroup_create(stream_name, group_name, id="0", mkstream=True)
        except Exception:
            # El grupo de consumo ya existe, ignorar excepción
            pass

        async def worker():
            logger.info("Iniciando worker de Redis Stream", stream=stream_name, group=group_name, consumer=consumer_name)
            while True:
                try:
                    # Leer eventos pendientes o nuevos (xreadgroup)
                    # Usamos '>' para leer mensajes nuevos que no han sido entregados a otros
                    messages = await self.client.xreadgroup(
                        groupname=group_name,
                        consumername=consumer_name,
                        streams={stream_name: ">"},
                        count=1,
                        block=2000 # Bloquea por 2 segundos esperando mensajes
                    )

                    if not messages:
                        continue

                    for _stream, msg_list in messages:
                        for msg_id, fields in msg_list:
                            raw_payload = fields.get(b"payload")
                            if raw_payload:
                                event = json.loads(raw_payload.decode("utf-8"))

                                # Extraer ID de correlación
                                corr_id_str = event.get("correlation_id")
                                corr_id = UUID(corr_id_str) if corr_id_str else None

                                # Configurar el ID de correlación en el contexto de esta tarea
                                token = None
                                if corr_id:
                                    token = set_correlation_id(corr_id)

                                try:
                                    logger.info(
                                        "Procesando evento del bus",
                                        stream=stream_name,
                                        event_id=event.get("id"),
                                        event_type=event.get("type"),
                                        correlation_id=corr_id_str
                                    )
                                    # Ejecutar la lógica de negocio
                                    await callback(event)

                                    # Confirmar procesamiento del mensaje (xack)
                                    await self.client.xack(stream_name, group_name, msg_id)

                                except Exception as e:
                                    logger.error(
                                        "Error procesando evento",
                                        stream=stream_name,
                                        msg_id=msg_id,
                                        error=str(e)
                                    )
                                finally:
                                    # Limpiar el correlation_id context
                                    if token:
                                        from mindos_common.context import clear_correlation_id
                                        clear_correlation_id(token)

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error("Error en el bucle principal del suscriptor", error=str(e))
                    await asyncio.sleep(5) # Esperar 5s antes de reintentar si hay error de conexión

        # Levantar el worker en segundo plano sin bloquear
        asyncio.create_task(worker())

# Fin del módulo event_bus
