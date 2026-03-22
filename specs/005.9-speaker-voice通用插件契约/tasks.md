# 任务清单 - speaker/voice 通用插件契约（人话版）

状态：Draft

## 这份任务清单是干什么的

这份清单不是拿来堆术语的，是拿来防止我们又把事情做歪。

这次真正要交付的，不是“再接一个小爱插件”，而是：

- 先把宿主 `speaker/voice` 契约立住。
- 再让第三方插件沿着这条契约接进来。
- 最后确认核心里不再留厂商特例。

## 状态说明

- `TODO`：还没开始
- `IN_PROGRESS`：正在做
- `BLOCKED`：被外部问题卡住
- `IN_REVIEW`：已有结果，等待复核
- `DONE`：已经完成，并且已经回写状态
- `CANCELLED`：明确取消，并写清原因

---

## 阶段 1：把宿主正式契约立起来

- [ ] 1.1 定义 `speaker/voice` 正式插件类型和 manifest 能力块
  - 状态：TODO
  - 这一步到底做什么：明确第三方 `speaker` 插件在宿主里到底怎么声明自己，入口叫什么，能力怎么写，哪些字段必填。
  - 做完以后你能看到什么：开发者不用再猜“这类插件到底该挂 integration、action，还是再偷开私有入口”。
  - 先依赖什么：无
  - 开始前先看：
    - `requirements.md` 需求 1
    - `design.md` §2.2
    - `design.md` §3.3.1
  - 主要改哪里：
    - `apps/api-server/app/modules/plugin/schemas.py`
    - `apps/api-server/tests/test_plugin_manifest.py`
    - `docs/开发者文档/插件开发/zh-CN/03-manifest字段规范.md`
  - 这一阶段先不做什么：先不接任何小米逻辑。
  - 怎么算完成：
    1. manifest 能明确声明 `speaker/voice` 契约。
    2. 缺关键字段时会在校验阶段直接失败。
  - 怎么验证：
    - manifest 校验测试
    - 开发者手册人工走查
  - 对应需求：`requirements.md` 需求 1
  - 对应设计：`design.md` §2.2、§3.3.1

- [ ] 1.2 把 discovery / binding / text turn DTO 定义完整
  - 状态：TODO
  - 这一步到底做什么：把宿主真正要认的输入输出模型钉死，特别是 `SpeakerTextTurnRequest`、`SpeakerTextTurnResult` 和 heartbeat。
  - 做完以后你能看到什么：插件和宿主之间不再靠私有 JSON 瞎传字段。
  - 先依赖什么：1.1
  - 开始前先看：
    - `requirements.md` 需求 2、需求 3、需求 6
    - `design.md` §3.2
    - `design.md` §4.1
  - 主要改哪里：
    - `apps/api-server/app/modules/voice/...`
    - `apps/api-server/app/modules/device_integration/schemas.py`
    - 相关测试文件
  - 这一阶段先不做什么：先不做后台 worker。
  - 怎么算完成：
    1. discovery、binding、text turn、heartbeat 都有正式 DTO。
    2. 幂等键、实例归属、设备归属有明确校验。
  - 怎么验证：
    - DTO 校验测试
    - 集成测试草跑
  - 对应需求：`requirements.md` 需求 2、需求 3、需求 6
  - 对应设计：`design.md` §3.2、§4.1

### 阶段检查

- [ ] 1.3 确认宿主已经有一条完整契约，而不是半套字段
  - 状态：TODO
  - 这一步到底做什么：回头检查 manifest、DTO、错误码和绑定关系是不是已经能单独成立。
  - 做完以后你能看到什么：后面做具体插件时不需要再回头改宿主基础边界。
  - 先依赖什么：1.1、1.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：本阶段相关文档和测试
  - 这一阶段先不做什么：不引入厂商实现。
  - 怎么算完成：
    1. 宿主契约能独立解释清楚。
    2. 没有再靠 `open-xiaoai` 私有字段补洞。
  - 怎么验证：
    - 人工走查
  - 对应需求：`requirements.md` 需求 1、需求 2、需求 3
  - 对应设计：`design.md` §2、§3、§4

---

## 阶段 2：补通用桥接和运行时边界

- [ ] 2.1 实现 `text turn bridge` 和统一幂等校验
  - 状态：TODO
  - 这一步到底做什么：让文本轮询型插件能正式把请求送进宿主实时对话主链，并拿到标准回复。
  - 做完以后你能看到什么：像 `mi-gpt` 这种方案终于有正式入口，不再是旁路接入。
  - 先依赖什么：1.3
  - 开始前先看：
    - `requirements.md` 需求 3
    - `design.md` §2.3.2
    - `design.md` §3.3.2
  - 主要改哪里：
    - `apps/api-server/app/modules/voice/...`
    - `apps/api-server/app/modules/realtime/...`
    - 相关测试文件
  - 这一阶段先不做什么：先不把文本插件伪装成音频插件。
  - 怎么算完成：
    1. 插件可以提交 text turn。
    2. 同一条 turn 不会重复入链。
  - 怎么验证：
    - text turn 集成测试
  - 对应需求：`requirements.md` 需求 3
  - 对应设计：`design.md` §2.3.2、§3.3.2

- [ ] 2.2 实现 runtime heartbeat、禁用拦截和音频车道边界
  - 状态：TODO
  - 这一步到底做什么：把常驻轮询 worker 的健康状态、禁用语义和音频会话边界全部拉进统一规则。
  - 做完以后你能看到什么：插件禁用后不会继续偷偷跑；文本插件也不会乱标“支持音频实时会话”。
  - 先依赖什么：2.1
  - 开始前先看：
    - `requirements.md` 需求 4、需求 6
    - `design.md` §2.3.3
    - `design.md` §2.3.5
    - `docs/开发设计规范/20260317-插件启用禁用统一规则.md`
    - `docs/开发设计规范/20260316-后端事件循环与周期任务开发规范.md`
  - 主要改哪里：
    - `apps/api-server/app/modules/plugin/...`
    - `apps/api-server/app/modules/voice/...`
    - `apps/api-server/app/core/worker_runtime.py`
    - 相关测试文件
  - 这一阶段先不做什么：先不接具体厂商。
  - 怎么算完成：
    1. heartbeat 状态可观测。
    2. 禁用插件会统一返回 `plugin_disabled`。
    3. 文本模式和音频模式边界清楚。
  - 怎么验证：
    - heartbeat 测试
    - 禁用插件执行拦截测试
  - 对应需求：`requirements.md` 需求 4、需求 6
  - 对应设计：`design.md` §2.3.3、§2.3.5、§5

### 阶段检查

- [ ] 2.3 确认宿主桥接层不再藏厂商知识
  - 状态：TODO
  - 这一步到底做什么：复核桥接层是不是只剩通用能力，没有混进小米、天猫精灵之类的协议细节。
  - 做完以后你能看到什么：宿主核心终于像个平台，不像某个厂商 SDK 拼接层。
  - 先依赖什么：2.1、2.2
  - 开始前先看：
    - `requirements.md` 需求 5、需求 7
    - `design.md` §6.1
  - 主要改哪里：相关桥接层代码和测试
  - 这一阶段先不做什么：不扩大功能范围。
  - 怎么算完成：
    1. 宿主只认通用 `speaker` 动作和通用 DTO。
    2. 搜索核心代码看不到厂商协议表。
  - 怎么验证：
    - grep
    - 人工审查
  - 对应需求：`requirements.md` 需求 5、需求 7
  - 对应设计：`design.md` §2.3.4、§6.1

---

## 阶段 3：文档、回归和收口

- [ ] 3.1 更新开发者手册和回归测试
  - 状态：TODO
  - 这一步到底做什么：把 manifest 规范、插件开发手册、错误语义和回归测试补齐。
  - 做完以后你能看到什么：第三方开发者可以照着文档接插件，不需要翻核心代码猜规则。
  - 先依赖什么：2.3
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `docs/`
  - 主要改哪里：
    - `docs/开发者文档/插件开发/...`
    - `apps/api-server/tests/...`
    - 当前 Spec 的 `docs/`
  - 这一阶段先不做什么：不新增厂商特性。
  - 怎么算完成：
    1. manifest 写法、text turn 写法、heartbeat 写法都有文档。
    2. 回归测试覆盖禁用、幂等、绑定和控制。
  - 怎么验证：
    - 文档人工走查
    - 测试通过
  - 对应需求：`requirements.md` 全部需求
  - 对应设计：`design.md` 全文

### 最终检查

- [ ] 3.2 最终检查点
  - 状态：TODO
  - 这一步到底做什么：确认 `005.9` 真的把宿主边界立住了，而不是只写了几段好听的话。
  - 做完以后你能看到什么：后续 `005.9.1` 这种第三方插件 Spec 可以直接站在这份契约上继续推进。
  - 先依赖什么：3.1
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
    - `docs/`
  - 主要改哪里：当前 Spec 全部文件
  - 这一阶段先不做什么：不把未完成内容硬标成 DONE。
  - 怎么算完成：
    1. 需求、设计、任务、文档、测试能一一对上。
    2. 宿主边界已经足够支撑第三方 `speaker` 插件接入。
  - 怎么验证：
    - 按 Spec 验收清单逐项核对
  - 对应需求：`requirements.md` 全部需求
  - 对应设计：`design.md` 全文
