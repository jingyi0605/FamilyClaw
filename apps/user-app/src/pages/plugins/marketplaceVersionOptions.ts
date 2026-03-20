import type {
  MarketplaceVersionOptionAction,
  MarketplaceVersionOptionRead,
  MarketplaceVersionOptionsRead,
} from '../settings/settingsTypes';

export function getDefaultMarketplaceVersionSelection(options: MarketplaceVersionOptionsRead | null): string {
  if (!options) {
    return '';
  }
  const installed = options.items.find(item => item.is_installed);
  if (installed) {
    return installed.version;
  }
  const latestCompatible = options.items.find(item => item.is_latest_compatible);
  return latestCompatible?.version ?? '';
}

export function isMarketplaceVersionActionable(action: MarketplaceVersionOptionAction): boolean {
  return action === 'install' || action === 'upgrade' || action === 'rollback';
}

export function resolveMarketplaceVersionActionStatusKey(action: MarketplaceVersionOptionAction): string | null {
  switch (action) {
    case 'install':
      return 'plugins.marketplace.status.installed';
    case 'upgrade':
      return 'plugins.marketplace.status.upgraded';
    case 'rollback':
      return 'plugins.marketplace.status.rolledBack';
    default:
      return null;
  }
}

export function resolveMarketplaceVersionOptionByVersion(
  options: MarketplaceVersionOptionsRead | null,
  version: string,
): MarketplaceVersionOptionRead | null {
  if (!options) {
    return null;
  }
  return options.items.find(item => item.version === version) ?? null;
}
