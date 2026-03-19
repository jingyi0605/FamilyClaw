import type { UserGuideManifestStep } from '@familyclaw/user-core';
import { waitForGuideAnchor } from '../../shared/user-guide/anchorRegistry';
import type { UserGuidePlatformAdapter } from '../../shared/user-guide/platformAdapter';

export function createH5UserGuidePlatformAdapter(): UserGuidePlatformAdapter {
  return {
    runtimeTarget: 'h5',
    supportsOverlay: true,
    supportsAnchorRegistration: true,
    async waitForAnchor(anchorId, timeoutMs) {
      return waitForGuideAnchor(anchorId, timeoutMs);
    },
    async beforeStepChange(_step: UserGuideManifestStep) {
      // H5 首版只需要在切换步骤前让路由和页面先稳定下来。
    },
  };
}
