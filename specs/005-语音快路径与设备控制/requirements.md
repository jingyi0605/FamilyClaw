# 需求文档 - 语音快路径与设备控制

状态：Draft

## 简介

项目现在已经有文本对话主链、设备控制、场景执行、家庭上下文和实时通道，但语音入口还是断的。

用户已经先把 `open-xiaoai` 官方 demo 的硬件链路跑通了，这意味着现在真正该做的，不再是“验证音箱能不能说话”，而是把它变成 FamilyClaw 的正式语音终端。

这次需求的核心是三件事：

- 初版把 `open-xiaoai` 固定为唯一语音终端适配器
- 新增 `open-xiaoai-gateway`，只做协议翻译和播放控制中转
- 把核心业务继续留在 `voice_pipeline / conversation / device_action / scene` 内

这份需求文档要把这些边界写死，避免后面又退回“demo 能跑就行”的脏路子。

## 术语表

- **System**：FamilyClaw API Server
- **语音终端**：家庭中的语音输入输出设备。初版专指刷入 `open-xiaoai` Client 的小爱音箱
- **`open-xiaoai-gateway`**：独立进程，监听 `4399`，把 `open-xiaoai` 私有 WebSocket 协议翻译成系统内部统一语音事件
- **终端适配器**：连接具体硬件协议和内部统一语音协议的桥。初版唯一实现是 `open-xiaoai-gateway`
- **语音运行时**：独立于业务 API 的本地推理进程，负责流式 ASR 和声纹推理
- **语音快路径**：明确、低歧义、以设备控制或场景触发为主的语音链路，不走完整 LLM 主链
- **语音慢路径**：复杂问答、家庭记忆查询、需要生成式回复的链路，最终复用现有 `conversation`
- **声纹识别**：对说话人做注册、验证和候选识别的能力
- **语音会话**：一次从终端唤醒、录音、转写、路由到执行或回答结束的完整交互

## 范围说明

### In Scope

- 初版以 `open-xiaoai` 作为唯一正式语音终端适配器
- 新增 `open-xiaoai-gateway`，监听 `4399`，只负责协议翻译、终端状态同步和播放控制中转
- 为终端建立正式的接入协议、终端绑定和房间归属模型
- 引入本地语音运行时，承接流式 ASR、声纹注册与验证
- 支持语音快路径设备控制和场景触发
- 支持复杂语音问题回流到现有 `conversation` 主链
- 支持内部 `play / stop / abort` 到终端播放控制的正式链路
- 支持声纹注册、验证、低置信回退和高风险动作保护
- 记录语音会话、转写结果、路由结果、播放结果、执行结果和关键时延

### Out of Scope

- 不把 `open-xiaoai` 官方 demo server 作为正式生产服务
- 不在小爱音箱上承载业务逻辑、设备控制逻辑或权限逻辑
- 不开放任意脚本执行、系统控制、刷机后系统升级等危险能力
- 初版不接入 `mi-gpt`
- 不做完整多轮自然打断、抢话、多人分离和连续对讲系统
- 不做原始音频默认长期保存
- 不做绕过现有设备确认和场景守卫的语音特权链路

## 需求

### 需求 1：系统必须通过 `open-xiaoai-gateway` 接入初版语音终端

**用户故事：** 作为项目维护者，我希望小爱音箱通过独立网关接入，而不是让 `api-server` 直接吃 `open-xiaoai` 私有协议，这样后面协议变化、设备异常和危险能力都能被隔离。

#### 验收标准

1. WHEN `open-xiaoai` Client 连接到 `open-xiaoai-gateway` THEN System SHALL 通过监听 `4399` 的正式入口建立终端连接。
2. WHEN 网关收到 `open-xiaoai` 的音频流、状态事件或中断事件 THEN System SHALL 把它们翻译成内部统一语音会话事件，而不是把外部私有字段直接泄漏到 `api-server`。
3. WHEN `voice_pipeline` 发出 `play / stop / abort` 控制 THEN `open-xiaoai-gateway` SHALL 把它们翻译成 `open-xiaoai` 可识别的播放命令。
4. WHEN 终端断线、重连或状态变化 THEN System SHALL 能更新终端在线状态，并避免旧会话残留。
5. WHEN 终端接入进入正式系统 THEN System SHALL 保存终端标识、所属家庭、所属房间、适配器类型、终端能力和最近心跳状态。

### 需求 2：系统必须支持语音终端播放控制、停止和打断回执

**用户故事：** 作为家庭成员，我希望系统在回答、播报或执行确认时能真正从音箱播出来，也能在我再次说话或主动中断时立刻停下来，而不是后台以为播了，前台其实乱套。

#### 验收标准

1. WHEN 系统需要向终端播放确认语、文本回复或提示音 THEN System SHALL 通过正式播放控制链路向 `open-xiaoai-gateway` 下发播放请求。
2. WHEN 终端开始播放、播放完成、播放失败或被打断 THEN System SHALL 记录回执并关联到对应语音会话。
3. WHEN 用户在播放过程中再次唤醒或说话 THEN System SHALL 支持中断当前播放，并继续进入新的语音会话。
4. WHEN `play / stop / abort` 控制失败 THEN System SHALL 返回明确错误，而不是静默假装执行成功。

### 需求 3：系统必须支持语音快路径设备控制和场景触发

**用户故事：** 作为家庭成员，我希望说“开客厅灯”“关空调”“进入睡前模式”时系统立刻执行，而不是先走一遍大模型聊天再慢吞吞返回。

#### 验收标准

1. WHEN 语音转写结果命中明确的设备控制或场景触发命令 THEN System SHALL 直接进入语音快路径，不走完整生成式聊天链路。
2. WHEN 快路径命中已有设备或场景 THEN System SHALL 复用现有 `device_action` 或 `scene` 服务执行，而不是另造一套控制实现。
3. WHEN 目标设备、房间或动作不明确 THEN System SHALL 先追问或回退，不允许猜一个设备直接执行。
4. WHEN 快路径命中高风险动作，如门锁解锁 THEN System SHALL 继续使用现有高风险确认与守卫机制，不因为语音入口而放宽。

### 需求 4：复杂语音问题必须复用现有对话主链

**用户故事：** 作为家庭成员，我希望问“奶奶今天吃药了吗”“朵朵明天几点上课”时，系统能像网页聊天一样调用家庭记忆、提案和后续能力，而不是在语音里变成另一套脑子。

#### 验收标准

1. WHEN 语音输入不属于快路径控制 THEN System SHALL 把最终文本和上下文转入现有 `conversation` 主链处理。
2. WHEN 慢路径进入 `conversation` THEN System SHALL 复用现有会话、提案、记忆、任务草稿和后续动作策略，而不是平行实现一套语音专用对话逻辑。
3. WHEN 慢路径需要较长时间返回结果 THEN System SHALL 先给出确认反馈，再返回完整回答。
4. WHEN `conversation` 链路失败 THEN System SHALL 返回可理解的降级提示，并保留语音会话与错误记录供排查。

### 需求 5：系统必须支持声纹注册、验证与低置信回退

**用户故事：** 作为家庭管理员，我希望系统能用声纹提升身份判断准确度，但又不能因为一次低质量录音就把高风险动作误判到某个家庭成员头上。

#### 验收标准

1. WHEN 管理员为成员注册声纹 THEN System SHALL 支持多段样本录入，并把结果保存为可更新、可停用的生物识别资料。
2. WHEN 一次语音会话进入身份判断 THEN System SHALL 输出声纹候选、置信度和所用模型来源，而不是只给一个拍脑袋结果。
3. WHEN 声纹置信度不足或与家庭上下文冲突 THEN System SHALL 回退到匿名或追问模式，不允许直接执行敏感动作。
4. WHEN 系统保存声纹资料 THEN System SHALL 只保存加密引用、摘要或受控模板，不允许把原始 embedding 或原始音频明文长期落库。

### 需求 6：语音链路必须与房间、设备、场景和家庭上下文正式集成

**用户故事：** 作为后端维护者，我希望语音判断能结合终端房间、成员在家状态、静默时段和儿童保护这些现有上下文，而不是光看一句转写文本瞎猜。

#### 验收标准

1. WHEN 系统做语音身份融合或快路径路由 THEN System SHALL 通过正式 `context` 入口读取终端房间、成员状态、家庭模式和关键保护开关。
2. WHEN 快路径命中设备控制或场景触发 THEN System SHALL 把执行结果继续写入现有事件、审计或记忆链路。
3. WHEN 家庭处于静默时段、访客模式、儿童保护或老人关怀特殊状态 THEN System SHALL 按现有规则决定是否执行、降级或改成追问。
4. WHEN 同一家庭多个终端同时在线 THEN System SHALL 基于终端房间和上下文做范围收缩，避免跨房间误控。

### 需求 7：部署方式必须保持本地优先且支持后续适配器演进

**用户故事：** 作为项目负责人，我希望初版先用 `open-xiaoai` 快速落地，但后续如果要接更多设备，不能把今天的业务核心全部推倒重来。

#### 验收标准

1. WHEN 语音能力上线 THEN System SHALL 采用“`open-xiaoai` 终端 + `open-xiaoai-gateway` + `voice-runtime` + `api-server voice_pipeline`”的部署方式。
2. WHEN `open-xiaoai-gateway` 或 `voice-runtime` 不可用 THEN System SHALL 让语音能力进入受限降级，但文本聊天、设备管理和其他系统能力仍可继续使用。
3. WHEN 后续接入新的终端适配器 THEN System SHALL 保持 `voice_pipeline / conversation / device_action / scene` 这些业务主链边界不变。
4. WHEN 初版范围评审 THEN System SHALL 明确 `mi-gpt` 只作为后续插件候选，不进入当前交付。

## 非功能需求

### 非功能需求 1：性能

1. WHEN 终端命中唤醒词 THEN System SHALL 在 `300ms` 内给出本地可感知反馈，这个反馈必须由终端或网关侧完成。
2. WHEN 用户开始说话 THEN System SHALL 在 `700ms` 内返回第一段可用的流式转写或明确的“正在识别”状态。
3. WHEN 快路径命中明确设备动作 THEN System SHALL 在用户说完话后 `1.2s` 内给出首个有效执行回执。
4. WHEN 系统下发播放请求 THEN System SHALL 在 `500ms` 内拿到终端已开始播放或明确失败的第一条回执。

### 非功能需求 2：可靠性

1. WHEN `open-xiaoai-gateway`、`voice-runtime`、Home Assistant 或 `conversation` 链路出现异常 THEN System SHALL 把失败收口为明确错误状态，不允许静默吞掉。
2. WHEN 终端断线重连或会话中断 THEN System SHALL 能正确结束旧会话，并避免重复执行同一条快路径动作。
3. WHEN 同一段音频或同一条播放控制被重复发送 THEN System SHALL 通过幂等键或会话状态避免重复落执行。

### 非功能需求 3：安全与可维护性

1. WHEN `open-xiaoai-gateway` 暴露给终端 THEN System SHALL 只开放音频输入、播放输出、停止播放、状态上报这些白名单能力。
2. WHEN 终端适配器新增或替换 THEN System SHALL 只扩展适配器层，不修改快慢路径业务核心。
3. WHEN 需要排查一次误触发、漏触发或播放异常 THEN System SHALL 能通过语音会话记录、结构化日志和关联业务记录快速定位。

## 成功定义

- `open-xiaoai` 能作为初版唯一终端稳定接入正式链路
- `open-xiaoai-gateway` 能稳定完成协议翻译、播放控制和中断回执
- 简单语音控制能稳定命中快路径，并复用现有设备与场景执行链路
- 复杂语音问题能稳定回到现有 `conversation` 主链
- 声纹低置信度不会直接放行高风险动作
- `mi-gpt` 不会污染当前交付边界，只保留成后续插件位
