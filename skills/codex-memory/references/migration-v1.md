# V1 Pilot Migration

试点迁移只增加 V2 控制层：

- 创建 `manifest.json`。
- 创建 `.runtime/`。
- 为 V1 Task 增加 `meta.json`。
- 生成 `tasks/index.v2.md`，不覆盖原 `tasks/index.md`。
- 保留项目 `AGENTS.md` 的 V1 区块，试点稳定后再单独迁移。
- 不移动、删除或重写 `current.md`、spec、brief、decisions、refs、archive。

试点通过后进入批量迁移：

- 先完整备份原 Memory、项目 `AGENTS.md` 和 V2 控制层。
- 将项目加入 V2 明确允许列表，再运行 `migrate-v1`。
- 只把 `<!-- CODEX-MEMORY:START -->` 到 `<!-- CODEX-MEMORY:END -->` 的旧管理块替换成一句 V2 读取入口；块外项目规则不变。
- 若文件带有 `codex-memory:template=project-agents:v1` 元数据，只把该元数据更新为 V2 路由标记，不改其他项目规则。
- 用 `fleet-status` 集中观察 Hook 心跳、写入、跳过、积压、事务、错误和空间。
- 明确保留 V1 的项目不得加入 V2 允许列表；旧 Memory 和历史副本不删除。

平级 Task 和月度冷归档属于后续存储优化，不是切换自动同步机制的前置条件。
