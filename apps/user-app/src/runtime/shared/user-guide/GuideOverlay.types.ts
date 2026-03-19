import type { UserGuideRuntimeStatus } from '@familyclaw/user-core';

export type UserGuideOverlayProps = {
  currentStepIndex: number;
  totalSteps: number;
  title: string;
  content: string;
  anchorId: string | null;
  status: UserGuideRuntimeStatus;
  errorMessage: string;
  isLastStep: boolean;
  isActionPending: boolean;
  onPrevious: () => void;
  onNext: () => void;
  onFinish: () => void;
  onSkip: () => void;
};
