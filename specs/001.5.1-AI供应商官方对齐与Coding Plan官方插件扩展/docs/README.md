# docs 说明

这次 `001.5.1` 的 `docs/` 不拿来堆术语，只放两类东西：

1. 已经做过的官方核查报告。
2. 本次新增 3 家 Coding Plan 供应商的官方资料与 OpenClaw 对照。

## 文档清单

- `20260317-AI供应商LLM通讯官方文档核查报告.md`
  - 这是这次修 builtin 供应商和补流式能力的基线。
  - 重点看报告里的 P0 / P1，不要先去修边角料。

- `20260317-Coding Plan供应商官方资料与OpenClaw对照.md`
  - 这是新增百炼 / Kimi / GLM Coding Plan 官方插件时的配置基线。
  - 重点看默认 `base_url`、协议族、鉴权说明和“是否与普通供应商分开”的结论。

## 使用方式

- 改现有 14 家 builtin 供应商前，先看官方核查报告。
- 新增 3 家 Coding Plan 插件前，先看 Coding Plan 对照文档。
- 如果代码实现和这两份文档冲突，以官方文档为准，同时更新本目录下的记录，不要把错实现硬说成“项目约定”。

## 2026-03-18 验证记录

- 已修正 builtin 默认配置对齐项：
  - `minimax` 改为 `native_sdk + anthropic_messages`
  - `doubao-coding` 切到 `/api/coding/v3`
  - `byteplus` / `byteplus-coding` 切到 `ark.ap-southeast.bytepluses.com`
- 已补齐流式调用：
  - `anthropic_messages` SSE
  - `gemini_generate_content` SSE
- 已新增官方插件：
  - `ai_provider_bailian_coding_plan`
  - `ai_provider_kimi_coding_plan`
  - `ai_provider_glm_coding_plan`
- 已收口插件目录：
- 历史官方插件手工挂载：`apps/api-server/data/plugins/official/...`，仅表示旧方案，当前已废弃
- 当前第三方开发源码目录：`apps/api-server/plugins-dev/...`
- 当前第三方本地安装目录：`apps/api-server/data/plugins/third_party/local/...`
- 当前插件市场安装目录：`apps/api-server/data/plugins/third_party/marketplace/...`
- 已补启动自动恢复：
  - 官方插件会在服务启动时自动发现并补齐到现有家庭挂载记录
  - 第三方手工插件会从 `data/plugins/third_party/manual/...` 恢复 `plugin_mounts`
  - 市场插件只恢复已安装实例，不会重跑下载安装流程
- 已补验证：
  - `python -m unittest tests.test_provider_runtime_async_stream`
  - `python -m unittest tests.test_ai_provider_official_plugins`
  - `python -m unittest tests.test_ai_config_center.AiConfigCenterTests.test_provider_adapter_registry_aligns_official_defaults`
  - `python -m py_compile` 覆盖本次改动的后端实现与测试文件
  - `python -m unittest tests.test_plugin_startup_sync`
  - `python -m unittest tests.test_plugin_mounts`
  - `python -m unittest tests.test_plugin_marketplace_service`
  - `python -m unittest tests.test_plugin_runs`
- 人工验收结论：
  - 官方插件挂载后，家庭维度 provider adapter 列表可以看到新增 Coding Plan 供应商
  - 未挂载时，后端会拒绝创建对应 provider profile
  - 旧 builtin provider 仍保留，和新官方插件路径可以共存
  - 新挂载和新安装的插件文件已经统一落到 `data/plugins`，后续 Docker 只需要把 `data/` 挂到外部
  - 服务重启后，只要 `data/plugins` 里的插件目录还在，挂载记录和市场已安装实例就会自动恢复
