#!/bin/sh

set -eu

PACKAGE_SPEC="${CODEX_MEMORY_PACKAGE:-github:AKin-lvyifang/codex-memory-lite}"

if ! command -v node >/dev/null 2>&1; then
  printf '%s\n' "Codex Memory Lite requires Node.js 18 or newer." >&2
  exit 1
fi

if ! command -v npx >/dev/null 2>&1; then
  printf '%s\n' "Codex Memory Lite requires npx (included with npm)." >&2
  exit 1
fi

set -- install
if [ -n "${CODEX_HOME:-}" ]; then
  set -- "$@" --codex-home "$CODEX_HOME"
fi

exec npx --yes --package="$PACKAGE_SPEC" codex-memory-lite "$@"
