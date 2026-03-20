# Public Skill Pack Update

Date: 2026-03-20

## Summary

This update refreshes the public skill pack so it can be shared safely and installed more easily by English and Simplified Chinese users.

## What Changed

- Added a bilingual public release structure:
  - `skills/` for the English installable pack
  - `skills.zh-CN/` for the Simplified Chinese installable pack
- Expanded the public package from 3 core project-memory skills to 4 skills:
  - `codex-memory-bootstrap`
  - `codex-memory-task-init`
  - `codex-memory-sync`
  - `codex-memory-promote-global` as an optional cross-project skill
- Removed hard-coded personal absolute paths and usernames from the public copies
- Sanitized the global memory validation script so its default global path is derived from `${CODEX_HOME}` or `${HOME}`
- Added `scripts/install-skill-pack.sh` for one-command language-specific installation
- Updated the README and install guide to explain:
  - how to choose the English or Simplified Chinese pack
  - which 3 skills are core
  - when the optional global promotion skill should be installed

## Scope Notes

- The public package preserves the original skill intent as much as possible
- The main functional changes are limited to:
  - privacy-safe path placeholders
  - bilingual packaging
  - one-command installation guidance

## Install Examples

English:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/AKin-lvyifang/codex-memory-lite/main/scripts/install-skill-pack.sh) en
```

Simplified Chinese:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/AKin-lvyifang/codex-memory-lite/main/scripts/install-skill-pack.sh) zh-CN
```
