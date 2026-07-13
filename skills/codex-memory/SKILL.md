---
name: codex-memory
description: 自动维护和读取项目级 `.codex-memory/`。当 Hook 要求初始化、恢复或同步项目记忆，用户询问项目进度、决定或历史，项目存在未同步状态，或需要迁移、检查、恢复和清理旧 Memory 时使用。日常同步由 Hook 自动完成，不要求用户手动触发。
---

# Codex Memory V2

把项目进度、长期任务、决定和关键索引保存为可恢复的项目记忆。Hook 收集事件并决定何时检查；只读 Curator 判断内容价值；`memoryctl.py` 校验并提交。

## 路由

- **查看进度或恢复上下文**：运行 `status`，再按需读取 `current.md`、活跃 Task；不要默认读取全部 archive。
- **Hook 请求同步或恢复**：执行“自动同步”。
- **新项目**：首轮 Hook 自动注册并运行 `bootstrap`；失败时下个 Prompt 重试。手动排障时才直接运行该命令。不得创建或修改项目 `AGENTS.md`。
- **V1 项目试点**：运行 `migrate-v1`，保留原文件和旧目录。
- **查看全部项目运行状态**：运行 `fleet-status`，读取统一观察台账。
- **排障**：运行 `doctor`；有未完成事务时先修复，再读 Memory 正文。
- **清理**：只清理临时运行文件；已确认长期记忆不得删除。

## 命令入口

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/codex-memory/scripts/memoryctl.py" <command> --project-root "<绝对项目根>"
```

常用命令：

```text
bootstrap
migrate-v1
status --json
prepare --session-id <id>
apply-result --transaction-id <id> --result-file <path>
commit --transaction-id <id> --commit-token <prepare 返回的临时能力>
recover --transaction-id <id>
abandon --transaction-id <id> --reason <text>
doctor --json
gc
fleet-status
```

`fleet-status` 会刷新 `~/.codex/memory-v2/fleet-status.md`。台账集中显示每个项目最近一次 Hook、最近一次整理结果、待整理事件、未完成事务、错误和空间占用，并实时核对 Hook 注册、信任和脚本哈希。它区分“Hook 在线但尚未整理”和“已完成 write/no-op 闭环”。用户询问“记忆有没有运行”“哪些项目有积压”或“观察记忆状态”时，直接运行该命令，不要求用户自己检查目录。

## 自动同步

1. Hook 把 Prompt、真实文件变化、最终回答和压缩边界写入本 Session 的 pending。
2. 仅在文件变化、强信号、压缩、恢复或 pending 达到阈值时运行 `prepare`；普通检查立即结束。
3. 若返回 `no_pending`，直接结束，不显示成功通知。
4. 若创建事务，Hook 启动一个临时、只读的 Codex Curator：
   - 模型：`gpt-5.6-sol`
   - 推理强度：`low`
   - 若模型不可用才继承当前模型，并保留回退告警。
   - 独立临时 `CODEX_HOME`，不加载个人 Skill。
   - `read-only` sandbox、`approval_policy=never`、关闭 Hook 和多 Agent。
5. Hook 把 `source.json` 和允许读取的 Memory 副本作为数据传入 Curator。
6. Curator 返回严格 JSON，必须完成：
   - 判断 `write` 或 `no-op`
   - 每个候选标记 `write`、`skip` 或 `unresolved`
   - 保留来源 event ID 和理由
   - 第二遍重读来源检查漏项
   - 只返回允许文件的完整候选内容，不直接写任何文件
7. 运行 `apply-result`。脚本验证来源覆盖、路径白名单、文件大小、写入类别和真实变化；失败时保留 pending。
8. 若有 `unresolved`，放弃临时事务但保留 pending，交给主 Agent 处理异常项。
9. Hook 使用 `prepare` 返回且不写入事务正文的临时 commit capability 运行 `commit`；Curator 或其他子 Agent 没有该能力。单文件原子替换，manifest revision 最后更新；中断后用 `recover` 回滚或收口。
10. 只有真实写入时显示一行：`已记录：<实际更新类别>`；`no-op` 保持安静。

详细语义规则见 [references/sync-policy.md](references/sync-policy.md)。数据结构见 [references/schema.md](references/schema.md)。

## Curator 边界

Curator 是独立、快速、只读的记忆整理员，不是工程执行者：

- 只读取 Hook 明确传入的事务包。
- 不调用工具，不修改代码、项目文档、`AGENTS.md`、事务目录或正式 `.codex-memory/`。
- 不创建更多子 Agent。
- 只输出符合 `references/curator-output.schema.json` 的 JSON，不保存内部推理链。
- 不把未确认脑暴写成决定。
- 冲突、架构、安全、不可逆操作、跨项目归属不清时返回 `unresolved`。

## 读取原则

默认顺序：

1. `.codex-memory/current.md`
2. V2 manifest 指向的活跃 Task
3. 相关 spec 或正式项目真源
4. 只有追溯时才读 archive / cold archive

真实代码、配置、测试和用户最新确认高于旧 Memory。发现冲突时标记过期并修正，不能让 Memory 覆盖真实事实。

## 长期保存

- 已确认长期记忆不自动删除。
- 临时 pending 在成功提交后可以清理，因为内容已经进入长期记忆或被明确判定为 `skip`。
- 完成 Task 先生成热摘要，原始长期记忆按月压缩进入冷归档。
- 当前试点不主动搬迁现有历史；只验证 manifest、事件、事务和恢复链路。

## 禁止

- 不要求用户手动同步日常记忆。
- 不让 Hook 用正则判断业务重要性。
- 不在每个工具调用后启动 Curator。
- 不把 `agent` 类型 Hook 当成已支持能力；当前官方实现只执行 command Hook。
- 不直接覆盖 V1 Memory、旧 Task 或旧 archive。
- 不修改项目 `AGENTS.md`，除非用户明确要求修改那一句路由。
- 不在校验失败时清空 pending 或宣称“已记录”。
