import type {
  AiCapabilityRoute,
  AiProviderAdapter,
  AiProviderProfile,
  AiProviderProfileCreatePayload,
  AiProviderProfileUpdatePayload,
} from './types';

export const AI_CAPABILITY_OPTIONS = [
  { value: 'qa_generation', label: '家庭问答生成' },
  { value: 'qa_structured_answer', label: '结构化问答' },
  { value: 'reminder_copywriting', label: '提醒文案' },
  { value: 'scene_explanation', label: '场景解释' },
  { value: 'embedding', label: '向量检索' },
  { value: 'rerank', label: '结果重排' },
  { value: 'stt', label: '语音转文字' },
  { value: 'tts', label: '文字转语音' },
  { value: 'vision', label: '视觉理解' },
] as const;

export const SETUP_ROUTE_CAPABILITIES = ['qa_generation', 'qa_structured_answer'];

export function getCapabilityLabel(capability: string) {
  return AI_CAPABILITY_OPTIONS.find(item => item.value === capability)?.label ?? capability;
}

export function parseTags(raw: string) {
  return Array.from(new Set(raw.split(/[,，、\n]/).map(item => item.trim()).filter(Boolean)));
}

export function stringifyTags(values: string[]) {
  return values.join(', ');
}

export function getProviderModelName(provider: AiProviderProfile) {
  const raw = provider.extra_config?.model_name;
  return typeof raw === 'string' && raw.trim() ? raw.trim() : provider.api_version;
}

export function getProviderAdapterCode(provider: AiProviderProfile) {
  const raw = provider.extra_config?.adapter_code;
  return typeof raw === 'string' && raw.trim() ? raw.trim() : '';
}

export function buildProviderFormState(adapter?: AiProviderAdapter | null) {
  return {
    adapterCode: adapter?.adapter_code ?? '',
    displayName: '',
    providerCode: '',
    baseUrl: readAdapterDefault(adapter, 'base_url'),
    secretRef: '',
    modelName: '',
    privacyLevel: String(readAdapterDefault(adapter, 'privacy_level') ?? adapter?.default_privacy_level ?? 'public_cloud'),
    latencyBudgetMs: String(readAdapterDefault(adapter, 'latency_budget_ms') ?? ''),
    enabled: true,
    supportedCapabilities: [...(adapter?.default_supported_capabilities ?? SETUP_ROUTE_CAPABILITIES)],
  };
}

export function toProviderFormState(provider: AiProviderProfile, adapter?: AiProviderAdapter | null) {
  return {
    adapterCode: getProviderAdapterCode(provider) || adapter?.adapter_code || '',
    displayName: provider.display_name,
    providerCode: provider.provider_code,
    baseUrl: provider.base_url ?? '',
    secretRef: provider.secret_ref ?? '',
    modelName: getProviderModelName(provider) ?? '',
    privacyLevel: provider.privacy_level,
    latencyBudgetMs: provider.latency_budget_ms ? String(provider.latency_budget_ms) : '',
    enabled: provider.enabled,
    supportedCapabilities: provider.supported_capabilities,
  };
}

export function buildCreateProviderPayload(
  form: ReturnType<typeof buildProviderFormState>,
  adapter: AiProviderAdapter,
): AiProviderProfileCreatePayload {
  const normalizedDisplayName = form.displayName.trim();
  const normalizedProviderCode = form.providerCode.trim() || buildSetupProviderCode(adapter.adapter_code);

  return {
    provider_code: normalizedProviderCode,
    display_name: normalizedDisplayName,
    transport_type: adapter.transport_type,
    base_url: form.baseUrl.trim() || null,
    api_version: null,
    secret_ref: form.secretRef.trim() || null,
    enabled: form.enabled,
    supported_capabilities: form.supportedCapabilities,
    privacy_level: form.privacyLevel as AiProviderProfileCreatePayload['privacy_level'],
    latency_budget_ms: parseOptionalNumber(form.latencyBudgetMs),
    cost_policy: {},
    extra_config: {
      adapter_code: adapter.adapter_code,
      model_name: form.modelName.trim(),
    },
  };
}

export function buildUpdateProviderPayload(
  form: ReturnType<typeof buildProviderFormState>,
  adapter: AiProviderAdapter,
): AiProviderProfileUpdatePayload {
  return {
    display_name: form.displayName.trim(),
    transport_type: adapter.transport_type,
    base_url: form.baseUrl.trim() || null,
    api_version: null,
    secret_ref: form.secretRef.trim() || null,
    enabled: form.enabled,
    supported_capabilities: form.supportedCapabilities,
    privacy_level: form.privacyLevel as AiProviderProfileUpdatePayload['privacy_level'],
    latency_budget_ms: parseOptionalNumber(form.latencyBudgetMs),
    cost_policy: {},
    extra_config: {
      adapter_code: adapter.adapter_code,
      model_name: form.modelName.trim(),
    },
  };
}

export function buildRoutePayload(
  householdId: string,
  capability: string,
  currentRoute: AiCapabilityRoute | undefined,
  primaryProviderProfileId: string | null,
  enabled: boolean,
) {
  return {
    capability,
    household_id: householdId,
    primary_provider_profile_id: primaryProviderProfileId,
    fallback_provider_profile_ids: currentRoute?.fallback_provider_profile_ids ?? [],
    routing_mode: currentRoute?.routing_mode ?? 'primary_then_fallback',
    timeout_ms: currentRoute?.timeout_ms ?? 15000,
    max_retry_count: currentRoute?.max_retry_count ?? 0,
    allow_remote: currentRoute?.allow_remote ?? true,
    prompt_policy: currentRoute?.prompt_policy ?? {},
    response_policy: currentRoute?.response_policy ?? {},
    enabled,
  };
}

function parseOptionalNumber(value: string) {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) ? parsed : null;
}

function readAdapterDefault(adapter: AiProviderAdapter | null | undefined, key: string) {
  if (!adapter) {
    return '';
  }
  return String(adapter.field_schema.find(item => item.key === key)?.default_value ?? '');
}

function buildSetupProviderCode(adapterCode: string) {
  return `setup-${adapterCode}-${Date.now()}`;
}
