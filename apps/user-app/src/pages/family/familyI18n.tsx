import {
  formatLocaleOptionLabel,
  getLocaleDefinition,
  type LocaleDefinition,
} from '@familyclaw/user-core';
import { useI18n as useShellI18n } from '../../runtime';

export { formatLocaleOptionLabel };

export function listLocaleDefinitions(localeDefinitions: LocaleDefinition[]) {
  return localeDefinitions;
}

export function getLocaleLabel(
  locale: string | null | undefined,
  localeDefinitions: LocaleDefinition[],
  formatLocaleLabel: (definition: Pick<LocaleDefinition, 'id' | 'nativeLabel'>) => string,
) {
  if (!locale) {
    return '-';
  }

  const definition = getLocaleDefinition(localeDefinitions, locale);
  return definition ? formatLocaleLabel(definition) : locale;
}

export function useI18n() {
  return useShellI18n();
}
