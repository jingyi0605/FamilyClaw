import { getPageMessage } from '../../../runtime/h5-shell/i18n/pageMessageUtils';
import {
  AI_CAPABILITY_OPTIONS,
  getCapabilityLabel,
} from '../../setup/setupAiConfig';
import type {
  AiProviderAdapter,
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

export function getLocalizedAdapterMeta(adapter: AiProviderAdapter, locale: string | undefined) {
  const descriptionKey = ({
    chatgpt: 'settings.ai.provider.adapter.chatgpt',
    deepseek: 'settings.ai.provider.adapter.deepseek',
    qwen: 'settings.ai.provider.adapter.qwen',
    glm: 'settings.ai.provider.adapter.glm',
    siliconflow: 'settings.ai.provider.adapter.siliconflow',
    kimi: 'settings.ai.provider.adapter.kimi',
    minimax: 'settings.ai.provider.adapter.minimax',
    claude: 'settings.ai.provider.adapter.claude',
    gemini: 'settings.ai.provider.adapter.gemini',
    openrouter: 'settings.ai.provider.adapter.openrouter',
    doubao: 'settings.ai.provider.adapter.doubao',
    'doubao-coding': 'settings.ai.provider.adapter.doubaoCoding',
    byteplus: 'settings.ai.provider.adapter.byteplus',
    'byteplus-coding': 'settings.ai.provider.adapter.byteplusCoding',
  } as Record<string, string | undefined>)[adapter.adapter_code];

  return {
    label: adapter.plugin_name || adapter.display_name,
    description: descriptionKey ? getPageMessage(locale, descriptionKey as any) : adapter.description,
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

export function getLocalizedField(field: AiProviderField, locale: string | undefined) {
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
