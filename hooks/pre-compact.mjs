// PreCompact hook: snapshots session state before the harness compacts context.
// Gated on $CLAUDE_CONFIG_DIR/.ferret-always (default ~/.claude).
// Never blocks compaction: any failure exits 0 with no output.
//
// Cross-platform by construction: pure Node, no shell, no network, no OS
// switches. Read-only git probes with tight timeouts; a missing git binary or
// a non-checkout cwd still yields a marker file, never an error.

import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

try {
  const configDir =
    process.env.FERRET_CONFIG_DIR || process.env.CLAUDE_CONFIG_DIR || path.join(os.homedir(), ".claude");
  if (!fs.existsSync(path.join(configDir, ".ferret-always"))) process.exit(0);

  const run = (cmd, args) => {
    try {
      return execFileSync(cmd, args, {
        encoding: "utf8",
        timeout: 10000,
        stdio: ["ignore", "pipe", "ignore"],
      }).trim();
    } catch {
      return "";
    }
  };
  const head = (text, n) => text.split("\n").slice(0, n).join("\n");

  const cwd = process.cwd();
  const branch = run("git", ["-C", cwd, "branch", "--show-current"]);
  const status = run("git", ["-C", cwd, "status", "--short"]);
  const stat = run("git", ["-C", cwd, "diff", "--stat"]);
  const log = run("git", ["-C", cwd, "log", "--oneline", "-5"]);

  const dir = path.join(cwd, ".ferret");
  fs.mkdirSync(dir, { recursive: true });
  const stamp = new Date().toISOString().replace(/[:.]/g, "-");
  const file = path.join(dir, `compact-${stamp}.md`);
  const snapshot = [
    `# Ferret pre-compact snapshot (${new Date().toISOString()})`,
    "",
    branch ? `Branch: ${branch}` : "Not a git checkout (or git unavailable).",
    "",
    "## Status",
    status ? head(status, 30) : "(clean or unavailable)",
    "",
    "## Diff stat",
    stat ? head(stat, 20) : "(none or unavailable)",
    "",
    "## Recent commits",
    log || "(none or unavailable)",
    "",
    "Read `.ferret/handoff.md` after compaction for the resume point.",
    "",
  ];
  fs.writeFileSync(file, snapshot.join("\n"));

  // Also keep the conversation itself, stripped of tool calls by program
  // (strip.mjs: plain code and regular expressions, no model tokens).
  let record = "";
  try {
    // The payload may never come (a terminal, or a pipe nobody closes), so
    // wait at most one second for it instead of blocking compaction.
    const payload = process.stdin.isTTY
      ? ""
      : await new Promise((resolve) => {
          let text = "";
          const done = () => resolve(text);
          const timer = setTimeout(done, 1000);
          process.stdin.setEncoding("utf8");
          process.stdin.on("data", (chunk) => (text += chunk));
          process.stdin.on("end", () => (clearTimeout(timer), done()));
          process.stdin.on("error", () => (clearTimeout(timer), done()));
        });
    process.stdin.pause();
    process.stdin.unref?.();
    const input = JSON.parse(payload || "{}");
    if (input.transcript_path) {
      const { stripFile } = await import("./strip.mjs");
      const id = String(input.session_id || stamp).replace(/[^A-Za-z0-9_-]/g, "_");
      const rawFile = path.join(dir, "raw", `${id}.md`);
      if (stripFile(input.transcript_path, rawFile)) record = ` Stripped session record: ${rawFile}.`;
    }
  } catch {
    // No payload or no transcript: the git snapshot alone is still written.
  }

  process.stdout.write(
    `FERRET PRE-COMPACT: state saved to ${file}.${record} ` +
      "The handoff in .ferret/handoff.md is the resume point after compaction.\n",
    // Exit once the line is flushed: an open stdin must not keep the hook alive.
    () => process.exit(0),
  );
} catch {
  // Never block compaction.
  process.exit(0);
}
