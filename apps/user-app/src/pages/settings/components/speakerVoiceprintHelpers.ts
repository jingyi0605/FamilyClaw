import type {
  HouseholdVoiceprintMemberSummaryRead,
  VoiceprintConversationMode,
  VoiceprintEnrollmentRead,
} from '../settingsTypes';

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

export function getVoiceprintConversationCopy(voiceprintIdentityEnabled: boolean): {
  mode: VoiceprintConversationMode;
  title: string;
  lines: string[];
} {
  if (voiceprintIdentityEnabled) {
    return {
      mode: 'voiceprint_member',
      title: '当前按成员路由处理',
      lines: [
        '系统会优先按声纹识别成员。',
        '识别成功后进入对应成员对话。',
        '识别失败时会按后端既有降级规则继续处理，不会把语音主链打断。',
      ],
    };
  }

  return {
    mode: 'public',
    title: '当前按公开对话处理',
    lines: [
      '这台设备当前不会按声纹识别成员。',
      '所有家庭成员都可以看到这台设备的对话内容。',
      '关闭声纹识别不会删除已有声纹档案，只是把这台设备切回公开对话。',
    ],
  };
}

export function getVoiceprintMemberStatusMeta(summary: HouseholdVoiceprintMemberSummaryRead): {
  label: string;
  tone: 'secondary' | 'success' | 'danger' | 'info' | 'warning';
  actionLabel: string;
  disabled: boolean;
  description: string;
} {
  switch (summary.status) {
    case 'pending':
      return {
        label: '建档中',
        tone: 'info',
        actionLabel: '查看进度',
        disabled: false,
        description: `当前正在处理样本，已采集 ${summary.sample_count} 轮。`,
      };
    case 'active':
      return {
        label: '可用',
        tone: 'success',
        actionLabel: '更新声纹',
        disabled: false,
        description: summary.sample_count > 0 ? `当前档案已可用，累计样本 ${summary.sample_count} 轮。` : '当前档案已可用。',
      };
    case 'failed':
      return {
        label: '失败',
        tone: 'danger',
        actionLabel: '重新录入',
        disabled: false,
        description: summary.error_message || '最近一次建档没有成功，可以重新开始。',
      };
    case 'disabled':
      return {
        label: '已停用',
        tone: 'warning',
        actionLabel: '重新录入',
        disabled: false,
        description: '已有历史档案，但当前不可用，需要重新录入。',
      };
    default:
      return {
        label: '未建档',
        tone: 'secondary',
        actionLabel: '开始录入',
        disabled: false,
        description: '还没有可用声纹档案，需要先完成首次录入。',
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
      error: enrollment.error_message || '这次录入没有成功，可以重新开始。',
    };
  }
  return { ...state, step: 'waiting', enrollmentId: enrollment.id, error: '' };
}

export function formatVoiceprintTime(value: string | null) {
  if (!value) return '暂无记录';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('zh-CN', {
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}
