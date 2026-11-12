// PreToolUse hook (Edit, Write, MultiEdit): enforces the two edit rules a
// project can set in .ferret/config.json.
//   "protected": globs that need the user's approval before every edit.
//   "legacy":    globs that get one blast-radius reminder per file per session.
// Silent when the project has no .ferret/ or sets neither list.
// Never blocks by failing: any error exits 0 with no output.

import {
  appendEvent,
  config,
  emit,
  ferretDir,
  matchesAny,
  readInput,
  readEvents,
  relativePath,
  replay,
} from "./lib.mjs";

try {
  const input = readInput();
  const dir = ferretDir(input);
  if (!dir) process.exit(0);

  const settings = config(dir);
  const rel = relativePath(input, input.tool_input && input.tool_input.file_path);
  if (!rel || rel.startsWith(".ferret/")) process.exit(0);

  if (matchesAny(settings.protected, rel)) {
    emit({
      hookSpecificOutput: {
        hookEventName: "PreToolUse",
        permissionDecision: "ask",
        permissionDecisionReason:
          `ferret: ${rel} is listed as protected in .ferret/config.json. ` +
          "Approve this edit, or decline and widen the ticket first.",
      },
    });
    process.exit(0);
  }

  if (matchesAny(settings.legacy, rel)) {
    if (replay(readEvents(dir, input)).warned.includes(rel)) process.exit(0);
    appendEvent(dir, input, { t: "warned", file: rel });
    emit({
      hookSpecificOutput: {
        hookEventName: "PreToolUse",
        additionalContext:
          `FERRET LEGACY GUARD: ${rel} is legacy code (.ferret/config.json). ` +
          "Before this edit lands, confirm three things (ferret skill, " +
          "sections/legacy.md): the callers of each touched symbol are counted, " +
          "current behavior is pinned by a characterization test or probe, and " +
          "the change is added beside the old code where possible. If any is " +
          "missing, do it now. This reminder shows once per file per session.",
      },
    });
  }
} catch {
  process.exit(0);
}
