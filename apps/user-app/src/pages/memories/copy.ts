import { useCallback } from 'react';
import { useI18n } from '../../runtime';

export function useMemoriesText() {
  const { t } = useI18n();

  return useCallback((key: string, params?: Record<string, string | number>) => t(key, params), [t]);
}
