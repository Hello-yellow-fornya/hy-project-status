"""Parse and check STATUS.md files."""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field

import yaml

STAGES = ("Pitch", "Onboarding", "Discovery", "Build", "Review", "Live", "Optimise", "Reporting")
STATUSES = ("active", "paused", "closed")
REQUIRED = ("section", "stage", "status", "updated", "last_action", "next_step")

_FRONT = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*(?:\n|\Z)(.*)\Z", re.S)
_LOG_LINE = re.compile(r"^\s*[-*]\s+(\d{4}-\d{2}-\d{2})\s*·\s*(.+?)\s*$")


class StatusParseError(Exception):
    """Raised with the short reason that goes after '⚠ STATUS.md unreadable: '."""


@dataclass
class LogEntry:
    date: dt.date
    text: str            # everything after the date, e.g. "Build · built X · Deck: <link>"


@dataclass
class Status:
    section: str
    stage: str
    status: str
    updated: dt.date
    last_action: str
    next_step: str
    blockers: str | None = None
    outputs: list[dict] = field(default_factory=list)
    log: list[LogEntry] = field(default_factory=list)


def _as_date(v) -> dt.date:
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    return dt.date.fromisoformat(str(v).strip())


def parse(text: str) -> Status:
    m = _FRONT.match(text.lstrip("﻿"))
    if not m:
        raise StatusParseError("no header")
    try:
        head = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError as exc:
        raise StatusParseError("header is not valid YAML") from exc
    if not isinstance(head, dict):
        raise StatusParseError("header is not valid YAML")
    for key in REQUIRED:
        if head.get(key) in (None, ""):
            raise StatusParseError(f"{key} missing")
    try:
        updated = _as_date(head["updated"])
    except ValueError as exc:
        raise StatusParseError("updated is not YYYY-MM-DD") from exc

    log: list[LogEntry] = []
    for line in m.group(2).splitlines():
        lm = _LOG_LINE.match(line)
        if lm:
            try:
                log.append(LogEntry(dt.date.fromisoformat(lm.group(1)), lm.group(2)))
            except ValueError:
                continue

    outputs = head.get("outputs") or []
    if not isinstance(outputs, list):
        outputs = []
    blockers = head.get("blockers")
    return Status(
        section=str(head["section"]).strip(),
        stage=str(head["stage"]).strip(),
        status=str(head["status"]).strip().lower(),
        updated=updated,
        last_action=" ".join(str(head["last_action"]).split()),
        next_step=" ".join(str(head["next_step"]).split()),
        blockers=None if blockers in (None, "") else " ".join(str(blockers).split()),
        outputs=[o for o in outputs if isinstance(o, dict)],
        log=log,
    )


_DATEISH = re.compile(
    r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}/\d{1,2}(/\d{2,4})?\b|"
    r"\b\d{1,2}(st|nd|rd|th)?\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b|"
    r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2}(st|nd|rd|th)?\b|"
    r"\b(today|yesterday|this week|last week)\b",
    re.I,
)


def check_last_action(text: str, banned_names: tuple[str, ...] = ()) -> list[str]:
    """Problems with a last_action phrase, per the STATUS.md rules. Empty list = fine."""
    problems: list[str] = []
    words = text.split()
    if len(words) > 12:
        problems.append(f"last_action is {len(words)} words; keep it to about 12")
    if text.rstrip().endswith("."):
        problems.append("last_action ends with a full stop")
    if words:
        first = words[0]
        is_acronym = len(first) > 1 and first[:2].isupper()
        if first[0].isupper() and not is_acronym:
            problems.append(f'last_action starts with a capital ("{first}"); start with a lowercase past-tense verb')
    if _DATEISH.search(text):
        problems.append("last_action contains a date; the date comes from 'updated'")
    low = text.lower()
    for name in banned_names:
        if name and re.search(rf"(^|\W){re.escape(name.lower())}(\W|$)", low):
            problems.append(f'last_action repeats "{name}", which the line already shows')
            break
    return problems


def check(status: Status, expected_section: str | None, today: dt.date,
          banned_names: tuple[str, ...] = ()) -> list[str]:
    problems: list[str] = []
    if expected_section and status.section != expected_section:
        problems.append(f"section is '{status.section}' but projects.yaml expects '{expected_section}'")
    if status.stage not in STAGES:
        problems.append(f"stage '{status.stage}' is not one of: {', '.join(STAGES)}")
    if status.status not in STATUSES:
        problems.append(f"status '{status.status}' is not one of: {', '.join(STATUSES)}")
    if status.updated > today:
        problems.append(f"updated ({status.updated}) is in the future")
    problems += check_last_action(status.last_action, banned_names)
    if status.log and status.log != sorted(status.log, key=lambda e: e.date, reverse=True):
        problems.append("Log is not newest first")
    return problems
