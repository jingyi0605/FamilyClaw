import { useEffect, useMemo, useState, type FormEvent } from 'react';
import { useI18n } from '../../../runtime';
import { getPageMessage } from '../../../runtime/h5-shell/i18n/pageMessageUtils';
import { Card } from '../../family/base';
import {
  buildCreateProviderPayload,
  buildProviderFormState,
  buildUpdateProviderPayload,
  getProviderAdapterCode,
  getProviderModelName,
  toProviderFormState,
} from '../../setup/setupAiConfig';
import { settingsApi } from '../settingsApi';
import type {
  AiCapabilityRoute,
  AiProviderAdapter,
  AiProviderField,
  AiProviderProfile,
} from '../settingsTypes';
import { AiProviderEditorDialog } from './AiProviderEditorDialog';
import {
  getLocalizedAdapterMeta,
  getLocalizedCapabilityLabel,
  getLocalizedField,
  getLocalizedModelTypeLabel,
  getLocalizedWorkflowLabel,
} from './aiProviderCatalog';

type ProviderFormState = ReturnType<typeof buildProviderFormState>;

function maskSecret(value: string | null | undefined) {
  if (!value) {
    return '';
  }
  if (value.length <= 6) {
    return '******';
  }
  return `${value.slice(0, 3)}******${value.slice(-3)}`;
}

function readSummaryValue(provider: AiProviderProfile, field: AiProviderField) {
  switch (field.key) {
    case 'display_name':
      return provider.display_name;
    case 'provider_code':
      return provider.provider_code;
    case 'base_url':
      return provider.base_url ?? '';
    case 'secret_ref':
      return maskSecret(provider.secret_ref);
    case 'model_name':
      return getProviderModelName(provider) ?? '';
    case 'privacy_level':
      return String(provider.privacy_level || '');
    case 'latency_budget_ms':
      return provider.latency_budget_ms ? String(provider.latency_budget_ms) : '';
    default: {
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
      return '';
    }
  }
}

export function AiProviderConfigPanel(props: {
  householdId: string;
  compact?: boolean;
  capabilityFilter?: string[];
  onChanged?: () => Promise<void> | void;
}) {
  const { locale, t } = useI18n();
  const { householdId, capabilityFilter, onChanged } = props;
  const [adapters, setAdapters] = useState<AiProviderAdapter[]>([]);
  const [providers, setProviders] = useState<AiProviderProfile[]>([]);
  const [routes, setRoutes] = useState<AiCapabilityRoute[]>([]);
  const [selectedProviderId, setSelectedProviderId] = useState('');
  const [editingProviderId, setEditingProviderId] = useState<string | null>(null);
  const [editorOpen, setEditorOpen] = useState(false);
  const [form, setForm] = useState<ProviderFormState>(buildProviderFormState());
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');

  const adapterMap = useMemo(
    () => new Map(adapters.map(item => [item.adapter_code, item])),
    [adapters],
  );

  const visibleProviders = useMemo(
    () => providers.filter(item => !capabilityFilter || capabilityFilter.some(capability => item.supported_capabilities.includes(capability))),
    [capabilityFilter, providers],
  );

  const selectedProvider = useMemo(
    () => visibleProviders.find(item => item.id === selectedProviderId) ?? visibleProviders[0] ?? null,
    [selectedProviderId, visibleProviders],
  );

  const selectedAdapter = useMemo(
    () => (selectedProvider ? adapterMap.get(getProviderAdapterCode(selectedProvider)) ?? null : null),
    [adapterMap, selectedProvider],
  );

  const configuredRoutes = useMemo(
    () => routes.filter(item => item.enabled && item.primary_provider_profile_id),
    [routes],
  );

  const summaryStats = useMemo(
    () => [
      { label: getPageMessage(locale, 'settings.ai.provider.summary.totalModels'), value: String(visibleProviders.length) },
      { label: getPageMessage(locale, 'settings.ai.provider.summary.enabledModels'), value: String(visibleProviders.filter(item => item.enabled).length) },
      { label: getPageMessage(locale, 'settings.ai.provider.summary.activeRoutes'), value: String(configuredRoutes.length) },
      { label: getPageMessage(locale, 'settings.ai.provider.summary.plugins'), value: String(new Set(adapters.map(item => item.plugin_id)).size) },
    ],
    [adapters, configuredRoutes.length, locale, visibleProviders],
  );

  const copy = {
    loadFailed: getPageMessage(locale, 'settings.ai.provider.loadFailed'),
    selectTypeFirst: getPageMessage(locale, 'settings.ai.provider.selectTypeFirst'),
    updatedStatus: getPageMessage(locale, 'settings.ai.provider.updatedStatus'),
    addedStatus: getPageMessage(locale, 'settings.ai.provider.addedStatus'),
    saveFailed: getPageMessage(locale, 'settings.ai.provider.saveFailed'),
    deletedStatus: getPageMessage(locale, 'settings.ai.provider.deletedStatus'),
    deleteFailed: getPageMessage(locale, 'settings.ai.provider.deleteFailed'),
    addProvider: getPageMessage(locale, 'settings.ai.provider.addProvider'),
    editProvider: getPageMessage(locale, 'settings.ai.provider.editProvider'),
    deleteProvider: getPageMessage(locale, 'settings.ai.provider.deleteProvider'),
    loading: getPageMessage(locale, 'settings.ai.provider.loading'),
    emptyProviders: getPageMessage(locale, 'settings.ai.provider.emptyProviders'),
    enabled: getPageMessage(locale, 'settings.ai.provider.enabled'),
    disabled: getPageMessage(locale, 'settings.ai.provider.disabled'),
    modelNameEmpty: getPageMessage(locale, 'settings.ai.provider.modelNameEmpty'),
    editTitle: getPageMessage(locale, 'settings.ai.provider.editTitle'),
    addTitle: getPageMessage(locale, 'settings.ai.provider.addTitle'),
    formDescription: getPageMessage(locale, 'settings.ai.provider.formDescription'),
    providerTypeLabel: getPageMessage(locale, 'settings.ai.provider.providerTypeLabel'),
    selectPlaceholder: getPageMessage(locale, 'settings.ai.provider.selectPlaceholder'),
    capabilityCheckboxLabel: getPageMessage(locale, 'settings.ai.provider.capabilityCheckboxLabel'),
    enableAfterSave: getPageMessage(locale, 'settings.ai.provider.enableAfterSave'),
    saveProvider: getPageMessage(locale, 'settings.ai.provider.saveProvider'),
    submitAddProvider: getPageMessage(locale, 'settings.ai.provider.submitAddProvider'),
    chooseProviderPlugin: getPageMessage(locale, 'settings.ai.provider.chooseProviderPlugin'),
    chooseProviderPluginDesc: getPageMessage(locale, 'settings.ai.provider.chooseProviderPluginDesc'),
    supportedModelTypes: getPageMessage(locale, 'settings.ai.provider.supportedModelTypes'),
    llmWorkflow: getPageMessage(locale, 'settings.ai.provider.llmWorkflow'),
    summaryTitle: getPageMessage(locale, 'settings.ai.provider.summaryTitle'),
    summaryDesc: getPageMessage(locale, 'settings.ai.provider.summaryDesc'),
    summaryConfigTitle: getPageMessage(locale, 'settings.ai.provider.summaryConfigTitle'),
    summaryRouteTitle: getPageMessage(locale, 'settings.ai.provider.summaryRouteTitle'),
    summaryRouteEmpty: getPageMessage(locale, 'settings.ai.provider.summaryRouteEmpty'),
    summarySupportTitle: getPageMessage(locale, 'settings.ai.provider.summarySupportTitle'),
    emptySummaryTitle: getPageMessage(locale, 'settings.ai.provider.emptySummaryTitle'),
    emptySummaryDesc: getPageMessage(locale, 'settings.ai.provider.emptySummaryDesc'),
    pluginLabel: getPageMessage(locale, 'settings.ai.provider.pluginLabel'),
    updatedAtLabel: getPageMessage(locale, 'settings.ai.provider.updatedAtLabel'),
    cancel: t('common.cancel'),
    saving: t('common.saving'),
    deleteConfirm: getPageMessage(locale, 'settings.ai.provider.deleteConfirm'),
  };

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError('');
      try {
        const [adapterRows, providerRows, routeRows] = await Promise.all([
          settingsApi.listAiProviderAdapters(),
          settingsApi.listHouseholdAiProviders(householdId),
          settingsApi.listHouseholdAiRoutes(householdId),
        ]);
        if (cancelled) {
          return;
        }
        setAdapters(adapterRows.map(item => ({
          ...item,
          plugin_id: item.plugin_id ?? item.adapter_code,
          plugin_name: item.plugin_name ?? item.display_name,
          supported_model_types: item.supported_model_types ?? ['llm'],
          llm_workflow: item.llm_workflow ?? item.api_family,
        })));
        setProviders(providerRows);
        setRoutes(routeRows);
        setSelectedProviderId(current => (providerRows.some(item => item.id === current) ? current : (providerRows[0]?.id ?? '')));
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : copy.loadFailed);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [copy.loadFailed, householdId]);

  useEffect(() => {
    if (!selectedProvider && selectedProviderId) {
      setSelectedProviderId(visibleProviders[0]?.id ?? '');
    }
  }, [selectedProvider, selectedProviderId, visibleProviders]);

  async function reload(selectProviderId?: string) {
    const [providerRows, routeRows] = await Promise.all([
      settingsApi.listHouseholdAiProviders(householdId),
      settingsApi.listHouseholdAiRoutes(householdId),
    ]);
    setProviders(providerRows);
    setRoutes(routeRows);
    setSelectedProviderId(selectProviderId ?? (providerRows.some(item => item.id === selectedProviderId) ? selectedProviderId : (providerRows[0]?.id ?? '')));
    await onChanged?.();
  }

  function startCreate() {
    setEditingProviderId(null);
    setForm(buildProviderFormState());
    setError('');
    setEditorOpen(true);
  }

  function startEdit(provider: AiProviderProfile) {
    const adapter = adapterMap.get(getProviderAdapterCode(provider)) ?? null;
    setEditingProviderId(provider.id);
    setSelectedProviderId(provider.id);
    setForm(toProviderFormState(provider, adapter));
    setError('');
    setEditorOpen(true);
  }

  function closeEditor() {
    if (saving) {
      return;
    }
    setEditorOpen(false);
    setEditingProviderId(null);
    setForm(buildProviderFormState());
  }

  function handleAdapterChange(adapterCode: string) {
    const adapter = adapters.find(item => item.adapter_code === adapterCode) ?? null;
    setForm(buildProviderFormState(adapter));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const currentAdapter = adapters.find(item => item.adapter_code === form.adapterCode) ?? null;
    if (!currentAdapter) {
      setError(copy.selectTypeFirst);
      return;
    }

    setSaving(true);
    setError('');
    setStatus('');
    try {
      if (editingProviderId) {
        await settingsApi.updateHouseholdAiProvider(
          householdId,
          editingProviderId,
          buildUpdateProviderPayload(form, currentAdapter),
        );
        setStatus(copy.updatedStatus);
        await reload(editingProviderId);
      } else {
        const created = await settingsApi.createHouseholdAiProvider(
          householdId,
          buildCreateProviderPayload(form, currentAdapter),
        );
        setStatus(copy.addedStatus);
        await reload(created.id);
      }
      closeEditor();
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : copy.saveFailed);
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!selectedProvider) {
      return;
    }
    if (globalThis.confirm && !globalThis.confirm(copy.deleteConfirm)) {
      return;
    }

    setSaving(true);
    setError('');
    setStatus('');
    try {
      await settingsApi.deleteHouseholdAiProvider(householdId, selectedProvider.id);
      setStatus(copy.deletedStatus);
      await reload();
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : copy.deleteFailed);
    } finally {
      setSaving(false);
    }
  }

  function renderSummary(provider: AiProviderProfile, adapter: AiProviderAdapter | null) {
    const adapterMeta = adapter ? getLocalizedAdapterMeta(adapter, locale) : null;
    const routeCapabilities = routes
      .filter(item => item.enabled && item.primary_provider_profile_id === provider.id)
      .map(item => item.capability);
    const summaryFields = adapter?.field_schema
      .map(field => {
        const localizedField = getLocalizedField(field, locale);
        const rawValue = readSummaryValue(provider, field);
        const value = localizedField.field_type === 'select'
          ? localizedField.options.find(option => option.value === rawValue)?.label ?? rawValue
          : (field.key === 'latency_budget_ms' && rawValue ? `${rawValue} ms` : rawValue);

        return {
          key: field.key,
          label: localizedField.label,
          value,
        };
      })
      .filter(item => item.value)
      ?? [];

    return (
      <Card className="ai-config-detail-card ai-provider-summary-card">
        <div className="ai-config-detail__hero">
          <div className="ai-config-card__avatar">AI</div>
          <div className="ai-config-detail__text">
            <div className="ai-config-detail__title-row">
              <h3>{provider.display_name}</h3>
              <span className={`ai-pill ${provider.enabled ? 'ai-pill--success' : 'ai-pill--muted'}`}>
                {provider.enabled ? copy.enabled : copy.disabled}
              </span>
            </div>
            <p>{adapterMeta?.label ?? provider.provider_code}</p>
            <p>{getProviderModelName(provider) ?? copy.modelNameEmpty}</p>
          </div>
        </div>

        <div className="ai-provider-summary-grid">
          <div className="ai-provider-summary-stat">
            <span>{copy.pluginLabel}</span>
            <strong>{adapter?.plugin_name ?? '--'}</strong>
          </div>
          <div className="ai-provider-summary-stat">
            <span>{copy.llmWorkflow}</span>
            <strong>{adapter ? getLocalizedWorkflowLabel(adapter.llm_workflow, locale) : '--'}</strong>
          </div>
          <div className="ai-provider-summary-stat">
            <span>{copy.updatedAtLabel}</span>
            <strong>{provider.updated_at}</strong>
          </div>
        </div>

        <div className="ai-provider-summary-section">
          <h4>{copy.summarySupportTitle}</h4>
          <div className="ai-config-chip-list">
            {(adapter?.supported_model_types ?? []).map(type => (
              <span key={type} className="ai-pill ai-pill--primary">
                {getLocalizedModelTypeLabel(type, locale)}
              </span>
            ))}
            {provider.supported_capabilities.map(capability => (
              <span key={capability} className="ai-pill">
                {getLocalizedCapabilityLabel(capability, locale)}
              </span>
            ))}
          </div>
        </div>

        <div className="ai-provider-summary-section">
          <h4>{copy.summaryRouteTitle}</h4>
          {routeCapabilities.length > 0 ? (
            <div className="ai-config-chip-list">
              {routeCapabilities.map(capability => (
                <span key={capability} className="ai-pill">
                  {getLocalizedCapabilityLabel(capability, locale)}
                </span>
              ))}
            </div>
          ) : (
            <p className="ai-config-muted">{copy.summaryRouteEmpty}</p>
          )}
        </div>

        <div className="ai-provider-summary-section">
          <h4>{copy.summaryConfigTitle}</h4>
          <div className="ai-provider-summary-list">
            {summaryFields.map(item => (
              <div key={item.key} className="ai-provider-summary-list__item">
                <span>{item.label}</span>
                <strong>{item.value}</strong>
              </div>
            ))}
          </div>
        </div>
      </Card>
    );
  }

  return (
    <div className="ai-provider-center">
      <Card className="ai-config-detail-card">
        <div className="agent-config-center__toolbar">
          <div className="agent-config-center__intro">
            <h3>{copy.summaryTitle}</h3>
            <p>{copy.summaryDesc}</p>
          </div>
          <div className="ai-provider-center__toolbar">
            <button className="btn btn--primary" type="button" onClick={startCreate}>
              {copy.addProvider}
            </button>
            {selectedProvider ? (
              <button className="btn btn--outline" type="button" onClick={() => startEdit(selectedProvider)}>
                {copy.editProvider}
              </button>
            ) : null}
            {selectedProvider ? (
              <button className="btn btn--outline" type="button" onClick={() => void handleDelete()} disabled={saving}>
                {copy.deleteProvider}
              </button>
            ) : null}
          </div>
        </div>

        <div className="ai-provider-summary-grid ai-provider-summary-grid--top">
          {summaryStats.map(item => (
            <div key={item.label} className="ai-provider-summary-stat">
              <span>{item.label}</span>
              <strong>{item.value}</strong>
            </div>
          ))}
        </div>

        {status ? <div className="setup-form-status">{status}</div> : null}
      </Card>

      {error ? <Card><p className="form-error">{error}</p></Card> : null}
      {loading ? <div className="settings-loading-copy settings-loading-copy--center">{copy.loading}</div> : null}

      {!loading ? (
        visibleProviders.length > 0 ? (
          <>
            <div className="ai-config-list ai-provider-config-list">
              {visibleProviders.map(provider => {
                const adapter = adapterMap.get(getProviderAdapterCode(provider)) ?? null;
                const adapterMeta = adapter ? getLocalizedAdapterMeta(adapter, locale) : null;
                const routeCapabilities = routes
                  .filter(item => item.enabled && item.primary_provider_profile_id === provider.id)
                  .map(item => item.capability);

                return (
                  <button
                    key={provider.id}
                    type="button"
                    className={`ai-config-card ai-provider-card ${selectedProvider?.id === provider.id ? 'ai-config-card--selected' : ''}`}
                    onClick={() => setSelectedProviderId(provider.id)}
                  >
                    <div className="ai-config-card__top">
                      <div className="ai-config-card__avatar">AI</div>
                      <div className="ai-config-card__text">
                        <div className="ai-config-card__title-row">
                          <h3>{provider.display_name}</h3>
                          <span className={`ai-pill ${provider.enabled ? 'ai-pill--success' : 'ai-pill--muted'}`}>
                            {provider.enabled ? copy.enabled : copy.disabled}
                          </span>
                        </div>
                        <p className="ai-config-card__meta">{adapterMeta?.label ?? provider.provider_code}</p>
                        <p className="ai-config-card__summary">{getProviderModelName(provider) ?? copy.modelNameEmpty}</p>
                      </div>
                    </div>

                    <div className="ai-config-chip-list">
                      {(adapter?.supported_model_types ?? []).map(type => (
                        <span key={type} className="ai-pill ai-pill--primary">
                          {getLocalizedModelTypeLabel(type, locale)}
                        </span>
                      ))}
                    </div>

                    <div className="ai-config-chip-list">
                      {routeCapabilities.length > 0
                        ? routeCapabilities.map(capability => (
                          <span key={capability} className="ai-pill">
                            {getLocalizedCapabilityLabel(capability, locale)}
                          </span>
                        ))
                        : provider.supported_capabilities.map(capability => (
                          <span key={capability} className="ai-pill">
                            {getLocalizedCapabilityLabel(capability, locale)}
                          </span>
                        ))}
                    </div>
                  </button>
                );
              })}
            </div>

            {selectedProvider ? renderSummary(selectedProvider, selectedAdapter) : null}
          </>
        ) : (
          <Card className="ai-config-detail-card agent-config-empty">
            <h4>{copy.emptySummaryTitle}</h4>
            <p className="ai-config-muted">{copy.emptySummaryDesc}</p>
          </Card>
        )
      ) : null}

      <AiProviderEditorDialog
        householdId={householdId}
        locale={locale}
        open={editorOpen}
        adapters={adapters}
        form={form}
        editingProviderId={editingProviderId}
        saving={saving}
        status=""
        copy={copy}
        onClose={closeEditor}
        onSubmit={handleSubmit}
        onAdapterChange={handleAdapterChange}
        onFormChange={setForm}
      />
    </div>
  );
}
