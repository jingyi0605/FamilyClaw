# 任务清单 - 小爱声纹采集与身份识别（人话版）

状态：Draft

## 这份文档是干什么的

这份任务清单不是愿望单，是后面真正要开工时的施工图。打开任意一个任务，应该立刻知道：

- 这一步到底做什么
- 做完以后能看到什么结果
- 它依赖什么
- 主要改哪些文件
- 这一步明确不做什么
- 怎么验证它真做完了

## 状态说明

- `TODO`：还没开始
- `IN_PROGRESS`：正在做
- `BLOCKED`：被外部问题卡住
- `IN_REVIEW`：已经有结果，等复核
- `DONE`：已经完成并回写状态
- `CANCELLED`：取消，不做了，但要写原因

规则：

- 只有 `状态：DONE` 的任务才能勾成 `[x]`
- 每完成一个任务，都要立刻回写这里
- 如果任务边界变了，先改任务描述，再继续做

---

## 阶段 0：先把测试做完，别急着写代码

- [x] 0.1 验证 open-xiaoai 到 gateway 的音频链路到底给了什么
  - 状态：DONE
  - 这一步到底做什么：确认 Rust client 发的是不是可恢复的原始音频流，别把“有文本回调”误当成“有声纹源文件”。
  - 做完你能看到什么：能明确说出链路里拿到的是 `record` 音频分片，并且能恢复成 `.wav / .pcm`。
  - 先依赖什么：无
  - 开始前先看：
    - `open-xiaoai/packages/client-rust/README.md`
    - `open-xiaoai/packages/client-rust/src/bin/client.rs`
    - `open-xiaoai/packages/client-rust/src/services/audio/record.rs`
    - `apps/open-xiaoai-gateway/open_xiaoai_gateway/translator.py`
  - 主要改哪里：无代码改动，只补 Spec 文档
  - 这一先不做什么：先不改正式业务代码
  - 怎么算完成：
    1. 已确认 Rust client 发送 `record` 音频流分片。
    2. 已确认 gateway 能翻译成 `audio.append`。
    3. 已确认分片可以恢复成标准源文件。
  - 怎么验证：
    - 音频恢复测试
    - 现有 gateway 翻译测试
  - 对应需求：`requirements.md` 闸门 A、需求 2
  - 对应设计：`design.md` 1.4、2.2

- [x] 0.2 跑通一个可落地的多轮声纹建档最小闭环
  - 状态：DONE
  - 这一步到底做什么：先别搞多 provider，先找一个本地可跑的基线方案，验证“多轮样本 -> embedding 聚合 -> 搜索/验证”是不是通的。
  - 做完你能看到什么：能明确知道第一版不是瞎选方案，而是选了一个已经跑通闭环的方案。
  - 先依赖什么：0.1
  - 开始前先看：
    - `docs/20260315-小爱声纹测试结论与开发闸门.md`
  - 主要改哪里：无代码改动，只补 Spec 文档
  - 这一先不做什么：先不接入正式业务链路
  - 怎么算完成：
    1. 已选定一条首版声纹基线方案。
    2. 已验证多轮样本可以聚合成一个可搜索档案。
  - 怎么验证：
    - 本地 ONNX 声纹闭环测试
  - 对应需求：`requirements.md` 闸门 B、需求 3
  - 对应设计：`design.md` 3.1、3.2

- [x] 0.2.1 用公开样本完成 `CAM++` 与 `ResNet34` 对比，并锁定首版模型
  - 状态：DONE
  - 这一步到底做什么：别再凭感觉选模型，直接拿公开样本把两种候选模型放到同一套规则里对比，锁定首版方案。
  - 做完你能看到什么：Spec 里不再写“模型待定”，而是明确第一版用 `ResNet34`。
  - 先依赖什么：0.2
  - 开始前先看：
    - `docs/20260315-小爱声纹测试结论与开发闸门.md`
  - 主要改哪里：无代码改动，只补 Spec 文档
  - 这一先不做什么：先不做线上 A/B，不做多模型共存
  - 怎么算完成：
    1. 已用公开样本完成 `CAM++` 与 `ResNet34` 对比。
    2. 已确认当前第一版正式选用 `ResNet34`。
  - 怎么验证：
    - 公开样本基准测试
  - 对应需求：`requirements.md` 需求 3
  - 对应设计：`design.md` 1.4、3.1

- [x] 0.3 测清楚 `100ms` 的边界，不许再靠猜
  - 状态：DONE
  - 这一步到底做什么：给不同查询窗口跑真实时延，明确 `100ms` 到底在哪个区间还能成立。
  - 做完你能看到什么：后面写需求时不会再空口承诺“默认 100ms”。
  - 先依赖什么：0.2
  - 开始前先看：
    - `docs/20260315-小爱声纹测试结论与开发闸门.md`
  - 主要改哪里：无代码改动，只补 Spec 文档
  - 这一先不做什么：先不做性能优化实现
  - 怎么算完成：
    1. 已给出 `1s / 2s / 3s / 4s` 查询窗口的实测时延。
    2. 已写清楚第一版允许的窗口和超出后的处理方式。
  - 怎么验证：
    - 本地基准测试
  - 对应需求：`requirements.md` 闸门 C、非功能需求 1
  - 对应设计：`design.md` 3.3、8.1

- [x] 0.4 把测试结论回写到 Spec，形成开发闸门
  - 状态：DONE
  - 这一步到底做什么：把已经测出来的结论正式写进 README、requirements、design 和 docs，防止后面又回到口头约定。
  - 做完你能看到什么：任何人拿到 `005.3` 都知道“先测了什么、结论是什么、接下来才允许做什么”。
  - 先依赖什么：0.1、0.2、0.3
  - 开始前先看：
    - `README.md`
    - `requirements.md`
    - `design.md`
    - `docs/README.md`
  - 主要改哪里：
    - 当前 Spec 全部文档
  - 这一先不做什么：先不入库业务实现
  - 怎么算完成：
    1. 已新增测试结论文档。
    2. 已把“测试先行”写进需求、设计和任务。
  - 怎么验证：
    - 人工走查
  - 对应需求：`requirements.md` 闸门 A、闸门 B、闸门 C
  - 对应设计：`design.md` 1.4、2.2、8.1

---

## 阶段 1：先把数据结构和音频产物链路立住

- [ ] 1.1 定义声纹建档、样本和档案的数据模型
  - 状态：TODO
  - 这一步到底做什么：把建档任务、成员声纹档案、录音样本三类对象建成正式 model 和 schema，别再靠零散字段硬凑。
  - 做完你能看到什么：数据库里有清楚的表结构，后续建档、识别、清理都知道该挂在哪。
  - 先依赖什么：0.4
  - 开始前先看：
    - `requirements.md` 需求 1、需求 4、需求 7
    - `design.md` 4.3、5.1、5.2
    - `apps/api-server/migrations/20260311-数据库迁移规范.md`
    - `apps/api-server/app/modules/member/models.py`
  - 主要改哪里：
    - `apps/api-server/app/modules/voiceprint/`
    - `apps/api-server/migrations/versions/`
  - 这一先不做什么：先不接入 provider，不先做页面，不先做识别算法
  - 怎么算完成：
    1. `voiceprint_enrollments / member_voiceprint_profiles / member_voiceprint_samples` 三类对象有正式模型。
    2. 对应 Alembic migration 已经写出来。
  - 怎么验证：
    - `alembic upgrade head`
    - 新旧库迁移检查
  - 对应需求：`requirements.md` 需求 1、需求 4、需求 7
  - 对应设计：`design.md` 4.3、5.1、5.2

- [ ] 1.2 让 voice-runtime 在 commit 时落出可解析音频文件
  - 状态：TODO
  - 这一步到底做什么：把现在只在内存里攒音频块的 `voice-runtime` 补成正式音频产物链路，commit 时能落出 `.wav`，必要时保留 `.pcm`。
  - 做完你能看到什么：每次采样或对话 commit 后，系统都能拿到明确的音频文件和元数据，而不是只剩一堆临时字节。
  - 先依赖什么：1.1
  - 开始前先看：
    - `requirements.md` 需求 2、需求 5、需求 7
    - `design.md` 4.2、4.5.3、5.3
    - `apps/voice-runtime/voice_runtime/service.py`
    - `apps/voice-runtime/voice_runtime/app.py`
  - 主要改哪里：
    - `apps/voice-runtime/voice_runtime/service.py`
    - `apps/voice-runtime/voice_runtime/schemas.py`
    - `apps/voice-runtime/voice_runtime/app.py`
    - `apps/voice-runtime/tests/test_app.py`
  - 这一先不做什么：先不在 runtime 里做成员识别，也不把 provider 调用塞进 runtime
  - 怎么算完成：
    1. commit 返回里能拿到音频产物元数据。
    2. 落地文件可以被标准音频库读出来。
  - 怎么验证：
    - `python -m unittest tests.test_app`
    - 临时样本文件读取测试
  - 对应需求：`requirements.md` 需求 2、需求 5、需求 7
  - 对应设计：`design.md` 4.2、4.5.3、5.3

- [ ] 1.3 扩展 gateway 会话打标，支持“普通对话”和“建档采样”两种用途
  - 状态：TODO
  - 这一步到底做什么：让 gateway 知道当前终端是否存在待处理建档任务，并把会话用途打到上行事件里。
  - 做完你能看到什么：同一条小爱录音链路，系统能区分“这次是普通聊天”还是“这次是给某个成员采样”。
  - 先依赖什么：1.1、1.2
  - 开始前先看：
    - `requirements.md` 需求 1、需求 2
    - `design.md` 2.4.1、4.1、4.5.2
    - `apps/open-xiaoai-gateway/open_xiaoai_gateway/bridge.py`
    - `apps/open-xiaoai-gateway/open_xiaoai_gateway/translator.py`
    - `apps/api-server/app/api/v1/endpoints/devices.py`
  - 主要改哪里：
    - `apps/open-xiaoai-gateway/open_xiaoai_gateway/bridge.py`
    - `apps/open-xiaoai-gateway/open_xiaoai_gateway/translator.py`
    - `apps/api-server/app/api/v1/endpoints/devices.py`
    - `apps/open-xiaoai-gateway/tests/`
  - 这一先不做什么：先不在 gateway 里做声纹识别，不做最终成员判定
  - 怎么算完成：
    1. gateway 能拿到待建档任务摘要。
    2. `session.start / audio.commit` 能区分建档和普通对话。
  - 怎么验证：
    - gateway 单元测试
    - 事件流断言测试
  - 对应需求：`requirements.md` 需求 1、需求 2
  - 对应设计：`design.md` 2.4.1、4.1、4.5.2

### 阶段检查

- [ ] 1.4 阶段检查：音频样本是不是已经有正式落点
  - 状态：TODO
  - 这一步到底做什么：确认建档链路最底层已经站稳，后面不会一边接 provider 一边还在猜音频样本从哪来。
  - 做完你能看到什么：数据库对象、音频文件和 gateway 会话用途三件事能串起来。
  - 先依赖什么：1.1、1.2、1.3
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：本阶段全部相关文件
  - 这一先不做什么：不扩新需求，不提前做 UI
  - 怎么算完成：
    1. 样本文件路径和元数据能被正式记录。
    2. gateway 已能正确标识建档会话。
  - 怎么验证：
    - 人工走查
    - 样本链路回放测试
  - 对应需求：`requirements.md` 需求 1、需求 2、需求 7
  - 对应设计：`design.md` 2.4.1、4.1、4.2、5.2

---

## 阶段 2：把成员声纹建档主链补完整

- [ ] 2.1 新增 voiceprint 模块和建档管理 API
  - 状态：TODO
  - 这一步到底做什么：把建档任务创建、查询、取消、查看档案这些正式入口补出来，别让后面联调还靠脚本硬捅数据库。
  - 做完你能看到什么：管理员可以通过正式 API 管理成员建档任务和声纹档案。
  - 先依赖什么：1.4
  - 开始前先看：
    - `requirements.md` 需求 1、需求 4、需求 7
    - `design.md` 4.3、4.5.1、4.5.4
    - `apps/api-server/app/api/v1/endpoints/members.py`
  - 主要改哪里：
    - `apps/api-server/app/modules/voiceprint/`
    - `apps/api-server/app/api/v1/endpoints/voiceprints.py`
    - `apps/api-server/tests/`
  - 这一先不做什么：先不补大而全前端页面
  - 怎么算完成：
    1. 有正式 API 创建和查询建档任务。
    2. 有正式 API 查看和删除成员声纹档案。
  - 怎么验证：
    - API 单元测试
    - 集成测试
  - 对应需求：`requirements.md` 需求 1、需求 4、需求 7
  - 对应设计：`design.md` 4.3、4.5.1、4.5.4

- [ ] 2.2 接入首版声纹适配层，支持建档和更新档案
  - 状态：TODO
  - 这一步到底做什么：先把已经测通过的本地基线方案接进来，把样本文件送去做 embedding，再保存档案。
  - 做完你能看到什么：系统不只是保存录音，还能真正生成“这个成员的声纹档案”。
  - 先依赖什么：2.1
  - 开始前先看：
    - `requirements.md` 需求 3、需求 4、需求 6
    - `design.md` 3.1、3.2、6.2
    - `apps/api-server/app/modules/voice/identity_service.py`
  - 主要改哪里：
    - `apps/api-server/app/modules/voiceprint/provider.py`
    - `apps/api-server/app/modules/voiceprint/service.py`
    - `apps/api-server/tests/`
  - 这一先不做什么：先不把多家 provider SDK 逻辑散到 gateway 和 voice pipeline 里
  - 怎么算完成：
    1. 适配层支持建档、更新和识别三类调用。
    2. provider 失败时能明确回写任务和错误状态。
  - 怎么验证：
    - provider mock 测试
    - 超时和失败分支测试
  - 对应需求：`requirements.md` 需求 3、需求 4、需求 6
  - 对应设计：`design.md` 3.1、3.2、6.2

- [ ] 2.3 把建档任务、样本和档案状态真正串起来
  - 状态：TODO
  - 这一步到底做什么：把“创建任务 -> 采到样本 -> 校验样本 -> 调 provider -> 更新档案 -> 回写状态”串成一条完整主链。
  - 做完你能看到什么：建档这件事不再是半路断开的多个步骤，而是一条完整工作流。
  - 先依赖什么：2.2
  - 开始前先看：
    - `requirements.md` 需求 1、需求 2、需求 4
    - `design.md` 2.4.1、5.2、6.2
  - 主要改哪里：
    - `apps/api-server/app/modules/voiceprint/service.py`
    - `apps/api-server/app/modules/voice/pipeline.py`
    - `apps/api-server/tests/`
  - 这一先不做什么：先不做批量导入历史音频
  - 怎么算完成：
    1. 建档任务状态能从 `pending` 走到 `completed/failed`。
    2. 样本和档案版本能互相关联。
  - 怎么验证：
    - 建档流程集成测试
    - 失败重试测试
  - 对应需求：`requirements.md` 需求 1、需求 2、需求 4
  - 对应设计：`design.md` 2.4.1、5.2、6.2

### 阶段检查

- [ ] 2.4 阶段检查：成员声纹是不是已经能正式建出来
  - 状态：TODO
  - 这一步到底做什么：确认系统已经不是“会录音”，而是真的“会建档”。
  - 做完你能看到什么：指定成员能产出可追踪的声纹档案，失败也有明确状态。
  - 先依赖什么：2.1、2.2、2.3
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：本阶段全部相关文件
  - 这一先不做什么：不提前做对话前识别优化
  - 怎么算完成：
    1. 至少一条建档链路可被自动化测试证明成立。
    2. 样本、档案、任务状态可以互相追踪。
  - 怎么验证：
    - 端到端建档测试
    - 人工走查状态记录
  - 对应需求：`requirements.md` 需求 1、需求 2、需求 4、需求 7
  - 对应设计：`design.md` 2.4.1、4.3、5.2

---

## 阶段 3：把对话前身份判定接进正式语音主链

- [ ] 3.1 在 voice pipeline 里接入“先声纹，后上下文兜底”的身份解析顺序
  - 状态：TODO
  - 这一步到底做什么：把对话前身份判定顺序改成“先试声纹识别，失败再退回现有上下文推断”，并统一产出一份身份结果。
  - 做完你能看到什么：系统不再只是靠房间和活跃成员猜人，而是真正先跑一次声纹。
  - 先依赖什么：2.4
  - 开始前先看：
    - `requirements.md` 需求 5、需求 6
    - `design.md` 2.4.2、4.4、7.3
    - `apps/api-server/app/modules/voice/identity_service.py`
    - `apps/api-server/app/modules/voice/router.py`
    - `apps/api-server/app/modules/voice/pipeline.py`
  - 主要改哪里：
    - `apps/api-server/app/modules/voice/identity_service.py`
    - `apps/api-server/app/modules/voice/router.py`
    - `apps/api-server/app/modules/voice/pipeline.py`
    - `apps/api-server/tests/`
  - 这一先不做什么：先不搞多说话人识别
  - 怎么算完成：
    1. 普通对话会先尝试声纹识别。
    2. 最终身份结果仍通过统一 `VoiceIdentityResolution` 暴露。
  - 怎么验证：
    - voice pipeline 集成测试
    - 低置信度回退测试
  - 对应需求：`requirements.md` 需求 5、需求 6
  - 对应设计：`design.md` 2.4.2、4.4、7.3

- [ ] 3.2 确保 LLM 慢路径使用声纹识别出的成员身份
  - 状态：TODO
  - 这一步到底做什么：把识别出的成员真正传进 `conversation` 慢路径，别停留在日志里自嗨。
  - 做完你能看到什么：同一个小爱音响，不同成员说话时，LLM 对话上下文会按成员身份走。
  - 先依赖什么：3.1
  - 开始前先看：
    - `requirements.md` 需求 5
    - `design.md` 2.4.2、4.4
    - `apps/api-server/app/modules/voice/conversation_bridge.py`
  - 主要改哪里：
    - `apps/api-server/app/modules/voice/conversation_bridge.py`
    - `apps/api-server/tests/`
  - 这一先不做什么：先不补全部 persona 精细化配置
  - 怎么算完成：
    1. `conversation` 慢路径能拿到声纹识别出的成员 id。
    2. 没识别出来时仍能按现有逻辑回退。
  - 怎么验证：
    - conversation bridge 集成测试
    - 请求身份断言测试
  - 对应需求：`requirements.md` 需求 5、需求 6
  - 对应设计：`design.md` 2.4.2、4.4、7.2

- [ ] 3.3 回归快路径、权限和现有用户空间
  - 状态：TODO
  - 这一步到底做什么：确认加了声纹识别之后，设备控制快路径、匿名回退和默认对话主链都没被搞坏。
  - 做完你能看到什么：新能力是增强项，不是新炸弹。
  - 先依赖什么：3.2
  - 开始前先看：
    - `requirements.md` 需求 6
    - `design.md` 2.4.3、6.2、7.2
    - `apps/api-server/app/modules/voice/fast_action_service.py`
  - 主要改哪里：
    - `apps/api-server/tests/`
    - 视情况补 `apps/open-xiaoai-gateway/tests/`
  - 这一先不做什么：先不做高风险操作的额外生物识别确认
  - 怎么算完成：
    1. provider 不可用时普通对话还能继续。
    2. 快路径和慢路径读取的是同一份身份结果。
  - 怎么验证：
    - 降级回归测试
    - 快路径回归测试
  - 对应需求：`requirements.md` 需求 6
  - 对应设计：`design.md` 2.4.3、6.2、7.2、7.3

### 阶段检查

- [ ] 3.4 阶段检查：声纹识别是不是已经站到 LLM 前面了
  - 状态：TODO
  - 这一步到底做什么：确认系统已经真的做到“先识别身份，再进 LLM”，不是只把字段塞进数据库装样子。
  - 做完你能看到什么：慢路径对话前已经有正式身份结果，且回退策略清楚。
  - 先依赖什么：3.1、3.2、3.3
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：本阶段全部相关文件
  - 这一先不做什么：不追加新业务能力
  - 怎么算完成：
    1. 对话前身份解析顺序已经改对。
    2. 识别失败时不会打断主链。
  - 怎么验证：
    - 端到端对话回归测试
    - 人工走查
  - 对应需求：`requirements.md` 需求 5、需求 6
  - 对应设计：`design.md` 2.4.2、2.4.3、4.4

---

## 阶段 4：补测试、联调和交接文档

- [ ] 4.1 补齐 gateway、voice-runtime、api-server 三段测试
  - 状态：TODO
  - 这一步到底做什么：把最容易回归的三段链路都补上测试，不然以后谁一改语音链路，声纹能力就会被顺手搞死。
  - 做完你能看到什么：建档、音频落地、对话前识别和降级回退都有自动化保护。
  - 先依赖什么：3.4
  - 开始前先看：
    - `requirements.md` 全部需求
    - `design.md` 8.2、8.3、8.4
  - 主要改哪里：
    - `apps/open-xiaoai-gateway/tests/`
    - `apps/voice-runtime/tests/`
    - `apps/api-server/tests/`
  - 这一先不做什么：先不做实机长时间 soak test 自动化
  - 怎么算完成：
    1. 三段测试都覆盖成功、失败和降级路径。
    2. 关键主链有回归保护。
  - 怎么验证：
    - 分项目测试跑通
  - 对应需求：`requirements.md` 全部需求
  - 对应设计：`design.md` 8.2、8.3、8.4

- [ ] 4.2 写联调和验收文档
  - 状态：TODO
  - 这一步到底做什么：把建档怎么跑、样本怎么看、识别失败怎么查、隐私数据怎么清理写成文档，别让后面的人继续靠猜。
  - 做完你能看到什么：后续接手的人知道怎么验建档、怎么验识别、怎么定位问题。
  - 先依赖什么：4.1
  - 开始前先看：
    - `requirements.md` 需求 2、需求 6、需求 7
    - `design.md` 6、8、9
    - `specs/005.2-小爱原生优先与前缀接管/docs/`
  - 主要改哪里：
    - `specs/005.3-小爱声纹采集与身份识别/docs/`
  - 这一先不做什么：不写宣传稿，只写能干活的文档
  - 怎么算完成：
    1. 联调步骤写清楚。
    2. 样本文件、档案状态和识别结果的排查方式写清楚。
    3. 隐私清理规则写清楚。
  - 怎么验证：
    - 人工走查
  - 对应需求：`requirements.md` 需求 2、需求 6、需求 7
  - 对应设计：`design.md` 6、8、9

- [ ] 4.3 最终检查点
  - 状态：TODO
  - 这一步到底做什么：确认这份 Spec 真的把边界、数据、链路、回退和验证方式写完整了，而不是又留下一堆口头约定。
  - 做完你能看到什么：新的 Codex 上下文或新同事拿到这份 Spec，能直接接着干，不需要重新猜架构。
  - 先依赖什么：4.2
  - 开始前先看：
    - `README.md`
    - `requirements.md`
    - `design.md`
    - `tasks.md`
    - `docs/`
  - 主要改哪里：当前 Spec 全部文件
  - 这一先不做什么：不再扩需求
  - 怎么算完成：
    1. 需求、设计、任务能一一追踪。
    2. 数据结构、职责边界和验证方式都清楚。
    3. 后续接手的人知道先做什么、改哪里、怎么验。
  - 怎么验证：
    - 按 Spec 验收清单逐项核对
  - 对应需求：`requirements.md` 全部需求
  - 对应设计：`design.md` 全文
