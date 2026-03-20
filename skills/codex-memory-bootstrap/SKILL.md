---
name: codex-memory-bootstrap
description: Use when the user says "Initialize this project's memory", or when a project enters long-running, complex collaboration, or cross-session continuation and needs project-level `.codex-memory/` scaffolding.
---

# Codex Memory Bootstrap

Initialize a structured project memory layer for long-running collaboration so work no longer depends on a single handoff file.

## Pre-Write Checks

Before creating `.codex-memory/`, first define an absolute path variable: `PROJECT_ROOT`.

- `PROJECT_ROOT` must be the project root for the current session
- Do not treat `~`, `/`, `~/.config/opencode`, `~/.codex`, a skills directory, or a config directory as the project root
- If the current directory does not look like a project directory, or the project root is still unclear, stop and confirm it before creating anything
- All directories and files must be created under `{PROJECT_ROOT}/.codex-memory/`
- Do not treat the bare relative path `.codex-memory/` as the final target path

## When To Use

Use this when any of the following is true:
- The user explicitly says "Initialize this project's memory"
- The work will continue across multiple sessions
- The work spans multiple files, pages, or topics
- The project already has handoff, rule, or history buildup
- The current thread is visibly getting bloated

## Natural Trigger Phrases

- Initialize this project's memory

## Goal

Create the smallest usable `.codex-memory/` structure and establish or update the project-level `AGENTS.md`.

Specifically:
- if the project does not have `AGENTS.md`, create the full file from `templates/project-agents.md`
- if the project already has `AGENTS.md`, update only the managed `CODEX-MEMORY` block
- after writing, always run validation so `AGENTS.md` is confirmed against the full template or the managed-block template

## Workflow

1. Check whether `.codex-memory/` already exists at the project root.
2. If it does not exist, create the following structure:

```text
.codex-memory/
├── current.md
├── spec/
│   ├── index.md
│   ├── design-rules.md
│   ├── frontend-design-standards.md
│   ├── frontend-page-workflow.md
│   ├── component-reuse.md
│   └── workflow-rules.md
├── tasks/
│   ├── index.md
│   ├── active/
│   └── archive/
└── archive/
```

3. Write the standard templates into those files.
4. Handle project-level `AGENTS.md`:
   - if `AGENTS.md` does not exist, create the full file from `templates/project-agents.md`
   - if `AGENTS.md` already exists, only append or update the managed `CODEX-MEMORY` block defined by `templates/project-agents-block.md`
5. Run validation:
   - freshly created full file: `python3 scripts/validate_project_agents.py --project-root <project-root> --mode create`
   - managed-block update on an existing file: `python3 scripts/validate_project_agents.py --project-root <project-root> --mode update`
6. If the project contains an older handoff file such as `codex-handoff.md`, record it as "pending migration", but do not delete it automatically.
7. Report the initialization result:
   - the `PROJECT_ROOT` used this time
   - created directories
   - created files
   - whether `AGENTS.md` was created or updated
   - `AGENTS.md` validation result
   - whether an old handoff was found
   - whether migration should be recommended next

## Templates And Validation

- full project-level `AGENTS.md` template: `templates/project-agents.md`
- managed block template: `templates/project-agents-block.md`
- validation script: `scripts/validate_project_agents.py`

Validation requirements:
- `AGENTS.md` must exist
- `CODEX-MEMORY:START / END` must each appear exactly once
- if the file was newly created, it must match `templates/project-agents.md`
- if the file already existed, its managed block must match `templates/project-agents-block.md`

## Remind The User After Initialization

- This project now has `.codex-memory/` enabled
- Future sessions should read `current.md` first
- Project-level `AGENTS.md` was created from template or updated by managed block and passed validation
- If an old handoff exists, migrate it instead of maintaining both systems in parallel

## Constraints

- Do not automatically delete old handoff files
- Do not migrate legacy content during bootstrap without an explicit migration step
- Do not dump historical process notes straight into `current.md`
- Do not freely improvise a new project-level `AGENTS.md`; use `templates/project-agents.md`
- Do not skip validation after writing `AGENTS.md`
- Do not create any `.codex-memory/` directories or files before `PROJECT_ROOT` is confirmed
