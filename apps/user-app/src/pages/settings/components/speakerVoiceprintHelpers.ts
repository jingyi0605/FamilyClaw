import { getPageMessage } from '../../../runtime/h5-shell/i18n/pageMessageUtils';
import type {
  HouseholdVoiceprintMemberSummaryRead,
  VoiceprintConversationMode,
  VoiceprintEnrollmentRead,
} from '../settingsTypes';

type TranslateFn = (key: string, params?: Record<string, string | number>) => string;
const defaultTranslate: TranslateFn = (key, params) => getPageMessage('zh-CN', key as keyof typeof import('../../../runtime/h5-shell/i18n/pageMessages').PAGE_MESSAGES['en-US'], params);

export type VoiceprintWizardMode = 'create' | 'update';
export type VoiceprintWizardStep = 'select_member' | 'confirm' | 'creating' | 'waiting' | 'success' | 'failed';

export type VoiceprintWizardState = {
  mode: VoiceprintWizardMode;
  step: VoiceprintWizardStep;
  memberId: string | null;
  enrollmentId: string | null;
  lockedMemberId: string | null;
  error: string;
};

export function createVoiceprintWizardState(mode: VoiceprintWizardMode, memberId?: string | null): VoiceprintWizardState {
  const normalizedMemberId = memberId ?? null;
  return {
    mode,
    step: normalizedMemberId ? 'confirm' : 'select_member',
    memberId: normalizedMemberId,
    enrollmentId: null,
    lockedMemberId: normalizedMemberId,
    error: '',
  };
}

export function createVoiceprintWaitingWizardState(
  memberId: string,
  enrollmentId: string,
  mode: VoiceprintWizardMode = 'create',
): VoiceprintWizardState {
  return {
    mode,
    step: 'waiting',
    memberId,
    enrollmentId,
    lockedMemberId: memberId,
    error: '',
  };
}

export function getVoiceprintConversationCopy(
  voiceprintIdentityEnabled: boolean,
  t: TranslateFn = defaultTranslate,
): {
  mode: VoiceprintConversationMode;
  title: string;
  lines: string[];
} {
  if (voiceprintIdentityEnabled) {
    return {
      mode: 'voiceprint_member',
      title: t('voiceprint.tab.conversation.memberTitle'),
      lines: [
        t('voiceprint.tab.conversation.memberLine1'),
        t('voiceprint.tab.conversation.memberLine2'),
        t('voiceprint.tab.conversation.memberLine3'),
      ],
    };
  }

  return {
    mode: 'public',
    title: t('voiceprint.tab.conversation.publicTitle'),
    lines: [
      t('voiceprint.tab.conversation.publicLine1'),
      t('voiceprint.tab.conversation.publicLine2'),
      t('voiceprint.tab.conversation.publicLine3'),
    ],
  };
}

export function getVoiceprintMemberStatusMeta(
  summary: HouseholdVoiceprintMemberSummaryRead,
  t: TranslateFn = defaultTranslate,
): {
  label: string;
  tone: 'secondary' | 'success' | 'danger' | 'info' | 'warning';
  actionLabel: string;
  disabled: boolean;
  description: string;
} {
  switch (summary.status) {
    case 'pending':
      return {
        label: t('voiceprint.tab.status.pending.label'),
        tone: 'info',
        actionLabel: t('voiceprint.tab.status.pending.action'),
        disabled: false,
        description: t('voiceprint.tab.status.pending.desc', { count: summary.sample_count }),
      };
    case 'active':
      return {
        label: t('voiceprint.tab.status.active.label'),
        tone: 'success',
        actionLabel: t('voiceprint.tab.status.active.action'),
        disabled: false,
        description: summary.sample_count > 0
          ? t('voiceprint.tab.status.active.desc', { count: summary.sample_count })
          : t('voiceprint.tab.status.active.descNoCount'),
      };
    case 'failed':
      return {
        label: t('voiceprint.tab.status.failed.label'),
        tone: 'danger',
        actionLabel: t('voiceprint.tab.status.failed.action'),
        disabled: false,
        description: summary.error_message || t('voiceprint.tab.status.failed.desc'),
      };
    case 'disabled':
      return {
        label: t('voiceprint.tab.status.disabled.label'),
        tone: 'warning',
        actionLabel: t('voiceprint.tab.status.disabled.action'),
        disabled: false,
        description: t('voiceprint.tab.status.disabled.desc'),
      };
    default:
      return {
        label: t('voiceprint.tab.status.empty.label'),
        tone: 'secondary',
        actionLabel: t('voiceprint.tab.status.empty.action'),
        disabled: false,
        description: t('voiceprint.tab.status.empty.desc'),
      };
  }
}

export function getNextWizardStateFromEnrollment(
  state: VoiceprintWizardState,
  enrollment: VoiceprintEnrollmentRead,
): VoiceprintWizardState {
  if (enrollment.status === 'completed') {
    return { ...state, step: 'success', enrollmentId: enrollment.id, error: '' };
  }
  if (enrollment.status === 'failed' || enrollment.status === 'cancelled') {
    return {
      ...state,
      step: 'failed',
      enrollmentId: enrollment.id,
      error: enrollment.error_message || '',
    };
  }
  return { ...state, step: 'waiting', enrollmentId: enrollment.id, error: '' };
}

export function formatVoiceprintTime(
  value: string | null,
  locale = 'zh-CN',
  t: TranslateFn = defaultTranslate,
) {
  if (!value) return t('voiceprint.tab.time.empty');
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(locale.toLowerCase().startsWith('en') ? 'en-US' : 'zh-CN', {
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}
