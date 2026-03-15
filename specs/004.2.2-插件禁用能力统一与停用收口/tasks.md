# 任务清单 - 插件禁用能力统一与停用收口（人话版）

状态：Draft

## 这份任务清单怎么用

这份清单不是拿来讨论“插件治理方向”的，是拿来把插件禁用这件事真正做实。

这次目标只有一个：

- 让当前家庭禁用插件以后，前端看起来是禁用，后端也真的停用，运行链路不会再偷偷绕过去

## 阶段 1：先把状态模型收口

- [ ] 1.1 定义家庭级插件覆盖状态模型
  - 状态：TODO
  - 这一步到底做什么：给每个家庭一个正式的插件启停覆盖记录，不再拿零散字段和本地文件混着凑。
  - 做完你能看到什么：后端已经有地方记录“这个家庭把哪个插件关掉了”。
  - 先依赖什么：`requirements.md` 需求 1、需求 2
  - 开始前先看：
    - `requirements.md`
    - `design.md` §3.2、§4.1
    - `apps/api-server/migrations/20260311-数据库迁移规范.md`
  - 主要改哪里：
    - 插件状态模型
    - Alembic migration
  - 按文件拆开看：
    - `apps/api-server/app/modules/plugin/models.py`：新增家庭级插件状态覆盖模型，别把它硬塞回 `PluginMount`。
    - `apps/api-server/app/modules/plugin/repository.py`：补覆盖状态的查询、写入、按家庭读取接口。
    - `apps/api-server/app/modules/plugin/schemas.py`：补状态覆盖相关 schema，不再把 builtin 排除在状态更新语义之外。
    - `apps/api-server/alembic/versions/`：新增 migration，创建覆盖状态表和唯一索引。
    - `apps/api-server/migrations/20260311-数据库迁移规范.md`：实现前必须先按这里的规则检查迁移写法。
  - 这一步先不做什么：先不改前端，不先碰所有运行链路。
  - 怎么算完成：
    1. 当前家庭可以对任意来源插件保存启停覆盖状态
    2. 没有覆盖记录时仍保持现有默认行为
  - 怎么验证：
    - 模型测试
    - migration 结构检查
  - 对应需求：`requirements.md` 需求 1、需求 2
  - 对应设计：`design.md` §3.2、§4.1

- [ ] 1.2 做统一最终状态解析器
  - 状态：TODO
  - 这一步到底做什么：把基础状态和家庭覆盖状态合并成一个最终 `enabled`，不再让每个模块自己写判断。
  - 做完你能看到什么：后端已经能稳定返回每个插件在当前家庭下的最终状态。
  - 先依赖什么：1.1
  - 开始前先看：
    - `requirements.md` 需求 1
    - `design.md` §2.1、§3.2.2
  - 主要改哪里：
    - 插件服务层
    - 插件列表组装逻辑
  - 按文件拆开看：
    - `apps/api-server/app/modules/plugin/service.py`：新增最终状态合并逻辑，把基础状态和家庭覆盖状态合成统一 `enabled`。
    - `apps/api-server/app/modules/plugin/schemas.py`：给列表返回结构补 `base_enabled`、`household_enabled`、最终 `enabled` 等字段。
    - `apps/api-server/app/modules/plugin/repository.py`：支持批量读取当前家庭插件覆盖状态，避免列表接口 N 次查库。
    - `apps/api-server/tests/test_plugin_manifest.py`：补最终状态合并和内置插件家庭级禁用测试。
  - 这一步先不做什么：先不改页面交互，不先改任务或 Agent 入口。
  - 怎么算完成：
    1. 当前家庭插件列表直接返回最终 `enabled`
    2. 内置插件不再被默认写死为启用
  - 怎么验证：
    - 列表接口测试
    - 内置插件状态对照测试
  - 对应需求：`requirements.md` 需求 1
  - 对应设计：`design.md` §2.3.1、§3.2.2

### 阶段检查

- [ ] 1.3 状态模型检查点
  - 状态：TODO
  - 这一步到底做什么：确认插件状态已经能在后端统一说清楚，不再存在“一半看文件、一半看挂载、一半前端自己猜”的烂状态。
  - 做完你能看到什么：后面可以放心继续改接口和运行链路。
  - 先依赖什么：1.1、1.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：本阶段全部相关后端模块
  - 这一步先不做什么：不加前端按钮，不先改业务链路文案。
  - 怎么算完成：
    1. 最终状态规则稳定
    2. 现有默认行为未被破坏
  - 怎么验证：
    - 人工走查
    - 关键测试回归
  - 对应需求：`requirements.md` 需求 1、非功能需求 2
  - 对应设计：`design.md` §2、§4

## 阶段 2：把前端启停交互改成真的可用

- [ ] 2.1 改插件管理页和详情页的状态来源
  - 状态：TODO
  - 这一步到底做什么：让前端只认后端返回的最终 `enabled`，不再本地推导内置插件状态。
  - 做完你能看到什么：页面展示和后端真实状态一致。
  - 先依赖什么：1.3
  - 开始前先看：
    - `requirements.md` 需求 4
    - `design.md` §2.3.1、§3.3.1
    - `specs/004.4-用户前端插件管理与插件市场/`
  - 主要改哪里：
    - 插件管理页
    - 插件详情抽屉
    - 前端类型和 API 适配层
  - 按文件拆开看：
    - `apps/user-web/src/pages/SettingsPluginsPage.tsx`：删掉“内置插件默认启用”的本地推导，统一以后端 `enabled` 渲染。
    - `apps/user-web/src/components/PluginDetailDrawer.tsx`：删掉 builtin 不显示开关的特殊判断，详情页状态和列表页保持一致。
    - `apps/user-web/src/lib/types.ts`：补最终状态字段定义，前端不再只靠 mount 类型描述插件启停。
    - `apps/user-web/src/lib/api.ts`：调整列表接口响应类型，确保页面能直接拿到最终状态。
  - 这一步先不做什么：先不扩市场页，不重做整套 UI。
  - 怎么算完成：
    1. 内置插件禁用状态可以正确显示
    2. 刷新页面后状态保持一致
  - 怎么验证：
    - 页面联调
    - 人工操作后刷新验证
  - 对应需求：`requirements.md` 需求 2、需求 4
  - 对应设计：`design.md` §2.3.1、§3.3.1、§3.3.2

- [ ] 2.2 提供统一插件状态更新接口并接到前端
  - 状态：TODO
  - 这一步到底做什么：让前端不再区分 builtin 和 mount 走不同启停逻辑，统一发一个状态更新请求。
  - 做完你能看到什么：当前家庭下所有来源插件的启停入口一致。
  - 先依赖什么：2.1
  - 开始前先看：
    - `requirements.md` 需求 2
    - `design.md` §2.3.2、§3.3.2
  - 主要改哪里：
    - 后端插件状态更新接口
    - 前端启停交互
  - 按文件拆开看：
    - `apps/api-server/app/api/v1/endpoints/ai_config.py`：新增统一插件状态更新接口，语义覆盖 builtin / official / third_party。
    - `apps/api-server/app/modules/plugin/service.py`：收口状态更新逻辑，别再让 builtin 和 mount 分两套写法。
    - `apps/api-server/app/modules/plugin/schemas.py`：新增状态更新请求和响应 schema。
    - `apps/user-web/src/lib/api.ts`：补统一启停接口调用方法。
    - `apps/user-web/src/pages/SettingsPluginsPage.tsx`：列表页启停按钮改成统一调用新接口。
    - `apps/user-web/src/components/PluginDetailDrawer.tsx`：详情页启停按钮也改成统一调用新接口。
  - 这一步先不做什么：先不做批量启停。
  - 怎么算完成：
    1. builtin / official / third_party 都能走同一启停接口
    2. 失败时能返回明确错误并展示给用户
  - 怎么验证：
    - 接口测试
    - 前后端联调
  - 对应需求：`requirements.md` 需求 2、需求 4
  - 对应设计：`design.md` §2.3.2、§3.3.2

### 阶段检查

- [ ] 2.3 前端启停检查点
  - 状态：TODO
  - 这一步到底做什么：确认用户看到的不是假开关，而是真能影响后端状态的启停操作。
  - 做完你能看到什么：插件管理页已经能正确管理内置插件和挂载插件。
  - 先依赖什么：2.1、2.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：本阶段前后端联动点
  - 这一步先不做什么：不先验收全部运行入口。
  - 怎么算完成：
    1. 状态显示正确
    2. 启停操作可用
    3. 错误提示明确
  - 怎么验证：
    - 人工走查
    - 前端联调验证
  - 对应需求：`requirements.md` 需求 2、需求 4
  - 对应设计：`design.md` §2.3.1、§2.3.2、§5.3

## 阶段 3：把运行时停用收口补齐

- [ ] 3.1 给任务和 Agent 入口接统一可用性判断
  - 状态：TODO
  - 这一步到底做什么：确保插件禁用后，任务执行和 Agent 调用都会在入口就被拦住。
  - 做完你能看到什么：最主要的两条执行链路不再绕过禁用状态。
  - 先依赖什么：2.3
  - 开始前先看：
    - `requirements.md` 需求 3
    - `design.md` §2.3.3、§3.3.3
    - `specs/004.2-插件系统与外部能力接入/`
  - 主要改哪里：
    - 插件任务入口
    - Agent 桥接入口
  - 按文件拆开看：
    - `apps/api-server/app/modules/plugin/service.py`：在任务创建、执行入口前统一检查最终状态。
    - `apps/api-server/app/modules/plugin/agent_bridge.py`：不要只看旧字段，统一走最终可用性判断。
    - `apps/api-server/app/api/v1/endpoints/plugin_jobs.py`：如果这里还存在入口层校验，也要同步接统一判断。
    - `apps/api-server/tests/test_agent_plugin_bridge.py`：补家庭级禁用后的 Agent 调用失败测试。
  - 这一步先不做什么：先不碰通道和地区 provider。
  - 怎么算完成：
    1. 禁用插件不能被创建任务或继续执行
    2. Agent 调用禁用插件时能拿到结构化错误
  - 怎么验证：
    - 集成测试
    - 手动验证错误提示
  - 对应需求：`requirements.md` 需求 3
  - 对应设计：`design.md` §2.3.3、§6.3

- [ ] 3.2 给通道、地区 provider、语言包链路接统一可用性判断
  - 状态：TODO
  - 这一步到底做什么：把最容易漏掉的几条插件链路也接回统一判断，避免禁用后还有侧门。
  - 做完你能看到什么：插件被关掉后，相关功能不会在别的地方偷偷继续生效。
  - 先依赖什么：3.1
  - 开始前先看：
    - `requirements.md` 需求 3、需求 4
    - `design.md` §2.3.3、§5.3
  - 主要改哪里：
    - channel 相关模块
    - region provider 运行时
    - locale 插件过滤逻辑
  - 按文件拆开看：
    - `apps/api-server/app/modules/channel/account_service.py`：解析 channel 插件时补最终状态校验。
    - `apps/api-server/app/modules/channel/gateway_service.py`：执行前补统一可用性判断，别绕过 household registry。
    - `apps/api-server/app/modules/channel/delivery_service.py`：投递前补统一可用性判断。
    - `apps/api-server/app/modules/channel/status_service.py`：确认 probe 和状态展示也尊重禁用状态。
    - `apps/api-server/app/modules/region/plugin_runtime.py`：同步地区 provider 时改成认最终状态，不只看 mount.enabled。
    - `apps/api-server/app/modules/plugin/service.py`：语言包插件过滤改成认最终状态。
    - `apps/api-server/app/modules/scheduler/service.py`：如果调度链路直接引用插件状态，也要切到统一判断。
  - 这一步先不做什么：先不做历史配置自动清理。
  - 怎么算完成：
    1. 禁用插件不会继续参与通道执行或 provider 注册
    2. 前端不会再把该插件能力当成可用能力展示
  - 怎么验证：
    - 集成测试
    - 关键链路人工走查
  - 对应需求：`requirements.md` 需求 3、需求 4
  - 对应设计：`design.md` §2.3.3、§5.3、§6.3

### 阶段检查

- [ ] 3.3 停用收口检查点
  - 状态：TODO
  - 这一步到底做什么：确认插件禁用已经不是“UI 状态变化”，而是系统里真的停下来。
  - 做完你能看到什么：主要运行链路都已经服从统一状态判断。
  - 先依赖什么：3.1、3.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：本阶段所有运行链路相关模块
  - 这一步先不做什么：不扩插件卸载和配置迁移。
  - 怎么算完成：
    1. 禁用后运行入口不会继续执行
    2. 前端和后端提示一致
  - 怎么验证：
    - 人工走完整链路
    - 关键回归测试
  - 对应需求：`requirements.md` 需求 3、需求 4
  - 对应设计：`design.md` §2.3.3、§6

## 阶段 4：补旧 Spec 和最终验收

- [ ] 4.1 更新旧插件系统 Spec 的相关描述
  - 状态：TODO
  - 这一步到底做什么：把 `004.2`、`004.4` 里涉及插件启停的地方补上新规则，避免旧文档继续误导。
  - 做完你能看到什么：后来接手的人能直接找到正确文档，不会还照着旧说法继续开发。
  - 先依赖什么：3.3
  - 开始前先看：
    - `requirements.md` 需求 5
    - `design.md` §6.4
    - `specs/004.2-插件系统与外部能力接入/README.md`
    - `specs/004.4-用户前端插件管理与插件市场/README.md`
  - 主要改哪里：
    - `specs/004.2-插件系统与外部能力接入/`
    - `specs/004.4-用户前端插件管理与插件市场/`
  - 按文件拆开看：
    - `specs/004.2-插件系统与外部能力接入/README.md`：补“插件启停基础能力”和“统一禁用规则”的边界说明。
    - `specs/004.4-用户前端插件管理与插件市场/README.md`：补前端必须以后端最终状态为准的说明。
    - `specs/004.4-用户前端插件管理与插件市场/requirements.md`：把内置插件家庭级禁用和最终状态语义写明。
    - `specs/004.4-用户前端插件管理与插件市场/design.md`：把插件管理页的数据结构、接口语义和错误处理改到与 `004.2.2` 对齐。

## 附：本次实施建议按这个文件顺序推进

### 后端先做

1. `apps/api-server/app/modules/plugin/models.py`
2. `apps/api-server/app/modules/plugin/repository.py`
3. `apps/api-server/app/modules/plugin/schemas.py`
4. `apps/api-server/alembic/versions/`
5. `apps/api-server/app/modules/plugin/service.py`
6. `apps/api-server/app/api/v1/endpoints/ai_config.py`
7. `apps/api-server/app/modules/plugin/agent_bridge.py`
8. `apps/api-server/app/modules/channel/account_service.py`
9. `apps/api-server/app/modules/channel/gateway_service.py`
10. `apps/api-server/app/modules/channel/delivery_service.py`
11. `apps/api-server/app/modules/region/plugin_runtime.py`
12. `apps/api-server/app/modules/scheduler/service.py`
13. `apps/api-server/tests/test_plugin_manifest.py`
14. `apps/api-server/tests/test_agent_plugin_bridge.py`

### 前端再接

1. `apps/user-web/src/lib/types.ts`
2. `apps/user-web/src/lib/api.ts`
3. `apps/user-web/src/pages/SettingsPluginsPage.tsx`
4. `apps/user-web/src/components/PluginDetailDrawer.tsx`

### 文档最后收口

1. `specs/004.2.2-插件禁用能力统一与停用收口/`
2. `specs/004.2-插件系统与外部能力接入/README.md`
3. `specs/004.4-用户前端插件管理与插件市场/requirements.md`
4. `specs/004.4-用户前端插件管理与插件市场/design.md`
5. `specs/004.4-用户前端插件管理与插件市场/README.md`
  - 这一步先不做什么：先不大改 `004.3`。
  - 怎么算完成：
    1. 旧 Spec 已明确指向 `004.2.2`
    2. 不再出现“内置插件不支持禁用”这类过时说法
  - 怎么验证：
    - 文档走查
  - 对应需求：`requirements.md` 需求 5
  - 对应设计：`design.md` §6.4

### 最终检查

- [ ] 4.2 最终检查点
  - 状态：TODO
  - 这一步到底做什么：确认这次改造已经把“禁用插件”从散乱能力收成一致规则。
  - 做完你能看到什么：前端、后端、运行时和旧文档都已经对上，不再各说各话。
  - 先依赖什么：4.1
  - 开始前先看：
    - `README.md`
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：当前 Spec 全部内容和相关旧 Spec 补充说明
  - 这一步先不做什么：不追加插件卸载和市场安装。
  - 怎么算完成：
    1. 当前家庭可以禁用内置插件和挂载插件
    2. 禁用后相关功能真的停止
    3. 旧 Spec 已更新到位
  - 怎么验证：
    - 按主链路做一次完整人工验收
    - 核对关键测试结果
  - 对应需求：`requirements.md` 全部需求
  - 对应设计：`design.md` 全文
