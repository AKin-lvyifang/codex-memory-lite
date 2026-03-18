# Root `AGENTS.md` Snippet

Use this in your root-level `AGENTS.md` to trigger structured project memory when needed.

```md
## Context Management

- For long conversations, complex work, multi-file changes, multi-topic work, or obvious context bloat, write key project context into reusable structured memory instead of relying only on chat history.
- If a project-level `AGENTS.md` already defines a project memory structure, follow the project-level rules first.
- Project memory should separate:
  - current effective state
  - stable long-lived rules
  - active task context
  - historical archive
- Do not keep current state and historical logs mixed in one file for long-running work.
- On a new thread for the same project, read the project-level startup entry first. Only fall back to a temporary handoff if no project memory entry exists.

## Codex Memory Triggers

- Enable structured memory when any of these is true:
  - the work will continue across multiple sessions
  - the work spans multiple files, pages, or topics
  - handoff / rules / history are already piling up
  - context is clearly getting bloated
- If the project needs structured memory and `.codex-memory/` does not exist yet, run `codex-memory-bootstrap`.
- If `.codex-memory/` already exists, read:
  1. `.codex-memory/current.md`
  2. `.codex-memory/spec/index.md`
  3. if there is an active task, `.codex-memory/tasks/index.md` and that task `brief.md`
- If a new major long-running task appears and does not have its own task folder yet, run `codex-memory-task-init`.
- Do not load `.codex-memory/archive/` by default. Only read it when tracing history is actually needed.
- At phase changes, before ending a thread, or when context grows significantly, run `codex-memory-sync`.
- Do not enable `.codex-memory/` by default for tiny one-off questions or temporary experiments.
```
