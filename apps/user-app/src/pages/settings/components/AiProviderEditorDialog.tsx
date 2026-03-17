import { type FormEvent } from 'react';
import { Card } from '../../family/base';
import {
  assignProviderFormValue,
  buildProviderFormState,
  readProviderFormValue,
} from '../../setup/setupAiConfig';
import type { AiProviderAdapter } from '../settingsTypes';
import { SettingsDialog } from './SettingsSharedBlocks';
import {
  getLocalizedAdapterMeta,
  getLocalizedCapabilityOptions,
  getLocalizedField,
  getLocalizedModelTypeLabel,
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
  editingProviderId: string | null;
  saving: boolean;
  status: string;
  copy: {
    addTitle: string;
    editTitle: string;
    formDescription: string;
    providerTypeLabel: string;
    selectPlaceholder: string;
    capabilityCheckboxLabel: string;
    enableAfterSave: string;
    saveProvider: string;
    submitAddProvider: string;
    chooseProviderPlugin: string;
    chooseProviderPluginDesc: string;
    supportedModelTypes: string;
    llmWorkflow: string;
    cancel: string;
    saving: string;
  };
  onClose: () => void;
  onBack?: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onAdapterChange: (adapterCode: string) => void;
  onFormChange: (form: ProviderFormState) => void;
}) {
  const {
    householdId,
    locale,
    open,
    adapters,
    resolvedAdapter,
    form,
    editingProviderId,
    saving,
    status,
    copy,
    onClose,
    onBack,
    onSubmit,
    onAdapterChange,
    onFormChange,
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

  // 构建对话框标题：编辑模式显示"编辑xxx"，新建模式显示"添加模型"
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
              {locale?.startsWith('en') ? 'Back' : '返回'}
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
              || form.supportedCapabilities.length === 0
            }
          >
            {saving ? copy.saving : editingProviderId ? copy.saveProvider : copy.submitAddProvider}
          </button>
        </>
      )}
    >
      {currentAdapter && adapterMeta ? (
        <>
          {/* 供应商信息头部 */}
          <div className="ai-provider-editor-header">
            {Logo ? (
              <div className="ai-provider-editor-header__logo">
                <Logo width={32} height={32} />
              </div>
            ) : null}
            <div className="ai-provider-editor-header__info">
              <h4>{adapterMeta.label}</h4>
              <p>{adapterMeta.description}</p>
            </div>
          </div>

          <Card className="ai-config-detail-card ai-provider-editor-card">
            <div className="setup-form-grid">
              <div className="form-group">
                <label htmlFor={`provider-adapter-${householdId}`}>{copy.providerTypeLabel}</label>
                <select
                  id={`provider-adapter-${householdId}`}
                  className="form-select"
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

              <div className="form-group">
                <label>{copy.llmWorkflow}</label>
                <div className="form-help">{getLocalizedWorkflowLabel(currentAdapter.llm_workflow, locale)}</div>
              </div>

              <div className="form-group">
                <label>{copy.supportedModelTypes}</label>
                <div className="ai-config-chip-list">
                  {(currentAdapter.supported_model_types ?? []).map(type => (
                    <span key={type} className="ai-pill">
                      {getLocalizedModelTypeLabel(type, locale)}
                    </span>
                  ))}
                </div>
              </div>
            </div>

            <div className="setup-form-grid">
              {currentAdapter.field_schema.map(field => {
                const localizedField = getLocalizedField(field, locale);
                const fieldValue = readFieldValue(form, field.key);
                const inputId = `${householdId}-${field.key}`;

                if (localizedField.field_type === 'boolean') {
                  return (
                    <div key={field.key} className="form-group">
                      <label className="setup-choice" htmlFor={inputId}>
                        <input
                          id={inputId}
                          type="checkbox"
                          checked={fieldValue === 'true'}
                          onChange={event => onFormChange(assignFieldValue(form, field.key, event.target.checked ? 'true' : 'false'))}
                        />
                        <span>{localizedField.label}</span>
                      </label>
                      {localizedField.help_text ? <p className="ai-config-muted">{localizedField.help_text}</p> : null}
                    </div>
                  );
                }

                return (
                  <div key={field.key} className="form-group">
                    <label htmlFor={inputId}>{localizedField.label}</label>
                    {localizedField.field_type === 'select' ? (
                      <select
                        id={inputId}
                        className="form-select"
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
                        className="form-input"
                        type={localizedField.field_type === 'number' ? 'number' : 'text'}
                        value={fieldValue}
                        onChange={event => onFormChange(assignFieldValue(form, field.key, event.target.value))}
                        placeholder={localizedField.placeholder ?? undefined}
                        disabled={Boolean(editingProviderId && field.key === 'provider_code')}
                      />
                    )}
                    {localizedField.help_text ? <p className="ai-config-muted">{localizedField.help_text}</p> : null}
                  </div>
                );
              })}

              <div className="form-group">
                <label>{copy.capabilityCheckboxLabel}</label>
                <div className="setup-choice-group">
                  {localizedCapabilityOptions.map(item => (
                    <label key={item.value} className="setup-choice">
                      <input
                        type="checkbox"
                        checked={form.supportedCapabilities.includes(item.value)}
                        onChange={() => {
                          onFormChange({
                            ...form,
                            supportedCapabilities: form.supportedCapabilities.includes(item.value)
                              ? form.supportedCapabilities.filter(capability => capability !== item.value)
                              : [...form.supportedCapabilities, item.value],
                          });
                        }}
                      />
                      <span>{item.label}</span>
                    </label>
                  ))}
                </div>
              </div>

              <div className="form-group">
                <label className="setup-choice">
                  <input
                    type="checkbox"
                    checked={form.enabled}
                    onChange={event => onFormChange({ ...form, enabled: event.target.checked })}
                  />
                  <span>{copy.enableAfterSave}</span>
                </label>
              </div>
            </div>
          </Card>
        </>
      ) : null}

      {status ? <div className="setup-form-status">{status}</div> : null}
    </SettingsDialog>
  );
}
