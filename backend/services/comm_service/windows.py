"""
Communication window scheduling (V4).

Enceladus is ~1.3 billion km from Earth, so ground control can only reach a
rover during scheduled uplink windows. The schedule is a simple wall-clock
cycle: a window opens every `comm_slot_seconds` and stays open for
`comm_window_duration_seconds`. It is intentionally independent of any
mission's simulation tick — the schedule keeps running even if no plan is
currently executing, so a queued ground command is guaranteed to eventually
be delivered.

All functions take an optional `now` (seconds since the epoch) so callers —
and tests — can evaluate the schedule at an arbitrary point in time instead
of the wall clock.
"""
import time

from core.config import settings


def _phase(now: float) -> float:
    return now % settings.comm_slot_seconds


def is_window_open(now: float | None = None) -> bool:
    now = time.time() if now is None else now
    return _phase(now) < settings.comm_window_duration_seconds


def seconds_until_next_open(now: float | None = None) -> float:
    now = time.time() if now is None else now
    phase = _phase(now)
    if phase < settings.comm_window_duration_seconds:
        return 0.0
    return settings.comm_slot_seconds - phase


def seconds_until_close(now: float | None = None) -> float:
    now = time.time() if now is None else now
    phase = _phase(now)
    if phase < settings.comm_window_duration_seconds:
        return settings.comm_window_duration_seconds - phase
    return 0.0
