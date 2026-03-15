import { KeyValueStorage } from './types';
import { createMemoryStorage } from './memory';

export function createBrowserStorageAdapter(): KeyValueStorage {
  const fallback = createMemoryStorage();

  return {
    async getItem(key) {
      try {
        return globalThis.localStorage?.getItem(key) ?? null;
      } catch {
        return fallback.getItem(key);
      }
    },
    async setItem(key, value) {
      try {
        globalThis.localStorage?.setItem(key, value);
        return;
      } catch {
        await fallback.setItem(key, value);
      }
    },
    async removeItem(key) {
      try {
        globalThis.localStorage?.removeItem(key);
        return;
      } catch {
        await fallback.removeItem(key);
      }
    },
    async keys() {
      try {
        if (!globalThis.localStorage) {
          return fallback.keys();
        }

        return Array.from({ length: globalThis.localStorage.length }, (_, index) => globalThis.localStorage.key(index))
          .filter((key): key is string => Boolean(key));
      } catch {
        return fallback.keys();
      }
    },
  };
}
