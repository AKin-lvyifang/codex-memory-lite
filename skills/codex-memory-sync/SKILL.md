---
name: codex-memory-sync
description: Use when a long-running project needs its structured memory updated after a phase change, major progress, context growth, or before ending a thread.
---

# Codex Memory Sync

Update `.codex-memory/` after meaningful progress so current state, stable rules, task context, and history stay separated.

## When To Use

- A phase of work just finished
- The task changed direction
- The thread is about to end
- Context is getting long
- The user explicitly asks to update memory, current, archive, or task context

## Routing Rules

- current effective state -> `current.md`
- repeated stable rules -> `spec/`
- active task state -> `tasks/active/<task>/`
- historical process -> `archive/YYYY-MM/YYYY-MM-DD-<topic>.md`

## File Update Rules

- `current.md` must be updated by section, not turned back into a dated log
- `decisions.md` only records confirmed decisions
- `refs.md` only records references that will still matter later
- archive entries must be created from this skill's archive template
- do not delete frozen legacy handoff files

## Validation

Verify:

- `current.md` still contains its six required sections
- any active task still has all three task files
- any new archive file contains the archive template marker and required sections

## Report Back

- updated files
- what stayed in current
- what moved into archive
- any new decisions or refs
- validation result
