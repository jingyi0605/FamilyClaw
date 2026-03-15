import { Household } from '../domain/types';

export type StorageAdapter = {
  getItem: (key: string) => Promise<string | null>;
  setItem: (key: string, value: string) => Promise<void>;
  removeItem: (key: string) => Promise<void>;
};

export interface HouseholdSummary {
  id: string;
  name: string;
  city?: string | null;
  timezone?: string;
  locale?: string;
  status?: string;
  region?: Household['region'];
}

export const HOUSEHOLD_STORAGE_KEY = 'familyclaw-household';

export async function getStoredHouseholdId(storage: StorageAdapter, storageKey = HOUSEHOLD_STORAGE_KEY) {
  return (await storage.getItem(storageKey)) ?? '';
}

export async function persistHouseholdId(
  storage: StorageAdapter,
  householdId: string,
  storageKey = HOUSEHOLD_STORAGE_KEY,
) {
  if (!householdId) {
    await storage.removeItem(storageKey);
    return;
  }

  await storage.setItem(storageKey, householdId);
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
