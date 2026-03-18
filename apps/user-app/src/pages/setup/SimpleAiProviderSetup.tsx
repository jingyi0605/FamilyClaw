import { useEffect, useMemo, useState, type FormEvent } from 'react';
import { useI18n } from '../../runtime';
import { getPageMessage } from '../../runtime/h5-shell/i18n/pageMessageUtils';
import { Card } from './base';
import { buildCreateProviderPayload, buildProviderFormState, buildRoutePayload, buildUpdateProviderPayload, getProviderAdapterCode, readProviderFormValue, SETUP_ROUTE_CAPABILITIES, toProviderFormState, assignProviderFormValue } from './setupAiConfig';
import { setupApi } from './setupApi';
import type { AiCapabilityRoute, AiProviderAdapter, AiProviderField, AiProviderFieldOption, AiProviderProfile } from './setupTypes';

const HIDDEN_SETUP_FIELDS = new Set(['provider_code', 'latency_budget_ms']);

const ADAPTER_DESCRIPTION_KEYS: Record<string, string> = {
  chatgpt: 'settings.ai.provider.adapter.chatgpt',
  deepseek: 'settings.ai.provider.adapter.deepseek',
  qwen: 'settings.ai.provider.adapter.qwen',
  glm: 'settings.ai.provider.adapter.glm',
  siliconflow: 'settings.ai.provider.adapter.siliconflow',
  kimi: 'settings.ai.provider.adapter.kimi',
  minimax: 'settings.ai.provider.adapter.minimax',
  claude: 'settings.ai.provider.adapter.claude',
  gemini: 'settings.ai.provider.adapter.gemini',
  openrouter: 'settings.ai.provider.adapter.openrouter',
  doubao: 'settings.ai.provider.adapter.doubao',
  'doubao-coding': 'settings.ai.provider.adapter.doubaoCoding',
  byteplus: 'settings.ai.provider.adapter.byteplus',
  'byteplus-coding': 'settings.ai.provider.adapter.byteplusCoding',
};

const FIELD_LABEL_KEYS: Record<string, string> = {
  display_name: 'settings.ai.provider.field.displayName',
  provider_code: 'settings.ai.provider.field.providerCode',
  base_url: 'settings.ai.provider.field.baseUrl',
  secret_ref: 'settings.ai.provider.field.secretRef',
  model_name: 'settings.ai.provider.field.modelName',
  privacy_level: 'settings.ai.provider.field.privacyLevel',
  anthropic_version: 'settings.ai.provider.field.anthropicVersion',
  site_url: 'settings.ai.provider.field.siteUrl',
  app_name: 'settings.ai.provider.field.appName',
  latency_budget_ms: 'settings.ai.provider.field.latencyBudgetMs',
};

const FIELD_HELP_KEYS: Record<string, string> = {
  base_url: 'settings.ai.provider.help.baseUrl',
  site_url: 'settings.ai.provider.help.siteUrl',
  app_name: 'settings.ai.provider.help.appName',
};

const PRIVACY_LEVEL_LABELS: Record<string, string> = {
  public_cloud: 'settings.ai.provider.privacy.publicCloud',
  private_cloud: 'settings.ai.provider.privacy.privateCloud',
  local_only: 'settings.ai.provider.privacy.localOnly',
};

function getLocalizedAdapterDescription(adapter: AiProviderAdapter, locale: string | undefined): string {
  const key = ADAPTER_DESCRIPTION_KEYS[adapter.adapter_code];
  return key ? getPageMessage(locale, key as Parameters<typeof getPageMessage>[1]) : adapter.description;
}

function getLocalizedFieldLabel(field: AiProviderField, locale: string | undefined): string {
  const key = FIELD_LABEL_KEYS[field.key];
  return key ? getPageMessage(locale, key as Parameters<typeof getPageMessage>[1]) : field.label;
}

function getLocalizedFieldHelp(field: AiProviderField, locale: string | undefined): string | null {
  const key = FIELD_HELP_KEYS[field.key];
  return key ? getPageMessage(locale, key as Parameters<typeof getPageMessage>[1]) : field.help_text;
}

function getLocalizedPrivacyLabel(value: string, locale: string | undefined): string {
  const key = PRIVACY_LEVEL_LABELS[value];
  return key ? getPageMessage(locale, key as Parameters<typeof getPageMessage>[1]) : value;
}

function localizeExamplePrefix(text: string | null | undefined, locale: string | undefined): string | null {
  if (!text) return null;
  const normalized = text.trim();
  const prefixes = ['例如：', '例如:', 'For example:', 'Example:'];
  const matchedPrefix = prefixes.find(prefix => normalized.startsWith(prefix));
  if (!matchedPrefix) return text;
  return `${getPageMessage(locale, 'settings.ai.provider.examplePrefix')}${normalized.slice(matchedPrefix.length).trimStart()}`;
}

function getLocalizedField(field: AiProviderField, locale: string | undefined) {
  const localizedOptions: AiProviderFieldOption[] = field.options.map((option: AiProviderFieldOption) => ({
    ...option,
    label: field.key === 'privacy_level' ? getLocalizedPrivacyLabel(option.value, locale) : localizeExamplePrefix(option.label, locale) ?? option.label,
  }));
  return {
    ...field,
    label: getLocalizedFieldLabel(field, locale),
    placeholder: localizeExamplePrefix(field.placeholder, locale),
    help_text: getLocalizedFieldHelp(field, locale),
    options: localizedOptions,
  };
}

export function SimpleAiProviderSetup(props: { householdId: string; onCompleted?: () => void }) {
  const { locale, t } = useI18n();
  const [adapters, setAdapters] = useState<AiProviderAdapter[]>([]);
  const [form, setForm] = useState(buildProviderFormState());
  const [editingProviderId, setEditingProviderId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');

  const currentAdapter = useMemo(() => adapters.find(item => item.adapter_code === form.adapterCode) ?? null, [adapters, form.adapterCode]);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError('');
      try {
        const [adapterRows, providerRows, routeRows] = await Promise.all([
          setupApi.listAiProviderAdapters(props.householdId),
          setupApi.listHouseholdAiProviders(props.householdId),
          setupApi.listHouseholdAiRoutes(props.householdId),
        ]);
        if (cancelled) return;
        const existingProvider = pickSetupProvider(providerRows, routeRows);
        const existingAdapter = existingProvider ? adapterRows.find(item => item.adapter_code === getProviderAdapterCode(existingProvider)) ?? adapterRows[0] ?? null : null;
        setAdapters(adapterRows);
        setEditingProviderId(existingProvider?.id ?? null);
        setForm(existingProvider ? toProviderFormState(existingProvider, existingAdapter) : buildProviderFormState(adapterRows[0] ?? null));
      } catch (loadError) {
        if (!cancelled) setError(loadError instanceof Error ? loadError.message : t('setup.providerSetup.loadFailed'));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => { cancelled = true; };
  }, [props.householdId, t]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!currentAdapter) { setError(t('setup.providerSetup.selectTypeFirst')); return; }
    setSaving(true);
    setError('');
    setStatus(editingProviderId ? t('setup.providerSetup.saving') : t('setup.providerSetup.creating'));
    try {
      const providerId = editingProviderId ? editingProviderId : (await setupApi.createHouseholdAiProvider(props.householdId, buildCreateProviderPayload(form, currentAdapter))).id;
      if (editingProviderId) {
        await setupApi.updateHouseholdAiProvider(props.householdId, editingProviderId, buildUpdateProviderPayload(form, currentAdapter));
      } else {
        setEditingProviderId(providerId);
      }
      setStatus(t('setup.providerSetup.configuringRoutes'));
      const supportedCapabilities = form.supportedCapabilities;
      if (supportedCapabilities.length === 0) throw new Error(t('setup.providerSetup.noSupportedCapability'));
      const routes = await setupApi.listHouseholdAiRoutes(props.householdId);
      await Promise.all(supportedCapabilities.map(capability => {
        const currentRoute = routes.find(item => item.capability === capability);
        return setupApi.upsertHouseholdAiRoute(props.householdId, capability, buildRoutePayload(props.householdId, capability, currentRoute, providerId, true));
      }));
      setStatus(t('setup.providerSetup.completed'));
      props.onCompleted?.();
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : t('setup.providerSetup.saveFailed'));
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <Card><p>{t('setup.providerSetup.loading')}</p></Card>;

  return (
    <Card className="ai-config-detail-card">
      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label htmlFor={`provider-adapter-${props.householdId}`}>{t('setup.providerSetup.platformLabel')}</label>
          <select id={`provider-adapter-${props.householdId}`} className="form-select" value={form.adapterCode} onChange={event => setForm(buildProviderFormState(adapters.find(item => item.adapter_code === event.target.value) ?? null))} disabled={Boolean(editingProviderId)}>
            <option value="">{t('setup.providerSetup.selectPlaceholder')}</option>
            {adapters.map(adapter => <option key={adapter.adapter_code} value={adapter.adapter_code}>{adapter.display_name}</option>)}
          </select>
        </div>
        {currentAdapter ? (
          <>
            <p className="ai-config-muted">{getLocalizedAdapterDescription(currentAdapter, locale)}</p>
            <div className="setup-form-grid">
              {currentAdapter.field_schema.filter(field => !HIDDEN_SETUP_FIELDS.has(field.key)).map(field => {
                const localizedField = getLocalizedField(field, locale);
                return (
                  <div key={field.key} className="form-group">
                    <label htmlFor={`${props.householdId}-${field.key}`}>{localizedField.label}</label>
                    {field.field_type === 'select' ? (
                      <select id={`${props.householdId}-${field.key}`} className="form-select" value={readProviderFormValue(form, field.key)} onChange={event => setForm(assignProviderFormValue(form, field.key, event.target.value))}>
                        <option value="">{t('setup.providerSetup.selectPlaceholder')}</option>
                        {localizedField.options.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
                      </select>
                    ) : (
                      <input id={`${props.householdId}-${field.key}`} className="form-input" type={field.key === 'secret_ref' ? 'password' : field.field_type === 'number' ? 'number' : 'text'} value={readProviderFormValue(form, field.key)} onChange={event => setForm(assignProviderFormValue(form, field.key, event.target.value))} placeholder={localizedField.placeholder ?? undefined} />
                    )}
                    {localizedField.help_text ? <p className="ai-config-muted">{localizedField.help_text}</p> : null}
                  </div>
                );
              })}
            </div>
            <div className="setup-inline-tip"><strong>{t('setup.providerSetup.tipTitle')}</strong><span>{t('setup.providerSetup.tipBody')}</span></div>
          </>
        ) : null}
        {error ? <div className="form-error">{error}</div> : null}
        {status ? <div className="setup-form-status">{status}</div> : null}
        <div className="setup-form-actions"><button className="btn btn--primary btn--large" type="submit" disabled={saving || !currentAdapter || !form.displayName.trim() || !form.modelName.trim()}>{saving ? t('setup.providerSetup.binding') : editingProviderId ? t('setup.providerSetup.saveAndUpdateAll') : t('setup.providerSetup.createAndApplyAll')}</button></div>
      </form>
    </Card>
  );
}

function pickSetupProvider(providers: AiProviderProfile[], routes: AiCapabilityRoute[]) {
  const routeProviderIds = SETUP_ROUTE_CAPABILITIES.map(capability => routes.find(item => item.capability === capability)?.primary_provider_profile_id).filter((providerId): providerId is string => Boolean(providerId));
  for (const providerId of routeProviderIds) {
    const matchedProvider = providers.find(item => item.id === providerId);
    if (matchedProvider) return matchedProvider;
  }
  return providers[0] ?? null;
}
