# 设计文档 - AI 供应商彻底插件化迁移

状态：In Progress

## 1. 最终结构

迁移完成后的结构固定为两层：

1. 宿主层
   - `app/modules/ai_gateway/*`
   - `app/modules/plugin/*`
   - 负责统一网关、路由、权限、审计、密钥、插件状态、错误语义和结果收口
2. `ai-provider` 插件层
   - `app/plugins/builtin/ai_provider_*/`
   - 负责供应商声明、品牌资源、字段 schema、配置 UI、模型发现声明、协议适配、流式输出和厂商特例

## 2. 当前代码落点

### 2.1 宿主侧

- `apps/api-server/app/modules/ai_gateway/provider_driver.py`
  - 定义并加载 provider driver contract
- `apps/api-server/app/modules/ai_gateway/provider_config_service.py`
  - 通过统一插件注册结果列出 provider adapter，并只做通用宿主整形
- `apps/api-server/app/modules/ai_gateway/provider_runtime.py`
  - 当前仍保留协议族运行时桥接；后续要继续评估哪些属于稳定宿主能力，哪些必须继续下沉
- `apps/api-server/app/modules/ai_gateway/service.py`
  - 只做宿主层配置处理，不再写供应商默认值特例
- `apps/api-server/app/modules/plugin/service.py`
  - 只维护统一插件注册表，不再虚拟生成 `ai-provider`

### 2.2 插件侧

- `apps/api-server/app/plugins/builtin/ai_provider_*/manifest.json`
  - 每个 builtin 供应商都有真实 manifest
- `apps/api-server/app/plugins/_ai_provider_runtime_helpers.py`
  - 提供插件侧 runtime helper
- `apps/api-server/app/plugins/builtin/ai_provider_siliconflow/driver.py`
  - 处理 SiliconFlow thinking 默认值和 token ceiling
- `apps/api-server/app/plugins/builtin/ai_provider_openrouter/driver.py`
  - 处理 OpenRouter 专用 header 映射

### 2.3 已删除的旧核心实现

- `apps/api-server/app/modules/ai_gateway/provider_adapter_registry.py`

它不再作为兼容桥保留，而是已经从核心移除。

## 3. provider driver contract

宿主只依赖一个稳定接口：

- `invoke(...)`
- `ainvoke(...)`
- `stream(...)`

接口定义位于：

- `apps/api-server/app/modules/ai_gateway/provider_driver.py`

宿主的使用方式：

1. 从插件注册表找到目标 `ai-provider` 插件
2. 读取 `entrypoints.ai_provider`
3. 加载 driver builder
4. 调用 `invoke / ainvoke / stream`

宿主不再关心：

- 某家供应商的专有 header
- 某家供应商的 thinking 默认值
- 某家供应商的 chunk 格式细节
- 某家供应商的模型名特判

## 4. manifest 规则

每个 `ai-provider` 插件现在都必须提供：

- `types: ["ai-provider"]`
- `entrypoints.ai_provider`
- `capabilities.ai_provider.adapter_code`
- `capabilities.ai_provider.display_name`
- `capabilities.ai_provider.branding`
- `capabilities.ai_provider.field_schema`
- `capabilities.ai_provider.config_ui`
- `capabilities.ai_provider.model_discovery`
- `capabilities.ai_provider.supported_model_types`
- `capabilities.ai_provider.llm_workflow`
- `capabilities.ai_provider.runtime_capability`

这意味着：

- `ai-provider` 不再是“只有静态元数据”的特殊类型
- builtin AI 供应商必须有真实 manifest
- 不再允许虚拟 ai-provider manifest
- 不再允许核心前端通过 `adapter_code` 自己猜 Logo、说明文案、字段动作和模型发现行为

## 5. 宿主和插件边界

### 必须保留在宿主的部分

- AI Gateway 统一入口
- provider profile 选择与 fallback
- household 可见性和插件启停校验
- 密钥读取和保护
- 审计、权限、统一错误语义
- 通用协议能力抽象与调用收口

### 必须迁到插件的部分

- 供应商声明
- Logo、说明文案和其他品牌资源
- 字段 schema
- config_ui
- model_discovery
- 请求 body/header 的厂商差异
- 流式输出格式适配
- 供应商默认值和特殊上限
- 厂商诊断信息

## 6. 旧方案怎么处理

旧 spec 现在只保留历史背景，不再定义当前边界。

处理规则：

- 主规则只写在 `004.8.1`
- 旧 spec 顶部明确说明“这是历史背景”
- dated report 可以保留旧文件名和旧现状，但不能再被当成当前实现说明

## 7. 验收设计

代码层面必须能证明下面几件事：

1. `provider_adapter_registry.py` 已删除
2. builtin AI 供应商通过真实 manifest 暴露
3. 宿主通过 provider driver 调用插件
4. 核心前端目录里没有新的 `adapter_code -> logo/description/form behavior` 映射
5. `ai-provider` manifest 已声明 branding、config_ui、model_discovery
6. 开发者文档和主 spec 口径一致
