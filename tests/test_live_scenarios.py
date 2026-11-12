"""Offline checks for scripts/run_live_scenarios.py. No model is called here."""

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import run_live_scenarios as live  # noqa: E402


def line(**event):
    return json.dumps(event)


STREAM = "\n".join(
    [
        line(type="system", subtype="hook_response", hook_event="SessionStart", output="FERRET PROJECT BRIEF", exit_code=0, stderr=""),
        line(type="system", subtype="hook_response", hook_event="Stop", output="", exit_code=1, stderr="boom"),
        line(
            type="assistant",
            parent_tool_use_id=None,
            message={
                "content": [
                    {"type": "text", "text": "Mode: review — diff needs critics"},
                    {"type": "tool_use", "name": "Agent", "input": {"subagent_type": "ferret:ferret-critic"}},
                    {"type": "tool_use", "name": "Agent", "input": {"subagent_type": "ferret:ferret-critic"}},
                ]
            },
        ),
        line(
            type="assistant",
            parent_tool_use_id="toolu_1",
            message={"content": [{"type": "text", "text": "SUBAGENT TEXT"}, {"type": "tool_use", "name": "Read", "input": {}}]},
        ),
        "not json",
        line(type="result", subtype="success", total_cost_usd=0.5, num_turns=4, permission_denials=[]),
    ]
)


class ScenarioFileTest(unittest.TestCase):
    def test_scenarios_load_and_cover_every_new_piece(self):
        ids = {s["id"] for s in live.load_scenarios()}
        for needed in (
            "init", "session-brief", "unjumble", "explain", "legacy", "worker", "review",
            "review-codex", "review-gate", "protected", "compact", "first-run",
        ):
            self.assertIn(needed, ids)

    def test_fixture_and_review_overlay_exist(self):
        self.assertTrue((live.FIXTURE / "legacy" / "billing" / "calc.py").is_file())
        self.assertTrue((live.REVIEW_OVERLAY / "legacy" / "billing" / "store.py").is_file())


class ParseStreamTest(unittest.TestCase):
    def setUp(self):
        self.run = live.parse_stream(STREAM)

    def test_keeps_main_thread_reply_only(self):
        self.assertEqual(["Mode: review — diff needs critics"], self.run["reply"])

    def test_collects_tools_agents_hooks_and_result(self):
        self.assertEqual(["Agent", "Agent", "Read"], self.run["tools"])
        self.assertEqual(["ferret:ferret-critic"] * 2, self.run["agents"])
        self.assertEqual("FERRET PROJECT BRIEF", self.run["hooks"][0]["output"])
        self.assertEqual(0.5, self.run["result"]["total_cost_usd"])

    def test_reports_failing_hooks(self):
        self.assertEqual(1, len(self.run["hook_errors"]))
        self.assertIn("Stop", self.run["hook_errors"][0])


@unittest.skipUnless(shutil.which("git"), "git is required")
class PrepareAndEvaluateTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        scenario = {
            "id": "t",
            "setup": {"config": {"legacy": ["legacy/**"]}, "review_branch": True, "files": {".ferret/tickets/001-x.md": "# T-001 x\nStage: open\n"}},
        }
        self.ctx = live.prepare(scenario, Path(self.temp.name))
        self.run = live.parse_stream(STREAM)

    def check(self, **check):
        return live.evaluate(check, self.run, self.ctx)[0]

    def test_prepare_builds_an_isolated_project(self):
        project, config = self.ctx["project"], self.ctx["config"]
        self.assertTrue((project / ".git").is_dir())
        self.assertEqual({"legacy": ["legacy/**"]}, json.loads((project / ".ferret" / "config.json").read_text()))
        self.assertIn("lower(name)", (project / "legacy" / "billing" / "store.py").read_text())
        self.assertTrue((config / ".ferret-always").is_file())
        self.assertTrue((config / ".ferret-onboarded").is_file())

    def test_reply_hook_agent_and_tool_checks(self):
        self.assertTrue(self.check(type="reply_matches", regex="^Mode: review"))
        self.assertFalse(self.check(type="reply_matches", regex="SUBAGENT"))
        self.assertTrue(self.check(type="reply_not_matches", regex="^Goal:"))
        self.assertTrue(self.check(type="hook_output_contains", event="SessionStart", text="BRIEF"))
        self.assertFalse(self.check(type="hook_output_contains", event="Stop", text="BRIEF"))
        self.assertTrue(self.check(type="agent_spawned", agent="ferret-critic", min=2))
        self.assertFalse(self.check(type="agent_spawned", agent="ferret-critic", min=3))
        self.assertFalse(self.check(type="agent_spawned", agent="ferret-worker"))
        self.assertTrue(self.check(type="tool_used", name="Agent"))
        self.assertTrue(self.check(type="tool_not_used", name="Edit"))

    def test_file_checks(self):
        self.assertTrue(self.check(type="file_exists", path=".ferret/tickets/*.md"))
        self.assertFalse(self.check(type="file_exists", path=".ferret/map.md"))
        self.assertTrue(self.check(type="file_contains", path=".ferret/tickets/*.md", regex="(?m)^Stage:"))
        self.assertTrue(self.check(type="file_not_contains", path=".ferret/tickets/*.md", text="toolu_"))
        self.assertFalse(self.check(type="file_not_contains", path=".ferret/missing/*.md", text="x"))
        self.assertTrue(self.check(type="file_unchanged", path="app.py"))
        (self.ctx["project"] / "app.py").write_text("changed", encoding="utf8")
        self.assertFalse(self.check(type="file_unchanged", path="app.py"))
        self.assertFalse(self.check(type="journal_written"))
        (self.ctx["journal"] / "daily").mkdir()
        (self.ctx["journal"] / "daily" / "d.md").write_text("x", encoding="utf8")
        self.assertTrue(self.check(type="journal_written"))
        self.assertTrue(self.check(type="config_file_exists", path=".ferret-always"))


if __name__ == "__main__":
    unittest.main()
