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
  resolvePluginTextValue,
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
  PluginConfigPreviewArtifactRead,
  IntegrationActionResult,
  IntegrationCatalogItem,
  IntegrationDiscoveryItem,
  IntegrationInstance,
  IntegrationResource,
  PluginConfigFormRead,
  PluginManifestConfigPreviewAction,
  PluginManifestConfigField,
  PluginManifestConfigSpec,
  PluginManifestFieldUiSchema,
  PluginManifestRuntimeStateItem,
  PluginManifestRuntimeStateSection,
  PluginManifestUiSection,
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
  instanceDisplayNamePlaceholder: string | null;
  instanceDisplayNamePlaceholderKey: string | null;
  configSpec: PluginManifestConfigSpec;
};
const EMPTY_RUNTIME_STATE: Record<string, unknown> = {};
const EMPTY_PREVIEW_ARTIFACTS: PluginConfigPreviewArtifactRead[] = [];

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
  if (field.type === 'integer') {
    if (typeof value === 'number') {
      return Number.isInteger(value) ? value : value;
    }
    if (typeof value === 'string') {
      const normalizedValue = value.trim();
      if (!normalizedValue) {
        return field.required ? value : undefined;
      }
      const parsed = Number(normalizedValue);
      return Number.isInteger(parsed) ? parsed : value;
    }
  }
  if (field.type === 'number') {
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
  if (field.type === 'multi_enum') {
    if (!Array.isArray(value)) {
      return value;
    }
    const normalizedValues = value
      .filter((item): item is string => typeof item === 'string')
      .map((item) => item.trim())
      .filter(Boolean);
    if (normalizedValues.length === 0) {
      return field.required ? value : undefined;
    }
    return normalizedValues;
  }
  if (field.type === 'json') {
    if (typeof value === 'string') {
      const normalizedValue = value.trim();
      if (!normalizedValue) {
        return field.required ? value : undefined;
      }
      try {
        const parsed = JSON.parse(normalizedValue);
        if (Array.isArray(parsed) || (parsed && typeof parsed === 'object')) {
          return parsed;
        }
      } catch {
        return value;
      }
      return value;
    }
    if (Array.isArray(value) || (value && typeof value === 'object')) {
      return value;
    }
  }
  return value ?? undefined;
}

function normalizeDraftValuesForConfigSpec(
  configSpec: PluginManifestConfigSpec,
  values: Record<string, unknown>,
): Record<string, unknown> {
  const normalizedValues: Record<string, unknown> = {};
  for (const field of configSpec.config_schema.fields) {
    const rawValue = values[field.key];
    if (rawValue === undefined) {
      continue;
    }
    const normalizedValue = normalizeSubmitValue(field, rawValue);
    if (normalizedValue === undefined) {
      continue;
    }
    normalizedValues[field.key] = normalizedValue;
  }
  return normalizedValues;
}

function getMultiEnumValues(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter((item): item is string => typeof item === 'string');
}

function formatJsonEditorValue(value: unknown): string {
  if (typeof value === 'string') {
    return value;
  }
  if (value === null || value === undefined) {
    return '';
  }
  if (Array.isArray(value) || typeof value === 'object') {
    try {
      return JSON.stringify(value, null, 2);
    } catch {
      return '';
    }
  }
  return String(value);
}

function getVisibleSectionFieldKeys(
  section: PluginManifestUiSection,
  configSpec: PluginManifestConfigSpec,
  values: Record<string, unknown>,
): string[] {
  return section.fields.filter((fieldKey) => (
    isPluginFieldVisible(fieldKey, values, configSpec.ui_schema.widgets)
  ));
}

function isAdvancedUiSection(section: PluginManifestUiSection): boolean {
  return section.mode === 'advanced';
}

function areNormalizedValuesEqual(left: unknown, right: unknown): boolean {
  return JSON.stringify(left) === JSON.stringify(right);
}

function hasMeaningfulConfiguredValue(field: PluginManifestConfigField, draft: CreateDraft): boolean {
  if (field.type === 'secret') {
    return Boolean(draft.secrets[field.key]?.trim())
      || (Boolean(draft.secretFields[field.key]?.has_value) && !draft.clearSecretFields[field.key]);
  }

  const normalizedValue = normalizeSubmitValue(field, draft.values[field.key]);
  if (normalizedValue === undefined) {
    return false;
  }
  if (field.default !== undefined) {
    const normalizedDefaultValue = normalizeSubmitValue(field, field.default);
    if (areNormalizedValuesEqual(normalizedValue, normalizedDefaultValue)) {
      return false;
    }
  }
  return true;
}

function sectionHasConfiguredValue(
  section: PluginManifestUiSection,
  configSpec: PluginManifestConfigSpec,
  draft: CreateDraft,
): boolean {
  return section.fields.some((fieldKey) => {
    const field = configSpec.config_schema.fields.find((item) => item.key === fieldKey);
    if (!field) {
      return false;
    }
    return hasMeaningfulConfiguredValue(field, draft);
  });
}




function getPreviewActionErrorKey(actionKey: string): string {
  return `__preview_action__:${actionKey}`;
}

function getRuntimeItemErrorKey(itemKey: string): string {
  return `__runtime_item__:${itemKey}`;
}

function isMeaningfulRuntimeValue(value: unknown): boolean {
  if (value === null || value === undefined) {
    return false;
  }
  if (typeof value === 'string') {
    return value.trim().length > 0;
  }
  if (Array.isArray(value)) {
    return value.length > 0;
  }
  if (typeof value === 'object') {
    return Object.keys(value as Record<string, unknown>).length > 0;
  }
  return true;
}

function getObjectPathValue(payload: unknown, source: string): unknown {
  if (!source.trim()) {
    return undefined;
  }
  const parts = source.split('.').map((item) => item.trim()).filter(Boolean);
  let current: unknown = payload;
  for (const part of parts) {
    if (Array.isArray(current)) {
      const index = Number(part);
      current = Number.isInteger(index) ? current[index] : undefined;
      continue;
    }
    if (!current || typeof current !== 'object') {
      return undefined;
    }
    current = (current as Record<string, unknown>)[part];
  }
  return current;
}

function buildRuntimeSelectionValue(item: PluginManifestRuntimeStateItem, candidate: Record<string, unknown>): unknown {
  if (item.selection_mode === 'field') {
    return item.selection_value_field ? getObjectPathValue(candidate, item.selection_value_field) : undefined;
  }
  if (item.selection_mode === 'object') {
    const nextValue: Record<string, unknown> = {};
    for (const fieldPath of item.selection_object_fields ?? []) {
      const nextFieldValue = getObjectPathValue(candidate, fieldPath);
      if (nextFieldValue !== undefined) {
        const key = fieldPath.split('.').pop() ?? fieldPath;
        nextValue[key] = nextFieldValue;
      }
    }
    return nextValue;
  }
  return undefined;
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
  const [createStepIndex, setCreateStepIndex] = useState(0);
  const [showAdvancedWizardSections, setShowAdvancedWizardSections] = useState(false);

  const [previewRuntimeState, setPreviewRuntimeState] = useState<Record<string, unknown>>(EMPTY_RUNTIME_STATE);
  const [previewArtifacts, setPreviewArtifacts] = useState<PluginConfigPreviewArtifactRead[]>(EMPTY_PREVIEW_ARTIFACTS);
  const [previewLoadingActionKey, setPreviewLoadingActionKey] = useState<string | null>(null);
  const [previewResultActionKey, setPreviewResultActionKey] = useState<string | null>(null);
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

  const allWizardSections = useMemo(() => {
    if (!formContext) {
      return [];
    }
    return formContext.configSpec.ui_schema.sections.filter((section) => (
      getVisibleSectionFieldKeys(section, formContext.configSpec, createDraft.values).length > 0
    ));
  }, [formContext, createDraft.values]);

  const defaultWizardSections = useMemo(
    () => allWizardSections.filter((section) => !isAdvancedUiSection(section)),
    [allWizardSections],
  );
  const advancedWizardSections = useMemo(
    () => allWizardSections.filter((section) => isAdvancedUiSection(section)),
    [allWizardSections],
  );
  const wizardSections = useMemo(() => {
    if (
      showAdvancedWizardSections
      || advancedWizardSections.length === 0
      || defaultWizardSections.length === 0
    ) {
      return allWizardSections;
    }
    return defaultWizardSections;
  }, [advancedWizardSections.length, allWizardSections, defaultWizardSections, showAdvancedWizardSections]);
  const hasHiddenAdvancedWizardSections = advancedWizardSections.length > 0
    && !showAdvancedWizardSections
    && defaultWizardSections.length > 0;
  const hasConfiguredHiddenAdvancedSections = Boolean(
    formContext
    && hasHiddenAdvancedWizardSections
    && advancedWizardSections.some((section) => sectionHasConfiguredValue(section, formContext.configSpec, createDraft)),
  );
  const wizardMode = Boolean(formContext && wizardSections.length > 1);
  const activeWizardStepIndex = wizardMode
    ? Math.min(createStepIndex, Math.max(wizardSections.length - 1, 0))
    : 0;
  const currentWizardSection = wizardMode ? wizardSections[activeWizardStepIndex] : null;
  const renderedSections = wizardMode
    ? (currentWizardSection ? [currentWizardSection] : [])
    : wizardSections;
  const isLastWizardStep = !wizardMode || activeWizardStepIndex === wizardSections.length - 1;
  const previewActions = formContext?.configSpec.ui_schema.actions ?? [];
  const runtimeStateSections = formContext?.configSpec.ui_schema.runtime_sections ?? [];

  useEffect(() => {
    if (!createModalOpen) {
      setCreateStepIndex(0);
      setShowAdvancedWizardSections(false);
      setPreviewRuntimeState(EMPTY_RUNTIME_STATE);
      setPreviewArtifacts(EMPTY_PREVIEW_ARTIFACTS);
      setPreviewLoadingActionKey(null);
      setPreviewResultActionKey(null);
      return;
    }
    setCreateStepIndex(0);
    setShowAdvancedWizardSections(false);
    setPreviewRuntimeState(EMPTY_RUNTIME_STATE);
    setPreviewArtifacts(EMPTY_PREVIEW_ARTIFACTS);
    setPreviewLoadingActionKey(null);
    setPreviewResultActionKey(null);
  }, [createModalOpen, formContext?.pluginId, instanceFormMode]);

  useEffect(() => {
    if (!wizardMode) {
      return;
    }
    if (createStepIndex > wizardSections.length - 1) {
      setCreateStepIndex(Math.max(wizardSections.length - 1, 0));
    }
  }, [wizardMode, createStepIndex, wizardSections.length]);

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
  const createDisplayNamePlaceholder = formContext
    ? (
      resolvePluginTextValue(
        formContext.instanceDisplayNamePlaceholder,
        formContext.instanceDisplayNamePlaceholderKey,
        t,
      ) || page('settings.integrations.modal.instance.displayNamePlaceholder')
    )
    : page('settings.integrations.modal.instance.displayNamePlaceholder');
  function getConfigField(fieldKey: string): PluginManifestConfigField | null {
    return formContext?.configSpec.config_schema.fields.find((item) => item.key === fieldKey) ?? null;
  }

  function hasDraftFieldValue(fieldKey: string): boolean {
    const field = getConfigField(fieldKey);
    if (!field) {
      return false;
    }
    if (field.type === 'secret') {
      return Boolean(createDraft.secrets[field.key]?.trim())
        || (Boolean(createDraft.secretFields[field.key]?.has_value) && !createDraft.clearSecretFields[field.key]);
    }
    return isMeaningfulRuntimeValue(normalizeSubmitValue(field, createDraft.values[field.key]));
  }

  function resetPreviewState(errorKeys: string[] = []) {
    setPreviewRuntimeState(EMPTY_RUNTIME_STATE);
    setPreviewArtifacts(EMPTY_PREVIEW_ARTIFACTS);
    setPreviewLoadingActionKey(null);
    setPreviewResultActionKey(null);
    if (errorKeys.length === 0) {
      return;
    }
    setCreateDraft((current) => {
      const nextFieldErrors = { ...current.fieldErrors };
      for (const errorKey of errorKeys) {
        nextFieldErrors[errorKey] = '';
      }
      return {
        ...current,
        fieldErrors: nextFieldErrors,
      };
    });
  }

  function getPreviewSupplementErrorKeys(): string[] {
    return [
      ...previewActions.map((action) => getPreviewActionErrorKey(action.key)),
      ...runtimeStateSections.flatMap((section) => section.items.map((item) => getRuntimeItemErrorKey(item.key))),
    ];
  }

  function getSectionPreviewActions(sectionId: string): PluginManifestConfigPreviewAction[] {
    return previewActions.filter((action) => (
      action.section_id === sectionId
      && (action.modes ?? ['create', 'edit']).includes(instanceFormMode)
    ));
  }

  function getSectionRuntimeSections(sectionId: string): PluginManifestRuntimeStateSection[] {
    return runtimeStateSections.filter((section) => (
      section.section_id === sectionId
      && (!section.action_key || section.action_key === previewResultActionKey)
    ));
  }

  function findPreviewActionByActionKey(actionKey: string): PluginManifestConfigPreviewAction | null {
    return previewActions.find((item) => (item.action_key ?? item.key) === actionKey) ?? null;
  }

  function resolveActionLabel(action: PluginManifestConfigPreviewAction): string {
    return resolvePluginTextValue(action.label, action.label_key, t) || action.key;
  }

  function resolveActionDescription(action: PluginManifestConfigPreviewAction): string {
    return resolvePluginTextValue(action.description, action.description_key, t) || '';
  }

  function resolveRuntimeText(value: string | null | undefined, valueKey: string | null | undefined): string {
    return resolvePluginTextValue(value ?? null, valueKey ?? null, t) || '';
  }

  function isPreviewActionReady(action: PluginManifestConfigPreviewAction): boolean {
    return (action.depends_on_fields ?? []).every((fieldKey) => hasDraftFieldValue(fieldKey));
  }

  async function resolveIntegrationDraftConfig(
    pluginId: string,
    configSpec: PluginManifestConfigSpec,
    draft: CreateDraft,
    scopeKey?: string,
  ) {
    if (!currentHouseholdId) {
      return;
    }
    const resolveSeq = configResolveSeqRef.current + 1;
    configResolveSeqRef.current = resolveSeq;

    let workingValues = normalizeDraftValuesForConfigSpec(configSpec, draft.values);
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
        instanceDisplayNamePlaceholder: item.instance_display_name_placeholder ?? null,
        instanceDisplayNamePlaceholderKey: item.instance_display_name_placeholder_key ?? null,
        configSpec: resolvedForm.config_spec,
      });
      setCreateDraft(buildDraft(resolvedForm.config_spec, {
        form: resolvedForm,
      }));
      resetPreviewState(getPreviewSupplementErrorKeys());
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
        instanceDisplayNamePlaceholder: catalogItem?.instance_display_name_placeholder ?? null,
        instanceDisplayNamePlaceholderKey: catalogItem?.instance_display_name_placeholder_key ?? null,
        configSpec: configForm.config_spec,
      });
      setCreateDraft(buildDraft(configForm.config_spec, {
        displayName: instance.display_name,
        form: configForm,
      }));
      resetPreviewState(getPreviewSupplementErrorKeys());
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
    setCreateStepIndex(0);
    setShowAdvancedWizardSections(false);
    resetPreviewState(getPreviewSupplementErrorKeys());
  }

  function buildPreviewPayload(draft: CreateDraft) {
    const payloadValues: Record<string, unknown> = {};
    const secretValues: Record<string, string> = {};
    const clearSecretFields: string[] = [];
    if (!formContext) {
      return {
        values: payloadValues,
        secret_values: secretValues,
        clear_secret_fields: clearSecretFields,
      };
    }
    for (const field of formContext.configSpec.config_schema.fields) {
      if (field.type === 'secret') {
        const rawSecret = (draft.secrets[field.key] ?? '').trim();
        if (rawSecret) {
          secretValues[field.key] = rawSecret;
          continue;
        }
        if (draft.clearSecretFields[field.key]) {
          clearSecretFields.push(field.key);
        }
        continue;
      }
      const rawValue = draft.values[field.key];
      if (rawValue === undefined) {
        continue;
      }
      const normalizedValue = normalizeSubmitValue(field, rawValue);
      if (normalizedValue === undefined) {
        continue;
      }
      payloadValues[field.key] = normalizedValue;
    }
    return {
      values: payloadValues,
      secret_values: secretValues,
      clear_secret_fields: clearSecretFields,
    };
  }


  function applyPreviewResetToDraft(draft: CreateDraft, fieldKey: string): CreateDraft {
    const resetActions = previewActions.filter((action) => (action.reset_on_change_fields ?? []).includes(fieldKey));
    if (resetActions.length === 0) {
      return draft;
    }
    const clearFieldKeys = new Set<string>();
    for (const action of resetActions) {
      for (const clearFieldKey of action.clear_fields_on_reset ?? []) {
        clearFieldKeys.add(clearFieldKey);
      }
    }
    const nextValues = { ...draft.values };
    const nextFieldErrors = { ...draft.fieldErrors };
    for (const clearFieldKey of clearFieldKeys) {
      delete nextValues[clearFieldKey];
      nextFieldErrors[clearFieldKey] = '';
    }
    for (const errorKey of getPreviewSupplementErrorKeys()) {
      nextFieldErrors[errorKey] = '';
    }
    return {
      ...draft,
      values: nextValues,
      fieldErrors: nextFieldErrors,
    };
  }

  async function updateValue(fieldKey: string, value: unknown) {
    const baseDraft: CreateDraft = {
      ...createDraft,
      values: { ...createDraft.values, [fieldKey]: value },
      fieldErrors: {
        ...createDraft.fieldErrors,
        [fieldKey]: '',
      },
    };
    const nextDraft = applyPreviewResetToDraft(baseDraft, fieldKey);
    setCreateDraft(nextDraft);
    if (nextDraft !== baseDraft) {
      resetPreviewState(getPreviewSupplementErrorKeys());
    }
    if (!formContext || !shouldResolveConfigChange(formContext.configSpec, fieldKey)) {
      return;
    }
    await resolveIntegrationDraftConfig(
      formContext.pluginId,
      formContext.configSpec,
      nextDraft,
      instanceFormMode === 'edit' ? (editingInstanceId ?? undefined) : undefined,
    );
  }

  function updateSecret(fieldKey: string, value: string) {
    const shouldResetPreview = previewActions.some((action) => (action.reset_on_change_fields ?? []).includes(fieldKey));
    if (shouldResetPreview) {
      resetPreviewState(getPreviewSupplementErrorKeys());
    }
    setCreateDraft((current) => applyPreviewResetToDraft({
      ...current,
      secrets: { ...current.secrets, [fieldKey]: value },
      clearSecretFields: value.trim()
        ? { ...current.clearSecretFields, [fieldKey]: false }
        : current.clearSecretFields,
      fieldErrors: { ...current.fieldErrors, [fieldKey]: '' },
    }, fieldKey));
  }

  function toggleClearSecret(fieldKey: string, checked: boolean) {
    const shouldResetPreview = previewActions.some((action) => (action.reset_on_change_fields ?? []).includes(fieldKey));
    if (shouldResetPreview) {
      resetPreviewState(getPreviewSupplementErrorKeys());
    }
    setCreateDraft((current) => applyPreviewResetToDraft({
      ...current,
      secrets: checked
        ? { ...current.secrets, [fieldKey]: '' }
        : current.secrets,
      clearSecretFields: { ...current.clearSecretFields, [fieldKey]: checked },
      fieldErrors: { ...current.fieldErrors, [fieldKey]: '' },
    }, fieldKey));
  }

  async function executePreviewAction(
    action: PluginManifestConfigPreviewAction,
    options?: {
      showLoading?: boolean;
    },
  ) {
    if (!currentHouseholdId || !formContext) {
      return;
    }
    const shouldShowLoading = options?.showLoading ?? true;
    if (shouldShowLoading) {
      setPreviewLoadingActionKey(action.key);
    }
    try {
      const previewForm = await settingsApi.previewHouseholdPluginConfigForm(currentHouseholdId, formContext.pluginId, {
        scope_type: 'integration_instance',
        scope_key: instanceFormMode === 'edit' ? (editingInstanceId ?? null) : null,
        ...buildPreviewPayload(createDraft),
        action_key: action.action_key ?? action.key,
      });
      setFormContext((current) => {
        if (!current || current.pluginId !== formContext.pluginId) {
          return current;
        }
        return {
          ...current,
          configSpec: previewForm.config_spec,
        };
      });
      setCreateDraft((current) => {
        const displayNameError = current.fieldErrors.display_name;
        const nextFieldErrors: Record<string, string> = {
          ...(displayNameError ? { display_name: displayNameError } : {}),
          ...previewForm.view.field_errors,
        };
        for (const errorKey of getPreviewSupplementErrorKeys()) {
          nextFieldErrors[errorKey] = '';
        }
        return {
          ...current,
          values: previewForm.view.values,
          secretFields: Object.keys(previewForm.view.secret_fields).length > 0
            ? previewForm.view.secret_fields
            : current.secretFields,
          fieldErrors: nextFieldErrors,
        };
      });
      setPreviewRuntimeState(previewForm.view.runtime_state ?? EMPTY_RUNTIME_STATE);
      setPreviewArtifacts(previewForm.view.preview_artifacts ?? EMPTY_PREVIEW_ARTIFACTS);
      setPreviewResultActionKey(action.key);
      setError('');
    } catch (previewError) {
      const fallbackMessage = previewError instanceof Error
        ? previewError.message
        : page('settings.integrations.error.previewActionFailed');
      if (previewError instanceof ApiError) {
        const payload = previewError.payload as { detail?: { field_errors?: Record<string, string> } } | undefined;
        if (payload?.detail?.field_errors) {
          setCreateDraft((current) => ({
            ...current,
            fieldErrors: {
              ...current.fieldErrors,
              ...payload.detail!.field_errors!,
              [getPreviewActionErrorKey(action.key)]: fallbackMessage,
            },
          }));
        }
      }
      setPreviewRuntimeState(EMPTY_RUNTIME_STATE);
      setPreviewArtifacts(EMPTY_PREVIEW_ARTIFACTS);
      setPreviewResultActionKey(action.key);
      setCreateDraft((current) => ({
        ...current,
        fieldErrors: {
          ...current.fieldErrors,
          [getPreviewActionErrorKey(action.key)]: fallbackMessage,
        },
      }));
      setError(fallbackMessage);
    } finally {
      if (shouldShowLoading) {
        setPreviewLoadingActionKey((current) => (current === action.key ? null : current));
      }
    }
  }

  function validateSingleField(field: PluginManifestConfigField): string | null {
    const fieldLabel = resolvePluginFieldLabel(field, t);

    if (field.type === 'secret') {
      const rawSecret = createDraft.secrets[field.key] ?? '';
      const hasExistingValue = Boolean(createDraft.secretFields[field.key]?.has_value) && !createDraft.clearSecretFields[field.key];
      if (field.required && !rawSecret.trim() && !hasExistingValue) {
        return page('settings.integrations.modal.create.validation.required', { field: fieldLabel });
      }
      return null;
    }

    const rawValue = createDraft.values[field.key];
    const normalizedValue = normalizeSubmitValue(field, rawValue);

    if (normalizedValue === undefined) {
      if (field.required && !field.nullable) {
        return page('settings.integrations.modal.create.validation.required', { field: fieldLabel });
      }
      return null;
    }

    if (field.type === 'integer' && (typeof normalizedValue !== 'number' || !Number.isInteger(normalizedValue))) {
      return page('settings.integrations.modal.create.validation.integer', { field: fieldLabel });
    }
    if (field.type === 'number' && (typeof normalizedValue !== 'number' || Number.isNaN(normalizedValue))) {
      return page('settings.integrations.modal.create.validation.number', { field: fieldLabel });
    }
    if (field.type === 'enum') {
      const allowedValues = new Set((field.enum_options ?? []).map((option) => option.value));
      if (typeof normalizedValue !== 'string' || !allowedValues.has(normalizedValue)) {
        return page('settings.integrations.modal.create.validation.select', { field: fieldLabel });
      }
    }
    if (field.type === 'multi_enum') {
      if (!Array.isArray(normalizedValue)) {
        return page('settings.integrations.modal.create.validation.multiSelect', { field: fieldLabel });
      }
      if (field.required && normalizedValue.length === 0) {
        return page('settings.integrations.modal.create.validation.multiSelect', { field: fieldLabel });
      }
    }
    if (field.type === 'json') {
      if (typeof normalizedValue === 'string') {
        return page('settings.integrations.modal.create.validation.json', { field: fieldLabel });
      }
      if (!Array.isArray(normalizedValue) && typeof normalizedValue !== 'object') {
        return page('settings.integrations.modal.create.validation.json', { field: fieldLabel });
      }
    }
    return null;
  }

  function validateRuntimeSectionRequirements(
    sectionId: string,
    nextFieldErrors: Record<string, string>,
  ): boolean {
    let hasError = false;
    for (const runtimeSection of getSectionRuntimeSections(sectionId)) {
      for (const item of runtimeSection.items) {
        const errorKey = getRuntimeItemErrorKey(item.key);
        if (item.kind !== 'candidate_select' || !item.required || !item.target_field) {
          nextFieldErrors[errorKey] = '';
          continue;
        }
        const targetField = getConfigField(item.target_field);
        const selectedValue = targetField
          ? normalizeSubmitValue(targetField, createDraft.values[item.target_field])
          : createDraft.values[item.target_field];
        if (isMeaningfulRuntimeValue(selectedValue)) {
          nextFieldErrors[errorKey] = '';
          continue;
        }
        nextFieldErrors[errorKey] = resolveRuntimeText(item.required_message, item.required_message_key)
          || page('settings.integrations.modal.create.validation.required', {
            field: resolveRuntimeText(item.label, item.label_key) || item.target_field,
          });
        hasError = true;
      }
    }
    return hasError;
  }

  function validateCurrentWizardStep(): boolean {
    if (!formContext || !wizardMode || !currentWizardSection) {
      return true;
    }

    const nextFieldErrors = { ...createDraft.fieldErrors };
    let hasError = false;

    if (activeWizardStepIndex === 0) {
      if (!createDraft.displayName.trim()) {
        nextFieldErrors.display_name = page('settings.integrations.modal.create.displayNameRequired');
        hasError = true;
      } else {
        nextFieldErrors.display_name = '';
      }
    }

    for (const fieldKey of currentWizardSection.fields) {
      const field = formContext.configSpec.config_schema.fields.find((item) => item.key === fieldKey);
      if (!field) {
        continue;
      }
      if (!isPluginFieldVisible(field.key, createDraft.values, formContext.configSpec.ui_schema.widgets)) {
        nextFieldErrors[field.key] = '';
        continue;
      }
      const fieldError = validateSingleField(field);
      nextFieldErrors[field.key] = fieldError ?? '';
      hasError = hasError || Boolean(fieldError);
    }

    hasError = validateRuntimeSectionRequirements(currentWizardSection.id, nextFieldErrors) || hasError;

    setCreateDraft((current) => ({
      ...current,
      fieldErrors: nextFieldErrors,
    }));
    return !hasError;
  }

  function goToNextWizardStep() {
    if (!wizardMode) {
      return;
    }
    if (!validateCurrentWizardStep()) {
      return;
    }
    setCreateStepIndex((current) => Math.min(current + 1, wizardSections.length - 1));
  }

  function revealAdvancedWizardSections() {
    if (advancedWizardSections.length === 0) {
      return;
    }
    const firstAdvancedIndex = allWizardSections.findIndex((section) => isAdvancedUiSection(section));
    setShowAdvancedWizardSections(true);
    if (firstAdvancedIndex >= 0) {
      setCreateStepIndex(firstAdvancedIndex);
    }
  }

  function getRuntimeCandidateSelectionValue(item: PluginManifestRuntimeStateItem): unknown {
    if (!item.target_field) {
      return undefined;
    }
    return createDraft.values[item.target_field];
  }

  function isRuntimeCandidateSelected(item: PluginManifestRuntimeStateItem, candidate: Record<string, unknown>): boolean {
    const selectedValue = getRuntimeCandidateSelectionValue(item);
    if (selectedValue === undefined || item.selected_match_field == null) {
      return false;
    }
    const candidateMatchValue = getObjectPathValue(candidate, item.selected_match_field);
    if (item.selection_mode === 'field') {
      return areNormalizedValuesEqual(selectedValue, candidateMatchValue);
    }
    if (!selectedValue || typeof selectedValue !== 'object') {
      return false;
    }
    const selectedKey = item.selected_match_field.split('.').pop() ?? item.selected_match_field;
    return areNormalizedValuesEqual((selectedValue as Record<string, unknown>)[selectedKey], candidateMatchValue);
  }

  function renderRuntimeStateItem(item: PluginManifestRuntimeStateItem) {
    const itemError = createDraft.fieldErrors[getRuntimeItemErrorKey(item.key)];
    const itemLabel = resolveRuntimeText(item.label, item.label_key);
    const itemDescription = resolveRuntimeText(item.description, item.description_key);

    if (item.kind === 'status_badge') {
      const rawValue = getObjectPathValue(previewRuntimeState, item.source);
      if (!isMeaningfulRuntimeValue(rawValue)) {
        return null;
      }
      const statusValue = String(rawValue);
      const option = (item.status_options ?? []).find((statusOption) => statusOption.value === statusValue) ?? null;
      const badgeLabel = option
        ? resolveRuntimeText(option.label, option.label_key) || statusValue
        : statusValue;
      const badgeClassName = option?.tone === 'success'
        ? 'badge badge--success'
        : option?.tone === 'warning'
          ? 'badge badge--warning'
          : option?.tone === 'danger'
            ? 'badge badge--danger'
            : 'badge';
      return (
        <div key={item.key} className="form-group" style={{ marginBottom: '12px' }}>
          {itemLabel ? <label>{itemLabel}</label> : null}
          {itemDescription ? <div className="form-help">{itemDescription}</div> : null}
          <div style={{ marginTop: itemLabel || itemDescription ? '8px' : 0 }}>
            <span className={badgeClassName}>{badgeLabel}</span>
          </div>
        </div>
      );
    }

    if (item.kind === 'text') {
      const rawValue = getObjectPathValue(previewRuntimeState, item.source);
      if (!isMeaningfulRuntimeValue(rawValue)) {
        const emptyText = resolveRuntimeText(item.empty_text, item.empty_text_key);
        return emptyText ? <div key={item.key} className="form-help">{emptyText}</div> : null;
      }
      const textValue = typeof rawValue === 'string'
        ? rawValue
        : typeof rawValue === 'number' || typeof rawValue === 'boolean'
          ? String(rawValue)
          : formatJsonEditorValue(rawValue);
      return (
        <div key={item.key} className="form-group" style={{ marginBottom: '12px' }}>
          {itemLabel ? <label>{itemLabel}</label> : null}
          {itemDescription ? <div className="form-help">{itemDescription}</div> : null}
          <div className="integration-status__detail" style={{ marginTop: itemLabel || itemDescription ? '8px' : 0 }}>
            {textValue}
          </div>
          {itemError ? <div className="form-help" style={{ marginTop: '8px' }}>{resolvePluginMaybeKey(itemError, t)}</div> : null}
        </div>
      );
    }

    if (item.kind === 'link') {
      const rawUrl = getObjectPathValue(previewRuntimeState, item.source);
      const url = typeof rawUrl === 'string' ? rawUrl.trim() : '';
      if (!url) {
        const emptyText = resolveRuntimeText(item.empty_text, item.empty_text_key);
        return emptyText ? <div key={item.key} className="form-help">{emptyText}</div> : null;
      }
      const linkTextSource = item.link_text_source ? getObjectPathValue(previewRuntimeState, item.link_text_source) : null;
      const linkText = resolveRuntimeText(item.link_text, item.link_text_key)
        || (typeof linkTextSource === 'string' ? linkTextSource.trim() : '')
        || url;
      return (
        <div key={item.key} className="form-group" style={{ marginBottom: '12px' }}>
          {itemLabel ? <label>{itemLabel}</label> : null}
          {itemDescription ? <div className="form-help">{itemDescription}</div> : null}
          <a
            href={url}
            target="_blank"
            rel="noreferrer"
            style={{ color: 'var(--brand-primary)', textDecoration: 'underline', wordBreak: 'break-all', display: 'inline-block', marginTop: itemLabel || itemDescription ? '8px' : 0 }}
          >
            {linkText}
          </a>
          {itemError ? <div className="form-help" style={{ marginTop: '8px' }}>{resolvePluginMaybeKey(itemError, t)}</div> : null}
        </div>
      );
    }

    if (item.kind === 'candidate_select') {
      const rawCandidates = getObjectPathValue(previewRuntimeState, item.source);
      const candidates = Array.isArray(rawCandidates)
        ? rawCandidates.filter((candidate): candidate is Record<string, unknown> => Boolean(candidate && typeof candidate === 'object'))
        : [];
      const emptyText = resolveRuntimeText(item.empty_text, item.empty_text_key);
      return (
        <div key={item.key} className="form-group" style={{ marginBottom: '12px' }}>
          {itemLabel ? <label>{itemLabel}</label> : null}
          {itemDescription ? <div className="form-help">{itemDescription}</div> : null}
          {candidates.length === 0 ? (
            emptyText ? <div className="form-help" style={{ marginTop: itemLabel || itemDescription ? '8px' : 0 }}>{emptyText}</div> : null
          ) : (
            <div style={{ display: 'grid', gap: '8px', marginTop: itemLabel || itemDescription ? '8px' : 0 }}>
              {candidates.map((candidate, index) => {
                const label = (item.option_label_fields ?? [])
                  .map((fieldPath) => getObjectPathValue(candidate, fieldPath))
                  .find((fieldValue) => typeof fieldValue === 'string' && fieldValue.trim()) as string | undefined;
                const descriptionParts = (item.option_description_fields ?? [])
                  .map((fieldPath) => getObjectPathValue(candidate, fieldPath))
                  .filter((fieldValue): fieldValue is string => typeof fieldValue === 'string' && fieldValue.trim().length > 0);
                const candidateKey = String(getObjectPathValue(candidate, item.selected_match_field ?? '') ?? index);
                const selected = isRuntimeCandidateSelected(item, candidate);
                return (
                  <button
                    key={`${item.key}-${candidateKey}`}
                    className="btn"
                    type="button"
                    onClick={() => {
                      if (!item.target_field) {
                        return;
                      }
                      const nextValue = buildRuntimeSelectionValue(item, candidate);
                      setCreateDraft((current) => ({
                        ...current,
                        values: { ...current.values, [item.target_field!]: nextValue },
                        fieldErrors: {
                          ...current.fieldErrors,
                          [item.target_field!]: '',
                          [getRuntimeItemErrorKey(item.key)]: '',
                        },
                      }));
                    }}
                    style={{
                      textAlign: 'left',
                      border: selected ? '1px solid var(--brand-primary)' : '1px solid var(--border-light)',
                      background: selected ? 'var(--brand-primary-light)' : 'var(--bg-card)',
                      color: 'var(--text-primary)',
                      borderRadius: '12px',
                      padding: '12px',
                    }}
                  >
                    <div style={{ fontWeight: 600, marginBottom: descriptionParts.length > 0 ? '4px' : 0 }}>
                      {label || candidateKey}
                    </div>
                    {descriptionParts.length > 0 ? (
                      <div className="form-help">{descriptionParts.join(' / ')}</div>
                    ) : null}
                  </button>
                );
              })}
            </div>
          )}
          {itemError ? <div className="form-help" style={{ marginTop: '8px' }}>{resolvePluginMaybeKey(itemError, t)}</div> : null}
        </div>
      );
    }

    return null;
  }

  function renderConfigPreviewPanel(sectionId: string) {
    const sectionActions = getSectionPreviewActions(sectionId);
    const sectionRuntimeSections = getSectionRuntimeSections(sectionId);
    const shouldRenderArtifacts = previewArtifacts.length > 0 && (
      sectionActions.some((action) => action.key === previewResultActionKey)
      || sectionRuntimeSections.some((runtimeSection) => !runtimeSection.action_key || runtimeSection.action_key === previewResultActionKey)
    );
    if (sectionActions.length === 0 && sectionRuntimeSections.length === 0 && !shouldRenderArtifacts) {
      return null;
    }
    return (
      <div
        key={`config-preview-${sectionId}`}
        style={{
          border: '1px solid var(--border-light)',
          borderRadius: '16px',
          padding: '16px',
          marginBottom: '16px',
          background: 'var(--bg-card)',
        }}
      >
        {sectionActions.map((action) => {
          const actionError = createDraft.fieldErrors[getPreviewActionErrorKey(action.key)];
          const actionLoading = previewLoadingActionKey === action.key;
          return (
            <div key={action.key} className="form-group" style={{ marginBottom: '12px' }}>
              <label>{resolveActionLabel(action)}</label>
              {resolveActionDescription(action) ? <div className="form-help">{resolveActionDescription(action)}</div> : null}
              <div style={{ marginTop: '8px' }}>
                <button
                  className="btn btn--primary btn--sm"
                  type="button"
                  onClick={() => void executePreviewAction(action)}
                  disabled={submitting || Boolean(previewLoadingActionKey) || !isPreviewActionReady(action)}
                >
                  {actionLoading ? page('common.loading') : resolveActionLabel(action)}
                </button>
              </div>
              {!isPreviewActionReady(action) ? (
                <div className="form-help" style={{ marginTop: '8px' }}>
                  {page('settings.integrations.modal.create.previewAction.dependencyHint')}
                </div>
              ) : null}
              {actionError ? <div className="form-help" style={{ marginTop: '8px' }}>{resolvePluginMaybeKey(actionError, t)}</div> : null}
            </div>
          );
        })}

        {sectionRuntimeSections.map((runtimeSection) => (
          <div key={runtimeSection.key} style={{ marginTop: '8px' }}>
            {resolveRuntimeText(runtimeSection.title, runtimeSection.title_key) ? (
              <div className="form-group" style={{ marginBottom: '8px' }}>
                <label>{resolveRuntimeText(runtimeSection.title, runtimeSection.title_key)}</label>
                {resolveRuntimeText(runtimeSection.description, runtimeSection.description_key) ? (
                  <div className="form-help">{resolveRuntimeText(runtimeSection.description, runtimeSection.description_key)}</div>
                ) : null}
              </div>
            ) : null}
            {runtimeSection.items
              .filter((item) => !item.action_key || item.action_key === previewResultActionKey)
              .map((item) => renderRuntimeStateItem(item))}
          </div>
        ))}

        {shouldRenderArtifacts ? (
          <div style={{ display: 'grid', gap: '8px' }}>
            {previewArtifacts.map((artifact) => (
              <div key={artifact.key} className="form-help">
                {artifact.kind === 'external_url' || artifact.kind === 'image_url' ? (
                  <a href={artifact.url ?? '#'} target="_blank" rel="noreferrer" style={{ color: 'var(--brand-primary)', textDecoration: 'underline', wordBreak: 'break-all' }}>
                    {artifact.label || artifact.url}
                  </a>
                ) : (
                  artifact.text ?? artifact.label ?? ''
                )}
              </div>
            ))}
          </div>
        ) : null}
      </div>
    );
  }

  function renderField(field: PluginManifestConfigField, widget?: PluginManifestFieldUiSchema) {
    const fieldError = createDraft.fieldErrors[field.key];
    if (widget?.widget === 'display') {
      const rawValue = createDraft.values[field.key] ?? field.default;
      const displayValue = typeof rawValue === 'string'
        ? rawValue
        : typeof rawValue === 'number' || typeof rawValue === 'boolean'
          ? String(rawValue)
          : formatJsonEditorValue(rawValue);
      return (
        <div key={field.key} className="form-group">
          <label>{resolvePluginFieldLabel(field, t)}</label>
          <pre className="channel-config-field__display">
            {displayValue || resolvePluginWidgetHelpText(widget, field, t) || page('settings.integrations.modal.config.displayEmpty')}
          </pre>
          <div className="form-help">{resolvePluginWidgetHelpText(widget, field, t)}</div>
          {fieldError ? <div className="form-help">{resolvePluginMaybeKey(fieldError, t)}</div> : null}
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
    if (field.type === 'multi_enum') {
      return (
        <div key={field.key} className="form-group">
          <label>{resolvePluginFieldLabel(field, t)}</label>
          <select
            className="form-select"
            multiple
            value={getMultiEnumValues(createDraft.values[field.key])}
            onChange={(event) => {
              const nextValues = Array.from(event.target.selectedOptions).map((option) => option.value);
              void updateValue(field.key, nextValues);
            }}
          >
            {(field.enum_options ?? []).map((option) => (
              <option key={option.value} value={option.value}>{resolvePluginOptionLabel(option, t)}</option>
            ))}
          </select>
          <div className="form-help">{resolvePluginWidgetHelpText(widget, field, t)}</div>
          <div className="form-help">{page('settings.integrations.modal.config.multiSelectHint')}</div>
          {fieldError ? <div className="form-help">{resolvePluginMaybeKey(fieldError, t)}</div> : null}
        </div>
      );
    }
    if (field.type === 'json') {
      return (
        <div key={field.key} className="form-group">
          <label>{resolvePluginFieldLabel(field, t)}</label>
          <textarea
            className="form-input"
            value={formatJsonEditorValue(createDraft.values[field.key])}
            onChange={(event) => void updateValue(field.key, event.target.value)}
            placeholder={resolvePluginWidgetPlaceholder(widget, t) || undefined}
            spellCheck={false}
            rows={8}
          />
          <div className="form-help">{resolvePluginWidgetHelpText(widget, field, t)}</div>
          <div className="form-help">{page('settings.integrations.modal.config.jsonHint')}</div>
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
      const nextStatus = page(
        instanceFormMode === 'create'
          ? 'settings.integrations.status.instanceCreated'
          : 'settings.integrations.status.instanceUpdated',
        { name: instance.display_name },
      );
      setStatus(nextStatus);
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
                {wizardMode ? (
                  <div
                    style={{
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '12px',
                      marginBottom: '16px',
                    }}
                  >
                    <div className="integration-status__detail">
                      {page('settings.integrations.modal.create.step.progress', {
                        current: activeWizardStepIndex + 1,
                        total: wizardSections.length,
                      })}
                    </div>
                    <div className="form-help">{page('settings.integrations.modal.create.step.hint')}</div>
                    <div
                      style={{
                        display: 'grid',
                        gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
                        gap: '8px',
                      }}
                    >
                      {wizardSections.map((section, index) => {
                        const active = index === activeWizardStepIndex;
                        const completed = index < activeWizardStepIndex;
                        return (
                          <button
                            key={section.id}
                            type="button"
                            onClick={() => setCreateStepIndex(index)}
                            style={{
                              border: active ? '1px solid var(--brand-primary)' : '1px solid var(--border-light)',
                              background: active ? 'var(--brand-primary-light)' : 'var(--bg-card)',
                              color: active ? 'var(--brand-primary)' : 'var(--text-primary)',
                              borderRadius: '12px',
                              padding: '12px',
                              textAlign: 'left',
                              cursor: 'pointer',
                              display: 'flex',
                              flexDirection: 'column',
                              gap: '4px',
                            }}
                          >
                            <span style={{ fontSize: '12px', color: completed ? 'var(--brand-primary)' : 'var(--text-tertiary)' }}>
                              {completed
                                ? page('settings.integrations.modal.create.step.done')
                                : page('settings.integrations.modal.create.step.index', { index: index + 1 })}
                            </span>
                            <span style={{ fontSize: '14px', fontWeight: 600 }}>
                              {resolvePluginConfigSectionTitle(section, t)}
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                ) : null}

                {hasHiddenAdvancedWizardSections ? (
                  <div className="integration-status__detail" style={{ marginBottom: '12px' }}>
                    {hasConfiguredHiddenAdvancedSections
                      ? page('settings.integrations.modal.create.step.advancedConfigured')
                      : page('settings.integrations.modal.create.step.optionalHint', {
                        count: advancedWizardSections.length,
                      })}
                  </div>
                ) : null}

                {(!wizardMode || activeWizardStepIndex === 0) ? (
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
                      placeholder={instanceFormMode === 'create'
                        ? createDisplayNamePlaceholder
                        : page('settings.integrations.modal.instance.displayNamePlaceholder')}
                    />
                    {createDraft.fieldErrors.display_name ? <div className="form-help">{resolvePluginMaybeKey(createDraft.fieldErrors.display_name, t)}</div> : null}
                  </div>
                ) : null}

                {renderedSections.map((section) => (
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
                    {renderConfigPreviewPanel(section.id)}
                  </div>
                ))}
                <div className="member-modal__actions">
                  <button className="btn btn--outline btn--sm" type="button" onClick={closeCreateModal} disabled={submitting}>
                    {page('settings.integrations.action.cancel')}
                  </button>
                  {hasHiddenAdvancedWizardSections && isLastWizardStep ? (
                    <button
                      className="btn btn--outline btn--sm"
                      type="button"
                      onClick={revealAdvancedWizardSections}
                      disabled={submitting}
                    >
                      {page('settings.integrations.modal.create.step.showAdvanced')}
                    </button>
                  ) : null}
                  {wizardMode && activeWizardStepIndex > 0 ? (
                    <button
                      className="btn btn--outline btn--sm"
                      type="button"
                      onClick={() => setCreateStepIndex((current) => Math.max(current - 1, 0))}
                      disabled={submitting}
                    >
                      {page('settings.integrations.modal.create.step.previous')}
                    </button>
                  ) : null}
                  {wizardMode && !isLastWizardStep ? (
                    <button
                      className="btn btn--primary btn--sm"
                      type="button"
                      onClick={goToNextWizardStep}
                      disabled={submitting}
                    >
                      {page('settings.integrations.modal.create.step.next')}
                    </button>
                  ) : (
                    <button
                      className="btn btn--primary btn--sm"
                      type="submit"
                      disabled={submitting}
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
                  )}
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
