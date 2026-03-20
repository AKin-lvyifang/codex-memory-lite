# Install Guide

## Goal

Make Codex use this structured memory system in real projects.

The install is basically just three things:

1. update the right `AGENTS.md` files
2. install the skill pack in your preferred language
3. keep the templates and support files together with the skills

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

If the project does not already have `AGENTS.md`, `codex-memory-bootstrap` can create the full file from its bundled template.
If the project already has `AGENTS.md`, bootstrap updates only the managed `CODEX-MEMORY` block and keeps the rest of the file intact.

## How To Install The Skills

### One-command install

Install the English pack:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/AKin-lvyifang/codex-memory-lite/main/scripts/install-skill-pack.sh) en
```

Install the Simplified Chinese pack:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/AKin-lvyifang/codex-memory-lite/main/scripts/install-skill-pack.sh) zh-CN
```

Both commands install the selected pack into `${CODEX_HOME:-$HOME/.codex}/skills` by default, and you can optionally pass a target directory as the second argument.

Choose one language pack per install target:

- `en` for the English pack
- `zh-CN` for the Simplified Chinese pack

### Manual install

Choose one language pack:

- English pack: `skills/`
- Simplified Chinese pack: `skills.zh-CN/`

Each language pack includes these 3 core skills:

- `codex-memory-bootstrap`
- `codex-memory-task-init`
- `codex-memory-sync`

Optional cross-project skill:

- `codex-memory-promote-global`

Important:

- do not copy only `SKILL.md`
- keep each skill's `templates/`, `references/`, `scripts/`, and other support files beside it when they exist

That is what keeps file generation stable and consistent.

## What Bootstrap Now Guarantees

`codex-memory-bootstrap` handles project-level `AGENTS.md` in two modes:

- missing `AGENTS.md`: create the full file from `templates/project-agents.md`
- existing `AGENTS.md`: update only the managed `CODEX-MEMORY` block

After writing, it runs `scripts/validate_project_agents.py`:

- `--mode create` checks that the full file matches the bundled full template
- `--mode update` checks that the managed block matches `templates/project-agents-block.md`

If bootstrap finds an older `codex-handoff.md`, it should keep that file untouched and mark it for a separate migration step instead of rewriting it automatically.

## Recommended First-Time Setup

1. put the root snippet into your root `AGENTS.md`
2. if a project already has `AGENTS.md`, keep it; otherwise let bootstrap create it from template
3. install the 3 core skills from one language pack
4. open the project in Codex
5. run `codex-memory-bootstrap`

After that:

- when a new major task appears, run `codex-memory-task-init`
- when a phase changes or a long thread is ending, run `codex-memory-sync`
- if you maintain a separate global memory layer, optionally install and run `codex-memory-promote-global`

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
