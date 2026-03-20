# 需求文档 - 插件系统 V1 定稿与全量迁移

状态：Done

## 2026-03-18 子 Spec 说明

这份需求文档负责插件系统 V1 的总需求。

AI 供应商彻底插件化迁移的细化需求已拆到：

- `specs/004.8.1-AI供应商彻底插件化迁移/requirements.md`

## 简介

FamilyClaw 现在已经有插件注册、启停、配置、任务、卡片、内置插件这些基础，但系统边界还没有真正定型。

真正的问题有三个：

- **文档边界没定型**：稳定规则、接口事实、示例、旧设计混在一起，开发者手册后续会越来越难维护。
- **宿主边界没定型**：宿主里还残留领域模块、旧插件语义和特判，违背“宿主只做平台内核”的方向。
- **插件落地没定型**：现有内置插件没有全部迁到统一模型，导致规范写一套、代码跑一套。

这次 Spec 要把这三个问题一起解决，形成真正可落地的插件系统 V1。

## 术语表

- **System**：FamilyClaw 插件平台、插件运行时、内置插件与开发者文档体系
- **宿主内核**：家庭、成员、权限、审计、设备/实体标准模型、插件运行时、卡片规范、记忆标准等平台能力
- **普通插件类型**：`integration`、`action`、`channel`、`agent-skill`、`ai-provider`、`region-provider`、`locale-pack`、`theme-pack`
- **独占槽位插件**：`memory_engine`、`memory_provider`、`context_engine`
- **开发者手册**：后续面向官方和第三方插件开发者的正式文档集合

## 范围说明

### In Scope

- 按 V1 规范重构插件相关 Spec 与开发者文档
- 建立“稳定规范 + 高频接口事实来源”两层文档结构
- 重构宿主插件类型体系、运行时入口、实例模型和标准 DTO 契约
- 重构记忆槽位型插件接入边界
- 迁移所有现有内置插件、官方插件到新架构
- 清理旧 `connector` / `memory-ingestor` 主语义与宿主领域特判

### Out of Scope

- 发布后兼容层设计
- 远程插件执行和代码沙箱
- 新增插件市场付费、签名、商业审核体系
- 顺手扩展天气、健康、家居等新的业务字段

## 需求

### 需求 1：插件开发文档必须收口成正式手册

**用户故事：** 作为官方维护者或插件开发者，我希望有一套长期稳定、结构清楚的插件开发者手册，以便后续新增插件或调整实现时，不用在一堆互相打架的文档里猜规则。

#### 验收标准

1. WHEN 开发者阅读官方插件文档 THEN System SHALL 先说明宿主与插件边界、正式插件类型、调用原则和禁止事项。
2. WHEN 文档涉及高频变化接口 THEN System SHALL 把稳定规则与接口表、调用示例分层维护，而不是在多份文档里重复复制。
3. WHEN 插件系统核心代码调整 THEN System SHALL 让开发者手册能映射到真实代码结构、真实接口和真实示例。
4. WHEN 第三方开发者按手册实现插件 THEN System SHALL 让其能明确知道 manifest 怎么写、入口怎么接、DTO 怎么产出、卡片和配置怎么接。

### 需求 2：宿主插件核心必须按 V1 规范收口

**用户故事：** 作为平台维护者，我希望宿主核心只保留平台级接口、运行时和标准模型，以便领域能力都通过插件接入，而不是继续堆回宿主。

#### 验收标准

1. WHEN 宿主识别插件类型 THEN System SHALL 使用 V1 正式类型体系和独占槽位体系，而不是继续把 `connector`、`memory-ingestor` 当主语义。
2. WHEN `integration` 类插件刷新状态 THEN System SHALL 通过统一实例、设备、实体、卡片快照和动作契约接入。
3. WHEN 记忆相关插件接入 THEN System SHALL 按 `memory_engine`、`memory_provider`、`context_engine` 槽位执行，并保留宿主的权限、可见性、修订和 fallback 主权。
4. WHEN 插件执行失败、禁用或配置错误 THEN System SHALL 继续遵守统一启停、错误语义、降级和后台任务规则。
5. WHEN 宿主加载核心数据库模型或执行宿主核心数据库迁移 THEN System SHALL NOT 将任何插件私有领域表注册到宿主核心 ORM 总模型入口，也 SHALL NOT 由宿主核心 Alembic migration 直接管理这些表。
6. WHEN 宿主读取设备、实体或仪表盘展示数据 THEN System SHALL 只消费标准设备与标准实体，SHALL NOT 按插件 id、平台或领域类型执行专用归一化。
7. WHEN `integration` 插件提交刷新结果 THEN System SHALL 要求插件直接产出完整标准实体，宿主只负责校验、去重、落库、关联和状态更新。
8. WHEN 宿主承接运行态标准实体 THEN System SHALL 将实体写入宿主公共标准实体承载层，SHALL NOT 再把 `DeviceBinding.capabilities.entities` 当成正式实体事实源。
9. WHEN `official` 或 `third_party` 插件目录缺失 THEN System SHALL 仍可完成宿主启动、数据库迁移和核心接口初始化。
10. WHEN 插件私有表需要建表、升级或删表 THEN System SHALL 使用插件私有迁移边界处理，而不是倒挂回宿主核心 Alembic 历史。
11. WHEN 插件产出仪表盘卡片 THEN System SHALL 只消费卡片 payload 里的标准可见字段，SHALL NOT 按某个插件的词典 key、卡片字段名或领域类型写宿主专用渲染分支。
12. WHEN 卡片 payload 包含用户可见文案 THEN System SHALL 要求插件通过 `label`、`label_key`、`value_display`、`value_type` 等标准字段传递，SHALL NOT 允许宿主把插件词典 key 原样显示给用户。

### 需求 3：现有内置插件和官方插件必须全量迁移

**用户故事：** 作为系统维护者，我希望仓库里的现有插件全部改到新架构，以便规范、代码和实际运行模型一致，不再并存两套设计。

#### 验收标准

1. WHEN 检查现有内置插件 THEN System SHALL 将状态型插件统一迁为 `integration`，将通道插件统一迁为 `channel`，将资源包统一迁为 `locale-pack`。
2. WHEN 检查带控制能力的插件 THEN System SHALL 把控制能力收口到 `action` 或 `integration + action`，不再混用旧执行入口。
3. WHEN 检查记忆相关输出 THEN System SHALL 统一改为调用宿主标准记忆写入接口，而不是保留旧 `memory-ingestor` 语义。
4. WHEN 迁移完成 THEN System SHALL 清理宿主和插件目录中的旧主语义、旧分支和明显过时的字段命名。
5. WHEN 历史官方插件语义迁移完成 THEN System SHALL 使用 `apps/api-server/plugins-dev/` 作为仓库内开发源码目录，并使用 `data/plugins/third_party/marketplace/` 作为市场安装运行时目录，SHALL NOT 再依赖 `apps/api-server/data/plugins/official/`。
6. WHEN 宿主源码被导入、执行迁移或启动应用 THEN System SHALL NOT 静态 import `official` 或 `third_party` 插件模块。
7. WHEN 插件需要持久化领域私有状态 THEN System SHALL 使用插件私有表或插件私有存储边界，SHALL NOT 倒挂到宿主核心模型，也 SHALL NOT 倒挂到宿主核心 Alembic migration。

## 非功能需求

### 非功能需求 1：可维护性

1. WHEN 后续新增插件类型字段或接口 THEN System SHALL 优先改事实来源文档和接口表，而不是重写整套手册。
2. WHEN 开发者排查插件问题 THEN System SHALL 能让文档、manifest、运行时代码和测试入口互相对上。

### 非功能需求 2：一致性

1. WHEN 插件类型、槽位名、配置作用域、DTO 字段被定义 THEN System SHALL 在规范文档、开发者手册和核心代码里保持一致命名。
2. WHEN 系统导出设备、实体、卡片、动作和记忆接口 THEN System SHALL 让不同插件遵守同一标准，而不是各造一套协议。

### 非功能需求 3：可靠性

1. WHEN 插件刷新、调度、动作执行或槽位调用失败 THEN System SHALL 保持可观测、可降级、可恢复，不允许直接把对话主链路或状态读取打断。
2. WHEN 内置插件全量迁移 THEN System SHALL 保持插件启停、配置、后台任务和错误状态规则一致。

## 成功定义

- 宿主、插件、记忆槽位三层边界被文档和代码同时收口
- 官方开发者手册可以直接作为后续插件接入的唯一主入口
- 仓库里的现有内置插件不再保留旧主语义
- 之后新增天气、电费、健康、设备状态类能力时，不再默认往宿主里写领域模块
