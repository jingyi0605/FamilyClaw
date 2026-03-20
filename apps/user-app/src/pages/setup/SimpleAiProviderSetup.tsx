import { useEffect, useMemo, useState, type FormEvent } from 'react';
import { useI18n } from '../../runtime';
import { Card } from './base';
import {
  assignProviderFormValue,
  buildCreateProviderPayload,
  buildProviderFormState,
  buildRoutePayload,
  buildUpdateProviderPayload,
  getProviderAdapterCode,
  readProviderFormValue,
  SETUP_ROUTE_CAPABILITIES,
  toProviderFormState,
} from './setupAiConfig';
import { setupApi } from './setupApi';
import type { AiCapabilityRoute, AiProviderAdapter, AiProviderField, AiProviderProfile } from './setupTypes';
import { AiProviderSelectDialog } from '../settings/components/AiProviderSelectDialog';
import { AiProviderBrandMark } from '../settings/components/AiProviderBrandMark';
import {
  getLocalizedAdapterMeta,
  getLocalizedField,
  getProviderFieldAction,
  getProviderFieldSections,
  isProviderFieldHidden,
} from '../settings/components/aiProviderCatalog';
import { useAiProviderModelDiscovery } from '../settings/components/useAiProviderModelDiscovery';

function renderDiscoveryMessage(
  adapter: AiProviderAdapter,
  modelDiscovery: ReturnType<typeof useAiProviderModelDiscovery>,
) {
  if (modelDiscovery.error) {
    return modelDiscovery.error;
  }
  if (modelDiscovery.status.startsWith('found:')) {
    const count = modelDiscovery.status.slice('found:'.length);
    return adapter.model_discovery.discovered_text_template?.replace('{count}', count) || `已发现 ${count} 个模型。`;
  }
  if (modelDiscovery.status === 'empty') {
    return adapter.model_discovery.empty_state_text || '没有发现可用模型。';
  }
  return adapter.model_discovery.discovery_hint_text || '';
}

function renderSetupField(props: {
  householdId: string;
  locale: string | undefined;
  selectPlaceholder: string;
  adapter: AiProviderAdapter;
  field: AiProviderField;
  form: ReturnType<typeof buildProviderFormState>;
  onFormChange: (form: ReturnType<typeof buildProviderFormState>) => void;
  modelDiscovery: ReturnType<typeof useAiProviderModelDiscovery>;
}) {
  const { householdId, locale, selectPlaceholder, adapter, field, form, onFormChange, modelDiscovery } = props;
  const fieldUi = adapter.config_ui.field_ui[field.key];
  const localizedField = getLocalizedField(field, locale, fieldUi);
  const inputId = `${householdId}-${field.key}`;
  const fieldValue = readProviderFormValue(form, field.key);
  const action = getProviderFieldAction(adapter, field.key);
  const isDiscoveryField = Boolean(
    action
    && action.kind === 'model_discovery'
    && adapter.model_discovery.enabled
    && adapter.model_discovery.target_field === field.key,
  );
  const discoveryMessage = isDiscoveryField ? renderDiscoveryMessage(adapter, modelDiscovery) : '';
  const datalistId = `${inputId}-options`;

  return (
    <div key={field.key} className="form-group">
      <div className={isDiscoveryField ? 'ai-provider-model-field__label-row' : undefined}>
        <label htmlFor={inputId}>{localizedField.label}</label>
        {isDiscoveryField && action ? (
          <button
            className="btn btn--outline btn--sm"
            type="button"
            onClick={modelDiscovery.refreshModels}
            disabled={modelDiscovery.discovering}
            title={action.description ?? undefined}
          >
            {modelDiscovery.discovering
              ? (adapter.model_discovery.discovering_text || action.label)
              : action.label}
          </button>
        ) : null}
      </div>
      {field.field_type === 'select' ? (
        <select
          id={inputId}
          className="form-select"
          value={fieldValue}
          onChange={event => onFormChange(assignProviderFormValue(form, field.key, event.target.value))}
        >
          <option value="">{selectPlaceholder}</option>
          {localizedField.options.map(option => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      ) : (
        <>
          <input
            id={inputId}
            className="form-input"
            type={field.field_type === 'secret' ? 'password' : field.field_type === 'number' ? 'number' : 'text'}
            list={isDiscoveryField && modelDiscovery.models.length > 0 ? datalistId : undefined}
            value={fieldValue}
            onChange={event => onFormChange(assignProviderFormValue(form, field.key, event.target.value))}
            placeholder={localizedField.placeholder ?? undefined}
          />
          {isDiscoveryField && modelDiscovery.models.length > 0 ? (
            <datalist id={datalistId}>
              {modelDiscovery.models.map(model => <option key={model.id} value={model.id}>{model.label}</option>)}
            </datalist>
          ) : null}
        </>
      )}
      {localizedField.help_text ? <p className="ai-config-muted">{localizedField.help_text}</p> : null}
      {isDiscoveryField && modelDiscovery.supportsModelDiscovery && discoveryMessage ? (
        <p className={modelDiscovery.error ? 'ai-config-muted form-error' : 'ai-config-muted'}>{discoveryMessage}</p>
      ) : null}
    </div>
  );
}

export function SimpleAiProviderSetup(props: { householdId: string; onCompleted?: () => void }) {
  const { locale, t } = useI18n();
  const [adapters, setAdapters] = useState<AiProviderAdapter[]>([]);
  const [form, setForm] = useState(buildProviderFormState());
  const [editingProviderId, setEditingProviderId] = useState<string | null>(null);
  const [selectOpen, setSelectOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');

  const currentAdapter = useMemo(() => adapters.find(item => item.adapter_code === form.adapterCode) ?? null, [adapters, form.adapterCode]);
  const currentAdapterMeta = useMemo(
    () => (currentAdapter ? getLocalizedAdapterMeta(currentAdapter, locale) : null),
    [currentAdapter, locale],
  );
  const modelDiscovery = useAiProviderModelDiscovery({
    householdId: props.householdId,
    adapter: currentAdapter,
    form,
    onFormChange: setForm,
    discoverModels: setupApi.discoverAiProviderModels,
  });
  const sections = currentAdapter ? getProviderFieldSections(currentAdapter) : [];

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

  function handleSelectAdapter(adapterCode: string) {
    setForm(buildProviderFormState(adapters.find(item => item.adapter_code === adapterCode) ?? null));
    setSelectOpen(false);
  }

  if (loading) return <Card><p>{t('setup.providerSetup.loading')}</p></Card>;

  return (
    <Card className="ai-config-detail-card">
      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label htmlFor={`provider-adapter-trigger-${props.householdId}`}>{t('setup.providerSetup.platformLabel')}</label>
          <button
            id={`provider-adapter-trigger-${props.householdId}`}
            type="button"
            className="setup-provider-trigger"
            onClick={() => setSelectOpen(true)}
            disabled={Boolean(editingProviderId)}
            aria-haspopup="dialog"
            aria-expanded={selectOpen}
          >
            {currentAdapter && currentAdapterMeta ? (
              <>
                <span className="setup-provider-trigger__logo">
                  <AiProviderBrandMark adapter={currentAdapter} size={18} />
                </span>
                <span className="setup-provider-trigger__content">
                  <span className="setup-provider-trigger__title">{currentAdapterMeta.label}</span>
                  <span className="setup-provider-trigger__desc">{currentAdapterMeta.description}</span>
                </span>
              </>
            ) : (
              <span className="setup-provider-trigger__placeholder">
                {t('setup.providerSetup.selectPlaceholder')}
              </span>
            )}
            <span className="setup-provider-trigger__action">
              {editingProviderId ? t('setup.providerSetup.selectedState') : t('setup.providerSetup.changeAction')}
            </span>
          </button>
        </div>
        {currentAdapter ? (
          <>
            {sections.map(section => (
              <div key={section.key} className="setup-form-section">
                {section.title ? <h4 className="setup-form-section__title">{section.title}</h4> : null}
                {section.description ? <p className="setup-form-section__desc">{section.description}</p> : null}
                <div className="setup-form-grid">
                  {section.fields_meta
                    .filter(field => field.key !== 'provider_code')
                    .filter(field => !isProviderFieldHidden(currentAdapter, field.key, fieldKey => readProviderFormValue(form, fieldKey)))
                    .map(field => renderSetupField({
                      householdId: props.householdId,
                      locale,
                      selectPlaceholder: t('setup.providerSetup.selectPlaceholder'),
                      adapter: currentAdapter,
                      field,
                      form,
                      onFormChange: setForm,
                      modelDiscovery,
                    }))}
                </div>
              </div>
            ))}
            <div className="setup-inline-tip"><strong>{t('setup.providerSetup.tipTitle')}</strong><span>{t('setup.providerSetup.tipBody')}</span></div>
          </>
        ) : null}
        {error ? <div className="form-error">{error}</div> : null}
        {status ? <div className="setup-form-status">{status}</div> : null}
        <div className="setup-form-actions"><button className="btn btn--primary btn--large" type="submit" disabled={saving || !currentAdapter || !form.displayName.trim() || !form.modelName.trim()}>{saving ? t('setup.providerSetup.binding') : editingProviderId ? t('setup.providerSetup.saveAndUpdateAll') : t('setup.providerSetup.createAndApplyAll')}</button></div>
      </form>
      <AiProviderSelectDialog
        open={selectOpen}
        locale={locale}
        adapters={adapters}
        copy={{
          title: t('setup.providerSetup.dialogTitle'),
          description: t('setup.providerSetup.dialogDescription'),
          close: t('common.close'),
        }}
        onSelect={handleSelectAdapter}
        onClose={() => setSelectOpen(false)}
      />
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
