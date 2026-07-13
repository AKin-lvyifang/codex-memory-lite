#!/usr/bin/env node

"use strict";

const path = require("path");
const {
  doctor,
  install,
  uninstall,
} = require("../lib/installer");
const { version: VERSION } = require("../package.json");

function usage() {
  process.stdout.write(`Codex Memory Lite

Usage:
  codex-memory-lite install [--codex-home PATH] [--dry-run] [--json]
  codex-memory-lite update [--codex-home PATH] [--dry-run] [--json]
  codex-memory-lite doctor [--codex-home PATH] [--json]
  codex-memory-lite uninstall [--codex-home PATH] [--purge-config] [--json]
  codex-memory-lite version

Install and update always back up existing Codex Memory files first.
Uninstall keeps project .codex-memory folders and V2 configuration by default.
`);
}

function parseArgs(argv) {
  const values = [...argv];
  let command = "install";
  if (values[0] && !values[0].startsWith("-")) command = values.shift();
  const options = {
    codexHome: process.env.CODEX_HOME || path.join(require("os").homedir(), ".codex"),
    dryRun: false,
    json: false,
    purgeConfig: false,
  };
  while (values.length) {
    const value = values.shift();
    if (value === "--codex-home") {
      const target = values.shift();
      if (!target) throw new Error("--codex-home requires a path");
      options.codexHome = path.resolve(target);
    } else if (value === "--dry-run") {
      options.dryRun = true;
    } else if (value === "--json") {
      options.json = true;
    } else if (value === "--purge-config") {
      options.purgeConfig = true;
    } else if (value === "--help" || value === "-h") {
      options.help = true;
    } else if (value === "--version" || value === "-v") {
      options.version = true;
    } else {
      throw new Error(`unknown option: ${value}`);
    }
  }
  return { command, options };
}

function printResult(result, asJson) {
  if (asJson) {
    process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
    return;
  }
  process.stdout.write(`${result.title}\n`);
  for (const line of result.lines || []) process.stdout.write(`${line}\n`);
  for (const warning of result.warnings || []) process.stdout.write(`Warning: ${warning}\n`);
}

async function main() {
  const { command, options } = parseArgs(process.argv.slice(2));
  if (options.help || command === "help") {
    usage();
    return;
  }
  if (options.version || command === "version") {
    process.stdout.write(`${VERSION}\n`);
    return;
  }
  let result;
  if (command === "install" || command === "update") {
    result = install(options);
  } else if (command === "doctor") {
    result = doctor(options);
  } else if (command === "uninstall") {
    result = uninstall(options);
  } else {
    throw new Error(`unknown command: ${command}`);
  }
  printResult(result, options.json);
  if (result.healthy === false) process.exitCode = 1;
}

main().catch((error) => {
  process.stderr.write(`Codex Memory Lite: ${error.message}\n`);
  process.exitCode = 1;
});
