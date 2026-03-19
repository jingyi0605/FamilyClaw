import type { UserGuideManifestStep } from '@familyclaw/user-core';
import { waitForGuideAnchor } from '../../shared/user-guide/anchorRegistry';
import type { UserGuidePlatformAdapter } from '../../shared/user-guide/platformAdapter';

export function createRnUserGuidePlatformAdapter(): UserGuidePlatformAdapter {
  return {
    runtimeTarget: 'rn',
    supportsOverlay: true,
    supportsAnchorRegistration: true,
    async waitForAnchor(anchorId, timeoutMs) {
      return waitForGuideAnchor(anchorId, timeoutMs);
    },
    async beforeStepChange(_step: UserGuideManifestStep) {
      // RN 第一版先保持最小行为，不在这里引入额外测量和滚动复杂度。
    },
  };
}
