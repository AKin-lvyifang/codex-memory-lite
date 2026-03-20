#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  install-skill-pack.sh <language> [target-skill-dir]

Arguments:
  <language>         en | english | zh | zh-cn | cn | chinese
  [target-skill-dir] Optional. Defaults to "${CODEX_HOME:-$HOME/.codex}/skills"
EOF
}

if [[ "${1:-}" == "" ]] || [[ "${1:-}" == "--help" ]] || [[ "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

language_input="${1:-}"
target_skill_dir="${2:-${CODEX_HOME:-$HOME/.codex}/skills}"

language_normalized="$(printf '%s' "$language_input" | tr '[:upper:]' '[:lower:]')"

case "$language_normalized" in
  en|english)
    pack_dir="skills"
    pack_label="English"
    ;;
  zh|zh-cn|cn|chinese)
    pack_dir="skills.zh-CN"
    pack_label="Simplified Chinese"
    ;;
  *)
    echo "Unsupported language: $language_input" >&2
    usage >&2
    exit 1
    ;;
esac

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
repo_url="${CODEX_MEMORY_LITE_REPO_URL:-https://github.com/AKin-lvyifang/codex-memory-lite.git}"

ensure_repo_checkout() {
  if [[ -d "$repo_root/$pack_dir" ]]; then
    printf '%s\n' "$repo_root"
    return 0
  fi

  tmp_dir="$(mktemp -d)"
  git clone --depth=1 "$repo_url" "$tmp_dir/repo" >/dev/null 2>&1
  printf '%s\n' "$tmp_dir/repo"
}

source_root="$(ensure_repo_checkout)"
cleanup_tmp=""

if [[ "$source_root" != "$repo_root" ]]; then
  cleanup_tmp="$(cd "$source_root/.." && pwd)"
fi

cleanup() {
  if [[ -n "$cleanup_tmp" ]] && [[ -d "$cleanup_tmp" ]]; then
    rm -rf "$cleanup_tmp"
  fi
}

trap cleanup EXIT

skills=(
  "codex-memory-bootstrap"
  "codex-memory-task-init"
  "codex-memory-sync"
  "codex-memory-promote-global"
)

mkdir -p "$target_skill_dir"

for skill in "${skills[@]}"; do
  source_path="$source_root/$pack_dir/$skill"
  target_path="$target_skill_dir/$skill"

  if [[ ! -d "$source_path" ]]; then
    echo "Missing source skill directory: $source_path" >&2
    exit 1
  fi

  rm -rf "$target_path"
  cp -R "$source_path" "$target_path"
done

echo "Installed the $pack_label skill pack into: $target_skill_dir"
echo "Installed skills:"
for skill in "${skills[@]}"; do
  echo "- $skill"
done
