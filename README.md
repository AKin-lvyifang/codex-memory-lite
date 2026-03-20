# Codex Memory Lite

[English](README.md) | [简体中文](README.zh-CN.md)

Make Codex less forgetful on long-running projects by moving key context out of chat history and into a small, structured memory layer inside each project.

This package is mainly for:

- long memory on long-running projects
- cross-thread and cross-session continuation inside the same project
- lower token usage by reading only the required memory entry files
- cross-project reuse of the same rules, skills, and templates

## What It Solves

When a session gets long, three things usually happen:

1. Chat context becomes too large.
2. Automatic compression drops useful details.
3. A single `codex-handoff.md` keeps growing until current state, stable rules, task details, and old history are all mixed together.

This starter fixes that by splitting memory into four layers:

- `current.md`
  - only the current effective state
- `spec/`
  - stable rules that stay useful across sessions
- `tasks/`
  - per-task folders for long-running work
- `archive/`
  - history that should stay searchable but should not pollute current context

## Core Idea

Do not keep everything in one handoff file.

Instead:

- current work goes to `current.md`
- long-lived rules go to `spec/`
- each major task gets its own folder
- old progress moves to `archive/`

That turns "memory that only lives inside chat" into "memory that belongs to the project itself."

## Repo Contents

- `snippets/`
  - root-level and project-level `AGENTS.md` snippets for triggering and reading the memory layer
- `skills/`
  - English installable pack with 3 core project-memory skills plus 1 optional global promotion skill
- `skills.zh-CN/`
  - Simplified Chinese installable mirror of the same 4 skill packages
- `templates/`
  - the canonical memory file templates
- `scripts/`
  - one-command installer for the English or Simplified Chinese skill pack
- `examples/demo-project/`
  - a sanitized example project showing migrated handoff + structured memory
- `docs/`
  - plain-language explanations, install steps, and migration notes

## Install In 5 Minutes

If you want to actually use this in Codex, the real setup is very simple:

1. update your root-level `AGENTS.md`
2. prepare the project-level `AGENTS.md` for each project, or let bootstrap create it from template
3. install the skill pack in your preferred language
4. keep the bundled templates and support files together with those skills

Detailed guide:

- [docs/install.md](docs/install.md)

### One-Command Install

Install the English pack (`en` argument):

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/AKin-lvyifang/codex-memory-lite/main/scripts/install-skill-pack.sh) en
```

Install the Simplified Chinese pack (`zh-CN` argument):

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/AKin-lvyifang/codex-memory-lite/main/scripts/install-skill-pack.sh) zh-CN
```

Each command installs the selected pack into `${CODEX_HOME:-$HOME/.codex}/skills` by default, and you can optionally pass a target directory as the second argument.

Choose one language pack per install target:

- `en` for the English pack
- `zh-CN` for the Simplified Chinese pack

### Step 1. Update your root-level `AGENTS.md`

Add the snippet from:

- [snippets/GLOBAL-AGENTS-SNIPPET.md](snippets/GLOBAL-AGENTS-SNIPPET.md)

This is the trigger layer.

It tells Codex:

- when a project should switch into structured memory
- when to create `.codex-memory/`
- when to initialize a task folder
- when to sync memory back

### Step 2. Update each project-level `AGENTS.md`

Add the snippet from:

- [snippets/PROJECT-AGENTS-SNIPPET.md](snippets/PROJECT-AGENTS-SNIPPET.md)

This is the project reading layer.

It tells Codex:

- what to read first on a new thread
- what belongs in `current`, `spec`, `tasks`, and `archive`
- when `current.md` should be updated

If the project does not already have `AGENTS.md`, `codex-memory-bootstrap` can create the full file from its bundled template.
If the project already has `AGENTS.md`, bootstrap updates only the managed `CODEX-MEMORY` block and keeps the rest of the file intact.

### Step 3. Install the skill pack

Choose one language pack:

- English pack: `skills/`
- Simplified Chinese pack: `skills.zh-CN/`

Each language pack includes these 3 core skills:

- `codex-memory-bootstrap`
- `codex-memory-task-init`
- `codex-memory-sync`

Optional cross-project skill:

- `codex-memory-promote-global`

If your environment already uses a shared skill directory, keep using that directory.

The important part is:

- Codex can discover the pack you chose
- each skill keeps its own `templates/`, `references/`, `scripts/`, or other support files next to `SKILL.md` when required

### Step 4. Keep templates with the skills

Do not install only the `SKILL.md` files.

Each skill expects its support files to exist beside it.

That is how the generated memory files stay consistent instead of drifting over time.

### Step 5. Start using it

Typical first run:

1. open a long-running project
2. make sure the root-level trigger rules are in place
3. if the project already has `AGENTS.md`, keep it; otherwise let bootstrap create it from template
4. run `codex-memory-bootstrap`
5. when a new major task appears, run `codex-memory-task-init`
6. when the phase changes or the thread is ending, run `codex-memory-sync`

## The Skill Packs

### 3 Core Project-Memory Skills

### `codex-memory-bootstrap`

Use when a project becomes long-running, noisy, or clearly spans multiple sessions.

It will:

- create `.codex-memory/`
- write the standard files from templates
- if `AGENTS.md` is missing, write the full project-level file from `templates/project-agents.md`
- if `AGENTS.md` already exists, update only the managed `CODEX-MEMORY` block defined in `templates/project-agents-block.md`
- after writing `AGENTS.md`, run `python3 scripts/validate_project_agents.py --project-root <project-root> --mode create` (new file) or `--mode update` (managed block) so the block matches the template verbatim
- flag an old `codex-handoff.md` as pending migration instead of rewriting or deleting it

### `codex-memory-task-init`

Use when a new major task needs its own memory folder.

It creates:

- `brief.md`
- `decisions.md`
- `refs.md`

### `codex-memory-sync`

Use when the project changes phase, context grows, or you are about to end a thread.

It keeps:

- `current.md`
- active task files
- archive notes

in sync with the latest reality.

### 1 Optional Cross-Project Skill

#### `codex-memory-promote-global`

Use when confirmed, reusable knowledge should be lifted into a separate global memory layer.

It helps promote:

- durable rules
- recurring workflows
- shared topics that span more than one project

This flow is explicit and opt-in. It does **not** automatically share all project context across repositories.

## How Root And Project Rules Work Together

### Root-level rule

The root `AGENTS.md` decides when structured memory should be activated.

Typical triggers:

- the work will continue across sessions
- multiple files or topics are involved
- handoff/history is already piling up
- context is clearly getting bloated

### Project-level rule

The project `AGENTS.md` decides what Codex should read first inside that project.

Default order:

1. `.codex-memory/current.md`
2. `.codex-memory/spec/index.md`
3. if there is an active task, read `.codex-memory/tasks/index.md` and the task `brief.md`

## Recommended Project Structure

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

## Daily Usage

### Start a new long-running project

1. Add the root snippet into your root `AGENTS.md`.
2. Keep the 3 core skills available in your Codex skills directory.
3. When the project crosses the trigger threshold, run `codex-memory-bootstrap`.

### Start a new major task

Run `codex-memory-task-init`.

### End a phase or finish a long turn

Run `codex-memory-sync`.

### Maintain an explicit global memory layer

If you also keep a separate global memory layer, install `codex-memory-promote-global` from the same language pack and run it only when you intentionally want to promote stable cross-project knowledge.

## What "Cross-Project" Means Here

This is important to state clearly.

This project is best at:

- cross-thread continuation within the same project
- cross-session continuation within the same project

At the cross-project level, what you really reuse is:

- the same trigger rules
- the same project memory structure
- the same core skill pack
- the same templates

In other words:

it reuses the memory mechanism across projects.

It does **not** mean all projects should automatically share all business context with each other.

Global promotion, if you use it, is explicit and opt-in.

## Migration From A Single Handoff File

The intended migration is:

- current effective state -> `current.md`
- repeated stable rules -> `spec/`
- active long-running work -> `tasks/active/<task>/`
- obsolete progress and history -> `archive/`

The old `codex-handoff.md` stays in the repo as a frozen reference, but it should no longer be the main entry point.

See [docs/migration-guide.md](docs/migration-guide.md) for the simple routing rules.

## Example

See [examples/demo-project](examples/demo-project) for a full, sanitized demo.

It includes:

- a project-level `AGENTS.md`
- a frozen legacy `codex-handoff.md`
- a working `.codex-memory/` tree
- an example active task with `brief / decisions / refs`

## Screenshots

- [Storyboard Preview](docs/screenshots/codex-memory-story-preview.png)
- [Slide 01](docs/screenshots/codex-memory-story-01.png)
- [Slide 02](docs/screenshots/codex-memory-story-02.png)
- [Slide 03](docs/screenshots/codex-memory-story-03.png)
- [Slide 04](docs/screenshots/codex-memory-story-04.png)
- [Slide 05](docs/screenshots/codex-memory-story-05.png)
- [Slide 06](docs/screenshots/codex-memory-story-06.png)
- [Slide 07](docs/screenshots/codex-memory-story-07.png)
- [Slide 08](docs/screenshots/codex-memory-story-08.png)

## FAQ

### Is this replacing Codex context?

No. It reduces pressure on live context by moving durable information into files.

### Does this make projects more complicated?

Only slightly at setup time. In practice it makes long projects much easier to resume.

### Should every small question use this?

No. Use it for long-running, multi-file, multi-topic, or cross-session work.

### Should archive be loaded by default?

No. Archive is for tracing history, not for normal startup.

## Publish Checklist

Before you publish your own version:

- remove private absolute home paths
- remove private business names and node IDs
- keep only the memory-related part of your root rules
- make sure example files are sanitized

## License

This starter ships with an MIT license by default. Change it if your use case needs something else.
