# Unjumble — turn a messy dump into a clean prompt

Run for brain dumps, voice-to-text, typo-heavy or run-on prompts, several asks
in one breath, and "clean this up into a prompt". Also fires when the prompt
hook flags the message as jumbled. The user never retypes anything.

## 1. Extract, do not invent

Read the dump once and sort every fragment into one slot:

- **Goal:** the one outcome wanted most. One sentence.
- **Context:** links, files, names, and prior work the user mentioned.
- **Constraints:** tools, limits, and preferences the user stated.
- **Done-when:** the observable result, if the user gave one.
- **Parked:** every other ask and tangent, each one line.

Cleaning is not rewriting. Do not add requirements, plans, or acceptance
criteria the user did not state. An empty slot stays empty.

## 2. Repair rules

- Fix a typo silently only when one reading is possible.
- Two readings possible → keep the user's token and list it: `Unsure: "<token>"
  → <reading A> or <reading B>`.
- Keep the user's own words for domain terms, product names, and anything quoted.
- Order several asks by dependency, then by the order the user gave them.

## 3. Show it, then go

The clean prompt is the first thing you write, before any tool call, so the
user can correct it while you work. One fenced block, eight lines or fewer:

```text
Goal: <one sentence>
Context: <links, files, names>
Constraints: <stated limits>
Done-when: <observable result>
Parked: <n> items → .ferret/parked.md
```

Then start work on the Goal in the same turn, in its own mode. Do not wait for
approval of the cleanup: the user corrects it in one line if it is wrong. Append
parked items to `.ferret/parked.md` so nothing is lost, and offer the first one
when the Goal is done.

## 4. One specific question

Ask only when a wrong guess would waste more than ten minutes of work or touch
something hard to undo. Then ask exactly one question, shaped like this:

```text
Question: <one decision, answerable in five words or fewer>
Options: A) <default> · B) <alternative>
If you say nothing: A.
Unblocks: <what proceeds once answered>
```

Never stack questions. Never ask what the repo, the map, or the ticket already
answers. Work that does not depend on the answer continues meanwhile.

## 5. Keep the good ones

On "save this prompt", write it to `.ferret/prompts/<slug>.md` with a one-line
note on when to use it. The third reuse of a saved prompt is a promotion
candidate (`sections/meta.md` §1).
