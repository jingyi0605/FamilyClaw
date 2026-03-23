# 需求文档 - 微信claw第三方通道插件

状态：Draft

## 简介

这次不是做一个“微信适配脚本”，而是要把已经验证过的微信 transport 能力，正式收口成 `FamilyClaw` 可维护、可禁用、可升级的第三方插件。

业务背景已经很明确：

- 微信 transport 的核心价值已经被 POC 验证
- OpenClaw 路由层不是核心资产，不能继续带进来
- 宿主核心代码库明确禁止出现任何微信 claw 逻辑

目标用户有两类：

- 家庭管理员：负责新增微信通道账号、扫码登录、查看状态、排查失败
- 家庭成员：直接通过微信和 `FamilyClaw` 对话，不需要切回网页

做完后的核心收益也很直接：

- 微信成为一个真正独立的第三方通道插件，而不是宿主里的特判
- 后续升级微信 transport 或替换上游实现时，只改插件目录
- 宿主依然保持通用 `channel` 运行时，不被某个平台拖进泥里

## 术语表

- **System**：当前 `FamilyClaw` 宿主系统
- **微信claw插件**：本次规划的第三方插件包，代码全部落在 `apps/api-server/plugins-dev`
- **transport**：微信扫码登录、`getUpdates`、`sendMessage`、媒体上传下载、`context_token` 等底层通讯能力
- **OpenClaw 耦合层**：上游仓库里依赖 OpenClaw runtime 的路由和消息处理层，本次明确不复用
- **channel_account**：宿主里某个通道账号实例的统一配置作用域
- **插件私有运行目录**：插件自己的 `working_dir`，用于保存登录态、SQLite、媒体缓存和日志
- **context_token**：微信回复原链路需要的上下文令牌，丢失后会直接影响回复能力

## 范围说明

### In Scope

- 以第三方插件方式接入微信 claw 通道
- 插件代码固定放在 `apps/api-server/plugins-dev`
- 插件包目录、插件 ID 和入口声明在首版直接定死：
  - 目录：`apps/api-server/plugins-dev/weixin_claw_channel/`
  - manifest：`apps/api-server/plugins-dev/weixin_claw_channel/manifest.json`
  - 插件 ID：`weixin-claw-channel`
  - 类型：`channel`、`action`
  - 入口：`plugin/channel.py`、`plugin/action.py`
- 复用并裁剪上游 transport 能力，不复用 OpenClaw 耦合层
- 支持扫码登录、登录态持久化、轮询收消息、文本发送、基础媒体上传下载
- 支持 `context_token` 的持久化、恢复和失效更新
- 允许宿主补齐通用插件能力，但禁止引入任何微信特化逻辑
- 规划插件管理、账号配置、状态展示、失败排查和合规检查入口

### Out of Scope

- 不把微信能力做成宿主内建插件
- 不在核心仓库增加微信专属模型、服务、轮询器、协议字段
- 第一版不做联系人同步、群管理、朋友圈、支付、办公套件等无关能力
- 第一版不做分布式多节点共享状态的强一致方案

## 需求

### 需求 1：微信接入必须是第三方插件，而不是宿主内建逻辑

**用户故事：** 作为系统维护者，我希望微信 claw 以第三方插件落在 `plugins-dev`，以便后续升级、停用、回滚和替换时不需要改宿主核心代码。

#### 验收标准

1. WHEN 开始实现微信通道 THEN System SHALL 把插件源码放在 `apps/api-server/plugins-dev/<plugin_dir>/`，而不是 `app/plugins/builtin/`
2. WHEN 宿主运行微信通道 THEN System SHALL 只通过通用 `channel`、`action`、配置和状态接口与插件交互，而不是写 `if platform == "weixin"` 这类分支
3. WHEN 后续替换微信 transport 版本或裁剪上游代码 THEN System SHALL 主要改动插件目录，不要求改宿主核心流程
4. WHEN 审查插件包结构 THEN System SHALL 看到固定的第三方插件契约：
   - 插件目录固定为 `apps/api-server/plugins-dev/weixin_claw_channel/`
   - 插件 ID 固定为 `weixin-claw-channel`
   - manifest 固定声明 `types=["channel","action"]`
   - 宿主只认 `entrypoints.channel` 和 `entrypoints.action`

### 需求 2：管理员必须能完成微信账号扫码登录与状态管理

**用户故事：** 作为家庭管理员，我希望在插件管理或通道账号页面里完成扫码登录、查看登录状态、失效重登和主动退出，以便微信账号真的能长期可用。

#### 验收标准

1. WHEN 管理员创建一个微信 `channel_account` THEN System SHALL 提供开始扫码登录、查看二维码、轮询登录结果和清理登录态的能力
2. WHEN 微信登录成功、失效或被登出 THEN System SHALL 在账号状态里反映最新状态，而不是只留在插件内部黑箱
3. WHEN 管理员禁用或删除该账号 THEN System SHALL 停止轮询并清理该账号对应的插件私有运行状态或明确标记为不可再用

### 需求 3：插件必须能稳定拉取微信消息并接入现有通道链路

**用户故事：** 作为家庭成员，我希望微信收到的消息能像其他通道一样稳定进入 `FamilyClaw`，以便我在微信里说话时系统能正常理解和回复。

#### 验收标准

1. WHEN 插件执行 `poll` THEN System SHALL 通过微信 transport 拉取新消息，并输出符合宿主 `channel` 契约的标准事件
2. WHEN 微信重复返回同一条更新或插件重复轮询 THEN System SHALL 通过外部事件 ID 和插件私有游标避免重复入站
3. WHEN 拉取失败、游标异常或登录态过期 THEN System SHALL 记录失败原因，并让管理员能看到需要重试还是重新登录

### 需求 4：插件必须支持文本发送和基础媒体收发

**用户故事：** 作为家庭成员，我希望系统不仅能收微信文本，还能把回复发回去，并在第一版支持基础媒体上传下载，以便日常对话链路完整可用。

#### 验收标准

1. WHEN 宿主调用插件 `send` 动作发送文本 THEN System SHALL 使用微信 transport 完成原路发送
2. WHEN 入站消息包含图片、文件或语音等可下载媒体 THEN System SHALL 能把媒体拉到插件私有运行目录并输出宿主可消费的标准引用信息
3. WHEN 宿主需要发出第一版支持的媒体类型 THEN System SHALL 先完成上传再发消息，并在失败时记录上传或发送失败原因

### 需求 5：插件必须自己解决 `context_token` 持久化与恢复

**用户故事：** 作为系统维护者，我希望 `context_token` 不再依赖进程内缓存，以便进程重启、轮询切换、延迟回复和失败重试后，微信回复仍然可靠。

#### 验收标准

1. WHEN 插件收到一条带有 `context_token` 的微信消息 THEN System SHALL 把该令牌持久化到插件私有运行目录，而不是只放在内存 `Map`
2. WHEN 插件稍后发送回复、重试投递或进程重启后再次发送 THEN System SHALL 能按账号和会话键恢复最近有效的 `context_token`
3. WHEN `context_token` 失效、缺失或与会话不匹配 THEN System SHALL 明确记录失败并触发可恢复策略，而不是静默发送错误请求

### 需求 6：宿主只允许补齐通用能力，不能加入任何微信特化逻辑

**用户故事：** 作为开发者，我希望宿主改动只停留在“第三方插件通用能力补齐”层面，以便后续接其他私有 transport 平台时也能复用，而不是给微信开后门。

#### 验收标准

1. WHEN 宿主需要支持扫码动作、插件状态卡片或插件私有工作目录 THEN System SHALL 以通用插件能力形式提供，而不是只对微信开放
2. WHEN 宿主存储或展示插件配置、运行状态和日志 THEN System SHALL 只理解通用 `plugin` 和 `channel_account` 语义，不理解微信专属字段
3. WHEN 代码评审或验收时检查核心代码库 THEN System SHALL 不出现微信专属 DTO、微信专属 worker、微信专属消息路由或微信专属媒体协议代码
4. WHEN 宿主需要新增能力支持微信插件 THEN System SHALL 只允许新增下面这些脱离微信也成立的能力：
   - 账号级插件动作执行入口
   - 账号级插件状态摘要读取入口
   - 插件 `working_dir` 只读暴露或提示能力
   - 通用的结构化插件错误码和状态卡片
   - 通用的轮询/探活执行入口
5. WHEN 某个宿主改动只有微信 transport 才会用到 THEN System SHALL 视它为违规设计并拒绝合入，例如：
   - 微信二维码专属字段
   - 微信 `context_token` 专属表结构
   - 微信消息体专属 DTO
   - 微信账号状态专属枚举

### 需求 7：项目必须在技术和法律边界上可解释、可验收

**用户故事：** 作为项目负责人，我希望在正式开发前就把技术来源、验证结论和合规风险写清楚，以便后续开发不是闭眼往前冲。

#### 验收标准

1. WHEN 开发进入实现阶段 THEN System SHALL 已记录当前 POC 验证结论，至少覆盖扫码、收消息、发文本和二维码生成链路
2. WHEN 复用上游微信 transport 代码 THEN System SHALL 明确记录许可证、来源和裁剪边界
3. WHEN 准备发布或对外使用 THEN System SHALL 明确列出仍需法务确认的平台条款、使用限制和商业风险

## 非功能需求

### 非功能需求 1：可靠性

1. WHEN 微信轮询返回重复事件、网络超时或账号临时失效 THEN System SHALL 保持幂等并留下可追踪错误
2. WHEN 插件进程或宿主进程重启 THEN System SHALL 通过插件私有运行目录恢复必要状态，至少包括登录态、游标和 `context_token`

### 非功能需求 2：可维护性

1. WHEN 后续升级上游 transport 或替换为新的 transport 实现 THEN System SHALL 主要改动插件目录，而不是扩散到宿主核心模块
2. WHEN 维护者排查问题 THEN System SHALL 能从账号状态、轮询日志、发送日志和插件私有状态文件一路查到问题点

### 非功能需求 3：性能

1. WHEN 插件执行一次常规轮询 THEN System SHALL 在可接受时间内完成拉取、去重和标准化，不能把宿主调度线程长期卡死
2. WHEN 插件发送文本或基础媒体 THEN System SHALL 在超时前完成发送或明确失败，不允许无响应悬挂

### 非功能需求 4：合规与安全

1. WHEN 插件保存登录态、令牌或媒体缓存 THEN System SHALL 把敏感数据限制在插件私有运行目录，并避免输出到公开日志
2. WHEN 项目准备对外分发或商用 THEN System SHALL 先完成上游许可证检查和平台条款确认，而不是默认“能跑就能发”

## 成功定义

- 微信通道实现被正式限定为第三方插件，宿主核心代码库不出现微信 claw 逻辑
- 管理员可以完成扫码登录、查看状态、重新登录和禁用账号
- 微信消息可以稳定进入现有 `channel` 链路并完成原路文本回复
- `context_token` 具备持久化与恢复方案，不再依赖内存 `Map`
- 已知技术风险和法律风险被文档化，而不是靠记忆推进
