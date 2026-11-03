# hy-status: design proposal

**Status:** proposal, not built yet. Decisions marked **[DECIDE]** need a call before the build starts.

## 1. What it does

Anyone at Hello Yellow asks "where is MCD at?" or "what's happened on OCG this week?" and gets the same factual card back:

- current stage
- where the work lives (repo, Drive folder, links)
- last activity and its date
- what's next

It only reports what is written down or visible in a source. No interpretation, no opinions. Every line says where it came from, so anyone can read it without knowing the client.

## 2. Sources

| Source | Role | Why |
|---|---|---|
| **STATUS.md** (per project) | Primary. Stage, last action, outputs, next step | Written by the person or chat that did the work, so it is the most accurate record |
| **GitHub** | Live check: last commit, open PRs | Shows real activity even when STATUS.md hasn't been updated |
| **Google Drive** | Live check: most recently modified files in the project folder | Most deliverables (decks, sheets) live here, not in repos |
| **Asana** (optional, v2) | Cross-check "next": open tasks due soonest | Only useful if projects are kept up to date in Asana **[DECIDE]** |

**Recommendation:** v1 uses STATUS.md plus GitHub plus Drive. Add Asana in v2 only if the team keeps it current. A tool that reports stale Asana tasks as fact is worse than no tool.

The live sources are there to **check** STATUS.md, not replace it. If a repo or folder shows activity newer than STATUS.md's last entry, the card says so (see §5).

## 3. Data model

### 3.1 Project registry: `projects.yaml` (in this repo)

One entry per client project. This is how "MCD", "McDonald's" and "maccies" all resolve to the same project.

```yaml
- code: MCD
  name: McDonald's – Paid Social always-on
  aliases: [mcdonalds, "mcdonald's", maccies]
  status_file:                     # where STATUS.md lives: exactly one of
    github: hello-yellow-fornya/mcd-paid-social/STATUS.md
    # drive_file_id: 1AbC...       # for projects with no repo
  repos: [hello-yellow-fornya/mcd-paid-social]
  drive_folders: [1XyZ...]         # Drive folder IDs
  asana_project: null              # optional, v2
  owner: <name>                    # who to ask; shown on the card
```

### 3.2 STATUS.md (per project)

It lives **next to the work**: at the repo root, or as `STATUS.md` in the project's Drive folder when there is no repo. Whoever does the work (a person or a chat) updates it in the same place. **[DECIDE: alternatively all STATUS files live centrally in this repo under `projects/<CODE>/STATUS.md`. That is simpler to find, but a chat working in the project repo then has to write to a second repo.]**

Format: a small YAML header that the tool reads, then a short log that people read.

```markdown
---
project: MCD
stage: Build                 # one of the fixed stages (§3.3)
updated: 2026-11-02          # date of the last real action, YYYY-MM-DD
last_action: Built Q4 creative variants (6 static, 2 video) and shared for internal review
next_step: Client review of Q4 creatives, due 2026-11-06 (owner: Sam)
outputs:
  - label: Q4 creative deck
    url: https://docs.google.com/presentation/d/...
  - label: Campaign build repo
    url: https://github.com/hello-yellow-fornya/mcd-paid-social
blockers: none               # optional; "none" or a short factual line
---

## Log
<!-- Newest first. One line per real piece of work. Never edit old lines. -->
- 2026-11-02 · Build · Built Q4 creative variants, shared for internal review · Deck: <link>
- 2026-10-28 · Build · Audience structure signed off by client on call
- 2026-10-21 · Discovery · Account audit delivered · Audit: <link>
```

Rules for whoever updates it (written into the chat skill as well):
1. Update only after **real work**: something shipped, sent, decided or signed off. Not for "looked at it".
2. Overwrite the header fields. Add **one** new line to the top of the Log.
3. Facts only: what was done, by when, where it is. No adjectives, no "going well".
4. `next_step` names an action, plus a date and owner if they are known.
5. Header plus Log stays under about 40 lines. Move old log lines to `STATUS-archive.md` if needed.

The Log is what answers "what happened this week?". The tool filters it by date, and git history (or Drive revision history) backs it up.

### 3.3 Stages (fixed list, so cards can be compared across clients) **[DECIDE]**

`Pitch` → `Onboarding` → `Discovery` → `Build` → `Review` → `Live` → `Optimise` → `Reporting` → `Paused` → `Closed`

## 4. How it's triggered

There are three entry points. Two of them call the same CLI, so the facts are produced the same way every time.

1. **Ask Claude** (claude.ai, Claude Code, Slack via Claude): a `hy-status` skill. Claude's only jobs are to (a) pick the project out of the question, (b) pick the time window ("this week" means Monday to today) and (c) run the CLI and return its output **verbatim**. Claude doesn't summarise or reword it, so it can't add anything that isn't in the sources.
2. **CLI:** `hy-status MCD`, `hy-status OCG --since monday`, `hy-status --all`. Python, with read-only GitHub and Drive credentials.
3. **Optional later:** a scheduled Monday-morning `--all` digest posted to a Slack channel. **[DECIDE]**

The same skill also covers the **write** side. When a chat finishes real work, it updates STATUS.md in the format above, so updates come out consistent.

## 5. Output format

Fixed template, plain text and markdown, the same for every project:

```
MCD · McDonald's – Paid Social always-on                     owner: Sam
────────────────────────────────────────────────────────────────────
Stage         Build
Last action   2026-11-02 · Built Q4 creative variants (6 static, 2 video),
              shared for internal review
Next          Client review of Q4 creatives, due 2026-11-06 (Sam)
Blockers      none

Where it lives
  Repo        github.com/hello-yellow-fornya/mcd-paid-social
  Drive       MCD / 2026 Q4  (drive link)
  Outputs     Q4 creative deck (link)

Activity since Mon 2026-11-02
  2026-11-02  STATUS  Built Q4 creative variants, shared for internal review
  2026-11-03  GitHub  3 commits on main, latest "Add video variant specs"
  2026-11-03  Drive   "MCD Q4 Creative v3.pptx" modified

⚠ Repo/Drive show activity after STATUS.md was last updated (2026-11-02).
  STATUS.md may be behind. Ask the owner.

Sources: STATUS.md @ a1b2c3d · GitHub · Drive · generated 2026-11-03 10:14
```

Edge cases, always stated and never guessed:
- No STATUS.md: "No STATUS.md for this project", followed by live activity only.
- STATUS.md older than 14 days with no live activity: "No recorded activity since <date>".
- Unknown project: list the closest registry matches.
- Source unreachable (permissions): "Drive: not accessible with the tool's credentials", and the rest of the card is still shown.

## 6. Access and permissions

"Anyone can read it, even if it isn't their client" means the tool reads with **one shared, read-only service identity** (a GitHub App or token with read access to project repos, and a Google service account added as Viewer on project folders), not each person's own access. **[DECIDE: is team-wide visibility of every client's status OK? Should some clients be excluded?]**

## 7. Build plan (after sign-off)

1. Add `projects.yaml`, the STATUS.md template and a validator (`hy-status lint`).
2. CLI: registry lookup, STATUS.md parsing, the card renderer (STATUS-only first).
3. GitHub and Drive live checks, plus the staleness warning.
4. `hy-status` Claude skill (read and update).
5. Backfill STATUS.md for 2–3 live projects (e.g. MCD, OCG) as a pilot.
6. Optional: Asana and the weekly Slack digest.
