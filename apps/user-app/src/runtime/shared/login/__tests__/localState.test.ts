import test from 'node:test';
import assert from 'node:assert/strict';
import type { KeyValueStorage } from '@familyclaw/user-platform';
import {
  BOOTSTRAP_LOGIN_USERNAME,
  LOGIN_BOOTSTRAP_PREFILL_DISMISSED_KEY,
  dismissBootstrapLoginPrefillForUsername,
  markBootstrapLoginPrefillDismissed,
  readBootstrapLoginPrefillDismissed,
} from '../localState';

function createMemoryStorage(): KeyValueStorage {
  const store = new Map<string, string>();

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

test('默认情况下仍允许首登预填 bootstrap 账号', async () => {
  const storage = createMemoryStorage();

  assert.equal(await readBootstrapLoginPrefillDismissed(storage), false);
});

test('markBootstrapLoginPrefillDismissed 会永久关闭 bootstrap 预填', async () => {
  const storage = createMemoryStorage();

  await markBootstrapLoginPrefillDismissed(storage);

  assert.equal(await readBootstrapLoginPrefillDismissed(storage), true);
  assert.equal(await storage.getItem(LOGIN_BOOTSTRAP_PREFILL_DISMISSED_KEY), '1');
});

test('dismissBootstrapLoginPrefillForUsername 遇到正式账号会关闭预填', async () => {
  const storage = createMemoryStorage();

  const dismissed = await dismissBootstrapLoginPrefillForUsername(storage, 'alice');

  assert.equal(dismissed, true);
  assert.equal(await readBootstrapLoginPrefillDismissed(storage), true);
});

test('dismissBootstrapLoginPrefillForUsername 遇到 bootstrap 账号不会误伤默认行为', async () => {
  const storage = createMemoryStorage();

  const dismissed = await dismissBootstrapLoginPrefillForUsername(storage, BOOTSTRAP_LOGIN_USERNAME);

  assert.equal(dismissed, false);
  assert.equal(await readBootstrapLoginPrefillDismissed(storage), false);
});
