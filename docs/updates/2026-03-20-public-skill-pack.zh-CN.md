# 公开技能包更新说明

日期：2026-03-20

## 概述

这次更新把公开版技能包整理成了一个对外可分享、对中英文用户都更容易安装的版本。

## 本次更新了什么

- 新增双语公开结构：
  - `skills/` 作为英文可安装包
  - `skills.zh-CN/` 作为简体中文可安装包
- 公开包从 3 个核心项目记忆 skill 扩展为 4 个 skill：
  - `codex-memory-bootstrap`
  - `codex-memory-task-init`
  - `codex-memory-sync`
  - `codex-memory-promote-global`，作为可选的跨项目 skill
- 去掉了公开副本里写死的个人绝对路径、用户名和本机目录示例
- 调整了全局记忆校验脚本，让默认路径从 `${CODEX_HOME}` 或 `${HOME}` 推导，不再绑定个人机器路径
- 新增 `scripts/install-skill-pack.sh`，支持按语言一键安装
- 更新了 README 和安装文档，明确说明：
  - 如何选择英文包或简体中文包
  - 哪 3 个 skill 属于核心 skill
  - 什么时候需要额外安装可选的全局提升 skill

## 范围说明

- 公开包尽量保持原 skill 的意图不变
- 这次真正改动的重点只有三类：
  - 隐私安全的路径占位符
  - 中英双语分包
  - 一键安装入口

## 安装示例

英文包：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/AKin-lvyifang/codex-memory-lite/main/scripts/install-skill-pack.sh) en
```

简体中文包：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/AKin-lvyifang/codex-memory-lite/main/scripts/install-skill-pack.sh) zh-CN
```
