import type {
  AiCapabilityRoute,
  AiCapabilityRouteUpsertPayload,
  AiProviderAdapter,
  AiProviderField,
  AiProviderProfile,
  AiProviderProfileCreatePayload,
  AiProviderProfileUpdatePayload,
} from '../domain/types';

export const SETUP_ROUTE_CAPABILITIES = ['qa_generation', 'qa_structured_answer'] as const;

export type SetupProviderFormState = {
  adapterCode: string;
  displayName: string;
  baseUrl: string;
  secretRef: string;
  modelName: string;
  privacyLevel: string;
  latencyBudgetMs: string;
  enabled: boolean;
  supportedCapabilities: string[];
  dynamicFields: Record<string, string>;
};

const CORE_PROVIDER_FIELD_KEYS = new Set([
  'display_name',
  'provider_code',
  'base_url',
  'secret_ref',
  'model_name',
  'privacy_level',
  'latency_budget_ms',
]);

export function buildSetupProviderFormState(adapter?: AiProviderAdapter | null): SetupProviderFormState {
  const dynamicFields = Object.fromEntries(
    (adapter?.field_schema ?? [])
      .filter(field => !CORE_PROVIDER_FIELD_KEYS.has(field.key))
      .map(field => [field.key, readAdapterDefault(adapter, field.key)]),
  );

  return {
    adapterCode: adapter?.adapter_code ?? '',
    displayName: '',
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

export function toSetupProviderFormState(provider: AiProviderProfile, adapter?: AiProviderAdapter | null): SetupProviderFormState {
  const dynamicFields = Object.fromEntries(
    (adapter?.field_schema ?? [])
      .filter(field => !CORE_PROVIDER_FIELD_KEYS.has(field.key))
      .map(field => [field.key, readProviderExtraConfigValue(provider, field)]),
  );

  return {
    adapterCode: getProviderAdapterCode(provider) || adapter?.adapter_code || '',
    displayName: provider.display_name,
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

export function buildCreateSetupProviderPayload(
  form: SetupProviderFormState,
  adapter: AiProviderAdapter,
): AiProviderProfileCreatePayload {
  return {
    display_name: form.displayName.trim(),
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

export function buildUpdateSetupProviderPayload(
  form: SetupProviderFormState,
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

export function readSetupProviderFormValue(form: SetupProviderFormState, fieldKey: string) {
  if (fieldKey === 'display_name') return form.displayName;
  if (fieldKey === 'base_url') return form.baseUrl;
  if (fieldKey === 'secret_ref') return form.secretRef;
  if (fieldKey === 'model_name') return form.modelName;
  if (fieldKey === 'privacy_level') return form.privacyLevel;
  if (fieldKey === 'latency_budget_ms') return form.latencyBudgetMs;
  return form.dynamicFields[fieldKey] ?? '';
}

export function assignSetupProviderFormValue(
  form: SetupProviderFormState,
  fieldKey: string,
  value: string,
): SetupProviderFormState {
  if (fieldKey === 'display_name') return { ...form, displayName: value };
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

export function buildSetupRoutePayload(
  householdId: string,
  capability: string,
  currentRoute: AiCapabilityRoute | undefined,
  primaryProviderProfileId: string | null,
  enabled: boolean,
): AiCapabilityRouteUpsertPayload {
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

export function pickSetupProviderProfile(providers: AiProviderProfile[], routes: AiCapabilityRoute[]) {
  const routeProviderIds = SETUP_ROUTE_CAPABILITIES
    .map(capability => routes.find(item => item.capability === capability)?.primary_provider_profile_id)
    .filter((providerId): providerId is string => Boolean(providerId));

  for (const providerId of routeProviderIds) {
    const matchedProvider = providers.find(item => item.id === providerId);
    if (matchedProvider) {
      return matchedProvider;
    }
  }

  return providers[0] ?? null;
}

export function resolveSetupRoutableCapabilities(capabilities: string[]) {
  return SETUP_ROUTE_CAPABILITIES.filter(capability => capabilities.includes(capability));
}

export function parseTagList(raw: string) {
  return Array.from(new Set(raw.split(/[,，、\n]/).map(item => item.trim()).filter(Boolean)));
}

export function stringifyTagList(values: string[]) {
  return values.join(', ');
}

function getProviderModelName(provider: AiProviderProfile) {
  const raw = provider.extra_config?.model_name;
  return typeof raw === 'string' && raw.trim() ? raw.trim() : provider.api_version;
}

function getProviderAdapterCode(provider: AiProviderProfile) {
  const raw = provider.extra_config?.adapter_code;
  return typeof raw === 'string' && raw.trim() ? raw.trim() : '';
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

