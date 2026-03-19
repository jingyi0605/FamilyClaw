# 任务文档 - AI助手设置生效与对话配置回写统一

状态：Draft

## 这份文档是干什么的

这份任务文档不是拿来凑流程的，是拿来确保我们不会再做出“字段加上去了，结果谁都不用”的烂活。

这次要解决的是 4 件实打实的事：

- 设置页里的字段到底哪些是真字段
- 默认助手和可对话状态到底由谁说了算
- 对话里的配置修改到底能改哪些资料
- 改完以后前端到底怎么读到最新值

## 状态说明

- `TODO`：还没开始
- `IN_PROGRESS`：正在做
- `BLOCKED`：被外部问题卡住
- `IN_REVIEW`：已经有结果，等复核
- `DONE`：已经完成，并且已回写状态
- `CANCELLED`：取消，不做了，但必须写原因

## 阶段 1：先把字段收口，别再让假配置混进来

- [ ] 1.1 建立 Agent 设置字段真值矩阵
  - 状态：TODO
  - 这一步到底做什么：把 AI 助手设置页当前所有字段逐个登记清楚，明确“存哪、谁用、对话能不能改、测什么”，并据此决定保留、降级还是下线。
  - 做完后你能看到什么结果：我们能直接回答每个字段是不是假字段，不再靠代码全仓库盲搜。
  - 这一步依赖什么：无
  - 开始前先看：
    - `requirements.md` 需求 1、需求 3、需求 4
    - `design.md` 2.1、3.1、3.2
  - 主要改哪些文件：
    - `apps/user-app/src/pages/settings/components/AgentDetailDialog.tsx`
    - `apps/user-app/src/pages/settings/settingsTypes.ts`
    - `apps/api-server/app/modules/agent/schemas.py`
    - `apps/api-server/app/modules/agent/service.py`
    - 当前 Spec 文档
  - 这一步明确不做什么：先不处理会话默认 Agent 和动作策略语义，只收口字段契约。
  - 怎么算完成：
    1. 设置页保留字段清单明确下来。
    2. 需要下线的字段清单明确下来。
    3. 派生字段和用户可编辑字段不再混为一谈。
  - 怎么验证：
    - 人工对照字段矩阵检查设置页代码和后端 schema
  - 对应需求：`requirements.md` 需求 1、需求 3、需求 4
  - 对应设计：`design.md` 3.1、3.2、6.1、6.2

- [ ] 1.2 把假字段从用户表单里下掉，或降成派生字段
  - 状态：TODO
  - 这一步到底做什么：按 1.1 的结论，移除当前没有稳定消费者的表单项，并把 `self_identity` 这类内部字段收口成派生字段或高级字段。
  - 做完后你能看到什么结果：用户在设置页里看到的字段只剩下真正能生效的项目。
  - 这一步依赖什么：1.1
  - 开始前先看：
    - `requirements.md` 需求 1、需求 4
    - `design.md` 3.1.3、3.2
  - 主要改哪些文件：
    - `apps/user-app/src/pages/settings/components/AgentDetailDialog.tsx`
    - `apps/user-app/src/runtime/h5-shell/i18n/pageMessages.zh-CN.ts`
    - `apps/user-app/src/runtime/h5-shell/i18n/pageMessages.en-US.ts`
  - 这一步明确不做什么：先不改对话提案和后端运行策略。
  - 怎么算完成：
    1. `routing_tags` 不再以普通用户字段存在，除非本期接上明确消费者。
    2. `closeness_level`、`service_priority` 不再继续作为普通用户可编辑项出现，除非本期接上明确消费者。
    3. 助手资料页不再同时出现语义重复的字段。
  - 怎么验证：
    - 人工打开设置页检查字段展示
    - 前端构建通过
  - 对应需求：`requirements.md` 需求 1、需求 4
  - 对应设计：`design.md` 3.1.3、3.2.1、3.2.2、3.2.3

### 阶段检查

- [ ] 1.3 阶段检查：设置页不再展示假配置
  - 状态：TODO
  - 这一步到底做什么：确认阶段 1 结束后，页面上剩下的字段都已经有明确定义。
  - 做完后你能看到什么结果：后续实现不会再围着“这个字段到底要不要留”反复打补丁。
  - 这一步依赖什么：1.1、1.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪些文件：当前 Spec 文档
  - 这一步明确不做什么：不扩范围，不新增业务字段。
  - 怎么算完成：
    1. 保留字段、派生字段、下线字段三张清单都明确。
    2. 代码实现和 Spec 描述一致。
  - 怎么验证：
    - 人工走查
  - 对应需求：`requirements.md` 需求 1、需求 4
  - 对应设计：`design.md` 3.1、3.2、6.2

---

## 阶段 2：统一运行策略和默认 Agent 规则

- [ ] 2.1 统一“可对话 Agent”判定和默认 Agent 解析
  - 状态：TODO
  - 这一步到底做什么：把前端列表过滤、默认 Agent 选择、后端会话创建、会话切换统一到同一套判定规则上。
  - 做完后你能看到什么结果：`conversation_enabled` 和 `default_entry` 不再是“前端认、后端不认”的半截配置。
  - 这一步依赖什么：1.3
  - 开始前先看：
    - `requirements.md` 需求 2
    - `design.md` 2.3.2、4.1、4.2
  - 主要改哪些文件：
    - `apps/user-app/src/pages/assistant/assistant.agents.ts`
    - `apps/user-app/src/pages/assistant/index.h5.tsx`
    - `apps/api-server/app/modules/agent/service.py`
    - `apps/api-server/app/modules/conversation/service.py`
  - 这一步明确不做什么：先不处理 ask/notify/auto 的差异语义。
  - 怎么算完成：
    1. 不可对话 Agent 不能被后端会话激活。
    2. 默认助手解析顺序在前后端一致。
    3. 没有合法可对话 Agent 时，系统返回明确错误，不偷偷选错 Agent。
  - 怎么验证：
    - 后端单元测试
    - 人工测试设置默认助手和关闭对话权限
  - 对应需求：`requirements.md` 需求 2
  - 对应设计：`design.md` 2.3.2、4.1、4.2、6.3

- [ ] 2.2 把 `ask / notify / auto` 的语义真正拆开
  - 状态：TODO
  - 这一步到底做什么：统一动作记录和提案执行里三种策略值的行为，不再让 `notify` 和 `auto` 走完全一样的分支。
  - 做完后你能看到什么结果：运行策略终于不是摆设，用户改哪个值，系统就表现成哪个值。
  - 这一步依赖什么：2.1
  - 开始前先看：
    - `requirements.md` 需求 2、需求 6
    - `design.md` 4.3、5、6.1
  - 主要改哪些文件：
    - `apps/api-server/app/modules/conversation/service.py`
    - `apps/api-server/app/modules/conversation/proposal_pipeline.py`
    - `apps/user-app/src/pages/assistant/index.h5.tsx`
    - `apps/user-app/src/runtime/h5-shell/i18n/pageMessages.zh-CN.ts`
  - 这一步明确不做什么：先不扩展对话回写字段范围。
  - 怎么算完成：
    1. `ask` 仍然等待确认。
    2. `notify` 立即执行且有明确结果提示。
    3. `auto` 立即执行但不再冒充“通知模式”。
  - 怎么验证：
    - 后端单元测试
    - 前后端联调动作记录展示
  - 对应需求：`requirements.md` 需求 2、需求 6
  - 对应设计：`design.md` 4.3、5.2、7

### 阶段检查

- [ ] 2.3 阶段检查：运行策略终于真的影响对话
  - 状态：TODO
  - 这一步到底做什么：确认阶段 2 完成后，运行策略不再是只写数据库的装饰品。
  - 做完后你能看到什么结果：默认助手、可对话状态、动作策略三件事已经形成统一闭环。
  - 这一步依赖什么：2.1、2.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪些文件：当前 Spec 文档
  - 这一步明确不做什么：不扩展新的动作种类。
  - 怎么算完成：
    1. 三个关键运行策略都能被自动化测试覆盖。
    2. 人工能复现“设置变更 -> 对话行为变化”。
  - 怎么验证：
    - 人工走查
    - 测试结果复核
  - 对应需求：`requirements.md` 需求 2、需求 6
  - 对应设计：`design.md` 4.1、4.2、4.3、7

---

## 阶段 3：统一对话回写和设置页回填

- [ ] 3.1 扩展对话配置回写白名单，覆盖真实资料字段
  - 状态：TODO
  - 这一步到底做什么：把对话里允许修改的 Agent 资料字段扩到本期保留的真实资料字段，并强制统一走 Agent 更新服务。
  - 做完后你能看到什么结果：用户在对话里改名字、简介、角色设定，不再出现“说是改了，设置页却没变”的情况。
  - 这一步依赖什么：2.3
  - 开始前先看：
    - `requirements.md` 需求 3、需求 5
    - `design.md` 2.3.3、3.1.2、3.3.3、6.1
  - 主要改哪些文件：
    - `apps/api-server/app/modules/conversation/proposal_analyzers.py`
    - `apps/api-server/app/modules/conversation/service.py`
    - `apps/api-server/app/modules/realtime/schemas.py`
    - `apps/api-server/app/modules/agent/service.py`
  - 这一步明确不做什么：不把所有内部字段都开放给对话改，只处理本期定义的真实资料字段。
  - 怎么算完成：
    1. 对话提案支持本期定义的资料字段白名单。
    2. 对话执行回写和设置页保存复用同一条更新链路。
    3. 越权字段不会被旁路写入。
  - 怎么验证：
    - 后端集成测试
    - 人工测试对话改名、改简介、改角色设定
  - 对应需求：`requirements.md` 需求 3、需求 5、需求 6
  - 对应设计：`design.md` 2.3.3、3.1.2、3.3.3、6.1

- [ ] 3.2 让设置页和对话页在配置变更后刷新同一份数据
  - 状态：TODO
  - 这一步到底做什么：实现最小可用的前端失效缓存和刷新机制，让对话回写成功后，Agent 列表和详情表单都能重新拉最新数据。
  - 做完后你能看到什么结果：对话里改完资料，设置页重新打开或保持打开时，都能看到新值。
  - 这一步依赖什么：3.1
  - 开始前先看：
    - `requirements.md` 需求 5
    - `design.md` 3.3.4
  - 主要改哪些文件：
    - `apps/user-app/src/pages/settings/components/AgentConfigPanel.tsx`
    - `apps/user-app/src/pages/settings/components/AgentDetailDialog.tsx`
    - `apps/user-app/src/pages/assistant/index.h5.tsx`
    - `apps/user-app/src/runtime/`
  - 这一步明确不做什么：不做复杂的实时协同系统，只做当前浏览器会话下可用的刷新机制。
  - 怎么算完成：
    1. 设置页保存成功会刷新详情。
    2. 对话配置回写成功会触发 Agent 列表和详情失效。
    3. 重新打开 Agent 详情时一定读到最新值。
  - 怎么验证：
    - 前端联调
    - 人工同时走设置页和对话页
  - 对应需求：`requirements.md` 需求 5
  - 对应设计：`design.md` 3.3.3、3.3.4

- [ ] 3.3 让成员互动设置只保留真正会影响 Prompt 的字段
  - 状态：TODO
  - 这一步到底做什么：把成员互动设置中保留的字段接到 Prompt 组装，并确认被下线的字段不再继续出现在用户表单里。
  - 做完后你能看到什么结果：用户填写“怎么称呼 Ta”“沟通方式”“补充备注”后，助手回复风格和称呼能真的变。
  - 这一步依赖什么：3.2
  - 开始前先看：
    - `requirements.md` 需求 4
    - `design.md` 2.3.4、3.2.3
  - 主要改哪些文件：
    - `apps/api-server/app/modules/agent/service.py`
    - `apps/api-server/app/modules/ai_gateway/provider_runtime.py`
    - `apps/user-app/src/pages/settings/components/AgentDetailDialog.tsx`
  - 这一步明确不做什么：不再硬给 `closeness_level`、`service_priority` 编造新业务意义。
  - 怎么算完成：
    1. 保留字段会进入 Prompt。
    2. 下线字段不再对用户可见。
    3. 旧数据仍可兼容读取，不影响已有家庭。
  - 怎么验证：
    - 后端集成测试
    - 人工检查 Prompt 组装结果或相关调试日志
  - 对应需求：`requirements.md` 需求 4、需求 6
  - 对应设计：`design.md` 2.3.4、3.2.3、5

### 最终检查

- [ ] 3.4 最终检查：AI 助手设置不再是两套逻辑
  - 状态：TODO
  - 这一步到底做什么：确认整个 Spec 做完以后，设置页展示、对话行为、对话回写、表单回填都收口到一套真值源。
  - 做完后你能看到什么结果：以后再问“这个设置到底生没生效”，可以直接看代码、看测试、看日志，不用猜。
  - 这一步依赖什么：3.1、3.2、3.3
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪些文件：
    - 当前 Spec 全部文档
    - 相关测试文件
  - 这一步明确不做什么：不新增本 Spec 之外的功能。
  - 怎么算完成：
    1. 设置页保留字段全部是真字段。
    2. 运行策略前后端统一。
    3. 对话改资料能回写，设置页能回填。
    4. 自动化测试覆盖关键链路。
  - 怎么验证：
    - 按验收标准逐项复核
    - 运行相关单元测试、集成测试和前端构建
  - 对应需求：`requirements.md` 全部需求
  - 对应设计：`design.md` 全文
