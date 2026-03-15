import Taro from '@tarojs/taro';
import { createBrowserStorageAdapter } from './browser';
import { KeyValueStorage } from './types';

export function createTaroStorageAdapter(): KeyValueStorage {
  const fallback = createBrowserStorageAdapter();

  return {
    async getItem(key) {
      if (typeof Taro.getStorageSync !== 'function') {
        return fallback.getItem(key);
      }

      try {
        return Taro.getStorageSync(key) ?? null;
      } catch {
        return fallback.getItem(key);
      }
    },
    async setItem(key, value) {
      if (typeof Taro.setStorageSync !== 'function') {
        await fallback.setItem(key, value);
        return;
      }

      try {
        Taro.setStorageSync(key, value);
      } catch {
        await fallback.setItem(key, value);
      }
    },
    async removeItem(key) {
      if (typeof Taro.removeStorageSync !== 'function') {
        await fallback.removeItem(key);
        return;
      }

      try {
        Taro.removeStorageSync(key);
      } catch {
        await fallback.removeItem(key);
      }
    },
    async keys() {
      if (typeof Taro.getStorageInfoSync !== 'function') {
        return fallback.keys();
      }

      try {
        return Taro.getStorageInfoSync().keys ?? [];
      } catch {
        return fallback.keys();
      }
    },
  };
}
