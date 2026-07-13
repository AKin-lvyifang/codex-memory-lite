<a href="https://github.com/AKin-lvyifang/codex-memory-lite">
  <img width="1280" alt="Codex Memory Lite v2.0.0, automatic project memory for Codex." src="https://raw.githubusercontent.com/AKin-lvyifang/codex-memory-lite/v2.0.0/docs/images/codex-memory-lite-v2.0.0.png">
</a>

<p align="center">
  <a href="#install">Install</a> ·
  <a href="#how-it-works">How it works</a> ·
  <a href="#commands">Commands</a> ·
  <a href="docs/install.md">Documentation</a> ·
  <a href="README.zh-CN.md">简体中文</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-v2.0.0-167D73?style=flat-square" alt="Version v2.0.0">
  <img src="https://img.shields.io/badge/runtime-Node.js_18%2B-2F6F4E?style=flat-square" alt="Node.js 18 or newer">
  <img src="https://img.shields.io/badge/platform-ChatGPT_%2F_Codex-1F2937?style=flat-square" alt="ChatGPT and Codex">
  <img src="https://img.shields.io/badge/license-MIT-D97706?style=flat-square" alt="MIT License">
</p>

# Codex Memory Lite

Automatic, project-scoped memory for long-running Codex work. It records durable progress and decisions in `.codex-memory/` while leaving temporary conversation noise behind.

<a id="install"></a>
## Install

```bash
npx --yes --package=https://github.com/AKin-lvyifang/codex-memory-lite/releases/latest/download/codex-memory-lite.tgz codex-memory-lite install
```

Start a new task or restart ChatGPT/Codex after installation. The first prompt inside a project initializes memory automatically.

**Prefer to let an Agent handle it? Send this sentence:**

> Install the latest Codex Memory Lite from https://github.com/AKin-lvyifang/codex-memory-lite using its one-command installer; preserve my existing Hooks, MCP servers, Skills, and config, run doctor, and tell me whether ChatGPT needs a restart.

Alternative `curl` entry:

```bash
curl -fsSL https://raw.githubusercontent.com/AKin-lvyifang/codex-memory-lite/main/scripts/install.sh | sh
```

The installer backs up affected files first, merges its eight Hook handlers into the existing Hook configuration, and keeps unrelated Hooks, MCP settings, Skills, and project memory.

## What V2 Changes

- **Automatic startup**: a first-prompt Hook detects projects and creates or migrates `.codex-memory/` without editing project `AGENTS.md`.
- **Selective recording**: Hooks observe every relevant lifecycle event, but the Curator runs only after a durable signal, workspace change, checkpoint, or pending threshold.
- **Separated judgment and writes**: a read-only Curator proposes `write`, `skip`, or `unresolved`; deterministic code validates and commits the result.
- **Recoverable updates**: checksums, transactions, revisions, and atomic writes prevent partial or silent memory corruption.
- **Bounded storage**: temporary runtime data is cleaned after it is resolved; confirmed long-term memory is never automatically deleted.

<a id="how-it-works"></a>
## How It Works

```text
Codex lifecycle event
        ↓
Hook records a small, redacted event
        ↓
Trigger gate decides whether a review is needed
        ↓
Read-only Curator classifies durable information
        ↓
memoryctl validates coverage, paths, and revisions
        ↓
Atomic update to .codex-memory/
```

The default Curator is `gpt-5.6-sol` with low reasoning effort. If that model is unavailable, V2 can inherit the active task model and records the fallback in diagnostics.

Only a real write produces a short notice such as `已记录：任务进度`. A no-op stays silent.

Read the full mechanism in [How it works](docs/how-it-works.md).

## Daily Use

1. Open a Git project or a folder with a recognized project marker.
2. Continue the actual task. Do not manually initialize or sync memory.
3. Ask Codex to “show project progress/history” when you want it to read the stored memory.
4. Run `doctor` when Hooks appear inactive or a sync reports an error.

V2 keeps this structure:

```text
.codex-memory/
├── current.md            # current effective state
├── spec/                 # durable project rules
├── tasks/                # active and archived task context
├── archive/              # historical memory
├── manifest.json         # schema and revision metadata
└── .runtime/             # pending events and recoverable transactions
```

<a id="commands"></a>
## Commands

```bash
# Update without overwriting unrelated configuration
npx --yes --package=https://github.com/AKin-lvyifang/codex-memory-lite/releases/latest/download/codex-memory-lite.tgz codex-memory-lite update

# Verify the installed Skill, Hooks, trust hashes, config, and fleet status
npx --yes --package=https://github.com/AKin-lvyifang/codex-memory-lite/releases/latest/download/codex-memory-lite.tgz codex-memory-lite doctor

# Remove the installed runtime; keep V2 config and every project memory folder
npx --yes --package=https://github.com/AKin-lvyifang/codex-memory-lite/releases/latest/download/codex-memory-lite.tgz codex-memory-lite uninstall
```

Use `--codex-home PATH` for a non-default Codex home. `CODEX_HOME=/path` also works. See [Installation and configuration](docs/install.md) for version pinning, backup locations, and all options.

## Safety And Boundaries

- Installation never deletes a project `.codex-memory/` directory.
- Existing `hooks.json`, `config.toml`, V2 config, and the installed `codex-memory` Skill are backed up before mutation.
- The installer owns one Skill, one bootstrap Hook script, and eight command Hook handlers. It does not rewrite MCP configuration or project `AGENTS.md`.
- Curator input can include the current prompt, compact tool-effect summaries, final response text, workspace-change metadata, and relevant memory files. Common secret patterns are redacted, but users should still avoid placing secrets in prompts or memory.
- V1 Skills and old `AGENTS.md` memory blocks are preserved, not silently removed. Follow the [V1 migration guide](docs/migration-v1.md) to retire them deliberately.

## Documentation

- [Installation and configuration](docs/install.md)
- [How V2 works](docs/how-it-works.md)
- [Migrate from V1](docs/migration-v1.md)
- [中文安装说明](docs/install.zh-CN.md)

## Development

```bash
npm test
npm run package:release
npm run verify:release
```

`verify:release` checks archive contents and SHA256 values, then performs an isolated install, doctor, and uninstall cycle.

## License

Codex Memory Lite is released under the [MIT License](LICENSE).
