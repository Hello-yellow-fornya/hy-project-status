"""Gather everything known about a section into a SectionReport. No rendering here."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from hy_status import dates
from hy_status.registry import Section
from hy_status.sources import (Commit, DriveFile, DriveSource, NotFound, RegistryRepoStatus,
                               RepoSource, SourceUnavailable)
from hy_status.statusfile import Status, StatusParseError, parse

STALE_DAYS = 14


@dataclass
class SectionReport:
    section: Section
    today: dt.date
    status: Status | None = None
    missing: bool = False                     # no STATUS.md at the expected place
    unreadable: str | None = None             # reason, when STATUS.md didn't parse
    status_ref: str | None = None             # short sha of STATUS.md
    baseline: dt.datetime | None = None       # "since STATUS.md": its last commit, else end of 'updated'
    commits_after: list[Commit] = field(default_factory=list)
    drive_after: list[DriveFile] = field(default_factory=list)
    window_start: dt.date | None = None
    commits_in_window: list[Commit] = field(default_factory=list)
    drive_in_window: list[DriveFile] = field(default_factory=list)
    unavailable: list[str] = field(default_factory=list)   # "repo", "Drive"

    @property
    def stale(self) -> bool:
        s = self.status
        if not s or s.status != "active":
            return False
        if (self.today - s.updated).days < STALE_DAYS:
            return False
        return not self.commits_after and not self.drive_after


def build(section: Section, *, today: dt.date, repos: RepoSource, drive: DriveSource,
          registry_repo: RegistryRepoStatus, live: bool = True,
          window_start: dt.date | None = None) -> SectionReport:
    r = SectionReport(section=section, today=today, window_start=window_start)

    # 1. STATUS.md
    try:
        if section.main_repo:
            st = repos.status_text(section.main_repo)
        else:
            st = registry_repo.status_text(section.id)
    except NotFound:
        r.missing = True
        st = None
    except SourceUnavailable:
        r.unavailable.append("repo")
        return r
    if st is not None:
        r.status_ref = st.ref
        try:
            r.status = parse(st.text)
        except StatusParseError as exc:
            r.unreadable = str(exc)
        if r.status:
            r.baseline = st.committed or dates.end_of_day_utc(r.status.updated)

    if not live:
        return r

    # 2. Live checks: one call per source covering both the baseline and the detail window
    starts = []
    if r.baseline:
        starts.append(r.baseline)
    if window_start:
        starts.append(dates.start_of_day_utc(window_start))
    if not starts:
        return r
    since = min(starts)

    if section.main_repo and "repo" not in r.unavailable:
        try:
            commits = repos.commits_since(section.main_repo, since)
        except (SourceUnavailable, NotFound):
            r.unavailable.append("repo")
            commits = []
        if r.baseline:
            r.commits_after = [c for c in commits if c.when > r.baseline]
        if window_start:
            ws = dates.start_of_day_utc(window_start)
            r.commits_in_window = [c for c in commits if c.when >= ws]

    files: list[DriveFile] = []
    for fid in section.all_drive_folder_ids:
        try:
            files += drive.files_modified_since(fid, since)
        except SourceUnavailable:
            if "Drive" not in r.unavailable:
                r.unavailable.append("Drive")
    files.sort(key=lambda f: f.modified, reverse=True)
    if r.baseline:
        r.drive_after = [f for f in files if f.modified > r.baseline]
    if window_start:
        ws = dates.start_of_day_utc(window_start)
        r.drive_in_window = [f for f in files if f.modified >= ws]
    return r
