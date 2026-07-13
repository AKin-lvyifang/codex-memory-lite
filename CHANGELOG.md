# Changelog

## 2.0.0 - 2026-07-13

### Breaking Changes

- Replace the manual V1 four-Skill workflow with one automatic V2 Skill and lifecycle Hooks.
- Stop using project `AGENTS.md` as the memory engine. V2 preserves existing files but no longer requires them for initialization or synchronization.

### Features

- Add one-command installation, update, doctor, and non-destructive uninstall commands.
- Add automatic project discovery, V1 project-memory migration, selective Curator review, transaction validation, recovery, and fleet diagnostics.
- Preserve unrelated Hooks, MCP settings, Skills, configuration, and every project `.codex-memory/` directory.
- Add bilingual README, installation, architecture, and migration documentation.
- Add reproducible TGZ and ZIP packaging with SHA256 verification and isolated install smoke tests.
