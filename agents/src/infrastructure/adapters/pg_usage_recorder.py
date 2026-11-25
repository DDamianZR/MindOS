"""
Uso del asistente en Postgres (Fase 9).

Los números coinciden con `InMemoryUsageRecorder`, pero salen de SQL y no hay tope de
turnos: es la historia completa y sigue ahí aunque el proceso arranque de nuevo.
"""
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from mindos_common.ids import new_id
from sqlalchemy import case, distinct, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from agents.src.application.ports.usage_recorder import (
    DayCount,
    ToolCount,
    UsageRecorderPort,
    UsageSnapshot,
    UsageTotals,
)
from agents.src.infrastructure.adapters.in_memory_usage_recorder import (
    _DAY_WINDOW,
    _as_utc,
    _cache_hit_ratio,
    _estimated_cost_usd,
    _normalize_usage,
)
from agents.src.infrastructure.database.models import DbUsageTurn
from agents.src.infrastructure.database.session import SessionFactory

_USAGE_TABLE = DbUsageTurn.__tablename__


def _date_label(value: date | datetime | str) -> str:
    # `datetime` es subclase de `date`: hay que descartarlo antes o el isoformat trae la hora.
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


@dataclass(frozen=True)
class _Totals:
    turns: int
    failed_turns: int
    conversations: int
    usage: UsageTotals
    avg_turn_seconds: float | None
    first_at: datetime | None


async def _totals(session: AsyncSession) -> _Totals:
    row = (
        await session.execute(
            select(
                func.count().label("turns"),
                func.coalesce(
                    func.sum(case((DbUsageTurn.ok.is_(False), 1), else_=0)),
                    0,
                ).label("failed_turns"),
                func.count(distinct(DbUsageTurn.conversation_id)).label("conversations"),
                func.coalesce(func.sum(DbUsageTurn.input_tokens), 0).label("input_tokens"),
                func.coalesce(func.sum(DbUsageTurn.output_tokens), 0).label("output_tokens"),
                func.coalesce(
                    func.sum(DbUsageTurn.cache_read_input_tokens), 0
                ).label("cache_read_input_tokens"),
                func.coalesce(
                    func.sum(DbUsageTurn.cache_creation_input_tokens), 0
                ).label("cache_creation_input_tokens"),
                func.avg(DbUsageTurn.duration_seconds).label("avg_turn_seconds"),
                func.min(DbUsageTurn.at).label("first_at"),
            ).select_from(DbUsageTurn)
        )
    ).one()
    avg = row.avg_turn_seconds
    return _Totals(
        turns=int(row.turns),
        failed_turns=int(row.failed_turns),
        conversations=int(row.conversations),
        usage=UsageTotals(
            input_tokens=int(row.input_tokens),
            output_tokens=int(row.output_tokens),
            cache_read_input_tokens=int(row.cache_read_input_tokens),
            cache_creation_input_tokens=int(row.cache_creation_input_tokens),
        ),
        avg_turn_seconds=None if avg is None else float(avg),
        first_at=row.first_at,
    )


async def _tool_counts(session: AsyncSession) -> list[ToolCount]:
    # Cada aparición cuenta, también las repetidas dentro del mismo turno.
    rows = await session.execute(
        text(
            f"""
            SELECT elem AS tool, COUNT(*) AS n
            FROM {_USAGE_TABLE}
            CROSS JOIN LATERAL jsonb_array_elements_text(tools) AS elem
            GROUP BY elem
            ORDER BY n DESC, elem ASC
            """
        )
    )
    return [ToolCount(key=str(row.tool), count=int(row.n)) for row in rows]


async def _turns_by_day(session: AsyncSession, today: datetime) -> list[DayCount]:
    # El día es el de UTC, no el de la zona de la sesión: si no, la serie de 14 días se corre.
    end = _as_utc(today).date()
    start = end - timedelta(days=_DAY_WINDOW - 1)
    rows = await session.execute(
        text(
            f"""
            SELECT CAST(gs AS date) AS day, COUNT(t.id) AS turn_count
            FROM generate_series(
                CAST(:start AS timestamp),
                CAST(:end AS timestamp),
                INTERVAL '1 day'
            ) AS gs
            LEFT JOIN {_USAGE_TABLE} AS t
              ON CAST(t.at AT TIME ZONE 'UTC' AS date) = CAST(gs AS date)
            GROUP BY gs
            ORDER BY gs
            """
        ),
        {
            "start": datetime(start.year, start.month, start.day),
            "end": datetime(end.year, end.month, end.day),
        },
    )
    return [
        DayCount(date=_date_label(row.day), turns=int(row.turn_count))
        for row in rows
    ]


class PgUsageRecorder(UsageRecorderPort):
    """Historia completa de turnos en `agent_usage_turns`. Una sesión corta por operación."""

    def __init__(
        self,
        session_factory: SessionFactory,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._sessions = session_factory
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        # Si todavía no hay turnos, `since` es este instante (el recorder acaba de nacer).
        self._created_since = _as_utc(self._clock()).isoformat()

    async def record_turn(
        self,
        conversation_id: str,
        *,
        ok: bool,
        duration_seconds: float,
        tools: list[str],
        usage: dict[str, int] | None = None,
        at: datetime | None = None,
    ) -> None:
        totals = _normalize_usage(usage)
        moment = _as_utc(at or self._clock())
        async with self._sessions() as session:
            session.add(
                DbUsageTurn(
                    id=str(new_id()),
                    conversation_id=conversation_id,
                    at=moment,
                    ok=ok,
                    duration_seconds=float(duration_seconds),
                    tools=list(tools),
                    input_tokens=totals.input_tokens,
                    output_tokens=totals.output_tokens,
                    cache_read_input_tokens=totals.cache_read_input_tokens,
                    cache_creation_input_tokens=totals.cache_creation_input_tokens,
                )
            )
            await session.commit()

    async def snapshot(self, model: str) -> UsageSnapshot:
        async with self._sessions() as session:
            totals = await _totals(session)
            tool_calls = await _tool_counts(session)
            turns_by_day = await _turns_by_day(session, self._clock())
            await session.commit()
        # Con turnos, `since` es el `at` del más antiguo: un recorder nuevo (reinicio)
        # sigue contando desde el mismo momento, no desde que él se creó.
        since = (
            self._created_since
            if totals.first_at is None
            else _as_utc(totals.first_at).isoformat()
        )
        return UsageSnapshot(
            since=since,
            conversations=totals.conversations,
            turns=totals.turns,
            failed_turns=totals.failed_turns,
            tool_calls=tool_calls,
            usage=totals.usage,
            cache_hit_ratio=_cache_hit_ratio(totals.usage),
            estimated_cost_usd=_estimated_cost_usd(model, totals.usage),
            avg_turn_seconds=totals.avg_turn_seconds,
            turns_by_day=turns_by_day,
        )
