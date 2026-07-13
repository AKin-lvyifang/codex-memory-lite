import importlib.util
import json
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "memoryctl.py"
SPEC = importlib.util.spec_from_file_location("memoryctl", MODULE_PATH)
memoryctl = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(memoryctl)


class MemoryCtlTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        self.config = {
            "enabled": True,
            "mode": "test",
            "project_roots": [str(self.root)],
            "storage": {"failed_transaction_limit": 3},
        }
        memory = self.root / ".codex-memory"
        task = memory / "tasks" / "active" / "test-task"
        task.mkdir(parents=True)
        (memory / "spec").mkdir(parents=True)
        (memory / "archive").mkdir(parents=True)
        (memory / "current.md").write_text("# Current\n\n- Original.\n", encoding="utf-8")
        (memory / "spec" / "index.md").write_text("# Spec\n", encoding="utf-8")
        (memory / "tasks" / "index.md").write_text("# Tasks\n", encoding="utf-8")
        (task / "brief.md").write_text("# Brief\n", encoding="utf-8")
        (task / "decisions.md").write_text("# Decisions\n", encoding="utf-8")
        (task / "refs.md").write_text("# Refs\n", encoding="utf-8")
        self.agents = self.root / "AGENTS.md"
        self.agents.write_text("# Project rules\n", encoding="utf-8")
        memoryctl.migrate_v1(self.root, self.config)

    def tearDown(self):
        self.temporary.cleanup()

    def append_event(self, session_id="session-1", seq=1, event_type="user_prompt"):
        session, state_path, pending_path = memoryctl.session_paths(self.root, session_id)
        session.mkdir(parents=True, exist_ok=True)
        unsigned = {
            "schema_version": 2,
            "event_id": f"{session_id}:{seq}",
            "session_id": session_id,
            "turn_id": "turn-1",
            "seq": seq,
            "event_type": event_type,
            "created_at": memoryctl.utc_now(),
            "payload": {"text": "test"},
        }
        record = dict(unsigned)
        record["checksum"] = memoryctl.sha256_bytes(
            memoryctl.canonical_json(unsigned).encode("utf-8")
        )
        with pending_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        memoryctl.atomic_write_json(state_path, {"next_seq": seq + 1})
        return record

    def write_result(self, transaction_dir, result):
        path = Path(transaction_dir) / "test-result.json"
        memoryctl.atomic_write_json(path, result)
        return path

    @staticmethod
    def no_op_result(event_ids):
        return {
            "outcome": "no-op",
            "summary": "No durable project change.",
            "updated_categories": [],
            "candidates": [
                {
                    "candidate_id": "c1",
                    "category": "skip",
                    "disposition": "skip",
                    "target": None,
                    "source_event_ids": event_ids,
                    "reason": "Temporary test conversation.",
                }
            ],
            "files": [],
            "unresolved": [],
        }

    def test_migration_preserves_agents_and_v1_files(self):
        self.assertEqual(self.agents.read_text(encoding="utf-8"), "# Project rules\n")
        manifest = memoryctl.load_json(self.root / ".codex-memory" / "manifest.json")
        self.assertEqual(manifest["layout_mode"], "compat-v1")
        self.assertTrue(
            (self.root / ".codex-memory" / "tasks" / "active" / "test-task" / "meta.json").is_file()
        )

    def test_hook_hash_matches_codex_normalization(self):
        value = memoryctl.command_hook_hash(
            "UserPromptSubmit",
            {"hooks": []},
            {
                "type": "command",
                "command": "node /Users/tester/.codex/ai/hooks/codex-memory-bootstrap-first-prompt.js",
                "statusMessage": "Checking project memory",
            },
        )
        self.assertEqual(
            value,
            "sha256:f56903ff9d71c5f5a48b674a265d35326b8ddc549ba46b8207d4a285a82ea530",
        )

    def test_no_op_covers_and_clears_pending_without_revision_change(self):
        event = self.append_event()
        prepared = memoryctl.prepare(self.root, self.config, "session-1")
        result_path = self.write_result(
            prepared["transaction_dir"], self.no_op_result([event["event_id"]])
        )
        memoryctl.apply_result(
            self.root, self.config, prepared["transaction_id"], result_path
        )
        committed = memoryctl.commit(
            self.root,
            self.config,
            prepared["transaction_id"],
            prepared["commit_token"],
        )
        self.assertEqual(committed["outcome"], "no-op")
        self.assertEqual(committed["memory_revision"], 0)
        self.assertFalse(
            memoryctl.session_paths(self.root, "session-1")[2].exists()
        )
        self.assertEqual(
            (self.root / ".codex-memory" / "current.md").read_text(encoding="utf-8"),
            "# Current\n\n- Original.\n",
        )

    def test_write_updates_only_allowed_file_and_revision(self):
        event = self.append_event()
        prepared = memoryctl.prepare(self.root, self.config, "session-1")
        content = "# Current\n\n- Original.\n- Durable update.\n"
        result = {
            "outcome": "write",
            "summary": "Recorded project progress.",
            "updated_categories": ["progress"],
            "candidates": [
                {
                    "candidate_id": "c1",
                    "category": "progress",
                    "disposition": "write",
                    "target": "current.md",
                    "source_event_ids": [event["event_id"]],
                    "reason": "Needed for the next session.",
                }
            ],
            "files": [{"path": "current.md", "content": content}],
            "unresolved": [],
        }
        result_path = self.write_result(prepared["transaction_dir"], result)
        memoryctl.apply_result(
            self.root, self.config, prepared["transaction_id"], result_path
        )
        committed = memoryctl.commit(
            self.root,
            self.config,
            prepared["transaction_id"],
            prepared["commit_token"],
        )
        self.assertEqual(committed["memory_revision"], 1)
        self.assertEqual(
            (self.root / ".codex-memory" / "current.md").read_text(encoding="utf-8"),
            content,
        )
        self.assertEqual(self.agents.read_text(encoding="utf-8"), "# Project rules\n")

    def test_result_rejects_missing_event_coverage(self):
        first = self.append_event(seq=1)
        self.append_event(seq=2, event_type="assistant_final")
        prepared = memoryctl.prepare(self.root, self.config, "session-1")
        result_path = self.write_result(
            prepared["transaction_dir"], self.no_op_result([first["event_id"]])
        )
        with self.assertRaises(memoryctl.MemoryCtlError):
            memoryctl.apply_result(
                self.root, self.config, prepared["transaction_id"], result_path
            )
        memoryctl.abandon(
            self.root, self.config, prepared["transaction_id"], "test cleanup"
        )

    def test_result_rejects_path_outside_transaction(self):
        event = self.append_event()
        prepared = memoryctl.prepare(self.root, self.config, "session-1")
        result = {
            "outcome": "write",
            "summary": "Bad write.",
            "updated_categories": ["progress"],
            "candidates": [
                {
                    "candidate_id": "c1",
                    "category": "progress",
                    "disposition": "write",
                    "target": "AGENTS.md",
                    "source_event_ids": [event["event_id"]],
                    "reason": "Attempted escape.",
                }
            ],
            "files": [{"path": "AGENTS.md", "content": "bad"}],
            "unresolved": [],
        }
        result_path = self.write_result(prepared["transaction_dir"], result)
        with self.assertRaises(memoryctl.MemoryCtlError):
            memoryctl.apply_result(
                self.root, self.config, prepared["transaction_id"], result_path
            )
        self.assertEqual(self.agents.read_text(encoding="utf-8"), "# Project rules\n")
        memoryctl.abandon(
            self.root, self.config, prepared["transaction_id"], "test cleanup"
        )

    def test_result_rejects_deleting_existing_durable_decisions(self):
        event = self.append_event()
        prepared = memoryctl.prepare(self.root, self.config, "session-1")
        target = "tasks/active/test-task/decisions.md"
        result = {
            "outcome": "write",
            "summary": "Attempted destructive rewrite.",
            "updated_categories": ["decision"],
            "candidates": [
                {
                    "candidate_id": "c1",
                    "category": "decision",
                    "disposition": "write",
                    "target": target,
                    "source_event_ids": [event["event_id"]],
                    "reason": "New decision.",
                }
            ],
            "files": [{"path": target, "content": "# Replacement\n"}],
            "unresolved": [],
        }
        result_path = self.write_result(prepared["transaction_dir"], result)
        with self.assertRaises(memoryctl.MemoryCtlError):
            memoryctl.apply_result(
                self.root, self.config, prepared["transaction_id"], result_path
            )
        self.assertEqual(
            (
                self.root
                / ".codex-memory"
                / "tasks"
                / "active"
                / "test-task"
                / "decisions.md"
            ).read_text(encoding="utf-8"),
            "# Decisions\n",
        )
        memoryctl.abandon(
            self.root, self.config, prepared["transaction_id"], "test cleanup"
        )

    def test_corrupt_pending_blocks_prepare(self):
        self.append_event()
        pending = memoryctl.session_paths(self.root, "session-1")[2]
        with pending.open("a", encoding="utf-8") as handle:
            handle.write("not-json\n")
        with self.assertRaises(memoryctl.MemoryCtlError):
            memoryctl.prepare(self.root, self.config, "session-1")

    def test_revision_conflict_preserves_pending_and_formal_memory(self):
        event = self.append_event()
        prepared = memoryctl.prepare(self.root, self.config, "session-1")
        content = "# Current\n\n- Conflict candidate.\n"
        result = {
            "outcome": "write",
            "summary": "Conflict test.",
            "updated_categories": ["progress"],
            "candidates": [
                {
                    "candidate_id": "c1",
                    "category": "progress",
                    "disposition": "write",
                    "target": "current.md",
                    "source_event_ids": [event["event_id"]],
                    "reason": "Needed later.",
                }
            ],
            "files": [{"path": "current.md", "content": content}],
            "unresolved": [],
        }
        result_path = self.write_result(prepared["transaction_dir"], result)
        memoryctl.apply_result(
            self.root, self.config, prepared["transaction_id"], result_path
        )
        manifest_path = self.root / ".codex-memory" / "manifest.json"
        manifest = memoryctl.load_json(manifest_path)
        manifest["memory_revision"] = 9
        memoryctl.atomic_write_json(manifest_path, manifest)
        with self.assertRaises(memoryctl.MemoryCtlError):
            memoryctl.commit(
                self.root,
                self.config,
                prepared["transaction_id"],
                prepared["commit_token"],
            )
        self.assertEqual(
            (self.root / ".codex-memory" / "current.md").read_text(encoding="utf-8"),
            "# Current\n\n- Original.\n",
        )
        self.assertTrue(memoryctl.session_paths(self.root, "session-1")[2].exists())
        memoryctl.abandon(
            self.root, self.config, prepared["transaction_id"], "test cleanup"
        )

    def test_recover_rolls_back_partial_commit(self):
        event = self.append_event()
        prepared = memoryctl.prepare(self.root, self.config, "session-1")
        content = "# Current\n\n- Partial commit.\n"
        result = {
            "outcome": "write",
            "summary": "Partial commit test.",
            "updated_categories": ["progress"],
            "candidates": [
                {
                    "candidate_id": "c1",
                    "category": "progress",
                    "disposition": "write",
                    "target": "current.md",
                    "source_event_ids": [event["event_id"]],
                    "reason": "Needed later.",
                }
            ],
            "files": [{"path": "current.md", "content": content}],
            "unresolved": [],
        }
        result_path = self.write_result(prepared["transaction_dir"], result)
        memoryctl.apply_result(
            self.root, self.config, prepared["transaction_id"], result_path
        )
        tx = Path(prepared["transaction_dir"])
        source, plan, _ = memoryctl.validate_plan(tx)
        entries = memoryctl.build_commit_entries(
            self.root / ".codex-memory", tx, plan
        )
        memoryctl.atomic_write_json(
            tx / "commit-log.json",
            {
                "transaction_id": prepared["transaction_id"],
                "state": "applying",
                "base_revision": 0,
                "target_revision": 1,
                "session_id": source["session_id"],
                "files": entries,
            },
        )
        memoryctl.atomic_write_text(
            self.root / ".codex-memory" / "current.md", content
        )
        recovered = memoryctl.recover(
            self.root, self.config, prepared["transaction_id"]
        )
        self.assertEqual(recovered["status"], "rolled_back")
        self.assertEqual(
            (self.root / ".codex-memory" / "current.md").read_text(encoding="utf-8"),
            "# Current\n\n- Original.\n",
        )
        self.assertTrue(memoryctl.session_paths(self.root, "session-1")[2].exists())

    def test_second_session_cannot_overwrite_active_transaction(self):
        self.append_event(session_id="session-1")
        self.append_event(session_id="session-2")
        first = memoryctl.prepare(self.root, self.config, "session-1")
        with self.assertRaises(memoryctl.MemoryCtlError):
            memoryctl.prepare(self.root, self.config, "session-2")
        lock = memoryctl.load_json(
            self.root / ".codex-memory" / ".runtime" / "lock.json"
        )
        self.assertEqual(lock["transaction_id"], first["transaction_id"])
        memoryctl.abandon(
            self.root, self.config, first["transaction_id"], "test cleanup"
        )

    def test_commit_rejects_actor_without_prepare_capability(self):
        event = self.append_event()
        prepared = memoryctl.prepare(self.root, self.config, "session-1")
        result_path = self.write_result(
            prepared["transaction_dir"], self.no_op_result([event["event_id"]])
        )
        memoryctl.apply_result(
            self.root, self.config, prepared["transaction_id"], result_path
        )
        with self.assertRaises(memoryctl.MemoryCtlError):
            memoryctl.commit(
                self.root,
                self.config,
                prepared["transaction_id"],
                "wrong-token",
            )
        self.assertTrue(memoryctl.session_paths(self.root, "session-1")[2].exists())
        memoryctl.abandon(
            self.root, self.config, prepared["transaction_id"], "test cleanup"
        )

    def test_prepare_commit_capability_is_safe_as_cli_argument(self):
        self.append_event()
        prepared = memoryctl.prepare(self.root, self.config, "session-1")
        self.assertTrue(prepared["commit_token"].startswith("cap_"))
        self.assertFalse(prepared["commit_token"].startswith("-"))
        memoryctl.abandon(
            self.root, self.config, prepared["transaction_id"], "test cleanup"
        )

    def test_unresolved_result_keeps_pending_and_formal_memory(self):
        event = self.append_event()
        prepared = memoryctl.prepare(self.root, self.config, "session-1")
        result = {
            "outcome": "no-op",
            "summary": "Source conflicts with existing project truth.",
            "updated_categories": [],
            "candidates": [
                {
                    "candidate_id": "c1",
                    "category": "decision",
                    "disposition": "unresolved",
                    "target": None,
                    "source_event_ids": [event["event_id"]],
                    "reason": "The source is insufficient.",
                }
            ],
            "files": [],
            "unresolved": ["Need main-agent verification."],
        }
        result_path = self.write_result(prepared["transaction_dir"], result)
        applied = memoryctl.apply_result(
            self.root, self.config, prepared["transaction_id"], result_path
        )
        self.assertEqual(applied["status"], "unresolved")
        memoryctl.abandon(
            self.root, self.config, prepared["transaction_id"], "unresolved test"
        )
        self.assertTrue(memoryctl.session_paths(self.root, "session-1")[2].exists())
        self.assertEqual(
            (self.root / ".codex-memory" / "current.md").read_text(encoding="utf-8"),
            "# Current\n\n- Original.\n",
        )

    def test_recover_finalizes_commit_after_manifest_advanced(self):
        event = self.append_event()
        prepared = memoryctl.prepare(self.root, self.config, "session-1")
        content = "# Current\n\n- Committed before checkpoint.\n"
        result = {
            "outcome": "write",
            "summary": "Finalize test.",
            "updated_categories": ["progress"],
            "candidates": [
                {
                    "candidate_id": "c1",
                    "category": "progress",
                    "disposition": "write",
                    "target": "current.md",
                    "source_event_ids": [event["event_id"]],
                    "reason": "Needed later.",
                }
            ],
            "files": [{"path": "current.md", "content": content}],
            "unresolved": [],
        }
        result_path = self.write_result(prepared["transaction_dir"], result)
        memoryctl.apply_result(
            self.root, self.config, prepared["transaction_id"], result_path
        )
        tx = Path(prepared["transaction_dir"])
        source, plan, _ = memoryctl.validate_plan(tx)
        entries = memoryctl.build_commit_entries(
            self.root / ".codex-memory", tx, plan
        )
        memoryctl.atomic_write_json(
            tx / "commit-log.json",
            {
                "transaction_id": prepared["transaction_id"],
                "state": "applying",
                "base_revision": 0,
                "target_revision": 1,
                "session_id": source["session_id"],
                "files": entries,
            },
        )
        memoryctl.atomic_write_text(
            self.root / ".codex-memory" / "current.md", content
        )
        manifest_path = self.root / ".codex-memory" / "manifest.json"
        manifest = memoryctl.load_json(manifest_path)
        manifest["memory_revision"] = 1
        memoryctl.atomic_write_json(manifest_path, manifest)
        recovered = memoryctl.recover(
            self.root, self.config, prepared["transaction_id"]
        )
        self.assertEqual(recovered["status"], "finalized")
        self.assertFalse(memoryctl.session_paths(self.root, "session-1")[2].exists())
        self.assertEqual(
            (self.root / ".codex-memory" / "current.md").read_text(encoding="utf-8"),
            content,
        )

    def test_gc_never_deletes_pending_or_durable_memory(self):
        self.append_event()
        durable = self.root / ".codex-memory" / "archive" / "durable.md"
        durable.write_text("# Durable\n", encoding="utf-8")
        result = memoryctl.gc_runtime(self.root, self.config)
        self.assertFalse(result["durable_memory_deleted"])
        self.assertTrue(durable.exists())
        self.assertTrue(memoryctl.session_paths(self.root, "session-1")[2].exists())

    def test_fleet_status_builds_one_observation_report(self):
        state_path = self.root / ".codex-memory" / ".runtime" / "project-state.json"
        memoryctl.atomic_write_json(
            state_path,
            {
                "last_hook_heartbeat_at": memoryctl.utc_now(),
                "last_hook_heartbeat_epoch": time.time(),
                "last_hook_event": "Stop",
                "last_hook_sync_at": memoryctl.utc_now(),
                "last_hook_sync_outcome": "no-op",
            },
        )
        self.config["excluded_project_roots"] = [
            {"path": "/tmp/legacy-project", "reason": "kept on V1"}
        ]
        report = self.root / "fleet-status.md"
        result = memoryctl.fleet_status(self.config, report, verify_hooks=False)
        self.assertEqual(result["totals"]["configured"], 1)
        self.assertEqual(result["totals"]["healthy"], 1)
        self.assertEqual(result["projects"][0]["last_outcome"], "no-op")
        self.assertTrue(report.is_file())
        report_text = report.read_text(encoding="utf-8")
        self.assertIn("Codex Memory V2 观察台账", report_text)
        self.assertIn(str(self.root), report_text)
        self.assertIn("/tmp/legacy-project", report_text)

    def test_fleet_status_marks_unmigrated_configured_project(self):
        second = self.root / "second-project"
        second.mkdir()
        config = dict(self.config)
        config["project_roots"] = [str(self.root), str(second)]
        result = memoryctl.fleet_status(config, verify_hooks=False)
        by_root = {item["project_root"]: item for item in result["projects"]}
        self.assertEqual(by_root[str(second)]["state"], "not_initialized")
        self.assertEqual(result["totals"]["attention"], 1)

    def test_fleet_status_does_not_hide_broken_hook_behind_recent_heartbeat(self):
        state_path = self.root / ".codex-memory" / ".runtime" / "project-state.json"
        memoryctl.atomic_write_json(
            state_path,
            {
                "last_hook_heartbeat_at": memoryctl.utc_now(),
                "last_hook_heartbeat_epoch": time.time(),
            },
        )
        with mock.patch.object(
            memoryctl,
            "hook_installation_status",
            return_value=(["Hook is untrusted or modified"], [], {}),
        ):
            project = memoryctl.fleet_project_status(str(self.root), self.config)
        self.assertEqual(project["state"], "needs_attention")
        self.assertIn("Hook is untrusted or modified", project["issues"])

    def test_fleet_status_marks_corrupt_pending_as_attention(self):
        self.append_event()
        pending = memoryctl.session_paths(self.root, "session-1")[2]
        with pending.open("a", encoding="utf-8") as handle:
            handle.write("not-json\n")
        project = memoryctl.fleet_project_status(
            str(self.root), self.config, verify_hooks=False
        )
        self.assertEqual(project["state"], "needs_attention")
        self.assertIn("pending 队列", project["issues"][0])

    def test_fleet_status_marks_storage_limit_breach_as_attention(self):
        config = dict(self.config)
        config["storage"] = {
            **self.config["storage"],
            "runtime_soft_limit_mb": 0,
            "project_soft_limit_mb": 50,
        }
        project = memoryctl.fleet_project_status(
            str(self.root), config, verify_hooks=False
        )
        self.assertEqual(project["state"], "needs_attention")
        self.assertTrue(any("运行数据超过" in issue for issue in project["issues"]))

    def test_fleet_status_distinguishes_online_from_completed_sync(self):
        state_path = self.root / ".codex-memory" / ".runtime" / "project-state.json"
        memoryctl.atomic_write_json(
            state_path,
            {
                "last_hook_heartbeat_at": memoryctl.utc_now(),
                "last_hook_heartbeat_epoch": time.time(),
            },
        )
        project = memoryctl.fleet_project_status(
            str(self.root), self.config, verify_hooks=False
        )
        self.assertEqual(project["state"], "online_unverified")

    def test_audit_summary_does_not_return_candidate_details(self):
        memoryctl.append_audit(
            self.root,
            {
                "type": "transaction_committed",
                "transaction_id": "test",
                "outcome": "no-op",
                "summary": "sensitive summary",
                "candidates": [{"reason": "sensitive reason"}],
            },
        )
        latest = memoryctl.audit_summary(self.root)["latest"]
        self.assertEqual(latest["transaction_id"], "test")
        self.assertNotIn("summary", latest)
        self.assertNotIn("candidates", latest)


if __name__ == "__main__":
    unittest.main()
