"""projects.yaml: clients and their sections (workstreams).

Only sections listed here can be read by the tool.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REGISTRY = ROOT / "projects.yaml"


class RegistryError(Exception):
    pass


@dataclass(frozen=True)
class DriveFolder:
    id: str            # authoritative: every Drive lookup uses this
    path: str          # display only: printed in the line, never used to look anything up


@dataclass(frozen=True)
class Section:
    id: str
    label: str
    client_code: str
    client_name: str
    owner: str | None
    main_repo: str | None = None
    main_folder: DriveFolder | None = None
    drive_folders: tuple[str, ...] = ()

    @property
    def status_location(self) -> str:
        """Where STATUS.md lives, per the agreed rule."""
        if self.main_repo:
            return f"{self.main_repo}/STATUS.md"
        return f"projects/{self.id}/STATUS.md"

    @property
    def all_drive_folder_ids(self) -> tuple[str, ...]:
        ids = list(self.drive_folders)
        if self.main_folder and self.main_folder.id not in ids:
            ids.insert(0, self.main_folder.id)
        return tuple(ids)


@dataclass
class Client:
    code: str
    name: str
    aliases: tuple[str, ...]
    sections: list[Section] = field(default_factory=list)


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower().replace("'", "")).strip()


def load(path: Path | str = DEFAULT_REGISTRY) -> list[Client]:
    path = Path(path)
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    except FileNotFoundError as exc:
        raise RegistryError(f"No registry at {path}") from exc
    if not isinstance(raw, list):
        raise RegistryError("projects.yaml must be a list of clients")

    clients: list[Client] = []
    seen_ids: set[str] = set()
    for i, c in enumerate(raw):
        where = f"projects.yaml client #{i + 1}"
        if not isinstance(c, dict) or not c.get("client") or not c.get("name"):
            raise RegistryError(f"{where}: needs 'client' and 'name'")
        client = Client(
            code=str(c["client"]),
            name=str(c["name"]),
            aliases=tuple(str(a) for a in c.get("aliases") or ()),
        )
        for s in c.get("sections") or ():
            sid = s.get("id")
            if not sid or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", str(sid)):
                raise RegistryError(f"{where}: section id '{sid}' must be lowercase letters, digits and hyphens")
            if sid in seen_ids:
                raise RegistryError(f"duplicate section id '{sid}'")
            seen_ids.add(sid)
            if not s.get("label"):
                raise RegistryError(f"section {sid}: needs a 'label'")
            repo, folder = s.get("main_repo"), s.get("main_folder")
            if bool(repo) == bool(folder):
                raise RegistryError(f"section {sid}: needs exactly one of 'main_repo' or 'main_folder'")
            if repo and not re.fullmatch(r"[\w.-]+/[\w.-]+", str(repo)):
                raise RegistryError(f"section {sid}: main_repo must be owner/repo")
            main_folder = None
            if folder:
                if not isinstance(folder, dict) or not folder.get("id") or not folder.get("path"):
                    raise RegistryError(f"section {sid}: main_folder needs 'id' (used for lookups) and 'path' (display only)")
                main_folder = DriveFolder(id=str(folder["id"]), path=str(folder["path"]))
            client.sections.append(
                Section(
                    id=str(sid),
                    label=str(s["label"]),
                    client_code=client.code,
                    client_name=client.name,
                    owner=s.get("owner"),
                    main_repo=str(repo) if repo else None,
                    main_folder=main_folder,
                    drive_folders=tuple(str(x) for x in s.get("drive_folders") or ()),
                )
            )
        clients.append(client)
    return clients


def all_sections(clients: list[Client]) -> list[Section]:
    out = [s for c in clients for s in c.sections]
    return sorted(out, key=lambda s: (s.client_code.lower(), s.label.lower()))


def resolve(clients: list[Client], query: str) -> list[Section]:
    """Sections matching a client code/name/alias, a section id or a section label.

    A client match returns all its sections. Returns [] when nothing matches.
    """
    q = _norm(query)
    if not q:
        return []
    for c in clients:
        names = {_norm(c.code), _norm(c.name), *(_norm(a) for a in c.aliases)}
        if q in names:
            return sorted(c.sections, key=lambda s: s.label.lower())
    hits = [s for c in clients for s in c.sections if q in (_norm(s.id), _norm(s.label))]
    if hits:
        return hits
    # "<client> <words>" -> sections of that client whose label contains the words
    for c in clients:
        for name in {_norm(c.code), _norm(c.name), *(_norm(a) for a in c.aliases)}:
            if name and q.startswith(name + " "):
                rest = q[len(name) + 1:]
                hits = [s for s in c.sections if rest in _norm(s.label) or rest in _norm(s.id)]
                if hits:
                    return hits
    return []


def closest(clients: list[Client], query: str, n: int = 3) -> list[str]:
    candidates: dict[str, str] = {}
    for c in clients:
        for name in (c.code, c.name, *c.aliases):
            candidates[_norm(name)] = c.code
        for s in c.sections:
            candidates[_norm(s.label)] = s.label
            candidates[_norm(s.id)] = s.id
    matches = difflib.get_close_matches(_norm(query), list(candidates), n=n * 2, cutoff=0.5)
    out: list[str] = []
    for m in matches:
        if candidates[m] not in out:
            out.append(candidates[m])
    return out[:n]
