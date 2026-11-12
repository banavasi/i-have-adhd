# Init — set up this project

Run once per repo when the user says set up, init, install ferret here, or on
board this project. Creates the gitignored `.ferret/` channel: the durable way
to communicate with ferret in this project.

## 1. Check first (idempotent)

If `.ferret/` already exists: stop. Report the config summary, open inbox count,
and last handoff date. Offer to reseed only when asked — never wipe existing
project memory on a re-run.

## 2. Ask once, then write

Ask up to 4 short questions in one message, with defaults the user can accept
as-is: issue tracker (GitHub, GitLab, local files, other), triage labels,
docs directory, journal location. Obvious answers get filled in, not asked.

Write:

- `.ferret/config.json` — tracker, labels, docs dir, journal path. Other modes
  read this instead of re-asking.
- `.ferret/handoff.md` — seed: `# Handoff`, `Status: no active session`,
  and the resume-point headings the compact protocol fills in.
- `.ferret/learnings.md` — seed header only. Entries append newest-last.
- `.ferret/rules.md` — the project's own rules under three headings:
  `## Communication`, `## Ticket scope`, `## Delivery`. Seed each with one
  default line; the user edits them in words. Loaded at every session start.
- `.ferret/config.json` also takes optional hook settings: `protected` (globs
  that need approval before an edit), `legacy` (globs that get a blast-radius
  reminder on first edit), and `reviewGate` (`nudge` default, `block`, `off`).
- `.ferret/inbox.md` — the human-to-ferret channel. Seed with the format:

```text
# Inbox — ferret reads this at session start
# Add items as: - [ ] <note>
# Ferret moves handled items to inbox.done.md with the date and outcome.
```

## 3. Gitignore it

Append `.ferret/` to the project's `.gitignore` (create the file when missing).
Never duplicate an existing entry. When inside a git checkout, verify with
`git check-ignore .ferret/handoff.md` — silence means it failed, fix it.

## 4. Prove the channel

Read `.ferret/inbox.md` back, then report: what was created, that it is
gitignored, and how to talk to ferret (`- [ ]` items in the inbox get read at
the next session start). Handle any pre-seeded inbox items immediately.
