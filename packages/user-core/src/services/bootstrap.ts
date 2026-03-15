import { CoreApiClient } from '../api';
import { AppPlatformTarget, AuthActor, Household, HouseholdSetupStatus, PluginLocaleListResponse } from '../domain/types';
import { getStoredHouseholdId, persistHouseholdId } from '../state';

type StorageAdapter = {
  getItem: (key: string) => Promise<string | null>;
  setItem: (key: string, value: string) => Promise<void>;
  removeItem: (key: string) => Promise<void>;
};

export type BootstrapSnapshot = {
  actor: AuthActor | null;
  households: Household[];
  currentHousehold: Household | null;
  setupStatus: HouseholdSetupStatus | null;
  platformTarget: AppPlatformTarget;
  locales: PluginLocaleListResponse['items'];
};

export async function loadBootstrapSnapshot(options: {
  client: CoreApiClient;
  platformTarget: AppPlatformTarget;
  storage: StorageAdapter;
}) {
  const { client, platformTarget, storage } = options;

  let actor: AuthActor | null = null;
  try {
    const authResult = await client.getAuthMe();
    actor = authResult.actor;
  } catch {
    actor = null;
  }

  if (!actor?.authenticated) {
    return {
      actor: null,
      households: [],
      currentHousehold: null,
      setupStatus: null,
      platformTarget,
      locales: [],
    } satisfies BootstrapSnapshot;
  }

  const householdsResponse = await client.listHouseholds();
  const storedHouseholdId = await getStoredHouseholdId(storage);
  const preferredHouseholdId = storedHouseholdId || actor.household_id || householdsResponse.items[0]?.id || '';
  const currentHousehold = householdsResponse.items.find(item => item.id === preferredHouseholdId) ?? null;

  if (currentHousehold) {
    await persistHouseholdId(storage, currentHousehold.id);
  }

  const [setupStatus, locales] = await Promise.all([
    currentHousehold ? client.getHouseholdSetupStatus(currentHousehold.id).catch(() => null) : Promise.resolve(null),
    currentHousehold ? client.listHouseholdLocales(currentHousehold.id).then(result => result.items).catch(() => []) : Promise.resolve([]),
  ]);

  return {
    actor,
    households: householdsResponse.items,
    currentHousehold,
    setupStatus,
    platformTarget,
    locales,
  } satisfies BootstrapSnapshot;
}
