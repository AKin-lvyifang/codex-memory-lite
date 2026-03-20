#!/usr/bin/env python3
"""Validate the global memory layer and one project's linkage to it."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


REQUIRED_CURRENT_HEADINGS = [
    "# 当前主题",
    "# 范围 / 不做",
    "# 当前状态",
    "# 稳定约束",
    "# 关键索引",
    "# 风险 / 下一步",
]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def validate_required_paths(global_root: Path, errors: list[str]) -> None:
    required_dirs = [
        global_root / "spec",
        global_root / "topics" / "active",
        global_root / "topics" / "archive",
        global_root / "projects",
        global_root / "archive",
    ]
    required_files = [
        global_root / "current.md",
        global_root / "spec" / "index.md",
        global_root / "spec" / "promotion-rules.md",
        global_root / "projects" / "index.md",
        global_root / "topics" / "index.md",
    ]

    for directory in required_dirs:
        if not directory.is_dir():
            errors.append(f"missing directory: {directory}")

    for file_path in required_files:
        if not file_path.is_file():
            errors.append(f"missing file: {file_path}")


def validate_current(global_root: Path, errors: list[str]) -> None:
    current_path = global_root / "current.md"
    if not current_path.is_file():
        return

    current_text = read_text(current_path)
    for heading in REQUIRED_CURRENT_HEADINGS:
        if heading not in current_text:
            errors.append(f"global current missing heading: {heading}")


def parse_project_topics(projects_index_text: str, project_root: str) -> list[str]:
    topics: list[str] = []
    for line in projects_index_text.splitlines():
        if project_root not in line or not line.startswith("|"):
            continue
        columns = [part.strip() for part in line.strip().strip("|").split("|")]
        if len(columns) < 5:
            continue
        raw_topics = columns[2]
        if not raw_topics or raw_topics == "暂无":
            return []
        topics = [topic.strip() for topic in raw_topics.split(",") if topic.strip()]
        return topics
    return topics


def validate_project_link(
    global_root: Path,
    project_root: Path | None,
    errors: list[str],
    warnings: list[str],
) -> None:
    if project_root is None:
        return

    projects_index = global_root / "projects" / "index.md"
    if not projects_index.is_file():
        return

    projects_text = read_text(projects_index)
    project_root_str = str(project_root)
    if project_root_str not in projects_text:
        errors.append(f"project path not found in projects index: {project_root_str}")
        return

    topics = parse_project_topics(projects_text, project_root_str)
    if not topics:
        warnings.append("project has no linked global topic")
        return

    for topic in topics:
        active_dir = global_root / "topics" / "active" / topic
        archive_dir = global_root / "topics" / "archive" / topic
        if not active_dir.is_dir() and not archive_dir.is_dir():
            errors.append(f"linked topic missing directory: {topic}")


def validate_no_project_leak(
    global_root: Path,
    project_root: Path | None,
    errors: list[str],
) -> None:
    if project_root is None:
        return

    project_root_str = str(project_root)
    leak_roots = [
        global_root / "current.md",
        global_root / "spec",
    ]

    for leak_root in leak_roots:
        if leak_root.is_file():
            files = [leak_root]
        else:
            files = sorted(leak_root.rglob("*.md"))

        for file_path in files:
            text = read_text(file_path)
            if project_root_str in text:
                errors.append(
                    f"project-specific path leaked into global stable file: {file_path}"
                )


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate global memory structure.")
    default_codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    parser.add_argument(
        "--global-root",
        default=str(default_codex_home / "memory" / "global"),
        help="Global memory root directory",
    )
    parser.add_argument(
        "--project-root",
        help="Project root to validate against projects/index.md",
    )
    args = parser.parse_args()

    global_root = Path(args.global_root).expanduser().resolve()
    project_root = (
        Path(args.project_root).expanduser().resolve()
        if args.project_root
        else None
    )

    errors: list[str] = []
    warnings: list[str] = []

    validate_required_paths(global_root, errors)
    validate_current(global_root, errors)
    validate_project_link(global_root, project_root, errors, warnings)
    validate_no_project_leak(global_root, project_root, errors)

    if errors:
        print("Validation failed:")
        for error in errors:
            print(f"- {error}")
        if warnings:
            print("Warnings:")
            for warning in warnings:
                print(f"- {warning}")
        return 1

    print("Global memory validation passed.")
    if warnings:
        print("Warnings:")
        for warning in warnings:
            print(f"- {warning}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
