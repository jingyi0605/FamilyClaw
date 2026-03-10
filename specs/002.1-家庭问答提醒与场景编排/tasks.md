# 任务清单 - 家庭问答、提醒与场景编排（人话版）

状态说明：

- `TODO`：还没开始
- `IN_PROGRESS`：正在做
- `DONE`：已经做完，并且已经回写任务状态
- `BLOCKED`：卡住了，得先解决外部问题

使用规则：

- 这份文档是给人看的，不是给机器堆黑话的
- 每个任务都要先说清楚“这一步到底做什么”
- 每个任务都要说清楚“这一步先不做什么”，防止做着做着范围失控
- 每完成一个任务，必须立刻回写这里的状态

---

## 阶段 1：先把后端底座搭起来

- [x] 1.1 建 AI 供应商配置、能力路由和调用日志
  - 状态：DONE
  - 这一步到底做什么：先把 AI 相关的三本账建好——有哪些供应商、不同能力走谁、每次模型调用怎么记日志。
  - 做完你能看到什么：数据库里有 `ai_provider_profiles`、`ai_capability_routes`、`ai_model_call_logs`，代码里有对应模型、迁移和基础服务层。
  - 先依赖什么：无
  - 开始前先看：
    - `requirements.md` 需求 8、需求 9、需求 10
    - `design.md` §3.0「AI 模型供应商抽象与能力路由」
    - `design.md` §4.0「AI 供应商配置模型」
    - `design.md` §5.0「AI 模型网关不变量」
    - `design.md` §6.0「AI 供应商错误处理」
  - 主要改哪里：
    - `apps/api-server/migrations/`
    - `apps/api-server/app/modules/ai_gateway/`
    - `apps/api-server/app/core/config.py`
    - `apps/api-server/.env.example`
  - 这一步先不做什么：先不接真实供应商 SDK，先不做问答接口。
  - 怎么算完成：
    1. 能创建和查询供应商档案、能力路由、调用日志
    2. 数据库里不存明文密钥，只存 `secret_ref`
    3. 运行时配置里已经留出主备、超时、重试、本地优先、禁止远端这些开关
  - 怎么验证：
    - `cd apps/api-server && python -m compileall app`
    - 能通过服务层读写 `AiProviderProfile / AiCapabilityRoute`
  - 对应需求：`requirements.md` 需求 8、9、10
  - 对应设计：`design.md` §3.0、§4.0、§5.0、§6.0

- [x] 1.2 建问答、提醒、场景三块的核心数据表
  - 状态：DONE
  - 这一步到底做什么：把后面业务真正要用的几本账先建出来，别等做到一半才发现数据没地方落。
  - 做完你能看到什么：数据库里有问答日志、提醒任务/运行/送达/确认、场景模板/执行/步骤这些表和对应模型。
  - 先依赖什么：1.1
  - 开始前先看：
    - `requirements.md` 需求 3、需求 4、需求 5、需求 6、需求 8
    - `design.md` §4.2「QaQueryLog」
    - `design.md` §4.3「ReminderTask」
    - `design.md` §4.4「ReminderRun」
    - `design.md` §4.7「SceneTemplate」
    - `design.md` §4.8「SceneExecution」
  - 主要改哪里：
    - `apps/api-server/migrations/`
    - `apps/api-server/app/modules/family_qa/`
    - `apps/api-server/app/modules/reminder/`
    - `apps/api-server/app/modules/scene/`
  - 这一步先不做什么：先不开放 API，先不做调度器，先不做真实场景执行。
  - 怎么算完成：
    1. 问答、提醒、场景的核心对象都能创建和查询
    2. 家庭边界、外键、版本号、状态字段语义清楚
    3. 提醒和场景历史不是乱塞到一张 JSON 大表里
  - 怎么验证：
    - `cd apps/api-server && python -m compileall app migrations`
    - 通过服务层读写提醒任务、提醒运行和场景模板
  - 对应需求：`requirements.md` 需求 3、4、5、6、8
  - 对应设计：`design.md` §4.2、§4.3、§4.4、§4.5、§4.6、§4.7、§4.8、§4.9

- [x] 1.3 先把问答资料包、AI 路由骨架和防重复逻辑做出来
  - 状态：DONE
  - 这一步到底做什么：把“后面业务能跑起来”的公共骨架先做掉，包括问答前要拼的资料包、统一的 AI 调用入口、提醒防重复槽位、场景防重复触发。
  - 做完你能看到什么：
    - 能组装 `QaFactView`
    - 能按请求人权限裁掉不该看的内容
    - 能按 capability 读出 AI 路由
    - 能稳定算出提醒槽位键和场景触发键
  - 先依赖什么：1.2
  - 开始前先看：
    - `requirements.md` 需求 1、需求 2、需求 4、需求 9、需求 10
    - `design.md` §2.3.1「问答查询流」
    - `design.md` §2.3.6「AI 能力路由与降级流」
    - `design.md` §4.1「QaFactView」
    - `design.md` §5.0「AI 模型网关不变量」
    - `design.md` §6.4「回滚与恢复策略」
  - 主要改哪里：
    - `apps/api-server/app/modules/family_qa/`
    - `apps/api-server/app/modules/ai_gateway/`
    - `apps/api-server/app/modules/reminder_scheduler/`
    - `apps/api-server/app/modules/scene/`
    - `apps/api-server/app/modules/delivery/`
  - 这一步先不做什么：
    - 不做完整问答 API
    - 不接真实 AI SDK
    - 不做复杂智能体
  - 怎么算完成：
    1. 能生成家庭级问答资料包，并按成员权限裁剪
    2. 能按 capability 取到主供应商、备供应商和降级策略
    3. 同一个提醒不会因为重复调度生成多份运行
    4. 同一个场景不会因为重复触发无限连发
  - 怎么验证：
    - `cd apps/api-server && python -m compileall app`
    - 构造多成员、多房间、多权限场景，检查裁剪结果
    - 重复计算同一提醒槽位和同一场景触发键，结果应稳定不变
  - 对应需求：`requirements.md` 需求 1、2、4、9、10
  - 对应设计：`design.md` §2.3.1、§2.3.6、§4.1、§5.0、§5.1、§5.2、§5.5、§6.0、§6.4

### 阶段检查

- [x] 1.4 检查后端底座是不是已经站稳了
  - 状态：DONE
  - 这一步到底做什么：不加新功能，只检查阶段 1 的底座是不是已经能支撑后面的 API 和执行逻辑。
  - 做完你能看到什么：AI、问答、提醒、场景这几块的基础结构都已经清楚，不会后面一做接口就返工表结构。
  - 先依赖什么：1.1、1.2、1.3
  - 开始前先看：
    - `requirements.md` 需求 1、2、3、4、5、6、8、9、10
    - `design.md` §2
    - `design.md` §3.0
    - `design.md` §4
    - `design.md` §5
    - `design.md` §6
  - 主要改哪里：阶段 1 全部相关文件
  - 这一步先不做什么：不新增接口，不补新页面。
  - 怎么算完成：
    1. AI 调用只能走网关这件事已经守住
    2. 问答、提醒、场景三条链路的主数据结构已经够用
    3. 幂等、防重复、隐私边界这些关键规则已经落地
  - 怎么验证：
    - 人工走查迁移、配置、模型和服务骨架
    - `cd apps/api-server && python -m compileall app migrations`
  - 对应需求：`requirements.md` 需求 1、2、3、4、5、6、8、9、10
  - 对应设计：`design.md` §2、§3.0、§4、§5、§6

---

## 阶段 2：把 AI、问答、提醒做成真正能跑的闭环

- [x] 2.1 做统一的 AI 网关，支持主备切换和降级
  - 状态：DONE
  - 这一步到底做什么：把所有模型调用都收口到一个地方，统一处理主供应商、备供应商、超时、限流、降级和日志。
  - 做完你能看到什么：业务层只需要说“我要 `qa_generation`”，不需要自己判断该调哪个供应商。
  - 先依赖什么：1.4
  - 开始前先看：
    - `requirements.md` 需求 8、需求 9、需求 10
    - `design.md` §2.3.6「AI 能力路由与降级流」
    - `design.md` §3.0「AI 模型供应商抽象与能力路由」
    - `design.md` §6.0「AI 供应商错误处理」
  - 主要改哪里：
    - `apps/api-server/app/modules/ai_gateway/`
    - `apps/api-server/app/api/v1/endpoints/ai_admin.py`
    - `apps/api-server/app/core/config.py`
    - `apps/api-server/.env.example`
  - 这一步先不做什么：先不做特别复杂的模型治理台。
  - 怎么算完成：
    1. 能按能力读取主备路由并执行统一调用
    2. 主供应商失败时能切到备供应商或模板降级
    3. 每次调用都能记日志，并保留回退信息
  - 怎么验证：
    - `cd apps/api-server && python -m compileall app`
    - 用打桩 provider 验证主成功、主失败切备、全部失败走模板三条路径
  - 对应需求：`requirements.md` 需求 8、9、10
  - 对应设计：`design.md` §2.3.6、§3.0、§4.0、§5.0、§6.0

- [x] 2.2 做家庭问答接口和热门问题建议
  - 状态：DONE
  - 这一步到底做什么：把家庭问答真正做成一个只读接口，并加一个“猜你想问什么”的建议接口。
  - 做完你能看到什么：能问“谁在家”“设备是不是开着”“提醒有没有完成”“场景最近有没有跑”这类高频问题。
  - 先依赖什么：2.1
  - 开始前先看：
    - `requirements.md` 需求 1、需求 2、需求 8、需求 9
    - `design.md` §3.1「家庭问答查询接口」
    - `design.md` §3.2「热门问题与建议接口」
    - `design.md` §5.1「问答不变量」
  - 主要改哪里：
    - `apps/api-server/app/modules/family_qa/`
    - `apps/api-server/app/api/v1/endpoints/family_qa.py`
    - `apps/api-server/app/modules/audit/`
  - 这一步先不做什么：
    - 不做能触发设备动作的“会执行的问答”
    - 不让模型自己编事实
  - 怎么算完成：
    1. 高频家庭问题能返回答案
    2. 无权限的信息会被裁掉或拒绝
    3. 返回里能看到事实依据、置信度和降级标记
  - 怎么验证：
    - `cd apps/api-server && python -m compileall app`
    - 直调端点函数验证正常回答、权限裁剪和信息不足降级
  - 对应需求：`requirements.md` 需求 1、2、8、9
  - 对应设计：`design.md` §2.3.1、§3.1、§3.2、§4.1、§4.2、§5.0、§5.1、§6.0、§6.1

- [x] 2.3 做提醒任务管理和提醒总览接口
  - 状态：DONE
  - 这一步到底做什么：把提醒从“只有表”变成“可以配、可以改、可以看总览”的服务。
  - 做完你能看到什么：管理台可以创建提醒、停用提醒、看最近执行情况和下一次触发时间。
  - 先依赖什么：1.4
  - 开始前先看：
    - `requirements.md` 需求 3、需求 7、需求 8
    - `design.md` §3.3「提醒任务管理接口」
    - `design.md` §3.4「提醒总览、手动触发与确认接口」
    - `design.md` §4.3「ReminderTask」
  - 主要改哪里：
    - `apps/api-server/app/modules/reminder/`
    - `apps/api-server/app/api/v1/endpoints/reminders.py`
    - `apps/api-server/app/modules/audit/`
  - 这一步先不做什么：不做“自然语言一句话生成提醒”。
  - 怎么算完成：
    1. 能创建、修改、删除、启停提醒任务
    2. 能看家庭级提醒总览和最近执行摘要
    3. 字段校验和家庭边界有效
  - 怎么验证：
    - `cd apps/api-server && python -m compileall app`
    - 直调端点函数验证创建、修改、删除、查询和总览
  - 对应需求：`requirements.md` 需求 3、7、8
  - 对应设计：`design.md` §3.3、§3.4、§4.3、§4.4、§5.2、§6.2

- [x] 2.4 做提醒调度、送达、确认和升级闭环
  - 状态：DONE
  - 这一步到底做什么：把提醒从“静态配置”变成“真的会跑”，包括触发、送达、确认和没人响应时的升级。
  - 做完你能看到什么：提醒能变成一次次具体运行，能记录送达尝试，能被成员确认，也能在必要时升级。
  - 先依赖什么：2.3
  - 开始前先看：
    - `requirements.md` 需求 4、需求 7、需求 8
    - `design.md` §2.3.2「提醒调度流」
    - `design.md` §2.3.3「提醒送达与确认流」
    - `design.md` §5.3「提醒确认不变量」
  - 主要改哪里：
    - `apps/api-server/app/modules/reminder_scheduler/`
    - `apps/api-server/app/modules/delivery/`
    - `apps/api-server/app/modules/reminder/`
    - `apps/api-server/app/api/v1/endpoints/reminders.py`
  - 这一步先不做什么：先不做复杂的第三方送达生态，只要把主链路跑通。
  - 怎么算完成：
    1. 能按时间或条件生成提醒运行
    2. 能记录送达尝试，并根据确认结果停止或继续升级
    3. 重复触发或调度器重启时不会无限重复创建运行
  - 怎么验证：
    - `cd apps/api-server && python -m compileall app`
    - 构造服药提醒和家庭公告两个例子，验证状态流转
    - 重复执行同一槽位调度，只应生成一个有效运行
  - 对应需求：`requirements.md` 需求 4、7、8
  - 对应设计：`design.md` §2.3.2、§2.3.3、§3.4、§4.4、§4.5、§4.6、§5.2、§5.3、§6.2、§6.4

### 阶段检查

- [x] 2.5 检查 AI、问答、提醒是不是已经形成闭环
  - 状态：DONE
  - 这一步到底做什么：确认第二阶段的主链路已经跑通，可以开始接场景和前端。
  - 做完你能看到什么：AI 网关、家庭问答、提醒服务三块已经能演示，不是只有表没有流程。
  - 先依赖什么：2.1、2.2、2.3、2.4
  - 开始前先看：
    - `requirements.md` 需求 1、2、3、4、7、8、9、10
    - `design.md` §3.0、§3.1、§3.3、§3.4
    - `design.md` §5.0、§5.1、§5.2、§5.3
  - 主要改哪里：阶段 2 全部相关文件
  - 这一步先不做什么：不扩成通用智能体平台。
  - 怎么算完成：
    1. AI 请求统一走网关
    2. 问答结果可解释而且受权限约束
    3. 提醒从创建到确认的主链路可验证
  - 怎么验证：
    - 人工走查接口和服务实现
    - 回放主备切换、问答请求、定时提醒、未响应升级、确认终止升级
  - 对应需求：`requirements.md` 需求 1、2、3、4、7、8、9、10
  - 对应设计：`design.md` §2.3.1、§2.3.2、§2.3.3、§2.3.6、§3.0、§3.1、§3.3、§3.4、§5.0、§5.1、§5.2、§5.3

---

## 阶段 3：把场景和管理台做成可演示版本

- [x] 3.1 做场景模板、预览和手动触发接口
  - 状态：DONE
  - 这一步到底做什么：先把固定模板场景做起来，让人能查、能预览、能手动触发。
  - 做完你能看到什么：至少能管理三类模板场景，并看到“如果现在触发，会做什么”。
  - 先依赖什么：2.5
  - 开始前先看：
    - `requirements.md` 需求 5、需求 7
    - `design.md` §3.5「场景模板与手动触发接口」
    - `design.md` §4.7「SceneTemplate」
    - `design.md` §5.5「场景冲突与冷却不变量」
  - 主要改哪里：
    - `apps/api-server/app/modules/scene/`
    - `apps/api-server/app/api/v1/endpoints/scenes.py`
    - `apps/api-server/app/modules/audit/`
  - 这一步先不做什么：不做任意拖拽编排器。
  - 怎么算完成：
    1. 能启停和查询三类模板场景
    2. 能返回预览结果，包括计划动作和守卫命中情况
    3. 能手动触发并生成执行记录
  - 怎么验证：
    - `cd apps/api-server && python -m compileall app`
    - 直调端点函数验证模板查询、预览、手动触发
  - 对应需求：`requirements.md` 需求 5、7
  - 对应设计：`design.md` §3.5、§4.7、§5.4、§5.5、§6.3

- [x] 3.2 做场景真正执行、守卫、冲突处理和审计
  - 状态：DONE
  - 这一步到底做什么：让场景不只是“能触发”，而是真的能按步骤执行，并且遇到高风险、冲突和冷却时表现正确。
  - 做完你能看到什么：场景可以调用提醒、广播和设备动作，失败和阻断也都能解释清楚。
  - 先依赖什么：3.1
  - 开始前先看：
    - `requirements.md` 需求 6、需求 8、需求 9
    - `design.md` §2.3.4「场景触发评估流」
    - `design.md` §2.3.5「场景执行与审计流」
    - `design.md` §5.4「场景安全不变量」
    - `design.md` §5.5「场景冲突与冷却不变量」
  - 主要改哪里：
    - `apps/api-server/app/modules/scene/`
    - `apps/api-server/app/modules/device_action/`
    - `apps/api-server/app/modules/reminder/`
    - `apps/api-server/app/api/v1/endpoints/scenes.py`
  - 这一步先不做什么：不做“万能 AI 场景引擎”。
  - 怎么算完成：
    1. 场景能按步骤执行提醒、广播和设备动作
    2. 静默时段、儿童保护、敏感房间、高风险动作守卫生效
    3. 冲突、冷却、部分失败和阻断都有记录，也能解释
  - 怎么验证：
    - `cd apps/api-server && python -m compileall app`
    - 回放智能回家、儿童睡前、老人关怀三条链路
    - 查询 `scene_executions / scene_execution_steps / audit_logs`
  - 对应需求：`requirements.md` 需求 6、8、9
  - 对应设计：`design.md` §2.3.4、§2.3.5、§4.8、§4.9、§5.4、§5.5、§6.3、§6.4

- [x] 3.3 做管理台服务中心页面，并和 context-center 联动
  - 状态：DONE
  - 这一步到底做什么：给管理台一个统一入口，把问答、提醒、场景、AI 路由摘要都摆出来。
  - 做完你能看到什么：页面上能看问答、提醒、场景最近状态，也能看到 AI 主备和降级摘要。
  - 先依赖什么：3.2
  - 开始前先看：
    - `requirements.md` 需求 7、需求 9、需求 10
    - `design.md` §3.0「AI 模型供应商抽象与能力路由」
    - `design.md` §3.7「管理台页面设计」
    - `design.md` §7.4「管理台联调」
    - `design.md` §8.1「当前明确风险」
  - 主要改哪里：
    - `apps/admin-web/src/pages/ServiceCenterPage.tsx`
    - `apps/admin-web/src/components/service/`
    - `apps/admin-web/src/lib/api.ts`
    - `apps/admin-web/src/types.ts`
    - `apps/admin-web/src/pages/ContextCenterPage.tsx`
  - 这一步先不做什么：先不做完整 AI 供应商治理后台，首期只要摘要和只读状态。
  - 怎么算完成：
    1. 页面能执行示例问答，能看提醒和场景最近运行状态
    2. 能看当前问答能力的主供应商、回退策略和最近降级摘要
    3. `context-center` 能展示服务摘要并跳转过去
  - 怎么验证：
    - `cd apps/admin-web && npm run build`
    - 管理台手工联调问答、提醒确认、场景预览和手动触发
  - 对应需求：`requirements.md` 需求 7、9、10
  - 对应设计：`design.md` §3.0、§3.7、§7.4、§8.1

- [x] 3.4 补联调说明和验收记录文档
  - 状态：DONE
  - 这一步到底做什么：把“怎么联调、怎么验收、哪些地方还没做”写清楚，别让后面的人靠猜。
  - 做完你能看到什么：至少有两份能直接拿来走流程的文档：联调说明和代表场景验收记录。
  - 先依赖什么：3.3
  - 开始前先看：
    - `requirements.md` 需求 5、6、7、8、9、10
    - `design.md` §7.2「集成测试」
    - `design.md` §7.3「场景回放测试」
    - `design.md` §7.4「管理台联调」
    - `design.md` §8「风险与延期项」
  - 主要改哪里：
    - `specs/002.1-家庭问答提醒与场景编排/docs/20260310-家庭服务中心与AI网关-前后端联调说明-v0.1.md`
    - `specs/002.1-家庭问答提醒与场景编排/docs/20260310-家庭服务中心-代表场景验收记录-v0.1.md`
  - 这一步先不做什么：不再扩范围，只写清现状和边界。
  - 怎么算完成：
    1. 联调路径写清楚，别人照着能跑
    2. 三个代表场景和一条 AI 回退路径有验收记录
    3. 已知风险和延期项写清楚
  - 怎么验证：
    - 文档走查
    - 按文档回放三条代表链路和一条 AI 回退链路
  - 对应需求：`requirements.md` 需求 5、6、7、8、9、10
  - 对应设计：`design.md` §7.2、§7.3、§7.4、§8.1、§8.2

### 最终检查

- [x] 3.5 最终检查点
  - 状态：DONE
  - 这一步到底做什么：确认这个 Spec 该有的都已经闭环，不再假装“差一点点”。
  - 做完你能看到什么：需求、设计、任务、代码、页面、联调文档、验收记录和风险说明是一条完整链路。
  - 先依赖什么：3.4
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
    - `docs/`
  - 主要改哪里：当前 Spec 全部文件
  - 这一步先不做什么：不临时加新需求。
  - 怎么算完成：
    1. 需求、设计、任务能一一对应
    2. 问答、提醒、场景、AI 抽象层边界清楚
    3. 已知风险和延期项都已经记清楚
  - 怎么验证：
    - 按 Spec 清单逐项走查
    - 回放代表链路，核对文档和实现是否一致
  - 对应需求：`requirements.md` 全部需求
  - 对应设计：`design.md` 全文

---

## 补充任务：为完整测试补可操作页面

- [x] 3.6 补一个 AI 模型供应商配置页面，方便手工联调和完整测试
  - 状态：DONE
  - 这一步到底做什么：在 `admin-web` 里补一个独立页面，让人可以手动新增/编辑 AI 供应商、配置能力路由，并做一次预览调用。
  - 做完你能看到什么：管理台里有一个单独的 AI 配置页面，不用再靠接口工具手敲 JSON。
  - 先依赖什么：3.5
  - 开始前先看：
    - `apps/api-server/app/api/v1/endpoints/ai_admin.py`
    - `apps/admin-web/src/lib/api.ts`
    - `apps/admin-web/src/types.ts`
    - `apps/admin-web/src/App.tsx`
  - 主要改哪里：
    - `apps/admin-web/src/pages/`
    - `apps/admin-web/src/lib/api.ts`
    - `apps/admin-web/src/types.ts`
    - `apps/admin-web/src/App.tsx`
  - 这一步先不做什么：先不做复杂权限系统，不做完整多租户治理台，只做当前测试所需的最小可用页面。
  - 怎么算完成：
    1. 可新增并编辑 AI 供应商
    2. 可为当前家庭或全局配置 capability 路由
    3. 可在页面里发起一次 AI 预览调用，检查主备和降级结果
  - 怎么验证：
    - `cd apps/admin-web && npm.cmd run build`
    - 在页面中手动新增 provider、配置 route、发起 preview 调用
  - 对应需求：`requirements.md` 需求 7、需求 9、需求 10
  - 对应设计：`design.md` §3.0、§3.7、§4.0、§5.0、§6.0

- [x] 3.7 让兼容式模型供应商发起真实对话，而不是只返回模拟结果
  - 状态：DONE
  - 这一步到底做什么：把 `openai_compatible` / `local_gateway` 这两类供应商从“假返回”改成真实 HTTP 调用，同时保留现有主备切换和模板降级。
  - 做完你能看到什么：在 AI 配置页发起预览调用时，真的会打到你配置的模型服务，而不是只拼一段假文本。
  - 先依赖什么：3.6
  - 开始前先看：
    - `apps/api-server/app/modules/ai_gateway/provider_runtime.py`
    - `apps/api-server/app/modules/ai_gateway/gateway_service.py`
    - `apps/api-server/app/core/config.py`
    - `apps/admin-web/src/pages/AiProviderConfigPage.tsx`
  - 主要改哪里：
    - `apps/api-server/app/modules/ai_gateway/provider_runtime.py`
    - `apps/api-server/app/modules/ai_gateway/gateway_service.py`
    - `apps/api-server/app/core/config.py`
    - `apps/admin-web/src/pages/AiProviderConfigPage.tsx`
  - 这一步先不做什么：先不接各家原生 SDK，先把兼容式 HTTP 协议打通。
  - 怎么算完成：
    1. `openai_compatible` / `local_gateway` 能发起真实 HTTP 请求
    2. 可从 `secret_ref` 或运行时配置解析密钥
    3. 失败时仍然能切备供应商或走模板降级
  - 怎么验证：
    - `cd apps/api-server && python -m compileall app`
    - 在 AI 配置页配置真实 provider 后，发起 preview 调用并观察真实返回
  - 对应需求：`requirements.md` 需求 9、需求 10
  - 对应设计：`design.md` §3.0、§4.0、§5.0、§6.0
