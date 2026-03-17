import { useEffect, useMemo, useState } from 'react';
import Taro from '@tarojs/taro';
import { Home, Check, Plug } from 'lucide-react';
import { GuardedPage, useHouseholdContext, useI18n } from '../../../runtime';
import { getPageMessage } from '../../../runtime/h5-shell/i18n/pageMessageUtils';
import { Card, Section } from '../../family/base';
import { IntegrationSyncedDevicePreviewDialog } from '../../device-management/IntegrationSyncedDevicePreviewDialog';
import { SettingsPageShell } from '../SettingsPageShell';
import { ApiError, settingsApi } from '../settingsApi';
import {
  buildSyncAllImpactSummary,
  filterIntegrationDeviceCandidates,
  getCandidateDomainOptions,
  getCandidateEntityDomain,
  getCandidateRoomOptions,
  type IntegrationDeviceCandidate,
  type SyncAllImpactSummary,
} from './integrationSyncHelpers';
import type {
  IntegrationActionResult,
  IntegrationCatalogItem,
  IntegrationInstance,
  IntegrationResource,
  PluginManifestConfigField,
  PluginManifestFieldUiSchema,
} from '../settingsTypes';

type CreateDraft = {
  displayName: string;
  values: Record<string, unknown>;
  secrets: Record<string, string>;
  fieldErrors: Record<string, string>;
};

type SyncAllConfirmStep = 'first' | 'second' | null;

function getActionOutputItems<T>(result: IntegrationActionResult): T[] {
  const items = result.output.items;
  return Array.isArray(items) ? (items as T[]) : [];
}

function getActionOutputSummary<T>(result: IntegrationActionResult): T | null {
  const summary = result.output.summary;
  return summary && typeof summary === 'object' ? (summary as T) : null;
}

function buildDraft(item: IntegrationCatalogItem | null): CreateDraft {
  const values: Record<string, unknown> = {};
  for (const field of item?.config_spec?.config_schema.fields ?? []) {
    if (field.default !== undefined && field.type !== 'secret') {
      values[field.key] = field.default;
    }
  }
  return {
    displayName: item?.name ?? '',
    values,
    secrets: {},
    fieldErrors: {},
  };
}

function getScalarValue(values: Record<string, unknown>, key: string): string {
  const value = values[key];
  if (typeof value === 'string') {
    return value;
  }
  if (typeof value === 'number') {
    return String(value);
  }
  return '';
}

function normalizeSubmitValue(field: PluginManifestConfigField, value: unknown): unknown {
  if (field.type === 'boolean') {
    return value === true;
  }
  if (field.type === 'integer' || field.type === 'number') {
    if (typeof value === 'number') {
      return value;
    }
    if (typeof value === 'string' && value.trim()) {
      const parsed = Number(value.trim());
      return Number.isFinite(parsed) ? parsed : value;
    }
  }
  if (field.type === 'string' || field.type === 'text' || field.type === 'secret' || field.type === 'enum') {
    return typeof value === 'string' ? value.trim() : value;
  }
  return value;
}

function SettingsIntegrationsContent() {
  const { locale } = useI18n();
  const { currentHouseholdId } = useHouseholdContext();
  const page = (
    key: Parameters<typeof getPageMessage>[1],
    params?: Record<string, string | number>,
  ) => getPageMessage(locale, key, params);

  const [catalog, setCatalog] = useState<IntegrationCatalogItem[]>([]);
  const [instances, setInstances] = useState<IntegrationInstance[]>([]);
  const [deviceResources, setDeviceResources] = useState<IntegrationResource[]>([]);
  const [selectedInstanceId, setSelectedInstanceId] = useState<string | null>(null);
  const [selectedCatalogItem, setSelectedCatalogItem] = useState<IntegrationCatalogItem | null>(null);
  const [createDraft, setCreateDraft] = useState<CreateDraft>(() => buildDraft(null));
  const [deviceCandidates, setDeviceCandidates] = useState<IntegrationDeviceCandidate[]>([]);
  const [selectedDeviceIds, setSelectedDeviceIds] = useState<string[]>([]);
  const [catalogModalOpen, setCatalogModalOpen] = useState(false);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [deviceModalOpen, setDeviceModalOpen] = useState(false);
  const [syncedPreviewOpen, setSyncedPreviewOpen] = useState(false);
  const [syncAllConfirmStep, setSyncAllConfirmStep] = useState<SyncAllConfirmStep>(null);
  const [syncAllImpactSummary, setSyncAllImpactSummary] = useState<SyncAllImpactSummary | null>(null);
  const [syncAllLoading, setSyncAllLoading] = useState(false);
  const [candidateKeyword, setCandidateKeyword] = useState('');
  const [candidateRoomFilter, setCandidateRoomFilter] = useState('all');
  const [candidateDomainFilter, setCandidateDomainFilter] = useState('all');
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    void Taro.setNavigationBarTitle({ title: page('settings.integrations.title') }).catch(() => undefined);
  }, [locale]);

  async function reload(householdId: string, preferredInstanceId?: string | null) {
    setLoading(true);
    try {
      const view = await settingsApi.getIntegrationPageView(householdId);
      setCatalog(view.catalog);
      setInstances(view.instances);
      setDeviceResources(view.resources.device ?? []);
      setSelectedInstanceId((current) => {
        const nextId = preferredInstanceId ?? current;
        if (nextId && view.instances.some((item) => item.id === nextId)) {
          return nextId;
        }
        return view.instances[0]?.id ?? null;
      });
      setError('');
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : page('settings.integrations.error.loadIntegrationFailed'));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!currentHouseholdId) {
      setCatalog([]);
      setInstances([]);
      setDeviceResources([]);
      setSelectedInstanceId(null);
      return;
    }
    void reload(currentHouseholdId);
  }, [currentHouseholdId]);

  const selectedInstance = useMemo(
    () => instances.find((item) => item.id === selectedInstanceId) ?? null,
    [instances, selectedInstanceId],
  );
  const selectedDevices = useMemo(
    () => deviceResources.filter((item) => item.integration_instance_id === selectedInstanceId),
    [deviceResources, selectedInstanceId],
  );
  const candidateRoomOptions = useMemo(() => getCandidateRoomOptions(deviceCandidates), [deviceCandidates]);
  const candidateDomainOptions = useMemo(() => getCandidateDomainOptions(deviceCandidates), [deviceCandidates]);
  const filteredDeviceCandidates = useMemo(() => filterIntegrationDeviceCandidates(deviceCandidates, {
    keyword: candidateKeyword,
    room: candidateRoomFilter,
    domain: candidateDomainFilter,
  }), [candidateDomainFilter, candidateKeyword, candidateRoomFilter, deviceCandidates]);

  useEffect(() => {
    setSyncedPreviewOpen(false);
    setSyncAllConfirmStep(null);
    setSyncAllImpactSummary(null);
  }, [selectedInstanceId]);

  function formatStatus(instance: IntegrationInstance) {
    if (instance.status === 'degraded') {
      return page('settings.integrations.instance.status.degraded');
    }
    if (instance.status === 'disabled') {
      return page('settings.integrations.instance.status.disabled');
    }
    if (instance.status === 'draft' || instance.config_state !== 'configured') {
      return page('settings.integrations.instance.status.draft');
    }
    return page('settings.integrations.instance.status.active');
  }

  function openCreateModal(item: IntegrationCatalogItem) {
    setSelectedCatalogItem(item);
    setCreateDraft(buildDraft(item));
    setCatalogModalOpen(false);
    setCreateModalOpen(true);
  }

  function closeCreateModal() {
    setCreateModalOpen(false);
    setSelectedCatalogItem(null);
    setCreateDraft(buildDraft(null));
  }

  function updateValue(fieldKey: string, value: unknown) {
    setCreateDraft((current) => ({
      ...current,
      values: { ...current.values, [fieldKey]: value },
      fieldErrors: { ...current.fieldErrors, [fieldKey]: '' },
    }));
  }

  function updateSecret(fieldKey: string, value: string) {
    setCreateDraft((current) => ({
      ...current,
      secrets: { ...current.secrets, [fieldKey]: value },
      fieldErrors: { ...current.fieldErrors, [fieldKey]: '' },
    }));
  }

  function renderField(field: PluginManifestConfigField, widget?: PluginManifestFieldUiSchema) {
    const fieldError = createDraft.fieldErrors[field.key];
    if (field.type === 'secret') {
      return (
        <div key={field.key} className="form-group">
          <label>{field.label}</label>
          <input
            className="form-input"
            type="password"
            value={createDraft.secrets[field.key] ?? ''}
            onChange={(event) => updateSecret(field.key, event.target.value)}
            placeholder={widget?.placeholder ?? undefined}
          />
          <div className="form-help">{widget?.help_text ?? field.description ?? ''}</div>
          {fieldError ? <div className="form-help">{fieldError}</div> : null}
        </div>
      );
    }
    if (field.type === 'boolean') {
      return (
        <div key={field.key} className="form-group">
          <label>{field.label}</label>
          <select
            className="form-select"
            value={createDraft.values[field.key] === true ? 'true' : 'false'}
            onChange={(event) => updateValue(field.key, event.target.value === 'true')}
          >
            <option value="false">{page('settings.integrations.modal.config.booleanFalse')}</option>
            <option value="true">{page('settings.integrations.modal.config.booleanTrue')}</option>
          </select>
          <div className="form-help">{widget?.help_text ?? field.description ?? ''}</div>
          {fieldError ? <div className="form-help">{fieldError}</div> : null}
        </div>
      );
    }
    if (field.type === 'enum') {
      return (
        <div key={field.key} className="form-group">
          <label>{field.label}</label>
          <select
            className="form-select"
            value={getScalarValue(createDraft.values, field.key)}
            onChange={(event) => updateValue(field.key, event.target.value)}
          >
            <option value="">{page('settings.integrations.modal.config.selectPlaceholder')}</option>
            {(field.enum_options ?? []).map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
          <div className="form-help">{widget?.help_text ?? field.description ?? ''}</div>
          {fieldError ? <div className="form-help">{fieldError}</div> : null}
        </div>
      );
    }
    if (field.type === 'text') {
      return (
        <div key={field.key} className="form-group">
          <label>{field.label}</label>
          <textarea
            className="form-input"
            value={getScalarValue(createDraft.values, field.key)}
            onChange={(event) => updateValue(field.key, event.target.value)}
            placeholder={widget?.placeholder ?? undefined}
          />
          <div className="form-help">{widget?.help_text ?? field.description ?? ''}</div>
          {fieldError ? <div className="form-help">{fieldError}</div> : null}
        </div>
      );
    }
    return (
      <div key={field.key} className="form-group">
        <label>{field.label}</label>
        <input
          className="form-input"
          type={field.type === 'integer' || field.type === 'number' ? 'number' : 'text'}
          value={getScalarValue(createDraft.values, field.key)}
          onChange={(event) => updateValue(field.key, event.target.value)}
          placeholder={widget?.placeholder ?? undefined}
        />
        <div className="form-help">{widget?.help_text ?? field.description ?? ''}</div>
        {fieldError ? <div className="form-help">{fieldError}</div> : null}
      </div>
    );
  }

  async function handleCreateInstance(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!currentHouseholdId || !selectedCatalogItem?.config_spec) {
      return;
    }
    if (!createDraft.displayName.trim()) {
      setCreateDraft((current) => ({
        ...current,
        fieldErrors: {
          ...current.fieldErrors,
          display_name: page('settings.integrations.modal.create.displayNameRequired'),
        },
      }));
      return;
    }

    const payloadValues: Record<string, unknown> = {};
    for (const field of selectedCatalogItem.config_spec.config_schema.fields) {
      const rawValue = field.type === 'secret'
        ? (createDraft.secrets[field.key] ?? '')
        : createDraft.values[field.key];
      if (field.type === 'secret' && typeof rawValue === 'string' && !rawValue.trim()) {
        continue;
      }
      if (rawValue === undefined) {
        continue;
      }
      payloadValues[field.key] = normalizeSubmitValue(field, rawValue);
    }

    setSubmitting(true);
    try {
      const instance = await settingsApi.createIntegrationInstance({
        household_id: currentHouseholdId,
        plugin_id: selectedCatalogItem.plugin_id,
        display_name: createDraft.displayName.trim(),
        config: payloadValues,
        clear_secret_fields: [],
      });
      setStatus(page('settings.integrations.status.instanceCreated', { name: instance.display_name }));
      closeCreateModal();
      await reload(currentHouseholdId, instance.id);
    } catch (submitError) {
      if (submitError instanceof ApiError) {
        const payload = submitError.payload as { detail?: { field_errors?: Record<string, string> } } | undefined;
        if (payload?.detail?.field_errors) {
          setCreateDraft((current) => ({
            ...current,
            fieldErrors: {
              ...current.fieldErrors,
              ...payload.detail!.field_errors!,
            },
          }));
        }
      }
      setError(submitError instanceof Error ? submitError.message : page('settings.integrations.error.actionFailed'));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleOpenSyncAllConfirm() {
    if (!selectedInstance) {
      return;
    }
    setSyncAllLoading(true);
    try {
      const result = await settingsApi.executeIntegrationInstanceAction(selectedInstance.id, {
        action: 'sync',
        payload: {
          sync_scope: 'device_candidates',
        },
      });
      const candidates = getActionOutputItems<IntegrationDeviceCandidate>(result);
      setSyncAllImpactSummary(buildSyncAllImpactSummary(candidates));
      setSyncAllConfirmStep('first');
      setError('');
    } catch (syncError) {
      setError(syncError instanceof Error ? syncError.message : page('settings.integrations.error.loadHaDevicesFailed'));
    } finally {
      setSyncAllLoading(false);
    }
  }

  async function handleSyncAll() {
    if (!selectedInstance) {
      return;
    }
    setSubmitting(true);
    try {
      const result = await settingsApi.executeIntegrationInstanceAction(selectedInstance.id, {
        action: 'sync',
        payload: {
          sync_scope: 'device_sync',
          selected_external_ids: [],
        },
      });
      const summary = getActionOutputSummary<{ created_devices: number; updated_devices: number }>(result);
      setStatus(page('settings.integrations.status.deviceSyncFinished', {
        count: (summary?.created_devices ?? 0) + (summary?.updated_devices ?? 0),
      }));
      setSyncAllConfirmStep(null);
      setSyncAllImpactSummary(null);
      await reload(currentHouseholdId ?? '', selectedInstance.id);
    } catch (syncError) {
      setError(syncError instanceof Error ? syncError.message : page('settings.integrations.error.actionFailed'));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleOpenPicker() {
    if (!selectedInstance) {
      return;
    }
    setSubmitting(true);
    try {
      const result = await settingsApi.executeIntegrationInstanceAction(selectedInstance.id, {
        action: 'sync',
        payload: {
          sync_scope: 'device_candidates',
        },
      });
      setDeviceCandidates(getActionOutputItems<IntegrationDeviceCandidate>(result));
      setSelectedDeviceIds([]);
      setCandidateKeyword('');
      setCandidateRoomFilter('all');
      setCandidateDomainFilter('all');
      setDeviceModalOpen(true);
    } catch (syncError) {
      setError(syncError instanceof Error ? syncError.message : page('settings.integrations.error.loadHaDevicesFailed'));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleSyncSelected() {
    if (!selectedInstance) {
      return;
    }
    setSubmitting(true);
    try {
      const result = await settingsApi.executeIntegrationInstanceAction(selectedInstance.id, {
        action: 'sync',
        payload: {
          sync_scope: 'device_sync',
          selected_external_ids: selectedDeviceIds,
        },
      });
      const summary = getActionOutputSummary<{ created_devices: number; updated_devices: number }>(result);
      setStatus(page('settings.integrations.status.deviceSyncFinished', {
        count: (summary?.created_devices ?? 0) + (summary?.updated_devices ?? 0),
      }));
      setDeviceModalOpen(false);
      setSelectedDeviceIds([]);
      await reload(currentHouseholdId ?? '', selectedInstance.id);
    } catch (syncError) {
      setError(syncError instanceof Error ? syncError.message : page('settings.integrations.error.actionFailed'));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <SettingsPageShell activeKey="integrations">
      <div className="settings-page settings-page--integrations">
        {status ? <div className="settings-status">{status}</div> : null}
        {error ? <div className="settings-error">{error}</div> : null}

        <Section title={page('settings.integrations.section.integrations')}>
          {loading ? (
            <Card>
              <div className="integration-status__detail">{page('settings.integrations.loading')}</div>
            </Card>
          ) : instances.length === 0 && deviceResources.length === 0 ? (
            <Card>
              <div className="settings-empty-state">
                <h3>{page('settings.integrations.empty.title')}</h3>
                <p>{page('settings.integrations.empty.desc')}</p>
                <button className="btn btn--primary btn--sm" type="button" onClick={() => setCatalogModalOpen(true)}>
                  {page('settings.integrations.action.addByInstance')}
                </button>
              </div>
            </Card>
          ) : (
            <>
              <div className="integration-instances-grid">
                {instances.map((instance) => (
                  <button
                    key={instance.id}
                    type="button"
                    className={`integration-instance-card ${selectedInstanceId === instance.id ? 'integration-instance-card--active' : ''}`}
                    onClick={() => setSelectedInstanceId(instance.id)}
                  >
                    <div className="integration-instance-card__header">
                      <strong className="integration-instance-card__name">{instance.display_name}</strong>
                      <span className={`badge badge--${instance.status === 'degraded' ? 'warning' : 'success'}`}>
                        {formatStatus(instance)}
                      </span>
                    </div>
                    <div className="integration-instance-card__plugin">
                      <span className="integration-instance-card__plugin-label">插件</span>
                      <span className="integration-instance-card__plugin-name">{instance.plugin_id}</span>
                    </div>
                    <div className="integration-instance-card__meta">
                      {page('settings.integrations.instance.resourceCount', { count: instance.resource_counts.device })}
                    </div>
                  </button>
                ))}
                <button
                  type="button"
                  className="integration-instance-card integration-instance-card--adder"
                  onClick={() => setCatalogModalOpen(true)}
                >
                  <span className="integration-instance-card__adder-icon">+</span>
                  <span className="integration-instance-card__adder-text">{page('settings.integrations.action.addByInstance')}</span>
                </button>
              </div>

              {selectedInstance ? (
                <div className="integration-detail-panel">
                  <div className="integration-detail-panel__header">
                    <div className="integration-detail-panel__title-row">
                      <h4 className="integration-detail-panel__title">{selectedInstance.display_name}</h4>
                      <span className={`badge badge--${selectedInstance.status === 'degraded' ? 'warning' : 'success'}`}>
                        {formatStatus(selectedInstance)}
                      </span>
                    </div>
                    <div className="integration-detail-panel__subtitle">
                      {page('settings.integrations.instance.pluginInfo', { plugin: selectedInstance.plugin_id })}
                    </div>
                  </div>

                  <div className="integration-detail-panel__stats">
                    <div className="integration-detail-panel__stat">
                      <span className="integration-detail-panel__stat-value">{selectedInstance.resource_counts.device}</span>
                      <span className="integration-detail-panel__stat-label">{page('settings.integrations.instance.devicesLabel')}</span>
                    </div>
                    <div className="integration-detail-panel__stat">
                      <span className="integration-detail-panel__stat-value">
                        {selectedInstance.sync_state.last_synced_at
                          ? page('settings.integrations.instance.lastSyncShort', { time: selectedInstance.sync_state.last_synced_at })
                          : '-'}
                      </span>
                      <span className="integration-detail-panel__stat-label">{page('settings.integrations.instance.lastSyncLabel')}</span>
                    </div>
                  </div>

                  {selectedInstance.last_error?.message ? (
                    <div className="integration-detail-panel__error">
                      {selectedInstance.last_error.message}
                    </div>
                  ) : null}

                  <div className="integration-detail-panel__actions">
                    <button
                      className="btn btn--primary btn--sm"
                      type="button"
                      onClick={() => void handleOpenSyncAllConfirm()}
                      disabled={submitting || syncAllLoading || selectedInstance.config_state !== 'configured'}
                    >
                      {page('settings.integrations.action.syncAllEntities')}
                    </button>
                    <button
                      className="btn btn--outline btn--sm"
                      type="button"
                      onClick={() => void handleOpenPicker()}
                      disabled={submitting || selectedInstance.config_state !== 'configured'}
                    >
                      {page('settings.integrations.action.syncSelectedEntities')}
                    </button>
                    <button
                      className="btn btn--outline btn--sm"
                      type="button"
                      onClick={() => setSyncedPreviewOpen(true)}
                    >
                      {page('settings.integrations.action.viewSyncedDevices')}
                    </button>
                  </div>
                </div>
              ) : (
                <div className="integration-detail-placeholder">
                  <p>{page('settings.integrations.instance.selectHint')}</p>
                </div>
              )}
            </>
          )}
        </Section>

        <IntegrationSyncedDevicePreviewDialog
          open={syncedPreviewOpen}
          instanceName={selectedInstance?.display_name ?? ''}
          devices={selectedDevices}
          page={page}
          onClose={() => setSyncedPreviewOpen(false)}
        />

        {syncAllConfirmStep ? (
          <div className="member-modal-overlay" onClick={() => setSyncAllConfirmStep(null)}>
            <div className="member-modal" onClick={(event) => event.stopPropagation()}>
              <div className="member-modal__header">
                <div>
                  <h3>{page('settings.integrations.syncAll.confirm.title')}</h3>
                  <p>
                    {syncAllConfirmStep === 'first'
                      ? page('settings.integrations.syncAll.confirm.firstDesc')
                      : page('settings.integrations.syncAll.confirm.secondDesc')}
                  </p>
                </div>
              </div>
              {syncAllImpactSummary ? (
                <Card>
                  <div className="integration-status__detail">
                    {page('settings.integrations.syncAll.confirm.impact', {
                      total: syncAllImpactSummary.total,
                      synced: syncAllImpactSummary.alreadySynced,
                      newCount: syncAllImpactSummary.newCount,
                    })}
                  </div>
                </Card>
              ) : null}
              <div className="member-modal__actions">
                <button
                  className="btn btn--outline btn--sm"
                  type="button"
                  onClick={() => setSyncAllConfirmStep(null)}
                  disabled={submitting}
                >
                  {page('settings.integrations.action.cancel')}
                </button>
                {syncAllConfirmStep === 'first' ? (
                  <button
                    className="btn btn--primary btn--sm"
                    type="button"
                    onClick={() => setSyncAllConfirmStep('second')}
                  >
                    {page('settings.integrations.syncAll.confirm.firstAction')}
                  </button>
                ) : (
                  <button
                    className="btn btn--primary btn--sm"
                    type="button"
                    onClick={() => void handleSyncAll()}
                    disabled={submitting}
                  >
                    {page('settings.integrations.syncAll.confirm.secondAction')}
                  </button>
                )}
              </div>
            </div>
          </div>
        ) : null}

        {catalogModalOpen ? (
          <div className="member-modal-overlay" onClick={() => setCatalogModalOpen(false)}>
            <div className="member-modal integration-catalog-modal" onClick={(event) => event.stopPropagation()}>
              <div className="member-modal__header">
                <div>
                  <h3>{page('settings.integrations.modal.catalog.title')}</h3>
                  <p>{page('settings.integrations.modal.catalog.desc')}</p>
                </div>
              </div>
              <div className="integration-catalog-grid">
                {catalog.map((item) => (
                    <div key={item.plugin_id} className="integration-catalog-card">
                      <div className="integration-catalog-card__icon">
                      {item.plugin_id.includes('home_assistant') || item.plugin_id.includes('open_xiaoai') ? (
                        <Home size={24} />
                      ) : (
                        <Plug size={24} />
                      )}
                    </div>
                    <div className="integration-catalog-card__body">
                      <div className="integration-catalog-card__header">
                        <h4 className="integration-catalog-card__title">{item.name}</h4>
                        <span className={`badge badge--${item.config_schema_available ? 'success' : 'secondary'} integration-catalog-card__badge`}>
                          {item.config_schema_available
                            ? page('settings.integrations.modal.catalog.supported')
                            : page('settings.integrations.modal.catalog.pending')}
                        </span>
                      </div>
                      <p className="integration-catalog-card__desc">{item.description || item.plugin_id}</p>
                      {item.config_schema_available ? (
                        <div className="integration-catalog-card__features">
                          <span className="integration-catalog-card__feature">
                            <Check size={12} />
                            {page('settings.integrations.modal.catalog.feature.sync')}
                          </span>
                          <span className="integration-catalog-card__feature">
                            <Check size={12} />
                            {page('settings.integrations.modal.catalog.feature.control')}
                          </span>
                        </div>
                      ) : null}
                    </div>
                    <div className="integration-catalog-card__actions">
                      <button
                        className="btn btn--primary btn--sm"
                        type="button"
                        disabled={!item.config_schema_available}
                        onClick={() => openCreateModal(item)}
                      >
                        {page('settings.integrations.modal.catalog.choose')}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        ) : null}

        {createModalOpen && selectedCatalogItem?.config_spec ? (
          <div className="member-modal-overlay" onClick={closeCreateModal}>
            <div className="member-modal" onClick={(event) => event.stopPropagation()}>
              <div className="member-modal__header">
                <div>
                  <h3>{page('settings.integrations.modal.create.title', { plugin: selectedCatalogItem.name })}</h3>
                  <p>{selectedCatalogItem.config_spec.description || page('settings.integrations.modal.create.desc')}</p>
                </div>
              </div>
              <form className="settings-form integration-config-form" onSubmit={handleCreateInstance}>
                <div className="form-group">
                  <label>{page('settings.integrations.modal.create.displayName')}</label>
                  <input
                    className="form-input"
                    value={createDraft.displayName}
                    onChange={(event) => setCreateDraft((current) => ({
                      ...current,
                      displayName: event.target.value,
                      fieldErrors: { ...current.fieldErrors, display_name: '' },
                    }))}
                    placeholder={page('settings.integrations.modal.create.displayNamePlaceholder')}
                  />
                  {createDraft.fieldErrors.display_name ? <div className="form-help">{createDraft.fieldErrors.display_name}</div> : null}
                </div>
                {selectedCatalogItem.config_spec.ui_schema.sections.map((section) => (
                  <div key={section.id}>
                    <div className="form-group">
                      <label>{section.title}</label>
                      {section.description ? <div className="form-help">{section.description}</div> : null}
                    </div>
                    {section.fields.map((fieldKey) => {
                      const field = selectedCatalogItem.config_spec?.config_schema.fields.find((item) => item.key === fieldKey);
                      if (!field) {
                        return null;
                      }
                      return renderField(field, selectedCatalogItem.config_spec?.ui_schema.widgets?.[field.key]);
                    })}
                  </div>
                ))}
                <div className="member-modal__actions">
                  <button className="btn btn--outline btn--sm" type="button" onClick={closeCreateModal} disabled={submitting}>
                    {page('settings.integrations.action.cancel')}
                  </button>
                  <button className="btn btn--primary btn--sm" type="submit" disabled={submitting}>
                    {submitting ? page('settings.integrations.action.saving') : page('settings.integrations.modal.create.submit')}
                  </button>
                </div>
              </form>
            </div>
          </div>
        ) : null}

        {deviceModalOpen ? (
          <div className="member-modal-overlay" onClick={() => setDeviceModalOpen(false)}>
            <div className="member-modal ha-device-modal" onClick={(event) => event.stopPropagation()}>
              <div className="member-modal__header">
                <div>
                  <h3>{page('settings.integrations.modal.devices.title')}</h3>
                  <p>{page('settings.integrations.modal.devices.desc')}</p>
                </div>
              </div>
              <div className="integration-status__detail">
                {page('settings.integrations.modal.devices.selectedCount', {
                  selected: selectedDeviceIds.length,
                  total: deviceCandidates.length,
                })}
              </div>
              <div className="integration-status__detail">
                {page('settings.integrations.modal.devices.domainFilterHint')}
              </div>
              <div className="family-device-filters">
                <label className="family-device-filters__item">
                  <span className="family-device-filters__label">{page('settings.integrations.modal.devices.roomFilter')}</span>
                  <select
                    className="form-select"
                    value={candidateRoomFilter}
                    onChange={(event) => setCandidateRoomFilter(event.target.value)}
                  >
                    <option value="all">{page('settings.integrations.modal.devices.roomFilterAll')}</option>
                    {candidateRoomOptions.map((roomName) => (
                      <option key={roomName} value={roomName}>{roomName}</option>
                    ))}
                  </select>
                </label>
                <label className="family-device-filters__item">
                  <span className="family-device-filters__label">{page('settings.integrations.modal.devices.domainFilter')}</span>
                  <select
                    className="form-select"
                    value={candidateDomainFilter}
                    onChange={(event) => setCandidateDomainFilter(event.target.value)}
                  >
                    <option value="all">{page('settings.integrations.modal.devices.domainFilterAll')}</option>
                    {candidateDomainOptions.map((domain) => (
                      <option key={domain} value={domain}>{domain}</option>
                    ))}
                  </select>
                </label>
                <label className="family-device-filters__item">
                  <span className="family-device-filters__label">{page('settings.integrations.modal.devices.searchLabel')}</span>
                  <input
                    className="form-input"
                    value={candidateKeyword}
                    onChange={(event) => setCandidateKeyword(event.target.value)}
                    placeholder={page('settings.integrations.modal.devices.searchPlaceholder')}
                  />
                </label>
              </div>
              <div className="ha-device-modal__list">
                {deviceCandidates.length === 0 ? (
                  <div className="integration-status__detail">{page('settings.integrations.modal.devices.empty')}</div>
                ) : filteredDeviceCandidates.length === 0 ? (
                  <div className="integration-status__detail">{page('settings.integrations.modal.devices.noFilterResult')}</div>
                ) : filteredDeviceCandidates.map((candidate) => {
                  const entityDomain = getCandidateEntityDomain(candidate);
                  return (
                    <label key={candidate.external_device_id} className="ha-device-option">
                      <input
                        type="checkbox"
                        checked={selectedDeviceIds.includes(candidate.external_device_id)}
                        onChange={() => setSelectedDeviceIds((current) => current.includes(candidate.external_device_id)
                          ? current.filter((item) => item !== candidate.external_device_id)
                          : [...current, candidate.external_device_id])}
                        disabled={submitting}
                      />
                      <div className="ha-device-option__body">
                        <div className="ha-device-option__title-row">
                          <strong>{candidate.name}</strong>
                          <span className={`badge badge--${candidate.already_synced ? 'secondary' : 'success'}`}>
                            {candidate.already_synced
                              ? page('settings.integrations.modal.devices.importedBefore')
                              : page('settings.integrations.modal.devices.newDevice')}
                          </span>
                        </div>
                        <div className="integration-status__detail">
                          {candidate.room_name || page('settings.integrations.instance.noRoom')} · {page('settings.integrations.modal.devices.entityCount', { count: candidate.entity_count })}
                          {entityDomain ? ` · ${entityDomain}` : ''}
                        </div>
                      </div>
                    </label>
                  );
                })}
              </div>
              <div className="member-modal__actions">
                <button className="btn btn--outline btn--sm" type="button" onClick={() => setDeviceModalOpen(false)} disabled={submitting}>
                  {page('settings.integrations.action.cancel')}
                </button>
                <button className="btn btn--primary btn--sm" type="button" onClick={() => void handleSyncSelected()} disabled={submitting || selectedDeviceIds.length === 0}>
                  {page('settings.integrations.action.importSelectedDevices')}
                </button>
              </div>
            </div>
          </div>
        ) : null}
      </div>
    </SettingsPageShell>
  );
}

export default function SettingsIntegrationsPage() {
  return (
    <GuardedPage mode="protected" path="/pages/settings/integrations/index">
      <SettingsIntegrationsContent />
    </GuardedPage>
  );
}
