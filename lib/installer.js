"use strict";

const childProcess = require("child_process");
const crypto = require("crypto");
const fs = require("fs");
const os = require("os");
const path = require("path");

const PACKAGE_ROOT = path.resolve(__dirname, "..");
const PACKAGE_JSON = require(path.join(PACKAGE_ROOT, "package.json"));
const VERSION = PACKAGE_JSON.version;
const EVENT_LABELS = {
  PreToolUse: "pre_tool_use",
  PermissionRequest: "permission_request",
  PostToolUse: "post_tool_use",
  PreCompact: "pre_compact",
  PostCompact: "post_compact",
  SessionStart: "session_start",
  UserPromptSubmit: "user_prompt_submit",
  SubagentStart: "subagent_start",
  SubagentStop: "subagent_stop",
  Stop: "stop",
};
const MATCHER_EVENTS = new Set([
  "PreToolUse",
  "PermissionRequest",
  "PostToolUse",
  "PreCompact",
  "PostCompact",
  "SessionStart",
  "SubagentStart",
  "SubagentStop",
]);
const OWNED_COMMAND_MARKERS = [
  "codex-memory/scripts/memory-hook.js",
  "codex-memory-bootstrap-first-prompt.js",
];
const LEGACY_SKILL_NAMES = [
  "codex-memory-bootstrap",
  "codex-memory-task-init",
  "codex-memory-sync",
  "codex-memory-promote-global",
];

function canonicalJson(value) {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

function sha256(value) {
  return crypto.createHash("sha256").update(value).digest("hex");
}

function atomicWrite(file, content, mode = 0o600) {
  fs.mkdirSync(path.dirname(file), { recursive: true, mode: 0o700 });
  const temporary = `${file}.tmp-${process.pid}-${Date.now()}`;
  fs.writeFileSync(temporary, content, { mode });
  fs.renameSync(temporary, file);
  fs.chmodSync(file, mode);
}

function atomicWriteJson(file, value, mode = 0o600) {
  atomicWrite(file, `${JSON.stringify(value, null, 2)}\n`, mode);
}

function commandExists(command) {
  const result = childProcess.spawnSync(command, ["--version"], {
    encoding: "utf8",
    timeout: 5000,
  });
  return result.status === 0;
}

function quoteCommandPath(value) {
  return `"${String(value)
    .replace(/\\/g, "\\\\")
    .replace(/"/g, '\\"')
    .replace(/\$/g, "\\$")
    .replace(/`/g, "\\`")}"`;
}

function pathsFor(codexHome) {
  const home = path.resolve(codexHome);
  return {
    codexHome: home,
    skill: path.join(home, "skills", "codex-memory"),
    bootstrapHook: path.join(home, "ai", "hooks", "codex-memory-bootstrap-first-prompt.js"),
    memoryHook: path.join(home, "skills", "codex-memory", "scripts", "memory-hook.js"),
    memoryctl: path.join(home, "skills", "codex-memory", "scripts", "memoryctl.py"),
    hooks: path.join(home, "hooks.json"),
    memoryConfig: path.join(home, "memory-v2", "config.json"),
    codexConfig: path.join(home, "config.toml"),
    backups: path.join(home, "backups", "codex-memory-lite"),
  };
}

function existingLegacySkills(paths) {
  const skills = path.join(paths.codexHome, "skills");
  return LEGACY_SKILL_NAMES.filter((name) => fs.existsSync(path.join(skills, name)));
}

function requiredHooks(paths) {
  const memoryCommand = `node ${quoteCommandPath(paths.memoryHook)}`;
  const bootstrapCommand = `node ${quoteCommandPath(paths.bootstrapHook)}`;
  return {
    SessionStart: [{
      matcher: "startup|resume|clear|compact",
      hooks: [{ type: "command", command: memoryCommand, timeout: 300, statusMessage: "Restoring project memory" }],
    }],
    UserPromptSubmit: [
      { hooks: [{ type: "command", command: bootstrapCommand, statusMessage: "Checking project memory" }] },
      { hooks: [{ type: "command", command: memoryCommand, timeout: 15 }] },
    ],
    PostToolUse: [{
      matcher: "Bash|apply_patch|Edit|Write|mcp__.*",
      hooks: [{ type: "command", command: memoryCommand, timeout: 30 }],
    }],
    PreCompact: [{
      matcher: "manual|auto",
      hooks: [{ type: "command", command: memoryCommand, timeout: 300, statusMessage: "Organizing project memory" }],
    }],
    SubagentStart: [{ hooks: [{ type: "command", command: memoryCommand, timeout: 15 }] }],
    SubagentStop: [{ hooks: [{ type: "command", command: memoryCommand, timeout: 30 }] }],
    Stop: [{
      hooks: [{ type: "command", command: memoryCommand, timeout: 300, statusMessage: "Organizing project memory" }],
    }],
  };
}

function isOwnedHandler(handler) {
  const command = String(handler && handler.command || "").replace(/\\/g, "/");
  return OWNED_COMMAND_MARKERS.some((marker) => command.includes(marker));
}

function mergeHooks(existing, required) {
  const value = existing && typeof existing === "object" ? structuredClone(existing) : {};
  value.hooks = value.hooks && typeof value.hooks === "object" ? value.hooks : {};
  const events = new Set([...Object.keys(value.hooks), ...Object.keys(required)]);
  for (const event of events) {
    const groups = Array.isArray(value.hooks[event]) ? value.hooks[event] : [];
    const reusable = [];
    for (let index = 0; index < groups.length; index += 1) {
      const group = groups[index] && typeof groups[index] === "object" ? groups[index] : { hooks: [] };
      const handlers = Array.isArray(group.hooks) ? group.hooks : [];
      const owned = handlers.filter(isOwnedHandler);
      if (!owned.length) continue;
      const unowned = handlers.filter((handler) => !isOwnedHandler(handler));
      if (unowned.length) groups[index] = { ...group, hooks: unowned };
      else {
        groups[index] = { ...group, hooks: [] };
        reusable.push(index);
      }
    }
    const requiredGroups = required[event] || [];
    requiredGroups.forEach((group, requiredIndex) => {
      if (reusable[requiredIndex] !== undefined) groups[reusable[requiredIndex]] = group;
      else groups.push(group);
    });
    value.hooks[event] = groups;
  }
  return value;
}

function removeOwnedHooks(existing) {
  const value = existing && typeof existing === "object" ? structuredClone(existing) : {};
  value.hooks = value.hooks && typeof value.hooks === "object" ? value.hooks : {};
  for (const [event, groups] of Object.entries(value.hooks)) {
    if (!Array.isArray(groups)) continue;
    value.hooks[event] = groups.map((group) => ({
      ...group,
      hooks: (Array.isArray(group.hooks) ? group.hooks : []).filter((handler) => !isOwnedHandler(handler)),
    }));
  }
  return value;
}

function commandHookHash(eventName, group, handler) {
  const normalizedHandler = {
    type: "command",
    command: String(handler.command || ""),
    timeout: Math.max(1, Number.parseInt(handler.timeout || 600, 10)),
    async: Boolean(handler.async || false),
  };
  if (handler.statusMessage !== undefined && handler.statusMessage !== null) {
    normalizedHandler.statusMessage = String(handler.statusMessage);
  }
  const identity = {
    event_name: EVENT_LABELS[eventName],
    hooks: [normalizedHandler],
  };
  if (MATCHER_EVENTS.has(eventName) && group.matcher) identity.matcher = String(group.matcher);
  return `sha256:${sha256(canonicalJson(identity))}`;
}

function ownedHookEntries(hooksPath, hooksConfig) {
  const result = [];
  for (const [event, groups] of Object.entries(hooksConfig.hooks || {})) {
    if (!EVENT_LABELS[event] || !Array.isArray(groups)) continue;
    groups.forEach((group, groupIndex) => {
      (Array.isArray(group.hooks) ? group.hooks : []).forEach((handler, handlerIndex) => {
        if (!isOwnedHandler(handler)) return;
        const rawKey = `${hooksPath}:${EVENT_LABELS[event]}:${groupIndex}:${handlerIndex}`;
        result.push({
          event,
          groupIndex,
          handlerIndex,
          rawKey,
          fileKey: `file:${rawKey}`,
          hash: commandHookHash(event, group, handler),
        });
      });
    });
  }
  return result;
}

function tomlEscape(value) {
  return String(value).replace(/\\/g, "\\\\").replace(/"/g, '\\"');
}

function removeTomlSections(text, names) {
  const targets = new Set(names);
  const lines = String(text || "").split("\n");
  const output = [];
  let skipping = false;
  for (const line of lines) {
    const section = line.match(/^\s*\[([^\]]+)\]\s*(?:#.*)?$/);
    if (section) skipping = targets.has(section[1]);
    if (!skipping) output.push(line);
  }
  return output.join("\n").replace(/\n{3,}/g, "\n\n").trimEnd();
}

function tomlSectionValue(text, sectionName, key) {
  const lines = String(text || "").split("\n");
  let inSection = false;
  for (const line of lines) {
    const section = line.match(/^\s*\[([^\]]+)\]\s*(?:#.*)?$/);
    if (section) {
      inSection = section[1] === sectionName;
      continue;
    }
    if (!inSection) continue;
    const entry = line.match(/^\s*([A-Za-z0-9_-]+)\s*=\s*(.*?)\s*(?:#.*)?$/);
    if (entry && entry[1] === key) return entry[2].trim();
  }
  return undefined;
}

function hooksFeatureEnabled(text) {
  return tomlSectionValue(text, "features", "hooks") === "true";
}

function enableHooksFeature(text) {
  const lines = String(text || "").split("\n");
  let start = lines.findIndex((line) => line.trim() === "[features]");
  if (start < 0) {
    const prefix = lines.join("\n").trimEnd();
    return `${prefix}${prefix ? "\n\n" : ""}[features]\nhooks = true\n`;
  }
  let end = lines.length;
  for (let index = start + 1; index < lines.length; index += 1) {
    if (/^\s*\[/.test(lines[index])) {
      end = index;
      break;
    }
  }
  const hookIndex = lines.slice(start + 1, end).findIndex((line) => /^\s*hooks\s*=/.test(line));
  if (hookIndex >= 0) lines[start + 1 + hookIndex] = "hooks = true";
  else lines.splice(start + 1, 0, "hooks = true");
  return `${lines.join("\n").trimEnd()}\n`;
}

function updateTrustConfig(text, entries, previousEntries = []) {
  const removeEntries = [...entries, ...previousEntries];
  const names = removeEntries.flatMap((entry) => [
    `hooks.state."${tomlEscape(entry.rawKey)}"`,
    `hooks.state."${tomlEscape(entry.fileKey)}"`,
  ]);
  let result = removeTomlSections(enableHooksFeature(text), names);
  const blocks = [];
  for (const entry of entries) {
    for (const key of [entry.rawKey, entry.fileKey]) {
      blocks.push(
        `[hooks.state."${tomlEscape(key)}"]\nenabled = true\ntrusted_hash = "${entry.hash}"`,
      );
    }
  }
  if (blocks.length) result = `${result.trimEnd()}\n\n${blocks.join("\n\n")}\n`;
  return result;
}

function removeTrustConfig(text, entries) {
  const names = entries.flatMap((entry) => [
    `hooks.state."${tomlEscape(entry.rawKey)}"`,
    `hooks.state."${tomlEscape(entry.fileKey)}"`,
  ]);
  const result = removeTomlSections(text, names);
  return result ? `${result}\n` : "";
}

function mergeMissing(current, defaults) {
  if (Array.isArray(defaults)) return current === undefined ? structuredClone(defaults) : current;
  if (!defaults || typeof defaults !== "object") return current === undefined ? defaults : current;
  const result = current && typeof current === "object" && !Array.isArray(current) ? structuredClone(current) : {};
  for (const [key, value] of Object.entries(defaults)) {
    result[key] = mergeMissing(result[key], value);
  }
  return result;
}

function timestamp() {
  return new Date().toISOString().replace(/[:.]/g, "-");
}

function backupFiles(paths) {
  const backup = path.join(paths.backups, timestamp());
  const sources = [paths.skill, paths.bootstrapHook, paths.hooks, paths.memoryConfig, paths.codexConfig];
  const copied = [];
  for (const source of sources) {
    if (!fs.existsSync(source)) continue;
    const relative = path.relative(paths.codexHome, source);
    const target = path.join(backup, relative);
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.cpSync(source, target, { recursive: true, force: true });
    copied.push(relative);
  }
  fs.mkdirSync(backup, { recursive: true });
  atomicWriteJson(path.join(backup, "manifest.json"), {
    created_at: new Date().toISOString(),
    codex_home: paths.codexHome,
    files: copied,
  });
  return backup;
}

function copyRuntimeSkill(source, target) {
  fs.rmSync(target, { recursive: true, force: true });
  fs.cpSync(source, target, {
    recursive: true,
    filter: (entry) => {
      const normalized = entry.replace(/\\/g, "/");
      return !normalized.includes("/tests/")
        && !normalized.endsWith("/tests")
        && !normalized.includes("/__pycache__/")
        && !normalized.endsWith(".pyc");
    },
  });
  fs.chmodSync(path.join(target, "scripts", "memory-hook.js"), 0o755);
  fs.chmodSync(path.join(target, "scripts", "memoryctl.py"), 0o755);
}

function readJson(file, fallback = {}) {
  if (!fs.existsSync(file)) return fallback;
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

function install(options = {}) {
  const paths = pathsFor(options.codexHome || path.join(os.homedir(), ".codex"));
  const warnings = [];
  if (!commandExists("python3")) warnings.push("python3 is not available; the Memory control plane cannot run");
  if (!commandExists("codex")) warnings.push("codex is not available in PATH; Curator sync will not run until it is available");
  const legacySkills = existingLegacySkills(paths);
  if (legacySkills.length) {
    warnings.push(`legacy V1 Skills were preserved: ${legacySkills.join(", ")}; review the V1 migration guide after V2 validation`);
  }
  if (options.dryRun) {
    return {
      title: `Codex Memory Lite ${VERSION} dry run`,
      lines: [
        `Target: ${paths.codexHome}`,
        `Install skill: ${paths.skill}`,
        `Merge hooks: ${paths.hooks}`,
        "No files were changed.",
      ],
      healthy: warnings.length === 0,
      warnings,
    };
  }

  const defaults = readJson(path.join(PACKAGE_ROOT, "config", "default-config.json"));
  const currentConfig = readJson(paths.memoryConfig, {});
  const memoryConfig = mergeMissing(currentConfig, defaults);
  memoryConfig.installed_version = VERSION;
  const currentHooks = readJson(paths.hooks, { hooks: {} });
  const previousEntries = ownedHookEntries(paths.hooks, currentHooks);
  const hooks = mergeHooks(currentHooks, requiredHooks(paths));
  const entries = ownedHookEntries(paths.hooks, hooks);
  if (entries.length !== 8) throw new Error(`expected 8 installed Hook handlers, found ${entries.length}`);
  const currentToml = fs.existsSync(paths.codexConfig)
    ? fs.readFileSync(paths.codexConfig, "utf8")
    : "";
  const trustedToml = updateTrustConfig(currentToml, entries, previousEntries);

  fs.mkdirSync(paths.codexHome, { recursive: true, mode: 0o700 });
  const backup = backupFiles(paths);
  copyRuntimeSkill(path.join(PACKAGE_ROOT, "skills", "codex-memory"), paths.skill);
  fs.mkdirSync(path.dirname(paths.bootstrapHook), { recursive: true, mode: 0o700 });
  fs.copyFileSync(
    path.join(PACKAGE_ROOT, "ai", "hooks", "codex-memory-bootstrap-first-prompt.js"),
    paths.bootstrapHook,
  );
  fs.chmodSync(paths.bootstrapHook, 0o755);
  atomicWriteJson(paths.memoryConfig, memoryConfig);
  atomicWriteJson(paths.hooks, hooks);
  atomicWrite(paths.codexConfig, trustedToml);

  const checked = doctor({ codexHome: paths.codexHome });
  return {
    title: `Codex Memory Lite ${VERSION} installed`,
    lines: [
      `Codex home: ${paths.codexHome}`,
      `Backup: ${backup}`,
      `Hook handlers: ${entries.length}/8 trusted`,
      checked.healthy ? "Doctor: healthy" : "Doctor: needs attention",
      "Restart ChatGPT/Codex or start a new task to activate the installed Hooks.",
    ],
    healthy: checked.healthy,
    backup,
    warnings: [...new Set([...warnings, ...(checked.warnings || [])])],
  };
}

function parseTrustStates(text) {
  const states = new Map();
  let current = null;
  for (const line of String(text || "").split("\n")) {
    const section = line.match(/^\s*\[hooks\.state\."((?:\\.|[^"])*)"\]\s*(?:#.*)?$/);
    if (section) {
      let key = section[1];
      try {
        key = JSON.parse(`"${key}"`);
      } catch {}
      current = { key, trusted_hash: "", enabled: "true" };
      states.set(key, current);
      continue;
    }
    if (/^\s*\[/.test(line)) {
      current = null;
      continue;
    }
    if (!current) continue;
    const hash = line.match(/^\s*trusted_hash\s*=\s*"([^"]+)"\s*(?:#.*)?$/);
    const enabled = line.match(/^\s*enabled\s*=\s*(true|false)\s*(?:#.*)?$/);
    if (hash) current.trusted_hash = hash[1];
    if (enabled) current.enabled = enabled[1];
  }
  return states;
}

function doctor(options = {}) {
  const paths = pathsFor(options.codexHome || path.join(os.homedir(), ".codex"));
  const issues = [];
  const warnings = [];
  const legacySkills = existingLegacySkills(paths);
  if (legacySkills.length) {
    warnings.push(`legacy V1 Skills are still active: ${legacySkills.join(", ")}`);
  }
  for (const [label, file] of [
    ["skill", path.join(paths.skill, "SKILL.md")],
    ["memory Hook", paths.memoryHook],
    ["bootstrap Hook", paths.bootstrapHook],
    ["control plane", paths.memoryctl],
    ["Hook configuration", paths.hooks],
    ["Memory configuration", paths.memoryConfig],
    ["Codex configuration", paths.codexConfig],
  ]) {
    if (!fs.existsSync(file)) issues.push(`missing ${label}: ${file}`);
  }
  if (!commandExists("python3")) issues.push("python3 is not available");
  if (!commandExists("codex")) issues.push("codex is not available in PATH");

  let entries = [];
  try {
    const hooks = readJson(paths.hooks, { hooks: {} });
    entries = ownedHookEntries(paths.hooks, hooks);
    if (entries.length !== 8) issues.push(`expected 8 installed Hook handlers, found ${entries.length}`);
    const configText = fs.existsSync(paths.codexConfig) ? fs.readFileSync(paths.codexConfig, "utf8") : "";
    if (!hooksFeatureEnabled(configText)) issues.push("Codex Hooks are not enabled in [features]");
    const states = parseTrustStates(configText);
    for (const entry of entries) {
      const candidates = [states.get(entry.rawKey), states.get(entry.fileKey)];
      if (!candidates.some((state) => state && state.enabled !== "false" && state.trusted_hash === entry.hash)) {
        issues.push(`Hook is not trusted: ${entry.event}:${entry.groupIndex}:${entry.handlerIndex}`);
      }
    }
  } catch (error) {
    issues.push(`invalid Hook configuration: ${error.message}`);
  }

  if (!issues.length) {
    const result = childProcess.spawnSync(
      "python3",
      [paths.memoryctl, "fleet-status", "--json"],
      {
        cwd: paths.codexHome,
        env: {
          ...process.env,
          CODEX_HOME: paths.codexHome,
          CODEX_MEMORY_CONFIG: paths.memoryConfig,
          CODEX_MEMORY_INTERNAL: "1",
        },
        encoding: "utf8",
        timeout: 30000,
      },
    );
    if (result.status !== 0) issues.push(`memoryctl fleet-status failed: ${(result.stderr || result.stdout).trim()}`);
  }

  return {
    title: issues.length ? "Codex Memory Lite doctor found problems" : "Codex Memory Lite doctor: healthy",
    lines: issues.length
      ? issues.map((issue) => `- ${issue}`)
      : [
          `Codex home: ${paths.codexHome}`,
          `Version: ${VERSION}`,
          `Hook handlers: ${entries.length}/8 trusted`,
          `Fleet report: ${path.join(paths.codexHome, "memory-v2", "fleet-status.md")}`,
        ],
    healthy: issues.length === 0,
    issues,
    warnings,
  };
}

function uninstall(options = {}) {
  const paths = pathsFor(options.codexHome || path.join(os.homedir(), ".codex"));
  if (options.dryRun) {
    return {
      title: `Codex Memory Lite ${VERSION} uninstall dry run`,
      lines: ["The installed Skill and owned Hook handlers would be removed. Project memory would be kept."],
      healthy: true,
    };
  }
  const backup = backupFiles(paths);
  const hooks = readJson(paths.hooks, { hooks: {} });
  const entries = ownedHookEntries(paths.hooks, hooks);
  atomicWriteJson(paths.hooks, removeOwnedHooks(hooks));
  if (fs.existsSync(paths.codexConfig) && entries.length) {
    const currentToml = fs.readFileSync(paths.codexConfig, "utf8");
    atomicWrite(paths.codexConfig, removeTrustConfig(currentToml, entries));
  }
  fs.rmSync(paths.skill, { recursive: true, force: true });
  fs.rmSync(paths.bootstrapHook, { force: true });
  if (options.purgeConfig) fs.rmSync(paths.memoryConfig, { force: true });
  return {
    title: `Codex Memory Lite ${VERSION} uninstalled`,
    lines: [
      `Backup: ${backup}`,
      "Owned Skill and Hook handlers were removed.",
      options.purgeConfig ? "V2 configuration was removed." : "V2 configuration was kept.",
      "Project .codex-memory folders were not deleted.",
    ],
    healthy: true,
    backup,
  };
}

module.exports = {
  canonicalJson,
  commandHookHash,
  doctor,
  install,
  isOwnedHandler,
  hooksFeatureEnabled,
  mergeHooks,
  ownedHookEntries,
  parseTrustStates,
  pathsFor,
  removeOwnedHooks,
  removeTrustConfig,
  uninstall,
  updateTrustConfig,
};
