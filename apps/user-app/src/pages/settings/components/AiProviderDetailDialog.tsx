import { SettingsDialog } from './SettingsSharedBlocks';
import type { AiProviderAdapter, AiCapabilityRoute, AiProviderProfile, AiProviderField } from '../settingsTypes';
import { getProviderAdapterCode, getProviderModelName } from '../../setup/setupAiConfig';
import {
  getLocalizedAdapterMeta,
  getLocalizedCapabilityLabel,
  getLocalizedField,
  getLocalizedModelTypeLabel,
  getLocalizedWorkflowLabel,
} from './aiProviderCatalog';

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

export function AiProviderDetailDialog(props: {
  open: boolean;
  provider: AiProviderProfile | null;
  adapter: AiProviderAdapter | null;
  routes: AiCapabilityRoute[];
  locale: string | undefined;
  copy: {
    enabled: string;
    disabled: string;
    modelNameEmpty: string;
    pluginLabel: string;
    llmWorkflow: string;
    updatedAtLabel: string;
    summarySupportTitle: string;
    summaryRouteTitle: string;
    summaryRouteEmpty: string;
    summaryConfigTitle: string;
    close: string;
    edit: string;
  };
  onClose: () => void;
  onEdit: () => void;
}) {
  const { open, provider, adapter, routes, locale, copy, onClose, onEdit } = props;

  if (!open || !provider) {
    return null;
  }

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
    <SettingsDialog
      title={provider.display_name}
      description={adapterMeta?.description ?? ''}
      headerExtra={(
        <span className={`ai-pill ${provider.enabled ? 'ai-pill--success' : 'ai-pill--muted'}`}>
          {provider.enabled ? copy.enabled : copy.disabled}
        </span>
      )}
      className="ai-provider-detail-modal"
      onClose={onClose}
      actions={(
        <>
          <button className="btn btn--outline btn--sm" type="button" onClick={onClose}>
            {copy.close}
          </button>
          <button className="btn btn--primary btn--sm" type="button" onClick={onEdit}>
            {copy.edit}
          </button>
        </>
      )}
    >
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
          <strong>{adapter?.plugin_name ?? '--'}</strong>
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

      <div className="ai-detail-modal__section">
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
