# STATUS.md format and rules

Every section (workstream) in `projects.yaml` has one STATUS.md:

- **Section with a repo:** `STATUS.md` at the root of its `main_repo`, on the default branch.
- **Drive-only section:** `projects/<section-id>/STATUS.md` in this repo.

hy-status builds each status line from it with a fixed template:

```
<label> – main repo is <repo>, last updated <relative> (<2 Nov 2026>), last change: <last_action>[ ⚠ warnings]
```

So `last_action` has to read naturally after "last change:".

## Template

Copy `templates/STATUS.md`:

```markdown
---
section: revelion-website      # must match the section id in projects.yaml
stage: Build                   # Pitch | Onboarding | Discovery | Build | Review | Live | Optimise | Reporting
status: active                 # active | paused | closed
updated: 2026-11-03            # date of the last real action, YYYY-MM-DD
last_action: added per-page metadata, canonicals and JSON-LD schema
next_step: Build the real pages, starting with the homepage
outputs:
  - label: Build spec
    url: https://...
blockers: none
---

## Log
<!-- Newest first. One line per real piece of work. Never edit old lines. -->
- 2026-11-03 · Build · added per-page metadata, canonicals and JSON-LD schema · PR #7
```

Required fields: `section`, `stage`, `status`, `updated`, `last_action`, `next_step`.

## Rules

1. **Update only after real work**: something was shipped, sent, decided or signed off. Not for "looked at it".
2. **Overwrite the header fields and add one line to the top of the Log.** Never edit old log lines.
3. **`last_action` is a short past-tense phrase, about 12 words or fewer.**
   - Start with a lowercase past-tense verb: *built, delivered, sent, launched, fixed, added*. Capitalise only proper nouns and acronyms (starting with `GA4` is fine).
   - No date (it comes from `updated`), no client or section name (already in the line), no full stop at the end.
   - ✅ `delivered September performance report`
   - ✅ `launched Black Friday campaigns on Meta and TikTok`
   - ❌ `The team has been working on creatives this week.`
   - ❌ `Revelion: 2 Nov – Built creatives`
4. **Facts only, no adjectives.** `next_step` names an action, plus a date and owner if they are known.
5. **`stage` is where the work is in its lifecycle. `status` says whether it's moving.** Set `status: paused` or `closed` instead of inventing a stage. Paused and closed sections never show `⚠ stale`.
6. Keep the file under about 40 lines. Move older log lines to `STATUS-archive.md`.

Check a file before committing:

```bash
bin/hy-status lint path/to/STATUS.md
```

## Warnings the line can carry

| Warning | Meaning |
|---|---|
| `⚠ no STATUS.md found` | The file isn't where projects.yaml says it should be |
| `⚠ STATUS.md unreadable: <reason>` | The header doesn't parse, or a required field is missing |
| `⚠ repo has N commits since STATUS.md (latest …)` | Work was committed after STATUS.md last changed (merge commits aren't counted) |
| `⚠ Drive folder changed since STATUS.md (latest …)` | Files in the section's Drive folder changed after STATUS.md |
| `⚠ stale` | `updated` is 14 or more days old, there is no newer repo or Drive activity, and the status is `active` |
| `⚠ repo not accessible` / `⚠ Drive not accessible` | The tool's read-only account can't reach the source |
