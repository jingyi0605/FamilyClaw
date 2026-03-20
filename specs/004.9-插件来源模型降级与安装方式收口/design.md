# 设计文档 - 插件来源模型降级与安装方式收口

状态：In Review

## 1. 概述

### 1.1 目标

- 砍掉 `official` 这条伪语义，把插件系统收口到最小可用模型。
- 把“插件类型”和“安装方式”拆成两条清晰轴线，避免目录、数据库和流程继续互相污染。
- 让开发源码目录从运行时目录中搬出去，彻底结束开发态和安装态互相踩踏的问题。
- 在不破坏现有插件能力的前提下，完成数据库、目录和同步链路迁移。

### 1.2 覆盖需求

- `requirements.md` 需求 1
- `requirements.md` 需求 2
- `requirements.md` 需求 3
- `requirements.md` 需求 4
- `requirements.md` 需求 5

### 1.3 技术约束

- 后端：FastAPI、SQLAlchemy、Alembic。
- 数据存储：PostgreSQL + 文件系统运行时目录。
- 插件运行：沿用当前 subprocess runner、插件挂载和启动同步机制。
- 兼容要求：迁移期内必须能读旧数据，最终态必须停止写旧模型。
- 文档要求：只要接口语义、目录语义或开发流程变化，对应正式文档必须同一变更同步更新。

## 2. 架构

### 2.1 新的分类模型

这次收口后，插件系统只保留两层判断：

1. **插件类型**
   - `builtin`
   - `third_party`

2. **安装方式**
   - `marketplace`
   - `local`
   - 内置插件没有安装方式字段，或者显式为空

这意味着：

- “官方插件”不再是正式数据模型的一部分。
- 默认市场源是不是系统自带，只属于“市场源元数据”，不属于“插件来源类型”。
- 第三方插件无论以前来源于 `official` 还是 `third_party`，统一收口为 `third_party`。

### 2.2 目录结构

#### 2.2.1 开发源码目录

仓库内新增独立开发源码目录：

```text
apps/api-server/plugins-dev/
  <plugin_id>/
```

用途：

- 存放仓库内开发、联调中的第三方插件源码。
- 不参与市场安装目录扫描。
- 不参与家庭级运行时落盘。

约束：

- 宿主启动不得依赖该目录存在。
- 该目录不得写入家庭 ID、安装版本等运行时信息。

#### 2.2.2 运行时安装目录

运行时目录统一收口到：

```text
apps/api-server/data/plugins/
  third_party/
    local/
      <household_id>/
        <plugin_id>/
          <release_dir>/
    marketplace/
      <household_id>/
        <plugin_id>/
          <version>/
```

保留原因：

- `data/` 目录天然表示运行时可变产物。
- `third_party/local` 和 `third_party/marketplace` 正好对应两种安装方式。

删除内容：

- `apps/api-server/data/plugins/official/` 不再作为正式运行时目录。

#### 2.2.3 内置插件目录

内置插件继续保持宿主自带目录和注册表加载方式，不进入第三方安装目录，也不参与第三方同步扫描。

### 2.3 模块职责

| 模块 | 职责 | 输入 | 输出 |
| --- | --- | --- | --- |
| 插件挂载模型 | 表达插件类型、安装方式、运行路径 | 数据库记录、插件 manifest | 统一挂载记录 |
| 本地安装流程 | 处理本地包或本地目录安装 | 本地插件包、manifest、家庭上下文 | `third_party + local` 挂载与落盘 |
| 市场安装流程 | 处理市场解析、下载、安装和升级 | 市场源、条目快照、插件包 | `third_party + marketplace` 挂载与落盘 |
| 启动同步流程 | 启动时从磁盘恢复挂载和市场实例 | 运行时目录、数据库、家庭列表 | 最新挂载记录与实例状态 |
| 市场源模型 | 表达市场仓库本身，而不是插件信任等级 | 默认市场源、用户自定义市场源 | 市场源元数据 |
| 迁移与兼容层 | 处理旧字段、旧目录和旧值回填 | `official` 旧数据和旧目录 | 新模型数据与新目录 |

### 2.4 关键流程

#### 2.4.1 第三方本地安装流程

1. 用户或开发者提交本地包、本地目录或本地导入请求。
2. System 校验 manifest。
3. System 生成 `install_method=local` 的目标目录：
   `data/plugins/third_party/local/<household_id>/<plugin_id>/<release_dir>/`
4. System 复制产物并创建或更新第三方挂载记录。
5. System 后续启停、清理和排障都按 `third_party + local` 处理。

#### 2.4.2 第三方市场安装流程

1. System 从市场源读取条目和版本信息。
2. 下载并解包插件包。
3. 生成 `install_method=marketplace` 的目标目录：
   `data/plugins/third_party/marketplace/<household_id>/<plugin_id>/<version>/`
4. 创建或更新第三方挂载记录和市场安装实例。
5. 升级和卸载都只操作 `marketplace` 安装分支。

#### 2.4.3 启动同步流程

启动同步收口为三段：

1. 内置插件注册表同步。
2. 第三方本地安装目录同步。
3. 第三方市场安装目录同步。

删除的流程：

- 官方插件目录专属同步。
- 按 `trusted_level in {"official","third_party"}` 遍历市场安装目录。

#### 2.4.4 旧数据兼容与迁移流程

1. 数据库迁移增加新字段，保留旧字段的兼容读取窗口。
2. 迁移脚本将旧 `official` 挂载记录回填为 `third_party`。
3. 市场源表把 `trusted_level=official|third_party` 收口为 `is_system=true|false`。
4. 文件系统把旧 `official/marketplace` 目录迁移到 `third_party/marketplace`。
5. 仓库内开发中的官方插件源码迁移到 `apps/api-server/plugins-dev/`。
6. 代码切换为只写新字段和新目录。
7. 清理兼容写路径，保留必要的旧数据只读兼容或一次性迁移脚本。

## 3. 组件和接口

### 3.1 核心组件

覆盖需求：1、2、3、4、5

- **插件来源模型组件**：统一 `PluginSourceType`、`PluginMount` 和相关 DTO，只保留 `builtin`、`third_party`。
- **安装方式组件**：在第三方挂载、安装结果和清理逻辑中显式表达 `install_method`。
- **市场源组件**：用 `is_system` 或等价字段表达“是否系统内置市场源”，不再用 `trusted_level`。
- **磁盘目录组件**：统一生成本地安装和市场安装路径。
- **兼容迁移组件**：承接旧目录、旧数据、旧接口值。

### 3.2 数据结构

覆盖需求：1、2、4、5

#### 3.2.1 `PluginSourceType`

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `value` | enum | 是 | 插件类型 | 只允许 `builtin`、`third_party` |

说明：

- `official` 从正式枚举中删除。

#### 3.2.2 `PluginInstallMethod`

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `value` | enum | 否 | 第三方插件安装方式 | 只允许 `local`、`marketplace`；内置插件为空 |

#### 3.2.3 `PluginMount`

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `plugin_id` | string | 是 | 插件 ID | 全局稳定 |
| `source_type` | enum | 是 | 插件类型 | `builtin` 或 `third_party` |
| `install_method` | enum \| null | 否 | 安装方式 | `third_party` 必填，`builtin` 为空 |
| `plugin_root` | string | 是 | 插件根目录 | 必须指向新目录结构 |
| `manifest_path` | string | 是 | manifest 路径 | 必须位于 `plugin_root` 下 |
| `enabled` | boolean | 是 | 是否启用 | 沿用现有规则 |

规则：

1. `source_type=builtin` 时，`install_method` 必须为空。
2. `source_type=third_party` 时，`install_method` 必须为 `local` 或 `marketplace`。
3. 不允许再写入 `source_type=official`。

#### 3.2.4 `PluginMarketplaceSource`

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `source_id` | string | 是 | 市场源 ID | 唯一 |
| `repo_url` | string | 是 | 仓库地址 | 合法仓库 URL |
| `entry_root` | string | 是 | 条目目录 | 非空 |
| `is_system` | boolean | 是 | 是否系统内置市场源 | 替代旧 `trusted_level` |
| `enabled` | boolean | 是 | 是否启用 | 沿用现有规则 |

规则：

1. `is_system=true` 只表示“系统自带默认市场源”。
2. 市场源不会再决定插件类型。

#### 3.2.5 `market.json`

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `market_id` | string | 是 | 市场 ID | 非空 |
| `name` | string | 是 | 市场名称 | 非空 |
| `repo_url` | string | 是 | 仓库地址 | 必须匹配当前源 |
| `default_branch` | string | 是 | 默认分支 | 非空 |
| `entry_root` | string | 是 | 条目根目录 | 非空 |

变更：

- `trusted_level` 从正式契约中移除。
- 迁移期内如果读取到旧字段，只做兼容忽略，不再参与校验。

### 3.3 接口契约

覆盖需求：1、2、4、5

#### 3.3.1 插件挂载读写接口

- 类型：HTTP / Service / Repository
- 输入：
  - `plugin_id`
  - `source_type`
  - `install_method`
  - 路径信息
- 输出：
  - 挂载记录
- 校验：
  - 不允许新增 `official`
  - `third_party` 必须带安装方式
  - `builtin` 不得带安装方式
- 错误：
  - `plugin_source_type_invalid`
  - `plugin_install_method_invalid`

#### 3.3.2 市场源创建与同步接口

- 类型：HTTP / Service
- 输入：
  - 市场源仓库地址
  - 分支
  - entry root
- 输出：
  - 市场源记录
  - 条目快照
- 校验：
  - 不再要求 `trusted_level=third_party`
  - 系统默认市场源通过 `is_system` 管理
- 错误：
  - `market_repo_structure_invalid`
  - `marketplace_source_conflict`

#### 3.3.3 启动同步接口

- 类型：启动期 Service
- 输入：
  - 家庭列表
  - 运行时安装目录
  - 数据库现有记录
- 输出：
  - 同步后的挂载记录
  - 同步日志
- 校验：
  - 只扫描 `third_party/local` 与 `third_party/marketplace`
  - 不再依赖 `official` 目录
- 错误：
  - 目录缺失、manifest 无效、路径与记录不一致

## 4. 数据与状态模型

### 4.1 数据关系

新的核心关系如下：

- **内置插件**
  - 插件注册表 -> 内置插件运行时

- **第三方本地安装插件**
  - 第三方插件 -> `install_method=local` -> 本地安装目录 -> 挂载记录

- **第三方市场安装插件**
  - 市场源 -> 条目快照 -> 安装任务 / 安装实例 -> `install_method=marketplace` -> 市场安装目录 -> 挂载记录

这里最关键的一点：

- 市场源是否系统自带，不再决定插件是什么类型。
- 插件是不是第三方，也不再决定它是市场装还是本地装。

### 4.2 状态流转

| 状态 | 含义 | 进入条件 | 退出条件 |
| --- | --- | --- | --- |
| `legacy_official` | 旧数据仍带 `official` 语义 | 迁移前旧记录存在 | 迁移脚本回填完成 |
| `normalized` | 已收口到新模型 | 写入或回填为新字段 | 删除、卸载或再次迁移 |
| `installed_local` | 第三方本地安装完成 | 本地安装成功 | 卸载、覆盖安装 |
| `installed_marketplace` | 第三方市场安装完成 | 市场安装成功 | 卸载、升级 |

## 5. 错误处理

### 5.1 错误类型

- **旧来源值错误**：仍然试图写入 `official`。
- **安装方式缺失错误**：第三方插件没有 `install_method`。
- **目录结构错误**：插件落盘目录不符合新目录结构。
- **迁移回填错误**：数据库或磁盘旧数据无法映射到新模型。
- **市场源契约错误**：旧 `trusted_level` 逻辑仍然参与校验。

### 5.2 错误响应格式

```json
{
  "detail": "Plugin install method is required for third_party plugin",
  "error_code": "plugin_install_method_invalid",
  "field": "install_method",
  "timestamp": "2026-03-20T00:00:00Z"
}
```

### 5.3 处理策略

1. 输入校验错误：拒绝写入，并返回明确字段名。
2. 迁移回填错误：中断该条数据迁移，记录日志并保留人工处理入口。
3. 磁盘目录缺失：启动同步跳过并告警，不允许让宿主整体启动失败。
4. 旧字段兼容期结束后：拒绝继续写旧值，但保留清晰错误信息。

## 6. 正确性属性

### 6.1 属性 1：插件类型和安装方式不能混写

*对于任何* 插件挂载记录，系统都应该满足：

- `builtin` 只表示宿主内置插件
- `third_party` 只表示第三方插件
- `install_method` 只描述第三方插件怎么装进来

系统不得再把“谁维护市场源”偷渡成插件类型。

**验证需求：** `requirements.md` 需求 1、需求 2、需求 5

### 6.2 属性 2：开发源码目录不是运行时目录

*对于任何* 第三方插件开发流程，系统都应该满足：

- 仓库开发源码目录只存源码
- `data/plugins/` 只存运行时产物
- 任一方都不能覆盖另一方

**验证需求：** `requirements.md` 需求 3

### 6.3 属性 3：迁移后不再生成 official 新数据

*对于任何* 新建、更新、安装、同步和清理流程，系统都应该满足：

- 不再新增 `official` 字段值
- 不再新增 `official` 目录
- 不再新增 `trusted_level` 驱动的插件分支

**验证需求：** `requirements.md` 需求 4、需求 5

## 7. 测试策略

### 7.1 单元测试

- `PluginSourceType` 和 `PluginInstallMethod` 校验。
- 第三方挂载必须带安装方式。
- `market.json` 兼容旧 `trusted_level`、正式忽略旧字段。
- 市场源 `is_system` 行为校验。
- 新目录生成函数只生成 `third_party/local` 和 `third_party/marketplace`。

### 7.2 集成测试

- 本地安装写入 `third_party/local` 并能被启动同步恢复。
- 市场安装写入 `third_party/marketplace` 并能被启动同步恢复。
- 旧 `official/marketplace` 目录迁移后实例仍可恢复。
- 删除和清理只作用于目标安装方式。

### 7.3 端到端测试

- 从市场安装第三方插件、启用、升级、卸载全链路。
- 从本地安装第三方插件、启用、覆盖升级、卸载全链路。
- 仓库开发源码目录存在或缺失时，宿主都能正常启动。

### 7.4 验证映射

| 需求 | 设计章节 | 验证方式 |
| --- | --- | --- |
| `requirements.md` 需求 1 | `design.md` 2.1、3.2.1、3.2.3、6.1 | 单元测试、启动同步集成测试、代码走查 |
| `requirements.md` 需求 2 | `design.md` 2.1、2.4.1、2.4.2、3.2.2、3.2.3 | 本地安装和市场安装集成测试 |
| `requirements.md` 需求 3 | `design.md` 2.2、6.2 | 目录结构检查、端到端测试、人工走查 |
| `requirements.md` 需求 4 | `design.md` 2.4.4、5.3、6.3 | Alembic 迁移测试、旧目录迁移测试 |
| `requirements.md` 需求 5 | `design.md` 3.2.4、3.2.5、3.3.2、6.1 | 市场源单元测试、市场源同步集成测试 |

## 8. 风险与待确认项

### 8.1 风险

- 旧 `official` 数据可能散落在数据库、磁盘目录、测试用例和文档里，不是一刀删一个枚举就能结束。
- 当前代码可能默认把“默认市场源 = 官方市场源 = 官方插件”三件事绑死，拆开时容易漏掉判断。
- 开发者当前已经在 `data/plugins/official` 下工作，迁移开发目录时要明确一次性搬迁方式和后续开发规范。

### 8.2 待确认项

- 第三方开发源码目录最终命名是否固定为 `apps/api-server/plugins-dev/`；本 Spec 先按这个路径设计。
- 对旧 `market.json` 的 `trusted_level` 字段是保留一版兼容读取后废弃，还是直接忽略但不报错；本 Spec 默认兼容读取一版并忽略。
- 是否需要提供一次性迁移脚本帮助把当前仓库内的旧“官方插件开发目录”搬到 `plugins-dev/`；本 Spec 建议提供。
