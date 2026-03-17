# 设计文档 - 插件版本治理与手动升级

状态：Draft

## 1. 概述

### 1.1 目标

- 把插件版本信息从散装字段收成统一结果
- 补上宿主兼容性判断和版本筛选逻辑
- 支持手动升级和手动回滚
- 保证升级默认不破坏现有启停和配置状态
- 把当前版本治理边界写清楚，避免继续自欺欺人

### 1.2 覆盖需求

- `requirements.md` 需求 1：系统必须提供统一插件版本结果
- `requirements.md` 需求 2：系统必须在安装和升级前做宿主兼容性判断
- `requirements.md` 需求 3：系统必须支持手动升级和手动回滚
- `requirements.md` 需求 4：升级和回滚不能破坏现有用户空间
- `requirements.md` 需求 5：前端必须清楚展示版本治理状态
- `requirements.md` 需求 6：版本治理规则和文档必须保持一致

### 1.3 技术约束

- 后端：FastAPI + SQLAlchemy + 现有 `app.modules.plugin`、`app.modules.plugin_marketplace`
- 前端：`apps/user-app`
- 数据存储：现有插件市场表、插件挂载表、插件状态表、插件配置表
- 认证授权：沿用现有家庭管理员权限边界
- 外部依赖：GitHub 市场条目里的版本列表和兼容性字段

### 1.4 当前代码真相（2026-03-17 盘点）

- 市场条目已经有 `latest_version`、`versions[]`、`min_app_version`，但安装链路当前还没消费 `min_app_version`。
- 安装链路已经支持按指定版本安装，也会校验 `manifest.version` 和目标版本一致。
- 安装目录已经天然按 `household_id/plugin_id/version` 落盘，这为手动回滚提供了现实基础。
- 通用插件注册表虽然已经有 `version / installed_version / compatibility / update_state`，但 `update_state` 现在只是最粗糙的字符串比较。
- 市场前端页面当前默认拿 `latest_version` 发起安装，没有“最新可兼容版本”概念，也没有升级和回滚入口。

## 2. 架构

### 2.1 系统结构

这次不新增一套“版本中心服务”，而是在现有插件和市场模块上补一层统一的版本治理逻辑。

系统分成四层：

1. **版本事实层**
   - 市场条目版本列表
   - 已安装实例版本
   - 当前 manifest 声明版本
   - 宿主版本

2. **版本判断层**
   - 版本解析
   - 宿主兼容性校验
   - 最新可兼容版本筛选
   - 更新状态归类

3. **版本操作层**
   - 手动升级
   - 手动回滚
   - 升级后的状态保持与降级

4. **前端消费层**
   - 市场卡片版本状态
   - 插件详情版本状态
   - 升级/回滚弹窗与风险提示

### 2.2 模块职责

| 模块 | 职责 | 输入 | 输出 |
| --- | --- | --- | --- |
| `app.modules.plugin.versioning` | 统一版本解析、兼容性判断、状态归类 | 已安装版本、市场版本列表、宿主版本 | 统一版本治理结果 |
| `app.modules.plugin_marketplace.service` | 承接安装、升级、回滚和版本相关接口 | 市场条目、插件实例、用户操作 | 安装任务、升级结果、回滚结果 |
| `app.modules.plugin.service` | 把版本治理结果挂到统一插件注册出口 | 插件实例、manifest、版本治理结果 | `PluginRegistryItem` |
| `apps/user-app` 插件页 | 展示版本状态和升级入口 | 市场目录、插件详情、治理结果 | 页面状态和用户操作 |
| 文档体系 | 明确边界和后续扩展路径 | 需求、设计、实现结果 | 一致文档 |

### 2.3 关键流程

#### 2.3.1 统一版本治理结果计算

1. 读取当前宿主版本。
2. 读取插件实例里的 `installed_version`。
3. 读取市场条目 `versions[]` 和 `latest_version`。
4. 过滤出当前宿主可兼容的版本列表。
5. 选出最高的可兼容版本作为 `latest_compatible_version`。
6. 根据已安装版本和可兼容版本计算统一 `update_state`。

#### 2.3.2 手动升级流程

1. 用户在页面点击升级。
2. 前端提交 `household_id + plugin_id + source_id + target_version`。
3. 后端校验插件实例存在、来源一致、目标版本存在且兼容。
4. 复用现有下载、校验、解压和挂载能力安装目标版本。
5. 安装成功后保留原有启用状态和配置状态，除非兼容性检查明确要求降级。
6. 返回新的插件实例和统一版本治理结果。

#### 2.3.3 手动回滚流程

1. 用户在页面选择旧版本。
2. 后端校验该版本在当前市场条目中仍可识别且满足最小兼容约束。
3. 执行和升级相同的版本切换链路。
4. 安装成功后保留现有启停与配置，必要时将配置状态降级。
5. 返回新的插件实例和统一版本治理结果。

#### 2.3.4 升级后的状态保持流程

1. 升级前读取实例当前 `enabled`、`config_status` 和配置内容。
2. 版本切换完成后重新计算配置状态。
3. 若配置仍满足新版本要求，则保留原 `enabled`。
4. 若配置不满足，则把实例降级为 `unconfigured` 或 `invalid`，并在结果里明确原因。

## 3. 组件和接口

### 3.1 核心组件

覆盖需求：1、2、3、4、5、6

- `PluginVersionResolver`：负责解析和比较版本字符串，先支持最小可用规则
- `PluginCompatibilityResolver`：根据宿主版本和 `min_app_version` 过滤兼容版本
- `PluginVersionGovernanceService`：输出统一版本治理结果
- `PluginMarketplaceUpgradeService`：承接升级和回滚操作
- 前端版本状态组件：把升级状态、兼容性阻断和目标版本讲清楚

### 3.2 数据结构

覆盖需求：1、2、3、4、5

#### 3.2.1 `PluginVersionGovernanceRead`

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `source_type` | `string` | 是 | `builtin` / `marketplace` / `manual` | 稳定枚举 |
| `installed_version` | `string \| null` | 否 | 当前家庭已安装版本 | 市场插件从实例表读取 |
| `declared_version` | `string \| null` | 否 | 当前 manifest 或兼容源声明版本 | 非市场插件可只返回这个 |
| `latest_version` | `string \| null` | 否 | 市场条目声明的最新版本 | 市场插件可用 |
| `latest_compatible_version` | `string \| null` | 否 | 当前宿主下最高可兼容版本 | 由兼容性判断层计算 |
| `compatibility_status` | `string` | 是 | `compatible` / `host_too_old` / `unknown` | 稳定枚举 |
| `update_state` | `string` | 是 | 版本状态摘要 | 见 §4.2.1 |
| `blocked_reason` | `string \| null` | 否 | 当前不能升级的主要原因 | 人能看懂 |

#### 3.2.2 `PluginVersionOperationRequest`

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `household_id` | `string` | 是 | 家庭 ID | 非空 |
| `source_id` | `string` | 是 | 市场来源 ID | 非空 |
| `plugin_id` | `string` | 是 | 插件 ID | 非空 |
| `target_version` | `string` | 是 | 目标版本 | 必须存在于市场条目版本列表 |
| `operation` | `string` | 是 | `upgrade` / `rollback` | 稳定枚举 |

#### 3.2.3 `PluginVersionOperationResultRead`

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `instance` | `MarketplaceInstanceRead` | 是 | 操作后的插件实例 | 非空 |
| `governance` | `PluginVersionGovernanceRead` | 是 | 操作后的版本治理结果 | 非空 |
| `previous_version` | `string` | 是 | 操作前版本 | 非空 |
| `target_version` | `string` | 是 | 目标版本 | 非空 |
| `state_changed` | `bool` | 是 | 启停或配置状态是否变化 | 非空 |
| `state_change_reason` | `string \| null` | 否 | 若发生状态降级，说明原因 | 人能看懂 |

### 3.3 接口契约

覆盖需求：1、2、3、4、5

#### 3.3.1 查询插件版本治理结果

- 类型：HTTP
- 路径或标识：`GET /api/plugin-marketplace/catalog/{source_id}/{plugin_id}/version-governance`
- 输入：`household_id`、`source_id`、`plugin_id`
- 输出：`PluginVersionGovernanceRead`
- 校验：插件必须存在；若插件不受市场管理，返回统一不可比较状态
- 错误：`404/marketplace_entry_not_found`、`409/plugin_source_mismatch`

#### 3.3.2 手动升级或回滚插件

- 类型：HTTP
- 路径或标识：`POST /api/plugin-marketplace/instances/{instance_id}/version-operations`
- 输入：`PluginVersionOperationRequest`
- 输出：`PluginVersionOperationResultRead`
- 校验：
  - 目标版本必须存在
  - 目标版本必须满足当前宿主兼容性
  - 升级和回滚都只能在同一市场来源内执行
- 错误：
  - `409/plugin_version_incompatible`
  - `409/plugin_version_not_found`
  - `409/plugin_source_mismatch`

#### 3.3.3 市场目录版本字段扩展

- 类型：HTTP
- 路径或标识：沿用 `GET /api/plugin-marketplace/catalog`
- 输入：`household_id`
- 输出：在现有 `MarketplaceCatalogItemRead` 上补版本治理结果
- 校验：目录查询不应因为某条版本治理计算失败而整体失败
- 错误：局部失败降级为空字段，不拖垮整个目录

## 4. 数据与状态模型

### 4.1 数据关系

这次必须把数据真相钉死：

1. 市场条目定义“市场有哪些版本可选”
2. 插件实例定义“当前家庭实际装的是哪个版本”
3. manifest 定义“当前落盘代码自称是什么版本”
4. 宿主版本定义“哪些市场版本当前允许安装”

这里最重要的原则是：

不要再新增一张“插件版本状态表”去重复存派生结果。

因为 `latest_compatible_version`、`update_state`、`compatibility_status` 这些东西，本质上都是从已有事实算出来的。把派生结果再存一遍，只会制造第二套真相。

### 4.2 状态流转

#### 4.2.1 `update_state`

| 状态 | 含义 | 进入条件 | 退出条件 |
| --- | --- | --- | --- |
| `up_to_date` | 已安装版本就是当前最新可兼容版本 | `installed_version == latest_compatible_version` | 市场有更高兼容版本或已安装版本变化 |
| `upgrade_available` | 存在更高的可兼容版本 | `latest_compatible_version > installed_version` | 升级完成或兼容条件变化 |
| `upgrade_blocked` | 市场有更新，但当前宿主不兼容最新版本 | `latest_version > latest_compatible_version` 且已安装版本已到兼容上限 | 宿主升级或市场版本变化 |
| `installed_newer_than_market` | 当前已安装版本比市场可见版本更高或不在目录里 | 已安装版本无法在市场目录里匹配 | 市场目录修复或版本切换 |
| `not_market_managed` | 插件不受市场版本治理 | 内置插件、兼容源插件等 | 接入市场治理后 |
| `unknown` | 当前信息不足，无法得出可靠结论 | 缺少已安装版本或缺少市场版本信息 | 信息补齐后 |

#### 4.2.2 版本切换操作状态

| 状态 | 含义 | 进入条件 | 退出条件 |
| --- | --- | --- | --- |
| `validating_target` | 正在校验目标版本是否存在且兼容 | 用户发起升级或回滚 | 通过或失败 |
| `switching_version` | 正在下载、校验、解压和挂载目标版本 | 校验通过 | 成功或失败 |
| `rechecking_config` | 正在重新评估配置状态 | 挂载完成 | 配置状态稳定 |
| `completed` | 版本切换成功 | 所有步骤通过 | 再次操作 |
| `failed` | 版本切换失败 | 任一步骤失败 | 用户重新发起操作 |

## 5. 错误处理

### 5.1 错误类型

- `plugin_version_incompatible`：目标版本与当前宿主版本不兼容
- `plugin_version_not_found`：目标版本不在市场条目里
- `plugin_source_mismatch`：当前插件实例和目标来源不一致
- `plugin_version_governance_unavailable`：当前版本治理信息不足
- `plugin_version_switch_failed`：版本切换过程失败
- `plugin_config_revalidation_failed`：版本切换后配置重新校验失败

### 5.2 错误响应格式

```json
{
  "detail": "目标版本要求更高的宿主版本，当前不能升级。",
  "error_code": "plugin_version_incompatible",
  "field": "target_version",
  "timestamp": "2026-03-17T00:00:00Z"
}
```

### 5.3 处理策略

1. 目标版本不存在：直接拒绝，不进入下载阶段。
2. 目标版本不兼容：直接拒绝，并返回兼容性阻断原因。
3. 版本切换失败：保留失败前实例信息，不清空旧版本状态。
4. 配置重新校验失败：版本切换成功，但插件状态降级为 `unconfigured` 或 `invalid`，禁止继续执行。

## 6. 正确性属性

### 6.1 属性 1：版本真相单一

*对于任何* 市场管理插件，系统都应该满足：当前家庭插件的已安装版本只由插件实例记录和当前落盘 manifest 共同定义，而不是由前端或其他模块自行推断。

**验证需求：** 需求 1、需求 4

### 6.2 属性 2：不兼容版本永不落盘

*对于任何* 手动安装、升级或回滚操作，系统都应该满足：如果目标版本和当前宿主版本不兼容，就不能进入真正的下载和挂载阶段。

**验证需求：** 需求 2、需求 3

### 6.3 属性 3：升级不破坏用户空间

*对于任何* 同源版本切换操作，系统都应该满足：默认保留现有启停和配置状态；只有在明确检测到不兼容时，才允许状态降级。

**验证需求：** 需求 4

## 7. 测试策略

### 7.1 单元测试

- 版本解析和比较
- `min_app_version` 兼容性判断
- `latest_compatible_version` 选择逻辑
- `update_state` 状态归类

### 7.2 集成测试

- 安装时遇到宿主版本过低的阻断
- 手动升级到兼容版本
- 手动回滚到旧版本
- 升级后保留启用状态
- 升级后配置失效时状态降级

### 7.3 端到端测试

- 市场页展示已安装版本、最新版本、最新可兼容版本
- 市场页触发升级并看到成功结果
- 市场页因宿主版本不足而阻断升级
- 插件详情页展示统一版本治理结果

### 7.4 验证映射

| 需求 | 设计章节 | 验证方式 |
| --- | --- | --- |
| `requirements.md` 需求 1 | `design.md` §2.3.1、§3.2.1、§4.1 | 单元测试、接口测试 |
| `requirements.md` 需求 2 | `design.md` §2.3.2、§5.1、§6.2 | 集成测试 |
| `requirements.md` 需求 3 | `design.md` §2.3.2、§2.3.3、§3.3.2 | 集成测试、端到端测试 |
| `requirements.md` 需求 4 | `design.md` §2.3.4、§4.1、§6.3 | 集成测试 |
| `requirements.md` 需求 5 | `design.md` §2.1、§3.3.3、§4.2.1 | 前端联调、端到端测试 |
| `requirements.md` 需求 6 | `design.md` §1.4、§8.2 | 文档走查 |

## 8. 风险与待确认项

### 8.1 风险

- 当前项目还没有完整 semver 规则，如果一开始就把版本比较做得太激进，很容易误判。
- 现在插件实例唯一键还是 `household_id + plugin_id`，这意味着同一插件 ID 不能多源并存，版本治理必须接受这个现实边界。
- 如果升级继续沿用“首次安装后默认禁用”的语义，会直接破坏现有用户空间。

### 8.2 待确认项

- 版本比较第一阶段是否只支持点分数字版本，还是要兼容更多预发布标记。
- 回滚是否只允许回到市场条目里仍然存在的历史版本，还是允许回到本地已缓存但市场已移除的版本。
- 配置兼容性第一阶段是否只依赖现有 `config_status` 重算，还是要引入显式 schema 版本迁移规则。
