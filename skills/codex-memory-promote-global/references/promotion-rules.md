# Promotion Rules

Use this file when deciding whether project content deserves promotion into `{GLOBAL_MEMORY_ROOT}`.

## Promote only when

- the rule, preference, or workflow has clearly become cross-project
- the content has survived at least two sessions or appears in more than one project
- the content is confirmed and will likely matter again later
- the target location is clear: `current.md`, `spec/*.md`, or `topics/active/<topic>/`

## Reject when

- the content is only today's project progress
- the content includes project-only paths, branch names, or temporary file references
- the content is still a guess, draft, or unresolved dispute
- the content is a one-off exception that should stay in project history

## Routing guide

- cross-project current state -> `{GLOBAL_MEMORY_ROOT}/current.md`
- durable rule -> `{GLOBAL_MEMORY_ROOT}/spec/*.md`
- living cross-project stream -> `{GLOBAL_MEMORY_ROOT}/topics/active/<topic>/`
- expired context -> `{GLOBAL_MEMORY_ROOT}/archive/`

## Write-back rule

After promoting, update `{GLOBAL_MEMORY_ROOT}/projects/index.md` and, when needed, add or refresh `关联全局主题` in the project's `.codex-memory/current.md`.

## Validation command

Run:

```bash
python3 scripts/validate_global_memory.py --project-root "<project-root>"
```
