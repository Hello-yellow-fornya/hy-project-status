import datetime as dt
import io
import tempfile
import textwrap
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from hy_status import cli, dates, render, report
from hy_status.registry import RegistryError, load, resolve
from hy_status.sources import Commit, DriveFile, NotFound, SourceUnavailable, StatusText
from hy_status.statusfile import StatusParseError, check_last_action, parse

UTC = dt.timezone.utc

# Test fixtures use made-up names on purpose; none of these exist in projects.yaml.
REGISTRY = textwrap.dedent("""
    - client: ACME
      name: Acme Ltd
      aliases: [acme]
      sections:
        - id: acme-web
          label: Acme Web
          main_repo: example-org/acme-web
          owner: Pat
        - id: acme-reports
          label: Acme Reports
          main_folder: {id: FOLDER123, path: Clients/Acme/Reports}
          owner: Lee
""")

STATUS_WEB = textwrap.dedent("""
    ---
    section: acme-web
    stage: Build
    status: active
    updated: 2026-11-02
    last_action: built checkout flow and shared for review
    next_step: Client review, due 2026-11-06 (Pat)
    outputs:
      - label: Prototype
        url: https://example.com/p
    blockers: none
    ---

    ## Log
    - 2026-11-02 · Build · built checkout flow and shared for review
    - 2026-10-20 · Discovery · delivered audit
""").lstrip()


def status_for(section, updated, last_action="delivered monthly report", status="active"):
    return textwrap.dedent(f"""
        ---
        section: {section}
        stage: Reporting
        status: {status}
        updated: {updated}
        last_action: {last_action}
        next_step: Send November report
        ---
    """).lstrip()


class FakeRepos:
    def __init__(self, files=None, commits=None, unavailable=()):
        self.files = files or {}
        self.commits = commits or {}
        self.unavailable = set(unavailable)

    def status_text(self, repo):
        if repo in self.unavailable:
            raise SourceUnavailable("no access")
        if repo not in self.files:
            raise NotFound(repo)
        return self.files[repo]

    def commits_since(self, repo, since):
        if repo in self.unavailable:
            raise SourceUnavailable("no access")
        return sorted([c for c in self.commits.get(repo, []) if c.when > since], key=lambda c: c.when, reverse=True)


class FakeRegistryRepo:
    def __init__(self, files=None):
        self.files = files or {}

    def status_text(self, sid):
        if sid not in self.files:
            raise NotFound(sid)
        return self.files[sid]


class FakeDrive:
    def __init__(self, files=None, fail=False):
        self.files = files or {}
        self.fail = fail

    def files_modified_since(self, fid, since):
        if self.fail:
            raise SourceUnavailable("no creds")
        return [f for f in self.files.get(fid, []) if f.modified > since]


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.reg = Path(self.tmp.name) / "projects.yaml"
        self.reg.write_text(REGISTRY)

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *argv, repos=None, drive=None, registry_repo=None):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = cli.main(["--registry", str(self.reg), *argv], repos=repos or FakeRepos(),
                            drive=drive or FakeDrive(), registry_repo=registry_repo or FakeRegistryRepo())
        return code, buf.getvalue().rstrip("\n")


class DatesTest(unittest.TestCase):
    def test_relative(self):
        t = dt.date(2026, 11, 3)
        cases = {0: "today", 1: "yesterday", 2: "2 days ago", 6: "6 days ago", 7: "1 week ago",
                 13: "1 week ago", 14: "2 weeks ago", 27: "3 weeks ago", 28: "1 month ago",
                 59: "1 month ago", 60: "2 months ago"}
        for days, want in cases.items():
            self.assertEqual(dates.relative(t - dt.timedelta(days=days), t), want, days)

    def test_display_date(self):
        self.assertEqual(dates.display_date(dt.date(2026, 11, 2)), "2 Nov 2026")

    def test_since(self):
        t = dt.date(2026, 11, 5)  # Thursday
        self.assertEqual(dates.parse_since("monday", t), dt.date(2026, 11, 2))
        self.assertEqual(dates.parse_since("this week", t), dt.date(2026, 11, 2))
        self.assertEqual(dates.parse_since("thursday", t), t)
        self.assertEqual(dates.parse_since("7d", t), dt.date(2026, 10, 29))
        self.assertEqual(dates.parse_since("2026-10-01", t), dt.date(2026, 10, 1))
        with self.assertRaises(ValueError):
            dates.parse_since("whenever", t)


class RegistryTest(Base):
    def test_resolve(self):
        clients = load(self.reg)
        self.assertEqual([s.id for s in resolve(clients, "ACME")], ["acme-reports", "acme-web"])
        self.assertEqual([s.id for s in resolve(clients, "acme ltd")], ["acme-reports", "acme-web"])
        self.assertEqual([s.id for s in resolve(clients, "acme-web")], ["acme-web"])
        self.assertEqual([s.id for s in resolve(clients, "Acme Reports")], ["acme-reports"])
        self.assertEqual([s.id for s in resolve(clients, "acme reports")], ["acme-reports"])
        self.assertEqual(resolve(clients, "nobody"), [])

    def test_status_location(self):
        web, reports = sorted(load(self.reg)[0].sections, key=lambda s: s.id, reverse=True)
        self.assertEqual(web.status_location, "example-org/acme-web/STATUS.md")
        self.assertEqual(reports.status_location, "projects/acme-reports/STATUS.md")

    def test_needs_exactly_one_home(self):
        self.reg.write_text("- client: X\n  name: X\n  sections:\n    - {id: x, label: X}\n")
        with self.assertRaises(RegistryError):
            load(self.reg)

    def test_folder_needs_id(self):
        self.reg.write_text("- client: X\n  name: X\n  sections:\n"
                            "    - {id: x, label: X, main_folder: {path: Clients/X}}\n")
        with self.assertRaisesRegex(RegistryError, "id"):
            load(self.reg)


class StatusFileTest(unittest.TestCase):
    def test_parse(self):
        s = parse(STATUS_WEB)
        self.assertEqual(s.updated, dt.date(2026, 11, 2))
        self.assertEqual(s.last_action, "built checkout flow and shared for review")
        self.assertEqual(len(s.log), 2)
        self.assertEqual(s.outputs[0]["label"], "Prototype")

    def test_missing_field(self):
        with self.assertRaisesRegex(StatusParseError, "updated missing"):
            parse(STATUS_WEB.replace("updated: 2026-11-02\n", ""))

    def test_last_action_rules(self):
        self.assertEqual(check_last_action("delivered September performance report"), [])
        self.assertEqual(check_last_action("launched GA4 events on Meta and TikTok"), [])
        self.assertEqual(check_last_action("GA4 tags fixed on checkout"), [])  # acronym start is fine
        probs = check_last_action("The team has been working on creatives this week.")
        self.assertTrue(any("capital" in p for p in probs))
        self.assertTrue(any("full stop" in p for p in probs))
        self.assertTrue(any("date" in p for p in probs))
        self.assertTrue(any("words" in p for p in check_last_action(" ".join(["word"] * 13))))
        self.assertTrue(any("date" in p for p in check_last_action("built creatives on 2 Nov")))
        self.assertTrue(any("repeats" in p for p in check_last_action("built acme creatives", ("Acme",))))


class LineTest(Base):
    def test_repo_line_today(self):
        repos = FakeRepos({"example-org/acme-web": StatusText(STATUS_WEB, "abc1234",
                                                              dt.datetime(2026, 11, 2, 17, tzinfo=UTC))})
        code, out = self.run_cli("acme-web", "--today", "2026-11-03", repos=repos)
        self.assertEqual(code, 0)
        self.assertEqual(out, "Acme Web – main repo is example-org/acme-web, last updated yesterday (2 Nov 2026), "
                              "last change: built checkout flow and shared for review")

    def test_folder_line_and_stale(self):
        reg = FakeRegistryRepo({"acme-reports": StatusText(status_for("acme-reports", "2026-10-13"), None, None)})
        code, out = self.run_cli("acme reports", "--today", "2026-11-03", registry_repo=reg)
        self.assertEqual(out, "Acme Reports – main folder is Clients/Acme/Reports, last updated 3 weeks ago "
                              "(13 Oct 2026), last change: delivered monthly report ⚠ stale")

    def test_paused_is_not_stale(self):
        reg = FakeRegistryRepo({"acme-reports": StatusText(
            status_for("acme-reports", "2026-09-01", status="paused"), None, None)})
        _, out = self.run_cli("acme-reports", "--today", "2026-11-03", registry_repo=reg)
        self.assertNotIn("⚠", out)

    def test_commits_since_status(self):
        committed = dt.datetime(2026, 10, 30, 12, tzinfo=UTC)
        status = STATUS_WEB.replace("2026-11-02", "2026-10-30", 1)
        repos = FakeRepos(
            {"example-org/acme-web": StatusText(status, "abc1234", committed)},
            {"example-org/acme-web": [
                Commit("a", committed, "the STATUS commit itself"),
                Commit("b", dt.datetime(2026, 11, 1, 9, tzinfo=UTC), "x"),
                Commit("c", dt.datetime(2026, 11, 3, 9, tzinfo=UTC), "y"),
            ]},
        )
        _, out = self.run_cli("acme-web", "--today", "2026-11-03", repos=repos)
        self.assertTrue(out.endswith("last change: built checkout flow and shared for review "
                                     "⚠ repo has 2 commits since STATUS.md (latest today)"), out)

    def test_old_status_with_live_activity_is_not_stale(self):
        committed = dt.datetime(2026, 10, 1, 12, tzinfo=UTC)
        status = STATUS_WEB.replace("2026-11-02", "2026-10-01", 1)
        repos = FakeRepos({"example-org/acme-web": StatusText(status, "abc", committed)},
                          {"example-org/acme-web": [Commit("b", dt.datetime(2026, 11, 2, 9, tzinfo=UTC), "x")]})
        _, out = self.run_cli("acme-web", "--today", "2026-11-03", repos=repos)
        self.assertIn("⚠ repo has 1 commit since STATUS.md (latest yesterday)", out)
        self.assertNotIn("stale", out)

    def test_drive_changed_and_warning_order(self):
        reg = FakeRegistryRepo({"acme-reports": StatusText(status_for("acme-reports", "2026-10-01"), None, None)})
        drive = FakeDrive({"FOLDER123": [DriveFile("Report.xlsx", dt.datetime(2026, 11, 1, 10, tzinfo=UTC))]})
        _, out = self.run_cli("acme-reports", "--today", "2026-11-03", registry_repo=reg, drive=drive)
        self.assertTrue(out.endswith("⚠ Drive folder changed since STATUS.md (latest 2 days ago)"), out)

    def test_missing_status(self):
        _, out = self.run_cli("acme-web", "--today", "2026-11-03")
        self.assertEqual(out, "Acme Web – main repo is example-org/acme-web ⚠ no STATUS.md found")

    def test_unreadable_status(self):
        repos = FakeRepos({"example-org/acme-web": StatusText("no header here", None, None)})
        _, out = self.run_cli("acme-web", "--today", "2026-11-03", repos=repos)
        self.assertEqual(out, "Acme Web – main repo is example-org/acme-web ⚠ STATUS.md unreadable: no header")

    def test_repo_not_accessible(self):
        repos = FakeRepos(unavailable={"example-org/acme-web"})
        _, out = self.run_cli("acme-web", "--today", "2026-11-03", repos=repos)
        self.assertEqual(out, "Acme Web – main repo is example-org/acme-web ⚠ repo not accessible")

    def test_drive_not_accessible_still_prints_line(self):
        reg = FakeRegistryRepo({"acme-reports": StatusText(status_for("acme-reports", "2026-11-02"), None, None)})
        _, out = self.run_cli("acme-reports", "--today", "2026-11-03", registry_repo=reg, drive=FakeDrive(fail=True))
        self.assertTrue(out.endswith("last change: delivered monthly report ⚠ Drive not accessible"), out)

    def test_unknown_project(self):
        code, out = self.run_cli("acne", "--today", "2026-11-03")
        self.assertEqual(code, 2)
        self.assertTrue(out.startswith('No project matches "acne". Closest: ACME'), out)

    def test_all_groups_by_client(self):
        _, out = self.run_cli("--all", "--today", "2026-11-03", "--offline")
        self.assertEqual(out.splitlines()[0], "Acme Ltd (ACME)")
        self.assertEqual(len(out.splitlines()), 3)


class DetailTest(Base):
    def test_card(self):
        repos = FakeRepos(
            {"example-org/acme-web": StatusText(STATUS_WEB, "abc1234", dt.datetime(2026, 11, 2, 17, tzinfo=UTC))},
            {"example-org/acme-web": [Commit("c", dt.datetime(2026, 11, 3, 9, tzinfo=UTC), "Add specs")]},
        )
        _, out = self.run_cli("acme-web", "--since", "monday", "--now", "2026-11-03T10:14:00+00:00", repos=repos)
        self.assertIn("owner: Pat", out.splitlines()[0])
        for want in ["Stage         Build",
                     "Last action   2026-11-02 · built checkout flow and shared for review",
                     "Next          Client review, due 2026-11-06 (Pat)",
                     "Blockers      none",
                     "  Repo        github.com/example-org/acme-web",
                     "  Outputs     Prototype (https://example.com/p)",
                     "Activity since Mon 2026-11-02",
                     "  2026-11-02  STATUS  Build · built checkout flow and shared for review",
                     '  2026-11-03  GitHub  1 commit, latest "Add specs"',
                     "⚠ repo has 1 commit since STATUS.md (latest today)",
                     "Sources: STATUS.md @ abc1234 · GitHub · generated 2026-11-03 10:14"]:
            self.assertIn(want, out)
        self.assertNotIn("delivered audit", out)  # outside the window


class LintTest(Base):
    def test_lint_file(self):
        bad = Path(self.tmp.name) / "STATUS.md"
        bad.write_text(STATUS_WEB.replace("built checkout flow and shared for review",
                                          "Built Acme checkout flow on 2 Nov."))
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = cli.main(["lint", "--registry", str(self.reg), "--today", "2026-11-03", str(bad)],
                            repos=FakeRepos(), registry_repo=FakeRegistryRepo())
        out = buf.getvalue()
        self.assertEqual(code, 1)
        for want in ("full stop", "capital", "date", "repeats"):
            self.assertIn(want, out)


class RealRegistryTest(unittest.TestCase):
    def test_real_projects_yaml_loads(self):
        clients = load()
        ids = [s.id for c in clients for s in c.sections]
        self.assertEqual(len(ids), len(set(ids)))
        for banned in ("mcd", "ocg", "acme", "example"):
            self.assertFalse(any(banned in i for i in ids), f"example name '{banned}' in projects.yaml")


if __name__ == "__main__":
    unittest.main()


class GitHubReposTest(unittest.TestCase):
    def test_parsing_with_fake_http(self):
        import json
        import urllib.parse
        from hy_status.sources import GitHubRepos

        class Resp(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        seen = []

        def opener(req, timeout):
            url = urllib.parse.urlparse(req.full_url)
            seen.append((url.path, req.get_header("Accept")))
            q = urllib.parse.parse_qs(url.query)
            if url.path.endswith("/contents/STATUS.md"):
                return Resp(STATUS_WEB.encode())
            if q.get("path") == ["STATUS.md"]:
                body = [{"sha": "abc1234def", "parents": [{}],
                         "commit": {"committer": {"date": "2026-11-02T17:00:00Z"}, "message": "Update STATUS"}}]
            else:
                body = [
                    {"sha": "m" * 40, "parents": [{}, {}],
                     "commit": {"committer": {"date": "2026-11-03T09:00:00Z"}, "message": "Merge pull request"}},
                    {"sha": "c" * 40, "parents": [{}],
                     "commit": {"committer": {"date": "2026-11-03T08:00:00Z"}, "message": "Add specs\n\nbody"}},
                ]
            return Resp(json.dumps(body).encode())

        gh = GitHubRepos(token="t", opener=opener)
        st = gh.status_text("example-org/acme-web")
        self.assertEqual(st.ref, "abc1234")
        self.assertEqual(st.committed, dt.datetime(2026, 11, 2, 17, tzinfo=UTC))
        self.assertEqual(seen[0][1], "application/vnd.github.raw")
        commits = gh.commits_since("example-org/acme-web", dt.datetime(2026, 11, 2, 17, tzinfo=UTC))
        self.assertEqual([c.subject for c in commits], ["Add specs"])  # merge commit skipped
