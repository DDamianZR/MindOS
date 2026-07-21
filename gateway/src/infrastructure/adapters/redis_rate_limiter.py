from redis.asyncio import Redis

from gateway.src.application.ports.rate_limiter import RateLimiterPort


class RedisRateLimiter(RateLimiterPort):
    """
    Ventana fija sobre Redis: `INCR` de un contador por `key`, con `EXPIRE` puesto solo la
    primera vez (cuando el contador pasa a 1) para que la ventana dure `window_seconds` desde
    la primera petición, no se reinicie en cada hit.
    """
    def __init__(self, client: Redis):
        self.client = client

    async def hit(self, key: str, limit: int, window_seconds: int) -> bool:
        redis_key = f"ratelimit:{key}"
        count = await self.client.incr(redis_key)
        if count == 1:
            await self.client.expire(redis_key, window_seconds)
        return count <= limit
