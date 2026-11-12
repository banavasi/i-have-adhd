"""Checks for hooks/strip.mjs: the program that strips a transcript without a model."""

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")
STRIP = ROOT / "hooks" / "strip.mjs"


def entry(kind, content, **extra):
    return json.dumps({"type": kind, "message": {"role": kind, "content": content}, **extra})


TRANSCRIPT = "\n".join(
    [
        json.dumps({"type": "custom-title", "customTitle": "BOOKKEEPING"}),
        entry("user", "<system-reminder>\nSECRET REMINDER\n</system-reminder>\nadd csv export to reports"),
        entry(
            "assistant",
            [
                {"type": "thinking", "thinking": "PRIVATE REASONING", "signature": "abc"},
                {"type": "text", "text": "Let me check the reports module.\nExport goes in reports/export.py."},
                {"type": "tool_use", "id": "toolu_1", "name": "Bash", "input": {"command": "pytest tests/reports -q\necho done"}},
                {"type": "tool_use", "id": "toolu_2", "name": "Read", "input": {"file_path": "reports/view.py"}},
                {"type": "tool_use", "id": "toolu_3", "name": "Edit", "input": {"file_path": "reports/export.py", "old_string": "a", "new_string": "b"}},
            ],
        ),
        entry("user", [{"type": "tool_result", "tool_use_id": "toolu_1", "content": "TOOL OUTPUT 5 passed"}]),
        entry("assistant", [{"type": "text", "text": "SUBAGENT CHATTER"}], isSidechain=True),
        entry("user", "[SYSTEM NOTIFICATION - NOT USER INPUT]\nBACKGROUND EVENT"),
        entry("user", "UserPromptSubmit hook additional context: HOOK NOISE\nalso add a header row"),
        entry("assistant", [{"type": "text", "text": "\u001b[32mHeader row added.\u001b[0m"}]),
        "not json at all",
        "",
    ]
)


@unittest.skipUnless(NODE, "node is not available")
class StripTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.source = Path(self.temp_dir.name) / "session.jsonl"
        self.source.write_text(TRANSCRIPT, encoding="utf8")

    def run_strip(self, *args):
        result = subprocess.run(
            [NODE, str(STRIP), *[str(a) for a in args]],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf8",
        )
        return result

    def test_removes_tool_traffic_reasoning_and_injected_text(self):
        out = self.run_strip(self.source).stdout
        for gone in (
            "BOOKKEEPING", "SECRET REMINDER", "PRIVATE REASONING", "TOOL OUTPUT",
            "SUBAGENT CHATTER", "BACKGROUND EVENT", "HOOK NOISE", "toolu_",
            "tool_use", "tool_result", "system-reminder", "Let me check", "\u001b",
            "reports/view.py", "old_string",
        ):
            with self.subTest(gone=gone):
                self.assertNotIn(gone, out)

    def test_keeps_the_conversation_commands_and_edited_files(self):
        out = self.run_strip(self.source).stdout
        self.assertEqual(
            "## User\n\n"
            "add csv export to reports\n\n"
            "## Assistant\n\n"
            "Export goes in reports/export.py.\n\n"
            "- ran: `pytest tests/reports -q`\n"
            "- edited: reports/export.py\n\n"
            "## User\n\n"
            "also add a header row\n\n"
            "## Assistant\n\n"
            "Header row added.\n",
            out,
        )

    def test_writes_a_file_and_reports_the_size(self):
        target = Path(self.temp_dir.name) / "raw" / "out.md"
        result = self.run_strip(self.source, target)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertRegex(result.stdout, r"\d+ → \d+ chars")
        text = target.read_text(encoding="utf8")
        self.assertTrue(text.startswith("# Session record (stripped "))
        self.assertIn("add csv export to reports", text)

    def test_usage_error_without_arguments(self):
        result = self.run_strip()
        self.assertEqual(2, result.returncode)
        self.assertIn("usage:", result.stderr)

    def test_stripper_calls_no_model_and_no_network(self):
        source = STRIP.read_text(encoding="utf8")
        for banned in ("fetch(", "node:http", "node:https", "child_process", "anthropic", "openai"):
            self.assertNotIn(banned, source)

    def test_compact_hook_saves_the_stripped_record_and_points_to_it(self):
        project = Path(self.temp_dir.name) / "proj"
        (project / ".ferret").mkdir(parents=True)
        self.source.write_text(
            TRANSCRIPT
            + "\n"
            + entry("assistant", [{"type": "text", "text": "big"}]).replace(
                '"content"', '"usage": {"input_tokens": 90000}, "content"'
            )
            + "\n",
            encoding="utf8",
        )
        payload = {
            "session_id": "s9",
            "cwd": str(project),
            "hook_event_name": "Stop",
            "stop_hook_active": False,
            "transcript_path": str(self.source),
        }
        import os

        env = dict(os.environ, CLAUDE_PROJECT_DIR=str(project), CLAUDE_CONFIG_DIR=str(project / "cfg"))
        result = subprocess.run(
            [NODE, str(ROOT / "hooks" / "context-watch.mjs")],
            check=False, capture_output=True, text=True, encoding="utf8", env=env, input=json.dumps(payload),
        )
        self.assertEqual("", result.stderr)
        reason = json.loads(result.stdout)["reason"]
        raw = project / ".ferret" / "raw" / "s9.md"
        self.assertTrue(raw.is_file())
        self.assertIn("stripped by program", reason)
        self.assertIn("Do not rewrite or clean it", reason)
        self.assertNotIn("TOOL OUTPUT", raw.read_text(encoding="utf8"))
        self.assertIn("add csv export to reports", raw.read_text(encoding="utf8"))


if __name__ == "__main__":
    unittest.main()
