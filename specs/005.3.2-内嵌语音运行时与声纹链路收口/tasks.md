# 任务清单 - 内嵌语音运行时与声纹链路收口（人话版）

状态：Draft

## 这份文档是干什么的

这份任务清单不是为了凑格式，是为了保证迁移时别一会儿改 WebSocket，一会儿改声纹，一会儿又去补配置，最后把主链改烂。

这里要始终回答清楚：

- 先做什么
- 后做什么
- 每一步到底改哪里
- 做完以后怎么判断真的完成了

## 状态说明

- `TODO`：还没开始
- `IN_PROGRESS`：正在做
- `BLOCKED`：被外部问题卡住
- `IN_REVIEW`：已有结果，等复核
- `DONE`：已经完成，并且已回写状态
- `CANCELLED`：取消，不做了，但要写清原因

规则：

- 只有 `状态：DONE` 的任务才能勾成 `[x]`
- 每完成一个任务，必须立刻回写这里
- 如果范围变了，先改任务描述，再继续做

---

## 阶段 1：先把运行时边界和配置入口立住

- [ ] 1.1 给 `api-server` 增加明确的 runtime mode 配置
  - 状态：TODO
  - 这一阶段到底做什么：把 runtime 模式从现在的“看有没有 base_url 猜”改成明确配置，支持 `embedded / remote / disabled`。
  - 做完你能看到什么：本地、测试和兼容环境都能明确知道当前走哪套 runtime。
  - 先依赖什么：无
  - 开始前先看：
    - `requirements.md` 需求 1
    - `design.md` 2.1、3.2、3.3
    - `specs/001.6-事件循环与后台任务阻塞治理/`
  - 主要改哪里：
    - `apps/api-server/app/core/config.py`
    - `apps/api-server/.env.example`
    - `apps/start-api-server.sh`
  - 这一阶段先不做什么：先不碰音频缓存和声纹逻辑实现。
  - 怎么算完成：
    1. 配置里有明确的 runtime mode
    2. `remote` 和 `disabled` 旧语义不被破坏
  - 怎么验证：
    - 配置单测
    - 手工检查 `.env.example` 和启动脚本
  - 对应需求：`requirements.md` 需求 1 / 验收 1.1、1.2、1.3
  - 对应设计：`design.md` 2.1、3.2、3.3

- [ ] 1.2 抽 runtime backend 接口，给上层保留同一套入口
  - 状态：TODO
  - 这一阶段到底做什么：把现在的 `voice_runtime_client` 从“远程 HTTP 实现”改成“可插拔 backend 门面”，上层 `pipeline` 不感知模式差异。
  - 做完你能看到什么：`pipeline` 还用同一套 `start/append/finalize`，但底下已经能切换 `embedded` 和 `remote`。
  - 先依赖什么：1.1
  - 开始前先看：
    - `requirements.md` 需求 1、需求 4
    - `design.md` 2.2、3.1、3.3
  - 主要改哪里：
    - `apps/api-server/app/modules/voice/runtime_client.py`
    - 新增 `apps/api-server/app/modules/voice/runtime_backends/`
  - 这一阶段先不做什么：先不实现完整 embedded 逻辑，只先把接口和选择器立住。
  - 怎么算完成：
    1. 上层调用点不需要知道 backend 细节
    2. 旧的 remote 实现还能正常接上
  - 怎么验证：
    - `voice_runtime_client` 单测
    - 现有 remote 模式回归测试
  - 对应需求：`requirements.md` 需求 1、需求 4
  - 对应设计：`design.md` 2.2、3.1、3.3

### 阶段检查

- [ ] 1.3 阶段检查：确认“模式切换”和“统一入口”已经站稳
  - 状态：TODO
  - 这一阶段到底做什么：只检查架构入口，确保后面不会一边改 embedded，一边把 remote 兼容搞没。
  - 做完你能看到什么：迁移后续实现有稳定入口，不会把上层调用点改成到处都是 if/else。
  - 先依赖什么：1.1、1.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：本阶段相关全部文件
  - 这一阶段先不做什么：不扩大功能范围。
  - 怎么算完成：
    1. runtime mode 和 backend 入口已经清楚
    2. `pipeline` 还没有被模式判断污染
  - 怎么验证：
    - 人工走查
  - 对应需求：`requirements.md` 需求 1、需求 4
  - 对应设计：`design.md` 2.1、2.2、3.1

---

## 阶段 2：把音频缓存和音频产物真正收回 api-server

- [ ] 2.1 新增独立的内嵌音频会话缓存，不污染业务 session
  - 状态：TODO
  - 这一阶段到底做什么：在 `api-server` 新建只服务于 runtime 的短生命周期音频缓存 store，不把原始音频字节塞进现有 `VoiceSessionState`。
  - 做完你能看到什么：系统能在 `audio.append` 时真正接住原始音频，而不是只记分片数和字节数。
  - 先依赖什么：1.3
  - 开始前先看：
    - `requirements.md` 需求 2、非功能需求 2、非功能需求 3
    - `design.md` 2.3、3.2、4.1、4.2
    - `apps/api-server/app/modules/voice/registry.py`
  - 主要改哪里：
    - 新增 `apps/api-server/app/modules/voice/embedded_runtime_store.py`
    - `apps/api-server/app/modules/voice/runtime_backends/`
  - 这一阶段先不做什么：先不写文件、不做声纹识别。
  - 怎么算完成：
    1. append 阶段已能保存音频字节
    2. cancel / fail / commit 后有明确清理入口
  - 怎么验证：
    - store 单元测试
  - 对应需求：`requirements.md` 需求 2、需求 5
  - 对应设计：`design.md` 2.3、3.2、4.1、4.2、6.3

- [ ] 2.2 实现 embedded finalize：commit 时在线程池里落盘并生成 artifact
  - 状态：TODO
  - 这一阶段到底做什么：把现在 `voice-runtime` 里那套“拼 wav、算时长、算 hash、生成 artifact”的逻辑搬回 `api-server`，并通过 blocking helper 在线程池里执行。
  - 做完你能看到什么：`embedded` 模式下，普通会话和建档会话都能拿到完整 audio artifact，不再依赖远程进程。
  - 先依赖什么：2.1
  - 开始前先看：
    - `requirements.md` 需求 2、需求 3、需求 4
    - `design.md` 2.3、3.3、5.3、6.2
    - `apps/voice-runtime/voice_runtime/service.py`
    - `apps/api-server/app/core/blocking.py`
  - 主要改哪里：
    - 新增 `apps/api-server/app/modules/voice/embedded_runtime.py`
    - `apps/api-server/app/modules/voice/runtime_backends/`
    - `apps/api-server/tests/`
  - 这一阶段先不做什么：先不把声纹 provider 调用混进 finalize。
  - 怎么算完成：
    1. `embedded` 模式 finalize 返回结构和当前 remote 等价
    2. 阻塞落盘逻辑不直接跑在事件循环里
  - 怎么验证：
    - embedded runtime 单测
    - pipeline 集成测试
  - 对应需求：`requirements.md` 需求 2、需求 3、需求 4
  - 对应设计：`design.md` 2.3、3.3、5.3、6.2

- [ ] 2.3 把 pipeline 接到 embedded backend，并保留 remote 回退
  - 状态：TODO
  - 这一阶段到底做什么：让 `voice_pipeline_service` 在 `embedded` 模式下走本地 runtime，在 `remote` 模式下继续走 HTTP，不改上层业务顺序。
  - 做完你能看到什么：本地只起 `api-server` 就能跑通 transcript + artifact 主链，切回 `remote` 也不炸。
  - 先依赖什么：2.2
  - 开始前先看：
    - `requirements.md` 需求 1、需求 4、需求 5
    - `design.md` 2.3、6.1
    - `apps/api-server/app/modules/voice/pipeline.py`
  - 主要改哪里：
    - `apps/api-server/app/modules/voice/pipeline.py`
    - `apps/api-server/app/modules/voice/runtime_client.py`
    - `apps/api-server/tests/test_voice_pipeline.py`
  - 这一阶段先不做什么：先不碰前端或文档。
  - 怎么算完成：
    1. `embedded` 模式普通会话能拿到 transcript 和 artifact
    2. `remote` 模式兼容测试继续通过
  - 怎么验证：
    - `voice_pipeline` 回归测试
    - `voice_runtime_client` 模式切换测试
  - 对应需求：`requirements.md` 需求 1、需求 4、需求 5
  - 对应设计：`design.md` 2.3、3.3、6.1

### 阶段检查

- [ ] 2.4 阶段检查：确认 api-server 已经能自己产出音频 artifact
  - 状态：TODO
  - 这一阶段到底做什么：只检查“接住音频、落出 artifact、兼容旧模式”这三件事，不提前把声纹异步改造搅进来。
  - 做完你能看到什么：runtime 迁移的第一段已经站稳，后面只剩声纹执行边界收口。
  - 先依赖什么：2.1、2.2、2.3
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：本阶段相关全部文件
  - 这一阶段先不做什么：不加新需求。
  - 怎么算完成：
    1. `embedded` 模式能替代当前本地 `voice-runtime` 核心职责
    2. 旧 `remote` 模式仍可回退
  - 怎么验证：
    - 人工走查
    - 关键测试回放
  - 对应需求：`requirements.md` 需求 1、需求 2、需求 5
  - 对应设计：`design.md` 2.3、4.1、4.2

---

## 阶段 3：把声纹重活从主事件循环里赶出去

- [ ] 3.1 给声纹建档补异步 facade，统一走 blocking DB helper
  - 状态：TODO
  - 这一阶段到底做什么：把 `process_voiceprint_enrollment_sample(...)` 的同步调用包成异步 facade，在线程池里用独立 Session 执行。
  - 做完你能看到什么：建档还保持原语义，但不会在 WebSocket 协程里同步跑完 embedding 和 DB 写入。
  - 先依赖什么：2.4
  - 开始前先看：
    - `requirements.md` 需求 3、需求 4
    - `design.md` 2.3、3.3、5.3、6.2
    - `apps/api-server/app/modules/voiceprint/service.py`
    - `apps/api-server/app/core/blocking.py`
  - 主要改哪里：
    - 新增 `apps/api-server/app/modules/voiceprint/async_service.py`
    - `apps/api-server/app/modules/voice/pipeline.py`
    - `apps/api-server/tests/`
  - 这一阶段先不做什么：先不改识别链路。
  - 怎么算完成：
    1. 建档走线程池，不复用当前 WebSocket DB Session
    2. 现有 enrollment 语义和错误码保持一致
  - 怎么验证：
    - enrollment pipeline 回归测试
    - timeout / provider 异常测试
  - 对应需求：`requirements.md` 需求 3、需求 4
  - 对应设计：`design.md` 2.3、3.3、5.3、6.2

- [ ] 3.2 给普通声纹识别补异步 facade，统一走 blocking helper
  - 状态：TODO
  - 这一阶段到底做什么：把 `identify_household_member_by_voiceprint(...)` 的同步 provider 调用包成异步 facade，避免直接卡住 `voice_identity_service.resolve(...)`。
  - 做完你能看到什么：普通对话前身份识别继续可用，但不会把整个 WebSocket worker 拖慢。
  - 先依赖什么：3.1
  - 开始前先看：
    - `requirements.md` 需求 3、需求 4、非功能需求 1
    - `design.md` 2.3、3.3、6.2
    - `apps/api-server/app/modules/voice/identity_service.py`
  - 主要改哪里：
    - `apps/api-server/app/modules/voiceprint/async_service.py`
    - `apps/api-server/app/modules/voice/identity_service.py`
    - `apps/api-server/tests/`
  - 这一阶段先不做什么：先不做新的身份策略。
  - 怎么算完成：
    1. 普通识别调用不再同步跑 provider
    2. `VoiceIdentityResolution` 输出结构不变
  - 怎么验证：
    - `voice_identity_service` 回归测试
    - provider 失败与低置信度测试
  - 对应需求：`requirements.md` 需求 3、需求 4
  - 对应设计：`design.md` 2.3、3.3、6.1、6.2

- [ ] 3.3 补“慢任务不拖死别的请求”的回归测试
  - 状态：TODO
  - 这一阶段到底做什么：明确补一组测试，证明慢的声纹处理不会把同一 worker 的其他 HTTP / WebSocket 一起拖死。
  - 做完你能看到什么：这次迁移不是靠嘴保证“不阻塞”，而是有测试证据。
  - 先依赖什么：3.2
  - 开始前先看：
    - `requirements.md` 需求 3、非功能需求 1
    - `design.md` 7.3
    - `apps/api-server/tests/test_realtime_ws.py`
  - 主要改哪里：
    - `apps/api-server/tests/test_voice_realtime_ws.py`
    - `apps/api-server/tests/test_realtime_ws.py`
  - 这一阶段先不做什么：先不做长时间 soak test 自动化。
  - 怎么算完成：
    1. 至少一条测试能证明慢声纹任务不拖慢别的请求
    2. 关键 timeout 和异常路径有回归保护
  - 怎么验证：
    - 相关测试文件执行
  - 对应需求：`requirements.md` 需求 3、非功能需求 1
  - 对应设计：`design.md` 7.3、7.4

### 阶段检查

- [ ] 3.4 阶段检查：确认内嵌后不会卡主事件循环
  - 状态：TODO
  - 这一阶段到底做什么：只检查阻塞边界和回归结果，确认没有把同步 CPU / I/O 重活塞回 async 主链。
  - 做完你能看到什么：内嵌 runtime 不只是“能跑”，而是“跑法对”。
  - 先依赖什么：3.1、3.2、3.3
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：本阶段相关全部文件
  - 这一阶段先不做什么：不扩展业务需求。
  - 怎么算完成：
    1. 音频落盘和声纹计算都有 blocking helper 包裹
    2. 回归测试证明主事件循环没被拖死
  - 怎么验证：
    - 人工走查
    - 关键回归测试
  - 对应需求：`requirements.md` 需求 3、需求 5
  - 对应设计：`design.md` 3.3、6.2、7.3

---

## 阶段 4：收口启动方式、文档和旧 spec 信息

- [ ] 4.1 更新本地启动与配置文档，默认以 api-server 单进程为准
  - 状态：TODO
  - 这一阶段到底做什么：把本地启动说明、配置模板和脚本调整到“默认只起 `api-server`”的现实，不再误导大家必须额外起 `voice-runtime`。
  - 做完你能看到什么：新同事照着文档配，不会平白多起一个进程。
  - 先依赖什么：3.4
  - 开始前先看：
    - `requirements.md` 需求 1、需求 5
    - `design.md` 2.1、3.2
  - 主要改哪里：
    - `apps/api-server/.env.example`
    - `apps/start-api-server.sh`
    - 相关开发文档
  - 这一阶段先不做什么：先不删除 remote 兼容入口。
  - 怎么算完成：
    1. 默认本地启动只依赖 `api-server`
    2. `remote` 模式仍有明确配置入口
  - 怎么验证：
    - 文档走查
    - 本地 dry run
  - 对应需求：`requirements.md` 需求 1、需求 5
  - 对应设计：`design.md` 2.1、3.2

- [ ] 4.2 迁移完成后回写 `005.3` 中受影响的信息
  - 状态：TODO
  - 这一阶段到底做什么：把 `005.3` 里所有还把独立 `voice-runtime` 当成本地默认前提的描述改掉，避免后面的人读旧 spec 读歪。
  - 做完你能看到什么：`005.3` 讲业务，`005.3.2` 讲运行时收口，两边说的是同一个现实，不互相打架。
  - 先依赖什么：4.1
  - 开始前先看：
    - `requirements.md` 需求 6
    - `design.md` 8.2
    - `specs/005.3-小爱声纹采集与身份识别/`
  - 主要改哪里：
    - `specs/005.3-小爱声纹采集与身份识别/README.md`
    - `specs/005.3-小爱声纹采集与身份识别/requirements.md`
    - `specs/005.3-小爱声纹采集与身份识别/design.md`
    - `specs/005.3-小爱声纹采集与身份识别/tasks.md`
  - 这一阶段先不做什么：不借机改写 `005.3` 的业务边界。
  - 怎么算完成：
    1. `005.3` 不再把独立 `voice-runtime` 写成本地默认必需项
    2. `005.3` 明确引用 `005.3.2` 作为运行时收口来源
  - 怎么验证：
    - 人工走查
  - 对应需求：`requirements.md` 需求 6
  - 对应设计：`design.md` 8.2

- [ ] 4.3 最终检查点
  - 状态：TODO
  - 这一阶段到底做什么：确认这轮迁移不是只写了代码，而是真的把配置、测试、文档和 spec 都收干净了。
  - 做完你能看到什么：后面的人拿着 `005.3` 和 `005.3.2`，都能知道当前真实结构是什么。
  - 先依赖什么：4.1、4.2
  - 开始前先看：
    - `README.md`
    - `requirements.md`
    - `design.md`
    - `tasks.md`
    - `specs/005.3-小爱声纹采集与身份识别/`
  - 主要改哪里：当前 Spec 全部文件，以及 `005.3` 相关文件
  - 这一阶段先不做什么：不额外扩需求。
  - 怎么算完成：
    1. 代码、测试、配置、文档、旧 spec 已对齐
    2. 本地默认启动不再依赖独立 runtime 进程
    3. 回退到 `remote` 模式仍可行
  - 怎么验证：
    - 按迁移验收清单逐项核对
  - 对应需求：`requirements.md` 全部需求
  - 对应设计：`design.md` 全文
