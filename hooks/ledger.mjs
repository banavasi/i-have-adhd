// Session ledger hook. One module, four events, one append-only log
// (.ferret/session/<session id>.log, see lib.mjs):
//   PostToolUse   (Edit, Write, MultiEdit): records the file as edited.
//   SubagentStart a ferret critic begins: records where in the log it started.
//   SubagentStop  a ferret critic that returned a verdict clears the review
//                 debt for the files it covered; a ferret worker must end with
//                 its Status report or is sent back once.
//   Stop          edited files with no review → remind once ("nudge", the
//                 default), hold the turn once ("block"), or stay quiet ("off"),
//                 per "reviewGate" in .ferret/config.json.
// Silent when the project has no .ferret/. Never blocks by failing.

import { execFileSync } from "node:child_process";
import {
  appendEvent,
  config,
  emit,
  ferretDir,
  projectDir,
  readEvents,
  readInput,
  relativePath,
  replay,
} from "./lib.mjs";

const REPORT_STATUS = /^\s*Status:\s*(ready|blocked|failed|dropped)\b/im;
const VERDICT = /^\s*Verdict:\s*(approve|changes-needed)\b/im;
const TARGET = /^\s*Target:\s*(.+)$/im;

/**
 * Which edited files a finished review covered, from the critic's `Target:`
 * line. null means all of them.
 *   uncommitted / working tree → every edited file
 *   one commit                 → none (it reviewed history, not this session)
 *   a base ref or range        → only files with no uncommitted changes left,
 *                                because the range stops at the last commit
 *   no Target line             → every edited file (older critic reports)
 */
function coveredFiles(message, input, changed) {
  const target = ((message.match(TARGET) || [])[1] || "").trim().toLowerCase();
  if (!target || /uncommitted|working tree|worktree/.test(target)) return null;
  if (/^(commit\b|--commit\b|[0-9a-f]{7,40}$)/.test(target)) return [];
  try {
    const dirty = execFileSync("git", ["status", "--porcelain", "--untracked-files=all"], {
      cwd: projectDir(input),
      encoding: "utf8",
      timeout: 5000,
      stdio: ["ignore", "pipe", "ignore"],
    })
      .split("\n")
      .filter(Boolean)
      .map((line) => line.slice(3).split(" -> ").pop().replace(/^"|"$/g, ""));
    return changed.filter((file) => !dirty.includes(file));
  } catch {
    return []; // Cannot tell what was committed: clear nothing.
  }
}

try {
  const input = readInput();
  const dir = ferretDir(input);
  if (!dir) process.exit(0);

  const event = input.hook_event_name;
  const agent = String(input.agent_type || "");
  const isCritic = /ferret-(codex-)?critic$/.test(agent);

  if (event === "PostToolUse") {
    const rel = relativePath(input, input.tool_input && input.tool_input.file_path);
    if (rel && !rel.startsWith(".ferret/")) appendEvent(dir, input, { t: "edit", file: rel });
    process.exit(0);
  }

  if (event === "SubagentStart") {
    if (isCritic) appendEvent(dir, input, { t: "review-start", agent: input.agent_id || agent });
    process.exit(0);
  }

  if (event === "SubagentStop") {
    const message = String(input.last_assistant_message || "");

    if (isCritic) {
      // Only an explicit verdict counts: an empty or crashed critic reviewed nothing.
      if (VERDICT.test(message)) {
        const { changed } = replay(readEvents(dir, input));
        appendEvent(dir, input, {
          t: "review-done",
          agent: input.agent_id || agent,
          files: coveredFiles(message, input, changed),
        });
      }
      process.exit(0);
    }

    if (/ferret-worker$/.test(agent) && !input.stop_hook_active && !REPORT_STATUS.test(message)) {
      emit({
        decision: "block",
        reason:
          "ferret: finish with the worker report. End your final message with " +
          "Status: ready | blocked | failed | dropped, then Ticket, Changes, " +
          "Tests run, Risks, Question. A draft is never ready.",
      });
    }
    process.exit(0);
  }

  if (event === "Stop") {
    const gate = config(dir).reviewGate || "nudge";
    const state = replay(readEvents(dir, input));
    if (gate === "off" || state.changed.length === 0) process.exit(0);

    const total = state.changed.length;
    const sample = state.changed.slice(0, 5).join(", ");
    const files = `${total} changed file(s) not reviewed (${sample}${total > 5 ? ", …" : ""})`;

    if (gate === "block" && !input.stop_hook_active && !state.gated) {
      appendEvent(dir, input, { t: "gated" });
      emit({
        decision: "block",
        reason:
          `ferret review gate: ${files}. This project requires critics for every ` +
          "change, whatever its size; reviewing it yourself does not count. Run " +
          "review mode now (ferret skill, sections/review.md): spawn at least the " +
          "blind ferret-critic against the uncommitted diff, plus ferret-codex-critic " +
          "when the codex CLI is installed, then report. If the user declined a " +
          "review in this session, say so in one line and stop.",
      });
      process.exit(0);
    }

    if (gate === "nudge" && !state.nudged) {
      appendEvent(dir, input, { t: "nudged" });
      emit({ systemMessage: `ferret: ${files}. Say "review" to run the critics.` });
    }
  }
} catch {
  process.exit(0);
}
