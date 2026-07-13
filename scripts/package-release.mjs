#!/usr/bin/env node

import childProcess from "node:child_process";
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const pkg = JSON.parse(fs.readFileSync(path.join(root, "package.json"), "utf8"));
const version = fs.readFileSync(path.join(root, "VERSION"), "utf8").trim();
if (version !== pkg.version) throw new Error(`VERSION (${version}) does not match package.json (${pkg.version})`);

const release = path.join(root, "release");
const staging = path.join(release, ".staging");
fs.rmSync(release, { recursive: true, force: true });
fs.mkdirSync(release, { recursive: true });

function run(command, args, options = {}) {
  const result = childProcess.spawnSync(command, args, {
    cwd: options.cwd || root,
    encoding: "utf8",
    stdio: options.capture ? "pipe" : "inherit",
  });
  if (result.status !== 0) throw new Error(`${command} failed: ${(result.stderr || result.stdout || "").trim()}`);
  return String(result.stdout || "").trim();
}

const packed = JSON.parse(run("npm", ["pack", "--pack-destination", release, "--json"], { capture: true }));
const tgz = path.join(release, packed[0].filename);
fs.mkdirSync(staging, { recursive: true });
run("tar", ["-xzf", tgz, "-C", staging]);
const packageFolder = path.join(staging, "package");
const releaseFolderName = `codex-memory-lite-${version}`;
const releaseFolder = path.join(staging, releaseFolderName);
fs.renameSync(packageFolder, releaseFolder);
const fixedTime = new Date("1985-10-26T00:00:00.000Z");
const timeQueue = [releaseFolder];
const timeEntries = [];
while (timeQueue.length) {
  const current = timeQueue.shift();
  timeEntries.push(current);
  if (!fs.statSync(current).isDirectory()) continue;
  for (const entry of fs.readdirSync(current)) timeQueue.push(path.join(current, entry));
}
for (const entry of timeEntries.reverse()) fs.utimesSync(entry, fixedTime, fixedTime);
const zip = path.join(release, `${releaseFolderName}.zip`);
run("zip", ["-Xqry", zip, releaseFolderName], { cwd: staging });

function sha256(file) {
  return crypto.createHash("sha256").update(fs.readFileSync(file)).digest("hex");
}

const assets = [tgz, zip];
const sums = assets.map((file) => `${sha256(file)}  ${path.basename(file)}`).join("\n");
fs.writeFileSync(path.join(release, "SHA256SUMS"), `${sums}\n`);
fs.rmSync(staging, { recursive: true, force: true });

process.stdout.write(`${JSON.stringify({
  version,
  assets: assets.map((file) => ({
    name: path.basename(file),
    bytes: fs.statSync(file).size,
    sha256: sha256(file),
  })),
}, null, 2)}\n`);
