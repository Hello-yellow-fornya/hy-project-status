"""hy-status command line."""

from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
from pathlib import Path

from hy_status import dates, lint, registry, render, report
from hy_status.sources import (GitHubRepos, GoogleDrive, LocalRepos, NoLiveChecks,
                               RegistryRepoStatus)

DEFAULT_WINDOW_DAYS = 14


def _common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--registry", default=str(registry.DEFAULT_REGISTRY), help=argparse.SUPPRESS)
    p.add_argument("--local-repos", default=os.environ.get("HY_STATUS_LOCAL_REPOS"),
                   help="read repos from local clones in this folder instead of GitHub")
    p.add_argument("--today", help=argparse.SUPPRESS)          # YYYY-MM-DD, for tests
    p.add_argument("--now", help=argparse.SUPPRESS)            # ISO datetime, for tests


def _status_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="hy-status",
        description="Factual status for Hello Yellow client workstreams. "
                    "One line per section by default; --detail for the full card. "
                    "'hy-status lint [STATUS.md ...]' checks the format.",
    )
    p.add_argument("query", nargs="*", help="client code, client name, alias, section id or section label")
    p.add_argument("--all", action="store_true", help="every section, grouped by client")
    p.add_argument("--detail", action="store_true", help="full card per section")
    p.add_argument("--since", help="activity window for --detail: monday, this week, 7d, YYYY-MM-DD (implies --detail)")
    p.add_argument("--offline", action="store_true", help="skip live GitHub/Drive checks")
    _common(p)
    return p


def _now(args) -> dt.datetime:
    if args.now:
        return dt.datetime.fromisoformat(args.now).astimezone(dt.timezone.utc)
    if args.today:
        d = dt.date.fromisoformat(args.today)
        return dt.datetime.combine(d, dt.time(12, 0), dates.LONDON).astimezone(dt.timezone.utc)
    return dt.datetime.now(dt.timezone.utc)


def _repos(args):
    return LocalRepos(args.local_repos) if args.local_repos else GitHubRepos()


def main(argv: list[str] | None = None, *, repos=None, drive=None, registry_repo=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "lint":
        return _lint(argv[1:], repos=repos, registry_repo=registry_repo)

    args = _status_parser().parse_args(argv)
    now = _now(args)
    today = dates.today_london(now)
    query = " ".join(args.query).strip()
    if not query and not args.all:
        print("Name a client or section (e.g. hy-status REV), or use --all.", file=sys.stderr)
        return 2

    try:
        clients = registry.load(args.registry)
    except registry.RegistryError as exc:
        print(f"projects.yaml: {exc}", file=sys.stderr)
        return 1

    if args.all:
        sections = registry.all_sections(clients)
    else:
        sections = registry.resolve(clients, query)
        if not sections:
            near = registry.closest(clients, query)
            msg = f'No project matches "{query}".'
            if near:
                msg += f" Closest: {', '.join(near)}"
            print(msg)
            return 2

    detail = args.detail or bool(args.since)
    try:
        window = (dates.parse_since(args.since, today) if args.since
                  else today - dt.timedelta(days=DEFAULT_WINDOW_DAYS)) if detail else None
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    repos = repos or _repos(args)
    drive = drive or (NoLiveChecks() if args.offline else GoogleDrive())
    registry_repo = registry_repo or RegistryRepoStatus(Path(args.registry).resolve().parent)

    reports = [
        report.build(s, today=today, repos=repos, drive=drive, registry_repo=registry_repo,
                     live=not args.offline, window_start=window)
        for s in sections
    ]
    if detail:
        print("\n\n".join(render.card(r, now) for r in reports))
    else:
        print(render.lines(reports, group_by_client=args.all))
    return 0


def _lint(argv: list[str], *, repos=None, registry_repo=None) -> int:
    p = argparse.ArgumentParser(prog="hy-status lint",
                                description="Check projects.yaml and STATUS.md files. "
                                            "With no files, checks every registered section.")
    p.add_argument("files", nargs="*")
    _common(p)
    args = p.parse_args(argv)
    today = dates.today_london(_now(args))
    problems, notes = lint.run(
        args.files,
        registry_path=Path(args.registry),
        repos=repos or _repos(args),
        registry_repo=registry_repo or RegistryRepoStatus(Path(args.registry).resolve().parent),
        today=today,
    )
    for n in notes:
        print(n)
    for x in problems:
        print(f"✗ {x}")
    if not problems:
        print("✓ no problems")
    return 1 if problems else 0
