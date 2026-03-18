# 设计文档 - AI供应商官方对齐与 Coding Plan 官方插件扩展

状态：Draft

## 1. 概述

### 1.1 目标

- 把现有 14 家内置供应商里已经确认的错误默认配置和缺失流式能力补齐。
- 新增百炼、Kimi、GLM 三家 Coding Plan 供应商，但不再走 builtin provider 扩写。
- 让新增供应商统一落在正式 `ai-provider` 插件体系里，服从插件启停、挂载和家庭可见性规则。
- 保证旧 provider profile 不被这次改造打坏。

### 1.2 覆盖需求

- `requirements.md` 需求 1
- `requirements.md` 需求 2
- `requirements.md` 需求 3
- `requirements.md` 需求 4
- `requirements.md` 需求 5
- `requirements.md` 需求 6

### 1.3 技术约束

- 当前插件系统已经正式支持 `ai-provider`，不能再假装这是未来能力。
- `ai-provider` 属于非执行型插件，新增插件必须以 manifest 能力描述为主，不靠额外执行入口撑起来。
- 新增 3 家 Coding Plan 必须通过 `plugin_mounts` 和 `source_type=official` 接入，不写回 builtin provider 注册表。
- 旧的 14 家内置供应商短期内继续保留 builtin / virtual manifest 方案，本次只修问题，不做整批迁移。

## 2. 架构

### 2.1 当前结构判断

现在的链路已经分成两半：

1. 插件系统层已经支持正式 `ai-provider`。
2. AI Gateway 也已经能消费插件化的 `ai-provider`。

真正没收口的地方不是“系统不支持插件”，而是“当前内置供应商还主要靠 virtual manifest 暴露出来”。所以这次最简单的正确做法是：

- 旧的 builtin 供应商继续按原链路修正；
- 新增的 3 家 Coding Plan 不再加入 builtin 注册表；
- 直接走正式官方插件。

### 2.2 模块职责

| 模块 | 职责 | 输入 | 输出 |
| --- | --- | --- | --- |
| `provider_adapter_registry.py` | 维护现有 14 家 builtin provider 的默认描述 | 代码内置配置 | builtin adapter 描述 |
| `plugin.service` | 发现 builtin / official / mounted 插件，并产出注册快照 | `manifest.json`、`plugin_mounts` | `PluginRegistrySnapshot` |
| `provider_config_service.py` | 从插件快照构建 `AiProviderAdapterRead` | `PluginRegistryItem[]` | 供应商适配器列表 |
| `ai_gateway.service.py` | 面向家庭列出可用供应商、创建配置、执行前校验 | 家庭上下文、插件快照、provider profile | 家庭可用 provider 能力 |
| `provider_runtime.py` | 执行真实 LLM 通讯 | provider profile、消息、流式参数 | 非流式或流式响应 |
| 新增 `ai-provider` 官方插件 manifest | 描述 3 家 Coding Plan 的字段、默认值、支持类型和协议信息 | 官方文档、OpenClaw 对照 | 可挂载的官方插件 |

### 2.3 关键流程

#### 2.3.1 修正现有 builtin 供应商

1. 以报告为基准，先修 `minimax`、`doubao-coding`、`byteplus`、`byteplus-coding`。
2. 保持当前 builtin provider 数据结构不变，只修默认 `base_url`、协议族、端点和请求实现。
3. 为 `claude`、`gemini` 增加真实流式调用实现。

#### 2.3.2 新增 Coding Plan 官方插件

1. 为每家新增供应商准备独立 `manifest.json`。
2. manifest 声明 `types=["ai-provider"]`，并提供 `capabilities.ai_provider`。
3. 通过官方插件目录和 `plugin_mounts` 以 `source_type=official` 暴露给家庭。
4. `provider_config_service.py` 通过现有 `list_provider_adapters_from_plugins(...)` 自动把它们转成 adapter 列表。
5. 家庭创建 provider profile 时，继续通过 `require_available_household_plugin(..., plugin_type="ai-provider")` 做执行前校验。

#### 2.3.3 运行时执行

1. 新插件只负责描述供应商，不负责运行逻辑分发。
2. 真正的 LLM 通讯仍由 `provider_runtime.py` 按协议族执行。
3. 新增 3 家 Coding Plan 需要各自映射到已经存在的协议实现：
   - 百炼 Coding Plan：OpenAI compatible
   - Kimi Coding Plan：Anthropic Messages
   - GLM Coding Plan：OpenAI compatible

#### 2.3.4 插件安装目录持久化收口

1. `settings.plugin_storage_root` 和 `settings.plugin_marketplace_install_root` 默认都指向 `BASE_DIR/data/plugins`。
2. `register_plugin_mount(...)` 在写入挂载记录前，先把不受管的插件目录复制到受管目录，再把数据库里的 `plugin_root`、`manifest_path`、`working_dir` 改成受管路径。
3. 目录布局统一为：
   - 官方插件手工挂载：`data/plugins/official/<plugin_dir_name>`
   - 第三方插件手工挂载：`data/plugins/third_party/manual/<household_id>/<plugin_id>`
   - 插件市场安装：`data/plugins/<trusted_level>/marketplace/<household_id>/<plugin_id>/<version>`
4. 这轮先收口新挂载和新安装，不偷偷迁移历史数据库记录，避免读操作带副作用。

#### 2.3.5 启动自动恢复挂载和安装实例

1. 在 `app.main` 的启动阶段增加一次同步，把 `data/plugins` 里的真实目录重新对齐到数据库。
2. 官方插件：
   - 扫描 `data/plugins/official/*/manifest.json`
   - 对现有每个家庭补齐或更新 `plugin_mounts`
   - 官方来源受控，允许按“所有家庭都可用”的方式自动补齐
3. 第三方手工插件：
   - 扫描 `data/plugins/third_party/manual/<household_id>/<plugin_id>/manifest.json`
   - 目录层级必须能反推出 `household_id` 和 `plugin_id`
   - 只恢复或补齐 `plugin_mounts`，已有 `enabled` 不改，新补记录默认保持保守状态
4. 市场插件：
   - 扫描 `data/plugins/<trusted_level>/marketplace/<household_id>/<plugin_id>/<version>/manifest.json`
   - 只恢复已安装实例和对应挂载，不调用下载、解压、checksum 校验这些安装步骤
   - 如果 `source_id` 无法从现有 source / snapshot / install task 唯一反推，就记日志跳过，不猜
5. 整个恢复流程只做“把磁盘状态同步回数据库”，不负责偷偷启用第三方插件，也不把恢复和安装混成同一条链路。

## 3. 组件和接口

### 3.1 现有 builtin 修复范围

| 供应商 | 当前判断 | 本次动作 |
| --- | --- | --- |
| `claude` | 非流式已接通，流式缺实现 | 补真实流式 |
| `gemini` | 非流式已接通，流式缺实现 | 补真实流式 |
| `minimax` | 默认配置与官方文档存在高风险偏差 | 修正默认地址和调用约束 |
| `doubao-coding` | 当前接法与官方 Coding 场景不够对齐 | 修正默认地址、说明和请求链路 |
| `byteplus` | 当前默认值和 ModelArk 官方接法存在偏差 | 修正默认地址和协议映射 |
| `byteplus-coding` | 当前默认值和官方 Coding 接法存在偏差 | 修正默认地址、说明和请求链路 |
| 其他 8 家 | 非流式主链路无空实现 | 本次不做结构迁移，只保留回归验证 |

### 3.2 新增官方插件清单

建议新增 3 个官方 `ai-provider` 插件：

| 插件 ID | adapter_code | 展示名称 | 协议族 | 默认站点 |
| --- | --- | --- | --- | --- |
| `ai-provider-bailian-coding-plan` | `bailian-coding-plan` | 百炼 Coding Plan | `openai-compatible` | 中国站 / 国际站 |
| `ai-provider-kimi-coding-plan` | `kimi-coding-plan` | Kimi Coding Plan | `anthropic-messages` | 独立 Coding 端点 |
| `ai-provider-glm-coding-plan` | `glm-coding-plan` | GLM Coding Plan | `openai-compatible` | 中国站 / 国际站 |

### 3.3 manifest 结构约束

每个新增插件都必须至少包含这些信息：

- `id`
- `name`
- `version`
- `types=["ai-provider"]`
- `capabilities.ai_provider.adapter_code`
- `capabilities.ai_provider.supported_model_types`
- `capabilities.ai_provider.llm_workflow`
- `capabilities.ai_provider.field_schema`

这些插件不需要执行入口，不需要 runner。它们本质上是供应商能力描述，不是执行型插件。

### 3.4 字段设计

3 家新增插件的表单字段保持一套共同骨架，再按官方文档加差异项。

共同字段：

- `display_name`
- `model_name`
- `api_key`
- `base_url`
- `region`
- `temperature`
- `max_tokens`
- `timeout_seconds`

供应商差异：

- 百炼 Coding Plan
  - 提供中国站和国际站两个 `base_url`
  - 文案明确这是 Coding Plan 专用地址，不是普通 DashScope 通用地址
- Kimi Coding Plan
  - 提供独立 Coding 端点
  - 文案明确需要独立 API Key，不能和普通 Moonshot / Kimi Key 混用
  - `llm_workflow` 标记为 `anthropic-messages`
- GLM Coding Plan
  - 提供 `api.z.ai` 国际站和 `open.bigmodel.cn` 中国站
  - 文案明确这是 Coding Plan 专用地址，不是普通 GLM 通用聊天接口

### 3.5 官方资料对照基线

这次新增 3 家的默认值按下面的基线来：

| 供应商 | 官方 / OpenClaw 基线 |
| --- | --- |
| 百炼 Coding Plan | `https://coding.dashscope.aliyuncs.com/v1`、`https://coding-intl.dashscope.aliyuncs.com/v1` |
| Kimi Coding Plan | `https://api.kimi.com/coding/`，独立 Coding API Key，协议走 Anthropic Messages |
| GLM Coding Plan | `https://open.bigmodel.cn/api/coding/paas/v4`、`https://api.z.ai/api/coding/paas/v4` |

证据和链接统一放在 `docs/20260317-Coding Plan供应商官方资料与OpenClaw对照.md`。

## 4. 数据与状态模型

### 4.1 数据关系

这次最关键的数据关系很简单：

1. `manifest.json` 描述“这个供应商插件是什么”。
2. `plugin_mounts` 描述“这个家庭能不能看到它”。
3. `provider profile` 描述“这个家庭实际配了哪个模型和密钥”。
4. `provider_runtime` 描述“实际请求怎么发出去”。

这四层不能再混成一坨。

补一条和持久化有关的边界：

5. `data/plugins` 描述“插件源码最终落在哪个持久化目录里”，它服务的是插件挂载和市场安装，不直接参与 AI 配置语义。

### 4.2 状态流转

| 状态 | 含义 | 进入条件 | 退出条件 |
| --- | --- | --- | --- |
| `registered` | 插件 manifest 已被系统发现 | 官方插件已落盘并可被发现 | 被挂载到家庭或被移除 |
| `mounted` | 插件已挂载到某家庭 | 写入 `plugin_mounts` 且状态有效 | 被禁用、卸载或挂载失效 |
| `configured` | 家庭已创建 provider profile | 创建成功 | 被删除或失效 |
| `runnable` | 运行前校验通过，可以实际发请求 | 插件可用且 provider profile 合法 | 插件不可用或配置失效 |

## 5. 错误处理

### 5.1 错误类型

- 官方插件 manifest 缺字段或字段不合法。
- 家庭没有挂载对应 `ai-provider` 官方插件。
- provider profile 指向了不可用插件。
- 外部供应商流式或非流式接口返回错误。

### 5.2 处理策略

1. manifest 错误
   - 发现层记录错误并阻止该插件进入可用列表。
2. 家庭未挂载或插件不可用
   - 创建、更新和执行前统一报业务错误，不绕过校验。
3. 外部供应商错误
   - 维持真实错误语义，不伪装成成功或空实现。

## 6. 正确性约束

### 6.1 新增 Coding Plan 供应商不能回流 builtin

对于本次新增的百炼、Kimi、GLM Coding Plan，系统都必须通过正式插件 manifest 和挂载链路接入，不能再把它们写回 `provider_adapter_registry.py` 的 builtin 列表。

**验证需求：** `requirements.md` 需求 3、需求 5

### 6.2 旧配置必须继续可读

对于任何已经存在的 builtin provider profile，系统都必须继续允许读取、展示和更新，不能因为引入新插件而把旧配置判成非法。

**验证需求：** `requirements.md` 需求 6

### 6.3 流式能力必须是真实现

对于 `claude` 和 `gemini`，系统都必须提供真实流式路径；不允许“配置里显示支持，但运行时没有实现”。

**验证需求：** `requirements.md` 需求 2

## 7. 测试策略

### 7.1 单元测试

- 覆盖 `claude` 和 `gemini` 流式调用分支。
- 覆盖 `minimax`、`doubao-coding`、`byteplus`、`byteplus-coding` 默认配置解析。
- 覆盖 3 个 Coding Plan 官方插件 manifest 的 schema 校验。

### 7.2 集成测试

- 覆盖插件注册快照到 `AiProviderAdapterRead` 的转换。
- 覆盖家庭已挂载 / 未挂载官方插件时的 provider profile 创建与执行校验。
- 覆盖新增 3 家 Coding Plan 的 adapter 列表可见性。

### 7.3 人工验收

- 为某个家庭挂载百炼、Kimi、GLM 三家官方 `ai-provider` 插件。
- 确认供应商列表能看到这 3 家，且字段、说明和默认地址正确。
- 分别创建 3 家的 provider profile，确认创建成功。
- 调用非流式与需要覆盖的流式链路，确认没有落回空实现。

### 7.4 验证映射

| 需求 | 设计章节 | 验证方式 |
| --- | --- | --- |
| `requirements.md` 需求 1 | `design.md` 2.3.1、3.1 | 后端单元测试 + 人工核对默认值 |
| `requirements.md` 需求 2 | `design.md` 2.3.1、6.3 | 流式单元测试 / 集成测试 |
| `requirements.md` 需求 3 | `design.md` 2.3.2、3.2、6.1 | 插件清单检查 + 集成测试 |
| `requirements.md` 需求 4 | `design.md` 3.4、3.5 | manifest 检查 + 人工验收 |
| `requirements.md` 需求 5 | `design.md` 2.3.2、4.2、5.2 | 集成测试 |
| `requirements.md` 需求 6 | `design.md` 4.1、6.2 | 回归测试 |

## 8. 风险与待确认项

### 8.1 风险

- 当前内置供应商既有 builtin 描述，又有 virtual manifest，改错时很容易只修一半。
- `ai-provider` 插件虽然是正式类型，但现有官方插件目录和挂载样例还不多，第一批实现容易把目录结构写散。
- Kimi Coding Plan 走 Anthropic Messages，不和项目里大多数 OpenAI compatible 供应商同路，最容易被误接。

### 8.2 待确认项

- 3 家 Coding Plan 官方插件是否需要在本次同时补充用户侧展示文案和图标资源。
- 是否要为百炼 / GLM 的中国站与国际站拆成两个插件，还是单插件加 `region/base_url` 选项。
- 现有 builtin provider 的长期归宿是否要在后续 Spec 中继续迁到正式插件体系。
