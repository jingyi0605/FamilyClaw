# 任务清单 - 语音快路径与设备控制（人话版）

状态：Draft

## 这份文档是干什么的

这份任务清单不是拿来堆概念的，是给后续实现的人直接开工用的。

打开任何一个任务，应该立刻知道：

- 这一步到底建什么
- 做完以后系统里能看到什么结果
- 依赖什么现有模块
- 主要改哪些文件
- 这一步故意先不做什么
- 做完以后怎么验证

## 状态说明

- `TODO`：还没开始
- `IN_PROGRESS`：正在做
- `BLOCKED`：被外部问题卡住
- `IN_REVIEW`：已经有结果，等复核
- `DONE`：已经完成，并且已经回写状态
- `CANCELLED`：取消，不做了，但要写原因

规则：

- 只有 `状态：DONE` 的任务才能勾成 `[x]`
- 每完成一个任务，都必须立刻回写这里
- 如果卡住，必须写清楚卡在哪，别装没事

## 阶段 0：先确认硬件链路不是嘴炮

- [x] 0.1 用 `open-xiaoai` 官方 demo 验证硬件链路
  - 状态：DONE
  - 这一步到底做什么：先不碰项目主链，只验证刷机、连接、录音、播放和打断是不是都能跑。
  - 做完你能看到什么：知道小爱终端能不能作为话筒和音箱被真正拿来用，而不是停留在 README。
  - 先依赖什么：无
  - 主要改哪里：无，验证性工作
  - 这一步先不做什么：先不接 `voice_pipeline`，先不做正式网关
  - 怎么算完成：
    1. 设备能刷机
    2. Client 能稳定连接
    3. 麦克风输入正常
    4. 音箱播放正常
    5. 中断小爱播报正常
  - 怎么验证：用户已完成实机验证
  - 备注：此项已由用户确认完成

## 阶段 1：先把 `open-xiaoai-gateway` 立住

- [ ] 1.1 定 `open-xiaoai-gateway` 的进程边界和危险能力白名单
  - 状态：TODO
  - 这一步到底做什么：明确网关是独立进程、监听 `4399`，并把允许能力和禁止能力写进代码与配置。
  - 做完你能看到什么：后面所有人都知道这层只干协议翻译和播放中转，不准偷偷加业务逻辑。
  - 先依赖什么：0.1
  - 开始前先看：
    - `requirements.md` 需求 1、需求 2、需求 7
    - `design.md` §1.4、§2.2、§2.3、§6.5、§6.6
  - 主要改哪里：
    - `specs/005-语音快路径与设备控制/`
    - 后续实际代码建议新建 `apps/open-xiaoai-gateway/` 或等价目录
  - 这一步先不做什么：先不接 ASR 和业务快慢路径
  - 怎么算完成：
    1. 网关职责清楚
    2. 白名单能力固定
    3. 禁用能力固定
  - 怎么验证：
    - 设计走查
    - 配置与能力声明检查

- [ ] 1.2 定内部统一语音事件协议和终端模型
  - 状态：TODO
  - 这一步到底做什么：定义 `terminal.online / session.start / audio.append / play.start / play.abort` 这套内部事件，不让 `api-server` 直接理解 `open-xiaoai` 私有字段。
  - 做完你能看到什么：后面即使换终端适配器，`voice_pipeline` 也不用改协议脑子。
  - 先依赖什么：1.1
  - 开始前先看：
    - `requirements.md` 需求 1、需求 2
    - `design.md` §3.2、§3.3
    - `apps/api-server/app/modules/realtime/`
  - 主要改哪里：
    - `apps/api-server/app/modules/voice/`
    - `apps/api-server/app/api/v1/endpoints/realtime.py`
    - 网关协议定义文件
  - 这一步先不做什么：先不管具体设备控制逻辑
  - 怎么算完成：
    1. 统一事件集合定下来
    2. 终端模型字段定下来
    3. 双向播放控制事件定下来
  - 怎么验证：
    - 协议样例检查
    - 事件序列回放测试

- [ ] 1.3 实现 `open-xiaoai WS -> 内部 voice session events`
  - 状态：TODO
  - 这一步到底做什么：让网关能接住 `open-xiaoai` 音频流和终端状态，并转成内部统一事件推给 `/api/v1/realtime/voice`。
  - 做完你能看到什么：`api-server` 终于能把小爱终端当正式语音终端来看。
  - 先依赖什么：1.2
  - 开始前先看：
    - `requirements.md` 需求 1
    - `design.md` §2.4.1、§3.3.1、§3.3.2
  - 主要改哪里：
    - `apps/open-xiaoai-gateway/`
    - `apps/api-server/app/modules/voice/realtime_service.py`
    - `apps/api-server/tests/`
  - 这一步先不做什么：先不做慢路径和声纹
  - 怎么算完成：
    1. 终端上线、下线、心跳能同步
    2. 音频流能进入内部会话
    3. 断线重连不留下脏会话
  - 怎么验证：
    - 网关到 `api-server` 联调测试
    - 重连与幂等测试

- [ ] 1.4 实现 `内部 play/stop/abort -> open-xiaoai WS commands`
  - 状态：TODO
  - 这一步到底做什么：把 `voice_pipeline` 的播放、停止和打断控制翻回终端命令，并把播放回执回写系统。
  - 做完你能看到什么：系统说“播了”就是真的播了，用户打断也是真的停了。
  - 先依赖什么：1.3
  - 开始前先看：
    - `requirements.md` 需求 2
    - `design.md` §2.4.3、§3.3.2、§5.3
  - 主要改哪里：
    - `apps/open-xiaoai-gateway/`
    - `apps/api-server/app/modules/voice/playback_service.py`
    - `apps/api-server/tests/`
  - 这一步先不做什么：先不追求复杂 TTS 模板管理
  - 怎么算完成：
    1. `play / stop / abort` 都能落到终端
    2. 播放开始、完成、失败、打断都有回执
    3. 播放失败不会假装成功
  - 怎么验证：
    - 播放控制集成测试
    - 打断联调测试

- [ ] 1.5 阶段检查：终端接入层是不是收干净了
  - 状态：TODO
  - 这一步到底做什么：只检查网关、终端模型、事件协议和播放控制有没有站稳，不往业务逻辑乱扩。
  - 做完你能看到什么：后面接 `voice_pipeline` 时，不需要再返工终端协议层。
  - 先依赖什么：1.1、1.2、1.3、1.4
  - 怎么算完成：
    1. `api-server` 不直接依赖 `open-xiaoai` 私有协议
    2. 网关没有偷带业务逻辑
    3. 播放控制闭环完整
  - 怎么验证：
    - 人工走查
    - 核心协议回放测试

## 阶段 2：接 `voice_pipeline`，打通快路径主链

- [ ] 2.1 建语音会话编排器，接流式 ASR 和最终转写
  - 状态：TODO
  - 这一步到底做什么：把网关送来的音频事件、流式 ASR 回调、最终转写和会话状态流转收口成正式的 `voice_pipeline`。
  - 做完你能看到什么：一段音频进来后，系统能稳定给出部分转写、最终转写和后续路由入口。
  - 先依赖什么：1.5
  - 开始前先看：
    - `requirements.md` 需求 3、需求 6
    - `design.md` §2.4.1、§3.1、§4.2
    - `apps/api-server/app/modules/conversation/orchestrator.py`
  - 主要改哪里：
    - `apps/api-server/app/modules/voice/pipeline.py`
    - `apps/api-server/app/modules/voice/runtime_client.py`
    - `apps/api-server/tests/`
  - 这一步先不做什么：先不落具体设备控制解析
  - 怎么算完成：
    1. 流式转写和最终转写能驱动会话状态变化
    2. 转写超时和运行时异常有明确错误码
    3. 最终转写能进入正式会话记录
  - 怎么验证：
    - 语音会话集成测试
    - 流式转写回放测试

- [ ] 2.2 建快路径动作解析并复用现有 `device_action / scene`
  - 状态：TODO
  - 这一步到底做什么：把“开灯、关空调、拉窗帘、进入睡前模式”这类语音命令解析成现有设备动作或场景执行，不再走 LLM 主链。
  - 做完你能看到什么：简单语音控制终于能快起来，而且不是新造一套控制器。
  - 先依赖什么：2.1
  - 开始前先看：
    - `requirements.md` 需求 3、需求 6
    - `design.md` §2.4.1、§2.3、§6.1
    - `apps/api-server/app/modules/device_action/service.py`
    - `apps/api-server/app/modules/scene/service.py`
    - `apps/api-server/app/modules/context/service.py`
  - 主要改哪里：
    - `apps/api-server/app/modules/voice/fast_action_service.py`
    - `apps/api-server/app/modules/voice/router.py`
    - `apps/api-server/tests/`
  - 这一步先不做什么：先不做复杂自然语言解释控制
  - 怎么算完成：
    1. 明确命令能稳定映射到设备动作或场景
    2. 目标不明确时会追问，不瞎猜
    3. 执行结果复用现有回执和审计链路
  - 怎么验证：
    - 快路径集成测试
    - 模糊目标回退测试

- [ ] 2.3 建身份融合和高风险动作保护
  - 状态：TODO
  - 这一步到底做什么：把声纹结果、终端房间、在家状态和家庭保护开关融合起来，决定是直接执行、匿名降级还是追问确认。
  - 做完你能看到什么：语音入口不会因为一段低质量音频就误开门、误切场景。
  - 先依赖什么：2.2
  - 开始前先看：
    - `requirements.md` 需求 5、需求 6
    - `design.md` §2.3、§2.4.4、§6.1
  - 主要改哪里：
    - `apps/api-server/app/modules/voice/identity_service.py`
    - `apps/api-server/app/modules/voice/fast_action_service.py`
    - `apps/api-server/tests/`
  - 这一步先不做什么：先不做多人混说分离
  - 怎么算完成：
    1. 声纹低置信或上下文冲突时会回退
    2. 高风险动作不会只靠一次声纹就放行
    3. 房间和成员状态会影响快路径目标收缩
  - 怎么验证：
    - 高风险阻断测试
    - 声纹低置信回退测试

- [ ] 2.4 阶段检查：快路径链路是不是闭合了
  - 状态：TODO
  - 这一步到底做什么：检查“音频 -> 转写 -> 身份融合 -> 快路径动作 -> 播放回执 -> 审计”这条链是不是已经闭合。
  - 做完你能看到什么：简单语音控制已经不是 PPT，而是真能跑。
  - 先依赖什么：2.1、2.2、2.3
  - 怎么算完成：
    1. 至少一条设备控制和一条场景触发能完整跑通
    2. 播放确认和打断闭环稳定
    3. 高风险阻断、模糊目标、运行时失败都有正式收口
  - 怎么验证：
    - 集成测试
    - 人工回放链路

## 阶段 3：把慢路径和声纹链路补齐

- [ ] 3.1 建语音慢路径到 `conversation` 的桥接
  - 状态：TODO
  - 这一步到底做什么：把复杂语音问题正式转成现有 `conversation` 请求，复用会话、提案、记忆和后续任务草稿能力。
  - 做完你能看到什么：语音问“奶奶今天吃药了吗”时，背后用的还是同一个 AI 主链。
  - 先依赖什么：2.4
  - 开始前先看：
    - `requirements.md` 需求 4
    - `design.md` §2.4.2、§6.2
    - `apps/api-server/app/modules/conversation/service.py`
  - 主要改哪里：
    - `apps/api-server/app/modules/voice/conversation_bridge.py`
    - `apps/api-server/app/modules/voice/pipeline.py`
    - `apps/api-server/tests/`
  - 这一步先不做什么：先不做语音专用提案逻辑
  - 怎么算完成：
    1. 复杂语音问题能复用现有 `conversation`
    2. 回答结果和异常状态能回写语音会话
    3. 不新增第二套语音专用问答链路
  - 怎么验证：
    - 慢路径集成测试
    - 对话能力回归测试

- [ ] 3.2 建声纹注册、更新和停用链路
  - 状态：TODO
  - 这一步到底做什么：给管理员正式补成员声纹注册、重录、停用和查看资料状态的后端入口。
  - 做完你能看到什么：声纹不是只在推理时“顺便试一下”，而是有正式资料生命周期。
  - 先依赖什么：1.5
  - 开始前先看：
    - `requirements.md` 需求 5
    - `design.md` §2.4.4、§3.2.2
  - 主要改哪里：
    - `apps/api-server/app/api/v1/endpoints/voice.py`
    - `apps/api-server/app/modules/voice/biometric_service.py`
    - `apps/api-server/tests/`
  - 这一步先不做什么：先不做家庭成员自助开户式流程
  - 怎么算完成：
    1. 声纹资料可注册、更新、停用
    2. 资料只保存受控引用和状态，不落原始敏感数据
    3. 资料边界清楚
  - 怎么验证：
    - API 测试
    - 资料状态流转测试

- [ ] 3.3 补语音会话查询、审计和时延观测
  - 状态：TODO
  - 这一步到底做什么：把语音会话历史、失败记录、关键时延、播放结果和关联系统动作查出来，给排查和调优留正式入口。
  - 做完你能看到什么：以后再说“语音慢”“误触发”“经常失败”，终于不是靠拍脑袋。
  - 先依赖什么：3.1、3.2
  - 开始前先看：
    - `requirements.md` 需求 2、需求 7
    - `design.md` §3.2.3、§5、§7
  - 主要改哪里：
    - `apps/api-server/app/api/v1/endpoints/voice.py`
    - `apps/api-server/app/modules/voice/query_service.py`
    - `apps/api-server/app/modules/audit/`
    - `apps/api-server/tests/`
  - 这一步先不做什么：先不做复杂 BI 面板和报表中心
  - 怎么算完成：
    1. 能按终端、成员候选、状态、错误码查语音会话
    2. 能看到关键时延、播放结果和关联动作
    3. 失败会话不再是黑盒
  - 怎么验证：
    - 查询 API 测试
    - 审计关联测试

- [ ] 3.4 阶段检查：慢路径和声纹资料是不是站住了
  - 状态：TODO
  - 这一步到底做什么：检查“复杂语音 -> `conversation`”和“声纹资料生命周期”这两条链是不是已经靠谱。
  - 做完你能看到什么：语音终于不只是快控，而是有完整的身份和问答闭环。
  - 先依赖什么：3.1、3.2、3.3
  - 怎么算完成：
    1. 复杂语音问题能完整回接 `conversation`
    2. 声纹资料注册、更新、停用链路完整
    3. 近期语音失败有正式查询入口
  - 怎么验证：
    - 集成测试
    - 人工回放问答链路

## 阶段 4：把文档、演进路线和后续插件位收口

- [ ] 4.1 补 `open-xiaoai` 接入文档、联调清单和排错手册
  - 状态：TODO
  - 这一步到底做什么：把网关怎么起、终端怎么绑、联调看什么、常见问题怎么排写成文档。
  - 做完你能看到什么：后续接手的人不用再反复问“4399 这层到底在干什么”。
  - 先依赖什么：3.4
  - 主要改哪里：
    - `specs/005-语音快路径与设备控制/docs/`
    - `docs/`
  - 这一步先不做什么：先不写采购指南和营销文案
  - 怎么算完成：
    1. 网关职责写清楚
    2. 联调顺序写清楚
    3. 常见故障定位点写清楚
  - 怎么验证：
    - 人工走查文档

- [ ] 4.2 写后续插件路线，明确 `mi-gpt` 只占插件位
  - 状态：TODO
  - 这一步到底做什么：把 `mi-gpt` 的定位写清楚，只保留为后续终端适配器候选，不让它影响当前实现。
  - 做完你能看到什么：大家不会再拿“以后可能接更多设备”当理由，把现在的代码抽象成看不懂的空壳。
  - 先依赖什么：4.1
  - 开始前先看：
    - `requirements.md` 需求 7
    - `design.md` §1.4.6、§6.5
    - `docs/20260314-open-xiaoai接入草案与演进路线.md`
  - 主要改哪里：
    - `specs/005-语音快路径与设备控制/docs/`
  - 这一步先不做什么：先不实现 `mi-gpt` 代码接入
  - 怎么算完成：
    1. `mi-gpt` 被明确标成后续候选
    2. 插件边界清楚
    3. 不污染当前交付范围
  - 怎么验证：
    - 设计和需求交叉检查

- [ ] 4.3 最终检查点
  - 状态：TODO
  - 这一步到底做什么：确认这份 Spec 真能指导后续分批落地，而不是看起来很全、实际上没人知道先做什么。
  - 做完你能看到什么：需求、设计、任务、选型说明和验证方式能一一对上。
  - 先依赖什么：4.1、4.2
  - 怎么算完成：
    1. `open-xiaoai-gateway`、`voice_pipeline`、`voice-runtime` 和现有主链边界清楚
    2. 每个阶段都能独立交付
    3. 风险和延期项写清楚，不藏雷
  - 怎么验证：
    - 按 Spec 验收清单逐项核对
