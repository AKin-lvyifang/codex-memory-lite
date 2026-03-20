---
name: codex-memory-bootstrap
description: 当用户说“初始化这个项目记忆”，或项目进入长任务、复杂协作、跨会话续接阶段时使用。
---

# Codex Memory Bootstrap

在需要长期协作的项目中，初始化结构化上下文目录，避免继续依赖单文件 handoff。

## 写入前校验

在创建 `.codex-memory/` 之前，先确定绝对路径变量：`PROJECT_ROOT`。

- `PROJECT_ROOT` 必须是当前会话对应的项目根目录
- 不得把 `~`、`/`、`~/.config/opencode`、`~/.codex`、skills 目录、配置目录当成项目根目录
- 如果当前目录看起来不像项目目录，或项目根目录仍不明确，先停止创建，再确认目录
- 后续所有目录和文件都必须创建在 `{PROJECT_ROOT}/.codex-memory/` 下
- 不要直接把裸相对路径 `.codex-memory/` 当成最终创建目标

## 适用场景

满足任一条件时使用：
- 用户明确说“初始化这个项目记忆”
- 当前任务会跨多个会话继续推进
- 当前任务涉及多个文件、多个页面或多个主题
- 当前项目已有 handoff/规则/历史堆积
- 当前会话已出现上下文膨胀风险

## 自然触发短语

- 初始化这个项目记忆

## 目标

创建最小可用的 `.codex-memory/` 结构，并在项目根目录建立或更新项目级 `AGENTS.md`。

其中：
- 若项目里没有 `AGENTS.md`，必须从 `templates/project-agents.md` 创建完整文件
- 若项目里已有 `AGENTS.md`，只更新受管控的 `CODEX-MEMORY` 管理块
- 写完后必须运行校验脚本，确认 `AGENTS.md` 符合模板或区块规则

## 执行步骤

1. 检查项目根目录是否已存在 `.codex-memory/`
2. 若不存在，则创建以下结构：

```text
.codex-memory/
├── current.md
├── spec/
│   ├── index.md
│   ├── design-rules.md
│   ├── frontend-design-standards.md
│   ├── frontend-page-workflow.md
│   ├── component-reuse.md
│   └── workflow-rules.md
├── tasks/
│   ├── index.md
│   ├── active/
│   └── archive/
└── archive/
```

3. 使用标准模板写入上述文件
4. 处理项目级 `AGENTS.md`：
   - 若项目根目录不存在 `AGENTS.md`，必须使用 `templates/project-agents.md` 创建完整文件
   - 若项目根目录已存在 `AGENTS.md`，则只追加或更新 `templates/project-agents-block.md` 对应的 `CODEX-MEMORY` 管理块，不要破坏用户其他内容
5. 运行校验：
   - 新创建的完整文件：`python3 scripts/validate_project_agents.py --project-root <project-root> --mode create`
   - 仅更新管理块：`python3 scripts/validate_project_agents.py --project-root <project-root> --mode update`
6. 若项目中存在旧 handoff 文件，如 `codex-handoff.md`，则记录"待迁移"提示，但不要自动删除旧文件
7. 汇报初始化结果：
   - 本次使用的 `PROJECT_ROOT`
   - 已创建目录
   - 已创建文件
   - `AGENTS.md` 是新建还是更新
   - `AGENTS.md` 校验结果
   - 是否发现旧 handoff
   - 是否建议下一步执行迁移

## 模板与校验

- 完整项目级 `AGENTS.md` 模板：`templates/project-agents.md`
- 管理块模板：`templates/project-agents-block.md`
- 校验脚本：`scripts/validate_project_agents.py`

校验要求：
- `AGENTS.md` 必须存在
- `CODEX-MEMORY:START / END` 只能各出现一次
- 若是新创建的完整文件，内容必须与 `templates/project-agents.md` 一致
- 若是更新已有文件，管理块内容必须与 `templates/project-agents-block.md` 一致

## 初始化完成后应提醒用户

- 该项目已启用 `.codex-memory/`
- 后续新会话优先读取 `current.md`
- 项目级 `AGENTS.md` 已按模板创建或按模板块更新，并已通过校验
- 若存在旧 handoff，建议执行迁移而不是继续双轨维护

## 约束

- 不要自动删除旧 handoff 文件
- 不要在初始化阶段擅自迁移旧内容
- 不要把历史过程直接塞进 `current.md`
- 不要在项目里没有 `AGENTS.md` 时临场自由生成，必须使用 `templates/project-agents.md`
- 不要在写完 `AGENTS.md` 后跳过校验
- 在 `PROJECT_ROOT` 未确认前，不要创建任何 `.codex-memory/` 目录或文件
