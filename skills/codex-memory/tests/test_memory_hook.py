import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
HOOK = SKILL_ROOT / "scripts" / "memory-hook.js"


class MemoryHookTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        memory = self.root / ".codex-memory"
        (memory / "spec").mkdir(parents=True)
        (memory / "tasks").mkdir(parents=True)
        (memory / "archive").mkdir(parents=True)
        (memory / "current.md").write_text("# Current\n\n- Original.\n", encoding="utf-8")
        (memory / "spec" / "index.md").write_text("# Spec\n", encoding="utf-8")
        (memory / "tasks" / "index.md").write_text("# Tasks\n", encoding="utf-8")
        self.config_path = self.root / "memory-config.json"
        self.write_config()

    def tearDown(self):
        self.temporary.cleanup()

    def write_config(self):
        self.config_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "enabled": True,
                    "mode": "test",
                    "project_roots": [str(self.root)],
                    "curator": {
                        "preferred_model": "gpt-5.6-sol",
                        "reasoning_effort": "low",
                        "fallback_model_policy": "inherit",
                        "timeout_seconds": 30,
                    },
                    "sync": {
                        "active_task_event_threshold": 99,
                        "max_pending_age_seconds": 99999,
                        "max_event_chars": 12000,
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )

    def add_active_task(self):
        task = self.root / ".codex-memory" / "tasks" / "active" / "test-task"
        task.mkdir(parents=True, exist_ok=True)
        (task / "brief.md").write_text("# Brief\n", encoding="utf-8")
        (task / "decisions.md").write_text("# Decisions\n", encoding="utf-8")
        (task / "refs.md").write_text("# Refs\n", encoding="utf-8")

    def run_hook(self, event, extra_env=None):
        env = os.environ.copy()
        env["CODEX_MEMORY_CONFIG"] = str(self.config_path)
        env.pop("CODEX_MEMORY_INTERNAL", None)
        if extra_env:
            env.update(extra_env)
        result = subprocess.run(
            ["node", str(HOOK)],
            cwd=self.root,
            input=json.dumps(event),
            text=True,
            capture_output=True,
            env=env,
            timeout=60,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout) if result.stdout.strip() else None

    def prompt_event(self, session="session-1", turn="turn-1", prompt="hello"):
        return {
            "session_id": session,
            "turn_id": turn,
            "cwd": str(self.root),
            "hook_event_name": "UserPromptSubmit",
            "model": "gpt-5.6-sol",
            "permission_mode": "dontAsk",
            "prompt": prompt,
        }

    def stop_event(self, session="session-1", turn="turn-1", answer="done"):
        return {
            "session_id": session,
            "turn_id": turn,
            "cwd": str(self.root),
            "hook_event_name": "Stop",
            "model": "gpt-5.6-sol",
            "permission_mode": "dontAsk",
            "stop_hook_active": False,
            "last_assistant_message": answer,
        }

    def test_prompt_redacts_secret_before_pending(self):
        fake_secret = "sk-" + "abcdefghijklmnopqrstuvwxyz123456"
        self.run_hook(self.prompt_event(prompt=f"token is {fake_secret}"))
        pending = next((self.root / ".codex-memory" / ".runtime" / "sessions").glob("*/pending.jsonl"))
        text = pending.read_text(encoding="utf-8")
        self.assertIn("[REDACTED_OPENAI_KEY]", text)
        self.assertNotIn(fake_secret, text)

    def test_short_turn_without_active_task_is_discarded(self):
        self.run_hook(self.prompt_event())
        self.run_hook(self.stop_event())
        pending_files = list(
            (self.root / ".codex-memory" / ".runtime" / "sessions").glob("*/pending.jsonl")
        )
        self.assertEqual(pending_files, [])
        self.assertEqual(
            (self.root / ".codex-memory" / "current.md").read_text(encoding="utf-8"),
            "# Current\n\n- Original.\n",
        )

    def test_english_remember_signal_triggers_sync(self):
        self.run_hook(
            self.prompt_event(
                session="session-remember",
                turn="turn-remember",
                prompt="Please remember this decision for future sessions.",
            )
        )
        fixture = self.root / "remember-no-op.json"
        fixture.write_text(
            json.dumps(
                {
                    "outcome": "no-op",
                    "summary": "Signal routing test.",
                    "updated_categories": [],
                    "candidates": [
                        {
                            "candidate_id": "c1",
                            "category": "skip",
                            "disposition": "skip",
                            "target": None,
                            "source_event_ids": ["session-remember:1", "session-remember:2"],
                            "reason": "Fixture validates routing only.",
                        }
                    ],
                    "files": [],
                    "unresolved": [],
                }
            ),
            encoding="utf-8",
        )
        output = self.run_hook(
            self.stop_event(session="session-remember", turn="turn-remember"),
            {"CODEX_MEMORY_CURATOR_FIXTURE": str(fixture)},
        )
        self.assertEqual(output, {"continue": True})
        pending = (
            self.root
            / ".codex-memory"
            / ".runtime"
            / "sessions"
            / "session-remember"
            / "pending.jsonl"
        )
        self.assertFalse(pending.exists())

    def test_forced_active_task_no_op_runs_full_hook_transaction(self):
        self.add_active_task()
        self.run_hook(self.prompt_event(session="session-noop", turn="turn-noop"))
        fixture = self.root / "no-op-result.json"
        fixture.write_text(
            json.dumps(
                {
                    "outcome": "no-op",
                    "summary": "Ordinary test turn has no durable value.",
                    "updated_categories": [],
                    "candidates": [
                        {
                            "candidate_id": "c1",
                            "category": "skip",
                            "disposition": "skip",
                            "target": None,
                            "source_event_ids": ["session-noop:1", "session-noop:2"],
                            "reason": "Temporary smoke test.",
                        }
                    ],
                    "files": [],
                    "unresolved": [],
                }
            ),
            encoding="utf-8",
        )
        output = self.run_hook(
            self.stop_event(session="session-noop", turn="turn-noop"),
            {
                "CODEX_MEMORY_FORCE_SYNC": "1",
                "CODEX_MEMORY_CURATOR_FIXTURE": str(fixture),
            },
        )
        self.assertEqual(output, {"continue": True})
        manifest = json.loads(
            (self.root / ".codex-memory" / "manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["memory_revision"], 0)
        pending = self.root / ".codex-memory" / ".runtime" / "sessions" / "session-noop" / "pending.jsonl"
        self.assertFalse(pending.exists())

    def test_forced_write_uses_validated_fixture_and_reports_category(self):
        self.add_active_task()
        self.run_hook(self.prompt_event(session="session-write", turn="turn-write"))
        fixture = self.root / "write-result.json"
        new_content = "# Current\n\n- Original.\n- Hook write verified.\n"
        fixture.write_text(
            json.dumps(
                {
                    "outcome": "write",
                    "summary": "Recorded verified progress.",
                    "updated_categories": ["progress"],
                    "candidates": [
                        {
                            "candidate_id": "c1",
                            "category": "progress",
                            "disposition": "write",
                            "target": "current.md",
                            "source_event_ids": ["session-write:1", "session-write:2"],
                            "reason": "Needed by the next session.",
                        }
                    ],
                    "files": [{"path": "current.md", "content": new_content}],
                    "unresolved": [],
                }
            ),
            encoding="utf-8",
        )
        output = self.run_hook(
            self.stop_event(session="session-write", turn="turn-write"),
            {
                "CODEX_MEMORY_FORCE_SYNC": "1",
                "CODEX_MEMORY_CURATOR_FIXTURE": str(fixture),
            },
        )
        self.assertEqual(output["continue"], True)
        self.assertIn("已记录：任务进度", output["systemMessage"])
        self.assertEqual(
            (self.root / ".codex-memory" / "current.md").read_text(encoding="utf-8"),
            new_content,
        )

    def test_active_task_plain_turn_waits_without_calling_curator(self):
        self.add_active_task()
        self.run_hook(self.prompt_event(session="session-wait", turn="turn-wait"))
        output = self.run_hook(
            self.stop_event(session="session-wait", turn="turn-wait")
        )
        self.assertEqual(output, {"continue": True})
        pending = self.root / ".codex-memory" / ".runtime" / "sessions" / "session-wait" / "pending.jsonl"
        self.assertEqual(len(pending.read_text(encoding="utf-8").splitlines()), 2)
        self.assertEqual(
            list((self.root / ".codex-memory" / ".runtime" / "transactions").glob("*")),
            [],
        )

    def test_stop_hook_active_does_not_create_events(self):
        event = self.stop_event(session="session-recursion", turn="turn-recursion")
        event["stop_hook_active"] = True
        output = self.run_hook(event)
        self.assertEqual(output, {"continue": True})
        session = self.root / ".codex-memory" / ".runtime" / "sessions" / "session-recursion"
        self.assertFalse((session / "pending.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
