import { useEffect, useMemo, useState } from "react";

import { PageSection } from "../components/PageSection";
import { StatusMessage } from "../components/StatusMessage";
import { api } from "../lib/api";
import { useHousehold } from "../state/household";
import type {
  AiCapabilityRoute,
  AiCapabilityRouteUpsertPayload,
  AiCallLog,
  AiGatewayInvokeResponse,
  AiProviderProfile,
  AiProviderProfileCreatePayload,
} from "../types";

const capabilityOptions = [
  "qa_generation",
  "qa_structured_answer",
  "reminder_copywriting",
  "scene_explanation",
  "embedding",
  "rerank",
  "stt",
  "tts",
  "vision",
];

const routingModeOptions = [
  "template_only",
  "primary_then_fallback",
  "local_only",
  "local_preferred_then_cloud",
];

const capabilityLabels: Record<string, string> = {
  qa_generation: "家庭问答生成",
  qa_structured_answer: "结构化问答",
  reminder_copywriting: "提醒文案润色",
  scene_explanation: "场景解释",
  embedding: "向量嵌入",
  rerank: "结果重排",
  stt: "语音转文字",
  tts: "文字转语音",
  vision: "图像理解",
};

const routingModeLabels: Record<string, string> = {
  template_only: "仅模板回答",
  primary_then_fallback: "主供应商失败后切备",
  local_only: "只允许本地模型",
  local_preferred_then_cloud: "本地优先，必要时再走云端",
};

const transportTypeLabels: Record<string, string> = {
  openai_compatible: "OpenAI兼容接口",
  native_sdk: "原生接入",
  local_gateway: "本地模型网关",
};

const privacyLevelLabels: Record<string, string> = {
  local_only: "仅本地",
  private_cloud: "私有云",
  public_cloud: "公有云",
};

const callStatusLabels: Record<string, string> = {
  success: "成功",
  fallback_success: "降级成功",
  blocked: "被策略阻断",
  failed: "失败",
  timeout: "超时",
  rate_limited: "被限流",
  validation_error: "输出校验失败",
};

function getErrorMessage(error: unknown) {
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }
  return "未知错误";
}

function formatDateTime(value: string | null | undefined) {
  if (!value) {
    return "暂无";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function stringifyJson(value: unknown) {
  return JSON.stringify(value ?? {}, null, 2);
}

function formatCapability(value: string) {
  return capabilityLabels[value] ?? value;
}

function formatRoutingMode(value: string) {
  return routingModeLabels[value] ?? value;
}

function formatTransportType(value: string) {
  return transportTypeLabels[value] ?? value;
}

function formatPrivacyLevel(value: string) {
  return privacyLevelLabels[value] ?? value;
}

function formatCallStatus(value: string) {
  return callStatusLabels[value] ?? value;
}

export function AiProviderConfigPage() {
  const { household } = useHousehold();
  const householdId = household?.id ?? "";

  const [providers, setProviders] = useState<AiProviderProfile[]>([]);
  const [routes, setRoutes] = useState<AiCapabilityRoute[]>([]);
  const [callLogs, setCallLogs] = useState<AiCallLog[]>([]);
  const [message, setMessage] = useState<{ tone: "info" | "success" | "error"; text: string } | null>(null);
  const [selectedProviderId, setSelectedProviderId] = useState("");
  const [selectedCapability, setSelectedCapability] = useState("qa_generation");
  const [providerForm, setProviderForm] = useState<AiProviderProfileCreatePayload>({
    provider_code: "",
    display_name: "",
    transport_type: "openai_compatible",
    base_url: "",
    api_version: "",
    secret_ref: "",
    enabled: true,
    supported_capabilities: ["qa_generation"],
    privacy_level: "public_cloud",
    latency_budget_ms: 15000,
    cost_policy: {},
    extra_config: {},
  });
  const [routeForm, setRouteForm] = useState<AiCapabilityRouteUpsertPayload>({
    capability: "qa_generation",
    household_id: householdId || null,
    primary_provider_profile_id: null,
    fallback_provider_profile_ids: [],
    routing_mode: "primary_then_fallback",
    timeout_ms: 15000,
    max_retry_count: 1,
    allow_remote: true,
    prompt_policy: {},
    response_policy: { template_fallback_enabled: true },
    enabled: true,
  });
  const [fallbackProviderText, setFallbackProviderText] = useState("");
  const [previewPayloadText, setPreviewPayloadText] = useState(stringifyJson({ question: "爷爷今天吃药了吗？" }));
  const [previewResult, setPreviewResult] = useState<AiGatewayInvokeResponse | null>(null);

  async function refreshData() {
    const [providerResponse, routeResponse, callLogResponse] = await Promise.all([
      api.listAiProviders(),
      api.listAiRoutes(householdId || undefined),
      api.listAiCallLogs(householdId || undefined),
    ]);
    setProviders(providerResponse);
    setRoutes(routeResponse);
    setCallLogs(callLogResponse);
  }

  useEffect(() => {
    refreshData().catch((error) => {
      setMessage({ tone: "error", text: getErrorMessage(error) });
    });
  }, [householdId]);

  useEffect(() => {
    setRouteForm((current) => ({
      ...current,
      household_id: householdId || null,
    }));
  }, [householdId]);

  const selectedProvider = useMemo(
    () => providers.find((item) => item.id === selectedProviderId) ?? null,
    [providers, selectedProviderId],
  );

  const selectedRoute = useMemo(
    () => routes.find((item) => item.capability === selectedCapability) ?? null,
    [routes, selectedCapability],
  );

  async function handleCreateProvider() {
    try {
      await api.createAiProvider({
        ...providerForm,
        base_url: providerForm.base_url || null,
        api_version: providerForm.api_version || null,
        secret_ref: providerForm.secret_ref || null,
        latency_budget_ms: providerForm.latency_budget_ms ?? null,
      });
      setMessage({ tone: "success", text: "AI 供应商已创建。" });
      await refreshData();
      setProviderForm({
        ...providerForm,
        provider_code: "",
        display_name: "",
        secret_ref: "",
      });
    } catch (error) {
      setMessage({ tone: "error", text: getErrorMessage(error) });
    }
  }

  async function handleLoadProviderForEdit(provider: AiProviderProfile) {
    setSelectedProviderId(provider.id);
    setProviderForm({
      provider_code: provider.provider_code,
      display_name: provider.display_name,
      transport_type: provider.transport_type,
      base_url: provider.base_url ?? "",
      api_version: provider.api_version ?? "",
      secret_ref: provider.secret_ref ?? "",
      enabled: provider.enabled,
      supported_capabilities: provider.supported_capabilities,
      privacy_level: provider.privacy_level,
      latency_budget_ms: provider.latency_budget_ms,
      cost_policy: provider.cost_policy,
      extra_config: provider.extra_config,
    });
  }

  async function handleUpdateProvider() {
    if (!selectedProvider) {
      setMessage({ tone: "error", text: "先从右侧列表里选择一个供应商。" });
      return;
    }
    try {
      await api.updateAiProvider(selectedProvider.id, {
        display_name: providerForm.display_name,
        transport_type: providerForm.transport_type,
        base_url: providerForm.base_url || null,
        api_version: providerForm.api_version || null,
        secret_ref: providerForm.secret_ref || null,
        enabled: providerForm.enabled,
        supported_capabilities: providerForm.supported_capabilities,
        privacy_level: providerForm.privacy_level,
        latency_budget_ms: providerForm.latency_budget_ms ?? null,
        cost_policy: providerForm.cost_policy,
        extra_config: providerForm.extra_config,
      });
      setMessage({ tone: "success", text: "AI 供应商已更新。" });
      await refreshData();
    } catch (error) {
      setMessage({ tone: "error", text: getErrorMessage(error) });
    }
  }

  function loadRouteForEdit(route: AiCapabilityRoute) {
    setSelectedCapability(route.capability);
    setRouteForm({
      capability: route.capability,
      household_id: route.household_id,
      primary_provider_profile_id: route.primary_provider_profile_id,
      fallback_provider_profile_ids: route.fallback_provider_profile_ids,
      routing_mode: route.routing_mode,
      timeout_ms: route.timeout_ms,
      max_retry_count: route.max_retry_count,
      allow_remote: route.allow_remote,
      prompt_policy: route.prompt_policy,
      response_policy: route.response_policy,
      enabled: route.enabled,
    });
    setFallbackProviderText(route.fallback_provider_profile_ids.join(","));
  }

  async function handleSaveRoute() {
    try {
      await api.upsertAiRoute(routeForm.capability, {
        ...routeForm,
        household_id: routeForm.household_id || null,
        primary_provider_profile_id: routeForm.primary_provider_profile_id || null,
        fallback_provider_profile_ids: fallbackProviderText
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean),
      });
      setMessage({ tone: "success", text: `能力路由“${formatCapability(routeForm.capability)}”已保存。` });
      await refreshData();
    } catch (error) {
      setMessage({ tone: "error", text: getErrorMessage(error) });
    }
  }

  async function handleInvokePreview() {
    try {
      const parsedPayload = JSON.parse(previewPayloadText) as Record<string, unknown>;
      const result = await api.invokeAiPreview({
        capability: routeForm.capability,
        household_id: householdId || null,
        payload: parsedPayload,
      });
      setPreviewResult(result);
      setMessage({ tone: "success", text: "预览调用完成。" });
      await refreshData();
    } catch (error) {
      setMessage({ tone: "error", text: getErrorMessage(error) });
    }
  }

  return (
    <div className="page-grid">
      {message ? <StatusMessage tone={message.tone} message={message.text} /> : null}

      <PageSection
        title="AI 供应商配置"
        description="这里就是给你手工配模型的，不讲虚的。先配供应商，再配能力路由。"
      >
        <div className="service-grid">
          <div className="service-card">
            <h4>{selectedProvider ? "编辑供应商" : "新增供应商"}</h4>
            <label>
              供应商编码
              <input
                value={providerForm.provider_code}
                onChange={(event) =>
                  setProviderForm((current) => ({ ...current, provider_code: event.target.value }))
                }
                disabled={Boolean(selectedProvider)}
              />
            </label>
            <label>
              展示名称
              <input
                value={providerForm.display_name}
                onChange={(event) =>
                  setProviderForm((current) => ({ ...current, display_name: event.target.value }))
                }
              />
            </label>
            <label>
              接入方式
              <select
                value={providerForm.transport_type}
                onChange={(event) =>
                  setProviderForm((current) => ({
                    ...current,
                    transport_type: event.target.value as AiProviderProfileCreatePayload["transport_type"],
                  }))
                }
              >
                <option value="openai_compatible">{formatTransportType("openai_compatible")}</option>
                <option value="native_sdk">{formatTransportType("native_sdk")}</option>
                <option value="local_gateway">{formatTransportType("local_gateway")}</option>
              </select>
            </label>
            <label>
              接口地址
              <input
                value={providerForm.base_url ?? ""}
                onChange={(event) =>
                  setProviderForm((current) => ({ ...current, base_url: event.target.value }))
                }
              />
            </label>
            <label>
              接口版本
              <input
                value={providerForm.api_version ?? ""}
                onChange={(event) =>
                  setProviderForm((current) => ({ ...current, api_version: event.target.value }))
                }
              />
            </label>
            <label>
              密钥引用
              <input
                value={providerForm.secret_ref ?? ""}
                onChange={(event) =>
                  setProviderForm((current) => ({ ...current, secret_ref: event.target.value }))
                }
                placeholder="可填 env://环境变量名，测试时也兼容直接填真实密钥"
              />
            </label>
            <label>
              隐私级别
              <select
                value={providerForm.privacy_level}
                onChange={(event) =>
                  setProviderForm((current) => ({
                    ...current,
                    privacy_level: event.target.value as AiProviderProfileCreatePayload["privacy_level"],
                  }))
                }
              >
                <option value="local_only">{formatPrivacyLevel("local_only")}</option>
                <option value="private_cloud">{formatPrivacyLevel("private_cloud")}</option>
                <option value="public_cloud">{formatPrivacyLevel("public_cloud")}</option>
              </select>
            </label>
            <label>
              支持能力（用逗号分隔编码）
              <input
                value={providerForm.supported_capabilities.join(",")}
                onChange={(event) =>
                  setProviderForm((current) => ({
                    ...current,
                    supported_capabilities: event.target.value
                      .split(",")
                      .map((item) => item.trim())
                      .filter(Boolean),
                  }))
                }
              />
            </label>
            <label>
              延迟预算（毫秒）
              <input
                type="number"
                value={providerForm.latency_budget_ms ?? 15000}
                onChange={(event) =>
                  setProviderForm((current) => ({
                    ...current,
                    latency_budget_ms: Number(event.target.value),
                  }))
                }
              />
            </label>
            <label>
              扩展配置（JSON）
              <textarea
                rows={6}
                value={stringifyJson(providerForm.extra_config)}
                onChange={(event) => {
                  try {
                    const parsed = JSON.parse(event.target.value) as Record<string, unknown>;
                    setProviderForm((current) => ({ ...current, extra_config: parsed }));
                  } catch {
                    setProviderForm((current) => ({ ...current }));
                  }
                }}
              />
            </label>
            <label>
              <input
                type="checkbox"
                checked={providerForm.enabled}
                onChange={(event) =>
                  setProviderForm((current) => ({ ...current, enabled: event.target.checked }))
                }
              />
              启用这个供应商
            </label>
            <div className="button-row">
              <button type="button" onClick={() => handleCreateProvider()}>
                新增供应商
              </button>
              <button type="button" className="ghost" onClick={() => handleUpdateProvider()}>
                更新当前供应商
              </button>
            </div>
          </div>

          <div className="service-card">
            <h4>现有供应商</h4>
            <div className="stack-list">
              {providers.map((provider) => (
                <article key={provider.id} className="stack-item">
                  <strong>{provider.display_name}</strong>
                  <p className="muted">
                    {provider.provider_code} · {formatTransportType(provider.transport_type)} · {formatPrivacyLevel(provider.privacy_level)}
                  </p>
                  <p className="muted">
                    {provider.enabled ? "已启用" : "已禁用"} · 最近更新 {formatDateTime(provider.updated_at)}
                  </p>
                  <div className="button-row">
                    <button type="button" className="ghost" onClick={() => handleLoadProviderForEdit(provider)}>
                      载入编辑
                    </button>
                  </div>
                </article>
              ))}
            </div>
          </div>
        </div>
      </PageSection>

      <PageSection
        title="能力路由配置"
        description="按能力配置，不允许业务代码自己到处写供应商分支。"
      >
        <div className="service-grid">
          <div className="service-card">
            <label>
              能力类型
              <select
                value={routeForm.capability}
                onChange={(event) =>
                  setRouteForm((current) => ({
                    ...current,
                    capability: event.target.value,
                  }))
                }
              >
                {capabilityOptions.map((item) => (
                  <option key={item} value={item}>
                    {formatCapability(item)}
                  </option>
                ))}
              </select>
            </label>
            <label>
              生效范围
              <select
                value={routeForm.household_id ?? ""}
                onChange={(event) =>
                  setRouteForm((current) => ({
                    ...current,
                    household_id: event.target.value || null,
                  }))
                }
              >
                <option value="">全局默认</option>
                {householdId ? <option value={householdId}>当前家庭</option> : null}
              </select>
            </label>
            <label>
              主供应商
              <select
                value={routeForm.primary_provider_profile_id ?? ""}
                onChange={(event) =>
                  setRouteForm((current) => ({
                    ...current,
                    primary_provider_profile_id: event.target.value || null,
                  }))
                }
              >
                <option value="">无</option>
                {providers.map((provider) => (
                  <option key={provider.id} value={provider.id}>
                    {provider.display_name} ({provider.provider_code})
                  </option>
                ))}
              </select>
            </label>
            <label>
              备供应商 ID（逗号分隔）
              <input
                value={fallbackProviderText}
                onChange={(event) => setFallbackProviderText(event.target.value)}
                placeholder="provider_profile_id_1,provider_profile_id_2"
              />
            </label>
            <label>
              路由模式
              <select
                value={routeForm.routing_mode}
                onChange={(event) =>
                  setRouteForm((current) => ({
                    ...current,
                    routing_mode: event.target.value,
                  }))
                }
              >
                {routingModeOptions.map((item) => (
                  <option key={item} value={item}>
                    {formatRoutingMode(item)}
                  </option>
                ))}
              </select>
            </label>
            <label>
              超时时间（毫秒）
              <input
                type="number"
                value={routeForm.timeout_ms}
                onChange={(event) =>
                  setRouteForm((current) => ({
                    ...current,
                    timeout_ms: Number(event.target.value),
                  }))
                }
              />
            </label>
            <label>
              最大重试次数
              <input
                type="number"
                value={routeForm.max_retry_count}
                onChange={(event) =>
                  setRouteForm((current) => ({
                    ...current,
                    max_retry_count: Number(event.target.value),
                  }))
                }
              />
            </label>
            <label>
              请求策略（JSON）
              <textarea
                rows={4}
                value={stringifyJson(routeForm.prompt_policy)}
                onChange={(event) => {
                  try {
                    setRouteForm((current) => ({
                      ...current,
                      prompt_policy: JSON.parse(event.target.value) as Record<string, unknown>,
                    }));
                  } catch {
                    setRouteForm((current) => ({ ...current }));
                  }
                }}
              />
            </label>
            <label>
              响应策略（JSON）
              <textarea
                rows={4}
                value={stringifyJson(routeForm.response_policy)}
                onChange={(event) => {
                  try {
                    setRouteForm((current) => ({
                      ...current,
                      response_policy: JSON.parse(event.target.value) as Record<string, unknown>,
                    }));
                  } catch {
                    setRouteForm((current) => ({ ...current }));
                  }
                }}
              />
            </label>
            <label>
              <input
                type="checkbox"
                checked={routeForm.allow_remote}
                onChange={(event) =>
                  setRouteForm((current) => ({
                    ...current,
                    allow_remote: event.target.checked,
                  }))
                }
              />
              允许远端模型
            </label>
            <label>
              <input
                type="checkbox"
                checked={routeForm.enabled}
                onChange={(event) =>
                  setRouteForm((current) => ({
                    ...current,
                    enabled: event.target.checked,
                  }))
                }
              />
              启用这条路由
            </label>
            <div className="button-row">
              <button type="button" onClick={() => handleSaveRoute()}>
                保存路由
              </button>
            </div>
          </div>

          <div className="service-card">
            <h4>现有路由</h4>
            <div className="stack-list">
              {routes.map((route) => (
                <article key={route.id} className="stack-item">
                  <strong>{formatCapability(route.capability)}</strong>
                  <p className="muted">
                    {formatCapability(route.capability)} · {formatRoutingMode(route.routing_mode)} · {route.allow_remote ? "允许远端" : "仅本地"} ·
                    {route.household_id ? "当前家庭" : "全局默认"}
                  </p>
                  <div className="button-row">
                    <button type="button" className="ghost" onClick={() => loadRouteForEdit(route)}>
                      载入编辑
                    </button>
                  </div>
                </article>
              ))}
            </div>
          </div>
        </div>
        {selectedRoute ? (
          <div className="inline-note">
            当前已选能力“{formatCapability(selectedRoute.capability)}”最近更新时间：{formatDateTime(selectedRoute.updated_at)}
          </div>
        ) : null}
      </PageSection>

      <PageSection
        title="预览调用"
        description="配完路由后，直接在这里打一枪，看看主备和降级是不是按预期走。"
      >
        <div className="service-grid">
          <div className="service-card">
            <label>
              预览能力
              <select
                value={routeForm.capability}
                onChange={(event) =>
                  setRouteForm((current) => ({
                    ...current,
                    capability: event.target.value,
                  }))
                }
              >
                {capabilityOptions.map((item) => (
                  <option key={item} value={item}>
                    {formatCapability(item)}
                  </option>
                ))}
              </select>
            </label>
            <label>
              预览入参（JSON）
              <textarea
                rows={10}
                value={previewPayloadText}
                onChange={(event) => setPreviewPayloadText(event.target.value)}
              />
            </label>
            <div className="button-row">
              <button type="button" onClick={() => handleInvokePreview()}>
                发送预览调用
              </button>
            </div>
          </div>
          <div className="service-card">
            <h4>预览结果</h4>
            {previewResult ? (
              <>
                <p>
                  结果：{formatCallStatus(previewResult.status)} · 供应商：{previewResult.provider_code} · 模型：
                  {previewResult.model_name}
                </p>
                <p className="muted">
                  跟踪编号：{previewResult.trace_id} {previewResult.degraded ? "· 已降级" : ""}
                </p>
                <pre>{stringifyJson(previewResult.normalized_output)}</pre>
                <pre>{stringifyJson(previewResult.attempts)}</pre>
              </>
            ) : (
              <p className="muted">还没有预览调用结果。</p>
            )}
          </div>
        </div>
      </PageSection>

      <PageSection
        title="最近调用日志"
        description="如果这里没有记录，说明你的配置根本没真正被调用到。"
      >
        <div className="table-shell">
          <table>
            <thead>
              <tr>
                <th>时间</th>
                <th>能力</th>
                <th>供应商</th>
                <th>状态</th>
                <th>跟踪编号</th>
              </tr>
            </thead>
            <tbody>
              {callLogs.map((log) => (
                <tr key={log.id}>
                  <td>{formatDateTime(log.created_at)}</td>
                  <td>{formatCapability(log.capability)}</td>
                  <td>{log.provider_code}</td>
                  <td>{formatCallStatus(log.status)}</td>
                  <td>{log.trace_id}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </PageSection>
    </div>
  );
}
