import type {
  AiCapabilityRoute,
  AiProviderAdapter,
  AiProviderField,
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

const CORE_PROVIDER_FIELD_KEYS = new Set([
  'display_name',
  'provider_code',
  'base_url',
  'secret_ref',
  'model_name',
  'privacy_level',
  'latency_budget_ms',
]);

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
  const dynamicFields = Object.fromEntries(
    (adapter?.field_schema ?? [])
      .filter(field => !CORE_PROVIDER_FIELD_KEYS.has(field.key))
      .map(field => [field.key, readAdapterDefault(adapter, field.key)]),
  );

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
    dynamicFields,
  };
}

export function toProviderFormState(provider: AiProviderProfile, adapter?: AiProviderAdapter | null) {
  const dynamicFields = Object.fromEntries(
    (adapter?.field_schema ?? [])
      .filter(field => !CORE_PROVIDER_FIELD_KEYS.has(field.key))
      .map(field => [field.key, readProviderExtraConfigValue(provider, field)]),
  );

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
    dynamicFields,
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
    api_family: adapter.api_family,
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
      ...buildDynamicExtraConfig(form.dynamicFields, adapter),
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
    api_family: adapter.api_family,
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
      ...buildDynamicExtraConfig(form.dynamicFields, adapter),
    },
  };
}

export function readProviderFormValue(
  form: ReturnType<typeof buildProviderFormState>,
  fieldKey: string,
) {
  if (fieldKey === 'display_name') return form.displayName;
  if (fieldKey === 'provider_code') return form.providerCode;
  if (fieldKey === 'base_url') return form.baseUrl;
  if (fieldKey === 'secret_ref') return form.secretRef;
  if (fieldKey === 'model_name') return form.modelName;
  if (fieldKey === 'privacy_level') return form.privacyLevel;
  if (fieldKey === 'latency_budget_ms') return form.latencyBudgetMs;
  return form.dynamicFields[fieldKey] ?? '';
}

export function assignProviderFormValue(
  form: ReturnType<typeof buildProviderFormState>,
  fieldKey: string,
  value: string,
) {
  if (fieldKey === 'display_name') return { ...form, displayName: value };
  if (fieldKey === 'provider_code') return { ...form, providerCode: value };
  if (fieldKey === 'base_url') return { ...form, baseUrl: value };
  if (fieldKey === 'secret_ref') return { ...form, secretRef: value };
  if (fieldKey === 'model_name') return { ...form, modelName: value };
  if (fieldKey === 'privacy_level') return { ...form, privacyLevel: value };
  if (fieldKey === 'latency_budget_ms') return { ...form, latencyBudgetMs: value };
  return {
    ...form,
    dynamicFields: {
      ...form.dynamicFields,
      [fieldKey]: value,
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

function readProviderExtraConfigValue(provider: AiProviderProfile, field: AiProviderField) {
  const raw = provider.extra_config?.[field.key];
  if (typeof raw === 'boolean') {
    return raw ? 'true' : 'false';
  }
  if (typeof raw === 'number') {
    return String(raw);
  }
  if (typeof raw === 'string') {
    return raw;
  }
  return String(field.default_value ?? '');
}

function buildDynamicExtraConfig(
  dynamicFields: Record<string, string>,
  adapter: AiProviderAdapter,
) {
  const result: Record<string, string | number | boolean> = {};

  for (const field of adapter.field_schema) {
    if (CORE_PROVIDER_FIELD_KEYS.has(field.key)) {
      continue;
    }

    const rawValue = dynamicFields[field.key] ?? '';
    if (!rawValue.trim()) {
      continue;
    }

    if (field.field_type === 'number') {
      const parsed = Number(rawValue);
      if (Number.isFinite(parsed)) {
        result[field.key] = parsed;
      }
      continue;
    }

    if (field.field_type === 'boolean') {
      result[field.key] = rawValue === 'true';
      continue;
    }

    result[field.key] = rawValue.trim();
  }

  return result;
}

function buildSetupProviderCode(adapterCode: string) {
  return `setup-${adapterCode}-${Date.now()}`;
}
