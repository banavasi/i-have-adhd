// Transcript stripper: turns a session transcript (JSONL) into a clean
// markdown record with plain code and regular expressions. No model call, no
// tokens spent. Used by the context-watch and pre-compact hooks, and runnable
// by hand:
//
//   node hooks/strip.mjs <transcript.jsonl> [out.md]
//
// REMOVED: tool calls and their results, reasoning blocks, subagent threads,
// harness bookkeeping entries, injected reminders and hook text, terminal
// colour codes, one-line narration ("Let me check...").
// KEPT: what the user wrote, what the assistant answered, each shell command
// that was run (first line), and each file that was edited.

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

// Wrapper tags the harness injects into message text. Tag and body both go.
const INJECTED_BLOCKS =
  /<(system-reminder|task-notification|local-command-stdout|local-command-stderr|command-name|command-message|command-args|command-contents|user-prompt-submit-hook|agent-message|ide_selection|ide_opened_file)\b[^>]*>[\s\S]*?<\/\1>/g;
const NOTIFICATION = /^\[SYSTEM NOTIFICATION[^\n]*\n[\s\S]*$/;
const HOOK_LINE =
  /^(?:\w+ hook additional context:|FERRET [A-Z -]+[:.(]|CAVEMAN MODE ACTIVE|Stop hook feedback:)[^\n]*$/gm;
const ANSI = /\u001b\[[0-9;?]*[ -/]*[@-~]/g;
const NARRATION =
  /^(?:Let me|I'll now|I will now|Now I'll|Now let me|I'm going to|Next, I'll)\b[^\n]{0,160}$/gim;

const SHELL_TOOLS = new Set(["Bash", "PowerShell"]);
const EDIT_TOOLS = new Set(["Edit", "Write", "MultiEdit", "NotebookEdit"]);

/** Regex cleanup for one piece of message text. */
export function cleanText(text) {
  return String(text)
    .replace(INJECTED_BLOCKS, "")
    .replace(NOTIFICATION, "")
    .replace(HOOK_LINE, "")
    .replace(ANSI, "")
    .replace(NARRATION, "")
    .replace(/[ \t]+$/gm, "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

/** One short line for a tool call worth remembering, or null to drop it. */
function toolLine(block) {
  const input = block.input || {};
  if (SHELL_TOOLS.has(block.name) && typeof input.command === "string") {
    const first = input.command.trim().split(/\r?\n/)[0];
    return `- ran: \`${first.length > 200 ? `${first.slice(0, 200)}…` : first}\``;
  }
  const file = input.file_path || input.notebook_path;
  if (EDIT_TOOLS.has(block.name) && typeof file === "string") return `- edited: ${file}`;
  return null;
}

/** Strip a transcript's JSONL text down to a markdown record. */
export function stripTranscript(jsonl) {
  const out = [];
  let lastRole = "";
  const push = (role, body) => {
    if (!body) return;
    if (role !== lastRole) out.push(`## ${role}`);
    lastRole = role;
    if (out[out.length - 1] !== body) out.push(body);
  };

  for (const line of String(jsonl).split("\n")) {
    if (!line.trim()) continue;
    let entry;
    try {
      entry = JSON.parse(line);
    } catch {
      continue;
    }
    if (entry.type !== "user" && entry.type !== "assistant") continue;
    if (entry.isSidechain || entry.isMeta || !entry.message) continue;

    const role = entry.isCompactSummary
      ? "Earlier context (summary)"
      : entry.type === "user"
        ? "User"
        : "Assistant";
    const content = entry.message.content;
    if (typeof content === "string") {
      push(role, cleanText(content));
      continue;
    }
    if (!Array.isArray(content)) continue;
    for (const block of content) {
      if (!block || typeof block !== "object") continue;
      if (block.type === "text") push(role, cleanText(block.text || ""));
      else if (block.type === "tool_use" && entry.type === "assistant") push(role, toolLine(block));
      // thinking, tool_result, images, and everything else: dropped.
    }
  }
  return out.length ? `${out.join("\n\n").replace(/(?<=^- [^\n]*)\n\n(?=- )/gm, "\n")}\n` : "";
}

/** Strip `transcriptPath` into `outPath`. Returns size figures, or null. */
export function stripFile(transcriptPath, outPath) {
  const raw = fs.readFileSync(transcriptPath, "utf8");
  const clean = stripTranscript(raw);
  if (!clean) return null;
  fs.mkdirSync(path.dirname(outPath), { recursive: true });
  const header = `# Session record (stripped ${new Date().toISOString()})\n\n`;
  fs.writeFileSync(outPath, header + clean);
  return { before: raw.length, after: header.length + clean.length };
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const [source, target] = process.argv.slice(2);
  if (!source) {
    process.stderr.write("usage: node strip.mjs <transcript.jsonl> [out.md]\n");
    process.exit(2);
  }
  if (target) {
    const sizes = stripFile(source, target);
    process.stdout.write(
      sizes ? `${target}: ${sizes.before} → ${sizes.after} chars\n` : "nothing to keep\n",
    );
  } else {
    process.stdout.write(stripTranscript(fs.readFileSync(source, "utf8")));
  }
}
