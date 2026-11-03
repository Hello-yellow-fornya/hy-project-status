"""Fetch STATUS.md and live activity from GitHub, a local clone, or Drive.

Every fetcher returns plain data. Errors become SourceUnavailable, which the
renderer turns into a '⚠ <source> not accessible' warning. Nothing here guesses.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from hy_status.registry import ROOT


class SourceUnavailable(Exception):
    pass


class NotFound(Exception):
    pass


@dataclass
class Commit:
    sha: str
    when: dt.datetime        # aware, UTC
    subject: str


@dataclass
class DriveFile:
    name: str
    modified: dt.datetime    # aware, UTC
    url: str | None = None


@dataclass
class StatusText:
    text: str
    ref: str | None          # short sha of the commit holding this version, when known
    committed: dt.datetime | None   # when STATUS.md last changed in git, when known


def _parse_iso(s: str) -> dt.datetime:
    d = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    return d.astimezone(dt.timezone.utc)


# ---------------------------------------------------------------- repos

class RepoSource:
    def status_text(self, repo: str) -> StatusText: ...
    def commits_since(self, repo: str, since: dt.datetime) -> list[Commit]: ...


class GitHubRepos(RepoSource):
    """GitHub REST API with a read-only token (HY_STATUS_GITHUB_TOKEN or GITHUB_TOKEN)."""

    API = "https://api.github.com"

    def __init__(self, token: str | None = None, opener=None):
        self.token = token or os.environ.get("HY_STATUS_GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN")
        self._open = opener or urllib.request.urlopen

    def _get(self, path: str, params: dict | None = None, raw: bool = False):
        url = f"{self.API}{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url)
        req.add_header("Accept", "application/vnd.github.raw" if raw else "application/vnd.github+json")
        req.add_header("X-GitHub-Api-Version", "2022-11-28")
        req.add_header("User-Agent", "hy-status")
        if self.token:
            req.add_header("Authorization", f"Bearer {self.token}")
        try:
            with self._open(req, timeout=20) as resp:
                body = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise NotFound(path) from exc
            raise SourceUnavailable(f"GitHub {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise SourceUnavailable(str(exc)) from exc
        return body if raw else json.loads(body)

    def status_text(self, repo: str) -> StatusText:
        try:
            text = self._get(f"/repos/{repo}/contents/STATUS.md", raw=True)
        except NotFound:
            # 404 is also what GitHub returns for a repo the token can't see.
            try:
                self._get(f"/repos/{repo}")
            except NotFound as exc:
                raise SourceUnavailable("repo not found or no access") from exc
            raise
        commits = self._get(f"/repos/{repo}/commits", {"path": "STATUS.md", "per_page": 1})
        ref = committed = None
        if commits:
            ref = commits[0]["sha"][:7]
            committed = _parse_iso(commits[0]["commit"]["committer"]["date"])
        return StatusText(text, ref, committed)

    def commits_since(self, repo: str, since: dt.datetime) -> list[Commit]:
        out: list[Commit] = []
        page = 1
        while page <= 5:
            batch = self._get(
                f"/repos/{repo}/commits",
                {"since": since.strftime("%Y-%m-%dT%H:%M:%SZ"), "per_page": 100, "page": page},
            )
            for c in batch:
                if len(c.get("parents") or []) > 1:
                    continue  # merge commits: count the work, not the merge
                when = _parse_iso(c["commit"]["committer"]["date"])
                if when > since:
                    out.append(Commit(c["sha"][:7], when, c["commit"]["message"].splitlines()[0]))
            if len(batch) < 100:
                break
            page += 1
        return sorted(out, key=lambda c: c.when, reverse=True)


class LocalRepos(RepoSource):
    """Read repos from local clones: <base>/<repo-name>. For Claude Code sessions and testing.

    Reads the working tree, so an uncommitted STATUS.md is shown as written.
    """

    def __init__(self, base: str | Path):
        self.base = Path(base)

    def _dir(self, repo: str) -> Path:
        d = self.base / repo.split("/", 1)[1]
        if not (d / ".git").exists():
            raise SourceUnavailable(f"no local clone at {d}")
        return d

    def _git(self, d: Path, *args: str) -> str:
        try:
            return subprocess.run(["git", "-C", str(d), *args], check=True,
                                  capture_output=True, text=True).stdout
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            raise SourceUnavailable(f"git failed in {d}") from exc

    def status_text(self, repo: str) -> StatusText:
        d = self._dir(repo)
        f = d / "STATUS.md"
        if not f.exists():
            raise NotFound(str(f))
        out = self._git(d, "log", "-1", "--format=%h %cI", "--", "STATUS.md").strip()
        ref = committed = None
        if out:
            ref, iso = out.split(" ", 1)
            committed = _parse_iso(iso)
        return StatusText(f.read_text(encoding="utf-8"), ref, committed)

    def commits_since(self, repo: str, since: dt.datetime) -> list[Commit]:
        d = self._dir(repo)
        out = self._git(d, "log", "--no-merges", f"--since={since.isoformat()}", "--format=%h\t%cI\t%s")
        commits = []
        for line in out.splitlines():
            sha, iso, subject = line.split("\t", 2)
            when = _parse_iso(iso)
            if when > since:
                commits.append(Commit(sha, when, subject))
        return commits


# ---------------------------------------------------------------- this repo (Drive-only STATUS files)

class RegistryRepoStatus:
    """STATUS.md for Drive-only sections: projects/<section-id>/STATUS.md in this repo."""

    def __init__(self, root: Path = ROOT):
        self.root = Path(root)

    def status_text(self, section_id: str) -> StatusText:
        rel = f"projects/{section_id}/STATUS.md"
        f = self.root / rel
        if not f.exists():
            raise NotFound(rel)
        ref = committed = None
        try:
            out = subprocess.run(["git", "-C", str(self.root), "log", "-1", "--format=%h %cI", "--", rel],
                                 check=True, capture_output=True, text=True).stdout.strip()
            if out:
                ref, iso = out.split(" ", 1)
                committed = _parse_iso(iso)
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
        return StatusText(f.read_text(encoding="utf-8"), ref, committed)


# ---------------------------------------------------------------- Drive

class DriveSource:
    def files_modified_since(self, folder_id: str, since: dt.datetime) -> list[DriveFile]: ...


class GoogleDrive(DriveSource):
    """Drive v3 files.list on one folder (top level), read-only.

    Credentials: HY_STATUS_DRIVE_TOKEN (an OAuth access token), or a service-account
    JSON at GOOGLE_APPLICATION_CREDENTIALS when the google-auth package is installed.
    Folders are looked up by ID only.
    """

    API = "https://www.googleapis.com/drive/v3/files"

    def __init__(self, token: str | None = None, opener=None):
        self._token = token or os.environ.get("HY_STATUS_DRIVE_TOKEN")
        self._open = opener or urllib.request.urlopen

    def _access_token(self) -> str:
        if self._token:
            return self._token
        key = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if not key:
            raise SourceUnavailable("no Drive credentials configured")
        try:
            from google.auth.transport.requests import Request  # type: ignore
            from google.oauth2 import service_account  # type: ignore
        except ImportError as exc:
            raise SourceUnavailable("google-auth not installed") from exc
        creds = service_account.Credentials.from_service_account_file(
            key, scopes=["https://www.googleapis.com/auth/drive.metadata.readonly"])
        creds.refresh(Request())
        self._token = creds.token
        return self._token

    def files_modified_since(self, folder_id: str, since: dt.datetime) -> list[DriveFile]:
        q = (f"'{folder_id}' in parents and trashed = false and "
             f"modifiedTime > '{since.strftime('%Y-%m-%dT%H:%M:%SZ')}'")
        params = {
            "q": q, "orderBy": "modifiedTime desc", "pageSize": 50,
            "fields": "files(name,modifiedTime,webViewLink)",
            "supportsAllDrives": "true", "includeItemsFromAllDrives": "true",
        }
        req = urllib.request.Request(f"{self.API}?{urllib.parse.urlencode(params)}")
        req.add_header("Authorization", f"Bearer {self._access_token()}")
        try:
            with self._open(req, timeout=20) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise SourceUnavailable(f"Drive {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise SourceUnavailable(str(exc)) from exc
        return [DriveFile(f["name"], _parse_iso(f["modifiedTime"]), f.get("webViewLink"))
                for f in data.get("files", [])]


class NoLiveChecks(RepoSource, DriveSource):
    """--offline: skip live checks entirely (no warnings from them)."""

    def commits_since(self, repo, since):
        return []

    def files_modified_since(self, folder_id, since):
        return []
