# hy-status

A factual status read on any Hello Yellow client workstream, for anyone on the team.

```
$ bin/hy-status REV
Revelion Website – main repo is Hello-yellow-fornya/revelion-site, last updated today (3 Nov 2026), last change: added per-page metadata, canonicals and JSON-LD schema
```

Every line is a fixed template filled from `projects.yaml` and the section's `STATUS.md`. Live GitHub and Drive checks only add ⚠ warnings.

## Use

```bash
bin/hy-status REV                       # one line per section
bin/hy-status --all                     # every section, grouped by client
bin/hy-status REV --detail              # full card: stage, next step, blockers, outputs, activity (last 14 days)
bin/hy-status REV --since monday        # card with activity since Monday
bin/hy-status lint                      # check projects.yaml and every STATUS.md
bin/hy-status lint path/to/STATUS.md    # check one file
```

Or ask Claude: "where is Revelion at?" (skill: `.claude/skills/hy-status`).

## Setup

- Python 3.10+ and PyYAML (`pip install -e .` also gives you a `hy-status` command).
- **GitHub:** `HY_STATUS_GITHUB_TOKEN` (or `GITHUB_TOKEN`), a read-only token for the shared account.
- **Drive:** `HY_STATUS_DRIVE_TOKEN`, or `GOOGLE_APPLICATION_CREDENTIALS` pointing at the shared service account's key (`pip install -e '.[drive]'`). Without credentials, Drive sections show `⚠ Drive not accessible`.
- **Local clones instead of GitHub:** `--local-repos DIR` or `HY_STATUS_LOCAL_REPOS=DIR`, where `DIR/<repo-name>` is a clone. This is useful inside Claude Code sessions.
- `--offline` skips the live checks.

## Adding a section

1. Add it to `projects.yaml`, with exactly one of `main_repo` or `main_folder: {id, path}`.
2. Create its STATUS.md from `templates/STATUS.md`: at the repo root, or at `projects/<section-id>/STATUS.md` here for Drive-only sections.
3. Run `bin/hy-status lint`.

Format and rules: [docs/STATUS-FORMAT.md](docs/STATUS-FORMAT.md). Design: [docs/DESIGN.md](docs/DESIGN.md).

## Tests

```bash
python3 -m unittest discover -s tests
```
