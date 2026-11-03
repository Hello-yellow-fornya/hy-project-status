---
name: hy-status
description: Factual status of a Hello Yellow client workstream, and updating its STATUS.md after real work. Use for "where is <client> at?", "what's happened on <client> this week?", "tell me more about <client>", "status of everything", or after finishing a real piece of work on a client section.
---

# hy-status

## Reading status

1. Run `git -C <this repo> pull --ff-only` (quietly) so `projects.yaml` is current.
2. Turn the question into **one** command. Pass only the client or section name, not the whole sentence:

| Question | Command |
|---|---|
| "where is REV at?" / "status of Revelion" | `bin/hy-status REV` |
| "where is everything at?" | `bin/hy-status --all` |
| "tell me more about Revelion" | `bin/hy-status REV --detail` |
| "what's happened on Revelion this week?" | `bin/hy-status REV --since monday` |
| "what's happened since the 20th?" | `bin/hy-status REV --since 2026-10-20` |
| "tell me more about the Revelion website" | `bin/hy-status revelion-website --detail` |

3. **Return the command's output exactly as printed, inside a code block.** Don't summarise, reword, reorder, translate, add context or leave out warnings. If you add anything at all, keep it to one line after the code block, and only if the output asks for it (for example, it lists the closest matches for an unknown name).
4. If it prints `No project matches …`, show that output. Don't guess the project, and don't look for status anywhere else. Only sections in projects.yaml are reported.

## Updating STATUS.md after real work

Do this only after real work: something shipped, sent, decided or signed off. Follow `docs/STATUS-FORMAT.md` exactly:

- Overwrite `stage`, `status`, `updated` (today, YYYY-MM-DD), `last_action`, `next_step`, `outputs` and `blockers`.
- `last_action` is a lowercase past-tense phrase of about 12 words or fewer, with no date, no client or section name and no full stop. Example: `delivered September performance report`.
- Add one line to the top of `## Log`: `- YYYY-MM-DD · <stage> · <what was done> · <link>`. Never edit older lines.
- Run `bin/hy-status lint <path to STATUS.md>` and fix anything it reports before committing.
- STATUS.md lives at the repo root for sections with a repo, and at `projects/<section-id>/STATUS.md` in this repo for Drive-only sections.
