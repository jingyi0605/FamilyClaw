# 20260317-Coding Plan供应商官方资料与OpenClaw对照

## 1. 这份文档干什么

这份文档只回答一个问题：新增百炼、Kimi、GLM 这 3 家 Coding Plan 供应商时，默认接法到底该按什么来。

别再猜。这里直接拿三类证据对照：

1. 官方文档怎么写。
2. OpenClaw 现在怎么实现。
3. 我们这次应该怎么落地成官方 `ai-provider` 插件。

## 2. 先给结论

### 【核心判断】

✅ 值得做，而且必须按官方插件做。

原因很简单：

- 这 3 家都不是“再加一个普通 OpenAI 兼容地址”这么简单。
- 它们都带有明显的 Coding / Plan 专用端点或独立鉴权约束。
- OpenClaw 已经把它们和普通供应商分开处理了，我们继续塞进 builtin provider 只是倒退。

### 【关键洞察】

- 数据结构：这 3 家应该是独立 `ai-provider` 插件，而不是旧供应商上的几个可选地址。
- 复杂度：真正要做的是新增 3 个 manifest，不是往 builtin 注册表里继续堆分支。
- 风险点：Kimi Coding Plan 最容易接错，因为它不是普通 Moonshot OpenAI 兼容接口，而是独立 Coding 端点。

## 3. 百炼 Coding Plan

### 3.1 官方资料

- 中文文档：[阿里云百炼 Coding Plan 专属 API Key 和 Base URL](https://help.aliyun.com/zh/model-studio/get-api-key-and-url-for-model-studio-coding-plan)
- 国际文档：[Alibaba Cloud Model Studio Coding Plan](https://www.alibabacloud.com/help/en/model-studio/get-api-key-and-url-for-model-studio-coding-plan)

### 3.2 OpenClaw 证据

- `apps/api-server/data/openclaw-main/src/commands/onboard-auth.models.ts`
  - `MODELSTUDIO_CN_BASE_URL = "https://coding.dashscope.aliyuncs.com/v1"`
  - `MODELSTUDIO_GLOBAL_BASE_URL = "https://coding-intl.dashscope.aliyuncs.com/v1"`
- `apps/api-server/data/openclaw-main/src/commands/auth-choice.apply.api-providers.ts`
  - 明确把它当成 `Alibaba Cloud Model Studio Coding Plan`
  - 分中国站和国际站两套入口

### 3.3 本次落地结论

- 插件 ID：建议 `ai-provider-bailian-coding-plan`
- `adapter_code`：建议 `bailian-coding-plan`
- 协议族：`openai-compatible`
- 默认 `base_url`：
  - 中国站：`https://coding.dashscope.aliyuncs.com/v1`
  - 国际站：`https://coding-intl.dashscope.aliyuncs.com/v1`
- 表单至少要有：
  - `api_key`
  - `region`
  - `base_url`
  - `model_name`

### 3.4 关键提醒

- 这是 Coding Plan 专用地址，不要和普通 DashScope 通用模型地址混用。
- 这类差异正适合放进独立插件 manifest，而不是藏在一个通用 provider 的备注字段里。

## 4. Kimi Coding Plan

### 4.1 官方资料

- 官方站点：[Kimi Code](https://www.kimi.com/code/en)
- 官方文档入口：[Moonshot AI Third-party Agents Guide](https://platform.moonshot.ai/docs/guide/third-party-agents)

### 4.2 OpenClaw 证据

- `apps/api-server/data/openclaw-main/src/agents/models-config.providers.static.ts`
  - `KIMI_CODING_BASE_URL = "https://api.kimi.com/coding/"`
- `apps/api-server/data/openclaw-main/src/commands/auth-choice.apply.api-providers.ts`
  - 明确写了 `Kimi Coding uses a dedicated endpoint and API key.`
- `apps/api-server/data/openclaw-main/docs/providers/moonshot.md`
  - 明确写了 Moonshot 和 Kimi Coding 是两套独立 provider
  - key 不通用，端点不同，模型引用前缀不同

### 4.3 本次落地结论

- 插件 ID：建议 `ai-provider-kimi-coding-plan`
- `adapter_code`：建议 `kimi-coding-plan`
- 协议族：`anthropic-messages`
- 默认 `base_url`：`https://api.kimi.com/coding`
- 兼容备选地址：`https://api.moonshot.cn/anthropic`
- 表单至少要有：
  - `api_key`
  - `base_url`
  - `model_name`

### 4.4 关键提醒

- 不要把它当成普通 Moonshot / Kimi OpenAI 兼容接口。
- 不要复用普通 Moonshot 的 API Key。
- 这家如果接错协议族，后面所有请求细节都会跟着错。

## 5. GLM Coding Plan

### 5.1 官方资料

- 国际文档：[Z.ai API Reference](https://docs.z.ai/api-reference/introduction)
- 国内文档：[智谱 BigModel 开放平台](https://docs.bigmodel.cn/)

### 5.2 OpenClaw 证据

- `apps/api-server/data/openclaw-main/src/commands/onboard-auth.models.ts`
  - `ZAI_CODING_GLOBAL_BASE_URL = "https://api.z.ai/api/coding/paas/v4"`
  - `ZAI_CODING_CN_BASE_URL = "https://open.bigmodel.cn/api/coding/paas/v4"`
- `apps/api-server/data/openclaw-main/src/commands/auth-choice.apply.api-providers.ts`
  - 明确提供 `GLM Coding Plan Global (api.z.ai)` 和 `GLM Coding Plan CN (open.bigmodel.cn)` 两套提示

### 5.3 本次落地结论

- 插件 ID：建议 `ai-provider-glm-coding-plan`
- `adapter_code`：建议 `glm-coding-plan`
- 协议族：`openai-compatible`
- 默认 `base_url`：
  - 中国站：`https://open.bigmodel.cn/api/coding/paas/v4`
  - 国际站：`https://api.z.ai/api/coding/paas/v4`
- 表单至少要有：
  - `api_key`
  - `region`
  - `base_url`
  - `model_name`

### 5.4 关键提醒

- 这也是 Coding Plan 专用地址，不是普通 GLM 聊天接口地址。
- 建议单插件加站点选项，不建议拆成两套完全重复的插件，除非后面业务明确要求不同启停策略。

## 6. 统一落地规则

这 3 家新增供应商统一按下面的规则实现：

1. 用正式 `ai-provider` 插件 manifest 描述供应商，不写回 builtin provider 注册表。
2. 通过 `plugin_mounts` 挂到家庭上，`source_type=official`。
3. `provider_config_service.py` 继续通过插件快照生成 `AiProviderAdapterRead`。
4. 创建、更新和执行前统一走家庭插件可用性校验。

### 6.1 2026-03-21 实施补充

这次把 3 个 `plugins-dev` Coding Plan 插件重新收口时，额外加了两条硬规则：

1. `plugins-dev` 插件自己的 `manifest.json` 和 `driver.py` 必须自包含，不能再把入口指回 `app.plugins.builtin.*`。
2. 加快回复速度的策略也必须留在插件里做，不准回到核心补分支。

具体做法：

- 百炼 Coding Plan：对 Qwen3 / QwQ 族模型在插件里下发 `enable_thinking=false`，并对快任务缩短历史消息和输出上限。
- GLM Coding Plan：对 `glm-4.5+ / glm-5` 在插件里下发 `thinking={"type":"disabled"}`，并对快任务缩短历史消息和输出上限。
- Kimi Coding Plan：官方文档没有给出统一的“关 think”请求字段，所以不瞎编参数，只把默认模型收口到 `kimi-for-coding`，并在插件里裁剪快任务上下文与输出长度。

## 7. 最终建议

按实现顺序，建议先做：

1. 百炼 Coding Plan
2. Kimi Coding Plan
3. GLM Coding Plan

原因：

- 百炼和 GLM 都是 OpenAI compatible，先把官方插件路径打通最稳。
- Kimi Coding Plan 走 Anthropic Messages，协议差异最大，放在第二步或第三步都行，但实现时必须单独盯紧。
