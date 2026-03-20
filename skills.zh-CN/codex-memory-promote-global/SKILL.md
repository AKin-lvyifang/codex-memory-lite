---
name: codex-memory-promote-global
description: 当用户说“把这个提升到全局记忆”，或需要把稳定的项目知识提升到 `{GLOBAL_MEMORY_ROOT}` 时使用。
---

# Codex Memory Promote Global

## 概述

把项目内稳定、可复用的记忆，从 `.codex-memory/` 提升到 `{GLOBAL_MEMORY_ROOT}`。当用户明确要求提升到全局层，或某条规则、工作方法、主题已经明显跨项目复用时，使用这个 skill。

## 适用场景

- 用户明确说“把这个提升到全局记忆”
- 用户明确要求“提升到全局记忆”“沉淀成跨项目规则”“把这个主题挂到全局”
- 同一条规则在两个以上项目重复出现
- 某个主题已经不再属于单项目，而是多个项目共用
- 线程即将结束，需要把稳定内容从项目层抽到全局层

## 自然触发短语

- 把这个提升到全局记忆
- 把这条规则沉淀到 global
- 这个经验跨项目可用，提到全局层

## 输入

- 当前项目根目录
- 当前项目 `.codex-memory/current.md`
- 当前项目相关 `spec/` 与活跃任务
- 全局根目录 `{GLOBAL_MEMORY_ROOT}`
- 参考规则：`references/promotion-rules.md`

## 工作流

1. 读取当前项目的 `.codex-memory/current.md`、相关 `spec/`、`tasks/active/*/brief.md`
2. 按 `references/promotion-rules.md` 筛出候选内容
3. 判断候选内容的全局落点：
   - 当前仍有效的跨项目状态 -> `{GLOBAL_MEMORY_ROOT}/current.md`
   - 长期稳定规则 -> `{GLOBAL_MEMORY_ROOT}/spec/*.md`
   - 持续推进的跨项目主题 -> `{GLOBAL_MEMORY_ROOT}/topics/active/<topic>/`
4. 更新 `{GLOBAL_MEMORY_ROOT}/projects/index.md`
5. 必要时回写当前项目 `current.md` 的 `关联全局主题`
6. 运行 `python3 scripts/validate_global_memory.py --project-root <project-root>`
7. 报告本次提升了什么、拒绝了什么、为什么拒绝

## 必须拒绝

- 单个项目当天的进度和流水
- 项目专属文件路径、分支名、临时目录
- 未确认的猜测和试探性判断
- 只在一个项目里有效的局部约束
- 含敏感信息但没有明确说明可共享的内容

## 校验

- 全局目录和核心文件必须存在
- `current.md` 必须保留固定栏目
- `projects/index.md` 必须能找到当前项目路径
- 项目关联的全局主题必须真实存在
- 全局 `spec/` 与 `current.md` 不得误混入当前项目绝对路径

## 汇报

- 更新了哪些全局文件
- 新增或更新了哪些项目 <-> 主题关联
- 哪些候选内容被拒绝，以及拒绝原因
- 校验结果
