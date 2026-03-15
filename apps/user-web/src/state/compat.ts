import {
  CLIENT_ONLY_STORAGE_PREFIXES,
  HOUSEHOLD_STORAGE_KEY,
  clearClientOnlyStorage as clearSharedClientOnlyStorage,
  loadSetupStatus,
  toHouseholdSummary,
  type HouseholdSummary,
} from '@familyclaw/user-core';
import { createBrowserStorageAdapter } from '@familyclaw/user-platform/web';
import type { HouseholdSetupStatus } from '../lib/types';

interface SetupStatusClient {
  getHouseholdSetupStatus: (householdId: string) => Promise<HouseholdSetupStatus>;
}

const browserStorage = createBrowserStorageAdapter();

export async function clearClientOnlyStorage(
  prefixes: readonly string[] = CLIENT_ONLY_STORAGE_PREFIXES,
): Promise<void> {
  await clearSharedClientOnlyStorage(browserStorage, prefixes);
}

export async function loadHouseholdSetupStatus(
  client: SetupStatusClient,
  householdId: string,
): Promise<HouseholdSetupStatus | null> {
  return loadSetupStatus(client, householdId);
}

export type { HouseholdSummary };
export { HOUSEHOLD_STORAGE_KEY, toHouseholdSummary };
