---
name: codex-memory-sync
description: 当用户说“同步当前项目记忆”，或在长任务阶段切换、准备结束线程、上下文变长时使用。
---

# Codex Memory Sync

在长任务、阶段切换、准备结束线程、上下文膨胀时，将会话中的有效信息同步到**当前工作目录（项目根目录）下的 `.codex-memory/`**。

**重要**：必须使用项目目录下的 `.codex-memory/`（如 `{PROJECT_ROOT}/.codex-memory/`），而不是全局的 `~/.codex-memory/`。

## 写入前校验

在任何读取、创建、写入动作之前，先明确一个绝对路径变量：`PROJECT_ROOT`。

- `PROJECT_ROOT` 必须是**当前会话对应的项目根目录**
- 不得把 `~`、`/`、`~/.config/opencode`、`~/.codex`、skills 目录、配置目录当成项目根目录
- 如果当前目录看起来像 home、配置目录、或无法确认项目根目录，**先停止写入**，先确认/读取当前会话目录，再继续
- 后续所有记忆路径都必须写成绝对路径：`{PROJECT_ROOT}/.codex-memory/...`
- 不要直接把裸相对路径 `.codex-memory/...` 当成最终落盘目标

## 适用场景

满足任一条件时使用：
- 用户明确说“同步当前项目记忆”
- 完成一轮阶段性工作
- 任务方向切换
- 准备结束当前线程
- 上下文已明显变长
- 用户明确要求"更新 current / 写入 archive / 提升规则"

## 自然触发短语

- 同步当前项目记忆

## 目标

把当前会话中的信息分流到正确位置：
- 当前有效状态 → `current.md`
- 长期稳定规则 → `spec/`
- 活跃任务上下文 → `tasks/active/<task>/`
- 历史过程 → `archive/`

## 执行步骤

1. 读取：
   - `.codex-memory/current.md`
   - `.codex-memory/spec/index.md`
   - 如存在活跃任务，再读对应任务 `brief.md`
2. 从当前会话中提炼信息，并按下面规则分类：

### A. current
写入 `current.md` 的内容必须是"当前仍有效"的：
- 当前目标
- 范围 / 不做
- 当前状态
- 稳定约束摘要
- 关键索引
- 风险 / 下一步

### B. spec
若某条规则满足任一条件，则提升到 `spec/`：
- 跨两次以上会话仍有效
- 在两个以上主题中重复出现
- 丢失后会导致明显返工

### C. tasks
若当前工作属于某个活跃任务，则同步更新：
- `brief.md`
- `decisions.md`
- `refs.md`

### D. archive
将本轮过程、旧目标、一次性微调、历史决策写入按月归档文件

3. 更新原则
- `current.md` 必须覆盖更新，不得继续按日期追加流水
- 历史信息写入 `archive/`，而不是残留在 `current.md`
- 活跃任务只保留仍在继续的信息
- 默认不要把所有节点 ID 都塞入 current，只保留关键少数
- 若发现目标路径不是 `{PROJECT_ROOT}/.codex-memory/`，立即停止，不要继续写

## 输出要求

同步完成后，汇报：
- 本次使用的 `PROJECT_ROOT`
- 更新了哪些文件
- 哪些内容进入 current
- 哪些内容进入 archive
- 哪些规则被提升到 spec
- 是否发现冲突或待确认项

## 约束

- 不要擅自删除 archive 中的旧记录
- 不要把"当前状态"和"历史过程"再次混写
- 不要在没有必要时建立任务目录
- 在 `PROJECT_ROOT` 未确认前，不要创建任何 `.codex-memory/` 目录或文件
