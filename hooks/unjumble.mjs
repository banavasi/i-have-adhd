// UserPromptSubmit hook: spots a raw brain dump and asks the model to restate
// it as a clean prompt before working (skills/ferret/sections/unjumble.md).
// Active when the project has .ferret/ or the user opted in to always-on.
// Scores cheap text signals only; the model makes the final call.
// Never blocks: any failure exits 0 with no output.

import { alwaysOn, ferretDir, readInput } from "./lib.mjs";

const COMMON_WORDS = [
  "that", "this", "with", "have", "from", "they", "what", "when", "which",
  "their", "there", "would", "about", "should", "could", "because", "something",
  "the", "and", "for", "you", "need", "want", "things", "using", "create",
  "project", "working", "update", "explain", "review", "feature", "please",
];
const ASK_MARKERS =
  /\b(i need|i want|can you|could you|please|also|and then|then|create|explain|build|make|add|fix|use|update|review|convert|extract|research)\b/gi;

/** True when `token` is `word` with two neighbouring letters swapped. */
function isTransposition(token, word) {
  if (token.length !== word.length || token === word) return false;
  for (let i = 0; i < word.length - 1; i += 1) {
    if (
      token[i] === word[i + 1] &&
      token[i + 1] === word[i] &&
      token.slice(0, i) === word.slice(0, i) &&
      token.slice(i + 2) === word.slice(i + 2)
    ) {
      return true;
    }
  }
  return false;
}

/** Returns the names of the jumble signals found in `prompt`. */
export function jumbleSignals(prompt) {
  const text = prompt.replace(/```[\s\S]*?```/g, " ");
  const urls = text.match(/https?:\/\/\S+/g) || [];
  const prose = text.replace(/https?:\/\/\S+/g, " ");
  const words = prose.split(/\s+/).filter(Boolean);
  if (words.length < 25) return [];

  const signals = [];
  const stops = (prose.match(/[.?!](?:\s|$)|\n/g) || []).length;
  if (words.length >= 40 && stops * 40 < words.length) signals.push("run-on");
  if (words.length >= 80) signals.push("long");
  if (urls.length >= 2) signals.push("several links");
  if ((prose.match(ASK_MARKERS) || []).length >= 5) signals.push("several asks");

  const tokens = words.map((word) => word.toLowerCase().replace(/[^a-z]/g, ""));
  const swapped = tokens.filter(
    (token) =>
      token.length >= 3 &&
      !COMMON_WORDS.includes(token) &&
      COMMON_WORDS.some((word) => isTransposition(token, word)),
  );
  const stutters = tokens.filter((token) => /([a-z])\1\1/.test(token));
  if (swapped.length + stutters.length >= 1) signals.push("typos");
  return signals;
}

try {
  const input = readInput();
  const prompt = typeof input.prompt === "string" ? input.prompt.trim() : "";
  if (!prompt || prompt.startsWith("/")) process.exit(0);
  if (!ferretDir(input) && !alwaysOn()) process.exit(0);

  const signals = jumbleSignals(prompt);
  if (signals.length < 2) process.exit(0);

  process.stdout.write(
    `FERRET UNJUMBLE: this prompt reads like a raw dump (${signals.join(", ")}). ` +
      "As the first thing you write, before any tool call, restate it in one " +
      "fenced block of eight lines or fewer: " +
      "Goal / Context / Constraints / Done-when / Parked " +
      "(ferret skill, sections/unjumble.md). Keep the user's own terms. Do not add " +
      "requirements or plans. Then start on the Goal in the same turn. Ask at most " +
      "one question, and only when a wrong guess would be costly. If the prompt is " +
      "already clear, ignore this hint silently.\n",
  );
} catch {
  process.exit(0);
}
