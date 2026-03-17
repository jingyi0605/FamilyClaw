# 需求文档 - 内嵌语音运行时与声纹链路收口

状态：Draft

## 简介

当前小爱语音主链里，`api-server` 负责业务路由、声纹建档和声纹识别，独立 `voice-runtime` 负责音频缓存、音频落盘和 commit 兜底。这个拆法在最初验证阶段能跑，但长期维护不划算：

- 本地和测试环境要多维护一个进程
- 语音链路调试要跨 HTTP 看两边日志
- `api-server` 自己明明有声纹算法，却拿不到原始音频缓存
- 现在这段运行时逻辑不大，拆成独立服务收益不够

这轮不是重做业务，而是把运行时边界收回来，同时保证：

- 现有语音主链不被破坏
- 现有声纹建档、识别、降级语义不被破坏
- 主事件循环不因为同步音频处理或声纹计算被拖死

## 术语表

- **Embedded Runtime**：内嵌在 `api-server` 里的本地语音运行时实现，负责短生命周期音频缓存、落盘和 commit 结果生成。
- **Runtime Backend**：`voice_runtime_client` 背后具体使用的实现，当前只允许 `embedded` 或 `disabled`。
- **Audio Artifact**：commit 后生成的音频产物，包括 `.wav` 文件路径、采样率、声道、位宽、时长和 `sha256`。
- **Blocking Helper**：`app.core.blocking` 里的统一阻塞调用封装，用来把同步 I/O 或 CPU 任务下沉到线程池。

## 范围说明

### In Scope

- 为 `api-server` 增加内嵌 runtime 模式，并作为本地默认方案
- 在 `api-server` 内部缓存会话音频分片，并在 commit 时生成音频产物
- 把声纹建档和声纹识别里的同步重活改成通过 blocking helper 下沉执行
- 删除独立 `voice-runtime` 代码、启动脚本和配置模板
- 更新本地启动、配置模板和文档，明确默认不再依赖额外 `voice-runtime` 进程
- 在迁移完成后回写 `005.3` 相关文档

### Out of Scope

- 更换声纹 provider、模型或阈值策略
- 改造前端声纹管理页面
- 引入新的队列系统、缓存系统或独立 worker 服务

## 需求

### 需求 1：提供可切换的 runtime 模式

**用户故事：** 作为开发者，我希望 `api-server` 能明确配置当前使用 `embedded` 还是 `disabled` 模式，这样本地和测试环境都按同一套入口启动，也不会再误走已经废弃的远程分支。

#### 验收标准

1. WHEN `FAMILYCLAW_VOICE_RUNTIME_MODE=embedded` THEN System SHALL 在 `api-server` 内使用本地 runtime 实现，不再发出到独立 `voice-runtime` 的 HTTP 请求。
2. WHEN `FAMILYCLAW_VOICE_RUNTIME_MODE=disabled` THEN System SHALL 保持当前禁用语义，普通语音链路按现有降级规则继续处理。
3. WHEN 配置中仍残留 `remote`、`voice_runtime_base_url` 或 `voice_runtime_api_key` 旧值 THEN System SHALL 不再把它们当成有效运行路径。

### 需求 2：在 api-server 内部完成音频缓存与音频产物落盘

**用户故事：** 作为语音链路维护者，我希望 `api-server` 自己就能接住实时音频分片并在 commit 时生成 `.wav` 产物，这样声纹能力不再依赖额外进程。

#### 验收标准

1. WHEN 语音网关发送 `audio.append` THEN System SHALL 在 `api-server` 内部保存该会话需要的音频字节，而不只是保存统计数。
2. WHEN 会话进入 `audio.commit` THEN System SHALL 生成和当前 `voice-runtime` 等价的音频产物元数据，包括 `audio_artifact_id`、`audio_file_path`、`sample_rate`、`channels`、`sample_width`、`duration_ms` 和 `audio_sha256`。
3. WHEN 音频数据无效、codec 不支持或无法生成有效帧 THEN System SHALL 明确返回降级结果，而不是把会话卡死在中间状态。

### 需求 3：主事件循环不能被同步重活拖死

**用户故事：** 作为后端维护者，我希望内嵌后的音频落盘、声纹 embedding 和建档逻辑都遵守统一阻塞边界，这样 WebSocket 和 HTTP 请求不会被整条链一起拖慢。

#### 验收标准

1. WHEN 执行音频落盘、hash、音频元数据计算或声纹 embedding THEN System SHALL 通过 `app.core.blocking` 下沉到线程池，不得直接在主事件循环里同步执行。
2. WHEN 需要在线程池里执行数据库写入或读取 THEN System SHALL 使用线程内新建 Session 的统一 helper，不得把当前请求或 WebSocket 持有的 Session 直接带入线程池。
3. WHEN 阻塞任务超时或抛错 THEN System SHALL 记录带 label、kind、timeout 和上下文的日志，并按既有降级语义结束当前链路。

### 需求 4：保持 005.3 的业务语义不变

**用户故事：** 作为现有语音用户，我希望这次迁移只改变运行方式，不改变建档、识别、对话前身份解析和降级行为。

#### 验收标准

1. WHEN 普通 `conversation` 会话提交音频 THEN System SHALL 继续先拿到 transcript 和 audio artifact，再执行身份解析、快路径和慢路径，不改变现有顺序。
2. WHEN `voiceprint_enrollment` 会话提交音频 THEN System SHALL 继续走当前建档主链，并保持对 `voiceprint_artifact_missing`、`voice_transcript_empty`、provider 失败等错误的现有处理语义。
3. WHEN 声纹识别不可用或低置信度 THEN System SHALL 继续按 `005.3` 里现有的上下文兜底和公开对话策略处理，而不是新增新的用户可见错误路径。

### 需求 5：迁移过程必须可观测、可收口

**用户故事：** 作为运维或开发者，我希望这次迁移完成后仓库里不再保留半套旧 runtime 壳子，同时日志和测试还能明确告诉我当前到底是不是内嵌模式。

#### 验收标准

1. WHEN 使用 `embedded` 模式时 THEN System SHALL 在日志或健康信息里明确暴露当前 runtime mode。
2. WHEN 内嵌 runtime 处理失败 THEN System SHALL 保留足够日志定位到会话、终端、模式、阻塞任务标签和异常摘要。
3. WHEN 迁移完成 THEN System SHALL 删除独立 `voice-runtime` 目录、启动脚本和远程配置模板，避免仓库继续保留失效回退入口。

### 需求 6：迁移完成后同步更新 005.3 文档

**用户故事：** 作为后续接手项目的人，我希望 `005.3` 里的运行时描述和启动方式与真实实现一致，而不是继续保留过时信息。

#### 验收标准

1. WHEN `005.3.2` 迁移任务全部完成 THEN System SHALL 回写更新 `005.3` 的 `README.md`、`design.md`、`requirements.md` 和 `tasks.md` 中与 runtime 拓扑、启动方式、联调入口相关的过时描述。
2. WHEN `005.3` 回写完成 THEN System SHALL 明确区分“业务能力归属在 `005.3`”与“运行时收口由 `005.3.2` 完成”这两个事实。
3. WHEN 后续查看 `005.3` THEN System SHALL 不再让人误以为默认本地开发必须单独启动 `voice-runtime` 才能跑通声纹主链。

## 非功能需求

### 非功能需求 1：性能

1. WHEN 处理实时 `audio.append` 分片 THEN System SHALL 只做轻量缓存和统计更新，不在该阶段执行重 CPU 或重 I/O 逻辑。
2. WHEN 执行 `audio.commit` THEN System SHALL 保持当前语音链路可接受的提交耗时，并且不得因为单个 commit 阻塞同一 worker 的其他 HTTP 或 WebSocket 请求。

### 非功能需求 2：可靠性

1. WHEN 内嵌 runtime 落盘失败、声纹 provider 异常或 blocking helper 超时 THEN System SHALL 返回明确降级结果，并保证会话最终进入可解释状态。
2. WHEN 会话结束、取消或失败 THEN System SHALL 释放该会话对应的内存音频缓存，避免长期堆积。

### 非功能需求 3：可维护性

1. WHEN 后续继续维护 runtime 逻辑 THEN System SHALL 只有一套对上层暴露的 runtime 接口，不允许 `pipeline` 同时掺杂 HTTP 分支和本地分支细节。
2. WHEN 排查运行问题 THEN System SHALL 能从日志和测试快速分辨问题是在音频缓存、音频落盘、声纹识别还是业务降级阶段发生。

## 成功定义

- 本地开发默认只启动 `api-server` 即可跑通 `005.3` 声纹主链
- `embedded` 模式对上层业务行为保持稳定，`disabled` 模式保留现有降级语义
- 迁移后新增回归测试能证明 HTTP / WebSocket 不会被同步声纹计算拖死
- `005.3` 文档在迁移完成后不再保留过时的独立 runtime 默认前提
