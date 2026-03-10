# 任务文档 - 家庭问答提醒与场景编排

状态说明：

- `TODO`：尚未开始
- `IN_PROGRESS`：正在进行
- `DONE`：当前阶段已完成
- `BLOCKED`：被外部依赖阻塞

---

## 阶段 1：AI 基础架构与服务层底座

- [ ] 1.1 创建 AI 供应商配置、能力路由与调用审计模型
  - 状态：TODO
  - 目标：建立 `ai_provider_profiles`、`ai_capability_routes`、`ai_model_call_logs` 的迁移、模型与基础仓储能力
  - 依赖：无
  - 需求关联：`requirements.md` 需求 9 / 验收 9.1、9.2、9.3、9.4；需求 10 / 验收 10.1、10.2、10.3、10.4；需求 8 / 验收 8.1、8.2、8.4
  - 设计关联：`design.md` §3.0、§4.0、§5.0、§6.0
  - 上下文入口：
    - `requirements.md` 需求 8、需求 9、需求 10
    - `design.md` §3.0「AI 模型供应商抽象与能力路由」
    - `design.md` §4.0「AI 供应商配置模型」
    - `design.md` §5.0「AI 模型网关不变量」
    - `design.md` §6.0「AI 供应商错误处理」
  - 涉及产物：
    - `apps/api-server/migrations/`
    - `apps/api-server/app/modules/ai_gateway/`
    - `apps/api-server/app/core/config.py`
    - `apps/api-server/.env.example`
  - 执行说明：先把 AI 配置与治理模型钉死。密钥绝不能落业务库，数据库只保存 `secret_ref`；能力路由必须按能力而不是按页面硬编码。
  - 验收标准：
    1. 可创建并查询供应商档案、能力路由与调用日志结构
    2. 支持供应商能力枚举、路由模式、远端限制与密钥引用约束
    3. 运行时配置已为默认 provider、超时、降级模式和隐私开关预留环境变量
  - 验证方式：
    - `cd apps/api-server && .venv/bin/alembic upgrade head`
    - `cd apps/api-server && .venv/bin/python -m compileall app`
    - 服务层读写 `AiProviderProfile / AiCapabilityRoute`，验证能力位、远端限制和密钥引用结构正确

- [ ] 1.2 创建问答、提醒与场景编排的数据模型与迁移
  - 状态：TODO
  - 目标：建立 `qa_query_logs`、`reminder_tasks`、`reminder_runs`、`reminder_delivery_attempts`、`reminder_ack_events`、`scene_templates`、`scene_executions`、`scene_execution_steps` 的迁移、模型与基础仓储能力
  - 依赖：1.1
  - 需求关联：`requirements.md` 需求 3 / 验收 3.1、3.2、3.3；需求 4 / 验收 4.1、4.4；需求 5 / 验收 5.1、5.2；需求 6 / 验收 6.1、6.4；需求 8 / 验收 8.1、8.4
  - 设计关联：`design.md` §4.2、§4.3、§4.4、§4.5、§4.6、§4.7、§4.8、§4.9、§5.2、§5.3、§5.5
  - 上下文入口：
    - `requirements.md` 需求 3、需求 4、需求 5、需求 6、需求 8
    - `design.md` §4.2「QaQueryLog」
    - `design.md` §4.3「ReminderTask」
    - `design.md` §4.4「ReminderRun」
    - `design.md` §4.7「SceneTemplate」
    - `design.md` §4.8「SceneExecution」
  - 涉及产物：
    - `apps/api-server/migrations/`
    - `apps/api-server/app/modules/family_qa/`
    - `apps/api-server/app/modules/reminder/`
    - `apps/api-server/app/modules/scene/`
  - 执行说明：先把服务层业务对象钉死，提醒运行和场景执行必须独立建模，别偷懒把所有历史记录塞进一张 JSON 大表。
  - 验收标准：
    1. 可创建并查询问答、提醒与场景的核心对象
    2. 家庭边界与外键引用可验证
    3. 幂等键、版本号、状态字段的语义清晰
  - 验证方式：
    - `cd apps/api-server && .venv/bin/alembic upgrade head`
    - `cd apps/api-server && .venv/bin/python -m compileall app`
    - 服务层读写提醒任务、提醒运行与场景模板，验证状态字段与 JSON 结构可持久化

- [ ] 1.3 建立问答事实视图、AI 网关抽象与调度骨架
  - 状态：TODO
  - 目标：提供 `QaFactView` 组装、问答权限裁剪、AI 能力路由骨架、提醒槽位计算、场景触发去重与运行锁能力
  - 依赖：1.2
  - 需求关联：`requirements.md` 需求 1 / 验收 1.1、1.3、1.4；需求 2 / 验收 2.1、2.2、2.3；需求 4 / 验收 4.1、4.2；需求 9 / 验收 9.1、9.2、9.4；需求 10 / 验收 10.2、10.4
  - 设计关联：`design.md` §2.3.1、§2.3.2、§2.3.4、§2.3.6、§4.1、§5.0、§5.1、§5.2、§5.5、§6.0、§6.4
  - 上下文入口：
    - `requirements.md` 需求 1、需求 2、需求 4、需求 9、需求 10
    - `design.md` §2.3.1「问答查询流」
    - `design.md` §2.3.6「AI 能力路由与降级流」
    - `design.md` §4.1「QaFactView」
    - `design.md` §5.0「AI 模型网关不变量」
    - `design.md` §6.4「回滚与恢复策略」
  - 涉及产物：
    - `apps/api-server/app/modules/family_qa/`
    - `apps/api-server/app/modules/ai_gateway/`
    - `apps/api-server/app/modules/reminder_scheduler/`
    - `apps/api-server/app/modules/scene/`
    - `apps/api-server/app/modules/delivery/`
  - 执行说明：先做“能稳定算”的骨架，不做花哨 Agent。问答事实视图必须先拼装后裁剪；AI 请求统一走网关；提醒幂等键与场景触发键必须稳定。
  - 验收标准：
    1. 可生成家庭级事实视图并按请求者权限裁剪
    2. 可按能力读取主备供应商路由并形成统一调用上下文
    3. 可计算提醒槽位与场景触发去重键
  - 验证方式：
    - `cd apps/api-server && .venv/bin/python -m compileall app`
    - 服务层构造多成员、多房间、多权限场景，验证事实裁剪结果
    - 服务层重复计算同一提醒槽位、同一场景触发和同一 AI 路由请求，验证幂等键与路由上下文稳定不变

### 阶段检查点

- [ ] 1.4 AI 与服务层底座检查点
  - 状态：TODO
  - 目标：确认 AI 抽象层、数据模型、事实视图、调度骨架与幂等规则已经成型，可进入 API 与执行闭环实现
  - 依赖：1.1、1.2、1.3
  - 需求关联：`requirements.md` 需求 1、需求 2、需求 3、需求 4、需求 5、需求 6、需求 8、需求 9、需求 10
  - 设计关联：`design.md` §2、§3.0、§4、§5、§6
  - 上下文入口：
    - `requirements.md` 需求 1、需求 2、需求 3、需求 4、需求 5、需求 6、需求 8、需求 9、需求 10
    - `design.md` §2「架构设计」
    - `design.md` §3.0「AI 模型供应商抽象与能力路由」
    - `design.md` §4「数据模型」
    - `design.md` §5「正确性属性与业务不变量」
  - 涉及产物：阶段 1 全部相关文件
  - 执行说明：只检查结构闭环、边界与幂等策略，不扩展新接口。
  - 验收标准：
    1. AI 网关与能力路由可追踪
    2. 问答、提醒、场景三条主链路的幂等与降级策略明确
    3. 密钥、远端限制与隐私边界没有被业务层绕开
  - 验证方式：
    - 人工走查迁移、配置、模型与服务骨架
    - `cd apps/api-server && .venv/bin/alembic upgrade head`
    - 服务层回放重复触发场景、重复提醒槽位与 AI 供应商回退路径，验证不会无控制重复执行

---

## 阶段 2：AI 网关、问答与提醒闭环

- [ ] 2.1 实现 AI 供应商网关、能力路由与降级机制
  - 状态：TODO
  - 目标：交付统一模型网关，支持多供应商能力路由、主备切换、模板降级、隐私裁剪与调用审计
  - 依赖：1.4
  - 需求关联：`requirements.md` 需求 9 / 验收 9.1、9.2、9.3、9.4；需求 10 / 验收 10.1、10.2、10.3、10.4；需求 8 / 验收 8.1、8.2
  - 设计关联：`design.md` §2.3.6、§3.0、§4.0、§5.0、§6.0
  - 上下文入口：
    - `requirements.md` 需求 8、需求 9、需求 10
    - `design.md` §2.3.6「AI 能力路由与降级流」
    - `design.md` §3.0「AI 模型供应商抽象与能力路由」
    - `design.md` §6.0「AI 供应商错误处理」
  - 涉及产物：
    - `apps/api-server/app/modules/ai_gateway/`
    - `apps/api-server/app/api/v1/endpoints/ai_admin.py`
    - `apps/api-server/app/core/config.py`
    - `apps/api-server/.env.example`
  - 执行说明：把 AI 供应商差异收敛进网关，不许在业务里继续到处 `if provider == ...`。首期至少支持一个主供应商、一个备供应商和模板回答降级。
  - 验收标准：
    1. 可按能力读取主备供应商并调用统一适配器
    2. 可在超时、失败、限流时走回退路径并记录调用日志
    3. 可对敏感字段执行脱敏、阻断或本地优先策略
  - 验证方式：
    - `cd apps/api-server && .venv/bin/python -m compileall app`
    - 通过打桩 provider 验证主供应商成功、主失败切备、全部失败回模板三条路径
    - 查询 `ai_model_call_logs` 验证 provider、model、latency、fallback_used 已记录

- [ ] 2.2 实现家庭问答 API v1 与热门问题建议
  - 状态：TODO
  - 目标：提供可解释、可裁剪、只读的家庭问答接口与热门问题建议接口
  - 依赖：2.1
  - 需求关联：`requirements.md` 需求 1 / 验收 1.1、1.2、1.3、1.4；需求 2 / 验收 2.1、2.2、2.3、2.4；需求 8 / 验收 8.1、8.2、8.4；需求 9 / 验收 9.1、9.4
  - 设计关联：`design.md` §2.3.1、§3.0、§3.1、§3.2、§4.1、§4.2、§5.0、§5.1、§6.0、§6.1
  - 上下文入口：
    - `requirements.md` 需求 1、需求 2、需求 8、需求 9
    - `design.md` §3.0「AI 模型供应商抽象与能力路由」
    - `design.md` §3.1「家庭问答查询接口」
    - `design.md` §3.2「热门问题与建议接口」
    - `design.md` §5.1「问答不变量」
  - 涉及产物：
    - `apps/api-server/app/modules/family_qa/`
    - `apps/api-server/app/api/v1/endpoints/family_qa.py`
    - `apps/api-server/app/modules/audit/`
  - 执行说明：先支持高频问答，答案结构必须带证据事实与推断标记；问答文本生成可经网关润色，但事实与权限判断不能交给模型瞎猜。
  - 验收标准：
    1. 可回答成员状态、设备状态、提醒状态、场景状态等首期问题
    2. 无权限问题会被裁剪或拒绝
    3. 回答包含事实引用、置信度、降级标记与模型回退信息（如发生）
  - 验证方式：
    - `cd apps/api-server && .venv/bin/python -m compileall app`
    - 通过端点函数直调验证正常问答、权限裁剪和信息不足降级路径
    - 查询问答日志与 AI 调用日志，验证请求摘要、证据引用和模型路由可追踪

- [ ] 2.3 实现提醒任务 CRUD 与提醒总览接口
  - 状态：TODO
  - 目标：提供提醒任务管理与家庭级提醒总览，支撑后续调度和管理台展示
  - 依赖：1.4
  - 需求关联：`requirements.md` 需求 3 / 验收 3.1、3.2、3.3、3.4；需求 7 / 验收 7.1、7.4；需求 8 / 验收 8.1、8.4
  - 设计关联：`design.md` §3.3、§3.4、§4.3、§4.4、§5.2、§6.2
  - 上下文入口：
    - `requirements.md` 需求 3、需求 7、需求 8
    - `design.md` §3.3「提醒任务管理接口」
    - `design.md` §3.4「提醒总览、手动触发与确认接口」
    - `design.md` §4.3「ReminderTask」
  - 涉及产物：
    - `apps/api-server/app/modules/reminder/`
    - `apps/api-server/app/api/v1/endpoints/reminders.py`
    - `apps/api-server/app/modules/audit/`
  - 执行说明：提醒管理先做成清晰的结构化配置，不做“自然语言创建提醒”的花活。
  - 验收标准：
    1. 可创建、修改、删除、启停提醒任务
    2. 可查询提醒总览、下次触发时间与最近执行摘要
    3. 家庭边界与字段约束可被正确验证
  - 验证方式：
    - `cd apps/api-server && .venv/bin/python -m compileall app`
    - 端点函数直调验证创建、更新、禁用、删除和总览查询
    - 查询数据库验证历史运行记录不会随任务删除而丢失

- [ ] 2.4 实现提醒调度、送达、确认与升级闭环
  - 状态：TODO
  - 目标：让提醒从静态配置变成真实可运行的服务链路，具备送达、确认与升级能力
  - 依赖：2.3
  - 需求关联：`requirements.md` 需求 4 / 验收 4.1、4.2、4.3、4.4；需求 7 / 验收 7.3、7.4；需求 8 / 验收 8.1、8.2、8.3、8.4
  - 设计关联：`design.md` §2.3.2、§2.3.3、§3.4、§4.4、§4.5、§4.6、§5.2、§5.3、§6.2、§6.4
  - 上下文入口：
    - `requirements.md` 需求 4、需求 7、需求 8
    - `design.md` §2.3.2「提醒调度流」
    - `design.md` §2.3.3「提醒送达与确认流」
    - `design.md` §5.3「提醒确认不变量」
  - 涉及产物：
    - `apps/api-server/app/modules/reminder_scheduler/`
    - `apps/api-server/app/modules/delivery/`
    - `apps/api-server/app/modules/reminder/`
    - `apps/api-server/app/api/v1/endpoints/reminders.py`
  - 执行说明：先把“任务 → 运行 → 送达 → 确认 → 升级”这条链路钉实，不做复杂多渠道生态适配；可以先用管理台通知、日志和音箱播报骨架承接。
  - 验收标准：
    1. 可按定时或条件触发生成提醒运行
    2. 可记录送达尝试，并根据确认结果停止或继续升级
    3. 调度器重启或重复触发时不会无控制重复创建运行
  - 验证方式：
    - `cd apps/api-server && .venv/bin/python -m compileall app`
    - 服务层构造服药提醒与家庭公告场景，验证运行、送达、确认与升级状态流转
    - 重复执行同一槽位调度，验证仅生成一个有效运行

### 阶段检查点

- [ ] 2.5 AI、问答与提醒闭环检查点
  - 状态：TODO
  - 目标：确认 AI 网关、问答与提醒都已形成可演示闭环，可进入场景编排与前端服务中心集成
  - 依赖：2.1、2.2、2.3、2.4
  - 需求关联：`requirements.md` 需求 1、需求 2、需求 3、需求 4、需求 7、需求 8、需求 9、需求 10
  - 设计关联：`design.md` §2.3.1、§2.3.2、§2.3.3、§2.3.6、§3.0、§3.1、§3.3、§3.4、§5.0、§5.1、§5.2、§5.3
  - 上下文入口：
    - `requirements.md` 需求 1、需求 2、需求 3、需求 4、需求 7、需求 8、需求 9、需求 10
    - `design.md` §3.0、§3.1、§3.3、§3.4
    - `design.md` §5.0、§5.1、§5.2、§5.3
  - 涉及产物：阶段 2 全部相关文件
  - 执行说明：验证闭环，不新增通用智能体或复杂规则能力。
  - 验收标准：
    1. AI 请求统一走网关且回退路径可追踪
    2. 问答结果可解释且受权限约束
    3. 提醒从创建到确认的链路可验证
  - 验证方式：
    - 人工走查 AI 网关、问答、提醒接口与服务实现
    - 关键流程回放：AI 主备切换、问答请求、定时提醒、未响应升级、确认终止升级

---

## 阶段 3：模板场景与管理台服务中心

- [ ] 3.1 实现场景模板注册、预览与手动触发接口
  - 状态：TODO
  - 目标：提供首批模板场景的配置、预览和手动触发入口
  - 依赖：2.5
  - 需求关联：`requirements.md` 需求 5 / 验收 5.1、5.2、5.3、5.4；需求 7 / 验收 7.1、7.3、7.4
  - 设计关联：`design.md` §3.5、§4.7、§5.4、§5.5、§6.3
  - 上下文入口：
    - `requirements.md` 需求 5、需求 7
    - `design.md` §3.5「场景模板与手动触发接口」
    - `design.md` §4.7「SceneTemplate」
    - `design.md` §5.5「场景冲突与冷却不变量」
  - 涉及产物：
    - `apps/api-server/app/modules/scene/`
    - `apps/api-server/app/api/v1/endpoints/scenes.py`
    - `apps/api-server/app/modules/audit/`
  - 执行说明：先实现固定模板注册与有限参数覆盖，不做通用自由编排器。
  - 验收标准：
    1. 可启停并查询三类模板场景
    2. 可返回预览结果，包括计划动作和守卫命中情况
    3. 可手动触发场景并生成执行记录
  - 验证方式：
    - `cd apps/api-server && .venv/bin/python -m compileall app`
    - 端点函数直调验证三类模板查询、预览与手动触发
    - 查询执行记录验证触发来源与预览/执行结果可追踪

- [ ] 3.2 实现场景执行、守卫、冲突处理与审计闭环
  - 状态：TODO
  - 目标：让模板场景具备真正可控的执行能力，并能和提醒、设备动作、安全守卫形成闭环
  - 依赖：3.1
  - 需求关联：`requirements.md` 需求 6 / 验收 6.1、6.2、6.3、6.4；需求 8 / 验收 8.1、8.2、8.3、8.4；需求 9 / 验收 9.4
  - 设计关联：`design.md` §2.3.4、§2.3.5、§4.8、§4.9、§5.4、§5.5、§6.3、§6.4
  - 上下文入口：
    - `requirements.md` 需求 6、需求 8、需求 9
    - `design.md` §2.3.4「场景触发评估流」
    - `design.md` §2.3.5「场景执行与审计流」
    - `design.md` §5.4「场景安全不变量」
    - `design.md` §5.5「场景冲突与冷却不变量」
  - 涉及产物：
    - `apps/api-server/app/modules/scene/`
    - `apps/api-server/app/modules/device_action/`
    - `apps/api-server/app/modules/reminder/`
    - `apps/api-server/app/api/v1/endpoints/scenes.py`
  - 执行说明：把场景看成“结构化步骤执行器”，不是万能魔法。设备动作、广播、提醒都必须走既有受控路径；场景解释若走 AI，也必须经过统一网关。
  - 验收标准：
    1. 场景可按步骤执行提醒、广播和设备动作
    2. 静默时段、儿童保护、敏感房间和高风险动作守卫有效
    3. 冲突、冷却、部分失败和阻断都可被正确记录与解释
  - 验证方式：
    - `cd apps/api-server && .venv/bin/python -m compileall app`
    - 回放智能回家、儿童睡前、老人关怀三个模板链路
    - 查询 `scene_executions / scene_execution_steps / audit_logs` 验证执行、跳过与失败记录

- [ ] 3.3 实现管理台服务中心页面、context-center 摘要联动与 AI 配置摘要
  - 状态：TODO
  - 目标：交付可演示的服务中心页面，并在 `context-center` 补充问答、提醒、场景、AI 路由摘要入口
  - 依赖：3.2
  - 需求关联：`requirements.md` 需求 7 / 验收 7.1、7.2、7.3、7.4；需求 9 / 验收 9.3；需求 10 / 验收 10.1、10.4
  - 设计关联：`design.md` §3.0、§3.7、§7.4、§8.1
  - 上下文入口：
    - `requirements.md` 需求 7、需求 9、需求 10
    - `design.md` §3.0「AI 模型供应商抽象与能力路由」
    - `design.md` §3.7「管理台页面设计」
    - `design.md` §7.4「管理台联调」
    - `design.md` §8.1「当前明确风险」
  - 涉及产物：
    - `apps/admin-web/src/pages/ServiceCenterPage.tsx`
    - `apps/admin-web/src/components/service/`
    - `apps/admin-web/src/lib/api.ts`
    - `apps/admin-web/src/types.ts`
    - `apps/admin-web/src/pages/ContextCenterPage.tsx`
  - 执行说明：服务中心做统一入口，`context-center` 只补摘要卡与跳转。AI 供应商配置首期可以只做摘要与只读状态，不必一口气做完整治理台。
  - 验收标准：
    1. 页面可执行示例问答、查看提醒与场景最近运行状态
    2. 可展示当前问答能力的主供应商、回退策略与最近降级状态摘要
    3. `context-center` 可展示服务摘要并跳转到服务中心
  - 验证方式：
    - `cd apps/admin-web && npm run build`
    - 管理台手工联调：问答、提醒确认、场景预览、手动触发与 AI 回退摘要

- [ ] 3.4 补齐联调说明与代表场景验收文档
  - 状态：TODO
  - 目标：形成 AI 网关、问答、提醒、场景编排的前后端联调与验收文档，明确边界和已知风险
  - 依赖：3.3
  - 需求关联：`requirements.md` 需求 5、需求 6、需求 7、需求 8、需求 9、需求 10
  - 设计关联：`design.md` §7.2、§7.3、§7.4、§8.1、§8.2
  - 上下文入口：
    - `requirements.md` 需求 5、需求 6、需求 7、需求 8、需求 9、需求 10
    - `design.md` §7.2「集成测试」
    - `design.md` §7.3「场景回放测试」
    - `design.md` §7.4「管理台联调」
    - `design.md` §8「风险与延期项」
  - 涉及产物：
    - `specs/002.1-家庭问答提醒与场景编排/docs/20260310-家庭服务中心与AI网关-前后端联调说明-v0.1.md`
    - `specs/002.1-家庭问答提醒与场景编排/docs/20260310-家庭服务中心-代表场景验收记录-v0.1.md`
  - 执行说明：文档必须讲清“能做什么、不能做什么、失败时怎么退、AI 供应商怎么切、哪些能力还是占位”。
  - 验收标准：
    1. 联调路径完整可执行
    2. 三个代表场景与 AI 主备切换路径有明确验收记录
    3. 已知风险与延期项有明确记录
  - 验证方式：
    - 文档走查
    - 按三条代表链路与一条 AI 回退链路复核联调步骤与结果

### 最终检查点

- [ ] 3.5 最终检查点
  - 状态：TODO
  - 目标：确认家庭问答、提醒、模板场景编排与 AI 供应商抽象层已经满足当前阶段可交付条件，可继续支撑后续服务成熟化
  - 依赖：3.4
  - 需求关联：`requirements.md` 全部需求
  - 设计关联：`design.md` 全文
  - 上下文入口：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
    - `docs/`
  - 涉及产物：当前 Spec 全部文件
  - 执行说明：核对需求、设计、任务、接口、页面、联调说明、风险说明和验收记录，不再追加新范围。
  - 验收标准：
    1. 需求到设计到任务可完整追踪
    2. 问答、提醒、场景、AI 供应商抽象四类能力边界清晰
    3. 已知延期项和风险已被记录，不再假装不存在
  - 验证方式：
    - 按 Spec 清单逐项走查
    - 回放代表链路并核对文档与实现一致性
