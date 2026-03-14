# Spec 005 - 语音快路径与设备控制

状态：Draft

## 这份 Spec 解决什么问题

`FamilyClaw` 现在已经有文本对话、设备控制、场景执行、上下文聚合和实时通道，但语音入口还是缺口。

真正的问题不是“要不要做语音”，而是下面这几件事怎么收口：

- 小爱音箱怎么作为正式语音终端接进来
- 音频怎么进入系统而不把 `api-server` 搞成协议垃圾桶
- 简单命令怎么快速打到现有 `device_action / scene`
- 复杂问题怎么稳定回到现有 `conversation`
- 声纹怎么做成身份增强，而不是新的高风险漏洞
- 播放、停止、打断怎么走正式链路，而不是各写一套私货

如果边界不先立住，后面一定会长出三种垃圾代码：

1. 把 `open-xiaoai` 私有协议直接塞进 `api-server`
2. 把设备控制、播放控制、对话回复都堆到音箱侧脚本里
3. 为了“先跑起来”继续沿用官方 demo server，当成正式生产服务

这三种都不该留活口。

## 当前项目现状判断

基于现有代码和已有规划，当前判断很明确：

- 这是一个**模块化单体**后端，不需要为了语音入口先拆一堆微服务
- `conversation`、`device_action`、`scene`、`context`、`realtime` 都已经是可复用的正式主链
- 当前没有正式 `voice` 模块，也没有终端模型、语音会话模型和声纹资料链路
- 当前没有 Redis、MQ 这类分布式基础设施，初版设计必须老老实实按单机可跑来定

换句话说：

> 真问题不是“做一个能说话的音箱”，而是“把音箱收编成正式终端，业务核心继续留在 FamilyClaw 内部”。

## 这次的核心判断

### 【核心判断】

✅ 值得做：语音是家庭入口，`open-xiaoai` 已经帮我们把硬件链路打通，现在该做的是把它变成正式终端接入层，而不是把业务搬到音箱上。

### 【关键洞察】

- 数据结构：语音不是新业务岛，它只是新的输入输出通道，最后仍然要落回 `context / conversation / device_action / scene / scheduler`
- 复杂度：真正该独立的是 **`open-xiaoai-gateway` 和 `voice-runtime`**，不是把整个后端拆碎
- 风险点：最大的风险不是识别率，而是把私有协议、播放控制和危险设备能力混成一锅

### 【Linus式方案】

1. 初版只支持一个正式终端适配器：`open-xiaoai`
2. `open-xiaoai` 只当话筒和音箱，不承载业务逻辑
3. 新增独立进程 `open-xiaoai-gateway`，监听 `4399`，只做协议翻译
4. `voice_pipeline` 继续留在 `api-server` 内，复用现有业务主链
5. 后续要兼容更多设备，再抽象统一 `voice_terminal_adapter` 插件协议

## 已确认前提

用户已经完成 `P0` 验证，下面这些不是纸上谈兵，而是已验证事实：

- 设备可刷机
- `open-xiaoai` Client 可稳定连接
- 麦克风输入正常
- 音箱播放正常
- 中断小爱播报正常

这意味着初版已经可以不再讨论“硬件能不能跑”，而是直接进入网关和主链接入设计。

## 技术架构结论

初版技术架构写死为四层：

1. **小爱音箱 + `open-xiaoai` Client**
   - 只负责音频输入、播放输出、播放打断和终端状态
   - 不放业务逻辑，不做设备控制决策

2. **`open-xiaoai-gateway`**
   - 独立进程，监听 `4399`
   - 把 `open-xiaoai` 私有 WebSocket 协议翻译成 FamilyClaw 内部统一语音事件
   - 把内部 `play / stop / abort` 控制翻译回 `open-xiaoai` 命令
   - 裁掉任意脚本执行、系统控制等危险能力

3. **`voice-runtime`**
   - 独立于 `api-server`
   - 承接流式 ASR、声纹注册、声纹验证
   - 第一版继续按本地中文栈设计

4. **`api-server` 内的 `voice_pipeline`**
   - 负责会话、终端绑定、身份融合、快慢路径分流
   - 快路径复用 `device_action / scene`
   - 慢路径复用 `conversation`

最终运行形态是：

- `api-server`
- `worker`
- `voice-runtime`
- `open-xiaoai-gateway`
- 一个或多个已刷机的小爱终端

## 初版范围写死

- 初版唯一正式语音终端适配器：`open-xiaoai`
- 初版唯一正式终端接入方式：`open-xiaoai-gateway`
- 初版只开放：音频输入、播放输出、播放停止、播放中断、终端状态上报
- 初版不开放：终端侧脚本执行、系统升级、任意命令转发、音箱侧业务编排

## 演进路线

- **V1**
  - `open-xiaoai` 作为唯一终端适配器
  - 跑通 `gateway -> voice_pipeline -> voice-runtime`

- **V2**
  - 抽象统一 `voice_terminal_adapter` 插件协议
  - 允许新增其他终端适配器，但不改 `voice_pipeline` 业务边界

- **V3 候选**
  - 评估 `mi-gpt` 或其后继方案作为“普通用户路径”适配器
  - 但它不进入当前初版交付，也不影响 `open-xiaoai` 主链设计

## 这次明确不做什么

- 不把 `open-xiaoai` 官方 demo server 当正式生产服务
- 不把业务逻辑下沉到小爱终端
- 不在音箱侧做设备控制、场景判断、权限判断
- 不做多终端大一统兼容层的过度设计
- 不因为后续可能接 `mi-gpt`，现在就把所有接口抽象到看不懂

## 主要文档

- `requirements.md`：把初版范围、网关职责、快慢路径、声纹和审计要求写清楚
- `design.md`：把 `open-xiaoai-gateway`、`voice-runtime`、`voice_pipeline` 的连接关系写清楚
- `tasks.md`：按 `P0 -> P1 -> P2` 的顺序拆任务
- `docs/20260314-语音技术选型与边界说明.md`：把为什么选这个方向写死
- `docs/20260314-open-xiaoai接入草案与演进路线.md`：把网关协议、终端模型、禁用能力和后续演进路线写死

## 参考来源

- [open-xiaoai](https://github.com/idootop/open-xiaoai)
- [mi-gpt](https://github.com/idootop/mi-gpt)
- [FunASR 官方仓库](https://github.com/modelscope/FunASR)
- [3D-Speaker 官方仓库](https://github.com/modelscope/3D-Speaker)
