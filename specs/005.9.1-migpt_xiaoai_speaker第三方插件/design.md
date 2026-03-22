# 设计文档 - migpt_xiaoai_speaker 第三方插件

状态：Draft

## 1. 概述

### 1.1 目标

- 在 `005.9` 的宿主契约基础上，定义 `migpt_xiaoai_speaker` 第三方插件如何接入。
- 首版明确走“文本轮询型实时对话”车道，不伪装成原始音频会话。
- 把小米账号、设备发现、消息轮询、机型差异、控制指令和风控恢复全部关进插件内部。

### 1.2 覆盖需求

- `requirements.md` 需求 1：实例配置
- `requirements.md` 需求 2：设备发现与同步
- `requirements.md` 需求 3：文本轮询型实时对话
- `requirements.md` 需求 4：统一 `speaker` 动作执行
- `requirements.md` 需求 5：机型 profile
- `requirements.md` 需求 6：runtime 和风控状态
- `requirements.md` 需求 7：小米逻辑留在插件内

### 1.3 技术约束

- 插件必须只调用 `005.9` 定义的宿主 `speaker/voice` 能力，不读宿主私有数据库，不走私有旁路接口。
- 常驻轮询 worker 必须遵守项目现有插件禁用规则和后台 worker 规范。
- 首版不承诺原始音频会话，只承诺文本轮询型实时对话。
- 设备动作继续复用宿主统一 `speaker` 协议，插件只做翻译。

## 2. 架构

### 2.1 系统结构

插件内部划分成七块：

1. `plugin/config`
   负责实例配置、字段校验和 profile 选择。
2. `plugin/xiaomi_auth`
   负责小米账号登录、cookie / token 刷新和失效检测。
3. `plugin/device_discovery`
   负责拉取小米账号下可接入的小爱音箱，并转换成宿主候选设备。
4. `plugin/model_profiles`
   负责管理不同机型的指令映射和能力差异。
5. `plugin/runtime_worker`
   负责周期性轮询会话消息、上报 heartbeat、处理降级。
6. `plugin/text_turn_bridge`
   负责把轮询到的消息转换成宿主 `SpeakerTextTurnRequest`。
7. `plugin/action_executor`
   负责把统一 `speaker` 动作翻译成 MiNA / MIoT 请求。

### 2.2 模块职责

| 模块 | 职责 | 输入 | 输出 |
| --- | --- | --- | --- |
| `config` | 解析实例配置和运行参数 | 插件实例配置 | 标准化配置对象 |
| `xiaomi_auth` | 登录和维护小米云会话 | 账号配置 | 可用客户端、登录状态 |
| `device_discovery` | 拉取并转换候选音箱 | 小米设备列表 | 宿主候选设备结果 |
| `model_profiles` | 处理机型差异 | 设备型号、手动覆盖 | 指令映射、能力标签 |
| `runtime_worker` | 轮询会话和上报健康状态 | 实例配置、认证客户端 | heartbeat、turn 事件 |
| `text_turn_bridge` | 把小米会话消息送进宿主 | 小米 query、游标 | `SpeakerTextTurnRequest` |
| `action_executor` | 执行统一控制动作 | 宿主 `speaker` 动作 | 标准执行结果 |

### 2.3 关键流程

#### 2.3.1 实例创建与认证

1. 用户创建 `migpt_xiaoai_speaker` 集成实例。
2. 插件保存账号、设备筛选、轮询频率、profile 覆盖等配置。
3. 插件通过 `xiaomi_auth` 登录小米账号。
4. 登录成功后，实例进入可发现和可轮询状态。

#### 2.3.2 候选设备发现与绑定

1. 插件调用小米云接口获取当前账号下的小爱音箱列表。
2. 插件根据实例配置和 profile 过滤出可接入设备。
3. 插件把设备转换成宿主候选设备结构。
4. 宿主继续走正式 discovery / binding 主链。

#### 2.3.3 文本轮询型实时对话

1. `runtime_worker` 按心跳周期拉取 MiNA 会话记录。
2. 插件根据 `polling cursor + timestamp + turn_id` 找到新的 query。
3. 插件把 query 转成 `SpeakerTextTurnRequest`，提交给宿主。
4. 宿主返回 `SpeakerTextTurnResult`。
5. 插件根据返回值选择：
   - 直接用小米 TTS 播放文本；
   - 调第三方 TTS 生成音频 URL，再通过 MiNA 播放。

#### 2.3.4 统一动作执行

1. 宿主对绑定的小爱音箱执行统一 `speaker` 动作。
2. 插件 action 入口接收动作请求。
3. `action_executor` 根据机型 profile 选择合适指令。
4. 插件调用 MiNA / MIoT 并按标准结果模型返回。

#### 2.3.5 风控、失效和恢复

1. 登录失效、风控或连续调用失败时，runtime 进入 `degraded` 或 `error`。
2. 插件继续通过 heartbeat 上报错误摘要。
3. 宿主显示插件不可用，但保留配置和排障入口。
4. 人工修复后，runtime 可重新登录和恢复轮询。

## 3. 组件和接口

### 3.1 核心组件

覆盖需求：1、2、3、4、5、6、7

- `xiaomi_client`
  封装 MiNA / MIoT 调用，不向宿主暴露小米协议细节。
- `speaker_host_client`
  封装宿主正式 `speaker/voice` 调用能力，只开放 discovery、text turn、heartbeat 等接口。
- `profile_resolver`
  根据设备型号、能力标签和人工覆盖选择正确 profile。

### 3.2 数据结构

覆盖需求：1、2、3、4、5、6

#### 3.2.1 `MiGPTInstanceConfig`

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `xiaomi_user_id` | `string` | 是 | 小米账号标识 | 非空 |
| `password_secret_ref` | `string` | 是 | 密码或等价密钥引用 | 插件 secret 配置 |
| `device_selector` | `object` | 否 | 设备筛选条件 | 可按 did、名称、型号过滤 |
| `poll_interval_ms` | `integer` | 是 | 轮询间隔 | 不低于最小阈值 |
| `check_playback_after_seconds` | `integer` | 否 | 播放状态检查延迟 | 大于等于 1 |
| `tts_mode` | `string` | 是 | TTS 模式 | `xiaoai` 或 `custom_audio_url` |
| `profile_overrides` | `object` | 否 | 机型 profile 覆盖 | 仅限插件内部使用 |

#### 3.2.2 `XiaoAiDeviceProfile`

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `profile_code` | `string` | 是 | profile 标识 | 插件内部唯一 |
| `match_models` | `list[string]` | 是 | 适用机型 | 至少一个 |
| `tts_command` | `list[number]` | 否 | MIoT TTS 指令 | 未知时可为空 |
| `wake_up_command` | `list[number]` | 否 | 唤醒指令 | 未知时可为空 |
| `playing_command` | `list[number]` | 否 | 播放状态指令 | 未知时可为空 |
| `supports_custom_audio_play` | `boolean` | 是 | 是否支持音频 URL 播放 | - |
| `supports_keep_alive_simulation` | `boolean` | 是 | 是否支持连续对话模拟 | - |

#### 3.2.3 `XiaoAiConversationCursor`

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `integration_instance_id` | `string` | 是 | 宿主实例 id | 已存在 |
| `external_device_id` | `string` | 是 | 小米设备 id | 非空 |
| `last_message_timestamp` | `integer` | 是 | 上次处理的消息时间戳 | 毫秒 |
| `last_turn_id` | `string` | 否 | 上次处理的 turn 标识 | 用于幂等 |

#### 3.2.4 `XiaoAiTextTurnEnvelope`

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `query_text` | `string` | 是 | 小米会话里的用户文本 | 非空 |
| `answer_preview` | `string` | 否 | 小米已有回答摘要 | 用于过滤非目标消息 |
| `message_timestamp` | `integer` | 是 | 消息时间戳 | 毫秒 |
| `conversation_id` | `string` | 是 | 小米会话标识 | 稳定 |
| `dedupe_key` | `string` | 是 | 幂等键 | 同消息唯一 |

#### 3.2.5 `MiGPTRuntimeState`

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `state` | `string` | 是 | runtime 状态 | `idle`、`running`、`degraded`、`error` |
| `consecutive_failures` | `integer` | 是 | 连续失败次数 | 大于等于 0 |
| `last_success_at` | `string` | 否 | 最近成功时间 | ISO 时间 |
| `last_failure_at` | `string` | 否 | 最近失败时间 | ISO 时间 |
| `last_error_summary` | `string` | 否 | 错误摘要 | 排障用 |
| `risk_flags` | `list[string]` | 否 | 风控标记 | 例如登录失效、速率限制 |

### 3.3 接口契约

覆盖需求：1、2、3、4、6、7

#### 3.3.1 插件 manifest

- 类型：Manifest
- 建议类型组合：`integration + action + speaker_adapter`
- 关键声明：
  - `capabilities.integration`
  - `capabilities.speaker_adapter`
  - `entrypoints.integration`
  - `entrypoints.action`
  - `entrypoints.speaker_adapter` 或等价 runtime 入口
- 约束：
  - 必须声明 `supported_modes=["text_turn"]`
  - 首版不得声明 `audio_session`

#### 3.3.2 `speaker_host.submit_text_turn`

- 类型：宿主接口
- 输入：`SpeakerTextTurnRequest`
- 输出：`SpeakerTextTurnResult`
- 插件职责：
  - 准备稳定 `turn_id`
  - 传入已解析的用户文本
  - 附带实例和设备归属

#### 3.3.3 `speaker_host.report_runtime_heartbeat`

- 类型：宿主接口
- 输入：`SpeakerRuntimeHeartbeat`
- 输出：确认结果
- 插件职责：
  - 周期性上报健康状态
  - 遇到风控、登录失效、连续失败时及时更新状态

#### 3.3.4 action 入口

- 类型：插件 action entrypoint
- 输入：宿主统一 `speaker` 动作
- 输出：宿主统一动作结果
- 约束：
  - 不得返回小米私有错误模型
  - 必须能把 profile 命中结果记录进调试信息

## 4. 数据与状态模型

### 4.1 数据关系

- 一个插件实例对应一个小米账号上下文。
- 一个实例可以发现和绑定多台小爱音箱。
- 每台绑定设备都有一个 `profile` 和一个独立 `polling cursor`。
- 所有 text turn 都必须能追溯到 `integration_instance_id + external_device_id + turn_id`。

### 4.2 状态流转

| 状态 | 含义 | 进入条件 | 退出条件 |
| --- | --- | --- | --- |
| `idle` | 已配置但未开始轮询 | 实例创建成功 | 启动 runtime |
| `running` | 正常轮询中 | 登录成功且 heartbeat 正常 | 连续失败、禁用、停止 |
| `degraded` | 可运行但不稳定 | 连续失败、限流、状态不完整 | 恢复成功或进入 `error` |
| `error` | 当前不可服务 | 登录失效、严重异常、风控阻断 | 人工修复或重启成功 |
| `disabled` | 宿主禁用 | 插件禁用 | 重新启用 |

## 5. 错误处理

### 5.1 错误类型

- `xiaomi_auth_failed`：登录失败
- `xiaomi_risk_controlled`：触发风控或限流
- `xiaomi_profile_missing`：机型 profile 缺失
- `speaker_text_turn_invalid`：提交给宿主的 turn 不合法
- `plugin_disabled`：宿主已禁用插件
- `speaker_binding_missing`：设备未正式绑定

### 5.2 错误响应格式

```json
{
  "detail": "小米账号登录已失效，当前实例进入降级状态。",
  "error_code": "xiaomi_auth_failed",
  "field": "xiaomi_user_id",
  "timestamp": "2026-03-22T00:00:00Z"
}
```

### 5.3 处理策略

1. 认证失败优先进入 `degraded` 或 `error`，并通过 heartbeat 上报。
2. profile 缺失时禁止假装支持对应动作或持续对话能力。
3. 宿主禁用后立即停止新的轮询提交和动作执行。
4. 小米云接口短暂失败允许有限重试，但不能在主事件循环里裸跑阻塞轮询。

## 6. 正确性属性

### 6.1 所有小米协议知识都留在插件内

对于任何 `migpt_xiaoai_speaker` 实现，宿主只能看到标准 `speaker/voice` DTO 和统一控制结果，不应看到 MiNA、MIoT、cookie、serviceToken 之类的协议细节。

**验证需求：** 需求 2、需求 4、需求 7

### 6.2 同一条厂商消息只会进入宿主一次

对于任何轮询到的小米会话消息，插件都必须通过稳定游标和幂等键保证它最多生成一次正式 `text turn`。

**验证需求：** 需求 3

### 6.3 首版不伪装成原始音频方案

对于任何首版 `migpt_xiaoai_speaker` 实现，都必须只声明并只走 `text_turn` 车道，不能声称已经支持 `audio_session`。

**验证需求：** 需求 3、需求 5

## 7. 测试策略

### 7.1 单元测试

- 配置校验和 secret 引用解析
- profile 命中和降级
- 轮询游标与幂等键生成
- 动作到 MiNA / MIoT 映射

### 7.2 集成测试

- 实例创建与认证失败语义
- 候选设备发现与正式绑定
- text turn 提交与宿主返回
- heartbeat / 禁用 / 降级状态

### 7.3 端到端测试

- 不刷机小爱音箱从插件实例创建到对话播报整链路
- 长文本回复和播放状态检查
- 插件禁用后停止轮询和控制执行

### 7.4 验证映射

| 需求 | 设计章节 | 验证方式 |
| --- | --- | --- |
| `requirements.md` 需求 1 | `design.md` §2.3.1、§3.2.1 | 配置与实例测试 |
| `requirements.md` 需求 2 | `design.md` §2.3.2、§3.2.2 | discovery / binding 测试 |
| `requirements.md` 需求 3 | `design.md` §2.3.3、§6.2、§6.3 | text turn 与幂等测试 |
| `requirements.md` 需求 4 | `design.md` §2.3.4、§3.3.4 | 动作执行测试 |
| `requirements.md` 需求 5 | `design.md` §2.1、§3.2.2 | profile 测试 |
| `requirements.md` 需求 6 | `design.md` §2.3.5、§4.2 | heartbeat / 风控测试 |
| `requirements.md` 需求 7 | `design.md` §6.1 | 人工审查与回归测试 |

## 8. 风险与待确认项

### 8.1 风险

- 小米云接口和风控策略不稳定，插件必须设计成可降级，而不是追求理论完美。
- 不同机型指令差异较大，如果 profile 建模太差，后面会继续长特殊分支。
- 播放状态轮询存在延迟，长文本回复可能被过早中断，需要允许参数调优。

### 8.2 待确认项

- 首版是否允许第三方 TTS 作为可选能力；本 Spec 默认允许，但不是强依赖。
- profile 的来源是内置静态表、远程更新还是用户手动覆盖；本 Spec 先要求插件内部可扩展，不强制具体来源。
