# AI Provider Pluginization Implementation Record

状态：Completed

## 目标

把 AI 供应商调用从“宿主核心里的供应商注册表和厂商分发表”迁成“宿主通过统一 provider driver contract 调用真实 `ai-provider` 插件”。

## 实际落地结果

### 1. 插件契约

- `ai-provider` manifest 现在必须声明 `entrypoints.ai_provider`
- 宿主通过 `apps/api-server/app/modules/ai_gateway/provider_driver.py` 加载 driver
- 宿主只依赖 `invoke / ainvoke / stream`

### 2. builtin AI 供应商

- builtin AI 供应商已经改成真实插件目录
- 不再使用虚拟 ai-provider manifest
- 供应商目录位于 `apps/api-server/app/plugins/builtin/ai_provider_*/`

### 3. 核心代码清理

- `apps/api-server/app/modules/ai_gateway/provider_adapter_registry.py` 已删除
- `apps/api-server/app/modules/plugin/service.py` 不再虚拟生成 ai-provider 条目
- `apps/api-server/app/modules/ai_gateway/service.py` 不再写厂商默认值
- `apps/api-server/app/modules/ai_gateway/provider_runtime.py` 不再保留厂商专用 header/default 特判

### 4. 厂商特例迁移

- SiliconFlow 特例迁到 `apps/api-server/app/plugins/builtin/ai_provider_siliconflow/driver.py`
- OpenRouter 特例迁到 `apps/api-server/app/plugins/builtin/ai_provider_openrouter/driver.py`
- 公共 helper 位于 `apps/api-server/app/plugins/_ai_provider_runtime_helpers.py`

## 验证记录

已通过：

- `.\.venv\Scripts\python.exe -m unittest tests.test_ai_provider_driver_registry tests.test_plugin_manifest.PluginManifestTests.test_registered_plugins_include_theme_and_real_ai_provider_entries tests.test_ai_provider_builtin_driver_specials tests.test_ai_config_center.AiConfigCenterTests.test_provider_adapter_catalog_exposes_builtin_ai_provider_plugins tests.test_ai_config_center.AiConfigCenterTests.test_provider_adapter_catalog_aligns_builtin_defaults tests.test_ai_config_center.AiConfigCenterTests.test_create_siliconflow_qwen_provider_does_not_write_vendor_defaults_into_profile tests.test_ai_config_center.AiProviderAdapterCatalogTests.test_list_provider_adapters_reads_from_registered_plugins tests.test_ai_provider_plugin_state tests.test_ai_provider_official_plugins tests.test_ai_provider_driver_gateway tests.test_provider_runtime_async_stream`
- 结果：`Ran 21 tests ... OK`

已知无关项：

- `tests.test_ai_config_center` 全量里有一个工作区既存失败：`test_butler_bootstrap_flow_reuses_existing_agent_creation_model`
- 现象：期望 `reviewing`，实际 `collecting`
- 这个问题不属于本次 AI 供应商插件化改造引入
