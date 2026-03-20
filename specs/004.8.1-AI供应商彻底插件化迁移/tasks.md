# 任务清单 - AI 供应商彻底插件化迁移

状态：In Progress

## 这份任务清单怎么用

这份文档现在分两段：

- 已完成：第一阶段已经落地的迁移
- 进行中：为了把 AI 供应商从核心前后端彻底剥离，还必须继续做的事

## 阶段 1：建立 provider driver contract

- [x] 1.1 定义统一 driver 接口
  - 状态：DONE
  - 做了什么：新增 `apps/api-server/app/modules/ai_gateway/provider_driver.py`，把宿主对供应商执行的依赖收口为 `invoke / ainvoke / stream`
  - 做完后能看到什么：宿主不再直接依赖厂商分支，而是依赖统一 driver
  - 依赖：`requirements.md`、`design.md`
  - 主要文件：
    - `apps/api-server/app/modules/ai_gateway/provider_driver.py`
    - `apps/api-server/tests/test_ai_provider_driver_registry.py`
  - 不做什么：不在 contract 里重新发明新的宿主治理逻辑
  - 验证：
    - `.\.venv\Scripts\python.exe -m unittest tests.test_ai_provider_driver_registry`

- [x] 1.2 把 `ai-provider` 接入正式 entrypoint
  - 状态：DONE
  - 做了什么：`ai-provider` manifest 现在必须声明 `entrypoints.ai_provider`
  - 做完后能看到什么：供应商插件既有声明，也有正式执行入口
  - 主要文件：
    - `apps/api-server/app/modules/plugin/schemas.py`
    - `apps/api-server/tests/test_plugin_manifest.py`
  - 验证：
    - `.\.venv\Scripts\python.exe -m unittest tests.test_plugin_manifest`

## 阶段 2：把 builtin AI 供应商迁成真实插件

- [x] 2.1 用真实 manifest 替代虚拟 ai-provider 条目
  - 状态：DONE
  - 做了什么：新增 `apps/api-server/app/plugins/builtin/ai_provider_*/manifest.json`
  - 做完后能看到什么：builtin AI 供应商直接来自插件目录，不再由核心虚拟生成
  - 主要文件：
    - `apps/api-server/app/plugins/builtin/ai_provider_chatgpt/manifest.json`
    - `apps/api-server/app/plugins/builtin/ai_provider_deepseek/manifest.json`
    - `apps/api-server/app/plugins/builtin/ai_provider_qwen/manifest.json`
    - `apps/api-server/app/plugins/builtin/ai_provider_glm/manifest.json`
    - `apps/api-server/app/plugins/builtin/ai_provider_siliconflow/manifest.json`
    - `apps/api-server/app/plugins/builtin/ai_provider_kimi/manifest.json`
    - `apps/api-server/app/plugins/builtin/ai_provider_minimax/manifest.json`
    - `apps/api-server/app/plugins/builtin/ai_provider_claude/manifest.json`
    - `apps/api-server/app/plugins/builtin/ai_provider_gemini/manifest.json`
    - `apps/api-server/app/plugins/builtin/ai_provider_openrouter/manifest.json`
    - `apps/api-server/app/plugins/builtin/ai_provider_doubao/manifest.json`
    - `apps/api-server/app/plugins/builtin/ai_provider_doubao_coding/manifest.json`
    - `apps/api-server/app/plugins/builtin/ai_provider_byteplus/manifest.json`
    - `apps/api-server/app/plugins/builtin/ai_provider_byteplus_coding/manifest.json`
  - 验证：
    - `.\.venv\Scripts\python.exe -m unittest tests.test_plugin_manifest.PluginManifestTests.test_registered_plugins_include_theme_and_real_ai_provider_entries`

- [x] 2.2 把厂商特例迁到插件 driver
  - 状态：DONE
  - 做了什么：把 SiliconFlow 和 OpenRouter 的厂商逻辑迁到插件目录
  - 做完后能看到什么：核心运行时不再保留这些供应商专用逻辑
  - 主要文件：
    - `apps/api-server/app/plugins/_ai_provider_runtime_helpers.py`
    - `apps/api-server/app/plugins/builtin/ai_provider_siliconflow/driver.py`
    - `apps/api-server/app/plugins/builtin/ai_provider_openrouter/driver.py`
    - `apps/api-server/tests/test_ai_provider_builtin_driver_specials.py`
  - 验证：
    - `.\.venv\Scripts\python.exe -m unittest tests.test_ai_provider_builtin_driver_specials`

## 阶段 3：从核心移除供应商真相源和厂商分发表

- [x] 3.1 删除核心供应商注册表
  - 状态：DONE
  - 做了什么：删除 `apps/api-server/app/modules/ai_gateway/provider_adapter_registry.py`
  - 做完后能看到什么：核心不再维护供应商真相源
  - 主要文件：
    - `apps/api-server/app/modules/ai_gateway/provider_config_service.py`
    - `apps/api-server/app/modules/plugin/service.py`
  - 验证：
    - `.\.venv\Scripts\python.exe -m unittest tests.test_ai_config_center.AiProviderAdapterCatalogTests.test_list_provider_adapters_reads_from_registered_plugins`

- [x] 3.2 清理核心里的厂商特判
  - 状态：DONE
  - 做了什么：`provider_runtime.py`、`service.py` 不再保留 SiliconFlow/OpenRouter 专用逻辑
  - 做完后能看到什么：核心只保留协议族桥接和统一治理逻辑
  - 主要文件：
    - `apps/api-server/app/modules/ai_gateway/provider_runtime.py`
    - `apps/api-server/app/modules/ai_gateway/service.py`
    - `apps/api-server/tests/test_ai_provider_driver_gateway.py`
    - `apps/api-server/tests/test_provider_runtime_async_stream.py`
  - 验证：
    - `.\.venv\Scripts\python.exe -m unittest tests.test_ai_provider_driver_gateway tests.test_provider_runtime_async_stream`

## 阶段 4：统一文档和旧 spec 边界

- [x] 4.1 把 `004.8.1` 收口成唯一主 spec
  - 状态：DONE
  - 做了什么：把 `README.md`、`requirements.md`、`design.md`、`tasks.md` 改成已实施口径
  - 做完后能看到什么：不再把迁移目标态写成“尚未实施”
  - 主要文件：
    - `specs/004.8.1-AI供应商彻底插件化迁移/*`

- [x] 4.2 把开发者文档和旧 spec 改成“主 spec + 历史背景”
  - 状态：DONE
  - 做了什么：统一把 AI 供应商插件化相关文档改成引用 `004.8.1`
  - 做完后能看到什么：开发者不会再把旧实现误读成当前规则
  - 主要文件：
    - `docs/开发者文档/插件开发/*`
    - `specs/001.5-*/*`
    - `specs/004.5-*/*`
    - `specs/004.8-*/*`

## 阶段 5：最终验收

- [x] 5.1 完成针对性回归
  - 状态：DONE
  - 做了什么：执行插件 manifest、driver registry、builtin specials、gateway、streaming 相关测试
  - 做完后能看到什么：迁移后的核心链路和插件链路都能回归通过
  - 验证：
    - `.\.venv\Scripts\python.exe -m unittest tests.test_ai_provider_driver_registry tests.test_plugin_manifest.PluginManifestTests.test_registered_plugins_include_theme_and_real_ai_provider_entries tests.test_ai_provider_builtin_driver_specials tests.test_ai_config_center.AiConfigCenterTests.test_provider_adapter_catalog_exposes_builtin_ai_provider_plugins tests.test_ai_config_center.AiConfigCenterTests.test_provider_adapter_catalog_aligns_builtin_defaults tests.test_ai_config_center.AiConfigCenterTests.test_create_siliconflow_qwen_provider_does_not_write_vendor_defaults_into_profile tests.test_ai_config_center.AiProviderAdapterCatalogTests.test_list_provider_adapters_reads_from_registered_plugins tests.test_ai_provider_plugin_state tests.test_ai_provider_official_plugins tests.test_ai_provider_driver_gateway tests.test_provider_runtime_async_stream`

- [x] 5.2 完成语法检查和核心痕迹回扫
  - 状态：DONE
  - 做了什么：对 `app/modules/ai_gateway`、`app/modules/plugin`、`app/plugins` 做编译和关键词回扫
  - 做完后能看到什么：核心目录里不再残留供应商注册表和厂商特判
  - 验证：
    - `.\.venv\Scripts\python.exe -m compileall app\modules\ai_gateway app\modules\plugin app\plugins`

## 阶段 6：补齐 ai-provider 前端契约

- [ ] 6.1 给 manifest 增加 branding 契约
  - 状态：DONE
  - 做什么：为 `ai-provider` manifest 增加 `branding`，至少覆盖 logo 资源路径、说明文案资源路径、可选明暗变体
  - 做完后能看到什么：前端不再需要核心里的 Logo 映射表
  - 依赖：`requirements.md`、`design.md`
  - 主要文件：
    - `apps/api-server/app/modules/plugin/schemas.py`
    - `apps/api-server/app/modules/ai_gateway/schemas.py`
    - `apps/api-server/app/modules/ai_gateway/provider_config_service.py`
    - `apps/api-server/app/plugins/builtin/ai_provider_*/manifest.json`
  - 当前结果：宿主 adapter API 已经能返回 `branding.logo_url / logo_dark_url / description_locales`；Ollama、LM Studio、LocalAI 已迁成完整 branding 样板
  - 明确不做什么：不在核心前端继续新增任何供应商 SVG
  - 验证：
    - `.\.venv\Scripts\python.exe -m unittest tests.test_plugin_manifest tests.test_ai_config_center.AiConfigCenterTests.test_provider_adapter_catalog_exposes_builtin_ai_provider_plugins`

- [x] 6.2 给 manifest 增加 config_ui 契约
  - 状态：DONE
  - 做什么：声明字段分组、字段顺序、隐藏规则、说明文本和动作按钮
  - 做完后能看到什么：前端不再通过 `field.key === 'model_name'` 之类的分支决定 UI
  - 主要文件：
    - `apps/api-server/app/modules/plugin/schemas.py`
    - `apps/api-server/app/modules/ai_gateway/schemas.py`
    - `apps/user-app/src/pages/settings/components/*`
    - `apps/user-app/src/pages/setup/*`
  - 当前结果：前端已经按 `config_ui.sections / actions / field_ui` 做通用渲染，不再用 `adapter_code` 选页面分支；当前 Ollama、LM Studio、LocalAI 已声明 section 和 action
  - 明确不做什么：不为单个供应商继续加 React 分支
  - 验证：
    - `npm.cmd run typecheck`

- [x] 6.3 给 manifest 增加 model_discovery 契约
  - 状态：DONE
  - 做什么：声明触发依赖字段、回填字段、节流时间、空结果提示和动作绑定关系
  - 做完后能看到什么：模型刷新逻辑改成插件声明驱动
  - 主要文件：
    - `apps/api-server/app/modules/plugin/schemas.py`
    - `apps/api-server/app/modules/ai_gateway/provider_model_discovery_service.py`
    - `apps/user-app/src/pages/settings/components/useAiProviderModelDiscovery.ts`
  - 当前结果：模型发现 hook 已经改成按 `depends_on_fields / target_field / debounce_ms` 运行；不再对 `model_name` 和 `base_url` 写核心特判
  - 明确不做什么：不在核心页面继续写字段名特判
  - 验证：
    - `.\.venv\Scripts\python.exe -m unittest tests.test_ai_config_center`

## 阶段 7：把前端供应商特定资源和行为移出核心

- [ ] 7.1 删除核心 Logo 与说明文案映射
  - 状态：DONE
  - 做什么：删除 `AiProviderLogos.tsx` 和 `adapter_code -> description key` 这类硬编码映射
  - 做完后能看到什么：前端只认 adapter API 返回的 branding/description
  - 主要文件：
    - `apps/user-app/src/pages/settings/components/AiProviderLogos.tsx`
    - `apps/user-app/src/pages/settings/components/aiProviderCatalog.ts`
    - `apps/user-app/src/pages/setup/SimpleAiProviderSetup.tsx`
  - 当前结果：`AiProviderLogos.tsx` 已删除，`adapter_code -> description key` 映射已删除
  - 明确不做什么：不以“先兼容一下”为理由保留旧映射表
  - 验证：
    - `npm.cmd run typecheck`
    - 核心前端回扫不再命中 `adapter_code` 品牌映射

- [x] 7.2 改成通用品牌渲染器
  - 状态：DONE
  - 做什么：统一从插件 manifest 派生的 adapter 数据里渲染 logo、说明和动作按钮
  - 做完后能看到什么：设置页和初始化页使用同一套品牌渲染逻辑
  - 主要文件：
    - `apps/user-app/src/pages/settings/components/AiProviderEditorDialog.tsx`
    - `apps/user-app/src/pages/settings/components/AiProviderSelectDialog.tsx`
    - `apps/user-app/src/pages/settings/components/AiProviderConfigPanel.tsx`
    - `apps/user-app/src/pages/setup/SimpleAiProviderSetup.tsx`
  - 当前结果：已新增 `AiProviderBrandMark.tsx`，设置页和初始化页都改成走 adapter.branding
  - 验证：
    - `npm.cmd run typecheck`

## 阶段 8：重新确认协议级执行边界

- [ ] 8.1 评估 `provider_runtime.py` 是否还能继续留在宿主
  - 状态：TODO
  - 做什么：把现有执行逻辑拆成“稳定通用能力”和“仍是协议特例的部分”，决定是否继续下沉到插件端
  - 做完后能看到什么：`004.8.1` 对协议级执行边界有明确结论，不再模糊
  - 主要文件：
    - `apps/api-server/app/modules/ai_gateway/provider_runtime.py`
    - `apps/api-server/app/modules/ai_gateway/provider_driver.py`
    - `docs/开发者文档/插件开发/zh-CN/05-插件对接方式说明.md`
  - 明确不做什么：不在没有评估的前提下继续往 `provider_runtime.py` 塞新协议分支

- [ ] 8.2 如果需要继续下沉，就迁出宿主特定协议执行
  - 状态：TODO
  - 做什么：把不能稳定抽象成宿主能力的协议执行搬到插件侧，同时保留宿主统一调用契约、路由、fallback、状态、审计和错误收口
  - 依赖：8.1
  - 明确不做什么：不破坏现有 provider profile 和 gateway 路由能力

## 阶段 9：补文档和防回归

- [ ] 9.1 更新插件开发文档
  - 状态：DONE
  - 做什么：把 `branding / config_ui / model_discovery` 契约补到插件开发文档
  - 主要文件：
    - `docs/开发者文档/插件开发/zh-CN/05-插件对接方式说明.md`

- [x] 9.2 增加防回归测试
  - 状态：DONE
  - 做什么：增加 manifest 校验和核心目录回扫，防止以后又把 AI 供应商 Logo、说明文案、模型发现分支写回核心
  - 主要文件：
    - `apps/api-server/tests/test_plugin_manifest.py`
    - `apps/api-server/tests/test_ai_config_center.py`
    - `apps/user-app/scripts/check-style-guard.mjs`
  - 当前结果：已补 manifest 契约校验测试、adapter 输出测试，以及前端 style-guard 规则，禁止 `AI_PROVIDER_LOGO_MAP`、`settings.ai.provider.adapter.*`、`field.key === 'model_name'` 回流到核心页面
  - 验证：
    - `.\.venv\Scripts\python.exe -m unittest tests.test_plugin_manifest tests.test_ai_config_center`
