#!/usr/bin/env node

"use strict";

const childProcess = require("child_process");
const crypto = require("crypto");
const fs = require("fs");
const os = require("os");
const path = require("path");

const SCRIPT_DIR = __dirname;
const MEMORYCTL = path.join(SCRIPT_DIR, "memoryctl.py");
const CURATOR_SCHEMA = path.join(SCRIPT_DIR, "..", "references", "curator-output.schema.json");
const CURATOR_PROMPT = path.join(SCRIPT_DIR, "..", "references", "curator-prompt.md");
const SOURCE_CODEX_HOME = path.resolve(process.env.CODEX_HOME || path.join(os.homedir(), ".codex"));
const DEFAULT_CONFIG = path.join(SOURCE_CODEX_HOME, "memory-v2", "config.json");
const GLOBAL_HOOKS = path.join(SOURCE_CODEX_HOME, "hooks.json");
const INTERNAL_ENV = "CODEX_MEMORY_INTERNAL";
let currentEvent = {};

function readJson(file, fallback = null) {
  try {
    return JSON.parse(fs.readFileSync(file, "utf8"));
  } catch {
    return fallback;
  }
}

function atomicWriteJson(file, value) {
  fs.mkdirSync(path.dirname(file), { recursive: true, mode: 0o700 });
  const temporary = path.join(path.dirname(file), `.${path.basename(file)}.${process.pid}.${Date.now()}`);
  fs.writeFileSync(temporary, `${JSON.stringify(value, null, 2)}\n`, { mode: 0o600 });
  fs.renameSync(temporary, file);
  fs.chmodSync(file, 0o600);
}

function sha256(value) {
  return crypto.createHash("sha256").update(value).digest("hex");
}

function fileSha256(file) {
  return sha256(fs.readFileSync(file));
}

function canonicalJson(value) {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

function isoNow() {
  return new Date().toISOString();
}

function isInside(child, parent) {
  const relative = path.relative(parent, child);
  return relative === "" || (!relative.startsWith("..") && !path.isAbsolute(relative));
}

function safeSessionId(value) {
  const result = String(value || "unknown-session").replace(/[^A-Za-z0-9._-]+/g, "_").replace(/^[._]+|[._]+$/g, "");
  return (result || "unknown-session").slice(0, 160);
}

function sleep(milliseconds) {
  Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, milliseconds);
}

function withDirectoryLock(lock, callback) {
  fs.mkdirSync(path.dirname(lock), { recursive: true, mode: 0o700 });
  const deadline = Date.now() + 3000;
  while (true) {
    try {
      fs.mkdirSync(lock, { mode: 0o700 });
      break;
    } catch (error) {
      if (error.code !== "EEXIST") throw error;
      try {
        if (Date.now() - fs.statSync(lock).mtimeMs > 30000) fs.rmSync(lock, { recursive: true, force: true });
      } catch {}
      if (Date.now() >= deadline) throw new Error(`timed out waiting for ${lock}`);
      sleep(25);
    }
  }
  try {
    return callback();
  } finally {
    fs.rmSync(lock, { recursive: true, force: true });
  }
}

function loadConfig() {
  const file = path.resolve(process.env.CODEX_MEMORY_CONFIG || DEFAULT_CONFIG);
  const config = readJson(file, {});
  if (!config.enabled) return null;
  return { ...config, _path: file };
}

function resolveProjectRoot(cwd, config) {
  const current = path.resolve(String(cwd || process.cwd()));
  const matches = (config.project_roots || [])
    .map((item) => path.resolve(String(item)))
    .filter((root) => isInside(current, root) && fs.existsSync(root))
    .sort((left, right) => right.length - left.length);
  return matches[0] || null;
}

function memoryPaths(root, sessionId) {
  const runtime = path.join(root, ".codex-memory", ".runtime");
  const session = path.join(runtime, "sessions", safeSessionId(sessionId));
  return {
    memory: path.join(root, ".codex-memory"),
    runtime,
    session,
    state: path.join(session, "state.json"),
    pending: path.join(session, "pending.jsonl"),
    eventLock: path.join(session, ".event-lock"),
    projectState: path.join(runtime, "project-state.json"),
    projectLock: path.join(runtime, ".hook-state-lock"),
  };
}

function runMemoryctl(root, args, config, timeout = 30000) {
  const result = childProcess.spawnSync(
    "python3",
    [MEMORYCTL, ...args, "--project-root", root, "--json"],
    {
      cwd: root,
      env: { ...process.env, CODEX_MEMORY_CONFIG: config._path, [INTERNAL_ENV]: "1" },
      encoding: "utf8",
      timeout,
      maxBuffer: 8 * 1024 * 1024,
    },
  );
  if (result.error) throw result.error;
  if (result.status !== 0) {
    throw new Error((result.stderr || result.stdout || `memoryctl exited ${result.status}`).trim());
  }
  try {
    return JSON.parse(result.stdout);
  } catch {
    throw new Error(`memoryctl returned invalid JSON: ${String(result.stdout).slice(0, 1000)}`);
  }
}

function ensureV2(root, config) {
  const manifest = path.join(root, ".codex-memory", "manifest.json");
  if (fs.existsSync(path.join(root, ".codex-memory-disabled"))) return false;
  if (!fs.existsSync(manifest)) runMemoryctl(root, ["migrate-v1"], config);
  return true;
}

function redactText(value) {
  let text = String(value || "");
  let count = 0;
  const replacements = [
    [/\bsk-[A-Za-z0-9_-]{16,}\b/g, "[REDACTED_OPENAI_KEY]"],
    [/\bgh[oprsu]_[A-Za-z0-9]{20,}\b/g, "[REDACTED_GITHUB_TOKEN]"],
    [/\bAKIA[0-9A-Z]{16}\b/g, "[REDACTED_AWS_KEY]"],
    [/\bBearer\s+[A-Za-z0-9._~+\/-]{12,}=*/gi, "Bearer [REDACTED_TOKEN]"],
    [/\b((?:api[_-]?key|access[_-]?token|secret|password|passwd)\s*[:=]\s*)[^\s,;]{8,}/gi, "$1[REDACTED_SECRET]"],
  ];
  for (const [pattern, replacement] of replacements) {
    text = text.replace(pattern, () => {
      count += 1;
      return replacement;
    });
  }
  return { text, redactedCount: count };
}

function boundedText(value, limit) {
  const redacted = redactText(value);
  if (redacted.text.length <= limit) {
    return { text: redacted.text, truncated: false, redacted_count: redacted.redactedCount };
  }
  const clipped = redacted.text.slice(0, limit);
  return {
    text: clipped,
    truncated: true,
    original_chars: redacted.text.length,
    clipped_sha256: sha256(redacted.text),
    redacted_count: redacted.redactedCount,
  };
}

function durablePromptSignal(prompt) {
  return /(?:请记住|记下来|以后(?:都|默认)|从现在起|决定(?:采用|改为)|确认(?:采用|完成)|当前进度|下一步|暂停任务|恢复任务|任务完成|范围改为|持仓(?:更新|改为)|已(?:完成|修复|发布|部署)|\b(?:please\s+)?remember\b|\bfrom\s+now\s+on\b|\bgoing\s+forward\b|\bwe\s+(?:decided|confirmed)\b|\b(?:decision|next\s+step|scope\s+changed)\b|\b(?:task\s+)?(?:paused|resumed|completed)\b|\b(?:fixed|released|deployed)\b)/i.test(prompt);
}

function appendEvent(root, sessionId, eventType, payload, turnId, stateUpdates = {}) {
  const files = memoryPaths(root, sessionId);
  return withDirectoryLock(files.eventLock, () => {
    fs.mkdirSync(files.session, { recursive: true, mode: 0o700 });
    const state = readJson(files.state, {}) || {};
    const seq = Number(state.next_seq || 1);
    const unsigned = {
      schema_version: 2,
      event_id: `${sessionId}:${seq}`,
      session_id: String(sessionId),
      turn_id: turnId ? String(turnId) : null,
      seq,
      event_type: eventType,
      created_at: isoNow(),
      payload,
    };
    const record = { ...unsigned, checksum: sha256(canonicalJson(unsigned)) };
    fs.appendFileSync(files.pending, `${JSON.stringify(record)}\n`, { encoding: "utf8", mode: 0o600 });
    fs.chmodSync(files.pending, 0o600);
    Object.assign(state, stateUpdates, {
      next_seq: seq + 1,
      last_event_at: unsigned.created_at,
      updated_at: unsigned.created_at,
    });
    atomicWriteJson(files.state, state);
    return { record, state };
  });
}

function updateSessionState(root, sessionId, updates) {
  const files = memoryPaths(root, sessionId);
  return withDirectoryLock(files.eventLock, () => {
    const state = readJson(files.state, {}) || {};
    Object.assign(state, updates, { updated_at: isoNow() });
    atomicWriteJson(files.state, state);
    return state;
  });
}

function updateProjectState(root, sessionId, eventName, updates = {}) {
  const files = memoryPaths(root, sessionId);
  return withDirectoryLock(files.projectLock, () => {
    const state = readJson(files.projectState, {}) || {};
    Object.assign(state, updates, {
      last_hook_heartbeat_at: isoNow(),
      last_hook_heartbeat_epoch: Date.now() / 1000,
      last_hook_event: eventName,
      hook_script_sha256: fileSha256(__filename),
      hooks_config_sha256: fs.existsSync(GLOBAL_HOOKS) ? fileSha256(GLOBAL_HOOKS) : null,
    });
    atomicWriteJson(files.projectState, state);
    return state;
  });
}

function parseGitPaths(statusOutput) {
  const tokens = statusOutput.split("\0").filter(Boolean);
  const paths = [];
  for (let index = 0; index < tokens.length; index += 1) {
    const token = tokens[index];
    if (token.length < 4) continue;
    const status = token.slice(0, 2);
    const first = token.slice(3);
    if (first) paths.push(first);
    if ((status.includes("R") || status.includes("C")) && tokens[index + 1]) {
      paths.push(tokens[index + 1]);
      index += 1;
    }
  }
  return [...new Set(paths)].sort();
}

function fileSignature(file, budget) {
  const stat = fs.statSync(file);
  let digest = null;
  if (stat.isFile() && stat.size <= 1024 * 1024 && budget.remaining >= stat.size) {
    digest = fileSha256(file);
    budget.remaining -= stat.size;
  }
  return `${stat.isFile() ? "f" : "o"}:${stat.size}:${Math.floor(stat.mtimeMs)}:${digest || ""}`;
}

function gitSnapshot(root) {
  const status = childProcess.spawnSync("git", ["status", "--porcelain=v1", "-z", "--untracked-files=all"], {
    cwd: root,
    encoding: "utf8",
    timeout: 10000,
    maxBuffer: 8 * 1024 * 1024,
  });
  if (status.status !== 0) return null;
  const head = childProcess.spawnSync("git", ["rev-parse", "HEAD"], {
    cwd: root,
    encoding: "utf8",
    timeout: 5000,
  });
  const files = {};
  const budget = { remaining: 16 * 1024 * 1024 };
  const paths = parseGitPaths(status.stdout).slice(0, 2000);
  for (const relative of paths) {
    if (relative.startsWith(".codex-memory/.runtime/") || relative.startsWith(".git/")) continue;
    const absolute = path.join(root, relative);
    try {
      files[relative] = fileSignature(absolute, budget);
    } catch {
      files[relative] = "missing";
    }
  }
  return {
    kind: "git",
    head: head.status === 0 ? head.stdout.trim() : null,
    status_sha256: sha256(status.stdout),
    files,
    partial: parseGitPaths(status.stdout).length > 2000 || budget.remaining <= 0,
  };
}

function walkSnapshot(root) {
  const files = {};
  const budget = { remaining: 16 * 1024 * 1024 };
  const queue = [root];
  while (queue.length && Object.keys(files).length < 2000) {
    const directory = queue.shift();
    for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
      const absolute = path.join(directory, entry.name);
      const relative = path.relative(root, absolute);
      if (relative === ".git" || relative.startsWith(".git/") || relative.startsWith(".codex-memory/.runtime/")) continue;
      if (entry.isDirectory()) queue.push(absolute);
      else if (entry.isFile()) files[relative] = fileSignature(absolute, budget);
      if (Object.keys(files).length >= 2000 || budget.remaining <= 0) break;
    }
  }
  return { kind: "files", head: null, status_sha256: null, files, partial: queue.length > 0 || budget.remaining <= 0 };
}

function workspaceSnapshot(root) {
  return gitSnapshot(root) || walkSnapshot(root);
}

function compareSnapshots(before, after) {
  if (!before || !after) return { changed: false, paths: [], head_changed: false, partial: true };
  const keys = [...new Set([...Object.keys(before.files || {}), ...Object.keys(after.files || {})])].sort();
  const paths = keys.filter((key) => before.files[key] !== after.files[key]);
  const headChanged = before.head !== after.head;
  return {
    changed: headChanged || before.status_sha256 !== after.status_sha256 || paths.length > 0,
    paths: paths.slice(0, 200),
    paths_truncated: paths.length > 200,
    head_changed: headChanged,
    partial: Boolean(before.partial || after.partial),
  };
}

function pendingStats(root, sessionId) {
  const pending = memoryPaths(root, sessionId).pending;
  if (!fs.existsSync(pending)) return { count: 0, oldestAgeSeconds: 0 };
  const records = fs.readFileSync(pending, "utf8").split("\n").filter(Boolean).map((line) => {
    try { return JSON.parse(line); } catch { return null; }
  }).filter(Boolean);
  const oldest = Math.min(...records.map((item) => Date.parse(item.created_at)).filter(Number.isFinite), Date.now());
  return { count: records.length, oldestAgeSeconds: Math.max(0, (Date.now() - oldest) / 1000) };
}

function hasActiveTask(root) {
  const manifest = readJson(path.join(root, ".codex-memory", "manifest.json"), {}) || {};
  return Array.isArray(manifest.active_task_ids) && manifest.active_task_ids.length > 0;
}

function discardTurn(root, sessionId, turnId) {
  if (!turnId) return;
  const files = memoryPaths(root, sessionId);
  withDirectoryLock(files.eventLock, () => {
    if (!fs.existsSync(files.pending)) return;
    const kept = fs.readFileSync(files.pending, "utf8").split("\n").filter(Boolean).filter((line) => {
      try { return String(JSON.parse(line).turn_id || "") !== String(turnId); } catch { return true; }
    });
    if (kept.length) fs.writeFileSync(files.pending, `${kept.join("\n")}\n`, { mode: 0o600 });
    else fs.rmSync(files.pending, { force: true });
  });
}

function buildCuratorPrompt(transactionDir) {
  const source = readJson(path.join(transactionDir, "source.json"), {});
  const transaction = readJson(path.join(transactionDir, "transaction.json"), {});
  const files = [];
  for (const relative of transaction.proposed_files || []) {
    const file = path.join(transactionDir, "proposed", relative);
    if (!fs.existsSync(file)) continue;
    files.push({
      path: relative,
      writable: (transaction.allowed_write_files || []).includes(relative),
      content: fs.readFileSync(file, "utf8"),
    });
  }
  const policy = fs.readFileSync(CURATOR_PROMPT, "utf8");
  return `${policy}\n\n## Transaction input\n\n${JSON.stringify({ source, files }, null, 2)}\n`;
}

function createCuratorHome() {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), "codex-memory-curator-"));
  const auth = path.join(SOURCE_CODEX_HOME, "auth.json");
  if (fs.existsSync(auth)) {
    const target = path.join(home, "auth.json");
    fs.copyFileSync(auth, target);
    fs.chmodSync(target, 0o600);
  }
  return home;
}

function runCuratorOnce(root, transactionDir, outputFile, model, effort, timeoutSeconds) {
  const fixture = process.env.CODEX_MEMORY_CURATOR_FIXTURE;
  if (fixture) {
    fs.copyFileSync(path.resolve(fixture), outputFile);
    return { model, fixture: true };
  }
  const curatorHome = createCuratorHome();
  try {
    const prompt = buildCuratorPrompt(transactionDir);
    const args = [
      "exec",
      "--ephemeral",
      "--ignore-user-config",
      "--ignore-rules",
      "--disable", "hooks",
      "--disable", "memories",
      "--disable", "multi_agent",
      "-s", "read-only",
      "-c", 'approval_policy="never"',
      "-c", `model_reasoning_effort="${effort}"`,
      "-c", 'model_verbosity="low"',
      "-m", model,
      "--skip-git-repo-check",
      "--color", "never",
      "-C", transactionDir,
      "--output-schema", CURATOR_SCHEMA,
      "-o", outputFile,
      "-",
    ];
    const result = childProcess.spawnSync("codex", args, {
      cwd: transactionDir,
      env: { ...process.env, CODEX_HOME: curatorHome, [INTERNAL_ENV]: "1" },
      input: prompt,
      encoding: "utf8",
      timeout: timeoutSeconds * 1000,
      maxBuffer: 16 * 1024 * 1024,
    });
    if (result.error) throw result.error;
    if (result.status !== 0 || !fs.existsSync(outputFile)) {
      throw new Error((result.stderr || result.stdout || `curator exited ${result.status}`).trim().slice(-4000));
    }
    return { model, fixture: false };
  } finally {
    fs.rmSync(curatorHome, { recursive: true, force: true });
  }
}

function runCurator(root, transactionDir, outputFile, eventModel, config, sessionId) {
  const curator = config.curator || {};
  const preferred = String(curator.preferred_model || "gpt-5.6-sol");
  const effort = String(curator.reasoning_effort || "low");
  const timeout = Number(curator.timeout_seconds || 240);
  try {
    return runCuratorOnce(root, transactionDir, outputFile, preferred, effort, timeout);
  } catch (error) {
    const fallback = String(eventModel || "");
    if (curator.fallback_model_policy !== "inherit" || !fallback || fallback === preferred) throw error;
    updateProjectState(root, sessionId, "CuratorFallback", {
      last_model_fallback: `${preferred} -> ${fallback}: ${String(error.message).slice(0, 500)}`,
    });
    return runCuratorOnce(root, transactionDir, outputFile, fallback, effort, timeout);
  }
}

function recoverStaleTransaction(root, config, sessionId) {
  const lockFile = path.join(root, ".codex-memory", ".runtime", "lock.json");
  const lock = readJson(lockFile, null);
  if (!lock) return null;
  const age = Date.now() / 1000 - Number(lock.created_epoch || 0);
  if (age < Number((config.curator || {}).timeout_seconds || 240) + 60) return "fresh_lock";
  const transactionId = String(lock.transaction_id || "");
  const transactionDir = path.join(root, ".codex-memory", ".runtime", "transactions", transactionId);
  if (!fs.existsSync(transactionDir)) {
    fs.rmSync(lockFile, { force: true });
    return "stale_lock_removed";
  }
  if (fs.existsSync(path.join(transactionDir, "commit-log.json"))) {
    runMemoryctl(root, ["recover", "--transaction-id", transactionId], config);
    return "recovered";
  }
  runMemoryctl(root, ["abandon", "--transaction-id", transactionId, "--reason", "stale prepared transaction recovered by Hook"], config);
  return "abandoned";
}

function syncMemory(root, event, config) {
  const sessionId = String(event.session_id || "unknown-session");
  const stale = recoverStaleTransaction(root, config, sessionId);
  if (stale === "fresh_lock") return { status: "deferred", message: "another memory sync is running" };
  const prepared = runMemoryctl(root, ["prepare", "--session-id", sessionId], config);
  if (prepared.status === "no_pending") return prepared;
  const transactionId = prepared.transaction_id;
  const transactionDir = prepared.transaction_dir;
  const outputFile = path.join(transactionDir, "curator-output.json");
  try {
    const runner = runCurator(root, transactionDir, outputFile, event.model, config, sessionId);
    const applied = runMemoryctl(
      root,
      ["apply-result", "--transaction-id", transactionId, "--result-file", outputFile],
      config,
    );
    if (applied.status === "unresolved") {
      runMemoryctl(
        root,
        ["abandon", "--transaction-id", transactionId, "--reason", applied.unresolved.join("; ")],
        config,
      );
      return { ...applied, model: runner.model };
    }
    let committed;
    try {
      committed = runMemoryctl(
        root,
        ["commit", "--transaction-id", transactionId, `--commit-token=${prepared.commit_token}`],
        config,
      );
    } catch (error) {
      if (fs.existsSync(path.join(transactionDir, "commit-log.json"))) {
        runMemoryctl(root, ["recover", "--transaction-id", transactionId], config);
      } else {
        runMemoryctl(root, ["abandon", "--transaction-id", transactionId, "--reason", String(error.message)], config);
      }
      throw error;
    }
    updateProjectState(root, sessionId, "MemorySync", {
      last_hook_sync_at: isoNow(),
      last_hook_sync_outcome: committed.outcome,
      last_hook_sync_summary: committed.summary,
      last_hook_error: null,
      last_curator_model: runner.model,
    });
    return { ...committed, model: runner.model };
  } catch (error) {
    const transactionStillExists = fs.existsSync(transactionDir);
    const commitStarted = fs.existsSync(path.join(transactionDir, "commit-log.json"));
    if (transactionStillExists && !commitStarted) {
      try {
        runMemoryctl(root, ["abandon", "--transaction-id", transactionId, "--reason", String(error.message)], config);
      } catch {}
    }
    throw error;
  }
}

function resultMessage(result) {
  if (!result) return null;
  if (result.status === "unresolved") return `项目记忆存在无法自动判断的冲突，已保留待处理内容：${result.unresolved.join("；")}`;
  if (result.status === "deferred") return null;
  if (result.outcome === "write") {
    const labels = {
      progress: "任务进度",
      decision: "关键决定",
      next_step: "下一步",
      constraint: "稳定约束",
      reference: "关键索引",
      task_status: "任务状态",
      other: "项目状态",
    };
    const categories = (result.updated_categories || []).map((item) => labels[item] || item).join("、") || "项目状态";
    return `已记录：${categories}`;
  }
  return null;
}

function emit(eventName, message = null) {
  if (!["Stop", "SubagentStop", "SessionStart", "PreCompact", "PostCompact", "UserPromptSubmit", "SubagentStart"].includes(eventName)) return;
  const output = { continue: true };
  if (message) output.systemMessage = message;
  process.stdout.write(`${JSON.stringify(output)}\n`);
}

function main() {
  if (process.env[INTERNAL_ENV] === "1") return;
  const raw = fs.readFileSync(0, "utf8").trim();
  if (!raw) return;
  const event = JSON.parse(raw);
  currentEvent = event;
  const eventName = String(event.hook_event_name || "");
  const config = loadConfig();
  if (!config) return emit(eventName);
  const root = resolveProjectRoot(event.cwd, config);
  if (!root) return emit(eventName);
  if (!ensureV2(root, config)) return emit(eventName);

  const sessionId = String(event.session_id || "unknown-session");
  const turnId = event.turn_id ? String(event.turn_id) : null;
  updateProjectState(root, sessionId, eventName);
  const files = memoryPaths(root, sessionId);
  let state = readJson(files.state, {}) || {};
  let syncResult = null;

  if (eventName === "SessionStart") {
    recoverStaleTransaction(root, config, sessionId);
    const snapshot = workspaceSnapshot(root);
    if (!state.workspace_baseline) {
      state = updateSessionState(root, sessionId, {
        workspace_baseline: snapshot,
        last_observed_snapshot: snapshot,
        source: event.source || null,
      });
    }
    if (pendingStats(root, sessionId).count > 0) syncResult = syncMemory(root, event, config);
    if (syncResult && ["committed", "no_pending"].includes(syncResult.status)) {
      const baseline = workspaceSnapshot(root);
      updateSessionState(root, sessionId, {
        workspace_baseline: baseline,
        last_observed_snapshot: baseline,
        dirty: false,
        explicit_signal: false,
        force_sync: false,
        checkpoint_required: false,
        last_sync_error: null,
      });
    }
  } else if (eventName === "UserPromptSubmit") {
    const prompt = String(event.prompt || "");
    const signal = durablePromptSignal(prompt);
    appendEvent(root, sessionId, "user_prompt", boundedText(prompt, Number(config.sync?.max_event_chars || 12000)), turnId, {
      explicit_signal: Boolean(state.explicit_signal || signal),
      source_model: event.model || null,
    });
  } else if (eventName === "PostToolUse") {
    const toolName = String(event.tool_name || "");
    const before = state.last_observed_snapshot || state.workspace_baseline || workspaceSnapshot(root);
    const after = workspaceSnapshot(root);
    const drift = compareSnapshots(before, after);
    const externalWrite = /(?:create|update|delete|write|post|send|publish|mutation|upload|commit|push)/i.test(toolName);
    if (drift.changed || toolName === "apply_patch" || externalWrite) {
      appendEvent(
        root,
        sessionId,
        "tool_effect",
        {
          tool_name: toolName,
          tool_input: boundedText(JSON.stringify(event.tool_input || {}), 6000),
          tool_response: boundedText(JSON.stringify(event.tool_response || {}), 2000),
          workspace_change: drift,
          external_write_signal: externalWrite,
        },
        turnId,
        {
          dirty: Boolean(state.dirty || drift.changed || toolName === "apply_patch" || externalWrite),
          last_observed_snapshot: after,
        },
      );
    } else {
      updateSessionState(root, sessionId, { last_observed_snapshot: after });
    }
  } else if (eventName === "PreCompact") {
    appendEvent(root, sessionId, "pre_compact", {
      trigger: event.trigger || null,
      transcript_path: event.transcript_path || null,
    }, turnId, { force_sync: true, checkpoint_required: true });
    syncResult = syncMemory(root, event, config);
  } else if (eventName === "SubagentStart") {
    appendEvent(root, sessionId, "subagent_start", {
      agent_id: event.agent_id || null,
      agent_type: event.agent_type || null,
    }, turnId);
  } else if (eventName === "SubagentStop") {
    appendEvent(root, sessionId, "subagent_stop", {
      agent_id: event.agent_id || null,
      agent_type: event.agent_type || null,
      last_assistant_message: boundedText(event.last_assistant_message || "", 6000),
    }, turnId);
  } else if (eventName === "Stop") {
    if (event.stop_hook_active) return emit(eventName);
    const recordedStops = Array.isArray(state.recorded_stop_turns) ? state.recorded_stop_turns : [];
    if (!turnId || !recordedStops.includes(turnId)) {
      const appended = appendEvent(root, sessionId, "assistant_final", boundedText(event.last_assistant_message || "", 12000), turnId, {
        recorded_stop_turns: [...recordedStops.slice(-19), turnId].filter(Boolean),
      });
      state = appended.state;
    }
    const before = state.workspace_baseline || state.last_observed_snapshot;
    const after = workspaceSnapshot(root);
    const drift = compareSnapshots(before, after);
    if (drift.changed) {
      const appended = appendEvent(root, sessionId, "workspace_change", drift, turnId, {
        dirty: true,
        last_observed_snapshot: after,
      });
      state = appended.state;
    }
    const stats = pendingStats(root, sessionId);
    const activeTask = hasActiveTask(root);
    const threshold = Number(config.sync?.active_task_event_threshold || 6);
    const maxAge = Number(config.sync?.max_pending_age_seconds || 900);
    const forced = process.env.CODEX_MEMORY_FORCE_SYNC === "1";
    const shouldSync = forced || state.force_sync || state.dirty || state.explicit_signal
      || (activeTask && (stats.count >= threshold || stats.oldestAgeSeconds >= maxAge));
    if (shouldSync) {
      syncResult = syncMemory(root, event, config);
      if (["committed", "no_pending"].includes(syncResult.status)) {
        const baseline = workspaceSnapshot(root);
        updateSessionState(root, sessionId, {
          workspace_baseline: baseline,
          last_observed_snapshot: baseline,
          dirty: false,
          explicit_signal: false,
          force_sync: false,
          checkpoint_required: false,
          last_sync_error: null,
        });
      }
    } else if (!activeTask && !state.dirty && !state.explicit_signal) {
      discardTurn(root, sessionId, turnId);
    }
  }

  emit(eventName, resultMessage(syncResult));
}

try {
  main();
} catch (error) {
  const event = currentEvent;
  const eventName = String(event.hook_event_name || "Stop");
  try {
    const config = loadConfig();
    const root = config ? resolveProjectRoot(event.cwd, config) : null;
    if (root) updateProjectState(root, String(event.session_id || "unknown-session"), eventName, {
      last_hook_error: String(error.stack || error.message || error).slice(0, 4000),
    });
  } catch {}
  emit(eventName, `项目记忆自动整理失败，待处理内容已保留：${String(error.message || error).slice(0, 500)}`);
}
