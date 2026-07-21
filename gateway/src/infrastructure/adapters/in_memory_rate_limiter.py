import time

from gateway.src.application.ports.rate_limiter import RateLimiterPort


class InMemoryRateLimiter(RateLimiterPort):
    """Ventana fija en memoria (tests/dev sin Redis) — misma semántica que RedisRateLimiter."""
    def __init__(self):
        self._counters: dict[str, tuple[int, float]] = {}  # key -> (count, window_started_at)

    async def hit(self, key: str, limit: int, window_seconds: int) -> bool:
        now = time.monotonic()
        count, window_started_at = self._counters.get(key, (0, now))
        if now - window_started_at >= window_seconds:
            count, window_started_at = 0, now
        count += 1
        self._counters[key] = (count, window_started_at)
        return count <= limit
