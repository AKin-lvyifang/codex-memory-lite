<!-- codex-memory:template=current:v1 -->

# 当前目标

- 把“账单导入优化”作为当前主线推进，先补齐缺失页面，再统一共享规则。

# 范围 / 不做

- 做：
  - 继续推进当前主线需求
  - 统一共享组件使用方式
  - 保持项目级结构化记忆为唯一主入口
- 不做：
  - 不把历史流水继续追加回 `codex-handoff.md`
  - 不重新把旧任务混回当前状态

# 当前状态

- 已完成：
  - 项目已启用 `.codex-memory/`
  - 旧 handoff 已迁移并冻结
  - 前端规则与任务规则已拆出
- 进行中：
  - 当前主线任务仍在推进
- 未开始：
  - 下一轮细节优化

# 稳定约束

- 新会话先读 `current.md`
- 长期规则统一放在 `spec/`
- 大任务单独建 `tasks/active/<task>/`
- 历史过程只放 `archive/`

# 关键索引

- 活跃任务：`sample-feature`
- 关键文件 / 路径：
  - `.codex-memory/spec/index.md`
  - `.codex-memory/tasks/index.md`
  - `.codex-memory/tasks/active/sample-feature/brief.md`

# 风险 / 下一步

- 风险：
  - 如果继续把历史过程写回 `current.md`，结构会再次膨胀
- 下一步：
  - 完成当前任务后更新任务记录，并归档本轮过程
