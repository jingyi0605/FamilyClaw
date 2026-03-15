import Taro from '@tarojs/taro';
import { KeyValueStorage } from './types';

export function createTaroStorageAdapter(): KeyValueStorage {
  return {
    async getItem(key) {
      try {
        return Taro.getStorageSync(key) ?? null;
      } catch {
        return null;
      }
    },
    async setItem(key, value) {
      Taro.setStorageSync(key, value);
    },
    async removeItem(key) {
      Taro.removeStorageSync(key);
    },
    async keys() {
      try {
        return Taro.getStorageInfoSync().keys ?? [];
      } catch {
        return [];
      }
    },
  };
}
