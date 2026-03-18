# Project `AGENTS.md` Snippet

Use this block inside a project-level `AGENTS.md`.

```md
<!-- CODEX-MEMORY:START -->
## Project Context Management

- This project uses `.codex-memory/` as its structured memory directory.
- Do not keep appending to `codex-handoff.md` as the main handoff file.
- On a new session, read in this order:
  1. `.codex-memory/current.md`
  2. `.codex-memory/spec/index.md`
  3. if there is an active task, `.codex-memory/tasks/index.md` and the task `brief.md`
- Do not load `.codex-memory/archive/` by default.
- If there is a frozen legacy handoff, treat it as migration history only, not as the main startup file.

## `current.md` Rules

- `current.md` keeps only current effective information.
- It should be overwritten, not continuously appended.
- Recommended sections:
  - current goal
  - scope / not doing
  - current status
  - stable constraints
  - key references
  - risks / next step

## `spec/` Rules

- Put stable long-lived rules in `.codex-memory/spec/`.
- If the same rule stays useful across multiple sessions or topics, promote it from current/task notes into `spec/`.

## `tasks/` Rules

- Large ongoing tasks should use `.codex-memory/tasks/active/<task>/`.
- Each active task should have:
  - `brief.md`
  - `decisions.md`
  - `refs.md`
- Move completed tasks into `.codex-memory/tasks/archive/`.

## `archive/` Rules

- Use `archive/` for old rounds, replaced goals, one-off adjustments, and obsolete decisions.
- Archive is for tracing history only, not for current startup.

## Update Timing

- Update `.codex-memory/current.md` when conversations get long, the work becomes complex, the phase changes, or before ending the current thread.
- If the work belongs to an active task, update that task's files as well.
<!-- CODEX-MEMORY:END -->
```
