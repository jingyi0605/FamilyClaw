import { CoreApiClient } from '../api';
import { HouseholdSetupStatus } from '../domain/types';

export async function loadSetupStatus(
  client: Pick<CoreApiClient, 'getHouseholdSetupStatus'>,
  householdId: string,
): Promise<HouseholdSetupStatus | null> {
  if (!householdId) {
    return null;
  }

  return client.getHouseholdSetupStatus(householdId);
}
