import { useEffect, useMemo, useState, type FormEvent } from 'react';
import { useI18n } from '../../../runtime';
import { getPageMessage } from '../../../runtime/h5-shell/i18n/pageMessageUtils';
import { Card } from '../../family/base';
import {
  buildCreateProviderPayload,
  buildProviderFormState,
  buildRoutePayload,
  buildUpdateProviderPayload,
  getProviderAdapterCode,
  providerSupportsCapability,
  toProviderFormState,
} from '../../setup/setupAiConfig';
import { settingsApi } from '../settingsApi';
import type {
  AiCapability,
  AiCapabilityRoute,
  AiProviderAdapter,
  AiProviderModelType,
  AiProviderProfile,
  PluginRegistryItem,
} from '../settingsTypes';
import { AiProviderDetailDialog } from './AiProviderDetailDialog';
import { AiProviderEditorDialog } from './AiProviderEditorDialog';
import { AiProviderSelectDialog } from './AiProviderSelectDialog';
import { SettingsEmptyState, SettingsPanelCard } from './SettingsSharedBlocks';
import { getLocalizedAdapterMeta, sortCapabilities } from './aiProviderCatalog';

type ProviderFormState = ReturnType<typeof buildProviderFormState>;
const AI_PROVIDER_MODEL_TYPES: AiProviderModelType[] = ['llm', 'embedding', 'vision', 'speech', 'image'];
const AI_CAPABILITIES: AiCapability[] = ['text', 'intent_recognition', 'vision', 'audio_generation', 'audio_recognition', 'image_generation'];
const HIDDEN_PROVIDER_FIELD_KEYS = new Set(['provider_code']);

function normalizeProviderFieldDefaultValue(value: unknown): string | number | boolean | null {
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    return value;
  }
  return null;
}

function normalizeCapabilityList(value: unknown): AiCapability[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map(item => String(item))
    .filter((item): item is AiCapability => AI_CAPABILITIES.includes(item as AiCapability));
}

function buildRegistryAdapter(plugin: PluginRegistryItem): AiProviderAdapter | null {
  const capability = plugin.capabilities.ai_provider;
  if (!plugin.types.includes('ai-provider') || !capability) {
    return null;
  }
  return {
    plugin_id: plugin.id,
    plugin_name: plugin.name,
    adapter_code: capability.adapter_code,
    display_name: capability.display_name,
    description: typeof plugin.compatibility?.description === 'string'
      ? plugin.compatibility.description
      : capability.display_name,
    transport_type: (String(capability.runtime_capability?.transport_type ?? 'openai_compatible') as AiProviderAdapter['transport_type']),
    api_family: (String(capability.runtime_capability?.api_family ?? 'openai_chat_completions') as AiProviderAdapter['api_family']),
    default_privacy_level: (
      String(capability.runtime_capability?.default_privacy_level ?? 'public_cloud') as AiProviderAdapter['default_privacy_level']
    ),
    default_supported_capabilities: normalizeCapabilityList(capability.runtime_capability?.default_supported_capabilities),
    supported_model_types: capability.supported_model_types.filter(
      (item): item is AiProviderModelType => AI_PROVIDER_MODEL_TYPES.includes(item as AiProviderModelType),
    ),
    llm_workflow: capability.llm_workflow,
    supports_model_discovery: Boolean(capability.runtime_capability?.supports_model_discovery),
    field_schema: capability.field_schema
      .filter(field => !HIDDEN_PROVIDER_FIELD_KEYS.has(String(field.key ?? '')))
      .map((field) => ({
        key: String(field.key ?? ''),
        label: String(field.label ?? field.key ?? ''),
        field_type: (
          field.field_type === 'text'
          || field.field_type === 'secret'
          || field.field_type === 'number'
          || field.field_type === 'select'
          || field.field_type === 'boolean'
            ? field.field_type
            : 'text'
        ),
        required: Boolean(field.required),
        placeholder: typeof field.placeholder === 'string' ? field.placeholder : null,
        help_text: typeof field.help_text === 'string' ? field.help_text : null,
        default_value: normalizeProviderFieldDefaultValue(field.default_value),
        options: Array.isArray(field.options)
          ? field.options.map((option) => ({
            label: String(option.label ?? option.value ?? ''),
            value: String(option.value ?? ''),
          }))
          : [],
      })),
  };
}

export function AiProviderConfigPanel(props: {
  householdId: string;
  compact?: boolean;
  capabilityFilter?: AiCapability[];
  onChanged?: () => Promise<void> | void;
}) {
  const { locale, t } = useI18n();
  const { householdId, capabilityFilter, onChanged } = props;
  const [adapters, setAdapters] = useState<AiProviderAdapter[]>([]);
  const [registryPlugins, setRegistryPlugins] = useState<PluginRegistryItem[]>([]);
  const [providers, setProviders] = useState<AiProviderProfile[]>([]);
  const [routes, setRoutes] = useState<AiCapabilityRoute[]>([]);
  const [editingProviderId, setEditingProviderId] = useState<string | null>(null);
  const [selectOpen, setSelectOpen] = useState(false);
  const [editorOpen, setEditorOpen] = useState(false);
  const [detailProviderId, setDetailProviderId] = useState<string | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [form, setForm] = useState<ProviderFormState>(buildProviderFormState());
  const [assignedCapabilities, setAssignedCapabilities] = useState<AiCapability[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');

  const availableAdapterMap = useMemo(
    () => new Map(adapters.map(item => [item.adapter_code, item])),
    [adapters],
  );

  const registryAdapterMap = useMemo(
    () => new Map(
      registryPlugins
        .map(buildRegistryAdapter)
        .filter((item): item is AiProviderAdapter => item !== null)
        .map(item => [item.adapter_code, item]),
    ),
    [registryPlugins],
  );

  const adapterMap = useMemo(
    () => new Map([...registryAdapterMap, ...availableAdapterMap]),
    [availableAdapterMap, registryAdapterMap],
  );

  const visibleProviders = useMemo(
    () => providers.filter(item => !capabilityFilter || capabilityFilter.some(capability => providerSupportsCapability(item, capability))),
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
  const detailPlugin = useMemo(
    () => (detailProvider?.plugin_id ? registryPlugins.find(item => item.id === detailProvider.plugin_id) ?? null : null),
    [detailProvider, registryPlugins],
  );

  const configuredRoutes = useMemo(
    () => routes.filter(item => item.enabled && item.primary_provider_profile_id),
    [routes],
  );

  const summaryStats = useMemo(
    () => [
      { label: getPageMessage(locale, 'settings.ai.provider.summary.totalModels'), value: String(visibleProviders.length) },
      {
        label: getPageMessage(locale, 'settings.ai.provider.summary.enabledModels'),
        value: String(visibleProviders.filter(item => item.enabled && item.plugin_enabled !== false).length),
      },
      { label: getPageMessage(locale, 'settings.ai.provider.summary.activeRoutes'), value: String(configuredRoutes.length) },
      { label: getPageMessage(locale, 'settings.ai.provider.summary.plugins'), value: String(new Set([...adapterMap.values()].map(item => item.plugin_id)).size) },
    ],
    [adapterMap, configuredRoutes.length, locale, visibleProviders],
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
    pluginDisabled: getPageMessage(locale, 'settings.ai.provider.pluginDisabled'),
    pluginDisabledTitle: getPageMessage(locale, 'settings.ai.provider.pluginDisabledTitle'),
    pluginDisabledFallback: getPageMessage(locale, 'settings.ai.provider.pluginDisabledFallback'),
    modelNameEmpty: getPageMessage(locale, 'settings.ai.provider.modelNameEmpty'),
    editTitle: getPageMessage(locale, 'settings.ai.provider.editTitle'),
    addTitle: getPageMessage(locale, 'settings.ai.provider.addTitle'),
    formDescription: getPageMessage(locale, 'settings.ai.provider.formDescription'),
    providerTypeLabel: getPageMessage(locale, 'settings.ai.provider.providerTypeLabel'),
    selectPlaceholder: getPageMessage(locale, 'settings.ai.provider.selectPlaceholder'),
    assignedCapabilityLabel: getPageMessage(locale, 'settings.ai.provider.assignedCapabilityLabel'),
    assignedCapabilityHint: getPageMessage(locale, 'settings.ai.provider.assignedCapabilityHint'),
    enableAfterSave: getPageMessage(locale, 'settings.ai.provider.enableAfterSave'),
    saveProvider: getPageMessage(locale, 'settings.ai.provider.saveProvider'),
    submitAddProvider: getPageMessage(locale, 'settings.ai.provider.submitAddProvider'),
    chooseProviderPlugin: getPageMessage(locale, 'settings.ai.provider.chooseProviderPlugin'),
    chooseProviderPluginDesc: getPageMessage(locale, 'settings.ai.provider.chooseProviderPluginDesc'),
    supportedModelTypes: getPageMessage(locale, 'settings.ai.provider.supportedModelTypes'),
    llmWorkflow: getPageMessage(locale, 'settings.ai.provider.llmWorkflow'),
    refreshModels: getPageMessage(locale, 'settings.ai.provider.refreshModels'),
    discoveringModels: getPageMessage(locale, 'settings.ai.provider.discoveringModels'),
    discoveredModels: getPageMessage(locale, 'settings.ai.provider.discoveredModels'),
    noModelsDiscovered: getPageMessage(locale, 'settings.ai.provider.noModelsDiscovered'),
    discoveryHint: getPageMessage(locale, 'settings.ai.provider.discoveryHint'),
    back: getPageMessage(locale, 'settings.ai.provider.back'),
    summaryTitle: getPageMessage(locale, 'settings.ai.provider.summaryTitle'),
    summaryDesc: getPageMessage(locale, 'settings.ai.provider.summaryDesc'),
    summaryConfigTitle: getPageMessage(locale, 'settings.ai.provider.summaryConfigTitle'),
    summaryRouteTitle: getPageMessage(locale, 'settings.ai.provider.summaryRouteTitle'),
    summaryRouteEmpty: getPageMessage(locale, 'settings.ai.provider.summaryRouteEmpty'),
    emptySummaryTitle: getPageMessage(locale, 'settings.ai.provider.emptySummaryTitle'),
    emptySummaryDesc: getPageMessage(locale, 'settings.ai.provider.emptySummaryDesc'),
    pluginLabel: getPageMessage(locale, 'settings.ai.provider.pluginLabel'),
    pluginVersionLabel: getPageMessage(locale, 'settings.ai.provider.pluginVersionLabel'),
    pluginUpdateStateLabel: getPageMessage(locale, 'settings.ai.provider.pluginUpdateStateLabel'),
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
        const [adapterRows, providerRows, routeRows, registrySnapshot] = await Promise.all([
          settingsApi.listAiProviderAdapters(householdId),
          settingsApi.listHouseholdAiProviders(householdId),
          settingsApi.listHouseholdAiRoutes(householdId),
          settingsApi.listRegisteredPlugins(householdId),
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
          supports_model_discovery: item.supports_model_discovery ?? false,
        })));
        setProviders(providerRows);
        setRoutes(routeRows);
        setRegistryPlugins(registrySnapshot.items);
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
    setAssignedCapabilities([]);
    setError('');
    setSelectOpen(true);
  }

  function selectAdapter(adapterCode: string) {
    const adapter = adapterMap.get(adapterCode) ?? null;
    if (adapter) {
      setForm(buildProviderFormState(adapter));
    }
    setAssignedCapabilities([]);
    setSelectOpen(false);
    setEditorOpen(true);
  }

  function goBackToSelect() {
    setEditorOpen(false);
    setSelectOpen(true);
  }

  function startEdit(provider: AiProviderProfile) {
    const adapter = adapterMap.get(getProviderAdapterCode(provider)) ?? null;
    const routeCapabilities = routes
      .filter(item => item.enabled && item.primary_provider_profile_id === provider.id)
      .map(item => item.capability);
    setEditingProviderId(provider.id);
    setForm(toProviderFormState(provider, adapter));
    setAssignedCapabilities(
      sortCapabilities(routeCapabilities.length > 0 ? routeCapabilities : provider.supported_capabilities) as AiCapability[],
    );
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
    setAssignedCapabilities([]);
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
    setAssignedCapabilities([]);
  }

  function buildDisabledRoutePayload(capability: AiCapability, currentRoute?: AiCapabilityRoute) {
    return {
      capability,
      household_id: householdId,
      primary_provider_profile_id: null,
      fallback_provider_profile_ids: [],
      routing_mode: 'template_only',
      timeout_ms: currentRoute?.timeout_ms ?? 15000,
      max_retry_count: currentRoute?.max_retry_count ?? 0,
      allow_remote: currentRoute?.allow_remote ?? true,
      prompt_policy: currentRoute?.prompt_policy ?? {},
      response_policy: currentRoute?.response_policy ?? {},
      enabled: false,
    };
  }

  async function syncAssignedCapabilityRoutes(providerId: string, supportedCapabilities: AiCapability[]) {
    const supportedCapabilitySet = new Set(supportedCapabilities);
    const desiredAssignedCapabilities = sortCapabilities(
      assignedCapabilities.filter(capability => supportedCapabilitySet.has(capability)),
    ) as AiCapability[];
    const currentAssignedCapabilities = routes
      .filter(item => item.enabled && item.primary_provider_profile_id === providerId)
      .map(item => item.capability);
    const capabilitiesToSync = sortCapabilities([
      ...desiredAssignedCapabilities,
      ...currentAssignedCapabilities,
    ]) as AiCapability[];

    if (capabilitiesToSync.length === 0) {
      return;
    }

    await Promise.all(capabilitiesToSync.map(async (capability) => {
      const currentRoute = routes.find(item => item.capability === capability);
      if (desiredAssignedCapabilities.includes(capability)) {
        await settingsApi.upsertHouseholdAiRoute(
          householdId,
          capability,
          buildRoutePayload(householdId, capability, currentRoute, providerId, true),
        );
        return;
      }

      if (currentRoute?.primary_provider_profile_id === providerId) {
        await settingsApi.upsertHouseholdAiRoute(
          householdId,
          capability,
          buildDisabledRoutePayload(capability, currentRoute),
        );
      }
    }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const currentAdapter = adapterMap.get(form.adapterCode) ?? null;
    if (!currentAdapter) {
      setError(copy.selectTypeFirst);
      return;
    }

    setSaving(true);
    setError('');
    setStatus('');
    try {
      const nextSupportedCapabilities = sortCapabilities(assignedCapabilities) as AiCapability[];
      if (nextSupportedCapabilities.length === 0) {
        setError(copy.selectTypeFirst);
        return;
      }
      if (editingProviderId) {
        const payload = buildUpdateProviderPayload(form, currentAdapter);
        payload.supported_capabilities = nextSupportedCapabilities;
        const savedProvider = await settingsApi.updateHouseholdAiProvider(
          householdId,
          editingProviderId,
          payload,
        );
        await syncAssignedCapabilityRoutes(savedProvider.id, nextSupportedCapabilities);
        setStatus(copy.updatedStatus);
      } else {
        const payload = buildCreateProviderPayload(form, currentAdapter);
        payload.supported_capabilities = nextSupportedCapabilities;
        const savedProvider = await settingsApi.createHouseholdAiProvider(
          householdId,
          payload,
        );
        await syncAssignedCapabilityRoutes(savedProvider.id, nextSupportedCapabilities);
        setStatus(copy.addedStatus);
      }

      await reload();
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
                const pluginDisabled = provider.plugin_enabled === false;
                const availabilityLabel = pluginDisabled ? copy.pluginDisabled : (provider.enabled ? copy.enabled : copy.disabled);

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
                      {pluginDisabled ? (
                        <div className="ai-config-muted">
                          {provider.plugin_disabled_reason || copy.pluginDisabledFallback}
                        </div>
                      ) : null}
                    </div>
                    <span className={`ai-pill ai-pill--sm ${pluginDisabled ? 'ai-pill--warning' : provider.enabled ? 'ai-pill--success' : 'ai-pill--muted'}`}>
                      {availabilityLabel}
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
        plugin={detailPlugin}
        routes={routes}
        locale={locale}
        copy={{
          enabled: copy.enabled,
          disabled: copy.disabled,
          pluginDisabled: copy.pluginDisabled,
          pluginDisabledTitle: copy.pluginDisabledTitle,
          pluginDisabledFallback: copy.pluginDisabledFallback,
          modelNameEmpty: copy.modelNameEmpty,
          pluginLabel: copy.pluginLabel,
          pluginVersionLabel: copy.pluginVersionLabel,
          pluginUpdateStateLabel: copy.pluginUpdateStateLabel,
          llmWorkflow: copy.llmWorkflow,
          updatedAtLabel: copy.updatedAtLabel,
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
        resolvedAdapter={adapterMap.get(form.adapterCode) ?? null}
        form={form}
        assignedCapabilities={assignedCapabilities}
        editingProviderId={editingProviderId}
        saving={saving}
        status=""
        copy={copy}
        onClose={closeEditor}
        onBack={!editingProviderId ? goBackToSelect : undefined}
        onSubmit={handleSubmit}
        onAdapterChange={handleAdapterChange}
        onFormChange={setForm}
        onAssignedCapabilitiesChange={(capabilities) => setAssignedCapabilities(sortCapabilities(capabilities) as AiCapability[])}
      />

      <AiProviderSelectDialog
        locale={locale}
        open={selectOpen}
        adapters={[...registryAdapterMap.values(), ...adapters].filter(
          (item, index, self) => self.findIndex(i => i.adapter_code === item.adapter_code) === index
        )}
        copy={{
          title: copy.chooseProviderPlugin,
          description: copy.chooseProviderPluginDesc,
          close: copy.close,
        }}
        onSelect={selectAdapter}
        onClose={() => setSelectOpen(false)}
      />
    </div>
  );
}
