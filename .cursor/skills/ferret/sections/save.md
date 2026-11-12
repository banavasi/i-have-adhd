# Save — journal, learnings, retro, handoff

Run for log-this, journal, learned, standup notes, retro, handoff, wrap-up, EOD.
This is the "save everything" phase: decisions, insights, and thread state are
captured or they evaporate. Append-only — never overwrite a journal file.

## 1. Journal

Location: `~/dev-journal/` (create on first use), or `$DEV_JOURNAL` when set:

```
daily/2026-10-17.md        one file per day
decisions/0001-<slug>.md   one file per decision
ideas.md                   append-only
learned.md                 append-only
```

- **log** (default): gather from git + session work; ask at most 2 short questions
  for the rest. Append `## HH:MM — <repo> — <title>` with Did / How / AI-did-vs-I-did
  (honest split) / Stuck-on / Next. Push back on vague How; if the AI wrote it and
  the user cannot say how it works, write that plainly and suggest a teach-back (§5).
- **decision**: next-numbered file with Context / Options (at least 2 real ones, each
  with its main cost) / Decision / Why / Consequences / Revisit-when (concrete trigger).
  One option is not a decision — push back hard. "AI suggested it" is a valid Why;
  dressing it up is not.
- **idea**: date, one line, problem it solves, cheapest test. No problem → say so.
- **learned**: date, concept, 2–3 line explanation, link to where it showed up in code.
- **standup**: last working day + today → Yesterday / Today / Blockers, max 3 each.
- **week**: last 7 daily files → shipped, decisions, learnings, recurring blockers,
  ending with one blunt pattern observation.

## 2. Raw

The raw record is written by a program, never by the model. `hooks/strip.mjs`
reads the session transcript and writes `.ferret/raw/<session>.md` with plain
code and regular expressions: no tokens spent. It runs by itself at the compact
limit and before every compaction. By hand:
`node <ferret>/hooks/strip.mjs <transcript.jsonl> <out.md>`.

Never re-clean, summarize, or retype the raw file. Raw preserves; the journal
distills from it. One raw file per session.

## 3. Strip pass (journal AND raw)

For raw, the program applies this pass. For the journal, you apply it:

- REMOVE: tool calls and their results, reasoning dumps, subagent threads,
  injected reminders and hook text, agent narration ("I'll now...", "Let me
  check..."), duplicate restatements of one fact.
- KEEP, as plain text: what the user asked, what was answered, commands run,
  file paths with line numbers, decisions with reasons, errors with causes,
  open items, next steps.
- Verify by reading the output once: if a stranger cannot tell which harness wrote
  it, the strip passed. A journal that leaks tool calls is a broken journal.

## 4. Learnings

Project memory that compounds across sessions, stored per repo
(`.ferret/learnings.md`, newest last, one line each):

```
- [<type>] <kebab-key>: <one-sentence insight> (confidence: <1-10>, <files>)
```

Types: pitfall, pattern, preference, fact. Log after bugfixes, surprises, and
user corrections. Search before advising — a stored finding beats fresh guessing.
Prune on request: STALE (paths gone) or CONFLICT (same key, opposing insights)
entries go to the user as remove / keep / update. Never silently drop.

## 5. Retro, handoff, teach-back

- **retro**: after a session, suggest environment improvements (navigation, checks,
  standards, tooling), most severe first, each with evidence and a concrete fix.
- **handoff**: when context compacts or another agent continues, write the compact
  doc: goal, current state, decisions taken, open threads, exact next step.
- **teach-back**: when understanding is fuzzy ("AI did / I did" says the user is
  unsure), have the user explain the mechanism back in their own words before the
  session's learning counts as learned.

## 6. Compact protocol (40% rule)

Trigger at 40% context used or more, or when usage is unknown and the session
runs long. No exceptions. Every harness (Claude, Codex, Grok, others). Every OS.

1. Stop new work. Mid-step is fine; note the exact resume point first.
2. Write `.ferret/handoff.md`: goal, current state, decisions taken, open
   threads, exact next step, files touched with line numbers.
3. Append the journal log entry for this session.
4. Compact now: `/compact` on Claude; the harness compact action elsewhere.
5. After compaction, read `.ferret/handoff.md` first, restate state, then continue.

The Stop hook measures context from the transcript and holds the turn once at
the limit (`compactAt` in `.ferret/config.json`, default 40; `contextWindow`
sets the model's size in tokens, default 200000). No hook can run `/compact`
or `/clear`: after steps 1–3, tell the user in one line to type it, then stop.
The PreCompact hook auto-saves git state alongside. It never replaces the handoff.
