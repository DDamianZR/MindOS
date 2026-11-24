"""
La zona horaria de una rutina se guarda siempre como nombre IANA: se vuelve a leer en otro
proceso (y, con Postgres, después de un reinicio), y solo un nombre IANA se resuelve igual en
cualquier máquina y respeta los cambios de horario. Encontrado probando en vivo en Windows,
donde la zona del sistema se llamaba "Hora estándar central (México)".
"""
from zoneinfo import ZoneInfo

import pytest

from agents.src.application.assistant import routines


def test_local_timezone_is_an_iana_name():
    name = routines._local_timezone_name()
    assert ZoneInfo(name)  # no lanza: es un nombre IANA real
    assert "(" not in name and " " not in name


def test_windows_display_names_are_rejected():
    with pytest.raises(routines.ScheduleError, match="America/Mexico_City"):
        routines._tzinfo_for("Hora estándar central (México)")


def test_without_a_detectable_zone_it_falls_back_to_utc(monkeypatch):
    monkeypatch.setattr(routines.tzlocal, "get_localzone_name", lambda: None)
    assert routines._local_timezone_name() == "UTC"


def test_next_run_respects_the_zone():
    nxt = routines.compute_next_run("0 9 * * 1", "America/Mexico_City")
    assert nxt.hour == 9 and nxt.weekday() == 0
    assert nxt.utcoffset() is not None
