# 任务清单 - 插件能力统一接入与版本治理（人话版）

状态：Draft

## 这份文档是干什么的

这份任务清单不是拿来摆样子的，而是用来防止这次改造做成“四处补洞”。

这次必须按顺序来：

- 先把能力模型和边界讲清楚
- 再改后端统一出口
- 再改前端入口消费
- 最后补文档和版本治理

否则只会再长出一层新补丁。

## 状态说明

- `TODO`：还没开始
- `IN_PROGRESS`：正在做
- `BLOCKED`：被外部问题卡住
- `IN_REVIEW`：已经有结果，等复核
- `DONE`：已经完成，并且已经回写状态
- `CANCELLED`：取消，不做了，但要写原因

规则：

- 只有 `状态：DONE` 的任务才能勾选成 `[x]`
- 每做完一个任务，必须立刻更新这里

---

## 阶段 1：先把插件能力边界和数据结构立住

- [x] 1.1 盘清主题、AI 供应商和现有插件系统的真实边界
  - 状态：DONE
  - 这一步到底做什么：把主题、AI 供应商、现有插件能力、当前启停规则、当前版本字段分别在哪一层维护写清楚。
  - 做完你能看到什么：后面设计时不再把“像插件”和“真插件”混为一谈。
  - 先依赖什么：无
  - 开始前先看：
    - `requirements.md` 需求 1、需求 4
    - `design.md` §2.1「系统结构」
    - `design.md` §4.1「数据关系」
    - `../001.5-AI供应商管理插件化与模型摘要重构/`
    - `../004.2.2-插件禁用能力统一与停用收口/`
  - 主要改哪里：
    - `apps/api-server/app/modules/plugin/`
    - `apps/api-server/app/modules/ai_gateway/`
    - `packages/user-core/src/state/theme.ts`
    - `specs/004.5-插件能力统一接入与版本治理/`
  - 这一步先不做什么：先不改业务代码，只做结构盘点和边界确认。
  - 怎么算完成：
    1. 能说清主题和 AI 供应商当前为什么还不算通用插件
    2. 能说清当前版本机制到底已有多少真实能力
  - 怎么验证：
    - 人工走查代码和现有 Spec
  - 对应需求：`requirements.md` 需求 1、需求 4
  - 对应设计：`design.md` §2.1、§4.1
  - 本次产出：
    - `docs/20260317-阶段1现状盘点与统一模型草图.md`
    - `design.md` §1.4「当前代码真相（2026-03-17 盘点）」

- [x] 1.2 设计主题插件和 AI 供应商插件的统一数据模型
  - 状态：DONE
  - 这一步到底做什么：确定这两类能力进入通用插件系统后，manifest、registry item、能力字段、配置字段和兼容层该长什么样。
  - 做完你能看到什么：后端 schema 和前端类型有明确落点，不再靠猜。
  - 先依赖什么：1.1
  - 开始前先看：
    - `requirements.md` 需求 1、需求 3、需求 6
    - `design.md` §3.2「数据结构」
    - `design.md` §4.2「状态流转」
  - 主要改哪里：
    - `apps/api-server/app/modules/plugin/schemas.py`
    - `apps/api-server/app/modules/ai_gateway/`
    - `packages/user-core/src/domain/types.ts`
  - 这一步先不做什么：先不改页面和入口行为。
  - 怎么算完成：
    1. 主题和 AI 供应商都能映射到统一插件结果
    2. 兼容旧主题配置和旧 provider profile 的路径写清楚
  - 怎么验证：
    - schema 设计评审
    - 类型和接口草图走查
  - 对应需求：`requirements.md` 需求 1、需求 3、需求 6
  - 对应设计：`design.md` §3.2、§4.2
  - 本次产出：
    - `apps/api-server/app/modules/plugin/schemas.py`
    - `packages/user-core/src/domain/types.ts`
    - `apps/user-app/src/pages/settings/settingsTypes.ts`
    - `docs/20260317-阶段1现状盘点与统一模型草图.md`

### 阶段检查

- [x] 1.3 阶段 1 检查：确认不是又造一套平行模型
  - 状态：DONE
  - 这一步到底做什么：检查主题和 AI 供应商设计是不是已经真正回到通用插件系统，而不是换个名字再单独维护一层。
  - 做完你能看到什么：可以进入后端实现，不会越改越散。
  - 先依赖什么：1.1、1.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：本阶段全部相关文件
  - 这一步先不做什么：不扩新范围。
  - 怎么算完成：
    1. 统一状态源和统一数据模型已经说清楚
    2. 没有留下新的平行注册表设计
  - 怎么验证：
    - 人工走查
  - 对应需求：`requirements.md` 需求 1、需求 2
  - 对应设计：`design.md` §2.1、§3.2、§4.1
  - 本次确认结果：
    - 主题和 AI 供应商都没有新增独立注册表入口，统一由 `app.modules.plugin.service` 汇总输出
    - 家庭级启停继续复用 `plugin_state_overrides`，没有新增第二套状态表或第二套 enabled 语义

---

## 阶段 2：把后端统一出口和执行边界收口

- [x] 2.1 后端接入主题插件和 AI 供应商插件到统一注册出口
  - 状态：DONE
  - 这一步到底做什么：让主题和 AI 供应商能够从统一插件注册结果里被读到，并带上类型、版本、来源、启停状态。
  - 做完你能看到什么：后端不再需要一份插件列表、一份 provider adapter 列表、一份主题常量表各自当真相。
  - 先依赖什么：1.3
  - 开始前先看：
    - `requirements.md` 需求 1、需求 4
    - `design.md` §2.2「模块职责」
    - `design.md` §3.3「接口契约」
  - 主要改哪里：
    - `apps/api-server/app/modules/plugin/service.py`
    - `apps/api-server/app/modules/plugin/schemas.py`
    - `apps/api-server/app/modules/ai_gateway/provider_adapter_registry.py`
    - 主题相关后端或资源接口文件
  - 这一步先不做什么：先不改前端页面展示。
  - 怎么算完成：
    1. 统一插件列表能包含主题和 AI 供应商能力
    2. 统一结果里能带出版本和状态字段
  - 怎么验证：
    - 接口测试
    - 关键模块单元测试
  - 对应需求：`requirements.md` 需求 1、需求 4
  - 对应设计：`design.md` §2.2、§3.2、§3.3
  - 本次产出：
    - `apps/api-server/app/modules/plugin/service.py`
    - `apps/api-server/app/modules/plugin/theme_registry.py`
    - `apps/api-server/app/modules/ai_gateway/provider_adapter_registry.py`
    - `apps/api-server/app/modules/plugin/schemas.py`
    - `apps/api-server/tests/test_plugin_manifest.py`
  - 本次落地结果：
    - `list_registered_plugins(...)` 和 `list_registered_plugins_for_household(...)` 现在会把文件 manifest、主题兼容源、AI 供应商兼容源统一合并成一个 `PluginRegistrySnapshot`
    - 主题兼容源和 AI 供应商兼容源都走 `PluginManifest -> PluginRegistryItem` 同一套模型，不再额外维护平行插件列表接口
    - 统一注册结果现在会带上 `installed_version`、`compatibility`，并继续复用统一 `enabled` / `disabled_reason`
  - 本次验证结果：
    - 直接运行最小验证脚本，确认统一快照包含 `builtin.theme.chun-he-jing-ming` 和 `builtin.provider.chatgpt`
    - 直接运行最小验证脚本，确认 `plugin_state_overrides` 可以对 `builtin.provider.chatgpt` 生效
    - 备注：项目现有 `tests/test_plugin_manifest.py` 有历史编码问题，无法直接用 `unittest` 跑整文件，所以这一步先用独立脚本验证改动链路

- [x] 2.2 把新增入口和执行入口统一接到插件启停规则
  - 状态：DONE
  - 这一步到底做什么：把设备与集成、AI 供应商、计划任务、主题选择、worker 执行等入口统一接到同一套可用性校验。
  - 做完你能看到什么：禁用不再只是页面上的一个按钮，而是真正统一生效。
  - 先依赖什么：2.1
  - 开始前先看：
    - `requirements.md` 需求 2、需求 3、需求 6
    - `design.md` §2.3「关键流程」
    - `design.md` §5.3「处理策略」
    - `../../docs/开发设计规范/20260317-插件启用禁用统一规则.md`
  - 主要改哪里：
    - `apps/api-server/app/modules/integration/`
    - `apps/api-server/app/modules/scheduler/`
    - `apps/api-server/app/modules/plugin/`
    - `apps/api-server/app/modules/ai_gateway/`
    - 主题消费相关接口
  - 这一步先不做什么：先不优化页面文案和视觉表现。
  - 怎么算完成：
    1. 新增入口不会继续放出禁用插件
    2. 执行入口统一返回禁用错误语义
    3. 存量对象能看到禁用状态但不能继续执行
  - 怎么验证：
    - 集成测试
    - 人工接口回放
  - 对应需求：`requirements.md` 需求 2、需求 3、需求 6
  - 对应设计：`design.md` §2.3、§3.3、§5.3、§6.1
  - 本次推进结果：
    - AI 供应商新增入口新增了家庭级 `provider-adapters` 视图，只返回当前家庭仍可新增的 `ai-provider` 插件，不再把已禁用插件继续当可选项
    - AI 供应商档案创建、更新、能力路由绑定，已经在 household 场景统一接到 `require_available_household_plugin(...)` 这条禁用校验链路
    - AI 调用运行时现在会在 household 场景过滤掉已禁用的 AI 供应商插件；当没有可用主供应商且原因就是插件被禁用时，统一返回 `409` + `plugin_disabled`
    - AI 供应商档案读取结果现在会回填 `plugin_id`、`plugin_enabled`、`plugin_disabled_reason`，给后续前端阶段消费统一状态
    - 设备与集成目录现在不会再放出已禁用插件；新增实例走 `require_available_household_plugin(...)`，已有实例在插件停用后会表现为 `status="disabled"`，并把 `sync` 动作明确置灰
    - 设备与集成执行入口现在按动作区分边界：`configure` 继续允许查看/配置，`sync` 改为统一走可用性校验，插件停用时返回 `409/plugin_disabled`
    - 计划任务的新增/更新依赖校验不再把插件停用错误吞成 `400`；调度运行时如果插件在排队后被停用，也会把运行记录保留成 `plugin_disabled`，不再写成模糊的 `scheduled_task_dispatch_failed`
    - 通讯平台新增账号入口现在改走 `require_available_household_plugin(...)`；`probe` 在执行前显式校验插件可用性，停用时统一返回 `409/plugin_disabled`
    - 通讯平台存量账号更新继续保留查看/配置语义，不再因为插件停用把已有配置页和状态维护入口一起锁死
    - 计划任务草稿从自然语言解析插件目标时，已经不会再把 `enabled=false` 的插件当成可选目标
    - 主题统一改由 `ThemeProvider` 读取家庭插件注册表；当前家庭未启用的 `theme-pack` 不再继续出现在主题选择入口里，已选主题被停用时会自动 fallback 到可用主题
  - 本次验证结果：
    - 新增 `apps/api-server/tests/test_ai_provider_plugin_state.py`
    - 已用 `apps/api-server/.venv/Scripts/python.exe -m unittest tests.test_ai_provider_plugin_state` 跑通 4 个用例，覆盖 household provider adapter 过滤、禁用插件下创建 provider profile、禁用插件下绑定 capability route、禁用插件下调用返回 `409/plugin_disabled`
    - 新增 `apps/api-server/tests/test_integration_plugin_state.py`
    - 已用 `apps/api-server/.venv/Scripts/python.exe -m unittest tests.test_integration_plugin_state` 跑通 4 个用例，覆盖目录过滤、禁用插件下新增集成实例、存量实例禁用态展示、禁用插件下 `sync` 返回 `409/plugin_disabled`
    - 新增 `apps/api-server/tests/test_scheduler_plugin_state.py`
    - 已用 `apps/api-server/.venv/Scripts/python.exe -m unittest tests.test_scheduler_plugin_state` 跑通 3 个用例，覆盖禁用插件下创建计划任务、更新计划任务、运行记录保留 `plugin_disabled`
    - 已用 `apps/api-server/.venv/Scripts/python.exe -m py_compile ...` 验证本次新增和修改的 `integration` / `scheduler` 相关文件语法通过
    - 已用 `apps/api-server/.venv/Scripts/python.exe -m unittest tests.test_channel_accounts_api.ChannelAccountsApiTests.test_create_channel_account_rejects_disabled_channel_plugin tests.test_channel_accounts_api.ChannelAccountsApiTests.test_probe_channel_account_rejects_disabled_channel_plugin tests.test_channel_accounts_api.ChannelAccountsApiTests.test_update_channel_account_allows_configuring_disabled_channel_plugin tests.test_conversation_scheduled_task_proposals.ConversationScheduledTaskProposalTests.test_preview_does_not_match_disabled_plugin_target` 跑通 4 个定向用例，覆盖通讯平台新增入口、执行入口、存量配置入口和计划任务草稿插件过滤
    - 已用 `apps/api-server/.venv/Scripts/python.exe -m py_compile` 验证本次修改的 `channel` / `scheduler draft` 相关文件和定向测试文件语法通过
    - 已用 `cmd /c npm.cmd run typecheck` 跑通 `apps/user-app` 前端类型检查，确认主题状态改造没有破坏现有页面类型
    - 备注：`tests/test_scheduler_foundation.py` 仍有历史编码损坏，当前文件在导入阶段就会触发 `SyntaxError`，所以这次没法把旧回归入口一起跑通
  - 本次收口结论：
    - 2.2 需要覆盖的新增入口、执行入口和主题消费入口已经接上统一规则，可以进入 2.3 做后端散装逻辑复核

### 阶段检查

- [x] 2.3 阶段 2 检查：确认后端只有一套状态执法逻辑
  - 状态：DONE
  - 这一步到底做什么：检查后端是否还残留“这里看 enabled，那里自己拼条件”的散装逻辑。
  - 做完你能看到什么：执行边界清楚，后面前端只需要消费结果，不需要继续猜。
  - 先依赖什么：2.1、2.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：本阶段全部相关文件
  - 这一步先不做什么：不扩版本治理范围。
  - 怎么算完成：
    1. 关键执行入口都接到统一可用性校验
    2. 错误语义已经统一
  - 怎么验证：
    - 人工走查
    - 关键测试回归
  - 对应需求：`requirements.md` 需求 2、需求 3
  - 对应设计：`design.md` §3.3、§5.3、§6.1
  - 本次检查结果：
    - 已逐项复核 `ai_gateway`、`channel`、`integration`、`scheduler`、`device_control`、`plugin.agent_bridge`、`plugin.dashboard_service`、`region.plugin_runtime` 等核心链路
    - 执行类入口继续统一走 `require_available_household_plugin(...)`，查看/配置类场景继续允许走 `get_household_plugin(...)`
    - 新发现的散装历史逻辑只有首页插件卡片快照写入：此前还在 `plugin.dashboard_service.upsert_plugin_dashboard_card_snapshot(...)` 里手工判断 `plugin.enabled` 并返回旧错误码 `plugin_not_visible_in_household`
    - 该入口现已改为统一走 `require_available_household_plugin(...)`，禁用时回到 `409/plugin_disabled`
    - 复核后保留的直接 `plugin.enabled` 判断都属于目录过滤、状态展示、兼容降级或配置类读取，不再承担新的执行放行职责
  - 本次验证结果：
    - 已新增 `apps/api-server/tests/test_plugin_dashboard_plugin_state.py`
    - 已用 `apps/api-server/.venv/Scripts/python.exe -m unittest tests.test_plugin_dashboard_plugin_state` 跑通，确认禁用插件写入首页卡片快照时返回 `409/plugin_disabled`
    - 已用 `apps/api-server/.venv/Scripts/python.exe -m py_compile apps/api-server/app/modules/plugin/dashboard_service.py apps/api-server/tests/test_plugin_dashboard_plugin_state.py` 验证语法通过
    - 已再次搜索 `plugin_not_visible_in_household`，确认执行链路里的误用已经收掉，剩余出现点只保留给“当前家庭看不到插件”的兼容语义和旧错误翻译
  - 收口结论：
    - 2.3 需要确认的“后端只留一套执行态执法逻辑”已经收口完成，可以进入最终检查

---

## 阶段 3：把前端入口、版本治理和文档一起收完

- [x] 3.1 前端统一消费插件状态，并完成主题 / AI 供应商 / 集成入口适配
  - 状态：DONE
  - 这一步到底做什么：让前端不再自己猜插件状态，而是统一消费后端返回的状态字段和禁用原因。
  - 做完你能看到什么：主题页、AI 供应商页、设备与集成页、插件管理页的行为一致。
  - 先依赖什么：2.3
  - 开始前先看：
    - `requirements.md` 需求 2、需求 3
    - `design.md` §3.3「接口契约」
    - `design.md` §4.2「状态流转」
    - `../004.4-用户前端插件管理与插件市场/`
  - 主要改哪里：
    - `apps/user-app/src/pages/settings/integrations/`
    - `apps/user-app/src/pages/settings/ai/` 或相关 AI 配置页面
    - 主题选择页和主题状态管理
    - `apps/user-app/src/pages/settings/settingsTypes.ts`
  - 这一步先不做什么：先不改主题视觉设计本身。
  - 怎么算完成：
    1. 新增入口不会继续显示禁用插件为可选项
    2. 存量对象能明确显示禁用原因
    3. 页面按钮不再靠本地硬编码猜是否可点
  - 怎么验证：
    - 前端页面联调
    - 人工回放主要流程
  - 对应需求：`requirements.md` 需求 2、需求 3
  - 对应设计：`design.md` §3.3、§4.2、§6.1
  - 本次推进结果：
    - `ThemeProvider` 不再直接信任本地静态主题列表，而是会读取当前家庭的统一插件注册表，只暴露 `enabled=true` 的 `theme-pack`
    - 当用户本地之前选过的主题在当前家庭被停用时，前端会自动 fallback 到默认可用主题或首个可用主题，并把停用原因暴露给页面消费
    - 设置页的主题卡片和长辈模式开关现在统一消费 `useTheme()` 提供的可用性结果，不再自己硬编码“能不能点”
    - `app.ts` 已重排 provider 顺序，让主题状态可以直接读取 household 上下文，避免再额外造一层平行主题状态模型
    - 插件管理页的类型筛选器已补齐 9 种正式插件类型，新增 `theme-pack` 和 `ai-provider` 两类筛选项
    - 插件管理页的筛选逻辑已从“多选数组”收口为“单一类型或全部”，点击某个分类时只会切到该分类，不再叠加多个条件
  - 本次验证结果：
    - 已用 `cmd /c npm.cmd run typecheck` 跑通 `apps/user-app` 类型检查
  - 本轮补充结果：
    - AI 供应商页现在会消费 `plugin_enabled`、`plugin_disabled_reason`，存量模型配置能明确显示来源插件已停用的原因
    - AI 供应商编辑弹窗会优先复用统一插件注册表里的 `ai-provider` 能力，插件停用后旧配置仍可继续查看和维护
    - 设备与集成页的同步按钮现在直接消费后端 `allowed_actions` 和 `disabled_reason`，不再本地猜“能不能点”
    - 设备与集成页的实例状态徽标已经按真实状态着色，`disabled` 不再显示成绿色启用态
  - 收口结论：
    - 主题页、AI 供应商页、设备与集成页、插件管理页已经统一消费后端插件状态，3.1 可以收为 `DONE`

- [x] 3.2 盘点并补齐插件版本治理的最小可用能力
  - 状态：DONE
  - 这一步到底做什么：确认当前版本机制实际有哪些，补出统一展示、兼容性声明、升级提示需要的最小结构。
  - 做完你能看到什么：`version` 不再只是一个摆设字段，前后端和文档都知道它负责什么、不负责什么。
  - 先依赖什么：3.1
  - 开始前先看：
    - `requirements.md` 需求 4
    - `design.md` §3.2「数据结构」
    - `design.md` §6.3「版本字段不再只是展示」
  - 主要改哪里：
    - `apps/api-server/app/modules/plugin/`
    - `apps/api-server/app/modules/ai_gateway/`
    - `apps/user-app` 插件详情、AI 供应商、主题展示页
    - 插件开发文档
  - 这一步先不做什么：先不做自动升级平台。
  - 怎么算完成：
    1. 当前版本机制现状和缺口被写清楚
    2. 接口和前端能展示统一版本结果
    3. 兼容性字段有明确边界
  - 怎么验证：
    - 接口测试
    - 文档走查
  - 对应需求：`requirements.md` 需求 4
  - 对应设计：`design.md` §3.2、§6.3
  - 本次推进结果：
    - 后端统一插件注册出口开始产出最小 `update_state`，不再长期返回空值；当前规则只保留 `up_to_date`、`update_available`、`unknown` 三种结果
    - 插件详情抽屉现在会统一展示声明版本、已安装版本、更新状态和兼容性字段，`version / installed_version / compatibility / update_state` 不再只是接口里的摆设
    - AI 供应商详情页现在会显示来源插件版本和来源插件更新状态，继续沿用统一插件注册结果，不再额外拼一套版本模型
    - 主题设置页现在会显示主题对应插件版本，复用 `ThemeProvider` 已经拉取的统一插件注册表，不新增第二套主题版本状态
    - 已新增 `specs/004.5-插件能力统一接入与版本治理/docs/20260317-插件版本治理现状与最小能力说明.md`，把当前真实能力、字段边界和明确不做的范围写清楚
  - 本次验证结果：
    - 已用 `apps/api-server/.venv/Scripts/python.exe -m py_compile apps/api-server/app/modules/plugin/service.py` 验证后端版本状态改动语法通过
    - 已用 `cmd /c npm.cmd run typecheck` 跑通 `apps/user-app` 类型检查
  - 收口结论：
    - 3.2 需要的“现状写清楚、统一结果能展示、边界说清楚”这三件事已经落地，可以收为 `DONE`

- [x] 3.3 更新旧 Spec、插件规范文档和开发者手册
  - 状态：DONE
  - 这一步到底做什么：把 `004.2.2`、`004.3`、`004.4`、`001.5` 和开发者手册里的旧说法回写到最新规则。
  - 做完你能看到什么：以后不管先看哪份文档，都不会再看到互相打架的规则。
  - 先依赖什么：3.2
  - 开始前先看：
    - `requirements.md` 需求 5
    - `design.md` §8.2「待确认项」
    - `docs/开发设计规范/20260317-插件启用禁用统一规则.md`
    - `docs/开发者文档/插件开发/`
  - 主要改哪里：
    - `specs/004.2.2-插件禁用能力统一与停用收口/`
    - `specs/004.3-插件开发规范与注册表/`
    - `specs/004.4-用户前端插件管理与插件市场/`
    - `specs/001.5-AI供应商管理插件化与模型摘要重构/`
    - `docs/开发者文档/插件开发/`
  - 这一步先不做什么：不再新开第二份平行规范。
  - 怎么算完成：
    1. 旧 Spec 补上最新边界或跳转说明
    2. 开发者手册能看到主题插件、AI 供应商插件和版本治理说明
    3. 项目规则引用关系清楚
  - 怎么验证：
    - 文档走查
    - 抽样检查旧文档引用
  - 对应需求：`requirements.md` 需求 5
  - 对应设计：`design.md` §2.2、§8.2
  - 本次推进结果：
    - 已在 `specs/004.2.2-插件禁用能力统一与停用收口/requirements.md` 顶部补 `2026-03-17 最新边界说明`，明确插件启停唯一真相已经由 `004.5` 和统一规则文档接管
    - 已在 `specs/004.3-插件开发规范与注册表/README.md`、`specs/004.4-用户前端插件管理与插件市场/README.md`、`specs/001.5-AI供应商管理插件化与模型摘要重构/README.md` 顶部补最新边界说明，收口主题包、AI 供应商、统一启停和最小版本治理的跳转关系
    - 已在 `docs/开发者文档/插件开发/README.md` 补当前正式插件类型和统一规则入口，明确开发者手册不再维护平行的主题规则和 AI 供应商规则
    - 已在 `docs/开发者文档/插件开发/zh-CN/01-插件开发总览.md` 补 9 类正式插件类型，把 `theme-pack`、`ai-provider` 纳入总览说明，并补统一启停和版本治理边界
    - 已在 `docs/开发者文档/插件开发/zh-CN/03-manifest字段规范.md` 补 `theme-pack`、`ai-provider` 类型说明，以及 `version / compatibility / installed_version / update_state` 的最小边界
    - 已同步更新 `docs/开发者文档/插件开发/en/README.md`、`docs/开发者文档/插件开发/en/01-plugin-development-overview.md`、`docs/开发者文档/插件开发/en/03-manifest-spec.md`，保持中英文入口的边界说明一致
    - 已顺手收掉 `apps/user-app/src/pages/settings/integrations/index.tsx` 的插件标签硬编码，统一改用 i18n 键 `settings.integrations.instance.pluginLabel`
  - 本次验证结果：
    - 已人工走查旧 Spec 顶部最新边界说明，确认都明确指回 `004.5`、统一启停规则文档和版本治理说明文档
    - 已抽样检查开发者手册，确认正式插件类型已经更新到 9 类，且 `theme-pack`、`ai-provider` 已进入总览和 manifest 规则
    - 前端改动已纳入后续 `typecheck` 验证

### 最终检查

- [x] 3.4 最终检查点
  - 状态：DONE
  - 这一步到底做什么：确认这次改造不是“主题补一点、AI 补一点、入口补一点”的散装结果，而是真正统一收口。
  - 做完你能看到什么：主题、AI 供应商、现有插件能力、启停规则、版本治理和文档体系能一一对上。
  - 先依赖什么：3.3
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
    - `docs/`
  - 主要改哪里：当前 Spec 全部文件和相关实现文件
  - 这一步先不做什么：不再加新目标。
  - 怎么算完成：
    1. 关键任务都能追溯到需求和设计
    2. 兼容性、风险和延后项写清楚
    3. 后续接手的人能顺着文档快速找到真实规则
  - 怎么验证：
    - 按 Spec 验收清单逐项核对
  - 对应需求：`requirements.md` 全部需求
  - 对应设计：`design.md` 全文
  - 最终核对结果：
    - 主题和 AI 供应商都已经进入统一插件注册结果，不再维护新的平行注册表真相
    - 新增入口、执行入口、存量对象页面、主题消费入口、AI 供应商消费入口已经统一回到 `enabled / disabled_reason` 和 `require_available_household_plugin(...)`
    - 插件筛选类型、插件详情、主题版本显示、AI 供应商来源版本显示都已经落到统一版本字段：`version / installed_version / compatibility / update_state`
    - 旧 Spec、中文开发手册、英文开发手册都已补最新边界说明，不再把 `theme-pack`、`ai-provider` 当成体系外特例
  - 剩余风险与延后项：
    - 项目里仍保留 `plugin_not_visible_in_household` 这类历史错误码，但当前只用于“当前家庭看不到插件”的兼容语义，未继续承担禁用执法职责
    - `tests/test_scheduler_foundation.py` 仍有历史编码损坏，本轮无法把那条旧回归入口一起跑通
    - 当前版本治理仍然是最小能力，只做统一字段展示和状态提示，明确还没有远程市场比对、自动升级和完整 semver 治理
  - 本次验收结果：
    - 已按 `requirements.md` 6 条需求逐项回看对应实现和文档回写
    - 已完成本轮新增后端定向测试与前端 `typecheck`
    - 004.5 当前任务可收口为阶段性完成，后续若继续扩范围，应新开任务而不是在这里偷偷加目标
