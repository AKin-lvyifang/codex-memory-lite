<a href="https://github.com/AKin-lvyifang/codex-memory-lite">
  <img width="1280" alt="Codex Memory Lite v2.0.0，面向 Codex 的自动项目记忆。" src="https://raw.githubusercontent.com/AKin-lvyifang/codex-memory-lite/v2.0.0/docs/images/codex-memory-lite-v2.0.0.png">
</a>

<p align="center">
  <a href="#安装">安装</a> ·
  <a href="#工作原理">工作原理</a> ·
  <a href="#常用命令">常用命令</a> ·
  <a href="docs/install.zh-CN.md">完整文档</a> ·
  <a href="README.md">English</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-v2.0.0-167D73?style=flat-square" alt="版本 v2.0.0">
  <img src="https://img.shields.io/badge/runtime-Node.js_18%2B-2F6F4E?style=flat-square" alt="Node.js 18 或更高版本">
  <img src="https://img.shields.io/badge/platform-ChatGPT_%2F_Codex-1F2937?style=flat-square" alt="ChatGPT 和 Codex">
  <img src="https://img.shields.io/badge/license-MIT-D97706?style=flat-square" alt="MIT License">
</p>

# Codex Memory Lite

一套面向长期项目的自动记忆系统。它把真正影响后续工作的进度、决定和约束写进项目的 `.codex-memory/`，不会把每轮聊天都堆成长日志。

<a id="安装"></a>
## 安装

```bash
npx --yes --package=https://github.com/AKin-lvyifang/codex-memory-lite/releases/latest/download/codex-memory-lite.tgz codex-memory-lite install
```

安装后新建一个 task，或重启 ChatGPT / Codex。第一次在项目里发送消息时，记忆会自动初始化。

**不想自己执行命令？把这句话发给 Agent：**

> 请从 https://github.com/AKin-lvyifang/codex-memory-lite 安装最新版 Codex Memory Lite；使用仓库的一键安装器，保留我已有的 Hook、MCP、Skill 和配置，安装后运行 doctor，并告诉我是否需要重启 ChatGPT。

也可以使用 `curl`：

```bash
curl -fsSL https://raw.githubusercontent.com/AKin-lvyifang/codex-memory-lite/main/scripts/install.sh | sh
```

安装器会先备份受影响文件，再把自己的 8 个 Hook 合并进现有配置。其他 Hook、MCP、Skill 和项目记忆都会保留。

## V2 解决了什么

- **自动初始化**：首轮 Hook 自动识别项目并创建或迁移 `.codex-memory/`，不再占用项目 `AGENTS.md`。
- **有价值才整理**：Hook 会观察关键生命周期，但只有出现长期信号、文件变化、压缩检查点或积压阈值时，才启动记忆整理员。
- **判断和写入分离**：只读 Curator 负责判断 `write / skip / unresolved`，确定性脚本负责校验和落盘。
- **写坏可恢复**：通过校验和、事务、版本号和原子写入，避免半写入和静默覆盖。
- **空间有边界**：临时运行数据在完成处置后可清理；已经确认的长期记忆不会被自动删除。

<a id="工作原理"></a>
## 工作原理

```text
Codex 生命周期事件
        ↓
Hook 记录一条经过脱敏的小事件
        ↓
触发门判断是否值得整理
        ↓
只读 Curator 判断哪些信息值得长期保存
        ↓
memoryctl 校验覆盖率、路径和版本
        ↓
原子更新 .codex-memory/
```

默认 Curator 使用 `gpt-5.6-sol` 和低推理强度。如果该模型不可用，V2 可以继承当前 task 的模型，并在诊断信息里记录回退结果。

只有真实写入时才会显示一行提示，例如 `已记录：任务进度`；没有长期价值时保持安静。

完整机制见 [V2 如何工作](docs/how-it-works.zh-CN.md)。

## 日常使用

1. 打开 Git 项目，或包含常见项目标记的文件夹。
2. 继续做真实任务，不需要手动初始化或同步记忆。
3. 想看进度、决定或历史时，直接让 Codex 查看项目记忆。
4. 如果 Hook 没有运行或同步报错，再执行 `doctor`。

V2 使用以下结构：

```text
.codex-memory/
├── current.md            # 当前有效状态
├── spec/                 # 稳定项目规则
├── tasks/                # 活跃任务和已归档任务
├── archive/              # 历史记忆
├── manifest.json         # 结构和版本信息
└── .runtime/             # 待处理事件与可恢复事务
```

<a id="常用命令"></a>
## 常用命令

```bash
# 更新，不覆盖其他配置
npx --yes --package=https://github.com/AKin-lvyifang/codex-memory-lite/releases/latest/download/codex-memory-lite.tgz codex-memory-lite update

# 检查 Skill、Hook、信任状态、配置和项目运行台账
npx --yes --package=https://github.com/AKin-lvyifang/codex-memory-lite/releases/latest/download/codex-memory-lite.tgz codex-memory-lite doctor

# 卸载运行组件，默认保留 V2 配置和所有项目记忆
npx --yes --package=https://github.com/AKin-lvyifang/codex-memory-lite/releases/latest/download/codex-memory-lite.tgz codex-memory-lite uninstall
```

如果 Codex 主目录不是默认的 `~/.codex`，可使用 `--codex-home PATH` 或设置 `CODEX_HOME=/path`。版本锁定、备份位置和完整参数见 [安装与配置](docs/install.zh-CN.md)。

## 安全边界

- 安装和卸载都不会删除任何项目的 `.codex-memory/`。
- 修改前会备份已有 `hooks.json`、`config.toml`、V2 配置和已安装的 `codex-memory` Skill。
- 安装器只管理 1 个 Skill、1 个启动 Hook 脚本和 8 个命令 Hook，不会重写 MCP 配置或项目 `AGENTS.md`。
- Curator 输入可能包含当前 Prompt、精简后的工具影响、最终回答、工作区变化和相关记忆文件。常见密钥格式会先脱敏，但仍不建议把秘密写进 Prompt 或记忆。
- V1 Skill 和旧 `AGENTS.md` 记忆区块会被保留，不会偷偷删除。请按 [V1 迁移指南](docs/migration-v1.zh-CN.md) 主动退出旧流程。

## 文档

- [安装与配置](docs/install.zh-CN.md)
- [V2 如何工作](docs/how-it-works.zh-CN.md)
- [从 V1 迁移](docs/migration-v1.zh-CN.md)
- [English installation guide](docs/install.md)

## 本地开发

```bash
npm test
npm run package:release
npm run verify:release
```

`verify:release` 会检查压缩包内容和 SHA256，再在隔离目录里真实执行安装、诊断和卸载。

## 许可证

Codex Memory Lite 使用 [MIT License](LICENSE) 开源。
