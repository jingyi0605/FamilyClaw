# 任务清单 - AI供应商管理插件化与模型摘要重构（人话版）

状态：Blocked

## 这份文档是干什么的

这不是补材料用的清单，而是把这次改造的真实进度写明白：

- 哪些已经做完了
- 哪些验证已经跑过了
- 哪些还卡在外部环境
- 下一步该怎么收尾

## 状态说明

- `TODO`：还没开始
- `IN_PROGRESS`：正在做
- `BLOCKED`：被外部条件卡住
- `IN_REVIEW`：实现已到位，等补最终验收
- `DONE`：已经完成并回写

---

## 阶段 1：把供应商能力收口成统一插件描述

- [x] 1.1 重构后端 provider adapter 注册表
  - 状态：DONE
  - 这一部到底做什么：把原来偏硬编码的 provider adapter 列表收口成统一注册表，同时允许从 `provider_plugins/*.json` 加载外部扩展。
  - 做完你能看到什么：后端能同时返回内置供应商和外部 JSON 插件描述，而且结构一致。
  - 先依赖什么：无
  - 开始前先看：
    - `requirements.md` 需求 2
    - `design.md` 2.2
    - `design.md` 3.2
  - 主要改哪里：
    - `apps/api-server/app/modules/ai_gateway/provider_adapter_registry.py`
    - `apps/api-server/app/modules/ai_gateway/provider_config_service.py`
  - 这一部先不做什么：不接入通用插件市场，不重做数据库模型。
  - 怎么算完成：
    1. 内置供应商带有 `plugin_id`、`plugin_name`、`supported_model_types`、`llm_workflow`、`field_schema`
    2. 外部 JSON 插件能按统一结构被加载
  - 怎么验证：
    - 运行后端定向测试
    - 人工检查 adapter 返回字段
  - 对应需求：`requirements.md` 需求 2 / 验收 2.1、2.2、2.3
  - 对应设计：`design.md` 2.2、3.2、3.3、6.1

- [x] 1.2 补齐前后端共用的供应商元数据契约
  - 状态：DONE
  - 这一部到底做什么：给 schema 和前端类型补上插件名、支持类型、workflow、动态字段等元数据。
  - 做完你能看到什么：前端可以直接根据 adapter 元数据渲染支持类型、workflow 和动态表单。
  - 先依赖什么：1.1
  - 开始前先看：
    - `requirements.md` 需求 2
    - `requirements.md` 需求 4
    - `design.md` 3.2
  - 主要改哪里：
    - `apps/api-server/app/modules/ai_gateway/schemas.py`
    - `apps/user-app/src/pages/settings/settingsTypes.ts`
    - `packages/user-core/src/domain/types.ts`
  - 这一部先不做什么：不扩展新的路由存储结构。
  - 怎么算完成：
    1. adapter API 能返回支持类型和 `llm_workflow`
    2. 前端类型定义能消费这些字段
  - 怎么验证：
    - 前端类型检查
    - 后端 adapter 定向测试
  - 对应需求：`requirements.md` 需求 2、需求 4
  - 对应设计：`design.md` 3.2、4.1

### 阶段检查

- [x] 1.3 确认插件元数据链路已经打通
  - 状态：DONE
  - 这一部到底做什么：检查从后端 registry 到前端 adapter 列表的数据链路是不是已经闭环。
  - 做完你能看到什么：后面页面改造不需要再临时补字段。
  - 先依赖什么：1.1、1.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：
    - `apps/api-server/tests/test_ai_config_center.py`
  - 这一部先不做什么：不开始页面重构。
  - 怎么算完成：
    1. 核心内置 adapter 定向测试通过
    2. 适配器字段可被前端消费
  - 怎么验证：
    - `.\.venv\Scripts\python.exe -m unittest tests.test_ai_config_center.AiConfigCenterTests.test_provider_adapter_registry_exposes_core_adapters`
  - 对应需求：`requirements.md` 需求 2、需求 4
  - 对应设计：`design.md` 2.1、2.2、7.1

---

## 阶段 2：把 user-app 页面从平铺表单改成列表加摘要

- [x] 2.1 重构主页面为列表和配置摘要
  - 状态：DONE
  - 这一部到底做什么：把设置页主视图改成列表、统计和摘要卡片，不再在页面上平铺完整配置表单。
  - 做完你能看到什么：用户一眼能看见当前有哪些模型、哪些启用、哪些能力已路由。
  - 先依赖什么：1.3
  - 开始前先看：
    - `requirements.md` 需求 1
    - `requirements.md` 需求 4
    - `design.md` 2.3.1
  - 主要改哪里：
    - `apps/user-app/src/pages/settings/components/AiProviderConfigPanel.tsx`
    - `apps/user-app/src/runtime/h5-shell/styles/index.h5.scss`
  - 这一部先不做什么：不在主页面直接编辑所有字段。
  - 怎么算完成：
    1. 主页面只剩列表、统计和摘要
    2. 摘要能展示插件、模型名、支持类型、路由能力和关键字段
  - 怎么验证：
    - 页面人工验收
    - 前端类型检查
  - 对应需求：`requirements.md` 需求 1、需求 4
  - 对应设计：`design.md` 2.3.1、3.1、6.3

- [x] 2.2 新增供应商编辑弹窗和动态表单流程
  - 状态：DONE
  - 这一部到底做什么：把新增/编辑 provider 的操作迁到弹窗里，新增时必须先选供应商插件，再展示动态表单。
  - 做完你能看到什么：不同供应商能展示不同字段，新增流程不再是一张混合大表单。
  - 先依赖什么：2.1
  - 开始前先看：
    - `requirements.md` 需求 3
    - `design.md` 2.3.2
    - `design.md` 2.3.3
  - 主要改哪里：
    - `apps/user-app/src/pages/settings/components/AiProviderEditorDialog.tsx`
    - `apps/user-app/src/pages/settings/components/AiProviderConfigPanel.tsx`
    - `apps/user-app/src/pages/settings/components/aiProviderCatalog.ts`
  - 这一部先不做什么：不支持在编辑时切换已有 provider 的 adapter。
  - 怎么算完成：
    1. 新增时先看到供应商插件选择区
    2. 选中插件后能渲染动态字段、支持类型和 workflow
    3. 提交能正常创建或更新 provider
  - 怎么验证：
    - 页面人工验收
    - 前端类型检查
  - 对应需求：`requirements.md` 需求 3、需求 4
  - 对应设计：`design.md` 2.3.2、2.3.3、6.2

- [x] 2.3 补齐本地化文案和展示映射
  - 状态：DONE
  - 这一部到底做什么：给支持类型、workflow、字段标签和摘要说明补齐前端展示映射。
  - 做完你能看到什么：页面上的模型类型、workflow、字段说明能按 i18n 正常显示。
  - 先依赖什么：2.1、2.2
  - 开始前先看：
    - `requirements.md` 需求 4
    - `design.md` 3.1
  - 主要改哪里：
    - `apps/user-app/src/pages/settings/components/aiProviderCatalog.ts`
    - `apps/user-app/src/runtime/h5-shell/i18n/pageMessages.en-US.ts`
    - `apps/user-app/src/runtime/h5-shell/i18n/pageMessages.zh-CN.ts`
  - 这一部先不做什么：不重构整个设置页的 i18n 体系。
  - 怎么算完成：
    1. 支持类型和 workflow 有稳定展示文案
    2. 动态字段能按 key 映射本地化标签
  - 怎么验证：
    - 前端类型检查
    - 页面人工验收
  - 对应需求：`requirements.md` 需求 4
  - 对应设计：`design.md` 3.1、3.2、7.2

### 阶段检查

- [x] 2.4 确认页面交互主链路已经改完
  - 状态：DONE
  - 这一部到底做什么：确认用户最常走的主链路已经从“平铺配置”切到“列表 + 摘要 + 弹窗编辑”。
  - 做完你能看到什么：结构上的烂味道已经消掉，不需要再继续往旧页面补字段。
  - 先依赖什么：2.1、2.2、2.3
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：
    - `apps/user-app/src/pages/settings/components/AiProviderConfigPanel.tsx`
    - `apps/user-app/src/pages/settings/components/AiProviderEditorDialog.tsx`
  - 这一部先不做什么：不扩展新的 AI 业务能力。
  - 怎么算完成：
    1. 主视图和编辑视图职责分离
    2. 页面结构能支撑继续加供应商插件
  - 怎么验证：
    - 前端类型检查
    - 页面人工验收
  - 对应需求：`requirements.md` 需求 1、需求 2、需求 3、需求 4
  - 对应设计：`design.md` 2.1、2.3、6.2、6.3

---

## 阶段 3：验证、交付和阻塞项

- [ ] 3.1 跑通本地静态验证和后端定向测试
  - 状态：BLOCKED
  - 这一部到底做什么：先把不依赖外部账号和真实 key 的验证跑通，证明这次结构改造没有基础性断裂。
  - 做完你能看到什么：前端类型检查通过，后端 provider registry 的关键测试通过。
  - 先依赖什么：2.4
  - 开始前先看：
    - `requirements.md` 非功能需求 3
    - `design.md` 7.1
    - `design.md` 7.2
  - 主要改哪里：
    - 无新增实现，主要是执行验证
  - 这一部先不做什么：不把真实第三方 API 失败算进结构改造 bug。
  - 阻塞原因：`npm.cmd run typecheck:user-app` 当前失败，错误集中在 `src/pages/family/LegacyFamilyPage.tsx` 和 `src/pages/home/page.rn.tsx`，属于工作区里其他功能的编译问题；后端 provider registry 定向测试已通过。
  - 恢复条件：
    1. 先修复当前工作区其他页面的 TypeScript 编译错误
    2. 重新执行全量 `user-app` 类型检查
  - 怎么算完成：
    1. `npm.cmd run typecheck:user-app` 通过
    2. provider registry 定向测试通过
  - 怎么验证：
    - `npm.cmd run typecheck:user-app`
    - `.\.venv\Scripts\python.exe -m unittest tests.test_ai_config_center.AiConfigCenterTests.test_provider_adapter_registry_exposes_core_adapters`
  - 对应需求：`requirements.md` 非功能需求 3
  - 对应设计：`design.md` 7.1、7.2

- [ ] 3.2 完成页面联调和依赖真实模型调用的流程验收
  - 状态：BLOCKED
  - 这一部到底做什么：补齐真实登录环境下的页面验收，以及依赖有效 OpenAI key 的引导流程测试。
  - 做完你能看到什么：这次改造才能从“核心开发完成”升级到“完整闭环验收完成”。
  - 先依赖什么：3.1
  - 开始前先看：
    - `requirements.md` 需求 1、需求 3、需求 4
    - `design.md` 7.3
    - `docs/README.md`
  - 主要改哪里：
    - 暂无代码改动，主要依赖测试环境
  - 这一部先不做什么：不伪造联调结论，不把环境问题硬说成已完成。
  - 阻塞原因：现网页面访问会跳登录页，当前测试凭据无效；完整 `tests.test_ai_config_center` 中的 `test_butler_bootstrap_flow_reuses_existing_agent_creation_model` 会触发真实 OpenAI 调用，当前环境 key 无效。
  - 恢复条件：
    1. 提供可用的页面登录账号
    2. 提供有效的 OpenAI API key 或隔离掉真实调用依赖
  - 怎么算完成：
    1. 页面手工验收跑完新增、编辑、摘要回显主链路
    2. 依赖真实模型调用的引导测试能稳定通过
  - 怎么验证：
    - 打开 `/pages/settings/ai/index` 做人工验收
    - `.\.venv\Scripts\python.exe -m unittest tests.test_ai_config_center`
  - 对应需求：`requirements.md` 需求 1、需求 3、需求 4 / 非功能需求 3
  - 对应设计：`design.md` 2.3、7.3、8.2

### 最终检查

- [ ] 3.3 关闭阻塞并完成最终验收
  - 状态：BLOCKED
  - 这一部到底做什么：等 3.2 的环境阻塞解除后，把这份 Spec 收口到真正可交付状态。
  - 做完你能看到什么：需求、设计、任务、验证证据能一一对上。
  - 先依赖什么：3.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
    - `docs/README.md`
  - 主要改哪里：
    - 当前 Spec 全部文档
  - 这一部先不做什么：不再追加新范围。
  - 阻塞原因：依赖 3.2 的联调环境恢复。
  - 恢复条件：3.2 完成。
  - 怎么算完成：
    1. 页面和后端完整验收都有证据
    2. 当前阻塞项被关闭或明确转成新任务
  - 怎么验证：
    - 对照 `docs/README.md` 逐项核验
  - 对应需求：`requirements.md` 全部需求
  - 对应设计：`design.md` 全文
