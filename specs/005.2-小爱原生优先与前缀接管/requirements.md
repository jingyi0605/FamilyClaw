# 需求文档 - 小爱原生优先与前缀接管

状态：Draft

## 简介

当前 `Spec 005` 的默认行为是：

- 小爱音箱一旦被认领并激活
- 语音就进入 FamilyClaw 正式主链

这条链路本身没错，但它和 `mi-gpt` 已经验证过的用户体验不一样。

现在要补的是另一种交互模型：

- 普通对话继续交给小爱原生处理
- 只有命中特定前缀时，才由 FamilyClaw 接管

这件事看起来像一句 `if startswith(...)`，实际上不是。真正的问题有三个：

1. 这道闸门到底放 gateway 还是 `api-server`
2. 未命中前缀时，FamilyClaw 该保持多安静
3. 命中前缀后，如何继续复用现有正式主链，而不是又造一套“前缀专用语音链”

## 术语表

- **native-first 模式**：默认由小爱原生处理语音，命中特定前缀时才由 FamilyClaw 接管
- **接管前缀**：用来显式表达“这句话要交给 FamilyClaw”的前缀，例如“请”“请问”“帮我”
- **接管闸门**：判断这次语音是否应进入 FamilyClaw 正式主链的入口规则
- **native_passthrough**：未命中前缀时，FamilyClaw 不接管、不播报、不下发控制，保持静默
- **takeover**：命中前缀后，由 gateway 把这次语音正式交给 FamilyClaw 处理
- **调试转写**：gateway 用终端已经给出的最终文本，作为 `audio.commit.debug_transcript` 送入 `voice_pipeline`

## 范围说明

### In Scope

- 新增 native-first 模式定义
- 在 gateway 侧新增前缀接管闸门
- 新增接管前缀配置
- 定义命中前缀后的最小 takeover 事件流
- 定义未命中前缀时 FamilyClaw 的静默行为
- 继续复用现有 `voice_pipeline / router / fast_action / conversation`
- 补 gateway、`api-server`、测试和联调任务

### Out of Scope

- 本次不接入 `mi-gpt` 代码本身
- 本次不新增前端可视化配置页
- 本次不做家庭级动态前缀管理
- 本次不做“普通对话结果同步回 FamilyClaw”这种额外监听链
- 本次不重做 `voice-runtime` 或 `conversation` 主链

## 需求

### 需求 1：系统必须支持 native-first 交互模式

**用户故事：** 作为家庭成员，我希望普通问答仍由小爱自己处理，只有明确带前缀时才交给 FamilyClaw，这样日常使用更接近原生体验，也更符合 `mi-gpt` 已验证的习惯。

#### 验收标准

1. WHEN 小爱终端已认领并开启 native-first 模式 THEN System SHALL 默认不把普通语音请求送入 FamilyClaw 正式主链。
2. WHEN 用户说出未命中接管前缀的普通对话 THEN System SHALL 保持 FamilyClaw 侧静默，不主动播放、不主动打断。
3. WHEN 用户说出命中接管前缀的语句 THEN System SHALL 由 FamilyClaw 接管并进入正式语音主链。

### 需求 2：接管闸门必须放在 gateway 侧

**用户故事：** 作为架构维护者，我希望“这句该不该交给 FamilyClaw”在 gateway 就决定，而不是等文本进了 `api-server` 再退回，这样才能真正保持“默认原生、命中才接管”的行为语义。

#### 验收标准

1. WHEN gateway 收到终端最终文本 THEN System SHALL 在 gateway 侧完成前缀命中判断。
2. WHEN 文本未命中前缀 THEN gateway SHALL 不向 `api-server` 发起正式会话事件。
3. WHEN 文本命中前缀 THEN gateway SHALL 才向 `api-server` 发起 takeover 所需的最小事件。
4. WHEN 实现 native-first 模式 THEN System SHALL 不要求 `api-server/voice/router` 再承担“这句要不要接管”的第一道职责。

### 需求 3：命中前缀后的处理必须复用现有正式主链

**用户故事：** 作为后端维护者，我希望命中前缀后的处理仍然走现在的 `voice_pipeline / router / fast_action / conversation`，而不是为前缀模式再造一套半吊子链路。

#### 验收标准

1. WHEN 文本命中接管前缀 THEN System SHALL 继续复用现有 `voice_pipeline`。
2. WHEN 接管文本命中快路径设备控制或场景 THEN System SHALL 继续复用现有 `fast_action` 主链。
3. WHEN 接管文本不属于快路径 THEN System SHALL 继续复用现有 `conversation` 主链。
4. WHEN 实现前缀接管 THEN System SHALL 不新增一套“前缀专用对话”或“前缀专用设备控制”逻辑。

### 需求 4：未命中前缀时，FamilyClaw 必须保持静默

**用户故事：** 作为产品维护者，我希望未命中前缀时，FamilyClaw 不做假处理、不发多余控制，这样才能不和小爱原生逻辑抢话。

#### 验收标准

1. WHEN 文本未命中接管前缀 THEN System SHALL 不创建 FamilyClaw 侧正式语音会话。
2. WHEN 文本未命中接管前缀 THEN System SHALL 不下发 `play.start`、`play.stop` 或 `play.abort`。
3. WHEN 文本未命中接管前缀 THEN System SHALL 不进入 `conversation`、`fast_action` 或其他业务处理。
4. WHEN native-first 模式开启 THEN System SHALL 明确记录这次会话被视为 `native_passthrough` 或等价状态，避免后续排查时一片黑。

### 需求 5：接管前缀必须是受控配置，而不是散落硬编码

**用户故事：** 作为后续维护者，我希望接管前缀由清晰配置收口，而不是散落在多个文件里写死，这样以后改词、补词不会到处翻代码。

#### 验收标准

1. WHEN gateway 启用 native-first 模式 THEN System SHALL 通过受控配置读取接管前缀列表。
2. WHEN 接管前缀列表为空 THEN System SHALL 拒绝把 native-first 模式视为已正确启用，或回退到显式禁用状态。
3. WHEN 命中前缀后需要进入正式主链 THEN System SHALL 支持可控地保留或剥离前缀文本。
4. WHEN 后续要调整前缀 THEN System SHALL 只需要改一处明确配置，而不是改多处业务代码。

### 需求 6：新增模式不能破坏现有默认接管模式

**用户故事：** 作为项目负责人，我希望 native-first 是一种明确模式，而不是把现有已跑通的正式主链悄悄改坏。

#### 验收标准

1. WHEN native-first 模式关闭 THEN System SHALL 保持当前“认领后默认进入 FamilyClaw 正式主链”的行为不变。
2. WHEN native-first 模式开启 THEN System SHALL 只改变接管闸门，不改变现有快路径、慢路径和播放主链的核心边界。
3. WHEN 新模式实现完成 THEN System SHALL 能通过自动化测试证明两种模式都能工作，而不是只保一边。

## 非功能需求

### 非功能需求 1：边界清晰

1. WHEN native-first 模式实现完成 THEN gateway SHALL 只承担接管判定，不承担快路径、慢路径、权限或身份判断。
2. WHEN `api-server` 接收到 takeover 请求 THEN System SHALL 仍按现有业务边界处理，不反向理解 `open-xiaoai` 私有协议。

### 非功能需求 2：可排查

1. WHEN 一次语音没有被 FamilyClaw 接管 THEN System SHALL 能看出是“未命中前缀”而不是“链路坏了”。
2. WHEN 一次语音命中前缀但接管失败 THEN System SHALL 能区分是 gateway 判定失败、takeover 失败还是正式主链失败。

### 非功能需求 3：兼容与演进

1. WHEN 后续增加更多终端适配器 THEN System SHALL 把 native-first 视为终端入口策略，而不是把业务主链写死在 `open-xiaoai` 私有实现里。
2. WHEN 后续需要做家庭级或终端级前缀配置 THEN 当前方案 SHALL 能在现有配置基础上演进，而不是推翻重来。

## 成功定义

- gateway 已经能在 native-first 模式下先做前缀接管判定
- 未命中前缀时，FamilyClaw 正式主链保持静默
- 命中前缀后，仍然复用现有 `voice_pipeline / fast_action / conversation`
- 默认接管模式和 native-first 模式都能稳定通过测试
