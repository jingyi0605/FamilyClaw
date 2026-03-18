# 任务清单 - AI 供应商彻底插件化迁移

状态：Completed

## 这份任务清单怎么用

这份文档不再描述“计划做什么”，而是回写这次迁移到底做了什么、哪些结果已经落地、怎么验证。

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
