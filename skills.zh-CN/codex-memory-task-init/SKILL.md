---
name: codex-memory-task-init
description: 当用户说“这是个长期任务，记一下”或“为这个长期任务创建任务记忆”，或当前任务需要跨会话单独维护时使用。
---

# Codex Memory Task Init

## 写入前校验

在创建任务目录之前，先明确一个绝对路径变量：`PROJECT_ROOT`。

- `PROJECT_ROOT` 必须是当前会话对应的项目根目录
- 不得把 `~`、`/`、`~/.config/opencode`、`~/.codex`、skills 目录、配置目录当成项目根目录
- 如果当前目录看起来像 home、配置目录、或无法确认项目根目录，先停止创建，再确认目录
- 后续所有任务目录和文件都必须创建在 `{PROJECT_ROOT}/.codex-memory/tasks/active/<task-slug>/` 下
- 不要直接把裸相对路径 `.codex-memory/tasks/...` 当成最终创建目标

## 使用场景

满足任一条件时使用：
- 用户明确说“这是个长期任务，记一下”
- 用户明确说“为这个长期任务创建任务记忆”
- 当前任务会跨多个会话继续推进
- 当前任务需要单独维护目标、决定与关键引用
- 当前任务已经明显不适合只写在 `current.md` 中

## 自然触发短语

- 这是个长期任务，记一下
- 为这个长期任务创建任务记忆

## 目标

在 `.codex-memory/tasks/active/<task-slug>/` 下创建标准任务骨架。

## 固定输出

实际落盘路径必须是：

```text
{PROJECT_ROOT}/.codex-memory/tasks/active/<task-slug>/
```

下方仅用于展示项目内结构：

创建：

```text
.codex-memory/tasks/active/<task-slug>/
├── brief.md
├── decisions.md
└── refs.md
```

并更新：

```text
.codex-memory/tasks/index.md
```

## 执行规则

1. 先确认 `PROJECT_ROOT`；所有实际落盘路径都必须使用 `{PROJECT_ROOT}/.codex-memory/...` 绝对路径。
2. `<task-slug>` 需简短稳定，可读，不要带日期。
3. `brief.md`、`decisions.md`、`refs.md` 必须同时创建，缺一不可。
4. 所有文件必须从本 skill 自带模板生成。
5. 若任务目录已存在，则不重建，只补齐缺失文件并校验。
6. 更新 `tasks/index.md` 时，新增该任务入口与一句话说明。
7. 写完后执行结构校验；校验失败则停止并汇报。

## 汇报格式

- 本次使用的 `PROJECT_ROOT`
- 任务 slug
- 已创建文件
- 已补齐文件
- `tasks/index.md` 更新结果
- 校验结果

## 约束

- 不要在 `PROJECT_ROOT` 未确认前创建任何 `.codex-memory/tasks/` 目录或文件
- 若发现目标路径不是 `{PROJECT_ROOT}/.codex-memory/tasks/active/<task-slug>/`，立即停止，不要继续写
