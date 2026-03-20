# 提升规则

当你判断项目内容是否值得提升到 `{GLOBAL_MEMORY_ROOT}` 时，使用这份规则。

## 只有在以下情况才提升

- 规则、偏好或工作流已经明显跨项目复用
- 内容至少跨过两次会话，或已经出现在多个项目里
- 内容已经确认，并且后续大概率还会再用到
- 落点明确：`current.md`、`spec/*.md` 或 `topics/active/<topic>/`

## 以下情况拒绝提升

- 内容只是今天这个项目的进度流水
- 内容包含项目专属路径、分支名或临时文件引用
- 内容仍然只是猜测、草稿或未解决争议
- 内容只是一次性例外，应该留在项目历史中

## 路由指引

- 跨项目的当前状态 -> `{GLOBAL_MEMORY_ROOT}/current.md`
- 持久规则 -> `{GLOBAL_MEMORY_ROOT}/spec/*.md`
- 持续推进的跨项目主题 -> `{GLOBAL_MEMORY_ROOT}/topics/active/<topic>/`
- 已过期的上下文 -> `{GLOBAL_MEMORY_ROOT}/archive/`

## 回写规则

提升完成后，更新 `{GLOBAL_MEMORY_ROOT}/projects/index.md`；必要时，在项目的 `.codex-memory/current.md` 中新增或刷新 `关联全局主题`。

## 校验命令

运行：

```bash
python3 scripts/validate_global_memory.py --project-root "<project-root>"
```
