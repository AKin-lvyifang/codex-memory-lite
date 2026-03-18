---
name: codex-memory-task-init
description: Use when a new long-running project task needs its own structured memory folder with brief, decisions, and refs files.
---

# Codex Memory Task Init

Create a task-level memory folder under `.codex-memory/tasks/active/` and populate the standard task trio from templates.

## When To Use

- The work will continue across multiple sessions
- The work needs its own target, decisions, and reference tracking
- The work no longer fits cleanly inside `current.md` alone

## Required Output

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

- Use a stable, readable slug
- Always create all three files together
- Always use the templates in this skill's `templates/` directory
- If the task folder already exists, fill gaps and validate instead of rebuilding
- Add the task to `tasks/index.md` with a one-line summary

## Validation

Verify:

- the task directory exists
- `brief.md`, `decisions.md`, and `refs.md` all exist
- each file contains the correct template marker
- `tasks/index.md` lists the task

## Report Back

- task slug
- created files
- updated index status
- validation result
