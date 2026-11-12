# Legacy — add a feature to code you did not write

Run for legacy, old code, no tests, afraid to touch this, add a feature to an
existing module, change behavior nobody fully understands. The old behavior is
the spec until proven otherwise. Stop by impact, not by effort.

## 1. Open a ticket

Always, and before the first edit, even for a one-line change: the ticket is
the record of what was allowed. Write it with the Write tool, then continue.
One ticket per unit of authorized work, in `.ferret/tickets/<NNN>-<slug>.md`:

```text
# T-<NNN> <title>
Stage: open            open | working | ready | blocked | ended
Request: <the user's words, verbatim>
Mandate: in <paths or modules> · out <what stays untouched>
Done-when: <one observable result>
## Reports             append-only, newest last
```

The mandate is fixed once the user confirms it in one line. Wider scope is a
new ticket, never a quiet edit to this one.

## 2. Measure the blast radius

Before any edit, from `.ferret/map.md` (`sections/explain.md` when missing):

1. Grep every caller of each symbol the change touches. Count them.
2. List the public interfaces involved: exports, routes, schemas, CLI flags.
3. Check which of those callers have tests, and whether those tests pass now.

Show at most five rows: `symbol | callers | tested | risk`. A failing baseline
is reported before work starts, so it is never blamed on the change.

## 3. Pin current behavior

Write characterization tests at the seam: they record what the code does today,
bugs included, with values captured from a real run. No test harness in the
repo → the smallest executable probe (script, snapshot, recorded request), and
the report says so. A surprising current behavior is a question for the user,
not something to fix in passing.

## 4. Add beside, not inside

Reuse ladder first (router rules). Then, in order of preference:

1. **Sprout:** new function or class, called from one new line in old code.
2. **Wrap:** new code around the old call, old code untouched.
3. **Edit in place:** only when 1 and 2 cannot express the change. Say why.

New code follows `sections/build.md` §2 (red, green, next slice).

## 5. Dispatch

A change inside one file stays on the main thread. Anything larger goes to a
`ferret-worker` in its own worktree. `.ferret/` is gitignored, so a worktree
does not contain it: give the worker the absolute path of the ticket in the
main checkout. It reads the ticket, map, and rules there and appends its report
there. The brief is that path plus a routing
note of at most 30 words: constraints the user stated, nothing else. No plan, no
acceptance checklist, no invented requirements. The worker reads the ticket and
the original request, decides the approach, and reports.

## 6. Stop rules

Keep going through: many files, failing tests, layout defects, routine choices.

Stop with one concrete question (`sections/unjumble.md` §4) when the change
would break what existing callers expect, move a responsibility between
modules, need a coordinated redesign of independent modules, or when two
feasible approaches have failed. Name the interface and the callers affected.
Keep partial work as a clearly marked draft. Never widen the mandate to get
unstuck.

A "wait" or "stop" from the user holds across follow-ups, workers, and
compaction until the user lifts it. New clues do not lift it.

## 7. Ready means proven

A ticket is `ready` only when the §3 tests pass before and after, the new
behavior has its own test, and the critics have run (`sections/review.md`).
A draft is reported as a draft. Then update the map lines the change touched.
