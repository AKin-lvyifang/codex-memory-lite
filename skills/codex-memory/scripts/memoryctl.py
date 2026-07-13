#!/usr/bin/env python3
"""Deterministic control plane for Codex Memory V2."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


CODEX_HOME = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))).expanduser().resolve()
DEFAULT_CONFIG = CODEX_HOME / "memory-v2" / "config.json"
MANIFEST = "manifest.json"
RUNTIME = ".runtime"
SCHEMA_VERSION = 2
MAX_PROPOSED_FILE_BYTES = 96 * 1024
WRITABLE_MEMORY_BASENAMES = {"current.md", "brief.md", "decisions.md", "refs.md"}
ALLOWED_CATEGORIES = {
    "progress",
    "decision",
    "next_step",
    "constraint",
    "reference",
    "task_status",
    "skip",
    "other",
}
HOOK_EVENT_LABELS = {
    "PreToolUse": "pre_tool_use",
    "PermissionRequest": "permission_request",
    "PostToolUse": "post_tool_use",
    "PreCompact": "pre_compact",
    "PostCompact": "post_compact",
    "SessionStart": "session_start",
    "UserPromptSubmit": "user_prompt_submit",
    "SubagentStart": "subagent_start",
    "SubagentStop": "subagent_stop",
    "Stop": "stop",
}
HOOK_MATCHER_EVENTS = {
    "PreToolUse",
    "PermissionRequest",
    "PostToolUse",
    "PreCompact",
    "PostCompact",
    "SessionStart",
    "SubagentStart",
    "SubagentStop",
}


class MemoryCtlError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MemoryCtlError(f"invalid JSON: {path}: {exc}") from exc


def atomic_write_bytes(path: Path, data: bytes, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.tmp-{uuid.uuid4().hex}")
    fd = os.open(str(temp), os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
        os.chmod(path, mode)
    finally:
        if temp.exists():
            temp.unlink()


def atomic_write_text(path: Path, text: str, mode: int = 0o600) -> None:
    atomic_write_bytes(path, text.encode("utf-8"), mode=mode)


def atomic_write_json(path: Path, value: Any, mode: int = 0o600) -> None:
    atomic_write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n", mode=mode)


def append_jsonl(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)


def audit_path(root: Path) -> Path:
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    return runtime_dir(root) / "audit" / f"{month}.jsonl"


def append_audit(root: Path, value: Dict[str, Any]) -> None:
    append_jsonl(audit_path(root), {"recorded_at": utc_now(), **value})


def command_hook_hash(event_name: str, group: Dict[str, Any], handler: Dict[str, Any]) -> str:
    normalized_handler: Dict[str, Any] = {
        "type": "command",
        "command": str(handler.get("command") or ""),
        "timeout": max(1, int(handler.get("timeout", 600))),
        "async": bool(handler.get("async", False)),
    }
    if handler.get("statusMessage") is not None:
        normalized_handler["statusMessage"] = str(handler["statusMessage"])
    identity: Dict[str, Any] = {
        "event_name": HOOK_EVENT_LABELS[event_name],
        "hooks": [normalized_handler],
    }
    if event_name in HOOK_MATCHER_EVENTS and group.get("matcher"):
        identity["matcher"] = str(group["matcher"])
    digest = sha256_bytes(canonical_json(identity).encode("utf-8"))
    return f"sha256:{digest}"


def parse_hook_trust_states(config_text: str) -> Dict[str, Dict[str, str]]:
    states: Dict[str, Dict[str, str]] = {}
    pattern = re.compile(
        r'(?ms)^\[hooks\.state\."([^"]+)"\]\s*$\n(.*?)(?=^\[|\Z)'
    )
    for match in pattern.finditer(config_text):
        body = match.group(2)
        trusted = re.search(r'(?m)^\s*trusted_hash\s*=\s*"([^"]+)"\s*$', body)
        enabled = re.search(r"(?m)^\s*enabled\s*=\s*(true|false)\s*$", body)
        states[match.group(1)] = {
            "trusted_hash": trusted.group(1) if trusted else "",
            "enabled": enabled.group(1) if enabled else "true",
        }
    return states


def config_path() -> Path:
    return Path(os.environ.get("CODEX_MEMORY_CONFIG", str(DEFAULT_CONFIG))).expanduser().resolve()


def load_config() -> Dict[str, Any]:
    config = load_json(config_path(), default={}) or {}
    if not config.get("enabled", False):
        raise MemoryCtlError(f"Codex Memory V2 is disabled in {config_path()}")
    return config


def resolve_project_root(value: str) -> Path:
    root = Path(value).expanduser().resolve()
    if not root.is_dir():
        raise MemoryCtlError(f"project root is not a directory: {root}")
    home = Path.home().resolve()
    blocked = {
        Path("/").resolve(),
        home,
        CODEX_HOME,
        (home / ".agents").resolve(),
    }
    if root in blocked:
        raise MemoryCtlError(f"refusing unsafe project root: {root}")
    return root


def ensure_allowed(root: Path, config: Dict[str, Any]) -> None:
    allowed = {Path(item).expanduser().resolve() for item in config.get("project_roots", [])}
    if root not in allowed:
        raise MemoryCtlError(f"project is not enabled for the V2 pilot: {root}")


def memory_dir(root: Path) -> Path:
    return root / ".codex-memory"


def runtime_dir(root: Path) -> Path:
    return memory_dir(root) / RUNTIME


def safe_session_id(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    if not safe:
        raise MemoryCtlError("session id is empty")
    return safe[:160]


def project_tracking_mode(root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "ls-files", ".codex-memory"],
            cwd=root,
            text=True,
            capture_output=True,
            timeout=5,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return "shared"
    except (OSError, subprocess.SubprocessError):
        pass
    return "local"


def ensure_runtime_ignored(root: Path) -> None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-path", "info/exclude"],
            cwd=root,
            text=True,
            capture_output=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return
    if result.returncode != 0 or not result.stdout.strip():
        return
    exclude = Path(result.stdout.strip())
    if not exclude.is_absolute():
        exclude = (root / exclude).resolve()
    exclude.parent.mkdir(parents=True, exist_ok=True)
    current = exclude.read_text(encoding="utf-8") if exclude.exists() else ""
    rule = "/.codex-memory/.runtime/"
    if rule not in {line.strip() for line in current.splitlines()}:
        suffix = "" if not current or current.endswith("\n") else "\n"
        with exclude.open("a", encoding="utf-8") as handle:
            handle.write(f"{suffix}{rule}\n")


def minimal_current() -> str:
    return (
        "# 当前项目状态\n\n"
        "- 尚未建立长期任务。\n\n"
        "# 活跃任务\n\n"
        "- 无。\n\n"
        "# 风险 / 下一步\n\n"
        "- 按当前任务需要更新。\n"
    )


def bootstrap(root: Path, config: Dict[str, Any]) -> Dict[str, Any]:
    ensure_allowed(root, config)
    if (root / ".codex-memory-disabled").exists():
        raise MemoryCtlError(f"project disabled memory with {root / '.codex-memory-disabled'}")

    mem = memory_dir(root)
    runtime = runtime_dir(root)
    for path in (
        mem,
        mem / "spec",
        mem / "tasks",
        mem / "archive",
        runtime,
        runtime / "sessions",
        runtime / "transactions",
        runtime / "audit",
    ):
        path.mkdir(parents=True, exist_ok=True)
    os.chmod(runtime, 0o700)

    created: List[str] = []
    current = mem / "current.md"
    if not current.exists():
        atomic_write_text(current, minimal_current())
        created.append(str(current))
    spec_index = mem / "spec" / "index.md"
    if not spec_index.exists():
        atomic_write_text(spec_index, "# 稳定上下文索引\n\n- 按需添加，不存临时过程。\n")
        created.append(str(spec_index))
    tasks_index = mem / "tasks" / "index.md"
    if not tasks_index.exists():
        atomic_write_text(tasks_index, "# 任务索引\n\n- 暂无长期任务。\n")
        created.append(str(tasks_index))

    manifest_path = mem / MANIFEST
    manifest = load_json(manifest_path, default=None)
    if manifest is None:
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "project_id": str(uuid.uuid4()),
            "created_at": utc_now(),
            "memory_revision": 0,
            "layout_mode": "v2",
            "last_sync_at": None,
            "tracking_mode": project_tracking_mode(root),
            "auto_sync": True,
            "active_task_ids": [],
        }
        atomic_write_json(manifest_path, manifest)
        created.append(str(manifest_path))
    elif manifest.get("schema_version") != SCHEMA_VERSION:
        raise MemoryCtlError(f"unsupported manifest schema: {manifest.get('schema_version')}")

    state_path = runtime / "project-state.json"
    state = load_json(state_path, default={}) or {}
    state.update({"last_bootstrap_at": utc_now(), "project_root": str(root)})
    atomic_write_json(state_path, state)
    ensure_runtime_ignored(root)
    return {"status": "ok", "project_root": str(root), "created": created, "manifest": manifest}


def find_task_meta(root: Path) -> List[Tuple[Path, Dict[str, Any]]]:
    result: List[Tuple[Path, Dict[str, Any]]] = []
    tasks = memory_dir(root) / "tasks"
    if not tasks.exists():
        return result
    for path in sorted(tasks.rglob("meta.json")):
        if RUNTIME in path.parts:
            continue
        meta = load_json(path, default={}) or {}
        if meta.get("task_id"):
            result.append((path, meta))
    return result


def render_v2_index(root: Path) -> Path:
    groups: Dict[str, List[Tuple[Path, Dict[str, Any]]]] = {
        "active": [],
        "paused": [],
        "completed": [],
        "cancelled": [],
    }
    mem = memory_dir(root)
    for path, meta in find_task_meta(root):
        groups.setdefault(meta.get("status", "paused"), []).append((path, meta))
    labels = {
        "active": "活跃",
        "paused": "暂停",
        "completed": "完成",
        "cancelled": "取消",
    }
    lines = ["# V2 任务索引", "", "本文件由 memoryctl 生成；V1 试点期间不覆盖 tasks/index.md。", ""]
    for status in ("active", "paused", "completed", "cancelled"):
        lines.extend([f"## {labels[status]}", ""])
        items = groups.get(status, [])
        if not items:
            lines.extend(["- 无。", ""])
            continue
        for meta_path, meta in items:
            rel = meta_path.parent.relative_to(mem)
            lines.append(f"- `{meta.get('slug')}`：`{rel}`")
        lines.append("")
    target = mem / "tasks" / "index.v2.md"
    atomic_write_text(target, "\n".join(lines).rstrip() + "\n")
    return target


def migrate_v1(root: Path, config: Dict[str, Any]) -> Dict[str, Any]:
    result = bootstrap(root, config)
    mem = memory_dir(root)
    manifest_path = mem / MANIFEST
    manifest = load_json(manifest_path)
    created: List[str] = []
    active_ids: List[str] = []

    for status, base in (("active", mem / "tasks" / "active"), ("completed", mem / "tasks" / "archive")):
        if not base.exists():
            continue
        for task_dir in sorted(path for path in base.iterdir() if path.is_dir()):
            meta_path = task_dir / "meta.json"
            meta = load_json(meta_path, default=None)
            if meta is None:
                task_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{manifest['project_id']}:{task_dir.name}"))
                meta = {
                    "task_id": task_id,
                    "slug": task_dir.name,
                    "status": status,
                    "created_at": utc_now(),
                    "updated_at": utc_now(),
                    "legacy_path": str(task_dir.relative_to(mem)),
                }
                atomic_write_json(meta_path, meta)
                created.append(str(meta_path))
            if meta.get("status") == "active":
                active_ids.append(meta["task_id"])

    manifest.update(
        {
            "layout_mode": "compat-v1",
            "active_task_ids": sorted(set(active_ids)),
            "migration": {
                "from_schema": 1,
                "started_at": manifest.get("migration", {}).get("started_at", utc_now()),
                "legacy_preserved": True,
            },
        }
    )
    atomic_write_json(manifest_path, manifest)
    index_path = render_v2_index(root)
    created.append(str(index_path))
    result.update(
        {
            "migration": "compat-v1",
            "created": result["created"] + created,
            "manifest": manifest,
        }
    )
    return result


def session_paths(root: Path, session_id: str) -> Tuple[Path, Path, Path]:
    session = runtime_dir(root) / "sessions" / safe_session_id(session_id)
    return session, session / "state.json", session / "pending.jsonl"


def verify_event(record: Dict[str, Any]) -> bool:
    checksum = record.get("checksum")
    unsigned = dict(record)
    unsigned.pop("checksum", None)
    return isinstance(checksum, str) and checksum == sha256_bytes(canonical_json(unsigned).encode("utf-8"))


def read_pending(path: Path) -> Tuple[List[Dict[str, Any]], List[str]]:
    records: List[Dict[str, Any]] = []
    warnings: List[str] = []
    if not path.exists():
        return records, warnings
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    for index, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            warnings.append(f"invalid pending JSON at {path}:{index}")
            continue
        if not verify_event(record):
            warnings.append(f"checksum mismatch at {path}:{index}")
            continue
        records.append(record)
    return records, warnings


def active_task_for_session(root: Path, state: Dict[str, Any]) -> Optional[Tuple[Path, Dict[str, Any]]]:
    task_id = state.get("task_id")
    active = [(path, meta) for path, meta in find_task_meta(root) if meta.get("status") == "active"]
    if task_id:
        for item in active:
            if item[1].get("task_id") == task_id:
                return item
    if len(active) == 1:
        return active[0]
    return None


def acquire_lock(root: Path, session_id: str, transaction_id: str) -> Path:
    lock = runtime_dir(root) / "lock.json"
    if lock.exists():
        existing = load_json(lock, default={}) or {}
        created = existing.get("created_epoch", 0)
        existing_id = str(existing.get("transaction_id") or "")
        existing_tx = runtime_dir(root) / "transactions" / existing_id
        if existing_tx.is_dir():
            raise MemoryCtlError(
                f"memory has an unfinished transaction {existing_id}; recover or abandon it first"
            )
        if time.time() - float(created) < 1800:
            raise MemoryCtlError(f"memory is locked by transaction {existing_id}")
        lock.unlink()
    payload = {
        "session_id": session_id,
        "transaction_id": transaction_id,
        "created_at": utc_now(),
        "created_epoch": time.time(),
    }
    try:
        fd = os.open(str(lock), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise MemoryCtlError("another memory transaction acquired the lock") from exc
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return lock


def copy_into_proposed(mem: Path, proposed: Path, source: Path) -> None:
    rel = source.relative_to(mem)
    target = proposed / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def prepare(root: Path, config: Dict[str, Any], session_id: str) -> Dict[str, Any]:
    bootstrap(root, config)
    mem = memory_dir(root)
    manifest = load_json(mem / MANIFEST)
    session, state_path, pending_path = session_paths(root, session_id)
    state = load_json(state_path, default={}) or {}
    records, warnings = read_pending(pending_path)
    if warnings:
        raise MemoryCtlError("pending queue is damaged; run doctor before syncing: " + "; ".join(warnings))
    checkpoint = load_json(session / "checkpoint.json", default={}) or {}
    covered = int(checkpoint.get("covered_through_seq", 0))
    records = [record for record in records if int(record.get("seq", 0)) > covered]
    if not records:
        return {"status": "no_pending", "session_id": session_id, "warnings": warnings}

    transaction_id = str(uuid.uuid4())
    commit_token = f"cap_{secrets.token_urlsafe(32)}"
    lock = acquire_lock(root, session_id, transaction_id)
    tx = runtime_dir(root) / "transactions" / transaction_id
    proposed = tx / "proposed"
    try:
        proposed.mkdir(parents=True, exist_ok=False)
    except Exception:
        if lock.exists():
            lock.unlink()
        raise

    copied: List[str] = []
    writable: List[str] = []
    for source in (mem / "current.md",):
        if source.exists():
            copy_into_proposed(mem, proposed, source)
            copied.append(str(source.relative_to(mem)))
            writable.append(str(source.relative_to(mem)))

    task = active_task_for_session(root, state)
    if task:
        meta_path, meta = task
        state["task_id"] = meta["task_id"]
        for name in ("meta.json", "brief.md", "decisions.md", "refs.md"):
            source = meta_path.parent / name
            if source.exists():
                copy_into_proposed(mem, proposed, source)
                copied.append(str(source.relative_to(mem)))
                if name in WRITABLE_MEMORY_BASENAMES:
                    writable.append(str(source.relative_to(mem)))

    source_payload = {
        "schema_version": SCHEMA_VERSION,
        "transaction_id": transaction_id,
        "session_id": session_id,
        "base_revision": manifest["memory_revision"],
        "task_id": state.get("task_id"),
        "events": records,
        "warnings": warnings,
        "allowed_write_files": sorted(writable),
    }
    plan = {
        "schema_version": SCHEMA_VERSION,
        "transaction_id": transaction_id,
        "session_id": session_id,
        "base_revision": manifest["memory_revision"],
        "outcome": "pending",
        "summary": "",
        "updated_categories": [],
        "candidates": [],
    }
    coverage = {
        "schema_version": SCHEMA_VERSION,
        "transaction_id": transaction_id,
        "complete": False,
        "covered_event_ids": [],
        "unresolved": [],
    }
    atomic_write_json(tx / "source.json", source_payload)
    atomic_write_json(tx / "sync-plan.json", plan)
    atomic_write_json(tx / "coverage-report.json", coverage)
    atomic_write_json(
        tx / "transaction.json",
        {
            "transaction_id": transaction_id,
            "session_id": session_id,
            "base_revision": manifest["memory_revision"],
            "state": "prepared",
            "created_at": utc_now(),
            "lock": str(lock),
            "proposed_files": copied,
            "allowed_write_files": sorted(writable),
            "source_file_sha256": {
                rel: file_sha256(proposed / rel) for rel in copied if (proposed / rel).is_file()
            },
            "commit_token_sha256": sha256_bytes(commit_token.encode("utf-8")),
        },
    )
    state.update({"transaction_id": transaction_id, "updated_at": utc_now()})
    atomic_write_json(state_path, state)
    return {
        "status": "prepared",
        "transaction_id": transaction_id,
        "transaction_dir": str(tx),
        "session_id": session_id,
        "event_count": len(records),
        "task_id": state.get("task_id"),
        "proposed_files": copied,
        "warnings": warnings,
        "commit_token": commit_token,
    }


def rewrite_pending(path: Path, covered_ids: Iterable[str]) -> None:
    covered = set(covered_ids)
    records, warnings = read_pending(path)
    if warnings:
        raise MemoryCtlError("refusing to rewrite damaged pending queue: " + "; ".join(warnings))
    keep = [record for record in records if record.get("event_id") not in covered]
    if not keep:
        if path.exists():
            path.unlink()
        return
    text = "".join(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n" for record in keep)
    atomic_write_text(path, text)


def load_transaction(root: Path, transaction_id: str) -> Tuple[Path, Dict[str, Any], Dict[str, Any]]:
    tx = runtime_dir(root) / "transactions" / transaction_id
    if not tx.is_dir():
        raise MemoryCtlError(f"transaction not found: {transaction_id}")
    transaction = load_json(tx / "transaction.json", default=None)
    source = load_json(tx / "source.json", default=None)
    if transaction is None or source is None:
        raise MemoryCtlError(f"transaction is incomplete: {transaction_id}")
    return tx, transaction, source


def validate_curator_result(
    tx: Path,
    transaction: Dict[str, Any],
    source: Dict[str, Any],
    result: Dict[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, Any], List[str]]:
    if not isinstance(result, dict):
        raise MemoryCtlError("curator result must be a JSON object")
    outcome = result.get("outcome")
    if outcome not in {"write", "no-op"}:
        raise MemoryCtlError("curator outcome must be write or no-op")

    source_ids = {str(event.get("event_id")) for event in source.get("events", [])}
    if not source_ids:
        raise MemoryCtlError("transaction has no source events")

    candidates = result.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise MemoryCtlError("curator must classify every source event with at least one candidate")

    candidate_ids: set = set()
    candidate_sources: set = set()
    write_targets: set = set()
    unresolved: List[str] = []
    normalized_candidates: List[Dict[str, Any]] = []
    for item in candidates:
        if not isinstance(item, dict):
            raise MemoryCtlError("candidate must be an object")
        candidate_id = str(item.get("candidate_id") or "").strip()
        if not candidate_id or candidate_id in candidate_ids:
            raise MemoryCtlError(f"invalid or duplicate candidate id: {candidate_id!r}")
        candidate_ids.add(candidate_id)
        category = str(item.get("category") or "")
        if category not in ALLOWED_CATEGORIES:
            raise MemoryCtlError(f"invalid candidate category: {category}")
        disposition = str(item.get("disposition") or "")
        if disposition not in {"write", "skip", "unresolved"}:
            raise MemoryCtlError(f"invalid candidate disposition: {disposition}")
        reason = str(item.get("reason") or "").strip()
        if not reason or len(reason) > 1000:
            raise MemoryCtlError(f"candidate reason is missing or too long: {candidate_id}")
        item_sources = {str(value) for value in item.get("source_event_ids", [])}
        if not item_sources or not item_sources.issubset(source_ids):
            raise MemoryCtlError(f"candidate has invalid source events: {candidate_id}")
        candidate_sources.update(item_sources)
        target_value = item.get("target")
        target = str(target_value).strip() if target_value is not None else None
        if target == "":
            target = None
        if disposition == "write":
            if target is None:
                raise MemoryCtlError(f"write candidate has no target: {candidate_id}")
            write_targets.add(target)
        elif target is not None and target not in transaction.get("allowed_write_files", []):
            raise MemoryCtlError(f"candidate target is outside the transaction: {target}")
        if disposition == "unresolved":
            unresolved.append(f"{candidate_id}: {reason}")
        normalized_candidates.append(
            {
                "candidate_id": candidate_id,
                "category": category,
                "disposition": disposition,
                "target": target,
                "source_event_ids": sorted(item_sources),
                "reason": reason,
            }
        )

    if candidate_sources != source_ids:
        missing = sorted(source_ids - candidate_sources)
        extra = sorted(candidate_sources - source_ids)
        raise MemoryCtlError(f"candidate coverage mismatch; missing={missing}, extra={extra}")

    explicit_unresolved = result.get("unresolved", [])
    if not isinstance(explicit_unresolved, list):
        raise MemoryCtlError("unresolved must be an array")
    unresolved.extend(str(item).strip() for item in explicit_unresolved if str(item).strip())

    files = result.get("files")
    if not isinstance(files, list):
        raise MemoryCtlError("files must be an array")
    if outcome == "no-op" and (files or write_targets):
        raise MemoryCtlError("no-op result cannot contain writes")
    if outcome == "write" and (not write_targets or not files):
        raise MemoryCtlError("write result requires write candidates and changed files")

    allowed = set(transaction.get("allowed_write_files", []))
    proposed_root = tx / "proposed"
    changed: List[str] = []
    seen_paths: set = set()
    for item in files:
        if not isinstance(item, dict):
            raise MemoryCtlError("file result must be an object")
        rel = str(item.get("path") or "").strip()
        content = item.get("content")
        if rel in seen_paths:
            raise MemoryCtlError(f"duplicate proposed file: {rel}")
        seen_paths.add(rel)
        if rel not in allowed:
            raise MemoryCtlError(f"curator attempted an unapproved path: {rel}")
        if Path(rel).name not in WRITABLE_MEMORY_BASENAMES:
            raise MemoryCtlError(f"curator attempted an unsupported memory file: {rel}")
        if not isinstance(content, str) or not content.strip() or "\x00" in content:
            raise MemoryCtlError(f"invalid proposed content for {rel}")
        encoded = content.encode("utf-8")
        if len(encoded) > MAX_PROPOSED_FILE_BYTES:
            raise MemoryCtlError(f"proposed file exceeds size limit: {rel}")
        target = proposed_root / rel
        if not target.is_file():
            raise MemoryCtlError(f"proposed source file is missing: {rel}")
        existing_text = target.read_text(encoding="utf-8")
        basename = Path(rel).name
        if basename in {"decisions.md", "refs.md"}:
            missing_lines = [
                line
                for line in existing_text.splitlines()
                if line.strip() and line not in content
            ]
            if missing_lines:
                raise MemoryCtlError(
                    f"durable memory cannot remove existing lines from {rel}; "
                    f"first missing line={missing_lines[0]!r}"
                )
        elif len(existing_text.encode("utf-8")) >= 1024 and len(encoded) < len(
            existing_text.encode("utf-8")
        ) * 0.35:
            raise MemoryCtlError(f"proposed rewrite removes too much current context: {rel}")
        if target.read_bytes() != encoded:
            atomic_write_bytes(target, encoded)
            changed.append(rel)

    changed_set = set(changed)
    if outcome == "write":
        if write_targets != changed_set:
            raise MemoryCtlError(
                f"write targets do not match changed files; targets={sorted(write_targets)} changed={sorted(changed_set)}"
            )
    elif changed:
        raise MemoryCtlError("no-op result changed proposed files")

    summary = str(result.get("summary") or "").strip()
    if not summary or len(summary) > 1000:
        raise MemoryCtlError("curator summary is missing or too long")
    categories = result.get("updated_categories", [])
    if not isinstance(categories, list):
        raise MemoryCtlError("updated_categories must be an array")
    normalized_categories = sorted({str(item).strip() for item in categories if str(item).strip()})
    invalid_categories = set(normalized_categories) - (ALLOWED_CATEGORIES - {"skip"})
    if invalid_categories:
        raise MemoryCtlError(f"invalid updated categories: {sorted(invalid_categories)}")
    if outcome == "no-op" and normalized_categories:
        raise MemoryCtlError("no-op result cannot report updated categories")
    if outcome == "write" and not normalized_categories:
        raise MemoryCtlError("write result must report updated categories")

    plan = {
        "schema_version": SCHEMA_VERSION,
        "transaction_id": tx.name,
        "session_id": source["session_id"],
        "base_revision": source["base_revision"],
        "outcome": outcome,
        "summary": summary,
        "updated_categories": normalized_categories,
        "changed_files": sorted(changed),
        "candidates": normalized_candidates,
    }
    coverage = {
        "schema_version": SCHEMA_VERSION,
        "transaction_id": tx.name,
        "complete": not unresolved,
        "covered_event_ids": sorted(candidate_sources),
        "unresolved": unresolved,
    }
    return plan, coverage, unresolved


def apply_result(
    root: Path,
    config: Dict[str, Any],
    transaction_id: str,
    result_path: Path,
) -> Dict[str, Any]:
    ensure_allowed(root, config)
    tx, transaction, source = load_transaction(root, transaction_id)
    result = load_json(result_path, default=None)
    if result is None:
        raise MemoryCtlError(f"curator result not found: {result_path}")
    plan, coverage, unresolved = validate_curator_result(tx, transaction, source, result)
    atomic_write_json(tx / "curator-result.json", result)
    atomic_write_json(tx / "sync-plan.json", plan)
    atomic_write_json(tx / "coverage-report.json", coverage)
    transaction.update({"state": "curated", "curated_at": utc_now()})
    atomic_write_json(tx / "transaction.json", transaction)
    if unresolved:
        return {
            "status": "unresolved",
            "transaction_id": transaction_id,
            "unresolved": unresolved,
            "summary": plan["summary"],
        }
    return {
        "status": "ready",
        "transaction_id": transaction_id,
        "outcome": plan["outcome"],
        "summary": plan["summary"],
        "changed_files": plan["changed_files"],
    }


def abandon(
    root: Path,
    config: Dict[str, Any],
    transaction_id: str,
    reason: str,
) -> Dict[str, Any]:
    ensure_allowed(root, config)
    tx, transaction, source = load_transaction(root, transaction_id)
    if (tx / "commit-log.json").exists():
        raise MemoryCtlError("cannot abandon a transaction after commit started; use recover")
    reason = reason.strip()[:2000] or "curator did not complete"
    append_audit(
        root,
        {
            "type": "transaction_abandoned",
            "transaction_id": transaction_id,
            "session_id": source.get("session_id"),
            "reason": reason,
            "source_event_ids": [event.get("event_id") for event in source.get("events", [])],
        },
    )
    _session, state_path, _pending = session_paths(root, str(source["session_id"]))
    state = load_json(state_path, default={}) or {}
    state.update(
        {
            "transaction_id": None,
            "force_sync": True,
            "last_sync_error": reason,
            "updated_at": utc_now(),
        }
    )
    atomic_write_json(state_path, state)
    lock = runtime_dir(root) / "lock.json"
    lock_data = load_json(lock, default={}) or {} if lock.exists() else {}
    shutil.rmtree(tx)
    if lock.exists() and lock_data.get("transaction_id") == transaction_id:
        lock.unlink()
    return {
        "status": "abandoned",
        "transaction_id": transaction_id,
        "pending_preserved": True,
        "reason": reason,
    }


def validate_plan(tx: Path) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    source = load_json(tx / "source.json")
    plan = load_json(tx / "sync-plan.json")
    coverage = load_json(tx / "coverage-report.json")
    txid = tx.name
    for name, value in (("source", source), ("plan", plan), ("coverage", coverage)):
        if value.get("transaction_id") != txid:
            raise MemoryCtlError(f"{name} transaction id mismatch")
    if plan.get("outcome") not in {"write", "no-op"}:
        raise MemoryCtlError("sync plan outcome must be write or no-op")
    if coverage.get("complete") is not True:
        raise MemoryCtlError("coverage report is incomplete")
    source_ids = {event["event_id"] for event in source.get("events", [])}
    covered_ids = set(coverage.get("covered_event_ids", []))
    if source_ids != covered_ids:
        missing = sorted(source_ids - covered_ids)
        extra = sorted(covered_ids - source_ids)
        raise MemoryCtlError(f"coverage mismatch; missing={missing}, extra={extra}")
    if coverage.get("unresolved"):
        raise MemoryCtlError(f"unresolved memory candidates: {coverage['unresolved']}")
    dispositions = {"write", "skip", "unresolved"}
    candidate_sources: set = set()
    for candidate in plan.get("candidates", []):
        if candidate.get("disposition") not in dispositions:
            raise MemoryCtlError(f"invalid candidate disposition: {candidate}")
        if not candidate.get("reason"):
            raise MemoryCtlError(f"candidate missing reason: {candidate}")
        candidate_sources.update(candidate.get("source_event_ids", []))
        if candidate.get("disposition") == "unresolved":
            raise MemoryCtlError(f"candidate remains unresolved: {candidate}")
    if plan.get("outcome") == "write" and not any(
        item.get("disposition") == "write" for item in plan.get("candidates", [])
    ):
        raise MemoryCtlError("write outcome requires at least one write candidate")
    if candidate_sources != source_ids:
        raise MemoryCtlError("candidate sources must cover every source event exactly")
    changed_files = plan.get("changed_files", [])
    if not isinstance(changed_files, list) or len(set(changed_files)) != len(changed_files):
        raise MemoryCtlError("changed_files must be a unique array")
    transaction = load_json(tx / "transaction.json", default={}) or {}
    allowed = set(transaction.get("allowed_write_files", []))
    if not set(changed_files).issubset(allowed):
        raise MemoryCtlError("changed_files contains a path outside the transaction")
    write_targets = {
        item.get("target") for item in plan.get("candidates", []) if item.get("disposition") == "write"
    }
    if plan.get("outcome") == "write" and write_targets != set(changed_files):
        raise MemoryCtlError("write candidates must match changed_files exactly")
    if plan.get("outcome") == "no-op" and changed_files:
        raise MemoryCtlError("no-op transaction cannot contain changed files")
    return source, plan, coverage


def build_commit_entries(mem: Path, tx: Path, plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    for rel_text in plan.get("changed_files", []):
        rel = Path(rel_text)
        proposed = tx / "proposed" / rel
        if not proposed.is_file() or any(part in {"..", RUNTIME} for part in rel.parts):
            raise MemoryCtlError(f"unsafe or missing proposed path: {rel}")
        target = mem / rel
        backup = tx / "backup" / rel
        existed = target.exists()
        if existed:
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, backup)
        entries.append(
            {
                "relative_path": str(rel),
                "target": str(target),
                "backup": str(backup),
                "existed": existed,
                "original_sha256": file_sha256(target) if existed else None,
                "proposed_sha256": file_sha256(proposed),
            }
        )
    return entries


def finalize_checkpoint(root: Path, source: Dict[str, Any], plan: Dict[str, Any], revision: int) -> None:
    session_id = source["session_id"]
    session, state_path, pending_path = session_paths(root, session_id)
    events = source.get("events", [])
    covered_ids = [event["event_id"] for event in events]
    covered_seq = max((int(event.get("seq", 0)) for event in events), default=0)
    checkpoint = {
        "session_id": session_id,
        "covered_through_seq": covered_seq,
        "memory_revision": revision,
        "synced_at": utc_now(),
        "outcome": plan["outcome"],
        "summary": plan.get("summary", ""),
    }
    atomic_write_json(session / "checkpoint.json", checkpoint)
    rewrite_pending(pending_path, covered_ids)
    state = load_json(state_path, default={}) or {}
    state.update(
        {
            "dirty": False,
            "force_sync": False,
            "checkpoint_required": False,
            "transaction_id": None,
            "last_sync_at": utc_now(),
        }
    )
    atomic_write_json(state_path, state)


def commit(
    root: Path,
    config: Dict[str, Any],
    transaction_id: str,
    commit_token: str,
) -> Dict[str, Any]:
    ensure_allowed(root, config)
    mem = memory_dir(root)
    tx = runtime_dir(root) / "transactions" / transaction_id
    if not tx.is_dir():
        raise MemoryCtlError(f"transaction not found: {transaction_id}")
    source, plan, _coverage = validate_plan(tx)
    manifest = load_json(mem / MANIFEST)
    if int(manifest["memory_revision"]) != int(plan["base_revision"]):
        raise MemoryCtlError(
            f"revision conflict: current={manifest['memory_revision']} base={plan['base_revision']}"
        )
    target_revision = int(manifest["memory_revision"]) + (1 if plan["outcome"] == "write" else 0)
    transaction = load_json(tx / "transaction.json", default={}) or {}
    expected_token_hash = transaction.get("commit_token_sha256")
    if not expected_token_hash or not secrets.compare_digest(
        str(expected_token_hash), sha256_bytes(commit_token.encode("utf-8"))
    ):
        raise MemoryCtlError("invalid commit capability; only the preparing Hook may commit")
    if transaction.get("state") != "curated":
        raise MemoryCtlError("transaction has not passed curator result validation")
    lock = runtime_dir(root) / "lock.json"
    lock_data = load_json(lock, default={}) or {}
    if lock_data.get("transaction_id") != transaction_id:
        raise MemoryCtlError("transaction does not own the project memory lock")
    entries = build_commit_entries(mem, tx, plan)
    commit_log = {
        "transaction_id": transaction_id,
        "state": "applying",
        "base_revision": manifest["memory_revision"],
        "target_revision": target_revision,
        "session_id": source["session_id"],
        "files": entries,
        "started_at": utc_now(),
    }
    atomic_write_json(tx / "commit-log.json", commit_log)

    try:
        if plan["outcome"] == "write":
            for entry in entries:
                proposed = tx / "proposed" / entry["relative_path"]
                atomic_write_bytes(Path(entry["target"]), proposed.read_bytes())
        if plan["outcome"] == "write":
            manifest.update(
                {
                    "memory_revision": target_revision,
                    "last_sync_at": utc_now(),
                    "last_transaction_id": transaction_id,
                }
            )
            atomic_write_json(mem / MANIFEST, manifest)
        finalize_checkpoint(root, source, plan, target_revision)
        commit_log.update({"state": "committed", "finished_at": utc_now()})
        atomic_write_json(tx / "commit-log.json", commit_log)
        append_audit(
            root,
            {
                "type": "transaction_committed",
                "transaction_id": transaction_id,
                "session_id": source["session_id"],
                "outcome": plan["outcome"],
                "base_revision": plan["base_revision"],
                "target_revision": target_revision,
                "source_event_ids": [event["event_id"] for event in source.get("events", [])],
                "summary": plan.get("summary", ""),
                "updated_categories": plan.get("updated_categories", []),
                "changed_files": plan.get("changed_files", []),
                "candidates": plan.get("candidates", []),
            },
        )
        project_state = load_json(runtime_dir(root) / "project-state.json", default={}) or {}
        project_state.update(
            {
                "last_transaction_id": transaction_id,
                "last_sync_at": utc_now(),
                "last_outcome": plan["outcome"],
            }
        )
        atomic_write_json(runtime_dir(root) / "project-state.json", project_state)
        shutil.rmtree(tx)
        lock = runtime_dir(root) / "lock.json"
        if lock.exists():
            lock.unlink()
        return {
            "status": "committed",
            "transaction_id": transaction_id,
            "outcome": plan["outcome"],
            "memory_revision": target_revision,
            "summary": plan.get("summary", ""),
            "updated_categories": plan.get("updated_categories", []),
        }
    except Exception:
        raise


def recover(root: Path, config: Dict[str, Any], transaction_id: str) -> Dict[str, Any]:
    ensure_allowed(root, config)
    mem = memory_dir(root)
    tx = runtime_dir(root) / "transactions" / transaction_id
    log = load_json(tx / "commit-log.json", default=None)
    if log is None:
        raise MemoryCtlError(f"transaction has no commit log: {transaction_id}")
    manifest = load_json(mem / MANIFEST)
    current_revision = int(manifest["memory_revision"])
    base_revision = int(log["base_revision"])
    target_revision = int(log["target_revision"])
    if current_revision not in {base_revision, target_revision}:
        raise MemoryCtlError(
            f"cannot recover across a newer revision: current={current_revision} "
            f"base={base_revision} target={target_revision}"
        )
    committed_files_valid = all(
        Path(entry["target"]).is_file()
        and file_sha256(Path(entry["target"])) == entry.get("proposed_sha256")
        for entry in log.get("files", [])
    )
    if current_revision == target_revision and committed_files_valid:
        source = load_json(tx / "source.json")
        plan = load_json(tx / "sync-plan.json")
        finalize_checkpoint(root, source, plan, target_revision)
        result = "finalized"
    else:
        for entry in reversed(log.get("files", [])):
            target = Path(entry["target"])
            backup = Path(entry["backup"])
            if entry.get("existed") and backup.exists():
                atomic_write_bytes(target, backup.read_bytes())
            elif not entry.get("existed") and target.exists():
                target.unlink()
        if current_revision == target_revision:
            manifest.update(
                {
                    "memory_revision": base_revision,
                    "last_sync_at": utc_now(),
                    "recovery_note": f"rolled back damaged transaction {transaction_id}",
                }
            )
            atomic_write_json(mem / MANIFEST, manifest)
        result = "rolled_back"
    log.update({"state": result, "recovered_at": utc_now()})
    atomic_write_json(tx / "commit-log.json", log)
    lock = runtime_dir(root) / "lock.json"
    if lock.exists():
        lock.unlink()
    source = load_json(tx / "source.json", default={}) or {}
    if result == "rolled_back" and source.get("session_id"):
        _session, state_path, _pending = session_paths(root, str(source["session_id"]))
        state = load_json(state_path, default={}) or {}
        state.update(
            {
                "transaction_id": None,
                "dirty": True,
                "force_sync": True,
                "last_sync_error": f"transaction {transaction_id} rolled back",
            }
        )
        atomic_write_json(state_path, state)
    append_audit(
        root,
        {
            "type": "transaction_recovered",
            "transaction_id": transaction_id,
            "result": result,
            "manifest_revision": load_json(mem / MANIFEST).get("memory_revision"),
        },
    )
    return {"status": result, "transaction_id": transaction_id, "transaction_dir": str(tx)}


def directory_size(path: Path) -> int:
    total = 0
    if not path.exists():
        return 0
    for item in path.rglob("*"):
        try:
            if item.is_file():
                total += item.stat().st_size
        except OSError:
            continue
    return total


def audit_summary(root: Path) -> Dict[str, Any]:
    counts = {
        "committed": 0,
        "writes": 0,
        "no_ops": 0,
        "abandoned": 0,
        "recovered": 0,
        "invalid_records": 0,
    }
    latest: Optional[Dict[str, Any]] = None
    audit_root = runtime_dir(root) / "audit"
    if not audit_root.exists():
        return {**counts, "latest": latest}

    for audit_file in sorted(audit_root.glob("*.jsonl")):
        for line in audit_file.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                counts["invalid_records"] += 1
                continue
            record_type = record.get("type")
            if record_type == "transaction_committed":
                counts["committed"] += 1
                if record.get("outcome") == "write":
                    counts["writes"] += 1
                elif record.get("outcome") == "no-op":
                    counts["no_ops"] += 1
            elif record_type == "transaction_abandoned":
                counts["abandoned"] += 1
            elif record_type == "transaction_recovered":
                counts["recovered"] += 1
            if latest is None or str(record.get("recorded_at") or "") > str(
                latest.get("recorded_at") or ""
            ):
                latest = {
                    key: record.get(key)
                    for key in ("recorded_at", "type", "transaction_id", "outcome")
                    if record.get(key) is not None
                }
    return {**counts, "latest": latest}


def human_bytes(value: int) -> str:
    size = float(value)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def local_timestamp(value: Any) -> str:
    if not value:
        return "-"
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.astimezone().isoformat(timespec="seconds")
    except ValueError:
        return str(value)


def normalize_inventory_entries(values: Any) -> List[Dict[str, str]]:
    result: List[Dict[str, str]] = []
    for value in values if isinstance(values, list) else []:
        if isinstance(value, str):
            result.append({"path": value, "reason": ""})
        elif isinstance(value, dict) and value.get("path"):
            result.append(
                {
                    "path": str(value["path"]),
                    "reason": str(value.get("reason") or ""),
                }
            )
    return result


def fleet_project_status(
    raw_root: str,
    config: Dict[str, Any],
    verify_hooks: bool = True,
) -> Dict[str, Any]:
    root = Path(raw_root).expanduser().resolve()
    item: Dict[str, Any] = {
        "project_root": str(root),
        "state": "needs_attention",
        "state_label": "需处理",
        "issues": [],
        "warnings": [],
    }
    if not root.is_dir():
        item["issues"].append("项目目录不存在")
        return item

    manifest_path = memory_dir(root) / MANIFEST
    if not manifest_path.is_file():
        item.update({"state": "not_initialized", "state_label": "未迁移"})
        item["issues"].append("缺少 manifest.json")
        return item

    try:
        status = collect_status(root, config)
        state = load_json(runtime_dir(root) / "project-state.json", default={}) or {}
        audit = audit_summary(root)
        if verify_hooks:
            hook_issues, hook_warnings, hook_detail = hook_installation_status(root)
        else:
            hook_issues, hook_warnings, hook_detail = [], [], {}
    except MemoryCtlError as exc:
        item["issues"].append(str(exc))
        return item

    manifest = status.get("manifest") or {}
    heartbeat_epoch = state.get("last_hook_heartbeat_epoch")
    heartbeat_age = None
    if heartbeat_epoch is not None:
        try:
            heartbeat_age = max(0, time.time() - float(heartbeat_epoch))
        except (TypeError, ValueError):
            item["issues"].append("Hook 心跳时间无效")

    waiting_only_issues = {
        "current hooks.json has not produced a V2 heartbeat; restart and trust the Hook",
        "current V2 Hook script has not produced a heartbeat; restart and trust the Hook",
        "no V2 Hook heartbeat has been observed",
    }
    for issue in hook_issues:
        if heartbeat_epoch is None and issue in waiting_only_issues:
            continue
        item["issues"].append(issue)
    item["warnings"].extend(hook_warnings)

    if state.get("last_hook_error"):
        item["issues"].append(str(state["last_hook_error"]))
    pending_warnings = [
        warning
        for session in status.get("sessions", [])
        for warning in session.get("warnings", [])
    ]
    if pending_warnings:
        item["issues"].append(
            f"pending 队列存在 {len(pending_warnings)} 条损坏记录：{pending_warnings[0]}"
        )
    if audit.get("invalid_records"):
        item["warnings"].append(f"审计日志损坏记录：{audit['invalid_records']}")
    current = memory_dir(root) / "current.md"
    if current.is_file() and current.stat().st_size > 4096:
        item["warnings"].append(f"current.md 超过 4 KB：{current.stat().st_size} bytes")
    storage = config.get("storage", {})
    runtime_limit = int(storage.get("runtime_soft_limit_mb", 20)) * 1024 * 1024
    project_limit = int(storage.get("project_soft_limit_mb", 50)) * 1024 * 1024
    if int(status.get("runtime_bytes", 0)) > runtime_limit:
        item["issues"].append(
            f"运行数据超过 {storage.get('runtime_soft_limit_mb', 20)} MB 软上限"
        )
    if int(status.get("memory_bytes", 0)) > project_limit:
        item["issues"].append(
            f"项目记忆超过 {storage.get('project_soft_limit_mb', 50)} MB 软上限"
        )

    last_sync_at = state.get("last_hook_sync_at") or state.get("last_sync_at")

    if item["issues"]:
        state_code, state_label = "needs_attention", "需处理"
    elif status.get("transactions"):
        state_code, state_label = "syncing", "整理中"
    elif status.get("pending_total"):
        state_code, state_label = "pending", "待整理"
    elif heartbeat_epoch is None:
        state_code, state_label = "waiting_first_use", "待首次使用"
    elif heartbeat_age is not None and heartbeat_age > 7 * 86400:
        state_code, state_label = "stale", "超过 7 天未使用"
    elif not last_sync_at:
        state_code, state_label = "online_unverified", "Hook 在线，尚未整理"
    else:
        state_code, state_label = "healthy", "闭环正常"

    item.update(
        {
            "state": state_code,
            "state_label": state_label,
            "layout_mode": manifest.get("layout_mode"),
            "memory_revision": manifest.get("memory_revision"),
            "active_tasks": len(status.get("active_tasks") or []),
            "pending_total": status.get("pending_total", 0),
            "transactions": status.get("transactions", 0),
            "memory_bytes": status.get("memory_bytes", 0),
            "runtime_bytes": status.get("runtime_bytes", 0),
            "last_hook_at": state.get("last_hook_heartbeat_at"),
            "last_hook_event": state.get("last_hook_event"),
            "last_sync_at": last_sync_at,
            "last_outcome": state.get("last_hook_sync_outcome") or state.get("last_outcome"),
            "last_summary": state.get("last_hook_sync_summary"),
            "last_curator_model": state.get("last_curator_model"),
            "model_fallback": state.get("last_model_fallback"),
            "audit": audit,
            "hook_integrity": hook_detail,
        }
    )
    if state.get("last_model_fallback"):
        item["warnings"].append("Curator 曾发生模型回退")
    return item


def render_fleet_report(result: Dict[str, Any]) -> str:
    totals = result["totals"]
    lines = [
        "# Codex Memory V2 观察台账",
        "",
        f"> 生成时间：{local_timestamp(result['generated_at'])}。运行 `memoryctl.py fleet-status` 可刷新。",
        "",
        "## 总览",
        "",
        f"- V2 项目：{totals['configured']} 个；闭环已验证：{totals['healthy']} 个；Hook 在线待首次整理：{totals['online_unverified']} 个；待首次使用：{totals['waiting_first_use']} 个；需关注：{totals['attention']} 个。",
        f"- 待整理事件：{totals['pending_total']}；未完成事务：{totals['transactions']}；累计写入：{totals['writes']} 次；累计跳过：{totals['no_ops']} 次。",
        f"- 有非阻塞提醒：{totals['warning_projects']} 个项目；长期记忆与运行数据合计：{human_bytes(totals['memory_bytes'])}。",
        "",
        "## 项目",
        "",
        "| 状态 | 项目 | 最近 Hook | 最近整理 | 结果 | 待整理 | 事务 | 提醒 | 空间 |",
        "|---|---|---|---|---|---:|---:|---:|---:|",
    ]
    for project in result["projects"]:
        root = str(project["project_root"]).replace("|", "\\|")
        lines.append(
            "| {state} | `{root}` | {hook} | {sync} | {outcome} | {pending} | {transactions} | {warnings} | {size} |".format(
                state=project.get("state_label") or "未知",
                root=root,
                hook=local_timestamp(project.get("last_hook_at")),
                sync=local_timestamp(project.get("last_sync_at")),
                outcome=project.get("last_outcome") or "-",
                pending=project.get("pending_total", 0),
                transactions=project.get("transactions", 0),
                warnings=len(project.get("warnings") or []),
                size=human_bytes(int(project.get("memory_bytes", 0))),
            )
        )

    lines.extend(["", "## 提醒与错误", ""])
    projects_with_notes = [
        project
        for project in result["projects"]
        if project.get("issues") or project.get("warnings")
    ]
    if not projects_with_notes:
        lines.append("- 无。")
    for project in projects_with_notes:
        notes = [f"错误：{value}" for value in project.get("issues", [])]
        notes.extend(f"提醒：{value}" for value in project.get("warnings", []))
        lines.append(f"- `{project['project_root']}`：{'；'.join(notes)}")

    lines.extend(["", "## 排除项", ""])
    excluded = result.get("excluded_projects") or []
    ignored = result.get("ignored_memory_roots") or []
    if not excluded and not ignored:
        lines.append("- 无。")
    for entry in excluded:
        lines.append(f"- 保留 V1：`{entry['path']}`。{entry.get('reason') or ''}".rstrip())
    for entry in ignored:
        lines.append(f"- 不注册：`{entry['path']}`。{entry.get('reason') or ''}".rstrip())

    lines.extend(
        [
            "",
            "## 状态说明",
            "",
            "- `闭环正常`：Hook 在线，且至少完成过一次自动整理，没有积压、未完成事务或错误。",
            "- `Hook 在线，尚未整理`：Hook 已运行，但该项目还没有完成过 write/no-op 整理闭环。",
            "- `待首次使用`：迁移已完成；进入该项目并产生一次对话后会出现心跳。",
            "- `待整理`：已有候选事件，达到阈值或出现文件变化时会自动整理。",
            "- `需处理`：存在错误、目录缺失或配置损坏，需要运行 `doctor`。",
            "",
        ]
    )
    return "\n".join(lines)


def fleet_status(
    config: Dict[str, Any],
    report_path: Optional[Path] = None,
    verify_hooks: bool = True,
) -> Dict[str, Any]:
    projects = [
        fleet_project_status(str(root), config, verify_hooks=verify_hooks)
        for root in config.get("project_roots", [])
    ]
    totals = {
        "configured": len(projects),
        "healthy": sum(project["state"] == "healthy" for project in projects),
        "online_unverified": sum(
            project["state"] == "online_unverified" for project in projects
        ),
        "waiting_first_use": sum(project["state"] == "waiting_first_use" for project in projects),
        "attention": sum(
            project["state"] in {"needs_attention", "not_initialized", "stale"}
            for project in projects
        ),
        "pending_total": sum(int(project.get("pending_total", 0)) for project in projects),
        "transactions": sum(int(project.get("transactions", 0)) for project in projects),
        "memory_bytes": sum(int(project.get("memory_bytes", 0)) for project in projects),
        "runtime_bytes": sum(int(project.get("runtime_bytes", 0)) for project in projects),
        "writes": sum(int((project.get("audit") or {}).get("writes", 0)) for project in projects),
        "no_ops": sum(int((project.get("audit") or {}).get("no_ops", 0)) for project in projects),
        "warning_projects": sum(bool(project.get("warnings")) for project in projects),
    }
    result: Dict[str, Any] = {
        "generated_at": utc_now(),
        "config_path": str(config_path()),
        "totals": totals,
        "projects": projects,
        "excluded_projects": normalize_inventory_entries(config.get("excluded_project_roots")),
        "ignored_memory_roots": normalize_inventory_entries(config.get("ignored_memory_roots")),
    }
    if report_path is not None:
        report = report_path.expanduser().resolve()
        atomic_write_text(report, render_fleet_report(result), mode=0o600)
        result["report_path"] = str(report)
    return result


def collect_status(root: Path, config: Dict[str, Any]) -> Dict[str, Any]:
    ensure_allowed(root, config)
    mem = memory_dir(root)
    manifest = load_json(mem / MANIFEST, default=None)
    sessions: List[Dict[str, Any]] = []
    pending_total = 0
    sessions_root = runtime_dir(root) / "sessions"
    if sessions_root.exists():
        for session in sorted(path for path in sessions_root.iterdir() if path.is_dir()):
            records, warnings = read_pending(session / "pending.jsonl")
            state = load_json(session / "state.json", default={}) or {}
            pending_total += len(records)
            sessions.append(
                {
                    "session_id": session.name,
                    "pending": len(records),
                    "dirty": bool(state.get("dirty")),
                    "task_id": state.get("task_id"),
                    "warnings": warnings,
                }
            )
    tasks = [meta for _path, meta in find_task_meta(root)]
    return {
        "project_root": str(root),
        "manifest": manifest,
        "active_tasks": [task for task in tasks if task.get("status") == "active"],
        "sessions": sessions,
        "pending_total": pending_total,
        "transactions": len(list((runtime_dir(root) / "transactions").glob("*")))
        if (runtime_dir(root) / "transactions").exists()
        else 0,
        "runtime_bytes": directory_size(runtime_dir(root)),
        "memory_bytes": directory_size(mem),
        "hook": {
            key: value
            for key, value in (load_json(runtime_dir(root) / "project-state.json", default={}) or {}).items()
            if key.startswith("last_hook_")
            or key
            in {
                "hook_script_sha256",
                "hooks_config_sha256",
                "last_curator_model",
                "last_model_fallback",
            }
        },
    }


def hook_installation_status(root: Path) -> Tuple[List[str], List[str], Dict[str, Any]]:
    issues: List[str] = []
    warnings: List[str] = []
    hook_script = Path(__file__).with_name("memory-hook.js")
    hooks_config = CODEX_HOME / "hooks.json"
    codex_config = CODEX_HOME / "config.toml"
    state = load_json(runtime_dir(root) / "project-state.json", default={}) or {}
    v2_handlers: List[Tuple[str, int, int, Dict[str, Any], Dict[str, Any]]] = []
    detail: Dict[str, Any] = {
        "script": str(hook_script),
        "hooks_config": str(hooks_config),
        "last_heartbeat_at": state.get("last_hook_heartbeat_at"),
    }
    if not hook_script.is_file():
        issues.append("V2 Hook script is missing")
        return issues, warnings, detail
    current_script_hash = file_sha256(hook_script)
    detail["script_sha256"] = current_script_hash
    if not hooks_config.is_file():
        issues.append(f"hooks.json is missing: {hooks_config}")
    else:
        hooks = load_json(hooks_config, default={}) or {}
        commands = []
        for event_name, groups in (hooks.get("hooks") or {}).items():
            if not isinstance(groups, list):
                continue
            for group_index, group in enumerate(groups):
                for handler_index, handler in enumerate(
                    group.get("hooks", []) if isinstance(group, dict) else []
                ):
                    if isinstance(handler, dict):
                        commands.append(str(handler.get("command") or ""))
                        if str(hook_script) in str(handler.get("command") or ""):
                            v2_handlers.append(
                                (
                                    event_name,
                                    group_index,
                                    handler_index,
                                    group,
                                    handler,
                                )
                            )
        if not any(str(hook_script) in command for command in commands):
            issues.append(f"V2 Hook is not registered in {hooks_config}")
        current_hooks_hash = file_sha256(hooks_config)
        detail["hooks_config_sha256"] = current_hooks_hash
        if state.get("hooks_config_sha256") != current_hooks_hash:
            issues.append("current hooks.json has not produced a V2 heartbeat; restart and trust the Hook")
    if state.get("hook_script_sha256") != current_script_hash:
        issues.append("current V2 Hook script has not produced a heartbeat; restart and trust the Hook")
    if codex_config.is_file():
        try:
            config_text = codex_config.read_text(encoding="utf-8")
            features_match = re.search(
                r"(?ms)^\[features\]\s*$([\s\S]*?)(?=^\[|\Z)",
                config_text,
            )
            if features_match and re.search(
                r"(?m)^\s*hooks\s*=\s*false\s*(?:#.*)?$",
                features_match.group(1),
            ):
                issues.append("Codex Hooks are disabled in config.toml")
            trust_states = parse_hook_trust_states(config_text)
            trusted_count = 0
            for event_name, group_index, handler_index, group, handler in v2_handlers:
                if event_name not in HOOK_EVENT_LABELS:
                    issues.append(f"unsupported Hook event in hooks.json: {event_name}")
                    continue
                event_label = HOOK_EVENT_LABELS[event_name]
                expected = command_hook_hash(event_name, group, handler)
                raw_key = f"{hooks_config}:{event_label}:{group_index}:{handler_index}"
                file_key = f"file:{raw_key}"
                candidates = [trust_states.get(raw_key), trust_states.get(file_key)]
                if not any(
                    state
                    and state.get("enabled") != "false"
                    and state.get("trusted_hash") == expected
                    for state in candidates
                ):
                    issues.append(f"Hook is untrusted or modified: {event_label}:{group_index}:{handler_index}")
                else:
                    trusted_count += 1
            detail["trusted_v2_hooks"] = trusted_count
            detail["configured_v2_hooks"] = len(v2_handlers)
        except OSError as exc:
            warnings.append(f"could not verify config.toml Hook feature: {exc}")
    heartbeat_epoch = state.get("last_hook_heartbeat_epoch")
    if heartbeat_epoch is None:
        issues.append("no V2 Hook heartbeat has been observed")
    elif time.time() - float(heartbeat_epoch) > 7 * 86400:
        warnings.append("V2 Hook heartbeat is older than 7 days")
    if state.get("last_model_fallback"):
        warnings.append(f"Curator model fallback occurred: {state['last_model_fallback']}")
    if state.get("last_hook_error"):
        warnings.append(f"last Hook error: {state['last_hook_error']}")
    return issues, warnings, detail


def doctor(root: Path, config: Dict[str, Any]) -> Dict[str, Any]:
    issues: List[str] = []
    warnings: List[str] = []
    mem = memory_dir(root)
    manifest = load_json(mem / MANIFEST, default=None)
    if manifest is None:
        issues.append("missing manifest.json")
    elif manifest.get("schema_version") != SCHEMA_VERSION:
        issues.append(f"unsupported manifest schema {manifest.get('schema_version')}")
    if not (mem / "current.md").is_file():
        issues.append("missing current.md")
    lock = runtime_dir(root) / "lock.json"
    if lock.exists():
        lock_data = load_json(lock, default={}) or {}
        age = time.time() - float(lock_data.get("created_epoch", 0))
        warnings.append(f"memory lock present ({int(age)}s old): {lock_data.get('transaction_id')}")
    transactions = [path for path in (runtime_dir(root) / "transactions").glob("*") if path.is_dir()]
    if transactions:
        warnings.append(f"incomplete transactions: {len(transactions)}")
        for transaction in transactions:
            log = load_json(transaction / "commit-log.json", default={}) or {}
            if log.get("state") == "applying":
                issues.append(f"transaction requires recovery: {transaction.name}")
    invalid_pending = 0
    sessions_root = runtime_dir(root) / "sessions"
    if sessions_root.exists():
        for pending in sessions_root.glob("*/pending.jsonl"):
            _records, pending_warnings = read_pending(pending)
            invalid_pending += len(pending_warnings)
            warnings.extend(pending_warnings)
    current_size = (mem / "current.md").stat().st_size if (mem / "current.md").exists() else 0
    if current_size > 4096:
        warnings.append(f"current.md exceeds soft budget: {current_size} bytes")
    status = collect_status(root, config) if manifest else {}
    storage = config.get("storage", {})
    runtime_limit = int(storage.get("runtime_soft_limit_mb", 20)) * 1024 * 1024
    project_limit = int(storage.get("project_soft_limit_mb", 50)) * 1024 * 1024
    if status and status["runtime_bytes"] > runtime_limit:
        warnings.append("runtime exceeds configured soft limit")
    if status and status["memory_bytes"] > project_limit:
        warnings.append("project memory exceeds configured soft limit")
    hook_issues, hook_warnings, hook_status = hook_installation_status(root)
    issues.extend(hook_issues)
    warnings.extend(hook_warnings)
    return {
        "healthy": not issues and invalid_pending == 0,
        "issues": issues,
        "warnings": warnings,
        "status": status,
        "config": {
            "path": str(config_path()),
            "mode": config.get("mode"),
            "visibility": config.get("visibility"),
            "curator": config.get("curator"),
        },
        "hook": hook_status,
    }


def gc_runtime(root: Path, config: Dict[str, Any]) -> Dict[str, Any]:
    ensure_allowed(root, config)
    removed: List[str] = []
    now = time.time()
    sessions_root = runtime_dir(root) / "sessions"
    if sessions_root.exists():
        for session in [path for path in sessions_root.iterdir() if path.is_dir()]:
            pending, _warnings = read_pending(session / "pending.jsonl")
            newest = max((item.stat().st_mtime for item in session.rglob("*") if item.is_file()), default=0)
            if not pending and newest and now - newest > 7 * 86400:
                shutil.rmtree(session)
                removed.append(str(session))
    transactions_root = runtime_dir(root) / "transactions"
    limit = int(config.get("storage", {}).get("failed_transaction_limit", 3))
    rolled_back: List[Path] = []
    if transactions_root.exists():
        for tx in [path for path in transactions_root.iterdir() if path.is_dir()]:
            log = load_json(tx / "commit-log.json", default={}) or {}
            if log.get("state") in {"rolled_back", "finalized"}:
                rolled_back.append(tx)
        rolled_back.sort(key=lambda path: path.stat().st_mtime, reverse=True)
        for tx in rolled_back[limit:]:
            shutil.rmtree(tx)
            removed.append(str(tx))
    state = load_json(runtime_dir(root) / "project-state.json", default={}) or {}
    state["last_gc_at"] = utc_now()
    atomic_write_json(runtime_dir(root) / "project-state.json", state)
    return {"status": "ok", "removed": removed, "durable_memory_deleted": False}


def output(value: Any, as_json: bool = True) -> None:
    if as_json:
        print(json.dumps(value, ensure_ascii=False, indent=2))
    else:
        print(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Codex Memory V2 control plane")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("bootstrap", "migrate-v1", "status", "doctor", "gc"):
        item = sub.add_parser(name)
        item.add_argument("--project-root", required=True)
        item.add_argument("--json", action="store_true")
    prepare_cmd = sub.add_parser("prepare")
    prepare_cmd.add_argument("--project-root", required=True)
    prepare_cmd.add_argument("--session-id", required=True)
    prepare_cmd.add_argument("--json", action="store_true")
    commit_cmd = sub.add_parser("commit")
    commit_cmd.add_argument("--project-root", required=True)
    commit_cmd.add_argument("--transaction-id", required=True)
    commit_cmd.add_argument("--commit-token", required=True)
    commit_cmd.add_argument("--json", action="store_true")
    recover_cmd = sub.add_parser("recover")
    recover_cmd.add_argument("--project-root", required=True)
    recover_cmd.add_argument("--transaction-id", required=True)
    recover_cmd.add_argument("--json", action="store_true")
    apply_cmd = sub.add_parser("apply-result")
    apply_cmd.add_argument("--project-root", required=True)
    apply_cmd.add_argument("--transaction-id", required=True)
    apply_cmd.add_argument("--result-file", required=True)
    apply_cmd.add_argument("--json", action="store_true")
    abandon_cmd = sub.add_parser("abandon")
    abandon_cmd.add_argument("--project-root", required=True)
    abandon_cmd.add_argument("--transaction-id", required=True)
    abandon_cmd.add_argument("--reason", required=True)
    abandon_cmd.add_argument("--json", action="store_true")
    fleet_cmd = sub.add_parser("fleet-status")
    fleet_cmd.add_argument("--report")
    fleet_cmd.add_argument("--json", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        config = load_config()
        if args.command == "fleet-status":
            report = (
                Path(args.report).expanduser().resolve()
                if args.report
                else config_path().parent / "fleet-status.md"
            )
            result = fleet_status(config, report)
        else:
            root = resolve_project_root(args.project_root)
        if args.command == "bootstrap":
            result = bootstrap(root, config)
        elif args.command == "migrate-v1":
            result = migrate_v1(root, config)
        elif args.command == "status":
            result = collect_status(root, config)
        elif args.command == "doctor":
            result = doctor(root, config)
        elif args.command == "gc":
            result = gc_runtime(root, config)
        elif args.command == "prepare":
            result = prepare(root, config, args.session_id)
        elif args.command == "commit":
            result = commit(root, config, args.transaction_id, args.commit_token)
        elif args.command == "recover":
            result = recover(root, config, args.transaction_id)
        elif args.command == "apply-result":
            result = apply_result(root, config, args.transaction_id, Path(args.result_file).resolve())
        elif args.command == "abandon":
            result = abandon(root, config, args.transaction_id, args.reason)
        elif args.command == "fleet-status":
            pass
        else:
            raise MemoryCtlError(f"unsupported command: {args.command}")
        output(result, as_json=True)
        return 0
    except MemoryCtlError as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
