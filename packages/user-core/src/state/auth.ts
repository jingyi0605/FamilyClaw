import { AuthActor } from '../domain/types';

export const CLIENT_ONLY_STORAGE_PREFIXES = [
  'familyclaw-conversation-sessions',
  'familyclaw-assistant-sessions',
] as const;

export type StorageAdapter = {
  keys?: () => Promise<string[]>;
  removeItem: (key: string) => Promise<void>;
};

export async function clearClientOnlyStorage(
  storage: StorageAdapter,
  prefixes: readonly string[] = CLIENT_ONLY_STORAGE_PREFIXES,
) {
  if (!storage.keys) {
    return;
  }

  const keys = await storage.keys();
  await Promise.all(
    keys
      .filter(key => prefixes.some(prefix => key.startsWith(prefix)))
      .map(key => storage.removeItem(key)),
  );
}

export function isAuthenticatedActor(actor: AuthActor | null): boolean {
  return Boolean(actor?.authenticated);
}
