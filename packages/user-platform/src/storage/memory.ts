import { KeyValueStorage } from './types';

export function createMemoryStorage(initialState?: Record<string, string>): KeyValueStorage {
  const store = new Map<string, string>(Object.entries(initialState ?? {}));

  return {
    async getItem(key) {
      return store.get(key) ?? null;
    },
    async setItem(key, value) {
      store.set(key, value);
    },
    async removeItem(key) {
      store.delete(key);
    },
    async keys() {
      return Array.from(store.keys());
    },
  };
}
