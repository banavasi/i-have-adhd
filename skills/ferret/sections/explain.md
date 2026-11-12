# Explain — map the project, then answer from the map

Run for explain-this-project, how does this repo work, where is X, onboard me,
what does this module do. Target: a first answer in 5 lines, backed by a map
that the next session reuses instead of re-reading the code.

## 1. Read the map first

`.ferret/map.md` is the project map. If it exists, answer from it and cite it.
It is stale when its `Commit:` line is more than 50 commits behind `HEAD`
(`git rev-list --count <commit>..HEAD`) or the question lands in an area it
marks unknown. Stale or missing → §2, scoped to what the question needs. Never
remap the whole repo to answer a question about one module.

## 2. Fan out cartographers

Spawn `ferret-cartographer` workers in parallel, one axis each, fresh context,
read-only. Each returns under 300 words with `file:line` evidence:

- **Entry points:** how the program starts, what it listens to, how to run it.
- **Data:** stores, schemas, the three most important types, who writes them.
- **Boundaries:** modules, who imports whom, the public surface of each.
- **Checks:** build, tests, CI, deploy. Which commands actually pass today.
- **Hot spots:** churn (`git log --since=1.year --name-only --format=`, counted)
  crossed with test presence. High churn and no tests is a danger zone.

For a scoped question, send one cartographer with the question itself.
The main thread does not re-read what a cartographer covered.

Small repo exception: under 20 tracked source files, map it on the main thread.
Fan-out there costs more than it saves. The map (§3) is still written.

## 3. Write the map

`.ferret/map.md`, under 120 lines, facts with `file:line`, no adjectives:

```text
# Map   Commit: <sha>   Date: <YYYY-MM-DD>
## What it is      two sentences
## Run it          exact commands that worked
## Layout          table: path | owns | talks to
## One real flow   one request traced end to end, each hop with file:line
## Data            stores and the types that matter
## Seams           places where new behavior can be added without editing old code
## Danger zones    high churn, no tests, hidden coupling
## Unknown         what nobody could confirm, and what would confirm it
```

A claim nobody verified goes under Unknown. A guess written as a fact poisons
every later session.

## 4. Answer at the altitude asked

1. Five lines first: what it is, how it runs, where the asked-about thing lives.
2. Trace one real flow instead of listing folders. Folders are not an explanation.
3. Offer at most five named places to go deeper. The user picks one.
4. Define each project term once, in the user's words where they gave any.
5. When the user must own the code afterwards, end with a teach-back prompt
   (`sections/save.md` §5): they explain one hop back in their own words.

## 5. Keep it true

After a change lands in a mapped area, update the affected map lines in the same
session. A wrong map entry found during other work is fixed on the spot and
logged as a `pitfall` learning.
