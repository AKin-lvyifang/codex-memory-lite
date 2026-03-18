# How It Works

## One Sentence Version

Instead of letting important project memory live only inside chat history, this pattern stores it in small files that each have one clear job.

## The Four Layers

### `current.md`

This is the startup file.

It answers:

- what are we doing now
- what is in scope
- what is already done
- what still matters

It should stay short and be overwritten, not endlessly appended.

### `spec/`

This is where stable rules live.

Examples:

- design rules
- workflow rules
- component reuse rules

If a rule keeps showing up across sessions, move it here.

### `tasks/`

This is where long-running tasks get separated from one another.

Each major task gets:

- `brief.md`
- `decisions.md`
- `refs.md`

That prevents different workstreams from getting mixed together.

### `archive/`

This is the history shelf.

It keeps:

- old rounds
- obsolete progress
- past decisions that no longer define current state

Useful for tracing. Not useful as a default startup file.

## Why This Helps

Without structure, one handoff file ends up mixing four different time scales:

- what is true now
- what is usually true
- what is true for one specific task
- what used to be true

Once those get mixed, the file grows fast and becomes hard to trust.

This structure keeps them separate, which makes startup faster and resuming work more reliable.
