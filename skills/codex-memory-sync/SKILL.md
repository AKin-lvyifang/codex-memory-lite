---
name: codex-memory-sync
description: Use when the user says "Sync the current project memory", or when a long-running project changes phase, grows in context, or is about to end a thread.
---

# Codex Memory Sync

When a task runs long, changes phase, approaches the end of a thread, or becomes context-heavy, sync the effective information from the session back into the **project-local `.codex-memory/`**.

**Important**: Always use the project-local `.codex-memory/` (for example, `{PROJECT_ROOT}/.codex-memory/`), not the global `~/.codex-memory/`.

## Pre-Write Checks

Before any read, create, or write action, first define an absolute path variable: `PROJECT_ROOT`.

- `PROJECT_ROOT` must be the project root for the current session
- Do not treat `~`, `/`, `~/.config/opencode`, `~/.codex`, a skills directory, or a config directory as the project root
- If the current directory looks like a home directory or a config directory, or if the project root is still unclear, stop and confirm it first
- All memory paths must be written as absolute paths: `{PROJECT_ROOT}/.codex-memory/...`
- Do not treat the bare relative path `.codex-memory/...` as the final write target

## When To Use

Use this when any of the following is true:
- The user explicitly says "Sync the current project memory"
- A phase of work just finished
- The task changed direction
- The current thread is about to end
- Context has clearly grown large
- The user explicitly asks to update `current`, write `archive`, or promote a rule

## Natural Trigger Phrases

- Sync the current project memory

## Goal

Route information from the current session into the correct destination:
- current effective state -> `current.md`
- long-lived stable rules -> `spec/`
- active task context -> `tasks/active/<task>/`
- historical process -> `archive/`

## Workflow

1. Read:
   - `.codex-memory/current.md`
   - `.codex-memory/spec/index.md`
   - if an active task exists, also read its `brief.md`
2. Extract information from the current session and classify it with the following rules:

### A. current
Only write information to `current.md` if it is still currently effective:
- current goal
- scope / not doing
- current status
- stable constraints summary
- key index
- risks / next steps

### B. spec
Promote a rule to `spec/` if any of the following is true:
- it stays valid across more than two sessions
- it appears repeatedly in more than one topic
- losing it would create obvious rework

### C. tasks
If the current work belongs to an active task, sync:
- `brief.md`
- `decisions.md`
- `refs.md`

### D. archive
Write this round's process notes, old goals, one-off tweaks, and historical decisions into the monthly archive file

3. Update rules:
- `current.md` must be overwritten by section, not extended into a dated running log
- historical information goes into `archive/`, not back into `current.md`
- active tasks should keep only information that is still ongoing
- do not dump every node ID into `current`; keep only the key few
- if the target path is not `{PROJECT_ROOT}/.codex-memory/`, stop immediately and do not keep writing

## Report Back

After sync finishes, report:
- the `PROJECT_ROOT` used this time
- updated files
- what went into `current`
- what went into `archive`
- which rules were promoted into `spec`
- whether any conflicts or pending confirmations were found

## Constraints

- Do not delete old archive records on your own
- Do not mix "current state" and "historical process" back together
- Do not create task directories unless they are actually needed
- Do not create any `.codex-memory/` directories or files before `PROJECT_ROOT` is confirmed
