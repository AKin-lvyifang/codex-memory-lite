# Migrate From Codex Memory Lite V1

[简体中文](migration-v1.zh-CN.md)

V2 is a breaking workflow change. V1 depended on four manually routed Skills and memory instructions in `AGENTS.md`; V2 uses one runtime Skill plus automatic Hooks.

The migration keeps existing memory, tasks, archives, `AGENTS.md`, and legacy Skills. It does not silently remove them.

## Before You Start

Identify whether V1 is active:

- `codex-memory-bootstrap`, `codex-memory-task-init`, `codex-memory-sync`, or `codex-memory-promote-global` exists under the Skill directory
- root or project `AGENTS.md` tells the Agent to run those Skills
- a project already has `.codex-memory/current.md` but no V2 `manifest.json`

Do not delete `.codex-memory/` or the old handoff file to migrate.

## Migration Steps

1. Install V2:

```bash
npx --yes --package=github:AKin-lvyifang/codex-memory-lite#v2.0.0 codex-memory-lite install
```

2. Start a new task or restart ChatGPT/Codex.
3. Open one V1 project and send a normal prompt.
4. Confirm `.codex-memory/manifest.json` now reports `schema_version: 2`.
5. Run doctor:

```bash
npx --yes --package=github:AKin-lvyifang/codex-memory-lite#v2.0.0 codex-memory-lite doctor
```

6. Ask the Agent to show the current project progress and confirm that current/task/spec files remain readable.
7. Only after the pilot project passes, retire the V1 routing described below.

## What Automatic `migrate-v1` Does

- Creates the V2 manifest, runtime directories, transaction metadata, and task metadata where needed.
- Keeps existing `current.md`, `spec/`, `tasks/`, `archive/`, `AGENTS.md`, and legacy handoff files.
- Marks the layout as V1-compatible instead of rewriting historical content.
- Adds only `.codex-memory/.runtime/` to the local Git exclude when possible.

It does not summarize or delete old history during migration.

## Retire Old Routing

V2 must not be forced back into the manual V1 workflow by global rules.

Review root and project `AGENTS.md` for instructions that require:

- `codex-memory-bootstrap`
- `codex-memory-task-init`
- `codex-memory-sync`
- manual synchronization at every phase or task end

Remove only the obsolete memory workflow instructions. Keep real project standards, architecture rules, commands, and product constraints.

If a project contains the managed block below, it is V1 memory routing:

```text
<!-- CODEX-MEMORY:START -->
...
<!-- CODEX-MEMORY:END -->
```

V2 does not require that block. Remove it only after verifying that no unrelated project rule was placed inside it.

## Retire Legacy Skills

The V2 installer preserves old Skill directories because they may be used by other tools or tasks. After all required projects pass V2 validation, archive or remove these directories from the active Skill search path:

```text
codex-memory-bootstrap/
codex-memory-task-init/
codex-memory-sync/
codex-memory-promote-global/
```

Keep a backup until old tasks and external tools no longer depend on them. Do not remove the new `codex-memory/` directory.

## Rollback

Every install or update writes a timestamped backup under:

```text
${CODEX_HOME:-$HOME/.codex}/backups/codex-memory-lite/
```

To stop V2 without touching projects:

```bash
npx --yes --package=github:AKin-lvyifang/codex-memory-lite#v2.0.0 codex-memory-lite uninstall
```

This removes the V2 runtime and owned Hook entries but keeps `memory-v2/config.json` and every project `.codex-memory/`. Restore legacy routing only if you intentionally return to V1.

## Migration Acceptance Checklist

- V2 doctor is healthy.
- The project has a schema V2 manifest.
- Existing current, spec, task, and archive content remains present.
- Project `AGENTS.md` is unchanged by automatic migration.
- A durable test update is recorded once; an ordinary short turn stays silent.
- Root rules no longer force the four V1 Skills.
- Legacy Skills remain backed up until no old task or external tool needs them.
