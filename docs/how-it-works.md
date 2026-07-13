# How Codex Memory Lite V2 Works

[简体中文](how-it-works.zh-CN.md)

V2 separates observation, judgment, validation, and storage. The model can decide what is useful, but it cannot directly overwrite durable memory.

## The Five Parts

### 1. Bootstrap Hook

The first `UserPromptSubmit` event searches upward from the working directory for a Git root or a recognized project marker. It skips system, temporary, Codex, and explicitly excluded directories.

If the project has no V2 manifest, the Hook registers the root and runs one of two actions:

- `bootstrap` for a new project
- `migrate-v1` when an existing `.codex-memory/current.md` is found

It does not create or edit project `AGENTS.md`.

### 2. Event Hook

The main Hook observes these lifecycle points:

| Event | What V2 does |
| --- | --- |
| `SessionStart` | Recover stale transactions, establish a workspace baseline, process existing pending data |
| `UserPromptSubmit` | Record a bounded and redacted prompt event |
| `PostToolUse` | Record tool effects only when files or external state may have changed |
| `PreCompact` | Create a forced checkpoint before context compression |
| `SubagentStart` / `SubagentStop` | Preserve task boundaries and relevant subagent outcomes |
| `Stop` | Record the final response, compare workspace state, and run the trigger gate |

The installer adds eight handlers because `UserPromptSubmit` has separate bootstrap and event handlers.

### 3. Trigger Gate

The Hook itself does not use regular expressions to decide business importance. It uses deterministic signals only to decide whether a model review is worth running:

- the workspace changed
- the user used an explicit durable signal such as “remember” or “going forward”
- context is about to be compacted
- unresolved pending data exists at session start
- an active task crossed the event-count or age threshold
- a test or operator explicitly forced synchronization

Ordinary short turns without an active task are discarded after the turn when they contain no durable signal or workspace change. This prevents every message from becoming a model call or a history file.

### 4. Read-Only Curator

When the gate opens, `memoryctl.py prepare` creates a transaction snapshot. The Hook then starts a temporary Codex process with:

- a separate ephemeral `CODEX_HOME`
- read-only sandbox
- approval policy `never`
- Hooks, memories, personal rules, and multi-agent behavior disabled
- a strict JSON output schema

The Curator classifies every source event as:

- `write`: durable information that affects future work
- `skip`: temporary, repeated, speculative, or reconstructable information
- `unresolved`: a conflict or high-risk ambiguity the Curator must not guess about

The default model is `gpt-5.6-sol` with low reasoning effort. The configured fallback can inherit the active task model.

### 5. Deterministic Commit

The Curator returns proposals, not file writes. `memoryctl.py` then checks:

- every source event has a disposition
- every target is on the transaction's write allowlist
- returned files are complete and within size limits
- append-only decision/reference content was not silently deleted
- the project memory revision still matches the prepared revision
- a real file change exists before declaring `write`

Commit uses single-file atomic replacements and advances the manifest revision last. A transaction interrupted after writing begins can be recovered or rolled back from its commit log.

## Memory Layers

| Layer | Purpose | Update behavior |
| --- | --- | --- |
| `current.md` | Current effective state and next step | May replace stale current state |
| `spec/` | Stable project rules and constraints | Durable, read only when relevant |
| `tasks/` | Active and archived workstream context | Task-scoped |
| `archive/` | Historical memory | Preserved for traceability |
| `.runtime/` | Pending events, transactions, locks, and audit receipts | Temporary and recoverable |

Confirmed long-term memory is not automatically deleted. Runtime pending data can be removed only after a validated `write` or `skip` disposition is committed.

## Storage And Compaction

V2 defines soft limits rather than deleting durable information:

- runtime data: 20 MB per project by default
- total project memory: 50 MB by default
- completed task hot window: 90 days by default

`gc` removes safe temporary artifacts and enforces failed-transaction retention. It never deletes unresolved pending events or durable memory. Long-term monthly compaction is designed to summarize and preserve source history, not erase it; existing V1 history is not rearranged automatically in this release.

## Privacy And Network Boundary

Events and memory are stored locally in the project. When Curator review runs, the prepared transaction input is sent through the configured Codex model service. It may include prompt text, compact tool-effect summaries, final response text, workspace-change metadata, and relevant memory copies.

The Hook redacts common OpenAI, GitHub, AWS, bearer-token, password, and API-key patterns before pending storage. Pattern redaction is a guardrail, not a complete secret scanner. Do not place credentials in prompts or project memory.

## Failure Behavior

- Invalid Curator JSON leaves pending data intact.
- Missing source coverage blocks commit.
- `unresolved` abandons the temporary transaction but keeps source events for the main Agent.
- Revision conflicts preserve both formal memory and pending input.
- Partial commits use a commit log for recovery.
- Only a validated real write emits `已记录：...`; no-op remains silent.

Use `codex-memory-lite doctor` for installation health and the `codex-memory` Skill's `fleet-status` command for project-level observations.
