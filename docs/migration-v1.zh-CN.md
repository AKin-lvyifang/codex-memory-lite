# 从 Codex Memory Lite V1 迁移

[English](migration-v1.md)

V2 是一次工作流层面的破坏性升级。V1 依赖 4 个手动路由的 Skill 和 `AGENTS.md` 记忆说明；V2 改成 1 个运行 Skill 加自动 Hook。

迁移会保留已有记忆、任务、归档、`AGENTS.md` 和旧 Skill，不会偷偷删除。

## 先判断 V1 是否还在运行

出现以下任一情况，说明还有 V1：

- Skill 目录里存在 `codex-memory-bootstrap`、`codex-memory-task-init`、`codex-memory-sync` 或 `codex-memory-promote-global`
- 全局或项目 `AGENTS.md` 要求 Agent 调用这些 Skill
- 项目已有 `.codex-memory/current.md`，但没有 V2 `manifest.json`

迁移不需要删除 `.codex-memory/` 或旧 handoff 文件。

## 迁移步骤

1. 安装 V2：

```bash
npx --yes --package=https://github.com/AKin-lvyifang/codex-memory-lite/releases/download/v2.0.0/codex-memory-lite-2.0.0.tgz codex-memory-lite install
```

2. 新建一个 task，或重启 ChatGPT / Codex。
3. 打开一个 V1 项目，发送一条正常消息。
4. 确认 `.codex-memory/manifest.json` 的 `schema_version` 已经是 `2`。
5. 运行 doctor：

```bash
npx --yes --package=https://github.com/AKin-lvyifang/codex-memory-lite/releases/download/v2.0.0/codex-memory-lite-2.0.0.tgz codex-memory-lite doctor
```

6. 让 Agent 查看当前项目进度，确认 current、task、spec 仍然可读。
7. 只有试点项目通过后，才退出下面的 V1 路由。

## 自动 `migrate-v1` 会做什么

- 创建 V2 manifest、运行目录、事务元数据和必要的任务元数据。
- 保留已有 `current.md`、`spec/`、`tasks/`、`archive/`、`AGENTS.md` 和旧 handoff。
- 标记为兼容 V1 的布局，不重写历史正文。
- 在条件允许时，只把 `.codex-memory/.runtime/` 加入本地 Git exclude。

迁移阶段不会总结或删除旧历史。

## 退出旧路由

如果全局规则仍强制使用 V1，V2 就可能被拉回手动流程。

检查全局和项目 `AGENTS.md`，重点查找这些要求：

- 调用 `codex-memory-bootstrap`
- 调用 `codex-memory-task-init`
- 调用 `codex-memory-sync`
- 每次阶段变化或 task 结束都手动同步

只删除已经过时的记忆工作流说明。项目规范、架构要求、真实命令和产品约束都要保留。

如果项目里存在以下受管区块，它属于 V1 记忆路由：

```text
<!-- CODEX-MEMORY:START -->
...
<!-- CODEX-MEMORY:END -->
```

V2 不再需要这个区块。删除前先确认里面没有混入其他项目规范。

## 退出旧 Skill

V2 安装器会保留旧 Skill，因为其他工具或旧 task 可能仍在使用。等所有必要项目都通过 V2 验收后，再把以下目录移出活跃 Skill 搜索路径或归档：

```text
codex-memory-bootstrap/
codex-memory-task-init/
codex-memory-sync/
codex-memory-promote-global/
```

在旧 task 和外部软件彻底切换前保留备份。不要移除新的 `codex-memory/`。

## 回退

每次安装或更新都会把备份放在：

```text
${CODEX_HOME:-$HOME/.codex}/backups/codex-memory-lite/
```

如果只想停用 V2，不动项目：

```bash
npx --yes --package=https://github.com/AKin-lvyifang/codex-memory-lite/releases/download/v2.0.0/codex-memory-lite-2.0.0.tgz codex-memory-lite uninstall
```

它会移除 V2 运行组件和所属 Hook，但保留 `memory-v2/config.json` 和所有项目 `.codex-memory/`。只有明确回到 V1 时，才恢复旧路由。

## 迁移验收清单

- V2 doctor 通过。
- 项目存在 schema V2 manifest。
- current、spec、task 和 archive 原内容仍在。
- 自动迁移没有修改项目 `AGENTS.md`。
- 一条长期信息只记录一次，普通短对话保持安静。
- 全局规则不再强制调用 4 个 V1 Skill。
- 旧 task 和外部工具彻底切换前，旧 Skill 仍有备份。
