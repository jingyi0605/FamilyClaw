import { useEffect, useMemo, useState, type FormEvent } from 'react';
import { useI18n } from '../../../runtime';
import { getPageMessage } from '../../../runtime/h5-shell/i18n/pageMessageUtils';
import { Card } from '../../family/base';
import {
  buildCreateProviderPayload,
  buildProviderFormState,
  buildUpdateProviderPayload,
  getProviderAdapterCode,
  toProviderFormState,
} from '../../setup/setupAiConfig';
import { settingsApi } from '../settingsApi';
import type {
  AiCapabilityRoute,
  AiProviderAdapter,
  AiProviderProfile,
} from '../settingsTypes';
import { AiProviderDetailDialog } from './AiProviderDetailDialog';
import { AiProviderEditorDialog } from './AiProviderEditorDialog';
import { SettingsEmptyState, SettingsPanelCard } from './SettingsSharedBlocks';
import { getLocalizedAdapterMeta } from './aiProviderCatalog';

type ProviderFormState = ReturnType<typeof buildProviderFormState>;

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
  const [editingProviderId, setEditingProviderId] = useState<string | null>(null);
  const [editorOpen, setEditorOpen] = useState(false);
  const [detailProviderId, setDetailProviderId] = useState<string | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
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

  const detailProvider = useMemo(
    () => providers.find(item => item.id === detailProviderId) ?? null,
    [detailProviderId, providers],
  );

  const detailAdapter = useMemo(
    () => (detailProvider ? adapterMap.get(getProviderAdapterCode(detailProvider)) ?? null : null),
    [adapterMap, detailProvider],
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
    close: t('common.close'),
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

  async function reload() {
    const [providerRows, routeRows] = await Promise.all([
      settingsApi.listHouseholdAiProviders(householdId),
      settingsApi.listHouseholdAiRoutes(householdId),
    ]);
    setProviders(providerRows);
    setRoutes(routeRows);
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
    setForm(toProviderFormState(provider, adapter));
    setError('');
    setDetailOpen(false);
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

  function openDetail(provider: AiProviderProfile) {
    setDetailProviderId(provider.id);
    setDetailOpen(true);
  }

  function closeDetail() {
    setDetailOpen(false);
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
        await reload();
      } else {
        await settingsApi.createHouseholdAiProvider(
          householdId,
          buildCreateProviderPayload(form, currentAdapter),
        );
        setStatus(copy.addedStatus);
        await reload();
      }
      closeEditor();
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : copy.saveFailed);
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(provider: AiProviderProfile) {
    if (globalThis.confirm && !globalThis.confirm(copy.deleteConfirm)) {
      return;
    }

    setSaving(true);
    setError('');
    setStatus('');
    try {
      await settingsApi.deleteHouseholdAiProvider(householdId, provider.id);
      setStatus(copy.deletedStatus);
      setDetailOpen(false);
      await reload();
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : copy.deleteFailed);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="ai-provider-center">
      <SettingsPanelCard
        title={copy.summaryTitle}
        description={copy.summaryDesc}
        actions={(
          <button className="btn btn--primary btn--sm" type="button" onClick={startCreate}>
            {copy.addProvider}
          </button>
        )}
      >
        <div className="ai-provider-summary-grid ai-provider-summary-grid--top">
          {summaryStats.map(item => (
            <div key={item.label} className="ai-provider-summary-stat">
              <span>{item.label}</span>
              <strong>{item.value}</strong>
            </div>
          ))}
        </div>
        {status ? <div className="setup-form-status">{status}</div> : null}
      </SettingsPanelCard>

      {error ? <Card><p className="form-error">{error}</p></Card> : null}
      {loading ? <div className="settings-loading-copy settings-loading-copy--center">{copy.loading}</div> : null}

      {!loading ? (
        visibleProviders.length > 0 ? (
          <Card className="ai-provider-list-card">
            <div className="ai-provider-simple-list">
              {visibleProviders.map(provider => {
                const adapter = adapterMap.get(getProviderAdapterCode(provider)) ?? null;
                const adapterMeta = adapter ? getLocalizedAdapterMeta(adapter, locale) : null;

                return (
                  <button
                    key={provider.id}
                    type="button"
                    className="ai-provider-simple-item"
                    onClick={() => openDetail(provider)}
                  >
                    <div className="ai-provider-simple-item__icon">AI</div>
                    <div className="ai-provider-simple-item__content">
                      <div className="ai-provider-simple-item__name">{provider.display_name}</div>
                      <div className="ai-provider-simple-item__meta">{adapterMeta?.label ?? provider.provider_code}</div>
                    </div>
                    <span className={`ai-pill ai-pill--sm ${provider.enabled ? 'ai-pill--success' : 'ai-pill--muted'}`}>
                      {provider.enabled ? copy.enabled : copy.disabled}
                    </span>
                  </button>
                );
              })}
            </div>
          </Card>
        ) : (
          <SettingsEmptyState
            icon="AI"
            title={copy.emptySummaryTitle}
            description={copy.emptySummaryDesc}
            action={(
              <button className="btn btn--primary" type="button" onClick={startCreate}>
                {copy.addProvider}
              </button>
            )}
          />
        )
      ) : null}

      <AiProviderDetailDialog
        open={detailOpen}
        provider={detailProvider}
        adapter={detailAdapter}
        routes={routes}
        locale={locale}
        copy={{
          enabled: copy.enabled,
          disabled: copy.disabled,
          modelNameEmpty: copy.modelNameEmpty,
          pluginLabel: copy.pluginLabel,
          llmWorkflow: copy.llmWorkflow,
          updatedAtLabel: copy.updatedAtLabel,
          summarySupportTitle: copy.summarySupportTitle,
          summaryRouteTitle: copy.summaryRouteTitle,
          summaryRouteEmpty: copy.summaryRouteEmpty,
          summaryConfigTitle: copy.summaryConfigTitle,
          close: copy.close,
          edit: copy.editProvider,
        }}
        onClose={closeDetail}
        onEdit={() => {
          if (detailProvider) {
            startEdit(detailProvider);
          }
        }}
      />

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
