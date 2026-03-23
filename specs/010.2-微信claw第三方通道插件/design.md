# 设计文档 - 微信claw第三方通道插件

状态：Draft

## 1. 概述

### 1.1 目标

- 用第三方插件方式接入微信 claw 通道，不污染宿主核心代码
- 复用已经验证过的微信 transport，去掉 OpenClaw 耦合层
- 给扫码登录、轮询收信、文本发送、媒体处理和 `context_token` 恢复提供完整落地方案
- 把需要宿主补齐的能力限制在“通用插件能力”范围内

### 1.2 覆盖需求

- `requirements.md` 需求 1：第三方插件边界
- `requirements.md` 需求 2：扫码登录与状态管理
- `requirements.md` 需求 3：轮询接入
- `requirements.md` 需求 4：文本和媒体收发
- `requirements.md` 需求 5：`context_token` 持久化
- `requirements.md` 需求 6：宿主仅做通用能力补齐
- `requirements.md` 需求 7：技术与法律边界记录

### 1.3 技术约束

- 后端宿主：Python，现有插件运行链路通过 `plugin_type="channel"` 和 `plugin_type="action"` 执行
- 上游 transport：Node.js/TypeScript 生态，当前已在 `tmp/weixin-agent-gateway` 完成 POC
- 插件落点：`C:\Code\FamilyClaw\apps\api-server\plugins-dev`
- 宿主硬约束：核心仓库里不允许出现任何微信 claw 逻辑代码
- 插件状态存储：优先使用插件自己的 `working_dir`，避免把微信私有状态灌回宿主表结构

## 2. 架构

### 2.1 系统结构

整体结构分三层，边界必须死死守住：

1. 宿主通用层  
   只负责插件发现、配置、启停、调度、日志、状态展示、`channel` 动作执行和通用 `action` 执行。

2. 微信插件适配层  
   放在 `plugins-dev/weixin_claw_channel/` 下，负责把宿主的 `poll / send / probe` 和扫码动作翻译成 transport 调用。

3. 微信 transport 层  
   来自上游 transport 能力裁剪版，负责扫码登录、拉消息、发消息、媒体上传下载、`context_token` 处理。

宿主和 transport 中间不直接连线。中间必须隔着插件自己的适配层。

#### 2.1.1 宿主禁止项清单

下面这些东西只要出现在宿主核心代码里，就是边界破了：

- `if platform == "weixin"`、`if plugin_id == "weixin-claw-channel"` 这类平台特判
- 微信二维码生成、扫码轮询、登录态解释逻辑
- 微信 `context_token` 专属缓存、专属表结构、专属恢复逻辑
- 微信原始消息 DTO、微信媒体协议字段、微信私有错误码翻译
- 从 `tmp/weixin-agent-gateway` 或 `official-openclaw-weixin` 直接搬来的 `src/channel.ts`、`src/runtime.ts`、`src/messaging/process-message.ts` 这一层耦合代码

这不是风格问题，这是结构污染。谁把这些塞进宿主，谁就在制造后续不可维护的烂泥。

### 2.2 模块职责

| 模块 | 职责 | 输入 | 输出 |
| --- | --- | --- | --- |
| 宿主 `channel` 运行时 | 调用插件 `poll / webhook / send / probe`，记录通用状态 | `channel_account`、通用消息 DTO | 插件执行结果、状态更新 |
| 宿主插件动作运行时 | 执行扫码登录、登出、清理状态等通用插件动作 | 插件 ID、动作名、作用域参数 | 动作结果、通知、状态卡片 |
| 微信插件 Python 入口 | 把宿主请求翻译成 Node transport 调用 | 宿主 JSON payload | 标准 `channel` 响应 JSON |
| 微信插件 Node bridge | 调用 transport 并处理上游协议细节 | Python 入口透传请求 | 标准化 transport 结果 |
| 微信插件状态存储 | 保存登录态、轮询游标、`context_token`、媒体缓存、日志 | 插件运行过程产生的状态 | 本地 SQLite、文件、结构化日志 |
| 上游 transport 裁剪层 | 扫码、收信、发信、媒体、token | 微信协议参数 | 原始 transport 结果 |

#### 2.2.1 宿主允许补齐的通用能力

宿主如果要改，只能补下面这些放到别的平台也成立的能力：

1. 账号级插件动作执行入口  
   用来对某个 `channel_account` 调插件 `action`，不关心二维码、微信登录之类平台细节。
2. 账号级插件状态摘要读取入口  
   只读展示 `status`、`message`、`last_error_code`、`last_error_message` 这类通用信息。
3. 插件 `working_dir` 通用暴露规则  
   只允许返回只读提示或受控路径，不允许让宿主理解插件私有文件内容。
4. 通用轮询和探活调度  
   调 `channel` 的 `poll`、`probe`，不增加微信专属 worker 类型。
5. 通用结构化错误返回  
   宿主只认 `error_code`、`detail`、`field`、`timestamp`，不认微信协议细节。

如果某个所谓“通用能力”必须知道二维码、微信 token、微信扫码阶段，那它就根本不通用，不准进宿主。

### 2.3 关键流程

#### 2.3.1 扫码登录流程

1. 管理员在微信通道账号页触发“开始登录”
2. 宿主以通用插件动作方式执行 `start_login`
3. 微信插件 Python 入口调用 Node bridge
4. Node bridge 调 transport 生成二维码内容，并转成浏览器可展示的二维码图片或文本
5. 管理员扫码后，插件持续查询登录状态
6. 登录成功后，插件把 cookie、设备信息、账号标识等写入插件私有运行目录
7. 宿主只接收“账号已登录/未登录/失效”这类通用状态，不理解微信内部字段

#### 2.3.2 轮询收消息流程

1. 宿主调度 `poll_channel_account`
2. 宿主把 `channel_account` 通用信息和上次游标交给插件
3. 插件从私有状态存储恢复登录态和游标
4. Node bridge 调 transport 的 `getUpdates`
5. 插件把微信原始消息转换成宿主标准 `ChannelGatewayInboundEvent`
6. 插件把需要回传的上下文信息放进通用 `metadata`
7. 宿主继续走现有 `channel` 入站链路，不增加任何微信分支

#### 2.3.3 发送消息流程

1. 宿主调用插件 `send`
2. 插件按账号和会话键恢复最近有效的 `context_token`
3. Node bridge 调 transport 的 `sendMessage` 或媒体发送接口
4. 插件返回标准发送结果和 provider reference
5. 宿主只记录通用 delivery 结果

#### 2.3.4 `context_token` 恢复流程

1. 插件在收到微信入站消息时抽取 `context_token`
2. 按 `channel_account_id + external_conversation_key + external_user_id` 维度持久化
3. 发送时优先使用当前入站 `metadata` 里的 token 引用
4. 若当前 `metadata` 没有，则回退到插件私有状态存储中的最近有效 token
5. 若发送返回 token 失效，则标记旧 token 过期并等待下一次入站刷新

## 3. 组件和接口

### 3.1 插件包结构

覆盖需求：1、2、3、4、5、6

建议目录如下：

```text
apps/api-server/plugins-dev/weixin_claw_channel/
  manifest.json
  requirements.txt
  package.json
  README.md
  plugin/
    __init__.py
    channel.py
    action.py
    bridge.py
    runtime_state.py
    models.py
    logging_utils.py
  vendor/
    weixin_transport/
      package.json
      src/
      dist/
  tests/
    test_channel.py
    test_action.py
    test_runtime_state.py
```

设计要点：

- 首版目录直接定稿，不再摇摆：
  - 插件根目录：`apps/api-server/plugins-dev/weixin_claw_channel/`
  - manifest：`apps/api-server/plugins-dev/weixin_claw_channel/manifest.json`
  - Python 包：`apps/api-server/plugins-dev/weixin_claw_channel/plugin/`
  - Node vendor：`apps/api-server/plugins-dev/weixin_claw_channel/vendor/weixin_transport/`
- `manifest.json` 声明为第三方插件包，至少包含 `channel` 和 `action` 两种类型
- `plugin/channel.py` 负责 `poll / send / probe / webhook`
- `plugin/action.py` 负责扫码登录、查询登录状态、退出登录、清理状态
- `plugin/bridge.py` 负责 Python 与 Node 的单次 JSON 调用桥接
- `vendor/weixin_transport/` 保存裁剪后的上游 transport 代码
- 所有运行态数据都落到该插件自己的 `working_dir`

### 3.2 数据结构

覆盖需求：2、3、4、5、6

#### 3.2.1 Manifest 关键声明

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | 插件唯一 ID，建议 `weixin-claw-channel` | 不与 builtin 重名 |
| `types` | array | 是 | 插件类型 | 至少包含 `channel`、`action` |
| `entrypoints.channel` | string | 是 | 通道入口 | 指向 Python 入口函数 |
| `entrypoints.action` | string | 是 | 动作入口 | 用于扫码和状态管理 |
| `capabilities.channel` | object | 是 | 通道能力声明 | 符合宿主 `channel` 约束 |
| `config_specs` | array | 是 | 配置声明 | 至少包含 `channel_account` 作用域 |

首版直接固定如下，后续实现照这个来，不再重新发明命名：

- `id = "weixin-claw-channel"`
- `entrypoints.channel = "plugin.channel.handle"`
- `entrypoints.action = "plugin.action.execute"`
- `config_specs[0].scope_type = "channel_account"`
- `capabilities.channel.platform_code = "weixin-claw"`
- `capabilities.channel.inbound_modes = ["polling"]`
- `capabilities.channel.delivery_modes = ["reply"]`

#### 3.2.2 `channel_account` 配置字段

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `account_label` | string | 是 | 管理端显示名 | 仅用于识别 |
| `poll_interval_seconds` | integer | 否 | 轮询间隔 | 默认值由插件给出 |
| `login_status` | string | 否 | 登录状态摘要 | 只读展示字段 |
| `runtime_profile` | enum | 否 | 运行模式 | 预留 `stable` / `debug` |
| `working_dir_hint` | string | 否 | 运行目录提示 | 只读，不暴露敏感路径 |

注意：

- cookie、token、设备信息不进入宿主表单字段
- 敏感登录态只保存在插件私有运行目录

#### 3.2.3 插件私有状态存储

推荐在 `working_dir` 下使用一个 SQLite 文件和几个缓存目录：

| 结构 | 用途 |
| --- | --- |
| `runtime.sqlite` | 保存账号登录态索引、轮询游标、`context_token`、发送回执 |
| `media/` | 保存下载的媒体和待上传临时文件 |
| `logs/` | 保存插件结构化日志 |
| `qr/` | 暂存二维码渲染结果和过期时间 |

建议的 SQLite 表：

| 表名 | 职责 | 关键字段 |
| --- | --- | --- |
| `account_sessions` | 保存账号登录态索引 | `channel_account_id`、`status`、`session_blob_path`、`updated_at` |
| `poll_checkpoints` | 保存轮询游标 | `channel_account_id`、`cursor`、`latest_external_event_id` |
| `context_tokens` | 保存可恢复 token | `channel_account_id`、`conversation_key`、`external_user_id`、`token`、`expires_at` |
| `delivery_receipts` | 保存发送结果 | `channel_account_id`、`provider_message_ref`、`status`、`error_code` |

### 3.3 接口契约

覆盖需求：2、3、4、5、6

#### 3.3.1 插件 `channel` 入口

- 类型：Function
- 标识：`entrypoints.channel`
- 输入：
  - `action="poll"`：账号信息、宿主游标
  - `action="send"`：账号信息、目标会话键、文本或媒体、通用 `metadata`
  - `action="probe"`：账号信息
  - `action="webhook"`：本次默认不作为主链路，但接口保持兼容
- 输出：
  - `poll`：宿主标准 `ChannelPollingExecutionRead`
  - `send`：宿主标准发送结果 JSON
  - `probe`：通用健康检查结果
- 校验：
  - 必须验证账号已启用且存在有效登录态
  - 必须验证 `send` 目标是否能恢复到合法 token
- 错误：
  - `login_required`
  - `transport_unavailable`
  - `context_token_missing`
  - `media_upload_failed`
  - `poll_cursor_invalid`

#### 3.3.2 插件 `action` 入口

- 类型：Function
- 标识：`entrypoints.action`
- 输入：
  - `action_name="start_login"`
  - `action_name="get_login_status"`
  - `action_name="logout"`
  - `action_name="purge_runtime_state"`
  - 作用域参数：`channel_account_id`
- 输出：
  - 二维码内容或二维码图片数据
  - 登录状态摘要
  - 清理结果
- 校验：
  - 必须限制在当前账号作用域内
  - 必须对不存在或已禁用账号返回明确错误
- 错误：
  - `qr_code_expired`
  - `login_timeout`
  - `account_disabled`
  - `runtime_state_not_found`

## 4. 数据与状态模型

### 4.1 数据关系

宿主和插件的数据关系要保持简单：

- 宿主拥有 `plugin`、`channel_account`、通用入站事件、通用投递记录
- 插件拥有微信私有登录态、轮询游标、`context_token`、媒体缓存和私有日志
- 宿主永远不直接操作插件私有 SQLite 表
- 插件可以把少量通用状态摘要回写给宿主，例如“已登录”“登录失效”“最近轮询失败”

### 4.2 状态流转

#### 4.2.1 账号登录状态

| 状态 | 含义 | 进入条件 | 退出条件 |
| --- | --- | --- | --- |
| `not_logged_in` | 尚未建立可用登录态 | 新账号创建、手动登出、清理状态 | 开始扫码 |
| `waiting_scan` | 已生成二维码等待扫码 | 执行 `start_login` | 登录成功、二维码过期、手动取消 |
| `active` | 登录态可用 | 扫码成功并持久化 | 登录失效、禁用账号、手动登出 |
| `expired` | 原登录态不可用 | transport 返回登录失效 | 重新登录成功或清理状态 |
| `disabled` | 宿主已禁用账号 | 管理员禁用账号 | 管理员重新启用 |

#### 4.2.2 `context_token` 状态

| 状态 | 含义 | 进入条件 | 退出条件 |
| --- | --- | --- | --- |
| `fresh` | 最新入站消息刚刷新 | 收到新 token | 被新 token 覆盖或被判定失效 |
| `stale` | 可尝试使用但不保证有效 | 超过新鲜窗口但未报错 | 发送成功刷新或发送失败失效 |
| `invalid` | 已确认不可用 | 发送返回 token 错误 | 下一次入站刷新 |

## 5. 错误处理

### 5.1 错误类型

- `login_required`：未登录或登录态丢失
- `login_expired`：登录态已过期
- `poll_failed`：拉取消息失败
- `context_token_missing`：发送时找不到可用 token
- `context_token_invalid`：发送时 token 已失效
- `media_download_failed`：媒体下载失败
- `media_upload_failed`：媒体上传失败
- `bridge_protocol_error`：Python 和 Node 之间的桥接协议异常

### 5.2 错误响应格式

```json
{
  "detail": "微信登录态已失效，请重新扫码登录",
  "error_code": "login_expired",
  "field": "channel_account_id",
  "timestamp": "2026-03-23T00:00:00Z"
}
```

### 5.3 处理策略

1. 输入校验错误：直接拒绝，并返回具体字段
2. 运行态缺失：提示重新登录或重新初始化运行目录
3. transport 错误：记录原始错误摘要，但不要把敏感 payload 打到公开日志
4. `context_token` 失效：标记旧 token 为 `invalid`，等待下一次入站刷新
5. Node bridge 异常：把该次执行判定为失败，并保留 stderr 摘要供排查

## 6. 正确性属性

### 6.1 宿主无微信特化

对于任何微信相关功能，宿主都只能看到通用插件、通用账号和通用消息契约，不能依赖微信私有字段。

**验证需求：** 需求 1、需求 6

### 6.2 `context_token` 可恢复

对于任何一次需要原路回复的微信发送，只要插件已经收到过该会话的有效入站消息，就应该能够从私有状态中恢复最近可用的 `context_token`，或者明确报告缺失。

**验证需求：** 需求 4、需求 5

### 6.3 transport 可替换

对于任何一次 transport 升级或替换，只要宿主 `channel` 契约不变，就不应该要求改宿主核心代码。

**验证需求：** 需求 1、需求 6、需求 7

## 7. 测试策略

### 7.1 单元测试

- 插件运行目录初始化和状态存储读写
- `context_token` 保存、覆盖、失效标记和恢复
- Python 与 Node bridge 的请求封装和错误处理
- manifest 和 `channel_account` 配置校验

### 7.2 集成测试

- `start_login` 生成二维码并轮询登录状态
- `poll` 拉取标准化事件并进入宿主现有通道链路
- `send` 发送文本，包含 token 命中和 token 缺失场景
- 媒体下载与上传的基础链路

### 7.3 端到端测试

- 管理员创建账号、扫码登录、收文本、发文本
- 重启插件后继续发送，验证 `context_token` 恢复
- 登录失效后重新扫码恢复
- 禁用账号后停止轮询与发送

### 7.4 验证映射

| 需求 | 设计章节 | 验证方式 |
| --- | --- | --- |
| `requirements.md` 需求 1 | `design.md` 2.1、3.1、6.1 | 代码评审、目录检查 |
| `requirements.md` 需求 2 | `design.md` 2.3.1、3.3.2、4.2.1 | 动作集成测试、人工扫码验证 |
| `requirements.md` 需求 3 | `design.md` 2.3.2、3.3.1 | 轮询集成测试、人工收消息验证 |
| `requirements.md` 需求 4 | `design.md` 2.3.3、3.3.1、5.3 | 发送测试、媒体测试 |
| `requirements.md` 需求 5 | `design.md` 2.3.4、3.2.3、4.2.2、6.2 | 重启恢复测试、失败恢复测试 |
| `requirements.md` 需求 6 | `design.md` 2.1、4.1、6.1、6.3 | 代码评审、宿主 diff 审查 |
| `requirements.md` 需求 7 | `design.md` 8.1、8.2 | 文档检查、发布前清单 |

## 8. 风险与待确认项

### 8.1 风险

- 上游 transport 是 Node 生态，宿主插件入口是 Python，需要桥接，但这个复杂度必须关在插件内
- `context_token` 的有效期和失效条件可能带平台灰度差异，需要持续观察
- 媒体类型越多，格式和缓存清理越容易变成烂泥，所以第一版必须收边界
- 如果将来需要多节点部署，单机 `working_dir + SQLite` 方案要升级

### 8.2 待确认项

- 最终选用 `BytePioneer-AI/weixin-agent-gateway` 裁剪版，还是 `@tencent-weixin/openclaw-weixin` 作为更小的 transport 来源
- 插件动作页面是复用现有插件动作 UI，还是需要宿主补一个通用“账号级动作面板”
- 发布前是否需要单独的法务评审，确认微信平台条款、自动化登录边界和商用限制
