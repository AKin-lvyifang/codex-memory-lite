# Codex Memory Lite

[English](README.md) | [简体中文](README.zh-CN.md)

让 Codex 在长项目里不那么容易“失忆”。

这个项目的做法不是继续把所有信息都塞在聊天记录里，而是在每个项目内部放一层轻量、结构化的记忆文件，让 Codex 需要时按顺序读取。

这个包主要适合：

- 长周期项目里的长记忆
- 同一个项目里跨线程、跨会话续跑
- 通过“只读必要入口文件”来减少 token 消耗
- 在不同项目之间复用同一套规则、skills 和模板

## 它解决什么问题

当一个会话越来越长时，通常会同时出现这 3 个问题：

1. 聊天上下文越来越大。
2. 自动压缩会丢掉有用信息。
3. 单个 `codex-handoff.md` 会越写越大，当前状态、长期规范、任务细节、旧历史全混在一起。

这个 starter 的核心思路，就是把记忆拆成 4 层：

- `current.md`
  - 只放当前真正生效的状态
- `spec/`
  - 放跨会话仍然稳定有效的规则
- `tasks/`
  - 每个长期任务单独建文件夹
- `archive/`
  - 放历史记录，便于回查，但不默认污染当前上下文

## 核心原理

不要把所有内容都堆在一个交接文件里。

而是改成：

- 当前工作写进 `current.md`
- 长期规则写进 `spec/`
- 每个大任务单独建任务文件夹
- 旧进度和旧历史移到 `archive/`

这样，原本“只存在聊天里的记忆”，就会变成“属于项目本身的记忆”。

## 仓库里有什么

- `snippets/`
  - 根级和项目级 `AGENTS.md` 片段，用来让 Codex 知道什么时候启用这套结构化记忆
- `skills/`
  - 3 个辅助 skills，分别负责初始化、建任务、同步记忆
- `templates/`
  - 这一整套记忆文件的标准模板
- `examples/demo-project/`
  - 一个已经完成迁移的示例项目
- `docs/`
  - 更详细的说明、安装步骤和迁移规则

## 5 分钟安装

如果你要把这套东西真正装进 Codex，用起来其实就 4 步：

1. 更新你的根级 `AGENTS.md`
2. 更新每个项目里的 `AGENTS.md`
3. 安装这 3 个 skills
4. 保证模板和 skills 放在一起

详细安装看：

- [docs/install.md](docs/install.md)

### 第 1 步：更新根级 `AGENTS.md`

把下面这个片段加进你的根级规则里：

- [snippets/GLOBAL-AGENTS-SNIPPET.md](snippets/GLOBAL-AGENTS-SNIPPET.md)

这一层是“触发层”。

它会告诉 Codex：

- 什么情况下应该切换到结构化记忆
- 什么时候创建 `.codex-memory/`
- 什么时候初始化任务文件夹
- 什么时候把最新进展同步回记忆文件

### 第 2 步：更新项目级 `AGENTS.md`

把下面这个片段加进项目里的 `AGENTS.md`：

- [snippets/PROJECT-AGENTS-SNIPPET.md](snippets/PROJECT-AGENTS-SNIPPET.md)

这一层是“项目读取层”。

它会告诉 Codex：

- 新线程进项目后先读什么
- 哪些信息该进 `current / spec / tasks / archive`
- 什么时候要更新 `current.md`

### 第 3 步：安装这 3 个 skills

把这 3 个文件夹复制到你的 Codex skills 目录里：

- `skills/codex-memory-bootstrap/`
- `skills/codex-memory-task-init/`
- `skills/codex-memory-sync/`

关键点有两个：

- 不是只复制 `SKILL.md`
- 每个 skill 自己的 `templates/` 必须跟着一起放

只有这样，后面自动生成出来的记忆文件才会稳定，不会越跑越歪。

### 第 4 步：开始使用

第一次使用通常是这样：

1. 打开一个长期项目
2. 确保项目级 `AGENTS.md` 已经放好
3. 运行 `codex-memory-bootstrap`
4. 遇到新的大任务时，运行 `codex-memory-task-init`
5. 阶段切换或准备结束线程时，运行 `codex-memory-sync`

## 这 3 个 skills 分别做什么

### `codex-memory-bootstrap`

适合在项目开始变长、信息变杂、明显会跨会话时使用。

它会：

- 创建 `.codex-memory/`
- 按模板写入标准文件
- 自动写入或更新项目级 `AGENTS.md` 里的记忆规则块
- 读取旧的 `codex-handoff.md`，把关键信息迁移进新结构
- 把旧 handoff 冻结保留，而不是直接删掉

### `codex-memory-task-init`

适合在出现一个新的长期任务时使用。

它会创建：

- `brief.md`
- `decisions.md`
- `refs.md`

### `codex-memory-sync`

适合在项目阶段变化、上下文变大、或者你准备结束一个长线程时使用。

它会把下面这些内容同步到最新状态：

- `current.md`
- 活跃任务文件
- archive 记录

## 根规则和项目规则怎么配合

### 根级规则

根级 `AGENTS.md` 决定：

什么时候应该启用结构化记忆。

常见触发条件：

- 工作会跨多个会话继续
- 涉及多个文件或多个话题
- 交接信息已经开始堆积
- 上下文明显在膨胀

### 项目级规则

项目级 `AGENTS.md` 决定：

进入这个项目后，Codex 应该先读哪些记忆文件。

推荐读取顺序：

1. `.codex-memory/current.md`
2. `.codex-memory/spec/index.md`
3. 如果有活跃任务，再读 `.codex-memory/tasks/index.md` 和对应任务的 `brief.md`

## 推荐目录结构

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

## 日常怎么用

### 启动一个长期项目

1. 先把根级 `AGENTS.md` 片段加进去。
2. 确保 3 个 skills 在你的技能目录里。
3. 当项目达到触发条件时，运行 `codex-memory-bootstrap`。

### 启动一个新任务

运行 `codex-memory-task-init`。

### 结束一个阶段或长线程

运行 `codex-memory-sync`。

## 这里说的“跨项目”到底是什么意思

这点必须讲清楚，不然很容易被误解。

这套方案最擅长的是：

- 同一个项目里的跨线程续跑
- 同一个项目里的跨会话续跑

所谓“跨项目复用”，真正复用的是：

- 同一套触发规则
- 同一套项目记忆结构
- 同一套 3 个 skills
- 同一套模板

也就是说：

它复用的是“记忆机制”，不是让不同项目自动共享全部业务上下文。

## 从单个 handoff 文件迁移过来

推荐的迁移路由是：

- 当前仍然生效的信息 -> `current.md`
- 重复出现、长期有效的规则 -> `spec/`
- 仍在推进中的长期任务 -> `tasks/active/<task>/`
- 已经过时但需要留档的历史 -> `archive/`

旧的 `codex-handoff.md` 会保留为冻结参考，但不再作为主入口。

具体路由规则可以看：

- [docs/migration-guide.md](docs/migration-guide.md)

## 示例

可以直接看：

- [examples/demo-project](examples/demo-project)

这个示例里包含：

- 一个项目级 `AGENTS.md`
- 一个冻结保留的旧 `codex-handoff.md`
- 一套已经运行起来的 `.codex-memory/`
- 一个带 `brief / decisions / refs` 的示例任务

## 截图

- [Storyboard Preview](docs/screenshots/codex-memory-story-preview.png)
- [Slide 01](docs/screenshots/codex-memory-story-01.png)
- [Slide 02](docs/screenshots/codex-memory-story-02.png)
- [Slide 03](docs/screenshots/codex-memory-story-03.png)
- [Slide 04](docs/screenshots/codex-memory-story-04.png)
- [Slide 05](docs/screenshots/codex-memory-story-05.png)
- [Slide 06](docs/screenshots/codex-memory-story-06.png)
- [Slide 07](docs/screenshots/codex-memory-story-07.png)
- [Slide 08](docs/screenshots/codex-memory-story-08.png)

## 常见问题

### 这是不是在替代 Codex 自己的上下文

不是。

它是在减轻聊天上下文的压力，把长期信息搬到项目文件里。

### 这会不会让项目更复杂

初始化时会多一点结构，但长期来看，反而更容易续跑和接手。

### 每个小问题都要用它吗

不用。

它适合的是长任务、多文件、多话题、跨会话的工作，不适合一次性小问题。

### archive 要不要默认读取

不要。

archive 是拿来追历史的，不应该变成默认启动上下文。

## 对外分享前的检查清单

在你发布自己的版本前，最好先检查：

- 去掉私人绝对路径
- 去掉私人业务名、节点号、账号信息
- 根规则里只保留跟记忆系统有关的部分
- 示例文件确认已经脱敏

## License

这个 starter 默认使用 MIT 协议。

如果你的场景有别的要求，可以自行替换。
