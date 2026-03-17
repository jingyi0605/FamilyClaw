# 设计文档 - 内嵌语音运行时与声纹链路收口

状态：Draft

## 1. 概述

### 1.1 目标

- 把当前独立 `voice-runtime` 的短生命周期运行时逻辑内嵌到 `api-server`
- 保持 `005.3` 现有建档、识别、对话前身份解析与降级语义不变
- 明确主事件循环、线程池阻塞任务和数据库 Session 的边界
- 删除独立 `voice-runtime` 目录和远程分支，彻底收口到 `embedded / disabled`

### 1.2 覆盖需求

- `requirements.md` 需求 1：可切换 runtime 模式
- `requirements.md` 需求 2：内嵌音频缓存与音频产物落盘
- `requirements.md` 需求 3：阻塞任务下沉
- `requirements.md` 需求 4：业务语义保持不变
- `requirements.md` 需求 5：迁移可观测与可收口
- `requirements.md` 需求 6：迁移完成后回写 `005.3`

### 1.3 技术约束

- 后端：FastAPI + WebSocket + SQLAlchemy，同步 DB 仍是项目现状
- 事件循环边界：遵守 `001.6` 和 `app.core.blocking`
- 现有声纹 provider：继续使用 `sherpa-onnx + weSpeaker/ResNet34`
- 数据库迁移：本方案不要求新增表结构，优先复用现有 `voice_session_registry` 与 `voiceprint` 数据表
- 向后兼容：不破坏现有 `voice_runtime_client` 调用点，不破坏现有 `disabled` 降级语义

## 2. 架构

### 2.1 系统结构

迁移后的结构分成四层：

1. **WebSocket 接入层**
   - 继续在 `voice_realtime_service` 收 `session.start / audio.append / audio.commit`
   - 继续把事件交给 `voice_pipeline_service`

2. **Runtime 抽象层**
   - `voice_runtime_client` 继续作为上层唯一入口
   - 内部根据配置选择 `embedded / disabled`

3. **Embedded Runtime 层**
   - 管会话音频缓存
   - 管 commit 时的音频落盘与元数据生成
   - 不做声纹决策，不做业务路由

4. **Voiceprint 业务层**
   - 继续负责建档、识别、验证和降级
   - 所有同步重活通过 blocking helper 下沉

### 2.2 模块职责

| 模块 | 职责 | 输入 | 输出 |
| --- | --- | --- | --- |
| `voice.realtime_service` | 接收 WebSocket 事件并转交 pipeline | 网关事件 | 语音命令事件 |
| `voice.runtime_client` | 屏蔽 runtime 模式差异 | 会话、终端、音频参数 | runtime start/append/finalize 结果 |
| `voice.embedded_runtime` | 在 `api-server` 内做音频缓存和 commit 落盘 | 分片音频、会话上下文 | transcript、audio artifact |
| `voice.embedded_runtime_store` | 保存短生命周期音频缓存 | session_id、音频字节 | 会话缓冲状态 |
| `voiceprint.service` | 建档、识别、验证 | audio artifact path、DB 数据 | profile、识别结果、错误状态 |
| `app.core.blocking` | 执行同步 I/O、CPU 任务 | blocking 函数、policy | 线程池结果 |

### 2.3 关键流程

#### 2.3.1 会话开始与分片追加

1. `voice_realtime_service` 收到 `session.start`
2. `voice_pipeline_service` 调 `voice_runtime_client.start_session(...)`
3. 当 mode 为 `embedded` 时，本地创建一条 `EmbeddedAudioSession`
4. 收到 `audio.append` 后，本地 decode base64，写入 `bytearray`
5. 此阶段只更新统计信息，不落盘、不做声纹、不碰数据库

#### 2.3.2 commit 与音频产物生成

1. `voice_pipeline_service` 收到 `audio.commit`
2. 调 `voice_runtime_client.finalize_session(...)`
3. 当 mode 为 `embedded` 时：
   - 从 `EmbeddedAudioSessionStore` 取出内存音频
   - 用 `run_blocking(...)` 在线程池里执行：
     - 校验 codec / frame
     - 拼接 wav
     - 写文件
     - 计算 `sha256`
     - 计算时长
     - 构造 runtime transcript 结果
4. 返回结果后，继续走当前 `pipeline` 的 transcript、artifact、建档或识别链路

#### 2.3.3 声纹建档与识别

1. `pipeline` 收到 commit 结果并记录 audio artifact
2. 建档链路走异步包装的 `async_process_voiceprint_enrollment_sample(...)`
3. 普通对话识别链路走异步包装的 `async_identify_household_member_by_voiceprint(...)`
4. 两者内部都通过 blocking helper 下沉同步 provider 和同步 DB
5. 返回结果后继续使用现有 `VoiceIdentityResolution` 和现有降级策略

## 3. 组件和接口

### 3.1 核心组件

覆盖需求：1、2、3、4、5

- `VoiceRuntimeBackend`：统一 backend 协议，定义 `start_session / append_audio / finalize_session`
- `EmbeddedVoiceRuntimeBackend`：新增本地实现
- `EmbeddedAudioSessionStore`：新增短生命周期音频缓存
- `VoiceprintAsyncFacade`：新增异步包装层，负责调用 blocking helper

### 3.2 数据结构

覆盖需求：2、3、4

#### 3.2.1 `EmbeddedAudioSession`

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `session_id` | `str` | 是 | runtime 会话 id | 非空 |
| `terminal_id` | `str` | 是 | 终端 id | 非空 |
| `household_id` | `str` | 是 | 家庭 id | 非空 |
| `room_id` | `str \| None` | 否 | 房间 id | 可空 |
| `sample_rate` | `int` | 是 | 采样率 | `>=1` |
| `codec` | `str` | 是 | 编码格式 | 首版只支持 `pcm_s16le` |
| `channels` | `int` | 是 | 声道数 | `>=1` |
| `session_purpose` | `str` | 是 | 会话用途 | `conversation / voiceprint_enrollment` |
| `enrollment_id` | `str \| None` | 否 | 建档任务 id | 建档时必填 |
| `audio_bytes` | `bytearray` | 是 | 原始音频缓存 | 短生命周期 |
| `chunk_count` | `int` | 是 | 分片数 | `>=0` |
| `received_bytes` | `int` | 是 | 接收字节数 | `>=0` |

#### 3.2.2 `Voice Runtime Mode`

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `voice_runtime_mode` | `str` | 是 | 当前 runtime 模式 | `embedded / disabled` |
| `voice_runtime_artifacts_root` | `str` | 否 | 内嵌 runtime 落盘目录 | mode=`embedded` 时有效 |
| `voice_runtime_timeout_ms` | `int` | 否 | runtime 超时 | `>=100` |

### 3.3 接口契约

覆盖需求：1、2、3、4

#### 3.3.1 `VoiceRuntimeBackend.start_session`

- 类型：Function
- 标识：`VoiceRuntimeBackend.start_session`
- 输入：会话、终端、采样率、codec、channels
- 输出：`VoiceRuntimeStartResult`
- 校验：
  - `embedded` 模式下创建本地缓存会话
- 错误：
  - codec 不支持
  - backend 创建失败

#### 3.3.2 `VoiceRuntimeBackend.append_audio`

- 类型：Function
- 标识：`VoiceRuntimeBackend.append_audio`
- 输入：会话、终端、`chunk_base64`、`chunk_bytes`
- 输出：`VoiceRuntimeAppendResult`
- 校验：
  - `embedded` 模式下 decode base64 并追加到 `bytearray`
  - 不允许 session 和 terminal 不匹配
- 错误：
  - session 不存在
  - base64 不合法
  - codec 不支持

#### 3.3.3 `VoiceRuntimeBackend.finalize_session`

- 类型：Function
- 标识：`VoiceRuntimeBackend.finalize_session`
- 输入：会话、终端、`debug_transcript`
- 输出：`VoiceRuntimeTranscriptResult`
- 校验：
  - `embedded` 模式下必须返回稳定的 transcript/artifact 结构
  - `disabled` 模式下保留当前 debug transcript 兜底语义
- 错误：
  - 音频帧无效
  - 会话不存在
  - 落盘失败
  - blocking helper 超时

#### 3.3.4 `async_process_voiceprint_enrollment_sample`

- 类型：Function
- 标识：`voiceprint.async_process_voiceprint_enrollment_sample`
- 输入：`enrollment_id`、`artifact_path`、`transcript_text` 等
- 输出：`VoiceprintEnrollmentProcessResult`
- 校验：
  - 在线程池中创建独立 DB Session
  - 不允许复用当前 WebSocket 持有的 Session
- 错误：
  - provider 不可用
  - 音频文件不存在
  - DB 写入失败

#### 3.3.5 `async_identify_household_member_by_voiceprint`

- 类型：Function
- 标识：`voiceprint.async_identify_household_member_by_voiceprint`
- 输入：`household_id`、`artifact_path`
- 输出：`VoiceprintIdentificationRead`
- 校验：
  - 在线程池中执行同步 provider 逻辑
  - 返回结构继续兼容现有 `VoiceIdentityService`
- 错误：
  - provider 不可用
  - 音频产物缺失
  - 超时

## 4. 数据与状态模型

### 4.1 数据关系

- `VoiceSessionState` 继续承担业务会话状态，不直接保存大块音频字节
- `EmbeddedAudioSession` 只承担短生命周期音频缓存
- commit 成功后，`EmbeddedAudioSession` 产生 `Audio Artifact`
- `Audio Artifact` 继续被 `voiceprint.service` 和 `voice.identity_service` 消费

### 4.2 状态流转

| 状态 | 含义 | 进入条件 | 退出条件 |
| --- | --- | --- | --- |
| `active` | 正在接收音频分片 | `session.start` 成功 | `commit / cancel / failure` |
| `finalizing` | 正在线程池里落盘和生成结果 | 收到 `audio.commit` | finalize 完成或失败 |
| `closed` | 会话缓存已释放 | finalize、cancel 或 failure 后清理 | 无 |

## 5. 错误处理

### 5.1 错误类型

- `embedded_session_not_found`：内嵌 runtime 找不到会话缓存
- `embedded_runtime_unsupported_codec`：codec 不支持
- `embedded_runtime_artifact_failed`：音频落盘失败
- `voiceprint_provider_unavailable`：声纹 provider 不可用
- `blocking_timeout`：阻塞任务超时

### 5.2 错误响应格式

```json
{
  "detail": "voice runtime unavailable",
  "error_code": "voice_runtime_unavailable",
  "timestamp": "2026-03-17T00:00:00Z"
}
```

### 5.3 处理策略

1. 输入验证错误：直接返回当前链路已有错误码，不新增花哨语义。
2. 音频落盘失败：返回 `voice_runtime_unavailable` 或现有降级结果，保持对上层兼容。
3. 声纹 provider 失败：继续走 `005.3` 既有上下文兜底逻辑。
4. 阻塞任务超时：记录 timeout 日志，并按当前链路的失败或降级路径收口。

## 6. 正确性属性

### 6.1 业务语义不变

对于任何 `conversation` 或 `voiceprint_enrollment` 会话，系统都应该继续遵守 `005.3` 当前的 transcript、artifact、建档、识别和降级顺序，而不是因为 runtime 改成本地实现就改变业务路径。

**验证需求：** 需求 4

### 6.2 事件循环不承载同步重活

对于任何音频落盘、声纹 embedding、建档或识别调用，系统都应该通过 blocking helper 下沉执行，不允许直接在 WebSocket 事件循环中同步跑完。

**验证需求：** 需求 3

### 6.3 缓存生命周期可释放

对于任何已 commit、cancel 或失败的 runtime 会话，系统都应该在收口后释放该会话的内存音频缓存，避免无上限堆积。

**验证需求：** 需求 2、需求 5

## 7. 测试策略

### 7.1 单元测试

- `EmbeddedAudioSessionStore` 的 start / append / finalize / cleanup
- runtime mode 选择逻辑
- artifact 生成逻辑
- blocking helper 包装层

### 7.2 集成测试

- `voice_pipeline` 在 `embedded` 模式下的普通 commit
- `voice_pipeline` 在 `embedded` 模式下的 enrollment commit
- `voice_identity_service` 通过异步 facade 做识别
- provider 异常和 timeout 降级

### 7.3 端到端测试

- 单启动 `api-server` 时跑通本地声纹建档与普通对话识别
- 慢声纹任务不拖死其他 HTTP / WebSocket 请求

### 7.4 验证映射

| 需求 | 设计章节 | 验证方式 |
| --- | --- | --- |
| `requirements.md` 需求 1 | `design.md` 3.2、3.3 | 配置切换测试、模式日志检查 |
| `requirements.md` 需求 2 | `design.md` 2.3、4.1 | pipeline 集成测试、artifact 断言 |
| `requirements.md` 需求 3 | `design.md` 2.3、3.3、6.2 | blocking helper 测试、并发回归测试 |
| `requirements.md` 需求 4 | `design.md` 2.3、6.1 | voice pipeline / identity / enrollment 回归测试 |
| `requirements.md` 需求 5 | `design.md` 5、6.3 | 日志检查、目录与配置收口检查 |
| `requirements.md` 需求 6 | `design.md` 8.2 | 文档回写检查 |

## 8. 风险与待确认项

### 8.1 风险

- 如果直接把同步 provider 调用塞回 async 主链，会重现 `001.6` 里明令禁止的阻塞问题。
- 如果把大块音频字节直接塞进 `VoiceSessionState`，会让业务状态和运行时缓存缠死。
- 如果删除独立 `voice-runtime` 后，文档和测试没同步回写，后面的人会继续按旧拓扑排障。

### 8.2 待确认项

- 本轮是否需要补一个轻量 health/diagnostics 接口暴露当前 runtime mode 与缓存统计
