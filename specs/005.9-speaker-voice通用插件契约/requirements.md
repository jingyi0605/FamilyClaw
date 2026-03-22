# 需求文档 - speaker/voice 通用插件契约

状态：Draft

## 简介

项目已经有 `speaker` 设备类型、统一设备控制入口、集成实例和插件系统，但“语音对话接入”这部分还没有真正完成通用化。

现状是两层断裂：

- 设备接入这层，已经开始围绕 `integration_instance + plugin_id + binding` 工作。
- 语音对话这层，仍然偏向 `open-xiaoai` 现有链路，没有给第三方插件一条正式、稳定、能长期维护的入口。

这会直接造成三个问题：

1. 新型号小爱音箱如果不能刷机，就只能继续走特例。
2. 宿主核心会不断吸收厂商协议细节，越改越脏。
3. “实时对话”到底是文本轮询还是原始音频流，没有正式边界，后面一定会写成混乱补丁。

这个 Spec 的目标很明确：宿主要把 `speaker/voice` 的正式插件契约补齐，让第三方插件能用统一方式接入。

## 术语表

- **speaker adapter 插件**：声明自己能接入音箱或语音终端的插件实现。
- **文本轮询型实时对话**：插件通过第三方平台的会话列表、消息记录或等价 API 轮询到文本请求，再把文本 turn 提交给宿主处理。
- **音频会话型实时对话**：插件能拿到原始音频流或等价双向音频会话控制，再和宿主协作处理。
- **text turn**：一次用户文本请求及其对应的宿主回复过程。
- **runtime heartbeat**：插件运行时定期上报的健康信息，用来判断 worker 是否在线、是否降级、是否出错。

## 范围说明

### In Scope

- `speaker/voice` 插件正式类型或等价能力声明
- discovery / binding / text turn / command / runtime health 契约
- 文本轮询型和音频会话型两条接入车道
- 插件禁用、错误、可观测性、回归要求

### Out of Scope

- 小米账号登录、cookie、serviceToken 等厂商实现细节
- 某个音箱厂商的指令表或机型兼容表
- ASR / TTS / 声纹算法本身的重写

## 需求

### 需求 1：宿主必须提供正式的 `speaker/voice` 插件能力声明

**用户故事**
作为平台维护者，我希望 `speaker/voice` 接入不再靠历史约定和私有入口，而是有正式的插件契约，这样第三方插件才能按规范接进来。

#### 验收标准

1. WHEN 宿主加载一个声明 `speaker/voice` 能力的插件 THEN System SHALL 能从 manifest 识别它支持的接入车道、运行模式和设备域。
2. WHEN 插件缺少 `speaker/voice` 能力所需的关键字段 THEN System SHALL 在 manifest 校验阶段直接拒绝，而不是运行时再猜。
3. WHEN 第三方开发者查看插件开发文档 THEN System SHALL 能明确告诉他这类插件该声明哪些入口、哪些能力、哪些配置作用域。

### 需求 2：discovery 和 binding 必须完全脱离 `open-xiaoai` 专用硬编码

**用户故事**
作为平台开发者，我希望音箱发现和绑定都走正式插件链路，而不是继续在宿主里保留“小爱专用 if/else”。

#### 验收标准

1. WHEN 宿主列出可用的 `speaker` 集成插件 THEN System SHALL 基于插件能力声明决定是否展示，而不是硬编码某个插件 id。
2. WHEN 某个 `speaker` 插件返回候选设备 THEN System SHALL 能把这些候选项放进统一 discovery / binding 主链，而不是走专用 API。
3. WHEN 后续新增另一个 `speaker` 插件 THEN System SHALL 不需要新增厂商分支也能进入同一条 discovery / binding 主链。

### 需求 3：宿主必须提供文本轮询型实时对话正式入口

**用户故事**
作为第三方音箱插件开发者，我希望像 `mi-gpt` 这种通过云端会话轮询拿到文本请求的方案，也能正式接入宿主实时对话。

#### 验收标准

1. WHEN 插件轮询到一条新的文本请求 THEN System SHALL 提供正式的 `text turn` 提交入口，让插件把请求送进宿主。
2. WHEN 宿主处理完一个 `text turn` THEN System SHALL 能把标准化回复结果返回给插件，而不是要求插件自己读核心私有状态。
3. WHEN 同一条请求被插件重复提交 THEN System SHALL 能基于正式幂等键或等价机制避免重复入链。

### 需求 4：宿主必须保留音频会话型入口，但不能强迫所有插件伪装成音频插件

**用户故事**
作为架构维护者，我希望宿主同时支持文本轮询型和音频会话型两类接入，但不能把没有原始音频能力的插件硬塞进音频模型里。

#### 验收标准

1. WHEN 插件只支持文本轮询型实时对话 THEN System SHALL 允许它只声明文本车道，而不要求声明音频流入口。
2. WHEN 插件支持原始音频会话 THEN System SHALL 提供独立的音频会话契约，而不是复用文本轮询接口硬凑。
3. WHEN 某插件不具备原始音频能力 THEN System SHALL 不得把它标记成“音频实时对话已支持”。

### 需求 5：设备控制和命令回传必须继续走统一 `speaker` 语义

**用户故事**
作为平台维护者，我希望音箱控制继续走统一 `speaker` 设备协议，而不是每个厂商自己定义一套动作。

#### 验收标准

1. WHEN 宿主对 `speaker` 设备执行 `turn_on`、`turn_off`、`play_pause`、`set_volume` 等动作 THEN System SHALL 继续走统一设备控制入口和统一结果模型。
2. WHEN `speaker` 插件收到控制请求 THEN System SHALL 只要求插件把统一动作翻译成厂商动作，而不是重定义动作语义。
3. WHEN 插件返回控制结果或失败信息 THEN System SHALL 继续复用统一的 `plugin_id`、`binding`、错误码和状态回写语义。

### 需求 6：runtime 健康、禁用和错误语义必须纳入统一插件规则

**用户故事**
作为运维和排障人员，我希望 `speaker/voice` 插件的运行时状态、禁用行为和错误返回都遵守现有插件统一规则，而不是另造一套。

#### 验收标准

1. WHEN `speaker/voice` 插件进入常驻运行、后台轮询或 worker 模式 THEN System SHALL 提供正式 heartbeat / health 上报能力。
2. WHEN 插件被禁用 THEN System SHALL 阻止新的实时对话提交、自动轮询执行和设备控制执行，并继续允许查看配置和状态。
3. WHEN 插件不可用但对象仍存在 THEN System SHALL 统一返回现有插件规则定义的禁用语义，而不是伪装成 404 或参数错误。

### 需求 7：宿主与厂商插件的职责边界必须可审计

**用户故事**
作为后续接手的人，我希望一眼看清哪些逻辑是宿主通用能力，哪些逻辑必须留在厂商插件里，避免核心再次被污染。

#### 验收标准

1. WHEN 审查宿主核心代码 THEN System SHALL 只能看到通用 `speaker/voice` 契约、桥接和校验逻辑，不能看到厂商协议细节。
2. WHEN 审查厂商插件代码 THEN System SHALL 能看到厂商鉴权、消息轮询、机型指令、设备 profile 等专有逻辑都留在插件内。
3. WHEN 新增另一个厂商 `speaker` 插件 THEN 开发者 SHALL 优先复用宿主通用契约，而不是修改核心新增厂商分支。

## 非功能需求

### 非功能需求 1：向后兼容

1. WHEN 宿主补齐新契约 THEN System SHALL 不破坏现有 `open-xiaoai-speaker` 已经接入的 discovery、binding 和控制主链。
2. WHEN 旧插件暂时还没迁到新契约 THEN System SHALL 允许保留短期兼容层，但必须写清退出条件。

### 非功能需求 2：实时性

1. WHEN 文本轮询型插件提交新的 `text turn` THEN System SHALL 让请求尽快进入现有实时对话主链，不能额外再绕长链路。
2. WHEN 宿主返回回复结果 THEN System SHALL 提供足够轻的结果模型，避免插件为了拿一条回复再查多套私有状态。

### 非功能需求 3：可维护性和可观测性

1. WHEN 新增一种 `speaker` 接入方式 THEN System SHALL 主要通过扩展能力声明和 DTO 完成，而不是复制整条业务链。
2. WHEN 排查问题 THEN System SHALL 能从插件实例、设备绑定、text turn、runtime heartbeat 四个维度追踪全链路。

## 成功定义

- 宿主正式支持文本轮询型和音频会话型两类 `speaker/voice` 插件。
- `mi-gpt` 这类方案可以通过正式契约接入，而不是修改核心加特例。
- 后续新增免刷机音箱插件时，不需要宿主继续增加厂商协议分支。
