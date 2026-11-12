// Shared helpers for the project-scoped ferret hooks.
// Pure Node, no shell, no network. Every helper fails soft: a hook that
// cannot read its input or its state does nothing rather than block the user.

import fs from "node:fs";
import os from "node:os";
import path from "node:path";

/** Parse the hook's stdin JSON. Returns {} when stdin is empty or not JSON. */
export function readInput() {
  try {
    const raw = fs.readFileSync(0, "utf8");
    return raw.trim() ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

/** The project root: the harness-provided dir, else the hook input's cwd. */
export function projectDir(input) {
  return process.env.CLAUDE_PROJECT_DIR || input.cwd || process.cwd();
}

/** The project's .ferret directory, or null when the project is not set up. */
export function ferretDir(input) {
  const dir = path.join(projectDir(input), ".ferret");
  try {
    return fs.statSync(dir).isDirectory() ? dir : null;
  } catch {
    return null;
  }
}

/** True when the user opted in to always-on ferret for every session. */
export function alwaysOn() {
  const configDir = process.env.FERRET_CONFIG_DIR || process.env.CLAUDE_CONFIG_DIR || path.join(os.homedir(), ".claude");
  return fs.existsSync(path.join(configDir, ".ferret-always"));
}

export function readText(file) {
  try {
    return fs.readFileSync(file, "utf8");
  } catch {
    return "";
  }
}

export function readJson(file) {
  try {
    const value = JSON.parse(fs.readFileSync(file, "utf8"));
    return value && typeof value === "object" ? value : {};
  } catch {
    return {};
  }
}

/** .ferret/config.json, or {} when missing or malformed. */
export function config(dir) {
  return readJson(path.join(dir, "config.json"));
}

function logPath(dir, input) {
  const id = String(input.session_id || "unknown").replace(/[^A-Za-z0-9_-]/g, "_");
  return path.join(dir, "session", `${id}.log`);
}

/**
 * Append one event to the session ledger. The ledger is an append-only log,
 * one JSON object per line. Hooks for one session run as separate processes,
 * often at the same time: a single short append cannot lose another process's
 * update the way read-change-write of a whole state file can.
 */
export function appendEvent(dir, input, event) {
  const file = logPath(dir, input);
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.appendFileSync(file, `${JSON.stringify(event)}\n`);
}

/** Every event recorded for this session, oldest first. Bad lines are skipped. */
export function readEvents(dir, input) {
  const events = [];
  for (const line of readText(logPath(dir, input)).split("\n")) {
    if (!line.trim()) continue;
    try {
      events.push(JSON.parse(line));
    } catch {
      // A torn or foreign line: ignore it rather than lose the whole ledger.
    }
  }
  return events;
}

/**
 * Replay the events into the current ledger:
 *   changed  files edited and not yet covered by a finished review
 *   nudged   the reminder was already shown for the current change set
 *   gated    the turn was already held for the current change set
 *   warned   files that already got the legacy reminder
 *
 * A finished review clears a file only when the file's last edit came before
 * that review started, and only when the review's target covered the file.
 */
export function replay(events) {
  const lastEdit = new Map();
  const reviewStart = new Map();
  const warned = new Set();
  let nudgedAt = -1;
  let gatedAt = -1;
  let editedAt = -1;

  events.forEach((event, index) => {
    if (event.t === "edit" && typeof event.file === "string") {
      lastEdit.set(event.file, index);
      editedAt = index;
    } else if (event.t === "review-start") {
      reviewStart.set(String(event.agent), index);
    } else if (event.t === "review-done") {
      // No recorded start (a runtime without SubagentStart): the review is
      // taken to cover everything edited before it finished.
      const started = reviewStart.has(String(event.agent)) ? reviewStart.get(String(event.agent)) : index;
      for (const [file, at] of [...lastEdit]) {
        const covered = !Array.isArray(event.files) || event.files.includes(file);
        if (at < started && covered) lastEdit.delete(file);
      }
    } else if (event.t === "nudged") {
      nudgedAt = index;
    } else if (event.t === "gated") {
      gatedAt = index;
    } else if (event.t === "warned" && typeof event.file === "string") {
      warned.add(event.file);
    }
  });

  return {
    changed: [...lastEdit.keys()],
    nudged: nudgedAt > editedAt,
    gated: gatedAt > editedAt,
    warned: [...warned],
  };
}

/** Project-relative path with forward slashes, or null when outside the project. */
export function relativePath(input, filePath) {
  if (typeof filePath !== "string" || !filePath) return null;
  const rel = path.relative(projectDir(input), path.resolve(projectDir(input), filePath));
  if (!rel || rel.startsWith("..") || path.isAbsolute(rel)) return null;
  return rel.split(path.sep).join("/");
}

/** Glob to RegExp: `**` spans directories, `*` stays inside one, `?` is one char. */
export function globToRegExp(glob) {
  let source = "";
  for (let i = 0; i < glob.length; i += 1) {
    const char = glob[i];
    if (char === "*") {
      if (glob[i + 1] === "*") {
        i += 1;
        if (glob[i + 1] === "/") {
          i += 1;
          source += "(?:.*/)?";
        } else {
          source += ".*";
        }
      } else {
        source += "[^/]*";
      }
    } else if (char === "?") {
      source += "[^/]";
    } else {
      source += char.replace(/[.+^${}()|[\]\\]/g, "\\$&");
    }
  }
  return new RegExp(`^${source}$`, "i");
}

export function matchesAny(globs, rel) {
  if (!Array.isArray(globs)) return false;
  return globs.some((glob) => typeof glob === "string" && globToRegExp(glob).test(rel));
}

export function emit(payload) {
  process.stdout.write(`${JSON.stringify(payload)}\n`);
}
