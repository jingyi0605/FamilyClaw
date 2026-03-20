import { getPageMessage } from '../../../runtime/h5-shell/i18n/pageMessageUtils';
import { AI_CAPABILITY_OPTIONS, getCapabilityLabel } from '../../setup/setupAiConfig';
import type {
  AiProviderAdapter,
  AiProviderConfigAction,
  AiProviderConfigSection,
  AiProviderConfigVisibilityRule,
  AiProviderField,
  AiProviderFieldOption,
} from '../settingsTypes';

const WORKFLOW_LABEL_MAP: Record<string, Parameters<typeof getPageMessage>[1]> = {
  openai_chat_completions: 'settings.ai.provider.workflow.openaiCompatible',
  anthropic_messages: 'settings.ai.provider.workflow.anthropic',
  gemini_generate_content: 'settings.ai.provider.workflow.gemini',
};

const CAPABILITY_ORDER = new Map<string, number>(AI_CAPABILITY_OPTIONS.map((item, index) => [item.value, index]));

export function getLocalizedCapabilityLabel(capability: string, locale: string | undefined) {
  return getCapabilityLabel(capability, locale);
}

export function getLocalizedWorkflowLabel(workflow: string, locale: string | undefined) {
  const key = WORKFLOW_LABEL_MAP[workflow];
  return key ? getPageMessage(locale, key) : workflow;
}

function pickLocalizedText(messages: Record<string, string> | null | undefined, locale: string | undefined): string | null {
  if (!messages) {
    return null;
  }
  const normalizedLocale = (locale || '').trim();
  if (normalizedLocale && messages[normalizedLocale]) {
    return messages[normalizedLocale];
  }
  const language = normalizedLocale.split('-')[0];
  if (language) {
    const matchedKey = Object.keys(messages).find(key => key.split('-')[0] === language);
    if (matchedKey) {
      return messages[matchedKey];
    }
  }
  return messages.default ?? Object.values(messages)[0] ?? null;
}

export function getLocalizedAdapterMeta(adapter: AiProviderAdapter, locale: string | undefined) {
  return {
    label: adapter.plugin_name || adapter.display_name,
    description: pickLocalizedText(adapter.branding.description_locales, locale) || adapter.description,
  };
}

export function getLocalizedCapabilityOptions(locale: string | undefined) {
  return AI_CAPABILITY_OPTIONS.map(item => ({
    ...item,
    label: getLocalizedCapabilityLabel(item.value, locale),
  }));
}

export function sortCapabilities(capabilities: string[]) {
  return Array.from(new Set(capabilities.filter(Boolean))).sort((left, right) => {
    const leftOrder = CAPABILITY_ORDER.get(left) ?? Number.MAX_SAFE_INTEGER;
    const rightOrder = CAPABILITY_ORDER.get(right) ?? Number.MAX_SAFE_INTEGER;
    if (leftOrder !== rightOrder) {
      return leftOrder - rightOrder;
    }
    return left.localeCompare(right);
  });
}

function localizeExamplePrefix(text: string | null | undefined, locale: string | undefined) {
  if (!text) {
    return text ?? null;
  }

  const normalized = text.trim();
  const prefixes = ['例如：', '例如:', 'For example:', 'Example:'];
  const matchedPrefix = prefixes.find(prefix => normalized.startsWith(prefix));
  if (!matchedPrefix) {
    return text;
  }

  return `${getPageMessage(locale, 'settings.ai.provider.examplePrefix')}${normalized.slice(matchedPrefix.length).trimStart()}`;
}

export function getLocalizedField(
  field: AiProviderField,
  locale: string | undefined,
  fieldUi?: { help_text: string | null } | null,
) {
  const label = (() => {
    switch (field.key) {
      case 'display_name':
        return getPageMessage(locale, 'settings.ai.provider.field.displayName');
      case 'provider_code':
        return getPageMessage(locale, 'settings.ai.provider.field.providerCode');
      case 'base_url':
        return getPageMessage(locale, 'settings.ai.provider.field.baseUrl');
      case 'secret_ref':
        return getPageMessage(locale, 'settings.ai.provider.field.secretRef');
      case 'model_name':
        return getPageMessage(locale, 'settings.ai.provider.field.modelName');
      case 'privacy_level':
        return getPageMessage(locale, 'settings.ai.provider.field.privacyLevel');
      case 'anthropic_version':
        return getPageMessage(locale, 'settings.ai.provider.field.anthropicVersion');
      case 'site_url':
        return getPageMessage(locale, 'settings.ai.provider.field.siteUrl');
      case 'app_name':
        return getPageMessage(locale, 'settings.ai.provider.field.appName');
      case 'latency_budget_ms':
        return getPageMessage(locale, 'settings.ai.provider.field.latencyBudgetMs');
      default:
        return field.label;
    }
  })();

  const helpText = (() => {
    if (fieldUi?.help_text) {
      return fieldUi.help_text;
    }
    switch (field.key) {
      case 'base_url':
        return getPageMessage(locale, 'settings.ai.provider.help.baseUrl');
      case 'site_url':
        return getPageMessage(locale, 'settings.ai.provider.help.siteUrl');
      case 'app_name':
        return getPageMessage(locale, 'settings.ai.provider.help.appName');
      default:
        return field.help_text;
    }
  })();

  const options: AiProviderFieldOption[] = field.options.map(option => ({
    ...option,
    label: field.key === 'privacy_level'
      ? ({
        public_cloud: getPageMessage(locale, 'settings.ai.provider.privacy.publicCloud'),
        private_cloud: getPageMessage(locale, 'settings.ai.provider.privacy.privateCloud'),
        local_only: getPageMessage(locale, 'settings.ai.provider.privacy.localOnly'),
      } as Record<string, string>)[option.value] ?? option.label
      : localizeExamplePrefix(option.label, locale) ?? option.label,
  }));

  return {
    ...field,
    label,
    placeholder: localizeExamplePrefix(field.placeholder, locale),
    help_text: localizeExamplePrefix(helpText, locale),
    options,
  };
}

export function getProviderFieldSections(adapter: AiProviderAdapter): Array<AiProviderConfigSection & { fields_meta: AiProviderField[] }> {
  const fieldMap = new Map(adapter.field_schema.map(field => [field.key, field]));
  return adapter.config_ui.sections.map(section => ({
    ...section,
    fields_meta: section.fields.map(fieldKey => fieldMap.get(fieldKey)).filter((field): field is AiProviderField => Boolean(field)),
  }));
}

export function getProviderFieldAction(adapter: AiProviderAdapter, fieldKey: string): AiProviderConfigAction | null {
  return adapter.config_ui.actions.find(action => action.field_key === fieldKey) ?? null;
}

function matchesVisibilityRule(rule: AiProviderConfigVisibilityRule, readValue: (fieldKey: string) => string) {
  const value = readValue(rule.field);
  if (rule.operator === 'truthy') {
    return Boolean(value.trim());
  }
  if (rule.operator === 'in') {
    return Array.isArray(rule.value) ? rule.value.map(String).includes(value) : false;
  }
  if (rule.operator === 'not_equals') {
    return value !== String(rule.value ?? '');
  }
  return value === String(rule.value ?? '');
}

export function isProviderFieldHidden(adapter: AiProviderAdapter, fieldKey: string, readValue: (fieldKey: string) => string) {
  if (adapter.config_ui.hidden_fields.includes(fieldKey)) {
    return true;
  }
  const fieldUi = adapter.config_ui.field_ui[fieldKey];
  if (!fieldUi) {
    return false;
  }
  return fieldUi.hidden_when.some(rule => matchesVisibilityRule(rule, readValue));
}
