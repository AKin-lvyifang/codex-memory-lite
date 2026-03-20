---
name: codex-memory-promote-global
description: Use when the user says "Promote this to global memory", or when stable project knowledge should be promoted into `{GLOBAL_MEMORY_ROOT}`.
---

# Codex Memory Promote Global

## Overview

Promote stable, reusable memory from a project's `.codex-memory/` into `{GLOBAL_MEMORY_ROOT}`. Use this skill when the user explicitly asks for global promotion, or when a rule, workflow, or topic has clearly become reusable across projects.

## When To Use

- The user explicitly says "Promote this to global memory"
- The user explicitly asks to promote a rule into the global layer
- The same rule appears in more than one project
- A topic is no longer project-specific and is now shared across projects
- A thread is about to end and stable content should be lifted from project memory into the global layer

## Natural Trigger Phrases

- Promote this to global memory
- Promote this rule into the global layer
- This can be reused across projects. Move it to the global layer

## Inputs

- current project root
- current project's `.codex-memory/current.md`
- current project's related `spec/` and active task files
- global memory root: `{GLOBAL_MEMORY_ROOT}`
- reference rules: `references/promotion-rules.md`

## Workflow

1. Read the current project's `.codex-memory/current.md`, related `spec/`, and `tasks/active/*/brief.md`.
2. Use `references/promotion-rules.md` to filter candidate content.
3. Decide the correct target in the global layer:
   - cross-project state that is still currently effective -> `{GLOBAL_MEMORY_ROOT}/current.md`
   - long-lived stable rules -> `{GLOBAL_MEMORY_ROOT}/spec/*.md`
   - ongoing cross-project topics -> `{GLOBAL_MEMORY_ROOT}/topics/active/<topic>/`
4. Update `{GLOBAL_MEMORY_ROOT}/projects/index.md`.
5. When needed, write back `关联全局主题` into the current project's `current.md`.
6. Run `python3 scripts/validate_global_memory.py --project-root <project-root>`.
7. Report what was promoted, what was rejected, and why it was rejected.

## Must Reject

- today's progress log from a single project
- project-only file paths, branch names, or temporary directories
- unconfirmed guesses or exploratory judgments
- local constraints that only matter inside one project
- content containing sensitive information unless sharing permission is explicit

## Validation

- the global directory and core files must exist
- `current.md` must keep its fixed headings
- `projects/index.md` must contain the current project entry
- linked global topics must really exist
- global `spec/` and `current.md` must not accidentally contain machine-specific absolute project paths

## Report Back

- which global files were updated
- which project <-> topic links were added or updated
- which candidate items were rejected and why
- validation result
