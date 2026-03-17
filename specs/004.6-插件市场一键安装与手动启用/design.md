# 设计文档 - 基于 GitHub 仓库的插件市场、一键安装与手动启用

状态：Draft

## 1. 概述

### 1.1 目标

- 把插件市场改成“基于 GitHub 仓库”的无服务器目录机制。
- 让官方市场和第三方市场仓库可以并存。
- 把“注册表仓库”和“插件源码仓库”两层职责拆开。
- 保留一键安装能力，但安装成功后默认禁用，必须手动启用。

### 1.2 覆盖需求

- `requirements.md` 需求 1：市场必须基于 GitHub 仓库，而不是中心化服务端
- `requirements.md` 需求 2：必须支持官方市场和第三方市场仓库并存
- `requirements.md` 需求 3：第三方作者必须通过 PR 向市场仓库提交插件条目
- `requirements.md` 需求 4：插件代码必须放在独立插件仓库，注册表只存元数据
- `requirements.md` 需求 5：必须定义 GitHub 仓库式市场的文件规则
- `requirements.md` 需求 6：用户必须可以基于注册表条目一键安装插件
- `requirements.md` 需求 7：安装成功后默认禁用，启用必须手动触发
- `requirements.md` 需求 8：未配置完成的插件不能被误运行
- `requirements.md` 需求 9：市场同步和安装失败必须可见、可追踪
- `requirements.md` 需求 10：市场要展示基于 GitHub 的仓库评价信息
- `requirements.md` 需求 11：仓库浏览量只能作为可选增强信息
- `requirements.md` 需求 12：市场不做内嵌 GitHub Star 写回

### 1.3 技术约束

- 必须遵守 `docs/开发设计规范/20260317-插件启用禁用统一规则.md`
- 必须遵守 `docs/开发设计规范/20260317-插件挂载与运行隔离开发规范.md`
- 必须复用 `004.3` 已经确立的“注册表 + PR 提交”方向，不能再发明第二套发布流程
- 前端只改 `user-app`
- 插件市场不能依赖新增专门市场后端服务

## 2. 架构

### 2.1 系统结构

这次架构上最关键的，不是多加几个页面，而是先把来源关系摆正。

系统分成五层：

1. **市场源配置层**
   - 管理官方市场仓库和用户添加的第三方市场仓库
   - 每个市场源都是一个 GitHub 仓库配置

2. **市场同步层**
   - 从 GitHub 仓库拉取注册表文件
   - 校验仓库结构
   - 生成本地市场快照

3. **市场聚合层**
   - 把多个市场源的插件条目聚合成统一列表
   - 但不抹掉来源信息

4. **评价指标同步层**
   - 读取 GitHub 仓库公开可读指标
   - 聚合 star、fork 等评价信息
   - 对不可公开读取的指标做降级
5. **安装执行层**
   - 根据注册表条目去插件源码仓库拉取指定版本
   - 校验 manifest、版本和完整性
   - 安装、挂载、注册插件实例

6. **运行守门层**
   - 所有执行入口统一检查 `install_status`、`enabled`、`config_status`
   - 已安装不等于可运行

### 2.2 模块职责

| 模块 | 职责 | 输入 | 输出 |
| --- | --- | --- | --- |
| `MarketplaceSourceService` | 管理市场仓库配置 | 仓库地址、分支、路径 | 市场源记录 |
| `MarketplaceSyncService` | 拉取并校验 GitHub 市场仓库 | 市场源配置 | 市场快照、同步错误 |
| `MarketplaceCatalogService` | 聚合多个市场源的条目 | 市场快照 | 插件目录列表 |
| `RegistryEntryValidator` | 校验注册表条目和仓库结构 | 条目文件、schema | 校验结果 |
| `RepositoryMetricsService` | 读取仓库 star、fork 等评价指标 | 插件源码仓库地址 | 仓库指标快照 |
| `PluginInstallTaskService` | 创建和推进安装任务 | 安装请求、注册表条目 | 安装任务 |
| `PluginPackageResolver` | 从插件源码仓库解析安装目标 | 源码仓库、版本、tag/release | 下载定位信息 |
| `PluginInstanceService` | 维护插件实例安装/启用/配置状态 | 安装结果、启停操作 | 插件实例 |
| `PluginRuntimeGuard` | 统一拦截未启用或未配置插件 | 插件实例状态 | 允许运行 / 拒绝运行 |

### 2.3 关键流程

#### 2.3.1 市场源同步流程

1. 系统内置官方市场仓库源。
2. 用户可以新增第三方市场仓库源。
3. 同步服务按仓库地址、分支和目录读取 GitHub 内容。
4. 校验仓库根目录文件、注册表索引和插件条目结构。
5. 对条目关联的插件源码仓库读取公开可读指标，如 `star`、`fork`。
6. 生成本地市场快照。
7. 前端基于快照展示市场列表、来源标签和评价指标。

#### 2.3.2 第三方发布流程

1. 第三方开发者先准备独立插件源码仓库。
2. 开发者按注册表模板在某个市场仓库新增插件条目文件。
3. 开发者向该市场仓库发起 PR。
4. 市场维护者审核条目、插件仓库地址、README、风险信息。
5. PR 合并后，该条目才会在市场同步时进入正式目录。

#### 2.3.3 一键安装流程

1. 用户在市场里点击“安装”。
2. 前端把 `source_id + plugin_id + version` 提交给后端。
3. 后端读取本地市场快照中的注册表条目。
4. 安装任务根据条目解析插件源码仓库和安装目标。
5. 执行下载、校验、解压、挂载、注册。
6. 安装成功后写入插件实例：`install_status=installed`、`enabled=false`。

#### 2.3.4 手动启用流程

1. 用户打开已安装插件详情。
2. 前端展示安装状态、配置状态、启用状态。
3. 若配置未完成，则禁止启用。
4. 用户手动点击“启用”。
5. 后端只修改 `enabled=true`，不改安装状态。
6. 后续执行链路才允许该插件运行。

#### 2.3.5 评价指标读取流程

1. 市场同步拿到注册表条目中的 `source_repo`。
2. 指标服务读取对应 GitHub 仓库的公开元数据。
3. 能公开拿到的指标写入本地快照，例如 `stargazers_count`、`forks_count`。
4. 访问量这类非公开统一指标，只有在仓库拥有者提供足够权限时才读取。
5. 指标读取失败不阻断市场条目同步，只把指标字段标记为不可用。

## 3. GitHub 仓库规则

### 3.1 市场仓库规则

市场仓库是给人提 PR 和给客户端同步用的，不是拿来塞插件源码的。

建议固定结构：

```text
<marketplace-repo>/
  market.json
  plugins/
    <plugin_id>/
      entry.json
      README.md
      icon.png                # 可选
      screenshots/            # 可选
  schemas/
    entry.schema.json         # 可选，供人工和 CI 复用
  .github/
    PULL_REQUEST_TEMPLATE.md
```

#### 3.1.1 根文件 `market.json`

作用：定义这个市场仓库自己的元数据。

最小字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `market_id` | string | 是 | 市场唯一标识 |
| `name` | string | 是 | 市场展示名 |
| `owner` | string | 是 | 市场维护方 |
| `repo_url` | string | 是 | GitHub 仓库地址 |
| `default_branch` | string | 是 | 默认分支 |
| `entry_root` | string | 是 | 插件条目根目录，默认 `plugins/` |
| `trusted_level` | string | 是 | `official` / `third_party` |

#### 3.1.2 单插件目录 `plugins/<plugin_id>/`

这里故意一插件一个目录，不用一堆散文件。原因很简单：

- 以后 README、图标、截图、审查备注都能放一起
- PR diff 也更清楚
- 客户端读取逻辑稳定

#### 3.1.3 插件条目文件 `entry.json`

作用：描述这个插件是谁、代码在哪、安装目标是什么。

最小字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `plugin_id` | string | 是 | 插件唯一标识，必须与目录名一致 |
| `name` | string | 是 | 展示名 |
| `summary` | string | 是 | 简介 |
| `source_repo` | string | 是 | 插件源码 GitHub 仓库地址 |
| `manifest_path` | string | 是 | 源码仓库中 manifest 路径，默认 `manifest.json` |
| `readme_url` | string | 是 | 插件 README 地址 |
| `publisher` | object | 是 | 发布方摘要 |
| `categories` | array | 否 | 分类 |
| `risk_level` | string | 是 | 风险等级 |
| `permissions` | array | 是 | 权限摘要 |
| `latest_version` | string | 是 | 默认安装版本 |
| `versions` | array | 是 | 可安装版本列表 |
| `install` | object | 是 | 默认安装来源与校验信息 |
| `repository_metrics` | object | 否 | 仓库公开评价指标快照 |
| `maintainers` | array | 否 | 维护者信息 |

#### 3.1.4 版本条目 `versions[*]`

建议字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `version` | string | 是 | 版本号 |
| `git_ref` | string | 是 | tag 或 commit |
| `artifact_type` | string | 是 | `release_asset` / `source_archive` |
| `artifact_url` | string | 是 | GitHub release asset 或 archive 地址 |
| `checksum` | string | 否 | 完整性摘要 |
| `published_at` | string | 否 | 发布时间 |
| `min_app_version` | string | 否 | 最低宿主版本 |

#### 3.1.5 仓库评价指标 `repository_metrics`

建议字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `stargazers_count` | integer | 否 | GitHub star 数 |
| `forks_count` | integer | 否 | GitHub fork 数 |
| `subscribers_count` | integer | 否 | 仓库订阅数，可选 |
| `open_issues_count` | integer | 否 | 公开 issue 数，可选 |
| `views_count` | integer | 否 | 仓库访问量，仅授权可读时存在 |
| `views_period_days` | integer | 否 | 访问量统计周期，通常 14 天 |
| `fetched_at` | string | 是 | 指标抓取时间 |
| `availability` | object | 是 | 哪些字段可用、哪些字段不可用 |

### 3.2 插件源码仓库规则

插件源码仓库是事实来源。注册表条目不能替代它。

建议最小结构：

```text
<plugin-repo>/
  manifest.json
  README.md
  requirements.txt
  plugin/
  tests/
```

最小规则：

1. `manifest.json` 必须存在，且 `id` 必须和注册表 `plugin_id` 一致。
2. README 必须存在，至少说明插件用途、权限、风险和最小验证方式。
3. 依赖清单必须存在，不能把依赖信息只写在注册表里。
4. 安装目标必须能稳定定位到具体版本，不能只给一个会漂移的主页链接。

### 3.3 PR 提交流程规则

这次不重写开发者文档全文，但实现层要按下面几条消费：

1. PR 合并前，插件不进入正式市场目录。
2. 市场同步只读默认分支的正式内容，不读 PR 临时内容。
3. 注册表条目必须能定位到插件源码仓库。
4. 条目缺字段、字段和 manifest 对不上、安装目标不可解析，都视为无效条目。

## 4. 组件和接口

### 4.1 核心组件

- `MarketplaceSource`：一个市场仓库源配置。
- `MarketplaceSnapshot`：一次同步后的本地快照。
- `RegistryEntry`：市场仓库中的单插件条目。
- `PluginInstallTask`：插件安装任务。
- `PluginInstance`：安装到本地后的插件实例。

### 4.2 数据结构

#### 4.2.1 市场源 `marketplace_source`

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `source_id` | string | 是 | 市场源编号 | 全局唯一 |
| `name` | string | 是 | 展示名称 | 非空 |
| `repo_url` | string | 是 | GitHub 仓库地址 | 必须是 GitHub URL |
| `branch` | string | 是 | 读取分支 | 默认仓库主分支 |
| `entry_root` | string | 是 | 条目目录 | 默认 `plugins/` |
| `trusted_level` | string | 是 | `official` / `third_party` | 非空 |
| `enabled` | boolean | 是 | 是否启用该市场源 | 默认 `true` |
| `last_sync_status` | string | 否 | 最近同步状态 | `success` / `failed` |
| `last_sync_error` | object | 否 | 最近同步错误 | 可为空 |

#### 4.2.2 市场条目快照 `marketplace_entry_snapshot`

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `source_id` | string | 是 | 所属市场源 | 非空 |
| `plugin_id` | string | 是 | 插件标识 | 与目录一致 |
| `name` | string | 是 | 展示名 | 非空 |
| `source_repo` | string | 是 | 插件源码仓库 | GitHub URL |
| `latest_version` | string | 是 | 最新可安装版本 | 非空 |
| `risk_level` | string | 是 | 风险等级 | 非空 |
| `install` | object | 是 | 安装元数据 | 非空 |
| `repository_metrics` | object | 否 | 仓库评价指标快照 | 可为空 |
| `manifest_digest` | string | 否 | manifest 摘要 | 可为空 |
| `sync_status` | string | 是 | 条目同步状态 | `ready` / `invalid` |
| `sync_error` | object | 否 | 条目错误信息 | 可为空 |

#### 4.2.3 插件实例 `plugin_instance`

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `instance_id` | string | 是 | 插件实例编号 | 全局唯一 |
| `source_id` | string | 是 | 安装来源市场 | 非空 |
| `plugin_id` | string | 是 | 插件标识 | 非空 |
| `installed_version` | string | 是 | 当前已安装版本 | 非空 |
| `install_status` | string | 是 | 安装状态 | 见 5.2 |
| `enabled` | boolean | 是 | 是否允许运行 | 默认 `false` |
| `config_status` | string | 是 | 配置状态 | `unconfigured` / `configured` / `invalid` |
| `source_repo` | string | 是 | 插件源码仓库 | 非空 |
| `market_repo` | string | 是 | 市场仓库 | 非空 |
| `installed_at` | datetime | 否 | 安装完成时间 | 成功后必填 |

### 4.3 接口契约

#### 4.3.1 查询市场源列表

- 类型：HTTP
- 路径：`GET /api/plugin-marketplace/sources`
- 输出：市场源列表、信任级别、同步状态
- 错误：`invalid_query`

#### 4.3.2 添加第三方市场源

- 类型：HTTP
- 路径：`POST /api/plugin-marketplace/sources`
- 输入：`repo_url`、`branch?`、`entry_root?`
- 输出：新增市场源记录
- 校验：必须是合法 GitHub 仓库，且结构可识别
- 错误：`invalid_market_repo`、`market_repo_conflict`、`market_repo_structure_invalid`

#### 4.3.3 同步市场源

- 类型：HTTP
- 路径：`POST /api/plugin-marketplace/sources/{source_id}/sync`
- 输入：`source_id`
- 输出：同步结果摘要
- 错误：`source_not_found`、`market_sync_failed`

#### 4.3.4 查询聚合市场目录

- 类型：HTTP
- 路径：`GET /api/plugin-marketplace/catalog`
- 输入：关键词、分类、来源过滤
- 输出：聚合条目列表，保留 `source_id`、`trusted_level` 和 `repository_metrics`
- 错误：`invalid_query`

#### 4.3.5 查询单插件详情

- 类型：HTTP
- 路径：`GET /api/plugin-marketplace/catalog/{source_id}/{plugin_id}`
- 输入：`source_id`、`plugin_id`
- 输出：插件条目详情、来源信息、仓库评价指标、GitHub 跳转地址
- 校验：无效条目仍可查看，但必须明确标记不可安装
- 错误：`entry_not_found`

#### 4.3.6 创建安装任务

- 类型：HTTP
- 路径：`POST /api/plugin-marketplace/install-tasks`
- 输入：`source_id`、`plugin_id`、`version?`
- 输出：`task_id`、`install_status=queued`
- 校验：条目必须可安装；同一插件不能并行重复安装
- 错误：`entry_not_found`、`entry_not_installable`、`install_task_conflict`

#### 4.3.7 手动启用插件

- 类型：HTTP
- 路径：`POST /api/plugins/instances/{instance_id}/enable`
- 输入：`instance_id`
- 输出：更新后的实例状态
- 校验：必须 `install_status=installed` 且 `config_status=configured`
- 错误：`instance_not_installed`、`plugin_not_configured`、`plugin_enable_blocked`

## 5. 数据与状态模型

### 5.1 数据关系

这里的核心数据关系必须足够简单：

1. 市场仓库定义“谁可以被发现”。
2. 插件源码仓库定义“真实代码和真实 manifest 是什么”。
3. 市场快照定义“本地当前看到了什么”。
4. 仓库指标快照定义“这个插件仓库公开能看到哪些评价信息”。
5. 安装任务定义“这次安装现在做到哪了”。
6. 插件实例定义“这个插件在本机到底装没装、能不能跑”。

不要把注册表条目、安装任务、实例状态混成一个对象。那样后面一定一堆补丁。

### 5.2 状态流转

#### 5.2.1 市场源同步状态

| 状态 | 含义 | 进入条件 | 退出条件 |
| --- | --- | --- | --- |
| `idle` | 尚未同步 | 新增市场源 | 发起同步 |
| `syncing` | 正在同步 | 发起同步 | 成功或失败 |
| `success` | 最近一次同步成功 | 拉取并校验通过 | 再次同步 |
| `failed` | 最近一次同步失败 | 拉取失败或结构错误 | 重试同步成功 |

#### 5.2.2 安装状态 `install_status`

| 状态 | 含义 | 进入条件 | 退出条件 |
| --- | --- | --- | --- |
| `not_installed` | 本地尚未安装 | 默认状态 | 创建安装任务 |
| `queued` | 已创建安装任务 | 用户点击安装 | 开始解析下载目标 |
| `resolving` | 正在解析插件仓库安装目标 | 任务开始执行 | 解析成功或失败 |
| `downloading` | 正在下载插件包 | 解析成功 | 下载完成或失败 |
| `validating` | 正在校验 manifest 和完整性 | 下载完成 | 校验成功或失败 |
| `installing` | 正在解压、挂载、注册 | 校验通过 | 安装完成或失败 |
| `installed` | 安装完成 | 安装执行成功 | 卸载或升级 |
| `install_failed` | 安装失败 | 任一步失败 | 用户重试安装 |
| `uninstalled` | 已卸载 | 卸载成功 | 重新安装 |

#### 5.2.3 启用状态 `enabled`

| 状态 | 含义 | 进入条件 | 退出条件 |
| --- | --- | --- | --- |
| `false` | 已安装但不允许运行，或尚未安装 | 默认值；安装成功后默认写入 | 用户手动启用 |
| `true` | 允许运行 | 用户手动启用且配置通过校验 | 用户手动禁用、卸载、隔离 |

#### 5.2.4 配置状态 `config_status`

| 状态 | 含义 | 进入条件 | 退出条件 |
| --- | --- | --- | --- |
| `unconfigured` | 必填配置未补齐 | 安装完成但未配置 | 保存合法配置 |
| `configured` | 配置完整 | 配置校验通过 | 配置变脏 |
| `invalid` | 配置错误 | 配置校验失败 | 修复并重新校验通过 |

### 5.3 关键不变量

1. 市场同步失败不能破坏本地已安装插件实例。
2. `install_status=installed` 不自动推出 `enabled=true`。
3. `enabled=true` 的前提必须是 `install_status=installed` 且 `config_status=configured`。
4. 注册表条目不是源码事实来源，manifest 校验必须回到插件源码仓库或安装产物。
5. 多个市场源同名插件必须保留来源，不允许静默吃掉来源信息。
6. 评价指标缺失不等于插件质量差，只代表 GitHub 没公开给我们或当前没授权。

## 6. 错误处理

### 6.1 错误类型

- `market_repo_structure_invalid`：市场仓库结构不符合规则。
- `market_sync_failed`：拉取 GitHub 仓库失败。
- `registry_entry_invalid`：单条注册表元数据不合法。
- `plugin_repo_unreachable`：插件源码仓库不可访问。
- `repository_metrics_unavailable`：仓库评价指标当前不可读取。
- `install_target_invalid`：条目里声明的安装目标不可解析。
- `manifest_mismatch`：注册表条目和插件 manifest 不一致。
- `download_failed`：下载插件包失败。
- `package_validation_failed`：完整性或版本校验失败。
- `plugin_not_configured`：配置未完成，禁止启用。

### 6.2 错误响应格式

```json
{
  "detail": "市场仓库结构不合法，缺少根文件 market.json",
  "error_code": "market_repo_structure_invalid",
  "source_id": "official-market",
  "timestamp": "2026-03-17T00:00:00Z"
}
```

### 6.3 处理策略

1. 市场源结构错误：拒绝接入或标记同步失败，不生成假目录。
2. 注册表条目错误：仅把该条目标记为无效，不拖垮整个市场源。
3. 仓库指标读取错误：只降级评价字段，不阻断条目同步和安装。
4. 插件仓库解析错误：禁止安装，并给出仓库级定位信息。
5. 安装流程错误：清理临时产物，不留下半装状态。
6. 启用前置条件错误：允许继续改配置，但不允许执行。

## 7. 测试策略

### 7.1 单元测试

- 市场仓库结构校验测试
- 注册表条目 schema 校验测试
- 多市场源同名插件来源保留测试
- star、fork 等公开指标同步测试
- 浏览量不可读时的降级测试
- 安装与启用分离测试

### 7.2 集成测试

- 官方市场仓库同步测试
- 第三方市场仓库接入测试
- 仓库评价指标聚合同步测试
- 基于注册表条目解析插件源码仓库并安装测试
- manifest 不一致阻断安装测试
- 安装成功但默认禁用测试

### 7.3 端到端测试

- 添加第三方市场仓库并成功展示插件
- 市场卡片正确展示 star、fork，且浏览量缺失时不报错
- 用户从市场一键安装插件后看到“已安装未启用”
- 用户补齐配置后手动启用插件
- 市场仓库结构错误时给出明确提示

### 7.4 验证映射

| 需求 | 设计章节 | 验证方式 |
| --- | --- | --- |
| `requirements.md` 需求 1 | `design.md` 2.1、3.1、4.3.2 | 集成测试、人工审查 |
| `requirements.md` 需求 2 | `design.md` 2.3.1、4.2.1、5.3 | 集成测试、端到端测试 |
| `requirements.md` 需求 3 | `design.md` 2.3.2、3.3 | 人工审查、流程测试 |
| `requirements.md` 需求 4 | `design.md` 3.1.3、3.2、5.1 | 集成测试 |
| `requirements.md` 需求 5 | `design.md` 3.1、3.2 | 单元测试、人工审查 |
| `requirements.md` 需求 6 | `design.md` 2.3.3、4.3.5、5.2.2 | 集成测试、端到端测试 |
| `requirements.md` 需求 7 | `design.md` 2.3.4、5.2.3、5.3 | 单元测试、端到端测试 |
| `requirements.md` 需求 8 | `design.md` 5.2.4、5.3 | 单元测试、集成测试 |
| `requirements.md` 需求 9 | `design.md` 4.2、6.1、6.3 | 集成测试、端到端测试 |
| `requirements.md` 需求 10 | `design.md` 2.3.5、3.1.5、4.3.4 | 单元测试、端到端测试 |
| `requirements.md` 需求 11 | `design.md` 2.3.5、5.3、6.3 | 单元测试、集成测试 |
| `requirements.md` 需求 12 | `design.md` 4.3.5、5.3、8.2 | 人工审查、前端走查 |

## 8. 风险与待确认项

### 8.1 风险

- GitHub 速率限制和网络波动会直接影响市场同步体验，如果不做快照缓存，市场页面会非常脆弱。
- 如果条目 schema 设计得太松，第三方市场很快会变成格式垃圾场。
- 如果前端仍只显示“已安装”，用户一定会误解插件已经可运行。
- 如果把“浏览量”硬当成所有插件都该有的字段，第三方仓库很快就会出现大量空值和误导。

### 8.2 待确认项

- 官方市场仓库最终采用哪个 GitHub 仓库地址。
- 安装目标优先支持 `release_asset` 还是也允许 `source_archive`。
- 第三方市场仓库是否允许关闭结构校验中的部分非关键字段检查。
- 是否在 UI 上把 `star/fork` 明确标成“GitHub 仓库指标”，避免用户误解成平台内评分。
