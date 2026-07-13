"use strict";

const assert = require("node:assert/strict");
const childProcess = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

const {
  hooksFeatureEnabled,
  ownedHookEntries,
  parseTrustStates,
  pathsFor,
} = require("../lib/installer");

const ROOT = path.resolve(__dirname, "..");
const CLI = path.join(ROOT, "bin", "codex-memory-lite.js");

function makeFixture() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "codex-memory-lite test-"));
  const home = path.join(root, "Codex Home $safe");
  const bin = path.join(root, "bin");
  fs.mkdirSync(bin, { recursive: true });
  const python = childProcess.execFileSync("sh", ["-c", "command -v python3"], { encoding: "utf8" }).trim();
  fs.symlinkSync(python, path.join(bin, "python3"));
  const codex = path.join(bin, "codex");
  fs.writeFileSync(codex, "#!/bin/sh\nprintf 'codex-cli 0.0.0-test\\n'\n", { mode: 0o755 });
  return {
    root,
    home,
    env: { ...process.env, PATH: `${bin}:${process.env.PATH || ""}` },
    cleanup() {
      fs.rmSync(root, { recursive: true, force: true });
    },
  };
}

function runCli(fixture, args, expectedStatus = 0) {
  const result = childProcess.spawnSync(process.execPath, [CLI, ...args], {
    cwd: ROOT,
    env: fixture.env,
    encoding: "utf8",
    timeout: 60000,
  });
  assert.equal(result.status, expectedStatus, result.stderr || result.stdout);
  return result;
}

function seedExistingInstall(home) {
  const paths = pathsFor(home);
  fs.mkdirSync(paths.skill, { recursive: true });
  fs.writeFileSync(path.join(paths.skill, "KEEP.txt"), "old skill\n");
  const legacy = path.join(home, "skills", "codex-memory-sync");
  fs.mkdirSync(legacy, { recursive: true });
  fs.writeFileSync(path.join(legacy, "SKILL.md"), "legacy must survive\n");
  fs.mkdirSync(path.dirname(paths.memoryConfig), { recursive: true });
  fs.writeFileSync(paths.memoryConfig, `${JSON.stringify({
    enabled: true,
    sync: { active_task_event_threshold: 77 },
    custom: { keep: "yes" },
  }, null, 2)}\n`);
  fs.writeFileSync(paths.hooks, `${JSON.stringify({
    metadata: { keep: true },
    hooks: {
      PreToolUse: [{
        matcher: "Read",
        hooks: [{ type: "command", command: "printf keep-pre", timeout: 12 }],
      }],
      UserPromptSubmit: [{
        hooks: [{ type: "command", command: "printf keep-prompt" }],
      }],
      Stop: [{
        hooks: [{ type: "command", command: "node /old/codex-memory/scripts/memory-hook.js" }],
      }, {
        hooks: [{ type: "command", command: "node /older/codex-memory/scripts/memory-hook.js" }],
      }],
    },
  }, null, 2)}\n`);
  const staleTrustKey = `${paths.hooks}:stop:1:0`;
  fs.writeFileSync(paths.codexConfig, [
    'model = "keep-model"',
    "",
    "[features]",
    "hooks = false",
    "memories = true",
    "",
    "[other]",
    "hooks = false",
    "",
    '[hooks.state."unrelated"]',
    "enabled = true",
    'trusted_hash = "sha256:keep"',
    "",
    `[hooks.state."${staleTrustKey}"]`,
    "enabled = true",
    'trusted_hash = "sha256:stale-owned-hook"',
    "",
  ].join("\n"));
  return paths;
}

test("install is additive, trusted, and idempotent", () => {
  const fixture = makeFixture();
  try {
    const paths = seedExistingInstall(fixture.home);
    const first = runCli(fixture, ["install", "--codex-home", fixture.home, "--json"]);
    const firstResult = JSON.parse(first.stdout);
    assert.equal(firstResult.healthy, true);
    assert.equal(firstResult.warnings.some((warning) => warning.includes("codex-memory-sync")), true);
    assert.equal(fs.existsSync(path.join(paths.skill, "KEEP.txt")), false);
    assert.equal(fs.existsSync(path.join(paths.skill, "SKILL.md")), true);
    assert.equal(fs.existsSync(paths.bootstrapHook), true);
    assert.equal(fs.readFileSync(path.join(fixture.home, "skills", "codex-memory-sync", "SKILL.md"), "utf8"), "legacy must survive\n");

    const hooks = JSON.parse(fs.readFileSync(paths.hooks, "utf8"));
    assert.deepEqual(hooks.metadata, { keep: true });
    assert.equal(hooks.hooks.PreToolUse[0].hooks[0].command, "printf keep-pre");
    assert.equal(hooks.hooks.UserPromptSubmit[0].hooks[0].command, "printf keep-prompt");
    const entries = ownedHookEntries(paths.hooks, hooks);
    assert.equal(entries.length, 8);

    const memoryConfig = JSON.parse(fs.readFileSync(paths.memoryConfig, "utf8"));
    assert.equal(memoryConfig.sync.active_task_event_threshold, 77);
    assert.equal(memoryConfig.sync.max_pending_age_seconds, 1800);
    assert.deepEqual(memoryConfig.custom, { keep: "yes" });
    assert.equal(memoryConfig.installed_version, "2.0.0");

    const toml = fs.readFileSync(paths.codexConfig, "utf8");
    assert.equal(hooksFeatureEnabled(toml), true);
    assert.match(toml, /\[other\]\nhooks = false/);
    const trust = parseTrustStates(toml);
    assert.deepEqual(trust.get("unrelated"), {
      key: "unrelated",
      trusted_hash: "sha256:keep",
      enabled: "true",
    });
    assert.equal(trust.has(`${paths.hooks}:stop:1:0`), false);
    for (const entry of entries) {
      const states = [trust.get(entry.rawKey), trust.get(entry.fileKey)];
      assert.equal(states.some((state) => state && state.trusted_hash === entry.hash), true);
    }

    const firstHooks = fs.readFileSync(paths.hooks, "utf8");
    const firstToml = fs.readFileSync(paths.codexConfig, "utf8");
    const second = runCli(fixture, ["update", "--codex-home", fixture.home, "--json"]);
    assert.equal(JSON.parse(second.stdout).healthy, true);
    assert.equal(fs.readFileSync(paths.hooks, "utf8"), firstHooks);
    assert.equal(fs.readFileSync(paths.codexConfig, "utf8"), firstToml);
    assert.equal(ownedHookEntries(paths.hooks, JSON.parse(firstHooks)).length, 8);

    const backups = fs.readdirSync(paths.backups);
    assert.equal(backups.length, 2);
    for (const backup of backups) {
      assert.equal(fs.existsSync(path.join(paths.backups, backup, "manifest.json")), true);
    }

    const doctor = runCli(fixture, ["doctor", "--codex-home", fixture.home, "--json"]);
    assert.equal(JSON.parse(doctor.stdout).healthy, true);
  } finally {
    fixture.cleanup();
  }
});

test("uninstall removes only owned runtime and keeps project data and other Hooks", () => {
  const fixture = makeFixture();
  try {
    const paths = seedExistingInstall(fixture.home);
    runCli(fixture, ["install", "--codex-home", fixture.home, "--json"]);
    const projectMemory = path.join(fixture.root, "project", ".codex-memory");
    fs.mkdirSync(projectMemory, { recursive: true });
    fs.writeFileSync(path.join(projectMemory, "current.md"), "keep project memory\n");

    const result = runCli(fixture, ["uninstall", "--codex-home", fixture.home, "--json"]);
    assert.equal(JSON.parse(result.stdout).healthy, true);
    assert.equal(fs.existsSync(paths.skill), false);
    assert.equal(fs.existsSync(paths.bootstrapHook), false);
    assert.equal(fs.existsSync(paths.memoryConfig), true);
    assert.equal(fs.readFileSync(path.join(projectMemory, "current.md"), "utf8"), "keep project memory\n");

    const hooks = JSON.parse(fs.readFileSync(paths.hooks, "utf8"));
    assert.equal(ownedHookEntries(paths.hooks, hooks).length, 0);
    assert.equal(hooks.hooks.PreToolUse[0].hooks[0].command, "printf keep-pre");
    assert.equal(hooks.hooks.UserPromptSubmit[0].hooks[0].command, "printf keep-prompt");
    const trust = parseTrustStates(fs.readFileSync(paths.codexConfig, "utf8"));
    assert.equal(trust.size, 1);
    assert.equal(trust.get("unrelated").trusted_hash, "sha256:keep");
  } finally {
    fixture.cleanup();
  }
});

test("dry-run changes nothing and invalid JSON fails before replacement", () => {
  const fixture = makeFixture();
  try {
    const dryHome = path.join(fixture.root, "dry home");
    runCli(fixture, ["install", "--codex-home", dryHome, "--dry-run", "--json"]);
    assert.equal(fs.existsSync(dryHome), false);

    const paths = pathsFor(fixture.home);
    fs.mkdirSync(paths.skill, { recursive: true });
    fs.writeFileSync(path.join(paths.skill, "KEEP.txt"), "must survive\n");
    fs.mkdirSync(path.dirname(paths.hooks), { recursive: true });
    fs.writeFileSync(paths.hooks, "not-json\n");
    const result = runCli(fixture, ["install", "--codex-home", fixture.home, "--json"], 1);
    assert.match(result.stderr, /Unexpected token|JSON/);
    assert.equal(fs.readFileSync(path.join(paths.skill, "KEEP.txt"), "utf8"), "must survive\n");
    assert.equal(fs.existsSync(paths.backups), false);
  } finally {
    fixture.cleanup();
  }
});

test("Hook feature detection is scoped to the features table", () => {
  assert.equal(hooksFeatureEnabled("[other]\nhooks = false\n[features]\nhooks = true\n"), true);
  assert.equal(hooksFeatureEnabled("[other]\nhooks = true\n[features]\nhooks = false\n"), false);
  assert.equal(hooksFeatureEnabled("hooks = true\n"), false);
});
