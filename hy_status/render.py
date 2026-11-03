"""Fixed templates. Every word of output comes from here, projects.yaml or STATUS.md."""

from __future__ import annotations

import datetime as dt

from hy_status import dates
from hy_status.report import SectionReport

RULE = "─" * 68


def _where(r: SectionReport) -> str:
    s = r.section
    if s.main_repo:
        return f"main repo is {s.main_repo}"
    return f"main folder is {s.main_folder.path}"


def _rel_utc(when: dt.datetime, today: dt.date) -> str:
    return dates.relative(when.astimezone(dates.LONDON).date(), today)


def warnings(r: SectionReport) -> list[str]:
    """In the fixed order from the design doc."""
    out: list[str] = []
    if r.missing:
        out.append("no STATUS.md found")
    if r.unreadable:
        out.append(f"STATUS.md unreadable: {r.unreadable}")
    if r.commits_after:
        n = len(r.commits_after)
        out.append(f"repo has {n} commit{'s' if n != 1 else ''} since STATUS.md "
                   f"(latest {_rel_utc(r.commits_after[0].when, r.today)})")
    if r.drive_after:
        out.append(f"Drive folder changed since STATUS.md (latest {_rel_utc(r.drive_after[0].modified, r.today)})")
    if r.stale:
        out.append("stale")
    for src in r.unavailable:
        out.append(f"{src} not accessible")
    return out


def _suffix(r: SectionReport) -> str:
    w = warnings(r)
    return f" ⚠ {'; '.join(w)}" if w else ""


def line(r: SectionReport) -> str:
    s = r.status
    head = f"{r.section.label} – {_where(r)}"
    if not s:
        return head + _suffix(r)
    return (f"{head}, last updated {dates.relative(s.updated, r.today)} ({dates.display_date(s.updated)}), "
            f"last change: {s.last_action}{_suffix(r)}")


def lines(reports: list[SectionReport], group_by_client: bool = False) -> str:
    if not group_by_client:
        return "\n".join(line(r) for r in reports)
    out: list[str] = []
    current = None
    for r in reports:
        if r.section.client_code != current:
            if out:
                out.append("")
            current = r.section.client_code
            out.append(f"{r.section.client_name} ({current})")
        out.append(line(r))
    return "\n".join(out)


def card(r: SectionReport, generated: dt.datetime) -> str:
    sec, s = r.section, r.status
    owner = f"owner: {sec.owner}" if sec.owner else ""
    out = [f"{sec.label}{owner.rjust(max(1, 68 - len(sec.label)))}" if owner else sec.label, RULE]

    if s:
        out += [
            f"Stage         {s.stage}" + ("" if s.status == "active" else f" ({s.status})"),
            f"Last action   {s.updated.isoformat()} · {s.last_action}",
            f"Next          {s.next_step}",
            f"Blockers      {s.blockers or 'none'}",
        ]
    elif r.missing:
        out.append(f"No STATUS.md at {sec.status_location}")
    elif r.unreadable:
        out.append(f"STATUS.md at {sec.status_location} is unreadable: {r.unreadable}")
    else:
        out.append(f"STATUS.md at {sec.status_location} could not be reached")

    out += ["", "Where it lives"]
    if sec.main_repo:
        out.append(f"  Repo        github.com/{sec.main_repo}")
    if sec.main_folder:
        out.append(f"  Drive       {sec.main_folder.path} (https://drive.google.com/drive/folders/{sec.main_folder.id})")
    for fid in sec.drive_folders:
        if not sec.main_folder or fid != sec.main_folder.id:
            out.append(f"  Drive       https://drive.google.com/drive/folders/{fid}")
    if s and s.outputs:
        for i, o in enumerate(s.outputs):
            label = "  Outputs     " if i == 0 else "              "
            out.append(f"{label}{o.get('label', 'output')} ({o.get('url', 'no link')})")

    if r.window_start:
        out += ["", f"Activity since {r.window_start.strftime('%a')} {r.window_start.isoformat()}"]
        items: list[tuple[dt.date, str, str]] = []
        if s:
            items += [(e.date, "STATUS", e.text) for e in s.log if e.date >= r.window_start]
        by_day: dict[dt.date, list] = {}
        for c in r.commits_in_window:
            by_day.setdefault(c.when.astimezone(dates.LONDON).date(), []).append(c)
        for day, cs in by_day.items():
            n = len(cs)
            items.append((day, "GitHub", f'{n} commit{"s" if n != 1 else ""}, latest "{cs[0].subject}"'))
        for f in r.drive_in_window[:10]:
            items.append((f.modified.astimezone(dates.LONDON).date(), "Drive", f'"{f.name}" modified'))
        order = {"STATUS": 0, "GitHub": 1, "Drive": 2}
        items.sort(key=lambda t: (t[0], order[t[1]]))
        if items:
            out += [f"  {d.isoformat()}  {src:<6}  {text}" for d, src, text in items]
        else:
            out.append("  No recorded activity in this window")

    w = warnings(r)
    if w:
        out += [""] + [f"⚠ {x}" for x in w]

    srcs = []
    srcs.append(f"STATUS.md @ {r.status_ref}" if r.status_ref else "STATUS.md")
    if sec.main_repo:
        srcs.append("GitHub")
    if sec.all_drive_folder_ids:
        srcs.append("Drive")
    stamp = generated.astimezone(dates.LONDON).strftime("%Y-%m-%d %H:%M")
    out += ["", f"Sources: {' · '.join(srcs)} · generated {stamp}"]
    return "\n".join(out)
