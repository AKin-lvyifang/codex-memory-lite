#!/usr/bin/env python3
"""Validate a project-level AGENTS.md created or updated by codex-memory-bootstrap."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


FULL_TEMPLATE_MARKER = "<!-- codex-memory:template=project-agents:v1 -->"
BLOCK_START = "<!-- CODEX-MEMORY:START -->"
BLOCK_END = "<!-- CODEX-MEMORY:END -->"


def normalize_text(text: str) -> str:
    normalized = text.replace("\r\n", "\n")
    if not normalized.endswith("\n"):
        normalized += "\n"
    return normalized


def load_template(skill_root: Path, name: str) -> str:
    return normalize_text((skill_root / "templates" / name).read_text(encoding="utf-8"))


def extract_managed_block(text: str, errors: list[str]) -> str | None:
    start_count = text.count(BLOCK_START)
    end_count = text.count(BLOCK_END)

    if start_count != 1:
        errors.append(f"expected exactly 1 '{BLOCK_START}', found {start_count}")
    if end_count != 1:
        errors.append(f"expected exactly 1 '{BLOCK_END}', found {end_count}")
    if errors:
        return None

    start_index = text.index(BLOCK_START)
    end_index = text.index(BLOCK_END) + len(BLOCK_END)
    if start_index >= end_index:
        errors.append("managed CODEX-MEMORY block markers are out of order")
        return None

    return text[start_index:end_index]


def validate_create_mode(agents_text: str, full_template_text: str, errors: list[str]) -> None:
    if FULL_TEMPLATE_MARKER not in agents_text:
        errors.append(f"missing full template marker: {FULL_TEMPLATE_MARKER}")
    if agents_text != full_template_text:
        errors.append("AGENTS.md does not exactly match templates/project-agents.md")


def validate_update_mode(agents_text: str, expected_block_text: str, errors: list[str]) -> None:
    block_text = extract_managed_block(agents_text, errors)
    if block_text is None:
        return

    if normalize_text(block_text) != expected_block_text:
        errors.append("managed CODEX-MEMORY block does not match templates/project-agents-block.md")


def detect_mode(agents_text: str, requested_mode: str) -> str:
    if requested_mode != "auto":
        return requested_mode
    return "create" if FULL_TEMPLATE_MARKER in agents_text else "update"


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate project-level AGENTS.md")
    parser.add_argument("--project-root", required=True, help="Project root containing AGENTS.md")
    parser.add_argument(
        "--mode",
        choices=("auto", "create", "update"),
        default="auto",
        help="Validation mode. Use 'create' for freshly generated AGENTS.md, 'update' for managed-block refreshes.",
    )
    args = parser.parse_args()

    project_root = Path(args.project_root).expanduser().resolve()
    agents_path = project_root / "AGENTS.md"
    skill_root = Path(__file__).resolve().parents[1]

    if not agents_path.is_file():
        print(f"Validation failed:\n- missing file: {agents_path}")
        return 1

    agents_text = normalize_text(agents_path.read_text(encoding="utf-8"))
    full_template_text = load_template(skill_root, "project-agents.md")
    expected_block_text = load_template(skill_root, "project-agents-block.md")

    mode = detect_mode(agents_text, args.mode)
    errors: list[str] = []

    validate_update_mode(agents_text, expected_block_text, errors)
    if mode == "create":
        validate_create_mode(agents_text, full_template_text, errors)

    if errors:
        print("Validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"AGENTS validation passed (mode: {mode}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
