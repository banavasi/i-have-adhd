// Stop hook: enforces the 40% compact rule. Reads the session transcript,
// measures how full the context is, and at the threshold holds the turn once
// so the model writes the handoff and the journal entry, then tells the user
// to run /compact. A hook cannot run /compact or /clear itself; the user types
// it, and the SessionStart brief restores the handoff afterwards.
// Before holding the turn it writes the raw session record with strip.mjs:
// plain code and regular expressions, no model tokens.
//
// Active when the project has .ferret/ or the user opted in to always-on.
// Settings (in .ferret/config.json, or the FERRET_* environment variables):
//   "compactAt"      percent that triggers the rule (default 40, 0 turns it off)
//   "contextWindow"  model context size in tokens (default 200000)
// Never blocks by failing: any error exits 0 with no output.

import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { alwaysOn, config, emit, ferretDir, readInput, readJson } from "./lib.mjs";
import { stripFile } from "./strip.mjs";

const TAIL_BYTES = 512 * 1024;

/** Tokens in the context at the last main-thread model call, or 0 if unknown. */
export function contextTokens(transcriptPath) {
  let text = "";
  try {
    const size = fs.statSync(transcriptPath).size;
    const start = Math.max(0, size - TAIL_BYTES);
    const buffer = Buffer.alloc(size - start);
    const handle = fs.openSync(transcriptPath, "r");
    try {
      fs.readSync(handle, buffer, 0, buffer.length, start);
    } finally {
      fs.closeSync(handle);
    }
    text = buffer.toString("utf8");
  } catch {
    return 0;
  }

  const lines = text.split("\n");
  for (let i = lines.length - 1; i >= 0; i -= 1) {
    const line = lines[i].trim();
    if (!line.includes('"usage"')) continue;
    try {
      const entry = JSON.parse(line);
      const usage = entry.message && entry.message.usage;
      if (entry.type !== "assistant" || entry.isSidechain || !usage) continue;
      return (
        (usage.input_tokens || 0) +
        (usage.cache_read_input_tokens || 0) +
        (usage.cache_creation_input_tokens || 0)
      );
    } catch {
      // A line cut by the tail window, or not JSON: skip it.
    }
  }
  return 0;
}

const positive = (value, fallback) => {
  const number = Number(value);
  return Number.isFinite(number) && number >= 0 ? number : fallback;
};

try {
  const input = readInput();
  const dir = ferretDir(input);
  if (!dir && !alwaysOn()) process.exit(0);

  const settings = dir ? config(dir) : {};
  const threshold = positive(process.env.FERRET_COMPACT_AT ?? settings.compactAt, 40);
  const window = positive(process.env.FERRET_CONTEXT_WINDOW ?? settings.contextWindow, 200000);
  if (!threshold || !window || !input.transcript_path) process.exit(0);

  const tokens = contextTokens(input.transcript_path);
  if (!tokens) process.exit(0);
  // Floor, so 39.5% is still under a 40% limit.
  const percent = Math.floor((tokens / window) * 100);

  const id = String(input.session_id || "unknown").replace(/[^A-Za-z0-9_-]/g, "_");
  // Without a project channel, state and the raw record live beside the flag.
  const home =
    dir || path.join(process.env.FERRET_CONFIG_DIR || process.env.CLAUDE_CONFIG_DIR || path.join(os.homedir(), ".claude"), ".ferret-state");
  const stateFile = path.join(home, "session", `${id}.context.json`);
  const asked = readJson(stateFile).asked === true;
  const save = (value) => {
    fs.mkdirSync(path.dirname(stateFile), { recursive: true });
    fs.writeFileSync(stateFile, JSON.stringify({ asked: value, percent }));
  };

  if (percent < threshold) {
    // Context shrank (compacted or cleared): arm the rule again.
    if (asked) save(false);
    process.exit(0);
  }
  if (asked || input.stop_hook_active) process.exit(0);

  save(true);
  const handoff = dir ? ".ferret/handoff.md" : "a handoff note in the journal";

  // Save the raw record by program: tool calls and noise are stripped with
  // regular expressions here, so the model spends no tokens cleaning it.
  let raw = "";
  try {
    const rawFile = path.join(home, "raw", `${id}.md`);
    const sizes = stripFile(input.transcript_path, rawFile);
    if (sizes) {
      raw =
        `The raw session record is already saved, stripped by program, at ${rawFile} ` +
        `(${sizes.before} → ${sizes.after} chars). Do not rewrite or clean it, and do ` +
        "not paste tool output into the journal; read that file if you need the detail. ";
    }
  } catch {
    // The record is a convenience. The rule still fires without it.
  }
  emit({
    decision: "block",
    reason:
      `ferret compact rule: context is at ${percent}% (limit ${threshold}%). ` +
      raw +
      "Stop new work and run the compact protocol now (ferret skill, " +
      `sections/save.md §6): 1) write ${handoff} with goal, current state, ` +
      "decisions, open threads, exact next step, files touched; 2) append the " +
      "journal log entry for this session; 3) tell the user in one line to type " +
      "/compact (or /clear to start clean — the handoff is restored at the next " +
      "session start). Do not continue the task after that line.",
  });
} catch {
  process.exit(0);
}
