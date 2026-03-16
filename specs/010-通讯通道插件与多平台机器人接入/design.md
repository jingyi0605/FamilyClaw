# 设计文档 - 通讯通道插件与多平台机器人接入

状态：Draft

## 1. 设计目标

这份设计文档现在只收两件核心事：

1. 把聊天平台接入收成正式 `channel` 插件能力
2. 把通道账号配置从“页面硬编码字段”改成“正式插件配置协议 + 通用动态表单”

也就是说，这份 Spec 现在不能再把通道配置当成一堆页面特例来写。

## 2. 关键判断

### 2.1 正式插件类型

- 聊天平台接入不再继续塞进 `connector`
- 通讯通道是正式 `channel` 插件类型

### 2.2 AI 主链不变

- 外部平台负责进出站
- AI 决策继续复用现有 `conversation` 主链

### 2.3 配置事实来源已经变化

这条必须写死：

- 通道账号配置的正式字段来源，是通道插件 `manifest.config_specs`
- `channel_account` 是这轮正式支持的作用域
- 读取和保存都走统一插件配置 API

下面这些东西不再是正式事实来源：

- `SettingsChannelAccessPage` 里的平台字段常量
- 页面里的硬编码 widget 选择
- `channel_plugin_accounts.config_json` 里的旧字段定义

## 3. 配置协议在通道体系里的位置

### 3.1 manifest 声明

通道插件如果需要让用户配置账号参数，必须在 manifest 里声明：

- `config_specs`

每个通道账号配置项至少包含：

- `scope_type: channel_account`
- `schema_version`
- `config_schema`
- `ui_schema`

如果插件还需要插件级配置，可以另外声明：

- `scope_type: plugin`

### 3.2 正式支持的作用域

这轮通道体系只承认两种正式配置作用域：

- `plugin`
- `channel_account`

不要在通道模块里自己再发明第三层作用域。

### 3.3 secret 语义

通道插件经常涉及 token、secret、webhook key，这里必须统一：

1. secret 字段读取时绝不回显明文
2. 保存时没提交某个 secret 字段，表示保留原值
3. 要清空 secret，必须显式走 `clear_secret_fields`

## 4. 数据模型怎么落

### 4.1 `plugin_config_instances`

正式配置实例统一保存在插件配置实例表里。

通道账号配置实例的唯一键是：

- `household_id + plugin_id + scope_type + scope_key`

其中：

- `scope_type = channel_account`
- `scope_key = <channel_account_id>`

### 4.2 `channel_plugin_accounts`

`channel_plugin_accounts` 继续保留，但角色变了。

它现在负责：

- 通道账号身份
- 运行状态
- 最近探测和错误摘要
- 兼容运行链路需要的副本字段

它不再负责：

- 成为页面字段定义的唯一事实来源

尤其是：

- `config_json` 现在只是兼容运行时副本
- 真正的字段定义和正式配置实例，不在这里维护

如果文档还把 `config_json` 写成唯一来源，就是旧设计没删干净。

### 4.3 绑定和会话表

下面这些表的职责不变：

- `member_channel_bindings`
- `channel_conversation_bindings`
- `channel_inbound_events`
- `channel_deliveries`

它们继续负责：

- 成员绑定
- 外部会话到内部会话的映射
- 入站事件留痕
- 出站投递留痕

配置协议不会替代这些表，它只替代“字段定义和配置表单来源”那一层。

## 5. 后端接口边界

### 5.1 通道账号管理接口

通道账号的创建、编辑、探测、状态查询还继续走通道模块自己的接口。

这层负责：

- 创建账号记录
- 更新账号状态
- 执行 probe
- 查失败摘要

### 5.2 正式配置接口

通道账号的字段定义和配置读写，走统一插件配置接口：

- 获取插件可配置作用域
- 读取某个作用域的配置表单
- 保存某个作用域的配置

也就是说：

- “账号有没有”
- “账号状态是什么”

还是通道模块管。

但：

- “这个账号需要填哪些字段”
- “这些字段怎么渲染”
- “secret 怎么保存”

统一交给插件配置协议这层。

## 6. 前端页面怎么收口

### 6.1 `SettingsChannelAccessPage`

这页现在应该分成两层看：

#### A. 通道账号管理层

负责：

- 列账号
- 新建账号
- 编辑账号基础信息
- 探测状态
- 看绑定和失败摘要

#### B. 正式配置表单层

负责：

- 读取当前通道插件的 `channel_account` 作用域协议
- 用通用 dynamic renderer 渲染表单
- 调统一保存接口提交配置

页面里不应该再保留：

- `PLATFORM_CONFIG_FIELDS`
- 平台专属表单常量
- secret 特殊回显逻辑

### 6.2 `PluginDetailDrawer`

插件详情抽屉现在也要承认一个新事实：

- 它已经是统一插件级配置入口的一部分

也就是说，通道插件不只有账号页配置入口，插件详情页也可以承接：

- `plugin` 作用域配置

### 6.3 旧插件兼容

没有配置协议的旧通道插件仍然必须继续：

- 可展示
- 可启停
- 可运行

只是不会自动拥有正式动态表单入口。

## 7. 为什么这样拆

这样拆的好处很直接：

1. 后端 schema 和前端 renderer 不再各维护一份字段定义
2. 通道页面不再是事实来源，只是协议消费者
3. secret 语义终于统一，不会某个平台一个处理方式
4. 新增通道插件时，不需要先改页面常量才能上线配置

说白了，就是把“字段定义”从页面拿走，交还给插件本身。

## 8. 与 004.2.3 的关系

这份 Spec 只负责讲通道体系怎么消费正式配置协议。

下面这些正文统一以 `004.2.3` 为准：

- `config_specs`
- `config_schema`
- `ui_schema`
- secret 保存语义
- 动态表单字段类型和 widget 类型
- `plugin_config_instances` 的详细结构

这里不再复制第二套。

## 9. 验收边界

通道这条线改完后，至少要满足：

1. 通道插件 manifest 能正式声明 `channel_account` 配置协议
2. 通道账号配置可通过统一插件配置 API 读取和保存
3. `SettingsChannelAccessPage` 不再把硬编码字段当事实来源
4. `PluginDetailDrawer` 能接入通用插件配置入口
5. `channel_plugin_accounts.config_json` 只作为兼容副本，不再被文档写成唯一配置来源
