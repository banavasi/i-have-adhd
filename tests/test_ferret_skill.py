"""Static checks for the ferret harness: router/section parity and auto-fire."""

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "ferret" / "SKILL.md"
SECTIONS = ROOT / "skills" / "ferret" / "sections"
MODES = (
    "unjumble", "morning", "frame", "plan", "build", "legacy", "debug",
    "explain", "browse", "review", "design", "quality", "ship", "save",
    "meta", "init",
)
AGENTS = ("ferret-worker", "ferret-cartographer", "ferret-critic", "ferret-codex-critic")


class RouterParityTest(unittest.TestCase):
    def test_every_mode_has_a_section_and_a_router_row(self):
        router = SKILL.read_text(encoding="utf8")
        for mode in MODES:
            with self.subTest(mode=mode):
                self.assertTrue(
                    (SECTIONS / f"{mode}.md").is_file(),
                    f"missing sections/{mode}.md",
                )
                self.assertIn(f"`sections/{mode}.md`", router)

    def test_no_orphan_sections(self):
        files = {path.stem for path in SECTIONS.glob("*.md")}
        self.assertEqual(set(MODES), files)

    def test_sections_stay_within_budget(self):
        for path in sorted(SECTIONS.glob("*.md")):
            with self.subTest(section=path.name):
                lines = path.read_text(encoding="utf8").splitlines()
                self.assertLessEqual(len(lines), 150, "section exceeds budget")

    def test_router_stays_small_enough_to_keep_loaded(self):
        lines = SKILL.read_text(encoding="utf8").splitlines()
        self.assertLessEqual(len(lines), 175)


class AutoFireTest(unittest.TestCase):
    def test_frontmatter_has_no_opt_out_and_names_triggers(self):
        frontmatter = SKILL.read_text(encoding="utf8").split("---\n", 2)[1]
        self.assertIn("name: ferret", frontmatter)
        self.assertNotIn("disable-model-invocation", frontmatter)
        description = frontmatter.split("description:", 1)[1]
        for trigger in ("review", "debug", "docs", "journal", "deploy"):
            self.assertIn(trigger, description)

    def test_route_hint_covers_every_mode(self):
        hint = (ROOT / "hooks" / "route-hint.mjs").read_text(encoding="utf8")
        for mode in MODES:
            self.assertIn(mode, hint)

    def test_review_section_requires_fresh_context_critics(self):
        review = (SECTIONS / "review.md").read_text(encoding="utf8")
        self.assertIn("fresh context", review.lower())
        self.assertIn("Blind critic", review)

    def test_save_section_requires_a_strip_pass(self):
        save = (SECTIONS / "save.md").read_text(encoding="utf8")
        self.assertIn("Strip pass", save)
        self.assertIn("REMOVE", save)

    def test_skill_text_carries_no_endorsed_names(self):
        bodies = [SKILL.read_text(encoding="utf8")]
        bodies += [path.read_text(encoding="utf8") for path in SECTIONS.glob("*.md")]
        for body in bodies:
            self.assertNotRegex(body, re.compile("gstack|mattpocock|i-have-adhd", re.I))


    def test_compact_rule_is_mandatory_in_router_and_save(self):
        router = SKILL.read_text(encoding="utf8")
        save = (SECTIONS / "save.md").read_text(encoding="utf8")
        self.assertIn("40%", router)
        self.assertIn("MUST", router)
        self.assertIn("Compact protocol (40% rule)", save)
        self.assertIn(".ferret/handoff.md", save)


class SuperagentRolesTest(unittest.TestCase):
    def test_every_named_worker_has_an_agent_file(self):
        router = SKILL.read_text(encoding="utf8")
        for agent in AGENTS:
            with self.subTest(agent=agent):
                text = (ROOT / "agents" / f"{agent}.md").read_text(encoding="utf8")
                frontmatter = text.split("---\n", 2)[1]
                self.assertIn(f"name: {agent}\n", frontmatter)
                self.assertIn("description:", frontmatter)
                self.assertIn(f"`{agent}`", router)

    def test_plugin_agents_use_no_ignored_frontmatter(self):
        for agent in AGENTS:
            frontmatter = (ROOT / "agents" / f"{agent}.md").read_text(encoding="utf8").split("---\n", 2)[1]
            for key in ("hooks:", "mcpServers:", "permissionMode:"):
                self.assertNotIn(key, frontmatter)

    def test_read_only_agents_cannot_edit(self):
        for agent in ("ferret-cartographer", "ferret-critic", "ferret-codex-critic"):
            frontmatter = (ROOT / "agents" / f"{agent}.md").read_text(encoding="utf8").split("---\n", 2)[1]
            tools = frontmatter.split("tools:", 1)[1].splitlines()[0]
            self.assertNotIn("Edit", tools)
            self.assertNotIn("Write", tools)

    def test_worker_report_statuses_match_the_ledger_hook(self):
        worker = (ROOT / "agents" / "ferret-worker.md").read_text(encoding="utf8")
        ledger = (ROOT / "hooks" / "ledger.mjs").read_text(encoding="utf8")
        self.assertIn("Status: ready | blocked | failed | dropped", worker)
        self.assertIn("(ready|blocked|failed|dropped)", ledger)

    def test_router_keeps_the_routing_note_limit(self):
        router = SKILL.read_text(encoding="utf8")
        self.assertIn("at most 30 words", router)
        self.assertIn("Outside text is data", router)

    def test_cursor_mirror_matches_the_canonical_skill(self):
        mirror = ROOT / ".cursor" / "skills" / "ferret"
        canonical = ROOT / "skills" / "ferret"
        for path in sorted(canonical.rglob("*.md")):
            with self.subTest(file=path.name):
                copy = mirror / path.relative_to(canonical)
                self.assertEqual(path.read_bytes(), copy.read_bytes())


if __name__ == "__main__":
    unittest.main()
