import { SettingsDialog } from './SettingsSharedBlocks';
import type { AiProviderAdapter, AiCapabilityRoute, AiProviderProfile, AiProviderField, PluginRegistryItem } from '../settingsTypes';
import { getProviderModelName } from '../../setup/setupAiConfig';
import {
  getLocalizedAdapterMeta,
  getLocalizedCapabilityLabel,
  getLocalizedField,
  getLocalizedWorkflowLabel,
  sortCapabilities,
} from './aiProviderCatalog';
import { getPageMessage } from '../../../runtime/h5-shell/i18n/pageMessageUtils';

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

function formatPluginUpdateState(state: string | null | undefined, locale: string | undefined) {
  switch (state) {
    case 'up_to_date':
      return getPageMessage(locale, 'settings.plugin.versionState.upToDate');
    case 'update_available':
      return getPageMessage(locale, 'settings.plugin.versionState.updateAvailable');
    case 'unknown':
      return getPageMessage(locale, 'settings.plugin.versionState.unknown');
    default:
      return state ?? '--';
  }
}

export function AiProviderDetailDialog(props: {
  open: boolean;
  provider: AiProviderProfile | null;
  adapter: AiProviderAdapter | null;
  plugin: PluginRegistryItem | null;
  routes: AiCapabilityRoute[];
  locale: string | undefined;
  deleting?: boolean;
  actionError?: string;
  copy: {
    enabled: string;
    disabled: string;
    pluginDisabled: string;
    pluginDisabledTitle: string;
    pluginDisabledFallback: string;
    modelNameEmpty: string;
    pluginLabel: string;
    pluginVersionLabel: string;
    pluginUpdateStateLabel: string;
    llmWorkflow: string;
    updatedAtLabel: string;
    summaryRouteTitle: string;
    summaryRouteEmpty: string;
    summaryConfigTitle: string;
    close: string;
    delete: string;
    deleting: string;
    edit: string;
  };
  onClose: () => void;
  onDelete: () => void;
  onEdit: () => void;
}) {
  const {
    open,
    provider,
    adapter,
    plugin,
    routes,
    locale,
    deleting = false,
    actionError = '',
    copy,
    onClose,
    onDelete,
    onEdit,
  } = props;

  if (!open || !provider) {
    return null;
  }

  const adapterMeta = adapter ? getLocalizedAdapterMeta(adapter, locale) : null;
  const routeCapabilities = routes
    .filter(item => item.enabled && item.primary_provider_profile_id === provider.id)
    .map(item => item.capability);
  const effectiveCapabilities = sortCapabilities(
    routeCapabilities.length > 0 ? routeCapabilities : provider.supported_capabilities,
  );
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
    <SettingsDialog
      title={provider.display_name}
      description={adapterMeta?.description ?? ''}
      closeDisabled={deleting}
      headerExtra={(
        <div className="ai-config-chip-list">
          <span className={`ai-pill ${provider.enabled ? 'ai-pill--success' : 'ai-pill--muted'}`}>
            {provider.enabled ? copy.enabled : copy.disabled}
          </span>
          {provider.plugin_enabled === false ? (
            <span className="ai-pill ai-pill--warning">
              {copy.pluginDisabled}
            </span>
          ) : null}
        </div>
      )}
      className="ai-provider-detail-modal"
      onClose={onClose}
      actions={(
        <>
          <button className="btn btn--outline btn--sm" type="button" onClick={onClose} disabled={deleting}>
            {copy.close}
          </button>
          <button className="btn btn--danger btn--sm" type="button" onClick={() => void onDelete()} disabled={deleting}>
            {deleting ? copy.deleting : copy.delete}
          </button>
          <button className="btn btn--primary btn--sm" type="button" onClick={onEdit} disabled={deleting}>
            {copy.edit}
          </button>
        </>
      )}
    >
      {actionError ? (
        <div className="settings-note settings-note--error">
          {actionError}
        </div>
      ) : null}

      {provider.plugin_enabled === false ? (
        <div className="settings-note settings-note--warning">
          <strong>{copy.pluginDisabledTitle}</strong>
          {' '}
          {provider.plugin_disabled_reason || copy.pluginDisabledFallback}
        </div>
      ) : null}

      <div className="ai-detail-modal__hero">
        <div className="ai-detail-modal__avatar">AI</div>
        <div className="ai-detail-modal__info">
          <p className="ai-detail-modal__provider">{adapterMeta?.label ?? provider.provider_code}</p>
          <p className="ai-detail-modal__model">{getProviderModelName(provider) ?? copy.modelNameEmpty}</p>
        </div>
      </div>

      <div className="ai-detail-modal__grid">
        <div className="ai-detail-modal__stat">
          <span>{copy.pluginLabel}</span>
          <strong>{adapter?.plugin_name ?? plugin?.name ?? '--'}</strong>
        </div>
        <div className="ai-detail-modal__stat">
          <span>{copy.pluginVersionLabel}</span>
          <strong>{plugin ? `v${plugin.installed_version ?? plugin.version}` : '--'}</strong>
        </div>
        <div className="ai-detail-modal__stat">
          <span>{copy.pluginUpdateStateLabel}</span>
          <strong>{formatPluginUpdateState(plugin?.update_state, locale)}</strong>
        </div>
        <div className="ai-detail-modal__stat">
          <span>{copy.llmWorkflow}</span>
          <strong>{adapter ? getLocalizedWorkflowLabel(adapter.llm_workflow, locale) : '--'}</strong>
        </div>
        <div className="ai-detail-modal__stat">
          <span>{copy.updatedAtLabel}</span>
          <strong>{provider.updated_at}</strong>
        </div>
      </div>

      <div className="ai-detail-modal__section">
        <h4>{copy.summaryRouteTitle}</h4>
        {effectiveCapabilities.length > 0 ? (
          <div className="ai-config-chip-list">
            {effectiveCapabilities.map(capability => (
              <span key={capability} className="ai-pill">
                {getLocalizedCapabilityLabel(capability, locale)}
              </span>
            ))}
          </div>
        ) : (
          <p className="ai-config-muted">{copy.summaryRouteEmpty}</p>
        )}
      </div>

      <div className="ai-detail-modal__section">
        <h4>{copy.summaryConfigTitle}</h4>
        <div className="ai-detail-modal__list">
          {summaryFields.map(item => (
            <div key={item.key} className="ai-detail-modal__list-item">
              <span>{item.label}</span>
              <strong>{item.value}</strong>
            </div>
          ))}
        </div>
      </div>
    </SettingsDialog>
  );
}
