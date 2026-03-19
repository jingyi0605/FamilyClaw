import test from 'node:test';
import assert from 'node:assert/strict';
import type { KeyValueStorage } from '@familyclaw/user-platform';
import { USER_GUIDE_AUTO_START_STORAGE_KEY, USER_GUIDE_SESSION_STORAGE_KEY } from '../constants';
import {
  clearGuideSessionCheckpoint,
  clearPendingGuideAutoStart,
  consumePendingGuideAutoStart,
  markPendingGuideAutoStart,
  readPendingGuideAutoStart,
  readGuideSessionCheckpoint,
  saveGuideSessionCheckpoint,
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

test('markPendingGuideAutoStart 和 consumePendingGuideAutoStart 会写入并消费一次性标记', async () => {
  const storage = createMemoryStorage();

  await markPendingGuideAutoStart(storage);
  const firstRead = await consumePendingGuideAutoStart(storage);
  const secondRead = await consumePendingGuideAutoStart(storage);

  assert.equal(firstRead?.source, 'auto_after_setup');
  assert.equal(typeof firstRead?.created_at, 'string');
  assert.equal(secondRead, null);
});

test('clearPendingGuideAutoStart 会清理残留标记', async () => {
  const storage = createMemoryStorage();

  await markPendingGuideAutoStart(storage);
  await clearPendingGuideAutoStart(storage);

  assert.equal(await consumePendingGuideAutoStart(storage), null);
});

test('consumePendingGuideAutoStart 遇到脏数据时会安全返回 null', async () => {
  const storage = createMemoryStorage();
  await storage.setItem(USER_GUIDE_AUTO_START_STORAGE_KEY, '{"source":"unknown"}');

  const payload = await consumePendingGuideAutoStart(storage);

  assert.equal(payload, null);
});

test('readPendingGuideAutoStart 只读取标记，不会提前消费', async () => {
  const storage = createMemoryStorage();

  await markPendingGuideAutoStart(storage);
  const pendingLaunch = await readPendingGuideAutoStart(storage);
  const consumedLaunch = await consumePendingGuideAutoStart(storage);

  assert.equal(pendingLaunch?.source, 'auto_after_setup');
  assert.equal(consumedLaunch?.source, 'auto_after_setup');
  assert.equal(await consumePendingGuideAutoStart(storage), null);
});

test('saveGuideSessionCheckpoint 和 readGuideSessionCheckpoint 会保留最近一步', async () => {
  const storage = createMemoryStorage();

  await saveGuideSessionCheckpoint(storage, {
    manifest_version: 1,
    current_step_index: 3,
    source: 'manual',
    updated_at: '2026-03-19T11:00:00Z',
  });

  const checkpoint = await readGuideSessionCheckpoint(storage);

  assert.deepEqual(checkpoint, {
    manifest_version: 1,
    current_step_index: 3,
    source: 'manual',
    updated_at: '2026-03-19T11:00:00Z',
  });
});

test('clearGuideSessionCheckpoint 会清空导览恢复信息', async () => {
  const storage = createMemoryStorage();
  await storage.setItem(USER_GUIDE_SESSION_STORAGE_KEY, '{"manifest_version":1,"current_step_index":1,"source":"manual"}');

  await clearGuideSessionCheckpoint(storage);

  assert.equal(await readGuideSessionCheckpoint(storage), null);
});
