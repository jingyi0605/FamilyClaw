import { createCoreApiClient, createRequestClient, loadBootstrapSnapshot } from '@familyclaw/user-core';
import { getPlatformTarget, createTaroStorageAdapter } from '@familyclaw/user-platform';

const coreApiClient = createCoreApiClient(
  createRequestClient({
    baseUrl: '/api/v1',
  }),
);

const taroStorage = createTaroStorageAdapter();

export async function loadUserAppBootstrap() {
  return loadBootstrapSnapshot({
    client: coreApiClient,
    platformTarget: getPlatformTarget(),
    storage: taroStorage,
  });
}

export { coreApiClient, taroStorage };
