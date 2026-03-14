import type { Household, HouseholdSetupStatus } from '../lib/types';

const CLIENT_ONLY_STORAGE_PREFIXES = [
  'familyclaw-conversation-sessions',
  'familyclaw-assistant-sessions',
] as const;

export const HOUSEHOLD_STORAGE_KEY = 'familyclaw-household';

export interface HouseholdSummary {
  id: string;
  name: string;
  city?: string | null;
  timezone?: string;
  locale?: string;
  status?: string;
  region?: Household['region'];
}

interface SetupStatusClient {
  getHouseholdSetupStatus: (householdId: string) => Promise<HouseholdSetupStatus>;
}

export async function clearClientOnlyStorage(
  prefixes: readonly string[] = CLIENT_ONLY_STORAGE_PREFIXES,
): Promise<void> {
  if (typeof globalThis.localStorage === 'undefined') {
    return;
  }

  const keys = Array.from({ length: globalThis.localStorage.length }, (_, index) =>
    globalThis.localStorage.key(index),
  ).filter((key): key is string => Boolean(key));

  for (const key of keys) {
    if (!prefixes.some(prefix => key.startsWith(prefix))) {
      continue;
    }

    try {
      globalThis.localStorage.removeItem(key);
    } catch {
      // 忽略单个 key 的清理失败，避免登出流程被本地存储异常卡死
    }
  }
}

export function toHouseholdSummary(household: Household): HouseholdSummary {
  return {
    id: household.id,
    name: household.name,
    city: household.city,
    timezone: household.timezone,
    locale: household.locale,
    status: household.status,
    region: household.region,
  };
}

export async function loadHouseholdSetupStatus(
  client: SetupStatusClient,
  householdId: string,
): Promise<HouseholdSetupStatus | null> {
  if (!householdId) {
    return null;
  }

  return client.getHouseholdSetupStatus(householdId);
}
