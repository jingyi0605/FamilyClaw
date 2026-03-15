# 任务清单 - 小爱原生优先与前缀接管（人话版）

状态：Draft

## 这份文档是干什么的

这份任务清单不是“以后有空再说”的愿望单，而是给后续实现的人直接开工用的。

你打开任意一个任务，应该立刻知道：

- 这一步到底做什么
- 做完以后能看到什么结果
- 依赖什么
- 主要改哪些文件
- 这一步先不做什么
- 怎么验证是不是真的完成

## 状态说明

- `TODO`：还没开始
- `IN_PROGRESS`：正在做
- `BLOCKED`：被外部问题卡住
- `IN_REVIEW`：已经有结果，等复核
- `DONE`：已经完成，并且已经回写状态
- `CANCELLED`：取消，不做了，但必须写原因

规则：

- 只有 `状态：DONE` 的任务才能勾成 `[x]`
- 每完成一个任务，都必须立刻回写这里
- 如果任务边界变了，先改任务描述，再继续做

---

## 阶段 1：先把 native-first 的入口边界立住

- [ ] 1.1 定 gateway 入口模式和接管前缀配置
  - 状态：TODO
  - 这一步到底做什么：把 gateway 的入口模式、前缀配置、前缀剥离和 takeover 打断开关一次写清楚并落到正式配置上。
  - 做完你能看到什么：gateway 不再只有“默认接管”一种行为，而是有明确模式和清晰配置，不靠散落硬编码。
  - 先依赖什么：无
  - 开始前先看：
    - `requirements.md` 需求 1、需求 2、需求 5、需求 6
    - `design.md` §1.4、§2.2、§3.2
    - `apps/open-xiaoai-gateway/open_xiaoai_gateway/settings.py`
  - 主要改哪里：
    - `apps/open-xiaoai-gateway/open_xiaoai_gateway/settings.py`
    - 新增或重构 `apps/open-xiaoai-gateway/open_xiaoai_gateway/invocation_policy.py`
  - 这一步先不做什么：先不动 `api-server` 主链，不做前端配置页。
  - 怎么算完成：
    1. gateway 能明确区分 `always_familyclaw` 和 `native_first`
    2. 前缀列表、前缀剥离和 takeover 打断开关都有正式配置
  - 怎么验证：
    - 配置解析单元测试
    - 非法配置测试
  - 对应需求：`requirements.md` 需求 1、需求 2、需求 5、需求 6
  - 对应设计：`design.md` §1.4、§2.2、§3.2、§5.2

- [ ] 1.2 在 gateway 落正式接管判定，不让未命中前缀进主链
  - 状态：TODO
  - 这一步到底做什么：把“是否接管这次语音”的第一道判定落在 gateway，未命中前缀时保持 FamilyClaw 侧静默。
  - 做完你能看到什么：native-first 模式下，普通对话不会再跑进 FamilyClaw 正式主链。
  - 先依赖什么：1.1
  - 开始前先看：
    - `requirements.md` 需求 1、需求 2、需求 4
    - `design.md` §1.4.1、§3.1、§3.3.2、§4.4.1
    - `apps/open-xiaoai-gateway/open_xiaoai_gateway/translator.py`
    - `apps/open-xiaoai-gateway/open_xiaoai_gateway/bridge.py`
  - 主要改哪里：
    - `apps/open-xiaoai-gateway/open_xiaoai_gateway/translator.py`
    - `apps/open-xiaoai-gateway/open_xiaoai_gateway/bridge.py`
  - 这一步先不做什么：先不处理 takeover 后的业务路由，只负责“进不进主链”。
  - 怎么算完成：
    1. 未命中前缀时不发 `session.start`
    2. 未命中前缀时不发 `audio.commit`
    3. 未命中前缀时不主动下发播放控制
  - 怎么验证：
    - gateway 单元测试
    - 事件流断言测试
  - 对应需求：`requirements.md` 需求 1、需求 2、需求 4
  - 对应设计：`design.md` §3.1、§3.3.2、§4.4.1

- [ ] 1.3 落命中前缀后的 takeover 最小事件流
  - 状态：TODO
  - 这一步到底做什么：命中前缀后，让 gateway 先做最小 takeover，再把清洗后的文本送进现有正式主链。
  - 做完你能看到什么：gateway 已经能像 `mi-gpt` 一样只在命中前缀时接管，但接管后继续走我们现有正式链路。
  - 先依赖什么：1.2
  - 开始前先看：
    - `requirements.md` 需求 2、需求 3、需求 5
    - `design.md` §1.4.3、§3.3.3、§5.2
    - `apps/open-xiaoai-gateway/open_xiaoai_gateway/translator.py`
    - `apps/open-xiaoai-gateway/open_xiaoai_gateway/bridge.py`
  - 主要改哪里：
    - `apps/open-xiaoai-gateway/open_xiaoai_gateway/translator.py`
    - `apps/open-xiaoai-gateway/open_xiaoai_gateway/bridge.py`
  - 这一步先不做什么：先不追求流式录音 takeover，先走最终文本接管。
  - 怎么算完成：
    1. 命中前缀后能按配置剥离前缀
    2. 命中前缀后能发 `session.start + audio.commit(debug_transcript=...)`
    3. `pause_on_takeover` 开关生效
  - 怎么验证：
    - gateway 单元测试
    - takeover 事件流测试
  - 对应需求：`requirements.md` 需求 2、需求 3、需求 5
  - 对应设计：`design.md` §1.4.3、§3.3.3、§5.2

### 阶段检查

- [ ] 1.4 阶段检查：gateway 还是不是干净入口层
  - 状态：TODO
  - 这一步到底做什么：检查这次改动有没有把 gateway 污染成业务决策层。
  - 做完你能看到什么：gateway 只多了一道接管判定，没有顺手长出快路径、慢路径、权限和身份逻辑。
  - 先依赖什么：1.1、1.2、1.3
  - 开始前先看：
    - `requirements.md` 需求 2、需求 6
    - `design.md` §1.4.2、§4.4.3
  - 主要改哪里：本阶段全部相关文件
  - 这一步先不做什么：不去扩产品配置功能。
  - 怎么算完成：
    1. gateway 只承担接管判定
    2. `api-server` 仍然承担正式业务处理
  - 怎么验证：
    - 人工走查
    - grep 检查 gateway 中没有新增快路径/慢路径/权限调用
  - 对应需求：`requirements.md` 需求 2、需求 6
  - 对应设计：`design.md` §1.4.2、§4.4.3

---

## 阶段 2：让 api-server 无痛复用现有主链

- [ ] 2.1 校正 `voice_pipeline` 对 takeover 文本的接入假设
  - 状态：TODO
  - 这一步到底做什么：确认 `audio.commit(debug_transcript=...)` 这条现有入口足够承接 takeover 文本，必要时补齐最小兼容处理。
  - 做完你能看到什么：命中前缀后的文本进入 `voice_pipeline` 时，不需要重造协议。
  - 先依赖什么：1.3
  - 开始前先看：
    - `requirements.md` 需求 3、需求 6
    - `design.md` §3.4、§4.4.2
    - `apps/api-server/app/modules/voice/pipeline.py`
    - `apps/api-server/app/modules/voice/runtime_client.py`
  - 主要改哪里：
    - `apps/api-server/app/modules/voice/pipeline.py`
    - 视情况补 `apps/api-server/app/modules/voice/protocol.py`
  - 这一步先不做什么：不把 `api-server` 变成前缀判定层。
  - 怎么算完成：
    1. takeover 文本能继续进 `voice_pipeline`
    2. 快路径和慢路径不需要额外分叉协议
  - 怎么验证：
    - `api-server` 集成测试
    - takeover 文本回放测试
  - 对应需求：`requirements.md` 需求 3、需求 6
  - 对应设计：`design.md` §3.4、§4.4.2、§6.2

- [ ] 2.2 补 native-first 双模式回归测试
  - 状态：TODO
  - 这一步到底做什么：给“默认接管”和“native-first”两种模式都补回归测试，防止以后只保一边。
  - 做完你能看到什么：模式切换不再靠口头保证，而是有自动化约束。
  - 先依赖什么：2.1
  - 开始前先看：
    - `requirements.md` 需求 4、需求 6
    - `design.md` §2.2、§6
    - `apps/open-xiaoai-gateway/tests/`
    - `apps/api-server/tests/`
  - 主要改哪里：
    - `apps/open-xiaoai-gateway/tests/`
    - `apps/api-server/tests/`
  - 这一步先不做什么：不扩前端页面，不做实机自动化。
  - 怎么算完成：
    1. 默认接管模式回归通过
    2. native-first 模式下未命中前缀保持静默
    3. native-first 模式下命中前缀能进入正式主链
  - 怎么验证：
    - Python 测试跑通
  - 对应需求：`requirements.md` 需求 4、需求 6
  - 对应设计：`design.md` §2.2、§3.3、§6

### 阶段检查

- [ ] 2.3 阶段检查：接管后是不是还在复用现有主链
  - 状态：TODO
  - 这一步到底做什么：只检查命中前缀后的处理是不是仍然走现有 `voice_pipeline / fast_action / conversation`。
  - 做完你能看到什么：前缀模式不是一条新主链，只是新入口。
  - 先依赖什么：2.1、2.2
  - 开始前先看：
    - `requirements.md` 需求 3
    - `design.md` §3.4、§4.4.2
  - 主要改哪里：本阶段全部相关文件
  - 这一步先不做什么：不扩动态配置。
  - 怎么算完成：
    1. takeover 后仍进现有主链
    2. 没有新造“前缀专用快路径/慢路径”
  - 怎么验证：
    - 集成测试
    - 人工走查
  - 对应需求：`requirements.md` 需求 3
  - 对应设计：`design.md` §3.4、§4.4.2

---

## 阶段 3：补文档、联调和验收说明

- [ ] 3.1 补 native-first 联调手册和模式说明
  - 状态：TODO
  - 这一步到底做什么：把两种模式怎么配、怎么验、怎么看日志写清楚，避免后面谁都以为语音链坏了。
  - 做完你能看到什么：后续接手的人知道为什么有时 FamilyClaw 不说话，那是未命中前缀，不是链路断了。
  - 先依赖什么：2.3
  - 开始前先看：
    - `requirements.md` 需求 4、需求 5、需求 6
    - `design.md` §3.2、§5、§6
    - `specs/005-语音快路径与设备控制/docs/20260315-open-xiaoai接入与网关初始化启动手册.md`
  - 主要改哪里：
    - `specs/005.2-小爱原生优先与前缀接管/docs/`
    - 视情况补 `specs/005-语音快路径与设备控制/docs/`
  - 这一步先不做什么：不写营销话术，不画大而空的规划图。
  - 怎么算完成：
    1. 两种模式的行为差异写清楚
    2. 联调顺序写清楚
    3. 常见误判点写清楚
  - 怎么验证：
    - 人工走查
  - 对应需求：`requirements.md` 需求 4、需求 5、需求 6
  - 对应设计：`design.md` §3.2、§5、§6

- [ ] 3.2 最终检查点
  - 状态：TODO
  - 这一步到底做什么：确认这份 Spec 真的已经把行为变化、技术边界、任务顺序和验证方式写清楚了。
  - 做完你能看到什么：新的 Codex 上下文或新同事接手时，不需要再反复追问“前缀到底放哪里判”。
  - 先依赖什么：3.1
  - 开始前先看：
    - `README.md`
    - `requirements.md`
    - `design.md`
    - `tasks.md`
    - `docs/`
  - 主要改哪里：当前 Spec 全部文件
  - 这一步先不做什么：不再扩新范围。
  - 怎么算完成：
    1. 需求、设计、任务追踪完整
    2. gateway 和 `api-server` 边界清楚
    3. 模式切换和验证方式清楚
  - 怎么验证：
    - 按 Spec 验收清单逐项核对
  - 对应需求：`requirements.md` 全部需求
  - 对应设计：`design.md` 全文
