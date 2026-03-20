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

Create the smallest usable `.codex-memory/` structure and establish the managed project-level memory block inside `AGENTS.md`.

## Workflow

1. Check whether `.codex-memory/` already exists at the project root.
2. If it does not exist, create the following structure:

```text
.codex-memory/
├── current.md
├── spec/
│   ├── index.md
│   ├── design-rules.md
│   ├── component-reuse.md
│   └── workflow-rules.md
├── tasks/
│   ├── index.md
│   ├── active/
│   └── archive/
└── archive/
```

3. Write the standard templates into those files.
4. If `AGENTS.md` does not exist at the project root, create a project-level `AGENTS.md`.
5. If `AGENTS.md` already exists, only append or update the managed "project-level context management" block without disturbing the user's other content.
6. If the project contains an older handoff file such as `codex-handoff.md`, record it as "pending migration", but do not delete it automatically.
7. Report the initialization result:
   - the `PROJECT_ROOT` used this time
   - created directories
   - created files
   - whether an old handoff was found
   - whether migration should be recommended next

## Remind The User After Initialization

- This project now has `.codex-memory/` enabled
- Future sessions should read `current.md` first
- If an old handoff exists, migrate it instead of maintaining both systems in parallel

## Constraints

- Do not automatically delete old handoff files
- Do not migrate legacy content during bootstrap without an explicit migration step
- Do not dump historical process notes straight into `current.md`
- Do not create any `.codex-memory/` directories or files before `PROJECT_ROOT` is confirmed
