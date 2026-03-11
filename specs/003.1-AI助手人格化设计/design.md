# 设计文档 - AI多Agent与管家角色设计

状态：Draft

## 1. 设计目标

这次不是给“管家”补几个字段，而是把单助手结构升级成**多 Agent 基座**。

目标有六个：

1. 建立统一的多 Agent 数据模型
2. 让 `管家` 成为默认主 Agent，而不是唯一角色
3. 让每个 Agent 都有独立的 `soul`、成员认知、记忆视角和外观
4. 长期记忆继续复用 `Spec 003`，不制造第二套真相
5. 前端保留 `AI配置` 作为统一设置入口
6. 前端把原“助手页面”改成 `对话`

## 2. 现状与约束

### 2.1 当前已经有什么

- `member` 模块已经定义真实家庭成员
- `relationship` 模块已经定义真实成员之间的关系
- `Spec 003` 已完成家庭记忆中心核心落地，包括 `event_records`、`memory_cards`、`hot_summary`、权限过滤和修订链路
- `user-web` 已有设置页、记忆页和原助手相关页面骨架
- `ai_gateway` 已是统一 AI 供应商入口

### 2.2 当前真正缺什么

- 缺多 Agent 基础模型
- 缺每个 Agent 的显式 `soul` 和成员认知承载
- 缺 Agent 级外观系统
- 缺 AI配置作为统一多 Agent 管理入口
- 缺“对话页”和 Agent 体系的清晰分工

### 2.3 约束

1. 不破坏现有 `members` 和 `member_relationships` 默认语义
2. 任何 Agent 都不出现在家庭成员列表，也不出现在家庭图谱
3. 不新建第二套长期记忆系统
4. 外观生成必须走 `ai_gateway`
5. 第一版默认一个主管家，可扩多个专业 Agent

## 3. 核心设计原则

### 3.1 先做 Agent 基座，再谈具体角色

如果先把“管家”写死成唯一模型，后面营养师、健身教练一进来，代码一定开始复制粘贴。

所以第一原则是：

- 先抽象 `Agent`
- 再把 `管家` 作为默认主 Agent 角色实例化

### 3.2 Agent 是系统角色，不是家庭成员

这条必须写死。

如果把 Agent 塞进 `members`：

- 成员列表会被污染
- 家庭图谱语义会变脏
- 生日、监护、电话这些字段都会变成笑话

所以：

- `members` 继续只表达真人
- `member_relationships` 继续只表达真人关系
- Agent 只存在于 AI 体系里

### 3.3 AI配置和对话必须分离

这也是关键。

- `AI配置` 解决的是：系统里有哪些 Agent、它们怎么配置
- `对话` 解决的是：用户现在正在和谁交互、如何交互

把这两个东西混成一个页面，最后一定烂。

### 3.4 Soul、成员认知、记忆、外观分开建模

这四块不是一回事：

- `soul`：它是谁
- 成员认知：它怎么看待家里每个人
- 长期记忆：它能从家庭事实中持续记住什么
- 外观：它被看起来是什么样子

拆开以后才能扩多 Agent，不然所有角色共用一坨配置。

### 3.5 复用记忆中心，不做第二套真相

所有 Agent 的长期记忆都必须直接接 `Spec 003`。

不能做这些蠢事：

- 新建 `butler_memories`
- 新建 `nutritionist_memories`
- 复制一份家庭事实到 Agent 模块

Agent 只是使用家庭记忆中心，不拥有独立真相。

## 4. 数据模型

### 4.1 新增表

#### 4.1.1 `family_agents`

用途：定义家庭中的 Agent 基础身份。

建议字段：

| 字段 | 说明 |
| --- | --- |
| `id` | 主键 |
| `household_id` | 所属家庭 |
| `code` | 稳定代码，如 `butler_primary`、`nutritionist_default` |
| `agent_type` | 角色类型，如 `butler`、`nutritionist`、`fitness_coach` |
| `display_name` | 展示名称 |
| `status` | `active / inactive / draft` |
| `is_primary` | 是否主 Agent，第一版默认主管家为 `true` |
| `sort_order` | 配置页排序 |
| `created_at / updated_at` | 审计字段 |

#### 4.1.2 `family_agent_soul_profiles`

用途：保存某个 Agent 当前生效的 `soul` 和版本快照。

建议字段：

| 字段 | 说明 |
| --- | --- |
| `id` | 主键 |
| `agent_id` | 关联 `family_agents.id` |
| `version` | 版本号 |
| `self_identity` | 自我认知 |
| `role_summary` | 角色定位 |
| `intro_message` | 自我介绍 |
| `speaking_style` | 说话风格 |
| `personality_traits` | 性格特征，JSON 数组 |
| `service_focus` | 服务重点，JSON 数组 |
| `service_boundaries` | 边界规则，JSON |
| `is_active` | 当前是否生效 |
| `created_by / created_at` | 审计字段 |

#### 4.1.3 `family_agent_member_cognitions`

用途：保存某个 Agent 对每个家庭成员的内部认知。

建议字段：

| 字段 | 说明 |
| --- | --- |
| `id` | 主键 |
| `agent_id` | 关联 `family_agents.id` |
| `member_id` | 关联 `members.id` |
| `display_address` | 对该成员的称呼 |
| `closeness_level` | 亲近度 1-5 |
| `service_priority` | 服务优先级 1-5 |
| `communication_style` | 沟通风格提示 |
| `care_notes_json` | 注意事项 |
| `prompt_notes` | 运行时补充说明 |
| `version / updated_at` | 审计字段 |

#### 4.1.4 `family_agent_appearance_profiles`

用途：保存某个 Agent 的视觉设定和当前生效外观。

建议字段：

| 字段 | 说明 |
| --- | --- |
| `id` | 主键 |
| `agent_id` | 关联 `family_agents.id` |
| `style_brief` | 外观风格描述 |
| `appearance_prompt` | 生成提示词 |
| `negative_prompt` | 负向提示 |
| `palette` | 颜色偏好 |
| `reference_assets_json` | 参考素材 |
| `selected_asset_id` | 当前生效素材 |
| `status` | `draft / generating / ready / failed / published` |
| `updated_at` | 更新时间 |

#### 4.1.5 `family_agent_appearance_assets`

用途：保存某个 Agent 的外观生成结果和人工选择结果。

建议字段：

| 字段 | 说明 |
| --- | --- |
| `id` | 主键 |
| `agent_id` | 关联 `family_agents.id` |
| `provider_profile_id` | 使用的多模态供应商配置 |
| `generation_request_json` | 生成参数快照 |
| `asset_url` | 结果地址或对象键 |
| `thumbnail_url` | 缩略图 |
| `status` | `pending / ready / failed / rejected / selected` |
| `safety_review_status` | `pending / approved / rejected` |
| `error_message` | 失败原因 |
| `created_at` | 生成时间 |

#### 4.1.6 `family_agent_runtime_policies`

用途：保存某个 Agent 的运行时策略，避免把所有逻辑塞进对话页。

建议字段：

| 字段 | 说明 |
| --- | --- |
| `agent_id` | 关联 `family_agents.id` |
| `conversation_enabled` | 是否可在对话页直接唤起 |
| `default_entry` | 是否默认入口候选 |
| `routing_tags_json` | 路由标签，如饮食、运动、家庭综合 |
| `memory_scope_json` | 该 Agent 的记忆偏好与过滤范围 |
| `updated_at` | 更新时间 |

### 4.2 明确复用的现有模型

所有 Agent 的长期记忆继续复用：

- `event_records`
- `memory_cards`
- `memory_card_members`
- `memory_card_revisions`
- `hot_summary`
- 记忆查询、权限过滤、纠错、删除、回放

### 4.3 Agent 相关记忆如何落在现有记忆中心里

第一版不要改记忆中心主表结构。

优先做法：

- 在 `event_records.payload_json` 中写入 `agent_id`、`agent_type`、`persona_scope`、`related_member_ids`
- 在 `memory_cards.content_json` 中写入 `agent_id`、`agent_type`、`persona_scope`、`persona_tags`
- 继续使用现有 `subject_member_id`、`related_members`、`visibility` 做权限裁剪

这样所有 Agent 共享一套长期记忆基座，但运行时能按 `agent_id` 和作用域读出不同视角。

### 4.4 为什么不单独给每个 Agent 建记忆表

因为那会制造垃圾结构：

- 家庭事实变成多份
- 纠错和失效要跑多条链路
- 对话和服务到底读谁会越来越乱

这不是抽象问题，是一定会把系统拖死的真实问题。

## 5. 读写链路设计

### 5.1 AI配置读模型

新增 `agent_config_service`，负责聚合：

- `family_agents`
- 当前生效的 `family_agent_soul_profiles`
- `family_agent_member_cognitions`
- 当前生效的 `family_agent_appearance_profiles`
- `family_agent_runtime_policies`

返回结果建议统一成：

- `agents[]`
  - `id`
  - `agent_type`
  - `display_name`
  - `status`
  - `is_primary`
  - `summary`
  - `conversation_enabled`

这份读模型专门给 `AI配置` 页面和管理配置页用。

### 5.2 单个 Agent 资料读模型

新增 `agent_profile_service`，返回：

- `agent`
- `soul`
- `member_cognitions[]`
- `appearance`
- `runtime_policy`

这份读模型给 AI配置里的详情页和编辑页用。

### 5.3 Soul 配置链路

写入流程：

1. 管理员选择某个 Agent
2. 提交该 Agent 的人格配置
3. 服务层校验必填项和边界字段
4. 生成新版本 `family_agent_soul_profiles`
5. 将旧版本设为非激活，新版本设为激活
6. 刷新运行时缓存

### 5.4 成员认知链路

写入流程：

1. 管理员选择某个 Agent
2. 为某个家庭成员配置称呼、服务优先级、沟通风格和注意事项
3. 服务层检查该成员是否属于当前家庭
4. 写入或更新 `family_agent_member_cognitions`
5. 记录版本和更新时间

注意：

- 这是 Agent 内部认知，不是家庭图谱数据
- 不往 `member_relationships` 里硬塞

### 5.5 长期记忆复用链路

任意 Agent 读取长期记忆时，不单独查新表，而是直接调 `memory.context_engine`。

运行时顺序建议如下：

1. 先读当前 Agent 的 `soul`
2. 再读该 Agent 的成员认知
3. 调用 `get_memory_hot_summary` 和 `query_memory_cards`
4. 根据 `agent_id`、`agent_type` 与 `persona_scope` 过滤长期线索
5. 组合成该 Agent 的最终运行时上下文

关键点：

- 家庭事实仍以家庭记忆中心为准
- 每个 Agent 只是用不同视角读取同一套记忆基座
- 记忆被纠错或删除后，相关 Agent 下次查询自然反映新结果

### 5.6 对话页链路

“对话页”不承担配置职责，只承担交互职责。

建议流程：

1. 用户进入 `对话`
2. 默认激活主管家 Agent
3. 用户可显式切换到营养师、健身教练等已启用 Agent
4. 系统按当前 Agent 组装运行时上下文
5. 调用 `ai_gateway` 完成响应

第一版先支持：

- 默认主管家
- 手动切换 Agent

自动路由可以后续再加，但别第一版就把自己绕死。

### 5.7 外观生成链路

外观生成必须和主对话链路解耦，独立异步执行。

建议流程：

1. 管理员在 AI配置里选择某个 Agent
2. 提交外观描述、风格偏好、禁用元素、参考图
3. 服务层生成标准化 prompt
4. 调用 `ai_gateway` 的多模态供应商路由
5. 生成多个候选素材并写入 `family_agent_appearance_assets`
6. 管理员人工选中一个素材发布
7. AI配置页、对话页和相关卡片读取 `selected_asset_id`

## 6. API 设计

### 6.1 新增接口建议

- `GET /api/v1/ai-config/{household_id}`
  - 返回多个 Agent 的配置摘要
- `GET /api/v1/ai-config/{household_id}/agents/{agent_id}`
  - 返回单个 Agent 的完整配置
- `POST /api/v1/ai-config/{household_id}/agents`
  - 新增一个 Agent
- `PUT /api/v1/ai-config/{household_id}/agents/{agent_id}/soul`
  - 更新某个 Agent 的人格
- `PUT /api/v1/ai-config/{household_id}/agents/{agent_id}/member-cognitions`
  - 更新某个 Agent 的成员认知
- `PUT /api/v1/ai-config/{household_id}/agents/{agent_id}/runtime-policy`
  - 更新某个 Agent 的运行时策略
- `POST /api/v1/ai-config/{household_id}/agents/{agent_id}/appearance/generate`
  - 发起某个 Agent 的外观生成任务
- `POST /api/v1/ai-config/{household_id}/agents/{agent_id}/appearance/select`
  - 选择并发布某个 Agent 的外观素材
- `POST /api/v1/conversations/route`
  - 以当前 Agent 上下文发起对话

### 6.2 现有接口兼容策略

- `GET /members`：保持不变，继续只返回真人成员
- `GET /member-relationships`：保持不变，继续只返回真人关系
- 家庭图谱接口：保持不变，不加入任何 Agent 节点
- `GET /memories/*`：继续复用现有接口；Agent 相关筛选通过新增参数或 `content_json` 解释实现
- `family_qa`：内部增加 Agent 运行时上下文组装，但外部调用语义不变

## 7. 前端设计

### 7.1 用户端

#### 家庭页

- 成员列表继续只展示真人
- 家庭图谱继续只展示真人关系
- 不在家庭页显式加入任何 Agent 节点

#### AI配置页

- 设置中的 AI 相关入口继续叫 `AI配置`
- 页面展示多个 Agent 卡片或列表
- 支持查看每个 Agent 的人格摘要、状态、外观和角色类型
- 支持进入单个 Agent 的详细配置页

#### 对话页

- 原“助手页面”直接改成“对话”
- 对话页默认使用主管家 Agent
- 对话页支持切换到其他已启用 Agent
- 对话页展示当前 Agent 的名称、外观和角色摘要

#### 记忆页

- 继续使用统一记忆页
- 可增加“与某个 Agent 相关”的解释视图或标签，不额外做第二个记忆页面

### 7.2 管理台

- 增加 AI 多 Agent 配置入口
- 增加 Agent 列表、新增、启停和排序能力
- 增加单个 Agent 的人格、成员认知和外观配置
- 继续复用记忆中心页面查看 Agent 相关长期记忆

## 8. 运行时上下文组装

### 8.1 组装顺序

严格固定顺序：

1. 当前 Agent 的 `soul`
2. 当前 Agent 的成员认知
3. 当前 Agent 的长期记忆视角
4. 实时家庭上下文

### 8.2 推荐上下文片段

- `agent_identity`
- `agent_boundaries`
- `member_cognition_notes`
- `memory_bundle`
- `live_household_context`

### 8.3 降级策略

- 某个 Agent 的 `soul` 读不到：回退到该角色默认模板
- 某个 Agent 的成员认知缺失：回退到通用称呼和基础服务策略
- 记忆中心不可用：回退到实时上下文与普通问答
- 外观服务异常：只影响展示，不影响对应 Agent 可用性
- 某个专业 Agent 不可用：回退到主管家 Agent 兜底

## 9. 风险与权衡

### 9.1 最大风险

#### 风险 1：先做单管家，再补多 Agent

后果：后面全是复制粘贴和兼容补丁。

结论：不干。

#### 风险 2：把 Agent 塞进 `members`

后果：成员系统被污染。

结论：不干。

#### 风险 3：给每个 Agent 单开记忆系统

后果：双份甚至多份真相，最终没人知道该信谁。

结论：不干。

#### 风险 4：把 AI配置和对话混成一个页面

后果：配置流程和交互流程互相污染，体验和代码都会烂。

结论：分开。

### 9.2 第一版刻意不做的复杂度

- 不做自动无限扩张 Agent
- 不做复杂自动路由编排
- 不做图谱人格化展示
- 不做实时动态虚拟形象
- 不做复杂向量化“每个 Agent 一套人格记忆仓库”

## 10. 实施顺序建议

1. 先落多 Agent 数据模型：`family_agents`、`soul`、成员认知、外观、运行时策略
2. 再做 AI配置读模型和单 Agent 资料读模型
3. 再接 Agent 运行时上下文和对话页
4. 再接外观生成链路
5. 最后补治理、联调和验收文档
