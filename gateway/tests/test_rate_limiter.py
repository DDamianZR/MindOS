"""F3-T1: ventana fija de rate-limit — InMemoryRateLimiter comparte la misma semántica que
RedisRateLimiter (probado aparte, ver test_gateway.py con Redis real cuando esté disponible)."""
import asyncio

import pytest

from gateway.src.infrastructure.adapters.in_memory_rate_limiter import InMemoryRateLimiter


@pytest.mark.asyncio
async def test_allows_requests_within_the_limit():
    limiter = InMemoryRateLimiter()
    for _ in range(5):
        assert await limiter.hit("1.2.3.4", limit=5, window_seconds=60) is True


@pytest.mark.asyncio
async def test_blocks_requests_once_the_limit_is_exceeded():
    limiter = InMemoryRateLimiter()
    for _ in range(3):
        await limiter.hit("1.2.3.4", limit=3, window_seconds=60)
    assert await limiter.hit("1.2.3.4", limit=3, window_seconds=60) is False


@pytest.mark.asyncio
async def test_different_keys_have_independent_counters():
    limiter = InMemoryRateLimiter()
    for _ in range(3):
        await limiter.hit("1.2.3.4", limit=3, window_seconds=60)
    assert await limiter.hit("5.6.7.8", limit=3, window_seconds=60) is True


@pytest.mark.asyncio
async def test_window_resets_after_it_elapses():
    limiter = InMemoryRateLimiter()
    for _ in range(2):
        await limiter.hit("1.2.3.4", limit=2, window_seconds=1)
    assert await limiter.hit("1.2.3.4", limit=2, window_seconds=1) is False

    await asyncio.sleep(1.1)
    assert await limiter.hit("1.2.3.4", limit=2, window_seconds=1) is True
