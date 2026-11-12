// SessionStart hook: the one-time declutter question. The first session after
// ferret is installed, it lists the other plugins and personal skills on this
// machine and asks the model to let the user choose which to keep
// (skills/ferret/sections/meta.md §3). It writes a marker so the question is
// never asked again; delete $CLAUDE_CONFIG_DIR/.ferret-onboarded to re-ask.
//
// The hook itself changes nothing: it only reads the inventory. Disabling is
// done by the model, after the user answers, with reversible steps.
// Never blocks session start: any failure exits 0 with no output.

import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { readJson } from "./lib.mjs";

try {
  const configDir = process.env.FERRET_CONFIG_DIR || process.env.CLAUDE_CONFIG_DIR || path.join(os.homedir(), ".claude");
  const marker = path.join(configDir, ".ferret-onboarded");
  if (fs.existsSync(marker)) process.exit(0);

  const installed = readJson(path.join(configDir, "plugins", "installed_plugins.json")).plugins || {};
  const enabled = readJson(path.join(configDir, "settings.json")).enabledPlugins || {};
  const plugins = Object.keys(installed)
    .filter((id) => !/^ferret@/i.test(id) && enabled[id] !== false)
    .sort();

  let skills = [];
  try {
    const folder = path.join(configDir, "skills");
    skills = fs
      .readdirSync(folder, { withFileTypes: true })
      .filter(
        (entry) =>
          entry.isDirectory() &&
          entry.name !== "ferret" &&
          fs.existsSync(path.join(folder, entry.name, "SKILL.md")),
      )
      .map((entry) => entry.name)
      .sort();
  } catch {
    // No personal skills folder.
  }

  fs.mkdirSync(configDir, { recursive: true });
  fs.writeFileSync(marker, `${new Date().toISOString()}\n`);
  if (!plugins.length && !skills.length) process.exit(0);

  process.stdout.write(
    "FERRET FIRST RUN (asked once, never again). Other skills are installed next " +
      "to ferret and may overlap with it. Before other work, run the declutter " +
      "step (ferret skill, sections/meta.md §3): show the list below, ask the " +
      "user once which to KEEP, and disable only what they choose to drop. " +
      "Nothing is disabled without their answer. Nothing is uninstalled or deleted.\n\n" +
      `Plugins (enabled): ${plugins.length ? plugins.join(", ") : "none"}\n` +
      `Personal skills (${path.join(configDir, "skills")}): ${skills.length ? skills.join(", ") : "none"}\n`,
  );
} catch {
  process.exit(0);
}
