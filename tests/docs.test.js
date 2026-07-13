"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const ROOT = path.resolve(__dirname, "..");
const INSTALL = "npx --yes --package=github:AKin-lvyifang/codex-memory-lite codex-memory-lite install";

function markdownFiles() {
  const files = ["README.md", "README.zh-CN.md", "CHANGELOG.md", "CHANGELOG.zh-CN.md"];
  const queue = [path.join(ROOT, "docs")];
  while (queue.length) {
    const current = queue.shift();
    for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
      const absolute = path.join(current, entry.name);
      if (entry.isDirectory()) queue.push(absolute);
      else if (entry.isFile() && entry.name.endsWith(".md")) files.push(path.relative(ROOT, absolute));
    }
  }
  return files;
}

function localTargets(text) {
  const values = [];
  for (const pattern of [/[!?]?\[[^\]]*\]\(([^)]+)\)/g, /(?:href|src)="([^"]+)"/g]) {
    for (const match of text.matchAll(pattern)) values.push(match[1]);
  }
  return values.filter((value) => !/^(?:https?:|mailto:|#)/.test(value));
}

test("all local Markdown links resolve", () => {
  const missing = [];
  for (const relative of markdownFiles()) {
    const file = path.join(ROOT, relative);
    const text = fs.readFileSync(file, "utf8");
    for (const target of localTargets(text)) {
      const clean = decodeURIComponent(target.split("#")[0]);
      if (!clean) continue;
      const resolved = path.resolve(path.dirname(file), clean);
      if (!fs.existsSync(resolved)) missing.push(`${relative} -> ${target}`);
    }
  }
  assert.deepEqual(missing, []);
});

test("README first-run paths and versions match the package", () => {
  const pkg = JSON.parse(fs.readFileSync(path.join(ROOT, "package.json"), "utf8"));
  const version = fs.readFileSync(path.join(ROOT, "VERSION"), "utf8").trim();
  assert.equal(version, pkg.version);
  for (const file of ["README.md", "README.zh-CN.md"]) {
    const text = fs.readFileSync(path.join(ROOT, file), "utf8");
    assert.match(text, new RegExp(`v${pkg.version.replace(/\./g, "\\.")}`));
    assert.equal(text.includes(INSTALL), true);
    assert.equal(text.includes("https://github.com/AKin-lvyifang/codex-memory-lite"), true);
    assert.equal(text.includes("doctor"), true);
  }
  assert.equal(fs.existsSync(path.join(ROOT, "docs", "images", `codex-memory-lite-v${version}.png`)), true);
});
