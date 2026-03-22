export const MARKETPLACE_CONFIRM_CLICK_GUARD_MS = 800;

export function isMarketplaceConfirmClickGuardActive(
  openedAt: number | null,
  now: number = Date.now(),
): boolean {
  if (openedAt === null) {
    return false;
  }
  return now - openedAt < MARKETPLACE_CONFIRM_CLICK_GUARD_MS;
}

export function isMarketplaceInstallActionBusy(
  sourceId: string,
  pluginId: string,
  installingKey: string | null,
): boolean {
  return installingKey === `${sourceId}:${pluginId}`;
}

export function isMarketplaceInstanceActionBusy(
  instanceId: string | null,
  marketplaceBusyInstanceId: string | null,
): boolean {
  if (!instanceId || !marketplaceBusyInstanceId) {
    return false;
  }
  return instanceId === marketplaceBusyInstanceId;
}
