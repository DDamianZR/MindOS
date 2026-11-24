"""Arma `MemoryStatsResponse` a partir del snapshot agregado de la memoria."""
from datetime import date, datetime, timedelta, timezone
from typing import Any

from mindos_schemas.api.v1.stats_dto import ActivityDay, CountItem, MemoryStatsResponse, RecentNode

from memory.src.application.ports.database import DatabasePort

_ACTIVITY_DAYS = 30
_RECENT_LIMIT = 8
_THINKING_TYPES = frozenset({"decision", "insight", "learning", "hypothesis"})


class StatsService:
    """Estadísticas de la memoria para la portada. El orden y los huecos se resuelven aquí."""

    def __init__(self, database: DatabasePort):
        self.database = database

    async def get_stats(self) -> MemoryStatsResponse:
        snap = await self.database.get_stats_snapshot()
        return MemoryStatsResponse(
            generated_at=datetime.now(timezone.utc),
            nodes=int(snap["nodes"]),
            archived_nodes=int(snap["archived_nodes"]),
            versions=int(snap["versions"]),
            relations=int(snap["relations"]),
            sources=int(snap["sources"]),
            contradictions=int(snap["contradictions"]),
            by_type=_sorted_counts(snap["by_type"]),
            by_source=_sorted_counts(snap["by_source"]),
            by_relation=_sorted_counts(snap["by_relation"]),
            activity=_fill_activity(snap["activity"]),
            recent_thinking=_recent_thinking(snap["recent_thinking"]),
        )


def _sorted_counts(items: list[dict[str, Any]]) -> list[CountItem]:
    # A igual recuento, la clave alfabética deja el mismo orden en memoria y en Postgres.
    ranked = sorted(
        ((str(item["key"]), int(item["count"])) for item in items if item.get("key") is not None),
        key=lambda pair: (-pair[1], pair[0]),
    )
    return [CountItem(key=key, count=count) for key, count in ranked]


def _fill_activity(raw: list[dict[str, Any]]) -> list[ActivityDay]:
    # El snapshot solo trae días con versiones; la portada pide la serie continua de 30 días.
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=_ACTIVITY_DAYS - 1)
    totals: dict[date, list[int]] = {}
    for item in raw:
        day = _coerce_day(item["date"])
        if day < start or day > today:
            continue
        slot = totals.setdefault(day, [0, 0])
        slot[0] += int(item.get("created") or 0)
        slot[1] += int(item.get("updated") or 0)

    days: list[ActivityDay] = []
    cursor = start
    while cursor <= today:
        created, updated = totals.get(cursor, (0, 0))
        days.append(ActivityDay(date=cursor, created=created, updated=updated))
        cursor += timedelta(days=1)
    return days


def _recent_thinking(raw: list[dict[str, Any]]) -> list[RecentNode]:
    chosen = [item for item in raw if item.get("object_type") in _THINKING_TYPES]
    chosen.sort(key=lambda item: (_as_utc(item["created_at"]), str(item["node_id"])), reverse=True)
    return [
        RecentNode(
            node_id=item["node_id"],
            title=item["title"],
            object_type=item.get("object_type"),
            version=int(item["version"]),
            created_at=_as_utc(item["created_at"]),
        )
        for item in chosen[:_RECENT_LIMIT]
    ]


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _coerce_day(value: date | datetime | str) -> date:
    if isinstance(value, datetime):
        return _as_utc(value).date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])
