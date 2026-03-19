import { useEffect, useMemo, useRef, useState } from 'react';
import Taro from '@tarojs/taro';
import { Home, Check, Plug } from 'lucide-react';
import { GuardedPage, useHouseholdContext, useI18n } from '../../../runtime';
import { getPageMessage } from '../../../runtime/h5-shell/i18n/pageMessageUtils';
import { Card, Section } from '../../family/base';
import { IntegrationSyncedDevicePreviewDialog } from '../../device-management/IntegrationSyncedDevicePreviewDialog';
import { SettingsPageShell } from '../SettingsPageShell';
import {
  resolvePluginConfigSectionDescription,
  resolvePluginConfigSectionTitle,
  resolvePluginConfigSpecDescription,
  resolvePluginConfigSubmitText,
  resolvePluginFieldLabel,
  resolvePluginMaybeKey,
  resolvePluginOptionLabel,
  resolvePluginWidgetHelpText,
  resolvePluginWidgetPlaceholder,
} from '../pluginConfigI18n';
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
  IntegrationDiscoveryItem,
  IntegrationInstance,
  IntegrationResource,
  PluginConfigFormRead,
  PluginManifestConfigField,
  PluginManifestConfigSpec,
  PluginManifestFieldUiSchema,
} from '../settingsTypes';

type CreateDraft = {
  displayName: string;
  values: Record<string, unknown>;
  secrets: Record<string, string>;
  secretFields: Record<string, NonNullable<PluginConfigFormRead['view']['secret_fields'][string]>>;
  clearSecretFields: Record<string, boolean>;
  fieldErrors: Record<string, string>;
};

type SyncAllConfirmStep = 'first' | 'second' | null;
type InstanceFormMode = 'create' | 'edit';
type InstanceFormContext = {
  pluginId: string;
  pluginName: string;
  description: string | null;
  configSpec: PluginManifestConfigSpec;
};
type OpenXiaoaiGatewayCandidate = {
  gatewayId: string;
  modelSummary: string;
  speakerCount: number;
  onlineSpeakerCount: number;
  lastSeenAt: string | null;
};

const OPEN_XIAOAI_PLUGIN_ID = 'open-xiaoai-speaker';
const OPEN_XIAOAI_GATEWAY_FIELD_KEY = 'gateway_id';

function getActionOutputItems<T>(result: IntegrationActionResult): T[] {
  const items = result.output.items;
  return Array.isArray(items) ? (items as T[]) : [];
}

function getActionOutputSummary<T>(result: IntegrationActionResult): T | null {
  const summary = result.output.summary;
  return summary && typeof summary === 'object' ? (summary as T) : null;
}

function buildDraft(
  configSpec: PluginManifestConfigSpec | null,
  options?: {
    displayName?: string;
    form?: PluginConfigFormRead | null;
  },
): CreateDraft {
  const values: Record<string, unknown> = {};
  const secretFields: CreateDraft['secretFields'] = {};
  for (const field of configSpec?.config_schema.fields ?? []) {
    const formValue = options?.form?.view.values[field.key];
    if (field.type === 'secret') {
      const secretField = options?.form?.view.secret_fields[field.key];
      if (secretField) {
        secretFields[field.key] = secretField;
      }
      continue;
    }
    if (formValue !== undefined) {
      values[field.key] = formValue;
      continue;
    }
    if (field.default !== undefined && field.default !== null) {
      values[field.key] = field.default;
    }
  }
  return {
    displayName: options?.displayName ?? '',
    values,
    secrets: {},
    secretFields,
    clearSecretFields: {},
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

function isPluginFieldVisible(
  fieldKey: string,
  values: Record<string, unknown>,
  widgets: Record<string, PluginManifestFieldUiSchema> | undefined,
): boolean {
  const rules = widgets?.[fieldKey]?.visible_when ?? [];
  if (rules.length === 0) {
    return true;
  }
  return rules.every((rule) => {
    const currentValue = values[rule.field];
    if (rule.operator === 'truthy') {
      return Boolean(currentValue);
    }
    if (rule.operator === 'equals') {
      return currentValue === rule.value;
    }
    if (rule.operator === 'not_equals') {
      return currentValue !== rule.value;
    }
    if (rule.operator === 'in') {
      return Array.isArray(rule.value) && rule.value.includes(currentValue);
    }
    return true;
  });
}

function getFieldDependencies(field: PluginManifestConfigField): string[] {
  const dependencies = new Set(field.depends_on ?? []);
  if (field.option_source?.provider_field) {
    dependencies.add(field.option_source.provider_field);
  }
  if (field.option_source?.parent_field) {
    dependencies.add(field.option_source.parent_field);
  }
  return Array.from(dependencies);
}

function shouldResolveConfigChange(configSpec: PluginManifestConfigSpec, fieldKey: string): boolean {
  if (configSpec.config_schema.fields.some((field) => getFieldDependencies(field).includes(fieldKey))) {
    return true;
  }
  return Object.values(configSpec.ui_schema.widgets ?? {}).some((widget) => (
    (widget.visible_when ?? []).some((rule) => rule.field === fieldKey)
  ));
}

function sanitizeDraftValuesWithConfigSpec(
  configSpec: PluginManifestConfigSpec,
  values: Record<string, unknown>,
): Record<string, unknown> {
  const nextValues = { ...values };
  for (const field of configSpec.config_schema.fields) {
    const currentValue = nextValues[field.key];
    if (field.type === 'enum') {
      const optionValues = new Set((field.enum_options ?? []).map((option) => option.value));
      if (typeof currentValue === 'string' && currentValue && !optionValues.has(currentValue)) {
        delete nextValues[field.key];
      }
      continue;
    }
    if (field.type === 'multi_enum' && Array.isArray(currentValue)) {
      const optionValues = new Set((field.enum_options ?? []).map((option) => option.value));
      const filtered = currentValue.filter((item): item is string => typeof item === 'string' && optionValues.has(item));
      if (filtered.length === 0) {
        delete nextValues[field.key];
      } else if (filtered.length !== currentValue.length) {
        nextValues[field.key] = filtered;
      }
    }
  }
  return nextValues;
}

function areDraftValuesEqual(left: Record<string, unknown>, right: Record<string, unknown>): boolean {
  return JSON.stringify(left) === JSON.stringify(right);
}

function buildPluginClearFields(
  configSpec: PluginManifestConfigSpec,
  values: Record<string, unknown>,
  widgets: Record<string, PluginManifestFieldUiSchema> | undefined,
): string[] {
  return configSpec.config_schema.fields
    .filter((field) => {
      if (field.type === 'secret') {
        return false;
      }
      if (!isPluginFieldVisible(field.key, values, widgets)) {
        return true;
      }
      const value = values[field.key];
      if (value === undefined || value === null) {
        return true;
      }
      if (typeof value === 'string' && !value.trim()) {
        return true;
      }
      if (Array.isArray(value) && value.length === 0) {
        return true;
      }
      return false;
    })
    .map((field) => field.key);
}

function normalizeSubmitValue(field: PluginManifestConfigField, value: unknown): unknown {
  if (value === null || value === undefined) {
    return undefined;
  }
  if (field.type === 'boolean') {
    return value === true;
  }
  if (field.type === 'integer' || field.type === 'number') {
    if (typeof value === 'number') {
      return value;
    }
    if (typeof value === 'string') {
      const normalizedValue = value.trim();
      if (!normalizedValue) {
        return field.required ? value : undefined;
      }
      const parsed = Number(normalizedValue);
      return Number.isFinite(parsed) ? parsed : value;
    }
  }
  if (field.type === 'string' || field.type === 'text' || field.type === 'secret' || field.type === 'enum') {
    if (typeof value !== 'string') {
      return value;
    }
    const normalizedValue = value.trim();
    if (!normalizedValue) {
      return field.required ? normalizedValue : undefined;
    }
    return normalizedValue;
  }
  return value ?? undefined;
}

function buildOpenXiaoaiGatewayCandidates(discoveries: IntegrationDiscoveryItem[]): OpenXiaoaiGatewayCandidate[] {
  const gatewayMap = new Map<
    string,
    {
      models: Set<string>;
      speakerCount: number;
      onlineSpeakerCount: number;
      lastSeenAt: string | null;
    }
  >();

  for (const discovery of discoveries) {
    if (
      discovery.plugin_id !== OPEN_XIAOAI_PLUGIN_ID
      || discovery.integration_instance_id
      || discovery.status !== 'pending'
    ) {
      continue;
    }
    const gatewayId = String(discovery.metadata.gateway_id ?? '').trim();
    if (!gatewayId) {
      continue;
    }

    const current = gatewayMap.get(gatewayId) ?? {
      models: new Set<string>(),
      speakerCount: 0,
      onlineSpeakerCount: 0,
      lastSeenAt: null,
    };
    const model = String(discovery.metadata.model ?? '').trim();
    const connectionStatus = String(discovery.metadata.connection_status ?? '').trim();
    const lastSeenAt = typeof discovery.updated_at === 'string' && discovery.updated_at.trim()
      ? discovery.updated_at
      : discovery.discovered_at;

    if (model) {
      current.models.add(model);
    }
    current.speakerCount += 1;
    if (connectionStatus === 'online') {
      current.onlineSpeakerCount += 1;
    }
    if (!current.lastSeenAt || (lastSeenAt && lastSeenAt > current.lastSeenAt)) {
      current.lastSeenAt = lastSeenAt;
    }
    gatewayMap.set(gatewayId, current);
  }

  return Array.from(gatewayMap.entries())
    .map(([gatewayId, item]) => ({
      gatewayId,
      modelSummary: Array.from(item.models).join(' / ') || '小爱网关',
      speakerCount: item.speakerCount,
      onlineSpeakerCount: item.onlineSpeakerCount,
      lastSeenAt: item.lastSeenAt,
    }))
    .sort((left, right) => left.gatewayId.localeCompare(right.gatewayId));
}

function SettingsIntegrationsContent() {
  const { locale, t } = useI18n();
  const { currentHouseholdId } = useHouseholdContext();
  const page = (
    key: Parameters<typeof getPageMessage>[1],
    params?: Record<string, string | number>,
  ) => getPageMessage(locale, key, params);

  const [catalog, setCatalog] = useState<IntegrationCatalogItem[]>([]);
  const [instances, setInstances] = useState<IntegrationInstance[]>([]);
  const [discoveries, setDiscoveries] = useState<IntegrationDiscoveryItem[]>([]);
  const [deviceResources, setDeviceResources] = useState<IntegrationResource[]>([]);
  const [selectedInstanceId, setSelectedInstanceId] = useState<string | null>(null);
  const [formContext, setFormContext] = useState<InstanceFormContext | null>(null);
  const [instanceFormMode, setInstanceFormMode] = useState<InstanceFormMode>('create');
  const [editingInstanceId, setEditingInstanceId] = useState<string | null>(null);
  const [createDraft, setCreateDraft] = useState<CreateDraft>(() => buildDraft(null));
  const [deviceCandidates, setDeviceCandidates] = useState<IntegrationDeviceCandidate[]>([]);
  const [selectedDeviceIds, setSelectedDeviceIds] = useState<string[]>([]);
  const [catalogModalOpen, setCatalogModalOpen] = useState(false);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [deviceModalOpen, setDeviceModalOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<IntegrationInstance | null>(null);
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
  const configResolveSeqRef = useRef(0);

  useEffect(() => {
    void Taro.setNavigationBarTitle({ title: page('settings.integrations.title') }).catch(() => undefined);
  }, [locale]);

  async function reload(householdId: string, preferredInstanceId?: string | null) {
    setLoading(true);
    try {
      const view = await settingsApi.getIntegrationPageView(householdId);
      setCatalog(view.catalog);
      setInstances(view.instances);
      setDiscoveries(view.discoveries ?? []);
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
      setDiscoveries([]);
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
  const openXiaoaiGatewayCandidates = useMemo(
    () => buildOpenXiaoaiGatewayCandidates(discoveries),
    [discoveries],
  );
  const selectedGatewayId = getScalarValue(createDraft.values, OPEN_XIAOAI_GATEWAY_FIELD_KEY).trim();
  const selectedGatewayCandidate = useMemo(
    () => openXiaoaiGatewayCandidates.find((item) => item.gatewayId === selectedGatewayId) ?? null,
    [openXiaoaiGatewayCandidates, selectedGatewayId],
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

  function getInstanceStatusPresentation(instance: IntegrationInstance) {
    if (instance.status === 'degraded') {
      return {
        label: page('settings.integrations.instance.status.degraded'),
        tone: 'warning',
      } as const;
    }
    if (instance.status === 'disabled') {
      return {
        label: page('settings.integrations.instance.status.disabled'),
        tone: 'secondary',
      } as const;
    }
    if (instance.status === 'draft' || instance.config_state !== 'configured') {
      return {
        label: page('settings.integrations.instance.status.draft'),
        tone: 'info',
      } as const;
    }
    return {
      label: page('settings.integrations.instance.status.active'),
      tone: 'success',
    } as const;
  }

  const selectedSyncAction = useMemo(
    () => selectedInstance?.allowed_actions.find((item) => item.action === 'sync') ?? null,
    [selectedInstance],
  );
  const selectedConfigureAction = useMemo(
    () => selectedInstance?.allowed_actions.find((item) => item.action === 'configure') ?? null,
    [selectedInstance],
  );
  const selectedDeleteAction = useMemo(
    () => selectedInstance?.allowed_actions.find((item) => item.action === 'delete') ?? null,
    [selectedInstance],
  );
  const syncActionDisabled = selectedSyncAction?.disabled ?? true;
  const syncActionDisabledReason = selectedSyncAction?.disabled_reason ?? page('settings.integrations.action.syncUnavailable');
  const configureActionDisabled = selectedConfigureAction?.disabled ?? false;
  const configureActionDisabledReason = selectedConfigureAction?.disabled_reason ?? '';
  const deleteActionDisabled = selectedDeleteAction?.disabled ?? false;
  const deleteActionDisabledReason = selectedDeleteAction?.disabled_reason ?? '';

  function formatOpenXiaoaiGatewaySummary(candidate: OpenXiaoaiGatewayCandidate) {
    return page('settings.integrations.modal.create.gateway.summary', {
      model: candidate.modelSummary,
      count: candidate.speakerCount,
      online: candidate.onlineSpeakerCount,
    });
  }

  async function resolveIntegrationDraftConfig(
    pluginId: string,
    draft: CreateDraft,
    scopeKey?: string,
  ) {
    if (!currentHouseholdId) {
      return;
    }
    const resolveSeq = configResolveSeqRef.current + 1;
    configResolveSeqRef.current = resolveSeq;

    let workingValues = { ...draft.values };
    let resolvedForm: PluginConfigFormRead | null = null;
    for (let attempt = 0; attempt < 4; attempt += 1) {
      resolvedForm = await settingsApi.resolveHouseholdPluginConfigForm(currentHouseholdId, pluginId, {
        scope_type: 'integration_instance',
        scope_key: scopeKey ?? null,
        values: workingValues,
      });
      const sanitizedValues = sanitizeDraftValuesWithConfigSpec(resolvedForm.config_spec, resolvedForm.view.values);
      if (areDraftValuesEqual(workingValues, sanitizedValues)) {
        break;
      }
      workingValues = sanitizedValues;
    }

    if (!resolvedForm || resolveSeq !== configResolveSeqRef.current) {
      return;
    }

    setFormContext((current) => {
      if (!current || current.pluginId !== pluginId) {
        return current;
      }
      return {
        ...current,
        configSpec: resolvedForm!.config_spec,
      };
    });
    setCreateDraft((current) => {
      if (resolveSeq !== configResolveSeqRef.current) {
        return current;
      }
      const displayNameError = current.fieldErrors.display_name;
      return {
        ...current,
        values: resolvedForm!.view.values,
        secretFields: Object.keys(resolvedForm!.view.secret_fields).length > 0
          ? resolvedForm!.view.secret_fields
          : current.secretFields,
        fieldErrors: {
          ...(displayNameError ? { display_name: displayNameError } : {}),
          ...resolvedForm!.view.field_errors,
        },
      };
    });
  }

  async function openCreateModal(item: IntegrationCatalogItem) {
    if (!item.config_spec || !currentHouseholdId) {
      return;
    }
    setSubmitting(true);
    try {
      const resolvedForm = await settingsApi.resolveHouseholdPluginConfigForm(currentHouseholdId, item.plugin_id, {
        scope_type: 'integration_instance',
        scope_key: null,
        values: {},
      });
      setInstanceFormMode('create');
      setEditingInstanceId(null);
      setFormContext({
        pluginId: item.plugin_id,
        pluginName: item.name,
        description: item.description ?? null,
        configSpec: resolvedForm.config_spec,
      });
      setCreateDraft(buildDraft(resolvedForm.config_spec, {
        displayName: item.name,
        form: resolvedForm,
      }));
      setCatalogModalOpen(false);
      setCreateModalOpen(true);
      setError('');
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : page('settings.integrations.error.loadIntegrationFormFailed'));
    } finally {
      setSubmitting(false);
    }
  }

  async function openEditModal(instance: IntegrationInstance) {
    if (!currentHouseholdId) {
      setError(page('settings.integrations.error.selectHousehold'));
      return;
    }
    if (instanceFormMode === 'edit' && !editingInstanceId) {
      return;
    }

    setSubmitting(true);
    try {
      const configForm = await settingsApi.getHouseholdPluginConfigForm(currentHouseholdId, instance.plugin_id, {
        scope_type: 'integration_instance',
        scope_key: instance.id,
      });
      const catalogItem = catalog.find((item) => item.plugin_id === instance.plugin_id) ?? null;
      setInstanceFormMode('edit');
      setEditingInstanceId(instance.id);
      setFormContext({
        pluginId: instance.plugin_id,
        pluginName: catalogItem?.name ?? instance.plugin_id,
        description: catalogItem?.description ?? instance.description ?? null,
        configSpec: configForm.config_spec,
      });
      setCreateDraft(buildDraft(configForm.config_spec, {
        displayName: instance.display_name,
        form: configForm,
      }));
      setCreateModalOpen(true);
      setError('');
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : page('settings.integrations.error.loadIntegrationFormFailed'));
    } finally {
      setSubmitting(false);
    }
  }

  function closeCreateModal() {
    configResolveSeqRef.current += 1;
    setCreateModalOpen(false);
    setFormContext(null);
    setEditingInstanceId(null);
    setInstanceFormMode('create');
    setCreateDraft(buildDraft(null));
  }

  async function updateValue(fieldKey: string, value: unknown) {
    const nextDraft: CreateDraft = {
      ...createDraft,
      values: { ...createDraft.values, [fieldKey]: value },
      fieldErrors: { ...createDraft.fieldErrors, [fieldKey]: '' },
    };
    setCreateDraft(nextDraft);
    if (!formContext || !shouldResolveConfigChange(formContext.configSpec, fieldKey)) {
      return;
    }
    await resolveIntegrationDraftConfig(
      formContext.pluginId,
      nextDraft,
      instanceFormMode === 'edit' ? (editingInstanceId ?? undefined) : undefined,
    );
  }

  function updateSecret(fieldKey: string, value: string) {
    setCreateDraft((current) => ({
      ...current,
      secrets: { ...current.secrets, [fieldKey]: value },
      clearSecretFields: value.trim()
        ? { ...current.clearSecretFields, [fieldKey]: false }
        : current.clearSecretFields,
      fieldErrors: { ...current.fieldErrors, [fieldKey]: '' },
    }));
  }

  function toggleClearSecret(fieldKey: string, checked: boolean) {
    setCreateDraft((current) => ({
      ...current,
      secrets: checked
        ? { ...current.secrets, [fieldKey]: '' }
        : current.secrets,
      clearSecretFields: { ...current.clearSecretFields, [fieldKey]: checked },
      fieldErrors: { ...current.fieldErrors, [fieldKey]: '' },
    }));
  }

  function renderField(field: PluginManifestConfigField, widget?: PluginManifestFieldUiSchema) {
    const fieldError = createDraft.fieldErrors[field.key];
    if (formContext?.pluginId === OPEN_XIAOAI_PLUGIN_ID && field.key === OPEN_XIAOAI_GATEWAY_FIELD_KEY) {
      return (
        <div key={field.key} className="form-group">
          <label>{page('settings.integrations.modal.create.gateway.label')}</label>
          {openXiaoaiGatewayCandidates.length === 0 ? (
            selectedGatewayId ? (
              <>
                <div className="integration-status__detail">
                  {page('settings.integrations.modal.create.gateway.currentBound', { gateway: selectedGatewayId })}
                </div>
                <div className="form-help">{page('settings.integrations.modal.create.gateway.currentBoundHint')}</div>
              </>
            ) : (
              <>
                <div className="form-help">{page('settings.integrations.modal.create.gateway.empty')}</div>
                <div className="form-help">{page('settings.integrations.modal.create.gateway.emptyHint')}</div>
              </>
            )
          ) : openXiaoaiGatewayCandidates.length === 1 ? (
            <>
              <div className="integration-status__detail">
                {page('settings.integrations.modal.create.gateway.autoSelected')}
              </div>
              <div className="form-help">{formatOpenXiaoaiGatewaySummary(openXiaoaiGatewayCandidates[0])}</div>
              {openXiaoaiGatewayCandidates[0].lastSeenAt ? (
                <div className="form-help">
                  {page('settings.integrations.modal.create.gateway.lastSeen', {
                    time: openXiaoaiGatewayCandidates[0].lastSeenAt,
                  })}
                </div>
              ) : null}
            </>
          ) : (
            <>
              <select
                className="form-select"
                value={selectedGatewayId}
                onChange={(event) => void updateValue(field.key, event.target.value)}
              >
                <option value="">{page('settings.integrations.modal.create.gateway.selectPlaceholder')}</option>
                {openXiaoaiGatewayCandidates.map((candidate) => (
                  <option key={candidate.gatewayId} value={candidate.gatewayId}>
                    {formatOpenXiaoaiGatewaySummary(candidate)}
                  </option>
                ))}
              </select>
              <div className="form-help">{page('settings.integrations.modal.create.gateway.multipleHint')}</div>
              {selectedGatewayCandidate?.lastSeenAt ? (
                <div className="form-help">
                  {page('settings.integrations.modal.create.gateway.lastSeen', {
                    time: selectedGatewayCandidate.lastSeenAt,
                  })}
                </div>
              ) : null}
            </>
          )}
          {fieldError ? <div className="form-help">{fieldError}</div> : null}
        </div>
      );
    }
    if (field.type === 'secret') {
      const secretField = createDraft.secretFields[field.key];
      const keepExisting = Boolean(secretField?.has_value) && !createDraft.secrets[field.key]?.trim() && !createDraft.clearSecretFields[field.key];
      return (
        <div key={field.key} className="form-group">
          <label>{resolvePluginFieldLabel(field, t)}</label>
          <input
            className="form-input"
            type="password"
            value={createDraft.secrets[field.key] ?? ''}
            onChange={(event) => updateSecret(field.key, event.target.value)}
            placeholder={secretField?.has_value
              ? page('settings.integrations.modal.instance.secret.replacePlaceholder')
              : (resolvePluginWidgetPlaceholder(widget, t) || undefined)}
          />
          {secretField?.has_value ? (
            <label className="form-help" style={{ display: 'block' }}>
              <input
                type="checkbox"
                checked={Boolean(createDraft.clearSecretFields[field.key])}
                onChange={(event) => toggleClearSecret(field.key, event.target.checked)}
                disabled={Boolean(createDraft.secrets[field.key]?.trim())}
              />
              {' '}
              {page('settings.integrations.modal.instance.secret.clearToggle', {
                masked: secretField.masked ?? '******',
              })}
            </label>
          ) : null}
          <div className="form-help">{resolvePluginWidgetHelpText(widget, field, t)}</div>
          {keepExisting ? (
            <div className="form-help">
              {page('settings.integrations.modal.instance.secret.keepHint', {
                masked: secretField?.masked ?? '******',
              })}
            </div>
          ) : null}
          {fieldError ? <div className="form-help">{resolvePluginMaybeKey(fieldError, t)}</div> : null}
        </div>
      );
    }
    if (field.type === 'boolean') {
      return (
        <div key={field.key} className="form-group">
          <label>{resolvePluginFieldLabel(field, t)}</label>
          <select
            className="form-select"
            value={createDraft.values[field.key] === true ? 'true' : 'false'}
            onChange={(event) => void updateValue(field.key, event.target.value === 'true')}
          >
            <option value="false">{page('settings.integrations.modal.config.booleanFalse')}</option>
            <option value="true">{page('settings.integrations.modal.config.booleanTrue')}</option>
          </select>
          <div className="form-help">{resolvePluginWidgetHelpText(widget, field, t)}</div>
          {fieldError ? <div className="form-help">{resolvePluginMaybeKey(fieldError, t)}</div> : null}
        </div>
      );
    }
    if (field.type === 'enum') {
      return (
        <div key={field.key} className="form-group">
          <label>{resolvePluginFieldLabel(field, t)}</label>
          <select
            className="form-select"
            value={getScalarValue(createDraft.values, field.key)}
            onChange={(event) => void updateValue(field.key, event.target.value)}
          >
            <option value="">{page('settings.integrations.modal.config.selectPlaceholder')}</option>
            {(field.enum_options ?? []).map((option) => (
              <option key={option.value} value={option.value}>{resolvePluginOptionLabel(option, t)}</option>
            ))}
          </select>
          <div className="form-help">{resolvePluginWidgetHelpText(widget, field, t)}</div>
          {fieldError ? <div className="form-help">{resolvePluginMaybeKey(fieldError, t)}</div> : null}
        </div>
      );
    }
    if (field.type === 'text') {
      return (
        <div key={field.key} className="form-group">
          <label>{resolvePluginFieldLabel(field, t)}</label>
          <textarea
            className="form-input"
            value={getScalarValue(createDraft.values, field.key)}
            onChange={(event) => void updateValue(field.key, event.target.value)}
            placeholder={resolvePluginWidgetPlaceholder(widget, t) || undefined}
          />
          <div className="form-help">{resolvePluginWidgetHelpText(widget, field, t)}</div>
          {fieldError ? <div className="form-help">{resolvePluginMaybeKey(fieldError, t)}</div> : null}
        </div>
      );
    }
    return (
      <div key={field.key} className="form-group">
        <label>{resolvePluginFieldLabel(field, t)}</label>
        <input
          className="form-input"
          type={field.type === 'integer' || field.type === 'number' ? 'number' : 'text'}
          value={getScalarValue(createDraft.values, field.key)}
          onChange={(event) => void updateValue(field.key, event.target.value)}
          placeholder={resolvePluginWidgetPlaceholder(widget, t) || undefined}
        />
        <div className="form-help">{resolvePluginWidgetHelpText(widget, field, t)}</div>
        {fieldError ? <div className="form-help">{resolvePluginMaybeKey(fieldError, t)}</div> : null}
      </div>
    );
  }

  async function handleSubmitInstance(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!currentHouseholdId || !formContext) {
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
    if (instanceFormMode === 'create' && formContext.pluginId === OPEN_XIAOAI_PLUGIN_ID) {
      if (openXiaoaiGatewayCandidates.length === 0) {
        setCreateDraft((current) => ({
          ...current,
          fieldErrors: {
            ...current.fieldErrors,
            gateway_id: page('settings.integrations.modal.create.gateway.empty'),
          },
        }));
        return;
      }
      if (!selectedGatewayId || !selectedGatewayCandidate) {
        setCreateDraft((current) => ({
          ...current,
          fieldErrors: {
            ...current.fieldErrors,
            gateway_id: page('settings.integrations.modal.create.gateway.selectRequired'),
          },
        }));
        return;
      }
    }

    const payloadValues: Record<string, unknown> = {};
    const clearFields = buildPluginClearFields(
      formContext.configSpec,
      createDraft.values,
      formContext.configSpec.ui_schema.widgets,
    );
    const clearSecretFields: string[] = [];
    for (const field of formContext.configSpec.config_schema.fields) {
      if (!isPluginFieldVisible(field.key, createDraft.values, formContext.configSpec.ui_schema.widgets)) {
        continue;
      }
      if (field.type === 'secret') {
        const rawSecret = createDraft.secrets[field.key] ?? '';
        if (rawSecret.trim()) {
          payloadValues[field.key] = normalizeSubmitValue(field, rawSecret);
          continue;
        }
        if (createDraft.clearSecretFields[field.key]) {
          clearSecretFields.push(field.key);
        }
        continue;
      }
      const rawValue = createDraft.values[field.key];
      if (rawValue === undefined) {
        continue;
      }
      const normalizedValue = normalizeSubmitValue(field, rawValue);
      if (normalizedValue === undefined) {
        continue;
      }
      payloadValues[field.key] = normalizedValue;
    }

    setSubmitting(true);
    try {
      const payload = {
        display_name: createDraft.displayName.trim(),
        config: payloadValues,
        clear_fields: clearFields,
        clear_secret_fields: clearSecretFields,
      };
      const instance = instanceFormMode === 'create'
        ? await settingsApi.createIntegrationInstance({
          household_id: currentHouseholdId,
          plugin_id: formContext.pluginId,
          ...payload,
        })
        : await settingsApi.updateIntegrationInstance(editingInstanceId ?? '', payload);
      setStatus(page(
        instanceFormMode === 'create'
          ? 'settings.integrations.status.instanceCreated'
          : 'settings.integrations.status.instanceUpdated',
        { name: instance.display_name },
      ));
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

  useEffect(() => {
    if (formContext?.pluginId !== OPEN_XIAOAI_PLUGIN_ID) {
      return;
    }
    setCreateDraft((current) => {
      const currentGatewayId = getScalarValue(current.values, OPEN_XIAOAI_GATEWAY_FIELD_KEY).trim();
      if (instanceFormMode === 'edit' && currentGatewayId) {
        return current;
      }
      if (openXiaoaiGatewayCandidates.length === 1) {
        const onlyCandidate = openXiaoaiGatewayCandidates[0];
        if (currentGatewayId === onlyCandidate.gatewayId && !current.fieldErrors.gateway_id) {
          return current;
        }
        return {
          ...current,
          values: { ...current.values, [OPEN_XIAOAI_GATEWAY_FIELD_KEY]: onlyCandidate.gatewayId },
          fieldErrors: { ...current.fieldErrors, gateway_id: '' },
        };
      }
      if (currentGatewayId && openXiaoaiGatewayCandidates.some((item) => item.gatewayId === currentGatewayId)) {
        return current;
      }
      if (!currentGatewayId && !current.fieldErrors.gateway_id) {
        return current;
      }
      const nextValues = { ...current.values };
      delete nextValues[OPEN_XIAOAI_GATEWAY_FIELD_KEY];
      return {
        ...current,
        values: nextValues,
        fieldErrors: { ...current.fieldErrors, gateway_id: '' },
      };
    });
  }, [formContext?.pluginId, instanceFormMode, openXiaoaiGatewayCandidates]);

  async function handleOpenSyncAllConfirm() {
    if (!selectedInstance || syncActionDisabled) {
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
      setError(syncError instanceof Error ? syncError.message : page('settings.integrations.error.loadDeviceCandidatesFailed'));
    } finally {
      setSyncAllLoading(false);
    }
  }

  async function handleSyncAll() {
    if (!selectedInstance || syncActionDisabled) {
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
    if (!selectedInstance || syncActionDisabled) {
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
      setError(syncError instanceof Error ? syncError.message : page('settings.integrations.error.loadDeviceCandidatesFailed'));
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

  async function handleDeleteInstance() {
    if (!currentHouseholdId || !deleteTarget) {
      return;
    }
    setSubmitting(true);
    try {
      const deletedInstanceId = deleteTarget.id;
      const deletedInstanceName = deleteTarget.display_name;
      await settingsApi.deleteIntegrationInstance(deletedInstanceId);
      setDeleteTarget(null);
      setStatus(page('settings.integrations.status.instanceDeleted', { name: deletedInstanceName }));
      await reload(currentHouseholdId, selectedInstanceId === deletedInstanceId ? null : selectedInstanceId);
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : page('settings.integrations.error.deleteInstanceFailed'));
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
                      <span className={`badge badge--${getInstanceStatusPresentation(instance).tone}`}>
                        {getInstanceStatusPresentation(instance).label}
                      </span>
                    </div>
                    <div className="integration-instance-card__plugin">
                      <span className="integration-instance-card__plugin-label">{page('settings.integrations.instance.pluginLabel')}</span>
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
                      <span className={`badge badge--${getInstanceStatusPresentation(selectedInstance).tone}`}>
                        {getInstanceStatusPresentation(selectedInstance).label}
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

                  {syncActionDisabled ? (
                    <div className="settings-note settings-note--warning">
                      {syncActionDisabledReason}
                    </div>
                  ) : null}

                  <div className="integration-detail-panel__actions">
                    <button
                      className="btn btn--outline btn--sm"
                      type="button"
                      onClick={() => void openEditModal(selectedInstance)}
                      disabled={submitting || configureActionDisabled}
                      title={configureActionDisabled ? configureActionDisabledReason : undefined}
                    >
                      {page('settings.integrations.action.editInstance')}
                    </button>
                    <button
                      className="btn btn--primary btn--sm"
                      type="button"
                      onClick={() => void handleOpenSyncAllConfirm()}
                      disabled={submitting || syncAllLoading || syncActionDisabled}
                      title={syncActionDisabled ? syncActionDisabledReason : undefined}
                    >
                      {page('settings.integrations.action.syncAllEntities')}
                    </button>
                    <button
                      className="btn btn--outline btn--sm"
                      type="button"
                      onClick={() => void handleOpenPicker()}
                      disabled={submitting || syncActionDisabled}
                      title={syncActionDisabled ? syncActionDisabledReason : undefined}
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
                    <button
                      className="btn btn--danger btn--sm"
                      type="button"
                      onClick={() => setDeleteTarget(selectedInstance)}
                      disabled={submitting || deleteActionDisabled}
                      title={deleteActionDisabled ? deleteActionDisabledReason : undefined}
                    >
                      {page('settings.integrations.action.deleteInstance')}
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

        {deleteTarget ? (
          <div className="member-modal-overlay" onClick={() => setDeleteTarget(null)}>
            <div className="member-modal" onClick={(event) => event.stopPropagation()}>
              <div className="member-modal__header">
                <div>
                  <h3>{page('settings.integrations.modal.delete.title')}</h3>
                  <p>{page('settings.integrations.modal.delete.desc', { name: deleteTarget.display_name })}</p>
                </div>
              </div>
              <Card>
                <div className="integration-status__detail">
                  {page('settings.integrations.modal.delete.deviceHint')}
                </div>
              </Card>
              <div className="member-modal__actions">
                <button
                  className="btn btn--outline btn--sm"
                  type="button"
                  onClick={() => setDeleteTarget(null)}
                  disabled={submitting}
                >
                  {page('settings.integrations.action.cancel')}
                </button>
                <button
                  className="btn btn--danger btn--sm"
                  type="button"
                  onClick={() => void handleDeleteInstance()}
                  disabled={submitting}
                >
                  {submitting ? page('settings.integrations.action.deleting') : page('settings.integrations.modal.delete.confirm')}
                </button>
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
                    {item.icon_url ? (
                      <img
                        src={item.icon_url}
                        alt={item.name}
                        className="integration-catalog-card__icon-image"
                      />
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
                        onClick={() => void openCreateModal(item)}
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

        {createModalOpen && formContext ? (
          <div className="member-modal-overlay" onClick={closeCreateModal}>
            <div className="member-modal" onClick={(event) => event.stopPropagation()}>
              <div className="member-modal__header">
                <div>
                  <h3>{page(
                    instanceFormMode === 'create'
                      ? 'settings.integrations.modal.create.title'
                      : 'settings.integrations.modal.edit.title',
                    { plugin: resolvePluginMaybeKey(formContext.pluginName, t) },
                  )}</h3>
                  <p>{resolvePluginConfigSpecDescription(formContext.configSpec, t) || page(
                    instanceFormMode === 'create'
                      ? 'settings.integrations.modal.create.desc'
                      : 'settings.integrations.modal.edit.desc',
                  )}</p>
                </div>
              </div>
              <form className="settings-form integration-config-form" onSubmit={handleSubmitInstance}>
                <div className="form-group">
                  <label>{page('settings.integrations.modal.instance.displayName')}</label>
                  <input
                    className="form-input"
                    value={createDraft.displayName}
                    onChange={(event) => setCreateDraft((current) => ({
                      ...current,
                      displayName: event.target.value,
                      fieldErrors: { ...current.fieldErrors, display_name: '' },
                    }))}
                    placeholder={page('settings.integrations.modal.instance.displayNamePlaceholder')}
                  />
                  {createDraft.fieldErrors.display_name ? <div className="form-help">{resolvePluginMaybeKey(createDraft.fieldErrors.display_name, t)}</div> : null}
                </div>
                {formContext.configSpec.ui_schema.sections.map((section) => (
                  <div key={section.id}>
                    <div className="form-group">
                      <label>{resolvePluginConfigSectionTitle(section, t)}</label>
                      {resolvePluginConfigSectionDescription(section, t) ? (
                        <div className="form-help">{resolvePluginConfigSectionDescription(section, t)}</div>
                      ) : null}
                    </div>
                    {section.fields.map((fieldKey) => {
                      const field = formContext.configSpec.config_schema.fields.find((item) => item.key === fieldKey);
                      if (!field) {
                        return null;
                      }
                      if (!isPluginFieldVisible(field.key, createDraft.values, formContext.configSpec.ui_schema.widgets)) {
                        return null;
                      }
                      return renderField(field, formContext.configSpec.ui_schema.widgets?.[field.key]);
                    })}
                  </div>
                ))}
                <div className="member-modal__actions">
                  <button className="btn btn--outline btn--sm" type="button" onClick={closeCreateModal} disabled={submitting}>
                    {page('settings.integrations.action.cancel')}
                  </button>
                  <button
                    className="btn btn--primary btn--sm"
                    type="submit"
                    disabled={
                      submitting
                      || (
                        instanceFormMode === 'create'
                        && formContext.pluginId === OPEN_XIAOAI_PLUGIN_ID
                        && (
                          openXiaoaiGatewayCandidates.length === 0
                          || (openXiaoaiGatewayCandidates.length > 1 && !selectedGatewayCandidate)
                        )
                      )
                    }
                  >
                    {submitting
                      ? page('settings.integrations.action.saving')
                      : (
                        resolvePluginConfigSubmitText(formContext.configSpec, t)
                        || page(
                          instanceFormMode === 'create'
                            ? 'settings.integrations.modal.create.submit'
                            : 'settings.integrations.modal.edit.submit',
                        )
                      )}
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
