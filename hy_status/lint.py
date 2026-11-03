"""hy-status lint: check projects.yaml and STATUS.md files against the agreed format."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from hy_status import registry
from hy_status.sources import NotFound, RegistryRepoStatus, RepoSource, SourceUnavailable
from hy_status.statusfile import StatusParseError, check, parse


def _banned(section: registry.Section | None) -> tuple[str, ...]:
    if not section:
        return ()
    return (section.label, section.client_code, section.client_name)


def lint_text(text: str, where: str, section: registry.Section | None, today: dt.date) -> list[str]:
    try:
        st = parse(text)
    except StatusParseError as exc:
        return [f"{where}: unreadable: {exc}"]
    return [f"{where}: {p}" for p in check(st, section.id if section else None, today, _banned(section))]


def run(files: list[str], *, registry_path: Path, repos: RepoSource, registry_repo: RegistryRepoStatus,
        today: dt.date) -> tuple[list[str], list[str]]:
    """Returns (problems, notes)."""
    problems: list[str] = []
    notes: list[str] = []
    try:
        clients = registry.load(registry_path)
    except registry.RegistryError as exc:
        return [f"projects.yaml: {exc}"], notes
    by_id = {s.id: s for s in registry.all_sections(clients)}

    if files:
        for f in files:
            text = Path(f).read_text(encoding="utf-8")
            sec = None
            try:
                sec = by_id.get(parse(text).section)
            except StatusParseError:
                pass
            if sec is None:
                notes.append(f"{f}: section not found in projects.yaml, so the section id and names weren't checked")
            problems += lint_text(text, f, sec, today)
        return problems, notes

    notes.append(f"projects.yaml: {len(by_id)} section(s) OK")
    for sec in by_id.values():
        try:
            if sec.main_repo:
                st = repos.status_text(sec.main_repo)
            else:
                st = registry_repo.status_text(sec.id)
        except NotFound:
            problems.append(f"{sec.status_location}: no STATUS.md found")
            continue
        except SourceUnavailable as exc:
            notes.append(f"{sec.status_location}: not checked ({exc})")
            continue
        problems += lint_text(st.text, sec.status_location, sec, today)
    return problems, notes
