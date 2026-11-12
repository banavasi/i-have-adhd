# Review — external critics, verbatim aggregation

Run for review-this, PR review, diff review. The main thread never reviews its own
work from memory: every review fans out to critic agents in **fresh contexts**,
then aggregates their reports verbatim. Cost, budget, diff size, and time are
never reasons to review on the main thread instead: if critics cannot run, say
so and stop. Critics spawn automatically; the user never
asks for them.

## 1. Pin the fixed point

Whatever the user named (commit, branch, tag, `HEAD~5`) is the fixed point.
Capture once: `git diff <fixed-point>...HEAD` (three-dot, against the merge-base)
plus `git log <fixed-point>..HEAD --oneline`. Confirm the ref resolves and the diff
is non-empty here — a bad ref fails now, not inside the critics. If no point was
named, ask for it.

## 2. Find the spec and the standards

- **Spec source,** in order: issue refs in commit messages, a user-supplied path, a
  spec file under `docs/`, `specs/`, or `.scratch/` matching the branch. Nothing
  found → ask once; if there is no spec, the spec critic is skipped and the report
  says so.
- **Standards sources:** every repo file documenting how code should be written
  (`CODING_STANDARDS.md`, `CONTRIBUTING.md` when present). On top sits the smell
  baseline below. Repo rules override the baseline; baseline smells are always
  judgement calls, never hard violations; skip anything tooling already enforces.

Smell baseline (name → fix): Mysterious Name → rename, or the design is murky.
Duplicated Code → extract the shared shape. Feature Envy → move the method to the
data. Data Clumps → bundle into one type. Primitive Obsession → give the concept a
type. Repeated Switches → polymorphism or one shared map. Shotgun Surgery → gather
what changes together. Divergent Change → split by reason to change. Speculative
Generality → delete until a real need shows. Message Chains → hide the walk.
Middle Man → cut the delegator. Refused Bequest → composition over inheritance.

## 3. Spawn the critics in parallel

All critics start with fresh context and receive only their brief:

- **Standards critic:** diff command + commit list + standards files + the baseline
  pasted in full. Brief: per file/hunk, violations of documented standards (cite
  file + rule) and baseline smells (name + quoted hunk). Under 400 words.
- **Spec critic:** diff + commits + spec contents. Brief: missing or partial
  requirements, unasked-for behavior (scope creep), implementations that look wrong.
  Quote the spec line per finding. Under 400 words.
- **Blind critic:** the diff only — no branch name, no author, no chat context.
  Brief: what looks wrong, risky, or confusing to a stranger. Under 300 words.
- **Second-model critic:** when `codex --version` succeeds, spawn
  `ferret-codex-critic` with the fixed point (`--base <ref>`, `--commit <sha>`,
  or `--uncommitted`). It saves the report under `.ferret/reviews/` and relays
  it verbatim. Another model CLI works the same way with the standards brief.
  No second CLI → same-model fresh contexts, and the report says so.

The standards, spec, and blind critics run as `ferret-critic`, one per axis.
The second-model critic sends the diff to its provider: skip it when
`.ferret/rules.md` forbids external review, and say it was skipped.

## 4. Aggregate

Present each report under its own heading, verbatim or lightly cleaned. Do not
merge, rerank, or pick a winner across critics — the separation is the point.
End with one line per critic: finding count and its worst issue. When critics
disagree, show both positions with evidence. The user decides.
