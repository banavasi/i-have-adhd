"""Behavior checks for the project-scoped hooks: brief, unjumble, guard, ledger."""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")

JUMBLED = (
    "i need you to research this and taht in the mind of creating skill and using "
    "the subagent we need to use the architecture https://example.com/a and "
    "https://example.com/b i need you extract how they have structured these and "
    "create hooks that help me build features on a legacy project explain the "
    "project do code reviews use the external review ask specific questions and "
    "convert jumbled letters into clean prompts that can speed up the development"
)
CLEAN = (
    "Add a retry to the upload client. It should retry three times with backoff. "
    "Keep the public interface unchanged. Add one test for the retry path. "
    "Do not touch the download client. Report the test command you ran."
)


@unittest.skipUnless(NODE, "node is not available")
class ProjectHookCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        base = Path(self.temp_dir.name)
        self.plugin_root = base / "plugin with spaces"
        shutil.copytree(ROOT / "hooks", self.plugin_root / "hooks")
        self.config_dir = base / "claude config"
        self.config_dir.mkdir()
        self.project = base / "legacy project"
        self.project.mkdir()

    def init_project(self, config=None):
        ferret = self.project / ".ferret"
        ferret.mkdir(exist_ok=True)
        if config is not None:
            (ferret / "config.json").write_text(json.dumps(config), encoding="utf8")
        return ferret

    def run_hook(self, module, payload):
        env = os.environ.copy()
        env["CLAUDE_CONFIG_DIR"] = str(self.config_dir)
        env["CLAUDE_PROJECT_DIR"] = str(self.project)
        payload = {"session_id": "s1", "cwd": str(self.project), **payload}
        result = subprocess.run(
            [NODE, str(self.plugin_root / "hooks" / module)],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf8",
            env=env,
            input=json.dumps(payload),
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("", result.stderr)
        return result.stdout

    def run_json(self, module, payload):
        out = self.run_hook(module, payload)
        return json.loads(out) if out.strip() else None

    def edit(self, rel, event="PostToolUse", module="ledger.mjs"):
        return self.run_json(
            module,
            {
                "hook_event_name": event,
                "tool_name": "Edit",
                "tool_input": {"file_path": str(self.project / rel)},
            },
        )


class RegistrationTest(unittest.TestCase):
    def test_every_new_hook_uses_the_shared_launcher(self):
        hooks = json.loads((ROOT / "hooks" / "hooks.json").read_text(encoding="utf8"))["hooks"]
        expected = {
            "SessionStart": "session-brief.mjs",
            "UserPromptSubmit": "unjumble.mjs",
            "PreToolUse": "legacy-guard.mjs",
            "PostToolUse": "ledger.mjs",
            "SubagentStop": "ledger.mjs",
            "Stop": "ledger.mjs",
        }
        for event, module in expected.items():
            with self.subTest(event=event):
                commands = [h["command"] for group in hooks[event] for h in group["hooks"]]
                matching = [c for c in commands if module in c]
                self.assertEqual(1, len(matching))
                self.assertRegex(matching[0], r'^node -e "')
                self.assertIn("process.env.CLAUDE_PLUGIN_ROOT", matching[0])
                self.assertIn(".catch", matching[0])
                self.assertTrue((ROOT / "hooks" / module).is_file())


class UnjumbleTest(ProjectHookCase):
    def prompt(self, text):
        return self.run_hook("unjumble.mjs", {"hook_event_name": "UserPromptSubmit", "prompt": text})

    def test_silent_when_project_is_not_set_up(self):
        self.assertEqual("", self.prompt(JUMBLED))

    def test_flags_a_raw_dump_and_names_its_signals(self):
        self.init_project()
        out = self.prompt(JUMBLED)
        self.assertIn("FERRET UNJUMBLE", out)
        self.assertIn("run-on", out)
        self.assertIn("several links", out)
        self.assertIn("typos", out)
        self.assertIn("Do not add", out)

    def test_always_on_flag_enables_it_without_a_project(self):
        (self.config_dir / ".ferret-always").touch()
        self.assertIn("FERRET UNJUMBLE", self.prompt(JUMBLED))

    def test_leaves_clean_short_and_slash_prompts_alone(self):
        self.init_project()
        for text in (CLEAN, "fix teh bug", "/ferret " + JUMBLED, ""):
            with self.subTest(text=text[:20]):
                self.assertEqual("", self.prompt(text))


class SessionBriefTest(ProjectHookCase):
    def brief(self):
        return self.run_hook("session-brief.mjs", {"hook_event_name": "SessionStart", "source": "startup"})

    def test_silent_when_project_is_not_set_up(self):
        self.assertEqual("", self.brief())

    def test_reports_rules_handoff_open_tickets_and_counts(self):
        ferret = self.init_project()
        (ferret / "rules.md").write_text("## Ticket scope\nNever touch billing.\n", encoding="utf8")
        (ferret / "handoff.md").write_text("# Handoff\nGoal: add export\nNext: wire the route\n", encoding="utf8")
        (ferret / "inbox.md").write_text("# Inbox\n- [ ] one\n- [x] done\n- [ ] two\n", encoding="utf8")
        (ferret / "parked.md").write_text("- idea a\n", encoding="utf8")
        (ferret / "map.md").write_text("# Map   Commit: abc1234   Date: 2026-11-11\n", encoding="utf8")
        tickets = ferret / "tickets"
        tickets.mkdir()
        (tickets / "001-export.md").write_text("# T-001 CSV export\nStage: working\n", encoding="utf8")
        (tickets / "002-old.md").write_text("# T-002 Old thing\nStage: ended\n", encoding="utf8")

        out = self.brief()

        self.assertIn("FERRET PROJECT BRIEF", out)
        self.assertIn("Never touch billing.", out)
        self.assertIn("Next: wire the route", out)
        self.assertIn("T-001 CSV export — working", out)
        self.assertNotIn("T-002", out)
        self.assertIn("Inbox: 2 open", out)
        self.assertIn("Parked: 1 item", out)
        self.assertIn("commit abc1234", out)

    def test_skips_a_seed_handoff_and_says_when_there_is_no_map(self):
        ferret = self.init_project()
        (ferret / "handoff.md").write_text("# Handoff\nStatus: no active session\n", encoding="utf8")
        out = self.brief()
        self.assertNotIn("Last handoff", out)
        self.assertIn("Map: none yet", out)


class LegacyGuardTest(ProjectHookCase):
    def guard(self, rel):
        return self.edit(rel, event="PreToolUse", module="legacy-guard.mjs")

    def test_silent_without_project_or_lists(self):
        self.assertIsNone(self.guard("src/a.py"))
        self.init_project({})
        self.assertIsNone(self.guard("src/a.py"))

    def test_protected_path_asks_every_time(self):
        self.init_project({"protected": ["db/migrations/**"]})
        for _ in range(2):
            out = self.guard("db/migrations/0001_init.sql")["hookSpecificOutput"]
            self.assertEqual("ask", out["permissionDecision"])
            self.assertIn("db/migrations/0001_init.sql", out["permissionDecisionReason"])
        self.assertIsNone(self.guard("db/schema.sql"))

    def test_legacy_path_reminds_once_per_file(self):
        self.init_project({"legacy": ["src/old/**", "*.bas"]})
        first = self.guard("src/old/billing/calc.py")["hookSpecificOutput"]
        self.assertNotIn("permissionDecision", first)
        self.assertIn("FERRET LEGACY GUARD", first["additionalContext"])
        self.assertIsNone(self.guard("src/old/billing/calc.py"))
        self.assertIsNotNone(self.guard("main.bas"))
        self.assertIsNone(self.guard("src/new/calc.py"))
        self.assertIsNone(self.guard("lib/main.bas"))

    def test_ignores_files_outside_the_project_and_inside_the_channel(self):
        self.init_project({"protected": ["**"]})
        self.assertIsNone(self.guard("../elsewhere/a.py"))
        self.assertIsNone(self.guard(".ferret/handoff.md"))


class LedgerTest(ProjectHookCase):
    def stop(self, active=False):
        return self.run_json("ledger.mjs", {"hook_event_name": "Stop", "stop_hook_active": active})

    def subagent(self, agent, message, active=False):
        return self.run_json(
            "ledger.mjs",
            {
                "hook_event_name": "SubagentStop",
                "agent_type": agent,
                "last_assistant_message": message,
                "stop_hook_active": active,
            },
        )

    def test_silent_without_project_or_changes(self):
        self.assertIsNone(self.edit("src/a.py"))
        self.assertIsNone(self.stop())
        self.init_project()
        self.assertIsNone(self.stop())

    def test_nudges_once_per_change_set_by_default(self):
        self.init_project()
        self.edit("src/a.py")
        self.edit("src/a.py")
        self.edit(".ferret/handoff.md")
        message = self.stop()["systemMessage"]
        self.assertIn("1 changed file(s) not reviewed", message)
        self.assertIn("src/a.py", message)
        self.assertIsNone(self.stop())
        self.edit("src/b.py")
        self.assertIn("2 changed file(s)", self.stop()["systemMessage"])

    def test_block_mode_holds_the_turn_once(self):
        self.init_project({"reviewGate": "block"})
        self.edit("src/a.py")
        out = self.stop()
        self.assertEqual("block", out["decision"])
        self.assertIn("ferret-codex-critic", out["reason"])
        self.assertIsNone(self.stop(active=True))
        self.assertIsNone(self.stop())

    def test_off_mode_is_silent(self):
        self.init_project({"reviewGate": "off"})
        self.edit("src/a.py")
        self.assertIsNone(self.stop())

    def test_a_critic_clears_the_review_debt(self):
        self.init_project()
        self.edit("src/a.py")
        self.subagent("ferret:ferret-critic", "Axis: blind\nVerdict: changes-needed")
        self.assertIsNone(self.stop())

    def test_a_critic_that_could_not_review_clears_nothing(self):
        self.init_project()
        self.edit("src/a.py")
        self.subagent("ferret:ferret-codex-critic", "Verdict: cannot-review\ncodex missing")
        self.assertIn("not reviewed", self.stop()["systemMessage"])

    def test_worker_without_a_status_report_is_sent_back_once(self):
        self.init_project()
        out = self.subagent("ferret:ferret-worker", "I changed some files.")
        self.assertEqual("block", out["decision"])
        self.assertIn("Status: ready | blocked | failed | dropped", out["reason"])
        self.assertIsNone(self.subagent("ferret:ferret-worker", "Still no report.", active=True))

    def test_worker_with_a_status_report_passes(self):
        self.init_project()
        report = "Done.\n\nStatus: blocked\nTicket: T-001\nQuestion: Keep the v1 route?"
        self.assertIsNone(self.subagent("ferret-worker", report))
        self.assertIsNone(self.subagent("general-purpose", "no report needed"))


class ContextWatchTest(ProjectHookCase):
    def transcript(self, tokens, sidechain_tokens=None):
        def entry(total, sidechain=False):
            usage = {"input_tokens": 10, "cache_read_input_tokens": total - 10, "cache_creation_input_tokens": 0}
            return json.dumps({"type": "assistant", "isSidechain": sidechain, "message": {"usage": usage}})

        lines = [json.dumps({"type": "user", "message": {"content": "hi"}}), entry(tokens)]
        if sidechain_tokens:
            lines.append(entry(sidechain_tokens, sidechain=True))
        path = Path(self.temp_dir.name) / "transcript.jsonl"
        path.write_text("\n".join(lines) + "\n", encoding="utf8")
        return str(path)

    def stop(self, tokens, active=False, **extra):
        payload = {"hook_event_name": "Stop", "stop_hook_active": active}
        payload["transcript_path"] = self.transcript(tokens, **extra)
        return self.run_json("context-watch.mjs", payload)

    def test_registered_on_stop_with_the_shared_launcher(self):
        hooks = json.loads((ROOT / "hooks" / "hooks.json").read_text(encoding="utf8"))["hooks"]
        for event, module in (("Stop", "context-watch.mjs"), ("SessionStart", "first-run.mjs")):
            commands = [h["command"] for group in hooks[event] for h in group["hooks"]]
            self.assertEqual(1, len([c for c in commands if module in c]))

    def test_silent_when_project_is_not_set_up(self):
        self.assertIsNone(self.stop(150000))

    def test_silent_below_the_limit(self):
        self.init_project()
        self.assertIsNone(self.stop(79000))

    def test_holds_the_turn_once_at_forty_percent(self):
        self.init_project()
        out = self.stop(80000)
        self.assertEqual("block", out["decision"])
        self.assertIn("context is at 40% (limit 40%)", out["reason"])
        self.assertIn(".ferret/handoff.md", out["reason"])
        self.assertIn("journal", out["reason"])
        self.assertIn("/compact", out["reason"])
        self.assertIsNone(self.stop(90000))

    def test_arms_again_after_the_context_shrinks(self):
        self.init_project()
        self.assertIsNotNone(self.stop(90000))
        self.assertIsNone(self.stop(20000))
        self.assertEqual("block", self.stop(85000)["decision"])

    def test_never_blocks_while_a_stop_hook_is_already_active(self):
        self.init_project()
        self.assertIsNone(self.stop(120000, active=True))

    def test_ignores_subagent_usage(self):
        self.init_project()
        self.assertIsNone(self.stop(30000, sidechain_tokens=190000))

    def test_limit_and_window_come_from_project_config(self):
        self.init_project({"compactAt": 60, "contextWindow": 1000000})
        self.assertIsNone(self.stop(500000))
        self.assertIn("at 60% (limit 60%)", self.stop(600000)["reason"])

    def test_zero_turns_the_rule_off(self):
        self.init_project({"compactAt": 0})
        self.assertIsNone(self.stop(190000))

    def test_always_on_flag_enables_it_without_a_project(self):
        (self.config_dir / ".ferret-always").touch()
        out = self.stop(100000)
        self.assertEqual("block", out["decision"])
        self.assertNotIn(".ferret/handoff.md", out["reason"])


class FirstRunTest(ProjectHookCase):
    def start(self):
        return self.run_hook("first-run.mjs", {"hook_event_name": "SessionStart", "source": "startup"})

    def seed(self):
        plugins = self.config_dir / "plugins"
        plugins.mkdir()
        (plugins / "installed_plugins.json").write_text(
            json.dumps({"version": 2, "plugins": {"ferret@ferret": [], "other@market": [], "off@market": []}}),
            encoding="utf8",
        )
        (self.config_dir / "settings.json").write_text(
            json.dumps({"enabledPlugins": {"ferret@ferret": True, "other@market": True, "off@market": False}}),
            encoding="utf8",
        )
        for name in ("deep-review", "ferret"):
            (self.config_dir / "skills" / name).mkdir(parents=True)
            (self.config_dir / "skills" / name / "SKILL.md").write_text("x", encoding="utf8")
        (self.config_dir / "skills" / "not-a-skill").mkdir()

    def test_lists_other_enabled_plugins_and_skills_then_never_asks_again(self):
        self.seed()
        out = self.start()
        self.assertIn("FERRET FIRST RUN", out)
        self.assertIn("Plugins (enabled): other@market\n", out)
        self.assertIn("): deep-review\n", out)
        self.assertNotIn("not-a-skill", out)
        self.assertIn("Nothing is uninstalled or deleted", out)
        self.assertTrue((self.config_dir / ".ferret-onboarded").is_file())
        self.assertEqual("", self.start())

    def test_changes_nothing_on_disk_except_the_marker(self):
        self.seed()
        before = sorted(p.relative_to(self.config_dir).as_posix() for p in self.config_dir.rglob("*"))
        self.start()
        after = sorted(p.relative_to(self.config_dir).as_posix() for p in self.config_dir.rglob("*"))
        self.assertEqual(before + [".ferret-onboarded"], sorted(after, key=lambda p: (p == ".ferret-onboarded", p)))

    def test_silent_with_nothing_else_installed_and_still_marks_done(self):
        self.assertEqual("", self.start())
        self.assertTrue((self.config_dir / ".ferret-onboarded").is_file())


class LedgerCoverageTest(ProjectHookCase):
    """A finished review clears only what it covered, and parallel hooks lose nothing."""

    def stop(self):
        return self.run_json("ledger.mjs", {"hook_event_name": "Stop", "stop_hook_active": False})

    def critic(self, event, message="", agent_id="a1"):
        return self.run_json(
            "ledger.mjs",
            {
                "hook_event_name": event,
                "agent_type": "ferret:ferret-critic",
                "agent_id": agent_id,
                "last_assistant_message": message,
            },
        )

    def test_subagent_start_is_registered_for_critics(self):
        hooks = json.loads((ROOT / "hooks" / "hooks.json").read_text(encoding="utf8"))["hooks"]
        group = hooks["SubagentStart"][0]
        self.assertEqual("ferret-(critic|codex-critic)$", group["matcher"])
        self.assertIn("ledger.mjs", group["hooks"][0]["command"])

    def test_an_edit_made_while_the_critic_runs_stays_unreviewed(self):
        self.init_project()
        self.edit("src/a.py")
        self.critic("SubagentStart")
        self.edit("src/b.py")
        self.critic("SubagentStop", "Target: uncommitted\nVerdict: approve")
        message = self.stop()["systemMessage"]
        self.assertIn("1 changed file(s)", message)
        self.assertIn("src/b.py", message)
        self.assertNotIn("src/a.py", message)

    def test_a_file_edited_again_during_review_stays_unreviewed(self):
        self.init_project()
        self.edit("src/a.py")
        self.critic("SubagentStart")
        self.edit("src/a.py")
        self.critic("SubagentStop", "Target: uncommitted\nVerdict: changes-needed")
        self.assertIn("src/a.py", self.stop()["systemMessage"])

    def test_a_review_of_one_commit_clears_nothing(self):
        self.init_project()
        self.edit("src/a.py")
        self.critic("SubagentStart")
        self.critic("SubagentStop", "Target: commit 58422bc\nVerdict: approve")
        self.assertIn("src/a.py", self.stop()["systemMessage"])

    @unittest.skipUnless(shutil.which("git"), "git is required")
    def test_a_range_review_clears_committed_files_only(self):
        self.init_project()
        git = ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid"]
        subprocess.run([*git, "init", "-q"], cwd=self.project, check=True)
        (self.project / "src").mkdir()
        (self.project / ".gitignore").write_text(".ferret/\n", encoding="utf8")
        for name in ("done.py", "dirty.py"):
            (self.project / "src" / name).write_text("x = 1\n", encoding="utf8")
        subprocess.run([*git, "add", "-A"], cwd=self.project, check=True)
        subprocess.run([*git, "commit", "-q", "-m", "base"], cwd=self.project, check=True)
        (self.project / "src" / "dirty.py").write_text("x = 2\n", encoding="utf8")

        self.edit("src/done.py")
        self.edit("src/dirty.py")
        self.critic("SubagentStart")
        self.critic("SubagentStop", "Target: main..HEAD\nVerdict: approve")

        message = self.stop()["systemMessage"]
        self.assertIn("src/dirty.py", message)
        self.assertNotIn("src/done.py", message)

    def test_two_critics_are_tracked_separately(self):
        self.init_project()
        self.edit("src/a.py")
        self.critic("SubagentStart", agent_id="early")
        self.edit("src/b.py")
        self.critic("SubagentStart", agent_id="late")
        self.critic("SubagentStop", "Target: uncommitted\nVerdict: approve", agent_id="early")
        self.assertIn("src/b.py", self.stop()["systemMessage"])
        self.critic("SubagentStop", "Target: uncommitted\nVerdict: approve", agent_id="late")
        self.edit("src/c.py")
        message = self.stop()["systemMessage"]
        self.assertIn("1 changed file(s)", message)
        self.assertIn("src/c.py", message)

    def test_parallel_hooks_lose_no_edits(self):
        self.init_project({"legacy": ["src/**"]})
        env = os.environ.copy()
        env["CLAUDE_CONFIG_DIR"] = str(self.config_dir)
        env["CLAUDE_PROJECT_DIR"] = str(self.project)
        procs = []
        for index in range(24):
            module, event = (("ledger.mjs", "PostToolUse"), ("legacy-guard.mjs", "PreToolUse"))[index % 2]
            payload = {
                "session_id": "s1",
                "cwd": str(self.project),
                "hook_event_name": event,
                "tool_name": "Edit",
                "tool_input": {"file_path": str(self.project / "src" / f"f{index}.py")},
            }
            proc = subprocess.Popen(
                [NODE, str(self.plugin_root / "hooks" / module)],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, text=True,
            )
            proc.stdin.write(json.dumps(payload))
            proc.stdin.close()
            procs.append(proc)
        for proc in procs:
            proc.wait(timeout=60)
            self.assertEqual("", proc.stderr.read())
            proc.stdout.close()
            proc.stderr.close()

        log = (self.project / ".ferret" / "session" / "s1.log").read_text(encoding="utf8")
        events = [json.loads(row) for row in log.splitlines()]
        self.assertEqual(12, sum(1 for e in events if e["t"] == "edit"))
        self.assertEqual(12, sum(1 for e in events if e["t"] == "warned"))
        self.assertIn("12 changed file(s)", self.stop()["systemMessage"])

    def test_a_torn_log_line_is_skipped(self):
        ferret = self.init_project()
        self.edit("src/a.py")
        with (ferret / "session" / "s1.log").open("a", encoding="utf8") as handle:
            handle.write('{"t": "edit", "file": "src/half\n')
        self.edit("src/b.py")
        self.assertIn("2 changed file(s)", self.stop()["systemMessage"])


if __name__ == "__main__":
    unittest.main()
