import type { UserGuideManifestStep } from '@familyclaw/user-core';

export type UserGuidePlatformAdapter = {
  runtimeTarget: 'h5' | 'rn';
  supportsOverlay: boolean;
  supportsAnchorRegistration: boolean;
  waitForAnchor: (anchorId: string, timeoutMs: number) => Promise<'resolved' | 'timeout'>;
  beforeStepChange: (step: UserGuideManifestStep) => Promise<void>;
};
