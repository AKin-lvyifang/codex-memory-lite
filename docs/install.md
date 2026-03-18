# Install Guide

## Goal

Make Codex use this structured memory system in real projects.

The install is basically just three things:

1. update the right `AGENTS.md` files
2. install the 3 skills
3. keep the templates together with the skills

## What You Need To Update

### 1. Root-level `AGENTS.md`

Add the snippet from:

- `snippets/GLOBAL-AGENTS-SNIPPET.md`

Use this in the root place where your Codex environment keeps global rules.

Its job is to tell Codex:

- when to enable structured memory
- when to initialize project memory
- when to initialize a task folder
- when to sync memory back into files

### 2. Project-level `AGENTS.md`

Add the snippet from:

- `snippets/PROJECT-AGENTS-SNIPPET.md`

Use this inside each project that should have structured memory.

Its job is to tell Codex:

- what files to read first on a new thread
- what belongs in `current / spec / tasks / archive`
- when `current.md` should be updated

## How To Install The Skills

Copy these folders into the skill directory your Codex instance already scans:

- `skills/codex-memory-bootstrap/`
- `skills/codex-memory-task-init/`
- `skills/codex-memory-sync/`

Important:

- do not copy only `SKILL.md`
- keep each skill's `templates/` folder beside it

That is what keeps file generation stable and consistent.

## Recommended First-Time Setup

1. put the root snippet into your root `AGENTS.md`
2. put the project snippet into a project's `AGENTS.md`
3. install the 3 skills
4. open the project in Codex
5. run `codex-memory-bootstrap`

After that:

- when a new major task appears, run `codex-memory-task-init`
- when a phase changes or a long thread is ending, run `codex-memory-sync`

## Recommended File Layout

```text
.codex-memory/
├── current.md
├── spec/
├── tasks/
└── archive/
```

## Typical Startup Read Order

When a new thread enters a project, the intended read order is:

1. `.codex-memory/current.md`
2. `.codex-memory/spec/index.md`
3. if there is an active task, `.codex-memory/tasks/index.md`
4. then the active task `brief.md`

This is what helps reduce token usage:

- read the small entry files first
- do not load historical material by default
- only open `archive/` when tracing old decisions is actually needed

## Common Mistakes

### Mistake 1: Only creating `.codex-memory/` without rules

If you do not update `AGENTS.md`, Codex may never read the memory files in the correct order.

### Mistake 2: Installing only the skill prompts

If you forget the templates, generated files can drift and become inconsistent.

### Mistake 3: Loading `archive/` by default

That brings old context back into the main thread and defeats part of the token-saving benefit.

## Best Use Cases

Use this when work is:

- long-running
- multi-file
- multi-topic
- likely to continue across sessions or threads

Do not force it on every tiny one-off question.
