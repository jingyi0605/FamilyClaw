# 20260314-open-xiaoai接入草案与演进路线

## 1. 目标

这份草案只回答四个问题：

1. `open-xiaoai` 到底怎么接进 FamilyClaw
2. 网关协议怎么定
3. 终端模型和禁用能力怎么写死
4. 后面如果要接 `mi-gpt`，边界怎么留

## 2. 最终结论

初版接法写死如下：

```text
小爱音箱(open-xiaoai Client)
    -> open-xiaoai-gateway :4399
    -> api-server /api/v1/realtime/voice
    -> voice_pipeline
    -> voice-runtime / conversation / device_action / scene
```

关键原则：

- `open-xiaoai` 只当终端，不当业务服务
- 网关只做协议翻译，不做业务编排
- `api-server` 不直接理解 `open-xiaoai` 私有协议
- 后续新终端必须适配统一内部语音协议，而不是反过来污染主链

## 3. 为什么选这种接法

### 3.1 为什么不是直接用官方 demo server

因为 demo server 是给验证链路用的，不是给正式系统长期维护的。

正式系统要解决的是：

- 终端状态管理
- 统一会话事件
- 播放与打断回执
- 危险能力裁剪
- 后续插件扩展

demo server 没有义务替我们扛这些事。

### 3.2 为什么网关优先独立进程

因为这层协议会脏，而且一定会变。

把它独立出来有三个好处：

1. 协议变化只影响网关
2. 危险能力能在设备最近的一层被掐掉
3. 后续想接别的终端时，能自然长成适配器体系

### 3.3 为什么不是把业务放到音箱上

因为真正的业务定义在 FamilyClaw 里：

- 什么是快路径
- 什么动作有风险
- 什么场景可以触发
- 什么上下文要参与判断

这些都不该放在小爱侧脚本里。

## 4. 网关职责

`open-xiaoai-gateway` 初版职责固定为四类：

1. 维护 `open-xiaoai` 终端连接
2. 翻译外部私有协议到内部统一语音事件
3. 翻译内部 `play / stop / abort` 到终端命令
4. 上报终端状态、播放回执和中断事件

明确不做：

- 不做设备控制决策
- 不做对话路由
- 不做权限判断
- 不做任意脚本执行
- 不做系统升级或重启控制

## 5. 内部统一协议草案

### 5.1 网关 -> `api-server`

统一事件集合：

- `terminal.online`
- `terminal.offline`
- `terminal.heartbeat`
- `session.start`
- `audio.append`
- `audio.commit`
- `session.cancel`
- `playback.interrupted`
- `playback.receipt`

事件样例：

```json
{
  "type": "session.start",
  "session_id": "voice-session-id",
  "terminal_id": "xiaoai-living-room",
  "seq": 1,
  "payload": {
    "sample_rate": 16000,
    "codec": "pcm_s16le"
  },
  "ts": "2026-03-14T10:00:00+08:00"
}
```

### 5.2 `api-server` -> 网关

统一事件集合：

- `session.ready`
- `asr.partial`
- `asr.final`
- `route.selected`
- `play.start`
- `play.stop`
- `play.abort`
- `agent.done`
- `agent.error`

播放事件样例：

```json
{
  "type": "play.start",
  "session_id": "voice-session-id",
  "terminal_id": "xiaoai-living-room",
  "seq": 18,
  "payload": {
    "mode": "tts_text",
    "text": "好的，已经打开客厅灯。"
  },
  "ts": "2026-03-14T10:00:02+08:00"
}
```

### 5.3 映射原则

- 外部私有字段只允许存在于网关
- 内部事件字段保持稳定
- 每个播放回执都必须带 `session_id`
- 打断事件优先级高于普通播放完成事件

## 6. 终端模型草案

初版终端模型最少要有这些字段：

- `terminal_id`
- `terminal_code`
- `household_id`
- `room_id`
- `name`
- `adapter_type = open_xiaoai`
- `transport_type = gateway_ws`
- `capabilities`
- `status`
- `last_seen_at`

初版能力白名单：

- `audio_input`
- `audio_output`
- `playback_stop`
- `playback_abort`
- `heartbeat`

明确禁止的能力：

- `shell_exec`
- `script_exec`
- `system_upgrade`
- `reboot_control`
- `business_logic`

## 7. 安全边界

这部分必须写死，不然实现时最容易烂。

### 7.1 允许

- 音频上送
- 终端播放
- 停止当前播放
- 打断当前播放
- 状态上报

### 7.2 禁止

- 任意脚本执行
- 任意 shell 命令
- 系统升级控制
- 重启控制
- 直接设备控制
- 直接场景触发
- 终端侧业务逻辑扩展

## 8. 演进路线

### 8.1 V1

- 唯一终端适配器：`open-xiaoai`
- 唯一网关：`open-xiaoai-gateway`
- 先跑通：
  - 终端接入
  - 音频上送
  - 播放控制
  - 快路径
  - 慢路径

### 8.2 V2

- 抽象 `voice_terminal_adapter` 插件协议
- 允许新增：
  - `open_xiaoai_adapter`
  - 其他硬件适配器
- 但 `voice_pipeline`、`conversation`、`device_action`、`scene` 不改边界

### 8.3 V3 候选：`mi-gpt`

`mi-gpt` 可以保留为后续插件候选，但现在不该进主线，原因很简单：

- 它当前仓库已停止维护
- 官方也更推荐 `open-xiaoai`
- 如果现在同时接两套小米路线，只会把主链搞脏

所以它的定位只能是：

- 后续普通用户路径候选
- 插件层候选
- 非当前交付范围

## 9. 实施顺序

按顺序来，别乱：

1. P0：硬件链路验证
2. P1：实现 `open-xiaoai-gateway`
3. P2：接入 `voice_pipeline`
4. P3：补慢路径、声纹和审计
5. P4：再谈别的终端适配器

## 10. 一句话版本

> `open-xiaoai` 是终端，`open-xiaoai-gateway` 是翻译层，FamilyClaw 才是业务核心。
