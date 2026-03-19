import type { KeyValueStorage } from '@familyclaw/user-platform';

export const BOOTSTRAP_LOGIN_USERNAME = 'user';
export const BOOTSTRAP_LOGIN_PASSWORD = 'user';
export const LOGIN_BOOTSTRAP_PREFILL_DISMISSED_KEY = 'familyclaw:user-app:login-bootstrap-prefill-dismissed';

export async function readBootstrapLoginPrefillDismissed(
  storage: Pick<KeyValueStorage, 'getItem'>,
): Promise<boolean> {
  try {
    return (await storage.getItem(LOGIN_BOOTSTRAP_PREFILL_DISMISSED_KEY)) === '1';
  } catch {
    return false;
  }
}

export async function markBootstrapLoginPrefillDismissed(
  storage: Pick<KeyValueStorage, 'setItem'>,
) {
  await storage.setItem(LOGIN_BOOTSTRAP_PREFILL_DISMISSED_KEY, '1');
}

export async function dismissBootstrapLoginPrefillForUsername(
  storage: Pick<KeyValueStorage, 'setItem'>,
  username: string | null | undefined,
): Promise<boolean> {
  const normalizedUsername = username?.trim();
  if (!normalizedUsername || normalizedUsername === BOOTSTRAP_LOGIN_USERNAME) {
    return false;
  }

  await markBootstrapLoginPrefillDismissed(storage);
  return true;
}

export function readBootstrapLoginPrefillDismissedFromBrowserStorage(): boolean {
  try {
    return globalThis.localStorage?.getItem(LOGIN_BOOTSTRAP_PREFILL_DISMISSED_KEY) === '1';
  } catch {
    return false;
  }
}
