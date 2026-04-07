import type {
  PluginConfigEnumOption,
  PluginManifestConfigField,
  PluginManifestConfigSpec,
  PluginManifestFieldUiSchema,
  PluginManifestUiSection,
} from './settingsTypes';

type Translate = (key: string, params?: Record<string, string | number>) => string;

export function resolvePluginMaybeKey(value: string | null | undefined, translate: Translate): string {
  const normalized = typeof value === 'string' ? value.trim() : '';
  if (!normalized) {
    return '';
  }
  const translated = translate(normalized);
  return translated !== normalized ? translated : normalized;
}

function resolvePluginTranslatedKey(key: string | null | undefined, translate: Translate): string {
  const normalized = typeof key === 'string' ? key.trim() : '';
  if (!normalized) {
    return '';
  }
  const translated = translate(normalized);
  return translated !== normalized ? translated : '';
}

function resolvePluginText(
  text: string | null | undefined,
  key: string | null | undefined,
  translate: Translate,
): string {
  const translated = resolvePluginTranslatedKey(key, translate);
  if (translated) {
    return translated;
  }
  return resolvePluginMaybeKey(text, translate);
}

export function resolvePluginTextValue(
  text: string | null | undefined,
  key: string | null | undefined,
  translate: Translate,
): string {
  return resolvePluginText(text, key, translate);
}

export function resolvePluginConfigSpecTitle(configSpec: PluginManifestConfigSpec, translate: Translate): string {
  return resolvePluginText(configSpec.title, configSpec.title_key, translate);
}

export function resolvePluginConfigSpecDescription(configSpec: PluginManifestConfigSpec, translate: Translate): string {
  return resolvePluginText(configSpec.description, configSpec.description_key, translate);
}

export function resolvePluginConfigSectionTitle(section: PluginManifestUiSection, translate: Translate): string {
  return resolvePluginText(section.title, section.title_key, translate);
}

export function resolvePluginConfigSectionDescription(section: PluginManifestUiSection, translate: Translate): string {
  return resolvePluginText(section.description, section.description_key, translate);
}

export function resolvePluginConfigSubmitText(configSpec: PluginManifestConfigSpec, translate: Translate): string {
  return resolvePluginText(configSpec.ui_schema.submit_text, configSpec.ui_schema.submit_text_key, translate);
}

export function resolvePluginFieldLabel(field: PluginManifestConfigField, translate: Translate): string {
  return resolvePluginText(field.label, field.label_key, translate);
}

export function resolvePluginFieldDescription(field: PluginManifestConfigField, translate: Translate): string {
  return resolvePluginText(field.description, field.description_key, translate);
}

export function resolvePluginOptionLabel(option: PluginConfigEnumOption, translate: Translate): string {
  return resolvePluginText(option.label, option.label_key, translate);
}

export function resolvePluginWidgetPlaceholder(widget: PluginManifestFieldUiSchema | undefined, translate: Translate): string {
  return resolvePluginText(widget?.placeholder, widget?.placeholder_key, translate);
}

export function resolvePluginWidgetHelpText(
  widget: PluginManifestFieldUiSchema | undefined,
  field: PluginManifestConfigField,
  translate: Translate,
): string {
  const text = resolvePluginText(widget?.help_text, widget?.help_text_key, translate);
  if (text) {
    return text;
  }
  return resolvePluginFieldDescription(field, translate);
}

export function resolvePluginWidgetHelpToggleLabel(
  widget: PluginManifestFieldUiSchema | undefined,
  translate: Translate,
): string {
  return resolvePluginText(widget?.help_text_toggle_label, widget?.help_text_toggle_label_key, translate);
}
