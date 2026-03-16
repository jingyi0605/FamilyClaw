import { useEffect, useMemo, useState, type FormEvent } from 'react';
import type {
  PluginConfigUpdatePayload,
  PluginConfigView,
  PluginManifestConfigField,
  PluginManifestConfigSpec,
} from '../../lib/types';
import { ToggleSwitch } from '../base';

type DynamicPluginConfigDraft = {
  payload: PluginConfigUpdatePayload;
  hasErrors: boolean;
};

type Props = {
  configSpec: PluginManifestConfigSpec;
  view: PluginConfigView;
  onSubmit?: (payload: PluginConfigUpdatePayload) => Promise<void> | void;
  onDraftChange?: (draft: DynamicPluginConfigDraft) => void;
  showActions?: boolean;
  saving?: boolean;
  formError?: string;
  submitText?: string;
};

function createInitialDraft(configSpec: PluginManifestConfigSpec, view: PluginConfigView) {
  const draftValues: Record<string, unknown> = {};
  const jsonTexts: Record<string, string> = {};

  for (const field of configSpec.config_schema.fields) {
    if (field.type === 'secret') {
      continue;
    }
    const value = view.values[field.key] ?? field.default ?? defaultValueByType(field);
    draftValues[field.key] = value;
    if (field.type === 'json') {
      jsonTexts[field.key] = value === '' ? '' : JSON.stringify(value ?? {}, null, 2);
    }
  }

  return {
    draftValues,
    secretInputs: {} as Record<string, string>,
    clearSecretFields: [] as string[],
    jsonTexts,
    jsonErrors: {} as Record<string, string>,
  };
}

function updateJsonDraft(
  current: ReturnType<typeof createInitialDraft>,
  field: PluginManifestConfigField,
  nextText: string,
) {
  const nextJsonTexts = {
    ...current.jsonTexts,
    [field.key]: nextText,
  };
  const nextDraftValues = { ...current.draftValues };
  const nextJsonErrors = { ...current.jsonErrors };

  if (!nextText.trim()) {
    nextDraftValues[field.key] = field.nullable ? null : {};
    delete nextJsonErrors[field.key];
    return {
      ...current,
      draftValues: nextDraftValues,
      jsonTexts: nextJsonTexts,
      jsonErrors: nextJsonErrors,
    };
  }

  try {
    nextDraftValues[field.key] = JSON.parse(nextText);
    delete nextJsonErrors[field.key];
  } catch {
    nextJsonErrors[field.key] = 'JSON 格式不合法';
  }

  return {
    ...current,
    draftValues: nextDraftValues,
    jsonTexts: nextJsonTexts,
    jsonErrors: nextJsonErrors,
  };
}

function defaultValueByType(field: PluginManifestConfigField): unknown {
  switch (field.type) {
    case 'boolean':
      return false;
    case 'multi_enum':
      return [];
    case 'json':
      return {};
    default:
      return '';
  }
}

function buildSubmissionPayload(
  configSpec: PluginManifestConfigSpec,
  view: PluginConfigView,
  draftValues: Record<string, unknown>,
  secretInputs: Record<string, string>,
  clearSecretFields: string[],
): PluginConfigUpdatePayload {
  const values: Record<string, unknown> = {};

  for (const field of configSpec.config_schema.fields) {
    if (field.type === 'secret') {
      const secretValue = secretInputs[field.key];
      if (!clearSecretFields.includes(field.key) && secretValue !== undefined && secretValue !== '') {
        values[field.key] = secretValue;
      }
      continue;
    }

    const value = draftValues[field.key];
    if (field.type === 'integer' || field.type === 'number') {
      if (value === '' || value === undefined) {
        values[field.key] = field.nullable ? null : '';
      } else {
        values[field.key] = Number(value);
      }
      continue;
    }

    if (field.type === 'boolean') {
      values[field.key] = Boolean(value);
      continue;
    }

    if (field.type === 'multi_enum') {
      values[field.key] = Array.isArray(value) ? value : [];
      continue;
    }

    if (field.type === 'json') {
      values[field.key] = value ?? (field.nullable ? null : {});
      continue;
    }

    values[field.key] = value ?? '';
  }

  return {
    scope_type: view.scope_type,
    scope_key: view.scope_key,
    values,
    clear_secret_fields: clearSecretFields,
  };
}

function isFieldVisible(
  fieldKey: string,
  configSpec: PluginManifestConfigSpec,
  draftValues: Record<string, unknown>,
  secretInputs: Record<string, string>,
  clearSecretFields: string[],
  view: PluginConfigView,
) {
  const widget = configSpec.ui_schema.widgets?.[fieldKey];
  const rules = widget?.visible_when ?? [];
  if (rules.length === 0) {
    return true;
  }

  return rules.every(rule => {
    const referencedField = configSpec.config_schema.fields.find(item => item.key === rule.field);
    if (!referencedField) {
      return true;
    }

    let currentValue: unknown;
    if (referencedField.type === 'secret') {
      currentValue = clearSecretFields.includes(referencedField.key)
        ? false
        : (secretInputs[referencedField.key] || view.secret_fields[referencedField.key]?.has_value || false);
    } else {
      currentValue = draftValues[referencedField.key];
    }

    switch (rule.operator) {
      case 'equals':
        return currentValue === rule.value;
      case 'not_equals':
        return currentValue !== rule.value;
      case 'in':
        return Array.isArray(rule.value) && rule.value.includes(currentValue);
      case 'truthy':
        return Boolean(currentValue);
      default:
        return true;
    }
  });
}

export function DynamicPluginConfigForm({
  configSpec,
  view,
  onSubmit,
  onDraftChange,
  showActions = true,
  saving = false,
  formError = '',
  submitText,
}: Props) {
  const [draft, setDraft] = useState(() => createInitialDraft(configSpec, view));

  useEffect(() => {
    setDraft(createInitialDraft(configSpec, view));
  }, [configSpec, view]);

  const payload = useMemo(
    () => buildSubmissionPayload(configSpec, view, draft.draftValues, draft.secretInputs, draft.clearSecretFields),
    [configSpec, draft.clearSecretFields, draft.draftValues, draft.secretInputs, view],
  );

  const hasErrors = useMemo(() => Object.values(draft.jsonErrors).some(Boolean), [draft.jsonErrors]);

  useEffect(() => {
    onDraftChange?.({ payload, hasErrors });
  }, [hasErrors, onDraftChange, payload]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (hasErrors || !onSubmit) {
      return;
    }
    await onSubmit(payload);
  }

  function updateDraftValue(field: PluginManifestConfigField, value: unknown) {
    setDraft(current => ({
      ...current,
      draftValues: {
        ...current.draftValues,
        [field.key]: value,
      },
    }));
  }

  const content = (
    <div className="plugin-config-form">
      {configSpec.ui_schema.sections.map(section => (
        <div key={section.id} className="plugin-config-section">
          <div className="plugin-config-section__header">
            <h4>{section.title}</h4>
            {section.description && <p>{section.description}</p>}
          </div>
          <div className="plugin-config-section__fields">
            {section.fields.map(fieldKey => {
              const field = configSpec.config_schema.fields.find(item => item.key === fieldKey);
              if (!field) {
                return null;
              }
              if (!isFieldVisible(field.key, configSpec, draft.draftValues, draft.secretInputs, draft.clearSecretFields, view)) {
                return null;
              }

              const widget = configSpec.ui_schema.widgets?.[field.key];
              const error = draft.jsonErrors[field.key] ?? view.field_errors[field.key];

              if (field.type === 'boolean' || widget?.widget === 'switch') {
                return (
                  <div key={field.key} className="plugin-config-field plugin-config-field--switch">
                    <ToggleSwitch
                      checked={Boolean(draft.draftValues[field.key])}
                      label={field.label}
                      description={widget?.help_text ?? field.description ?? undefined}
                      onChange={checked => updateDraftValue(field, checked)}
                    />
                    {error && <div className="form-error">{error}</div>}
                  </div>
                );
              }

              if (field.type === 'secret') {
                const secretStatus = view.secret_fields[field.key];
                const clearChecked = draft.clearSecretFields.includes(field.key);
                return (
                  <div key={field.key} className="plugin-config-field">
                    <label className="plugin-config-field__label">
                      {field.label}
                      {field.required && <span className="required-mark">*</span>}
                    </label>
                    <input
                      className="form-input"
                      type="password"
                      value={draft.secretInputs[field.key] ?? ''}
                      placeholder={
                        secretStatus?.has_value
                          ? (widget?.placeholder ?? '已保存旧值，留空表示继续保留')
                          : (widget?.placeholder ?? '')
                      }
                      onChange={event => {
                        const nextValue = event.target.value;
                        setDraft(current => ({
                          ...current,
                          secretInputs: {
                            ...current.secretInputs,
                            [field.key]: nextValue,
                          },
                          clearSecretFields: current.clearSecretFields.filter(item => item !== field.key),
                        }));
                      }}
                    />
                    {secretStatus?.has_value && (
                      <label className="plugin-config-secret-clear">
                        <input
                          type="checkbox"
                          checked={clearChecked}
                          onChange={event => {
                            const checked = event.target.checked;
                            setDraft(current => ({
                              ...current,
                              secretInputs: {
                                ...current.secretInputs,
                                [field.key]: '',
                              },
                              clearSecretFields: checked
                                ? [...current.clearSecretFields.filter(item => item !== field.key), field.key]
                                : current.clearSecretFields.filter(item => item !== field.key),
                            }));
                          }}
                        />
                        <span>清空当前已保存的值</span>
                      </label>
                    )}
                    {widget?.help_text && <div className="form-help">{widget.help_text}</div>}
                    {secretStatus?.has_value && !clearChecked && (
                      <div className="plugin-config-secret-status">当前已保存旧值，留空就继续保留。</div>
                    )}
                    {error && <div className="form-error">{error}</div>}
                  </div>
                );
              }

              if (field.type === 'enum' || widget?.widget === 'select') {
                return (
                  <div key={field.key} className="plugin-config-field">
                    <label className="plugin-config-field__label">
                      {field.label}
                      {field.required && <span className="required-mark">*</span>}
                    </label>
                    <select
                      className="form-select"
                      value={String(draft.draftValues[field.key] ?? '')}
                      onChange={event => updateDraftValue(field, event.target.value)}
                    >
                      <option value="">请选择</option>
                      {(field.enum_options ?? []).map(option => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                    {widget?.help_text && <div className="form-help">{widget.help_text}</div>}
                    {error && <div className="form-error">{error}</div>}
                  </div>
                );
              }

              if (field.type === 'multi_enum' || widget?.widget === 'multi_select') {
                const currentValues = Array.isArray(draft.draftValues[field.key]) ? draft.draftValues[field.key] as string[] : [];
                return (
                  <div key={field.key} className="plugin-config-field">
                    <label className="plugin-config-field__label">
                      {field.label}
                      {field.required && <span className="required-mark">*</span>}
                    </label>
                    <div className="plugin-config-multi-select">
                      {(field.enum_options ?? []).map(option => {
                        const checked = currentValues.includes(option.value);
                        return (
                          <label key={option.value} className="plugin-config-multi-select__item">
                            <input
                              type="checkbox"
                              checked={checked}
                              onChange={() => {
                                const nextValues = checked
                                  ? currentValues.filter(item => item !== option.value)
                                  : [...currentValues, option.value];
                                updateDraftValue(field, nextValues);
                              }}
                            />
                            <span>{option.label}</span>
                          </label>
                        );
                      })}
                    </div>
                    {widget?.help_text && <div className="form-help">{widget.help_text}</div>}
                    {error && <div className="form-error">{error}</div>}
                  </div>
                );
              }

              if (field.type === 'json' || widget?.widget === 'json_editor') {
                return (
                  <div key={field.key} className="plugin-config-field">
                    <label className="plugin-config-field__label">
                      {field.label}
                      {field.required && <span className="required-mark">*</span>}
                    </label>
                    <textarea
                      className="form-input setup-textarea plugin-config-json-editor"
                      rows={8}
                      value={draft.jsonTexts[field.key] ?? ''}
                      placeholder={widget?.placeholder ?? '{\n  \n}'}
                      onChange={event => {
                        setDraft(current => updateJsonDraft(current, field, event.target.value));
                      }}
                    />
                    {widget?.help_text && <div className="form-help">{widget.help_text}</div>}
                    {error && <div className="form-error">{error}</div>}
                  </div>
                );
              }

              const inputType = field.type === 'integer' || field.type === 'number' ? 'number' : 'text';
              const widgetType = widget?.widget === 'textarea' || field.type === 'text' ? 'textarea' : 'input';

              return (
                <div key={field.key} className="plugin-config-field">
                  <label className="plugin-config-field__label">
                    {field.label}
                    {field.required && <span className="required-mark">*</span>}
                  </label>
                  {widgetType === 'textarea' ? (
                    <textarea
                      className="form-input setup-textarea"
                      rows={4}
                      value={String(draft.draftValues[field.key] ?? '')}
                      placeholder={widget?.placeholder ?? ''}
                      onChange={event => updateDraftValue(field, event.target.value)}
                    />
                  ) : (
                    <input
                      className="form-input"
                      type={inputType}
                      value={String(draft.draftValues[field.key] ?? '')}
                      placeholder={widget?.placeholder ?? ''}
                      onChange={event => updateDraftValue(field, event.target.value)}
                    />
                  )}
                  {(widget?.help_text ?? field.description) && (
                    <div className="form-help">{widget?.help_text ?? field.description}</div>
                  )}
                  {error && <div className="form-error">{error}</div>}
                </div>
              );
            })}
          </div>
        </div>
      ))}

      {formError && <div className="form-error">{formError}</div>}
      {showActions && (
        <div className="plugin-config-form__actions">
          <button className="btn btn--primary" type="submit" disabled={saving || hasErrors}>
            {saving ? '保存中...' : (submitText ?? configSpec.ui_schema.submit_text ?? '保存配置')}
          </button>
        </div>
      )}
    </div>
  );

  if (!showActions) {
    return content;
  }

  return (
    <form onSubmit={handleSubmit}>
      {content}
    </form>
  );
}
