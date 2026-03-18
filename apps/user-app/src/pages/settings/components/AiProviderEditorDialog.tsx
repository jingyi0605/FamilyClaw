import { type FormEvent } from 'react';
import {
  assignProviderFormValue,
  buildProviderFormState,
  readProviderFormValue,
} from '../../setup/setupAiConfig';
import type { AiProviderAdapter } from '../settingsTypes';
import { SettingsDialog } from './SettingsSharedBlocks';
import {
  getLocalizedAdapterMeta,
  getLocalizedCapabilityLabel,
  getLocalizedCapabilityOptions,
  getLocalizedField,
  getLocalizedWorkflowLabel,
} from './aiProviderCatalog';
import { getAiProviderLogo } from './AiProviderLogos';

type ProviderFormState = ReturnType<typeof buildProviderFormState>;

function readFieldValue(form: ProviderFormState, fieldKey: string) {
  return readProviderFormValue(form, fieldKey);
}

function assignFieldValue(form: ProviderFormState, fieldKey: string, value: string): ProviderFormState {
  return assignProviderFormValue(form, fieldKey, value);
}

export function AiProviderEditorDialog(props: {
  householdId: string;
  locale: string | undefined;
  open: boolean;
  adapters: AiProviderAdapter[];
  resolvedAdapter: AiProviderAdapter | null;
  form: ProviderFormState;
  assignedCapabilities: string[];
  editingProviderId: string | null;
  saving: boolean;
  status: string;
  copy: {
    addTitle: string;
    editTitle: string;
    formDescription: string;
    providerTypeLabel: string;
    selectPlaceholder: string;
    assignedCapabilityLabel: string;
    assignedCapabilityHint: string;
    enableAfterSave: string;
    saveProvider: string;
    submitAddProvider: string;
    llmWorkflow: string;
    back: string;
    cancel: string;
    saving: string;
  };
  onClose: () => void;
  onBack?: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onAdapterChange: (adapterCode: string) => void;
  onFormChange: (form: ProviderFormState) => void;
  onAssignedCapabilitiesChange: (capabilities: string[]) => void;
}) {
  const {
    householdId,
    locale,
    open,
    adapters,
    resolvedAdapter,
    form,
    assignedCapabilities,
    editingProviderId,
    saving,
    status,
    copy,
    onClose,
    onBack,
    onSubmit,
    onAdapterChange,
    onFormChange,
    onAssignedCapabilitiesChange,
  } = props;

  if (!open) {
    return null;
  }

  const currentAdapter = resolvedAdapter ?? adapters.find(item => item.adapter_code === form.adapterCode) ?? null;
  const selectAdapters = currentAdapter && !adapters.some(item => item.adapter_code === currentAdapter.adapter_code)
    ? [currentAdapter, ...adapters]
    : adapters;
  const localizedCapabilityOptions = getLocalizedCapabilityOptions(locale);
  const adapterMeta = currentAdapter ? getLocalizedAdapterMeta(currentAdapter, locale) : null;
  const Logo = currentAdapter ? getAiProviderLogo(currentAdapter.adapter_code) : null;

  // 编辑态直接显示编辑标题，新建态把供应商名字带进标题里。
  const dialogTitle = editingProviderId
    ? copy.editTitle
    : (currentAdapter && adapterMeta ? `${copy.addTitle} - ${adapterMeta.label}` : copy.addTitle);

  return (
    <SettingsDialog
      title={dialogTitle}
      description={copy.formDescription}
      className="ai-provider-editor-modal"
      formClassName="ai-provider-editor-form"
      closeDisabled={saving}
      onClose={onClose}
      onSubmit={onSubmit}
    actions={(
        <>
          {!editingProviderId && onBack ? (
            <button
              className="btn btn--outline btn--sm"
              type="button"
              onClick={onBack}
              disabled={saving}
            >
              {copy.back}
            </button>
          ) : null}
          <button className="btn btn--outline btn--sm" type="button" onClick={onClose} disabled={saving}>
            {copy.cancel}
          </button>
          <button
            className="btn btn--primary btn--sm"
            type="submit"
            disabled={
              saving
              || !currentAdapter
              || !form.displayName.trim()
              || !form.providerCode.trim()
              || !form.modelName.trim()
              || assignedCapabilities.length === 0
            }
          >
            {saving ? copy.saving : editingProviderId ? copy.saveProvider : copy.submitAddProvider}
          </button>
        </>
      )}
    >
      {currentAdapter && adapterMeta ? (
        <>
          {/* 供应商头部摘要 */}
          <div className="ai-provider-editor-header">
            {Logo ? (
              <div className="ai-provider-editor-header__logo">
                <Logo width={20} height={20} />
              </div>
            ) : null}
            <div className="ai-provider-editor-header__info">
              <h4>{adapterMeta.label}</h4>
              <p>{adapterMeta.description}</p>
            </div>
            <div className="ai-provider-editor-header__tags">
              {(currentAdapter.default_supported_capabilities ?? []).slice(0, 3).map(capability => (
                <span key={capability} className="ai-pill ai-pill--primary">
                  {getLocalizedCapabilityLabel(capability, locale)}
                </span>
              ))}
            </div>
          </div>

          <div className="ai-provider-editor-body">
            {/* 基础配置 */}
            <div className="ai-editor-section">
              <div className="ai-editor-row">
                <div className="form-group form-group--compact">
                  <label htmlFor={`provider-adapter-${householdId}`}>{copy.providerTypeLabel}</label>
                  <select
                    id={`provider-adapter-${householdId}`}
                    className="form-select form-select--compact"
                    value={form.adapterCode}
                    onChange={event => onAdapterChange(event.target.value)}
                    disabled={Boolean(editingProviderId)}
                  >
                    <option value="">{copy.selectPlaceholder}</option>
                    {selectAdapters.map(adapter => {
                      const meta = getLocalizedAdapterMeta(adapter, locale);
                      return (
                        <option key={adapter.adapter_code} value={adapter.adapter_code}>
                          {meta.label}
                        </option>
                      );
                    })}
                  </select>
                </div>
                <div className="form-group form-group--compact form-group--inline">
                  <label>{copy.llmWorkflow}</label>
                  <span className="ai-editor-workflow-badge">
                    {getLocalizedWorkflowLabel(currentAdapter.llm_workflow, locale)}
                  </span>
                </div>
              </div>
            </div>

            {/* 动态表单配置 */}
            <div className="ai-editor-section">
              <div className="ai-editor-grid">
                {currentAdapter.field_schema.map(field => {
                  const localizedField = getLocalizedField(field, locale);
                  const fieldValue = readFieldValue(form, field.key);
                  const inputId = `${householdId}-${field.key}`;

                  if (localizedField.field_type === 'boolean') {
                    return (
                      <div key={field.key} className="form-group form-group--compact form-group--checkbox">
                        <label className="ai-editor-checkbox" htmlFor={inputId}>
                          <input
                            id={inputId}
                            type="checkbox"
                            checked={fieldValue === 'true'}
                            onChange={event => onFormChange(assignFieldValue(form, field.key, event.target.checked ? 'true' : 'false'))}
                          />
                          <span className="ai-editor-checkbox__label">{localizedField.label}</span>
                        </label>
                        {localizedField.help_text ? <p className="ai-editor-hint">{localizedField.help_text}</p> : null}
                      </div>
                    );
                  }

                  return (
                    <div key={field.key} className="form-group form-group--compact">
                      <label htmlFor={inputId}>{localizedField.label}</label>
                      {localizedField.field_type === 'select' ? (
                        <select
                          id={inputId}
                          className="form-select form-select--compact"
                          value={fieldValue}
                          onChange={event => onFormChange(assignFieldValue(form, field.key, event.target.value))}
                        >
                          <option value="">{copy.selectPlaceholder}</option>
                          {localizedField.options.map(option => (
                            <option key={option.value} value={option.value}>
                              {option.label}
                            </option>
                          ))}
                        </select>
                      ) : (
                        <input
                          id={inputId}
                          className="form-input form-input--compact"
                          type={localizedField.field_type === 'number' ? 'number' : 'text'}
                          value={fieldValue}
                          onChange={event => onFormChange(assignFieldValue(form, field.key, event.target.value))}
                          placeholder={localizedField.placeholder ?? undefined}
                          disabled={Boolean(editingProviderId && field.key === 'provider_code')}
                        />
                      )}
                      {localizedField.help_text ? <p className="ai-editor-hint">{localizedField.help_text}</p> : null}
                    </div>
                  );
                })}
              </div>
            </div>

            {/* 能力配置 */}
            <div className="ai-editor-section ai-editor-section--capabilities">
              <div className="ai-editor-capability-panel">
                <label className="ai-editor-capabilities__label">{copy.assignedCapabilityLabel}</label>
                <p className="ai-editor-capabilities__hint">{copy.assignedCapabilityHint}</p>
                <div className="ai-editor-caps-grid">
                  {localizedCapabilityOptions.map(item => (
                    <label key={`assigned-${item.value}`} className="ai-editor-cap-chip">
                      <input
                        type="checkbox"
                        checked={assignedCapabilities.includes(item.value)}
                        onChange={() => {
                          const currentlyAssigned = assignedCapabilities.includes(item.value);
                          const nextAssignedCapabilities = currentlyAssigned
                            ? assignedCapabilities.filter(capability => capability !== item.value)
                            : [...assignedCapabilities, item.value];

                          onAssignedCapabilitiesChange(nextAssignedCapabilities);
                        }}
                      />
                      <span>{item.label}</span>
                    </label>
                  ))}
                </div>
              </div>
              <div className="ai-editor-enable ai-editor-enable-card">
                <label className="ai-editor-switch">
                  <input
                    type="checkbox"
                    checked={form.enabled}
                    onChange={event => onFormChange({ ...form, enabled: event.target.checked })}
                  />
                  <span className="ai-editor-switch__label">{copy.enableAfterSave}</span>
                </label>
              </div>
            </div>
          </div>
        </>
      ) : null}

      {status ? <div className="setup-form-status">{status}</div> : null}
    </SettingsDialog>
  );
}
