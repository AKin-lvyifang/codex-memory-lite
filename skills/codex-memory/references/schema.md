# V2 Schema

## Manifest

`.codex-memory/manifest.json` 是 V2 机器入口：

```json
{
  "schema_version": 2,
  "project_id": "uuid",
  "memory_revision": 0,
  "layout_mode": "compat-v1",
  "last_sync_at": null,
  "auto_sync": true
}
```

`compat-v1` 表示继续使用原有 `current/spec/tasks/active/archive`，仅增加 V2 元数据和事务层。

## Task meta

试点在原 V1 Task 目录旁增加 `meta.json`：

```json
{
  "task_id": "uuid",
  "slug": "a-share-daily-review",
  "status": "active",
  "created_at": "ISO-8601",
  "updated_at": "ISO-8601",
  "legacy_path": "tasks/active/a-share-daily-review"
}
```

## Pending event

```json
{
  "schema_version": 2,
  "event_id": "session-id:1",
  "session_id": "session-id",
  "seq": 1,
  "event_type": "user_prompt",
  "created_at": "ISO-8601",
  "payload": {},
  "checksum": "sha256"
}
```

## Sync plan

`outcome` 必须为 `write`、`no-op` 或 `pending`。候选 disposition 必须为 `write`、`skip` 或 `unresolved`。

```json
{
  "schema_version": 2,
  "transaction_id": "uuid",
  "base_revision": 0,
  "outcome": "write",
  "summary": "本轮更新了什么",
  "candidates": [
    {
      "candidate_id": "c1",
      "category": "progress",
      "disposition": "write",
      "target": "current.md",
      "source_event_ids": ["session-id:1"],
      "reason": "后续继续任务需要"
    }
  ]
}
```

## Coverage report

```json
{
  "schema_version": 2,
  "transaction_id": "uuid",
  "complete": true,
  "covered_event_ids": ["session-id:1"],
  "unresolved": []
}
```

## Curator result

Curator 只返回结构化结果，不直接写文件。完整约束见 `curator-output.schema.json`。

- `files` 只列真实变化的完整文件内容。
- `path` 必须属于事务的 `allowed_write_files`。
- 每个 source event ID 必须被 candidate 覆盖。
- `no-op` 不得包含文件或更新类别。

## Audit receipt

提交、放弃和恢复只在 `.runtime/audit/YYYY-MM.jsonl` 留小型审计记录。记录 event ID、处置理由、revision 和变更路径，不复制完整聊天与文件正文。
