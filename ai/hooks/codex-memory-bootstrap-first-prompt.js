#!/usr/bin/env node

const fs = require("fs");
const os = require("os");
const path = require("path");
const childProcess = require("child_process");

const MEMORYCTL = path.resolve(
  __dirname,
  "..",
  "..",
  "skills",
  "codex-memory",
  "scripts",
  "memoryctl.py",
);

const input = fs.readFileSync(0, "utf8").trim();
if (!input) process.exit(0);

let event;
try {
  event = JSON.parse(input);
} catch {
  process.exit(0);
}

if (event.hook_event_name !== "UserPromptSubmit") process.exit(0);

const home = os.homedir();
const codexHome = path.resolve(process.env.CODEX_HOME || path.join(home, ".codex"));
const cwd = path.resolve(String(event.cwd || process.cwd()));

function isInside(child, parent) {
  const rel = path.relative(parent, child);
  return rel === "" || (!rel.startsWith("..") && !path.isAbsolute(rel));
}

function skipDirectory(dir) {
  const exactExcludes = [
    path.resolve("/"),
    path.resolve(home),
  ];
  if (exactExcludes.includes(dir)) return true;

  const treeExcludes = [
    codexHome,
    path.resolve(path.join(home, ".config")),
    path.resolve(path.join(home, ".agents")),
    path.resolve(path.join(home, ".ssh")),
    path.resolve(path.join(home, ".gnupg")),
    path.resolve(path.join(home, ".aws")),
    path.resolve(path.join(home, ".kube")),
    path.resolve("/Applications"),
    path.resolve("/Library"),
    path.resolve("/System"),
    path.resolve("/bin"),
    path.resolve("/dev"),
    path.resolve("/etc"),
    path.resolve("/private"),
    path.resolve("/proc"),
    path.resolve("/sbin"),
    path.resolve("/sys"),
    path.resolve("/usr"),
    path.resolve("/var"),
    path.resolve("/tmp"),
  ];
  return treeExcludes.some((base) => isInside(dir, base));
}

function findProjectRoot(start) {
  const fallbackMarkers = [
    "package.json",
    "pnpm-workspace.yaml",
    "pyproject.toml",
    "Cargo.toml",
    "go.mod",
    "Makefile",
    "README.md",
    "AGENTS.md",
  ];

  let dir = start;
  let fallback = null;
  while (true) {
    if (skipDirectory(dir)) return fallback;
    if (fs.existsSync(path.join(dir, ".git"))) return dir;
    if (!fallback && fallbackMarkers.some((marker) => fs.existsSync(path.join(dir, marker)))) {
      fallback = dir;
    }
    const parent = path.dirname(dir);
    if (parent === dir) return fallback;
    dir = parent;
  }
}

function isProjectExcluded(root) {
  const configFile = path.resolve(
    process.env.CODEX_MEMORY_CONFIG || path.join(codexHome, "memory-v2", "config.json"),
  );
  try {
    const config = JSON.parse(fs.readFileSync(configFile, "utf8"));
    return (config.excluded_project_roots || []).some((entry) => {
      const value = typeof entry === "string" ? entry : entry.path;
      return value && path.resolve(String(value)) === root;
    });
  } catch {
    return false;
  }
}

function hasCompleteV2Memory(root) {
  const memory = path.join(root, ".codex-memory");
  try {
    const manifest = JSON.parse(fs.readFileSync(path.join(memory, "manifest.json"), "utf8"));
    if (manifest.schema_version !== 2) return false;
  } catch {
    return false;
  }
  return [
    path.join(memory, "current.md"),
    path.join(memory, "spec", "index.md"),
    path.join(memory, "tasks", "index.md"),
    path.join(memory, ".runtime", "sessions"),
    path.join(memory, ".runtime", "transactions"),
    path.join(memory, ".runtime", "audit"),
  ].every((entry) => fs.existsSync(entry));
}

function atomicWriteJson(file, value) {
  fs.mkdirSync(path.dirname(file), { recursive: true, mode: 0o700 });
  const temporary = `${file}.tmp-${process.pid}-${Date.now()}`;
  fs.writeFileSync(temporary, `${JSON.stringify(value, null, 2)}\n`, { mode: 0o600 });
  fs.renameSync(temporary, file);
  fs.chmodSync(file, 0o600);
}

function registerAndBootstrapV2(root) {
  const configFile = path.resolve(
    process.env.CODEX_MEMORY_CONFIG || path.join(codexHome, "memory-v2", "config.json"),
  );
  const lock = `${configFile}.lock`;
  fs.mkdirSync(path.dirname(configFile), { recursive: true, mode: 0o700 });
  try {
    if (fs.existsSync(lock) && Date.now() - fs.statSync(lock).mtimeMs > 30000) {
      fs.rmSync(lock, { force: true });
    }
  } catch {}

  let lockFd;
  try {
    lockFd = fs.openSync(lock, "wx", 0o600);
  } catch (error) {
    if (error.code === "EEXIST") throw new Error("V2 config is being updated; retry on the next prompt");
    throw error;
  }

  let registered = false;
  try {
    const config = JSON.parse(fs.readFileSync(configFile, "utf8"));
    if (!config.enabled) throw new Error(`Codex Memory V2 is disabled in ${configFile}`);
    const excluded = (config.excluded_project_roots || []).map((entry) =>
      path.resolve(String(typeof entry === "string" ? entry : entry.path || "")),
    );
    if (excluded.includes(root)) throw new Error(`project is explicitly reserved for V1: ${root}`);
    const roots = (config.project_roots || []).map((entry) => path.resolve(String(entry)));
    if (!roots.includes(root)) {
      config.project_roots = [...roots, root];
      atomicWriteJson(configFile, config);
      registered = true;
    }

    const legacyMemory = fs.existsSync(path.join(root, ".codex-memory", "current.md"));
    const action = legacyMemory ? "migrate-v1" : "bootstrap";
    const result = childProcess.spawnSync(
      "python3",
      [MEMORYCTL, action, "--project-root", root, "--json"],
      {
        cwd: root,
        env: {
          ...process.env,
          CODEX_MEMORY_CONFIG: configFile,
          CODEX_MEMORY_INTERNAL: "1",
        },
        encoding: "utf8",
        timeout: 30000,
        maxBuffer: 4 * 1024 * 1024,
      },
    );
    if (result.error) throw result.error;
    if (result.status !== 0) {
      throw new Error((result.stderr || result.stdout || `memoryctl exited ${result.status}`).trim());
    }
    return { action, configFile, registered };
  } finally {
    if (lockFd !== undefined) fs.closeSync(lockFd);
    fs.rmSync(lock, { force: true });
  }
}

if (!fs.existsSync(cwd) || !fs.statSync(cwd).isDirectory()) process.exit(0);

const projectRoot = findProjectRoot(cwd);
if (!projectRoot) process.exit(0);
if (skipDirectory(projectRoot)) process.exit(0);

if (isProjectExcluded(projectRoot)) process.exit(0);
if (hasCompleteV2Memory(projectRoot)) process.exit(0);
let additionalContext;
try {
  const initialized = registerAndBootstrapV2(projectRoot);
  additionalContext = [
    `Codex Memory V2 was initialized automatically for PROJECT_ROOT=${projectRoot}.`,
    initialized.registered ? `The project was added to ${initialized.configFile}.` : "The project was already enabled.",
    `Initialization action: ${initialized.action}.`,
    "Do not create or modify the project AGENTS.md for memory. Daily synchronization is handled by the V2 Hook.",
    "Continue with the user's requested task.",
  ].join("\n");
} catch (error) {
  additionalContext = [
    `Automatic Codex Memory V2 initialization failed for PROJECT_ROOT=${projectRoot}.`,
    `Error: ${String(error.message || error).slice(0, 1000)}`,
    "The Hook will retry on the next prompt because no success marker was written.",
    "Use codex-memory doctor before making any manual repair.",
  ].join("\n");
}

process.stdout.write(JSON.stringify({
  hookSpecificOutput: {
    hookEventName: "UserPromptSubmit",
    additionalContext,
  },
}) + "\n");
