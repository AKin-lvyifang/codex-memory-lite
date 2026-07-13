# 安装与配置

[English](install.md)

这份说明用于把 Codex Memory Lite V2 安装到支持 Hook 的 ChatGPT / Codex 环境，并验证它是否真实运行。安装、更新和卸载都不会删除项目记忆。

## 环境要求

- macOS 或 Linux
- Node.js 18 或更高版本，包含 `npx`
- Python 3
- Git
- 终端可以执行 Codex CLI
- 当前 ChatGPT / Codex 版本支持 command Hook

先检查主要环境：

```bash
node --version
python3 --version
git --version
codex --version
```

## 一键安装

```bash
npx --yes --package=https://github.com/AKin-lvyifang/codex-memory-lite/releases/latest/download/codex-memory-lite.tgz codex-memory-lite install
```

这条命令会跟随 GitHub 最新稳定 Release，不需要克隆仓库历史。如果你更在意结果可复现，可以锁定版本：

```bash
npx --yes --package=https://github.com/AKin-lvyifang/codex-memory-lite/releases/download/v2.0.0/codex-memory-lite-2.0.0.tgz codex-memory-lite install
```

也可以使用 `curl`：

```bash
curl -fsSL https://raw.githubusercontent.com/AKin-lvyifang/codex-memory-lite/main/scripts/install.sh | sh
```

这个脚本最终调用的是同一个 `npx` 安装器。如果你的安全规范不允许直接执行远程脚本，可以先查看 [scripts/install.sh](../scripts/install.sh)。

## 让 Agent 帮你安装

把下面这句话发给能够操作本机的 Agent：

> 请从 https://github.com/AKin-lvyifang/codex-memory-lite 安装最新版 Codex Memory Lite；使用仓库的一键安装器，保留我已有的 Hook、MCP、Skill 和配置，安装后运行 doctor，并告诉我是否需要重启 ChatGPT。

Agent 最后应该告诉你：安装到了哪个 Codex 主目录、备份在哪里、doctor 是否通过、是否需要重启或新建 task。

## 安装器会改什么

默认目标目录是 `${CODEX_HOME:-$HOME/.codex}`。

| 路径 | 动作 |
| --- | --- |
| `skills/codex-memory/` | 备份后安装或替换 V2 Skill |
| `ai/hooks/codex-memory-bootstrap-first-prompt.js` | 安装项目自动初始化 Hook |
| `hooks.json` | 合并 8 个 V2 Hook，保留其他 Hook 和顶层信息 |
| `config.toml` | 启用 `[features].hooks`，写入 V2 Hook 信任哈希 |
| `memory-v2/config.json` | 保留已有值，只补齐缺失的 V2 默认项 |
| `backups/codex-memory-lite/<时间戳>/` | 修改前备份所有受影响文件 |

安装器不会重写 MCP、其他 Skill、项目 `AGENTS.md` 或任何项目的 `.codex-memory/`。

## 自定义 Codex 主目录

两种写法都可以：

```bash
npx --yes --package=https://github.com/AKin-lvyifang/codex-memory-lite/releases/latest/download/codex-memory-lite.tgz codex-memory-lite install --codex-home "/custom/codex-home"
```

```bash
CODEX_HOME="/custom/codex-home" \
  npx --yes --package=https://github.com/AKin-lvyifang/codex-memory-lite/releases/latest/download/codex-memory-lite.tgz codex-memory-lite install
```

后续启动 ChatGPT / Codex 时也要使用同一个 `CODEX_HOME`，否则应用读取的是另一套 Hook 配置。

## 激活与验收

1. 新建一个 task，或重启 ChatGPT / Codex。
2. 进入一个项目，正常发送第一条消息。
3. 执行 doctor：

```bash
npx --yes --package=https://github.com/AKin-lvyifang/codex-memory-lite/releases/latest/download/codex-memory-lite.tgz codex-memory-lite doctor
```

doctor 通过代表 Skill 文件、8 个 Hook、信任哈希、Hook 开关、配置和全项目台账命令都正常。项目本身要等第一次 Prompt 才会注册。

## 配置文件

V2 配置位于 `${CODEX_HOME:-$HOME/.codex}/memory-v2/config.json`。

| 配置项 | 默认值 | 作用 |
| --- | --- | --- |
| `enabled` | `true` | V2 总开关 |
| `project_roots` | `[]` | 首轮 Hook 自动登记的项目 |
| `excluded_project_roots` | `[]` | 明确不启用 V2 的项目绝对路径 |
| `curator.preferred_model` | `gpt-5.6-sol` | 只读记忆整理员优先使用的模型 |
| `curator.reasoning_effort` | `low` | 优先保证判断速度 |
| `curator.fallback_model_policy` | `inherit` | 优先模型不可用时，继承当前 task 模型 |
| `sync.active_task_event_threshold` | `12` | 活跃任务积压多少事件后触发整理 |
| `sync.max_pending_age_seconds` | `1800` | 活跃任务最长积压时间 |
| `storage.runtime_soft_limit_mb` | `20` | 临时运行数据软上限 |
| `storage.project_soft_limit_mb` | `50` | 单项目记忆总量软上限 |

如果某个项目暂时不想启用 V2，把它的完整绝对路径加入 `excluded_project_roots`。不要为了停用自动化而删除记忆。

## 更新

```bash
npx --yes --package=https://github.com/AKin-lvyifang/codex-memory-lite/releases/latest/download/codex-memory-lite.tgz codex-memory-lite update
```

更新仍然会先备份再合并。你自己改过的配置值优先，只补缺失的默认项。

## 卸载

```bash
npx --yes --package=https://github.com/AKin-lvyifang/codex-memory-lite/releases/latest/download/codex-memory-lite.tgz codex-memory-lite uninstall
```

默认卸载会移除本产品管理的 Skill、启动脚本、Hook 和信任记录，但保留 V2 配置和所有项目记忆。

如果连 V2 配置也要移除：

```bash
npx --yes --package=https://github.com/AKin-lvyifang/codex-memory-lite/releases/latest/download/codex-memory-lite.tgz codex-memory-lite uninstall --purge-config
```

即使使用 `--purge-config`，项目 `.codex-memory/` 仍然不会被删除。

## 预演与 JSON 输出

```bash
npx --yes --package=https://github.com/AKin-lvyifang/codex-memory-lite/releases/latest/download/codex-memory-lite.tgz codex-memory-lite install --dry-run
npx --yes --package=https://github.com/AKin-lvyifang/codex-memory-lite/releases/latest/download/codex-memory-lite.tgz codex-memory-lite doctor --json
```

Agent 自动化或脚本检查时，建议使用 `--json`。

## 常见问题

### 提示 `codex is not available in PATH`

安装或更新 Codex CLI，并确认同一个终端能执行 `codex --version`。缺少 CLI 时可以复制文件，但 Curator 无法运行。

### Hook 已安装，但没有登记项目

新建 task 或重启应用，进入项目后发送一条消息。自动初始化发生在项目首轮 Prompt，不发生在安装阶段。

### 还能看到旧的 V1 Skill

安装器会故意保留旧 Skill。请先确认 V2 健康，再按 [V1 迁移指南](migration-v1.zh-CN.md) 退出旧路由。

### doctor 提示 Hook 不可信或已修改

先运行 `update` 重新生成 Hook 和信任哈希。如果仍然失败，查看最新备份，并检查是否有其他工具持续重写 `hooks.json` 或 `config.toml`。
