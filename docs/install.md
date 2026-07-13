# Installation And Configuration

[简体中文](install.zh-CN.md)

This guide installs Codex Memory Lite V2 into a Codex-compatible ChatGPT/Codex environment, verifies the Hook configuration, and explains how to update or remove it without deleting project memory.

## Requirements

- macOS or Linux
- Node.js 18 or newer, including `npx`
- Python 3
- Git
- Codex CLI available in `PATH`
- A ChatGPT/Codex build that supports command Hooks

Check the main prerequisites:

```bash
node --version
python3 --version
git --version
codex --version
```

## One-Command Install

```bash
npx --yes --package=github:AKin-lvyifang/codex-memory-lite codex-memory-lite install
```

The command installs from the repository's current `main` branch. Pin a release when reproducibility matters:

```bash
npx --yes --package=github:AKin-lvyifang/codex-memory-lite#v2.0.0 codex-memory-lite install
```

Alternative `curl` entry:

```bash
curl -fsSL https://raw.githubusercontent.com/AKin-lvyifang/codex-memory-lite/main/scripts/install.sh | sh
```

The script calls the same `npx` installer. Review [scripts/install.sh](../scripts/install.sh) before piping it to a shell if that is part of your security policy.

## Let An Agent Install It

Send this as one message to an Agent that can operate your local machine:

> Install the latest Codex Memory Lite from https://github.com/AKin-lvyifang/codex-memory-lite using its one-command installer; preserve my existing Hooks, MCP servers, Skills, and config, run doctor, and tell me whether ChatGPT needs a restart.

The Agent should report the target Codex home, backup path, doctor result, and whether a restart or new task is required.

## What The Installer Changes

Default target: `${CODEX_HOME:-$HOME/.codex}`.

| Path | Action |
| --- | --- |
| `skills/codex-memory/` | Install or replace the V2 runtime Skill after backup |
| `ai/hooks/codex-memory-bootstrap-first-prompt.js` | Install the automatic project bootstrap Hook |
| `hooks.json` | Merge eight V2 command handlers; preserve other handlers and top-level data |
| `config.toml` | Enable `[features].hooks` and add trust hashes for V2 handlers |
| `memory-v2/config.json` | Preserve existing values and add missing V2 defaults |
| `backups/codex-memory-lite/<timestamp>/` | Save every affected existing file before mutation |

The installer does not rewrite MCP settings, unrelated Skills, project `AGENTS.md`, or any project `.codex-memory/` directory.

## Custom Codex Home

Use either form:

```bash
npx --yes --package=github:AKin-lvyifang/codex-memory-lite codex-memory-lite install --codex-home "/custom/codex-home"
```

```bash
CODEX_HOME="/custom/codex-home" \
  npx --yes --package=github:AKin-lvyifang/codex-memory-lite codex-memory-lite install
```

Run ChatGPT/Codex with the same `CODEX_HOME`; otherwise the application will load a different Hook configuration.

## Activate And Verify

1. Start a new task or restart ChatGPT/Codex.
2. Open a project and send the first normal prompt.
3. Run doctor:

```bash
npx --yes --package=github:AKin-lvyifang/codex-memory-lite codex-memory-lite doctor
```

A healthy result confirms the Skill files, eight handlers, trust hashes, Hook feature, configuration, and fleet report command. A project is registered only after its first prompt.

## Configuration

V2 config is stored in `${CODEX_HOME:-$HOME/.codex}/memory-v2/config.json`.

Important fields:

| Field | Default | Purpose |
| --- | --- | --- |
| `enabled` | `true` | Global V2 switch |
| `project_roots` | `[]` | Projects registered automatically by the first-prompt Hook |
| `excluded_project_roots` | `[]` | Exact project roots V2 must skip |
| `curator.preferred_model` | `gpt-5.6-sol` | Preferred read-only Curator model |
| `curator.reasoning_effort` | `low` | Favors fast memory classification |
| `curator.fallback_model_policy` | `inherit` | Fall back to the active task model when available |
| `sync.active_task_event_threshold` | `12` | Pending-event threshold for active tasks |
| `sync.max_pending_age_seconds` | `1800` | Maximum pending age before active-task review |
| `storage.runtime_soft_limit_mb` | `20` | Runtime-data warning threshold |
| `storage.project_soft_limit_mb` | `50` | Total project-memory warning threshold |

To keep a project outside V2, add its exact absolute path to `excluded_project_roots`. Do not delete its memory just to disable automation.

## Update

```bash
npx --yes --package=github:AKin-lvyifang/codex-memory-lite codex-memory-lite update
```

Update runs the same backup-and-merge process as install. Existing custom config values remain authoritative; only missing defaults are added.

## Uninstall

```bash
npx --yes --package=github:AKin-lvyifang/codex-memory-lite codex-memory-lite uninstall
```

Default uninstall removes the owned Skill, bootstrap script, Hook handlers, and their trust entries. It keeps V2 config and all project memory.

Remove the V2 config as well:

```bash
npx --yes --package=github:AKin-lvyifang/codex-memory-lite codex-memory-lite uninstall --purge-config
```

Even with `--purge-config`, project `.codex-memory/` directories are not deleted.

## Dry Run And JSON Output

```bash
npx --yes --package=github:AKin-lvyifang/codex-memory-lite codex-memory-lite install --dry-run
npx --yes --package=github:AKin-lvyifang/codex-memory-lite codex-memory-lite doctor --json
```

Use `--json` for Agent automation and machine-readable checks.

## Common Problems

### `codex is not available in PATH`

Install or update Codex CLI, then confirm `codex --version` works in the same shell. Memory files can be installed without it, but Curator review cannot run.

### Hooks are installed but no project is registered

Start a new task or restart the application, enter the project, and send one prompt. The bootstrap Hook runs on the first prompt rather than during installation.

### An old V1 Skill still appears

The installer preserves old Skills deliberately. Follow [Migrate from V1](migration-v1.md) to retire legacy routing after confirming V2 is healthy.

### Doctor reports an untrusted or modified Hook

Run `update` to regenerate the V2 handlers and trust hashes. If the problem remains, inspect the latest backup and verify that another tool is not rewriting `hooks.json` or `config.toml`.
