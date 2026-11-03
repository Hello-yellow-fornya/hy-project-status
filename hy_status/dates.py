"""Date helpers. All 'today' logic is in Europe/London."""

from __future__ import annotations

import datetime as dt
import re
from zoneinfo import ZoneInfo

LONDON = ZoneInfo("Europe/London")

_WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def today_london(now: dt.datetime | None = None) -> dt.date:
    now = now or dt.datetime.now(dt.timezone.utc)
    return now.astimezone(LONDON).date()


def display_date(d: dt.date) -> str:
    """2 Nov 2026"""
    return f"{d.day} {d.strftime('%b')} {d.year}"


def relative(d: dt.date, today: dt.date) -> str:
    days = (today - d).days
    if days < 0:
        return "in the future"
    if days == 0:
        return "today"
    if days == 1:
        return "yesterday"
    if days <= 6:
        return f"{days} days ago"
    if days <= 27:
        weeks = days // 7
        return "1 week ago" if weeks == 1 else f"{weeks} weeks ago"
    months = max(1, days // 30)
    return "1 month ago" if months == 1 else f"{months} months ago"


def end_of_day_utc(d: dt.date) -> dt.datetime:
    """Last instant of a London calendar day, as an aware UTC datetime."""
    nxt = dt.datetime.combine(d + dt.timedelta(days=1), dt.time(0, 0), LONDON)
    return (nxt - dt.timedelta(microseconds=1)).astimezone(dt.timezone.utc)


def start_of_day_utc(d: dt.date) -> dt.datetime:
    return dt.datetime.combine(d, dt.time(0, 0), LONDON).astimezone(dt.timezone.utc)


def parse_since(value: str, today: dt.date) -> dt.date:
    """'monday', 'today', 'yesterday', 'this week', '7d', '2w' or 'YYYY-MM-DD'."""
    v = value.strip().lower()
    if v in ("today",):
        return today
    if v in ("yesterday",):
        return today - dt.timedelta(days=1)
    if v in ("this week", "week"):
        v = "monday"
    if v in ("last week",):
        return today - dt.timedelta(days=today.weekday() + 7)
    if v in _WEEKDAYS:
        back = (today.weekday() - _WEEKDAYS.index(v)) % 7
        return today - dt.timedelta(days=back)
    m = re.fullmatch(r"(\d+)\s*([dw])", v)
    if m:
        n = int(m.group(1)) * (7 if m.group(2) == "w" else 1)
        return today - dt.timedelta(days=n)
    try:
        return dt.date.fromisoformat(v)
    except ValueError as exc:
        raise ValueError(
            f'Can\'t read --since "{value}". Use a weekday, today, yesterday, this week, 7d, 2w or YYYY-MM-DD.'
        ) from exc
