# 设计文档 - speaker/voice 通用插件契约

状态：Draft

## 1. 概述

### 1.1 目标

- 给宿主补一份正式的 `speaker/voice` 插件契约。
- 同时覆盖“文本轮询型实时对话”和“音频会话型实时对话”两条接入车道。
- 让宿主只保留通用桥接能力，不再吸收厂商协议细节。

### 1.2 覆盖需求

- `requirements.md` 需求 1：正式能力声明
- `requirements.md` 需求 2：discovery / binding 去硬编码
- `requirements.md` 需求 3：文本轮询型实时对话入口
- `requirements.md` 需求 4：音频会话型入口边界
- `requirements.md` 需求 5：统一 `speaker` 控制语义
- `requirements.md` 需求 6：runtime / 禁用 / 错误统一
- `requirements.md` 需求 7：宿主与厂商职责可审计

### 1.3 技术约束

- 后端继续沿用现有插件系统、设备绑定、设备控制和实时对话链路。
- 新的常驻 runtime / worker 必须遵守现有“插件禁用统一规则”和“后端事件循环与周期任务开发规范”。
- 宿主不能要求文本轮询型插件伪装成原始音频插件。
- 任何厂商专有登录、消息轮询、指令表、机型差异，必须留在插件内。

## 2. 架构

### 2.1 系统结构

目标结构分成两层：

1. 宿主层负责定义正式契约、校验 manifest、管理绑定、接受 text turn、调度设备控制、维护 runtime 健康状态。
2. 插件层负责把第三方平台协议翻译成宿主能理解的标准模型。

数据流分成三条主链：

- `discovery / binding`：插件发现设备，宿主创建或更新正式 `Device + DeviceBinding`。
- `text turn / audio session`：插件把对话请求送进宿主，宿主产出统一回复，再回给插件。
- `speaker command`：宿主继续用统一设备控制语义下发命令，插件负责翻译和执行。

### 2.2 模块职责

| 模块 | 职责 | 输入 | 输出 |
| --- | --- | --- | --- |
| `plugin manifest speaker_adapter spec` | 定义插件声明格式 | manifest | 标准化能力声明 |
| `speaker adapter registry` | 注册和校验 `speaker/voice` 插件 | manifest、启停状态 | 可用插件列表、能力快照 |
| `speaker discovery bridge` | 把候选设备接入统一实例和绑定主链 | 插件 discovery 结果 | `DeviceCandidate`、`DeviceBinding` |
| `speaker text turn bridge` | 接收插件提交的文本请求并返回结果 | `SpeakerTextTurnRequest` | `SpeakerTextTurnResult` |
| `speaker audio session bridge` | 承接原始音频或等价会话型插件 | `SpeakerAudioSessionEnvelope` | 会话控制结果 |
| `speaker command relay` | 继续承接统一设备控制动作 | 统一 `speaker` 动作 | 插件动作执行结果 |
| `speaker runtime registry` | 汇总插件 worker 健康状态和降级信息 | heartbeat、错误摘要 | runtime 状态视图 |

### 2.3 关键流程

#### 2.3.1 插件注册与能力识别

1. 宿主加载插件 manifest。
2. 如果插件声明 `speaker_adapter` 能力，宿主校验它支持的车道、入口和运行模式。
3. 宿主把插件加入 `speaker adapter registry`，并把可用性统一纳入插件启停规则。

#### 2.3.2 文本轮询型实时对话

1. 插件 runtime 从第三方平台轮询到一条新的文本请求。
2. 插件把请求包装成 `SpeakerTextTurnRequest`，携带实例、设备、会话、幂等键和文本内容。
3. 宿主 `speaker text turn bridge` 校验插件是否可用、绑定是否有效、请求是否重复。
4. 宿主把请求送入现有对话主链，得到统一回复结果。
5. 宿主返回 `SpeakerTextTurnResult`，插件决定用厂商 TTS、播放 URL 或等价方式播报。

#### 2.3.3 音频会话型实时对话

1. 插件声明自己具备原始音频或等价会话能力。
2. 插件通过 `speaker audio session bridge` 向宿主建立、推进或结束会话。
3. 宿主只负责会话桥接和统一语义，不负责厂商音频协议细节。

#### 2.3.4 统一控制命令

1. 宿主通过现有 `device_control` 主链定位 `DeviceBinding`。
2. 根据 `binding.plugin_id` 路由到对应 `speaker` 插件。
3. 插件把统一动作翻译成厂商动作。
4. 插件按统一结果模型回传执行结果和错误。

#### 2.3.5 runtime 健康与禁用

1. 插件 runtime 定期上报 heartbeat。
2. 宿主记录 `state / consecutive_failures / last_succeeded_at / last_error_summary`。
3. 插件被禁用后，宿主立即阻止新的 text turn、音频会话和控制执行。
4. 宿主保留查看配置、状态和历史排障信息的能力。

## 3. 组件和接口

### 3.1 核心组件

覆盖需求：1、3、4、5、6

- `speaker adapter plugin type or equivalent capability`
  说明一个插件是不是正式的 `speaker/voice` 适配插件。
- `speaker host runtime sdk`
  给第三方插件提供正式的宿主调用能力，只开放 `speaker` 相关接口。
- `speaker bridge services`
  把 discovery、text turn、audio session、command 都桥接到宿主统一主链。

### 3.2 数据结构

覆盖需求：1、2、3、4、5、6、7

#### 3.2.1 `SpeakerAdapterCapability`

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `adapter_code` | `string` | 是 | 适配器标识 | 宿主内唯一 |
| `supported_modes` | `list[string]` | 是 | 支持的接入模式 | 至少包含 `text_turn` 或 `audio_session` 之一 |
| `supported_domains` | `list[string]` | 是 | 支持设备域 | 至少包含 `speaker` |
| `requires_runtime_worker` | `boolean` | 是 | 是否依赖常驻 worker | 文本轮询型通常为 `true` |
| `supports_discovery` | `boolean` | 是 | 是否支持候选设备发现 | 与集成能力一致 |
| `supports_commands` | `boolean` | 是 | 是否支持统一控制命令 | 与 action 能力一致 |

#### 3.2.2 `SpeakerTextTurnRequest`

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `plugin_id` | `string` | 是 | 插件标识 | 必须可路由到当前插件 |
| `integration_instance_id` | `string` | 是 | 集成实例 id | 必须已存在且启用 |
| `device_id` | `string` | 否 | 宿主设备 id | 已绑定时必须提供 |
| `external_device_id` | `string` | 是 | 插件侧设备标识 | 用于绑定和审计 |
| `conversation_id` | `string` | 是 | 会话标识 | 插件侧稳定 |
| `turn_id` | `string` | 是 | 幂等键 | 同一请求不可重复入链 |
| `input_text` | `string` | 是 | 用户文本 | 非空 |
| `occurred_at` | `string` | 是 | 请求时间 | ISO 时间 |
| `context` | `object` | 否 | 厂商补充上下文 | 只允许 `speaker/voice` 相关字段 |

#### 3.2.3 `SpeakerTextTurnResult`

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `accepted` | `boolean` | 是 | 宿主是否接受本次 turn | - |
| `result_type` | `string` | 是 | 回复类型 | `text`、`audio_url`、`none`、`error` |
| `reply_text` | `string` | 否 | 标准化文本回复 | `result_type=text` 时优先提供 |
| `audio_url` | `string` | 否 | 可播放音频地址 | `result_type=audio_url` 时提供 |
| `error_code` | `string` | 否 | 错误码 | 出错时必须提供 |
| `error_message` | `string` | 否 | 错误信息 | 用户可理解 |
| `conversation_state` | `object` | 否 | 会话补丁 | 仅限通用字段 |

#### 3.2.4 `SpeakerAudioSessionEnvelope`

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `session_id` | `string` | 是 | 会话标识 | 全局可追踪 |
| `stage` | `string` | 是 | 会话阶段 | `open`、`append`、`close` |
| `audio_ref` | `string` | 否 | 音频片段引用 | 文本模式不得伪造 |
| `metadata` | `object` | 否 | 会话元数据 | 仅限通用字段 |

#### 3.2.5 `SpeakerCommandEnvelope`

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `plugin_id` | `string` | 是 | 插件标识 | 与绑定一致 |
| `binding_id` | `string` | 是 | 绑定标识 | 已存在 |
| `action` | `string` | 是 | 统一动作 | 必须来自现有 `speaker` 协议 |
| `params` | `object` | 否 | 动作参数 | 由统一协议约束 |

#### 3.2.6 `SpeakerRuntimeHeartbeat`

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `plugin_id` | `string` | 是 | 插件标识 | 已注册 |
| `integration_instance_id` | `string` | 是 | 实例标识 | 已存在 |
| `state` | `string` | 是 | runtime 状态 | `idle`、`running`、`degraded`、`error`、`stopped` |
| `consecutive_failures` | `integer` | 是 | 连续失败次数 | 大于等于 0 |
| `last_succeeded_at` | `string` | 否 | 上次成功时间 | ISO 时间 |
| `last_failed_at` | `string` | 否 | 上次失败时间 | ISO 时间 |
| `last_error_summary` | `string` | 否 | 最近错误摘要 | 便于排障 |

### 3.3 接口契约

覆盖需求：1、3、4、5、6

#### 3.3.1 manifest 能力声明

- 类型：Manifest Capability
- 标识：`capabilities.speaker_adapter`
- 输入：插件 manifest
- 输出：宿主可识别的 `speaker/voice` 能力
- 校验：
  - 至少声明一种支持模式
  - 文本轮询型必须声明 runtime worker 需求
  - 音频会话型不能只给文本入口
- 错误：
  - `plugin_manifest_invalid`

#### 3.3.2 `submit_speaker_text_turn(...)`

- 类型：宿主内置接口 / SDK 能力
- 标识：`speaker_host.submit_text_turn`
- 输入：`SpeakerTextTurnRequest`
- 输出：`SpeakerTextTurnResult`
- 校验：
  - 插件启用状态
  - 集成实例可用状态
  - 幂等键唯一性
  - 绑定和设备归属一致性
- 错误：
  - `plugin_disabled`
  - `speaker_binding_missing`
  - `speaker_turn_duplicated`
  - `speaker_text_turn_invalid`

#### 3.3.3 `report_speaker_runtime_heartbeat(...)`

- 类型：宿主内置接口 / SDK 能力
- 标识：`speaker_host.report_runtime_heartbeat`
- 输入：`SpeakerRuntimeHeartbeat`
- 输出：确认结果
- 校验：
  - 插件和实例必须存在
  - 状态必须来自允许集合
- 错误：
  - `plugin_disabled`
  - `speaker_runtime_invalid`

#### 3.3.4 `open_speaker_audio_session(...)`

- 类型：宿主内置接口 / SDK 能力
- 标识：`speaker_host.open_audio_session`
- 输入：`SpeakerAudioSessionEnvelope`
- 输出：会话确认结果
- 校验：
  - 插件必须声明 `audio_session`
  - 文本轮询型插件不得调用
- 错误：
  - `speaker_audio_session_unsupported`

## 4. 数据与状态模型

### 4.1 数据关系

- 一个 `speaker adapter` 插件可以对应多个 `integration_instance`。
- 一个 `integration_instance` 可以绑定多台 `speaker` 设备。
- 一个设备控制动作必须落到正式 `DeviceBinding(plugin_id + integration_instance_id)`。
- 文本轮询型对话请求必须能追溯到实例、设备和具体 turn。

### 4.2 状态流转

| 状态 | 含义 | 进入条件 | 退出条件 |
| --- | --- | --- | --- |
| `registered` | 插件已注册 | manifest 校验通过 | 启用或禁用 |
| `available` | 插件可执行 | 插件启用且实例可用 | 禁用、故障、卸载 |
| `degraded` | 插件降级 | heartbeat 连续失败但未彻底停止 | 成功恢复或进入 `error` |
| `error` | 插件异常 | runtime 严重失败 | 手动恢复或重新启动 |
| `disabled` | 插件禁用 | 家庭级或全局禁用 | 重新启用 |

## 5. 错误处理

### 5.1 错误类型

- `plugin_manifest_invalid`：manifest 缺少 `speaker/voice` 契约所需字段
- `speaker_text_turn_invalid`：text turn 输入不合法
- `speaker_turn_duplicated`：同一条 turn 重复提交
- `speaker_audio_session_unsupported`：文本插件误用音频入口
- `plugin_disabled`：插件被禁用但仍试图执行
- `speaker_runtime_invalid`：heartbeat 或 runtime 状态不合法

### 5.2 错误响应格式

```json
{
  "detail": "当前 speaker 插件已禁用，不能继续执行。",
  "error_code": "plugin_disabled",
  "field": "plugin_id",
  "timestamp": "2026-03-22T00:00:00Z"
}
```

### 5.3 处理策略

1. manifest 校验错误在插件注册阶段直接拦住。
2. text turn 输入错误在桥接层返回标准错误，不进入对话主链。
3. 禁用插件继续严格复用统一 `409/plugin_disabled` 语义。
4. runtime 心跳丢失或连续失败进入 `degraded` / `error`，不能继续假装正常服务。

## 6. 正确性属性

### 6.1 宿主不持有厂商协议知识

对于任何声明 `speaker_adapter` 的插件，宿主都只能依赖通用 DTO、绑定关系和统一 `speaker` 动作协议，不能依赖厂商指令表或私有 API。

**验证需求：** 需求 1、需求 5、需求 7

### 6.2 文本轮询型插件不能伪装成音频插件

对于任何只支持文本轮询的插件，系统都必须只允许它走 `text turn` 车道，不能把它标记成“原始音频实时对话已支持”。

**验证需求：** 需求 3、需求 4

### 6.3 插件禁用后不得继续执行

对于任何 `speaker/voice` 插件，只要进入禁用状态，新的 text turn、音频会话、设备控制和自动轮询执行都必须被阻止。

**验证需求：** 需求 6

## 7. 测试策略

### 7.1 单元测试

- manifest 能力声明校验
- `SpeakerTextTurnRequest` / `SpeakerTextTurnResult` DTO 校验
- 幂等键、防重复提交、禁用状态拦截

### 7.2 集成测试

- discovery / binding 与 `speaker_adapter` 能力联动
- 文本轮询型插件提交通用 `text turn`
- 统一设备控制路由到 `speaker` 插件
- heartbeat / 禁用 / 降级语义

### 7.3 端到端测试

- 第三方 `speaker` 插件从实例创建到设备绑定到对话回传整链路
- 插件禁用后自动执行被拦截
- 已有 `open-xiaoai-speaker` 主链不被破坏

### 7.4 验证映射

| 需求 | 设计章节 | 验证方式 |
| --- | --- | --- |
| `requirements.md` 需求 1 | `design.md` §2.2、§3.2、§3.3 | manifest 校验测试 |
| `requirements.md` 需求 2 | `design.md` §2.3.1、§4.1 | discovery / binding 集成测试 |
| `requirements.md` 需求 3 | `design.md` §2.3.2、§3.3.2 | text turn 集成测试 |
| `requirements.md` 需求 4 | `design.md` §2.3.3、§6.2 | 模式边界测试 |
| `requirements.md` 需求 5 | `design.md` §2.3.4、§3.2.5 | 设备控制集成测试 |
| `requirements.md` 需求 6 | `design.md` §2.3.5、§5、§6.3 | 禁用与 heartbeat 测试 |
| `requirements.md` 需求 7 | `design.md` §1.3、§6.1 | 人工审查与回归测试 |

## 8. 风险与待确认项

### 8.1 风险

- 如果宿主契约只补一半，最后还是会退化成“小米先单独放个特例”。
- 如果没有正式幂等键，文本轮询型插件很容易重复入链。
- 如果 runtime worker 不纳入统一启停规则，禁用插件后仍可能继续轮询。

### 8.2 待确认项

- 正式落地时，新入口是定义为新插件类型 `speaker-adapter`，还是定义为现有插件类型上的强能力块；本 Spec 允许两种实现，但都必须满足同样的校验和运行边界。
- 宿主给第三方插件暴露 `speaker_host` 能力时，最终采用进程内 SDK、子进程桥接还是内部 API 调用；本 Spec 不限制传输方式，只限制能力边界。
