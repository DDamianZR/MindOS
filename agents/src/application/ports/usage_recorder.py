"""Puerto para anotar el uso del asistente personal y leer sus agregados (Fase 8)."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class UsageTotals:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0


@dataclass(frozen=True)
class ToolCount:
    key: str
    count: int


@dataclass(frozen=True)
class DayCount:
    """Un día UTC (`YYYY-MM-DD`) y cuántos turnos cayeron en él."""
    date: str
    turns: int


@dataclass(frozen=True)
class UsageSnapshot:
    """Agregados del asistente desde que arrancó el registro de uso."""
    since: str
    conversations: int
    turns: int
    failed_turns: int
    tool_calls: list[ToolCount]
    usage: UsageTotals
    cache_hit_ratio: float | None
    estimated_cost_usd: float
    avg_turn_seconds: float | None
    turns_by_day: list[DayCount]


class UsageRecorderPort(ABC):
    """
    Anota cada turno cerrado del asistente y devuelve el uso acumulado desde el arranque
    del registro. La implementación vive en el proceso: al reiniciar el servicio, vuelve a cero.
    """

    @abstractmethod
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
        """
        Registra un turno ya cerrado.

        `ok` es falso si terminó en error. `tools` es el nombre de cada herramienta que
        terminó (`tool_end`), repetido si se usó más de una vez. `usage` trae las claves del
        evento `done` (input_tokens, output_tokens, cache_read_input_tokens,
        cache_creation_input_tokens); las que falten cuentan como 0. `at` nulo significa ahora.
        """

    @abstractmethod
    def snapshot(self, model: str) -> UsageSnapshot:
        """
        Agregados para `/assistant/stats`.

        `model` elige la tarifa en USD por millón de tokens. `demo`, o un modelo sin tarifa,
        cuesta 0. `cache_hit_ratio` es cache_read / (input + cache_read + cache_creation),
        o nulo si ese denominador es 0.
        """
