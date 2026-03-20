---
name: codex-memory-task-init
description: Use when the user says "This is a long-running task. Record it." or "Create task memory for this long-running task", or when a new long-running task needs separate tracking across sessions.
---

# Codex Memory Task Init

## Pre-Write Checks

Before creating the task directory, first define an absolute path variable: `PROJECT_ROOT`.

- `PROJECT_ROOT` must be the project root for the current session
- Do not treat `~`, `/`, `~/.config/opencode`, `~/.codex`, a skills directory, or a config directory as the project root
- If the current directory looks like a home directory or a config directory, or if the project root is still unclear, stop and confirm it first
- All task directories and files must be created under `{PROJECT_ROOT}/.codex-memory/tasks/active/<task-slug>/`
- Do not treat the bare relative path `.codex-memory/tasks/...` as the final target path

## When To Use

Use this when any of the following is true:
- The user explicitly says "This is a long-running task. Record it."
- The user explicitly says "Create task memory for this long-running task"
- The task will continue across multiple sessions
- The task needs its own target, decisions, and reference tracking
- The task no longer fits cleanly inside `current.md`

## Natural Trigger Phrases

- This is a long-running task. Record it.
- Create task memory for this long-running task

## Goal

Create the standard task memory skeleton under `.codex-memory/tasks/active/<task-slug>/`.

## Required Output

The actual target path must be:

```text
{PROJECT_ROOT}/.codex-memory/tasks/active/<task-slug>/
```

The structure below is shown only as the project-relative layout:

Create:

```text
.codex-memory/tasks/active/<task-slug>/
├── brief.md
├── decisions.md
└── refs.md
```

Also update:

```text
.codex-memory/tasks/index.md
```

## Rules

1. Confirm `PROJECT_ROOT` first; all actual write paths must use absolute `{PROJECT_ROOT}/.codex-memory/...` paths.
2. `<task-slug>` should be short, stable, and readable, without a date.
3. `brief.md`, `decisions.md`, and `refs.md` must always be created together.
4. All files must be generated from this skill's built-in templates.
5. If the task directory already exists, do not rebuild it; only fill gaps and validate.
6. When updating `tasks/index.md`, add the task entry and a one-line summary.
7. Run a structure validation after writing; if validation fails, stop and report it.

## Report Back

- the `PROJECT_ROOT` used this time
- the task slug
- created files
- backfilled files
- `tasks/index.md` update result
- validation result

## Constraints

- Do not create any `.codex-memory/tasks/` directories or files before `PROJECT_ROOT` is confirmed
- If the target path is not `{PROJECT_ROOT}/.codex-memory/tasks/active/<task-slug>/`, stop immediately and do not continue
