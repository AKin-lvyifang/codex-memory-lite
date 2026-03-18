---
name: codex-memory-bootstrap
description: Use when a project enters long-running, multi-file, multi-topic, or cross-session work and needs a structured memory directory with automatic legacy handoff migration.
---

# Codex Memory Bootstrap

Initialize project-level `.codex-memory/`, write standard template files, inject the managed project `AGENTS.md` block, migrate any existing legacy handoff into the new structure, freeze the legacy handoff, and validate the result.

## When To Use

- A project will continue across multiple sessions
- Work spans multiple files, pages, or topics
- Existing handoff / rules / history are already piling up
- Context is visibly getting noisy or bloated

## Required Outputs

Create this project structure if missing:

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

## Legacy Handoff Migration

Detect legacy handoff sources in this order:

1. `codex-handoff.md`
2. `handoff.md`
3. `project-handoff.md`

If found, migrate automatically without asking again:

- current effective state -> `current.md`
- stable repeated rules -> `spec/`
- still-active large workstreams -> `tasks/active/<task>/`
- historical progress and obsolete state -> `archive/`

Freeze the legacy handoff after migration:

- prepend a short migration notice
- point future readers to `.codex-memory/current.md`
- do not delete the legacy file

## Template Rules

- All files must be created from this skill's `templates/` directory
- Do not improvise file structure
- Do not skip files from the required output set
- If files already exist, fill gaps and validate instead of overwriting blindly

## Project AGENTS Block

- If the project has no `AGENTS.md`, create one and insert the managed block from `templates/project-agents-block.md`
- If it already has one, update only the managed `CODEX-MEMORY` block

## Validation

After writing, verify:

- required directories exist
- required files exist
- each standard file contains the expected template marker
- `design-rules.md` references `frontend-design-standards.md` and `frontend-page-workflow.md`
- migrated `current.md` is not empty
- legacy handoff is frozen and no longer the main entry point

## Report Back

- created directories
- created files
- migrated legacy sources
- active tasks created from migration
- validation result
