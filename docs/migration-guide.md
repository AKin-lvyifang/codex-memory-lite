# Migration Guide

## Goal

Move from a single growing handoff file to a small structured memory tree.

## Route Old Content Like This

### Send to `current.md`

Use for:

- the current goal
- current scope
- what is already done
- what is in progress
- the next step

### Send to `spec/`

Use for:

- repeated rules
- long-lived standards
- conventions that still matter across sessions

Rule of thumb:

If losing this rule would likely cause rework later, it belongs in `spec/`.

### Send to `tasks/active/<task>/`

Use for:

- large workstreams that will continue
- task-specific decisions
- task-only references

Split them into:

- `brief.md`
- `decisions.md`
- `refs.md`

### Send to `archive/`

Use for:

- old progress logs
- replaced goals
- one-off tuning notes
- outdated decisions

## What To Do With The Old Handoff

Do not delete it automatically.

Instead:

1. prepend a short migration notice
2. point readers to `.codex-memory/current.md`
3. stop using it as the main startup file

## Quick Migration Checklist

1. Bootstrap `.codex-memory/`
2. Move current truth into `current.md`
3. move stable rules into `spec/`
4. create task folders for major active work
5. archive historical leftovers
6. freeze the legacy handoff
