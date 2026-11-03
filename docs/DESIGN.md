# hy-status: design proposal

**Status:** proposal, not built yet. Decisions marked **[DECIDE]** need a call before the build starts.

## 1. What it does

Anyone at Hello Yellow asks "where is MCD at?" and gets back one line per workstream, in the style of the workstream ledger:

```
MCD Paid Social – main repo is hello-yellow-fornya/mcd-paid-social, last updated yesterday (2 Nov 2026), last change: built Q4 creative variants and shared for internal review
MCD Reporting – main folder is Clients/McDonald's/Reporting, last updated 3 weeks ago (13 Oct 2026), last change: delivered September performance report ⚠ no update for 21 days
```

"Tell me more about MCD" (or `--detail`) gives the full card for each workstream: stage, next step, blockers, outputs and recent activity.

The tool only reports what is written down or visible in a source. **Every line is a fixed template filled in by code from STATUS.md and `projects.yaml`. The model never writes or rewords it.** That way anyone can read it without knowing the client.

## 2. Sources

| Source | Role | Why |
|---|---|---|
| **STATUS.md** (one per section) | Primary. Stage, last action, outputs, next step | Written by the person or chat that did the work, so it is the most accurate record |
| **`projects.yaml`** | Section names, main repo or folder, owner | Fixed facts about where each workstream lives |
| **GitHub** | Live check: last commit, open PRs | Raises a warning when STATUS.md is behind the repo |
| **Google Drive** | Live check: most recently modified files in the folder | Raises a warning when STATUS.md is behind the folder |
| **Asana** (optional, v2) | Cross-check "next": open tasks due soonest | Only useful if the team keeps it current **[DECIDE]** |

The live sources never change a line's content. They only add ⚠ warnings to it.

## 3. Data model

### 3.1 Sections

A **section** is one workstream for a client, e.g. MCD Paid Social, MCD Reporting or OCG ONE Prototype. A client can have several sections. Each section has its own STATUS.md and gets its own line.

### 3.2 Registry: `projects.yaml` (in this repo)

```yaml
- client: MCD
  name: McDonald's
  aliases: [mcdonalds, "mcdonald's", maccies]
  sections:
    - id: mcd-paid-social
      label: MCD Paid Social             # printed at the start of the line
      main_repo: hello-yellow-fornya/mcd-paid-social
      status_file: { github: hello-yellow-fornya/mcd-paid-social/STATUS.md }
      drive_folders: [1XyZ...]           # optional, live-check only
      owner: <name>
    - id: mcd-reporting
      label: MCD Reporting
      main_folder:                       # used when there is no main_repo
        path: Clients/McDonald's/Reporting   # printed as-is, so no API call is needed to render
        id: 1AbC...
      status_file: { drive_file_id: 1DeF... }
      owner: <name>
```

Each section has exactly one of `main_repo` or `main_folder`. The linter enforces this.

### 3.3 STATUS.md (one per section)

It lives **next to the work**: at the repo root, or as `STATUS.md` in the section's main Drive folder. Whoever does the work (a person or a chat) updates it in the same place. **[DECIDE: alternatively all STATUS files live centrally in this repo under `projects/<client>/<section-id>/STATUS.md`.]**

```markdown
---
section: mcd-paid-social       # must match the id in projects.yaml
stage: Build                   # one of the fixed stages (§3.4)
updated: 2026-11-02            # date of the last real action, YYYY-MM-DD
last_action: built Q4 creative variants and shared for internal review
next_step: Client review of Q4 creatives, due 2026-11-06 (owner: Sam)
outputs:
  - label: Q4 creative deck
    url: https://docs.google.com/presentation/d/...
blockers: none
---

## Log
<!-- Newest first. One line per real piece of work. Never edit old lines. -->
- 2026-11-02 · Build · built Q4 creative variants and shared for internal review · Deck: <link>
- 2026-10-28 · Build · got audience structure signed off by client
- 2026-10-21 · Discovery · delivered account audit · Audit: <link>
```

**Rules for whoever updates it** (also written into the chat skill and checked by `hy-status lint`):

1. Update only after **real work**: something shipped, sent, decided or signed off.
2. Overwrite the header fields and add **one** new line to the top of the Log.
3. **`last_action` is a short past-tense phrase of about 12 words or fewer**, because it completes the sentence "…last change: ___".
   - Start with a lowercase past-tense verb: *built, delivered, sent, launched, fixed, got … signed off*. Capitalise proper nouns and acronyms only.
   - Leave out the date (it comes from `updated`), the client or section name (already in the line) and the trailing full stop.
   - ✅ `delivered September performance report`
   - ✅ `launched Black Friday campaigns on Meta and TikTok`
   - ❌ `The team has been working on creatives this week.` (not past tense, vague, ends with a full stop)
   - ❌ `MCD: 2 Nov – Built creatives` (repeats the client and the date, starts with a capital)
4. Facts only, with no adjectives. `next_step` names an action, plus a date and owner if they are known.
5. Keep it under about 40 lines. Move old log lines to `STATUS-archive.md`.

The linter warns when `last_action` is over 12 words, ends with a full stop, starts with a capital (except acronyms), or contains a date.

### 3.4 Stages (fixed list) **[DECIDE]**

`Pitch` → `Onboarding` → `Discovery` → `Build` → `Review` → `Live` → `Optimise` → `Reporting` → `Paused` → `Closed`

## 4. How it's triggered

| Ask | CLI | Output |
|---|---|---|
| "where is MCD at?" | `hy-status MCD` | one line per MCD section |
| "where is everything at?" | `hy-status --all` | the ledger: one line per section, all clients |
| "tell me more about MCD" | `hy-status MCD --detail` | full card per section |
| "what's happened on OCG this week?" | `hy-status OCG --detail --since monday` | full card, activity limited to the window |
| "tell me more about MCD reporting" | `hy-status mcd-reporting --detail` | full card, one section |

- **Ask Claude** (claude.ai, Claude Code, Slack): the `hy-status` skill maps the question to a CLI call as in the table, runs it and returns stdout **verbatim**. It doesn't summarise, reword or add anything. The skill also covers writing STATUS.md after real work, following the §3.3 rules.
- **CLI:** Python, using read-only GitHub and Drive credentials.
- **Optional later:** a Monday `--all` post to Slack. **[DECIDE]**

## 5. Output

### 5.1 Default: one line per section

Fixed template, filled in by code:

```
<label> – main repo is <main_repo>, last updated <relative> (<date>), last change: <last_action>[ ⚠ <warning>[; <warning>…]]
<label> – main folder is <main_folder.path>, last updated <relative> (<date>), last change: <last_action>[ ⚠ …]
```

| Slot | Comes from |
|---|---|
| `<label>`, `<main_repo>`, `<main_folder.path>` | `projects.yaml` |
| `<date>` | STATUS.md `updated`, printed as `2 Nov 2026` |
| `<relative>` | `updated` compared with today (Europe/London): `today`, `yesterday`, `N days ago` (2–6), `N weeks ago` (7–27, rounded down, so 7–13 is `1 week ago`), `N months ago` (28+, days ÷ 30 rounded down, minimum 1) |
| `<last_action>` | STATUS.md `last_action`, inserted exactly as written |

Warnings come in a fixed order, joined with `; ` after a single ⚠:

| Warning | When |
|---|---|
| `⚠ no STATUS.md found` | file missing. The line becomes `<label> – main repo is <repo> ⚠ no STATUS.md found` |
| `⚠ STATUS.md unreadable: <field> missing` | header doesn't parse, or a required field is missing |
| `⚠ repo has N commits since STATUS.md (latest <relative>)` | commits on the default branch after `updated` |
| `⚠ Drive folder changed since STATUS.md (latest <relative>)` | files modified after `updated` |
| `⚠ no update for N days` | `updated` is 14 or more days old and no live activity was found. Not shown for `Paused` or `Closed` |
| `⚠ <repo\|Drive> not accessible` | the tool's credentials can't reach the source. The rest of the line still prints |

Examples:

```
MCD Paid Social – main repo is hello-yellow-fornya/mcd-paid-social, last updated yesterday (2 Nov 2026), last change: built Q4 creative variants and shared for internal review
MCD Reporting – main folder is Clients/McDonald's/Reporting, last updated 3 weeks ago (13 Oct 2026), last change: delivered September performance report ⚠ no update for 21 days
OCG ONE Prototype – main repo is hello-yellow-fornya/ocg-one, last updated 4 days ago (30 Oct 2026), last change: added campaign builder screens ⚠ repo has 6 commits since STATUS.md (latest today)
OCG Paid Search – main folder is Clients/ODEON/Paid Search ⚠ no STATUS.md found
```

`--all` prints the same lines grouped by client, sorted by label. An unknown name prints `No project matches "<name>". Closest: …`.

### 5.2 `--detail`: full card per section

```
MCD Paid Social                                             owner: Sam
────────────────────────────────────────────────────────────────────
Stage         Build
Last action   2026-11-02 · built Q4 creative variants and shared for internal review
Next          Client review of Q4 creatives, due 2026-11-06 (owner: Sam)
Blockers      none

Where it lives
  Repo        github.com/hello-yellow-fornya/mcd-paid-social
  Drive       Clients/McDonald's/Paid Social (link)
  Outputs     Q4 creative deck (link)

Activity since Mon 2026-11-02          (default: last 14 days; --since to change)
  2026-11-02  STATUS  built Q4 creative variants and shared for internal review
  2026-11-03  GitHub  3 commits on main, latest "Add video variant specs"
  2026-11-03  Drive   "MCD Q4 Creative v3.pptx" modified

⚠ repo has 3 commits since STATUS.md (latest today)

Sources: STATUS.md @ a1b2c3d · GitHub · Drive · generated 2026-11-03 10:14
```

## 6. Access and permissions

"Anyone can read it, even if it isn't their client" means the tool reads with **one shared, read-only service identity** (a GitHub App or token, and a Google service account added as Viewer on the folders), not each person's own access. **[DECIDE: is team-wide visibility of every client OK? Should some be excluded?]**

## 7. Build plan (after sign-off)

1. Add `projects.yaml` (client → sections), the STATUS.md template and `hy-status lint` (schema checks plus the `last_action` rules).
2. CLI: registry lookup, STATUS.md parsing, the one-line renderer with relative dates. Unit tests pin the exact output strings.
3. GitHub and Drive live checks, which feed the warnings.
4. `--detail` card and `--since`.
5. `hy-status` Claude skill: read (verbatim output) and update (writes STATUS.md).
6. Pilot: backfill STATUS.md for every section of 2–3 clients (e.g. MCD, OCG).
7. Optional: Asana and the weekly Slack ledger.
