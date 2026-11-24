"""
Rutinas programadas del asistente (Fase 8).

La expresión cron se valida y se traduce aquí, sin tocar el reloj del sistema salvo para
preguntar «ahora». El runner abre una conversación nueva y trata el `prompt` como un turno
normal: el resultado queda guardado en la ejecución, no en el chat de la persona.
"""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import tzlocal
from croniter import croniter
from mindos_common.logging import get_logger

from agents.src.application.ports.conversation_store import ConversationStorePort
from agents.src.application.ports.personal_agent import PersonalAgentPort, TextDelta, TurnFailed
from agents.src.application.ports.routine_store import (
    Routine,
    RoutineAuthor,
    RoutineRun,
    RoutineStatusName,
    RoutineStorePort,
)

logger = get_logger("routines")

_WEEKDAYS = {
    0: "domingo",
    1: "lunes",
    2: "martes",
    3: "miércoles",
    4: "jueves",
    5: "viernes",
    6: "sábado",
    7: "domingo",
}
_WEEKDAY_ALIASES = {
    "SUN": 0, "MON": 1, "TUE": 2, "WED": 3, "THU": 4, "FRI": 5, "SAT": 6,
}


class ScheduleError(ValueError):
    """La programación o la zona horaria no se pueden usar. El mensaje ya es para la persona."""


def normalize_schedule(expr: str) -> str:
    """Deja la expresión en 5 campos o lanza `ScheduleError` con un texto legible."""
    normalized = " ".join(expr.strip().split())
    parts = normalized.split(" ")
    if len(parts) != 5 or not croniter.is_valid(normalized):
        raise ScheduleError(
            "La programación no es válida. Usa cinco campos: minuto, hora, día, mes y día de la semana."
        )
    return normalized


def describe_schedule(expr: str) -> str:
    """
    Traduce los cron que se pueden decir en una frase. El resto vuelve tal cual, para no
    inventar un horario que no es el que se va a ejecutar.
    """
    normalized = " ".join(expr.strip().split())
    fallback = f"según la expresión cron {normalized}"
    parts = normalized.split(" ")
    if len(parts) != 5:
        return fallback
    clock = _fixed_clock(parts[0], parts[1])
    if clock is None or parts[3] != "*":
        return fallback
    return _describe_known(parts[2], parts[4], clock, fallback)


def resolve_timezone_name(explicit: str | None, configured: str = "") -> str:
    """
    Zona en la que se lee el cron. `configured` vacío (ROUTINES_TIMEZONE) significa la zona
    local del servidor. Un nombre que ZoneInfo no conoce se rechaza.
    """
    candidate = (explicit or "").strip() or (configured or "").strip()
    if not candidate:
        return _local_timezone_name()
    try:
        ZoneInfo(candidate)
    except ZoneInfoNotFoundError as exc:
        raise ScheduleError("Esa zona horaria no es válida.") from exc
    return candidate


def compute_next_run(schedule: str, timezone_name: str, *, after: datetime | None = None) -> datetime:
    """Siguiente instante estrictamente posterior a `after` (o a ahora), en la zona de la rutina."""
    tz = _tzinfo_for(timezone_name)
    if after is None:
        base = datetime.now(tz)
    elif after.tzinfo is None:
        base = after.replace(tzinfo=tz)
    else:
        base = after.astimezone(tz)
    nxt = croniter(schedule, base).get_next(datetime)
    if nxt.tzinfo is None:
        return nxt.replace(tzinfo=tz)
    return nxt


def prepare_schedule(
    schedule: str,
    timezone_name: str | None,
    configured_timezone: str,
    *,
    after: datetime | None = None,
) -> tuple[str, str, str, datetime]:
    """Devuelve (cron normalizado, frase en español, zona, próxima ejecución)."""
    normalized = normalize_schedule(schedule)
    zone = resolve_timezone_name(timezone_name, configured_timezone)
    return normalized, describe_schedule(normalized), zone, compute_next_run(normalized, zone, after=after)


async def register_routine(
    store: RoutineStorePort,
    *,
    title: str,
    prompt: str,
    schedule: str,
    timezone_name: str | None,
    configured_timezone: str,
    status: RoutineStatusName,
    created_by: RoutineAuthor,
) -> Routine:
    normalized, description, zone, nxt = prepare_schedule(schedule, timezone_name, configured_timezone)
    return await store.create(
        title=title.strip() or title,
        prompt=prompt.strip() or prompt,
        schedule=normalized,
        schedule_description=description,
        timezone_name=zone,
        status=status,
        created_by=created_by,
        next_run_at=nxt,
    )


class RoutineRunner:
    """Ejecuta una rutina vencida como un turno del asistente y guarda el texto o el error."""

    def __init__(
        self,
        store: RoutineStorePort,
        conversations: ConversationStorePort,
        agent: PersonalAgentPort,
    ) -> None:
        self._store = store
        self._conversations = conversations
        self._agent = agent

    async def run(
        self,
        routine_id: str,
        *,
        now: datetime | None = None,
        allow_paused: bool = False,
    ) -> RoutineRun | None:
        """
        Corre la rutina si está activa. `allow_paused` es el botón de «ejecutar ahora»: una
        en pausa puede lanzarse a mano, una pendiente de activar nunca.
        None si no toca correrla o si ya hay una ejecución en curso.
        """
        routine = await self._store.get(routine_id)
        if routine is None or not _can_run(routine.status, allow_paused):
            return None
        started_at = now if now is not None else datetime.now().astimezone()
        execution = await self._store.start_run(routine.id, started_at)
        if execution is None:
            return None
        output, failed = await self._produce(routine)
        return await self._close(routine, execution.id, output, failed)

    async def _produce(self, routine: Routine) -> tuple[str, bool]:
        try:
            return await self._consume(routine)
        except Exception as exc:
            logger.warning("La rutina no pudo completarse", routine_id=routine.id, error=str(exc))
            return "No se pudo completar la rutina.", True

    async def _consume(self, routine: Routine) -> tuple[str, bool]:
        conversation = await self._conversations.create()
        chunks: list[str] = []
        error: str | None = None
        async for event in self._agent.stream_reply(conversation, routine.prompt):
            if isinstance(event, TextDelta):
                chunks.append(event.text)
            elif isinstance(event, TurnFailed):
                error = event.message
        await self._conversations.save(conversation)
        if error is not None:
            return error, True
        return "".join(chunks), False

    async def _close(self, routine: Routine, run_id: str, output: str, failed: bool) -> RoutineRun | None:
        # Un fallo no pausa la rutina: se anota y se agenda la siguiente hora, igual que un acierto.
        finished_at = datetime.now().astimezone()
        status = "error" if failed else "ok"
        return await self._store.finish_run(
            run_id,
            status=status,
            output=output,
            finished_at=finished_at,
            next_run_at=_next_after(routine, finished_at),
        )


def _can_run(status: str, allow_paused: bool) -> bool:
    if status == "active":
        return True
    return allow_paused and status == "paused"


def _next_after(routine: Routine, finished_at: datetime) -> datetime:
    try:
        return compute_next_run(routine.schedule, routine.timezone, after=finished_at)
    except ScheduleError:
        # Sin una hora futura el planificador la volvería a lanzar en cada tic.
        logger.warning("No se pudo calcular la siguiente ejecución", routine_id=routine.id)
        return finished_at + timedelta(hours=1)


def _fixed_int(field: str, low: int, high: int) -> int | None:
    if not field.isdigit():
        return None
    value = int(field)
    if low <= value <= high:
        return value
    return None


def _fixed_clock(minute_s: str, hour_s: str) -> str | None:
    minute = _fixed_int(minute_s, 0, 59)
    hour = _fixed_int(hour_s, 0, 23)
    if minute is None or hour is None:
        return None
    return f"{hour:02d}:{minute:02d}"


def _describe_known(day_of_month: str, day_of_week: str, clock: str, fallback: str) -> str:
    if day_of_month == "*" and day_of_week == "*":
        return f"todos los días a las {clock}"
    if day_of_month == "*":
        days = _describe_weekdays(day_of_week)
        if not days:
            return fallback
        return f"{days} a las {clock}"
    if day_of_week != "*":
        return fallback
    day = _fixed_int(day_of_month, 1, 31)
    if day is None:
        return fallback
    return f"el día {day} de cada mes a las {clock}"


def _weekday_number(token: str) -> int | None:
    token = token.strip().upper()
    if token.isdigit():
        value = int(token)
        return value if value in _WEEKDAYS else None
    return _WEEKDAY_ALIASES.get(token)


def _describe_weekdays(field: str) -> str | None:
    if "-" in field and "," not in field:
        return _describe_weekday_range(field)
    names = _weekday_names(field)
    if names is None:
        return None
    return _join_weekdays(names)


def _describe_weekday_range(field: str) -> str | None:
    start_s, _, end_s = field.partition("-")
    start, end = _weekday_number(start_s), _weekday_number(end_s)
    if start is None or end is None or end <= start:
        return None
    return f"de {_WEEKDAYS[start]} a {_WEEKDAYS[end]}"


def _weekday_names(field: str) -> list[str] | None:
    tokens = [token for token in field.split(",") if token != ""]
    if not tokens:
        return None
    names: list[str] = []
    for token in tokens:
        number = _weekday_number(token)
        if number is None:
            return None
        name = _WEEKDAYS[number]
        if name not in names:
            names.append(name)
    return names


def _join_weekdays(names: list[str]) -> str:
    if len(names) == 1:
        return f"cada {names[0]}"
    if len(names) == 2:
        return f"cada {names[0]} y {names[1]}"
    return "cada " + ", ".join(names[:-1]) + " y " + names[-1]


def _local_timezone_name() -> str:
    """
    Nombre IANA de la zona del servidor ("America/Mexico_City"), nunca el nombre que da el
    sistema ("Hora estándar central (México)" en Windows): la rutina se guarda y se vuelve a
    leer en otro proceso, y solo un nombre IANA se resuelve igual en cualquier máquina y con
    los cambios de horario. `tzlocal` traduce la zona de Windows y lee la de Linux.
    """
    try:
        name = tzlocal.get_localzone_name()
    except Exception:  # sin zona configurada (contenedor mínimo): se avisa y se usa UTC
        name = None
    if name:
        return name
    logger.warning("No se pudo determinar la zona horaria del servidor; las rutinas usan UTC. Fija ROUTINES_TIMEZONE.")
    return "UTC"


def _tzinfo_for(name: str):
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        raise ScheduleError("Esa zona horaria no es válida. Usa un nombre como America/Mexico_City.") from None
