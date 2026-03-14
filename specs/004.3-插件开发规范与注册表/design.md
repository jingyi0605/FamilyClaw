# 设计文档 - 插件开发规范与注册表

状态：Draft

## 1. 概述

### 1.1 目标

- 给第三方开发者一套能照着做的插件开发规则
- 给插件市场一套稳定的注册表 schema
- 给官方维护者一套可执行的审核和提交流程

### 1.2 覆盖需求

- `requirements.md` 需求 1
- `requirements.md` 需求 2
- `requirements.md` 需求 3
- `requirements.md` 需求 4

### 1.3 技术约束

- 后端：现有插件系统以 Python 模块和 `manifest.json` 为基础
- 前端：后续插件市场和插件管理页都需要复用同一注册表结构
- 数据存储：第一版注册表以 Git 仓库中的静态文件为主，不引入新数据库
- 认证授权：GitHub PR 流程由仓库维护者控制，不在系统内自建提交流程
- 外部依赖：GitHub 仓库、第三方源码仓库地址、文档地址

## 2. 架构

### 2.1 系统结构

这份 Spec 的主线仍然是“开发规范层”和“注册表分发层”。

但基于当前开发者文档调整，这里补一个最小运行方向约束：

- 内置插件：继续复用 `004.2` 已完成的同进程执行底座
- 第三方插件：后续实现优先走“同容器子进程 runner”

这里不是要在 `004.3` 里直接落代码实现，而是先把第三方插件推荐运行模式定清楚，避免文档继续把第三方开发者往主进程里引。

可以把它看成两层：

1. **开发规范层**
   - 告诉开发者插件该怎么写
   - 包括目录结构、manifest、入口、返回格式、测试要求
2. **注册表层**
   - 告诉市场和维护者插件该怎么被识别
   - 包括注册项 schema、来源字段、仓库地址、审核要求

补一层运行时边界理解：

3. **第三方 runner 约束层**
   - 告诉维护者第三方插件后续该怎么跑，才能不污染主 API 进程
   - 第一版先约束运行边界、目录约定、协议输入输出、错误处理和不做项

### 2.2 模块职责

| 模块 | 职责 | 输入 | 输出 |
| --- | --- | --- | --- |
| 开发规范文档 | 说明插件开发规则 | 现有插件系统能力边界 | 开发者可执行规范 |
| manifest 规范 | 约束插件声明格式 | 插件元数据 | 统一字段规则 |
| 注册表 schema | 约束市场识别格式 | 注册表条目 | 插件索引数据 |
| PR 提交流程 | 约束插件注册进入方式 | 第三方提交内容 | 可审核 PR |
| 来源机制 | 区分官方和第三方注册表 | 注册表地址、来源声明 | 来源标识与风险提示 |
| 第三方 runner 约束 | 约束第三方插件最小执行方式 | 插件目录、依赖、payload | 可隔离的执行边界 |

### 2.3 关键流程

#### 2.3.1 第三方开发插件流程

1. 开发者阅读插件开发规范和样板。
2. 开发者按目录结构创建插件并编写 `manifest.json`。
3. 开发者在插件自己的 venv 里安装依赖，并按 runner 约定自检入口。
4. 开发者按测试与验收规范完成最小验证。
5. 开发者把插件仓库和注册元数据准备好，等待提交注册表 PR。

#### 2.3.2 插件注册进入市场流程

1. 第三方 fork 或提交 PR 到注册表仓库。
2. PR 提交插件注册项，包括元数据、仓库地址、文档地址和来源信息。
3. 官方按审核清单检查字段、仓库可访问性、风险声明和文档完整度。
4. 合并后，该插件开始能被插件市场读取和展示。

#### 2.3.3 第三方插件运行接入流程（最小版）

这条流程不是当前代码已实现流程，而是后续实现必须对齐的最小方向。

1. 主服务从注册表读取第三方插件条目，拿到仓库地址、manifest、来源和运行摘要。
2. 运维或维护者把插件代码放到第三方插件目录，并准备插件自己的 venv、`python_path`、`working_dir`。
3. 调用方先创建 `plugin_job`，而不是直接同步拉起第三方插件。
4. worker 领取任务后，根据插件来源和执行后端决定走 `subprocess_runner`。
5. runner 在子进程里加载 `manifest.entrypoints` 指向的函数，传入 `payload`。
6. runner 把插件返回值转成 JSON 结果，回给主服务。
7. 主服务继续复用现有原始记录保存、记忆写入、权限校验、审计记录这些底座，并把结果收口到任务状态、尝试记录和通知记录。

这条流程故意收得很小：

- 不做自动下载源码
- 不做自动创建 venv
- 不做自动安装依赖
- 不做跨容器编排
- 不做沙箱执行

这里还要明确区分两件事：

- 安装：准备插件目录、venv、`requirements.txt` 依赖、解释器路径
- 执行：worker 真正调用 runner 跑入口函数

第一版只把这两件事的边界写清楚，不做自动化平台。

## 3. 组件和接口

### 3.1 核心组件

覆盖需求：1、2、3、4

- `插件开发指南`：写清楚怎么开发插件
- `manifest 规范`：写清楚每个字段是什么、必不必填、怎么校验
- `注册表 schema`：写清楚市场识别什么字段
- `审核清单`：写清楚 PR 审核时检查什么

### 3.2 数据结构

覆盖需求：1、2、4

#### 3.2.1 `manifest.json`

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | 插件唯一标识 | 小写英文、数字、中划线 |
| `name` | string | 是 | 插件展示名称 | 人能看懂 |
| `version` | string | 是 | 插件版本 | 推荐 semver |
| `types` | string[] | 是 | 插件支持的能力类型 | 仅允许现有系统支持类型 |
| `permissions` | string[] | 是 | 插件声明的权限 | 与能力类型匹配 |
| `risk_level` | string | 是 | 风险等级 | `low` / `medium` / `high` |
| `triggers` | string[] | 是 | 插件支持的触发方式 | 第一版以手动或受控触发为主 |
| `entrypoints` | object | 是 | 各类型对应入口 | 入口必须可定位 |
| `description` | string | 否 | 插件用途说明 | 推荐填写 |
| `vendor` | object | 否 | 插件维护者信息 | 推荐填写 |

第一版先按现有后端实现收口，规则不要写虚的：

- 必填字段最小集合是：`id`、`name`、`version`、`types`、`permissions`、`risk_level`、`triggers`、`entrypoints`
- 当前运行时真实支持的类型只有 4 个：`connector`、`memory-ingestor`、`action`、`agent-skill`
- `id` 必须和代码仓库、注册表里的 `plugin_id` 保持稳定一致，不能今天一个名字、明天一个名字
- `permissions` 和 `triggers` 允许为空数组，但不能有空字符串，也不能有重复值
- `entrypoints` 必须是“Python 模块路径 + 函数名”格式，比如 `app.plugins.builtin.health_basic.connector.sync`
- `entrypoints` 的 key 对外允许写成连字符或下划线，运行时会统一归一成下划线；但文档里推荐统一写成下划线，减少歧义
- 你声明了什么 `types`，`entrypoints` 就必须提供对应入口；少一个都不算合法插件

建议把字段再拆开理解：

| 字段 | 细化说明 | 为什么这样定 |
| --- | --- | --- |
| `id` | 全局稳定 id，建议直接用于目录名、仓库名和注册表索引名 | 避免一个插件在不同地方出现多个身份 |
| `name` | 给人看的展示名 | 市场、后台、日志都要看得懂 |
| `version` | 推荐 semver，例如 `0.1.0` | 后续排错、升级、审核都要用 |
| `types` | 一个插件可以声明多个类型，但必须真有对应入口 | 现在仓库已经支持多能力插件 |
| `permissions` | 只声明当前插件运行需要的最小权限 | 避免插件一上来就要一堆大权限 |
| `risk_level` | 只允许 `low`、`medium`、`high` | 现有权限和人工确认逻辑已经按这三档工作 |
| `triggers` | 第一版推荐 `manual`、`schedule`、`agent` 这类可控触发 | 先把触发面收窄，别引入不可控自动执行 |
| `entrypoints` | 每个能力类型都要能定位到真实函数 | 运行时最终就是按这里 import 并调用 |
| `description` | 推荐写一段人能看懂的话 | 方便审核和市场展示，不要求运行时依赖 |
| `vendor` | 推荐写维护者名字、组织名、联系方式 | 方便追责、沟通和后续下架处理 |

#### 3.2.1.1 插件目录结构约定

当前这里也要分成两类看：

- 内置插件目录：继续贴近现有仓库代码
- 第三方插件目录：按 runner 最小运行形态约束

内置插件目录仍然保持现状，不在 `004.3` 里重写。

第三方插件第一版最小目录建议如下：

```text
<plugin_repo>/
  manifest.json
  requirements.txt
  README.md
  plugin/
    __init__.py
    connector.py          # 可选，声明 connector 时需要
    ingestor.py           # 可选，声明 memory-ingestor 时需要
    executor.py           # 可选，声明 action 时需要
    skill.py              # 可选，声明 agent-skill 时需要
  tests/                  # 推荐，放最小自测
```

如果要对照当前仓库里的内置插件样例，也可以理解成：

- 内置插件样例用于看能力和返回结构
- 第三方插件目录规范用于看 runner 接入形态

这里有 3 个硬规则：

1. 一插件一目录，不要多个插件共用一个 `manifest.json`
2. `manifest.json` 必须放在插件目录根下，不能藏在子目录里
3. 入口代码文件名可以不是上面这几个，但 `entrypoints` 必须能指向真实可 import 的模块函数

第三方 runner 形态再补 3 条约束：

4. 第三方插件依赖必须写在自己的 `requirements.txt` 里，不默认进入主 API 环境
5. 第三方代码建议全部放进 `plugin/` 包目录，避免仓库根目录变成杂物堆
6. 第三方入口路径推荐写成 `plugin.connector.sync` 这类相对稳定形式，不要把主项目模块路径写死到第三方插件里

#### 3.2.1.2 类型和入口对照

| 插件类型 | 推荐模块文件 | 推荐函数名 | 现有用途 |
| --- | --- | --- | --- |
| `connector` | `connector.py` | `sync` | 从外部系统读原始数据 |
| `memory-ingestor` | `ingestor.py` | `transform` | 把原始记录转成标准记忆 |
| `action` | `executor.py` | `run` | 执行外部动作 |
| `agent-skill` | `skill.py` | `run` | 给 Agent 暴露受控能力 |

这些文件名和函数名是推荐，不是死规定；但如果你偏离这个习惯，必须保证：

- `entrypoints` 仍然清楚
- 审核的人不用翻半天才能知道入口在哪
- 不会破坏现有运行时 import 方式

#### 3.2.1.3 第三方 runner 最小运行约定

这部分只约束最小运行方式，不引入复杂平台能力。

| 项目 | 最小要求 | 为什么这样定 |
| --- | --- | --- |
| 运行位置 | 和主 API 服务在同一个容器里 | 运维成本最低，先不引入多容器编排 |
| 执行方式 | 主服务拉起子进程 runner | 避免第三方代码直接进主进程 |
| Python 环境 | 每个插件使用自己的 venv | 避免依赖污染主 API 环境 |
| 输入方式 | 主服务传 JSON `payload` | 贴近现有执行入口，改动最小 |
| 输出方式 | runner 返回 JSON 结果 | 现有原始记录、记忆、审计都能继续复用 |
| 进程通信 | 第一版优先 `stdin/stdout` | 最笨但最容易落地和调试 |
| 安装方式 | 人工准备插件目录和 venv | 明确不做自动下载安装 |
| 对外语义 | 主服务先创建后台任务 | 避免长插件执行直接拖住 HTTP 接口 |
| 状态回写 | 结果必须落回任务状态和尝试记录 | 失败、超时、重试要有正式留痕 |

第一版 runner 明确不做这些事：

- 不做自动 `git clone`
- 不做自动 `pip install`
- 不做系统级依赖安装
- 不做网络沙箱
- 不做插件热更新编排

再补 4 条死规矩：

1. 第三方插件依赖只放在插件自己的环境里解析，不要求装进主 API 环境。
2. `python_path`、`working_dir`、插件目录必须能让 runner 稳定定位入口模块。
3. worker 只关心任务推进和结果收口，不负责现场替你装依赖。
4. runner 执行失败、超时、非法 JSON、缺依赖，都要转成结构化错误回写任务。

#### 3.2.2 `registry-plugin.json`

第一版注册表条目先收成“一个插件一个 JSON 文件”，不要一上来搞复杂聚合格式。

建议目录：

```text
registry/
  plugins/
    <plugin_id>.json
```

这样做有两个现实好处：

1. 单个插件的改动范围清楚，PR review 简单
2. 后端后续做解析时，可以直接按文件遍历，不需要先拆大 JSON

字段定义如下：

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `schema_version` | string | 是 | 注册表条目 schema 版本 | 第一版固定为 `1.0` |
| `plugin_id` | string | 是 | 对应插件 id | 必须和 manifest `id` 一致 |
| `display_name` | string | 是 | 市场展示名称 | 去空格后不能为空 |
| `summary` | string | 是 | 一句话介绍 | 去空格后不能为空，不写空话 |
| `source_type` | string | 是 | 来源类型 | `builtin` / `official` / `third_party` |
| `registry_slug` | string | 是 | 注册表来源标识 | 同一注册表内稳定，建议小写中划线 |
| `plugin_repo_url` | string | 是 | 插件源码仓库地址 | 必须是可访问的 `https` 地址 |
| `manifest_url` | string | 否 | manifest 原始地址 | 推荐提供，指向仓库内原始文件 |
| `docs_url` | string | 否 | 插件说明文档地址 | 推荐提供 |
| `homepage_url` | string | 否 | 插件主页 | 可选 |
| `maintainers` | array | 是 | 维护者列表 | 至少 1 个维护者，便于联系和追踪 |
| `categories` | string[] | 否 | 分类标签 | 允许空数组，不允许重复值 |
| `capabilities` | string[] | 否 | 对外展示能力摘要 | 允许空数组，不允许重复值 |
| `runtime` | object | 是 | 运行时声明摘要 | 至少包含 `types`、`risk_level`、`permissions` |
| `status` | string | 是 | 注册状态 | `active` / `deprecated` / `hidden` |
| `source` | object | 是 | 来源追踪信息 | 至少包含 `repo_owner`、`repo_name`、`submitted_via` |
| `verification` | object | 否 | 审核补充信息 | 可记录测试说明、兼容版本、备注 |

推荐把容易混掉的字段拆开看：

| 字段 | 细化要求 | 为什么这样定 |
| --- | --- | --- |
| `schema_version` | 第一版固定 `1.0` | 后面扩字段时可以平滑升级，不要硬猜版本 |
| `plugin_id` | 必须和 `manifest.id` 完全一致 | 避免市场、运行时、仓库三边 id 对不上 |
| `source_type` | 用来区分内置、官方注册、第三方注册 | 前端展示和信任标记都要靠它 |
| `registry_slug` | 标识“这条记录来自哪个注册表” | 同一插件被多个注册表引用时要靠它区分来源 |
| `maintainers` | 第一版直接要求至少 1 个 | 不然出问题时没人能联系 |
| `runtime` | 只放市场和审核要用的运行时摘要，不复制整份 manifest | 避免注册表条目变成第二份 manifest |
| `source` | 记录仓库归属和提交方式 | 后续排查来源、下架、迁移都得靠它 |

#### 3.2.2.1 `maintainers` 结构

`maintainers` 第一版要求是对象数组，每项结构如下：

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `name` | string | 是 | 维护者名称 | 去空格后不能为空 |
| `role` | string | 否 | 角色说明 | 如 `author`、`maintainer` |
| `contact` | string | 是 | 联系方式 | 可以是邮箱、GitHub 主页、项目主页 |
| `github` | string | 否 | GitHub 用户名或组织名 | 方便 PR 审核对照 |

#### 3.2.2.2 `runtime` 结构

`runtime` 不是运行时代码配置，只是给注册表和市场用的摘要：

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `types` | string[] | 是 | 插件类型列表 | 必须与 manifest `types` 一致 |
| `risk_level` | string | 是 | 风险等级 | 必须与 manifest 一致 |
| `permissions` | string[] | 是 | 权限声明 | 必须与 manifest 一致 |
| `triggers` | string[] | 否 | 触发方式摘要 | 推荐与 manifest 保持一致 |

这里故意不把 `entrypoints` 放进注册表条目。

原因很简单：

- 市场识别插件，不需要知道 Python 入口字符串
- 第三方提交注册时，入口校验应该回到插件仓库里的 `manifest.json`
- 少复制一份，就少一份漂移风险

#### 3.2.2.3 `source` 结构

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `repo_owner` | string | 是 | 插件仓库 owner | 去空格后不能为空 |
| `repo_name` | string | 是 | 插件仓库名 | 去空格后不能为空 |
| `submitted_via` | string | 是 | 提交进入方式 | 第一版固定 `github_pr` |
| `registry_repo_url` | string | 否 | 注册表仓库地址 | 推荐提供 |
| `notes` | string | 否 | 来源补充说明 | 可选 |

#### 3.2.2.4 最小 JSON 示例

```json
{
  "schema_version": "1.0",
  "plugin_id": "health-basic-reader",
  "display_name": "健康基础数据插件",
  "summary": "读取基础健康数据，并转成标准 Observation 记忆。",
  "source_type": "official",
  "registry_slug": "familyclaw-official",
  "plugin_repo_url": "https://github.com/familyclaw/familyclaw-health-basic-reader",
  "manifest_url": "https://raw.githubusercontent.com/familyclaw/familyclaw-health-basic-reader/main/manifest.json",
  "docs_url": "https://github.com/familyclaw/familyclaw-health-basic-reader/blob/main/README.md",
  "homepage_url": "https://github.com/familyclaw/familyclaw-health-basic-reader",
  "maintainers": [
    {
      "name": "FamilyClaw Team",
      "role": "maintainer",
      "contact": "https://github.com/familyclaw",
      "github": "familyclaw"
    }
  ],
  "categories": ["health", "memory-sync"],
  "capabilities": ["读取步数", "读取心率", "写入 Observation"],
  "runtime": {
    "types": ["connector", "memory-ingestor"],
    "risk_level": "low",
    "permissions": ["health.read", "memory.write.observation"],
    "triggers": ["manual", "schedule"]
  },
  "status": "active",
  "source": {
    "repo_owner": "familyclaw",
    "repo_name": "familyclaw-health-basic-reader",
    "submitted_via": "github_pr",
    "registry_repo_url": "https://github.com/familyclaw/plugin-registry"
  },
  "verification": {
    "tested_against": "FamilyClaw plugin runtime v1",
    "notes": "已按第一版 manifest 规范人工走查"
  }
}
```

#### 3.2.2.5 第一版校验规则

第一版别玩“尽量兼容”。校验规则直接一点：

1. 缺少必填字段，直接拒绝条目。
2. `plugin_id`、`runtime.risk_level`、`runtime.permissions`、`runtime.types` 与 manifest 不一致，直接拒绝条目。
3. `source_type` 不在允许值内，直接拒绝条目。
4. `status` 不在允许值内，直接拒绝条目。
5. `plugin_repo_url` 不可访问，或明显不是插件仓库地址，直接拒绝条目。
6. `maintainers` 为空，直接拒绝条目。
7. 数组字段出现空字符串或重复值，直接拒绝条目。
8. 可选字段缺失可以接受，但如果填写了，就必须是合法类型和值。

### 3.3 接口契约

覆盖需求：2、3、4

#### 3.3.1 注册表仓库目录约定

- 类型：Git 仓库文件结构
- 路径或标识：`registry/plugins/<plugin_id>.json`
- 输入：第三方提交的插件注册 JSON 文件
- 输出：统一 schema 的注册项
- 校验：字段完整、链接可访问、来源明确、风险等级和权限声明清楚
- 错误：缺字段、字段不合法、与 manifest 不一致时拒绝合并

#### 3.3.2 PR 提交流程

- 类型：GitHub Pull Request 约定
- 路径或标识：官方注册表仓库的 PR 模板和审核规则
- 输入：插件注册项、插件仓库地址、文档地址、维护者信息
- 输出：审核通过或要求补充
- 校验：最少校验字段完整性、仓库有效性、文档可读性、风险说明
- 错误：信息不完整时不进入市场可见范围

#### 3.3.3 官方注册表 / 第三方注册表并存机制

第一版先把来源机制说清楚，但不把它做成复杂平台。

统一原则只有 4 条：

1. 不管是官方注册表还是第三方注册表，都必须产出同一个条目 schema。
2. 市场识别插件时，先看统一字段，不为某个来源单独发明结构。
3. 来源可信度不一样，可以标记不一样；但解析结构不能不一样。
4. 注册表只负责提供元数据，不负责下载和执行第三方代码。

来源模型如下：

| 来源类型 | 维护方 | `source_type` | 用途 | 第一版处理方式 |
| --- | --- | --- | --- | --- |
| 内置插件 | 主仓库 | `builtin` | 标识仓库内已随系统发布的插件 | 直接信任为项目内来源 |
| 官方注册表 | 项目官方 | `official` | 收录官方维护或官方认可的外部插件 | 作为默认注册表来源 |
| 第三方注册表 | 社区或组织 | `third_party` | 收录社区维护插件 | 允许接入，但要保留来源和风险标记 |

第一版最小机制如下：

- 市场或后端后续接入多个注册表时，统一按“注册表源 + 条目文件列表”读取。
- 每条记录都必须带 `registry_slug` 和 `source_type`。
- 同一个 `plugin_id` 可以出现在多个注册表，但不能把它们硬合并成一条匿名记录。
- 展示层后续如果要聚合，也必须保留“来自哪个注册表”的来源信息。

处理冲突时，先按最不容易出事故的方式来：

1. `plugin_id` 相同，但 `registry_slug` 不同：视为“同一插件被多个注册表引用”，允许共存。
2. `plugin_id` 相同，且同一 `registry_slug` 下出现多份条目：视为注册表错误，拒绝该来源。
3. 第三方注册表条目字段不完整：忽略该条目，不影响其他来源。
4. 第三方注册表整体质量太差：允许前端或后端整源禁用，不做局部容错秀操作。

#### 3.3.4 第三方 runner 调用契约（最小版）

这不是对外 HTTP API，而是主服务和本地 runner 之间的最小契约。

- 类型：主服务进程到本地子进程的 JSON 调用
- 输入：`plugin_id`、`plugin_type`、`entrypoint`、`payload`、`trigger`
- 输出：`success`、`output`、`error_code`、`error_message`、`started_at`、`finished_at`

最小输入示例：

```json
{
  "plugin_id": "health-demo-sync",
  "plugin_type": "connector",
  "entrypoint": "plugin.connector.sync",
  "trigger": "manual",
  "payload": {
    "member_id": "member-001"
  }
}
```

最小输出示例：

```json
{
  "success": true,
  "output": {
    "records": [
      {
        "record_type": "steps",
        "value": 9032,
        "captured_at": "2026-03-13T07:30:00Z"
      }
    ]
  },
  "error_code": null,
  "error_message": null,
  "started_at": "2026-03-13T07:30:00Z",
  "finished_at": "2026-03-13T07:30:01Z"
}
```

这里有 4 条硬约束：

1. runner 只返回 JSON 可序列化结构。
2. runner 不直接写数据库，不直接写审计，不直接做权限判断。
3. 主服务收到结果后，仍然走现有统一数据链路和权限链路。
4. runner 失败时必须给出明确错误码，不能只吐一段模糊 stderr。

## 4. 数据与状态模型

### 4.1 数据关系

- 插件仓库保存插件代码和 `manifest.json`
- 注册表仓库只保存插件元数据索引，不直接保存运行代码
- 一个插件可以被多个注册表引用，但必须使用同一个 `plugin_id`
- 插件市场以后只读注册表，不直接信任任意代码仓库执行内容
- 第三方插件运行时通过本地 runner 执行，不直接把代码 import 进主 API 进程

把这 4 个对象关系说成人话，就是：

1. 插件代码归插件仓库自己管。
2. 注册表只负责告诉市场“有这么一个插件，它的源码和文档在哪”。
3. 官方注册表和第三方注册表都只是索引源，不是执行源。
4. 同一个插件可以被不同注册表收录，但来源不能丢，不然后面没法追责也没法做信任标记。
5. 第三方插件自己的依赖归插件 venv 管，不归主 API 环境管。

### 4.2 状态流转

| 状态 | 含义 | 进入条件 | 退出条件 |
| --- | --- | --- | --- |
| `draft` | 插件开发中 | 开发者本地开发 | 满足提交要求 |
| `submitted` | 已提交注册 PR | 注册表仓库收到 PR | 审核通过或拒绝 |
| `active` | 已在注册表可见 | PR 合并 | 标记废弃或隐藏 |
| `deprecated` | 已不推荐使用 | 官方或维护者标记 | 重新激活或下线 |
| `hidden` | 暂不展示 | 风险或失效 | 修复后恢复 |

## 5. 错误处理

### 5.1 错误类型

- `manifest 字段错误`：字段缺失、类型不符、值不合法
- `注册表条目错误`：元数据不完整、链接无效、来源不明确
- `审核信息不足`：缺文档、缺维护者、缺风险说明
- `来源冲突`：同一插件 id 被不同条目错误复用
- `runner 执行错误`：子进程启动失败、超时、返回非法 JSON、缺依赖

### 5.2 错误响应格式

```json
{
  "detail": "插件注册项缺少 plugin_repo_url",
  "error_code": "registry_item_invalid",
  "field": "plugin_repo_url",
  "timestamp": "2026-03-13T00:00:00Z"
}
```

### 5.3 处理策略

1. 输入验证错误：直接拒绝，不模糊兼容。
2. 业务规则错误：要求补充后重新提交。
3. 外部依赖错误：仓库地址不可访问时不合并。
4. 重试、降级或补偿：第一版允许重新提交 PR，不做自动修复。
5. runner 执行错误：主服务记录失败结果并保留错误码，不把子进程异常直接冒充业务成功。

## 6. 正确性属性

### 6.1 属性 1：同一个插件必须有稳定身份

*对于任何* 可进入注册表的插件，系统都应该满足：`plugin_id` 在 manifest 和注册项中保持一致，不能一个插件在不同地方用不同 id。

**验证需求：** 需求 1、需求 2

### 6.2 属性 2：注册表只负责识别，不负责执行代码

*对于任何* 第一版注册表来源，系统都应该满足：注册表只保存元数据和来源链接，不直接承担下载、安装、执行第三方代码的职责。

**验证需求：** 需求 2、需求 4

### 6.3 属性 3：第三方注册必须可追踪

*对于任何* 进入市场可见范围的第三方插件，系统都应该满足：能看到来源注册表、源码仓库、维护者和风险等级。

**验证需求：** 需求 3、需求 4

### 6.4 属性 4：不同来源必须统一结构、保留来源

*对于任何* 被系统接入的注册表来源，系统都应该满足：官方注册表和第三方注册表使用同一条目结构，但不能丢掉 `registry_slug`、`source_type` 这类来源字段。

**验证需求：** 需求 2、需求 4

### 6.5 属性 5：第三方依赖不能污染主 API 进程

*对于任何* 走第三方 runner 形态的插件，系统都应该满足：插件自己的 Python 依赖在插件 venv 中解析，不要求把第三方依赖直接装进主 API 运行环境。

**验证需求：** 需求 1、需求 4

### 6.6 属性 6：第三方代码不能直接进入主进程

*对于任何* 走第三方 runner 形态的插件，系统都应该满足：主服务负责编排和校验，但第三方代码执行发生在本地子进程里，而不是主 API 进程里。

**验证需求：** 需求 1、需求 4

## 7. 测试策略

### 7.1 单元测试

- 校验 manifest 字段是否符合规范
- 校验注册表条目 schema 是否完整

### 7.2 集成测试

- 用样板插件生成一份完整注册项
- 检查官方注册表和第三方注册表是否能被统一解析
- 用虚拟 runner 输入输出验证主服务能否接住第三方插件返回结果

### 7.3 端到端测试

- 从“开发者按规范建插件”到“提交注册 PR”走一遍人工验收流程
- 从“注册表条目进入市场源”到“前端可识别来源”走一遍联调验证
- 从“runner 拉起插件子进程”到“主服务继续写原始记录/记忆/审计”走一遍最小链路验证

### 7.4 验证映射

| 需求 | 设计章节 | 验证方式 |
| --- | --- | --- |
| `requirements.md` 需求 1 | `design.md` §2.3.1、§3.2.1 | 文档走查、样板插件自检 |
| `requirements.md` 需求 2 | `design.md` §3.2.2、§4.1 | 注册表 schema 校验 |
| `requirements.md` 需求 3 | `design.md` §2.3.2、§3.3.2 | PR 模板和审核清单走查 |
| `requirements.md` 需求 4 | `design.md` §2.3.3、§4.1、§6.2 | 多注册表来源联调验证、runner 边界走查 |

## 8. 风险与待确认项

### 8.1 风险

- 如果注册表 schema 设计得太松，后面前端市场会很难做稳定展示。
- 如果开发规范写得太抽象，第三方还是会各写各的。
- 如果第一版就尝试自动安装远程代码，会把安全和边界一下子做炸。
- 如果第三方 runner 协议不收口，后面会把主服务和插件实现重新耦合回去。

### 8.2 待确认项

- 官方注册表仓库是否独立建仓，还是先放在主仓库的某个目录里。
- 分类枚举和市场展示标签是否需要先给一版固定列表。
- 是否需要在第一版就给 PR 模板和 JSON schema 校验脚本。
- runner 后续是单脚本入口，还是独立 `plugin_runner.py` 模块。
- runner 错误码是否需要先给一版固定枚举。

## 9. 阶段 2 检查结论

### 9.1 这一步检查了什么

- `design.md` 里的注册表条目 schema、PR 流程、来源机制是否能互相对上
- `tasks.md` 的 2.1、2.2、2.3 是否按顺序推进，没有跳步骤
- 第三方开发者文档是否只保留“怎么提交 PR”这种他们真的需要看的内容

### 9.2 这一步确认了什么

1. 注册表条目已经有稳定字段，不再靠口头约定。
2. 第三方开发者只需要按模板提 PR，不需要理解后端内部解析细节。
3. 官方注册表和第三方注册表已经明确使用同一 schema，但保留不同来源标识。
4. 第一版继续守住边界：不做自动下载安装、不做远程执行、不做沙箱执行、不做签名体系全量落地。
5. 第三方运行方向已经收口为“同容器子进程 runner”，后面实现时不用再在主进程直载和独立服务之间反复摇摆。

### 9.3 阶段 2 是否可以视为完成

可以。

原因很直接：

- 市场后续要读什么字段，已经定清楚了
- 第三方提交入口和审核清单，已经定清楚了
- 官方和第三方注册表怎么并存，已经定清楚了

后续如果要实现后端注册表解析，可以直接基于这一版 schema 和来源机制继续做，不用再回头猜规则。
