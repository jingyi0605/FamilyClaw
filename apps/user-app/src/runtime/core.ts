import { createCoreApiClient, createRequestClient, loadBootstrapSnapshot } from '@familyclaw/user-core';
import { getPlatformTarget, createTaroStorageAdapter, createBrowserStorageAdapter } from '@familyclaw/user-platform';

const coreApiClient = createCoreApiClient(
  createRequestClient({
    baseUrl: '/api/v1',
  }),
);

// 在 H5 环境中使用浏览器存储，其他环境使用 Taro 存储
const appStorage = process.env.TARO_ENV === 'h5'
  ? createBrowserStorageAdapter()
  : createTaroStorageAdapter();

export async function loadUserAppBootstrap() {
  return loadBootstrapSnapshot({
    client: coreApiClient,
    platformTarget: getPlatformTarget(),
    storage: appStorage,
  });
}

export { coreApiClient, appStorage };
