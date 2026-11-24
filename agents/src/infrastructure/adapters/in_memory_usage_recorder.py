"""
Uso del asistente en memoria del proceso (Fase 8).

Se pierde al reiniciar el servicio: `/assistant/stats` mide desde el arranque, no la historia
completa. El tope de turnos evita que un proceso de larga vida crezca sin límite.
"""
from collections import deque
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from agents.src.application.ports.usage_recorder import (
    DayCount,
    ToolCount,
    UsageRecorderPort,
    UsageSnapshot,
    UsageTotals,
)
from agents.src.config import settings

_MAX_TURNS = 5000
_DAY_WINDOW = 14
_MILLION = 1_000_000


def _as_utc(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def _normalize_usage(usage: dict[str, int] | None) -> UsageTotals:
    raw = usage or {}
    return UsageTotals(
        input_tokens=int(raw.get("input_tokens") or 0),
        output_tokens=int(raw.get("output_tokens") or 0),
        cache_read_input_tokens=int(raw.get("cache_read_input_tokens") or 0),
        cache_creation_input_tokens=int(raw.get("cache_creation_input_tokens") or 0),
    )


def _sum_usage(turns: Iterable["_Turn"]) -> UsageTotals:
    input_tokens = output_tokens = cache_read = cache_creation = 0
    for turn in turns:
        input_tokens += turn.usage.input_tokens
        output_tokens += turn.usage.output_tokens
        cache_read += turn.usage.cache_read_input_tokens
        cache_creation += turn.usage.cache_creation_input_tokens
    return UsageTotals(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_input_tokens=cache_read,
        cache_creation_input_tokens=cache_creation,
    )


def _cache_hit_ratio(usage: UsageTotals) -> float | None:
    denominator = (
        usage.input_tokens + usage.cache_read_input_tokens + usage.cache_creation_input_tokens
    )
    if denominator == 0:
        return None
    return usage.cache_read_input_tokens / denominator


def _estimated_cost_usd(model: str, usage: UsageTotals) -> float:
    # El modo demostración no llama a la API: no hay gasto aunque existiera una tarifa.
    if model == "demo":
        return 0.0
    rates = settings.ASSISTANT_PRICING.get(model)
    if not rates:
        return 0.0
    per_million = (
        usage.input_tokens * rates.get("input", 0.0)
        + usage.output_tokens * rates.get("output", 0.0)
        + usage.cache_read_input_tokens * rates.get("cache_read", 0.0)
        + usage.cache_creation_input_tokens * rates.get("cache_write", 0.0)
    )
    return round(per_million / _MILLION, 6)


def _count_tools(turns: Iterable["_Turn"]) -> list[ToolCount]:
    counts: dict[str, int] = {}
    for turn in turns:
        for name in turn.tools:
            counts[name] = counts.get(name, 0) + 1
    # A igual cantidad, por nombre: el orden no depende de cómo esté el dict.
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [ToolCount(key=name, count=count) for name, count in ordered]


def _turns_by_day(turns: Iterable["_Turn"], today: datetime) -> list[DayCount]:
    counts: dict[str, int] = {}
    for turn in turns:
        day = _as_utc(turn.at).date().isoformat()
        counts[day] = counts.get(day, 0) + 1
    start = _as_utc(today).date()
    return [
        DayCount(
            date=(start - timedelta(days=offset)).isoformat(),
            turns=counts.get((start - timedelta(days=offset)).isoformat(), 0),
        )
        for offset in range(_DAY_WINDOW - 1, -1, -1)
    ]


@dataclass(frozen=True)
class _Turn:
    conversation_id: str
    ok: bool
    duration_seconds: float
    tools: tuple[str, ...]
    usage: UsageTotals
    at: datetime


class InMemoryUsageRecorder(UsageRecorderPort):
    """Registro en memoria del proceso. Guarda como máximo los últimos `max_turns` turnos."""

    def __init__(self, max_turns: int = _MAX_TURNS, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._since = _as_utc(self._clock()).isoformat()
        self._turns: deque[_Turn] = deque(maxlen=max_turns)

    def record_turn(
        self,
        conversation_id: str,
        *,
        ok: bool,
        duration_seconds: float,
        tools: list[str],
        usage: dict[str, int] | None = None,
        at: datetime | None = None,
    ) -> None:
        self._turns.append(_Turn(
            conversation_id=conversation_id,
            ok=ok,
            duration_seconds=duration_seconds,
            tools=tuple(tools),
            usage=_normalize_usage(usage),
            at=_as_utc(at or self._clock()),
        ))

    def snapshot(self, model: str) -> UsageSnapshot:
        turns = self._turns
        usage = _sum_usage(turns)
        avg = (
            sum(turn.duration_seconds for turn in turns) / len(turns)
            if turns else None
        )
        return UsageSnapshot(
            since=self._since,
            conversations=len({turn.conversation_id for turn in turns}),
            turns=len(turns),
            failed_turns=sum(1 for turn in turns if not turn.ok),
            tool_calls=_count_tools(turns),
            usage=usage,
            cache_hit_ratio=_cache_hit_ratio(usage),
            estimated_cost_usd=_estimated_cost_usd(model, usage),
            avg_turn_seconds=avg,
            turns_by_day=_turns_by_day(turns, self._clock()),
        )


_recorder: InMemoryUsageRecorder | None = None


def get_usage_recorder() -> UsageRecorderPort:
    """Instancia única del proceso, para inyectarla con `Depends`."""
    global _recorder
    if _recorder is None:
        _recorder = InMemoryUsageRecorder()
    return _recorder
