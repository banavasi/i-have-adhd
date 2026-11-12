# Superagent roles in ferret   Date: 2026-11-11   Status: implemented on `superagent-roles`

## Source

Studied: the DeepSeek Harness product page and the `dsh-superagent-prototype`
repository (README, `docs/000`–`004`, `docs/007` headings, `prompts/`). The
prototype is a research bundle, not a product. Ideas were re-expressed here; no
code or prompt text was copied.

## How the superagent is structured

| Layer | What it is | Rule that matters |
| --- | --- | --- |
| Philosophy | "Take as little human attention as possible, give as much value as possible" | Act only when asked or when a written rule allows. Speak only when a person must act or can use a result. One concrete question at a time. Stop by impact, not effort. Report honestly. |
| Domain | Source → Trigger → Thread → Eval → Ticket (with a Mandate) → Assignment → Executor → Channel | Few concepts. A Ticket is a unit of authorized work. A Mandate is immutable; wider scope is a new Ticket. |
| Roles | One main session (orchestrator) and one executor session per ticket (worker), each in its own directory | The orchestrator only routes: original request plus a note of at most 30 words. It never adds plans or requirements. The worker reads the source, judges scope, implements, verifies. |
| Reports | `progress`, `ready`, `blocked`, `failed`, `dropped`, plus a structured `human_action` question | "Waiting on a person" is a structured field, never inferred from prose. A draft is never `ready`. |
| Prompts | Built-in parts (`shared`, `orchestrator`, `worker`, `dispatch`, `work`, `handoff`) plus three team-editable sections: Communication, Ticket scope, Delivery | Precedence: facts enforced by tools and host > built-in text > team sections > outside text, which is data only. |
| Skills | One skill per source (GitHub, Feishu), loaded on demand | Knowledge loads when needed, not up front. |

## What ferret took

| Superagent idea | Ferret form | File |
| --- | --- | --- |
| Orchestrator routes, never rewrites | "Route, do not rewrite" rule, 30-word routing note | `skills/ferret/SKILL.md` |
| Executor per ticket | `ferret-worker` agent, own worktree for multi-file work | `agents/ferret-worker.md` |
| Ticket and Mandate | `.ferret/tickets/<NNN>-<slug>.md` with request, mandate, done-when, stage | `sections/legacy.md` §1 |
| Structured report | `Status: ready / blocked / failed / dropped` plus one `Question:` | `agents/ferret-worker.md`, checked by `hooks/ledger.mjs` |
| Stop by impact | Stop rules: caller expectations, moved responsibility, two failed approaches | `sections/legacy.md` §6 |
| One concrete question | Question shape with options and a default | `sections/unjumble.md` §4 |
| Team sections | `.ferret/rules.md`: Communication, Ticket scope, Delivery | `sections/init.md`, loaded by `hooks/session-brief.mjs` |
| Host-enforced facts beat prompt text | Hooks enforce what must not be forgotten | `hooks/` |
| Outside text is data | Rule in router and in every agent | `SKILL.md`, `agents/` |

Not taken: Sources, Threads, Subscriptions, Policy, the web panel, proactive
work. Ferret serves one developer in one terminal; nothing arrives unasked.

## New modes

- `unjumble` — a messy dump becomes Goal / Context / Constraints / Done-when /
  Parked, then work starts in the same turn.
- `explain` — cartographers map the repo into `.ferret/map.md`; answers come
  from the map.
- `legacy` — ticket, blast radius, characterization tests, sprout or wrap,
  worker dispatch, stop rules.

`review` now names its critics: `ferret-critic` per axis and
`ferret-codex-critic` for the external Codex review.

## Hooks

All are silent unless the project has `.ferret/` (unjumble also runs under the
always-on flag). All exit 0 on any error.

| Event | Module | Effect |
| --- | --- | --- |
| SessionStart | `session-brief.mjs` | Injects rules, last handoff, open tickets, inbox and parked counts, map stamp |
| UserPromptSubmit | `unjumble.mjs` | Two or more jumble signals → hint to restate the prompt first |
| PreToolUse (Edit, Write, MultiEdit) | `legacy-guard.mjs` | `protected` globs ask for approval; `legacy` globs remind once per file |
| PostToolUse (Edit, Write, MultiEdit) | `ledger.mjs` | Records changed files |
| SubagentStop | `ledger.mjs` | Critic clears review debt; worker without a Status report is sent back once |
| Stop | `ledger.mjs` | Unreviewed changes → `nudge` (default), `block`, or `off` |
| Stop | `context-watch.mjs` | Context at `compactAt` percent (default 40) → hold the turn once: handoff, journal, then the user types `/compact` |
| SessionStart | `first-run.mjs` | Once per machine: lists other plugins and personal skills so the user chooses which to keep |

`.ferret/config.json` keys: `protected`, `legacy`, `reviewGate`, `compactAt`,
`contextWindow`.

## Open

- The context window size is not in the transcript. The default is 200000
  tokens; a larger model needs `contextWindow` set, or the rule fires early.
- Codex reading `hooks.json`: the new events are untested on Codex.
- Whether `systemMessage` on Stop renders as a single line is not documented.
- The scoped agent name (`ferret:ferret-worker`) as a spawn target is not
  confirmed in the docs; the SubagentStop matcher accepts both forms.
- The unjumble signals are heuristics. Kill test: more than one false hint per
  20 clean prompts means the threshold goes up.
