"""Run ferret end to end in real Claude Code sessions and check what happened.

Each scenario copies the fixture legacy project into a temp folder, starts a
headless Claude Code session there with this checkout loaded as a plugin, sends
one prompt, and then checks the event stream and the files left behind.

    python scripts/run_live_scenarios.py --list
    python scripts/run_live_scenarios.py --only unjumble,explain
    python scripts/run_live_scenarios.py --model claude-opus-5-5 --jobs 3

Isolation: user settings are not loaded (`--setting-sources ""`), ferret's own
flag and marker files go to a temp folder (FERRET_CONFIG_DIR), and the journal
goes to a temp folder (DEV_JOURNAL). The operator's real config is not touched.

This spends real model tokens. Every session is capped with --budget-usd.
"""

import argparse
import concurrent.futures
import datetime
import fnmatch
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ROOT / "evals" / "live" / "scenarios.json"
FIXTURE = ROOT / "evals" / "fixtures" / "legacy-shop"
REVIEW_OVERLAY = ROOT / "evals" / "fixtures" / "legacy-shop-review"

BASE_TOOLS = [
    "Read", "Grep", "Glob", "Agent", "Task", "Skill", "TodoWrite",
    "Bash(git:*)", "Bash(python:*)", "Bash(python3:*)", "Bash(ls:*)", "Bash(cat:*)",
    "Bash(mkdir:*)", "Bash(grep:*)", "Bash(wc:*)", "Bash(sort:*)", "Bash(head:*)",
    "Bash(uniq:*)", "Bash(date:*)",
    # On Windows the session's shell tool is PowerShell.
    "PowerShell(git:*)", "PowerShell(python:*)", "PowerShell(ls:*)", "PowerShell(cat:*)",
    "PowerShell(mkdir:*)", "PowerShell(Get-ChildItem:*)", "PowerShell(Get-Content:*)",
    "PowerShell(Get-Date:*)", "PowerShell(New-Item:*)", "PowerShell(Test-Path:*)",
]
CHECK_TYPES = {
    "reply_matches", "reply_not_matches", "hook_output_contains", "agent_spawned",
    "tool_used", "any_tool_used", "tool_not_used", "file_exists", "file_contains", "file_not_contains",
    "file_unchanged", "journal_written", "config_file_exists", "command_passes",
}


def load_scenarios():
    scenarios = json.loads(SCENARIOS.read_text(encoding="utf8"))
    seen = set()
    for scenario in scenarios:
        for key in ("id", "title", "prompt", "checks"):
            if key not in scenario:
                raise ValueError(f"scenario missing {key}: {scenario.get('id')}")
        if scenario["id"] in seen:
            raise ValueError(f"duplicate scenario id: {scenario['id']}")
        seen.add(scenario["id"])
        for check in scenario["checks"]:
            if check.get("type") not in CHECK_TYPES:
                raise ValueError(f"{scenario['id']}: unknown check type {check.get('type')}")
    return scenarios


# ---------------------------------------------------------------- stream

def parse_stream(text):
    """Reduce a stream-json transcript to the facts the checks need."""
    run = {"hooks": [], "reply": [], "tools": [], "agents": [], "result": {}, "hook_errors": []}
    for line in text.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        kind = event.get("type")
        if kind == "system" and event.get("subtype") == "hook_response":
            output = event.get("output") or event.get("stdout") or ""
            run["hooks"].append({"event": event.get("hook_event", ""), "output": output})
            if event.get("exit_code") not in (0, None) or event.get("stderr"):
                run["hook_errors"].append(
                    f"{event.get('hook_event')}: exit {event.get('exit_code')} {event.get('stderr', '')[:200]}"
                )
        elif kind == "assistant":
            main_thread = event.get("parent_tool_use_id") is None
            for block in (event.get("message") or {}).get("content") or []:
                if block.get("type") == "text" and main_thread and block.get("text", "").strip():
                    run["reply"].append(block["text"].strip())
                elif block.get("type") == "tool_use":
                    run["tools"].append(block.get("name", ""))
                    if block.get("name") in ("Agent", "Task"):
                        run["agents"].append(str((block.get("input") or {}).get("subagent_type", "")))
        elif kind == "result":
            run["result"] = event
    return run


# ---------------------------------------------------------------- checks

def _matches(pattern, project):
    return sorted(glob.glob(str(project / pattern), recursive=True))


def _read(path):
    try:
        return Path(path).read_text(encoding="utf8", errors="replace")
    except OSError:
        return ""


def _hit(check, text):
    if "regex" in check:
        return re.search(check["regex"], text) is not None
    return check["text"] in text


def evaluate(check, run, ctx):
    """Return (passed, detail) for one check."""
    kind = check["type"]
    reply = "\n\n".join(run["reply"])
    project = ctx["project"]

    if kind == "reply_matches":
        return re.search(check["regex"], reply) is not None, f"reply ~ /{check['regex']}/"
    if kind == "reply_not_matches":
        return re.search(check["regex"], reply) is None, f"reply !~ /{check['regex']}/"
    if kind == "hook_output_contains":
        hit = any(
            h["event"] == check["event"] and check["text"] in h["output"] for h in run["hooks"]
        )
        return hit, f"{check['event']} hook output has '{check['text']}'"
    if kind == "agent_spawned":
        count = sum(1 for a in run["agents"] if a.split(":")[-1] == check["agent"])
        need = check.get("min", 1)
        return count >= need, f"{check['agent']} spawned {count}x (need {need})"
    if kind == "tool_used":
        return check["name"] in run["tools"], f"tool {check['name']} used"
    if kind == "any_tool_used":
        used = [n for n in check["names"] if n in run["tools"]]
        return bool(used), f"one of {check['names']} used (got {used})"
    if kind == "tool_not_used":
        return check["name"] not in run["tools"], f"tool {check['name']} not used"
    if kind == "file_exists":
        return bool(_matches(check["path"], project)), f"exists {check['path']}"
    if kind == "file_contains":
        hit = any(_hit(check, _read(p)) for p in _matches(check["path"], project))
        return hit, f"{check['path']} has {check.get('regex') or check.get('text')}"
    if kind == "file_not_contains":
        files = _matches(check["path"], project)
        clean = bool(files) and not any(_hit(check, _read(p)) for p in files)
        return clean, f"{check['path']} lacks {check.get('regex') or check.get('text')}"
    if kind == "file_unchanged":
        same = _read(project / check["path"]) == ctx["baseline"].get(check["path"], None)
        return same, f"unchanged {check['path']}"
    if kind == "journal_written":
        files = [p for p in ctx["journal"].rglob("*") if p.is_file()]
        return bool(files), f"journal has {len(files)} file(s)"
    if kind == "config_file_exists":
        return (ctx["config"] / check["path"]).exists(), f"config has {check['path']}"
    if kind == "command_passes":
        done = subprocess.run(check["command"], cwd=project, capture_output=True, text=True)
        return done.returncode == 0, f"{' '.join(check['command'])} exit {done.returncode}"
    raise ValueError(f"unknown check type: {kind}")


# ---------------------------------------------------------------- setup

def _git(project, *args):
    subprocess.run(
        ["git", "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid",
         "-c", "core.autocrlf=false", *args],
        cwd=project, check=True, capture_output=True,
    )


def prepare(scenario, workdir):
    """Build the temp project, config folder, and journal folder for a scenario."""
    setup = scenario.get("setup", {})
    project, config, journal = workdir / "project", workdir / "config", workdir / "journal"
    shutil.copytree(FIXTURE, project)
    config.mkdir()
    journal.mkdir()

    (project / ".gitignore").write_text("__pycache__/\n", encoding="utf8")
    _git(project, "init", "-q", "-b", "main")
    _git(project, "add", "-A")
    _git(project, "commit", "-q", "-m", "legacy-shop as found")

    if setup.get("review_branch"):
        _git(project, "checkout", "-q", "-b", "feature/loyalty")
        shutil.copytree(REVIEW_OVERLAY, project, dirs_exist_ok=True)
        _git(project, "add", "-A")
        _git(project, "commit", "-q", "-m", "loyalty discount, case-insensitive lookup, average order value")

    if setup.get("init", True):
        ferret = project / ".ferret"
        ferret.mkdir()
        (ferret / "config.json").write_text(json.dumps(setup.get("config", {})), encoding="utf8")
        (ferret / "handoff.md").write_text("# Handoff\nStatus: no active session\n", encoding="utf8")
        (ferret / "inbox.md").write_text("# Inbox\n", encoding="utf8")
        (ferret / "learnings.md").write_text("# Learnings\n", encoding="utf8")
        with (project / ".gitignore").open("a", encoding="utf8") as handle:
            handle.write(".ferret/\n")
        _git(project, "commit", "-q", "-am", "ignore .ferret")
    for rel, content in setup.get("files", {}).items():
        target = project / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf8")

    if setup.get("always_on", True):
        (config / ".ferret-always").touch()
    if setup.get("fake_plugins"):
        (config / "plugins").mkdir()
        (config / "plugins" / "installed_plugins.json").write_text(
            json.dumps({"version": 2, "plugins": {"ferret@ferret": [], "other-tool@market": []}}),
            encoding="utf8",
        )
        (config / "settings.json").write_text(
            json.dumps({"enabledPlugins": {"other-tool@market": True}}), encoding="utf8"
        )
        (config / "skills" / "deep-review").mkdir(parents=True)
        (config / "skills" / "deep-review" / "SKILL.md").write_text("---\nname: deep-review\n---\n", encoding="utf8")
    else:
        (config / ".ferret-onboarded").write_text("fixture\n", encoding="utf8")

    baseline = {
        str(p.relative_to(project)).replace("\\", "/"): _read(p)
        for p in project.rglob("*.py")
    }
    return {"project": project, "config": config, "journal": journal, "baseline": baseline}


# ---------------------------------------------------------------- run

def run_scenario(scenario, args, out_dir):
    # realpath: Windows temp paths can use 8.3 short names (USERNA~1), and
    # Claude Code refuses edits under a path spelled that way.
    workdir = Path(os.path.realpath(tempfile.mkdtemp(prefix=f"ferret-live-{scenario['id']}-")))
    record = {"id": scenario["id"], "title": scenario["title"], "workdir": str(workdir)}
    try:
        ctx = prepare(scenario, workdir)
        tools = BASE_TOOLS + scenario.get("extra_tools", [])
        command = [
            args.claude, "--print", "--model", args.model,
            "--plugin-dir", str(ROOT), "--setting-sources", "", "--strict-mcp-config",
            "--output-format", "stream-json", "--verbose", "--include-hook-events",
            "--permission-mode", "acceptEdits",
            "--add-dir", str(ctx["journal"]),
            "--max-budget-usd", str(args.budget_usd),
        ]
        # The compact rule measures the session transcript, so that scenario
        # must let Claude Code write one.
        if not scenario.get("persist"):
            command.append("--no-session-persistence")
        command += ["--allowedTools", *tools]
        env = dict(os.environ, FERRET_CONFIG_DIR=str(ctx["config"]), DEV_JOURNAL=str(ctx["journal"]))
        env.pop("FERRET_COMPACT_AT", None)
        env.pop("FERRET_CONTEXT_WINDOW", None)
        try:
            done = subprocess.run(
                command, cwd=ctx["project"], env=env, input=scenario["prompt"],
                capture_output=True, text=True, encoding="utf8", errors="replace",
                timeout=args.timeout,
            )
            stream, stderr, code = done.stdout, done.stderr, done.returncode
        except subprocess.TimeoutExpired as error:
            stream = error.stdout or ""
            stream = stream.decode("utf8", "replace") if isinstance(stream, bytes) else stream
            stderr, code = f"timed out after {args.timeout}s", -1

        (out_dir / f"{scenario['id']}.stream.jsonl").write_text(stream, encoding="utf8")
        run = parse_stream(stream)
        (out_dir / f"{scenario['id']}.reply.md").write_text("\n\n".join(run["reply"]), encoding="utf8")

        checks = []
        for check in scenario["checks"]:
            try:
                passed, detail = evaluate(check, run, ctx)
            except Exception as error:  # a broken check is a failed check, not a crash
                passed, detail = False, f"{check['type']} raised {error!r}"
            checks.append({"passed": passed, "detail": detail})
        if run["hook_errors"]:
            checks.append({"passed": False, "detail": "hook errors: " + "; ".join(run["hook_errors"])})
        result = run["result"]
        record.update(
            exit_code=code,
            stderr=stderr[-400:],
            cost_usd=result.get("total_cost_usd"),
            turns=result.get("num_turns"),
            stop=result.get("subtype") or result.get("terminal_reason"),
            denials=[d.get("tool_name") for d in result.get("permission_denials") or []],
            agents=run["agents"],
            checks=checks,
            passed=bool(result) and all(c["passed"] for c in checks),
        )
    except Exception as error:
        record.update(passed=False, checks=[{"passed": False, "detail": f"runner error: {error!r}"}])
    finally:
        if not args.keep:
            shutil.rmtree(workdir, ignore_errors=True)
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", default="claude-opus-5-5")
    parser.add_argument("--only", help="comma-separated scenario ids")
    parser.add_argument("--include-slow", action="store_true", help="also run scenarios marked slow")
    parser.add_argument(
        "--budget-usd", type=float, default=8.0,
        help="hard cap per scenario; keep it generous, a tight cap makes the model skip subagents",
    )
    parser.add_argument("--timeout", type=int, default=900, help="seconds per scenario")
    parser.add_argument("--jobs", type=int, default=3)
    parser.add_argument("--keep", action="store_true", help="keep the temp projects")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "evals" / "results" / "live")
    args = parser.parse_args(argv)
    # Windows consoles default to a legacy code page; the report uses → and ✗.
    sys.stdout.reconfigure(encoding="utf8", errors="replace")

    scenarios = load_scenarios()
    if args.list:
        for scenario in scenarios:
            print(f"{scenario['id']:<14} {'(slow) ' if scenario.get('slow') else ''}{scenario['title']}")
        return 0
    if args.only:
        wanted = set(args.only.split(","))
        unknown = wanted - {s["id"] for s in scenarios}
        if unknown:
            parser.error(f"unknown scenario id(s): {', '.join(sorted(unknown))}")
        scenarios = [s for s in scenarios if s["id"] in wanted]
    elif not args.include_slow:
        scenarios = [s for s in scenarios if not s.get("slow")]

    args.claude = shutil.which("claude")
    if not args.claude:
        parser.error("the claude CLI is not on PATH")

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = args.output / stamp
    out_dir.mkdir(parents=True)
    print(f"{len(scenarios)} scenario(s) on {args.model}, cap ${args.budget_usd:.2f} each → {out_dir}")

    records = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        futures = [pool.submit(run_scenario, s, args, out_dir) for s in scenarios]
        for future in concurrent.futures.as_completed(futures):
            record = future.result()
            records.append(record)
            cost = record.get("cost_usd")
            spent = f"${cost:.2f}" if cost is not None else "$?"
            print(f"{'PASS' if record['passed'] else 'FAIL'}  {record['id']:<14} {spent}")
            for check in record["checks"]:
                if not check["passed"]:
                    print(f"      ✗ {check['detail']}")
            sys.stdout.flush()

    order = {s["id"]: i for i, s in enumerate(scenarios)}
    records.sort(key=lambda r: order[r["id"]])
    total = sum(r.get("cost_usd") or 0 for r in records)
    summary = {"model": args.model, "stamp": stamp, "total_cost_usd": round(total, 4), "scenarios": records}
    (out_dir / "results.json").write_text(json.dumps(summary, indent=2), encoding="utf8")
    passed = sum(1 for r in records if r["passed"])
    print(f"\n{passed}/{len(records)} passed, ${total:.2f} total. Details: {out_dir / 'results.json'}")
    return 0 if passed == len(records) else 1


if __name__ == "__main__":
    sys.exit(main())
