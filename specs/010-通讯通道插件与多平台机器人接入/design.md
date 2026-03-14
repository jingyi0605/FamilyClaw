# 设计文档 - 通讯通道插件与多平台机器人接入

状态：Draft

## 1. 概述

### 1.1 目标

- 给现有插件系统补一类正式的“通讯通道插件”，把聊天平台接入从特例变成标准能力
- 复用现有 `conversation` 主链，让外部平台和网页对话共享同一套脑子
- 把平台账号配置、成员绑定、外部会话映射、入站事件、出站投递做成可追踪、可观测的数据链

### 1.2 覆盖需求

- `requirements.md` 需求 1
- `requirements.md` 需求 2
- `requirements.md` 需求 3
- `requirements.md` 需求 4
- `requirements.md` 需求 5
- `requirements.md` 需求 6
- `requirements.md` 需求 7

### 1.3 技术约束

- 后端：`FastAPI + SQLAlchemy + Alembic`
- 前端：`user-web React + TypeScript`
- 数据存储：当前主数据库，结构变更只能走 `Alembic`
- 认证授权：沿用当前 `admin actor / bound member actor` 边界
- 外部依赖：
  - OpenClaw 官方渠道实现思路
  - `openclaw-china` 的钉钉和企业微信扩展思路

### 1.4 关键设计判断

- 不把聊天平台继续塞进现有 `connector`
- 新增正式的 `channel` 插件类型
- 外部平台只负责“进出站”，AI 决策继续由现有对话主链负责
- `企业微信` 优先 `wecom-app`，`wecom` 机器人模式后补
- 平台配置接口沿用当前项目的家庭级配置风格，优先挂在 `ai-config/{household_id}` 下面，由 `user-web` 设置页消费
- 平台 webhook 入口单独建 router，不混进 `conversations` 或 `plugin_jobs`

## 2. 架构

### 2.1 系统结构

系统分成五层：

1. 平台接入层
   - 接 webhook、轮询事件、平台签名校验、机器人状态探测
2. 通道编排层
   - 标准化入站事件、查成员绑定、做会话映射、投递出站消息
3. 现有对话主链
   - 继续负责 session、turn、agent、memory、proposal、action
4. 管理与观测层
   - 平台账号配置、成员绑定、失败列表、投递记录
5. 平台插件实现层
   - 每个平台自己的回调适配、目标解析、发送消息、状态探测

### 2.2 模块职责

| 模块 | 职责 | 输入 | 输出 |
| --- | --- | --- | --- |
| 通道插件注册层 | 注册 `channel` 插件、校验 manifest、提供运行入口 | 插件 manifest、插件 entrypoint | 可执行的通道插件定义 |
| 平台账号服务 | 管理平台机器人账号配置、启停、探测状态 | 管理员请求、平台配置 | 平台账号记录、状态摘要 |
| 成员绑定服务 | 管理成员与平台账号映射 | 成员 ID、平台类型、外部账号 | 绑定记录 |
| 通道事件服务 | 记录入站事件、做幂等去重、串起处理链路 | 平台回调、标准化事件 | 入站事件记录、处理结果 |
| 通道会话映射服务 | 把平台会话映射为内部 conversation session | 平台会话键、member_id、agent 策略 | 内部 session 绑定 |
| 通道出站服务 | 把 AI 输出送回平台并记录结果 | 内部回复、平台目标、插件发送器 | 出站投递记录 |
| 用户端通讯平台接入页 | 配置平台账号、绑定成员、查看状态 | API 响应 | `user-web` 里的正式管理入口 |

### 2.3 关键流程

#### 2.3.1 管理员在 `user-web` 设置页配置平台账号

1. 管理员在 `user-web` 设置界面的“通讯平台接入”页面新增平台账号
2. 后端校验平台类型、密钥、回调参数和唯一性
3. 系统保存平台账号记录
4. 系统执行一次状态探测或校验
5. 设置页展示账号状态和最近错误

#### 2.3.2 管理员在通讯平台接入页为平台账号配置成员绑定

1. 管理员进入 `user-web` 的“通讯平台接入”页面
2. 用户端展开某个平台账号详情，读取该账号下现有绑定
3. 管理员选择家庭成员，并填写该成员在此平台账号下对应的外部用户标识
4. 后端校验该平台账号是否属于当前家庭、该外部标识是否冲突
5. 系统保存绑定结果并记录审计日志

#### 2.3.3 外部平台消息入站

1. 平台把消息推送到统一 webhook 入口或对应通道入口
2. 系统找到对应平台账号和通道插件
3. 通道插件校验签名、解包消息并标准化为统一入站事件
4. 系统按平台账号和外部用户标识查成员绑定
5. 系统按平台会话键查或建内部会话映射
6. 系统复用现有 `conversation` 主链创建 turn
7. 系统保存入站事件处理结果

#### 2.3.4 AI 回复原路返回

1. 现有对话主链生成 assistant 输出
2. 通道编排层把内部输出转换成通用出站消息
3. 通道插件根据平台能力发送文本或平台原生消息
4. 系统记录投递结果、平台消息引用和失败原因
5. 用户端页面可查看最近投递与失败

#### 2.3.5 平台状态探测与降级

1. 管理员手动探测或系统定时探测平台账号
2. 通道插件返回探测结果
3. 系统刷新平台账号状态
4. 连续失败达到阈值时标记为 `degraded`
5. 通讯平台接入页显示失败摘要，避免黑盒

### 2.4 建议文件结构

后端建议按当前项目现有模块风格新增 `channel` 模块，不要把实现散落到 `plugin`、`conversation` 和 `realtime` 里。

建议新增这些文件：

- `apps/api-server/app/modules/channel/models.py`
- `apps/api-server/app/modules/channel/repository.py`
- `apps/api-server/app/modules/channel/schemas.py`
- `apps/api-server/app/modules/channel/service.py`
- `apps/api-server/app/modules/channel/account_service.py`
- `apps/api-server/app/modules/channel/binding_service.py`
- `apps/api-server/app/modules/channel/gateway_service.py`
- `apps/api-server/app/modules/channel/conversation_bridge.py`
- `apps/api-server/app/modules/channel/delivery_service.py`
- `apps/api-server/app/modules/channel/status_service.py`
- `apps/api-server/app/modules/channel/__init__.py`

建议新增这些 API 文件：

- `apps/api-server/app/api/v1/endpoints/channel_accounts.py`
- `apps/api-server/app/api/v1/endpoints/channel_gateways.py`

建议修改这些现有文件：

- `apps/api-server/app/api/v1/router.py`
- `apps/api-server/app/db/models.py`
- `apps/api-server/app/modules/plugin/schemas.py`
- `apps/api-server/app/modules/plugin/service.py`
- `apps/api-server/app/modules/conversation/service.py`

建议新增这些内置平台插件目录：

- `apps/api-server/app/plugins/builtin/channel_telegram/`
- `apps/api-server/app/plugins/builtin/channel_discord/`
- `apps/api-server/app/plugins/builtin/channel_feishu/`
- `apps/api-server/app/plugins/builtin/channel_dingtalk/`
- `apps/api-server/app/plugins/builtin/channel_wecom_app/`
- `apps/api-server/app/plugins/builtin/channel_wecom_bot/`

用户端建议新增这些页面或组件：

- `apps/user-web/src/pages/SettingsPage.tsx`（在“设备与集成”下方新增“通讯平台接入”页面，沿用现有主题和设置页结构）
- `apps/user-web/src/components/SettingsNav.tsx`
- `apps/user-web/src/components/ChannelAccountBindingsPanel.tsx`
- `apps/user-web/src/lib/api.ts`
- `apps/user-web/src/lib/types.ts`

## 3. 组件和接口

### 3.1 核心组件

覆盖需求：1、2、3、4、5、6、7

- `ChannelPluginManifest`
  - 定义通道插件的插件类型、entrypoint、支持能力、平台代码
- `ChannelAccountService`
  - 管理平台机器人账号配置和状态
- `MemberChannelBindingService`
  - 管理成员与外部平台账号绑定
- `ChannelGatewayService`
  - 处理回调、标准化事件、进入内部会话
- `ChannelConversationBridge`
  - 复用现有 `conversation` 服务，不另起一套聊天内核
- `ChannelDeliveryService`
  - 管理出站投递、重试和日志

同时需要扩展现有插件声明：

- `PluginType`
  - 新增 `channel`
- `PluginManifestType`
  - 新增 `channel`
- `PluginManifestEntrypoints`
  - 新增 `channel`
- `PluginManifestCapabilities`
  - 新增 `channel` 能力声明

建议新增一个 `PluginManifestChannelSpec`，至少包含：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `platform_code` | `str` | 平台代码，如 `telegram` |
| `inbound_modes` | `list[str]` | 支持的入站模式，如 `webhook`、`polling`、`websocket` |
| `delivery_modes` | `list[str]` | 支持的出站模式，如 `reply`、`push` |
| `supports_member_binding` | `bool` | 是否支持成员绑定 |
| `supports_group_chat` | `bool` | 是否支持群聊 |
| `supports_threading` | `bool` | 是否支持线程或话题 |
| `reserved` | `bool` | 保留字段，沿用当前 region-provider 风格 |

### 3.2 数据结构

覆盖需求：2、3、4、5、6

#### 3.2.1 `channel_plugin_accounts`

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `id` | `text` | 是 | 平台账号主键 | 主键 |
| `household_id` | `text` | 是 | 所属家庭 | 外键 |
| `plugin_id` | `varchar(64)` | 是 | 对应通道插件 ID | 索引 |
| `platform_code` | `varchar(32)` | 是 | 平台代码，如 `telegram` | 索引 |
| `account_code` | `varchar(64)` | 是 | 家庭内账号唯一代码 | 家庭内唯一 |
| `display_name` | `varchar(100)` | 是 | 后台显示名 | 非空 |
| `connection_mode` | `varchar(32)` | 是 | `webhook` / `polling` / `websocket` | 非空 |
| `config_json` | `text` | 是 | 平台配置 | JSON |
| `status` | `varchar(20)` | 是 | `draft` / `active` / `degraded` / `disabled` | 索引 |
| `last_probe_status` | `varchar(20)` | 否 | 最近探测结果 | 可空 |
| `last_error_code` | `varchar(100)` | 否 | 最近错误码 | 可空 |
| `last_error_message` | `text` | 否 | 最近错误说明 | 可空 |
| `last_inbound_at` | `text` | 否 | 最近入站时间 | 可空 |
| `last_outbound_at` | `text` | 否 | 最近出站时间 | 可空 |
| `created_at` | `text` | 是 | 创建时间 | 非空 |
| `updated_at` | `text` | 是 | 更新时间 | 非空 |

#### 3.2.2 `member_channel_bindings`

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `id` | `text` | 是 | 绑定主键 | 主键 |
| `household_id` | `text` | 是 | 所属家庭 | 外键 |
| `member_id` | `text` | 是 | 家庭成员 | 外键、索引 |
| `channel_account_id` | `text` | 是 | 平台账号 | 外键、索引 |
| `platform_code` | `varchar(32)` | 是 | 平台代码 | 索引 |
| `external_user_id` | `varchar(255)` | 是 | 平台用户主标识 | 家庭+平台+用户唯一 |
| `external_chat_id` | `varchar(255)` | 否 | 需要时保留平台会话侧标识 | 可空 |
| `display_hint` | `varchar(255)` | 否 | 后台识别备注 | 可空 |
| `binding_status` | `varchar(20)` | 是 | `active` / `disabled` | 索引 |
| `created_at` | `text` | 是 | 创建时间 | 非空 |
| `updated_at` | `text` | 是 | 更新时间 | 非空 |

#### 3.2.3 `channel_conversation_bindings`

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `id` | `text` | 是 | 映射主键 | 主键 |
| `household_id` | `text` | 是 | 所属家庭 | 外键 |
| `channel_account_id` | `text` | 是 | 平台账号 | 外键 |
| `platform_code` | `varchar(32)` | 是 | 平台代码 | 索引 |
| `external_conversation_key` | `varchar(255)` | 是 | 平台会话键，统一后字符串 | 家庭+账号+键唯一 |
| `external_user_id` | `varchar(255)` | 否 | 发起人平台用户标识 | 可空 |
| `member_id` | `text` | 否 | 已解析的内部成员 | 外键、可空 |
| `conversation_session_id` | `text` | 是 | 内部会话 ID | 外键 |
| `active_agent_id` | `text` | 否 | 当前映射使用的 agent | 可空 |
| `last_message_at` | `text` | 是 | 最近消息时间 | 非空 |
| `status` | `varchar(20)` | 是 | `active` / `archived` / `disabled` | 索引 |
| `created_at` | `text` | 是 | 创建时间 | 非空 |
| `updated_at` | `text` | 是 | 更新时间 | 非空 |

#### 3.2.4 `channel_inbound_events`

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `id` | `text` | 是 | 入站事件主键 | 主键 |
| `household_id` | `text` | 是 | 所属家庭 | 外键 |
| `channel_account_id` | `text` | 是 | 平台账号 | 外键 |
| `platform_code` | `varchar(32)` | 是 | 平台代码 | 索引 |
| `external_event_id` | `varchar(255)` | 是 | 平台事件唯一标识 | 家庭+账号+事件唯一 |
| `event_type` | `varchar(50)` | 是 | `message` / `callback` 等 | 索引 |
| `external_user_id` | `varchar(255)` | 否 | 平台用户 ID | 可空 |
| `external_conversation_key` | `varchar(255)` | 否 | 平台会话键 | 可空 |
| `normalized_payload_json` | `text` | 是 | 标准化事件载荷 | JSON |
| `status` | `varchar(20)` | 是 | `received` / `matched` / `dispatched` / `ignored` / `failed` | 索引 |
| `conversation_session_id` | `text` | 否 | 内部会话 ID | 可空 |
| `error_code` | `varchar(100)` | 否 | 错误码 | 可空 |
| `error_message` | `text` | 否 | 错误信息 | 可空 |
| `received_at` | `text` | 是 | 接收时间 | 非空 |
| `processed_at` | `text` | 否 | 处理完成时间 | 可空 |

#### 3.2.5 `channel_deliveries`

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `id` | `text` | 是 | 投递主键 | 主键 |
| `household_id` | `text` | 是 | 所属家庭 | 外键 |
| `channel_account_id` | `text` | 是 | 平台账号 | 外键 |
| `platform_code` | `varchar(32)` | 是 | 平台代码 | 索引 |
| `conversation_session_id` | `text` | 否 | 对应内部会话 | 可空 |
| `assistant_message_id` | `text` | 否 | 对应内部 assistant 消息 | 可空 |
| `external_conversation_key` | `varchar(255)` | 是 | 平台目标会话 | 非空 |
| `delivery_type` | `varchar(30)` | 是 | `reply` / `notice` / `error` | 非空 |
| `request_payload_json` | `text` | 是 | 待发送内容 | JSON |
| `provider_message_ref` | `varchar(255)` | 否 | 平台返回的消息 ID | 可空 |
| `status` | `varchar(20)` | 是 | `pending` / `sent` / `failed` / `skipped` | 索引 |
| `attempt_count` | `int` | 是 | 已尝试次数 | 默认 0 |
| `last_error_code` | `varchar(100)` | 否 | 最近错误码 | 可空 |
| `last_error_message` | `text` | 否 | 最近错误信息 | 可空 |
| `created_at` | `text` | 是 | 创建时间 | 非空 |
| `updated_at` | `text` | 是 | 更新时间 | 非空 |

#### 3.2.6 与现有表的关联字段约束

第一版不建议修改现有 `conversation_sessions` 和 `conversation_messages` 表结构来塞平台字段，避免把平台细节污染核心会话表。

第一版追踪关系统一这样做：

- 外部入站到内部会话：`channel_inbound_events.conversation_session_id`
- 内部 assistant 到外部投递：`channel_deliveries.assistant_message_id`
- 外部会话到内部会话：`channel_conversation_bindings.conversation_session_id`

如果后续确实需要把“消息来源平台”直接展示到聊天消息列表，再单独补一次 migration，而不是现在提前埋一堆字段。

### 3.3 接口契约

覆盖需求：2、3、4、5、6

#### 3.3.1 平台账号管理接口

- 类型：HTTP
- 路径：
  - `GET /api/v1/ai-config/{household_id}/channel-accounts`
  - `POST /api/v1/ai-config/{household_id}/channel-accounts`
  - `PUT /api/v1/ai-config/{household_id}/channel-accounts/{account_id}`
  - `POST /api/v1/ai-config/{household_id}/channel-accounts/{account_id}/probe`
  - `GET /api/v1/ai-config/{household_id}/channel-accounts/{account_id}/status`
  - `GET /api/v1/ai-config/{household_id}/channel-deliveries?channel_account_id={account_id}&status=failed`
  - `GET /api/v1/ai-config/{household_id}/channel-inbound-events?channel_account_id={account_id}&status=failed`
- 输入：
  - 家庭 ID
  - 平台类型
  - 插件 ID
  - 连接方式
  - 平台专属配置
- 输出：
  - 平台账号详情
  - 最近探测状态
  - 最近错误摘要
  - 最近入站 / 出站失败记录
- 校验：
  - 只允许管理员访问
  - 平台配置字段必须匹配该平台插件定义
- 错误：
  - 配置不合法
  - 平台账号重复
  - 插件不存在或不是 `channel` 类型

建议对应文件：

- `apps/api-server/app/api/v1/endpoints/channel_accounts.py`
- `apps/api-server/app/modules/channel/account_service.py`

#### 3.3.1.1 `user-web` 通讯平台接入页路由与信息结构

这页不要继续塞进现有“设备与集成”正文里，而是作为设置页里的独立子路由。原因很简单：`Home Assistant` 已经占掉整页，再把平台账号配置、探测、失败记录混进去，只会做成一坨难维护的杂物间。

- 页面路由：
  - 路由名：`/settings/channel-access`
  - 页面组件名：`SettingsChannelAccess`
  - 导航位置：设置页二级导航中放在 `/settings/integrations` 后面，也就是“设备与集成”下方
  - 默认跳转：保持 `/settings` -> `/settings/appearance` 不变，不抢当前默认设置首页
- 页面结构：
  - 顶部说明卡
    - 说明这页负责平台机器人账号接入、成员绑定和失败排查
    - 明确“谁在平台上给 AI 发消息”就是在这里绑定，不再拆去家庭成员页
  - 平台账号列表区
    - 每个平台账号一张卡片
    - 卡片上直接展示平台、账号名、连接方式、账号状态、最近探测状态、最近错误摘要、最近入站时间、最近出站时间
    - 每张卡片提供 `编辑`、`立即探测`、`启用 / 停用` 三个动作
  - 新增 / 编辑账号弹窗
    - 统一复用一个弹窗
    - 基础字段固定，平台专属字段按 `config` 渲染
    - 创建成功后回到列表，不跳新页面
  - 账号详情抽屉或展开区
    - 展示 `GET .../status` 返回的最近失败摘要、最新投递、最新入站、最新失败入站
    - 同一区块内挂成员绑定面板，直接维护“家庭成员 <-> 外部通讯平台 ID”
    - 同时给一个“查看全部失败记录”入口，按当前账号筛到失败列表
  - 失败记录区
    - 默认展示该账号最近失败的投递记录和入站记录各 5 条
    - 第一版不做复杂筛选器，只保留“只看失败”这个固定视图
- 页面加载策略：
  - 首屏先调 `GET /channel-accounts`
  - 用户展开某个账号或刚完成探测后，再调 `GET /channel-accounts/{account_id}/status`
  - 用户展开某个账号详情时，同时调该账号的绑定列表
  - 点击“查看更多失败”时，再按账号调用 `GET /channel-deliveries` 和 `GET /channel-inbound-events`

#### 3.3.1.2 `user-web` 前端字段清单

前端字段不要自己发明。第一版就直接对齐后端现成 schema。

- 账号列表主数据：`ChannelAccountRead`

| 字段 | 类型 | 页面用途 |
| --- | --- | --- |
| `id` | `string` | 卡片主键、后续探测和编辑动作目标 |
| `household_id` | `string` | 当前家庭校验，前端一般不展示 |
| `plugin_id` | `string` | 平台插件标识，弹窗提交时回传 |
| `platform_code` | `string` | 展示平台类型，如 `telegram`、`discord` |
| `account_code` | `string` | 家庭内唯一账号编码，创建后不建议频繁修改 |
| `display_name` | `string` | 列表主标题，用户真正看见的账号名 |
| `connection_mode` | `webhook | polling | websocket` | 展示连接方式，也作为创建 / 编辑字段 |
| `config` | `Record<string, unknown>` | 平台专属配置，弹窗表单源数据 |
| `status` | `draft | active | degraded | disabled` | 账号状态徽标和启停动作依据 |
| `last_probe_status` | `string \| null` | 探测结果标签，如 `ok` / `failed` / `pending` |
| `last_error_code` | `string \| null` | 卡片错误摘要 |
| `last_error_message` | `string \| null` | 卡片错误摘要正文 |
| `last_inbound_at` | `string \| null` | 最近收到平台消息时间 |
| `last_outbound_at` | `string \| null` | 最近向平台发消息时间 |
| `created_at` | `string` | 详情区辅助信息 |
| `updated_at` | `string` | 详情区辅助信息 |

- 新建账号提交体：`ChannelAccountCreate`

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `plugin_id` | 是 | 直接决定平台类型 |
| `account_code` | 是 | 家庭内唯一编码，建议前端限制英文、数字、短横线 |
| `display_name` | 是 | 页面显示名称 |
| `connection_mode` | 是 | 当前后端只接受 `webhook` / `polling` / `websocket` |
| `config` | 是 | 平台专属配置对象，没有字段时也传空对象 |
| `status` | 否 | 默认传 `draft`，不建议创建时直接启用 |

- 编辑账号提交体：`ChannelAccountUpdate`

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `display_name` | 否 | 修改显示名称 |
| `connection_mode` | 否 | 修改连接方式 |
| `config` | 否 | 整体替换平台配置 |
| `status` | 否 | 用于启用 / 停用 |
| `last_probe_status` | 否 | 前端不主动提交，留给系统探测回写 |
| `last_error_code` | 否 | 前端不主动提交 |
| `last_error_message` | 否 | 前端不主动提交 |
| `last_inbound_at` | 否 | 前端不主动提交 |
| `last_outbound_at` | 否 | 前端不主动提交 |

- 账号详情状态数据：`ChannelAccountStatusRead`

| 字段 | 类型 | 页面用途 |
| --- | --- | --- |
| `account` | `ChannelAccountRead` | 详情头部复用账号基础信息 |
| `recent_failure_summary.channel_account_id` | `string` | 对齐当前账号 |
| `recent_failure_summary.platform_code` | `string` | 失败摘要标题 |
| `recent_failure_summary.recent_failure_count` | `number` | “最近失败次数”指标 |
| `recent_failure_summary.last_delivery_id` | `string \| null` | 最近失败投递定位 |
| `recent_failure_summary.last_error_code` | `string \| null` | 最近失败错误码 |
| `recent_failure_summary.last_error_message` | `string \| null` | 最近失败错误信息 |
| `recent_failure_summary.last_failed_at` | `string \| null` | 最近失败时间 |
| `latest_delivery` | `ChannelDeliveryRead \| null` | 最新一次出站记录 |
| `latest_inbound_event` | `ChannelInboundEventRead \| null` | 最新一次入站记录 |
| `latest_failed_inbound_event` | `ChannelInboundEventRead \| null` | 最新一次失败入站 |
| `recent_delivery_count` | `number` | 最近出站记录数 |
| `recent_inbound_count` | `number` | 最近入站记录数 |

- 失败记录列表数据
  - `GET /channel-deliveries` 使用 `ChannelDeliveryRead[]`
  - 重点展示字段：`delivery_type`、`status`、`provider_message_ref`、`attempt_count`、`last_error_code`、`last_error_message`、`created_at`、`updated_at`
  - `GET /channel-inbound-events` 使用 `ChannelInboundEventRead[]`
  - 重点展示字段：`external_event_id`、`event_type`、`external_user_id`、`status`、`error_code`、`error_message`、`received_at`、`processed_at`

#### 3.3.2 平台账号下的成员绑定管理接口

- 类型：HTTP
- 路径：
  - `GET /api/v1/ai-config/{household_id}/channel-accounts/{account_id}/bindings`
  - `POST /api/v1/ai-config/{household_id}/channel-accounts/{account_id}/bindings`
  - `PUT /api/v1/ai-config/{household_id}/channel-accounts/{account_id}/bindings/{binding_id}`
- 输入：
  - 家庭 ID
  - 平台账号 ID
  - 成员 ID
  - 外部用户标识
  - 绑定状态
- 输出：
  - 某个平台账号下的绑定列表
- 校验：
  - 成员和平台账号必须属于同一家庭
  - 同一家庭内同一平台外部用户标识不能重复绑定
- 错误：
  - 家庭不存在或无权限
  - 平台账号不存在
  - 成员不存在
  - 外部账号冲突

建议对应文件：

- `apps/api-server/app/api/v1/endpoints/channel_accounts.py`
  直接把绑定子路由挂在对应平台账号下面，数据方向最顺，不要再拆一套成员视角入口
- `apps/api-server/app/modules/channel/binding_service.py`

#### 3.3.2.1 绑定面板字段清单

绑定面板直接围绕“当前平台账号下有哪些外部 ID 绑定给了谁”来展示，不要再做成员页反查视角。

- 面板结构建议拆成 4 块：
  - 绑定列表区
    - 展示当前平台账号下已有绑定
    - 每行至少显示成员名、外部用户 ID、外部会话 ID、备注、绑定状态、更新时间
    - 每行提供 `编辑`、`停用 / 恢复` 动作
  - 新增 / 编辑绑定弹窗
    - 统一复用一个弹窗
    - 必填字段只有成员、`external_user_id`
    - `external_chat_id`、`display_hint` 保持可选
    - 编辑时允许改绑定状态，不单独再开第二个状态弹窗
  - 成员选择数据源
    - 直接读取当前家庭成员列表
    - 只允许选择当前家庭内有效成员
    - 第一版优先展示 `active` 成员，`inactive` 成员可隐藏或禁选，不要把停用成员混进默认候选
  - 绑定冲突提示
    - 当同一家庭内同平台同 `external_user_id` 已被别的成员占用时，前端要把冲突提示直接贴在表单里
    - 当账号未配置完成、绑定列表加载失败、保存失败时，也要在当前账号详情区给出可见提示，不要静默失败

- 列表数据：`MemberChannelBindingRead[]`

| 字段 | 类型 | 页面用途 |
| --- | --- | --- |
| `id` | `string` | 绑定主键 |
| `household_id` | `string` | 当前家庭校验，前端一般不展示 |
| `member_id` | `string` | 绑定到哪个家庭成员 |
| `channel_account_id` | `string` | 归属哪个平台账号 |
| `platform_code` | `string` | 展示平台类型 |
| `external_user_id` | `string` | 平台用户主标识，AI 识别消息来源的关键字段 |
| `external_chat_id` | `string \| null` | 平台会话侧标识，需要时辅助排查 |
| `display_hint` | `string \| null` | 管理员备注，如“妈妈私人号” |
| `binding_status` | `active | disabled` | 绑定是否生效 |
| `created_at` | `string` | 辅助信息 |
| `updated_at` | `string` | 辅助信息 |

- 创建提交体：`MemberChannelBindingCreate`

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `channel_account_id` | 是 | 当前详情页账号 ID，前端可隐式带入 |
| `external_user_id` | 是 | 平台用户主标识 |
| `external_chat_id` | 否 | 平台会话侧标识 |
| `display_hint` | 否 | 管理备注 |
| `binding_status` | 否 | 默认 `active` |

- 编辑提交体：`MemberChannelBindingUpdate`

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `external_user_id` | 否 | 修改平台用户主标识 |
| `external_chat_id` | 否 | 修改平台会话侧标识 |
| `display_hint` | 否 | 修改备注 |
| `binding_status` | 否 | 用于停用 / 恢复绑定 |

#### 3.3.3 平台入站统一入口

- 类型：HTTP / Event
- 路径示例：
  - `POST /api/v1/channel-gateways/accounts/{account_id}/webhook`
- 输入：
  - 原始平台回调头
  - 原始平台回调体
  - 平台签名、时间戳、token
- 输出：
  - 平台要求的确认响应
  - 系统侧的事件记录
- 校验：
  - 先做平台签名校验
  - 再做事件幂等去重
  - 再做成员绑定解析
- 错误：
  - 签名不合法
  - 平台账号禁用
  - 事件重复
  - 绑定未找到

建议对应文件：

- `apps/api-server/app/api/v1/endpoints/channel_gateways.py`
- `apps/api-server/app/modules/channel/gateway_service.py`

#### 3.3.4 通道到会话的内部桥接接口

- 类型：Function / Service
- 标识：`ChannelConversationBridge.handle_inbound_message`
- 输入：
  - 标准化入站消息
  - `member_id`
  - 平台会话键
  - 平台账号上下文
- 输出：
  - 内部 `conversation_session`
  - 新建或复用的 `turn`
  - 可投递的 assistant 输出
- 校验：
  - 只允许复用现有 `conversation` 服务
  - 不允许旁路调用简化问答接口替代正式会话
- 错误：
  - 会话创建失败
  - turn 创建失败
  - 会话权限冲突

建议对应文件：

- `apps/api-server/app/modules/channel/conversation_bridge.py`
- `apps/api-server/app/modules/conversation/service.py`

#### 3.3.5 平台出站投递接口

- 类型：Function / Job
- 标识：`ChannelDeliveryService.send_reply`
- 输入：
  - 平台账号
  - 外部会话键
  - assistant 输出
  - 平台消息上下文
- 输出：
  - 投递结果
  - 平台消息引用
- 校验：
  - 平台账号必须启用
  - 出站载荷必须符合平台能力约束
- 错误：
  - 目标无效
  - 平台限流
  - 平台网络失败

建议对应文件：

- `apps/api-server/app/modules/channel/delivery_service.py`
- `apps/api-server/app/modules/channel/status_service.py`

#### 3.3.6 平台状态与失败摘要接口

- 类型：HTTP
- 路径：
  - `GET /api/v1/ai-config/{household_id}/channel-accounts/{account_id}/status`
  - `GET /api/v1/ai-config/{household_id}/channel-deliveries`
  - `GET /api/v1/ai-config/{household_id}/channel-inbound-events`
- 输入：
  - 家庭 ID
  - 平台账号 ID
  - 可选筛选条件：`platform_code`、`status`、`created_from`、`created_to`
- 输出：
  - 平台状态摘要
  - 最近入站失败
  - 最近投递失败
- 校验：
  - 管理员可看全家庭
  - 非管理员第一版不开放这些观测接口
- 错误：
  - 平台账号不存在
  - 家庭权限不匹配

#### 3.3.7 `user-web` 建议使用的请求与响应命名

建议接口 schema 命名与现有风格保持一致：

- `ChannelAccountCreate`
- `ChannelAccountUpdate`
- `ChannelAccountRead`
- `ChannelAccountStatusRead`
- `MemberChannelBindingCreate`
- `MemberChannelBindingUpdate`
- `MemberChannelBindingRead`
- `ChannelInboundEventRead`
- `ChannelDeliveryRead`
- `ChannelGatewayWebhookAck`

不要发明另一套奇怪名字，比如 `ConnectorBotProfileDTO` 这种垃圾名。

### 3.4 Alembic 拆分建议

当前仓库最新 migration 编号已经到 `20260314_0028`。按现有风格，建议把通道能力拆成下面三步，而不是一个大 migration 把所有东西砸进去。

#### 3.4.1 `20260314_0029_create_channel_account_and_binding_tables.py`

这一步只建最基础的身份和配置层：

- `channel_plugin_accounts`
- `member_channel_bindings`

这样做完以后，管理员配置平台账号和成员绑定这条线就有了正式落点。

#### 3.4.2 `20260314_0030_create_channel_conversation_binding_and_event_tables.py`

这一步只建消息入站和会话映射层：

- `channel_conversation_bindings`
- `channel_inbound_events`

这样做完以后，外部消息怎么找到内部会话就能稳定落地。

#### 3.4.3 `20260314_0031_create_channel_delivery_tables.py`

这一步只建出站和观测层：

- `channel_deliveries`

这样做完以后，原路回复、失败摘要和重试依据就有正式表结构。

#### 3.4.4 为什么这样拆

- 先把“谁在用、替谁说话”落库
- 再把“消息怎么进来”落库
- 最后把“消息怎么出去”落库

这比一个大 migration 全塞进去更容易排错，也更符合当前项目已经在用的递进式迁移风格。

## 4. 数据与状态模型

### 4.1 数据关系

- 一个家庭可以配置多个平台账号
- 一个平台账号可以绑定多个成员
- 一个成员可以在多个平台各有一个或多个绑定
- 一个外部会话键稳定映射到一个内部 `conversation_session`
- 一条入站事件最多对应一次内部 turn
- 一条 assistant 消息可以对应一次或多次出站投递记录
- 一个平台账号探测失败不应该影响其他平台账号或其他家庭

### 4.2 状态流转

#### 4.2.1 平台账号状态

| 状态 | 含义 | 进入条件 | 退出条件 |
| --- | --- | --- | --- |
| `draft` | 配置已保存但未验证 | 新建账号 | 成功探测后进入 `active` |
| `active` | 可正常收发消息 | 探测成功或人工启用 | 连续失败进入 `degraded` 或人工停用 |
| `degraded` | 可配置但不稳定 | 探测失败或连续投递失败 | 再次探测成功或人工停用 |
| `disabled` | 明确停用 | 管理员停用 | 管理员重新启用 |

#### 4.2.2 入站事件状态

| 状态 | 含义 | 进入条件 | 退出条件 |
| --- | --- | --- | --- |
| `received` | 已收到原始事件 | 平台回调到达 | 标准化后继续处理 |
| `matched` | 已解析绑定和会话 | 成员绑定、会话映射成功 | 分发到内部主链 |
| `dispatched` | 已进入内部主链 | 成功创建或复用 turn | 等待投递完成 |
| `ignored` | 明确忽略 | 重复事件、未绑定且策略忽略 | 终态 |
| `failed` | 处理失败 | 任一关键步骤失败 | 终态 |

#### 4.2.3 出站投递状态

| 状态 | 含义 | 进入条件 | 退出条件 |
| --- | --- | --- | --- |
| `pending` | 待投递 | 生成待发消息 | 发送或跳过 |
| `sent` | 已发送成功 | 平台返回成功 | 终态 |
| `failed` | 发送失败 | 平台或网络失败 | 人工重试或终态保留 |
| `skipped` | 明确跳过发送 | 账号禁用、目标失效、策略禁止 | 终态 |

## 5. 错误处理

### 5.1 错误类型

- `channel_account_invalid_config`
  - 平台账号配置不完整或格式错误
- `channel_webhook_auth_failed`
  - 平台回调鉴权失败
- `channel_member_binding_not_found`
  - 找不到成员绑定
- `channel_session_binding_failed`
  - 外部会话映射失败
- `channel_delivery_failed`
  - 平台出站投递失败
- `channel_plugin_protocol_invalid`
  - 平台插件不符合通道协议

### 5.2 错误响应格式

```json
{
  "detail": "平台回调签名校验失败",
  "error_code": "channel_webhook_auth_failed",
  "field": null,
  "timestamp": "2026-03-14T00:00:00Z"
}
```

### 5.3 处理策略

1. 输入校验错误
   - 直接拒绝请求，不落半成状态
2. 平台回调鉴权错误
   - 返回平台要求的失败响应，并记录入站失败事件
3. 成员绑定缺失
   - 按家庭配置决定忽略、回固定提示或进入待绑定列表
4. 出站投递失败
   - 保留投递记录和错误信息，允许后续重试
5. 平台账号连续失败
   - 标记 `degraded`，在用户端突出显示

### 5.4 未绑定成员的默认策略建议

第一版建议默认策略不是“直接放过”，而是：

1. 私聊场景：
   - 回固定提示文案，告诉用户当前账号未绑定，请联系管理员
   - 同时保留一条 `channel_inbound_events` 记录，状态记为 `ignored`
2. 群聊场景：
   - 默认忽略
   - 只记录事件，不主动回复

这样最笨，但最清楚，也最不容易把系统搞出安全洞。

## 6. 正确性属性

### 6.1 同一外部会话必须稳定映射到同一内部会话

对于任何同一 `household + channel_account + external_conversation_key` 组合，系统都应该稳定复用同一个内部 `conversation_session`，除非管理员或策略明确要求重新建会话。

**验证需求：** 需求 4、需求 5

### 6.2 同一平台事件不能重复制造内部 turn

对于任何同一 `external_event_id`，系统都应该保证幂等处理，不能因为平台重复推送导致重复回复。

**验证需求：** 需求 4、需求 5，非功能需求 2

### 6.3 外部平台不能绕开现有 AI 主链

对于任何来自聊天平台的正式用户消息，系统都应该通过现有 `conversation` 主链处理，而不是旁路走另一个简化回答接口。

**验证需求：** 需求 4

## 7. 测试策略

### 7.1 单元测试

- 通道插件 manifest 校验
- 平台账号配置校验
- 成员绑定冲突校验
- 外部会话键归一化
- 入站事件幂等去重
- 出站状态流转

### 7.2 集成测试

- 平台账号配置到探测状态的完整链路
- 平台账号详情下的成员绑定创建、更新、停用链路
- 外部消息进入内部会话、生成回复、出站投递链路
- 同一外部事件重复推送的幂等链路
- 平台账号禁用、签名失败、未绑定成员等异常链路

### 7.3 端到端测试

- `Telegram` 文本消息往返
- `Discord` 文本消息往返
- `飞书` 文本消息往返
- 第二批平台接入后的 `钉钉` 和 `企业微信` 文本消息往返
- `user-web` 在通讯平台接入页配置平台账号、绑定成员、查看失败记录

### 7.4 验证映射

| 需求 | 设计章节 | 验证方式 |
| --- | --- | --- |
| `requirements.md` 需求 1 | `design.md` 3.1、3.3、6.3 | manifest 校验测试、插件注册测试 |
| `requirements.md` 需求 2 | `design.md` 2.3.1、3.2.1、3.3.1、4.2.1 | API 测试、`user-web` 联调 |
| `requirements.md` 需求 3 | `design.md` 2.3.2、3.2.2、3.3.2 | API 测试、冲突校验测试 |
| `requirements.md` 需求 4 | `design.md` 2.3.3、2.3.4、3.3.4、6.3 | 集成测试、端到端对话测试 |
| `requirements.md` 需求 5 | `design.md` 3.2.3、3.2.4、3.2.5、4.1、6.1、6.2 | 集成测试、幂等与映射测试 |
| `requirements.md` 需求 6 | `design.md` 2.2、3.3.1、3.3.2、5.3 | `user-web` 联调、页面回归 |
| `requirements.md` 需求 7 | `design.md` 1.4、2.3、8.2 | 任务评审、分批验收 |

## 8. 风险与待确认项

### 8.1 风险

- 各平台回调和签名模型差异很大，如果协议抽象过浅，后面还会回到平台特例代码
- 当前内部会话主链主要面向网页，外部平台消息的异步确认、超时、部分失败需要额外兜底
- 富媒体、卡片、线程这些平台能力差异巨大，第一版必须守住文本优先，否则范围会炸

### 8.2 当前平台落地边界

- `Telegram`
  - 当前已落地：webhook 文本消息、成员绑定解析、`conversation` 主链复用、文本原路回发、账号 probe
  - 当前明确不做：卡片、投票、复杂按钮、多媒体排版
- `Discord`
  - 当前已落地：interaction webhook 文本命令、签名校验、defer + followup 回发、账号 probe
  - 当前明确不做：普通频道消息通过 Gateway/WebSocket 直接进入主链
  - 原因：这需要补长期运行的 Discord Gateway/WebSocket 入站运行时，不是现有统一 HTTP webhook 入口顺手多写几行解析能解决的
- `飞书`
  - 当前已落地：明文 challenge、`encrypt` 加密回调解包、文本消息标准化、文本回发、账号 probe
  - 当前明确不做：复杂卡片、文档、审批流和群组高级事件
- `钉钉`
  - 当前已落地：统一 HTTP gateway 可消费的文本事件、`sessionWebhook` 原路回发、配置级 probe
  - 当前明确不做：常驻 `stream/websocket` 运行时
- `企业微信`
  - `wecom-app`
    - 当前已落地：回调握手、加密 XML 解包、文本入站、文本回发、凭证 probe
    - 当前明确不做：复杂群聊、菜单、审批事件
  - `wecom-bot`
    - 当前已落地：出站推送兼容边界、配置级 probe
    - 当前明确不做：双向用户消息入站

### 8.3 延期项与风险

- `Discord` 普通频道消息直连主链
  - 延期原因：需要补一层通道长连接运行时，涉及生命周期、异常恢复、状态探测，不适合混进当前 HTTP webhook 主线
- `钉钉` 常驻流式接入
  - 延期原因：当前先用 `sessionWebhook` 跑通文本闭环，后续再补真实运行时，避免先把范围炸开
- `企业微信群机器人` 双向接入
  - 延期原因：当前模式天然更适合作为出站通知通道，若要做成双向对话，需要重新设计入站来源与绑定边界
- 富媒体、卡片、审批和复杂群事件
  - 延期原因：五个平台能力差异过大，第一版继续守住文本优先，否则主链会被平台细节拖烂
