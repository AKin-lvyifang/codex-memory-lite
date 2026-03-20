from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = SKILL_ROOT / "scripts" / "validate_project_agents.py"
FULL_TEMPLATE_PATH = SKILL_ROOT / "templates" / "project-agents.md"
BLOCK_TEMPLATE_PATH = SKILL_ROOT / "templates" / "project-agents-block.md"


class ValidateProjectAgentsTests(unittest.TestCase):
    def run_validator(self, agents_text: str, mode: str = "auto") -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            (project_root / "AGENTS.md").write_text(agents_text, encoding="utf-8")

            return subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "--project-root",
                    str(project_root),
                    "--mode",
                    mode,
                ],
                capture_output=True,
                text=True,
                check=False,
            )

    def test_create_mode_accepts_exact_full_template(self) -> None:
        result = self.run_validator(FULL_TEMPLATE_PATH.read_text(encoding="utf-8"), mode="create")

        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)

    def test_update_mode_accepts_custom_wrapper_with_managed_block(self) -> None:
        block = BLOCK_TEMPLATE_PATH.read_text(encoding="utf-8").strip()
        custom_agents = (
            "# Project Instructions\n\n"
            "## Custom Rules\n\n"
            "- keep my existing project notes here\n\n"
            f"{block}\n"
        )

        result = self.run_validator(custom_agents, mode="update")

        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)

    def test_update_mode_rejects_modified_managed_block(self) -> None:
        broken_block = BLOCK_TEMPLATE_PATH.read_text(encoding="utf-8").replace(
            "## current 规则", "## current rules", 1
        )
        custom_agents = "# Project Instructions\n\n" + broken_block

        result = self.run_validator(custom_agents, mode="update")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("managed CODEX-MEMORY block", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
