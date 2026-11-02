"""Per-device daily limits and the whole-service daily budget, counted per IST day.

Counters live in memory (one backend instance) and are restored from Supabase on startup.
"""

from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone

from kettu.config import Settings
from kettu.domain.errors import ErrorCode, KettuError

IST = timezone(timedelta(hours=5, minutes=30))


def ist_today() -> date:
    return datetime.now(IST).date()


def ist_midnight() -> datetime:
    return datetime.combine(ist_today(), time(0, 0), tzinfo=IST)


@dataclass
class DayCounters:
    day: date
    per_device: dict[tuple[str, str], int] = field(default_factory=lambda: defaultdict(int))
    stt_seconds: float = 0.0
    tts_chars: int = 0
    pending: dict[tuple[str, str], int] = field(default_factory=lambda: defaultdict(int))
    reserved_stt: float = 0.0
    reserved_tts: int = 0
    operations: int = 0


class Limits:
    def __init__(self, settings: Settings):
        self.s = settings
        self._c = DayCounters(ist_today())

    @property
    def c(self) -> DayCounters:
        today = ist_today()
        if self._c.day != today:
            self._c = DayCounters(today)
        return self._c

    def restore(self, rows: list[dict]) -> None:
        for r in rows:
            if r.get("status") not in (None, "ok"):
                continue
            self.c.per_device[(r["device_id"], r["kind"])] += 1
            self.c.stt_seconds += float(r.get("audio_seconds") or 0)
            self.c.tts_chars += int(r.get("tts_chars") or 0)
            self.c.operations += 1

    def count(self, device: str, kind: str) -> int:
        return self.c.per_device[(device, kind)] + self.c.pending[(device, kind)]

    @contextmanager
    def reserve(self, device: str, kind: str, stt_seconds: float = 0, tts_chars: int = 0):
        """Reserve before awaiting a provider or queue; concurrent calls see the reservation.

        Attempts count toward the service operation cap even when a provider fails.
        All state belongs to one process; deployments must keep a single worker.
        """
        if kind == "note":
            self.check_note(device)
        elif kind == "reply_preview":
            self.check_preview(device)
        elif kind == "translate":
            self.check_translate(device)
        else:
            self.check_speak(device, tts_chars, kind)
        c = self.c
        if (c.stt_seconds + c.reserved_stt + stt_seconds > self.s.daily_stt_seconds_cap
                or c.tts_chars + c.reserved_tts + tts_chars > self.s.daily_tts_chars_cap
                or c.operations >= self.s.daily_operations_cap):
            raise KettuError(ErrorCode.SERVICE_BUDGET)
        c.operations += 1
        c.pending[(device, kind)] += 1
        c.reserved_stt += stt_seconds
        c.reserved_tts += tts_chars
        try:
            yield
        finally:
            c.pending[(device, kind)] -= 1
            c.reserved_stt -= stt_seconds
            c.reserved_tts -= tts_chars

    # ---- checks (raise before any paid call)

    def service_open(self) -> bool:
        return (self.c.stt_seconds + self.c.reserved_stt < self.s.daily_stt_seconds_cap
                and self.c.tts_chars + self.c.reserved_tts < self.s.daily_tts_chars_cap
                and self.c.operations < self.s.daily_operations_cap)

    def check_note(self, device: str) -> None:
        if self.c.stt_seconds >= self.s.daily_stt_seconds_cap:
            raise KettuError(ErrorCode.SERVICE_BUDGET)
        if self.count(device, "note") >= self.s.notes_per_day:
            raise KettuError(ErrorCode.DAILY_LIMIT)

    def check_preview(self, device: str) -> None:
        if self.count(device, "reply_preview") >= self.s.replies_per_day * 4:
            raise KettuError(ErrorCode.DAILY_LIMIT, "You have drafted a lot of replies today. Come back tomorrow.")

    def check_translate(self, device: str) -> None:
        if self.count(device, "translate") >= self.s.translate_per_day:
            raise KettuError(ErrorCode.DAILY_LIMIT, "You have translated a lot today. Come back tomorrow.")

    def check_speak(self, device: str, chars: int, kind: str = "reply_speak") -> None:
        if self.c.tts_chars + self.c.reserved_tts + chars > self.s.daily_tts_chars_cap:
            raise KettuError(ErrorCode.SERVICE_BUDGET)
        if kind == "read_aloud":
            if self.count(device, kind) >= self.s.read_aloud_per_day:
                raise KettuError(ErrorCode.DAILY_LIMIT, "You have used today's read-alouds. Come back tomorrow.")
            return
        if self.count(device, "reply_speak") >= self.s.replies_per_day:
            raise KettuError(ErrorCode.DAILY_LIMIT, "You have used today's free voice replies. Come back tomorrow.")

    # ---- records

    def record(self, device: str, kind: str, stt_seconds: float = 0.0, tts_chars: int = 0) -> None:
        self.c.per_device[(device, kind)] += 1
        self.c.stt_seconds += stt_seconds
        self.c.tts_chars += tts_chars

    def add_stt(self, seconds: float) -> None:
        """Spoken replies are transcribed too; they count against the budget, not the note limit."""
        self.c.stt_seconds += seconds

    def remaining(self, device: str) -> dict:
        return {
            "notes_left": max(0, self.s.notes_per_day - self.count(device, "note")),
            "replies_left": max(0, self.s.replies_per_day - self.count(device, "reply_speak")),
            "service_open": self.service_open(),
        }
