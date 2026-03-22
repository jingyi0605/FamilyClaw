# 需求文档 - migpt_xiaoai_speaker 第三方插件

状态：Draft

## 简介

`mi-gpt` 这条路解决的是“新型号小爱音箱不刷机也能接入”的问题，但它不是宿主现有 `open-xiaoai` 那种网关实时事件模型。

参考源码后，可以确认它的核心模式是：

- 用小米账号登录。
- 通过 MiNA / MIoT 查询设备和控制音箱。
- 通过 MiNA 会话记录轮询拿到最新文本请求。
- 再用小米自带 TTS 或第三方 TTS 音频播放把回复播回去。

所以，这个插件要解决的不是“如何伪装成原始音频实时插件”，而是“如何把这套文本轮询型实时对话，干净地接到 `005.9` 的正式契约上”。

## 术语表

- **MiNA**：小米音箱会话和播放相关能力。
- **MIoT**：小米 IoT 设备动作与属性能力。
- **device profile**：针对某一类或某一型号小爱音箱维护的指令映射和能力差异配置。
- **polling cursor**：插件记录自己已经处理到哪条会话消息的游标。
- **text turn runtime**：插件的常驻轮询 worker，负责发现新消息并提交到宿主。

## 范围说明

### In Scope

- 小米账号配置和实例级连接配置
- 设备发现与正式绑定
- 文本轮询型实时对话
- 统一 `speaker` 动作执行
- runtime 心跳、降级和风控状态
- 机型 profile 管理

### Out of Scope

- 首版不做原始音频流接入
- 不改宿主核心去兼容小米私有协议
- 不在宿主里新增小米专用业务表意模型

## 需求

### 需求 1：插件必须通过正式实例配置承载小米账号和运行参数

**用户故事**
作为家庭管理员，我希望这个插件像其他正式集成一样，通过实例配置承载小米账号和轮询参数，而不是靠宿主环境变量或硬编码。

#### 验收标准

1. WHEN 用户创建 `migpt_xiaoai_speaker` 集成实例 THEN System SHALL 通过正式配置 schema 采集账号、设备筛选和运行参数。
2. WHEN 插件实例保存成功 THEN System SHALL 只把这些配置保存在插件实例作用域，而不是写进宿主核心特例字段。
3. WHEN 后续新增运行参数 THEN System SHALL 优先通过插件配置 schema 扩展，而不是修改宿主页面硬编码表单。

### 需求 2：插件必须通过小米云能力发现和同步可接入音箱

**用户故事**
作为用户，我希望插件能从我的小米账号下发现可接入的小爱音箱，并把它们作为正式候选设备加入平台。

#### 验收标准

1. WHEN 插件执行设备发现 THEN System SHALL 通过插件自身的小米云逻辑拉取候选音箱，而不是要求宿主写小米专用发现逻辑。
2. WHEN 插件返回候选音箱 THEN System SHALL 通过 `005.9` 和现有集成主链把它们变成正式候选设备。
3. WHEN 用户确认绑定某台音箱 THEN System SHALL 创建带 `plugin_id + integration_instance_id` 的正式 `DeviceBinding`。

### 需求 3：插件必须支持文本轮询型实时对话

**用户故事**
作为用户，我希望新型号小爱音箱在不刷机的情况下也能和 FamilyClaw 实时对话，哪怕底层是文本轮询方案。

#### 验收标准

1. WHEN 插件 runtime 轮询到一条新的小米会话消息 THEN System SHALL 把它转换成正式 `SpeakerTextTurnRequest` 提交给宿主。
2. WHEN 宿主返回标准回复结果 THEN 插件 SHALL 使用小米 TTS 或音频播放方式把结果播回去。
3. WHEN 同一条小米消息被重复读到 THEN 插件 SHALL 通过稳定游标或幂等键避免重复提交。
4. WHEN 插件不具备原始音频能力 THEN System SHALL 明确把它标记为文本轮询型，而不是音频会话型。

### 需求 4：插件必须通过 MiNA / MIoT 完成统一 `speaker` 动作

**用户故事**
作为平台开发者，我希望这个插件收到统一 `speaker` 动作时，自己把动作翻译成 MiNA / MIoT 调用，而不是要求宿主理解小米指令细节。

#### 验收标准

1. WHEN 宿主对绑定的小爱音箱执行统一 `speaker` 动作 THEN 插件 SHALL 通过自己的 action 入口完成翻译和执行。
2. WHEN 不同机型动作指令不同 THEN 插件 SHALL 通过 profile 选择正确指令，而不是要求宿主加机型分支。
3. WHEN 执行成功或失败 THEN 插件 SHALL 按宿主统一结果模型返回，不得自造一套错误协议。

### 需求 5：插件必须管理机型 profile，不把指令表写死宿主

**用户故事**
作为后续维护者，我希望不同小爱机型之间的 `ttsCommand`、`wakeUpCommand`、`playingCommand` 差异都收口在插件里。

#### 验收标准

1. WHEN 插件接入不同型号小爱音箱 THEN 插件 SHALL 能根据型号命中相应 profile。
2. WHEN 某个新型号只需要补指令映射 THEN 开发者 SHALL 主要修改插件 profile，而不是修改宿主核心。
3. WHEN 某型号能力未知或部分缺失 THEN 插件 SHALL 明确降级，而不是假装全部支持。

### 需求 6：插件必须暴露可观测 runtime 和风控状态

**用户故事**
作为运维人员，我希望知道插件当前是不是在线、有没有连续失败、是不是因为风控或登录失效而降级。

#### 验收标准

1. WHEN 插件 runtime 正常轮询 THEN 插件 SHALL 定期通过宿主正式接口上报 heartbeat。
2. WHEN 小米账号失效、接口风控或连续请求失败 THEN 插件 SHALL 把状态上报成 `degraded` 或 `error`，并附带错误摘要。
3. WHEN 插件被禁用 THEN 插件 SHALL 停止新的轮询提交，并遵守宿主统一禁用规则。

### 需求 7：所有小米特例逻辑必须留在插件内

**用户故事**
作为架构维护者，我希望 `migpt_xiaoai_speaker` 再复杂，也只能复杂在插件里，不能把宿主核心重新污染回去。

#### 验收标准

1. WHEN 审查宿主核心 THEN System SHALL 看不到小米账号登录、cookie 管理、MiNA 会话轮询和 MIoT 指令表。
2. WHEN 审查插件实现 THEN System SHALL 能看到上述小米逻辑都留在插件目录内。
3. WHEN 新增另一个厂商音箱插件 THEN 开发者 SHALL 复用宿主 `speaker/voice` 契约，而不是继续沿用小米特例。

## 非功能需求

### 非功能需求 1：稳定性

1. WHEN 小米云接口短暂抖动 THEN 插件 SHALL 有有限重试、降级和恢复机制，不能把宿主主链一起拖死。
2. WHEN 轮询 worker 出错 THEN 插件 SHALL 能继续上报健康状态或错误摘要，不能静默失踪。

### 非功能需求 2：实时体验

1. WHEN 用户在音箱上发起请求 THEN 插件 SHALL 尽量在可接受延迟内完成轮询、提交和播报。
2. WHEN 长文本回复被过早打断或播放状态不准 THEN 插件 SHALL 允许通过 profile 或运行参数调整检测策略。

### 非功能需求 3：可维护性

1. WHEN 新增机型兼容 THEN 插件 SHALL 优先通过 profile 扩展。
2. WHEN 宿主升级 `speaker/voice` 契约 THEN 插件 SHALL 主要调整宿主 SDK 调用层，而不是散改所有业务模块。

## 成功定义

- `migpt_xiaoai_speaker` 可以不刷机接入更多小爱音箱。
- 首版走正式的文本轮询型实时对话车道，不伪装成原始音频方案。
- 宿主核心不新增小米专用入口、专用状态模型或专用协议分支。
