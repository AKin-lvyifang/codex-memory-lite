#!/usr/bin/env node

import childProcess from "node:child_process";
import crypto from "node:crypto";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const pkg = JSON.parse(fs.readFileSync(path.join(root, "package.json"), "utf8"));
const release = path.join(root, "release");
const tgz = path.join(release, `codex-memory-lite-${pkg.version}.tgz`);
const zip = path.join(release, `codex-memory-lite-${pkg.version}.zip`);
const sumsFile = path.join(release, "SHA256SUMS");

function run(command, args, options = {}) {
  const result = childProcess.spawnSync(command, args, {
    cwd: options.cwd || root,
    env: options.env || process.env,
    encoding: "utf8",
    timeout: options.timeout || 120000,
  });
  if (result.status !== 0) throw new Error(`${command} failed: ${(result.stderr || result.stdout || "").trim()}`);
  return result.stdout.trim();
}

function sha256(file) {
  return crypto.createHash("sha256").update(fs.readFileSync(file)).digest("hex");
}

for (const file of [tgz, zip, sumsFile]) {
  if (!fs.existsSync(file)) throw new Error(`missing release asset: ${file}`);
}

const expected = new Map(fs.readFileSync(sumsFile, "utf8").trim().split("\n").map((line) => {
  const match = line.match(/^([a-f0-9]{64})  (.+)$/);
  if (!match) throw new Error(`invalid SHA256SUMS line: ${line}`);
  return [match[2], match[1]];
}));
for (const file of [tgz, zip]) {
  if (expected.get(path.basename(file)) !== sha256(file)) throw new Error(`checksum mismatch: ${file}`);
}

const tarEntries = run("tar", ["-tzf", tgz]).split("\n").filter(Boolean);
const zipEntries = run("unzip", ["-Z1", zip]).split("\n").filter(Boolean);
const forbiddenDirectory = /(?:^|\/)(?:tests?|release|node_modules|\.codex-memory)(?:\/|$)/;
const forbiddenFile = /(?:^|\/)(?:AGENTS\.md|\.env[^/]*)(?:$|\/)/;
for (const entry of [...tarEntries, ...zipEntries]) {
  if (forbiddenDirectory.test(entry) || forbiddenFile.test(entry)) {
    throw new Error(`forbidden package entry: ${entry}`);
  }
}

const temporary = fs.mkdtempSync(path.join(os.tmpdir(), "codex-memory-release-verify-"));
try {
  const bin = path.join(temporary, "bin");
  const codexHome = path.join(temporary, "Codex Home");
  const inspected = path.join(temporary, "inspected");
  fs.mkdirSync(bin, { recursive: true });
  fs.mkdirSync(inspected, { recursive: true });
  run("tar", ["-xzf", tgz, "-C", inspected]);

  const contentRisks = [
    { label: "personal macOS path", pattern: /\/Users\/lyuakin\b/ },
    { label: "OpenAI-style secret", pattern: /\bsk-[A-Za-z0-9_-]{20,}\b/ },
    { label: "GitHub-style token", pattern: /\bgh[oprsu]_[A-Za-z0-9]{20,}\b/ },
    { label: "AWS access key", pattern: /\bAKIA[0-9A-Z]{16}\b/ },
    { label: "private key", pattern: /-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----/ },
  ];
  const queue = [path.join(inspected, "package")];
  while (queue.length) {
    const current = queue.shift();
    for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
      const absolute = path.join(current, entry.name);
      if (entry.isDirectory()) {
        queue.push(absolute);
        continue;
      }
      if (!entry.isFile() || fs.statSync(absolute).size > 2 * 1024 * 1024) continue;
      const data = fs.readFileSync(absolute);
      if (data.includes(0)) continue;
      const content = data.toString("utf8");
      for (const risk of contentRisks) {
        if (risk.pattern.test(content)) throw new Error(`${risk.label} found in ${path.relative(inspected, absolute)}`);
      }
    }
  }

  const python = run("sh", ["-c", "command -v python3"]);
  fs.symlinkSync(python, path.join(bin, "python3"));
  const codex = path.join(bin, "codex");
  fs.writeFileSync(codex, "#!/bin/sh\nprintf 'codex-cli 0.0.0-release-test\\n'\n", { mode: 0o755 });
  const env = { ...process.env, PATH: `${bin}:${process.env.PATH || ""}` };

  const packageArgs = ["--yes", `--package=${tgz}`, "codex-memory-lite"];
  run("sh", [path.join(root, "scripts", "install.sh")], {
    env: { ...env, CODEX_HOME: codexHome, CODEX_MEMORY_PACKAGE: tgz },
  });
  const doctor = JSON.parse(run("npx", [...packageArgs, "doctor", "--codex-home", codexHome, "--json"], { env }));
  if (!doctor.healthy) throw new Error(`installed package doctor failed: ${JSON.stringify(doctor.issues)}`);
  run("npx", [...packageArgs, "uninstall", "--codex-home", codexHome, "--json"], { env });
  if (fs.existsSync(path.join(codexHome, "skills", "codex-memory"))) throw new Error("uninstall left the runtime Skill behind");
} finally {
  fs.rmSync(temporary, { recursive: true, force: true });
}

process.stdout.write(`Verified Codex Memory Lite ${pkg.version}: archives, checksums, install, doctor, and uninstall passed.\n`);
