# Meta — improve the harness, extend the reach

Run when a flow repeats, when the task needs a domain the harness lacks, when
the first-run hook asks to declutter skills, or when
asked to improve the harness itself. The harness compounds or it rots.

## 1. Skillify (promote repeated flows)

When the same flow runs for the third time, offer to promote it into the harness:

1. Name the trigger (what prompt shape fires it) and the done-test.
2. Write the steps at section density: under 120 lines, no story, rules not prose.
3. Wire the router row in `SKILL.md` and the section file in `sections/`.
4. Rehearse it once on a real task before it counts as part of the harness.

A promoted flow that nobody fires within a month gets cut. The harness stays
proportional to the work actually done.

## 2. Extend (borrow, do not improvise)

When the task needs a domain the harness lacks (a framework, a platform, a
specialty), look outward before improvising:

1. Search the skills ecosystem (`npx skills find <keywords>`, plus the leaderboard
   at skills.sh for well-known domains).
2. Verify before recommending: prefer 1K+ installs; trusted sources
   (vendor-official, major-maintainer) over unknown authors; check repo stars —
   under ~100 stars is treated with skepticism.
3. Present: name, what it does, installs + source, install command, link.
4. Offer to install. Never auto-install; the user approves every addition.

If nothing vetted exists, say so and work from primary sources
(`sections/browse.md` §2) instead of pretending a skill covered it.

## 3. Declutter (once, at install)

The first session after install, a hook lists the other enabled plugins and
personal skills. Overlapping skills fight the router, so ask once:

1. Show the list, grouped: plugins, personal skills. Mark each one that
   overlaps a ferret mode with the mode name.
2. Ask one multi-select question: which to KEEP. Default: keep all. Never
   pre-select a removal.
3. For each one the user drops, disable it reversibly: a plugin with
   `claude plugin disable <id>`; a personal skill by moving its folder to
   `skills.disabled/` beside `skills/`. Never uninstall, never delete.
   Skills managed by an organization are left alone.
4. Report what was disabled and the one command that undoes each.

The question is asked once. "declutter skills" runs it again on request.

## 4. Evolve (change the harness safely)

Harness edits follow the same discipline as product edits: router changes get the
day-rehearsal (one prompt per phase, correct mode each time); new sections get a
real-task rehearsal; strip and critic checks re-run after any save/review change.
A harness change without its rehearsal is not done.
