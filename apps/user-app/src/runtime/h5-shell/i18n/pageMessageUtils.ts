import { PAGE_MESSAGES } from './pageMessages';

type MessageKey = keyof typeof PAGE_MESSAGES['en-US'];

function formatMessage(template: string, params?: Record<string, string | number>) {
  if (!params) {
    return template;
  }
  return Object.entries(params).reduce(
    (result, [key, value]) => result.replaceAll(`{${key}}`, String(value)),
    template,
  );
}

function resolveLocale(locale?: string) {
  return locale?.toLowerCase().startsWith('en') ? 'en-US' : 'zh-CN';
}

export function getPageMessage(
  locale: string | undefined,
  key: MessageKey,
  params?: Record<string, string | number>,
) {
  const bundle = PAGE_MESSAGES[resolveLocale(locale)] as Record<string, string>;
  const fallbackBundle = PAGE_MESSAGES['en-US'] as Record<string, string>;
  const template = bundle[key] ?? fallbackBundle[key] ?? key;
  return formatMessage(template, params);
}
