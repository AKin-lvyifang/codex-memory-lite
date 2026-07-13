import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


HOOK = Path(__file__).resolve().parents[3] / "ai" / "hooks" / "codex-memory-bootstrap-first-prompt.js"


class BootstrapRouterTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(
            prefix=".codex-memory-router-",
            dir=Path.home(),
        )
        self.base = Path(self.temporary.name).resolve()
        self.config_path = self.base / "config.json"
        self.config_path.write_text(
            json.dumps(
                {
                    "enabled": True,
                    "mode": "test",
                    "project_roots": [],
                    "storage": {"failed_transaction_limit": 3},
                }
            ),
            encoding="utf-8",
        )

    def tearDown(self):
        self.temporary.cleanup()

    def run_hook(self, root, session_id):
        event = {
            "hook_event_name": "UserPromptSubmit",
            "cwd": str(root),
            "session_id": session_id,
        }
        env = dict(os.environ)
        env["CODEX_MEMORY_CONFIG"] = str(self.config_path)
        return subprocess.run(
            ["node", str(HOOK)],
            input=json.dumps(event),
            text=True,
            capture_output=True,
            env=env,
            timeout=30,
            check=True,
        )

    def test_non_echoink_project_is_registered_and_bootstrapped(self):
        root = self.base / "normal-project"
        root.mkdir()
        (root / "package.json").write_text("{}\n", encoding="utf-8")

        result = self.run_hook(root, "v2-route")

        output = json.loads(result.stdout)
        context = output["hookSpecificOutput"]["additionalContext"]
        self.assertIn("initialized automatically", context)
        self.assertTrue((root / ".codex-memory" / "manifest.json").is_file())
        self.assertFalse((root / "AGENTS.md").exists())
        config = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertEqual(config["project_roots"], [str(root)])

        second = self.run_hook(root, "v2-route-again")
        self.assertEqual(second.stdout, "")

    def test_explicitly_excluded_project_is_not_registered(self):
        root = self.base / "legacy-project"
        root.mkdir()
        (root / "package.json").write_text("{}\n", encoding="utf-8")
        config = json.loads(self.config_path.read_text(encoding="utf-8"))
        config["excluded_project_roots"] = [
            {"path": str(root), "reason": "kept on a legacy workflow"}
        ]
        self.config_path.write_text(json.dumps(config), encoding="utf-8")

        result = self.run_hook(root, "v1-route")

        self.assertEqual(result.stdout, "")
        self.assertFalse((root / ".codex-memory").exists())
        config = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertEqual(config["project_roots"], [])

    def test_sensitive_system_directory_is_never_registered(self):
        result = self.run_hook(Path("/etc"), "sensitive-route")

        self.assertEqual(result.stdout, "")
        config = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertEqual(config["project_roots"], [])

    def test_partial_bootstrap_failure_retries_on_next_prompt(self):
        root = self.base / "partial-project"
        memory = root / ".codex-memory"
        memory.mkdir(parents=True)
        (root / "package.json").write_text("{}\n", encoding="utf-8")
        (memory / "manifest.json").write_text("not-json\n", encoding="utf-8")

        first = self.run_hook(root, "partial-first")
        first_context = json.loads(first.stdout)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("initialization failed", first_context)
        config = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertEqual(config["project_roots"], [str(root)])

        (memory / "manifest.json").unlink()
        second = self.run_hook(root, "partial-second")
        second_context = json.loads(second.stdout)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("initialized automatically", second_context)
        self.assertIn("Initialization action: migrate-v1", second_context)
        manifest = json.loads((memory / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["schema_version"], 2)


if __name__ == "__main__":
    unittest.main()
