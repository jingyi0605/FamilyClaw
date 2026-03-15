# 20260315-open-xiaoai接入与网关初始化启动手册

## 这份文档解决什么问题

这份手册只解决两件事：

1. 怎么把已经能跑的 `open-xiaoai` 终端接到 FamilyClaw 的 `open-xiaoai-gateway`
2. 怎么把 `open-xiaoai-gateway` 初始化、配置、启动，并确认它真的工作了

别把这件事想复杂。当前正式链路就是：

```text
小爱音箱(open-xiaoai Client)
  -> open-xiaoai-gateway :4399
  -> api-server /api/v1
  -> 设备待添加列表
  -> 用户认领
  -> api-server /api/v1/realtime/voice
  -> voice_pipeline
```

当前边界也写死了：

- 小爱只当话筒和音箱
- `open-xiaoai-gateway` 只做协议翻译、发现上报、播放中转
- 业务逻辑仍然留在 FamilyClaw
- 终端不再靠环境变量硬绑 `household_id / terminal_id / room_id / terminal_name`

## 一、开始前先准备好这些东西

### 1. 终端侧前提

- 小爱音箱已经刷好并能运行 `open-xiaoai` Client
- 终端能访问到网关主机的 `4399` 端口
- 终端和网关尽量在同一局域网内

### 2. 服务侧前提

- `api-server` 已经可用，并且能提供 `http://<host>:<port>/api/v1`
- `api-server` 的 realtime voice 入口已可用：`ws://<host>:<port>/api/v1/realtime/voice`
- 当前家庭里至少已经有一个房间

最后这条不是废话。因为认领音箱时必须选择房间，没有房间就没法完成接入。

### 3. 网关鉴权前提

`api-server` 和 `open-xiaoai-gateway` 必须使用同一个 `voice gateway token`。

`api-server` 侧配置项：

```text
FAMILYCLAW_VOICE_GATEWAY_TOKEN
```

`open-xiaoai-gateway` 侧配置项：

```text
FAMILYCLAW_OPEN_XIAOAI_GATEWAY_VOICE_GATEWAY_TOKEN
```

两边值不一致时，发现上报、绑定查询和正式语音链路都会被拒绝。

## 二、open-xiaoai 终端怎么接到咱们的网关

### 1. 终端实际连的就是网关地址

上游 `open-xiaoai` Rust Client 的入口很简单，它启动时直接吃一个 WebSocket 地址参数，然后持续重连那个地址。

也就是说，终端侧真正要填的不是 `api-server` 地址，而是：

```text
ws://<gateway_host>:4399
```

如果你的网关部署在 `192.168.31.20`，那终端侧目标地址就是：

```text
ws://192.168.31.20:4399
```

### 2. 终端连上网关后，网关会自动做什么

终端一旦连上来，网关会立刻用官方 `open-xiaoai` RPC 做三次探测：

1. `get_version` 取 `runtime_version`
2. `run_shell -> echo $(micocfg_model)` 取 `model`
3. `run_shell -> echo $(micocfg_sn)` 取 `sn`

然后网关会生成稳定指纹：

```text
open_xiaoai:<model>:<sn>
```

例如：

```text
open_xiaoai:LX06:1234567890
```

接着它会把这台设备作为“待添加设备”上报到 `api-server`。

### 3. 首次接入时，为什么音箱不会立刻进入正式语音链路

这是故意的，不是坏了。

未认领前，网关只做发现上报，不会做下面这些事：

- 不连接 `/api/v1/realtime/voice`
- 不上报 `terminal.online`
- 不启动正式录音
- 不把 `kws / instruction / record` 翻译进正式语音会话

原因很简单：还没绑定到哪个家庭、哪个房间、叫什么名字，硬进主链就是脏数据。

### 4. 用户怎么把它接进家庭

操作入口在 `user-web` 的“设备与集成”页面。

用户看到的是“发现到的新音箱”区块，不是工程字段。

实际操作顺序：

1. 打开“设备与集成”
2. 看到新发现的音箱
3. 填“设备名称”
4. 选“所在房间”
5. 点“添加到家庭”

认领成功后，`api-server` 会：

- 创建或复用 `Device`
- 创建或复用 `DeviceBinding`
- 用 `Device.id` 作为正式 `terminal_id`

然后网关下一轮轮询会拿到正式绑定结果：

- `household_id`
- `terminal_id`
- `room_id`
- `terminal_name`

拿到这些之后，它才会进入正式语音链路。

### 5. 认领成功后，网关会做什么

认领完成后，网关会顺序执行：

1. 连接 `ws://.../api/v1/realtime/voice`
2. query 中带上 `household_id / terminal_id / fingerprint`
3. 用 `x-voice-gateway-token` 建立鉴权
4. 上报 `terminal.online`
5. 调用 `start_recording`
6. 开始把录音流 `Stream(tag=\"record\")` 翻译成 `audio.append`
7. 把文本 `instruction` 翻译成 `audio.commit`

只要这一步成功，这台音箱就已经从“待添加设备”变成“正式语音终端”了。

## 三、open-xiaoai-gateway 怎么初始化

### 1. 代码位置

网关代码在：

[`apps/open-xiaoai-gateway`](/C:/Code/FamilyClaw/apps/open-xiaoai-gateway)

入口在：

[`open_xiaoai_gateway/main.py`](/C:/Code/FamilyClaw/apps/open-xiaoai-gateway/open_xiaoai_gateway/main.py)

安装后还会暴露命令行脚本：

```text
familyclaw-open-xiaoai-gateway
```

### 2. 建议的初始化步骤

下面用 PowerShell 示例，别自己脑补成别的花活。

### 步骤 1：进入网关目录

```powershell
Set-Location C:\Code\FamilyClaw\apps\open-xiaoai-gateway
```

### 步骤 2：创建虚拟环境

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 步骤 3：安装网关

```powershell
python -m pip install -U pip
python -m pip install -e .
```

如果你不想装成可执行脚本，也至少保证当前环境里能导入 `open_xiaoai_gateway` 包。

### 3. 必须知道的配置项

网关所有环境变量前缀都是：

```text
FAMILYCLAW_OPEN_XIAOAI_GATEWAY_
```

最小必配项如下：

| 环境变量 | 说明 | 默认值 | 是否建议显式设置 |
| --- | --- | --- | --- |
| `FAMILYCLAW_OPEN_XIAOAI_GATEWAY_LISTEN_HOST` | 网关监听地址 | `0.0.0.0` | 建议 |
| `FAMILYCLAW_OPEN_XIAOAI_GATEWAY_LISTEN_PORT` | 网关监听端口 | `4399` | 建议 |
| `FAMILYCLAW_OPEN_XIAOAI_GATEWAY_API_SERVER_HTTP_URL` | `api-server` HTTP 基地址，包含 `/api/v1` | `http://127.0.0.1:8000/api/v1` | 必须 |
| `FAMILYCLAW_OPEN_XIAOAI_GATEWAY_API_SERVER_WS_URL` | `api-server` realtime voice WS 地址 | `ws://127.0.0.1:8000/api/v1/realtime/voice` | 必须 |
| `FAMILYCLAW_OPEN_XIAOAI_GATEWAY_VOICE_GATEWAY_TOKEN` | 网关鉴权 token | `dev-voice-gateway-token` | 必须 |
| `FAMILYCLAW_OPEN_XIAOAI_GATEWAY_CLAIM_POLL_INTERVAL_SECONDS` | 认领轮询间隔 | `5` | 可选 |
| `FAMILYCLAW_OPEN_XIAOAI_GATEWAY_LOG_LEVEL` | 日志级别 | `INFO` | 建议 |

录音和播放相关项通常先用默认值，除非你明确知道设备端参数已经变了：

- `FAMILYCLAW_OPEN_XIAOAI_GATEWAY_RECORDING_ENABLED`
- `FAMILYCLAW_OPEN_XIAOAI_GATEWAY_RECORDING_PCM`
- `FAMILYCLAW_OPEN_XIAOAI_GATEWAY_RECORDING_CHANNELS`
- `FAMILYCLAW_OPEN_XIAOAI_GATEWAY_RECORDING_BITS_PER_SAMPLE`
- `FAMILYCLAW_OPEN_XIAOAI_GATEWAY_RECORDING_SAMPLE_RATE`
- `FAMILYCLAW_OPEN_XIAOAI_GATEWAY_RECORDING_PERIOD_SIZE`
- `FAMILYCLAW_OPEN_XIAOAI_GATEWAY_RECORDING_BUFFER_SIZE`
- `FAMILYCLAW_OPEN_XIAOAI_GATEWAY_PLAYBACK_SAMPLE_RATE`
- `FAMILYCLAW_OPEN_XIAOAI_GATEWAY_PLAYBACK_CHANNELS`
- `FAMILYCLAW_OPEN_XIAOAI_GATEWAY_PLAYBACK_BITS_PER_SAMPLE`
- `FAMILYCLAW_OPEN_XIAOAI_GATEWAY_PLAYBACK_PERIOD_SIZE`
- `FAMILYCLAW_OPEN_XIAOAI_GATEWAY_PLAYBACK_BUFFER_SIZE`

### 4. 明确不要再配的旧变量

下面这些旧思路现在已经废了，不要再配：

- `FAMILYCLAW_OPEN_XIAOAI_GATEWAY_HOUSEHOLD_ID`
- `FAMILYCLAW_OPEN_XIAOAI_GATEWAY_TERMINAL_ID`
- `FAMILYCLAW_OPEN_XIAOAI_GATEWAY_ROOM_ID`
- `FAMILYCLAW_OPEN_XIAOAI_GATEWAY_TERMINAL_NAME`

现在的正式流程是“自动发现 -> 前端认领 -> 认领后入链路”，不是“环境变量把终端身份写死”。

### 5. 一个最小可用的 `.env` 示例

如果你打算在网关目录里放 `.env`，可以用下面这个最小模板：

```dotenv
FAMILYCLAW_OPEN_XIAOAI_GATEWAY_LISTEN_HOST=0.0.0.0
FAMILYCLAW_OPEN_XIAOAI_GATEWAY_LISTEN_PORT=4399
FAMILYCLAW_OPEN_XIAOAI_GATEWAY_API_SERVER_HTTP_URL=http://127.0.0.1:8000/api/v1
FAMILYCLAW_OPEN_XIAOAI_GATEWAY_API_SERVER_WS_URL=ws://127.0.0.1:8000/api/v1/realtime/voice
FAMILYCLAW_OPEN_XIAOAI_GATEWAY_VOICE_GATEWAY_TOKEN=dev-voice-gateway-token
FAMILYCLAW_OPEN_XIAOAI_GATEWAY_CLAIM_POLL_INTERVAL_SECONDS=5
FAMILYCLAW_OPEN_XIAOAI_GATEWAY_LOG_LEVEL=INFO
```

如果 `api-server` 不在本机，把上面的 `127.0.0.1` 改成真实地址。

## 四、网关怎么启动

### 1. 直接用 Python 启动

```powershell
Set-Location C:\Code\FamilyClaw\apps\open-xiaoai-gateway
.\.venv\Scripts\Activate.ps1
python -m open_xiaoai_gateway.main
```

### 2. 用安装后的命令行脚本启动

```powershell
Set-Location C:\Code\FamilyClaw\apps\open-xiaoai-gateway
.\.venv\Scripts\Activate.ps1
familyclaw-open-xiaoai-gateway
```

两种方式本质一样，别搞成两套配置。

### 3. 启动成功时应该看到什么

最先应该看到类似日志：

```text
open-xiaoai-gateway listening on 0.0.0.0:4399
```

这说明网关至少已经把 WebSocket 服务端口真的监听起来了。

## 五、第一次接入时怎么验收

按这个顺序验，不要东一榔头西一棒子。

### 1. 先看网关有没有收到终端连接

终端接上后，网关应该开始做自动探测和发现上报。

这一步成功时，前端“设备与集成”页面里应该能看到新音箱。

### 2. 再看前端能不能完成认领

在“发现到的新音箱”里填写：

- 设备名称
- 所在房间

然后点“添加到家庭”。

### 3. 最后看网关有没有切到正式语音链路

认领成功后，网关日志应该出现类似信息：

```text
connect api-server realtime.voice terminal_id=...
claimed terminal activated fingerprint=... household_id=... terminal_id=...
```

如果这两条没有出现，说明“发现到了”但“没真正激活”。

### 4. 成功后的最终表现

完整成功时会同时满足下面几点：

1. 这台音箱不再出现在“发现到的新音箱”列表里
2. 它已经出现在正式设备列表里
3. 网关已经连接 realtime voice
4. 唤醒、录音、转写、播放开始进入正式主链

## 六、常见问题怎么排

### 1. 前端一直看不到新音箱

先查这几件事：

1. 终端是不是连到了正确的 `ws://<gateway_host>:4399`
2. 网关是不是已经启动，并且真的监听在 `4399`
3. `FAMILYCLAW_OPEN_XIAOAI_GATEWAY_API_SERVER_HTTP_URL` 是否可达
4. `FAMILYCLAW_OPEN_XIAOAI_GATEWAY_VOICE_GATEWAY_TOKEN` 是否和 `api-server` 一致
5. 终端和网关是否在同一局域网，或者路由是否放通

如果连发现列表都没有，先别怀疑语音链路，先把发现上报打通。

### 2. 发现到了，但添加失败

常见错误和含义：

- `voice discovery not found`
  - 这条待添加记录已经失效，刷新页面再试
- `room not found`
  - 选的房间不存在
- `room must belong to the same household`
  - 选错家庭或房间了
- `voice terminal already claimed by another household`
  - 这台设备已经被别的家庭认领

### 3. 认领成功了，但网关没进入正式语音链路

重点看下面几项：

1. `FAMILYCLAW_OPEN_XIAOAI_GATEWAY_API_SERVER_WS_URL` 是否正确
2. `api-server` 的 `/api/v1/realtime/voice` 是否可达
3. gateway token 是否一致
4. 认领后查询到的 `fingerprint -> DeviceBinding -> Device.id` 是否一致

现在 realtime voice 会严格校验：

- `fingerprint`
- `terminal_id`
- `household_id`

只要有一个对不上，就会被拒绝，不会装作成功。

### 4. 已激活，但没有录音上送

优先查这几项：

1. `FAMILYCLAW_OPEN_XIAOAI_GATEWAY_RECORDING_ENABLED` 是不是被关了
2. 终端侧 `start_recording` 是否成功
3. 终端是否真的在发送 `Stream(tag=\"record\")`
4. 录音参数是否被改坏了，尤其是 `sample_rate / channels / bits_per_sample`

### 5. 终端能连上，但播放不正常

当前播放分两种：

1. `tts_text`
   - 网关通过受控 `run_shell` 调 `/usr/sbin/tts_play.sh`
2. `audio_bytes`
   - 网关先发 `start_play`，再发 `Stream(tag=\"play\")`

如果播放异常，优先确认：

1. 终端侧 `run_shell` / `start_play` 是否正常
2. 播放参数和设备实际支持是否一致
3. 终端侧 `playing` 事件是否还能正常回传

## 七、建议的最小联调顺序

别跳步骤，老老实实按顺序来：

1. 启动 `api-server`
2. 启动 `open-xiaoai-gateway`
3. 让 `open-xiaoai` Client 连到 `ws://<gateway_host>:4399`
4. 在前端确认看到“发现到的新音箱”
5. 完成设备名称和房间认领
6. 观察网关是否激活正式链路
7. 再做唤醒、录音、播放联调

这个顺序的好处是，任何一步坏了都能立刻定位在“发现、认领、绑定、正式语音链路”中的哪一层。

## 八、最后一句

如果你发现自己又想给网关补 `household_id / terminal_id / room_id / terminal_name` 这种硬绑定配置，说明你又走回老路了。

现在正确路径已经不是那套了：

> 先发现，再认领，最后再让它进入正式语音链路。
